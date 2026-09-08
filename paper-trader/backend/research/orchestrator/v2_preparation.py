"""Durable preparation of real, owner-scoped saved V2 research evidence."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.ir.hashing import canonical_json, content_address
from research.orchestrator.v2_operation import (
    V2OperationRefusal, _address, _plain, _request_id, _validate_experiment,
    _whole_utc, operation_id_for_request, _eligibility_interval,
)

PREPARATION_SCHEMA = "v2-graph-research-operation/2"
SETTINGS_PREPARATION_SCHEMA = "v2-graph-research-operation/3"
INPUT_SET_PREPARATION_SCHEMA = "v2-graph-research-operation/4"
EVIDENCE_SCHEMA = "v2-research-preparation-evidence/1"
INPUT_SET_EVIDENCE_SCHEMA = "v2-research-preparation-evidence/2"
MAX_EVIDENCE_BYTES = 262144
_FIELDS = {"owner_id", "project_id", "graph_identifier", "graph_version",
           "content_address", "graph_address", "registry_snapshot_address",
           "dataset_manifest_address", "dataset_as_of", "request_id", "experiment",
           "execution_policy", "resource_policy_address", "runtime_contract_addresses", "descriptor_address"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise V2OperationRefusal("V2_PREPARATION_INVALID", message)


def execution_policy(capital: float, risk_policy: str = "none", *, stop_loss_pct=0.0, take_profit_pct=0.0) -> dict[str, Any]:
    from app.engine.charges import CORRECTED_RESEARCH_CHARGE_SCHEDULE, charge_schedule_document
    from research.strategy.v2_runtime_strategy import DIRECTIONAL_ADAPTER_POLICY_ADDRESS, risk_policy_document
    _require(risk_policy in {"none", "pine-v4-ratchet/1", "pine-v4-reversal/1"}, "Choose a supported research risk policy.")
    from app.backtest.engine import protective_band_document
    band = protective_band_document(stop_loss_pct, take_profit_pct)
    policy = {
        "schema": "v2-research-execution-policy/2" if band else "v2-research-execution-policy/1",
        "adapter_policy_address": DIRECTIONAL_ADAPTER_POLICY_ADDRESS,
        "fee": charge_schedule_document(CORRECTED_RESEARCH_CHARGE_SCHEDULE),
        "slippage": {"schema": "research-slippage-assumption/1", "basis_points": 5.0,
                     "challenge_multiplier": 2.0, "application": "existing-research-kernel"},
        "risk": {"schema": "research-risk-assumption/1", "risk_policy": risk_policy,
                 "overlay": _plain(risk_policy_document(risk_policy)), "capital": capital,
                 "sizing_model": "fixed_unit_v1" if risk_policy == "pine-v4-reversal/1" else "one_lot_or_cash_budget_v1",
                 "fill": "next-bar-open-reversal/1" if risk_policy == "pine-v4-reversal/1" else "existing-next-bar-open"},
    }

    if band:
        policy["risk"] = {**policy["risk"], "schema": "research-risk-assumption/2", "protective_band": band}
    return policy


def protective_percentages(risk):
    band = risk.get("protective_band", {})
    _require(isinstance(band, dict), "Protective exit policy is invalid.")
    return {key: band.get(key, 0.0) for key in ("stop_loss_pct", "take_profit_pct")}


def _validate_descriptor(value: Mapping[str, Any], *, settings_snapshot=False, input_set=False) -> dict[str, Any]:
    fields = _FIELDS | {"settings_snapshot"} if settings_snapshot else _FIELDS
    if input_set:
        fields = fields - {"dataset_manifest_address"} | {"input_datasets", "primary_input"}
    _require(isinstance(value, Mapping) and set(value) == fields, "Preparation fields are incomplete.")
    item = _plain(value)
    _request_id(item["request_id"])
    _validate_experiment(item["experiment"])
    _whole_utc(item["dataset_as_of"])
    for key in ("owner_id", "project_id", "graph_identifier"):
        _require(isinstance(item[key], str) and 0 < len(item[key]) <= 128, "Saved strategy identity is invalid.")
    _require(type(item["graph_version"]) is int and item["graph_version"] > 0, "Select a saved version.")
    if input_set:
        _validate_input_datasets(item)
    _validate_descriptor_addresses(item, input_set=input_set)
    if settings_snapshot:
        _validate_settings_binding(item)
    return item


def _validate_input_datasets(item):
    rows = item["input_datasets"]
    _require(isinstance(rows, list) and 2 <= len(rows) <= 8, "Select between two and eight distinct datasets.")
    names, manifests = [], []
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {"graph_input_id", "dataset_manifest_address"},
                 "Each selected dataset must name one graph input.")
        name = row["graph_input_id"]
        _require(isinstance(name, str) and 0 < len(name) <= 128 and "\x00" not in name, "Graph input name is invalid.")
        names.append(name); manifests.append(_address(row["dataset_manifest_address"], "dataset manifest"))
    _require(names == sorted(set(names)) and len(set(manifests)) == len(rows), "Selected inputs or manifests are duplicated or unordered.")
    _require(isinstance(item["primary_input"], str) and item["primary_input"] in names,
             "Select the primary input from the selected datasets.")


def _validate_descriptor_addresses(item: dict[str, Any], *, input_set=False) -> None:
    keys = ("content_address", "graph_address", "registry_snapshot_address")
    for key in keys if input_set else (*keys, "dataset_manifest_address"):
        _address(item[key], key)
    policy = item["execution_policy"]
    _require(isinstance(policy, dict) and isinstance(policy.get("risk"), dict), "Research policy is invalid.")
    expected = execution_policy(item["experiment"]["research_capital"], policy["risk"].get("risk_policy"), **protective_percentages(policy["risk"]))
    _require(item["resource_policy_address"] == _resource_policy_address(input_set),
             "Research resource policy changed. Start a new request.")
    _require(item["runtime_contract_addresses"] == _runtime_contracts(expected, input_set=input_set), "Research runtime policy changed. Start a new request.")
    _require(policy == expected, "Research assumptions differ from the supported policy.")
    _require(item["descriptor_address"] == content_address({k: v for k, v in item.items() if k != "descriptor_address"}),
             "Preparation identity is stale.")


def _validate_settings_binding(item):
    from research.domain.settings import validate_snapshot
    try:
        snapshot = validate_snapshot(item["settings_snapshot"], owner_id=item["owner_id"],
                                     graph_identifier=item["graph_identifier"])
    except (ValueError, TypeError, KeyError) as exc:
        raise V2OperationRefusal("V2_SETTINGS_SNAPSHOT_INVALID", "The pinned research settings could not be reconstructed.") from exc
    values = snapshot["values"]
    expected = {**values, "hypothesis": item["experiment"]["hypothesis"]}
    expected.pop("optimization", None)
    risk = expected.pop("risk_policy")
    bands = {key: expected.pop(key, 0.0) for key in ("stop_loss_pct", "take_profit_pct")}
    _require(item["experiment"] == expected, "Research experiment differs from pinned settings.")
    _require(item["execution_policy"] == execution_policy(values["research_capital"], risk, **bands),
             "Research execution policy differs from pinned settings.")


def _resource_policy_address(input_set):
    from research.evaluation.v2_resource_policy import V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS, V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS
    return V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS if input_set else V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS


def _runtime_contracts(policy, *, input_set=False):
    from research.orchestrator.v2_operation import RUNTIME_CONTRACT_ADDRESSES, INPUT_SET_RUNTIME_CONTRACT_ADDRESSES
    contracts = INPUT_SET_RUNTIME_CONTRACT_ADDRESSES if input_set else RUNTIME_CONTRACT_ADDRESSES
    return {**_plain(contracts), "output_adaptation": policy["adapter_policy_address"]}


def build_preparation_plan(item: Mapping[str, Any]) -> dict[str, Any]:
    return _build_preparation_plan(item, PREPARATION_SCHEMA)


def build_settings_preparation_plan(item: Mapping[str, Any]) -> dict[str, Any]:
    return _build_preparation_plan(item, SETTINGS_PREPARATION_SCHEMA)


def build_input_set_preparation_plan(item: Mapping[str, Any]) -> dict[str, Any]:
    return _build_preparation_plan(item, INPUT_SET_PREPARATION_SCHEMA)


def _build_preparation_plan(item, schema):
    value = _plain(item)
    input_set = schema == INPUT_SET_PREPARATION_SCHEMA
    value["resource_policy_address"] = _resource_policy_address(input_set)
    value["runtime_contract_addresses"] = _runtime_contracts(value["execution_policy"], input_set=input_set)
    value["descriptor_address"] = content_address(value)
    plan = {"schema": schema, "experiment_count": 1, "v2_graphs": [value]}
    plan["content_address"] = content_address(plan)
    return parse_public_preparation_plan(plan)


def parse_preparation_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    return _parse_preparation_plan(plan, PREPARATION_SCHEMA)


def parse_settings_preparation_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    return _parse_preparation_plan(plan, SETTINGS_PREPARATION_SCHEMA)


def parse_public_preparation_plan(plan):
    if isinstance(plan, Mapping) and plan.get("schema") == INPUT_SET_PREPARATION_SCHEMA:
        return _parse_preparation_plan(plan, INPUT_SET_PREPARATION_SCHEMA)
    if isinstance(plan, Mapping) and plan.get("schema") == SETTINGS_PREPARATION_SCHEMA:
        return parse_settings_preparation_plan(plan)
    return parse_preparation_plan(plan)


def _parse_preparation_plan(plan, schema):
    _require(isinstance(plan, Mapping) and set(plan) == {"schema", "experiment_count", "v2_graphs", "content_address"},
             "Preparation plan is incomplete.")
    _require(plan["schema"] == schema and type(plan["experiment_count"]) is int and plan["experiment_count"] == 1,
             "Preparation plan version or size is unsupported.")
    _require(isinstance(plan["v2_graphs"], list) and len(plan["v2_graphs"]) == 1, "Select one saved strategy.")
    value = _plain(plan); value["v2_graphs"][0] = _validate_descriptor(value["v2_graphs"][0],
        settings_snapshot=schema in {SETTINGS_PREPARATION_SCHEMA, INPUT_SET_PREPARATION_SCHEMA},
        input_set=schema == INPUT_SET_PREPARATION_SCHEMA)
    _require(value["content_address"] == content_address({k: v for k, v in value.items() if k != "content_address"}),
             "Preparation plan address is stale.")
    _require(len(canonical_json(value).encode()) <= 65536, "Preparation plan is too large.")
    return value


@dataclass(frozen=True)
class PreparationInputs:
    descriptor: dict[str, Any]
    version: dict[str, Any]
    projection: Any
    resolved: Any
    data_plan: Any
    resource_plan: Any
    policy: Any


def require_current_strategy_library(saved):
    from app.ir.library import REGISTRY
    if saved["registry_snapshot_address"] != REGISTRY.registry_snapshot_address:
        raise V2OperationRefusal("STRATEGY_LIBRARY_CHANGED",
            "The strategy library changed since this version was saved. Review and save a new version with the current library before running it. Earlier versions and results remain unchanged.")


def _saved_version(item: dict[str, Any]) -> dict[str, Any]:
    from app.editor.v2_editor_store import read_version
    saved = read_version(item["project_id"], item["graph_identifier"], item["graph_version"], owner_id=item["owner_id"])
    pairs = (("content_address", "content_address"), ("graph_address", "graph_address"),
             ("registry_snapshot_address", "registry_snapshot_address"))
    _require(all(saved[left] == item[right] for left, right in pairs), "The saved strategy changed. Select its verified version again.")
    require_current_strategy_library(saved)
    return saved


def _dataset(item: dict[str, Any], version: dict[str, Any], research_session, execution_session):
    if "input_datasets" in item:
        from research.orchestrator.v2_operation import _load_input_set_projection
        _, canonical, projection = _load_input_set_projection(item, version["document"], execution_session, research_session)
        return canonical, projection
    from types import SimpleNamespace
    from app.ir.library import REGISTRY
    from research.data.canonical_dataset import load_canonical_datasets, project_verified_research_inputs
    from research.orchestrator.v2_operation import _graph_input_fields
    selection = SimpleNamespace(manifest_address=item["dataset_manifest_address"], as_of=dt.datetime.fromisoformat(item["dataset_as_of"]))
    datasets = load_canonical_datasets(research_session, execution_session=execution_session,
        owner_id=item["owner_id"], selections=[selection])
    _require(len(datasets) == 1, "Select one verified dataset.")
    canonical = datasets[0][1]
    projection = project_verified_research_inputs(canonical, owner_id=item["owner_id"],
        graph_input_fields=_graph_input_fields(version["document"], REGISTRY))
    return canonical, projection


def _runtime_inputs(item, version, canonical, projection, operation, repository):
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.ir.incremental_runtime import accept_research_resource_plan
    from app.market_data.requirements import compile_data_requirement_plan
    from research.orchestrator.v2_operation import _evaluation_policy_document, _projection_resource_admission, _research_policy
    resolved = resolve_v2(version["document"], REGISTRY)
    data_plan = compile_data_requirement_plan(resolved, registry=REGISTRY, input_bindings=projection.input_bindings)
    resource = accept_research_resource_plan(resolved, data_plan, REGISTRY, input_bindings=projection.input_bindings)
    _projection_resource_admission(resource, canonical, projection, operation.plan, repository, item["owner_id"])
    run_identity = content_address({"schema": "v2-preparation-run/1", "operation_id": operation.operation_id,
                                    "descriptor_address": item["descriptor_address"]})
    policy = _research_policy(_evaluation_policy_document(owner_id=item["owner_id"], manifest=projection.manifest,
        projection=projection, resolved=resolved, resource_plan=resource, run_authority_address=run_identity))
    return PreparationInputs(item, version, projection, resolved, data_plan, resource, policy)


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _profile(inputs, execution_session):
    from app.market_data.authority import load_capability_profile, load_provider_conformance
    from app.market_truth.identity import load_provider_identity
    manifest = inputs.projection.manifest
    profile = load_capability_profile(execution_session, manifest.capability_profile_address,
                                     at_time=_now())
    conformance = load_provider_conformance(execution_session, profile.conformance_evidence_address)
    _, _, contract = load_provider_identity(execution_session, profile.provider_contract_address)
    return profile, conformance, contract


def _eligibility(inputs, execution_session) -> None:
    if inputs.projection.input_sources is not None:
        result = bound_projection_eligibility(inputs.descriptor, inputs.version["document"],
            inputs.projection, inputs.resolved, inputs.data_plan, inputs.policy.policy_address, execution_session)
        _require_supported_eligibility(result)
        return
    from app.ir.library import REGISTRY
    from app.ir.v2_graph_versions import V2GraphFacts
    from app.market_truth.identity import load_canonical_instrument
    from app.market_data.eligibility import EligibilityRequest, SelectedDataset, compile_graph_data_eligibility
    item, manifest = inputs.descriptor, inputs.projection.manifest
    profile, conformance, contract = _profile(inputs, execution_session)
    physical = load_canonical_instrument(execution_session, manifest.instrument_addresses[0])
    facts = V2GraphFacts(owner_id=item["owner_id"], graph_identifier=item["graph_identifier"], graph_version=item["graph_version"],
        artifact_json=canonical_json(inputs.version["document"]), format_version=2, content_address=item["content_address"],
        graph_address=item["graph_address"], registry_snapshot_address=item["registry_snapshot_address"])
    start = dt.datetime.fromisoformat(manifest.event_start)
    warmup = max((row["requirement"]["history"]["minimum_bars"] + row["requirement"]["history"]["warmup_bars"])
                 * row["requirement"]["timeframe"] for row in inputs.data_plan.requirements)
    requested_start, requested_end = _eligibility_interval(start, dt.datetime.fromisoformat(manifest.event_end), warmup)
    result = compile_graph_data_eligibility(request=EligibilityRequest(owner_id=item["owner_id"], mode="RESEARCH",
        requested_start=requested_start, requested_end=requested_end,
        as_of=dt.datetime.fromisoformat(item["dataset_as_of"])), graph=facts, resolved_graph=inputs.resolved,
        plan=inputs.data_plan, input_bindings=inputs.projection.input_bindings,
        datasets=(SelectedDataset(manifest, inputs.projection.segment_objects, physical),),
        profile=profile, conformance=conformance, provider_contract=contract, registry=REGISTRY)
    _require_supported_eligibility(result)


def _require_supported_eligibility(result):
    if result.status != "SUPPORTED":
        reasons = "; ".join(row.detail for row in result.refusals)[:350]
        raise V2OperationRefusal("V2_DATASET_INELIGIBLE", f"{reasons}. Choose compatible data or revise the strategy.")


def _bound_source_records(projection, execution_session, as_of):
    from app.strategy.admission import _bound_capability_sources
    from app.market_data.eligibility import SelectedDataset
    from app.market_truth.identity import load_canonical_instrument
    sources = _bound_capability_sources(projection, execution_session, as_of)
    selected = {}
    for name, source in projection.input_sources.items():
        manifest = source.manifest
        selected[name] = SelectedDataset(manifest, source.segment_objects,
            load_canonical_instrument(execution_session, manifest.instrument_addresses[0]))
    return sources, selected


def bound_projection_eligibility(descriptor, document, projection, resolved, data_plan,
                                 evaluation_policy_address, execution_session):
    """Recheck each pinned source against the complete current graph, including candidates."""
    from app.ir.library import REGISTRY
    from app.ir.v2_graph_versions import V2GraphFacts
    from app.market_data.eligibility import EligibilityRequest, compile_bound_graph_data_eligibility
    as_of = dt.datetime.fromisoformat(descriptor["dataset_as_of"])
    sources, selected = _bound_source_records(projection, execution_session, as_of)
    owner_id = projection.manifest.owner_id
    authored = {"identity_scheme_version": 1, "graph": {key: document[key]
        for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}}
    facts = V2GraphFacts(owner_id, descriptor["graph_identifier"], descriptor["graph_version"],
        canonical_json(document), 2, content_address(document), content_address(authored), data_plan.registry_snapshot_address)
    warmup = max((row["requirement"]["history"]["minimum_bars"] + row["requirement"]["history"]["warmup_bars"])
                 * row["requirement"]["timeframe"] for row in data_plan.requirements)
    start = max(dt.datetime.fromisoformat(item.manifest.event_start) for item in selected.values())
    end = min(dt.datetime.fromisoformat(item.manifest.event_end) for item in selected.values())
    requested_start, requested_end = _eligibility_interval(start, end, warmup)
    return compile_bound_graph_data_eligibility(request=EligibilityRequest(owner_id, "RESEARCH",
        requested_start, requested_end, as_of), graph=facts, resolved_graph=resolved,
        plan=data_plan, input_bindings=projection.input_bindings, datasets=selected, sources=sources,
        registry=REGISTRY, dataset_set_address=projection.dataset_selection_address,
        evaluation_policy_address=evaluation_policy_address)


def _evidence(inputs, result) -> dict[str, Any]:
    _require(result.document["status"] == "COMPLETED", "Preparation was cancelled. No admission was created.")
    item, projection = inputs.descriptor, inputs.projection
    documents = {
        "input": {"input_digest": projection.input_digest, "derivation_address": projection.derivation_address,
                  "input_bindings": _plain(projection.input_bindings.document)},
        "fee": item["execution_policy"]["fee"], "slippage": item["execution_policy"]["slippage"],
        "risk": item["execution_policy"]["risk"], "evaluation_policy": _plain(inputs.policy.document),
        "parity": _plain(result.document),
        "causal": {"schema": "v2-dataset-prefix-evidence/1", "result_address": result.result_address,
                   "input_digest": projection.input_digest, "descriptor_address": item["descriptor_address"],
                   "evaluation_policy_address": inputs.policy.policy_address,
                   "scope": "prefix-consistency-on-selected-retrospective-dataset",
                   "historical_source_availability": "NOT_ASSERTED"},
    }
    addresses = {"input_address": projection.input_digest, "dataset_address": projection.manifest.manifest_address,
                 "fee_address": documents["fee"]["address"], "slippage_address": content_address(documents["slippage"]),
                 "risk_address": content_address(documents["risk"]), "parity_address": result.result_address,
                 "causal_evidence_address": content_address(documents["causal"])}
    schema = EVIDENCE_SCHEMA
    if projection.input_sources is not None:
        schema = INPUT_SET_EVIDENCE_SCHEMA
        documents["dataset_selection"] = _plain(projection.dataset_selection_document)
        documents["causal"].update(schema="v2-dataset-prefix-evidence/2",
                                   dataset_selection_address=projection.dataset_selection_address)
        addresses.update(dataset_address=projection.dataset_selection_address,
                         causal_evidence_address=content_address(documents["causal"]))
    value = {"schema": schema, "descriptor_address": item["descriptor_address"],
             "owner_id": item["owner_id"], "documents": documents, "addresses": addresses}
    value["evidence_address"] = content_address(value)
    return validate_preparation_evidence(value, item)


def decode_preparation_evidence(raw: str, descriptor):
    import json
    try:
        _require(isinstance(raw, str) and len(raw.encode()) <= MAX_EVIDENCE_BYTES, "Preparation evidence exceeds its byte bound.")
        value = json.loads(raw)
        _require(canonical_json(value) == raw, "Preparation evidence bytes are noncanonical.")
        return validate_preparation_evidence(value, descriptor)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise V2OperationRefusal("V2_PREPARATION_EVIDENCE_INVALID",
            "The recorded preparation evidence could not be verified. Start a new research request.") from exc


def validate_preparation_evidence(value, descriptor=None):
    _require(isinstance(value, dict) and set(value) == {"schema", "descriptor_address", "owner_id", "documents", "addresses", "evidence_address"},
             "Preparation evidence is incomplete.")
    _require(value["schema"] in {EVIDENCE_SCHEMA, INPUT_SET_EVIDENCE_SCHEMA}, "Preparation evidence version is unsupported.")
    _require(len(canonical_json(value).encode()) <= MAX_EVIDENCE_BYTES, "Preparation evidence exceeds its byte bound.")
    _require(value["evidence_address"] == content_address({k: v for k, v in value.items() if k != "evidence_address"}),
             "Preparation evidence bytes do not match their address.")
    _validate_evidence_documents(value)
    if descriptor is not None:
        _bind_evidence_descriptor(value, descriptor)
    return _plain(value)


def _bind_evidence_descriptor(value, descriptor):
    _require(value["owner_id"] == descriptor["owner_id"] and value["descriptor_address"] == descriptor["descriptor_address"],
             "Preparation evidence belongs to another request.")
    documents = value["documents"]
    _require(all(documents[name] == descriptor["execution_policy"][name] for name in ("fee", "slippage", "risk")),
             "Preparation assumptions belong to another request.")
    expected = {"owner_id": descriptor["owner_id"], "authored_ir_address": descriptor["content_address"],
                "registry_snapshot_address": descriptor["registry_snapshot_address"],
                "dataset_input_digest": documents["input"]["input_digest"]}
    if "input_datasets" in descriptor:
        _bind_input_set_evidence(value, descriptor)
    else:
        _require(value["schema"] == EVIDENCE_SCHEMA, "Preparation evidence belongs to another dataset kind.")
        expected["dataset_manifest_address"] = descriptor["dataset_manifest_address"]
    _require(all(documents["parity"][key] == expected_value for key, expected_value in expected.items()),
             "Preparation comparison belongs to another graph or dataset.")


def _bind_input_set_evidence(value, descriptor):
    _require(value["schema"] == INPUT_SET_EVIDENCE_SCHEMA, "Input-set preparation requires source evidence.")
    selection = value["documents"]["dataset_selection"]
    selected = {row["graph_input_id"]: row["dataset_manifest_address"] for row in descriptor["input_datasets"]}
    _require(selection["owner_id"] == descriptor["owner_id"]
             and selection["primary_input"] == descriptor["primary_input"]
             and selection["as_of"] == descriptor["dataset_as_of"]
             and {name: row["dataset_manifest_address"] for name, row in selection["inputs"].items()} == selected,
             "Preparation evidence belongs to another selected input set.")


def _validate_evidence_documents(value):
    documents, addresses = value["documents"], value["addresses"]
    fields = {"input", "fee", "slippage", "risk", "evaluation_policy", "parity", "causal"}
    if value["schema"] == INPUT_SET_EVIDENCE_SCHEMA:
        fields.add("dataset_selection")
    _require(isinstance(documents, dict) and set(documents) == fields,
             "Preparation documents are incomplete.")
    from app.strategy.admission import V2AdmissionEvidence
    V2AdmissionEvidence(**addresses)
    expected = {"input_address": documents["input"]["input_digest"],
                "dataset_address": documents["parity"]["dataset_manifest_address"],
                "fee_address": documents["fee"]["address"], "slippage_address": content_address(documents["slippage"]),
                "risk_address": content_address(documents["risk"]), "causal_evidence_address": content_address(documents["causal"]),
                "parity_address": content_address({k: v for k, v in documents["parity"].items() if k != "result_address"})}
    if value["schema"] == INPUT_SET_EVIDENCE_SCHEMA:
        expected["dataset_address"] = _verify_input_set_evidence(documents)
    else:
        _require(documents["evaluation_policy"]["schema"] == "research-evaluation-policy/1", "Legacy preparation requires its original evaluation policy.")
    _require(addresses == expected and documents["parity"]["status"] == "COMPLETED", "Preparation facts or comparisons do not verify.")
    _verify_recorded_policy(documents)


def _verify_input_set_evidence(documents):
    selection = documents["dataset_selection"]
    _require(isinstance(selection, dict) and set(selection) == {"schema", "owner_id", "primary_input", "as_of", "alignment", "inputs"}
             and selection["schema"] == "canonical-research-input-selection/1", "Selected source evidence is incomplete.")
    address = content_address(selection)
    parity, policy = documents["parity"], documents["evaluation_policy"]
    _require(parity["schema"] == "phase5-research-run-result/2" and policy["schema"] == "research-evaluation-policy/2"
             and parity["dataset_selection_address"] == policy["dataset_selection_address"] == address
             and parity["primary_input"] == policy["primary_input"] == selection["primary_input"]
             and parity["source_policies"] == policy["source_policies"], "Comparison source evidence differs from its policy.")
    return address


def _verify_recorded_policy(documents):
    from research.orchestrator.v2_operation import _research_policy
    policy = _research_policy(documents["evaluation_policy"])
    risk = documents["risk"]
    expected = execution_policy(risk["capital"], risk["risk_policy"], **protective_percentages(risk))
    _require(all(documents[name] == expected[name] for name in ("fee", "slippage", "risk")),
             "Recorded research assumptions do not match their policy.")
    _require(documents["parity"]["evaluation_policy_address"] == policy.policy_address,
             "The comparison used a different evaluation policy.")


def _admit(inputs, evidence, execution_session, research_session):
    if inputs.projection.input_sources is not None:
        from app.ir.library import REGISTRY
        from app.strategy.admission import V2AdmissionEvidence, admit_phase4_bound_v2_strategy
        return admit_phase4_bound_v2_strategy(owner_id=inputs.descriptor["owner_id"],
            document=inputs.version["document"], registry=REGISTRY,
            evidence=V2AdmissionEvidence(**evidence["addresses"]), plan=inputs.data_plan,
            projection=inputs.projection, evaluation_policy_address=inputs.policy.policy_address,
            research_session=research_session, execution_session=execution_session,
            at_time=dt.datetime.fromisoformat(inputs.descriptor["dataset_as_of"]))
    from app.ir.library import REGISTRY
    from app.market_data.capability import assess_capability
    from app.market_data.authority import persist_capability_assessment
    from app.strategy.admission import V2AdmissionEvidence, admit_phase4_v2_strategy
    item, manifest = inputs.descriptor, inputs.projection.manifest
    _require(len(manifest.truth_snapshot_addresses) == 1, "Select a dataset with one verified market-truth snapshot.")
    profile, conformance, contract = _profile(inputs, execution_session)
    now = dt.datetime.fromisoformat(item["dataset_as_of"])
    assessment = assess_capability(plan=inputs.data_plan, profile=profile, owner_id=item["owner_id"], mode="RESEARCH",
        dataset_manifest_address=manifest.manifest_address, market_truth_snapshot_address=manifest.truth_snapshot_addresses[0],
        evaluation_policy_address=inputs.policy.policy_address, assessment_evidence_address=conformance.address,
        at_time=int(now.timestamp()), conformance=conformance, provider_contract=contract)
    persist_capability_assessment(execution_session, assessment, plan=inputs.data_plan, at_time=now)
    wrapper = admit_phase4_v2_strategy(owner_id=item["owner_id"], mode="RESEARCH", document=inputs.version["document"],
        registry=REGISTRY, evidence=V2AdmissionEvidence(**evidence["addresses"]), plan=inputs.data_plan,
        input_bindings=inputs.projection.input_bindings, assessment_address=assessment.authority_address,
        dataset_manifest_address=manifest.manifest_address, market_truth_snapshot_address=manifest.truth_snapshot_addresses[0],
        evaluation_policy_address=inputs.policy.policy_address, research_session=research_session,
        execution_session=execution_session, at_time=now)
    return wrapper


def _publication_fence(recorder, repository):
    recorder.assert_claim()
    repository.lock_preparation(recorder.operation_id, owner_id=recorder.owner_id, token=recorder.token)


def _publish_admission(wrapper, recorder, repository, execution_session, research_session):
    """Keep costly reconstruction outside the operation row's publication lock."""
    from app.core.strategy_admissions import put
    from research.domain.admissions import store_admission
    _require(repository.session is research_session, "The research publication transaction does not match its operation.")
    try:
        put(execution_session, wrapper)
        _publication_fence(recorder, repository)
        execution_session.commit()
        research_session.commit()  # Release the operation fence before canonical research validation.
        store_admission(research_session, wrapper)
        _publication_fence(recorder, repository)
        research_session.commit()
    except Exception:
        execution_session.rollback()
        research_session.rollback()
        raise


def _refuse_bound_replay(operation, recorder, repository, item):
    key = f"v2_graph:000:{item['descriptor_address'].split(':', 1)[1][:32]}"
    if repository.bound_item_run(operation.operation_id, owner_id=item["owner_id"], item_key=key) is not None:
        repository.fail_bound_v2_replay(operation.operation_id, owner_id=item["owner_id"],
                                      token=recorder.token, item_key=key)
        raise V2OperationRefusal("V2_BOUND_RUN_REPLAY_REFUSED", "This operation already has a recorded run. Open that run instead.")


def _load_preparation_inputs(item, operation, repository, research_session, execution_session):
    from app.editor.v2_editor_store import EditorNotFound
    from research.data.canonical_dataset import CanonicalDatasetRefused
    from app.market_data.capability import CapabilityRefusal
    try:
        version = _saved_version(item)
        canonical, projection = _dataset(item, version, research_session, execution_session)
        inputs = _runtime_inputs(item, version, canonical, projection, operation, repository)
        _eligibility(inputs, execution_session)
        return inputs
    except EditorNotFound as exc:
        raise V2OperationRefusal("V2_GRAPH_NOT_FOUND", "The saved strategy is no longer available. Select an active project and saved version.") from exc
    except CanonicalDatasetRefused as exc:
        raise V2OperationRefusal("V2_DATASET_UNAVAILABLE", "The selected dataset could not be verified. Reimport it or choose another dataset.") from exc
    except CapabilityRefusal as exc:
        raise V2OperationRefusal("V2_CAPABILITY_UNAVAILABLE", "The dataset's current capability could not be verified. Refresh its data source or select compatible data.") from exc


def _evaluate_preparation(inputs, recorder):
    from app.ir.library import REGISTRY
    from research.evaluation.phase5_runtime import execute_research, ResearchExecutionRefusal
    from research.orchestrator.v2_operation import DurableClaimCancellationToken
    try:
        return execute_research(inputs.resolved, REGISTRY, inputs.resource_plan, inputs.projection, inputs.policy,
            cancellation=DurableClaimCancellationToken(recorder.assert_durable_claim))
    except ResearchExecutionRefusal as exc:
        raise V2OperationRefusal("V2_PREPARATION_EVALUATION_REFUSED",
            "The strategy calculation could not be verified against completed-bar prefixes. Check its components and input data.") from exc


def prepare_operation(*, operation, recorder, repository, execution_session, research_session):
    item = parse_public_preparation_plan(operation.plan)["v2_graphs"][0]
    _require(operation.operation_id == operation_id_for_request(owner_id=item["owner_id"], request_id=item["request_id"]),
             "Preparation operation identity differs.")
    recorder.assert_durable_claim()
    _refuse_bound_replay(operation, recorder, repository, item)
    repository.preparation_evidence(operation.operation_id, owner_id=item["owner_id"])
    inputs = _load_preparation_inputs(item, operation, repository, research_session, execution_session)
    recorder.assert_durable_claim()
    result = _evaluate_preparation(inputs, recorder)
    evidence = _evidence(inputs, result)
    repository.store_preparation_evidence(operation.operation_id, owner_id=item["owner_id"], token=recorder.token, evidence=evidence)
    recorder.assert_durable_claim()
    wrapper = _admit(inputs, evidence, execution_session, research_session)
    _publish_admission(wrapper, recorder, repository, execution_session, research_session)
    return _admitted_descriptor(item, wrapper)


def _admitted_descriptor(item, wrapper):
    value = {**item, "admission_address": wrapper.admission_address,
            "phase4_binding": _plain(wrapper.phase4_data_binding),
            "adapter_policy_address": item["execution_policy"]["adapter_policy_address"]}
    if "input_datasets" in item:
        value["dataset_manifest_address"] = wrapper.phase4_data_binding["dataset_manifest_address"]
    return value
