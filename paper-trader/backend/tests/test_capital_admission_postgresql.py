"""Authoritative PostgreSQL 16 lock/fence tests for capital admission."""
from __future__ import annotations

import concurrent.futures
import dataclasses
import datetime as dt
import threading

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    AccountExecutionCommand,
    Base,
    BrokerAccount,
    CapitalReservationEventRecord,
    CapitalReservationHead,
    CapitalReservationRecord,
    CapitalState,
    DecisionBatchRecord,
    Deployment,
    ExecutionIntent,
    ExecutionOrderEvent,
    Organization,
    SizingPolicyRecord,
)
from app.events.planes import execution_outbox
from app.execution.capital_admission import (
    CapitalAdmissionRefused,
    admit_closed_batch,
    current_held_pending_digest,
)
from app.execution.leases import LeaseRepository, RecoveryRequired, StaleLease
from tests.test_capital_admission import (
    ACCOUNT,
    NOW,
    OWNER,
    POLICY,
    _batch,
    _candidate,
    _pending_intent,
    _seed_candidates,
)


@pytest.fixture()
def postgres_admission(pg_sandbox):
    engine = pg_sandbox.engine("capital_admission", pool_size=8, max_overflow=4)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sessions.begin() as session:
        session.add(Organization(organization_id=OWNER, name="Owner A"))
        session.add(BrokerAccount(
            broker_account_id=ACCOUNT, owner_id=OWNER, broker="paper",
            external_account_id="external-a", display_name="A",
        ))
        session.add(Deployment(
            id=101, owner_id=OWNER, broker_account_id=ACCOUNT,
            name="capital-admission-fixture", strategy_key=None,
            strategy_version=None, admission_address=None, graph_address=None,
            attribution_state="NON_GRAPH", universe_mode="legacy", params_json="{}",
            allocation=None, status="active", armed=False, notes="",
            created_at=NOW, updated_at=NOW,
        ))
        session.add(CapitalState(
            broker_account_id=ACCOUNT, book="paper", initial_capital=1000.0,
            cash=1000.0, realized_pnl=0.0, updated_at=NOW,
        ))
        session.add(SizingPolicyRecord(
            policy_address=POLICY, policy_id="fixed", version=1,
            mode="FIXED_UNITS", currency="INR", fixed_units=1, fixed_lots=None,
            amount_minor=None, rate_ppm=None, risk_budget_minor=None,
            target_volatility_ppm=None, min_quantity=1, max_quantity=None,
            max_capital_minor=None, fee_buffer_minor=0, safety_buffer_minor=0,
            allow_resize=False, canonical_json="{}", created_at=NOW,
        ))
        session.add(CapitalReservationHead(
            owner_id=OWNER, broker_account_id=ACCOUNT, book="paper",
            currency="INR", revision=0, updated_at=NOW,
        ))
    leases = LeaseRepository(sessions)
    token = leases.claim(
        owner_id=OWNER, broker_account_id=ACCOUNT,
        cell_id="pg-cell", worker_id="pg-boot", ttl_seconds=300,
    )
    leases.activate(token, reconciliation_evidence="PostgreSQL fixture is reconciled")
    with sessions() as session:
        database_now = leases.database_time(session)
    return sessions, leases, token, database_now


def _pg_candidate(index, database_now, **kwargs):
    return dataclasses.replace(
        _candidate(index, **kwargs), created_at=database_now,
        freshness_deadline=database_now + dt.timedelta(minutes=5),
    )


def _pg_batch(token, candidates, database_now, **kwargs):
    return dataclasses.replace(
        _batch(token, candidates, **kwargs),
        decision_at=database_now, effective_at=database_now,
        margin_observed_at=database_now,
    )


def _attempt(sessions, leases, token, batch, barrier):
    with sessions() as session:
        barrier.wait(timeout=5)
        try:
            result = admit_closed_batch(session, leases, token, batch)
            session.commit()
            return result
        except Exception as exc:  # The assertion inspects the exact typed outcome.
            session.rollback()
            return exc


def test_two_postgres_sessions_cannot_double_reserve_one_head(postgres_admission):
    sessions, leases, token, database_now = postgres_admission
    first = _pg_candidate(1, database_now, cost=70_000, priority=1)
    second = _pg_candidate(2, database_now, cost=70_000, priority=1)
    _seed_candidates(sessions, (first, second))
    batches = (
        _pg_batch(token, (first,), database_now, batch_id="race-a"),
        _pg_batch(token, (second,), database_now, batch_id="race-b"),
    )
    barrier = threading.Barrier(2)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(
            lambda batch: _attempt(sessions, leases, token, batch, barrier), batches))
    successes = [row for row in outcomes if not isinstance(row, Exception)]
    refusals = [row for row in outcomes if isinstance(row, CapitalAdmissionRefused)]
    assert len(successes) == 1
    assert len(refusals) == 1 and refusals[0].code == "STALE_HEAD_REVISION"
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DecisionBatchRecord)) == 1
        reservations = list(session.scalars(sa.select(CapitalReservationRecord)))
        assert len(reservations) == 1 and reservations[0].estimated_minor == 70_000
        assert session.get(CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR")).revision == 1


def test_postgres_admission_waits_for_the_exact_head_row(postgres_admission):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _pg_batch(token, (candidate,), database_now)
    blocker = sessions()
    blocker.begin()
    blocker.scalar(sa.select(CapitalReservationHead).where(
        CapitalReservationHead.owner_id == OWNER,
        CapitalReservationHead.broker_account_id == ACCOUNT,
        CapitalReservationHead.book == "paper",
        CapitalReservationHead.currency == "INR",
    ).with_for_update())
    statements = []
    engine = blocker.get_bind()

    def observe(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(" ".join(statement.upper().split()))

    sa.event.listen(engine, "before_cursor_execute", observe)
    started = threading.Event()
    outcome = []

    def admit():
        started.set()
        with sessions() as session:
            try:
                result = admit_closed_batch(session, leases, token, batch)
                session.commit()
                outcome.append(result)
            except Exception as exc:
                session.rollback()
                outcome.append(exc)

    thread = threading.Thread(target=admit)
    thread.start()
    started.wait(2)
    thread.join(0.2)
    assert thread.is_alive(), "admission did not wait for the reservation-head row lock"
    blocker.rollback()
    blocker.close()
    thread.join(5)
    sa.event.remove(engine, "before_cursor_execute", observe)
    assert not thread.is_alive() and len(outcome) == 1
    assert not isinstance(outcome[0], Exception)
    assert any("FROM CAPITAL_RESERVATION_HEADS" in statement
               and "FOR UPDATE" in statement for statement in statements)


def test_two_postgres_sessions_prepare_one_reservation_once(postgres_admission):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    with sessions() as session:
        admitted = admit_closed_batch(
            session, leases, token, _pg_batch(token, (candidate,), database_now))
        session.commit()
    reservation_id = admitted.decisions[0].reservation_id
    with pytest.raises(RecoveryRequired, match="side"):
        leases.prepare_command(
            token, kind="place_order",
            target_id=candidate.target_position_request_id,
            idempotency_key="pg-wrong-side", request_digest="9" * 64,
            requested_qty=candidate.requested_quantity,
            requested_side="SELL", capital_reservation_id=reservation_id)
    barrier = threading.Barrier(2)

    def prepare(index):
        barrier.wait(timeout=5)
        try:
            return leases.prepare_command(
                token, kind="place_order",
                target_id=candidate.target_position_request_id,
                idempotency_key=f"prepare-{index}",
                request_digest=f"{index + 1:064x}"[-64:],
                requested_qty=candidate.requested_quantity,
                requested_side="BUY", capital_reservation_id=reservation_id,
            )
        except Exception as exc:
            return exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(prepare, (1, 2)))
    commands = [row for row in outcomes if isinstance(row, AccountExecutionCommand)]
    refusals = [row for row in outcomes if isinstance(row, RecoveryRequired)]
    assert len(commands) == 1 and len(refusals) == 1
    with sessions() as session:
        reservation = session.get(CapitalReservationRecord, reservation_id)
        assert reservation.state == "submission_pending"
        assert reservation.command_id == commands[0].command_id
        assert session.scalar(sa.select(sa.func.count()).select_from(
            AccountExecutionCommand).where(
                AccountExecutionCommand.kind == "place_order")) == 1


@pytest.mark.parametrize(
    ("candidate_index", "invalid_quantity"),
    ((1, 2.0), (0, True)),
)
def test_postgres_reserved_command_quantity_requires_exact_positive_int(
        postgres_admission, candidate_index, invalid_quantity):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(candidate_index, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    with sessions() as session:
        admitted = admit_closed_batch(
            session, leases, token,
            _pg_batch(token, (candidate,), database_now))
        session.commit()
    reservation_id = admitted.decisions[0].reservation_id
    outbox = execution_outbox()
    with sessions() as session:
        before = (
            session.scalar(sa.select(sa.func.count()).select_from(
                AccountExecutionCommand)),
            session.scalar(sa.select(sa.func.count()).select_from(
                CapitalReservationEventRecord)),
            session.get(
                CapitalReservationHead,
                (OWNER, ACCOUNT, "paper", "INR"),
            ).revision,
            session.scalar(sa.select(sa.func.count()).select_from(
                outbox.models.Event)),
        )
    with pytest.raises(RecoveryRequired, match="quantity"):
        leases.prepare_command(
            token,
            kind="place_order",
            target_id=candidate.target_position_request_id,
            idempotency_key=f"pg-invalid-{type(invalid_quantity).__name__}",
            request_digest="6" * 64,
            requested_qty=invalid_quantity,
            requested_side="BUY",
            capital_reservation_id=reservation_id,
        )
    with sessions() as session:
        reservation = session.get(CapitalReservationRecord, reservation_id)
        after = (
            session.scalar(sa.select(sa.func.count()).select_from(
                AccountExecutionCommand)),
            session.scalar(sa.select(sa.func.count()).select_from(
                CapitalReservationEventRecord)),
            session.get(
                CapitalReservationHead,
                (OWNER, ACCOUNT, "paper", "INR"),
            ).revision,
            session.scalar(sa.select(sa.func.count()).select_from(
                outbox.models.Event)),
        )
        assert (reservation.state, reservation.command_id, reservation.revision) == (
            "held", None, 0)
    assert after == before


def test_postgres_unresolved_intent_event_snapshot_blocks_new_reservation(
        postgres_admission):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    stale_batch = _pg_batch(token, (candidate,), database_now)
    with sessions.begin() as session:
        intent = _pending_intent(token, client_intent_id="pg-pending")
        session.add(intent)
        session.add(ExecutionOrderEvent(
            owner_id=OWNER, broker_account_id=ACCOUNT,
            client_intent_id=intent.client_intent_id,
            source="engine", source_event_id="intent-created",
            kind="INTENT_CREATED", broker_order_id=None, broker_status="",
            cumulative_filled_qty=0, avg_price=0.0,
            observed_at=database_now, payload_json="{}", anomaly="",
            fence_epoch=token.fence_epoch))
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="HELD_PENDING_SNAPSHOT_STALE"):
            admit_closed_batch(session, leases, token, stale_batch)
        session.rollback()
        digest = current_held_pending_digest(
            session, owner_id=OWNER, broker_account_id=ACCOUNT,
            book="paper", currency="INR")
    current = dataclasses.replace(candidate, held_pending_digest=digest)
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="BROKER_RECONCILIATION_REQUIRED"):
            admit_closed_batch(
                session, leases, token,
                _pg_batch(token, (current,), database_now))
        session.rollback()
    with sessions.begin() as session:
        session.add(ExecutionOrderEvent(
            owner_id=OWNER, broker_account_id=ACCOUNT,
            client_intent_id="pg-pending", source="broker",
            source_event_id="rejected", kind="REJECTED",
            broker_order_id="pg-order", broker_status="REJECTED",
            cumulative_filled_qty=0, avg_price=0.0,
            observed_at=database_now + dt.timedelta(seconds=1),
            payload_json="{}", anomaly="", fence_epoch=token.fence_epoch))
    with sessions() as session:
        result = admit_closed_batch(session, leases, token, stale_batch)
        session.commit()
    assert result.decisions[0].status == "admitted"


def test_postgres_stale_fence_and_post_ttl_exact_replay_are_zero_effect(
        postgres_admission, monkeypatch):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _pg_batch(token, (candidate,), database_now)
    with sessions() as session:
        first = admit_closed_batch(session, leases, token, batch)
        session.commit()
    monkeypatch.setattr(
        leases, "database_time",
        lambda _session: database_now + dt.timedelta(
            seconds=batch.reservation_ttl_seconds + 1))
    with sessions() as session:
        replay = admit_closed_batch(session, leases, token, batch)
        session.commit()
    assert replay.duplicate and replay.batch_address == first.batch_address

    leases.release(token)
    replacement = leases.claim(
        owner_id=OWNER, broker_account_id=ACCOUNT,
        cell_id="replacement-cell", worker_id="replacement-boot", ttl_seconds=300,
    )
    candidate2 = _pg_candidate(2, database_now, cost=10_000)
    _seed_candidates(sessions, (candidate2,))
    stale_batch = _pg_batch(
        token, (candidate2,), database_now,
        batch_id="stale-batch", head_revision=1)
    with sessions() as session:
        with pytest.raises(StaleLease):
            admit_closed_batch(session, leases, token, stale_batch)
        session.rollback()
    with sessions() as session:
        assert session.get(DecisionBatchRecord, "stale-batch") is None
        assert session.get(CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR")).revision == 1
    # The replacement remains recovering; the stale attempt did not activate or mutate it.
    with pytest.raises(RecoveryRequired):
        leases.prepare_command(
            replacement, kind="place_order", target_id="none",
            idempotency_key="recovery-denied", request_digest="d" * 64,
        )


def test_postgres_float_rank_input_refuses_before_any_batch_effect(postgres_admission):
    sessions, leases, token, database_now = postgres_admission
    candidate = _pg_candidate(1, database_now, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    mutated = dataclasses.replace(candidate, score_scaled=0.5)
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="INVALID_CANDIDATE"):
            admit_closed_batch(
                session, leases, token,
                _pg_batch(token, (mutated,), database_now))
        session.rollback()
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(
            DecisionBatchRecord)) == 0
