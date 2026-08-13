"""Fail-closed structural evidence for causal strategy admission.

Parity evaluation belongs to the next layer.  This module only proves that a
specific owner, graph, registry closure, wiring, mapping, and risk declaration
are complete enough to be presented to that evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd
from pandas.api.types import is_bool_dtype

from app.ir.causal import CausalDeclarationError, CausalContract, JSONValue
from app.ir.hashing import content_address
from app.ir.implementation_identity import (
    ImplementationUnidentified,
    implementation_address,
)
from app.ir.registry import DependencyBoundary, PlatformRegistry
from app.ir.resolve import ResolvedGraph, ResolutionError, resolve
from app.ir.schema import is_content_address
from app.ir.validate import validate
from app.strategy.ir_adapter import (
    InvalidRiskModel,
    UnmappableGraph,
    column_mapping,
    validate_risk_model,
)
from app.strategy.registry.base import CANONICAL_COLUMNS, Strategy


class AdmissionRefusalCode(str, Enum):
    IR_INVALID = "IR_INVALID"
    RESOLUTION_FAILED = "RESOLUTION_FAILED"
    CONTRACT_MISSING = "CONTRACT_MISSING"
    CONTRACT_INVALID = "CONTRACT_INVALID"
    COMPONENT_QUARANTINED = "COMPONENT_QUARANTINED"
    INPUT_UNDECLARED = "INPUT_UNDECLARED"
    CONTEXT_UNDECLARED = "CONTEXT_UNDECLARED"
    EXTERNAL_SERIES_UNRESOLVED = "EXTERNAL_SERIES_UNRESOLVED"
    IMPURE_KERNEL = "IMPURE_KERNEL"
    IMPLEMENTATION_UNIDENTIFIED = "IMPLEMENTATION_UNIDENTIFIED"
    IMPLEMENTATION_STALE = "IMPLEMENTATION_STALE"
    HISTORY_INVALID = "HISTORY_INVALID"
    OUTPUT_DELAY_INVALID = "OUTPUT_DELAY_INVALID"
    OUTPUT_MAPPING_INVALID = "OUTPUT_MAPPING_INVALID"
    STREAMING_DIVERGENCE = "STREAMING_DIVERGENCE"
    VECTOR_EVALUATION_FAILED = "VECTOR_EVALUATION_FAILED"
    REFERENCE_EVALUATION_FAILED = "REFERENCE_EVALUATION_FAILED"
    OWNER_SCOPE_INVALID = "OWNER_SCOPE_INVALID"
    ARTEFACT_MISMATCH = "ARTEFACT_MISMATCH"
    RECEIPT_STALE = "RECEIPT_STALE"


class AdmissionRefused(Exception):
    """A typed, stable refusal. Detail is diagnostic and never hashed."""

    def __init__(self, code: AdmissionRefusalCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}")


def _frozen_json(value: Any, *, label: str) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must contain finite JSON values")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValueError(f"{label} keys must be strings")
        return MappingProxyType({
            key: _frozen_json(value[key], label=label) for key in sorted(value)
        })  # type: ignore[return-value]
    if isinstance(value, (list, tuple)):
        return tuple(_frozen_json(item, label=label) for item in value)  # type: ignore[return-value]
    raise ValueError(f"{label} must contain only closed JSON values")


def _plain_json(value: Any) -> JSONValue:
    if isinstance(value, Mapping):
        return {key: _plain_json(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain_json(item) for item in value]
    return value


def _mapping(value: Mapping[str, Any], *, label: str) -> Mapping[str, JSONValue]:
    frozen = _frozen_json(value, label=label)
    assert isinstance(frozen, Mapping)
    return frozen


@dataclass(frozen=True)
class IRGraphAdmissionInput:
    graph: Mapping[str, JSONValue]
    parameters: Mapping[str, JSONValue]
    risk_model: Mapping[str, JSONValue] | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "graph", _mapping(self.graph, label="graph"))
        object.__setattr__(self, "parameters", _mapping(self.parameters, label="parameters"))
        if self.risk_model is not None:
            object.__setattr__(self, "risk_model", _mapping(
                self.risk_model, label="risk_model"))


@dataclass(frozen=True)
class HandwrittenAdapterInput:
    strategy_key: str
    strategy_version: str
    adapter_implementation: object
    adapter_dependencies: object
    equivalent_ir: IRGraphAdmissionInput


@dataclass(frozen=True)
class SourceEvidence:
    source: str
    strategy_key: str
    strategy_version: str
    adapter_implementation_address: str | None
    adapter_decision_address: str | None

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "adapter_decision_address": self.adapter_decision_address,
            "adapter_implementation_address": self.adapter_implementation_address,
            "source": self.source,
            "strategy_key": self.strategy_key,
            "strategy_version": self.strategy_version,
        }


@dataclass(frozen=True)
class ResolvedComponentIdentity:
    node_path: str
    identifier: str
    version: int
    body_ref: str
    bound_parameters: Mapping[str, JSONValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bound_parameters", _mapping(
            self.bound_parameters, label="bound_parameters"))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "body_ref": self.body_ref,
            "bound_parameters": _plain_json(self.bound_parameters),
            "identifier": self.identifier,
            "node_path": self.node_path,
            "version": self.version,
        }


@dataclass(frozen=True)
class InputProvenance:
    node_path: str
    socket: str
    root_market_inputs: tuple[str, ...]
    source_paths: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_market_inputs", tuple(self.root_market_inputs))
        object.__setattr__(self, "source_paths", tuple(
            tuple(path) for path in self.source_paths))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "node_path": self.node_path,
            "root_market_inputs": list(self.root_market_inputs),
            "socket": self.socket,
            "source_paths": [list(path) for path in self.source_paths],
        }


@dataclass(frozen=True)
class AdmittedKernelIdentity:
    body_ref: str
    implementation_address: str
    causal_contract: Mapping[str, JSONValue]
    evaluated_history_bars: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "causal_contract", _mapping(
            self.causal_contract, label="causal_contract"))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "body_ref": self.body_ref,
            "causal_contract": _plain_json(self.causal_contract),
            "evaluated_history_bars": self.evaluated_history_bars,
            "implementation_address": self.implementation_address,
        }


@dataclass(frozen=True)
class StructuralAdmission:
    owner_id: str
    source: str
    source_evidence: SourceEvidence
    graph_identifier: str
    graph_version: int
    graph_address: str
    resolved_components: tuple[ResolvedComponentIdentity, ...]
    input_provenance: tuple[InputProvenance, ...]
    bound_parameters: Mapping[str, JSONValue]
    kernels: tuple[AdmittedKernelIdentity, ...]
    canonical_mapping: Mapping[str, str]
    declared_warmup: int
    risk_model: Mapping[str, JSONValue] | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolved_components", tuple(self.resolved_components))
        object.__setattr__(self, "input_provenance", tuple(self.input_provenance))
        object.__setattr__(self, "kernels", tuple(self.kernels))
        object.__setattr__(self, "bound_parameters", _mapping(
            self.bound_parameters, label="bound_parameters"))
        object.__setattr__(self, "canonical_mapping", MappingProxyType(dict(
            sorted(self.canonical_mapping.items()))))
        if self.risk_model is not None:
            object.__setattr__(self, "risk_model", _mapping(
                self.risk_model, label="risk_model"))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "bound_parameters": _plain_json(self.bound_parameters),
            "canonical_mapping": dict(self.canonical_mapping),
            "declared_warmup": self.declared_warmup,
            "graph_address": self.graph_address,
            "graph_identifier": self.graph_identifier,
            "graph_version": self.graph_version,
            "input_provenance": [item.to_dict() for item in self.input_provenance],
            "kernels": [item.to_dict() for item in self.kernels],
            "owner_id": self.owner_id,
            "resolved_components": [
                item.to_dict() for item in self.resolved_components],
            "risk_model": _plain_json(self.risk_model),
            "source": self.source,
            "source_evidence": self.source_evidence.to_dict(),
        }


@dataclass(frozen=True)
class StructuralDecision:
    structural: StructuralAdmission | None
    refusal_code: AdmissionRefusalCode | None
    detail: str


@dataclass(frozen=True)
class ParityEvidence:
    fixture_suite_address: str
    reference_decision_address: str
    vector_decision_address: str

    def __post_init__(self) -> None:
        for name in ("fixture_suite_address", "reference_decision_address",
                     "vector_decision_address"):
            if not is_content_address(getattr(self, name)):
                raise ValueError(f"{name} must be a canonical content address")


@dataclass(frozen=True)
class AdmittedStrategyArtifact:
    owner_id: str
    source: str
    source_evidence: SourceEvidence
    graph_identifier: str
    graph_version: int
    graph_address: str
    resolved_components: tuple[ResolvedComponentIdentity, ...]
    input_provenance: tuple[InputProvenance, ...]
    bound_parameters: Mapping[str, JSONValue]
    kernels: tuple[AdmittedKernelIdentity, ...]
    canonical_mapping: Mapping[str, str]
    declared_warmup: int
    risk_model: Mapping[str, JSONValue] | None
    fixture_suite_address: str
    reference_decision_address: str
    vector_decision_address: str
    scheme: str = "strategy-admission/1"
    contract_suite: str = "causal-contract/1"
    parity_suite: str = "prefix-vector-parity/1"

    def __post_init__(self) -> None:
        for name in ("graph_address", "fixture_suite_address",
                     "reference_decision_address", "vector_decision_address"):
            if not is_content_address(getattr(self, name)):
                raise ValueError(f"{name} must be a canonical content address")
        if self.reference_decision_address != self.vector_decision_address:
            raise AdmissionRefused(
                AdmissionRefusalCode.STREAMING_DIVERGENCE,
                "canonical decision addresses differ",
            )
        object.__setattr__(self, "resolved_components", tuple(self.resolved_components))
        object.__setattr__(self, "input_provenance", tuple(self.input_provenance))
        object.__setattr__(self, "kernels", tuple(self.kernels))
        object.__setattr__(self, "bound_parameters", _mapping(
            self.bound_parameters, label="bound_parameters"))
        object.__setattr__(self, "canonical_mapping", MappingProxyType(dict(
            sorted(self.canonical_mapping.items()))))
        if self.risk_model is not None:
            object.__setattr__(self, "risk_model", _mapping(
                self.risk_model, label="risk_model"))

    @classmethod
    def from_evidence(cls, structural: StructuralAdmission,
                      parity: ParityEvidence) -> "AdmittedStrategyArtifact":
        return cls(
            **{name: getattr(structural, name) for name in (
                "owner_id", "source", "source_evidence", "graph_identifier",
                "graph_version", "graph_address", "resolved_components",
                "input_provenance", "bound_parameters", "kernels",
                "canonical_mapping", "declared_warmup", "risk_model")},
            fixture_suite_address=parity.fixture_suite_address,
            reference_decision_address=parity.reference_decision_address,
            vector_decision_address=parity.vector_decision_address,
        )

    def to_dict(self) -> dict[str, JSONValue]:
        structural = StructuralAdmission(
            **{name: getattr(self, name) for name in (
                "owner_id", "source", "source_evidence", "graph_identifier",
                "graph_version", "graph_address", "resolved_components",
                "input_provenance", "bound_parameters", "kernels",
                "canonical_mapping", "declared_warmup", "risk_model")})
        return {
            **structural.to_dict(),
            "contract_suite": self.contract_suite,
            "fixture_suite_address": self.fixture_suite_address,
            "parity_suite": self.parity_suite,
            "reference_decision_address": self.reference_decision_address,
            "scheme": self.scheme,
            "vector_decision_address": self.vector_decision_address,
        }

    @property
    def admission_address(self) -> str:
        return content_address(self.to_dict())


def admitted_artifact(structural: StructuralAdmission,
                      parity: ParityEvidence) -> AdmittedStrategyArtifact:
    """The explicit Task 4 hand-off; structural evidence alone has no address."""
    if parity.reference_decision_address != parity.vector_decision_address:
        raise AdmissionRefused(
            AdmissionRefusalCode.STREAMING_DIVERGENCE,
            "canonical decision addresses differ",
        )
    return AdmittedStrategyArtifact.from_evidence(structural, parity)


def canonical_decisions(frame: pd.DataFrame) -> bytes:
    """Encode exact timestamped decisions for byte-level parity comparison."""
    missing = [name for name in CANONICAL_COLUMNS if name not in frame.columns]
    if missing:
        raise AdmissionRefused(
            AdmissionRefusalCode.OUTPUT_MAPPING_INVALID,
            f"canonical decision frame is missing {missing}",
        )
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise AdmissionRefused(
            AdmissionRefusalCode.ARTEFACT_MISMATCH,
            "canonical decisions require a timezone-aware DatetimeIndex",
        )
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise AdmissionRefused(
            AdmissionRefusalCode.ARTEFACT_MISMATCH,
            "canonical decision timestamps must be monotonic and unique",
        )
    for column in CANONICAL_COLUMNS:
        if not is_bool_dtype(frame[column].dtype) or frame[column].isna().any():
            raise AdmissionRefused(
                AdmissionRefusalCode.ARTEFACT_MISMATCH,
                f"canonical decision {column} must contain exact booleans",
            )
    rows: list[list[JSONValue]] = []
    utc_nanos = frame.index.tz_convert("UTC").as_unit("ns").asi8
    for position, timestamp in enumerate(utc_nanos):
        row: list[JSONValue] = [int(timestamp)]
        for column in CANONICAL_COLUMNS:
            value = frame[column].iloc[position]
            row.append(bool(value))
        rows.append(row)
    from app.ir.hashing import canonical_json
    return canonical_json(rows).encode("utf-8")


def _refusal(code: AdmissionRefusalCode, detail: str) -> StructuralDecision:
    return StructuralDecision(None, code, detail)


def _input_socket_names(component: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []

    def visit(items: Any) -> None:
        for item in items or ():
            if not isinstance(item, Mapping):
                continue
            if item.get("item") == "panel":
                visit(item.get("items"))
            elif item.get("item") == "socket" and item.get("direction") == "input":
                names.append(str(item.get("identifier")))

    visit(component.get("interface"))
    return tuple(names)


def _contract_dict(contract: CausalContract) -> Mapping[str, JSONValue]:
    return {
        "context_inputs": list(contract.context_inputs),
        "history": {
            "constant": contract.history.constant,
            "mode": contract.history.mode,
            "terms": [
                {"multiplier": term.multiplier, "parameter": term.parameter}
                for term in contract.history.terms
            ],
        },
        "input_bar": contract.input_bar,
        "node_input_sockets": list(contract.node_input_sockets),
        "output_delay_bars": contract.output_delay_bars,
        "purity": contract.purity,
        "recursive_state": contract.recursive_state is not None,
    }


def _boundary_markers(node_path: str) -> tuple[str, ...]:
    parts = node_path.split("/")
    return tuple(f"{'/'.join(parts[:end])}.input" for end in range(1, len(parts)))


def derive_input_provenance(graph: ResolvedGraph) -> tuple[InputProvenance, ...]:
    """Derive root sources from resolved wiring; no caller evidence is accepted."""
    targets: dict[tuple[str, str], list[tuple[tuple[str, ...], tuple[str, ...]]]] = {}
    for root, consumers in graph.inputs.items():
        for node_path, socket in consumers:
            path = (f"$input.{root}", *_boundary_markers(node_path),
                    f"{node_path}.{socket}")
            targets.setdefault((node_path, socket), []).append(((root,), path))

    incoming: dict[tuple[str, str], tuple[str, str]] = {}
    for edge in graph.edges:
        key = edge.target
        if key in incoming:
            raise AdmissionRefused(
                AdmissionRefusalCode.ARTEFACT_MISMATCH,
                f"input {key[0]}.{key[1]} has multiple sources",
            )
        incoming[key] = edge.source

    nodes = {node.instance_id: node for node in graph.nodes}
    memo: dict[tuple[str, str], tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = {}
    visiting: set[tuple[str, str]] = set()

    def trace(target: tuple[str, str]):
        if target in memo:
            return memo[target]
        if target in visiting:
            raise AdmissionRefused(
                AdmissionRefusalCode.ARTEFACT_MISMATCH,
                f"provenance cycle reaches {target[0]}.{target[1]}",
            )
        visiting.add(target)
        direct = targets.get(target)
        if direct:
            roots = tuple(sorted({root for item in direct for root in item[0]}))
            paths = tuple(sorted({item[1] for item in direct}))
        elif target in incoming:
            source = incoming[target]
            source_node = nodes.get(source[0])
            if source_node is None:
                raise AdmissionRefused(
                    AdmissionRefusalCode.EXTERNAL_SERIES_UNRESOLVED,
                    f"source {source[0]}.{source[1]} is not a resolved node",
                )
            source_contract = source_node.causal
            source_sockets = source_contract.node_input_sockets if source_contract else ()
            upstream = [trace((source_node.instance_id, socket))
                        for socket in source_sockets]
            roots = tuple(sorted({root for item in upstream for root in item[0]}))
            if upstream:
                paths = tuple(sorted({
                    (*path, f"{source[0]}.{source[1]}", f"{target[0]}.{target[1]}")
                    for item in upstream for path in item[1]
                }))
            else:
                # A closed zero-input scalar/value kernel has no market roots, but
                # its actual resolved source path still enters the receipt.
                paths = ((f"{source[0]}.{source[1]}",
                          f"{target[0]}.{target[1]}"),)
        else:
            roots, paths = (), ()
        visiting.remove(target)
        memo[target] = roots, paths
        return memo[target]

    evidence = []
    for node in graph.nodes:
        contract = node.causal
        if contract is None:
            continue
        for socket in contract.node_input_sockets:
            roots, paths = trace((node.instance_id, socket))
            if not paths:
                # Scalar inputs must still be explicitly wired in IR v1. Parameters are
                # bound separately and therefore never appear in node_input_sockets.
                raise AdmissionRefused(
                    AdmissionRefusalCode.EXTERNAL_SERIES_UNRESOLVED,
                    f"input {node.instance_id}.{socket} has no resolved source",
                )
            evidence.append(InputProvenance(
                node.instance_id, socket, roots, paths))
    return tuple(sorted(evidence, key=lambda item: (item.node_path, item.socket)))


def _inspect_ir(*, owner_id: str, source_input: IRGraphAdmissionInput,
                registry: PlatformRegistry, source: str,
                source_evidence: SourceEvidence) -> StructuralAdmission:
    graph_data = _plain_json(source_input.graph)
    parameters = _plain_json(source_input.parameters)
    assert isinstance(graph_data, Mapping) and isinstance(parameters, Mapping)
    violations = validate(graph_data, registry.library.components)
    if violations:
        raise AdmissionRefused(
            AdmissionRefusalCode.IR_INVALID,
            "; ".join(str(item) for item in violations),
        )
    _validate_reached_bodies(graph_data, registry)
    try:
        resolved = resolve(graph_data, registry.library, parameters)
    except ResolutionError as exc:
        raise AdmissionRefused(AdmissionRefusalCode.RESOLUTION_FAILED, str(exc)) from exc

    components: list[ResolvedComponentIdentity] = []
    kernels: list[tuple[str, AdmittedKernelIdentity]] = []
    actual_addresses: dict[str, str] = {}
    wired = {(edge.target[0], edge.target[1]) for edge in resolved.edges}
    wired |= {(node, socket) for consumers in resolved.inputs.values()
              for node, socket in consumers}
    for node in resolved.nodes:
        registration = registry.registrations.get(node.body_ref)
        if registration is None:
            raise AdmissionRefused(
                AdmissionRefusalCode.IMPLEMENTATION_UNIDENTIFIED,
                f"node {node.instance_id} has no complete registration",
            )
        contract = node.causal
        if contract is None:
            raise AdmissionRefused(
                AdmissionRefusalCode.CONTRACT_MISSING,
                f"node {node.instance_id} has no causal contract",
            )
        component = registry.library.components.get(node.definition)
        if component is None:
            raise AdmissionRefused(
                AdmissionRefusalCode.ARTEFACT_MISMATCH,
                f"node {node.instance_id} definition is absent",
            )
        declared = _input_socket_names(component)
        causal_sockets = contract.node_input_sockets
        missing = tuple(socket for socket in declared if socket not in causal_sockets)
        extra = tuple(socket for socket in causal_sockets if socket not in declared)
        if missing:
            raise AdmissionRefused(
                AdmissionRefusalCode.INPUT_UNDECLARED,
                f"node {node.instance_id} contract omits sockets {list(missing)}",
            )
        if extra:
            raise AdmissionRefused(
                AdmissionRefusalCode.CONTRACT_INVALID,
                f"node {node.instance_id} contract adds sockets {list(extra)}",
            )
        unwired = tuple(socket for socket in declared
                        if (node.instance_id, socket) not in wired)
        if unwired:
            raise AdmissionRefused(
                AdmissionRefusalCode.EXTERNAL_SERIES_UNRESOLVED,
                f"node {node.instance_id} sockets have no source: {list(unwired)}",
            )
        if set(causal_sockets) & set(contract.context_inputs):
            raise AdmissionRefused(
                AdmissionRefusalCode.CONTEXT_UNDECLARED,
                f"node {node.instance_id} uses context as a node socket",
            )
        if node.purity != "pure" or contract.purity != "pure":
            raise AdmissionRefused(
                AdmissionRefusalCode.IMPURE_KERNEL,
                f"node {node.instance_id} is not pure",
            )
        if contract.input_bar != "completed":
            raise AdmissionRefused(
                AdmissionRefusalCode.CONTRACT_INVALID,
                f"node {node.instance_id} does not consume completed bars",
            )
        if isinstance(contract.output_delay_bars, bool) \
                or not isinstance(contract.output_delay_bars, int) \
                or contract.output_delay_bars < 0:
            raise AdmissionRefused(
                AdmissionRefusalCode.OUTPUT_DELAY_INVALID,
                f"node {node.instance_id} has invalid output delay",
            )
        try:
            history = contract.history.bars(node.params)
        except CausalDeclarationError as exc:
            raise AdmissionRefused(
                AdmissionRefusalCode.HISTORY_INVALID,
                f"node {node.instance_id}: {exc}",
            ) from exc
        actual = actual_addresses.get(node.body_ref)
        if actual is None:
            try:
                actual = implementation_address(
                    registration.implementation,
                    registration.dependency_boundary,
                    recursive_state=contract.recursive_state,
                )
            except ImplementationUnidentified as exc:
                raise AdmissionRefused(
                    AdmissionRefusalCode.IMPLEMENTATION_UNIDENTIFIED,
                    f"node {node.instance_id}: {exc}",
                ) from exc
            actual_addresses[node.body_ref] = actual
        if actual != registration.implementation_address:
            raise AdmissionRefused(
                AdmissionRefusalCode.IMPLEMENTATION_STALE,
                f"node {node.instance_id} registration is stale",
            )
        kernels.append((node.instance_id, AdmittedKernelIdentity(
            node.body_ref, actual, _contract_dict(contract), history)))

    try:
        mapping = column_mapping(tuple(resolved.outputs))
    except UnmappableGraph as exc:
        raise AdmissionRefused(AdmissionRefusalCode.OUTPUT_MAPPING_INVALID, str(exc)) from exc
    try:
        risk = validate_risk_model(
            _plain_json(source_input.risk_model), f"ir.{resolved.identifier}")
    except InvalidRiskModel as exc:
        raise AdmissionRefused(AdmissionRefusalCode.ARTEFACT_MISMATCH, str(exc)) from exc
    provenance = derive_input_provenance(resolved)
    components = [ResolvedComponentIdentity(
        item.node_path, item.definition[0], item.definition[1],
        item.body_ref, item.params) for item in resolved.components]
    return StructuralAdmission(
        owner_id=owner_id,
        source=source,
        source_evidence=source_evidence,
        graph_identifier=resolved.identifier,
        graph_version=resolved.version,
        graph_address=content_address(graph_data),
        resolved_components=tuple(sorted(
            components, key=lambda item: item.node_path)),
        input_provenance=provenance,
        bound_parameters=parameters,
        kernels=tuple(identity for _, identity in sorted(kernels)),
        canonical_mapping=mapping,
        declared_warmup=resolved.warmup,
        risk_model=risk,
    )


def _validate_reached_bodies(graph: Mapping[str, Any],
                             registry: PlatformRegistry) -> None:
    """Validate each reached graph body against its published component seam."""
    visited: set[str] = set()

    def visit(candidate: Mapping[str, Any]) -> None:
        for node in candidate.get("nodes", ()):
            if not isinstance(node, Mapping):
                continue
            ref = node.get("component")
            if not isinstance(ref, Mapping):
                continue
            component = registry.library.components.get(
                (ref.get("identifier"), ref.get("version")))
            if component is None:
                continue
            body = component.get("body")
            if not isinstance(body, Mapping) or body.get("body") != "graph":
                continue
            body_ref = body.get("ref")
            if not isinstance(body_ref, str) or body_ref in visited:
                continue
            visited.add(body_ref)
            nested = registry.library.bodies.get(body_ref)
            if nested is None:
                raise AdmissionRefused(
                    AdmissionRefusalCode.RESOLUTION_FAILED,
                    f"reached graph body {body_ref!r} is absent",
                )
            plain_nested = _plain_json(nested)
            assert isinstance(plain_nested, Mapping)
            nested_violations = validate(plain_nested, registry.library.components)
            if nested_violations:
                raise AdmissionRefused(
                    AdmissionRefusalCode.IR_INVALID,
                    f"nested body {body_ref}: "
                    + "; ".join(str(item) for item in nested_violations),
                )
            published_interface = _plain_json(component.get("interface", ()))
            if plain_nested.get("interface") != published_interface:
                raise AdmissionRefused(
                    AdmissionRefusalCode.IR_INVALID,
                    f"nested body {body_ref} interface differs from its published component",
                )
            visit(plain_nested)

    visit(graph)


def inspect_strategy(*, owner_id: str,
                     source_input: IRGraphAdmissionInput | HandwrittenAdapterInput,
                     registry: PlatformRegistry) -> StructuralDecision:
    """Inspect exact structural evidence. This function never evaluates parity."""
    if not isinstance(owner_id, str) or not owner_id.strip():
        return _refusal(AdmissionRefusalCode.OWNER_SCOPE_INVALID,
                        "owner_id must be a non-empty string")
    if not isinstance(registry, PlatformRegistry):
        return _refusal(AdmissionRefusalCode.ARTEFACT_MISMATCH,
                        "admission requires the platform registry transport")
    try:
        if isinstance(source_input, IRGraphAdmissionInput):
            graph = source_input.graph
            evidence = SourceEvidence(
                "ir_graph", str(graph.get("identifier", "")),
                str(graph.get("version", "")), None, None)
            structural = _inspect_ir(
                owner_id=owner_id, source_input=source_input, registry=registry,
                source="ir_graph", source_evidence=evidence)
        elif isinstance(source_input, HandwrittenAdapterInput):
            if not source_input.strategy_key or not source_input.strategy_version:
                raise AdmissionRefused(
                    AdmissionRefusalCode.ARTEFACT_MISMATCH,
                    "handwritten adapter requires an exact key and version",
                )
            if not isinstance(source_input.adapter_dependencies, DependencyBoundary):
                raise AdmissionRefused(
                    AdmissionRefusalCode.IMPLEMENTATION_UNIDENTIFIED,
                    "handwritten adapter requires a closed dependency boundary",
                )
            try:
                adapter_address = implementation_address(
                    source_input.adapter_implementation,
                    source_input.adapter_dependencies)
            except ImplementationUnidentified as exc:
                raise AdmissionRefused(
                    AdmissionRefusalCode.IMPLEMENTATION_UNIDENTIFIED, str(exc)) from exc
            adapter_type = source_input.adapter_implementation
            if isinstance(adapter_type, type) and issubclass(adapter_type, Strategy):
                adapter = adapter_type()
            elif isinstance(adapter_type, Strategy):
                adapter = adapter_type
            else:
                raise AdmissionRefused(
                    AdmissionRefusalCode.ARTEFACT_MISMATCH,
                    "handwritten adapter must be an exact Strategy implementation",
                )
            if adapter.key != source_input.strategy_key \
                    or adapter.version != source_input.strategy_version:
                raise AdmissionRefused(
                    AdmissionRefusalCode.ARTEFACT_MISMATCH,
                    "handwritten adapter key/version differs from its executable identity",
                )
            evidence = SourceEvidence(
                "handwritten_adapter", source_input.strategy_key,
                source_input.strategy_version, adapter_address, None)
            structural = _inspect_ir(
                owner_id=owner_id, source_input=source_input.equivalent_ir,
                registry=registry, source="handwritten_adapter",
                source_evidence=evidence)
        else:
            raise AdmissionRefused(
                AdmissionRefusalCode.ARTEFACT_MISMATCH,
                "unsupported admission input",
            )
        return StructuralDecision(structural, None, "")
    except AdmissionRefused as exc:
        return _refusal(exc.code, exc.detail)
    except (TypeError, ValueError) as exc:
        return _refusal(AdmissionRefusalCode.CONTRACT_INVALID, str(exc))


__all__ = [
    "AdmittedKernelIdentity", "AdmittedStrategyArtifact", "AdmissionRefusalCode",
    "AdmissionRefused", "HandwrittenAdapterInput", "IRGraphAdmissionInput",
    "InputProvenance", "ParityEvidence", "ResolvedComponentIdentity",
    "SourceEvidence", "StructuralAdmission", "StructuralDecision",
    "admitted_artifact", "canonical_decisions", "derive_input_provenance",
    "inspect_strategy",
]
