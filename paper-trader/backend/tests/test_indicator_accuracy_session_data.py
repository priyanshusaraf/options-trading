"""Implementation-owner session/data proof; independent assurance remains required."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import session_data as session
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract
from app.ir.validity import NumericValue, ValidityState


EXPECTED_SCOPE = tuple("""ANCHORED_VWAP ASK BARS_SINCE_SESSION_OPEN BID BOOK_DEPTH CLOSE
DISTANCE_FROM_SESSION_HIGH_LOW DTE EXPIRY_CALENDAR HIGH INSTRUMENT_METADATA LOW LTP
MARKET_CLOCK MID OHLCV OPEN OPENING_RANGE OPEN_INTEREST PREVIOUS_SESSION_FIELDS
PREVIOUS_SESSION_OHLC RESAMPLING SESSION_CALENDAR SESSION_HIGH SESSION_LOW SESSION_OPEN
SESSION_OPEN_HIGH_LOW SPREAD TIMEFRAME TIME_TO_SESSION_CLOSE VWAP""".split())
REFUSED = tuple("ASK BID BOOK_DEPTH DTE EXPIRY_CALENDAR INSTRUMENT_METADATA LTP MARKET_CLOCK MID OPEN_INTEREST RESAMPLING SESSION_CALENDAR SPREAD TIMEFRAME".split())
H = ValidityState.INSUFFICIENT_HISTORY


def address(value):
    return hashing.content_address({"session_data_test": value})


def parameters(name):
    if name == "ANCHORED_VWAP":
        return {"anchor_at": "2025-01-02T09:30:00+00:00"}
    if name == "OPENING_RANGE":
        return {"range_minutes": 15}
    if name == "PREVIOUS_SESSION_FIELDS":
        return {"field": "close"}
    return {}


def binding(name, p=None, *, timeframe=900, fields=None):
    p = parameters(name) if p is None else p
    declared = session.fields_by_port(name, p)
    primary = session.source_contract(name)["required_resolution"]["port"]
    def fact(port, required): return {"schema": "canonical-input-binding/1", "owner_id": "org.session",
        "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
        "dataset_manifest_address": address("manifest"), "market_truth_address": address("market-truth"),
        "provider_product_address": address("provider-product"), "provider_contract_address": address("provider-contract"),
        "canonical_instrument_address": address("primary"),
        "timeframe": timeframe, "fields": sorted(field.upper() for field in (fields or required)),
        "freshness": {"maximum_age_seconds": 900}, "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR", "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": port == "session", "instrument": {"role": "primary" if port == primary else port, "type": "PHYSICAL"}}
    ports = {}
    for port, required in declared.items():
        value=fact(port,required);ports[port]={"source":{"scope":"graph_input","port_id":port},"binding":value,"binding_address":hashing.content_address(value)}
    context = {"schema": "node-input-binding/1", "owner_id": "org.session",
        "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
        "context_address": hashing.content_address(ports), "ports": ports}
    return materialize_node_contract(session.source_contract(name), session.CONTRACT_BINDINGS[session.component_key(name)], p, context)


def frame():
    first = pd.date_range("2025-01-02T09:15:00Z", periods=4, freq="15min")
    second = pd.date_range("2025-01-03T09:15:00Z", periods=4, freq="15min")
    index = first.append(second)
    opens = [10., 11., 12., 13., 20., 21., 22., 23.]
    highs = [12., 13., 14., 15., 22., 23., 24., 25.]
    lows = [9., 10., 11., 12., 19., 20., 21., 22.]
    closes = [11., 12., 13., 14., 21., 22., 23., 24.]
    volumes = [10., 0., 20., 30., 5., 10., 0., 15.]
    session_ids = ["XNSE:2025-01-02"] * 4 + ["XNSE:2025-01-03"] * 4
    session_opens = [pd.Timestamp("2025-01-02T09:00:00Z")] * 4 + [pd.Timestamp("2025-01-03T09:00:00Z")] * 4
    session_closes = [pd.Timestamp("2025-01-02T10:00:00Z")] * 4 + [pd.Timestamp("2025-01-03T10:00:00Z")] * 4
    values = {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes,
              "session_id": session_ids, "session_open_at": session_opens, "session_close_at": session_closes}
    return {"frame": {key: pd.Series(value, index=index) for key, value in values.items()}}


def inputs_for(name, data=None):
    data = frame() if data is None else data
    return {port: {field.lower(): data["frame"][field.lower()] for field in fields}
            for port, fields in session.fields_by_port(name, parameters(name)).items()}


def values(result, port="value"):
    return [cell.value if cell.state is ValidityState.VALID else cell.state for cell in result[port]]


def exact_vwap(high, low, close, volume):
    total_pv, total_volume, result = Fraction(0), Fraction(0), []
    for h, l, c, v in zip(high, low, close, volume):
        price = (Fraction(h) + Fraction(l) + Fraction(c)) / 3
        total_pv += price * Fraction(v)
        total_volume += Fraction(v)
        result.append(float(total_pv / total_volume) if total_volume else H)
    return result


def assert_cells(actual, expected):
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        assert isinstance(got, NumericValue)
        if isinstance(want, ValidityState):
            assert got.state is want and got.value is None
        else:
            assert got.state is ValidityState.VALID
            assert abs(got.value - want) <= (1e-12 if want == 0 else 1e-10)


def test_complete_scope_separates_candidates_from_honest_refusals():
    from app.ir.library import REGISTRY, V2_CONTRIBUTORS
    assert session.ALL_NAMES == tuple(sorted(EXPECTED_SCOPE))
    assert session.REFUSED_NAMES == tuple(sorted(REFUSED))
    assert len(session.NAMES) == 17 and len(session.REFUSALS) == 14
    assert session not in V2_CONTRIBUTORS
    assert set(session.V2_COMPONENTS) == {("analytical." + name.lower(), 2) for name in session.NAMES}
    for name in REFUSED:
        fact = session.refusal_for(name)
        assert fact["code"] == session.SPECS[name]["refusal"]["code"]
        assert fact["executable"] is False
        assert ("analytical." + name.lower(), 2) not in session.V2_COMPONENTS
        assert ("analytical." + name.lower(), 2) not in REGISTRY.v2_components
        with pytest.raises(node_contracts.NodeContractRefusal, match=fact["code"]):
            session.component_key(name)


def test_source_contracts_and_descriptors_cover_every_candidate():
    for name in session.NAMES:
        key = session.component_key(name)
        p = parameters(name)
        assert dict(session.parameters_for(name, p)) == p
        assert set(session.SPECS[name]["outputs"]) == {port["port_id"] for port in session.V2_COMPONENTS[key]["ports"] if port["direction"] == "output"}
        declared = session.fields_by_port(name, p)
        primary = session.NODE_CONTRACTS[key]["required_resolution"]["port"]
        expected_fields = {field.lower() if port == primary else port + "." + field.lower()
                           for port, fields in declared.items() for field in fields}
        assert set(session.NODE_CONTRACTS[key]["required_market_fields"]) == expected_fields
        assert session.NODE_CONTRACTS[key]["mode_eligibility"] == {"research": True, "paper": False, "live": False}


@pytest.mark.parametrize("name,field", [("OPEN", "open"), ("HIGH", "high"), ("LOW", "low"), ("CLOSE", "close")])
def test_exact_completed_bar_field_arrays(name, field):
    data = frame()
    result = session.evaluate(name, {}, inputs_for(name, data), bound_contract=binding(name))
    assert_cells(result["value"], data["frame"][field].tolist())


def test_ohlcv_named_ports_are_complete_and_not_a_hidden_frame():
    data = frame()
    result = session.evaluate("OHLCV", {}, inputs_for("OHLCV", data), bound_contract=binding("OHLCV"))
    assert set(result) == {"open", "high", "low", "close", "volume"}
    for field in result:
        assert_cells(result[field], data["frame"][field].tolist())


def test_current_session_state_arrays_and_complete_slot_count():
    data = frame()
    expected = {
        "SESSION_OPEN": [10.] * 4 + [20.] * 4,
        "SESSION_HIGH": [12., 13., 14., 15., 22., 23., 24., 25.],
        "SESSION_LOW": [9., 9., 9., 9., 19., 19., 19., 19.],
        "BARS_SINCE_SESSION_OPEN": [0., 1., 2., 3., 0., 1., 2., 3.],
    }
    for name, wanted in expected.items():
        result = session.evaluate(name, {}, inputs_for(name, data), bound_contract=binding(name))
        assert_cells(result["value"], wanted)
    result = session.evaluate("SESSION_OPEN_HIGH_LOW", {}, inputs_for("SESSION_OPEN_HIGH_LOW", data),
                              bound_contract=binding("SESSION_OPEN_HIGH_LOW"))
    assert_cells(result["open"], expected["SESSION_OPEN"])
    assert_cells(result["high"], expected["SESSION_HIGH"])
    assert_cells(result["low"], expected["SESSION_LOW"])


def test_distance_opening_range_and_time_to_close_arrays():
    data = frame()
    distance = session.evaluate("DISTANCE_FROM_SESSION_HIGH_LOW", {}, inputs_for("DISTANCE_FROM_SESSION_HIGH_LOW", data),
                                bound_contract=binding("DISTANCE_FROM_SESSION_HIGH_LOW"))
    assert_cells(distance["from_high"], [1.] * 8)
    assert_cells(distance["from_low"], [2., 3., 4., 5., 2., 3., 4., 5.])
    opening = session.evaluate("OPENING_RANGE", {"range_minutes": 15}, inputs_for("OPENING_RANGE", data),
                               bound_contract=binding("OPENING_RANGE"))
    assert_cells(opening["high"], [12.] * 4 + [22.] * 4)
    assert_cells(opening["low"], [9.] * 4 + [19.] * 4)
    assert_cells(opening["middle"], [10.5] * 4 + [20.5] * 4)
    remaining = session.evaluate("TIME_TO_SESSION_CLOSE", {}, inputs_for("TIME_TO_SESSION_CLOSE", data),
                                 bound_contract=binding("TIME_TO_SESSION_CLOSE"))
    assert_cells(remaining["value"], [45., 30., 15., 0.] * 2)


def test_vwap_zero_volume_and_anchored_carry_across_sessions():
    data = frame()
    expected = exact_vwap(data["frame"]["high"].iloc[:4], data["frame"]["low"].iloc[:4],
                          data["frame"]["close"].iloc[:4], data["frame"]["volume"].iloc[:4])
    expected += exact_vwap(data["frame"]["high"].iloc[4:], data["frame"]["low"].iloc[4:],
                           data["frame"]["close"].iloc[4:], data["frame"]["volume"].iloc[4:])
    result = session.evaluate("VWAP", {}, inputs_for("VWAP", data), bound_contract=binding("VWAP"))
    assert_cells(result["value"], expected)
    p = parameters("ANCHORED_VWAP")
    anchored = session.evaluate("ANCHORED_VWAP", p, inputs_for("ANCHORED_VWAP", data), bound_contract=binding("ANCHORED_VWAP"))
    wanted = [H] + exact_vwap(data["frame"]["high"].iloc[1:], data["frame"]["low"].iloc[1:],
                              data["frame"]["close"].iloc[1:], data["frame"]["volume"].iloc[1:])
    assert_cells(anchored["value"], wanted)


def test_previous_complete_session_fields_are_held_through_next_session():
    data = frame()
    previous = session.evaluate("PREVIOUS_SESSION_OHLC", {}, inputs_for("PREVIOUS_SESSION_OHLC", data),
                                bound_contract=binding("PREVIOUS_SESSION_OHLC"))
    for port, value in {"open": 10., "high": 15., "low": 9., "close": 14.}.items():
        assert_cells(previous[port], [H] * 4 + [value] * 4)
    for field, value in {"open": 10., "high": 15., "low": 9., "close": 14., "volume": 60.}.items():
        p = {"field": field}
        got = session.evaluate("PREVIOUS_SESSION_FIELDS", p, inputs_for("PREVIOUS_SESSION_FIELDS", data),
                               bound_contract=binding("PREVIOUS_SESSION_FIELDS", p))
        assert_cells(got["value"], [H] * 4 + [value] * 4)


@pytest.mark.parametrize("name", session.NAMES)
def test_prefix_streaming_and_serialized_restart(name):
    p, data = parameters(name), frame()
    selected = inputs_for(name, data)
    bound = binding(name, p)
    batch = session.evaluate(name, p, selected, bound_contract=bound)
    fields = session.fields_by_port(name, p)
    state = session.SessionDataState(name, p, bound)
    for i, timestamp in enumerate(next(iter(next(iter(selected.values())).values())).index):
        prefix = {port: {field.lower(): selected[port][field.lower()].iloc[:i + 1] for field in declared}
                  for port, declared in fields.items()}
        prefix_result = session.evaluate(name, p, prefix, bound_contract=bound)
        for port in batch:
            assert prefix_result[port].tolist() == batch[port].iloc[:i + 1].tolist()
        row = {port: {field.lower(): selected[port][field.lower()].iloc[i] for field in declared}
               for port, declared in fields.items()}
        produced = state.step(row, event_time=timestamp)
        assert produced == {port: batch[port].iloc[i] for port in batch}
        state = session.SessionDataState.restore(name, p, bound, json.loads(json.dumps(state.snapshot())))


def test_parameter_boundaries_and_binding_replay_guards():
    assert session.parameters_for("OPENING_RANGE", {"range_minutes": 1})["range_minutes"] == 1
    assert session.parameters_for("OPENING_RANGE", {"range_minutes": 240})["range_minutes"] == 240
    for value in (0, 241, True, 1.0, None):
        with pytest.raises(node_contracts.NodeContractRefusal):
            session.parameters_for("OPENING_RANGE", {"range_minutes": value})
    for value in (None, pd.Timestamp("2025-01-02T09:30:00Z"), "2025-01-02T09:30:00Z", "2025-01-02"):
        with pytest.raises(node_contracts.NodeContractRefusal):
            session.parameters_for("ANCHORED_VWAP", {"anchor_at": value})
    p = parameters("OPENING_RANGE")
    with pytest.raises(node_contracts.NodeContractRefusal):
        binding("OPENING_RANGE", p, timeframe=600)
    bound = binding("SESSION_HIGH")
    forged = deepcopy(node_contracts._plain(bound.document))
    forged["parameters"] = {"extra": 1}
    forged["bound_contract_address"] = hashing.content_address({key: value for key, value in forged.items() if key != "bound_contract_address"})
    with pytest.raises(node_contracts.NodeContractRefusal):
        session.SessionDataState("SESSION_HIGH", {}, session.contracts.ResolvedNodeContract(forged, forged["bound_contract_address"]))


def test_missing_invalid_gap_and_incomplete_anchor_refuse_without_fallback():
    data = frame()
    broken = inputs_for("VWAP", data)
    broken["frame"]["volume"] = broken["frame"]["volume"].copy()
    broken["frame"]["volume"].iloc[1] = -1
    result = session.evaluate("VWAP", {}, broken, bound_contract=binding("VWAP"))
    assert result["value"].iloc[1].state is ValidityState.INVALID
    missing_slot = inputs_for("BARS_SINCE_SESSION_OPEN", data)
    missing_slot = {port: {key: values.drop(values.index[1]) for key, values in columns.items()}
                    for port, columns in missing_slot.items()}
    with pytest.raises(node_contracts.NodeContractRefusal, match="MISSING_SESSION_SLOT"):
        session.evaluate("BARS_SINCE_SESSION_OPEN", {}, missing_slot, bound_contract=binding("BARS_SINCE_SESSION_OPEN"))
    p = {"anchor_at": "2025-01-02T09:15:00+00:00"}
    suffix = inputs_for("ANCHORED_VWAP", data)
    suffix = {"frame": {key: values.iloc[1:] for key, values in suffix["frame"].items()}}
    with pytest.raises(node_contracts.NodeContractRefusal, match="ANCHOR_HISTORY_INCOMPLETE"):
        session.evaluate("ANCHORED_VWAP", p, suffix, bound_contract=binding("ANCHORED_VWAP", p))


def test_state_payload_identity_and_event_guards():
    name, p = "SESSION_HIGH", {}
    bound = binding(name)
    state = session.SessionDataState(name, p, bound)
    data = inputs_for(name)
    timestamp = next(iter(next(iter(data.values())).values())).index[0]
    row = {port: {field: series.iloc[0] for field, series in columns.items()} for port, columns in data.items()}
    state.step(row, event_time=timestamp)
    document = state.snapshot()
    for field in ("component", "bound_contract_address", "session_count", "current", "payload_address"):
        forged = deepcopy(document)
        if field == "component": forged[field][0] += ".wrong"
        elif field == "bound_contract_address": forged[field] = address("wrong")
        elif field == "session_count": forged[field] = 100001
        elif field == "current": forged[field]["high"] = "NaN"
        else: forged[field] = address("wrong")
        with pytest.raises(node_contracts.NodeContractRefusal):
            session.SessionDataState.restore(name, p, bound, forged)
    with pytest.raises(node_contracts.NodeContractRefusal, match="EVENT_ORDER"):
        state.step(row, event_time=timestamp)


def test_source_and_resource_identity_are_bounded_and_unpublished():
    for name in session.NAMES:
        contract = session.source_contract(name)
        resource = contract["resource_profile"]
        assert resource["compute_microseconds_per_event"] == 250000
        assert resource["memory_bytes_upper_bound"] == 33554432
        assert resource["history_bytes_upper_bound"] == 2097152
        assert resource["state_bytes_upper_bound"] == 4194304
        assert tuple(contract["parameter_binding"]["parameter_names"]) == tuple(sorted(session.SPECS[name]["parameters"]))
        assert len(contract["reference_provenance"]) >= len(session.SPECS[name]["source_addresses"])
