import base64
import contextlib
import datetime
import json
import logging
import os
import pickle
import sqlite3
from collections.abc import Generator
from typing import Any

from clockify_invoice.invoice import Client
from clockify_invoice.invoice import Company
from clockify_invoice.invoice import Invoice
from clockify_invoice.invoice import TimeEntry

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
WHERE period_start > ?
    AND period_end < ?
"""

_DELETE_INVOICE_QUERY = """\
DELETE
FROM INVOICE
WHERE id = ?
"""


class ConfigError(Exception):
    pass


class Store:
    _DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, config_file: str | None) -> None:
        self.directory = self._get_default_directory()

        if not os.path.exists(self.directory):
            os.makedirs(self.directory, exist_ok=True)
            logger.debug(
                f"Store directory '{self.directory}' did not exist so it was created"
            )
        logger.debug(f"Using store directory: {self.directory}")

        _config_file = config_file or os.path.join(
            self.directory, "clockify-invoice-config.json"
        )

        self.db_path = os.path.join(self.directory, "db.db")
        self._workspace_id = None
        self._user_id = None
        self._load_and_validate_config(_config_file)
        self._create_db_if_not_exists()

    @staticmethod
    def _get_default_directory() -> str:
        return os.getenv("CLOCKIFY_INVOICE_HOME") or os.path.join(
            os.path.expanduser("~"),
            "clockify-invoice",
        )

    def _get_setting(
        self,
        setting: str,
        default: Any | None = None,
        required: bool = True,
        config_override: dict[str, Any] | None = None,
    ) -> Any:
        _cfg = config_override or self._config
        if not isinstance(_cfg, dict):
            raise ConfigError(f"Invalid config: {_cfg}")
        val = _cfg.get(setting, default)
        if required and val is None:
            raise ConfigError(f"Setting is required: {setting}")
        return val

    def _load_flask_settings(self) -> None:
        _flask_settings = self._get_setting("flask", default={})
        self.flask_user: str = self._get_setting(
            "user", required=False, config_override=_flask_settings
        )
        self.flask_password: str = self._get_setting(
            "password", required=False, config_override=_flask_settings
        )
        self.flask_host: str = self._get_setting(
            "host", default="0.0.0.0", config_override=_flask_settings
        )
        try:
            self.flask_port = int(
                self._get_setting("port", default=5000, config_override=_flask_settings)
            )
        except ValueError as e:
            raise ConfigError(f"Invalid flask port: {e}")

    def _load_company_from_config(self) -> Company:
        _company_settings = self._get_setting("company")
        try:
            rate = float(self._get_setting("rate", config_override=_company_settings))
        except ValueError as e:
            raise ConfigError(f"Invalid company rate: {e}")
        else:
            return Company(
                self._get_setting("name", config_override=_company_settings),
                self._get_setting("email", config_override=_company_settings),
                self._get_setting("abn", config_override=_company_settings),
                rate,
            )

    def _load_client_from_config(self) -> Client:
        _client_settings = self._get_setting("client")
        return Client(
            self._get_setting("name", config_override=_client_settings),
            self._get_setting("email", config_override=_client_settings),
            self._get_setting("contact", config_override=_client_settings),
        )

    def _load_and_validate_config(self, config_path: str) -> None:
        try:
            with open(config_path) as f:
                self._config: dict[str, Any] = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"Error in {config_path}: {e}")

        self.api_key = self._get_setting("api_key", os.getenv("CLOCKIFY_API_KEY"))
        self._load_flask_settings()
        self.company = self._load_company_from_config()
        self.client = self._load_client_from_config()

    def _create_db_if_not_exists(self, db_path: str | None = None) -> None:
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

    @contextlib.contextmanager
    def connect(
        self, db_path: str | None = None
    ) -> Generator[sqlite3.Connection, None, None]:
        path = db_path if db_path is not None else self.db_path
        with contextlib.closing(sqlite3.connect(path)) as db:
            with db:
                yield db

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
            time_entry = TimeEntry(date, description, duration_hours, self.company.rate)
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

    def get_invoices(self, financial_year: int) -> list[dict[str, Any]]:
        start_date = datetime.datetime(financial_year, 6, 30)
        end_date = datetime.datetime(financial_year + 1, 7, 1)
        with self.connect() as db:
            rows = db.execute(_INVOCES_QUERY, (start_date, end_date)).fetchall()

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
