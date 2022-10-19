from datetime import date, timedelta
import pandas as pd
import requests
import json


class Invoice:
    def __init__(
        self, company_name: str, client_name: str, start_date: date, end_date: date
    ):
        self.invoice_number = 1
        self.invoice_date = date.today()
        self.company = Company(company_name)
        self.client = Client(client_name)
        self.start_date = start_date
        self.end_date = end_date

    def get_time_entries(self):
        api_key = "NmViMDNlMjQtODY3OS00ODc0LTkzOTMtMDhmODAxZjcwOWJh"
        
        clockify_datetime_format = "%Y-%m-%dT%H:%M:%SZ"
        response_raw = requests.get(
            url + "/user",
            headers={"X-Api-key": api_key, "content-type": "application/json"},
        )

        user_id = response_raw.json()["id"]
        workspace_id = response_raw.json()["defaultWorkspace"]

        params = {
            "start": self.start_date.strftime(clockify_datetime_format),
            "end": self.end_date.strftime(clockify_datetime_format),
        }
        response_raw = requests.get(
            url + f"/workspaces/{workspace_id}/user/{user_id}/time-entries",
            headers={"X-Api-key": api_key, "content-type": "application/json"},
            params=params,
        )

        d = response_raw.json()

        df = pd.json_normalize(d)
        df = df[df.billable]
        df = df.drop(
            columns=[
                "id",
                "tagIds",
                "userId",
                "isLocked",
                "customFieldValues",
                "kioskId",
                "workspaceId",
                "type",
                "billable",
                "taskId",
                "projectId",
                "timeInterval.start",
            ],
            axis=1,
        )

        # df["timeInterval.start"] = pd.to_datetime(
        #     df["timeInterval.start"], format=clockify_datetime_format
        # )
        df["timeInterval.end"] = pd.to_datetime(
            df["timeInterval.end"], format=clockify_datetime_format
        )
        df["timeInterval.duration"] = pd.to_timedelta(df["timeInterval.duration"])
        df.rename(
            columns={
                "timeInterval.duration": "time_taken",
                # "timeInterval.start": "start",
                "timeInterval.end": "date_completed",
            },
            inplace=True,
        )

        df = df.groupby("description").agg({"date_completed": "max", "time_taken": "sum"})
        df["time_taken"] = df["time_taken"].dt.round("15min")
        df.loc[df["time_taken"] == pd.Timedelta(0), "time_taken"] = pd.Timedelta(15, "m")
        df["time_fraction"] = df["time_taken"] / pd.Timedelta(1, "h")
        df["rate"] = self.company.rate
        df["amount"] = df["time_fraction"] * df["rate"]
 
        return df


class Company:
    def __init__(self, company_name: str):
        self.company_name = company_name
        self.email = "jordan.amos@gmail.com"
        self.abn = "47 436 539 044"
        self.rate = 70.00


class Client:
    def __init__(self, client_name: str):
        self.client_name = client_name
        self.client_contact = "John Scott"
        self.email = "john.scott@6cloudsystems.com"
