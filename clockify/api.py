from __future__ import annotations

import os
from datetime import date
from json.decoder import JSONDecodeError
from typing import Any
from requests import Session
import urllib
import http.client
import json
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

    def get_clockify(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        """Performs a GET request to the clockify API and returns the JSON response."""
        url = f"{self.API_BASE_ENDPOINT}/{endpoint}"
        response = self.get(url, params=params)
        response.raise_for_status()
        try:
            return response.json()
        except JSONDecodeError:
            msg = f"Unable to parse response as JSON: '{response.text}'"
            raise APIResponseParseException(msg)

class ClockifySession1:
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
        self.headers = {
            "X-Api-key": api_key,
            "content-type": "application/json",
            "Connection": "keep-alive",
        }
        self.connection = http.client.HTTPSConnection("api.clockify.me")
        
    def __enter__(self):
        return self
    
    def __exit__(self, t,f,s):
        self.connection.close()
        
    def request(self, method:str, path):
        self.connection.request(method=method, url=path, headers=self.headers)
        response = self.connection.getresponse()
        return response
        
    def get(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        """Performs a GET request to the clockify API and returns the JSON response."""
        url = f"{self.API_BASE_ENDPOINT}/{endpoint}"
        response = self.request("GET",url)
        data = response.read().decode()
        try:
            return json.loads(data)
        except JSONDecodeError:
            msg = f"Unable to parse response as JSON: '{response.text}'"
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
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        path = f"/workspaces/{workspace_id}/user/{user_id}/time-entries"
        params = {}
        if start_date is not None:
            params["start"] = start_date.strftime(self.CLOCKIFY_DATETIME_FORMAT)
        if end_date is not None:
            params["end"] = end_date.strftime(self.CLOCKIFY_DATETIME_FORMAT)

        return self.api.get(path, params)


class ClockifyAPIException(Exception):
    pass


class APIKeyMissingError(ClockifyAPIException):
    pass


class APIResponseParseException(ClockifyAPIException):
    pass
