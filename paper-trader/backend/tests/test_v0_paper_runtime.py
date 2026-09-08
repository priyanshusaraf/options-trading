"""Critical contract and SQLite integration proof for the V0 paper runtime."""
from __future__ import annotations

import datetime as dt
import socket
import json
from dataclasses import replace

import pytest
from sqlalchemy import select

from app.backtest.repository import AdmissionRequired
from app.db.models import (
    CandidateIntentRecord, CapitalReservationHead, CapitalReservationRecord,
    Deployment, ExecutionIntent,
    PortfolioAdmissionDecisionRecord, Position, SizingDecisionRecord,
    SizingPolicyRecord, StrategyAdmission, TargetPositionRequestRecord, Trade,
)
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.execution.capital_admission import (
    AdmissionBatch, AdmissionCandidate, admit_closed_batch, current_held_pending_digest,
)
from app.execution.leases import LeaseRepository
from app.ir.hashing import canonical_json, content_address
from app.monitoring.contracts import (
    EntryReference, EntryReferenceKind, FactValidity, Freshness, MonitoringSignalEvent,
    ProtectionBasis, ProtectionEvidence, ProtectionKind, ProtectionUnits, SignalAction,
    StrategyState,
)
from app.paper_runtime.contracts import (
    AssignmentLifecycle, BranchResult, BranchStatus, EffectPreference, PaperAction,
    PaperInstrumentAuthority, PaperRuntimeRefusal, RuntimeAssignment,
    canonical_runtime_context, deterministic_client_intent_id, plan_paper_command,
    PaperCommand, RuntimeResult, validate_runtime_context_json,
    paper_book_scope_address, validate_runtime_relations,
)
from app.paper_runtime.service import PaperRuntimeService
from app.paper_runtime.service import (
    MAX_EVENTS_PER_INVOCATION, MAX_INTERNAL_QUEUE_DEPTH, MAX_POSITIONS_PER_INSTRUMENT,
)
from app.providers.mock import MockProvider


UTC = dt.timezone.utc
T0 = dt.datetime.now(UTC).replace(microsecond=0)


def address(letter: str) -> str:
    return "sha256:" + letter * 64


def _protection(kind: ProtectionKind, value: str) -> ProtectionEvidence:
    return ProtectionEvidence(
        kind=kind, basis=ProtectionBasis.ABSOLUTE_PRICE,
        authored_component_id="intent.fixed_protection", authored_component_version=1,
        authored_component_address=address("9"), authored_contract_address=address("a"),
        authored_parameters_address=address("b"), authored_value=value,
        units=ProtectionUnits.PRICE, resolved_value=value,
        resolution_address=address("c"), validity=FactValidity.VALID)


def _event(identity, *, action=SignalAction.BUY, event_minute=1, base_time=T0,
           owner="owner", assignment_id="monitoring.alpha", price="100",
           stop="90", target="120", valid_until=None) -> MonitoringSignalEvent:
    states = {
        SignalAction.BUY: (StrategyState.FLAT, StrategyState.LONG),
        SignalAction.SELL: (StrategyState.FLAT, StrategyState.SHORT),
        SignalAction.EXIT: (StrategyState.LONG, StrategyState.FLAT),
        SignalAction.HOLD: (StrategyState.FLAT, StrategyState.FLAT),
    }
    previous, target_state = states[action]
    event_at = base_time + dt.timedelta(minutes=event_minute)
    return MonitoringSignalEvent(
        owner_id=owner, assignment_id=assignment_id, strategy_id=identity["strategy_key"],
        graph_version_address=identity["graph_address"], resolved_graph_address=address("3"),
        implementation_closure_address=address("4"), admission_address=identity["admission_address"],
        canonical_instrument_address=address("7"), display_symbol="NIFTY 50",
        previous_state=previous, target_state=target_state, action=action,
        evaluation_event_address=address("6"), event_at=event_at,
        latest_data_at=event_at - dt.timedelta(minutes=1),
        knowledge_cutoff_at=event_at + dt.timedelta(minutes=1),
        valid_until=valid_until or event_at + dt.timedelta(minutes=5),
        evaluation_validity=FactValidity.VALID, freshness=Freshness.FRESH,
        repeated_target_state=False,
        entry_reference=EntryReference(
            kind=EntryReferenceKind.COMPLETED_EVENT_CLOSE,
            canonical_instrument_address=address("7"), value=price, currency="INR",
            observed_at=event_at - dt.timedelta(minutes=1), source_truth_address=address("8"),
            validity=FactValidity.VALID),
        stop_loss=_protection(ProtectionKind.STOP_LOSS, stop),
        take_profit=_protection(ProtectionKind.TAKE_PROFIT, target),
        state_before_address=address("0"), state_after_address=address("1"),
        provider_evidence_address=address("d"), dataset_address=address("e"),
        reason_code="TARGET_STATE_CHANGED", reason_evidence_address=address("f"))


def _facts(identity, event, *, preference=EffectPreference.BOTH,
           lifecycle=AssignmentLifecycle.ACTIVE, authority=None):
    if authority is None:
        raise AssertionError("tests must supply durable capital authority")
    assignment = RuntimeAssignment(
        owner_id=event.owner_id, monitoring_assignment_id=event.assignment_id,
        preference=preference, lifecycle=lifecycle, deployment_id=1,
        graph_version_address=event.graph_version_address,
        resolved_graph_address=event.resolved_graph_address,
        implementation_closure_address=event.implementation_closure_address,
        instrument_authority_address=authority.address,
        effective_from=authority.valid_from, valid_until=authority.valid_until)
    return assignment, authority


def _seed_capital_authority(broker, identity, event, token, *, total_minor=100_000):
    session = broker.s
    policy = content_address({"paper-runtime-sizing": "fixed-units-v1"})
    product = content_address({"paper-runtime-product": "equity-v1"})
    target_id = "paper-runtime-target"
    candidate_id = "paper-runtime-candidate"
    sizing_address = content_address({"paper-runtime-sizing-decision": event.action.value})
    event_time = event.event_at.replace(tzinfo=None)
    recorded_at = LeaseRepository.database_time(session) - dt.timedelta(seconds=1)
    if session.get(SizingPolicyRecord, policy) is None:
        session.add(SizingPolicyRecord(
            policy_address=policy, policy_id="paper-runtime-fixed", version=1,
            mode="FIXED_UNITS", currency="INR", fixed_units=10, fixed_lots=None,
            amount_minor=None, rate_ppm=None, risk_budget_minor=None,
            target_volatility_ppm=None, min_quantity=1, max_quantity=10,
            max_capital_minor=total_minor, fee_buffer_minor=0, safety_buffer_minor=0,
            allow_resize=False, canonical_json="{}", created_at=recorded_at))
        session.flush()
    session.add(SizingDecisionRecord(
        decision_address=sizing_address, policy_address=policy, product_address=product,
        inputs_address=content_address({"paper-runtime-inputs": event.address}), accepted=True,
        requested_quantity=10, admitted_quantity=10,
        required_capital_minor=total_minor, estimated_fees_minor=0,
        binding_constraint="capital", reason_code="SIZED", resized=False,
        input_addresses_json="[]", decided_at=recorded_at))
    session.flush()
    session.add(TargetPositionRequestRecord(
        request_id=target_id, request_address=content_address({"paper-runtime-target": event.address}),
        owner_id="owner", broker_account_id="account.default", book="paper", deployment_id=1,
        strategy_key=identity["strategy_key"], strategy_version=identity["strategy_version"],
        admission_address=identity["admission_address"], graph_address=identity["graph_address"],
        attribution_state=identity["attribution_state"], canonical_instrument_key="NIFTY",
        product_address=product, sizing_decision_address=sizing_address,
        target_quantity=(10 if event.action is not SignalAction.SELL else -10),
        purpose="ENTRY", group_id="", decision_at=recorded_at))
    session.flush()
    if session.get(CapitalReservationHead, ("owner", "account.default", "paper", "INR")) is None:
        session.add(CapitalReservationHead(
            owner_id="owner", broker_account_id="account.default", book="paper",
            currency="INR", revision=0, updated_at=recorded_at))
    session.commit()
    pending = current_held_pending_digest(
        session, owner_id="owner", broker_account_id="account.default",
        book="paper", currency="INR")
    direction = "SHORT" if event.action is SignalAction.SELL else "LONG"
    signed_qty = -10 if direction == "SHORT" else 10
    candidate = AdmissionCandidate(
        candidate_intent_id=candidate_id, deployment_id=1,
        strategy_key=identity["strategy_key"], strategy_version=identity["strategy_version"],
        admission_address=identity["admission_address"], graph_address=identity["graph_address"],
        attribution_state=identity["attribution_state"], signal_instrument_key="NIFTY",
        execution_instrument_key="NIFTY 50", product_address=product,
        sizing_decision_address=sizing_address, target_position_request_id=target_id,
        direction=direction, purpose="ENTRY", requested_quantity=signed_qty,
        required_capital_minor=total_minor, group_id="", group_semantics="INDEPENDENT",
        freshness_deadline=event_time + dt.timedelta(hours=1), priority=1, score_scaled=100,
        held_pending_digest=pending, created_at=recorded_at)
    batch = AdmissionBatch(
        decision_batch_id="paper-runtime-batch", owner_id="owner",
        broker_account_id="account.default", book="paper", currency="INR",
        fence_epoch=token.fence_epoch, decision_at=recorded_at, effective_at=recorded_at,
        capital_snapshot_minor=5_000_000,
        capital_snapshot_address=content_address({"paper-runtime-capital": 5_000_000}),
        margin_available_minor=5_000_000, margin_source="paper-runtime-fixture",
        margin_observed_at=recorded_at,
        margin_snapshot_address=content_address({"paper-runtime-margin": 5_000_000}),
        safety_buffer_minor=0, expected_head_revision=0,
        product_policy_address=content_address({"paper-runtime-product-policy": 1}),
        sizing_policy_address=policy,
        portfolio_policy_address=content_address({"paper-runtime-portfolio-policy": 1}),
        candidates=(candidate,), reservation_ttl_seconds=300)
    result = admit_closed_batch(session, LeaseRepository(SessionLocal), token, batch)
    session.commit()
    admitted = result.decisions[0]
    decision = session.scalar(select(PortfolioAdmissionDecisionRecord).where(
        PortfolioAdmissionDecisionRecord.candidate_intent_id == candidate_id))
    reservation = session.get(CapitalReservationRecord, admitted.reservation_id)
    return PaperInstrumentAuthority(
        owner_id="owner", monitoring_assignment_id=event.assignment_id, deployment_id=1,
        broker_account_id="account.default", instrument_key="NIFTY",
        strategy_key=identity["strategy_key"], strategy_version=identity["strategy_version"],
        graph_address=identity["graph_address"], attribution_state=identity["attribution_state"],
        canonical_instrument_address=event.canonical_instrument_address,
        admission_address=identity["admission_address"], candidate_intent_id=candidate_id,
        candidate_address=session.get(CandidateIntentRecord, candidate_id).candidate_address,
        decision_id=decision.decision_id, decision_address=decision.decision_address,
        reservation_id=reservation.reservation_id,
        reservation_address=reservation.reservation_address, approved_quantity=10,
        required_capital=f"{total_minor / 100:.1f}", charge_segment="NSE_INTRADAY",
        paper_book_address=paper_book_scope_address("owner", "account.default"),
        fence_epoch=token.fence_epoch, valid_from=recorded_at.replace(tzinfo=UTC),
        valid_until=recorded_at.replace(tzinfo=UTC) + dt.timedelta(hours=1))


class AlertSink:
    def __init__(self):
        self.effects = set()

    def __call__(self, _event, effect_id):
        fresh = effect_id not in self.effects
        self.effects.add(effect_id)
        return fresh


def _runtime(admitted_entry_identity, *, preference=EffectPreference.BOTH,
             action=SignalAction.BUY, price="100", stop="90", target="120",
             capital="1000.0"):
    init_db(reset=True)
    leases = LeaseRepository(SessionLocal)
    token = leases.claim(owner_id="owner", broker_account_id="account.default",
                         cell_id="paper-runtime-cell", worker_id="paper-runtime-worker",
                         ttl_seconds=300)
    leases.activate(token, reconciliation_evidence="synthetic paper runtime fixture is clean")
    broker = PaperBroker(MockProvider(), owner_id="owner", broker_account_id="account.default",
                         execution_lease_token=token)
    identity = admitted_entry_identity(broker.s)
    deployment = broker.s.get(Deployment, 1)
    deployment.armed = True
    broker.s.commit()
    time_anchor = LeaseRepository.database_time(broker.s).replace(tzinfo=UTC)
    broker.s.commit()
    event = _event(identity, action=action, price=price, stop=stop, target=target,
                   base_time=time_anchor)
    authority = _seed_capital_authority(
        broker, identity, event, token, total_minor=int(float(capital) * 100))
    assignment, authority = _facts(
        identity, event, preference=preference, authority=authority)
    sink = AlertSink()
    return broker, identity, event, assignment, authority, sink


def test_closed_contracts_have_no_preference_default_and_reject_tampering(admitted_entry_identity):
    broker, _, event, assignment, authority, _ = _runtime(admitted_entry_identity)
    assert {item.value for item in EffectPreference} == {"ALERTS", "PAPER", "BOTH"}
    assert RuntimeAssignment.from_dict(assignment.to_dict()) == assignment
    assert PaperInstrumentAuthority.from_dict(authority.to_dict()) == authority
    tampered = assignment.to_dict()
    tampered["preference"] = "LIVE"
    with pytest.raises(PaperRuntimeRefusal):
        RuntimeAssignment.from_dict(tampered)
    command = plan_paper_command(assignment, authority, event,
                                 now=event.event_at + dt.timedelta(minutes=1))
    assert PaperCommand.from_dict(
        command.to_dict(), assignment=assignment, authority=authority, event=event) == command
    assert command.client_intent_id == deterministic_client_intent_id(
        assignment.address, event.address, PaperAction.BUY)
    assert len(command.client_intent_id) == 32 and command.client_intent_id.islower()
    context = canonical_runtime_context(command, assignment, authority, event)
    assert assignment.address in context and event.address in context
    assert validate_runtime_context_json(
        context, client_intent_id=command.client_intent_id)["paper_command_address"] == command.address
    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_CONTEXT_NOT_CANONICAL"):
        validate_runtime_context_json(context + " ", client_intent_id=command.client_intent_id)
    result = PaperRuntimeService(broker, alert_sink=AlertSink()).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert RuntimeResult.from_dict(
        result.to_dict(), assignment=assignment, authority=authority, event=event) == result
    broker.close()


@pytest.mark.parametrize(
    ("preference", "alerts", "positions"),
    [(EffectPreference.ALERTS, 1, 0), (EffectPreference.PAPER, 0, 1),
     (EffectPreference.BOTH, 1, 1)],
)
def test_alert_and_paper_branches_are_exact_and_independent(
        admitted_entry_identity, preference, alerts, positions):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=preference)
    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert len(sink.effects) == alerts
    assert len(broker.s.scalars(select(Position)).all()) == positions
    assert result.alert.status is (BranchStatus.APPLIED if alerts else BranchStatus.NOT_SELECTED)
    assert result.paper.status is (BranchStatus.APPLIED if positions else BranchStatus.NOT_SELECTED)
    broker.close()


@pytest.mark.parametrize(
    ("action", "stop", "target", "direction"),
    [(SignalAction.BUY, "90", "120", "LONG"),
     (SignalAction.SELL, "110", "80", "SHORT")],
)
def test_buy_and_sell_book_exact_position_money_and_context(
        admitted_entry_identity, action, stop, target, direction):
    broker, _, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER,
        action=action, stop=stop, target=target)
    cash0 = broker.cash()
    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    pos = broker.s.scalar(select(Position))
    intent = broker.s.get(ExecutionIntent, result.command.client_intent_id)
    assert (pos.direction, pos.qty, pos.stop_price, pos.target_price) == (
        direction, 10, float(stop), float(target))
    assert (pos.entry_intent_id, pos.admission_address, pos.graph_address) == (
        result.command.client_intent_id, authority.admission_address, authority.graph_address)
    assert assignment.address in intent.context_json and event.address in intent.context_json
    assert cash0 - broker.cash() == pytest.approx(pos.entry_cost)
    assert broker.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)
    broker.close()


def test_duplicate_both_retry_does_not_duplicate_alert_or_money(admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(admitted_entry_identity)
    service = PaperRuntimeService(broker, alert_sink=sink)
    first = service.process(assignment, authority, event,
                            now=event.event_at + dt.timedelta(minutes=1))
    cash = broker.cash()
    second = service.process(assignment, authority, event,
                             now=event.event_at + dt.timedelta(minutes=1))
    assert first.paper.status is BranchStatus.APPLIED
    assert (second.alert.status, second.paper.status) == (
        BranchStatus.ALREADY_APPLIED, BranchStatus.ALREADY_APPLIED)
    assert len(sink.effects) == 1
    assert len(broker.s.scalars(select(Position)).all()) == 1
    assert len(broker.s.scalars(select(ExecutionIntent)).all()) == 1
    assert broker.cash() == cash
    broker.close()


def test_alert_failure_does_not_suppress_paper_effect(admitted_entry_identity):
    broker, _, event, assignment, authority, _ = _runtime(admitted_entry_identity)

    def failed_alert(_event, _effect_id):
        raise RuntimeError("synthetic alert outage")

    result = PaperRuntimeService(broker, alert_sink=failed_alert).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert result.alert.status is BranchStatus.REFUSED
    assert result.paper.status is BranchStatus.APPLIED
    assert len(broker.s.scalars(select(Position)).all()) == 1
    broker.close()


def test_hold_has_no_alert_or_paper_effect(admitted_entry_identity):
    broker, identity, _, _, authority, sink = _runtime(admitted_entry_identity)
    event = _event(identity, action=SignalAction.HOLD,
                   base_time=authority.valid_from)
    assignment, authority = _facts(identity, event, authority=authority)
    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert (result.alert.status, result.paper.status) == (
        BranchStatus.NO_EFFECT, BranchStatus.NO_EFFECT)
    assert not sink.effects and broker.s.scalar(select(Position)) is None
    broker.close()


def test_exit_closes_exact_held_position_while_entry_is_disarmed(admitted_entry_identity):
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER)
    service = PaperRuntimeService(broker, alert_sink=sink)
    service.process(assignment, authority, event,
                    now=event.event_at + dt.timedelta(minutes=1))
    broker.s.get(Deployment, 1).armed = False
    broker.s.commit()
    exit_event = _event(identity, action=SignalAction.EXIT, event_minute=3,
                        base_time=event.event_at - dt.timedelta(minutes=1),
                        price="105", stop="90", target="120")
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER, authority=authority)
    closed = service.process(exit_assignment, exit_authority, exit_event,
                             now=exit_event.event_at + dt.timedelta(minutes=1))
    assert closed.paper.status is BranchStatus.APPLIED
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)).exit_reason.startswith("PAPER_RUNTIME_EXIT:")
    assert broker.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)
    retry = service.process(exit_assignment, exit_authority, exit_event,
                            now=exit_event.event_at + dt.timedelta(minutes=1))
    assert retry.paper.status is BranchStatus.ALREADY_APPLIED
    broker.close()


def test_fence_lifecycle_expiry_foreign_capital_and_provider_poison_refuse(
        admitted_entry_identity, monkeypatch):
    broker, identity, event, assignment, authority, sink = _runtime(admitted_entry_identity)
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("paper runtime attempted network access")))
    service = PaperRuntimeService(broker, alert_sink=sink)
    stale = replace(authority, fence_epoch=8)
    stale_assignment = replace(assignment, instrument_authority_address=stale.address)
    stale_result = service.process(
        stale_assignment, stale, event, now=event.event_at + dt.timedelta(minutes=1))
    assert (stale_result.alert.status, stale_result.paper.status,
            stale_result.paper.refusal) == (
        BranchStatus.APPLIED, BranchStatus.REFUSED,
        "RUNTIME_BROKER_RELATION_MISMATCH")
    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_ASSIGNMENT_NOT_ACTIVE_FOR_ENTRY"):
        service.process(replace(assignment, lifecycle=AssignmentLifecycle.PAUSED), authority, event,
                        now=event.event_at + dt.timedelta(minutes=1))
    expired = _event(
        identity, base_time=event.event_at - dt.timedelta(minutes=1),
        valid_until=event.event_at + dt.timedelta(minutes=1, seconds=30))
    expired_assignment, expired_authority = _facts(identity, expired, authority=authority)
    with pytest.raises(PaperRuntimeRefusal, match="MONITORING_EVENT_EXPIRED"):
        service.process(expired_assignment, expired_authority, expired,
                        now=expired.valid_until + dt.timedelta(seconds=1))
    foreign = _event(identity, owner="other",
                     base_time=event.event_at - dt.timedelta(minutes=1))
    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_AUTHORITY_MISMATCH"):
        service.process(assignment, authority, foreign,
                        now=foreign.event_at + dt.timedelta(minutes=1))
    broker.capital().cash = 1.0
    broker.s.commit()
    refused = service.process(assignment, authority, event,
                              now=event.event_at + dt.timedelta(minutes=1))
    assert (refused.paper.status, refused.paper.refusal) == (
        BranchStatus.REFUSED, "CAPITAL_REFUSED")

    class PoisonPaperBroker(PaperBroker):
        pass
    poison = PoisonPaperBroker(MockProvider(), owner_id="owner", broker_account_id="account.default")
    with pytest.raises(PaperRuntimeRefusal, match="EXACT_PAPER_BROKER_REQUIRED"):
        PaperRuntimeService(poison, alert_sink=sink)
    poison.close()
    from app.engine.live_broker import LiveBroker
    with pytest.raises(PaperRuntimeRefusal, match="EXACT_PAPER_BROKER_REQUIRED"):
        PaperRuntimeService(object.__new__(LiveBroker), alert_sink=sink)
    broker.close()


def test_correction_rejects_non_finite_capital_and_future_event(admitted_entry_identity):
    broker, identity, event, assignment, authority, sink = _runtime(admitted_entry_identity)
    with pytest.raises(PaperRuntimeRefusal, match="REQUIRED_CAPITAL_CANONICAL_REQUIRED"):
        replace(authority, required_capital="nan")
    with pytest.raises(PaperRuntimeRefusal, match="MONITORING_EVENT_IN_FUTURE"):
        PaperRuntimeService(broker, alert_sink=sink).process(
            assignment, authority, event, now=event.event_at - dt.timedelta(seconds=1))
    broker.close()


def test_correction_context_and_result_semantics_reject_forgery(admitted_entry_identity):
    broker, _, event, assignment, authority, _ = _runtime(admitted_entry_identity)
    command = plan_paper_command(assignment, authority, event, now=event.event_at)
    context = json.loads(canonical_runtime_context(command, assignment, authority, event))
    context["action"] = "SELL"
    forged = json.dumps(context, sort_keys=True, separators=(",", ":"))
    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_CONTEXT_INTENT_MISMATCH"):
        validate_runtime_context_json(forged, client_intent_id=command.client_intent_id)
    with pytest.raises(PaperRuntimeRefusal, match="BRANCH_EFFECT_ID_REQUIRED"):
        BranchResult("PAPER", BranchStatus.APPLIED, None, None)
    context = json.loads(canonical_runtime_context(command, assignment, authority, event))
    context["paper_command_address"] = address("0")
    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_CONTEXT_COMMAND_MISMATCH"):
        validate_runtime_context_json(
            json.dumps(context, sort_keys=True, separators=(",", ":")),
            client_intent_id=command.client_intent_id)
    result = PaperRuntimeService(broker, alert_sink=AlertSink()).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    forged_result = result.to_dict()
    forged_result["preference"] = "ALERTS"
    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_RESULT_SELECTION_MISMATCH"):
        RuntimeResult.from_dict(
            forged_result, assignment=assignment, authority=authority, event=event)
    broker.close()


@pytest.mark.parametrize("receipt_failure", ["missing", "corrupt"])
def test_reviewer_probe_admission_failure_preserves_alert_and_refuses_paper_before_effect(
        admitted_entry_identity, receipt_failure, monkeypatch):
    broker, _, event, assignment, authority, sink = _runtime(admitted_entry_identity)
    if receipt_failure == "missing":
        missing_address = address("2")
        event = replace(event, admission_address=missing_address)
        authority = replace(authority, admission_address=missing_address)
        assignment = replace(
            assignment, instrument_authority_address=authority.address)
    else:
        def corrupt_loader(*_args, **_kwargs):
            raise AdmissionRequired("RECEIPT_STALE")
        monkeypatch.setattr(
            "app.paper_runtime.service.load_verified_admission", corrupt_loader)
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    before = (broker.capital().cash, reservation.state, reservation.command_id)

    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))

    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    assert result.alert.status is BranchStatus.APPLIED
    assert (result.paper.status, result.paper.refusal) == (
        BranchStatus.REFUSED, "STRATEGY_ADMISSION_INVALID")
    assert broker.s.scalar(select(ExecutionIntent)) is None
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)) is None
    assert (broker.capital().cash, reservation.state, reservation.command_id) == before
    broker.close()


def test_real_loader_refuses_noncanonical_persisted_receipt_before_paper_effect(
        admitted_entry_identity):
    def persist_noncanonical(session):
        identity = admitted_entry_identity(session)
        current = session.get(
            StrategyAdmission, ("owner", identity["admission_address"]))
        corrupt_address = address("2")
        session.execute(StrategyAdmission.__table__.insert().values(
            owner_id=current.owner_id, admission_address=corrupt_address,
            graph_identifier=current.graph_identifier,
            graph_version=current.graph_version, graph_address=current.graph_address,
            artifact_json=current.artifact_json + " ", scheme=current.scheme,
            contract_suite=current.contract_suite, parity_suite=current.parity_suite,
            format_version=current.format_version,
            content_address=current.content_address,
            created_at=current.created_at))
        session.commit()
        return {**identity, "admission_address": corrupt_address}

    broker, _, event, assignment, authority, sink = _runtime(
        persist_noncanonical, preference=EffectPreference.BOTH)
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    before = (broker.capital().cash, reservation.state, reservation.command_id)
    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event,
        now=event.event_at + dt.timedelta(minutes=1))
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    assert (result.alert.status, result.paper.status, result.paper.refusal) == (
        BranchStatus.APPLIED, BranchStatus.REFUSED, "STRATEGY_ADMISSION_INVALID")
    assert broker.s.scalar(select(ExecutionIntent)) is None
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)) is None
    assert (broker.capital().cash, reservation.state, reservation.command_id) == before
    broker.close()


def test_phase4_contextless_both_preserves_alert_and_refuses_all_paper_effects(
        monkeypatch):
    from app.core.strategy_admissions import put
    from tests.test_phase4_capability_admission import _phase4_fixture

    def persist_phase4(session):
        registry, _document, _plan, _assessment, wrapper = _phase4_fixture(
            owner_id="owner")
        monkeypatch.setattr("app.ir.library.REGISTRY", registry)
        put(session, wrapper)
        session.commit()
        return {
            "strategy_key": f"ir.{wrapper.graph_identifier}",
            "strategy_version": str(wrapper.graph_version),
            "graph_address": wrapper.graph_address,
            "attribution_state": "VERIFIED_GRAPH",
            "admission_address": wrapper.admission_address,
        }

    broker, _, event, assignment, authority, sink = _runtime(
        persist_phase4, preference=EffectPreference.BOTH)
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    before = (broker.capital().cash, reservation.state, reservation.command_id)
    result = PaperRuntimeService(broker, alert_sink=sink).process(
        assignment, authority, event,
        now=event.event_at + dt.timedelta(minutes=1))
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    assert (result.alert.status, result.paper.status, result.paper.refusal) == (
        BranchStatus.APPLIED, BranchStatus.REFUSED, "PHASE4_CONTEXT_REQUIRED")
    assert broker.s.scalar(select(ExecutionIntent)) is None
    assert broker.s.scalar(select(Position)) is None
    assert broker.s.scalar(select(Trade)) is None
    assert (broker.capital().cash, reservation.state, reservation.command_id) == before
    broker.close()


def test_reviewer_probe_real_authority_address_cannot_authenticate_forged_command_fields(
        admitted_entry_identity):
    broker, _, event, assignment, authority, _ = _runtime(admitted_entry_identity)
    command = plan_paper_command(assignment, authority, event, now=event.event_at)

    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_SOURCE_RELATION_MISMATCH"):
        canonical_runtime_context(
            replace(command, owner_id="other"), assignment, authority, event)
    with pytest.raises(PaperRuntimeRefusal, match="DEPLOYMENT_ID_REQUIRED"):
        replace(command, deployment_id=0)
    with pytest.raises(PaperRuntimeRefusal, match="APPROVED_QUANTITY_REQUIRED"):
        replace(command, approved_quantity=0)

    forged = replace(command, owner_id="other")
    context = json.loads(canonical_runtime_context(
        command, assignment, authority, event))
    context["owner_id"] = forged.owner_id
    context["paper_command_address"] = forged.address
    serialized = canonical_json(context)
    with pytest.raises(PaperRuntimeRefusal, match="RUNTIME_SOURCE_RELATION_MISMATCH"):
        validate_runtime_context_json(
            serialized, client_intent_id=command.client_intent_id,
            assignment=assignment, authority=authority, event=event)
    with pytest.raises(ValueError, match="PAPER_RUNTIME_CONTEXT_INVALID"):
        broker._prepare_paper_entry_intent(
            entry_intent_id=command.client_intent_id, recovery_intent=None,
            instrument_key=authority.instrument_key, tradingsymbol="NIFTY 50",
            exchange=authority.charge_segment, side="BUY", segment="equity_intraday",
            qty=authority.approved_quantity,
            decision_price=float(command.entry_reference),
            now=command.event_at.replace(tzinfo=None),
            strategy_key=authority.strategy_key,
            strategy_version=authority.strategy_version,
            admission_address=authority.admission_address,
            graph_address=authority.graph_address,
            attribution_state=authority.attribution_state,
            runtime_context_json=serialized)
    broker.close()


def _mutate_matrix_relation(field, assignment, authority, event, command):
    broker_values = {}
    if field == "owner_id":
        command = replace(command, owner_id="other")
    elif field == "deployment_id":
        command = replace(command, deployment_id=2)
    elif field == "instrument_key":
        command = replace(command, instrument_key="BANKNIFTY")
    elif field == "runtime_assignment_address":
        command = replace(command, runtime_assignment_address=address("2"))
    elif field == "instrument_authority_address":
        command = replace(command, instrument_authority_address=address("2"))
    elif field == "monitoring_event_address":
        command = replace(command, monitoring_event_address=address("2"))
    elif field == "action":
        command = replace(
            command, action=PaperAction.SELL,
            client_intent_id=deterministic_client_intent_id(
                assignment.address, event.address, PaperAction.SELL))
    elif field == "client_intent_id":
        command = replace(command, client_intent_id="0" * 32)
    elif field == "approved_quantity":
        command = replace(command, approved_quantity=9)
    elif field == "entry_reference":
        command = replace(command, entry_reference="101")
    elif field == "stop_loss":
        command = replace(command, stop_loss="91")
    elif field == "take_profit":
        command = replace(command, take_profit="121")
    elif field == "graph_version_address":
        command = replace(command, graph_version_address=address("2"))
    elif field == "resolved_graph_address":
        command = replace(command, resolved_graph_address=address("2"))
    elif field == "implementation_closure_address":
        command = replace(command, implementation_closure_address=address("2"))
    elif field == "canonical_instrument_address":
        command = replace(command, canonical_instrument_address=address("2"))
    elif field == "admission_address":
        command = replace(command, admission_address=address("2"))
    elif field == "capital_decision_address":
        command = replace(command, capital_decision_address=address("2"))
    elif field == "capital_reservation_address":
        command = replace(command, capital_reservation_address=address("2"))
    elif field == "paper_book_address":
        command = replace(command, paper_book_address=address("2"))
    elif field == "evaluation_event_address":
        command = replace(command, evaluation_event_address=address("2"))
    elif field == "event_at":
        command = replace(command, event_at=command.event_at + dt.timedelta(seconds=1))
    elif field == "valid_until":
        command = replace(command, valid_until=command.valid_until + dt.timedelta(seconds=1))
    elif field == "monitoring_assignment_id":
        authority = replace(authority, monitoring_assignment_id="monitoring.other")
    elif field == "broker_account_id":
        broker_values["broker_account_id"] = "account.other"
    elif field == "strategy_key":
        authority = replace(authority, strategy_key="ir.other")
    elif field == "fence_epoch":
        broker_values["broker_fence_epoch"] = authority.fence_epoch + 1
    elif field == "authority_window":
        authority = replace(authority, valid_from=event.event_at + dt.timedelta(seconds=1))
    elif field == "lifecycle_status_withdrawal":
        assignment = replace(assignment, lifecycle=AssignmentLifecycle.PAUSED)
    else:
        raise AssertionError(f"{field} requires the durable service seam")
    return assignment, authority, event, command, broker_values


def test_all_36_authority_matrix_relations_reject_independent_field_forgery(
        admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(admitted_entry_identity)
    service = PaperRuntimeService(broker, alert_sink=sink)
    command = plan_paper_command(assignment, authority, event, now=event.event_at)
    matrix_fields = (
        "owner_id", "deployment_id", "instrument_key", "runtime_assignment_address",
        "instrument_authority_address", "monitoring_event_address", "action",
        "client_intent_id", "approved_quantity", "entry_reference", "stop_loss",
        "take_profit", "graph_version_address", "resolved_graph_address",
        "implementation_closure_address", "canonical_instrument_address",
        "admission_address", "capital_decision_address", "capital_reservation_address",
        "paper_book_address", "evaluation_event_address", "event_at", "valid_until",
        "monitoring_assignment_id", "broker_account_id", "strategy_key",
        "strategy_version", "attribution_state", "candidate_identity",
        "decision_identity", "reservation_identity", "required_capital",
        "charge_segment", "fence_epoch", "authority_window",
        "lifecycle_status_withdrawal",
    )
    durable_mutations = {
        "strategy_version": {"strategy_version": "999"},
        "attribution_state": {"attribution_state": "NON_GRAPH"},
        "candidate_identity": {"candidate_address": address("2")},
        "decision_identity": {"decision_address": address("2")},
        "reservation_identity": {"reservation_address": address("2")},
        "required_capital": {"required_capital": "999.0"},
        "charge_segment": {"charge_segment": "BSE_INTRADAY"},
    }
    missed = []
    for field in matrix_fields:
        if field in durable_mutations:
            forged_authority = replace(authority, **durable_mutations[field])
            forged_assignment = replace(
                assignment, instrument_authority_address=forged_authority.address)
            result = service.process(
                forged_assignment, forged_authority, event,
                now=event.event_at + dt.timedelta(minutes=1))
            if result.paper.status is not BranchStatus.REFUSED:
                missed.append(field)
            continue
        try:
            a, u, e, c, broker_values = _mutate_matrix_relation(
                field, assignment, authority, event, command)
            validate_runtime_relations(
                a, u, e, c, broker_owner_id=broker.owner_id,
                broker_account_id=broker_values.get(
                    "broker_account_id", broker.broker_account_id),
                broker_deployment_id=broker.deployment_id,
                broker_fence_epoch=broker_values.get(
                    "broker_fence_epoch", authority.fence_epoch))
        except PaperRuntimeRefusal:
            continue
        missed.append(field)
    assert not missed, f"authority relations accepted forged fields: {missed}"
    assert broker.s.scalar(select(ExecutionIntent)) is None
    assert broker.s.scalar(select(Position)) is None
    broker.close()


def test_durable_authority_and_bounded_capacity_are_not_caller_assertions(
        admitted_entry_identity):
    broker, _, event, assignment, authority, sink = _runtime(admitted_entry_identity)
    assert (MAX_EVENTS_PER_INVOCATION, MAX_INTERNAL_QUEUE_DEPTH,
            MAX_POSITIONS_PER_INSTRUMENT) == (1, 0, 1)
    service = PaperRuntimeService(broker, alert_sink=sink)
    forged = replace(authority, candidate_address=address("0"))
    forged_assignment = replace(assignment, instrument_authority_address=forged.address)
    forged_command = plan_paper_command(
        forged_assignment, forged, event,
        now=event.event_at + dt.timedelta(minutes=1))
    with pytest.raises(PaperRuntimeRefusal, match="DURABLE_CANDIDATE_MISMATCH"):
        service._validate_durable_authority(
            forged, forged_command, forged_assignment, event)
    first = service.process(
        assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    for _ in range(32):
        duplicate = service.process(
            assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
        assert duplicate.paper.status is BranchStatus.ALREADY_APPLIED
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    assert (reservation.state, reservation.consumed_quantity,
            reservation.consumed_minor) == (
        "consumed", authority.approved_quantity, reservation.estimated_minor)
    assert len(broker.s.scalars(select(Position)).all()) == MAX_POSITIONS_PER_INSTRUMENT
    assert first.command.capital_reservation_address == reservation.reservation_address
    refused = service.process(
        forged_assignment, forged, event, now=event.event_at + dt.timedelta(minutes=1))
    assert (refused.paper.status, refused.paper.refusal) == (
        BranchStatus.REFUSED, "DURABLE_CANDIDATE_MISMATCH")
    broker.close()
