"""Research and ledger database authority/profile contracts."""
from __future__ import annotations

import pytest
from sqlalchemy import create_mock_engine

from app.ledger import config as ledger_config
from app.ledger import db as ledger_db
from app.core.config import Settings
from app.db.plane_config import PlaneSettings
from research import config as research_config
from research.domain import base as research_db
from research import guards
from research.guards import ResearchIsolationError


def test_research_database_url_precedes_legacy_path_and_rejects_sqlite_in_production():
    env = {
        "PT_RESEARCH_DATABASE_URL": "postgresql+psycopg://app@db/research",
        "PT_RESEARCH_DB_PATH": "ignored.db",
    }
    assert research_config.research_database_url(env) == env["PT_RESEARCH_DATABASE_URL"]

    with pytest.raises(RuntimeError, match="PT_RESEARCH_DATABASE_URL"):
        research_config.research_database_url({"PT_PRODUCTION": "1"})
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        research_config.research_database_url({
            "PT_PRODUCTION": "1",
            "PT_RESEARCH_DATABASE_URL": "sqlite:///research.db",
        })


def test_ledger_database_url_precedes_legacy_path_and_rejects_sqlite_in_production():
    env = {
        "PT_LEDGER_DATABASE_URL": "postgresql+psycopg://app@db/ledger",
        "PT_LEDGER_DB_PATH": "ignored.db",
    }
    assert ledger_config.ledger_database_url(env) == env["PT_LEDGER_DATABASE_URL"]

    with pytest.raises(RuntimeError, match="PT_LEDGER_DATABASE_URL"):
        ledger_config.ledger_database_url({"PT_PRODUCTION": "true"})
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        ledger_config.ledger_database_url({
            "PT_PRODUCTION": "true",
            "PT_LEDGER_DATABASE_URL": "sqlite:///ledger.db",
        })


@pytest.mark.parametrize("module", (research_db, ledger_db))
def test_postgresql_plane_engine_has_no_sqlite_arguments_or_pragmas(monkeypatch, module):
    captured = {}
    registrations = []

    def capture(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return create_mock_engine(url, lambda *_args, **_kwargs: None)

    def listens_for(target, identifier):
        registrations.append((target.dialect.name, identifier))
        return lambda callback: callback

    monkeypatch.setattr(module, "create_engine", capture)
    monkeypatch.setattr(module.event, "listens_for", listens_for)

    engine = module.make_engine("postgresql+psycopg://app@db/plane")

    assert engine.dialect.name == "postgresql"
    assert captured["kwargs"] == {
        "future": True,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 10,
    }
    assert registrations == []


def test_url_sidecars_do_not_embed_database_credentials():
    env = {"PT_RESEARCH_DATABASE_URL": "postgresql+psycopg://app:secret@db/research"}

    assert research_config.operation_receipt_path(env) == "research.operations.json"
    assert research_config.operation_lock_path(env) == "research.operations.json.lock"


def test_database_authority_label_redacts_credentials_and_query_secrets():
    authority = (
        "postgresql+psycopg://research-user:database-password@db.internal:5433/strategy"
        "?options=-csearch_path%3Dresearch&sslpassword=query-secret"
    )

    label = research_config.database_authority_label(authority)

    assert label == "postgresql://db.internal:5433/strategy"
    for secret in ("research-user", "database-password", "query-secret", "options", "research"):
        assert secret not in label


def test_manual_research_startup_never_prints_raw_database_urls(monkeypatch, capsys):
    from app.core import config as app_config
    from research import guards as research_guards
    from scripts import research_run

    monkeypatch.setenv(
        "PT_RESEARCH_DATABASE_URL",
        "postgresql+psycopg://research-user:research-password@db/research"
        "?sslpassword=research-query-secret",
    )
    monkeypatch.setenv(
        "PT_DATABASE_URL",
        "postgresql+psycopg://execution-user:execution-password@db/execution"
        "?sslpassword=execution-query-secret",
    )
    monkeypatch.setenv("PT_LEDGER_DATABASE_URL", "postgresql+psycopg://app@db/ledger")
    monkeypatch.setattr(research_guards, "enforce", lambda **_kwargs: None)
    isolated_settings = app_config.Settings()
    monkeypatch.setattr(app_config, "get_settings", lambda: isolated_settings)
    research_run._enforce_isolation()

    output = capsys.readouterr().out
    assert "postgresql://db/research" in output
    assert "postgresql://db/execution" in output
    for secret in (
        "research-user", "research-password", "research-query-secret",
        "execution-user", "execution-password", "execution-query-secret",
        "sslpassword",
    ):
        assert secret not in output


def test_nightly_completion_never_prints_raw_database_url(monkeypatch, capsys):
    from app.core.config import get_settings
    from app.ledger import config as configured_ledger
    from research import nightly

    authority = (
        "postgresql+psycopg://nightly-user:nightly-password@db/research"
        "?sslpassword=nightly-query-secret"
    )
    monkeypatch.setattr(nightly, "research_database_url", lambda: authority)
    monkeypatch.setattr(nightly, "_execution_db_path",
                        lambda: "postgresql+psycopg://app@db/execution")
    monkeypatch.setattr(nightly, "enforce", lambda **_kwargs: None)
    monkeypatch.setattr(nightly, "_run_enabled_operation", lambda _authority: [])
    monkeypatch.setattr(configured_ledger, "ledger_database_url",
                        lambda: "postgresql+psycopg://app@db/ledger")
    monkeypatch.setattr(get_settings(), "research_enabled", True)

    assert nightly.main() == 0

    output = capsys.readouterr().out
    assert "postgresql://db/research" in output
    for secret in ("nightly-user", "nightly-password", "nightly-query-secret", "sslpassword"):
        assert secret not in output


def test_equal_postgresql_database_requires_explicit_distinct_search_paths():
    common = "postgresql+psycopg://app@db/strategy"
    with pytest.raises(ResearchIsolationError, match="search_path"):
        guards.assert_distinct_database_authorities(common, common)

    guards.assert_distinct_database_authorities(
        common + "?options=-csearch_path%3Dresearch",
        common + "?options=-csearch_path%3Dexecution",
    )

    with pytest.raises(ResearchIsolationError, match="search_path"):
        guards.assert_distinct_database_authorities(
            common + "?options=-csearch_path%3Dresearch",
            common + "?options=-csearch_path%3Dresearch",
        )


def test_ledger_sessionmaker_cache_tracks_database_authority(monkeypatch):
    built = []
    disposed = []

    class Engine:
        def __init__(self, authority):
            self.authority = authority

        def dispose(self):
            disposed.append(self.authority)

    monkeypatch.setattr(ledger_db, "make_engine", lambda authority: Engine(authority))
    monkeypatch.setattr(ledger_db, "init_ledger_db", lambda engine: built.append(engine.authority))
    monkeypatch.setattr(ledger_db, "sessionmaker", lambda **kwargs: kwargs["bind"])
    ledger_db.reset_sessionmaker_cache()

    first = ledger_db.get_sessionmaker("sqlite:///one.db")
    same = ledger_db.get_sessionmaker("sqlite:///one.db")
    second = ledger_db.get_sessionmaker("sqlite:///two.db")

    assert same is first
    assert second is not first
    assert built == ["sqlite:///one.db", "sqlite:///two.db"]
    assert disposed == ["sqlite:///one.db"]
    ledger_db.reset_sessionmaker_cache()
    assert disposed == ["sqlite:///one.db", "sqlite:///two.db"]


def test_all_three_plane_authorities_are_checked_pairwise():
    common = "postgresql+psycopg://app@db/strategy"
    execution = common + "?options=-csearch_path%3Dexecution"
    research = common + "?options=-csearch_path%3Dresearch"
    ledger = common + "?options=-csearch_path%3Dledger"

    guards.assert_pairwise_database_authorities(execution, research, ledger)

    with pytest.raises(ResearchIsolationError, match="search_path"):
        guards.assert_pairwise_database_authorities(execution, research, research)


def test_different_postgresql_credentials_do_not_make_one_database_distinct():
    execution = "postgresql+psycopg://execution@db/strategy"
    research = "postgresql+psycopg://research@db/strategy"

    with pytest.raises(ResearchIsolationError, match="search_path"):
        guards.assert_distinct_database_authorities(execution, research)


def test_effective_last_search_path_setting_controls_distinctness():
    common = "postgresql+psycopg://app@db/strategy"
    execution = (
        common + "?options=-csearch_path%3Dfirst_execution"
        "&options=-c%20search_path%3Dshared_final"
    )
    research = (
        common + "?options=-csearch_path%3Dfirst_research"
        "&options=-csearch_path%3Dshared_final"
    )

    with pytest.raises(ResearchIsolationError, match="search_path"):
        guards.assert_distinct_database_authorities(execution, research)


def test_default_postgresql_port_and_explicit_5432_are_one_endpoint():
    without_port = "postgresql+psycopg://app@db/strategy"
    explicit_port = "postgresql+psycopg://other@db:5432/strategy"

    with pytest.raises(ResearchIsolationError, match="search_path"):
        guards.assert_distinct_database_authorities(without_port, explicit_port)


def test_app_settings_plane_authorities_feed_resolvers_without_os_environ():
    settings = Settings(
        _env_file=None,
        production=True,
        research_database_url="postgresql+psycopg://app@db/research",
        ledger_database_url="postgresql+psycopg://app@db/ledger",
    )

    assert research_config.research_database_url(
        database_url=settings.research_database_url,
        production=settings.production,
        db_path=settings.research_db_path,
    ) == settings.research_database_url
    assert ledger_config.ledger_database_url(
        database_url=settings.ledger_database_url,
        production=settings.production,
        db_path=settings.ledger_db_path,
    ) == settings.ledger_database_url


def test_app_settings_production_plane_authorities_never_fall_back():
    settings = Settings(_env_file=None, production=True)

    with pytest.raises(RuntimeError, match="PT_RESEARCH_DATABASE_URL"):
        research_config.research_database_url(
            database_url=settings.research_database_url,
            production=settings.production,
            db_path=settings.research_db_path,
        )
    with pytest.raises(RuntimeError, match="PT_LEDGER_DATABASE_URL"):
        ledger_config.ledger_database_url(
            database_url=settings.ledger_database_url,
            production=settings.production,
            db_path=settings.ledger_db_path,
        )


def test_standalone_plane_settings_load_private_authorities_from_env_file(tmp_path, monkeypatch):
    for name in ("PT_PRODUCTION", "PT_RESEARCH_DATABASE_URL", "PT_LEDGER_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PT_PRODUCTION=1\n"
        "PT_RESEARCH_DATABASE_URL=postgresql+psycopg://app@db/research\n"
        "PT_LEDGER_DATABASE_URL=postgresql+psycopg://app@db/ledger\n"
    )

    settings = PlaneSettings(_env_file=env_file)

    assert settings.production is True
    assert settings.research_database_url.endswith("/research")
    assert settings.ledger_database_url.endswith("/ledger")


def test_research_read_authority_uses_resolved_plane_url_without_process_env(monkeypatch):
    from app.core import research_read

    authority = "postgresql+psycopg://app@db/research"
    monkeypatch.delenv("PT_RESEARCH_DATABASE_URL", raising=False)
    monkeypatch.setattr(research_read, "research_database_url", lambda: authority)

    assert research_read._research_authority() == authority
