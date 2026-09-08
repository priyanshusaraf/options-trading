"""Closure regressions for typed, transaction-coupled projection events."""
from __future__ import annotations

import datetime as dt
import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.backtest import repository as backtests
from app.core import deployments
from app.db.models import (
    Base,
    BacktestRun,
    BrokerAccount,
    Deployment,
    ExecutionIntent,
)
from app.engine.execution_lifecycle import ExecutionLifecycleStore, NewExecutionIntent
from app.events.planes import execution_outbox


@pytest.fixture
def execution_store():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    with sm.begin() as session:
        session.add(BrokerAccount(
            broker_account_id="account-a", owner_id="owner-a", broker="kite",
            external_account_id="external-a", display_name="A",
        ))
        session.add(Deployment(
            id=1, owner_id="owner-a", broker_account_id="account-a",
            name="fixture", status="active", armed=False,
        ))
    try:
        yield sm
    finally:
        engine.dispose()


def _events(session):
    return list(session.scalars(select(execution_outbox().models.Event).order_by(
        execution_outbox().models.Event.plane_offset)))


def test_backtest_enqueue_and_rollback_keep_state_and_event_atomic(
        execution_store, admitted_backtest_receipt):
    """Removing the typed append must expose a committed run without its refresh fact."""
    with execution_store() as session:
        identity = admitted_backtest_receipt(session, owner_id="owner-a")
        run = backtests.enqueue_run(
            session, owner_id="owner-a", scope="liquid", intervals="day",
            capital=10_000, total=1, now=dt.datetime(2026, 8, 13), **identity,
        )
        run_id = run.id
        session.rollback()
    with execution_store() as session:
        assert session.get(BacktestRun, run_id) is None
        assert _events(session) == []

    with execution_store() as session:
        identity = admitted_backtest_receipt(session, owner_id="owner-a")
    with execution_store.begin() as session:
        run = backtests.enqueue_run(
            session, owner_id="owner-a", scope="liquid", intervals="day",
            capital=10_000, total=1, now=dt.datetime(2026, 8, 13), **identity,
        )
        run_id = run.id
    with execution_store() as session:
        event = _events(session)[0]
        assert event.event_type == "execution.backtest.changed"
        assert (event.owner_id, event.broker_account_id) == ("owner-a", None)
        assert json.loads(event.payload_json) == {
            "projection": "backtest_runs", "state": "pending",
        }
        assert event.aggregate_id == str(run_id)


def test_backtest_cancel_and_terminal_each_emit_one_typed_change(
        execution_store, admitted_backtest_receipt):
    """A cancel or terminal transition without a new sequence leaves replicas stale."""
    now = dt.datetime(2026, 8, 13)
    with execution_store() as session:
        identity = admitted_backtest_receipt(session, owner_id="owner-a")
    with execution_store.begin() as session:
        run = backtests.enqueue_run(
            session, owner_id="owner-a", scope="liquid", intervals="day",
            capital=10_000, total=1, now=now, **identity,
        )
        pending_id = run.id
    with execution_store.begin() as session:
        assert backtests.request_cancel(
            session, owner_id="owner-a", run_id=pending_id, now=now,
        )

    with execution_store() as session:
        identity = admitted_backtest_receipt(session, owner_id="owner-a")
    with execution_store.begin() as session:
        run = backtests.enqueue_run(
            session, owner_id="owner-a", scope="liquid", intervals="day",
            capital=10_000, total=1, now=now, **identity,
        )
        terminal_id = run.id
        claimed = backtests.claim_run(
            session, owner_id="owner-a", run_id=terminal_id,
            claimed_by="worker", now=now, lease_seconds=30,
        )
        assert claimed is not None
        token = claimed.claim_token
    with execution_store.begin() as session:
        assert backtests.complete_claim(
            session, owner_id="owner-a", run_id=terminal_id,
            claim_token=token, status="done", now=now + dt.timedelta(seconds=1),
        )

    with execution_store() as session:
        states = [json.loads(event.payload_json)["state"] for event in _events(session)]
        assert states == ["pending", "cancelled", "pending", "done"]


def test_deployment_commit_owner_emits_account_scoped_invalidation(
        execution_store, admitted_entry_identity):
    """Deleting the deployment producer must leave another API replica unaware."""
    with execution_store() as session:
        identity = admitted_entry_identity(session, owner_id="owner-a")
    with execution_store.begin() as session:
        row = deployments.create_deployment(
            session, "alpha", owner_id="owner-a", broker_account_id="account-a",
            strategy_key=identity["strategy_key"],
            strategy_version=identity["strategy_version"],
            graph_address=identity["graph_address"],
            admission_address=identity["admission_address"],
            attribution_state=identity["attribution_state"],
        )
        deployment_id = row.id
    with execution_store() as session:
        event = _events(session)[0]
        assert event.event_type == "execution.deployment.changed"
        assert (event.owner_id, event.broker_account_id) == ("owner-a", "account-a")
        assert event.aggregate_id == str(deployment_id)
        assert json.loads(event.payload_json) == {
            "projection": "deployments", "state": "draft",
        }


def test_deployment_mutation_identity_is_bounded_at_maximum_scope_lengths(execution_store):
    """Maximum durable identifiers must still fit the 128-byte producer contract."""
    owner_id = "o" * 64
    deployment_id = 9_223_372_036_854_775_807
    with execution_store.begin() as session:
        session.add(BrokerAccount(
            broker_account_id="account-long", owner_id=owner_id, broker="kite",
            external_account_id="external-long", display_name="Long",
        ))
        session.add(Deployment(
            id=deployment_id, owner_id=owner_id, broker_account_id="account-long",
            name="max-id", status="active", armed=False,
        ))

    with execution_store.begin() as session:
        deployments.set_status(
            session, deployment_id, "paused", owner_id=owner_id,
            broker_account_id="account-long",
        )

    with execution_store() as session:
        event = _events(session)[0]
        assert len(event.producer_key) <= 128
        assert event.aggregate_id == str(deployment_id)


def test_lifecycle_intent_commit_emits_exact_account_projection(execution_store):
    """An intent commit without its lifecycle fact hides execution ambiguity on replicas."""
    with execution_store() as session:
        store = ExecutionLifecycleStore(
            session, owner_id="owner-a", broker_account_id="account-a",
        )
        row = store.create_intent(NewExecutionIntent(
            deployment_id=1, broker="kite", account_scope="main",
            connection_scope="orders", intent="ENTRY", instrument_key="NIFTY",
            tradingsymbol="NIFTY26AUG", exchange="NFO", side="BUY", product="NRML",
            order_type="MARKET", requested_qty=25, limit_price=None,
            decision_price=100.0, signal_at=dt.datetime(2026, 8, 13),
            strategy_key="trend", strategy_version="v1", owner_id="owner-a",
            broker_account_id="account-a", admission_address="sha256:" + "a" * 64,
        ), {}, dt.datetime(2026, 8, 13))
        intent_id = row.client_intent_id
    with execution_store() as session:
        assert session.get(ExecutionIntent, intent_id) is not None
        event = _events(session)[0]
        assert event.event_type == "execution.lifecycle.changed"
        assert event.aggregate_id == intent_id
        assert json.loads(event.payload_json) == {
            "projection": "execution_lifecycle", "state": "intent_created",
        }


def test_typed_producer_retry_does_not_create_duplicate_event(execution_store):
    """Retrying one immutable mutation identity must not create an event storm."""
    from app.events.producers import append_execution_change

    with execution_store.begin() as session:
        first = append_execution_change(
            session, owner_id="owner-a", broker_account_id="account-a",
            aggregate_type="position", aggregate_id="position-1",
            event_type="execution.position.changed", projection="positions",
            producer_key="position:position-1:opened", facts={"state": "opened"},
        )
        second = append_execution_change(
            session, owner_id="owner-a", broker_account_id="account-a",
            aggregate_type="position", aggregate_id="position-1",
            event_type="execution.position.changed", projection="positions",
            producer_key="position:position-1:opened", facts={"state": "opened"},
        )
        assert first == second
    with execution_store() as session:
        assert session.scalar(select(func.count()).select_from(
            execution_outbox().models.Event)) == 1


def test_money_commit_owner_emits_one_compound_position_trade_capital_change(execution_store):
    """Removing the broker's explicit commit-owner fact must hide a booked fill."""
    from app.engine.broker import PaperBroker

    with execution_store.begin() as session:
        broker = PaperBroker.__new__(PaperBroker)
        broker.s = session
        broker.owner_id = "owner-a"
        broker.broker_account_id = "account-a"
        broker._append_money_projection(
            state="position_opened", aggregate_id="position-42",
        )
    with execution_store() as session:
        event = _events(session)[0]
        assert event.event_type == "execution.money.changed"
        assert json.loads(event.payload_json) == {
            "projection": "money_book", "state": "position_opened",
        }
