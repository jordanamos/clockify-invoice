import calendar as cal
import io
import json
import os
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

import api
import client
import werkzeug.wrappers
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import session
from flask import wrappers
from invoice import Invoice
from weasyprint import HTML

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
        invoice = json.loads(session.get("invoice"))
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
                download_name=invoice_name,
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

    invoice = Invoice(
        clockify_session,
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


if __name__ == "__main__":
    API_KEY = os.getenv("CLOCKIFY_API_KEY")
    if API_KEY is None:
        raise api.APIKeyMissingError(
            """'CLOCKIFY_API_KEY' environment variable not set.
            Connection to Clockify's API requires an  API Key which can
            be found in your user settings."""
        )
    app.secret_key = API_KEY
    clockify_session = client.APISession(api.APIServer(API_KEY))
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
