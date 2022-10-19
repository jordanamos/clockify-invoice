from operator import index
import os

# from weasyprint import HTML
from flask import Flask, render_template
from invoice import Invoice
from clockify import APIServer
from datetime import datetime


app = Flask(__name__)


@app.route("/")
def hello_world():
    company = "Jordan Amos"
    client = "6 Cloud Systems"
    start_date = datetime(2022, 9, 1)
    end_date = datetime(2022, 10, 1)

    # invoice = Invoice(company, client, start_date, end_date)

    # time_entries = invoice.get_time_entries()

    # return render_template(
    #     "invoice.html",
    #     invoice=invoice.__dict__,
    #     invoice_time_entries=time_entries.to_dict("index"),
    # )


if __name__ == "__main__":

    outfile_directory = "./invoices/"
    invoice_name = "invoice.pdf"

    api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"

    session = APIServer(api_key)
    print(session.user)
    # hello_world()
    # client = ClockifyAPI(url, api_key)
    # company = "Jordan Amos"
    # client = "6 Cloud Systems"
    # start_date = datetime(2022, 9, 1)
    # end_date = datetime(2022, 9, 30)

    # invoice = Invoice(company, client, start_date, end_date)
    # time_entries = invoice.get_time_entries()
    # print(time_entries.to_dict("index"))
    # print(df)

    # html = HTML("templates/invoice.html")
    # html.write_pdf(outfile_directory + invoice_name)
    # port = int(os.environ.get("PORT", 5000))
    # app.run(host="0.0.0.0", port=port)
