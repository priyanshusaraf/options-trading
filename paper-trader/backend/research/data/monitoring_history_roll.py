"""Reopen and roll bounded monitoring history without changing source receipts."""
from __future__ import annotations

from dataclasses import replace
import datetime as dt
import json
from types import SimpleNamespace

from app.market_data import dataset_authority as authority
from app.market_data.observations import load_raw_segment
from app.market_truth.dated_sessions import expected_bars
from research.data import historical_capture as history
from research.data import provider_capture as capture
from research.data import provider_history_bundle as bundle
from research.data.canonical_dataset import MAX_ROWS, load_canonical_datasets
from research.data.provider_history_fetch import CurrentReferenceCapture, HistoricalResponseCapture, HistoricalFetchResult
from research.data.provider_history_windows import CLOCK_PRODUCER


def _captures(session, windows, raws, interval, exchange):
    result = []
    for row, raw in zip(windows.rows, raws, strict=True):
        reference = load_raw_segment(session, row['reference_raw'])
        current = CurrentReferenceCapture(reference.payload, dt.datetime.fromisoformat(row['reference_received_at']),
            reference.recorded_at, exchange)
        result.append(HistoricalResponseCapture(raw.payload, dt.datetime.fromisoformat(row['received_at']),
            raw.recorded_at, dt.datetime.fromisoformat(row['from']), dt.datetime.fromisoformat(row['to']),
            interval, len(json.loads(raw.payload)['data']['candles']), current))
    return tuple(result)


def load_retained_monitoring_history(execution_session, research_session, *, owner_id, project_id,
                                     manifest_address, as_of):
    """Fully replay the owner/project input before exposing its retained requests."""
    _, data = load_canonical_datasets(research_session, execution_session=execution_session, owner_id=owner_id,
        selections=[SimpleNamespace(manifest_address=manifest_address, as_of=as_of)], now=as_of)[0]
    manifest = data._verified_authority.manifest
    history._require(manifest.purpose == history.PURPOSE + project_id)
    transform = authority.load_normalization_transform(execution_session, manifest.normalization_transform_addresses[0])
    history._require(dict(transform.parameters).get('kind') == CLOCK_PRODUCER)
    sources, raws, windows = bundle._retained_sources(execution_session, transform.parameters, owner_id, as_of)
    receipt = json.loads(sources[0].receipt.payload)
    connection = capture._connection(execution_session, owner_id, project_id, receipt['connection_id'])
    definition = load_raw_segment(execution_session, dict(transform.parameters)['definition'])
    captures = _captures(execution_session, windows, raws, receipt['request']['interval'], receipt['selection']['exchange'])
    return HistoricalFetchResult(owner_id, project_id, windows.selection_address, connection.broker_account_id,
        connection.id, sources[0].context.canonical_instrument, definition.payload,
        windows.requested_start, windows.requested_end, captures[-1].current_reference, captures, sources)


def _append_identity(previous, acquired, maximum_bars):
    history._require(type(maximum_bars) is int and 1 <= maximum_bars <= MAX_ROWS)
    fields = ('owner_id', 'project_id', 'selection_address', 'data_account_id', 'connection_id',
              'instrument', 'definition_evidence')
    history._require(all(getattr(previous, key) == getattr(acquired, key) for key in fields))
    history._require(previous.requested_end + dt.timedelta(seconds=1) == acquired.requested_start)
    sources = previous.sources + acquired.sources
    history._require(bool(sources) and all(bundle._same_source(sources[0], source)
        and source.clock_binding == sources[0].clock_binding for source in sources))
    clock = sources[0].clock_binding
    history._require(clock is not None)
    return sources, clock


def append_monitoring_history(previous, acquired, *, maximum_bars=MAX_ROWS):
    """Keep the newest completed prefix; publication verifies every original fact."""
    sources, clock = _append_identity(previous, acquired, maximum_bars)
    captures = previous.captures + acquired.captures
    bars = expected_bars(clock.calendar, requested_start=previous.requested_start,
        requested_end=acquired.requested_end, resolution_seconds=clock.resolution_seconds,
        cutoff_at=max(item.received_at for item in captures))
    history._require(bool(bars))
    start = bars[max(0, len(bars)-maximum_bars)][0]
    kept = tuple(item for item in captures if item.requested_end >= start)
    raw_payloads = {item.payload for item in kept}
    retained = tuple(source for source in sources if source.historical_response.payload in raw_payloads)
    bundle._source_identity(retained)
    return replace(acquired, requested_start=start, captures=kept, sources=retained)
