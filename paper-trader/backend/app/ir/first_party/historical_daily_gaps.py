"""Full completed-session gaps, separate from opening-price GAP_UP/GAP_DOWN.

Inputs are complete daily session bars from one pinned canonical source, indexed
at or after the canonical session close. Intraday/forming sessions refuse. A gap's
original geometry never moves. Reaches are observations, not execution fills.
The existing Component IR runtime evaluates this batch/prefix kernel; GapState is
its bounded mathematical state and restores under the same bound contract.
"""
from __future__ import annotations

import collections.abc as abc
import dataclasses
import math

import pandas as pd

from app.ir import hashing, node_contracts, registry, validity
from app.ir.first_party.analytical_v2 import common, contracts

KEY = ("structure.historical_daily_gaps", 2)
MAX_ZONES = 4096
_FIELDS = {"frame": ("CLOSE", "HIGH", "LOW"),
           "session": ("SESSION_CLOSE_AT", "SESSION_ID", "SESSION_OPEN_AT")}
_OUTPUTS = tuple(f"{side}_{field}" for side in ("bearish", "bullish")
                 for field in ("distal", "formed_at", "proximal", "still_open"))
_POLICY = {
    "schema": "historical-daily-gap-policy/1", "maximum_zones": MAX_ZONES,
    "formation": "completed-session-low-above-prior-high-or-high-below-prior-low",
    "geometry": "immutable-original-edges", "reach": "inclusive-proximal-partial-distal-filled",
    "selection": "nearest-unresolved-on-price-side-then-oldest-formation-then-zone-id",
    "history": "complete-canonical-session-sequence-invalidity-poisons-unresolved-history",
    "expiry": "none", "execution_fills": "not-modelled",
}


def _refuse(condition, code):
    if not condition:
        raise node_contracts.NodeContractRefusal(code)


def _time(value):
    try:
        result = pd.Timestamp(value)
        _refuse(not pd.isna(result) and result.tzinfo is not None, "GAP_CANONICAL_TIME_REQUIRED")
        return result.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError) as exc:
        raise node_contracts.NodeContractRefusal("GAP_CANONICAL_TIME_REQUIRED") from exc


def _session(inputs, event_time):
    _refuse(isinstance(inputs, abc.Mapping) and set(inputs) == set(_FIELDS), "GAP_INPUT_PORTS")
    context = inputs["session"]
    _refuse(isinstance(context, abc.Mapping), "GAP_SESSION_CONTEXT_REQUIRED")
    _refuse(set(context) >= {field.lower() for field in _FIELDS["session"]}, "GAP_SESSION_FIELDS_REQUIRED")
    identifier = context["session_id"]
    _refuse(isinstance(identifier, str) and 0 < len(identifier) <= 128, "GAP_SESSION_ID_REQUIRED")
    opening, closing = _time(context["session_open_at"]), _time(context["session_close_at"])
    _refuse(opening < closing and event_time >= closing, "GAP_COMPLETE_SESSION_REQUIRED")
    return {"session_id": identifier, "session_open_at": opening.isoformat(),
            "session_close_at": closing.isoformat()}


def _prices(frame):
    cells = {name: common.required_numeric_scalar(frame, name) for name in ("high", "low", "close")}
    fault = validity.propagate(cells.values())
    if fault is not None:
        return cells, fault
    values = {name: float(cell.value) for name, cell in cells.items()}
    if not 0 < values["low"] <= values["close"] <= values["high"]:
        return cells, validity.invalid(validity.ValidityState.INVALID)
    return values, None


def _cell_document(cell):
    return {"state": cell.state.value, "value": cell.value,
            "causes": [cause.value for cause in cell.causes]}


def _read_cell(value):
    _refuse(isinstance(value, abc.Mapping) and set(value) == {"state", "value", "causes"},
            "GAP_STATE_VALIDITY_REQUIRED")
    return validity.NumericValue(validity.ValidityState(value["state"]), value["value"],
                                 tuple(validity.ValidityState(item) for item in value["causes"]))


def _event_address(session, prices, fault):
    facts = ({name: _cell_document(cell) for name, cell in prices.items()} if fault is not None else prices)
    return hashing.content_address({"session": session, "prices": facts})


@dataclasses.dataclass(frozen=True)
class GapZone:
    zone_id: str
    direction: str
    lower: float
    upper: float
    formed_at: str
    session_id: str
    status: str = "OPEN"
    touched_at: str | None = None
    filled_at: str | None = None

    def __post_init__(self):
        _validate_zone_geometry(self)
        _validate_zone_status(self)

    @property
    def proximal(self):
        return self.upper if self.direction == "BULLISH" else self.lower

    @property
    def distal(self):
        return self.lower if self.direction == "BULLISH" else self.upper


def _zone_identity(direction, lower, upper, session):
    return {"schema": "historical-daily-gap-zone/1", "direction": direction,
            "lower": lower, "upper": upper, "formed_at": session["session_close_at"],
            "session_id": session["session_id"]}


def _positive_price(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _validate_zone_geometry(zone):
    _refuse(zone.direction in {"BULLISH", "BEARISH"}, "GAP_ZONE_DIRECTION")
    _refuse(_positive_price(zone.lower) and _positive_price(zone.upper) and zone.lower < zone.upper,
            "GAP_ZONE_GEOMETRY")
    session = {"session_close_at": zone.formed_at, "session_id": zone.session_id}
    _refuse(_time(zone.formed_at).isoformat() == zone.formed_at, "GAP_ZONE_FORMATION_TIME")
    _refuse(zone.zone_id == hashing.content_address(_zone_identity(zone.direction, zone.lower, zone.upper, session)),
            "GAP_ZONE_IDENTITY")


def _validate_zone_status(zone):
    states = {"OPEN": (False, False), "PARTIAL": (True, False), "FILLED": (True, True)}
    _refuse(zone.status in states and (zone.touched_at is not None, zone.filled_at is not None) == states[zone.status],
            "GAP_ZONE_STATUS")
    previous = _time(zone.formed_at)
    for moment in (zone.touched_at, zone.filled_at):
        if moment is not None:
            current = _time(moment)
            _refuse(current.isoformat() == moment and current >= previous and current > _time(zone.formed_at), "GAP_ZONE_REACH_TIME")
            previous = current


def _new_zone(previous, prices, session):
    if prices["low"] > previous["high"]:
        direction, lower, upper = "BULLISH", previous["high"], prices["low"]
    elif prices["high"] < previous["low"]:
        direction, lower, upper = "BEARISH", prices["high"], previous["low"]
    else:
        return None
    identity = _zone_identity(direction, lower, upper, session)
    return GapZone(hashing.content_address(identity), direction, lower, upper,
                   session["session_close_at"], session["session_id"])


def _reached(zone, prices, level):
    return prices["low"] <= level if zone.direction == "BULLISH" else prices["high"] >= level


def _observe_zone(zone, prices, when):
    if zone.status == "FILLED" or not _reached(zone, prices, zone.proximal):
        return zone
    filled = _reached(zone, prices, zone.distal)
    return dataclasses.replace(zone, status="FILLED" if filled else "PARTIAL",
        touched_at=zone.touched_at or when, filled_at=when if filled else None)


def _nearest(zones, direction, close):
    candidates = [zone for zone in zones if zone.direction == direction and zone.status != "FILLED"
                  and (zone.proximal <= close if direction == "BULLISH" else zone.proximal >= close)]
    return min(candidates, key=lambda zone: (abs(close - zone.proximal), zone.formed_at, zone.zone_id), default=None)


def _zone_outputs(zone, missing):
    if zone is None:
        return {"distal": missing, "formed_at": missing, "proximal": missing,
                "still_open": validity.valid(False)}
    return {"distal": validity.valid(zone.distal), "proximal": validity.valid(zone.proximal),
            "formed_at": validity.valid(float(_time(zone.formed_at).timestamp())),
            "still_open": validity.valid(zone.status == "OPEN")}


def _outputs(zones, close, count, fault):
    if fault is not None:
        return {port: fault for port in _OUTPUTS}
    missing = validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY if count < 2
                               else validity.ValidityState.MISSING)
    return {f"{side}_{port}": value for side in ("bearish", "bullish")
            for port, value in _zone_outputs(_nearest(zones, side.upper(), close), missing).items()}


class GapState:
    """Bounded registry state; no process-global registry, clock, broker or I/O."""

    def __init__(self, bound_contract):
        _check_bound(bound_contract)
        self.bound_contract = bound_contract
        self.zones = ()
        self.previous = None
        self.last_time = None
        self.last_event_address = None
        self.fault = None
        self.count = 0
        self.close = 0.0  # no executable output exists before a completed observation

    def _check_event(self, session, timestamp, event_address):
        if timestamp == self.last_time:
            _refuse(event_address == self.last_event_address, "GAP_DUPLICATE_EVENT_CONFLICT")
            return False
        _refuse(self.last_time is None or timestamp > self.last_time, "GAP_EVENT_ORDER")
        if self.previous is not None:
            _refuse(session["session_id"] != self.previous["session_id"], "GAP_SESSION_ALREADY_FINALISED")
            _refuse(_time(session["session_open_at"]) > _time(self.previous["session_close_at"]), "GAP_SESSION_OVERLAP")
        return True

    def _advance(self, prices, session):
        when = session["session_close_at"]
        zone = _new_zone(self.previous, prices, session) if self.previous is not None else None
        _refuse(zone is None or len(self.zones) < MAX_ZONES, "GAP_REGISTRY_CAPACITY_EXCEEDED")
        observed = tuple(_observe_zone(item, prices, when) for item in self.zones)
        self.zones = observed if zone is None else (*observed, zone)
        self.previous = {**session, **prices}
        self.close = prices["close"]

    def step(self, inputs, *, event_time):
        timestamp = _time(event_time)
        session = _session(inputs, timestamp)
        prices, fault = _prices(inputs["frame"])
        address = _event_address(session, prices, fault)
        if not self._check_event(session, timestamp, address):
            return _outputs(self.zones, self.close, self.count, self.fault)
        self.fault = self.fault or fault
        if self.fault is None:
            self._advance(prices, session)
        self.count += 1
        self.last_time, self.last_event_address = timestamp, address
        return _outputs(self.zones, self.close, self.count, self.fault)

    def snapshot(self):
        body = {"schema": "historical-daily-gap-state/1", "bound_contract_address": self.bound_contract.bound_contract_address,
                "zones": [dataclasses.asdict(zone) for zone in self.zones], "previous": self.previous,
                "last_time": None if self.last_time is None else self.last_time.isoformat(),
                "last_event_address": self.last_event_address, "count": self.count, "close": self.close,
                "fault": None if self.fault is None else _cell_document(self.fault)}
        return node_contracts._freeze({**body, "payload_address": hashing.content_address(body)})

    @classmethod
    def restore(cls, bound_contract, document, *, expected_payload_address):
        state = cls(bound_contract)
        value = node_contracts._plain(document)
        _validate_snapshot(value, bound_contract, expected_payload_address)
        state.zones = tuple(GapZone(**zone) for zone in value["zones"])
        state.previous, state.count, state.close = value["previous"], value["count"], value["close"]
        state.last_time = None if value["last_time"] is None else _time(value["last_time"])
        state.last_event_address = value["last_event_address"]
        state.fault = None if value["fault"] is None else _read_cell(value["fault"])
        return state


def _validate_snapshot(value, bound, expected):
    fields = {"schema", "bound_contract_address", "zones", "previous", "last_time", "last_event_address",
              "count", "close", "fault", "payload_address"}
    _refuse(isinstance(value, abc.Mapping) and set(value) == fields, "GAP_STATE_CLOSED_SCHEMA")
    body = {key: item for key, item in value.items() if key != "payload_address"}
    _refuse(value["schema"] == "historical-daily-gap-state/1"
            and value["bound_contract_address"] == bound.bound_contract_address
            and value["payload_address"] == expected == hashing.content_address(body), "GAP_STATE_IDENTITY")
    _refuse(type(value["count"]) is int and value["count"] >= 0, "GAP_STATE_COUNT")
    _refuse(isinstance(value["zones"], list) and len(value["zones"]) <= MAX_ZONES, "GAP_STATE_ZONE_LIMIT")


def _input_columns(inputs):
    _refuse(isinstance(inputs, abc.Mapping) and set(inputs) == set(_FIELDS), "GAP_INPUT_PORTS")
    columns, index = {}, None
    for port, fields in _FIELDS.items():
        columns[port] = {}
        for field in fields:
            name = field.lower()
            _refuse(isinstance(inputs[port], abc.Mapping) and name in inputs[port], "GAP_INPUT_FIELD_REQUIRED")
            series = inputs[port][name]
            index = _column_index(series, index)
            columns[port][name] = series.tolist()
    return columns, index


def _column_index(series, expected):
    _refuse(isinstance(series, pd.Series) and isinstance(series.index, pd.DatetimeIndex), "GAP_INDEXED_INPUT_REQUIRED")
    index = series.index
    _refuse(not index.empty and index.tz is not None and not index.hasnans and index.is_unique
            and index.is_monotonic_increasing, "GAP_CANONICAL_INDEX_REQUIRED")
    _refuse(expected is None or index.equals(expected), "GAP_EXACT_ALIGNMENT_REQUIRED")
    return index


def evaluate(parameters, inputs, *, evaluation_context=None):
    _refuse(parameters == {}, "GAP_PARAMETERS_UNSUPPORTED")
    _refuse(isinstance(evaluation_context, abc.Mapping) and set(evaluation_context) == {"bound_contract"},
            "GAP_BOUND_CONTEXT_REQUIRED")
    state = GapState(evaluation_context["bound_contract"])
    columns, index = _input_columns(inputs)
    outputs = {port: [] for port in _OUTPUTS}
    for i, timestamp in enumerate(index):
        row = {port: {field: values[i] for field, values in fields.items()} for port, fields in columns.items()}
        result = state.step(row, event_time=timestamp)
        for port in outputs:
            outputs[port].append(result[port])
    return {port: pd.Series(cells, index=index, dtype=object) for port, cells in outputs.items()}


def _port(name, direction):
    kind = "market_frame" if direction == "input" else "boolean" if name.endswith("still_open") else "float64"
    descriptor = {"port_id": name, "direction": direction, "semantic_flow": "value",
                  "semantic_role": "market_frame" if direction == "input" else "gap_value",
                  "type_ref": {"type_id": f"analytical.{kind}", "type_version": 2}, "shape": "series"}
    if direction == "input":
        descriptor["connections"] = {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}
    return descriptor


_DESCRIPTOR = {"component_id": KEY[0], "component_version": KEY[1], "domain_family": "state",
               "structural_role": "stateful", "parameters": {},
               "ports": [_port(port, "input") for port in _FIELDS] + [_port(port, "output") for port in _OUTPUTS]}
_RULE = {"rule_id": KEY[0] + ".binding", "rule_version": 1}
_CONTRACT = node_contracts._freeze({
    "schema": "first-party-node-contract/2", "stable_node_id": KEY[0], "semantic_version": KEY[1],
    "visible_family": "TYPE_3", "input_types": {port: "analytical.market_frame/series" for port in _FIELDS},
    "output_types": {port: ("analytical.boolean/series" if port.endswith("still_open") else "analytical.float64/series")
                     for port in _OUTPUTS},
    "required_market_fields": sorted(field.lower() if port == "frame" else "session." + field.lower()
                                     for port, fields in _FIELDS.items() for field in fields),
    "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "SESSION"},
    "warmup_history": _RULE, "execution_form": "RECURSIVE",
    "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
    "state_reset_policy": {"schema": "state-reset-policy/2", "reasons": []},
    "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "PROPAGATE",
    "numeric_validity_policy": "EXPLICIT_VALIDITY", "causal_declaration": "COMPLETED_EVENT_PREFIX",
    "evaluation_triggers": ["completed_bar"], "streaming_support": True, "batch_support": True,
    "mode_eligibility": {"research": True, "paper": False, "live": False}, "provider_requirements": [],
    "resource_profile": {"compute_microseconds_per_event": 250000, "memory_bytes_upper_bound": 8388608,
        "history_bytes_upper_bound": 1048576, "state_bytes_upper_bound": 4194304,
        "storage_bytes_per_day_upper_bound": 0, "subscription_count_upper_bound": 1, "fanout_upper_bound": 1},
    "reference_provenance": [hashing.content_address(_POLICY)],
    "parameter_binding": {"scheme": "analytical-contract-binding/1", **_RULE,
                          "parameter_names": [], "input_ports": list(_FIELDS)},
})


def _daily_binding_fact(fact, fields):
    if (fact["timeframe"] != 86400 or not set(fields) <= set(fact["fields"])
            or fact["session"] != "INSTRUMENT_CALENDAR"
            or fact["alignment"] != {"kind": "EXACT", "maximum_skew_seconds": 0}):
        raise ValueError("gap primitive requires exact canonical daily session fields")


def _binding(parameters, inputs, _builder=contracts.binding_result,
             _fields=tuple(_FIELDS.items()), _outputs=_OUTPUTS):
    if parameters:
        raise ValueError("gap primitive has no parameters")
    for port, fields in _fields:
        _daily_binding_fact(inputs["ports"][port]["binding"], fields)
    frame, session = (inputs["ports"][port]["binding"] for port, _ in _fields)
    if (session["derived_local"] is not True or session["instrument"]["role"] != "session"
            or session["canonical_instrument_address"] != frame["canonical_instrument_address"]
            or session["market_truth_address"] != frame["market_truth_address"]):
        raise ValueError("gap session calendar must belong to its canonical price instrument")
    return _builder(inputs, fields_by_port=dict(_fields), warmup_history=1,
                                    output_warmup={port: 1 for port in _outputs})


_BOUNDARY = registry.DependencyBoundary("defining_module", (abc, dataclasses, math, pd, hashing,
                        node_contracts, registry, validity, common, contracts, contracts.binding_result))
V2_TYPES = node_contracts._freeze({})
V2_COMPONENTS = node_contracts._freeze({KEY: _DESCRIPTOR})
NODE_CONTRACTS = node_contracts._freeze({KEY: _CONTRACT})
DATA_REQUIREMENTS = node_contracts._freeze({})
def _binding_registration():
    return registry.registered_contract_binding(
        component=KEY, source_contract=_CONTRACT, implementation=_binding,
        dependency_boundary=registry.DependencyBoundary("defining_module", (contracts.binding_result,)))


CONTRACT_BINDINGS = node_contracts._freeze({KEY: _binding_registration()})


def _check_bound(bound):
    _refuse(isinstance(bound, contracts.ResolvedNodeContract), "GAP_VERIFIED_BINDING_REQUIRED")
    expected = contracts.materialize_node_contract(_CONTRACT, _binding_registration(), {}, bound.document["input_binding"])
    _refuse(bound.bound_contract_address == expected.bound_contract_address, "GAP_BINDING_MISMATCH")


V2_IMPLEMENTATIONS = node_contracts._freeze({KEY: registry.registered_v2_implementation(
    component=KEY, implementation=evaluate, dependency_boundary=_BOUNDARY)})
