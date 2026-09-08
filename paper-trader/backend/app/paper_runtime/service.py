"""Local, additive MonitoringSignalEvent -> alert/paper effect orchestration."""
from __future__ import annotations

import hashlib
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.backtest.repository import AdmissionRequired, load_verified_admission
from app.core.instruments import get_instrument
from app.db.models import (
    CandidateIntentRecord,
    BrokerAccount,
    CapitalReservationHead,
    CapitalReservationRecord,
    CapitalState,
    DecisionBatchRecord,
    Deployment,
    ExecutionIntent,
    ExecutionOrderEvent,
    PortfolioAdmissionDecisionRecord,
    Position,
    Trade,
)
from app.db.session import SessionLocal
from app.engine.broker import PaperBroker
from app.execution.capital_recovery import RecoveryEvidence, RecoveryRefused, recover_reservation
from app.execution.leases import (
    LeaseRepository,
    LeaseToken,
    LeaseUnavailable,
    RecoveryRequired,
    StaleLease,
)
from app.ir.hashing import canonical_json
from app.monitoring.contracts import MonitoringSignalEvent
from app.providers.mock import MockProvider
from app.providers.replay import ReplayProvider

from .contracts import (
    BranchResult,
    BranchStatus,
    EffectPreference,
    PaperAction,
    PaperCommand,
    PaperInstrumentAuthority,
    PaperRuntimeRefusal,
    RuntimeAssignment,
    RuntimeResult,
    canonical_runtime_context,
    paper_book_scope_address,
    plan_paper_command,
    validate_runtime_relations,
)


AlertSink = Callable[[MonitoringSignalEvent, str], bool]
DeathHook = Callable[[str], None]
MAX_EVENTS_PER_INVOCATION = 1
MAX_INTERNAL_QUEUE_DEPTH = 0
MAX_POSITIONS_PER_INSTRUMENT = 1


def _effect_id(domain: str, assignment_address: str, event_address: str) -> str:
    raw = canonical_json({"domain": domain, "assignment_address": assignment_address,
                          "event_address": event_address}).encode("utf-8")
    return hashlib.blake2b(raw, digest_size=16).hexdigest()


def _exact_runtime_effect(session, authority: PaperInstrumentAuthority,
                          command: PaperCommand) -> Position | Trade | None:
    """Find only the money effect that can justify a converged reservation."""
    if command.action in {PaperAction.BUY, PaperAction.SELL}:
        position = session.scalar(select(Position).where(
            Position.entry_intent_id == command.client_intent_id))
        trade = session.scalar(select(Trade).where(
            Trade.entry_intent_id == command.client_intent_id).limit(1))
        effect = position or trade
        if effect is None:
            return None
        effects = (effect,)
    else:
        positions = list(session.scalars(select(Position).where(
            Position.owner_id == authority.owner_id,
            Position.broker_account_id == authority.broker_account_id,
            Position.deployment_id == authority.deployment_id,
            Position.instrument_key == authority.instrument_key)))
        trades = list(session.scalars(select(Trade).where(
            Trade.owner_id == authority.owner_id,
            Trade.broker_account_id == authority.broker_account_id,
            Trade.deployment_id == authority.deployment_id,
            Trade.instrument_key == authority.instrument_key)))
        runtime_exit_reason = f"PAPER_RUNTIME_EXIT:{command.client_intent_id}"
        has_terminal_exit = any(
            trade.exit_reason == runtime_exit_reason for trade in trades)
        if (len(positions) > 1 or not (positions or has_terminal_exit)
                or sum(row.qty for row in (*positions, *trades))
                    != authority.approved_quantity):
            raise PaperRuntimeRefusal("RECONCILIATION_ENTRY_EFFECT_MISMATCH")
        effects = (*positions, *trades)
        effect = positions[0] if positions else next(
            trade for trade in trades if trade.exit_reason == runtime_exit_reason)
    if not all(
            row.owner_id == authority.owner_id
            and row.broker_account_id == authority.broker_account_id
            and row.deployment_id == authority.deployment_id
            and row.instrument_key == authority.instrument_key
            and row.strategy_key == authority.strategy_key
            and row.strategy_version == authority.strategy_version
            and row.graph_address == authority.graph_address
            and row.admission_address == authority.admission_address
            and row.attribution_state == authority.attribution_state
            and row.mode == "paper"
            for row in effects):
        raise PaperRuntimeRefusal("RECONCILIATION_ENTRY_EFFECT_MISMATCH")
    if command.action in {PaperAction.BUY, PaperAction.SELL} \
            and effect.qty != authority.approved_quantity:
        raise PaperRuntimeRefusal("RECONCILIATION_ENTRY_EFFECT_MISMATCH")
    return effect


def validate_durable_runtime_authority(
        broker: PaperBroker, assignment: RuntimeAssignment,
        authority: PaperInstrumentAuthority, event: MonitoringSignalEvent,
        command: PaperCommand, *, allow_converged_effect: bool = True,
        leases: LeaseRepository | None = None) -> CapitalReservationRecord:
    """Validate source facts and their one current durable paper authority.

    A service retry may reconstruct an already-booked exact paper effect. A broker
    money seam sets ``allow_converged_effect=False`` and therefore requires an
    unexpired, unused held reservation immediately before booking.
    """
    validate_runtime_relations(
        assignment, authority, event, command,
        broker_owner_id=broker.owner_id,
        broker_account_id=broker.broker_account_id,
        broker_deployment_id=broker.deployment_id,
        broker_fence_epoch=getattr(broker.execution_lease_token, "fence_epoch", None))
    if (broker.owner_id != authority.owner_id
            or broker.broker_account_id != authority.broker_account_id
            or broker.deployment_id != authority.deployment_id):
        raise PaperRuntimeRefusal("PAPER_BOOK_SCOPE_MISMATCH")
    token = broker.execution_lease_token
    if type(token) is not LeaseToken or (
            token.owner_id, token.broker_account_id, token.fence_epoch) != (
            authority.owner_id, authority.broker_account_id, authority.fence_epoch):
        raise PaperRuntimeRefusal("AUTHENTIC_EXECUTION_LEASE_REQUIRED")
    lease_repository = leases or LeaseRepository(SessionLocal)
    try:
        lease_repository.require_current_in_session(
            broker.s, token, active=True, lock=False)
    except (LeaseUnavailable, RecoveryRequired, StaleLease) as exc:
        broker.s.rollback()
        raise PaperRuntimeRefusal("STALE_EXECUTION_FENCE") from exc
    if authority.paper_book_address != paper_book_scope_address(
            authority.owner_id, authority.broker_account_id):
        raise PaperRuntimeRefusal("PAPER_BOOK_ADDRESS_MISMATCH")
    capital = broker.s.get(CapitalState, (authority.broker_account_id, "paper"))
    deployment = broker.s.scalar(select(Deployment).where(
        Deployment.id == authority.deployment_id,
        Deployment.owner_id == authority.owner_id,
        Deployment.broker_account_id == authority.broker_account_id))
    if capital is None or broker.book != "paper" or deployment is None:
        raise PaperRuntimeRefusal("EXACT_PAPER_BOOK_REQUIRED")

    candidate = broker.s.get(CandidateIntentRecord, authority.candidate_intent_id)
    decision = broker.s.get(PortfolioAdmissionDecisionRecord, authority.decision_id)
    reservation = broker.s.get(CapitalReservationRecord, authority.reservation_id)
    if candidate is None or candidate.candidate_address != authority.candidate_address:
        raise PaperRuntimeRefusal("DURABLE_CANDIDATE_MISMATCH")
    if decision is None or decision.decision_address != authority.decision_address:
        raise PaperRuntimeRefusal("DURABLE_CAPITAL_DECISION_MISMATCH")
    if reservation is None or reservation.reservation_address != authority.reservation_address:
        raise PaperRuntimeRefusal("DURABLE_CAPITAL_RESERVATION_MISMATCH")
    batch = broker.s.get(DecisionBatchRecord, reservation.batch_id)
    head = broker.s.get(CapitalReservationHead, (
        authority.owner_id, authority.broker_account_id, "paper", "INR"))
    instrument = get_instrument(authority.instrument_key)
    expected_execution_key = instrument.spot_symbol or authority.instrument_key
    expected_charge_segment = instrument.spot_exchange + "_INTRADAY"
    required_minor = Decimal(authority.required_capital) * 100
    exact_scope = (
        candidate.owner_id == reservation.owner_id == authority.owner_id
        and candidate.broker_account_id == reservation.broker_account_id
            == authority.broker_account_id
        and candidate.book == reservation.book == "paper"
        and candidate.currency == reservation.currency == "INR"
        and candidate.fence_epoch == reservation.fence_epoch
        and reservation.fence_epoch <= authority.fence_epoch
        and candidate.deployment_id == authority.deployment_id
        and candidate.strategy_key == authority.strategy_key
        and candidate.strategy_version == authority.strategy_version
        and candidate.admission_address == authority.admission_address
        and candidate.graph_address == authority.graph_address
        and candidate.attribution_state == authority.attribution_state
        and candidate.signal_instrument_key == authority.instrument_key
        and candidate.execution_instrument_key == expected_execution_key
        and authority.charge_segment == expected_charge_segment
        and decision.candidate_intent_id == candidate.candidate_intent_id
        and decision.batch_id == reservation.batch_id
        and decision.decision_id == reservation.decision_id
        and decision.reservation_id == reservation.reservation_id
        and decision.status in {"admitted", "resized"}
        and abs(decision.admitted_quantity) == authority.approved_quantity
        and abs(reservation.admitted_quantity) == authority.approved_quantity
        and reservation.candidate_intent_id == candidate.candidate_intent_id
        and required_minor == required_minor.to_integral_value()
        and int(required_minor) == candidate.required_capital_minor
        and int(required_minor) == decision.required_capital_minor
        and int(required_minor) == reservation.estimated_minor
        and reservation.estimated_minor == decision.held_capital_minor
        and batch is not None
        and batch.owner_id == authority.owner_id
        and batch.broker_account_id == authority.broker_account_id
        and batch.book == "paper" and batch.currency == "INR"
        and batch.fence_epoch == reservation.fence_epoch
        and head is not None)
    if not exact_scope:
        raise PaperRuntimeRefusal("DURABLE_CAPITAL_AUTHORITY_MISMATCH")

    observed_at = LeaseRepository.database_time(broker.s)
    observed_utc = observed_at.replace(tzinfo=dt.timezone.utc)
    if (not assignment.effective_from <= observed_utc <= assignment.valid_until
            or not authority.valid_from <= observed_utc <= authority.valid_until
            or observed_utc > event.valid_until):
        raise PaperRuntimeRefusal("RUNTIME_AUTHORITY_EXPIRED")
    event_time = command.event_at.replace(tzinfo=None)
    if candidate.created_at > event_time or candidate.freshness_deadline < event_time:
        raise PaperRuntimeRefusal("DURABLE_CANDIDATE_TIME_MISMATCH")
    if command.action in {PaperAction.BUY, PaperAction.SELL}:
        expected_direction = "LONG" if command.action is PaperAction.BUY else "SHORT"
        expected_signed_qty = (authority.approved_quantity
                               if expected_direction == "LONG"
                               else -authority.approved_quantity)
        if (candidate.purpose != "ENTRY" or candidate.direction != expected_direction
                or candidate.requested_quantity != expected_signed_qty
                or reservation.fence_epoch != authority.fence_epoch):
            raise PaperRuntimeRefusal("DURABLE_CANDIDATE_ACTION_MISMATCH")

    held_and_usable = (reservation.state == "held"
                       and reservation.command_id is None
                       and reservation.expires_at > observed_at)
    if held_and_usable:
        return reservation
    converged = reservation.state in {"consumed", "partially_consumed"} \
        and _exact_runtime_effect(broker.s, authority, command) is not None
    if allow_converged_effect and converged:
        return reservation
    raise PaperRuntimeRefusal("CAPITAL_RESERVATION_NOT_AVAILABLE")


class PaperRuntimeService:
    """One exact paper book plus an independently idempotent alert branch.

    The alert sink owns its durable alert uniqueness.  A ``True`` return means it
    inserted the effect and ``False`` means that exact effect already existed.
    """

    def __init__(self, broker: PaperBroker, *, alert_sink: AlertSink,
                 death_hook: DeathHook | None = None) -> None:
        if type(broker) is not PaperBroker or broker.book != "paper" or broker.MODE != "paper":
            raise PaperRuntimeRefusal("EXACT_PAPER_BROKER_REQUIRED")
        if type(broker.provider) not in {MockProvider, ReplayProvider}:
            raise PaperRuntimeRefusal("MOCK_OR_REPLAY_PROVIDER_REQUIRED")
        if not callable(alert_sink):
            raise PaperRuntimeRefusal("ALERT_SINK_REQUIRED")
        self.broker = broker
        self.alert_sink = alert_sink
        self.death_hook = death_hook
        self.leases = LeaseRepository(SessionLocal)

    def process(self, assignment: RuntimeAssignment, authority: PaperInstrumentAuthority,
                event: MonitoringSignalEvent, *, now) -> RuntimeResult:
        command = plan_paper_command(assignment, authority, event, now=now)

        alert = BranchResult("ALERT", BranchStatus.NOT_SELECTED, None, None)
        paper = BranchResult("PAPER", BranchStatus.NOT_SELECTED, None, None)
        if assignment.preference in {EffectPreference.ALERTS, EffectPreference.BOTH}:
            alert = self._alert_branch(assignment, event, command)
        if assignment.preference in {EffectPreference.PAPER, EffectPreference.BOTH}:
            paper = self._paper_branch(assignment, authority, event, command)
        return RuntimeResult(command=command, preference=assignment.preference,
                             alert=alert, paper=paper)

    def _validate_durable_authority(
            self, authority: PaperInstrumentAuthority, command: PaperCommand,
            assignment: RuntimeAssignment | None = None,
            event: MonitoringSignalEvent | None = None,
    ) -> CapitalReservationRecord:
        if assignment is None or event is None:
            raise PaperRuntimeRefusal("RUNTIME_SOURCE_FACTS_REQUIRED")
        return validate_durable_runtime_authority(
            self.broker, assignment, authority, event, command,
            allow_converged_effect=True, leases=self.leases)

    def _validate_strategy_admission(
            self, assignment: RuntimeAssignment, authority: PaperInstrumentAuthority,
            event: MonitoringSignalEvent, command: PaperCommand) -> None:
        """Reload one current executable receipt before every paper effect or retry."""
        validate_runtime_relations(
            assignment, authority, event, command,
            broker_owner_id=self.broker.owner_id,
            broker_account_id=self.broker.broker_account_id,
            broker_deployment_id=self.broker.deployment_id,
            broker_fence_epoch=getattr(self.broker.execution_lease_token, "fence_epoch", None))
        try:
            admitted = load_verified_admission(
                self.broker.s, owner_id=authority.owner_id,
                admission_address=authority.admission_address)
        except AdmissionRequired as exc:
            self.broker.s.rollback()
            code = (exc.args[0] if exc.args == ("PHASE4_CONTEXT_REQUIRED",)
                    else "STRATEGY_ADMISSION_INVALID")
            raise PaperRuntimeRefusal(code) from exc
        if (admitted.admission_address != authority.admission_address
                or admitted.strategy_key != authority.strategy_key
                or admitted.strategy_version != authority.strategy_version
                or admitted.graph_address != authority.graph_address
                or admitted.attribution_state != authority.attribution_state
                or admitted.phase4_binding is not None):
            raise PaperRuntimeRefusal("STRATEGY_ADMISSION_IDENTITY_MISMATCH")

    def _alert_branch(self, assignment: RuntimeAssignment, event: MonitoringSignalEvent,
                      command: PaperCommand) -> BranchResult:
        if command.action is PaperAction.HOLD:
            return BranchResult("ALERT", BranchStatus.NO_EFFECT, None, None)
        effect_id = _effect_id("strategy-os-paper-runtime-alert/1", assignment.address, event.address)
        try:
            applied = self.alert_sink(event, effect_id)
        except Exception as exc:  # the independent paper branch must still run
            return BranchResult("ALERT", BranchStatus.REFUSED, effect_id,
                                f"ALERT_BRANCH_FAILED:{type(exc).__name__.upper()}")
        return BranchResult("ALERT", BranchStatus.APPLIED if applied else BranchStatus.ALREADY_APPLIED,
                            effect_id, None)

    def _paper_branch(self, assignment: RuntimeAssignment, authority: PaperInstrumentAuthority,
                      event: MonitoringSignalEvent, command: PaperCommand) -> BranchResult:
        if command.action is PaperAction.HOLD:
            return BranchResult("PAPER", BranchStatus.NO_EFFECT, None, None)
        try:
            self._validate_strategy_admission(
                assignment, authority, event, command)
            reservation = self._validate_durable_authority(
                authority, command, assignment, event)
            if command.action in {PaperAction.BUY, PaperAction.SELL}:
                return self._entry(assignment, authority, event, command, reservation)
            return self._exit(authority, command)
        except PaperRuntimeRefusal as exc:
            status = (BranchStatus.RECONCILIATION_REQUIRED
                      if exc.code.startswith("RECONCILIATION_") else BranchStatus.REFUSED)
            return BranchResult("PAPER", status, command.client_intent_id, exc.code)

    def _deployment(self, authority: PaperInstrumentAuthority) -> Deployment:
        row = self.broker.s.scalar(select(Deployment).where(
            Deployment.id == authority.deployment_id,
            Deployment.owner_id == authority.owner_id,
            Deployment.broker_account_id == authority.broker_account_id))
        if row is None:
            raise PaperRuntimeRefusal("DEPLOYMENT_NOT_FOUND")
        return row

    def _exact_entry_effect(self, authority: PaperInstrumentAuthority,
                            command: PaperCommand) -> Position | Trade | None:
        position = self.broker.s.scalar(select(Position).where(
            Position.entry_intent_id == command.client_intent_id))
        trade = self.broker.s.scalar(select(Trade).where(
            Trade.entry_intent_id == command.client_intent_id).limit(1))
        effect = position or trade
        if effect is None:
            return None
        exact = (effect.owner_id == authority.owner_id
                 and effect.broker_account_id == authority.broker_account_id
                 and effect.deployment_id == authority.deployment_id
                 and effect.instrument_key == authority.instrument_key
                 and effect.strategy_key == authority.strategy_key
                 and effect.strategy_version == authority.strategy_version
                 and effect.graph_address == authority.graph_address
                 and effect.admission_address == authority.admission_address
                 and effect.attribution_state == authority.attribution_state
                 and effect.mode == "paper")
        if not exact:
            raise PaperRuntimeRefusal("RECONCILIATION_ENTRY_EFFECT_MISMATCH")
        return effect

    def _expected_intent(self, authority: PaperInstrumentAuthority,
                         command: PaperCommand, context_json: str) -> dict:
        inst = get_instrument(authority.instrument_key)
        direction = "LONG" if command.action is PaperAction.BUY else "SHORT"
        side = "BUY" if direction == "LONG" else "SELL"
        return {
            "deployment_id": authority.deployment_id, "owner_id": authority.owner_id,
            "broker_account_id": authority.broker_account_id, "broker": self.broker.account.broker,
            "account_scope": self.broker.account.external_account_id, "connection_scope": "paper",
            "intent": "ENTRY", "instrument_key": authority.instrument_key,
            "tradingsymbol": inst.spot_symbol or inst.key, "exchange": authority.charge_segment,
            "side": side, "product": "MIS", "order_type": "MARKET",
            "requested_qty": authority.approved_quantity, "limit_price": None,
            "decision_price": float(command.entry_reference),
            "signal_at": command.event_at.replace(tzinfo=None),
            "strategy_key": authority.strategy_key, "strategy_version": authority.strategy_version,
            "admission_address": authority.admission_address, "graph_address": authority.graph_address,
            "attribution_state": authority.attribution_state, "context_json": context_json,
            "fence_epoch": authority.fence_epoch,
        }

    def _ensure_intent(self, expected: dict, command: PaperCommand) -> tuple[ExecutionIntent, bool]:
        session = self.broker.s
        row = session.get(ExecutionIntent, command.client_intent_id)
        if row is not None:
            if not all(getattr(row, key) == value for key, value in expected.items()):
                raise PaperRuntimeRefusal("RECONCILIATION_INTENT_MISMATCH")
            return row, False
        row = ExecutionIntent(
            client_intent_id=command.client_intent_id,
            broker_tag=f"prt-{command.client_intent_id[:16]}",
            created_at=command.event_at.replace(tzinfo=None), **expected)
        session.add(row)
        try:
            session.commit()
            return row, True
        except IntegrityError:
            session.rollback()
            row = session.get(ExecutionIntent, command.client_intent_id)
            if row is None or not all(getattr(row, key) == value for key, value in expected.items()):
                raise PaperRuntimeRefusal("RECONCILIATION_INTENT_COLLISION")
            return row, False

    def _entry(self, assignment: RuntimeAssignment,
               authority: PaperInstrumentAuthority, event: MonitoringSignalEvent,
               command: PaperCommand,
               reservation: CapitalReservationRecord) -> BranchResult:
        deployment = self._deployment(authority)
        if deployment.status != "active" or not deployment.armed or deployment.halted_on is not None:
            raise PaperRuntimeRefusal("ENTRY_DISARMED_OR_KILLED")
        existing = self._exact_entry_effect(authority, command)
        if existing is not None:
            self._consume_reservation(authority, command)
            return BranchResult("PAPER", BranchStatus.ALREADY_APPLIED,
                                command.client_intent_id, None)
        if reservation.state != "held" or reservation.command_id is not None:
            raise PaperRuntimeRefusal("CAPITAL_RESERVATION_NOT_AVAILABLE")

        context_json = canonical_runtime_context(command, assignment, authority, event)
        expected = self._expected_intent(authority, command, context_json)
        intent, created = self._ensure_intent(expected, command)
        if self.broker.s.scalar(select(ExecutionOrderEvent.id).where(
                ExecutionOrderEvent.client_intent_id == command.client_intent_id).limit(1)) is not None:
            raise PaperRuntimeRefusal("RECONCILIATION_UNKNOWN_PROVIDER_STATE")
        if created and self.death_hook is not None:
            self.death_hook("after_intent")

        price = float(command.entry_reference)
        stop = float(command.stop_loss)
        target = float(command.take_profit)
        if command.action is PaperAction.BUY:
            if not stop < price < target:
                raise PaperRuntimeRefusal("LONG_PROTECTION_GEOMETRY_INVALID")
            direction, sl_pct, tp_pct = "LONG", (price - stop) / price, (target - price) / price
        else:
            if not target < price < stop:
                raise PaperRuntimeRefusal("SHORT_PROTECTION_GEOMETRY_INVALID")
            direction, sl_pct, tp_pct = "SHORT", (stop - price) / price, (price - target) / price
        charges = self.broker._compute_charge(
            authority.charge_segment, "BUY" if direction == "LONG" else "SELL",
            price, authority.approved_quantity)["total"]
        required_total = Decimal(authority.required_capital)
        margin = required_total - Decimal(str(charges))
        if margin <= 0:
            raise PaperRuntimeRefusal("CAPITAL_RESERVATION_CHARGE_MISMATCH")
        if Decimal(str(self.broker.capital().cash)) < required_total:
            raise PaperRuntimeRefusal("CAPITAL_REFUSED")
        try:
            position = self.broker.open_equity_position(
                get_instrument(authority.instrument_key), direction, price,
                authority.approved_quantity, authority.charge_segment,
                f"PAPER_RUNTIME_ENTRY:{command.client_intent_id}",
                command.event_at.replace(tzinfo=None), margin=float(margin),
                sl_pct=sl_pct, tp_pct=tp_pct, entry_intent_id=command.client_intent_id,
                strategy_key=authority.strategy_key, strategy_version=authority.strategy_version,
                admission_address=authority.admission_address, graph_address=authority.graph_address,
                attribution_state=authority.attribution_state, recovery_intent=intent,
                runtime_context_json=context_json)
        except ValueError as exc:
            if str(exc) in {
                    "ADMISSION_REQUIRED", "RECEIPT_STALE", "ARTEFACT_MISMATCH",
                    "GRAPH_ATTRIBUTION_MISMATCH", "V2_RUNTIME_UNAVAILABLE"}:
                raise PaperRuntimeRefusal("STRATEGY_ADMISSION_INVALID") from exc
            if str(exc) in {
                    "PAPER_RUNTIME_CONTEXT_INVALID",
                    "PAPER_RUNTIME_CONTEXT_RELATION_MISMATCH"}:
                raise PaperRuntimeRefusal("RUNTIME_BROKER_RELATION_MISMATCH") from exc
            if str(exc) != "ENTRY_INTENT_ALREADY_USED":
                raise
            self.broker.s.rollback()
            position = self._exact_entry_effect(authority, command)
            if position is None:
                raise PaperRuntimeRefusal("RECONCILIATION_ENTRY_EFFECT_UNKNOWN") from exc
            self._consume_reservation(authority, command)
            return BranchResult("PAPER", BranchStatus.ALREADY_APPLIED,
                                command.client_intent_id, None)
        if (position.stop_price != stop or position.target_price != target
                or position.qty != authority.approved_quantity):
            raise PaperRuntimeRefusal("RECONCILIATION_BOOKED_POSITION_MISMATCH")
        self._consume_reservation(authority, command)
        if self.death_hook is not None:
            self.death_hook("after_paper_commit")
        return BranchResult("PAPER", BranchStatus.APPLIED, command.client_intent_id, None)

    def _consume_reservation(self, authority: PaperInstrumentAuthority,
                             command: PaperCommand) -> None:
        self.broker.s.commit()
        reservation = self.broker.s.get(CapitalReservationRecord, authority.reservation_id)
        if reservation is None:
            raise PaperRuntimeRefusal("RECONCILIATION_CAPITAL_RESERVATION_MISSING")
        if reservation.state == "consumed":
            if (reservation.consumed_quantity != authority.approved_quantity
                    or reservation.consumed_minor != reservation.estimated_minor):
                raise PaperRuntimeRefusal("RECONCILIATION_CAPITAL_CONSUMPTION_MISMATCH")
            return
        if reservation.state != "held" or reservation.command_id is not None:
            raise PaperRuntimeRefusal("RECONCILIATION_CAPITAL_RESERVATION_STATE")
        head = self.broker.s.get(CapitalReservationHead, (
            authority.owner_id, authority.broker_account_id, "paper", "INR"))
        if head is None:
            raise PaperRuntimeRefusal("RECONCILIATION_CAPITAL_HEAD_MISSING")
        occurred_at = LeaseRepository.database_time(self.broker.s)
        self.broker.s.commit()
        evidence = RecoveryEvidence(
            recovery_id=f"paper-fill-{command.client_intent_id}",
            reservation_id=authority.reservation_id, outcome="FILLED",
            expected_head_revision=head.revision,
            cumulative_filled_quantity=authority.approved_quantity,
            consumed_minor=reservation.estimated_minor,
            broker_evidence_address=command.address, occurred_at=occurred_at,
            broker_identity="local-paper-broker")
        try:
            recover_reservation(
                self.broker.s, self.leases, self.broker.execution_lease_token, evidence)
            self.broker.s.commit()
        except RecoveryRefused as exc:
            self.broker.s.rollback()
            current = self.broker.s.get(CapitalReservationRecord, authority.reservation_id)
            if current is not None and current.state == "consumed" \
                    and current.consumed_quantity == authority.approved_quantity \
                    and current.consumed_minor == current.estimated_minor:
                return
            raise PaperRuntimeRefusal("RECONCILIATION_CAPITAL_CONSUMPTION_FAILED") from exc

    def _exit(self, authority: PaperInstrumentAuthority, command: PaperCommand) -> BranchResult:
        self._serialize_exit(authority)
        reason = f"PAPER_RUNTIME_EXIT:{command.client_intent_id}"
        existing_trade = self.broker.s.scalar(select(Trade).where(
            Trade.owner_id == authority.owner_id,
            Trade.broker_account_id == authority.broker_account_id,
            Trade.deployment_id == authority.deployment_id,
            Trade.instrument_key == authority.instrument_key,
            Trade.exit_reason == reason).limit(1))
        if existing_trade is not None:
            if not self._exact_exit_effect(existing_trade, authority, command, reason):
                raise PaperRuntimeRefusal("RECONCILIATION_EXIT_TRADE_MISMATCH")
            return BranchResult("PAPER", BranchStatus.ALREADY_APPLIED,
                                command.client_intent_id, None)
        positions = list(self.broker.s.scalars(select(Position).where(
            Position.owner_id == authority.owner_id,
            Position.broker_account_id == authority.broker_account_id,
            Position.deployment_id == authority.deployment_id,
            Position.instrument_key == authority.instrument_key)))
        if len(positions) != 1:
            raise PaperRuntimeRefusal("RECONCILIATION_EXIT_POSITION_NOT_EXACT")
        pos = positions[0]
        if (pos.mode != "paper" or pos.strategy_key != authority.strategy_key
                or pos.strategy_version != authority.strategy_version
                or pos.graph_address != authority.graph_address
                or pos.admission_address != authority.admission_address
                or pos.attribution_state != authority.attribution_state):
            raise PaperRuntimeRefusal("RECONCILIATION_EXIT_POSITION_MISMATCH")
        price = float(command.entry_reference)
        when = command.event_at.replace(tzinfo=None)
        if pos.segment == "equity_intraday":
            self.broker.close_equity_position(pos, price, reason, when)
        elif pos.segment == "index_futures":
            self.broker.close_futures_position(pos, price, reason, when)
        elif pos.segment == "options":
            self.broker.close_position(pos, price, reason, when, spot=price)
        else:
            raise PaperRuntimeRefusal("UNSUPPORTED_PAPER_POSITION_SEGMENT")
        if self.death_hook is not None:
            self.death_hook("after_paper_commit")
        return BranchResult("PAPER", BranchStatus.APPLIED, command.client_intent_id, None)

    def _serialize_exit(self, authority: PaperInstrumentAuthority) -> None:
        """Serialize exact-position close/retry without introducing a second lock authority."""
        self.broker.s.commit()
        dialect = self.broker.s.get_bind().dialect.name
        if dialect == "sqlite":
            self.broker.s.connection().exec_driver_sql("BEGIN IMMEDIATE")
            account = self.broker.s.scalar(select(BrokerAccount).where(
                BrokerAccount.owner_id == authority.owner_id,
                BrokerAccount.broker_account_id == authority.broker_account_id))
        elif dialect == "postgresql":
            account = self.broker.s.scalar(select(BrokerAccount).where(
                BrokerAccount.owner_id == authority.owner_id,
                BrokerAccount.broker_account_id == authority.broker_account_id).with_for_update())
        else:
            raise PaperRuntimeRefusal("PAPER_EXIT_DATABASE_UNSUPPORTED")
        if account is None:
            self.broker.s.rollback()
            raise PaperRuntimeRefusal("PAPER_BOOK_SCOPE_MISMATCH")

    @staticmethod
    def _exact_exit_effect(trade: Trade, authority: PaperInstrumentAuthority,
                           command: PaperCommand, reason: str) -> bool:
        return (
            trade.owner_id == authority.owner_id
            and trade.broker_account_id == authority.broker_account_id
            and trade.deployment_id == authority.deployment_id
            and trade.instrument_key == authority.instrument_key
            and trade.strategy_key == authority.strategy_key
            and trade.strategy_version == authority.strategy_version
            and trade.graph_address == authority.graph_address
            and trade.admission_address == authority.admission_address
            and trade.attribution_state == authority.attribution_state
            and trade.mode == "paper"
            and trade.exit_reason == reason
            and trade.exit_premium == float(command.entry_reference)
            and trade.exit_time == command.event_at.replace(tzinfo=None)
        )
