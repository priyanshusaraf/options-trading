from __future__ import annotations

import subprocess
import sys
from dataclasses import replace

import pytest

from app.engine import charges


V1 = "zerodha_charges_v1"
V2 = "zerodha_resident_individual_standard_charges_v2"


def _v2(segment: str, side: str, price, qty: int) -> dict:
    return charges.compute_charges_exact(
        segment, side, price, qty, schedule_id=V2
    )


def test_nmt_004_corrected_stt_rates_and_official_rounding_examples():
    option = _v2("NFO", "SELL", "200.00", 75)
    future = _v2("NFO_FUT", "SELL", "24000.00", 75)
    assert option["stt_ctt_minor"] == 2_300
    assert future["stt_ctt_minor"] == 90_000

    # Zerodha's published examples: ₹4.50 STT rounds to ₹5; ₹375 is exact.
    assert _v2("NFO", "SELL", "60.00", 50)["stt_ctt_minor"] == 500
    assert _v2("NFO_FUT", "SELL", "750000.00", 1)["stt_ctt_minor"] == 37_500


def test_v2_price_and_every_component_close_in_integer_paise():
    out = _v2("NFO", "SELL", "1000.005", 10)
    assert out["price_minor"] == 100_001
    assert out["turnover_minor"] == 1_000_010
    component_keys = (
        "brokerage_minor",
        "stt_ctt_minor",
        "exchange_txn_minor",
        "sebi_minor",
        "stamp_minor",
        "dp_minor",
        "gst_minor",
    )
    assert all(type(out[key]) is int and out[key] >= 0 for key in component_keys)
    assert out["total_minor"] == sum(out[key] for key in component_keys)
    assert out["rounding_policy"] == charges.ROUNDING_POLICY_V2


def test_v2_exact_breakdown_and_compatibility_projection_are_equal():
    exact = _v2("NFO", "SELL", "172.80", 75)
    projected = charges.compute_charges(
        "NFO", "SELL", "172.80", 75, schedule_id=V2
    )
    for name in charges.CHARGE_COMPONENTS:
        assert projected[f"{name}_minor"] == exact[f"{name}_minor"]
        assert projected[name] == exact[f"{name}_minor"] / 100
    assert projected["total_minor"] == exact["total_minor"]
    assert projected["total"] == exact["total_minor"] / 100


@pytest.mark.parametrize(
    ("segment", "expected_exchange_minor"),
    [
        ("NFO", 3_553),
        ("BFO", 3_250),
        ("NSE_EQ", 307),
        ("BSE_EQ", 375),
        ("NFO_FUT", 183),
    ],
)
def test_every_supported_v2_segment_has_an_exact_two_side_answer(
        segment, expected_exchange_minor):
    buy = _v2(segment, "BUY", "100000.00", 1)
    sell = _v2(segment, "SELL", "100000.00", 1)
    assert buy["exchange_txn_minor"] == expected_exchange_minor
    assert sell["exchange_txn_minor"] == expected_exchange_minor
    assert buy["schedule_address"] == sell["schedule_address"]
    assert buy["total_minor"] == sum(
        buy[f"{component}_minor"] for component in charges.CHARGE_COMPONENTS
    )
    assert sell["total_minor"] == sum(
        sell[f"{component}_minor"] for component in charges.CHARGE_COMPONENTS
    )


def test_standard_equity_delivery_dp_charge_closes_to_published_1534_paise():
    sell = _v2("NSE_EQ", "SELL", "100.00", 1)
    # ₹13 base plus ₹2.34 GST. Other GST bases are zero at this tiny turnover.
    assert sell["dp_minor"] == 1_300
    assert sell["gst_minor"] == 234


@pytest.mark.parametrize("segment", ["TYPO", "", "NFO_FUT "])
def test_unknown_segments_refuse_instead_of_falling_back_to_nfo(segment):
    with pytest.raises(charges.ChargeScheduleRefusal, match="unknown segment") as exc:
        _v2(segment, "BUY", "100.00", 1)
    assert exc.value.code == "CHARGE_SEGMENT_UNKNOWN"


@pytest.mark.parametrize(
    "segment",
    [
        "BFO_FUT",
        "NSE_INTRADAY",
        "BSE_INTRADAY",
        "MCX",
        "MCX_FUT",
        "NCDEX",
        "NCDEX_FUT",
    ],
)
def test_unverified_segments_are_typed_refusals(segment):
    with pytest.raises(charges.ChargeScheduleRefusal, match="unverified") as exc:
        _v2(segment, "BUY", "100.00", 1)
    assert exc.value.code == "CHARGE_SEGMENT_UNVERIFIED"


def test_unknown_or_stale_schedule_identity_refuses():
    with pytest.raises(charges.ChargeScheduleRefusal) as unknown:
        charges.compute_charges_exact(
            "NFO", "BUY", "100", 1, schedule_id="unverified_schedule"
        )
    assert unknown.value.code == "CHARGE_SCHEDULE_UNKNOWN"

    with pytest.raises(charges.ChargeScheduleRefusal) as stale:
        charges.compute_charges_exact(
            "NFO", "BUY", "100", 1, schedule_id=V2,
            expected_schedule_address="sha256:" + "0" * 64,
        )
    assert stale.value.code == "CHARGE_SCHEDULE_STALE"


@pytest.mark.parametrize(
    ("side", "price", "qty", "code"),
    [
        ("HOLD", "100", 1, "CHARGE_SIDE_INVALID"),
        ("buy", "100", 1, "CHARGE_SIDE_INVALID"),
        ("BUY", "-0.01", 1, "CHARGE_PRICE_INVALID"),
        ("BUY", float("nan"), 1, "CHARGE_PRICE_INVALID"),
        ("BUY", float("inf"), 1, "CHARGE_PRICE_INVALID"),
        ("BUY", "100", 0, "CHARGE_QUANTITY_INVALID"),
        ("BUY", "100", True, "CHARGE_QUANTITY_INVALID"),
        ("BUY", "1000000000001", 1, "CHARGE_TURNOVER_EXCESSIVE"),
    ],
)
def test_invalid_inputs_refuse_before_a_charge_answer(side, price, qty, code):
    with pytest.raises(charges.ChargeScheduleRefusal) as exc:
        _v2("NFO", side, price, qty)
    assert exc.value.code == code


@pytest.mark.parametrize(
    ("price", "qty", "refusal"),
    [
        ("999999999999.99", 1, None),
        ("1000000000000.00", 1, None),
        ("1000000000000.01", 1, "CHARGE_TURNOVER_EXCESSIVE"),
        ("1e1000000", 1, "CHARGE_TURNOVER_EXCESSIVE"),
    ],
)
def test_decimal_turnover_boundary_is_closed_and_typed(price, qty, refusal):
    if refusal is None:
        assert _v2("NFO", "BUY", price, qty)["turnover_minor"] <= (
            charges.MAX_TURNOVER_MINOR
        )
        return
    with pytest.raises(charges.ChargeScheduleRefusal) as exc:
        _v2("NFO", "BUY", price, qty)
    assert exc.value.code == refusal


def test_legacy_v1_known_answers_are_reconstructible_but_unknowns_refuse():
    old = charges.compute_charges(
        "NFO", "BUY", 172.8, 75, schedule_id=V1
    )
    assert old["total"] == 29.36
    assert old["schedule_id"] == V1
    with pytest.raises(charges.ChargeScheduleRefusal):
        charges.compute_charges("TYPO", "BUY", 172.8, 75, schedule_id=V1)


def test_v1_and_v2_documents_have_distinct_stable_content_addresses():
    v1 = charges.charge_schedule_document(V1)
    v2 = charges.charge_schedule_document(V2)
    assert v1["address"].startswith("sha256:")
    assert v2["address"].startswith("sha256:")
    assert v1["address"] != v2["address"]
    assert charges.charge_schedule_address(V2) == v2["address"]
    restarted = subprocess.check_output(
        [
            sys.executable,
            "-c",
            (
                "from app.engine.charges import charge_schedule_address; "
                f"print(charge_schedule_address({V2!r}))"
            ),
        ],
        text=True,
    ).strip()
    assert restarted == v2["address"]


def test_round_trip_components_conserve_across_direction_and_replay():
    first = charges.round_trip_charges_exact(
        "NFO", "LONG", "100.00", "95.00", 10, schedule_id=V2
    )
    replay = charges.round_trip_charges_exact(
        "NFO", "LONG", "100.00", "95.00", 10, schedule_id=V2
    )
    assert first == replay
    assert first["entry"]["side"] == "BUY"
    assert first["exit"]["side"] == "SELL"
    assert first["total_minor"] == (
        first["entry"]["total_minor"] + first["exit"]["total_minor"]
    )
    assert first["total_minor"] == sum(
        first[f"{component}_minor"] for component in charges.CHARGE_COMPONENTS
    )


def test_distinct_research_and_paper_option_paths_share_v2_and_restart_receipt(
        admitted_entry_identity):
    from app.backtest.premium import _close_premium
    from app.core.instruments import get_instrument
    from app.db.models import Position, Trade
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default"
    )
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    admission = admitted_entry_identity(broker.s)
    position = broker.open_position(
        instrument, "LONG", quote, "V2 PAPER", broker.provider.now(), chain.spot,
        **admission,
    )
    entry_receipt = broker.charge_result_receipt(position)
    assert position.entry_intent_id is not None
    assert entry_receipt["scheme"] == "paper-charge-result/2"
    assert entry_receipt["entry_intent_id"] == position.entry_intent_id
    assert entry_receipt["entry_lifecycle_state"] == "KNOWN_INTENT"
    assert entry_receipt["entry_schedule_id"] == V2
    exit_price = quote.ltp * 1.25
    paper_trade = broker.close_position(
        position, exit_price, "V2 PAPER EXIT", broker.provider.now(), chain.spot
    )
    paper_receipt = broker.charge_result_receipt(paper_trade)

    research_trade = _close_premium(
        {
            "qty": quote.lot_size,
            "entry_fill": quote.ltp,
            "direction": "LONG",
            "entry_time": 1,
            "entry_idx": 1,
            "mae_pct": 0.0,
            "notional": quote.ltp * quote.lot_size,
        },
        exit_price,
        2,
        2,
        instrument.segment,
        "SYNTHETIC_RESEARCH",
    )
    assert paper_trade.charges_total == research_trade.charges
    assert paper_receipt["entry_schedule_id"] == V2
    assert paper_receipt["exit_schedule_id"] == V2
    assert paper_receipt["entry_schedule_address"] == entry_receipt["entry_schedule_address"]
    assert paper_receipt["exit_rounding_policy"]["id"] == charges.ROUNDING_POLICY_V2
    assert paper_receipt["address"].startswith("sha256:")

    trade_id = paper_trade.id
    broker.s.close()
    restarted = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default"
    )
    reloaded = restarted.s.get(Trade, trade_id)
    assert restarted.charge_result_receipt(reloaded) == paper_receipt


@pytest.mark.parametrize("family", ["options", "equity", "futures"])
def test_equal_valued_paper_entries_have_distinct_lifecycle_intents_and_receipts(
        admitted_entry_identity, family):
    import datetime as dt
    from sqlalchemy import func, select

    from app.core.instruments import get_instrument
    from app.db.models import ExecutionOrderEvent, Trade
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    admission = admitted_entry_identity(broker.s)
    opened_at = dt.datetime(2026, 8, 30, 10, 0)
    receipts = []
    trade_ids = []
    intent_ids = []
    for index in range(2):
        if family == "options":
            chain = broker.provider.get_option_chain(instrument)
            quote = next(q for q in chain.quotes if q.option_type == "CE")
            position = broker.open_position(
                instrument, "LONG", quote, f"EQUAL-{index}", opened_at, chain.spot,
                **admission)
            trade = broker.close_position(
                position, quote.ltp * 1.1, f"EQUAL-{index}",
                opened_at + dt.timedelta(minutes=15), chain.spot)
        elif family == "equity":
            position = broker.open_equity_position(
                instrument, "LONG", 100.0, 200, "NSE_INTRADAY",
                f"EQUAL-{index}", opened_at, margin=4_000.0, params={}, **admission)
            trade = broker.close_equity_position(
                position, 102.0, f"EQUAL-{index}",
                opened_at + dt.timedelta(minutes=15))
        else:
            position = broker.open_futures_position(
                instrument, "LONG", 24_000.0, 75, "NFO_FUT",
                f"EQUAL-{index}", opened_at, dt.date(2026, 9, 24), 120_000.0,
                params={}, **admission)
            trade = broker.close_futures_position(
                position, 24_100.0, f"EQUAL-{index}",
                opened_at + dt.timedelta(minutes=15))
        assert position.entry_intent_id == trade.entry_intent_id
        intent_ids.append(trade.entry_intent_id)
        trade_ids.append(trade.id)
        receipt = broker.charge_result_receipt(trade)
        assert receipt["scheme"] == "paper-charge-result/2"
        assert receipt["entry_intent_id"] == trade.entry_intent_id
        receipts.append(receipt)

    assert None not in intent_ids
    assert intent_ids[0] != intent_ids[1]
    assert broker.s.scalar(select(func.count()).select_from(ExecutionOrderEvent).where(
        ExecutionOrderEvent.client_intent_id.in_(intent_ids))) == 0
    assert receipts[0]["entry_charge_minor"] == receipts[1]["entry_charge_minor"]
    broker.s.close()

    restarted = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    assert [restarted.charge_result_receipt(restarted.s.get(Trade, trade_id))
            for trade_id in trade_ids] == receipts


def test_supplied_paper_intent_cannot_book_a_second_effect_after_full_close(
        admitted_entry_identity):
    from sqlalchemy import func, select

    from app.core.instruments import get_instrument
    from app.db.models import ExecutionIntent, Position, Trade
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(q for q in chain.quotes if q.option_type == "CE")
    admission = admitted_entry_identity(broker.s)
    opened_at = broker.provider.now()
    position = broker.open_position(
        instrument, "LONG", quote, "ONE EFFECT", opened_at, chain.spot, **admission)
    intent_id = position.entry_intent_id
    intent = broker.s.get(ExecutionIntent, intent_id)
    broker.close_position(
        position, quote.ltp * 1.1, "ONE EFFECT", opened_at, chain.spot)
    cash_after = broker.cash()
    with pytest.raises(ValueError, match="ENTRY_INTENT_ALREADY_USED"):
        broker.open_position(
            instrument, "LONG", quote, "REPLAY", opened_at, chain.spot,
            entry_intent_id=intent_id, recovery_intent=intent, **admission)
    assert broker.cash() == cash_after
    assert broker.s.scalar(select(func.count()).select_from(Position)) == 0
    assert broker.s.scalar(select(func.count()).select_from(Trade)) == 1


def test_corrupt_supplied_intent_refuses_new_money_before_effect(
        admitted_entry_identity):
    from sqlalchemy import func, select

    from app.core.instruments import get_instrument
    from app.db.models import ExecutionIntent, Position, Trade
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    admission = admitted_entry_identity(broker.s)
    opened_at = broker.provider.now()
    position = broker.open_position(
        instrument, "LONG", quote, "TEMPLATE", opened_at, chain.spot, **admission)
    original = broker.s.get(ExecutionIntent, position.entry_intent_id)
    values = {
        column.name: getattr(original, column.name)
        for column in ExecutionIntent.__table__.columns
    }
    values.update(
        client_intent_id="9" * 32,
        broker_tag="pti-" + "9" * 16,
        requested_qty=original.requested_qty + 1,
    )
    corrupt = ExecutionIntent(**values)
    broker.s.add(corrupt)
    broker.s.commit()
    before_cash = broker.cash()
    before_positions = broker.s.scalar(select(func.count()).select_from(Position))
    before_trades = broker.s.scalar(select(func.count()).select_from(Trade))
    with pytest.raises(ValueError, match="ENTRY_INTENT_SCOPE_MISMATCH"):
        broker.open_position(
            instrument, "LONG", quote, "CORRUPT", opened_at, chain.spot,
            entry_intent_id=corrupt.client_intent_id, recovery_intent=corrupt,
            **admission)
    assert broker.cash() == before_cash
    assert broker.s.scalar(select(func.count()).select_from(Position)) == before_positions
    assert broker.s.scalar(select(func.count()).select_from(Trade)) == before_trades


@pytest.mark.parametrize("same_intent", [True, False])
def test_sqlite_concurrent_paper_entry_intents_serialize_before_money(
        admitted_entry_identity, same_intent):
    import datetime as dt
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import func, select

    from app.core.instruments import get_instrument
    from app.db.models import ExecutionIntent, Position
    from app.db.session import SessionLocal, init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    opened_at = dt.datetime(2026, 8, 30, 10, 0)
    seed = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    admission = admitted_entry_identity(seed.s)
    account = seed.account
    intent_ids = ["a" * 32, "a" * 32 if same_intent else "b" * 32]
    for intent_id in sorted(set(intent_ids)):
        seed.s.add(ExecutionIntent(
            client_intent_id=intent_id, deployment_id=seed.deployment_id,
            owner_id=seed.owner_id, broker_account_id=seed.broker_account_id,
            broker=account.broker, account_scope=account.external_account_id,
            connection_scope="paper", broker_tag=f"pti-{intent_id[:16]}",
            intent="ENTRY", instrument_key="NIFTY", tradingsymbol="NIFTY 50",
            exchange="NSE_INTRADAY", side="BUY", product="MIS",
            order_type="MARKET", requested_qty=200, limit_price=None,
            decision_price=100.0, signal_at=opened_at,
            strategy_key=admission["strategy_key"],
            strategy_version=admission["strategy_version"],
            admission_address=admission["admission_address"],
            graph_address=admission["graph_address"],
            attribution_state=admission["attribution_state"],
            context_json='{"schema":"paper-entry-lifecycle/1"}',
            created_at=opened_at))
    seed.s.commit()
    cash_before = seed.cash()
    seed.s.close()
    barrier = threading.Barrier(2)

    def open_once(intent_id):
        broker = PaperBroker(
            MockProvider(), owner_id="owner", broker_account_id="account.default")
        try:
            intent = broker.s.get(ExecutionIntent, intent_id)
            barrier.wait(timeout=10)
            position = broker.open_equity_position(
                get_instrument("NIFTY"), "LONG", 100.0, 200, "NSE_INTRADAY",
                "CONCURRENT", opened_at, margin=4_000.0, params={},
                entry_intent_id=intent_id, recovery_intent=intent, **admission)
            return ("opened", position.entry_intent_id)
        except ValueError as exc:
            return ("refused", str(exc))
        finally:
            broker.s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(open_once, intent_ids))

    with SessionLocal() as session:
        positions = list(session.scalars(select(Position).order_by(Position.id)))
        cash_after = seed.settings.initial_capital
        from app.db.models import CapitalState
        capital = session.get(CapitalState, ("account.default", "paper"))
        cash_after = capital.cash
    if same_intent:
        assert sorted(result[0] for result in results) == ["opened", "refused"]
        assert any(result == ("refused", "ENTRY_INTENT_ALREADY_USED")
                   for result in results)
        assert len(positions) == 1
        assert positions[0].entry_intent_id == "a" * 32
        expected_cost = 4_000.0 + positions[0].entry_charges
        assert cash_after == pytest.approx(cash_before - expected_cost)
    else:
        assert sorted(result[0] for result in results) == ["opened", "opened"]
        assert len(positions) == 2
        assert {position.entry_intent_id for position in positions} == {"a" * 32, "b" * 32}
        assert cash_after == pytest.approx(
            cash_before - sum(position.entry_cost for position in positions))


def test_attempted_rebind_full_close_restart_keeps_original_intent_consumed_concurrently(
        admitted_entry_identity):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import func, select, text
    from sqlalchemy.exc import IntegrityError

    from app.core.instruments import get_instrument
    from app.db.models import CapitalState, ExecutionIntent, Position, Trade
    from app.db.session import SessionLocal, init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    admission = admitted_entry_identity(broker.s)
    opened_at = broker.provider.now()
    position = broker.open_position(
        instrument, "LONG", quote, "ORIGINAL", opened_at, chain.spot, **admission)
    original_id = position.entry_intent_id
    original = broker.s.get(ExecutionIntent, original_id)
    clone_values = {
        column.name: getattr(original, column.name)
        for column in ExecutionIntent.__table__.columns
    }
    clone_values.update(
        client_intent_id="f" * 32,
        broker_tag="pti-" + "f" * 16,
    )
    broker.s.add(ExecutionIntent(**clone_values))
    broker.s.commit()
    with pytest.raises(IntegrityError, match="entry_intent_id is immutable"):
        broker.s.execute(text(
            "UPDATE positions SET entry_intent_id=:clone WHERE id=:id"),
            {"clone": "f" * 32, "id": position.id})
        broker.s.commit()
    broker.s.rollback()
    trade = broker.close_position(
        position, quote.ltp, "FULL CLOSE", opened_at, chain.spot)
    trade_id = trade.id
    cash_after = broker.cash()
    broker.s.close()

    barrier = threading.Barrier(2)

    def replay_once():
        contender = PaperBroker(
            MockProvider(), owner_id="owner", broker_account_id="account.default")
        try:
            intent = contender.s.get(ExecutionIntent, original_id)
            barrier.wait(timeout=10)
            contender.open_position(
                instrument, "LONG", quote, "REPLAY", opened_at, chain.spot,
                entry_intent_id=original_id, recovery_intent=intent, **admission)
            return "opened"
        except ValueError as exc:
            return str(exc)
        finally:
            contender.s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: replay_once(), range(2)))
    assert results == ["ENTRY_INTENT_ALREADY_USED", "ENTRY_INTENT_ALREADY_USED"]
    with SessionLocal() as session:
        assert session.get(Trade, trade_id).entry_intent_id == original_id
        assert session.scalar(select(func.count()).select_from(Trade)) == 1
        assert session.scalar(select(func.count()).select_from(Position)) == 0
        assert session.get(CapitalState, ("account.default", "paper")).cash == cash_after


def test_generated_paper_intent_collision_retries_only_identity(monkeypatch,
                                                                admitted_entry_identity):
    from types import SimpleNamespace

    from app.core.instruments import get_instrument
    from app.db.models import ExecutionIntent
    from app.db.session import init_db
    from app.engine import broker as broker_module
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(q for q in chain.quotes if q.option_type == "CE")
    admission = admitted_entry_identity(broker.s)
    now = broker.provider.now()
    colliding = "c" * 32
    replacement = "d" * 32
    broker.s.add(ExecutionIntent(
        client_intent_id=colliding, deployment_id=broker.deployment_id,
        owner_id=broker.owner_id, broker_account_id=broker.broker_account_id,
        broker=broker.account.broker, account_scope=broker.account.external_account_id,
        connection_scope="paper", broker_tag=f"pti-{colliding[:16]}", intent="ENTRY",
        instrument_key="OTHER", tradingsymbol="OTHER", exchange="NFO", side="BUY",
        product=None, order_type="MARKET", requested_qty=1, limit_price=None,
        decision_price=1.0, signal_at=now, strategy_key=admission["strategy_key"],
        strategy_version=admission["strategy_version"],
        admission_address=admission["admission_address"],
        graph_address=admission["graph_address"],
        attribution_state=admission["attribution_state"], context_json="{}",
        created_at=now))
    broker.s.commit()
    generated = iter((colliding, replacement))
    real_uuid4 = broker_module.uuid.uuid4

    def next_uuid():
        try:
            return SimpleNamespace(hex=next(generated))
        except StopIteration:
            return real_uuid4()

    monkeypatch.setattr(broker_module.uuid, "uuid4", next_uuid)

    position = broker.open_position(
        instrument, "LONG", quote, "COLLISION RETRY", now, chain.spot, **admission)
    assert position.entry_intent_id == replacement
    assert broker.s.get(ExecutionIntent, colliding).instrument_key == "OTHER"


def test_receipt_v2_binds_intent_and_refuses_intent_scope_mutations(
        admitted_entry_identity):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.core.instruments import get_instrument
    from app.db.models import ExecutionIntent, Position, Trade
    from app.db.session import init_db
    from app.engine import charges as charge_module
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    admission = admitted_entry_identity(broker.s)
    opened_at = broker.provider.now()
    position = broker.open_equity_position(
        instrument, "LONG", 100.0, 200, "NSE_INTRADAY", "ADDRESS",
        opened_at, margin=4_000.0, params={}, **admission)
    original = broker.charge_result_receipt(position)
    intent = broker.s.get(ExecutionIntent, position.entry_intent_id)

    for field, value in (
        ("owner_id", "other-owner"),
        ("instrument_key", "BANKNIFTY"),
        ("requested_qty", intent.requested_qty + 1),
    ):
        original_value = getattr(intent, field)
        setattr(intent, field, value)
        broker.s.flush()
        with pytest.raises(charge_module.ChargeScheduleRefusal,
                           match="intent does not match|quantity"):
            broker.charge_result_receipt(position)
        broker.s.rollback()
        intent = broker.s.get(ExecutionIntent, position.entry_intent_id)
        assert getattr(intent, field) == original_value

    clone_values = {
        column.name: getattr(intent, column.name)
        for column in ExecutionIntent.__table__.columns
    }
    clone_values.update(
        client_intent_id="e" * 32,
        broker_tag="pti-" + "e" * 16,
    )
    broker.s.add(ExecutionIntent(**clone_values))
    broker.s.commit()
    original_id = position.entry_intent_id
    for rebound in ("e" * 32, None):
        with pytest.raises(IntegrityError, match="entry_intent_id is immutable"):
            broker.s.execute(text(
                "UPDATE positions SET entry_intent_id=:intent WHERE id=:id"),
                {"intent": rebound, "id": position.id})
            broker.s.commit()
        broker.s.rollback()
        assert broker.s.get(Position, position.id).entry_intent_id == original_id
    assert broker.charge_result_receipt(position) == original

    trade = broker.close_equity_position(position, 102.0, "IMMUTABLE", opened_at)
    trade_id = trade.id
    for rebound in ("e" * 32, None):
        with pytest.raises(IntegrityError, match="entry_intent_id is immutable"):
            broker.s.execute(text(
                "UPDATE trades SET entry_intent_id=:intent WHERE id=:id"),
                {"intent": rebound, "id": trade_id})
            broker.s.commit()
        broker.s.rollback()
        assert broker.s.get(Trade, trade_id).entry_intent_id == original_id
    broker.s.close()

    restarted = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    reloaded = restarted.s.get(Trade, trade_id)
    assert reloaded.entry_intent_id == original_id
    original_intent = restarted.s.get(ExecutionIntent, original_id)
    with pytest.raises(ValueError, match="ENTRY_INTENT_ALREADY_USED"):
        restarted.open_equity_position(
            instrument, "LONG", 100.0, 200, "NSE_INTRADAY", "REUSE",
            opened_at, margin=4_000.0, params={}, entry_intent_id=original_id,
            recovery_intent=original_intent, **admission)


def test_live_and_unsupported_paper_segments_preserve_v1_selection():
    from app.engine.broker import PaperBroker

    class LiveSelectionProbe(PaperBroker):
        MODE = "live"

    live = object.__new__(LiveSelectionProbe)
    paper = object.__new__(PaperBroker)
    assert live._charge_schedule_id("NFO") == V1
    assert paper._charge_schedule_id("NSE_INTRADAY") == V1
    assert paper._charge_schedule_id("BFO_FUT") == V1
    assert paper._charge_schedule_id("NFO") == V2
    live_answer = live._compute_charge("NFO", "BUY", 21.15, 75)
    assert live_answer["schedule_id"] == V1
    assert live._paper_entry_authority(live_answer) == {
        "paper_entry_charge_schedule_id": None,
        "paper_entry_charge_schedule_address": None,
    }
    assert live._paper_trade_authority(object(), live_answer) == {
        "paper_entry_charge_schedule_id": None,
        "paper_entry_charge_schedule_address": None,
        "paper_exit_charge_schedule_id": None,
        "paper_exit_charge_schedule_address": None,
    }


def test_preexisting_paper_v1_position_reconstructs_and_closes_under_v1(
        admitted_entry_identity, monkeypatch):
    from app.core.instruments import get_instrument
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default"
    )
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    admission = admitted_entry_identity(broker.s)
    monkeypatch.setattr(broker, "_charge_schedule_id", lambda _segment: V1)
    position = broker.open_position(
        instrument, "LONG", quote, "LEGACY V1", broker.provider.now(), chain.spot,
        **admission,
    )
    monkeypatch.undo()
    assert broker.charge_result_receipt(position)["entry_schedule_id"] == V1
    trade = broker.close_position(
        position, quote.ltp * 1.2, "LEGACY V1 EXIT", broker.provider.now(),
        chain.spot,
    )
    assert broker.charge_result_receipt(trade)["entry_schedule_id"] == V1
    assert broker.charge_result_receipt(trade)["exit_schedule_id"] == V1


def test_partial_allocations_are_deterministic_and_conserve_every_paise():
    breakdown = _v2("NFO", "SELL", "100.00", 10)
    total = breakdown["total_minor"]
    first = charges.allocate_minor_units(total, (4, 3, 3))
    replay = charges.allocate_minor_units(total, (4, 3, 3))
    assert first == replay
    assert sum(first) == total
    assert charges.allocate_minor_units(total, (10,)) == (total,)
    components = charges.allocate_charge_components(breakdown, (4, 3, 3))
    assert sum(row["total_minor"] for row in components) == total
    for component in charges.CHARGE_COMPONENTS:
        key = f"{component}_minor"
        assert sum(row[key] for row in components) == breakdown[key]


def test_paper_v2_partial_close_conserves_and_receipt_survives_restart(
        admitted_entry_identity):
    from app.core.instruments import get_instrument
    from app.db.models import Trade
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default"
    )
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    admission = admitted_entry_identity(broker.s)
    position = broker.open_position(
        instrument, "LONG", quote, "V2 PARTIAL", broker.provider.now(), chain.spot,
        **admission,
    )
    original_entry_minor = charges.monetary_minor(position.entry_charges)
    close_qty = max(1, quote.lot_size // 3)
    partial = broker.book_partial_close(
        position, close_qty, quote.ltp * 1.1, "PARTIAL", broker.provider.now(),
        chain.spot,
    )
    assert position.entry_intent_id == partial.entry_intent_id
    receipt = broker.charge_result_receipt(partial)
    assert receipt["entry_schedule_id"] == V2
    assert receipt["exit_schedule_id"] == V2
    assert receipt["partial_entry_allocation"] is True
    assert (
        charges.monetary_minor(position.entry_charges)
        + receipt["entry_charge_minor"]
        == original_entry_minor
    )
    assert position.entry_charges == (
        charges.monetary_minor(position.entry_charges) / 100
    )
    assert partial.charges_total == charges.monetary_minor(partial.charges_total) / 100
    assert broker.reconcile()["diff"] == 0.0

    trade_id = partial.id
    broker.s.close()
    restarted = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default"
    )
    reloaded = restarted.s.get(Trade, trade_id)
    assert restarted.charge_result_receipt(reloaded) == receipt


def test_schedule_document_binds_segment_product_units_sides_sources_and_rounding():
    document = charges.charge_schedule_document(V2)
    nfo = document["segments"]["NFO"]
    assert nfo["product_class"] == "equity_option_premium"
    assert nfo["turnover_unit"] == "price_minor_times_quantity"
    assert nfo["supported_sides"] == ["BUY", "SELL"]
    assert document["rounding_policy"]["id"] == charges.ROUNDING_POLICY_V2
    assert document["sources"]
    assert document["status"] == "verified_public_simulation_profile"
    assert document["application_mode"] == charges.APPLICATION_MODE_V2


def _open_collision_position(broker, admitted_entry_identity, *, reason="COLLISION"):
    from app.core.instruments import get_instrument

    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    quote = replace(quote, ltp=21.15, bid=21.10, ask=21.20)
    position = broker.open_position(
        instrument, "LONG", quote, reason, broker.provider.now(), chain.spot,
        **admitted_entry_identity(broker.s),
    )
    return position, chain.spot


def test_collision_paper_authority_is_durable_before_effect_and_restart(
        admitted_entry_identity):
    """FH-01/FH-02: rounded equality never becomes schedule authority."""
    from app.db.models import Position
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner",
                         broker_account_id="account.default")
    position, _spot = _open_collision_position(broker, admitted_entry_identity)
    assert position.paper_entry_charge_schedule_id == V2
    assert position.paper_entry_charge_schedule_address == charges.charge_schedule_address(V2)
    position_id = position.id
    broker.s.close()

    restarted = PaperBroker(MockProvider(), owner_id="owner",
                            broker_account_id="account.default")
    reloaded = restarted.s.get(Position, position_id)
    receipt = restarted.charge_result_receipt(reloaded)
    assert receipt["entry_authority_state"] == "KNOWN"
    assert receipt["entry_schedule_id"] == V2
    with pytest.raises(TypeError):
        restarted.charge_result_receipt(reloaded, expected_schedule_id=V1)


def test_incomplete_or_stale_paper_authority_refuses_before_any_effect(
        admitted_entry_identity, monkeypatch):
    """FH-02/FH-07: a caller label or malformed pair cannot reach money state."""
    from sqlalchemy import func, select
    from app.core.instruments import get_instrument
    from app.db.models import Position
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner",
                         broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    before_cash = broker.cash()
    before_positions = broker.s.scalar(select(func.count()).select_from(Position))
    original = broker._compute_charge

    def stale(*args, **kwargs):
        return {**original(*args, **kwargs), "schedule_address": "sha256:" + "0" * 64}

    monkeypatch.setattr(broker, "_compute_charge", stale)
    with pytest.raises(charges.ChargeScheduleRefusal, match="address") as exc:
        broker.open_position(
            instrument, "LONG", quote, "STALE", broker.provider.now(), chain.spot,
            **admitted_entry_identity(broker.s),
        )
    assert exc.value.code == "CHARGE_SCHEDULE_STALE"
    assert broker.cash() == before_cash
    assert broker.s.scalar(select(func.count()).select_from(Position)) == before_positions


@pytest.mark.parametrize("partial", [False, True])
def test_historical_null_entry_keeps_risk_reducing_exit_and_truth(
        admitted_entry_identity, partial):
    """FH-03/FH-04/FH-05: unknown history never blocks or gets relabelled."""
    from app.db.session import init_db
    from app.db.models import Position, Trade
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner",
                         broker_account_id="account.default")
    position, spot = _open_collision_position(broker, admitted_entry_identity,
                                               reason="HISTORICAL NULL")
    original_entry_minor = charges.monetary_minor(position.entry_charges)
    historical_values = {
        column.name: getattr(position, column.name)
        for column in Position.__table__.columns
    }
    historical_values.update(
        entry_intent_id=None,
        paper_entry_charge_schedule_id=None,
        paper_entry_charge_schedule_address=None,
    )
    position_id = position.id
    broker.s.delete(position)
    broker.s.flush()
    broker.s.add(Position(**historical_values))
    broker.s.commit()
    position = broker.s.get(Position, position_id)

    if partial:
        qty = max(1, position.qty // 3)
        trade = broker.book_partial_close(
            position, qty, 22.0, "RISK_REDUCTION", broker.provider.now(), spot)
        assert position.paper_entry_charge_schedule_id is None
        assert (charges.monetary_minor(position.entry_charges)
                + charges.monetary_minor(trade.charges_total)
                - charges.monetary_minor(trade.exit_charges)) == original_entry_minor
        remaining = broker.close_position(
            position, 22.0, "REMAINING_RISK_REDUCTION",
            broker.provider.now(), spot)
        assert remaining.entry_intent_id is None
    else:
        trade = broker.close_position(
            position, 22.0, "RISK_REDUCTION", broker.provider.now(), spot)
    trade_id = trade.id
    assert broker.reconcile()["diff"] == 0.0
    broker.s.close()
    restarted = PaperBroker(MockProvider(), owner_id="owner",
                            broker_account_id="account.default")
    trade = restarted.s.get(Trade, trade_id)
    receipt = restarted.charge_result_receipt(trade)
    assert trade.paper_entry_charge_schedule_id is None
    assert trade.paper_entry_charge_schedule_address is None
    assert trade.entry_intent_id is None
    assert trade.paper_exit_charge_schedule_id == V2
    assert trade.paper_exit_charge_schedule_address == charges.charge_schedule_address(V2)
    assert receipt["entry_authority_state"] == "LEGACY_ENTRY_AUTHORITY_UNKNOWN"
    assert receipt["entry_lifecycle_state"] == "LEGACY_NULL"
    assert receipt["entry_schedule_id"] is None
    assert receipt["exit_authority_state"] == "KNOWN"
    assert receipt["exit_schedule_id"] == V2
    assert restarted.reconcile()["diff"] == 0.0


@pytest.mark.parametrize("family", ["options", "equity", "futures"])
@pytest.mark.parametrize("exit_stage", ["full", "partial", "remaining"])
def test_corrupt_lifecycle_never_blocks_exact_owned_risk_reducing_exit(
        admitted_entry_identity, caplog, family, exit_stage):
    import datetime as dt

    from sqlalchemy import func, select, text

    from app.core.instruments import get_instrument
    from app.db.models import ExecutionIntent, Position, Trade
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    admission = admitted_entry_identity(broker.s)
    opened_at = dt.datetime(2026, 8, 30, 10, 0)
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    if family == "options":
        position = broker.open_position(
            instrument, "LONG", quote, "CORRUPT EXIT", opened_at, chain.spot,
            **admission)
        partial_qty = max(1, position.qty // 3)
    elif family == "equity":
        position = broker.open_equity_position(
            instrument, "LONG", 100.0, 101, "NSE_INTRADAY", "CORRUPT EXIT",
            opened_at, margin=4_001.0, params={}, **admission)
        partial_qty = 37
    else:
        position = broker.open_futures_position(
            instrument, "LONG", 24_000.0, 50, "NFO_FUT", "CORRUPT EXIT",
            opened_at, dt.date(2026, 9, 24), margin=25_000.0, **admission)
        partial_qty = 17
    original_intent_id = position.entry_intent_id
    original_qty = position.qty

    def close_full(current, reason):
        when = opened_at + dt.timedelta(minutes=30)
        if family == "options":
            return broker.close_position(
                current, quote.ltp, reason, when, chain.spot)
        if family == "equity":
            return broker.close_equity_position(current, 102.0, reason, when)
        return broker.close_futures_position(current, 24_100.0, reason, when)

    def close_partial(current):
        when = opened_at + dt.timedelta(minutes=15)
        if family == "options":
            return broker.book_partial_close(
                current, partial_qty, quote.ltp, "PARTIAL", when, chain.spot)
        if family == "equity":
            return broker.book_partial_close_equity(
                current, partial_qty, 101.0, "PARTIAL", when)
        return broker.book_partial_close_futures(
            current, partial_qty, 24_050.0, "PARTIAL", when)

    if exit_stage == "full":
        intent = broker.s.get(ExecutionIntent, original_intent_id)
        intent.requested_qty += 1
        broker.s.commit()
        trade = close_full(position, "FULL")
        expected_trades, expected_positions = 1, 0
    elif exit_stage == "partial":
        intent = broker.s.get(ExecutionIntent, original_intent_id)
        intent.instrument_key = "BANKNIFTY"
        broker.s.commit()
        trade = close_partial(position)
        expected_trades, expected_positions = 1, 1
        assert position.qty == original_qty - partial_qty
        assert position.entry_intent_id == original_intent_id
    else:
        first = close_partial(position)
        assert first.charge_result_receipt is not None
        alternate = V1 if first.paper_entry_charge_schedule_id == V2 else V2
        broker.s.execute(text(
            "UPDATE trades SET paper_entry_charge_schedule_id=:schedule, "
            "paper_entry_charge_schedule_address=:address WHERE id=:id"), {
                "schedule": alternate,
                "address": charges.charge_schedule_address(alternate),
                "id": first.id,
            })
        broker.s.commit()
        position_id = position.id
        broker.s.close()
        broker = PaperBroker(
            MockProvider(), owner_id="owner", broker_account_id="account.default")
        position = broker.s.get(Position, position_id)
        trade = close_full(position, "REMAINDER")
        expected_trades, expected_positions = 2, 0

    assert trade.entry_intent_id == original_intent_id
    assert trade.charge_result_receipt is None
    assert "Paper broker event" in caplog.text
    for private_detail in (
            "Risk-reducing exit booked without lifecycle receipt",
            "CHARGE_ENTRY_LIFECYCLE", "BANKNIFTY", original_intent_id):
        assert private_detail not in caplog.text
    assert broker.s.scalar(select(func.count()).select_from(Trade)) == expected_trades
    assert broker.s.scalar(select(func.count()).select_from(Position)) == expected_positions
    assert broker.reconcile()["diff"] == 0.0


def test_paper_close_retry_has_one_cash_trade_and_projection_effect(
        admitted_entry_identity):
    """Retrying an already-booked close cannot double the Paper business effect."""
    from sqlalchemy import func, select
    from app.db.models import CapitalState, Trade
    from app.db.session import SessionLocal, init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner",
                         broker_account_id="account.default")
    position, spot = _open_collision_position(broker, admitted_entry_identity,
                                               reason="RETRY")
    trade = broker.close_position(
        position, 22.0, "RETRY", broker.provider.now(), spot)
    cash_after = broker.cash()
    trade_id = trade.id
    with pytest.raises(ValueError, match="no longer open"):
        broker.close_position(position, 22.0, "RETRY", broker.provider.now(), spot)
    broker.s.rollback()
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Trade)) == 1
        assert session.get(Trade, trade_id) is not None
        capital = session.get(CapitalState, ("account.default", "paper"))
        assert capital.cash == cash_after


def _paper_broker(admitted_entry_identity):
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner",
                         broker_account_id="account.default")
    return broker, admitted_entry_identity(broker.s)


def test_full_equity_trade_receipt_survives_restart(admitted_entry_identity):
    import datetime as dt
    from app.core.instruments import get_instrument
    from app.db.models import Trade
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    broker, admission = _paper_broker(admitted_entry_identity)
    opened_at = broker.provider.now()
    position = broker.open_equity_position(
        get_instrument("NIFTY"), "LONG", 100.0, 200, "NSE_INTRADAY",
        "EQUITY RECEIPT", opened_at, margin=4_000.0, params={}, **admission)
    trade = broker.close_equity_position(
        position, 102.0, "EQUITY RECEIPT", opened_at + dt.timedelta(minutes=30))
    receipt = broker.charge_result_receipt(trade)
    assert receipt["entry_authority_state"] == "KNOWN"
    assert receipt["exit_authority_state"] == "KNOWN"
    assert receipt["entry_schedule_id"] == receipt["exit_schedule_id"] == V1
    trade_id = trade.id
    broker.s.close()
    restarted = PaperBroker(MockProvider(), owner_id="owner",
                            broker_account_id="account.default")
    assert restarted.charge_result_receipt(restarted.s.get(Trade, trade_id)) == receipt


def test_partial_equity_receipt_restart_remaining_exit_and_stale_retry_one_effect(
        admitted_entry_identity):
    import datetime as dt
    from sqlalchemy import func, select
    from app.core.instruments import get_instrument
    from app.db.models import Position, Trade
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    broker, admission = _paper_broker(admitted_entry_identity)
    opened_at = dt.datetime(2026, 8, 30, 10, 0)
    position = broker.open_equity_position(
        get_instrument("NIFTY"), "LONG", 100.0, 101, "NSE_INTRADAY",
        "EQUITY PARTIAL", opened_at, margin=4_001.0, params={}, **admission)
    original_entry_minor = charges.monetary_minor(position.entry_charges)
    partial = broker.book_partial_close_equity(
        position, 37, 101.0, "PARTIAL", opened_at + dt.timedelta(minutes=15))
    assert position.entry_intent_id == partial.entry_intent_id
    partial_receipt = broker.charge_result_receipt(partial)
    assert partial_receipt["partial_entry_allocation"] is True
    assert (partial_receipt["entry_charge_minor"]
            + charges.monetary_minor(position.entry_charges)) == original_entry_minor
    position_id, partial_id = position.id, partial.id
    broker.s.close()

    restarted = PaperBroker(MockProvider(), owner_id="owner",
                            broker_account_id="account.default")
    remaining = restarted.s.get(Position, position_id)
    assert restarted.charge_result_receipt(
        restarted.s.get(Trade, partial_id)) == partial_receipt
    final_trade = restarted.close_equity_position(
        remaining, 103.0, "REMAINDER", opened_at + dt.timedelta(minutes=30))
    assert final_trade.entry_intent_id == partial.entry_intent_id
    final_receipt = restarted.charge_result_receipt(final_trade)
    assert final_receipt["entry_authority_state"] == "KNOWN"
    assert final_receipt["exit_authority_state"] == "KNOWN"
    cash_after = restarted.cash()
    with pytest.raises(ValueError, match="no longer open"):
        restarted.close_equity_position(
            remaining, 103.0, "RETRY", opened_at + dt.timedelta(minutes=31))
    restarted.s.rollback()
    assert restarted.cash() == cash_after
    assert restarted.s.scalar(select(func.count()).select_from(Trade)) == 2
    assert restarted.reconcile()["diff"] == 0.0


def test_full_and_partial_futures_receipts_survive_restart_and_remaining_exit(
        admitted_entry_identity):
    import datetime as dt
    from app.core.instruments import get_instrument
    from app.db.models import Position, Trade
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    broker, admission = _paper_broker(admitted_entry_identity)
    opened_at = dt.datetime(2026, 8, 30, 10, 0)
    expiry = dt.date(2026, 9, 24)
    position = broker.open_futures_position(
        get_instrument("NIFTY"), "LONG", 24_000.0, 50, "NFO_FUT",
        "FUTURES PARTIAL", opened_at, expiry, margin=25_000.0, **admission)
    original_entry_minor = charges.monetary_minor(position.entry_charges)
    partial = broker.book_partial_close_futures(
        position, 17, 24_050.0, "PARTIAL", opened_at + dt.timedelta(minutes=15))
    assert position.entry_intent_id == partial.entry_intent_id
    partial_receipt = broker.charge_result_receipt(partial)
    assert partial.segment == "index_futures" and partial.option_type == "FUT"
    assert partial_receipt["partial_entry_allocation"] is True
    assert (partial_receipt["entry_charge_minor"]
            + charges.monetary_minor(position.entry_charges)) == original_entry_minor
    position_id, partial_id = position.id, partial.id
    broker.s.close()

    restarted = PaperBroker(MockProvider(), owner_id="owner",
                            broker_account_id="account.default")
    remaining = restarted.s.get(Position, position_id)
    assert restarted.charge_result_receipt(
        restarted.s.get(Trade, partial_id)) == partial_receipt
    final_trade = restarted.close_futures_position(
        remaining, 24_100.0, "REMAINDER", opened_at + dt.timedelta(minutes=30))
    assert final_trade.entry_intent_id == partial.entry_intent_id
    final_receipt = restarted.charge_result_receipt(final_trade)
    assert final_receipt["entry_schedule_id"] == V1
    assert final_receipt["exit_schedule_id"] == V1
    assert restarted.reconcile()["diff"] == 0.0


def test_full_futures_trade_receipt_survives_restart(admitted_entry_identity):
    import datetime as dt
    from app.core.instruments import get_instrument
    from app.db.models import Trade
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    broker, admission = _paper_broker(admitted_entry_identity)
    opened_at = dt.datetime(2026, 8, 30, 10, 0)
    position = broker.open_futures_position(
        get_instrument("NIFTY"), "LONG", 24_000.0, 50, "NFO_FUT",
        "FUTURES FULL", opened_at, dt.date(2026, 9, 24),
        margin=25_000.0, **admission)
    trade = broker.close_futures_position(
        position, 24_100.0, "FULL", opened_at + dt.timedelta(minutes=30))
    receipt = broker.charge_result_receipt(trade)
    assert receipt["partial_entry_allocation"] is False
    assert receipt["entry_schedule_id"] == receipt["exit_schedule_id"] == V1
    trade_id = trade.id
    broker.s.close()
    restarted = PaperBroker(MockProvider(), owner_id="owner",
                            broker_account_id="account.default")
    assert restarted.charge_result_receipt(restarted.s.get(Trade, trade_id)) == receipt
