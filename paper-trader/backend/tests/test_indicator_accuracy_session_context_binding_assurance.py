"""Fresh consumer assurance for the sealed session-context field grammar."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import session_data as session
from app.ir.first_party.analytical_v2.contracts import (
    ContractInputBindings,
    canonical_input_bindings,
)
from app.ir.registry import PlatformRegistry, _DATA_FIELDS
from app.ir.resolve import resolve_v2
from app.market_data.requirements import (
    DataRequirementRefusal,
    compile_data_requirement_plan,
    verify_data_requirement_plan,
)


ROOT = Path(__file__).resolve().parents[3]
PRE_MUTATION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/pre-mutation.json"
SESSION_FIELDS = frozenset({"SESSION_ID", "SESSION_OPEN_AT", "SESSION_CLOSE_AT"})


def address(label: str) -> str:
    return hashing.content_address({"session_context_assurance": label})


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [plain(item) for item in value]
    return value


def session_registry() -> PlatformRegistry:
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types=session.V2_TYPES,
        v2_components=session.V2_COMPONENTS,
        v2_implementations=session.V2_IMPLEMENTATIONS,
        node_contracts=session.NODE_CONTRACTS,
        contract_bindings=session.CONTRACT_BINDINGS,
    )


def parameters(name: str):
    if name == "OPENING_RANGE":
        return session.parameters_for(name, {"range_minutes": 15})
    if name == "PREVIOUS_SESSION_FIELDS":
        return session.parameters_for(name, {"field": "close"})
    if name == "ANCHORED_VWAP":
        return session.parameters_for(name, {"anchor_at": "2025-01-02T09:30:00+00:00"})
    return session.parameters_for(name)


def graph_document(registry: PlatformRegistry, name: str):
    key = session.component_key(name)
    descriptor = plain(registry.v2_components[key])
    graph_input = deepcopy(next(port for port in descriptor["ports"] if port["direction"] == "input"))
    graph_input["port_id"] = "bars"
    return {
        "format_version": 2,
        "strategy_id": "session-context-assurance",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Session context assurance", "description": None, "tags": []},
        "graph_inputs": [graph_input],
        "graph_outputs": [],
        "nodes": [{
            "node_id": "probe",
            "component": {"component_id": key[0], "component_version": key[1]},
            "parameters": plain(parameters(name)),
        }],
        "edges": [{
            "edge_id": "bars-to-probe",
            "source": {"scope": "graph_input", "port_id": "bars"},
            "target": {"scope": "node", "node_id": "probe", "port_id": "frame"},
            "binding": {"kind": "single"},
        }],
    }


def input_fact(*, fields, role="primary", session_name="INSTRUMENT_CALENDAR", derived_local=False):
    return {
        "schema": "canonical-input-binding/1",
        "owner_id": "org.session-context-assurance",
        "dataset_context_address": address("dataset-context"),
        "evaluation_context_address": address("evaluation-context"),
        "dataset_manifest_address": address("dataset-manifest"),
        "market_truth_address": address("market-truth"),
        "provider_product_address": address("provider-product"),
        "provider_contract_address": address("provider-contract"),
        "canonical_instrument_address": address("instrument"),
        "instrument": {"role": role, "type": "PHYSICAL"},
        "timeframe": 900,
        "fields": sorted(fields),
        "freshness": {"maximum_age_seconds": 900},
        "depth": {"kind": "NONE", "levels": None},
        "session": session_name,
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": derived_local,
    }


def input_context(fact, *, expected_address=None):
    return canonical_input_bindings(
        owner_id="org.session-context-assurance",
        dataset_context_address=address("dataset-context"),
        evaluation_context_address=address("evaluation-context"),
        bindings={"bars": fact},
        expected_source_addresses={"bars": expected_address or hashing.content_address(fact)},
    )


def compile_for(name: str, fact):
    registry = session_registry()
    resolved = resolve_v2(graph_document(registry, name), registry)
    context = input_context(fact)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)
    assert verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context) is not None
    receipt = plan.parameter_binding_provenance[0]["node_contract_binding"]
    return registry, resolved, context, plan, receipt


def test_closed_grammar_added_exactly_three_fields_and_real_consumers_use_each():
    import json

    before = frozenset(json.loads(PRE_MUTATION.read_text())["data_fields"])
    assert len(before) == 17
    assert frozenset(_DATA_FIELDS) - before == SESSION_FIELDS
    assert len(_DATA_FIELDS) == 20

    cases = {
        "BARS_SINCE_SESSION_OPEN": {"SESSION_ID", "SESSION_OPEN_AT"},
        "TIME_TO_SESSION_CLOSE": {"SESSION_ID", "SESSION_CLOSE_AT"},
    }
    consumed = set()
    for name, expected in cases.items():
        fact = input_fact(fields=expected | SESSION_FIELDS)
        _, resolved, _, plan, receipt = compile_for(name, fact)
        assert resolved.nodes[0].component == session.component_key(name)
        actual = {row["requirement"]["field"] for row in plan.requirements}
        assert actual == expected
        assert {row["field"] for row in receipt["bound_requirements"]} == expected
        consumed.update(actual)
    assert consumed == SESSION_FIELDS


@pytest.mark.parametrize("bad_field", ["SESSION_LABEL", "session_id", "SESSION_OPEN", "SESSION_CLOSE"])
def test_every_fourth_or_wrong_session_field_is_refused_before_materialization(bad_field):
    fact = input_fact(fields={"SESSION_ID", "SESSION_OPEN_AT", bad_field})
    with pytest.raises(node_contracts.NodeContractRefusal):
        input_context(fact)


def test_role_owner_and_source_address_forgeries_refuse_at_canonical_consumers():
    wrong_role = input_fact(fields={"SESSION_ID", "SESSION_OPEN_AT"}, role="peer")
    registry = session_registry()
    resolved = resolve_v2(graph_document(registry, "BARS_SINCE_SESSION_OPEN"), registry)
    with pytest.raises(DataRequirementRefusal):
        compile_data_requirement_plan(resolved, registry=registry, input_bindings=input_context(wrong_role))

    wrong_owner = input_fact(fields={"SESSION_ID", "SESSION_OPEN_AT"})
    wrong_owner["owner_id"] = "org.forged-owner"
    with pytest.raises(node_contracts.NodeContractRefusal):
        input_context(wrong_owner)

    fact = input_fact(fields={"SESSION_ID", "SESSION_OPEN_AT"})
    with pytest.raises(node_contracts.NodeContractRefusal):
        input_context(fact, expected_address=address("forged-source-address"))

    accepted = input_context(fact)
    with pytest.raises(node_contracts.NodeContractRefusal):
        ContractInputBindings(plain(accepted.document), address("forged-context-address"))


def test_session_and_derived_local_facts_are_not_silently_rewritten():
    fields = {"SESSION_ID", "SESSION_CLOSE_AT"}
    _, _, _, base_plan, base_receipt = compile_for("TIME_TO_SESSION_CLOSE", input_fact(fields=fields))
    _, _, _, local_plan, local_receipt = compile_for(
        "TIME_TO_SESSION_CLOSE", input_fact(fields=fields, derived_local=True)
    )
    assert {row["derived_local"] for row in base_receipt["bound_requirements"]} == {False}
    assert {row["derived_local"] for row in local_receipt["bound_requirements"]} == {True}
    assert base_plan.plan_address != local_plan.plan_address
    assert base_receipt["bound_contract_address"] != local_receipt["bound_contract_address"]

    _, _, _, _, wrong_session_receipt = compile_for(
        "TIME_TO_SESSION_CLOSE", input_fact(fields=fields, session_name="CONTINUOUS")
    )
    index = pd.date_range("2025-01-02T09:15:00Z", periods=1, freq="15min")
    inputs = {"frame": {
        "session_id": pd.Series(["XNSE:2025-01-02"], index=index),
        "session_close_at": pd.Series([pd.Timestamp("2025-01-02T10:00:00Z")], index=index),
    }}
    from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract
    wrong_bound = ResolvedNodeContract(wrong_session_receipt, wrong_session_receipt["bound_contract_address"])
    with pytest.raises(node_contracts.NodeContractRefusal, match="SESSION_DATA_CANONICAL_BINDING_REQUIRED"):
        session.evaluate("TIME_TO_SESSION_CLOSE", {}, inputs, bound_contract=wrong_bound)


def test_rehashed_bound_receipt_cannot_forge_owner_or_session_truth():
    _, _, _, _, receipt = compile_for(
        "BARS_SINCE_SESSION_OPEN", input_fact(fields={"SESSION_ID", "SESSION_OPEN_AT"})
    )
    from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract

    for mutate in (
        lambda document: document["input_binding"].update(owner_id="org.forged"),
        lambda document: document["input_binding"]["ports"]["frame"]["binding"].update(session="CONTINUOUS"),
        lambda document: document["input_binding"]["ports"]["frame"]["binding"].update(derived_local=True),
    ):
        forged = deepcopy(plain(receipt))
        mutate(forged)
        forged["bound_contract_address"] = hashing.content_address(
            {key: value for key, value in forged.items() if key != "bound_contract_address"}
        )
        transport = ResolvedNodeContract(forged, forged["bound_contract_address"])
        registry = session_registry()
        with pytest.raises(node_contracts.NodeContractRefusal):
            registry.bind_node_contract(
                session.component_key("BARS_SINCE_SESSION_OPEN"),
                {},
                transport.document["input_binding"],
            )
