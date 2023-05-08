from datetime import date
from typing import Any

from clockify.api import APIServer


class APISession:
    """
    Handles all the GET requests to the Clockify API

    """

    clockify_datetime_format = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, api: APIServer) -> None:
        self.api = api
        # self.user = self.get_user()
        # self.user_id = self.user["id"]
        # self.email = self.user["email"]
        # self.workspace = self.user["defaultWorkspace"]
        # self.timezone = self.user["settings"]["timeZone"]

    def set_workspace(self, workspace_id: str) -> None:
        self.workspace = workspace_id

    def get_user(self) -> dict[str, Any]:
        return self.api.get("/user")

    def get_project(self, project_id: int) -> dict[str, Any]:
        return self.api.get(f"/workspaces/{self.workspace}/projects/{project_id}")

    def get_projects(self) -> list[dict[str, Any]]:
        return self.api.get(f"/workspaces/{self.workspace}/projects")

    def get_workspaces(self) -> list[dict[str, Any]]:
        return self.api.get("/workspaces")

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
            params["start"] = start_date.strftime(self.clockify_datetime_format)
        if end_date is not None:
            params["end"] = end_date.strftime(self.clockify_datetime_format)

        return self.api.get(path, params)
