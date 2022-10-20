import pandas as pd
from datetime import date
from clockify.client import APISession


class Invoice:
    """
    A Class representation of an Invoice with clockify line items

    """

    # TODO handle timezones
    date_format = "%d-%M-%yyyy"
    def __init__(
        self,
        APISession: APISession,
        company_name: str,
        client_name: str,
        start_date: date,
        end_date: date,
    ):
        self.invoice_date = date.today()
        self.invoice_number = 1
        self.session = APISession
        self.company = Company(company_name)
        self.client = Client(client_name)
        self.start_date = start_date
        self.end_date = end_date

    @property
    def line_items(self) -> pd.DataFrame:

        # TODO add params for end date <= self.end_date for ?improved? performance with historic requests
        time_entries = self.session.get_time_entries()
        return self.get_billable_items(time_entries)

    @property
    def total(self) -> float:
        return self.line_items["amount"].sum()

    def get_billable_items(self, time_entries) -> pd.DataFrame:

        # pd.options.display.float_format = "{:,.2f}".format

        df = pd.json_normalize(time_entries)
        # filter rows to billable only
        df[df.billable]
        df[["description", "timeInterval.end", "timeInterval.duration"]]
        df.rename(
            columns={
                "timeInterval.end": "item_date",
                "timeInterval.duration": "time_spent",
            },
            inplace=True,
        )

        # convert item date to date
        df["item_date"] = pd.to_datetime(
            df["item_date"], format=self.session.clockify_datetime_format
        ).dt.date

        # convert time spent to time delta
        df["time_spent"] = pd.to_timedelta(df["time_spent"])

        # group items together, getting the max item date (the date the item was complete)
        # and the sum of time taken (what we will use to bill)
        df = df.groupby("description").agg({"item_date": "max", "time_spent": "sum"})
        df = df.loc[
            (df["item_date"] >= self.start_date) & (df["item_date"] <= self.end_date)
        ]

        # round the time spent to the nearest 15mins. if 0, set to 15mins. (nothing is for free!)
        df["time_spent"] = df["time_spent"].dt.round("15min")
        df.loc[df["time_spent"] == pd.Timedelta(0), "time_spent"] = pd.Timedelta(
            15, "m"
        )

        # generate additional invoicing related columns
        df["time_spent_frac"] = df["time_spent"] / pd.Timedelta(1, "h")
        df["rate"] = self.company.rate
        df["amount"] = df["time_spent_frac"] * df["rate"]

        df.reset_index(inplace=True)

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
