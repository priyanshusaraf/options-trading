import datetime as dt

import pytest
from sqlalchemy import select

from app.core.instruments import get_instrument
from app.db.models import Deployment, ExecutionIntent, ExecutionOrderEvent, OrderJournal, Position
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.engine.execution_lifecycle import (
    ExecutionLifecycleStore, NewExecutionEvent, NewExecutionIntent)
from app.engine.live_broker import LiveBroker
from app.providers.mock import MockProvider


NOW = dt.datetime(2026, 8, 9, 10, 30)


class _RecoveryClient:
    def __init__(self, orders=None, status=None):
        self.order_book = list(orders or [])
        self.observation = status or {
            "status": "COMPLETE", "filled_qty": 75, "avg_price": 101.0, "reason": ""}
        self.requests = []
        self.stop_calls = 0

    def place(self, request):
        self.requests.append(request)
        raise RuntimeError("ack lost")

    def orders(self):
        return list(self.order_book)

    def status(self, order_id):
        return dict(self.observation)

    def place_stop_gtt(self, *args, **kwargs):
        self.stop_calls += 1
        return "GTT-RECOVERED"

    def place_stop_order(self, *args, **kwargs):
        self.stop_calls += 1
        return "SLM-RECOVERED"


class _PartialGrowthClient(_RecoveryClient):
    def __init__(self):
        super().__init__()
        self.observations = iter([
            {"status": "OPEN", "filled_qty": 25, "avg_price": 100.0, "reason": ""},
            {"status": "COMPLETE", "filled_qty": 75, "avg_price": 102.0, "reason": ""},
        ])

    def place(self, request):
        self.requests.append(request)
        return "OID-GROW"

    def status(self, order_id):
        return dict(next(self.observations))


def _option_context(provider):
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = min(
        (q for q in chain.quotes if q.option_type == "CE"),
        key=lambda q: abs(q.strike - chain.spot),
    )
    return inst, quote, {
        "inst_key": inst.key,
        "direction": "LONG",
        "reason": "recovered",
        "spot": chain.spot,
        "params": {},
        "q": LiveBroker._quote_to_ctx(quote),
        "strategy_key": None,
        "strategy_version": None,
    }


def _seed_lifecycle(context, *, symbol, exchange, qty, account_scope="default",
                    connection_scope="kite:default", deployment_id=1,
                    decision_price=100.0):
    with SessionLocal() as session:
        store = ExecutionLifecycleStore(session)
        intent = store.create_intent(
            NewExecutionIntent(
                deployment_id=deployment_id,
                broker="kite",
                account_scope=account_scope,
                connection_scope=connection_scope,
                intent="ENTRY",
                instrument_key=context["inst_key"],
                tradingsymbol=symbol,
                exchange=exchange,
                side="BUY",
                product=None,
                order_type="MARKET",
                requested_qty=qty,
                limit_price=None,
                decision_price=decision_price,
                signal_at=NOW,
                strategy_key=None,
                strategy_version=None,
            ),
            context,
            NOW,
        )
        store.append_event(
            intent.client_intent_id,
            NewExecutionEvent(
                source="engine",
                source_event_id="submit-started",
                kind="SUBMIT_STARTED",
                broker_order_id=None,
                broker_status="",
                cumulative_filled_qty=0,
                avg_price=0.0,
                payload={"broker_tag": intent.broker_tag},
            ),
            NOW,
        )
        return intent.client_intent_id, intent.broker_tag


def test_exact_tag_miss_stays_blocked_and_delayed_match_is_adopted_without_replace():
    init_db(reset=True)
    provider = MockProvider()
    client = _RecoveryClient()
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)
    inst, quote, context = _option_context(provider)

    assert broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={}) is None
    pending = broker._pending_entries[quote.tradingsymbol]
    intent_id = pending["client_intent_id"]
    tag = pending["broker_tag"]

    assert broker._ensure_no_inflight("OTHER") is False
    assert quote.tradingsymbol in broker._pending_entries
    with SessionLocal() as session:
        assert ExecutionLifecycleStore(session).state_for(intent_id).terminal is False
        assert session.scalar(select(OrderJournal)).status == "WORKING"

    client.order_book = [{"order_id": "OID-LATE", "tag": tag,
                          "tradingsymbol": quote.tradingsymbol}]
    assert broker._ensure_no_inflight("OTHER") is False
    assert len(client.requests) == 1
    with SessionLocal() as session:
        events = list(session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == intent_id).order_by(ExecutionOrderEvent.id)))
        kinds = [event.kind for event in events]
        assert kinds.index("ACKNOWLEDGED") < kinds.index("STATUS_OBSERVED", 3)
        pos = session.scalar(select(Position).where(Position.entry_intent_id == intent_id))
        assert pos is not None and pos.qty == 75


def test_multiple_exact_tag_matches_persist_anomaly_and_remain_blocked():
    init_db(reset=True)
    provider = MockProvider()
    client = _RecoveryClient()
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)
    inst, quote, context = _option_context(provider)

    assert broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={}) is None
    pending = broker._pending_entries[quote.tradingsymbol]
    client.order_book = [
        {"order_id": "OID-A", "tag": pending["broker_tag"]},
        {"order_id": "OID-B", "tag": pending["broker_tag"]},
    ]

    assert broker._ensure_no_inflight("OTHER") is False
    assert pending["order_id"] is None
    assert len(client.requests) == 1
    with SessionLocal() as session:
        state = ExecutionLifecycleStore(session).state_for(pending["client_intent_id"])
        assert any("multiple" in anomaly.lower() for anomaly in state.anomalies)
        assert session.scalar(select(Position)) is None


def test_startup_recovers_lifecycle_only_intent_in_exact_scope_and_ignores_wrong_scope():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    correct_id, _ = _seed_lifecycle(
        context, symbol=quote.tradingsymbol, exchange=quote.exchange, qty=quote.lot_size)
    wrong_id, _ = _seed_lifecycle(
        context, symbol="WRONG-SCOPE", exchange=quote.exchange, qty=quote.lot_size,
        account_scope="other", connection_scope="kite:other")
    with SessionLocal() as session:
        session.add(Deployment(id=2, name="other-deployment", account_id="default"))
        session.commit()
    wrong_deployment_id, _ = _seed_lifecycle(
        context, symbol="WRONG-DEPLOYMENT", exchange=quote.exchange, qty=quote.lot_size,
        deployment_id=2)
    client = _RecoveryClient()
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)

    broker.recover_journal(NOW)

    assert {ctx["client_intent_id"] for ctx in broker._pending_entries.values()} == {correct_id}
    assert wrong_id not in {ctx["client_intent_id"] for ctx in broker._pending_entries.values()}
    assert wrong_deployment_id not in {
        ctx["client_intent_id"] for ctx in broker._pending_entries.values()}
    with SessionLocal() as session:
        assert session.scalar(select(OrderJournal)) is None
        wrong_kinds = [event.kind for event in session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == wrong_id).order_by(ExecutionOrderEvent.id))]
        assert wrong_kinds == ["INTENT_CREATED", "SUBMIT_STARTED"]
        wrong_deployment_kinds = [event.kind for event in session.scalars(
            select(ExecutionOrderEvent).where(
                ExecutionOrderEvent.client_intent_id == wrong_deployment_id)
            .order_by(ExecutionOrderEvent.id))]
        assert wrong_deployment_kinds == ["INTENT_CREATED", "SUBMIT_STARTED"]


def test_startup_exact_tag_match_persists_ack_before_status_and_adopts_lifecycle_only_fill():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    intent_id, tag = _seed_lifecycle(
        context, symbol=quote.tradingsymbol, exchange=quote.exchange, qty=quote.lot_size)
    client = _RecoveryClient([{"order_id": "OID-FOUND", "tag": tag,
                               "tradingsymbol": quote.tradingsymbol}])
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)

    broker.recover_journal(NOW)

    with SessionLocal() as session:
        events = list(session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == intent_id).order_by(ExecutionOrderEvent.id)))
        assert [event.kind for event in events][2:4] == ["ACKNOWLEDGED", "STATUS_OBSERVED"]
        assert session.scalar(select(Position).where(
            Position.entry_intent_id == intent_id)).qty == 75


def test_unrelated_legacy_position_does_not_consume_lifecycle_recovery():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    legacy = PaperBroker(provider).open_position(
        inst, "LONG", quote, "legacy", NOW, context["spot"], params={})
    with SessionLocal() as session:
        stored_legacy = session.get(Position, legacy.id)
        stored_legacy.mode = "live"
        session.commit()
        session.refresh(stored_legacy)
        original = (stored_legacy.id, stored_legacy.qty, stored_legacy.entry_cost,
                    stored_legacy.gtt_trigger_id)
    intent_id, tag = _seed_lifecycle(
        context, symbol=quote.tradingsymbol, exchange=quote.exchange, qty=quote.lot_size)
    client = _RecoveryClient([{"order_id": "OID-CONFLICT", "tag": tag}])
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)

    broker.recover_journal(NOW)

    with SessionLocal() as session:
        positions = list(session.scalars(select(Position)))
        assert [(p.id, p.qty, p.entry_cost, p.gtt_trigger_id) for p in positions] == [original]
        assert ExecutionLifecycleStore(session).state_for(intent_id).reconciliation_required is True
    assert any(ctx["client_intent_id"] == intent_id for ctx in broker._pending_entries.values())
    assert client.stop_calls == 0


def test_lifecycle_only_equity_recovery_uses_durable_margin_basis():
    init_db(reset=True)
    provider = MockProvider()
    inst = get_instrument("NIFTY")
    symbol = getattr(inst, "spot_symbol", None) or inst.key
    context = {
        "inst_key": inst.key, "direction": "LONG", "charge_segment": "NSE_INTRADAY",
        "reason": "recovered", "params": {}, "strategy_key": None,
        "strategy_version": None, "sl_pct": None, "tp_pct": None,
        "requested_qty": 4, "margin": 400.0,
    }
    intent_id, tag = _seed_lifecycle(
        context, symbol=symbol, exchange="NSE", qty=4, decision_price=100.0)
    client = _RecoveryClient(
        [{"order_id": "OID-EQ", "tag": tag}],
        {"status": "COMPLETE", "filled_qty": 2, "avg_price": 100.0, "reason": ""},
    )
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)

    broker.recover_journal(NOW)

    with SessionLocal() as session:
        pos = session.scalar(select(Position).where(Position.entry_intent_id == intent_id))
        assert pos.entry_cost - pos.entry_charges == pytest.approx(200.0)


def test_cumulative_adoption_commit_failure_rolls_back_ledger_delta(monkeypatch):
    init_db(reset=True)
    provider = MockProvider()
    client = _PartialGrowthClient()
    broker = LiveBroker(provider, client, poll_seconds=1.0, timeout_seconds=0.0)
    inst, quote, context = _option_context(provider)
    pos = broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={})
    assert pos.qty == 25
    cash_before = broker.cash()
    pending = broker._pending_entries[quote.tradingsymbol]
    pending["booked_qty"] = 75  # stale mutable state must not control the delta
    intent_id = pending["client_intent_id"]
    with SessionLocal() as session:
        assert ExecutionLifecycleStore(session).state_for(intent_id).booked_qty == 25

    original_commit = broker.s.commit

    def fail_position_update():
        if any(isinstance(row, Position) for row in broker.s.dirty):
            raise RuntimeError("ledger write failed")
        return original_commit()

    monkeypatch.setattr(broker.s, "commit", fail_position_update)
    assert broker.adopt_pending_entries(NOW) == []

    assert broker.s.in_transaction() is False
    with SessionLocal() as session:
        stored = session.scalar(select(Position).where(Position.entry_intent_id == intent_id))
        assert stored.qty == 25
        assert ExecutionLifecycleStore(session).state_for(intent_id).booked_qty == 25
    assert broker.cash() == cash_before
    assert quote.tradingsymbol in broker._pending_entries
