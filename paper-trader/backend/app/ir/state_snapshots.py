"""Canonical research checkpoint creation and fail-closed restore."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import content_address
from app.ir.node_contracts import (
    NodeContractRefusal,
    StateSnapshot,
    canonical_reset_schedule,
    canonical_state_snapshot,
    state_snapshot_document,
)
from app.ir.schema import is_content_address


class ResearchSnapshotRefusal(ValueError):
    pass


@dataclass(frozen=True, init=False)
class ResearchSnapshotAuthority:
    strategy_address: str
    resolved_graph_address: str
    node_contract_address: str
    implementation_closure_address: str
    dataset_context_address: str
    evaluation_context_address: str
    reset_policy_address: str
    creation_evidence_address: str
    initial_state_payload: Any

    def __init__(self, *args, **kwargs) -> None:
        raise ResearchSnapshotRefusal(
            "snapshot authority is minted by the accepted execution boundary"
        )

    def _validate(self) -> None:
        for name in (
            "strategy_address", "resolved_graph_address", "node_contract_address",
            "implementation_closure_address", "dataset_context_address",
            "evaluation_context_address", "reset_policy_address",
            "creation_evidence_address",
        ):
            _address(getattr(self, name), name)
        _closed(self.initial_state_payload)
        object.__setattr__(self, "initial_state_payload", _freeze(self.initial_state_payload))


def _create_research_snapshot_authority(
    *,
    strategy_address: str,
    resolved_graph_address: str,
    node_contract_address: str,
    implementation_closure_address: str,
    dataset_context_address: str,
    evaluation_context_address: str,
    reset_policy_address: str,
    creation_evidence_address: str,
    initial_state_payload: Any,
) -> ResearchSnapshotAuthority:
    result = object.__new__(ResearchSnapshotAuthority)
    for name, value in (
        ("strategy_address", strategy_address),
        ("resolved_graph_address", resolved_graph_address),
        ("node_contract_address", node_contract_address),
        ("implementation_closure_address", implementation_closure_address),
        ("dataset_context_address", dataset_context_address),
        ("evaluation_context_address", evaluation_context_address),
        ("reset_policy_address", reset_policy_address),
        ("creation_evidence_address", creation_evidence_address),
        ("initial_state_payload", initial_state_payload),
    ):
        object.__setattr__(result, name, value)
    result._validate()
    return result


@dataclass(frozen=True, init=False)
class ResearchCheckpoint:
    snapshot: StateSnapshot
    state_payload: Any
    checkpoint_address: str

    def __init__(self, *args, **kwargs) -> None:
        raise ResearchSnapshotRefusal("research checkpoints use create_research_checkpoint")

    def _validate(self) -> None:
        if type(self.snapshot) is not StateSnapshot:
            raise ResearchSnapshotRefusal("canonical StateSnapshot is required")
        try:
            reconstructed = canonical_state_snapshot(self.snapshot.document)
        except NodeContractRefusal as exc:
            raise ResearchSnapshotRefusal("canonical StateSnapshot is required") from exc
        _closed(self.state_payload)
        expected = content_address({
            "schema": "research-checkpoint/1",
            "snapshot_address": reconstructed.snapshot_address,
            "state_payload": _plain(self.state_payload),
        })
        if reconstructed != self.snapshot or expected != self.checkpoint_address \
                or reconstructed.document["state_bytes_digest"] != content_address({
                    "state": _plain(self.state_payload),
                }):
            raise ResearchSnapshotRefusal("research checkpoint identity is stale")


@dataclass(frozen=True)
class RestoredResearchState:
    state_payload: Any
    applied_reset_reasons: tuple[str, ...]
    snapshot_address: str
    next_event_address: str
    next_event_time: str


def create_research_checkpoint(
    authority: ResearchSnapshotAuthority,
    state_payload: Any,
    *,
    last_event_address: str,
    last_event_time: str,
    validity_state: str = "VALID",
    snapshot_reset_reasons: tuple[str, ...] = (),
) -> ResearchCheckpoint:
    if not isinstance(authority, ResearchSnapshotAuthority):
        raise ResearchSnapshotRefusal("research snapshot authority is required")
    authority._validate()
    _closed(state_payload)
    state_payload = _freeze(state_payload)
    _address(last_event_address, "last_event_address")
    _aware(last_event_time, "last_event_time")
    reset = canonical_reset_schedule(snapshot_reset_reasons)
    try:
        document = state_snapshot_document(
            strategy_address=authority.strategy_address,
            resolved_graph_address=authority.resolved_graph_address,
            node_contract_address=authority.node_contract_address,
            implementation_closure_address=authority.implementation_closure_address,
            dataset_context_address=authority.dataset_context_address,
            evaluation_context_address=authority.evaluation_context_address,
            last_event_address=last_event_address,
            last_event_time=last_event_time,
            state_bytes_digest=content_address({"state": _plain(state_payload)}),
            validity_state=validity_state,
            reset_policy_address=authority.reset_policy_address,
            reset_reasons=list(reset),
            creation_evidence_address=authority.creation_evidence_address,
        )
        snapshot = canonical_state_snapshot(document)
    except NodeContractRefusal as exc:
        raise ResearchSnapshotRefusal("research snapshot document is invalid") from exc
    address = content_address({
        "schema": "research-checkpoint/1",
        "snapshot_address": snapshot.snapshot_address,
        "state_payload": _plain(state_payload),
    })
    result = object.__new__(ResearchCheckpoint)
    object.__setattr__(result, "snapshot", snapshot)
    object.__setattr__(result, "state_payload", state_payload)
    object.__setattr__(result, "checkpoint_address", address)
    result._validate()
    return result


def restore_research_checkpoint(
    checkpoint: ResearchCheckpoint,
    authority: ResearchSnapshotAuthority,
    *,
    next_event_address: str,
    next_event_time: str,
    pending_reset_reasons: tuple[str, ...] = (),
) -> RestoredResearchState:
    if not isinstance(checkpoint, ResearchCheckpoint) \
            or not isinstance(authority, ResearchSnapshotAuthority):
        raise ResearchSnapshotRefusal("checkpoint and authority are required")
    authority._validate()
    checkpoint._validate()
    _address(next_event_address, "next_event_address")
    next_time = _aware(next_event_time, "next_event_time")
    document = checkpoint.snapshot.document
    expected = (
        authority.strategy_address, authority.resolved_graph_address,
        authority.node_contract_address, authority.implementation_closure_address,
        authority.dataset_context_address, authority.evaluation_context_address,
        authority.reset_policy_address, authority.creation_evidence_address,
    )
    actual = tuple(document[name] for name in (
        "strategy_address", "resolved_graph_address", "node_contract_address",
        "implementation_closure_address", "dataset_context_address",
        "evaluation_context_address", "reset_policy_address",
        "creation_evidence_address",
    ))
    if actual != expected:
        raise ResearchSnapshotRefusal("checkpoint authority identity differs")
    if document["validity_state"] != "VALID" \
            or _aware(document["last_event_time"], "last_event_time") >= next_time:
        raise ResearchSnapshotRefusal("checkpoint validity or event ordering differs")
    reset = canonical_reset_schedule(pending_reset_reasons)
    state = authority.initial_state_payload if reset else checkpoint.state_payload
    return RestoredResearchState(
        state, reset, checkpoint.snapshot.snapshot_address,
        next_event_address, next_time.isoformat(),
    )


def _address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not is_content_address(value):
        raise ResearchSnapshotRefusal(f"{label} must be a content address")
    return value


def _aware(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ResearchSnapshotRefusal(f"{label} must be an aware timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchSnapshotRefusal(f"{label} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchSnapshotRefusal(f"{label} must be timezone-aware")
    return parsed.astimezone(dt.UTC)


def _closed(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isfinite(value): return
        raise ResearchSnapshotRefusal("state payload contains a non-finite number")
    if isinstance(value, tuple):
        for item in value: _closed(item)
        return
    if isinstance(value, Mapping) and all(isinstance(key, str) and key for key in value):
        for item in value.values(): _closed(item)
        return
    raise ResearchSnapshotRefusal("state payload is not closed data")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


__all__ = [
    "ResearchCheckpoint", "ResearchSnapshotAuthority", "ResearchSnapshotRefusal",
    "RestoredResearchState", "create_research_checkpoint",
    "restore_research_checkpoint",
]
