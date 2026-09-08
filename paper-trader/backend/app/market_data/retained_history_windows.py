"""Bounded retained intraday capture catalogs, without source or execution grants.

Catalog windows are explicit request intervals, not inferred trading sessions.
The consuming bundle must verify every referenced raw source and clock binding.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from types import MappingProxyType
from typing import Mapping

from app.ir.hashing import canonical_json
from app.market_data.kite_historical_attribution import _closed, _instant, _json
from app.market_data.observations import RawObservationSegment
from app.market_truth.identity import MarketTruthError, _address, _closed_text

SCHEMA = "kite-intraday-capture-catalog/1"
MAX_CATALOG_BYTES = 4 * 1024 * 1024
MAX_CAPTURE_WINDOWS = 2366
_FIELDS = {"schema", "owner_id", "product_address", "contract_address", "clock_binding",
           "selection_address", "requested_start", "requested_end", "rows"}
_CLOCK_FIELDS = {"calendar_source_address", "completion_source_address", "calendar_address",
                 "resolution_seconds"}
_ROW_FIELDS = {"raw", "received_at", "from", "to", "mapping", "reference_raw",
               "reference_received_at", "reference_recorded_at"}


@dataclass(frozen=True, slots=True)
class CaptureCatalog:
    owner_id: str
    product_address: str
    contract_address: str
    clock_binding: Mapping[str, str | int]
    selection_address: str
    requested_start: dt.datetime
    requested_end: dt.datetime
    rows: tuple[Mapping[str, str], ...]

    def __post_init__(self):
        object.__setattr__(self, "clock_binding", MappingProxyType(dict(self.clock_binding)))
        object.__setattr__(self, "rows", tuple(MappingProxyType(dict(row)) for row in self.rows))

    def payload(self):
        return {"schema": SCHEMA, "owner_id": self.owner_id,
                "product_address": self.product_address, "contract_address": self.contract_address,
                "clock_binding": dict(self.clock_binding), "selection_address": self.selection_address,
                "requested_start": self.requested_start.isoformat(),
                "requested_end": self.requested_end.isoformat(),
                "rows": [dict(row) for row in self.rows]}


def _require(condition, reason):
    if not condition:
        raise MarketTruthError(f"capture catalog {reason}")


def _scope(owner_id, product_address, contract_address):
    _closed_text(owner_id, "catalog owner", maximum=64)
    _address(product_address, "catalog product")
    _address(contract_address, "catalog contract")
    return owner_id, product_address, contract_address


def _raw_document(raw, scope, as_of):
    _require(type(raw) is RawObservationSegment, "requires retained raw bytes")
    raw.__post_init__()
    _require((raw.owner_id, raw.product_address, raw.contract_address) == scope,
             "raw scope differs")
    _require((raw.media_type, raw.raw_schema) == ("application/json", SCHEMA),
             "raw schema differs")
    _require(_instant(raw.recorded_at) <= as_of, "raw recording is in the future")
    _require(len(raw.payload) <= MAX_CATALOG_BYTES, "payload exceeds 4 MiB")
    try:
        document = _closed(_json(raw.payload), _FIELDS)
        canonical_json(document).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise MarketTruthError("capture catalog JSON is invalid") from exc
    _require(document["schema"] == SCHEMA, "schema differs")
    _require((document["owner_id"], document["product_address"], document["contract_address"]) == scope,
             "document scope differs")
    return document


def _clock_binding(value):
    _closed(value, _CLOCK_FIELDS)
    for field in ("calendar_source_address", "completion_source_address", "calendar_address"):
        _address(value[field], field)
    resolution = value["resolution_seconds"]
    _require(type(resolution) is int and resolution in (900, 1800, 3600),
             "resolution is unsupported")
    return value


def _row_clocks(row, as_of):
    start, end = (_instant(row[key], whole=True) for key in ("from", "to"))
    _require(start <= end, "window is reversed")
    received, reference_received, reference_recorded = (
        _instant(row[key]) for key in ("received_at", "reference_received_at", "reference_recorded_at"))
    _require(reference_received <= reference_recorded <= as_of,
             "reference receipt and recording clocks differ")
    _require(reference_received <= received <= as_of,
             "response receipt clock is unavailable")
    return start, end


def _capture_row(row, as_of):
    _closed(row, _ROW_FIELDS)
    _require(all(type(value) is str for value in row.values()), "row fields must be strings")
    for field in ("raw", "reference_raw"):
        _address(row[field], field)
    if row["mapping"] != "EMPTY":
        _address(row["mapping"], "mapping")
    return _row_clocks(row, as_of)


def _capture_rows(rows, start, end, as_of):
    _require(type(rows) is list and 1 <= len(rows) <= MAX_CAPTURE_WINDOWS,
             "requires 1..2366 capture windows")
    previous_end = None
    for row in rows:
        window_start, window_end = _capture_row(row, as_of)
        if previous_end is not None:
            _require(window_start - previous_end == dt.timedelta(seconds=1),
                     "windows must be consecutive without gaps or overlap")
        previous_end = window_end
    first_start, first_end = (_instant(rows[0][key], whole=True) for key in ("from", "to"))
    _require(first_start <= start <= first_end, "retained first window does not cover requested start")
    _require(previous_end == end, "last window does not match requested end")
    return rows


def parse_capture_catalog(raw: RawObservationSegment, *, owner_id: str,
                          product_address: str, contract_address: str,
                          as_of: dt.datetime) -> CaptureCatalog:
    """Read a scoped catalog; dependencies remain unverified until bundle loading."""
    scope = _scope(owner_id, product_address, contract_address)
    cutoff = _instant(as_of)
    document = _raw_document(raw, scope, cutoff)
    binding = _clock_binding(document["clock_binding"])
    _address(document["selection_address"], "selection")
    _require(type(document["requested_start"]) is str and type(document["requested_end"]) is str,
             "request clocks must be strings")
    start, end = (_instant(document[key], whole=True) for key in ("requested_start", "requested_end"))
    _require(start <= end, "request range is reversed")
    rows = _capture_rows(document["rows"], start, end, cutoff)
    return CaptureCatalog(*scope, binding, document["selection_address"], start, end, tuple(rows))


def prepare_capture_catalog(*, owner_id: str, product_address: str, contract_address: str,
                            clock_binding, selection_address: str,
                            requested_start: dt.datetime, requested_end: dt.datetime,
                            rows, recorded_at: dt.datetime) -> RawObservationSegment:
    """Encode detached canonical bytes; this does not persist or admit sources."""
    _require(type(rows) in (list, tuple) and 1 <= len(rows) <= MAX_CAPTURE_WINDOWS,
             "requires 1..2366 capture windows")
    document = {"schema": SCHEMA, "owner_id": owner_id, "product_address": product_address,
                "contract_address": contract_address, "clock_binding": dict(clock_binding),
                "selection_address": selection_address,
                "requested_start": _instant(requested_start, whole=True).isoformat(),
                "requested_end": _instant(requested_end, whole=True).isoformat(),
                "rows": [dict(row) for row in rows]}
    raw = RawObservationSegment(owner_id, product_address, contract_address, "application/json", SCHEMA,
                                canonical_json(document).encode("utf-8"), _instant(recorded_at))
    parse_capture_catalog(raw, owner_id=owner_id, product_address=product_address,
                          contract_address=contract_address, as_of=recorded_at)
    return raw
