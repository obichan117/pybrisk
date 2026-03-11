# TASK-003: Exception Hierarchy

**Status**: todo
**Priority**: high

## Description
Implement `_internal/exceptions.py` — the full error hierarchy.

## Acceptance Criteria
- [ ] `PyBriskError` base
- [ ] `AuthenticationError` — login failed, invalid credentials
- [ ] `SessionExpiredError` — cookies expired, re-login needed
- [ ] `APIError(status_code, message)` — generic HTTP error
- [ ] `NotFoundError` — 404, invalid stock code
- [ ] `RateLimitError` — 429
- [ ] `ConfigurationError` — missing credentials
- [ ] All exported from `pybrisk` top level
