"""Configuration loading: env vars → TOML file → defaults."""

from __future__ import annotations

import os
from pathlib import Path

from pybrisk._internal.exceptions import ConfigurationError

_DEFAULT_CONFIG_DIR = Path.home() / ".pybrisk"
_DEFAULT_TOML_PATH = _DEFAULT_CONFIG_DIR / "config.toml"
_DEFAULT_COOKIES_PATH = _DEFAULT_CONFIG_DIR / "cookies.json"


class Config:
    """Runtime configuration for pybrisk.

    Priority: env vars > TOML file > defaults.
    """

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self.timeout: int = 30
        self.cache_ttl: int = 3600
        self.rate_limit: float = 1.0
        self.cookies_path: Path = _DEFAULT_COOKIES_PATH
        self._load_env()
        self._load_toml()

    def _load_env(self) -> None:
        if val := os.environ.get("BRISK_USERNAME"):
            self._username = val
        if val := os.environ.get("BRISK_PASSWORD"):
            self._password = val

    def _load_toml(self) -> None:
        if not _DEFAULT_TOML_PATH.exists():
            return
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        with open(_DEFAULT_TOML_PATH, "rb") as f:
            data = tomllib.load(f)

        auth = data.get("auth", {})
        if not self._username:
            self._username = auth.get("username")
        if not self._password:
            self._password = auth.get("password")

        settings = data.get("settings", {})
        if "timeout" in settings:
            self.timeout = int(settings["timeout"])
        if "cache_ttl" in settings:
            self.cache_ttl = int(settings["cache_ttl"])
        if "rate_limit" in settings:
            self.rate_limit = float(settings["rate_limit"])

    @property
    def username(self) -> str:
        if not self._username:
            raise ConfigurationError(
                "Username not set. Use BRISK_USERNAME env var or ~/.pybrisk/config.toml"
            )
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        self._username = value

    @property
    def password(self) -> str:
        if not self._password:
            raise ConfigurationError(
                "Password not set. Use BRISK_PASSWORD env var or ~/.pybrisk/config.toml"
            )
        return self._password

    @password.setter
    def password(self, value: str) -> None:
        self._password = value

    @property
    def has_credentials(self) -> bool:
        return self._username is not None and self._password is not None
