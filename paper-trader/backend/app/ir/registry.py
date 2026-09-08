"""Immutable transport for Component IR declarations and implementations."""
from __future__ import annotations

from dataclasses import dataclass
import dis
import inspect
import types
from types import MappingProxyType, SimpleNamespace
from typing import Any, Callable, Mapping
import re

from app.ir.causal import CausalContract
from app.ir.hashing import canonical_json, content_address
from app.ir.implementation_identity import ImplementationUnidentified, implementation_address
from app.ir.kernels import KernelSpec, kernel_spec
from app.ir.resolve import Library, ResolutionError, validate_graph_component_body
from app.ir.schema import is_content_address


@dataclass(frozen=True)
class DependencyBoundary:
    mode: str
    objects: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in {"declared_objects", "defining_module"}:
            raise ValueError(f"unsupported dependency boundary {self.mode!r}")
        object.__setattr__(self, "objects", tuple(self.objects))


@dataclass(frozen=True)
class KernelRegistration:
    body_ref: str
    spec: KernelSpec
    implementation: Callable[..., Mapping[str, Any]]
    dependency_boundary: DependencyBoundary
    implementation_address: str


@dataclass(frozen=True)
class V2ImplementationRegistration:
    """The registry-owned executable identity for one v2 leaf component."""

    component: tuple[str, int]
    implementation: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    dependency_boundary: DependencyBoundary
    implementation_address: str


@dataclass(frozen=True)
class ContractBindingRegistration:
    """One reviewed pure binding rule; no numerical or execution authority."""

    rule_id: str
    rule_version: int
    component: tuple[str, int]
    source_contract_address: str
    implementation_address: str
    implementation: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    dependency_boundary: DependencyBoundary

    @property
    def document(self) -> Mapping[str, Any]:
        return _freeze({
            "rule_id": self.rule_id, "rule_version": self.rule_version,
            "component": {"component_id": self.component[0], "component_version": self.component[1]},
            "source_contract_address": self.source_contract_address,
            "implementation_address": self.implementation_address,
        })


def registered_contract_binding(
    *, component: tuple[str, int], source_contract: Mapping[str, Any],
    implementation: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    dependency_boundary: DependencyBoundary,
) -> ContractBindingRegistration:
    contract = _canonical_registry_node_contract(component, source_contract)
    if contract.document.get("schema") != "first-party-node-contract/2":
        raise ValueError("binding registration requires a source /2 contract")
    _reject_ambient_binding_code(implementation)
    rule = contract.document["parameter_binding"]
    return ContractBindingRegistration(
        rule["rule_id"], rule["rule_version"], component, contract.contract_address,
        implementation_address(implementation, dependency_boundary),
        implementation, dependency_boundary,
    )


def registered_v2_implementation(
    *, component: tuple[str, int], implementation: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    dependency_boundary: DependencyBoundary,
) -> V2ImplementationRegistration:
    return V2ImplementationRegistration(
        component=component,
        implementation=implementation,
        dependency_boundary=dependency_boundary,
        implementation_address=implementation_address(implementation, dependency_boundary),
    )


def registered_kernel(
    *,
    body_ref: str,
    implementation: Callable[..., Mapping[str, Any]],
    causal: CausalContract,
    dependency_boundary: DependencyBoundary,
    warmup: int | Callable[[Mapping[str, Any]], int] = 0,
    purity: str = "pure",
    cache_identity: str = "transitive",
    cache_key: str | None = None,
) -> KernelRegistration:
    """Create one registration; the implementation address is never caller input."""
    if not is_content_address(body_ref):
        raise ValueError("body_ref must be a canonical content address")
    spec = kernel_spec(
        warmup=warmup,
        purity=purity,
        cache_identity=cache_identity,
        cache_key=cache_key,
        causal=causal,
    )
    address = implementation_address(
        implementation,
        dependency_boundary,
        recursive_state=causal.recursive_state,
    )
    return KernelRegistration(
        body_ref=body_ref,
        spec=spec,
        implementation=implementation,
        dependency_boundary=dependency_boundary,
        implementation_address=address,
    )


class PlatformRegistry:
    """One immutable authority for component bytes and executable registrations."""

    def __init__(
        self,
        *,
        components: Mapping[tuple[str, int], Mapping[str, Any]],
        bodies: Mapping[str, Mapping[str, Any]],
        registrations: Mapping[str, KernelRegistration],
        v2_types: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
        v2_components: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
        v2_implementations: Mapping[tuple[str, int], V2ImplementationRegistration] | None = None,
        data_requirement_declarations: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
        node_contracts: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
        contract_bindings: Mapping[tuple[str, int], ContractBindingRegistration] | None = None,
    ) -> None:
        copied_components = {key: _freeze(value) for key, value in components.items()}
        copied_bodies = {key: _freeze(value) for key, value in bodies.items()}
        copied_registrations = dict(registrations)
        copied_v2_types = {key: _freeze(value) for key, value in (v2_types or {}).items()}
        copied_v2_components = {key: _freeze(value) for key, value in (v2_components or {}).items()}
        copied_v2_implementations = dict(v2_implementations or {})
        _validate_v2_registry(copied_v2_types, copied_v2_components)
        _validate_v2_implementation_closure(copied_v2_components, copied_v2_implementations)
        copied_node_contracts, node_contract_addresses = _validate_registry_contract_closure(
            copied_v2_components, node_contracts or {},
        )
        declarations = dict(data_requirement_declarations or {})
        for key, contract in copied_node_contracts.items():
            if contract.get("schema") == "first-party-node-contract/2":
                # The source contract is its dynamic declaration. Never fabricate
                # literal history rows or mark a bound-data node as NO_DATA.
                if key in declarations and _plain(declarations[key]) != _plain(contract):
                    raise ValueError("binding declaration differs from its source contract")
                declarations[key] = contract
        copied_declarations, declaration_addresses = _validate_data_requirement_declarations(
            copied_v2_components, declarations,
        )
        copied_bindings = dict(contract_bindings or {})
        _validate_contract_binding_closure(copied_v2_components, copied_node_contracts,
                                          node_contract_addresses, copied_bindings)
        for key, declaration in copied_declarations.items():
            if declaration.get("schema") == "first-party-node-contract/2" and key not in copied_bindings:
                raise ValueError("dynamic declaration lacks its exact contract binding")
        for ref, registration in copied_registrations.items():
            if ref != registration.body_ref:
                raise ValueError(
                    f"registration key {ref!r} differs from body_ref {registration.body_ref!r}"
                )
            try:
                actual_address = implementation_address(
                    registration.implementation,
                    registration.dependency_boundary,
                    recursive_state=(registration.spec.causal.recursive_state
                                     if registration.spec.causal else None),
                )
            except ImplementationUnidentified as exc:
                raise ValueError(
                    f"registration {ref} has stale implementation dependency closure"
                ) from exc
            if actual_address != registration.implementation_address:
                raise ValueError(
                    f"registration {ref} has stale or forged implementation_address"
                )
        component_kernel_refs = {
            component["body"]["ref"]
            for component in copied_components.values()
            if component.get("body", {}).get("body") == "kernel"
        }
        if component_kernel_refs != set(copied_registrations):
            missing = sorted(component_kernel_refs - set(copied_registrations))
            extra = sorted(set(copied_registrations) - component_kernel_refs)
            raise ValueError(
                f"component/registration closure differs; missing={missing}, extra={extra}"
            )
        component_graph_refs = {
            component["body"]["ref"]
            for component in copied_components.values()
            if component.get("body", {}).get("body") == "graph"
        }
        if component_graph_refs != set(copied_bodies):
            missing = sorted(component_graph_refs - set(copied_bodies))
            extra = sorted(set(copied_bodies) - component_graph_refs)
            raise ValueError(
                f"component/graph body closure differs; missing={missing}, extra={extra}"
            )
        for ref, body in copied_bodies.items():
            if content_address(body) != ref:
                raise ValueError(f"graph body {ref} does not match its content address")
        for component in copied_components.values():
            if component.get("body", {}).get("body") != "graph":
                continue
            try:
                validate_graph_component_body(
                    component,
                    copied_bodies[component["body"]["ref"]],
                    copied_components,
                    "$",
                )
            except ResolutionError as exc:
                raise ValueError(str(exc)) from exc
        self._registrations = MappingProxyType(copied_registrations)
        self._library = Library(
            components=MappingProxyType(copied_components),
            bodies=MappingProxyType(copied_bodies),
            kernels=MappingProxyType({
                ref: registration.spec
                for ref, registration in copied_registrations.items()
            }),
        )
        self._implementations = MappingProxyType({
            ref: registration.implementation
            for ref, registration in copied_registrations.items()
        })
        self._v2_types = MappingProxyType(copied_v2_types)
        self._v2_components = MappingProxyType(copied_v2_components)
        self._v2_implementations = MappingProxyType({
            key: registration.implementation for key, registration in copied_v2_implementations.items()
        })
        self._v2_implementation_registrations = MappingProxyType(copied_v2_implementations)
        self._v2_implementation_identities = MappingProxyType({
            key: registration.implementation_address for key, registration in copied_v2_implementations.items()
        })
        self._data_requirement_declarations = MappingProxyType(copied_declarations)
        self._data_requirement_declaration_addresses = MappingProxyType(declaration_addresses)
        self._node_contracts = MappingProxyType(copied_node_contracts)
        self._node_contract_addresses = MappingProxyType(node_contract_addresses)
        self._contract_bindings = MappingProxyType(copied_bindings)
        snapshot = {
            "v1_components": _snapshot_entries(copied_components), "v1_bodies": _plain(copied_bodies),
            "v1_implementations": {key: value.implementation_address for key, value in copied_registrations.items()},
            "v2_types": _snapshot_entries(copied_v2_types), "v2_components": _snapshot_entries(copied_v2_components),
            "v2_implementations": _snapshot_entries(self._v2_implementation_identities),
            "data_requirement_declarations": [
                {"component_id": key[0], "component_version": key[1], "declaration_address": declaration_addresses[key]}
                for key in sorted(declaration_addresses)
            ],
        }
        if node_contract_addresses:
            snapshot["node_contracts"] = [
                {
                    "component_id": key[0],
                    "component_version": key[1],
                    "contract_address": node_contract_addresses[key],
                    "contract": _plain(copied_node_contracts[key]),
                }
                for key in sorted(node_contract_addresses)
            ]
        if copied_bindings:
            snapshot["contract_bindings"] = [
                _plain(copied_bindings[key].document) for key in sorted(copied_bindings)
            ]
        self._registry_snapshot_payload = _freeze(snapshot)
        self._registry_snapshot_address = content_address(_plain(self._registry_snapshot_payload))

    @property
    def registrations(self) -> Mapping[str, KernelRegistration]:
        return self._registrations

    @property
    def library(self) -> Library:
        return self._library

    @property
    def implementations(self) -> Mapping[str, Callable[..., Mapping[str, Any]]]:
        return self._implementations

    @property
    def v2_types(self) -> Mapping[tuple[str, int], Mapping[str, Any]]:
        return self._v2_types

    @property
    def v2_components(self) -> Mapping[tuple[str, int], Mapping[str, Any]]:
        return self._v2_components

    @property
    def v2_implementations(self) -> Mapping[tuple[str, int], Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]]:
        return self._v2_implementations

    @property
    def v2_implementation_registrations(self) -> Mapping[tuple[str, int], V2ImplementationRegistration]:
        return self._v2_implementation_registrations

    @property
    def v2_implementation_identities(self) -> Mapping[tuple[str, int], str]:
        return self._v2_implementation_identities

    @property
    def data_requirement_declarations(self) -> Mapping[tuple[str, int], Mapping[str, Any]]:
        return self._data_requirement_declarations

    @property
    def data_requirement_declaration_addresses(self) -> Mapping[tuple[str, int], str]:
        return self._data_requirement_declaration_addresses

    @property
    def node_contracts(self) -> Mapping[tuple[str, int], Mapping[str, Any]]:
        return self._node_contracts

    @property
    def node_contract_addresses(self) -> Mapping[tuple[str, int], str]:
        return self._node_contract_addresses

    @property
    def contract_bindings(self) -> Mapping[tuple[str, int], ContractBindingRegistration]:
        return self._contract_bindings

    def validate_contract_bindings(self) -> None:
        _validate_contract_binding_closure(self._v2_components, self._node_contracts,
                                          self._node_contract_addresses, self._contract_bindings)
        if self._contract_bindings:
            actual = [_plain(self._contract_bindings[key].document) for key in sorted(self._contract_bindings)]
            if actual != _plain(self._registry_snapshot_payload.get("contract_bindings")):
                raise ValueError("contract bindings differ from their registry snapshot")

    def bind_node_contract(self, component: tuple[str, int], parameters: Mapping[str, Any],
                           input_binding: Mapping[str, Any]):
        """Replay this registry's exact binding; stored receipt hashes are not proof."""
        from app.ir.first_party.analytical_v2.contracts import (
            canonical_binding_parameters, materialize_node_contract,
        )

        self.validate_contract_bindings()
        if component not in self._contract_bindings:
            raise ValueError("unknown node contract binding")
        registration = self._contract_bindings[component]
        params = canonical_binding_parameters(parameters, self._v2_components[component]["parameters"])
        return materialize_node_contract(self._node_contracts[component], registration,
                                         params, input_binding)

    @property
    def registry_snapshot_address(self) -> str:
        return self._registry_snapshot_address

    @property
    def registry_snapshot_payload(self) -> Mapping[str, Any]:
        """Frozen bytes behind ``registry_snapshot_address`` for downstream verification."""
        return self._registry_snapshot_payload


def _validate_v2_registry(types: Mapping[tuple[str, int], Mapping[str, Any]], components: Mapping[tuple[str, int], Mapping[str, Any]]) -> None:
    """Reject incomplete v2 declarations at the single immutable registry boundary."""
    type_keys = frozenset({"type_id", "type_version", "shapes", "runtime_representation"})
    component_keys = frozenset({"component_id", "component_version", "domain_family", "structural_role", "ports", "parameters", "compound", "numeric_validity"})
    for key, descriptor in types.items():
        if not isinstance(descriptor, Mapping) or set(descriptor) != type_keys:
            raise ValueError(f"v2 type {key!r} must have exactly {sorted(type_keys)}")
        if key != (descriptor.get("type_id"), descriptor.get("type_version")):
            raise ValueError(f"v2 type key {key!r} conflicts with descriptor")
        if not isinstance(key[0], str) or not key[0] or isinstance(key[1], bool) or not isinstance(key[1], int) or key[1] < 1:
            raise ValueError(f"v2 type {key!r} has invalid exact reference")
        if not isinstance(descriptor["shapes"], (tuple, list, frozenset)) or not descriptor["shapes"]:
            raise ValueError(f"v2 type {key!r} must declare supported shapes")
    for key, component in components.items():
        if not isinstance(component, Mapping) or set(component) - component_keys:
            raise ValueError(f"v2 component {key!r} has unknown declaration fields")
        required = {"component_id", "component_version", "domain_family", "structural_role", "ports", "parameters"}
        if not required <= set(component):
            raise ValueError(f"v2 component {key!r} is incomplete")
        if key != (component.get("component_id"), component.get("component_version")):
            raise ValueError(f"v2 component key {key!r} conflicts with descriptor")
        _validate_numeric_validity_declaration(key, component.get("numeric_validity"))
        from app.ir.schema import V2_COMPONENT_DOMAIN_FAMILIES, V2_COMPONENT_STRUCTURAL_ROLES
        if component["domain_family"] not in V2_COMPONENT_DOMAIN_FAMILIES or component["structural_role"] not in V2_COMPONENT_STRUCTURAL_ROLES:
            raise ValueError(f"v2 component {key!r} has unregistered classification")
        ports = component["ports"]
        if not isinstance(ports, (tuple, list)) or len({port.get("port_id") for port in ports if isinstance(port, Mapping)}) != len(ports):
            raise ValueError(f"v2 component {key!r} has non-unique ports")
        for port in ports:
            if not isinstance(port, Mapping): raise ValueError(f"v2 component {key!r} has invalid port")
            ref = port.get("type_ref", {})
            if (ref.get("type_id"), ref.get("type_version")) not in types:
                raise ValueError(f"v2 component {key!r} references an unknown type")
            if port.get("shape") not in types[(ref.get("type_id"), ref.get("type_version"))]["shapes"]:
                raise ValueError(f"v2 component {key!r} port shape conflicts with type")
        _validate_v2_compound(key, component, components, types)
    _validate_v2_component_closure(components)


def _validate_numeric_validity_declaration(key: tuple[str, int], declaration: Any) -> None:
    """Keep Phase 4 policy declaration closed at the existing registry seam."""
    if declaration is None:
        return
    if not isinstance(declaration, Mapping) or set(declaration) != {"input_policy", "output_policy"}:
        raise ValueError(f"v2 component {key!r} numeric_validity must be closed")
    if declaration["input_policy"] not in {"propagate", "explicit_fallback"}:
        raise ValueError(f"v2 component {key!r} has unknown numeric input policy")
    if declaration["output_policy"] != "numeric_envelope":
        raise ValueError(f"v2 component {key!r} has unknown numeric output policy")


_DATA_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_DATA_FIELDS = frozenset({"OPEN", "HIGH", "LOW", "CLOSE", "LAST", "BID", "ASK", "BID_SIZE", "ASK_SIZE", "TRADE", "VOLUME", "OPEN_INTEREST", "IMPLIED_VOLATILITY", "DELTA", "GAMMA", "VEGA", "THETA", "SESSION_ID", "SESSION_OPEN_AT", "SESSION_CLOSE_AT"})


def _validate_data_requirement_declarations(components: Mapping[tuple[str, int], Mapping[str, Any]], declarations: Mapping[tuple[str, int], Mapping[str, Any]]) -> tuple[dict[tuple[str, int], Mapping[str, Any]], dict[tuple[str, int], str]]:
    copied: dict[tuple[str, int], Mapping[str, Any]] = {}
    addresses: dict[tuple[str, int], str] = {}
    for key, raw in declarations.items():
        if key not in components or components[key].get("compound") is not None:
            raise ValueError(f"data requirement declaration {key!r} must belong to a registered v2 leaf")
        normalized = _normalize_data_declaration(key, raw, components[key])
        copied[key] = _freeze(normalized)
        addresses[key] = content_address(normalized)
    return copied, addresses


def _snapshot_entries(values: Mapping[tuple[str, int], Any]) -> list[dict[str, Any]]:
    return [
        {"component_id": key[0], "component_version": key[1], "value": _plain(value)}
        for key, value in sorted(values.items())
    ]


def _normalize_data_declaration(key: tuple[str, int], value: Any, component: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping) and value.get("schema") == "first-party-node-contract/2":
        return _plain(_canonical_registry_node_contract(key, value).document)
    if not isinstance(value, Mapping) or set(value) != {"schema", "classification", "requirements"}:
        raise ValueError(f"data requirement declaration {key!r} must have exactly schema, classification, requirements")
    if value["schema"] != "data-requirement-declaration/1" or value["classification"] not in {"NO_DATA", "REQUIRES_DATA"} or not isinstance(value["requirements"], (list, tuple)):
        raise ValueError(f"data requirement declaration {key!r} is malformed")
    rows = [_normalize_data_row(key, row, component) for row in value["requirements"]]
    ids = [row["requirement_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"data requirement declaration {key!r} has duplicate requirement_id")
    if (value["classification"] == "NO_DATA") != (not rows):
        raise ValueError(f"data requirement declaration {key!r} classification conflicts with requirements")
    return {"schema": "data-requirement-declaration/1", "classification": value["classification"], "requirements": sorted(rows, key=lambda row: row["requirement_id"].encode())}


def _canonical_registry_node_contract(component, document):
    """One registry-owned dispatch, retaining the frozen /1 helper unchanged.

    Legacy numerical modules hash node_contracts.py as a dependency. Moving the
    /2 private implementation there would silently change their v1 identities.
    """
    if isinstance(document, Mapping) and document.get("schema") == "first-party-node-contract/2":
        from app.ir.first_party.analytical_v2.contracts import _canonical_source_contract_v2
        return _canonical_source_contract_v2(component, document)
    from app.ir.node_contracts import canonical_node_contract
    return canonical_node_contract(component, document)


def _validate_registry_contract_closure(components, contracts):
    from app.ir.node_contracts import NodeContractRefusal, validate_node_contract_closure
    legacy = {key: value for key, value in contracts.items()
              if not isinstance(value, Mapping) or value.get("schema") != "first-party-node-contract/2"}
    copied, addresses = validate_node_contract_closure(components, legacy)
    for key, value in contracts.items():
        if key in legacy:
            continue
        descriptor = components.get(key)
        if descriptor is None or descriptor.get("compound") is not None:
            raise NodeContractRefusal("source contract must belong to an exact registered leaf")
        contract = _canonical_registry_node_contract(key, value)
        inputs = sorted(port["port_id"] for port in descriptor["ports"] if port["direction"] == "input")
        outputs = sorted(port["port_id"] for port in descriptor["ports"] if port["direction"] == "output")
        if (inputs != list(contract.document["input_types"])
                or outputs != list(contract.document["output_types"])
                or sorted(descriptor["parameters"]) != list(contract.document["parameter_binding"]["parameter_names"])):
            raise NodeContractRefusal("source /2 parameter or typed port closure differs from descriptor")
        copied[key] = contract.document
        addresses[key] = contract.contract_address
    return copied, addresses


def _validate_contract_binding_closure(components, contracts, addresses, bindings) -> None:
    required = {key for key, value in contracts.items()
                if value.get("schema") == "first-party-node-contract/2"}
    if set(bindings) != required:
        raise ValueError("contract binding closure has missing or extra registrations")
    if not required:
        return
    from app.ir.first_party.analytical_v2.contracts import validate_parameter_descriptors
    rules: set[tuple[str, int]] = set()
    for key, registration in bindings.items():
        contract = contracts[key]
        if _canonical_registry_node_contract(key, contract).contract_address != addresses[key]:
            raise ValueError("contract binding source address is stale")
        rule = contract["parameter_binding"]
        if (not isinstance(registration, ContractBindingRegistration)
                or registration.component != key
                or registration.source_contract_address != addresses[key]
                or registration.rule_id != rule["rule_id"]
                or type(registration.rule_version) is not int
                or registration.rule_version != rule["rule_version"]):
            raise ValueError("contract binding registration disagrees with its source contract")
        identity = (registration.rule_id, registration.rule_version)
        if identity in rules:
            raise ValueError("contract binding rule identity has conflicting owners")
        rules.add(identity)
        _reject_ambient_binding_code(registration.implementation)
        actual = implementation_address(registration.implementation, registration.dependency_boundary)
        if actual != registration.implementation_address:
            raise ValueError("contract binding implementation identity is stale or forged")
        validate_parameter_descriptors(components[key]["parameters"])


def _reject_ambient_binding_code(implementation) -> None:
    """Conservative defense for trusted registry code, not an untrusted-code sandbox.

    Binding rules describe requirements and may use scalar arithmetic and pure
    helpers. They cannot import at runtime, read a clock/file/provider, or mutate
    captured state. Exact transitive identity is still checked independently.
    """
    from app.ir.implementation_identity import ImplementationUnidentified
    forbidden_names = {"open", "input", "print", "exec", "eval", "compile", "globals", "locals",
                       "vars", "__import__", "__builtins__", "getattr", "setattr", "delattr", "breakpoint"}
    forbidden_attributes = {"now", "utcnow", "today", "random", "rand", "randn", "randint",
                            "randrange", "default_rng", "urandom", "uuid4", "read", "write",
                            "read_text", "write_text", "read_bytes", "write_bytes", "connect"}
    seen = set()

    def check_code(code):
        for instruction in dis.get_instructions(code):
            if (instruction.opname in {"IMPORT_NAME", "IMPORT_FROM", "STORE_GLOBAL", "DELETE_GLOBAL", "STORE_ATTR", "DELETE_ATTR"}
                    or instruction.opname in {"STORE_DEREF", "DELETE_DEREF"} and instruction.argval in code.co_freevars
                    or instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"} and instruction.argval in forbidden_names
                    or instruction.opname in {"LOAD_ATTR", "LOAD_METHOD"} and instruction.argval in forbidden_attributes):
                raise ImplementationUnidentified("contract binding uses runtime import, ambient I/O/clock or mutable state")
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                check_code(value)

    def visit(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if inspect.isfunction(value):
            check_code(value.__code__)
            closure = inspect.getclosurevars(value)
            for dependency in (*closure.globals.values(), *closure.nonlocals.values()):
                visit(dependency)
            for dependency in (*(value.__defaults__ or ()), *(value.__kwdefaults__ or {}).values()):
                visit(dependency)
        elif inspect.ismodule(value):
            if value.__name__ not in {"math", "datetime"}:
                raise ImplementationUnidentified("contract binding has an ambient module dependency")
        elif isinstance(value, (dict, list, set)):
            raise ImplementationUnidentified("contract binding closes over mutable global state")
        elif isinstance(value, (tuple, frozenset)):
            for dependency in value:
                visit(dependency)
        elif value is not None and type(value) not in {str, int, float, bool, bytes}:
            raise ImplementationUnidentified("contract binding has an unsupported ambient dependency")

    if not inspect.isfunction(implementation):
        raise ImplementationUnidentified("contract binding must be a source-identifiable pure function")
    visit(implementation)


def _normalize_data_row(key: tuple[str, int], row: Any, component: Mapping[str, Any]) -> dict[str, Any]:
    fields = ("instrument", "field", "timeframe", "history", "freshness", "depth", "session", "alignment", "derived_local")
    if not isinstance(row, Mapping) or set(row) != {"requirement_id", *fields} or not isinstance(row["requirement_id"], str) or not _DATA_ID.fullmatch(row["requirement_id"]):
        raise ValueError(f"data requirement declaration {key!r} has malformed requirement row")
    result = {"requirement_id": row["requirement_id"]}
    for field in fields:
        expression = row[field]
        if not isinstance(expression, Mapping) or set(expression) not in ({"literal"}, {"parameter"}):
            raise ValueError(f"data requirement declaration {key!r} {field} must be whole-field literal or parameter")
        if "parameter" in expression:
            parameter = expression["parameter"]
            if not isinstance(parameter, str) or parameter not in component["parameters"]:
                raise ValueError(f"data requirement declaration {key!r} has unbound parameter")
            result[field] = {"parameter": parameter}
        else:
            _validate_data_direct(field, expression["literal"])
            result[field] = {"literal": _freeze(expression["literal"])}
    return result


def _integer(value: Any, *, positive: bool = False) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= (1 if positive else 0)


def _validate_data_direct(field: str, value: Any) -> None:
    if field == "instrument": valid = isinstance(value, Mapping) and set(value) == {"role", "type"} and isinstance(value["role"], str) and bool(_DATA_ID.fullmatch(value["role"])) and value["type"] in {"PHYSICAL", "ECONOMIC_SELECTOR", "CONTINUOUS_FUTURE"}
    elif field == "field": valid = value in _DATA_FIELDS
    elif field == "timeframe": valid = _integer(value, positive=True)
    elif field == "history": valid = isinstance(value, Mapping) and set(value) == {"minimum_bars", "warmup_bars"} and all(_integer(value[x]) for x in value)
    elif field == "freshness": valid = isinstance(value, Mapping) and set(value) == {"maximum_age_seconds"} and _integer(value["maximum_age_seconds"])
    elif field == "depth": valid = isinstance(value, Mapping) and set(value) == {"kind", "levels"} and value["kind"] in {"NONE", "TOP_OF_BOOK", "BOOK"} and ((value["kind"] == "BOOK" and _integer(value["levels"], positive=True)) or (value["kind"] != "BOOK" and value["levels"] is None))
    elif field == "session": valid = value in {"INSTRUMENT_CALENDAR", "CONTINUOUS", "ALL_RECORDED"}
    elif field == "alignment": valid = isinstance(value, Mapping) and set(value) == {"kind", "maximum_skew_seconds"} and value["kind"] in {"EXACT", "ASOF_BACKWARD", "COMPLETED_RESAMPLE"} and _integer(value["maximum_skew_seconds"])
    else: valid = isinstance(value, bool)
    if not valid: raise ValueError(f"invalid data requirement {field}")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [_plain(item) for item in value]
    return value


def _validate_v2_implementation_closure(
    components: Mapping[tuple[str, int], Mapping[str, Any]],
    registrations: Mapping[tuple[str, int], V2ImplementationRegistration],
) -> None:
    """Close executable v2 identity at construction, never at evaluator call sites."""
    # Empty v2 registration is retained only for declaration-only registries.
    # Once a v2 executable registry is supplied it must close every leaf.
    if not registrations:
        return
    leaves = {key for key, value in components.items() if value.get("compound") is None}
    if set(registrations) != leaves:
        missing = sorted(leaves - set(registrations)); extra = sorted(set(registrations) - leaves)
        raise ValueError(f"v2 implementation closure differs; missing={missing}, extra={extra}")
    for key, registration in registrations.items():
        if registration.component != key:
            raise ValueError(f"v2 implementation registration {key!r} conflicts with component")
        try:
            actual = implementation_address(registration.implementation, registration.dependency_boundary)
        except ImplementationUnidentified as exc:
            raise ValueError(f"v2 implementation {key!r} has stale dependency closure") from exc
        if actual != registration.implementation_address:
            raise ValueError(f"v2 implementation {key!r} has stale or forged implementation_address")


def _validate_v2_compound(
    key: tuple[str, int], component: Mapping[str, Any],
    components: Mapping[tuple[str, int], Mapping[str, Any]], types: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    compound = component.get("compound")
    if compound is None: return
    if not isinstance(compound, Mapping) or set(compound) != {"body", "parameter_bindings"}:
        raise ValueError(f"v2 compound {key!r} must declare only body and parameter_bindings")
    bindings = compound["parameter_bindings"]
    if not isinstance(bindings, (tuple, list)): raise ValueError(f"v2 compound {key!r} bindings must be a list")
    names: set[str] = set(); targets: set[tuple[str, str]] = set()
    parameters = component["parameters"]
    for binding in bindings:
        if not isinstance(binding, Mapping) or set(binding) != {"parameter_id", "targets"}:
            raise ValueError(f"v2 compound {key!r} binding must be closed and transform-free")
        name = binding.get("parameter_id")
        if not isinstance(name, str) or name not in parameters or name in names:
            raise ValueError(f"v2 compound {key!r} has missing or duplicate public parameter binding")
        names.add(name)
        entries = binding.get("targets")
        if not isinstance(entries, (tuple, list)) or not entries: raise ValueError(f"v2 compound {key!r} binding targets must be non-empty")
        for target in entries:
            if not isinstance(target, Mapping) or set(target) != {"node_id", "parameter_id"}:
                raise ValueError(f"v2 compound {key!r} binding target is not direct")
            marker = (target.get("node_id"), target.get("parameter_id"))
            if not all(isinstance(value, str) and value for value in marker) or marker in targets:
                raise ValueError(f"v2 compound {key!r} has duplicate or invalid parameter target")
            targets.add(marker)
    if names != set(parameters):
        missing = sorted(set(parameters) - names)
        extra = sorted(names - set(parameters))
        raise ValueError(
            f"v2 compound {key!r} requires exactly one binding for every public parameter; "
            f"missing={missing}, extra={extra}"
        )
    body = compound["body"]
    required_body_keys = {"graph_inputs", "graph_outputs", "nodes", "edges"}
    if not isinstance(body, Mapping) or set(body) != required_body_keys:
        raise ValueError(f"v2 compound {key!r} body must be a complete ordinary v2 graph")
    # The body is validated by the same graph validator as a top-level v2
    # document.  This keeps topology, endpoint, duplicate-tuple, port, type,
    # cardinality, and cycle rules at one authority boundary.
    from app.ir.formats.v2 import validate_graph_body
    violations = validate_graph_body(body, SimpleNamespace(v2_components=components, v2_types=types))
    if violations:
        first = violations[0]
        raise ValueError(f"v2 compound {key!r} invalid ordinary body {first.code}:{first.path}: {first.message}")
    # When body boundaries are declared, they are the exact public contract;
    # accepting a default/cardinality/type drift here would make expansion
    # silently change the component the graph named.
    for public_direction, body_key in (("input", "graph_inputs"), ("output", "graph_outputs")):
        boundary = body[body_key]
        if not isinstance(boundary, (tuple, list)):
            raise ValueError(f"v2 compound {key!r} body {body_key} must be a list")
        public_ports = [port for port in component["ports"] if port.get("direction") == public_direction]
        if canonical_json(list(public_ports)) != canonical_json(list(boundary)):
            raise ValueError(f"v2 compound {key!r} public port differs from body boundary port")
    body_nodes = {node.get("node_id"): node for node in body["nodes"] if isinstance(node, Mapping)}
    if len(body_nodes) != len(body["nodes"]):
        raise ValueError(f"v2 compound {key!r} body nodes must be closed declarations")
    for binding in bindings:
        public = parameters[binding["parameter_id"]]
        for target in binding["targets"]:
            node = body_nodes.get(target["node_id"])
            nested = node.get("component", {}) if node else {}
            target_component = components.get((nested.get("component_id"), nested.get("component_version")))
            target_parameters = target_component.get("parameters", {}) if target_component else {}
            if target["parameter_id"] not in target_parameters:
                raise ValueError(f"v2 compound {key!r} target names an unknown body parameter")
            if canonical_json(public) != canonical_json(target_parameters[target["parameter_id"]]):
                raise ValueError(f"v2 compound {key!r} parameter descriptor mismatch")
            if target["parameter_id"] in node.get("parameters", {}):
                raise ValueError(f"v2 compound {key!r} body literal collides with public parameter binding")


def _validate_v2_component_closure(components: Mapping[tuple[str, int], Mapping[str, Any]]) -> None:
    """Refuse absent and recursive compound references before evaluator use."""
    references: dict[tuple[str, int], set[tuple[str, int]]] = {}
    for key, component in components.items():
        compound = component.get("compound")
        if compound is None:
            continue
        refs = {
            (node["component"]["component_id"], node["component"]["component_version"])
            for node in compound["body"]["nodes"]
        }
        missing = sorted(refs - set(components))
        if missing:
            raise ValueError(f"v2 compound {key!r} component closure missing={missing}")
        references[key] = refs

    active: set[tuple[str, int]] = set()
    visited: set[tuple[str, int]] = set()

    def visit(key: tuple[str, int]) -> None:
        if key in active:
            raise ValueError(f"v2 compound component reference cycle includes {key!r}")
        if key in visited:
            return
        active.add(key)
        for child in sorted(references.get(key, ())):
            if child in references:
                visit(child)
        active.remove(key)
        visited.add(key)

    for key in sorted(references):
        visit(key)


class _FrozenDict(dict):
    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("registry values are immutable")

    __setitem__ = __delitem__ = __ior__ = clear = pop = popitem = setdefault = update = _immutable


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


__all__ = [
    "DependencyBoundary",
    "KernelRegistration",
    "PlatformRegistry",
    "registered_kernel",
]
