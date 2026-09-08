from __future__ import annotations

import dataclasses
import datetime as dt

import pytest
from sqlalchemy import func, select, update

from app.db.models import (
    CapitalReservationHead,
    CapitalReservationRecord,
    DecisionBatchRecord,
    ExecutionIntent,
    ExecutionOrderEvent,
    FillAllocationRecord,
    PortfolioAdmissionDecisionRecord,
    Position,
    PositionCampaignRecord,
)
from app.execution.capital_admission import CapitalAdmissionRefused, admit_closed_batch
from app.execution.capital_recovery import RecoveryEvidence, recover_reservation
from app.execution.position_lineage import (
    CampaignSpec,
    FillShare,
    LineageRefused,
    TrancheSpec,
    allocate_paper_fill,
    close_paper_campaign_if_flat,
    create_paper_tranche,
    ensure_paper_campaign,
    legacy_position_lineage,
    reconstruct_campaign_quantity,
    verify_position_quantity,
)
from app.ir.hashing import content_address
from tests import test_capital_admission as capital_admission_fixtures
from tests.test_capital_admission import (
    ACCOUNT,
    EMPTY_PENDING_DIGEST,
    NOW,
    OWNER,
    PRODUCT,
    _admit,
    _batch,
    _candidate,
    _seed_candidates,
    admission_store,
)
from tests.test_capital_admission_postgresql import (
    _pg_batch,
    _pg_candidate,
    postgres_admission,
)


TARGET_POLICY = content_address({"target-policy": "campaign-v1"})


@pytest.fixture()
def current_lineage_time(admission_store, monkeypatch):
    _engine, sessions, leases, _token = admission_store
    with sessions() as session:
        database_now = leases.database_time(session)
    monkeypatch.setitem(globals(), "NOW", database_now)
    monkeypatch.setattr(capital_admission_fixtures, "NOW", database_now)
    return database_now


def _position(sessions, *, qty=3, key="signal-1"):
    with sessions.begin() as session:
        row = Position(
            owner_id=OWNER, broker_account_id=ACCOUNT, deployment_id=101,
            entry_intent_id=None, instrument_key=key, direction="LONG",
            option_type="CE", tradingsymbol="execution-1", exchange="NFO",
            segment="options", strategy_key=None, strategy_version=None,
            admission_address=None, graph_address=None,
            attribution_state="NON_GRAPH", strike=24_000.0,
            expiry=NOW.date() + dt.timedelta(days=7), lot_size=1, qty=qty,
            entry_premium=100.0, entry_charges=0.0, entry_cost=qty * 100.0,
            entry_spot=24_000.0, entry_time=NOW, entry_reason="fixture",
            stop_price=90.0, target_price=120.0,
            last_premium=100.0, last_spot=24_000.0,
            high_water_premium=100.0, mfe=0.0, mae=0.0, mode="paper",
        )
        session.add(row)
        session.flush()
        return row.id


def _campaign_spec(position_id, *, direction="LONG", strategy_key=None):
    return CampaignSpec(
        owner_id=OWNER, broker_account_id=ACCOUNT, book="paper",
        deployment_id=101, strategy_key=strategy_key,
        strategy_version=None, admission_address=None, graph_address=None,
        attribution_state="NON_GRAPH", canonical_instrument_key="signal-1",
        execution_instrument_key="execution-1", product_address=PRODUCT,
        direction=direction, target_policy_address=TARGET_POLICY,
        opened_at=NOW, position_id=position_id,
    )


def _intent_and_event(
        sessions, token, *, name, side, cumulative, observed_at,
        requested_qty=None, instrument_key="signal-1",
        tradingsymbol="execution-1"):
    with sessions.begin() as session:
        intent = ExecutionIntent(
            client_intent_id=name, deployment_id=101,
            owner_id=OWNER, broker_account_id=ACCOUNT,
            broker="paper", account_scope=ACCOUNT,
            connection_scope="paper", broker_tag=f"tag-{name}",
            intent="ENTRY", instrument_key=instrument_key,
            tradingsymbol=tradingsymbol, exchange="NFO", side=side,
            product="MIS", order_type="MARKET",
            requested_qty=requested_qty or cumulative,
            limit_price=None, decision_price=100.0, signal_at=NOW,
            strategy_key=None, strategy_version=None,
            admission_address=None, graph_address=None,
            attribution_state="NON_GRAPH", context_json='{"book":"paper"}',
            created_at=NOW, fence_epoch=token.fence_epoch,
        )
        session.add(intent)
        session.flush()
        event = ExecutionOrderEvent(
            owner_id=OWNER, broker_account_id=ACCOUNT,
            client_intent_id=name, source="paper",
            source_event_id=f"fill-{name}", kind="FILL",
            broker_order_id=f"order-{name}", broker_status="COMPLETE",
            cumulative_filled_qty=cumulative, avg_price=100.0,
            observed_at=observed_at, payload_json="{}", anomaly="",
            fence_epoch=token.fence_epoch,
        )
        session.add(event)
        session.flush()
        return event.id


def _resolve_intent(sessions, token, *, name, cumulative, observed_at):
    with sessions.begin() as session:
        for kind in ("POSITION_BOOKED", "POSITION_PROTECTED"):
            session.add(ExecutionOrderEvent(
                owner_id=OWNER, broker_account_id=ACCOUNT,
                client_intent_id=name, source="paper",
                source_event_id=f"{kind.lower()}-{name}", kind=kind,
                broker_order_id=f"order-{name}", broker_status="COMPLETE",
                cumulative_filled_qty=cumulative, avg_price=100.0,
                observed_at=observed_at, payload_json="{}", anomaly="",
                fence_epoch=token.fence_epoch))


def _consume(
        sessions, leases, token, reservation_id, *, head, quantity, minor, name,
        when=None):
    if when is None:
        when = NOW
    evidence = RecoveryEvidence(
        recovery_id=name, reservation_id=reservation_id, outcome="FILLED",
        expected_head_revision=head, cumulative_filled_quantity=quantity,
        consumed_minor=minor,
        broker_evidence_address=content_address({"fill": name}),
        occurred_at=when, command_id=None, broker_identity=f"paper-{name}",
    )
    with sessions() as session:
        result = recover_reservation(session, leases, token, evidence)
        session.commit()
        return result


def _decision(sessions, batch_id, candidate_id):
    with sessions() as session:
        return session.scalar(select(PortfolioAdmissionDecisionRecord).where(
            PortfolioAdmissionDecisionRecord.batch_id == batch_id,
            PortfolioAdmissionDecisionRecord.candidate_intent_id == candidate_id))


def _create_tranche(sessions, leases, token, spec):
    with sessions() as session:
        row = create_paper_tranche(session, leases, token, spec)
        session.commit()
        return row


def _allocate(sessions, leases, token, event_id, shares, when):
    with sessions() as session:
        rows = allocate_paper_fill(
            session, leases, token, execution_order_event_id=event_id,
            shares=shares, allocated_at=when)
        session.commit()
        return rows


def test_stale_lineage_decision_time_is_refused_without_admission_effect(
        admission_store, current_lineage_time):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    current_batch = _batch(token, (candidate,))
    stale_batch = dataclasses.replace(
        current_batch,
        decision_at=current_lineage_time - dt.timedelta(
            seconds=current_batch.reservation_ttl_seconds + 1),
    )

    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused) as refused:
            admit_closed_batch(session, leases, token, stale_batch)
        assert refused.value.code == "DECISION_TIME_INVALID"
        session.rollback()

    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(
            DecisionBatchRecord)) == 0
        assert session.scalar(select(func.count()).select_from(
            CapitalReservationRecord)) == 0
        head = session.get(
            CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR"))
        assert head is not None and head.revision == 0


def test_entry_add_reduce_close_reconstructs_position_without_mutating_it(
        admission_store, current_lineage_time):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=3)
    campaign_spec = _campaign_spec(position_id)
    with sessions() as session:
        campaign = ensure_paper_campaign(session, leases, token, campaign_spec)
        session.commit()
        campaign_id = campaign.campaign_id

    entry = _candidate(1, cost=40_000, priority=1)
    _seed_candidates(sessions, (entry,))
    entry_batch = _admit(sessions, leases, token, _batch(token, (entry,)))
    entry_decision = _decision(sessions, entry_batch.decision_batch_id,
                               entry.candidate_intent_id)
    _consume(sessions, leases, token, entry_decision.reservation_id,
             head=1, quantity=2, minor=40_000, name="entry")
    entry_event = _intent_and_event(
        sessions, token, name="entry-intent", side="BUY",
        cumulative=2, observed_at=NOW)
    entry_tranche = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign_id, purpose="ENTRY",
        requested_quantity=2, admitted_quantity=2, created_at=NOW,
        target_position_request_id=entry.target_position_request_id,
        candidate_intent_id=entry.candidate_intent_id,
        batch_id=entry_batch.decision_batch_id,
        decision_id=entry_decision.decision_id,
        reservation_id=entry_decision.reservation_id,
        execution_intent_id="entry-intent",
    ))
    _allocate(sessions, leases, token, entry_event,
              (FillShare(entry_tranche.tranche_id, 2),), NOW)
    _resolve_intent(
        sessions, token, name="entry-intent", cumulative=2,
        observed_at=NOW + dt.timedelta(microseconds=1))

    addition = dataclasses.replace(
        _candidate(2, cost=20_000, priority=2, purpose="TARGET_ADJUSTMENT"),
        requested_quantity=1, held_pending_digest=EMPTY_PENDING_DIGEST,
        signal_instrument_key="signal-1", execution_instrument_key="execution-1")
    _seed_candidates(sessions, (addition,))
    addition_batch = _admit(sessions, leases, token, _batch(
        token, (addition,), batch_id="addition-batch", head_revision=2))
    addition_decision = _decision(
        sessions, addition_batch.decision_batch_id, addition.candidate_intent_id)
    _consume(sessions, leases, token, addition_decision.reservation_id,
             head=3, quantity=1, minor=20_000, name="addition")
    addition_event = _intent_and_event(
        sessions, token, name="addition-intent", side="BUY",
        cumulative=1, observed_at=NOW + dt.timedelta(seconds=1))
    addition_tranche = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign_id, purpose="ADDITION",
        requested_quantity=1, admitted_quantity=1,
        created_at=NOW + dt.timedelta(seconds=1),
        target_position_request_id=addition.target_position_request_id,
        candidate_intent_id=addition.candidate_intent_id,
        batch_id=addition_batch.decision_batch_id,
        decision_id=addition_decision.decision_id,
        reservation_id=addition_decision.reservation_id,
        execution_intent_id="addition-intent",
    ))
    _allocate(sessions, leases, token, addition_event,
              (FillShare(addition_tranche.tranche_id, 1),),
              NOW + dt.timedelta(seconds=1))
    with sessions() as session:
        assert reconstruct_campaign_quantity(session, campaign_id) == 3
        assert verify_position_quantity(session, campaign_id)

    reduction_event = _intent_and_event(
        sessions, token, name="reduction-intent", side="SELL",
        cumulative=3, observed_at=NOW + dt.timedelta(seconds=2))
    reduction_tranche = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign_id, purpose="REDUCTION",
        requested_quantity=-3, admitted_quantity=-3,
        created_at=NOW + dt.timedelta(seconds=2),
        execution_intent_id="reduction-intent",
    ))
    _allocate(sessions, leases, token, reduction_event,
              (FillShare(reduction_tranche.tranche_id, 3),),
              NOW + dt.timedelta(seconds=2))

    with sessions() as session:
        assert reconstruct_campaign_quantity(session, campaign_id) == 0
        position = session.get(Position, position_id)
        assert position.qty == 3, "lineage must not mutate current Position"
    with sessions() as session:
        with pytest.raises(LineageRefused, match="POSITION_NOT_FLAT"):
            close_paper_campaign_if_flat(
                session, leases, token, campaign_id=campaign_id,
                closed_at=NOW + dt.timedelta(seconds=3))
        session.rollback()
    # Simulate the current operational Position owner applying the exit. The
    # lineage service did not and cannot perform this update.
    with sessions.begin() as session:
        session.get(Position, position_id).qty = 0
    with sessions() as session:
        closed = close_paper_campaign_if_flat(
            session, leases, token, campaign_id=campaign_id,
            closed_at=NOW + dt.timedelta(seconds=3))
        session.commit()
        assert closed.status == "closed"
    with sessions() as session:
        replay = close_paper_campaign_if_flat(
            session, leases, token, campaign_id=campaign_id,
            closed_at=NOW + dt.timedelta(seconds=3))
        session.commit()
        assert replay.status == "closed"
    with sessions() as session:
        with pytest.raises(LineageRefused, match="CAMPAIGN_CLOSE_CONFLICT"):
            close_paper_campaign_if_flat(
                session, leases, token, campaign_id=campaign_id,
                closed_at=NOW + dt.timedelta(seconds=4))
        session.rollback()


def test_fill_delta_is_complete_unique_and_cannot_exceed_reconciled_reservation(
        admission_store, current_lineage_time):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=2)
    spec = _campaign_spec(position_id)
    with sessions() as session:
        campaign = ensure_paper_campaign(session, leases, token, spec)
        session.commit()
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _admit(sessions, leases, token, _batch(token, (candidate,)))
    decision = _decision(sessions, batch.decision_batch_id, candidate.candidate_intent_id)
    event_id = _intent_and_event(
        sessions, token, name="fill-intent", side="BUY", cumulative=2,
        observed_at=NOW)
    tranche = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign.campaign_id, purpose="ENTRY",
        requested_quantity=2, admitted_quantity=2, created_at=NOW,
        target_position_request_id=candidate.target_position_request_id,
        candidate_intent_id=candidate.candidate_intent_id,
        batch_id=batch.decision_batch_id, decision_id=decision.decision_id,
        reservation_id=decision.reservation_id, execution_intent_id="fill-intent",
    ))
    with sessions() as session:
        with pytest.raises(LineageRefused, match="FILL_DELTA_MISMATCH"):
            allocate_paper_fill(
                session, leases, token, execution_order_event_id=event_id,
                shares=(FillShare(tranche.tranche_id, 1),), allocated_at=NOW)
        session.rollback()
    with sessions() as session:
        with pytest.raises(LineageRefused, match="RESERVATION_FILL_NOT_RECONCILED"):
            allocate_paper_fill(
                session, leases, token, execution_order_event_id=event_id,
                shares=(FillShare(tranche.tranche_id, 2),), allocated_at=NOW)
        session.rollback()
    _consume(sessions, leases, token, decision.reservation_id,
             head=1, quantity=2, minor=40_000, name="fill")
    rows = _allocate(
        sessions, leases, token, event_id,
        (FillShare(tranche.tranche_id, 2),), NOW)
    assert len(rows) == 1
    replay = _allocate(
        sessions, leases, token, event_id,
        (FillShare(tranche.tranche_id, 2),), NOW)
    assert replay[0].allocation_address == rows[0].allocation_address
    with sessions() as session:
        with pytest.raises(LineageRefused, match="FILL_ALLOCATION_CONFLICT"):
            allocate_paper_fill(
                session, leases, token, execution_order_event_id=event_id,
                shares=(FillShare(tranche.tranche_id, 2),),
                allocated_at=NOW + dt.timedelta(seconds=1))
        session.rollback()
        assert session.scalar(select(func.sum(FillAllocationRecord.quantity))) == 2


def test_partial_fill_allocations_advance_monotonically_to_filled(
        admission_store, current_lineage_time):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=2)
    with sessions() as session:
        campaign = ensure_paper_campaign(
            session, leases, token, _campaign_spec(position_id))
        session.commit()
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _admit(sessions, leases, token, _batch(token, (candidate,)))
    decision = _decision(sessions, batch.decision_batch_id, candidate.candidate_intent_id)
    _consume(sessions, leases, token, decision.reservation_id,
             head=1, quantity=2, minor=40_000, name="partial-lineage")
    first_event = _intent_and_event(
        sessions, token, name="partial-intent", side="BUY", cumulative=1,
        requested_qty=2, observed_at=NOW)
    tranche = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign.campaign_id, purpose="ENTRY",
        requested_quantity=2, admitted_quantity=2, created_at=NOW,
        target_position_request_id=candidate.target_position_request_id,
        candidate_intent_id=candidate.candidate_intent_id,
        batch_id=batch.decision_batch_id, decision_id=decision.decision_id,
        reservation_id=decision.reservation_id,
        execution_intent_id="partial-intent",
    ))
    _allocate(sessions, leases, token, first_event,
              (FillShare(tranche.tranche_id, 1),), NOW)
    with sessions.begin() as session:
        second = ExecutionOrderEvent(
            owner_id=OWNER, broker_account_id=ACCOUNT,
            client_intent_id="partial-intent", source="paper",
            source_event_id="fill-partial-intent-2", kind="FILL",
            broker_order_id="order-partial-intent", broker_status="COMPLETE",
            cumulative_filled_qty=2, avg_price=100.0,
            observed_at=NOW + dt.timedelta(seconds=1), payload_json="{}",
            anomaly="", fence_epoch=token.fence_epoch,
        )
        session.add(second)
        session.flush()
        second_event = second.id
    _allocate(sessions, leases, token, second_event,
              (FillShare(tranche.tranche_id, 1),),
              NOW + dt.timedelta(seconds=1))
    with sessions() as session:
        stored = session.get(type(tranche), tranche.tranche_id)
        assert stored.state == "filled" and stored.revision == 2
        assert session.scalar(select(func.sum(FillAllocationRecord.quantity)).where(
            FillAllocationRecord.tranche_id == tranche.tranche_id)) == 2


def test_tranche_intent_quantity_must_match_admitted_quantity(admission_store):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=2)
    with sessions() as session:
        campaign = ensure_paper_campaign(
            session, leases, token, _campaign_spec(position_id))
        session.commit()
    event_id = _intent_and_event(
        sessions, token, name="over-reduction", side="SELL", cumulative=3,
        observed_at=NOW)
    with sessions() as session:
        with pytest.raises(LineageRefused, match="INTENT_TRANCHE_MISMATCH"):
            create_paper_tranche(session, leases, token, TrancheSpec(
                campaign_id=campaign.campaign_id, purpose="REDUCTION",
                requested_quantity=-2, admitted_quantity=-2, created_at=NOW,
                execution_intent_id="over-reduction"))
        session.rollback()
        assert session.scalar(select(func.count()).select_from(
            FillAllocationRecord)) == 0


def test_every_new_tranche_requires_exact_execution_intent(admission_store):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=1)
    with sessions() as session:
        campaign = ensure_paper_campaign(
            session, leases, token, _campaign_spec(position_id))
        session.commit()
    with sessions() as session:
        with pytest.raises(LineageRefused, match="TRANCHE_INTENT_REQUIRED"):
            create_paper_tranche(session, leases, token, TrancheSpec(
                campaign_id=campaign.campaign_id, purpose="REDUCTION",
                requested_quantity=-1, admitted_quantity=-1,
                created_at=NOW, execution_intent_id=None))
        session.rollback()


def test_fill_event_cannot_cross_intent_or_instrument(admission_store):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=1)
    with sessions() as session:
        campaign = ensure_paper_campaign(
            session, leases, token, _campaign_spec(position_id))
        session.commit()
    causal_event = _intent_and_event(
        sessions, token, name="causal-intent", side="SELL", cumulative=1,
        observed_at=NOW)
    tranche = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign.campaign_id, purpose="REDUCTION",
        requested_quantity=-1, admitted_quantity=-1, created_at=NOW,
        execution_intent_id="causal-intent"))
    foreign_event = _intent_and_event(
        sessions, token, name="foreign-intent", side="SELL", cumulative=1,
        observed_at=NOW + dt.timedelta(seconds=1))
    with sessions() as session:
        with pytest.raises(LineageRefused, match="FILL_INTENT_MISMATCH"):
            allocate_paper_fill(
                session, leases, token,
                execution_order_event_id=foreign_event,
                shares=(FillShare(tranche.tranche_id, 1),),
                allocated_at=NOW + dt.timedelta(seconds=1))
        session.rollback()
    with sessions.begin() as session:
        session.execute(update(ExecutionIntent).where(
            ExecutionIntent.client_intent_id == "causal-intent").values(
                instrument_key="CHANGED"))
    with sessions() as session:
        with pytest.raises(LineageRefused, match="FILL_INTENT_MISMATCH"):
            allocate_paper_fill(
                session, leases, token,
                execution_order_event_id=causal_event,
                shares=(FillShare(tranche.tranche_id, 1),),
                allocated_at=NOW + dt.timedelta(seconds=2))
        session.rollback()


def test_reservation_consumption_is_aggregate_across_all_linked_tranches(
        admission_store, current_lineage_time):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=2)
    with sessions() as session:
        campaign = ensure_paper_campaign(
            session, leases, token, _campaign_spec(position_id))
        session.commit()
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _admit(sessions, leases, token, _batch(token, (candidate,)))
    decision = _decision(sessions, batch.decision_batch_id, candidate.candidate_intent_id)
    _consume(sessions, leases, token, decision.reservation_id,
             head=1, quantity=2, minor=40_000, name="aggregate")
    first_event = _intent_and_event(
        sessions, token, name="aggregate-1", side="BUY", cumulative=2,
        observed_at=NOW)
    first = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign.campaign_id, purpose="ENTRY",
        requested_quantity=2, admitted_quantity=2, created_at=NOW,
        target_position_request_id=candidate.target_position_request_id,
        candidate_intent_id=candidate.candidate_intent_id,
        batch_id=batch.decision_batch_id, decision_id=decision.decision_id,
        reservation_id=decision.reservation_id,
        execution_intent_id="aggregate-1"))
    _allocate(sessions, leases, token, first_event,
              (FillShare(first.tranche_id, 2),), NOW)
    second_event = _intent_and_event(
        sessions, token, name="aggregate-2", side="BUY", cumulative=1,
        requested_qty=2, observed_at=NOW + dt.timedelta(seconds=1))
    second = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign.campaign_id, purpose="ENTRY",
        requested_quantity=2, admitted_quantity=2,
        created_at=NOW + dt.timedelta(seconds=1),
        target_position_request_id=candidate.target_position_request_id,
        candidate_intent_id=candidate.candidate_intent_id,
        batch_id=batch.decision_batch_id, decision_id=decision.decision_id,
        reservation_id=decision.reservation_id,
        execution_intent_id="aggregate-2"))
    with sessions() as session:
        with pytest.raises(LineageRefused, match="RESERVATION_FILL_NOT_RECONCILED"):
            allocate_paper_fill(
                session, leases, token, execution_order_event_id=second_event,
                shares=(FillShare(second.tranche_id, 1),),
                allocated_at=NOW + dt.timedelta(seconds=1))
        session.rollback()
        assert session.scalar(select(func.sum(FillAllocationRecord.quantity))) == 2


def test_opposing_strategy_campaigns_are_distinct_and_legacy_is_not_inferred(
        admission_store):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=1)
    with sessions() as session:
        first = ensure_paper_campaign(
            session, leases, token, _campaign_spec(position_id))
        session.commit()
        first_id = first.campaign_id
    opposing_spec = dataclasses.replace(
        _campaign_spec(None), direction="SHORT",
        strategy_key="opposing.strategy")
    with sessions() as session:
        opposing = ensure_paper_campaign(session, leases, token, opposing_spec)
        session.commit()
        opposing_id = opposing.campaign_id
    legacy_id = _position(sessions, qty=1, key="legacy-key")
    with sessions() as session:
        receipt = legacy_position_lineage(session, legacy_id)
        assert receipt.classification == "legacy_unattributed"
        assert receipt.campaign_ids == ()
        assert first_id != opposing_id
        assert session.scalar(select(func.count()).select_from(
            PositionCampaignRecord).where(
                PositionCampaignRecord.position_id == legacy_id)) == 0


def test_position_quantity_verification_is_read_only(admission_store):
    _engine, sessions, leases, token = admission_store
    position_id = _position(sessions, qty=1)
    spec = _campaign_spec(position_id)
    with sessions() as session:
        campaign = ensure_paper_campaign(session, leases, token, spec)
        session.commit()
    with sessions() as session:
        assert not verify_position_quantity(session, campaign.campaign_id)
        assert session.get(Position, position_id).qty == 1


def test_postgres_reservation_consumption_is_aggregate_across_tranches(
        postgres_admission):
    sessions, leases, token, database_now = postgres_admission
    position_id = _position(sessions, qty=2)
    with sessions() as session:
        campaign = ensure_paper_campaign(
            session, leases, token, _campaign_spec(position_id))
        session.commit()
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    with sessions() as session:
        batch = admit_closed_batch(
            session, leases, token,
            _pg_batch(token, (candidate,), database_now))
        session.commit()
    decision = _decision(sessions, batch.decision_batch_id, candidate.candidate_intent_id)
    _consume(sessions, leases, token, decision.reservation_id,
             head=1, quantity=2, minor=40_000, name="pg-aggregate",
             when=database_now)
    first_event = _intent_and_event(
        sessions, token, name="pg-aggregate-1", side="BUY", cumulative=2,
        observed_at=database_now)
    first = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign.campaign_id, purpose="ENTRY",
        requested_quantity=2, admitted_quantity=2, created_at=database_now,
        target_position_request_id=candidate.target_position_request_id,
        candidate_intent_id=candidate.candidate_intent_id,
        batch_id=batch.decision_batch_id, decision_id=decision.decision_id,
        reservation_id=decision.reservation_id,
        execution_intent_id="pg-aggregate-1"))
    _allocate(sessions, leases, token, first_event,
              (FillShare(first.tranche_id, 2),), database_now)
    second_event = _intent_and_event(
        sessions, token, name="pg-aggregate-2", side="BUY", cumulative=1,
        requested_qty=2, observed_at=database_now + dt.timedelta(seconds=1))
    second = _create_tranche(sessions, leases, token, TrancheSpec(
        campaign_id=campaign.campaign_id, purpose="ENTRY",
        requested_quantity=2, admitted_quantity=2,
        created_at=database_now + dt.timedelta(seconds=1),
        target_position_request_id=candidate.target_position_request_id,
        candidate_intent_id=candidate.candidate_intent_id,
        batch_id=batch.decision_batch_id, decision_id=decision.decision_id,
        reservation_id=decision.reservation_id,
        execution_intent_id="pg-aggregate-2"))
    with sessions() as session:
        with pytest.raises(LineageRefused, match="RESERVATION_FILL_NOT_RECONCILED"):
            allocate_paper_fill(
                session, leases, token, execution_order_event_id=second_event,
                shares=(FillShare(second.tranche_id, 1),),
                allocated_at=database_now + dt.timedelta(seconds=1))
        session.rollback()
        assert session.scalar(select(func.sum(FillAllocationRecord.quantity))) == 2
