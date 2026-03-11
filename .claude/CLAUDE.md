# pybrisk

Python client for SBI BRiSK market data (TSE full order book, OHLC, margin lending, market alerts).

## Quick Start

```bash
uv sync --all-extras
uv run pytest --tb=short
uv run mkdocs build --strict -f mkdocs.yml -d site
uv run ruff check src/ tests/
uv run mypy src/
```

## Architecture

```
src/pybrisk/
├── __init__.py          # Public API: Ticker, Market, login, config
├── ticker.py            # Per-stock data (ohlc, jsfc)
├── market.py            # Market-wide data (alerts, stocks_info, stock_lists)
└── _internal/
    ├── auth.py          # Playwright login → cookie extraction
    ├── session.py       # HTTP I/O (httpx, cookies, rate limiting)
    ├── client.py        # API orchestration (fetch → parse)
    ├── config.py        # Config loading (env → toml → defaults)
    ├── endpoints.py     # Declarative endpoint definitions
    ├── exceptions.py    # Error hierarchy
    └── models/          # Pydantic response models
        ├── ohlc.py      # OHLCBar, OHLCResponse
        ├── stock.py     # StockInfo, StockList
        ├── margin.py    # JSFCData
        └── market.py    # MarketCondition
```

## Key Files

- `docs/research/` — Reverse-engineered API documentation
- `docs/spec.md` — Project specification
- `tasks/` — Task tracking (todo/in-progress/done)

## API Base URL

`https://sbi.brisk.jp` — All endpoints under `/api/`

## Dependency Direction

`ticker.py/market.py` → `client.py` → `session.py` → `auth.py`
