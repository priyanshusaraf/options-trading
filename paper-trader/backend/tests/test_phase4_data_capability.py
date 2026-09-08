"""Focused closed-world capability assessment cases."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from dataclasses import replace
from types import MappingProxyType

from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.market_data.capability import (
    CapabilityAssessment,
    CapabilityProfile,
    CapabilityRefusal,
    ProviderConformance,
    assess_capability,
    verify_profile_conformance,
)
from app.market_data.requirements import compile_data_requirement_plan
from app.market_truth.identity import ProviderContract

ADDRESS = "sha256:" + "a" * 64
def _address(letter): return "sha256:" + letter * 64
T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _declaration():
    return {"schema": "data-requirement-declaration/1", "classification": "REQUIRES_DATA", "requirements": [{"requirement_id": "primary_close", "instrument": {"literal": {"role": "primary", "type": "PHYSICAL"}}, "field": {"literal": "CLOSE"}, "timeframe": {"literal": 60}, "history": {"literal": {"minimum_bars": 1, "warmup_bars": 20}}, "freshness": {"literal": {"maximum_age_seconds": 60}}, "depth": {"literal": {"kind": "NONE", "levels": None}}, "session": {"literal": "INSTRUMENT_CALENDAR"}, "alignment": {"literal": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}}, "derived_local": {"literal": False}}]}


def _registry():
    component = {"component_id": "leaf.close", "component_version": 1, "domain_family": "transform", "structural_role": "transform", "ports": [], "parameters": {}}
    return PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={("leaf.close", 1): component}, data_requirement_declarations={("leaf.close", 1): _declaration()})


def _plan():
    doc = {"format_version": 2, "strategy_id": "phase4", "strategy_version": 1, "metadata": {"metadata_version": 1, "name": "P4", "description": None, "tags": []}, "graph_inputs": [], "graph_outputs": [], "nodes": [{"node_id": "close", "component": {"component_id": "leaf.close", "component_version": 1}, "parameters": {}}], "edges": []}
    registry = _registry()
    return registry, doc, compile_data_requirement_plan(resolve_v2(doc, registry))


def _profile(**changes):
    values = {"owner_id": "owner-a", "mode": "RESEARCH", "profile_version": 1,
        "observed_at": T0 + timedelta(seconds=10),
        "expires_at": T0 + timedelta(seconds=100),
        "offers": ({"field": "CLOSE", "timeframes": [60],
            "maximum_history_bars": 21, "maximum_freshness_seconds": 60,
            "depth": "NONE", "entitled": True, "known": True},)}
    values.update(changes)
    for name in ("observed_at", "expires_at"):
        if isinstance(values[name], int):
            values[name] = T0 + timedelta(seconds=values[name])
    offers = tuple({**{key: value for key, value in item.items() if key != "levels"},
        "instrument": item.get("instrument", {"role": "primary", "type": "PHYSICAL"}),
        "session": item.get("session", "INSTRUMENT_CALENDAR"),
        "alignment": item.get("alignment", {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}),
        "derived_local": item.get("derived_local", False),
        "available_from": item.get("available_from", T0 - timedelta(days=1)),
        "available_to": item.get("available_to", T0 + timedelta(days=1)),
        "depth": {"kind": item["depth"],
            "levels": item.get("levels") if item["depth"] == "BOOK" else None}}
        for item in values.pop("offers"))
    conformance, contract = _profile_authorities(values["owner_id"], values["mode"], offers)
    conformance_address = values.pop("conformance_evidence_address", conformance.address)
    return CapabilityProfile(**values, conformance_evidence_address=conformance_address,
        offers=offers, provider_entity_address=_address("6"),
        provider_product_address=conformance.product_address,
        provider_contract_address=contract.address)


def _profile_authorities(owner_id, mode, offers):
    coverage = []
    fields = set()
    resolutions = set()
    for offer in offers:
        for resolution in offer["timeframes"]:
            fields.add(offer["field"]); resolutions.add(resolution)
            start = offer["available_from"]
            end = offer["available_to"]
            if isinstance(start, str): start = datetime.fromisoformat(start)
            if isinstance(end, str): end = datetime.fromisoformat(end)
            coverage.append({"instrument": dict(offer["instrument"]),
                "field": offer["field"], "resolution_seconds": resolution,
                "history": {"from": start, "to": end,
                    "bars": offer["maximum_history_bars"]},
                "maximum_freshness_seconds": offer["maximum_freshness_seconds"],
                "depth": dict(offer["depth"]), "session": offer["session"],
                "alignment": dict(offer["alignment"]),
                "derived_local": offer["derived_local"],
                "entitlement": "VERIFIED" if offer["entitled"] else "UNVERIFIED"})
    conformance = ProviderConformance(_address("7"), tuple(sorted(fields)),
        tuple(sorted(resolutions)), "fixture", "2", T0 - timedelta(days=2),
        T0 + timedelta(days=2), (_address("8"),), "PASS",
        tuple(coverage))
    contract = ProviderContract(owner_id, conformance.product_address, mode,
        ("HISTORICAL",), T0 - timedelta(days=2),
        T0 + timedelta(days=2), _address("9"))
    return conformance, contract


def _assess_profile(profile, *, plan=None, owner_id="owner-a", mode=None, at_time=50):
    conformance, contract = _profile_authorities(profile.owner_id, profile.mode, profile.offers)
    return assess_capability(plan=plan or _plan()[2], profile=profile,
        owner_id=owner_id, mode=mode or profile.mode,
        dataset_manifest_address=_address("b"),
        market_truth_snapshot_address=_address("c"),
        evaluation_policy_address=_address("d"),
        assessment_evidence_address=_address("e"),
        at_time=int((T0 + timedelta(seconds=at_time)).timestamp()),
        conformance=conformance, provider_contract=contract)


def _assessment(profile=None, **kwargs):
    return _assess_profile(profile or _profile(), at_time=kwargs.get("at_time", 50))


def test_provider_conformance_v1_identity_is_exact_and_reconstructible():
    conformance = ProviderConformance(
        "sha256:03ac17029b02da265b96c69f3a8a5648d3d86817c0e8e83ce06472d8797327d7",
        ("CLOSE",),
        (60,),
        "fixture-vector",
        "1",
        datetime(2026, 8, 30, tzinfo=timezone.utc),
        datetime(2026, 8, 31, tzinfo=timezone.utc),
        ("sha256:64a0218c8362b81ca429cd235858000128a9132def5fa44cebc7fde5a504f85f",),
        "PASS",
    )
    assert conformance.canonical_bytes.decode() == (
        '{"fact":{"evidence_artifacts":["sha256:64a0218c8362b81ca429cd235858000128a9132def5fa44cebc7fde5a504f85f"],'
        '"observed_from":"2026-08-30T00:00:00+00:00","observed_to":"2026-08-31T00:00:00+00:00",'
        '"product_address":"sha256:03ac17029b02da265b96c69f3a8a5648d3d86817c0e8e83ce06472d8797327d7",'
        '"result":"PASS","test_method":"fixture-vector","test_version":"1","tested_fields":["CLOSE"],'
        '"tested_resolutions":[60]},"schema":"provider-conformance/1"}'
    )
    assert conformance.address == "sha256:f23d5663335273b337a75359746254ef3385fd9c7bcdee98c7e5d7138d8ff136"
    assert ProviderConformance.from_bytes(conformance.canonical_bytes) == conformance


def test_capability_profile_v2_identity_is_exact_but_known_offer_cannot_assess():
    legacy_offer = {"instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21,
        "maximum_freshness_seconds": 60, "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60},
        "derived_local": False, "entitled": True, "known": True}
    profile = CapabilityProfile("owner-a", "RESEARCH", 1, 10, 100, ADDRESS,
        (legacy_offer,))
    assert profile.schema == "capability-profile/2"
    assert profile.capability_profile_address == \
        "sha256:ae58d689c99c1cde1b655e540198ddfbdd2a365e2aa3716df816198e32d88823"
    assert profile.canonical_bytes.decode() == (
        '{"fact":{"change_level":0,"conformance_evidence_address":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        '"expires_at":100,"mode":"RESEARCH","observed_at":10,"offers":[{"alignment":{"kind":"ASOF_BACKWARD","maximum_skew_seconds":60},'
        '"depth":{"kind":"NONE","levels":null},"derived_local":false,"entitled":true,"field":"CLOSE",'
        '"instrument":{"role":"primary","type":"PHYSICAL"},"known":true,"maximum_freshness_seconds":60,'
        '"maximum_history_bars":21,"session":"INSTRUMENT_CALENDAR","timeframes":[60]}],'
        '"owner_id":"owner-a","profile_version":1},"schema":"capability-profile/2"}'
    )
    with pytest.raises(CapabilityRefusal, match="evidence or contract is absent"):
        assess_capability(plan=_plan()[2], profile=profile, owner_id="owner-a",
            mode="RESEARCH", dataset_manifest_address=_address("b"),
            market_truth_snapshot_address=_address("c"),
            evaluation_policy_address=_address("d"),
            assessment_evidence_address=_address("e"), at_time=50)


def test_provider_conformance_v1_cannot_certify_a_known_offer():
    conformance = ProviderConformance(
        _address("1"), ("CLOSE",), (60,), "fixture-vector", "1",
        datetime(2026, 8, 30, tzinfo=timezone.utc),
        datetime(2026, 8, 31, tzinfo=timezone.utc), (_address("2"),), "PASS",
    )
    with pytest.raises(CapabilityRefusal, match="exceeds conformance coverage"):
        verify_profile_conformance(_profile(), conformance)
    unknown = _profile(offers=({
        "field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21,
        "maximum_freshness_seconds": 60, "depth": "NONE",
        "entitled": False, "known": False,
    },))
    verify_profile_conformance(unknown, conformance)


def test_typed_profile_requires_exact_conformance_during_assessment():
    profile = _profile()
    conformance, contract = _profile_authorities(
        profile.owner_id, profile.mode, profile.offers)
    arguments = dict(plan=_plan()[2], profile=profile, owner_id="owner-a",
        mode="RESEARCH", dataset_manifest_address=_address("b"),
        market_truth_snapshot_address=_address("c"),
        evaluation_policy_address=_address("d"),
        assessment_evidence_address=_address("e"),
        at_time=int((T0 + timedelta(seconds=50)).timestamp()))
    with pytest.raises(CapabilityRefusal, match="evidence or contract is absent"):
        assess_capability(**arguments)
    failed = replace(conformance, result="FAIL")
    failed_profile = replace(profile, conformance_evidence_address=failed.address)
    with pytest.raises(CapabilityRefusal, match="evidence or contract is absent"):
        assess_capability(**{**arguments, "profile": failed_profile},
            conformance=failed, provider_contract=contract)
    with pytest.raises(CapabilityRefusal, match="evidence or contract is absent"):
        assess_capability(**arguments, conformance=conformance)
    assert assess_capability(**arguments, conformance=conformance,
        provider_contract=contract).requirement_results[0]["result"] == "SATISFIED"


def test_capability_is_deterministic_and_owner_mode_scoped():
    first = _assessment(); second = _assessment()
    assert first.capability_assessment_address == second.capability_assessment_address
    assert first.requirement_results[0]["result"] == "SATISFIED"
    with pytest.raises(CapabilityRefusal, match="owner or mode"):
        assess_capability(plan=_plan()[2], profile=_profile(), owner_id="owner-b", mode="RESEARCH", dataset_manifest_address=ADDRESS, market_truth_snapshot_address=ADDRESS, evaluation_policy_address=ADDRESS, assessment_evidence_address=ADDRESS, at_time=50)


@pytest.mark.parametrize(("profile", "expected"), [
    (_profile(offers=({"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": False},)), "UNKNOWN"),
    (_profile(offers=({"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 20, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": True},)), "INSUFFICIENT_RANGE"),
    (_profile(offers=({"field": "CLOSE", "timeframes": [120], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": True},)), "INSUFFICIENT_RESOLUTION"),
    (_profile(offers=({"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21, "maximum_freshness_seconds": 61, "depth": "NONE", "entitled": True, "known": True},)), "INSUFFICIENT_FRESHNESS"),
    (_profile(offers=({"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": False, "known": True},)), "UNAVAILABLE"),
])
def test_unknown_and_insufficient_capability_fails_closed(profile, expected):
    assert _assessment(profile).requirement_results[0]["result"] == expected


@pytest.mark.parametrize("profile", [_profile(expires_at=49), _profile(change_level=2), _profile(change_level=3)])
def test_stale_and_semantic_breaks_refuse(profile):
    with pytest.raises(CapabilityRefusal): _assessment(profile)


def test_split_offers_never_collectively_satisfy():
    left = {"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 1, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": True}
    right = {"field": "CLOSE", "timeframes": [120], "maximum_history_bars": 21, "maximum_freshness_seconds": 61, "depth": "NONE", "entitled": True, "known": True}
    assert _assessment(_profile(offers=(left, right))).requirement_results[0]["result"] != "SATISFIED"


@pytest.mark.parametrize("dimension, value", [
    ("instrument", {"role": "secondary", "type": "PHYSICAL"}),
    ("session", "UTC"),
    ("alignment", {"kind": "EXACT", "maximum_skew_seconds": 0}),
    ("derived_local", True),
])
def test_semantic_offer_dimensions_cannot_be_silently_ignored(dimension, value):
    offer = {"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": True}
    profile = _profile(offers=(offer,))
    raw = dict(profile.to_dict()["offers"][0]); raw[dimension] = value
    try:
        changed = CapabilityProfile(**{**profile.to_dict(), "offers": (raw,)})
    except CapabilityRefusal:
        return
    assert _assessment(changed).requirement_results[0]["result"] != "SATISFIED"


def test_book_levels_and_profile_validity_fail_closed():
    _, _, plan = _plan()
    record = dict(plan.requirements[0]); requirement = dict(record["requirement"])
    requirement["depth"] = {"kind": "BOOK", "levels": 2}; record["requirement"] = requirement
    book_plan = replace(plan, requirements=(MappingProxyType(record),))
    offer = {"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "BOOK", "levels": 1, "entitled": True, "known": True}
    profile = _profile(offers=(offer,))
    assert _assess_profile(profile, plan=book_plan).requirement_results[0]["result"] != "SATISFIED"
    with pytest.raises(CapabilityRefusal, match="stale"):
        _assessment(_profile(observed_at=51))


def test_top_of_book_is_a_closed_satisfiable_depth_kind():
    _, _, plan = _plan(); record = dict(plan.requirements[0]); requirement = dict(record["requirement"])
    requirement["depth"] = {"kind": "TOP_OF_BOOK", "levels": None}; record["requirement"] = requirement
    top_plan = replace(plan, requirements=(MappingProxyType(record),))
    offer = {"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "TOP_OF_BOOK", "entitled": True, "known": True}
    profile = _profile(offers=(offer,))
    assert _assess_profile(profile, plan=top_plan).requirement_results[0]["result"] == "SATISFIED"


def test_same_requirement_id_on_distinct_leaves_has_distinct_selectors():
    _, _, plan = _plan(); first = dict(plan.requirements[0]); second = dict(first)
    second["authored_node_id"] = "close-2"; second["lowered_path"] = ("close-2",)
    doubled = replace(plan, requirements=(MappingProxyType(first), MappingProxyType(second)))
    assessment = _assess_profile(_profile(), plan=doubled)
    assert len(assessment.requirement_results) == 2
    assert len({row["selector"] for row in assessment.requirement_results}) == 2


def test_duplicate_assessment_selector_is_rejected():
    assessment = _assessment(); row = assessment.requirement_results[0]
    with pytest.raises(CapabilityRefusal, match="duplicated"):
        CapabilityAssessment(assessment.owner_id, assessment.mode, assessment.plan_address, assessment.registry_snapshot_address, assessment.capability_profile_address, assessment.dataset_manifest_address, assessment.market_truth_snapshot_address, assessment.evaluation_policy_address, assessment.assessment_evidence_address, (row, row))


@pytest.mark.parametrize("result, reason", [("SATISFIED", "forged"), ("UNKNOWN", "one declared offer covers the complete requirement")])
def test_assessment_reasons_are_closed_and_result_bound(result, reason):
    assessment = _assessment(); row = dict(assessment.requirement_results[0]); row.update(result=result, reason=reason)
    with pytest.raises(CapabilityRefusal, match="malformed"):
        CapabilityAssessment(assessment.owner_id, assessment.mode, assessment.plan_address, assessment.registry_snapshot_address, assessment.capability_profile_address, assessment.dataset_manifest_address, assessment.market_truth_snapshot_address, assessment.evaluation_policy_address, assessment.assessment_evidence_address, (row,))


def test_profile_rejects_execution_vocabulary_and_invalid_evidence():
    with pytest.raises(CapabilityRefusal, match="not closed"):
        _profile(offers=({"field": "CLOSE", "timeframes": [60], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": True, "execution_key": "broker"},))
    with pytest.raises(CapabilityRefusal, match="content address"):
        _profile(conformance_evidence_address="missing")


def test_offer_and_timeframe_permutations_are_byte_identical():
    first = _profile(offers=(
        {"field": "CLOSE", "timeframes": [120, 60], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": True},
        {"field": "LAST", "timeframes": [60], "maximum_history_bars": 1, "maximum_freshness_seconds": 1, "depth": "NONE", "entitled": False, "known": True},
    ))
    second = _profile(offers=(
        {"field": "LAST", "timeframes": [60], "maximum_history_bars": 1, "maximum_freshness_seconds": 1, "depth": "NONE", "entitled": False, "known": True},
        {"field": "CLOSE", "timeframes": [60, 120], "maximum_history_bars": 21, "maximum_freshness_seconds": 60, "depth": "NONE", "entitled": True, "known": True},
    ))
    assert first.capability_profile_address == second.capability_profile_address
    assert _assessment(first).to_dict() == _assessment(second).to_dict()


def test_mode_profiles_are_independent():
    _, _, plan = _plan()
    for mode in ("RESEARCH", "PAPER", "LIVE"):
        profile = _profile(mode=mode)
        assessment = _assess_profile(profile, plan=plan, mode=mode)
        assert assessment.requirement_results[0]["result"] == "SATISFIED"
    with pytest.raises(CapabilityRefusal, match="owner or mode"):
        assess_capability(plan=plan, profile=_profile(mode="LIVE"), owner_id="owner-a", mode="PAPER", dataset_manifest_address=_address("b"), market_truth_snapshot_address=_address("c"), evaluation_policy_address=_address("d"), assessment_evidence_address=_address("e"), at_time=50)


def _bound_case(*, benchmark_history=101):
    """Real dynamic full-plan fixture; source records retain their local primary role."""
    from copy import deepcopy
    from app.backtest.dataset_store import DatasetManifest
    from app.market_truth.identity import CanonicalPhysicalInstrument
    from app.ir.first_party.analytical_v2 import core_math
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
    from app.ir.hashing import content_address
    from app.market_data.capability import CapabilitySourceBinding
    from tests.test_v0_graph_data_eligibility import _case
    from tests.test_indicator_accuracy_session_context_binding_correction import component_registry, graph_document, plain
    registry = component_registry(core_math, "SMA")
    graph = graph_document(core_math, "SMA", {"window": 2})
    graph["graph_outputs"] = []; graph["edges"] = []; graph["nodes"] = []; graph["graph_inputs"] = []
    sources, projected = [], {}
    for index, name in enumerate(("primary", "benchmark")):
        instrument = CanonicalPhysicalInstrument(name, "1", "XNSE", "INDEX" if name == "benchmark" else "EQUITY", "SPOT", "INR", None)
        base = _case(instrument=instrument)
        offer = {**plain(base["profile"].offers[0]), "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
                 "maximum_history_bars": benchmark_history if name == "benchmark" else 100}
        conformance, contract = _profile_authorities("owner-a", "RESEARCH", (offer,))
        profile = CapabilityProfile("owner-a", "RESEARCH", 1, T0, T0 + timedelta(days=1), conformance.address,
            (offer,), 0, _address("6"), conformance.product_address, contract.address)
        manifest = DatasetManifest(**{**base["datasets"][0].manifest.fact(), "purpose": name,
            "capability_profile_address": profile.capability_profile_address, "provider_entity_addresses": (_address("6"),),
            "provider_product_addresses": (profile.provider_product_address,), "provider_contract_addresses": (contract.address,)})
        fact = {**plain(base["input_bindings"].document["inputs"]["primary"]["binding"]),
            "dataset_manifest_address": manifest.manifest_address, "provider_product_address": profile.provider_product_address,
            "provider_contract_address": contract.address, "alignment": offer["alignment"]}
        original = canonical_input_bindings(owner_id="owner-a", dataset_context_address=fact["dataset_context_address"],
            evaluation_context_address=fact["evaluation_context_address"], bindings={"original": fact},
            expected_source_addresses={"original": content_address(fact)})
        projected[name] = {**deepcopy(fact), "instrument": {"role": name, "type": "PHYSICAL"},
            "dataset_context_address": _address("b"), "evaluation_context_address": _address("c")}
        sources.append(CapabilitySourceBinding(name, "original", original, manifest, profile, conformance, contract))
        single = graph_document(core_math, "SMA", {"window": 2})
        graph["graph_inputs"].append({**single["graph_inputs"][0], "port_id": name})
        graph["nodes"].append({**single["nodes"][0], "node_id": name})
        graph["edges"].append({"edge_id": name, "source": {"scope": "graph_input", "port_id": name},
            "target": {"scope": "node", "node_id": name, "port_id": "frame"}, "binding": {"kind": "single"}})
    bindings = canonical_input_bindings(owner_id="owner-a", dataset_context_address=_address("b"),
        evaluation_context_address=_address("c"), bindings=projected,
        expected_source_addresses={key: content_address(value) for key, value in projected.items()})
    resolved = resolve_v2(graph, registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=bindings)
    return dict(plan=plan, resolved_graph=resolved, registry=registry, input_bindings=bindings, sources=tuple(sources),
        owner_id="owner-a", mode="RESEARCH", dataset_set_address=_address("d"), evaluation_policy_address=_address("e"),
        at_time=int((T0 + timedelta(seconds=50)).timestamp()))


def test_source_bound_capability_uses_distinct_profiles_and_original_full_plan():
    from app.market_data.capability import assess_bound_capability, bound_capability_assessment_envelope
    case = _bound_case(); before = case["plan"]
    assessment = assess_bound_capability(**case)
    assert len({source.manifest.instrument_addresses[0] for source in case["sources"]}) == 2
    assert case["plan"] is before
    assert assessment.document["plan_address"] == before.plan_address
    assert {row["result"] for row in assessment.requirement_results} == {"SATISFIED"}
    assert len({row["capability_profile_address"] for row in assessment.document["sources"]}) == 2
    assert {row["graph_input_id"] for row in assessment.document["requirement_sources"]} == {"primary", "benchmark"}
    assert all(source.profile.offers[0]["instrument"]["role"] == "primary" for source in case["sources"])
    assert bound_capability_assessment_envelope(assessment)["schema"] == "capability-assessment/3"
    assert assess_bound_capability(**{**case, "sources": tuple(reversed(case["sources"]))}).canonical_bytes == assessment.canonical_bytes


@pytest.mark.parametrize("change", ["profile", "manifest", "source", "missing", "extra", "owner", "mode", "stale", "plan"])
def test_source_bound_capability_refuses_mismatched_authority(change):
    from app.market_data.capability import assess_bound_capability
    from app.ir.node_contracts import NodeContractRefusal
    from app.market_data.requirements import DataRequirementRefusal
    case = _bound_case(); first, second = case["sources"]
    if change == "profile": case["sources"] = (replace(first, profile=second.profile, conformance=second.conformance, provider_contract=second.provider_contract), second)
    if change == "manifest": case["sources"] = (replace(first, manifest=second.manifest), second)
    if change == "source": case["sources"] = (replace(first, source_bindings=second.source_bindings), second)
    if change == "missing": case["sources"] = (first,)
    if change == "extra": case["sources"] = (*case["sources"], first)
    if change == "owner": case["owner_id"] = "foreign"
    if change == "mode": case["mode"] = "LIVE"
    if change == "stale": case["at_time"] += 172800
    if change == "plan": case["plan"] = replace(case["plan"], requirements=case["plan"].requirements[:1])
    with pytest.raises((CapabilityRefusal, NodeContractRefusal, DataRequirementRefusal)):
        assess_bound_capability(**case)


def test_source_bound_envelope_refuses_rehashed_open_or_incomplete_rows():
    from copy import deepcopy
    from app.market_data.capability import assess_bound_capability, bound_capability_assessment_envelope, require_bound_capability_assessment_envelope, BoundCapabilityAssessment
    envelope = bound_capability_assessment_envelope(assess_bound_capability(**_bound_case()))
    for target, field, value in [("fact", "extra", True), ("source", "profile", ADDRESS), ("assignment", "graph_input_id", "absent"),
                                  ("fact", "requirement_sources", []), ("fact", "requirement_results", []), ("fact", "sources", [])]:
        forged = deepcopy(envelope)
        row = forged["fact"] if target == "fact" else forged["fact"]["sources" if target == "source" else "requirement_sources"][0]
        row[field] = value
        with pytest.raises(CapabilityRefusal): require_bound_capability_assessment_envelope(forged)
    with pytest.raises(CapabilityRefusal): BoundCapabilityAssessment()


def test_source_bound_shortfall_cannot_borrow_another_sources_history():
    from app.market_data.capability import assess_bound_capability
    assessment = assess_bound_capability(**_bound_case(benchmark_history=1))
    assignments = {row["selector"]: row["graph_input_id"] for row in assessment.document["requirement_sources"]}
    assert {assignments[row["selector"]]: row["result"] for row in assessment.requirement_results} == {
        "primary": "SATISFIED", "benchmark": "INSUFFICIENT_RANGE"}


def test_source_bound_original_fact_cannot_change_alignment_even_when_readdressed():
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
    from app.ir.hashing import content_address
    from app.market_data.capability import assess_bound_capability, _plain
    case = _bound_case(); first, second = case["sources"]
    document = _plain(first.source_bindings.document)
    fact = {**document["inputs"]["original"]["binding"], "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}}
    original = canonical_input_bindings(owner_id="owner-a", dataset_context_address=document["dataset_context_address"],
        evaluation_context_address=document["evaluation_context_address"], bindings={"original": fact},
        expected_source_addresses={"original": content_address(fact)})
    with pytest.raises(CapabilityRefusal, match="altered facts"):
        assess_bound_capability(**{**case, "sources": (replace(first, source_bindings=original), second)})


def test_source_bound_ambiguous_roles_refuse_a_freshly_verified_full_plan():
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
    from app.ir.hashing import content_address
    from app.market_data.capability import assess_bound_capability, _plain
    case = _bound_case(); document = _plain(case["input_bindings"].document)
    facts = {name: row["binding"] for name, row in document["inputs"].items()}
    facts["benchmark"]["instrument"]["role"] = "primary"
    context = canonical_input_bindings(owner_id="owner-a", dataset_context_address=document["dataset_context_address"],
        evaluation_context_address=document["evaluation_context_address"], bindings=facts,
        expected_source_addresses={name: content_address(fact) for name, fact in facts.items()})
    plan = compile_data_requirement_plan(case["resolved_graph"], registry=case["registry"], input_bindings=context)
    with pytest.raises(CapabilityRefusal, match="ambiguous"):
        assess_bound_capability(**{**case, "plan": plan, "input_bindings": context})
