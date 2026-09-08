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
from tests.admitted_entry import persist_admitted_entry


OWNER_A = "org-a"
OWNER_B = "org-b"
ACCOUNT_A = "account.a"
ACCOUNT_B = "account.b"
NOW = dt.datetime(2026, 8, 11, 10, 0)


_ADMISSIONS: dict[tuple[str, str], dict[str, str]] = {}


def _create_deployment(session, name, *, owner_id, broker_account_id, **kwargs):
    admission = persist_admitted_entry(session, owner_id=owner_id)
    _ADMISSIONS[(owner_id, broker_account_id)] = admission
    return deployments.create_deployment(
        session, name, owner_id=owner_id, broker_account_id=broker_account_id,
        strategy_key=admission["strategy_key"],
        strategy_version=admission["strategy_version"],
        graph_address=admission["graph_address"],
        attribution_state=admission["attribution_state"],
        admission_address=admission["admission_address"], **kwargs)


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
        a = _create_deployment(
            session, "momentum", owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
            status=deployments.ACTIVE,
        )
        b = _create_deployment(
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
        strategy_key=_ADMISSIONS[(owner_id, broker_account_id)]["strategy_key"],
        strategy_version=_ADMISSIONS[(owner_id, broker_account_id)]["strategy_version"],
        graph_address=_ADMISSIONS[(owner_id, broker_account_id)]["graph_address"],
        attribution_state=_ADMISSIONS[(owner_id, broker_account_id)]["attribution_state"],
        admission_address=_ADMISSIONS[(owner_id, broker_account_id)]["admission_address"],
        owner_id=owner_id,
        broker_account_id=broker_account_id,
    )


def test_lifecycle_guessed_id_and_recovery_are_owner_and_account_scoped():
    """Catches id-only state reads and recovery keyed only by external account labels."""
    with SessionLocal() as session:
        dep_a = _create_deployment(
            session, "a", owner_id=OWNER_A, broker_account_id=ACCOUNT_A)
        dep_b = _create_deployment(
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


def test_paper_portfolio_combines_owned_books_and_preserves_revisions(monkeypatch):
    from app.core.paper_portfolio import read_paper_portfolio
    from app.api.principal import Principal
    from app.core.config import get_settings
    from app.db.models import GraphArtifact
    import app.main as main
    from fastapi.testclient import TestClient

    with SessionLocal() as session:
        dep_a = _create_deployment(session, "portfolio", owner_id=OWNER_A,
                                   broker_account_id=ACCOUNT_A)
        dep_b = _create_deployment(session, "portfolio", owner_id=OWNER_B,
                                   broker_account_id=ACCOUNT_B)
        session.add(BrokerAccount(broker_account_id="account.extra", owner_id=OWNER_A,
                                  broker="paper", external_account_id="extra", display_name="Extra"))
        session.flush()
        dep_extra = _create_deployment(session, "extra", owner_id=OWNER_A,
                                       broker_account_id="account.extra")
        for owner, label in ((OWNER_A, "My saved strategy"), (OWNER_B, "Private other strategy")):
            graph = session.scalar(select(GraphArtifact).where(GraphArtifact.owner_id == owner))
            graph.display_name = label
        rows = [_trade(OWNER_A, ACCOUNT_A, dep_a.id, value)
                for value in (10.25, -3.1, 2.0, 999.0)]
        for index, row in enumerate(rows[:3]):
            row.mode = "paper"
            row.strategy_key = "trend_impulse_v3"
            row.strategy_version = "first" if index < 2 else "second"
        rows[1].exit_time = NOW + dt.timedelta(days=1)
        rows[2].exit_time = NOW + dt.timedelta(days=1)
        rows[2].broker_account_id = "account.extra"
        rows[2].deployment_id = dep_extra.id
        rows[0].gross_pnl = 12.25
        rows[0].charges_total = 2.0
        foreign = _trade(OWNER_B, ACCOUNT_B, dep_b.id, 800.0)
        foreign.mode = "paper"
        session.add_all([*rows, foreign])
        session.commit()
        result = read_paper_portfolio(session, owner_id=OWNER_A)
        assert result["schema"] == "paper-portfolio/1"
        assert result["currency"] == "INR"
        assert result["realized_pnl"] == 9.15
        assert result["closed_trades"] == 3
        assert result["points"] == [
            {"timestamp": "2026-08-11", "realized_pnl": 10.25},
            {"timestamp": "2026-08-12", "realized_pnl": 9.15},
        ]
        assert [(item["strategy_version"], item["realized_pnl"], item["closed_trades"])
                for item in result["strategies"]] == [("first", 7.15, 2), ("second", 2.0, 1)]
        assert all(item["display_name"] == "Trend Impulse V3" for item in result["strategies"])
        assert result["untraded_strategies"] == [{
            "strategy_key": _ADMISSIONS[(OWNER_A, ACCOUNT_A)]["strategy_key"],
            "strategy_version": "1", "display_name": "My saved strategy"}]
        assert read_paper_portfolio(session, owner_id=OWNER_B)["realized_pnl"] == 800.0
        empty = read_paper_portfolio(session, owner_id="absent-owner")
        assert empty["points"] == empty["strategies"] == []
        assert empty["closed_trades"] == empty["realized_pnl"] == 0
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setattr(get_settings(), "browser_auth_enabled", False)
    principal = Principal(id="reader", kind="user", scopes=frozenset({"read:portfolio"}),
                          organization_id=OWNER_A, role="viewer")
    monkeypatch.setattr(main, "resolve_http_principal", lambda request: principal)
    client = TestClient(main.app)
    response = client.get("/api/v1/paper-portfolio")
    assert response.status_code == 200
    assert response.json()["realized_pnl"] == 9.15
    principal = Principal(id="other", kind="user", scopes=frozenset({"read:portfolio"}),
                          organization_id=OWNER_B, role="viewer")
    assert client.get("/api/paper-portfolio").json()["realized_pnl"] == 800.0
    principal = Principal(id="denied", kind="user", scopes=frozenset(),
                          organization_id=OWNER_A, role="viewer")
    assert client.get("/api/v1/paper-portfolio").status_code == 403


def test_paper_portfolio_keeps_unknown_attribution_and_owned_names():
    from app.core.paper_portfolio import _display_name
    from app.api.request_actions import classify_request

    assert _display_name(None, {}) == "Unattributed strategy"
    assert _display_name("ir.saved", {"ir.saved": "My strategy"}) == "My strategy"
    assert _display_name("ir.saved.abcdef123456", {"ir.saved": "My strategy"}) == "My strategy"
    assert _display_name("ir.saved.unknown", {"ir.saved": "My strategy"}) == "Saved strategy"
    assert _display_name("ir.foreign", {}) == "Saved strategy"
    assert _display_name("expanding_z_v4", {}) == "Expanding Z Impulse V4"
    assert classify_request("GET", "/api/paper-portfolio") == "read:portfolio"
    assert classify_request("POST", "/api/paper-portfolio") is None


def test_analytics_money_queries_exclude_the_other_tenant():
    """Catches a missing owner or account predicate on Trade/EquitySnapshot/SignalEvent."""
    with SessionLocal() as session:
        dep_a = _create_deployment(
            session, "analytics", owner_id=OWNER_A, broker_account_id=ACCOUNT_A)
        dep_b = _create_deployment(
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
        dep_a = _create_deployment(session, "count-a", owner_id=OWNER_A,
                                               broker_account_id=ACCOUNT_A)
        dep_b = _create_deployment(session, "count-b", owner_id=OWNER_B,
                                               broker_account_id=ACCOUNT_B)
        session.add_all([_trade(OWNER_A, ACCOUNT_A, dep_a.id, 1),
                         _trade(OWNER_B, ACCOUNT_B, dep_b.id, 1)])
        session.commit()
    runner = object.__new__(EngineRunner)
    runner.book, runner.owner_id, runner.broker_account_id = "live", OWNER_A, ACCOUNT_A
    assert runner._today_trade_count(NOW.date()) == 1
