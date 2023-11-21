import argparse
import calendar as cal
import io
import logging
import os
import pickle
import shutil
import sqlite3
import tempfile
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from datetime import timezone
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

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)

logger = logging.getLogger("clockify-invoice")
app = Flask(__name__)


class APIKeyMissingError(Exception):
    pass


@app.template_filter("format_date")
def format_date(value: date, format: str = "%d/%m/%Y") -> str:
    return value.strftime(format)


@app.route("/delete_invoice/<int:invoice_id>", methods=["POST"])
def delete_invoice(invoice_id: int) -> werkzeug.wrappers.Response:
    store: Store = app.config["store"]
    store.delete_invoice(invoice_id)
    return redirect("/")


@app.route("/download", methods=["GET"])
def download() -> werkzeug.wrappers.Response:
    if "invoice" not in session:
        return redirect("/")
    invoice: Invoice = pickle.loads(session["invoice"])
    pdf_bytes = invoice.pdf()
    store: Store = app.config["store"]

    store.save_invoice(invoice)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=invoice.invoice_name,  # type: ignore
    )


@app.route("/", methods=["GET", "POST"])
def process_invoice() -> str:
    today = date.today()
    years = list(range(today.year, today.year - 5, -1))
    store: Store = app.config["store"]
    form_data: dict[str, Any] = {
        "months": list(cal.month_name[1:]),
        "years": years,
        "display-form": "block",
        "invoice-number": store.get_next_invoice_number(),
        "month": today.month,
        "year": today.year,
    }

    if request.method == "POST":
        form_data.update(request.form)

    start_year, start_month = int(form_data["year"]), int(form_data["month"])
    end_month = 1 if start_month == 12 else start_month + 1
    end_year = start_year + 1 if start_month == 12 else start_year

    period_start, period_end = date(start_year, start_month, 1), date(
        end_year, end_month, 1
    )

    invoice_number = int(form_data["invoice-number"])

    if "invoice" in session:
        invoice: Invoice = pickle.loads(session["invoice"])
        invoice.invoice_number = invoice_number
        invoice.period_start = period_start
        invoice.period_end = period_end
    else:
        invoice_company = "Jordan Amos"
        invoice_client = "6 Cloud Systems"
        invoice = Invoice(
            invoice_number,
            invoice_company,
            invoice_client,
            period_start,
            period_end,
        )

    invoice.time_entries = store.get_time_entries(
        invoice.period_start, invoice.period_end
    )

    session["invoice"] = pickle.dumps(invoice)

    invoices = store.get_invoices()
    invoices_total = sum(invoice["total"] for invoice in invoices)

    return invoice.html(
        form_data=form_data, invoices=invoices, invoices_total=invoices_total
    )


@app.route("/synch", methods=["GET", "POST"])
def synch() -> werkzeug.wrappers.Response:
    store = app.config["store"]
    synch_with_clockify(store)
    return redirect("/")


def get_api_key() -> str:
    api_key = os.getenv("CLOCKIFY_API_KEY")
    if api_key is None:
        raise APIKeyMissingError(
            "'CLOCKIFY_API_KEY' environment variable not set.\n"
            "Connection to Clockify's API requires an API Key which can"
            "be found in your user settings."
        )
    return api_key


def run_interactive(store: Store, host: str, port: int) -> int:
    app.config["store"] = store
    app.secret_key = get_api_key()
    app.run(host=host, port=port, debug=True)
    return 0


def generate_invoice(
    store: Store, year: int, month: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
) -> int:
    workspace_id = store.get_workspace_id()
    user_id = store.get_user_id()
    if not (workspace_id and user_id):
        logger.error(
            f"Unable to generate invoice: Invalid User ({user_id}) or "
            f"Workspace ({workspace_id})"
        )
        return 1

    invoice_number = store.get_next_invoice_number()
    invoice_company = "Jordan Amos"
    invoice_client = "6 Cloud Systems"

    period_start, period_end = date(year, month, 1), date(year, month + 1, 1)

    invoice = Invoice(
        invoice_number,
        invoice_company,
        invoice_client,
        period_start,
        period_end,
    )

    invoice.time_entries = store.get_time_entries(period_start, period_end)

    print(invoice)

    return 0


def synch_user(api_session: ClockifyClient, db: sqlite3.Connection) -> tuple[str, str]:
    """
    Fetches the User from the clockify API and inserts the User into the db.
    Returns the user id and workspace id
    """
    user = api_session.get_user()
    user_id = user["id"]
    active_workspace = user["activeWorkspace"]
    default_workspace = user["defaultWorkspace"]
    workspace = active_workspace or default_workspace
    user_table_data = (
        user_id,
        user["name"],
        user["email"],
        default_workspace,
        active_workspace,
        user["settings"]["timeZone"],
    )

    if not user_id:
        raise ValueError(f"SYNCH FAILED: Invalid User {user_id}")
    if not workspace:
        raise ValueError("SYNCH FAILED: Unable to fetch Workspace")

    db.execute("INSERT INTO user VALUES(?,?,?,?,?,?)", user_table_data)
    return user_id, workspace


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

    def _convert_datestr(datestr: str) -> datetime:
        return (
            datetime.strptime(datestr, clockify_date_format)
            .replace(tzinfo=timezone.utc)
            .astimezone(tz=None)
        )

    for te in time_entries:
        entry_id = te["id"]
        start_time = _convert_datestr(te["timeInterval"]["start"])
        start_time_formatted = datetime.strftime(start_time, "%Y-%m-%d %H:%M:%S")
        end_time = _convert_datestr(te["timeInterval"]["end"])
        end_time_formatted = datetime.strftime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_secs = (end_time - start_time).total_seconds()
        desc = te["description"]
        data.append(
            (
                entry_id,
                start_time_formatted,
                end_time_formatted,
                duration_secs,
                desc,
                user_id,
                workspace_id,
            )
        )
    db.executemany("INSERT INTO time_entry VALUES(?,?,?,?,?,?,?)", data)


def synch_with_clockify(store: Store) -> int:
    # Create a back up of the db
    fd, backup_db = tempfile.mkstemp(dir=store.directory)
    os.close(fd)
    shutil.copy(store.db_path, backup_db)
    try:
        store.clear_clockify_tables()
        with (
            ClockifySession(get_api_key()) as session,
            store.connect() as db,
        ):
            logger.info("Synching the local db with clockify...")
            client = ClockifyClient(session)
            user_id, workspace_id = synch_user(client, db)
            synch_workspaces(client, db)
            synch_time_entries(client, db, user_id, workspace_id)
    except (KeyboardInterrupt, Exception):
        # Something bad happened restore the db backup
        os.replace(backup_db, store.db_path)
        raise
    else:
        os.remove(backup_db)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    today = date.today()

    parser = argparse.ArgumentParser(description="Clockify Invoice Command Line Tool")
    parser.add_argument(
        "--synch",
        help="synch the local db with clockify",
        action="store_true",
    )
    parser.add_argument(
        "-i",
        action="store_true",
        dest="interactive_mode",
        help="run a local server to create invoices interactively in the browser",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help=("(%(default)s) set the host to use when running in interactive mode."),
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=5000,
        help=("(%(default)s) set the port to use when running in interactive mode."),
    )
    parser.add_argument(
        "--year",
        type=int,
        default=today.year,
        metavar="INT",
        help="(%(default)s) set the invoice period year.",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=today.month,
        metavar="INT",
        choices=range(1, 13),
        help=" (%(default)s) set the invoice period month (%(choices)s)",
    )

    args = parser.parse_args(argv)
    store = Store()
    ret = 0
    # First synch the db if the flag is set
    if args.synch:
        ret = synch_with_clockify(store)
    if args.interactive_mode:
        ret |= run_interactive(store, args.host, args.port)
    else:
        ret |= generate_invoice(store, args.year, args.month)
    return ret


if __name__ == "__main__":
    raise SystemExit(main())
