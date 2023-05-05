import argparse
import calendar as cal
import contextlib
import io
import json
import os
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

from clockify import api
from clockify import client
from clockify.api import APIKeyMissingError
from clockify.invoice import Invoice
from clockify.store import Store

app = Flask(__name__)


@app.template_filter("format_date")
def format_date(
    value: Any, informat: str = "%d/%m/%Y", outformat: str = "%d/%m/%Y"
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
    if "invoice" in session:
        # invoice = json.loads(session.__dict__)
        invoice = json.loads(session.get("invoice", ""))
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
    if form_data["invoice-period"] == "two-months-ago":
        period_date = period_date - timedelta(weeks=8)
    if form_data["invoice-period"] == "three-months-ago":
        period_date = period_date - timedelta(weeks=12)

    period_start = period_date.replace(day=1)
    period_end = period_date.replace(
        day=cal.monthrange(period_date.year, period_date.month)[1]
    )

    with clockify_session() as sess:
        invoice = Invoice(
            client.APISession(api.APIServer(sess)),
            invoice_number,
            invoice_company,
            invoice_client,
            period_start,
            period_end,
        )

    session["invoice"] = invoice.to_json()
    rendered_invoice = render_template(
        "invoice.html", invoice=invoice.__dict__, form_data=form_data
    )

    return rendered_invoice


def run_interactive() -> int:
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
    return 0


def synch(store: Store, sess: Session, time_entries_only: bool) -> int:
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clockify Invoice Command Line Tool")
    command_parser = parser.add_subparsers(dest="command")

    synch_parser = command_parser.add_parser(
        "synch",
        help="Synchs the local db with clockify.",
    )
    synch_parser.add_argument(
        "--entries-only",
        action="store_true",
        help="Set this flag to only synch the time entries",
    )

    invoice_parser = command_parser.add_parser(
        "invoice", help="Generate a clockify invoice"
    )

    invoice_parser.add_argument(
        "-i",
        action="store_true",
        dest="interactive_mode",
        help="Runs a local server to create invoices interactively in the browser",
    )

    args = parser.parse_args(argv)

    store = Store()

    if args.command == "invoice":
        if args.interactive_mode:
            return run_interactive()
        return generate_invoice(store)
    elif args.command == "synch":
        with clockify_session() as sess:
            return synch(store, sess, args.entries_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
