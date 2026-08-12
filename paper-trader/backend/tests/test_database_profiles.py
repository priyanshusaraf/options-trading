"""Database profile contracts independent of a live PostgreSQL service."""
from __future__ import annotations

import pytest
from sqlalchemy import create_mock_engine

from app.core.config import Settings
from app.db import engine as db_engine


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_database_url_overrides_legacy_sqlite_path():
    settings = _settings(
        db_path="ignored.db",
        database_url="postgresql+psycopg://app:secret@db/strategy",
    )

    assert db_engine.database_url(settings) == "postgresql+psycopg://app:secret@db/strategy"


def test_database_url_uses_sqlite_only_as_legacy_compatibility_boundary():
    settings = _settings(db_path="local paper.db")

    assert db_engine.database_url(settings) == "sqlite:///local paper.db"


def test_production_profile_refuses_implicit_sqlite_url():
    settings = _settings(production=True, db_path="local.db")

    with pytest.raises(RuntimeError, match="PT_DATABASE_URL"):
        db_engine.database_url(settings)


def test_production_profile_refuses_an_explicit_sqlite_url():
    settings = _settings(production=True, database_url="sqlite:///local.db")

    with pytest.raises(RuntimeError, match="PostgreSQL"):
        db_engine.database_url(settings)


def test_postgresql_profile_uses_a_bounded_pool_without_sqlite_arguments(monkeypatch):
    captured = {}

    def capture(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return create_mock_engine(url, lambda *_args, **_kwargs: None)

    monkeypatch.setattr(db_engine, "create_engine", capture)

    engine = db_engine.create_database_engine("postgresql+psycopg://app:secret@db/strategy")

    assert engine.dialect.name == "postgresql"
    assert captured["kwargs"] == {
        "future": True,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 10,
    }


def test_sqlite_profile_keeps_thread_and_timeout_compatibility(monkeypatch):
    captured = {}

    def capture(url, **kwargs):
        captured["kwargs"] = kwargs
        return create_mock_engine(url, lambda *_args, **_kwargs: None)

    monkeypatch.setattr(db_engine, "create_engine", capture)

    db_engine.create_database_engine("sqlite:///local.db")

    assert captured["kwargs"] == {
        "future": True,
        "connect_args": {"check_same_thread": False},
        "pool_pre_ping": True,
        "pool_timeout": 10,
    }


def test_sqlite_pragmas_are_registered_only_for_sqlite(monkeypatch):
    registrations = []

    def listen_for(target, identifier):
        registrations.append((target.dialect.name, identifier))

        def decorate(callback):
            return callback

        return decorate

    monkeypatch.setattr(db_engine.event, "listens_for", listen_for)

    sqlite = create_mock_engine("sqlite:///local.db", lambda *_args, **_kwargs: None)
    postgres = create_mock_engine("postgresql+psycopg://app:secret@db/strategy",
                                  lambda *_args, **_kwargs: None)

    db_engine.configure_connection_profile(sqlite)
    db_engine.configure_connection_profile(postgres)

    assert registrations == [("sqlite", "connect")]
