# TASK-010: Market Class

**Status**: todo
**Priority**: high

## Description
Implement `market.py` — the user-facing `Market` class for market-wide data.

## Acceptance Criteria
- [ ] `Market()` constructor
- [ ] `market.stocks_info()` → pandas DataFrame (~3800 stocks: code, turnover, shares_outstanding)
- [ ] `market.stock_lists()` → dict[str, list[str]] (list_id → stock codes)
- [ ] `market.alerts()` → pandas DataFrame (market condition events)
- [ ] `market.alerts(index_from=0, index_to=100)` → paginated
- [ ] `market.schedule()` → dict (session times)
- [ ] `market.watchlist()` → list[str] (user's saved stock codes, zlib decompression)
- [ ] Integration test with real API
