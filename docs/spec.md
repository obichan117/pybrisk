# pybrisk — Project Specification

## Problem Statement

There is no Python library to access SBI BRiSK's market data. BRiSK provides full-depth order book, OHLC, margin lending, and market alert data for all TSE-listed securities — but only through a browser UI. pybrisk wraps BRiSK's hidden REST API so Python users can fetch this data programmatically with a yfinance-style interface.

## Target Users

- Japanese equity traders/analysts who use SBI Securities
- Quant developers building TSE market data pipelines
- Anyone with a BRiSK subscription (330 yen/month or free with qualifying account)

## Core Features (MVP)

### Authentication
- **Automated login**: Playwright opens SBI Securities → navigates to BRiSK → extracts session cookies
- **Cookie caching**: Cookies saved to disk, reused until session expires
- **Manual cookie mode**: Users can provide cookies directly (no Playwright needed)

### Per-Stock Data (`Ticker`)
- **OHLC candles**: 5-minute, daily, weekly, monthly — via `/api/ohlc/{code}`
- **Margin lending (JSFC)**: 逆日歩, lending/borrowing shares — via `/api/jsfc/{code}`

### Market-Wide Data (`Market`)
- **Stock info**: Turnover + shares outstanding for all ~3800 TSE stocks — via `/api/stocks_info`
- **Stock lists**: Curated lists (IPO, NK225 constituents) — via `/api/stock_lists`
- **Market alerts**: Basket orders, limit up/down, volume surges, etc. — via `/api/markets`
- **Watchlist**: User's saved watchlist (zlib+base64 decompression) — via `/api/frontend/watchlist`
- **Trading schedule**: Session times, market status — via `/api/app/boot`

### Configuration
- **Credentials**: Environment variables (`BRISK_USERNAME`, `BRISK_PASSWORD`) or TOML file (`~/.pybrisk/config.toml`)
- **Settings**: Timeout, rate limiting, cache TTL — configurable at runtime

## Future Features (Post-MVP)

- **TFX futures data**: gRPC-Connect API at `tfx-api.brisk.jp` (Protobuf)
- **Binary data decoding**: Master file, snapshot, delta updates (reverse engineering needed)
- **WebSocket streaming**: Real-time market data via `wss://sbi.brisk.jp/realtime/0`
- **Multi-ticker download**: `pb.download(["7203", "6758"])` batch fetching

## Tech Stack

| Dependency | Purpose | Required |
|---|---|---|
| `httpx` | HTTP client (async-ready, HTTP/2) | Yes |
| `pydantic>=2.0` | Response parsing & validation | Yes |
| `pandas>=2.0` | DataFrame output | Yes |
| `playwright` | Browser login automation | Optional |

Dev dependencies: `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `mkdocs-material`

Build: `hatchling` via `pyproject.toml`, Python 3.10+

## Architecture

```
pybrisk/
├── __init__.py              # Exports: Ticker, Market, login, config
├── ticker.py                # Ticker("7203") — per-stock: ohlc, jsfc
├── market.py                # Market() — market-wide: alerts, stocks_info, lists
├── _internal/
│   ├── __init__.py
│   ├── auth.py              # Playwright login → SBI → BRiSK → extract & cache cookies
│   ├── session.py           # HTTP I/O (cookies, rate limiting, retry)
│   ├── client.py            # API orchestration (calls session, returns models)
│   ├── config.py            # Config loading: env → toml → defaults
│   ├── endpoints.py         # Declarative endpoint definitions (frozen dataclasses)
│   ├── exceptions.py        # PyBriskError hierarchy
│   └── models/
│       ├── __init__.py
│       ├── ohlc.py          # OHLCBar, OHLCResponse
│       ├── stock.py         # StockInfo, StockList
│       ├── margin.py        # JSFCData
│       └── market.py        # MarketCondition, MarketAlert
```

### Dependency Direction (top → bottom)

```
ticker.py / market.py      ← user-facing
    ↓
_internal/client.py        ← orchestration (fetch + parse)
    ↓
_internal/session.py       ← HTTP I/O (raw JSON/bytes)
    ↓
_internal/auth.py          ← cookie acquisition (Playwright, optional)
```

### Data Flow

```
login("user", "pass")
  → Playwright opens SBI → navigates to BRiSK
  → extracts cookies → caches to ~/.pybrisk/cookies.json

Ticker("7203").ohlc()
  → client.fetch(endpoints.OHLC, code="7203")
  → session.get("/api/ohlc/7203?date=2026-03-11", cookies=cached)
  → raw JSON response
  → OHLCResponse.model_validate(raw)
  → convert to pandas DataFrame
```

### Config Taxonomy

| Type | Location | Examples |
|---|---|---|
| User settings | `~/.pybrisk/config.toml` + env vars | Credentials, cache dir, timeout |
| Internal constants | `_internal/endpoints.py` | Base URL, endpoint paths, param names |
| Hardcoded defaults | `_internal/config.py` | Rate limit (1 req/sec), cache TTL (3600s) |

## User API

```python
import pybrisk as pb

# --- Auth ---
pb.login("username", "password")     # Playwright login, cookies cached
# or
pb.login(cookies={...})              # Manual cookies, no browser needed

# --- Per-Stock ---
ticker = pb.Ticker("7203")
ohlc = ticker.ohlc()                 # DataFrame: 5min/daily/weekly/monthly
jsfc = ticker.jsfc()                 # DataFrame: margin lending data
jsfc = ticker.jsfc(count=30)         # Last 30 trading days

# --- Market-Wide ---
market = pb.Market()
info = market.stocks_info()          # DataFrame: all ~3800 TSE stocks
lists = market.stock_lists()         # dict[str, list[str]]: IPO, NK225, etc.
alerts = market.alerts()             # DataFrame: market conditions
schedule = market.schedule()         # dict: session times
watchlist = market.watchlist()       # list[str]: user's saved codes

# --- Config ---
pb.config.timeout = 30
pb.config.cache_ttl = 3600
```

## Exception Hierarchy

```
PyBriskError
├── AuthenticationError        # Login failed, session expired
├── APIError(status_code)      # HTTP error from BRiSK
│   ├── NotFoundError(404)     # Invalid stock code
│   └── RateLimitError(429)    # Too many requests
├── SessionExpiredError        # Cookies expired, re-login needed
└── ConfigurationError         # Missing credentials
```

## Testing Strategy

- **Unit tests**: Mock HTTP responses, test parsing/validation
- **Integration tests**: Real API calls (marked, excluded by default)
- **Fixtures**: Saved JSON responses from HAR capture in `tests/fixtures/`
- CI: `pytest --ignore=tests/integration/`, `ruff check`, `mypy`

## Project Structure (full)

```
pybrisk/
├── pyproject.toml
├── README.md
├── LICENSE
├── docs/
│   ├── research/              # Reverse-engineering findings
│   │   ├── overview.md
│   │   ├── api-endpoints.md
│   │   ├── authentication.md
│   │   ├── data-schemas.md
│   │   └── data-flow.md
│   └── mkdocs/                # User documentation
├── examples/
│   └── quickstart.ipynb
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── src/
    └── pybrisk/
        ├── __init__.py
        ├── ticker.py
        ├── market.py
        └── _internal/
            ├── __init__.py
            ├── auth.py
            ├── session.py
            ├── client.py
            ├── config.py
            ├── endpoints.py
            ├── exceptions.py
            └── models/
                ├── __init__.py
                ├── ohlc.py
                ├── stock.py
                ├── margin.py
                └── market.py
```

Uses `src/` layout (hatchling standard).
