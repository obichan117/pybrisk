"""Integration tests against live BRiSK API.

Run with: uv run pytest tests/integration/ -v
Requires active BRiSK session (cookies in Chrome).
"""

from __future__ import annotations

import pytest
from pycookiecheat import chrome_cookies

import pybrisk as pb

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def authenticate() -> None:
    cookies = chrome_cookies("https://sbi.brisk.jp")
    assert cookies, "No BRiSK cookies found in Chrome. Is BRiSK open?"
    pb.login(cookies=cookies)


class TestBootstrap:
    def test_frontend_boot(self) -> None:
        boot = pb._client.frontend_boot
        assert boot.result is True
        assert boot.user_id
        assert boot.csrf_token
        assert boot.api_token.startswith("v2.local.")

    def test_app_boot(self) -> None:
        boot = pb._client.app_boot
        assert boot.result is True
        assert boot.date
        assert boot.session_status in ("running", "closed", "pre_open")
        assert boot.schedule_info.morning_session_open_time == 32400000000


class TestTicker:
    def test_ohlc_daily(self) -> None:
        ticker = pb.Ticker("7203")
        df = ticker.ohlc()
        assert len(df) > 0
        assert "open" in df.columns
        assert "close" in df.columns
        assert "turnover" in df.columns
        print(f"\n  OHLC daily: {len(df)} rows")
        print(df.head(3).to_string())

    def test_ohlc_5min(self) -> None:
        ticker = pb.Ticker("7203")
        df = ticker.ohlc("5m")
        assert len(df) > 0
        assert "index" in df.columns
        print(f"\n  OHLC 5min: {len(df)} rows")

    def test_ohlc_weekly(self) -> None:
        ticker = pb.Ticker("7203")
        df = ticker.ohlc("1w")
        assert len(df) > 0
        assert "year" in df.columns

    def test_ohlc_monthly(self) -> None:
        ticker = pb.Ticker("7203")
        df = ticker.ohlc("1mo")
        assert len(df) > 0

    def test_jsfc(self) -> None:
        ticker = pb.Ticker("7203")
        df = ticker.jsfc(count=30)
        assert len(df) > 0
        assert "long_shares" in df.columns
        assert "borrowing_fee" in df.columns
        print(f"\n  JSFC: {len(df)} rows")
        print(df.head(3).to_string())


class TestMarket:
    def test_stocks_info(self) -> None:
        market = pb.Market()
        df = market.stocks_info()
        assert len(df) > 3000  # should have ~3800 stocks
        assert "code" in df.columns
        assert "turnover" in df.columns
        print(f"\n  Stocks info: {len(df)} stocks")

    def test_stock_lists(self) -> None:
        market = pb.Market()
        lists = market.stock_lists()
        assert isinstance(lists, dict)
        assert len(lists) > 0
        print(f"\n  Stock lists: {list(lists.keys())}")
        for name, codes in lists.items():
            print(f"    {name}: {len(codes)} stocks")

    def test_alerts(self) -> None:
        market = pb.Market()
        df = market.alerts()
        assert isinstance(df, type(df))  # DataFrame
        print(f"\n  Alerts: {len(df)} events")
        if len(df) > 0:
            print(df.head(3).to_string())

    def test_schedule(self) -> None:
        market = pb.Market()
        sched = market.schedule()
        assert "date" in sched
        assert "status" in sched
        assert "morning_open" in sched
        print(f"\n  Schedule: {sched}")

    def test_watchlist(self) -> None:
        market = pb.Market()
        codes = market.watchlist()
        assert isinstance(codes, list)
        print(f"\n  Watchlist: {len(codes)} stocks")
