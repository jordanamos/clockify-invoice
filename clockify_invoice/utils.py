import functools
import logging
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from datetime import date
from datetime import datetime
from datetime import timezone
from typing import Any

from flask import current_app
from flask import make_response
from flask import request

from clockify_invoice.api import ClockifyClient
from clockify_invoice.api import ClockifySession
from clockify_invoice.store import Store

logger = logging.getLogger("clockify-invoice")


class APIKeyMissingError(Exception):
    pass


def auth_required(func: Callable[..., Any]) -> Any:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        auth = request.authorization
        if (
            request.authorization
            and auth.username == current_app.config["USER"]  # type: ignore
            and auth.password == current_app.config["PASS"]  # type: ignore
        ):
            return func(*args, **kwargs)
        return make_response(
            "<h1>Access Denied!</h1>",
            401,
            {"WWW-Authenticate": "Basic realm='Login Required!'"},
        )
    return wrapper


def get_period_dates(start_year: int, start_month: int) -> tuple[date, date]:
    end_month = 1 if start_month == 12 else start_month + 1
    end_year = start_year + 1 if start_month == 12 else start_year
    period_start = date(start_year, start_month, 1)
    period_end = date(end_year, end_month, 1)
    return period_start, period_end


def get_api_key() -> str:
    env_var = "CLOCKIFY_API_KEY"
    api_key = os.getenv(env_var)
    if api_key is None:
        raise APIKeyMissingError(
            "'CLOCKIFY_API_KEY' environment variable not set.\n"
            "Connection to Clockify's API requires an API Key which can"
            "be found in your user settings."
        )
    return api_key


def synch_user(api_session: ClockifyClient, db: sqlite3.Connection) -> tuple[str, str]:
    """
    Fetches the User from the clockify API and inserts the User into the db.
    Returns the user id and workspace id
    """
    user = api_session.get_user()
    user_id = user["id"]
    active_workspace = user["activeWorkspace"]
    default_workspace = user["defaultWorkspace"]
    workspace = active_workspace or default_workspace
    user_table_data = (
        user_id,
        user["name"],
        user["email"],
        default_workspace,
        active_workspace,
        user["settings"]["timeZone"],
    )

    if not user_id:
        raise ValueError(f"SYNCH FAILED: Invalid User {user_id}")
    if not workspace:
        raise ValueError("SYNCH FAILED: Unable to fetch Workspace")

    db.execute("INSERT INTO user VALUES(?,?,?,?,?,?)", user_table_data)
    return user_id, workspace


def synch_workspaces(api_session: ClockifyClient, db: sqlite3.Connection) -> None:
    workspaces = api_session.get_workspaces()
    workspaces_data = [(ws["id"], ws["name"]) for ws in workspaces]
    db.executemany("INSERT INTO workspace VALUES(?,?)", workspaces_data)


def synch_time_entries(
    api_session: ClockifyClient,
    db: sqlite3.Connection,
    user_id: str,
    workspace_id: str,
) -> None:
    time_entries = api_session.get_time_entries(workspace_id, user_id)
    clockify_date_format = "%Y-%m-%dT%H:%M:%SZ"
    data = []

    def _convert_datestr(datestr: str) -> datetime:
        return (
            datetime.strptime(datestr, clockify_date_format)
            .replace(tzinfo=timezone.utc)
            .astimezone(tz=None)
        )

    for te in time_entries:
        end = te["timeInterval"]["end"]
        if end is None:
            # No end date. Is the timer still going?
            continue

        entry_id = te["id"]
        desc = te["description"]
        start = te["timeInterval"]["start"]
        start_time = _convert_datestr(start)
        end_time = _convert_datestr(end)
        start_time_formatted = datetime.strftime(start_time, Store._DATE_FORMAT)
        end_time_formatted = datetime.strftime(end_time, Store._DATE_FORMAT)

        duration_secs = (end_time - start_time).total_seconds()

        data.append(
            (
                entry_id,
                start_time_formatted,
                end_time_formatted,
                duration_secs,
                desc,
                user_id,
                workspace_id,
            )
        )
    db.executemany("INSERT INTO time_entry VALUES(?,?,?,?,?,?,?)", data)


def synch_with_clockify(store: Store) -> int:
    # Create a back up of the db
    fd, backup_db = tempfile.mkstemp(dir=store.directory)
    os.close(fd)
    shutil.copy(store.db_path, backup_db)
    try:
        store.clear_clockify_tables()
        with (
            ClockifySession(get_api_key()) as session,
            store.connect() as db,
        ):
            logger.info("Synching the local db with clockify...")
            client = ClockifyClient(session)
            user_id, workspace_id = synch_user(client, db)
            synch_workspaces(client, db)
            synch_time_entries(client, db, user_id, workspace_id)
    except (KeyboardInterrupt, Exception):
        # Something bad happened restore the db backup
        os.replace(backup_db, store.db_path)
        raise
    else:
        os.remove(backup_db)
    return 0
