"""Receipt propagation tests for money rows.

Each test names the ownership seam that would otherwise lose immutable provenance.
"""
from __future__ import annotations

import datetime as dt

import pytest
from app.db.models import ExecutionIntent
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.engine.execution_lifecycle import ExecutionLifecycleStore, NewExecutionIntent
from app.db.session import SessionLocal
from app.providers.mock import MockProvider


ADDRESS = "sha256:" + "a" * 64
NOW = dt.datetime(2026, 8, 13, 10, 0)


def test_paper_position_and_trade_copy_the_entry_receipt(monkeypatch):
    """A paper fill or its later exit must not lose the receipt that authorised it."""
    init_db(reset=True)
    provider = MockProvider()
    broker = PaperBroker(provider, owner_id="owner", broker_account_id="account.default")
    # Receipt authority has a separate direct seam test below.  This test isolates
    # position/trade propagation after that owning verification has succeeded.
    monkeypatch.setattr(broker, "_require_current_entry_receipt", lambda **_: None)
    inst = get_instrument("NIFTY")
    chain = provider.get_option_chain(inst)
    quote = next(item for item in chain.quotes if item.option_type == "CE")

    position = broker.open_position(
        inst, "LONG", quote, "admitted", NOW, chain.spot,
        strategy_key="expanding_z_v4", strategy_version="v4",
        admission_address=ADDRESS,
    )
    trade = broker.close_position(position, quote.ltp, "exit", NOW, chain.spot)

    assert position.admission_address == ADDRESS
    assert trade.admission_address == ADDRESS
    assert trade.strategy_key == position.strategy_key
    assert trade.strategy_version == position.strategy_version


def test_manual_open_without_a_receipt_cannot_book_new_exposure():
    """The manual endpoint cannot bypass the runner's signal-entry receipt gate."""
    init_db(reset=True)
    provider = MockProvider()
    broker = PaperBroker(provider, owner_id="owner", broker_account_id="account.default")
    inst = get_instrument("NIFTY")
    position, reason = broker.manual_open(
        inst, "LONG", provider.get_option_chain(inst), broker.settings, NOW)

    assert position is None
    assert reason == "ADMISSION_REQUIRED"
    assert broker.position_for(inst.key) is None


def test_paper_open_seam_refuses_direct_receiptless_booking():
    """A caller cannot bypass the runner and write a new paper position directly."""
    init_db(reset=True)
    provider = MockProvider()
    broker = PaperBroker(provider, owner_id="owner", broker_account_id="account.default")
    inst = get_instrument("NIFTY")
    quote = next(item for item in provider.get_option_chain(inst).quotes if item.option_type == "CE")

    with pytest.raises(ValueError, match="ADMISSION_REQUIRED"):
        broker.open_position(inst, "LONG", quote, "bypass", NOW, 25_000.0)


def test_paper_open_seam_refuses_a_hash_shaped_forged_receipt(monkeypatch):
    """The owning paper-book seam verifies current owner-local authority itself."""
    init_db(reset=True)
    provider = MockProvider()
    broker = PaperBroker(provider, owner_id="owner", broker_account_id="account.default")
    inst = get_instrument("NIFTY")
    quote = next(item for item in provider.get_option_chain(inst).quotes if item.option_type == "CE")
    calls = []

    def stale(**kwargs):
        calls.append(kwargs)
        raise ValueError("RECEIPT_STALE")

    monkeypatch.setattr(broker, "_require_current_entry_receipt", stale)
    with pytest.raises(ValueError, match="RECEIPT_STALE"):
        broker.open_position(
            inst, "LONG", quote, "forged", NOW, 25_000.0,
            strategy_key="expanding_z_v4", strategy_version="v4",
            admission_address="sha256:" + "f" * 64)

    assert len(calls) == 1
    assert broker.position_for(inst.key) is None


def test_transient_legacy_recovery_object_cannot_bypass_receipt_requirement():
    """A caller cannot forge recovery authority by constructing an unpersisted intent."""
    init_db(reset=True)
    provider = MockProvider()
    broker = PaperBroker(provider, owner_id="owner", broker_account_id="account.default")
    inst = get_instrument("NIFTY")
    quote = next(item for item in provider.get_option_chain(inst).quotes if item.option_type == "CE")
    forged = ExecutionIntent(
        client_intent_id="forged", deployment_id=1, owner_id="owner",
        broker_account_id="account.default", broker="mock", account_scope="paper",
        connection_scope="mock:paper", broker_tag="forged", intent="ENTRY",
        instrument_key="NIFTY", tradingsymbol="NIFTYOPT", exchange="NFO", side="BUY",
        product=None, order_type="MARKET", requested_qty=1, limit_price=None,
        decision_price=100.0, signal_at=NOW, strategy_key="legacy", strategy_version="v",
        admission_address=None, context_json="{}", created_at=NOW,
    )

    with pytest.raises(ValueError, match="ADMISSION_REQUIRED"):
        broker.open_position(
            inst, "LONG", quote, "forged", NOW, 25_000.0,
            entry_intent_id="forged", recovery_intent=forged)


def test_persisted_original_intent_books_a_fill_when_receipt_stales_after_submit(monkeypatch):
    """A filled order is booked/protected from its durable intent, not re-authorised."""
    init_db(reset=True)
    provider = MockProvider()
    broker = PaperBroker(provider, owner_id="owner", broker_account_id="account.default")
    inst = get_instrument("NIFTY")
    quote = next(item for item in provider.get_option_chain(inst).quotes if item.option_type == "CE")
    store = ExecutionLifecycleStore(
        broker.s, owner_id="owner", broker_account_id="account.default")
    intent = store.create_intent(NewExecutionIntent(
        deployment_id=1, owner_id="owner", broker_account_id="account.default",
        broker="mock", account_scope="paper", connection_scope="mock:paper",
        intent="ENTRY", instrument_key="NIFTY", tradingsymbol=quote.tradingsymbol,
        exchange="NFO", side="BUY", product=None, order_type="MARKET",
        requested_qty=quote.lot_size, limit_price=None, decision_price=quote.ltp,
        signal_at=NOW, strategy_key="expanding_z_v4", strategy_version="v4",
        admission_address=ADDRESS), {}, NOW)
    checks = []
    monkeypatch.setattr(
        broker, "_require_current_entry_receipt",
        lambda **kwargs: checks.append(kwargs) or (_ for _ in ()).throw(ValueError("RECEIPT_STALE")),
    )

    position = broker.open_position(
        inst, "LONG", quote, "filled-before-helper-change", NOW, 25_000.0,
        strategy_key=intent.strategy_key, strategy_version=intent.strategy_version,
        entry_intent_id=intent.client_intent_id, admission_address=intent.admission_address,
        recovery_intent=intent)

    assert checks == []
    assert position.entry_intent_id == intent.client_intent_id
    assert position.admission_address == intent.admission_address


def test_lifecycle_intent_seam_refuses_direct_receiptless_creation():
    """A live submit cannot create an intent whose durable provenance is null."""
    init_db(reset=True)
    with SessionLocal() as session:
        store = ExecutionLifecycleStore(
            session, owner_id="owner", broker_account_id="account.default")
        request = NewExecutionIntent(
            deployment_id=1, owner_id="owner", broker_account_id="account.default",
            broker="mock", account_scope="paper", connection_scope="mock:paper",
            intent="ENTRY", instrument_key="NIFTY", tradingsymbol="NIFTYOPT",
            exchange="NFO", side="BUY", product=None, order_type="MARKET",
            requested_qty=1, limit_price=None, decision_price=100.0, signal_at=NOW,
            strategy_key="expanding_z_v4", strategy_version="v4", admission_address=None,
        )
        with pytest.raises(ValueError, match="ADMISSION_REQUIRED"):
            store.create_intent(request, {}, NOW)
