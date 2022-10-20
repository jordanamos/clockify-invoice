from datetime import datetime
import pandas as pd
from clockify.client import APISession


class Invoice:
    """
    A Class representation of an Invoice with clockify line items

    """

    # TODO handle timezones
    invoice_date = datetime.today()

    def __init__(
        self,
        APISession: APISession,
        company_name: str,
        client_name: str,
        start_date: datetime,
        end_date: datetime,
    ):
        self.invoice_number = 1
        self.session = APISession
        self.company = Company(company_name)
        self.client = Client(client_name)
        self.start_date = start_date
        self.end_date = end_date

    def get_line_items(self) -> pd.DataFrame:

        time_entries = self.session.get_time_entries()
        return self.get_line_items_for_period(time_entries)

    def get_line_items_for_period(self, time_entries) -> pd.DataFrame:

        df = pd.json_normalize(time_entries)
        df[df.billable]
        df[["description", "timeInterval.end", "timeInterval.duration"]]
        df.rename(
            columns={
                "timeInterval.duration": "time_spent",
                "timeInterval.end": "item_date",
            },
            inplace=True,
        )

        df["item_date"] = pd.to_datetime(
            df["item_date"], format=self.session.clockify_datetime_format
        ).dt.date

        df["time_spent"] = pd.to_timedelta(df["time_spent"])

        df = df.groupby("description").agg({"item_date": "max", "time_spent": "sum"})
        # df = df.reset_index().set_index("item_date", drop=False)
        df = df.loc[
            (df["item_date"] >= self.start_date) & (df["item_date"] <= self.end_date)
        ]

        df["time_spent"] = df["time_spent"].dt.round("15min")

        df.loc[df["time_spent"] == pd.Timedelta(0), "time_spent"] = pd.Timedelta(
            15, "m"
        )
        df["time_spent_frac"] = df["time_spent"] / pd.Timedelta(1, "h")
        df["rate"] = self.company.rate
        df["amount"] = df["time_spent_frac"] * df["rate"]
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
