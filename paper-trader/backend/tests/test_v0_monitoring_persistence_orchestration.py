from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.ir.hashing import content_address
from app.db.models import (
    MonitoringAlertDeliveryAttemptRow,
    MonitoringSignalAlertRow,
    MonitoringSignalEventRow,
    MonitoringStateSnapshotRow,
)
from app.monitoring import contracts
from app.monitoring.evaluation import MonitoringEvaluationTransition
from app.monitoring.repository import MonitoringRefused, MonitoringRepository
from app.monitoring import runtime as subject
from tests.test_v0_monitoring_persistence import (
    T0,
    _engine,
    _facts,
    _spec,
    _transition,
)
from tests.test_v0_signal_alert_attention_contract import event, protection


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "paper-trader/backend/app/monitoring/runtime.py"


def _compiled(snapshot, event, alert):
    return MonitoringEvaluationTransition(
        next_snapshot=snapshot,
        signal_event=event,
        alert_result=contracts.AlertDerived(alert),
    )


def _hold(previous):
    source = replace(
        _facts()[2],
        previous_state=previous.strategy_state,
        target_state=previous.strategy_state,
        action=contracts.SignalAction.HOLD,
        repeated_target_state=True,
        state_before_address=previous.address,
        state_after_address=previous.address,
        reason_code="NO_TARGET_REQUESTED",
    )
    after = replace(
        previous,
        snapshot_sequence=previous.snapshot_sequence + 1,
        predecessor_snapshot_address=previous.address,
        evaluation_event_address=source.evaluation_event_address,
        effective_at=source.event_at,
    )
    source = replace(source, state_after_address=after.address)
    no_alert = contracts.derive_signal_alert(source)
    assert isinstance(no_alert, contracts.NoAlert)
    return MonitoringEvaluationTransition(after, source, no_alert)


def _seed(repository):
    before, after, event, alert = _facts()
    repository.create_assignment(_spec(), now=T0)
    repository.append_state_snapshot(before, created_at=T0)
    return before, _compiled(after, event, alert)


def _counts(session):
    return tuple(
        session.scalar(sa.select(sa.func.count()).select_from(model))
        for model in (
            MonitoringStateSnapshotRow,
            MonitoringSignalEventRow,
            MonitoringSignalAlertRow,
            MonitoringAlertDeliveryAttemptRow,
        )
    )


def test_alert_transition_persists_once_and_byte_identical_retry_is_idempotent(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        first = subject.persist_monitoring_transition(
            repository, transition, created_at=T0,
        )
        second = subject.persist_monitoring_transition(
            repository, transition, created_at=T0,
        )
        assert first == second
        assert first.snapshot == transition.next_snapshot
        assert first.event == transition.signal_event
        assert first.alert == transition.alert_result.alert
        assert _counts(session) == (2, 1, 1, 0)


def test_hold_transition_persists_event_without_alert(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        before, _transition_value = _seed(repository)
        transition = _hold(before)
        persisted = subject.persist_monitoring_transition(
            repository, transition, created_at=T0,
        )
        assert persisted.alert is None
        assert _counts(session) == (2, 1, 0, 0)


def test_sell_transition_persists_short_state_event_and_alert(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        before, _unused = _seed(repository)
        source = event(
            previous=contracts.StrategyState.FLAT,
            target=contracts.StrategyState.SHORT,
            action=contracts.SignalAction.SELL,
            stop_loss=protection(contracts.ProtectionKind.STOP_LOSS, "110"),
            take_profit=protection(contracts.ProtectionKind.TAKE_PROFIT, "80"),
        )
        after = replace(
            before,
            snapshot_sequence=1,
            predecessor_snapshot_address=before.address,
            strategy_state=contracts.StrategyState.SHORT,
            entry_reference=source.entry_reference,
            stop_loss=source.stop_loss,
            take_profit=source.take_profit,
            evaluation_event_address=source.evaluation_event_address,
            effective_at=source.event_at,
        )
        source = replace(
            source,
            state_before_address=before.address,
            state_after_address=after.address,
        )
        derived = contracts.derive_signal_alert(source)
        assert isinstance(derived, contracts.AlertDerived)
        persisted = subject.persist_monitoring_transition(
            repository, MonitoringEvaluationTransition(after, source, derived),
            created_at=T0,
        )
        assert persisted.snapshot.strategy_state is contracts.StrategyState.SHORT
        assert persisted.event.action is contracts.SignalAction.SELL
        assert persisted.alert.action is contracts.SignalAction.SELL
        assert _counts(session) == (2, 1, 1, 0)


def test_forged_no_alert_cannot_suppress_canonical_buy_alert(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        forged = replace(
            transition,
            alert_result=contracts.NoAlert(
                transition.signal_event.address,
                contracts.NoAlertCode.HOLD,
            ),
        )
        with pytest.raises(subject.MonitoringRuntimeRefusal, match="not canonical"):
            subject.persist_monitoring_transition(repository, forged, created_at=T0)
        assert _counts(session) == (1, 0, 0, 0)


def test_failure_after_snapshot_rolls_back_partial_prefix_and_retry_succeeds(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        real_append_event = repository.append_event

        def fail(*_args, **_kwargs):
            raise RuntimeError("injected after snapshot")

        monkeypatch.setattr(repository, "append_event", fail)
        with pytest.raises(RuntimeError, match="after snapshot"):
            subject.persist_monitoring_transition(repository, transition, created_at=T0)
        assert _counts(session) == (1, 0, 0, 0)
        monkeypatch.setattr(repository, "append_event", real_append_event)
        persisted = subject.persist_monitoring_transition(repository, transition, created_at=T0)
        assert persisted.event == transition.signal_event
        assert _counts(session) == (2, 1, 1, 0)


def test_failure_before_alert_rolls_back_event_projection_and_retry_succeeds(
    tmp_path, monkeypatch,
):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        before, transition = _seed(repository)
        real_append_alert = repository.append_alert

        def fail(*_args, **_kwargs):
            raise RuntimeError("injected before alert")

        monkeypatch.setattr(repository, "append_alert", fail)
        with pytest.raises(RuntimeError, match="before alert"):
            subject.persist_monitoring_transition(repository, transition, created_at=T0)
        assert _counts(session) == (1, 0, 0, 0)
        assert repository.get_latest_state(
            before.assignment_id, before.canonical_instrument_address,
        ) == before
        monkeypatch.setattr(repository, "append_alert", real_append_alert)
        persisted = subject.persist_monitoring_transition(repository, transition, created_at=T0)
        assert persisted.alert == transition.alert_result.alert
        assert _counts(session) == (2, 1, 1, 0)


def test_two_events_persist_one_exact_predecessor_chain(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, first_transition = _seed(repository)
        first = subject.persist_monitoring_transition(
            repository, first_transition, created_at=T0,
        )
        second_snapshot, second_event, second_alert = _transition(first.snapshot, 2)
        second = subject.persist_monitoring_transition(
            repository, _compiled(second_snapshot, second_event, second_alert),
            created_at=second_event.event_at,
        )
        assert second.snapshot.predecessor_snapshot_address == first.snapshot.address
        assert second.event.state_before_address == first.snapshot.address
        assert _counts(session) == (3, 2, 2, 0)


def test_paused_assignment_refusal_rolls_back_successor_snapshot(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        repository.update_assignment(
            transition.signal_event.assignment_id,
            expected_revision=2,
            lifecycle_state="PAUSED",
            now=T0,
        )
        with pytest.raises(MonitoringRefused, match="active assignment"):
            subject.persist_monitoring_transition(repository, transition, created_at=T0)
        assert _counts(session) == (1, 0, 0, 0)


def test_failed_delivery_attempt_is_separate_and_cannot_erase_alert(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        persisted = subject.persist_monitoring_transition(
            repository, transition, created_at=T0,
        )
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        attempt = contracts.AlertDeliveryAttempt.create(
            alert=persisted.alert,
            sequence=1,
            outcome=contracts.DeliveryOutcome.FAILED,
            occurred_at=persisted.alert.event_at,
            failure_code="IN_APP_UNAVAILABLE",
        )
        assert repository.append_delivery_attempt(attempt, created_at=T0) == attempt
        assert _counts(session) == (2, 1, 1, 1)


def test_committed_restart_retry_is_idempotent(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        first = subject.persist_monitoring_transition(repository, transition, created_at=T0)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        second = subject.persist_monitoring_transition(repository, transition, created_at=T0)
        assert second == first
        assert _counts(session) == (2, 1, 1, 0)


def test_runtime_never_commits_caller_transaction(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        subject.persist_monitoring_transition(repository, transition, created_at=T0)
        assert _counts(session) == (2, 1, 1, 0)
        session.rollback()
    with Session(engine) as session:
        assert _counts(session) == (0, 0, 0, 0)


def test_forged_alert_derivation_refuses_before_repository_write(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        forged_alert = replace(
            transition.alert_result.alert,
            monitoring_event_address=content_address({"foreign": "event"}),
        )
        forged = replace(
            transition,
            alert_result=contracts.AlertDerived(forged_alert),
        )
        calls = []
        real_append = repository.append_state_snapshot

        def counted(*args, **kwargs):
            calls.append(True)
            return real_append(*args, **kwargs)

        monkeypatch.setattr(repository, "append_state_snapshot", counted)
        with pytest.raises(subject.MonitoringRuntimeRefusal, match="not canonical"):
            subject.persist_monitoring_transition(repository, forged, created_at=T0)
        assert calls == []
        assert _counts(session) == (1, 0, 0, 0)


def test_exact_runtime_types_owner_scope_and_utc_are_required(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        _before, transition = _seed(repository)
        with pytest.raises(subject.MonitoringRuntimeRefusal, match="exact compiled"):
            subject.persist_monitoring_transition(repository, object(), created_at=T0)
        with pytest.raises(subject.MonitoringRuntimeRefusal, match="exact UTC"):
            subject.persist_monitoring_transition(
                repository, transition, created_at=T0.replace(tzinfo=None),
            )
        foreign = replace(
            transition,
            next_snapshot=replace(transition.next_snapshot, owner_id="tenant.beta"),
        )
        with pytest.raises(subject.MonitoringRuntimeRefusal, match="identity differs"):
            subject.persist_monitoring_transition(repository, foreign, created_at=T0)
        assert _counts(session) == (1, 0, 0, 0)


def test_source_has_no_provider_worker_api_execution_or_money_import():
    tree = ast.parse(SOURCE.read_text())
    imports = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    }
    forbidden = (
        "app.providers", "app.engine", "app.execution", "app.ledger",
        "app.api", "requests", "httpx", "socket", "websocket",
    )
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
# Pure persistence fixtures; the prefix compiler and worker own admission.
def _research_runtime_case(last=3):
    from datetime import timedelta
    from app.monitoring.research_event_contracts import derive_research_signal_alert
    from tests.test_v0_monitoring_evaluation_transition import _research_signal_event_case
    from tests.test_v0_monitoring_persistence import _research_monitoring_snapshot_case
    snapshots, _, _ = _research_monitoring_snapshot_case()
    completed = snapshots[last].effective_at
    cutoff = completed+timedelta(seconds=3)
    transitions = []
    for index in range(1, last+1):
        source = _research_signal_event_case(index=index)
        source = replace(source, prefix_completed_at=completed,
            prefix_available_at=completed+timedelta(seconds=1), prefix_recorded_at=completed+timedelta(seconds=2),
            knowledge_cutoff_at=cutoff, replay_scope="CURRENT" if index == last else "CATCH_UP",
            freshness=contracts.Freshness.FRESH if cutoff <= source.valid_until else contracts.Freshness.STALE)
        transitions.append(MonitoringEvaluationTransition(snapshots[index], source, derive_research_signal_alert(source)))
    return snapshots[0], tuple(transitions), cutoff


def test_research_runtime_persists_full_tail_terminal_alert_and_restart_retry(tmp_path):
    from app.monitoring.research_runtime import persist_research_transitions
    from tests.test_v0_monitoring_persistence import _research_snapshot_repository
    initial, transitions, cutoff = _research_runtime_case()
    engine = _engine(tmp_path)
    with Session(engine) as session, session.begin():
        repository = _research_snapshot_repository(session)
        repository.append_state_snapshot(initial, created_at=initial.effective_at)
        result = persist_research_transitions(repository, transitions, created_at=cutoff)
        assert [item.alert is not None for item in result] == [False, False, True]
        assert _counts(session) == (4, 3, 1, 0)
        assert repository.get_latest_state(initial.assignment_id, initial.canonical_instrument_address) == transitions[-1].next_snapshot
        assert persist_research_transitions(repository, transitions, created_at=cutoff) == result
        assert persist_research_transitions(repository, (), created_at=cutoff) == ()
        assert _counts(session) == (4, 3, 1, 0)
    with Session(engine) as session, session.begin():
        repository = MonitoringRepository(session, owner_id=initial.owner_id)
        assert persist_research_transitions(repository, transitions, created_at=cutoff) == result
        assert repository.list_events(initial.assignment_id).items == tuple(item.signal_event for item in transitions)
        assert repository.list_alerts().items == (result[-1].alert,)
        repository.rebuild_projections()
        assert repository.get_latest_state(initial.assignment_id, initial.canonical_instrument_address) == transitions[-1].next_snapshot
        attention = repository.get_attention_state(initial.assignment_id, result[-1].alert.address)
        assert attention.alert_address == result[-1].alert.address
    engine.dispose()


def test_research_runtime_terminal_alert_failure_rolls_back_every_step_and_keeps_caller_work(tmp_path, monkeypatch):
    from app.monitoring.research_runtime import persist_research_transitions
    from tests.test_v0_monitoring_persistence import _research_snapshot_repository
    initial, transitions, cutoff = _research_runtime_case()
    engine = _engine(tmp_path)
    with Session(engine) as session, session.begin():
        repository = _research_snapshot_repository(session)
        repository.append_state_snapshot(initial, created_at=initial.effective_at)
        original = repository.append_alert
        def refuse(*_args, **_kwargs):
            raise MonitoringRefused("synthetic terminal persistence failure")
        monkeypatch.setattr(repository, "append_alert", refuse)
        with pytest.raises(MonitoringRefused, match="synthetic terminal"):
            persist_research_transitions(repository, transitions, created_at=cutoff)
        assert _counts(session) == (1, 0, 0, 0)
        assert repository.get_latest_state(initial.assignment_id, initial.canonical_instrument_address) == initial
        monkeypatch.setattr(repository, "append_alert", original)
        assert persist_research_transitions(repository, transitions, created_at=cutoff)[-1].alert is not None
        assert _counts(session) == (4, 3, 1, 0)
    engine.dispose()


@pytest.mark.parametrize("change", ["bar", "reference", "stop_loss", "take_profit", "consumer"])
def test_research_event_repository_refuses_internally_valid_evidence_different_from_snapshot(tmp_path, change):
    from tests.test_v0_monitoring_persistence import _research_snapshot_repository
    initial, transitions, cutoff = _research_runtime_case(last=1)
    transition = transitions[0]
    event = transition.signal_event
    if change == "bar":
        event = replace(event, completed_bar_identity=content_address({"different": "bar"}))
    elif change == "reference":
        event = replace(event, entry_reference=replace(event.entry_reference, value="987.5"))
    elif change in ("stop_loss", "take_profit"):
        evidence = getattr(event, change)
        assert evidence.rules
        event = replace(event, **{change: replace(evidence, rules=())})
    else:
        consumer = content_address({"different": "consumer"})
        protections = {name: replace(getattr(event, name), consumer_address=consumer,
            rules=tuple(replace(rule, consumer_address=consumer) for rule in getattr(event, name).rules))
            for name in ("stop_loss", "take_profit")}
        event = replace(event, consumer_address=consumer, **protections)
    # Each event is self-consistent; persistence must compare it to stored replay evidence.
    event.__post_init__()
    engine = _engine(tmp_path)
    with Session(engine) as session, session.begin():
        repository = _research_snapshot_repository(session)
        repository.append_state_snapshot(initial, created_at=initial.effective_at)
        repository.append_state_snapshot(transition.next_snapshot, created_at=cutoff)
        with pytest.raises(MonitoringRefused, match="replay checkpoint"):
            repository.append_event(event, created_at=cutoff)
        assert _counts(session) == (2, 0, 0, 0)
        assert repository.get_latest_state(initial.assignment_id, initial.canonical_instrument_address) == initial
    engine.dispose()


@pytest.mark.parametrize("change", ["reordered", "missing_terminal", "mixed_prefix", "mixed_source", "forged_no_alert", "future_publication", "expired_publication", "wrong_owner", "not_tuple"])
def test_research_runtime_refuses_incomplete_or_mixed_prefix_before_writes(tmp_path, change):
    from datetime import timedelta
    from app.monitoring.research_runtime import persist_research_transitions
    from tests.test_v0_monitoring_persistence import _research_snapshot_repository
    initial, transitions, cutoff = _research_runtime_case()
    if change == "reordered":
        transitions = (transitions[1], transitions[0], transitions[2])
    elif change == "missing_terminal":
        transitions = transitions[:-1]
    elif change in ("mixed_prefix", "mixed_source"):
        field = "evaluation_event_address" if change == "mixed_prefix" else "dataset_address"
        changed = replace(transitions[0].signal_event, **{field: content_address({"different": field})})
        from app.monitoring.research_event_contracts import derive_research_signal_alert
        snapshot = replace(transitions[0].next_snapshot, evaluation_event_address=changed.evaluation_event_address)
        changed = replace(changed, state_after_address=snapshot.address)
        transitions = (MonitoringEvaluationTransition(snapshot, changed, derive_research_signal_alert(changed)), *transitions[1:])
    elif change == "forged_no_alert":
        last = transitions[-1]
        transitions = (*transitions[:-1], replace(last, alert_result=contracts.NoAlert(last.signal_event.address, contracts.NoAlertCode.HOLD)))
    elif change == "future_publication":
        cutoff -= timedelta(microseconds=1)
    elif change == "expired_publication":
        cutoff = transitions[-1].signal_event.valid_until + timedelta(microseconds=1)
    elif change == "not_tuple":
        transitions = list(transitions)
    engine = _engine(tmp_path)
    with Session(engine) as session, session.begin():
        repository = _research_snapshot_repository(session)
        repository.append_state_snapshot(initial, created_at=initial.effective_at)
        if change == "wrong_owner":
            repository = MonitoringRepository(session, owner_id="tenant.beta")
        with pytest.raises(subject.MonitoringRuntimeRefusal):
            persist_research_transitions(repository, transitions, created_at=cutoff)
        assert _counts(session) == (1, 0, 0, 0)
    engine.dispose()
