import contextlib
import os
import sqlite3
from collections.abc import Generator
import logging

logger = logging.getLogger("clockify-invoice")


class Store:
    def __init__(self) -> None:
        self.directory = self._get_default_directory()

        logger.info(f"Using store directory: {self.directory}")

        self.db_path = os.path.join(self.directory, "db.db")
        self._workspace_id = None
        self._user_id = None
        if not os.path.exists(self.directory):
            os.makedirs(self.directory, exist_ok=True)
        self.create_db()

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
                    pdf TEXT
                );
                """
            )

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
        logger.info(f"Connecting to db... {self.db_path}")
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                yield db
