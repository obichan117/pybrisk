"""Tests for API client."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from pybrisk._internal.client import Client
from pybrisk._internal.config import Config
from pybrisk._internal.session import Session


@pytest.fixture
def config() -> Config:
    with patch.dict(os.environ, {}, clear=True):
        c = Config()
    c.rate_limit = 0
    return c


@pytest.fixture
def mock_session(config: Config) -> MagicMock:
    return MagicMock(spec=Session)


BOOT_RESPONSE = {
    "result": True,
    "user_id": "test-uuid",
    "identity": "testhash",
    "csrf_token": "csrfhash",
    "api_token": "v2.local.testtoken",
    "api_endpoint": "https://api.brisk.jp",
    "session_expires": 9999999999,
    "tfx_token": "",
    "tfx_api_base_url": "",
}

APP_BOOT_RESPONSE = {
    "result": True,
    "series": 0,
    "date": "2026-03-11",
    "session_status": "running",
    "ws_url": "/realtime/0?session=abc",
    "master": "masterhash",
    "snapshot": "snaphash",
    "time": 1773193002,
    "next_date": 1773270000,
    "schedule_info": {
        "morning_session_pre_open_time": 28800000000,
        "morning_session_open_time": 32400000000,
        "morning_session_close_time": 41400000000,
        "afternoon_session_pre_open_time": 43500000000,
        "afternoon_session_open_time": 45000000000,
        "afternoon_session_pre_close_time": 55500000000,
        "afternoon_session_close_time": 55800000000,
        "sq_jump_interval": 180,
    },
}


def _setup_boot(mock_session: MagicMock) -> None:
    """Configure mock to return boot responses."""
    mock_session.get.side_effect = lambda url, **kwargs: (
        BOOT_RESPONSE
        if "frontend/boot" in url
        else APP_BOOT_RESPONSE
        if "app/boot" in url
        else {}
    )


def test_boot_sequence(mock_session: MagicMock) -> None:
    _setup_boot(mock_session)
    client = Client(mock_session)
    client._ensure_booted()
    assert client.frontend_boot.user_id == "test-uuid"
    assert client.app_boot.date == "2026-03-11"
    assert mock_session.get.call_count == 2


def test_boot_called_once(mock_session: MagicMock) -> None:
    _setup_boot(mock_session)
    client = Client(mock_session)
    client._ensure_booted()
    client._ensure_booted()
    assert mock_session.get.call_count == 2  # only called during first boot


def test_fetch_ohlc(mock_session: MagicMock) -> None:
    call_count = 0

    def side_effect(url: str, **kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if "frontend/boot" in url:
            return BOOT_RESPONSE
        if "app/boot" in url:
            return APP_BOOT_RESPONSE
        if "ohlc" in url:
            return {"ohlc5min": [], "ohlc1day": [], "ohlc1week": [], "ohlc1month": []}
        return {}

    mock_session.get.side_effect = side_effect
    client = Client(mock_session)
    resp = client.fetch_ohlc("7203")
    assert resp.ohlc5min == []
    assert resp.ohlc1day == []


def test_fetch_jsfc(mock_session: MagicMock) -> None:
    def side_effect(url: str, **kwargs: object) -> dict:
        if "frontend/boot" in url:
            return BOOT_RESPONSE
        if "app/boot" in url:
            return APP_BOOT_RESPONSE
        if "jsfc" in url:
            return {
                "2025-03-11": {
                    "date": "2025-03-11",
                    "sochi": "",
                    "kakuhoLongShares": 100,
                    "kakuhoShortShares": 200,
                    "sokuhoLongShares": 100,
                    "sokuhoShortShares": 200,
                }
            }
        return {}

    mock_session.get.side_effect = side_effect
    client = Client(mock_session)
    entries = client.fetch_jsfc("7203")
    assert len(entries) == 1
    assert entries[0].date == "2025-03-11"


def test_fetch_stocks_info(mock_session: MagicMock) -> None:
    def side_effect(url: str, **kwargs: object) -> object:
        if "frontend/boot" in url:
            return BOOT_RESPONSE
        if "app/boot" in url:
            return APP_BOOT_RESPONSE
        if "stocks_info" in url:
            return [{"issue_code": "7203", "turnover": 1000000}]
        return {}

    mock_session.get.side_effect = side_effect
    client = Client(mock_session)
    infos = client.fetch_stocks_info()
    assert len(infos) == 1
    assert infos[0].issue_code == "7203"


def test_fetch_stock_lists(mock_session: MagicMock) -> None:
    def side_effect(url: str, **kwargs: object) -> dict:
        if "frontend/boot" in url:
            return BOOT_RESPONSE
        if "app/boot" in url:
            return APP_BOOT_RESPONSE
        if "stock_lists" in url:
            return {
                "version": "1",
                "stock_lists": [
                    {"id": "nk225etf", "name": "NK225", "issue_codes": ["1332"]}
                ],
            }
        return {}

    mock_session.get.side_effect = side_effect
    client = Client(mock_session)
    resp = client.fetch_stock_lists()
    assert resp.stock_lists[0].id == "nk225etf"


def test_fetch_markets(mock_session: MagicMock) -> None:
    def side_effect(url: str, **kwargs: object) -> dict:
        if "frontend/boot" in url:
            return BOOT_RESPONSE
        if "app/boot" in url:
            return APP_BOOT_RESPONSE
        if "markets" in url:
            return {
                "market_conditions": [
                    {
                        "index": 0,
                        "issue_code": "3655",
                        "kind": 1,
                        "type": 6,
                        "price10": 26910,
                        "value10": 2691000000,
                        "diff_bps_from_last": 0,
                        "time": "08:00:00.048598",
                    }
                ]
            }
        return {}

    mock_session.get.side_effect = side_effect
    client = Client(mock_session)
    conditions = client.fetch_markets()
    assert len(conditions) == 1
    assert conditions[0].issue_code == "3655"
