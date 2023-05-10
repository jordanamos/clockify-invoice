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
from typing import Literal

import werkzeug.wrappers
from flask import Flask
from flask import redirect
from flask import request
from flask import send_file
from flask import session

from clockify.api import ClockifyClient
from clockify.api import ClockifySession
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


def run_interactive(store: Store) -> int:
    app.config["store"] = store
    app.secret_key = ClockifySession.get_api_key()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    return 0


def generate_invoice(
    store: Store, year: int, month: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
) -> int:
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

    _weekdays, days_in_month = cal.monthrange(year, month)
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
    time_entries = api_session.get_time_entries(workspace_id, user_id)
    clockify_date_format = "%Y-%m-%dT%H:%M:%SZ"
    data = []

    for te in time_entries:
        entry_id = te["id"]
        start_time = datetime.strptime(
            te["timeInterval"]["start"], clockify_date_format
        )
        end_time = datetime.strptime(te["timeInterval"]["end"], clockify_date_format)
        duration_secs = (end_time - start_time).total_seconds()
        desc = te["description"]
        data.append(
            (entry_id, start_time, end_time, duration_secs, desc, user_id, workspace_id)
        )

    db.executemany("INSERT INTO time_entry VALUES(?,?,?,?,?,?,?)", data)


def synch(store: Store) -> int:
    fd, tmp_db = tempfile.mkstemp(dir=store.directory)
    os.close(fd)
    store.create_db(tmp_db)

    try:
        with (
            ClockifySession() as session,
            store.connect(tmp_db) as db,
            spinner("Synching..."),
        ):
            client = ClockifyClient(session)

            user_id, workspace_id = synch_user(client, db)
            if workspace_id is None or user_id is None:
                logger.error(
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
    today = date.today()
    parser = argparse.ArgumentParser(description="Clockify Invoice Command Line Tool")
    parser.add_argument(
        "--synch",
        help="Synch the local db with clockify",
        action="store_true",
    )
    parser.add_argument(
        "-i",
        action="store_true",
        dest="interactive_mode",
        help="Run a local server to create invoices interactively in the browser",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=today.year,
        metavar="INT",
        help="Set the invoice period year. Default is the current year (%(default)s)",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=today.month,
        metavar="INT",
        choices=range(1, 13),
        help="Set the invoice period month. Default is the current month (%(default)s)",
    )
    args = parser.parse_args(argv)

    store = Store()

    ret = 0

    if args.synch:
        ret |= synch(store)
    if args.interactive_mode:
        ret |= run_interactive(store)
    else:
        ret |= generate_invoice(store, args.year, args.month)

    return ret


if __name__ == "__main__":
    raise SystemExit(main())
