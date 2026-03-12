# Configuration

pybrisk configuration follows a priority chain: **environment variables > TOML file > defaults**.

## Runtime settings

```python
import pybrisk as pb

pb.config.timeout = 60          # HTTP timeout in seconds (default: 30)
pb.config.cache_ttl = 7200      # Cache TTL in seconds (default: 3600)
pb.config.rate_limit = 2.0      # Max requests per second (default: 1.0)
pb.config.username = "user"     # SBI Securities username
pb.config.password = "pass"     # SBI Securities password
```

## Environment variables

| Variable | Description |
|---|---|
| `BRISK_USERNAME` | SBI Securities username |
| `BRISK_PASSWORD` | SBI Securities password |

## TOML config file

Location: `~/.pybrisk/config.toml`

```toml
[auth]
username = "your_username"
password = "your_password"

[settings]
timeout = 30        # HTTP timeout (seconds)
cache_ttl = 3600    # Cache TTL (seconds)
rate_limit = 1.0    # Max requests per second
```

## Cookie storage

Session cookies are cached at `~/.pybrisk/cookies.json`. This file is created automatically after `pb.login()` and reused on subsequent calls.

To force a fresh login, delete this file or call `pb.login()` with explicit credentials.

## Exceptions

All exceptions inherit from `PyBriskError`:

```python
from pybrisk import (
    PyBriskError,           # Base — catch all pybrisk errors
    AuthenticationError,    # Login failed or Playwright not installed
    SessionExpiredError,    # Cookies expired (HTTP 401/403) — re-login needed
    APIError,               # Generic HTTP error (has .status_code attribute)
    NotFoundError,          # HTTP 404 — invalid stock code
    RateLimitError,         # HTTP 429 — too many requests
    ConfigurationError,     # Missing credentials or invalid config
)
```

Example error handling:

```python
try:
    df = pb.Ticker("9999").ohlc()
except pb.SessionExpiredError:
    pb.login(cookies=fresh_cookies)
    df = pb.Ticker("9999").ohlc()
except pb.NotFoundError:
    print("Invalid stock code")
```
