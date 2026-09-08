"""Restart, mismatch, unknown-state and partial-close proof for V0 paper runtime."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import threading
from decimal import Decimal

import pytest
from dataclasses import replace
from sqlalchemy import select

from app.db.models import (
    AccountExecutionLease, CapitalReservationRecord, Deployment, ExecutionIntent,
    ExecutionOrderEvent, Position, Trade,
)
from app.db.session import SessionLocal
from app.core.instruments import get_instrument
from app.engine.broker import PaperBroker
from app.monitoring.contracts import SignalAction
from app.paper_runtime.contracts import (
    AssignmentLifecycle, BranchStatus, EffectPreference, canonical_runtime_context,
    plan_paper_command,
)
from app.paper_runtime.service import PaperRuntimeService
from app.providers.mock import MockProvider
from app.execution.leases import LeaseRepository, LeaseToken
from tests.test_v0_paper_runtime import AlertSink, _event, _facts, _runtime


class Death(RuntimeError):
    pass


def _restart(alert_sink):
    with SessionLocal() as session:
        row = session.get(AccountExecutionLease, ("owner", "account.default"))
        token = LeaseToken(row.owner_id, row.broker_account_id, row.fence_epoch,
                           row.cell_id, row.worker_id)
    broker = PaperBroker(MockProvider(), owner_id="owner", broker_account_id="account.default",
                         execution_lease_token=token)
    return broker, PaperRuntimeService(broker, alert_sink=alert_sink)


def _open_runtime_entry(broker, authority, command, intent, context_json):
    price = float(command.entry_reference)
    charges = broker._compute_charge(
        authority.charge_segment, "BUY", price,
        authority.approved_quantity)["total"]
    margin = Decimal(authority.required_capital) - Decimal(str(charges))
    return broker.open_equity_position(
        get_instrument(authority.instrument_key), "LONG", price,
        authority.approved_quantity, authority.charge_segment,
        f"PAPER_RUNTIME_ENTRY:{command.client_intent_id}",
        command.event_at.replace(tzinfo=None), margin=float(margin),
        sl_pct=(price - float(command.stop_loss)) / price,
        tp_pct=(float(command.take_profit) - price) / price,
        entry_intent_id=command.client_intent_id,
        strategy_key=authority.strategy_key,
        strategy_version=authority.strategy_version,
        admission_address=authority.admission_address,
        graph_address=authority.graph_address,
        attribution_state=authority.attribution_state,
        recovery_intent=intent, runtime_context_json=context_json)


def test_death_before_intent_leaves_no_durable_effect(admitted_entry_identity, monkeypatch):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)

    def die_before_intent(*_args, **_kwargs):
        raise Death("before_intent")

    monkeypatch.setattr(PaperRuntimeService, "_ensure_intent", die_before_intent)
    with pytest.raises(Death, match="before_intent"):
        PaperRuntimeService(broker, alert_sink=sink).process(
            assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert broker.s.scalar(select(ExecutionIntent)) is None
    assert broker.s.scalar(select(Position)) is None
    broker.close()


def test_death_after_intent_restarts_without_duplicate(admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)

    def die(checkpoint):
        if checkpoint == "after_intent":
            raise Death(checkpoint)

    with pytest.raises(Death, match="after_intent"):
        PaperRuntimeService(broker, alert_sink=sink, death_hook=die).process(
            assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert broker.s.scalar(select(ExecutionIntent)) is not None
    assert broker.s.scalar(select(Position)) is None
    broker.close()
    restarted, service = _restart(sink)
    result = service.process(assignment, authority, event,
                             now=event.event_at + dt.timedelta(minutes=1))
    assert result.paper.status is BranchStatus.APPLIED
    assert len(restarted.s.scalars(select(ExecutionIntent)).all()) == 1
    assert len(restarted.s.scalars(select(Position)).all()) == 1
    restarted.close()


def test_death_after_intent_released_reservation_refuses_direct_broker_money_seam(
        admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)

    def die(checkpoint):
        if checkpoint == "after_intent":
            raise Death(checkpoint)

    with pytest.raises(Death, match="after_intent"):
        PaperRuntimeService(broker, alert_sink=sink, death_hook=die).process(
            assignment, authority, event,
            now=event.event_at + dt.timedelta(minutes=1))
    command = plan_paper_command(
        assignment, authority, event,
        now=event.event_at + dt.timedelta(minutes=1))
    intent = broker.s.get(ExecutionIntent, command.client_intent_id)
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    reservation.state = "released"
    broker.s.commit()
    cash_before = broker.cash()
    context_json = canonical_runtime_context(command, assignment, authority, event)
    with pytest.raises(ValueError, match="CAPITAL_RESERVATION_NOT_AVAILABLE"):
        _open_runtime_entry(broker, authority, command, intent, context_json)
    assert broker.cash() == cash_before
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)) is None
    assert broker.s.get(
        CapitalReservationRecord, authority.reservation_id).state == "released"
    broker.close()


@pytest.mark.parametrize(("field", "change", "refusal"), [
    ("candidate", {"candidate_address": "sha256:" + "2" * 64},
     "DURABLE_CANDIDATE_MISMATCH"),
    ("decision", {"decision_address": "sha256:" + "3" * 64},
     "DURABLE_CAPITAL_DECISION_MISMATCH"),
    ("reservation", {"reservation_address": "sha256:" + "4" * 64},
     "DURABLE_CAPITAL_RESERVATION_MISMATCH"),
    ("required_capital", {"required_capital": "999.0"},
     "DURABLE_CAPITAL_AUTHORITY_MISMATCH"),
    ("charge_segment", {"charge_segment": "BSE_INTRADAY"},
     "DURABLE_CAPITAL_AUTHORITY_MISMATCH"),
])
def test_broker_use_rejects_durable_authority_field_mutations(
        admitted_entry_identity, field, change, refusal):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    forged_authority = replace(authority, **change)
    forged_assignment = replace(
        assignment, instrument_authority_address=forged_authority.address)
    command = plan_paper_command(
        forged_assignment, forged_authority, event,
        now=event.event_at + dt.timedelta(minutes=1))
    context_json = canonical_runtime_context(
        command, forged_assignment, forged_authority, event)
    service = PaperRuntimeService(broker, alert_sink=sink)
    intent, _ = service._ensure_intent(
        service._expected_intent(forged_authority, command, context_json), command)
    cash_before = broker.cash()
    with pytest.raises(ValueError, match=refusal):
        _open_runtime_entry(
            broker, forged_authority, command, intent, context_json)
    assert broker.cash() == cash_before
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)) is None
    broker.close()


@pytest.mark.parametrize("field", ["validity", "authority_window"])
def test_broker_use_rejects_context_validity_and_authority_window_mutations(
        admitted_entry_identity, field):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    command = plan_paper_command(
        assignment, authority, event,
        now=event.event_at + dt.timedelta(minutes=1))
    document = json.loads(canonical_runtime_context(
        command, assignment, authority, event))
    if field == "validity":
        document["monitoring_event"]["evaluation_validity"] = "INVALID"
    else:
        document["instrument_authority"]["valid_until"] = (
            event.event_at - dt.timedelta(seconds=1)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ")
    context_json = json.dumps(document, sort_keys=True, separators=(",", ":"))
    service = PaperRuntimeService(broker, alert_sink=sink)
    intent, _ = service._ensure_intent(
        service._expected_intent(authority, command, context_json), command)
    cash_before = broker.cash()
    with pytest.raises(ValueError, match="PAPER_RUNTIME_CONTEXT_INVALID"):
        _open_runtime_entry(broker, authority, command, intent, context_json)
    assert broker.cash() == cash_before
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)) is None
    broker.close()


def test_killed_then_restored_broker_durable_guard_controls_money_effect(
        admitted_entry_identity, monkeypatch):
    def prepared_released_runtime():
        broker, _, event, assignment, authority, sink = _runtime(
            admitted_entry_identity, preference=EffectPreference.PAPER)

        def die(checkpoint):
            if checkpoint == "after_intent":
                raise Death(checkpoint)

        with pytest.raises(Death, match="after_intent"):
            PaperRuntimeService(
                broker, alert_sink=sink, death_hook=die).process(
                    assignment, authority, event,
                    now=event.event_at + dt.timedelta(minutes=1))
        command = plan_paper_command(
            assignment, authority, event,
            now=event.event_at + dt.timedelta(minutes=1))
        intent = broker.s.get(ExecutionIntent, command.client_intent_id)
        reservation = broker.s.get(
            CapitalReservationRecord, authority.reservation_id)
        reservation.state = "released"
        broker.s.commit()
        return (broker, authority, command, intent,
                canonical_runtime_context(command, assignment, authority, event))

    killed = prepared_released_runtime()
    monkeypatch.setattr(
        "app.paper_runtime.service.validate_durable_runtime_authority",
        lambda *_args, **_kwargs: None)
    cash_before = killed[0].cash()
    _open_runtime_entry(*killed)
    assert killed[0].cash() < cash_before
    assert killed[0].s.scalar(select(Position)) is not None
    killed[0].close()

    monkeypatch.undo()
    restored = prepared_released_runtime()
    cash_before = restored[0].cash()
    with pytest.raises(ValueError, match="CAPITAL_RESERVATION_NOT_AVAILABLE"):
        _open_runtime_entry(*restored)
    assert restored[0].cash() == cash_before
    assert restored[0].s.scalar(select(Position)) is None
    restored[0].close()


def test_death_after_paper_commit_reconstructs_already_applied(admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)

    def die(checkpoint):
        if checkpoint == "after_paper_commit":
            raise Death(checkpoint)

    with pytest.raises(Death, match="after_paper_commit"):
        PaperRuntimeService(broker, alert_sink=sink, death_hook=die).process(
            assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    cash = broker.cash()
    broker.close()
    restarted, service = _restart(sink)
    result = service.process(assignment, authority, event,
                             now=event.event_at + dt.timedelta(minutes=1))
    assert result.paper.status is BranchStatus.ALREADY_APPLIED
    assert restarted.cash() == cash
    assert len(restarted.s.scalars(select(Position)).all()) == 1
    restarted.close()


def test_mismatch_and_unknown_observation_require_reconciliation(admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)

    def die(checkpoint):
        if checkpoint == "after_intent":
            raise Death(checkpoint)

    with pytest.raises(Death):
        PaperRuntimeService(broker, alert_sink=sink, death_hook=die).process(
            assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    intent = broker.s.scalar(select(ExecutionIntent))
    intent.context_json = "{}"
    broker.s.commit()
    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert (result.paper.status, result.paper.refusal) == (
        BranchStatus.RECONCILIATION_REQUIRED, "RECONCILIATION_INTENT_MISMATCH")

    intent.context_json = canonical_runtime_context(
        result.command, assignment, authority, event)
    broker.s.add(ExecutionOrderEvent(
        owner_id="owner", broker_account_id="account.default",
        client_intent_id=intent.client_intent_id, source="paper-test",
        source_event_id="unknown-1", kind="submitted", broker_order_id="",
        broker_status="UNKNOWN", cumulative_filled_qty=0, avg_price=0.0,
        observed_at=event.event_at.replace(tzinfo=None), payload_json="{}", anomaly="unknown",
        fence_epoch=7))
    broker.s.commit()
    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert (result.paper.status, result.paper.refusal) == (
        BranchStatus.RECONCILIATION_REQUIRED, "RECONCILIATION_UNKNOWN_PROVIDER_STATE")
    assert broker.s.scalar(select(Position)) is None
    broker.close()


def test_partial_close_then_exact_exit_and_retry_conserve_money(admitted_entry_identity):
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    service = PaperRuntimeService(broker, alert_sink=sink)
    service.process(assignment, authority, event,
                    now=event.event_at + dt.timedelta(minutes=1))
    pos = broker.s.scalar(select(Position))
    broker.book_partial_close(pos, 4, 103.0, "PARTIAL_TEST",
                              (event.event_at + dt.timedelta(minutes=2)).replace(tzinfo=None),
                              spot=103.0)
    assert broker.s.scalar(select(Position)).qty == 6
    broker.s.get(Deployment, 1).armed = False
    broker.s.commit()
    exit_event = _event(
        identity, action=SignalAction.EXIT, event_minute=4, price="104",
        base_time=event.event_at - dt.timedelta(minutes=1))
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER, authority=authority)
    first = service.process(exit_assignment, exit_authority, exit_event,
                            now=exit_event.event_at + dt.timedelta(minutes=1))
    second = service.process(exit_assignment, exit_authority, exit_event,
                             now=exit_event.event_at + dt.timedelta(minutes=1))
    assert (first.paper.status, second.paper.status) == (
        BranchStatus.APPLIED, BranchStatus.ALREADY_APPLIED)
    assert broker.s.scalar(select(Position)) is None
    assert len(broker.s.scalars(select(Trade)).all()) == 2
    assert broker.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)
    broker.close()


def test_concurrent_duplicate_has_one_intent_position_and_cash_effect(admitted_entry_identity):
    broker, _, event, assignment, authority, _ = _runtime(
        admitted_entry_identity, preference=EffectPreference.BOTH)
    class ConcurrentSink:
        def __init__(self):
            self.effects = set()
            self.lock = threading.Lock()

        def __call__(self, _event, effect_id):
            with self.lock:
                fresh = effect_id not in self.effects
                self.effects.add(effect_id)
                return fresh

    sink = ConcurrentSink()
    cash0 = broker.cash()
    broker.close()
    barrier = threading.Barrier(2)
    outcomes = []
    errors = []

    def run():
        current, service = _restart(sink)
        try:
            barrier.wait()
            result = service.process(
                assignment, authority, event,
                now=event.event_at + dt.timedelta(minutes=1))
            outcomes.append((result.alert.status, result.paper.status))
        except Exception as exc:  # asserted below so thread failures cannot disappear
            errors.append(exc)
        finally:
            current.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)
    assert not errors
    assert sorted(item[0].value for item in outcomes) == ["ALREADY_APPLIED", "APPLIED"]
    assert sorted(item[1].value for item in outcomes) == ["ALREADY_APPLIED", "APPLIED"]
    assert len(sink.effects) == 1
    check, _ = _restart(sink)
    assert len(check.s.scalars(select(ExecutionIntent)).all()) == 1
    assert len(check.s.scalars(select(Position)).all()) == 1
    assert check.cash() < cash0
    check.close()


def test_fresh_process_rebinds_exact_serialized_facts_without_wall_clock_recompute(
        admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    command = plan_paper_command(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    payload = {
        "assignment": assignment.to_dict(), "authority": authority.to_dict(),
        "event": event.to_dict(),
        "command": command.to_dict(),
        "context": canonical_runtime_context(command, assignment, authority, event),
    }
    script = """
import json, sys
from app.paper_runtime.contracts import (PaperCommand, PaperInstrumentAuthority,
    RuntimeAssignment, validate_runtime_context_json)
from app.monitoring.contracts import MonitoringSignalEvent
p = json.load(sys.stdin)
a = RuntimeAssignment.from_dict(p['assignment'])
i = PaperInstrumentAuthority.from_dict(p['authority'])
e = MonitoringSignalEvent.from_dict(p['event'])
c = PaperCommand.from_dict(p['command'], assignment=a, authority=i, event=e)
x = validate_runtime_context_json(p['context'], client_intent_id=c.client_intent_id)
assert a.address == p['assignment']['address']
assert i.address == p['authority']['address']
assert c.address == p['command']['address'] == x['paper_command_address']
print(c.client_intent_id)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(payload), text=True,
        capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == command.client_intent_id
    broker.close()


@pytest.mark.parametrize("lifecycle", [AssignmentLifecycle.PAUSED, AssignmentLifecycle.WITHDRAWN])
def test_correction_paused_and_withdrawn_exact_exit_remain_available(
        admitted_entry_identity, lifecycle):
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    service = PaperRuntimeService(broker, alert_sink=sink)
    service.process(assignment, authority, event,
                    now=event.event_at + dt.timedelta(minutes=1))
    exit_event = _event(
        identity, action=SignalAction.EXIT, event_minute=3, price="105",
        base_time=event.event_at - dt.timedelta(minutes=1))
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER, authority=authority)
    exit_assignment = replace(exit_assignment, lifecycle=lifecycle)
    result = service.process(exit_assignment, exit_authority, exit_event,
                             now=exit_event.event_at + dt.timedelta(minutes=1))
    assert result.paper.status is BranchStatus.APPLIED
    broker.close()


def test_correction_exit_refuses_complete_attribution_mismatch(admitted_entry_identity):
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    service = PaperRuntimeService(broker, alert_sink=sink)
    service.process(assignment, authority, event,
                    now=event.event_at + dt.timedelta(minutes=1))
    exit_event = _event(
        identity, action=SignalAction.EXIT, event_minute=3, price="105",
        base_time=event.event_at - dt.timedelta(minutes=1))
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER, authority=authority)
    forged = replace(exit_authority, strategy_version="wrong-version",
                     attribution_state="NON_GRAPH")
    exit_assignment = replace(exit_assignment, instrument_authority_address=forged.address)
    result = service.process(exit_assignment, forged, exit_event,
                             now=exit_event.event_at + dt.timedelta(minutes=1))
    assert (result.paper.status, result.paper.refusal) == (
        BranchStatus.REFUSED, "STRATEGY_ADMISSION_IDENTITY_MISMATCH")
    assert broker.s.scalar(select(Position)) is not None
    broker.close()


def test_authentic_lease_loss_reclaim_fences_entry_but_preserves_exact_exit(
        admitted_entry_identity):
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.BOTH)
    old_service = PaperRuntimeService(broker, alert_sink=sink)
    old_service.process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    assert reservation.state == "consumed"
    leases = LeaseRepository(SessionLocal)
    database_now = LeaseRepository.database_time(broker.s)
    lease = broker.s.get(AccountExecutionLease, ("owner", "account.default"))
    lease.heartbeat_at = database_now - dt.timedelta(seconds=2)
    lease.expires_at = database_now - dt.timedelta(seconds=1)
    broker.s.commit()
    new_token = leases.claim(
        owner_id="owner", broker_account_id="account.default",
        cell_id="paper-runtime-cell-2", worker_id="paper-runtime-worker-2",
        ttl_seconds=300)
    leases.activate(new_token, reconciliation_evidence="consumed paper reservation is exact")
    stale = old_service.process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert (stale.alert.status, stale.paper.status, stale.paper.refusal) == (
        BranchStatus.ALREADY_APPLIED, BranchStatus.REFUSED, "STALE_EXECUTION_FENCE")
    broker.close()

    current = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default",
        execution_lease_token=new_token)
    exit_authority = replace(authority, fence_epoch=new_token.fence_epoch)
    exit_event = _event(
        identity, action=SignalAction.EXIT, event_minute=3, price="105",
        base_time=event.event_at - dt.timedelta(minutes=1))
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER,
        lifecycle=AssignmentLifecycle.PAUSED, authority=exit_authority)
    result = PaperRuntimeService(current, alert_sink=sink).process(
        exit_assignment, exit_authority, exit_event,
        now=exit_event.event_at + dt.timedelta(minutes=1))
    assert result.paper.status is BranchStatus.APPLIED
    assert current.s.scalar(select(Position)) is None
    current.close()


def test_concurrent_exact_exit_applies_once_and_retry_reconstructs(
        admitted_entry_identity):
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    exit_event = _event(
        identity, action=SignalAction.EXIT, event_minute=3, price="105",
        base_time=event.event_at - dt.timedelta(minutes=1))
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER, authority=authority)
    cash_before = broker.cash()
    broker.close()
    barrier = threading.Barrier(2)
    outcomes = []
    errors = []

    def run():
        current, service = _restart(sink)
        try:
            barrier.wait()
            outcomes.append(service.process(
                exit_assignment, exit_authority, exit_event,
                now=exit_event.event_at + dt.timedelta(minutes=1)).paper.status)
        except Exception as exc:
            errors.append(exc)
        finally:
            current.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)
    assert not errors
    assert sorted(status.value for status in outcomes) == ["ALREADY_APPLIED", "APPLIED"]
    check, _ = _restart(sink)
    assert check.s.scalar(select(Position)) is None
    trades = list(check.s.scalars(select(Trade).where(
        Trade.exit_reason.like("PAPER_RUNTIME_EXIT:%"))))
    assert len(trades) == 1
    assert check.cash() > cash_before
    check.close()
