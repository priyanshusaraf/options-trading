"""Closed saved-V2 research operation descriptor and restart executor.

The descriptor is persisted before canonical object bytes are loaded.  Execution
reconstructs every owner/version/admission/data/runtime address from that record;
it never accepts a provider object or lowers the graph into the V1 adapter.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import datetime as dt
import json
import math
import re
from types import MappingProxyType
from typing import Any
import uuid

from app.ir.hashing import canonical_json, content_address
from research.evaluation.v2_resource_policy import (
    V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS,
)


V2_OPERATION_SCHEMA = "v2-graph-research-operation/1"
V2_OPERATION_TRIGGER = "v2_graph"
V2_PROVIDER_MODE = "persisted-dataset"
ADAPTER_POLICY_ADDRESS = "sha256:e35daffd61c1bacb3b51a4384cafaac71f7637b029a541189060a1d6ff7e0ca1"
_PLAN_LIMIT = 65_536
_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class V2OperationRefusal(ValueError):
    """A saved-V2 descriptor cannot be reconstructed exactly."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


def _algorithm_address(name: str, version: int = 1) -> str:
    return content_address({"schema": name, "algorithm_version": version})


TIME_PROJECTION_ALGORITHM_ADDRESS = content_address({
    "schema": "v2-availability-to-bar-open-position-projection/1",
    "algorithm_version": 1,
    "mapping": "same-verified-integer-position",
    "fill": "existing-next-bar-open",
})
RUNTIME_CONTRACT_ADDRESSES = MappingProxyType({
    "input_projection": _algorithm_address("verified-observation-availability-projection"),
    "input_binding": _algorithm_address("canonical-input-bindings"),
    "data_plan_compilation": _algorithm_address("bound-data-requirement-plan"),
    "graph_data_eligibility": _algorithm_address("graph-data-eligibility"),
    "resource_plan_compilation": _algorithm_address("research-resource-plan-compilation"),
    "phase5_policy": _algorithm_address("research-evaluation-policy-construction"),
    "phase5_evaluation": _algorithm_address("phase5-execute-research"),
    "output_adaptation": ADAPTER_POLICY_ADDRESS,
    "time_projection": TIME_PROJECTION_ALGORITHM_ADDRESS,
})
INPUT_SET_RUNTIME_CONTRACT_ADDRESSES = MappingProxyType({
    **RUNTIME_CONTRACT_ADDRESSES,
    "input_projection": _algorithm_address("verified-exact-observation-input-set"),
    "graph_data_eligibility": _algorithm_address("graph-data-eligibility", 2),
    "phase5_policy": _algorithm_address("research-evaluation-policy-construction", 2),
    "source_capability": _algorithm_address("source-bound-capability-evaluation"),
})

_PHASE4_FIELDS = {
    "authored_ir_address", "capability_assessment_address",
    "dataset_manifest_address", "declaration_addresses",
    "evaluation_policy_address", "implementation_closure_address",
    "market_truth_snapshot_address", "mode", "owner_id", "plan_address",
    "registry_snapshot_address", "resolved_graph_address",
}
_EXPERIMENT_FIELDS = {
    "hypothesis", "min_positive_fold_frac", "min_trades", "n_folds",
    "research_capital", "seed",
}
_ITEM_FIELDS = {
    "adapter_policy_address", "admission_address", "content_address",
    "dataset_as_of", "dataset_manifest_address", "descriptor_address",
    "experiment", "graph_address", "graph_identifier", "graph_version",
    "phase4_binding", "project_id", "request_id", "request_identity_address",
    "resource_policy_address", "runtime_contract_addresses",
}
_ROBUSTNESS_FIELDS = {"parameter_neighborhood"}


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _address(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ADDRESS.fullmatch(value) is None:
        raise V2OperationRefusal("V2_OPERATION_INVALID", f"{label} is invalid")
    return value


def _request_id(value: Any) -> str:
    if not isinstance(value, str):
        raise V2OperationRefusal("V2_OPERATION_INVALID", "request_id is invalid")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise V2OperationRefusal("V2_OPERATION_INVALID", "request_id is invalid") from None
    if parsed.version != 4 or str(parsed) != value or parsed.variant != uuid.RFC_4122:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "request_id is invalid")
    return value


def operation_id_for_request(*, owner_id: str, request_id: str) -> str:
    if not isinstance(owner_id, str) or not owner_id or len(owner_id) > 64:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "owner_id is invalid")
    request_id = _request_id(request_id)
    return content_address({
        "schema": "v2-research-operation-id/1",
        "owner_id": owner_id,
        "request_id": request_id,
    }).split(":", 1)[1]


def request_identity_address(*, owner_id: str, request_id: str) -> str:
    return "sha256:" + operation_id_for_request(owner_id=owner_id, request_id=request_id)


def _whole_utc(value: Any) -> str:
    if not isinstance(value, str):
        raise V2OperationRefusal("V2_OPERATION_INVALID", "dataset_as_of is invalid")
    try:
        instant = dt.datetime.fromisoformat(value)
    except ValueError:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "dataset_as_of is invalid") from None
    if instant.tzinfo is None or instant.utcoffset() != dt.timedelta(0) \
            or instant.microsecond or instant.isoformat() != value:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "dataset_as_of is invalid")
    return value


def _validate_phase4(binding: Any) -> dict[str, Any]:
    if not isinstance(binding, Mapping) or set(binding) != _PHASE4_FIELDS:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "phase4 binding is open or incomplete")
    value = _plain(binding)
    if value["mode"] != "RESEARCH" or not isinstance(value["owner_id"], str) \
            or not value["owner_id"]:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "phase4 binding is not RESEARCH")
    for name in _PHASE4_FIELDS - {"owner_id", "mode", "declaration_addresses"}:
        _address(value[name], f"phase4 {name}")
    declarations = value["declaration_addresses"]
    if not isinstance(declarations, list) or declarations != sorted(set(declarations)) \
            or not declarations:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "declaration addresses are invalid")
    for address in declarations:
        _address(address, "declaration address")
    return value


def _validate_experiment(experiment: Any) -> dict[str, Any]:
    if not isinstance(experiment, Mapping) or set(experiment) != _EXPERIMENT_FIELDS:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "experiment is open or incomplete")
    value = _plain(experiment)
    hypothesis = value["hypothesis"]
    capital = value["research_capital"]
    fraction = value["min_positive_fold_frac"]
    if (not isinstance(hypothesis, str) or not hypothesis.strip() or len(hypothesis) > 4000
            or not isinstance(capital, (int, float)) or isinstance(capital, bool)
            or not math.isfinite(float(capital)) or not 0 < float(capital) <= 1_000_000_000
            or type(value["seed"]) is not int or not 0 <= value["seed"] <= 2_147_483_647
            or type(value["min_trades"]) is not int or not 1 <= value["min_trades"] <= 100_000
            or type(value["n_folds"]) is not int or not 2 <= value["n_folds"] <= 32
            or not isinstance(fraction, (int, float)) or isinstance(fraction, bool)
            or not math.isfinite(float(fraction)) or not 0 <= float(fraction) <= 1):
        raise V2OperationRefusal("V2_OPERATION_INVALID", "experiment values are invalid")
    return value


def _validate_item(item: Any, *, descriptor_present: bool) -> dict[str, Any]:
    expected = _ITEM_FIELDS if descriptor_present else _ITEM_FIELDS - {
        "adapter_policy_address", "descriptor_address", "request_identity_address",
        "resource_policy_address", "runtime_contract_addresses",
    }
    if not isinstance(item, Mapping) or set(item) not in (expected, expected | {"robustness"}):
        raise V2OperationRefusal("V2_OPERATION_INVALID", "V2 operation item is open or incomplete")
    value = _plain(item)
    if "robustness" in value:
        from research.robustness.parameter_integration import (
            ParameterNeighborhoodIntegrationRejected,
            parameter_neighborhood_recipe_binding,
        )
        robustness = value["robustness"]
        if not isinstance(robustness, Mapping) or set(robustness) != _ROBUSTNESS_FIELDS:
            raise V2OperationRefusal(
                "V2_OPERATION_INVALID", "V2 robustness request is open or incomplete",
            )
        try:
            parameter_neighborhood_recipe_binding(robustness["parameter_neighborhood"])
        except ParameterNeighborhoodIntegrationRejected as exc:
            raise V2OperationRefusal("V2_OPERATION_INVALID", str(exc)) from exc
    for name in ("project_id", "graph_identifier"):
        if not isinstance(value[name], str) or _ID.fullmatch(value[name]) is None:
            raise V2OperationRefusal("V2_OPERATION_INVALID", f"{name} is invalid")
    if type(value["graph_version"]) is not int or value["graph_version"] < 1:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "graph_version is invalid")
    for name in ("content_address", "graph_address", "admission_address",
                 "dataset_manifest_address"):
        _address(value[name], name)
    _request_id(value["request_id"])
    _whole_utc(value["dataset_as_of"])
    phase4 = _validate_phase4(value["phase4_binding"])
    _validate_experiment(value["experiment"])
    if phase4["owner_id"] == "":
        raise V2OperationRefusal("V2_OPERATION_INVALID", "phase4 owner is invalid")
    if (phase4["dataset_manifest_address"] != value["dataset_manifest_address"]
            or phase4["authored_ir_address"] != value["content_address"]
            or phase4["resolved_graph_address"] == value["graph_address"]):
        # Authored and resolved identities are deliberately distinct facts.
        raise V2OperationRefusal("V2_OPERATION_INVALID", "version or manifest binding differs")
    if descriptor_present:
        if value["adapter_policy_address"] != ADAPTER_POLICY_ADDRESS \
                or value["resource_policy_address"] != V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS \
                or value["runtime_contract_addresses"] != _plain(RUNTIME_CONTRACT_ADDRESSES):
            raise V2OperationRefusal("V2_OPERATION_INVALID", "runtime contract address is stale")
        expected_request = request_identity_address(
            owner_id=phase4["owner_id"], request_id=value["request_id"])
        if value["request_identity_address"] != expected_request:
            raise V2OperationRefusal("V2_OPERATION_INVALID", "request identity differs")
        _address(value["descriptor_address"], "descriptor address")
        if value["descriptor_address"] != content_address({
            key: value[key] for key in sorted(value) if key != "descriptor_address"
        }):
            raise V2OperationRefusal("V2_OPERATION_INVALID", "descriptor address is stale")
    return value


def build_v2_operation_plan(item: Mapping[str, Any]) -> dict[str, Any]:
    value = _validate_item(item, descriptor_present=False)
    phase4 = value["phase4_binding"]
    complete = {
        **value,
        "adapter_policy_address": ADAPTER_POLICY_ADDRESS,
        "request_identity_address": request_identity_address(
            owner_id=phase4["owner_id"], request_id=value["request_id"]),
        "resource_policy_address": V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS,
        "runtime_contract_addresses": _plain(RUNTIME_CONTRACT_ADDRESSES),
    }
    complete["descriptor_address"] = content_address(complete)
    plan_identity = {
        "schema": V2_OPERATION_SCHEMA, "experiment_count": 1,
        "v2_graphs": [complete],
    }
    plan = {**plan_identity, "content_address": content_address(plan_identity)}
    return parse_v2_operation_plan(plan)


def parse_v2_operation_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or set(plan) != {
        "content_address", "experiment_count", "schema", "v2_graphs"
    } or plan.get("schema") != V2_OPERATION_SCHEMA or plan.get("experiment_count") != 1 \
            or not isinstance(plan.get("v2_graphs"), list) or len(plan["v2_graphs"]) != 1:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "V2 operation plan is open or incomplete")
    value = _plain(plan)
    value["v2_graphs"][0] = _validate_item(value["v2_graphs"][0], descriptor_present=True)
    expected = content_address({
        "schema": V2_OPERATION_SCHEMA, "experiment_count": 1,
        "v2_graphs": value["v2_graphs"],
    })
    if value["content_address"] != expected:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "V2 operation plan address is stale")
    if len(canonical_json(value).encode("utf-8")) > _PLAN_LIMIT:
        raise V2OperationRefusal("V2_OPERATION_INVALID", "V2 operation plan exceeds 65536 bytes")
    return value


class DurableClaimCancellationToken:
    """Phase 5 token whose every event observes the durable operation fence."""

    def __init__(self, claim_guard: Callable[[], None]) -> None:
        if not callable(claim_guard):
            raise V2OperationRefusal("V2_OPERATION_INVALID", "claim guard is absent")
        self._claim_guard = claim_guard
        self.observed_events = 0
        self.cancelled = False

    def observe(self) -> bool:
        try:
            self._claim_guard()
        except RuntimeError:
            self.cancelled = True
            return False
        self.observed_events += 1
        return True


def _validate_position_indexes(availability_index, bar_open_index):
    import pandas as pd
    indexes = (availability_index, bar_open_index)
    if any(not isinstance(index, pd.DatetimeIndex) for index in indexes):
        raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")
    if any(not index.is_unique or not index.is_monotonic_increasing for index in indexes):
        raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")
    if len(availability_index) != len(bar_open_index):
        raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")


class _BarOpenPositionProjectionStrategy:
    """Transfer only frozen adapter flags onto the verified bar-open positions."""

    default_params: dict[str, Any] = {}
    risk_model = None

    def __init__(self, adapter: Any, *, manifest_address: str,
                 availability_index: Any, bar_open_index: Any,
                 position_map_address: str, declared_warmup: int | None = None,
                 slippage_pct: float | None = None) -> None:
        _validate_position_indexes(availability_index, bar_open_index)
        expected = content_address({
            "schema": "bar-open-position-map/1",
            "dataset_manifest_address": manifest_address,
            "availability_index": [item.isoformat() for item in availability_index],
            "bar_open_index": [item.isoformat() for item in bar_open_index],
        })
        if position_map_address != expected:
            raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")
        self._adapter = adapter
        self._availability = availability_index.copy()
        self._bar_open = bar_open_index.copy()
        self.position_map_address = position_map_address
        self.time_projection_algorithm_address = TIME_PROJECTION_ALGORITHM_ADDRESS
        self.key = adapter.key
        self.display_name = adapter.display_name
        self.declared_warmup = (
            adapter.declared_warmup if declared_warmup is None else declared_warmup
        )
        self.adapter_address = adapter.adapter_address
        self.adapter_policy_address = adapter.adapter_policy_address
        self.protective_band_document = getattr(adapter, "protective_band_document", None)
        self.replay_slippage_pct = slippage_pct
        self.replay_policy = getattr(adapter, "replay_policy", None)
        self.risk_model = getattr(adapter, "risk_model", None)
        self.risk_atr_seed_policy = getattr(adapter, "risk_atr_seed_policy", "first_observation")

    def signals(self, frame: Any, **overrides: Any):
        import pandas as pd
        from app.strategy.registry.base import CANONICAL_COLUMNS

        if overrides or not isinstance(frame, pd.DataFrame) or "date" not in frame:
            raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")
        observed = pd.DatetimeIndex(frame["date"])
        if not observed.equals(self._bar_open) or len(frame) != len(self._availability):
            raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")
        evaluation_frame = frame.copy(deep=True)
        evaluation_frame["date"] = self._availability
        evaluated = self._adapter.signals(evaluation_frame)
        if (len(evaluated) != len(frame)
                or not pd.DatetimeIndex(evaluated["date"]).equals(self._availability)):
            raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")
        projected = frame.copy(deep=True)
        for column in CANONICAL_COLUMNS:
            values = evaluated[column]
            if values.dtype != bool or len(values) != len(projected):
                raise V2OperationRefusal("V2_TIME_PROJECTION_MISMATCH")
            projected[column] = values.to_numpy(copy=True)
        return projected


def _input_set_graph_fields(document, datasets):
    inputs = document.get("graph_inputs")
    if not isinstance(inputs, (tuple, list)) or not all(isinstance(row, Mapping) for row in inputs):
        raise V2OperationRefusal("V2_GRAPH_INPUT_UNSUPPORTED")
    names = [row.get("port_id") for row in inputs]
    if len(set(names)) != len(names) or set(names) != set(datasets):
        raise V2OperationRefusal("V2_GRAPH_INPUT_UNSUPPORTED", "Select one dataset for each saved graph input.")
    # Project actual source fields; the canonical binder determines each node's requirements.
    return {name: tuple(dataset._verified_authority.manifest.fields) for name, dataset in sorted(datasets.items())}


def _load_input_set_projection(descriptor, document, execution_session, research_session):
    from types import SimpleNamespace
    from research.data.canonical_dataset import load_canonical_datasets, project_verified_research_input_set
    owner_id = descriptor.get("owner_id") or descriptor["phase4_binding"]["owner_id"]
    as_of = dt.datetime.fromisoformat(descriptor["dataset_as_of"])
    selections = [SimpleNamespace(manifest_address=row["dataset_manifest_address"], as_of=as_of)
                  for row in descriptor["input_datasets"]]
    loaded = load_canonical_datasets(research_session, execution_session=execution_session,
        owner_id=owner_id, selections=selections, now=as_of)
    by_address = {dataset.content_hash: (instrument, dataset) for instrument, dataset in loaded}
    datasets = {row["graph_input_id"]: by_address[row["dataset_manifest_address"]][1]
                for row in descriptor["input_datasets"]}
    projection = project_verified_research_input_set(datasets, owner_id=owner_id,
        primary_input=descriptor["primary_input"], graph_input_fields=_input_set_graph_fields(document, datasets))
    primary = datasets[descriptor["primary_input"]]
    if primary.binding["instrument"]["asset_class"] != "EQUITY":
        raise V2OperationRefusal("V2_PRIMARY_INPUT_UNSUPPORTED", "Select an equity dataset as the strategy's execution input; index data can be an observation input.")
    return by_address[primary.content_hash][0], primary, projection


def _projection_resource_admission(resource_plan, canonical, projection, operation_plan, repository, owner_id):
    from research.evaluation.v2_resource_policy import admit_v0_v2_research_resource_plan, admit_v0_v2_input_set_resource_plan
    admission = admit_v0_v2_research_resource_plan
    dimensions = dict(manifest_count=1, total_rows=canonical.bar_count,
                      total_bytes=projection.manifest.aggregate_byte_length)
    if projection.input_sources is not None:
        sources = tuple(projection.input_sources.values())
        admission = admit_v0_v2_input_set_resource_plan
        dimensions = dict(manifest_count=len({source.manifest.manifest_address for source in sources}),
            total_rows=sum(segment.row_end - segment.row_start for source in sources for segment in source.segments),
            total_bytes=sum(source.manifest.aggregate_byte_length for source in sources))
    return admission(resource_plan, **dimensions, maximum_events=len(projection.availability_index),
        items_per_operation=1, running_v2_operations_per_owner=repository.running_v2_count(owner_id=owner_id),
        plan_bytes=len(canonical_json(operation_plan).encode("utf-8")))


def _research_policy(document):
    from research.evaluation.phase5_runtime import research_evaluation_policy, research_input_set_evaluation_policy
    parser = research_input_set_evaluation_policy if document["schema"] == "research-evaluation-policy/2" else research_evaluation_policy
    return parser(document)


def _graph_input_fields(document: Mapping[str, Any], registry: Any) -> dict[str, tuple[str, ...]]:
    from app.ir.resolve import resolve_v2
    inputs = document.get("graph_inputs")
    if not isinstance(inputs, (tuple, list)) or len(inputs) != 1 \
            or not isinstance(inputs[0], Mapping) or inputs[0].get("port_id") != "frame":
        raise V2OperationRefusal(
            "V2_GRAPH_INPUT_UNSUPPORTED",
            "the initial saved V2 research subset requires one frame graph input",
        )
    # Compound presets carry requirements on their resolved members, not the
    # presentation node. Use the same expansion as evaluation and admission.
    fields = _resolved_market_fields(resolve_v2(document, registry), registry)
    if not fields:
        raise V2OperationRefusal("V2_GRAPH_INPUT_UNSUPPORTED", "graph has no primary market fields")
    return {"frame": tuple(fields)}


def _resolved_market_fields(graph: Any, registry: Any) -> list[str]:
    fields: set[str] = set()
    for node in graph.nodes:
        contract = registry.node_contracts.get(node.component, {})
        for field in contract.get("required_market_fields", ()):
            if isinstance(field, str) and "." not in field:
                fields.add(field.upper())
    return sorted(fields)


def _verify_version_and_admission(
    descriptor: Mapping[str, Any], *, execution_session,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reload exact V2 version plus closed Phase 4 descriptor before data bytes."""
    from app.core import strategy_admissions
    from app.editor import v2_editor_store
    from app.ir.v2_graph_versions import V2GraphVerificationError

    owner_id = descriptor["phase4_binding"]["owner_id"]
    try:
        version = v2_editor_store.read_version(
            descriptor["project_id"], descriptor["graph_identifier"],
            descriptor["graph_version"], owner_id=owner_id,
        )
        admission = strategy_admissions.load_phase4_descriptor(
            execution_session, owner_id=owner_id,
            admission_address=descriptor["admission_address"],
        )
    except (v2_editor_store.EditorNotFound, V2GraphVerificationError,
            strategy_admissions.AdmissionPersistenceError) as exc:
        raise V2OperationRefusal("V2_AUTHORITY_UNAVAILABLE", "saved V2 authority is unavailable") from exc
    binding = admission["phase4_data_binding"]
    base = admission["base_v2_admission"]
    expected = (
        version.get("format_version") == 2,
        version.get("graph_identifier") == descriptor["graph_identifier"],
        version.get("graph_version") == descriptor["graph_version"],
        version.get("content_address") == descriptor["content_address"],
        version.get("graph_address") == descriptor["graph_address"],
        version.get("registry_snapshot_address") == binding["registry_snapshot_address"],
        admission["owner_id"] == owner_id,
        content_address(admission) == descriptor["admission_address"],
        admission["graph_identifier"] == descriptor["graph_identifier"],
        admission["graph_version"] == descriptor["graph_version"],
        admission["content_address"] == descriptor["content_address"],
        admission["graph_address"] == descriptor["graph_address"],
        binding == descriptor["phase4_binding"],
        binding["mode"] == "RESEARCH",
        binding["dataset_manifest_address"] == descriptor["dataset_manifest_address"],
        canonical_json(version.get("document")) == canonical_json(
            base["document"]),
    )
    if not all(expected):
        raise V2OperationRefusal("V2_AUTHORITY_MISMATCH", "saved V2 version/admission binding differs")
    return version, admission


def _evaluation_policy_document(
    *, owner_id: str, manifest: Any, projection: Any, resolved: Any,
    resource_plan: Any, run_authority_address: str,
) -> dict[str, Any]:
    from app.ir.library import REGISTRY
    from research.evaluation.phase5_runtime import NODE_CONTEXT_RESOLVER_ADDRESS

    document = {
        "schema": "research-evaluation-policy/1", "owner_id": owner_id,
        "mode": "RESEARCH", "dataset_manifest_address": manifest.manifest_address,
        "dataset_input_digest": projection.input_digest,
        "input_derivation_address": projection.derivation_address,
        "node_context_resolver_address": NODE_CONTEXT_RESOLVER_ADDRESS,
        "resolved_graph_address": resolved.resolved_graph_address,
        "registry_snapshot_address": REGISTRY.registry_snapshot_address,
        "implementation_closure_address": resolved.implementation_closure_address,
        "resource_plan_address": resource_plan.plan_address,
        "truth_snapshot_addresses": list(manifest.truth_snapshot_addresses),
        "adjustment_policy_address": manifest.adjustment_policy_address,
        "session_policy_address": projection.session_policy_address,
        "resampling_policy_address": projection.resampling_policy_address,
        "missing_data_policy_address": manifest.missing_data_policy_address,
        "alignment_policy_address": manifest.alignment_policy_address,
        "run_authority_address": run_authority_address,
        "input_bindings": _plain(projection.policy_input_bindings),
        "event_kind": "completed_bar",
        "event_start": projection.availability_index[0].isoformat(),
        "event_end": projection.evaluation_window[1].isoformat(),
        "maximum_events": len(projection.availability_index),
        "cancellation_check_interval": 1,
    }
    if projection.input_sources is not None:
        from research.evaluation.phase5_runtime import input_set_policy_fields
        document.update(input_set_policy_fields(projection))
    document["evaluation_policy_address"] = content_address(document)
    return document


def _adapter_settings(descriptor):
    if "execution_policy" not in descriptor:
        return {}
    from research.orchestrator.v2_preparation import protective_percentages
    policy = descriptor["execution_policy"]
    return {**protective_percentages(policy["risk"]), "policy_address": policy["adapter_policy_address"],
            "risk_policy": policy["risk"]["risk_policy"]}


def _canonical_search_options(prepared, evaluator):
    from research.pipeline.v2_parameter_search import SEARCH_SCHEMA
    return {"optimize_search": prepared is not None,
            "optimizer_version": SEARCH_SCHEMA if prepared is not None else "none",
            "canonical_search": prepared,
            "canonical_candidate_evaluator": evaluator if prepared is not None else None}


def _pinned_replay_slippage(descriptor):
    """New settings bind the recorded round-trip fill spread; old snapshots keep their semantics."""
    policy = descriptor.get("execution_policy")
    if policy is None:
        return None
    modern_settings = descriptor.get("settings_snapshot", {}).get("schema") in {"research-settings-snapshot/2", "research-settings-snapshot/3"}
    if not modern_settings and policy["schema"] != "v2-research-execution-policy/2":
        return None
    return policy["slippage"]["basis_points"] / 10_000.0


def _cost_settings(descriptor):
    if "execution_policy" not in descriptor:
        return {}
    slippage = descriptor["execution_policy"]["slippage"]
    return {"slippage_bps": slippage["basis_points"],
            "slippage_multiplier": slippage["challenge_multiplier"]}


def execute_v2_graph_operation(
    *, operation: Any, recorder: Any, repository: Any,
    execution_session: Any, research_session: Any,
) -> dict[str, Any]:
    """Dispatch immutable admitted and public-preparation operation versions."""
    if operation.plan.get("schema") in {"v2-graph-research-operation/2", "v2-graph-research-operation/3", "v2-graph-research-operation/4"}:
        from research.orchestrator.v2_preparation import prepare_operation
        descriptor = prepare_operation(operation=operation, recorder=recorder,
            repository=repository, execution_session=execution_session,
            research_session=research_session)
    else:
        descriptor = parse_v2_operation_plan(operation.plan)["v2_graphs"][0]
    return _execute_admitted_operation(operation=operation, recorder=recorder,
        repository=repository, execution_session=execution_session,
        research_session=research_session, descriptor=descriptor)


def _verify_operation_identity(operation, descriptor):
    owner_id = descriptor["phase4_binding"]["owner_id"]
    if (operation.trigger != V2_OPERATION_TRIGGER
            or operation.provider_mode != V2_PROVIDER_MODE
            or operation.operation_id != operation_id_for_request(owner_id=owner_id, request_id=descriptor["request_id"])):
        raise V2OperationRefusal("V2_OPERATION_IDENTITY_MISMATCH")
    return owner_id


def _refuse_bound_operation(operation, recorder, repository, owner_id, item_key):
    if repository.bound_item_run(operation.operation_id, owner_id=owner_id, item_key=item_key) is not None:
        repository.fail_bound_v2_replay(operation.operation_id, owner_id=owner_id,
                                      token=recorder.token, item_key=item_key)
        raise V2OperationRefusal("V2_BOUND_RUN_REPLAY_REFUSED", "bound V2 research run cannot be replayed")


def _one_dataset(datasets):
    if len(datasets) != 1:
        raise V2OperationRefusal("V2_DATASET_MISMATCH")
    return datasets[0]


def _load_admitted_artifact(descriptor, admission, projection, execution_session, research_session):
    from app.core import strategy_admissions
    from app.ir.library import REGISTRY
    try:
        loader = strategy_admissions.load_current_phase4_artifact
        arguments = {"input_bindings": projection.input_bindings}
        if projection.input_sources is not None:
            loader = strategy_admissions.load_current_phase4_bound_artifact
            arguments = {"projection": projection, "at_time": dt.datetime.fromisoformat(descriptor["dataset_as_of"])}
        artifact = loader(execution_session,
            owner_id=descriptor["phase4_binding"]["owner_id"], admission_address=descriptor["admission_address"],
            registry=REGISTRY, research_session=research_session, **arguments)
    except strategy_admissions.AdmissionPersistenceError as exc:
        raise V2OperationRefusal("V2_AUTHORITY_MISMATCH", "saved V2 admission did not reconstruct") from exc
    if canonical_json(artifact.to_dict()) != canonical_json(admission):
        raise V2OperationRefusal("V2_AUTHORITY_MISMATCH")
    return artifact


def _resolve_admitted_plan(document, projection, binding):
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.market_data.requirements import compile_data_requirement_plan
    resolved = resolve_v2(document, REGISTRY)
    fields = ("authored_ir_address", "resolved_graph_address", "registry_snapshot_address", "implementation_closure_address")
    if any(getattr(resolved, field) != binding[field] for field in fields):
        raise V2OperationRefusal("V2_AUTHORITY_MISMATCH")
    plan = compile_data_requirement_plan(resolved, registry=REGISTRY, input_bindings=projection.input_bindings)
    if (plan.authored_ir_address != binding["authored_ir_address"]
            or plan.registry_snapshot_address != binding["registry_snapshot_address"]
            or tuple(plan.declaration_addresses) != tuple(binding["declaration_addresses"])):
        raise V2OperationRefusal("V2_DATA_PLAN_MISMATCH")
    return resolved, plan


def _check_admitted_assessment(execution_session, binding, artifact, as_of, owner_id):
    from app.market_data.authority import load_capability_assessment
    assessment = load_capability_assessment(execution_session, binding["capability_assessment_address"],
                                            plan=artifact.plan, at_time=as_of)
    expected = {"owner_id": owner_id, "mode": "RESEARCH", **{field: binding[field] for field in (
        "dataset_manifest_address", "plan_address", "registry_snapshot_address", "evaluation_policy_address")}}
    if any(getattr(assessment, field) != value for field, value in expected.items()):
        raise V2OperationRefusal("V2_CAPABILITY_MISMATCH")


def _candidate_commands(point):
    if not isinstance(point, tuple) or not point:
        raise V2OperationRefusal("V2_PARAMETER_CANDIDATE_INVALID")
    identities = tuple((row.get("node_id"), row.get("parameter_id")) for row in point if isinstance(row, Mapping))
    if len(identities) != len(point) or identities != tuple(sorted(set(identities))):
        raise V2OperationRefusal("V2_PARAMETER_CANDIDATE_INVALID")
    return [{"command": "set_parameter", "node_id": row["node_id"],
             "parameter_id": row["parameter_id"], "value": row["value"]} for row in point]


def _operation_projection(descriptor, document, execution_session, research_session):
    if "input_datasets" in descriptor:
        return _load_input_set_projection(descriptor, document, execution_session, research_session)
    from types import SimpleNamespace
    from app.ir.library import REGISTRY
    from research.data.canonical_dataset import load_canonical_datasets, project_verified_research_inputs
    as_of = dt.datetime.fromisoformat(descriptor["dataset_as_of"])
    datasets = load_canonical_datasets(research_session, execution_session=execution_session,
        owner_id=descriptor["phase4_binding"]["owner_id"], now=as_of,
        selections=[SimpleNamespace(manifest_address=descriptor["dataset_manifest_address"], as_of=as_of)])
    instrument, canonical = _one_dataset(datasets)
    projection = project_verified_research_inputs(canonical, owner_id=descriptor["phase4_binding"]["owner_id"],
        graph_input_fields=_graph_input_fields(document, REGISTRY))
    return instrument, canonical, projection


def _operation_eligibility(descriptor, document, projection, resolved, data_plan,
                           evaluation_policy_address, execution_session):
    if projection.input_sources is not None:
        from research.orchestrator.v2_preparation import bound_projection_eligibility
        return bound_projection_eligibility(descriptor, document, projection, resolved, data_plan,
                                             evaluation_policy_address, execution_session)
    return _scalar_operation_eligibility(descriptor, document, projection, resolved, data_plan, execution_session)


def _eligibility_interval(start, end, warmup_seconds):
    requested_start = start + dt.timedelta(seconds=warmup_seconds)
    if requested_start >= end:
        raise V2OperationRefusal("V2_DATASET_INELIGIBLE",
            "No evaluation interval remains after the strategy's lookback and warmup. "
            "Use more matching history, or shorten the lookback and save a new strategy version.")
    return requested_start, end


def _scalar_operation_eligibility(descriptor, document, projection, resolved, data_plan, execution_session):
    from app.ir.library import REGISTRY
    from app.ir.v2_graph_versions import V2GraphFacts
    from app.market_data.authority import load_capability_profile, load_provider_conformance
    from app.market_data.eligibility import EligibilityRequest, SelectedDataset, compile_graph_data_eligibility
    from app.market_truth.identity import load_canonical_instrument, load_provider_identity
    manifest = projection.manifest
    as_of = dt.datetime.fromisoformat(descriptor["dataset_as_of"])
    profile = load_capability_profile(execution_session, manifest.capability_profile_address, at_time=as_of)
    conformance = load_provider_conformance(execution_session, profile.conformance_evidence_address)
    _, _, contract = load_provider_identity(execution_session, profile.provider_contract_address)
    physical = load_canonical_instrument(execution_session, manifest.instrument_addresses[0])
    authored = {"identity_scheme_version": 1, "graph": {key: document[key]
        for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}}
    facts = V2GraphFacts(manifest.owner_id, descriptor["graph_identifier"], descriptor["graph_version"],
        canonical_json(document), 2, content_address(document), content_address(authored), data_plan.registry_snapshot_address)
    warmup = max((row["requirement"]["history"]["minimum_bars"] + row["requirement"]["history"]["warmup_bars"])
                 * row["requirement"]["timeframe"] for row in data_plan.requirements)
    start = dt.datetime.fromisoformat(manifest.event_start)
    requested_start, requested_end = _eligibility_interval(start, dt.datetime.fromisoformat(manifest.event_end), warmup)
    return compile_graph_data_eligibility(request=EligibilityRequest(manifest.owner_id, "RESEARCH",
        requested_start, requested_end, as_of),
        graph=facts, resolved_graph=resolved, plan=data_plan, input_bindings=projection.input_bindings,
        datasets=(SelectedDataset(manifest, projection.segment_objects, physical),),
        profile=profile, conformance=conformance, provider_contract=contract, registry=REGISTRY)


def _verify_candidate_data_universe(candidate, baseline, projection, registry):
    if projection.input_sources is not None:
        unchanged = canonical_json(candidate["graph_inputs"]) == canonical_json(baseline["graph_inputs"])
    else:
        unchanged = _graph_input_fields(candidate, registry) == _graph_input_fields(baseline, registry)
    if not unchanged:
        raise V2OperationRefusal("V2_PARAMETER_DATA_UNIVERSE_CHANGED")


def _input_set_lineage(projection, result):
    if projection.input_sources is None:
        return {}
    return {"dataset_selection_address": projection.dataset_selection_address,
            "dataset_selection": _plain(projection.dataset_selection_document),
            "primary_input": projection.primary_input,
            "input_set_position_map_address": projection.position_map_address,
            "source_policies": _plain(result.document["source_policies"])}


def _execution_position_map(projection):
    source = projection if projection.input_sources is None else projection.input_sources[projection.primary_input]
    return source.position_map_address


def _execute_admitted_operation(
    *, operation: Any, recorder: Any, repository: Any,
    execution_session: Any, research_session: Any, descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    """Run a verified descriptor without replacing its durable operation identity."""
    from app.ir.incremental_runtime import accept_research_resource_plan
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.market_data.requirements import compile_data_requirement_plan
    from research.evaluation.phase5_runtime import execute_research
    from research.orchestrator.run import run_experiment
    from research.robustness.parameter_integration import (
        CandidateEvaluationCancelled,
        CandidateRuntime,
        parameter_neighborhood_recipe_binding,
        prepare_parameter_neighborhood,
    )
    from research.strategy.v2_runtime_strategy import V2RuntimeStrategy
    from sqlalchemy.orm import Session

    plan = operation.plan
    owner_id = _verify_operation_identity(operation, descriptor)
    item_key = f"v2_graph:000:{descriptor['descriptor_address'].split(':', 1)[1][:32]}"

    def durable_fence() -> None:
        recorder.assert_claim()
        with Session(bind=research_session.get_bind()) as fence_session:
            from research.domain.operations import ResearchOperationRepository
            if not ResearchOperationRepository(fence_session).claim_active(
                    operation.operation_id, owner_id=owner_id, token=recorder.token):
                raise RuntimeError("research operation claim was lost")

    _refuse_bound_operation(operation, recorder, repository, owner_id, item_key)

    durable_fence()  # before version/admission authority load
    version, admission = _verify_version_and_admission(
        descriptor, execution_session=execution_session,
    )
    parameter_recipe = parameter_neighborhood_recipe_binding(
        descriptor.get("robustness", {}).get("parameter_neighborhood")
        if "robustness" in descriptor else None
    )
    parameter_prepared = prepare_parameter_neighborhood(
        parameter_recipe, baseline_document=version["document"], registry=REGISTRY,
    )
    from research.pipeline.v2_parameter_search import prepare_canonical_search
    canonical_search = prepare_canonical_search(
        descriptor.get("settings_snapshot", {}).get("values", {}).get("optimization"),
        document=version["document"], registry=REGISTRY)
    durable_fence()  # after authority, before data-object load
    as_of = dt.datetime.fromisoformat(descriptor["dataset_as_of"])
    instrument, canonical, projection = _operation_projection(
        descriptor, version["document"], execution_session, research_session)
    durable_fence()  # after all selected data objects and source clocks reconstruct
    artifact = _load_admitted_artifact(descriptor, admission, projection, execution_session, research_session)
    binding = descriptor["phase4_binding"]
    resolved, data_plan = _resolve_admitted_plan(version["document"], projection, binding)

    manifest = projection.manifest
    if projection.input_sources is None:
        _check_admitted_assessment(execution_session, binding, artifact, as_of, owner_id)
    resource_plan = accept_research_resource_plan(
        resolved, data_plan, REGISTRY, input_bindings=projection.input_bindings,
        queue_concurrency_upper_bound=1,
    )
    resource_admission = _projection_resource_admission(
        resource_plan, canonical, projection, plan, repository, owner_id)
    run_authority_address = content_address({
        "schema": "v2-research-operation-run-authority/1",
        "operation_id": operation.operation_id,
        "descriptor_address": descriptor["descriptor_address"],
    })
    policy_document = _evaluation_policy_document(
        owner_id=owner_id, manifest=manifest, projection=projection,
        resolved=resolved, resource_plan=resource_plan,
        run_authority_address=run_authority_address,
    )
    policy = _research_policy(policy_document)
    eligibility = _operation_eligibility(descriptor, version["document"], projection,
        resolved, data_plan, policy.policy_address, execution_session)
    if eligibility.status != "SUPPORTED":
        raise V2OperationRefusal("V2_DATASET_INELIGIBLE")
    durable_fence()  # before evaluation
    result = execute_research(
        resolved, REGISTRY, resource_plan, projection, policy,
        cancellation=DurableClaimCancellationToken(durable_fence),
    )
    if result.document["status"] != "COMPLETED":
        raise V2OperationRefusal("V2_OPERATION_CANCELLED")
    durable_fence()  # after evaluation, before experiment writes
    adapter = V2RuntimeStrategy(
        version["document"], result, projection.availability_index,
        **_adapter_settings(descriptor),
    )
    position_map_address = _execution_position_map(projection)
    strategy = _BarOpenPositionProjectionStrategy(
        adapter, manifest_address=manifest.manifest_address,
        availability_index=projection.availability_index,
        bar_open_index=projection.bar_open_index,
        position_map_address=position_map_address,
        slippage_pct=_pinned_replay_slippage(descriptor),
    )

    def evaluate_parameter_candidate(
        point: tuple[Mapping[str, Any], ...],
    ) -> CandidateRuntime:
        """Narrow one operation's verified authorities to one ephemeral point."""
        from app.editor.v2_mutations import apply_semantic_commands

        commands = _candidate_commands(point)
        durable_fence()
        baseline_bytes = canonical_json(version["document"])
        mutation = apply_semantic_commands(
            version["document"], commands, registry=REGISTRY,
        )
        if canonical_json(version["document"]) != baseline_bytes:
            raise V2OperationRefusal("V2_PARAMETER_BASELINE_MUTATED")
        candidate_resolved = resolve_v2(mutation.document, REGISTRY)
        _verify_candidate_data_universe(mutation.document, version["document"], projection, REGISTRY)
        candidate_data_plan = compile_data_requirement_plan(
            candidate_resolved, registry=REGISTRY,
            input_bindings=projection.input_bindings,
        )
        if candidate_data_plan.registry_snapshot_address != binding["registry_snapshot_address"] \
                or candidate_data_plan.authored_ir_address != mutation.content_address:
            raise V2OperationRefusal("V2_PARAMETER_DATA_PLAN_MISMATCH")
        candidate_resource_plan = accept_research_resource_plan(
            candidate_resolved, candidate_data_plan, REGISTRY,
            input_bindings=projection.input_bindings,
            queue_concurrency_upper_bound=1,
        )
        candidate_resource_admission = _projection_resource_admission(
            candidate_resource_plan, canonical, projection, plan, repository, owner_id)
        candidate_run_authority = content_address({
            "schema": "v2-parameter-candidate-run-authority/1",
            "operation_id": operation.operation_id,
            "descriptor_address": descriptor["descriptor_address"],
            "candidate_graph_address": mutation.graph_address,
            "point": _plain(point),
        })
        candidate_policy = _research_policy(_evaluation_policy_document(
            owner_id=owner_id, manifest=manifest, projection=projection,
            resolved=candidate_resolved, resource_plan=candidate_resource_plan,
            run_authority_address=candidate_run_authority,
        ))
        candidate_eligibility = _operation_eligibility(descriptor, mutation.document, projection,
            candidate_resolved, candidate_data_plan, candidate_policy.policy_address, execution_session)
        if candidate_eligibility.status != "SUPPORTED":
            raise V2OperationRefusal("V2_PARAMETER_DATASET_INELIGIBLE")
        durable_fence()
        candidate_result = execute_research(
            candidate_resolved, REGISTRY, candidate_resource_plan, projection,
            candidate_policy,
            cancellation=DurableClaimCancellationToken(durable_fence),
        )
        if candidate_result.document["status"] != "COMPLETED":
            raise CandidateEvaluationCancelled("V2_OPERATION_CANCELLED")
        candidate_adapter = V2RuntimeStrategy(
            mutation.document, candidate_result, projection.availability_index,
            **_adapter_settings(descriptor),
        )
        candidate_strategy = _BarOpenPositionProjectionStrategy(
            candidate_adapter, manifest_address=manifest.manifest_address,
            availability_index=projection.availability_index,
            bar_open_index=projection.bar_open_index,
            position_map_address=position_map_address,
            declared_warmup=adapter.declared_warmup,
            slippage_pct=_pinned_replay_slippage(descriptor),
        )
        durable_fence()
        return CandidateRuntime(
            strategy=candidate_strategy,
            candidate_graph_address=mutation.graph_address,
            lineage={
                **_input_set_lineage(projection, candidate_result),
                "content_address": mutation.content_address,
                "graph_address": mutation.graph_address,
                "resolved_graph_address": candidate_resolved.resolved_graph_address,
                "registry_snapshot_address": REGISTRY.registry_snapshot_address,
                "data_requirement_plan_address": candidate_data_plan.plan_address,
                "eligibility_address": candidate_eligibility.eligibility_address,
                "resource_plan_address": candidate_resource_plan.plan_address,
                "resource_admission_address": candidate_resource_admission.admission_address,
                "resource_policy_address": candidate_resource_admission.resource_policy_address,
                "evaluation_policy_address": candidate_policy.policy_address,
                "research_result_address": candidate_result.result_address,
                "research_output_digest": candidate_result.document["output_digest"],
                "adapter_address": candidate_adapter.adapter_address,
                "adapter_policy_address": candidate_adapter.adapter_policy_address,
                "position_map_address": position_map_address,
                "time_projection_algorithm_address": TIME_PROJECTION_ALGORITHM_ADDRESS,
            },
        )
    runtime_lineage = {
        **_input_set_lineage(projection, result),
        "runtime_contract_addresses": descriptor["runtime_contract_addresses"],
        "input_digest": projection.input_digest,
        "input_derivation_address": projection.derivation_address,
        "input_binding_context_address": projection.input_bindings.context_address,
        "data_requirement_plan_address": data_plan.plan_address,
        "eligibility_address": eligibility.eligibility_address,
        "resource_plan_address": resource_plan.plan_address,
        "resource_admission_address": resource_admission.admission_address,
        "resource_policy_address": resource_admission.resource_policy_address,
        "evaluation_policy_address": policy.policy_address,
        "research_result_address": result.result_address,
        "research_output_digest": result.document["output_digest"],
        "adapter_policy_address": adapter.adapter_policy_address,
        "adapter_address": adapter.adapter_address,
        "position_map_address": position_map_address,
        "time_projection_algorithm_address": TIME_PROJECTION_ALGORITHM_ADDRESS,
    }
    graph_provenance = {
        "schema": "saved-v2-graph-research-provenance/2" if projection.input_sources is not None else "saved-v2-graph-research-provenance/1",
        "operation_id": operation.operation_id,
        "request_id": descriptor["request_id"],
        "descriptor_address": descriptor["descriptor_address"],
        "graph": {
            "project_id": descriptor["project_id"], "format_version": 2,
            "identifier": descriptor["graph_identifier"],
            "version": descriptor["graph_version"],
            "content_address": descriptor["content_address"],
            "graph_address": descriptor["graph_address"],
        },
        "admission_address": descriptor["admission_address"],
        "phase4_binding": descriptor["phase4_binding"],
        "dataset_manifest_address": descriptor["dataset_manifest_address"],
        **runtime_lineage,
        **({"execution_policy": descriptor["execution_policy"]} if "execution_policy" in descriptor else {}),
    }
    experiment = descriptor["experiment"]
    return run_experiment(
        research_session, owner_id=owner_id,
        program_name="Saved V2 graph research",
        hypothesis_statement=experiment["hypothesis"], strategy=strategy,
        datasets=[(instrument, canonical)], params={}, git_commit=operation.build,
        seed=experiment["seed"], min_trades=experiment["min_trades"],
        n_folds=experiment["n_folds"],
        min_positive_fold_frac=experiment["min_positive_fold_frac"],
        capital=experiment["research_capital"],
        **_canonical_search_options(canonical_search, evaluate_parameter_candidate),
        **_cost_settings(descriptor),
        parameter_neighborhood=parameter_prepared,
        parameter_neighborhood_evaluator=(
            evaluate_parameter_candidate if parameter_prepared is not None else None
        ),
        graph_provenance=graph_provenance,
        bind_run=lambda run_id: recorder.bind_item_run_in_transaction(item_key, run_id),
        finalize_run=lambda run_id: recorder.finalize_v2_operation_in_transaction(
            item_key, run_id,
        ),
    )


__all__ = [
    "DurableClaimCancellationToken", "RUNTIME_CONTRACT_ADDRESSES",
    "TIME_PROJECTION_ALGORITHM_ADDRESS",
    "V2_OPERATION_SCHEMA", "V2_OPERATION_TRIGGER",
    "V2_PROVIDER_MODE", "V2OperationRefusal", "build_v2_operation_plan",
    "execute_v2_graph_operation", "operation_id_for_request", "parse_v2_operation_plan",
    "request_identity_address",
]
