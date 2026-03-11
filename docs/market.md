# Market API

The `Market` class provides market-wide data access for all TSE-listed securities.

```python
import pybrisk as pb

market = pb.Market()
```

---

## `market.stocks_info()`

Fetch turnover and shares outstanding for all TSE-listed stocks. Returns ~4,500 rows.

### Return columns

| Column | Type | Description |
|---|---|---|
| `code` | str | Stock code (e.g., `"7203"`) |
| `turnover` | int \| None | Previous day trading value (yen) |
| `shares_outstanding` | int \| None | Calculated shares outstanding |

### Example

```python
>>> market.stocks_info()
      code     turnover  shares_outstanding
0     1301    123456000          50000000.0
1     1332   5678900000         200000000.0
...
4550  9999     98765000          10000000.0

>>> len(market.stocks_info())
4551
```

### Backend endpoint

`GET /api/stocks_info?date={today}` — Returns an array of stock info objects for all TSE securities.

---

## `market.stock_lists()`

Fetch curated stock lists maintained by BRiSK.

### Return type

`dict[str, list[str]]` — Maps list ID to a list of stock codes.

### Available lists

| List ID | Name | Description | Count |
|---|---|---|---|
| `ipo3month` | 直近IPO | IPOs from the last 3 months | ~28 |
| `nk225etf` | 日経225構成銘柄 | Nikkei 225 constituent stocks | 225 |

### Example

```python
>>> lists = market.stock_lists()
>>> lists.keys()
dict_keys(['ipo3month', 'nk225etf'])

>>> lists['nk225etf'][:5]
['1332', '1333', '1605', '1721', '1801']

>>> len(lists['nk225etf'])
225
```

### Backend endpoint

`GET /api/stock_lists?date={today}` — Returns list metadata with stock codes.

---

## `market.alerts(index_from=0, index_to=618)`

Fetch market condition alerts (場況速報). These are real-time events calculated independently from full order book data by BRiSK's servers.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `index_from` | `int` | `0` | Start index for pagination |
| `index_to` | `int` | `618` | End index (up to 619 events per page) |

### Return columns

| Column | Type | Description |
|---|---|---|
| `index` | int | Sequential event index |
| `code` | str | Stock code (empty for market-wide events like basket orders) |
| `kind` | float \| None | Event kind |
| `type` | int | Event type |
| `price` | float \| None | Price in yen (converted from `price10 / 10`) |
| `value` | float \| None | Value in yen (converted from `value10 / 10`) |
| `diff_bps` | int \| None | Price change in basis points from previous event |
| `time` | str | Event time with microsecond precision (`HH:MM:SS.μμμμμμ`) |

### Alert types

| Alert | Trigger condition |
|---|---|
| **NK225 Basket Orders** | Estimated 500M+ yen basket order detected |
| **Limit Up (ストップ高)** | Price reaches or approaches daily upper limit |
| **Limit Down (ストップ安)** | Price reaches or approaches daily lower limit |
| **Special Quote Update** | 30 seconds before anticipated special quote change |
| **Opening Volume Surge** | Pre-market volume forecast exceeds 2x previous day |
| **Large Orders** | Orders exceeding 1B yen or 10%+ of previous day volume (100M+ min) |
| **5-Min Volume Spike** | 5-min volume exceeds 100M yen AND recent 12-period maximum |
| **IPO Initial Price** | Newly listed stock establishes opening price |
| **High Lending Rate** | 逆日歩 at 0.1%+ (max 20 alerts) |

!!! note
    ETFs, ETNs, and foreign stocks are excluded from alerts.

### Example

```python
>>> market.alerts()
   index  code  kind  type   price        value  diff_bps             time
0      0  3655   1.0     6  2691.0  269100000.0       0.0  08:00:00.048598
1      1  7739   1.0     6  3615.0  180750000.0     -28.0  08:00:00.049639
2      2  7718   1.0     6  2197.0  219700000.0     -14.0  08:00:00.049727

>>> len(market.alerts())
618
```

### Backend endpoint

`GET /api/markets?date={today}&series=0&index_from={from}&index_to={to}` — Returns paginated market condition events.

---

## `market.schedule()`

Fetch the current trading session schedule and market status.

### Return type

`dict[str, Any]` — Schedule times in nanoseconds from midnight JST.

### Return keys

| Key | Type | Description | Time (JST) |
|---|---|---|---|
| `date` | str | Trading date | — |
| `status` | str | `"running"`, `"closed"`, or `"pre_open"` | — |
| `morning_pre_open` | int | Morning pre-open auction | 08:00 |
| `morning_open` | int | Morning session open | 09:00 |
| `morning_close` | int | Morning session close | 11:30 |
| `afternoon_pre_open` | int | Afternoon pre-open auction | 12:05 |
| `afternoon_open` | int | Afternoon session open | 12:30 |
| `afternoon_pre_close` | int | Afternoon pre-close | 15:25 |
| `afternoon_close` | int | Afternoon session close | 15:30 |

Times are in **nanoseconds from midnight JST**. To convert: `time_ns / 1_000_000_000 / 3600` = hours.

### Example

```python
>>> market.schedule()
{
    'date': '2026-03-11',
    'status': 'running',
    'morning_pre_open': 28800000000,   # 08:00
    'morning_open': 32400000000,       # 09:00
    'morning_close': 41400000000,      # 11:30
    'afternoon_pre_open': 43500000000, # 12:05
    'afternoon_open': 45000000000,     # 12:30
    'afternoon_pre_close': 55500000000, # 15:25
    'afternoon_close': 55800000000     # 15:30
}
```

### Backend endpoint

`GET /api/app/boot` — Returns session metadata including schedule, WebSocket URL, and data hashes.

---

## `market.watchlist()`

Fetch the user's saved watchlist stock codes from BRiSK.

### Return type

`list[str]` — List of stock code strings.

### Example

```python
>>> market.watchlist()
['7203', '6758', '9984']

>>> market.watchlist()  # empty if no watchlist configured
[]
```

### Backend endpoint

`GET /api/frontend/watchlist` — Returns compressed (zlib + base64) watchlist data. pybrisk decompresses and extracts stock codes automatically.
