"""Tests for application configuration loading."""

import os

import pytest

from makervault.config import Settings, get_settings


def test_default_app_name() -> None:
    settings = Settings()
    assert settings.app_name == "MakerVault API"


def test_default_version() -> None:
    settings = Settings()
    assert settings.app_version == "1.0.0"


def test_debug_defaults_false() -> None:
    settings = Settings()
    assert settings.debug is False


def test_database_url_has_default() -> None:
    settings = Settings()
    assert "postgresql+asyncpg" in settings.database_url


def test_document_store_path_default() -> None:
    settings = Settings()
    assert settings.document_store_path == "/data/makervault/documents"


def test_env_var_override(monkeypatch) -> None:
    """Environment variables should override defaults."""
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("APP_NAME", "Test Override")
    settings = Settings()
    assert settings.debug is True
    assert settings.app_name == "Test Override"


def test_get_settings_returns_singleton() -> None:
    """get_settings() should return the same cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
