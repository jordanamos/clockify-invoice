import requests


class ClockifyAPI:
    def __init__(self, url: str, api_key: str) -> None:
        self.url = url

    def get(self, path, api_key, params=None):

        return requests.get(
            self.url + path,
            headers={"X-Api-key": api_key, "content-type": "application/json"},
            params=params,
        )
