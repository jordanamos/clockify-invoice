import json
from datetime import date
from typing import Any

from typing import NamedTuple
from datetime import datetime
from clockify.store import Store


class TimeEntry(NamedTuple):
    date: datetime
    description: str
    duration_hours: float
    rate: float
    
    @property
    def billable_amount(self) -> float:
        return self.duration_hours * self.rate
    
class Invoice:
    """
    A Class representation of an Invoice with clockify line items

    """

    # TODO handle timezones
    date_display_format = "%d/%m/%Y"

    def __init__(
        self,
        store: Store,
        invoice_number: str,
        company_name: str,
        client_name: str,
        start_date: date,
        end_date: date,
        invoice_date: date = date.today(),
    ):
        self.store = store
        self.invoice_date = invoice_date
        self.invoice_number = invoice_number
        self.company = Company(company_name)
        self.client = Client(client_name)
        self.start_date = start_date
        self.end_date = end_date

    def convert_data(self, o: Any) -> Any:
        if isinstance(o, date):
            return o.strftime("%d/%m/%Y")
        elif isinstance(o, (Client, Company)):
            return o.__dict__
        elif isinstance(o, Store):
            return str(o)
        else:
            json.JSONEncoder.default(json.JSONEncoder(), o)

    def to_json(self) -> str:
        return json.dumps(
            self.__dict__, default=self.convert_data, sort_keys=True, indent=4
        )

    # def __dict__(self):
    #     return {
    #         "invoice_number": self.invoice_number
    #     }


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
