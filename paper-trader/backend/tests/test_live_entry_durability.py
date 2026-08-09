"""Fail-closed tests for the only two real-money entry paths.

The fake lifecycle store records commit boundaries while the fake client records
the external submit. The observable order is the safety contract.
"""
import datetime as dt
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.instruments import get_instrument
from app.db.models import (
    Deployment, ExecutionIntent, ExecutionOrderEvent, OrderJournal, Position, Trade)
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.engine import live_broker as live_broker_module
from app.engine.live_broker import LiveBroker
from app.engine.order_executor import OrderRequest
from app.providers.mock import MockProvider


class _Session:
    def get(self, model, key):
        return SimpleNamespace(id=key, account_id="account-7")


class _Client:
    def __init__(self, timeline):
        self.timeline = timeline
        self.places = 0

    def place(self, req):
        self.places += 1
        self.request = req
        self.timeline.append("place")
        return "OID-7"

    def status(self, order_id):
        return {"status": "COMPLETE", "filled_qty": 10, "avg_price": 101.0,
                "reason": ""}


def _broker(timeline):
    broker = LiveBroker.__new__(LiveBroker)
    broker.s = _Session()
    broker.client = _Client(timeline)
    broker.deployment_id = 7
    broker.poll_seconds = 0.0
    broker.timeout_seconds = 0.0
    broker.lifecycle_clock = lambda: dt.datetime(2026, 8, 9, 10, 0)
    broker._journal_open = lambda *args, **kwargs: None
    broker._journal_resolve = lambda *args, **kwargs: None
    return broker


def _request():
    return OrderRequest("NIFTY26AUG25000CE", "NFO", "BUY", 10, "MARKET")


def _entry(broker):
    return broker._execute_entry(
        _request(), kind="options", context={"inst_key": "NIFTY"},
        now=SimpleNamespace(), decision_price=100.0,
        strategy_key="trend", strategy_version="sha256:abc")


def test_entry_does_not_call_place_when_intent_commit_fails(monkeypatch):
    timeline = []

    class _FailingStore:
        def __init__(self, session):
            pass

        def create_intent(self, request, context, now):
            timeline.append("intent_commit")
            raise RuntimeError("disk full")

    monkeypatch.setattr(live_broker_module, "ExecutionLifecycleStore", _FailingStore)
    broker = _broker(timeline)

    with pytest.raises(RuntimeError, match="disk full"):
        _entry(broker)

    assert timeline == ["intent_commit"]
    assert broker.client.places == 0


def test_entry_commits_intent_and_submit_started_before_place(monkeypatch):
    timeline = []

    class _Store:
        def __init__(self, session):
            pass

        def create_intent(self, request, context, now):
            timeline.append("intent_commit")
            self.request = request
            return SimpleNamespace(client_intent_id="a" * 32,
                                   broker_tag="pti-" + "a" * 16)

        def append_event(self, client_intent_id, event, now):
            names = {
                "SUBMIT_STARTED": "submit_started_commit",
                "ACKNOWLEDGED": "ack_commit",
                "STATUS_OBSERVED": "status",
            }
            timeline.append(names[event.kind])

    monkeypatch.setattr(live_broker_module, "ExecutionLifecycleStore", _Store)
    broker = _broker(timeline)

    res, filled, avg, client_intent_id, row_id = _entry(broker)

    assert timeline == ["intent_commit", "submit_started_commit", "place",
                        "ack_commit", "status"]
    assert res.status == "FILLED"
    assert (filled, avg, client_intent_id) == (10, 101.0, "a" * 32)
    assert row_id is None
    assert broker.client.request.tag == "pti-" + "a" * 16
    assert broker.client.places == 1


def test_new_entry_uses_unique_twenty_character_intent_tag():
    from app.engine.execution_lifecycle import make_broker_tag, make_intent_id
    from app.engine.kite_order_client import is_strategy_os_tag

    tags = {make_broker_tag(make_intent_id()) for _ in range(100)}

    assert len(tags) == 100
    assert all(len(tag) == 20 and is_strategy_os_tag(tag) for tag in tags)


def test_legacy_and_intent_tags_are_both_recognised():
    from app.engine.kite_order_client import is_strategy_os_tag

    assert is_strategy_os_tag("pt-bot")
    assert is_strategy_os_tag("pti-0123456789abcdef")
    assert not is_strategy_os_tag("pti-0123456789ABCDEf")
    assert not is_strategy_os_tag("pti-0123456789abcde")
    assert not is_strategy_os_tag("pt-bot-extra")
    assert not is_strategy_os_tag(None)


class _FilledClient:
    def __init__(self, fill_price):
        self.fill_price = fill_price
        self.requests = []
        self.stop_tags = []

    def place(self, req):
        self.requests.append(req)
        return f"OID-{len(self.requests)}"

    def status(self, order_id):
        return {"status": "COMPLETE", "filled_qty": self.requests[-1].qty,
                "avg_price": self.fill_price, "reason": ""}

    def place_stop_gtt(self, *args, **kwargs):
        return "GTT-1"

    def place_stop_order(self, *args, tag=None, **kwargs):
        self.stop_tags.append(tag)
        return "SLM-1"


class _GrowingOptionsClient(_FilledClient):
    def __init__(self):
        super().__init__(102.0)
        self.observations = iter([
            {"status": "OPEN", "filled_qty": 25, "avg_price": 100.0, "reason": ""},
            {"status": "OPEN", "filled_qty": 20, "avg_price": 99.0, "reason": ""},
            {"status": "COMPLETE", "filled_qty": 75, "avg_price": 102.0, "reason": ""},
        ])
        self.gtt_modifications = []

    def status(self, order_id):
        return next(self.observations)

    def modify_stop_gtt(self, trigger_id, symbol, exchange, qty, trigger, last, side="SELL"):
        self.gtt_modifications.append(qty)


class _RecoveryClient(_FilledClient):
    def __init__(self, qty=75, avg=101.0):
        super().__init__(avg)
        self.qty = qty

    def status(self, order_id):
        return {"status": "COMPLETE", "filled_qty": self.qty,
                "avg_price": self.fill_price, "reason": ""}

    def orders(self):
        return []


class _GrowingEquityClient(_FilledClient):
    def __init__(self):
        super().__init__(101.0)
        self.observations = iter([
            {"status": "OPEN", "filled_qty": 2, "avg_price": 100.0, "reason": ""},
            {"status": "COMPLETE", "filled_qty": 4, "avg_price": 101.0, "reason": ""},
        ])

    def status(self, order_id):
        return next(self.observations)

    def cancel(self, order_id):
        pass


def test_options_entry_links_durable_intent_to_position_and_trade():
    init_db(reset=True)
    provider = MockProvider()
    client = _FilledClient(101.25)
    clock_times = iter([
        dt.datetime(2026, 8, 9, 10, 15, 30, 100000),
        dt.datetime(2026, 8, 9, 10, 15, 30, 200000),
        dt.datetime(2026, 8, 9, 10, 15, 30, 300000),
        dt.datetime(2026, 8, 9, 10, 15, 30, 400000),
        dt.datetime(2026, 8, 9, 10, 15, 30, 500000),
        dt.datetime(2026, 8, 9, 10, 15, 30, 600000),
        dt.datetime(2026, 8, 9, 10, 15, 30, 700000),
    ])
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0,
                        lifecycle_clock=lambda: next(clock_times))
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = min((q for q in chain.quotes if q.option_type == "CE"),
                key=lambda q: abs(q.strike - chain.spot))
    runtime_now = dt.datetime(2026, 8, 9, 10, 15, 30)

    pos = broker.open_position(
        inst, "LONG", quote, "signal", runtime_now, chain.spot,
        params={}, strategy_key="trend", strategy_version="sha256:abc")

    with SessionLocal() as session:
        intent = session.scalar(select(ExecutionIntent))
        events = list(session.scalars(select(ExecutionOrderEvent).order_by(ExecutionOrderEvent.id)))
        stored_pos = session.scalar(select(Position))
        assert intent.decision_price == pytest.approx((quote.bid + quote.ask) / 2.0)
        assert intent.signal_at == runtime_now
        assert [event.kind for event in events] == [
            "INTENT_CREATED", "SUBMIT_STARTED", "ACKNOWLEDGED", "STATUS_OBSERVED",
            "PROTECTION_SUBMIT_STARTED", "POSITION_PROTECTED", "POSITION_BOOKED"]
        state = live_broker_module.ExecutionLifecycleStore(session).state_for(
            intent.client_intent_id)
        assert state.signal_to_intent_ms == 100.0
        assert state.submit_to_ack_ms == 100.0
        assert state.ack_to_fill_ms == 100.0
        assert state.reconciliation_required is False
        assert stored_pos.entry_intent_id == intent.client_intent_id == pos.entry_intent_id
        journal = session.scalar(select(OrderJournal).where(OrderJournal.intent == "ENTRY"))
        assert journal.status == "TERMINAL"

    PaperBroker.close_position(broker, pos, 102.0, "TEST", runtime_now, chain.spot)
    with SessionLocal() as session:
        trade = session.scalar(select(Trade))
        assert trade.entry_intent_id == intent.client_intent_id


def test_equity_entry_uses_decision_price_and_links_intent_while_stop_stays_legacy_tagged():
    init_db(reset=True)
    provider = MockProvider()
    client = _FilledClient(251.0)
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)
    inst = get_instrument("NIFTY")
    runtime_now = dt.datetime(2026, 8, 9, 10, 16, 0)

    pos = broker.open_equity_position(
        inst, "LONG", 250.0, 4, "NSE_INTRADAY", "signal", runtime_now,
        params={}, strategy_key="equity", strategy_version="sha256:def")

    with SessionLocal() as session:
        intent = session.scalar(select(ExecutionIntent))
        stored_pos = session.scalar(select(Position))
        assert intent.decision_price == 250.0
        assert intent.signal_at == runtime_now
        assert stored_pos.entry_intent_id == intent.client_intent_id == pos.entry_intent_id
    assert client.stop_tags == ["pt-bot"]

    PaperBroker.close_equity_position(broker, pos, 252.0, "TEST", runtime_now)
    with SessionLocal() as session:
        trade = session.scalar(select(Trade))
        assert trade.entry_intent_id == intent.client_intent_id


def test_partial_timeout_books_only_later_positive_fill_delta_once():
    init_db(reset=True)
    provider = MockProvider()
    client = _GrowingOptionsClient()
    broker = LiveBroker(provider, client, poll_seconds=1.0, timeout_seconds=0.0)
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = min((q for q in chain.quotes if q.option_type == "CE"),
                key=lambda q: abs(q.strike - chain.spot))

    pos = broker.open_position(
        inst, "LONG", quote, "signal", provider.now(), chain.spot, params={})
    cash_after_25 = broker.cash()
    assert pos.qty == 25
    assert quote.tradingsymbol in broker._pending_entries

    broker.adopt_pending_entries(provider.now())  # lower 20 after booked 25
    assert pos.qty == 25
    assert broker.cash() == cash_after_25
    with SessionLocal() as session:
        intent = session.scalar(select(ExecutionIntent))
        assert "lower cumulative fill 20 after 25" in \
            live_broker_module.ExecutionLifecycleStore(session).state_for(
                intent.client_intent_id).anomalies

    broker.adopt_pending_entries(provider.now())  # cumulative COMPLETE 75
    assert pos.qty == 75
    assert pos.entry_premium == 102.0
    cash_after_75 = broker.cash()
    assert client.gtt_modifications[-1] == 75

    broker.adopt_pending_entries(provider.now())  # duplicate recovery is a no-op
    assert pos.qty == 75
    assert broker.cash() == cash_after_75


def test_complete_then_ledger_commit_failure_recovers_and_books_once(monkeypatch):
    init_db(reset=True)
    provider = MockProvider()
    broker = LiveBroker(provider, _RecoveryClient(), poll_seconds=0.0, timeout_seconds=0.0)
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = min((q for q in chain.quotes if q.option_type == "CE"),
                key=lambda q: abs(q.strike - chain.spot))
    original_commit = broker.s.commit

    def fail_position_commit():
        if any(isinstance(row, Position) for row in broker.s.new):
            broker.s.rollback()
            raise RuntimeError("ledger commit failed")
        return original_commit()

    monkeypatch.setattr(broker.s, "commit", fail_position_commit)
    with pytest.raises(RuntimeError, match="ledger commit failed"):
        broker.open_position(
            inst, "LONG", quote, "signal", provider.now(), chain.spot, params={})
    with SessionLocal() as session:
        assert session.scalar(select(Position)) is None
        journal = session.scalar(select(OrderJournal).where(OrderJournal.intent == "ENTRY"))
        assert journal.status == "WORKING"

    restarted = LiveBroker(provider, _RecoveryClient(), poll_seconds=0.0, timeout_seconds=0.0)
    restarted.recover_journal(provider.now())
    cash_after_recovery = restarted.cash()
    with SessionLocal() as session:
        positions = list(session.scalars(select(Position)))
        assert len(positions) == 1
        assert positions[0].qty == 75
        intent = session.scalar(select(ExecutionIntent))
        assert live_broker_module.ExecutionLifecycleStore(session).state_for(
            intent.client_intent_id).reconciliation_required is False
        assert session.scalar(select(OrderJournal).where(
            OrderJournal.intent == "ENTRY")).status == "TERMINAL"

    restarted.recover_journal(provider.now())
    assert restarted.cash() == cash_after_recovery


def test_equity_partial_timeout_recomputes_cumulative_order_without_double_debit():
    init_db(reset=True)
    provider = MockProvider()
    client = _GrowingEquityClient()
    broker = LiveBroker(provider, client, poll_seconds=1.0, timeout_seconds=0.0)
    inst = get_instrument("NIFTY")

    pos = broker.open_equity_position(
        inst, "LONG", 100.0, 4, "NSE_INTRADAY", "signal", provider.now(),
        params={}, margin=400.0)
    old_cost = pos.entry_cost
    old_cash = broker.cash()
    assert pos.qty == 2

    broker.adopt_pending_entries(provider.now())

    assert pos.qty == 4
    assert pos.entry_premium == 101.0
    assert broker.cash() == pytest.approx(old_cash - (pos.entry_cost - old_cost))
    assert client.stop_tags == ["pt-bot", "pt-bot"]


def test_restart_closes_position_booked_gap_without_second_debit(monkeypatch):
    init_db(reset=True)
    provider = MockProvider()
    broker = LiveBroker(provider, _RecoveryClient(), poll_seconds=0.0, timeout_seconds=0.0)
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = min((q for q in chain.quotes if q.option_type == "CE"),
                key=lambda q: abs(q.strike - chain.spot))
    monkeypatch.setattr(broker, "_mark_position_booked", lambda *args: False)

    pos = broker.open_position(
        inst, "LONG", quote, "signal", provider.now(), chain.spot, params={})
    cash_after_position = broker.cash()
    assert pos is not None

    restarted = LiveBroker(provider, _RecoveryClient(), poll_seconds=0.0, timeout_seconds=0.0)
    restarted.recover_journal(provider.now())
    assert restarted.cash() == cash_after_position
    with SessionLocal() as session:
        assert len(list(session.scalars(select(Position)))) == 1
        intent = session.scalar(select(ExecutionIntent))
        assert live_broker_module.ExecutionLifecycleStore(session).state_for(
            intent.client_intent_id).reconciliation_required is False


def test_paper_entry_remains_unlinked():
    init_db(reset=True)
    provider = MockProvider()
    broker = PaperBroker(provider)
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = min((q for q in chain.quotes if q.option_type == "CE"),
                key=lambda q: abs(q.strike - chain.spot))

    pos = broker.open_position(
        inst, "LONG", quote, "paper", provider.now(), chain.spot, params={})

    assert pos.entry_intent_id is None


def test_pre_ack_place_exception_remains_uncertain_and_reconciliation_required():
    class _PlaceFails(_FilledClient):
        def place(self, req):
            self.requests.append(req)
            raise RuntimeError("risk rejected before acknowledgement")

        def status(self, order_id):
            raise AssertionError("an unacknowledged order must not be polled")

    init_db(reset=True)
    provider = MockProvider()
    broker = LiveBroker(provider, _PlaceFails(0.0), poll_seconds=0.0, timeout_seconds=0.0)
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = min((q for q in chain.quotes if q.option_type == "CE"),
                key=lambda q: abs(q.strike - chain.spot))

    pos = broker.open_position(
        inst, "LONG", quote, "signal", provider.now(), chain.spot, params={})

    assert pos is None
    with SessionLocal() as session:
        final_event = session.scalars(
            select(ExecutionOrderEvent).order_by(ExecutionOrderEvent.id.desc())).first()
        assert final_event.kind == "STATUS_OBSERVED"
        assert final_event.broker_status == "ERROR"
        intent = session.scalar(select(ExecutionIntent))
        state = live_broker_module.ExecutionLifecycleStore(session).state_for(
            intent.client_intent_id)
        assert state.terminal is False
        assert state.reconciliation_required is True
        journal = session.scalar(select(OrderJournal).where(OrderJournal.intent == "ENTRY"))
        assert journal.status == "WORKING"


def test_journal_commit_failure_rolls_back_before_lifecycle_write(monkeypatch):
    init_db(reset=True)
    broker = LiveBroker(MockProvider(), _FilledClient(100.0), poll_seconds=0.0,
                        timeout_seconds=0.0)
    original_commit = broker.s.commit
    calls = 0

    def fail_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("journal disk error")
        return original_commit()

    monkeypatch.setattr(broker.s, "commit", fail_once)
    assert broker._journal_open(
        OrderRequest("RELIANCE", "NSE", "BUY", 1, "MARKET"),
        "ENTRY", "equity", {"inst_key": "NIFTY"}) is None
    assert broker.s.in_transaction() is False
    intent = live_broker_module.ExecutionLifecycleStore(broker.s).create_intent(
        live_broker_module.NewExecutionIntent(
            deployment_id=1, broker="kite", account_scope="default",
            connection_scope=live_broker_module.KITE_LEGACY_CONNECTION_SCOPE,
            intent="ENTRY", instrument_key="NIFTY",
            tradingsymbol="RELIANCE", exchange="NSE", side="BUY", product="MIS",
            order_type="MARKET", requested_qty=1, limit_price=None,
            decision_price=100.0, signal_at=dt.datetime(2026, 8, 9, 10),
            strategy_key=None, strategy_version=None), {}, dt.datetime(2026, 8, 9, 10))
    assert intent.client_intent_id


def test_journal_terminalization_is_deployment_scoped():
    init_db(reset=True)
    broker = LiveBroker(MockProvider(), _FilledClient(100.0), poll_seconds=0.0,
                        timeout_seconds=0.0, deployment_id=1)
    broker.s.add(Deployment(id=2, name="other", account_id="other"))
    for deployment_id in (2, 1):
        broker.s.add(OrderJournal(
            deployment_id=deployment_id, order_id="SAME", tradingsymbol="RELIANCE",
            instrument_key="NIFTY", side="BUY", kind="equity", intent="ENTRY",
            qty=1, status="WORKING", placed_at=dt.datetime(2026, 8, 9, 10)))
    broker.s.commit()

    broker.journal_mark_terminal("SAME", "ADOPTED", 1, 100.0)

    rows = list(broker.s.scalars(select(OrderJournal).order_by(OrderJournal.deployment_id)))
    assert [(row.deployment_id, row.status) for row in rows] == [
        (1, "TERMINAL"), (2, "WORKING")]
