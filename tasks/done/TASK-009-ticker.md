# TASK-009: Ticker Class

**Status**: todo
**Priority**: high

## Description
Implement `ticker.py` — the user-facing `Ticker` class for per-stock data access.

## Acceptance Criteria
- [ ] `Ticker("7203")` constructor (validates stock code)
- [ ] `ticker.ohlc()` → pandas DataFrame (5min, daily, weekly, monthly candles)
- [ ] `ticker.ohlc(interval="5m")` / `"1d"` / `"1w"` / `"1mo"` for specific timeframes
- [ ] `ticker.jsfc()` → pandas DataFrame (margin lending data)
- [ ] `ticker.jsfc(count=30)` → last N trading days
- [ ] DataFrame column names are clean English (open, high, low, close, volume, turnover)
- [ ] Integration test with real API
