from __future__ import annotations

import http.client
import json
import os
from json.decoder import JSONDecodeError
from types import TracebackType
from typing import Any
from typing import Literal


class ClockifySession:
    API_BASE_ENDPOINT = "https://api.clockify.me/api/v1"

    def __init__(self) -> None:
        api_key = os.getenv("CLOCKIFY_API_KEY")
        if api_key is None:
            raise APIKeyMissingError(
                "'CLOCKIFY_API_KEY' environment variable not set.\n"
                "Connection to Clockify's API requires an API Key which can"
                "be found in your user settings."
            )
        self.api_key = api_key
        self.headers = {
            "X-Api-key": api_key,
            "content-type": "application/json",
            "Connection": "keep-alive",
        }
        self.connection = http.client.HTTPSConnection("api.clockify.me")

    def __enter__(self) -> ClockifySession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        self.connection.close()

    def _request(
        self, method: Literal["GET", "POST"], url: str
    ) -> http.client.HTTPResponse:
        self.connection.request(method, url, headers=self.headers)
        response = self.connection.getresponse()
        return response

    def get(self, endpoint: str) -> Any:
        """Performs a GET request to the clockify API and returns the JSON response."""
        url = f"{self.API_BASE_ENDPOINT}/{endpoint}"
        response = self._request("GET", url)
        data = response.read().decode()
        try:
            return json.loads(data)
        except JSONDecodeError:
            msg = f"Unable to parse response as JSON: '{data}'"
            raise APIResponseParseException(msg)


class ClockifyClient:
    CLOCKIFY_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, api: ClockifySession) -> None:
        self.api = api

    def get_user(self) -> dict[str, Any]:
        return self.api.get("user")

    def get_workspaces(self) -> list[dict[str, Any]]:
        return self.api.get("workspaces")

    def get_time_entries(
        self,
        workspace_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        path = f"/workspaces/{workspace_id}/user/{user_id}/time-entries"
        return self.api.get(path)


class ClockifyAPIException(Exception):
    pass


class APIKeyMissingError(ClockifyAPIException):
    pass


class APIResponseParseException(ClockifyAPIException):
    pass
