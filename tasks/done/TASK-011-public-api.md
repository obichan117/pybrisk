# TASK-011: Public API & __init__.py

**Status**: todo
**Priority**: medium

## Description
Wire up `__init__.py` with clean public exports. Ensure the top-level API matches the spec.

## Acceptance Criteria
- [ ] `from pybrisk import Ticker, Market, login, config`
- [ ] `pb.login()`, `pb.Ticker()`, `pb.Market()` all work
- [ ] `__version__` exposed
- [ ] `__all__` defined
- [ ] No internal modules importable without `_internal`
