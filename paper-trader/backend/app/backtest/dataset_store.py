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
import sqlite3
import struct
import threading
import uuid
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from app.backtest.identity import (INSTRUMENT_IDENTITY_FIELDS,
                                   PROVIDER_IDENTITY_FIELDS,
                                   ordered_dataset_address, source_identity)
from app.core.config import get_settings

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
        out += struct.pack(">q5d", _timestamp_us(ts), float(candle.open),
                           float(candle.high), float(candle.low),
                           float(candle.close), float(candle.volume))
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
        if len(address) != 64 or any(c not in "0123456789abcdef" for c in address):
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
        return IndexEntry(*row) if row else None

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
