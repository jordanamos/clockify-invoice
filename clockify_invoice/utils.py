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


def auth_required(func: Callable[..., Any]) -> Any:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        auth = request.authorization
        store: Store = current_app.config["store"]

        if not (store.config.FLASK_USER and store.config.FLASK_PASSWORD) or (
            request.authorization
            and auth.username == store.config.FLASK_USER
            and auth.password == store.config.FLASK_PASSWORD
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


def _split_entry_by_month(
    entry_id: str,
    start_time: datetime,
    end_time: datetime,
    desc: str,
    user_id: str,
    workspace_id: str,
) -> list[tuple[Any, ...]]:
    """Split a time entry at month boundaries into one or more DB rows."""
    segments = []
    seg_start = start_time
    while True:
        if seg_start.month == 12:
            next_month = seg_start.replace(
                year=seg_start.year + 1,
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        else:
            next_month = seg_start.replace(
                month=seg_start.month + 1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        seg_end = min(end_time, next_month)
        segments.append((seg_start, seg_end))
        if seg_end >= end_time:
            break
        seg_start = next_month

    fmt = Store._DATE_FORMAT
    return [
        (
            entry_id if len(segments) == 1 else f"{entry_id}_{i}",
            datetime.strftime(s, fmt),
            datetime.strftime(e, fmt),
            (e - s).total_seconds(),
            desc,
            user_id,
            workspace_id,
        )
        for i, (s, e) in enumerate(segments)
    ]


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
        start_time = _convert_datestr(te["timeInterval"]["start"])
        end_time = _convert_datestr(end)

        data.extend(
            _split_entry_by_month(
                entry_id, start_time, end_time, desc, user_id, workspace_id
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
            ClockifySession(store.config.api_key) as session,
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
