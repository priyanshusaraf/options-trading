"""Verified, provenance-complete Phase 5 research execution."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
import math
from types import MappingProxyType
from typing import Any, Mapping
from weakref import WeakKeyDictionary

import pandas as pd

from app.backtest.dataset_store import (
    DatasetManifest,
    DatasetSegment,
    verify_dataset_manifest,
)
from app.ir.hashing import canonical_json, content_address
from app.ir.implementation_identity import ImplementationUnidentified, implementation_address
from app.ir.incremental_runtime import (
    AcceptedResearchResourcePlan,
    AcceptedResearchSnapshotContext,
    CancellationToken,
    IncrementalRuntimeRefusal,
    StatefulRestartEvaluation,
    _create_accepted_research_snapshot_context,
    _evaluate_stateful_restart_mechanics,
    _verify_resource_plan,
    evaluate_incremental_v2,
    _common_index,
)
from app.ir.registry import PlatformRegistry
from app.ir.resolve import ResolvedV2Graph, ResolutionError, resolved_v2_graph_address
from app.ir.runtime import EvaluationError, evaluate_v2
from app.ir.schema import is_content_address
from app.ir.validity import NumericValue
from app.ir.first_party.logic_state import (
    DerivativeEvaluationContext,
    StateSeriesResult,
)
from app.ir.first_party.analytical_v2.contracts import (
    ContractInputBindings,
    ResolvedNodeContract,
    validate_input_bindings,
)


class ResearchExecutionRefusal(ValueError):
    pass


_CALLABLE_CLOSURE_CACHE: WeakKeyDictionary = WeakKeyDictionary()
NODE_CONTEXT_RESOLVER_ADDRESS = content_address({
    "schema": "research-node-context-resolver/1",
    "algorithm": "accepted-type3-point-in-time-fact",
    "version": 1,
})


@dataclass(frozen=True, init=False)
class VerifiedDatasetInputs:
    manifest: DatasetManifest
    segments: tuple[DatasetSegment, ...]
    segment_objects: Mapping[str, tuple[DatasetSegment, bytes]]
    inputs: Mapping[str, Any]
    input_digest: str
    derivation_address: str
    input_bindings: ContractInputBindings | None
    availability_index: pd.DatetimeIndex | None
    bar_open_index: pd.DatetimeIndex | None
    position_map_address: str | None
    session_policy_address: str | None
    resampling_policy_address: str | None
    source_codec: str
    input_sources: Mapping[str, VerifiedDatasetInputs] | None = None
    primary_input: str | None = None
    dataset_selection_document: Mapping[str, Any] | None = None
    dataset_selection_address: str | None = None
    source_provenance_json: str | None = None
    source_provenance_address: str | None = None

    def __init__(self, *args, **kwargs) -> None:
        raise ResearchExecutionRefusal("verified datasets use verify_research_dataset")

    @property
    def evaluation_window(self) -> tuple[dt.datetime, dt.datetime]:
        """Verified evaluation clock bounds; imported source arrival stays separate."""
        return _manifest_clock_window(self)

    @property
    def policy_input_bindings(self) -> Mapping[str, Any]:
        if self.input_bindings is None:
            return MappingProxyType({
                name: {"instrument_address": self.manifest.instrument_addresses[0],
                       "field": self.manifest.fields[0]}
                for name in sorted(self.inputs)
            })
        return MappingProxyType({
            name: MappingProxyType({
                "instrument_address": entry["binding"]["canonical_instrument_address"],
                "fields": tuple(entry["binding"]["fields"]),
                "binding_address": entry["binding_address"],
            })
            for name, entry in self.input_bindings.document["inputs"].items()
        })


@dataclass(frozen=True)
class ResearchEvaluationPolicy:
    document: Mapping[str, Any]
    policy_address: str

    def __post_init__(self) -> None:
        if self.document.get("evaluation_policy_address") != self.policy_address \
                or content_address({
                    key: _plain(item) for key, item in self.document.items()
                    if key != "evaluation_policy_address"
                }) != self.policy_address:
            raise ResearchExecutionRefusal("evaluation policy address is stale")


@dataclass(frozen=True)
class ResearchRunResult:
    document: Mapping[str, Any]
    result_address: str
    batch_output_document: Mapping[str, Any]
    incremental_output_document: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.document.get("result_address") != self.result_address \
                or content_address({
                    key: _plain(item) for key, item in self.document.items()
                    if key != "result_address"
                }) != self.result_address:
            raise ResearchExecutionRefusal("research result address is stale")
        if self.document["status"] == "COMPLETED":
            if self.batch_output_document != self.incremental_output_document \
                    or self.document["output_digest"] != content_address({
                        "schema": "incremental-output/1",
                        "outputs": _plain(self.batch_output_document),
                    }):
                raise ResearchExecutionRefusal("research result outputs differ from identity")
        elif self.document["status"] == "CANCELLED":
            if self.batch_output_document or self.incremental_output_document \
                    or self.document["output_digest"] is not None:
                raise ResearchExecutionRefusal("cancelled result carries executable outputs")
        else:
            raise ResearchExecutionRefusal("research result status is unknown")

    @property
    def batch_outputs(self) -> Mapping[str, Any]:
        return MappingProxyType(_materialize_outputs(self.batch_output_document))

    @property
    def incremental_outputs(self) -> Mapping[str, Any]:
        return MappingProxyType(_materialize_outputs(self.incremental_output_document))


def verify_research_dataset(
    manifest: DatasetManifest,
    segments: Mapping[str, tuple[DatasetSegment, bytes]],
    inputs: Mapping[str, Any],
) -> VerifiedDatasetInputs:
    if not isinstance(manifest, DatasetManifest):
        raise ResearchExecutionRefusal("DatasetManifest/2 is required")
    try:
        if DatasetManifest.from_bytes(manifest.canonical_bytes) != manifest:
            raise ValueError
        ordered = verify_dataset_manifest(manifest, segments)
    except (TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("dataset authority chain did not verify") from exc
    if not isinstance(inputs, Mapping) or not inputs:
        raise ResearchExecutionRefusal("research dataset inputs are absent")
    combined = b"".join(segments[address][1] for address in manifest.segment_addresses)
    decoded = _decode_research_inputs(combined)
    if not _equal(decoded, inputs):
        raise ResearchExecutionRefusal(
            "research inputs do not derive from the verified segment bytes"
        )
    copied = _copy_materialized(decoded)
    derivation_address = content_address({
        "algorithm": "phase5-canonical-research-inputs", "version": 1,
    })
    digest = content_address({
        "schema": "verified-research-inputs/1",
        "dataset_manifest_address": manifest.manifest_address,
        "inputs": _stable_value(copied),
    })
    result = object.__new__(VerifiedDatasetInputs)
    object.__setattr__(result, "manifest", manifest)
    object.__setattr__(result, "segments", ordered)
    object.__setattr__(result, "segment_objects", MappingProxyType({
        address: (segment, bytes(payload))
        for address, (segment, payload) in segments.items()
    }))
    object.__setattr__(result, "inputs", MappingProxyType(copied))
    object.__setattr__(result, "input_digest", digest)
    object.__setattr__(result, "derivation_address", derivation_address)
    index = next((value.index for value in copied.values()
                  if isinstance(value, pd.Series)), None)
    object.__setattr__(result, "input_bindings", None)
    object.__setattr__(result, "availability_index", index)
    object.__setattr__(result, "bar_open_index", None)
    object.__setattr__(result, "position_map_address", None)
    object.__setattr__(result, "session_policy_address", None)
    object.__setattr__(result, "resampling_policy_address", None)
    object.__setattr__(result, "source_codec", "canonical-research-inputs/1")
    return result


def _verify_canonical_observation_projection(
    manifest: DatasetManifest,
    segments: Mapping[str, tuple[DatasetSegment, bytes]],
    inputs: Mapping[str, Any], input_bindings: ContractInputBindings, *,
    availability_index: pd.DatetimeIndex, bar_open_index: pd.DatetimeIndex,
    session_policy_address: str, resampling_policy_address: str,
) -> VerifiedDatasetInputs:
    try:
        ordered = verify_dataset_manifest(manifest, segments)
        validate_input_bindings(input_bindings)
    except (TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("canonical observation authority did not verify") from exc
    if (not isinstance(inputs, Mapping) or not inputs
            or not isinstance(availability_index, pd.DatetimeIndex)
            or not isinstance(bar_open_index, pd.DatetimeIndex)
            or not availability_index.equals(_common_index(
                type("ProjectionGraph", (), {"nodes": ()})(), inputs,
                type("ProjectionRegistry", (), {"node_contracts": {}})(),
            ))
            or len(bar_open_index) != len(availability_index)
            or bar_open_index.tz is None or not bar_open_index.is_unique
            or not bar_open_index.is_monotonic_increasing
            or any(opened >= available for opened, available
                   in zip(bar_open_index, availability_index, strict=True))):
        raise ResearchExecutionRefusal("canonical observation clock projection is invalid")
    copied = _copy_materialized(inputs)
    derivation_address = content_address({
        "algorithm": "verified-observation-availability-projection", "version": 1,
    })
    digest = content_address({
        "schema": "verified-research-inputs/1",
        "dataset_manifest_address": manifest.manifest_address,
        "inputs": _stable_value(copied),
    })
    position_map_address = content_address({
        "schema": "bar-open-position-map/1",
        "dataset_manifest_address": manifest.manifest_address,
        "availability_index": [item.isoformat() for item in availability_index],
        "bar_open_index": [item.isoformat() for item in bar_open_index],
    })
    result = object.__new__(VerifiedDatasetInputs)
    values = {
        "manifest": manifest, "segments": ordered,
        "segment_objects": MappingProxyType({address: (segment, bytes(payload))
            for address, (segment, payload) in segments.items()}),
        "inputs": MappingProxyType(copied), "input_digest": digest,
        "derivation_address": derivation_address, "input_bindings": input_bindings,
        "availability_index": availability_index.copy(),
        "bar_open_index": bar_open_index.copy(),
        "position_map_address": position_map_address,
        "session_policy_address": _address(session_policy_address, "session policy"),
        "resampling_policy_address": _address(resampling_policy_address, "resampling policy"),
        "source_codec": "strategy-os-observation-candle-index/1",
    }
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def _input_set_sources(sources, owner_id, primary_input):
    if not isinstance(sources, Mapping) or not 2 <= len(sources) <= 8 \
            or primary_input not in sources or "primary" in set(sources) - {primary_input}:
        raise ResearchExecutionRefusal("input set requires separate sources and one primary input")
    for source in sources.values():
        _input_set_source(source, owner_id)
    primary = sources[primary_input]
    _input_set_clocks(sources, primary)
    instruments = [source.manifest.instrument_addresses for source in sources.values()]
    if len(set(instruments)) != len(instruments):
        raise ResearchExecutionRefusal("each input requires its own selected instrument")
    return primary


def _input_set_clocks(sources, primary):
    for source in sources.values():
        if not source.availability_index.equals(primary.availability_index) \
                or not source.bar_open_index.equals(primary.bar_open_index):
            raise ResearchExecutionRefusal("selected datasets require matching completed-bar timestamps")


def _input_set_source(source, owner_id):
    if not isinstance(source, VerifiedDatasetInputs) or source.input_sources is not None \
            or source.input_bindings is None:
        raise ResearchExecutionRefusal("each input requires one verified observation source")
    _validate_verified_dataset(source)
    validate_input_bindings(source.input_bindings)
    source_name = _source_input_name(source)
    manifest = source.manifest
    if manifest.owner_id != owner_id or manifest.mode != "RESEARCH" \
            or len(manifest.instrument_addresses) != 1:
        raise ResearchExecutionRefusal("input source owner or instrument differs")
    _verify_input_binding(source, source_name, source.policy_input_bindings[source_name])
    _input_set_source_fact(source, source_name)
    _input_set_source_clock(source, source_name)


def _source_input_name(source):
    if len(source.inputs) != 1 or set(source.input_bindings.document["inputs"]) != set(source.inputs):
        raise ResearchExecutionRefusal("source proof requires exactly one original input")
    return next(iter(source.inputs))


def _input_set_source_clock(source, name):
    if source.source_codec not in {"strategy-os-observation-candle-index/1",
                                   "strategy-os-observation-candle-index/2"}:
        raise ResearchExecutionRefusal("input set requires verified observation clocks")
    rebuilt = _verify_canonical_observation_projection(
        source.manifest, source.segment_objects, source.inputs, source.input_bindings,
        availability_index=source.availability_index, bar_open_index=source.bar_open_index,
        session_policy_address=source.session_policy_address,
        resampling_policy_address=source.resampling_policy_address)
    seconds = source.input_bindings.document["inputs"][name]["binding"]["timeframe"]
    opened = source.availability_index - pd.Timedelta(seconds=seconds)
    if not source.bar_open_index.equals(opened) \
            or source.position_map_address != rebuilt.position_map_address \
            or source.input_digest != rebuilt.input_digest:
        raise ResearchExecutionRefusal("input source clock differs from its observed series")


def _input_set_source_fact(source, name):
    fact = source.input_bindings.document["inputs"][name]["binding"]
    manifest = source.manifest
    allowed = {
        "owner_id": (manifest.owner_id,),
        "dataset_manifest_address": (manifest.manifest_address,),
        "market_truth_address": manifest.truth_snapshot_addresses,
        "provider_product_address": manifest.provider_product_addresses,
        "provider_contract_address": manifest.provider_contract_addresses,
        "canonical_instrument_address": manifest.instrument_addresses,
    }
    if any(fact[key] not in values for key, values in allowed.items()):
        raise ResearchExecutionRefusal("input binding is outside its source manifest")


def _input_set_selection(sources, owner_id, primary_input, as_of):
    instant = _aware(as_of, "dataset selection as-of")
    provenance = {name: _input_set_source_provenance(source)
                  for name, source in sources.items()}
    if any(cutoff != instant for cutoff, _ in provenance.values()):
        raise ResearchExecutionRefusal("input source cutoffs differ from the selected as-of")
    return {
        "schema": "canonical-research-input-selection/1", "owner_id": owner_id,
        "primary_input": primary_input, "as_of": instant.isoformat(),
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "inputs": {name: {
            "source_input_id": _source_input_name(source),
            "dataset_manifest_address": source.manifest.manifest_address,
            "source_input_digest": source.input_digest,
            "source_binding_address": source.input_bindings.document["inputs"][_source_input_name(source)]["binding_address"],
            "source_codec": source.source_codec,
            "source_provenance_address": provenance[name][1],
        } for name, source in sorted(sources.items())},
    }


def _input_set_source_provenance(source):
    try:
        proof = json.loads(source.source_provenance_json)
        if canonical_json(proof) != source.source_provenance_json \
                or content_address(proof) != source.source_provenance_address \
                or proof["manifest_address"] != source.manifest.manifest_address \
                or proof["instrument_address"] != source.manifest.instrument_addresses[0] \
                or content_address(proof["authority_manifest"]) != content_address(source.manifest.fact()):
            raise ValueError("source provenance differs")
        return _aware(proof["as_of"], "source as-of"), content_address(proof)
    except (KeyError, TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("input source provenance no longer reconstructs") from exc


def _input_set_bindings(sources, owner_id, primary_input, selection_address):
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
    context = content_address({
        "schema": "verified-observation-input-set-context/1",
        "dataset_selection_address": selection_address,
    })
    evaluation = content_address({
        "schema": "verified-observation-input-set-evaluation/1",
        "dataset_selection_address": selection_address,
        "source_contexts": {name: source.input_bindings.document["evaluation_context_address"]
                            for name, source in sorted(sources.items())},
    })
    facts = {}
    for name, source in sorted(sources.items()):
        fact = _plain(source.input_bindings.document["inputs"][_source_input_name(source)]["binding"])
        fact.update(dataset_context_address=context, evaluation_context_address=evaluation)
        fact["instrument"]["role"] = "primary" if name == primary_input else name
        facts[name] = fact
    return canonical_input_bindings(
        owner_id=owner_id, dataset_context_address=context,
        evaluation_context_address=evaluation, bindings=facts,
        expected_source_addresses={name: content_address(fact) for name, fact in facts.items()})


def _input_set_segments(sources):
    objects = {}
    for source in sources.values():
        for address, item in source.segment_objects.items():
            if address in objects and objects[address] != item:
                raise ResearchExecutionRefusal("dataset segment identities conflict")
            objects[address] = item
    return MappingProxyType(dict(sorted(objects.items())))


def _verify_observation_input_set(sources, *, owner_id, primary_input, as_of):
    primary = _input_set_sources(sources, owner_id, primary_input)
    selection = _input_set_selection(sources, owner_id, primary_input, as_of)
    selection_address = content_address(selection)
    bindings = _input_set_bindings(sources, owner_id, primary_input, selection_address)
    inputs = _copy_materialized({name: source.inputs[_source_input_name(source)]
                                for name, source in sorted(sources.items())})
    objects = _input_set_segments(sources)
    values = {**vars(primary),
        "inputs": MappingProxyType(inputs), "input_bindings": bindings,
        "input_sources": MappingProxyType(dict(sorted(sources.items()))),
        "primary_input": primary_input,
        "dataset_selection_document": _freeze(selection),
        "dataset_selection_address": selection_address,
        "segment_objects": objects, "segments": tuple(item[0] for item in objects.values()),
        "source_codec": "strategy-os-observation-input-set/1",
        "source_provenance_json": None,
        "source_provenance_address": None,
        "derivation_address": content_address({
            "algorithm": "verified-exact-observation-input-set", "version": 1}),
        "input_digest": content_address({
            "schema": "verified-research-input-set/1",
            "dataset_selection_address": selection_address, "inputs": _stable_value(inputs)}),
        "position_map_address": content_address({
            "schema": "input-set-bar-open-position-map/1",
            "dataset_selection_address": selection_address,
            "primary_position_map_address": primary.position_map_address}),
    }
    result = object.__new__(VerifiedDatasetInputs)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def _validate_verified_input_set(dataset):
    try:
        rebuilt = _verify_observation_input_set(
            dataset.input_sources, owner_id=dataset.manifest.owner_id,
            primary_input=dataset.primary_input,
            as_of=dataset.dataset_selection_document["as_of"])
        attributes = ("manifest", "segments", "segment_objects", "input_bindings",
                      "dataset_selection_document", "dataset_selection_address",
                      "input_digest", "derivation_address", "position_map_address",
                      "session_policy_address", "resampling_policy_address", "source_codec")
        if any(getattr(dataset, name) != getattr(rebuilt, name) for name in attributes) \
                or not _equal(dataset.inputs, rebuilt.inputs) \
                or not dataset.availability_index.equals(rebuilt.availability_index) \
                or not dataset.bar_open_index.equals(rebuilt.bar_open_index):
            raise ValueError("input set changed")
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("verified input-set proof no longer reconstructs") from exc


def canonical_research_input_bytes(inputs: Mapping[str, Any]) -> bytes:
    if not isinstance(inputs, Mapping) or not inputs:
        raise ResearchExecutionRefusal("canonical research inputs are absent")
    return canonical_json({
        "schema": "canonical-research-inputs/1",
        "inputs": _stable_value(inputs),
    }).encode("utf-8")


def input_set_policy_fields(dataset: VerifiedDatasetInputs) -> dict[str, Any]:
    """Additional policy facts for an already verified multi-source projection."""
    _validate_verified_dataset(dataset)
    if dataset.input_sources is None:
        raise ResearchExecutionRefusal("input-set policy requires multiple verified sources")
    return {
        "schema": "research-evaluation-policy/2",
        "dataset_selection_address": dataset.dataset_selection_address,
        "primary_input": dataset.primary_input,
        "source_policies": _source_policies(dataset),
        "truth_snapshot_addresses": list(_dataset_truth_snapshots(dataset)),
    }


def _source_policies(dataset):
    return {name: {
        "dataset_manifest_address": source.manifest.manifest_address,
        "input_digest": source.input_digest,
        "truth_snapshot_addresses": list(source.manifest.truth_snapshot_addresses),
        "adjustment_policy_address": source.manifest.adjustment_policy_address,
        "missing_data_policy_address": source.manifest.missing_data_policy_address,
        "alignment_policy_address": source.manifest.alignment_policy_address,
        "session_policy_address": source.session_policy_address,
        "resampling_policy_address": source.resampling_policy_address,
    } for name, source in sorted(dataset.input_sources.items())}


def _dataset_truth_snapshots(dataset):
    if dataset.input_sources is None:
        return tuple(dataset.manifest.truth_snapshot_addresses)
    return tuple(sorted({address for source in dataset.input_sources.values()
                         for address in source.manifest.truth_snapshot_addresses}))


def _validate_source_policy(row):
    fields = {"dataset_manifest_address", "input_digest", "truth_snapshot_addresses",
              "adjustment_policy_address", "missing_data_policy_address",
              "alignment_policy_address", "session_policy_address", "resampling_policy_address"}
    if not isinstance(row, Mapping) or set(row) != fields:
        raise ResearchExecutionRefusal("source policy is open or incomplete")
    _addresses(row["truth_snapshot_addresses"], "source truth snapshots")
    for field in fields - {"truth_snapshot_addresses"}:
        _address(row[field], field)


def _validate_policy_sources(value):
    sources = value.get("source_policies")
    if not isinstance(sources, dict) or not 2 <= len(sources) <= 8 \
            or not isinstance(value.get("primary_input"), str):
        raise ResearchExecutionRefusal("source policies require one named primary input")
    if value["primary_input"] not in sources or set(sources) != set(value["input_bindings"]):
        raise ResearchExecutionRefusal("source policies must cover every graph input")
    for row in sources.values():
        _validate_source_policy(row)
    _address(value.get("dataset_selection_address"), "dataset selection")


def research_input_set_evaluation_policy(document: Mapping[str, Any]) -> ResearchEvaluationPolicy:
    if not isinstance(document, Mapping) or document.get("schema") != "research-evaluation-policy/2":
        raise ResearchExecutionRefusal("input-set policy version is unsupported")
    value = _plain(document)
    base = {key: item for key, item in value.items()
            if key not in {"dataset_selection_address", "primary_input", "source_policies"}}
    base["schema"] = "research-evaluation-policy/1"
    base["evaluation_policy_address"] = content_address({key: item for key, item in base.items()
                                                       if key != "evaluation_policy_address"})
    research_evaluation_policy(base)
    _validate_policy_sources(value)
    return ResearchEvaluationPolicy(_freeze(value), _address(value.get("evaluation_policy_address"), "evaluation policy"))


def research_evaluation_policy(document: Mapping[str, Any]) -> ResearchEvaluationPolicy:
    fields = {
        "schema", "owner_id", "mode", "dataset_manifest_address",
        "dataset_input_digest", "input_derivation_address",
        "node_context_resolver_address",
        "resolved_graph_address", "registry_snapshot_address",
        "implementation_closure_address", "resource_plan_address",
        "truth_snapshot_addresses", "adjustment_policy_address",
        "session_policy_address", "resampling_policy_address",
        "missing_data_policy_address", "alignment_policy_address",
        "run_authority_address", "input_bindings", "event_kind",
        "event_start", "event_end", "maximum_events",
        "cancellation_check_interval", "evaluation_policy_address",
    }
    if not isinstance(document, Mapping) or set(document) != fields \
            or document.get("schema") != "research-evaluation-policy/1" \
            or not isinstance(document.get("owner_id"), str) \
            or not document["owner_id"] or document.get("mode") != "RESEARCH":
        raise ResearchExecutionRefusal("evaluation policy is open or incomplete")
    for name in (
        "dataset_manifest_address", "resolved_graph_address",
        "dataset_input_digest", "input_derivation_address",
        "node_context_resolver_address",
        "registry_snapshot_address", "implementation_closure_address",
        "resource_plan_address", "adjustment_policy_address",
        "session_policy_address", "resampling_policy_address",
        "missing_data_policy_address", "alignment_policy_address",
        "run_authority_address",
    ):
        _address(document[name], name)
    truth = _addresses(document["truth_snapshot_addresses"], "truth snapshots")
    bindings = document["input_bindings"]
    if not isinstance(bindings, Mapping) or not bindings or list(bindings) != sorted(bindings):
        raise ResearchExecutionRefusal("input bindings are absent or noncanonical")
    copied_bindings = {}
    for name, binding in bindings.items():
        if not isinstance(name, str) or not name \
                or not isinstance(binding, Mapping) \
                or set(binding) not in (
                    {"instrument_address", "field"},
                    {"instrument_address", "fields", "binding_address"},
                ):
            raise ResearchExecutionRefusal("input binding is malformed")
        _address(binding["instrument_address"], "binding instrument")
        if "field" in binding:
            if not isinstance(binding["field"], str) or not binding["field"]:
                raise ResearchExecutionRefusal("input binding field is malformed")
        else:
            fields = binding["fields"]
            if (not isinstance(fields, (tuple, list)) or not fields
                    or tuple(fields) != tuple(sorted(set(fields)))
                    or any(not isinstance(field, str) or not field for field in fields)):
                raise ResearchExecutionRefusal("input binding fields are malformed")
            _address(binding["binding_address"], "input binding source")
        copied_bindings[name] = dict(binding)
    start = _aware(document["event_start"], "event_start")
    end = _aware(document["event_end"], "event_end")
    if start >= end or not isinstance(document["event_kind"], str) \
            or not document["event_kind"] \
            or type(document["maximum_events"]) is not int \
            or document["maximum_events"] < 1 \
            or document["cancellation_check_interval"] != 1:
        raise ResearchExecutionRefusal("evaluation time/event/cancellation bounds are invalid")
    payload = {
        **document,
        "truth_snapshot_addresses": list(truth),
        "input_bindings": copied_bindings,
    }
    expected = content_address({
        key: _plain(item) for key, item in payload.items()
        if key != "evaluation_policy_address"
    })
    if document["evaluation_policy_address"] != expected:
        raise ResearchExecutionRefusal("evaluation policy address is stale")
    return ResearchEvaluationPolicy(_freeze(payload), expected)


def execute_research(
    graph: Any,
    registry: Any,
    resource_plan: AcceptedResearchResourcePlan,
    dataset: VerifiedDatasetInputs,
    policy: ResearchEvaluationPolicy,
    *,
    cancellation: CancellationToken | None = None,
) -> ResearchRunResult:
    if not isinstance(resource_plan, AcceptedResearchResourcePlan) \
            or not isinstance(registry, PlatformRegistry) \
            or not isinstance(dataset, VerifiedDatasetInputs) \
            or not isinstance(policy, ResearchEvaluationPolicy):
        raise ResearchExecutionRefusal("canonical graph inputs, plan and policy are required")
    _validate_policy(policy)
    _validate_verified_dataset(dataset)
    _validate_graph_registry(graph, registry)
    _verify_authority(graph, registry, resource_plan, dataset, policy)
    try:
        _verify_resource_plan(
            graph, registry, resource_plan, policy.document["event_kind"],
        )
    except IncrementalRuntimeRefusal as exc:
        raise ResearchExecutionRefusal(
            "research ResourcePlan authority did not reconstruct"
        ) from exc
    try:
        context_resolver = _node_context_resolver(policy, dataset, registry, resource_plan)
        incremental = evaluate_incremental_v2(
            graph, dataset.inputs, registry, resource_plan,
            event_kind=policy.document["event_kind"],
            maximum_events=policy.document["maximum_events"],
            cancellation=cancellation,
            evaluation_context_resolver=context_resolver,
        )
    except IncrementalRuntimeRefusal as exc:
        if "differ" in str(exc):
            raise ResearchExecutionRefusal(
                "vector and incremental outputs differ"
            ) from exc
        raise ResearchExecutionRefusal("incremental evaluation refused") from exc
    except (TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("incremental evaluation refused") from exc
    if incremental.status == "CANCELLED":
        return _result(
            graph, registry, resource_plan, dataset, policy,
            status="CANCELLED", batch={}, incremental={}, output_digest=None,
            event_count=incremental.completed_events,
            last_event_address=None, last_event_time=None,
        )
    try:
        batch = evaluate_v2(
            graph, dataset.inputs, registry,
            evaluation_context_resolver=context_resolver,
        )
    except (EvaluationError, TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("vector evaluation refused") from exc
    if not _equal(batch, incremental.outputs):
        raise ResearchExecutionRefusal("vector and incremental outputs differ")
    batch_digest = content_address({
        "schema": "incremental-output/1", "outputs": _stable_value(batch),
    })
    if batch_digest != incremental.output_digest:
        raise ResearchExecutionRefusal("vector and incremental output identities differ")
    return _result(
        graph, registry, resource_plan, dataset, policy,
        status="COMPLETED", batch=batch, incremental=incremental.outputs,
        output_digest=batch_digest, event_count=incremental.completed_events,
        last_event_address=incremental.last_event_address,
        last_event_time=incremental.last_event_time,
    )


def _node_context_resolver(
    policy: ResearchEvaluationPolicy,
    dataset: VerifiedDatasetInputs,
    registry: PlatformRegistry,
    resource_plan: AcceptedResearchResourcePlan,
):
    if policy.document["node_context_resolver_address"] \
            != NODE_CONTEXT_RESOLVER_ADDRESS:
        raise ResearchExecutionRefusal("node context resolver identity differs")

    bound_contracts = {}
    for row in resource_plan.data_requirement_plan.parameter_binding_provenance:
        receipt = row.get("node_contract_binding")
        if receipt is not None:
            bound_contracts[tuple(row["lowered_path"])] = ResolvedNodeContract(
                receipt, receipt["bound_contract_address"],
            )

    def resolve(node: Any, assembled: Mapping[str, Any]) -> Any:
        contract = registry.node_contracts.get(node.component)
        if contract is None:
            raise ResearchExecutionRefusal("node context contract is absent")
        bound = bound_contracts.get(tuple(node.lowered_path))
        if bound is not None:
            return {"bound_contract": bound}
        if contract["visible_family"] != "TYPE_3":
            return None
        if set(assembled) != {"input"} or not isinstance(assembled["input"], Mapping):
            raise ResearchExecutionRefusal(
                "Type 3 context requires one assembled point-in-time fact"
            )
        fact = assembled["input"]
        if fact.get("owner_id") != policy.document["owner_id"] \
                or fact.get("mode") != policy.document["mode"]:
            raise ResearchExecutionRefusal("Type 3 fact owner or mode differs")
        event_time = _aware(fact.get("event_time"), "Type 3 event_time")
        knowledge_time = _aware(fact.get("knowledge_time"), "Type 3 knowledge_time")
        cutoff = _aware(fact.get("evaluation_cutoff"), "Type 3 evaluation_cutoff")
        policy_start = _aware(policy.document["event_start"], "event_start")
        policy_end = _aware(policy.document["event_end"], "event_end")
        manifest_start = _aware(dataset.manifest.event_start, "manifest event_start")
        manifest_end = _aware(dataset.manifest.event_end, "manifest event_end")
        if not (
            policy_start >= manifest_start
            and policy_end <= manifest_end
            and policy_start <= event_time <= knowledge_time <= cutoff < policy_end
        ):
            raise ResearchExecutionRefusal(
                "Type 3 fact time escapes accepted dataset/policy authority"
            )
        for name in (
            "fact_address", "source_address", "acceptance_evidence_address",
            "rulebook_snapshot_address", "selector_policy_address",
            "role_requirement_address",
        ):
            _address(fact.get(name), f"Type 3 {name}")
        capability = fact.get("capability_evidence_address")
        if capability is not None:
            _address(capability, "Type 3 capability evidence")
        return DerivativeEvaluationContext(
            owner_id=fact["owner_id"], mode=fact["mode"],
            point_in_time_fact_address=fact["fact_address"],
            source_address=fact["source_address"],
            acceptance_evidence_address=fact["acceptance_evidence_address"],
            rulebook_snapshot_address=fact["rulebook_snapshot_address"],
            selector_policy_address=fact["selector_policy_address"],
            role_requirement_address=fact["role_requirement_address"],
            capability_evidence_address=capability,
        )

    return resolve


def accept_research_snapshot_context(
    component: tuple[str, int],
    node_id: str,
    graph: ResolvedV2Graph,
    registry: PlatformRegistry,
    resource_plan: AcceptedResearchResourcePlan,
    dataset: VerifiedDatasetInputs,
    policy: ResearchEvaluationPolicy,
    *,
    initial_state_payload: Any,
) -> AcceptedResearchSnapshotContext:
    if not isinstance(resource_plan, AcceptedResearchResourcePlan) \
            or not isinstance(registry, PlatformRegistry) \
            or not isinstance(dataset, VerifiedDatasetInputs) \
            or not isinstance(policy, ResearchEvaluationPolicy):
        raise ResearchExecutionRefusal(
            "snapshot context requires accepted research execution inputs"
        )
    _validate_policy(policy)
    _validate_verified_dataset(dataset)
    _validate_graph_registry(graph, registry)
    _verify_authority(graph, registry, resource_plan, dataset, policy)
    try:
        _verify_resource_plan(
            graph, registry, resource_plan, policy.document["event_kind"],
        )
    except IncrementalRuntimeRefusal as exc:
        raise ResearchExecutionRefusal(
            "snapshot ResourcePlan authority did not reconstruct"
        ) from exc
    matching = tuple(
        node for node in graph.nodes
        if node.node_id == node_id and node.component == component
    )
    contract = registry.node_contracts.get(component)
    contract_address = registry.node_contract_addresses.get(component)
    if len(matching) != 1 or contract is None or contract_address is None \
            or contract["execution_form"] != "RECURSIVE" \
            or not contract["mode_eligibility"]["research"] \
            or not contract["batch_support"] or not contract["streaming_support"]:
        raise ResearchExecutionRefusal(
            "snapshot component is not one accepted recursive graph node"
        )
    reset_document = {
        "schema": contract["state_reset_policy"]["schema"],
        "reasons": list(contract["state_reset_policy"]["reasons"]),
    }
    dataset_context_address = content_address({
        "schema": "accepted-research-dataset-context/1",
        "dataset_manifest_address": dataset.manifest.manifest_address,
        "dataset_input_digest": dataset.input_digest,
        "input_derivation_address": dataset.derivation_address,
    })
    return _create_accepted_research_snapshot_context(
        component=component,
        node_id=node_id,
        node_parameters=matching[0].parameters,
        registry_snapshot_address=registry.registry_snapshot_address,
        resource_plan_address=resource_plan.plan_address,
        run_authority_address=policy.document["run_authority_address"],
        strategy_address=graph.authored_ir_address,
        resolved_graph_address=graph.resolved_graph_address,
        node_contract_address=contract_address,
        implementation_closure_address=graph.implementation_closure_address,
        dataset_context_address=dataset_context_address,
        evaluation_context_address=policy.policy_address,
        reset_policy_address=content_address(reset_document),
        initial_state_payload=initial_state_payload,
    )


def evaluate_stateful_restart(
    component: tuple[str, int],
    parameters: Mapping[str, Any],
    full_input: Mapping[str, Any],
    graph: ResolvedV2Graph,
    registry: PlatformRegistry,
    resource_plan: AcceptedResearchResourcePlan,
    dataset: VerifiedDatasetInputs,
    policy: ResearchEvaluationPolicy,
    context: AcceptedResearchSnapshotContext,
    *,
    node_id: str,
    split_index: int,
    pending_reset_reasons: tuple[str, ...] = (),
) -> StatefulRestartEvaluation:
    if type(context) is not AcceptedResearchSnapshotContext:
        raise ResearchExecutionRefusal(
            "stateful restart requires an accepted snapshot context"
        )
    try:
        initial_state_payload = context.authority.initial_state_payload
    except (AttributeError, TypeError) as exc:
        raise ResearchExecutionRefusal(
            "accepted snapshot context does not reconstruct"
        ) from exc
    expected = accept_research_snapshot_context(
        component, node_id, graph, registry, resource_plan, dataset, policy,
        initial_state_payload=initial_state_payload,
    )
    if context != expected:
        raise ResearchExecutionRefusal(
            "snapshot context does not derive from accepted execution inputs"
        )
    try:
        return _evaluate_stateful_restart_mechanics(
            component, parameters, full_input, registry, expected,
            split_index=split_index,
            pending_reset_reasons=pending_reset_reasons,
        )
    except IncrementalRuntimeRefusal as exc:
        raise ResearchExecutionRefusal("stateful restart evaluation refused") from exc


def registered_research_universe(registry: PlatformRegistry) -> tuple[tuple[str, int], ...]:
    if not isinstance(registry, PlatformRegistry):
        raise ResearchExecutionRefusal("PlatformRegistry is required")
    result = tuple(sorted(
        key for key, contract in registry.node_contracts.items()
        if contract["mode_eligibility"]["research"]
        and contract["batch_support"] and contract["streaming_support"]
    ))
    if any(key not in registry.v2_implementations for key in result):
        raise ResearchExecutionRefusal("research universe contains an unimplemented node")
    return result


def require_complete_research_case_universe(
    registry: PlatformRegistry, components: Any,
) -> tuple[tuple[str, int], ...]:
    if not isinstance(components, (tuple, list)):
        raise ResearchExecutionRefusal("research case universe must be finite")
    actual = tuple(components)
    expected = registered_research_universe(registry)
    if actual != expected or len(actual) != len(set(actual)):
        raise ResearchExecutionRefusal("research case universe is incomplete or noncanonical")
    return expected


def _verify_authority(
    graph: Any, registry: Any, resource_plan: AcceptedResearchResourcePlan,
    dataset: VerifiedDatasetInputs, policy: ResearchEvaluationPolicy,
) -> None:
    _verify_execution_identities(graph, registry, resource_plan, dataset, policy)
    _verify_dataset_policy(dataset, resource_plan, policy.document)
    _verify_policy_bindings(graph, dataset, policy.document)
    _verify_input_window(graph, registry, dataset, policy.document)


def _verify_execution_identities(
    graph: Any, registry: Any, resource_plan: AcceptedResearchResourcePlan,
    dataset: VerifiedDatasetInputs, policy: ResearchEvaluationPolicy,
) -> None:
    document = policy.document
    identities = (
        (document["dataset_manifest_address"], dataset.manifest.manifest_address),
        (document["dataset_input_digest"], dataset.input_digest),
        (document["input_derivation_address"], dataset.derivation_address),
        (document["node_context_resolver_address"], NODE_CONTEXT_RESOLVER_ADDRESS),
        (document["resolved_graph_address"], getattr(graph, "resolved_graph_address", None)),
        (document["registry_snapshot_address"], getattr(registry, "registry_snapshot_address", None)),
        (document["implementation_closure_address"], getattr(graph, "implementation_closure_address", None)),
        (document["resource_plan_address"], resource_plan.plan_address),
    )
    if any(left != right for left, right in identities):
        raise ResearchExecutionRefusal("research policy authority identities differ")
    closure_document = {
        "implementations": [
            {"component_id": key[0], "component_version": key[1],
             "implementation_address": value}
            for key, value in sorted(
                getattr(registry, "v2_implementation_identities", {}).items()
            )
        ]
    }
    contract_bindings = getattr(registry, "contract_bindings", {})
    if contract_bindings:
        closure_document["contract_bindings"] = [
            _plain(contract_bindings[key].document) for key in sorted(contract_bindings)
        ]
    expected_closure = content_address(closure_document)
    if graph.implementation_closure_address != expected_closure \
            or not is_content_address(getattr(graph, "authored_ir_address", None)):
        raise ResearchExecutionRefusal("graph implementation/authored identity differs")


def _verify_dataset_policy(dataset, resource_plan, document):
    _verify_policy_dataset_selection(dataset, document)
    manifest = dataset.manifest
    if manifest.owner_id != document["owner_id"] or manifest.mode != "RESEARCH" \
            or _dataset_truth_snapshots(dataset) \
            != tuple(document["truth_snapshot_addresses"]):
        raise ResearchExecutionRefusal("dataset owner/mode/truth authority differs")
    if document["adjustment_policy_address"] != manifest.adjustment_policy_address \
            or document["missing_data_policy_address"] != manifest.missing_data_policy_address \
            or document["alignment_policy_address"] != manifest.alignment_policy_address:
        raise ResearchExecutionRefusal("evaluation and dataset policy identities differ")
    _verify_bound_dataset_policy(dataset, resource_plan, document)


def _verify_policy_dataset_selection(dataset, document):
    if dataset.input_sources is None:
        if document["schema"] != "research-evaluation-policy/1":
            raise ResearchExecutionRefusal("scalar dataset requires its original policy version")
        return
    if document["schema"] != "research-evaluation-policy/2" \
            or document.get("dataset_selection_address") != dataset.dataset_selection_address \
            or document.get("primary_input") != dataset.primary_input \
            or _plain(document.get("source_policies")) != _source_policies(dataset):
        raise ResearchExecutionRefusal("research policy does not bind the verified input set")


def _verify_bound_dataset_policy(dataset, resource_plan, document):
    if dataset.input_bindings is not None:
        if resource_plan.input_bindings != dataset.input_bindings:
            raise ResearchExecutionRefusal("dataset and ResourcePlan input bindings differ")
        if document["session_policy_address"] != dataset.session_policy_address \
                or document["resampling_policy_address"] != dataset.resampling_policy_address:
            raise ResearchExecutionRefusal("dataset-derived session/resampling identity differs")


def _verify_policy_bindings(graph, dataset, document):
    graph_inputs = set(getattr(graph, "graph_inputs", {}))
    if graph_inputs != set(dataset.inputs) or graph_inputs != set(document["input_bindings"]):
        raise ResearchExecutionRefusal("graph, dataset and policy input universes differ")
    for name, binding in document["input_bindings"].items():
        _verify_input_binding(dataset, name, binding)


def _policy_input_manifest(dataset, name):
    return (dataset.manifest if dataset.input_sources is None
            else dataset.input_sources[name].manifest)


def _verify_input_binding(dataset, name, binding):
    manifest = _policy_input_manifest(dataset, name)
    fields = (binding["field"],) if "field" in binding else tuple(binding["fields"])
    if binding["instrument_address"] not in manifest.instrument_addresses \
            or any(field not in manifest.fields for field in fields):
        raise ResearchExecutionRefusal("input binding is outside verified dataset authority")
    if dataset.input_bindings is not None:
        source = dataset.input_bindings.document["inputs"].get(name)
        if source is None or source["binding_address"] != binding.get("binding_address") \
                or tuple(source["binding"]["fields"]) != fields:
            raise ResearchExecutionRefusal("policy input binding differs from verified source")


def _verify_input_window(graph, registry, dataset, document):
    index = _authority_event_index(graph, registry, dataset.inputs)
    if index is not None:
        start = _aware(index[0].isoformat(), "input start")
        end = _aware(index[-1].isoformat(), "input end")
        policy_start = _aware(document["event_start"], "event_start")
        policy_end = _aware(document["event_end"], "event_end")
        manifest_start, manifest_end = _manifest_clock_window(dataset)
        if len(index) > document["maximum_events"]:
            raise ResearchExecutionRefusal("event count exceeds evaluation policy")
        if policy_start < manifest_start or policy_end > manifest_end \
                or start < policy_start or end >= policy_end \
                or start < manifest_start or end >= manifest_end:
            raise ResearchExecutionRefusal("research input timestamps escape accepted windows")


def _manifest_clock_window(dataset):
    if getattr(dataset, "input_sources", None) is not None:
        return _manifest_clock_window(dataset.input_sources[dataset.primary_input])
    manifest = dataset.manifest
    if dataset.source_codec == "strategy-os-observation-candle-index/2":
        return _retrospective_clock_window(dataset)
    if dataset.source_codec == "strategy-os-observation-candle-index/1":
        start, end = manifest.availability_start, manifest.availability_end
    else:
        start, end = manifest.event_start, manifest.event_end
    return _aware(start, "manifest window start"), _aware(end, "manifest window end")


def _retrospective_clock_window(dataset):
    if dataset.input_bindings is None:
        raise ResearchExecutionRefusal("retrospective evaluation requires verified input bindings")
    entries = dataset.input_bindings.document["inputs"].values()
    seconds = [entry["binding"]["timeframe"] for entry in entries]
    if not seconds or any(type(value) is not int or value <= 0 for value in seconds) \
            or len(set(seconds)) != 1:
        raise ResearchExecutionRefusal("retrospective evaluation requires one verified timeframe")
    manifest = dataset.manifest
    try:
        duration = dt.timedelta(seconds=seconds[0])
        return (_aware(manifest.event_start, "manifest event start") + duration,
                _aware(manifest.event_end, "manifest event end") + duration)
    except OverflowError as exc:
        raise ResearchExecutionRefusal("retrospective evaluation timeframe exceeds timestamp bounds") from exc


def _authority_event_index(
    graph: ResolvedV2Graph,
    registry: PlatformRegistry,
    inputs: Mapping[str, Any],
) -> pd.DatetimeIndex | None:
    try:
        return _common_index(graph, inputs, registry)
    except IncrementalRuntimeRefusal as exc:
        raise ResearchExecutionRefusal("research input index is not one causal clock") from exc


def _validate_graph_registry(graph: Any, registry: PlatformRegistry) -> None:
    if type(graph) is not ResolvedV2Graph or graph.topology_document is None:
        raise ResearchExecutionRefusal("exact resolved v2 topology authority is required")
    try:
        reconstructed = ResolvedV2Graph(
            graph.nodes, graph.bundles, graph.outputs, graph.graph_inputs,
            format_version=graph.format_version,
            registry_snapshot_address=graph.registry_snapshot_address,
            resolved_graph_address=graph.resolved_graph_address,
            implementation_closure_address=graph.implementation_closure_address,
            authored_ir_address=graph.authored_ir_address,
            registry_snapshot_payload=graph.registry_snapshot_payload,
            data_requirement_declaration_closure=graph.data_requirement_declaration_closure,
            topology_document=graph.topology_document,
            authored_executable_address=graph.authored_executable_address,
        )
        address = resolved_v2_graph_address(
            reconstructed.nodes, reconstructed.registry_snapshot_address,
            reconstructed.implementation_closure_address,
            reconstructed.registry_snapshot_payload,
            reconstructed.data_requirement_declaration_closure,
        )
    except (ResolutionError, TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("resolved graph topology did not reconstruct") from exc
    if address != graph.resolved_graph_address \
            or reconstructed.topology_document != graph.topology_document \
            or graph.registry_snapshot_payload != registry.registry_snapshot_payload \
            or content_address(_plain(registry.registry_snapshot_payload)) \
            != registry.registry_snapshot_address:
        raise ResearchExecutionRefusal("resolved graph or registry snapshot identity differs")
    registrations = registry.v2_implementation_registrations
    marker = []
    for key in sorted(registrations):
        registration = registrations[key]
        actual = registry.v2_implementations.get(key)
        if actual is not registration.implementation \
                or registry.v2_implementation_identities.get(key) \
                != registration.implementation_address:
            raise ResearchExecutionRefusal(
                "registry callable differs from implementation closure"
            )
        marker.append((key, id(actual), registration.implementation_address))
    marker = tuple(marker)
    if _CALLABLE_CLOSURE_CACHE.get(registry) != marker:
        keys_to_hash = tuple(sorted(registrations))
    else:
        keys_to_hash = tuple(sorted({node.component for node in graph.nodes}))
    for key in keys_to_hash:
        registration = registrations.get(key)
        actual = registry.v2_implementations.get(key)
        try:
            actual_address = implementation_address(
                actual, registration.dependency_boundary,
            )
        except (ImplementationUnidentified, TypeError, ValueError) as exc:
            raise ResearchExecutionRefusal("registry callable identity is unavailable") from exc
        if actual_address != registration.implementation_address \
                or registry.v2_implementation_identities.get(key) != actual_address:
            raise ResearchExecutionRefusal("registry callable differs from implementation closure")
    _CALLABLE_CLOSURE_CACHE[registry] = marker


def _validate_policy(policy: ResearchEvaluationPolicy) -> None:
    try:
        parser = (research_input_set_evaluation_policy
                  if policy.document.get("schema") == "research-evaluation-policy/2"
                  else research_evaluation_policy)
        reconstructed = parser(_plain(policy.document))
    except (AttributeError, TypeError, ResearchExecutionRefusal) as exc:
        raise ResearchExecutionRefusal("evaluation policy no longer reconstructs") from exc
    if reconstructed != policy:
        raise ResearchExecutionRefusal("evaluation policy wrapper is stale")


def _verified_scalar_payload(dataset):
    try:
        if DatasetManifest.from_bytes(dataset.manifest.canonical_bytes) != dataset.manifest:
            raise ValueError
        ordered = verify_dataset_manifest(dataset.manifest, dataset.segment_objects)
        decoded = None
        if dataset.source_codec == "canonical-research-inputs/1":
            combined = b"".join(
                dataset.segment_objects[address][1]
                for address in dataset.manifest.segment_addresses
            )
            decoded = _decode_research_inputs(combined)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ResearchExecutionRefusal("verified dataset proof no longer reconstructs") from exc
    return ordered, decoded


def _validate_verified_dataset(dataset: VerifiedDatasetInputs) -> None:
    if dataset.input_sources is not None:
        _validate_verified_input_set(dataset)
        return
    ordered, decoded = _verified_scalar_payload(dataset)
    digest = content_address({
        "schema": "verified-research-inputs/1",
        "dataset_manifest_address": dataset.manifest.manifest_address,
        "inputs": _stable_value(dataset.inputs),
    })
    derivation_address = content_address({"algorithm": (
        "phase5-canonical-research-inputs" if dataset.source_codec == "canonical-research-inputs/1"
        else "verified-observation-availability-projection"), "version": 1})
    if ordered != dataset.segments or decoded is not None and not _equal(decoded, dataset.inputs) \
            or digest != dataset.input_digest \
            or derivation_address != dataset.derivation_address:
        raise ResearchExecutionRefusal("verified dataset wrapper is stale or mutated")


def _result(
    graph: Any, registry: Any, plan: AcceptedResearchResourcePlan,
    dataset: VerifiedDatasetInputs, policy: ResearchEvaluationPolicy,
    *, status: str, batch: Mapping[str, Any], incremental: Mapping[str, Any],
    output_digest: str | None, event_count: int,
    last_event_address: str | None, last_event_time: str | None,
) -> ResearchRunResult:
    components = sorted({
        f"{node.component[0]}@{node.component[1]}" for node in graph.nodes
    })
    document = {
        "schema": "phase5-research-run-result/1",
        "status": status,
        "owner_id": policy.document["owner_id"],
        "authored_ir_address": graph.authored_ir_address,
        "resolved_graph_address": graph.resolved_graph_address,
        "registry_snapshot_address": registry.registry_snapshot_address,
        "implementation_closure_address": graph.implementation_closure_address,
        "dataset_manifest_address": dataset.manifest.manifest_address,
        "dataset_input_digest": dataset.input_digest,
        "input_derivation_address": dataset.derivation_address,
        "node_context_resolver_address": policy.document[
            "node_context_resolver_address"
        ],
        "truth_snapshot_addresses": list(policy.document["truth_snapshot_addresses"]),
        "evaluation_policy_address": policy.policy_address,
        "resource_plan_address": plan.plan_address,
        "data_requirement_plan_address": plan.document["data_requirement_plan_address"],
        "run_authority_address": policy.document["run_authority_address"],
        "node_components": components,
        "node_contract_addresses": list(plan.document["node_contract_addresses"]),
        "event_count": event_count,
        "last_event_address": last_event_address,
        "last_event_time": last_event_time,
        "output_digest": output_digest,
        "cancellation_state": "CANCELLED" if status == "CANCELLED" else "NOT_CANCELLED",
    }
    if dataset.input_sources is not None:
        document.update({
            "schema": "phase5-research-run-result/2",
            "dataset_selection_address": dataset.dataset_selection_address,
            "primary_input": dataset.primary_input,
            "source_policies": _plain(policy.document["source_policies"]),
        })
    address = content_address(document)
    frozen = _freeze({**document, "result_address": address})
    return ResearchRunResult(
        frozen, address, _freeze(_stable_value(batch)),
        _freeze(_stable_value(incremental)),
    )


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, pd.Series) and isinstance(right, pd.Series):
        return left.equals(right)
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(_equal(left[key], right[key]) for key in left)
    if isinstance(left, tuple) and isinstance(right, tuple):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _materialize_outputs(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _materialize_value(item) for key, item in value.items()}


def _materialize_value(value: Any) -> Any:
    if isinstance(value, Mapping) and value.get("schema") == "state-series-result/1":
        return StateSeriesResult(
            tuple(_materialize_value(item) for item in value["values"]),
            _materialize_value(value["state_payload"]),
            value["last_event_time"],
        )
    if isinstance(value, Mapping) and value.get("schema") == "pandas-series/1":
        return pd.Series(
            [_materialize_value(item) for item in value["values"]],
            index=pd.DatetimeIndex(value["index"]),
        )
    if isinstance(value, Mapping) and value.get("schema") == "numeric-value/1":
        from app.ir.validity import NumericValue, ValidityState
        return NumericValue(
            ValidityState(value["state"]), _materialize_value(value["value"]),
            tuple(ValidityState(item) for item in value["causes"]),
        )
    if isinstance(value, Mapping):
        return {key: _materialize_value(item) for key, item in value.items()}
    if isinstance(value, list): return tuple(_materialize_value(item) for item in value)
    if isinstance(value, tuple): return tuple(_materialize_value(item) for item in value)
    return value


def _decode_research_inputs(payload: bytes) -> Mapping[str, Any]:
    if not isinstance(payload, bytes) or not payload:
        raise ResearchExecutionRefusal("verified research input bytes are absent")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResearchExecutionRefusal(
            "verified research input bytes are not canonical JSON"
        ) from exc
    if not isinstance(document, Mapping) \
            or set(document) != {"schema", "inputs"} \
            or document.get("schema") != "canonical-research-inputs/1" \
            or canonical_json(document).encode("utf-8") != payload:
        raise ResearchExecutionRefusal(
            "verified research input bytes use an open or noncanonical schema"
        )
    inputs = _materialize_value(document["inputs"])
    if not isinstance(inputs, Mapping) or not inputs:
        raise ResearchExecutionRefusal("verified research inputs are absent")
    if canonical_research_input_bytes(inputs) != payload:
        raise ResearchExecutionRefusal(
            "verified research inputs do not round-trip canonically"
        )
    return inputs


def _copy_materialized(value: Any) -> Any:
    if isinstance(value, pd.Series): return value.copy(deep=True)
    if isinstance(value, Mapping):
        return {key: _copy_materialized(item) for key, item in value.items()}
    if isinstance(value, tuple): return tuple(_copy_materialized(item) for item in value)
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
        return {"schema": "numeric-value/1", "state": value.state.value, "value": _stable_value(value.value),
                "causes": [item.value for item in value.causes]}
    if isinstance(value, pd.Series):
        return {"schema": "pandas-series/1", "index": [item.isoformat() for item in value.index],
                "values": [_stable_value(item) for item in value.tolist()]}
    if isinstance(value, Mapping):
        return {key: _stable_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple): return [_stable_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)): return value
    if isinstance(value, float) and math.isfinite(value): return value
    raise ResearchExecutionRefusal("research values are not closed finite data")


def _addresses(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not value:
        raise ResearchExecutionRefusal(f"{label} are absent")
    result = tuple(value)
    if result != tuple(sorted(set(result))):
        raise ResearchExecutionRefusal(f"{label} must be sorted and unique")
    for item in result: _address(item, label)
    return result


def _address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not is_content_address(value):
        raise ResearchExecutionRefusal(f"{label} must be a content address")
    return value


def _aware(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ResearchExecutionRefusal(f"{label} must be an aware timestamp")
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchExecutionRefusal(f"{label} is malformed") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ResearchExecutionRefusal(f"{label} must be timezone-aware")
    return result.astimezone(dt.UTC)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping): return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple): return [_plain(item) for item in value]
    return value


__all__ = [
    "NODE_CONTEXT_RESOLVER_ADDRESS", "ResearchEvaluationPolicy",
    "ResearchExecutionRefusal", "ResearchRunResult",
    "VerifiedDatasetInputs", "accept_research_snapshot_context",
    "canonical_research_input_bytes", "execute_research", "research_evaluation_policy",
    "input_set_policy_fields", "research_input_set_evaluation_policy",
    "evaluate_stateful_restart", "registered_research_universe",
    "require_complete_research_case_universe",
    "verify_research_dataset",
]
