"""A completed V2 research result behind the established Strategy contract.

This adapter assigns trade meaning only to the reviewed graph-output roles. It is
dataset-bound and read-only: V2 evaluation, data loading, fills, charges, sizing,
authority, persistence, and lifecycle work stay with their existing owners.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

import pandas as pd

from app.ir.hashing import content_address
from app.engine.decision_kernel import protective_band_document
from app.ir.validity import NumericValue, ValidityState
from app.strategy.registry.base import CANONICAL_COLUMNS, Strategy
from research.evaluation.phase5_runtime import ResearchRunResult


class V2SignalAdapterRefusal(ValueError):
    """The evaluated outputs cannot safely represent research trade signals."""


class _FrozenDict(dict):
    """JSON-serializable mapping that rejects mutation."""

    def _immutable(self, *args, **kwargs):
        raise TypeError("mapping is immutable")

    __delitem__ = _immutable
    __ior__ = _immutable
    __setitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


ADAPTER_POLICY_DOCUMENT = _freeze({
    "schema": "v2-research-signal-adapter-policy/1",
    "algorithm_version": 1,
    "accepted_role_sets": [
        ["research_long_entry", "research_long_exit"],
        ["research_short_entry", "research_short_exit"],
        ["research_long_entry", "research_short_entry", "research_long_exit",
         "research_short_exit"],
    ],
    "descriptor": {
        "direction": "output",
        "semantic_flow": "value",
        "type_ref": {"type_id": "analytical.boolean", "type_version": 2},
        "shape": "series",
    },
    "warmup_policy": "max-leading-insufficient-history-suppress-all/1",
    "hold_policy": "all-four-false/1",
    "simultaneous_policy": "refuse-more-than-one-true/1",
    "parameter_override_policy": "refuse/1",
})
ADAPTER_POLICY_ADDRESS = "sha256:e35daffd61c1bacb3b51a4384cafaac71f7637b029a541189060a1d6ff7e0ca1"


# Version 1 remains the default for existing operations. Version 2 preserves
# directional predicates: an entry may accompany the opposite position's exit.
# Existing execution code decides whether that exit applies to a held position.
DIRECTIONAL_ADAPTER_POLICY_DOCUMENT = _freeze({
    **ADAPTER_POLICY_DOCUMENT,
    "algorithm_version": 2,
    "simultaneous_policy": "allow-opposite-exits-refuse-entry-conflicts/1",
})
DIRECTIONAL_ADAPTER_POLICY_ADDRESS = "sha256:9c8e2359ab971e55649bbffe6ed5d3c41a239b3c0b41786ac7cbe9950a3cd9dc"


def _adapter_policy(address: str):
    policies = {
        ADAPTER_POLICY_ADDRESS: ADAPTER_POLICY_DOCUMENT,
        DIRECTIONAL_ADAPTER_POLICY_ADDRESS: DIRECTIONAL_ADAPTER_POLICY_DOCUMENT,
    }
    try:
        policy = policies[address]
    except (KeyError, TypeError):
        raise V2SignalAdapterRefusal("signal adapter policy is unsupported") from None
    if content_address(policy) != address:
        raise V2SignalAdapterRefusal("adapter policy document address is stale")
    return policy


_PINE_V4_RISK_MODEL = {
    "atr_length": 14, "initial_risk_atr": 1.25,
    "trail_start_r": 1.75, "trail_atr": 3.0,
    "use_mfe_capture_floor": True, "capture_start_r": 1.25,
    "capture_pct": 0.35,
}
_RISK_POLICIES = _freeze({
    "none": {
        "schema": "v2-research-risk-policy/1", "policy_id": "none",
        "risk_model": None, "atr_seed_policy": "first_observation",
    },
    "pine-v4-ratchet/1": {
        "schema": "v2-research-risk-policy/1", "policy_id": "pine-v4-ratchet/1",
        "risk_model": _PINE_V4_RISK_MODEL,
        "atr_seed_policy": "sma",
        "management": "close-confirmed-after-fill/1",
        "warmup": "require-atr-seed-before-entries/1",
    },
    "pine-v4-reversal/1": {
        "schema": "v2-research-risk-policy/2", "policy_id": "pine-v4-reversal/1",
        "risk_model": _PINE_V4_RISK_MODEL, "atr_seed_policy": "sma",
        "management": "close-confirmed-after-fill/1",
        "warmup": "require-atr-seed-before-entries/1",
        "replay_policy": "pine-reversal-fixed-unit/1",
    },
})


def risk_policy_document(name: str) -> Mapping[str, Any]:
    """Return one closed research overlay; no strategy metadata selects it."""
    try:
        return _RISK_POLICIES[name]
    except (KeyError, TypeError):
        raise V2SignalAdapterRefusal("research risk policy is unsupported") from None


def _risk_binding(name: str, adapter_policy: str):
    if name != "none" and adapter_policy == ADAPTER_POLICY_ADDRESS:
        raise V2SignalAdapterRefusal("risk overlay requires the directional adapter policy")
    document = risk_policy_document(name)
    return document, content_address(document)



def _risk_warmup(warmup: int, risk_document, events: int) -> int:
    model = risk_document["risk_model"]
    if model is None:
        return warmup
    required = max(warmup, int(model["atr_length"]) - 1)
    if required >= events:
        raise V2SignalAdapterRefusal("risk policy needs more completed bars to seed ATR")
    return required


_ROLE_TO_COLUMN = MappingProxyType({
    "research_long_entry": "longEntry",
    "research_short_entry": "shortEntry",
    "research_long_exit": "longExit",
    "research_short_exit": "shortExit",
})
_ACCEPTED_ROLE_SETS = frozenset(
    frozenset(role_set) for role_set in ADAPTER_POLICY_DOCUMENT["accepted_role_sets"]
)
_EXPECTED_DESCRIPTOR = ADAPTER_POLICY_DOCUMENT["descriptor"]


def _event_index(value: Any, label: str) -> pd.DatetimeIndex:
    if not isinstance(value, pd.DatetimeIndex):
        raise V2SignalAdapterRefusal(f"{label} must be a pandas DatetimeIndex")
    if value.empty:
        raise V2SignalAdapterRefusal(f"{label} must not be empty")
    if value.tz is None:
        raise V2SignalAdapterRefusal(f"{label} must be timezone-aware")
    if not value.is_monotonic_increasing:
        raise V2SignalAdapterRefusal(f"{label} must be monotonic increasing")
    if not value.is_unique:
        raise V2SignalAdapterRefusal(f"{label} must be unique")
    return value.copy()


def _same_index(left: pd.DatetimeIndex, right: pd.DatetimeIndex) -> bool:
    return (
        len(left) == len(right)
        and all(
            left_item == right_item
            and left_item.utcoffset() == right_item.utcoffset()
            for left_item, right_item in zip(left, right)
        )
    )


def _graph_outputs(document: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    outputs = document.get("graph_outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)) or not outputs:
        raise V2SignalAdapterRefusal("graph output role set is absent")
    if any(not isinstance(item, Mapping) for item in outputs):
        raise V2SignalAdapterRefusal("graph output descriptors must be mappings")
    return tuple(outputs)


def _validate_descriptor(role: str, descriptor: Mapping[str, Any]) -> None:
    for field in ("direction", "semantic_flow", "shape"):
        if descriptor.get(field) != _EXPECTED_DESCRIPTOR[field]:
            raise V2SignalAdapterRefusal(
                f"graph output {role!r} {field} does not match adapter policy"
            )
    if descriptor.get("type_ref") != _EXPECTED_DESCRIPTOR["type_ref"]:
        raise V2SignalAdapterRefusal(
            f"graph output {role!r} type_ref does not match adapter policy"
        )


def _role_mapping(document: Mapping[str, Any]) -> dict[str, str]:
    outputs = _graph_outputs(document)
    roles: list[str] = []
    ports: list[str] = []
    for number, descriptor in enumerate(outputs):
        role = descriptor.get("semantic_role")
        port = descriptor.get("port_id")
        if not isinstance(role, str) or not role:
            raise V2SignalAdapterRefusal(
                f"graph output {number} semantic role must be a non-empty string"
            )
        if not isinstance(port, str) or not port:
            raise V2SignalAdapterRefusal(
                f"graph output {number} port_id must be a non-empty string"
            )
        roles.append(role)
        ports.append(port)
        _validate_descriptor(role, descriptor)
    if len(set(roles)) != len(roles):
        raise V2SignalAdapterRefusal("graph output semantic roles must be unique")
    if len(set(ports)) != len(ports):
        raise V2SignalAdapterRefusal("graph output port_ids must be unique")
    if frozenset(roles) not in _ACCEPTED_ROLE_SETS:
        raise V2SignalAdapterRefusal(
            f"graph output role set is unsupported: {sorted(roles)!r}"
        )
    return dict(zip(roles, ports, strict=True))


def _unwrap_series(
    role: str,
    value: Any,
    verified_index: pd.DatetimeIndex,
) -> tuple[list[bool], int]:
    if not isinstance(value, pd.Series):
        raise V2SignalAdapterRefusal(f"output role {role!r} must be a pandas Series")
    if not isinstance(value.index, pd.DatetimeIndex):
        raise V2SignalAdapterRefusal(f"output role {role!r} index must be a DatetimeIndex")
    output_index = _event_index(value.index, f"output role {role!r} index")
    if not _same_index(output_index, verified_index):
        raise V2SignalAdapterRefusal(
            f"output role {role!r} index differs from the verified event index"
        )

    flags: list[bool] = []
    warmup = 0
    settled = False
    for position, cell in enumerate(value.tolist()):
        if not isinstance(cell, NumericValue):
            raise V2SignalAdapterRefusal(
                f"output role {role!r} cell {position} must use NumericValue"
            )
        if cell.state is ValidityState.VALID:
            settled = True
            if type(cell.value) is not bool:
                raise V2SignalAdapterRefusal(
                    f"output role {role!r} VALID cell {position} must carry an exact bool"
                )
            flags.append(cell.value)
            continue
        if settled:
            raise V2SignalAdapterRefusal(
                f"output role {role!r} has invalidity after settlement at cell {position}"
            )
        if cell.state is not ValidityState.INSUFFICIENT_HISTORY:
            raise V2SignalAdapterRefusal(
                f"output role {role!r} before settlement must be INSUFFICIENT_HISTORY"
            )
        warmup += 1
        flags.append(False)
    if not settled:
        raise V2SignalAdapterRefusal(f"output role {role!r} never settles to VALID")
    return flags, warmup


def _suppress_before_global_warmup(
    columns: dict[str, list[bool]], declared_warmup: int,
) -> None:
    for column in CANONICAL_COLUMNS:
        columns[column][:declared_warmup] = [False] * declared_warmup


def _refuse_simultaneous(
    columns: Mapping[str, Sequence[bool]], declared_warmup: int, events: int,
) -> None:
    for position in range(declared_warmup, events):
        if sum(columns[column][position] for column in CANONICAL_COLUMNS) > 1:
            raise V2SignalAdapterRefusal(
                f"simultaneous signal flags refuse at event position {position}"
            )


def _refuse_directional_conflicts(columns, declared_warmup: int, events: int) -> None:
    conflicts = (("longEntry", "shortEntry"), ("longEntry", "longExit"),
                 ("shortEntry", "shortExit"))
    for position in range(declared_warmup, events):
        if any(columns[left][position] and columns[right][position]
               for left, right in conflicts):
            raise V2SignalAdapterRefusal(
                f"conflicting directional signal flags at event position {position}"
            )


def _verify_result(document, result) -> None:
    if not isinstance(document, Mapping):
        raise V2SignalAdapterRefusal("immutable V2 document must be a mapping")
    if document.get("format_version") != 2:
        raise V2SignalAdapterRefusal("adapter requires a V2 document")
    if not isinstance(result, ResearchRunResult):
        raise V2SignalAdapterRefusal("adapter requires a ResearchRunResult")
    if result.document.get("status") != "COMPLETED":
        raise V2SignalAdapterRefusal("adapter requires a COMPLETED ResearchRunResult")


def research_signal_columns(document, outputs, event_index, *, policy_address, risk_policy):
    """Map evaluated boolean outputs without manufacturing a research-run receipt.

    This checks roles, validity, clocks, warmup and directional conflicts. The
    caller separately verifies graph evaluation and its input authority.
    """
    if not isinstance(document, Mapping) or document.get("format_version") != 2:
        raise V2SignalAdapterRefusal("signal columns require a V2 document")
    _adapter_policy(policy_address)
    risk_document, _ = _risk_binding(risk_policy, policy_address)
    event_index = _event_index(event_index, "verified event index")
    role_to_port = _role_mapping(document)
    if set(outputs) != set(role_to_port.values()):
        raise V2SignalAdapterRefusal("evaluated output ports differ from graph output ports")
    columns = {column: [False] * len(event_index) for column in CANONICAL_COLUMNS}
    warmups = []
    for role, port in role_to_port.items():
        flags, warmup = _unwrap_series(role, outputs[port], event_index)
        columns[_ROLE_TO_COLUMN[role]] = flags
        warmups.append(warmup)
    declared_warmup = _risk_warmup(max(warmups), risk_document, len(event_index))
    _suppress_before_global_warmup(columns, declared_warmup)
    if policy_address == ADAPTER_POLICY_ADDRESS:
        _refuse_simultaneous(columns, declared_warmup, len(event_index))
    else:
        _refuse_directional_conflicts(columns, declared_warmup, len(event_index))
    return role_to_port, columns, declared_warmup


class V2RuntimeStrategy(Strategy):
    """Read-only mapping of one completed V2 result to four boolean columns."""

    default_params: dict[str, Any] = {}
    risk_model = None

    def __init__(
        self,
        document: Mapping[str, Any],
        result: ResearchRunResult,
        verified_event_index: pd.DatetimeIndex,
        *, policy_address: str = ADAPTER_POLICY_ADDRESS, risk_policy: str = "none",
        stop_loss_pct: float | None = None, take_profit_pct: float | None = None,
    ) -> None:
        band = protective_band_document(stop_loss_pct, take_profit_pct)
        _verify_result(document, result)
        policy = _adapter_policy(policy_address)
        risk_document, risk_address = _risk_binding(risk_policy, policy_address)

        event_index = _event_index(verified_event_index, "verified event index")
        role_to_port, columns, declared_warmup = research_signal_columns(
            document, result.batch_outputs, event_index,
            policy_address=policy_address, risk_policy=risk_policy)

        self.key = f"v2.research.{result.result_address.split(':', 1)[-1][:12]}"
        self.display_name = str(document.get("strategy_id") or "V2 research strategy")
        self.declared_warmup = declared_warmup
        self.adapter_policy_address = policy_address
        self.adapter_policy_document = policy
        self.protective_band_document = _freeze(band)
        self.replay_policy = risk_document.get("replay_policy")
        self.risk_model = risk_document["risk_model"]
        self.risk_atr_seed_policy = risk_document["atr_seed_policy"]
        self.risk_policy_document = risk_document
        self.risk_policy_address = risk_address
        self.role_to_port = _freeze(dict(sorted(role_to_port.items())))
        self._event_index = event_index
        self._columns = MappingProxyType({
            column: tuple(columns[column]) for column in CANONICAL_COLUMNS
        })
        provenance = {
            "schema": "v2-research-signal-adapter-provenance/1",
            "adapter_policy_address": policy_address,
            "adapter_policy_document": policy,
            "research_result_address": result.result_address,
            "research_output_digest": result.document["output_digest"],
            "role_to_port": self.role_to_port,
            "declared_warmup": declared_warmup,
        }
        if policy_address != ADAPTER_POLICY_ADDRESS:
            provenance.update(risk_policy_document=risk_document, risk_policy_address=risk_address)
        if band is not None:
            provenance["protective_band_document"] = self.protective_band_document
        adapter_address = content_address(provenance)
        self.adapter_address = adapter_address
        self.provenance_document = _freeze({**provenance, "adapter_address": adapter_address})
        self.pin_version(adapter_address)

    def signals(self, df: pd.DataFrame, **overrides: Any) -> pd.DataFrame:
        if overrides:
            raise V2SignalAdapterRefusal("parameter overrides are not accepted")
        return self.compute(df)

    def compute(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        if params:
            raise V2SignalAdapterRefusal("parameter overrides are not accepted")
        if not isinstance(df, pd.DataFrame):
            raise V2SignalAdapterRefusal("signal input must be a pandas DataFrame")
        frame_index = pd.DatetimeIndex(df["date"]) if "date" in df.columns else df.index
        if not isinstance(frame_index, pd.DatetimeIndex) \
                or not _same_index(frame_index, self._event_index):
            raise V2SignalAdapterRefusal(
                "signal frame differs from the verified event index"
            )
        output = df.copy(deep=True)
        for column in CANONICAL_COLUMNS:
            output[column] = list(self._columns[column])
        return output


__all__ = [
    "ADAPTER_POLICY_ADDRESS", "ADAPTER_POLICY_DOCUMENT", "V2RuntimeStrategy",
    "V2SignalAdapterRefusal", "DIRECTIONAL_ADAPTER_POLICY_ADDRESS",
    "DIRECTIONAL_ADAPTER_POLICY_DOCUMENT", "risk_policy_document",
]
