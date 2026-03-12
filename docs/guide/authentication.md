# Authentication

BRiSK uses cookie-based authentication inherited from the SBI Securities session. You need to establish a session first, then pass the cookies to pybrisk.

## Method 1: Manual cookies (recommended)

Extract cookies from your browser:

1. Open BRiSK in Chrome (`sbi.brisk.jp`)
2. Open DevTools (`Cmd+Option+I`)
3. Go to **Application** tab → **Cookies** → `https://sbi.brisk.jp`
4. Copy the cookie name and value (typically `session_xxxxxxxx` with a `v2.local.` value)

```python
import pybrisk as pb

pb.login(cookies={"session_bfaf77a2": "v2.local.BvaDKm5..."})
```

## Method 2: Automatic extraction from Chrome

If BRiSK is open in Chrome, use [pycookiecheat](https://github.com/n8henrie/pycookiecheat) to extract cookies automatically:

```bash
pip install pycookiecheat
```

```python
from pycookiecheat import chrome_cookies
import pybrisk as pb

cookies = chrome_cookies("https://sbi.brisk.jp")
pb.login(cookies=cookies)
```

The first time you run this, macOS will ask for Keychain access — click **"Always Allow"**.

## Method 3: Browser automation

Opens a real browser, logs into SBI Securities, navigates to BRiSK, and extracts cookies automatically:

```bash
pip install 'pybrisk[browser]'
playwright install chromium
```

```python
pb.login("your_username", "your_password")
```

Cookies are cached to `~/.pybrisk/cookies.json` so you don't re-login every time.

## Environment variables

```bash
export BRISK_USERNAME=your_username
export BRISK_PASSWORD=your_password
```

Then just call `pb.login()` with no arguments.

## Config file

Create `~/.pybrisk/config.toml`:

```toml
[auth]
username = "your_username"
password = "your_password"

[settings]
timeout = 30
rate_limit = 1.0
```

## How authentication works internally

pybrisk uses a two-phase authentication flow:

1. **Cookie auth** → `GET /api/frontend/boot` — sends the session cookie, receives an `api_token` (PASETO v2.local encrypted token)
2. **Bearer auth** → All subsequent requests send `Authorization: Bearer {api_token}` header

This happens automatically on the first API call after `login()`.
