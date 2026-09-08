from __future__ import annotations

import datetime as dt
import json

import sqlalchemy as sa
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Base, MarketDataCapabilityProfile, MarketTruthInstrument, MarketTruthProviderMapping, MarketTruthSnapshotRecord
from app.ir.hashing import canonical_json, content_address
from research.domain.base import ResearchBase
from research.domain import migrate as research_migrate
from research.domain.base import init_research_db, make_engine
from research_tests.test_ir_v2_research_migration import (
    _REFUSAL_PATTERN,
    _sqlite_logical_digest,
)
from research.domain.models import DatasetManifest, persist_dataset_manifest

OTHER = "sha256:" + "b" * 64
EMPTY_DIGEST = content_address({})


def _manifest_values(*, owner_id="owner-a", provider="test", dataset_version="2026-01", market_truth_digest=OTHER, capability_digest=OTHER, extra=None):
    document = {"owner_id": owner_id, "provider": provider, "dataset_version": dataset_version,
                "market_truth_digest": market_truth_digest, "capability_digest": capability_digest,
                "schema_version": 1}
    if extra:
        document.update(extra)
    return {"owner_id": owner_id, "provider": provider, "dataset_version": dataset_version,
            "market_truth_digest": market_truth_digest, "capability_digest": capability_digest,
            "digest": content_address(document), "manifest_json": canonical_json(document)}


def test_market_truth_reference_facts_refuse_bad_digests_and_intervals():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(sa.insert(MarketTruthInstrument), {"address": EMPTY_DIGEST, "identity_json": "{}"})
        with pytest.raises(ValueError, match="does not match"):
            connection.execute(sa.insert(MarketTruthInstrument), {
                "address": OTHER, "identity_json": "{}",
            })
        connection.execute(sa.insert(MarketTruthProviderMapping), {"instrument_address": EMPTY_DIGEST, "provider": "test", "provider_token": "opaque-id", "adapter_version": "v1", "effective_from": dt.datetime(2026, 1, 1, tzinfo=dt.UTC), "effective_to": dt.datetime(2026, 2, 1, tzinfo=dt.UTC)})
        with pytest.raises(IntegrityError, match="overlaps"):
            connection.execute(sa.insert(MarketTruthProviderMapping), {"instrument_address": EMPTY_DIGEST, "provider": "test", "provider_token": "opaque-id", "adapter_version": "v1", "effective_from": dt.datetime(2026, 1, 15, tzinfo=dt.UTC), "effective_to": dt.datetime(2026, 3, 1, tzinfo=dt.UTC)})
        with pytest.raises(IntegrityError):
            connection.execute(sa.insert(MarketTruthProviderMapping), {"instrument_address": EMPTY_DIGEST, "provider": "test", "provider_token": "bad", "adapter_version": "v1", "effective_from": dt.datetime(2026, 2, 1, tzinfo=dt.UTC), "effective_to": dt.datetime(2026, 1, 1, tzinfo=dt.UTC)})
        with pytest.raises(ValueError, match="does not match"):
            connection.execute(sa.insert(MarketTruthSnapshotRecord), {"digest": "invalid", "payload_json": "{}", "quality": "OBSERVED"})
        with pytest.raises(ValueError, match="does not match"):
            connection.execute(sa.insert(MarketTruthSnapshotRecord), {"digest": OTHER, "payload_json": "{}", "quality": "OBSERVED"})
        connection.execute(sa.insert(MarketTruthSnapshotRecord), {"digest": EMPTY_DIGEST, "payload_json": "{}", "quality": "OBSERVED"})
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(sa.text("UPDATE market_truth_snapshots SET quality='UNKNOWN' WHERE digest=:digest"), {"digest": EMPTY_DIGEST})
        connection.execute(sa.insert(MarketDataCapabilityProfile), {"owner_id": "owner-a", "digest": EMPTY_DIGEST, "provider": "test", "capability_json": "{}"})
        safe_capability = {"nested": {"classification": "public"}, "segments": [{"name": "primary"}]}
        connection.execute(sa.insert(MarketDataCapabilityProfile), {
            "owner_id": "owner-safe", "digest": content_address(safe_capability), "provider": "test",
            "capability_json": canonical_json(safe_capability),
        })
        canonical_nested_secret = {"nested": {"api_key": "forbidden"}}
        with pytest.raises((IntegrityError, ValueError), match="credential-bearing"):
            connection.execute(sa.insert(MarketDataCapabilityProfile), {
                "owner_id": "owner-canonical-secret", "digest": content_address(canonical_nested_secret),
                "provider": "test", "capability_json": canonical_json(canonical_nested_secret),
            })
        with pytest.raises((IntegrityError, ValueError)):
            connection.execute(sa.insert(MarketDataCapabilityProfile), {"owner_id": "owner-b", "digest": OTHER, "provider": "test", "capability_json": r'{"\u0061pi_key":"forbidden"}'})
        with pytest.raises((IntegrityError, ValueError), match="credential-bearing|canonical JSON"):
            connection.execute(sa.insert(MarketDataCapabilityProfile), {"owner_id": "owner-nested", "digest": OTHER, "provider": "test", "capability_json": r'{"nested":{"\u0061pi_key":"forbidden"}}'})


def test_dataset_manifest_is_owner_scoped_cross_plane_and_secret_free():
    engine = sa.create_engine("sqlite://")
    ResearchBase.metadata.create_all(engine)
    values = _manifest_values()
    with engine.begin() as connection:
        connection.execute(sa.insert(DatasetManifest), values)
        safe_values = _manifest_values(owner_id="owner-safe", extra={
            "nested": {"classification": "public"}, "segments": [{"name": "primary"}],
        })
        connection.execute(sa.insert(DatasetManifest), safe_values)
        with pytest.raises((IntegrityError, ValueError)):
            connection.execute(sa.insert(DatasetManifest), {**values, "manifest_json": '{"secret":"no"}'})
        with pytest.raises((IntegrityError, ValueError)):
            connection.execute(sa.insert(DatasetManifest), {**values, "manifest_json": '{"api_key":"no"}'})
        with pytest.raises((IntegrityError, ValueError)):
            connection.execute(sa.insert(DatasetManifest), {**values, "manifest_json": r'{"\u0061pi_key":"no"}'})
        nested_secret = _manifest_values(owner_id="owner-nested", extra={
            "nested": {"api_key": "forbidden"},
        })
        with pytest.raises((IntegrityError, ValueError), match="credential-bearing|canonical JSON"):
            connection.execute(sa.insert(DatasetManifest), {
                **nested_secret,
                "manifest_json": nested_secret["manifest_json"].replace('"api_key"', r'"\u0061pi_key"'),
            })
        connection.execute(sa.insert(DatasetManifest), _manifest_values(owner_id="owner-b"))
        with pytest.raises(IntegrityError):
            connection.execute(sa.text("UPDATE research_dataset_manifests SET provider='other' WHERE owner_id='owner-a'"))
    with Session(engine) as session:
        tampered = {**values, "manifest_json": canonical_json({
            **json.loads(values["manifest_json"]), "extra": True,
        })}
        session.add(DatasetManifest(**tampered))
        with pytest.raises(ValueError, match="digest does not match"):
            session.flush()
    with engine.begin() as connection:
        with pytest.raises((IntegrityError, ValueError)):
            connection.execute(sa.insert(DatasetManifest), {**values, "provider": "other"})


def test_dataset_manifest_seam_uses_authoritative_owner_sqlite():
    """Caller-supplied manifest values cannot select another owner's capability."""
    execution = sa.create_engine("sqlite://")
    research = sa.create_engine("sqlite://")
    Base.metadata.create_all(execution)
    ResearchBase.metadata.create_all(research)
    with execution.begin() as connection:
        connection.execute(sa.insert(MarketTruthSnapshotRecord), {
            "digest": EMPTY_DIGEST, "payload_json": "{}", "quality": "OBSERVED",
        })
        connection.execute(sa.insert(MarketDataCapabilityProfile), {
            "owner_id": "owner-a", "digest": EMPTY_DIGEST, "provider": "test",
            "capability_json": "{}",
        })
    with execution.connect() as execution_connection, research.begin() as research_connection:
        with pytest.raises(ValueError, match="authoritative owner"):
            persist_dataset_manifest(
                execution_connection, research_connection, owner_id="owner-a",
                values=_manifest_values(owner_id="owner-b", market_truth_digest=EMPTY_DIGEST,
                                        capability_digest=EMPTY_DIGEST),
            )
        with pytest.raises(ValueError, match="not owned"):
            persist_dataset_manifest(
                execution_connection, research_connection, owner_id="owner-b",
                values=_manifest_values(owner_id="owner-b", market_truth_digest=EMPTY_DIGEST,
                                        capability_digest=EMPTY_DIGEST),
            )


def test_content_address_guards_all_controlled_sqlalchemy_insert_shapes_sqlite():
    """Inline Core values, bound values, executemany, and ORM all fail closed.

    The controlled boundary is SQLAlchemy Core/ORM; raw driver SQL is not claimed.
    """
    execution = sa.create_engine("sqlite://")
    research = sa.create_engine("sqlite://")
    Base.metadata.create_all(execution)
    ResearchBase.metadata.create_all(research)
    bad_execution = (
        (MarketTruthInstrument,
         {"address": EMPTY_DIGEST, "identity_json": "{}"},
         {"address": OTHER, "identity_json": "{}"}),
        (MarketTruthSnapshotRecord,
         {"digest": EMPTY_DIGEST, "payload_json": "{}", "quality": "OBSERVED"},
         {"digest": OTHER, "payload_json": "{}", "quality": "OBSERVED"}),
        (MarketDataCapabilityProfile,
         {"owner_id": "owner-multi-valid", "digest": EMPTY_DIGEST,
          "provider": "test", "capability_json": "{}"},
         {"owner_id": "owner-multi-invalid", "digest": OTHER,
          "provider": "test", "capability_json": "{}"}),
    )
    valid_manifest = _manifest_values(owner_id="owner-multi-valid", market_truth_digest=EMPTY_DIGEST,
                                      capability_digest=EMPTY_DIGEST)
    bad_manifest = {**_manifest_values(owner_id="owner-multi-invalid",
                                        market_truth_digest=EMPTY_DIGEST,
                                        capability_digest=EMPTY_DIGEST), "digest": OTHER}
    for model, valid_values, values in bad_execution:
        with execution.begin() as connection:
            for statement, arguments in (
                (sa.insert(model).values(**values), None),
                (sa.insert(model).values([valid_values, values]), None),
                (sa.insert(model), values),
                (sa.insert(model), [valid_values, values]),
            ):
                with pytest.raises(ValueError, match="does not match"):
                    if arguments is None:
                        connection.execute(statement)
                    else:
                        connection.execute(statement, arguments)
        with Session(execution) as session:
            session.add(model(**values))
            with pytest.raises(ValueError, match="does not match"):
                session.flush()
    with research.begin() as connection:
        for statement, arguments in (
            (sa.insert(DatasetManifest).values(**bad_manifest), None),
            (sa.insert(DatasetManifest).values([valid_manifest, bad_manifest]), None),
            (sa.insert(DatasetManifest), bad_manifest),
            (sa.insert(DatasetManifest), [valid_manifest, bad_manifest]),
        ):
            with pytest.raises(ValueError, match="digest does not match"):
                if arguments is None:
                    connection.execute(statement)
                else:
                    connection.execute(statement, arguments)
    with Session(research) as session:
        session.add(DatasetManifest(**bad_manifest))
        with pytest.raises(ValueError, match="digest does not match"):
            session.flush()


def test_phase4_sqlite_refuses_destructive_downgrade_and_repairs_forward(tmp_path):
    """Both additive facts survive refusal; head init remains an idempotent repair."""
    from alembic import command
    from app.db import migrate as execution_migrate
    from research.domain.migrate import ResearchMigrationError, downgrade_research_db

    execution = sa.create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    research = make_engine(str(tmp_path / "research.db"))
    current_execution_head = execution_migrate.head_revision()
    assert execution_migrate.init_schema(
        execution, create_all=lambda: Base.metadata.create_all(execution),
        legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
        expected_tables=Base.metadata.tables,
    ) == current_execution_head
    with execution.begin() as connection:
        connection.execute(sa.insert(MarketTruthSnapshotRecord), {
            "digest": EMPTY_DIGEST, "payload_json": "{}", "quality": "OBSERVED",
        })
        with pytest.raises(RuntimeError, match="refuses destructive"):
            command.downgrade(execution_migrate.alembic_config(connection), "0035")
    assert execution_migrate.schema_version(execution) == current_execution_head
    with execution.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM market_truth_snapshots")) == 1
    assert execution_migrate.init_schema(
        execution, create_all=lambda: Base.metadata.create_all(execution),
        legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
        expected_tables=Base.metadata.tables,
    ) == current_execution_head
    with execution.begin() as connection:
        connection.execute(sa.text("DROP TABLE market_truth_snapshots"))
    with pytest.raises(RuntimeError, match="not the current execution relational model"):
        execution_migrate._validate_current_schema(execution, Base.metadata.tables)

    init_research_db(research)
    values = _manifest_values()
    with research.begin() as connection:
        connection.execute(sa.insert(DatasetManifest), values)
    with pytest.raises(ResearchMigrationError, match="refuses destructive"):
        downgrade_research_db(research)
    init_research_db(research)
    with research.connect() as connection:
        # A-04 refresh: pinned 0008 when that was the research head.
        assert connection.scalar(sa.text("SELECT version FROM research_schema_version")) == "0011"
        assert connection.scalar(sa.text("SELECT count(*) FROM research_dataset_manifests")) == 1

    with research.begin() as connection:
        connection.execute(sa.text("DROP TABLE research_dataset_manifests"))
    before = _sqlite_logical_digest(research)
    with pytest.raises(research_migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        init_research_db(research)
    assert _sqlite_logical_digest(research) == before
    execution.dispose()
    research.dispose()


@pytest.mark.parametrize("version", ("0005", "0006"))
def test_research_phase4_old_transition_refuses_without_calling_replay(tmp_path, monkeypatch, version):
    def at_version(path):
        engine = sa.create_engine(f"sqlite:///{path}")
        with engine.begin() as connection:
            tables = (research_migrate._pre_0006_tables() if version == "0005"
                      else research_migrate._pre_0007_tables())
            for table in tables:
                table.create(connection)
            for statement in research_migrate._expected_triggers(tables=tables).values():
                connection.exec_driver_sql(statement)
            connection.exec_driver_sql(
                "CREATE TABLE research_schema_version (version VARCHAR(16) NOT NULL PRIMARY KEY, schema_cookie INTEGER NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO research_schema_version VALUES (?, ?)",
                (version, connection.exec_driver_sql("PRAGMA schema_version").scalar_one()),
            )
        return engine

    upgraded = at_version(tmp_path / f"{version}-upgrade.db")
    calls = 0
    original = research_migrate._upgrade_dataset_provenance

    def counted(connection):
        nonlocal calls
        calls += 1
        return original(connection)

    monkeypatch.setattr(research_migrate, "_upgrade_dataset_provenance", counted)
    before = _sqlite_logical_digest(upgraded)
    with pytest.raises(research_migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        init_research_db(upgraded)
    assert calls == 0
    assert _sqlite_logical_digest(upgraded) == before
    with upgraded.connect() as connection:
        assert connection.scalar(sa.text("SELECT version FROM research_schema_version")) == version
        assert not sa.inspect(connection).has_table(DatasetManifest.__tablename__)
    upgraded.dispose()

    failed = at_version(tmp_path / f"{version}-failure.db")
    monkeypatch.setattr(research_migrate, "_upgrade_dataset_provenance", lambda _connection: (_ for _ in ()).throw(AssertionError("old replay must not run")))
    failed_before = _sqlite_logical_digest(failed)
    with pytest.raises(research_migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
        init_research_db(failed)
    assert _sqlite_logical_digest(failed) == failed_before
    with failed.connect() as connection:
        assert connection.scalar(sa.text("SELECT version FROM research_schema_version")) == version
        assert not sa.inspect(connection).has_table(DatasetManifest.__tablename__)
    monkeypatch.setattr(research_migrate, "_upgrade_dataset_provenance", original)
    failed.dispose()
