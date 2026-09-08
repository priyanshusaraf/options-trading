"""Retained request windows for bounded intraday monitoring bundles."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json

from app.market_data import kite_historical_attribution as attribution
from app.market_data.observations import RawObservationSegment, load_raw_segment
from research.data import historical_capture as history

CLOCK_PRODUCER = "historical-kite-bundle/2"


@dataclass(frozen=True, slots=True)
class BundleWindows:
    rows: tuple
    requested_start: dt.datetime
    requested_end: dt.datetime
    selection_address: str
    catalog: RawObservationSegment | None = None
    clock_binding: object | None = None


def _reference(context, captured):
    return RawObservationSegment(context.owner_id, context.provider_product_address,
        context.provider_contract_address, "text/csv", attribution.REFERENCE_SCHEMA,
        captured.payload, captured.recorded_at)


def prepare_windows(fetch, raws, as_of):
    from app.market_data.retained_history_windows import prepare_capture_catalog
    context, clock = fetch.sources[0].context, fetch.sources[0].clock_binding
    history._require(clock is not None)
    mappings = {source.historical_response.address: source.mapping.address for source in fetch.sources}
    history._require(len(mappings) == len(fetch.sources))
    rows, references = [], []
    for captured, raw in zip(fetch.captures, raws, strict=True):
        reference = getattr(captured, "current_reference", None) or fetch.current_reference
        retained = _reference(context, reference)
        references.append(retained)
        rows.append({"raw": raw.address, "received_at": captured.received_at.isoformat(),
            "from": captured.requested_start.isoformat(), "to": captured.requested_end.isoformat(),
            "mapping": mappings.get(raw.address, "EMPTY"), "reference_raw": retained.address,
            "reference_received_at": reference.received_at.isoformat(),
            "reference_recorded_at": reference.recorded_at.isoformat()})
    catalog = prepare_capture_catalog(owner_id=fetch.owner_id, product_address=context.provider_product_address,
        contract_address=context.provider_contract_address, clock_binding=clock.receipt_binding(),
        selection_address=fetch.selection_address, requested_start=fetch.requested_start,
        requested_end=fetch.requested_end, rows=rows, recorded_at=as_of)
    return catalog, tuple(references)


def load_windows(session, parameters, owner_id, as_of):
    from app.market_data.retained_history_windows import parse_capture_catalog
    params = dict(parameters)
    history._require(len(params) == len(parameters) and set(params) == {"kind", "catalog", "definition"}
                     and params["kind"] == CLOCK_PRODUCER)
    raw = load_raw_segment(session, params["catalog"])
    catalog = parse_capture_catalog(raw, owner_id=owner_id, product_address=raw.product_address,
        contract_address=raw.contract_address, as_of=as_of)
    return BundleWindows(catalog.rows, catalog.requested_start, catalog.requested_end,
                         catalog.selection_address, raw, catalog.clock_binding)


def verify_reference(session, row, source, reference, as_of):
    from research.data.provider_history_fetch import verify_captured_reference
    context = source.context
    raw = load_raw_segment(session, row["reference_raw"])
    history._require((raw.owner_id, raw.product_address, raw.contract_address, raw.raw_schema, raw.media_type)
        == (context.owner_id, context.provider_product_address, context.provider_contract_address,
            attribution.REFERENCE_SCHEMA, "text/csv"))
    received, recorded = (attribution._instant(row[key])
        for key in ("reference_received_at", "reference_recorded_at"))
    history._require(received <= recorded == raw.recorded_at <= as_of)
    verify_captured_reference(raw.payload, reference)
    if row["mapping"] != "EMPTY":
        original = json.loads(source.receipt.payload)["current_reference"]
        history._require(raw == source.current_reference
            and received == attribution._instant(original["received_at"]))
    return received


def artifact_addresses(raws, definition_address, catalog):
    if catalog is None:
        return tuple(sorted([definition_address, *(raw.address for raw in raws)]))
    return tuple(sorted((definition_address, catalog.address)))


def selected_observations(observations, windows):
    return tuple(item for item in observations
        if windows.requested_start <= item.event_time <= windows.requested_end)
