# TASK-008: Authentication (Playwright Login)

**Status**: todo
**Priority**: high

## Description
Implement `_internal/auth.py` — automates the SBI Securities login flow via Playwright, navigates to BRiSK, extracts session cookies, and caches them to disk.

## Acceptance Criteria
- [ ] `login(username, password)` → opens browser, logs into SBI, launches BRiSK
- [ ] `login(cookies={...})` → manual cookie mode, no browser
- [ ] Cookies saved to `~/.pybrisk/cookies.json`
- [ ] Cookies loaded from disk on subsequent calls (skip browser if valid)
- [ ] Playwright imported lazily (optional dependency)
- [ ] Clear error message if Playwright not installed
- [ ] Handles session expiry detection

## Notes
Login flow: sbisec.co.jp → fill credentials → navigate to 全板/BRiSK → sbi.brisk.jp opens → extract cookies from browser context.
Requires research on exact SBI login page selectors (separate investigation during implementation).
