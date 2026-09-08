"""Retained, owner-bound attribution of one retrospective Kite response.

This is response-series attribution, not a historical token directory. The
caller supplies a previously admitted canonical root and an existing grant.
Original current-reference and historical-response bytes remain separate facts.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
from dataclasses import dataclass, replace

from app.ir.hashing import canonical_json
from app.market_data.observations import RawObservationSegment
from app.market_truth.identity import (MarketTruthError, ProviderInstrumentAlias,
    ProviderResponseInstrumentAlias)

MAPPING_AUTHORITY = "RETROSPECTIVE_RESPONSE"
ADAPTER_SCHEMA = "kite-historical-response/1"
RECEIPT_SCHEMA = "kite-historical-attribution/1"
CLOCK_ADAPTER_SCHEMA = "kite-historical-response/2"
CLOCK_RECEIPT_SCHEMA = "kite-historical-attribution/2"
ADAPTER_SCHEMAS = frozenset({ADAPTER_SCHEMA, CLOCK_ADAPTER_SCHEMA})
REFERENCE_SCHEMA = "kite-current-instruments-csv/3"
RESPONSE_SCHEMA = "kite-historical-http-response/3"
INTERVAL_SECONDS = {"15minute": 900, "30minute": 1800, "60minute": 3600, "day": 86400}
_REFERENCE_FIELDS = {
    "instrument_token", "exchange_token", "tradingsymbol", "name", "last_price",
    "expiry", "strike", "tick_size", "lot_size", "instrument_type", "segment", "exchange",
}


def _require(condition, reason):
    if not condition:
        raise MarketTruthError(f"historical attribution {reason}")


def _instant(value, *, whole=False):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    _require(type(value) is dt.datetime and value.tzinfo is not None
             and value.utcoffset() == dt.timedelta(0), "requires exact UTC clocks")
    _require(not whole or value.microsecond == 0, "requires whole-second request labels")
    return value


def _closed(value, fields):
    _require(type(value) is dict and set(value) == set(fields), "receipt shape is invalid")
    return value


def _unique_object(pairs):
    value = dict(pairs)
    _require(len(value) == len(pairs), "contains duplicate JSON keys")
    return value


def _json(payload):
    try:
        return json.loads(payload, object_pairs_hook=_unique_object)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise MarketTruthError("historical attribution JSON is unavailable") from exc


def _selection(instrument, token, symbol, exchange):
    _require(type(token) is int and 0 < token <= 4_294_967_295, "token is invalid")
    _require(type(symbol) is str and 0 < len(symbol) <= 64 and symbol == symbol.strip(),
             "symbol is invalid")
    _require((instrument.asset_class, instrument.contract_kind, instrument.currency)
             in {("EQUITY", "SPOT", "INR"), ("INDEX", "SPOT", "INR")}, "root is unsupported")
    _require({"XNSE": "NSE", "XBOM": "BSE"}.get(instrument.venue_code) == exchange,
             "exchange does not match root")
    return {"token": token, "symbol": symbol, "exchange": exchange, "kind": instrument.asset_class}


def _reference_rows(payload):
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), strict=True)
        _require(reader.fieldnames is not None and len(reader.fieldnames) == len(_REFERENCE_FIELDS)
                 and set(reader.fieldnames) == _REFERENCE_FIELDS, "current-reference columns are invalid")
        rows = []
        for row in reader:
            _require(len(rows) < 100_000 and None not in row and None not in row.values(),
                     "current-reference rows are invalid")
            rows.append(row)
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise MarketTruthError("historical attribution current reference is unavailable") from exc


def _verify_reference(payload, selected):
    token, symbol = str(selected["token"]), selected["symbol"]
    related = [row for row in _reference_rows(payload)
               if row["instrument_token"] == token or row["tradingsymbol"] == symbol]
    _require(len(related) == 1, "current-reference selection is ambiguous")
    row = related[0]
    segment = "INDICES" if selected["kind"] == "INDEX" else selected["exchange"]
    expected = (token, symbol, selected["exchange"], segment, "EQ", "")
    actual = tuple(row[key] for key in (
        "instrument_token", "tradingsymbol", "exchange", "segment", "instrument_type", "expiry"))
    _require(actual == expected, "current-reference selection does not match")


def _request(interval, requested_start, requested_end):
    _require(type(interval) is str and interval in INTERVAL_SECONDS, "interval is unsupported")
    start, end = (_instant(value, whole=True) for value in (requested_start, requested_end))
    _require(start <= end, "request range is invalid")
    return {"interval": interval, "from": start.isoformat(), "to": end.isoformat(),
            "continuous": False, "oi": False}


def _history_rows(payload):
    envelope = _closed(_json(payload), ("status", "data"))
    _require(envelope["status"] == "success", "response is not successful")
    rows = _closed(envelope["data"], ("candles",))["candles"]
    _require(type(rows) is list and 0 < len(rows) <= 2_000, "response row count is invalid")
    _require(all(type(row) is list and len(row) == 6 for row in rows), "response must contain OHLCV rows")
    return rows


def _row_time(value):
    try:
        _require(type(value) is str, "bar label is invalid")
        parsed = dt.datetime.fromisoformat(value)
        _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "bar timezone is absent")
        return _instant(parsed.astimezone(dt.timezone.utc), whole=True)
    except (ValueError, TypeError) as exc:
        raise MarketTruthError("historical attribution bar label is invalid") from exc


def _dated_bounds(events, request, captured_at, clock_binding):
    from app.market_truth.dated_sessions import expected_bars
    expected = expected_bars(clock_binding.calendar, requested_start=_instant(request["from"]),
        requested_end=_instant(request["to"]), resolution_seconds=clock_binding.resolution_seconds,
        cutoff_at=captured_at)
    _require(tuple(events) == tuple(event for event, _ in expected),
             "response does not cover the declared completed sessions")
    return events[0], expected[-1][1]


def _history_bounds(payload, request, captured_at, clock_binding=None):
    events = [_row_time(row[0]) for row in _history_rows(payload)]
    _require(all(left < right for left, right in zip(events, events[1:])), "bar order is invalid")
    if clock_binding is not None:
        return _dated_bounds(events, request, captured_at, clock_binding)
    start, end = _instant(request["from"]), _instant(request["to"])
    completed = events[-1] + dt.timedelta(seconds=INTERVAL_SECONDS[request["interval"]])
    _require(start <= events[0] <= events[-1] <= end and completed <= captured_at,
             "bars are outside the completed requested range")
    return events[0], completed


def _grant(contract, when):
    _require(contract.mode == "RESEARCH" and "HISTORICAL" in contract.permitted_uses,
             "requires an existing historical research grant")
    _require(contract.effective_from <= when
             and (contract.effective_to is None or when < contract.effective_to),
             "grant does not cover acquisition")


def _authorities(owner_id, connection_id, entity, product, contract):
    _require(type(connection_id) is int and connection_id > 0, "connection is invalid")
    _require(entity.entity_code == "kite" and product.entity_address == entity.address,
             "provider identity does not match")
    _require(contract.owner_id == owner_id and contract.product_address == product.address,
             "owner grant does not match")


def _capture_clocks(reference_received_at, reference_recorded_at, captured_at, recorded_at, as_of):
    reference_received_at, reference_recorded_at, captured_at, recorded_at, as_of = map(
        _instant, (reference_received_at, reference_recorded_at, captured_at, recorded_at, as_of))
    _require(reference_received_at <= reference_recorded_at <= as_of
             and reference_received_at <= captured_at <= recorded_at <= as_of,
             "acquisition clocks are incoherent")
    return reference_received_at, reference_recorded_at, captured_at, recorded_at, as_of


@dataclass(frozen=True)
class HistoricalAttribution:
    context: object
    current_reference: RawObservationSegment
    historical_response: RawObservationSegment
    receipt: RawObservationSegment
    clock_binding: object | None = None

    @property
    def mapping(self):
        return self.context.mapping


def _receipt_document(owner_id, connection_id, entity, product, contract, instrument,
                      selected, request, reference, response, clocks, clock_binding=None):
    reference_received, reference_recorded, captured_at, recorded_at, as_of = clocks
    document = {"schema": RECEIPT_SCHEMA, "owner_id": owner_id, "connection_id": connection_id,
        "provider_entity_address": entity.address, "provider_product_address": product.address,
        "provider_contract_address": contract.address, "instrument_address": instrument.address,
        "selection": selected, "request": request, "as_of": as_of.isoformat(),
        "current_reference": {"raw_address": reference.address,
            "received_at": reference_received.isoformat(), "recorded_at": reference_recorded.isoformat()},
        "historical_response": {"raw_address": response.address,
            "received_at": captured_at.isoformat(), "recorded_at": recorded_at.isoformat()}}
    if clock_binding is not None:
        document.update(schema=CLOCK_RECEIPT_SCHEMA, clock_binding=clock_binding.receipt_binding())
    return document


def _verified_clock(clock_binding, owner_id, entity, product, contract, instrument, interval, captured_at):
    if clock_binding is None:
        return None
    from app.market_data.dated_session_clock import verify_session_clock
    return verify_session_clock(clock_binding, owner_id=owner_id, entity=entity, product=product,
        contract=contract, instrument=instrument, resolution_seconds=INTERVAL_SECONDS[interval],
        as_of=captured_at)


def prepare_historical_attribution(*, owner_id, connection_id, entity, product, contract, instrument,
        token, symbol, exchange, interval, requested_start, requested_end, current_reference_bytes,
        reference_received_at, reference_recorded_at, historical_response_bytes, captured_at, recorded_at, as_of,
        clock_binding=None):
    """Prepare facts only; no grant/root creation, database write or provider call."""
    from app.market_data.kite_observations import KiteMappingContext
    _authorities(owner_id, connection_id, entity, product, contract)
    clocks = _capture_clocks(reference_received_at, reference_recorded_at, captured_at, recorded_at, as_of)
    _grant(contract, clocks[0]); _grant(contract, clocks[2])
    selected = _selection(instrument, token, symbol, exchange)
    request = _request(interval, requested_start, requested_end)
    clock_binding = _verified_clock(clock_binding, owner_id, entity, product, contract,
                                   instrument, interval, clocks[2])
    reference = RawObservationSegment(owner_id, product.address, contract.address, "text/csv",
        REFERENCE_SCHEMA, current_reference_bytes, clocks[1])
    response = RawObservationSegment(owner_id, product.address, contract.address, "application/json",
        RESPONSE_SCHEMA, historical_response_bytes, clocks[3])
    _verify_reference(reference.payload, selected)
    first, end = _history_bounds(response.payload, request, clocks[2], clock_binding)
    document = _receipt_document(owner_id, connection_id, entity, product, contract, instrument,
        selected, request, reference, response, clocks, clock_binding)
    receipt = RawObservationSegment(owner_id, product.address, contract.address, "application/json",
        document["schema"], canonical_json(document).encode(), max(clocks[1], clocks[3]))
    adapter = CLOCK_ADAPTER_SCHEMA if clock_binding is not None else ADAPTER_SCHEMA
    mapping = ProviderResponseInstrumentAlias(product.address, str(token), symbol, instrument.address,
        adapter, first, end, product.observation_namespace, receipt.address, contract.address)
    context = KiteMappingContext(owner_id, entity.address, product.address, contract.address,
        mapping, instrument, MAPPING_AUTHORITY)
    return HistoricalAttribution(context, reference, response, receipt, clock_binding)


def _receipt_parts(receipt):
    _require(receipt.raw_schema in {RECEIPT_SCHEMA, CLOCK_RECEIPT_SCHEMA}
             and receipt.media_type == "application/json",
             "receipt raw schema is invalid")
    fields = ("schema", "owner_id", "connection_id", "provider_entity_address",
        "provider_product_address", "provider_contract_address", "instrument_address", "selection", "request",
        "as_of", "current_reference", "historical_response")
    if receipt.raw_schema == CLOCK_RECEIPT_SCHEMA:
        fields += ("clock_binding",)
    doc = _closed(_json(receipt.payload), fields)
    _require(doc["schema"] == receipt.raw_schema, "receipt schema is invalid")
    selected = _closed(doc["selection"], ("token", "symbol", "exchange", "kind"))
    request = _closed(doc["request"], ("interval", "from", "to", "continuous", "oi"))
    _require(request["continuous"] is False and request["oi"] is False, "request flags are unsupported")
    reference = _closed(doc["current_reference"], ("raw_address", "received_at", "recorded_at"))
    response = _closed(doc["historical_response"], ("raw_address", "received_at", "recorded_at"))
    return doc, selected, request, reference, response


def _retained_clock(session, doc, instrument):
    if doc["schema"] == RECEIPT_SCHEMA:
        return None
    from app.market_data.dated_session_clock import load_session_clock
    return load_session_clock(session, owner_id=doc["owner_id"], instrument=instrument,
        product_address=doc["provider_product_address"], contract_address=doc["provider_contract_address"],
        binding=doc["clock_binding"], as_of=_instant(doc["as_of"]))


def _rebuild(session, receipt, reference, response, mapping):
    from app.market_truth.identity import load_canonical_instrument, load_provider_identity
    doc, selected, request, ref, history = _receipt_parts(receipt)
    entity, product, contract = load_provider_identity(session, doc["provider_contract_address"])
    instrument = load_canonical_instrument(session, doc["instrument_address"])
    expected = prepare_historical_attribution(owner_id=doc["owner_id"], connection_id=doc["connection_id"],
        entity=entity, product=product, contract=contract, instrument=instrument, token=selected["token"],
        symbol=selected["symbol"], exchange=selected["exchange"], interval=request["interval"],
        requested_start=request["from"], requested_end=request["to"], current_reference_bytes=reference.payload,
        reference_received_at=ref["received_at"], reference_recorded_at=ref["recorded_at"],
        historical_response_bytes=response.payload, captured_at=history["received_at"],
        recorded_at=history["recorded_at"], as_of=doc["as_of"],
        clock_binding=_retained_clock(session, doc, instrument))
    if type(mapping) is ProviderInstrumentAlias:
        _require(doc["schema"] == RECEIPT_SCHEMA, "legacy alias cannot carry new clock semantics")
        legacy_fields = expected.mapping.fact()
        legacy_fields.pop("provider_contract_address")
        legacy_fields.update(effective_from=expected.mapping.effective_from,
                             effective_to=expected.mapping.effective_to)
        expected = replace(expected, context=replace(expected.context,
            mapping=ProviderInstrumentAlias(**legacy_fields)))
    _require((expected.receipt, expected.current_reference, expected.historical_response)
             == (receipt, reference, response), "retained request/response binding differs")
    return expected


def persist_historical_attribution(session, attribution):
    """Validate existing authorities and atomically retain this bounded response."""
    from app.db.concurrency import caller_owned_savepoint
    from app.market_data.observations import persist_raw_segment
    from app.market_truth.identity import persist_provider_alias
    _require(type(attribution) is HistoricalAttribution, "prepared facts are required")
    expected = _rebuild(session, attribution.receipt, attribution.current_reference, attribution.historical_response,
                        attribution.mapping)
    _require(expected == attribution, "prepared context differs from retained evidence")
    with caller_owned_savepoint(session, scope="kite-historical-attribution"):
        for segment in (attribution.current_reference, attribution.historical_response, attribution.receipt):
            persist_raw_segment(session, segment)
        persist_provider_alias(session, attribution.mapping)
    return attribution.context


def load_historical_attribution(session, mapping):
    from app.market_data.observations import load_raw_segment
    _require(mapping.adapter_schema_version in ADAPTER_SCHEMAS, "mapping variant is unsupported")
    receipt = load_raw_segment(session, mapping.source_evidence_address)
    _, _, _, reference, response = _receipt_parts(receipt)
    expected = _rebuild(session, receipt, load_raw_segment(session, reference["raw_address"]),
                        load_raw_segment(session, response["raw_address"]), mapping)
    _require(expected.mapping == mapping, "alias does not match retained attribution")
    return expected


def validate_historical_capture_attribution(session, context, *, connection_id, raw_response, captured_at, recorded_at,
        requested_start, requested_end, resolution_seconds, clock_binding=None):
    attribution = load_historical_attribution(session, context.mapping)
    doc, _, request, _, response = _receipt_parts(attribution.receipt)
    _require(type(connection_id) is int and connection_id == doc["connection_id"],
             "publication connection differs")
    _require(attribution.context == context and raw_response == attribution.historical_response.payload,
             "publication response or context differs")
    _require(attribution.clock_binding == clock_binding, "publication bar-clock evidence differs")
    expected = (_instant(response["received_at"]), _instant(response["recorded_at"]),
                _instant(request["from"]), _instant(request["to"]), INTERVAL_SECONDS[request["interval"]])
    _require(expected == (captured_at, recorded_at, requested_start, requested_end, resolution_seconds),
             "publication request or clocks differ")
    return expected[0]


def _observation_response(session, mapping):
    from app.market_data.observations import _observation_pass_memo
    memo = _observation_pass_memo(session)
    key = ("historical-response", mapping.address)
    if memo is not None and key in memo:
        return memo[key]
    attribution = load_historical_attribution(session, mapping)
    doc, _, request, _, response = _receipt_parts(attribution.receipt)
    rows = {_row_time(row[0]): row for row in _history_rows(attribution.historical_response.payload)}
    result = (attribution, doc, request, response, rows, {})
    if memo is not None:
        memo[key] = result
    return result


def _observation_response_batch(evidence, event_time):
    from app.market_data.kite_observations import map_historical_candles
    attribution, doc, request, response, rows, batches = evidence
    _require(event_time in rows, "observation is absent from the retained response")
    if event_time not in batches:
        batches[event_time] = map_historical_candles(
            {"status": "success", "data": {"candles": [rows[event_time]]}},
            context=attribution.context, resolution_seconds=INTERVAL_SECONDS[request["interval"]],
            available_at=_instant(response["received_at"]), recorded_at=_instant(response["recorded_at"]),
            as_of=_instant(doc["as_of"]),
            dated_sessions=attribution.clock_binding.calendar if attribution.clock_binding is not None else None)
    return batches[event_time]


def observation_grant_time(session, observation, mapping, segment):
    """Use acquisition only after this exact observation is proved in its response."""
    if mapping.adapter_schema_version not in ADAPTER_SCHEMAS:
        return observation.event_time
    evidence = _observation_response(session, mapping)
    batch = _observation_response_batch(evidence, observation.event_time)
    _require(segment == batch.raw_segment and observation in batch.observations,
             "observation bytes or identity differ from the retained response")
    return _instant(evidence[3]["received_at"])
