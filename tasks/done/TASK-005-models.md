# TASK-005: Pydantic Models

**Status**: todo
**Priority**: high

## Description
Implement `_internal/models/` — Pydantic v2 models for all JSON API responses.

## Acceptance Criteria
- [ ] `ohlc.py`: `OHLCBar` (5min/daily/weekly/monthly variants), `OHLCResponse`
- [ ] `stock.py`: `StockInfo`, `StockList`, `StockListsResponse`
- [ ] `margin.py`: `JSFCEntry`, `JSFCResponse`
- [ ] `market.py`: `MarketCondition`, `MarketsResponse`
- [ ] All models handle the actual JSON shapes from `docs/research/data-schemas.md`
- [ ] `price10` → float conversion (26910 → 2691.0)
- [ ] Unit tests with fixture data from HAR capture

## Notes
See `docs/research/data-schemas.md` for all response schemas.
