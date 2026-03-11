# TASK-002: Configuration System

**Status**: todo
**Priority**: high

## Description
Implement `_internal/config.py` — loads credentials and settings from environment variables → TOML file → hardcoded defaults.

## Acceptance Criteria
- [ ] `Config` class with: `username`, `password`, `timeout`, `cache_ttl`, `cookies_path`
- [ ] Loads from `BRISK_USERNAME`/`BRISK_PASSWORD` env vars
- [ ] Falls back to `~/.pybrisk/config.toml`
- [ ] Sensible defaults (timeout=30, cache_ttl=3600)
- [ ] Runtime-modifiable via `pb.config.timeout = 60`
- [ ] Unit tests for all loading strategies
