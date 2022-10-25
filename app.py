import os
import io
import calendar as cal
from datetime import date, timedelta, datetime
from weasyprint import HTML
from flask import Flask, request, render_template, send_file, session,redirect
from invoice import Invoice
import json
from clockify import client
from clockify import api


app = Flask(__name__)
app.secret_key = "jordan"
api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"
clockify_session = client.APISession(api.APIServer(api_key))


@app.template_filter("format_date")
def format_date(value, informat="%d/%m/%Y", outformat="%d/%m/%Y") -> str:
    if not isinstance(value, date):
        try:
            return datetime.strptime(value, informat).strftime(outformat)
        except ValueError:
            return f"Error parsing date [{value}]"
    else:
        return value.strftime(outformat)



@app.route("/download", methods=["GET"])
def download():
    if "invoice" in session:
        # invoice = json.loads(session.__dict__)
        invoice = json.loads(session.get("invoice"))
        invoice_name = "invoice.pdf"
        form_data = {
            "display-form": "none",
        }
        rendered_invoice = render_template(
            "invoice.html", invoice=invoice
            , form_data=form_data
        )
        html = HTML(string=rendered_invoice)
        rendered_pdf = html.write_pdf()

        return send_file(
            io.BytesIO(rendered_pdf),
            mimetype="application/pdf",
            download_name=invoice_name,
            as_attachment=True,
        )
    else:
        redirect("/") 

@app.route("/", methods=["GET", "POST"])
def process_invoice():

    invoice_company = "Jordan Amos"
    invoice_client = "6 Cloud Systems"

    form_data = {
        "invoice-number": "1",
        "invoice-period": "this-month",
        "display-form": "block",
    }

    if request.method == "POST":
        form_data.update(request.form)

    today = date.today()
    period_date = date(today.year, today.month, 1)

    if form_data["invoice-period"] == "last-month":
        period_date = period_date - timedelta(weeks=4)

    period_start = period_date.replace(day=1)
    period_end = period_date.replace(
        day=cal.monthrange(period_date.year, period_date.month)[1]
    )

    invoice = Invoice(
        clockify_session, invoice_company, invoice_client, period_start, period_end
    )

    session["invoice"] = invoice.to_json()
    rendered_invoice = render_template(
        "invoice.html", invoice=invoice.__dict__, form_data=form_data
    )  

    return rendered_invoice


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
