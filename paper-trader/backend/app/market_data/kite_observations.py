"""Pure offline mapping of sanitized Kite Connect v3 response shapes.

The adapter forms existing immutable provider/raw observation facts. It does not
open a connection, read credentials, register a public capability, persist data,
or infer historical derivative identity from today's instrument dump.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from app.ir.hashing import canonical_json
from app.ir.validity import ValidityState
from app.market_data.numeric import NumericIngressError, market_float
from app.market_data.observations import ProviderObservation, RawObservationSegment
from app.market_truth.identity import CanonicalPhysicalInstrument, ProviderInstrumentAlias
from app.providers.base import (
    ProviderFactError,
    ProviderUnavailable,
    ProviderUnavailableReason,
)

MAX_PAYLOAD_BYTES = 1024 * 1024
MAX_HISTORICAL_ROWS = 2_000
MAX_INSTRUMENT_ROWS = 10_000
MAX_QUOTE_INSTRUMENTS = 500
DEPTH_LEVELS = 5

_UTC = dt.timezone.utc
_ADDRESS_PREFIX = "sha256:"
_MAPPING_AUTHORITIES = {"CURRENT_DUMP", "CAPTURED_POINT_IN_TIME", "RETROSPECTIVE_RESPONSE"}
_SENSITIVE_KEYS = frozenset({
    "access_token", "api_key", "api_secret", "authorization", "credential",
    "password", "private_key", "refresh_token", "secret", "totp",
})
_QUOTE_ROW_KEYS = frozenset({
    "instrument_token", "timestamp", "last_trade_time", "last_price",
    "last_quantity", "average_price", "volume", "buy_quantity", "sell_quantity",
    "change", "net_change", "lower_circuit_limit", "upper_circuit_limit",
    "ohlc", "oi", "oi_day_high", "oi_day_low", "depth",
})


@dataclass(frozen=True)
class KiteMappingContext:
    owner_id: str
    provider_entity_address: str
    provider_product_address: str
    provider_contract_address: str
    mapping: ProviderInstrumentAlias
    canonical_instrument: CanonicalPhysicalInstrument
    mapping_authority: str

    def __post_init__(self) -> None:
        _validate_context_identity(self)
        if not isinstance(self.mapping, ProviderInstrumentAlias):
            raise ProviderFactError("mapping must be a canonical provider alias")
        if not isinstance(self.canonical_instrument, CanonicalPhysicalInstrument):
            raise ProviderFactError("canonical instrument authority is required")
        if (self.mapping.product_address != self.provider_product_address
                or self.mapping.canonical_instrument_address != self.canonical_instrument.address):
            raise ProviderFactError("provider mapping does not match the supplied authorities")
        if self.mapping_authority not in _MAPPING_AUTHORITIES:
            raise ProviderFactError("mapping authority is not closed")
        _validate_retrospective_context(self)

    @property
    def quote_key(self) -> str:
        if self.mapping_authority == "RETROSPECTIVE_RESPONSE":
            raise ProviderFactError("retrospective response attribution cannot supply quotes")
        venue = _kite_exchange(self.canonical_instrument)
        return f"{venue}:{self.mapping.provider_symbol}"


def _validate_context_identity(context):
    if not isinstance(context.owner_id, str) or not context.owner_id:
        raise ProviderFactError("owner_id is required")
    for name in ("provider_entity_address", "provider_product_address", "provider_contract_address"):
        value = getattr(context, name)
        if (not isinstance(value, str) or not value.startswith(_ADDRESS_PREFIX) or len(value) != 71):
            raise ProviderFactError(f"{name} is not a canonical address")


def _validate_retrospective_context(context):
    from app.market_data.kite_historical_attribution import ADAPTER_SCHEMAS, MAPPING_AUTHORITY
    retrospective = context.mapping_authority == MAPPING_AUTHORITY
    if retrospective != (context.mapping.adapter_schema_version in ADAPTER_SCHEMAS):
        raise ProviderFactError("retrospective mapping requires its retained response adapter")
    scope = getattr(context.mapping, "provider_contract_address", context.provider_contract_address)
    if scope != context.provider_contract_address:
        raise ProviderFactError("response mapping contract differs from context")
    if retrospective and context.canonical_instrument.contract_kind != "SPOT":
        raise ProviderFactError("retrospective response attribution only supports spot roots")


@dataclass(frozen=True)
class KiteInstrumentBinding:
    canonical_instrument: CanonicalPhysicalInstrument
    effective_from: dt.datetime
    effective_to: dt.datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_instrument, CanonicalPhysicalInstrument):
            raise ProviderFactError("instrument binding requires canonical authority")
        start = _aware_utc(self.effective_from, "effective_from")
        end = (_aware_utc(self.effective_to, "effective_to")
               if self.effective_to is not None else None)
        if end is not None and end <= start:
            raise ProviderFactError("instrument binding interval is incoherent")
        object.__setattr__(self, "effective_from", start)
        object.__setattr__(self, "effective_to", end)


@dataclass(frozen=True)
class KiteObservationBatch:
    raw_segments: tuple[RawObservationSegment, ...]
    observations: tuple[ProviderObservation, ...]
    unavailable: tuple[ProviderUnavailable, ...]

    @property
    def raw_segment(self) -> RawObservationSegment:
        """The sole segment for quote responses; candle rows stay independently addressed."""
        if len(self.raw_segments) != 1:
            raise ProviderFactError("batch does not contain exactly one raw segment")
        return self.raw_segments[0]


def _aware_utc(value: object, name: str) -> dt.datetime:
    if (not isinstance(value, dt.datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        raise ProviderFactError(f"{name} must be timezone-aware")
    return value.astimezone(_UTC)


def _parse_time(value: object, name: str) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise ProviderFactError(f"{name} is missing")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProviderFactError(f"{name} is malformed") from exc
    return _aware_utc(parsed, name)


def _timeline(*, event: dt.datetime, completed: dt.datetime, available: dt.datetime,
              recorded: dt.datetime, as_of: dt.datetime) -> tuple[dt.datetime, ...]:
    event = _aware_utc(event, "event_time")
    completed = _aware_utc(completed, "completed_at")
    available = _aware_utc(available, "available_at")
    recorded = _aware_utc(recorded, "recorded_at")
    as_of = _aware_utc(as_of, "as_of")
    if completed < event:
        raise ProviderFactError("completed_at precedes event_time")
    if available < completed:
        raise ProviderFactError("available_at is before completed_at")
    if recorded < available:
        raise ProviderFactError("recorded_at precedes available_at")
    if any(value > as_of for value in (event, completed, available, recorded)):
        raise ProviderFactError("future provider fact is not available at as_of")
    return event, completed, available, recorded, as_of


def _capture_times(available: dt.datetime, recorded: dt.datetime,
                   as_of: dt.datetime) -> tuple[dt.datetime, dt.datetime, dt.datetime]:
    available = _aware_utc(available, "available_at")
    recorded = _aware_utc(recorded, "recorded_at")
    as_of = _aware_utc(as_of, "as_of")
    if recorded < available:
        raise ProviderFactError("recorded_at precedes available_at")
    if available > as_of or recorded > as_of:
        raise ProviderFactError("future provider fact is not available at as_of")
    return available, recorded, as_of


def _closed_envelope(payload: object, *, data_key: str | None = None) -> Mapping[str, Any]:
    if (type(payload) is not dict or set(payload) != {"status", "data"}
            or payload.get("status") != "success" or type(payload.get("data")) is not dict):
        raise ProviderFactError("payload is not a closed official envelope")
    data = payload["data"]
    if data_key is not None and (set(data) != {data_key} or type(data[data_key]) is not list):
        raise ProviderFactError("payload is not a closed official envelope")
    return data


def _payload_bytes(payload: object) -> bytes:
    _reject_sensitive_keys(payload)
    try:
        encoded = canonical_json(payload).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProviderFactError("provider payload is not canonical JSON data") from exc
    if not encoded or len(encoded) > MAX_PAYLOAD_BYTES:
        raise ProviderFactError("provider payload bound exceeded")
    return encoded


def _reject_sensitive_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _SENSITIVE_KEYS or any(part in lowered for part in (
                    "credential", "password", "private_key", "access_token")):
                raise ProviderFactError("provider payload contains a sensitive field")
            _reject_sensitive_keys(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _reject_sensitive_keys(item)


def _numeric(value: object, field: str, *, minimum: float | None = None) -> float:
    try:
        number = market_float(value, field=f"kite {field}")
    except NumericIngressError as exc:
        raise ProviderFactError(str(exc)) from exc
    if minimum is not None and number < minimum:
        raise ProviderFactError(f"kite {field} is below its bound")
    return number


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ProviderFactError(f"kite {field} must be an integer at least {minimum}")
    return value


def _kite_exchange(instrument: CanonicalPhysicalInstrument) -> str:
    table = {
        ("XNSE", "SPOT"): "NSE",
        ("XNSE", "FUTURE"): "NFO",
        ("XNSE", "WEEKLY_OPTION"): "NFO",
        ("XNSE", "MONTHLY_OPTION"): "NFO",
        ("XBOM", "SPOT"): "BSE",
        ("XBOM", "FUTURE"): "BFO",
        ("XBOM", "WEEKLY_OPTION"): "BFO",
        ("XBOM", "MONTHLY_OPTION"): "BFO",
        ("XMCX", "FUTURE"): "MCX",
        ("XMCX", "WEEKLY_OPTION"): "MCX",
        ("XMCX", "MONTHLY_OPTION"): "MCX",
    }
    try:
        return table[(instrument.venue_code, instrument.contract_kind)]
    except KeyError as exc:
        raise ProviderFactError("canonical instrument has no admitted Kite venue mapping") from exc


def _kite_segment(instrument: CanonicalPhysicalInstrument) -> str:
    exchange = _kite_exchange(instrument)
    if instrument.asset_class == "INDEX":
        return "INDICES"
    if exchange in {"NFO", "BFO"}:
        suffix = "FUT" if instrument.contract_kind == "FUTURE" else "OPT"
        return f"{exchange}-{suffix}"
    return exchange


def _mapping_covers(context: KiteMappingContext, when: dt.datetime) -> None:
    when = _aware_utc(when, "mapping instant")
    mapping = context.mapping
    if when < mapping.effective_from or (
            mapping.effective_to is not None and when >= mapping.effective_to):
        raise ProviderFactError("provider mapping does not cover the observation instant")


def _raw_range(payload: bytes, value: object, *, start: int = 0) -> tuple[int, int, str]:
    needle = canonical_json(value).encode("utf-8")
    offset = payload.find(needle, start)
    if offset < 0:
        raise ProviderFactError("raw provider value is not present in its segment")
    return offset, len(needle), hashlib.sha256(needle).hexdigest()


def _segment(context: KiteMappingContext, payload: bytes, *, raw_schema: str,
             recorded_at: dt.datetime) -> RawObservationSegment:
    return RawObservationSegment(
        context.owner_id, context.provider_product_address,
        context.provider_contract_address, "application/json", raw_schema,
        payload, recorded_at,
    )


def _correction_id(sequence: str, resolution_seconds: int) -> str:
    # A bounded identity for one field/event/resolution; provider sequence stays intact.
    return hashlib.sha256(canonical_json([sequence, resolution_seconds]).encode("utf-8")).hexdigest()


def _observation(context: KiteMappingContext, segment: RawObservationSegment, *,
                 field: str, resolution_seconds: int, event: dt.datetime,
                 completed: dt.datetime, available: dt.datetime, recorded: dt.datetime,
                 raw_range: tuple[int, int, str], sequence: str) -> ProviderObservation:
    offset, length, digest = raw_range
    return ProviderObservation(
        context.owner_id, context.provider_entity_address,
        context.provider_product_address, context.provider_contract_address,
        context.mapping.address, context.mapping.provider_token, segment.raw_schema,
        field, resolution_seconds, event, completed, available, recorded,
        sequence, _correction_id(sequence, resolution_seconds), segment.address, offset, length, digest,
        ValidityState.VALID,
    )


def _dedupe_unavailable(values: Sequence[ProviderUnavailable]) -> tuple[ProviderUnavailable, ...]:
    return tuple(dict.fromkeys(values))


def _historical_completion(event, resolution_seconds, dated_sessions):
    if dated_sessions is None:
        return event + dt.timedelta(seconds=resolution_seconds)
    from app.market_truth.dated_sessions import completion_for
    return completion_for(dated_sessions, event, resolution_seconds)


def _historical_fields(row: list) -> tuple[str, ...]:
    open_, high, low, close = (
        _numeric(row[position], field, minimum=0.0)
        for position, field in zip(range(1, 5), ("open", "high", "low", "close"), strict=True)
    )
    if (min(open_, high, low, close) <= 0
            or high < max(open_, close, low)
            or low > min(open_, close, high)):
        raise ProviderFactError("historical candle OHLC is incoherent")
    _numeric(row[5], "volume", minimum=0.0)
    fields = ("open", "high", "low", "close", "volume")
    if len(row) == 7:
        _numeric(row[6], "oi", minimum=0.0)
        return fields + ("oi",)
    return fields


def _historical_rows(payload: object, context: KiteMappingContext,
                     resolution_seconds: int) -> list:
    if type(resolution_seconds) is not int or resolution_seconds <= 0:
        raise ProviderFactError("resolution_seconds must be a positive integer")
    if (context.canonical_instrument.contract_kind != "SPOT"
            and context.mapping_authority != "CAPTURED_POINT_IN_TIME"):
        raise ProviderFactError("historical derivative requires captured point-in-time mapping")
    data = _closed_envelope(payload, data_key="candles")
    rows = data["candles"]
    if len(rows) > MAX_HISTORICAL_ROWS:
        raise ProviderFactError("historical row bound exceeded")
    return rows


def _historical_row_timeline(row: object, *, context: KiteMappingContext,
                             resolution_seconds: int, dated_sessions,
                             previous_event: dt.datetime | None,
                             capture_times: tuple[dt.datetime, dt.datetime, dt.datetime],
                             ) -> tuple[dt.datetime, ...]:
    if type(row) is not list or len(row) not in {6, 7}:
        raise ProviderFactError("historical candle must contain six or seven fields")
    event = _parse_time(row[0], "historical candle timestamp")
    completed = _historical_completion(event, resolution_seconds, dated_sessions)
    available, recorded, as_of = capture_times
    if completed > as_of:
        raise ProviderFactError("forming or future historical candle refuses")
    times = _timeline(event=event, completed=completed, available=available,
                      recorded=recorded, as_of=as_of)
    if previous_event is not None and times[0] <= previous_event:
        raise ProviderFactError("historical candles are not strictly increasing")
    _mapping_covers(context, times[0])
    return times


def map_historical_candles(
    payload: object,
    *,
    context: KiteMappingContext,
    resolution_seconds: int,
    available_at: dt.datetime,
    recorded_at: dt.datetime,
    as_of: dt.datetime,
    dated_sessions=None,
) -> KiteObservationBatch:
    """Map the documented six/seven-column historical candle response."""
    rows = _historical_rows(payload, context, resolution_seconds)
    raw = _payload_bytes(payload)
    capture_times = _capture_times(available_at, recorded_at, as_of)
    recorded = capture_times[1]
    segments: list[RawObservationSegment] = []
    observations: list[ProviderObservation] = []
    unavailable: list[ProviderUnavailable] = []
    previous_event: dt.datetime | None = None
    for row in rows:
        event, completed, row_available, row_recorded, _ = _historical_row_timeline(
            row, context=context, resolution_seconds=resolution_seconds,
            dated_sessions=dated_sessions, previous_event=previous_event,
            capture_times=capture_times,
        )
        previous_event = event
        fields = _historical_fields(row)
        if len(row) == 6:
            unavailable.append(ProviderUnavailable(
                context.mapping.provider_token, "OI", ProviderUnavailableReason.FIELD_ABSENT))
        source_bytes = canonical_json(row).encode("utf-8")
        segment = _segment(context, source_bytes, raw_schema="kite-historical-candle/3",
                           recorded_at=recorded)
        segments.append(segment)
        row_range = (0, len(source_bytes), hashlib.sha256(source_bytes).hexdigest())
        for field in fields:
            observations.append(_observation(
                context, segment, field=field, resolution_seconds=resolution_seconds,
                event=event, completed=completed, available=row_available,
                recorded=row_recorded, raw_range=row_range,
                sequence=f"history:{context.mapping.provider_token}:{event.isoformat()}:{field}",
            ))
    if not segments:
        segments.append(_segment(
            context, raw, raw_schema="kite-historical-candle/3", recorded_at=recorded))
    return KiteObservationBatch(tuple(segments), tuple(observations),
                                _dedupe_unavailable(unavailable))


def _validate_depth(depth: object) -> tuple[tuple[str, int, Mapping[str, Any]], ...]:
    if type(depth) is not dict or set(depth) != {"buy", "sell"}:
        raise ProviderFactError("depth must contain exactly buy and sell")
    output: list[tuple[str, int, Mapping[str, Any]]] = []
    prices: dict[str, list[float]] = {"buy": [], "sell": []}
    for side in ("buy", "sell"):
        levels = depth[side]
        if type(levels) is not list or len(levels) != DEPTH_LEVELS:
            raise ProviderFactError("depth side must contain exactly five levels")
        for index, level in enumerate(levels):
            if type(level) is not dict or set(level) != {"quantity", "price", "orders"}:
                raise ProviderFactError("depth level is not a closed official shape")
            _integer(level["quantity"], f"depth {side} quantity")
            _integer(level["orders"], f"depth {side} orders")
            prices[side].append(_numeric(level["price"], f"depth {side} price", minimum=0.0))
            output.append((side, index, level))
    if any(left < right for left, right in zip(prices["buy"], prices["buy"][1:])):
        raise ProviderFactError("buy depth prices are incoherent")
    if any(left > right for left, right in zip(prices["sell"], prices["sell"][1:])):
        raise ProviderFactError("sell depth prices are incoherent")
    if prices["buy"][0] > 0 and prices["sell"][0] > 0 \
            and prices["buy"][0] > prices["sell"][0]:
        raise ProviderFactError("depth book is crossed")
    return tuple(output)


def map_quote_snapshot(
    payload: object,
    *,
    contexts: Sequence[KiteMappingContext],
    available_at: dt.datetime,
    recorded_at: dt.datetime,
    as_of: dt.datetime,
) -> KiteObservationBatch:
    """Map one documented full-quote response without defaulting absent fields."""
    if not isinstance(contexts, (tuple, list)) or not contexts:
        raise ProviderFactError("quote mapping contexts are required")
    if len(contexts) > MAX_QUOTE_INSTRUMENTS:
        raise ProviderFactError("quote instrument request bound exceeded")
    if any(not isinstance(item, KiteMappingContext) for item in contexts):
        raise ProviderFactError("quote mapping context is malformed")
    quote_keys = tuple(item.quote_key for item in contexts)
    tokens = tuple(item.mapping.provider_token for item in contexts)
    if len(set(quote_keys)) != len(quote_keys) or len(set(tokens)) != len(tokens):
        raise ProviderFactError("quote contexts must have unique keys and tokens")
    first = contexts[0]
    if any((item.owner_id, item.provider_entity_address, item.provider_product_address,
            item.provider_contract_address) !=
           (first.owner_id, first.provider_entity_address, first.provider_product_address,
            first.provider_contract_address) for item in contexts[1:]):
        raise ProviderFactError("quote batch authorities are inconsistent")
    data = _closed_envelope(payload)
    unexpected = set(data) - set(quote_keys)
    if unexpected:
        raise ProviderFactError("quote response contains an unrequested instrument key")
    rows: dict[str, dict[str, Any] | None] = {}
    for quote_key in quote_keys:
        if quote_key not in data:
            rows[quote_key] = None
            continue
        row = data[quote_key]
        if type(row) is not dict:
            raise ProviderFactError("quote row is malformed")
        _reject_sensitive_keys(row)
        if not set(row).issubset(_QUOTE_ROW_KEYS):
            raise ProviderFactError("quote row contains an undocumented field")
        if "instrument_token" not in row or "timestamp" not in row:
            raise ProviderFactError("quote row is missing required keys")
        rows[quote_key] = row
    raw = _payload_bytes(payload)
    available, recorded, as_of_value = _capture_times(available_at, recorded_at, as_of)
    segment = _segment(first, raw, raw_schema="kite-quote-snapshot/3", recorded_at=recorded)
    observations: list[ProviderObservation] = []
    unavailable: list[ProviderUnavailable] = []
    for context in contexts:
        row = rows[context.quote_key]
        if row is None:
            unavailable.append(ProviderUnavailable(
                context.mapping.provider_token, "QUOTE",
                ProviderUnavailableReason.MISSING_QUOTE_KEY))
            continue
        token = _integer(row["instrument_token"], "instrument_token", minimum=1)
        if str(token) != context.mapping.provider_token:
            raise ProviderFactError("quote token does not match canonical mapping")
        event = _parse_time(row["timestamp"], "quote timestamp")
        if "last_trade_time" in row and row["last_trade_time"] is not None:
            last_trade = _parse_time(row["last_trade_time"], "last_trade_time")
            if last_trade > event:
                raise ProviderFactError("last trade time is after quote timestamp")
        event, completed, row_available, row_recorded, _ = _timeline(
            event=event, completed=event, available=available,
            recorded=recorded, as_of=as_of_value,
        )
        _mapping_covers(context, event)
        row_range = _raw_range(raw, row)
        scalar_fields = (
            "last_price", "last_quantity", "average_price", "volume",
            "buy_quantity", "sell_quantity", "change", "net_change",
            "lower_circuit_limit", "upper_circuit_limit",
        )
        for field in scalar_fields:
            if field in row:
                minimum = None if field == "change" else 0.0
                _numeric(row[field], field, minimum=minimum)
                observations.append(_observation(
                    context, segment, field=field, resolution_seconds=1,
                    event=event, completed=completed, available=row_available,
                    recorded=row_recorded, raw_range=row_range,
                    sequence=f"quote:{context.mapping.provider_token}:{event.isoformat()}:{field}",
                ))
        if "ohlc" in row:
            ohlc = row["ohlc"]
            if type(ohlc) is not dict or set(ohlc) != {"open", "high", "low", "close"}:
                raise ProviderFactError("quote OHLC is not a closed official shape")
            values = {field: _numeric(value, f"ohlc {field}", minimum=0.0)
                      for field, value in ohlc.items()}
            if (min(values.values()) <= 0 or values["high"] < max(values.values())
                    or values["low"] > min(values.values())):
                raise ProviderFactError("quote OHLC is incoherent")
            for field in ("open", "high", "low", "close"):
                name = f"ohlc.{field}"
                observations.append(_observation(
                    context, segment, field=name, resolution_seconds=1,
                    event=event, completed=completed, available=row_available,
                    recorded=row_recorded, raw_range=row_range,
                    sequence=f"quote:{context.mapping.provider_token}:{event.isoformat()}:{name}",
                ))
        if "oi" in row:
            _numeric(row["oi"], "oi", minimum=0.0)
            observations.append(_observation(
                context, segment, field="oi", resolution_seconds=1,
                event=event, completed=completed, available=row_available,
                recorded=row_recorded, raw_range=row_range,
                sequence=f"quote:{context.mapping.provider_token}:{event.isoformat()}:oi",
            ))
        else:
            unavailable.append(ProviderUnavailable(
                context.mapping.provider_token, "OI", ProviderUnavailableReason.FIELD_ABSENT))
        if "depth" in row:
            for side, index, level in _validate_depth(row["depth"]):
                for leaf in ("quantity", "price", "orders"):
                    field = f"depth.{side}.{index}.{leaf}"
                    observations.append(_observation(
                        context, segment, field=field, resolution_seconds=1,
                        event=event, completed=completed, available=row_available,
                        recorded=row_recorded, raw_range=row_range,
                        sequence=(f"quote:{context.mapping.provider_token}:"
                                  f"{event.isoformat()}:{field}"),
                    ))
        else:
            unavailable.append(ProviderUnavailable(
                context.mapping.provider_token, "DEPTH", ProviderUnavailableReason.FIELD_ABSENT))
    return KiteObservationBatch((segment,), tuple(observations),
                                _dedupe_unavailable(unavailable))


def _canonical_decimal_matches(value: object, expected: str) -> bool:
    try:
        return Decimal(str(value)) == Decimal(expected)
    except (InvalidOperation, ValueError):
        return False


def _validate_instrument_row(row: object, binding: KiteInstrumentBinding,
                             token: str, dump_at: dt.datetime) -> str:
    required = {"instrument_token", "tradingsymbol", "expiry", "strike", "lot_size",
                "instrument_type", "segment", "exchange"}
    if type(row) is not dict or not required.issubset(row):
        raise ProviderFactError("instrument row is missing required keys")
    if str(_integer(row["instrument_token"], "instrument_token", minimum=1)) != token:
        raise ProviderFactError("instrument token does not match its binding")
    symbol = row["tradingsymbol"]
    if not isinstance(symbol, str) or not symbol:
        raise ProviderFactError("instrument symbol is missing")
    instrument = binding.canonical_instrument
    expected_exchange = _kite_exchange(instrument)
    if row["exchange"] != expected_exchange or row["segment"] != _kite_segment(instrument):
        raise ProviderFactError("instrument venue does not match canonical identity")
    expected_type = {"SPOT": "EQ", "FUTURE": "FUTURE",
                     "WEEKLY_OPTION": instrument.option_right,
                     "MONTHLY_OPTION": instrument.option_right}[instrument.contract_kind]
    expected_type = {"CALL": "CE", "PUT": "PE"}.get(expected_type, expected_type)
    expected_type = "FUT" if expected_type == "FUTURE" else expected_type
    if row["instrument_type"] != expected_type:
        raise ProviderFactError("instrument type does not match canonical identity")
    if instrument.contract_kind == "SPOT":
        if row["expiry"] not in {"", None} or _numeric(row["strike"], "strike") != 0:
            raise ProviderFactError("spot dump row carries derivative terms")
    else:
        expiry = row["expiry"]
        try:
            expiry_date = expiry if isinstance(expiry, dt.date) else dt.date.fromisoformat(expiry)
        except (TypeError, ValueError) as exc:
            raise ProviderFactError("instrument expiry is malformed") from exc
        if expiry_date < dump_at.date():
            raise ProviderFactError("expired contract cannot be inferred from today's dump")
        if instrument.expiry is None or expiry_date != instrument.expiry.date():
            raise ProviderFactError("instrument expiry does not match canonical identity")
        if instrument.contract_kind in {"WEEKLY_OPTION", "MONTHLY_OPTION"}:
            if (instrument.strike is None
                    or not _canonical_decimal_matches(row["strike"], instrument.strike)):
                raise ProviderFactError("instrument strike does not match canonical identity")
        if (instrument.multiplier is None
                or _integer(row["lot_size"], "lot_size", minimum=1)
                != int(Decimal(instrument.multiplier))):
            raise ProviderFactError("instrument lot size does not match canonical identity")
    if binding.effective_from != dump_at or binding.effective_to is None \
            or binding.effective_to <= dump_at:
        raise ProviderFactError(
            "current dump binding must start at the dump instant and have an explicit end")
    return symbol


def map_instrument_dump(
    rows: Sequence[object],
    *,
    bindings: Mapping[str, KiteInstrumentBinding],
    product_address: str,
    observation_namespace: str,
    source_evidence_address: str,
    dump_at: dt.datetime,
) -> tuple[ProviderInstrumentAlias, ...]:
    """Validate selected current rows; never treat the dump as historical truth."""
    if not isinstance(rows, (tuple, list)) or len(rows) > MAX_INSTRUMENT_ROWS:
        raise ProviderFactError("instrument row bound exceeded")
    if not isinstance(bindings, Mapping):
        raise ProviderFactError("instrument bindings are malformed")
    dump_instant = _aware_utc(dump_at, "dump_at")
    if any(not isinstance(token, str) or not token or not isinstance(binding, KiteInstrumentBinding)
           for token, binding in bindings.items()):
        raise ProviderFactError("instrument binding is malformed")
    selected: dict[str, object] = {}
    for row in rows:
        if type(row) is dict and "instrument_token" in row:
            raw_token = row["instrument_token"]
            if type(raw_token) is int and raw_token > 0 and str(raw_token) in bindings:
                token = str(raw_token)
                if token in selected:
                    raise ProviderFactError("instrument dump repeats a bound token")
                selected[token] = row
    aliases: list[ProviderInstrumentAlias] = []
    for token, binding in bindings.items():
        if token not in selected:
            raise ProviderFactError("instrument dump is missing a bound token")
        symbol = _validate_instrument_row(selected[token], binding, token, dump_instant)
        aliases.append(ProviderInstrumentAlias(
            product_address, token, symbol, binding.canonical_instrument.address,
            "kite-static/1", binding.effective_from, binding.effective_to,
            observation_namespace, source_evidence_address,
        ))
    return tuple(aliases)
