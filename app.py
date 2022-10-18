import json
import os

from weasyprint import HTML
from flask import Flask, render_template
from invoice import Invoice
from clockify import ClockifyAPI
from datetime import datetime
import requests
import pandas as pd

app = Flask(__name__)


@app.route("/")
def hello_world():
    company = "Jordan Amos"
    client = "6 Cloud Systems"
    start_date = datetime(2022, 9, 1)
    end_date = datetime(2022, 9, 30)

    invoice = Invoice(company, client, start_date, end_date)

    return render_template("invoice.html", **invoice.__dict__)


if __name__ == "__main__":

    outfile_directory = "./invoices/"
    invoice_name = "invoice.pdf"
    api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"
    url = "https://api.clockify.me/api/v1"
    client = ClockifyAPI(url, api_key)
    clockify_datetime_format = "%Y-%m-%dT%H:%M:%SZ"
    start_date = datetime(2022, 10, 7)
    end_date = datetime(2022, 10, 17, 23, 59, 59, 100)

    response_raw = requests.get(
        url + "/user",
        headers={"X-Api-key": api_key, "content-type": "application/json"},
    )

    user_id = response_raw.json()["id"]
    workspace_id = response_raw.json()["defaultWorkspace"]

    params = {
        "start": start_date.strftime(clockify_datetime_format),
        "end": end_date.strftime(clockify_datetime_format),
    }
    response_raw = requests.get(
        url + f"/workspaces/{workspace_id}/user/{user_id}/time-entries",
        headers={"X-Api-key": api_key, "content-type": "application/json"},
        params=params,
    )

    d = response_raw.json()

    df = pd.json_normalize(d)
    # times = d["timeInterval"]
    df = df.drop(
        columns=[
            "id",
            "tagIds",
            "userId",
            "isLocked",
            "customFieldValues",
            "kioskId",
            "workspaceId",
            "billable",
            "taskId",
            "projectId",
        ],
        axis=1,
    )
    df["timeInterval.start"] = pd.to_datetime(
        df["timeInterval.start"], format=clockify_datetime_format
    )
    df["timeInterval.end"] = pd.to_datetime(
        df["timeInterval.end"], format=clockify_datetime_format
    )
    df["timeInterval.duration"] = pd.to_timedelta(df["timeInterval.duration"])
    # print(df)
    # print(invoice.__dict__)
    html = HTML("templates/invoice.html")
    html.write_pdf(outfile_directory + invoice_name)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
