"""Ticker class — per-stock data access."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pandas as pd

if TYPE_CHECKING:
    from pybrisk._internal.client import Client

Interval = Literal["5m", "1d", "1w", "1mo"]


class Ticker:
    """Access per-stock market data from BRiSK.

    Usage::

        ticker = Ticker("7203", client=client)
        df = ticker.ohlc()
        df = ticker.ohlc(interval="5m")
        df = ticker.jsfc(count=30)
    """

    def __init__(self, code: str, *, client: Client) -> None:
        self._code = code
        self._client = client

    @property
    def code(self) -> str:
        return self._code

    def __repr__(self) -> str:
        return f"Ticker('{self._code}')"

    def ohlc(self, interval: Interval | None = None) -> pd.DataFrame:
        """Fetch OHLC candle data.

        Args:
            interval: "5m", "1d", "1w", "1mo", or None for daily.

        Returns:
            DataFrame with columns: date, open, high, low, close, turnover.
        """
        resp = self._client.fetch_ohlc(self._code)

        if interval is None:
            interval = "1d"

        if interval == "5m":
            rows = [
                {
                    "date": bar.date,
                    "index": bar.index,
                    "open": bar.open_price,
                    "high": bar.high_price,
                    "low": bar.low_price,
                    "close": bar.close_price,
                    "turnover": bar.turnover,
                }
                for bar in resp.ohlc5min
            ]
        elif interval == "1d":
            rows = [
                {
                    "date": bar.date,
                    "open": bar.open_price,
                    "high": bar.high_price,
                    "low": bar.low_price,
                    "close": bar.close_price,
                    "turnover": bar.turnover,
                }
                for bar in resp.ohlc1day
            ]
        elif interval == "1w":
            rows = [
                {
                    "year": bar.year,
                    "week": bar.week,
                    "open": bar.open_price,
                    "high": bar.high_price,
                    "low": bar.low_price,
                    "close": bar.close_price,
                    "turnover": bar.turnover,
                }
                for bar in resp.ohlc1week
            ]
        elif interval == "1mo":
            rows = [
                {
                    "year": bar.year,
                    "month": bar.month,
                    "open": bar.open_price,
                    "high": bar.high_price,
                    "low": bar.low_price,
                    "close": bar.close_price,
                    "turnover": bar.turnover,
                }
                for bar in resp.ohlc1month
            ]
        else:
            raise ValueError(f"Invalid interval: {interval!r}. Use '5m', '1d', '1w', or '1mo'.")

        return pd.DataFrame(rows)

    def jsfc(self, count: int = 365) -> pd.DataFrame:
        """Fetch margin lending (JSFC) data.

        Args:
            count: Number of trading days to fetch.

        Returns:
            DataFrame with margin lending/borrowing data.
        """
        entries = self._client.fetch_jsfc(self._code, count=count)
        rows = [
            {
                "date": e.date,
                "long_shares": e.kakuhoLongShares,
                "short_shares": e.kakuhoShortShares,
                "preliminary_long": e.sokuhoLongShares,
                "preliminary_short": e.sokuhoShortShares,
                "standardized_long": e.standardizedLongShares,
                "standardized_short": e.standardizedShortShares,
                "borrowing_fee": e.gyakuhibuFee,
                "borrowing_fee_pct": e.gyakuhibuFeePercent,
                "borrowing_fee_days": e.gyakuhibuFeeDayCount,
                "borrowing_fee_max": e.gyakuhibuMaxFee,
            }
            for e in entries
        ]
        return pd.DataFrame(rows)
