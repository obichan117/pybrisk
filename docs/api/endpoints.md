# Backend API Endpoints

pybrisk wraps BRiSK's internal REST API at `https://sbi.brisk.jp`. This page documents all endpoints used by the library, plus additional endpoints available for future use.

## Authentication flow

```
1. Cookie auth    →  GET /api/frontend/boot  →  returns api_token (PASETO v2.local)
2. Bearer auth    →  All subsequent requests use Authorization: Bearer {api_token}
```

The session cookie (e.g., `session_bfaf77a2`) is an HTTPOnly cookie set when opening BRiSK from the SBI Securities website. The `api_token` is a PASETO v2.local encrypted token (not inspectable client-side).

## Endpoints used by pybrisk

### `GET /api/frontend/boot`

Bootstrap endpoint. Returns user identity and tokens.

**Auth:** Cookie only (no Bearer token yet)

**Response:**
```json
{
  "result": true,
  "user_id": "uuid-v4",
  "identity": "sha256-hex-64chars",
  "csrf_token": "sha256-hex-64chars",
  "api_token": "v2.local.{PASETO}",
  "api_endpoint": "https://api.brisk.jp",
  "session_expires": 1773259200,
  "tfx_token": "v2.local.{PASETO}",
  "tfx_api_base_url": "https://tfx-api.brisk.jp"
}
```

---

### `GET /api/app/boot`

App bootstrap. Returns trading session info.

**Auth:** Bearer token

**Response:**
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
  "next_date": 1773270000,
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

Schedule times are in **nanoseconds from midnight JST**.

---

### `GET /api/ohlc/{code}?date={YYYY-MM-DD}`

OHLC candle data for a single stock. Returns all four timeframes in one response.

**Auth:** Bearer token

**Response:**
```json
{
  "ohlc5min": [
    {"date": "2026-03-09", "index": 2, "diff": -2, "open_price": 4610.0,
     "high_price": 4640.0, "low_price": 4600.0, "close_price": 4635.0,
     "turnover": 687492500, "open_turnover": 444404000}
  ],
  "ohlc1day": [
    {"date": "2025-09-16", "open_price": 2900.0, "high_price": 2944.0,
     "low_price": 2895.5, "close_price": 2934.5, "turnover": 64755932500}
  ],
  "ohlc1week": [
    {"year": 2022, "week": 40, "open_price": 605.0, "high_price": 641.0,
     "low_price": 602.0, "close_price": 620.0, "turnover": 3327362200}
  ],
  "ohlc1month": [
    {"year": 2014, "month": 4, "open_price": 964.0, "high_price": 968.0,
     "low_price": 757.0, "close_price": 768.0, "turnover": 8975884900}
  ]
}
```

Prices are in **yen** (float — some stocks have .5 yen increments). Turnover is in **yen** (integer).

---

### `GET /api/jsfc/{code}?count={N}`

Margin lending data from JSFC (Japan Securities Finance Corporation).

**Auth:** Bearer token

**Response:** Map keyed by date string:
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

---

### `GET /api/stocks_info?date={YYYY-MM-DD}`

Stock metadata for all TSE securities (~4,500 items).

**Auth:** Bearer token

**Response:** Array of objects:
```json
[
  {"issue_code": "4169", "turnover": 27063800, "calc_shares_outstanding": 42834528},
  {"issue_code": "7203", "turnover": 50000000000, "calc_shares_outstanding": 16314987460}
]
```

---

### `GET /api/stock_lists?date={YYYY-MM-DD}`

Curated stock lists.

**Auth:** Bearer token

**Response:**
```json
{
  "version": "1",
  "stock_lists": [
    {"id": "ipo3month", "name": "直近IPO", "issue_codes": ["509A", "511A"]},
    {"id": "nk225etf", "name": "日経225構成銘柄", "issue_codes": ["1332", "1333"]}
  ]
}
```

---

### `GET /api/markets?date={YYYY-MM-DD}&series=0&index_from=0&index_to=618`

Market condition alerts (場況速報), paginated.

**Auth:** Bearer token

**Response:**
```json
{
  "market_conditions": [
    {
      "index": 0,
      "issue_code": "3655",
      "kind": 1,
      "type": 6,
      "price10": 26910,
      "value10": 2691000000,
      "diff_bps_from_last": 0,
      "time": "08:00:00.048598"
    }
  ]
}
```

`price10` = price × 10 (26910 → 2691.0 yen). `time` has microsecond precision. Some fields are optional (e.g., basket orders have no `issue_code`).

---

### `GET /api/frontend/watchlist`

User's saved watchlist.

**Auth:** Bearer token (uses cookie session)

**Response:**
```json
{
  "empty": false,
  "version": "1.0.0",
  "uuid": "uuid-v4",
  "data": "base64+zlib-compressed-string"
}
```

The `data` field is zlib-compressed then base64-encoded JSON containing watchlist groups and stock codes.

---

### `GET /api/app/market-token`

Token for real-time WebSocket data (future use).

**Auth:** Bearer token

**Response:**
```json
{"token": "v2.local.{PASETO}"}
```

## Endpoints not yet used by pybrisk

These endpoints are available but require binary format reverse-engineering:

| Endpoint | Method | Format | Description |
|---|---|---|---|
| `/api/master/{hash}` | GET | Binary (~800KB) | Master data — all stock definitions |
| `/api/snapshot/{hash}` | GET | Binary (~29MB) | Full market snapshot — current state of all order books |
| `POST /api/stocks_update/{series}` | POST | Binary (~227KB) | Delta updates for specific stocks |
| `wss://sbi.brisk.jp/realtime/0?session={token}` | WebSocket | Binary (compressed) | Real-time streaming market data |

### TFX API (Futures)

A separate gRPC-Connect API at `tfx-api.brisk.jp` serves Tokyo Financial Exchange data:

| Endpoint | Method | Format | Description |
|---|---|---|---|
| `/brisk.tfx.api.ApiService/Boot` | POST | Protobuf | TFX bootstrap — master/snapshot hashes |
| `/data/master/{hash}` | GET | Protobuf (~3KB) | Futures contract definitions |
| `/data/snapshot/{hash}` | GET | Protobuf (~6.5KB) | Futures price snapshot |
