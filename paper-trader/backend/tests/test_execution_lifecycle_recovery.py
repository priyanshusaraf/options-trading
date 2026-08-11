import datetime as dt
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.core.instruments import get_instrument
from app.db.models import (
    Deployment, ExecutionIntent, ExecutionOrderEvent, LEGACY_BROKER_ACCOUNT_ID,
    LEGACY_OWNER_ID, OrderJournal, Position)
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.engine.execution_lifecycle import (
    ExecutionLifecycleStore as _ExecutionLifecycleStore,
    NewExecutionEvent, NewExecutionIntent)
from app.engine.live_broker import LiveBroker
import inspect
import app.engine.live_broker as live_broker_module


def test_protection_intent_lookup_is_not_an_unscoped_primary_key_read():
    """An intent id received in a protection path must be checked against this broker's book."""
    assert ".get(ExecutionIntent, client_intent_id)" not in inspect.getsource(
        live_broker_module.LiveBroker)
from app.engine.kite_order_client import PreWireProtectionRejected
from app.providers import capabilities as caps
from app.providers.connection import Connection
from app.providers.mock import MockProvider


NOW = dt.datetime(2026, 8, 9, 10, 30)


def ExecutionLifecycleStore(session, **scope):
    scope.setdefault("owner_id", LEGACY_OWNER_ID)
    scope.setdefault("broker_account_id", LEGACY_BROKER_ACCOUNT_ID)
    return _ExecutionLifecycleStore(session, **scope)


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

    def gtts(self):
        return []

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


class _AcknowledgedFillClient(_RecoveryClient):
    def place(self, request):
        self.requests.append(request)
        return "OID-ENTRY"


class _StopFailsClient(_AcknowledgedFillClient):
    def place_stop_gtt(self, *args, **kwargs):
        self.stop_calls += 1
        raise PreWireProtectionRejected("GTT rejected before wire")

    def place_stop_order(self, *args, **kwargs):
        self.stop_calls += 1
        raise PreWireProtectionRejected("SL-M rejected before wire")


class _InvisibleAcceptedProtectionClient(_AcknowledgedFillClient):
    def place_stop_gtt(self, *args, **kwargs):
        self.stop_calls += 1
        raise RuntimeError("connection dropped after submit")


class _OwnerGttCollisionClient(_InvisibleAcceptedProtectionClient):
    def __init__(self, status, owner_gtt):
        super().__init__(status=status)
        self.owner_gtt = dict(owner_gtt)

    def gtts(self):
        return [dict(self.owner_gtt)]


class _ConcurrentOwnerGttClient(_InvisibleAcceptedProtectionClient):
    def __init__(self, status):
        super().__init__(status=status)
        self.inventory_reads = 0

    def gtts(self):
        self.inventory_reads += 1
        if self.inventory_reads == 1:
            return []
        return [{
            "trigger_id": "OWNER-CONCURRENT", "status": "active",
            "tradingsymbol": self.last_symbol,
            "exchange": self.last_exchange,
            "side": "SELL", "qty": self.last_qty,
            "trigger_price": self.last_trigger,
        }]

    def place_stop_gtt(self, tradingsymbol, exchange, qty, trigger, last, side="SELL"):
        self.stop_calls += 1
        self.last_symbol = tradingsymbol
        self.last_exchange = exchange
        self.last_qty = qty
        self.last_trigger = trigger
        raise RuntimeError("connection dropped after submit")


class _FailingInventoryClient(_AcknowledgedFillClient):
    def orders(self):
        raise RuntimeError("order inventory unavailable")

    def gtts(self):
        raise RuntimeError("GTT inventory unavailable")


class _MissingInventoryClient:
    def __init__(self):
        self.requests = []

    def place(self, request):
        self.requests.append(request)
        return "OID-UNEXPECTED"

    def status(self, order_id):
        return {"status": "COMPLETE", "filled_qty": 1,
                "avg_price": 100.0, "reason": ""}


class _GrowingEquityProtectionClient(_RecoveryClient):
    def __init__(self):
        super().__init__()
        self.observations = iter([
            {"status": "OPEN", "filled_qty": 2, "avg_price": 100.0, "reason": ""},
            {"status": "COMPLETE", "filled_qty": 4, "avg_price": 101.0, "reason": ""},
        ])
        self.protected_qty = 0

    def place(self, request):
        self.requests.append(request)
        return "OID-EQ-GROW"

    def status(self, order_id):
        return dict(next(self.observations))

    def place_stop_order(self, tradingsymbol, exchange, qty, trigger, side="SELL", tag=None):
        self.stop_calls += 1
        self.protected_qty = qty
        return "SLM-GROW"

    def modify_stop_order(self, order_id, trigger_price, tradingsymbol=None,
                          exchange=None, quantity=None):
        if quantity is not None:
            self.protected_qty = quantity


class _ProtectionPersistsAtBrokerClient(_AcknowledgedFillClient):
    def __init__(self, status):
        super().__init__(status=status)
        self.gtt_book = []

    def place_stop_gtt(self, tradingsymbol, exchange, qty, trigger, last, side="SELL"):
        self.stop_calls += 1
        self.gtt_book.append({
            "trigger_id": "GTT-LIVE", "status": "active",
            "tradingsymbol": tradingsymbol, "exchange": exchange,
            "side": side, "qty": qty, "trigger_price": trigger,
        })
        return "GTT-LIVE"

    def gtts(self):
        return list(self.gtt_book)


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
                        connection_scope="kite:legacy", deployment_id=1,
                        decision_price=100.0, broker="mock", owner_id="owner",
                        broker_account_id="account.default"):
    """Seed a durable intent as the broker-under-test would have written it.

    `broker` defaults to `"mock"`, not `"kite"`, and that is the point: these tests build a
    `LiveBroker` on a `MockProvider`, so `connection_for(provider).broker` is `"mock"`. The
    helper used to hardcode `"kite"` — writing a broker it was not using — which was invisible
    until `unresolved_entries` started matching on it (2026-08-10). A recovery query that
    ignores the broker cannot tell a Kite intent from a Dhan one, and adopting another venue's
    working orders is the failure this dimension exists to prevent.
    """
    with SessionLocal() as session:
        store = ExecutionLifecycleStore(session)
        intent = store.create_intent(
            NewExecutionIntent(
                deployment_id=deployment_id,
                    broker=broker,
                    owner_id=owner_id,
                    broker_account_id=broker_account_id,
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
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
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
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
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
        session.add(Deployment(
            id=2, name="other-deployment", owner_id=LEGACY_OWNER_ID,
            broker_account_id=LEGACY_BROKER_ACCOUNT_ID))
        session.commit()
    wrong_deployment_id, _ = _seed_lifecycle(
        context, symbol="WRONG-DEPLOYMENT", exchange=quote.exchange, qty=quote.lot_size,
        deployment_id=2)
    client = _RecoveryClient()
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

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
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

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
    legacy = PaperBroker(provider, owner_id="owner", broker_account_id="account.default").open_position(
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
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

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
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

    broker.recover_journal(NOW)

    with SessionLocal() as session:
        pos = session.scalar(select(Position).where(Position.entry_intent_id == intent_id))
        assert pos.entry_cost - pos.entry_charges == pytest.approx(200.0)


def test_cumulative_adoption_commit_failure_rolls_back_ledger_delta(monkeypatch):
    init_db(reset=True)
    provider = MockProvider()
    client = _PartialGrowthClient()
    broker = LiveBroker(provider, client, poll_seconds=1.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
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


def test_restart_journal_without_order_id_uses_existing_lifecycle_ack():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    intent_id, _ = _seed_lifecycle(
        context, symbol=quote.tradingsymbol, exchange=quote.exchange, qty=quote.lot_size)
    with SessionLocal() as session:
        ExecutionLifecycleStore(session).append_event(
            intent_id,
            NewExecutionEvent(
                source="broker", source_event_id="ack:OID-ACK",
                kind="ACKNOWLEDGED", broker_order_id="OID-ACK", broker_status="",
                cumulative_filled_qty=0, avg_price=0.0,
                payload={"order_id": "OID-ACK"},
            ),
            NOW,
        )
        journal_context = dict(context, client_intent_id=intent_id)
        session.add(OrderJournal(
            owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID,
            deployment_id=1, order_id=None, tradingsymbol=quote.tradingsymbol,
            instrument_key=inst.key, side="BUY", kind="options", intent="ENTRY",
            qty=quote.lot_size, context_json=__import__("json").dumps(journal_context),
            status="WORKING", placed_at=NOW,
        ))
        session.commit()
    client = _RecoveryClient(status={
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

    broker.recover_journal(NOW)

    with SessionLocal() as session:
        assert session.scalar(select(Position).where(
            Position.entry_intent_id == intent_id)) is not None
        ack_events = list(session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == intent_id,
            ExecutionOrderEvent.kind == "ACKNOWLEDGED")))
        assert len(ack_events) == 1
        assert session.scalar(select(OrderJournal)).status == "TERMINAL"


def test_legacy_working_entry_without_intent_still_adopts():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    with SessionLocal() as session:
        session.add(OrderJournal(
            owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID,
            deployment_id=1, order_id="OID-LEGACY", tradingsymbol=quote.tradingsymbol,
            instrument_key=inst.key, side="BUY", kind="options", intent="ENTRY",
            qty=quote.lot_size, context_json=__import__("json").dumps(context),
            status="WORKING", placed_at=NOW,
        ))
        session.commit()
    client = _RecoveryClient(status={
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

    broker.recover_journal(NOW)

    with SessionLocal() as session:
        positions = list(session.scalars(select(Position)))
        assert len(positions) == 1
        assert positions[0].entry_intent_id is None
        assert positions[0].gtt_trigger_id == "GTT-RECOVERED"
        journal = session.scalar(select(OrderJournal).where(OrderJournal.intent == "ENTRY"))
        assert journal.status == "TERMINAL"
        assert journal.resolution == "ADOPTED"


def test_option_stop_failure_remains_recoverable_after_restart():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    failing = _StopFailsClient(status={
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    broker = LiveBroker(provider, failing, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

    pos = broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={})
    intent_id = pos.entry_intent_id
    cash_after_fill = broker.cash()
    with SessionLocal() as session:
        stored = session.get(Position, pos.id)
        assert stored.gtt_trigger_id is None
        assert ExecutionLifecycleStore(session).state_for(
            intent_id).reconciliation_required is True
        assert session.scalar(select(OrderJournal).where(
            OrderJournal.intent == "ENTRY")).status == "WORKING"

    recovered_client = _RecoveryClient(status={
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    restarted = LiveBroker(provider, recovered_client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    restarted.recover_journal(NOW)

    assert restarted.cash() == cash_after_fill
    with SessionLocal() as session:
        positions = list(session.scalars(select(Position)))
        assert len(positions) == 1
        assert positions[0].gtt_trigger_id == "GTT-RECOVERED"
        state = ExecutionLifecycleStore(session).state_for(intent_id)
        assert state.reconciliation_required is False
        kinds = [event.kind for event in session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == intent_id).order_by(ExecutionOrderEvent.id))]
        assert kinds.index("POSITION_PROTECTED") < kinds.index("POSITION_BOOKED")


def test_equity_stop_failure_remains_recoverable_after_restart():
    init_db(reset=True)
    provider = MockProvider()
    inst = get_instrument("NIFTY")
    client_status = {"status": "COMPLETE", "filled_qty": 4,
                     "avg_price": 100.0, "reason": ""}
    broker = LiveBroker(
        provider, _StopFailsClient(status=client_status),
        poll_seconds=0.0, timeout_seconds=0.0,
        owner_id=LEGACY_OWNER_ID,
        broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

    pos = broker.open_equity_position(
        inst, "LONG", 100.0, 4, "NSE_INTRADAY", "signal", NOW,
        params={}, margin=400.0)
    intent_id = pos.entry_intent_id
    cash_after_fill = broker.cash()
    with SessionLocal() as session:
        stored = session.get(Position, pos.id)
        assert stored.gtt_trigger_id is None
        assert ExecutionLifecycleStore(session).state_for(
            intent_id).reconciliation_required is True
        assert session.scalar(select(OrderJournal).where(
            OrderJournal.intent == "ENTRY")).status == "WORKING"

    recovered_client = _RecoveryClient(status=client_status)
    restarted = LiveBroker(provider, recovered_client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    restarted.recover_journal(NOW)

    assert restarted.cash() == cash_after_fill
    with SessionLocal() as session:
        positions = list(session.scalars(select(Position)))
        assert len(positions) == 1
        assert positions[0].gtt_trigger_id == "SLM-RECOVERED"
        assert ExecutionLifecycleStore(session).state_for(
            intent_id).reconciliation_required is False


def test_protection_id_persistence_failure_reconciles_without_duplicate(monkeypatch):
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    client = _ProtectionPersistsAtBrokerClient({
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    original_commit = broker.s.commit
    failed = False

    def fail_protection_id_once():
        nonlocal failed
        protected_position = next((
            row for row in broker.s.dirty
            if isinstance(row, Position) and row.gtt_trigger_id == "GTT-LIVE"
        ), None)
        if protected_position is not None and not failed:
            failed = True
            raise RuntimeError("position protection id write failed")
        return original_commit()

    monkeypatch.setattr(broker.s, "commit", fail_protection_id_once)
    pos = broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={})
    intent_id = pos.entry_intent_id

    assert client.stop_calls == 1
    with SessionLocal() as session:
        assert session.get(Position, pos.id).gtt_trigger_id is None
        assert ExecutionLifecycleStore(session).state_for(
            intent_id).reconciliation_required is True

    restarted = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    restarted.recover_journal(NOW)

    assert client.stop_calls == 1
    with SessionLocal() as session:
        stored = session.get(Position, pos.id)
        assert stored.gtt_trigger_id == "GTT-LIVE"
        assert ExecutionLifecycleStore(session).state_for(
            intent_id).reconciliation_required is False


def test_live_entry_uses_legacy_connection_scope():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    broker = LiveBroker(
        provider,
        _AcknowledgedFillClient(status={
            "status": "COMPLETE", "filled_qty": quote.lot_size,
            "avg_price": 101.0, "reason": ""}),
        poll_seconds=0.0,
        timeout_seconds=0.0,
        owner_id=LEGACY_OWNER_ID,
        broker_account_id=LEGACY_BROKER_ACCOUNT_ID,
    )

    broker.open_position(inst, "LONG", quote, "signal", NOW, context["spot"], params={})

    with SessionLocal() as session:
        assert session.scalar(select(ExecutionIntent)).connection_scope == "kite:legacy"


def test_restart_recovers_this_connections_entries_and_not_another_connections():
    """The mirror of the exact-scope test above, from the second connection's side.

    That test builds a broker on the default connection, where "this connection's scope" and
    the legacy constant are the same string — so it cannot tell a correct lookup from a
    hardcoded one. This one can: the broker runs on `upstox:acct-1` and must adopt only the
    intent seeded there, leaving the legacy-scope intent for the broker that owns it.

    Getting this wrong is not cosmetic. Adopting another connection's unresolved entry means
    polling one broker for an order id that only exists at another, and abandoning your own
    means a real working order with no local record of it.
    """
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    legacy_id, _ = _seed_lifecycle(
        context, symbol=quote.tradingsymbol, exchange=quote.exchange, qty=quote.lot_size)
    second_id, _ = _seed_lifecycle(
        context, symbol="SECOND-CONNECTION", exchange=quote.exchange, qty=quote.lot_size,
        connection_scope="upstox:acct-1", broker="upstox")
    broker = LiveBroker(
        provider, _RecoveryClient(), poll_seconds=0.0, timeout_seconds=0.0,
        owner_id=LEGACY_OWNER_ID,
        broker_account_id=LEGACY_BROKER_ACCOUNT_ID,
        connection=Connection(
            broker="upstox", scope="upstox:acct-1",
            capabilities=frozenset({caps.LIVE_EXECUTION})))

    broker.recover_journal(NOW)

    adopted = {ctx["client_intent_id"] for ctx in broker._pending_entries.values()}
    assert adopted == {second_id}
    assert legacy_id not in adopted


def test_the_money_record_carries_the_connection_that_actually_placed_the_order():
    """The scope and broker on an intent must come from the execution connection.

    Both were hardcoded (`"kite"`, `KITE_LEGACY_CONNECTION_SCOPE`) until the connection seam,
    so a second broker's fills would have been attributed to Kite's legacy connection — and
    the restart-recovery query matches on exactly this pair, so a wrong scope means a restart
    either adopts another connection's unresolved entries or abandons its own.
    """
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    second = Connection(
        broker="upstox", scope="upstox:acct-1",
        capabilities=frozenset({caps.LIVE_EXECUTION}))
    broker = LiveBroker(
        provider,
        _AcknowledgedFillClient(status={
            "status": "COMPLETE", "filled_qty": quote.lot_size,
            "avg_price": 101.0, "reason": ""}),
        poll_seconds=0.0,
        timeout_seconds=0.0,
        owner_id=LEGACY_OWNER_ID,
        broker_account_id=LEGACY_BROKER_ACCOUNT_ID,
        connection=second,
    )

    broker.open_position(inst, "LONG", quote, "signal", NOW, context["spot"], params={})

    with SessionLocal() as session:
        intent = session.scalar(select(ExecutionIntent))
        assert intent.connection_scope == "upstox:acct-1"
        assert intent.broker == "upstox"


def test_equity_partial_growth_updates_protection_quantity_before_completion():
    init_db(reset=True)
    provider = MockProvider()
    client = _GrowingEquityProtectionClient()
    broker = LiveBroker(provider, client, poll_seconds=1.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    inst = get_instrument("NIFTY")

    pos = broker.open_equity_position(
        inst, "LONG", 100.0, 4, "NSE_INTRADAY", "signal", NOW,
        params={}, margin=400.0)
    assert pos.qty == 2
    assert client.protected_qty == 2

    broker.adopt_pending_entries(NOW)

    assert pos.qty == 4
    assert client.protected_qty == 4
    with SessionLocal() as session:
        state = ExecutionLifecycleStore(session).state_for(pos.entry_intent_id)
        assert state.protected_qty == 4
        assert state.reconciliation_required is False


def test_uncertain_invisible_protection_is_not_replaced_after_one_empty_read():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    client = _InvisibleAcceptedProtectionClient(status={
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    pos = broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={})

    assert client.stop_calls == 1
    restarted = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    restarted.recover_journal(NOW)

    assert client.stop_calls == 1
    with SessionLocal() as session:
        assert session.get(Position, pos.id).gtt_trigger_id is None
        assert ExecutionLifecycleStore(session).state_for(
            pos.entry_intent_id).reconciliation_required is True


def test_owner_gtt_in_submit_baseline_is_never_attached_to_bot_position():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    owner_gtt = {
        "trigger_id": "OWNER-GTT", "status": "active",
        "tradingsymbol": quote.tradingsymbol, "exchange": quote.exchange,
        "side": "SELL", "qty": quote.lot_size,
        "trigger_price": 65.0,
    }
    client = _OwnerGttCollisionClient(
        {"status": "COMPLETE", "filled_qty": quote.lot_size,
         "avg_price": 101.0, "reason": ""}, owner_gtt)
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    pos = broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={})

    restarted = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    restarted.recover_journal(NOW)

    assert client.stop_calls == 1
    with SessionLocal() as session:
        assert session.get(Position, pos.id).gtt_trigger_id is None
        submit = session.scalars(select(ExecutionOrderEvent).where(
            ExecutionOrderEvent.client_intent_id == pos.entry_intent_id,
            ExecutionOrderEvent.kind == "PROTECTION_SUBMIT_STARTED")).first()
        assert "OWNER-GTT" in submit.payload_json


def test_concurrent_owner_gtt_after_empty_baseline_is_never_attached():
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    client = _ConcurrentOwnerGttClient({
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)

    pos = broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={})
    LiveBroker(provider, client, poll_seconds=0.0,
               timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID,
               broker_account_id=LEGACY_BROKER_ACCOUNT_ID).recover_journal(NOW)

    assert client.stop_calls == 1
    with SessionLocal() as session:
        stored = session.get(Position, pos.id)
        state = ExecutionLifecycleStore(session).state_for(pos.entry_intent_id)
        assert stored.gtt_trigger_id is None
        assert state.protected_qty == 0
        assert state.booked_qty == 0
        assert state.reconciliation_required is True


@pytest.mark.parametrize("payload", ["not-json", "{}", '{"baseline_ids": "bad"}'])
def test_invalid_protection_submit_metadata_fails_closed(payload):
    init_db(reset=True)
    provider = MockProvider()
    inst, quote, context = _option_context(provider)
    client = _ConcurrentOwnerGttClient({
        "status": "COMPLETE", "filled_qty": quote.lot_size,
        "avg_price": 101.0, "reason": ""})
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    pos = broker.open_position(
        inst, "LONG", quote, "signal", NOW, context["spot"], params={})

    with SessionLocal() as session:
        session.execute(text("""
            INSERT INTO execution_order_events (
                client_intent_id, owner_id, broker_account_id, source, source_event_id, kind,
                broker_order_id, broker_status, cumulative_filled_qty,
                avg_price, observed_at, payload_json, anomaly
            ) VALUES (
                :intent_id, :owner_id, :broker_account_id, 'engine', 'protection-submit:legacy-corrupt',
                'PROTECTION_SUBMIT_STARTED', NULL, '', 0, 0.0,
                :observed_at, :payload, ''
            )
        """), {"intent_id": pos.entry_intent_id, "owner_id": LEGACY_OWNER_ID,
               "broker_account_id": LEGACY_BROKER_ACCOUNT_ID, "observed_at": NOW,
                "payload": payload})
        session.commit()

    LiveBroker(provider, client, poll_seconds=0.0,
               timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID,
               broker_account_id=LEGACY_BROKER_ACCOUNT_ID).recover_journal(NOW)

    with SessionLocal() as session:
        stored = session.get(Position, pos.id)
        state = ExecutionLifecycleStore(session).state_for(pos.entry_intent_id)
        assert stored.gtt_trigger_id is None
        assert state.protected_qty == 0
        assert state.booked_qty == 0
        assert state.reconciliation_required is True


@pytest.mark.parametrize("kind", ["options", "equity"])
@pytest.mark.parametrize("client_factory", [_FailingInventoryClient, _MissingInventoryClient])
def test_live_entry_refuses_before_intent_when_protection_inventory_fails(
        kind, client_factory):
    init_db(reset=True)
    provider = MockProvider()
    client = client_factory()
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    inst, quote, context = _option_context(provider)

    if kind == "options":
        result = broker.open_position(
            inst, "LONG", quote, "signal", NOW, context["spot"], params={})
    else:
        result = broker.open_equity_position(
            inst, "LONG", 100.0, 4, "NSE_INTRADAY", "signal", NOW,
            params={}, margin=400.0)

    assert result is None
    assert client.requests == []
    with SessionLocal() as session:
        assert session.scalar(select(ExecutionIntent)) is None
        assert session.scalar(select(ExecutionOrderEvent)) is None


@pytest.mark.parametrize("kind", ["options", "equity"])
def test_live_entry_does_not_submit_when_exchange_protection_disabled(monkeypatch, kind):
    init_db(reset=True)
    provider = MockProvider()
    client = _AcknowledgedFillClient()
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    monkeypatch.setattr(broker, "_gtt_enabled", lambda: False)
    inst, quote, context = _option_context(provider)

    if kind == "options":
        result = broker.open_position(
            inst, "LONG", quote, "signal", NOW, context["spot"], params={})
    else:
        result = broker.open_equity_position(
            inst, "LONG", 100.0, 4, "NSE_INTRADAY", "signal", NOW,
            params={}, margin=400.0)

    assert result is None
    assert client.requests == []
    with SessionLocal() as session:
        assert session.scalar(select(ExecutionIntent)) is None
        assert session.scalar(select(ExecutionOrderEvent)) is None


def test_journal_stop_failure_rolls_back_and_same_session_remains_usable(monkeypatch):
    init_db(reset=True)
    provider = MockProvider()
    broker = LiveBroker(provider, _RecoveryClient(), poll_seconds=0.0, timeout_seconds=0.0, owner_id=LEGACY_OWNER_ID, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    original_commit = broker.s.commit
    calls = 0

    def fail_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("stop journal disk failure")
        return original_commit()

    monkeypatch.setattr(broker.s, "commit", fail_once)
    broker._journal_stop(SimpleNamespace(
        id=91, tradingsymbol="RELIANCE", instrument_key="NIFTY",
        qty=4, stop_price=95.0), "SLM-91", "SELL")
    intent = ExecutionLifecycleStore(broker.s).create_intent(
        NewExecutionIntent(
            deployment_id=1, broker="kite", account_scope="default",
            owner_id="owner", broker_account_id="account.default",
            connection_scope="kite:legacy", intent="ENTRY", instrument_key="NIFTY",
            tradingsymbol="RELIANCE", exchange="NSE", side="BUY", product="MIS",
            order_type="MARKET", requested_qty=4, limit_price=None,
            decision_price=100.0, signal_at=NOW, strategy_key=None,
            strategy_version=None), {}, NOW)

    assert intent.client_intent_id
    assert broker.s.scalar(select(OrderJournal).where(
        OrderJournal.intent == "STOP")) is None
