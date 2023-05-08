import argparse
import calendar as cal
import contextlib
import io
import json
import os
from collections.abc import Generator
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

import werkzeug.wrappers
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import session
from flask import wrappers
from requests import Session
from weasyprint import HTML

from clockify.api import APIKeyMissingError
from clockify.api import APIServer
from clockify.client import APISession
from clockify.invoice import Invoice, TimeEntry
from clockify.store import Store

app = Flask(__name__)


@app.template_filter("format_date")
def format_date(
    value: Any, informat: str = "%d/%m/%Y", outformat: str = "%d/%m/%Y"
) -> str:
    if not isinstance(value, date):
        try:
            return datetime.strptime(value, informat).strftime(outformat)
        except ValueError:
            return f"Error parsing date [{value}]"
    else:
        return value.strftime(outformat)


@app.route("/download", methods=["GET"])
def download() -> wrappers.Response | werkzeug.wrappers.Response:
    if "invoice" in session:
        invoice = json.loads(session.get("invoice", ""))
        invoice_name = "invoice.pdf"
        form_data = {
            "display-form": "none",
        }
        rendered_invoice = render_template(
            "invoice.html", invoice=invoice, form_data=form_data
        )
        html = HTML(string=rendered_invoice)
        rendered_pdf = html.write_pdf()

        if rendered_pdf:
            return send_file(
                io.BytesIO(rendered_pdf),
                mimetype="application/pdf",
                download_name=invoice_name,  # type: ignore
                as_attachment=True,
            )
    return redirect("/")


@app.route("/", methods=["GET", "POST"])
def process_invoice() -> str:
    store = app.config["store"]
    invoice_company = "Jordan Amos"
    invoice_client = "6 Cloud Systems"

    form_data = {
        "invoice-number": "1",
        "invoice-period": "this-month",
        "display-form": "block",
    }

    if request.method == "POST":
        form_data.update(request.form)

    invoice_number = form_data["invoice-number"]
    today = date.today()
    period_date = date(today.year, today.month, 1)

    if form_data["invoice-period"] == "last-month":
        period_date = period_date - timedelta(weeks=4)
    elif form_data["invoice-period"] == "two-months-ago":
        period_date = period_date - timedelta(weeks=8)
    elif form_data["invoice-period"] == "three-months-ago":
        period_date = period_date - timedelta(weeks=12)

    period_start = period_date.replace(day=1)
    period_end = period_date.replace(
        day=cal.monthrange(period_date.year, period_date.month)[1]
    )

    invoice = Invoice(
        store,
        invoice_number,
        invoice_company,
        invoice_client,
        period_start,
        period_end,
    )

    session["invoice"] = invoice.to_json()
    rendered_invoice = render_template(
        "invoice.html", invoice=invoice.__dict__, form_data=form_data
    )

    return rendered_invoice


def run_interactive() -> int:
    print(app.config["store"])
    # app.run(host="0.0.0.0", port=5000, debug=True)
    return 0


@contextlib.contextmanager
def clockify_session() -> Generator[Session, None, None]:
    api_key = os.getenv("CLOCKIFY_API_KEY")
    if api_key is None:
        raise APIKeyMissingError(
            """
            'CLOCKIFY_API_KEY' environment variable not set.
            Connection to Clockify's API requires an  API Key which can
            be found in your user settings.
            """
        )

    app.secret_key = api_key

    with contextlib.closing(Session()) as sess:
        sess.headers = {
            "X-Api-key": api_key,
            "content-type": "application/json",
        }
        yield sess


def generate_invoice(store: Store) -> int:
    workspace = store.get_default_workspace_id()
    user = store.get_user_id()
    if not (workspace and user):
        print(
            f"Unable to generate invoice: User ({user}) or "
            f"Workspace ({workspace}) has 'None' value."
        )
        return 1

    # invoice_number = "1"
    # invoice_company = "Jordan Amos"
    # invoice_client = "6 Cloud Systems"
    today = date.today()
    period_date = date(today.year, today.month, 1) - timedelta(weeks=4)
    period_start = period_date.replace(day=1)
    period_end = period_date.replace(
        day=cal.monthrange(period_date.year, period_date.month)[1]
    )

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
    
    with store.connect() as db:
        rows = db.execute(
            TIME_ENTRIES_QUERY, 
            (user, workspace, period_start, period_end),
        ).fetchall()


    # 2023-04-11 04:30:24 2023-04-11 05:20:54 0:50:30 PT50M30S
    # 2023-04-11 00:43:08 2023-04-11 01:46:33 1:03:25 PT1H3M25S
    # 2023-04-10 22:28:44 2023-04-11 00:05:08 1:36:24 PT1H36M24S
    # 2023-04-10 21:38:00 2023-04-10 22:20:00 0:42:00 PT42M
    time_entries: list[TimeEntry] = []

    for row in rows:
        duration_hours = round((row[2] / 3600) * 4) / 4
        if duration_hours == 0:
            # nothing is for free
            duration_hours = 0.25
        time_entry = TimeEntry(row[0], row[1], duration_hours, 70.0)
        time_entries.append(time_entry)

    for e in time_entries:
        print(e.billable_amount)
        # start = datetime.strptime(row[0], clockify_date_format)
        # end = datetime.strptime(row[1], clockify_date_format)
        # diff = end - start
        # print(start, end, diff, row[3])
        # print(datetime.fromisoformat(row[2]))
        # duration = datetime.strptime(row[2], 'PT%HH%Mm%Ss')
        # total_seconds = duration.hour * 3600 + duration.minute * 60 + duration.second
        # print(duration)
        # print(total_seconds)
    # invoice = Invoice(
    #     store,
    #     invoice_number,
    #     invoice_company,
    #     invoice_client,
    #     period_start,
    #     period_end,
    # )
    # print(invoice)
    return 0
# 

def synch(store: Store, time_entries_only: bool) -> int:
    with (
        clockify_session() as session,
        store.connect() as db,
    ):
        api_session = APISession(APIServer(session))
        # TODO make a backup of the db file if it exists
        # before doing this work incase it fails
        if not time_entries_only:
            store.clear_db()
            user = api_session.get_user()
            user_table_data = (
                user["id"],
                user["name"],
                user["email"],
                user["defaultWorkspace"],
                user["activeWorkspace"],
            )
            db.execute("INSERT INTO user VALUES(?,?,?,?,?)", user_table_data)

            workspaces = api_session.get_workspaces()
            workspaces_data = [(ws["id"], ws["name"]) for ws in workspaces]
            db.executemany("INSERT INTO workspace VALUES(?,?)", workspaces_data)
            db.commit()
        else:
            store.clear_db("time_entry")

        workspace = store.get_default_workspace_id()
        user = store.get_user_id()  # type: ignore
        if workspace is None or user is None:
            print(
                f"Unable to fetch time entries: User ({user}) or "
                f"Workspace ({workspace}) has 'None' value."
            )
            return 1

        clockify_date_format = "%Y-%m-%dT%H:%M:%SZ"  # ISO 8601

        def get_clockify_diff_seconds(date_start_string: str, date_end_string:str):
            date_start = datetime.strptime(date_start_string, clockify_date_format)
            date_end = datetime.strptime(date_end_string, clockify_date_format)
            return (date_end - date_start).total_seconds()
        
        time_entries = api_session.get_time_entries(workspace, user)  # type: ignore
        time_entries_data = [
            (
                te["id"],
                datetime.strptime(te["timeInterval"]["start"], clockify_date_format),
                datetime.strptime(te["timeInterval"]["end"], clockify_date_format),
                # te["timeInterval"]["duration"],
                get_clockify_diff_seconds(te["timeInterval"]["start"], te["timeInterval"]["end"]),
                te["description"],
                user,
                None,  # Project
                workspace,
            )
            for te in time_entries
        ]
        db.executemany(
            "INSERT INTO time_entry VALUES(?,?,?,?,?,?,?,?)", time_entries_data
        )

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clockify Invoice Command Line Tool")
    command_parser = parser.add_subparsers(dest="command")

    synch_parser = command_parser.add_parser(
        "synch",
        help="Synch the local db with clockify.",
    )
    synch_parser.add_argument(
        "--entries-only",
        action="store_true",
        help="Set this flag to only synch the time entries",
    )

    invoice_parser = command_parser.add_parser(
        "invoice", help="Generate a clockify invoice"
    )

    invoice_parser.add_argument(
        "-i",
        action="store_true",
        dest="interactive_mode",
        help="Run a local server to create invoices interactively in the browser",
    )

    args = parser.parse_args(argv)

    store = Store()

    if args.command == "invoice":
        if args.interactive_mode:
            app.config["store"] = store
            return run_interactive()
        return generate_invoice(store)
    elif args.command == "synch":
        return synch(store, args.entries_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
