from __future__ import annotations

from json.decoder import JSONDecodeError
from typing import Any

import requests
from exceptions import ClockifyAPIException


class APIServer:
    api_base_endpoint = "https://api.clockify.me/api/v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers = {
            "X-Api-key": self.api_key,
            "content-type": "application/json",
        }

    def get(self, path: str, params: dict[str, str] = {}) -> dict[str, Any]:
        url = self.api_base_endpoint + path

        raw_response = self.session.get(
            url,
            params=params,
        )
        return APIResponse(raw_response).parse()


# class User:
#     def __init__(self, APISession) -> None:
#         user = APISession.get("/user")
#         self.user_id = user["id"]
#         self.email = user["email"]
#         self.active_workspace = user["activeWorkspace"]
#         self.default_workspace = user["defaultWorkspace"]
#         self.timezone = user["settings"]["timeZone"]


class APIResponse:
    def __init__(self, raw_response: requests.Response) -> None:
        self.raw_response = raw_response

    def parse(self) -> dict[str, Any]:
        if self.raw_response.status_code in [200, 201]:
            return self.parse_json()
        else:
            error_response = self.parse_json()
            # msg = f"APIResponse Error [{error_response['code']}]
            #  {error_response['message']}"
            # TODO handle exceptions
            raise Exception(error_response)

    def parse_json(self) -> dict[str, Any]:
        try:
            return self.raw_response.json()
        except JSONDecodeError:
            msg = f"Unable to parse response as JSON: '{self.raw_response.text}'"
            raise APIResponseParseException(msg)


class APIException(ClockifyAPIException):
    """Base exception for this module."""

    pass


class APIServerException(APIException):
    """An exception in the API server itself, communicated in response by the API"""

    pass


class APIKeyMissingError(APIException):
    pass


class APIResponseParseException(APIException):
    pass
