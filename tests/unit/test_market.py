"""Tests for Market class."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pandas as pd

from pybrisk._internal.models import (
    AppBootResponse,
    MarketCondition,
    ScheduleInfo,
    StockInfo,
    StockListEntry,
    StockListsResponse,
    WatchlistResponse,
)
from pybrisk.market import Market

_SCHEDULE = ScheduleInfo(
    morning_session_pre_open_time=28800000000,
    morning_session_open_time=32400000000,
    morning_session_close_time=41400000000,
    afternoon_session_pre_open_time=43500000000,
    afternoon_session_open_time=45000000000,
    afternoon_session_pre_close_time=55500000000,
    afternoon_session_close_time=55800000000,
    sq_jump_interval=180,
)


def _mock_client() -> MagicMock:
    client = MagicMock()
    type(client).app_boot = PropertyMock(
        return_value=AppBootResponse(
            result=True,
            series=0,
            date="2026-03-11",
            session_status="running",
            ws_url="/realtime/0?session=abc",
            master="hash",
            snapshot="snap",
            time=1773193002,
            next_date=1773270000,
            schedule_info=_SCHEDULE,
        )
    )
    client.fetch_stocks_info.return_value = [
        StockInfo(issue_code="7203", turnover=5000000000, calc_shares_outstanding=1000000000),
    ]
    client.fetch_stock_lists.return_value = StockListsResponse(
        version="1",
        stock_lists=[
            StockListEntry(id="nk225etf", name="NK225", issue_codes=["1332", "7203"]),
        ],
    )
    client.fetch_markets.return_value = [
        MarketCondition(
            index=0,
            issue_code="3655",
            kind=1,
            type=6,
            price10=26910,
            value10=2691000000,
            diff_bps_from_last=0,
            time="08:00:00.048598",
        ),
    ]
    client.fetch_watchlist.return_value = WatchlistResponse(empty=True)
    return client


def test_stocks_info() -> None:
    client = _mock_client()
    m = Market(client=client)
    df = m.stocks_info()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert list(df.columns) == ["code", "turnover", "shares_outstanding"]
    assert df.iloc[0]["code"] == "7203"


def test_stock_lists() -> None:
    client = _mock_client()
    m = Market(client=client)
    lists = m.stock_lists()
    assert isinstance(lists, dict)
    assert "nk225etf" in lists
    assert "7203" in lists["nk225etf"]


def test_alerts() -> None:
    client = _mock_client()
    m = Market(client=client)
    df = m.alerts()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]["price"] == 2691.0  # price10 / 10
    assert df.iloc[0]["code"] == "3655"


def test_schedule() -> None:
    client = _mock_client()
    m = Market(client=client)
    sched = m.schedule()
    assert sched["date"] == "2026-03-11"
    assert sched["status"] == "running"
    assert sched["morning_open"] == 32400000000


def test_watchlist_empty() -> None:
    client = _mock_client()
    m = Market(client=client)
    codes = m.watchlist()
    assert codes == []
