"""Disposable PostgreSQL 16 proof for Phase 4's two persistence planes."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import uuid

from alembic import command
import pytest
import sqlalchemy as sa


EMPTY_DIGEST = "sha256:" + hashlib.sha256(b"{}").hexdigest()
ADDRESS = "sha256:" + "a" * 64
TRUTH = EMPTY_DIGEST
CAPABILITY = "sha256:" + "c" * 64
INSTRUMENT_IDENTITY = json.dumps({"instrument": "fixture"}, sort_keys=True, separators=(",", ":"))
INSTRUMENT_ADDRESS = "sha256:" + hashlib.sha256(INSTRUMENT_IDENTITY.encode()).hexdigest()


def _digest_json(document: dict) -> tuple[str, str]:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return encoded, "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


MULTI_INSTRUMENT_IDENTITY, MULTI_INSTRUMENT_ADDRESS = _digest_json({"instrument": "multi"})
MULTI_SNAPSHOT_PAYLOAD, MULTI_SNAPSHOT_DIGEST = _digest_json({"snapshot": "multi"})
MULTI_CAPABILITY_JSON, MULTI_CAPABILITY_DIGEST = _digest_json({"capability": "multi"})


def _manifest_values(*, owner_id="owner-a", provider="fixture", dataset_version="fixture-v1", market_truth_digest=TRUTH, capability_digest=EMPTY_DIGEST, extra=None):
    document = {"owner_id": owner_id, "provider": provider, "dataset_version": dataset_version,
                "market_truth_digest": market_truth_digest, "capability_digest": capability_digest,
                "schema_version": 1}
    if extra:
        document.update(extra)
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return {"owner_id": owner_id, "provider": provider, "dataset_version": dataset_version,
            "market_truth_digest": market_truth_digest, "capability_digest": capability_digest,
            "digest": "sha256:" + hashlib.sha256(encoded.encode()).hexdigest(), "manifest_json": encoded}


def _schema_url(base_url: str, schema: str) -> str:
    return str(sa.engine.make_url(base_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    ))


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="disposable PostgreSQL harness required")
def test_phase4_postgresql_install_upgrade_restart_restore_and_guards(tmp_path):
    """Both planes migrate to their owned heads and survive a local clean restore."""
    from app.db import migrate as execution_migrate
    from app.db.models import (Base, MarketDataCapabilityProfile, MarketTruthInstrument,
                               MarketTruthProviderMapping, MarketTruthSnapshotRecord)
    from app.operations.postgresql_backup import (postgres_process_spec,
                                                   resolve_postgresql16_tools,
                                                   run_process_spec)
    from research.domain.base import ResearchBase, init_research_db
    from research.domain.migrate import (
        HEAD_VERSION as RESEARCH_HEAD,
        ResearchMigrationError,
        downgrade_research_db,
    )
    from research.domain.models import DatasetManifest, persist_dataset_manifest

    base_url = os.environ["PT_TEST_POSTGRES_URL"]
    execution_schema = f"phase4_execution_{uuid.uuid4().hex}"
    research_schema = f"phase4_research_{uuid.uuid4().hex}"
    execution_empty_schema = f"phase4_execution_empty_{uuid.uuid4().hex}"
    research_empty_schema = f"phase4_research_empty_{uuid.uuid4().hex}"
    execution_url = _schema_url(base_url, execution_schema)
    research_url = _schema_url(base_url, research_schema)
    execution_empty_url = _schema_url(base_url, execution_empty_schema)
    research_empty_url = _schema_url(base_url, research_empty_schema)
    admin = sa.create_engine(base_url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{execution_schema}"'))
        connection.execute(sa.text(f'CREATE SCHEMA "{research_schema}"'))
        connection.execute(sa.text(f'CREATE SCHEMA "{execution_empty_schema}"'))
        connection.execute(sa.text(f'CREATE SCHEMA "{research_empty_schema}"'))
    execution = sa.create_engine(execution_url, future=True)
    research = sa.create_engine(research_url, future=True)
    execution_empty = sa.create_engine(execution_empty_url, future=True)
    research_empty = sa.create_engine(research_empty_url, future=True)
    try:
        phase4_execution = {
            "market_truth_instruments", "market_truth_provider_mappings",
            "market_truth_snapshots", "market_data_capability_profiles",
        }
        # Head contract: exactly one migration head exists, a clean install
        # reaches exactly that head, and the owned Phase 4 tables exist there.
        execution_head = execution_migrate.head_revision()
        from alembic.script import ScriptDirectory

        assert ScriptDirectory.from_config(
            execution_migrate.alembic_config()).get_heads() == [execution_head]
        assert execution_migrate.init_schema(
            execution_empty, create_all=lambda: Base.metadata.create_all(execution_empty),
            legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
            expected_tables=Base.metadata.tables,
        ) == execution_head
        assert execution_migrate.schema_version(execution_empty) == execution_head
        assert phase4_execution <= set(sa.inspect(execution_empty).get_table_names())
        init_research_db(research_empty)
        with research_empty.connect() as connection:
            assert connection.scalar(sa.text("SELECT version FROM research_schema_version")) == RESEARCH_HEAD
            assert sa.inspect(connection).has_table(DatasetManifest.__tablename__)
        with execution_empty.begin() as connection:
            connection.execute(sa.text("DROP TABLE market_truth_snapshots"))
        with pytest.raises(RuntimeError, match="not the current execution relational model"):
            execution_migrate.init_schema(
                execution_empty, create_all=lambda: Base.metadata.create_all(execution_empty),
                legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
                expected_tables=Base.metadata.tables,
            )
        with research_empty.begin() as connection:
            connection.execute(sa.text("DROP TABLE research_dataset_manifests"))
        with pytest.raises(RuntimeError, match="table-set drift"):
            init_research_db(research_empty)

        with execution.begin() as connection:
            for table in Base.metadata.sorted_tables:
                if table.name not in phase4_execution:
                    table.create(connection, checkfirst=True)
            command.stamp(execution_migrate.alembic_config(connection), "0035")
            command.upgrade(execution_migrate.alembic_config(connection), "0036")
        assert execution_migrate.schema_version(execution) == "0036"

        # POLICY-BLOCKED COVERAGE REMOVED (owner decision pending): this test
        # previously built a "0006-era" research plane from current metadata
        # minus one table and proved an upgrade from it. That hybrid fixture is
        # banned by the owner, and an honest historical state cannot be produced
        # by today's step DDL (current-model constraints) — supporting research
        # historical upgrades on PostgreSQL is exactly the open migration-matrix
        # policy question presented to the owner. All current-head contracts
        # below (fresh install, tamper refusal, restore parity) remain proven.
        init_research_db(research)
        with research.connect() as connection:
            assert connection.scalar(sa.text("SELECT version FROM research_schema_version")) == RESEARCH_HEAD

        with execution.begin() as connection:
            connection.execute(sa.insert(MarketTruthInstrument), {
                "address": INSTRUMENT_ADDRESS, "identity_json": INSTRUMENT_IDENTITY,
            })
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthInstrument), {
                    "address": ADDRESS, "identity_json": "{}",
                })
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthInstrument).values(
                    address=ADDRESS, identity_json="{}",
                ))
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthInstrument).values([
                    {"address": MULTI_INSTRUMENT_ADDRESS, "identity_json": MULTI_INSTRUMENT_IDENTITY},
                    {"address": "sha256:" + "b" * 64, "identity_json": "{}"},
                ]))
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthInstrument), [
                    {"address": MULTI_INSTRUMENT_ADDRESS, "identity_json": MULTI_INSTRUMENT_IDENTITY},
                    {"address": "sha256:" + "b" * 64, "identity_json": "{}"},
                ])
            connection.execute(sa.insert(MarketTruthProviderMapping), {
                "instrument_address": INSTRUMENT_ADDRESS, "provider": "fixture", "provider_token": "opaque",
                "adapter_version": "v1", "effective_from": dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                "effective_to": dt.datetime(2026, 2, 1, tzinfo=dt.UTC),
            })
            with pytest.raises(sa.exc.DBAPIError, match="overlaps"):
                with connection.begin_nested():
                    connection.execute(sa.insert(MarketTruthProviderMapping), {
                        "instrument_address": INSTRUMENT_ADDRESS, "provider": "fixture", "provider_token": "opaque",
                        "adapter_version": "v1", "effective_from": dt.datetime(2026, 1, 15, tzinfo=dt.UTC),
                        "effective_to": dt.datetime(2026, 3, 1, tzinfo=dt.UTC),
                    })
            connection.execute(sa.insert(MarketTruthSnapshotRecord), {
                "digest": TRUTH, "payload_json": "{}", "quality": "OBSERVED",
            })
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthSnapshotRecord), {
                    "digest": ADDRESS, "payload_json": "{}", "quality": "OBSERVED",
                })
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthSnapshotRecord).values(
                    digest=ADDRESS, payload_json="{}", quality="OBSERVED",
                ))
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthSnapshotRecord).values([
                    {"digest": MULTI_SNAPSHOT_DIGEST, "payload_json": MULTI_SNAPSHOT_PAYLOAD,
                     "quality": "OBSERVED"},
                    {"digest": "sha256:" + "b" * 64, "payload_json": "{}", "quality": "OBSERVED"},
                ]))
            with pytest.raises(ValueError, match="does not match"):
                connection.execute(sa.insert(MarketTruthSnapshotRecord), [
                    {"digest": MULTI_SNAPSHOT_DIGEST, "payload_json": MULTI_SNAPSHOT_PAYLOAD,
                     "quality": "OBSERVED"},
                    {"digest": "sha256:" + "b" * 64, "payload_json": "{}", "quality": "OBSERVED"},
                ])
            connection.execute(sa.insert(MarketDataCapabilityProfile), {
                "owner_id": "owner-a", "digest": EMPTY_DIGEST, "provider": "fixture",
                "capability_json": "{}",
            })
            with pytest.raises(ValueError, match="capability digest does not match"):
                connection.execute(sa.insert(MarketDataCapabilityProfile).values(
                    owner_id="owner-inline", digest=CAPABILITY, provider="fixture", capability_json="{}",
                ))
            with pytest.raises(ValueError, match="capability digest does not match"):
                connection.execute(sa.insert(MarketDataCapabilityProfile).values([
                    {"owner_id": "owner-inline-a", "digest": MULTI_CAPABILITY_DIGEST,
                     "provider": "fixture", "capability_json": MULTI_CAPABILITY_JSON},
                    {"owner_id": "owner-inline-b", "digest": ADDRESS,
                     "provider": "fixture", "capability_json": "{}"},
                ]))
            with pytest.raises(ValueError, match="capability digest does not match"):
                connection.execute(sa.insert(MarketDataCapabilityProfile), [
                    {"owner_id": "owner-inline-a", "digest": MULTI_CAPABILITY_DIGEST,
                     "provider": "fixture", "capability_json": MULTI_CAPABILITY_JSON},
                    {"owner_id": "owner-inline-b", "digest": ADDRESS,
                     "provider": "fixture", "capability_json": "{}"},
                ])
            safe_capability = {"nested": {"classification": "public"}, "segments": [{"name": "primary"}]}
            safe_encoded = json.dumps(safe_capability, sort_keys=True, separators=(",", ":"))
            safe_digest = "sha256:" + hashlib.sha256(safe_encoded.encode()).hexdigest()
            connection.execute(sa.insert(MarketDataCapabilityProfile), {
                "owner_id": "owner-safe", "digest": safe_digest, "provider": "fixture",
                "capability_json": safe_encoded,
            })
            assert connection.scalar(sa.text(
                "SELECT phase4_json_has_secret_key(CAST(:payload AS jsonb))"
            ), {"payload": safe_encoded}) is False
            nested_secret = r'{"nested":{"\u0061pi_key":"forbidden"}}'
            assert connection.scalar(sa.text(
                "SELECT phase4_json_has_secret_key(CAST(:payload AS jsonb))"
            ), {"payload": nested_secret}) is True
            with pytest.raises((sa.exc.DBAPIError, ValueError)):
                with connection.begin_nested():
                    connection.execute(sa.insert(MarketDataCapabilityProfile), {
                        "owner_id": "owner-b", "digest": CAPABILITY, "provider": "fixture",
                        "capability_json": r'{"\u0061pi_key":"forbidden"}',
                    })
            with pytest.raises((sa.exc.DBAPIError, ValueError)):
                with connection.begin_nested():
                    connection.execute(sa.insert(MarketDataCapabilityProfile), {
                        "owner_id": "owner-nested", "digest": CAPABILITY, "provider": "fixture",
                        "capability_json": nested_secret,
                    })
            with pytest.raises(sa.exc.DBAPIError, match="immutable"):
                with connection.begin_nested():
                    connection.execute(sa.text(
                        "UPDATE market_truth_snapshots SET quality='UNKNOWN' WHERE digest=:digest"
                    ), {"digest": TRUTH})

        with execution.connect() as execution_connection, research.begin() as research_connection:
            manifest = _manifest_values()
            with pytest.raises(ValueError, match="dataset manifest digest does not match"):
                research_connection.execute(sa.insert(DatasetManifest).values(
                    **{**manifest, "digest": ADDRESS},
                ))
            with pytest.raises(ValueError, match="dataset manifest digest does not match"):
                research_connection.execute(sa.insert(DatasetManifest).values([
                    _manifest_values(owner_id="owner-inline-a", market_truth_digest=TRUTH,
                                     capability_digest=EMPTY_DIGEST),
                    {**_manifest_values(owner_id="owner-inline-b", market_truth_digest=TRUTH,
                                        capability_digest=EMPTY_DIGEST), "digest": CAPABILITY},
                ]))
            with pytest.raises(ValueError, match="dataset manifest digest does not match"):
                research_connection.execute(sa.insert(DatasetManifest), [
                    _manifest_values(owner_id="owner-inline-a", market_truth_digest=TRUTH,
                                     capability_digest=EMPTY_DIGEST),
                    {**_manifest_values(owner_id="owner-inline-b", market_truth_digest=TRUTH,
                                        capability_digest=EMPTY_DIGEST), "digest": CAPABILITY},
                ])
            with pytest.raises(ValueError, match="market-truth"):
                persist_dataset_manifest(execution_connection, research_connection, owner_id="owner-a", values=_manifest_values(market_truth_digest=ADDRESS))
            with pytest.raises(ValueError, match="authoritative owner"):
                persist_dataset_manifest(execution_connection, research_connection, owner_id="owner-a", values=_manifest_values(owner_id="owner-b"))
            with pytest.raises(ValueError, match="not owned"):
                persist_dataset_manifest(execution_connection, research_connection, owner_id="owner-b", values=_manifest_values(owner_id="owner-b"))
            with pytest.raises(ValueError, match="not owned"):
                persist_dataset_manifest(execution_connection, research_connection, owner_id="owner-a", values=_manifest_values(provider="other"))
            with pytest.raises(ValueError, match="digest does not match"):
                tampered = json.loads(manifest["manifest_json"])
                tampered["extra"] = True
                persist_dataset_manifest(execution_connection, research_connection, owner_id="owner-a", values={
                    **manifest, "manifest_json": json.dumps(tampered, sort_keys=True, separators=(",", ":")),
                })
            persist_dataset_manifest(execution_connection, research_connection, owner_id="owner-a", values=manifest)
            safe_manifest = _manifest_values(owner_id="owner-safe", capability_digest=safe_digest, extra={
                "nested": {"classification": "public"}, "segments": [{"name": "primary"}],
            })
            persist_dataset_manifest(execution_connection, research_connection, owner_id="owner-safe", values=safe_manifest)
            nested_manifest = _manifest_values(owner_id="owner-nested", extra={
                "nested": {"api_key": "forbidden"},
            })
            nested_manifest_json = nested_manifest["manifest_json"].replace('"api_key"', r'"\u0061pi_key"')
            assert research_connection.scalar(sa.text(
                "SELECT phase4_json_has_secret_key(CAST(:payload AS jsonb))"
            ), {"payload": nested_manifest_json}) is True
            with pytest.raises((sa.exc.DBAPIError, ValueError)):
                with research_connection.begin_nested():
                    research_connection.execute(sa.insert(DatasetManifest), {
                        **nested_manifest, "manifest_json": nested_manifest_json,
                    })
            with pytest.raises(sa.exc.DBAPIError, match="immutable"):
                with research_connection.begin_nested():
                    research_connection.execute(sa.text(
                        "UPDATE research_dataset_manifests SET provider='other' WHERE owner_id='owner-a'"
                    ))

        with execution.connect() as execution_connection, research.connect() as research_connection:
            assert execution_connection.scalar(sa.text(
                "SELECT count(*) FROM market_truth_snapshots WHERE digest=:digest"
            ), {"digest": TRUTH}) == 1
            assert execution_connection.scalar(sa.text(
                "SELECT count(*) FROM market_data_capability_profiles "
                "WHERE owner_id='owner-a' AND digest=:digest"
            ), {"digest": EMPTY_DIGEST}) == 1
            assert research_connection.scalar(sa.text(
                "SELECT count(*) FROM research_dataset_manifests "
                "WHERE owner_id='owner-a' AND market_truth_digest=:truth "
                "AND capability_digest=:capability"
            ), {"truth": TRUTH, "capability": EMPTY_DIGEST}) == 1

        with execution.begin() as connection:
            with pytest.raises(RuntimeError, match="refuses destructive"):
                command.downgrade(execution_migrate.alembic_config(connection), "0035")
        assert execution_migrate.schema_version(execution) == "0036"
        # A supported prior state must upgrade cleanly to the exact current
        # head; afterwards init_schema is a validated no-op at head.
        with execution.begin() as connection:
            command.upgrade(execution_migrate.alembic_config(connection), execution_head)
        assert execution_migrate.schema_version(execution) == execution_head
        with execution.connect() as connection:
            assert connection.scalar(sa.text(
                "SELECT count(*) FROM market_truth_snapshots WHERE digest=:digest"
            ), {"digest": TRUTH}) == 1
        assert execution_migrate.init_schema(
            execution, create_all=lambda: Base.metadata.create_all(execution),
            legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
            expected_tables=Base.metadata.tables,
        ) == execution_head
        with pytest.raises(ResearchMigrationError, match="refuses destructive"):
            downgrade_research_db(research)
        init_research_db(research)
        with research.connect() as connection:
            assert connection.scalar(sa.text("SELECT version FROM research_schema_version")) == RESEARCH_HEAD
            assert connection.scalar(sa.text(
                "SELECT count(*) FROM research_dataset_manifests WHERE owner_id='owner-a'"
            )) == 1

        execution.dispose()
        research.dispose()
        dump, restore = resolve_postgresql16_tools()
        execution_dump = tmp_path / "execution.dump"
        research_dump = tmp_path / "research.dump"
        for url, artifact in ((execution_url, execution_dump), (research_url, research_dump)):
            run_process_spec(postgres_process_spec(url, executable=dump, action="dump", artifact=artifact))
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{execution_schema}" CASCADE'))
            connection.execute(sa.text(f'DROP SCHEMA "{research_schema}" CASCADE'))
        for url, artifact in ((execution_url, execution_dump), (research_url, research_dump)):
            run_process_spec(postgres_process_spec(url, executable=restore, action="restore", artifact=artifact))

        execution = sa.create_engine(execution_url, future=True)
        research = sa.create_engine(research_url, future=True)
        assert execution_migrate.schema_version(execution) == execution_head
        init_research_db(research)
        assert execution_migrate.init_schema(
            execution, create_all=lambda: Base.metadata.create_all(execution),
            legacy_migrate=lambda: (_ for _ in ()).throw(AssertionError("legacy path")),
            expected_tables=Base.metadata.tables,
        ) == execution_head
        with research.connect() as connection:
            assert connection.scalar(sa.text("SELECT version FROM research_schema_version")) == RESEARCH_HEAD
            assert connection.scalar(sa.text(
                "SELECT count(*) FROM research_dataset_manifests WHERE owner_id='owner-a'"
            )) == 1
    finally:
        execution.dispose()
        research.dispose()
        execution_empty.dispose()
        research_empty.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{execution_schema}" CASCADE'))
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{research_schema}" CASCADE'))
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{execution_empty_schema}" CASCADE'))
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{research_empty_schema}" CASCADE'))
        admin.dispose()
