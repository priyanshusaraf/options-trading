"""Bounded, owner-scoped local research cache and artifact authority."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import hashlib
import json
import math
from threading import Condition, RLock
from types import MappingProxyType
from typing import Any, Callable, Mapping

from app.ir.hashing import content_address
from app.ir.schema import is_content_address


class ResearchArtifactRefusal(ValueError):
    pass


IDENTITY_FIELDS = {
    "schema", "owner_id", "licence_scope", "semantic_nodes",
    "parameters_address", "instrument_addresses", "registry_snapshot_address",
    "dataset_manifest_address", "provider_evidence_addresses", "event_start",
    "event_end", "segment_addresses", "adjustment_policy_address",
    "session_policy_address", "resampling_policy_address",
    "missing_data_policy_address", "alignment_policy_address",
    "implementation_closure_address", "resolved_graph_address",
    "resource_plan_address", "evaluation_policy_address",
    "node_context_resolver_address", "run_authority_address", "identity_address",
}
LICENCE_SCOPES = ("OWNER_PRIVATE", "PLATFORM_PUBLIC")


@dataclass(frozen=True, init=False)
class ResearchCacheIdentity:
    document: Mapping[str, Any]
    identity_address: str

    def __init__(self, *args, **kwargs) -> None:
        raise ResearchArtifactRefusal("research identities use research_cache_identity")

    def _validate(self) -> None:
        reconstructed = research_cache_identity(_plain(self.document))
        if reconstructed.document != self.document \
                or reconstructed.identity_address != self.identity_address:
            raise ResearchArtifactRefusal("research cache identity is stale")


def research_cache_identity(document: Mapping[str, Any]) -> ResearchCacheIdentity:
    if not isinstance(document, Mapping) or set(document) != IDENTITY_FIELDS \
            or document.get("schema") != "phase5-research-cache-identity/1":
        raise ResearchArtifactRefusal("research cache identity schema is incomplete")
    owner_id = document["owner_id"]
    if not isinstance(owner_id, str) or not owner_id:
        raise ResearchArtifactRefusal("research cache owner is absent")
    if document["licence_scope"] not in LICENCE_SCOPES:
        raise ResearchArtifactRefusal("research cache licence scope is unknown")
    nodes = document["semantic_nodes"]
    if not isinstance(nodes, (tuple, list)) or not nodes:
        raise ResearchArtifactRefusal("research semantic nodes are absent")
    canonical_nodes = []
    for row in nodes:
        if not isinstance(row, Mapping) or set(row) != {
            "component_id", "component_version",
        } or not isinstance(row["component_id"], str) or not row["component_id"] \
                or type(row["component_version"]) is not int \
                or row["component_version"] < 1:
            raise ResearchArtifactRefusal("research semantic node is malformed")
        canonical_nodes.append(dict(row))
    if canonical_nodes != sorted(
        canonical_nodes, key=lambda row: (row["component_id"], row["component_version"])
    ) or len({(row["component_id"], row["component_version"])
              for row in canonical_nodes}) != len(canonical_nodes):
        raise ResearchArtifactRefusal("research semantic nodes are noncanonical")
    for name in (
        "parameters_address", "registry_snapshot_address",
        "dataset_manifest_address", "adjustment_policy_address",
        "session_policy_address", "resampling_policy_address",
        "missing_data_policy_address", "alignment_policy_address",
        "implementation_closure_address", "resolved_graph_address",
        "resource_plan_address", "evaluation_policy_address",
        "node_context_resolver_address", "run_authority_address",
    ):
        _address(document[name], name)
    instruments = _addresses(document["instrument_addresses"], "instruments")
    providers = _addresses(document["provider_evidence_addresses"], "provider evidence")
    segments = _addresses(document["segment_addresses"], "segments")
    start, end = _aware(document["event_start"]), _aware(document["event_end"])
    if start >= end:
        raise ResearchArtifactRefusal("research cache event window is empty")
    payload = {
        **document,
        "semantic_nodes": canonical_nodes,
        "instrument_addresses": list(instruments),
        "provider_evidence_addresses": list(providers),
        "segment_addresses": list(segments),
    }
    expected = content_address({
        key: _plain(value) for key, value in payload.items()
        if key != "identity_address"
    })
    if payload["identity_address"] != expected:
        raise ResearchArtifactRefusal("research cache identity address is stale")
    result = object.__new__(ResearchCacheIdentity)
    object.__setattr__(result, "document", _freeze(payload))
    object.__setattr__(result, "identity_address", expected)
    return result


def research_cache_identity_document(**values: Any) -> Mapping[str, Any]:
    payload = {"schema": "phase5-research-cache-identity/1", **values}
    payload["identity_address"] = content_address(payload)
    return payload


@dataclass(frozen=True)
class ResearchCostRecord:
    document: Mapping[str, Any]
    cost_address: str


@dataclass(frozen=True)
class MaterializedArtifact:
    payload: Any
    artifact_address: str
    from_cache: bool
    cost: ResearchCostRecord


@dataclass(frozen=True)
class ResearchArtifactSnapshot:
    owner_id: str
    licence_scope: str
    entries: tuple[tuple[Mapping[str, Any], bytes], ...]


@dataclass
class _StoredArtifact:
    document: Mapping[str, Any]
    payload_bytes: bytes
    access_sequence: int


class BoundedResearchArtifactStore:
    """Thread-safe single-flight local adapter with hard byte/concurrency bounds."""

    _METRIC_NAMES = (
        "cold_computes", "cache_hits", "waits", "cancellations", "failures",
        "evictions", "corruption_refusals", "read_bytes", "write_bytes",
    )

    def __init__(
        self, *, owner_id: str, licence_scope: str,
        cache_bytes_upper_bound: int, artifact_bytes_upper_bound: int,
        entry_upper_bound: int, concurrency_upper_bound: int,
        queue_depth_upper_bound: int,
    ) -> None:
        if not isinstance(owner_id, str) or not owner_id \
                or licence_scope not in LICENCE_SCOPES:
            raise ResearchArtifactRefusal("artifact store owner/licence is invalid")
        for label, value, positive in (
            ("cache bytes", cache_bytes_upper_bound, False),
            ("artifact bytes", artifact_bytes_upper_bound, False),
            ("entries", entry_upper_bound, True),
            ("concurrency", concurrency_upper_bound, True),
            ("queue depth", queue_depth_upper_bound, False),
        ):
            _integer(value, label, positive=positive)
        self.owner_id, self.licence_scope = owner_id, licence_scope
        self.cache_bytes_upper_bound = cache_bytes_upper_bound
        self.artifact_bytes_upper_bound = artifact_bytes_upper_bound
        self.entry_upper_bound = entry_upper_bound
        self.concurrency_upper_bound = concurrency_upper_bound
        self.queue_depth_upper_bound = queue_depth_upper_bound
        self._condition = Condition(RLock())
        self._entries: dict[str, _StoredArtifact] = {}
        self._inflight: set[str] = set()
        self._active = self._queued = self._sequence = 0
        self._metrics = {name: 0 for name in self._METRIC_NAMES}

    def get_or_compute(
        self, identity: ResearchCacheIdentity,
        compute: Callable[[], Any], *,
        cancelled: Callable[[], bool] | None = None,
    ) -> MaterializedArtifact:
        identity = self._require_identity(identity)
        queued = False
        while True:
            with self._condition:
                if cancelled is not None and cancelled():
                    if queued: self._queued -= 1
                    self._metrics["cancellations"] += 1
                    raise ResearchArtifactRefusal("research computation is cancelled")
                stored = self._entries.get(identity.identity_address)
                if stored is not None:
                    if queued: self._queued -= 1
                    payload = self._read_verified(identity, stored)
                    stored.access_sequence = self._next_sequence()
                    self._metrics["cache_hits"] += 1
                    self._metrics["read_bytes"] += len(stored.payload_bytes)
                    return MaterializedArtifact(
                        payload, stored.document["artifact_address"], True,
                        self._cost(identity, "CACHE_HIT", read_bytes=len(stored.payload_bytes)),
                    )
                blocked = (
                    identity.identity_address in self._inflight
                    or self._active >= self.concurrency_upper_bound
                )
                if blocked:
                    if not queued:
                        if self._queued >= self.queue_depth_upper_bound:
                            raise ResearchArtifactRefusal("research queue depth exceeds bound")
                        self._queued += 1; queued = True
                        self._metrics["waits"] += 1
                    self._condition.wait(timeout=0.05)
                    continue
                if queued: self._queued -= 1
                self._active += 1
                self._inflight.add(identity.identity_address)
                break
        try:
            if cancelled is not None and cancelled():
                self._metrics["cancellations"] += 1
                raise ResearchArtifactRefusal("research computation is cancelled")
            payload = compute()
            payload_bytes = _canonical_payload(payload)
            if len(payload_bytes) > self.artifact_bytes_upper_bound:
                raise ResearchArtifactRefusal("research artifact exceeds byte bound")
            if cancelled is not None and cancelled():
                self._metrics["cancellations"] += 1
                raise ResearchArtifactRefusal("research computation is cancelled")
            document = _artifact_document(identity, payload_bytes)
            with self._condition:
                self._evict_to_fit(len(payload_bytes))
                self._entries[identity.identity_address] = _StoredArtifact(
                    _freeze(document), bytes(payload_bytes), self._next_sequence(),
                )
                self._metrics["cold_computes"] += 1
                self._metrics["write_bytes"] += len(payload_bytes)
            return MaterializedArtifact(
                _decode_payload(payload_bytes), document["artifact_address"], False,
                self._cost(identity, "COLD_COMPUTE", write_bytes=len(payload_bytes)),
            )
        except Exception:
            self._metrics["failures"] += 1
            raise
        finally:
            with self._condition:
                self._active -= 1
                self._inflight.discard(identity.identity_address)
                self._condition.notify_all()

    def evict(self, identity: ResearchCacheIdentity) -> bool:
        identity = self._require_identity(identity)
        with self._condition:
            removed = self._entries.pop(identity.identity_address, None)
            if removed is not None: self._metrics["evictions"] += 1
            return removed is not None

    def snapshot(self) -> ResearchArtifactSnapshot:
        with self._condition:
            entries = tuple(
                (stored.document, bytes(stored.payload_bytes))
                for _key, stored in sorted(self._entries.items())
            )
        return ResearchArtifactSnapshot(self.owner_id, self.licence_scope, entries)

    @classmethod
    def from_snapshot(cls, snapshot: ResearchArtifactSnapshot, **limits: int):
        if not isinstance(snapshot, ResearchArtifactSnapshot):
            raise ResearchArtifactRefusal("artifact snapshot type is invalid")
        result = cls(
            owner_id=snapshot.owner_id, licence_scope=snapshot.licence_scope,
            **limits,
        )
        with result._condition:
            for document, payload_bytes in snapshot.entries:
                _verify_artifact(document, payload_bytes)
                if document["owner_id"] != result.owner_id \
                        or document["licence_scope"] != result.licence_scope:
                    raise ResearchArtifactRefusal(
                        "artifact snapshot crosses owner or licence scope"
                    )
                identity = document["identity_address"]
                if identity in result._entries:
                    raise ResearchArtifactRefusal("artifact snapshot duplicates identity")
                result._evict_to_fit(len(payload_bytes))
                result._entries[identity] = _StoredArtifact(
                    _freeze(document), bytes(payload_bytes), result._next_sequence(),
                )
        return result

    def metrics(self) -> Mapping[str, int]:
        with self._condition:
            return MappingProxyType({
                **self._metrics,
                "active": self._active, "queued": self._queued,
                "entries": len(self._entries),
                "cache_bytes": sum(len(item.payload_bytes) for item in self._entries.values()),
            })

    def _require_identity(self, identity: ResearchCacheIdentity) -> ResearchCacheIdentity:
        if type(identity) is not ResearchCacheIdentity:
            raise ResearchArtifactRefusal("canonical research cache identity is required")
        identity._validate()
        if identity.document["owner_id"] != self.owner_id \
                or identity.document["licence_scope"] != self.licence_scope:
            raise ResearchArtifactRefusal("cross-owner or licence cache reuse refused")
        return identity

    def _read_verified(self, identity: ResearchCacheIdentity, stored: _StoredArtifact) -> Any:
        try:
            _verify_artifact(stored.document, stored.payload_bytes)
        except ResearchArtifactRefusal:
            self._entries.pop(identity.identity_address, None)
            self._metrics["corruption_refusals"] += 1
            raise
        return _decode_payload(stored.payload_bytes)

    def _evict_to_fit(self, incoming: int) -> None:
        if incoming > self.cache_bytes_upper_bound:
            raise ResearchArtifactRefusal("research cache byte bound cannot fit artifact")
        while self._entries and (
            len(self._entries) >= self.entry_upper_bound
            or sum(len(item.payload_bytes) for item in self._entries.values()) + incoming
            > self.cache_bytes_upper_bound
        ):
            victim = min(self._entries, key=lambda key: self._entries[key].access_sequence)
            self._entries.pop(victim)
            self._metrics["evictions"] += 1
        if len(self._entries) >= self.entry_upper_bound:
            raise ResearchArtifactRefusal("research cache entry bound exceeded")

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _cost(
        self, identity: ResearchCacheIdentity, category: str,
        *, read_bytes: int = 0, write_bytes: int = 0,
    ) -> ResearchCostRecord:
        document = {
            "schema": "research-cost-record/1",
            "identity_address": identity.identity_address,
            "category": category,
            "read_bytes": read_bytes,
            "write_bytes": write_bytes,
            "compute_units": 1 if category == "COLD_COMPUTE" else 0,
        }
        address = content_address(document)
        return ResearchCostRecord(_freeze(document), address)


def _artifact_document(identity: ResearchCacheIdentity, payload_bytes: bytes) -> dict[str, Any]:
    document = {
        "schema": "research-artifact/1",
        "identity_address": identity.identity_address,
        "owner_id": identity.document["owner_id"],
        "licence_scope": identity.document["licence_scope"],
        "payload_digest": "sha256:" + hashlib.sha256(payload_bytes).hexdigest(),
        "payload_bytes": len(payload_bytes),
    }
    return {**document, "artifact_address": content_address(document)}


def _verify_artifact(document: Mapping[str, Any], payload_bytes: bytes) -> None:
    if not isinstance(document, Mapping) or set(document) != {
        "schema", "identity_address", "owner_id", "licence_scope",
        "payload_digest", "payload_bytes", "artifact_address",
    } or document["schema"] != "research-artifact/1" \
            or not is_content_address(document["identity_address"]) \
            or document["payload_bytes"] != len(payload_bytes) \
            or document["payload_digest"] != "sha256:" + hashlib.sha256(payload_bytes).hexdigest() \
            or document["artifact_address"] != content_address({
                key: _plain(value) for key, value in document.items()
                if key != "artifact_address"
            }):
        raise ResearchArtifactRefusal("research artifact is corrupt or stale")


def _canonical_payload(payload: Any) -> bytes:
    _closed(payload)
    try:
        return json.dumps(
            _plain(payload), sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ResearchArtifactRefusal("research artifact payload is not canonical") from exc


def _decode_payload(payload_bytes: bytes) -> Any:
    try:
        return json.loads(payload_bytes.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResearchArtifactRefusal("research artifact payload cannot decode") from exc


def _address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not is_content_address(value):
        raise ResearchArtifactRefusal(f"{label} must be a content address")
    return value


def _addresses(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not value:
        raise ResearchArtifactRefusal(f"{label} are absent")
    result = tuple(value)
    if result != tuple(sorted(set(result))):
        raise ResearchArtifactRefusal(f"{label} must be sorted and unique")
    for item in result: _address(item, label)
    return result


def _aware(value: Any) -> dt.datetime:
    if not isinstance(value, str):
        raise ResearchArtifactRefusal("research event time is absent")
    try: result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise ResearchArtifactRefusal("research event time is invalid") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ResearchArtifactRefusal("research event time must be aware")
    return result.astimezone(dt.UTC)


def _integer(value: Any, label: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < (1 if positive else 0):
        raise ResearchArtifactRefusal(f"{label} bound is invalid")


def _closed(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)): return
    if isinstance(value, float):
        if math.isfinite(value): return
        raise ResearchArtifactRefusal("research payload contains non-finite value")
    if isinstance(value, (tuple, list)):
        for item in value: _closed(item)
        return
    if isinstance(value, Mapping) and all(isinstance(key, str) and key for key in value):
        for item in value.values(): _closed(item)
        return
    raise ResearchArtifactRefusal("research payload is not closed data")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping): return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (tuple, list)): return tuple(_freeze(item) for item in value)
    return value


__all__ = [
    "BoundedResearchArtifactStore", "IDENTITY_FIELDS", "LICENCE_SCOPES",
    "MaterializedArtifact", "ResearchArtifactRefusal", "ResearchArtifactSnapshot",
    "ResearchCacheIdentity", "ResearchCostRecord", "research_cache_identity",
    "research_cache_identity_document",
]
