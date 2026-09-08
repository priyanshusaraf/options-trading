from __future__ import annotations

import ast
import copy
from pathlib import Path
from types import MappingProxyType

import pytest

from app.ir import custom_nodes as custom_nodes_module
from app.ir.custom_nodes import (
    CUSTOM_LEVELS,
    CustomNodeAdmission,
    CustomNodeRefusal,
    RuntimeUnavailableDecision,
    admit_custom_node,
    evaluate_custom_node,
)
from app.ir.hashing import content_address
from app.ir.validity import ValidityState, invalid, valid


def _address(name: str) -> str:
    return content_address({"fixture": name})


def _plain(value):
    if isinstance(value, dict) or isinstance(value, MappingProxyType):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _readdress(document):
    plain = _plain(document)
    plain.pop("admission_address", None)
    address = content_address(plain)
    plain["admission_address"] = address
    return MappingProxyType(plain), address


def _unavailable_for(document, address):
    if document["level"] not in {
        "LEVEL_3_SANDBOXED_PYTHON_CONTRACT",
        "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT",
    }:
        return None
    return RuntimeUnavailableDecision(
        "custom-node-runtime-decision/1", document["level"], address,
        "UNAVAILABLE", "SECURITY_OWNER_GATE_REQUIRED",
    )


def _python_source() -> str:
    return "import math\n\ndef transform(left, right):\n    return math.fabs(left) + right\n"


def _external_contract(tenant_id="tenant-a"):
    return {
        "source_tenant_id": tenant_id,
        "schema_address": _address("external-schema"),
        "authentication_policy_address": _address("external-auth"),
        "replay_policy_address": _address("external-replay"),
        "declared_fields": ["left", "right"],
        "maximum_payload_bytes": 4096,
    }


def _python_contract(tenant_id="tenant-a", source_text=None):
    return {
        "source_tenant_id": tenant_id,
        "source_text": source_text or _python_source(),
        "entrypoint": "transform",
        "declared_imports": ["math"],
        "declared_inputs": ["left", "right"],
        "declared_capabilities": ["PURE_COMPUTE"],
    }


def _lineage(level: str, *, source_address=None, python_contract=None,
             external_contract=None):
    result = {_address("author-evidence")}
    if source_address is not None:
        result.add(source_address)
    if level == "LEVEL_3_SANDBOXED_PYTHON_CONTRACT":
        source = (python_contract or _python_contract())["source_text"]
        result.add(content_address({"python-source": source}))
    if level == "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT":
        external = external_contract or _external_contract()
        result.update({
            external["schema_address"], external["authentication_policy_address"],
            external["replay_policy_address"],
        })
    return sorted(result)


def _node_contract(level: str, node_id: str, version: int, lineage):
    enabled = level in {"LEVEL_1_FORK", "LEVEL_2_FORMULA"}
    return {
        "stable_node_id": f"custom.tenant-a.{node_id}",
        "semantic_version": version,
        "visible_family": "TYPE_5",
        "input_types": {"left": "number/scalar", "right": "number/scalar"},
        "output_types": {"value": "number/scalar"},
        "required_market_fields": ["close"],
        "required_resolution": {"timeframe_seconds": 60, "alignment": "BAR_CLOSE"},
        "warmup_history": 3,
        "execution_form": "STATELESS",
        "state_initialization": {
            "schema": "state-initialization/1", "initial_state_address": None,
        },
        "state_reset_policy": {"schema": "state-reset-policy/1", "reasons": []},
        "bar_policy": "COMPLETED_ONLY",
        "missing_data_policy": "PROPAGATE",
        "numeric_validity_policy": "EXPLICIT_VALIDITY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"],
        "streaming_support": enabled,
        "batch_support": enabled,
        "mode_eligibility": {
            "research": enabled, "paper": enabled, "live": False,
        },
        "provider_requirements": [],
        "resource_profile": {
            "compute_microseconds_per_event": 250,
            "memory_bytes_upper_bound": 4096,
            "history_bytes_upper_bound": 4096,
            "state_bytes_upper_bound": 0,
            "storage_bytes_per_day_upper_bound": 0,
            "subscription_count_upper_bound": 0,
            "fanout_upper_bound": 8,
        },
        "reference_provenance": list(sorted(lineage)),
    }


def _data_contract():
    return {
        "schema": "custom-data-contract/1",
        "instrument_role_addresses": [_address("primary-role")],
        "provider_requirement_addresses": [],
        "required_fields": ["close"],
        "timeframe_seconds": 60,
        "history_bars": 3,
        "alignment": "BAR_CLOSE",
        "bar_policy": "COMPLETED_ONLY",
    }


def _proposal(
    level="LEVEL_2_FORMULA", *, node_id="formula", version=1,
    source_address=None, formula="left * 2 + right", python_contract=None,
    external_contract=None,
):
    if level == "LEVEL_3_SANDBOXED_PYTHON_CONTRACT":
        python_contract = python_contract or _python_contract()
    if level == "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT":
        external_contract = external_contract or _external_contract()
    lineage = _lineage(
        level, source_address=source_address, python_contract=python_contract,
        external_contract=external_contract,
    )
    return {
        "schema": "custom-node-proposal/1",
        "level": level,
        "tenant_id": "tenant-a",
        "custom_node_id": node_id,
        "custom_node_version": version,
        "visible_family": "TYPE_5",
        "input_types": {"left": "number/scalar", "right": "number/scalar"},
        "output_types": {"value": "number/scalar"},
        "node_contract": _node_contract(level, node_id, version, lineage),
        "data_contract": _data_contract(),
        "trigger_rate": {"events": 2, "per_seconds": 2},
        "lineage_addresses": lineage,
        "fork_source_address": source_address if level == "LEVEL_1_FORK" else None,
        "formula": formula if level == "LEVEL_2_FORMULA" else None,
        "python_contract": python_contract if level == "LEVEL_3_SANDBOXED_PYTHON_CONTRACT" else None,
        "external_signal_contract": (
            external_contract if level == "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT" else None
        ),
    }


def _formula_admission():
    return admit_custom_node(_proposal())


def _fork_proposal(source, *, node_id="fork", version=2, tenant_id="tenant-a"):
    proposal = _proposal(
        "LEVEL_1_FORK", node_id=node_id, version=version,
        source_address=source.admission_address, formula=None,
    )
    proposal["tenant_id"] = tenant_id
    proposal["node_contract"]["stable_node_id"] = f"custom.{tenant_id}.{node_id}"
    proposal["node_contract"]["reference_provenance"] = sorted(set((
        *source.node_contract.document["reference_provenance"], source.admission_address,
    )))
    proposal["lineage_addresses"] = list(
        proposal["node_contract"]["reference_provenance"]
    )
    return proposal


@pytest.mark.parametrize("level", CUSTOM_LEVELS)
def test_all_four_levels_have_closed_immutable_addressed_contracts(level):
    if level == "LEVEL_1_FORK":
        source = _formula_admission()
        admission = admit_custom_node(_fork_proposal(source), source=source)
    else:
        admission = admit_custom_node(_proposal(level, node_id=level.lower()))
    assert admission.document["schema"] == "custom-node-admission/1"
    assert admission.document["level"] == level
    assert admission.document["node_contract_address"] == admission.node_contract.contract_address
    assert admission.document["admission_address"] == admission.admission_address
    assert len(admission.node_contract.document) == 22
    assert admission.document["trigger_rate"] == {"events": 1, "per_seconds": 1}
    with pytest.raises(TypeError):
        admission.document["tenant_id"] = "tenant-b"
    if level in {"LEVEL_3_SANDBOXED_PYTHON_CONTRACT",
                 "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT"}:
        assert admission.document["runtime_status"] == "UNAVAILABLE"
        assert isinstance(admission.runtime_decision, RuntimeUnavailableDecision)
    else:
        assert admission.document["runtime_status"] == "CONTRACT_EVALUABLE"
        assert admission.runtime_decision is None


def test_formula_and_fork_use_only_declared_inputs_and_match_prefixes():
    source = _formula_admission()
    fork = admit_custom_node(_fork_proposal(source), source=source)
    expected = (valid(5.0), valid(7.0), valid(9.0))
    actual = tuple(evaluate_custom_node(
        source, {"left": valid(float(index)), "right": valid(3.0)},
        tenant_id="tenant-a",
    ) for index in range(1, 4))
    replay = tuple(evaluate_custom_node(
        fork, {"left": valid(float(index)), "right": valid(3.0)},
        tenant_id="tenant-a",
    ) for index in range(1, 4))
    assert actual == expected == replay
    assert fork.formula_expression == source.formula_expression
    assert source.admission_address in fork.document["lineage_addresses"]
    assert evaluate_custom_node(
        source, {"left": invalid(ValidityState.STALE), "right": valid(3.0)},
        tenant_id="tenant-a",
    ) == invalid(ValidityState.STALE)
    with pytest.raises(CustomNodeRefusal, match="typed universe"):
        evaluate_custom_node(source, {"left": valid(1.0)}, tenant_id="tenant-a")
    with pytest.raises(CustomNodeRefusal, match="cross-tenant"):
        evaluate_custom_node(source, {
            "left": valid(1.0), "right": valid(2.0),
        }, tenant_id="tenant-b")


def test_admission_wrapper_cannot_swap_formula_or_contract_after_addressing():
    admission = _formula_admission()
    with pytest.raises(CustomNodeRefusal, match="only be constructed"):
        CustomNodeAdmission(
            admission.document, admission.admission_address,
            admission.node_contract, admission.data_contract,
            "left - right", admission.runtime_decision,
        )
    forged_data = copy.deepcopy(dict(admission.data_contract))
    forged_data["history_bars"] = 2
    with pytest.raises(CustomNodeRefusal):
        CustomNodeAdmission(
            admission.document, admission.admission_address,
            admission.node_contract, forged_data,
            admission.formula_expression, admission.runtime_decision,
        )


@pytest.mark.parametrize("mutation", ("level3-to-level2", "tenant", "open-level4"))
def test_coordinated_public_wrapper_readdressing_and_object_bypass_refuse(mutation):
    if mutation == "tenant":
        admission = _formula_admission()
    elif mutation == "level3-to-level2":
        admission = admit_custom_node(_proposal(
            "LEVEL_3_SANDBOXED_PYTHON_CONTRACT", node_id="python",
        ))
    else:
        admission = admit_custom_node(_proposal(
            "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT", node_id="external",
        ))
    document = _plain(admission.document)
    formula = admission.formula_expression
    decision = admission.runtime_decision
    if mutation == "tenant":
        document["tenant_id"] = "tenant-b"
    elif mutation == "level3-to-level2":
        document.update(
            level="LEVEL_2_FORMULA", formula="left + right",
            python_contract=None, runtime_status="CONTRACT_EVALUABLE",
        )
        formula = "left + right"
        decision = None
    else:
        document["external_signal_contract"]["endpoint_url"] = "https://example.com"
        document["external_signal_contract"]["runtime_enabled"] = True
    document.pop("admission_address")
    address = content_address(document)
    document["admission_address"] = address
    with pytest.raises(CustomNodeRefusal, match="only be constructed"):
        CustomNodeAdmission(
            MappingProxyType(document), address, admission.node_contract,
            admission.data_contract, formula, decision,
        )
    forged = object.__new__(CustomNodeAdmission)
    for name, value in (
        ("document", MappingProxyType(document)), ("admission_address", address),
        ("node_contract", admission.node_contract),
        ("data_contract", admission.data_contract),
        ("formula_expression", formula), ("runtime_decision", decision),
        ("source_admission", admission.source_admission),
        ("python_source_text", admission.python_source_text),
    ):
        object.__setattr__(forged, name, value)
    with pytest.raises(CustomNodeRefusal):
        evaluate_custom_node(forged, {
            "left": valid(1.0), "right": valid(2.0),
        }, tenant_id=document["tenant_id"])


@pytest.mark.parametrize("mutation", (
    "same-version", "cross-tenant", "resource-drift", "data-drift",
    "rate-drift", "missing-lineage", "wrong-source",
))
def test_fork_must_inherit_and_version_exact_source_contract(mutation):
    source = _formula_admission()
    proposal = _fork_proposal(source)
    if mutation == "same-version":
        proposal["custom_node_version"] = 1
        proposal["node_contract"]["semantic_version"] = 1
    elif mutation == "cross-tenant":
        proposal = _fork_proposal(source, tenant_id="tenant-b")
    elif mutation == "resource-drift":
        proposal["node_contract"]["resource_profile"]["memory_bytes_upper_bound"] += 1
    elif mutation == "data-drift":
        proposal["data_contract"]["history_bars"] = 2
    elif mutation == "rate-drift":
        proposal["trigger_rate"] = {"events": 2, "per_seconds": 1}
    elif mutation == "missing-lineage":
        proposal["lineage_addresses"].remove(source.admission_address)
    else:
        proposal["fork_source_address"] = _address("wrong-source")
    with pytest.raises(CustomNodeRefusal):
        admit_custom_node(proposal, source=source)


def test_fork_cannot_drop_transitive_lineage_while_retaining_immediate_source():
    source_proposal = _proposal()
    extra = _address("second-source-evidence")
    source_proposal["lineage_addresses"] = sorted((
        *source_proposal["lineage_addresses"], extra,
    ))
    source_proposal["node_contract"]["reference_provenance"] = list(
        source_proposal["lineage_addresses"]
    )
    source = admit_custom_node(source_proposal)
    fork = _fork_proposal(source)
    fork["lineage_addresses"].remove(extra)
    with pytest.raises(CustomNodeRefusal, match="transitive source"):
        admit_custom_node(fork, source=source)


def test_multi_generation_forks_reconstruct_every_ancestor_and_evaluate():
    source = _formula_admission()
    first = admit_custom_node(_fork_proposal(source, node_id="fork-one", version=2), source=source)
    second = admit_custom_node(_fork_proposal(first, node_id="fork-two", version=3), source=first)
    assert tuple(second.document["lineage_addresses"]) == tuple(sorted(set((
        *first.document["lineage_addresses"], first.admission_address,
    ))))
    assert source.admission_address in second.document["lineage_addresses"]
    assert first.admission_address in second.document["lineage_addresses"]
    assert evaluate_custom_node(second, {
        "left": valid(2.0), "right": valid(1.0),
    }, tenant_id="tenant-a") == valid(5.0)


@pytest.mark.parametrize("mutation", (
    "fork-source", "fork-lineage", "python-source", "external-auth",
    "external-provenance",
))
def test_private_factory_and_object_reconstruction_require_exact_retained_proof(mutation):
    source = None
    if mutation.startswith("fork"):
        source = _formula_admission()
        admission = admit_custom_node(_fork_proposal(source), source=source)
    elif mutation == "python-source":
        admission = admit_custom_node(_proposal(
            "LEVEL_3_SANDBOXED_PYTHON_CONTRACT", node_id="python-proof",
        ))
    else:
        admission = admit_custom_node(_proposal(
            "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT", node_id="external-proof",
        ))
    document = _plain(admission.document)
    if mutation == "fork-source":
        document["fork_source_address"] = _address("substituted-source")
    elif mutation == "fork-lineage":
        document["lineage_addresses"] = [admission.document["fork_source_address"]]
    elif mutation == "python-source":
        document["python_contract"]["source_address"] = _address("substituted-python")
    else:
        document["external_signal_contract"]["authentication_policy_address"] = _address(
            "substituted-auth"
        )
        if mutation == "external-provenance":
            document["lineage_addresses"] = sorted(set((
                *document["lineage_addresses"],
                document["external_signal_contract"]["authentication_policy_address"],
            )))
    wrapped, address = _readdress(document)
    decision = _unavailable_for(wrapped, address)
    with pytest.raises(CustomNodeRefusal):
        custom_nodes_module._new_custom_admission(
            wrapped, address, admission.node_contract, admission.data_contract,
            admission.formula_expression, decision,
            source, admission.python_source_text,
        )
    forged = object.__new__(CustomNodeAdmission)
    for name, value in (
        ("document", wrapped), ("admission_address", address),
        ("node_contract", admission.node_contract),
        ("data_contract", admission.data_contract),
        ("formula_expression", admission.formula_expression),
        ("runtime_decision", decision), ("source_admission", source),
        ("python_source_text", admission.python_source_text),
    ):
        object.__setattr__(forged, name, value)
    with pytest.raises(CustomNodeRefusal):
        evaluate_custom_node(forged, {
            "left": valid(1.0), "right": valid(2.0),
        }, tenant_id="tenant-a")


def test_level3_retained_source_replays_scan_without_execution():
    admission = admit_custom_node(_proposal(
        "LEVEL_3_SANDBOXED_PYTHON_CONTRACT", node_id="retained-source",
    ))
    assert admission.python_source_text == _python_source()
    assert admission.document["python_contract"]["source_address"] == content_address({
        "python-source": admission.python_source_text,
    })
    assert evaluate_custom_node(admission, {}, tenant_id="tenant-a") \
        == admission.runtime_decision


@pytest.mark.parametrize("formula", (
    "undeclared + 1", "sum([left, right])", "left.__class__",
    "(lambda x: x)(left)", "[x for x in [left]]", "'secret'", "float('nan')",
))
def test_formula_forbidden_or_undeclared_constructs_refuse(formula):
    with pytest.raises(CustomNodeRefusal):
        admit_custom_node(_proposal(formula=formula))


def test_formula_numeric_domain_and_power_bounds_fail_closed():
    divide = admit_custom_node(_proposal(formula="left / right", node_id="divide"))
    with pytest.raises(CustomNodeRefusal, match="undefined"):
        evaluate_custom_node(divide, {
            "left": valid(1.0), "right": valid(0.0),
        }, tenant_id="tenant-a")


def test_formula_static_types_are_exact_and_boolean_truthiness_is_forbidden():
    boolean = _proposal(formula="left > right", node_id="compare")
    boolean["output_types"]["value"] = "boolean/scalar"
    boolean["node_contract"]["output_types"]["value"] = "boolean/scalar"
    admission = admit_custom_node(boolean)
    assert evaluate_custom_node(admission, {
        "left": valid(2.0), "right": valid(1.0),
    }, tenant_id="tenant-a") == valid(True)
    with pytest.raises(CustomNodeRefusal, match="output type"):
        admit_custom_node(_proposal(formula="left > right", node_id="wrong-output"))
    with pytest.raises(CustomNodeRefusal, match="boolean operands"):
        admit_custom_node(_proposal(formula="left and right", node_id="truthiness"))


@pytest.mark.parametrize(
    ("formula", "expected"),
    (
        ("False and (left / 0 > right)", False),
        ("True or (left / 0 > right)", True),
        ("True if left >= right else False", True),
    ),
)
def test_boolean_formula_short_circuit_and_conditionals_match_reference(formula, expected):
    proposal = _proposal(formula=formula, node_id="short-circuit")
    proposal["output_types"]["value"] = "boolean/scalar"
    proposal["node_contract"]["output_types"]["value"] = "boolean/scalar"
    admission = admit_custom_node(proposal)
    for left in (1.0, 2.0, 3.0):
        assert evaluate_custom_node(admission, {
            "left": valid(left), "right": valid(1.0),
        }, tenant_id="tenant-a") == valid(expected)
    power = admit_custom_node(_proposal(formula="left ** right", node_id="power"))
    with pytest.raises(CustomNodeRefusal, match="undefined"):
        evaluate_custom_node(power, {
            "left": valid(2.0), "right": valid(100.0),
        }, tenant_id="tenant-a")


@pytest.mark.parametrize("mutation", (
    "missing-profile", "bool-resource", "resource-over", "state-mismatch",
    "missing-family", "partial-bar", "empty-trigger", "rate-zero", "rate-bool",
    "rate-over", "provider-drift", "data-history-drift", "extra-field",
))
def test_missing_unbounded_or_conflicting_contracts_refuse(mutation):
    proposal = _proposal()
    if mutation == "missing-profile":
        proposal["node_contract"].pop("resource_profile")
    elif mutation == "bool-resource":
        proposal["node_contract"]["resource_profile"]["memory_bytes_upper_bound"] = True
    elif mutation == "resource-over":
        proposal["node_contract"]["resource_profile"]["memory_bytes_upper_bound"] = 65*1024*1024
    elif mutation == "state-mismatch":
        proposal["node_contract"]["resource_profile"]["state_bytes_upper_bound"] = 1
    elif mutation == "missing-family":
        proposal["visible_family"] = None
    elif mutation == "partial-bar":
        proposal["node_contract"]["bar_policy"] = "PARTIAL_ALLOWED"
        proposal["data_contract"]["bar_policy"] = "PARTIAL_ALLOWED"
    elif mutation == "empty-trigger":
        proposal["node_contract"]["evaluation_triggers"] = []
    elif mutation == "rate-zero":
        proposal["trigger_rate"] = {"events": 0, "per_seconds": 1}
    elif mutation == "rate-bool":
        proposal["trigger_rate"] = {"events": True, "per_seconds": 1}
    elif mutation == "rate-over":
        proposal["trigger_rate"] = {"events": 1001, "per_seconds": 1}
    elif mutation == "provider-drift":
        proposal["data_contract"]["provider_requirement_addresses"] = [_address("provider")]
    elif mutation == "data-history-drift":
        proposal["data_contract"]["history_bars"] = 2
    else:
        proposal["other"] = True
    with pytest.raises(CustomNodeRefusal):
        admit_custom_node(proposal)


@pytest.mark.parametrize("source,imports", (
    ("import os\n\ndef transform(left, right):\n return left\n", ["os"]),
    ("def transform(left, right):\n return open('x')\n", []),
    ("import socket\n\ndef transform(left, right):\n return left\n", ["socket"]),
    ("def transform(left, right):\n return broker.place_order(left)\n", []),
    ("def transform(left, right):\n return eval('left')\n", []),
    ("def transform(left, right):\n return 'https://example.com'\n", []),
    ("def transform(left, right):\n while True:\n  left += 1\n return left\n", []),
    ("sum([1, 2])\n\ndef transform(left, right):\n return left\n", []),
    ("def transform(left):\n return left\n", []),
    ("def transform(left, right):\n return tenant.lookup(left)\n", []),
    ("from decimal import __builtins__ as payload\n\ndef transform(left, right):\n return payload\n", ["decimal"]),
    ("import math as broker\n\ndef transform(left, right):\n return left\n", ["math"]),
))
def test_python_forbidden_import_filesystem_network_broker_and_order_corpus(source, imports):
    contract = _python_contract(source_text=source)
    contract["declared_imports"] = imports
    with pytest.raises(CustomNodeRefusal):
        admit_custom_node(_proposal(
            "LEVEL_3_SANDBOXED_PYTHON_CONTRACT", node_id="python",
            python_contract=contract,
        ))


@pytest.mark.parametrize("mutation", (
    "cross-tenant", "unknown-import", "capability", "input", "entrypoint", "extra",
))
def test_python_contract_identity_and_tenant_refusals(mutation):
    contract = _python_contract()
    if mutation == "cross-tenant": contract["source_tenant_id"] = "tenant-b"
    elif mutation == "unknown-import": contract["declared_imports"] = ["os"]
    elif mutation == "capability": contract["declared_capabilities"] = ["NETWORK"]
    elif mutation == "input": contract["declared_inputs"] = ["left"]
    elif mutation == "entrypoint": contract["entrypoint"] = "other"
    else: contract["other"] = True
    with pytest.raises(CustomNodeRefusal):
        admit_custom_node(_proposal(
            "LEVEL_3_SANDBOXED_PYTHON_CONTRACT", node_id="python",
            python_contract=contract,
        ))


@pytest.mark.parametrize("mutation", (
    "cross-tenant", "field", "size-zero", "size-over", "bad-auth", "extra",
))
def test_external_signal_contract_has_no_ingress_tenant_or_replay_escape(mutation):
    contract = _external_contract()
    if mutation == "cross-tenant": contract["source_tenant_id"] = "tenant-b"
    elif mutation == "field": contract["declared_fields"] = ["left"]
    elif mutation == "size-zero": contract["maximum_payload_bytes"] = 0
    elif mutation == "size-over": contract["maximum_payload_bytes"] = 1024*1024+1
    elif mutation == "bad-auth": contract["authentication_policy_address"] = "none"
    else: contract["endpoint_url"] = "https://example.com"
    with pytest.raises(CustomNodeRefusal):
        admit_custom_node(_proposal(
            "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT", node_id="external",
            external_contract=contract,
        ))


@pytest.mark.parametrize("level", (
    "LEVEL_3_SANDBOXED_PYTHON_CONTRACT", "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT",
))
def test_level3_and_level4_always_return_typed_runtime_unavailable(level):
    admission = admit_custom_node(_proposal(level, node_id=level.lower()))
    result = evaluate_custom_node(admission, {}, tenant_id="tenant-a")
    assert result == admission.runtime_decision
    assert result.status == "UNAVAILABLE"
    assert result.reason == "SECURITY_OWNER_GATE_REQUIRED"
    assert not admission.node_contract.document["mode_eligibility"]["research"]
    assert not admission.node_contract.document["streaming_support"]
    assert not admission.node_contract.document["batch_support"]


def test_custom_node_module_has_no_runtime_or_side_effect_imports():
    from app.ir import custom_nodes
    tree = ast.parse(Path(custom_nodes.__file__).read_text())
    imports = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }
    forbidden = {
        "app.engine", "app.execution", "app.providers", "app.ledger", "os",
        "pathlib", "requests", "socket", "subprocess", "urllib",
    }
    assert not any(any(name.startswith(prefix) for prefix in forbidden) for name in imports)
