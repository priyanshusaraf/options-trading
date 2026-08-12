from __future__ import annotations

import concurrent.futures
import datetime as dt

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    AccountExecutionCommand, AccountExecutionLease, Base, BrokerAccount, CapitalState, Deployment,
)
from app.execution.leases import (
    AmbiguousBrokerOutcome, FencedBrokerGateway, FencedTransportProxy, LeaseRepository,
    LeaseUnavailable, RecoveryRequired, StaleLease,
    validate_recovery_snapshot,
)
from app.core.execution_book import capital_for_book


@pytest.fixture()
def lease_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'leases.db'}", future=True,
                           connect_args={"check_same_thread": False, "timeout": 5})
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sessions.begin() as session:
        session.add_all([
            BrokerAccount(broker_account_id="account-a", owner_id="tenant-a", broker="kite",
                          external_account_id="ext-a", display_name="A"),
            BrokerAccount(broker_account_id="account-b", owner_id="tenant-a", broker="kite",
                          external_account_id="ext-b", display_name="B"),
        ])
        session.add(Deployment(id=1, owner_id="tenant-a", broker_account_id="account-a",
                               name="default", armed=False))
    yield LeaseRepository(sessions), sessions
    engine.dispose()


def _claim(repo, worker):
    return repo.claim(owner_id="tenant-a", broker_account_id="account-a",
                      cell_id=f"cell-{worker}", worker_id=f"boot-{worker}")


def test_exact_account_claim_race_has_one_winner(lease_store):
    repo, _ = lease_store
    def attempt(worker):
        try:
            return _claim(repo, worker)
        except LeaseUnavailable as exc:
            return exc
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (1, 2)))
    assert sum(hasattr(result, "fence_epoch") for result in results) == 1
    assert sum(isinstance(result, LeaseUnavailable) for result in results) == 1


def test_release_and_takeover_increment_epoch_and_fence_old_writer(lease_store):
    repo, _ = lease_store
    first = _claim(repo, 1)
    repo.activate(first, reconciliation_evidence="broker and journal empty")
    repo.release(first)
    second = _claim(repo, 2)
    assert second.fence_epoch == first.fence_epoch + 1
    with pytest.raises(StaleLease):
        repo.heartbeat(first)


def test_stale_token_cannot_flush_money_state(lease_store):
    repo, sessions = lease_store
    old = _claim(repo, 1)
    with sessions() as stale_session:
        repo.bind_money_session(stale_session, old)
        repo.release(old)
        _claim(repo, 2)
        stale_session.add(CapitalState(
            broker_account_id="account-a", book="live", initial_capital=100,
            cash=100, realized_pnl=0, updated_at=dt.datetime.now()))
        with pytest.raises(StaleLease):
            stale_session.commit()


def test_stale_token_cannot_bootstrap_capital(lease_store):
    repo, sessions = lease_store
    stale = _claim(repo, 1)
    repo.release(stale)
    _claim(repo, 2)
    with sessions() as session:
        repo.bind_money_session(session, stale)
        with pytest.raises(StaleLease):
            capital_for_book(session, "live", broker_account_id="account-a")
    with sessions() as session:
        assert session.get(CapitalState, ("account-a", "live")) is None


def test_recovery_must_finish_before_broker_command(lease_store):
    repo, _ = lease_store
    token = _claim(repo, 1)
    gateway = FencedBrokerGateway(repo, token)
    calls = []
    with pytest.raises(RecoveryRequired):
        gateway.call(kind="place_order", target_id="intent-1",
                     operation=lambda: calls.append("wire"))
    assert calls == []


def test_every_current_transport_shape_calls_once_and_stale_calls_zero(lease_store):
    repo, _ = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="reconciled")
    gateway = FencedBrokerGateway(repo, token)
    calls = []
    for kind in ("place_order", "cancel_order", "place_protective",
                 "cancel_protective", "modify_protective"):
        assert gateway.call(kind=kind, target_id=kind,
                            operation=lambda k=kind: calls.append(k) or f"ack-{k}") == f"ack-{kind}"
    assert calls == ["place_order", "cancel_order", "place_protective",
                     "cancel_protective", "modify_protective"]
    repo.release(token)
    with pytest.raises(StaleLease):
        gateway.call(kind="place_order", target_id="late", operation=lambda: calls.append("late"))
    assert "late" not in calls


def test_two_legitimate_identical_calls_get_distinct_command_identities(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="reconciled")
    gateway = FencedBrokerGateway(repo, token)
    assert gateway.call(kind="cancel_order", target_id="order-1", operation=lambda: "ok") == "ok"
    assert gateway.call(kind="cancel_order", target_id="order-1", operation=lambda: "ok") == "ok"
    with sessions() as session:
        rows = list(session.scalars(select(AccountExecutionCommand).where(
            AccountExecutionCommand.kind == "cancel_order")))
    assert len(rows) == 2
    assert rows[0].idempotency_key != rows[1].idempotency_key


def test_network_exception_is_sent_unknown_and_never_retried(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="reconciled")
    gateway = FencedBrokerGateway(repo, token)
    calls = []

    def uncertain():
        calls.append("wire")
        raise OSError("lost acknowledgement")

    with pytest.raises(AmbiguousBrokerOutcome):
        gateway.call(kind="cancel_order", target_id="order-1", operation=uncertain)
    with pytest.raises(StaleLease):
        gateway.call(kind="cancel_order", target_id="order-1", operation=uncertain)
    assert calls == ["wire"]
    with sessions() as session:
        row = session.scalar(select(AccountExecutionCommand))
        assert row.state == "sent_unknown"
    repo.release(token)
    next_token = _claim(repo, 2)
    with pytest.raises(RecoveryRequired):
        repo.activate(next_token, reconciliation_evidence="not actually resolved")


def test_ack_before_evidence_failure_is_ambiguous_and_blocks_activation(lease_store, monkeypatch):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="reconciled")
    gateway = FencedBrokerGateway(repo, token)
    original = repo.transition_command

    def lose_ack(*args, **kwargs):
        if kwargs.get("to_state") == "acknowledged":
            raise StaleLease("failpoint after broker ack")
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "transition_command", lose_ack)
    calls = []
    with pytest.raises(AmbiguousBrokerOutcome):
        gateway.call(kind="place_order", target_id="intent-x",
                     operation=lambda: calls.append("wire") or "broker-7")
    assert calls == ["wire"]
    with sessions() as session:
        assert session.scalar(select(AccountExecutionCommand.state)) == "sent_unknown"


def test_wire_failure_plus_lost_unknown_transition_is_still_ambiguous(lease_store, monkeypatch):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="reconciled")
    original = repo.transition_command

    def lose_transition(*args, **kwargs):
        if kwargs.get("to_state") == "sent_unknown":
            raise StaleLease("lease lost after wire exception")
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "transition_command", lose_transition)
    with pytest.raises(AmbiguousBrokerOutcome):
        FencedBrokerGateway(repo, token).call(
            kind="place_order", target_id="intent",
            operation=lambda: (_ for _ in ()).throw(OSError("wire uncertain")))
    with sessions() as session:
        assert session.scalar(select(AccountExecutionCommand.state)) == "sent_unknown"


def test_unrelated_fenced_commit_does_not_resolve_acknowledged_command(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="reconciled")
    with sessions() as money:
        repo.bind_money_session(money, token)
        gateway = FencedBrokerGateway(repo, token)
        gateway.call(kind="place_order", target_id="intent", operation=lambda: "broker-1")
        with sessions() as observer:
            assert observer.scalar(select(AccountExecutionCommand.state)) == "acknowledged"
        money.add(CapitalState(
            broker_account_id="account-a", book="live", initial_capital=100,
            cash=100, realized_pnl=0, updated_at=dt.datetime.now()))
        money.commit()
    with sessions() as observer:
        assert observer.scalar(select(AccountExecutionCommand.state)) == "acknowledged"


def test_late_old_epoch_response_cannot_commit_core_money_write(lease_store):
    repo, sessions = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="reconciled")
    with sessions.begin() as seed:
        seed.add(CapitalState(
            broker_account_id="account-a", book="live", initial_capital=100,
            cash=100, realized_pnl=0, updated_at=dt.datetime.now()))
    stale_money = sessions()
    repo.bind_money_session(stale_money, old)

    def wire_then_takeover():
        repo.release(old)
        _claim(repo, 2)
        return "late-broker-ack"

    with pytest.raises(AmbiguousBrokerOutcome):
        FencedBrokerGateway(repo, old).call(
            kind="place_order", target_id="late", operation=wire_then_takeover)
    with pytest.raises(StaleLease):
        stale_money.execute(update(CapitalState).where(
            CapitalState.broker_account_id == "account-a").values(cash=0))
    stale_money.rollback()
    stale_money.close()
    with sessions() as observer:
        assert observer.scalar(select(CapitalState.cash)) == 100
        assert observer.scalar(select(AccountExecutionCommand.state)) == "prepared"


def test_late_prior_epoch_effect_blocks_entries_until_explicit_resolution(lease_store):
    repo, sessions = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="reconciled")
    digest = "a" * 64
    command = repo.prepare_command(old, kind="place_order", target_id="intent-late",
                                   idempotency_key="late", request_digest=digest)
    repo.release(old)
    new = _claim(repo, 2)
    with pytest.raises(RecoveryRequired):
        repo.activate(new, reconciliation_evidence="orderbook read")
    repo.block(new, "late prior-epoch order may be working")
    assert repo.status(owner_id="tenant-a", broker_account_id="account-a")["blocked"] is True
    with sessions.begin() as session:
        session.execute(update(AccountExecutionCommand).where(
            AccountExecutionCommand.command_id == command.command_id).values(
                state="resolved", resolved_at=dt.datetime.now(), updated_at=dt.datetime.now()))


def test_different_accounts_progress_independently(lease_store):
    repo, _ = lease_store
    one = _claim(repo, 1)
    two = repo.claim(owner_id="tenant-a", broker_account_id="account-b",
                     cell_id="cell-b", worker_id="boot-b")
    assert one.broker_account_id != two.broker_account_id


def test_database_refuses_cross_owner_lease_even_for_existing_account(lease_store):
    _, sessions = lease_store
    with sessions() as session:
        session.add(AccountExecutionLease(
            owner_id="forged-owner", broker_account_id="account-a", fence_epoch=1,
            state="recovering", cell_id="cell", worker_id="worker",
            claimed_at=dt.datetime.now(), heartbeat_at=dt.datetime.now(),
            expires_at=dt.datetime.now() + dt.timedelta(seconds=30),
            recovery_started_at=dt.datetime.now(), desired_state="disabled",
            updated_at=dt.datetime.now()))
        with pytest.raises(Exception):
            session.commit()


def test_control_is_claimed_once_and_survives_takeover(lease_store):
    repo, _ = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="reconciled")
    accepted = repo.request_control(
        owner_id="tenant-a", broker_account_id="account-a", kind="kill",
        idempotency_key="kill-once", actor_user_id="operator")
    repo.release(old)
    new = _claim(repo, 2)

    def claim():
        return repo.claim_controls(new, limit=1)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    winners = [row for rows in results for row in rows]
    assert [row.command_id for row in winners] == [accepted["request_id"]]
    assert winners[0].fence_epoch == new.fence_epoch


def test_idempotent_control_request_returns_same_identity(lease_store):
    repo, _ = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="reconciled")
    first = repo.request_control(owner_id="tenant-a", broker_account_id="account-a",
                                 kind="disarm", idempotency_key="same", actor_user_id="u")
    second = repo.request_control(owner_id="tenant-a", broker_account_id="account-a",
                                  kind="disarm", idempotency_key="same", actor_user_id="u")
    assert second["request_id"] == first["request_id"]


def test_control_idempotency_key_rejects_cross_kind_collision(lease_store):
    repo, _ = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a",
                         kind="arm", idempotency_key="same-key", actor_user_id="u")
    with pytest.raises(ValueError, match="collision"):
        repo.request_control(owner_id="tenant-a", broker_account_id="account-a",
                             kind="disarm", idempotency_key="same-key", actor_user_id="u")


def test_release_clears_effective_arm_state(lease_store):
    repo, _ = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a",
                         kind="arm", idempotency_key="arm-once", actor_user_id="u")
    command = repo.claim_controls(token)[0]
    repo.complete_control(token, command.command_id, success=True)
    assert repo.status(owner_id="tenant-a", broker_account_id="account-a")["effective_state"] == "armed"
    repo.release(token)
    status = repo.status(owner_id="tenant-a", broker_account_id="account-a")
    assert status["desired_state"] == status["effective_state"] == "disabled"


def test_control_claim_uses_current_monotonic_revision_not_equal_timestamp_uuid_order(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a", kind="arm",
                         idempotency_key="rev-1", actor_user_id="u")
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a", kind="disarm",
                         idempotency_key="rev-2", actor_user_id="u")
    same_time = dt.datetime(2026, 1, 1)
    with sessions.begin() as session:
        arm = session.scalar(select(AccountExecutionCommand).where(
            AccountExecutionCommand.kind == "control_arm"))
        disarm = session.scalar(select(AccountExecutionCommand).where(
            AccountExecutionCommand.kind == "control_disarm"))
        arm.created_at = disarm.created_at = same_time
        arm.command_id = "z" * 32
        disarm.command_id = "a" * 32
    claimed = repo.claim_controls(token)
    assert [(row.kind, row.expected_revision) for row in claimed] == [("control_disarm", 2)]
    repo.complete_control(token, claimed[0].command_id, success=True)
    status = repo.status(owner_id="tenant-a", broker_account_id="account-a")
    assert status["desired_state"] == status["effective_state"] == "disabled"
    with sessions() as session:
        stale_arm = session.scalar(select(AccountExecutionCommand).where(
            AccountExecutionCommand.kind == "control_arm"))
        assert stale_arm.state == "cancelled"


def test_control_claim_refuses_revision_gap(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    accepted = repo.request_control(owner_id="tenant-a", broker_account_id="account-a",
                                    kind="disarm", idempotency_key="gap", actor_user_id="u")
    with sessions.begin() as session:
        session.execute(update(AccountExecutionCommand).where(
            AccountExecutionCommand.command_id == accepted["request_id"]
        ).values(expected_revision=3))
    with pytest.raises(RecoveryRequired, match="revision gap"):
        repo.claim_controls(token)


def test_superseded_processing_control_cannot_project_stale_effective_state(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a", kind="arm",
                         idempotency_key="arm-processing", actor_user_id="u")
    arm = repo.claim_controls(token)[0]
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a", kind="disarm",
                         idempotency_key="newer-disarm", actor_user_id="u")
    with pytest.raises(StaleLease, match="superseded"):
        repo.complete_control(token, arm.command_id, success=True)
    status = repo.status(owner_id="tenant-a", broker_account_id="account-a")
    assert status["desired_state"] == status["effective_state"] == "disabled"
    with sessions() as session:
        assert session.get(AccountExecutionCommand, arm.command_id).state == "cancelled"


def test_atomic_arm_projection_refuses_superseded_control_without_deployment_drift(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a", kind="arm",
                         idempotency_key="atomic-arm", actor_user_id="u")
    arm = repo.claim_controls(token)[0]
    repo.request_control(owner_id="tenant-a", broker_account_id="account-a", kind="disarm",
                         idempotency_key="atomic-disarm", actor_user_id="u")
    with pytest.raises(StaleLease, match="superseded"):
        repo.complete_control_with_projection(
            token, arm.command_id, deployment_id=1, armed=True)
    with sessions() as session:
        assert session.get(Deployment, 1).armed is False


def test_protective_proxy_persists_exact_wire_tag_and_target(lease_store):
    repo, sessions = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")

    class Transport:
        def place_protective_stop(self, kind, **kwargs):
            return "stop-1"

    proxy = FencedTransportProxy(
        Transport(), FencedBrokerGateway(repo, token),
        {"place_protective_stop": "place_protective"})
    proxy.place_protective_stop("resting", tradingsymbol="NIFTY", tag="pt-bot",
                                qty=10, side="SELL", trigger_price=100)
    with sessions() as session:
        command = session.scalar(select(AccountExecutionCommand))
        assert command.broker_tag == "pt-bot"
        assert command.target_id == "pt-bot:NIFTY"
        assert (command.requested_qty, command.requested_side,
                command.requested_trigger) == (10, "SELL", 100)


@pytest.mark.parametrize("accounts,protection", [
    (None, {}),
    ([], {"stop": []}),
    ([{"tradingsymbol": "NIFTY", "quantity": 10}],
     {"stop": [{"id": "S1", "qty": 10, "side": "SELL", "trigger_price": 100,
                "status": "dead"}]}),
    ([{"tradingsymbol": "NIFTY", "quantity": -10}],
     {"stop": [{"id": "S1", "qty": 10, "side": "SELL", "trigger_price": 100}]}),
    ([{"tradingsymbol": "NIFTY", "quantity": 20}],
     {"stop": [{"id": "S1", "qty": 10, "side": "SELL", "trigger_price": 100}]}),
    ([{"tradingsymbol": "NIFTY", "quantity": 5}], {"stop": []}),
    ([{"tradingsymbol": "NIFTY", "quantity": 10}], {"stop": []}),
    ([{"tradingsymbol": "NIFTY", "quantity": 10}],
     {"stop": [{"id": "S1", "qty": 5, "side": "SELL", "trigger_price": 100}]}),
    ([{"tradingsymbol": "NIFTY", "quantity": 10}],
     {"stop": [{"id": "S1", "qty": 20, "side": "SELL", "trigger_price": 100}]}),
    ([{"tradingsymbol": "NIFTY", "quantity": 10}],
     {"stop": [{"id": "S1", "qty": 10, "side": "BUY", "trigger_price": 100}]}),
    ([{"tradingsymbol": "NIFTY", "quantity": 10}],
     {"stop": [{"id": "S1", "qty": 10, "side": "SELL", "trigger_price": 50}]}),
])
def test_recovery_snapshot_refuses_unreadable_or_mismatched_broker_state(accounts, protection):
    position = type("P", (), {"tradingsymbol": "NIFTY", "qty": 10,
                              "direction": "LONG", "segment": "options",
                              "stop_price": 100, "protective_id": "S1"})()
    with pytest.raises(RecoveryRequired):
        validate_recovery_snapshot([position], accounts, protection,
                                   lambda _: "stop", lambda p: p.protective_id)


def test_recovery_snapshot_accepts_exact_position_and_protection():
    position = type("P", (), {"tradingsymbol": "NIFTY", "qty": 10,
                              "direction": "LONG", "segment": "options",
                              "stop_price": 100, "protective_id": "S1"})()
    validate_recovery_snapshot(
        [position], [{"tradingsymbol": "NIFTY", "quantity": 10}],
        {"stop": [{"id": "S1", "qty": 10, "side": "SELL", "trigger_price": 100}]},
        lambda _: "stop", lambda p: p.protective_id)


def test_recovery_snapshot_requires_durable_protective_identity():
    position = type("P", (), {"tradingsymbol": "NIFTY", "qty": 10,
                              "direction": "LONG", "segment": "options",
                              "stop_price": 100, "protective_id": None})()
    with pytest.raises(RecoveryRequired, match="identity"):
        validate_recovery_snapshot(
            [position], [{"tradingsymbol": "NIFTY", "quantity": 10}], {"stop": []},
            lambda _: "stop", lambda p: p.protective_id)


@pytest.mark.parametrize("prior_state", ["prepared", "sent_unknown", "acknowledged"])
def test_new_epoch_can_reconcile_prior_command_then_activate(lease_store, prior_state):
    repo, sessions = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="clean")
    command = repo.prepare_command(old, kind="place_order", target_id="intent",
                                   idempotency_key=f"prior-{prior_state}", request_digest="a" * 64)
    with sessions.begin() as session:
        session.execute(update(AccountExecutionCommand).where(
            AccountExecutionCommand.command_id == command.command_id).values(state=prior_state))
    repo.release(old)
    new = _claim(repo, 2)
    repo.reconcile_prior_command(new, command.command_id, expected_state=prior_state,
                                 outcome="resolved", evidence_digest="b" * 64)
    repo.activate(new, reconciliation_evidence="prior effect reconciled")
    assert repo.status(owner_id="tenant-a", broker_account_id="account-a")["state"] == "active"


def test_new_epoch_can_block_prior_command_with_operator_visible_reason(lease_store):
    repo, _ = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="clean")
    command = repo.prepare_command(old, kind="modify_protective", target_id="stop-1",
                                   idempotency_key="prior-mismatch", request_digest="a" * 64)
    repo.release(old)
    new = _claim(repo, 2)
    repo.reconcile_prior_command(new, command.command_id, expected_state="prepared",
                                 outcome="blocked", evidence_digest="b" * 64)
    status = repo.status(owner_id="tenant-a", broker_account_id="account-a")
    assert status["state"] == "blocked"
    assert status["block_reason"] == "reconciliation discrepancy"
    with pytest.raises((RecoveryRequired, StaleLease)):
        repo.activate(new, reconciliation_evidence="must not activate")


def test_production_snapshot_reconciler_resolves_exact_prior_identity(lease_store):
    repo, _ = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="clean")
    command = repo.prepare_command(old, kind="modify_protective", target_id="stop-1",
                                   idempotency_key="snapshot-exact", request_digest="a" * 64,
                                   broker_tag="pt-bot")
    repo.release(old)
    new = _claim(repo, 2)
    repo.reconcile_prior_commands_from_snapshot(
        new, orders=[], protection=[{"id": "stop-1", "tag": "pt-bot"}])
    repo.activate(new, reconciliation_evidence="strict snapshot consumed prior command")
    assert repo.status(owner_id="tenant-a", broker_account_id="account-a")["state"] == "active"


def test_production_snapshot_reconciler_blocks_uncorrelated_prior_identity(lease_store):
    repo, _ = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="clean")
    repo.prepare_command(old, kind="modify_protective", target_id="stop-missing",
                         idempotency_key="snapshot-missing", request_digest="a" * 64)
    repo.release(old)
    new = _claim(repo, 2)
    with pytest.raises(RecoveryRequired, match="disagrees"):
        repo.reconcile_prior_commands_from_snapshot(new, orders=[], protection=[])
    assert repo.status(owner_id="tenant-a", broker_account_id="account-a")["state"] == "blocked"


@pytest.mark.parametrize("row", [
    {"id": "stop-1", "tag": "pt-bot", "qty": 5, "side": "SELL",
     "trigger_price": 100, "status": "live"},
    {"id": "stop-1", "tag": "pt-bot", "qty": 10, "side": "BUY",
     "trigger_price": 100, "status": "live"},
    {"id": "stop-1", "tag": "pt-bot", "qty": 10, "side": "SELL",
     "trigger_price": 50, "status": "live"},
    {"id": "stop-1", "tag": "pt-bot", "qty": 10, "side": "SELL",
     "trigger_price": 100, "status": "dead"},
])
def test_prior_protective_reconciliation_requires_exact_requested_fields(lease_store, row):
    repo, _ = lease_store
    old = _claim(repo, 1)
    repo.activate(old, reconciliation_evidence="clean")
    repo.prepare_command(old, kind="modify_protective", target_id="stop-1",
                         idempotency_key="detailed", request_digest="a" * 64,
                         broker_tag="pt-bot", requested_qty=10,
                         requested_side="SELL", requested_trigger=100)
    repo.release(old)
    new = _claim(repo, 2)
    with pytest.raises(RecoveryRequired):
        repo.reconcile_prior_commands_from_snapshot(new, orders=[], protection=[row])


def test_ambiguous_call_blocks_account_and_all_followup_wire(lease_store):
    repo, _ = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    gateway = FencedBrokerGateway(repo, token)
    with pytest.raises(AmbiguousBrokerOutcome):
        gateway.call(kind="modify_protective", target_id="stop",
                     operation=lambda: (_ for _ in ()).throw(OSError("unknown")))
    assert repo.status(owner_id="tenant-a", broker_account_id="account-a")["state"] == "blocked"
    calls = []
    with pytest.raises((StaleLease, RecoveryRequired)):
        gateway.call(kind="place_order", target_id="new", operation=lambda: calls.append(1))
    assert calls == []


def test_metrics_are_bounded_aggregate_without_identity_labels(lease_store):
    repo, _ = lease_store
    token = _claim(repo, 1)
    repo.activate(token, reconciliation_evidence="clean")
    metrics = repo.metrics()
    rendered = str(metrics)
    assert set(metrics) == {"transitions", "states", "sent_unknown_age_seconds",
                            "control_age_seconds", "recovery_age_seconds",
                            "reconciliation_discrepancy_count"}
    assert "tenant-a" not in rendered and "account-a" not in rendered and "boot-1" not in rendered
