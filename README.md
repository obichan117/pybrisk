# pybrisk

[![PyPI version](https://badge.fury.io/py/pybrisk.svg)](https://badge.fury.io/py/pybrisk)
[![Python versions](https://img.shields.io/pypi/pyversions/pybrisk.svg)](https://pypi.org/project/pybrisk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://obichan117.github.io/pybrisk/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/obichan117/pybrisk/blob/main/examples/quickstart.ipynb)

Python client for [SBI BRiSK](https://www.brisk.jp/) market data. Wraps BRiSK's internal REST API to provide programmatic access to OHLC candles, margin lending data, market alerts, and stock universe information for all Tokyo Stock Exchange (TSE) listed securities.

## What is BRiSK?

BRiSK is a browser-based, real-time full order book viewer developed by [ArGentumCode](https://www.argentumcode.co.jp/) and offered through SBI Securities (and other Japanese brokers). It provides full-depth order book data, microsecond-precision tick data, and market condition alerts for all TSE-listed stocks.

**pybrisk** reverse-engineers BRiSK's internal JSON API so you can access this data from Python without browser automation.

## Installation

```bash
pip install pybrisk
```

For automated browser login (optional):

```bash
pip install 'pybrisk[browser]'
```

## Quick Start

```python
import pybrisk as pb

# Authenticate — see "Authentication" below
pb.login(cookies={"session_xxx": "v2.local.xxx"})

# Per-stock data
ticker = pb.Ticker("7203")        # Toyota
df = ticker.ohlc()                # Daily OHLC candles (~116 rows, ~6 months)
df = ticker.ohlc("5m")            # 5-minute candles (~131 rows, 3 trading days)
margin = ticker.jsfc()            # Margin lending data (~245 rows, ~1 year)

# Market-wide data
market = pb.Market()
info = market.stocks_info()       # All ~4,500 TSE stocks
lists = market.stock_lists()      # Nikkei 225 constituents, recent IPOs
alerts = market.alerts()          # Market condition events (~618 per page)
schedule = market.schedule()      # Trading session times
watchlist = market.watchlist()    # Your saved stock codes
```

## Authentication

BRiSK uses cookie-based authentication inherited from the SBI Securities session. pybrisk supports three methods:

### Method 1: Manual cookies (recommended)

Extract cookies from your browser (DevTools > Application > Cookies > `sbi.brisk.jp`) and pass them directly:

```python
pb.login(cookies={"session_bfaf77a2": "v2.local.BvaDKm5..."})
```

### Method 2: Automatic extraction from Chrome

If you have BRiSK open in Chrome, pybrisk can extract cookies automatically using [pycookiecheat](https://github.com/n8henrie/pycookiecheat):

```python
from pycookiecheat import chrome_cookies
import pybrisk as pb

cookies = chrome_cookies("https://sbi.brisk.jp")
pb.login(cookies=cookies)
```

### Method 3: Browser automation (requires Playwright)

Opens a browser, logs into SBI Securities, navigates to BRiSK, and extracts cookies automatically:

```python
pb.login("your_username", "your_password")
```

Requires `pip install 'pybrisk[browser]'`. Cookies are cached to `~/.pybrisk/cookies.json` for reuse.

### Configuration file

Credentials can also be set via environment variables or TOML config:

```bash
export BRISK_USERNAME=your_username
export BRISK_PASSWORD=your_password
```

Or `~/.pybrisk/config.toml`:

```toml
[auth]
username = "your_username"
password = "your_password"

[settings]
timeout = 30
rate_limit = 1.0
```

## API Reference

### `pb.Ticker(code)`

Access per-stock data. Code is a TSE stock code (e.g., `"7203"` for Toyota, `"6758"` for Sony).

#### `ticker.ohlc(interval=None)` → `pd.DataFrame`

Fetch OHLC (Open/High/Low/Close) candle data.

| Interval | Description | Rows | History |
|---|---|---|---|
| `"1d"` (default) | Daily candles | ~116 | ~6 months |
| `"5m"` | 5-minute candles | ~131 | 3 trading days |
| `"1w"` | Weekly candles | ~180 | ~3.5 years |
| `"1mo"` | Monthly candles | ~144 | ~12 years |

**Columns (daily):** `date`, `open`, `high`, `low`, `close`, `turnover`

```python
>>> ticker = pb.Ticker("7203")
>>> ticker.ohlc()
         date    open    high     low   close     turnover
0  2025-09-16  2900.0  2944.0  2895.5  2934.5  64755932500
1  2025-09-17  2930.0  2954.5  2919.0  2950.5  55586997350
2  2025-09-18  2966.5  2972.0  2928.0  2940.5  60581792600

>>> ticker.ohlc("5m")  # 5-minute candles (includes 'index' column for intraday bar number)
         date  index    open    high     low   close    turnover
0  2026-03-09      0  2600.0  2610.0  2595.0  2605.0  1200000000
```

**Columns by interval:**

- `"1d"`: `date`, `open`, `high`, `low`, `close`, `turnover`
- `"5m"`: `date`, `index`, `open`, `high`, `low`, `close`, `turnover`
- `"1w"`: `year`, `week`, `open`, `high`, `low`, `close`, `turnover`
- `"1mo"`: `year`, `month`, `open`, `high`, `low`, `close`, `turnover`

Prices are in yen (float — some stocks have half-yen increments like 2895.5). Turnover is in yen (integer).

#### `ticker.jsfc(count=365)` → `pd.DataFrame`

Fetch margin lending/borrowing data from JSFC (Japan Securities Finance Corporation).

| Parameter | Default | Description |
|---|---|---|
| `count` | 365 | Number of trading days to fetch |

**Columns:**

| Column | Description |
|---|---|
| `date` | Trading date |
| `long_shares` | Confirmed margin long shares (貸借融資残高) |
| `short_shares` | Confirmed margin short shares (貸借貸株残高) |
| `preliminary_long` | Preliminary long shares (速報融資残高) |
| `preliminary_short` | Preliminary short shares (速報貸株残高) |
| `standardized_long` | Standardized margin long (制度信用融資) |
| `standardized_short` | Standardized margin short (制度信用貸株) |
| `borrowing_fee` | Stock borrowing fee / 逆日歩 (yen) |
| `borrowing_fee_pct` | Borrowing fee as percentage of price |
| `borrowing_fee_days` | Number of days the fee applies |
| `borrowing_fee_max` | Maximum borrowing fee (yen) |

```python
>>> ticker.jsfc(count=30)
         date  long_shares  short_shares  ...  borrowing_fee  borrowing_fee_pct
0  2025-03-11     819600.0       77400.0  ...            NaN                NaN
1  2025-03-12     768000.0      111200.0  ...            NaN                NaN
```

---

### `pb.Market()`

Access market-wide data for all TSE-listed securities.

#### `market.stocks_info()` → `pd.DataFrame`

Fetch turnover and shares outstanding for all TSE stocks (~4,500 securities).

**Columns:** `code`, `turnover`, `shares_outstanding`

```python
>>> market = pb.Market()
>>> market.stocks_info()
      code     turnover  shares_outstanding
0     1301    123456000          50000000.0
1     1332   5678900000         200000000.0
...
4550  9999     98765000          10000000.0
```

#### `market.stock_lists()` → `dict[str, list[str]]`

Fetch curated stock lists. Returns a dict mapping list ID to stock codes.

| List ID | Description | Count |
|---|---|---|
| `ipo3month` | Recent IPOs (last 3 months) | ~28 |
| `nk225etf` | Nikkei 225 constituent stocks | 225 |

```python
>>> market.stock_lists()
{
    'ipo3month': ['509A', '511A', ...],
    'nk225etf': ['1332', '1333', ..., '9984']
}
```

#### `market.alerts(index_from=0, index_to=618)` → `pd.DataFrame`

Fetch market condition events (場況速報). These are real-time alerts calculated from full order book data.

| Parameter | Default | Description |
|---|---|---|
| `index_from` | 0 | Start index for pagination |
| `index_to` | 618 | End index for pagination |

**Columns:** `index`, `code`, `kind`, `type`, `price`, `value`, `diff_bps`, `time`

Alert types include:
- Nikkei 225 basket orders (estimated 500M+ yen)
- Limit up/down (approaching or executed)
- Special quote updates (30-second advance notice)
- Opening volume surges (2x previous day)
- Large orders (1B+ yen or 10%+ of previous day volume)
- 5-minute volume spikes
- IPO initial prices
- High lending rates (逆日歩 0.1%+)

```python
>>> market.alerts()
   index  code  kind  type   price        value  diff_bps             time
0      0  3655   1.0     6  2691.0  269100000.0       0.0  08:00:00.048598
1      1  7739   1.0     6  3615.0  180750000.0     -28.0  08:00:00.049639
```

Times are microsecond-precision strings. Prices are in yen. Values are in yen. `diff_bps` is the price change in basis points from the previous event.

#### `market.schedule()` → `dict`

Fetch the current trading session schedule and market status.

```python
>>> market.schedule()
{
    'date': '2026-03-11',
    'status': 'running',              # or 'closed', 'pre_open'
    'morning_pre_open': 28800000000,  # 08:00 JST (nanoseconds from midnight)
    'morning_open': 32400000000,      # 09:00 JST
    'morning_close': 41400000000,     # 11:30 JST
    'afternoon_pre_open': 43500000000, # 12:05 JST
    'afternoon_open': 45000000000,    # 12:30 JST
    'afternoon_pre_close': 55500000000, # 15:25 JST
    'afternoon_close': 55800000000    # 15:30 JST
}
```

#### `market.watchlist()` → `list[str]`

Fetch the user's saved watchlist stock codes from BRiSK.

```python
>>> market.watchlist()
['7203', '6758', '9984']
```

---

### Configuration

```python
pb.config.timeout = 60          # HTTP timeout in seconds (default: 30)
pb.config.cache_ttl = 7200      # Cache TTL in seconds (default: 3600)
pb.config.rate_limit = 2.0      # Max requests per second (default: 1.0)
```

### Exceptions

```python
from pybrisk import (
    PyBriskError,           # Base exception
    AuthenticationError,    # Login failed
    SessionExpiredError,    # Cookies expired, re-login needed
    APIError,               # HTTP error (has .status_code)
    NotFoundError,          # 404 — invalid stock code
    RateLimitError,         # 429 — too many requests
    ConfigurationError,     # Missing credentials
)
```

## Backend API Endpoints

pybrisk wraps the following BRiSK REST API endpoints:

| Endpoint | Method | Description | Used by |
|---|---|---|---|
| `/api/frontend/boot` | GET | Session bootstrap — returns user ID, API token, CSRF token | `login()` (internal) |
| `/api/app/boot` | GET | App bootstrap — trading date, session status, schedule, WebSocket URL | `Market.schedule()` |
| `/api/ohlc/{code}` | GET | OHLC candles (5min/daily/weekly/monthly) for a stock | `Ticker.ohlc()` |
| `/api/jsfc/{code}` | GET | Margin lending data from JSFC | `Ticker.jsfc()` |
| `/api/stocks_info` | GET | Turnover + shares outstanding for all stocks | `Market.stocks_info()` |
| `/api/stock_lists` | GET | Curated lists (IPO, NK225) | `Market.stock_lists()` |
| `/api/markets` | GET | Market condition alerts (paginated) | `Market.alerts()` |
| `/api/frontend/watchlist` | GET | User's watchlist (zlib+base64 compressed) | `Market.watchlist()` |
| `/api/app/market-token` | GET | PASETO token for real-time data | (future: WebSocket) |

Authentication flow: cookie → `frontend/boot` → `api_token` → `Authorization: Bearer` header on all subsequent requests.

Full API documentation in [`docs/research/`](docs/research/overview.md).

## Requirements

- Python 3.10+
- Active SBI Securities account with BRiSK (全板) subscription (330 yen/month, or free with qualifying account)
- BRiSK must have been opened at least once (to establish the session)
- Service hours: 8:00 AM – 3:50 PM JST (aligned with TSE trading hours)

## License

MIT
