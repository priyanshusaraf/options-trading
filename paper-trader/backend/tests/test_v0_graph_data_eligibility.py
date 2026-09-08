"""V0 graph/data eligibility is pure, closed, bounded, and owner scoped."""
from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from app.api.data_eligibility_routes import (
    eligibility_document,
    private_eligibility_response,
    router,
)
from app.backtest.dataset_store import DatasetManifest, DatasetSegment, dataset_byte_digest
from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
from app.ir.hashing import canonical_json, content_address
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.v2_graph_versions import V2GraphFacts
from app.market_data.capability import CapabilityProfile, ProviderConformance
from app.market_data.eligibility import (
    EligibilityCode,
    EligibilityRequest,
    EligibilityResult,
    SelectedDataset,
    compile_graph_data_eligibility,
)
from app.market_data.requirements import compile_data_requirement_plan
from app.market_truth.identity import CanonicalPhysicalInstrument, ProviderContract


UTC = dt.timezone.utc
T0 = dt.datetime(2026, 8, 1, tzinfo=UTC)


def address(seed: str) -> str:
    return content_address({"fixture": seed})


def _graph_plan(*, field: str = "CLOSE", depth=None, timeframe: int = 60,
                instrument_type: str = "PHYSICAL", extra_component: bool = False):
    depth = depth or {"kind": "NONE", "levels": None}
    declaration = {"schema": "data-requirement-declaration/1", "classification": "REQUIRES_DATA",
        "requirements": [{"requirement_id": "primary_data",
            "instrument": {"literal": {"role": "primary", "type": instrument_type}},
            "field": {"literal": field}, "timeframe": {"literal": timeframe},
            "history": {"literal": {"minimum_bars": 1, "warmup_bars": 1}},
            "freshness": {"literal": {"maximum_age_seconds": 60}},
            "depth": {"literal": depth}, "session": {"literal": "INSTRUMENT_CALENDAR"},
            "alignment": {"literal": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}},
            "derived_local": {"literal": False}}]}
    component = {"component_id": "leaf.data", "component_version": 1,
        "domain_family": "transform", "structural_role": "transform", "ports": [],
        "parameters": {}}
    components = {("leaf.data", 1): component}
    if extra_component:
        components[("leaf.unused", 1)] = {**component, "component_id": "leaf.unused"}
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={},
        v2_components=components,
        data_requirement_declarations={("leaf.data", 1): declaration})
    document = {"format_version": 2, "strategy_id": "eligibility.fixture", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Eligibility", "description": None, "tags": []},
        "graph_inputs": [], "graph_outputs": [], "nodes": [{"node_id": "data",
            "component": {"component_id": "leaf.data", "component_version": 1},
            "parameters": {}}], "edges": []}
    resolved = resolve_v2(document, registry)
    plan = compile_data_requirement_plan(resolved)
    projection = {"identity_scheme_version": 1, "graph": {key: document[key]
        for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}}
    facts = V2GraphFacts("owner-a", document["strategy_id"], 1, canonical_json(document), 2,
        content_address(document), content_address(projection), plan.registry_snapshot_address)
    return resolved, plan, facts


def _selected(*, field: str = "CLOSE", timeframe: int = 60,
              instrument: CanonicalPhysicalInstrument | None = None,
              event_start: dt.datetime | None = None, gaps=()):
    instrument = instrument or CanonicalPhysicalInstrument(
        "fixture", "1", "XNSE", "EQUITY", "SPOT", "INR", None)
    raw = b"bounded-fixture"
    segment = DatasetSegment(owner_id="owner-a", object_address=dataset_byte_digest(raw),
        byte_digest=dataset_byte_digest(raw), byte_length=len(raw), media_type="application/json",
        raw_schema_address=address("schema"), row_start=0, row_end=100,
        instrument_addresses=(instrument.address,), fields=(field,),
        event_start=(event_start or T0).isoformat(),
        event_end=(T0 + dt.timedelta(days=2)).isoformat(),
        availability_start=(event_start or T0).isoformat(),
        availability_end=(T0 + dt.timedelta(days=2)).isoformat(),
        provider_product_addresses=(address("product"),),
        provider_contract_addresses=(address("contract-placeholder"),),
        provider_observation_addresses=(address("observation"),),
        normalized_observation_addresses=(address("normalized"),),
        normalization_transform_addresses=(address("transform"),),
        algorithm_addresses=(address("algorithm"),), correction_addresses=(),
        creation_evidence_address=address("creation"))
    return instrument, segment, raw


def _case(*, field="CLOSE", depth=None, timeframe=60, instrument=None,
          event_start=None, gaps=(), owner="owner-a", binding_timeframe=None,
          profile_available_from=None):
    requirement_type = (
        "ECONOMIC_SELECTOR"
        if instrument is not None and instrument.asset_class == "OPTION"
        else "PHYSICAL"
    )
    resolved, plan, graph = _graph_plan(
        field=field, depth=depth, timeframe=timeframe,
        instrument_type=requirement_type)
    instrument, segment, raw = _selected(field=field, timeframe=timeframe,
        instrument=instrument, event_start=event_start, gaps=gaps)
    contract = ProviderContract(owner, address("product"), "RESEARCH", ("HISTORICAL",),
        T0 - dt.timedelta(days=1), T0 + dt.timedelta(days=4), address("contract-evidence"))
    segment = dataclasses.replace(segment, provider_contract_addresses=(contract.address,))
    if gaps == "required":
        gaps = ({"instrument_address": instrument.address, "field": field,
            "start": (T0 + dt.timedelta(minutes=10)).isoformat(),
            "end": (T0 + dt.timedelta(minutes=11)).isoformat(), "reason": "MISSING"},)
    manifest = DatasetManifest(owner_id=owner, purpose="eligibility-fixture", mode="RESEARCH",
        segment_addresses=(segment.segment_address,), aggregate_byte_digest=dataset_byte_digest(raw),
        aggregate_byte_length=len(raw), instrument_addresses=segment.instrument_addresses,
        fields=segment.fields, event_start=segment.event_start, event_end=segment.event_end,
        availability_start=segment.availability_start, availability_end=segment.availability_end,
        gaps=gaps, correction_addresses=(), provider_entity_addresses=(address("entity"),),
        provider_product_addresses=segment.provider_product_addresses,
        provider_contract_addresses=segment.provider_contract_addresses,
        provider_observation_addresses=segment.provider_observation_addresses,
        normalized_observation_addresses=segment.normalized_observation_addresses,
        raw_schema_addresses=(segment.raw_schema_address,),
        normalization_transform_addresses=segment.normalization_transform_addresses,
        truth_snapshot_addresses=(address("truth"),),
        creation_evidence_addresses=(segment.creation_evidence_address,),
        capability_profile_address=address("temporary-profile"),
        alignment_policy_address=address("alignment-policy"),
        missing_data_policy_address=address("missing-policy"),
        adjustment_policy_address=address("adjustment-policy"),
        roll_policy_address=address("roll-policy"), algorithm_addresses=segment.algorithm_addresses,
        created_at=(T0 + dt.timedelta(days=2)).isoformat(),
        recorded_at=(T0 + dt.timedelta(days=2)).isoformat())
    depth_value = depth or {"kind": "NONE", "levels": None}
    offer = {"instrument": {"role": "primary", "type": requirement_type}, "field": field,
        "timeframes": [timeframe], "maximum_history_bars": 100,
        "maximum_freshness_seconds": 60, "depth": depth_value,
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60},
        "derived_local": False, "entitled": True, "known": True,
        "available_from": profile_available_from or T0 - dt.timedelta(days=1),
        "available_to": T0 + dt.timedelta(days=3)}
    coverage = {**offer, "resolution_seconds": timeframe,
        "history": {"from": offer["available_from"], "to": offer["available_to"], "bars": 100},
        "maximum_freshness_seconds": 60, "entitlement": "VERIFIED"}
    for key in ("timeframes", "maximum_history_bars", "entitled", "known", "available_from", "available_to"):
        coverage.pop(key, None)
    conformance = ProviderConformance(address("product"), (field,), (timeframe,), "fixture", "1",
        T0 - dt.timedelta(days=2), T0 + dt.timedelta(days=4), (address("evidence"),), "PASS",
        (coverage,))
    profile = CapabilityProfile(owner, "RESEARCH", 1, T0, T0 + dt.timedelta(days=4),
        conformance.address, (offer,), provider_entity_address=address("entity"),
        provider_product_address=address("product"), provider_contract_address=contract.address)
    manifest = DatasetManifest(**{**manifest.fact(),
        "capability_profile_address": profile.capability_profile_address})
    binding = {"schema": "canonical-input-binding/1", "owner_id": owner,
        "dataset_context_address": address("dataset-context"),
        "evaluation_context_address": address("evaluation-context"),
        "dataset_manifest_address": manifest.manifest_address,
        "market_truth_address": manifest.truth_snapshot_addresses[0],
        "provider_product_address": address("product"),
        "provider_contract_address": contract.address,
        "canonical_instrument_address": instrument.address,
        "instrument": {"role": "primary", "type": requirement_type},
        "timeframe": timeframe if binding_timeframe is None else binding_timeframe,
        "fields": [field],
        "freshness": {"maximum_age_seconds": 60}, "depth": depth_value,
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60},
        "derived_local": False}
    bindings = canonical_input_bindings(owner_id=owner,
        dataset_context_address=address("dataset-context"),
        evaluation_context_address=address("evaluation-context"),
        bindings={"primary": binding}, expected_source_addresses={"primary": content_address(binding)})
    request = EligibilityRequest(owner_id="owner-a", mode="RESEARCH",
        requested_start=T0 + dt.timedelta(minutes=2),
        requested_end=T0 + dt.timedelta(hours=1), as_of=T0 + dt.timedelta(days=3))
    return dict(request=request, graph=graph, resolved_graph=resolved, plan=plan,
        input_bindings=bindings, datasets=(SelectedDataset(manifest, {segment.segment_address: (segment, raw)}, instrument),),
        profile=profile, conformance=conformance, provider_contract=contract)


def _replace_binding(case, **changes):
    def plain(value):
        if isinstance(value, dict) or hasattr(value, "items"):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [plain(item) for item in value]
        return value
    old = plain(next(iter(case["input_bindings"].document["inputs"].values()))["binding"])
    binding = {**old, **changes}
    context = canonical_input_bindings(owner_id="owner-a",
        dataset_context_address=address("dataset-context"),
        evaluation_context_address=address("evaluation-context"),
        bindings={"primary": binding},
        expected_source_addresses={"primary": content_address(binding)})
    return {**case, "input_bindings": context}


def test_same_owner_exact_cash_subset_is_supported_and_deterministic():
    case = _case()
    first = compile_graph_data_eligibility(**case)
    second = compile_graph_data_eligibility(**case)
    assert first.status == "SUPPORTED"
    assert first.eligibility_address == second.eligibility_address
    assert first.graph_version == 1
    assert first.plan_address == case["plan"].plan_address
    assert first.dataset_manifest_addresses == (case["datasets"][0].manifest.manifest_address,)
    with pytest.raises(TypeError):
        EligibilityResult()


def test_saved_registry_version_refuses_fresh_plan_after_unrelated_registry_change():
    from app.ir.v2_graph_versions import require_row_matches
    from app.market_data.eligibility import PrivateEligibilityUnavailable

    case = _case()
    assert compile_graph_data_eligibility(**case).status == "SUPPORTED"
    resolved, plan, current_graph = _graph_plan(extra_component=True)
    saved_graph = case["graph"]
    assert saved_graph.artifact_json == current_graph.artifact_json
    assert saved_graph.content_address == current_graph.content_address
    assert saved_graph.graph_address == current_graph.graph_address
    assert saved_graph.registry_snapshot_address != current_graph.registry_snapshot_address
    assert require_row_matches(saved_graph, saved_graph) == saved_graph
    changed = {**case, "resolved_graph": resolved, "plan": plan}
    with pytest.raises(PrivateEligibilityUnavailable, match="eligibility authority is unavailable"):
        compile_graph_data_eligibility(**changed)
    assert compile_graph_data_eligibility(**{**changed, "graph": current_graph}).status == "SUPPORTED"


@pytest.mark.parametrize(("change", "code"), [
    ({"binding_timeframe": 120}, EligibilityCode.INSUFFICIENT_RESOLUTION),
    ({"event_start": T0 + dt.timedelta(minutes=1)}, EligibilityCode.INSUFFICIENT_RANGE),
])
def test_resolution_and_warmup_range_refuse_with_typed_codes(change, code):
    case = _case(**change)
    result = compile_graph_data_eligibility(**case)
    assert result.status == "REFUSED"
    assert code in {item.code for item in result.refusals}


def test_profile_interval_refuses_even_when_bar_count_and_dataset_range_are_sufficient():
    result = compile_graph_data_eligibility(**_case(
        profile_available_from=T0 + dt.timedelta(minutes=1)))
    assert EligibilityCode.INSUFFICIENT_RANGE in {item.code for item in result.refusals}


def test_foreign_and_missing_answers_share_private_absence_shape():
    foreign = private_eligibility_response("foreign")
    missing = private_eligibility_response("missing")
    assert foreign.status_code == missing.status_code == 404
    assert foreign.body == missing.body


def test_resource_bounds_refuse_before_dataset_verification(monkeypatch):
    case = _case()
    poisoned = tuple(case["datasets"] * 33)
    monkeypatch.setattr("app.market_data.eligibility.verify_dataset_manifest",
        lambda *_args, **_kwargs: pytest.fail("oversized request reached manifest verification"))
    result = compile_graph_data_eligibility(**{**case, "datasets": poisoned})
    assert result.refusals[0].code is EligibilityCode.RESOURCE_BOUND


@pytest.mark.parametrize(("binding_change", "code"), [
    ({"session": "CONTINUOUS"}, EligibilityCode.INSUFFICIENT_SESSION),
    ({"alignment": {"kind": "EXACT", "maximum_skew_seconds": 60}},
     EligibilityCode.INSUFFICIENT_ALIGNMENT),
    ({"freshness": {"maximum_age_seconds": 61}},
     EligibilityCode.INSUFFICIENT_FRESHNESS),
    ({"depth": {"kind": "BOOK", "levels": 1}},
     EligibilityCode.INSUFFICIENT_DEPTH),
])
def test_exact_binding_dimensions_refuse_independently(binding_change, code):
    result = compile_graph_data_eligibility(**_replace_binding(_case(), **binding_change))
    assert code in {item.code for item in result.refusals}


def test_explicit_required_interval_gap_refuses():
    result = compile_graph_data_eligibility(**_case(gaps="required"))
    assert EligibilityCode.HISTORY_GAP in {item.code for item in result.refusals}


def test_changed_profile_identity_refuses_entitlement_before_support():
    case = _case()
    changed = dataclasses.replace(case["profile"], profile_version=2)
    result = compile_graph_data_eligibility(**{**case, "profile": changed})
    assert EligibilityCode.ENTITLEMENT_UNVERIFIED in {item.code for item in result.refusals}


def test_foreign_owner_is_private_and_has_no_consumer_side_effect(monkeypatch):
    case = _case(owner="owner-b")
    calls = {"persist": 0, "provider": 0, "cache": 0, "evaluate": 0}
    def forbidden(name):
        def fail(*_args, **_kwargs):
            calls[name] += 1
            raise AssertionError(f"{name} side effect was reached")
        return fail
    monkeypatch.setattr("app.market_data.authority.persist_capability_assessment", forbidden("persist"))
    monkeypatch.setattr("app.providers.factory.get_provider", forbidden("provider"))
    monkeypatch.setattr("app.backtest.cache.find_reusable", forbidden("cache"))
    monkeypatch.setattr("app.ir.runtime.evaluate_v2", forbidden("evaluate"))
    with pytest.raises(Exception, match="eligibility authority is unavailable") as caught:
        compile_graph_data_eligibility(**case)
    assert caught.type.__name__ == "PrivateEligibilityUnavailable"
    assert calls == {"persist": 0, "provider": 0, "cache": 0, "evaluate": 0}


def test_supported_compile_has_no_provider_cache_evaluation_or_write_side_effect(monkeypatch):
    calls = {"persist": 0, "provider": 0, "cache": 0, "evaluate": 0, "socket": 0}
    def forbidden(name):
        def fail(*_args, **_kwargs):
            calls[name] += 1
            raise AssertionError(f"{name} side effect was reached")
        return fail
    monkeypatch.setattr("app.market_data.authority.persist_capability_assessment", forbidden("persist"))
    monkeypatch.setattr("app.providers.factory.get_provider", forbidden("provider"))
    monkeypatch.setattr("app.backtest.cache.find_reusable", forbidden("cache"))
    monkeypatch.setattr("app.ir.runtime.evaluate_v2", forbidden("evaluate"))
    monkeypatch.setattr("socket.socket", forbidden("socket"))
    assert compile_graph_data_eligibility(**_case()).status == "SUPPORTED"
    assert calls == {"persist": 0, "provider": 0, "cache": 0, "evaluate": 0, "socket": 0}


def test_request_range_and_depth_resource_boundaries(monkeypatch):
    case = _case()
    at_range = dataclasses.replace(case["request"],
        requested_start=case["request"].requested_end - dt.timedelta(days=366))
    above_range = dataclasses.replace(case["request"],
        requested_start=case["request"].requested_end - dt.timedelta(days=366, seconds=1))
    assert EligibilityCode.RESOURCE_BOUND not in {
        item.code for item in compile_graph_data_eligibility(**{**case, "request": at_range}).refusals}
    assert compile_graph_data_eligibility(**{**case, "request": above_range}).refusals[0].code \
        is EligibilityCode.RESOURCE_BOUND

    depth_case = _case(field="BID_SIZE", depth={"kind": "BOOK", "levels": 5})
    monkeypatch.setattr("app.market_data.eligibility.MAX_DEPTH_LEVELS", 4)
    assert compile_graph_data_eligibility(**depth_case).refusals[0].code \
        is EligibilityCode.RESOURCE_BOUND


def test_row_byte_and_instrument_request_limits_are_checked_before_loading(monkeypatch):
    case = _case()
    monkeypatch.setattr("app.market_data.eligibility.MAX_TOTAL_ROWS", 99)
    assert compile_graph_data_eligibility(**case).refusals[0].code is EligibilityCode.RESOURCE_BOUND
    monkeypatch.setattr("app.market_data.eligibility.MAX_TOTAL_ROWS", 100)
    monkeypatch.setattr("app.market_data.eligibility.MAX_TOTAL_BYTES",
        case["datasets"][0].manifest.aggregate_byte_length - 1)
    assert compile_graph_data_eligibility(**case).refusals[0].code is EligibilityCode.RESOURCE_BOUND
    monkeypatch.setattr("app.market_data.eligibility.MAX_TOTAL_BYTES",
        case["datasets"][0].manifest.aggregate_byte_length)
    assert EligibilityCode.RESOURCE_BOUND not in {
        item.code for item in compile_graph_data_eligibility(**case).refusals}
    monkeypatch.setattr("app.market_data.eligibility.MAX_DATASETS", 1)
    assert EligibilityCode.RESOURCE_BOUND not in {
        item.code for item in compile_graph_data_eligibility(**case).refusals}
    monkeypatch.setattr("app.market_data.eligibility.MAX_DATASETS", 0)
    assert compile_graph_data_eligibility(**case).refusals[0].code is EligibilityCode.RESOURCE_BOUND


def test_router_is_unregistered_and_serializes_only_compiled_result():
    case = _case()
    result = compile_graph_data_eligibility(**case)
    assert len(router.routes) == 1
    assert router.routes[0].path.endswith("/data-eligibility")
    document = eligibility_document(result)
    assert document["status"] == "SUPPORTED"
    assert document["eligibility_address"] == result.eligibility_address


# Reuse the existing isolated execution/research database fixture; no user DB.
from research_tests.test_canonical_dataset import authority_sessions


@pytest.fixture
def bound_csv_case(authority_sessions):
    from types import SimpleNamespace
    from research.data.user_csv_import import UserCsvSpec, CsvColumnMapping, persist_user_csv
    from research.data.canonical_dataset import load_canonical_datasets, project_verified_research_input_set
    from app.market_data.authority import load_capability_profile, load_provider_conformance
    from app.market_data.capability import CapabilitySourceBinding
    from app.market_truth.identity import load_provider_identity
    from app.ir.first_party.analytical_v2 import session_data
    from tests.test_indicator_accuracy_session_context_binding_correction import graph_document
    es, rs = authority_sessions; observed = dt.datetime(2026, 4, 1, tzinfo=UTC)
    imports = {}
    for name, asset, symbol in (("frame", "EQUITY", "SELF"), ("benchmark", "INDEX", "IDX")):
        volume = asset == "EQUITY"; rows = ["Symbol,Date,Open,High,Low,Close" + (",Volume" if volume else "")]
        days = [dt.date(2026, 1, 1) + dt.timedelta(days=offset) for offset in range(20)]
        days = [day for day in days if day.weekday() < 5][:8]
        for index, day in enumerate(days):
            price = 100 + index
            rows.append(f"{symbol},{day.isoformat()},{price},{price+2},{price-1},{price+1}" + (",1000" if volume else ""))
        spec = UserCsvSpec("Synthetic CSV", f"user-csv:XNSE:{asset}:{symbol}", "1", symbol, symbol,
            "XNSE", asset, CsvColumnMapping("Symbol", "Date", "Open", "High", "Low", "Close", "Volume" if volume else None),
            date_format="%Y-%m-%d")
        imports[name] = persist_user_csv(es, rs, owner_id="owner-a", project_id="mixed-source-fixture",
            raw=("\n".join(rows)+"\n").encode(), spec=spec, observed_at=observed)
    es.commit(); rs.commit(); as_of = imports["frame"].ready_as_of
    loaded = {name: load_canonical_datasets(rs, execution_session=es, owner_id="owner-a",
        selections=[SimpleNamespace(manifest_address=item.manifest.manifest_address, as_of=as_of)], now=as_of)[0][1]
        for name, item in imports.items()}
    projection = project_verified_research_input_set(loaded, owner_id="owner-a", primary_input="frame",
        graph_input_fields={"frame": ("CLOSE", "HIGH", "LOW", "OPEN", "VOLUME"), "benchmark": ("CLOSE",)})
    sources, selected = [], {}
    for name, projected in projection.input_sources.items():
        profile = load_capability_profile(es, projected.manifest.capability_profile_address, at_time=as_of)
        conformance = load_provider_conformance(es, profile.conformance_evidence_address)
        _, _, contract = load_provider_identity(es, profile.provider_contract_address)
        sources.append(CapabilitySourceBinding(name, "frame", projected.input_bindings, projected.manifest, profile, conformance, contract))
        selected[name] = SelectedDataset(projected.manifest, projected.segment_objects, imports[name].instrument)
    keys = [session_data.component_key(name) for name in ("OHLCV", "CLOSE")]
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=session_data.V2_TYPES,
        v2_components={key: session_data.V2_COMPONENTS[key] for key in keys},
        node_contracts={key: session_data.NODE_CONTRACTS[key] for key in keys},
        contract_bindings={key: session_data.CONTRACT_BINDINGS[key] for key in keys},
        v2_implementations={key: session_data.V2_IMPLEMENTATIONS[key] for key in keys})
    document = graph_document(session_data, "OHLCV", {})
    document.update(graph_outputs=[], nodes=[], edges=[], graph_inputs=[])
    for name in selected:
        single = graph_document(session_data, "OHLCV" if name == "frame" else "CLOSE", {})
        document["nodes"].append({**single["nodes"][0], "node_id": name})
        document["graph_inputs"].append({**single["graph_inputs"][0], "port_id": name})
        document["edges"].append({"edge_id": name, "source": {"scope": "graph_input", "port_id": name},
            "target": {"scope": "node", "node_id": name, "port_id": "frame"}, "binding": {"kind": "single"}})
    resolved = resolve_v2(document, registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=projection.input_bindings)
    graph_projection = {"identity_scheme_version": 1, "graph": {key: document[key]
        for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}}
    graph = V2GraphFacts("owner-a", document["strategy_id"], 1, canonical_json(document), 2,
        content_address(document), content_address(graph_projection), plan.registry_snapshot_address)
    manifest = imports["frame"].manifest
    request = EligibilityRequest("owner-a", "RESEARCH", dt.datetime.fromisoformat(manifest.event_start)+dt.timedelta(days=3),
        dt.datetime.fromisoformat(manifest.event_end), as_of)
    return dict(request=request, graph=graph, resolved_graph=resolved, plan=plan, input_bindings=projection.input_bindings,
        datasets=selected, sources=tuple(sources), registry=registry, dataset_set_address=projection.dataset_selection_address,
        evaluation_policy_address=address("bound-evaluation")), loaded


def test_real_csv_index_and_equity_bound_eligibility_preserves_source_evidence(bound_csv_case):
    from app.market_data.eligibility import compile_bound_graph_data_eligibility
    case, _ = bound_csv_case; result = compile_bound_graph_data_eligibility(**case)
    assert result.status == "SUPPORTED", result.refusals
    assert result.document["schema"] == "graph-data-eligibility/2"
    envelope = result.document["capability_assessment"]
    assert envelope["schema"] == "capability-assessment/3"
    assert len({row["capability_profile_address"] for row in envelope["fact"]["sources"]}) == 2
    assert {item.instrument.asset_class for item in case["datasets"].values()} == {"INDEX", "EQUITY"}
    assert "VOLUME" not in case["datasets"]["benchmark"].manifest.fields
    assert "VOLUME" in case["datasets"]["frame"].manifest.fields
    assert all(source.source_bindings.document["inputs"]["frame"]["binding"]["instrument"]["role"] == "primary" for source in case["sources"])
    assert "VOLUME" in {row["requirement"]["field"] for row in case["plan"].requirements}
    assert case["input_bindings"].document["inputs"]["benchmark"]["binding"]["instrument"]["role"] == "benchmark"
    reordered = compile_bound_graph_data_eligibility(**{**case, "sources": tuple(reversed(case["sources"])),
        "datasets": dict(reversed(tuple(case["datasets"].items())))})
    assert reordered.eligibility_address == result.eligibility_address
    assert result.document["plan_address"] == case["plan"].plan_address
    assert "capability_profile_address" not in result.document


@pytest.mark.parametrize("change", ["profile", "source", "range", "owner", "bytes"])
def test_real_csv_bound_eligibility_refuses_wrong_authority_or_range(bound_csv_case, change):
    from app.market_data.eligibility import compile_bound_graph_data_eligibility, PrivateEligibilityUnavailable
    case, _ = bound_csv_case
    if change == "profile":
        first, second = case["sources"]
        case["sources"] = (dataclasses.replace(first, profile=second.profile, conformance=second.conformance, provider_contract=second.provider_contract), second)
    if change == "source": case["datasets"] = {"frame": case["datasets"]["benchmark"], "benchmark": case["datasets"]["frame"]}
    if change == "range": case["request"] = dataclasses.replace(case["request"], requested_start=dt.datetime.fromisoformat(case["datasets"]["frame"].manifest.event_start))
    if change == "owner": case["request"] = dataclasses.replace(case["request"], owner_id="foreign")
    if change == "bytes":
        item = case["datasets"]["frame"]; segments = dict(item.segments); key = next(iter(segments))
        segments[key] = (segments[key][0], b"corrupt")
        case["datasets"] = {**case["datasets"], "frame": SelectedDataset(item.manifest, segments, item.instrument)}
    if change in {"owner", "bytes"}:
        with pytest.raises(PrivateEligibilityUnavailable): compile_bound_graph_data_eligibility(**case)
    else:
        result = compile_bound_graph_data_eligibility(**case)
        assert result.status == "REFUSED"
        assert result.refusals
        if change == "range": assert any(row.code == EligibilityCode.INSUFFICIENT_RANGE for row in result.refusals)


def test_actual_csv_index_volume_is_not_borrowed_from_equity(bound_csv_case):
    from research.data.canonical_dataset import project_verified_research_input_set, CanonicalDatasetRefused
    _, loaded = bound_csv_case
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_input_set(loaded, owner_id="owner-a", primary_input="frame",
            graph_input_fields={"frame": ("CLOSE", "VOLUME"), "benchmark": ("CLOSE", "VOLUME")})


def test_bound_interval_requires_one_complete_offer_not_complementary_offers(bound_csv_case):
    from types import SimpleNamespace
    from app.market_data.eligibility import _bound_offer_interval
    case, _ = bound_csv_case; source = case["sources"][0]
    requirement = next(row["requirement"] for row in case["plan"].requirements if row["requirement"]["field"] == "CLOSE")
    offer = dict(next(row for row in source.profile.offers if row["field"] == "CLOSE"))
    start, end = case["request"].requested_start, case["request"].requested_end
    enough_bars = {**offer, "available_from": (end-dt.timedelta(seconds=1)).isoformat()}
    enough_dates = {**offer, "maximum_history_bars": 0}
    mixed = dataclasses.replace(source, profile=SimpleNamespace(offers=(enough_bars, enough_dates)))
    assert not _bound_offer_interval(mixed, requirement, start, end)
    complete = dataclasses.replace(source, profile=SimpleNamespace(offers=(offer,)))
    assert _bound_offer_interval(complete, requirement, start, end)


def test_bound_history_refuses_only_gaps_intersecting_the_required_interval():
    from types import SimpleNamespace
    from app.market_data.eligibility import _bound_history
    case = _case(gaps="required")
    source = SimpleNamespace(source_bindings=case["input_bindings"], source_input_id="primary", profile=case["profile"])
    requirement = case["plan"].requirements[0]["requirement"]; selector = address("gap-selector")
    refusals = _bound_history(case["request"], requirement, case["datasets"][0], source, selector)
    assert [(row.code, row.selector) for row in refusals] == [(EligibilityCode.HISTORY_GAP, selector)]
    earlier = dataclasses.replace(case["request"], requested_end=T0 + dt.timedelta(minutes=5))
    assert _bound_history(earlier, requirement, case["datasets"][0], source, selector) == []
