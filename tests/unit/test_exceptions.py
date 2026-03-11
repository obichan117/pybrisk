"""Tests for exception hierarchy."""

from pybrisk._internal.exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    PyBriskError,
    RateLimitError,
    SessionExpiredError,
)


def test_hierarchy() -> None:
    assert issubclass(AuthenticationError, PyBriskError)
    assert issubclass(SessionExpiredError, PyBriskError)
    assert issubclass(ConfigurationError, PyBriskError)
    assert issubclass(APIError, PyBriskError)
    assert issubclass(NotFoundError, APIError)
    assert issubclass(RateLimitError, APIError)


def test_api_error_status_code() -> None:
    err = APIError(500, "Internal server error")
    assert err.status_code == 500
    assert "500" in str(err)


def test_not_found_error() -> None:
    err = NotFoundError("Stock 9999 not found")
    assert err.status_code == 404


def test_rate_limit_error() -> None:
    err = RateLimitError()
    assert err.status_code == 429
