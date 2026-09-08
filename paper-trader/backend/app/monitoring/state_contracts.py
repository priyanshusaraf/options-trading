"""Pure monitoring assignment and state facts shared by runtime and persistence."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import re
from typing import Any

from app.ir.hashing import content_address
from app.ir.schema import is_content_address
from app.monitoring.contracts import (
    EntryReference,
    MonitoringContractError,
    ProtectionEvidence,
    StrategyState,
)


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise MonitoringContractError(f"{label.upper()}_IDENTIFIER_REQUIRED")
    return value


def _address(value: Any, label: str) -> str:
    if type(value) is not str or not is_content_address(value):
        raise MonitoringContractError(f"{label.upper()}_CONTENT_ADDRESS_REQUIRED")
    return value


def _utc(value: Any, label: str) -> dt.datetime:
    if type(value) is not dt.datetime or value.tzinfo is not dt.timezone.utc:
        raise MonitoringContractError(f"{label.upper()}_UTC_REQUIRED")
    return value


def _time(value: dt.datetime) -> str:
    return _utc(value, "time").strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_time(value: Any, label: str) -> dt.datetime:
    if type(value) is not str:
        raise MonitoringContractError(f"{label.upper()}_UTC_REQUIRED")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=dt.timezone.utc
        )
    except ValueError as exc:
        raise MonitoringContractError(f"{label.upper()}_UTC_REQUIRED") from exc
    if _time(parsed) != value:
        raise MonitoringContractError(f"{label.upper()}_UTC_REQUIRED")
    return parsed


@dataclass(frozen=True, slots=True)
class MonitoringAssignmentSpec:
    assignment_id: str
    project_id: str
    strategy_id: str
    graph_version_address: str
    resolved_graph_address: str
    registry_address: str
    implementation_closure_address: str
    research_admission_address: str
    static_scope_revision_address: str
    role_binding_address: str
    data_connection_id: int
    capability_profile_address: str
    resource_plan_address: str
    evaluation_trigger_address: str
    state_reset_policy_address: str

    def __post_init__(self) -> None:
        _identifier(self.assignment_id, "assignment")
        _identifier(self.project_id, "project")
        _identifier(self.strategy_id, "strategy")
        for field in self.__dataclass_fields__:
            if field.endswith("_address"):
                _address(getattr(self, field), field)
        if type(self.data_connection_id) is not int or self.data_connection_id < 1:
            raise MonitoringContractError("DATA_ONLY_CONNECTION_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class MonitoringAssignment:
    owner_id: str
    spec: MonitoringAssignmentSpec
    optimistic_revision: int
    lifecycle_state: str
    current_state_snapshot_address: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    withdrawn_at: dt.datetime | None


@dataclass(frozen=True, slots=True)
class MonitoringStateSnapshot:
    owner_id: str
    assignment_id: str
    canonical_instrument_address: str
    snapshot_sequence: int
    predecessor_snapshot_address: str | None
    strategy_state: StrategyState
    entry_reference: EntryReference
    stop_loss: ProtectionEvidence
    take_profit: ProtectionEvidence
    evaluation_event_address: str
    effective_at: dt.datetime

    schema = "monitoring-state-snapshot/1"

    def __post_init__(self) -> None:
        _identifier(self.owner_id, "owner")
        _identifier(self.assignment_id, "assignment")
        _address(self.canonical_instrument_address, "canonical instrument")
        _address(self.evaluation_event_address, "evaluation event")
        if self.predecessor_snapshot_address is not None:
            _address(self.predecessor_snapshot_address, "predecessor snapshot")
        if type(self.snapshot_sequence) is not int or self.snapshot_sequence < 0:
            raise MonitoringContractError("SNAPSHOT_SEQUENCE_NONNEGATIVE_REQUIRED")
        if (self.snapshot_sequence == 0) != (self.predecessor_snapshot_address is None):
            raise MonitoringContractError("SNAPSHOT_PREDECESSOR_SEQUENCE_MISMATCH")
        if type(self.strategy_state) is not StrategyState:
            raise MonitoringContractError("STRATEGY_STATE_CLOSED_VALUE_REQUIRED")
        if type(self.entry_reference) is not EntryReference:
            raise MonitoringContractError("ENTRY_REFERENCE_REQUIRED")
        if type(self.stop_loss) is not ProtectionEvidence \
                or type(self.take_profit) is not ProtectionEvidence:
            raise MonitoringContractError("PROTECTION_EVIDENCE_REQUIRED")
        if self.entry_reference.canonical_instrument_address \
                != self.canonical_instrument_address:
            raise MonitoringContractError("SNAPSHOT_ENTRY_INSTRUMENT_MISMATCH")
        _utc(self.effective_at, "snapshot effective time")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "owner_id": self.owner_id,
            "assignment_id": self.assignment_id,
            "canonical_instrument_address": self.canonical_instrument_address,
            "snapshot_sequence": self.snapshot_sequence,
            "predecessor_snapshot_address": self.predecessor_snapshot_address,
            "strategy_state": self.strategy_state.value,
            "entry_reference": self.entry_reference.to_dict(),
            "stop_loss": self.stop_loss.to_dict(),
            "take_profit": self.take_profit.to_dict(),
            "evaluation_event_address": self.evaluation_event_address,
            "effective_at": _time(self.effective_at),
        }

    @property
    def address(self) -> str:
        return content_address(self.canonical_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_payload(), "address": self.address}

    @classmethod
    def from_dict(cls, value: Any) -> "MonitoringStateSnapshot":
        expected = {
            "schema", "owner_id", "assignment_id", "canonical_instrument_address",
            "snapshot_sequence", "predecessor_snapshot_address", "strategy_state",
            "entry_reference", "stop_loss", "take_profit", "evaluation_event_address",
            "effective_at", "address",
        }
        if type(value) is not dict or set(value) != expected or value.get("schema") != cls.schema:
            raise MonitoringContractError("MONITORING_STATE_SNAPSHOT_SCHEMA")
        try:
            result = cls(
                owner_id=value["owner_id"], assignment_id=value["assignment_id"],
                canonical_instrument_address=value["canonical_instrument_address"],
                snapshot_sequence=value["snapshot_sequence"],
                predecessor_snapshot_address=value["predecessor_snapshot_address"],
                strategy_state=StrategyState(value["strategy_state"]),
                entry_reference=EntryReference.from_dict(value["entry_reference"]),
                stop_loss=ProtectionEvidence.from_dict(value["stop_loss"]),
                take_profit=ProtectionEvidence.from_dict(value["take_profit"]),
                evaluation_event_address=value["evaluation_event_address"],
                effective_at=_parse_time(value["effective_at"], "snapshot effective time"),
            )
        except (KeyError, TypeError, ValueError, MonitoringContractError) as exc:
            raise MonitoringContractError("MONITORING_STATE_SNAPSHOT_INVALID") from exc
        if value["address"] != result.address:
            raise MonitoringContractError("MONITORING_STATE_SNAPSHOT_ADDRESS_MISMATCH")
        return result


__all__ = [
    "MonitoringAssignment", "MonitoringAssignmentSpec", "MonitoringStateSnapshot",
]
