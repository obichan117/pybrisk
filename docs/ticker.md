# Ticker API

The `Ticker` class provides per-stock data access. Create one by passing a TSE stock code:

```python
import pybrisk as pb

ticker = pb.Ticker("7203")  # Toyota Motor
ticker = pb.Ticker("6758")  # Sony Group
ticker = pb.Ticker("9984")  # SoftBank Group
```

---

## `ticker.ohlc(interval=None)`

Fetch OHLC (Open/High/Low/Close) candle data. Returns a pandas DataFrame.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `interval` | `str \| None` | `None` (daily) | `"5m"`, `"1d"`, `"1w"`, or `"1mo"` |

### Intervals

| Interval | Description | Typical rows | History depth |
|---|---|---|---|
| `"1d"` (default) | Daily candles | ~116 | ~6 months |
| `"5m"` | 5-minute intraday candles | ~131 | 3 trading days |
| `"1w"` | Weekly candles | ~180 | ~3.5 years |
| `"1mo"` | Monthly candles | ~144 | ~12 years |

### Return columns

**Daily (`"1d"`):**

| Column | Type | Description |
|---|---|---|
| `date` | str | Trading date (`YYYY-MM-DD`) |
| `open` | float | Opening price (yen) |
| `high` | float | High price (yen) |
| `low` | float | Low price (yen) |
| `close` | float | Closing price (yen) |
| `turnover` | int | Trading value (yen) |

**5-minute (`"5m"`):**

Same as daily plus:

| Column | Type | Description |
|---|---|---|
| `index` | int | Bar number within the trading day |

**Weekly (`"1w"`):**

| Column | Type | Description |
|---|---|---|
| `year` | int | Year |
| `week` | int | ISO week number |
| `open` | float | Opening price (yen) |
| `high` | float | High price (yen) |
| `low` | float | Low price (yen) |
| `close` | float | Closing price (yen) |
| `turnover` | int | Trading value (yen) |

**Monthly (`"1mo"`):**

| Column | Type | Description |
|---|---|---|
| `year` | int | Year |
| `month` | int | Month (1–12) |
| `open` | float | Opening price (yen) |
| `high` | float | High price (yen) |
| `low` | float | Low price (yen) |
| `close` | float | Closing price (yen) |
| `turnover` | int | Trading value (yen) |

### Example

```python
>>> ticker = pb.Ticker("7203")

>>> ticker.ohlc()
         date    open    high     low   close     turnover
0  2025-09-16  2900.0  2944.0  2895.5  2934.5  64755932500
1  2025-09-17  2930.0  2954.5  2919.0  2950.5  55586997350
2  2025-09-18  2966.5  2972.0  2928.0  2940.5  60581792600

>>> ticker.ohlc("5m")
         date  index    open    high     low   close    turnover
0  2026-03-09      0  2600.0  2610.0  2595.0  2605.0  1200000000

>>> ticker.ohlc("1mo")
   year  month    open    high     low   close      turnover
0  2014      4   964.0   968.0   757.0   768.0   8975884900
```

!!! note
    Some stocks have half-yen price increments (e.g., 2895.5 yen). Prices are always `float`.

### Backend endpoint

`GET /api/ohlc/{code}?date={today}` — Returns all four timeframes in a single response. pybrisk filters by your requested interval.

---

## `ticker.jsfc(count=365)`

Fetch margin lending/borrowing data from JSFC (Japan Securities Finance Corporation / 日本証券金融).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `count` | `int` | `365` | Number of trading days to fetch |

### Return columns

| Column | Type | Description | Japanese |
|---|---|---|---|
| `date` | str | Trading date | 日付 |
| `long_shares` | float | Confirmed margin long shares | 貸借融資残高 (確報) |
| `short_shares` | float | Confirmed margin short shares | 貸借貸株残高 (確報) |
| `preliminary_long` | float | Preliminary long shares | 融資残高 (速報) |
| `preliminary_short` | float | Preliminary short shares | 貸株残高 (速報) |
| `standardized_long` | float \| None | Standardized margin long | 制度信用融資 |
| `standardized_short` | float \| None | Standardized margin short | 制度信用貸株 |
| `borrowing_fee` | float \| None | Stock borrowing fee (yen) | 逆日歩 |
| `borrowing_fee_pct` | float \| None | Borrowing fee as % of price | 逆日歩率 |
| `borrowing_fee_days` | int \| None | Days the fee applies | 日数 |
| `borrowing_fee_max` | float \| None | Maximum borrowing fee (yen) | 最高料率 |

### Example

```python
>>> ticker = pb.Ticker("7203")
>>> ticker.jsfc(count=30)
         date  long_shares  short_shares  ...  borrowing_fee
0  2026-02-01     819600.0       77400.0  ...            NaN
1  2026-02-03     768000.0      111200.0  ...            NaN
```

### Backend endpoint

`GET /api/jsfc/{code}?count={count}` — Returns a map of date → margin data.
