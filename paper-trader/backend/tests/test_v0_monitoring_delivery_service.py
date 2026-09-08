"""Critical evidence for deterministic unpublished IN_APP delivery commands."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import threading

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import (
    MonitoringAlertAttentionStateRow,
    MonitoringAlertDeliveryAttemptRow,
    MonitoringSignalAlertRow,
)
from app.monitoring.contracts import AlertDeliveryAttempt, DeliveryOutcome
from app.monitoring import delivery_service as delivery_subject
from app.monitoring.delivery_service import (
    MonitoringDeliveryConflict,
    MonitoringDeliveryNotFound,
    MonitoringDeliveryRefusal,
    record_in_app_delivery,
)
from app.monitoring.repository import MonitoringRepository
from tests.test_v0_monitoring_inbox_query import _seed
from tests.test_v0_monitoring_persistence import _engine


ROOT = Path(__file__).resolve().parents[3]


def _request(repository, alert, *, expected_sequence, outcome, when, failure_code=None):
    return record_in_app_delivery(
        repository,
        assignment_id=alert.assignment_id,
        alert_address=alert.address,
        expected_sequence=expected_sequence,
        outcome=outcome,
        occurred_at=when,
        failure_code=failure_code,
    )


def test_delivered_failed_replay_conflict_and_gap_are_deterministic(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    delivered_at = first.alert.event_at + timedelta(minutes=1)
    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        delivered = _request(
            repository, first.alert, expected_sequence=0,
            outcome=DeliveryOutcome.DELIVERED, when=delivered_at,
        )
        failed = _request(
            repository, first.alert, expected_sequence=1,
            outcome=DeliveryOutcome.FAILED,
            when=delivered_at + timedelta(minutes=1),
            failure_code="IN_APP_STORE_UNAVAILABLE",
        )
        assert delivered.replayed is False and delivered.attempt.sequence == 1
        assert failed.replayed is False and failed.attempt.sequence == 2
        session.commit()

    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        replay = _request(
            repository, first.alert, expected_sequence=0,
            outcome=DeliveryOutcome.DELIVERED,
            when=delivered_at + timedelta(days=30),
        )
        assert replay.replayed is True
        assert replay.attempt == delivered.attempt
        with pytest.raises(MonitoringDeliveryConflict, match="outcome or failure"):
            _request(
                repository, first.alert, expected_sequence=0,
                outcome=DeliveryOutcome.FAILED,
                when=delivered_at + timedelta(days=30),
                failure_code="IN_APP_STORE_UNAVAILABLE",
            )
        with pytest.raises(MonitoringDeliveryConflict, match="outcome or failure"):
            _request(
                repository, first.alert, expected_sequence=1,
                outcome=DeliveryOutcome.DELIVERED,
                when=delivered_at + timedelta(days=30),
            )
        with pytest.raises(MonitoringDeliveryConflict, match="sequence"):
            _request(
                repository, first.alert, expected_sequence=4,
                outcome=DeliveryOutcome.DELIVERED,
                when=delivered_at + timedelta(days=30),
            )
        session.rollback()

    with Session(engine) as session:
        rows = session.scalars(sa.select(MonitoringAlertDeliveryAttemptRow).where(
            MonitoringAlertDeliveryAttemptRow.owner_id == "tenant.alpha",
            MonitoringAlertDeliveryAttemptRow.alert_address == first.alert.address,
        ).order_by(MonitoringAlertDeliveryAttemptRow.sequence)).all()
        assert [(row.sequence, row.outcome, row.failure_code) for row in rows] == [
            (1, "DELIVERED", None),
            (2, "FAILED", "IN_APP_STORE_UNAVAILABLE"),
        ]


def test_outer_rollback_removes_delivery_and_service_never_commits(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _request(
            repository, first.alert, expected_sequence=0,
            outcome=DeliveryOutcome.DELIVERED,
            when=first.alert.event_at + timedelta(minutes=1),
        )
        assert session.in_transaction()
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertDeliveryAttemptRow
        )) == 1
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertDeliveryAttemptRow
        )) == 0


def test_divergent_repository_return_rolls_back_the_inner_business_effect(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=1)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        original = repository.append_delivery_attempt

        def divergent(attempt, *, created_at):
            persisted = original(attempt, created_at=created_at)
            return replace(persisted, occurred_at=persisted.occurred_at + timedelta(seconds=1))

        monkeypatch.setattr(repository, "append_delivery_attempt", divergent)
        with pytest.raises(MonitoringDeliveryConflict, match="differs"):
            _request(
                repository, first.alert, expected_sequence=0,
                outcome=DeliveryOutcome.DELIVERED, when=when,
            )
        session.commit()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertDeliveryAttemptRow
        )) == 0


def test_foreign_and_missing_alerts_share_one_private_absence_and_create_nothing(tmp_path):
    engine = _engine(tmp_path)
    first, _second, beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=1)
    with Session(engine) as session:
        alpha = MonitoringRepository(session, owner_id="tenant.alpha")
        errors = []
        for assignment_id, alert_address in (
            (beta.alert.assignment_id, beta.alert.address),
            ("assignment.missing", "sha256:" + "0" * 64),
        ):
            with pytest.raises(MonitoringDeliveryNotFound) as refused:
                record_in_app_delivery(
                    alpha, assignment_id=assignment_id, alert_address=alert_address,
                    expected_sequence=0, outcome=DeliveryOutcome.DELIVERED,
                    occurred_at=when,
                )
            errors.append((type(refused.value), str(refused.value)))
        assert errors == [
            (MonitoringDeliveryNotFound, "monitoring object not found"),
            (MonitoringDeliveryNotFound, "monitoring object not found"),
        ]
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertDeliveryAttemptRow
        )) == 0


def test_failed_delivery_preserves_exact_alert_and_initial_attention_bytes(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    with Session(engine) as session:
        alert_key = (
            "tenant.alpha", first.alert.assignment_id, first.alert.address,
        )
        alert_before = session.get(MonitoringSignalAlertRow, alert_key).canonical_json
        attention_before = session.get(MonitoringAlertAttentionStateRow, alert_key)
        attention_bytes = (
            attention_before.projection_address,
            attention_before.last_sequence,
            attention_before.is_unread,
            attention_before.read_at,
            attention_before.acknowledged_at,
            attention_before.dismissed_at,
        )
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _request(
            repository, first.alert, expected_sequence=0,
            outcome=DeliveryOutcome.FAILED,
            when=first.alert.event_at + timedelta(minutes=1),
            failure_code="IN_APP_STORE_UNAVAILABLE",
        )
        session.commit()
    with Session(engine) as session:
        assert session.get(MonitoringSignalAlertRow, alert_key).canonical_json == alert_before
        attention_after = session.get(MonitoringAlertAttentionStateRow, alert_key)
        assert (
            attention_after.projection_address,
            attention_after.last_sequence,
            attention_after.is_unread,
            attention_after.read_at,
            attention_after.acknowledged_at,
            attention_after.dismissed_at,
        ) == attention_bytes


@pytest.mark.parametrize("different", [False, True])
def test_simultaneous_same_sequence_has_one_created_and_replay_or_conflict(
    tmp_path, different,
):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    barrier = threading.Barrier(2)

    def worker(index):
        with Session(engine, expire_on_commit=False) as session:
            repository = MonitoringRepository(session, owner_id="tenant.alpha")
            barrier.wait()
            outcome = DeliveryOutcome.FAILED if different and index else DeliveryOutcome.DELIVERED
            failure = "IN_APP_STORE_UNAVAILABLE" if outcome is DeliveryOutcome.FAILED else None
            try:
                result = _request(
                    repository, first.alert, expected_sequence=0,
                    outcome=outcome,
                    when=first.alert.event_at + timedelta(minutes=1, seconds=index),
                    failure_code=failure,
                )
                session.commit()
                return "replay" if result.replayed else "created"
            except MonitoringDeliveryConflict:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(worker, range(2)))
    assert results == (["conflict", "created"] if different else ["created", "replay"])
    with Session(engine) as session:
        rows = session.scalars(sa.select(MonitoringAlertDeliveryAttemptRow).where(
            MonitoringAlertDeliveryAttemptRow.owner_id == "tenant.alpha",
            MonitoringAlertDeliveryAttemptRow.alert_address == first.alert.address,
        )).all()
        assert len(rows) == 1 and rows[0].sequence == 1


def test_reservation_and_savepoint_are_active_before_repository_reads(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    original = MonitoringRepository.get_alert

    def guarded(self, assignment_id, alert_address):
        raw = self.session.connection().connection.driver_connection
        assert raw.in_transaction
        assert self.session.in_nested_transaction()
        return original(self, assignment_id, alert_address)

    monkeypatch.setattr(MonitoringRepository, "get_alert", guarded)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _request(
            repository, first.alert, expected_sequence=0,
            outcome=DeliveryOutcome.DELIVERED,
            when=first.alert.event_at + timedelta(minutes=1),
        )
        session.rollback()


def test_exact_types_closed_values_and_failure_coupling_refuse(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=1)
    with pytest.raises(MonitoringDeliveryRefusal, match="exact owner-scoped"):
        record_in_app_delivery(
            object(), assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address, expected_sequence=0,
            outcome=DeliveryOutcome.DELIVERED, occurred_at=when,
        )
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        bad = [
            {"expected_sequence": True},
            {"expected_sequence": -1},
            {"outcome": "DELIVERED"},
            {"occurred_at": when.replace(tzinfo=None)},
            {"failure_code": "FAIL", "outcome": DeliveryOutcome.DELIVERED},
            {"failure_code": "open-code", "outcome": DeliveryOutcome.FAILED},
        ]
        base = {
            "expected_sequence": 0,
            "outcome": DeliveryOutcome.DELIVERED,
            "occurred_at": when,
            "failure_code": None,
        }
        for change in bad:
            with pytest.raises(MonitoringDeliveryRefusal):
                record_in_app_delivery(
                    repository,
                    assignment_id=first.alert.assignment_id,
                    alert_address=first.alert.address,
                    **{**base, **change},
                )
        session.rollback()


def test_arbitrary_uppercase_failure_code_refuses_without_delivery_effect(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        before = (tuple(session.new), tuple(session.dirty), tuple(session.deleted))
        with pytest.raises(MonitoringDeliveryRefusal, match="closed"):
            _request(
                repository, first.alert, expected_sequence=0,
                outcome=DeliveryOutcome.FAILED,
                when=first.alert.event_at + timedelta(minutes=1),
                failure_code="ARBITRARY_UNREGISTERED_CODE",
            )
        assert (tuple(session.new), tuple(session.dirty), tuple(session.deleted)) == before
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertDeliveryAttemptRow
        )) == 0
        session.rollback()


def test_finite_failure_vocabulary_guard_is_killed_and_restored(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=1)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        with monkeypatch.context() as mutation:
            mutation.setattr(
                delivery_subject,
                "_FAILURE_CODES",
                frozenset({
                    "IN_APP_STORE_UNAVAILABLE",
                    "ARBITRARY_UNREGISTERED_CODE",
                }),
            )
            killed = _request(
                repository, first.alert, expected_sequence=0,
                outcome=DeliveryOutcome.FAILED, when=when,
                failure_code="ARBITRARY_UNREGISTERED_CODE",
            )
            assert killed.attempt.failure_code == "ARBITRARY_UNREGISTERED_CODE"
        session.rollback()

        with pytest.raises(MonitoringDeliveryRefusal, match="closed"):
            _request(
                repository, first.alert, expected_sequence=0,
                outcome=DeliveryOutcome.FAILED, when=when,
                failure_code="ARBITRARY_UNREGISTERED_CODE",
            )
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertDeliveryAttemptRow
        )) == 0
        session.rollback()


def test_repository_postcondition_guard_detects_a_divergent_lookup(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    original = MonitoringRepository.get_delivery_attempt
    calls = 0

    def divergent(self, assignment_id, alert_address, sequence):
        nonlocal calls
        calls += 1
        value = original(self, assignment_id, alert_address, sequence)
        if calls == 2:
            return replace(value, occurred_at=value.occurred_at + timedelta(seconds=1))
        return value

    monkeypatch.setattr(MonitoringRepository, "get_delivery_attempt", divergent)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        with pytest.raises(MonitoringDeliveryConflict, match="postcondition"):
            _request(
                repository, first.alert, expected_sequence=0,
                outcome=DeliveryOutcome.DELIVERED,
                when=first.alert.event_at + timedelta(minutes=1),
            )
        session.commit()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertDeliveryAttemptRow
        )) == 0


def test_one_hundred_attempts_are_contiguous_and_bounded(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        for index in range(100):
            result = _request(
                repository, first.alert, expected_sequence=index,
                outcome=(DeliveryOutcome.FAILED if index % 7 == 0
                         else DeliveryOutcome.DELIVERED),
                when=first.alert.event_at + timedelta(seconds=index + 1),
                failure_code=("IN_APP_STORE_UNAVAILABLE" if index % 7 == 0 else None),
            )
            assert result.attempt.sequence == index + 1
        session.commit()
    with Session(engine) as session:
        sequences = session.scalars(sa.select(
            MonitoringAlertDeliveryAttemptRow.sequence,
        ).where(
            MonitoringAlertDeliveryAttemptRow.owner_id == "tenant.alpha",
            MonitoringAlertDeliveryAttemptRow.alert_address == first.alert.address,
        ).order_by(MonitoringAlertDeliveryAttemptRow.sequence)).all()
        assert sequences == list(range(1, 101))


def test_source_has_no_api_provider_worker_execution_money_or_network_authority():
    source = ROOT / "paper-trader/backend/app/monitoring/delivery_service.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    text = source.read_text(encoding="utf-8")
    forbidden = (
        "app.api", "app.providers", "app.engine", "app.execution", "app.ledger",
        "requests", "httpx", "socket", "worker", "order", "position", "capital",
        "pnl", "broker", "deployment", "commit(", "rollback(",
    )
    assert not any(name.startswith((
        "app.api", "app.providers", "app.engine", "app.execution", "app.ledger",
    )) for name in imports)
    lowered = text.lower()
    assert not [value for value in forbidden if value in lowered]


def test_service_and_repository_compile_without_public_export_requirement():
    for relative in (
        "paper-trader/backend/app/monitoring/delivery_service.py",
        "paper-trader/backend/app/monitoring/repository.py",
    ):
        compile((ROOT / relative).read_text(encoding="utf-8"), relative, "exec")
    assert not hasattr(AlertDeliveryAttempt, "commit")
