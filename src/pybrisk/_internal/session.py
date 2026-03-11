"""HTTP session layer — I/O only, returns raw data."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from pybrisk._internal.config import Config
from pybrisk._internal.exceptions import (
    APIError,
    NotFoundError,
    RateLimitError,
    SessionExpiredError,
)


class Session:
    """HTTP session with cookie auth, rate limiting, and error handling.

    This layer only does I/O. It returns raw dicts/bytes, never parses into models.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._cookies: dict[str, str] = {}
        self._client: httpx.Client | None = None
        self._last_request_time: float = 0.0
        self._api_token: str | None = None

    def load_cookies(self, cookies: dict[str, str] | None = None) -> None:
        if cookies is not None:
            self._cookies = cookies
            self._save_cookies()
            self._reset_client()
            return

        path = self._config.cookies_path
        if path.exists():
            with open(path) as f:
                self._cookies = json.load(f)
            self._reset_client()

    def _save_cookies(self) -> None:
        path = self._config.cookies_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._cookies, f)

    def _reset_client(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @property
    def has_cookies(self) -> bool:
        return bool(self._cookies)

    @property
    def api_token(self) -> str | None:
        return self._api_token

    @api_token.setter
    def api_token(self, value: str) -> None:
        self._api_token = value
        self._reset_client()

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers = {}
            if self._api_token:
                headers["Authorization"] = f"Bearer {self._api_token}"
            self._client = httpx.Client(
                cookies=self._cookies,
                headers=headers,
                timeout=self._config.timeout,
                follow_redirects=True,
            )
        return self._client

    def _rate_limit(self) -> None:
        if self._config.rate_limit <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        interval = 1.0 / self._config.rate_limit
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_time = time.monotonic()

    def _handle_response(self, response: httpx.Response) -> None:
        if response.status_code == 200:
            return
        if response.status_code == 401 or response.status_code == 403:
            raise SessionExpiredError("Session expired. Call login() again.")
        if response.status_code == 404:
            raise NotFoundError(response.text)
        if response.status_code == 429:
            raise RateLimitError(response.text)
        raise APIError(response.status_code, response.text)

    def get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._rate_limit()
        response = self.client.get(url, params=params)
        self._handle_response(response)
        return response.json()  # type: ignore[no-any-return]

    def get_bytes(self, url: str, params: dict[str, Any] | None = None) -> bytes:
        self._rate_limit()
        response = self.client.get(url, params=params)
        self._handle_response(response)
        return response.content

    def post(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._rate_limit()
        response = self.client.post(url, params=params, json=json_body)
        self._handle_response(response)
        return response.json()  # type: ignore[no-any-return]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
