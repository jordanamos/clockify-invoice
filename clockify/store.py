import contextlib
import os
import sqlite3
from collections.abc import Generator


class Store:
    def __init__(self) -> None:
        self.directory = self._get_default_directory()
        self.db_path = os.path.join(self.directory, "db.db")

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
                    default_workspace_id TEXT,
                    active_workspace_id TEXT,
                    FOREIGN KEY (default_workspace_id) REFERENCES workspace(id)
                    FOREIGN KEY (active_workspace_id) REFERENCES workspace(id)
                )
            """
            )

            db.execute(
                """
                CREATE TABLE client (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    workspace_id TEXT,
                    FOREIGN KEY (workspace_id) REFERENCES workspace(id)
                )
            """
            )

            db.execute(
                """
                CREATE TABLE project (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    client_id TEXT,
                    workspace_id TEXT,
                    FOREIGN KEY (client_id) REFERENCES client(id),
                    FOREIGN KEY (workspace_id) REFERENCES workspace(id)
                )
            """
            )

            db.execute(
                """
                CREATE TABLE time_entry (
                    id TEXT PRIMARY KEY,
                    start_time TEXT,
                    end_time TEXT,
                    duration TEXT,
                    description TEXT,
                    user_id TEXT,
                    project_id TEXT,
                    workspace_id TEXT,
                    FOREIGN KEY (user_id) REFERENCES user(id),
                    FOREIGN KEY (project_id) REFERENCES project(id),
                    FOREIGN KEY (workspace_id) REFERENCES workspace(id)
                )
            """
            )

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
