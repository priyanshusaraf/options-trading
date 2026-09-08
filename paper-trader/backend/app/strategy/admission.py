"""Fail-closed structural evidence for causal strategy admission.

Parity evaluation belongs to the next layer.  This module only proves that a
specific owner, graph, registry closure, wiring, mapping, and risk declaration
are complete enough to be presented to that evaluator.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from dataclasses import InitVar, dataclass
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
from app.ir.formats.v2 import canonical_document, content_address_for, graph_address_for
from app.ir.first_party.analytical_v2.contracts import ContractInputBindings
from app.ir.resolve import (
    ResolvedGraph, ResolvedV2Graph, ResolutionError, resolve, resolve_v2,
)
from app.ir.v2_graph_versions import (
    PersistedPhase4Artifact,
    PHASE4_SCHEME,
    V2GraphFacts,
    V2GraphVerificationError,
)
from app.ir.schema import is_content_address
from app.ir.validate import validate
from app.market_data.capability import (
    CapabilityAssessment,
    CapabilityRefusal,
    _require_canonical_assessment,
    verify_assessment_coverage,
)
from app.market_data.requirements import DataRequirementPlan, compile_data_requirement_plan
from app.strategy.ir_adapter import (
    InvalidRiskModel,
    UnmappableGraph,
    column_mapping,
    validate_risk_model,
)
from app.strategy.registry.base import CANONICAL_COLUMNS, Strategy


VERIFIED_GRAPH = "VERIFIED_GRAPH"
NON_GRAPH = "NON_GRAPH"
LEGACY_UNVERIFIED = "LEGACY_UNVERIFIED"
ATTRIBUTION_STATES = (VERIFIED_GRAPH, NON_GRAPH, LEGACY_UNVERIFIED)
GRAPH_ATTRIBUTION_UNVERIFIED = "GRAPH_ATTRIBUTION_UNVERIFIED"
GRAPH_ATTRIBUTION_MISMATCH = "GRAPH_ATTRIBUTION_MISMATCH"


class GraphAttributionRefused(ValueError):
    """Stable pre-effect refusal for an incomplete or conflicting source tuple."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def require_attribution_tuple(*, strategy_key: str | None,
                              strategy_version: str | None,
                              graph_address: str | None,
                              admission_address: str | None,
                              attribution_state: str | None,
                              allow_legacy: bool = False) -> None:
    """Validate source/state coherence without inferring authority from value shape."""
    if attribution_state not in ATTRIBUTION_STATES:
        raise GraphAttributionRefused(GRAPH_ATTRIBUTION_UNVERIFIED)
    graph_source = isinstance(strategy_key, str) and strategy_key.startswith("ir.")
    if attribution_state == VERIFIED_GRAPH:
        if (not graph_source or not isinstance(strategy_version, str)
                or not strategy_version.isdecimal()
                or strategy_version.startswith("0")
                or not is_content_address(graph_address)
                or not is_content_address(admission_address)):
            raise GraphAttributionRefused(GRAPH_ATTRIBUTION_UNVERIFIED)
        return
    if attribution_state == NON_GRAPH:
        if graph_source or graph_address is not None:
            raise GraphAttributionRefused(GRAPH_ATTRIBUTION_MISMATCH)
        return
    if not allow_legacy or graph_address is not None:
        raise GraphAttributionRefused(GRAPH_ATTRIBUTION_UNVERIFIED)


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
class AdmissionDecision:
    artifact: "AdmittedStrategyArtifact | None"
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
class V2AdmissionEvidence:
    """Externally produced evidence identities required by an IR-v2 receipt.

    The values are identities only.  This admission layer does not evaluate a
    v2 graph, manufacture legacy evidence, or turn the receipt into execution
    permission.
    """
    input_address: str
    dataset_address: str
    fee_address: str
    slippage_address: str
    risk_address: str
    parity_address: str
    causal_evidence_address: str

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if not is_content_address(getattr(self, name)):
                raise ValueError(f"{name} must be a canonical content address")

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class V2AdmittedStrategyArtifact:
    """Immutable receipt for one resolved Closed Component IR v2 document."""
    owner_id: str
    graph_identifier: str
    graph_version: int
    document: Mapping[str, Any]
    registry_snapshot: Mapping[str, JSONValue]
    resolved_topology: Mapping[str, JSONValue]
    evidence: V2AdmissionEvidence
    scheme: str = "strategy-admission/2"
    contract_suite: str = "closed-component-ir/2"
    parity_suite: str = "prefix-vector-parity/1"

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id:
            raise ValueError("owner_id must be non-empty")
        if not isinstance(self.graph_identifier, str) or not self.graph_identifier:
            raise ValueError("graph_identifier must be non-empty")
        if isinstance(self.graph_version, bool) or not isinstance(self.graph_version, int) or self.graph_version < 1:
            raise ValueError("graph_version must be >= 1")
        object.__setattr__(self, "document", _mapping(self.document, label="v2_document"))
        object.__setattr__(self, "registry_snapshot", _mapping(self.registry_snapshot, label="registry_snapshot"))
        object.__setattr__(self, "resolved_topology", _mapping(self.resolved_topology, label="resolved_topology"))

    @property
    def content_address(self) -> str:
        return content_address(_plain_json(self.document))

    @property
    def graph_address(self) -> str:
        return content_address({"identity_scheme_version": 1, "graph": {
            key: _plain_json(self.document)[key]
            for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")
        }})

    @property
    def format_version(self) -> int:
        return 2

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "content_address": self.content_address,
            "contract_suite": self.contract_suite,
            "document": _plain_json(self.document),
            "evidence": self.evidence.to_dict(),
            "format_version": 2,
            "graph_address": self.graph_address,
            "graph_identifier": self.graph_identifier,
            "graph_version": self.graph_version,
            "owner_id": self.owner_id,
            "parity_suite": self.parity_suite,
            "registry_snapshot": _plain_json(self.registry_snapshot),
            "resolved_topology": _plain_json(self.resolved_topology),
            "scheme": self.scheme,
        }

    @property
    def admission_address(self) -> str:
        return content_address(self.to_dict())


def _v2_registry_snapshot(registry: PlatformRegistry, *, uses_phase4_declarations: bool = False) -> Mapping[str, JSONValue]:
    if uses_phase4_declarations:
        payload = _plain_json(registry.registry_snapshot_payload)
        address = registry.registry_snapshot_address
        if content_address(payload) != address:
            raise AdmissionRefused(AdmissionRefusalCode.ARTEFACT_MISMATCH,
                                   "opted-in registry snapshot is stale or forged")
        return {"address": address, "snapshot": payload}
    types = [_plain_json(value) for _, value in sorted(registry.v2_types.items())]
    components = [_plain_json(value) for _, value in sorted(registry.v2_components.items())]
    identities = [
        {"component_id": key[0], "component_version": key[1], "implementation_address": address}
        for key, address in sorted(registry.v2_implementation_identities.items())
    ]
    if registry.v2_components and not identities:
        raise AdmissionRefused(
            AdmissionRefusalCode.IR_INVALID,
            "v2 registry has no executable implementation identity closure",
        )
    snapshot = {"components": components, "implementation_identities": identities, "types": types}
    return {"address": content_address(snapshot), "snapshot": snapshot}


def _v2_topology(resolved: ResolvedV2Graph) -> Mapping[str, JSONValue]:
    return {
        "bundles": [{"assembly": bundle.assembly, "default": _plain_json(bundle.default),
                     "default_provenance": bundle.default_provenance,
                     "members": [{"binding": _plain_json(member.binding), "edge_id": member.edge_id,
                                  "provenance": _plain_json(member.provenance), "source": _plain_json(member.source),
                                  "type_ref": _plain_json(member.type_ref)} for member in bundle.members],
                     "target": _plain_json(bundle.target)}
                    for _, bundle in sorted(resolved.bundles.items())],
        "graph_inputs": _plain_json(resolved.graph_inputs),
        "nodes": [{"component": {"component_id": node.component[0], "component_version": node.component[1]},
                   "node_id": node.node_id, "parameter_provenance": _plain_json(node.parameter_provenance),
                   "parameters": _plain_json(node.parameters)} for node in resolved.nodes],
        "outputs": {name: {"binding": _plain_json(member.binding), "edge_id": member.edge_id,
                            "provenance": _plain_json(member.provenance), "source": _plain_json(member.source),
                            "type_ref": _plain_json(member.type_ref)} for name, member in resolved.outputs.items()},
    }


def _admit_v2_strategy_and_resolved(
    *, owner_id: str, document: Mapping[str, Any], registry: PlatformRegistry,
    evidence: V2AdmissionEvidence,
) -> tuple[V2AdmittedStrategyArtifact, ResolvedV2Graph]:
    """Build one V2 receipt and return its exact already-resolved graph."""
    try:
        canonical = canonical_document(document, registry)
        content = content_address_for(canonical, registry)
        graph = graph_address_for(canonical, registry)
        resolved = resolve_v2(canonical, registry)
        topology = _v2_topology(resolved)
        # Preserve the legacy receipt for graphs which do not consume a Phase 4
        # declaration, even when the registry also contains unrelated ones.
        uses_phase4_declarations = any(node.declaration_address is not None for node in resolved.nodes)
    except (ValueError, ResolutionError) as exc:
        raise AdmissionRefused(AdmissionRefusalCode.IR_INVALID, "v2 document cannot be admitted") from exc
    if content != content_address(canonical) or graph != content_address({"identity_scheme_version": 1, "graph": {
            key: canonical[key] for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}}):
        raise AdmissionRefused(AdmissionRefusalCode.ARTEFACT_MISMATCH, "v2 canonical identity mismatch")
    artifact = V2AdmittedStrategyArtifact(
        owner_id, canonical["strategy_id"], canonical["strategy_version"],
        canonical,
        _v2_registry_snapshot(
            registry, uses_phase4_declarations=uses_phase4_declarations
        ),
        topology, evidence,
    )
    return artifact, resolved


def admit_v2_strategy(*, owner_id: str, document: Mapping[str, Any], registry: PlatformRegistry,
                      evidence: V2AdmissionEvidence) -> V2AdmittedStrategyArtifact:
    """Create a v2 evidence receipt from only canonical document and resolver facts."""
    artifact, _resolved = _admit_v2_strategy_and_resolved(
        owner_id=owner_id, document=document, registry=registry, evidence=evidence
    )
    return artifact


_PHASE4_CONSTRUCTION_TOKEN = object()

_PHASE4_REGISTRY_SNAPSHOT_KEYS = frozenset({
    "v1_components", "v1_bodies", "v1_implementations", "v2_types",
    "v2_components", "v2_implementations", "data_requirement_declarations",
})
_PHASE4_CONTRACT_REGISTRY_SNAPSHOT_KEYS = frozenset({
    *_PHASE4_REGISTRY_SNAPSHOT_KEYS, "node_contracts", "contract_bindings",
})


def is_closed_phase4_registry_snapshot(
    snapshot: Any, *, expected_address: Any,
) -> bool:
    """Recognize only the two immutable Phase 4 registry snapshot shapes."""
    if (
        not isinstance(snapshot, Mapping)
        or set(snapshot) != {"address", "snapshot"}
        or not is_content_address(expected_address)
        or snapshot.get("address") != expected_address
    ):
        return False
    payload = snapshot.get("snapshot")
    if not isinstance(payload, Mapping) or set(payload) not in {
        _PHASE4_REGISTRY_SNAPSHOT_KEYS,
        _PHASE4_CONTRACT_REGISTRY_SNAPSHOT_KEYS,
    }:
        return False
    if not isinstance(payload["data_requirement_declarations"], list):
        return False
    if (
        set(payload) == _PHASE4_CONTRACT_REGISTRY_SNAPSHOT_KEYS
        and any(not isinstance(payload[key], list) for key in (
            "node_contracts", "contract_bindings"
        ))
    ):
        return False
    return (
        bool(payload["data_requirement_declarations"])
        and content_address(_plain_json(payload)) == expected_address
    )

@dataclass(frozen=True)
class Phase4V2AdmittedStrategyArtifact:
    """An immutable data-capability binding around an untouched V2 receipt."""
    base_v2_admission: V2AdmittedStrategyArtifact
    phase4_data_binding: Mapping[str, JSONValue]
    assessment: CapabilityAssessment
    _construction_token: InitVar[object | None] = None
    scheme: str = "strategy-admission/phase4-data/1"
    contract_suite: str = "closed-component-ir/2"
    parity_suite: str = "prefix-vector-parity/1"

    def __post_init__(self, _construction_token: object | None) -> None:
        if _construction_token is not _PHASE4_CONSTRUCTION_TOKEN:
            raise ValueError("Phase 4 wrappers may only be constructed by the admission seam")
        base = self.base_v2_admission
        if content_address(base.to_dict()) != base.admission_address:
            raise ValueError("base V2 receipt address is stale")
        binding = _mapping(self.phase4_data_binding, label="phase4_data_binding")
        expected = {"owner_id", "mode", "authored_ir_address", "registry_snapshot_address", "resolved_graph_address", "implementation_closure_address", "declaration_addresses", "plan_address", "capability_assessment_address", "dataset_manifest_address", "market_truth_snapshot_address", "evaluation_policy_address"}
        if set(binding) != expected or binding["owner_id"] != base.owner_id or binding["authored_ir_address"] != base.content_address or binding["mode"] not in {"RESEARCH", "PAPER", "LIVE"}:
            raise ValueError("Phase 4 binding is malformed or does not match base receipt")
        addresses = expected - {"owner_id", "mode", "declaration_addresses"}
        if any(not is_content_address(binding[key]) for key in addresses):
            raise ValueError("Phase 4 binding has invalid addresses")
        declarations = binding["declaration_addresses"]
        if not isinstance(declarations, tuple) or tuple(sorted(declarations)) != declarations or len(set(declarations)) != len(declarations) or any(not is_content_address(value) for value in declarations):
            raise ValueError("Phase 4 declaration addresses are malformed")
        snapshot = base.registry_snapshot
        if snapshot.get("address") != binding["registry_snapshot_address"] or content_address(_plain_json(snapshot.get("snapshot"))) != binding["registry_snapshot_address"]:
            raise ValueError("base receipt does not embed the full bound registry snapshot")
        assessment = self.assessment
        if not isinstance(assessment, CapabilityAssessment):
            raise ValueError("Phase 4 assessment has an invalid type")
        _require_canonical_assessment(assessment)
        if (assessment.owner_id != binding["owner_id"] or assessment.mode != binding["mode"] or assessment.plan_address != binding["plan_address"] or assessment.registry_snapshot_address != binding["registry_snapshot_address"] or assessment.authority_address != binding["capability_assessment_address"] or assessment.dataset_manifest_address != binding["dataset_manifest_address"] or assessment.market_truth_snapshot_address != binding["market_truth_snapshot_address"] or assessment.evaluation_policy_address != binding["evaluation_policy_address"] or any(row["result"] != "SATISFIED" for row in assessment.requirement_results)):
            raise ValueError("Phase 4 binding does not match validated assessment")
        object.__setattr__(self, "phase4_data_binding", binding)

    @property
    def owner_id(self) -> str: return self.base_v2_admission.owner_id
    @property
    def graph_identifier(self) -> str: return self.base_v2_admission.graph_identifier
    @property
    def graph_version(self) -> int: return self.base_v2_admission.graph_version
    @property
    def graph_address(self) -> str: return self.base_v2_admission.graph_address
    @property
    def content_address(self) -> str: return self.base_v2_admission.content_address
    @property
    def format_version(self) -> int: return 2
    @property
    def admission_address(self) -> str: return content_address(self.to_dict())

    def to_dict(self) -> dict[str, JSONValue]:
        from app.market_data.capability import capability_assessment_authority_envelope

        return {"scheme": self.scheme, "contract_suite": self.contract_suite, "parity_suite": self.parity_suite, "format_version": 2, "owner_id": self.owner_id, "graph_identifier": self.graph_identifier, "graph_version": self.graph_version, "graph_address": self.graph_address, "content_address": self.content_address, "base_v2_admission": self.base_v2_admission.to_dict(), "base_v2_admission_address": self.base_v2_admission.admission_address, "phase4_data_binding": _plain_json(self.phase4_data_binding), "capability_assessment": _plain_json(capability_assessment_authority_envelope(self.assessment))}


def admit_phase4_v2_strategy(*, owner_id: str, mode: str, document: Mapping[str, Any], registry: PlatformRegistry,
                             evidence: V2AdmissionEvidence, plan: DataRequirementPlan,
                             input_bindings: ContractInputBindings | None = None,
                             assessment_address: str, dataset_manifest_address: str,
                             market_truth_snapshot_address: str, evaluation_policy_address: str,
                             research_session, execution_session,
                             at_time: dt.datetime) -> Phase4V2AdmittedStrategyArtifact:
    """Construct the sole Phase 4 wrapper after fresh two-plane reconstruction."""
    if not registry.data_requirement_declarations:
        raise AdmissionRefused(AdmissionRefusalCode.ARTEFACT_MISMATCH, "Phase 4 admission requires an opted-in registry")
    try:
        base, resolved = _admit_v2_strategy_and_resolved(
            owner_id=owner_id, document=document, registry=registry,
            evidence=evidence,
        )
        canonical_plan = compile_data_requirement_plan(
            resolved, registry=registry, input_bindings=input_bindings
        )
        from app.market_data.authority import load_capability_assessment
        from research.domain.strategy_admissions import load_verified_dataset_authority
        dataset = load_verified_dataset_authority(
            research_session, owner_id=owner_id,
            manifest_address=dataset_manifest_address, execution_session=execution_session,
            at_time=at_time)
        assessment = load_capability_assessment(
            execution_session, assessment_address, plan=canonical_plan, at_time=at_time)
        _require_canonical_assessment(assessment)
        manifest = dataset.manifest
        from app.market_data.authority import load_capability_profile
        from app.market_truth.authority import load_market_truth_snapshot
        from app.market_truth.identity import load_provider_identity
        load_capability_profile(
            execution_session, manifest.capability_profile_address, at_time=at_time)
        for truth_address in manifest.truth_snapshot_addresses:
            load_market_truth_snapshot(execution_session, truth_address)
        for contract_address in manifest.provider_contract_addresses:
            entity, product, contract = load_provider_identity(
                execution_session, contract_address)
            if (entity.address not in manifest.provider_entity_addresses
                    or product.address not in manifest.provider_product_addresses
                    or contract.owner_id != owner_id or contract.mode != mode):
                raise CapabilityRefusal("dataset provider chain does not match admission")
        if (plan != canonical_plan or assessment.authority_address != assessment_address
                or manifest.owner_id != owner_id or manifest.mode != mode
                or manifest.manifest_address != dataset_manifest_address
                or assessment.owner_id != owner_id or assessment.mode != mode
                or assessment.plan_address != plan.plan_address
                or assessment.registry_snapshot_address != plan.registry_snapshot_address
                or assessment.dataset_manifest_address != dataset_manifest_address
                or assessment.market_truth_snapshot_address != market_truth_snapshot_address
                or assessment.evaluation_policy_address != evaluation_policy_address
                or any(row["result"] != "SATISFIED" for row in assessment.requirement_results)):
            raise CapabilityRefusal("Phase 4 facts disagree or capability is unavailable")
        verify_assessment_coverage(assessment, canonical_plan)
        binding = {"owner_id": owner_id, "mode": mode, "authored_ir_address": plan.authored_ir_address, "registry_snapshot_address": plan.registry_snapshot_address, "resolved_graph_address": plan.resolved_graph_address, "implementation_closure_address": plan.implementation_closure_address, "declaration_addresses": list(plan.declaration_addresses), "plan_address": plan.plan_address, "capability_assessment_address": assessment.authority_address, "dataset_manifest_address": dataset_manifest_address, "market_truth_snapshot_address": market_truth_snapshot_address, "evaluation_policy_address": evaluation_policy_address}
        return Phase4V2AdmittedStrategyArtifact(base, binding, assessment, _PHASE4_CONSTRUCTION_TOKEN)
    except (CapabilityRefusal, ValueError) as exc:
        raise AdmissionRefused(AdmissionRefusalCode.ARTEFACT_MISMATCH, "Phase 4 capability binding refused") from exc


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


def matches_execution_identity(
    artifact: AdmittedStrategyArtifact,
    *,
    strategy_key: str | None,
    strategy_version: str | None,
    graph_address: str | None = None,
    attribution_state: str | None = None,
) -> bool:
    """Match the identity a money row records to one exact admitted artefact.

    Native IR authority records the graph namespace and immutable graph address.
    Handwritten adapters retain their separately admitted source key and version while
    executing the equivalent IR runtime.
    """
    if artifact.source == "ir_graph":
        return (
            strategy_key == f"ir.{artifact.graph_identifier}"
            and strategy_version == str(artifact.graph_version)
            and graph_address == artifact.graph_address
            and attribution_state == VERIFIED_GRAPH
        )
    source = artifact.source_evidence
    return (
        strategy_key == source.strategy_key
        and strategy_version == source.strategy_version
        and graph_address is None
        and attribution_state == NON_GRAPH
    )


def artifact_from_dict(document: Mapping[str, Any]) -> AdmittedStrategyArtifact:
    """Rebuild one persisted receipt only when its full canonical shape is valid."""
    try:
        source = document["source_evidence"]
        artifact = AdmittedStrategyArtifact(
            owner_id=document["owner_id"], source=document["source"],
            source_evidence=SourceEvidence(
                source["source"], source["strategy_key"], source["strategy_version"],
                source["adapter_implementation_address"], source["adapter_decision_address"],
            ),
            graph_identifier=document["graph_identifier"], graph_version=document["graph_version"],
            graph_address=document["graph_address"],
            resolved_components=tuple(ResolvedComponentIdentity(
                item["node_path"], item["identifier"], item["version"], item["body_ref"],
                item["bound_parameters"],
            ) for item in document["resolved_components"]),
            input_provenance=tuple(InputProvenance(
                item["node_path"], item["socket"], tuple(item["root_market_inputs"]),
                tuple(tuple(path) for path in item["source_paths"]),
            ) for item in document["input_provenance"]),
            bound_parameters=document["bound_parameters"],
            kernels=tuple(AdmittedKernelIdentity(
                item["body_ref"], item["implementation_address"], item["causal_contract"],
                item["evaluated_history_bars"],
            ) for item in document["kernels"]),
            canonical_mapping=document["canonical_mapping"],
            declared_warmup=document["declared_warmup"], risk_model=document["risk_model"],
            fixture_suite_address=document["fixture_suite_address"],
            reference_decision_address=document["reference_decision_address"],
            vector_decision_address=document["vector_decision_address"],
            scheme=document["scheme"], contract_suite=document["contract_suite"],
            parity_suite=document["parity_suite"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AdmissionRefused(
            AdmissionRefusalCode.RECEIPT_STALE, "persisted admission receipt is invalid"
        ) from exc
    if artifact.to_dict() != dict(document):
        raise AdmissionRefused(
            AdmissionRefusalCode.RECEIPT_STALE, "persisted admission receipt is not canonical"
        )
    return artifact


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
    input_provenance = derive_input_provenance(resolved)
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
        input_provenance=input_provenance,
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


def admit_strategy(*, owner_id: str,
                   source_input: IRGraphAdmissionInput | HandwrittenAdapterInput,
                   registry: PlatformRegistry) -> AdmissionDecision:
    """Admit only exact structural and registered prefix/vector parity evidence."""
    structural_decision = inspect_strategy(
        owner_id=owner_id, source_input=source_input, registry=registry)
    if structural_decision.structural is None:
        return AdmissionDecision(
            None, structural_decision.refusal_code, structural_decision.detail)
    structural = structural_decision.structural
    ir_input = (source_input.equivalent_ir
                if isinstance(source_input, HandwrittenAdapterInput) else source_input)
    graph_data = _plain_json(ir_input.graph)
    parameters = _plain_json(ir_input.parameters)
    assert isinstance(graph_data, Mapping) and isinstance(parameters, Mapping)
    try:
        resolved = resolve(graph_data, registry.library, parameters)
    except (ResolutionError, TypeError, ValueError) as exc:
        return AdmissionDecision(None, AdmissionRefusalCode.RESOLUTION_FAILED, str(exc))

    from app.ir.runtime import EvaluationError, evaluate
    from app.ir.streaming_reference import (
        ReferenceEvaluationError, evaluate_prefix_stream)
    from app.strategy.causal_fixtures import FIXTURE_SUITES

    try:
        suite = FIXTURE_SUITES.require("causal-fixtures/1")
    except (KeyError, ValueError) as exc:
        return AdmissionDecision(None, AdmissionRefusalCode.RECEIPT_STALE, str(exc))

    vector_bytes: list[bytes] = []
    reference_bytes: list[bytes] = []
    adapter_bytes: list[bytes] = []
    for fixture in suite.fixtures:
        fixture_inputs = {
            name: fixture.inputs[name]
            for name in resolved.inputs
            if name in fixture.inputs
        }
        if set(fixture_inputs) != set(resolved.inputs):
            return AdmissionDecision(
                None, AdmissionRefusalCode.REFERENCE_EVALUATION_FAILED,
                f"fixture {fixture.name} lacks graph inputs",
            )
        try:
            vector = evaluate(resolved, fixture_inputs, registry.implementations)
        except (EvaluationError, Exception) as exc:
            return AdmissionDecision(
                None, AdmissionRefusalCode.VECTOR_EVALUATION_FAILED,
                f"fixture {fixture.name}: {exc}",
            )
        try:
            reference = evaluate_prefix_stream(resolved, fixture_inputs, registry)
        except (ReferenceEvaluationError, Exception) as exc:
            return AdmissionDecision(
                None, AdmissionRefusalCode.REFERENCE_EVALUATION_FAILED,
                f"fixture {fixture.name}: {exc}",
            )
        recursive_mismatch = _first_recursive_mismatch(
            resolved, vector.values, reference.values)
        if recursive_mismatch is not None:
            return AdmissionDecision(
                None, AdmissionRefusalCode.STREAMING_DIVERGENCE,
                f"fixture {fixture.name}: recursive node {recursive_mismatch} diverged",
            )
        vector_frame = _decision_frame(vector.outputs, structural, fixture_inputs)
        reference_frame = _decision_frame(reference.outputs, structural, fixture_inputs)
        vector_encoded = canonical_decisions(vector_frame)
        reference_encoded = canonical_decisions(reference_frame)
        if vector_encoded != reference_encoded:
            return AdmissionDecision(
                None, AdmissionRefusalCode.STREAMING_DIVERGENCE,
                f"fixture {fixture.name}: canonical decisions diverged",
            )
        vector_bytes.append(vector_encoded)
        reference_bytes.append(reference_encoded)

        if isinstance(source_input, HandwrittenAdapterInput):
            try:
                adapter = (source_input.adapter_implementation()
                           if isinstance(source_input.adapter_implementation, type)
                           else source_input.adapter_implementation)
                frame = pd.DataFrame({
                    name: fixture.inputs[name] for name in fixture.inputs
                })
                frame["date"] = frame.index
                adapter_frame = adapter.signals(frame, **parameters)
                encoded = canonical_decisions(adapter_frame)
            except Exception as exc:
                return AdmissionDecision(
                    None, AdmissionRefusalCode.REFERENCE_EVALUATION_FAILED,
                    f"fixture {fixture.name}: handwritten adapter failed: {exc}",
                )
            if encoded != vector_encoded:
                return AdmissionDecision(
                    None, AdmissionRefusalCode.STREAMING_DIVERGENCE,
                    f"fixture {fixture.name}: handwritten adapter decisions diverged",
                )
            adapter_bytes.append(encoded)

    reference_address = content_address({
        "suite": suite.address,
        "decisions": [item.decode("utf-8") for item in reference_bytes],
    })
    vector_address = content_address({
        "suite": suite.address,
        "decisions": [item.decode("utf-8") for item in vector_bytes],
    })
    if adapter_bytes:
        adapter_address = content_address({
            "suite": suite.address,
            "decisions": [item.decode("utf-8") for item in adapter_bytes],
        })
        if adapter_address != vector_address:
            return AdmissionDecision(
                None, AdmissionRefusalCode.STREAMING_DIVERGENCE,
                "handwritten adapter decision address diverged",
            )
        structural = dataclasses.replace(
            structural,
            source_evidence=dataclasses.replace(
                structural.source_evidence,
                adapter_decision_address=adapter_address,
            ),
        )
    try:
        artifact = admitted_artifact(structural, ParityEvidence(
            suite.address, reference_address, vector_address))
    except AdmissionRefused as exc:
        return AdmissionDecision(None, exc.code, exc.detail)
    return AdmissionDecision(artifact, None, "")


def verify_admission(*, artifact: AdmittedStrategyArtifact, owner_id: str,
                     source_input: IRGraphAdmissionInput | HandwrittenAdapterInput,
                     registry: PlatformRegistry) -> None:
    """Recompute an admission and reject any stale or owner-mismatched receipt."""
    decision = admit_strategy(
        owner_id=owner_id, source_input=source_input, registry=registry)
    if decision.artifact is None:
        raise AdmissionRefused(
            decision.refusal_code or AdmissionRefusalCode.RECEIPT_STALE,
            decision.detail)
    if decision.artifact.admission_address != artifact.admission_address:
        raise AdmissionRefused(
            AdmissionRefusalCode.RECEIPT_STALE,
            "recomputed admission address differs from the supplied artifact")


def runtime_for_admitted(
    artifact: AdmittedStrategyArtifact,
    source_input: IRGraphAdmissionInput | HandwrittenAdapterInput,
    registry: PlatformRegistry,
):
    """Return admitted IR authority; handwritten code remains parity evidence only."""
    from app.strategy.ir_adapter import IRGraphStrategy
    verify_admission(
        artifact=artifact,
        owner_id=artifact.owner_id,
        source_input=source_input,
        registry=registry,
    )
    graph_input = (source_input.equivalent_ir
                   if isinstance(source_input, HandwrittenAdapterInput) else source_input)
    if artifact.graph_address != content_address(_plain_json(graph_input.graph)):
        raise AdmissionRefused(
            AdmissionRefusalCode.ARTEFACT_MISMATCH,
            "runtime graph differs from the admitted graph")
    return IRGraphStrategy(
        _plain_json(graph_input.graph),
        (registry.library, registry.implementations),
    )


def _decision_frame(outputs: Mapping[str, Any], structural: StructuralAdmission,
                    inputs: Mapping[str, pd.Series]) -> pd.DataFrame:
    index = next(iter(inputs.values())).index
    frame = pd.DataFrame(index=index)
    for canonical in CANONICAL_COLUMNS:
        output_name = structural.canonical_mapping.get(canonical)
        if output_name is None:
            frame[canonical] = False
            continue
        value = outputs[output_name]
        values = value if isinstance(value, pd.Series) else [value] * len(index)
        frame[canonical] = pd.Series(values, index=index).fillna(False).astype(bool)
    return frame


def _first_recursive_mismatch(
    graph: ResolvedGraph,
    vector_values: Mapping[str, Mapping[str, Any]],
    reference_values: Mapping[str, Mapping[str, Any]],
) -> str | None:
    from app.ir.hashing import canonical_json
    for node in graph.nodes:
        if not node.causal or node.causal.history.mode != "causal_recursive":
            continue
        warmup = node.warmup
        for socket, reference in reference_values[node.instance_id].items():
            vector = vector_values[node.instance_id].get(socket)
            if _canonical_stream(vector, warmup, canonical_json) != _canonical_stream(
                    reference, warmup, canonical_json):
                return f"{node.instance_id}.{socket}"
    return None


def _canonical_stream(value: Any, warmup: int, canonical_json_fn) -> str:
    if not isinstance(value, pd.Series):
        return canonical_json_fn(value)
    encoded = []
    for item in value.iloc[warmup:].tolist():
        if pd.isna(item):
            encoded.append(None)
        elif isinstance(item, (bool, int, float, str)):
            encoded.append(item.item() if hasattr(item, "item") else item)
        else:
            encoded.append(str(item))
    return canonical_json_fn(encoded)


__all__ = [
    "AdmittedKernelIdentity", "AdmittedStrategyArtifact", "AdmissionDecision",
    "AdmissionRefusalCode",
    "AdmissionRefused", "HandwrittenAdapterInput", "IRGraphAdmissionInput",
    "InputProvenance", "ParityEvidence", "ResolvedComponentIdentity",
    "SourceEvidence", "StructuralAdmission", "StructuralDecision",
    "admit_strategy", "admitted_artifact", "artifact_from_dict", "canonical_decisions",
    "derive_input_provenance", "inspect_strategy", "matches_execution_identity",
    "runtime_for_admitted",
    "verify_admission",
]


# ── Phase-4 v2 reconstruction (moved from app/ir per layering: strategy→ir only) ──

from app.ir.v2_graph_versions import (  # noqa: E402 — seam-adjacent helpers
    _SATISFIED_REASON,
    _freeze as _v2_freeze,
    _plain as _v2_plain,
)
from app.ir.hashing import canonical_json as _v2_canonical_json  # noqa: E402

_plain, _freeze, canonical_json = _v2_plain, _v2_freeze, _v2_canonical_json

def derive_v2_graph_facts(artifact) -> "V2GraphFacts":
    """Derive the sole graph record from a constructor-authorized wrapper."""
    from app.ir.v2_graph_versions import (
        V2GraphVerificationError,
        _freeze as _v2_freeze,
        _plain as _v2_plain,
        _verify_graph_facts,
    )
    _plain, _freeze = _v2_plain, _v2_freeze
    from app.ir.hashing import canonical_json as _canonical_json
    canonical_json = _canonical_json

    from app.ir.v2_graph_versions import PHASE4_BOUND_SCHEME
    expected_type = {PHASE4_SCHEME: Phase4V2AdmittedStrategyArtifact,
                     PHASE4_BOUND_SCHEME: Phase4BoundV2AdmittedStrategyArtifact}.get(getattr(artifact, "scheme", None))
    if type(artifact) is not expected_type:
        raise V2GraphVerificationError(
            "v2 graph writes require the constructor-authorized Phase 4 artifact"
        )
    base = artifact.base_v2_admission
    document = _plain(base.document)
    artifact_json = canonical_json(document)
    facts = V2GraphFacts(
        owner_id=artifact.owner_id,
        graph_identifier=artifact.graph_identifier,
        graph_version=artifact.graph_version,
        artifact_json=artifact_json,
        format_version=2,
        content_address=artifact.content_address,
        graph_address=artifact.graph_address,
        registry_snapshot_address=artifact.phase4_data_binding[
            "registry_snapshot_address"
        ],
    )
    _verify_graph_facts(facts, document=document)
    return facts


def _require_assessment(document: Any, *, binding: Mapping[str, Any], plan: Any) -> Mapping[str, Any]:
    from app.market_data.capability import (
        CapabilityRefusal,
        require_capability_assessment_authority_envelope,
    )

    try:
        envelope, address = require_capability_assessment_authority_envelope(document)
    except CapabilityRefusal as exc:
        raise V2GraphVerificationError(
            "persisted capability assessment authority is invalid"
        ) from exc
    assessment = envelope["fact"]
    if (
        assessment["owner_id"] != binding["owner_id"]
        or assessment["mode"] != binding["mode"]
        or address != binding["capability_assessment_address"]
    ):
        raise V2GraphVerificationError("persisted capability assessment identity is stale")
    repeated = {
        "plan_address": "plan_address",
        "registry_snapshot_address": "registry_snapshot_address",
        "dataset_manifest_address": "dataset_manifest_address",
        "market_truth_snapshot_address": "market_truth_snapshot_address",
        "evaluation_policy_address": "evaluation_policy_address",
    }
    if any(assessment[left] != binding[right] for left, right in repeated.items()):
        raise V2GraphVerificationError("persisted capability assessment binding is stale")
    rows = assessment["requirement_results"]
    if not isinstance(rows, list):
        raise V2GraphVerificationError("persisted assessment results are malformed")
    selectors: list[str] = []
    for row in rows:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"selector", "result", "reason"}
            or not is_content_address(row.get("selector"))
            or row.get("result") != "SATISFIED"
            or row.get("reason") != _SATISFIED_REASON
        ):
            raise V2GraphVerificationError("persisted assessment result is not satisfied")
        selectors.append(row["selector"])
    if selectors != sorted(selectors) or len(selectors) != len(set(selectors)):
        raise V2GraphVerificationError("persisted assessment selectors are not canonical")
    expected_selectors = sorted(content_address({
        "authored_node_id": record["authored_node_id"],
        "lowered_path": list(record["lowered_path"]),
        "leaf_component": {
            "component_id": record["leaf_component"][0],
            "component_version": record["leaf_component"][1],
        },
        "requirement": _plain(record["requirement"]),
    }) for record in plan.requirements)
    if selectors != expected_selectors:
        raise V2GraphVerificationError(
            "persisted assessment coverage does not match the compiled plan"
        )
    return _freeze(envelope)


def _reconcile_phase4_base(*, owner_id: str, document: Mapping[str, Any],
                           registry: PlatformRegistry):
    """Re-run admission over a persisted base receipt's exact bytes."""
    evidence = V2AdmissionEvidence(**document["evidence"])
    return _admit_v2_strategy_and_resolved(
        owner_id=owner_id,
        document=document["document"],
        registry=registry,
        evidence=evidence,
    )


def reconstruct_phase4_artifact(
    document: Mapping[str, Any], *, owner_id: str, registry: Any,
    input_bindings: ContractInputBindings | None = None,
) -> PersistedPhase4Artifact:
    """Verify a Phase 4 receipt after restart without minting write authority."""
    if not isinstance(document, Mapping) or document.get("scheme") != PHASE4_SCHEME:
        raise V2GraphVerificationError("not a Phase 4 v2 receipt")
    receipt = _plain(document)
    required = {
        "scheme", "contract_suite", "parity_suite", "format_version", "owner_id",
        "graph_identifier", "graph_version", "graph_address", "content_address",
        "base_v2_admission", "base_v2_admission_address", "phase4_data_binding",
        "capability_assessment",
    }
    if set(receipt) != required:
        raise V2GraphVerificationError("Phase 4 v2 receipt is not closed")
    if (
        receipt["scheme"] != PHASE4_SCHEME
        or receipt["contract_suite"] != "closed-component-ir/2"
        or receipt["parity_suite"] != "prefix-vector-parity/1"
        or receipt["format_version"] != 2
    ):
        raise V2GraphVerificationError("Phase 4 v2 receipt contract is stale")
    base_document = receipt["base_v2_admission"]
    binding = receipt["phase4_data_binding"]
    if not isinstance(base_document, Mapping) or not isinstance(binding, Mapping):
        raise V2GraphVerificationError("Phase 4 base receipt or binding is malformed")
    try:
        base, resolved = _reconcile_phase4_base(
            owner_id=owner_id, document=base_document, registry=registry
        )
    except (AdmissionRefused, KeyError, TypeError, ValueError) as exc:
        raise V2GraphVerificationError("persisted Phase 4 base receipt is invalid") from exc
    if (
        base.to_dict() != base_document
        or base.admission_address != receipt["base_v2_admission_address"]
        or any(receipt.get(name) != getattr(base, name) for name in (
            "owner_id", "graph_identifier", "graph_version", "graph_address",
            "content_address", "format_version",
        ))
    ):
        raise V2GraphVerificationError("persisted Phase 4 base receipt is stale")
    try:
        plan = compile_data_requirement_plan(
            resolved, registry=registry, input_bindings=input_bindings
        )
    except (TypeError, ValueError) as exc:
        raise V2GraphVerificationError("persisted Phase 4 graph no longer resolves") from exc
    if (
        resolved.topology_document is None
        or binding.get("resolved_graph_address") != resolved.resolved_graph_address
    ):
        raise V2GraphVerificationError(
            "persisted Phase 4 resolved topology identity is stale")
    expected_binding = {
        "owner_id": owner_id,
        "mode": binding.get("mode"),
        "authored_ir_address": plan.authored_ir_address,
        "registry_snapshot_address": plan.registry_snapshot_address,
        "resolved_graph_address": plan.resolved_graph_address,
        "implementation_closure_address": plan.implementation_closure_address,
        "declaration_addresses": list(plan.declaration_addresses),
        "plan_address": plan.plan_address,
        "capability_assessment_address": binding.get("capability_assessment_address"),
        "dataset_manifest_address": binding.get("dataset_manifest_address"),
        "market_truth_snapshot_address": binding.get("market_truth_snapshot_address"),
        "evaluation_policy_address": binding.get("evaluation_policy_address"),
    }
    if binding != expected_binding:
        raise V2GraphVerificationError("persisted Phase 4 data binding is stale")
    assessment = _require_assessment(
        receipt["capability_assessment"], binding=binding, plan=plan
    )
    return PersistedPhase4Artifact(_freeze(receipt), base, assessment, plan)


@dataclass(frozen=True, init=False)
class Phase4BoundV2AdmittedStrategyArtifact(PersistedPhase4Artifact):
    """Constructor-authorized research receipt for separately verified sources."""

    def __init__(self, *_args, **_kwargs):
        raise V2GraphVerificationError("bound Phase 4 receipts use the admission seam")


def _bound_plan_binding(plan, projection, assessment, evaluation_policy_address):
    return {"owner_id": projection.manifest.owner_id, "mode": "RESEARCH",
        "authored_ir_address": plan.authored_ir_address, "registry_snapshot_address": plan.registry_snapshot_address,
        "resolved_graph_address": plan.resolved_graph_address, "implementation_closure_address": plan.implementation_closure_address,
        "declaration_addresses": list(plan.declaration_addresses), "plan_address": plan.plan_address,
        "capability_assessment_address": assessment.authority_address,
        "dataset_manifest_address": projection.manifest.manifest_address,
        "dataset_set_address": projection.dataset_selection_address, "primary_input": projection.primary_input,
        "input_binding_context_address": projection.input_bindings.context_address,
        "truth_snapshot_addresses": sorted({address for source in projection.input_sources.values()
                                            for address in source.manifest.truth_snapshot_addresses}),
        "evaluation_policy_address": evaluation_policy_address}


def reload_phase4_bound_projection(*, projection, owner_id, document, research_session,
                                  execution_session, at_time):
    """Reconstruct every owner-local source; supplied projection facts are hints only."""
    from types import SimpleNamespace
    from research.data.canonical_dataset import load_canonical_datasets, project_verified_research_input_set
    from app.ir.v2_graph_versions import _plain, _bound_check
    selection = _bound_projection_selection(projection, owner_id, document, at_time)
    inputs = selection["inputs"]
    addresses = sorted({row["dataset_manifest_address"] for row in inputs.values()})
    loaded = load_canonical_datasets(research_session, execution_session=execution_session, owner_id=owner_id,
        selections=[SimpleNamespace(manifest_address=address, as_of=at_time) for address in addresses])
    by_address = {dataset._verified_authority.manifest.manifest_address: dataset for _, dataset in loaded}
    rebuilt = project_verified_research_input_set(
        {name: by_address[row["dataset_manifest_address"]] for name, row in inputs.items()},
        owner_id=owner_id, primary_input=selection["primary_input"],
        graph_input_fields={name: tuple(entry["binding"]["fields"])
                            for name, entry in projection.input_bindings.document["inputs"].items()})
    _bound_check(_plain(rebuilt.dataset_selection_document) == selection
        and rebuilt.input_digest == projection.input_digest
        and rebuilt.input_bindings == projection.input_bindings, "bound dataset projection differs")
    return rebuilt


def _bound_projection_selection(projection, owner_id, document, at_time):
    from app.ir.v2_graph_versions import _plain, _bound_check
    selection = _plain(projection.dataset_selection_document)
    _bound_check(selection["owner_id"] == owner_id
        and dt.datetime.fromisoformat(selection["as_of"]) == at_time, "bound source owner or cutoff differs")
    _bound_check(set(selection["inputs"]) == {port["port_id"] for port in document["graph_inputs"]}, "bound graph inputs differ")
    return selection


def _bound_capability_sources(projection, execution_session, at_time):
    from app.market_data.authority import load_capability_profile, load_provider_conformance
    from app.market_truth.identity import load_provider_identity
    from app.market_data.capability import CapabilitySourceBinding
    sources = []
    for name, source in sorted(projection.input_sources.items()):
        manifest = source.manifest
        profile = load_capability_profile(execution_session, manifest.capability_profile_address, at_time=at_time)
        conformance = load_provider_conformance(execution_session, profile.conformance_evidence_address)
        _, _, contract = load_provider_identity(execution_session, profile.provider_contract_address)
        source_name = projection.dataset_selection_document["inputs"][name]["source_input_id"]
        sources.append(CapabilitySourceBinding(name, source_name, source.input_bindings,
                                               manifest, profile, conformance, contract))
    return tuple(sources)


def _recompute_bound_assessment(*, projection, resolved, registry, plan, evaluation_policy_address,
                                execution_session, at_time):
    from app.market_data.capability import assess_bound_capability
    return assess_bound_capability(plan=plan, resolved_graph=resolved, registry=registry,
        input_bindings=projection.input_bindings, sources=_bound_capability_sources(projection, execution_session, at_time),
        owner_id=projection.manifest.owner_id, mode="RESEARCH", dataset_set_address=projection.dataset_selection_address,
        evaluation_policy_address=evaluation_policy_address, at_time=int(at_time.timestamp()))


def admit_phase4_bound_v2_strategy(*, owner_id, document, registry, evidence, plan, projection,
        evaluation_policy_address, research_session, execution_session, at_time):
    """Issue a research-only /2 receipt after fresh source-bound reconstruction."""
    from app.ir.v2_graph_versions import PHASE4_BOUND_SCHEME, _bound_check, _freeze
    from app.market_data.capability import bound_capability_assessment_envelope
    projection = reload_phase4_bound_projection(projection=projection, owner_id=owner_id, document=document,
        research_session=research_session, execution_session=execution_session, at_time=at_time)
    base, resolved = _admit_v2_strategy_and_resolved(owner_id=owner_id, document=document, registry=registry, evidence=evidence)
    canonical_plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=projection.input_bindings)
    _bound_check(plan == canonical_plan and evidence.dataset_address == projection.dataset_selection_address
        and evidence.input_address == projection.input_digest, "bound preparation evidence differs")
    assessment = _recompute_bound_assessment(projection=projection, resolved=resolved, registry=registry, plan=plan,
        evaluation_policy_address=evaluation_policy_address, execution_session=execution_session, at_time=at_time)
    document = {key: getattr(base, key) for key in ("contract_suite", "parity_suite", "format_version", "owner_id",
                                                   "graph_identifier", "graph_version", "graph_address", "content_address")}
    document.update({"scheme": PHASE4_BOUND_SCHEME, "base_v2_admission": base.to_dict(),
        "base_v2_admission_address": base.admission_address,
        "phase4_data_binding": _bound_plan_binding(plan, projection, assessment, evaluation_policy_address),
        "capability_assessment": bound_capability_assessment_envelope(assessment),
        "dataset_selection": _plain_json(projection.dataset_selection_document)})
    checked = reconstruct_phase4_bound_artifact(document, owner_id=owner_id, registry=registry,
                                                input_bindings=projection.input_bindings)
    artifact = object.__new__(Phase4BoundV2AdmittedStrategyArtifact)
    for key, value in vars(checked).items():
        object.__setattr__(artifact, key, _freeze(value) if isinstance(value, Mapping) else value)
    return artifact


def reconstruct_phase4_bound_artifact(document, *, owner_id, registry, input_bindings):
    """Check /2 immutable evidence without granting new write authority."""
    from app.ir.v2_graph_versions import require_bound_phase4_receipt, _bound_check, _freeze
    from app.market_data.capability import _requirement_selector
    receipt = require_bound_phase4_receipt(document)
    base, resolved = _reconcile_phase4_base(owner_id=owner_id, document=receipt["base_v2_admission"], registry=registry)
    _bound_check(base.to_dict() == receipt["base_v2_admission"], "bound base reconstruction differs")
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=input_bindings)
    binding = receipt["phase4_data_binding"]
    expected = {"owner_id": owner_id, "authored_ir_address": plan.authored_ir_address,
        "registry_snapshot_address": plan.registry_snapshot_address, "resolved_graph_address": plan.resolved_graph_address,
        "implementation_closure_address": plan.implementation_closure_address,
        "declaration_addresses": list(plan.declaration_addresses), "plan_address": plan.plan_address,
        "input_binding_context_address": input_bindings.context_address}
    _bound_check(all(binding[key] == value for key, value in expected.items()), "bound plan reconstruction differs")
    assessment = receipt["capability_assessment"]["fact"]
    _bound_check([row["selector"] for row in assessment["requirement_results"]]
        == sorted(_requirement_selector(row) for row in plan.requirements), "bound requirement coverage differs")
    _require_bound_receipt_bindings(receipt, input_bindings, base)
    _require_bound_requirement_sources(assessment, plan, input_bindings)
    return PersistedPhase4Artifact(_freeze(receipt), base, _freeze(receipt["capability_assessment"]), plan)


def _require_bound_receipt_bindings(receipt, input_bindings, base):
    from app.ir.v2_graph_versions import _bound_check
    from app.ir.first_party.analytical_v2.contracts import validate_input_bindings
    validate_input_bindings(input_bindings)
    context = content_address({"schema": "verified-observation-input-set-context/1",
        "dataset_selection_address": receipt["phase4_data_binding"]["dataset_set_address"]})
    _bound_check(input_bindings.document["dataset_context_address"] == context, "bound selection context differs")
    sources = receipt["capability_assessment"]["fact"]["sources"]
    inputs = input_bindings.document["inputs"]
    _bound_check(input_bindings.document["owner_id"] == base.owner_id
        and set(inputs) == {source["graph_input_id"] for source in sources}, "bound input ownership differs")
    for source in sources:
        entry = inputs[source["graph_input_id"]]
        _bound_check(entry["binding_address"] == source["projected_binding_address"]
            and entry["binding"]["canonical_instrument_address"] == source["canonical_instrument_address"],
            "bound projected source differs")
    _bound_check(base.evidence.dataset_address == receipt["phase4_data_binding"]["dataset_set_address"],
        "bound evidence dataset differs")


def _require_bound_requirement_sources(assessment, plan, input_bindings):
    from app.ir.v2_graph_versions import _bound_check
    from app.market_data.capability import _requirement_selector
    assigned = {row["selector"]: row["graph_input_id"] for row in assessment["requirement_sources"]}
    for record in plan.requirements:
        requirement = record["requirement"]
        entry = input_bindings.document["inputs"][assigned[_requirement_selector(record)]]["binding"]
        _bound_check(requirement["instrument"] == entry["instrument"] and requirement["field"] in entry["fields"],
            "bound requirement source differs")


__all__ = [
    "Phase4BoundV2AdmittedStrategyArtifact", "admit_phase4_bound_v2_strategy", "reconstruct_phase4_bound_artifact",
    "PHASE4_SCHEME", "V2_RUNTIME_UNAVAILABLE", "PersistedPhase4Artifact",
    "V2GraphFacts", "V2GraphVerificationError", "derive_v2_graph_facts",
    "reconstruct_phase4_artifact",
]
