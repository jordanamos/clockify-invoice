import os
from datetime import date, datetime
from flask import Flask, render_template
from weasyprint import HTML

from invoice import Invoice
from clockify.client import APISession
from clockify.api import APIServer


app = Flask(__name__)


@app.template_filter("format_date")
def format_date(date: datetime, format="%d/%m/%Y"):
    return date.strftime(format)


@app.route("/")
def hello_world():
    api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"

    session = APISession(APIServer(api_key))
    company = "Jordan Amos"
    client = "6 Cloud Systems"
    start_date = date(2022, 10, 1)
    end_date = date(2022, 10, 30)
    invoice = Invoice(session, company, client, start_date, end_date)

    # print(invoice.__dict__)    
    rendered = render_template(
        "invoice.html",
        invoice=invoice.__dict__,
    )

    outfile_directory = "./invoices/"
    invoice_name = "invoice.pdf"
    # html = HTML(string=rendered)
    # html.write_pdf(outfile_directory + invoice_name)
    # print(html)
    return rendered


if __name__ == "__main__":
    
    # hello_world()
    # html = HTML("templates/invoice.html")
    # html.write_pdf(outfile_directory + invoice_name)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
