"""Bounded completed-event incremental evaluation for accepted v2 research graphs."""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from app.ir.hashing import content_address
from app.ir.implementation_identity import ImplementationUnidentified, implementation_address
from app.ir.registry import PlatformRegistry
from app.ir.resource_plan import (
    CanonicalResourceDocument,
    ResourcePlan,
    ResourcePlanRefusal,
    compile_resource_plan,
    instrument_role_requirement,
    provider_requirement,
)
from app.ir.schema import is_content_address
from app.ir.streaming_reference import (
    ReferenceEvaluationError, _v2_scalar_output_names, _v2_check_scalar_prefix,
    _v2_collect_prefix, _v2_prefix_outputs,
)
from app.ir.validity import NumericValue
from app.ir.state_snapshots import (
    ResearchSnapshotAuthority,
    _create_research_snapshot_authority,
    create_research_checkpoint,
)
from app.ir.first_party.logic_state import StateRestoreContext, StateSeriesResult
from app.ir.first_party.analytical_v2.contracts import (
    ContractInputBindings,
    validate_input_bindings,
)
from app.market_data.requirements import (
    DataRequirementPlan,
    DataRequirementRefusal,
    compile_data_requirement_plan,
)


class IncrementalRuntimeRefusal(ValueError):
    pass


@dataclass(frozen=True)
class _ResourceGraphProjection:
    authored_ir_address: str
    resolved_graph_address: str
    implementation_closure_address: str
    registry_snapshot_address: str
    nodes: tuple[Any, ...]
    topology_document: Mapping[str, Any]


@dataclass(frozen=True, init=False)
class AcceptedResearchResourcePlan:
    """A ResourcePlan retained with every input needed to recompile it."""

    plan: ResourcePlan
    data_requirement_plan: DataRequirementPlan
    input_bindings: ContractInputBindings | None
    registry_snapshot_address: str
    instrument_roles: tuple[CanonicalResourceDocument, ...]
    provider_requirements: tuple[CanonicalResourceDocument, ...]
    assumption_addresses: tuple[str, ...]
    cache_bytes_upper_bound: int
    artifact_bytes_upper_bound: int
    queue_concurrency_upper_bound: int

    def __init__(self, *args, **kwargs) -> None:
        raise IncrementalRuntimeRefusal(
            "research ResourcePlans use accept_research_resource_plan"
        )

    @property
    def document(self) -> Mapping[str, Any]:
        return self.plan.document

    @property
    def plan_address(self) -> str:
        return self.plan.plan_address


@dataclass(frozen=True, init=False)
class AcceptedResearchSnapshotContext:
    """Snapshot authority minted by the verified research execution boundary."""

    component: tuple[str, int]
    node_id: str
    node_parameters: Mapping[str, Any]
    registry_snapshot_address: str
    resource_plan_address: str
    run_authority_address: str
    authority: ResearchSnapshotAuthority
    context_address: str

    def __init__(self, *args, **kwargs) -> None:
        raise IncrementalRuntimeRefusal(
            "snapshot contexts use accept_research_snapshot_context"
        )


def accept_research_resource_plan(
    graph: Any,
    data_requirement_plan: DataRequirementPlan,
    registry: PlatformRegistry,
    *,
    instrument_roles: Sequence[CanonicalResourceDocument] = (),
    provider_requirements: Sequence[CanonicalResourceDocument] = (),
    assumption_addresses: Sequence[str] = (),
    cache_bytes_upper_bound: int = 0,
    artifact_bytes_upper_bound: int = 0,
    queue_concurrency_upper_bound: int = 1,
    input_bindings: ContractInputBindings | None = None,
) -> AcceptedResearchResourcePlan:
    if not isinstance(registry, PlatformRegistry) \
            or type(data_requirement_plan) is not DataRequirementPlan:
        raise IncrementalRuntimeRefusal(
            "accepted research resource authority requires canonical graph inputs"
        )
    try:
        if input_bindings is not None:
            validate_input_bindings(input_bindings)
        reconstructed_data = compile_data_requirement_plan(
            graph, registry=registry, input_bindings=input_bindings,
        )
        roles = tuple(_canonical_resource(item, role=True) for item in instrument_roles)
        providers = tuple(
            _canonical_resource(item, role=False) for item in provider_requirements
        )
        plan = compile_resource_plan(
            _resource_graph_projection(graph), data_requirement_plan, registry,
            instrument_roles=roles,
            provider_requirements=providers,
            assumption_addresses=tuple(assumption_addresses),
            cache_bytes_upper_bound=cache_bytes_upper_bound,
            artifact_bytes_upper_bound=artifact_bytes_upper_bound,
            queue_concurrency_upper_bound=queue_concurrency_upper_bound,
        )
    except (DataRequirementRefusal, ResourcePlanRefusal, TypeError, ValueError) as exc:
        raise IncrementalRuntimeRefusal(
            "research ResourcePlan inputs did not compile"
        ) from exc
    if reconstructed_data != data_requirement_plan \
            or plan.document["mode_support"]["research"] is not True:
        raise IncrementalRuntimeRefusal(
            "research ResourcePlan data or mode authority differs"
        )
    result = object.__new__(AcceptedResearchResourcePlan)
    object.__setattr__(result, "plan", plan)
    object.__setattr__(result, "data_requirement_plan", data_requirement_plan)
    object.__setattr__(result, "input_bindings", input_bindings)
    object.__setattr__(result, "registry_snapshot_address", registry.registry_snapshot_address)
    object.__setattr__(result, "instrument_roles", roles)
    object.__setattr__(result, "provider_requirements", providers)
    object.__setattr__(result, "assumption_addresses", tuple(assumption_addresses))
    object.__setattr__(result, "cache_bytes_upper_bound", cache_bytes_upper_bound)
    object.__setattr__(result, "artifact_bytes_upper_bound", artifact_bytes_upper_bound)
    object.__setattr__(result, "queue_concurrency_upper_bound", queue_concurrency_upper_bound)
    return result


def _create_accepted_research_snapshot_context(
    *,
    component: tuple[str, int],
    node_id: str,
    node_parameters: Mapping[str, Any],
    registry_snapshot_address: str,
    resource_plan_address: str,
    run_authority_address: str,
    strategy_address: str,
    resolved_graph_address: str,
    node_contract_address: str,
    implementation_closure_address: str,
    dataset_context_address: str,
    evaluation_context_address: str,
    reset_policy_address: str,
    initial_state_payload: Any,
) -> AcceptedResearchSnapshotContext:
    if not isinstance(component, tuple) or len(component) != 2 \
            or not isinstance(component[0], str) or not component[0] \
            or type(component[1]) is not int or component[1] < 1:
        raise IncrementalRuntimeRefusal("snapshot component identity is malformed")
    if not isinstance(node_id, str) or not node_id:
        raise IncrementalRuntimeRefusal("snapshot node identity is malformed")
    for label, value in (
        ("registry snapshot", registry_snapshot_address),
        ("resource plan", resource_plan_address),
        ("run authority", run_authority_address),
    ):
        if not isinstance(value, str) or not is_content_address(value):
            raise IncrementalRuntimeRefusal(f"{label} identity is malformed")
    evidence = content_address({
        "schema": "accepted-research-snapshot-context/1",
        "component": list(component),
        "node_id": node_id,
        "node_parameters": _plain(node_parameters),
        "registry_snapshot_address": registry_snapshot_address,
        "resource_plan_address": resource_plan_address,
        "run_authority_address": run_authority_address,
        "strategy_address": strategy_address,
        "resolved_graph_address": resolved_graph_address,
        "node_contract_address": node_contract_address,
        "implementation_closure_address": implementation_closure_address,
        "dataset_context_address": dataset_context_address,
        "evaluation_context_address": evaluation_context_address,
        "reset_policy_address": reset_policy_address,
    })
    authority = _create_research_snapshot_authority(
        strategy_address=strategy_address,
        resolved_graph_address=resolved_graph_address,
        node_contract_address=node_contract_address,
        implementation_closure_address=implementation_closure_address,
        dataset_context_address=dataset_context_address,
        evaluation_context_address=evaluation_context_address,
        reset_policy_address=reset_policy_address,
        creation_evidence_address=evidence,
        initial_state_payload=initial_state_payload,
    )
    result = object.__new__(AcceptedResearchSnapshotContext)
    object.__setattr__(result, "component", component)
    object.__setattr__(result, "node_id", node_id)
    object.__setattr__(result, "node_parameters", MappingProxyType(dict(node_parameters)))
    object.__setattr__(result, "registry_snapshot_address", registry_snapshot_address)
    object.__setattr__(result, "resource_plan_address", resource_plan_address)
    object.__setattr__(result, "run_authority_address", run_authority_address)
    object.__setattr__(result, "authority", authority)
    object.__setattr__(result, "context_address", evidence)
    return result


@dataclass
class CancellationToken:
    cancel_after_events: int | None = None
    observed_events: int = 0
    cancelled: bool = False

    def __post_init__(self) -> None:
        if self.cancel_after_events is not None and (
            type(self.cancel_after_events) is not int or self.cancel_after_events < 0
        ):
            raise IncrementalRuntimeRefusal("cancellation bound is invalid")

    def observe(self) -> bool:
        if self.cancelled:
            return False
        if self.cancel_after_events is not None \
                and self.observed_events >= self.cancel_after_events:
            self.cancelled = True
            return False
        self.observed_events += 1
        return True


@dataclass(frozen=True)
class IncrementalEvaluation:
    status: str
    outputs: Mapping[str, Any]
    completed_events: int
    last_event_address: str | None
    last_event_time: str | None
    output_digest: str | None


@dataclass(frozen=True)
class StatefulRestartEvaluation:
    component: tuple[str, int]
    values: tuple[NumericValue, ...]
    state_payload: Any
    checkpoint_address: str
    applied_reset_reasons: tuple[str, ...]


def evaluate_incremental_v2(
    graph: Any,
    inputs: Mapping[str, Any],
    registry: Any,
    resource_plan: AcceptedResearchResourcePlan,
    *,
    event_kind: str,
    maximum_events: int,
    cancellation: CancellationToken | None = None,
    evaluation_context_resolver: Callable[[Any, Mapping[str, Any]], Any]
    | None = None,
) -> IncrementalEvaluation:
    if not isinstance(event_kind, str) or not event_kind:
        raise IncrementalRuntimeRefusal("event kind is absent")
    if type(maximum_events) is not int or maximum_events < 1:
        raise IncrementalRuntimeRefusal("event limit is invalid")
    index = _common_index(graph, inputs, registry)
    event_count = len(index) if index is not None else 1
    if event_count > maximum_events:
        raise IncrementalRuntimeRefusal("event count exceeds evaluation policy")
    _verify_resource_plan(graph, registry, resource_plan, event_kind)
    token = cancellation or CancellationToken()
    try:
        outputs = _evaluate_cancellable_prefixes(
            graph, inputs, registry, token, index,
            evaluation_context_resolver=evaluation_context_resolver,
        )
    except ReferenceEvaluationError as exc:
        raise IncrementalRuntimeRefusal("independent prefix evaluation refused") from exc
    if outputs is None:
        return IncrementalEvaluation(
            "CANCELLED", MappingProxyType({}), token.observed_events,
            None, None, None,
        )
    # The full-input evaluator is the batch oracle.  The incremental result above
    # was assembled from one independently evaluated causal prefix per event, so
    # a future read changes prior cells and fails this comparison.
    oracle = _evaluate_incremental_once(
        graph, inputs, registry,
        evaluation_context_resolver=evaluation_context_resolver,
    )
    if not _equal_outputs(outputs, oracle):
        raise IncrementalRuntimeRefusal("incremental walk and prefix oracle differ")
    last_time = index[-1].isoformat() if index is not None else None
    last_address = content_address({
        "event_kind": event_kind, "event_time": last_time,
        "event_position": event_count,
    })
    digest = content_address({
        "schema": "incremental-output/1",
        "outputs": _stable_value(outputs),
    })
    return IncrementalEvaluation(
        "COMPLETED", MappingProxyType(dict(outputs)), event_count,
        last_address, last_time, digest,
    )


def _evaluate_cancellable_prefixes(
    graph: Any, inputs: Mapping[str, Any], registry: PlatformRegistry,
    token: CancellationToken, index: pd.DatetimeIndex | None,
    *,
    evaluation_context_resolver: Callable[[Any, Mapping[str, Any]], Any]
    | None = None,
) -> Mapping[str, Any] | None:
    if index is None:
        if not token.observe(): return None
        return _evaluate_incremental_once(
            graph, inputs, registry,
            evaluation_context_resolver=evaluation_context_resolver,
        )
    collected: dict[str, list[Any]] = {}
    state_outputs: dict[str, StateSeriesResult] = {}
    scalar_names = _v2_scalar_output_names(graph)
    scalar_outputs: dict[str, Any] = {}
    for end in range(1, len(index)+1):
        if not token.observe(): return None
        prefix = {
            name: _prefix_value(value, end, index)
            for name, value in inputs.items()
        }
        current = _evaluate_incremental_once(
            graph, prefix, registry,
            evaluation_context_resolver=evaluation_context_resolver,
        )
        _v2_check_scalar_prefix(graph, prefix, registry, current, scalar_names, evaluation_context_resolver)
        _v2_collect_prefix(current, end, scalar_names, collected, state_outputs, scalar_outputs)
    return _v2_prefix_outputs(index, collected, state_outputs, scalar_outputs)


def _evaluate_incremental_once(
    graph: Any, inputs: Mapping[str, Any], registry: PlatformRegistry,
    *,
    evaluation_context_resolver: Callable[[Any, Mapping[str, Any]], Any]
    | None = None,
) -> Mapping[str, Any]:
    nodes = {node.node_id: node for node in graph.nodes}
    waiting = {node_id: set() for node_id in nodes}
    for (node_id, _port_id), bundle in graph.bundles.items():
        for member in bundle.members:
            if member.source["scope"] == "node":
                waiting[node_id].add(member.source["node_id"])
    ready = sorted(node_id for node_id, needs in waiting.items() if not needs)
    values: dict[str, Mapping[str, Any]] = {}
    while ready:
        node_id = ready.pop(0); node = nodes[node_id]
        implementation = registry.v2_implementations.get(node.component)
        if implementation is None:
            raise IncrementalRuntimeRefusal("incremental node implementation is absent")
        assembled = {
            port_id: _incremental_bundle_value(bundle, inputs, values)
            for (target, port_id), bundle in graph.bundles.items()
            if target == node_id
        }
        frozen_inputs = MappingProxyType(assembled)
        evaluation_context = (
            evaluation_context_resolver(node, frozen_inputs)
            if evaluation_context_resolver is not None else None
        )
        produced = (
            implementation(
                node.parameters, frozen_inputs,
                evaluation_context=evaluation_context,
            )
            if evaluation_context is not None
            else implementation(node.parameters, frozen_inputs)
        )
        if not isinstance(produced, Mapping):
            raise IncrementalRuntimeRefusal("incremental implementation returned non-mapping")
        values[node_id] = MappingProxyType(dict(produced))
        for downstream in sorted(waiting):
            if node_id in waiting[downstream]:
                waiting[downstream].remove(node_id)
                if not waiting[downstream]: ready.append(downstream)
        ready.sort()
    if len(values) != len(nodes):
        raise IncrementalRuntimeRefusal("incremental graph is cyclic")
    outputs = {}
    for name, member in graph.outputs.items():
        source = member.source
        outputs[name] = (inputs[source["port_id"]]
                         if source["scope"] == "graph_input"
                         else values[source["node_id"]][source["port_id"]])
    return MappingProxyType(outputs)


def _incremental_bundle_value(
    bundle: Any, inputs: Mapping[str, Any], values: Mapping[str, Mapping[str, Any]],
) -> Any:
    members = []
    for member in bundle.members:
        source = member.source
        value = (inputs[source["port_id"]] if source["scope"] == "graph_input"
                 else values[source["node_id"]][source["port_id"]])
        members.append((member, value))
    if not members: return bundle.default
    if bundle.assembly == "single": return members[0][1]
    if bundle.assembly == "keyed":
        return MappingProxyType({member.binding["key"]: value for member, value in members})
    return tuple(value for _member, value in members)


def _equal_outputs(left: Any, right: Any) -> bool:
    if isinstance(left, pd.Series) and isinstance(right, pd.Series): return left.equals(right)
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(_equal_outputs(left[key], right[key]) for key in left)
    return left == right


def _evaluate_stateful_restart_mechanics(
    component: tuple[str, int],
    parameters: Mapping[str, Any],
    full_input: Mapping[str, Any],
    registry: PlatformRegistry,
    context: AcceptedResearchSnapshotContext,
    *,
    split_index: int,
    pending_reset_reasons: tuple[str, ...] = (),
) -> StatefulRestartEvaluation:
    if not isinstance(registry, PlatformRegistry) \
            or not isinstance(context, AcceptedResearchSnapshotContext):
        raise IncrementalRuntimeRefusal(
            "stateful restart requires an accepted research snapshot context"
        )
    authority = _validate_snapshot_context(context, registry, component, parameters)
    contract = registry.node_contracts.get(component)
    implementation = registry.v2_implementations.get(component)
    identity = registry.v2_implementation_identities.get(component)
    if contract is None or implementation is None or identity is None \
            or contract["execution_form"] != "RECURSIVE" \
            or registry.node_contract_addresses.get(component) != authority.node_contract_address:
        raise IncrementalRuntimeRefusal("stateful component authority differs")
    event_times = full_input.get("event_times")
    if not isinstance(event_times, tuple) or not 0 < split_index < len(event_times):
        raise IncrementalRuntimeRefusal("stateful split is invalid")
    full = _state_input_slice(full_input, 0, len(event_times))
    full["reset_reasons"] = []
    first_input = _state_input_slice(full_input, 0, split_index)
    first_input["reset_reasons"] = []
    second_input = _state_input_slice(full_input, split_index, len(event_times))
    second_input["reset_reasons"] = list(pending_reset_reasons)
    batch = implementation(parameters, {"input": full})["value"]
    first = implementation(parameters, {"input": first_input})["value"]
    if not isinstance(batch, StateSeriesResult) or not isinstance(first, StateSeriesResult):
        raise IncrementalRuntimeRefusal("recursive component did not return StateSeriesResult")
    last_event_address = content_address({
        "event_kind": "completed_bar", "event_time": first.last_event_time,
        "component": list(component),
    })
    checkpoint = create_research_checkpoint(
        authority, first.state_payload,
        last_event_address=last_event_address,
        last_event_time=first.last_event_time,
    )
    next_time = second_input["event_times"][0]
    next_address = content_address({
        "event_kind": "completed_bar", "event_time": next_time,
        "component": list(component),
    })
    document = checkpoint.snapshot.document
    context = StateRestoreContext(
        snapshot_address=checkpoint.snapshot.snapshot_address,
        strategy_address=document["strategy_address"],
        resolved_graph_address=document["resolved_graph_address"],
        node_contract_address=document["node_contract_address"],
        implementation_closure_address=document["implementation_closure_address"],
        dataset_context_address=document["dataset_context_address"],
        evaluation_context_address=document["evaluation_context_address"],
        reset_policy_address=document["reset_policy_address"],
        last_event_address=document["last_event_address"],
        creation_evidence_address=document["creation_evidence_address"],
        snapshot_reset_reasons=tuple(document["reset_reasons"]),
        pending_reset_reasons=tuple(pending_reset_reasons),
        next_event_address=next_address,
        next_event_time=next_time,
    )
    second_input.update(
        snapshot=checkpoint.snapshot,
        state_payload=checkpoint.state_payload,
        next_event_address=next_address,
        next_event_time=next_time,
    )
    second = implementation(
        parameters, {"input": second_input}, evaluation_context=context,
    )["value"]
    if not isinstance(second, StateSeriesResult):
        raise IncrementalRuntimeRefusal("recursive restart output is malformed")
    if pending_reset_reasons:
        fresh_input = _state_input_slice(full_input, split_index, len(event_times))
        fresh_input["reset_reasons"] = []
        expected = implementation(parameters, {"input": fresh_input})["value"]
        if second != expected:
            raise IncrementalRuntimeRefusal("reset restart differs from declared initial state")
        values = second.values
    else:
        if first.values + second.values != batch.values \
                or second.state_payload != batch.state_payload:
            raise IncrementalRuntimeRefusal("stateful batch/restart parity differs")
        values = batch.values
    return StatefulRestartEvaluation(
        component, values, second.state_payload, checkpoint.checkpoint_address,
        tuple(sorted(set(pending_reset_reasons))),
    )


def _state_input_slice(value: Mapping[str, Any], start: int, end: int) -> dict[str, Any]:
    result = dict(value)
    for name in ("series", "a_series", "b_series", "event_times", "reset_series"):
        if name in result:
            sequence = result[name]
            if not isinstance(sequence, tuple):
                raise IncrementalRuntimeRefusal(f"stateful {name} must be an immutable sequence")
            result[name] = sequence[start:end]
    for name in ("snapshot", "state_payload", "next_event_address",
                 "next_event_time", "expected_snapshot_identity"):
        result.pop(name, None)
    return result


def _verify_resource_plan(
    graph: Any, registry: Any, authority: AcceptedResearchResourcePlan,
    event_kind: str,
) -> None:
    if not isinstance(authority, AcceptedResearchResourcePlan) \
            or not isinstance(registry, PlatformRegistry):
        raise IncrementalRuntimeRefusal(
            "accepted ResourcePlan and PlatformRegistry are required"
        )
    try:
        if authority.registry_snapshot_address != registry.registry_snapshot_address:
            raise IncrementalRuntimeRefusal("retained registry identity differs")
        if authority.input_bindings is not None:
            validate_input_bindings(authority.input_bindings)
        data_plan = compile_data_requirement_plan(
            graph, registry=registry, input_bindings=authority.input_bindings,
        )
        roles = tuple(_canonical_resource(item, role=True)
                      for item in authority.instrument_roles)
        providers = tuple(_canonical_resource(item, role=False)
                          for item in authority.provider_requirements)
        plan = compile_resource_plan(
            _resource_graph_projection(graph), authority.data_requirement_plan, registry,
            instrument_roles=roles,
            provider_requirements=providers,
            assumption_addresses=authority.assumption_addresses,
            cache_bytes_upper_bound=authority.cache_bytes_upper_bound,
            artifact_bytes_upper_bound=authority.artifact_bytes_upper_bound,
            queue_concurrency_upper_bound=authority.queue_concurrency_upper_bound,
        )
    except (DataRequirementRefusal, ResourcePlanRefusal, TypeError, ValueError) as exc:
        raise IncrementalRuntimeRefusal(
            "ResourcePlan compiler authority did not reconstruct"
        ) from exc
    if data_plan != authority.data_requirement_plan or plan != authority.plan \
            or plan.document["mode_support"]["research"] is not True:
        raise IncrementalRuntimeRefusal(
            "ResourcePlan differs from its retained compiler inputs"
        )
    document = plan.document
    identities = (
        (document["resolved_graph_address"], getattr(graph, "resolved_graph_address", None)),
        (document["implementation_closure_address"], getattr(graph, "implementation_closure_address", None)),
        (document["registry_snapshot_address"], getattr(registry, "registry_snapshot_address", None)),
    )
    if any(left != right or not isinstance(left, str) or not is_content_address(left)
           for left, right in identities):
        raise IncrementalRuntimeRefusal("ResourcePlan and graph/registry identities differ")
    nodes = tuple(getattr(graph, "nodes", ()))
    if not nodes:
        raise IncrementalRuntimeRefusal("research graph has no executable node")
    contracts = getattr(registry, "node_contracts", {})
    addresses = getattr(registry, "node_contract_addresses", {})
    raw_addresses = tuple(addresses.get(node.component) for node in nodes)
    if any(item is None for item in raw_addresses):
        raise IncrementalRuntimeRefusal("research node lacks a contract address")
    expected_addresses = tuple(sorted(set(raw_addresses)))
    if tuple(document["node_contract_addresses"]) != expected_addresses:
        raise IncrementalRuntimeRefusal("ResourcePlan node-contract universe differs")
    family_counts = {family: 0 for family in ("TYPE_1", "TYPE_2", "TYPE_3", "TYPE_4", "TYPE_5")}
    expected_triggers = []
    expected_compute = []
    for node in nodes:
        contract = contracts.get(node.component)
        if contract is None:
            raise IncrementalRuntimeRefusal("research node lacks a canonical contract")
        if not contract["mode_eligibility"]["research"] \
                or not contract["batch_support"] or not contract["streaming_support"]:
            raise IncrementalRuntimeRefusal("research node is not batch/stream eligible")
        if event_kind not in contract["evaluation_triggers"]:
            raise IncrementalRuntimeRefusal("research event is not a declared node trigger")
        family_counts[contract["visible_family"]] += 1
        expected_compute.append({
            "node_id": node.node_id,
            "node_contract_address": addresses[node.component],
            "microseconds_per_event": contract["resource_profile"]["compute_microseconds_per_event"],
        })
        for trigger in contract["evaluation_triggers"]:
            expected_triggers.append({
                "node_id": node.node_id,
                "node_contract_address": addresses[node.component],
                "trigger": trigger,
            })
    if dict(document["family_counts"]) != family_counts \
            or tuple(document["trigger_requirements"]) != tuple(sorted(
                expected_triggers, key=lambda row: (row["node_id"], row["trigger"]),
            )) or tuple(document["compute_requirements"]) != tuple(sorted(
                expected_compute, key=lambda row: row["node_id"],
            )):
        raise IncrementalRuntimeRefusal(
            "ResourcePlan family/trigger/compute declarations differ"
        )


def _validate_snapshot_context(
    context: AcceptedResearchSnapshotContext,
    registry: PlatformRegistry,
    component: tuple[str, int],
    parameters: Mapping[str, Any],
) -> ResearchSnapshotAuthority:
    authority = context.authority
    if not isinstance(authority, ResearchSnapshotAuthority) \
            or context.component != component \
            or dict(context.node_parameters) != dict(parameters) \
            or context.registry_snapshot_address != registry.registry_snapshot_address \
            or context.resource_plan_address == "" \
            or context.run_authority_address == "":
        raise IncrementalRuntimeRefusal("accepted snapshot context identity differs")
    registration = registry.v2_implementation_registrations.get(component)
    implementation = registry.v2_implementations.get(component)
    try:
        address = implementation_address(
            implementation, registration.dependency_boundary,
        )
    except (AttributeError, ImplementationUnidentified, TypeError, ValueError) as exc:
        raise IncrementalRuntimeRefusal(
            "snapshot registry implementation identity is unavailable"
        ) from exc
    if implementation is not registration.implementation \
            or address != registration.implementation_address:
        raise IncrementalRuntimeRefusal(
            "snapshot registry callable differs from its retained identity"
        )
    closure_document = {
        "implementations": [
            {"component_id": key[0], "component_version": key[1],
             "implementation_address": value}
            for key, value in sorted(registry.v2_implementation_identities.items())
        ]
    }
    if registry.contract_bindings:
        closure_document["contract_bindings"] = [
            _plain(registry.contract_bindings[key].document)
            for key in sorted(registry.contract_bindings)
        ]
    closure = content_address(closure_document)
    expected_evidence = content_address({
        "schema": "accepted-research-snapshot-context/1",
        "component": list(component),
        "node_id": context.node_id,
        "node_parameters": _plain(context.node_parameters),
        "registry_snapshot_address": context.registry_snapshot_address,
        "resource_plan_address": context.resource_plan_address,
        "run_authority_address": context.run_authority_address,
        "strategy_address": authority.strategy_address,
        "resolved_graph_address": authority.resolved_graph_address,
        "node_contract_address": authority.node_contract_address,
        "implementation_closure_address": authority.implementation_closure_address,
        "dataset_context_address": authority.dataset_context_address,
        "evaluation_context_address": authority.evaluation_context_address,
        "reset_policy_address": authority.reset_policy_address,
    })
    if closure != authority.implementation_closure_address \
            or registry.node_contract_addresses.get(component) \
            != authority.node_contract_address \
            or expected_evidence != context.context_address \
            or expected_evidence != authority.creation_evidence_address:
        raise IncrementalRuntimeRefusal(
            "snapshot authority is not the accepted full execution closure"
        )
    return authority


def _canonical_resource(
    value: CanonicalResourceDocument, *, role: bool,
) -> CanonicalResourceDocument:
    if not isinstance(value, CanonicalResourceDocument) \
            or value.schema != (
                "instrument-role-requirement/1" if role else "provider-requirement/1"
            ):
        raise IncrementalRuntimeRefusal("resource compiler input is not canonical")
    rebuilt = (
        instrument_role_requirement(_plain(value.document))
        if role else provider_requirement(_plain(value.document))
    )
    if rebuilt != value:
        raise IncrementalRuntimeRefusal("resource compiler input identity differs")
    return rebuilt


def _resource_graph_projection(graph: Any) -> _ResourceGraphProjection:
    topology = getattr(graph, "topology_document", None)
    if not isinstance(topology, Mapping):
        raise IncrementalRuntimeRefusal(
            "ResourcePlan requires complete resolved topology authority"
        )
    edges = tuple(
        edge for edge in topology.get("edges", ())
        if isinstance(edge, Mapping)
        and isinstance(edge.get("source"), Mapping)
        and isinstance(edge["source"].get("node_id"), str)
        and edge["source"]["node_id"]
    )
    return _ResourceGraphProjection(
        getattr(graph, "authored_ir_address", None),
        getattr(graph, "resolved_graph_address", None),
        getattr(graph, "implementation_closure_address", None),
        getattr(graph, "registry_snapshot_address", None),
        tuple(getattr(graph, "nodes", ())),
        MappingProxyType({"edges": edges}),
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


_STATE_SEQUENCE_FIELDS = (
    "series", "a_series", "b_series", "event_times", "reset_series",
)


def _common_index(
    graph: Any, inputs: Mapping[str, Any], registry: PlatformRegistry,
) -> pd.DatetimeIndex | None:
    if not isinstance(inputs, Mapping) or not inputs:
        raise IncrementalRuntimeRefusal("research inputs are absent")
    series: list[pd.Series] = []
    event_indexes: list[pd.DatetimeIndex] = []

    def walk(value: Any) -> None:
        if isinstance(value, pd.Series):
            series.append(value)
            return
        if not isinstance(value, Mapping):
            return
        if any(not isinstance(name, str) or not name for name in value):
            raise IncrementalRuntimeRefusal("research input field name is malformed")
        if "event_times" in value:
            times = value["event_times"]
            if not isinstance(times, tuple) or not times:
                raise IncrementalRuntimeRefusal("recursive event_times must be immutable")
            event_indexes.append(pd.DatetimeIndex(times))
        for name, nested in value.items():
            if name != "event_times":
                walk(nested)

    walk(inputs)
    series = tuple(series)
    index = series[0].index if series else None
    if series and (
        not isinstance(index, pd.DatetimeIndex) or index.tz is None
        or not index.is_monotonic_increasing or not index.is_unique
        or any(not item.index.equals(index) for item in series[1:])
    ):
        raise IncrementalRuntimeRefusal("research input index is not one causal UTC sequence")
    recursive = any(
        (registry.node_contracts.get(node.component) or {}).get("execution_form")
        == "RECURSIVE"
        for node in graph.nodes
    )
    if not recursive:
        return index
    nested_indexes = []
    for nested in event_indexes:
        if nested.tz is None or not nested.is_monotonic_increasing or not nested.is_unique:
            raise IncrementalRuntimeRefusal(
                "recursive event_times are not one causal sequence"
            )
        nested_indexes.append(nested)
    if not nested_indexes and index is not None:
        return index
    if not nested_indexes:
        raise IncrementalRuntimeRefusal("recursive graph input lacks event_times")
    nested = nested_indexes[0]
    if any(not item.equals(nested) for item in nested_indexes[1:]) \
            or index is not None and not index.equals(nested):
        raise IncrementalRuntimeRefusal(
            "recursive graph inputs use different causal clocks"
        )
    return nested


def _prefix_value(value: Any, end: int, index: pd.DatetimeIndex) -> Any:
    if isinstance(value, pd.Series):
        if not value.index.equals(index):
            raise IncrementalRuntimeRefusal(
                "research input index is not one causal UTC sequence"
            )
        return value.iloc[:end]
    if isinstance(value, Mapping):
        result = dict(value)
        if "event_times" in result:
            if not pd.DatetimeIndex(result["event_times"]).equals(index):
                raise IncrementalRuntimeRefusal(
                    "recursive graph inputs use different causal clocks"
                )
            for field in _STATE_SEQUENCE_FIELDS:
                if field in result:
                    result[field] = result[field][:end]
        for field in tuple(result):
            if field not in _STATE_SEQUENCE_FIELDS:
                result[field] = _prefix_value(result[field], end, index)
        return result
    return value


def _stable_value(value: Any) -> Any:
    if isinstance(value, StateSeriesResult):
        return {
            "schema": "state-series-result/1",
            "values": [_stable_value(item) for item in value.values],
            "state_payload": _stable_value(value.state_payload),
            "last_event_time": value.last_event_time,
        }
    if isinstance(value, NumericValue):
        return {
            "schema": "numeric-value/1",
            "state": value.state.value,
            "value": _stable_value(value.value),
            "causes": [item.value for item in value.causes],
        }
    if isinstance(value, pd.Series):
        return {
            "schema": "pandas-series/1",
            "index": [item.isoformat() for item in value.index],
            "values": [_stable_value(item) for item in value.tolist()],
        }
    if isinstance(value, Mapping):
        return {key: _stable_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_stable_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise IncrementalRuntimeRefusal("research output is not closed finite data")


__all__ = [
    "AcceptedResearchResourcePlan", "AcceptedResearchSnapshotContext",
    "CancellationToken", "IncrementalEvaluation", "IncrementalRuntimeRefusal",
    "StatefulRestartEvaluation", "accept_research_resource_plan",
    "evaluate_incremental_v2",
]
