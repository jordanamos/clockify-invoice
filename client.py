from api import APIResponse, APIServer
from datetime import date, datetime


class APISession:
    """
    Handles all the GET requests to the Clockify API

    """

    clockify_datetime_format = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, APIServer):
        self.api = APIServer
        self.user = self.get_user()
        self.user_id = self.user["id"]
        self.email = self.user["email"]
        self.workspace = self.user["defaultWorkspace"]
        self.timezone = self.user["settings"]["timeZone"]

    def set_workspace(self, workspace_id: str) -> APIResponse:
        self.workspace = workspace_id

    def get_user(self) -> APIResponse:
        return self.api.get("/user")

    def get_project(self, project_id) -> APIResponse:
        return self.api.get(f"/workspaces/{self.workspace}/projects/{project_id}")

    def get_projects(self) -> APIResponse:
        return self.api.get(f"/workspaces/{self.workspace}/projects")

    def get_workspaces(self) -> APIResponse:
        return self.api.get("/workspaces")

    def get_default_workspace(self) -> APIResponse:
        return self.user["defaultWorkspace"]

    def get_time_entries(
        self,
        workspace_id: str = None,
        user_id: str = None,
        start_date: date = None,
        end_date: date = None,
    ) -> APIResponse:

        if workspace_id is None:
            workspace_id = self.workspace
        if user_id is None:
            user_id = self.user_id

        path = f"/workspaces/{workspace_id}/user/{user_id}/time-entries"
        params = {}

        if start_date is not None:
            params["start"] = start_date.strftime(self.clockify_datetime_format)
        if end_date is not None:
            params["end"] = end_date.strftime(self.clockify_datetime_format)

        return self.api.get(path, params)
