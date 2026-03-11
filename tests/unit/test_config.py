"""Tests for configuration loading."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from pybrisk._internal.config import Config
from pybrisk._internal.exceptions import ConfigurationError


def test_default_values() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
    assert config.timeout == 30
    assert config.cache_ttl == 3600
    assert config.rate_limit == 1.0


def test_env_vars() -> None:
    env = {"BRISK_USERNAME": "testuser", "BRISK_PASSWORD": "testpass"}
    with patch.dict(os.environ, env, clear=True):
        config = Config()
    assert config.username == "testuser"
    assert config.password == "testpass"


def test_missing_username_raises() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
    with pytest.raises(ConfigurationError, match="Username"):
        _ = config.username


def test_missing_password_raises() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
    with pytest.raises(ConfigurationError, match="Password"):
        _ = config.password


def test_has_credentials() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
    assert config.has_credentials is False
    config.username = "user"
    config.password = "pass"
    assert config.has_credentials is True


def test_runtime_modification() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
    config.timeout = 60
    config.cache_ttl = 7200
    assert config.timeout == 60
    assert config.cache_ttl == 7200


def test_toml_loading(tmp_path: object) -> None:
    """Test TOML loading with a temp config file."""
    import pybrisk._internal.config as config_module

    toml_path = tmp_path / "config.toml"  # type: ignore[operator]
    toml_path.write_text(
        '[auth]\nusername = "tomluser"\npassword = "tomlpass"\n\n'
        "[settings]\ntimeout = 60\n"
    )

    original = config_module._DEFAULT_TOML_PATH
    config_module._DEFAULT_TOML_PATH = toml_path
    try:
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
        assert config.username == "tomluser"
        assert config.password == "tomlpass"
        assert config.timeout == 60
    finally:
        config_module._DEFAULT_TOML_PATH = original


def test_env_overrides_toml(tmp_path: object) -> None:
    """Env vars take priority over TOML."""
    import pybrisk._internal.config as config_module

    toml_path = tmp_path / "config.toml"  # type: ignore[operator]
    toml_path.write_text('[auth]\nusername = "tomluser"\npassword = "tomlpass"\n')

    original = config_module._DEFAULT_TOML_PATH
    config_module._DEFAULT_TOML_PATH = toml_path
    try:
        env = {"BRISK_USERNAME": "envuser"}
        with patch.dict(os.environ, env, clear=True):
            config = Config()
        assert config.username == "envuser"
        assert config.password == "tomlpass"
    finally:
        config_module._DEFAULT_TOML_PATH = original
