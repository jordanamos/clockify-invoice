import argparse
import calendar as cal
import contextlib
import io
import itertools
import os
import sqlite3
import sys
import tempfile
import threading
import time
from collections.abc import Generator
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

import werkzeug.wrappers
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import session
from flask import wrappers
from requests import Session
from weasyprint import HTML

from clockify.api import APIKeyMissingError
from clockify.api import APIServer
from clockify.client import APISession
from clockify.invoice import Invoice
from clockify.store import Store

app = Flask(__name__)


@app.template_filter("format_date")
def format_date(
    value: Any, informat: str = "%Y-%m-%d", outformat: str = "%d/%m/%Y"
) -> str:
    if not isinstance(value, date):
        try:
            return datetime.strptime(value, informat).strftime(outformat)
        except ValueError:
            return f"Error parsing date [{value}]"
    else:
        return value.strftime(outformat)


@app.route("/download", methods=["GET"])
def download() -> wrappers.Response | werkzeug.wrappers.Response:
    if "invoice" not in session:
        return redirect("/")

    invoice: Invoice = session["invoice"]
    invoice_name = "invoice.pdf"
    form_data = {
        "display-form": "none",
    }
    rendered_invoice = render_template(
        "invoice.html", invoice=invoice, form_data=form_data
    )
    html = HTML(string=rendered_invoice)
    rendered_pdf = html.write_pdf()

    if rendered_pdf:
        return send_file(
            io.BytesIO(rendered_pdf),
            mimetype="application/pdf",
            download_name=invoice_name,  # type: ignore
            as_attachment=True,
        )
    return redirect("/")


@app.route("/", methods=["GET", "POST"])
def process_invoice() -> str:
    invoice_company = "Jordan Amos"
    invoice_client = "6 Cloud Systems"

    form_data = {
        "invoice-number": "1",
        "invoice-period": "this-month",
        "display-form": "block",
    }

    if request.method == "POST":
        form_data.update(request.form)

    invoice_number = form_data["invoice-number"]
    today = date.today()
    period_date = date(today.year, today.month, 1)

    if form_data["invoice-period"] == "last-month":
        period_date = period_date - timedelta(weeks=4)
    elif form_data["invoice-period"] == "two-months-ago":
        period_date = period_date - timedelta(weeks=8)
    elif form_data["invoice-period"] == "three-months-ago":
        period_date = period_date - timedelta(weeks=12)

    period_start = period_date.replace(day=1)
    period_end = period_date.replace(
        day=cal.monthrange(period_date.year, period_date.month)[1]
    )

    store = app.config["store"]
    invoice = Invoice(
        store,
        invoice_number,
        invoice_company,
        invoice_client,
        period_start,
        period_end,
    )

    session["invoice"] = invoice.to_json()
    rendered_invoice = render_template(
        "invoice.html", invoice=invoice.to_dict(), form_data=form_data
    )

    return rendered_invoice


def run_interactive() -> int:
    app.secret_key = "jo"
    app.run(host="0.0.0.0", port=5000, debug=True)
    return 0


@contextlib.contextmanager
def clockify_session() -> Generator[Session, None, None]:
    api_key = os.getenv("CLOCKIFY_API_KEY")

    if api_key is None:
        raise APIKeyMissingError(
            """
            'CLOCKIFY_API_KEY' environment variable not set.
            Connection to Clockify's API requires an  API Key which can
            be found in your user settings.
            """
        )
    app.secret_key = api_key

    with contextlib.closing(Session()) as sess:
        sess.headers = {
            "X-Api-key": api_key,
            "content-type": "application/json",
        }
        yield sess


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
    period_date = date(today.year, today.month, 1) - timedelta(weeks=4)
    period_start = period_date.replace(day=1)
    period_end = period_date.replace(
        day=cal.monthrange(period_date.year, period_date.month)[1]
    )

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


def synch_user(api_session: APISession, db: sqlite3.Connection) -> tuple[str, str]:
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


def synch_workspaces(api_session: APISession, db: sqlite3.Connection) -> None:
    workspaces = api_session.get_workspaces()
    workspaces_data = [(ws["id"], ws["name"]) for ws in workspaces]
    db.executemany("INSERT INTO workspace VALUES(?,?)", workspaces_data)


def synch_time_entries(
    api_session: APISession,
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
    db.executemany("INSERT INTO time_entry VALUES(?,?,?,?,?,?,?,?)", time_entries_data)


def synch(store: Store) -> int:
    fd, tmp_db = tempfile.mkstemp(dir=store.directory)
    os.close(fd)
    store.create_db(tmp_db)

    try:
        with (
            clockify_session() as session,
            store.connect(tmp_db) as db,
            spinner("Synching..."),
        ):
            api_session = APISession(APIServer(session))
            user_id, workspace_id = synch_user(api_session, db)
            if workspace_id is None or user_id is None:
                print(
                    f"SYNCH FAILED: Invalid User ({user_id}) "
                    f"or Workspace ({workspace_id})"
                )
                os.remove(tmp_db)
                return 1
            synch_workspaces(api_session, db)
            synch_time_entries(api_session, db, user_id, workspace_id)
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

    if args.command == "invoice":
        if args.interactive_mode:
            app.config["store"] = store
            return run_interactive()
        return generate_invoice(store)
    elif args.command == "synch":
        return synch(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
