# TASK-004: Endpoint Definitions

**Status**: todo
**Priority**: high

## Description
Implement `_internal/endpoints.py` — declarative endpoint definitions as frozen dataclasses. Each endpoint specifies path, HTTP method, query params, and response model.

## Acceptance Criteria
- [ ] `Endpoint` frozen dataclass: `path`, `method`, `params`, `model`
- [ ] All JSON endpoints defined: `BOOT`, `APP_BOOT`, `MARKET_TOKEN`, `OHLC`, `JSFC`, `STOCKS_INFO`, `STOCK_LISTS`, `MARKETS`, `WATCHLIST`
- [ ] Base URL constant: `https://sbi.brisk.jp`
- [ ] Path parameters supported (e.g., `{code}` in `/api/ohlc/{code}`)

## Notes
See `docs/research/api-endpoints.md` for full endpoint list.
