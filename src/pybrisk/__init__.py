"""pybrisk — Python client for SBI BRiSK market data."""

from __future__ import annotations

from pybrisk._internal.client import Client
from pybrisk._internal.config import Config
from pybrisk._internal.exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    PyBriskError,
    RateLimitError,
    SessionExpiredError,
)
from pybrisk._internal.session import Session
from pybrisk.market import Market as _Market
from pybrisk.ticker import Ticker as _Ticker

__version__ = "0.1.0"
__all__ = [
    "APIError",
    "AuthenticationError",
    "ConfigurationError",
    "Market",
    "NotFoundError",
    "PyBriskError",
    "RateLimitError",
    "SessionExpiredError",
    "Ticker",
    "config",
    "login",
]

config = Config()
_session = Session(config)
_client = Client(_session)


def login(
    username: str | None = None,
    password: str | None = None,
    *,
    cookies: dict[str, str] | None = None,
) -> None:
    """Authenticate with BRiSK.

    Either provide username/password (opens browser via Playwright)
    or provide cookies directly.

    Args:
        username: SBI Securities username. Falls back to config.
        password: SBI Securities password. Falls back to config.
        cookies: Pre-extracted cookies dict. Skips browser login.
    """
    if cookies is not None:
        from pybrisk._internal.auth import login_with_cookies

        login_with_cookies(cookies, _session)
        return

    if username is not None:
        config.username = username
    if password is not None:
        config.password = password

    # Try loading cached cookies first
    _session.load_cookies()
    if _session.has_cookies:
        return

    from pybrisk._internal.auth import login_with_browser

    login_with_browser(config, _session)


def Ticker(code: str) -> _Ticker:
    """Create a Ticker for per-stock data access.

    Args:
        code: Stock code (e.g., "7203" for Toyota).

    Returns:
        Ticker instance.
    """
    return _Ticker(code, client=_client)


def Market() -> _Market:
    """Create a Market instance for market-wide data access.

    Returns:
        Market instance.
    """
    return _Market(client=_client)
