"""Closed Phase 5 custom-node admission; Levels 3/4 never execute here."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import content_address
from app.ir.node_contracts import (
    NodeContract,
    NodeContractRefusal,
    VISIBLE_FAMILIES,
    canonical_node_contract,
)
from app.ir.resource_plan import ResourcePlanRefusal, bounded_rate
from app.ir.schema import is_content_address
from app.ir.validity import NumericValue, ValidityState, invalid, propagate, valid


CUSTOM_LEVELS = (
    "LEVEL_1_FORK",
    "LEVEL_2_FORMULA",
    "LEVEL_3_SANDBOXED_PYTHON_CONTRACT",
    "LEVEL_4_EXTERNAL_SIGNAL_CONTRACT",
)
RUNTIME_DISABLED_LEVELS = frozenset(CUSTOM_LEVELS[2:])
_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_MAX_INPUTS = 64
_MAX_FORMULA_NODES = 256
_MAX_FORMULA_BYTES = 8 * 1024
_MAX_PYTHON_BYTES = 64 * 1024
_MAX_EXTERNAL_PAYLOAD_BYTES = 1024 * 1024
_MAX_EVENTS_PER_SECOND = 1000
_RESOURCE_CEILINGS = {
    "compute_microseconds_per_event": 1_000_000,
    "memory_bytes_upper_bound": 64 * 1024 * 1024,
    "history_bytes_upper_bound": 256 * 1024 * 1024,
    "state_bytes_upper_bound": 64 * 1024 * 1024,
    "storage_bytes_per_day_upper_bound": 1024 * 1024 * 1024,
    "subscription_count_upper_bound": 256,
    "fanout_upper_bound": 128,
}
_SAFE_IMPORTS = frozenset({"decimal", "math", "statistics"})
_SAFE_CALLS = frozenset({"abs", "all", "any", "len", "max", "min", "round", "sum"})
_FORBIDDEN_NAMES = frozenset({
    "__import__", "account", "breakpoint", "broker", "compile", "credential",
    "database", "db", "eval", "exec", "execution", "globals", "input", "ledger",
    "live", "locals", "open", "order", "owner", "pathlib", "requests", "session",
    "socket", "subprocess", "sys", "tenant", "user", "venue",
})
_SECRET_MARKERS = (
    "api_key", "api_secret", "access_token", "authorization:", "password",
    "private_key", "refresh_token", "secret=", "totp", "://",
)


class CustomNodeRefusal(ValueError):
    """A custom contract is open, unbounded, cross-tenant, or capability-bearing."""


@dataclass(frozen=True)
class RuntimeUnavailableDecision:
    schema: str
    level: str
    contract_address: str
    status: str
    reason: str

    def __post_init__(self) -> None:
        if self.schema != "custom-node-runtime-decision/1" \
                or self.level not in RUNTIME_DISABLED_LEVELS \
                or not is_content_address(self.contract_address) \
                or self.status != "UNAVAILABLE" \
                or self.reason != "SECURITY_OWNER_GATE_REQUIRED":
            raise CustomNodeRefusal("runtime-unavailable decision is malformed")


@dataclass(frozen=True, init=False)
class CustomNodeAdmission:
    document: Mapping[str, Any]
    admission_address: str
    node_contract: NodeContract
    data_contract: Mapping[str, Any]
    formula_expression: str | None
    runtime_decision: RuntimeUnavailableDecision | None
    source_admission: CustomNodeAdmission | None
    python_source_text: str | None

    def __init__(self, *args, **kwargs) -> None:
        raise CustomNodeRefusal("custom admissions may only be constructed by admit_custom_node")

    def _validate(self, ancestry: tuple[str, ...] = ()) -> None:
        if self.admission_address in ancestry or len(ancestry) >= 64:
            raise CustomNodeRefusal("custom admission ancestry is cyclic or unbounded")
        ancestry = (*ancestry, self.admission_address)
        fields = {
            "schema", "level", "tenant_id", "custom_node_id", "custom_node_version",
            "visible_family", "input_types", "output_types", "node_contract_address",
            "data_contract_address", "trigger_rate", "lineage_addresses",
            "fork_source_address", "formula", "python_contract",
            "external_signal_contract", "runtime_status", "admission_address",
        }
        if type(self.document) is not MappingProxyType or set(self.document) != fields \
                or self.document.get("schema") != "custom-node-admission/1" \
                or self.document.get("admission_address") != self.admission_address \
                or content_address({
                    key: _plain(item) for key, item in self.document.items()
                    if key != "admission_address"
                }) != self.admission_address:
            raise CustomNodeRefusal("custom admission address is stale or forged")
        try:
            reconstructed_node = canonical_node_contract(
                self.node_contract.component, self.node_contract.document,
            )
        except NodeContractRefusal as exc:
            raise CustomNodeRefusal("custom admission node contract is malformed") from exc
        reconstructed_data, data_address = _data_contract(
            _plain(self.data_contract), reconstructed_node,
        )
        component = (
            f"custom.{self.document['tenant_id']}.{self.document['custom_node_id']}",
            self.document["custom_node_version"],
        )
        if reconstructed_node != self.node_contract \
                or self.node_contract.component != component \
                or self.node_contract.document["stable_node_id"] != component[0] \
                or self.node_contract.document["semantic_version"] != component[1] \
                or self.node_contract.document["visible_family"] != self.document["visible_family"] \
                or dict(self.node_contract.document["input_types"]) != dict(self.document["input_types"]) \
                or dict(self.node_contract.document["output_types"]) != dict(self.document["output_types"]) \
                or self.document["node_contract_address"] != self.node_contract.contract_address \
                or _plain(reconstructed_data) != _plain(self.data_contract) \
                or self.document["data_contract_address"] != data_address \
                or self.document["formula"] != self.formula_expression:
            raise CustomNodeRefusal("custom admission wrapper conflicts with its contracts")
        level = self.document["level"]
        if level not in CUSTOM_LEVELS:
            raise CustomNodeRefusal("custom admission level is unknown")
        _identifier(self.document["tenant_id"], "tenant_id")
        _identifier(self.document["custom_node_id"], "custom_node_id")
        if type(self.document["custom_node_version"]) is not int \
                or self.document["custom_node_version"] < 1:
            raise CustomNodeRefusal("custom admission version is invalid")
        _resource_contract(self.node_contract, level)
        _causal_contract(self.node_contract)
        rate = _trigger_rate(self.document["trigger_rate"])
        if dict(rate) != dict(self.document["trigger_rate"]):
            raise CustomNodeRefusal("custom admission trigger rate is noncanonical")
        lineage = _addresses(self.document["lineage_addresses"], "lineage addresses")
        if not lineage or not set(lineage).issubset(
            set(self.node_contract.document["reference_provenance"])
        ):
            raise CustomNodeRefusal("custom admission lineage is incomplete")
        if level in RUNTIME_DISABLED_LEVELS:
            if self.formula_expression is not None \
                    or self.runtime_decision is None \
                    or self.runtime_decision.contract_address != self.admission_address \
                    or self.runtime_decision.level != level \
                    or self.document["runtime_status"] != "UNAVAILABLE":
                raise CustomNodeRefusal("disabled custom admission wrapper is inconsistent")
            if self.document["fork_source_address"] is not None:
                raise CustomNodeRefusal("disabled custom admission carries a fork source")
            if level == "LEVEL_3_SANDBOXED_PYTHON_CONTRACT":
                if self.document["external_signal_contract"] is not None:
                    raise CustomNodeRefusal("Level 3 carries an external-signal contract")
                if self.source_admission is not None \
                        or not isinstance(self.python_source_text, str):
                    raise CustomNodeRefusal("Level 3 retained source proof is absent")
                stored_python = self.document["python_contract"]
                _validate_python_document(
                    stored_python, self.document["tenant_id"],
                    tuple(self.document["input_types"]),
                )
                reconstructed_python = _python_contract({
                    "source_tenant_id": stored_python["source_tenant_id"],
                    "source_text": self.python_source_text,
                    "entrypoint": stored_python["entrypoint"],
                    "declared_imports": list(stored_python["declared_imports"]),
                    "declared_inputs": list(stored_python["declared_inputs"]),
                    "declared_capabilities": list(stored_python["declared_capabilities"]),
                }, self.document["tenant_id"], tuple(self.document["input_types"]))
                if _plain(reconstructed_python) != _plain(stored_python) \
                        or stored_python["source_address"] not in lineage \
                        or stored_python["source_address"] not in set(
                            self.node_contract.document["reference_provenance"]
                        ):
                    raise CustomNodeRefusal("Level 3 retained source proof does not reconstruct")
            else:
                if self.document["python_contract"] is not None:
                    raise CustomNodeRefusal("Level 4 carries a Python contract")
                if self.source_admission is not None or self.python_source_text is not None:
                    raise CustomNodeRefusal("Level 4 carries incompatible retained proof")
                _validate_external_document(
                    self.document["external_signal_contract"], self.document["tenant_id"],
                    tuple(self.document["input_types"]),
                )
                external = self.document["external_signal_contract"]
                external_addresses = {
                    external["schema_address"],
                    external["authentication_policy_address"],
                    external["replay_policy_address"],
                }
                if not external_addresses.issubset(set(lineage)) \
                        or not external_addresses.issubset(set(
                            self.node_contract.document["reference_provenance"]
                        )):
                    raise CustomNodeRefusal("Level 4 provenance is not bound to lineage")
        else:
            if self.runtime_decision is not None \
                    or self.document["runtime_status"] != "CONTRACT_EVALUABLE" \
                    or self.formula_expression is None:
                raise CustomNodeRefusal("evaluable custom admission wrapper is inconsistent")
            _formula_contract(
                self.formula_expression,
                dict(self.document["input_types"]),
                self.document["output_types"]["value"],
            )
            if self.document["python_contract"] is not None \
                    or self.document["external_signal_contract"] is not None:
                raise CustomNodeRefusal("evaluable admission carries a disabled-level contract")
            if level == "LEVEL_2_FORMULA" and self.document["fork_source_address"] is not None:
                raise CustomNodeRefusal("formula admission carries a fork source")
            if level == "LEVEL_2_FORMULA":
                if self.source_admission is not None or self.python_source_text is not None:
                    raise CustomNodeRefusal("formula admission carries incompatible retained proof")
            else:
                _validate_fork_wrapper(self, ancestry)


def admit_custom_node(
    proposal: Mapping[str, Any], *, source: CustomNodeAdmission | None = None,
) -> CustomNodeAdmission:
    fields = {
        "schema", "level", "tenant_id", "custom_node_id", "custom_node_version",
        "visible_family", "input_types", "output_types", "node_contract",
        "data_contract", "trigger_rate", "lineage_addresses", "fork_source_address",
        "formula", "python_contract", "external_signal_contract",
    }
    if not isinstance(proposal, Mapping) or set(proposal) != fields \
            or proposal.get("schema") != "custom-node-proposal/1":
        raise CustomNodeRefusal("custom proposal uses an open or incomplete schema")
    level = proposal["level"]
    if level not in CUSTOM_LEVELS:
        raise CustomNodeRefusal("custom level is unknown")
    tenant_id = _identifier(proposal["tenant_id"], "tenant_id")
    node_id = _identifier(proposal["custom_node_id"], "custom_node_id")
    version = proposal["custom_node_version"]
    if type(version) is not int or version < 1:
        raise CustomNodeRefusal("custom node version must be a positive exact integer")
    if proposal["visible_family"] not in VISIBLE_FAMILIES:
        raise CustomNodeRefusal("custom node visible family is absent or unknown")
    input_types = _type_map(proposal["input_types"], "input types")
    output_types = _type_map(proposal["output_types"], "output types")
    if set(output_types) != {"value"}:
        raise CustomNodeRefusal("custom node must expose one named value output")
    component = (f"custom.{tenant_id}.{node_id}", version)
    try:
        node_contract = canonical_node_contract(component, proposal["node_contract"])
    except NodeContractRefusal as exc:
        raise CustomNodeRefusal("custom node contract is invalid") from exc
    if node_contract.document["visible_family"] != proposal["visible_family"] \
            or dict(node_contract.document["input_types"]) != input_types \
            or dict(node_contract.document["output_types"]) != output_types:
        raise CustomNodeRefusal("custom descriptor and node contract disagree")
    _resource_contract(node_contract, level)
    data_contract, data_address = _data_contract(
        proposal["data_contract"], node_contract,
    )
    rate = _trigger_rate(proposal["trigger_rate"])
    lineage = _addresses(proposal["lineage_addresses"], "lineage addresses")
    if not lineage:
        raise CustomNodeRefusal("custom node requires immutable lineage")
    if not set(lineage).issubset(set(node_contract.document["reference_provenance"])):
        raise CustomNodeRefusal("node reference provenance omits custom lineage")
    _causal_contract(node_contract)

    formula: str | None = None
    python_document = None
    external_document = None
    fork_address = proposal["fork_source_address"]
    if level == "LEVEL_1_FORK":
        formula, lineage = _fork_contract(
            proposal, source, tenant_id, version, node_contract, data_contract, rate,
            lineage,
        )
    elif level == "LEVEL_2_FORMULA":
        _only(proposal, formula=True)
        formula = _formula_contract(
            proposal["formula"], input_types, output_types["value"],
        )
    elif level == "LEVEL_3_SANDBOXED_PYTHON_CONTRACT":
        _only(proposal, python=True)
        python_document = _python_contract(
            proposal["python_contract"], tenant_id, tuple(input_types),
        )
        if python_document["source_address"] not in node_contract.document["reference_provenance"]:
            raise CustomNodeRefusal("Python source lineage is absent from node provenance")
        lineage = tuple(sorted(set((*lineage, python_document["source_address"]))))
    else:
        _only(proposal, external=True)
        external_document = _external_contract(
            proposal["external_signal_contract"], tenant_id, tuple(input_types),
        )
        external_lineage = {
            external_document["schema_address"],
            external_document["authentication_policy_address"],
            external_document["replay_policy_address"],
        }
        if not external_lineage.issubset(
            set(node_contract.document["reference_provenance"])
        ):
            raise CustomNodeRefusal("external-signal lineage is absent from node provenance")
        lineage = tuple(sorted(set((
            *lineage, external_document["schema_address"],
            external_document["authentication_policy_address"],
            external_document["replay_policy_address"],
        ))))

    document = {
        "schema": "custom-node-admission/1",
        "level": level,
        "tenant_id": tenant_id,
        "custom_node_id": node_id,
        "custom_node_version": version,
        "visible_family": proposal["visible_family"],
        "input_types": input_types,
        "output_types": output_types,
        "node_contract_address": node_contract.contract_address,
        "data_contract_address": data_address,
        "trigger_rate": dict(rate),
        "lineage_addresses": list(lineage),
        "fork_source_address": fork_address,
        "formula": formula,
        "python_contract": python_document,
        "external_signal_contract": external_document,
        "runtime_status": (
            "UNAVAILABLE" if level in RUNTIME_DISABLED_LEVELS
            else "CONTRACT_EVALUABLE"
        ),
    }
    address = content_address(_plain(document))
    frozen = _freeze({**document, "admission_address": address})
    decision = None
    if level in RUNTIME_DISABLED_LEVELS:
        decision = RuntimeUnavailableDecision(
            "custom-node-runtime-decision/1", level, address,
            "UNAVAILABLE", "SECURITY_OWNER_GATE_REQUIRED",
        )
    return _new_custom_admission(
        frozen, address, node_contract, data_contract, formula, decision,
        source if level == "LEVEL_1_FORK" else None,
        proposal["python_contract"]["source_text"]
        if level == "LEVEL_3_SANDBOXED_PYTHON_CONTRACT" else None,
    )


def _new_custom_admission(
    document: Mapping[str, Any], admission_address: str,
    node_contract: NodeContract, data_contract: Mapping[str, Any],
    formula_expression: str | None,
    runtime_decision: RuntimeUnavailableDecision | None,
    source_admission: CustomNodeAdmission | None = None,
    python_source_text: str | None = None,
) -> CustomNodeAdmission:
    result = object.__new__(CustomNodeAdmission)
    for name, value in (
        ("document", document), ("admission_address", admission_address),
        ("node_contract", node_contract), ("data_contract", data_contract),
        ("formula_expression", formula_expression),
        ("runtime_decision", runtime_decision),
        ("source_admission", source_admission),
        ("python_source_text", python_source_text),
    ):
        object.__setattr__(result, name, value)
    result._validate()
    return result


def evaluate_custom_node(
    admission: CustomNodeAdmission, inputs: Mapping[str, NumericValue], *, tenant_id: str,
) -> NumericValue | RuntimeUnavailableDecision:
    if not isinstance(admission, CustomNodeAdmission):
        raise CustomNodeRefusal("custom admission is required")
    admission._validate()
    if tenant_id != admission.document["tenant_id"]:
        raise CustomNodeRefusal("cross-tenant custom-node evaluation refused")
    if admission.document["level"] in RUNTIME_DISABLED_LEVELS:
        if admission.runtime_decision is None:
            raise CustomNodeRefusal("disabled custom runtime decision is absent")
        return admission.runtime_decision
    declared = set(admission.document["input_types"])
    if not isinstance(inputs, Mapping) or set(inputs) != declared \
            or any(not isinstance(item, NumericValue) for item in inputs.values()):
        raise CustomNodeRefusal("formula inputs differ from the declared typed universe")
    propagated = propagate(inputs.values())
    if propagated is not None:
        return propagated
    values = {name: item.value for name, item in inputs.items()}
    for name, item in values.items():
        type_name = admission.document["input_types"][name]
        if type_name == "number/scalar":
            _formula_number(item)
        elif type_name == "boolean/scalar":
            _formula_boolean(item)
        else:
            raise CustomNodeRefusal("formula input type is outside the closed domain")
    if admission.formula_expression is None:
        raise CustomNodeRefusal("evaluable custom node lacks a formula")
    tree, _result_type = _parse_formula(
        admission.formula_expression,
        dict(admission.document["input_types"]),
        admission.document["output_types"]["value"],
    )
    try:
        result = _formula_value(tree.body, values)
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise CustomNodeRefusal("formula result is mathematically undefined") from exc
    if isinstance(result, bool):
        return valid(result)
    if not isinstance(result, (int, float)) or not math.isfinite(result):
        return invalid(ValidityState.MATHEMATICALLY_UNDEFINED)
    return valid(result)


def _only(
    proposal: Mapping[str, Any], *, formula: bool = False,
    python: bool = False, external: bool = False,
) -> None:
    expected = {
        "formula": proposal["formula"] if formula else None,
        "python_contract": proposal["python_contract"] if python else None,
        "external_signal_contract": (
            proposal["external_signal_contract"] if external else None
        ),
        "fork_source_address": proposal["fork_source_address"],
    }
    if (formula and expected["formula"] is None) \
            or (python and expected["python_contract"] is None) \
            or (external and expected["external_signal_contract"] is None) \
            or expected["fork_source_address"] is not None \
            or (not formula and proposal["formula"] is not None) \
            or (not python and proposal["python_contract"] is not None) \
            or (not external and proposal["external_signal_contract"] is not None):
        raise CustomNodeRefusal("custom level carries incompatible contract fields")


def _fork_contract(
    proposal: Mapping[str, Any], source: CustomNodeAdmission | None,
    tenant_id: str, version: int, node_contract: NodeContract,
    data_contract: Mapping[str, Any], rate: Mapping[str, int],
    lineage: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    if proposal["formula"] is not None or proposal["python_contract"] is not None \
            or proposal["external_signal_contract"] is not None \
            or not isinstance(source, CustomNodeAdmission) \
            or proposal["fork_source_address"] != source.admission_address:
        raise CustomNodeRefusal("fork source contract is absent or conflicting")
    if source.document["tenant_id"] != tenant_id:
        raise CustomNodeRefusal("cross-tenant fork refused")
    if version <= source.document["custom_node_version"] \
            or source.document["level"] not in {"LEVEL_1_FORK", "LEVEL_2_FORMULA"} \
            or source.formula_expression is None:
        raise CustomNodeRefusal("fork version or source level is invalid")
    inherited = dict(source.node_contract.document)
    inherited["stable_node_id"] = node_contract.document["stable_node_id"]
    inherited["semantic_version"] = node_contract.document["semantic_version"]
    expected_provenance = tuple(sorted(set((
        *source.node_contract.document["reference_provenance"],
        source.admission_address,
    ))))
    inherited["reference_provenance"] = expected_provenance
    if tuple(node_contract.document["reference_provenance"]) != expected_provenance:
        raise CustomNodeRefusal("fork provenance does not extend the source lineage exactly")
    if _plain(node_contract.document) != _plain(inherited) \
            or _plain(data_contract) != _plain(source.data_contract) \
            or dict(rate) != dict(source.document["trigger_rate"]):
        raise CustomNodeRefusal("fork does not inherit the source contract exactly")
    expected_lineage = tuple(sorted(set((
        *source.document["lineage_addresses"], source.admission_address,
    ))))
    if lineage != expected_lineage:
        raise CustomNodeRefusal("fork lineage does not preserve the exact transitive source")
    return source.formula_expression, lineage


def _validate_fork_wrapper(
    admission: CustomNodeAdmission, ancestry: tuple[str, ...],
) -> None:
    source = admission.source_admission
    if not isinstance(source, CustomNodeAdmission) \
            or admission.python_source_text is not None:
        raise CustomNodeRefusal("fork retained source admission is absent")
    source._validate(ancestry)
    document = admission.document
    if document["fork_source_address"] != source.admission_address \
            or document["tenant_id"] != source.document["tenant_id"] \
            or document["custom_node_version"] <= source.document["custom_node_version"] \
            or source.document["level"] not in {"LEVEL_1_FORK", "LEVEL_2_FORMULA"} \
            or admission.formula_expression != source.formula_expression:
        raise CustomNodeRefusal("fork retained source identity or version is invalid")
    expected_lineage = tuple(sorted(set((
        *source.document["lineage_addresses"], source.admission_address,
    ))))
    expected_provenance = tuple(sorted(set((
        *source.node_contract.document["reference_provenance"],
        source.admission_address,
    ))))
    inherited = dict(source.node_contract.document)
    inherited["stable_node_id"] = admission.node_contract.document["stable_node_id"]
    inherited["semantic_version"] = admission.node_contract.document["semantic_version"]
    inherited["reference_provenance"] = expected_provenance
    if tuple(document["lineage_addresses"]) != expected_lineage \
            or tuple(admission.node_contract.document["reference_provenance"]) \
            != expected_provenance \
            or _plain(admission.node_contract.document) != _plain(inherited) \
            or _plain(admission.data_contract) != _plain(source.data_contract) \
            or dict(document["trigger_rate"]) != dict(source.document["trigger_rate"]):
        raise CustomNodeRefusal("fork retained proof does not reconstruct exact ancestry")


def _formula_contract(
    value: Any, inputs: Mapping[str, str], output_type: str,
) -> str:
    if not isinstance(value, str) or not value.strip() \
            or len(value.encode("utf-8")) > _MAX_FORMULA_BYTES:
        raise CustomNodeRefusal("formula is absent or oversized")
    _parse_formula(value, inputs, output_type)
    return value


def _parse_formula(
    value: str, inputs: Mapping[str, str], output_type: str,
) -> tuple[ast.Expression, str]:
    try:
        tree = ast.parse(value, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise CustomNodeRefusal("formula syntax is invalid") from exc
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
        ast.Name, ast.Load, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div,
        ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.And, ast.Or, ast.Not,
        ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE,
    )
    nodes = tuple(ast.walk(tree))
    if len(nodes) > _MAX_FORMULA_NODES or any(not isinstance(node, allowed) for node in nodes):
        raise CustomNodeRefusal("formula uses a forbidden or unbounded construct")
    names = {node.id for node in nodes if isinstance(node, ast.Name)}
    if not names.issubset(set(inputs)):
        raise CustomNodeRefusal("formula reads an undeclared input")
    for node in nodes:
        if isinstance(node, ast.Constant) and (
            isinstance(node.value, str) or node.value is None
            or not isinstance(node.value, (bool, int, float))
            or isinstance(node.value, float) and not math.isfinite(node.value)
        ):
            raise CustomNodeRefusal("formula constant is outside the closed domain")
    inferred = _formula_type(tree.body, inputs)
    if inferred != output_type or output_type not in {"number/scalar", "boolean/scalar"}:
        raise CustomNodeRefusal("formula output type differs from its declared output")
    return tree, inferred


def _formula_type(node: ast.AST, inputs: Mapping[str, str]) -> str:
    if isinstance(node, ast.Constant):
        return "boolean/scalar" if type(node.value) is bool else "number/scalar"
    if isinstance(node, ast.Name):
        value = inputs[node.id]
        if value not in {"number/scalar", "boolean/scalar"}:
            raise CustomNodeRefusal("formula input type is outside the closed domain")
        return value
    if isinstance(node, ast.BinOp):
        if _formula_type(node.left, inputs) != "number/scalar" \
                or _formula_type(node.right, inputs) != "number/scalar":
            raise CustomNodeRefusal("arithmetic formula operands must be numeric")
        return "number/scalar"
    if isinstance(node, ast.UnaryOp):
        operand = _formula_type(node.operand, inputs)
        expected = "boolean/scalar" if isinstance(node.op, ast.Not) else "number/scalar"
        if operand != expected:
            raise CustomNodeRefusal("formula unary operand type is invalid")
        return expected
    if isinstance(node, ast.BoolOp):
        if any(_formula_type(item, inputs) != "boolean/scalar" for item in node.values):
            raise CustomNodeRefusal("formula boolean operands must be exact booleans")
        return "boolean/scalar"
    if isinstance(node, ast.Compare):
        compared = (node.left, *node.comparators)
        if any(_formula_type(item, inputs) != "number/scalar" for item in compared):
            raise CustomNodeRefusal("formula comparisons require numeric operands")
        return "boolean/scalar"
    if isinstance(node, ast.IfExp):
        if _formula_type(node.test, inputs) != "boolean/scalar":
            raise CustomNodeRefusal("formula conditional must be an exact boolean")
        left = _formula_type(node.body, inputs)
        if left != _formula_type(node.orelse, inputs):
            raise CustomNodeRefusal("formula conditional branches have different types")
        return left
    raise CustomNodeRefusal("formula type cannot be inferred")


def _formula_value(node: ast.AST, values: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Name): return values[node.id]
    if isinstance(node, ast.UnaryOp):
        item = _formula_value(node.operand, values)
        if isinstance(node.op, ast.USub): return -_formula_number(item)
        if isinstance(node.op, ast.UAdd): return +_formula_number(item)
        if isinstance(node.op, ast.Not): return not _formula_boolean(item)
    if isinstance(node, ast.BinOp):
        left = _formula_number(_formula_value(node.left, values))
        right = _formula_number(_formula_value(node.right, values))
        if isinstance(node.op, ast.Pow) and (abs(right) > 32 or abs(left) > 1e12):
            raise ValueError("power bound exceeded")
        operations = {
            ast.Add: lambda: left+right, ast.Sub: lambda: left-right,
            ast.Mult: lambda: left*right, ast.Div: lambda: left/right,
            ast.Mod: lambda: left % right, ast.Pow: lambda: left**right,
        }
        return operations[type(node.op)]()
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for item in node.values:
                if not _formula_boolean(_formula_value(item, values)):
                    return False
            return True
        for item in node.values:
            if _formula_boolean(_formula_value(item, values)):
                return True
        return False
    if isinstance(node, ast.Compare):
        left = _formula_number(_formula_value(node.left, values))
        for operation, comparator in zip(node.ops, node.comparators, strict=True):
            right = _formula_number(_formula_value(comparator, values))
            checks = {ast.Eq: left == right, ast.NotEq: left != right,
                      ast.Gt: left > right, ast.GtE: left >= right,
                      ast.Lt: left < right, ast.LtE: left <= right}
            if not checks[type(operation)]: return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _formula_value(node.body if _formula_boolean(_formula_value(node.test, values))
                              else node.orelse, values)
    raise CustomNodeRefusal("formula node is not executable")


def _formula_number(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        raise CustomNodeRefusal("formula value must be a finite number")
    return value


def _formula_boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise CustomNodeRefusal("formula value must be an exact boolean")
    return value


def _python_contract(value: Any, tenant_id: str, inputs: tuple[str, ...]) -> Mapping[str, Any]:
    fields = {"source_tenant_id", "source_text", "entrypoint", "declared_imports",
              "declared_inputs", "declared_capabilities"}
    if not isinstance(value, Mapping) or set(value) != fields \
            or value["source_tenant_id"] != tenant_id:
        raise CustomNodeRefusal("Python contract is open or cross-tenant")
    source = value["source_text"]
    if not isinstance(source, str) or not source.strip() \
            or len(source.encode("utf-8")) > _MAX_PYTHON_BYTES:
        raise CustomNodeRefusal("Python source is absent or oversized")
    lowered = source.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        raise CustomNodeRefusal("Python source contains a secret or network marker")
    imports = _strings(value["declared_imports"], "declared imports", allow_empty=True)
    if any(item not in _SAFE_IMPORTS for item in imports):
        raise CustomNodeRefusal("Python import is not in the closed allowlist")
    declared_inputs = _strings(value["declared_inputs"], "declared inputs")
    if declared_inputs != tuple(inputs):
        raise CustomNodeRefusal("Python inputs differ from the declared node inputs")
    if _strings(value["declared_capabilities"], "declared capabilities") != ("PURE_COMPUTE",):
        raise CustomNodeRefusal("Python capabilities exceed pure compute")
    entrypoint = _identifier(value["entrypoint"], "Python entrypoint")
    try:
        tree = ast.parse(source, mode="exec")
    except (SyntaxError, ValueError) as exc:
        raise CustomNodeRefusal("Python source syntax is invalid") from exc
    actual_imports: set[str] = set()
    functions: list[ast.FunctionDef] = []
    if any(not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))
           for node in tree.body):
        raise CustomNodeRefusal("Python module has executable top-level statements")
    forbidden_nodes = (
        ast.AsyncFor, ast.AsyncFunctionDef, ast.Await, ast.ClassDef, ast.Delete,
        ast.DictComp, ast.For, ast.GeneratorExp, ast.Global, ast.Lambda, ast.ListComp,
        ast.Nonlocal, ast.Raise, ast.SetComp, ast.Try, ast.While, ast.With,
        ast.AsyncWith, ast.Yield, ast.YieldFrom,
    )
    for node in ast.walk(tree):
        if isinstance(node, forbidden_nodes):
            raise CustomNodeRefusal("Python source contains a forbidden capability")
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _forbidden_python_name(alias.name)
                if alias.asname is not None:
                    _forbidden_python_name(alias.asname)
                if alias.name != root or root not in _SAFE_IMPORTS:
                    raise CustomNodeRefusal("Python import is outside the exact allowlist")
                actual_imports.add(root)
        if isinstance(node, ast.ImportFrom):
            raise CustomNodeRefusal("Python ImportFrom is forbidden in V1")
        if isinstance(node, ast.FunctionDef):
            functions.append(node)
            if node.decorator_list:
                raise CustomNodeRefusal("Python decorators are forbidden")
        if isinstance(node, ast.Name):
            _forbidden_python_name(node.id)
        if isinstance(node, ast.Attribute):
            _forbidden_python_name(node.attr)
            root = node.value
            while isinstance(root, ast.Attribute): root = root.value
            if isinstance(root, ast.Name) and root.id not in _SAFE_IMPORTS:
                raise CustomNodeRefusal("Python attribute root is not an allowed module")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id not in _SAFE_CALLS:
                raise CustomNodeRefusal("Python call is outside the pure allowlist")
            if not isinstance(node.func, (ast.Name, ast.Attribute)):
                raise CustomNodeRefusal("dynamic Python call is forbidden")
    matching = [item for item in functions if item.name == entrypoint]
    if actual_imports != set(imports) or len(matching) != 1:
        raise CustomNodeRefusal("Python imports or entrypoint differ from the contract")
    arguments = matching[0].args
    if tuple(item.arg for item in arguments.args) != declared_inputs \
            or arguments.posonlyargs or arguments.kwonlyargs \
            or arguments.vararg is not None or arguments.kwarg is not None \
            or arguments.defaults or arguments.kw_defaults:
        raise CustomNodeRefusal("Python entrypoint signature differs from declared inputs")
    return _freeze({
        "source_tenant_id": tenant_id,
        "source_address": content_address({"python-source": source}),
        "entrypoint": entrypoint,
        "declared_imports": list(imports),
        "declared_inputs": list(declared_inputs),
        "declared_capabilities": ["PURE_COMPUTE"],
        "runtime_enabled": False,
    })


def _validate_python_document(
    value: Any, tenant_id: str, inputs: tuple[str, ...],
) -> None:
    fields = {
        "source_tenant_id", "source_address", "entrypoint", "declared_imports",
        "declared_inputs", "declared_capabilities", "runtime_enabled",
    }
    if not isinstance(value, Mapping) or set(value) != fields \
            or value["source_tenant_id"] != tenant_id \
            or value["runtime_enabled"] is not False:
        raise CustomNodeRefusal("stored Python contract is open or enabled")
    _address(value["source_address"], "Python source address")
    _identifier(value["entrypoint"], "Python entrypoint")
    imports = _strings(value["declared_imports"], "declared imports", allow_empty=True)
    if any(item not in _SAFE_IMPORTS for item in imports) \
            or _strings(value["declared_inputs"], "declared inputs") != inputs \
            or _strings(value["declared_capabilities"], "declared capabilities") \
            != ("PURE_COMPUTE",):
        raise CustomNodeRefusal("stored Python contract exceeds pure declared inputs")


def _external_contract(value: Any, tenant_id: str, inputs: tuple[str, ...]) -> Mapping[str, Any]:
    fields = {"source_tenant_id", "schema_address", "authentication_policy_address",
              "replay_policy_address", "declared_fields", "maximum_payload_bytes"}
    if not isinstance(value, Mapping) or set(value) != fields \
            or value["source_tenant_id"] != tenant_id:
        raise CustomNodeRefusal("external-signal contract is open or cross-tenant")
    for name in ("schema_address", "authentication_policy_address", "replay_policy_address"):
        _address(value[name], name)
    fields_value = _strings(value["declared_fields"], "declared fields")
    if fields_value != tuple(inputs):
        raise CustomNodeRefusal("external fields differ from declared node inputs")
    size = value["maximum_payload_bytes"]
    if type(size) is not int or not 1 <= size <= _MAX_EXTERNAL_PAYLOAD_BYTES:
        raise CustomNodeRefusal("external payload bound is invalid")
    return _freeze({**value, "declared_fields": list(fields_value), "runtime_enabled": False})


def _validate_external_document(
    value: Any, tenant_id: str, inputs: tuple[str, ...],
) -> None:
    fields = {
        "source_tenant_id", "schema_address", "authentication_policy_address",
        "replay_policy_address", "declared_fields", "maximum_payload_bytes",
        "runtime_enabled",
    }
    if not isinstance(value, Mapping) or set(value) != fields \
            or value["source_tenant_id"] != tenant_id \
            or value["runtime_enabled"] is not False:
        raise CustomNodeRefusal("stored external-signal contract is open or enabled")
    for name in ("schema_address", "authentication_policy_address", "replay_policy_address"):
        _address(value[name], name)
    if _strings(value["declared_fields"], "declared fields") != inputs \
            or type(value["maximum_payload_bytes"]) is not int \
            or not 1 <= value["maximum_payload_bytes"] <= _MAX_EXTERNAL_PAYLOAD_BYTES:
        raise CustomNodeRefusal("stored external-signal contract exceeds its bounds")


def _data_contract(value: Any, node_contract: NodeContract) -> tuple[Mapping[str, Any], str]:
    fields = {"schema", "instrument_role_addresses", "provider_requirement_addresses",
              "required_fields", "timeframe_seconds", "history_bars", "alignment",
              "bar_policy"}
    if not isinstance(value, Mapping) or set(value) != fields \
            or value.get("schema") != "custom-data-contract/1":
        raise CustomNodeRefusal("custom data contract is open or incomplete")
    roles = _addresses(value["instrument_role_addresses"], "instrument role addresses",
                       allow_empty=True)
    providers = _addresses(value["provider_requirement_addresses"],
                           "provider requirement addresses", allow_empty=True)
    required = _strings(value["required_fields"], "required fields", allow_empty=True)
    contract = node_contract.document
    if providers != tuple(contract["provider_requirements"]) \
            or required != tuple(contract["required_market_fields"]) \
            or value["timeframe_seconds"] != contract["required_resolution"]["timeframe_seconds"] \
            or value["history_bars"] != contract["warmup_history"] \
            or value["alignment"] != contract["required_resolution"]["alignment"] \
            or value["bar_policy"] != contract["bar_policy"]:
        raise CustomNodeRefusal("custom data and node contracts disagree")
    if type(value["timeframe_seconds"]) is not int or value["timeframe_seconds"] < 1 \
            or type(value["history_bars"]) is not int or value["history_bars"] < 0:
        raise CustomNodeRefusal("custom data bounds are invalid")
    frozen = _freeze({**value, "instrument_role_addresses": list(roles),
                      "provider_requirement_addresses": list(providers),
                      "required_fields": list(required)})
    return frozen, content_address(_plain(frozen))


def _resource_contract(contract: NodeContract, level: str) -> None:
    profile = contract.document["resource_profile"]
    for name, ceiling in _RESOURCE_CEILINGS.items():
        value = profile[name]
        if type(value) is not int or value < 0 or value > ceiling:
            raise CustomNodeRefusal(f"custom resource bound {name} is invalid")
    if profile["compute_microseconds_per_event"] == 0 \
            or profile["memory_bytes_upper_bound"] == 0 \
            or profile["fanout_upper_bound"] == 0:
        raise CustomNodeRefusal("custom compute, memory and fanout must be bounded positive")
    recursive = contract.document["execution_form"] == "RECURSIVE"
    initialized = contract.document["state_initialization"]["initial_state_address"] is not None
    if recursive != initialized or recursive != (profile["state_bytes_upper_bound"] > 0):
        raise CustomNodeRefusal("custom state declaration and resource bound disagree")
    modes = contract.document["mode_eligibility"]
    if level in RUNTIME_DISABLED_LEVELS:
        if any(modes.values()) or contract.document["streaming_support"] \
                or contract.document["batch_support"]:
            raise CustomNodeRefusal("Level 3/4 runtime must remain disabled")
    elif not modes["research"] or modes["live"]:
        raise CustomNodeRefusal("Level 1/2 must be research-enabled and live-ineligible")


def _causal_contract(contract: NodeContract) -> None:
    document = contract.document
    if document["bar_policy"] != "COMPLETED_ONLY" \
            or document["causal_declaration"] != "COMPLETED_EVENT_PREFIX" \
            or not document["evaluation_triggers"]:
        raise CustomNodeRefusal("custom node causal policy is incomplete")


def _trigger_rate(value: Any) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or set(value) != {"events", "per_seconds"}:
        raise CustomNodeRefusal("custom trigger rate must be explicitly bounded")
    try:
        rate = bounded_rate(value["events"], value["per_seconds"])
    except ResourcePlanRefusal as exc:
        raise CustomNodeRefusal("custom trigger rate is invalid") from exc
    if rate["events"] > rate["per_seconds"] * _MAX_EVENTS_PER_SECOND:
        raise CustomNodeRefusal("custom trigger rate exceeds the hard ceiling")
    return rate


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise CustomNodeRefusal(f"{label} is invalid")
    return value


def _type_map(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value or len(value) > _MAX_INPUTS \
            or list(value) != sorted(value) \
            or any(_ID.fullmatch(key) is None or not isinstance(item, str) or not item
                   for key, item in value.items()):
        raise CustomNodeRefusal(f"{label} is malformed or unbounded")
    return dict(value)


def _address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not is_content_address(value):
        raise CustomNodeRefusal(f"{label} must be a content address")
    return value


def _addresses(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or (not value and not allow_empty):
        raise CustomNodeRefusal(f"{label} must be a finite immutable set")
    result = tuple(value)
    if result != tuple(sorted(set(result))):
        raise CustomNodeRefusal(f"{label} must be sorted and unique")
    for item in result: _address(item, label)
    return result


def _strings(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or (not value and not allow_empty):
        raise CustomNodeRefusal(f"{label} must be a finite immutable set")
    result = tuple(value)
    if result != tuple(sorted(set(result))) or any(
        not isinstance(item, str) or not item for item in result
    ):
        raise CustomNodeRefusal(f"{label} must be sorted unique text")
    return result


def _forbidden_python_name(value: str) -> None:
    lowered = value.lower()
    parts = {item for item in re.split(r"[^a-z0-9]+|_", lowered) if item}
    if "__" in value or lowered in _FORBIDDEN_NAMES or parts & _FORBIDDEN_NAMES:
        raise CustomNodeRefusal("Python source names a forbidden capability")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise CustomNodeRefusal("custom contract is not closed JSON")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


__all__ = [
    "CUSTOM_LEVELS", "CustomNodeAdmission", "CustomNodeRefusal",
    "RUNTIME_DISABLED_LEVELS", "RuntimeUnavailableDecision",
    "admit_custom_node", "evaluate_custom_node",
]
