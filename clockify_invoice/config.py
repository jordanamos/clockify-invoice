from __future__ import annotations

import functools
import json
import os
from typing import Any

from clockify_invoice.invoice import Client
from clockify_invoice.invoice import Company

_SAMPLE_CONFIG = """\
{
    "api_key": "",
    "flask": {
        "host": "0.0.0.0",
        "port": 5000,
        "user": "",
        "password": ""

    },
    "mail": {
        "server": "smtp.gmail.com",
        "port": 465,
        "username": "",
        "password": "",
        "use_tls": false,
        "use_ssl": true
    },
    "company": {
        "name": "Your Company",
        "email": "your.email@gmail.com",
        "abn": "123 456 789",
        "rate": 70.0
    },
    "client": {
        "contact": "Ben Howard",
        "name": "Your Client",
        "email": "client.email@gmail.com"
    }
}
"""


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, config_file: str) -> None:
        try:
            with open(config_file) as f:
                self._config: dict[str, Any] = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"Error in {config_file}: {e}")

        self.config_file = config_file
        self._load_flask_config()
        self._load_mail_config()

    @property
    def api_key(self) -> str:
        return self._get_setting("api_key", os.getenv("CLOCKIFY_API_KEY"), True)

    @property
    def company(self) -> Company:
        return self._load_company_from_config()

    @property
    def client(self) -> Client:
        return self._load_client_from_config()

    def _get_setting(
        self,
        setting: str,
        default: Any | None = None,
        required: bool = True,
        cfg: dict[str, Any] | None = None,
    ) -> Any:
        _cfg = cfg or self._config
        if not isinstance(_cfg, dict):
            raise ConfigError(f"Invalid config: {_cfg}")
        val = _cfg.get(setting, default)
        if required and (val is None or (isinstance(val, str) and len(val) == 0)):
            raise ConfigError(f"Setting is required: {setting}")
        return val

    def _load_client_from_config(self) -> Client:
        _client_cfg = self._get_setting("client")
        _get_client_setting = functools.partial(self._get_setting, cfg=_client_cfg)
        return Client(
            _get_client_setting("name"),
            _get_client_setting("email"),
            _get_client_setting("contact"),
        )

    def _load_company_from_config(self) -> Company:
        _company_cfg = self._get_setting("company")
        _get_company_setting = functools.partial(self._get_setting, cfg=_company_cfg)
        try:
            rate = float(_get_company_setting("rate"))
        except ValueError as e:
            raise ConfigError(f"Invalid company rate: {e}")
        else:
            return Company(
                _get_company_setting("name"),
                _get_company_setting("email"),
                _get_company_setting("abn"),
                rate,
            )

    def _load_mail_config(self) -> None:
        _mail_cfg = self._get_setting("mail", default={})
        _get_mail_setting = functools.partial(self._get_setting, cfg=_mail_cfg)
        try:
            self.MAIL_PORT = int(_get_mail_setting("port", default=25))
        except ValueError as e:
            raise ConfigError(f"Invalid port: {e}")
        self.MAIL_USE_SSL = _get_mail_setting("use_ssl", default=False)
        self.MAIL_USE_TLS = _get_mail_setting("use_tls", default=False)
        self.MAIL_SERVER = _get_mail_setting("server", default="localhost")
        self.MAIL_USERNAME = _get_mail_setting("username", required=False)
        self.MAIL_PASSWORD = _get_mail_setting("password", required=False)

    def _load_flask_config(self) -> None:
        _flask_cfg = self._get_setting("flask", default={})
        _get_flask_setting = functools.partial(self._get_setting, cfg=_flask_cfg)
        try:
            self.FLASK_PORT = int(_get_flask_setting("port", default=5000))
        except ValueError as e:
            raise ConfigError(f"Invalid port: {e}")
        self.FLASK_HOST = _get_flask_setting("host", default="0.0.0.0")
        self.FLASK_USER = _get_flask_setting("user", required=False)
        self.FLASK_PASSWORD = _get_flask_setting("password", required=False)

    def reset(self) -> None:
        self.createConfig(self.config_file)
    
    @staticmethod
    def createConfig(config_file: str) -> None:
        with open(config_file, "w") as f:
            f.write(_SAMPLE_CONFIG)

    def save_config(self, config: dict[str, Any]) -> None:
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=4)
