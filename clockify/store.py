import contextlib
import os
import sqlite3
from collections.abc import Generator


class Store:
    def __init__(self) -> None:
        self.directory = self._get_default_directory()
        self.db_path = os.path.join(self.directory, "db.db")
        self._workspace = None
        self._user_id = None

        if not os.path.exists(self.directory):
            os.makedirs(self.directory, exist_ok=True)

        if os.path.exists(self.db_path):
            return

        with self.connect() as db:
            # Create tables
            db.execute(
                """
                CREATE TABLE workspace (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )
            """
            )

            db.execute(
                """
                CREATE TABLE user (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    default_workspace TEXT,
                    active_workspace TEXT,
                    FOREIGN KEY (default_workspace) REFERENCES workspace(id)
                    FOREIGN KEY (active_workspace) REFERENCES workspace(id)
                )
            """
            )

            db.execute(
                """
                CREATE TABLE client (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    workspace TEXT,
                    FOREIGN KEY (workspace) REFERENCES workspace(id)
                )
            """
            )

            db.execute(
                """
                CREATE TABLE project (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    client TEXT,
                    workspace TEXT,
                    FOREIGN KEY (client) REFERENCES client(id),
                    FOREIGN KEY (workspace) REFERENCES workspace(id)
                )
            """
            )

            db.execute(
                """
                CREATE TABLE time_entry (
                    id TEXT PRIMARY KEY,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds INT,
                    description TEXT,
                    user TEXT,
                    project TEXT,
                    workspace TEXT,
                    FOREIGN KEY (user) REFERENCES user(id),
                    FOREIGN KEY (project) REFERENCES project(id),
                    FOREIGN KEY (workspace) REFERENCES workspace(id)
                )
            """
            )

    def clear_db(self, table_name: str | None = None) -> None:
        """
        Delete all data in all tables.
        If table_name is given, only data in that table is deleted.
        """
        with self.connect() as db:
            if table_name:
                db.execute(f"DELETE FROM {table_name}")
            else:
                db.execute("DELETE FROM user")
                db.execute("DELETE FROM workspace")
                db.execute("DELETE FROM time_entry")
                db.execute("DELETE FROM client")
                db.execute("DELETE FROM project")

    def get_default_workspace_id(self) -> str | None:
        if not self._workspace:
            with self.connect() as db:
                cur = db.execute(
                    "SELECT COALESCE(active_workspace, default_workspace) FROM user"
                )
                result = cur.fetchone()
                try:
                    self._workspace = result[0]
                except TypeError:
                    self._workspace = None
        return self._workspace

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
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            with db:
                yield db
