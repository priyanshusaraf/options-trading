"""One bounded PG16 logical backup/clean-restore proof across all three planes."""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db import migrate
from app.db.models import (
    EXECUTION_OUTBOX_MODELS, AccountExecutionCommand, AccountExecutionLease,
    BacktestResult, BacktestRun, Base, BrokerAccount, CapitalState, Membership,
    Organization, User, UserSession,
)
from app.backtest import repository as backtest_repository
from app.execution.leases import LeaseRepository, StaleLease
from app.events.outbox import OutboxRepository
from app.db.copy_contract import CopyRefusal, validate_semantic_ownership
from app.db.restore_contract import RestoreRefusal, capture_manifest, configured_restore_planes, verify_restore
from app.events.planes import execution_outbox, ledger_outbox, research_outbox
from app.ledger import models as ledger_models
from app.ledger.db import init_ledger_db, make_engine
from app.operations.postgresql_backup import postgres_process_spec, run_process_spec, sha256_file
from app.operations.postgresql_backup import resolve_postgresql16_tools
from research.domain import models as research_models
from research.domain.base import init_research_db, make_engine as make_research_engine


def _plane_url(base: str, database: str, schema: str) -> str:
    return str(make_url(base).set(database=database).update_query_dict(
        {"options": f"-csearch_path={schema}"}))


def test_pg16_dump_restore_three_plane_generation_is_digest_identical(tmp_path):
    base = os.environ.get("PT_TEST_POSTGRES_URL")
    if not base:
        pytest.skip("PT_TEST_POSTGRES_URL is not configured")
    pg_dump, pg_restore = resolve_postgresql16_tools()
    nonce = uuid.uuid4().hex[:12]
    source_database = f"strategy_os_t7_src_{nonce}"
    target_database = f"strategy_os_t7_dst_{nonce}"
    admin = sa.create_engine(base, isolation_level="AUTOCOMMIT", future=True)
    try:
        with admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{source_database}"'))
            connection.execute(sa.text(f'CREATE DATABASE "{target_database}"'))
        source = {plane: _plane_url(base, source_database, plane)
                  for plane in ("execution", "research", "ledger")}
        target = {plane: _plane_url(base, target_database, plane)
                  for plane in ("execution", "research", "ledger")}
        source_admin = sa.create_engine(make_url(base).set(database=source_database), future=True)
        with source_admin.begin() as connection:
            for schema in source:
                connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        source_admin.dispose()

        execution_engine = sa.create_engine(source["execution"], future=True)
        migrate.init_schema(
            execution_engine, create_all=lambda: Base.metadata.create_all(execution_engine),
            legacy_migrate=lambda: None, expected_tables=Base.metadata.tables)
        research_engine = make_research_engine(source["research"])
        init_research_db(research_engine)
        ledger_engine = make_engine(source["ledger"])
        init_ledger_db(ledger_engine)
        now = dt.datetime.now()
        with execution_engine.begin() as connection:
            connection.execute(sa.insert(Organization), [
                {"organization_id": "org-a", "name": "A", "status": "active",
                 "created_at": now, "updated_at": now},
                {"organization_id": "org-b", "name": "B", "status": "active",
                 "created_at": now, "updated_at": now},
            ])
            connection.execute(sa.insert(User), [
                {"user_id": "user-a", "email_normalized": "a@example.test",
                 "display_name": "A", "status": "active", "created_at": now, "updated_at": now},
                {"user_id": "user-b", "email_normalized": "b@example.test",
                 "display_name": "B", "status": "active", "created_at": now, "updated_at": now},
            ])
            connection.execute(sa.insert(Membership), [
                {"organization_id": "org-a", "user_id": "user-a", "role": "owner",
                 "status": "active", "created_at": now, "updated_at": now},
                {"organization_id": "org-b", "user_id": "user-b", "role": "owner",
                 "status": "active", "created_at": now, "updated_at": now},
            ])
            connection.execute(sa.insert(UserSession), [
                {"session_id": "active", "token_digest": "a" * 64, "user_id": "user-a",
                 "organization_id": "org-a", "issued_at": now,
                 "expires_at": now + dt.timedelta(days=1), "revoked_at": None},
                {"session_id": "revoked", "token_digest": "b" * 64, "user_id": "user-b",
                 "organization_id": "org-b", "issued_at": now - dt.timedelta(days=2),
                 "expires_at": now - dt.timedelta(days=1), "revoked_at": now},
            ])
            connection.execute(sa.insert(BrokerAccount), [
                {"broker_account_id": "acc-a", "owner_id": "org-a", "broker": "fake",
                 "external_account_id": "a", "display_name": "A", "status": "active",
                 "created_at": now, "updated_at": now},
                {"broker_account_id": "acc-b", "owner_id": "org-b", "broker": "fake",
                 "external_account_id": "b", "display_name": "B", "status": "active",
                 "created_at": now, "updated_at": now},
            ])
            connection.execute(sa.insert(CapitalState), [
                {"broker_account_id": "acc-a", "book": "live", "initial_capital": 1000,
                 "cash": 1000, "realized_pnl": 0, "updated_at": now},
                {"broker_account_id": "acc-b", "book": "paper", "initial_capital": 2000,
                 "cash": 2000, "realized_pnl": 0, "updated_at": now},
            ])
        execution_sessions = sessionmaker(execution_engine, future=True, expire_on_commit=False)
        with execution_sessions.begin() as session:
            repo = execution_outbox()
            with repo.writer(session):
                repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id="acc-a", aggregate_type="execution_lease",
                    aggregate_id="acc-a", event_type="execution.lease.changed",
                    schema_version=1, payload={"projection": "execution_status"},
                    producer_key="restore-fixture-execution")
                repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id=None, aggregate_type="backtest_run",
                    aggregate_id="owner-run", event_type="execution.backtest.changed",
                    schema_version=1, payload={"projection": "backtest_runs"},
                    producer_key="restore-fixture-execution-owner")
        with execution_sessions.begin() as session:
            repo = execution_outbox()
            claimed = repo.claim_batch(session, consumer_id="restore-consumer",
                                       lease_owner="source", limit=10, lease_seconds=30)
            assert len(claimed.events) == 2
            for event in claimed.events:
                repo.ack(session, claimed.claim_token, event.event_id,
                         effect_key=f"projection:{event.producer_key}")
            repo.release(session, claimed.claim_token)
        lease_repository = LeaseRepository(execution_sessions)
        old_lease_token = lease_repository.claim(
            owner_id="org-a", broker_account_id="acc-a",
            cell_id="source-cell", worker_id="source-boot")
        lease_repository.activate(old_lease_token, reconciliation_evidence="fixture reconciled")
        prepared = lease_repository.prepare_command(
            old_lease_token, kind="place_order", target_id="intent-ambiguous",
            idempotency_key="restore-ambiguous", request_digest="c" * 64,
            broker_tag="pt-bot", requested_qty=1, requested_side="BUY")
        lease_repository.transition_command(
            old_lease_token, prepared.command_id,
            from_state="prepared", to_state="sent_unknown", error_code="ack_lost")

        job_started = dt.datetime(2026, 8, 13, 0, 0, 0)
        backtest_value = {
            "instrument_key": "NIFTY", "name": "NIFTY", "segment": "nse_delivery",
            "strategy_key": "trend_impulse_v3", "strategy_version": "strategy-v1",
            "interval": "day", "bars": 1, "params_hash": "params-v1", "error": "",
        }
        with execution_sessions.begin() as session:
            run = backtest_repository.enqueue_run(
                session, owner_id="org-a", scope="liquid", intervals="day",
                capital=1000, total=1, now=job_started)
            job_id = run.id
            old_job = backtest_repository.claim_run(
                session, owner_id="org-a", run_id=job_id, claimed_by="source-job",
                now=job_started, lease_seconds=1)
            assert old_job is not None
            old_job_token = old_job.claim_token
        with execution_sessions.begin() as session:
            assert backtest_repository.append_claimed_result_batch(
                session, owner_id="org-a", run_id=job_id,
                claim_token=old_job_token, values=[backtest_value],
                now=job_started + dt.timedelta(milliseconds=100), lease_seconds=1)

        with research_engine.begin() as connection:
            connection.execute(sa.insert(research_models.ResearchProgram), [
                {"owner_id": "org-a", "name": "A"}, {"owner_id": "org-b", "name": "B"}])
            operation_id = "restore-research-op"
            connection.execute(sa.insert(research_models.ResearchOperation), {
                "owner_id": "org-a", "operation_id": operation_id, "trigger": "manual",
                "plan_json": "{}", "status": "running", "stage": "experiments",
                "build": "test-build", "provider_mode": "fake", "completed_run_ids_json": "[]",
                "created_at": now, "queued_at": now, "started_at": now,
                "heartbeat_at": now, "claim_token": "research-old-token",
                "claimed_by": "research-source-worker",
                "claim_expires_at": now + dt.timedelta(seconds=1), "attempt_count": 1})
        research_sessions = sessionmaker(research_engine, future=True)
        with research_sessions.begin() as session:
            repo = research_outbox()
            with repo.writer(session):
                repo.append(session, classification="private", owner_id="org-a",
                            broker_account_id=None, aggregate_type="research_operation",
                            aggregate_id="op-a", event_type="research.operation.changed",
                            schema_version=1, payload={"projection": "research_operation"},
                            producer_key="restore-fixture-research")
        with ledger_engine.begin() as connection:
            connection.execute(sa.insert(ledger_models.LedgerSnapshot), [
                {"owner_id": "org-a", "broker_account_id": "acc-a", "id": 1,
                 "version": 1, "payload": "{}", "updated_at": now},
                {"owner_id": "org-b", "broker_account_id": "acc-b", "id": 1,
                 "version": 1, "payload": "{}", "updated_at": now},
            ])
            artifact_bytes = b"task7-ledger-artifact"
            artifact_id = hashlib.sha256(artifact_bytes).hexdigest()
            connection.execute(sa.insert(ledger_models.LedgerArtifact), {
                "owner_id": "org-a", "broker_account_id": "acc-a", "id": artifact_id,
                "mime": "application/octet-stream", "bytes": artifact_bytes,
                "created_at": now})
        ledger_sessions = sessionmaker(ledger_engine, future=True)
        with ledger_sessions.begin() as session:
            repo = ledger_outbox()
            with repo.writer(session):
                repo.append(session, classification="private", owner_id="org-a",
                            broker_account_id="acc-a", aggregate_type="ledger_snapshot",
                            aggregate_id="1", event_type="ledger.snapshot.changed",
                            schema_version=1, payload={"projection": "ledger_snapshot"},
                            producer_key="restore-fixture-ledger")

        artifacts = {}
        for plane in source:
            artifact = tmp_path / f"{plane}.dump"
            run_process_spec(postgres_process_spec(
                source[plane], executable=pg_dump, action="dump", artifact=artifact))
            artifacts[plane] = {"identifier": artifact.name, "sha256": sha256_file(artifact)}
        started = dt.datetime.now(dt.timezone.utc)
        signing_key = b"local-restore-fixture-signing-key"
        manifest = capture_manifest(
            configured_restore_planes(execution_url=source["execution"],
                                      research_url=source["research"], ledger_url=source["ledger"]),
            generation_id=f"restore-{nonce}", source_build="test-build", artifacts=artifacts,
            maintenance_evidence={"quiesced": True,
                                  "evidence_address": "sha256:" + "e" * 64},
            backup_started_at=started, backup_completed_at=dt.datetime.now(dt.timezone.utc),
            signing_key=signing_key)
        execution_engine.dispose(); research_engine.dispose(); ledger_engine.dispose()

        for plane in target:
            run_process_spec(postgres_process_spec(
                target[plane], executable=pg_restore, action="restore",
                artifact=tmp_path / f"{plane}.dump"))
        report = verify_restore(
            configured_restore_planes(execution_url=target["execution"],
                                      research_url=target["research"], ledger_url=target["ledger"]),
            manifest, signing_key=signing_key, require_signed=True)
        assert report["cutover_ready"] is True
        assert report["execution_recovery_required"] is True
        target_research = make_research_engine(target["research"])
        with target_research.connect() as connection:
            restored_operation = connection.execute(sa.select(
                research_models.ResearchOperation.status,
                research_models.ResearchOperation.claim_token,
                research_models.ResearchOperation.claimed_by).where(
                    research_models.ResearchOperation.owner_id == "org-a",
                    research_models.ResearchOperation.operation_id == operation_id)).one()
            assert restored_operation.status == "running"
            assert restored_operation.claim_token == "research-old-token"
            assert restored_operation.claimed_by == "research-source-worker"
        target_research.dispose()
        restored_planes = configured_restore_planes(
            execution_url=target["execution"], research_url=target["research"],
            ledger_url=target["ledger"])
        mutation_engine = sa.create_engine(target["execution"], future=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE execution_outbox_event "
                "SET broker_account_id='acc-b', scope_key='private:org-a:acc-b' "
                "WHERE producer_key='restore-fixture-execution-owner'"))
        with mutation_engine.connect() as connection:
            with pytest.raises(CopyRefusal, match="broker-account ownership"):
                validate_semantic_ownership(connection, Base.metadata)
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key,
                           require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE execution_outbox_event "
                "SET broker_account_id=NULL, scope_key='private:org-a:*' "
                "WHERE producer_key='restore-fixture-execution-owner'"))
        with mutation_engine.begin() as connection:
            connection.execute(sa.text("UPDATE alembic_version SET version_num='bad-head'"))
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE alembic_version SET version_num=:head"),
                {"head": migrate.head_revision()})
            connection.execute(sa.text(
                "UPDATE capital_state SET cash=cash+1 WHERE broker_account_id='acc-a' AND book='live'"))
        with pytest.raises(RestoreRefusal, match="digest"):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE capital_state SET cash=cash-1 WHERE broker_account_id='acc-a' AND book='live'"))
            sequence = connection.scalar(sa.text(
                "SELECT pg_get_serial_sequence('backtest_runs','id')"))
            connection.execute(sa.text(
                "SELECT setval(CAST(:sequence AS regclass), 1, false)"), {"sequence": sequence})
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "SELECT setval(CAST(:sequence AS regclass), 1, true)"), {"sequence": sequence})
        mutation_engine.dispose()
        ledger_mutation = make_engine(target["ledger"])
        with ledger_mutation.begin() as connection:
            connection.execute(sa.text(
                "UPDATE ledger_snapshot SET owner_id='unknown-owner' WHERE owner_id='org-b'"))
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with ledger_mutation.begin() as connection:
            connection.execute(sa.text(
                "UPDATE ledger_snapshot SET owner_id='org-b' WHERE owner_id='unknown-owner'"))
        ledger_mutation.dispose()
        target_engine = sa.create_engine(target["execution"], future=True)
        target_sessions = sessionmaker(target_engine, future=True)
        with target_sessions.begin() as session:
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.Event)) >= 5
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.StreamHead)) >= 2
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.ConsumerCursor)) == 1
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.ConsumerReceipt)) == 2
            assert session.scalar(sa.select(AccountExecutionLease.fence_epoch).where(
                AccountExecutionLease.owner_id == "org-a",
                AccountExecutionLease.broker_account_id == "acc-a")) == old_lease_token.fence_epoch
            assert session.scalar(sa.select(AccountExecutionCommand.state).where(
                AccountExecutionCommand.command_id == prepared.command_id)) == "sent_unknown"
            assert session.scalar(sa.select(sa.func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == "org-a", BacktestResult.run_id == job_id)) == 1
            restored_repo = execution_outbox()
            with restored_repo.writer(session):
                restored_repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id="acc-a", aggregate_type="execution_lease",
                    aggregate_id="acc-a", event_type="execution.lease.changed",
                    schema_version=1, payload={"projection": "execution_status"},
                    producer_key="restore-fixture-post-restore")
        with target_sessions.begin() as session:
            batch = execution_outbox().claim_batch(
                session, consumer_id="restore-consumer", lease_owner="target",
                limit=10, lease_seconds=30)
            assert len(batch.events) >= 1
            for event in batch.events:
                execution_outbox().ack(
                    session, batch.claim_token, event.event_id,
                    effect_key=f"projection:post-restore:{event.event_id}")
            execution_outbox().release(session, batch.claim_token)
        restored_leases = LeaseRepository(target_sessions)
        new_lease_token = restored_leases.claim_after_restore(
            owner_id="org-a", broker_account_id="acc-a",
            cell_id="target-cell", worker_id="target-boot",
            restore_evidence=report["content_address"])
        assert new_lease_token.fence_epoch == old_lease_token.fence_epoch + 1
        with pytest.raises(StaleLease):
            restored_leases.heartbeat(old_lease_token)
        with target_sessions() as stale_session:
            restored_leases.bind_money_session(stale_session, old_lease_token)
            stale_session.add(CapitalState(
                broker_account_id="acc-a", book="paper", initial_capital=50,
                cash=50, realized_pnl=0, updated_at=dt.datetime.now()))
            with pytest.raises(StaleLease):
                stale_session.commit()
        with target_sessions.begin() as session:
            restored = session.get(AccountExecutionLease, ("org-a", "acc-a"))
            assert restored.state == "recovering"
            assert restored.desired_state == restored.effective_state == "disabled"
            successor = backtest_repository.claim_run(
                session, owner_id="org-a", run_id=job_id, claimed_by="target-job",
                now=job_started + dt.timedelta(seconds=2), lease_seconds=30)
            assert successor is not None and successor.claim_token != old_job_token
            successor_token = successor.claim_token
        with target_sessions.begin() as session:
            assert backtest_repository.append_claimed_result_batch(
                session, owner_id="org-a", run_id=job_id, claim_token=successor_token,
                values=[backtest_value], now=job_started + dt.timedelta(seconds=3))
            assert backtest_repository.complete_claim(
                session, owner_id="org-a", run_id=job_id, claim_token=successor_token,
                status="done", now=job_started + dt.timedelta(seconds=3))
        with target_sessions.begin() as session:
            assert session.scalar(sa.select(sa.func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == "org-a", BacktestResult.run_id == job_id)) == 1
        target_engine.dispose()
        target_ledger = make_engine(target["ledger"])
        with target_ledger.connect() as connection:
            restored_artifact = connection.execute(sa.select(
                ledger_models.LedgerArtifact.id, ledger_models.LedgerArtifact.bytes).where(
                    ledger_models.LedgerArtifact.owner_id == "org-a",
                    ledger_models.LedgerArtifact.broker_account_id == "acc-a")).one()
            assert restored_artifact.id == artifact_id
            assert hashlib.sha256(restored_artifact.bytes).hexdigest() == artifact_id
        target_ledger.dispose()
    finally:
        # Drop only this test's UUID-bound databases, after terminating their
        # own remaining pooled sessions.
        with admin.connect() as connection:
            for database in (source_database, target_database):
                connection.execute(sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:database AND pid <> pg_backend_pid()"), {"database": database})
                connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}"'))
        admin.dispose()
