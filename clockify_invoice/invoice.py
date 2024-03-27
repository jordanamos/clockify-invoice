from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Any
from typing import NamedTuple

import tabulate
from flask import render_template
from weasyprint import HTML

class Invoice:
    """
    A Class representation of an Invoice with clockify line items
    """

    def __init__(
        self,
        invoice_number: int,
        company: Company,
        client: Client,
        period_start: date,
        period_end: date,
        invoice_date: date = date.today(),
    ) -> None:
        self.invoice_date = invoice_date
        self.invoice_number = invoice_number
        self.company = company
        self.client = client
        self.period_start = period_start
        self.period_end = period_end
        self._time_entries: list[TimeEntry] = []

    @property
    def time_entries(self) -> list[TimeEntry]:
        return self._time_entries

    @time_entries.setter
    def time_entries(self, val: list[TimeEntry]) -> None:
        self._time_entries = val

    @property
    def invoice_name(self) -> str:
        return (
            f"{self.period_start.strftime('%Y_%m')}_Invoice_{self.invoice_number}.pdf"
        )

    @property
    def total(self) -> float:
        return sum(entry.billable_amount for entry in self.time_entries)

    def html(self, **kwargs: Any) -> str:
        """Render the invoice html"""
        return render_template("invoice.html", invoice=self.to_dict(), **kwargs)

    def pdf(self) -> bytes:
        html = HTML(
            string=self.html(
                form_data={"display-form": "none"},
                invoices_total=0,
            )
        )
        ret = html.write_pdf(target=None)
        if not ret:
            raise ValueError("Error generating invoice pdf")
        return ret

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "company": self.company._asdict(),
            "client": self.client._asdict(),
            "period_start": self.period_start,
            "period_end": self.period_end,
            "time_entries": [entry._asdict() for entry in self.time_entries],
            "total": self.total,
        }

    def pprint(self) -> None:
        table_data = [
            (
                datetime.strftime(entry.date, "%d/%m/%Y"),
                entry.description,
                entry.duration_hours,
                entry.rate,
                entry.billable_amount,
            )
            for entry in self.time_entries
        ]
        headers = ["Date", "Description", "Time Spent", "Rate", "Amount"]
        table_str = tabulate.tabulate(table_data, headers=headers)
        print(
            f"Invoice #: {self.invoice_number}\n"
            f"Invoice Date: {self.invoice_date}\n"
            f"Payee: {self.company.name}\n"
            f"Payer: {self.client.name}\n"
            f"Invoice Period: {self.period_start} to {self.period_end}\n\n"
            f"{table_str}\n\n"
            f"Total: {self.total}\n"
        )

class TimeEntry(NamedTuple):
    date: datetime
    description: str
    duration_hours: float
    rate: float

    @property
    def billable_amount(self) -> float:
        return self.duration_hours * self.rate
    
class Company(NamedTuple):
    name: str
    email: str
    abn: str
    rate: float


class Client(NamedTuple):
    name: str
    email: str
    contact: str
