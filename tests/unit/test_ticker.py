"""Tests for Ticker class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from pybrisk._internal.models import JSFCEntry, OHLCBar1Day, OHLCBar5Min, OHLCResponse
from pybrisk.ticker import Ticker


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.fetch_ohlc.return_value = OHLCResponse(
        ohlc5min=[
            OHLCBar5Min(
                date="2026-03-11",
                index=0,
                diff=0,
                open_price=2000,
                high_price=2050,
                low_price=1980,
                close_price=2030,
                turnover=100000000,
            )
        ],
        ohlc1day=[
            OHLCBar1Day(
                date="2026-03-11",
                open_price=2000,
                high_price=2100,
                low_price=1950,
                close_price=2080,
                turnover=500000000,
            )
        ],
    )
    client.fetch_jsfc.return_value = [
        JSFCEntry(
            date="2026-03-11",
            kakuhoLongShares=100000,
            kakuhoShortShares=200000,
            sokuhoLongShares=100000,
            sokuhoShortShares=200000,
            gyakuhibuFee=0.05,
        )
    ]
    return client


def test_ticker_repr() -> None:
    t = Ticker("7203", client=MagicMock())
    assert repr(t) == "Ticker('7203')"


def test_ticker_code() -> None:
    t = Ticker("7203", client=MagicMock())
    assert t.code == "7203"


def test_ohlc_daily() -> None:
    client = _mock_client()
    t = Ticker("7203", client=client)
    df = t.ohlc()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert list(df.columns) == ["date", "open", "high", "low", "close", "turnover"]
    assert df.iloc[0]["open"] == 2000


def test_ohlc_5min() -> None:
    client = _mock_client()
    t = Ticker("7203", client=client)
    df = t.ohlc(interval="5m")
    assert len(df) == 1
    assert "index" in df.columns


def test_jsfc() -> None:
    client = _mock_client()
    t = Ticker("7203", client=client)
    df = t.jsfc(count=30)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]["long_shares"] == 100000
    assert df.iloc[0]["borrowing_fee"] == 0.05
    client.fetch_jsfc.assert_called_once_with("7203", count=30)
