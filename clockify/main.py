import argparse
import calendar as cal
import contextlib
import io
import itertools
import logging
import os
import pickle
import sqlite3
import sys
import tempfile
import threading
import time
from collections.abc import Generator
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from typing import Any

import werkzeug.wrappers
from flask import Flask
from flask import redirect
from flask import request
from flask import send_file
from flask import session

from clockify.api import ClockifyClient
from clockify.api import ClockifySession
from clockify.api import ClockifySession1
from clockify.invoice import Invoice
from clockify.store import Store

logger = logging.getLogger(__name__)
app = Flask(__name__)


@app.template_filter("format_date")
def format_date(value: date, format: str = "%d/%m/%Y") -> str:
    return value.strftime(format)


@app.route("/download", methods=["GET"])
def download() -> werkzeug.wrappers.Response:
    if "invoice" not in session:
        return redirect("/")

    invoice: Invoice = pickle.loads(session["invoice"])
    return send_file(
        io.BytesIO(invoice.pdf(form_data={"display-form": "none"})),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=invoice.invoice_name,  # type: ignore
    )


@app.route("/", methods=["GET", "POST"])
def process_invoice() -> str:
    today = date.today()
    years = list(range(today.year, today.year - 5, -1))

    form_data: dict[str, Any] = {
        "months": list(cal.month_name[1:]),
        "years": years,
        "display-form": "block",
        "invoice-number": "1",
        "month": today.month,
        "year": today.year,
    }

    if request.method == "POST":
        form_data.update(request.form)

    year, month = int(form_data["year"]), int(form_data["month"])
    _, days_in_month = cal.monthrange(year, month)
    period_start, period_end = date(year, month, 1), date(year, month, days_in_month)

    invoice_number = form_data["invoice-number"]

    if "invoice" in session:
        invoice: Invoice = pickle.loads(session["invoice"])
        invoice.invoice_number = invoice_number
        invoice.period_start = period_start
        invoice.period_end = period_end
        invoice.update_time_entries()
    else:
        store: Store = app.config["store"]
        invoice_company = "Jordan Amos"
        invoice_client = "6 Cloud Systems"
        invoice = Invoice(
            store,
            invoice_number,
            invoice_company,
            invoice_client,
            period_start,
            period_end,
        )

    session["invoice"] = pickle.dumps(invoice)

    return invoice.html(form_data=form_data)


def run_interactive(store: Store, api_key: str) -> int:
    app.config["store"] = store
    app.secret_key = api_key
    app.run(host="0.0.0.0", port=5000, debug=True)
    return 0


def generate_invoice(store: Store) -> int:
    workspace_id = store.get_workspace_id()
    user_id = store.get_user_id()
    if not (workspace_id and user_id):
        print(
            f"ERROR generating invoice: Invalid User ({user_id}) or "
            f"Workspace ({workspace_id})"
        )
        return 1

    invoice_number = "1"
    invoice_company = "Jordan Amos"
    invoice_client = "6 Cloud Systems"

    today = date.today()
    year, month = today.year, today.month
    _, days_in_month = cal.monthrange(year, month)
    period_start, period_end = date(year, month, 1), date(year, month, days_in_month)

    invoice = Invoice(
        store,
        invoice_number,
        invoice_company,
        invoice_client,
        period_start,
        period_end,
    )
    print(invoice)
    return 0


@contextlib.contextmanager
def spinner(message: str) -> Generator[None, None, None]:
    def spin() -> None:
        while running:
            sys.stdout.write(f"{next(spin_cycle)} {message}\r")
            sys.stdout.flush()
            time.sleep(0.1)
            sys.stdout.write(clear)
            sys.stdout.flush()

    spin_cycle = itertools.cycle(["-", "\\", "|", "/"])
    clear = f"\r{' ' * (len(message) + 2)}\r"
    running = True
    thread = threading.Thread(target=spin)
    try:
        thread.start()
        yield
    finally:
        running = False
        thread.join()
        sys.stdout.write(clear)
        sys.stdout.flush()


def synch_user(api_session: ClockifyClient, db: sqlite3.Connection) -> tuple[str, str]:
    """
    Fetches the User from the clockify API and inserts the User into the db.
    Returns the user id and workspace id
    """
    user = api_session.get_user()
    user_table_data = (
        user["id"],
        user["name"],
        user["email"],
        user["defaultWorkspace"],
        user["activeWorkspace"],
    )
    db.execute("INSERT INTO user VALUES(?,?,?,?,?)", user_table_data)
    return user["id"], user["activeWorkspace"] or user["defaultWorkspace"]


def synch_workspaces(api_session: ClockifyClient, db: sqlite3.Connection) -> None:
    workspaces = api_session.get_workspaces()
    workspaces_data = [(ws["id"], ws["name"]) for ws in workspaces]
    db.executemany("INSERT INTO workspace VALUES(?,?)", workspaces_data)


def synch_time_entries(
    api_session: ClockifyClient,
    db: sqlite3.Connection,
    user_id: str,
    workspace_id: str,
) -> None:
    clockify_date_format = "%Y-%m-%dT%H:%M:%SZ"

    def get_clockify_diff_seconds(
        date_start_string: str, date_end_string: str
    ) -> float:
        date_start = datetime.strptime(date_start_string, clockify_date_format)
        date_end = datetime.strptime(date_end_string, clockify_date_format)
        return (date_end - date_start).total_seconds()

    time_entries = api_session.get_time_entries(workspace_id, user_id)
    time_entries_data = [
        (
            te["id"],
            datetime.strptime(te["timeInterval"]["start"], clockify_date_format),
            datetime.strptime(te["timeInterval"]["end"], clockify_date_format),
            # te["timeInterval"]["duration"],
            get_clockify_diff_seconds(
                te["timeInterval"]["start"], te["timeInterval"]["end"]
            ),
            te["description"],
            user_id,
            workspace_id,
        )
        for te in time_entries
    ]
    db.executemany("INSERT INTO time_entry VALUES(?,?,?,?,?,?,?)", time_entries_data)


def synch(store: Store, clockify_session: ClockifySession) -> int:
    fd, tmp_db = tempfile.mkstemp(dir=store.directory)
    os.close(fd)
    store.create_db(tmp_db)

    try:
        with (
            store.connect(tmp_db) as db,
            spinner("Synching..."),
        ):
            client = ClockifyClient(clockify_session)

            user_id, workspace_id = synch_user(client, db)
            if workspace_id is None or user_id is None:
                print(
                    f"SYNCH FAILED: Invalid User ({user_id}) "
                    f"or Workspace ({workspace_id})"
                )
                os.remove(tmp_db)
                return 1

            synch_workspaces(client, db)
            synch_time_entries(client, db, user_id, workspace_id)
    except BaseException:
        os.remove(tmp_db)
        raise
    else:
        os.replace(tmp_db, store.db_path)
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clockify Invoice Command Line Tool")
    command_parser = parser.add_subparsers(dest="command")

    command_parser.add_parser("synch", help="Synch the local db with clockify.")

    invoice_parser = command_parser.add_parser(
        "invoice",
        help="Generate a clockify invoice",
    )

    invoice_parser.add_argument(
        "-i",
        action="store_true",
        dest="interactive_mode",
        help="Run a local server to create invoices interactively in the browser",
    )

    args = parser.parse_args(argv)

    store = Store()
    with ClockifySession1() as sess:
        if args.command == "invoice":
            if args.interactive_mode:
                return run_interactive(store, sess.api_key)
            return generate_invoice(store)
        elif args.command == "synch":
            start = time.time()
            ret = synch(store, sess)
            print(f"Synched in {time.time() - start :.2f}")
            return ret
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
