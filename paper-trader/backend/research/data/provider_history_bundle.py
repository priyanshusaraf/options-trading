"""One canonical daily input from separately retained provider request windows.

Provider responses and acquisition clocks stay unchanged. Only the normalized
index and its shared research policies are derived for the combined range.
The caller owns project admission, source-root registration and both commits.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import replace
from pathlib import Path

from app.db.concurrency import caller_owned_savepoint
from app.ir.hashing import content_address
from app.market_data import dataset_authority as authority
from app.market_data import kite_historical_attribution as attribution
from app.market_data.kite_observations import KiteObservationBatch
from app.market_data.observations import (
    RawObservationSegment, load_raw_segment, persist_raw_segment,
    retain_observation_dependencies,
)
from app.market_truth.identity import load_provider_alias
from research.data import historical_capture as history
from research.data import provider_capture as capture
from research.data import provider_history_authority as producer
from research.data import provider_history_windows as windows_binding
from research.data.canonical_dataset import MAX_ROWS

PRODUCER = "historical-kite-bundle/1"
PRODUCERS = frozenset({PRODUCER, windows_binding.CLOCK_PRODUCER})
DEFINITION_SCHEMA = "strategy-os-cash-definition-evidence/1"
_HEADER = {"kind", "count", "requested_start", "requested_end", "selection_address", "definition"}
_CAPTURE_FIELDS = {"raw", "received_at", "from", "to", "mapping"}


def _same_source(left, right):
    names = ("owner_id", "provider_entity_address", "provider_product_address",
             "provider_contract_address", "canonical_instrument")
    return all(getattr(left.context, name) == getattr(right.context, name) for name in names)


def _source_identity(sources):
    history._require(type(sources) is tuple and 0 < len(sources) <= MAX_ROWS)
    history._require(all(type(source) is attribution.HistoricalAttribution for source in sources))
    first = sources[0]
    history._require(all(_same_source(first, source) and source.clock_binding == first.clock_binding
                         for source in sources))
    if first.clock_binding is None:
        history._require(len(sources) <= 64 and all(source.current_reference == first.current_reference
                                                 for source in sources))


def _combined_bounds(bounds, maximum_rows=MAX_ROWS):
    history._require(all(left[1] <= right[0] for left, right in zip(bounds, bounds[1:])),
        "HISTORICAL_BUNDLE_OVERLAP",
        "These responses overlap or are out of order. Use one saved data version for this range.")
    count = sum(bound[2] for bound in bounds)
    history._require(count <= maximum_rows, "HISTORICAL_BUNDLE_ROW_LIMIT",
        f"This backtest input supports at most {MAX_ROWS:,} bars. Choose a shorter range; this is an application limit, not provider retention.")
    combined = (bounds[0][0], bounds[-1][1], count, max(bound[3] for bound in bounds))
    return combined, tuple(sorted(set((combined, *bounds))))


def _source_inputs(sources):
    _source_identity(sources)
    values = tuple(producer._intake(source) for source in sources)
    history._require(all(value["connection_id"] == values[0]["connection_id"] for value in values))
    dated = sources[0].clock_binding is not None
    combined, ranges = _combined_bounds(tuple(producer._measured_range(value) for value in values),
                                        MAX_ROWS * 2 if dated else MAX_ROWS)
    if dated:
        ranges = (combined,)
    return values, combined, ranges


def _raw_response(context, item):
    return RawObservationSegment(context.owner_id, context.provider_product_address,
        context.provider_contract_address, "application/json", attribution.RESPONSE_SCHEMA,
        item.payload, item.recorded_at)


def _window_order(windows, start, end):
    history._require(windows and windows[0][0] == start and windows[-1][1] == end)
    history._require(all(left <= right for left, right in windows))
    history._require(all(left[1] + dt.timedelta(seconds=1) == right[0]
        for left, right in zip(windows, windows[1:])),
        "HISTORICAL_BUNDLE_REQUEST_GAP",
        "The retained requests do not cover the chosen range. Fetch the full range again.")


def _parameters(fetch, raws, definition):
    mappings = {source.historical_response.address: source.mapping.address for source in fetch.sources}
    history._require(len(mappings) == len(fetch.sources))
    params = {"kind": PRODUCER, "count": str(len(raws)),
        "requested_start": fetch.requested_start.isoformat(),
        "requested_end": fetch.requested_end.isoformat(), "selection_address": fetch.selection_address,
        "definition": definition.address}
    for index, (item, raw) in enumerate(zip(fetch.captures, raws, strict=True)):
        values = {"raw": raw.address, "received_at": item.received_at.isoformat(),
            "from": item.requested_start.isoformat(), "to": item.requested_end.isoformat(),
            "mapping": mappings.get(raw.address, "EMPTY")}
        params.update({f"capture.{index:03}.{key}": value for key, value in values.items()})
    return tuple(sorted(params.items()))


def _parameter_rows(parameters):
    params = dict(parameters)
    history._require(len(params) == len(parameters) and params.get("kind") == PRODUCER)
    count = int(params["count"])
    history._require(str(count) == params["count"] and 0 < count <= 64)
    keys = _HEADER | {f"capture.{index:03}.{key}"
        for index in range(count) for key in _CAPTURE_FIELDS}
    history._require(set(params) == keys)
    rows = tuple({key: params[f"capture.{index:03}.{key}"] for key in _CAPTURE_FIELDS}
        for index in range(count))
    start, end = (attribution._instant(params[key], whole=True)
        for key in ("requested_start", "requested_end"))
    windows = tuple((attribution._instant(row["from"], whole=True),
        attribution._instant(row["to"], whole=True)) for row in rows)
    _window_order(windows, start, end)
    return rows, start, end


def _empty_response(raw, row, first_source, as_of, reference_time=None):
    context = first_source.context
    history._require((raw.owner_id, raw.product_address, raw.contract_address,
        raw.raw_schema, raw.media_type) == (context.owner_id, context.provider_product_address,
        context.provider_contract_address, attribution.RESPONSE_SCHEMA, "application/json"))
    document = attribution._closed(attribution._json(raw.payload), ("status", "data"))
    history._require(document["status"] == "success"
        and attribution._closed(document["data"], ("candles",))["candles"] == [])
    received = attribution._instant(row["received_at"])
    # The current reference precedes every historical request in this fetch.
    if reference_time is None:
        reference_time = dt.datetime.fromisoformat(json.loads(first_source.receipt.payload)
            ["current_reference"]["received_at"])
    history._require(reference_time <= received <= raw.recorded_at <= as_of)
    if first_source.clock_binding is not None:
        from app.market_truth.dated_sessions import expected_bars
        expected = expected_bars(first_source.clock_binding.calendar,
            requested_start=attribution._instant(row["from"]), requested_end=attribution._instant(row["to"]),
            resolution_seconds=first_source.clock_binding.resolution_seconds, cutoff_at=received)
        history._require(not expected, "HISTORICAL_BUNDLE_MISSING_SESSION_BARS",
                         "An empty response omitted completed bars in a declared open session.")


def _selection_binding(session, selection_address, source):
    from app.core.provider_selections import load_provider_selection, ProviderSelectionNotFound
    from research.data.provider_history_fetch import verify_captured_reference
    try:
        selected = load_provider_selection(session, owner_id=source.context.owner_id,
            selection_address=selection_address)["selection"]
    except ProviderSelectionNotFound:
        raise history.HistoricalCaptureRefused() from None
    reference = selected["reference"]
    receipt = json.loads(source.receipt.payload)
    history._require(selected["provider"] == "ZERODHA"
        and str(reference["token"]) == source.mapping.provider_token
        and reference["symbol"] == source.mapping.provider_symbol
        and reference["exchange"] == receipt["selection"]["exchange"])
    history._require(dt.datetime.fromisoformat(selected["observed_at"])
        <= dt.datetime.fromisoformat(receipt["current_reference"]["received_at"]))
    verify_captured_reference(source.current_reference.payload, reference)
    return reference


def _definition_segment(fetch, context, as_of):
    from app.market_truth.cash_reference import source_reference_for_symbol
    receipt = json.loads(fetch.sources[0].receipt.payload)
    reference = source_reference_for_symbol(receipt["selection"]["symbol"], receipt["selection"]["exchange"])
    history._require(reference is not None and reference[0] == fetch.instrument
        and json.loads(fetch.definition_evidence) == reference[1],
        "HISTORICAL_BUNDLE_DEFINITION_UNAVAILABLE",
        "The instrument's sourced definition changed or is unavailable. Review the selection and fetch again.")
    return RawObservationSegment(context.owner_id, context.provider_product_address,
        context.provider_contract_address, "application/json", DEFINITION_SCHEMA, fetch.definition_evidence, as_of)


def _retained_definition(session, address, source, reference, as_of):
    from app.market_truth.cash_reference import verify_retained_definition
    raw = load_raw_segment(session, address)
    context = source.context
    history._require((raw.owner_id, raw.product_address, raw.contract_address, raw.raw_schema, raw.media_type)
        == (context.owner_id, context.provider_product_address, context.provider_contract_address, DEFINITION_SCHEMA, "application/json")
        and raw.recorded_at <= as_of)
    verify_retained_definition(raw.payload, context.canonical_instrument,
        symbol=reference["symbol"], exchange=reference["exchange"], recorded_at=raw.recorded_at)
    return raw


def _bundle_windows(session, parameters, owner_id, as_of):
    params = dict(parameters)
    if params.get("kind") == windows_binding.CLOCK_PRODUCER:
        return windows_binding.load_windows(session, parameters, owner_id, as_of)
    rows, start, end = _parameter_rows(parameters)
    return windows_binding.BundleWindows(rows, start, end, params["selection_address"])


def _retained_source(session, raw, row, as_of):
    source = attribution.load_historical_attribution(session, load_provider_alias(session, row["mapping"]))
    values = producer._intake(source)
    history._require(source.historical_response == raw
        and values["captured_at"] == attribution._instant(row["received_at"])
        and values["requested_start"] == attribution._instant(row["from"], whole=True)
        and values["requested_end"] == attribution._instant(row["to"], whole=True)
        and values["as_of"] <= as_of)
    return source


def _window_references(session, windows, sources, as_of):
    references = {}
    for source in sources:
        reference = _selection_binding(session, windows.selection_address, source)
        references[source.mapping.address] = (source, reference)
    if windows.catalog is None:
        return {}
    clock = sources[0].clock_binding
    history._require(clock is not None and clock.receipt_binding() == dict(windows.clock_binding))
    first = references[sources[0].mapping.address]
    return {row["raw"]: windows_binding.verify_reference(session, row,
        *references.get(row["mapping"], first), as_of) for row in windows.rows}


def _retained_sources(session, parameters, owner_id, as_of):
    windows = _bundle_windows(session, parameters, owner_id, as_of)
    sources, raws, empty = [], [], []
    for row in windows.rows:
        raw = load_raw_segment(session, row["raw"])
        raws.append(raw)
        if row["mapping"] == "EMPTY":
            empty.append((raw, row))
            continue
        sources.append(_retained_source(session, raw, row, as_of))
    _source_inputs(tuple(sources))
    history._require(sources[0].context.owner_id == owner_id)
    params = dict(parameters)
    reference = _selection_binding(session, windows.selection_address, sources[0])
    _retained_definition(session, params["definition"], sources[0], reference, as_of)
    reference_times = _window_references(session, windows, sources, as_of)
    for raw, row in empty:
        _empty_response(raw, row, sources[0], as_of, reference_times.get(raw.address))
        _, _, contract = capture.load_provider_identity(session, raw.contract_address)
        attribution._grant(contract, attribution._instant(row["received_at"]))
    history._require(len({raw.address for raw in raws}) == len(raws))
    return tuple(sources), tuple(raws), windows


def _shared_facts(session, sources, values, bounds, coverage_bounds, definition, as_of):
    shared = {**values[0], "as_of": as_of}
    conformance, profile = producer._profile(sources[0], shared, bounds,
        sources=sources, coverage_bounds=coverage_bounds)
    algorithm, truth, policies = producer._policy_facts(sources[0], shared, bounds,
        sources=sources, additional_evidence=(definition.address,))
    producer._persist_policy_profile(session, conformance, profile, algorithm, truth, policies)
    return profile, truth, policies


def _normalization(sources, parameters, recorded_at):
    from app.market_data import kite_observations, dated_session_clock, retained_history_windows
    from app.market_truth import dated_sessions
    from research.data import dated_session_binding
    context, raw = sources[0].context, sources[0].historical_response
    implementation = Path(__file__).read_text() + ''.join(Path(module.__file__).read_text() for module in (
        capture, history, producer, windows_binding, attribution, kite_observations,
        dated_session_clock, retained_history_windows, dated_sessions, dated_session_binding))
    algorithm = authority.DeterministicAlgorithm(context.owner_id, dict(parameters)["kind"], "1",
        content_address({"source": implementation}),
        (content_address({"input": capture._NORMALIZATION_VECTOR[0],
            "expected": capture._NORMALIZATION_VECTOR[1]}),), recorded_at)
    schema = authority.RawSchema(context.owner_id, context.provider_product_address,
        context.provider_contract_address, "kite-historical-candle/3",
        tuple(sorted((field.lower(), "number") for field in capture.FIELDS)), raw.address, recorded_at)
    transform = authority.NormalizationTransform(context.owner_id, (schema.address,),
        "strategy-bar/1", parameters, algorithm.address, recorded_at)
    return algorithm, schema, transform


def _source_facts(session, source, values, profile, policies, as_of, bundle_maximum_age=None):
    return history._facts(session, owner_id=source.context.owner_id,
        connection_id=values["connection_id"], raw_response=values["raw_response"], context=source.context,
        capability_profile_address=profile.capability_profile_address,
        policy_addresses=tuple(policy.address for policy in policies),
        captured_at=values["captured_at"], recorded_at=values["recorded_at"], as_of=as_of,
        requested_start=values["requested_start"], requested_end=values["requested_end"],
        bundle_maximum_age=bundle_maximum_age)


def _verify_selected_clock(batch, sources, windows):
    history._require(0 < len(batch.observations) <= MAX_ROWS * len(capture.FIELDS),
        "HISTORICAL_BUNDLE_ROW_LIMIT", "The retained prefix must contain a bounded completed history.")
    if sources[0].clock_binding is None:
        return
    from app.market_truth.dated_sessions import expected_bars
    clock = sources[0].clock_binding
    expected = expected_bars(clock.calendar, requested_start=windows.requested_start,
        requested_end=windows.requested_end, resolution_seconds=clock.resolution_seconds,
        cutoff_at=max(item.available_at for item in batch.observations))
    actual = tuple((item.event_time, item.completed_at) for item in batch.observations[::len(capture.FIELDS)])
    history._require(actual == expected, "HISTORICAL_BUNDLE_MISSING_SESSION_BARS",
        "The retained windows do not contain every declared completed bar in this prefix.")


def _selected_batch(batches, windows):
    observations = windows_binding.selected_observations(
        (observation for batch in batches for observation in batch.observations), windows)
    addresses = {item.raw_segment_address for item in observations}
    return KiteObservationBatch(tuple(raw for batch in batches for raw in batch.raw_segments
                                     if raw.address in addresses), observations, ())


def _combined_observations(session, sources, values, profile, policies, algorithm, transform, as_of, windows):
    batches, normalized = [], []
    # The shared profile states the measured worst age of this whole bundle.
    # Each original response still keeps and validates its own acquisition clock.
    maximum_age = max(producer._measured_range(value)[3] for value in values) if windows.catalog is not None else None
    for source, value in zip(sources, values, strict=True):
        context, _, _, truth, document, batch, _ = _source_facts(
            session, source, value, profile, policies, as_of, maximum_age)
        batches.append(batch)
        normalized.extend(replace(item, recorded_at=as_of) for item in
            capture._normalized(context, policies, truth, document, batch, algorithm, transform))
    combined = _selected_batch(batches, windows)
    _verify_selected_clock(combined, sources, windows)
    return combined, windows_binding.selected_observations(normalized, windows)


def _dataset(context, project_id, policies, profile, truth, batch, normalized, schema, transform,
             algorithms, creation, recorded_at):
    manifest, segments = capture._dataset(context, project_id, policies, profile, truth,
        batch, normalized, schema, transform, algorithms, creation, purpose=history.PURPOSE)
    segment, payload = next(iter(segments.values()))
    start = min(item.available_at for item in batch.observations).isoformat()
    end = (max(item.available_at for item in batch.observations) + dt.timedelta(seconds=1)).isoformat()
    segment = replace(segment, availability_start=start, availability_end=end)
    manifest = capture.DatasetManifest(**{**manifest.fact(),
        "segment_addresses": (segment.segment_address,), "availability_start": start,
        "availability_end": end, "created_at": recorded_at.isoformat(),
        "recorded_at": recorded_at.isoformat()})
    return manifest, {segment.segment_address: (segment, payload)}


def _fetch_inputs(fetch):
    sources = fetch.sources
    values, bounds, coverage_bounds = _source_inputs(sources)
    context = sources[0].context
    history._require(fetch.owner_id == context.owner_id and fetch.instrument == context.canonical_instrument
        and all(value["connection_id"] == fetch.connection_id for value in values))
    raws = tuple(_raw_response(context, item) for item in fetch.captures)
    as_of = max(*(value["as_of"] for value in values), *(item.recorded_at for item in raws))
    definition = _definition_segment(fetch, context, as_of)
    catalog, references = None, ()
    if sources[0].clock_binding is not None:
        catalog, references = windows_binding.prepare_windows(fetch, raws, as_of)
        parameters = tuple(sorted({"kind": windows_binding.CLOCK_PRODUCER,
            "catalog": catalog.address, "definition": definition.address}.items()))
    else:
        parameters = _parameters(fetch, raws, definition)
    return values, bounds, coverage_bounds, raws, definition, parameters, as_of, catalog, references


@retain_observation_dependencies
def publish_historical_bundle(execution_session, research_session, fetch):
    """Publish one fetch atomically within caller-owned transactions; never commit."""
    values, bounds, coverage_bounds, raws, definition, parameters, as_of, catalog, references = _fetch_inputs(fetch)
    sources, context = fetch.sources, fetch.sources[0].context
    with caller_owned_savepoint(execution_session, scope="historical-data-bundle"):
        connection = capture._connection(execution_session, fetch.owner_id, fetch.project_id,
            fetch.connection_id, lock=True)
        capture._connection_clock(connection, min(item.received_at for item in fetch.captures), as_of)
        for source in sources:
            attribution.persist_historical_attribution(execution_session, source)
        for raw in (*raws, definition, *references, *((catalog,) if catalog is not None else ())):
            persist_raw_segment(execution_session, raw)
        retained, _, windows = _retained_sources(execution_session, parameters, fetch.owner_id, as_of)
        history._require(retained == sources)
        profile, truth, policies = _shared_facts(execution_session, sources, values, bounds,
            coverage_bounds, definition, as_of)
        algorithm, schema, transform = _normalization(sources, parameters, as_of)
        batch, normalized = _combined_observations(execution_session, sources, values, profile,
            policies, algorithm, transform, as_of, windows)
        algorithms = capture._algorithms(execution_session, fetch.owner_id, policies, algorithm, as_of)
        creation = authority.DatasetCreationEvidence(fetch.owner_id, dict(parameters)["kind"],
            tuple(sorted(item.address for item in (*batch.observations, *normalized))),
            windows_binding.artifact_addresses(raws, definition.address, catalog), algorithm.address, as_of)
        manifest, segments = _dataset(context, fetch.project_id, policies, profile, truth, batch,
            normalized, schema, transform, algorithms, creation, as_of)
        return capture._persist_capture(execution_session, research_session, raws[0], batch,
            normalized, algorithm, schema, transform, creation, manifest, segments, as_of)


def _match_candles(candles, facts, windows):
    observations = windows_binding.selected_observations((item for fact in facts for item in fact[5].observations), windows)
    rows = tuple(row for fact in facts for row in fact[4]["data"]["candles"]
        if windows.requested_start <= attribution._row_time(row[0]) <= windows.requested_end)
    history._require(len(candles) == len(rows))
    for candle, row, source in zip(candles, rows, observations[::len(capture.FIELDS)], strict=True):
        history._require(candle.ts == source.event_time
            and tuple(getattr(candle, field.lower()) for field in capture.FIELDS) == capture._numeric_values(row))
    return observations


def _bundle_matches(manifest, deps, candles, sources, raws, facts, transform, windows):
    observations = _match_candles(candles, facts, windows)
    schema = deps[manifest.raw_schema_addresses[0]]
    creation = deps[manifest.creation_evidence_addresses[0]]
    history._require(manifest.provider_observation_addresses == tuple(sorted(item.address for item in observations))
        and schema.evidence_address == sources[0].historical_response.address
        and creation.producer == dict(transform.parameters)["kind"]
        and creation.artifact_addresses == windows_binding.artifact_addresses(raws,
            dict(transform.parameters)["definition"], windows.catalog)
        and manifest.created_at == manifest.recorded_at == transform.recorded_at.isoformat())


def load_historical_bundle_binding(session, manifest, deps, candles, as_of):
    """Reconstruct every request, empty response and source clock before replay."""
    history._require(len(manifest.normalization_transform_addresses)
        == len(manifest.raw_schema_addresses) == len(manifest.creation_evidence_addresses) == 1)
    transform = deps[manifest.normalization_transform_addresses[0]]
    history._require(transform.output_schema == "strategy-bar/1"
        and transform.input_raw_schema_addresses == manifest.raw_schema_addresses)
    sources, raws, windows = _retained_sources(session, transform.parameters, manifest.owner_id, as_of)
    values, bounds, _ = _source_inputs(sources)
    policies = capture._policies(session, manifest.owner_id,
        (manifest.alignment_policy_address, manifest.missing_data_policy_address,
         manifest.adjustment_policy_address, manifest.roll_policy_address), as_of, historical=True)
    profile = capture._profile(session, manifest.owner_id, manifest.capability_profile_address,
        sources[0].context, as_of)
    maximum_age = bounds[3] if windows.catalog is not None else None
    facts = tuple(_source_facts(session, source, value, profile, policies, as_of, maximum_age)
        for source, value in zip(sources, values, strict=True))
    _bundle_matches(manifest, deps, candles, sources, raws, facts, transform, windows)
    rows, start, end = windows.rows, windows.requested_start, windows.requested_end
    return {"connection_id": values[0]["connection_id"],
        "provider_selection_address": windows.selection_address,
        "raw_capture_addresses": [raw.address for raw in raws],
        "captured_at": max(attribution._instant(row["received_at"]) for row in rows).isoformat(),
        "requested_start": start.isoformat(), "requested_end": end.isoformat(),
        "returned_start": candles[0].ts.isoformat(), "returned_end": candles[-1].ts.isoformat(),
        "bar_count": len(candles), "request_count": len(rows),
        "empty_request_count": sum(row["mapping"] == "EMPTY" for row in rows),
        "calendar_coverage": "NOT_ASSERTED", "historical_source_availability": "NOT_SUPPLIED"}


def provider_selection_for_manifest(session, manifest):
    """Read an index label association; canonical replay still verifies all rows."""
    from app.market_data.observations import load_provider_observation
    transform = authority.load_normalization_transform(session, manifest.normalization_transform_addresses[0])
    parameters = dict(transform.parameters)
    if parameters.get("kind") not in PRODUCERS:
        return None
    observation = load_provider_observation(session, manifest.provider_observation_addresses[0])
    source = attribution.load_historical_attribution(session, load_provider_alias(session, observation.mapping_address))
    history._require(transform.owner_id == source.context.owner_id == manifest.owner_id
        and manifest.instrument_addresses == (source.context.canonical_instrument.address,))
    windows = _bundle_windows(session, transform.parameters, manifest.owner_id, transform.recorded_at)
    reference = _selection_binding(session, windows.selection_address, source)
    _retained_definition(session, parameters["definition"], source, reference, transform.recorded_at)
    return windows.selection_address
