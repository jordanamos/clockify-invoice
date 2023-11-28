import base64
import contextlib
import datetime
import logging
import os
import pickle
import sqlite3
from collections.abc import Generator
from typing import Any

from clockify.invoice import Invoice
from clockify.invoice import TimeEntry

logger = logging.getLogger("clockify-invoice")

_TIME_ENTRIES_QUERY = """\
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

_INVOCES_QUERY = """\
SELECT id, pickle
FROM invoice
"""

_DELETE_INVOICE_QUERY = """\
DELETE
FROM INVOICE
WHERE id = ?
"""


class Store:
    _DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        self.directory = self._get_default_directory()

        logger.info(f"Using store directory: {self.directory}")

        self.db_path = os.path.join(self.directory, "db.db")
        self._workspace_id = None
        self._user_id = None
        if not os.path.exists(self.directory):
            os.makedirs(self.directory, exist_ok=True)
        self.create_db()

    @staticmethod
    def _get_default_directory() -> str:
        return os.getenv("CLOCKIFY_INVOICE_HOME") or os.path.join(
            os.path.expanduser("~"),
            "clockify-invoice",
        )

    @contextlib.contextmanager
    def connect(
        self, db_path: str | None = None
    ) -> Generator[sqlite3.Connection, None, None]:
        path = db_path if db_path is not None else self.db_path
        with contextlib.closing(sqlite3.connect(path)) as db:
            with db:
                yield db

    def create_db(self, db_path: str | None = None) -> None:
        with self.connect(db_path) as db:
            db.executescript(
                """\
                CREATE TABLE IF NOT EXISTS workspace (
                    id TEXT PRIMARY KEY,
                    name TEXT
                );

                CREATE TABLE IF NOT EXISTS user (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    default_workspace TEXT,
                    active_workspace TEXT,
                    time_zone TEXT,
                    FOREIGN KEY (default_workspace) REFERENCES workspace(id),
                    FOREIGN KEY (active_workspace) REFERENCES workspace(id)
                );

                CREATE TABLE IF NOT EXISTS time_entry (
                    id TEXT PRIMARY KEY,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds INT,
                    description TEXT,
                    user TEXT,
                    workspace TEXT,
                    FOREIGN KEY (user) REFERENCES user(id),
                    FOREIGN KEY (workspace) REFERENCES workspace(id)
                );

                CREATE TABLE IF NOT EXISTS invoice (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number INT,
                    date TEXT,
                    period_start TEXT,
                    period_end TEXT,
                    payer TEXT,
                    payee TEXT,
                    total REAL,
                    paid INT,
                    pdf TEXT,
                    pickle TEXT
                );
                """
            )

    def delete_invoice(self, id: int) -> None:
        with self.connect() as db:
            db.execute(_DELETE_INVOICE_QUERY, (id,))
        logger.info(f"Deleted invoice [{id}]")

    def get_time_entries(
        self, start: datetime.date, end: datetime.date
    ) -> list[TimeEntry]:
        with self.connect() as db:
            rows = db.execute(
                _TIME_ENTRIES_QUERY,
                (
                    self.get_user_id(),
                    self.get_workspace_id(),
                    start,
                    end,
                ),
            ).fetchall()

        entries: list[TimeEntry] = []

        for row in rows:
            date = datetime.datetime.strptime(row[0], self._DATE_FORMAT)
            description = str(row[1])
            duration_seconds = int(row[2])
            duration_hours = (round((duration_seconds / 3600) * 4) / 4) or 0.25
            time_entry = TimeEntry(date, description, duration_hours, 70.0)
            entries.append(time_entry)

        return entries

    def save_invoice(self, invoice: Invoice) -> None:
        invoice_data = (
            invoice.invoice_number,
            invoice.invoice_date,
            invoice.period_start,
            invoice.period_end,
            invoice.company.name,
            invoice.client.name,
            invoice.total,
            0,
            base64.b64encode(invoice.pdf()).decode(),
            base64.b64encode(pickle.dumps(invoice)).decode(),
        )
        with self.connect() as db:
            cols = (
                "number",
                "date",
                "period_start",
                "period_end",
                "payer",
                "payee",
                "total",
                "paid",
                "pdf",
                "pickle",
            )
            db.execute(
                f"INSERT INTO invoice({','.join(cols)}) VALUES(?,?,?,?,?,?,?,?,?,?)",
                invoice_data,
            )

    def get_invoices(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(_INVOCES_QUERY).fetchall()

        invoices: list[dict[str, Any]] = []

        for row in rows:
            invoice_id = int(row[0])
            pickle_bytes = base64.b64decode(row[1])
            invoice: Invoice = pickle.loads(pickle_bytes)
            invoice_dict = invoice.to_dict()
            invoice_dict.update({"invoice_id": invoice_id})
            invoices.append(invoice_dict)

        return invoices

    def get_next_invoice_number(self) -> int:
        with self.connect() as db:
            cur = db.execute("SELECT MAX(number) FROM invoice")
            result = cur.fetchone()[0] or 0
        return int(result) + 1

    def clear_clockify_tables(self) -> None:
        """
        Delete all data in time_entry, user, and workspace
        """
        with self.connect() as db:
            db.execute("DELETE FROM time_entry")
            db.execute("DELETE FROM user")
            db.execute("DELETE FROM workspace")

    def get_workspace_id(self) -> str | None:
        if not self._workspace_id:
            with self.connect() as db:
                cur = db.execute(
                    "SELECT COALESCE(active_workspace, default_workspace) FROM user"
                )
                result = cur.fetchone()
            if result:
                self._workspace_id = result[0]
        return self._workspace_id

    def get_user_id(self) -> str | None:
        if not self._user_id:
            with self.connect() as db:
                result = db.execute("SELECT id FROM user").fetchone()
                try:
                    self._user_id = result[0]
                except TypeError:
                    self._user_id = None
        return self._user_id
