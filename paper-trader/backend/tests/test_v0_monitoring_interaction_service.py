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
    MonitoringAlertAttentionEventRow,
    MonitoringAlertAttentionStateRow,
    MonitoringSignalReviewRow,
    Organization,
)
from app.monitoring.contracts import AttentionAction
from app.monitoring.interaction_service import (
    MonitoringInteractionConflict,
    MonitoringInteractionNotFound,
    MonitoringInteractionRefusal,
    apply_attention_command,
    submit_signal_review_command,
)
from app.monitoring.repository import MonitoringNotFound, MonitoringRepository
from tests.test_v0_monitoring_inbox_query import _seed
from tests.test_v0_monitoring_persistence import _engine


ROOT = Path(__file__).resolve().parents[3]


def test_attention_commands_append_replay_and_reconstruct_exact_projection(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=10)
    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        read = apply_attention_command(
            repository,
            assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
            expected_sequence=0,
            action=AttentionAction.READ,
            occurred_at=when,
        )
        assert read.replayed is False
        assert read.event.sequence == read.projection.last_sequence == 1
        assert read.projection.read_at == when
        session.commit()

    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        replay = apply_attention_command(
            repository,
            assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
            expected_sequence=0,
            action=AttentionAction.READ,
            occurred_at=when + timedelta(hours=1),
        )
        assert replay.replayed is True
        assert replay.event == read.event
        acknowledge = apply_attention_command(
            repository,
            assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
            expected_sequence=1,
            action=AttentionAction.ACKNOWLEDGE,
            occurred_at=when + timedelta(minutes=1),
        )
        dismiss = apply_attention_command(
            repository,
            assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
            expected_sequence=2,
            action=AttentionAction.DISMISS,
            occurred_at=when + timedelta(minutes=2),
        )
        assert acknowledge.projection.last_sequence == 2
        assert dismiss.projection.last_sequence == 3
        assert dismiss.projection.read_at == when
        assert dismiss.projection.acknowledged_at == when + timedelta(minutes=1)
        assert dismiss.projection.dismissed_at == when + timedelta(minutes=2)
        session.commit()

    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        restored = repository.get_attention_state(
            first.alert.assignment_id, first.alert.address,
        )
        assert restored == dismiss.projection
        assert repository.get_attention_event(
            first.alert.assignment_id,
            first.alert.address,
            read.event.request_id,
        ) == read.event


def test_attention_sequence_conflicts_leave_no_partial_rows(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=10)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        apply_attention_command(
            repository,
            assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
            expected_sequence=0,
            action=AttentionAction.READ,
            occurred_at=when,
        )
        session.commit()

    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        with pytest.raises(MonitoringInteractionConflict):
            apply_attention_command(
                repository,
                assignment_id=first.alert.assignment_id,
                alert_address=first.alert.address,
                expected_sequence=0,
                action=AttentionAction.ACKNOWLEDGE,
                occurred_at=when + timedelta(minutes=1),
            )
        with pytest.raises(MonitoringInteractionConflict, match="gap"):
            apply_attention_command(
                repository,
                assignment_id=first.alert.assignment_id,
                alert_address=first.alert.address,
                expected_sequence=3,
                action=AttentionAction.DISMISS,
                occurred_at=when + timedelta(minutes=2),
            )
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 1
        projection = session.get(MonitoringAlertAttentionStateRow, (
            "tenant.alpha", first.alert.assignment_id, first.alert.address,
        ))
        assert projection.last_sequence == 1


def test_review_command_is_idempotent_and_immutable_per_reviewer_event(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.event.event_at + timedelta(minutes=10)
    kwargs = {
        "assignment_id": first.event.assignment_id,
        "monitoring_event_address": first.event.address,
        "server_reviewer_user_id": "user.alpha",
        "disposition": "CONFIRMED",
        "reason_code": "MATCHED_EXPECTATION",
        "note": "Expected transition",
    }
    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        created = submit_signal_review_command(
            repository, **kwargs, created_at=when,
        )
        assert created.replayed is False
        session.commit()
    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        replay = submit_signal_review_command(
            repository, **kwargs, created_at=when + timedelta(hours=1),
        )
        assert replay.replayed is True
        assert replay.review == created.review
        with pytest.raises(MonitoringInteractionConflict, match="immutable"):
            submit_signal_review_command(
                repository,
                **{**kwargs, "disposition": "REJECTED"},
                created_at=when + timedelta(hours=2),
            )
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 1


def test_review_uses_the_server_resolved_beta_reviewer_identity(tmp_path):
    engine = _engine(tmp_path)
    _first, _second, beta = _seed(engine)
    when = beta.event.event_at + timedelta(minutes=10)
    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.beta")
        result = submit_signal_review_command(
            repository,
            assignment_id=beta.event.assignment_id,
            monitoring_event_address=beta.event.address,
            server_reviewer_user_id="user.beta",
            disposition="REJECTED",
            reason_code="UNEXPECTED_TRANSITION",
            note="Beta reviewer decision",
            created_at=when,
        )
        assert result.review.owner_id == "tenant.beta"
        assert result.review.reviewer_user_id == "user.beta"
        session.commit()


def test_two_tenant_guessed_attention_and_review_ids_have_private_absence(tmp_path):
    engine = _engine(tmp_path)
    first, _second, beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=10)
    with Session(engine) as session:
        alpha = MonitoringRepository(session, owner_id="tenant.alpha")
        with pytest.raises(MonitoringInteractionNotFound) as alert_absence:
            apply_attention_command(
                alpha,
                assignment_id=beta.alert.assignment_id,
                alert_address=beta.alert.address,
                expected_sequence=0,
                action=AttentionAction.READ,
                occurred_at=when,
            )
        with pytest.raises(MonitoringInteractionNotFound) as missing_alert:
            apply_attention_command(
                alpha,
                assignment_id="assignment.missing",
                alert_address="sha256:" + "0" * 64,
                expected_sequence=0,
                action=AttentionAction.READ,
                occurred_at=when,
            )
        with pytest.raises(MonitoringInteractionNotFound) as review_absence:
            submit_signal_review_command(
                alpha,
                assignment_id=beta.event.assignment_id,
                monitoring_event_address=beta.event.address,
                server_reviewer_user_id="user.alpha",
                disposition="REJECTED",
                reason_code="UNEXPECTED_TRANSITION",
                note="Foreign event must stay absent",
                created_at=when,
            )
        with pytest.raises(MonitoringInteractionNotFound) as missing_review:
            submit_signal_review_command(
                alpha,
                assignment_id="assignment.missing",
                monitoring_event_address="sha256:" + "0" * 64,
                server_reviewer_user_id="user.alpha",
                disposition="REJECTED",
                reason_code="UNEXPECTED_TRANSITION",
                note="Missing event must stay absent",
                created_at=when,
            )
        assert {
            str(alert_absence.value), str(missing_alert.value),
            str(review_absence.value), str(missing_review.value),
        } == {"monitoring object not found"}
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 0


def test_outer_rollback_removes_attention_review_and_projection_changes(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=10)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        apply_attention_command(
            repository,
            assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
            expected_sequence=0,
            action=AttentionAction.READ,
            occurred_at=when,
        )
        submit_signal_review_command(
            repository,
            assignment_id=first.event.assignment_id,
            monitoring_event_address=first.event.address,
            server_reviewer_user_id="user.alpha",
            disposition="CONFIRMED",
            reason_code="MATCHED_EXPECTATION",
            note="rollback-sentinel-private-note",
            created_at=when + timedelta(minutes=1),
        )
        session.rollback()
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        projection = repository.get_attention_state(
            first.alert.assignment_id, first.alert.address,
        )
        assert projection.last_sequence == 0 and projection.is_unread
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 0


def test_command_boundary_refuses_open_values_and_foreign_lookup(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=10)
    with pytest.raises(MonitoringInteractionRefusal, match="exact owner-scoped"):
        apply_attention_command(
            object(),
            assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
            expected_sequence=0,
            action=AttentionAction.READ,
            occurred_at=when,
        )
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        with pytest.raises(MonitoringInteractionRefusal):
            apply_attention_command(
                repository,
                assignment_id=first.alert.assignment_id,
                alert_address=first.alert.address,
                expected_sequence=True,
                action=AttentionAction.READ,
                occurred_at=when,
            )
        with pytest.raises(MonitoringInteractionRefusal):
            apply_attention_command(
                repository,
                assignment_id=first.alert.assignment_id,
                alert_address=first.alert.address,
                expected_sequence=0,
                action="READ",
                occurred_at=when,
            )
        with pytest.raises(MonitoringInteractionRefusal):
            submit_signal_review_command(
                repository,
                assignment_id=first.event.assignment_id,
                monitoring_event_address=first.event.address,
                server_reviewer_user_id="user.alpha",
                disposition="MAYBE",
                reason_code="OPEN",
                note="",
                created_at=when,
            )
        with pytest.raises(MonitoringInteractionRefusal, match="assignment"):
            apply_attention_command(
                repository,
                assignment_id="x" * 129,
                alert_address=first.alert.address,
                expected_sequence=0,
                action=AttentionAction.READ,
                occurred_at=when,
            )
        with pytest.raises(MonitoringNotFound):
            repository.get_review(
                first.event.assignment_id, first.event.address, "user.beta",
            )


def test_pending_caller_writes_refuse_before_command_or_implicit_rollback(tmp_path):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=10)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        pending = Organization(organization_id="pending.owner", name="pending")
        session.add(pending)
        with pytest.raises(MonitoringInteractionRefusal, match="attention command"):
            apply_attention_command(
                repository,
                assignment_id=first.alert.assignment_id,
                alert_address=first.alert.address,
                expected_sequence=0,
                action=AttentionAction.READ,
                occurred_at=when,
            )
        assert pending in session.new
        session.rollback()


def test_divergent_repository_returns_roll_back_before_caller_action(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    first, _second, _beta = _seed(engine)
    when = first.alert.event_at + timedelta(minutes=10)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        original_attention = MonitoringRepository.append_attention_event

        def divergent_attention(self, event, *, created_at, update_projection=True):
            persisted = original_attention(
                self, event, created_at=created_at,
                update_projection=update_projection,
            )
            return replace(
                persisted, occurred_at=persisted.occurred_at + timedelta(seconds=1),
            )

        with monkeypatch.context() as patcher:
            patcher.setattr(
                MonitoringRepository, "append_attention_event", divergent_attention,
            )
            with pytest.raises(MonitoringInteractionConflict, match="result differs"):
                apply_attention_command(
                    repository,
                    assignment_id=first.alert.assignment_id,
                    alert_address=first.alert.address,
                    expected_sequence=0,
                    action=AttentionAction.READ,
                    occurred_at=when,
                )
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAlertAttentionEventRow
        )) == 0
        projection = repository.get_attention_state(
            first.alert.assignment_id, first.alert.address,
        )
        assert projection.last_sequence == 0 and projection.is_unread

        original_review = MonitoringRepository.append_review

        def divergent_review(self, review):
            persisted = original_review(self, review)
            return replace(persisted, note=persisted.note + " changed")

        with monkeypatch.context() as patcher:
            patcher.setattr(MonitoringRepository, "append_review", divergent_review)
            with pytest.raises(MonitoringInteractionConflict, match="result differs"):
                submit_signal_review_command(
                    repository,
                    assignment_id=first.event.assignment_id,
                    monitoring_event_address=first.event.address,
                    server_reviewer_user_id="user.alpha",
                    disposition="CONFIRMED",
                    reason_code="MATCHED_EXPECTATION",
                    note="counterexample",
                    created_at=when + timedelta(minutes=1),
                )
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalReviewRow
        )) == 0
        assert session.is_active and session.in_transaction()
        session.rollback()


@pytest.mark.parametrize("same_action", [True, False])
def test_simultaneous_same_alert_commands_have_one_business_effect(
    tmp_path, same_action,
):
    engine = _engine(tmp_path)
    first, second, _beta = _seed(engine)
    selected = first if same_action else second
    barrier = threading.Barrier(2)
    actions = (
        AttentionAction.READ,
        AttentionAction.READ if same_action else AttentionAction.ACKNOWLEDGE,
    )

    def command(index):
        with Session(engine, expire_on_commit=False) as session:
            repository = MonitoringRepository(session, owner_id="tenant.alpha")
            barrier.wait(timeout=5)
            try:
                result = apply_attention_command(
                    repository,
                    assignment_id=selected.alert.assignment_id,
                    alert_address=selected.alert.address,
                    expected_sequence=0,
                    action=actions[index],
                    occurred_at=selected.alert.event_at + timedelta(
                        minutes=10, seconds=index,
                    ),
                )
                session.commit()
                return "replay" if result.replayed else "created", result.event
            except MonitoringInteractionConflict:
                session.rollback()
                return "conflict", None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(command, range(2)))
    labels = sorted(value[0] for value in outcomes)
    if same_action:
        assert labels == ["created", "replay"]
        assert outcomes[0][1] == outcomes[1][1]
    else:
        assert labels == ["conflict", "created"]
    with Session(engine) as session:
        rows = session.scalars(sa.select(MonitoringAlertAttentionEventRow).where(
            MonitoringAlertAttentionEventRow.owner_id == "tenant.alpha",
            MonitoringAlertAttentionEventRow.assignment_id == selected.alert.assignment_id,
            MonitoringAlertAttentionEventRow.alert_address == selected.alert.address,
        )).all()
        assert len(rows) == 1
        projection = session.get(MonitoringAlertAttentionStateRow, (
            "tenant.alpha", selected.alert.assignment_id, selected.alert.address,
        ))
        assert projection.last_sequence == 1
    engine.dispose()


def test_interaction_service_imports_no_api_provider_execution_or_frontend():
    path = ROOT / "paper-trader/backend/app/monitoring/interaction_service.py"
    source = path.read_text()
    tree = ast.parse(source)
    imports = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    }
    forbidden = (
        "app.api", "app.core.release_profile", "app.main", "app.providers",
        "app.engine", "app.execution", "app.ledger", "paper-trader.frontend",
    )
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in imports for prefix in forbidden
    )
    assert "logger" not in source and "print(" not in source
