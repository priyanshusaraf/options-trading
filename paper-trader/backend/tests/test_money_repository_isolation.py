"""Two-tenant proofs for account-bound money repositories.

Each test exercises a real query or write.  Removing either the owner or durable broker-account
predicate must make at least one assertion fail; constructor-signature checks alone are not a
tenancy proof.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.core import deployments
from app.db.models import (
    BrokerAccount,
    BrokerConnection,
    Deployment,
    EquitySnapshot,
    ExecutionIntent,
    ExecutionOrderEvent,
    IrPaperDeployment,
    IrShadowDeployment,
    IrShadowDivergence,
    OrderJournal,
    Organization,
    Position,
    SignalEvent,
    Trade,
)
from app.db.session import SessionLocal, init_db
from app.engine import analytics
from app.engine.execution_lifecycle import (
    ExecutionLifecycleStore,
    NewExecutionEvent,
    NewExecutionIntent,
)
from app.engine.runner import EngineRunner


OWNER_A = "org-a"
OWNER_B = "org-b"
ACCOUNT_A = "account.a"
ACCOUNT_B = "account.b"
NOW = dt.datetime(2026, 8, 11, 10, 0)


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)
    with SessionLocal() as session:
        for owner, account in ((OWNER_A, ACCOUNT_A), (OWNER_B, ACCOUNT_B)):
            session.add(Organization(organization_id=owner, name=owner))
            session.add(BrokerAccount(
                broker_account_id=account,
                owner_id=owner,
                broker="kite",
                external_account_id="same-external-account",
                display_name=account,
            ))
        session.commit()
    yield


ACCOUNT_MONEY_MODELS = (
    Position,
    Trade,
    EquitySnapshot,
    OrderJournal,
    SignalEvent,
    ExecutionIntent,
    ExecutionOrderEvent,
    BrokerConnection,
    IrPaperDeployment,
    IrShadowDeployment,
    IrShadowDivergence,
)


@pytest.mark.parametrize("model", ACCOUNT_MONEY_MODELS)
def test_new_account_money_rows_require_explicit_tenant_scope(model):
    """Only the migration may backfill legacy scope; ordinary ORM writes must supply it."""
    table = model.__table__
    for name in ("owner_id", "broker_account_id"):
        column = table.c[name]
        assert column.default is None, f"{table.name}.{name} still has a Python legacy default"
        assert column.server_default is None, f"{table.name}.{name} still has a server legacy default"

    with SessionLocal() as session:
        values = {"client_intent_id": "unscoped-intent"} if model is ExecutionIntent else {}
        session.add(model(**values))
        with pytest.raises(IntegrityError):
            session.flush()


@pytest.mark.parametrize("model", ACCOUNT_MONEY_MODELS)
def test_account_money_models_have_non_nullable_durable_account_and_tenant_index(model):
    """Catches an omitted column, nullable scope, missing MONEY-plane FK, or scan index."""
    table = model.__table__
    account = table.c.broker_account_id
    assert account.nullable is False
    assert any(
        fk.column.table.name == "broker_accounts"
        and fk.column.name == "broker_account_id"
        for fk in account.foreign_keys
    )
    assert any(
        tuple(column.name for column in index.columns) == ("owner_id", "broker_account_id")
        for index in table.indexes
    )


def test_same_deployment_name_is_local_to_owner_and_account_mutations_are_isolated():
    """Catches global name uniqueness or id-only getter/arm/disarm predicates."""
    with SessionLocal() as session:
        a = deployments.create_deployment(
            session, "momentum", owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
            status=deployments.ACTIVE,
        )
        b = deployments.create_deployment(
            session, "momentum", owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
            status=deployments.ACTIVE,
        )
        session.commit()

        assert deployments.get_deployment(
            session, a.id, owner_id=OWNER_B, broker_account_id=ACCOUNT_B) is None
        assert deployments.get_by_name(
            session, "momentum", owner_id=OWNER_A, broker_account_id=ACCOUNT_A).id == a.id
        assert deployments.get_by_name(
            session, "momentum", owner_id=OWNER_B, broker_account_id=ACCOUNT_B).id == b.id

        deployments.set_armed(
            session, a.id, True, owner_id=OWNER_A, broker_account_id=ACCOUNT_A)
        deployments.set_armed(
            session, b.id, True, owner_id=OWNER_B, broker_account_id=ACCOUNT_B)
        assert deployments.disarm_all(
            session, owner_id=OWNER_B, broker_account_id=ACCOUNT_B) == 1
        session.commit()

        assert session.get(Deployment, a.id).armed is True
        assert session.get(Deployment, b.id).armed is False
        assert [row.id for row in deployments.all_deployments(
            session, owner_id=OWNER_A, broker_account_id=ACCOUNT_A)] == [a.id]


def _intent(owner_id: str, broker_account_id: str, deployment_id: int) -> NewExecutionIntent:
    return NewExecutionIntent(
        deployment_id=deployment_id,
        broker="kite",
        account_scope="same-external-account",
        connection_scope="kite:same",
        intent="ENTRY",
        instrument_key="NSE_EQ|INE002A01018",
        tradingsymbol="RELIANCE",
        exchange="NSE",
        side="BUY",
        product="MIS",
        order_type="MARKET",
        requested_qty=10,
        limit_price=None,
        decision_price=100.0,
        signal_at=NOW,
        strategy_key="momentum",
        strategy_version="v1",
        admission_address="sha256:" + "a" * 64,
        owner_id=owner_id,
        broker_account_id=broker_account_id,
    )


def test_lifecycle_guessed_id_and_recovery_are_owner_and_account_scoped():
    """Catches id-only state reads and recovery keyed only by external account labels."""
    with SessionLocal() as session:
        dep_a = deployments.create_deployment(
            session, "a", owner_id=OWNER_A, broker_account_id=ACCOUNT_A)
        dep_b = deployments.create_deployment(
            session, "b", owner_id=OWNER_B, broker_account_id=ACCOUNT_B)
        session.commit()

        store_a = ExecutionLifecycleStore(
            session, owner_id=OWNER_A, broker_account_id=ACCOUNT_A)
        row_a = store_a.create_intent(_intent(OWNER_A, ACCOUNT_A, dep_a.id), {}, NOW)
        store_a.append_event(row_a.client_intent_id, NewExecutionEvent(
            source="engine", source_event_id="submit", kind="SUBMIT_STARTED",
            broker_order_id=None, broker_status="", cumulative_filled_qty=0,
            avg_price=0.0,
        ), NOW)

        store_b = ExecutionLifecycleStore(
            session, owner_id=OWNER_B, broker_account_id=ACCOUNT_B)
        with pytest.raises(LookupError, match="unknown execution intent"):
            store_b.state_for(row_a.client_intent_id)
        with pytest.raises(LookupError, match="unknown execution intent"):
            store_b.append_event(row_a.client_intent_id, NewExecutionEvent(
                source="broker", source_event_id="probe", kind="ACKNOWLEDGED",
                broker_order_id="other", broker_status="OPEN", cumulative_filled_qty=0,
                avg_price=0.0,
            ), NOW)
        assert store_b.unresolved_entries(
            dep_b.id, "same-external-account", "kite:same", broker="kite") == []

        assert session.scalar(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.source_event_id == "probe")) is None


def _trade(owner_id: str, broker_account_id: str, deployment_id: int, net: float) -> Trade:
    return Trade(
        owner_id=owner_id, broker_account_id=broker_account_id,
        deployment_id=deployment_id, instrument_key="RELIANCE", direction="LONG",
        option_type="EQ", tradingsymbol="RELIANCE", exchange="NSE_INTRADAY",
        segment="equity_intraday", strike=0.0, expiry=NOW.date(), qty=1,
        entry_premium=100.0, entry_cost=100.0, entry_spot=100.0,
        entry_time=NOW - dt.timedelta(minutes=5), exit_premium=100.0 + net,
        exit_charges=0.0, exit_spot=100.0 + net, exit_time=NOW,
        exit_reason="TEST", gross_pnl=net, charges_total=0.0, net_pnl=net,
        return_pct=net, holding_minutes=5.0, win=net > 0, mode="live",
    )


def test_analytics_money_queries_exclude_the_other_tenant():
    """Catches a missing owner or account predicate on Trade/EquitySnapshot/SignalEvent."""
    with SessionLocal() as session:
        dep_a = deployments.create_deployment(
            session, "analytics", owner_id=OWNER_A, broker_account_id=ACCOUNT_A)
        dep_b = deployments.create_deployment(
            session, "analytics", owner_id=OWNER_B, broker_account_id=ACCOUNT_B)
        session.add_all([
            _trade(OWNER_A, ACCOUNT_A, dep_a.id, 10.0),
            _trade(OWNER_B, ACCOUNT_B, dep_b.id, 200.0),
            EquitySnapshot(owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
                           deployment_id=dep_a.id, time=NOW, equity=1010.0, cash=900.0,
                           invested=100.0, realized_pnl=10.0, open_count=0, book="live"),
            EquitySnapshot(owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
                           deployment_id=dep_b.id, time=NOW, equity=1200.0, cash=1000.0,
                           invested=200.0, realized_pnl=200.0, open_count=0, book="live"),
            SignalEvent(owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
                        deployment_id=dep_a.id, time=NOW, instrument_key="RELIANCE",
                        signal="LONG_ENTRY", acted=True),
            SignalEvent(owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
                        deployment_id=dep_b.id, time=NOW, instrument_key="RELIANCE",
                        signal="LONG_ENTRY", acted=True),
        ])
        session.commit()

        scope = {"owner_id": OWNER_A, "broker_account_id": ACCOUNT_A}
        assert analytics.summary(session, **scope)["net_pnl"] == 10.0
        assert [row["net_pnl"] for row in analytics.recent_trades(session, **scope)] == [10.0]
        assert [row["equity"] for row in analytics.equity_curve(
            session, book="live", **scope)] == [1010.0]
        assert analytics.signal_counts(
            session, NOW + dt.timedelta(minutes=1), **scope)["RELIANCE"] == {
                "today": 1, "rolling": 1,
            }


def test_model_metadata_uses_tenant_local_deployment_name_uniqueness():
    """Catches reintroduction of a global Deployment.name uniqueness constraint."""
    uniques = {
        tuple(constraint.columns.keys())
        for constraint in Deployment.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("owner_id", "name") in uniques
    assert ("name",) not in uniques
    assert Deployment.__table__.c.broker_account_id.nullable is False
    assert "account_id" not in Deployment.__table__.c


def test_shadow_divergence_identity_is_local_to_an_owner_and_account():
    """The same observed bar is evidence for each book, never a global collision."""
    with SessionLocal() as session:
        session.add_all([
            IrShadowDivergence(owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
                observed_at=NOW, bar_time=NOW, instrument_key="RELIANCE",
                authoritative_strategy_key="a", shadow_strategy_key="shadow",
                graph_address="sha256:a", reason="MISMATCH"),
            IrShadowDivergence(owner_id=OWNER_B, broker_account_id=ACCOUNT_B,
                observed_at=NOW, bar_time=NOW, instrument_key="RELIANCE",
                authoritative_strategy_key="a", shadow_strategy_key="shadow",
                graph_address="sha256:a", reason="MISMATCH"),
        ])
        session.commit()
        assert session.query(IrShadowDivergence).count() == 2


def test_runner_today_trade_count_excludes_the_other_account():
    with SessionLocal() as session:
        dep_a = deployments.create_deployment(session, "count-a", owner_id=OWNER_A,
                                               broker_account_id=ACCOUNT_A)
        dep_b = deployments.create_deployment(session, "count-b", owner_id=OWNER_B,
                                               broker_account_id=ACCOUNT_B)
        session.add_all([_trade(OWNER_A, ACCOUNT_A, dep_a.id, 1),
                         _trade(OWNER_B, ACCOUNT_B, dep_b.id, 1)])
        session.commit()
    runner = object.__new__(EngineRunner)
    runner.book, runner.owner_id, runner.broker_account_id = "live", OWNER_A, ACCOUNT_A
    assert runner._today_trade_count(NOW.date()) == 1
