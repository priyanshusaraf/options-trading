from __future__ import annotations

import dataclasses
import concurrent.futures
import datetime as dt
import threading

import pytest
from sqlalchemy import func, select

from app.db.models import (
    CapitalReservationEventRecord,
    CapitalReservationHead,
    CapitalReservationRecord,
)
from app.events.planes import execution_outbox
from app.execution.capital_admission import admit_closed_batch
from app.execution.capital_recovery import (
    RecoveryEvidence,
    RecoveryRefused,
    expired_paper_reservations,
    recover_reservation,
)
from app.execution.target_position import (
    PendingQuantityEvidence,
    TargetPositionRequest,
    derive_target_delta,
)
from app.ir.hashing import content_address
from tests.test_capital_admission import (
    ACCOUNT,
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


def _reservation(admission_store, *, index=1, cost=40_000):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(index, cost=cost)
    _seed_candidates(sessions, (candidate,))
    admitted = _admit(sessions, leases, token, _batch(token, (candidate,)))
    return sessions, leases, token, candidate, admitted.decisions[0].reservation_id


def _evidence(reservation_id, *, recovery_id, outcome, head, quantity=0,
              consumed_minor=0, command_id=None, when=NOW, broker="evidence"):
    return RecoveryEvidence(
        recovery_id=recovery_id, reservation_id=reservation_id,
        outcome=outcome, expected_head_revision=head,
        cumulative_filled_quantity=quantity, consumed_minor=consumed_minor,
        broker_evidence_address=content_address({"broker": broker}),
        occurred_at=when, command_id=command_id,
        broker_identity="paper-order-1",
    )


def _recover(sessions, leases, token, evidence):
    with sessions() as session:
        result = recover_reservation(session, leases, token, evidence)
        session.commit()
        return result


def _capital_effects(sessions, reservation_id):
    outbox = execution_outbox()
    with sessions() as session:
        reservation = session.get(CapitalReservationRecord, reservation_id)
        head = session.get(
            CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR"))
        return (
            reservation.state,
            reservation.revision,
            reservation.consumed_quantity,
            reservation.consumed_minor,
            head.revision,
            session.scalar(select(func.count()).select_from(
                CapitalReservationEventRecord).where(
                    CapitalReservationEventRecord.reservation_id == reservation_id)),
            session.scalar(select(func.count()).select_from(outbox.models.Event)),
        )


def _invalid_recovery_numerics(valid):
    return (
        dataclasses.replace(valid, recovery_id="head-float",
                            expected_head_revision=1.0),
        dataclasses.replace(valid, recovery_id="head-bool",
                            expected_head_revision=True),
        dataclasses.replace(valid, recovery_id="head-negative",
                            expected_head_revision=-1),
        dataclasses.replace(valid, recovery_id="head-overflow",
                            expected_head_revision=1 << 31),
        dataclasses.replace(valid, recovery_id="quantity-float",
                            cumulative_filled_quantity=2.0),
        dataclasses.replace(valid, recovery_id="quantity-bool",
                            cumulative_filled_quantity=True),
        dataclasses.replace(valid, recovery_id="quantity-negative",
                            cumulative_filled_quantity=-1),
        dataclasses.replace(valid, recovery_id="quantity-overflow",
                            cumulative_filled_quantity=1 << 31),
        dataclasses.replace(valid, recovery_id="money-float",
                            consumed_minor=40_000.0),
        dataclasses.replace(valid, recovery_id="money-bool",
                            consumed_minor=True),
        dataclasses.replace(valid, recovery_id="money-negative",
                            consumed_minor=-1),
        dataclasses.replace(valid, recovery_id="money-overflow",
                            consumed_minor=1 << 63),
    )


def _assert_invalid_recovery_numerics_have_zero_effect(
        sessions, leases, token, reservation_id, valid, monkeypatch):
    before = _capital_effects(sessions, reservation_id)

    def binding_would_cross_prelock_boundary(*_args, **_kwargs):
        raise AssertionError("invalid recovery reached session binding")

    monkeypatch.setattr(
        leases, "bind_money_session", binding_would_cross_prelock_boundary)
    for evidence in _invalid_recovery_numerics(valid):
        with sessions() as session:
            with pytest.raises(RecoveryRefused, match="INVALID_RECOVERY_NUMERIC"):
                recover_reservation(session, leases, token, evidence)
            session.rollback()
        assert _capital_effects(sessions, reservation_id) == before


def test_invalid_recovery_numerics_refuse_before_binding_with_zero_sqlite_effects(
        admission_store, monkeypatch):
    sessions, leases, token, candidate, reservation_id = _reservation(
        admission_store)
    valid = _evidence(
        reservation_id,
        recovery_id="valid-shape",
        outcome="FILLED",
        head=1,
        quantity=abs(candidate.requested_quantity),
        consumed_minor=40_000,
    )
    _assert_invalid_recovery_numerics_have_zero_effect(
        sessions, leases, token, reservation_id, valid, monkeypatch)


def test_uncertainty_partial_late_ack_and_fill_consume_monotonically(admission_store):
    sessions, leases, token, candidate, reservation_id = _reservation(admission_store)
    command = leases.prepare_command(
        token, kind="place_order", target_id=candidate.target_position_request_id,
        idempotency_key="recovery-command", request_digest="a" * 64,
        requested_qty=candidate.requested_quantity, requested_side="BUY",
        capital_reservation_id=reservation_id,
    )
    leases.transition_command(
        token, command.command_id, from_state="prepared", to_state="sent_unknown")
    unknown = _evidence(
        reservation_id, recovery_id="unknown", outcome="SEND_UNKNOWN",
        head=1, command_id=command.command_id)
    first = _recover(sessions, leases, token, unknown)
    assert first.state == "reconciliation_required" and first.consumed_quantity == 0
    replay = _recover(sessions, leases, token, unknown)
    assert replay.duplicate and replay.revision == first.revision

    partial = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="partial", outcome="PARTIAL_FILL",
        head=2, quantity=1, consumed_minor=20_000,
        command_id=command.command_id, broker="partial"))
    assert (partial.state, partial.consumed_quantity, partial.consumed_minor) == (
        "partially_consumed", 1, 20_000)
    leases.transition_command(
        token, command.command_id, from_state="sent_unknown", to_state="acknowledged",
        broker_order_id="paper-order-1")
    late = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="late", outcome="LATE_ACK",
        head=3, quantity=1, consumed_minor=20_000,
        command_id=command.command_id, broker="late"))
    assert late.state == "reconciliation_required"
    filled = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="filled", outcome="FILLED",
        head=4, quantity=abs(candidate.requested_quantity), consumed_minor=40_000,
        command_id=command.command_id, broker="filled"))
    assert filled.state == "consumed"
    with sessions() as session:
        events = list(session.scalars(select(CapitalReservationEventRecord).where(
            CapitalReservationEventRecord.reservation_id == reservation_id).order_by(
                CapitalReservationEventRecord.revision)))
    assert [row.to_state for row in events] == [
        "held", "submission_pending", "reconciliation_required",
        "partially_consumed", "reconciliation_required", "consumed",
    ]


def test_expiry_external_order_and_cancel_fill_cross_never_release(admission_store):
    sessions, leases, token, _candidate_row, reservation_id = _reservation(admission_store)
    future = NOW + dt.timedelta(hours=2)
    with sessions() as session:
        assert reservation_id in expired_paper_reservations(
            session, owner_id=OWNER, broker_account_id=ACCOUNT,
            observed_at=future)
    expired = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="expired", outcome="EXPIRED",
        head=1, when=future, broker="expired"))
    assert expired.state == "reconciliation_required"
    external = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="external", outcome="EXTERNAL_ORDER",
        head=2, when=future, broker="external"))
    assert external.state == "reconciliation_required"
    crossing = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="cross", outcome="CANCEL_FILL_CROSS",
        head=3, when=future, broker="cross"))
    assert crossing.state == "reconciliation_required"


@pytest.mark.parametrize(
    "release_outcome",
    ("REJECTED_CONFIRMED", "CANCELLED_CONFIRMED", "RESOLVED_UNUSED"),
)
def test_only_exact_zero_fill_proof_releases_and_conflicts_have_zero_effect(
        admission_store, release_outcome):
    sessions, leases, token, candidate, reservation_id = _reservation(admission_store)
    command_id = None
    if release_outcome != "RESOLVED_UNUSED":
        command = leases.prepare_command(
            token, kind="place_order", target_id=candidate.target_position_request_id,
            idempotency_key=f"release-{release_outcome}", request_digest="e" * 64,
            requested_qty=candidate.requested_quantity, requested_side="BUY",
            capital_reservation_id=reservation_id)
        command_id = command.command_id
        leases.transition_command(
            token, command.command_id, from_state="prepared",
            to_state=("failed" if release_outcome == "REJECTED_CONFIRMED"
                      else "cancelled"))
    evidence = _evidence(
        reservation_id, recovery_id="release", outcome=release_outcome, head=1,
        command_id=command_id)
    released = _recover(sessions, leases, token, evidence)
    assert released.state == "released"
    with sessions() as session:
        with pytest.raises(RecoveryRefused, match="CONFLICTING_RECOVERY_DUPLICATE"):
            recover_reservation(session, leases, token, dataclasses.replace(
                evidence, broker_evidence_address=content_address({"different": True})))
        session.rollback()
        stored = session.get(CapitalReservationRecord, reservation_id)
        assert (stored.state, stored.revision) == (
            "released", 2 if command_id is not None else 1)


def test_release_with_fill_or_nonmonotonic_consumption_refuses(admission_store):
    sessions, leases, token, _candidate_row, reservation_id = _reservation(admission_store)
    with sessions() as session:
        with pytest.raises(RecoveryRefused, match="RELEASE_REQUIRES_ZERO_FILL_PROOF"):
            recover_reservation(session, leases, token, _evidence(
                reservation_id, recovery_id="bad-release",
                outcome="RESOLVED_UNUSED", head=1,
                quantity=1, consumed_minor=1))
        session.rollback()
    partial = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="partial", outcome="PARTIAL_FILL",
        head=1, quantity=1, consumed_minor=20_000, broker="partial"))
    with sessions() as session:
        with pytest.raises(RecoveryRefused, match="NON_MONOTONIC_CONSUMPTION"):
            recover_reservation(session, leases, token, _evidence(
                reservation_id, recovery_id="backwards", outcome="PARTIAL_FILL",
                head=partial.head_revision, quantity=0, consumed_minor=0,
                broker="backwards"))
        session.rollback()


def test_submitted_reservation_cannot_release_without_matching_command_state(
        admission_store):
    sessions, leases, token, candidate, reservation_id = _reservation(admission_store)
    command = leases.prepare_command(
        token, kind="place_order", target_id=candidate.target_position_request_id,
        idempotency_key="unconfirmed-reject", request_digest="f" * 64,
        requested_qty=candidate.requested_quantity, requested_side="BUY",
        capital_reservation_id=reservation_id)
    with sessions() as session:
        with pytest.raises(RecoveryRefused, match="REJECTION_COMMAND_MISMATCH"):
            recover_reservation(session, leases, token, _evidence(
                reservation_id, recovery_id="unconfirmed-reject",
                outcome="REJECTED_CONFIRMED", head=1,
                command_id=command.command_id))
        session.rollback()
    with sessions() as session:
        reservation = session.get(CapitalReservationRecord, reservation_id)
        assert reservation.state == "submission_pending"


@pytest.mark.parametrize(
    "command_state", ("prepared", "processing", "sent_unknown", "acknowledged"))
def test_submitted_resolved_unused_never_releases_pending_command(
        admission_store, command_state):
    sessions, leases, token, candidate, reservation_id = _reservation(admission_store)
    command = leases.prepare_command(
        token, kind="place_order", target_id=candidate.target_position_request_id,
        idempotency_key=f"unused-{command_state}", request_digest="1" * 64,
        requested_qty=candidate.requested_quantity, requested_side="BUY",
        capital_reservation_id=reservation_id)
    if command_state != "prepared":
        leases.transition_command(
            token, command.command_id, from_state="prepared", to_state=command_state,
            broker_order_id="paper-order" if command_state == "acknowledged" else "")
    with sessions() as session:
        with pytest.raises(RecoveryRefused, match="RESOLVED_UNUSED_COMMAND_MISMATCH"):
            recover_reservation(session, leases, token, _evidence(
                reservation_id, recovery_id=f"unused-{command_state}",
                outcome="RESOLVED_UNUSED", head=1,
                command_id=command.command_id))
        session.rollback()
        reservation = session.get(CapitalReservationRecord, reservation_id)
        assert reservation.state == "submission_pending"


def test_out_of_order_recovery_timestamp_has_zero_effect(admission_store):
    sessions, leases, token, _candidate_row, reservation_id = _reservation(admission_store)
    later = NOW + dt.timedelta(seconds=2)
    first = _recover(sessions, leases, token, _evidence(
        reservation_id, recovery_id="later", outcome="EXPIRED",
        head=1, when=later, broker="later"))
    with sessions() as session:
        with pytest.raises(RecoveryRefused, match="STALE_RECOVERY_EVIDENCE"):
            recover_reservation(session, leases, token, _evidence(
                reservation_id, recovery_id="earlier", outcome="EXPIRED",
                head=first.head_revision, when=NOW, broker="earlier"))
        session.rollback()
        reservation = session.get(CapitalReservationRecord, reservation_id)
        assert reservation.revision == first.revision


def test_takeover_requires_new_fence_and_retains_reservation(admission_store):
    sessions, leases, token, _candidate_row, reservation_id = _reservation(admission_store)
    with sessions() as session:
        with pytest.raises(RecoveryRefused, match="TAKEOVER_REQUIRES_NEW_FENCE"):
            recover_reservation(session, leases, token, _evidence(
                reservation_id, recovery_id="same-fence", outcome="TAKEOVER", head=1))
        session.rollback()
    leases.release(token)
    replacement = leases.claim(
        owner_id=OWNER, broker_account_id=ACCOUNT,
        cell_id="recovery-cell", worker_id="recovery-boot", ttl_seconds=300)
    result = _recover(sessions, leases, replacement, _evidence(
        reservation_id, recovery_id="takeover", outcome="TAKEOVER", head=1,
        broker="takeover"))
    assert result.state == "reconciliation_required"
    with sessions() as session:
        row = session.get(CapitalReservationRecord, reservation_id)
        assert row.fence_epoch == token.fence_epoch
        assert row.state == "reconciliation_required"


def test_uncertain_entry_block_does_not_disable_risk_reduction():
    request = TargetPositionRequest(
        request_id="reduce", owner_id=OWNER, broker_account_id=ACCOUNT,
        book="paper", deployment_id=101, strategy_key="legacy.strategy",
        strategy_version="v1", admission_address=content_address({"admission": 1}),
        graph_address=None, attribution_state="NON_GRAPH",
        canonical_instrument_key="NIFTY", product_address=PRODUCT,
        target_quantity=1, purpose="RISK_REDUCTION",
        decision_at=dt.datetime.now(dt.UTC),
    )
    pending = PendingQuantityEvidence(
        evidence_id="unknown", owner_id=OWNER, broker_account_id=ACCOUNT,
        book="paper", canonical_instrument_key="NIFTY",
        product_address=PRODUCT, signed_remaining_quantity=1,
        state="sent_unknown", uncertain=True,
        source_address=content_address({"command": "unknown"}),
    )
    result = derive_target_delta(request, held_quantity=2, pending=(pending,))
    assert result.accepted and result.risk_reducing
    assert result.bypass_entry_admission
    assert result.reason_code == "RISK_REDUCTION_BYPASSES_ENTRY_UNCERTAINTY"


def test_postgres_two_recovery_sessions_cannot_resolve_one_head_revision_twice(
        postgres_admission):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    with sessions() as session:
        admitted = admit_closed_batch(
            session, leases, token,
            _pg_batch(token, (candidate,), database_now))
        session.commit()
    reservation_id = admitted.decisions[0].reservation_id
    evidences = (
        _evidence(
            reservation_id, recovery_id="pg-expired", outcome="EXPIRED",
            head=1, when=database_now, broker="pg-expired"),
        _evidence(
            reservation_id, recovery_id="pg-external", outcome="EXTERNAL_ORDER",
            head=1, when=database_now, broker="pg-external"),
    )
    barrier = threading.Barrier(2)

    def attempt(evidence):
        barrier.wait(timeout=5)
        with sessions() as session:
            try:
                result = recover_reservation(session, leases, token, evidence)
                session.commit()
                return result
            except Exception as exc:
                session.rollback()
                return exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, evidences))
    accepted = [row for row in outcomes if not isinstance(row, Exception)]
    refused = [row for row in outcomes if isinstance(row, RecoveryRefused)]
    assert len(accepted) == 1
    assert len(refused) == 1 and refused[0].code == "STALE_HEAD_REVISION"
    with sessions() as session:
        reservation = session.get(CapitalReservationRecord, reservation_id)
        assert reservation.state == "reconciliation_required"
        reasons = set(session.scalars(select(
            CapitalReservationEventRecord.reason_code).where(
                CapitalReservationEventRecord.reservation_id == reservation_id)))
        assert len(reasons & {"EXPIRED", "EXTERNAL_ORDER"}) == 1


def test_invalid_recovery_numerics_refuse_before_binding_with_zero_postgres_effects(
        postgres_admission, monkeypatch):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    with sessions() as session:
        admitted = admit_closed_batch(
            session, leases, token,
            _pg_batch(token, (candidate,), database_now))
        session.commit()
    reservation_id = admitted.decisions[0].reservation_id
    valid = _evidence(
        reservation_id,
        recovery_id="pg-valid-shape",
        outcome="FILLED",
        head=1,
        quantity=abs(candidate.requested_quantity),
        consumed_minor=40_000,
        when=database_now,
    )
    _assert_invalid_recovery_numerics_have_zero_effect(
        sessions, leases, token, reservation_id, valid, monkeypatch)
