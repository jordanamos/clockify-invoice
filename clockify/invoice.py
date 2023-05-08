import json
from datetime import date
from datetime import datetime
from typing import Any
from typing import NamedTuple

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
        self._period_start = period_start
        self._period_end = period_end
        self._time_entries = self._get_time_entries()

    @property
    def period_start(self) -> date:
        return self._period_start

    @period_start.setter
    def period_start(self, value: date) -> None:
        self._period_start = value
        self._time_entries = self._get_time_entries()

    @property
    def period_end(self) -> date:
        return self._period_end

    @period_end.setter
    def period_end(self, value: date) -> None:
        self._period_end = value
        self._time_entries = self._get_time_entries()

    @property
    def time_entries(self) -> list[TimeEntry]:
        return self._time_entries

    def _get_time_entries(self) -> list[TimeEntry]:
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
            date = row[0]
            description = row[1]
            duration_seconds = int(row[2])
            duration_hours = (round((duration_seconds / 3600) * 4) / 4) or 0.25
            time_entry = TimeEntry(date, description, duration_hours, 70.0)
            entries.append(time_entry)
        return entries

    @property
    def total(self) -> float:
        return sum(entry.billable_amount for entry in self.time_entries)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_number": self.invoice_number,
            "company": {
                "name": self.company.__dict__,
            },
            "client": {
                "name": self.client.__dict__,
            },
            "period_start": str(self.period_start),
            "period_end": str(self.period_end),
            "time_entries": [entry._asdict() for entry in self.time_entries],
            "total": self.total,
        }


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
