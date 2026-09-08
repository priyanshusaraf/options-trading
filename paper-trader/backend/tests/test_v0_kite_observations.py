"""Offline conformance tests for Kite-shaped canonical observation mapping."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import replace

import pytest

from app.ir.hashing import canonical_json
from app.ir.validity import ValidityState
from app.market_data import kite_observations as mapper
from app.market_data.kite_observations import (
    MAX_HISTORICAL_ROWS,
    MAX_INSTRUMENT_ROWS,
    MAX_PAYLOAD_BYTES,
    MAX_QUOTE_INSTRUMENTS,
    KiteInstrumentBinding,
    KiteMappingContext,
    map_historical_candles,
    map_instrument_dump,
    map_quote_snapshot,
)
from app.market_truth.identity import (
    CanonicalPhysicalInstrument,
    ProviderContract,
    ProviderEntity,
    ProviderInstrumentAlias,
    ProviderProduct,
)
from app.providers.base import ProviderFactError, ProviderUnavailableReason

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 8, 31, 3, 45, tzinfo=UTC)


def address(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def authorities(*, derivative: bool = False, source: str = "CURRENT_DUMP", session=None):
    entity = ProviderEntity("strategy-os", "kite", "Zerodha Broking Limited")
    product = ProviderProduct(entity.address, "kite-connect-v3", "kite-connect", "3")
    contract = ProviderContract(
        "owner-a", product.address, "RESEARCH", ("OFFLINE_FIXTURE",),
        T0 - dt.timedelta(days=30), None, address("contract-evidence"),
    )
    underlier = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "INDEX", "SPOT", "INR", None,
    )
    instrument = (
        CanonicalPhysicalInstrument(
            "strategy-os", "1", "XNSE", "OPTION", "WEEKLY_OPTION", "INR",
            underlier.address, T0 + dt.timedelta(days=3), "25000", "CALL", "50",
        )
        if derivative
        else CanonicalPhysicalInstrument(
            "strategy-os", "1", "XNSE", "EQUITY", "SPOT", "INR", None,
        )
    )
    symbol = "NIFTY26SEP25000CE" if derivative else "INFY"
    token = "12345" if derivative else "408065"
    alias = ProviderInstrumentAlias(
        product.address, token, symbol, instrument.address, "kite-static/1",
        T0 - dt.timedelta(days=7), T0 + dt.timedelta(days=4) if derivative else None,
        "kite-connect", address("mapping-evidence"),
    )
    context = KiteMappingContext(
        owner_id="owner-a",
        provider_entity_address=entity.address,
        provider_product_address=product.address,
        provider_contract_address=contract.address,
        mapping=alias,
        canonical_instrument=instrument,
        mapping_authority=source,
    )
    if session is not None:
        from app.market_truth.identity import persist_canonical_instrument, persist_provider_identity, persist_provider_alias
        persist_canonical_instrument(session, underlier)
        persist_canonical_instrument(session, instrument)
        persist_provider_identity(session, entity, product, contract)
        persist_provider_alias(session, alias)
    return context, underlier


def quote(*, oi=0, depth=True):
    row = {
        "instrument_token": 408065,
        "last_price": 1500.0,
        "last_quantity": 0,
        "average_price": 1498.25,
        "volume": 0,
        "buy_quantity": 0,
        "sell_quantity": 0,
        "ohlc": {"open": 1490.0, "high": 1510.0, "low": 1480.0, "close": 1488.0},
        "change": 0.0,
        "last_trade_time": "2026-08-31T09:14:57+05:30",
        "timestamp": "2026-08-31T09:15:00+05:30",
        "oi": oi,
        "oi_day_high": oi,
        "oi_day_low": oi,
    }
    if depth:
        row["depth"] = {
            "buy": [
                {"quantity": 0 if i == 0 else i, "price": 1499.0 - i, "orders": i}
                for i in range(5)
            ],
            "sell": [
                {"quantity": i, "price": 1501.0 + i, "orders": 0 if i == 0 else i}
                for i in range(5)
            ],
        }
    return row


def snapshot(row=None):
    return {"status": "success", "data": {"NSE:INFY": row or quote()}}


def test_official_quote_shape_maps_exact_provenance_zero_and_five_level_depth():
    context, _ = authorities()
    batch = map_quote_snapshot(
        snapshot(), contexts=(context,), available_at=T0 + dt.timedelta(seconds=2),
        recorded_at=T0 + dt.timedelta(seconds=3), as_of=T0 + dt.timedelta(seconds=3),
    )

    assert batch.raw_segment.owner_id == "owner-a"
    assert batch.raw_segment.raw_schema == "kite-quote-snapshot/3"
    assert batch.unavailable == ()
    by_field = {item.field: item for item in batch.observations}
    assert by_field["last_price"].mapping_address == context.mapping.address
    assert by_field["last_price"].provider_token == "408065"
    assert by_field["last_price"].event_time == T0
    assert by_field["last_price"].completed_at == T0
    assert by_field["last_price"].available_at == T0 + dt.timedelta(seconds=2)
    assert by_field["last_price"].recorded_at == T0 + dt.timedelta(seconds=3)
    assert by_field["volume"].validity is ValidityState.VALID
    assert by_field["oi"].validity is ValidityState.VALID
    depth_fields = [name for name in by_field if name.startswith("depth.")]
    assert len(depth_fields) == 2 * 5 * 3
    assert "depth.buy.0.quantity" in by_field
    assert "depth.sell.4.orders" in by_field
    assert batch.raw_segment.payload.count(b'"quantity":0') >= 2
    for item in batch.observations:
        item.verify_segment(batch.raw_segment)


def test_missing_quote_key_oi_and_depth_are_absent_not_zero():
    context, _ = authorities()
    missing_key = map_quote_snapshot(
        {"status": "success", "data": {}}, contexts=(context,),
        available_at=T0, recorded_at=T0, as_of=T0,
    )
    assert missing_key.observations == ()
    assert {(item.field, item.reason) for item in missing_key.unavailable} == {
        ("QUOTE", ProviderUnavailableReason.MISSING_QUOTE_KEY),
    }

    row = quote()
    del row["oi"]
    del row["depth"]
    batch = map_quote_snapshot(
        snapshot(row), contexts=(context,), available_at=T0, recorded_at=T0, as_of=T0,
    )
    assert "oi" not in {item.field for item in batch.observations}
    assert not any(item.field.startswith("depth.") for item in batch.observations)
    assert {(item.field, item.reason) for item in batch.unavailable} == {
        ("OI", ProviderUnavailableReason.FIELD_ABSENT),
        ("DEPTH", ProviderUnavailableReason.FIELD_ABSENT),
    }


@pytest.mark.parametrize("side,size", [("buy", 4), ("buy", 6), ("sell", 4), ("sell", 6)])
def test_depth_must_be_exactly_five_coherent_levels(side, size):
    context, _ = authorities()
    row = quote()
    row["depth"][side] = (
        row["depth"][side][:size]
        if size < 5 else row["depth"][side] + [row["depth"][side][-1]]
    )
    with pytest.raises(ProviderFactError, match="five levels"):
        map_quote_snapshot(
            snapshot(row), contexts=(context,), available_at=T0, recorded_at=T0, as_of=T0,
        )


@pytest.mark.parametrize(("mutation", "match"), [
    (lambda row: row["depth"]["buy"][0].update(extra=1), "closed official shape"),
    (lambda row: row["depth"]["buy"][1].update(
        price=row["depth"]["buy"][0]["price"] + 1), "buy depth prices"),
    (lambda row: row["depth"]["sell"][1].update(
        price=row["depth"]["sell"][0]["price"] - 1), "sell depth prices"),
    (lambda row: row["depth"]["buy"][0].update(
        price=row["depth"]["sell"][0]["price"] + 1), "book is crossed"),
])
def test_depth_rejects_open_nonmonotone_and_crossed_shapes(mutation, match):
    context, _ = authorities()
    row = quote()
    mutation(row)
    with pytest.raises(ProviderFactError, match=match):
        map_quote_snapshot(
            snapshot(row), contexts=(context,), available_at=T0, recorded_at=T0, as_of=T0,
        )


def test_historical_rows_preserve_completed_available_recorded_and_optional_oi():
    context, _ = authorities()
    payload = {"status": "success", "data": {"candles": [
        ["2026-08-31T09:00:00+05:30", 100.0, 105.0, 99.0, 102.0, 0, 0],
        ["2026-08-31T09:01:00+05:30", 102.0, 106.0, 101.0, 104.0, 5],
    ]}}
    batch = map_historical_candles(
        payload, context=context, resolution_seconds=60,
        available_at=T0 + dt.timedelta(minutes=2),
        recorded_at=T0 + dt.timedelta(minutes=3),
        as_of=T0 + dt.timedelta(minutes=3),
    )
    assert len(batch.observations) == 11
    assert {(item.field, item.reason) for item in batch.unavailable} == {
        ("OI", ProviderUnavailableReason.FIELD_ABSENT),
    }
    first = next(
        item for item in batch.observations
        if item.field == "close" and item.event_time == T0 - dt.timedelta(minutes=15)
    )
    assert first.completed_at == first.event_time + dt.timedelta(minutes=1)
    assert first.available_at == T0 + dt.timedelta(minutes=2)
    assert first.recorded_at == T0 + dt.timedelta(minutes=3)
    assert any(
        item.field == "oi" and item.validity is ValidityState.VALID
        for item in batch.observations
    )


@pytest.mark.parametrize(
    "available,recorded,as_of,match",
    [
        (T0 - dt.timedelta(seconds=1), T0, T0, "before completed"),
        (T0, T0 - dt.timedelta(seconds=1), T0, "recorded"),
        (T0, T0, T0 - dt.timedelta(seconds=1), "future"),
    ],
)
def test_quote_timestamp_incoherence_and_future_suffix_refuse(available, recorded, as_of, match):
    context, _ = authorities()
    with pytest.raises(ProviderFactError, match=match):
        map_quote_snapshot(
            snapshot(), contexts=(context,), available_at=available,
            recorded_at=recorded, as_of=as_of,
        )


def test_forming_or_future_historical_candles_refuse():
    context, _ = authorities()
    payload = {"status": "success", "data": {"candles": [
        ["2026-08-31T09:15:00+05:30", 100, 101, 99, 100, 1],
    ]}}
    with pytest.raises(ProviderFactError, match="forming or future"):
        map_historical_candles(
            payload, context=context, resolution_seconds=60,
            available_at=T0, recorded_at=T0, as_of=T0,
        )


def test_historical_prefix_identity_is_stable_and_future_suffix_refuses():
    context, _ = authorities()
    first = ["2026-08-31T09:00:00+05:30", 100, 101, 99, 100, 1]
    second = ["2026-08-31T09:01:00+05:30", 100, 102, 99, 101, 2]
    prefix = map_historical_candles(
        {"status": "success", "data": {"candles": [first]}}, context=context,
        resolution_seconds=60, available_at=T0, recorded_at=T0, as_of=T0,
    )
    extended = map_historical_candles(
        {"status": "success", "data": {"candles": [first, second]}}, context=context,
        resolution_seconds=60, available_at=T0, recorded_at=T0, as_of=T0,
    )
    assert [item.fact() for item in prefix.observations] == [
        item.fact() for item in extended.observations[:5]
    ]
    assert prefix.raw_segments == extended.raw_segments[:1]

    future = ["2026-08-31T09:15:00+05:30", 101, 103, 100, 102, 3]
    with pytest.raises(ProviderFactError, match="forming or future"):
        map_historical_candles(
            {"status": "success", "data": {"candles": [first, future]}}, context=context,
            resolution_seconds=60, available_at=T0, recorded_at=T0, as_of=T0,
        )


def test_current_dump_maps_exact_alias_but_refuses_expired_contract_inference():
    context, _ = authorities()
    binding = KiteInstrumentBinding(
        canonical_instrument=context.canonical_instrument,
        effective_from=T0, effective_to=T0 + dt.timedelta(days=1),
    )
    rows = [{
        "instrument_token": 408065, "exchange_token": "1594", "tradingsymbol": "INFY",
        "name": "INFOSYS", "last_price": 0.0, "expiry": "", "strike": 0.0,
        "tick_size": 0.05, "lot_size": 1, "instrument_type": "EQ",
        "segment": "NSE", "exchange": "NSE",
    }]
    aliases = map_instrument_dump(
        rows, bindings={"408065": binding}, product_address=context.provider_product_address,
        observation_namespace="kite-connect", source_evidence_address=address("dump"),
        dump_at=T0,
    )
    assert aliases[0].provider_token == "408065"
    assert aliases[0].provider_symbol == "INFY"
    assert aliases[0].canonical_instrument_address == context.canonical_instrument.address

    option_context, _ = authorities(derivative=True)
    expired = {**rows[0], "instrument_token": 12345, "tradingsymbol": "NIFTY26AUG25000CE",
               "name": "NIFTY", "expiry": "2026-08-28", "strike": 25000.0,
               "lot_size": 50, "instrument_type": "CE", "segment": "NFO-OPT", "exchange": "NFO"}
    with pytest.raises(ProviderFactError, match="expired contract"):
        map_instrument_dump(
            [expired], bindings={"12345": KiteInstrumentBinding(
                option_context.canonical_instrument, T0, T0 + dt.timedelta(days=1))},
            product_address=option_context.provider_product_address,
            observation_namespace="kite-connect", source_evidence_address=address("today-dump"),
            dump_at=T0,
        )

    current_option = {**expired,
        "expiry": option_context.canonical_instrument.expiry.date().isoformat()}
    aliases = map_instrument_dump(
        [current_option], bindings={"12345": KiteInstrumentBinding(
            option_context.canonical_instrument, T0, T0 + dt.timedelta(days=1))},
        product_address=option_context.provider_product_address,
        observation_namespace="kite-connect", source_evidence_address=address("today-dump"),
        dump_at=T0,
    )
    assert aliases[0].provider_symbol == "NIFTY26AUG25000CE"


def test_current_future_requires_documented_nfo_fut_segment():
    cash_context, underlier = authorities()
    future = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "FUTURE", "FUTURE", "INR",
        underlier.address, T0 + dt.timedelta(days=30), None, None, "50",
    )
    alias = ProviderInstrumentAlias(
        cash_context.provider_product_address, "54321", "NIFTY26SEPFUT",
        future.address, "kite-static/1", T0, T0 + dt.timedelta(days=1),
        "kite-connect", address("future-mapping"),
    )
    context = KiteMappingContext(
        cash_context.owner_id, cash_context.provider_entity_address,
        cash_context.provider_product_address, cash_context.provider_contract_address,
        alias, future, "CURRENT_DUMP",
    )
    row = {
        "instrument_token": 54321, "exchange_token": "999",
        "tradingsymbol": "NIFTY26SEPFUT", "name": "NIFTY", "last_price": 0.0,
        "expiry": future.expiry.date().isoformat(), "strike": 0.0, "tick_size": 0.05,
        "lot_size": 50, "instrument_type": "FUT", "segment": "NFO-FUT",
        "exchange": "NFO",
    }
    binding = KiteInstrumentBinding(future, T0, T0 + dt.timedelta(days=1))
    assert map_instrument_dump(
        [row], bindings={"54321": binding},
        product_address=context.provider_product_address,
        observation_namespace="kite-connect", source_evidence_address=address("future-dump"),
        dump_at=T0,
    )[0].provider_symbol == "NIFTY26SEPFUT"
    with pytest.raises(ProviderFactError, match="venue"):
        map_instrument_dump(
            [{**row, "segment": "NFO-OPT"}], bindings={"54321": binding},
            product_address=context.provider_product_address,
            observation_namespace="kite-connect",
            source_evidence_address=address("future-dump"), dump_at=T0,
        )


def _current_index_dump(venue="XNSE", exchange="NSE"):
    context, _ = authorities()
    instrument = CanonicalPhysicalInstrument(
        f"synthetic-index:{venue}", "1", venue, "INDEX", "SPOT", "INR", None)
    row = {"instrument_token": 256265, "tradingsymbol": "SYNTHETIC INDEX",
        "expiry": "", "strike": 0.0, "lot_size": 0, "instrument_type": "EQ",
        "segment": "INDICES", "exchange": exchange}
    arguments = {"bindings": {"256265": KiteInstrumentBinding(instrument, T0, T0 + dt.timedelta(days=1))},
        "product_address": context.provider_product_address, "observation_namespace": "kite-connect",
        "source_evidence_address": address("current-index-dump"), "dump_at": T0}
    return context, instrument, row, arguments


@pytest.mark.parametrize("venue,exchange", [("XNSE", "NSE"), ("XBOM", "BSE")])
def test_current_index_dump_uses_indices_segment_and_keeps_exchange(venue, exchange):
    # Kite support confirms EQ + INDICES, with the exchange kept separately:
    # https://kite.trade/forum/discussion/14221/instrument-type-for-index-changed-few-months-back
    context, instrument, row, arguments = _current_index_dump(venue, exchange)
    alias, = map_instrument_dump([row], **arguments)
    assert alias.canonical_instrument_address == instrument.address
    assert (instrument.asset_class, instrument.contract_kind, instrument.multiplier) == ("INDEX", "SPOT", None)
    assert (alias.effective_from, alias.effective_to) == (T0, T0 + dt.timedelta(days=1))
    mapped = KiteMappingContext(context.owner_id, context.provider_entity_address,
        context.provider_product_address, context.provider_contract_address, alias, instrument, "CURRENT_DUMP")
    assert mapped.quote_key == f"{exchange}:SYNTHETIC INDEX"


@pytest.mark.parametrize("changes", [
    {"segment": "NSE"}, {"segment": "NSE-INDICES"}, {"exchange": "BSE"},
    {"instrument_type": "FUT"}, {"expiry": "2026-09-30"},
])
def test_current_index_dump_refuses_wrong_venue_segment_or_derivative_terms(changes):
    _, _, row, arguments = _current_index_dump()
    with pytest.raises(ProviderFactError):
        map_instrument_dump([{**row, **changes}], **arguments)


def test_current_index_dump_does_not_reclassify_equity_or_unknown_venue():
    from dataclasses import replace
    _, instrument, row, arguments = _current_index_dump()
    for changed in (replace(instrument, asset_class="EQUITY"), replace(instrument, venue_code="XMCX")):
        binding = KiteInstrumentBinding(changed, T0, T0 + dt.timedelta(days=1))
        with pytest.raises(ProviderFactError, match="venue"):
            map_instrument_dump([row], **{**arguments, "bindings": {"256265": binding}})


def test_current_index_dump_never_extends_mapping_back_to_older_history():
    context, instrument, row, arguments = _current_index_dump()
    alias, = map_instrument_dump([row], **arguments)
    mapped = KiteMappingContext(context.owner_id, context.provider_entity_address,
        context.provider_product_address, context.provider_contract_address, alias, instrument, "CURRENT_DUMP")
    previous_bar = [(T0 - dt.timedelta(minutes=1)).isoformat(), 100, 101, 99, 100, 0]
    with pytest.raises(ProviderFactError, match="mapping does not cover"):
        map_historical_candles({"status": "success", "data": {"candles": [previous_bar]}},
            context=mapped, resolution_seconds=60, available_at=T0, recorded_at=T0, as_of=T0)
    backdated = KiteInstrumentBinding(instrument, T0 - dt.timedelta(days=1), T0 + dt.timedelta(days=1))
    with pytest.raises(ProviderFactError, match="must start at the dump instant"):
        map_instrument_dump([row], **{**arguments, "bindings": {"256265": backdated}})


def test_quote_refuses_unrequested_and_sensitive_raw_keys():
    context, _ = authorities()
    payload = snapshot()
    payload["data"]["NSE:TCS"] = dict(payload["data"]["NSE:INFY"])
    with pytest.raises(ProviderFactError, match="unrequested instrument"):
        map_quote_snapshot(payload, contexts=(context,), available_at=T0,
            recorded_at=T0, as_of=T0)

    payload = snapshot()
    payload["data"]["NSE:INFY"]["access_token"] = "must-not-enter-raw-evidence"
    with pytest.raises(ProviderFactError, match="sensitive field"):
        map_quote_snapshot(payload, contexts=(context,), available_at=T0,
            recorded_at=T0, as_of=T0)

    payload = snapshot()
    payload["data"]["NSE:INFY"]["session_cookie"] = "not-an-official-quote-field"
    with pytest.raises(ProviderFactError, match="undocumented field"):
        map_quote_snapshot(payload, contexts=(context,), available_at=T0,
            recorded_at=T0, as_of=T0)


def test_quote_row_closes_before_raw_encoder_or_segment(monkeypatch):
    context, _ = authorities()
    payload = snapshot()
    payload["data"]["NSE:INFY"]["session_cookie"] = "must-never-reach-raw-evidence"
    calls: list[str] = []
    encode = mapper._payload_bytes
    segment = mapper._segment

    def observed_encode(value):
        calls.append("payload_bytes")
        return encode(value)

    def observed_segment(*args, **kwargs):
        calls.append("segment")
        return segment(*args, **kwargs)

    monkeypatch.setattr(mapper, "_payload_bytes", observed_encode)
    monkeypatch.setattr(mapper, "_segment", observed_segment)

    with pytest.raises(ProviderFactError, match="undocumented field"):
        map_quote_snapshot(
            payload, contexts=(context,), available_at=T0, recorded_at=T0, as_of=T0,
        )
    assert calls == []


def test_present_null_quote_row_refuses_before_raw_encoder_or_segment(monkeypatch):
    context, _ = authorities()
    payload = {"status": "success", "data": {"NSE:INFY": None}}
    calls: list[str] = []
    encode = mapper._payload_bytes
    segment = mapper._segment

    def observed_encode(value):
        calls.append("payload_bytes")
        return encode(value)

    def observed_segment(*args, **kwargs):
        calls.append("segment")
        return segment(*args, **kwargs)

    monkeypatch.setattr(mapper, "_payload_bytes", observed_encode)
    monkeypatch.setattr(mapper, "_segment", observed_segment)

    with pytest.raises(ProviderFactError, match="quote row is malformed"):
        map_quote_snapshot(
            payload, contexts=(context,), available_at=T0, recorded_at=T0, as_of=T0,
        )
    assert calls == []


def test_historical_derivative_requires_captured_point_in_time_mapping():
    context, _ = authorities(derivative=True, source="CURRENT_DUMP")
    payload = {"status": "success", "data": {"candles": [
        ["2026-08-30T09:00:00+05:30", 100, 101, 99, 100, 1, 2],
    ]}}
    with pytest.raises(ProviderFactError, match="captured point-in-time"):
        map_historical_candles(
            payload, context=context, resolution_seconds=60,
            available_at=T0, recorded_at=T0, as_of=T0,
        )
    captured, _ = authorities(derivative=True, source="CAPTURED_POINT_IN_TIME")
    assert map_historical_candles(
        payload, context=captured, resolution_seconds=60,
        available_at=T0, recorded_at=T0, as_of=T0,
    ).observations


def test_missing_required_keys_and_incoherent_prices_refuse():
    context, _ = authorities()
    for row, match in ((["2026-08-31T09:00:00+05:30", 100], "six or seven"),
                       (["2026-08-31T09:00:00+05:30", 100, 99, 101, 100, 1], "OHLC")):
        with pytest.raises(ProviderFactError, match=match):
            map_historical_candles(
                {"status": "success", "data": {"candles": [row]}}, context=context,
                resolution_seconds=60, available_at=T0, recorded_at=T0, as_of=T0,
            )
    malformed = snapshot()
    del malformed["status"]
    with pytest.raises(ProviderFactError, match="closed official envelope"):
        map_quote_snapshot(
            malformed, contexts=(context,), available_at=T0, recorded_at=T0, as_of=T0,
        )


def test_payload_quote_request_and_instrument_bounds_are_direct():
    context, _ = authorities()
    at_quote_bound = []
    for index in range(MAX_QUOTE_INSTRUMENTS):
        alias = ProviderInstrumentAlias(
            context.provider_product_address, str(index + 1), f"SYM{index}",
            context.canonical_instrument.address, "kite-static/1", T0, None,
            "kite-connect", address(f"mapping-{index}"),
        )
        at_quote_bound.append(KiteMappingContext(
            context.owner_id, context.provider_entity_address,
            context.provider_product_address, context.provider_contract_address,
            alias, context.canonical_instrument, "CURRENT_DUMP",
        ))
    at_bound = map_quote_snapshot(
        {"status": "success", "data": {}}, contexts=tuple(at_quote_bound),
        available_at=T0, recorded_at=T0, as_of=T0,
    )
    assert len(at_bound.unavailable) == MAX_QUOTE_INSTRUMENTS
    with pytest.raises(ProviderFactError, match="instrument request bound"):
        map_quote_snapshot(
            {"status": "success", "data": {}},
            contexts=tuple(at_quote_bound) + (context,),
            available_at=T0, recorded_at=T0, as_of=T0,
        )

    one = {"instrument_token": 1}
    assert map_instrument_dump(
        [one] * MAX_INSTRUMENT_ROWS, bindings={}, product_address=context.provider_product_address,
        observation_namespace="kite-connect", source_evidence_address=address("dump"), dump_at=T0,
    ) == ()
    with pytest.raises(ProviderFactError, match="instrument row bound"):
        map_instrument_dump(
            [one] * (MAX_INSTRUMENT_ROWS + 1), bindings={},
            product_address=context.provider_product_address,
            observation_namespace="kite-connect",
            source_evidence_address=address("dump"), dump_at=T0,
        )

    base = {"padding": ""}
    overhead = len(canonical_json(base).encode())
    at_payload_bound = {"padding": "x" * (MAX_PAYLOAD_BYTES - overhead)}
    assert len(canonical_json(at_payload_bound).encode()) == MAX_PAYLOAD_BYTES
    assert len(mapper._payload_bytes(at_payload_bound)) == MAX_PAYLOAD_BYTES
    oversized = {"padding": "x" * (MAX_PAYLOAD_BYTES - overhead + 1)}
    with pytest.raises(ProviderFactError, match="payload bound"):
        mapper._payload_bytes(oversized)


def test_historical_row_bound_is_accepted_then_refuses_one_more():
    context, _ = authorities()
    start = T0 - dt.timedelta(minutes=MAX_HISTORICAL_ROWS + 1)
    rows = [
        [(start + dt.timedelta(minutes=index)).isoformat(), 100, 101, 99, 100, 0]
        for index in range(MAX_HISTORICAL_ROWS)
    ]
    batch = map_historical_candles(
        {"status": "success", "data": {"candles": rows}}, context=context,
        resolution_seconds=60, available_at=T0, recorded_at=T0, as_of=T0,
    )
    assert len(batch.observations) == MAX_HISTORICAL_ROWS * 5
    with pytest.raises(ProviderFactError, match="historical row bound"):
        map_historical_candles(
            {"status": "success", "data": {"candles": rows + [rows[-1]]}},
            context=context, resolution_seconds=60,
            available_at=T0, recorded_at=T0, as_of=T0,
        )


def test_mapping_module_has_no_transport_credential_or_execution_imports():
    import app.market_data.kite_observations as module

    source = open(module.__file__, encoding="utf-8").read()
    forbidden = (
        "requests", "httpx", "socket", "KITE_API", "SafePaperKite",
        "app.engine", "app.execution",
    )
    assert all(name not in source for name in forbidden)


def test_mapped_candle_fields_and_resolutions_persist_and_exact_retry_is_idempotent():
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import Session
    from app.db.models import Base, AuthorityProviderObservation
    from app.market_data.observations import persist_raw_segment, persist_provider_observation
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    payload = {"status":"success", "data":{"candles":[["2026-08-31T09:15:00+05:30",100,102,99,101,1234]]}}
    with Session(engine) as session:
        context, _ = authorities(session=session)
        batches = [map_historical_candles(payload, context=context, resolution_seconds=seconds,
            available_at=T0+dt.timedelta(seconds=1802), recorded_at=T0+dt.timedelta(seconds=1803),
            as_of=T0+dt.timedelta(seconds=1804)) for seconds in (900, 1800)]
        for batch in (*batches, batches[0]):
            for raw in batch.raw_segments:
                persist_raw_segment(session, raw)
            for observation in batch.observations:
                persist_provider_observation(session, observation)
        session.commit()
        assert session.scalar(select(func.count()).select_from(AuthorityProviderObservation)) == 10
        ids = {item.correction_id for batch in batches for item in batch.observations}
        assert len(ids) == 10 and all(len(value) <= 128 for value in ids)
        assert batches[0].observations[0].sequence_id == batches[1].observations[0].sequence_id
        assert batches[0].raw_segment.payload == batches[1].raw_segment.payload
    engine.dispose()


def _retrospective_inputs():
    context, _ = authorities()
    entity = ProviderEntity("strategy-os", "kite", "Zerodha Broking Limited")
    product = ProviderProduct(entity.address, "kite-connect-v3", "kite-connect", "3")
    captured = T0 + dt.timedelta(days=2, microseconds=123456)
    contract = ProviderContract("owner-a", product.address, "RESEARCH", ("HISTORICAL",),
        T0 + dt.timedelta(days=1), None, address("existing-private-research-grant"))
    csv = ("instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"
           "408065,1594,INFY,INFOSYS,1500,,0,0.05,1,EQ,NSE,NSE\n").encode()
    raw = ('{ "status": "success", "data": { "candles": ['
           '["2026-08-31T09:15:00+05:30",100,102,99,101,1234],'
           '["2026-08-31T09:30:00+05:30",101,103,100,102,1235]] } }').encode()
    return dict(owner_id="owner-a", connection_id=42, entity=entity, product=product, contract=contract,
        instrument=context.canonical_instrument, token=408065, symbol="INFY", exchange="NSE", interval="15minute",
        requested_start=T0, requested_end=T0+dt.timedelta(minutes=15), current_reference_bytes=csv,
        reference_received_at=captured-dt.timedelta(seconds=1), reference_recorded_at=captured-dt.timedelta(microseconds=1),
        historical_response_bytes=raw, captured_at=captured, recorded_at=captured+dt.timedelta(microseconds=1),
        as_of=captured+dt.timedelta(microseconds=2))


@pytest.fixture
def retrospective_session(request):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.models import Base
    from app.market_truth.identity import persist_canonical_instrument, persist_provider_identity
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        inputs = _dated_retrospective_inputs() if getattr(request, "param", False) else _retrospective_inputs()
        persist_canonical_instrument(session, inputs["instrument"])
        persist_provider_identity(session, inputs["entity"], inputs["product"], inputs["contract"])
        yield session, inputs
    engine.dispose()


def _retrospective_batch(attribution, inputs, *, payload=None):
    return map_historical_candles(payload or json.loads(attribution.historical_response.payload),
        context=attribution.context, resolution_seconds=900, available_at=inputs["captured_at"],
        recorded_at=inputs["recorded_at"], as_of=inputs["as_of"])


def test_retrospective_response_uses_acquisition_grant_and_exact_retained_bytes(retrospective_session):
    from sqlalchemy.orm import Session
    from app.market_data.kite_historical_attribution import (
        prepare_historical_attribution, persist_historical_attribution, load_historical_attribution,
        validate_historical_capture_attribution)
    from app.market_data.observations import persist_raw_segment, persist_provider_observation, load_provider_observation
    session, inputs = retrospective_session
    attribution = prepare_historical_attribution(**inputs)
    assert attribution.mapping.effective_from < inputs["contract"].effective_from
    assert attribution.current_reference.payload == inputs["current_reference_bytes"]
    assert attribution.historical_response.payload == inputs["historical_response_bytes"]
    assert attribution.receipt.recorded_at == inputs["recorded_at"]
    assert persist_historical_attribution(session, attribution) == attribution.context
    batch = _retrospective_batch(attribution, inputs)
    for raw in batch.raw_segments:
        persist_raw_segment(session, raw)
    for observation in batch.observations:
        persist_provider_observation(session, observation)
    session.commit()
    with Session(session.get_bind()) as reopened:
        loaded = load_historical_attribution(reopened, attribution.mapping)
        assert loaded == attribution
        assert [load_provider_observation(reopened, item.address) for item in batch.observations] == list(batch.observations)
        assert validate_historical_capture_attribution(reopened, loaded.context,
            connection_id=inputs["connection_id"],
            raw_response=inputs["historical_response_bytes"], captured_at=inputs["captured_at"],
            recorded_at=inputs["recorded_at"], requested_start=inputs["requested_start"],
            requested_end=inputs["requested_end"], resolution_seconds=900) == inputs["captured_at"]


@pytest.mark.parametrize("change", ["owner", "future_grant", "expired_grant", "mode", "uses", "foreign_product"])
def test_retrospective_response_requires_an_existing_applicable_grant(change):
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from app.market_truth.identity import MarketTruthError
    inputs = _retrospective_inputs()
    modifications = {
        "owner": {"owner_id": "other"}, "future_grant": {"effective_from": inputs["captured_at"]+dt.timedelta(seconds=1)},
        "expired_grant": {"effective_to": inputs["captured_at"]}, "mode": {"mode": "LIVE"},
        "uses": {"permitted_uses": ("QUOTE",)}, "foreign_product": {"product_address": address("other-product")},
    }
    inputs["contract"] = replace(inputs["contract"], **modifications[change])
    with pytest.raises(MarketTruthError):
        prepare_historical_attribution(**inputs)


@pytest.mark.parametrize("change", ["token", "symbol", "exchange", "kind", "expiry", "duplicate", "headers", "invalid_utf8"])
def test_retrospective_response_rechecks_exact_current_reference(change):
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from app.market_truth.identity import MarketTruthError
    inputs = _retrospective_inputs()
    raw = inputs["current_reference_bytes"]
    changes = {"token": (b"408065", b"408066"), "symbol": (b"INFY,", b"OTHER,"),
        "exchange": (b"EQ,NSE,NSE", b"EQ,NSE,BSE"), "kind": (b"EQ,NSE,NSE", b"EQ,INDICES,NSE"),
        "expiry": (b"1500,,0", b"1500,2026-09-01,0"), "headers": (b"exchange_token", b"instrument_token")}
    if change in changes:
        raw = raw.replace(*changes[change])
    elif change == "duplicate":
        raw += raw.splitlines(keepends=True)[1]
    else:
        raw = b"\xff"
    inputs["current_reference_bytes"] = raw
    with pytest.raises(MarketTruthError):
        prepare_historical_attribution(**inputs)


@pytest.mark.parametrize("change", ["fractional_request", "future_reference", "early_recording", "outside_request", "forming", "oi", "duplicate_json", "duplicate_bar"])
def test_retrospective_response_refuses_incoherent_request_or_response(change):
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from app.market_truth.identity import MarketTruthError
    inputs = _retrospective_inputs()
    if change == "fractional_request": inputs["requested_start"] += dt.timedelta(microseconds=1)
    if change == "future_reference": inputs["reference_received_at"] = inputs["as_of"]+dt.timedelta(seconds=1)
    if change == "early_recording": inputs["recorded_at"] = inputs["captured_at"]-dt.timedelta(microseconds=1)
    if change == "outside_request": inputs["requested_end"] = inputs["requested_start"]
    if change == "forming": inputs["historical_response_bytes"] = inputs["historical_response_bytes"].replace(b"2026-08-31", b"2026-09-04")
    if change == "oi": inputs["historical_response_bytes"] = inputs["historical_response_bytes"].replace(b"1234]", b"1234,0]")
    if change == "duplicate_json": inputs["historical_response_bytes"] = b'{"status":"success","status":"success","data":{"candles":[]}}'
    if change == "duplicate_bar":
        document = json.loads(inputs["historical_response_bytes"])
        document["data"]["candles"][1] = document["data"]["candles"][0]
        inputs["historical_response_bytes"] = canonical_json(document).encode()
    with pytest.raises(MarketTruthError): prepare_historical_attribution(**inputs)


def _changed_attribution(attribution, change):
    doc = json.loads(attribution.receipt.payload)
    change(doc)
    receipt = replace(attribution.receipt, payload=canonical_json(doc).encode())
    mapping = replace(attribution.mapping, source_evidence_address=receipt.address)
    return replace(attribution, receipt=receipt, context=replace(attribution.context, mapping=mapping))


@pytest.mark.parametrize("change", [
    lambda doc: doc["request"].update(continuous=True),
    lambda doc: doc["request"].update(oi=True),
    lambda doc: doc["selection"].update(kind="INDEX"),
    lambda doc: doc["current_reference"].update(raw_address=address("another-raw")),
    lambda doc: doc.update(provider_entity_address=address("another-entity")),
])
def test_retrospective_receipt_tampering_cannot_create_an_alias(retrospective_session, change):
    from sqlalchemy import select, func
    from app.db.models import AuthorityRawSegment, AuthorityProviderAlias
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    forged = _changed_attribution(prepare_historical_attribution(**inputs), change)
    with pytest.raises(MarketTruthError): persist_historical_attribution(session, forged)
    assert session.scalar(select(func.count()).select_from(AuthorityRawSegment)) == 0
    assert session.scalar(select(func.count()).select_from(AuthorityProviderAlias)) == 0


def test_retrospective_alias_does_not_authorize_other_observations_or_quotes(retrospective_session):
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    from app.market_data.observations import persist_raw_segment, persist_provider_observation
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    attribution = prepare_historical_attribution(**inputs)
    persist_historical_attribution(session, attribution)
    payload = json.loads(attribution.historical_response.payload)
    payload["data"]["candles"][0][4] = 100
    batch = _retrospective_batch(attribution, inputs, payload=payload)
    persist_raw_segment(session, batch.raw_segments[0])
    with pytest.raises(MarketTruthError, match="retained response"):
        persist_provider_observation(session, batch.observations[0])
    with pytest.raises(ProviderFactError, match="cannot supply quotes"):
        map_quote_snapshot(snapshot(), contexts=(attribution.context,), available_at=inputs["captured_at"],
            recorded_at=inputs["recorded_at"], as_of=inputs["as_of"])


def test_retrospective_v1_capture_overlap_refuses_without_retaining_orphan_raws(retrospective_session):
    from sqlalchemy import select, func
    from app.db.models import AuthorityRawSegment
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    attribution = _legacy_retrospective(prepare_historical_attribution(**inputs))
    persist_historical_attribution(session, attribution)
    persist_historical_attribution(session, attribution)
    before = session.scalar(select(func.count()).select_from(AuthorityRawSegment))
    later = {**inputs, "as_of": inputs["as_of"]+dt.timedelta(seconds=1)}
    with pytest.raises(MarketTruthError, match="overlap"):
        persist_historical_attribution(session, _legacy_retrospective(prepare_historical_attribution(**later)))
    assert session.scalar(select(func.count()).select_from(AuthorityRawSegment)) == before


@pytest.mark.parametrize("field", ["connection_id", "raw_response", "captured_at", "recorded_at", "requested_start", "requested_end", "resolution_seconds"])
def test_retrospective_publication_requires_exact_request_response_pair(retrospective_session, field):
    from app.market_data.kite_historical_attribution import (prepare_historical_attribution,
        persist_historical_attribution, validate_historical_capture_attribution)
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    attribution = prepare_historical_attribution(**inputs)
    persist_historical_attribution(session, attribution)
    request = {key: inputs[key] for key in ("captured_at", "recorded_at", "requested_start", "requested_end")}
    request.update(connection_id=inputs["connection_id"], raw_response=inputs["historical_response_bytes"], resolution_seconds=900)
    if field == "raw_response": request[field] += b" "
    elif field == "resolution_seconds": request[field] = 1800
    elif field == "connection_id": request[field] += 1
    else: request[field] += dt.timedelta(microseconds=1)
    with pytest.raises(MarketTruthError):
        validate_historical_capture_attribution(session, attribution.context, **request)


def test_retrospective_loader_rechecks_retained_bytes_and_legacy_uses_event_clock(retrospective_session):
    from app.db.models import AuthorityRawSegment
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution, load_historical_attribution
    from app.market_data.observations import persist_raw_segment, persist_provider_observation
    from app.market_truth.identity import MarketTruthError, persist_provider_alias
    session, inputs = retrospective_session
    attribution = prepare_historical_attribution(**inputs)
    fields = attribution.mapping.fact()
    fields.pop("provider_contract_address")
    fields.update(effective_from=attribution.mapping.effective_from, effective_to=attribution.mapping.effective_to,
                  adapter_schema_version="kite-static/1", source_evidence_address=address("legacy"))
    legacy = ProviderInstrumentAlias(**fields)
    persist_provider_alias(session, legacy)
    context = replace(attribution.context, mapping=legacy, mapping_authority="CURRENT_DUMP")
    batch = _retrospective_batch(replace(attribution, context=context), inputs)
    persist_raw_segment(session, batch.raw_segments[0])
    with pytest.raises(MarketTruthError, match="interval"):
        persist_provider_observation(session, batch.observations[0])
    session.rollback()
    from app.market_truth.identity import persist_canonical_instrument, persist_provider_identity
    persist_canonical_instrument(session, inputs["instrument"])
    persist_provider_identity(session, inputs["entity"], inputs["product"], inputs["contract"])
    persist_historical_attribution(session, attribution)
    stored = session.get(AuthorityRawSegment, attribution.current_reference.address)
    stored.raw_bytes = stored.raw_bytes.replace(b"INFY", b"EVIL")
    with session.no_autoflush, pytest.raises(MarketTruthError):
        load_historical_attribution(session, attribution.mapping)


def test_retrospective_loader_refuses_a_stored_row_from_another_response(retrospective_session):
    from app.db.models import AuthorityProviderObservation
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    from app.market_data.observations import persist_raw_segment, persist_provider_observation, load_provider_observation
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    attribution = prepare_historical_attribution(**inputs)
    persist_historical_attribution(session, attribution)
    original = _retrospective_batch(attribution, inputs)
    persist_raw_segment(session, original.raw_segments[0])
    persist_provider_observation(session, original.observations[0])
    row = session.get(AuthorityProviderObservation, original.observations[0].address)
    payload = json.loads(attribution.historical_response.payload)
    payload["data"]["candles"][0][4] = 100
    altered = _retrospective_batch(attribution, inputs, payload=payload)
    persist_raw_segment(session, altered.raw_segments[0])
    false_observation = replace(altered.observations[0], correction_id="forged-independent-row")
    copied = {column.name: getattr(row, column.name) for column in AuthorityProviderObservation.__table__.columns}
    copied.update(address=false_observation.address, canonical_json=false_observation.canonical_bytes.decode(),
                  raw_segment_address=false_observation.raw_segment_address, correction_id=false_observation.correction_id)
    session.add(AuthorityProviderObservation(**copied)); session.flush()
    with pytest.raises(MarketTruthError, match="retained response"):
        load_provider_observation(session, false_observation.address)


def test_retrospective_preparation_does_not_invent_an_unpersisted_grant(retrospective_session):
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    inputs["contract"] = replace(inputs["contract"], evidence_address=address("unpersisted-grant"))
    attribution = prepare_historical_attribution(**inputs)
    with pytest.raises(MarketTruthError, match="absent"):
        persist_historical_attribution(session, attribution)


def test_retrospective_capture_preserves_microseconds_and_durable_size_bounds():
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    inputs = _retrospective_inputs()
    first = prepare_historical_attribution(**inputs)
    second = prepare_historical_attribution(**{**inputs, "recorded_at": inputs["recorded_at"]+dt.timedelta(microseconds=1)})
    assert first.historical_response.address != second.historical_response.address
    assert first.receipt.address != second.receipt.address
    assert first.mapping.address != second.mapping.address
    assert first.context.canonical_instrument == second.context.canonical_instrument
    for field in ("current_reference_bytes", "historical_response_bytes"):
        with pytest.raises(ValueError, match="oversized"):
            prepare_historical_attribution(**{**inputs, field: b"x"*(4*1024*1024+1)})


def test_retrospective_mapping_string_alone_cannot_change_an_old_alias():
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    context, _ = authorities()
    with pytest.raises(ProviderFactError, match="retained response adapter"):
        replace(context, mapping_authority="RETROSPECTIVE_RESPONSE")
    attribution = prepare_historical_attribution(**_retrospective_inputs())
    with pytest.raises(ProviderFactError, match="retained response adapter"):
        replace(attribution.context, mapping_authority="CURRENT_DUMP")


def test_mapper_correction_identity_is_bounded_and_keeps_timestamp_precision():
    from app.market_data.kite_observations import _correction_id
    sequence = "quote:" + "x"*190 + ":2026-08-31T03:45:00.123456+00:00:close"
    assert len(sequence) <= 256
    assert len(_correction_id(sequence, 1)) == 64
    assert _correction_id(sequence, 1) != _correction_id(sequence.replace("123456", "123457"), 1)
    assert _correction_id(sequence, 1) != _correction_id(sequence, 60)


def test_quote_correction_identity_keeps_utc_equivalence_and_subsecond_distinctions():
    context, _ = authorities()
    payload = {"status":"success", "data":{context.quote_key:quote()}}
    def mapped(timestamp):
        payload["data"][context.quote_key]["timestamp"] = timestamp
        return map_quote_snapshot(payload, contexts=(context,), available_at=T0+dt.timedelta(seconds=1),
            recorded_at=T0+dt.timedelta(seconds=2), as_of=T0+dt.timedelta(seconds=3))
    first = mapped("2026-08-31T09:15:00.123456+05:30")
    utc = mapped("2026-08-31T03:45:00.123456+00:00")
    newer = mapped("2026-08-31T03:45:00.123457+00:00")
    assert [row.sequence_id for row in first.observations] == [row.sequence_id for row in utc.observations]
    assert [row.correction_id for row in first.observations] == [row.correction_id for row in utc.observations]
    assert [row.correction_id for row in first.observations] != [row.correction_id for row in newer.observations]
    assert all(len(row.correction_id) == 64 for row in first.observations)


def _legacy_retrospective(attribution):
    fields = attribution.mapping.fact()
    fields.pop("provider_contract_address")
    fields.update(effective_from=attribution.mapping.effective_from, effective_to=attribution.mapping.effective_to)
    return replace(attribution, context=replace(attribution.context, mapping=ProviderInstrumentAlias(**fields)))


def test_response_alias_v2_is_closed_finite_and_replays_v1_exactly(retrospective_session):
    from app.market_truth.identity import ProviderResponseInstrumentAlias, MarketTruthError, load_provider_alias
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution, load_historical_attribution
    session, inputs = retrospective_session
    prepared = prepare_historical_attribution(**inputs)
    alias = prepared.mapping
    assert type(alias) is ProviderResponseInstrumentAlias and alias.SCHEMA == "provider-instrument-mapping/2"
    assert alias.provider_contract_address == inputs["contract"].address
    assert ProviderResponseInstrumentAlias.from_bytes(alias.canonical_bytes) == alias
    for change in ({"effective_to": None}, {"provider_contract_address": "bad"}):
        with pytest.raises(MarketTruthError):
            replace(alias, **change)
    with pytest.raises(MarketTruthError):
        ProviderInstrumentAlias.from_bytes(alias.canonical_bytes)
    legacy = _legacy_retrospective(prepared)
    legacy_bytes, legacy_address = legacy.mapping.canonical_bytes, legacy.mapping.address
    persist_historical_attribution(session, legacy)
    assert load_historical_attribution(session, legacy.mapping) == legacy
    assert load_provider_alias(session, legacy_address).canonical_bytes == legacy_bytes
    persist_historical_attribution(session, prepared)
    assert load_provider_alias(session, alias.address) == alias
    assert load_historical_attribution(session, alias) == prepared


def test_response_aliases_allow_separate_owner_contracts_and_receipts(retrospective_session):
    from sqlalchemy import select, func
    from app.db.models import AuthorityProviderAlias
    from app.market_truth.identity import persist_provider_identity, validate_provider_aliases, load_provider_alias
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    from app.market_data.observations import persist_raw_segment, persist_provider_observation, load_provider_observation
    session, inputs = retrospective_session
    other_contract = replace(inputs["contract"], owner_id="owner-b")
    persist_provider_identity(session, inputs["entity"], inputs["product"], other_contract)
    first = prepare_historical_attribution(**inputs)
    second = prepare_historical_attribution(**{**inputs, "owner_id": "owner-b", "contract": other_contract})
    later_inputs = {**inputs, "recorded_at": inputs["recorded_at"]+dt.timedelta(microseconds=1)}
    third = prepare_historical_attribution(**later_inputs)
    validate_provider_aliases((first.mapping, second.mapping, third.mapping))
    for attribution in (first, second, third, first):
        persist_historical_attribution(session, attribution)
        assert load_provider_alias(session, attribution.mapping.address) == attribution.mapping
    assert session.scalar(select(func.count()).select_from(AuthorityProviderAlias)) == 3
    for attribution in (first, second):
        batch = _retrospective_batch(attribution, inputs)
        for raw in batch.raw_segments:
            persist_raw_segment(session, raw)
        for observation in batch.observations:
            persist_provider_observation(session, observation)
            assert load_provider_observation(session, observation.address) == observation


@pytest.mark.parametrize("field", ["provider_token", "provider_symbol", "effective_from", "effective_to"])
def test_response_alias_same_receipt_conflict_refuses_both_python_and_native(retrospective_session, field):
    from sqlalchemy.exc import IntegrityError
    from app.db.models import AuthorityProviderAlias
    from app.market_truth.identity import MarketTruthError, persist_provider_alias, validate_provider_aliases
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    from app.market_truth.temporal import to_sql_utc_naive
    session, inputs = retrospective_session
    prepared = prepare_historical_attribution(**inputs)
    persist_historical_attribution(session, prepared)
    values = {"provider_token": "999", "provider_symbol": "OTHER",
              "effective_from": T0-dt.timedelta(minutes=15), "effective_to": T0+dt.timedelta(hours=1)}
    altered = replace(prepared.mapping, **{field: values[field]})
    with pytest.raises(MarketTruthError, match="overlaps|conflicts"):
        validate_provider_aliases((prepared.mapping, altered))
    with pytest.raises(MarketTruthError, match="overlaps"):
        persist_provider_alias(session, altered)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(AuthorityProviderAlias(address=altered.address, schema=altered.SCHEMA,
            canonical_json=altered.canonical_bytes.decode(), product_address=altered.product_address,
            instrument_address=altered.canonical_instrument_address, provider_token=altered.provider_token,
            provider_symbol=altered.provider_symbol, observation_namespace=altered.observation_namespace,
            effective_from=to_sql_utc_naive(altered.effective_from, "from"),
            effective_to=to_sql_utc_naive(altered.effective_to, "to"),
            provider_contract_address=altered.provider_contract_address, receipt_address=altered.source_evidence_address))
        session.flush()


def test_response_alias_rejects_missing_foreign_receipt_and_contract_context(retrospective_session):
    from app.market_truth.identity import MarketTruthError, persist_provider_alias, persist_provider_identity
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    session, inputs = retrospective_session
    prepared = prepare_historical_attribution(**inputs)
    with pytest.raises(MarketTruthError, match="raw segment"):
        persist_provider_alias(session, prepared.mapping)
    persist_historical_attribution(session, prepared)
    other_contract = replace(inputs["contract"], owner_id="owner-b")
    persist_provider_identity(session, inputs["entity"], inputs["product"], other_contract)
    foreign = replace(prepared.mapping, provider_contract_address=other_contract.address)
    with pytest.raises(MarketTruthError, match="contract or receipt"):
        persist_provider_alias(session, foreign)
    with pytest.raises(ProviderFactError, match="contract"):
        replace(prepared.context, mapping=foreign)


@pytest.mark.parametrize("version,field", [(1,"provider_contract_address"), (1,"receipt_address"),
    (2,"provider_contract_address"), (2,"receipt_address"), (2,"schema"),
    (1,"provider_symbol"), (2,"provider_symbol")])
def test_response_alias_loader_rejects_corrupted_copied_scope(retrospective_session, version, field):
    from app.db.models import AuthorityProviderAlias
    from app.market_truth.identity import MarketTruthError, load_provider_alias
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    session, inputs = retrospective_session
    prepared = prepare_historical_attribution(**inputs)
    if version == 1:
        prepared = _legacy_retrospective(prepared)
    persist_historical_attribution(session, prepared)
    row = session.get(AuthorityProviderAlias, prepared.mapping.address)
    setattr(row, field, "unsupported" if field == "schema" else address("foreign"))
    with session.no_autoflush, pytest.raises(MarketTruthError):
        load_provider_alias(session, prepared.mapping.address)


@pytest.mark.parametrize("change,conflict", [
    ({"provider_token": "other"}, True), ({"provider_symbol": "OTHER"}, True),
    ({"canonical_instrument_address": address("other")}, True),
    ({"product_address": address("other")}, False), ({"observation_namespace": "other"}, False),
    ({"effective_from": T0+dt.timedelta(hours=1), "effective_to": T0+dt.timedelta(hours=2)}, False),
    ({"effective_from": T0-dt.timedelta(hours=2), "effective_to": T0-dt.timedelta(hours=1)}, False),
    ({"provider_token": "other", "provider_symbol": "OTHER", "canonical_instrument_address": address("other")}, False),
])
def test_response_alias_change_preserves_v1_global_interval_rules(change, conflict):
    from app.market_truth.identity import validate_provider_aliases, MarketTruthError
    context, _ = authorities()
    first = replace(context.mapping, effective_from=T0, effective_to=T0+dt.timedelta(hours=1))
    second = replace(first, **change)
    if conflict:
        with pytest.raises(MarketTruthError, match="overlaps"):
            validate_provider_aliases((first, second))
    else:
        validate_provider_aliases((first, second))
    with pytest.raises(MarketTruthError, match="closed"):
        validate_provider_aliases((object(),))


def test_response_alias_observation_contract_scope_refuses_before_receipt_clock(retrospective_session):
    from app.market_truth.identity import MarketTruthError
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from app.market_data.observations import _provider_dependency_identity
    _, inputs = retrospective_session
    prepared = prepare_historical_attribution(**inputs)
    batch = _retrospective_batch(prepared, inputs)
    foreign = replace(prepared.mapping, provider_contract_address=address("foreign-contract"))
    with pytest.raises(MarketTruthError, match="identity chain"):
        _provider_dependency_identity(batch.observations[0], inputs["entity"], inputs["product"],
            inputs["contract"], foreign, batch.raw_segments[0])


def test_response_alias_retry_rechecks_existing_copied_facts(retrospective_session):
    from app.db.models import AuthorityProviderAlias
    from app.market_truth.identity import MarketTruthError, persist_provider_alias
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, persist_historical_attribution
    session, inputs = retrospective_session
    prepared = prepare_historical_attribution(**inputs)
    persist_historical_attribution(session, prepared)
    row = session.get(AuthorityProviderAlias, prepared.mapping.address)
    row.provider_symbol = "ALTERED"
    with session.no_autoflush, pytest.raises(MarketTruthError, match="copied columns"):
        persist_provider_alias(session, prepared.mapping)


def test_retrospective_validation_memo_is_pass_and_session_scoped(retrospective_session, monkeypatch):
    import app.market_data.kite_historical_attribution as history
    from app.market_data.observations import _observation_dependency_rows, _observation_pass_memo
    session, inputs = retrospective_session
    prepared = history.prepare_historical_attribution(**inputs)
    history.persist_historical_attribution(session, prepared)
    batch = _retrospective_batch(prepared, inputs)
    original = history.load_historical_attribution
    calls = []
    def counted(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(history, "load_historical_attribution", counted)
    def verify():
        for observation in batch.observations:
            segment = next(raw for raw in batch.raw_segments if raw.address == observation.raw_segment_address)
            assert history.observation_grant_time(session, observation, prepared.mapping, segment) == inputs["captured_at"]
    with _observation_dependency_rows(session):
        verify()
        assert len(calls) == 1
        assert _observation_pass_memo(object()) is None
        with _observation_dependency_rows(session):
            verify()
        assert len(calls) == 2
        verify()
        assert len(calls) == 2
    assert _observation_pass_memo(session) is None
    with pytest.raises(RuntimeError), _observation_dependency_rows(session):
        verify()
        raise RuntimeError("end pass")
    assert len(calls) == 3
    assert _observation_pass_memo(session) is None
    verify()
    assert len(calls) == 3 + len(batch.observations)


def test_retrospective_warm_memo_preserves_exact_observation_checks(retrospective_session):
    import app.market_data.kite_historical_attribution as history
    from app.market_data.observations import _observation_dependency_rows
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    prepared = history.prepare_historical_attribution(**inputs)
    history.persist_historical_attribution(session, prepared)
    batch = _retrospective_batch(prepared, inputs)
    observation, segment = batch.observations[0], batch.raw_segments[0]
    with _observation_dependency_rows(session):
        history.observation_grant_time(session, observation, prepared.mapping, segment)
        with pytest.raises(MarketTruthError, match="bytes or identity"):
            history.observation_grant_time(session, batch.observations[5], prepared.mapping, segment)
        with pytest.raises(MarketTruthError, match="bytes or identity"):
            history.observation_grant_time(session, replace(observation, provider_token="other"),
                prepared.mapping, segment)
        with pytest.raises(MarketTruthError, match="absent"):
            history._observation_response_batch(history._observation_response(session, prepared.mapping),
                inputs["requested_start"] + dt.timedelta(days=1))


def test_retrospective_memo_rechecks_response_after_pass(retrospective_session):
    import app.market_data.kite_historical_attribution as history
    from app.db.models import AuthorityRawSegment
    from app.market_data.observations import _observation_dependency_rows
    from app.market_truth.identity import MarketTruthError
    session, inputs = retrospective_session
    prepared = history.prepare_historical_attribution(**inputs)
    history.persist_historical_attribution(session, prepared)
    batch = _retrospective_batch(prepared, inputs)
    observation, segment = batch.observations[0], batch.raw_segments[0]
    with _observation_dependency_rows(session):
        history.observation_grant_time(session, observation, prepared.mapping, segment)
    row = session.get(AuthorityRawSegment, prepared.historical_response.address)
    row.raw_bytes = b"tampered response"
    with session.no_autoflush, _observation_dependency_rows(session), pytest.raises(MarketTruthError):
        history.observation_grant_time(session, observation, prepared.mapping, segment)


def test_retrospective_memo_keeps_foreign_sessions_and_facades_separate(retrospective_session):
    from sqlalchemy.orm import Session
    from app.market_data.observations import _observation_dependency_rows, _observation_pass_memo
    session, _ = retrospective_session
    facade = object()
    with Session(session.get_bind()) as other, _observation_dependency_rows(session):
        outer = _observation_pass_memo(session)
        outer["sentinel"] = "outer"
        assert _observation_pass_memo(other) is None
        assert _observation_pass_memo(facade) is None
        with _observation_dependency_rows(facade):
            assert _observation_pass_memo(facade) == {}
            assert _observation_pass_memo(session) is None
        assert _observation_pass_memo(session) is outer
        assert outer == {"sentinel": "outer"}


def test_retained_observation_decorator_scopes_each_call():
    from app.market_data.observations import retain_observation_dependencies, _observation_pass_memo
    facade = object()
    @retain_observation_dependencies
    def validate(session, value):
        memo = _observation_pass_memo(session)
        assert memo == {}
        memo["value"] = value
        if value == "raise":
            raise RuntimeError("validation failed")
        return value
    with pytest.raises(RuntimeError):
        validate(facade, "raise")
    assert _observation_pass_memo(facade) is None
    assert validate(facade, "first") == "first"
    assert validate(facade, "second") == "second"
    assert _observation_pass_memo(facade) is None


def _dated_retrospective_inputs(seconds=1800):
    values = _retrospective_inputs()
    entity = ProviderEntity('synthetic', 'kite', 'Synthetic provider authority')
    product = ProviderProduct(entity.address, 'kite-connect-v3', 'kite-connect', '3')
    contract = replace(values['contract'], product_address=product.address,
        effective_from=T0-dt.timedelta(hours=1))
    captured = T0+dt.timedelta(minutes=45, microseconds=123456)
    rows = [[(T0+dt.timedelta(seconds=offset)).isoformat(), 100,102,99,101,1234]
            for offset in range(0,2700,seconds)]
    values.update(entity=entity, product=product, contract=contract,
        interval={900:'15minute',1800:'30minute',3600:'60minute'}[seconds],
        requested_end=T0+dt.timedelta(minutes=45)-dt.timedelta(seconds=1),
        historical_response_bytes=canonical_json({'status':'success','data':{'candles':rows}}).encode(),
        reference_received_at=captured-dt.timedelta(seconds=1),
        reference_recorded_at=captured-dt.timedelta(microseconds=1),
        captured_at=captured, recorded_at=captured+dt.timedelta(microseconds=1),
        as_of=captured+dt.timedelta(microseconds=2))
    return values


def _retained_dated_clock(session, inputs, seconds):
    from app.market_data.dated_session_clock import SCHEMA, COMPLETION_SCHEMA, prepare_session_clock
    from app.market_data.observations import RawObservationSegment, persist_raw_segment
    from app.market_truth.dated_sessions import parse_dated_sessions
    recorded = T0-dt.timedelta(minutes=1)
    document = dict(schema=SCHEMA, instrument_address=inputs['instrument'].address,
        venue_code='XNSE', timezone='Asia/Kolkata', provenance='SYNTHETIC',
        source_reference='Synthetic bar-clock fixture; not exchange data', recorded_at=recorded.isoformat(),
        rows=[dict(date=T0.date().isoformat(), status='OPEN', opens_at=T0.isoformat(),
                   closes_at=(T0+dt.timedelta(minutes=45)).isoformat())])
    raw = RawObservationSegment(inputs['owner_id'], inputs['product'].address, inputs['contract'].address,
        'application/json', SCHEMA, canonical_json(document).encode(), recorded)
    calendar = parse_dated_sessions(raw.payload, instrument_address=inputs['instrument'].address,
        venue_code='XNSE', timezone='Asia/Kolkata', as_of=inputs['as_of'], allow_synthetic=True)
    completion = dict(schema=COMPLETION_SCHEMA, calendar_address=calendar.address,
        product_address=inputs['product'].address, contract_address=inputs['contract'].address,
        resolution_seconds=seconds, completion_rule='SESSION_OPEN_CLIP_CLOSE_V1', provenance='SYNTHETIC')
    semantics = RawObservationSegment(inputs['owner_id'], inputs['product'].address, inputs['contract'].address,
        'application/json', COMPLETION_SCHEMA, canonical_json(completion).encode(), recorded)
    for item in (raw, semantics):
        persist_raw_segment(session, item)
    return prepare_session_clock(**{key: inputs[key] for key in
        ('owner_id','entity','product','contract','instrument','as_of')},
        resolution_seconds=seconds, calendar_source=raw, completion_source=semantics)


@pytest.mark.parametrize('retrospective_session', [True], indirect=True)
@pytest.mark.parametrize('seconds', [900,1800,3600])
def test_dated_retrospective_receipt_replays_original_short_terminal_observations(retrospective_session, seconds):
    from sqlalchemy.orm import Session
    from app.market_data import kite_historical_attribution as history
    from app.market_data.observations import persist_raw_segment, persist_provider_observation, load_provider_observation
    session, _ = retrospective_session
    inputs = _dated_retrospective_inputs(seconds)
    clock_binding = _retained_dated_clock(session, inputs, seconds)
    source = history.prepare_historical_attribution(**inputs, clock_binding=clock_binding)
    history.persist_historical_attribution(session, source)
    assert source.receipt.raw_schema == history.CLOCK_RECEIPT_SCHEMA
    assert json.loads(source.receipt.payload)['clock_binding'] == clock_binding.receipt_binding()
    batch = map_historical_candles(json.loads(source.historical_response.payload), context=source.context,
        resolution_seconds=seconds, available_at=inputs['captured_at'], recorded_at=inputs['recorded_at'],
        as_of=inputs['as_of'], dated_sessions=clock_binding.calendar)
    for raw in batch.raw_segments:
        persist_raw_segment(session, raw)
    for observation in batch.observations:
        persist_provider_observation(session, observation)
    session.commit()
    with Session(session.get_bind()) as reopened:
        assert history.load_historical_attribution(reopened, source.mapping) == source
        assert tuple(load_provider_observation(reopened, row.address) for row in batch.observations) == batch.observations
    terminal = batch.observations[-1]
    assert terminal.completed_at == T0+dt.timedelta(minutes=45)
    assert terminal.available_at == inputs['captured_at']
    assert terminal.recorded_at == inputs['recorded_at']


@pytest.mark.parametrize('retrospective_session', [True], indirect=True)
@pytest.mark.parametrize('change', ['missing_bar','forming_bar','wrong_resolution','forged_calendar'])
def test_dated_retrospective_receipt_refuses_missing_forming_or_unbound_clocks(retrospective_session, change):
    from app.market_data import kite_historical_attribution as history
    session, inputs = retrospective_session
    clock_binding = _retained_dated_clock(session, inputs,1800)
    if change == 'missing_bar':
        document = json.loads(inputs['historical_response_bytes'])
        document['data']['candles'].pop(0)
        inputs['historical_response_bytes'] = canonical_json(document).encode()
    elif change == 'forming_bar':
        inputs['captured_at'] = T0+dt.timedelta(minutes=44)
        inputs['reference_received_at'] = T0
        inputs['reference_recorded_at'] = T0
    elif change == 'wrong_resolution':
        inputs['interval'] = '60minute'
    else:
        clock_binding = replace(clock_binding, calendar=replace(clock_binding.calendar,
            source_reference='Forged substitute'))
    with pytest.raises(ValueError):
        history.prepare_historical_attribution(**inputs, clock_binding=clock_binding)


@pytest.mark.parametrize('retrospective_session', [True], indirect=True)
def test_dated_retrospective_publication_requires_its_exact_clock_binding(retrospective_session):
    from app.market_data import kite_historical_attribution as history
    session, inputs = retrospective_session
    clock_binding = _retained_dated_clock(session, inputs,1800)
    source = history.prepare_historical_attribution(**inputs, clock_binding=clock_binding)
    history.persist_historical_attribution(session, source)
    fields = ('connection_id','captured_at','recorded_at','requested_start','requested_end')
    arguments = {key: inputs[key] for key in fields}
    arguments.update(raw_response=inputs['historical_response_bytes'], resolution_seconds=1800)
    with pytest.raises(ValueError, match='bar-clock evidence differs'):
        history.validate_historical_capture_attribution(session, source.context, **arguments)
    assert history.validate_historical_capture_attribution(session, source.context,
        **arguments, clock_binding=clock_binding) == inputs['captured_at']


def _capture_catalog_arguments():
    received = T0 + dt.timedelta(minutes=2, microseconds=123456)
    row = {"raw": address("capture"), "received_at": received.isoformat(),
           "from": T0.isoformat(), "to": (T0 + dt.timedelta(seconds=59)).isoformat(),
           "mapping": address("mapping"), "reference_raw": address("reference"),
           "reference_received_at": (T0 - dt.timedelta(seconds=1, microseconds=123456)).isoformat(),
           "reference_recorded_at": T0.isoformat()}
    second = {**row, "raw": address("capture2"),
              "from": (T0 + dt.timedelta(minutes=1)).isoformat(),
              "to": (T0 + dt.timedelta(seconds=119)).isoformat(), "mapping": "EMPTY"}
    return dict(owner_id="tenant.alpha", product_address=address("product"),
        contract_address=address("contract"), selection_address=address("selection"),
        clock_binding={"calendar_source_address": address("calendar-source"),
            "completion_source_address": address("completion-source"),
            "calendar_address": address("calendar"), "resolution_seconds": 900},
        requested_start=T0, requested_end=T0 + dt.timedelta(seconds=119),
        rows=[row, second], recorded_at=received)


def _parse_capture_catalog(raw, arguments):
    from app.market_data.retained_history_windows import parse_capture_catalog
    return parse_capture_catalog(raw, **{key: arguments[key] for key in (
        "owner_id", "product_address", "contract_address")}, as_of=arguments["recorded_at"])


def test_capture_catalog_canonical_reload_is_immutable_and_preserves_receipt_precision():
    from dataclasses import FrozenInstanceError
    from app.market_data.retained_history_windows import prepare_capture_catalog
    arguments = _capture_catalog_arguments()
    raw = prepare_capture_catalog(**arguments)
    reordered = {**arguments, "rows": [dict(reversed(tuple(row.items()))) for row in arguments["rows"]]}
    assert prepare_capture_catalog(**reordered) == raw
    catalog = _parse_capture_catalog(raw, arguments)
    assert canonical_json(catalog.payload()).encode() == raw.payload
    assert catalog.rows[0]["received_at"].endswith(".123456+00:00")
    assert catalog.rows[1]["mapping"] == "EMPTY"
    assert catalog.requested_start == T0 and catalog.requested_end == arguments["requested_end"]
    assert catalog.selection_address == arguments["selection_address"]
    arguments["rows"][0]["raw"] = address("changed")
    arguments["clock_binding"]["calendar_address"] = address("changed")
    assert catalog.rows[0]["raw"] == address("capture")
    assert catalog.clock_binding["calendar_address"] == address("calendar")
    with pytest.raises(TypeError):
        catalog.rows[0]["raw"] = address("changed")
    with pytest.raises(TypeError):
        catalog.clock_binding["calendar_address"] = address("changed")
    with pytest.raises(FrozenInstanceError):
        catalog.requested_start = T0 + dt.timedelta(seconds=1)
    copied = catalog.payload()
    rebuilt = prepare_capture_catalog(owner_id=catalog.owner_id, product_address=catalog.product_address,
        contract_address=catalog.contract_address, clock_binding=catalog.clock_binding,
        selection_address=catalog.selection_address, requested_start=catalog.requested_start,
        requested_end=catalog.requested_end, rows=catalog.rows, recorded_at=raw.recorded_at)
    assert rebuilt == raw and copied["schema"] == raw.raw_schema


def test_capture_catalog_crops_first_capture_without_inventing_calendar_closures():
    from app.market_data.retained_history_windows import prepare_capture_catalog
    arguments = _capture_catalog_arguments()
    arguments["requested_start"] = T0 + dt.timedelta(seconds=30)
    catalog = _parse_capture_catalog(prepare_capture_catalog(**arguments), arguments)
    assert catalog.rows[0]["from"] == T0.isoformat()
    assert catalog.requested_start == T0 + dt.timedelta(seconds=30)
    assert len(catalog.rows) == 2


@pytest.mark.parametrize("change", ["gap", "overlap", "reversed", "last_end", "first_missing", "first_past", "reversed_request"])
def test_capture_catalog_refuses_noncontiguous_or_uncovered_windows(change):
    from app.market_data.retained_history_windows import prepare_capture_catalog
    arguments = _capture_catalog_arguments()
    if change in ("gap", "overlap"):
        arguments["rows"][1]["from"] = (T0 + dt.timedelta(seconds=61 if change == "gap" else 59)).isoformat()
    elif change == "reversed":
        arguments["rows"][0]["to"] = (T0 - dt.timedelta(seconds=1)).isoformat()
    elif change == "last_end":
        arguments["rows"][-1]["to"] = (T0 + dt.timedelta(seconds=120)).isoformat()
    elif change == "first_missing":
        arguments["requested_start"] = T0 - dt.timedelta(seconds=1)
    elif change == "first_past":
        arguments["requested_start"] = T0 + dt.timedelta(seconds=60)
    else:
        arguments["requested_start"] = arguments["requested_end"] + dt.timedelta(seconds=1)
    with pytest.raises(ValueError):
        prepare_capture_catalog(**arguments)


@pytest.mark.parametrize("field,value", [
    ("raw", "SYNTHETIC"), ("reference_raw", "EMPTY"), ("mapping", "SYNTHETIC"),
    ("raw", None), ("mapping", 1), ("unexpected", "value"),
    ("from", "2026-08-31T03:45:00.000001+00:00"),
    ("to", "2026-08-31T03:45:59"),
    ("received_at", "2026-08-31T03:47:00+01:00"),
])
def test_capture_catalog_refuses_malformed_rows_and_synthetic_address_labels(field, value):
    from app.market_data.retained_history_windows import prepare_capture_catalog
    arguments = _capture_catalog_arguments()
    arguments["rows"][0][field] = value
    with pytest.raises(ValueError):
        prepare_capture_catalog(**arguments)


@pytest.mark.parametrize("change", ["reference_future", "receipt_future", "reference_reversed", "response_before_reference"])
def test_capture_catalog_checks_causal_receipt_clocks(change):
    from app.market_data.retained_history_windows import prepare_capture_catalog
    arguments = _capture_catalog_arguments()
    row = arguments["rows"][0]
    if change == "reference_future":
        row["reference_recorded_at"] = (arguments["recorded_at"] + dt.timedelta(microseconds=1)).isoformat()
    elif change == "receipt_future":
        row["received_at"] = (arguments["recorded_at"] + dt.timedelta(microseconds=1)).isoformat()
    elif change == "reference_reversed":
        row["reference_recorded_at"] = (T0 - dt.timedelta(seconds=2)).isoformat()
    else:
        row["received_at"] = (T0 - dt.timedelta(seconds=2)).isoformat()
    with pytest.raises(ValueError):
        prepare_capture_catalog(**arguments)


@pytest.mark.parametrize("change", ["extra", "missing", "invalid_address", "synthetic", "wrong_resolution", "bool_resolution"])
def test_capture_catalog_clock_binding_is_closed_and_addressed(change):
    from app.market_data.retained_history_windows import prepare_capture_catalog
    arguments = _capture_catalog_arguments()
    binding = arguments["clock_binding"]
    if change == "extra":
        binding["observed_truth"] = "yes"
    elif change == "missing":
        del binding["completion_source_address"]
    elif change == "invalid_address":
        binding["calendar_address"] = "sha256:bad"
    elif change == "synthetic":
        binding["calendar_source_address"] = "SYNTHETIC"
    else:
        binding["resolution_seconds"] = True if change == "bool_resolution" else 60
    with pytest.raises(ValueError):
        prepare_capture_catalog(**arguments)


@pytest.mark.parametrize("field", ["owner_id", "product_address", "contract_address"])
def test_capture_catalog_rejects_foreign_raw_and_document_scope(field):
    from app.market_data.retained_history_windows import prepare_capture_catalog, parse_capture_catalog
    arguments = _capture_catalog_arguments()
    raw = prepare_capture_catalog(**arguments)
    scope = {key: arguments[key] for key in ("owner_id", "product_address", "contract_address")}
    different = "tenant.beta" if field == "owner_id" else address("foreign")
    with pytest.raises(ValueError, match="raw scope"):
        parse_capture_catalog(raw, **{**scope, field: different}, as_of=arguments["recorded_at"])
    document = json.loads(raw.payload)
    document[field] = different
    with pytest.raises(ValueError, match="document scope"):
        _parse_capture_catalog(replace(raw, payload=canonical_json(document).encode()), arguments)


def test_capture_catalog_refuses_duplicate_keys_schema_substitution_and_future_recording():
    from app.market_data.retained_history_windows import prepare_capture_catalog, parse_capture_catalog
    arguments = _capture_catalog_arguments()
    raw = prepare_capture_catalog(**arguments)
    duplicates = [raw.payload.replace(b'"schema":', b'"schema":"other","schema":', 1),
                  raw.payload.replace(b'"mapping":', b'"mapping":"EMPTY","mapping":', 1)]
    for payload in duplicates:
        with pytest.raises(ValueError):
            _parse_capture_catalog(replace(raw, payload=payload), arguments)
    document = json.loads(raw.payload)
    document["schema"] = "kite-intraday-capture-catalog/2"
    for altered in (replace(raw, payload=canonical_json(document).encode()),
                    replace(raw, raw_schema="SYNTHETIC"), replace(raw, media_type="text/plain")):
        with pytest.raises(ValueError, match="schema"):
            _parse_capture_catalog(altered, arguments)
    with pytest.raises(ValueError, match="future"):
        parse_capture_catalog(raw, owner_id=arguments["owner_id"], product_address=arguments["product_address"],
            contract_address=arguments["contract_address"], as_of=raw.recorded_at - dt.timedelta(microseconds=1))


def test_capture_catalog_window_and_payload_bounds_are_enforced():
    from app.market_data.retained_history_windows import prepare_capture_catalog, MAX_CAPTURE_WINDOWS
    arguments = _capture_catalog_arguments()
    row = arguments["rows"][0]
    for count in (0, MAX_CAPTURE_WINDOWS + 1):
        with pytest.raises(ValueError, match="2366"):
            prepare_capture_catalog(**{**arguments, "rows": [row] * count})
    rows = [{**row, "from": (T0 + dt.timedelta(seconds=index)).isoformat(),
             "to": (T0 + dt.timedelta(seconds=index)).isoformat()} for index in range(MAX_CAPTURE_WINDOWS)]
    arguments.update(rows=rows, requested_end=T0 + dt.timedelta(seconds=MAX_CAPTURE_WINDOWS - 1),
                     recorded_at=T0 + dt.timedelta(hours=1))
    catalog = _parse_capture_catalog(prepare_capture_catalog(**arguments), arguments)
    assert len(catalog.rows) == MAX_CAPTURE_WINDOWS
    with pytest.raises(ValueError, match="oversized"):
        raw = prepare_capture_catalog(**arguments)
        replace(raw, payload=raw.payload + b" " * (4 * 1024 * 1024))
