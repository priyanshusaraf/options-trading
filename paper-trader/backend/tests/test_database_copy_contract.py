from __future__ import annotations

from pathlib import Path
import datetime as dt
import base64
import hashlib
import json
import os
import uuid
import shutil
from copy import deepcopy

import pytest
import sqlalchemy as sa


def test_copy_refuses_a_missing_sqlite_source_before_opening_any_destination(tmp_path: Path):
    from app.db.copy_contract import CopyPlane, CopyRefusal, copy_planes

    opened: list[str] = []
    plane = CopyPlane(
        name="execution",
        source_path=tmp_path / "missing.db",
        destination_url="postgresql+psycopg://app:secret@db/strategy",
        metadata=object(),
        marker_table="alembic_version",
        source_head="head",
        initialize_destination=lambda _engine: opened.append("destination"),
        validate_destination=lambda _engine: None,
    )

    with pytest.raises(CopyRefusal, match="missing SQLite source"):
        copy_planes([plane])

    assert opened == []


def test_source_opener_is_read_only_and_refuses_unknown_tables(tmp_path: Path):
    from app.db.copy_contract import (CopyPlane, CopyRefusal, _source_engine,
                                      _validate_source_schema)
    from app.ledger.db import LedgerBase, init_ledger_db, make_engine
    from app.ledger import models as _models  # noqa: F401

    path = tmp_path / "ledger.db"
    writer = make_engine(str(path))
    init_ledger_db(writer)
    with writer.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE leftover_copy_payload (id INTEGER)")
    writer.dispose()
    source = _source_engine(path)
    try:
        with pytest.raises(sa.exc.OperationalError, match="readonly"):
            with source.begin() as connection:
                connection.exec_driver_sql("CREATE TABLE forbidden_write (id INTEGER)")
        plane = CopyPlane("ledger", path, "postgresql://x@y/z", LedgerBase.metadata,
                          None, "unversioned/current-model-validated",
                          lambda _engine: None, lambda _engine: None)
        with pytest.raises(CopyRefusal, match="extra=.*leftover_copy_payload"):
            _validate_source_schema(plane, source)
    finally:
        source.dispose()


def test_report_content_address_refuses_mutation():
    from app.db.copy_contract import CopyRefusal, verify_report_content_address
    import hashlib
    import json

    unsigned = {"cutover_ready": True, "planes": []}
    report = dict(unsigned)
    report["content_address"] = "sha256:" + hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    verify_report_content_address(report)
    report["cutover_ready"] = False
    with pytest.raises(CopyRefusal, match="content address"):
        verify_report_content_address(report)


def test_typed_row_digest_canonicalizes_a_non_null_sql_date():
    from app.db.copy_contract import _row_digest
    from app.db.models import Base

    table = Base.metadata.tables["deployments"]
    row = {column.name: None for column in table.columns}
    row.update({
        "owner_id": "org-a", "id": 1, "name": "book", "broker_account_id": "account-a",
        "universe_mode": "legacy", "params_json": "{}", "status": "active",
        "armed": False, "halted_on": dt.date(2026, 8, 13), "notes": "",
        "created_at": dt.datetime(2026, 8, 13, 10, 0),
        "updated_at": dt.datetime(2026, 8, 13, 10, 0),
    })

    first = _row_digest(table, row)
    row["halted_on"] = dt.date(2026, 8, 14)

    assert len(first) == 64
    assert _row_digest(table, row) != first


def _execution_relationship_fixture():
    from app.db.models import Base

    engine = sa.create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    now = dt.datetime(2026, 8, 13, 10, 0)
    with engine.begin() as connection:
        for suffix in ("a", "b"):
            owner, user, account = f"org-{suffix}", f"user-{suffix}", f"account-{suffix}"
            connection.execute(Base.metadata.tables["organizations"].insert(), {
                "organization_id": owner, "name": owner, "status": "active",
                "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["users"].insert(), {
                "user_id": user, "email_normalized": f"{suffix}@example.test",
                "display_name": suffix, "status": "active", "created_at": now,
                "updated_at": now})
            connection.execute(Base.metadata.tables["memberships"].insert(), {
                "organization_id": owner, "user_id": user, "role": "owner",
                "status": "active", "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["user_sessions"].insert(), {
                "session_id": f"session-{suffix}", "token_digest": suffix * 64,
                "user_id": user, "organization_id": owner, "issued_at": now,
                "expires_at": now + dt.timedelta(days=1)})
            connection.execute(Base.metadata.tables["broker_accounts"].insert(), {
                "broker_account_id": account, "owner_id": owner, "broker": "mock",
                "external_account_id": suffix, "display_name": suffix,
                "status": "active", "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["broker_connections"].insert(), {
                "id": 1 if suffix == "a" else 2, "owner_id": owner,
                "broker_account_id": account, "broker": "mock", "scope": "trade",
                "label": suffix, "capabilities_json": "[]", "status": "active",
                "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["deployments"].insert(), {
                "id": 1 if suffix == "a" else 2, "owner_id": owner, "name": suffix,
                "broker_account_id": account, "universe_mode": "legacy",
                "params_json": "{}", "status": "active", "armed": False,
                "notes": "", "created_at": now, "updated_at": now})
    return engine, now


def test_execution_relationship_validator_refuses_cross_tenant_deployment_link():
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base

    engine, now = _execution_relationship_fixture()
    try:
        with engine.begin() as connection:
            connection.execute(Base.metadata.tables["execution_intents"].insert(), {
                "client_intent_id": "intent-a", "deployment_id": 2,
                "owner_id": "org-a", "broker_account_id": "account-a", "broker": "mock",
                "account_scope": "a", "connection_scope": "trade",
                "broker_tag": "tag-a", "intent": "ENTRY", "instrument_key": "ABC",
                "tradingsymbol": "ABC", "exchange": "NSE", "side": "BUY",
                "order_type": "MARKET", "requested_qty": 1,
                "context_json": "{}", "created_at": now})
            with pytest.raises(CopyRefusal, match="execution_intents.*deployment"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


def test_execution_relationship_validator_refuses_cross_tenant_oauth_links():
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base

    engine, now = _execution_relationship_fixture()
    try:
        with engine.begin() as connection:
            connection.execute(Base.metadata.tables["oauth_callback_states"].insert(), {
                "state_digest": "c" * 64, "connection_id": 2, "session_id": "session-b",
                "user_id": "user-a", "organization_id": "org-a", "created_at": now,
                "expires_at": now + dt.timedelta(minutes=5)})
            with pytest.raises(CopyRefusal, match="oauth_callback_states"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


def test_execution_relationship_validator_refuses_wrong_external_account_scope():
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base

    engine, now = _execution_relationship_fixture()
    try:
        with engine.begin() as connection:
            connection.execute(Base.metadata.tables["execution_intents"].insert(), {
                "client_intent_id": "intent-a", "deployment_id": 1,
                "owner_id": "org-a", "broker_account_id": "account-a", "broker": "mock",
                "account_scope": "WRONG-EXTERNAL-ACCOUNT", "connection_scope": "trade",
                "broker_tag": "tag-a", "intent": "ENTRY", "instrument_key": "ABC",
                "tradingsymbol": "ABC", "exchange": "NSE", "side": "BUY",
                "order_type": "MARKET", "requested_qty": 1,
                "context_json": "{}", "created_at": now})
            with pytest.raises(CopyRefusal, match="execution_intents.*broker_accounts"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


def test_position_intent_link_cannot_cross_deployments_within_one_account():
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base

    engine, now = _execution_relationship_fixture()
    try:
        with engine.begin() as connection:
            connection.execute(Base.metadata.tables["deployments"].insert(), {
                "id": 3, "owner_id": "org-a", "name": "other-book",
                "broker_account_id": "account-a", "universe_mode": "legacy",
                "params_json": "{}", "status": "active", "armed": False,
                "notes": "", "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["execution_intents"].insert(), {
                "client_intent_id": "intent-a", "deployment_id": 1,
                "owner_id": "org-a", "broker_account_id": "account-a", "broker": "mock",
                "account_scope": "a", "connection_scope": "trade", "broker_tag": "tag-a",
                "intent": "ENTRY", "instrument_key": "ABC", "tradingsymbol": "ABC",
                "exchange": "NSE", "side": "BUY", "order_type": "MARKET",
                "requested_qty": 1, "context_json": "{}", "created_at": now})
            connection.execute(Base.metadata.tables["positions"].insert(), {
                "id": 1, "owner_id": "org-a", "broker_account_id": "account-a",
                "deployment_id": 3, "entry_intent_id": "intent-a",
                "instrument_key": "ABC", "direction": "LONG", "option_type": "CE",
                "tradingsymbol": "ABC", "exchange": "NSE", "strike": 100.0,
                "expiry": dt.date(2026, 8, 27), "lot_size": 1, "qty": 1,
                "entry_premium": 10.0, "entry_charges": 0.0, "entry_cost": 10.0,
                "entry_spot": 100.0, "entry_time": now, "stop_price": 5.0,
                "target_price": 20.0})
            with pytest.raises(CopyRefusal, match="positions.*execution_intents"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


@pytest.mark.parametrize("table_name", ("ir_paper_deployments", "ir_shadow_deployments"))
def test_ir_deployment_requires_same_owner_graph_version_and_content_address(table_name: str):
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base
    from app.ir.hashing import canonical_json, content_address

    engine, now = _execution_relationship_fixture()
    graph = {"identifier": "graph-a", "version": 1}
    graph_json = canonical_json(graph)
    try:
        with engine.begin() as connection:
            connection.execute(Base.metadata.tables["projects"].insert(), {
                "project_id": "project-a", "owner_id": "org-a", "name": "project-a",
                "description": "", "status": "active", "created_at": now,
                "updated_at": now})
            connection.execute(Base.metadata.tables["graph_artifacts"].insert(), {
                "owner_id": "org-a", "identifier": "graph-a", "project_id": "project-a",
                "display_name": "graph", "draft_json": graph_json, "draft_revision": 1,
                "published_revision": 1, "current_version": 1,
                "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["graph_versions"].insert(), {
                "owner_id": "org-a", "graph_identifier": "graph-a", "version": 1,
                "artifact_json": graph_json, "content_address": content_address(graph),
                "visibility": "PRIVATE", "created_at": now})
            connection.execute(Base.metadata.tables[table_name].insert(), {
                "id": 20 if table_name == "ir_paper_deployments" else 21,
                "project_id": "project-a", "graph_identifier": "graph-a",
                "graph_version": 1, "graph_content_address": "sha256:" + "0" * 64,
                "evidence_content_address": "sha256:" + "0" * 64,
                "deployment_id": 1, "instrument_key": "ABC", "interval": "15minute",
                "strategy_key": "graph-a", "owner_id": "org-a",
                "broker_account_id": "account-a", "created_at": now, "updated_at": now})
            with pytest.raises(CopyRefusal, match=f"{table_name}.*graph_versions"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


def test_deployment_watchlist_must_belong_to_same_owner():
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base

    engine, now = _execution_relationship_fixture()
    try:
        with engine.begin() as connection:
            connection.execute(Base.metadata.tables["watchlists"].insert(), {
                "id": 10, "owner_id": "org-b", "name": "foreign", "strategy_key": "trend",
                "status": "active", "notes": "", "created_at": now})
            connection.execute(sa.update(Base.metadata.tables["deployments"]).where(
                Base.metadata.tables["deployments"].c.id == 1
            ).values(watchlist_id=10))
            with pytest.raises(CopyRefusal, match="deployments.*watchlists"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


def test_strategy_lifecycle_watchlist_must_belong_to_same_owner():
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base

    engine, now = _execution_relationship_fixture()
    try:
        with engine.begin() as connection:
            connection.execute(Base.metadata.tables["watchlists"].insert(), {
                "id": 10, "owner_id": "org-b", "name": "foreign", "strategy_key": "trend",
                "status": "active", "notes": "", "created_at": now})
            connection.execute(Base.metadata.tables["strategy_lifecycle"].insert(), {
                "id": 1, "owner_id": "org-a", "strategy_key": "trend",
                "status": "running", "source": "builtin", "deployed_watchlist_id": 10,
                "note": "", "created_at": now, "updated_at": now})
            with pytest.raises(CopyRefusal, match="strategy_lifecycle.*watchlists"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


def test_execution_relationship_validator_refuses_active_session_on_revoked_membership():
    from app.db.copy_contract import CopyRefusal, _validate_semantic_ownership
    from app.db.models import Base

    engine, _now = _execution_relationship_fixture()
    try:
        with engine.begin() as connection:
            connection.execute(sa.update(Base.metadata.tables["memberships"]).where(
                Base.metadata.tables["memberships"].c.organization_id == "org-a"
            ).values(status="revoked"))
            with pytest.raises(CopyRefusal, match="active user_sessions"):
                _validate_semantic_ownership(connection, Base.metadata)
    finally:
        engine.dispose()


def test_destination_redaction_is_independent_of_credentials_and_secret_query_values():
    from app.db.copy_contract import _redacted_destination

    first = _redacted_destination(
        "postgresql+psycopg://alice:first-secret@db.example/strategy"
        "?options=-csearch_path%3Dexecution&sslpassword=query-secret-one"
    )
    second = _redacted_destination(
        "postgresql+psycopg://bob:second-secret@db.example/strategy"
        "?options=-csearch_path%3Dexecution&sslpassword=query-secret-two"
    )

    assert first == second
    assert all(secret not in first for secret in (
        "alice", "bob", "first-secret", "second-secret", "query-secret",
    ))


def test_nonempty_later_destination_is_refused_before_earlier_initialization(tmp_path: Path):
    from app.db.copy_contract import CopyPlane, CopyRefusal, copy_planes
    from app.ledger.db import LedgerBase, init_ledger_db, make_engine
    from app.ledger import models as _models  # noqa: F401

    source_path = tmp_path / "ledger.db"
    source = make_engine(str(source_path))
    init_ledger_db(source)
    source.dispose()
    second_source = tmp_path / "ledger-2.db"
    shutil.copyfile(source_path, second_source)
    initialized: list[str] = []
    # SQLite URLs are rejected as destinations before initialization too. This
    # pins the all-plane preflight ordering without needing an external server.
    planes = [CopyPlane(
        name=f"ledger-{index}", source_path=path,
        destination_url=f"sqlite:///{tmp_path / f'destination-{index}.db'}",
        metadata=LedgerBase.metadata, marker_table=None,
        source_head="unversioned/current-model-validated",
        initialize_destination=lambda _engine: initialized.append("called"),
        validate_destination=lambda _engine: None,
    ) for index, path in enumerate((source_path, second_source))]
    with pytest.raises(CopyRefusal, match="explicit PostgreSQL"):
        copy_planes(planes)
    assert initialized == []


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_live_copy_preserves_two_tenant_rows_and_refuses_second_invocation(
    tmp_path: Path, monkeypatch,
):
    from app.db.copy_contract import (CopyRefusal, _validate_cross_plane_semantics,
                                      configured_planes, copy_planes, verify_planes)
    from app.db.engine import configure_connection_profile, create_database_engine
    from app.db.models import Base
    from app.db import migrate
    from app.ledger.db import init_ledger_db, make_engine as ledger_engine
    from app.ledger.models import LedgerArtifact, LedgerManualFill, LedgerSnapshot
    from research.domain.base import init_research_db, make_engine as research_engine
    from research.domain.models import (ExperimentRun, ExperimentSpec, Hypothesis,
                                        OptimizationTrial, ResearchOperation,
                                        ResearchOperationEvent, ResearchOperationItem,
                                        ResearchProgram)
    from research.orchestrator.run import spec_hash
    monkeypatch.setenv("PT_CREDENTIAL_KEY", base64.b64encode(b"k" * 32).decode())
    from app.core.credential_vault import seal
    from app.core.review_snapshot import build_snapshot_manifest
    from app.ir.hashing import canonical_json, content_address

    execution_path = tmp_path / "execution.db"
    research_path = tmp_path / "research.db"
    ledger_path = tmp_path / "ledger.db"
    execution = configure_connection_profile(create_database_engine(f"sqlite:///{execution_path}"))
    migrate.init_schema(execution, create_all=lambda: Base.metadata.create_all(execution),
                        legacy_migrate=lambda: None, expected_tables=Base.metadata.tables)
    now = dt.datetime(2026, 8, 13, 10, 0, 0)
    with execution.begin() as connection:
        for suffix in ("a", "b"):
            owner = f"org-{suffix}"
            user = f"user-{suffix}"
            account = f"account-{suffix}"
            connection.execute(Base.metadata.tables["organizations"].insert(), {
                "organization_id": owner, "name": owner, "status": "active",
                "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["users"].insert(), {
                "user_id": user, "email_normalized": f"{suffix}@example.test",
                "display_name": suffix, "status": "active", "created_at": now,
                "updated_at": now})
            connection.execute(Base.metadata.tables["memberships"].insert(), {
                "organization_id": owner, "user_id": user, "role": "owner",
                "status": "active", "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["user_sessions"].insert(), {
                "session_id": f"session-{suffix}", "token_digest": suffix * 64,
                "user_id": user, "organization_id": owner, "issued_at": now,
                "expires_at": now + dt.timedelta(days=1),
                "revoked_at": now if suffix == "b" else None})
            connection.execute(Base.metadata.tables["broker_accounts"].insert(), {
                "broker_account_id": account, "owner_id": owner, "broker": "mock",
                "external_account_id": suffix, "display_name": suffix,
                "status": "active", "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["capital_state"].insert(), {
                "id": 10 + ord(suffix), "broker_account_id": account, "book": "live",
                "initial_capital": 1000.0, "cash": 900.0,
                "realized_pnl": -100.0, "updated_at": now})
            ciphertext, key_id = seal({"access_token": f"secret-{suffix}"})
            connection.execute(Base.metadata.tables["broker_connections"].insert(), {
                "id": 1 if suffix == "a" else 2, "owner_id": owner,
                "broker_account_id": account, "broker": "mock", "scope": "trade",
                "label": suffix, "capabilities_json": '["orders"]',
                "credential_ciphertext": ciphertext, "credential_key_id": key_id,
                "status": "active", "created_at": now, "updated_at": now})
            deployment_id = 1 if suffix == "a" else 2
            connection.execute(Base.metadata.tables["deployments"].insert(), {
                "id": deployment_id, "owner_id": owner, "name": f"book-{suffix}",
                "broker_account_id": account, "universe_mode": "legacy",
                "params_json": "{}", "status": "active", "armed": False,
                "halted_on": dt.date(2026, 8, 13) if suffix == "b" else None,
                "notes": "", "created_at": now, "updated_at": now})
            intent_id = f"intent-{suffix}"
            connection.execute(Base.metadata.tables["execution_intents"].insert(), {
                "client_intent_id": intent_id, "deployment_id": deployment_id,
                "owner_id": owner, "broker_account_id": account, "broker": "mock",
                "account_scope": suffix, "connection_scope": "trade",
                "broker_tag": f"tag-{suffix}", "intent": "ENTRY",
                "instrument_key": "ABC", "tradingsymbol": "ABC", "exchange": "NSE",
                "side": "BUY", "order_type": "MARKET", "requested_qty": 1,
                "context_json": "{}", "created_at": now})
            connection.execute(Base.metadata.tables["execution_order_events"].insert(), {
                "id": deployment_id, "owner_id": owner, "broker_account_id": account,
                "client_intent_id": intent_id, "source": "broker",
                "source_event_id": f"event-{suffix}", "kind": "acknowledged",
                "broker_status": "OPEN", "cumulative_filled_qty": 0,
                "avg_price": 0.0, "observed_at": now, "payload_json": "{}",
                "anomaly": ""})
            connection.execute(Base.metadata.tables["oauth_callback_states"].insert(), {
                "state_digest": ("c" if suffix == "a" else "d") * 64,
                "connection_id": deployment_id, "session_id": f"session-{suffix}",
                "user_id": user, "organization_id": owner, "created_at": now,
                "expires_at": now + dt.timedelta(minutes=5),
                "consumed_at": now if suffix == "b" else None})
            run_id = 10 + deployment_id
            connection.execute(Base.metadata.tables["backtest_runs"].insert(), {
                "id": run_id, "owner_id": owner, "created_at": now,
                "status": "done" if suffix == "a" else "cancelled",
                "queued_at": now, "started_at": now, "completed_at": now,
                "request_json": "{}", "scope": "liquid", "intervals": "15minute",
                "capital": 50000.0, "total": 1, "done": 1})
            connection.execute(Base.metadata.tables["backtest_results"].insert(), {
                "id": run_id, "owner_id": owner, "run_id": run_id,
                "cell_key": "same-cell", "instrument_key": "ABC", "name": "ABC",
                "segment": "equity", "strategy_key": "trend", "interval": "15minute",
                "params_hash": f"params-{suffix}", "last_candle_ts": 1786595400})
            project_id = f"project-{suffix}"
            connection.execute(Base.metadata.tables["projects"].insert(), {
                "project_id": project_id, "owner_id": owner, "name": project_id,
                "description": "", "status": "active", "created_at": now,
                "updated_at": now})
            graph_document = {"identifier": "same-graph", "version": 1}
            graph_json = canonical_json(graph_document)
            graph_address = content_address(graph_document)
            connection.execute(Base.metadata.tables["graph_artifacts"].insert(), {
                "owner_id": owner, "identifier": "same-graph", "project_id": project_id,
                "display_name": "graph", "draft_json": graph_json, "draft_revision": 1,
                "published_revision": 1, "current_version": 1,
                "created_at": now, "updated_at": now})
            connection.execute(Base.metadata.tables["graph_versions"].insert(), {
                "owner_id": owner, "graph_identifier": "same-graph", "version": 1,
                "artifact_json": graph_json, "content_address": graph_address,
                "visibility": "PRIVATE", "created_at": now})
            snapshot = build_snapshot_manifest(project_id, {
                "events": [], "queues": {"review_needed_runs": [],
                "pending_candidates": [], "active_findings": []}, "source_errors": [],
            }, [])
            manifest_json = canonical_json(snapshot.manifest)
            connection.execute(Base.metadata.tables["project_review_snapshots"].insert(), {
                "owner_id": owner, "snapshot_id": f"snapshot-{suffix}",
                "project_id": project_id, "label": "cutover",
                "capture_key": f"00000000-0000-0000-0000-00000000000{deployment_id}",
                "manifest_json": manifest_json,
                "content_address": snapshot.content_address, "created_by": user,
                "capture_started_at": now, "capture_completed_at": now})
        public_payload = '{"version":1,"result":{}}'
        connection.execute(Base.metadata.tables["backtest_computations"].insert(), {
            "execution_address": "e" * 64, "dataset_address": "f" * 64,
            "strategy_key": "public", "strategy_version": "v1",
            "policy_address": "e" * 64, "schema_version": 1,
            "payload_json": public_payload,
            "payload_digest": hashlib.sha256(public_payload.encode()).hexdigest()})
    execution.dispose()

    research = research_engine(str(research_path))
    init_research_db(research)
    with research.begin() as connection:
        connection.execute(sa.insert(ResearchProgram), [
            {"id": 1, "owner_id": "org-a", "name": "program-a", "thesis": "a",
             "status": "active", "created_at": now},
            {"id": 2, "owner_id": "org-b", "name": "program-b", "thesis": "b",
             "status": "active", "created_at": now},
        ])
        connection.execute(sa.insert(ResearchOperation), [
            {"owner_id": owner, "operation_id": "same-local-id", "trigger": "manual",
             "plan_json": "{}", "status": "pending", "stage": "startup",
             "build": "test", "provider_mode": "mock", "completed_run_ids_json": "[]",
             "created_at": now, "queued_at": now, "attempt_count": 0}
            for owner in ("org-a", "org-b")])
        for index, owner in enumerate(("org-a", "org-b"), start=1):
            connection.execute(sa.insert(Hypothesis), {
                "id": index, "owner_id": owner, "program_id": index,
                "statement": "claim", "status": "open", "retest_priority": 1.0,
                "created_at": now})
            connection.execute(sa.insert(ExperimentSpec), {
                    "owner_id": owner, "id": spec_hash({}), "hypothesis_id": index,
                "recipe_json": "{}", "git_commit": "abc", "qualifier_version": "1",
                "optimizer_version": "1", "validator_version": "1",
                "scoring_version": "1", "rng_seed": 7, "created_at": now})
            connection.execute(sa.insert(ExperimentRun), {
                    "id": index, "owner_id": owner, "spec_id": spec_hash({}),
                "status": "completed", "decision": "archive", "spent_bar_seconds": 2.5,
                "error": "", "started_at": now, "completed_at": now, "created_at": now})
            connection.execute(sa.insert(OptimizationTrial), {
                "id": index, "owner_id": owner, "run_id": index,
                "instrument_key": "ABC", "fold_index": 0, "params_json": "{}",
                "is_objective": 0.5, "is_trades": 2, "oos_trades": 1,
                "selected": True, "created_at": now})
            connection.execute(sa.insert(ResearchOperationItem), {
                "owner_id": owner, "operation_id": "same-local-id", "item_key": "same-item",
                "ordinal": 0, "status": "completed", "run_id": index, "completed_at": now})
            connection.execute(sa.insert(ResearchOperationEvent), {
                "owner_id": owner, "operation_id": "same-local-id", "sequence": 1,
                "event_type": "completed", "stage": "completed", "payload_json": "{}",
                "created_at": now})
    research.dispose()

    ledger = ledger_engine(str(ledger_path))
    init_ledger_db(ledger)
    with ledger.begin() as connection:
        for suffix in ("a", "b"):
            owner, account = f"org-{suffix}", f"account-{suffix}"
            connection.execute(sa.insert(LedgerSnapshot), {
                "owner_id": owner, "broker_account_id": account, "id": 1,
                "version": 3, "payload": '{"raw":"unchanged"}', "updated_at": now})
            connection.execute(sa.insert(LedgerArtifact), {
                "owner_id": owner, "broker_account_id": account, "id": "same-local-id",
                "mime": "image/png", "bytes": b"\x00secret-artifact\xff", "created_at": now})
            connection.execute(sa.insert(LedgerManualFill), {
                "owner_id": owner, "broker_account_id": account, "order_id": "same-local-id",
                "tradingsymbol": "ABC", "side": "BUY", "qty": 1, "avg_price": 12.5,
                "verdict": "pending", "raw": '{"token":"must-not-report"}',
                "claimed_trade": "trade-1" if suffix == "a" else None, "seen_at": now})
    ledger.dispose()

    base = os.environ["PT_TEST_POSTGRES_URL"]
    admin = sa.create_engine(base)
    schemas = {name: f"task4_{name}_{uuid.uuid4().hex}" for name in ("execution", "research", "ledger")}
    with admin.begin() as connection:
        for schema in schemas.values():
            connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    def url(name: str) -> str:
        return str(sa.engine.make_url(base).update_query_dict(
            {"options": f"-csearch_path={schemas[name]}"}))
    planes = configured_planes(
        execution_source=execution_path, execution_destination=url("execution"),
        research_source=research_path, research_destination=url("research"),
        ledger_source=ledger_path, ledger_destination=url("ledger"))
    try:
        report = copy_planes(planes, batch_size=1)
        assert report["cutover_ready"] is True
        assert report["workload_rows"] == 57
        serialized = str(report)
        assert "must-not-report" not in serialized
        assert "secret-artifact" not in serialized
        assert "same-local-id" not in serialized
        verify_planes(planes, report)
        ledger_destination = sa.create_engine(url("ledger"))
        with ledger_destination.begin() as connection:
            connection.execute(sa.text(
                "UPDATE ledger_snapshot SET owner_id='org-missing' WHERE owner_id='org-a'"
            ))
        with pytest.raises(CopyRefusal, match="ledger.*execution broker account"):
            _validate_cross_plane_semantics(planes)
        with ledger_destination.begin() as connection:
            connection.execute(sa.text(
                "UPDATE ledger_snapshot SET owner_id='org-a' WHERE owner_id='org-missing'"
            ))
        ledger_destination.dispose()

        research_destination = sa.create_engine(url("research"))
        with research_destination.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO research_program "
                "(id, owner_id, name, thesis, status, created_at) "
                "VALUES (99, 'org-missing', 'cross-plane-probe', 'probe', "
                "'active', :created_at)"
            ), {"created_at": now})
        with pytest.raises(CopyRefusal, match="research owner.*execution organization"):
            _validate_cross_plane_semantics(planes)
        with research_destination.begin() as connection:
            connection.execute(sa.text(
                "DELETE FROM research_program WHERE id=99"
            ))
        research_destination.dispose()
        _validate_cross_plane_semantics(planes)
        omitted = deepcopy(report)
        omitted["planes"][0]["tables"].pop("option_data")
        with pytest.raises(CopyRefusal, match="digest"):
            verify_planes(planes, omitted)

        execution_destination = sa.create_engine(url("execution"))
        with execution_destination.begin() as connection:
            connection.execute(sa.text(
                "UPDATE capital_state SET cash = cash + 1 WHERE broker_account_id='account-a'"
            ))
        with pytest.raises(CopyRefusal, match="digest"):
            verify_planes(planes, report)
        with execution_destination.begin() as connection:
            connection.execute(sa.text(
                "UPDATE capital_state SET cash = cash - 1 WHERE broker_account_id='account-a'"
            ))
            connection.execute(sa.text(
                "UPDATE broker_accounts SET owner_id='org-b' WHERE broker_account_id='account-a'"
            ))
        with pytest.raises(CopyRefusal, match="ownership"):
            verify_planes(planes, report)
        with execution_destination.begin() as connection:
            connection.execute(sa.text(
                "UPDATE broker_accounts SET owner_id='org-a' WHERE broker_account_id='account-a'"
            ))
            connection.execute(sa.text(
                "UPDATE broker_connections SET credential_key_id=NULL WHERE id=1"
            ))
        with pytest.raises(CopyRefusal, match="credential"):
            verify_planes(planes, report)
        with execution_destination.begin() as connection:
            connection.execute(sa.text(
                "UPDATE broker_connections SET credential_key_id=:key_id WHERE id=1"
            ), {"key_id": key_id})
        execution_destination.dispose()

        research_destination = sa.create_engine(url("research"))
        with research_destination.begin() as connection:
            sequence = connection.execute(sa.text(
                "SELECT pg_get_serial_sequence('research_program', 'id')"
            )).scalar_one()
            connection.execute(sa.text("SELECT setval(CAST(:sequence AS regclass), 1, false)"),
                               {"sequence": sequence})
        with pytest.raises(CopyRefusal, match="sequence"):
            verify_planes(planes, report)
        with research_destination.begin() as connection:
            connection.execute(sa.text("SELECT setval(CAST(:sequence AS regclass), 2, true)"),
                               {"sequence": sequence})
        research_destination.dispose()
        verify_planes(planes, report)

        with pytest.raises(CopyRefusal, match="nonempty"):
            copy_planes(planes, batch_size=1)
    finally:
        with admin.begin() as connection:
            for schema in schemas.values():
                connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_live_copy_refuses_a_source_commit_during_snapshot(tmp_path: Path, monkeypatch):
    from app.db import copy_contract
    from app.db.copy_contract import CopyRefusal, configured_planes, copy_planes
    from app.ledger.db import init_ledger_db, make_engine
    from app.ledger.models import LedgerArtifact

    path = tmp_path / "mutating-ledger.db"
    writer = make_engine(str(path))
    init_ledger_db(writer)
    now = dt.datetime(2026, 8, 13, 10, 0, 0)
    with writer.begin() as connection:
        connection.execute(sa.insert(LedgerArtifact), {
            "owner_id": "org-a", "broker_account_id": "account-a", "id": "before",
            "mime": "image/png", "bytes": b"before", "created_at": now})

    base = os.environ["PT_TEST_POSTGRES_URL"]
    schema = f"task4_mutation_{uuid.uuid4().hex}"
    admin = sa.create_engine(base)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    url = str(sa.engine.make_url(base).update_query_dict(
        {"options": f"-csearch_path={schema}"}))
    plane = configured_planes(
        execution_source=path, execution_destination=url,
        research_source=path, research_destination=url,
        ledger_source=path, ledger_destination=url,
    )[2]
    mutated = False

    def mutate_after_snapshot_begins(_table, _offset, _rows):
        nonlocal mutated
        if not mutated:
            mutated = True
            with writer.begin() as other:
                other.execute(sa.insert(LedgerArtifact), {
                    "owner_id": "org-b", "broker_account_id": "account-b", "id": "after",
                    "mime": "image/png", "bytes": b"after", "created_at": now})

    monkeypatch.setattr(copy_contract, "_source_batch_read", mutate_after_snapshot_begins)
    try:
        with pytest.raises(CopyRefusal, match="source changed"):
            copy_planes([plane])
    finally:
        writer.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_live_copy_refuses_later_plane_change_after_all_plane_preflight(
    tmp_path: Path, monkeypatch,
):
    from app.db import copy_contract
    from app.db.copy_contract import CopyRefusal, configured_planes, copy_planes
    from app.ledger.db import init_ledger_db, make_engine
    from app.ledger.models import LedgerArtifact

    source_paths = [tmp_path / "ledger-one.db", tmp_path / "ledger-two.db"]
    now = dt.datetime(2026, 8, 13, 10, 0)
    for index, path in enumerate(source_paths):
        source = make_engine(str(path))
        init_ledger_db(source)
        with source.begin() as connection:
            connection.execute(sa.insert(LedgerArtifact), {
                "owner_id": f"org-{index}", "broker_account_id": f"account-{index}",
                "id": "before", "mime": "image/png", "bytes": b"before",
                "created_at": now})
        source.dispose()

    base = os.environ["PT_TEST_POSTGRES_URL"]
    schemas = [f"task4_freeze_{uuid.uuid4().hex}" for _ in range(2)]
    admin = sa.create_engine(base)
    with admin.begin() as connection:
        for schema in schemas:
            connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    urls = [str(sa.engine.make_url(base).update_query_dict(
        {"options": f"-csearch_path={schema}"})) for schema in schemas]
    planes = [configured_planes(
        execution_source=path, execution_destination=url,
        research_source=path, research_destination=url,
        ledger_source=path, ledger_destination=url,
    )[2] for path, url in zip(source_paths, urls, strict=True)]

    original_copy_one = copy_contract._copy_one
    copied = 0

    def mutate_later_source_after_first_copy(*args, **kwargs):
        nonlocal copied
        result = original_copy_one(*args, **kwargs)
        copied += 1
        if copied == 1:
            writer = make_engine(str(source_paths[1]))
            with writer.begin() as connection:
                connection.execute(sa.insert(LedgerArtifact), {
                    "owner_id": "org-late", "broker_account_id": "account-late",
                    "id": "after-preflight", "mime": "image/png", "bytes": b"late",
                    "created_at": now})
            writer.dispose()
        return result

    monkeypatch.setattr(copy_contract, "_copy_one", mutate_later_source_after_first_copy)
    try:
        with pytest.raises(CopyRefusal, match="changed since all-plane preflight"):
            copy_planes(planes)
    finally:
        with admin.begin() as connection:
            for schema in schemas:
                connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_live_copy_refuses_first_plane_change_after_its_copy_returns(
    tmp_path: Path, monkeypatch,
):
    from app.db import copy_contract
    from app.db.copy_contract import CopyRefusal, configured_planes, copy_planes
    from app.ledger.db import init_ledger_db, make_engine
    from app.ledger.models import LedgerArtifact

    source_paths = [tmp_path / "plane-one.db", tmp_path / "plane-two.db"]
    now = dt.datetime(2026, 8, 13, 10, 0)
    for index, path in enumerate(source_paths):
        source = make_engine(str(path))
        init_ledger_db(source)
        with source.begin() as connection:
            connection.execute(sa.insert(LedgerArtifact), {
                "owner_id": f"org-{index}", "broker_account_id": f"account-{index}",
                "id": "before", "mime": "image/png", "bytes": b"before",
                "created_at": now})
        source.dispose()
    base = os.environ["PT_TEST_POSTGRES_URL"]
    schemas = [f"task4_postcopy_{uuid.uuid4().hex}" for _ in range(2)]
    admin = sa.create_engine(base)
    with admin.begin() as connection:
        for schema in schemas:
            connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    urls = [str(sa.engine.make_url(base).update_query_dict(
        {"options": f"-csearch_path={schema}"})) for schema in schemas]
    planes = [configured_planes(
        execution_source=path, execution_destination=url,
        research_source=path, research_destination=url,
        ledger_source=path, ledger_destination=url,
    )[2] for path, url in zip(source_paths, urls, strict=True)]
    original_copy_one = copy_contract._copy_one
    calls = 0

    def mutate_first_after_its_copy(*args, **kwargs):
        nonlocal calls
        result = original_copy_one(*args, **kwargs)
        calls += 1
        if calls == 1:
            writer = make_engine(str(source_paths[0]))
            with writer.begin() as connection:
                connection.execute(sa.insert(LedgerArtifact), {
                    "owner_id": "org-late", "broker_account_id": "account-late",
                    "id": "after-copy", "mime": "image/png", "bytes": b"late",
                    "created_at": now})
            writer.dispose()
        return result

    monkeypatch.setattr(copy_contract, "_copy_one", mutate_first_after_its_copy)
    try:
        with pytest.raises(CopyRefusal, match="changed after sequential copy"):
            copy_planes(planes)
    finally:
        with admin.begin() as connection:
            for schema in schemas:
                connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
