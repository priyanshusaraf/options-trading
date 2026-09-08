"""Direct SQLite parity tests for the unwired capital-admission transaction."""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib

import pytest
from sqlalchemy import create_engine, func, select
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
    PortfolioAdmissionDecisionRecord,
    SizingDecisionRecord,
    SizingPolicyRecord,
    TargetPositionRequestRecord,
)
from app.events.planes import execution_outbox
from app.execution import capital_admission as capital_admission_module
from app.execution.capital_admission import (
    AdmissionBatch,
    AdmissionCandidate,
    CapitalAdmissionRefused,
    admit_closed_batch,
    current_held_pending_digest,
)
from app.execution.leases import LeaseRepository, RecoveryRequired, StaleLease
from app.ir.hashing import canonical_json, content_address


NOW = dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)
OWNER = "owner-a"
ACCOUNT = "account-a"
POLICY = content_address({"policy": "fixed-units-v1"})
PRODUCT = content_address({"product": "equity-v1"})
PRODUCT_POLICY = content_address({"product-policy": "v1"})
PORTFOLIO_POLICY = content_address({"portfolio-policy": "compatibility-v1"})
CAPITAL_SNAPSHOT = content_address({"cash_minor": 100_000, "observed_at": NOW.isoformat()})
MARGIN_SNAPSHOT = content_address({"margin_minor": 100_000, "observed_at": NOW.isoformat()})
EMPTY_PENDING_DIGEST = hashlib.sha256(canonical_json({
    "reservations": [], "commands": [], "unresolved_intents": [],
}).encode("utf-8")).hexdigest()


@pytest.fixture()
def admission_store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'capital-admission.db'}", future=True,
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sessions.begin() as session:
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
        cell_id="cell-a", worker_id="boot-a", ttl_seconds=300,
    )
    leases.activate(token, reconciliation_evidence="fixture has no broker commands")
    yield engine, sessions, leases, token
    engine.dispose()


def _candidate(index: int, *, cost: int, priority: int = 1,
               score: int = 100, group_id: str = "",
               group_semantics: str = "INDEPENDENT",
               purpose: str = "ENTRY") -> AdmissionCandidate:
    quantity = index + 1
    if purpose == "RISK_REDUCTION":
        cost = 0
    return AdmissionCandidate(
        candidate_intent_id=f"candidate-{index}", deployment_id=101,
        strategy_key=None, strategy_version=None, admission_address=None,
        graph_address=None, attribution_state="NON_GRAPH",
        signal_instrument_key=f"signal-{index}",
        execution_instrument_key=f"execution-{index}",
        product_address=PRODUCT,
        sizing_decision_address=content_address({"sizing": index}),
        target_position_request_id=f"target-{index}",
        direction="LONG", purpose=purpose, requested_quantity=quantity,
        required_capital_minor=cost, group_id=group_id,
        group_semantics=group_semantics,
        freshness_deadline=NOW + dt.timedelta(minutes=5),
        priority=priority, score_scaled=score,
        held_pending_digest=EMPTY_PENDING_DIGEST, created_at=NOW,
    )


def _seed_candidates(sessions, candidates: tuple[AdmissionCandidate, ...]) -> None:
    with sessions.begin() as session:
        for candidate in candidates:
            session.add(SizingDecisionRecord(
                decision_address=candidate.sizing_decision_address,
                policy_address=POLICY, product_address=PRODUCT,
                inputs_address=content_address({"inputs": candidate.candidate_intent_id}),
                accepted=True, requested_quantity=abs(candidate.requested_quantity),
                admitted_quantity=abs(candidate.requested_quantity),
                required_capital_minor=candidate.required_capital_minor,
                estimated_fees_minor=0, binding_constraint="none",
                reason_code="SIZED", resized=False,
                input_addresses_json="[]", decided_at=NOW,
            ))
            session.add(TargetPositionRequestRecord(
                request_id=candidate.target_position_request_id,
                request_address=content_address({"target": candidate.candidate_intent_id}),
                owner_id=OWNER, broker_account_id=ACCOUNT, book="paper",
                deployment_id=101, strategy_key=None, strategy_version=None,
                admission_address=None, graph_address=None,
                attribution_state="NON_GRAPH",
                canonical_instrument_key=candidate.signal_instrument_key,
                product_address=PRODUCT,
                sizing_decision_address=candidate.sizing_decision_address,
                target_quantity=candidate.requested_quantity,
                purpose=candidate.purpose, group_id=candidate.group_id,
                decision_at=NOW,
            ))


def _batch(token, candidates: tuple[AdmissionCandidate, ...], *, batch_id="batch-1",
           head_revision=0, margin_minor=100_000, capital_minor=100_000) -> AdmissionBatch:
    return AdmissionBatch(
        decision_batch_id=batch_id, owner_id=OWNER, broker_account_id=ACCOUNT,
        book="paper", currency="INR", fence_epoch=token.fence_epoch,
        decision_at=NOW, effective_at=NOW,
        capital_snapshot_minor=capital_minor,
        capital_snapshot_address=CAPITAL_SNAPSHOT,
        margin_available_minor=margin_minor, margin_source="fixture",
        margin_observed_at=NOW, margin_snapshot_address=MARGIN_SNAPSHOT,
        safety_buffer_minor=0, expected_head_revision=head_revision,
        product_policy_address=PRODUCT_POLICY, sizing_policy_address=POLICY,
        portfolio_policy_address=PORTFOLIO_POLICY, candidates=candidates,
        reservation_ttl_seconds=3600,
    )


def _admit(sessions, leases, token, batch):
    with sessions() as session:
        result = admit_closed_batch(session, leases, token, batch)
        session.commit()
        return result


def _pending_intent(token, *, client_intent_id="pending-intent"):
    return ExecutionIntent(
        client_intent_id=client_intent_id, deployment_id=101,
        owner_id=OWNER, broker_account_id=ACCOUNT,
        broker="paper", account_scope=ACCOUNT, connection_scope="paper",
        broker_tag=f"tag-{client_intent_id}"[:20], intent="ENTRY",
        instrument_key="signal-1", tradingsymbol="execution-1",
        exchange="NFO", side="BUY", product="MIS", order_type="MARKET",
        requested_qty=2, limit_price=None, decision_price=100.0,
        signal_at=NOW, strategy_key=None, strategy_version=None,
        admission_address=None, graph_address=None, attribution_state="NON_GRAPH",
        context_json=canonical_json({"book": "paper"}),
        created_at=NOW, fence_epoch=token.fence_epoch,
    )


def test_complete_batch_is_atomic_ranked_and_has_one_outbox(admission_store):
    _engine, sessions, leases, token = admission_store
    candidates = (
        _candidate(1, cost=50_000, priority=2),
        _candidate(2, cost=70_000, priority=1),
    )
    _seed_candidates(sessions, candidates)
    result = _admit(sessions, leases, token, _batch(token, candidates))
    assert [(row.candidate_intent_id, row.status) for row in result.decisions] == [
        ("candidate-1", "rejected"), ("candidate-2", "admitted")]
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 1
        assert session.scalar(select(func.count()).select_from(
            PortfolioAdmissionDecisionRecord)) == len(candidates)
        assert session.scalar(select(func.count()).select_from(CapitalReservationRecord)) == 1
        assert session.scalar(select(func.count()).select_from(
            CapitalReservationEventRecord)) == 1
        assert session.get(CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR")).revision == 1
        outbox = execution_outbox()
        assert session.scalar(select(func.count()).select_from(outbox.models.Event).where(
            outbox.models.Event.aggregate_type == "capital_admission")) == 1


def test_exact_duplicate_converges_and_conflicting_bytes_have_zero_effect(admission_store):
    _engine, sessions, leases, token = admission_store
    candidates = (_candidate(1, cost=40_000),)
    _seed_candidates(sessions, candidates)
    batch = _batch(token, candidates)
    first = _admit(sessions, leases, token, batch)
    replay = _admit(sessions, leases, token, batch)
    assert replay == dataclasses.replace(first, duplicate=True)
    conflict = dataclasses.replace(batch, margin_available_minor=99_999)
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="CONFLICTING_DUPLICATE"):
            admit_closed_batch(session, leases, token, conflict)
        session.rollback()
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 1
        assert session.get(CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR")).revision == 1


def test_atomic_and_resizable_group_semantics_fail_closed(admission_store):
    _engine, sessions, leases, token = admission_store
    candidates = (
        _candidate(1, cost=30_000, priority=1, group_id="atomic", group_semantics="ATOMIC"),
        _candidate(2, cost=30_000, priority=1, group_id="atomic", group_semantics="ATOMIC"),
        _candidate(3, cost=50_000, priority=2),
        _candidate(4, cost=1, priority=0, group_id="resize", group_semantics="RESIZABLE"),
    )
    _seed_candidates(sessions, candidates)
    result = _admit(sessions, leases, token, _batch(token, candidates, margin_minor=50_000))
    status = {row.candidate_intent_id: (row.status, row.reason_code)
              for row in result.decisions}
    assert status["candidate-1"] == ("rejected", "ATOMIC_GROUP_INSUFFICIENT_CAPITAL")
    assert status["candidate-2"] == ("rejected", "ATOMIC_GROUP_INSUFFICIENT_CAPITAL")
    assert status["candidate-3"] == ("admitted", "ADMITTED")
    assert status["candidate-4"] == ("rejected", "RESIZE_NOT_AUTHORIZED")


def test_mixed_group_semantics_refuse_before_any_effect(admission_store):
    _engine, sessions, leases, token = admission_store
    candidates = (
        _candidate(1, cost=10_000, group_id="mixed", group_semantics="ATOMIC"),
        _candidate(2, cost=10_000, group_id="mixed", group_semantics="INDEPENDENT"),
    )
    _seed_candidates(sessions, candidates)
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="INCONSISTENT_GROUP_SEMANTICS"):
            admit_closed_batch(session, leases, token, _batch(token, candidates))
        session.rollback()
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 0


def test_risk_reduction_remains_available_without_entry_capital(admission_store):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=0, purpose="RISK_REDUCTION")
    _seed_candidates(sessions, (candidate,))
    result = _admit(
        sessions, leases, token,
        _batch(token, (candidate,), margin_minor=0),
    )
    assert result.decisions[0].status == "admitted"
    assert result.decisions[0].reason_code == "RISK_REDUCTION_AVAILABLE"
    assert result.decisions[0].held_capital_minor == 0
    assert result.decisions[0].reservation_id is None


def test_stable_tie_uses_candidate_address_not_input_order(admission_store):
    _engine, sessions, leases, token = admission_store
    candidates = (
        _candidate(1, cost=60_000, priority=1, score=100),
        _candidate(2, cost=60_000, priority=1, score=100),
    )
    _seed_candidates(sessions, candidates)
    batch = _batch(token, tuple(reversed(candidates)), margin_minor=60_000)
    result = _admit(sessions, leases, token, batch)
    expected = min(candidates, key=batch.candidate_address).candidate_intent_id
    assert [row.candidate_intent_id for row in result.decisions if row.status == "admitted"] == [expected]


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        ("head", "STALE_HEAD_REVISION"),
        ("cash", "CAPITAL_SNAPSHOT_STALE"),
        ("sizing", "SIZING_EVIDENCE_MISMATCH"),
        ("freshness", "STALE_CANDIDATE"),
        ("pending", "HELD_PENDING_SNAPSHOT_STALE"),
    ),
)
def test_critical_input_mutations_have_zero_effect(admission_store, mutation, code):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _batch(token, (candidate,))
    if mutation == "head":
        batch = dataclasses.replace(batch, expected_head_revision=1)
    elif mutation == "cash":
        batch = dataclasses.replace(batch, capital_snapshot_minor=99_999)
    elif mutation == "sizing":
        candidate = dataclasses.replace(candidate, required_capital_minor=40_001)
        batch = _batch(token, (candidate,))
    elif mutation == "freshness":
        candidate = dataclasses.replace(candidate, freshness_deadline=NOW - dt.timedelta(seconds=1))
        batch = _batch(token, (candidate,))
    else:
        candidate = dataclasses.replace(candidate, held_pending_digest="f" * 64)
        batch = _batch(token, (candidate,))
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match=code):
            admit_closed_batch(session, leases, token, batch)
        session.rollback()
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 0
        assert session.scalar(select(func.count()).select_from(CapitalReservationRecord)) == 0
        assert session.get(CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR")).revision == 0


def test_stale_fence_and_unresolved_broker_command_have_zero_effect(admission_store):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _batch(token, (candidate,))
    leases.release(token)
    replacement = leases.claim(
        owner_id=OWNER, broker_account_id=ACCOUNT,
        cell_id="cell-b", worker_id="boot-b", ttl_seconds=300)
    with sessions() as session:
        with pytest.raises(StaleLease):
            admit_closed_batch(session, leases, token, batch)
        session.rollback()
    leases.activate(replacement, reconciliation_evidence="replacement reconciled")
    candidate2 = dataclasses.replace(
        candidate, candidate_intent_id="candidate-2",
        sizing_decision_address=content_address({"sizing": 2}),
        target_position_request_id="target-2")
    _seed_candidates(sessions, (candidate2,))
    with sessions.begin() as session:
        session.add(AccountExecutionCommand(
            command_id="unknown-command", idempotency_key="unknown-key",
            owner_id=OWNER, broker_account_id=ACCOUNT,
            fence_epoch=replacement.fence_epoch, cell_id=replacement.cell_id,
            worker_id=replacement.worker_id, kind="place_order", target_id="target-x",
            request_digest="a" * 64, state="sent_unknown", created_at=NOW,
            updated_at=NOW,
        ))
    with sessions() as session:
        pending_digest = current_held_pending_digest(
            session, owner_id=OWNER, broker_account_id=ACCOUNT,
            book="paper", currency="INR")
    candidate2 = dataclasses.replace(
        candidate2, held_pending_digest=pending_digest)
    batch2 = _batch(replacement, (candidate2,), batch_id="batch-2")
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="BROKER_RECONCILIATION_REQUIRED"):
            admit_closed_batch(session, leases, replacement, batch2)
        session.rollback()
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 0


def test_unresolved_intent_and_event_enter_pending_snapshot_and_block_new_capital(
        admission_store):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    stale_batch = _batch(token, (candidate,))
    with sessions.begin() as session:
        intent = _pending_intent(token)
        session.add(intent)
        session.add(ExecutionOrderEvent(
            owner_id=OWNER, broker_account_id=ACCOUNT,
            client_intent_id=intent.client_intent_id,
            source="engine", source_event_id="intent-created",
            kind="INTENT_CREATED", broker_order_id=None, broker_status="",
            cumulative_filled_qty=0, avg_price=0.0, observed_at=NOW,
            payload_json="{}", anomaly="", fence_epoch=token.fence_epoch,
        ))
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="HELD_PENDING_SNAPSHOT_STALE"):
            admit_closed_batch(session, leases, token, stale_batch)
        session.rollback()
        digest = current_held_pending_digest(
            session, owner_id=OWNER, broker_account_id=ACCOUNT,
            book="paper", currency="INR")
    current_candidate = dataclasses.replace(candidate, held_pending_digest=digest)
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="BROKER_RECONCILIATION_REQUIRED"):
            admit_closed_batch(
                session, leases, token, _batch(token, (current_candidate,)))
        session.rollback()
    with sessions.begin() as session:
        session.add(ExecutionOrderEvent(
            owner_id=OWNER, broker_account_id=ACCOUNT,
            client_intent_id="pending-intent", source="broker",
            source_event_id="rejected", kind="REJECTED",
            broker_order_id="paper-order", broker_status="REJECTED",
            cumulative_filled_qty=0, avg_price=0.0,
            observed_at=NOW + dt.timedelta(seconds=1), payload_json="{}",
            anomaly="", fence_epoch=token.fence_epoch,
        ))
    with sessions() as session:
        assert current_held_pending_digest(
            session, owner_id=OWNER, broker_account_id=ACCOUNT,
            book="paper", currency="INR") == EMPTY_PENDING_DIGEST
    result = _admit(sessions, leases, token, stale_batch)
    assert result.decisions[0].status == "admitted"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("score_scaled", 0.5), ("score_scaled", True),
        ("priority", 1.5), ("requested_quantity", 2.0),
        ("required_capital_minor", 40_000.0), ("deployment_id", 101.0),
    ),
)
def test_candidate_rank_and_money_numerics_require_exact_int_before_hashing(
        admission_store, field, value):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    mutated = dataclasses.replace(candidate, **{field: value})
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match="INVALID_CANDIDATE"):
            admit_closed_batch(session, leases, token, _batch(token, (mutated,)))
        session.rollback()
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 0


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("fence_epoch", True, "INVALID_REVISION"),
        ("expected_head_revision", False, "INVALID_REVISION"),
        ("reservation_ttl_seconds", True, "INVALID_BATCH_SHAPE"),
        ("margin_available_minor", 100_000.0, "INVALID_MONEY"),
    ),
)
def test_batch_numerics_require_exact_int(admission_store, field, value, code):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = dataclasses.replace(_batch(token, (candidate,)), **{field: value})
    with sessions() as session:
        with pytest.raises(CapitalAdmissionRefused, match=code):
            admit_closed_batch(session, leases, token, batch)
        session.rollback()


def test_exact_complete_duplicate_converges_after_decision_ttl(admission_store, monkeypatch):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    batch = _batch(token, (candidate,))
    first = _admit(sessions, leases, token, batch)
    monkeypatch.setattr(
        leases, "database_time",
        lambda _session: batch.decision_at + dt.timedelta(
            seconds=batch.reservation_ttl_seconds + 1))
    replay = _admit(sessions, leases, token, batch)
    assert replay == dataclasses.replace(first, duplicate=True)


def test_active_reservation_balance_prevents_double_allocation(admission_store):
    _engine, sessions, leases, token = admission_store
    first_candidate = _candidate(1, cost=70_000)
    _seed_candidates(sessions, (first_candidate,))
    first = _admit(sessions, leases, token, _batch(token, (first_candidate,)))
    assert first.decisions[0].status == "admitted"
    with sessions() as session:
        pending_digest = current_held_pending_digest(
            session, owner_id=OWNER, broker_account_id=ACCOUNT,
            book="paper", currency="INR")
    second_candidate = dataclasses.replace(
        _candidate(2, cost=40_000), held_pending_digest=pending_digest)
    _seed_candidates(sessions, (second_candidate,))
    second = _admit(sessions, leases, token, _batch(
        token, (second_candidate,), batch_id="batch-2", head_revision=1))
    assert second.decisions[0].status == "rejected"
    with sessions() as session:
        batches = list(session.scalars(select(DecisionBatchRecord).order_by(
            DecisionBatchRecord.decision_batch_id)))
        assert batches[1].active_reservation_minor == 70_000


def test_caller_rollback_erases_the_complete_batch(admission_store):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    with sessions() as session:
        admit_closed_batch(session, leases, token, _batch(token, (candidate,)))
        session.rollback()
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 0
        assert session.scalar(select(func.count()).select_from(
            PortfolioAdmissionDecisionRecord)) == 0
        assert session.scalar(select(func.count()).select_from(CapitalReservationRecord)) == 0
        assert session.get(CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR")).revision == 0


def test_savepoint_rolls_back_partial_flush_after_late_outbox_failure(
        admission_store, monkeypatch):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))

    def refuse_outbox(*_args, **_kwargs):
        raise RuntimeError("late outbox failure")

    monkeypatch.setattr(capital_admission_module, "_append_execution_change", refuse_outbox)
    with sessions() as session:
        with pytest.raises(RuntimeError, match="late outbox failure"):
            admit_closed_batch(session, leases, token, _batch(token, (candidate,)))
        # The caller can keep and commit its outer transaction. The seam must
        # already have erased every staged capital-admission effect.
        session.commit()
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DecisionBatchRecord)) == 0
        assert session.scalar(select(func.count()).select_from(CapitalReservationRecord)) == 0
        assert session.get(CapitalReservationHead, (OWNER, ACCOUNT, "paper", "INR")).revision == 0


def test_command_preparation_requires_exact_live_reservation(admission_store):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(1, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    result = _admit(sessions, leases, token, _batch(token, (candidate,)))
    reservation_id = result.decisions[0].reservation_id
    assert reservation_id is not None
    with pytest.raises(RecoveryRequired, match="quantity"):
        leases.prepare_command(
            token, kind="place_order", target_id=candidate.target_position_request_id,
            idempotency_key="wrong-quantity", request_digest="b" * 64,
            requested_qty=999, requested_side="BUY",
            capital_reservation_id=reservation_id,
        )
    for key, quantity, side, message in (
            ("negative-quantity", -candidate.requested_quantity, "BUY", "quantity"),
            ("missing-side", candidate.requested_quantity, "", "side"),
            ("opposite-side", candidate.requested_quantity, "SELL", "side")):
        with pytest.raises(RecoveryRequired, match=message):
            leases.prepare_command(
                token, kind="place_order",
                target_id=candidate.target_position_request_id,
                idempotency_key=key, request_digest="d" * 64,
                requested_qty=quantity, requested_side=side,
                capital_reservation_id=reservation_id)
    command = leases.prepare_command(
        token, kind="place_order", target_id=candidate.target_position_request_id,
        idempotency_key="exact-reservation", request_digest="c" * 64,
        requested_qty=candidate.requested_quantity, requested_side="BUY",
        capital_reservation_id=reservation_id,
    )
    with sessions() as session:
        reservation = session.get(CapitalReservationRecord, reservation_id)
        assert (reservation.state, reservation.command_id, reservation.revision) == (
            "submission_pending", command.command_id, 1)
        events = list(session.scalars(select(CapitalReservationEventRecord).where(
            CapitalReservationEventRecord.reservation_id == reservation_id).order_by(
                CapitalReservationEventRecord.revision)))
        assert [(row.revision, row.to_state) for row in events] == [
            (0, "held"), (1, "submission_pending")]


@pytest.mark.parametrize(
    ("candidate_index", "invalid_quantity"),
    ((1, 2.0), (0, True)),
)
def test_reserved_command_quantity_requires_exact_positive_int_before_effects(
        admission_store, candidate_index, invalid_quantity):
    _engine, sessions, leases, token = admission_store
    candidate = _candidate(candidate_index, cost=40_000)
    _seed_candidates(sessions, (candidate,))
    result = _admit(sessions, leases, token, _batch(token, (candidate,)))
    reservation_id = result.decisions[0].reservation_id
    outbox = execution_outbox()
    with sessions() as session:
        before = (
            session.scalar(select(func.count()).select_from(AccountExecutionCommand)),
            session.scalar(select(func.count()).select_from(
                CapitalReservationEventRecord)),
            session.get(
                CapitalReservationHead,
                (OWNER, ACCOUNT, "paper", "INR"),
            ).revision,
            session.scalar(select(func.count()).select_from(outbox.models.Event)),
        )
    with pytest.raises(RecoveryRequired, match="quantity"):
        leases.prepare_command(
            token,
            kind="place_order",
            target_id=candidate.target_position_request_id,
            idempotency_key=f"invalid-reserved-{type(invalid_quantity).__name__}",
            request_digest="8" * 64,
            requested_qty=invalid_quantity,
            requested_side="BUY",
            capital_reservation_id=reservation_id,
        )
    with sessions() as session:
        reservation = session.get(CapitalReservationRecord, reservation_id)
        after = (
            session.scalar(select(func.count()).select_from(AccountExecutionCommand)),
            session.scalar(select(func.count()).select_from(
                CapitalReservationEventRecord)),
            session.get(
                CapitalReservationHead,
                (OWNER, ACCOUNT, "paper", "INR"),
            ).revision,
            session.scalar(select(func.count()).select_from(outbox.models.Event)),
        )
        assert (reservation.state, reservation.command_id, reservation.revision) == (
            "held", None, 0)
    assert after == before


def test_unreserved_v1_command_quantity_behavior_is_unchanged(admission_store):
    _engine, _sessions, leases, token = admission_store
    command = leases.prepare_command(
        token,
        kind="place_order",
        target_id="legacy-unreserved-target",
        idempotency_key="legacy-unreserved-float",
        request_digest="a" * 64,
        requested_qty=2.0,
        requested_side="BUY",
    )
    assert command.requested_qty == 2.0


def test_short_reservation_requires_sell_side(admission_store):
    _engine, sessions, leases, token = admission_store
    candidate = dataclasses.replace(
        _candidate(1, cost=40_000), direction="SHORT", requested_quantity=-2)
    _seed_candidates(sessions, (candidate,))
    result = _admit(sessions, leases, token, _batch(token, (candidate,)))
    reservation_id = result.decisions[0].reservation_id
    with pytest.raises(RecoveryRequired, match="side"):
        leases.prepare_command(
            token, kind="place_order", target_id=candidate.target_position_request_id,
            idempotency_key="short-buy", request_digest="e" * 64,
            requested_qty=2, requested_side="BUY",
            capital_reservation_id=reservation_id)
    command = leases.prepare_command(
        token, kind="place_order", target_id=candidate.target_position_request_id,
        idempotency_key="short-sell", request_digest="f" * 64,
        requested_qty=2, requested_side="SELL",
        capital_reservation_id=reservation_id)
    assert command.requested_side == "SELL"
