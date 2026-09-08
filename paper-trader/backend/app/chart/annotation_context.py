"""Owner-scoped market context over verified saved research evidence.

The projection copies already verified canonical candles. It performs no provider
I/O, normalization, sorting, repair, resampling, interpolation, or strategy work.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Mapping

from app.core import research_read
from app.db.session import SessionLocal
from app.ir.hashing import canonical_json, content_address
from research.data.canonical_dataset import CanonicalDatasetRefused, load_canonical_datasets

MARKET_CONTEXT_SCHEMA = "strategy-os-market-context/1"
MARKET_CONTEXT_IDENTITY_SCHEMA = "market-context-identity/1"
MAX_PAGE_BARS = 500
MAX_CONTEXT_BARS = 2_000
MAX_RESPONSE_BYTES = 1 * 1024 * 1024
UTC = dt.timezone.utc


class MarketContextUnavailable(ValueError):
    """A source is missing, private, legacy, corrupt, or unsupported."""

    code = "MARKET_CONTEXT_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class MarketContextIdentity:
    owner_id: str
    terminal_evidence_address: str
    graph: Mapping[str, Any]
    dataset_manifest_address: str
    canonical_instrument_address: str
    instrument_label: str
    timeframe_seconds: int
    source_as_of: dt.datetime

    @property
    def market_context_address(self) -> str:
        return content_address({
            "schema": MARKET_CONTEXT_IDENTITY_SCHEMA,
            "owner_id": self.owner_id,
            "dataset_manifest_address": self.dataset_manifest_address,
            "canonical_instrument_address": self.canonical_instrument_address,
            "timeframe_seconds": self.timeframe_seconds,
            "source_as_of": _time_text(self.source_as_of),
        })


def _fail() -> None:
    raise MarketContextUnavailable("market context is unavailable")


def _address(value: object) -> str:
    if (type(value) is not str or len(value) != 71 or not value.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value[7:])):
        _fail()
    return value


def _utc(value: object) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        _fail()
    if (not isinstance(parsed, dt.datetime) or parsed.tzinfo is None
            or parsed.utcoffset() != dt.timedelta(0) or parsed.microsecond):
        _fail()
    return parsed.astimezone(UTC)


def _time_text(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _source_binding(run: Mapping[str, Any], owner_id: str) -> MarketContextIdentity:
    evidence = run.get("evidence")
    if run.get("evidence_state") != "verified" or not isinstance(evidence, Mapping):
        _fail()
    provenance = evidence.get("provenance")
    graph_provenance = provenance.get("graph_provenance") if isinstance(provenance, Mapping) else None
    canonical = graph_provenance.get("canonical_dataset_bindings") if isinstance(graph_provenance, Mapping) else None
    bindings = canonical.get("bindings") if isinstance(canonical, Mapping) else None
    if not isinstance(bindings, Mapping) or len(bindings) != 1:
        _fail()
    binding = next(iter(bindings.values()))
    if not isinstance(binding, Mapping):
        _fail()
    time = binding.get("time_interpretation")
    instrument = binding.get("instrument")
    if not isinstance(time, Mapping) or not isinstance(instrument, Mapping):
        _fail()
    seconds = time.get("resolution_seconds")
    if type(seconds) is not int or seconds <= 0:
        _fail()
    label_parts = (instrument.get("venue_code"), instrument.get("asset_class"),
                   instrument.get("contract_kind"))
    label = " · ".join(str(part) for part in label_parts if isinstance(part, str) and part)
    if type(label) is not str or not 1 <= len(label) <= 256:
        _fail()
    from app.ir.hashing import content_address as address_document
    return MarketContextIdentity(
        owner_id=owner_id,
        terminal_evidence_address=address_document(dict(evidence)),
        graph=dict(run["graph"]),
        dataset_manifest_address=_address(binding.get("manifest_address")),
        canonical_instrument_address=_address(binding.get("instrument_address")),
        instrument_label=label,
        timeframe_seconds=seconds,
        source_as_of=_utc(binding.get("as_of")),
    )


def resolve_market_context(project_id: str, run_id: int, *, owner_id: str) -> MarketContextIdentity:
    try:
        run = research_read.get_graph_run(project_id, run_id, owner_id=owner_id)
    except research_read.StoredEvidenceCorrupt:
        _fail()
    if run is None:
        _fail()
    return _source_binding(run, owner_id)


def build_market_context(
    project_id: str, run_id: int, *, owner_id: str, after: int = 0,
    limit: int = 500, replay_at: dt.datetime | None = None,
) -> dict[str, Any]:
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= MAX_PAGE_BARS:
        _fail()
    identity = resolve_market_context(project_id, run_id, owner_id=owner_id)
    replay = identity.source_as_of if replay_at is None else _utc(replay_at)
    if replay > identity.source_as_of:
        _fail()
    try:
        with research_read._research_session() as research_session, SessionLocal() as execution_session:
            if research_session is None:
                _fail()
            loaded = load_canonical_datasets(
                research_session, execution_session=execution_session, owner_id=owner_id,
                selections=(SimpleNamespace(
                    manifest_address=identity.dataset_manifest_address,
                    as_of=identity.source_as_of,
                ),), now=identity.source_as_of,
            )
    except (CanonicalDatasetRefused, ValueError, TypeError, KeyError):
        _fail()
    if len(loaded) != 1:
        _fail()
    instrument, dataset = loaded[0]
    binding = dataset.binding
    if (dataset.bar_count > MAX_CONTEXT_BARS
            or binding.get("manifest_address") != identity.dataset_manifest_address
            or binding.get("instrument_address") != identity.canonical_instrument_address
            or binding.get("time_interpretation", {}).get("resolution_seconds") != identity.timeframe_seconds
            or dataset.instrument_key != instrument.key):
        _fail()
    visible = []
    for cursor, candle in enumerate(dataset.candles, start=1):
        completed = candle.ts + dt.timedelta(seconds=identity.timeframe_seconds)
        if completed <= replay <= identity.source_as_of:
            values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
            if (not all(type(value) is float and math.isfinite(value) for value in values)
                    or min(values[:4]) <= 0 or candle.low > min(candle.open, candle.close)
                    or max(candle.open, candle.close) > candle.high or candle.volume < 0):
                _fail()
            visible.append({
                "cursor": cursor,
                "event_time": _time_text(candle.ts),
                "completed_at": _time_text(completed),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            })
    page = [bar for bar in visible if bar["cursor"] > after][:limit]
    next_cursor = page[-1]["cursor"] if page and page[-1]["cursor"] < visible[-1]["cursor"] else None
    closed = {
        "schema": MARKET_CONTEXT_SCHEMA,
        "state": "AVAILABLE" if visible else "EMPTY",
        "market_context_address": identity.market_context_address,
        "source": {"kind": "VERIFIED_SAVED_RUN", "address": identity.terminal_evidence_address},
        "graph": dict(identity.graph),
        "dataset_manifest_address": identity.dataset_manifest_address,
        "canonical_instrument_address": identity.canonical_instrument_address,
        "instrument_label": identity.instrument_label,
        "timeframe_seconds": identity.timeframe_seconds,
        "source_as_of": _time_text(identity.source_as_of),
        "replay_at": _time_text(replay),
        "bars": page,
    }
    result = {**closed, "projection_address": content_address(closed),
              "page": {"after": after, "limit": limit, "next_cursor": next_cursor,
                       "visible_count": len(visible)}}
    if len(canonical_json(result).encode()) > MAX_RESPONSE_BYTES:
        _fail()
    return result


__all__ = ["MARKET_CONTEXT_SCHEMA", "MarketContextIdentity", "MarketContextUnavailable",
           "build_market_context", "resolve_market_context"]
