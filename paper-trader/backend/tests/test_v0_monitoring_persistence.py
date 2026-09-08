"""Owner-scoped, append-only V0 monitoring repository contract."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import sys
import threading
from time import perf_counter

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db import migrate
from app.db.models import (
    Base, Membership, MonitoringAlertAttentionStateRow,
    MonitoringAlertAttentionEventRow, MonitoringAlertDeliveryAttemptRow,
    MonitoringAssignmentRow, MonitoringLatestStateRow, MonitoringSignalAlertRow,
    MonitoringSignalEventRow, MonitoringSignalReviewRow, MonitoringStateSnapshotRow,
    Organization, Project, User,
)
from app.monitoring import contracts
from app.ir.hashing import canonical_json
from app.monitoring.repository import (
    MonitoringAssignmentSpec,
    MonitoringConflict,
    MonitoringCorrupt,
    MonitoringNotFound,
    MonitoringRefused,
    MonitoringRepository,
    MonitoringStateSnapshot,
    SignalReview,
    TimeAddressCursor,
    validate_persisted_monitoring,
)
from tests.test_v0_signal_alert_attention_contract import T0, address, event


def _engine(tmp_path, name="monitoring.db"):
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)

    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("legacy migration is not a monitoring test path"),
    )
    _seed_two_owners(engine)
    return engine


def _seed_two_owners(engine):
    with Session(engine) as session, session.begin():
        for owner, user, project in (
            ("tenant.alpha", "user.alpha", "project.alpha"),
            ("tenant.beta", "user.beta", "project.beta"),
        ):
            if session.get(Organization, owner) is not None:
                continue
            session.add(Organization(organization_id=owner, name=owner))
            session.add(User(user_id=user, email_normalized=f"{user}@example.test",
                             display_name=user))
            session.flush()
            session.add(Membership(organization_id=owner, user_id=user,
                                   role="owner", status="active"))
            session.add(Project(project_id=project, owner_id=owner, name=project,
                                description="", status="active"))


def _spec(assignment_id="assignment.alpha", project_id="project.alpha"):
    return MonitoringAssignmentSpec(
        assignment_id=assignment_id, project_id=project_id,
        strategy_id="strategy.alpha", graph_version_address=address("2"),
        resolved_graph_address=address("3"), registry_address=address("d"),
        implementation_closure_address=address("4"),
        research_admission_address=address("5"),
        static_scope_revision_address=address("e"),
        role_binding_address=address("f"), data_connection_id=7,
        capability_profile_address=address("a"),
        resource_plan_address=address("b"),
        evaluation_trigger_address=address("c"),
        state_reset_policy_address=address("9"),
    )


def _facts():
    source = event()
    before = MonitoringStateSnapshot(
        owner_id=source.owner_id, assignment_id=source.assignment_id,
        canonical_instrument_address=source.canonical_instrument_address,
        snapshot_sequence=0, predecessor_snapshot_address=None,
        strategy_state=contracts.StrategyState.FLAT,
        entry_reference=source.entry_reference, stop_loss=source.stop_loss,
        take_profit=source.take_profit, evaluation_event_address=address("d"),
        effective_at=T0,
    )
    after = MonitoringStateSnapshot(
        owner_id=source.owner_id, assignment_id=source.assignment_id,
        canonical_instrument_address=source.canonical_instrument_address,
        snapshot_sequence=1, predecessor_snapshot_address=before.address,
        strategy_state=contracts.StrategyState.LONG,
        entry_reference=source.entry_reference, stop_loss=source.stop_loss,
        take_profit=source.take_profit,
        evaluation_event_address=source.evaluation_event_address,
        effective_at=source.event_at,
    )
    source = replace(
        source, state_before_address=before.address,
        state_after_address=after.address,
    )
    derived = contracts.derive_signal_alert(source)
    assert isinstance(derived, contracts.AlertDerived)
    return before, after, source, derived.alert


def _owned_facts(owner_id: str, assignment_id: str):
    source = replace(event(), owner_id=owner_id, assignment_id=assignment_id)
    before = MonitoringStateSnapshot(
        owner_id=owner_id, assignment_id=assignment_id,
        canonical_instrument_address=source.canonical_instrument_address,
        snapshot_sequence=0, predecessor_snapshot_address=None,
        strategy_state=contracts.StrategyState.FLAT,
        entry_reference=source.entry_reference, stop_loss=source.stop_loss,
        take_profit=source.take_profit, evaluation_event_address=address("d"),
        effective_at=T0,
    )
    after = MonitoringStateSnapshot(
        owner_id=owner_id, assignment_id=assignment_id,
        canonical_instrument_address=source.canonical_instrument_address,
        snapshot_sequence=1, predecessor_snapshot_address=before.address,
        strategy_state=contracts.StrategyState.LONG,
        entry_reference=source.entry_reference, stop_loss=source.stop_loss,
        take_profit=source.take_profit,
        evaluation_event_address=source.evaluation_event_address,
        effective_at=source.event_at,
    )
    source = replace(
        source, state_before_address=before.address,
        state_after_address=after.address,
    )
    derived = contracts.derive_signal_alert(source)
    assert isinstance(derived, contracts.AlertDerived)
    return before, after, source, derived.alert


def _transition(previous: MonitoringStateSnapshot, sequence: int):
    action = (contracts.SignalAction.BUY
              if previous.strategy_state is contracts.StrategyState.FLAT
              else contracts.SignalAction.EXIT)
    target = (contracts.StrategyState.LONG
              if action is contracts.SignalAction.BUY
              else contracts.StrategyState.FLAT)
    event_at = T0 + timedelta(minutes=sequence)
    evaluation = f"sha256:{sequence:064x}"
    source = replace(
        event(), previous_state=previous.strategy_state, target_state=target,
        action=action, evaluation_event_address=evaluation,
        event_at=event_at, latest_data_at=event_at - timedelta(seconds=1),
        knowledge_cutoff_at=event_at + timedelta(seconds=1),
        valid_until=event_at + timedelta(minutes=5),
        state_before_address=previous.address,
    )
    after = MonitoringStateSnapshot(
        owner_id=source.owner_id, assignment_id=source.assignment_id,
        canonical_instrument_address=source.canonical_instrument_address,
        snapshot_sequence=sequence, predecessor_snapshot_address=previous.address,
        strategy_state=target, entry_reference=source.entry_reference,
        stop_loss=source.stop_loss, take_profit=source.take_profit,
        evaluation_event_address=evaluation, effective_at=event_at,
    )
    source = replace(source, state_after_address=after.address)
    derived = contracts.derive_signal_alert(source)
    assert isinstance(derived, contracts.AlertDerived)
    return after, source, derived.alert


def test_monitoring_repository_is_available_without_execution_imports():
    from app.monitoring import repository

    assert repository.MonitoringRepository is not None


def test_owner_scoped_assignment_signal_alert_attention_delivery_review_and_rebuild(tmp_path):
    engine = _engine(tmp_path)
    before, after, source, alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        assignment = repository.create_assignment(_spec(), now=T0)
        assert assignment.optimistic_revision == 1
        assert repository.create_assignment(_spec(), now=T0) == assignment
        assert repository.list_assignments(limit=1).items == (assignment,)

        assert repository.append_state_snapshot(before, created_at=T0) == before
        assert repository.append_state_snapshot(after, created_at=T0 + timedelta(minutes=1)) == after
        persisted = repository.append_event(source, created_at=T0 + timedelta(minutes=2))
        assert persisted == source
        assert repository.append_event(source, created_at=T0 + timedelta(minutes=2)) == source
        assert repository.get_latest_state(
            source.assignment_id, source.canonical_instrument_address) == after
        assert repository.get_assignment(source.assignment_id).optimistic_revision == 3
        assert repository.list_events(source.assignment_id, limit=1).items == (source,)

        assert repository.append_alert(alert, created_at=T0 + timedelta(minutes=2)) == alert
        initial_attention = repository.get_attention_state(alert.assignment_id, alert.address)
        assert initial_attention.is_unread and initial_attention.last_sequence == 0

        delivery = contracts.AlertDeliveryAttempt.create(
            alert=alert, sequence=1, outcome=contracts.DeliveryOutcome.DELIVERED,
            occurred_at=T0 + timedelta(minutes=3),
        )
        assert repository.append_delivery_attempt(
            delivery, created_at=T0 + timedelta(minutes=3)) == delivery
        assert repository.append_delivery_attempt(
            delivery, created_at=T0 + timedelta(minutes=3)) == delivery

        attention = contracts.AlertAttentionEvent.create(
            alert=alert, sequence=1, action=contracts.AttentionAction.READ,
            occurred_at=T0 + timedelta(minutes=4),
        )
        assert repository.append_attention_event(
            attention, created_at=T0 + timedelta(minutes=4)) == attention
        assert repository.append_attention_event(
            attention, created_at=T0 + timedelta(minutes=4)) == attention
        attention_state = repository.get_attention_state(alert.assignment_id, alert.address)
        assert not attention_state.is_unread and attention_state.read_at == attention.occurred_at

        review = SignalReview(
            owner_id="tenant.alpha", assignment_id=source.assignment_id,
            monitoring_event_address=source.address,
            reviewer_user_id="user.alpha", disposition="CONFIRMED",
            reason_code="MATCHED_EXPECTATION", note="Expected transition",
            created_at=T0 + timedelta(minutes=5),
        )
        assert repository.append_review(review) == review
        assert repository.append_review(review) == review
        assert repository.list_reviews(source.assignment_id).items == (review,)

        session.execute(sa.delete(MonitoringLatestStateRow).where(
            MonitoringLatestStateRow.owner_id == "tenant.alpha"))
        session.execute(sa.delete(MonitoringAlertAttentionStateRow).where(
            MonitoringAlertAttentionStateRow.owner_id == "tenant.alpha"))
        assert repository.rebuild_projections() == {
            "latest_state": 1, "attention_state": 1,
        }
        assert repository.get_latest_state(
            source.assignment_id, source.canonical_instrument_address) == after
        assert repository.get_attention_state(
            alert.assignment_id, alert.address).address == attention_state.address
        validate_persisted_monitoring(session.connection())
    code = """import json,sys
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.monitoring.repository import MonitoringRepository
with Session(sa.create_engine(sys.argv[1])) as session:
 repository=MonitoringRepository(session,owner_id='tenant.alpha')
 event=repository.get_event('assignment.alpha',sys.argv[2])
 state=repository.get_latest_state('assignment.alpha',event.canonical_instrument_address)
 print(json.dumps({'event':event.address,'snapshot':state.address},sort_keys=True))
"""
    restart = subprocess.run(
        [sys.executable, "-c", code, str(engine.url), source.address],
        check=True, capture_output=True, text=True,
        env=dict(os.environ, PT_DISABLE_DOTENV="1", PT_PROVIDER="mock",
                 PT_EXECUTION="paper", PT_LIVE_ACK=""), timeout=30,
    )
    assert json.loads(restart.stdout) == {
        "event": source.address, "snapshot": after.address,
    }
    engine.dispose()


def test_two_owners_get_the_same_absence_shape_and_no_cross_tenant_effect(tmp_path):
    engine = _engine(tmp_path)
    before, after, source, _alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        alpha = MonitoringRepository(session, owner_id="tenant.alpha")
        beta = MonitoringRepository(session, owner_id="tenant.beta")
        alpha.create_assignment(_spec(), now=T0)
        alpha.append_state_snapshot(before, created_at=T0)
        alpha.append_state_snapshot(after, created_at=T0 + timedelta(minutes=1))
        alpha.append_event(source, created_at=T0 + timedelta(minutes=2))
        errors = []
        for identifier in ("assignment.alpha", "assignment.missing"):
            with pytest.raises(MonitoringNotFound) as refused:
                beta.get_assignment(identifier)
            errors.append(str(refused.value))
        assert errors == ["monitoring object not found"] * 2
        with pytest.raises(MonitoringRefused, match="owner-scoped"):
            beta.append_event(source, created_at=T0 + timedelta(minutes=2))
        assert beta.list_assignments().items == ()
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow)) == 1
    engine.dispose()


_MONITORING_MODELS = (
    MonitoringAssignmentRow, MonitoringStateSnapshotRow, MonitoringSignalEventRow,
    MonitoringSignalAlertRow, MonitoringAlertDeliveryAttemptRow,
    MonitoringAlertAttentionEventRow, MonitoringLatestStateRow,
    MonitoringAlertAttentionStateRow, MonitoringSignalReviewRow,
)


def _monitoring_inventory(session):
    return {
        model.__tablename__: session.scalar(
            sa.select(sa.func.count()).select_from(model))
        for model in _MONITORING_MODELS
    }


def _same_absence(foreign_call, missing_call):
    errors = []
    for call in (foreign_call, missing_call):
        with pytest.raises(MonitoringNotFound) as refused:
            call()
        errors.append((type(refused.value), str(refused.value)))
    assert errors == [
        (MonitoringNotFound, "monitoring object not found"),
        (MonitoringNotFound, "monitoring object not found"),
    ]


def _exercise_complete_two_owner_matrix(engine):
    _seed_two_owners(engine)
    before, after, source, alert = _owned_facts(
        "tenant.alpha", "assignment.alpha")
    second_snapshot, second_event, second_alert = _transition(after, 2)
    delivery = contracts.AlertDeliveryAttempt.create(
        alert=alert, sequence=1, outcome=contracts.DeliveryOutcome.DELIVERED,
        occurred_at=T0 + timedelta(minutes=3),
    )
    attention = contracts.AlertAttentionEvent.create(
        alert=alert, sequence=1, action=contracts.AttentionAction.READ,
        occurred_at=T0 + timedelta(minutes=4),
    )
    review = SignalReview(
        owner_id="tenant.alpha", assignment_id=source.assignment_id,
        monitoring_event_address=source.address, reviewer_user_id="user.alpha",
        disposition="CONFIRMED", reason_code="MATCHED_EXPECTATION", note="",
        created_at=T0 + timedelta(minutes=5),
    )
    with Session(engine, expire_on_commit=False) as session, session.begin():
        alpha = MonitoringRepository(session, owner_id="tenant.alpha")
        beta = MonitoringRepository(session, owner_id="tenant.beta")
        assignment = alpha.create_assignment(_spec(), now=T0)
        assert alpha.get_assignment(assignment.spec.assignment_id) == assignment
        assert alpha.append_state_snapshot(before, created_at=T0) == before
        assert alpha.append_state_snapshot(after, created_at=source.event_at) == after
        assert alpha.append_event(source, created_at=source.knowledge_cutoff_at) == source
        assert alpha.append_alert(alert, created_at=source.knowledge_cutoff_at) == alert
        assert alpha.append_delivery_attempt(delivery, created_at=delivery.occurred_at) == delivery
        assert alpha.append_attention_event(attention, created_at=attention.occurred_at) == attention
        assert alpha.append_review(review) == review
        assert alpha.append_state_snapshot(
            second_snapshot, created_at=second_event.event_at) == second_snapshot
        assert alpha.append_event(
            second_event, created_at=second_event.knowledge_cutoff_at) == second_event
        assert alpha.append_alert(
            second_alert, created_at=second_event.knowledge_cutoff_at) == second_alert

        events_page = alpha.list_events(source.assignment_id, limit=1)
        assert events_page.items == (source,)
        assert isinstance(events_page.next_cursor, TimeAddressCursor)
        assert alpha.list_events(
            source.assignment_id, limit=1,
            after=events_page.next_cursor).items == (second_event,)
        alerts_page = alpha.list_alerts(
            assignment_id=source.assignment_id, limit=1)
        assert alerts_page.items == (alert,)
        assert alpha.list_alerts(
            assignment_id=source.assignment_id, limit=1,
            after=alerts_page.next_cursor).items == (second_alert,)
        assert alpha.get_event(source.assignment_id, source.address) == source
        assert alpha.get_latest_state(
            source.assignment_id, source.canonical_instrument_address) == second_snapshot
        assert alpha.get_attention_state(
            alert.assignment_id, alert.address).last_sequence == 1
        assert alpha.list_reviews(source.assignment_id).items == (review,)
        assert alpha.rebuild_projections() == {
            "latest_state": 1, "attention_state": 2,
        }

        mutation = alpha.create_assignment(
            _spec("assignment.mutation"), now=T0)
        mutation = alpha.update_assignment(
            mutation.spec.assignment_id, expected_revision=1,
            lifecycle_state="PAUSED", now=T0 + timedelta(minutes=6))
        assert mutation.lifecycle_state == "PAUSED"
        mutation = alpha.update_assignment(
            mutation.spec.assignment_id, expected_revision=2,
            lifecycle_state="ACTIVE", now=T0 + timedelta(minutes=7))
        mutation = alpha.withdraw_assignment(
            mutation.spec.assignment_id,
            expected_revision=mutation.optimistic_revision,
            now=T0 + timedelta(minutes=8))
        assert mutation.lifecycle_state == "WITHDRAWN"

        inventory = _monitoring_inventory(session)
        alpha_assignment = alpha.get_assignment(source.assignment_id)
        alpha_projection = alpha.get_latest_state(
            source.assignment_id, source.canonical_instrument_address)

        _same_absence(
            lambda: beta.create_assignment(
                _spec("assignment.foreign", "project.alpha"), now=T0),
            lambda: beta.create_assignment(
                _spec("assignment.missing", "project.missing"), now=T0),
        )
        _same_absence(
            lambda: beta.get_assignment("assignment.alpha"),
            lambda: beta.get_assignment("assignment.missing"),
        )
        _same_absence(
            lambda: beta.update_assignment(
                "assignment.alpha", expected_revision=1,
                lifecycle_state="PAUSED", now=T0),
            lambda: beta.update_assignment(
                "assignment.missing", expected_revision=1,
                lifecycle_state="PAUSED", now=T0),
        )
        _same_absence(
            lambda: beta.withdraw_assignment(
                "assignment.alpha", expected_revision=1, now=T0),
            lambda: beta.withdraw_assignment(
                "assignment.missing", expected_revision=1, now=T0),
        )

        beta_before = replace(before, owner_id="tenant.beta")
        beta_missing_before = replace(
            beta_before, assignment_id="assignment.missing")
        _same_absence(
            lambda: beta.append_state_snapshot(beta_before, created_at=T0),
            lambda: beta.append_state_snapshot(beta_missing_before, created_at=T0),
        )
        beta_event = replace(source, owner_id="tenant.beta")
        beta_missing_event = replace(
            beta_event, assignment_id="assignment.missing")
        _same_absence(
            lambda: beta.append_event(
                beta_event, created_at=beta_event.knowledge_cutoff_at),
            lambda: beta.append_event(
                beta_missing_event,
                created_at=beta_missing_event.knowledge_cutoff_at),
        )
        beta_alert = replace(alert, owner_id="tenant.beta")
        beta_missing_alert = replace(
            beta_alert, assignment_id="assignment.missing")
        _same_absence(
            lambda: beta.append_alert(
                beta_alert, created_at=beta_alert.knowledge_cutoff_at),
            lambda: beta.append_alert(
                beta_missing_alert,
                created_at=beta_missing_alert.knowledge_cutoff_at),
        )
        beta_delivery = replace(delivery, owner_id="tenant.beta")
        beta_missing_delivery = replace(
            beta_delivery, assignment_id="assignment.missing")
        _same_absence(
            lambda: beta.append_delivery_attempt(
                beta_delivery, created_at=beta_delivery.occurred_at),
            lambda: beta.append_delivery_attempt(
                beta_missing_delivery,
                created_at=beta_missing_delivery.occurred_at),
        )
        beta_attention = replace(attention, owner_id="tenant.beta")
        beta_missing_attention = replace(
            beta_attention, assignment_id="assignment.missing")
        _same_absence(
            lambda: beta.append_attention_event(
                beta_attention, created_at=beta_attention.occurred_at),
            lambda: beta.append_attention_event(
                beta_missing_attention,
                created_at=beta_missing_attention.occurred_at),
        )
        beta_review = replace(
            review, owner_id="tenant.beta", reviewer_user_id="user.beta")
        beta_missing_review = replace(
            beta_review, assignment_id="assignment.missing")
        _same_absence(
            lambda: beta.append_review(beta_review),
            lambda: beta.append_review(beta_missing_review),
        )

        for foreign, missing in (
            (
                lambda: beta.get_event(source.assignment_id, source.address),
                lambda: beta.get_event("assignment.missing", address("f")),
            ),
            (
                lambda: beta.list_events(source.assignment_id),
                lambda: beta.list_events("assignment.missing"),
            ),
            (
                lambda: beta.list_alerts(assignment_id=source.assignment_id),
                lambda: beta.list_alerts(assignment_id="assignment.missing"),
            ),
            (
                lambda: beta.get_latest_state(
                    source.assignment_id, source.canonical_instrument_address),
                lambda: beta.get_latest_state(
                    "assignment.missing", source.canonical_instrument_address),
            ),
            (
                lambda: beta.get_attention_state(
                    alert.assignment_id, alert.address),
                lambda: beta.get_attention_state(
                    "assignment.missing", address("e")),
            ),
            (
                lambda: beta.list_reviews(source.assignment_id),
                lambda: beta.list_reviews("assignment.missing"),
            ),
        ):
            _same_absence(foreign, missing)

        assert beta.list_assignments().items == ()
        assert beta.list_assignments(after="assignment.alpha").items == ()
        assert beta.list_alerts().items == ()
        assert beta.list_alerts(after=alerts_page.next_cursor).items == ()
        assert beta.rebuild_projections() == {
            "latest_state": 0, "attention_state": 0,
        }
        assert _monitoring_inventory(session) == inventory
        assert alpha.get_assignment(source.assignment_id) == alpha_assignment
        assert alpha.get_latest_state(
            source.assignment_id,
            source.canonical_instrument_address) == alpha_projection
    return {
        "methods": 18,
        "foreign_missing_pairs": 16,
        "same_owner_controls": 18,
        "no_side_effect": True,
    }


def test_complete_two_owner_repository_matrix_sqlite(tmp_path):
    engine = _engine(tmp_path, "monitoring-two-owner-matrix.db")
    assert _exercise_complete_two_owner_matrix(engine)["no_side_effect"] is True
    engine.dispose()


def _exercise_concurrent_event_reorder(engine):
    _seed_two_owners(engine)
    initial, _unused_after, _unused_event, _unused_alert = _facts()
    first_snapshot, first_event, _first_alert = _transition(initial, 1)
    second_snapshot, second_event, _second_alert = _transition(first_snapshot, 2)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(initial, created_at=T0)
        repository.append_state_snapshot(first_snapshot, created_at=first_event.event_at)
        repository.append_state_snapshot(second_snapshot, created_at=second_event.event_at)
    barrier = threading.Barrier(2)

    def writer(source):
        with Session(engine, expire_on_commit=False) as session:
            try:
                with session.begin():
                    repository = MonitoringRepository(session, owner_id="tenant.alpha")
                    barrier.wait()
                    repository.append_event(
                        source, created_at=source.knowledge_cutoff_at)
                return source.address
            except MonitoringConflict:
                return "ordered-refusal"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, (second_event, first_event)))
    with Session(engine) as session:
        persisted = set(session.scalars(sa.select(
            MonitoringSignalEventRow.content_address)))
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        latest = repository.get_latest_state(
            first_event.assignment_id, first_event.canonical_instrument_address)
        validate_persisted_monitoring(session.connection())
    assert first_event.address in persisted
    assert persisted <= {first_event.address, second_event.address}
    assert (second_event.address not in persisted
            or first_event.address in persisted)
    assert latest.snapshot_sequence == len(persisted)
    assert set(results) <= {
        first_event.address, second_event.address, "ordered-refusal",
    }
    return {"persisted": len(persisted), "refusals": results.count("ordered-refusal")}


def test_concurrent_event_reorder_sqlite(tmp_path):
    engine = _engine(tmp_path, "monitoring-concurrent-reorder.db")
    result = _exercise_concurrent_event_reorder(engine)
    assert result["persisted"] in {1, 2}
    engine.dispose()


def test_assignment_revision_withdrawal_pagination_and_bounded_inputs(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        first = repository.create_assignment(_spec("assignment.1"), now=T0)
        second = repository.create_assignment(_spec("assignment.2"), now=T0)
        page = repository.list_assignments(limit=1)
        assert page.items == (first,) and page.next_cursor == "assignment.1"
        assert repository.list_assignments(limit=1, after=page.next_cursor).items == (second,)
        paused = repository.update_assignment(
            first.spec.assignment_id, expected_revision=1,
            lifecycle_state="PAUSED", now=T0 + timedelta(minutes=1),
        )
        assert paused.optimistic_revision == 2 and paused.lifecycle_state == "PAUSED"
        with pytest.raises(MonitoringConflict, match="revision"):
            repository.update_assignment(
                first.spec.assignment_id, expected_revision=1,
                lifecycle_state="ACTIVE", now=T0 + timedelta(minutes=2),
            )
        withdrawn = repository.withdraw_assignment(
            first.spec.assignment_id, expected_revision=2,
            now=T0 + timedelta(minutes=3),
        )
        assert withdrawn.lifecycle_state == "WITHDRAWN" and withdrawn.withdrawn_at is not None
        for limit in (0, -1, 101):
            with pytest.raises(MonitoringRefused, match="limit"):
                repository.list_assignments(limit=limit)
    engine.dispose()


def test_assignment_sql_guard_allows_only_declared_mutable_columns(tmp_path):
    engine = _engine(tmp_path, "monitoring-assignment-guard.db")
    with Session(engine, expire_on_commit=False) as session, session.begin():
        MonitoringRepository(session, owner_id="tenant.alpha").create_assignment(
            _spec(), now=T0)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE monitoring_assignments SET optimistic_revision=2,"
            "lifecycle_state='PAUSED',updated_at='2026-08-29 09:16:00' "
            "WHERE owner_id='tenant.alpha' AND assignment_id='assignment.alpha'")
    with pytest.raises(sa.exc.DBAPIError, match="identity is immutable"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE monitoring_assignments SET strategy_id='forged' "
                "WHERE owner_id='tenant.alpha' AND assignment_id='assignment.alpha'")
    with pytest.raises(sa.exc.DBAPIError, match="durable"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "DELETE FROM monitoring_assignments WHERE owner_id='tenant.alpha' "
                "AND assignment_id='assignment.alpha'")
    engine.dispose()


def test_duplicate_review_and_reordered_snapshot_conflicts(tmp_path):
    engine = _engine(tmp_path)
    before, after, source, _alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=T0 + timedelta(minutes=1))
        repository.append_event(source, created_at=T0 + timedelta(minutes=2))
        review = SignalReview(
            owner_id="tenant.alpha", assignment_id=source.assignment_id,
            monitoring_event_address=source.address, reviewer_user_id="user.alpha",
            disposition="CONFIRMED", reason_code="MATCHED_EXPECTATION", note="",
            created_at=T0 + timedelta(minutes=3),
        )
        repository.append_review(review)
        with pytest.raises(MonitoringConflict, match="different bytes"):
            repository.append_review(replace(review, disposition="REJECTED"))
        with pytest.raises(MonitoringConflict, match="snapshot"):
            repository.append_state_snapshot(
                replace(after, strategy_state=contracts.StrategyState.SHORT),
                created_at=T0 + timedelta(minutes=4),
            )
    engine.dispose()


def test_receipt_before_projection_restart_retry_repairs_once(tmp_path, monkeypatch):
    engine = _engine(tmp_path, "monitoring-receipt-before-projection.db")
    before, after, source, alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=source.event_at)
        monkeypatch.setattr(repository, "_advance_latest_projection", lambda *_args: None)
        repository.append_event(source, created_at=source.knowledge_cutoff_at)
        assert repository.get_latest_state(
            source.assignment_id, source.canonical_instrument_address) == before
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        assert repository.append_event(
            source, created_at=source.knowledge_cutoff_at) == source
        repaired = repository.get_latest_state(
            source.assignment_id, source.canonical_instrument_address)
        revision = repository.get_assignment(source.assignment_id).optimistic_revision
        assert repaired == after
        assert repository.append_event(
            source, created_at=source.knowledge_cutoff_at) == source
        assert repository.get_assignment(
            source.assignment_id).optimistic_revision == revision
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow)) == 1
        repository.append_alert(alert, created_at=source.knowledge_cutoff_at)
        attention = contracts.AlertAttentionEvent.create(
            alert=alert, sequence=1, action=contracts.AttentionAction.READ,
            occurred_at=T0 + timedelta(minutes=4),
        )
        repository.append_attention_event(
            attention, created_at=attention.occurred_at,
            update_projection=False,
        )
        assert repository.get_attention_state(
            alert.assignment_id, alert.address).last_sequence == 0
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.append_attention_event(
            attention, created_at=attention.occurred_at)
        repaired_attention = repository.get_attention_state(
            alert.assignment_id, alert.address)
        assert repaired_attention.last_sequence == 1
        revision = session.get(MonitoringAlertAttentionStateRow, (
            "tenant.alpha", alert.assignment_id, alert.address)).projection_revision
        repository.append_attention_event(
            attention, created_at=attention.occurred_at)
        assert session.get(MonitoringAlertAttentionStateRow, (
            "tenant.alpha", alert.assignment_id, alert.address)).projection_revision == revision
    engine.dispose()


def test_event_admission_refuses_reorder_atomically_and_delayed_retry_is_noop(tmp_path):
    engine = _engine(tmp_path, "monitoring-event-order.db")
    initial, _unused_after, _unused_event, _unused_alert = _facts()
    first_snapshot, first_event, _first_alert = _transition(initial, 1)
    second_snapshot, second_event, _second_alert = _transition(first_snapshot, 2)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(initial, created_at=T0)
        repository.append_state_snapshot(first_snapshot, created_at=first_event.event_at)
        repository.append_state_snapshot(second_snapshot, created_at=second_event.event_at)
        with pytest.raises(MonitoringConflict, match="ordered|current|state_before"):
            repository.append_event(
                second_event, created_at=second_event.knowledge_cutoff_at)
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow)) == 0
        assert repository.get_latest_state(
            initial.assignment_id, initial.canonical_instrument_address) == initial
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.append_event(first_event, created_at=first_event.knowledge_cutoff_at)
        repository.append_event(second_event, created_at=second_event.knowledge_cutoff_at)
        revision = repository.get_assignment(first_event.assignment_id).optimistic_revision
        assert repository.append_event(
            first_event, created_at=first_event.knowledge_cutoff_at) == first_event
        assert repository.get_latest_state(
            first_event.assignment_id,
            first_event.canonical_instrument_address) == second_snapshot
        assert repository.get_assignment(
            first_event.assignment_id).optimistic_revision == revision
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow)) == 2
    engine.dispose()


def test_event_projection_refusal_rolls_back_insert_when_caller_catches(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path, "monitoring-event-atomic-refusal.db")
    before, after, source, _alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=source.event_at)

        def refuse(*_args, **_kwargs):
            raise MonitoringConflict("synthetic projection refusal")

        monkeypatch.setattr(repository, "_advance_latest_projection", refuse)
        with pytest.raises(MonitoringConflict, match="synthetic projection refusal"):
            repository.append_event(source, created_at=source.knowledge_cutoff_at)
        assert session.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow)) == 0
    with engine.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(
            MonitoringSignalEventRow)) == 0
    engine.dispose()


def test_rebuild_ignores_unauthored_snapshot_and_repairs_assignment_pointer(tmp_path):
    engine = _engine(tmp_path, "monitoring-pointer-rebuild.db")
    before, after, source, _alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=source.event_at)
        session.execute(sa.update(MonitoringAssignmentRow).where(
            MonitoringAssignmentRow.owner_id == "tenant.alpha",
            MonitoringAssignmentRow.assignment_id == source.assignment_id,
        ).values(current_state_snapshot_address=after.address))
        session.flush()
        with pytest.raises(MonitoringCorrupt, match="current-state pointer"):
            validate_persisted_monitoring(session.connection())
        assert repository.rebuild_projections() == {
            "latest_state": 1, "attention_state": 0,
        }
        assert repository.get_latest_state(
            source.assignment_id, source.canonical_instrument_address) == before
        assert repository.get_assignment(
            source.assignment_id).current_state_snapshot_address == before.address
        validate_persisted_monitoring(session.connection())
    engine.dispose()


@pytest.mark.parametrize("mutation", ("trigger", "index", "marker"))
def test_schema_trigger_index_and_marker_drift_refuse_before_repository_writes(
    tmp_path, mutation,
):
    engine = _engine(tmp_path, f"monitoring-drift-{mutation}.db")
    with engine.begin() as connection:
        if mutation == "trigger":
            connection.exec_driver_sql(
                "DROP TRIGGER monitoring_signal_events_refuse_update")
        elif mutation == "index":
            connection.exec_driver_sql("DROP INDEX ix_monitoring_events_cursor")
        else:
            connection.exec_driver_sql("UPDATE alembic_version SET version_num='future'")
    with Session(engine) as session:
        with pytest.raises(MonitoringCorrupt, match="trigger|relational|marker"):
            MonitoringRepository(session, owner_id="tenant.alpha")
    engine.dispose()


def test_same_name_permissive_immutable_trigger_refuses_before_repository_writes(tmp_path):
    engine = _engine(tmp_path, "monitoring-permissive-trigger.db")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER monitoring_signal_events_refuse_update")
        connection.exec_driver_sql(
            "CREATE TRIGGER monitoring_signal_events_refuse_update "
            "BEFORE UPDATE ON monitoring_signal_events BEGIN SELECT 1; END")
    with Session(engine) as session:
        with pytest.raises(MonitoringCorrupt, match="trigger|schema contract drift"):
            MonitoringRepository(session, owner_id="tenant.alpha")
    engine.dispose()


def test_declared_local_resource_profile_retains_100000_facts_with_bounded_batches(tmp_path):
    engine = _engine(tmp_path, "monitoring-resource.db")
    before, after, source, alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=source.event_at)
        repository.append_event(source, created_at=source.knowledge_cutoff_at)
        repository.append_alert(alert, created_at=source.knowledge_cutoff_at)
        for index in range(15):
            owner = f"tenant.resource.{index:02d}"
            user = f"user.resource.{index:02d}"
            project = f"project.resource.{index:02d}"
            session.add(Organization(organization_id=owner, name=owner))
            session.add(User(user_id=user, email_normalized=f"{user}@example.test",
                             display_name=user))
            session.flush()
            session.add(Membership(organization_id=owner, user_id=user,
                                   role="owner", status="active"))
            session.add(Project(project_id=project, owner_id=owner, name=project,
                                description="", status="active"))
            session.flush()
            scoped = MonitoringRepository(session, owner_id=owner)
            for assignment in range(20):
                scoped.create_assignment(
                    _spec(f"assignment.{assignment:02d}", project), now=T0)

    durations = []
    batch_size = 1000
    for start in range(0, 100_000, batch_size):
        rows = []
        for sequence in range(start + 1, start + batch_size + 1):
            attempt = contracts.AlertDeliveryAttempt.create(
                alert=alert, sequence=sequence,
                outcome=contracts.DeliveryOutcome.DELIVERED,
                occurred_at=alert.event_at + timedelta(seconds=sequence),
            )
            rows.append({
                "owner_id": attempt.owner_id,
                "assignment_id": attempt.assignment_id,
                "attempt_address": attempt.address,
                "attempt_id": attempt.attempt_id,
                "alert_address": attempt.alert_address,
                "sequence": attempt.sequence,
                "channel": attempt.channel.value,
                "outcome": attempt.outcome.value,
                "occurred_at": attempt.occurred_at.replace(tzinfo=None),
                "failure_code": attempt.failure_code,
                "canonical_json": canonical_json(attempt.to_dict()),
                "created_at": attempt.occurred_at.replace(tzinfo=None),
            })
        started = perf_counter()
        with engine.begin() as connection:
            connection.execute(sa.insert(MonitoringAlertDeliveryAttemptRow), rows)
        durations.append(perf_counter() - started)

    with engine.connect() as connection:
        validate_persisted_monitoring(connection)
        retained = sum(
            connection.scalar(sa.select(sa.func.count()).select_from(
                Base.metadata.tables[name]))
            for name in (
                "monitoring_state_snapshots", "monitoring_signal_events",
                "monitoring_signal_alerts", "monitoring_alert_delivery_attempts",
                "monitoring_alert_attention_events", "monitoring_signal_reviews",
            )
        )
        resource_assignments = connection.scalar(sa.select(sa.func.count()).select_from(
            MonitoringAssignmentRow).where(
                MonitoringAssignmentRow.owner_id.like("tenant.resource.%"),
                MonitoringAssignmentRow.lifecycle_state == "ACTIVE",
            ))
        page_count = connection.exec_driver_sql("PRAGMA page_count").scalar_one()
        page_size = connection.exec_driver_sql("PRAGMA page_size").scalar_one()
        indexes = connection.exec_driver_sql(
            "SELECT count(*) FROM sqlite_master WHERE type='index' "
            "AND tbl_name LIKE 'monitoring_%'").scalar_one()
    ordered = sorted(durations)
    metrics = {
        "owners": 15,
        "active_assignments": resource_assignments,
        "retained_immutable_facts": retained,
        "batch_rows": batch_size,
        "batch_transactions": len(durations),
        "transaction_seconds": {
            "p50": ordered[len(ordered) // 2],
            "p95": ordered[int(len(ordered) * 0.95) - 1],
            "max": max(ordered),
        },
        "database_bytes": page_count * page_size,
        "database_file_bytes": os.path.getsize(engine.url.database),
        "monitoring_indexes": indexes,
    }
    print(json.dumps(metrics, sort_keys=True))
    assert resource_assignments == 300
    assert retained >= 100_000
    assert max(durations) < 1.0
    engine.dispose()


def test_300_transition_retry_burst_and_100_review_requests_are_deterministic(tmp_path):
    engine = _engine(tmp_path, "monitoring-burst.db")
    initial, _unused_after, _unused_event, _unused_alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(initial, created_at=T0)
        for index in range(100):
            user_id = f"reviewer.{index:03d}"
            session.add(User(
                user_id=user_id, email_normalized=f"{user_id}@example.test",
                display_name=user_id,
            ))
            session.flush()
            session.add(Membership(
                organization_id="tenant.alpha", user_id=user_id,
                role="member", status="active",
            ))

    previous = initial
    events = []
    transaction_seconds = []
    for sequence in range(1, 301):
        snapshot, source, alert = _transition(previous, sequence)
        started = perf_counter()
        with Session(engine, expire_on_commit=False) as session, session.begin():
            repository = MonitoringRepository(session, owner_id="tenant.alpha")
            repository.append_state_snapshot(snapshot, created_at=source.event_at)
            assert repository.append_event(
                source, created_at=source.knowledge_cutoff_at) == source
            assert repository.append_alert(
                alert, created_at=source.knowledge_cutoff_at) == alert
            assert repository.append_event(
                source, created_at=source.knowledge_cutoff_at) == source
        transaction_seconds.append(perf_counter() - started)
        events.append(source)
        previous = snapshot

    first_event = events[0]
    review_seconds = []
    for index in range(100):
        review = SignalReview(
            owner_id="tenant.alpha", assignment_id=first_event.assignment_id,
            monitoring_event_address=first_event.address,
            reviewer_user_id=f"reviewer.{index:03d}", disposition="CONFIRMED",
            reason_code="MATCHED_EXPECTATION", note="",
            created_at=T0 + timedelta(hours=8, seconds=index),
        )
        started = perf_counter()
        with Session(engine, expire_on_commit=False) as session, session.begin():
            repository = MonitoringRepository(session, owner_id="tenant.alpha")
            assert repository.append_review(review) == review
            assert repository.append_review(review) == review
        review_seconds.append(perf_counter() - started)

    with engine.connect() as connection:
        counts = {
            name: connection.scalar(sa.select(sa.func.count()).select_from(
                Base.metadata.tables[name]))
            for name in (
                "monitoring_signal_events", "monitoring_signal_alerts",
                "monitoring_signal_reviews", "monitoring_latest_state",
                "monitoring_alert_attention_state",
            )
        }
        validate_persisted_monitoring(connection)
    ordered = sorted(transaction_seconds)
    review_ordered = sorted(review_seconds)
    metrics = {
        "counts": counts,
        "transition_seconds": {
            "p50": ordered[len(ordered) // 2],
            "p95": ordered[int(len(ordered) * 0.95) - 1],
            "max": max(ordered),
        },
        "review_seconds": {
            "p50": review_ordered[len(review_ordered) // 2],
            "p95": review_ordered[int(len(review_ordered) * 0.95) - 1],
            "max": max(review_ordered),
        },
    }
    print(json.dumps(metrics, sort_keys=True))
    assert counts == {
        "monitoring_signal_events": 300,
        "monitoring_signal_alerts": 300,
        "monitoring_signal_reviews": 100,
        "monitoring_latest_state": 1,
        "monitoring_alert_attention_state": 300,
    }
    assert max(transaction_seconds) < 1.0
    assert max(review_seconds) < 1.0
    engine.dispose()


@pytest.fixture
def watchlist_case(tmp_path):
    from dataclasses import asdict
    from app.core import static_scopes
    from app.db.models import GraphArtifact, IrV2GraphVersion
    from app.market_truth.identity import CanonicalPhysicalInstrument, persist_canonical_instrument
    from app.monitoring.watchlist_config import WatchlistContext
    from app.ir.hashing import content_address
    from tests.test_v0_graph_data_eligibility import _graph_plan

    engine = _engine(tmp_path, "watchlist-preferences.db")
    members = [CanonicalPhysicalInstrument("fixture", str(i), "NSE", "EQUITY",
               "SPOT", "INR", None) for i in range(2)]
    facts = replace(_graph_plan()[2], owner_id="tenant.alpha")
    with Session(engine) as session, session.begin():
        from app.db.concurrency import begin_reservation
        begin_reservation(session, scope="static-scope:tenant.alpha:project.alpha")
        for instrument in members:
            persist_canonical_instrument(session, instrument)
        scope = static_scopes.create_scope(session, owner_id="tenant.alpha",
            project_id="project.alpha", scope_id="scope.watchlist", name="Watchlist",
            members=[instrument.address for instrument in members])
        session.add(GraphArtifact(owner_id=facts.owner_id, project_id="project.alpha",
            identifier=facts.graph_identifier, display_name="Saved strategy",
            draft_json=facts.artifact_json))
        session.add(IrV2GraphVersion(**asdict(facts)))
        foreign_document = json.loads(facts.artifact_json)
        foreign_document["strategy_id"] = "foreign.strategy"
        foreign = replace(facts, owner_id="tenant.beta", graph_identifier="foreign.strategy",
            artifact_json=canonical_json(foreign_document), content_address=content_address(foreign_document))
        session.add(GraphArtifact(owner_id=foreign.owner_id, project_id="project.beta",
            identifier=foreign.graph_identifier, display_name="Foreign strategy",
            draft_json=foreign.artifact_json))
        session.add(IrV2GraphVersion(**asdict(foreign)))
    context = WatchlistContext(project_id="project.alpha", scope_id="scope.watchlist",
        scope_revision=scope["snapshot"]["revision"], scope_address=scope["address"],
        membership_address=scope["membership_address"])
    yield engine, context, members, facts
    engine.dispose()


def _watchlist_write(session, case, operation, revision, **changes):
    from uuid import uuid4
    from app.monitoring.watchlist_config import WatchlistCommand, WatchlistSelection
    from app.monitoring.watchlist_store import write_watchlist_configuration

    _engine_value, context, members, facts = case
    command_values = dict(operation=operation, expected_revision=revision)
    if operation == "CONFIGURE":
        command_values["selection"] = WatchlistSelection(graph_id=facts.graph_identifier,
            graph_version=facts.graph_version, timeframe="30minute")
    else:
        command_values["flag"] = True
    command_values.update(changes.pop("command_values", {}))
    arguments = dict(owner_id="tenant.alpha", created_by="user.alpha", context=context,
        member={"kind": "CANONICAL", "instrument_address": members[0].address},
        command=WatchlistCommand(**command_values), request_id=str(uuid4()), now=T0)
    return write_watchlist_configuration(session, **{**arguments, **changes})


def _watchlist_rows(session, case):
    from app.monitoring.watchlist_query import read_watchlist_rows
    return read_watchlist_rows(session, owner_id="tenant.alpha", context=case[1], now=T0)["rows"]


def test_watchlist_saved_v2_strategy_timeframe_and_all_members_reopen(watchlist_case):
    engine, _context, members, facts = watchlist_case
    with Session(engine) as session, session.begin():
        saved = _watchlist_write(session, watchlist_case, "CONFIGURE", 0)
    with Session(engine) as session:
        rows = _watchlist_rows(session, watchlist_case)
        assert {row["member_key"] for row in rows} == {
            f"CANONICAL:{instrument.address}" for instrument in members}
        row = next(row for row in rows if row["member_key"] == saved.member_key)
        assert row["graph"] == dict(graph_id=facts.graph_identifier, graph_version=1,
            graph_version_address=facts.content_address, label="Saved strategy")
        assert row["timeframe"] == "30minute"
        assert row["configuration_revision"] == 1
        assert all(row["result"]["kind"] == "NOT_EVALUATED" for row in rows)
        assert all(row["monitoring"] == "OFF" for row in rows)


def test_watchlist_pin_monitor_pause_are_independent_and_append_only(watchlist_case):
    from app.db.models import WatchlistMonitoringRevision
    engine = watchlist_case[0]
    with Session(engine) as session, session.begin():
        first = _watchlist_write(session, watchlist_case, "CONFIGURE", 0)
        pin = _watchlist_write(session, watchlist_case, "PIN", 1)
        assert pin.pinned and pin.monitoring_intent == "PAUSE"
        monitor = _watchlist_write(session, watchlist_case, "MONITOR", 2)
        row = next(row for row in _watchlist_rows(session, watchlist_case)
                   if row["member_key"] == first.member_key)
        assert row["monitoring"] == "STARTING"
        assert row["assignment_id"] is None
        assert row["result"]["kind"] == "NOT_EVALUATED"
        assert monitor.pinned and monitor.monitoring_intent == "MONITOR"
        pause = _watchlist_write(session, watchlist_case, "MONITOR", 3,
            command_values={"flag": False})
        assert pause.pinned and pause.monitoring_intent == "PAUSE"
        history = session.scalars(sa.select(WatchlistMonitoringRevision).order_by(
            WatchlistMonitoringRevision.revision)).all()
        assert [item.address for item in history] == [first.address, pin.address,
                                                     monitor.address, pause.address]
        assert [item.predecessor_address for item in history] == [None, first.address,
                                                                 pin.address, monitor.address]
        assert history[0].canonical_json == canonical_json(first.stored_payload())
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringAssignmentRow)) == 0
        for name in ("graph_versions", "deployments", "order_journal", "positions"):
            assert session.scalar(sa.select(sa.func.count()).select_from(Base.metadata.tables[name])) == 0


def test_watchlist_retry_returns_original_revision_and_reused_request_conflicts(watchlist_case):
    from app.monitoring.watchlist_store import WatchlistMonitoringConflict
    engine = watchlist_case[0]
    with Session(engine) as session, session.begin():
        first = _watchlist_write(session, watchlist_case, "CONFIGURE", 0)
        _watchlist_write(session, watchlist_case, "PIN", 1)
        replay = _watchlist_write(session, watchlist_case, "CONFIGURE", 0,
            request_id=first.request_id, now=T0 + timedelta(seconds=3))
        assert replay == first
        with pytest.raises(WatchlistMonitoringConflict, match="different change"):
            _watchlist_write(session, watchlist_case, "PIN", 2, request_id=first.request_id)
        with pytest.raises(WatchlistMonitoringConflict, match="changed elsewhere"):
            _watchlist_write(session, watchlist_case, "MONITOR", 1)


@pytest.mark.parametrize("substitution", ["owner", "context", "strategy", "member"])
def test_watchlist_refuses_foreign_or_stale_selection_without_writes(watchlist_case, substitution):
    from app.core.static_scopes import ScopeNotFound
    from app.db.models import WatchlistMonitoringRevision
    from app.monitoring.watchlist_config import WatchlistSelection
    from app.monitoring.watchlist_store import WatchlistMonitoringConflict, WatchlistMonitoringUnavailable
    engine, context, _members, _facts_value = watchlist_case
    substitutions = {
        "owner": {"owner_id": "tenant.beta", "created_by": "user.beta"},
        "context": {"context": context.model_copy(update={"scope_address": address("a")})},
        "strategy": {"command_values": {"selection": WatchlistSelection(
            graph_id="foreign.strategy", graph_version=1, timeframe="day")}},
        "member": {"member": {"kind": "CANONICAL", "instrument_address": address("b")}},
    }
    with Session(engine) as session, session.begin():
        with pytest.raises((ScopeNotFound, WatchlistMonitoringConflict, WatchlistMonitoringUnavailable)):
            _watchlist_write(session, watchlist_case, "CONFIGURE", 0, **substitutions[substitution])
        assert session.scalar(sa.select(sa.func.count()).select_from(WatchlistMonitoringRevision)) == 0


def test_watchlist_two_writers_cannot_replace_same_revision(watchlist_case):
    from app.db.models import WatchlistMonitoringRevision
    from app.monitoring.watchlist_store import WatchlistMonitoringConflict
    engine = watchlist_case[0]
    with Session(engine) as session, session.begin():
        _watchlist_write(session, watchlist_case, "CONFIGURE", 0)
    barrier = threading.Barrier(2)

    def save(flag):
        barrier.wait(timeout=5)
        try:
            with Session(engine) as session, session.begin():
                return _watchlist_write(session, watchlist_case, "PIN", 1,
                    command_values={"flag": flag}).revision
        except WatchlistMonitoringConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(save, [True, False]))
    assert sorted(outcomes, key=str) == [2, "conflict"]
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(WatchlistMonitoringRevision)) == 2


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_watchlist_history_refuses_direct_sql_mutation(watchlist_case, operation):
    from app.db.models import WatchlistMonitoringRevision
    engine = watchlist_case[0]
    with Session(engine) as session, session.begin():
        saved = _watchlist_write(session, watchlist_case, "CONFIGURE", 0)
    statement = (sa.update(WatchlistMonitoringRevision).values(created_by="user.beta")
                 if operation == "update" else sa.delete(WatchlistMonitoringRevision))
    with engine.begin() as connection:
        with pytest.raises(sa.exc.DatabaseError):
            connection.execute(statement)
    with Session(engine) as session:
        retained = session.scalar(sa.select(WatchlistMonitoringRevision))
        assert retained.canonical_json == canonical_json(saved.stored_payload())


@pytest.mark.parametrize('change', ['owner', 'paused', 'unbound', 'changed', 'future_cutoff'])
def test_research_worker_refuses_unavailable_row_before_research_or_source_access(watchlist_case, monkeypatch, change):
    from app.monitoring import research_worker
    with Session(watchlist_case[0]) as session, session.begin():
        repository, requested = _bound_watchlist(session, watchlist_case)
        owner, cutoff = requested.owner_id, T0
        if change == 'owner':
            owner = 'tenant.beta'
        elif change == 'paused':
            assignment = repository.get_assignment(requested.assignment_id)
            repository.update_assignment(requested.assignment_id, expected_revision=assignment.optimistic_revision,
                lifecycle_state='PAUSED', now=T0)
        elif change == 'unbound':
            requested = requested.model_copy(update={'assignment_id': None})
        elif change == 'changed':
            requested = requested.model_copy(update={'pinned': not requested.pinned})
        else:
            cutoff += timedelta(microseconds=1)
        monkeypatch.setattr(research_worker, 'load_research_monitoring_context',
            lambda *_args, **_kwargs: pytest.fail('invalid row reached original research authority'))
        with pytest.raises(contracts.MonitoringContractError):
            research_worker.evaluate_research_watchlist_row(session, None, owner_id=owner, requested=requested,
                operation_id='not-read', input_manifest_address=address('0'), display_symbol='SELF',
                cutoff_at=cutoff, publication_clock=lambda: T0)
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringSignalEventRow)) == 0


def _bound_watchlist(session, case):
    """Persist an explicit assignment fixture; this is not a worker/admission producer."""
    from uuid import uuid4
    from app.monitoring.evaluation_policy import (
        compile_monitoring_evaluation_policy, monitoring_policy_payload,
    )
    from app.monitoring.watchlist_config import WatchlistCommand, WatchlistValues
    from app.monitoring.watchlist_store import _append

    first = _watchlist_write(session, case, "CONFIGURE", 0)
    policy = compile_monitoring_evaluation_policy(owner_id="tenant.alpha",
        assignment_id="assignment.alpha", initial_resource_plan_address=address("b"),
        maximum_age_seconds=60, history_bytes_upper_bound=1000,
        memory_bytes_upper_bound=1000, cache_bytes_upper_bound=1000,
        queue_concurrency_upper_bound=1, event_rate_events=1, event_rate_per_seconds=60)
    spec = replace(_spec(), strategy_id=case[3].graph_identifier,
        graph_version_address=case[3].content_address,
        static_scope_revision_address=case[1].scope_address,
        evaluation_trigger_address=policy.address)
    repository = MonitoringRepository(session, owner_id="tenant.alpha")
    repository.create_assignment(spec, now=T0)
    values = WatchlistValues(graph=first.graph, timeframe=first.timeframe,
        monitoring_intent="MONITOR", assignment_id=spec.assignment_id,
        evaluation_policy=monitoring_policy_payload(policy),
        canonical_instrument_address=case[2][0].address)
    configuration = _append(session, "tenant.alpha", "user.alpha", case[1], first.member_key,
        first, WatchlistCommand(operation="MONITOR", expected_revision=1, flag=True),
        str(uuid4()), values, T0)
    return repository, configuration


def _watchlist_event(case, *, hold=False):
    before, after, source, _alert = _facts()
    instrument = case[2][0].address
    entry_reference = replace(source.entry_reference, canonical_instrument_address=instrument)
    before = replace(before, canonical_instrument_address=instrument, entry_reference=entry_reference)
    after = replace(after, canonical_instrument_address=instrument, entry_reference=entry_reference,
        predecessor_snapshot_address=before.address,
        strategy_state=contracts.StrategyState.FLAT if hold else after.strategy_state)
    source = replace(source, canonical_instrument_address=instrument, entry_reference=entry_reference,
        strategy_id=case[3].graph_identifier, graph_version_address=case[3].content_address,
        state_before_address=before.address, state_after_address=after.address,
        action=contracts.SignalAction.HOLD if hold else source.action,
        target_state=contracts.StrategyState.FLAT if hold else source.target_state)
    return before, after, source


@pytest.mark.parametrize("result_kind", ["NOT_EVALUATED", "HOLD", "SIGNAL", "STALE"])
def test_watchlist_bound_assignment_reads_attributable_results(watchlist_case, result_kind):
    from app.monitoring.watchlist_query import watchlist_row
    engine = watchlist_case[0]
    with Session(engine) as session, session.begin():
        repository, configuration = _bound_watchlist(session, watchlist_case)
        before, after, source = _watchlist_event(watchlist_case, hold=result_kind == "HOLD")
        if result_kind != "NOT_EVALUATED":
            repository.append_state_snapshot(before, created_at=T0)
            repository.append_state_snapshot(after, created_at=source.event_at)
            repository.append_event(source, created_at=source.knowledge_cutoff_at)
        now = source.valid_until + timedelta(seconds=1) if result_kind == "STALE" else source.event_at
        row = watchlist_row(session, configuration.member_key, configuration, editable=True, now=now)
        assert row["monitoring"] == "ON"
        assert row["result"]["kind"] == result_kind
        if result_kind != "NOT_EVALUATED":
            assert row["result"]["assignment_id"] == configuration.assignment_id
            assert row["result"]["graph_version_address"] == watchlist_case[3].content_address
        assert row["result"]["label"] == {
            "NOT_EVALUATED": "Not evaluated", "HOLD": "No signal",
            "SIGNAL": "Buy", "STALE": "Stale result",
        }[result_kind]


def test_watchlist_reconfiguration_pauses_old_assignment_and_preserves_pin(watchlist_case):
    from app.monitoring.watchlist_config import WatchlistSelection
    engine = watchlist_case[0]
    with Session(engine) as session, session.begin():
        repository, configuration = _bound_watchlist(session, watchlist_case)
        _watchlist_write(session, watchlist_case, "PIN", 2)
        changed = _watchlist_write(session, watchlist_case, "CONFIGURE", 3,
            command_values={"selection": WatchlistSelection(
                graph_id=watchlist_case[3].graph_identifier, graph_version=1, timeframe="day")})
        assert repository.get_assignment(configuration.assignment_id).lifecycle_state == "PAUSED"
        assert changed.pinned and changed.timeframe == "day"
        assert changed.assignment_id is None and changed.monitoring_intent == "PAUSE"


def test_watchlist_bound_assignment_refuses_another_members_result(watchlist_case):
    from app.monitoring.watchlist_query import watchlist_row
    from app.monitoring.watchlist_store import WatchlistMonitoringUnavailable
    engine = watchlist_case[0]
    with Session(engine) as session, session.begin():
        repository, configuration = _bound_watchlist(session, watchlist_case)
        other_case = (*watchlist_case[:2], list(reversed(watchlist_case[2])), watchlist_case[3])
        before, after, source = _watchlist_event(other_case)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=source.event_at)
        repository.append_event(source, created_at=source.knowledge_cutoff_at)
        with pytest.raises(WatchlistMonitoringUnavailable, match="strategy and instrument"):
            watchlist_row(session, configuration.member_key, configuration,
                editable=True, now=source.event_at)


def test_watchlist_bound_configuration_cannot_copy_another_instrument(watchlist_case):
    from pydantic import ValidationError
    from app.monitoring.watchlist_config import WatchlistConfiguration
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, configuration = _bound_watchlist(session, watchlist_case)
        payload = {**configuration.payload(),
                   "canonical_instrument_address": watchlist_case[2][1].address}
        with pytest.raises(ValidationError, match="instrument differs"):
            WatchlistConfiguration.model_validate(payload)


def test_watchlist_latest_refuses_hash_valid_revision_jump(watchlist_case):
    from uuid import uuid4
    from app.db.models import WatchlistMonitoringRevision
    from app.monitoring.watchlist_config import WatchlistConfiguration
    from app.monitoring.watchlist_store import WatchlistMonitoringUnavailable
    with Session(watchlist_case[0]) as session, session.begin():
        first = _watchlist_write(session, watchlist_case, "CONFIGURE", 0)
        payload = {**first.payload(), "revision": 3, "predecessor_address": first.address,
            "request_id": str(uuid4()), "command": {"operation": "PIN", "expected_revision": 2,
                "selection": None, "flag": True}, "pinned": True}
        forged = WatchlistConfiguration.model_validate(payload)
        original = session.scalar(sa.select(WatchlistMonitoringRevision))
        values = {column.name: getattr(original, column.name)
                  for column in WatchlistMonitoringRevision.__table__.columns}
        values.update(revision=3, predecessor_address=first.address,
            request_id=forged.request_id, address=forged.address,
            canonical_json=canonical_json(forged.stored_payload()))
        session.add(WatchlistMonitoringRevision(**values))
        session.flush()
        with pytest.raises(WatchlistMonitoringUnavailable, match="history could not be verified"):
            _watchlist_rows(session, watchlist_case)


def test_watchlist_values_refuse_incomplete_or_cross_assignment_bindings(watchlist_case):
    from pydantic import ValidationError
    from app.monitoring.watchlist_config import WatchlistValues
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, configuration = _bound_watchlist(session, watchlist_case)
        payload = configuration.row_values().model_dump()
        cases = [
            ({"graph": None}, "Choose a saved strategy"),
            ({"evaluation_policy": None}, "assignment and policy must stay paired"),
            ({"canonical_instrument_address": None}, "assignment and instrument must stay paired"),
            ({"graph": None, "monitoring_intent": "PAUSE"}, "assignment requires its saved strategy"),
            ({"assignment_id": "assignment.other"}, "policy names a different assignment"),
        ]
        for changes, reason in cases:
            with pytest.raises(ValidationError, match=reason):
                WatchlistValues.model_validate({**payload, **changes})


def test_watchlist_configuration_refuses_broken_identity_and_foreign_policy_owner(watchlist_case):
    from pydantic import ValidationError
    from app.monitoring.watchlist_config import WatchlistConfiguration
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, configuration = _bound_watchlist(session, watchlist_case)
        payload = configuration.payload()
        cases = [
            ({"predecessor_address": None}, "predecessor and revision differ"),
            ({"revision": 3}, "does not follow the requested revision"),
            ({"project_id": "project.beta"}, "watchlist context differs"),
            ({"owner_id": "tenant.beta"}, "policy owner differs"),
        ]
        for changes, reason in cases:
            with pytest.raises(ValidationError, match=reason):
                WatchlistConfiguration.model_validate({**payload, **changes})


def test_watchlist_decoder_refuses_noncanonical_bytes_and_copied_column_tampering(watchlist_case):
    from types import SimpleNamespace
    from app.db.models import WatchlistMonitoringRevision
    from app.monitoring.watchlist_store import decode_configuration, WatchlistMonitoringUnavailable
    with Session(watchlist_case[0]) as session, session.begin():
        configuration = _watchlist_write(session, watchlist_case, "CONFIGURE", 0)
        row = session.scalar(sa.select(WatchlistMonitoringRevision))
        values = {column.name: getattr(row, column.name)
                  for column in WatchlistMonitoringRevision.__table__.columns}
        assert decode_configuration(SimpleNamespace(**values)) == configuration
        cases = [
            {"canonical_json": "{"},
            {"canonical_json": "[]"},
            {"canonical_json": json.dumps(configuration.stored_payload(), indent=2)},
            {"canonical_json": canonical_json({**configuration.stored_payload(), "unexpected": True})},
            {"created_by": "user.beta"},
            {"request_id": "36e922ba-c3f0-4717-a729-87f36c274f80"},
            {"created_at": row.created_at + timedelta(seconds=1)},
        ]
        for changes in cases:
            with pytest.raises(WatchlistMonitoringUnavailable, match="could not be verified"):
                decode_configuration(SimpleNamespace(**{**values, **changes}))


def _requested_watchlist_binding(session, case):
    from uuid import uuid4
    from app.monitoring.evaluation_policy import compile_monitoring_evaluation_policy
    _watchlist_write(session, case, "CONFIGURE", 0)
    _watchlist_write(session, case, "PIN", 1)
    requested = _watchlist_write(session, case, "MONITOR", 2)
    policy = compile_monitoring_evaluation_policy(owner_id="tenant.alpha",
        assignment_id="assignment.alpha", initial_resource_plan_address=address("b"),
        maximum_age_seconds=60, history_bytes_upper_bound=1000,
        memory_bytes_upper_bound=1000, cache_bytes_upper_bound=1000,
        queue_concurrency_upper_bound=1, event_rate_events=1, event_rate_per_seconds=60)
    spec = replace(_spec(), strategy_id=case[3].graph_identifier,
        graph_version_address=case[3].content_address,
        static_scope_revision_address=case[1].scope_address,
        evaluation_trigger_address=policy.address)
    repository = MonitoringRepository(session, owner_id="tenant.alpha")
    repository.create_assignment(spec, now=T0)
    initial = _watchlist_event(case)[0]
    initial = replace(initial,
        entry_reference=replace(initial.entry_reference, validity=contracts.FactValidity.MISSING, value=None),
        stop_loss=replace(initial.stop_loss, validity=contracts.FactValidity.MISSING, resolved_value=None),
        take_profit=replace(initial.take_profit, validity=contracts.FactValidity.MISSING, resolved_value=None))
    arguments = dict(owner_id="tenant.alpha", created_by="user.alpha", requested=requested,
        assignment_spec=spec, evaluation_policy=policy, initial_snapshot=initial,
        request_id=str(uuid4()), now=T0)
    return repository, arguments


@pytest.mark.parametrize("already_persisted", [False, True])
@pytest.mark.parametrize("research", [False, True])
def test_watchlist_internal_binding_preserves_requested_choices_and_retries_exactly(watchlist_case, already_persisted, research):
    from app.db.models import WatchlistMonitoringRevision
    from app.monitoring.watchlist_store import bind_watchlist_monitoring
    with Session(watchlist_case[0]) as session, session.begin():
        repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        initial = arguments["initial_snapshot"]
        if research:
            from app.monitoring.research_prefix import ResearchReplayCheckpoint
            from app.monitoring.research_replay_state import ResearchReplayState
            from app.monitoring.research_protection import ResearchProtectionEvidence
            from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot
            consumer = address("c")
            checkpoint = ResearchReplayCheckpoint(ResearchReplayState(initial.owner_id, initial.assignment_id,
                initial.canonical_instrument_address, consumer, 0))
            initial = ResearchMonitoringStateSnapshot(checkpoint, None, initial.entry_reference,
                ResearchProtectionEvidence(consumer, contracts.ProtectionKind.STOP_LOSS, ()),
                ResearchProtectionEvidence(consumer, contracts.ProtectionKind.TAKE_PROFIT, ()),
                initial.evaluation_event_address, initial.effective_at)
            arguments["initial_snapshot"] = initial
        if already_persisted:
            repository.append_state_snapshot(initial, created_at=T0)
        bound = bind_watchlist_monitoring(session, **arguments)
        assert bound.revision == 4
        assert bound.predecessor_address == arguments["requested"].address
        assert bound.pinned is True
        assert (bound.graph, bound.timeframe, bound.monitoring_intent) == (
            arguments["requested"].graph, "30minute", "MONITOR")
        assert bound.assignment_id == arguments["assignment_spec"].assignment_id
        assert bound.canonical_instrument_address == initial.canonical_instrument_address
        assert bound.evaluation_policy["address"] == arguments["evaluation_policy"].address
        assert repository.get_latest_state(bound.assignment_id, bound.canonical_instrument_address) == initial
        if research:
            assert initial.stop_loss.status == initial.take_profit.status == "DISABLED"
        else:
            assert initial.stop_loss.resolved_value is None and initial.take_profit.resolved_value is None
        revision = repository.get_assignment(bound.assignment_id).optimistic_revision
        assert bind_watchlist_monitoring(session, **arguments) == bound
        assert repository.get_assignment(bound.assignment_id).optimistic_revision == revision
        assert session.scalar(sa.select(sa.func.count()).select_from(WatchlistMonitoringRevision)) == 4
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringStateSnapshotRow)) == 1


@pytest.mark.parametrize("substitution", ["request_owner", "snapshot_owner", "snapshot_instrument", "policy_owner", "spec", "future", "nonflat"])
def test_watchlist_internal_binding_refuses_foreign_or_unhonest_facts(watchlist_case, substitution):
    from app.monitoring.evaluation_policy import compile_monitoring_evaluation_policy
    from app.monitoring.watchlist_store import bind_watchlist_monitoring, WatchlistMonitoringConflict
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        snapshot = arguments["initial_snapshot"]
        foreign_instrument = watchlist_case[2][1].address
        substitutions = {
            "request_owner": {"owner_id": "tenant.beta"},
            "snapshot_owner": {"initial_snapshot": replace(snapshot, owner_id="tenant.beta")},
            "snapshot_instrument": {"initial_snapshot": replace(snapshot,
                canonical_instrument_address=foreign_instrument,
                entry_reference=replace(snapshot.entry_reference, canonical_instrument_address=foreign_instrument))},
            "spec": {"assignment_spec": replace(arguments["assignment_spec"], graph_version_address=address("8"))},
            "future": {"initial_snapshot": replace(snapshot, effective_at=T0 + timedelta(seconds=1))},
            "nonflat": {"initial_snapshot": replace(snapshot, strategy_state=contracts.StrategyState.LONG)},
        }
        substitutions["policy_owner"] = {"evaluation_policy": compile_monitoring_evaluation_policy(
            **{**{key: value for key, value in arguments["evaluation_policy"].document.items()
                  if key != "trigger"}, "owner_id": "tenant.beta"})}
        # The canonical policy compiler selects the trigger itself.
        changes = substitutions[substitution]
        with pytest.raises(WatchlistMonitoringConflict):
            bind_watchlist_monitoring(session, **{**arguments, **changes})
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringStateSnapshotRow)) == 0


@pytest.mark.parametrize("when,lifecycle", [("before", "PAUSED"), ("after", "PAUSED"), ("before", "WITHDRAWN"), ("after", "WITHDRAWN")])
def test_watchlist_internal_binding_never_reactivates_paused_or_withdrawn_assignment(watchlist_case, when, lifecycle):
    from app.monitoring.watchlist_store import bind_watchlist_monitoring, WatchlistMonitoringConflict
    with Session(watchlist_case[0]) as session, session.begin():
        repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        if when == "after":
            bind_watchlist_monitoring(session, **arguments)
        assignment = repository.get_assignment(arguments["assignment_spec"].assignment_id)
        if lifecycle == "PAUSED":
            repository.update_assignment(assignment.spec.assignment_id,
                expected_revision=assignment.optimistic_revision, lifecycle_state="PAUSED", now=T0)
        else:
            repository.withdraw_assignment(assignment.spec.assignment_id,
                expected_revision=assignment.optimistic_revision, now=T0)
        with pytest.raises(WatchlistMonitoringConflict):
            bind_watchlist_monitoring(session, **arguments)
        assert repository.get_assignment(assignment.spec.assignment_id).lifecycle_state == lifecycle


@pytest.mark.parametrize("when", ["before", "after"])
def test_watchlist_internal_binding_refuses_stale_row_including_after_a_successful_binding(watchlist_case, when):
    from app.monitoring.watchlist_store import bind_watchlist_monitoring, WatchlistMonitoringConflict
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        revision = 3
        if when == "after":
            revision = bind_watchlist_monitoring(session, **arguments).revision
        _watchlist_write(session, watchlist_case, "PIN", revision,
            command_values={"flag": False})
        with pytest.raises(WatchlistMonitoringConflict):
            bind_watchlist_monitoring(session, **arguments)


def test_watchlist_internal_binding_retry_rejects_changed_initial_payload(watchlist_case):
    from app.monitoring.watchlist_store import bind_watchlist_monitoring, WatchlistMonitoringConflict
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        bind_watchlist_monitoring(session, **arguments)
        changed = replace(arguments["initial_snapshot"], evaluation_event_address=address("6"))
        with pytest.raises(WatchlistMonitoringConflict, match="different initial"):
            bind_watchlist_monitoring(session, **{**arguments, "initial_snapshot": changed})
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringStateSnapshotRow)) == 1


def test_watchlist_internal_binding_refuses_assignment_already_used_for_another_instrument(watchlist_case):
    from app.monitoring.watchlist_store import bind_watchlist_monitoring, WatchlistMonitoringConflict
    with Session(watchlist_case[0]) as session, session.begin():
        repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        initial = arguments["initial_snapshot"]
        foreign = watchlist_case[2][1].address
        repository.append_state_snapshot(replace(initial, canonical_instrument_address=foreign,
            entry_reference=replace(initial.entry_reference, canonical_instrument_address=foreign)), created_at=T0)
        with pytest.raises(WatchlistMonitoringConflict, match="another instrument"):
            bind_watchlist_monitoring(session, **arguments)
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringStateSnapshotRow)) == 1


def test_watchlist_internal_binding_rolls_back_initial_state_if_configuration_append_fails(watchlist_case, monkeypatch):
    from app.monitoring import watchlist_store
    with Session(watchlist_case[0]) as session, session.begin():
        repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        assignment_id = arguments["assignment_spec"].assignment_id
        prior = repository.get_assignment(assignment_id)
        def fail_append(*args, **kwargs):
            raise RuntimeError("injected append failure")
        monkeypatch.setattr(watchlist_store, "_append", fail_append)
        with pytest.raises(RuntimeError, match="injected"):
            watchlist_store.bind_watchlist_monitoring(session, **arguments)
        assert repository.get_assignment(assignment_id) == prior
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringStateSnapshotRow)) == 0
        current = watchlist_store.latest_configurations(session, "tenant.alpha", arguments["requested"].context,
            (arguments["requested"].member_key,))[arguments["requested"].member_key]
        assert current == arguments["requested"]


def test_watchlist_internal_binding_refuses_provider_reference_without_mapping_provenance(watchlist_case, monkeypatch):
    from app.monitoring import watchlist_store
    from app.monitoring.watchlist_config import WatchlistConfiguration
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        provider_key = f"PROVIDER_REFERENCE:{address('7')}"
        requested = WatchlistConfiguration.model_validate({
            **arguments["requested"].payload(), "member_key": provider_key})
        monkeypatch.setattr(watchlist_store, "scope_members", lambda _scope: {provider_key: {}})
        with pytest.raises(watchlist_store.WatchlistMonitoringConflict, match="mapping provenance"):
            watchlist_store.bind_watchlist_monitoring(session, **{**arguments, "requested": requested})
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringStateSnapshotRow)) == 0


def test_watchlist_internal_binding_cannot_create_an_unadmitted_assignment(watchlist_case):
    from app.monitoring.watchlist_store import bind_watchlist_monitoring, WatchlistMonitoringConflict
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        unknown = replace(arguments["assignment_spec"], assignment_id="assignment.unadmitted")
        with pytest.raises(WatchlistMonitoringConflict, match="no admitted assignment"):
            bind_watchlist_monitoring(session, **{**arguments, "assignment_spec": unknown})
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringAssignmentRow)) == 1


def test_watchlist_internal_binding_rejects_reused_request_with_different_policy_or_actor(watchlist_case):
    from app.monitoring.evaluation_policy import compile_monitoring_evaluation_policy
    from app.monitoring.watchlist_store import bind_watchlist_monitoring, WatchlistMonitoringConflict
    with Session(watchlist_case[0]) as session, session.begin():
        _repository, arguments = _requested_watchlist_binding(session, watchlist_case)
        bind_watchlist_monitoring(session, **arguments)
        changed_policy = compile_monitoring_evaluation_policy(**{
            **{key: value for key, value in arguments["evaluation_policy"].document.items() if key != "trigger"},
            "maximum_age_seconds": 61})
        for changes in ({"evaluation_policy": changed_policy}, {"created_by": "user.other"}):
            with pytest.raises(WatchlistMonitoringConflict):
                bind_watchlist_monitoring(session, **{**arguments, **changes})


def _research_replay_state_position(direction="LONG", *, ratchet=True):
    from app.monitoring.research_replay_state import ResearchReplayPosition
    return ResearchReplayPosition(direction, 100.0, T0, address("1"), 1,
        2.0 if ratchet else None, 100.0 if ratchet else None,
        (97.5 if direction == "LONG" else 102.5) if ratchet else None)


def _research_replay_state(position=None, pending=None):
    from app.monitoring.research_replay_state import ResearchReplayState
    return ResearchReplayState("tenant.alpha", "assignment.alpha", address("7"), address("8"), 3,
        address("9"), address("2"), T0 + timedelta(minutes=2), T0 + timedelta(minutes=3), position, pending)


def test_research_replay_state_initial_is_empty_addressed_and_json_roundtrips():
    from dataclasses import FrozenInstanceError
    from app.monitoring.research_replay_state import ResearchReplayState
    state = ResearchReplayState("tenant.alpha", "assignment.alpha", address("7"), address("8"), 0)
    payload = state.to_dict()
    assert ResearchReplayState.from_json(canonical_json(payload)) == state
    assert ResearchReplayState.from_json(canonical_json(payload).encode()) == state
    assert payload["position"] is None and payload["pending"] is None
    assert payload["address"] == state.address
    with pytest.raises(FrozenInstanceError):
        state.owner_id = "tenant.beta"
    with pytest.raises(ValueError, match="initial state"):
        replace(state, predecessor_snapshot_address=address("1"))
    with pytest.raises(ValueError, match="initial state"):
        replace(state, position=_research_replay_state_position())


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_research_replay_state_json_reopen_next_ratchet_update_matches_uninterrupted(direction):
    from app.backtest.ratchet import RatchetState
    from app.monitoring.research_replay_state import ResearchReplayPosition, ResearchReplayState, restore_ratchet
    from research.strategy.v2_runtime_strategy import risk_policy_document
    model = risk_policy_document("pine-v4-ratchet/1")["risk_model"]
    uninterrupted = RatchetState(direction, 100.0, 2.0, model)
    first = (110.0, 99.0, 108.0) if direction == "LONG" else (101.0, 90.0, 92.0)
    uninterrupted.update(*first, current_atr=1.0)
    position = ResearchReplayPosition(direction, 100.0, T0, address("1"), 1, 2.0,
        uninterrupted.hw, uninterrupted.stop)
    state = _research_replay_state(position)
    payload = state.to_dict()
    assert payload["position"]["entry_price_hex"] == 100.0.hex()
    reopened = ResearchReplayState.from_json(json.dumps(payload).encode())
    assert reopened == state
    restored = restore_ratchet(reopened.position, model)
    assert (restored.hw.hex(), restored.stop.hex()) == (uninterrupted.hw.hex(), uninterrupted.stop.hex())
    second = (111.0, 106.0, 109.0) if direction == "LONG" else (94.0, 89.0, 91.0)
    uninterrupted.update(*second, current_atr=1.5)
    restored.update(*second, current_atr=1.5)
    assert (restored.hw.hex(), restored.stop.hex(), restored.risk_pts.hex()) == (
        uninterrupted.hw.hex(), uninterrupted.stop.hex(), uninterrupted.risk_pts.hex())
    assert restored.stop_hit(second[2]) == uninterrupted.stop_hit(second[2])


def test_research_replay_state_disabled_risk_and_negative_stop_are_retained_without_reseeding():
    from app.monitoring.research_replay_state import ResearchReplayState, restore_ratchet
    from research.strategy.v2_runtime_strategy import risk_policy_document
    disabled = risk_policy_document("none")["risk_model"]
    model = risk_policy_document("pine-v4-ratchet/1")["risk_model"]
    flat_risk = _research_replay_state_position(ratchet=False)
    assert restore_ratchet(flat_risk, disabled) is None
    negative = replace(_research_replay_state_position(), entry_atr=100.0, ratchet_stop=-25.0)
    reopened = ResearchReplayState.from_json(json.dumps(_research_replay_state(negative).to_dict()))
    assert restore_ratchet(reopened.position, model).stop.hex() == (-25.0).hex()
    for position, policy in ((negative, disabled), (flat_risk, model)):
        with pytest.raises(ValueError, match="risk policy"):
            restore_ratchet(position, policy)


@pytest.mark.parametrize("field", ["atr_length", "initial_risk_atr", "trail_atr"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_research_replay_state_nonfinite_policy_has_typed_refusal(field, value):
    from app.monitoring.contracts import MonitoringContractError
    from app.monitoring.research_replay_state import restore_ratchet
    from research.strategy.v2_runtime_strategy import risk_policy_document
    model = {**risk_policy_document("pine-v4-ratchet/1")["risk_model"], field: value}
    with pytest.raises(MonitoringContractError, match="risk policy"):
        restore_ratchet(_research_replay_state_position(), model)


def test_research_replay_state_refuses_overflowed_or_underflowed_risk_distance():
    from app.monitoring.contracts import MonitoringContractError
    from app.monitoring.research_replay_state import restore_ratchet
    from research.strategy.v2_runtime_strategy import risk_policy_document
    model = risk_policy_document("pine-v4-ratchet/1")["risk_model"]
    for distance, atr in ((1e308, 1e308), (1e-300, 1e-300)):
        with pytest.raises(MonitoringContractError):
            restore_ratchet(replace(_research_replay_state_position(), entry_atr=atr),
                            {**model, "initial_risk_atr": distance})


@pytest.mark.parametrize("field,value", [
    ("entry_price", True), ("entry_price", 100), ("entry_price", 0.0),
    ("entry_price", float("nan")), ("entry_price", float("inf")),
    ("entry_atr", 0.0), ("entry_atr", None), ("ratchet_stop", None),
    ("ratchet_high_water", None), ("ratchet_high_water", 99.0),
    ("ratchet_stop", float("inf")), ("entry_sequence", True), ("entry_sequence", 0),
    ("entry_bar_identity", "invalid"), ("entry_open_at", T0.replace(tzinfo=None)),
    ("direction", "FLAT"),
])
def test_research_replay_state_position_refuses_invalid_values(field, value):
    with pytest.raises(ValueError):
        replace(_research_replay_state_position(), **{field: value})


def test_research_replay_state_short_high_water_cannot_exceed_entry():
    with pytest.raises(ValueError, match="high-water"):
        replace(_research_replay_state_position("SHORT"), ratchet_high_water=100.0001)


@pytest.mark.parametrize("field,value", [
    ("entry_price_hex", "0x1p+0"), ("entry_price_hex", "nan"),
    ("entry_price_hex", "inf"), ("entry_price_hex", True),
    ("entry_price_hex", 100.0), ("entry_price_hex", "0x1.0p+999999"),
    ("entry_price_hex", " 0x1.9000000000000p+6"),
    ("entry_atr_hex", "0X1.0000000000000P+1"),
    ("ratchet_stop_hex", "not-a-number"), ("schema", "research-replay-position/2"),
    ("extra", "forged"), ("entry_open_at", "2026-08-29T09:15:00Z"),
])
def test_research_replay_state_position_parser_refuses_noncanonical_hex_and_schema(field, value):
    from app.monitoring.research_replay_state import ResearchReplayPosition
    payload = _research_replay_state_position().to_dict()
    payload[field] = value
    with pytest.raises(ValueError):
        ResearchReplayPosition.from_dict(payload)


@pytest.mark.parametrize("changes", [
    {"owner_id": ""}, {"assignment_id": "bad name"}, {"consumer_address": "invalid"},
    {"canonical_instrument_address": "invalid"}, {"snapshot_sequence": True},
    {"snapshot_sequence": -1}, {"predecessor_snapshot_address": None},
    {"last_bar_identity": None}, {"last_bar_open_at": None}, {"last_bar_completed_at": None},
    {"last_bar_open_at": T0 + timedelta(minutes=3)},
    {"last_bar_completed_at": T0.replace(tzinfo=None)}, {"position": {}}, {"pending": {}},
])
def test_research_replay_state_refuses_incomplete_or_invalid_identity_and_clocks(changes):
    with pytest.raises(ValueError):
        replace(_research_replay_state(), **changes)


def test_research_replay_state_position_cannot_enter_after_last_bar_or_state_sequence():
    position = _research_replay_state_position()
    for changed in (replace(position, entry_sequence=4),
                    replace(position, entry_open_at=T0 + timedelta(minutes=3))):
        with pytest.raises(ValueError):
            _research_replay_state(changed)


@pytest.mark.parametrize("kind,argument,held", [
    ("ENTER", "LONG", False), ("ENTER", "SHORT", False), ("EXIT", "STOP_LOSS", True),
    ("EXIT", "TARGET", True), ("EXIT", "RATCHET_STOP", True), ("EXIT", "STRATEGY_EXIT", True),
    ("REVERSE", "SHORT", True),
])
def test_research_replay_state_pending_decision_roundtrips_exact_last_bar(kind, argument, held):
    from app.monitoring.research_replay_state import ResearchPendingDecision, ResearchReplayState
    pending = ResearchPendingDecision(kind, argument, address("2"), T0 + timedelta(minutes=3))
    position = _research_replay_state_position() if held else None
    state = _research_replay_state(position, pending)
    assert ResearchPendingDecision.from_dict(pending.to_dict()) == pending
    assert ResearchReplayState.from_json(json.dumps(state.to_dict())) == state


@pytest.mark.parametrize("kind,argument,held", [
    ("ENTER", "LONG", True), ("EXIT", "STOP_LOSS", False),
    ("REVERSE", "LONG", True), ("REVERSE", "SHORT", False),
])
def test_research_replay_state_refuses_pending_position_conflicts(kind, argument, held):
    from app.monitoring.research_replay_state import ResearchPendingDecision
    pending = ResearchPendingDecision(kind, argument, address("2"), T0 + timedelta(minutes=3))
    with pytest.raises(ValueError):
        _research_replay_state(_research_replay_state_position() if held else None, pending)


@pytest.mark.parametrize("changes", [
    {"kind": "FILL"}, {"argument": "TRAIL"}, {"decision_bar_identity": "invalid"},
    {"decision_completed_at": T0.replace(tzinfo=None)},
])
def test_research_replay_state_pending_refuses_invalid_closed_values(changes):
    from app.monitoring.research_replay_state import ResearchPendingDecision
    pending = ResearchPendingDecision("EXIT", "STOP_LOSS", address("2"), T0 + timedelta(minutes=3))
    with pytest.raises(ValueError):
        replace(pending, **changes)


def test_research_replay_state_pending_cannot_name_another_bar_or_completion():
    from app.monitoring.research_replay_state import ResearchPendingDecision
    pending = ResearchPendingDecision("ENTER", "LONG", address("2"), T0 + timedelta(minutes=3))
    for changed in (replace(pending, decision_bar_identity=address("3")),
                    replace(pending, decision_completed_at=T0 + timedelta(minutes=4))):
        with pytest.raises(ValueError, match="last bar"):
            _research_replay_state(pending=changed)
    for field in ("schema", "decision_completed_at"):
        payload = pending.to_dict()
        payload[field] = "invalid"
        with pytest.raises(ValueError):
            ResearchPendingDecision.from_dict(payload)


@pytest.mark.parametrize("changes", [
    {"owner_id": "tenant.beta"}, {"address": address("0")},
    {"schema": "research-replay-state/2"}, {"snapshot_sequence": 4}, {"extra": {}},
])
def test_research_replay_state_parser_refuses_tampered_address_or_closed_schema(changes):
    from app.monitoring.research_replay_state import ResearchReplayState
    payload = _research_replay_state().to_dict()
    with pytest.raises(ValueError):
        ResearchReplayState.from_dict({**payload, **changes})


def test_research_replay_state_json_parser_is_bounded_and_rejects_duplicate_or_arbitrary_payloads():
    from app.monitoring.research_replay_state import ResearchReplayState, MAX_STATE_BYTES
    payload = canonical_json(_research_replay_state().to_dict()).encode()
    duplicate = payload.replace(b'"owner_id":', b'"owner_id":"foreign","owner_id":', 1)
    for invalid in (duplicate, b"", b"[]", b"NaN", b"\xff", b" " * (MAX_STATE_BYTES + 1)):
        with pytest.raises(ValueError):
            ResearchReplayState.from_json(invalid)
    nested = _research_replay_state().to_dict()
    nested["position"] = {"arbitrary": "x" * MAX_STATE_BYTES}
    with pytest.raises(ValueError):
        ResearchReplayState.from_dict(nested)


def test_research_prefix_checkpoint_closed_json_and_address_refuse_tampering():
    from app.monitoring.research_prefix import ResearchReplayCheckpoint
    from app.monitoring.research_replay_state import ResearchReplayState
    initial = ResearchReplayCheckpoint(ResearchReplayState('tenant.alpha', 'assignment.alpha', address('7'), address('8'), 0))
    assert ResearchReplayCheckpoint.from_json(canonical_json(initial.to_dict())) == initial
    saved = ResearchReplayCheckpoint(_research_replay_state(), address('3'), 5)
    assert ResearchReplayCheckpoint.from_json(canonical_json(saved.to_dict()).encode()) == saved
    for changes in ({'history_address': address('4')}, {'history_bars': 4}, {'address': address('0')},
                    {'extra': None}, {'schema': 'research-replay-checkpoint/2'}):
        with pytest.raises(ValueError):
            ResearchReplayCheckpoint.from_dict({**saved.to_dict(), **changes})
    for changes in ({'history_address': address('3')}, {'history_bars': True}, {'history_bars': 2001}, {'state': {}}):
        with pytest.raises(ValueError):
            replace(initial, **changes)
    with pytest.raises(ValueError):
        ResearchReplayCheckpoint(_research_replay_state(), address('3'), 2)
    with pytest.raises(ValueError):
        ResearchReplayCheckpoint.from_json('{"schema":"research-replay-checkpoint/1","schema":"duplicate"}')


def _research_monitoring_snapshot_case(risk_policy="none"):
    """Pure snapshot facts; these do not create a monitoring admission or assignment."""
    from app.ir.hashing import content_address
    from app.market_truth.identity import CanonicalPhysicalInstrument
    from app.monitoring.research_prefix import ResearchReplayCheckpoint
    from app.monitoring.research_replay import advance_research_replay
    from app.monitoring.research_state_contracts import compile_research_monitoring_snapshot
    from research.data.canonical_dataset import instrument_key
    from tests.test_v0_monitoring_evaluation_transition import _research_replay_inputs, _research_replay_bars
    state, consumer, instrument, _ = _research_replay_inputs(risk_policy, stop=.05, target=.2)
    physical = CanonicalPhysicalInstrument("fixture", "monitoring-snapshot", "NSE", "EQUITY", "SPOT", "INR", None)
    state = replace(state, canonical_instrument_address=physical.address)
    instrument.name, instrument.key = physical.address, instrument_key(physical.address)
    bars = _research_replay_bars(state)
    arguments = dict(consumer=consumer, instrument=instrument, canonical_instrument=physical,
        source_truth_address=address("a"), evaluation_event_address=address("b"))
    initial = compile_research_monitoring_snapshot(ResearchReplayCheckpoint(state),
        bar=bars[0], previous=None, **arguments)
    snapshots = [initial]
    for index, bar in enumerate(bars[:4], start=1):
        state = advance_research_replay(state, bar, consumer=consumer, instrument=instrument).next_state
        checkpoint = ResearchReplayCheckpoint(state, content_address({"fixture_history": index}), index)
        snapshots.append(compile_research_monitoring_snapshot(checkpoint,
            bar=bar, previous=snapshots[-1], **arguments))
    return snapshots, bars, arguments


@pytest.mark.parametrize("risk_policy", ["none", "pine-v4-ratchet/1", "pine-v4-reversal/1"])
def test_research_monitoring_snapshot_roundtrip_separates_intent_simulation_and_signal_reference(risk_policy):
    from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot
    snapshots, bars, _ = _research_monitoring_snapshot_case(risk_policy)
    assert snapshots[0].strategy_state is contracts.StrategyState.FLAT
    assert snapshots[0].entry_reference.validity is contracts.FactValidity.MISSING
    assert snapshots[1].strategy_state is contracts.StrategyState.LONG
    assert snapshots[1].checkpoint.state.position is None
    assert snapshots[1].stop_loss.status == "UNRESOLVED"
    assert snapshots[2].checkpoint.state.position.entry_price != float(snapshots[2].entry_reference.value)
    assert float(snapshots[2].entry_reference.value) == bars[1].close
    assert snapshots[2].entry_reference.currency == "INR"
    assert snapshots[3].checkpoint.state.position.direction == "LONG"
    if risk_policy == "pine-v4-reversal/1":
        assert snapshots[3].strategy_state is contracts.StrategyState.SHORT
        assert snapshots[3].stop_loss.status == "UNRESOLVED"
        assert snapshots[4].checkpoint.state.position.direction == "SHORT"
    else:
        assert snapshots[3].strategy_state is contracts.StrategyState.FLAT
        assert snapshots[3].stop_loss.status == "RESOLVED"
        assert snapshots[4].checkpoint.state.position is None
    for index, snapshot in enumerate(snapshots):
        assert snapshot.snapshot_sequence == index
        assert snapshot.to_dict()["authority"] == "NONE"
        assert ResearchMonitoringStateSnapshot.from_json(canonical_json(snapshot.to_dict()).encode()) == snapshot
        if index:
            assert snapshot.predecessor_snapshot_address == snapshots[index-1].address
            assert snapshot.checkpoint.state.predecessor_snapshot_address == snapshots[index-1].checkpoint.state.address
            assert snapshot.effective_at == bars[index-1].completed_at


@pytest.mark.parametrize("field,value", [("owner_id", "other-owner"), ("assignment_id", "other-assignment"),
    ("canonical_instrument_address", address("c")), ("snapshot_sequence", True),
    ("snapshot_sequence", 3), ("strategy_state", "SHORT"), ("authority", "LIVE"),
    ("address", address("c")), ("schema", "monitoring-state-snapshot/1")])
def test_research_monitoring_snapshot_refuses_forged_copied_fields_even_with_rehashed_document(field, value):
    from app.ir.hashing import content_address
    from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot
    snapshot = _research_monitoring_snapshot_case()[0][1]
    payload = {**snapshot.to_dict(), field: value}
    if field != "address":
        payload["address"] = content_address({key: item for key, item in payload.items() if key != "address"})
    with pytest.raises(ValueError):
        ResearchMonitoringStateSnapshot.from_dict(payload)


@pytest.mark.parametrize("change", ["checkpoint", "initial_predecessor", "missing_predecessor", "clock",
    "entry_type", "entry_clock", "entry_instrument", "entry_validity", "protection_type",
    "protection_kind", "protection_consumer", "future_fill", "missing_held_levels", "event"])
def test_research_monitoring_snapshot_refuses_invalid_reference_protection_and_state(change):
    snapshots, _, _ = _research_monitoring_snapshot_case()
    snapshot = snapshots[1]
    edits = {"checkpoint": {"checkpoint": {}}, "missing_predecessor": {"predecessor_snapshot_address": None},
        "clock": {"effective_at": snapshot.effective_at+timedelta(seconds=1)}, "entry_type": {"entry_reference": {}},
        "entry_clock": {"entry_reference": replace(snapshot.entry_reference, observed_at=snapshot.effective_at+timedelta(seconds=1))},
        "entry_instrument": {"entry_reference": replace(snapshot.entry_reference, canonical_instrument_address=address("c"))},
        "entry_validity": {"entry_reference": replace(snapshot.entry_reference, value=None, validity=contracts.FactValidity.MISSING)},
        "protection_type": {"stop_loss": {}}, "protection_kind": {"stop_loss": snapshot.take_profit},
        "event": {"evaluation_event_address": "invalid"}}
    with pytest.raises(ValueError):
        if change == "initial_predecessor":
            replace(snapshots[0], predecessor_snapshot_address=address("c"))
        elif change == "protection_consumer":
            changed = replace(snapshot.stop_loss, consumer_address=address("c"),
                rules=tuple(replace(rule, consumer_address=address("c")) for rule in snapshot.stop_loss.rules))
            replace(snapshot, stop_loss=changed)
        elif change == "future_fill":
            resolved = replace(snapshot.stop_loss, rules=tuple(replace(rule, resolved_value=100.0) for rule in snapshot.stop_loss.rules))
            replace(snapshot, stop_loss=resolved)
        elif change == "missing_held_levels":
            snapshot = snapshots[2]
            missing = replace(snapshot.stop_loss, rules=tuple(replace(rule, resolved_value=None) for rule in snapshot.stop_loss.rules))
            replace(snapshot, stop_loss=missing)
        else:
            replace(snapshot, **edits[change])


@pytest.mark.parametrize("change", ["bar_type", "bar_owner", "bar_identity", "previous_type", "initial_previous",
    "wrong_previous", "previous_owner", "inner_predecessor", "history_jump", "physical_instrument", "checkpoint_type"])
def test_research_monitoring_snapshot_compiler_requires_the_exact_previous_step(change):
    from app.monitoring.research_state_contracts import compile_research_monitoring_snapshot
    snapshots, bars, arguments = _research_monitoring_snapshot_case()
    checkpoint, bar, previous = snapshots[2].checkpoint, bars[1], snapshots[1]
    if change == "bar_type":
        bar = {}
    elif change == "bar_owner":
        bar = replace(bar, owner_id="other-owner")
    elif change == "bar_identity":
        bar = replace(bar, opened_at=bar.opened_at+timedelta(seconds=1))
    elif change == "previous_type":
        previous = {}
    elif change == "initial_previous":
        checkpoint, bar = snapshots[0].checkpoint, bars[0]
    elif change == "wrong_previous":
        previous = snapshots[0]
    elif change == "previous_owner":
        previous = replace(previous, checkpoint=replace(previous.checkpoint,
            state=replace(previous.checkpoint.state, owner_id="other-owner")))
        checkpoint = replace(checkpoint, state=replace(checkpoint.state,
            predecessor_snapshot_address=previous.checkpoint.state.address))
    elif change == "inner_predecessor":
        checkpoint = replace(checkpoint, state=replace(checkpoint.state, predecessor_snapshot_address=address("c")))
    elif change == "history_jump":
        checkpoint = replace(checkpoint, history_bars=checkpoint.history_bars+1)
    elif change == "physical_instrument":
        arguments["canonical_instrument"] = replace(arguments["canonical_instrument"], currency="USD")
    else:
        checkpoint = {}
    with pytest.raises(ValueError):
        compile_research_monitoring_snapshot(checkpoint, bar=bar, previous=previous, **arguments)


def test_research_monitoring_snapshot_json_is_closed_bounded_and_rejects_duplicate_keys():
    from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot, research_intent_state
    snapshot = _research_monitoring_snapshot_case()[0][1]
    payload = canonical_json(snapshot.to_dict()).encode()
    duplicate = payload.replace(b'"owner_id":', b'"owner_id":"foreign","owner_id":', 1)
    for invalid in (duplicate, b"", b"[]", b"NaN", b"\xff", b" " * (16*1024+1)):
        with pytest.raises(ValueError):
            ResearchMonitoringStateSnapshot.from_json(invalid)
    with pytest.raises(ValueError):
        ResearchMonitoringStateSnapshot.from_dict({**snapshot.to_dict(), "extra": True})
    with pytest.raises(ValueError):
        research_intent_state({})


def _research_snapshot_repository(session):
    session.add(Organization(organization_id="replay.owner", name="Replay"))
    session.flush()
    session.add(Project(project_id="replay.project", owner_id="replay.owner", name="Replay", status="active"))
    session.flush()
    repository = MonitoringRepository(session, owner_id="replay.owner")
    repository.create_assignment(_spec("replay.assignment", "replay.project"), now=T0)
    return repository


def test_research_snapshot_repository_roundtrip_restart_and_owner_isolation(tmp_path):
    from app.monitoring.repository import _snapshot_from_row
    snapshots, _, _ = _research_monitoring_snapshot_case()
    engine = _engine(tmp_path)
    with Session(engine) as session, session.begin():
        repository = _research_snapshot_repository(session)
        for snapshot in snapshots:
            assert repository.append_state_snapshot(snapshot, created_at=snapshot.effective_at) == snapshot
            assert repository.append_state_snapshot(snapshot, created_at=snapshot.effective_at) == snapshot
        assert repository.get_latest_state(snapshots[0].assignment_id,
            snapshots[0].canonical_instrument_address) == snapshots[0]  # Events advance the projection.
        foreign = MonitoringRepository(session, owner_id="tenant.beta")
        with pytest.raises(MonitoringRefused):
            foreign.append_state_snapshot(snapshots[0], created_at=T0)
    with Session(engine) as session:
        rows = session.scalars(sa.select(MonitoringStateSnapshotRow).where(
            MonitoringStateSnapshotRow.owner_id == "replay.owner").order_by(MonitoringStateSnapshotRow.snapshot_sequence)).all()
        assert tuple(_snapshot_from_row(row) for row in rows) == tuple(snapshots)
        assert all(len(row.canonical_json.encode()) <= 16384 for row in rows)
    engine.dispose()


@pytest.mark.parametrize("change", ["missing", "inner", "sequence", "history", "consumer", "overlap", "repeated_bar"])
def test_research_snapshot_repository_refuses_disconnected_inner_chain(tmp_path, change):
    snapshots, _, _ = _research_monitoring_snapshot_case()
    previous, after = snapshots[1:3]
    if change == "missing":
        after = replace(after, predecessor_snapshot_address=address("0"))
    elif change == "history":
        after = replace(after, checkpoint=replace(after.checkpoint, history_bars=7))
    elif change in ("overlap", "repeated_bar"):
        alteration = ({"last_bar_open_at": previous.checkpoint.state.last_bar_completed_at - timedelta(microseconds=1)}
            if change == "overlap" else {"last_bar_identity": previous.checkpoint.state.last_bar_identity})
        if change == "overlap":
            alteration["position"] = replace(after.checkpoint.state.position,
                entry_open_at=alteration["last_bar_open_at"])
        after = replace(after, checkpoint=replace(after.checkpoint,
            state=replace(after.checkpoint.state, **alteration)))
    else:
        state = after.checkpoint.state
        state = replace(state, **{"inner": {"predecessor_snapshot_address": address("0")},
            "sequence": {"snapshot_sequence": 3}, "consumer": {"consumer_address": address("0")}}[change])
        checkpoint = replace(after.checkpoint, state=state, history_bars=max(3, after.checkpoint.history_bars))
        if change == "consumer":
            # Use internally consistent evidence so persistence must check the prior consumer.
            stop = replace(after.stop_loss, consumer_address=state.consumer_address,
                rules=tuple(replace(rule, consumer_address=state.consumer_address) for rule in after.stop_loss.rules))
            target = replace(after.take_profit, consumer_address=state.consumer_address,
                rules=tuple(replace(rule, consumer_address=state.consumer_address) for rule in after.take_profit.rules))
            after = replace(after, checkpoint=checkpoint, stop_loss=stop, take_profit=target)
        else:
            after = replace(after, checkpoint=checkpoint)
    engine = _engine(tmp_path)
    with Session(engine) as session, session.begin():
        repository = _research_snapshot_repository(session)
        for snapshot in snapshots[:2]:
            repository.append_state_snapshot(snapshot, created_at=snapshot.effective_at)
        with pytest.raises((MonitoringRefused, MonitoringNotFound)):
            repository.append_state_snapshot(after, created_at=after.effective_at)
        assert session.scalar(sa.select(sa.func.count()).select_from(MonitoringStateSnapshotRow)) == 2
    engine.dispose()


@pytest.mark.parametrize("research", [False, True])
def test_research_snapshot_repository_read_checks_copied_effective_time(research):
    from types import SimpleNamespace
    from app.monitoring.repository import _snapshot_from_row
    snapshot = _research_monitoring_snapshot_case()[0][1] if research else _facts()[0]
    row = SimpleNamespace(canonical_json=canonical_json(snapshot.to_dict()), owner_id=snapshot.owner_id,
        assignment_id=snapshot.assignment_id, canonical_instrument_address=snapshot.canonical_instrument_address,
        snapshot_address=snapshot.address, snapshot_sequence=snapshot.snapshot_sequence,
        predecessor_snapshot_address=snapshot.predecessor_snapshot_address, strategy_state=snapshot.strategy_state.value,
        evaluation_event_address=snapshot.evaluation_event_address, effective_at=snapshot.effective_at.replace(tzinfo=None),
        entry_reference_json=canonical_json(snapshot.entry_reference.to_dict()),
        stop_loss_json=canonical_json(snapshot.stop_loss.to_dict()), take_profit_json=canonical_json(snapshot.take_profit.to_dict()))
    assert _snapshot_from_row(row) == snapshot
    row.effective_at += timedelta(seconds=1)
    with pytest.raises(MonitoringCorrupt, match="copied columns"):
        _snapshot_from_row(row)
