import os
import io

from datetime import date, datetime
from flask import Flask, request, render_template, send_file
from weasyprint import HTML

from invoice import Invoice
from clockify.client import APISession
from clockify.api import APIServer


app = Flask(__name__)


@app.template_filter("format_date")
def format_date(date: datetime, format="%d/%m/%Y"):
    return date.strftime(format)


@app.route("/", methods=["POST", "GET"])
def hello_world():
    api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"

    session = APISession(APIServer(api_key))
    company = "Jordan Amos"
    client = "6 Cloud Systems"
    start_date = date(2022, 10, 1)
    end_date = date(2022, 10, 30)
    invoice = Invoice(session, company, client, start_date, end_date)

    rendered = render_template(
        "invoice.html",
        invoice=invoice.__dict__,
    )

    if request.method == "POST":
        download_invoice = request.form["download"]
        if download_invoice:
            outfile_directory = "./invoices/"
            invoice_name = "invoice.pdf"
            html = HTML(string=rendered)
            rendered_pdf = html.write_pdf()

            return send_file(
                io.BytesIO(rendered_pdf),
                mimetype="application/pdf",
                download_name=invoice_name,
                as_attachment=True,
            )

    return rendered


if __name__ == "__main__":

    # hello_world()
    # html = HTML("templates/invoice.html")
    # html.write_pdf(outfile_directory + invoice_name)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
