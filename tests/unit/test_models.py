"""Tests for Pydantic models against real API response shapes."""

from pybrisk._internal.models import (
    AppBootResponse,
    FrontendBootResponse,
    JSFCEntry,
    MarketCondition,
    MarketsResponse,
    OHLCResponse,
    StockInfo,
    StockListsResponse,
    WatchlistResponse,
)


def test_ohlc_response() -> None:
    data = {
        "ohlc5min": [
            {
                "date": "2026-03-09",
                "index": 2,
                "diff": -2,
                "open_price": 4610,
                "high_price": 4640,
                "low_price": 4600,
                "close_price": 4635,
                "turnover": 687492500,
                "open_turnover": 444404000,
            }
        ],
        "ohlc1day": [
            {
                "date": "2025-09-16",
                "open_price": 3200,
                "high_price": 3205,
                "low_price": 3035,
                "close_price": 3050,
                "turnover": 6797321000,
            }
        ],
        "ohlc1week": [
            {
                "year": 2022,
                "week": 40,
                "open_price": 605,
                "high_price": 641,
                "low_price": 602,
                "close_price": 620,
                "turnover": 3327362200,
            }
        ],
        "ohlc1month": [
            {
                "year": 2014,
                "month": 4,
                "open_price": 964,
                "high_price": 968,
                "low_price": 757,
                "close_price": 768,
                "turnover": 8975884900,
            }
        ],
    }
    resp = OHLCResponse.model_validate(data)
    assert len(resp.ohlc5min) == 1
    assert resp.ohlc5min[0].open_price == 4610
    assert len(resp.ohlc1day) == 1
    assert resp.ohlc1week[0].year == 2022
    assert resp.ohlc1month[0].month == 4


def test_stock_info() -> None:
    data = {"issue_code": "4169", "turnover": 27063800, "calc_shares_outstanding": 42834528}
    info = StockInfo.model_validate(data)
    assert info.issue_code == "4169"
    assert info.turnover == 27063800


def test_stock_lists_response() -> None:
    data = {
        "version": "1",
        "stock_lists": [
            {"id": "ipo3month", "name": "直近IPO", "issue_codes": ["509A", "511A"]},
            {"id": "nk225etf", "name": "日経225構成銘柄", "issue_codes": ["1332", "1333"]},
        ],
    }
    resp = StockListsResponse.model_validate(data)
    assert len(resp.stock_lists) == 2
    assert resp.stock_lists[0].id == "ipo3month"


def test_jsfc_entry() -> None:
    data = {
        "date": "2025-03-11",
        "sochi": "",
        "kakuhoLongShares": 543700,
        "kakuhoShortShares": 622400,
        "sokuhoLongShares": 467400,
        "sokuhoShortShares": 622400,
        "standardizedLongShares": None,
        "standardizedShortShares": None,
        "gyakuhibuFee": 0.05,
        "gyakuhibuFeePercent": 0.00224115,
        "gyakuhibuFeeDayCount": 1,
        "gyakuhibuMaxFee": 4.6,
    }
    entry = JSFCEntry.model_validate(data)
    assert entry.kakuhoLongShares == 543700
    assert entry.gyakuhibuFee == 0.05


def test_market_condition() -> None:
    data = {
        "diff_bps_from_last": 0,
        "index": 0,
        "issue_code": "3655",
        "kind": 1,
        "price10": 26910,
        "time": "08:00:00.048598",
        "type": 6,
        "value10": 2691000000,
    }
    cond = MarketCondition.model_validate(data)
    assert cond.issue_code == "3655"
    assert cond.price10 == 26910


def test_markets_response() -> None:
    data = {
        "market_conditions": [
            {
                "diff_bps_from_last": 0,
                "index": 0,
                "issue_code": "3655",
                "kind": 1,
                "price10": 26910,
                "time": "08:00:00.048598",
                "type": 6,
                "value10": 2691000000,
            }
        ]
    }
    resp = MarketsResponse.model_validate(data)
    assert len(resp.market_conditions) == 1


def test_frontend_boot_response() -> None:
    data = {
        "result": True,
        "user_id": "abc-123",
        "identity": "sha256hex",
        "csrf_token": "csrfhex",
        "api_token": "v2.local.token",
        "api_endpoint": "https://api.brisk.jp",
        "session_expires": 1773259200,
        "tfx_token": "v2.local.tfx",
        "tfx_api_base_url": "https://tfx-api.brisk.jp",
    }
    resp = FrontendBootResponse.model_validate(data)
    assert resp.result is True
    assert resp.user_id == "abc-123"


def test_app_boot_response() -> None:
    data = {
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
    resp = AppBootResponse.model_validate(data)
    assert resp.session_status == "running"
    assert resp.schedule_info.morning_session_open_time == 32400000000


def test_watchlist_response() -> None:
    data = {"empty": False, "version": "1.0.0", "uuid": "abc-uuid", "data": "base64data"}
    resp = WatchlistResponse.model_validate(data)
    assert resp.empty is False
    assert resp.data == "base64data"


def test_extra_fields_ignored() -> None:
    data = {"issue_code": "1234", "turnover": 100, "unknown_field": "ignored"}
    info = StockInfo.model_validate(data)
    assert info.issue_code == "1234"
