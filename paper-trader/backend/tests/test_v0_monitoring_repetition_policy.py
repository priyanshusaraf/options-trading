"""Transition-edge idempotency is the V0 repetition policy."""
from __future__ import annotations

import datetime as dt
from dataclasses import replace

import pytest
from sqlalchemy import select

from app.db.models import Position, Trade
from app.monitoring.contracts import AlertDerived, NoAlert, SignalAction, StrategyState
from app.paper_runtime.contracts import AssignmentLifecycle, BranchStatus, EffectPreference
from app.paper_runtime.service import PaperRuntimeService, _effect_id
from tests.test_v0_monitoring_evaluation_transition import _compile
from tests.test_v0_paper_runtime import _event, _facts, _runtime


def test_rapid_flat_long_flat_long_keeps_all_three_transition_edges():
    transitions = (
        _compile(target="BUY", previous_state=StrategyState.FLAT, event_second=0),
        _compile(target="CLOSE_POSITION", previous_state=StrategyState.LONG, event_second=1),
        _compile(target="BUY", previous_state=StrategyState.FLAT, event_second=2),
    )
    assert [item.signal_event.action for item in transitions] == [
        SignalAction.BUY, SignalAction.EXIT, SignalAction.BUY]
    assert all(isinstance(item.alert_result, AlertDerived) for item in transitions)
    assert len({item.signal_event.address for item in transitions}) == 3
    assert transitions[-1].signal_event.event_at - transitions[0].signal_event.event_at < dt.timedelta(minutes=1)


def test_repeated_target_and_exact_retry_add_no_effect_and_wall_time_is_irrelevant():
    repeated = _compile(target="BUY", previous_state=StrategyState.LONG, event_second=1)
    assert repeated.signal_event.repeated_target_state is True
    assert isinstance(repeated.alert_result, NoAlert)
    exact = _compile(target="BUY", previous_state=StrategyState.FLAT, event_second=0)
    replay = _compile(target="BUY", previous_state=StrategyState.FLAT, event_second=0)
    assert exact.signal_event.address == replay.signal_event.address
    assert exact.alert_result.alert.address == replay.alert_result.alert.address
    assignment_address = "sha256:" + "a" * 64
    assert _effect_id("alert", assignment_address, exact.signal_event.address) == _effect_id(
        "alert", assignment_address, replay.signal_event.address)


@pytest.mark.parametrize("lifecycle", [AssignmentLifecycle.PAUSED, AssignmentLifecycle.WITHDRAWN])
def test_risk_reducing_exit_is_not_suppressed_by_pause_withdrawal_or_retry(
        admitted_entry_identity, lifecycle):
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    service = PaperRuntimeService(broker, alert_sink=sink)
    opened = service.process(assignment, authority, event,
                             now=event.event_at + dt.timedelta(minutes=1))
    assert opened.paper.status is BranchStatus.APPLIED
    exit_event = _event(identity, action=SignalAction.EXIT, event_minute=3,
                        base_time=event.event_at)
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER, authority=authority)
    inactive = replace(exit_assignment, lifecycle=lifecycle)
    closed = service.process(inactive, exit_authority, exit_event,
                             now=exit_event.event_at + dt.timedelta(minutes=1))
    assert closed.paper.status is BranchStatus.APPLIED
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)) is not None
    retry = service.process(inactive, exit_authority, exit_event,
                            now=exit_event.event_at + dt.timedelta(minutes=1, seconds=10))
    assert retry.paper.status is BranchStatus.ALREADY_APPLIED
    broker.close()
