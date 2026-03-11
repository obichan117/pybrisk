# TASK-007: API Client

**Status**: todo
**Priority**: high

## Description
Implement `_internal/client.py` — orchestration layer. Calls session for HTTP, validates through Pydantic models, returns typed objects.

## Acceptance Criteria
- [ ] `Client` class using `Session` and `Endpoint` definitions
- [ ] `fetch(endpoint, **params)` → Pydantic model instance
- [ ] Path parameter substitution (`{code}` → actual stock code)
- [ ] Query parameter assembly
- [ ] Boot sequence: `frontend/boot` → `app/boot` (automatic on first request)
- [ ] Token management (stores tokens from boot responses internally)
- [ ] Unit tests with mocked session
