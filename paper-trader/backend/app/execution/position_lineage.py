"""Additive paper campaign/tranche/fill lineage; ``Position`` remains authority."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.concurrency import begin_after_clean_reads, caller_owned_savepoint, locked_rows
from app.db.models import (
    CandidateIntentRecord,
    CapitalReservationRecord,
    ExecutionIntent,
    ExecutionOrderEvent,
    FillAllocationRecord,
    PortfolioAdmissionDecisionRecord,
    Position,
    PositionCampaignRecord,
    PositionTrancheRecord,
    TargetPositionRequestRecord,
)
from app.execution.leases import LeaseRepository, LeaseToken, _append_execution_change
from app.ir.hashing import content_address


_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")


class LineageRefused(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _id(kind: str, address: str) -> str:
    return hashlib.sha256(f"{kind}\0{address}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CampaignSpec:
    owner_id: str
    broker_account_id: str
    book: str
    deployment_id: int
    strategy_key: str | None
    strategy_version: str | None
    admission_address: str | None
    graph_address: str | None
    attribution_state: str
    canonical_instrument_key: str
    execution_instrument_key: str
    product_address: str
    direction: str
    target_policy_address: str
    opened_at: dt.datetime
    position_id: int | None = None

    @property
    def address(self) -> str:
        return content_address({
            "schema": "strategy-os.position-campaign/v1",
            "owner_id": self.owner_id,
            "broker_account_id": self.broker_account_id,
            "book": self.book,
            "deployment_id": self.deployment_id,
            "strategy_key": self.strategy_key,
            "strategy_version": self.strategy_version,
            "admission_address": self.admission_address,
            "graph_address": self.graph_address,
            "attribution_state": self.attribution_state,
            "canonical_instrument_key": self.canonical_instrument_key,
            "execution_instrument_key": self.execution_instrument_key,
            "product_address": self.product_address,
            "direction": self.direction,
            "target_policy_address": self.target_policy_address,
            "opened_at": self.opened_at.isoformat(timespec="microseconds"),
            "position_id": self.position_id,
        })

    @property
    def campaign_id(self) -> str:
        return _id("campaign", self.address)


@dataclass(frozen=True)
class TrancheSpec:
    campaign_id: str
    purpose: str
    requested_quantity: int
    admitted_quantity: int
    created_at: dt.datetime
    target_position_request_id: str | None = None
    candidate_intent_id: str | None = None
    batch_id: str | None = None
    decision_id: str | None = None
    reservation_id: str | None = None
    execution_intent_id: str | None = None

    @property
    def address(self) -> str:
        return content_address({
            "schema": "strategy-os.position-tranche/v1",
            "campaign_id": self.campaign_id,
            "purpose": self.purpose,
            "requested_quantity": self.requested_quantity,
            "admitted_quantity": self.admitted_quantity,
            "created_at": self.created_at.isoformat(timespec="microseconds"),
            "target_position_request_id": self.target_position_request_id,
            "candidate_intent_id": self.candidate_intent_id,
            "batch_id": self.batch_id,
            "decision_id": self.decision_id,
            "reservation_id": self.reservation_id,
            "execution_intent_id": self.execution_intent_id,
        })

    @property
    def tranche_id(self) -> str:
        return _id("tranche", self.address)


@dataclass(frozen=True)
class FillShare:
    tranche_id: str
    quantity: int
    trade_id: int | None = None


@dataclass(frozen=True)
class LegacyLineageReceipt:
    position_id: int
    classification: str
    campaign_ids: tuple[str, ...]


def _validate_campaign(spec: CampaignSpec, token: LeaseToken) -> None:
    if (spec.owner_id, spec.broker_account_id) != (
            token.owner_id, token.broker_account_id):
        raise LineageRefused("CAMPAIGN_SCOPE_MISMATCH")
    if spec.book != "paper":
        raise LineageRefused("PAPER_LINEAGE_ONLY")
    if spec.direction not in {"LONG", "SHORT"} \
            or not spec.canonical_instrument_key or not spec.execution_instrument_key:
        raise LineageRefused("INVALID_CAMPAIGN")
    if not _ADDRESS.fullmatch(spec.product_address) \
            or not _ADDRESS.fullmatch(spec.target_policy_address):
        raise LineageRefused("INVALID_CAMPAIGN_ADDRESS")
    if spec.opened_at.tzinfo is not None:
        raise LineageRefused("INVALID_LINEAGE_TIMESTAMP")
    graph = spec.attribution_state == "VERIFIED_GRAPH"
    if graph != (spec.graph_address is not None) \
            or (graph and (spec.admission_address is None
                           or spec.strategy_key is None
                           or not spec.strategy_key.startswith("ir."))):
        raise LineageRefused("CAMPAIGN_ATTRIBUTION_MISMATCH")


def ensure_paper_campaign(
        session: Session, leases: LeaseRepository, token: LeaseToken,
        spec: CampaignSpec) -> PositionCampaignRecord:
    _validate_campaign(spec, token)
    leases.bind_money_session(session, token)
    scope = f"position-campaign:{token.owner_id}:{token.broker_account_id}"
    begin_after_clean_reads(session, scope=scope)
    with caller_owned_savepoint(session, scope=scope):
        leases.require_current_in_session(session, token, active=False, lock=True)
        existing = session.scalar(select(PositionCampaignRecord).where(or_(
            PositionCampaignRecord.campaign_id == spec.campaign_id,
            PositionCampaignRecord.campaign_address == spec.address,
        )))
        if existing is not None:
            if existing.campaign_id != spec.campaign_id \
                    or existing.campaign_address != spec.address:
                raise LineageRefused("CAMPAIGN_IDENTITY_CONFLICT")
            return existing
        if spec.position_id is not None:
            position = session.get(Position, spec.position_id)
            if position is None or (
                    position.owner_id, position.broker_account_id, position.mode,
                    position.deployment_id, position.instrument_key,
                    position.direction, position.strategy_key,
                    position.strategy_version, position.admission_address,
                    position.graph_address, position.attribution_state) != (
                    spec.owner_id, spec.broker_account_id, spec.book,
                    spec.deployment_id, spec.canonical_instrument_key,
                    spec.direction, spec.strategy_key, spec.strategy_version,
                    spec.admission_address, spec.graph_address,
                    spec.attribution_state):
                raise LineageRefused("POSITION_CAMPAIGN_MISMATCH")
        row = PositionCampaignRecord(
            campaign_id=spec.campaign_id, campaign_address=spec.address,
            owner_id=spec.owner_id, broker_account_id=spec.broker_account_id,
            book=spec.book, deployment_id=spec.deployment_id,
            strategy_key=spec.strategy_key, strategy_version=spec.strategy_version,
            admission_address=spec.admission_address,
            graph_address=spec.graph_address,
            attribution_state=spec.attribution_state,
            canonical_instrument_key=spec.canonical_instrument_key,
            execution_instrument_key=spec.execution_instrument_key,
            product_address=spec.product_address, direction=spec.direction,
            target_policy_address=spec.target_policy_address,
            position_id=spec.position_id, status="open",
            opened_at=spec.opened_at, closed_at=None, revision=0,
        )
        session.add(row)
        _append_execution_change(
            session, owner_id=spec.owner_id,
            broker_account_id=spec.broker_account_id,
            aggregate_type="position_campaign", aggregate_id=spec.campaign_id,
            event_type="execution.position.changed",
            producer_key=f"position-campaign:{spec.campaign_id}:0",
            payload={"projection": "position_lineage", "state": "open", "revision": 0},
        )
        session.flush()
        return row


def _validate_tranche_dependencies(
        session: Session, campaign: PositionCampaignRecord,
        spec: TrancheSpec, token: LeaseToken) -> None:
    if spec.purpose not in {"ENTRY", "ADDITION", "REDUCTION"} \
            or spec.requested_quantity == 0 or spec.admitted_quantity == 0:
        raise LineageRefused("INVALID_TRANCHE")
    if spec.created_at.tzinfo is not None:
        raise LineageRefused("INVALID_LINEAGE_TIMESTAMP")
    if spec.execution_intent_id is None:
        raise LineageRefused("TRANCHE_INTENT_REQUIRED")
    candidate = (session.get(CandidateIntentRecord, spec.candidate_intent_id)
                 if spec.candidate_intent_id else None)
    decision = (session.get(PortfolioAdmissionDecisionRecord, spec.decision_id)
                if spec.decision_id else None)
    reservation = (session.get(CapitalReservationRecord, spec.reservation_id)
                   if spec.reservation_id else None)
    target = (session.get(TargetPositionRequestRecord, spec.target_position_request_id)
              if spec.target_position_request_id else None)
    intent = (session.get(ExecutionIntent, spec.execution_intent_id)
              if spec.execution_intent_id else None)
    if candidate is not None:
        expected_purpose = {
            "ENTRY": "ENTRY", "TARGET_ADJUSTMENT": "ADDITION",
            "RISK_REDUCTION": "REDUCTION",
        }[candidate.purpose]
        if expected_purpose != spec.purpose or (
                candidate.owner_id, candidate.broker_account_id,
                candidate.book, candidate.deployment_id,
                candidate.signal_instrument_key,
                candidate.execution_instrument_key,
                candidate.product_address, candidate.direction) != (
                campaign.owner_id, campaign.broker_account_id,
                campaign.book, campaign.deployment_id,
                campaign.canonical_instrument_key,
                campaign.execution_instrument_key,
                campaign.product_address, campaign.direction):
            raise LineageRefused("CANDIDATE_CAMPAIGN_MISMATCH")
    if decision is not None and (
            decision.candidate_intent_id != spec.candidate_intent_id
            or decision.batch_id != spec.batch_id
            or decision.admitted_quantity != spec.admitted_quantity):
        raise LineageRefused("DECISION_TRANCHE_MISMATCH")
    if reservation is not None and (
            reservation.decision_id != spec.decision_id
            or reservation.candidate_intent_id != spec.candidate_intent_id
            or reservation.batch_id != spec.batch_id):
        raise LineageRefused("RESERVATION_TRANCHE_MISMATCH")
    if target is not None and (
            candidate is None
            or target.request_id != candidate.target_position_request_id):
        raise LineageRefused("TARGET_TRANCHE_MISMATCH")
    if intent is None:
        raise LineageRefused("TRANCHE_INTENT_REQUIRED")
    try:
        intent_context = json.loads(intent.context_json or "{}")
    except (TypeError, ValueError) as exc:
        raise LineageRefused("INTENT_TRANCHE_MISMATCH") from exc
    expected_side = (
        "BUY" if (campaign.direction == "LONG") == (spec.purpose != "REDUCTION")
        else "SELL")
    if (intent.owner_id, intent.broker_account_id, intent.deployment_id,
            intent.instrument_key, intent.tradingsymbol,
            intent.strategy_key, intent.strategy_version,
            intent.admission_address, intent.graph_address,
            intent.attribution_state, intent.side, intent.requested_qty,
            str(intent_context.get("book") or intent_context.get("mode") or "").lower()) != (
            campaign.owner_id, campaign.broker_account_id, campaign.deployment_id,
            campaign.canonical_instrument_key, campaign.execution_instrument_key,
            campaign.strategy_key, campaign.strategy_version,
            campaign.admission_address, campaign.graph_address,
            campaign.attribution_state, expected_side,
            abs(spec.admitted_quantity), campaign.book):
        raise LineageRefused("INTENT_TRANCHE_MISMATCH")
    if intent.fence_epoch is None or intent.fence_epoch > token.fence_epoch:
        raise LineageRefused("INTENT_FENCE_MISMATCH")
    if spec.purpose != "REDUCTION" and any(
            value is None for value in (
                candidate, decision, target, spec.batch_id)):
        raise LineageRefused("TRANCHE_EVIDENCE_MISSING")


def create_paper_tranche(
        session: Session, leases: LeaseRepository, token: LeaseToken,
        spec: TrancheSpec) -> PositionTrancheRecord:
    leases.bind_money_session(session, token)
    scope = f"position-tranche:{token.owner_id}:{token.broker_account_id}"
    begin_after_clean_reads(session, scope=scope)
    with caller_owned_savepoint(session, scope=scope):
        leases.require_current_in_session(session, token, active=False, lock=True)
        existing = session.scalar(select(PositionTrancheRecord).where(or_(
            PositionTrancheRecord.tranche_id == spec.tranche_id,
            PositionTrancheRecord.tranche_address == spec.address,
        )))
        if existing is not None:
            existing_campaign = session.get(
                PositionCampaignRecord, existing.campaign_id)
            if existing.tranche_id != spec.tranche_id \
                    or existing.tranche_address != spec.address:
                raise LineageRefused("TRANCHE_IDENTITY_CONFLICT")
            if existing_campaign is None or (
                    existing_campaign.owner_id,
                    existing_campaign.broker_account_id,
                    existing_campaign.book) != (
                    token.owner_id, token.broker_account_id, "paper"):
                raise LineageRefused("TRANCHE_SCOPE_MISMATCH")
            return existing
        campaign = session.scalar(locked_rows(select(PositionCampaignRecord).where(
            PositionCampaignRecord.campaign_id == spec.campaign_id,
            PositionCampaignRecord.owner_id == token.owner_id,
            PositionCampaignRecord.broker_account_id == token.broker_account_id,
            PositionCampaignRecord.book == "paper",
            PositionCampaignRecord.status == "open",
        ), session))
        if campaign is None:
            raise LineageRefused("OPEN_PAPER_CAMPAIGN_MISSING")
        _validate_tranche_dependencies(session, campaign, spec, token)
        row = PositionTrancheRecord(
            tranche_id=spec.tranche_id, tranche_address=spec.address,
            campaign_id=spec.campaign_id,
            target_position_request_id=spec.target_position_request_id,
            candidate_intent_id=spec.candidate_intent_id,
            batch_id=spec.batch_id, decision_id=spec.decision_id,
            reservation_id=spec.reservation_id,
            execution_intent_id=spec.execution_intent_id,
            purpose=spec.purpose,
            requested_quantity=spec.requested_quantity,
            admitted_quantity=spec.admitted_quantity,
            state="planned", created_at=spec.created_at,
            terminal_at=None, revision=0,
        )
        session.add(row)
        _append_execution_change(
            session, owner_id=token.owner_id,
            broker_account_id=token.broker_account_id,
            aggregate_type="position_tranche", aggregate_id=spec.tranche_id,
            event_type="execution.position.changed",
            producer_key=f"position-tranche:{spec.tranche_id}:0",
            payload={"projection": "position_lineage", "state": "planned", "revision": 0},
        )
        session.flush()
        return row


def allocate_paper_fill(
        session: Session, leases: LeaseRepository, token: LeaseToken, *,
        execution_order_event_id: int, shares: tuple[FillShare, ...],
        allocated_at: dt.datetime) -> tuple[FillAllocationRecord, ...]:
    if not shares or allocated_at.tzinfo is not None:
        raise LineageRefused("INVALID_FILL_ALLOCATION")
    leases.bind_money_session(session, token)
    scope = f"fill-allocation:{token.owner_id}:{token.broker_account_id}"
    begin_after_clean_reads(session, scope=scope)
    with caller_owned_savepoint(session, scope=scope):
        leases.require_current_in_session(session, token, active=False, lock=True)
        event = session.scalar(locked_rows(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.id == execution_order_event_id,
            ExecutionOrderEvent.owner_id == token.owner_id,
            ExecutionOrderEvent.broker_account_id == token.broker_account_id,
        ), session))
        if event is None or event.cumulative_filled_qty <= 0:
            raise LineageRefused("FILL_EVENT_MISSING")
        event_intent = session.get(ExecutionIntent, event.client_intent_id)
        if event_intent is None or event.cumulative_filled_qty > event_intent.requested_qty \
                or event.fence_epoch is None \
                or event_intent.fence_epoch != event.fence_epoch \
                or event.fence_epoch > token.fence_epoch:
            raise LineageRefused("FILL_EVENT_INTENT_MISMATCH")
        events = list(session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == event.client_intent_id).order_by(
                ExecutionOrderEvent.observed_at, ExecutionOrderEvent.id)))
        previous = 0
        found = False
        for row in events:
            if row.id == event.id:
                found = True
                break
            if row.cumulative_filled_qty < previous:
                raise LineageRefused("NON_MONOTONIC_FILL_EVENT")
            previous = row.cumulative_filled_qty
        if not found or event.cumulative_filled_qty < previous:
            raise LineageRefused("NON_MONOTONIC_FILL_EVENT")
        delta = event.cumulative_filled_qty - previous
        if delta <= 0 or sum(share.quantity for share in shares) != delta \
                or any(share.quantity <= 0 for share in shares):
            raise LineageRefused("FILL_DELTA_MISMATCH")
        if len({share.tranche_id for share in shares}) != len(shares):
            raise LineageRefused("DUPLICATE_FILL_SHARE")

        existing_rows = tuple(session.scalars(select(FillAllocationRecord).where(
            FillAllocationRecord.execution_order_event_id == event.id).order_by(
                FillAllocationRecord.tranche_id)))
        if existing_rows:
            existing_by_tranche = {row.tranche_id: row for row in existing_rows}
            if len(existing_rows) != len(shares):
                raise LineageRefused("FILL_ALLOCATION_CONFLICT")
            for share in shares:
                tranche = session.get(PositionTrancheRecord, share.tranche_id)
                if tranche is None:
                    raise LineageRefused("FILL_ALLOCATION_CONFLICT")
                expected_address = content_address({
                    "schema": "strategy-os.fill-allocation/v1",
                    "event_id": event.id,
                    "tranche_address": tranche.tranche_address,
                    "quantity": share.quantity,
                    "trade_id": share.trade_id,
                    "allocated_at": allocated_at.isoformat(timespec="microseconds"),
                })
                stored = existing_by_tranche.get(share.tranche_id)
                if stored is None or stored.allocation_address != expected_address:
                    raise LineageRefused("FILL_ALLOCATION_CONFLICT")
            return existing_rows

        allocations = []
        reservation_totals: dict[str, int] = {}
        for share in sorted(shares, key=lambda item: item.tranche_id):
            tranche = session.scalar(locked_rows(select(PositionTrancheRecord).where(
                PositionTrancheRecord.tranche_id == share.tranche_id,
            ), session))
            if tranche is None or tranche.state in {"filled", "cancelled"}:
                raise LineageRefused("OPEN_TRANCHE_MISSING")
            campaign = session.get(PositionCampaignRecord, tranche.campaign_id)
            if campaign is None or (
                    campaign.owner_id, campaign.broker_account_id, campaign.book) != (
                    token.owner_id, token.broker_account_id, "paper"):
                raise LineageRefused("FILL_CAMPAIGN_SCOPE_MISMATCH")
            if tranche.execution_intent_id is not None \
                    and tranche.execution_intent_id != event.client_intent_id:
                raise LineageRefused("FILL_INTENT_MISMATCH")
            try:
                event_context = json.loads(event_intent.context_json or "{}")
            except (TypeError, ValueError) as exc:
                raise LineageRefused("FILL_INTENT_MISMATCH") from exc
            expected_side = (
                "BUY" if (campaign.direction == "LONG")
                == (tranche.purpose != "REDUCTION") else "SELL")
            if (event_intent.deployment_id, event_intent.instrument_key,
                    event_intent.tradingsymbol, event_intent.strategy_key,
                    event_intent.strategy_version, event_intent.admission_address,
                    event_intent.graph_address, event_intent.attribution_state,
                    event_intent.side, event_intent.requested_qty,
                    str(event_context.get("book") or event_context.get("mode")
                        or "").lower()) != (
                    campaign.deployment_id, campaign.canonical_instrument_key,
                    campaign.execution_instrument_key, campaign.strategy_key,
                    campaign.strategy_version, campaign.admission_address,
                    campaign.graph_address, campaign.attribution_state,
                    expected_side, abs(tranche.admitted_quantity), campaign.book):
                raise LineageRefused("FILL_INTENT_MISMATCH")
            prior_allocated = sum(session.scalars(select(
                FillAllocationRecord.quantity).where(
                    FillAllocationRecord.tranche_id == tranche.tranche_id)))
            if prior_allocated + share.quantity > abs(tranche.admitted_quantity):
                raise LineageRefused("TRANCHE_OVER_ALLOCATION")
            if tranche.reservation_id is not None:
                reservation = session.scalar(locked_rows(select(
                    CapitalReservationRecord).where(
                        CapitalReservationRecord.reservation_id
                        == tranche.reservation_id,
                        CapitalReservationRecord.owner_id == token.owner_id,
                        CapitalReservationRecord.broker_account_id
                        == token.broker_account_id,
                        CapitalReservationRecord.book == "paper",
                    ), session))
                if reservation is None:
                    raise LineageRefused("RESERVATION_FILL_NOT_RECONCILED")
                if tranche.reservation_id not in reservation_totals:
                    reservation_totals[tranche.reservation_id] = int(
                        session.scalar(select(func.coalesce(func.sum(
                            FillAllocationRecord.quantity), 0)).join(
                                PositionTrancheRecord,
                                PositionTrancheRecord.tranche_id
                                == FillAllocationRecord.tranche_id).where(
                                    PositionTrancheRecord.reservation_id
                                    == tranche.reservation_id)) or 0)
                if reservation_totals[tranche.reservation_id] + share.quantity \
                        > reservation.consumed_quantity:
                    raise LineageRefused("RESERVATION_FILL_NOT_RECONCILED")
                reservation_totals[tranche.reservation_id] += share.quantity
            allocation_document = {
                "schema": "strategy-os.fill-allocation/v1",
                "event_id": event.id, "tranche_address": tranche.tranche_address,
                "quantity": share.quantity, "trade_id": share.trade_id,
                "allocated_at": allocated_at.isoformat(timespec="microseconds"),
            }
            address = content_address(allocation_document)
            row = FillAllocationRecord(
                allocation_id=_id("fill-allocation", address),
                allocation_address=address, tranche_id=tranche.tranche_id,
                execution_order_event_id=event.id, trade_id=share.trade_id,
                quantity=share.quantity, allocated_at=allocated_at,
            )
            session.add(row)
            total = prior_allocated + share.quantity
            tranche.state = ("filled" if total == abs(tranche.admitted_quantity)
                             else "partially_filled")
            tranche.terminal_at = allocated_at if tranche.state == "filled" else None
            tranche.revision += 1
            allocations.append(row)
        _append_execution_change(
            session, owner_id=token.owner_id,
            broker_account_id=token.broker_account_id,
            aggregate_type="fill_allocation", aggregate_id=str(event.id),
            event_type="execution.position.changed",
            producer_key=f"fill-allocation:event:{event.id}",
            payload={
                "projection": "position_lineage", "state": "allocated",
                "quantity": delta, "share_count": len(shares),
            },
        )
        session.flush()
        return tuple(allocations)


def reconstruct_campaign_quantity(session: Session, campaign_id: str) -> int:
    campaign = session.get(PositionCampaignRecord, campaign_id)
    if campaign is None:
        raise LineageRefused("CAMPAIGN_MISSING")
    rows = list(session.execute(select(
        PositionTrancheRecord.purpose, FillAllocationRecord.quantity).join(
            FillAllocationRecord,
            FillAllocationRecord.tranche_id == PositionTrancheRecord.tranche_id).where(
                PositionTrancheRecord.campaign_id == campaign_id).order_by(
                    FillAllocationRecord.allocated_at,
                    FillAllocationRecord.execution_order_event_id,
                    FillAllocationRecord.allocation_id)))
    quantity = 0
    for purpose, allocated in rows:
        quantity += allocated if purpose in {"ENTRY", "ADDITION"} else -allocated
        if quantity < 0:
            raise LineageRefused("REDUCTION_EXCEEDS_HELD_LINEAGE")
    return quantity


def close_paper_campaign_if_flat(
        session: Session, leases: LeaseRepository, token: LeaseToken, *,
        campaign_id: str, closed_at: dt.datetime) -> PositionCampaignRecord:
    if closed_at.tzinfo is not None:
        raise LineageRefused("INVALID_LINEAGE_TIMESTAMP")
    leases.bind_money_session(session, token)
    scope = f"position-campaign-close:{token.owner_id}:{token.broker_account_id}"
    begin_after_clean_reads(session, scope=scope)
    with caller_owned_savepoint(session, scope=scope):
        leases.require_current_in_session(session, token, active=False, lock=True)
        campaign = session.scalar(locked_rows(select(PositionCampaignRecord).where(
            PositionCampaignRecord.campaign_id == campaign_id,
            PositionCampaignRecord.owner_id == token.owner_id,
            PositionCampaignRecord.broker_account_id == token.broker_account_id,
            PositionCampaignRecord.book == "paper",
        ), session))
        if campaign is None:
            raise LineageRefused("PAPER_CAMPAIGN_MISSING")
        if campaign.status == "closed":
            if campaign.closed_at != closed_at:
                raise LineageRefused("CAMPAIGN_CLOSE_CONFLICT")
            return campaign
        allocations = session.scalar(select(FillAllocationRecord).join(
            PositionTrancheRecord,
            PositionTrancheRecord.tranche_id == FillAllocationRecord.tranche_id).where(
                PositionTrancheRecord.campaign_id == campaign_id).limit(1))
        if allocations is None or reconstruct_campaign_quantity(session, campaign_id) != 0:
            raise LineageRefused("CAMPAIGN_NOT_FLAT")
        if campaign.position_id is not None:
            position = session.get(Position, campaign.position_id)
            if position is not None and position.qty != 0:
                raise LineageRefused("POSITION_NOT_FLAT")
        campaign.status = "closed"
        campaign.closed_at = closed_at
        campaign.revision += 1
        _append_execution_change(
            session, owner_id=token.owner_id,
            broker_account_id=token.broker_account_id,
            aggregate_type="position_campaign", aggregate_id=campaign.campaign_id,
            event_type="execution.position.changed",
            producer_key=f"position-campaign:{campaign.campaign_id}:{campaign.revision}",
            payload={
                "projection": "position_lineage", "state": "closed",
                "revision": campaign.revision,
            },
        )
        session.flush()
        return campaign


def legacy_position_lineage(
        session: Session, position_id: int) -> LegacyLineageReceipt:
    position = session.get(Position, position_id)
    if position is None:
        raise LineageRefused("POSITION_MISSING")
    campaigns = tuple(session.scalars(select(
        PositionCampaignRecord.campaign_id).where(
            PositionCampaignRecord.position_id == position_id).order_by(
                PositionCampaignRecord.campaign_id)))
    return LegacyLineageReceipt(
        position_id, "attributed" if campaigns else "legacy_unattributed", campaigns)


def verify_position_quantity(session: Session, campaign_id: str) -> bool:
    campaign = session.get(PositionCampaignRecord, campaign_id)
    if campaign is None or campaign.position_id is None:
        raise LineageRefused("POSITION_LINK_MISSING")
    position = session.get(Position, campaign.position_id)
    if position is None:
        raise LineageRefused("POSITION_MISSING")
    return position.qty == reconstruct_campaign_quantity(session, campaign_id)


__all__ = [
    "CampaignSpec", "FillShare", "LegacyLineageReceipt", "LineageRefused",
    "TrancheSpec", "allocate_paper_fill", "close_paper_campaign_if_flat",
    "create_paper_tranche", "ensure_paper_campaign", "legacy_position_lineage",
    "reconstruct_campaign_quantity", "verify_position_quantity",
]
