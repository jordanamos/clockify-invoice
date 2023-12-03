import argparse
import calendar as cal
import io
import logging
import pickle
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

from clockify_invoice.invoice import Invoice
from clockify_invoice.store import Store
from clockify_invoice.utils import auth_required
from clockify_invoice.utils import get_api_key
from clockify_invoice.utils import synch_with_clockify

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)

logger = logging.getLogger("clockify-invoice")
app = Flask(__name__)
app.config.from_prefixed_env()  # type: ignore

# Constants
TODAY = date.today()
YEARS = list(range(TODAY.year, TODAY.year - 5, -1))
MONTHS = list(cal.month_name[1:])


@app.template_filter("format_financial_year")
def format_financial_year(year: int) -> str:
    start_date = datetime(year, 6, 30)
    end_date = datetime(year + 1, 7, 1)
    return f"{start_date.strftime('%Y')}-{end_date.strftime('%y')}"


@app.template_filter("format_date")
def format_date(value: date, format: str = "%d/%m/%Y") -> str:
    return value.strftime(format)


@app.route("/delete_invoice/<int:invoice_id>", methods=["POST"])
@auth_required
def delete_invoice(invoice_id: int) -> werkzeug.wrappers.Response:
    store: Store = app.config["store"]
    store.delete_invoice(invoice_id)
    session["active-tab"] = "table-tab"
    return redirect("/")


@app.route("/save", methods=["GET"])
@auth_required
def save() -> werkzeug.wrappers.Response:
    if "invoice" not in session:
        return redirect("/")
    invoice: Invoice = pickle.loads(session["invoice"])
    store: Store = app.config["store"]
    store.save_invoice(invoice)
    return redirect("/")


@app.route("/download", methods=["GET"])
@auth_required
def download() -> werkzeug.wrappers.Response:
    if "invoice" not in session:
        return redirect("/")
    invoice: Invoice = pickle.loads(session["invoice"])
    pdf_bytes = invoice.pdf()
    return send_file(
        io.BytesIO(pdf_bytes),
        "application/pdf",
        True,
        invoice.invoice_name,
    )


@app.route("/", methods=["GET", "POST"])
@auth_required
def process_invoice() -> str:
    store: Store = app.config["store"]

    form_data: dict[str, Any] = {
        "months": MONTHS,
        "years": YEARS,
        "month": TODAY.month,
        "year": TODAY.year,
        "financial-year": TODAY.year,
        "display-form": "block",
        "invoice-number": store.get_next_invoice_number(),
        "active-tab": session.get("active-tab") or "form-tab",
    }

    if request.method == "POST":
        form_data.update(request.form)

    start_year, start_month = int(form_data["year"]), int(form_data["month"])
    end_month = 1 if start_month == 12 else start_month + 1
    end_year = start_year + 1 if start_month == 12 else start_year

    period_start = date(start_year, start_month, 1)
    period_end = date(end_year, end_month, 1)
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
    invoices = store.get_invoices(int(form_data["financial-year"]))
    invoices_total = sum(invoice["total"] for invoice in invoices)
    return invoice.html(
        form_data=form_data, invoices=invoices, invoices_total=invoices_total
    )


@app.route("/synch", methods=["GET"])
@auth_required
def synch() -> werkzeug.wrappers.Response:
    store = app.config["store"]
    synch_with_clockify(store)
    session["active-table"] = "form-tab"
    return redirect("/")


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

    print(invoice.to_string())

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    today = date.today()

    parser = argparse.ArgumentParser(description="Clockify Invoice Command Line Tool")
    parser.add_argument(
        "--verbose",
        "--debug",
        "-v",
        help="Show debug messaging",
        action="store_true",
    )
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

    if args.verbose:
        logger.setLevel(logging.DEBUG)

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
