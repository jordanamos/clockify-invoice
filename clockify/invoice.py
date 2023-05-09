from datetime import date
from datetime import datetime
from typing import Any
from typing import NamedTuple

import tabulate
from flask import render_template
from weasyprint import HTML

from clockify.store import Store

TIME_ENTRIES_QUERY = """\
SELECT MAX(end_time) AS date
    , description
    , SUM(duration_seconds)
FROM time_entry
WHERE user = ?
    AND workspace = ?
    AND start_time >= ?
    AND end_time < ?
    AND duration_seconds > 0
GROUP BY description
"""


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

    def __init__(
        self,
        store: Store,
        invoice_number: str,
        company_name: str,
        client_name: str,
        period_start: date,
        period_end: date,
        invoice_date: date = date.today(),
    ) -> None:
        self.store = store
        self.invoice_date = invoice_date
        self.invoice_number = invoice_number
        self.company = Company(company_name)
        self.client = Client(client_name)
        self.period_start = period_start
        self.period_end = period_end

        self.update_time_entries()

    @property
    def time_entries(self) -> list[TimeEntry]:
        return self._time_entries

    @property
    def invoice_name(self) -> str:
        return (
            f"{self.invoice_date.strftime('%Y_%m')}_Invoice_{self.invoice_number}.pdf"
        )

    def update_time_entries(self) -> None:
        with self.store.connect() as db:
            rows = db.execute(
                TIME_ENTRIES_QUERY,
                (
                    self.store.get_user_id(),
                    self.store.get_workspace_id(),
                    self.period_start,
                    self.period_end,
                ),
            ).fetchall()

        entries: list[TimeEntry] = []

        for row in rows:
            date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            description = str(row[1])
            duration_seconds = int(row[2])
            duration_hours = (round((duration_seconds / 3600) * 4) / 4) or 0.25
            time_entry = TimeEntry(date, description, duration_hours, 70.0)
            entries.append(time_entry)
        self._time_entries = entries

    @property
    def total(self) -> float:
        return sum(entry.billable_amount for entry in self.time_entries)

    def html(self, **kwargs: dict[str, Any]) -> str:
        """Render the invoice html"""
        return render_template("invoice.html", invoice=self.to_dict(), **kwargs)

    def pdf(self, **kwargs: dict[str, Any]) -> bytes:
        html = HTML(string=self.html(**kwargs))
        ret = html.write_pdf(target=None)
        if not ret:
            raise ValueError("Error generating invoice pdf")
        return ret

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "company": self.company.__dict__,
            "client": self.client.__dict__,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "time_entries": [entry._asdict() for entry in self.time_entries],
            "total": self.total,
        }

    def __str__(self) -> str:
        table_data = [
            (entry.date, entry.description, entry.duration_hours, entry.billable_amount)
            for entry in self.time_entries
        ]
        headers = ["Date", "Description", "Duration", "Billable Amount"]
        table_str = tabulate.tabulate(table_data, headers=headers)
        return (
            f"Invoice {self.invoice_number} ({self.invoice_date}):"
            f"\n\n{table_str}\n\n"
            f"Total: {self.total}"
        )


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
