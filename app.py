import os
from weasyprint import HTML
from flask import Flask, render_template
from invoice import Invoice
from clockify import ClockifyAPI
from datetime import date

app = Flask(__name__)


@app.route("/")
def hello_world():
    company = "Jordan Amos"
    client = "6 Cloud Systems"
    start_date = date(2022, 9, 1)
    end_date = date(2022, 9, 30)

    invoice = Invoice(company, client, start_date, end_date)

    return render_template("invoice.html", **invoice.__dict__)


if __name__ == "__main__":

    outfile_directory = "./invoices/"
    invoice_name = "invoice.pdf"
    clockify_api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"
    url = "https://api.clockify.me/api/v1"
    path = "/workspaces"
    client = ClockifyAPI(url, clockify_api_key)
    print(client.get(path, clockify_api_key, ""))

    # print(invoice.__dict__)
    # html = HTML("templates/invoice.html")
    # html.write_pdf(outfile_directory + invoice_name)
    # port = int(os.environ.get("PORT", 5000))
    # app.run(host="0.0.0.0", port=port)
