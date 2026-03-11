"""Exception hierarchy for pybrisk."""


class PyBriskError(Exception):
    """Base exception for all pybrisk errors."""


class AuthenticationError(PyBriskError):
    """Login failed or invalid credentials."""


class SessionExpiredError(PyBriskError):
    """Session cookies have expired. Re-login required."""


class ConfigurationError(PyBriskError):
    """Missing or invalid configuration (e.g., no credentials)."""


class APIError(PyBriskError):
    """HTTP error from BRiSK API."""

    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}" if message else f"HTTP {status_code}")


class NotFoundError(APIError):
    """Resource not found (404). Usually invalid stock code."""

    def __init__(self, message: str = "Not found") -> None:
        super().__init__(404, message)


class RateLimitError(APIError):
    """Too many requests (429)."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(429, message)
