from __future__ import annotations

import ast
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.ir.hashing import content_address
from app.ir.first_party import analytical, derivatives, execution_intent, logic_state
from app.ir.first_party.conformance import CatalogueConformanceError, assert_catalogue_complete
from app.ir.library import REGISTRY
from app.ir.node_contracts import canonical_state_snapshot, state_snapshot_document
from app.ir.validity import NumericValue, ValidityState, invalid, valid
from app.market_data.capability import (
    CAPABILITY_ASSESSMENT_ALGORITHM,
    CAPABILITY_ASSESSMENT_ALGORITHM_VERSION,
    CAPABILITY_ASSESSMENT_SCHEMA,
)
from app.market_truth.identity import canonical_fact_address


CATALOGUE = Path(__file__).resolve().parents[2] / "docs/reports/phase5-v1-catalogue.json"
MODULES = (execution_intent, derivatives, logic_state)


def _expected() -> dict[str, set[str]]:
    document = json.loads(CATALOGUE.read_text())
    result = {"TYPE_1": set(), "TYPE_3": set(), "TYPE_5": set()}
    for group in document["groups"]:
        if group["owner_capsule"] != "phase5-state-execution-derivatives-catalogue":
            continue
        result[group["family"]].update(group["v1_required"])
        result[group["family"]].update(group["v1_capability_gated"])
    return result


def _address(name: str) -> str:
    return content_address({"fixture": name})


def _generic_input():
    return {
        "left": valid(2.0), "right": valid(1.0),
        "lower": valid(0.0), "upper": valid(3.0),
        "series": tuple(valid(item) for item in (0.0, 1.0, 1.0, 0.0)),
        "fallback": valid(7.0), "fallback_states": ("MISSING",),
        "reset_reasons": ["EXPLICIT", "SESSION"],
        "allowed": valid(True), "a_series": tuple(valid(item) for item in (True, False, False, True)),
        "b_series": tuple(valid(item) for item in (False, True, False, True)),
        "event_times": tuple(f"2026-08-26T00:0{index}:00+00:00" for index in range(4)),
        "initial_state": 0.0,
        "reset_series": tuple(valid(item) for item in (False, False, True, False)),
        "transition": {
            "False:False": False, "False:True": True,
            "True:False": False, "True:True": True,
        },
        "evaluation_time": "2026-08-26T10:30:00+00:00",
        "allowed_weekdays": (0, 1, 2, 3, 4),
        "session_open": "09:15:00", "session_close": "15:30:00",
        "time_start": "10:00:00", "time_end": "11:00:00",
        "date_start": "2026-08-01", "date_end": "2026-08-31",
        "dte": valid(7.0), "minimum_dte": valid(1.0), "maximum_dte": valid(10.0),
        "session_open_time": "2026-08-26T09:15:00+00:00",
        "session_close_time": "2026-08-26T15:30:00+00:00",
    }


def _type5_input(name: str):
    value = _generic_input()
    if name in {"AND", "OR", "XOR", "NOT"}:
        value.update(left=valid(True), right=valid(False))
    if name in {
        "ANY", "ALL", "LATCH", "RESETTABLE_LATCH", "TOGGLE", "STATE_MACHINE",
        "N_CONSECUTIVE", "N_OF_LAST_M",
    }:
        value["series"] = tuple(valid(item) for item in (False, True, True, False))
        value["initial_state"] = False
    if name == "HYSTERESIS":
        value["initial_state"] = False
        value["series"] = tuple(valid(item) for item in (0.0, 2.0, 1.0, 0.0))
        value["lower"] = valid(0.5)
        value["upper"] = valid(1.5)
    if name == "IF_MISSING":
        value["left"] = invalid(ValidityState.MISSING)
    if name == "EXPLICIT_FALLBACK":
        value["left"] = invalid(ValidityState.STALE)
        value["fallback_states"] = ("STALE",)
    return value


def _capability_envelope(name: str, rulebook_address: str):
    provider_requirement = content_address({"provider-capability": name})
    fact = {
        "owner_id": "owner-a", "mode": "RESEARCH",
        "plan_address": _address("plan"),
        "registry_snapshot_address": _address("registry"),
        "capability_profile_address": _address("profile"),
        "dataset_manifest_address": _address("dataset"),
        "market_truth_snapshot_address": rulebook_address,
        "evaluation_policy_address": _address("evaluation-policy"),
        "assessment_evidence_address": _address("assessment-evidence"),
        "assessed_at": int(dt.datetime(
            2026, 8, 26, 0, 1, 30, tzinfo=dt.UTC,
        ).timestamp()),
        "requirement_results": [{
            "selector": provider_requirement, "result": "SATISFIED",
            "reason": "one declared offer covers the complete requirement",
        }],
        "assessment_algorithm": CAPABILITY_ASSESSMENT_ALGORITHM,
        "assessment_algorithm_version": CAPABILITY_ASSESSMENT_ALGORITHM_VERSION,
    }
    envelope = {"schema": CAPABILITY_ASSESSMENT_SCHEMA, "fact": fact}
    return envelope, canonical_fact_address(CAPABILITY_ASSESSMENT_SCHEMA, fact)


def _derivative_fact(
    name: str, *, capability: bool = False, members: int = 3,
    maximum_members: int = 3, provider_declared: bool | None = None,
):
    if provider_declared is None:
        provider_declared = capability
    source_address = _address(f"source-{name}")
    acceptance_evidence_address = _address(f"acceptance-{name}")
    rulebook_address = _address(f"rulebook-{name}")
    provider_requirement = content_address({"provider-capability": name})
    role_requirement = {
        "role_id": "derivative_selection",
        "role_kind": "DERIVATIVE_SELECTOR",
        "instrument_type": "ECONOMIC_SELECTOR",
        "cardinality": "DYNAMIC_WINDOW",
        "maximum_members": maximum_members,
        "source_requirement_addresses": [_address(f"data-{name}")],
        "provider_requirement_addresses": [provider_requirement] if provider_declared else [],
        "binding_input_kind": "SELECTOR_POLICY_ADDRESS",
        "execution_eligible": False,
        "research_only": True,
    }
    role_address = content_address({
        "schema": "instrument-role-requirement/1", **role_requirement,
    })
    policy = {
        "schema": "derivative-selector-policy/1",
        "operation": name,
        "accepted_source_address": source_address,
        "acceptance_evidence_address": acceptance_evidence_address,
        "rulebook_snapshot_address": rulebook_address,
        "role_requirement_address": role_address,
        "provider_requirement_address": provider_requirement if provider_declared else None,
        "maximum_members": maximum_members,
        "algorithm_version": "phase5-type3/2",
    }
    policy["policy_address"] = content_address(policy)
    envelope, capability_address = _capability_envelope(name, rulebook_address)
    member_rows = []
    for index in range(members):
        values = {
            "structure_role": ("PRIMARY", "SECONDARY", "TERTIARY")[index % 3],
            "price": (10.0, 8.0, 6.0)[index % 3],
            "strike": (100.0, 100.0, 105.0)[index % 3],
            "right": ("CALL", "PUT", "CALL")[index % 3],
            "delta": (0.5, -0.5, 0.35)[index % 3],
            "dte": (7.0, 7.0, 14.0)[index % 3],
            "expiry": ("2026-09-02", "2026-09-02", "2026-09-09")[index % 3],
            "contract_rank": index,
            "open_interest": (100.0, 80.0, 60.0)[index % 3],
            "change_in_open_interest": (5.0, -2.0, 3.0)[index % 3],
            "volume": (50.0, 40.0, 30.0)[index % 3],
            "best_bid": 9.8 + index,
            "best_ask": 10.2 + index,
            "bid_quantity": 100.0 + 10 * index,
            "ask_quantity": 80.0 + 10 * index,
            "total_buy_quantity": 1000.0 + 100 * index,
            "total_sell_quantity": 900.0 + 100 * index,
            "depth_levels": (
                {"bid": 9.8, "ask": 10.2, "bid_quantity": 100.0,
                 "ask_quantity": 80.0},
                {"bid": 9.7, "ask": 10.3, "bid_quantity": 60.0,
                 "ask_quantity": 50.0},
            ),
            "aggressor_buy_volume": 30.0 + index,
            "aggressor_sell_volume": 20.0 + index,
            "cumulative_delta": 10.0 + index,
            "implied_volatility": 0.20 + index * 0.01,
            "gamma": 0.02 + index * 0.001,
            "theta": -0.01 - index * 0.001,
            "vega": 0.12 + index * 0.01,
            "rho": 0.04 + index * 0.001,
            "iv_rank": 40.0 + index,
            "iv_percentile": 55.0 + index,
            "skew": -0.05 + index * 0.01,
            "term_structure": 0.01 + index * 0.005,
        }
        member_rows.append({
            "instrument_address": _address(f"instrument-{index}"),
            "values": values,
            "values_address": content_address(values),
        })
    member_rows.sort(key=lambda row: row["instrument_address"])
    context = {
        "spot": 102.0, "strike": 100.0, "future": 104.0,
        "year_fraction": 0.25, "target_delta": 0.4,
        "target_dte": 10.0, "strike_offset_count": 1,
        "target_moneyness_ratio": 1.0, "option_right": "CALL",
        "strike_min": 99.0, "strike_max": 106.0,
        "selected_expiry": "2026-09-02", "minimum_roll_dte": 10.0,
        "mapped_contract_address": member_rows[-1]["instrument_address"],
        "depth_level_count": 2,
    }
    result = {
        "schema": "point-in-time-derivative-fact/2",
        "owner_id": "owner-a",
        "mode": "RESEARCH",
        "acceptance_evidence_address": acceptance_evidence_address,
        "source_address": source_address,
        "capability_evidence_address": capability_address if capability else None,
        "capability_assessment_envelope": envelope if capability else None,
        "rulebook_snapshot_address": rulebook_address,
        "selector_policy_address": policy["policy_address"],
        "selector_policy": policy,
        "role_requirement_address": role_address,
        "role_requirement": role_requirement,
        "event_time": "2026-08-26T00:00:00+00:00",
        "knowledge_time": "2026-08-26T00:01:00+00:00",
        "evaluation_cutoff": "2026-08-26T00:02:00+00:00",
        "members": tuple(member_rows),
        "context": context,
    }
    result["fact_address"] = content_address(result)
    return result


def _rehash_fact(value):
    value["fact_address"] = content_address({
        key: item for key, item in value.items() if key != "fact_address"
    })
    return value


def _derivative_evaluation_context(fact):
    return logic_state.DerivativeEvaluationContext(
        owner_id=fact["owner_id"], mode=fact["mode"],
        point_in_time_fact_address=fact["fact_address"],
        source_address=fact["source_address"],
        acceptance_evidence_address=fact["acceptance_evidence_address"],
        rulebook_snapshot_address=fact["rulebook_snapshot_address"],
        selector_policy_address=fact["selector_policy_address"],
        role_requirement_address=fact["role_requirement_address"],
        capability_evidence_address=fact["capability_evidence_address"],
    )


def _state_restore_context(snapshot, *, reset_reasons, next_event_time):
    next_event_address = _address(f"event-{next_event_time}")
    return logic_state.StateRestoreContext(
        snapshot_address=snapshot.snapshot_address,
        strategy_address=snapshot.document["strategy_address"],
        resolved_graph_address=snapshot.document["resolved_graph_address"],
        node_contract_address=snapshot.document["node_contract_address"],
        implementation_closure_address=snapshot.document["implementation_closure_address"],
        dataset_context_address=snapshot.document["dataset_context_address"],
        evaluation_context_address=snapshot.document["evaluation_context_address"],
        reset_policy_address=snapshot.document["reset_policy_address"],
        last_event_address=snapshot.document["last_event_address"],
        creation_evidence_address=snapshot.document["creation_evidence_address"],
        snapshot_reset_reasons=tuple(snapshot.document["reset_reasons"]),
        pending_reset_reasons=tuple(sorted(set(reset_reasons))),
        next_event_address=next_event_address,
        next_event_time=next_event_time,
    )


def _snapshot_input(
    name: str, state_payload, *, initial_state, reset_reasons=(),
    next_event_time="2026-08-26T00:01:00+00:00",
    last_event_time="2026-08-26T00:00:00+00:00", length=4,
    base_value=None,
):
    key = (f"logic.{name.lower()}", 1)
    contract = REGISTRY.node_contracts[key]
    reset_policy_address = content_address({
        "schema": contract["state_reset_policy"]["schema"],
        "reasons": list(contract["state_reset_policy"]["reasons"]),
    })
    facts = {
        "strategy_address": _address("strategy"),
        "resolved_graph_address": _address("graph"),
        "node_contract_address": REGISTRY.node_contract_addresses[key],
        "implementation_closure_address": (
            REGISTRY.v2_implementation_registrations[key].implementation_address
        ),
        "dataset_context_address": _address("dataset"),
        "evaluation_context_address": _address("evaluation"),
        "last_event_address": _address(f"event-{last_event_time}"),
        "last_event_time": last_event_time,
        "state_bytes_digest": content_address({"state": state_payload}),
        "validity_state": "VALID",
        "reset_policy_address": reset_policy_address,
        "reset_reasons": [],
        "creation_evidence_address": _address("creation"),
    }
    snapshot = canonical_state_snapshot(state_snapshot_document(**facts))
    next_event_address = _address(f"event-{next_event_time}")
    value = {
        **(_generic_input() if base_value is None else base_value), "snapshot": snapshot,
        "initial_state": initial_state, "state_payload": state_payload,
        "reset_reasons": list(reset_reasons), "next_event_time": next_event_time,
        "next_event_address": next_event_address,
    }
    start = dt.datetime.fromisoformat(next_event_time)
    value["event_times"] = tuple(
        (start + dt.timedelta(minutes=index)).isoformat() for index in range(length)
    )
    context = _state_restore_context(
        snapshot, reset_reasons=reset_reasons, next_event_time=next_event_time,
    )
    return value, snapshot, context


def _type3_expected(fact):
    members = fact["members"]
    by_role = {item["values"]["structure_role"]: item for item in members}
    primary = by_role["PRIMARY"]
    secondary = by_role["SECONDARY"]
    tertiary = by_role["TERTIARY"]
    addresses = tuple(item["instrument_address"] for item in members)
    calls = tuple(item["instrument_address"] for item in members
                  if item["values"]["right"] == "CALL")
    near_chain = tuple(item["instrument_address"] for item in members
                       if item["values"]["expiry"] == "2026-09-02")
    field_values = lambda field: tuple(item["values"][field] for item in members)
    depth_weighted_spread = ((10.2*80 + 10.3*50)/130) - ((9.8*100 + 9.7*60)/160)
    result = {
        "SECONDARY_INSTRUMENT_INPUT": secondary["instrument_address"],
        "PEER_BASKET": addresses,
        "RELATIVE_VALUE_STRUCTURE": 2.0,
        "EXPIRY_LIST": ("2026-09-02", "2026-09-09"),
        "NEAREST_EXPIRY": "2026-09-02",
        "NEXT_EXPIRY": "2026-09-09",
        "FAR_EXPIRY": "2026-09-09",
        "DTE_SELECTOR": min(
            primary["instrument_address"], secondary["instrument_address"],
        ),
        "ATM": 100.0,
        "ATM_PLUS_MINUS_N": (100.0, 105.0),
        "MONEYNESS_SELECTOR": min(
            primary["instrument_address"], secondary["instrument_address"],
        ),
        "DELTA_TARGET_SELECTOR": tertiary["instrument_address"],
        "CALL_PUT_SELECTOR": calls,
        "OPTION_CHAIN_SLICE": near_chain,
        "STRADDLE_SELECTOR": (
            primary["instrument_address"], secondary["instrument_address"],
        ),
        "STRANGLE_SELECTOR": (
            tertiary["instrument_address"], secondary["instrument_address"],
        ),
        "STRADDLE_PRICE": 18.0,
        "PUT_CALL_PARITY_DEVIATION": 0.0,
        "SYNTHETIC_FUTURE": 102.0,
        "IMPLIED_VOLATILITY": field_values("implied_volatility"),
        "DELTA": field_values("delta"),
        "GAMMA": field_values("gamma"),
        "THETA": field_values("theta"),
        "VEGA": field_values("vega"),
        "RHO": field_values("rho"),
        "IV_RANK": field_values("iv_rank"),
        "IV_PERCENTILE": field_values("iv_percentile"),
        "SKEW": field_values("skew"),
        "TERM_STRUCTURE": field_values("term_structure"),
        "CHAIN_OPEN_INTEREST": 240.0,
        "PCR_OPEN_INTEREST": 0.5,
        "PCR_VOLUME": 0.5,
        "OPEN_INTEREST_CONCENTRATION": 100.0/240.0,
        "CHANGE_IN_OPEN_INTEREST": 6.0,
        "STRIKE_VOLUME_OI_RATIO": (0.5, 0.5, 0.5),
        "FRONT_CONTRACT": primary["instrument_address"],
        "NEXT_CONTRACT": secondary["instrument_address"],
        "FAR_CONTRACT": tertiary["instrument_address"],
        "DAYS_TO_EXPIRY": 7.0,
        "BASIS": 2.0,
        "ANNUALIZED_BASIS": 8.0,
        "CALENDAR_SPREAD": 2.0,
        "ROLL_SELECTOR": tertiary["instrument_address"],
        "CONTINUOUS_RESEARCH_SERIES": (10.0, 8.0, 6.0),
        "TRADABLE_MAPPED_CONTRACT": fact["context"]["mapped_contract_address"],
        "BEST_BID": 9.8,
        "BEST_ASK": 10.2,
        "SPREAD": 0.4,
        "BID_QUANTITY": 100.0,
        "ASK_QUANTITY": 80.0,
        "DEPTH_LEVEL_N": (9.7, 10.3, 60.0, 50.0),
        "CUMULATIVE_N_LEVEL_DEPTH": (160.0, 130.0),
        "DEPTH_IMBALANCE": 1.0/9.0,
        "WEIGHTED_DEPTH_IMBALANCE": 25.0/235.0,
        "MICROPRICE": 1804.0/180.0,
        "BOOK_SLOPE": 0.1,
        "LIQUIDITY_CONCENTRATION": 100.0/290.0,
        "DEPTH_WEIGHTED_SPREAD": depth_weighted_spread,
        "PROVIDER_TOTAL_BUY_SELL_QUANTITY": (1000.0, 900.0),
        "AGGRESSOR_BUY_SELL_FLOW": (93.0, 63.0),
        "VOLUME_DELTA": 30.0,
        "TRADE_IMBALANCE": 30.0/156.0,
        "CUMULATIVE_DELTA": field_values("cumulative_delta"),
    }
    assert set(result) == set(derivatives.TYPE_3_NAMES)
    return result


def _assert_semantic_equal(actual, expected):
    if isinstance(expected, float):
        assert actual == pytest.approx(expected)
    elif isinstance(expected, tuple):
        assert isinstance(actual, tuple) and len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected, strict=True):
            _assert_semantic_equal(actual_item, expected_item)
    else:
        assert actual == expected


def _type5_expected():
    last_event = "2026-08-26T00:03:00+00:00"
    state = lambda values, payload: logic_state.StateSeriesResult(
        tuple(values), payload, last_event,
    )
    insufficient = invalid(ValidityState.INSUFFICIENT_HISTORY)
    result = {
        "ABS": valid(2.0), "ADD": valid(3.0), "ALL": valid(False),
        "AND": valid(False), "ANY": valid(True), "AVERAGE": valid(0.5),
        "A_THEN_B": state(tuple(map(valid, (False, True, False, True))), True),
        "A_WITHIN_N_BARS_OF_B": state(
            tuple(map(valid, (False, True, False, False))), (False, True),
        ),
        "BARS_SINCE": state(tuple(map(valid, (0, 1, 2, 0))), 0),
        "BETWEEN": valid(True), "CLAMP": valid(2.0),
        "COOLDOWN": state(tuple(map(valid, (True, False, False, True))), 2),
        "COUNT": valid(4),
        "COUNTER": state(tuple(map(valid, (0.0, 1.0, 2.0, 2.0))), 2.0),
        "DATE_RANGE": valid(True),
        "DEBOUNCE": state(tuple(map(valid, (False, False, False, False))), 1),
        "DIVIDE": valid(2.0), "DTE_GATE": valid(True), "EQ": valid(False),
        "EXPLICIT_FALLBACK": valid(7.0),
        "FALLING_N": state(
            (insufficient, valid(False), valid(False), valid(False)), (0.0, 1),
        ),
        "GT": valid(True), "GTE": valid(True),
        "HYSTERESIS": state(tuple(map(valid, (False, True, True, False))), False),
        "IF_MISSING": valid(7.0), "IS_MISSING": valid(False),
        "IS_STALE": valid(False), "IS_UNDEFINED": valid(False),
        "IS_VALID": valid(True),
        "LAG_N": state((insufficient, insufficient, valid(0.0), valid(1.0)), (1.0, 0.0)),
        "LATCH": state(tuple(map(valid, (False, True, True, True))), True),
        "LOG": valid(0.6931471805599453), "LT": valid(False), "LTE": valid(False),
        "MAX": valid(1.0), "MIN": valid(0.0), "MINUTES_FROM_OPEN": valid(75.0),
        "MINUTES_TO_CLOSE": valid(300.0), "MODULO": valid(0.0),
        "MULTIPLY": valid(2.0), "NEQ": valid(True), "NOT": valid(False),
        "N_CONSECUTIVE": state(
            tuple(map(valid, (False, False, True, False))), 0,
        ),
        "N_OF_LAST_M": state(
            (insufficient, valid(True), valid(True), valid(True)), (True, False),
        ),
        "OR": valid(True), "POWER": valid(2.0),
        "PREVIOUS_VALUE": state(
            (insufficient, valid(0.0), valid(1.0), valid(1.0)), (1.0, 0.0),
        ),
        "RESETTABLE_LATCH": state(
            tuple(map(valid, (False, True, False, False))), False,
        ),
        "RISING_N": state(
            (insufficient, valid(False), valid(False), valid(False)), (0.0, 0),
        ),
        "ROUND": valid(2),
        "SESSION_GATE": valid(True), "SQRT": valid(1.4142135623730951),
        "STATE_MACHINE": state(
            tuple(map(valid, (False, True, True, False))), False,
        ),
        "SUBTRACT": valid(1.0), "SUM": valid(2.0), "TIME_RANGE": valid(True),
        "TIME_SINCE": state(
            tuple(map(valid, (0.0, 60.0, 120.0, 0.0))), last_event,
        ),
        "TOGGLE": state(tuple(map(valid, (False, True, False, False))), False),
        "WEEKDAY_GATE": valid(True),
        "XOR": valid(True),
    }
    assert set(result) == set(logic_state.TYPE_5_NAMES)
    return result


def _assert_numeric_semantic(actual, expected):
    assert isinstance(actual, NumericValue)
    assert actual.state is expected.state
    assert actual.causes == expected.causes
    if expected.state is ValidityState.VALID:
        _assert_semantic_equal(actual.value, expected.value)


def _assert_type5_semantic(actual, expected):
    if isinstance(expected, logic_state.StateSeriesResult):
        assert isinstance(actual, logic_state.StateSeriesResult)
        assert actual.last_event_time == expected.last_event_time
        _assert_semantic_equal(actual.state_payload, expected.state_payload)
        assert len(actual.values) == len(expected.values)
        for actual_item, expected_item in zip(actual.values, expected.values, strict=True):
            _assert_numeric_semantic(actual_item, expected_item)
    else:
        _assert_numeric_semantic(actual, expected)


def _state_prefix_input(name: str, start: int, end: int):
    value = _type5_input(name)
    for field in ("series", "a_series", "b_series", "event_times", "reset_series"):
        if field in value:
            value[field] = value[field][start:end]
    value["reset_reasons"] = []
    value.pop("snapshot", None)
    value.pop("state_payload", None)
    value.pop("expected_snapshot_identity", None)
    value.pop("next_event_time", None)
    return value


def _declared_initial_state(name: str):
    if name in {"A_THEN_B", "LATCH", "RESETTABLE_LATCH", "TOGGLE",
                "STATE_MACHINE", "HYSTERESIS"}:
        return False
    if name in {"A_WITHIN_N_BARS_OF_B", "LAG_N", "PREVIOUS_VALUE", "N_OF_LAST_M"}:
        return ()
    if name in {"RISING_N", "FALLING_N"}:
        return (None, 0)
    if name == "TIME_SINCE":
        return None
    if name == "BARS_SINCE":
        return -1
    if name == "COUNTER":
        return 0.0
    if name in {"DEBOUNCE", "COOLDOWN", "N_CONSECUTIVE"}:
        return 0
    raise AssertionError(name)


def test_registry_equals_frozen_type1_type3_type5_inventory():
    expected = _expected()
    assert set(execution_intent.TYPE_1_NAMES) == expected["TYPE_1"]
    assert set(derivatives.TYPE_3_NAMES) == expected["TYPE_3"]
    assert set(logic_state.TYPE_5_NAMES) == expected["TYPE_5"]
    phase5_names = {
        (logic_state.component_id(family, name), 1)
        for family, names in expected.items() for name in names
    }
    analytical_names = {(analytical.component_id(name), 1) for name in analytical.CATALOGUE_NAMES}
    assert_catalogue_complete(REGISTRY, phase5_names | analytical_names)
    assert len(phase5_names) == 184


@pytest.mark.parametrize("omission", (
    "component", "implementation", "contract", "declaration",
))
def test_complete_registered_universe_rejects_every_omission_class(omission):
    expected = set(REGISTRY.v2_components)
    victim = ("logic.a_then_b", 1)
    values = {
        "v2_components": dict(REGISTRY.v2_components),
        "v2_implementation_registrations": dict(
            REGISTRY.v2_implementation_registrations,
        ),
        "node_contracts": dict(REGISTRY.node_contracts),
        "data_requirement_declarations": dict(
            REGISTRY.data_requirement_declarations,
        ),
    }
    key = {
        "component": "v2_components", "implementation": "v2_implementation_registrations",
        "contract": "node_contracts", "declaration": "data_requirement_declarations",
    }[omission]
    values[key].pop(victim)
    with pytest.raises(CatalogueConformanceError):
        assert_catalogue_complete(SimpleNamespace(**values), expected)


@pytest.mark.parametrize("module", MODULES)
def test_every_entry_has_contract_data_implementation_and_reference(module):
    keys = set(module.V2_COMPONENTS)
    assert keys == set(module.V2_IMPLEMENTATIONS) == set(module.NODE_CONTRACTS) \
        == set(module.DATA_REQUIREMENTS)
    for key in keys:
        contract = module.NODE_CONTRACTS[key]
        assert len(contract) == 22
        assert contract["reference_provenance"]
        assert contract["resource_profile"]
        assert module.V2_COMPONENTS[key]["ports"][-1]["port_id"] \
            in contract["output_types"]


def test_type5_recursive_state_contracts_equal_the_exact_stateful_universe():
    recursive = set()
    for name in logic_state.TYPE_5_NAMES:
        key = (f"logic.{name.lower()}", 1)
        contract = REGISTRY.node_contracts[key]
        component = REGISTRY.v2_components[key]
        if contract["execution_form"] == "RECURSIVE":
            recursive.add(name)
            assert contract["state_initialization"]["initial_state_address"]
            assert tuple(contract["state_reset_policy"]["reasons"]) == (
                "ELAPSED_WINDOW", "EXPIRY_ROLL", "EXPLICIT",
                "POSITION_CLOSE", "SESSION",
            )
            assert component["structural_role"] == "stateful"
            assert contract["output_types"]["value"] == "state-series-result/1"
        else:
            assert contract["execution_form"] == "STATELESS"
            assert contract["state_initialization"]["initial_state_address"] is None
            assert tuple(contract["state_reset_policy"]["reasons"]) == ()
            assert component["structural_role"] == "transform"
            assert contract["output_types"]["value"] == "numeric-value/1"
    assert recursive == set(logic_state.STATEFUL_TYPE_5_NAMES)


def test_family_components_expose_only_their_semantic_parameters():
    for name in execution_intent.TYPE_1_NAMES:
        assert set(REGISTRY.v2_components[(f"intent.{name.lower()}", 1)]["parameters"]) \
            == {"entry_blocked"}
    for name in derivatives.TYPE_3_NAMES:
        assert set(REGISTRY.v2_components[(f"derivative.{name.lower()}", 1)]["parameters"]) \
            == {"maximum_members"}
    for name in logic_state.TYPE_5_NAMES:
        expected = ({"window", "required_count"} if name == "N_OF_LAST_M"
                    else {"window"} if name in logic_state.STATEFUL_TYPE_5_NAMES else set())
        assert set(REGISTRY.v2_components[(f"logic.{name.lower()}", 1)]["parameters"]) \
            == expected


def test_type1_intents_are_pure_and_risk_reduction_survives_entry_block():
    for name in execution_intent.TYPE_1_NAMES:
        implementation = REGISTRY.v2_implementation_registrations[
            (logic_state.component_id("TYPE_1", name), 1)
        ].implementation
        value = implementation(
            {"window": 1, "entry_blocked": True, "maximum_members": 1,
             "required_count": 1},
            {"input": {"quantity": 1}},
        )["value"]
        assert value["schema"] == "execution-intent-description/1"
        assert value["operation"] == name
        assert value["payload"] == {"quantity": 1}
        assert value["risk_reducing"] is (name in logic_state.RISK_REDUCING_OPERATIONS)
        assert value["state"] == (
            "BLOCKED_ENTRY" if name in logic_state.ENTRY_OPERATIONS else "REQUESTED"
        )
        if name in logic_state.RISK_REDUCING_OPERATIONS:
            assert value["risk_reducing"] and value["state"] == "REQUESTED"
        if name in logic_state.ENTRY_OPERATIONS:
            assert value["state"] == "BLOCKED_ENTRY"


def test_type1_modules_have_no_broker_engine_venue_or_money_imports():
    forbidden = {
        "app.engine", "app.execution", "app.providers", "app.ledger",
        "app.core.credential_vault",
    }
    for module in (execution_intent, logic_state):
        tree = ast.parse(Path(module.__file__).read_text())
        imports = {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(any(name.startswith(prefix) for prefix in forbidden) for name in imports)


@pytest.mark.parametrize("name", derivatives.TYPE_3_NAMES)
def test_derivative_selectors_are_point_in_time_bounded_and_deterministic(name):
    implementation = REGISTRY.v2_implementation_registrations[
        (logic_state.component_id("TYPE_3", name), 1)
    ].implementation
    parameters = {
        "window": 1, "entry_blocked": False, "maximum_members": 3,
        "required_count": 1,
    }
    fact = _derivative_fact(
        name, capability=name in derivatives.CAPABILITY_GATED_NAMES,
    )
    context = _derivative_evaluation_context(fact)
    first = implementation(
        parameters, {"input": fact}, evaluation_context=context,
    )["value"]
    second = implementation(
        parameters, {"input": fact}, evaluation_context=context,
    )["value"]
    assert first == second
    assert first["knowledge_time"] == "2026-08-26T00:01:00+00:00"
    assert len(first["member_addresses"]) <= 3
    assert first["operation"] == name
    _assert_semantic_equal(first["value"], _type3_expected(fact)[name])


@pytest.mark.parametrize("name", derivatives.CAPABILITY_GATED_NAMES)
def test_unsupported_provider_supplied_derivatives_refuse_without_fallback(name):
    implementation = REGISTRY.v2_implementation_registrations[
        (logic_state.component_id("TYPE_3", name), 1)
    ].implementation
    fact = _derivative_fact(
        name, capability=False, provider_declared=True,
    )
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="CAPABILITY_REQUIRED"):
        implementation(
            {"window": 1, "entry_blocked": False, "maximum_members": 3,
             "required_count": 1},
            {"input": fact}, evaluation_context=_derivative_evaluation_context(fact),
        )


@pytest.mark.parametrize("name", derivatives.TYPE_3_NAMES)
def test_type3_contract_declaration_role_policy_and_capability_supply_agree(name):
    gated = name in derivatives.CAPABILITY_GATED_NAMES
    key = (f"derivative.{name.lower()}", 1)
    provider_requirement = content_address({"provider-capability": name})
    assert tuple(REGISTRY.node_contracts[key]["provider_requirements"]) == (
        (provider_requirement,) if gated else ()
    )
    declaration = REGISTRY.data_requirement_declarations[key]
    assert declaration["requirements"][0]["derived_local"]["literal"] is (not gated)
    fact = _derivative_fact(name, capability=gated)
    assert tuple(fact["role_requirement"]["provider_requirement_addresses"]) == (
        (provider_requirement,) if gated else ()
    )
    assert fact["selector_policy"]["provider_requirement_address"] == (
        provider_requirement if gated else None
    )
    if gated:
        capability_fact = fact["capability_assessment_envelope"]["fact"]
        assert capability_fact["requirement_results"] == [{
            "selector": provider_requirement, "result": "SATISFIED",
            "reason": "one declared offer covers the complete requirement",
        }]
    else:
        assert fact["capability_assessment_envelope"] is None
        assert fact["capability_evidence_address"] is None


def test_type3_context_is_keyword_only_and_cannot_be_substituted_by_graph_input():
    fact = _derivative_fact("BASIS")
    context = _derivative_evaluation_context(fact)
    implementation = REGISTRY.v2_implementation_registrations[
        ("derivative.basis", 1)
    ].implementation
    parameters = {"window": 1, "entry_blocked": False,
                  "maximum_members": 3, "required_count": 1}
    for inputs in (
        {"input": fact},
        {"input": fact, "evaluation_context": context},
    ):
        with pytest.raises(
            logic_state.FirstPartyCatalogueRefusal,
            match="DERIVATIVE_EVALUATION_CONTEXT_REQUIRED",
        ):
            implementation(parameters, inputs)


def test_coordinated_graph_authored_type3_authority_readdressing_refuses():
    fact = _derivative_fact("BASIS")
    accepted_context = _derivative_evaluation_context(fact)
    fact["source_address"] = _address("coordinated-source")
    fact["acceptance_evidence_address"] = _address("coordinated-acceptance")
    fact["rulebook_snapshot_address"] = _address("coordinated-rulebook")
    policy = fact["selector_policy"]
    policy["accepted_source_address"] = fact["source_address"]
    policy["acceptance_evidence_address"] = fact["acceptance_evidence_address"]
    policy["rulebook_snapshot_address"] = fact["rulebook_snapshot_address"]
    policy["policy_address"] = content_address({
        key: item for key, item in policy.items() if key != "policy_address"
    })
    fact["selector_policy_address"] = policy["policy_address"]
    _rehash_fact(fact)
    implementation = REGISTRY.v2_implementation_registrations[
        ("derivative.basis", 1)
    ].implementation
    with pytest.raises(
        logic_state.FirstPartyCatalogueRefusal,
        match="DERIVATIVE_EVALUATION_CONTEXT_MISMATCH",
    ):
        implementation(
            {"window": 1, "entry_blocked": False,
             "maximum_members": 3, "required_count": 1},
            {"input": fact}, evaluation_context=accepted_context,
        )


@pytest.mark.parametrize("name", logic_state.TYPE_5_NAMES)
def test_logic_temporal_validity_and_state_primitives_are_deterministic(name):
    implementation = REGISTRY.v2_implementation_registrations[
        (logic_state.component_id("TYPE_5", name), 1)
    ].implementation
    parameters = {
        "window": 2, "entry_blocked": False, "maximum_members": 1,
        "required_count": 1,
    }
    first = implementation(parameters, {"input": _type5_input(name)})["value"]
    second = implementation(parameters, {"input": _type5_input(name)})["value"]
    assert first == second
    _assert_type5_semantic(first, _type5_expected()[name])


@pytest.mark.parametrize("name", tuple(sorted(logic_state.STATEFUL_TYPE_5_NAMES)))
def test_stateful_batch_stream_and_warm_restart_prefixes_match(name):
    parameters = {"window": 2, "entry_blocked": False,
                  "maximum_members": 1, "required_count": 1}
    implementation = REGISTRY.v2_implementation_registrations[
        (f"logic.{name.lower()}", 1)
    ].implementation
    full = implementation(parameters, {"input": _state_prefix_input(name, 0, 4)})["value"]
    first = implementation(parameters, {"input": _state_prefix_input(name, 0, 2)})["value"]
    second_input = _state_prefix_input(name, 2, 4)
    second_input, _snapshot, restore_context = _snapshot_input(
        name, first.state_payload, initial_state=_declared_initial_state(name),
        reset_reasons=(), next_event_time="2026-08-26T00:02:00+00:00",
        last_event_time=first.last_event_time, length=2, base_value=second_input,
    )
    second = implementation(
        parameters, {"input": second_input}, evaluation_context=restore_context,
    )["value"]
    assert isinstance(full, logic_state.StateSeriesResult)
    assert first.values + second.values == full.values
    assert second.state_payload == full.state_payload
    assert second.last_event_time == full.last_event_time


@pytest.mark.parametrize("name", tuple(sorted(logic_state.STATEFUL_TYPE_5_NAMES)))
@pytest.mark.parametrize("reset_reason", (
    "ELAPSED_WINDOW", "EXPIRY_ROLL", "EXPLICIT", "POSITION_CLOSE", "SESSION",
))
def test_every_reset_reason_returns_each_stateful_node_to_declared_initial_state(
    name, reset_reason,
):
    parameters = {"window": 2, "entry_blocked": False,
                  "maximum_members": 1, "required_count": 1}
    implementation = REGISTRY.v2_implementation_registrations[
        (f"logic.{name.lower()}", 1)
    ].implementation
    first = implementation(parameters, {"input": _state_prefix_input(name, 0, 2)})["value"]
    second_fresh_input = _state_prefix_input(name, 2, 4)
    expected = implementation(parameters, {"input": second_fresh_input})["value"]
    restored_input = _state_prefix_input(name, 2, 4)
    restored_input, _snapshot, restore_context = _snapshot_input(
        name, first.state_payload, initial_state=_declared_initial_state(name),
        reset_reasons=(reset_reason,),
        next_event_time="2026-08-26T00:02:00+00:00",
        last_event_time=first.last_event_time, length=2, base_value=restored_input,
    )
    actual = implementation(
        parameters, {"input": restored_input}, evaluation_context=restore_context,
    )["value"]
    assert actual == expected


def test_counter_restart_reset_schedule_and_invalid_domains():
    parameters = {
        "window": 2, "entry_blocked": False, "maximum_members": 1,
        "required_count": 1,
    }
    counter = REGISTRY.v2_implementation_registrations[("logic.counter", 1)].implementation
    value, _snapshot, direct_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0, reset_reasons=(),
    )
    direct = counter(
        parameters, {"input": value}, evaluation_context=direct_context,
    )["value"]
    replay_value, _replay_snapshot, replay_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0,
        reset_reasons=("SESSION", "EXPLICIT"),
    )
    replay = counter(
        parameters, {"input": replay_value}, evaluation_context=replay_context,
    )["value"]
    assert direct != replay
    ordered_value, _ordered_snapshot, ordered_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0,
        reset_reasons=("EXPLICIT", "SESSION"),
    )
    ordered = counter(
        parameters, {"input": ordered_value}, evaluation_context=ordered_context,
    )["value"]
    assert replay == ordered
    divide = REGISTRY.v2_implementation_registrations[("logic.divide", 1)].implementation
    undefined = divide(parameters, {"input": {
        "left": valid(2.0), "right": valid(0.0),
    }})["value"]
    assert undefined.state is ValidityState.MATHEMATICALLY_UNDEFINED


def test_dynamic_window_and_missing_point_in_time_refuse():
    selector = REGISTRY.v2_implementation_registrations[("derivative.atm_plus_minus_n", 1)].implementation
    parameters = {
        "window": 1, "entry_blocked": False, "maximum_members": 1,
        "required_count": 1,
    }
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="POINT_IN_TIME"):
        selector(parameters, {"input": {"members": ()}})
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="DYNAMIC_WINDOW"):
        fact = _derivative_fact(
            "ATM_PLUS_MINUS_N", members=2, maximum_members=1,
        )
        selector(
            parameters, {"input": fact},
            evaluation_context=_derivative_evaluation_context(fact),
        )


def test_point_in_time_authority_and_operation_specific_derivatives():
    parameters = {"window": 1, "entry_blocked": False,
                  "maximum_members": 3, "required_count": 1}
    straddle = REGISTRY.v2_implementation_registrations[("derivative.straddle_price", 1)].implementation
    straddle_fact = _derivative_fact("STRADDLE_PRICE")
    result = straddle(
        parameters, {"input": straddle_fact},
        evaluation_context=_derivative_evaluation_context(straddle_fact),
    )["value"]
    assert result["value"] == 18.0
    basis = REGISTRY.v2_implementation_registrations[("derivative.basis", 1)].implementation
    basis_fact = _derivative_fact("BASIS")
    assert basis(
        parameters, {"input": basis_fact},
        evaluation_context=_derivative_evaluation_context(basis_fact),
    )["value"]["value"] == 2.0
    future = _derivative_fact("BASIS"); future["knowledge_time"] = None
    _rehash_fact(future)
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="knowledge_time"):
        basis(
            parameters, {"input": future},
            evaluation_context=_derivative_evaluation_context(future),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("wrong-source", "SELECTOR_POLICY_MISMATCH"),
        ("future-knowledge", "POINT_IN_TIME_ORDER_INVALID"),
        ("stale-rulebook", "SELECTOR_POLICY_MISMATCH"),
        ("role-bound", "CANONICAL_ROLE_MISMATCH"),
        ("member-fact", "DERIVATIVE_MEMBER_ADDRESS_MISMATCH"),
        ("fact-address", "POINT_IN_TIME_FACT_ADDRESS_MISMATCH"),
    ),
)
def test_point_in_time_fact_rejects_wrong_or_stale_authority(mutation, message):
    fact = _derivative_fact("BASIS")
    if mutation == "wrong-source":
        fact["source_address"] = _address("wrong-source")
        _rehash_fact(fact)
    elif mutation == "future-knowledge":
        fact["knowledge_time"] = "2026-08-26T00:03:00+00:00"
        _rehash_fact(fact)
    elif mutation == "stale-rulebook":
        fact["rulebook_snapshot_address"] = _address("new-rulebook")
        _rehash_fact(fact)
    elif mutation == "role-bound":
        fact["role_requirement"]["maximum_members"] = 2
        fact["role_requirement_address"] = content_address({
            "schema": "instrument-role-requirement/1", **fact["role_requirement"],
        })
        _rehash_fact(fact)
    elif mutation == "member-fact":
        fact["members"][0]["values"]["price"] = 99.0
        _rehash_fact(fact)
    else:
        fact["fact_address"] = _address("forged-fact")
    context = _derivative_evaluation_context(fact)
    implementation = REGISTRY.v2_implementation_registrations[("derivative.basis", 1)].implementation
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match=message):
        implementation({
            "window": 1, "entry_blocked": False,
            "maximum_members": 3, "required_count": 1,
        }, {"input": fact}, evaluation_context=context)


def test_capability_assessment_must_be_satisfied_current_and_exactly_bound():
    name = "BEST_BID"
    fact = _derivative_fact(name, capability=True)
    capability_fact = fact["capability_assessment_envelope"]["fact"]
    capability_fact["requirement_results"][0].update(
        result="UNAVAILABLE", reason="entitlement is not verified",
    )
    fact["capability_evidence_address"] = canonical_fact_address(
        CAPABILITY_ASSESSMENT_SCHEMA, capability_fact,
    )
    _rehash_fact(fact)
    implementation = REGISTRY.v2_implementation_registrations[("derivative.best_bid", 1)].implementation
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="ACCEPTED_CAPABILITY_REQUIRED"):
        implementation({
            "window": 1, "entry_blocked": False,
            "maximum_members": 3, "required_count": 1,
        }, {"input": fact},
        evaluation_context=_derivative_evaluation_context(fact))


def test_truth_validity_temporal_and_numeric_domains_are_distinct():
    parameters = {"window": 2, "entry_blocked": False,
                  "maximum_members": 1, "required_count": 1}
    and_impl = REGISTRY.v2_implementation_registrations[("logic.and", 1)].implementation
    assert and_impl(parameters, {"input": {
        "left": valid(True), "right": valid(False)
    }})["value"] == valid(False)
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="boolean"):
        and_impl(parameters, {"input": {
            "left": valid(1.0), "right": valid(True)
        }})
    power = REGISTRY.v2_implementation_registrations[("logic.power", 1)].implementation
    assert power(parameters, {"input": {
        "left": valid(-1.0), "right": valid(0.5)
    }})["value"].state is ValidityState.MATHEMATICALLY_UNDEFINED
    between = REGISTRY.v2_implementation_registrations[("logic.between", 1)].implementation
    assert between(parameters, {"input": {
        "left": valid(1), "right": valid(0),
        "lower": valid(2), "upper": valid(1),
    }})["value"].state is ValidityState.MATHEMATICALLY_UNDEFINED
    a_then_b = REGISTRY.v2_implementation_registrations[("logic.a_then_b", 1)].implementation
    bars_since = REGISTRY.v2_implementation_registrations[("logic.bars_since", 1)].implementation
    value = _generic_input()
    assert tuple(item.value for item in a_then_b(
        parameters, {"input": value},
    )["value"].values) == (False, True, False, True)
    assert tuple(item.value for item in bars_since(
        parameters, {"input": value},
    )["value"].values) == (0, 1, 2, 0)


@pytest.mark.parametrize("state", tuple(sorted(
    logic_state.FROZEN_VALIDITY_STATES, key=lambda item: item.value,
)))
def test_all_eight_frozen_validity_states_are_explicitly_preserved(state):
    parameters = {"window": 2, "entry_blocked": False,
                  "maximum_members": 1, "required_count": 1}
    left = valid(2.0) if state is ValidityState.VALID else invalid(state)
    add = REGISTRY.v2_implementation_registrations[("logic.add", 1)].implementation
    result = add(parameters, {"input": {
        "left": left, "right": valid(1.0),
    }})["value"]
    assert result == (valid(3.0) if state is ValidityState.VALID else invalid(state))
    predicates = {
        "IS_VALID": state is ValidityState.VALID,
        "IS_MISSING": state is ValidityState.MISSING,
        "IS_STALE": state is ValidityState.STALE,
        "IS_UNDEFINED": state is ValidityState.MATHEMATICALLY_UNDEFINED,
    }
    for name, expected in predicates.items():
        implementation = REGISTRY.v2_implementation_registrations[
            (f"logic.{name.lower()}", 1)
        ].implementation
        assert implementation(parameters, {"input": {"left": left}})["value"] == valid(expected)


@pytest.mark.parametrize("state", (ValidityState.NO_TRADE, ValidityState.INVALID))
def test_non_v1_validity_states_refuse_at_catalogue_boundary(state):
    implementation = REGISTRY.v2_implementation_registrations[("logic.add", 1)].implementation
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="non-V1"):
        implementation({
            "window": 1, "entry_blocked": False,
            "maximum_members": 1, "required_count": 1,
        }, {"input": {"left": invalid(state), "right": valid(1.0)}})


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("DIVIDE", {"left": valid(2.0), "right": valid(0.0)}),
        ("MODULO", {"left": valid(2.0), "right": valid(0.0)}),
        ("POWER", {"left": valid(-1.0), "right": valid(0.5)}),
        ("LOG", {"left": valid(0.0)}),
        ("SQRT", {"left": valid(-1.0)}),
        ("BETWEEN", {
            "left": valid(1.0), "right": valid(0.0),
            "lower": valid(2.0), "upper": valid(1.0),
        }),
        ("CLAMP", {
            "left": valid(1.0), "right": valid(0.0),
            "lower": valid(2.0), "upper": valid(1.0),
        }),
        ("ADD", {"left": valid(1e308), "right": valid(1e308)}),
    ),
)
def test_invalid_numeric_domains_never_emit_executable_values(name, value):
    implementation = REGISTRY.v2_implementation_registrations[
        (f"logic.{name.lower()}", 1)
    ].implementation
    result = implementation({
        "window": 1, "entry_blocked": False,
        "maximum_members": 1, "required_count": 1,
    }, {"input": value})["value"]
    assert result == invalid(ValidityState.MATHEMATICALLY_UNDEFINED)


def test_explicit_fallback_only_consumes_declared_validity_states():
    parameters = {"window": 1, "entry_blocked": False,
                  "maximum_members": 1, "required_count": 1}
    implementation = REGISTRY.v2_implementation_registrations[
        ("logic.explicit_fallback", 1)
    ].implementation
    value = {"left": invalid(ValidityState.STALE), "right": valid(0.0),
             "fallback": valid(7.0), "fallback_states": ("MISSING",)}
    assert implementation(parameters, {"input": value})["value"] == invalid(ValidityState.STALE)
    value["fallback_states"] = ("STALE",)
    assert implementation(parameters, {"input": value})["value"] == valid(7.0)


def test_verified_snapshot_restore_and_stale_snapshot_refusal():
    value, _snapshot, restore_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0, reset_reasons=(),
    )
    parameters = {"window": 1, "entry_blocked": False,
                  "maximum_members": 1, "required_count": 1}
    counter = REGISTRY.v2_implementation_registrations[("logic.counter", 1)].implementation
    assert counter(
        parameters, {"input": value}, evaluation_context=restore_context,
    )["value"].values[0].value == 5.0
    stale_time = "2026-08-25T23:59:00+00:00"
    stale_address = _address(f"event-{stale_time}")
    stale = {
        **value, "next_event_time": stale_time,
        "next_event_address": stale_address,
        "event_times": tuple(
            (dt.datetime.fromisoformat(stale_time) + dt.timedelta(minutes=index)).isoformat()
            for index in range(4)
        ),
    }
    stale_context = logic_state.StateRestoreContext(
        **{
            **restore_context.__dict__, "next_event_time": stale_time,
            "next_event_address": stale_address,
        }
    )
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="EVENT_ORDER"):
        counter(
            parameters, {"input": stale}, evaluation_context=stale_context,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("node-contract", "NODE_CONTRACT_MISMATCH"),
        ("implementation", "CONTEXT_MISMATCH"),
        ("dataset", "CONTEXT_MISMATCH"),
        ("state-bytes", "BYTES_MISMATCH"),
        ("reset-policy", "RESET_POLICY_MISMATCH"),
        ("validity", "VALIDITY_INVALID"),
        ("future-event", "EVENT_ORDER"),
    ),
)
def test_snapshot_restore_refuses_stale_identity_bytes_validity_and_time(mutation, message):
    value, snapshot, restore_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0, reset_reasons=(),
    )
    facts = {
        key: item for key, item in snapshot.document.items()
        if key not in {"schema", "snapshot_address"}
    }
    if mutation == "node-contract":
        facts["node_contract_address"] = _address("wrong-node-contract")
    elif mutation == "implementation":
        facts["implementation_closure_address"] = _address("wrong-implementation")
    elif mutation == "dataset":
        facts["dataset_context_address"] = _address("wrong-dataset")
    elif mutation == "state-bytes":
        value["state_payload"] = 6.0
    elif mutation == "reset-policy":
        facts["reset_policy_address"] = _address("wrong-reset-policy")
    elif mutation == "validity":
        facts["validity_state"] = "MISSING"
    else:
        facts["last_event_time"] = value["next_event_time"]
    if mutation != "state-bytes":
        mutated = canonical_state_snapshot(state_snapshot_document(**facts))
        value["snapshot"] = mutated
        if mutation in {"node-contract", "reset-policy", "validity", "future-event"}:
            restore_context = _state_restore_context(
                mutated, reset_reasons=(), next_event_time=value["next_event_time"],
            )
    implementation = REGISTRY.v2_implementation_registrations[("logic.counter", 1)].implementation
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match=message):
        implementation({
            "window": 1, "entry_blocked": False,
            "maximum_members": 1, "required_count": 1,
        }, {"input": value}, evaluation_context=restore_context)


def test_state_payload_cannot_restore_without_a_verified_snapshot():
    value = _state_prefix_input("COUNTER", 0, 2)
    value["state_payload"] = 99.0
    implementation = REGISTRY.v2_implementation_registrations[("logic.counter", 1)].implementation
    with pytest.raises(logic_state.FirstPartyCatalogueRefusal, match="REQUIRES_SNAPSHOT"):
        implementation({
            "window": 1, "entry_blocked": False,
            "maximum_members": 1, "required_count": 1,
        }, {"input": value})


@pytest.mark.parametrize("missing_field", (
    "schema", "last_event_address", "creation_evidence_address", "reset_reasons",
))
def test_incomplete_duck_typed_snapshot_never_restores(missing_field):
    value, snapshot, restore_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0, reset_reasons=(),
    )
    incomplete = dict(snapshot.document)
    incomplete.pop(missing_field)
    incomplete.pop("snapshot_address", None)
    forged_address = content_address(incomplete)
    incomplete["snapshot_address"] = forged_address
    value["snapshot"] = SimpleNamespace(
        document=incomplete, snapshot_address=forged_address,
    )
    implementation = REGISTRY.v2_implementation_registrations[
        ("logic.counter", 1)
    ].implementation
    with pytest.raises(
        logic_state.FirstPartyCatalogueRefusal,
        match="CANONICAL_STATE_SNAPSHOT_REQUIRED",
    ):
        implementation(
            {"window": 1, "entry_blocked": False,
             "maximum_members": 1, "required_count": 1},
            {"input": value}, evaluation_context=restore_context,
        )


def test_complete_duck_typed_snapshot_never_substitutes_for_canonical_type():
    value, snapshot, restore_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0, reset_reasons=(),
    )
    value["snapshot"] = SimpleNamespace(
        document=dict(snapshot.document),
        snapshot_address=snapshot.snapshot_address,
    )
    implementation = REGISTRY.v2_implementation_registrations[
        ("logic.counter", 1)
    ].implementation
    with pytest.raises(
        logic_state.FirstPartyCatalogueRefusal,
        match="CANONICAL_STATE_SNAPSHOT_REQUIRED",
    ):
        implementation(
            {"window": 1, "entry_blocked": False,
             "maximum_members": 1, "required_count": 1},
            {"input": value}, evaluation_context=restore_context,
        )


def test_restore_context_is_keyword_only_and_caller_identity_map_is_forbidden():
    value, _snapshot, restore_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0, reset_reasons=(),
    )
    implementation = REGISTRY.v2_implementation_registrations[
        ("logic.counter", 1)
    ].implementation
    parameters = {"window": 1, "entry_blocked": False,
                  "maximum_members": 1, "required_count": 1}
    with pytest.raises(
        logic_state.FirstPartyCatalogueRefusal,
        match="STATE_RESTORE_CONTEXT_REQUIRED",
    ):
        implementation(parameters, {
            "input": {**value, "evaluation_context": restore_context},
        })
    caller_identity = {
        field: value["snapshot"].document[field] for field in (
            "strategy_address", "resolved_graph_address", "node_contract_address",
            "implementation_closure_address", "dataset_context_address",
            "evaluation_context_address", "reset_policy_address",
        )
    }
    with pytest.raises(
        logic_state.FirstPartyCatalogueRefusal,
        match="CALLER_SNAPSHOT_IDENTITY_FORBIDDEN",
    ):
        implementation(
            parameters,
            {"input": {**value, "expected_snapshot_identity": caller_identity}},
            evaluation_context=restore_context,
        )


def test_coordinated_snapshot_identity_replacement_refuses_against_evaluator_context():
    value, snapshot, accepted_context = _snapshot_input(
        "COUNTER", 5.0, initial_state=0.0, reset_reasons=(),
    )
    facts = {
        key: item for key, item in snapshot.document.items()
        if key not in {"schema", "snapshot_address"}
    }
    facts.update(
        implementation_closure_address=_address("coordinated-implementation"),
        dataset_context_address=_address("coordinated-dataset"),
        evaluation_context_address=_address("coordinated-evaluation"),
        last_event_address=_address("coordinated-last-event"),
        creation_evidence_address=_address("coordinated-creation"),
    )
    value["snapshot"] = canonical_state_snapshot(state_snapshot_document(**facts))
    implementation = REGISTRY.v2_implementation_registrations[
        ("logic.counter", 1)
    ].implementation
    with pytest.raises(
        logic_state.FirstPartyCatalogueRefusal,
        match="STATE_RESTORE_CONTEXT_MISMATCH",
    ):
        implementation(
            {"window": 1, "entry_blocked": False,
             "maximum_members": 1, "required_count": 1},
            {"input": value}, evaluation_context=accepted_context,
        )
