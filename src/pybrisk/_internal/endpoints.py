"""Declarative endpoint definitions for BRiSK API."""

from __future__ import annotations

from dataclasses import dataclass

BASE_URL = "https://sbi.brisk.jp"


@dataclass(frozen=True)
class Endpoint:
    """API endpoint definition."""

    path: str
    method: str = "GET"

    def url(self, **path_params: str) -> str:
        path = self.path.format(**path_params) if path_params else self.path
        return f"{BASE_URL}{path}"


# Bootstrap
FRONTEND_BOOT = Endpoint("/api/frontend/boot")
APP_BOOT = Endpoint("/api/app/boot")
MARKET_TOKEN = Endpoint("/api/app/market-token")

# Per-stock
OHLC = Endpoint("/api/ohlc/{code}")
JSFC = Endpoint("/api/jsfc/{code}")

# Market-wide
STOCKS_INFO = Endpoint("/api/stocks_info")
STOCK_LISTS = Endpoint("/api/stock_lists")
MARKETS = Endpoint("/api/markets")

# User data
WATCHLIST = Endpoint("/api/frontend/watchlist")

# Binary (future use)
MASTER = Endpoint("/api/master/{hash}")
SNAPSHOT = Endpoint("/api/snapshot/{hash}")
STOCKS_UPDATE = Endpoint("/api/stocks_update/{series}", method="POST")
