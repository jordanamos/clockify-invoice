import contextlib
import os
import sqlite3
from collections.abc import Generator


class Store:
    def __init__(self) -> None:
        self.directory = self._get_default_directory()
        self.db_path = os.path.join(self.directory, "db.db")

        self._workspace_id = None
        self._user_id = None

        if not os.path.exists(self.directory):
            os.makedirs(self.directory, exist_ok=True)

        if not os.path.exists(self.db_path):
            self.create_db()

    def create_db(self, db_path: str | None = None) -> None:
        with self.connect(db_path) as db:
            db.executescript(
                """\
                CREATE TABLE workspace (
                    id TEXT PRIMARY KEY,
                    name TEXT
                );

                CREATE TABLE user (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    default_workspace TEXT,
                    active_workspace TEXT,
                    FOREIGN KEY (default_workspace) REFERENCES workspace(id),
                    FOREIGN KEY (active_workspace) REFERENCES workspace(id)
                );

                CREATE TABLE time_entry (
                    id TEXT PRIMARY KEY,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds INT,
                    description TEXT,
                    user TEXT,
                    workspace TEXT,
                    FOREIGN KEY (user) REFERENCES user(id),
                    FOREIGN KEY (workspace) REFERENCES workspace(id)
                );"""
            )

    def clear_db(
        self, db_path: str | None = None, table_name: str | None = None
    ) -> None:
        """
        Delete all data in all tables.
        If table_name is given, only data in that table is deleted.
        """
        with self.connect(db_path) as db:
            if table_name:
                db.execute(f"DELETE FROM {table_name}")
            else:
                db.execute("DELETE FROM user")
                db.execute("DELETE FROM workspace")
                db.execute("DELETE FROM time_entry")

    def get_workspace_id(self) -> str | None:
        if not self._workspace_id:
            with self.connect() as db:
                cur = db.execute(
                    "SELECT COALESCE(active_workspace, default_workspace) FROM user"
                )
                result = cur.fetchone()
                try:
                    self._workspace_id = result[0]
                except TypeError:
                    self._workspace_id = None
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
        return os.path.join(
            os.getenv("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "clockify"
        )

    @contextlib.contextmanager
    def connect(
        self, db_path: str | None = None
    ) -> Generator[sqlite3.Connection, None, None]:
        if db_path is None:
            db_path = self.db_path
        with contextlib.closing(sqlite3.connect(db_path)) as db:
            with db:
                yield db
