"""Tests for public API surface."""

import pybrisk as pb


def test_exports() -> None:
    assert hasattr(pb, "Ticker")
    assert hasattr(pb, "Market")
    assert hasattr(pb, "login")
    assert hasattr(pb, "config")
    assert hasattr(pb, "__version__")


def test_exception_exports() -> None:
    assert hasattr(pb, "PyBriskError")
    assert hasattr(pb, "AuthenticationError")
    assert hasattr(pb, "SessionExpiredError")
    assert hasattr(pb, "APIError")
    assert hasattr(pb, "NotFoundError")
    assert hasattr(pb, "RateLimitError")
    assert hasattr(pb, "ConfigurationError")


def test_version() -> None:
    assert pb.__version__ == "0.1.0"


def test_ticker_creates_instance() -> None:
    t = pb.Ticker("7203")
    assert t.code == "7203"
    assert repr(t) == "Ticker('7203')"


def test_market_creates_instance() -> None:
    m = pb.Market()
    assert m is not None
