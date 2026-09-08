"""Canonical contract binding helpers, not analytical implementations or authority.

Input projections must come from the existing verified data/admission producer.
This module proves closed identity and consistency against independently pinned
source addresses; it does not authenticate a caller or certify a provider.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping
import unicodedata

from app.ir.hashing import canonical_json, content_address
from app.ir.node_contracts import (
    NODE_CONTRACT_FIELDS, NodeContract, NodeContractRefusal, canonical_node_contract, _freeze, _plain, _ID,
)
from app.ir.schema import is_content_address


NODE_CONTRACT_V2_FIELDS = ("schema", *NODE_CONTRACT_FIELDS, "parameter_binding")
RESET_REASONS_V2 = ("DATA_GAP", "ELAPSED_WINDOW", "EXPLICIT", "IDENTITY_CHANGE", "SESSION")


def _canonical_source_contract_v2(
    component: tuple[str, int], document: Mapping[str, Any],
) -> NodeContract:
    if (not isinstance(component, tuple) or len(component) != 2
            or not isinstance(component[0], str) or type(component[1]) is not int
            or component[1] < 2 or not isinstance(document, Mapping)
            or set(document) != set(NODE_CONTRACT_V2_FIELDS)
            or document.get("schema") != "first-party-node-contract/2"
            or document.get("semantic_version") != component[1]
            or type(document.get("semantic_version")) is not int):
        raise NodeContractRefusal("source /2 contract must have an exact component/version and closed schema")
    binding = document["parameter_binding"]
    binding_fields = {"scheme", "rule_id", "rule_version", "parameter_names", "input_ports"}
    if (not isinstance(binding, Mapping) or set(binding) != binding_fields
            or binding["scheme"] != "analytical-contract-binding/1"):
        raise NodeContractRefusal("source contract binding is incomplete or open")
    _binding_rule(binding["rule_id"], binding["rule_version"])
    for name in ("parameter_names", "input_ports"):
        _closed_binding_names(binding[name], name)
    if not binding["input_ports"]:
        raise NodeContractRefusal("source contract requires explicit input binding ports")
    warmup = document["warmup_history"]
    if (not isinstance(warmup, Mapping) or set(warmup) != {"rule_id", "rule_version"}
            or warmup["rule_id"] != binding["rule_id"]
            or type(warmup["rule_version"]) is not int
            or warmup["rule_version"] != binding["rule_version"]):
        raise NodeContractRefusal("warmup must bind the exact registered rule")
    resolution = document["required_resolution"]
    if (not isinstance(resolution, Mapping) or set(resolution) != {"source", "port", "alignment"}
            or resolution["source"] != "canonical_input_binding"
            or resolution["port"] not in binding["input_ports"]
            or not isinstance(resolution["alignment"], str)
            or resolution["alignment"] not in {"BAR_CLOSE", "SESSION"}):
        raise NodeContractRefusal("source resolution must name an exact canonical input port")
    reset = document["state_reset_policy"]
    if (not isinstance(reset, Mapping) or set(reset) != {"schema", "reasons"}
            or reset["schema"] != "state-reset-policy/2"):
        raise NodeContractRefusal("source reset policy is not version /2")
    _closed_binding_names(reset["reasons"], "reset reasons", identifiers=False)
    if any(reason not in RESET_REASONS_V2 for reason in reset["reasons"]):
        raise NodeContractRefusal("source reset policy has an unknown reason")
    if (document["bar_policy"] != "COMPLETED_ONLY"
            or document["causal_declaration"] != "COMPLETED_EVENT_PREFIX"
            or not isinstance(document["missing_data_policy"], str)
            or document["missing_data_policy"] not in {"PROPAGATE", "REFUSE"}
            or document["numeric_validity_policy"] != "EXPLICIT_VALIDITY"):
        raise NodeContractRefusal("source /2 contracts require completed, explicit validity without fallback")
    modes = document["mode_eligibility"]
    if (not isinstance(modes, Mapping) or modes.get("paper") is not False
            or modes.get("live") is not False):
        raise NodeContractRefusal("source /2 contract cannot declare paper/live eligibility")
    # Reuse the unchanged /1 checks for static obligations. These projected values
    # are validation-only: they are never stored, addressed, or used as requirements.
    projection = {key: _plain(document[key]) for key in NODE_CONTRACT_FIELDS}
    projection["warmup_history"] = 0
    projection["required_resolution"] = {"timeframe_seconds": 1, "alignment": resolution["alignment"]}
    projection["state_reset_policy"] = {"schema": "state-reset-policy/1", "reasons": []}
    try:
        canonical_node_contract(component, projection)
    except (TypeError, KeyError, ValueError) as exc:
        raise NodeContractRefusal("source /2 contract has invalid static obligations") from exc
    if tuple(document["input_types"]) != tuple(binding["input_ports"]):
        raise NodeContractRefusal("source binding must cover every exact typed input")
    return NodeContract(component, _freeze(document), content_address(_plain(document)))


def _binding_rule(rule_id: Any, rule_version: Any) -> None:
    if (not isinstance(rule_id, str) or not _ID.fullmatch(rule_id)
            or type(rule_version) is not int or rule_version < 1):
        raise NodeContractRefusal("binding rule identity must be exact and versioned")


def _closed_binding_names(value: Any, label: str, *, identifiers: bool = True) -> tuple[str, ...]:
    if (not isinstance(value, (tuple, list)) or len(value) > 1024
            or any(not isinstance(item, str) or not item for item in value)):
        raise NodeContractRefusal(f"{label} must be a bounded string array")
    result = tuple(value)
    if result != tuple(sorted(set(result))) or (
        identifiers and any(not _ID.fullmatch(item) for item in result)
    ):
        raise NodeContractRefusal(f"{label} must be canonical, sorted and unique")
    return result



_PARAMETER_FIELDS = {"type", "required", "default", "enum", "domain", "units", "serialization"}
_INPUT_FIELDS = {
    "schema", "owner_id", "dataset_context_address", "evaluation_context_address",
    "dataset_manifest_address", "market_truth_address", "provider_product_address",
    "provider_contract_address", "canonical_instrument_address", "instrument",
    "timeframe", "fields", "freshness", "depth", "session", "alignment", "derived_local",
}
_INPUT_ADDRESSES = (
    "dataset_context_address", "evaluation_context_address", "dataset_manifest_address",
    "market_truth_address", "provider_product_address", "provider_contract_address",
    "canonical_instrument_address",
)
_REQUIREMENT_FIELDS = ("instrument", "field", "timeframe", "history", "freshness", "depth", "session", "alignment", "derived_local")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NodeContractRefusal(message)


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(value)
    except (TypeError, ValueError, OverflowError):
        return False


def _text(value: Any, label: str, maximum: int = 128) -> str:
    _require(isinstance(value, str) and bool(value) and len(value) <= maximum
             and "\x00" not in value and unicodedata.normalize("NFC", value) == value,
             f"{label} must be bounded canonical text")
    return value


def _address(value: Any, label: str) -> str:
    _require(isinstance(value, str) and is_content_address(value), f"{label} must be a content address")
    return value


def validate_parameter_descriptors(descriptors: Mapping[str, Any]) -> None:
    _require(isinstance(descriptors, Mapping) and len(descriptors) <= 1024,
             "binding parameter descriptors must be a bounded mapping")
    for name, descriptor in descriptors.items():
        _text(name, "parameter name")
        _require(isinstance(descriptor, Mapping) and set(descriptor) == _PARAMETER_FIELDS,
                 "binding parameter descriptor is incomplete or open")
        kind = descriptor["type"]
        _require(isinstance(kind, str) and kind in {"int", "float", "bool", "str"}, "binding parameter type is unsupported")
        _require(type(descriptor["required"]) is bool
                 and descriptor["serialization"] == "canonical-json", "binding parameter policy is invalid")
        _text(descriptor["units"], "parameter units")
        domain = descriptor["domain"]
        if kind in {"int", "float"}:
            _require(isinstance(domain, Mapping) and set(domain) == {"minimum", "maximum"},
                     "numeric binding parameter requires a closed bounded domain")
            for value in domain.values():
                _require(type(value) is int if kind == "int" else type(value) in {int, float},
                         "parameter domain has wrong numeric type")
                _require(_finite(value), "parameter domain must be finite")
            _require(domain["minimum"] <= domain["maximum"], "parameter domain is reversed")
        elif kind == "str":
            _require(isinstance(domain, Mapping) and set(domain) == {"max_length"}
                     and type(domain["max_length"]) is int and 1 <= domain["max_length"] <= 4096,
                     "string binding parameter requires a bounded domain")
        else:
            _require(domain is None, "boolean binding parameter has an unknown domain")
        enum = descriptor["enum"]
        _require(enum is None or isinstance(enum, (tuple, list)) and 0 < len(enum) <= 1024,
                 "parameter enum must be a bounded array")
        if enum is not None:
            for value in enum:
                _validate_parameter(value, descriptor, check_enum=False)
            _require(len({canonical_json(value) for value in enum}) == len(enum), "parameter enum is duplicated")
        if descriptor["default"] is not None:
            _validate_parameter(descriptor["default"], descriptor)


def _validate_parameter(value: Any, descriptor: Mapping[str, Any], *, check_enum: bool = True) -> None:
    kind = descriptor["type"]
    valid_type = (type(value) is int if kind == "int" else type(value) in {int, float}
                  if kind == "float" else type(value) is bool if kind == "bool" else isinstance(value, str))
    _require(valid_type, "binding parameter has wrong type or is absent")
    if kind in {"int", "float"}:
        domain = descriptor["domain"]
        _require(_finite(value) and domain["minimum"] <= value <= domain["maximum"],
                 "binding parameter is outside its finite domain")
    elif kind == "str":
        _text(value, "binding string parameter", descriptor["domain"]["max_length"])
    if check_enum and descriptor["enum"] is not None:
        _require(canonical_json(value) in {canonical_json(item) for item in descriptor["enum"]},
                 "binding parameter is outside its declared enum")


def canonical_binding_parameters(values: Mapping[str, Any], descriptors: Mapping[str, Any]) -> Mapping[str, Any]:
    validate_parameter_descriptors(descriptors)
    _require(isinstance(values, Mapping) and set(values) == set(descriptors),
             "binding requires every normalized declared parameter and no extras")
    for name, descriptor in descriptors.items():
        _validate_parameter(values[name], descriptor)
    return _freeze({name: values[name] for name in sorted(values)})


def _validate_input_fact(document: Any, owner: str, dataset: str, evaluation: str) -> None:
    from app.ir.registry import _validate_data_direct

    _require(isinstance(document, Mapping) and set(document) == _INPUT_FIELDS
             and document["schema"] == "canonical-input-binding/1", "canonical input binding is incomplete or open")
    _require(document["owner_id"] == owner and document["dataset_context_address"] == dataset
             and document["evaluation_context_address"] == evaluation,
             "input binding owner/dataset/evaluation context differs")
    for name in _INPUT_ADDRESSES:
        _address(document[name], name)
    fields = document["fields"]
    _require(isinstance(fields, (tuple, list)) and 0 < len(fields) <= 1024
             and all(isinstance(field, str) for field in fields), "input fields must be a bounded string array")
    _require(tuple(fields) == tuple(sorted(set(fields))), "input fields must be sorted and unique")
    try:
        for field in fields:
            _validate_data_direct("field", field)
        for field in ("instrument", "timeframe", "freshness", "depth", "session", "alignment", "derived_local"):
            _validate_data_direct(field, document[field])
    except (TypeError, ValueError) as exc:
        raise NodeContractRefusal("canonical input binding has an invalid data fact") from exc


@dataclass(frozen=True)
class ContractInputBindings:
    """Immutable explicit data projections and caller-pinned source identities."""

    document: Mapping[str, Any]
    context_address: str

    def __post_init__(self) -> None:
        validate_input_bindings(self)
        object.__setattr__(self, "document", _freeze(self.document))


def validate_input_bindings(context: ContractInputBindings) -> None:
    _require(type(context) is ContractInputBindings, "explicit canonical input bindings are required")
    value = context.document
    _require(isinstance(value, Mapping) and set(value) == {
        "schema", "owner_id", "dataset_context_address", "evaluation_context_address", "inputs"
    } and value["schema"] == "canonical-input-bindings/1", "input binding context is incomplete or open")
    owner = _text(value["owner_id"], "owner", 64)
    dataset = _address(value["dataset_context_address"], "dataset context")
    evaluation = _address(value["evaluation_context_address"], "evaluation context")
    inputs = value["inputs"]
    _require(isinstance(inputs, Mapping) and 0 < len(inputs) <= 1024, "input binding context must be bounded and non-empty")
    for name, entry in inputs.items():
        _text(name, "graph input")
        _require(isinstance(entry, Mapping) and set(entry) == {"binding_address", "binding"},
                 "input binding source envelope is incomplete or open")
        _validate_input_fact(entry["binding"], owner, dataset, evaluation)
        _require(_address(entry["binding_address"], "expected input source") == content_address(_plain(entry["binding"])),
                 "input binding differs from its independently pinned source")
    _require(context.context_address == content_address(_plain(value)), "input context address is stale or forged")


def canonical_input_bindings(*, owner_id: str, dataset_context_address: str,
                             evaluation_context_address: str, bindings: Mapping[str, Any],
                             expected_source_addresses: Mapping[str, str]) -> ContractInputBindings:
    """No expected address is derived here: the verified data producer supplies it."""
    _require(isinstance(bindings, Mapping) and isinstance(expected_source_addresses, Mapping)
             and set(bindings) == set(expected_source_addresses), "pinned sources must cover the exact input set")
    for name in bindings:
        _text(name, "graph input")
    document = {"schema": "canonical-input-bindings/1", "owner_id": owner_id,
                "dataset_context_address": dataset_context_address,
                "evaluation_context_address": evaluation_context_address,
                "inputs": {key: {"binding_address": expected_source_addresses[key], "binding": _plain(value)}
                           for key, value in sorted(bindings.items())}}
    try:
        return ContractInputBindings(document, content_address(document))
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise NodeContractRefusal("canonical input bindings are invalid or differ from pinned sources") from exc


def input_binding_for_node(graph: Any, node: Any, source_contract: Mapping[str, Any],
                           context: ContractInputBindings) -> Mapping[str, Any]:
    validate_input_bindings(context)
    ports = {}
    primary = source_contract["required_resolution"]["port"]
    for port in source_contract["parameter_binding"]["input_ports"]:
        bundle = graph.bundles.get((node.node_id, port))
        _require(bundle is not None and bundle.assembly == "single" and len(bundle.members) == 1
                 and bundle.default is None, "contract binding requires an exact connected canonical input")
        member = bundle.members[0]
        endpoint = member.source
        _require(isinstance(endpoint, Mapping) and set(endpoint) == {"scope", "port_id"}
                 and endpoint["scope"] == "graph_input", "unknown or derived input binding source requires an explicit canonical producer")
        name = endpoint["port_id"]
        _require(name in graph.graph_inputs and name in context.document["inputs"], "canonical graph input binding is missing")
        source = context.document["inputs"][name]
        # The resolution port is local; its pinned fact owns the instrument role.
        _require(port == primary or source["binding"]["instrument"]["role"] == port,
                 "canonical input role is swapped or mismatched")
        ports[port] = {"source": _plain(endpoint), **_plain(source)}
    return _freeze({"schema": "node-input-binding/1", "owner_id": context.document["owner_id"],
                    "dataset_context_address": context.document["dataset_context_address"],
                    "evaluation_context_address": context.document["evaluation_context_address"],
                    "context_address": context.context_address, "ports": ports})


def binding_result(inputs, *, fields_by_port, warmup_history, output_warmup):
    """Pure declaration builder. No imports, I/O, indicator math or hidden defaults.

    All validation happens again at materialization. Keeping this helper's closure
    to builtins makes its entire source directly identifiable by the registry.
    """
    if type(warmup_history) is not int or warmup_history < 0:
        raise ValueError("warmup must be a nonnegative exact integer")
    rows = []
    required = set()
    for port in sorted(fields_by_port):
        source = inputs["ports"][port]["binding"]
        for field in fields_by_port[port]:
            role = source["instrument"]["role"]
            required.add(field.lower() if role == "primary" else role + "." + field.lower())
            rows.append({"requirement_id": port + "_" + field.lower(),
                         "instrument": dict(source["instrument"]), "field": field,
                         "timeframe": source["timeframe"],
                         "history": {"minimum_bars": 1, "warmup_bars": warmup_history},
                         "freshness": dict(source["freshness"]), "depth": dict(source["depth"]),
                         "session": source["session"], "alignment": dict(source["alignment"]),
                         "derived_local": source["derived_local"]})
    return {"required_market_fields": sorted(required), "warmup_history": warmup_history,
            "output_warmup": dict(output_warmup),
            "bound_requirements": sorted(rows, key=lambda row: row["requirement_id"])}


@dataclass(frozen=True)
class ResolvedNodeContract:
    """Immutable receipt transport; only registry replay proves its authority.

    Construction validates the envelope and content address, not the rule's
    truth. Obtain authoritative receipts from canonical plan compilation or
    verification before using them as an expected state binding.
    """

    document: Mapping[str, Any]
    bound_contract_address: str

    def __post_init__(self) -> None:
        value = self.document
        _require(isinstance(value, Mapping) and set(value) == {
            "schema", "component", "source_contract_address", "binding_implementation_address",
            "parameters", "input_binding", "resolved_contract", "bound_requirements", "bound_contract_address"
        } and value["schema"] == "resolved-node-contract/1", "resolved node contract is incomplete or open")
        expected = content_address({key: _plain(item) for key, item in value.items() if key != "bound_contract_address"})
        _require(self.bound_contract_address == value["bound_contract_address"] == expected,
                 "resolved node contract address is stale or forged")
        object.__setattr__(self, "document", _freeze(value))


def _validate_node_input_binding(source, input_binding):
    _require(isinstance(input_binding, Mapping) and set(input_binding) == {
        "schema", "owner_id", "dataset_context_address", "evaluation_context_address", "context_address", "ports"
    } and input_binding["schema"] == "node-input-binding/1", "node input binding is incomplete or open")
    _text(input_binding["owner_id"], "owner", 64)
    _address(input_binding["dataset_context_address"], "dataset context")
    _address(input_binding["evaluation_context_address"], "evaluation context")
    _address(input_binding["context_address"], "input context")
    expected_ports = set(source["parameter_binding"]["input_ports"])
    _require(isinstance(input_binding["ports"], Mapping) and set(input_binding["ports"]) == expected_ports,
             "node input binding ports differ from source contract")
    for port, entry in input_binding["ports"].items():
        _require(isinstance(entry, Mapping) and set(entry) == {"source", "binding_address", "binding"},
                 "node input source is incomplete or open")
        endpoint = entry["source"]
        _require(isinstance(endpoint, Mapping) and set(endpoint) == {"scope", "port_id"}
                 and endpoint["scope"] == "graph_input", "node input source is not canonical")
        _text(endpoint["port_id"], "graph input")
        _validate_input_fact(entry["binding"], input_binding["owner_id"],
                             input_binding["dataset_context_address"], input_binding["evaluation_context_address"])
        _require(port == source["required_resolution"]["port"] or entry["binding"]["instrument"]["role"] == port,
                 "node input role is swapped or mismatched")
        _require(entry["binding_address"] == content_address(_plain(entry["binding"])), "node input source address differs")


def _bound_declared_fields(source, input_binding):
    declared = set(source["required_market_fields"])
    resolution_port = source["required_resolution"]["port"]
    bound = set()
    for port, entry in input_binding["ports"].items():
        role = entry["binding"]["instrument"]["role"]
        for field in entry["binding"]["fields"]:
            local = field.lower() if port == resolution_port else port + "." + field.lower()
            if local in declared:
                bound.add(field.lower() if role == "primary" else role + "." + field.lower())
    return bound


def _validate_bound_requirement_shape(row):
    from app.ir.registry import _DATA_ID

    _require(isinstance(row, Mapping) and set(row) == {"requirement_id", *_REQUIREMENT_FIELDS}
             and isinstance(row["requirement_id"], str) and bool(_DATA_ID.fullmatch(row["requirement_id"])),
             "bound requirement is incomplete or open")


def _validate_bound_requirement_facts(row, history, input_binding):
    from app.ir.registry import _validate_data_direct

    try:
        for field in _REQUIREMENT_FIELDS:
            _validate_data_direct(field, row[field])
    except (TypeError, ValueError) as exc:
        raise NodeContractRefusal("bound requirement has invalid data facts") from exc
    _require(row["history"]["minimum_bars"] >= 1 and row["history"]["warmup_bars"] == history,
             "bound requirement understates or changes exact warmup")
    _match_bound_input(row, input_binding)


def _match_bound_input(row, input_binding):
    matching = [entry["binding"] for entry in input_binding["ports"].values()
                if entry["binding"]["instrument"] == row["instrument"]
                and row["field"] in entry["binding"]["fields"]]
    _require(len(matching) == 1, "bound field/role does not identify one canonical input")
    for field in ("timeframe", "freshness", "depth", "session", "alignment", "derived_local"):
        _require(row[field] == matching[0][field], "binding altered canonical input " + field)


def _validate_bound_rows(rows, fields, history, input_binding):
    seen = set(); actual_fields = set()
    for row in rows:
        _validate_bound_requirement_shape(row)
        _require(row["requirement_id"] not in seen, "duplicate bound requirement")
        seen.add(row["requirement_id"])
        _validate_bound_requirement_facts(row, history, input_binding)
        role = row["instrument"]["role"]
        actual_fields.add(row["field"].lower() if role == "primary" else role + "." + row["field"].lower())
    _require(actual_fields == set(fields) and [row["requirement_id"] for row in rows] == sorted(seen),
             "bound field/requirement closure is incomplete or reordered")

def _validate_bound_warmup(source, result):
    history = result["warmup_history"]
    _require(type(history) is int and 0 <= history <= 1000000, "bound warmup must be a bounded exact integer")
    output_warmup = result["output_warmup"]
    _require(isinstance(output_warmup, Mapping) and set(output_warmup) == set(source["output_types"])
             and all(type(value) is int and 0 <= value <= history for value in output_warmup.values())
             and max(output_warmup.values()) == history, "binding must cover every output's exact warmup")
    return history, output_warmup


def _validate_bound_fields(source, result, input_binding):
    fields = result["required_market_fields"]
    _require(isinstance(fields, (tuple, list)) and fields
             and all(isinstance(field, str) for field in fields)
             and tuple(fields) == tuple(sorted(set(fields)))
             and set(fields) <= _bound_declared_fields(source, input_binding), "bound fields are undeclared or noncanonical")
    return fields


def _validate_binding_result(source, result, input_binding):
    _require(isinstance(result, Mapping) and set(result) == {
        "required_market_fields", "warmup_history", "output_warmup", "bound_requirements"
    }, "binding result is incomplete or open")
    history, output_warmup = _validate_bound_warmup(source, result)
    fields = _validate_bound_fields(source, result, input_binding)
    rows = result["bound_requirements"]
    _require(isinstance(rows, (tuple, list)) and 0 < len(rows) <= 1024, "bound requirements must be bounded and explicit")
    _validate_bound_rows(rows, fields, history, input_binding)
    return fields, rows, history, output_warmup


def materialize_node_contract(source: Mapping[str, Any], registration: Any,
                              parameters: Mapping[str, Any], input_binding: Mapping[str, Any]) -> ResolvedNodeContract:
    """Called only after registry/source/implementation and context verification."""
    contract = _canonical_source_contract_v2(registration.component, source)
    _require(contract.contract_address == registration.source_contract_address,
             "binding registration has wrong source contract")
    _validate_node_input_binding(source, input_binding)
    try:
        result = registration.implementation(_freeze(parameters), _freeze(input_binding))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise NodeContractRefusal("registered binding refused its exact inputs") from exc
    fields, rows, history, output_warmup = _validate_binding_result(source, result, input_binding)
    resolution = source["required_resolution"]
    primary = input_binding["ports"][resolution["port"]]["binding"]
    resolved = {key: _plain(source[key]) for key in NODE_CONTRACT_FIELDS}
    resolved.update({"required_market_fields": list(fields), "warmup_history": history,
                     "required_resolution": {"timeframe_seconds": primary["timeframe"], "alignment": resolution["alignment"]},
                     "output_warmup": {key: output_warmup[key] for key in sorted(output_warmup)}})
    document = {"schema": "resolved-node-contract/1",
                "component": {"component_id": registration.component[0], "component_version": registration.component[1]},
                "source_contract_address": contract.contract_address,
                "binding_implementation_address": registration.implementation_address,
                "parameters": _plain(parameters), "input_binding": _plain(input_binding),
                "resolved_contract": resolved, "bound_requirements": _plain(rows)}
    address = content_address(document)
    return ResolvedNodeContract({**document, "bound_contract_address": address}, address)
