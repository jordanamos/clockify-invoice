from operator import index
import os

# from weasyprint import HTML
from flask import Flask, render_template
from invoice import Invoice
from clockify.client import APISession
from clockify.api import APIServer
from datetime import datetime, date


app = Flask(__name__)


@app.route("/")
def hello_world():
    api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"

    outfile_directory = "./invoices/"
    invoice_name = "invoice.pdf"

    session = APISession(APIServer(api_key))
    company = "Jordan Amos"
    client = "6 Cloud Systems"
    start_date = date(2023, 8, 1)
    end_date = date(2023, 8, 30)
    invoice = Invoice(session, company, client, start_date, end_date)
    print(invoice.line_items.to_dict(orient="index"))

    # return render_template(
    #     "invoice.html",
    #     invoice=invoice.__dict__,
    #     invoice_time_entries=invoice.line_items.to_dict(orient="index"),
    # )


if __name__ == "__main__":

    hello_world()

# html = HTML("templates/invoice.html")
# html.write_pdf(outfile_directory + invoice_name)
# port = int(os.environ.get("PORT", 5000))
# app.run(host="0.0.0.0", port=port, debug=True)
