"""Fail-closed tests for the only two real-money entry paths.

The fake lifecycle store records commit boundaries while the fake client records
the external submit. The observable order is the safety contract.
"""
import datetime as dt
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.instruments import get_instrument
from app.db.models import ExecutionIntent, ExecutionOrderEvent, Position, Trade
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

    res, filled, avg, client_intent_id = _entry(broker)

    assert timeline == ["intent_commit", "submit_started_commit", "place",
                        "ack_commit", "status"]
    assert res.status == "FILLED"
    assert (filled, avg, client_intent_id) == (10, 101.0, "a" * 32)
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


def test_options_entry_links_durable_intent_to_position_and_trade():
    init_db(reset=True)
    provider = MockProvider()
    client = _FilledClient(101.25)
    broker = LiveBroker(provider, client, poll_seconds=0.0, timeout_seconds=0.0)
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
            "SUBMIT_STARTED", "ACKNOWLEDGED", "STATUS_OBSERVED"]
        assert stored_pos.entry_intent_id == intent.client_intent_id == pos.entry_intent_id

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


def test_pre_ack_place_failure_closes_the_durable_intent_as_failed():
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
        assert final_event.broker_status == "FAILED"
