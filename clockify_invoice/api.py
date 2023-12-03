from __future__ import annotations

import http.client
import json
from json.decoder import JSONDecodeError
from types import TracebackType
from typing import Any
from typing import Literal


class ClockifySession:
    API_BASE_ENDPOINT = "https://api.clockify.me/api/v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.connection = http.client.HTTPSConnection("api.clockify.me")
        self.headers = {
            "X-Api-key": self.api_key,
            "content-type": "application/json",
            "Connection": "keep-alive",
        }

    def __enter__(self) -> ClockifySession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _request(
        self, method: Literal["GET", "POST"], url: str
    ) -> http.client.HTTPResponse:
        self.connection.request(method, url, headers=self.headers)
        res = self.connection.getresponse()
        if res.status < 200 or res.status >= 300:
            # The response status code indicates an error
            error_msg = f"{res.status} {res.reason}:{res.read().decode()}"
            raise http.client.HTTPException(error_msg)
        return res

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
    def __init__(self, session: ClockifySession) -> None:
        self.session = session

    def get_user(self) -> dict[str, Any]:
        return self.session.get("user")

    def get_workspaces(self) -> list[dict[str, Any]]:
        return self.session.get("workspaces")

    def get_time_entries(
        self,
        workspace_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        path = f"workspaces/{workspace_id}/user/{user_id}/time-entries"
        return self.session.get(path)


class ClockifyAPIException(Exception):
    pass


class APIResponseParseException(Exception):
    pass
