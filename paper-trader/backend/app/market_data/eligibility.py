"""Pure V0 graph-to-dataset eligibility compilation.

This module consumes existing immutable graph, binding, dataset, instrument and
provider-authority facts.  It performs no loading, persistence, provider choice,
network access, caching, evaluation, or fallback.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from app.backtest.dataset_store import DatasetManifest, DatasetSegment, verify_dataset_manifest
from app.ir.first_party.analytical_v2.contracts import (
    ContractInputBindings,
    validate_input_bindings,
)
from app.ir.hashing import content_address
from app.ir.v2_graph_versions import V2GraphFacts, require_row_matches
from app.market_data.capability import (
    CapabilityProfile,
    CapabilityRefusal,
    ProviderConformance,
    assess_capability,
    verify_profile_conformance,
)
from app.market_data.requirements import (
    DataRequirementPlan,
    DataRequirementRefusal,
    verify_data_requirement_plan,
)
from app.market_truth.identity import CanonicalPhysicalInstrument, ProviderContract


MAX_DATASETS = 32
MAX_REQUIREMENTS = 10_000
MAX_REQUEST_SECONDS = 366 * 24 * 60 * 60
MAX_TOTAL_ROWS = 1_000_000
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_DEPTH_LEVELS = 5
_HISTORICAL_BOOK_FIELDS = frozenset({"BID", "ASK", "BID_SIZE", "ASK_SIZE", "TRADE"})
_CASH_VENUES = frozenset({"XNSE", "XBOM"})


class PrivateEligibilityUnavailable(LookupError):
    """Missing and foreign facts deliberately share one private absence."""


class EligibilityCode(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_RANGE = "INSUFFICIENT_RANGE"
    INSUFFICIENT_RESOLUTION = "INSUFFICIENT_RESOLUTION"
    INSUFFICIENT_FRESHNESS = "INSUFFICIENT_FRESHNESS"
    INSUFFICIENT_SESSION = "INSUFFICIENT_SESSION"
    INSUFFICIENT_ALIGNMENT = "INSUFFICIENT_ALIGNMENT"
    INSUFFICIENT_DEPTH = "INSUFFICIENT_DEPTH"
    ENTITLEMENT_UNVERIFIED = "ENTITLEMENT_UNVERIFIED"
    HISTORY_GAP = "HISTORY_GAP"
    EXPIRED_OPTIONS_HISTORY_UNAVAILABLE = "EXPIRED_OPTIONS_HISTORY_UNAVAILABLE"
    HISTORICAL_DEPTH_UNAVAILABLE = "HISTORICAL_DEPTH_UNAVAILABLE"
    HISTORICAL_ORDER_FLOW_UNAVAILABLE = "HISTORICAL_ORDER_FLOW_UNAVAILABLE"
    UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION = "UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION"
    RESOURCE_BOUND = "RESOURCE_BOUND"


@dataclass(frozen=True)
class EligibilityRequest:
    owner_id: str
    mode: str
    requested_start: dt.datetime
    requested_end: dt.datetime
    as_of: dt.datetime

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id or len(self.owner_id) > 64:
            raise ValueError("eligibility owner is invalid")
        if self.mode != "RESEARCH":
            raise ValueError("V0 eligibility is research-only")
        values = []
        for name in ("requested_start", "requested_end", "as_of"):
            value = getattr(self, name)
            if (not isinstance(value, dt.datetime) or value.tzinfo is None
                    or value.utcoffset() is None or value.microsecond):
                raise ValueError(f"{name} must be a whole UTC second")
            values.append(value.astimezone(dt.timezone.utc))
        if not values[0] < values[1] <= values[2]:
            raise ValueError("eligibility interval or as-of order is invalid")
        for name, value in zip(("requested_start", "requested_end", "as_of"), values, strict=True):
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class SelectedDataset:
    manifest: DatasetManifest
    segments: Mapping[str, tuple[DatasetSegment, bytes]]
    instrument: CanonicalPhysicalInstrument

    def __post_init__(self) -> None:
        if (not isinstance(self.manifest, DatasetManifest)
                or not isinstance(self.instrument, CanonicalPhysicalInstrument)
                or not isinstance(self.segments, Mapping)):
            raise ValueError("selected dataset authority is incomplete")
        object.__setattr__(self, "segments", MappingProxyType(dict(self.segments)))


@dataclass(frozen=True)
class EligibilityRefusal:
    code: EligibilityCode
    selector: str | None
    detail: str


@dataclass(frozen=True, init=False)
class EligibilityResult:
    owner_id: str
    graph_identifier: str
    graph_version: int
    graph_content_address: str
    resolved_graph_address: str
    plan_address: str
    registry_snapshot_address: str
    input_binding_context_address: str
    capability_profile_address: str
    conformance_address: str
    provider_contract_address: str
    dataset_manifest_addresses: tuple[str, ...]
    instrument_addresses: tuple[str, ...]
    truth_snapshot_addresses: tuple[str, ...]
    policy_addresses: tuple[str, ...]
    requested_start: dt.datetime
    requested_end: dt.datetime
    as_of: dt.datetime
    status: str
    refusals: tuple[EligibilityRefusal, ...]
    eligibility_address: str

    def __init__(self, *_args, **_kwargs) -> None:
        raise TypeError("eligibility results may only be constructed by the compiler")


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name)) for name in value.__dataclass_fields__}
    return value


def _result(*, request: EligibilityRequest, graph: V2GraphFacts,
            plan: DataRequirementPlan, input_bindings: ContractInputBindings,
            profile: CapabilityProfile, conformance: ProviderConformance,
            provider_contract: ProviderContract, datasets: tuple[SelectedDataset, ...],
            refusals: list[EligibilityRefusal]) -> EligibilityResult:
    manifests = tuple(sorted(item.manifest.manifest_address for item in datasets))
    instruments = tuple(sorted(item.instrument.address for item in datasets))
    truths = tuple(sorted({address for item in datasets
                           for address in item.manifest.truth_snapshot_addresses}))
    policies = tuple(sorted({address for item in datasets for address in (
        item.manifest.alignment_policy_address,
        item.manifest.missing_data_policy_address,
        item.manifest.adjustment_policy_address,
        item.manifest.roll_policy_address,
    )}))
    ordered = tuple(sorted(set(refusals), key=lambda item: (
        item.code.value, item.selector or "", item.detail)))
    payload = {
        "schema": "graph-data-eligibility/1", "owner_id": request.owner_id,
        "mode": request.mode, "graph_identifier": graph.graph_identifier,
        "graph_version": graph.graph_version, "graph_content_address": graph.content_address,
        "resolved_graph_address": plan.resolved_graph_address,
        "plan_address": plan.plan_address,
        "registry_snapshot_address": plan.registry_snapshot_address,
        "input_binding_context_address": input_bindings.context_address,
        "capability_profile_address": profile.capability_profile_address,
        "conformance_address": conformance.address,
        "provider_contract_address": provider_contract.address,
        "dataset_manifest_addresses": manifests, "instrument_addresses": instruments,
        "truth_snapshot_addresses": truths, "policy_addresses": policies,
        "requested_start": request.requested_start,
        "requested_end": request.requested_end, "as_of": request.as_of,
        "status": "REFUSED" if ordered else "SUPPORTED", "refusals": ordered,
    }
    address = content_address(_plain(payload))
    values = {
        "owner_id": request.owner_id, "graph_identifier": graph.graph_identifier,
        "graph_version": graph.graph_version, "graph_content_address": graph.content_address,
        "resolved_graph_address": plan.resolved_graph_address, "plan_address": plan.plan_address,
        "registry_snapshot_address": plan.registry_snapshot_address,
        "input_binding_context_address": input_bindings.context_address,
        "capability_profile_address": profile.capability_profile_address,
        "conformance_address": conformance.address,
        "provider_contract_address": provider_contract.address,
        "dataset_manifest_addresses": manifests, "instrument_addresses": instruments,
        "truth_snapshot_addresses": truths, "policy_addresses": policies,
        "requested_start": request.requested_start, "requested_end": request.requested_end,
        "as_of": request.as_of, "status": payload["status"], "refusals": ordered,
        "eligibility_address": address,
    }
    result = object.__new__(EligibilityResult)
    for name in EligibilityResult.__dataclass_fields__:
        object.__setattr__(result, name, values[name])
    return result


def _refuse(code: EligibilityCode, detail: str, selector: str | None = None) -> EligibilityRefusal:
    return EligibilityRefusal(code, selector, detail)


def _private() -> None:
    raise PrivateEligibilityUnavailable("eligibility authority is unavailable")


def _require_owner(request: EligibilityRequest, graph: V2GraphFacts,
                   input_bindings: ContractInputBindings,
                   profile: CapabilityProfile, contract: ProviderContract,
                   datasets: tuple[SelectedDataset, ...]) -> None:
    owners = {graph.owner_id, input_bindings.document.get("owner_id"), profile.owner_id,
              contract.owner_id, *(item.manifest.owner_id for item in datasets)}
    if owners != {request.owner_id}:
        _private()


def _dataset_refusals(
    request: EligibilityRequest,
    plan: DataRequirementPlan,
    input_bindings: ContractInputBindings,
    datasets: tuple[SelectedDataset, ...],
    profile: CapabilityProfile,
) -> tuple[list[EligibilityRefusal], dict[str, Mapping[str, Any]]]:
    refusals: list[EligibilityRefusal] = []
    inputs = input_bindings.document["inputs"]
    binding_rows = {name: entry["binding"] for name, entry in inputs.items()}
    for item in datasets:
        try:
            if (DatasetManifest.from_bytes(item.manifest.canonical_bytes) != item.manifest
                    or CanonicalPhysicalInstrument.from_bytes(
                        item.instrument.canonical_bytes) != item.instrument):
                raise ValueError("canonical bytes do not reconstruct")
            verify_dataset_manifest(item.manifest, item.segments)
        except (TypeError, ValueError):
            _private()
        if item.manifest.instrument_addresses != (item.instrument.address,):
            _private()
    expected_manifests = {row["dataset_manifest_address"] for row in binding_rows.values()}
    selected_manifests = {item.manifest.manifest_address for item in datasets}
    if expected_manifests != selected_manifests:
        refusals.append(_refuse(
            EligibilityCode.UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION,
            "selected instruments/manifests differ from the graph-pinned input binding",
        ))
        return refusals, binding_rows

    selected = {item.manifest.manifest_address: item for item in datasets}
    for item in datasets:
        manifest = item.manifest
        if manifest.mode != request.mode:
            refusals.append(_refuse(EligibilityCode.UNAVAILABLE,
                "dataset mode does not cover the requested mode"))
        if item.instrument.asset_class == "OPTION":
            refusals.append(_refuse(EligibilityCode.EXPIRED_OPTIONS_HISTORY_UNAVAILABLE,
                "broad historical options authority is unavailable in V0"))
        elif not (item.instrument.asset_class == "EQUITY"
                  and item.instrument.contract_kind == "SPOT"
                  and item.instrument.currency == "INR"
                  and item.instrument.venue_code in _CASH_VENUES):
            refusals.append(_refuse(EligibilityCode.UNAVAILABLE,
                "instrument is outside the exact V0 NSE/BSE INR cash subset"))
        if (dt.datetime.fromisoformat(manifest.recorded_at) > request.as_of
                or dt.datetime.fromisoformat(manifest.availability_end) > request.as_of):
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_FRESHNESS,
                "dataset was not recorded by the requested as-of"))

    for record in plan.requirements:
        requirement = record["requirement"]
        selector = content_address({
            "authored_node_id": record["authored_node_id"],
            "lowered_path": list(record["lowered_path"]),
            "leaf_component": {"component_id": record["leaf_component"][0],
                               "component_version": record["leaf_component"][1]},
            "requirement": _plain(requirement),
        })
        role = requirement["instrument"]["role"]
        candidates = [row for row in binding_rows.values()
                      if row["instrument"]["role"] == role]
        if len(candidates) != 1:
            refusals.append(_refuse(EligibilityCode.UNAVAILABLE,
                "graph role lacks one exact canonical input", selector))
            continue
        binding = candidates[0]
        item = selected[binding["dataset_manifest_address"]]
        manifest = item.manifest
        expected_binding_type = (
            "ECONOMIC_SELECTOR" if item.instrument.asset_class == "OPTION" else "PHYSICAL"
        )
        if (_plain(binding["instrument"]) != _plain(requirement["instrument"])
                or binding["instrument"]["type"] != expected_binding_type
                or binding["canonical_instrument_address"] != item.instrument.address
                or binding["market_truth_address"] not in manifest.truth_snapshot_addresses):
            refusals.append(_refuse(
                EligibilityCode.UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION,
                "canonical input type/instrument/truth differs from the graph version",
                selector))
            continue
        field = requirement["field"]
        if field not in binding["fields"] or field not in manifest.fields:
            refusals.append(_refuse(EligibilityCode.UNAVAILABLE,
                "dataset does not contain the required field", selector))
        if binding["timeframe"] != requirement["timeframe"]:
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_RESOLUTION,
                "dataset binding resolution differs from the requirement", selector))
        if binding["session"] != requirement["session"]:
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_SESSION,
                "dataset binding session differs from the requirement", selector))
        if _plain(binding["alignment"]) != _plain(requirement["alignment"]):
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_ALIGNMENT,
                "dataset binding alignment differs from the requirement", selector))
        if _plain(binding["depth"]) != _plain(requirement["depth"]):
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_DEPTH,
                "dataset binding depth differs from the requirement", selector))
        if binding["freshness"]["maximum_age_seconds"] > requirement["freshness"]["maximum_age_seconds"]:
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_FRESHNESS,
                "dataset binding freshness exceeds the requirement", selector))
        bars = requirement["history"]["minimum_bars"] + requirement["history"]["warmup_bars"]
        required_start = request.requested_start - dt.timedelta(
            seconds=bars * requirement["timeframe"])
        interval_offers = [offer for offer in profile.offers if (
            offer["known"] and offer["entitled"]
            and offer["field"] == requirement["field"]
            and _plain(offer["instrument"]) == _plain(requirement["instrument"])
            and requirement["timeframe"] in offer["timeframes"]
            and offer["session"] == requirement["session"]
            and _plain(offer["alignment"]) == _plain(requirement["alignment"])
            and offer["derived_local"] == requirement["derived_local"]
            and offer["depth"]["kind"] == requirement["depth"]["kind"]
            and dt.datetime.fromisoformat(offer["available_from"]) <= required_start
            and dt.datetime.fromisoformat(offer["available_to"]) >= request.requested_end
        )]
        if not interval_offers:
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_RANGE,
                "provider capability does not cover the requested interval plus warmup",
                selector))
        event_start = dt.datetime.fromisoformat(manifest.event_start)
        event_end = dt.datetime.fromisoformat(manifest.event_end)
        if event_start > required_start or event_end < request.requested_end:
            refusals.append(_refuse(EligibilityCode.INSUFFICIENT_RANGE,
                "dataset does not cover the requested interval plus graph warmup", selector))
        for gap in manifest.gaps:
            left = dt.datetime.fromisoformat(gap["start"])
            right = dt.datetime.fromisoformat(gap["end"])
            if (gap["instrument_address"] == item.instrument.address
                    and gap["field"] == field and left < request.requested_end
                    and right > required_start):
                refusals.append(_refuse(EligibilityCode.HISTORY_GAP,
                    "required dataset interval contains an explicit gap", selector))
        if requirement["depth"]["kind"] != "NONE":
            refusals.append(_refuse(EligibilityCode.HISTORICAL_DEPTH_UNAVAILABLE,
                "historical depth is unavailable in V0", selector))
        if field in _HISTORICAL_BOOK_FIELDS:
            refusals.append(_refuse(EligibilityCode.HISTORICAL_ORDER_FLOW_UNAVAILABLE,
                "historical order-flow fields are unavailable in V0", selector))
    return refusals, binding_rows


def compile_graph_data_eligibility(
    *, request: EligibilityRequest, graph: V2GraphFacts, resolved_graph: Any,
    plan: DataRequirementPlan, input_bindings: ContractInputBindings,
    datasets: tuple[SelectedDataset, ...], profile: CapabilityProfile,
    conformance: ProviderConformance, provider_contract: ProviderContract,
    registry: Any = None,
) -> EligibilityResult:
    """Compile one deterministic eligibility/refusal before any consumer side effect."""
    if (not isinstance(request, EligibilityRequest) or not isinstance(graph, V2GraphFacts)
            or type(plan) is not DataRequirementPlan
            or not isinstance(input_bindings, ContractInputBindings)
            or not isinstance(profile, CapabilityProfile)
            or not isinstance(conformance, ProviderConformance)
            or not isinstance(provider_contract, ProviderContract)
            or not isinstance(datasets, tuple)
            or any(not isinstance(item, SelectedDataset) for item in datasets)):
        _private()
    _require_owner(request, graph, input_bindings, profile, provider_contract, datasets)
    dataset_addresses = tuple(
        item.manifest.manifest_address for item in datasets
    )
    total_rows = sum(
        segment.row_end - segment.row_start
        for item in datasets for segment, _payload in item.segments.values()
    ) if datasets else 0
    total_bytes = sum(item.manifest.aggregate_byte_length for item in datasets) \
        if datasets else 0
    excessive_depth = any(
        record["requirement"]["depth"]["kind"] == "BOOK"
        and record["requirement"]["depth"]["levels"] > MAX_DEPTH_LEVELS
        for record in plan.requirements
    )
    if (not 0 < len(datasets) <= MAX_DATASETS or len(plan.requirements) > MAX_REQUIREMENTS
            or len(set(dataset_addresses)) != len(dataset_addresses)
            or total_rows > MAX_TOTAL_ROWS or total_bytes > MAX_TOTAL_BYTES
            or excessive_depth
            or (request.requested_end - request.requested_start).total_seconds()
            > MAX_REQUEST_SECONDS):
        refusal = [_refuse(EligibilityCode.RESOURCE_BOUND,
            "eligibility request exceeds the closed V0 resource boundary")]
        return _result(request=request, graph=graph, plan=plan,
            input_bindings=input_bindings, profile=profile, conformance=conformance,
            provider_contract=provider_contract,
            datasets=datasets, refusals=refusal)
    try:
        require_row_matches(graph, graph)
        if (graph.content_address != plan.authored_ir_address
                or graph.registry_snapshot_address != plan.registry_snapshot_address):
            raise ValueError("graph identity differs from its data plan")
        if registry is None:
            verify_data_requirement_plan(plan, resolved_graph)
        else:
            verify_data_requirement_plan(
                plan, resolved_graph, registry=registry,
                input_bindings=input_bindings,
            )
        validate_input_bindings(input_bindings)
    except (AttributeError, TypeError, ValueError, DataRequirementRefusal):
        _private()
    refusals, _bindings = _dataset_refusals(
        request, plan, input_bindings, datasets, profile)
    selection_address = content_address({"dataset_manifest_addresses": sorted(
        item.manifest.manifest_address for item in datasets)})
    truth_address = content_address({"truth_snapshot_addresses": sorted({
        address for item in datasets for address in item.manifest.truth_snapshot_addresses})})
    policy_address = content_address({"policy_addresses": sorted({
        address for item in datasets for address in (
            item.manifest.alignment_policy_address, item.manifest.missing_data_policy_address,
            item.manifest.adjustment_policy_address, item.manifest.roll_policy_address)})})
    try:
        if (profile.owner_id != request.owner_id or profile.mode != request.mode
                or any(item.manifest.capability_profile_address
                       != profile.capability_profile_address for item in datasets)
                or conformance.result != "PASS"
                or conformance.address != profile.conformance_evidence_address
                or provider_contract.address != profile.provider_contract_address
                or provider_contract.product_address != profile.provider_product_address
                or any(item.manifest.provider_product_addresses != (provider_contract.product_address,)
                       or item.manifest.provider_contract_addresses != (provider_contract.address,)
                       for item in datasets)):
            raise CapabilityRefusal("typed provider evidence differs")
        verify_profile_conformance(profile, conformance)
        assessment = assess_capability(
            plan=plan, profile=profile, owner_id=request.owner_id, mode=request.mode,
            dataset_manifest_address=selection_address,
            market_truth_snapshot_address=truth_address,
            evaluation_policy_address=policy_address,
            assessment_evidence_address=conformance.address,
            at_time=int(request.as_of.timestamp()), conformance=conformance,
            provider_contract=provider_contract,
        )
        mapping = {
            "UNAVAILABLE": EligibilityCode.ENTITLEMENT_UNVERIFIED,
            "UNKNOWN": EligibilityCode.UNAVAILABLE,
            "INSUFFICIENT_RANGE": EligibilityCode.INSUFFICIENT_RANGE,
            "INSUFFICIENT_RESOLUTION": EligibilityCode.INSUFFICIENT_RESOLUTION,
            "INSUFFICIENT_FRESHNESS": EligibilityCode.INSUFFICIENT_FRESHNESS,
        }
        for row in assessment.requirement_results:
            if row["result"] != "SATISFIED":
                refusals.append(_refuse(mapping[row["result"]], row["reason"], row["selector"]))
    except (CapabilityRefusal, TypeError, ValueError):
        refusals.append(_refuse(EligibilityCode.ENTITLEMENT_UNVERIFIED,
            "accepted capability profile, conformance, contract, or entitlement is absent"))
    return _result(request=request, graph=graph, plan=plan,
        input_bindings=input_bindings, profile=profile, conformance=conformance,
        provider_contract=provider_contract, datasets=datasets, refusals=refusals)


__all__ = [
    "EligibilityCode", "EligibilityRefusal", "EligibilityRequest", "EligibilityResult",
    "PrivateEligibilityUnavailable", "SelectedDataset", "compile_graph_data_eligibility",
]


@dataclass(frozen=True, init=False)
class BoundEligibilityResult:
    document: Mapping[str, Any]
    refusals: tuple[EligibilityRefusal, ...]

    def __init__(self, *_args, **_kwargs):
        raise TypeError("bound eligibility results may only be constructed by the compiler")

    @property
    def status(self):
        return self.document["status"]

    @property
    def eligibility_address(self):
        return content_address(_plain(self.document))


def _bound_selection_facts(datasets):
    return {
        "dataset_sources": [{"graph_input_id": name, "dataset_manifest_address": item.manifest.manifest_address,
            "canonical_instrument_address": item.instrument.address, "segment_addresses": item.manifest.segment_addresses}
            for name, item in sorted(datasets.items())],
        "truth_snapshot_addresses": sorted({value for item in datasets.values() for value in item.manifest.truth_snapshot_addresses}),
        "policy_addresses": sorted({value for item in datasets.values() for value in (
            item.manifest.alignment_policy_address, item.manifest.missing_data_policy_address,
            item.manifest.adjustment_policy_address, item.manifest.roll_policy_address)}),
    }


def _bound_result(request, graph, plan, input_bindings, datasets, dataset_set_address,
                  evaluation_policy_address, refusals, assessment=None):
    from app.ir.first_party.analytical_v2.contracts import _freeze
    from app.market_data.capability import bound_capability_assessment_envelope
    ordered = tuple(sorted(set(refusals), key=lambda row: (row.code.value, row.selector or "", row.detail)))
    facts = {
        "schema": "graph-data-eligibility/2", "owner_id": request.owner_id, "mode": request.mode,
        "graph_identifier": graph.graph_identifier, "graph_version": graph.graph_version,
        "graph_content_address": graph.content_address, "resolved_graph_address": plan.resolved_graph_address,
        "plan_address": plan.plan_address, "registry_snapshot_address": plan.registry_snapshot_address,
        "input_binding_context_address": input_bindings.context_address,
        "dataset_set_address": dataset_set_address, "evaluation_policy_address": evaluation_policy_address,
        **_bound_selection_facts(datasets),
        "requested_start": request.requested_start, "requested_end": request.requested_end, "as_of": request.as_of,
        "status": "REFUSED" if ordered else "SUPPORTED", "refusals": ordered,
        "capability_assessment": None if assessment is None else bound_capability_assessment_envelope(assessment),
    }
    if not ordered and assessment is None:
        _private()
    result = object.__new__(BoundEligibilityResult)
    object.__setattr__(result, "document", _freeze(_plain(facts)))
    object.__setattr__(result, "refusals", ordered)
    return result


def _bound_types(request, graph, plan, input_bindings, datasets, sources):
    from app.market_data.capability import CapabilitySourceBinding
    valid = (isinstance(request, EligibilityRequest), isinstance(graph, V2GraphFacts),
        type(plan) is DataRequirementPlan, type(input_bindings) is ContractInputBindings,
        isinstance(datasets, Mapping), isinstance(sources, tuple))
    if not all(valid):
        _private()
    if any(type(item) is not SelectedDataset for item in datasets.values()):
        _private()
    if any(type(source) is not CapabilitySourceBinding for source in sources):
        _private()


def _bound_owners(request, graph, input_bindings, datasets, sources):
    owners = {graph.owner_id, input_bindings.document.get("owner_id")}
    owners.update(item.manifest.owner_id for item in datasets.values())
    for source in sources:
        owners.update((source.manifest.owner_id, source.profile.owner_id, source.provider_contract.owner_id,
                       source.source_bindings.document.get("owner_id")))
    if owners != {request.owner_id}:
        _private()
    names = [source.graph_input_id for source in sources]
    if set(datasets) != set(input_bindings.document["inputs"]) or set(names) != set(datasets) or len(names) != len(set(names)):
        _private()


def _bound_resource_refusals(request, plan, datasets):
    rows = sum(segment.row_end - segment.row_start for item in datasets.values() for segment, _ in item.segments.values())
    size = sum(item.manifest.aggregate_byte_length for item in datasets.values())
    checks = (0 < len(datasets) <= MAX_DATASETS, len(plan.requirements) <= MAX_REQUIREMENTS,
        rows <= MAX_TOTAL_ROWS, size <= MAX_TOTAL_BYTES,
        (request.requested_end - request.requested_start).total_seconds() <= MAX_REQUEST_SECONDS)
    if not all(checks):
        return [_refuse(EligibilityCode.RESOURCE_BOUND, "eligibility request exceeds the closed V0 resource boundary")]
    return []


def _bound_graph(graph, plan, resolved_graph, input_bindings, registry):
    require_row_matches(graph, graph)
    if graph.content_address != plan.authored_ir_address or graph.registry_snapshot_address != plan.registry_snapshot_address:
        _private()
    verify_data_requirement_plan(plan, resolved_graph, registry=registry, input_bindings=input_bindings)
    validate_input_bindings(input_bindings)


def _bound_dataset_bytes(item):
    if DatasetManifest.from_bytes(item.manifest.canonical_bytes) != item.manifest:
        _private()
    if CanonicalPhysicalInstrument.from_bytes(item.instrument.canonical_bytes) != item.instrument:
        _private()
    verify_dataset_manifest(item.manifest, item.segments)
    if item.manifest.instrument_addresses != (item.instrument.address,):
        _private()


def _bound_market_refusals(request, item):
    instrument, manifest = item.instrument, item.manifest
    supported = (instrument.asset_class in {"INDEX", "EQUITY"}, instrument.contract_kind == "SPOT",
        instrument.currency == "INR", instrument.venue_code in _CASH_VENUES, manifest.mode == "RESEARCH")
    refusals = []
    if not all(supported):
        refusals.append(_refuse(EligibilityCode.UNAVAILABLE, "source is outside supported INR spot index/equity historical research"))
    if max(dt.datetime.fromisoformat(manifest.recorded_at), dt.datetime.fromisoformat(manifest.availability_end)) > request.as_of:
        refusals.append(_refuse(EligibilityCode.INSUFFICIENT_FRESHNESS, "dataset was not recorded by the requested as-of"))
    return refusals


def _bound_selected_refusals(request, datasets, sources, input_bindings):
    refusals = []
    for source in sources:
        item = datasets[source.graph_input_id]
        _bound_dataset_bytes(item)
        binding = input_bindings.document["inputs"][source.graph_input_id]["binding"]
        if source.manifest != item.manifest or binding["dataset_manifest_address"] != item.manifest.manifest_address:
            refusals.append(_refuse(EligibilityCode.UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION,
                "selected source differs from the graph-pinned manifest"))
        if binding["canonical_instrument_address"] != item.instrument.address or binding["instrument"]["type"] != "PHYSICAL":
            refusals.append(_refuse(EligibilityCode.UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION,
                "selected physical instrument differs from the graph-pinned source"))
        refusals.extend(_bound_market_refusals(request, item))
    return refusals


def _bound_dimensions(requirement, binding, manifest, selector):
    refusals = []
    if requirement["field"] not in binding["fields"] or requirement["field"] not in manifest.fields:
        refusals.append(_refuse(EligibilityCode.UNAVAILABLE, "dataset does not contain the required field", selector))
    dimensions = (("timeframe", EligibilityCode.INSUFFICIENT_RESOLUTION), ("session", EligibilityCode.INSUFFICIENT_SESSION),
        ("alignment", EligibilityCode.INSUFFICIENT_ALIGNMENT), ("depth", EligibilityCode.INSUFFICIENT_DEPTH))
    for field, code in dimensions:
        if _plain(binding[field]) != _plain(requirement[field]):
            refusals.append(_refuse(code, "dataset binding " + field + " differs from the requirement", selector))
    if binding["freshness"]["maximum_age_seconds"] > requirement["freshness"]["maximum_age_seconds"]:
        refusals.append(_refuse(EligibilityCode.INSUFFICIENT_FRESHNESS, "dataset binding freshness exceeds the requirement", selector))
    return refusals


def _bound_offer_interval(source, requirement, start, end):
    from app.market_data.capability import _offer_matches, _offer_complete
    original = source.source_bindings.document["inputs"][source.source_input_id]["binding"]
    comparison = {**_plain(requirement), "instrument": _plain(original["instrument"])}
    for offer in source.profile.offers:
        if (_offer_matches(offer, comparison) and _offer_complete(offer, comparison)
                and dt.datetime.fromisoformat(offer["available_from"]) <= start
                and dt.datetime.fromisoformat(offer["available_to"]) >= end):
            return True
    return False


def _bound_history(request, requirement, item, source, selector):
    bars = requirement["history"]["minimum_bars"] + requirement["history"]["warmup_bars"]
    start = request.requested_start - dt.timedelta(seconds=bars * requirement["timeframe"])
    manifest = item.manifest; refusals = []
    if not _bound_offer_interval(source, requirement, start, request.requested_end):
        refusals.append(_refuse(EligibilityCode.INSUFFICIENT_RANGE,
            "one source offer must cover the complete requirement and requested interval plus warmup", selector))
    if dt.datetime.fromisoformat(manifest.event_start) > start or dt.datetime.fromisoformat(manifest.event_end) < request.requested_end:
        refusals.append(_refuse(EligibilityCode.INSUFFICIENT_RANGE, "dataset does not cover the requested interval plus graph warmup", selector))
    for gap in manifest.gaps:
        if (gap["instrument_address"] == item.instrument.address and gap["field"] == requirement["field"]
                and dt.datetime.fromisoformat(gap["start"]) < request.requested_end and dt.datetime.fromisoformat(gap["end"]) > start):
            refusals.append(_refuse(EligibilityCode.HISTORY_GAP, "required dataset interval contains an explicit gap", selector))
    return refusals


def _bound_field_scope(requirement, item, selector):
    allowed = {"OPEN", "HIGH", "LOW", "CLOSE"}
    if item.instrument.asset_class == "EQUITY":
        allowed.add("VOLUME")
    if requirement["field"] not in allowed or requirement["depth"]["kind"] != "NONE":
        return [_refuse(EligibilityCode.UNAVAILABLE, "only historical OHLC index or OHLCV equity observations are supported", selector)]
    return []


def _bound_requirements(request, plan, input_bindings, datasets, sources, assessment):
    from app.market_data.capability import _requirement_selector
    assigned = {row["selector"]: row["graph_input_id"] for row in assessment.document["requirement_sources"]}
    source_by_name = {source.graph_input_id: source for source in sources}; refusals = []
    for record in plan.requirements:
        selector = _requirement_selector(record); name = assigned[selector]; requirement = record["requirement"]
        binding = input_bindings.document["inputs"][name]["binding"]; item = datasets[name]
        refusals.extend(_bound_dimensions(requirement, binding, item.manifest, selector))
        refusals.extend(_bound_history(request, requirement, item, source_by_name[name], selector))
        refusals.extend(_bound_field_scope(requirement, item, selector))
    return refusals


def _bound_capability_refusals(assessment):
    mapping = {"UNAVAILABLE": EligibilityCode.ENTITLEMENT_UNVERIFIED, "UNKNOWN": EligibilityCode.UNAVAILABLE,
        "INSUFFICIENT_RANGE": EligibilityCode.INSUFFICIENT_RANGE, "INSUFFICIENT_RESOLUTION": EligibilityCode.INSUFFICIENT_RESOLUTION,
        "INSUFFICIENT_FRESHNESS": EligibilityCode.INSUFFICIENT_FRESHNESS}
    return [_refuse(mapping[row["result"]], row["reason"], row["selector"])
            for row in assessment.requirement_results if row["result"] != "SATISFIED"]


def compile_bound_graph_data_eligibility(*, request, graph, resolved_graph, plan, input_bindings,
        datasets, sources, registry, dataset_set_address, evaluation_policy_address):
    """Verify a complete graph and each actual historical source before support."""
    from app.market_data.capability import assess_bound_capability
    try:
        _bound_types(request, graph, plan, input_bindings, datasets, sources)
        _bound_owners(request, graph, input_bindings, datasets, sources)
        refusals = _bound_resource_refusals(request, plan, datasets)
        if not refusals:
            _bound_graph(graph, plan, resolved_graph, input_bindings, registry)
            refusals.extend(_bound_selected_refusals(request, datasets, sources, input_bindings))
    except (AttributeError, KeyError, TypeError, ValueError, DataRequirementRefusal):
        _private()
    assessment = None
    if not refusals:
        try:
            assessment = assess_bound_capability(plan=plan, resolved_graph=resolved_graph, registry=registry,
                input_bindings=input_bindings, sources=sources, owner_id=request.owner_id, mode=request.mode,
                dataset_set_address=dataset_set_address, evaluation_policy_address=evaluation_policy_address,
                at_time=int(request.as_of.timestamp()))
            refusals.extend(_bound_capability_refusals(assessment))
            refusals.extend(_bound_requirements(request, plan, input_bindings, datasets, sources, assessment))
        except (CapabilityRefusal, TypeError, ValueError):
            refusals.append(_refuse(EligibilityCode.ENTITLEMENT_UNVERIFIED, "source capability or binding evidence differs; select compatible verified data"))
    return _bound_result(request, graph, plan, input_bindings, datasets, dataset_set_address,
                         evaluation_policy_address, refusals, assessment)


__all__ += ["BoundEligibilityResult", "compile_bound_graph_data_eligibility"]
