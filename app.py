import json
import os
from weasyprint import HTML
from flask import Flask, render_template
from invoice import Invoice
from clockify import ClockifyAPI
from datetime import date
import requests
import pandas as pd

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
    api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"
    url = "https://api.clockify.me/api/v1"
    client = ClockifyAPI(url, api_key)

    response_raw = requests.get(
        url + "/user",
        headers={"X-Api-key": api_key, "content-type": "application/json"},
    )

    user_id = response_raw.json()["id"]
    workspace_id = response_raw.json()["defaultWorkspace"]

    response_raw = requests.get(
        url + f"/workspaces/{workspace_id}/user/{user_id}/time-entries",
        headers={"X-Api-key": api_key, "content-type": "application/json"},
    )
    d = response_raw.json()
    df = pd.DataFrame(columns=d[0].keys())
    for i in range(len(d)):
        df.loc[i] = d[i].values()

    df = df.drop(
        columns=[
            "id",
            "tagIds",
            "userId",
            "isLocked",
            "customFieldValues",
            "kioskId",
            "type",
            "workspaceId",
            "billable",
        ],
        axis=1,
    )

    print(df)
    # print(invoice.__dict__)
    # html = HTML("templates/invoice.html")
    # html.write_pdf(outfile_directory + invoice_name)
    # port = int(os.environ.get("PORT", 5000))
    # app.run(host="0.0.0.0", port=port)
