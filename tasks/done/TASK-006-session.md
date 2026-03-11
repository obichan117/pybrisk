# TASK-006: HTTP Session Layer

**Status**: todo
**Priority**: high

## Description
Implement `_internal/session.py` — the HTTP I/O layer using httpx. Handles cookie auth, rate limiting, and retry logic. Returns raw JSON/bytes, never parses.

## Acceptance Criteria
- [ ] `Session` class wrapping `httpx.Client`
- [ ] Cookie-based authentication (loads from cached cookies file)
- [ ] Rate limiting (configurable, default 1 req/sec)
- [ ] Auto-detect session expiry → raise `SessionExpiredError`
- [ ] `get(path, params)` → raw JSON dict
- [ ] `post(path, params, json)` → raw JSON dict
- [ ] Unit tests with mocked httpx responses
