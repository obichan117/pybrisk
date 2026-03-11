# BRiSK Data Schemas

## `/api/frontend/boot`

```json
{
  "result": true,
  "user_id": "uuid-v4",
  "identity": "sha256-hex-64chars",
  "csrf_token": "sha256-hex-64chars",
  "api_token": "v2.local.{PASETO}",
  "api_endpoint": "https://api.brisk.jp",
  "api_local_prefer": true,
  "data": {
    "token": "md5-hex-32chars",
    "url": "https://site0.sbisec.co.jp/..."
  },
  "news_revision": 2,
  "session_expires": 1773259200,
  "chart_token": "",
  "chart_origin": "",
  "tfx_token": "v2.local.{PASETO}",
  "tfx_api_base_url": "https://tfx-api.brisk.jp"
}
```

## `/api/app/boot`

```json
{
  "result": true,
  "series": 0,
  "date": "2026-03-11",
  "session_status": "running",
  "ws_url": "/realtime/0?session={hex}",
  "master": "sha256-hex",
  "snapshot": "{hash}-{date}-{series}",
  "time": 1773193002,
  "session_expires": 0,
  "next_date": 1773270000,
  "base_prices": [],
  "exceptional_sq": [],
  "flex_version": 18000,
  "schedule_info": {
    "morning_session_pre_open_time": 28800000000,
    "morning_session_open_time": 32400000000,
    "morning_session_close_time": 41400000000,
    "afternoon_session_pre_open_time": 43500000000,
    "afternoon_session_open_time": 45000000000,
    "afternoon_session_pre_close_time": 55500000000,
    "afternoon_session_close_time": 55800000000,
    "sq_jump_interval": 180
  }
}
```

Schedule times are in **nanoseconds from midnight** JST.

## `/api/stocks_info?date=YYYY-MM-DD`

```json
[
  {
    "issue_code": "4169",
    "turnover": 27063800,
    "calc_shares_outstanding": 42834528
  }
]
```

~3800+ items (all TSE stocks).

## `/api/stock_lists?date=YYYY-MM-DD`

```json
{
  "version": "1",
  "stock_lists": [
    {
      "id": "ipo3month",
      "name": "直近IPO",
      "issue_codes": ["509A", "511A"]
    },
    {
      "id": "nk225etf",
      "name": "日経225構成銘柄",
      "issue_codes": ["1332", "1333"]
    }
  ]
}
```

## `/api/ohlc/{issue_code}?date=YYYY-MM-DD`

```json
{
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
      "open_turnover": 444404000
    }
  ],
  "ohlc1day": [
    {
      "date": "2025-09-16",
      "open_price": 3200,
      "high_price": 3205,
      "low_price": 3035,
      "close_price": 3050,
      "turnover": 6797321000
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
      "turnover": 3327362200
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
      "turnover": 8975884900
    }
  ]
}
```

Prices are in **yen (integer, no decimals for stocks)**.

## `/api/jsfc/{issue_code}?count=N`

```json
{
  "2025-03-11": {
    "date": "2025-03-11",
    "sochi": "",
    "kakuhoLongShares": 543700,
    "kakuhoShortShares": 622400,
    "sokuhoLongShares": 467400,
    "sokuhoShortShares": 622400,
    "standardizedLongShares": null,
    "standardizedShortShares": null,
    "gyakuhibuFee": 0.05,
    "gyakuhibuFeePercent": 0.00224115,
    "gyakuhibuFeeDayCount": 1,
    "gyakuhibuMaxFee": 4.6
  }
}
```

Map keyed by date string.

## `/api/markets?date=...&series=0&index_from=0&index_to=618`

```json
{
  "market_conditions": [
    {
      "diff_bps_from_last": 0,
      "index": 0,
      "issue_code": "3655",
      "kind": 1,
      "price10": 26910,
      "time": "08:00:00.048598",
      "type": 6,
      "value10": 2691000000
    }
  ]
}
```

- `price10`: price × 10 (26910 = 2691.0 yen)
- `value10`: value × 10
- `time`: microsecond precision
- Paginated via `index_from`/`index_to`

## `/api/frontend/watchlist`

```json
{
  "empty": false,
  "version": "1.0.0",
  "uuid": "uuid-v4",
  "data": "base64+zlib-compressed-string"
}
```

## `/api/app/market-token`

```json
{
  "token": "v2.local.{PASETO}"
}
```

## Binary Endpoints

| Endpoint | Format | Size |
|---|---|---|
| `/api/master/{hash}` | Custom binary | ~800KB |
| `/api/snapshot/{hash}` | Custom binary | ~29MB |
| `/api/stocks_update/{series}` | Custom binary | ~227KB |

## Delta Update Request (`stocks_update`)

```json
{
  "issue_ids": [0, 1, 5, 6],
  "update_numbers_from": [3678, 42262],
  "update_numbers_to": [3680, 42267]
}
```

Parallel arrays: issue_ids[i] → from[i]..to[i] sequence range.
