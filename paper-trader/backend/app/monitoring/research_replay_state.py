"""Pure simulated research replay facts with exact restart state.

These values grant no admission or execution authority. Callers must verify the
consumer identity and source history before using a restored position or decision.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
import math
from typing import ClassVar

from app.engine.decision_kernel import PRECEDENCE
from app.ir.hashing import canonical_json, content_address
from app.monitoring.contracts import MonitoringContractError
from app.monitoring.state_contracts import _address, _identifier, _parse_time, _time, _utc

MAX_STATE_BYTES = 16 * 1024
_POSITION_FIELDS = {"schema", "direction", "entry_price_hex", "entry_open_at", "entry_bar_identity",
                    "entry_sequence", "entry_atr_hex", "ratchet_high_water_hex", "ratchet_stop_hex",
                    "mae_pct_hex"}
_PENDING_FIELDS = {"schema", "kind", "argument", "decision_bar_identity", "decision_completed_at"}
_STATE_FIELDS = {"schema", "owner_id", "assignment_id", "canonical_instrument_address", "consumer_address",
                 "snapshot_sequence", "predecessor_snapshot_address", "last_bar_identity", "last_bar_open_at",
                 "last_bar_completed_at", "position", "pending", "address"}


def _require(condition, message):
    if not condition:
        raise MonitoringContractError(f"RESEARCH_REPLAY_STATE: {message}")


def _bounded(value):
    try:
        size = len(canonical_json(value).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise MonitoringContractError("RESEARCH_REPLAY_STATE: invalid JSON value") from exc
    _require(size <= MAX_STATE_BYTES, "state exceeds 16 KiB")


def _closed(value, fields, schema):
    _require(type(value) is dict and set(value) == fields, "fields must be closed")
    _require(value["schema"] == schema, "schema differs")
    _bounded(value)
    return value


def _sequence(value, *, initial=False):
    _require(type(value) is int and value >= (0 if initial else 1), "invalid sequence")


def _finite_float(value, *, positive=False):
    _require(type(value) is float and math.isfinite(value), "finite float required")
    _require(not positive or value > 0, "positive float required")
    return value


def _float_hex(value):
    return None if value is None else value.hex()


def _from_hex(value, *, optional=False):
    if optional and value is None:
        return None
    _require(type(value) is str and len(value) <= 32, "canonical float hex required")
    try:
        decoded = float.fromhex(value)
    except (ValueError, OverflowError) as exc:
        raise MonitoringContractError("RESEARCH_REPLAY_STATE: invalid float hex") from exc
    _finite_float(decoded)
    _require(decoded.hex() == value, "noncanonical float hex")
    return decoded


def _ratchet_values(position):
    values = (position.entry_atr, position.ratchet_high_water, position.ratchet_stop)
    _require(all(value is None for value in values) or all(value is not None for value in values),
             "ratchet fields must be all present or all absent")
    if position.entry_atr is None:
        return
    _finite_float(position.entry_atr, positive=True)
    _finite_float(position.ratchet_high_water, positive=True)
    _finite_float(position.ratchet_stop)
    favorable = (position.ratchet_high_water >= position.entry_price if position.direction == "LONG"
                 else position.ratchet_high_water <= position.entry_price)
    _require(favorable, "ratchet high-water precedes entry in the favorable direction")


@dataclass(frozen=True, slots=True)
class ResearchReplayPosition:
    direction: str
    entry_price: float
    entry_open_at: dt.datetime
    entry_bar_identity: str
    entry_sequence: int
    entry_atr: float | None = None
    ratchet_high_water: float | None = None
    ratchet_stop: float | None = None
    mae_pct: float = 0.0

    schema: ClassVar[str] = "research-replay-position/1"

    def __post_init__(self):
        _require(type(self.direction) is str and self.direction in ("LONG", "SHORT"), "direction must be LONG or SHORT")
        _finite_float(self.entry_price, positive=True)
        _utc(self.entry_open_at, "entry open")
        _address(self.entry_bar_identity, "entry bar")
        _sequence(self.entry_sequence)
        _ratchet_values(self)
        _finite_float(self.mae_pct)
        _require(self.mae_pct >= 0, "adverse excursion must be nonnegative")

    def to_dict(self):
        return {"schema": self.schema, "direction": self.direction,
                "entry_price_hex": self.entry_price.hex(), "entry_open_at": _time(self.entry_open_at),
                "entry_bar_identity": self.entry_bar_identity, "entry_sequence": self.entry_sequence,
                "entry_atr_hex": _float_hex(self.entry_atr),
                "ratchet_high_water_hex": _float_hex(self.ratchet_high_water),
                "ratchet_stop_hex": _float_hex(self.ratchet_stop), "mae_pct_hex": self.mae_pct.hex()}

    @classmethod
    def from_dict(cls, value):
        _closed(value, _POSITION_FIELDS, cls.schema)
        return cls(direction=value["direction"], entry_price=_from_hex(value["entry_price_hex"]),
            entry_open_at=_parse_time(value["entry_open_at"], "entry open"),
            entry_bar_identity=value["entry_bar_identity"], entry_sequence=value["entry_sequence"],
            entry_atr=_from_hex(value["entry_atr_hex"], optional=True),
            ratchet_high_water=_from_hex(value["ratchet_high_water_hex"], optional=True),
            ratchet_stop=_from_hex(value["ratchet_stop_hex"], optional=True),
            mae_pct=_from_hex(value["mae_pct_hex"]))


@dataclass(frozen=True, slots=True)
class ResearchPendingDecision:
    kind: str
    argument: str
    decision_bar_identity: str
    decision_completed_at: dt.datetime

    schema: ClassVar[str] = "research-pending-decision/1"

    def __post_init__(self):
        _require(type(self.kind) is str and self.kind in ("ENTER", "EXIT", "REVERSE"), "unsupported pending decision")
        choices = PRECEDENCE if self.kind == "EXIT" else ("LONG", "SHORT")
        _require(type(self.argument) is str and self.argument in choices, "unsupported pending argument")
        _address(self.decision_bar_identity, "decision bar")
        _utc(self.decision_completed_at, "decision completed")

    def to_dict(self):
        return {"schema": self.schema, "kind": self.kind, "argument": self.argument,
                "decision_bar_identity": self.decision_bar_identity,
                "decision_completed_at": _time(self.decision_completed_at)}

    @classmethod
    def from_dict(cls, value):
        _closed(value, _PENDING_FIELDS, cls.schema)
        return cls(value["kind"], value["argument"], value["decision_bar_identity"],
                   _parse_time(value["decision_completed_at"], "decision completed"))


def _state_clocks(state):
    if state.snapshot_sequence == 0:
        _require(all(value is None for value in (state.predecessor_snapshot_address, state.last_bar_identity,
            state.last_bar_open_at, state.last_bar_completed_at, state.position, state.pending)),
            "initial state must be empty")
        return
    _address(state.predecessor_snapshot_address, "predecessor snapshot")
    _address(state.last_bar_identity, "last bar")
    opened = _utc(state.last_bar_open_at, "last bar open")
    completed = _utc(state.last_bar_completed_at, "last bar completed")
    _require(opened < completed, "last bar completion must follow its open")


def _position_relationship(state):
    position = state.position
    if position is None:
        return
    _require(type(position) is ResearchReplayPosition, "closed position required")
    position.__post_init__()
    _require(position.entry_sequence <= state.snapshot_sequence, "entry sequence exceeds state sequence")
    _require(position.entry_open_at <= state.last_bar_open_at, "entry open exceeds last bar open")


def _pending_relationship(state):
    pending = state.pending
    if pending is None:
        return
    _require(type(pending) is ResearchPendingDecision, "closed pending decision required")
    pending.__post_init__()
    _require((pending.decision_bar_identity, pending.decision_completed_at)
             == (state.last_bar_identity, state.last_bar_completed_at), "pending decision must belong to last bar")
    _require((state.position is not None) == (pending.kind != "ENTER"), "pending decision differs from held state")
    if pending.kind == "REVERSE":
        _require(pending.argument != state.position.direction, "reversal must change direction")


@dataclass(frozen=True, slots=True)
class ResearchReplayState:
    owner_id: str
    assignment_id: str
    canonical_instrument_address: str
    consumer_address: str
    snapshot_sequence: int
    predecessor_snapshot_address: str | None = None
    last_bar_identity: str | None = None
    last_bar_open_at: dt.datetime | None = None
    last_bar_completed_at: dt.datetime | None = None
    position: ResearchReplayPosition | None = None
    pending: ResearchPendingDecision | None = None

    schema: ClassVar[str] = "research-replay-state/1"

    def __post_init__(self):
        _identifier(self.owner_id, "owner")
        _identifier(self.assignment_id, "assignment")
        _address(self.canonical_instrument_address, "canonical instrument")
        _address(self.consumer_address, "consumer")
        _sequence(self.snapshot_sequence, initial=True)
        _state_clocks(self)
        _position_relationship(self)
        _pending_relationship(self)

    def canonical_payload(self):
        return {"schema": self.schema, "owner_id": self.owner_id, "assignment_id": self.assignment_id,
            "canonical_instrument_address": self.canonical_instrument_address, "consumer_address": self.consumer_address,
            "snapshot_sequence": self.snapshot_sequence, "predecessor_snapshot_address": self.predecessor_snapshot_address,
            "last_bar_identity": self.last_bar_identity,
            "last_bar_open_at": None if self.last_bar_open_at is None else _time(self.last_bar_open_at),
            "last_bar_completed_at": None if self.last_bar_completed_at is None else _time(self.last_bar_completed_at),
            "position": None if self.position is None else self.position.to_dict(),
            "pending": None if self.pending is None else self.pending.to_dict()}

    @property
    def address(self):
        return content_address(self.canonical_payload())

    def to_dict(self):
        payload = {**self.canonical_payload(), "address": self.address}
        _bounded(payload)
        return payload

    @classmethod
    def from_dict(cls, value):
        _closed(value, _STATE_FIELDS, cls.schema)
        _address(value["address"], "snapshot")
        state = cls(**_state_arguments(value))
        _require(state.address == value["address"], "snapshot address differs")
        return state

    @classmethod
    def from_json(cls, payload: bytes | str):
        return cls.from_dict(_state_json(payload))


def _state_arguments(value):
    names = ("owner_id", "assignment_id", "canonical_instrument_address", "consumer_address", "snapshot_sequence",
             "predecessor_snapshot_address", "last_bar_identity")
    result = {name: value[name] for name in names}
    for name in ("last_bar_open_at", "last_bar_completed_at"):
        result[name] = None if value[name] is None else _parse_time(value[name], name)
    result["position"] = None if value["position"] is None else ResearchReplayPosition.from_dict(value["position"])
    result["pending"] = None if value["pending"] is None else ResearchPendingDecision.from_dict(value["pending"])
    return result


def _unique_json(pairs):
    result = dict(pairs)
    _require(len(result) == len(pairs), "duplicate JSON keys")
    return result


def _reject_constant(_value):
    raise MonitoringContractError("RESEARCH_REPLAY_STATE: non-finite JSON constant")


def _state_json(payload):
    _require(type(payload) in (bytes, str), "JSON bytes or text required")
    try:
        encoded = payload.encode("utf-8") if type(payload) is str else payload
        _require(0 < len(encoded) <= MAX_STATE_BYTES, "state exceeds 16 KiB or is empty")
        return json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_json, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise MonitoringContractError("RESEARCH_REPLAY_STATE: invalid bounded JSON") from exc


def restore_ratchet(position: ResearchReplayPosition, risk_model):
    """Restore held ratchet values exactly; the caller verifies the risk policy identity."""
    from app.backtest.ratchet import RatchetState
    from app.strategy.ir_adapter import InvalidRiskModel, validate_risk_model
    _require(type(position) is ResearchReplayPosition, "closed held position required")
    position.__post_init__()
    try:
        model = validate_risk_model(risk_model, "research replay")
    except (InvalidRiskModel, ValueError, TypeError, OverflowError) as exc:
        raise MonitoringContractError("RESEARCH_REPLAY_STATE: invalid risk policy") from exc
    _require((model is not None) == (position.entry_atr is not None), "risk policy and retained ratchet fields differ")
    if model is None:
        return None
    _require(all(math.isfinite(value) for key, value in model.items() if key != "use_mfe_capture_floor"),
             "risk policy contains non-finite values")
    restored = RatchetState.restore(position.direction, position.entry_price, position.entry_atr, model,
                                   hw=position.ratchet_high_water, stop=position.ratchet_stop)
    _finite_float(restored.risk_pts, positive=True)
    return restored
