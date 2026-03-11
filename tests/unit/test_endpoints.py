"""Tests for endpoint definitions."""

from pybrisk._internal.endpoints import (
    APP_BOOT,
    BASE_URL,
    FRONTEND_BOOT,
    JSFC,
    MARKETS,
    OHLC,
    STOCK_LISTS,
    STOCKS_INFO,
    WATCHLIST,
)


def test_base_url() -> None:
    assert BASE_URL == "https://sbi.brisk.jp"


def test_simple_endpoint_url() -> None:
    assert FRONTEND_BOOT.url() == "https://sbi.brisk.jp/api/frontend/boot"
    assert APP_BOOT.url() == "https://sbi.brisk.jp/api/app/boot"


def test_parameterized_endpoint_url() -> None:
    assert OHLC.url(code="7203") == "https://sbi.brisk.jp/api/ohlc/7203"
    assert JSFC.url(code="1321") == "https://sbi.brisk.jp/api/jsfc/1321"


def test_query_param_endpoints() -> None:
    assert STOCKS_INFO.url() == "https://sbi.brisk.jp/api/stocks_info"
    assert STOCK_LISTS.url() == "https://sbi.brisk.jp/api/stock_lists"
    assert MARKETS.url() == "https://sbi.brisk.jp/api/markets"
    assert WATCHLIST.url() == "https://sbi.brisk.jp/api/frontend/watchlist"


def test_default_method_is_get() -> None:
    assert OHLC.method == "GET"
    assert FRONTEND_BOOT.method == "GET"
