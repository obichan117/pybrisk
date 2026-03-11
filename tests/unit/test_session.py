"""Tests for HTTP session layer."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import httpx
import pytest

from pybrisk._internal.config import Config
from pybrisk._internal.exceptions import (
    APIError,
    NotFoundError,
    RateLimitError,
    SessionExpiredError,
)
from pybrisk._internal.session import Session


@pytest.fixture
def config() -> Config:
    with patch.dict(os.environ, {}, clear=True):
        c = Config()
    c.rate_limit = 0  # disable rate limiting for tests
    return c


@pytest.fixture
def session(config: Config) -> Session:
    return Session(config)


def test_load_cookies_from_dict(session: Session) -> None:
    session.load_cookies({"session_id": "abc123"})
    assert session.has_cookies
    assert session._cookies == {"session_id": "abc123"}


def test_load_cookies_from_file(session: Session, tmp_path: object) -> None:
    cookies_file = tmp_path / "cookies.json"  # type: ignore[operator]
    cookies_file.write_text(json.dumps({"key": "val"}))
    session._config.cookies_path = cookies_file  # type: ignore[assignment]
    session.load_cookies()
    assert session._cookies == {"key": "val"}


def test_no_cookies_initially(session: Session) -> None:
    assert session.has_cookies is False


def test_save_cookies(session: Session, tmp_path: object) -> None:
    session._config.cookies_path = tmp_path / "cookies.json"  # type: ignore[operator]
    session.load_cookies({"test": "cookie"})
    saved = json.loads(session._config.cookies_path.read_text())
    assert saved == {"test": "cookie"}


def test_handle_401_raises_session_expired(session: Session) -> None:
    response = httpx.Response(401, text="Unauthorized")
    with pytest.raises(SessionExpiredError):
        session._handle_response(response)


def test_handle_403_raises_session_expired(session: Session) -> None:
    response = httpx.Response(403, text="Forbidden")
    with pytest.raises(SessionExpiredError):
        session._handle_response(response)


def test_handle_404_raises_not_found(session: Session) -> None:
    response = httpx.Response(404, text="Not found")
    with pytest.raises(NotFoundError):
        session._handle_response(response)


def test_handle_429_raises_rate_limit(session: Session) -> None:
    response = httpx.Response(429, text="Too many requests")
    with pytest.raises(RateLimitError):
        session._handle_response(response)


def test_handle_500_raises_api_error(session: Session) -> None:
    response = httpx.Response(500, text="Server error")
    with pytest.raises(APIError) as exc_info:
        session._handle_response(response)
    assert exc_info.value.status_code == 500


def test_handle_200_ok(session: Session) -> None:
    response = httpx.Response(200)
    session._handle_response(response)  # should not raise
