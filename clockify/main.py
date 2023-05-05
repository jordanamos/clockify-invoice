import argparse
import contextlib
import os
from collections.abc import Generator
from collections.abc import Sequence

from requests import Session

from clockify.api import APIKeyMissingError
from clockify.app import app


def run_interactive(clockify_session: Session) -> int:
    app.run(host="0.0.0.0", port=5000, debug=True)
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
    with contextlib.closing(Session()) as sess:
        sess.headers = {
            "X-Api-key": api_key,
            "content-type": "application/json",
        }
        yield sess


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clockify Invoice Command Line Tool")
    parser.add_argument(
        "-i",
        action="store_true",
        dest="interactive_mode",
        help="Runs a local server to create invoices interactively in the browser",
    )
    args = parser.parse_args(argv)

    with clockify_session() as sess:
        if args.interactive_mode:
            return run_interactive(sess)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
