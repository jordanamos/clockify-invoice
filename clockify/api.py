from __future__ import annotations

import json
import os
import urllib.request
from datetime import date
from json.decoder import JSONDecodeError
from typing import Any
from http import cookiejar
from requests import Session


class ClockifySession(Session):
    API_BASE_ENDPOINT = "https://api.clockify.me/api/v1"

    def __init__(self) -> None:
        api_key = os.getenv("CLOCKIFY_API_KEY")
        if api_key is None:
            raise APIKeyMissingError(
                "'CLOCKIFY_API_KEY' environment variable not set.\n"
                "Connection to Clockify's API requires an API Key which can"
                "be found in your user settings."
            )
        super().__init__()
        self.api_key = api_key
        self.headers.update(
            {
                "X-Api-key": api_key,
                "content-type": "application/json",
            }
        )

    def get_clockify(self, endpoint: str, params: dict[str, str] = {}) -> Any:
        """Performs a "GET" request to the clockify API. Returns the JSON response."""
        url = f"{self.API_BASE_ENDPOINT}/{endpoint}"
        response = self.get(url, params=params)
        response.raise_for_status()
        try:
            return response.json()
        except JSONDecodeError:
            msg = f"Unable to parse response as JSON: '{response.text}'"
            raise APIResponseParseException(msg)


class ClockifySessionURLLIB:
    API_BASE_ENDPOINT = "https://api.clockify.me/api/v1"

    def __init__(self) -> None:
        api_key = os.getenv("CLOCKIFY_API_KEY")
        if api_key is None:
            raise APIKeyMissingError(
                "'CLOCKIFY_API_KEY' environment variable not set.\n"
                "Connection to Clockify's API requires an API Key which can"
                "be found in your user settings."
            )
        self.cookie_jar = cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.api_key = api_key
        self.headers = {
            "X-Api-key": api_key,
            "content-type": "application/json",
        }

    def get_clockify(self, endpoint: str, params: dict[str, str] = {}) -> Any:
        """Performs a "GET" request to the clockify API. Returns the JSON response."""
        url = f"{self.API_BASE_ENDPOINT}/{endpoint}"
        request = urllib.request.Request(url, headers=self.headers)
        resp = self.opener.open(request)
        try:
            return json.load(resp)
        except JSONDecodeError:
            msg = f"Unable to parse response as JSON: '{resp}'"
            raise APIResponseParseException(msg)


class ClockifyClient:
    CLOCKIFY_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, api: ClockifySession) -> None:
        self.api = api

    def get_user(self) -> dict[str, Any]:
        return self.api.get_clockify("user")

    def get_workspaces(self) -> list[dict[str, Any]]:
        return self.api.get_clockify("workspaces")

    def get_time_entries(
        self,
        workspace_id: str,
        user_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        path = f"/workspaces/{workspace_id}/user/{user_id}/time-entries"
        params = {}
        if start_date is not None:
            params["start"] = start_date.strftime(self.CLOCKIFY_DATETIME_FORMAT)
        if end_date is not None:
            params["end"] = end_date.strftime(self.CLOCKIFY_DATETIME_FORMAT)

        return self.api.get_clockify(path, params)


class ClockifyAPIException(Exception):
    pass


class APIKeyMissingError(ClockifyAPIException):
    pass


class APIResponseParseException(ClockifyAPIException):
    pass
