"""Local content-addressed store for backtest candle datasets.

Why it exists
-------------
Kite's historical endpoint is throttled to 0.40 s per request
(``app/providers/kite.py::_MIN_INTERVAL``).  The 10,000 instruments × 5
intervals tier is 50,000 datasets, so fetching them live has a **5 h 33 m**
floor that no amount of in-process optimisation can move.  Datasets must
therefore be fetched once and kept locally.

What it is NOT
--------------
It is not a cache that shortens a refresh.  Nothing here is read by the sweep.
A normal refresh still costs one provider read per dataset — the provider APIs
expose no revision token, so request metadata cannot prove historical bytes are
unchanged, and claiming otherwise would reintroduce the stale-history defect
fixed by cache schema v8 (design: "Truthful warm modes").  Serving a run from
this store is an *explicit* pinned-run decision, and lives in Task 4.

Storage
-------
The filesystem, never the ledger database.  Layout under ``store_root()``::

    blobs/<aa>/<address>.ptds     zlib-compressed packed bars
    blobs/<aa>/<address>.json     sidecar manifest (source context)
    index.sqlite3                 request key → newest address + fetch time

``<address>`` is exactly ``identity.ordered_dataset_address`` — there is no
second addressing scheme — and ``<aa>`` is its first two hex characters, which
keeps any one directory near 1/256th of the corpus.

The packed record is ``>q5d``: an int64 IST-epoch-microsecond timestamp
followed by open/high/low/close/volume as IEEE-754 binary64.  No rounding, no
text, no locale.

The index uses its own ``sqlite3`` connection to its own file inside the store
directory.  It deliberately does not touch ``app.db.session``: 50,000 datasets
must never become rows in ``paper_trader.db``.

On-disk size (measured 2026-08-09 on this machine)
--------------------------------------------------
=================================  =========  ========================
                                   bytes/bar   10,000 × 5 × 5,000 bars
---------------------------------  ---------  ------------------------
packed, uncompressed                   48.00   12.0 GB
zlib-6, 5,000 random-walk bars         38.32    9.6 GB
zlib-6, 1,288 smooth mock bars         21.85    5.5 GB
manifest sidecar (551 B each)              —   0.03 GB
=================================  =========  ========================

Compression is entirely a function of how much entropy the prices carry: the
mock provider's smooth ramp halves, a random walk barely compresses, because
binary64 mantissas of unrelated prices are near-incompressible.  **Plan on
38 bytes/bar, i.e. ~10 GB for the full 10,000 × 5 tier at 5,000 bars each.**
That is fine on a workstation and is a real constraint on the 25 GB VPS disk —
check free space before enabling the store there, and re-measure against real
Kite bars (2-decimal prices should sit between the two rows above) before
committing to a capacity plan.

Corruption containment
----------------------
A blob is only served when the address recomputed from its decoded bars and its
manifest equals the address in its filename.  Anything else — a flipped byte, a
truncated write, a revised file, a missing sidecar — is refused, never served.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import struct
import threading
import uuid
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from app.backtest.identity import (INSTRUMENT_IDENTITY_FIELDS,
                                   PROVIDER_IDENTITY_FIELDS,
                                   ordered_dataset_address, source_identity)
from app.core.config import get_settings
from app.market_data.numeric import NumericIngressError, market_float


@dataclass(frozen=True)
class LegacyDatasetManifest:
    """Closed, immutable Phase 4 provenance for an answer-bearing dataset."""
    owner_id: str
    dataset_address: str
    provider_dataset_version: str
    instruments: tuple[str, ...]
    fields: tuple[str, ...]
    range_start: str
    range_end: str
    segment_digests: tuple[str, ...]
    instrument_master_address: str
    rulebook_snapshot_address: str
    adjustment_policy_address: str
    roll_policy_address: str
    missing_data_policy_address: str
    alignment_policy_address: str
    resampling_policy_address: str
    timezone: str
    collection_algorithm_version: str
    import_algorithm_version: str
    gaps: tuple[str, ...] = ()
    reconstructed_regions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        scalar_facts = (self.owner_id, self.dataset_address, self.provider_dataset_version,
                        self.range_start, self.range_end, self.timezone,
                        self.collection_algorithm_version, self.import_algorithm_version,
                        self.instrument_master_address, self.rulebook_snapshot_address,
                        self.adjustment_policy_address, self.roll_policy_address,
                        self.missing_data_policy_address, self.alignment_policy_address,
                        self.resampling_policy_address)
        if (any(not isinstance(value, str) or not value.strip() for value in scalar_facts)
                or not self.instruments or not self.fields or not self.segment_digests):
            raise ValueError("dataset manifest identity is incomplete")
        ordered = (self.instruments, self.fields, self.segment_digests,
                   self.gaps, self.reconstructed_regions)
        if any(not isinstance(values, tuple)
               or any(not isinstance(value, str) or not value.strip() for value in values)
               for values in ordered):
            raise ValueError("manifest collection facts are malformed")
        try:
            ZoneInfo(self.timezone)
            start = dt.datetime.fromisoformat(self.range_start.replace("Z", "+00:00"))
            end = dt.datetime.fromisoformat(self.range_end.replace("Z", "+00:00"))
        except (TypeError, ValueError, KeyError):
            raise ValueError("manifest range or timezone is invalid") from None
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("manifest range is not ordered aware time")
        if any(tuple(sorted(values)) != values or len(set(values)) != len(values)
               for values in ordered):
            raise ValueError("manifest facts must be unique canonical order")
        values = tuple(str(value) for value in self.__dict__.values())
        if any("secret" in value.lower() or "token" in value.lower() for value in values):
            raise ValueError("manifest must not contain secrets")
        if not re.fullmatch(r"[0-9a-f]{64}", self.dataset_address):
            raise ValueError("dataset address is malformed")
        addresses = (self.segment_digests + (self.instrument_master_address,
                     self.rulebook_snapshot_address, self.adjustment_policy_address,
                     self.roll_policy_address, self.missing_data_policy_address,
                     self.alignment_policy_address, self.resampling_policy_address))
        if any(not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in addresses):
            raise ValueError("manifest provenance address is malformed")

    def address(self) -> str:
        from app.backtest.identity import _canonical_json
        payload = {"scheme": "dataset-manifest/phase4/1", **self.__dict__}
        return "sha256:" + hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _fact_address(schema: str, fact: Mapping[str, Any]) -> str:
    from app.market_truth.identity import canonical_fact_address
    return canonical_fact_address(schema, dict(fact))


def _fact_bytes(schema: str, fact: Mapping[str, Any]) -> bytes:
    from app.market_truth.identity import canonical_fact_bytes
    # Dataset manifests/segments can bind 10,000 observations of each source role.
    return canonical_fact_bytes(schema, dict(fact), maximum_bytes=2 * 1024 * 1024)


def _content_address(value: object, label: str) -> str:
    from app.ir.schema import is_content_address
    if not isinstance(value, str) or not is_content_address(value):
        raise ValueError(f"{label} must be a content address")
    return value


def _closed_sorted_addresses(values: object, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or len(values) > 10_000:
        raise ValueError(f"{label} is not a bounded address list")
    result = tuple(values)
    if (not allow_empty and not result) or result != tuple(sorted(set(result))):
        raise ValueError(f"{label} must be non-empty, unique, and sorted")
    for value in result:
        _content_address(value, label)
    return result


def _closed_sorted_strings(values: object, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or len(values) > 10_000:
        raise ValueError(f"{label} is not a bounded string list")
    result = tuple(values)
    if (not allow_empty and not result) or result != tuple(sorted(set(result))):
        raise ValueError(f"{label} must be non-empty, unique, and sorted")
    if any(not isinstance(value, str) or not value or len(value) > 256 for value in result):
        raise ValueError(f"{label} contains an invalid value")
    return result


def _utc_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a UTC timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed.astimezone(dt.timezone.utc).isoformat()


@dataclass(frozen=True)
class DatasetSegment:
    """Closed ``dataset-segment/1`` fact; object bytes are verified separately."""

    owner_id: str
    object_address: str
    byte_digest: str
    byte_length: int
    media_type: str
    raw_schema_address: str
    row_start: int
    row_end: int
    instrument_addresses: tuple[str, ...]
    fields: tuple[str, ...]
    event_start: str
    event_end: str
    availability_start: str
    availability_end: str
    provider_product_addresses: tuple[str, ...]
    provider_contract_addresses: tuple[str, ...]
    provider_observation_addresses: tuple[str, ...]
    normalized_observation_addresses: tuple[str, ...]
    normalization_transform_addresses: tuple[str, ...]
    algorithm_addresses: tuple[str, ...]
    correction_addresses: tuple[str, ...]
    creation_evidence_address: str

    SCHEMA = "dataset-segment/1"
    MAX_BYTES = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id or len(self.owner_id) > 64:
            raise ValueError("segment owner is invalid")
        for name in ("object_address", "byte_digest", "raw_schema_address", "creation_evidence_address"):
            _content_address(getattr(self, name), name)
        if (isinstance(self.byte_length, bool) or not isinstance(self.byte_length, int)
                or not 0 < self.byte_length <= self.MAX_BYTES):
            raise ValueError("segment byte length is outside the local boundary")
        if (isinstance(self.row_start, bool) or isinstance(self.row_end, bool)
                or not isinstance(self.row_start, int) or not isinstance(self.row_end, int)
                or self.row_start < 0 or self.row_end <= self.row_start):
            raise ValueError("segment row range is invalid")
        if not isinstance(self.media_type, str) or not self.media_type or len(self.media_type) > 128:
            raise ValueError("segment media type is invalid")
        for name in ("instrument_addresses", "provider_product_addresses", "provider_contract_addresses",
                     "provider_observation_addresses", "normalized_observation_addresses",
                     "normalization_transform_addresses", "algorithm_addresses"):
            object.__setattr__(self, name, _closed_sorted_addresses(getattr(self, name), name))
        object.__setattr__(self, "correction_addresses", _closed_sorted_addresses(
            self.correction_addresses, "correction_addresses", allow_empty=True))
        object.__setattr__(self, "fields", _closed_sorted_strings(self.fields, "fields"))
        for prefix in ("event", "availability"):
            start = _utc_text(getattr(self, f"{prefix}_start"), f"{prefix}_start")
            end = _utc_text(getattr(self, f"{prefix}_end"), f"{prefix}_end")
            if start >= end:
                raise ValueError(f"segment {prefix} range is inverted")
            object.__setattr__(self, f"{prefix}_start", start)
            object.__setattr__(self, f"{prefix}_end", end)

    def fact(self) -> dict[str, Any]:
        return {name: list(value) if isinstance(value, tuple) else value
                for name, value in self.__dict__.items()}

    @property
    def canonical_bytes(self) -> bytes:
        return _fact_bytes(self.SCHEMA, self.fact())

    @property
    def segment_address(self) -> str:
        return _fact_address(self.SCHEMA, self.fact())

    @classmethod
    def from_bytes(cls, value: bytes) -> "DatasetSegment":
        from app.ir.hashing import canonical_json
        try:
            document = json.loads(value.decode("utf-8"))
            if (canonical_json(document).encode() != value or set(document) != {"schema", "fact"}
                    or document["schema"] != cls.SCHEMA or not isinstance(document["fact"], dict)):
                raise ValueError
            fact = dict(document["fact"])
            for name in ("instrument_addresses", "fields", "provider_product_addresses",
                         "provider_contract_addresses", "provider_observation_addresses",
                         "normalized_observation_addresses", "normalization_transform_addresses",
                         "algorithm_addresses", "correction_addresses"):
                fact[name] = tuple(fact[name])
            result = cls(**fact)
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise ValueError("dataset segment bytes are malformed") from exc
        if result.canonical_bytes != value:
            raise ValueError("dataset segment bytes do not reconstruct exactly")
        return result


@dataclass(frozen=True, init=False)
class DatasetManifest:
    """Closed ``dataset-manifest/2`` fact, with read-only legacy construction.

    The legacy constructor remains solely so historical Phase 4 tests and audit
    rows can be decoded. ``canonical_bytes`` and authority persistence refuse it.
    """

    SCHEMA = "dataset-manifest/2"
    MAX_SEGMENTS = 10_000

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        if self._legacy is not None or other._legacy is not None:
            return self._legacy == other._legacy
        return self.canonical_bytes == other.canonical_bytes

    def __hash__(self):
        return hash(self._legacy if self._legacy is not None else self.canonical_bytes)

    def __init__(self, **values: Any) -> None:
        if "dataset_address" in values:
            legacy = LegacyDatasetManifest(**values)
            object.__setattr__(self, "_legacy", legacy)
            return
        required = {
            "owner_id", "purpose", "mode", "segment_addresses", "aggregate_byte_digest",
            "aggregate_byte_length", "instrument_addresses", "fields", "event_start", "event_end",
            "availability_start", "availability_end", "gaps", "correction_addresses",
            "provider_entity_addresses", "provider_product_addresses", "provider_contract_addresses",
            "provider_observation_addresses", "normalized_observation_addresses",
            "raw_schema_addresses", "normalization_transform_addresses", "truth_snapshot_addresses",
            "creation_evidence_addresses",
            "capability_profile_address", "alignment_policy_address",
            "missing_data_policy_address", "adjustment_policy_address", "roll_policy_address",
            "algorithm_addresses", "created_at", "recorded_at",
        }
        if set(values) != required:
            raise ValueError("dataset manifest fields are not closed")
        if (not isinstance(values["owner_id"], str) or not values["owner_id"]
                or len(values["owner_id"]) > 64 or values["mode"] not in {"RESEARCH", "PAPER", "LIVE"}
                or not isinstance(values["purpose"], str) or not values["purpose"]):
            raise ValueError("dataset manifest owner, purpose, or mode is invalid")
        if (isinstance(values["aggregate_byte_length"], bool)
                or not isinstance(values["aggregate_byte_length"], int)
                or values["aggregate_byte_length"] <= 0):
            raise ValueError("dataset aggregate byte length is invalid")
        address_lists = ("segment_addresses", "provider_entity_addresses", "provider_product_addresses",
            "provider_contract_addresses", "provider_observation_addresses",
            "normalized_observation_addresses", "raw_schema_addresses",
            "normalization_transform_addresses", "truth_snapshot_addresses",
            "creation_evidence_addresses", "algorithm_addresses")
        for name in address_lists:
            parsed = _closed_sorted_addresses(values[name], name)
            if name == "segment_addresses" and len(parsed) > self.MAX_SEGMENTS:
                raise ValueError("dataset segment bound exceeded")
            object.__setattr__(self, name, parsed)
        object.__setattr__(self, "correction_addresses", _closed_sorted_addresses(
            values["correction_addresses"], "correction_addresses", allow_empty=True))
        object.__setattr__(self, "instrument_addresses", _closed_sorted_addresses(
            values["instrument_addresses"], "instrument_addresses"))
        object.__setattr__(self, "fields", _closed_sorted_strings(values["fields"], "fields"))
        if not isinstance(values["gaps"], (tuple, list)) or len(values["gaps"]) > 10_000:
            raise ValueError("dataset gaps are not bounded")
        gaps = tuple(values["gaps"])
        if any(not isinstance(gap, dict) or set(gap) != {"instrument_address", "field", "start", "end", "reason"}
               for gap in gaps):
            raise ValueError("dataset gap is not closed")
        normalized_gaps = tuple(sorted((dict(gap) for gap in gaps), key=lambda gap: json.dumps(gap, sort_keys=True)))
        if normalized_gaps != gaps:
            raise ValueError("dataset gaps must be canonically ordered")
        object.__setattr__(self, "gaps", normalized_gaps)
        for name in ("aggregate_byte_digest", "capability_profile_address",
                     "alignment_policy_address", "missing_data_policy_address", "adjustment_policy_address",
                     "roll_policy_address"):
            object.__setattr__(self, name, _content_address(values[name], name))
        for prefix in ("event", "availability"):
            start = _utc_text(values[f"{prefix}_start"], f"{prefix}_start")
            end = _utc_text(values[f"{prefix}_end"], f"{prefix}_end")
            if start >= end:
                raise ValueError(f"manifest {prefix} range is inverted")
            object.__setattr__(self, f"{prefix}_start", start)
            object.__setattr__(self, f"{prefix}_end", end)
        for name in ("created_at", "recorded_at"):
            object.__setattr__(self, name, _utc_text(values[name], name))
        if self.recorded_at < self.created_at:
            raise ValueError("manifest recorded time precedes creation")
        for name in ("owner_id", "purpose", "mode", "aggregate_byte_length"):
            object.__setattr__(self, name, values[name])
        object.__setattr__(self, "_legacy", None)

    def fact(self) -> dict[str, Any]:
        if self._legacy is not None:
            raise ValueError("legacy dataset manifest has no dataset-manifest/2 authority")
        result: dict[str, Any] = {}
        for name, value in self.__dict__.items():
            if name == "_legacy":
                continue
            if isinstance(value, tuple):
                result[name] = [dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[name] = value
        return result

    @property
    def canonical_bytes(self) -> bytes:
        return _fact_bytes(self.SCHEMA, self.fact())

    @property
    def manifest_address(self) -> str:
        return _fact_address(self.SCHEMA, self.fact())

    def address(self) -> str:
        return self._legacy.address() if self._legacy is not None else self.manifest_address

    @classmethod
    def from_bytes(cls, value: bytes) -> "DatasetManifest":
        from app.ir.hashing import canonical_json
        try:
            document = json.loads(value.decode("utf-8"))
            if (canonical_json(document).encode() != value or set(document) != {"schema", "fact"}
                    or document["schema"] != cls.SCHEMA or not isinstance(document["fact"], dict)):
                raise ValueError
            fact = dict(document["fact"])
            for name in ("segment_addresses", "instrument_addresses", "fields", "gaps",
                         "correction_addresses", "provider_entity_addresses", "provider_product_addresses",
                         "provider_contract_addresses", "provider_observation_addresses",
                         "normalized_observation_addresses", "raw_schema_addresses",
                         "normalization_transform_addresses", "truth_snapshot_addresses", "algorithm_addresses"):
                fact[name] = tuple(fact[name])
            fact["creation_evidence_addresses"] = tuple(fact["creation_evidence_addresses"])
            result = cls(**fact)
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise ValueError("dataset manifest bytes are malformed") from exc
        if result.canonical_bytes != value:
            raise ValueError("dataset manifest bytes do not reconstruct exactly")
        return result


def dataset_byte_digest(value: bytes) -> str:
    """Return the byte identity used by segment and aggregate authority facts."""
    if not isinstance(value, bytes) or not value:
        raise ValueError("dataset object bytes must be non-empty bytes")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def verify_dataset_segment(segment: DatasetSegment, object_bytes: bytes) -> None:
    """Verify stored object bytes before any copied coverage is trusted."""
    if len(object_bytes) != segment.byte_length:
        raise ValueError("dataset segment byte length mismatch")
    if dataset_byte_digest(object_bytes) != segment.byte_digest:
        raise ValueError("dataset segment byte digest mismatch")


def _covers(intervals: list[tuple[str, str]], start: str, end: str) -> bool:
    """Whether half-open, UTC intervals cover the requested interval exactly."""
    cursor = start
    for left, right in sorted(intervals):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return False


def verify_dataset_manifest(
    manifest: DatasetManifest,
    segments: Mapping[str, tuple[DatasetSegment, bytes]],
) -> tuple[DatasetSegment, ...]:
    """Reconstruct the complete ``dataset-manifest/2`` authority chain.

    Callers receive segments in the manifest's canonical order only after raw
    bytes, copied unions, aggregate identity, ownership, and coverage verify.
    """
    if manifest._legacy is not None:
        raise ValueError("legacy dataset manifest is LEGACY_UNVERIFIED")
    if set(segments) != set(manifest.segment_addresses):
        raise ValueError("dataset manifest segment set is incomplete or contains extras")
    ordered: list[DatasetSegment] = []
    objects: list[bytes] = []
    for address in manifest.segment_addresses:
        try:
            segment, object_bytes = segments[address]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("dataset segment chain is malformed") from exc
        if segment.segment_address != address:
            raise ValueError("dataset segment address does not reconstruct")
        if segment.owner_id != manifest.owner_id:
            raise ValueError("dataset segment owner mismatch")
        verify_dataset_segment(segment, object_bytes)
        ordered.append(segment)
        objects.append(object_bytes)
    combined = b"".join(objects)
    if len(combined) != manifest.aggregate_byte_length:
        raise ValueError("dataset aggregate byte length mismatch")
    if dataset_byte_digest(combined) != manifest.aggregate_byte_digest:
        raise ValueError("dataset aggregate byte digest mismatch")

    def union(name: str) -> tuple[str, ...]:
        return tuple(sorted({value for segment in ordered for value in getattr(segment, name)}))

    copied_unions = {
        "instrument_addresses": union("instrument_addresses"),
        "fields": union("fields"),
        "correction_addresses": union("correction_addresses"),
        "provider_product_addresses": union("provider_product_addresses"),
        "provider_contract_addresses": union("provider_contract_addresses"),
        "provider_observation_addresses": union("provider_observation_addresses"),
        "normalized_observation_addresses": union("normalized_observation_addresses"),
        "raw_schema_addresses": tuple(sorted({segment.raw_schema_address for segment in ordered})),
        "normalization_transform_addresses": union("normalization_transform_addresses"),
        "creation_evidence_addresses": tuple(sorted({segment.creation_evidence_address for segment in ordered})),
        "algorithm_addresses": union("algorithm_addresses"),
    }
    for name, expected in copied_unions.items():
        if getattr(manifest, name) != expected:
            raise ValueError(f"dataset manifest copied {name} does not reconstruct")
    if min(segment.event_start for segment in ordered) < manifest.event_start:
        raise ValueError("dataset segment event range escapes manifest")
    if max(segment.event_end for segment in ordered) > manifest.event_end:
        raise ValueError("dataset segment event range escapes manifest")
    if min(segment.availability_start for segment in ordered) < manifest.availability_start:
        raise ValueError("dataset segment availability range escapes manifest")
    if max(segment.availability_end for segment in ordered) > manifest.availability_end:
        raise ValueError("dataset segment availability range escapes manifest")

    gap_intervals: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for gap in manifest.gaps:
        instrument = _content_address(gap["instrument_address"], "gap instrument")
        field = gap["field"]
        left = _utc_text(gap["start"], "gap start")
        right = _utc_text(gap["end"], "gap end")
        if (instrument not in manifest.instrument_addresses or field not in manifest.fields
                or not isinstance(gap["reason"], str) or not gap["reason"]
                or left >= right or left < manifest.event_start or right > manifest.event_end):
            raise ValueError("dataset gap is invalid or outside requested coverage")
        gap_intervals.setdefault((instrument, field), []).append((left, right))
    for instrument in manifest.instrument_addresses:
        for field in manifest.fields:
            event_intervals = [
                (segment.event_start, segment.event_end) for segment in ordered
                if instrument in segment.instrument_addresses and field in segment.fields
            ] + gap_intervals.get((instrument, field), [])
            if not _covers(event_intervals, manifest.event_start, manifest.event_end):
                raise ValueError("dataset event coverage is incomplete")
            availability_intervals = [
                (segment.availability_start, segment.availability_end) for segment in ordered
                if instrument in segment.instrument_addresses and field in segment.fields
            ]
            if not _covers(availability_intervals, manifest.availability_start,
                           manifest.availability_end):
                raise ValueError("dataset availability coverage is incomplete")
    return tuple(ordered)

BLOB_SUFFIX = ".ptds"
MANIFEST_SUFFIX = ".json"
STORE_SCHEME = "backtest-dataset-store/1"
MARKET_PUBLIC = "MARKET_PUBLIC"
_MAGIC = b"PTDS1\0"
_HEADER = len(_MAGIC) + 8
_RECORD = struct.calcsize(">q5d")            # 48 bytes: int64 + five binary64
_COMPRESSION_LEVEL = 6
# The project's native candle clock: naive timestamps ARE IST wall-clock
# (`app/core/market_hours.py::ist_epoch`), so they round-trip back naive.
_IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_UTC = dt.timezone.utc


@dataclass(frozen=True)
class StoredCandle:
    """One decoded bar. Field-compatible with providers' `Candle` and the
    sweep's `_FrozenCandle`, deliberately without either's behaviour."""
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class StoredDataset:
    address: str
    candles: tuple[StoredCandle, ...]
    provider: Any
    instrument: Any
    interval: str
    requested_window: Any
    effective_window: Any
    bars: int
    first_ts_us: int
    last_ts_us: int
    classification: str = MARKET_PUBLIC


@dataclass(frozen=True)
class IndexEntry:
    request_key: str
    address: str
    fetched_at: str


class DatasetStoreError(RuntimeError):
    """A dataset could not be stored. Never fatal to a sweep."""


@runtime_checkable
class PublicDatasetStorage(Protocol):
    """Port used by sweeps for verified public data, not filesystem internals.

    The local adapter is deliberately the only implementation in this phase. A
    future object store implements this protocol without gaining an owner/BYOD
    namespace by accident.
    """
    def put(self, candles, *, provider: Any, instrument: Any, interval: str,
            requested_window: Any, effective_window: Any, address: str | None = None,
            classification: str = MARKET_PUBLIC) -> str: ...
    def get(self, address: str, *, classification: str = MARKET_PUBLIC) -> StoredDataset | None: ...
    def lookup(self, *, provider: Any, instrument: Any, interval: str,
               requested_window: Any, classification: str = MARKET_PUBLIC) -> IndexEntry | None: ...
    def worker_descriptor(self) -> Mapping[str, str]: ...


def _require_public(classification: str) -> None:
    if classification != MARKET_PUBLIC:
        raise DatasetStoreError("public dataset storage refuses non-public classification")


def _is_public_address(value: object) -> bool:
    """A content address is lower-case hex only; never treat it as a path."""
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


# ── packed binary form ───────────────────────────────────────────────────────

def _timestamp_us(value: dt.datetime) -> int:
    aware = value.replace(tzinfo=_IST) if value.tzinfo is None else value
    delta = aware.astimezone(_UTC) - dt.datetime(1970, 1, 1, tzinfo=_UTC)
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def encode_candles(candles) -> bytes:
    out = bytearray(_MAGIC)
    out += struct.pack(">Q", len(candles))
    for index, candle in enumerate(candles):
        ts = getattr(candle, "ts", None)
        if not isinstance(ts, dt.datetime):
            raise DatasetStoreError(f"candle {index} has no datetime ts")
        try:
            fields = (
                market_float(candle.open, field=f"candle {index} open"),
                market_float(candle.high, field=f"candle {index} high"),
                market_float(candle.low, field=f"candle {index} low"),
                market_float(candle.close, field=f"candle {index} close"),
                market_float(candle.volume, field=f"candle {index} volume"))
        except NumericIngressError as e:
            # The storage boundary keeps its own vocabulary: a boolean that
            # reached this far is a DatasetStoreError naming the candle.
            raise DatasetStoreError(str(e)) from e
        out += struct.pack(">q5d", _timestamp_us(ts), *fields)
    return zlib.compress(bytes(out), _COMPRESSION_LEVEL)


def decode_candles(blob: bytes) -> tuple[StoredCandle, ...]:
    raw = zlib.decompress(blob)
    if len(raw) < _HEADER or raw[:len(_MAGIC)] != _MAGIC:
        raise ValueError("not a dataset blob")
    count = struct.unpack(">Q", raw[len(_MAGIC):_HEADER])[0]
    if len(raw) != _HEADER + count * _RECORD:
        raise ValueError("dataset blob length disagrees with its bar count")
    rows = []
    for index in range(count):
        offset = _HEADER + index * _RECORD
        us, o, h, low, close, volume = struct.unpack(
            ">q5d", raw[offset:offset + _RECORD])
        ts = dt.datetime.fromtimestamp(us / 1_000_000, _UTC).astimezone(
            _IST).replace(tzinfo=None)
        rows.append(StoredCandle(ts, o, h, low, close, volume))
    return tuple(rows)


def _json_stable(value: Any) -> Any:
    """The manifest must survive JSON round-trip *identically*, or a reloaded
    dataset re-addresses differently and is refused for no real reason."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         allow_nan=False)
    if json.loads(encoded) != value:
        raise DatasetStoreError("dataset metadata does not survive JSON")
    return encoded


# ── the store ────────────────────────────────────────────────────────────────

class DatasetStore:
    """Content-addressed datasets on disk, with a request index beside them."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.root / "index.sqlite3"),
                                     check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS dataset_requests ("
            " request_key TEXT PRIMARY KEY,"
            " provider TEXT NOT NULL, instrument TEXT NOT NULL,"
            " interval TEXT NOT NULL, requested_window TEXT NOT NULL,"
            " address TEXT NOT NULL, fetched_at TEXT NOT NULL)")
        self._conn.commit()
        self._measurements = {"put": 0, "get": 0, "lookup": 0,
                              "corruption_refusals": 0, "read_seconds": 0.0}

    # paths -------------------------------------------------------------
    def _shard(self, address: str) -> Path:
        return self.root / "blobs" / address[:2]

    def blob_path(self, address: str) -> Path:
        return self._shard(address) / f"{address}{BLOB_SUFFIX}"

    def manifest_path(self, address: str) -> Path:
        return self._shard(address) / f"{address}{MANIFEST_SUFFIX}"

    # request identity --------------------------------------------------
    def request_key(self, *, provider: Any, instrument: Any, interval: str,
                    requested_window: Any) -> str:
        """Address of the REQUEST — not of its answer. Two fetches of the same
        request in different weeks share this key and differ in address."""
        payload = _json_stable({
            "scheme": STORE_SCHEME,
            "provider": source_identity(provider, fields=PROVIDER_IDENTITY_FIELDS),
            "instrument": source_identity(instrument,
                                          fields=INSTRUMENT_IDENTITY_FIELDS),
            "interval": interval,
            "requested_window": requested_window,
        })
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # write -------------------------------------------------------------
    def put(self, candles, *, provider: Any, instrument: Any, interval: str,
            requested_window: Any, effective_window: Any,
            address: str | None = None,
            classification: str = MARKET_PUBLIC) -> str:
        """Store one dataset; return its address.

        Revised history is a NEW address, never an overwrite: the address binds
        the ordered bytes, so a corrected candle produces a different file and
        the previous dataset stays retrievable. Only the request index moves.
        """
        _require_public(classification)
        provider_identity = source_identity(provider,
                                            fields=PROVIDER_IDENTITY_FIELDS)
        instrument_identity = source_identity(instrument,
                                              fields=INSTRUMENT_IDENTITY_FIELDS)
        # Recompute even when a caller supplied an address.  The supplied value
        # is an assertion, not a permission to put arbitrary bytes at its path.
        recomputed_address = ordered_dataset_address(
            candles, provider=provider_identity, instrument=instrument_identity,
            interval=interval, requested_window=requested_window,
            effective_window=effective_window)
        if address is not None and address != recomputed_address:
            raise DatasetStoreError("supplied address does not name these dataset bytes")
        address = recomputed_address
        if not _is_public_address(address):
            raise DatasetStoreError(f"not a dataset address: {address!r}")

        # An immutable retry first checks the already-published pair.  This is
        # both idempotent and protects a good prior artifact from an unrelated
        # write failure on a later retry.
        existing = self.get(address, classification=classification)
        if existing is not None:
            self._record(address, provider=provider, instrument=instrument,
                         interval=interval, requested_window=requested_window,
                         provider_identity=provider_identity,
                         instrument_identity=instrument_identity)
            self._measurements["put"] += 1
            return address

        blob = encode_candles(candles)
        decoded = decode_candles(blob)
        manifest = _json_stable({
            "scheme": STORE_SCHEME,
            "address": address,
            "provider": provider_identity,
            "instrument": instrument_identity,
            "interval": interval,
            "requested_window": requested_window,
            "effective_window": effective_window,
            "bars": len(decoded),
            "first_ts_us": _timestamp_us(decoded[0].ts) if decoded else 0,
            "last_ts_us": _timestamp_us(decoded[-1].ts) if decoded else 0,
            "classification": MARKET_PUBLIC,
        })

        blob_path, manifest_path = self.blob_path(address), self.manifest_path(address)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._atomic_write(blob_path, blob)
            self._atomic_write(manifest_path, manifest.encode("utf-8"))
        except Exception:
            # Never delete target paths here. An interrupted pair is refused by
            # get(), while deleting can destroy an earlier valid immutable pair.
            raise
        self._record(address, provider=provider, instrument=instrument,
                     interval=interval, requested_window=requested_window,
                     provider_identity=provider_identity,
                     instrument_identity=instrument_identity)
        self._measurements["put"] += 1
        return address

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        """Write to a temp name in the same directory, then rename over.

        A reader only ever sees the complete file: `os.replace` is atomic within
        a filesystem, and the temp name carries a suffix no reader looks for.
        """
        tmp = path.parent / f"{path.name}.tmp-{uuid.uuid4().hex}"
        try:
            with open(tmp, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _record(self, address: str, *, provider, instrument, interval,
                requested_window, provider_identity, instrument_identity) -> None:
        key = self.request_key(provider=provider, instrument=instrument,
                               interval=interval,
                               requested_window=requested_window)
        row = (key, json.dumps(provider_identity, sort_keys=True),
               json.dumps(instrument_identity, sort_keys=True), interval,
               json.dumps(requested_window, sort_keys=True), address,
               dt.datetime.now().isoformat(timespec="microseconds"))
        with self._lock:
            self._conn.execute(
                "INSERT INTO dataset_requests(request_key,provider,instrument,"
                " interval,requested_window,address,fetched_at)"
                " VALUES(?,?,?,?,?,?,?)"
                " ON CONFLICT(request_key) DO UPDATE SET"
                " address=excluded.address, fetched_at=excluded.fetched_at",
                row)
            self._conn.commit()

    # read --------------------------------------------------------------
    def get(self, address: str, *, classification: str = MARKET_PUBLIC) -> StoredDataset | None:
        """Return the dataset at `address`, or None if it cannot be PROVEN to be
        that dataset. Every failure mode is a refusal, never a partial answer."""
        _require_public(classification)
        if not _is_public_address(address):
            return None
        started = dt.datetime.now().timestamp()
        self._measurements["get"] += 1
        blob_path, manifest_path = self.blob_path(address), self.manifest_path(address)
        if not (blob_path.is_file() and manifest_path.is_file()):
            self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
            return None
        try:
            manifest = json.loads(manifest_path.read_text())
            candles = decode_candles(blob_path.read_bytes())
        except (OSError, ValueError, zlib.error, struct.error):
            self._measurements["corruption_refusals"] += 1
            self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
            return None
        if not isinstance(manifest, dict) or manifest.get("scheme") != STORE_SCHEME:
            self._measurements["corruption_refusals"] += 1
            self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
            return None
        if manifest.get("bars") != len(candles):
            self._measurements["corruption_refusals"] += 1
            self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
            return None
        try:
            recomputed = ordered_dataset_address(
                candles, provider=manifest["provider"],
                instrument=manifest["instrument"],
                interval=manifest["interval"],
                requested_window=manifest["requested_window"],
                effective_window=manifest["effective_window"])
        except (KeyError, ValueError, TypeError):
            self._measurements["corruption_refusals"] += 1
            self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
            return None
        if recomputed != address:
            # THE containment guard: the bytes on disk are not the bytes this
            # address names. Serving them would put a silently wrong dataset
            # into a backtest, which is worse than any read failure.
            self._measurements["corruption_refusals"] += 1
            self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
            return None
        # Missing classification is a legacy/unknown namespace, never public.
        if manifest.get("classification") != MARKET_PUBLIC:
            self._measurements["corruption_refusals"] += 1
            self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
            return None
        self._measurements["read_seconds"] += dt.datetime.now().timestamp() - started
        return StoredDataset(
            address=address, candles=candles, provider=manifest["provider"],
            instrument=manifest["instrument"], interval=manifest["interval"],
            requested_window=manifest["requested_window"],
            effective_window=manifest["effective_window"], bars=len(candles),
            first_ts_us=int(manifest.get("first_ts_us", 0)),
            last_ts_us=int(manifest.get("last_ts_us", 0)), classification=MARKET_PUBLIC)

    def manifest(self, address: str) -> dict | None:
        """The sidecar manifest alone, without decoding the blob.

        This is a **planning** read, not a proof, and the difference matters.
        `get` proves the bytes on disk are the bytes this address names; this
        reads a few hundred bytes of JSON and proves nothing about them. It
        exists because a parallel pinned sweep must decide, cheaply and in the
        parent, which cells already have a reusable result — while the
        verification that decides whether a dataset may be SIMULATED happens in
        the worker that will simulate it.

        Nothing here may be used to serve candles or to skip a refusal. The one
        value the parent takes from it, the effective window's last timestamp,
        is a result-cache discriminator: a lying manifest can only cause a cache
        MISS, because a hit additionally requires an execution address that
        binds the dataset address, and a row whose stored last timestamp came
        from the real decoded bars.
        """
        if not _is_public_address(address):
            return None
        try:
            manifest = json.loads(self.manifest_path(address).read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(manifest, dict) or manifest.get("scheme") != STORE_SCHEME:
            return None
        return manifest

    def lookup(self, *, provider: Any, instrument: Any, interval: str,
               requested_window: Any,
               classification: str = MARKET_PUBLIC) -> IndexEntry | None:
        """The newest address stored for this request, and when it was fetched.

        A record of what was fetched, never a permission: it does not authorise
        skipping a provider read. C13 forbids executor paths from branching on
        where data came from, and this store is on that side of the line.
        """
        _require_public(classification)
        self._measurements["lookup"] += 1
        key = self.request_key(provider=provider, instrument=instrument,
                               interval=interval,
                               requested_window=requested_window)
        with self._lock:
            row = self._conn.execute(
                "SELECT request_key,address,fetched_at FROM dataset_requests"
                " WHERE request_key=?", (key,)).fetchone()
        if row is None or not _is_public_address(row[1]):
            return None
        return IndexEntry(*row)

    def stored_addresses(self) -> list[str]:
        return sorted(path.name[:-len(BLOB_SUFFIX)]
                      for path in self.root.glob(f"blobs/*/*{BLOB_SUFFIX}"))

    def measurements(self) -> dict[str, int | float]:
        """Bounded operational counters, deliberately without tenant labels."""
        return dict(self._measurements)

    def close(self) -> None:
        self._conn.close()

    def worker_descriptor(self) -> dict[str, str]:
        """Opaque local-adapter locator; sweep workers never know a root layout."""
        return {"scheme": "local-dataset-store/1", "root": str(self.root)}


# ── process-wide default ─────────────────────────────────────────────────────

def store_root() -> Path:
    """Where datasets live. Tests monkeypatch this onto a tmp_path."""
    return Path(get_settings().backtest_dataset_dir).expanduser()


_default_store: DatasetStore | None = None
_default_root: Path | None = None
_default_lock = threading.Lock()


def get_store() -> DatasetStore:
    global _default_store, _default_root
    root = Path(store_root())
    with _default_lock:
        if _default_store is None or _default_root != root:
            if _default_store is not None:
                _default_store.close()
            _default_store = DatasetStore(root)
            _default_root = root
        return _default_store


def reset_default_store() -> None:
    global _default_store, _default_root
    with _default_lock:
        if _default_store is not None:
            _default_store.close()
        _default_store = None
        _default_root = None


def open_worker_storage(descriptor: Mapping[str, str]) -> PublicDatasetStorage:
    """Resolve a parent-selected worker-readable storage port, fail closed."""
    if not isinstance(descriptor, Mapping) or descriptor.get("scheme") != "local-dataset-store/1":
        raise DatasetStoreError("unknown public dataset storage descriptor")
    root = descriptor.get("root")
    if not isinstance(root, str) or not root:
        raise DatasetStoreError("invalid public dataset storage descriptor")
    return DatasetStore(root)


__all__ = ["BLOB_SUFFIX", "MANIFEST_SUFFIX", "STORE_SCHEME", "MARKET_PUBLIC", "DatasetStore",
           "DatasetStoreError", "IndexEntry", "StoredCandle", "StoredDataset",
           "PublicDatasetStorage",
           "decode_candles", "encode_candles", "get_store", "open_worker_storage",
           "reset_default_store", "store_root"]
