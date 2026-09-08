"""Synthetic persisted authority only; no captured or licensed market data."""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
from types import SimpleNamespace

import pytest
import pandas as pd
from sqlalchemy import create_engine, event as sqlalchemy_event, text
from sqlalchemy.orm import Session

from app.backtest.dataset_store import DatasetManifest, DatasetSegment, dataset_byte_digest
from app.db.models import Base
from app.ir.hashing import canonical_json, content_address
from app.ir.validity import valid
from app.market_data import dataset_authority as a
from app.market_data.authority import persist_capability_profile, persist_provider_conformance
from app.market_data.observations import (
    RawObservationSegment, ProviderObservation, NormalizedMarketObservation,
    persist_raw_segment, persist_provider_observation, persist_normalized_observation,
)
from app.market_truth.authority import persist_market_truth_snapshot
from app.market_truth.identity import (
    CanonicalPhysicalInstrument, persist_canonical_instrument, persist_provider_alias,
)
from research.data.canonical_dataset import (
    CODEC, FIELDS, CanonicalDatasetRefused, encode_observation_index,
    decode_observation_index, load_canonical_datasets, instrument_key,
    project_verified_research_inputs,
)
from research.data.user_csv_import import (
    CsvColumnMapping, UserCsvSpec, persist_user_csv,
)
from research.domain.base import init_research_db
from research.domain.strategy_admissions import persist_verified_dataset_authority
from tests.test_phase4_dataset_assessment_authority import (
    _coverage,
    _offer,
    _seed_execution,
    T0,
    address,
)

AS_OF = T0 + dt.timedelta(days=27)


def seed_canonical(es, rs, *, count=4, owner="synthetic-owner", venue="XNSE",
                   volume_delta=0, source_name="synthetic-ohlcv/1", mutate_observation=None,
                   mutate_segment=None, shift_at=None, available_delay=0, flat=False,
                   instrument_namespace="synthetic-q03", shift_offset=1,
                   asset_class="EQUITY"):
    """Persist every source, row and dependency through real existing writers."""
    v = _seed_execution(es, owner_id=owner, instrument=CanonicalPhysicalInstrument(
        "synthetic-q03", "1", venue, asset_class, "SPOT", "INR", None), timeframe=900)
    if instrument_namespace != "synthetic-q03":
        v["instrument"] = dataclasses.replace(v["instrument"], authority_namespace=instrument_namespace)
        persist_canonical_instrument(es, v["instrument"])
        v["provider_token"] = instrument_namespace
        v["alias"] = dataclasses.replace(v["alias"], provider_token=instrument_namespace,
            provider_symbol=instrument_namespace, canonical_instrument_address=v["instrument"].address)
        persist_provider_alias(es, v["alias"])
    truth = dataclasses.replace(v["truth"], effective_to=AS_OF,
        instrument_addresses=(v["instrument"].address,),
        records=tuple(dataclasses.replace(record, effective_to=AS_OF) for record in v["truth"].records))
    persist_market_truth_snapshot(es, truth)
    alignment = dataclasses.replace(v["alignment"], resolution_seconds=900, truth_snapshot_address=truth.address)
    adjustment = dataclasses.replace(v["adjustment"], truth_snapshot_addresses=(truth.address,),
        instrument_addresses=(v["instrument"].address,))
    roll = dataclasses.replace(v["roll"], truth_snapshot_addresses=(truth.address,),
        instrument_addresses=(v["instrument"].address,))
    a.persist_alignment_policy(es, alignment)
    a.persist_adjustment_policy(es, adjustment)
    a.persist_roll_policy(es, roll)
    schema = a.RawSchema(owner, v["product"].address, v["contract"].address, source_name,
        tuple(sorted((field.lower(), "number") for field in FIELDS)), address("synthetic-schema"), T0)
    a.persist_raw_schema(es, schema)
    transform = a.NormalizationTransform(owner, (schema.address,), "synthetic-normalized/1", (),
        v["algorithm"].address, T0)
    a.persist_normalization_transform(es, transform)
    sources, normalized, raw_addresses, rows = [], [], [], []
    for i in range(count):
        event = T0 + dt.timedelta(minutes=15*(i + (shift_offset if shift_at is not None and i >= shift_at else 0)))
        completed = event + dt.timedelta(minutes=15)
        available = completed + dt.timedelta(seconds=available_delay)
        op = 100.0 + (i % 8)
        close = op + (1.5 if i % 3 else -1.5)
        numbers = (op, op+2.0, op-2.0, close, 1000.0+i+volume_delta)
        if flat:
            numbers = (100.0, 100.0, 100.0, 100.0, 0.0)
        payload = canonical_json(dict(zip((f.lower() for f in FIELDS), numbers))).encode()
        raw = RawObservationSegment(owner, v["product"].address, v["contract"].address,
            "application/json", source_name, payload, available)
        persist_raw_segment(es, raw)
        raw_addresses.append(raw.address)
        row = []
        for field, number in zip(FIELDS, numbers):
            source = ProviderObservation(owner, v["entity"].address, v["product"].address,
                v["contract"].address, v["alias"].address, v["provider_token"], source_name,
                field.lower(), 900, event, completed, available, available,
                f"{instrument_namespace}-{source_name}-{volume_delta}-{i}-{field}",
                f"{instrument_namespace}-{source_name}-{volume_delta}-{i}-{field}", raw.address, 0, len(payload),
                hashlib.sha256(payload).hexdigest(), valid(number).state)
            persist_provider_observation(es, source)
            obs = NormalizedMarketObservation(v["instrument"].address, (source.address,),
                transform.address, "1", alignment.address, v["algorithm"].address, "1",
                truth.address, transform.output_schema, field, 900, event, completed,
                available, available, valid(number))
            if mutate_observation:
                obs = mutate_observation(i, field, obs)
            persist_normalized_observation(es, obs)
            sources.append(source.address)
            normalized.append(obs.address)
            row.append(obs.address)
        rows.append(row)
    conformance = dataclasses.replace(v["conformance"],
        tested_fields=tuple(sorted(FIELDS)), tested_resolutions=(900,),
        coverage=tuple(_coverage(field=field, timeframe=900) for field in FIELDS))
    persist_provider_conformance(es, conformance)
    profile = dataclasses.replace(v["profile"], expires_at=AS_OF+dt.timedelta(days=1),
        conformance_evidence_address=conformance.address,
        offers=tuple(_offer(field=f, timeframe=900) for f in FIELDS))
    persist_capability_profile(es, profile)
    segments = {}
    creations = []
    for start in range(0, count, 100):
        stop = min(start+100, count)
        creation = a.DatasetCreationEvidence(owner, "synthetic-q03",
            tuple(sorted(sources[start*5:stop*5]+normalized[start*5:stop*5])),
            tuple(sorted(raw_addresses[start:stop])), v["algorithm"].address, AS_OF)
        a.persist_dataset_creation_evidence(es, creation)
        creations.append(creation.address)
        index = encode_observation_index(v["instrument"].address, 900, rows[start:stop])
        begin = T0+dt.timedelta(minutes=15*(start+(shift_offset if shift_at is not None and start >= shift_at else 0)))
        end = T0+dt.timedelta(minutes=15*(stop+(shift_offset if shift_at is not None and stop-1 >= shift_at else 0)))
        segment = DatasetSegment(owner_id=owner, object_address=dataset_byte_digest(index),
            byte_digest=dataset_byte_digest(index), byte_length=len(index), media_type="application/json",
            raw_schema_address=schema.address, row_start=start, row_end=stop,
            instrument_addresses=(v["instrument"].address,), fields=tuple(sorted(FIELDS)),
            event_start=begin.isoformat(), event_end=end.isoformat(),
            availability_start=(begin+dt.timedelta(minutes=15)).isoformat(),
            availability_end=(end+dt.timedelta(minutes=15)).isoformat(),
            provider_product_addresses=(v["product"].address,), provider_contract_addresses=(v["contract"].address,),
            provider_observation_addresses=tuple(sorted(sources[start*5:stop*5])),
            normalized_observation_addresses=tuple(sorted(normalized[start*5:stop*5])),
            normalization_transform_addresses=(transform.address,), algorithm_addresses=(v["algorithm"].address,),
            correction_addresses=(), creation_evidence_address=creation.address)
        if mutate_segment:
            segment = mutate_segment(segment)
        segments[segment.segment_address] = (segment, index)
    aggregate = b"".join(segments[key][1] for key in sorted(segments))
    m = DatasetManifest(owner_id=owner, purpose="synthetic-q03-test", mode="RESEARCH",
        segment_addresses=tuple(sorted(segments)), aggregate_byte_digest=dataset_byte_digest(aggregate),
        aggregate_byte_length=len(aggregate), instrument_addresses=segment.instrument_addresses, fields=segment.fields,
        event_start=T0.isoformat(), event_end=segment.event_end,
        availability_start=(T0+dt.timedelta(minutes=15)).isoformat(), availability_end=segment.availability_end,
        gaps=(), correction_addresses=(), provider_entity_addresses=(v["entity"].address,),
        provider_product_addresses=segment.provider_product_addresses,
        provider_contract_addresses=segment.provider_contract_addresses,
        provider_observation_addresses=tuple(sorted(sources)),
        normalized_observation_addresses=tuple(sorted(normalized)),
        raw_schema_addresses=(schema.address,), normalization_transform_addresses=(transform.address,),
        truth_snapshot_addresses=(truth.address,), creation_evidence_addresses=tuple(sorted(creations)),
        capability_profile_address=profile.capability_profile_address, alignment_policy_address=alignment.address,
        missing_data_policy_address=v["missing"].address, adjustment_policy_address=adjustment.address,
        roll_policy_address=roll.address, algorithm_addresses=segment.algorithm_addresses,
        created_at=AS_OF.isoformat(), recorded_at=AS_OF.isoformat())
    es.commit()
    persist_verified_dataset_authority(rs, manifest=m, segments=segments,
        execution_session=es, at_time=AS_OF)
    rs.commit()
    return m


@pytest.fixture
def authority_sessions(tmp_path):
    ee = create_engine(f"sqlite:///{tmp_path/'execution.db'}")
    re = create_engine(f"sqlite:///{tmp_path/'research.db'}")
    Base.metadata.create_all(ee)
    init_research_db(re)
    with Session(ee) as es, Session(re) as rs:
        yield es, rs
    ee.dispose()
    re.dispose()


def load(es, rs, manifest, *, owner="synthetic-owner", as_of=AS_OF):
    return load_canonical_datasets(rs, execution_session=es, owner_id=owner,
        selections=[SimpleNamespace(manifest_address=manifest.manifest_address, as_of=as_of)],
        now=AS_OF+dt.timedelta(days=1))


def test_real_persisted_index_roundtrip_and_frozen_values(authority_sessions):
    es, rs = authority_sessions
    m = seed_canonical(es, rs)
    instrument, data = load(es, rs, m)[0]
    assert data.content_hash == m.manifest_address and data.bar_count == 4
    assert data.candles[0].ts == T0 and data.candles[0].volume == 1000
    assert instrument.segment == "NSE" and not instrument.has_options
    assert len(data.instrument_key) == 46
    import base64
    assert "sha256:"+base64.urlsafe_b64decode(data.instrument_key[3:]+"=").hex() == m.instrument_addresses[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        data.candles[0].close = 0
    data.binding["manifest_address"] = "changed"
    assert data.binding["manifest_address"] == m.manifest_address
    es.expire_all()
    rs.expire_all()
    assert load(es, rs, m)[0][1] == data


def test_verified_analytical_projection_uses_availability_clock_and_retains_bar_open_map(authority_sessions):
    es, rs = authority_sessions
    manifest = seed_canonical(es, rs)
    data = load(es, rs, manifest)[0][1]
    projected = project_verified_research_inputs(
        data, owner_id="synthetic-owner",
        graph_input_fields={"frame": ("CLOSE", "OPEN")},
    )
    availability = projected.inputs["frame"]["close"].index
    assert availability[0] == pd.Timestamp(T0 + dt.timedelta(minutes=15))
    assert projected.bar_open_index[0] == pd.Timestamp(T0)
    assert projected.availability_index.equals(availability)
    assert projected.inputs["frame"]["close"].tolist() == [98.5, 102.5, 103.5, 101.5]
    binding = projected.input_bindings.document["inputs"]["frame"]["binding"]
    assert binding["dataset_manifest_address"] == manifest.manifest_address
    assert binding["canonical_instrument_address"] == manifest.instrument_addresses[0]
    assert binding["fields"] == ("CLOSE", "OPEN")
    assert projected.position_map_address


def test_verified_analytical_projection_refuses_wrong_owner_unknown_fields_and_plural_authority(authority_sessions):
    es, rs = authority_sessions
    manifest = seed_canonical(es, rs)
    data = load(es, rs, manifest)[0][1]
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_inputs(
            data, owner_id="foreign-owner", graph_input_fields={"frame": ("CLOSE",)},
        )
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_inputs(
            data, owner_id="synthetic-owner", graph_input_fields={"frame": ("MID",)},
        )
    # The legacy scalar source must never impersonate a second instrument.
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_inputs(
            data, owner_id="synthetic-owner",
            graph_input_fields={"frame": ("CLOSE",), "benchmark": ("CLOSE",)},
        )


def _assert_distinct_manifests(primary_manifest, benchmark_manifest):
    from tests.test_phase4_dataset_manifest import _manifest as legacy_manifest
    assert primary_manifest != benchmark_manifest
    assert primary_manifest != legacy_manifest()
    assert legacy_manifest() != primary_manifest
    assert len({primary_manifest, benchmark_manifest,
                DatasetManifest.from_bytes(primary_manifest.canonical_bytes)}) == 2


def _assert_local_source_roles(projected):
    for name, source in projected.input_sources.items():
        assert set(source.inputs) == {"frame"}
        assert source.input_bindings.document["inputs"]["frame"]["binding"]["instrument"]["role"] == "primary"
        assert projected.dataset_selection_document["inputs"][name]["source_input_id"] == "frame"


def test_verified_input_set_retains_distinct_sources_on_primary_clock(authority_sessions):
    from copy import copy
    from research.data.canonical_dataset import project_verified_research_input_set
    from research.evaluation.phase5_runtime import (
        ResearchExecutionRefusal, _validate_verified_dataset, _verify_observation_input_set,
    )

    es, rs = authority_sessions
    primary_manifest = seed_canonical(es, rs)
    benchmark_manifest = seed_canonical(
        es, rs, instrument_namespace="synthetic-benchmark", flat=True)
    _assert_distinct_manifests(primary_manifest, benchmark_manifest)
    primary = load(es, rs, primary_manifest)[0][1]
    benchmark = load(es, rs, benchmark_manifest)[0][1]
    selections = {"frame": primary, "benchmark": benchmark}
    fields = {"frame": ("CLOSE",), "benchmark": ("CLOSE",)}
    projected = project_verified_research_input_set(
        selections, owner_id="synthetic-owner", primary_input="frame",
        graph_input_fields=fields)

    assert projected.inputs["frame"]["close"].tolist() == [98.5, 102.5, 103.5, 101.5]
    assert projected.inputs["benchmark"]["close"].tolist() == [100.0] * 4
    assert projected.inputs["benchmark"]["close"].index.equals(projected.availability_index)
    assert projected.bar_open_index[0] == pd.Timestamp(T0)
    assert projected.manifest.manifest_address == primary_manifest.manifest_address
    entries = projected.input_bindings.document["inputs"]
    for name, manifest in (("frame", primary_manifest), ("benchmark", benchmark_manifest)):
        assert entries[name]["binding"]["dataset_manifest_address"] == manifest.manifest_address
        assert entries[name]["binding"]["canonical_instrument_address"] == manifest.instrument_addresses[0]
    assert entries["frame"]["binding"]["instrument"]["role"] == "primary"
    assert entries["benchmark"]["binding"]["instrument"]["role"] == "benchmark"
    _assert_local_source_roles(projected)
    _validate_verified_dataset(projected)
    with pytest.raises(ResearchExecutionRefusal, match="cutoffs"):
        _verify_observation_input_set(
            projected.input_sources, owner_id="synthetic-owner", primary_input="frame",
            as_of=(AS_OF - dt.timedelta(seconds=1)).isoformat())
    rewritten_sources = {}
    for name, source in projected.input_sources.items():
        changed_source = copy(source)
        proof = json.loads(source.source_provenance_json)
        proof["as_of"] = (AS_OF - dt.timedelta(seconds=1)).isoformat()
        object.__setattr__(changed_source, "source_provenance_json", canonical_json(proof))
        rewritten_sources[name] = changed_source
    with pytest.raises(ResearchExecutionRefusal, match="source provenance"):
        _verify_observation_input_set(
            rewritten_sources, owner_id="synthetic-owner", primary_input="frame",
            as_of=(AS_OF - dt.timedelta(seconds=1)).isoformat())
    reordered = project_verified_research_input_set(
        dict(reversed(list(selections.items()))), owner_id="synthetic-owner",
        primary_input="frame", graph_input_fields=fields)
    assert reordered.input_digest == projected.input_digest
    assert reordered.dataset_selection_address == projected.dataset_selection_address
    for field, value in (("dataset_selection_address", address("wrong-selection")),
                         ("input_digest", address("wrong-inputs")),
                         ("position_map_address", address("wrong-position-map")),
                         ("dataset_selection_document", {
                             **projected.dataset_selection_document,
                             "as_of": (AS_OF - dt.timedelta(seconds=1)).isoformat()}),
                         ("inputs", {"frame": projected.inputs["frame"]})):
        changed = copy(projected)
        object.__setattr__(changed, field, value)
        with pytest.raises(ResearchExecutionRefusal, match="input-set proof"):
            _validate_verified_dataset(changed)

    revised_manifest = seed_canonical(
        es, rs, instrument_namespace="synthetic-benchmark", flat=True,
        source_name="synthetic-revised-source/1")
    revised = project_verified_research_input_set(
        {"frame": primary, "benchmark": load(es, rs, revised_manifest)[0][1]},
        owner_id="synthetic-owner", primary_input="frame", graph_input_fields=fields)
    assert revised.inputs["benchmark"]["close"].equals(projected.inputs["benchmark"]["close"])
    assert revised.dataset_selection_address != projected.dataset_selection_address
    assert revised.input_digest != projected.input_digest


def test_verified_input_set_refuses_incomplete_foreign_and_misaligned_sources(authority_sessions):
    from copy import copy
    from research.data.canonical_dataset import project_verified_research_input_set
    from research.evaluation.phase5_runtime import ResearchExecutionRefusal, _verify_observation_input_set

    es, rs = authority_sessions
    primary = load(es, rs, seed_canonical(es, rs))[0][1]
    benchmark = load(es, rs, seed_canonical(
        es, rs, count=3, instrument_namespace="synthetic-benchmark", flat=True))[0][1]
    fields = {"frame": ("CLOSE",), "benchmark": ("CLOSE",)}
    for sources, owner, primary_name in (
        ({"frame": primary}, "synthetic-owner", "frame"),
        ({"frame": primary, "benchmark": benchmark}, "foreign-owner", "frame"),
        ({"frame": primary, "benchmark": benchmark}, "synthetic-owner", "missing"),
        ({"frame": primary, "benchmark": benchmark}, "synthetic-owner", "frame"),
    ):
        with pytest.raises(CanonicalDatasetRefused):
            project_verified_research_input_set(
                sources, owner_id=owner, primary_input=primary_name,
                graph_input_fields=fields)
    primary_source = project_verified_research_inputs(
        primary, owner_id="synthetic-owner", graph_input_fields={"frame": ("CLOSE",)})
    benchmark_source = project_verified_research_inputs(
        benchmark, owner_id="synthetic-owner", graph_input_fields={"benchmark": ("CLOSE",)})
    spoofed = copy(benchmark_source)
    object.__setattr__(spoofed, "availability_index", primary_source.availability_index)
    object.__setattr__(spoofed, "bar_open_index", primary_source.bar_open_index)
    with pytest.raises(ResearchExecutionRefusal, match="clock projection"):
        _verify_observation_input_set(
            {"frame": primary_source, "benchmark": spoofed}, owner_id="synthetic-owner",
            primary_input="frame", as_of=AS_OF.isoformat())
    with pytest.raises(ResearchExecutionRefusal, match="owner or instrument"):
        _verify_observation_input_set(
            {"frame": primary_source, "benchmark": benchmark_source}, owner_id="foreign-owner",
            primary_input="frame", as_of=AS_OF.isoformat())


def _two_source_ema_graph():
    from copy import deepcopy
    from app.ir.first_party.analytical_v2 import recursive_state
    from app.ir.resolve import resolve_v2
    from tests.test_indicator_accuracy_session_context_binding_correction import component_registry, graph_document

    registry = component_registry(recursive_state, "EMA")
    document = graph_document(recursive_state, "EMA", {"window": 2})
    input_port, output_port, node = (deepcopy(document[key][0])
                                    for key in ("graph_inputs", "graph_outputs", "nodes"))
    document.update(graph_inputs=[], graph_outputs=[], nodes=[], edges=[])
    for name in ("frame", "benchmark"):
        document["graph_inputs"].append({**deepcopy(input_port), "port_id": name})
        document["graph_outputs"].append({**deepcopy(output_port), "port_id": name})
        document["nodes"].append({**deepcopy(node), "node_id": name})
        document["edges"].extend([
            {"edge_id": f"in:{name}", "source": {"scope": "graph_input", "port_id": name},
             "target": {"scope": "node", "node_id": name, "port_id": "frame"}, "binding": {"kind": "single"}},
            {"edge_id": f"out:{name}", "source": {"scope": "node", "node_id": name, "port_id": "value"},
             "target": {"scope": "graph_output", "port_id": name}, "binding": {"kind": "single"}},
        ])
    return registry, resolve_v2(document, registry)


def _assert_input_set_run_outputs(result, projected, policy):
    assert result.document["schema"] == "phase5-research-run-result/2"
    assert result.document["dataset_selection_address"] == projected.dataset_selection_address
    assert result.document["primary_input"] == "frame"
    assert result.document["source_policies"] == policy.document["source_policies"]
    assert result.batch_outputs["benchmark"].iloc[-1].value == 100.0
    assert result.batch_outputs["frame"].iloc[-1].value == pytest.approx(101.83333333333333)
    assert result.batch_output_document == result.incremental_output_document


def test_input_set_policy_executes_both_instruments_and_refuses_rebound_source(authority_sessions):
    from copy import deepcopy
    from app.ir.incremental_runtime import CancellationToken, accept_research_resource_plan
    from app.market_data.requirements import compile_data_requirement_plan
    from research.data.canonical_dataset import project_verified_research_input_set
    from research.evaluation.phase5_runtime import (
        ResearchExecutionRefusal, execute_research, input_set_policy_fields,
        research_evaluation_policy, research_input_set_evaluation_policy, _plain, _verify_dataset_policy,
    )
    from research_tests.test_phase5_research_execution import _policy

    es, rs = authority_sessions
    primary = load(es, rs, seed_canonical(es, rs))[0][1]
    benchmark = load(es, rs, seed_canonical(
        es, rs, instrument_namespace="synthetic-benchmark", flat=True))[0][1]
    projected = project_verified_research_input_set(
        {"frame": primary, "benchmark": benchmark}, owner_id="synthetic-owner",
        primary_input="frame", graph_input_fields={"frame": ("CLOSE",), "benchmark": ("CLOSE",)})
    registry, graph = _two_source_ema_graph()
    requirements = compile_data_requirement_plan(graph, registry=registry, input_bindings=projected.input_bindings)
    resource = accept_research_resource_plan(graph, requirements, registry, input_bindings=projected.input_bindings)
    document = _plain(_policy(graph, registry, resource, projected, maximum_events=4).document)
    document.update(input_set_policy_fields(projected))
    document.update(owner_id="synthetic-owner", input_bindings=_plain(projected.policy_input_bindings),
                    session_policy_address=projected.session_policy_address,
                    resampling_policy_address=projected.resampling_policy_address,
                    event_start=projected.availability_index[0].isoformat(),
                    event_end=projected.evaluation_window[1].isoformat())
    document["evaluation_policy_address"] = content_address({k: v for k, v in document.items() if k != "evaluation_policy_address"})
    policy = research_input_set_evaluation_policy(document)
    result = execute_research(graph, registry, resource, projected, policy)
    _assert_input_set_run_outputs(result, projected, policy)
    cancelled = execute_research(graph, registry, resource, projected, policy,
                                 cancellation=CancellationToken(cancel_after_events=2))
    assert cancelled.document["status"] == "CANCELLED"
    assert cancelled.document["dataset_selection_address"] == projected.dataset_selection_address
    assert cancelled.document["source_policies"] == policy.document["source_policies"]
    assert not cancelled.batch_outputs and not cancelled.incremental_outputs
    for change in ("manifest", "source_policy", "selection", "primary"):
        forged = deepcopy(document)
        if change == "manifest":
            forged["source_policies"]["benchmark"]["dataset_manifest_address"] = primary.content_hash
        elif change == "source_policy":
            forged["source_policies"]["benchmark"]["missing_data_policy_address"] = address("wrong-source-policy")
        elif change == "selection":
            forged["dataset_selection_address"] = address("wrong-selection")
        else:
            forged["primary_input"] = "benchmark"
        forged["evaluation_policy_address"] = content_address({k: v for k, v in forged.items() if k != "evaluation_policy_address"})
        wrong = research_input_set_evaluation_policy(forged)
        with pytest.raises(ResearchExecutionRefusal, match="verified input set"):
            _verify_dataset_policy(projected, resource, wrong.document)
    legacy = {k: v for k, v in document.items()
              if k not in {"dataset_selection_address", "primary_input", "source_policies"}}
    legacy["schema"] = "research-evaluation-policy/1"
    legacy["evaluation_policy_address"] = content_address({k: v for k, v in legacy.items() if k != "evaluation_policy_address"})
    with pytest.raises(ResearchExecutionRefusal, match="verified input set"):
        _verify_dataset_policy(projected, resource, research_evaluation_policy(legacy).document)
    with pytest.raises(ResearchExecutionRefusal, match="scalar dataset"):
        _verify_dataset_policy(projected.input_sources["frame"], resource, policy.document)


def test_typed_authority_queries_are_batch_bounded(authority_sessions):
    es, rs = authority_sessions
    manifest = seed_canonical(es, rs, count=64)
    statements = [0]
    def counted(*_args):
        statements[0] += 1
    sqlalchemy_event.listen(es.bind, "before_cursor_execute", counted)
    sqlalchemy_event.listen(rs.bind, "before_cursor_execute", counted)
    try:
        assert load(es, rs, manifest)[0][1].bar_count == 64
    finally:
        sqlalchemy_event.remove(es.bind, "before_cursor_execute", counted)
        sqlalchemy_event.remove(rs.bind, "before_cursor_execute", counted)
    assert statements[0] <= 64


def test_provider_facts_are_reconstructed_once_per_authority_load(authority_sessions,monkeypatch):
    from app.market_data.observations import ProviderObservation
    es,rs=authority_sessions
    manifest=seed_canonical(es,rs,count=64)
    original=ProviderObservation.from_bytes.__func__
    calls=[0]
    def counted(cls,payload):
        calls[0]+=1
        return original(cls,payload)
    monkeypatch.setattr(ProviderObservation,"from_bytes",classmethod(counted))
    assert load(es,rs,manifest)[0][1].bar_count==64
    assert calls[0]==len(manifest.provider_observation_addresses)


@pytest.mark.parametrize("change", ["owner", "future", "cutoff", "fractional"])
def test_private_owner_and_cutoff_refusals(authority_sessions, change):
    es, rs = authority_sessions
    m = seed_canonical(es, rs)
    kwargs = {"owner":"other"} if change == "owner" else {"as_of": {
        "future":AS_OF+dt.timedelta(days=2), "cutoff":AS_OF-dt.timedelta(seconds=1),
        "fractional":AS_OF+dt.timedelta(microseconds=1)}[change]}
    with pytest.raises(CanonicalDatasetRefused, match="unavailable or unsupported"):
        load(es, rs, m, **kwargs)


@pytest.mark.parametrize("change", ["gap", "overlap", "delay", "negative_volume", "field", "media", "row_count", "late_record", "invalid", "untyped_lineage"])
def test_persisted_unsupported_rows_refuse_without_repairs(authority_sessions, change):
    es, rs = authority_sessions
    kwargs = {}
    if change == "gap": kwargs["shift_at"] = 2
    if change == "overlap": kwargs.update(shift_at=2,shift_offset=-1)
    if change == "delay": kwargs["available_delay"] = 1
    if change in {"negative_volume", "field"}:
        kwargs["mutate_observation"] = lambda i,f,o: dataclasses.replace(o,
            **({"numeric":valid(-1)} if change=="negative_volume" else {"field":"CLOSE"})) if i==0 and f=="VOLUME" else o
    if change in {"media", "row_count"}:
        kwargs["mutate_segment"] = lambda s: dataclasses.replace(s,
            **({"media_type":"application/zlib"} if change=="media" else {"row_end":5}))
    if change in {"late_record", "invalid"}:
        from app.ir.validity import NumericValue, ValidityState
        kwargs["mutate_observation"] = lambda i,f,o: dataclasses.replace(o,
            **({"recorded_at":AS_OF+dt.timedelta(seconds=1)} if change=="late_record"
               else {"numeric":NumericValue(ValidityState.MISSING, None)})) if i==0 and f=="CLOSE" else o
    if change == "untyped_lineage":
        kwargs["mutate_observation"] = lambda i,f,o: dataclasses.replace(o,
            correction_lineage=(address("untyped-correction"),)) if i==0 and f=="CLOSE" else o
    m = seed_canonical(es, rs, **kwargs)
    with pytest.raises(CanonicalDatasetRefused):
        load(es, rs, m)


def test_source_and_volume_changes_change_canonical_identity(authority_sessions):
    es, rs = authority_sessions
    first = seed_canonical(es, rs)
    volume = seed_canonical(es, rs, volume_delta=1)
    source = seed_canonical(es, rs, source_name="synthetic-ohlcv/2")
    datasets = [load(es,rs,m)[0][1] for m in (first,volume,source)]
    assert len({d.content_hash for d in datasets}) == 3
    assert datasets[0].candles == datasets[2].candles
    assert datasets[0].candles[0].volume != datasets[1].candles[0].volume


@pytest.mark.parametrize("payload", [b'{}', b'[]', b'not json', b'{"schema":NaN}'])
def test_codec_is_closed(payload):
    with pytest.raises(CanonicalDatasetRefused):
        decode_observation_index(payload)


@pytest.mark.parametrize("kwargs", [{"asset_class":"INDEX"},{"venue":"XMSE"}])
def test_unsupported_asset_and_venue_refuse(authority_sessions,kwargs):
    es,rs=authority_sessions
    manifest=seed_canonical(es,rs,**kwargs)
    with pytest.raises(CanonicalDatasetRefused):
        load(es,rs,manifest)


def test_unknown_codec_and_resolution_refuse():
    payload=canonical_json({"schema":"unknown/1","instrument_address":"sha256:"+"1"*64,
        "resolution_seconds":900,"rows":[["sha256:"+str(i)*64 for i in range(1,6)]]}).encode()
    with pytest.raises(CanonicalDatasetRefused):
        decode_observation_index(payload)
    with pytest.raises(CanonicalDatasetRefused):
        encode_observation_index("sha256:"+"1"*64,60,[["sha256:"+str(i)*64 for i in range(1,6)]])


def test_flat_prices_and_zero_volume_are_valid_not_repaired(authority_sessions):
    es, rs = authority_sessions
    manifest = seed_canonical(es, rs, flat=True)
    data = load(es, rs, manifest)[0][1]
    assert data.bar_count == 4
    assert all(c.open == c.high == c.low == c.close == 100 and c.volume == 0 for c in data.candles)


def test_user_csv_daily_equity_runs_price_research_with_bound_retrospective_clock(authority_sessions):
    from app.ir.library import REGISTRY
    from app.strategy.admission import admit_strategy, IRGraphAdmissionInput
    from research.orchestrator.graph_experiment import (
        GraphBindingRejected, build_graph_provenance, enqueue_graph_admission,
        run_published_graph_experiment,
    )

    es, rs = authority_sessions
    start = dt.date(2026, 1, 1)
    rows = ["Symbol,Date,Open,High,Low,Close,Volume"]
    recorded_days = [start + dt.timedelta(days=offset) for offset in range(100)
                     if (start + dt.timedelta(days=offset)).weekday() < 5][:64]
    for index, day in enumerate(recorded_days):
        price = 100 + index
        rows.append(f"SELF,{day.isoformat()},{price},{price+2},{price-1},{price+1},{1000+index}")
    raw = ("\n".join(rows) + "\n").encode()
    spec = UserCsvSpec(
        "User CSV upload", "user-csv:XNSE:EQUITY:SELF", "1", "SELF", "SELF",
        "XNSE", "EQUITY",
        CsvColumnMapping("Symbol", "Date", "Open", "High", "Low", "Close", "Volume"),
        date_format="%Y-%m-%d",
    )
    imported = persist_user_csv(
        es, rs, owner_id="synthetic-owner", project_id="synthetic-project", raw=raw, spec=spec,
        observed_at=dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc),
    )
    es.commit(); rs.commit()
    selection = SimpleNamespace(
        manifest_address=imported.manifest.manifest_address,
        as_of=imported.ready_as_of,
    )
    datasets = load_canonical_datasets(
        rs, execution_session=es, owner_id="synthetic-owner",
        selections=[selection], now=selection.as_of,
    )
    assert len(datasets[0][1].candles) == len(recorded_days)
    assert [candle.ts.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
            for candle in datasets[0][1].candles] == recorded_days
    assert any(right - left > dt.timedelta(days=1)
               for left, right in zip(recorded_days, recorded_days[1:]))
    graph = canonical_graph(imported.instrument.address)
    for item in graph["interface"]:
        if item["item"] == "socket":
            item["wire_type"]["domain"]["timeframe"] = "day"
    decision = admit_strategy(
        owner_id="synthetic-owner",
        source_input=IRGraphAdmissionInput(graph=graph, parameters={}, risk_model=None),
        registry=REGISTRY,
    )
    assert decision.artifact is not None, decision
    admission = enqueue_graph_admission(
        rs, owner_id="synthetic-owner", graph=graph,
        graph_content_address=content_address(graph),
        admission_address=decision.artifact.admission_address,
    )
    report = run_published_graph_experiment(
        rs, owner_id="synthetic-owner", project_id="synthetic-project", graph=graph,
        declared_content_address=content_address(graph),
        admission_address=admission.admission_address, datasets=datasets,
        program_name="User CSV daily", hypothesis_statement="Price-only retrospective research",
        min_trades=10_000, n_folds=2, seed=7,
    )
    assert report["total_bars"] == 64
    binding = datasets[0][1].binding
    assert binding["time_interpretation"]["retrospective_evaluation"] is True
    assert binding["time_interpretation"]["actual_source_observed_at"] == \
        "2026-04-01T00:00:00+00:00"
    clock = canonical_graph(imported.instrument.address, block="time_of_day")
    for item in clock["interface"]:
        if item["item"] == "socket":
            item["wire_type"]["domain"]["timeframe"] = "day"
    with pytest.raises(GraphBindingRejected):
        build_graph_provenance(
            project_id="synthetic-project", graph=clock,
            declared_content_address=content_address(clock), datasets=datasets,
        )


def test_raw_bytes_corruption_and_oversize_refuse_before_typed_loading(authority_sessions, monkeypatch):
    import research.data.canonical_dataset as adapter
    from app.db.models import AuthorityProviderObservation, AuthorityRawSegment
    from sqlalchemy import select, update
    es, rs = authority_sessions
    manifest = seed_canonical(es, rs)
    raw_address = es.scalar(select(AuthorityProviderObservation.raw_segment_address).where(
        AuthorityProviderObservation.address == manifest.provider_observation_addresses[0]))
    original = es.scalar(select(AuthorityRawSegment.raw_bytes).where(AuthorityRawSegment.address == raw_address))
    # Simulate a damaged restored object in this test's disposable database only.
    # Ordinary updates remain forbidden by the production immutability trigger.
    es.execute(text("DROP TRIGGER authority_raw_segments_refuse_update"))
    es.commit()
    es.execute(update(AuthorityRawSegment).where(AuthorityRawSegment.address == raw_address).values(raw_bytes=original+b" "))
    es.commit()
    with pytest.raises(CanonicalDatasetRefused):
        load(es,rs,manifest)
    es.execute(update(AuthorityRawSegment).where(AuthorityRawSegment.address == raw_address).values(raw_bytes=b"x"*(adapter.MAX_BYTES+1)))
    es.commit()
    def forbidden(*args, **kwargs):
        raise AssertionError("oversized object reached typed loader")
    monkeypatch.setattr(adapter, "load_verified_dataset_authority", forbidden)
    with pytest.raises(CanonicalDatasetRefused):
        load(es,rs,manifest)


def canonical_graph(instrument_address, *, block="body_frac_gt"):
    from research_tests.test_ir_block_components import _graph
    graph = _graph(block)
    graph["identifier"] = f"synthetic.q03.{block}"
    for item in graph["interface"]:
        if item["item"] == "socket":
            item["wire_type"]["domain"] = {"instrument": instrument_address, "timeframe": "15m"}
    return graph


def test_canonical_binding_enters_existing_spec_and_refuses_clock(authority_sessions):
    from app.ir.hashing import content_address
    from app.ir.library import REGISTRY
    from app.strategy.admission import admit_strategy, IRGraphAdmissionInput
    from research.orchestrator.graph_experiment import (
        enqueue_graph_admission, run_published_graph_experiment, build_graph_provenance, GraphBindingRejected,
    )
    from research.domain.models import ExperimentSpec
    es, rs = authority_sessions
    m = seed_canonical(es, rs, count=64)
    datasets = load(es,rs,m)
    graph = canonical_graph(m.instrument_addresses[0])
    decision = admit_strategy(owner_id="synthetic-owner",
        source_input=IRGraphAdmissionInput(graph=graph, parameters={}, risk_model=None), registry=REGISTRY)
    assert decision.artifact is not None, decision
    admission = enqueue_graph_admission(rs, owner_id="synthetic-owner", graph=graph,
        graph_content_address=content_address(graph), admission_address=decision.artifact.admission_address)
    report = run_published_graph_experiment(rs, owner_id="synthetic-owner", project_id="synthetic-project",
        graph=graph, declared_content_address=content_address(graph), admission_address=admission.admission_address,
        datasets=datasets, program_name="Synthetic Q03", hypothesis_statement="Synthetic integration only",
        min_trades=10000, n_folds=2, seed=7)
    spec = rs.get(ExperimentSpec, ("synthetic-owner", report["spec_id"]))
    recipe = json.loads(spec.recipe_json)
    assert recipe["graph_provenance"]["canonical_dataset_bindings"]["bindings"][datasets[0][1].instrument_key]["manifest_address"] == m.manifest_address
    clock = canonical_graph(m.instrument_addresses[0], block="time_of_day")
    with pytest.raises(GraphBindingRejected):
        build_graph_provenance(project_id="synthetic-project", graph=clock,
            declared_content_address=content_address(clock), datasets=datasets)


def test_postgresql_real_typed_authority_reopens_and_preserves_full_identity(pg_sandbox):
    ee, re = pg_sandbox.execution_engine, pg_sandbox.research_engine
    Base.metadata.create_all(ee)
    init_research_db(re)
    with Session(ee) as es, Session(re) as rs:
        manifest = seed_canonical(es, rs, venue="XBOM")
        inst, data = load(es, rs, manifest)[0]
        assert inst.segment == "BSE"
        assert data.binding["projection"]["charge_segment"] == "BSE_EQ"
    with Session(ee) as es, Session(re) as rs:
        assert load(es,rs,manifest)[0][1] == data
        with pytest.raises(CanonicalDatasetRefused):
            load(es,rs,manifest,owner="other")


def test_actual_next_open_fills_and_causal_prefix(authority_sessions):
    from app.ir.library import LIBRARY, IMPLEMENTATIONS
    from research.strategy.builder.ir_strategy import IRGraphStrategy
    from research.evaluation.kernels import simulate, compute_signals
    from app.core.market_hours import ist_epoch
    from app.backtest.engine import backtest_qty, backtest_charge_segment
    es, rs = authority_sessions
    manifest = seed_canonical(es,rs,count=64)
    inst, data = load(es,rs,manifest)[0]
    graph = canonical_graph(manifest.instrument_addresses[0])
    graph["nodes"][1]["overrides"] = {"frac":0.1}
    strategy = IRGraphStrategy(graph, (LIBRARY,IMPLEMENTATIONS))
    full = compute_signals(data.candles, strategy, {})
    prefix = compute_signals(data.candles[:6], strategy, {})
    import pandas as pd
    pd.testing.assert_frame_equal(full.iloc[:6], prefix)
    trades, _ = simulate(data.candles, inst, data.interval, strategy=strategy,
        capital=10000, slippage_pct=0.001)
    assert trades
    assert trades[0].entry_time == ist_epoch(data.candles[1].ts)
    assert trades[0].entry_price == pytest.approx(data.candles[1].open*1.0005)
    assert trades[0].entry_time != ist_epoch(data.candles[0].ts)
    assert backtest_charge_segment(inst) == "NSE_EQ"
    assert backtest_qty(inst,100,10000) == 100
    from app.engine.charges import (
        CORRECTED_RESEARCH_CHARGE_SCHEDULE,
        compute_charges,
    )
    trade = trades[0]
    expected_charges = (
        compute_charges(
            "NSE_EQ", "BUY", trade.entry_price, trade.qty,
            schedule_id=CORRECTED_RESEARCH_CHARGE_SCHEDULE,
        )["total"]
        + compute_charges(
            "NSE_EQ", "SELL", trade.exit_price, trade.qty,
            schedule_id=CORRECTED_RESEARCH_CHARGE_SCHEDULE,
        )["total"]
    )
    assert trade.charges == pytest.approx(expected_charges)
    assert trade.net_pnl == pytest.approx(trade.gross_pnl-trade.charges)


def _session_import(es, rs, metadata=True):
    raw = b"Date,Open,High,Low,Close\n2026-01-01,99,100,96,99\n2026-01-02,106,108,104,106\n2026-01-03,105,108,104,105\n"
    document = {"schema": "user-declared-daily-sessions/1", "provenance": "USER_DECLARED",
        "source": "Synthetic declared sessions; includes a short session", "timezone": "Asia/Kolkata",
        "complete_full_sessions": True, "rows": [{"date_label": f"2026-01-0{i}",
            "session_id": f"synthetic:{i}", "session_open_at": f"2026-01-0{i}T04:00:00+00:00",
            "session_close_at": f"2026-01-0{i}T{'08' if i == 2 else '10'}:00:00+00:00"}
            for i in range(1, 4)]}
    if callable(metadata):
        metadata(document)
    spec = UserCsvSpec("Synthetic sessions", "user-csv:session-test", "1", "SELF", "SELF",
        "XNSE", "INDEX", CsvColumnMapping(None, "Date", "Open", "High", "Low", "Close"),
        date_format="%Y-%m-%d")
    imported = persist_user_csv(es, rs, owner_id="synthetic-owner", project_id="sessions", raw=raw,
        spec=spec, observed_at=dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc),
        session_metadata=canonical_json(document).encode() if metadata else None)
    es.commit(); rs.commit()
    selection = SimpleNamespace(manifest_address=imported.manifest.manifest_address,
        as_of=imported.ready_as_of)
    data = load_canonical_datasets(rs, execution_session=es, owner_id="synthetic-owner",
        selections=[selection], now=selection.as_of)[0][1]
    return data, raw


def test_imported_sessions_persist_project_and_run_registered_gap(authority_sessions):
    from sqlalchemy import select
    from app.db.models import AuthorityRawSegment
    from app.ir.first_party import historical_daily_gaps as g
    from app.ir.first_party.analytical_v2 import contracts
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.streaming_reference import evaluate_v2_prefix_stream
    from tests.test_strategy_registry import _gap_graph
    es, rs = authority_sessions
    data, raw = _session_import(es, rs)
    assert raw in es.scalars(select(AuthorityRawSegment.raw_bytes)).all()
    assert data._alignment_fact.calendar == "USER_DECLARED_DATE_LABEL"
    assert data.binding["time_interpretation"]["historical_source_availability"] == "NOT_SUPPLIED"
    projected = project_verified_research_inputs(data, owner_id="synthetic-owner", graph_input_fields=g._FIELDS)
    assert projected.availability_index[0] == pd.Timestamp("2026-01-01T18:30:00Z")
    assert projected.inputs["session"]["session_close_at"].iloc[1] == "2026-01-02T08:00:00+00:00"
    facts = projected.input_bindings.document["inputs"]
    assert facts["session"]["binding"]["derived_local"] is True
    assert facts["frame"]["binding"]["derived_local"] is False
    assert facts["session"]["binding"]["market_truth_address"] == facts["frame"]["binding"]["market_truth_address"]
    graph = resolve_v2(_gap_graph(), REGISTRY)
    node = graph.nodes[0]
    binding = contracts.input_binding_for_node(graph, node, g.NODE_CONTRACTS[g.KEY], projected.input_bindings)
    bound = contracts.materialize_node_contract(g.NODE_CONTRACTS[g.KEY], g.CONTRACT_BINDINGS[g.KEY], {}, binding)
    context = lambda node, values: {"bound_contract": bound}
    batch = evaluate_v2(graph, projected.inputs, REGISTRY, evaluation_context_resolver=context)
    prefix = evaluate_v2_prefix_stream(graph, projected.inputs, REGISTRY, evaluation_context_resolver=context)
    for name in batch:
        pd.testing.assert_series_equal(batch[name], prefix[name])
    assert batch["bullish_proximal"].iloc[1].value == 104.
    assert batch["bullish_distal"].iloc[1].value == 100.
    assert batch["bullish_formed_at"].iloc[1].value == pd.Timestamp("2026-01-02T08:00:00Z").timestamp()


@pytest.mark.parametrize("change", [
    lambda d: d.update(complete_full_sessions=False),
    lambda d: d.update(timezone="UTC"),
    lambda d: d.update(source=""),
    lambda d: d["rows"].pop(),
    lambda d: d["rows"][1].update(session_id="synthetic:1"),
    lambda d: d["rows"][1].update(date_label="2026-01-01"),
    lambda d: d["rows"][1].update(session_open_at="2026-01-01T09:00:00+00:00"),
    lambda d: d["rows"][1].update(session_close_at="2026-01-02T19:00:00+00:00"),
    lambda d: d["rows"][1].update(session_close_at="2026-01-02T08:00:00"),
])
def test_imported_sessions_refuse_incomplete_or_conflicting_metadata(authority_sessions, change):
    from research.data.imported_sessions import ImportedSessionsRefused
    with pytest.raises(ImportedSessionsRefused):
        _session_import(*authority_sessions, metadata=change)


def test_imported_sessions_missing_remains_unavailable(authority_sessions):
    from app.ir.first_party import historical_daily_gaps as g
    data, _ = _session_import(*authority_sessions, metadata=False)
    assert data.binding["session_metadata"] is None
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_inputs(data, owner_id="synthetic-owner", graph_input_fields=g._FIELDS)


@pytest.mark.parametrize("change", ["bytes", "owner"])
def test_imported_sessions_persisted_tampering_refuses(authority_sessions, change):
    from sqlalchemy import select, update
    from app.db.models import AuthorityRawSegment
    es, rs = authority_sessions
    data, _ = _session_import(es, rs)
    source = data.binding["session_metadata"]["source_address"]
    row = es.scalar(select(AuthorityRawSegment).where(AuthorityRawSegment.address == source))
    assert row is not None
    values = {"raw_bytes": b"{}"} if change == "bytes" else {"owner_id": "foreign-owner"}
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError, match="immutable"):
        es.execute(update(AuthorityRawSegment).where(AuthorityRawSegment.address == source).values(**values))
    es.rollback(); es.expire_all()
    selection = SimpleNamespace(manifest_address=data.content_hash,
        as_of=dt.datetime.fromisoformat(data.binding["as_of"]))
    reloaded = load_canonical_datasets(rs, execution_session=es, owner_id="synthetic-owner",
        selections=[selection], now=selection.as_of)[0][1]
    assert reloaded.binding["session_metadata"] == data.binding["session_metadata"]


def _current_capture_source(es, owner="capture-owner", project_id="capture-project", asset_class="EQUITY", physical=None, base_at=T0):
    from app.db.models import Organization, Project
    from app.market_truth.identity import ProviderEntity, ProviderProduct, ProviderContract, ProviderInstrumentAlias, persist_provider_identity
    from app.market_truth.rulebook import MarketTruthSnapshot
    from app.market_truth.identity import Quality
    from app.market_data.capability import CapabilityProfile, ProviderConformance
    from app.market_data.kite_observations import KiteMappingContext
    from tests.test_connection_store import _store
    if es.get(Organization, owner) is None:
        es.add(Organization(organization_id=owner, name="Synthetic capture")); es.flush()
    if es.get(Project, project_id) is None:
        es.add(Project(project_id=project_id, owner_id=owner, name="Capture", description="", status="active")); es.flush()
    connection = _store(es, owner).create_data_connection()
    connection.created_at = connection.updated_at = connection.last_authenticated_at = base_at.replace(tzinfo=None)
    physical = physical or CanonicalPhysicalInstrument("synthetic-capture", "1", "XNSE", asset_class, "SPOT", "INR", None)
    entity = ProviderEntity("synthetic", "kite", "Synthetic provider authority")
    product = ProviderProduct(entity.address, "kite-connect-v3", "kite-connect", "3")
    contract = ProviderContract(owner, product.address, "RESEARCH", ("HISTORICAL",), base_at, None, address("synthetic-rights"))
    alias = ProviderInstrumentAlias(product.address, "408065", "SELF", physical.address, "3", base_at, None,
        "kite-connect", address("synthetic-alias"))
    persist_canonical_instrument(es, physical); persist_provider_identity(es, entity, product, contract)
    persist_provider_alias(es, alias)
    algorithm = a.DeterministicAlgorithm(owner, "synthetic-policy", "1", address("policy-code"), (address("policy-test"),), base_at)
    a.persist_deterministic_algorithm(es, algorithm)
    truth = MarketTruthSnapshot((), base_at, base_at+dt.timedelta(days=1), base_at, Quality.OBSERVED,
        authority_scope="RESEARCH", instrument_addresses=(physical.address,), source_evidence=(address("synthetic-truth"),))
    persist_market_truth_snapshot(es, truth)
    alignment = a.AlignmentPolicy(owner, "SYNTHETIC_CALENDAR", "regular", "UTC", 900, truth.address, algorithm.address, base_at)
    missing = a.MissingDataPolicy(owner, "REFUSE", (), algorithm.address, base_at)
    adjustment = a.AdjustmentPolicy(owner, (physical.address,), (truth.address,), "NONE", algorithm.address, base_at)
    roll = a.RollPolicy(owner, (physical.address,), (truth.address,), "NONE", algorithm.address, base_at, "NOT_APPLICABLE")
    for writer, value in ((a.persist_alignment_policy, alignment), (a.persist_missing_data_policy, missing),
                          (a.persist_adjustment_policy, adjustment), (a.persist_roll_policy, roll)):
        writer(es, value)
    coverage = [dict(_coverage(field=field, timeframe=900), alignment={"kind":"EXACT","maximum_skew_seconds":0}) for field in FIELDS]
    offers = [dict(_offer(field=field, timeframe=900), alignment={"kind":"EXACT","maximum_skew_seconds":0}) for field in FIELDS]
    for row in coverage:
        row['history'] = {**row['history'], 'from': base_at-dt.timedelta(days=1), 'to': base_at+dt.timedelta(days=1)}
    for row in offers:
        row.update(available_from=base_at-dt.timedelta(days=1), available_to=base_at+dt.timedelta(days=1))
    conformance = ProviderConformance(product.address, FIELDS, (900,), "synthetic injected response", "1", base_at,
        base_at+dt.timedelta(hours=1), (address("synthetic-conformance"),), "PASS", tuple(coverage))
    persist_provider_conformance(es, conformance)
    profile = CapabilityProfile(owner, "RESEARCH", 1, base_at, base_at+dt.timedelta(days=1), conformance.address,
        tuple(offers), 0, entity.address, product.address, contract.address)
    persist_capability_profile(es, profile)
    event = base_at + dt.timedelta(hours=4)
    raw = ('{ "status": "success", "data": {"candles": [["'+event.isoformat()+'",100,102,99,101,1234]]}}').encode()
    captured = event + dt.timedelta(seconds=902)
    return dict(owner_id=owner, project_id=project_id, connection_id=connection.id, raw_response=raw,
        context=KiteMappingContext(owner, entity.address, product.address, contract.address, alias, physical, "CURRENT_DUMP"),
        capability_profile_address=profile.capability_profile_address, alignment_policy_address=alignment.address,
        missing_data_policy_address=missing.address, adjustment_policy_address=adjustment.address, roll_policy_address=roll.address,
        captured_at=captured, recorded_at=captured+dt.timedelta(seconds=1), as_of=captured+dt.timedelta(seconds=2),
        maximum_age_seconds=60)


@pytest.mark.parametrize("asset_class", ["EQUITY", "INDEX"])
def test_current_capture_persists_exact_bytes_and_projects_actual_availability(authority_sessions, monkeypatch, asset_class):
    from app.db.models import AuthorityRawSegment
    from sqlalchemy import select
    from research.data.provider_capture import publish_current_kite_capture
    import app.providers.connection_store as connections
    es, rs = authority_sessions
    kwargs = _current_capture_source(es, asset_class=asset_class)
    monkeypatch.setattr(connections, "unseal", lambda *_args: pytest.fail("capture read credentials"))
    monkeypatch.setattr(connections.OwnedConnectionStore, "data_connection", lambda *_args: pytest.fail("capture called provider facade"))
    result = publish_current_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    assert kwargs["raw_response"] in es.scalars(select(AuthorityRawSegment.raw_bytes)).all()
    from app.market_data.observations import load_provider_observation
    sources = [load_provider_observation(es, value) for value in result.manifest.provider_observation_addresses]
    assert all(value.available_at == kwargs["captured_at"] and value.recorded_at == kwargs["recorded_at"] for value in sources)
    selection = SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=kwargs["as_of"])
    data = load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[selection], now=kwargs["as_of"])[0][1]
    projection = project_verified_research_inputs(data, owner_id=kwargs["owner_id"], graph_input_fields={"frame":FIELDS})
    assert data.bar_count == 1 and data.candles[0].close == 101 and data.candles[0].volume == 1234
    assert projection.availability_index[0] == pd.Timestamp(kwargs["captured_at"])
    assert projection.bar_open_index[0] == pd.Timestamp(T0+dt.timedelta(hours=4))
    assert data.binding["time_interpretation"]["retrospective_evaluation"] is False
    assert data.binding["time_interpretation"]["capture_kind"] == "CURRENT_COMPLETED_BAR"
    assert data.binding["time_interpretation"]["actual_source_lag_seconds"] == 2
    assert data.binding["current_capture"]["connection_id"] == kwargs["connection_id"]
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_inputs(data, owner_id=kwargs['owner_id'], graph_input_fields={'frame': FIELDS},
            evaluation_freshness_seconds=60)
    assert publish_current_kite_capture(es, rs, **kwargs).manifest == result.manifest


@pytest.mark.parametrize("change", ["forming", "stale", "before_completion", "recording_order", "foreign", "revoked",
    "missing_profile", "missing_policy", "wrong_mapping", "fractional", "multiple", "malformed", "future_connection", "duplicate_key",
    "subsecond_recording_order"])
def test_current_capture_refuses_before_publishing_authority(authority_sessions, change):
    from app.db.models import AuthorityRawSegment, BrokerConnection
    from sqlalchemy import select, func
    from research.domain.models import ResearchDatasetManifestV2
    from research.data.provider_capture import CurrentCaptureRefused, publish_current_kite_capture
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    document = json.loads(kwargs["raw_response"])
    if change == "forming":
        document["data"]["candles"][0][0] = kwargs["captured_at"].isoformat()
    if change == "stale":
        kwargs["as_of"] += dt.timedelta(seconds=61)
    if change == "before_completion":
        kwargs["captured_at"] -= dt.timedelta(seconds=3)
    if change == "recording_order":
        kwargs["recorded_at"] = kwargs["captured_at"]-dt.timedelta(seconds=1)
    if change == "subsecond_recording_order":
        kwargs["captured_at"] += dt.timedelta(microseconds=123456)
        kwargs["recorded_at"] = kwargs["captured_at"] - dt.timedelta(microseconds=1)
    if change == "foreign":
        kwargs["owner_id"] = "foreign-owner"
    if change == "revoked":
        es.get(BrokerConnection, kwargs["connection_id"]).status = "revoked"
    if change == "future_connection":
        es.get(BrokerConnection, kwargs["connection_id"]).last_authenticated_at = (kwargs["as_of"]+dt.timedelta(seconds=1)).replace(tzinfo=None)
    if change == "missing_profile":
        kwargs["capability_profile_address"] = address("absent-profile")
    if change == "missing_policy":
        kwargs["alignment_policy_address"] = address("absent-policy")
    if change == "wrong_mapping":
        kwargs["context"] = dataclasses.replace(kwargs["context"], provider_contract_address=address("absent-contract"))
    if change == "fractional":
        document["data"]["candles"][0][0] = "2026-08-01T04:00:00.123456Z"
    if change == "multiple":
        document["data"]["candles"].append(document["data"]["candles"][0])
    kwargs["raw_response"] = b"not-json" if change == "malformed" else json.dumps(document).encode()
    if change == "duplicate_key":
        kwargs["raw_response"] = kwargs["raw_response"].replace(b'"status": "success"', b'"status": "error", "status": "success"')
    with pytest.raises(CurrentCaptureRefused):
        publish_current_kite_capture(es, rs, **kwargs)
    assert es.scalar(select(func.count()).select_from(AuthorityRawSegment)) == 0
    assert rs.scalar(select(func.count()).select_from(ResearchDatasetManifestV2)) == 0


def test_current_capture_stale_or_revoked_reload_refuses_and_recapture_needs_explicit_lineage(authority_sessions):
    from app.db.models import BrokerConnection
    from research.data.provider_capture import CurrentCaptureRefused, publish_current_kite_capture
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    result = publish_current_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    newer = {**kwargs, "captured_at": kwargs["captured_at"]+dt.timedelta(seconds=1),
        "recorded_at": kwargs["recorded_at"]+dt.timedelta(seconds=1), "as_of": kwargs["as_of"]+dt.timedelta(seconds=1)}
    with pytest.raises(CurrentCaptureRefused) as error:
        publish_current_kite_capture(es, rs, **newer)
    assert error.value.code == "CURRENT_CAPTURE_EVENT_ALREADY_RECORDED"
    for stale in (True, False):
        as_of = kwargs["as_of"] + dt.timedelta(seconds=61 if stale else 0)
        if not stale:
            es.get(BrokerConnection, kwargs["connection_id"]).status = "revoked"; es.commit()
        with pytest.raises(CanonicalDatasetRefused):
            load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
                selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=as_of)], now=as_of)


@pytest.mark.parametrize("change", ["unentitled", "missing_field", "semantic_change", "future_conformance"])
def test_current_capture_requires_existing_complete_entitlement(authority_sessions, change):
    from app.market_data.authority import load_capability_profile
    from research.data.provider_capture import CurrentCaptureRefused, publish_current_kite_capture
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    profile = load_capability_profile(es, kwargs["capability_profile_address"], at_time=kwargs["as_of"])
    offers = tuple({**offer, "entitled":False} for offer in profile.offers) if change == "unentitled" else profile.offers
    if change == "missing_field":
        offers = offers[:-1]
    profile = dataclasses.replace(profile, offers=offers, change_level=3 if change == "semantic_change" else 0)
    if change == "future_conformance":
        from app.market_data.authority import load_provider_conformance
        conformance = load_provider_conformance(es, profile.conformance_evidence_address)
        conformance = dataclasses.replace(conformance, observed_to=kwargs["as_of"]+dt.timedelta(seconds=1))
        persist_provider_conformance(es, conformance)
        profile = dataclasses.replace(profile, conformance_evidence_address=conformance.address)
    persist_capability_profile(es, profile)
    kwargs["capability_profile_address"] = profile.capability_profile_address
    with pytest.raises(CurrentCaptureRefused):
        publish_current_kite_capture(es, rs, **kwargs)


@pytest.mark.parametrize("change", ["revoked", "late_authentication"])
def test_current_capture_rechecks_revocation_at_publication_boundary(authority_sessions, monkeypatch, change):
    from app.db.models import BrokerConnection, AuthorityRawSegment
    from sqlalchemy import select, func
    import research.data.provider_capture as capture
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    original = capture._normalization
    def revoke(*args):
        result = original(*args)
        connection = es.get(BrokerConnection, kwargs["connection_id"])
        if change == "revoked":
            connection.status = "revoked"
        else:
            connection.last_authenticated_at = (kwargs["captured_at"] + dt.timedelta(seconds=1)).replace(tzinfo=None)
        es.flush()
        return result
    monkeypatch.setattr(capture, "_normalization", revoke)
    with pytest.raises(capture.CurrentCaptureRefused):
        capture.publish_current_kite_capture(es, rs, **kwargs)
    assert es.scalar(select(func.count()).select_from(AuthorityRawSegment)) == 0


@pytest.mark.parametrize("field", ["connection_id", "capability_profile_address", "contract"])
def test_current_capture_refuses_existing_foreign_authority(authority_sessions, field):
    from research.data.provider_capture import CurrentCaptureRefused, publish_current_kite_capture
    es, rs = authority_sessions
    own = _current_capture_source(es)
    foreign = _current_capture_source(es, "capture-foreign", "capture-foreign-project")
    if field == "contract":
        own["context"] = dataclasses.replace(own["context"], provider_contract_address=foreign["context"].provider_contract_address)
    else:
        own[field] = foreign[field]
    with pytest.raises(CurrentCaptureRefused):
        publish_current_kite_capture(es, rs, **own)


def test_current_capture_refuses_future_policy_algorithm_before_writes(authority_sessions):
    from research.data.provider_capture import CurrentCaptureRefused, publish_current_kite_capture
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    alignment = a.load_alignment_policy(es, kwargs["alignment_policy_address"])
    algorithm = a.load_deterministic_algorithm(es, alignment.algorithm_address)
    future = dataclasses.replace(algorithm, recorded_at=kwargs["as_of"]+dt.timedelta(seconds=1))
    a.persist_deterministic_algorithm(es, future)
    alignment = dataclasses.replace(alignment, algorithm_address=future.address)
    a.persist_alignment_policy(es, alignment)
    kwargs["alignment_policy_address"] = alignment.address
    with pytest.raises(CurrentCaptureRefused):
        publish_current_kite_capture(es, rs, **kwargs)


def test_current_capture_normalization_vector_is_explicit_and_executable():
    from research.data.provider_capture import _NORMALIZATION_VECTOR, _numeric_values
    assert _numeric_values(_NORMALIZATION_VECTOR[0]) == _NORMALIZATION_VECTOR[1]


@pytest.mark.parametrize("receipt_microseconds", [0, 123456])
def test_current_capture_same_second_receipt_never_projects_future_data(authority_sessions, receipt_microseconds):
    from research.data.provider_capture import publish_current_kite_capture
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    kwargs["captured_at"] += dt.timedelta(microseconds=receipt_microseconds)
    kwargs["recorded_at"] = kwargs["as_of"] = kwargs["captured_at"]
    result = publish_current_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    assert dt.datetime.fromisoformat(result.manifest.availability_end) > kwargs["as_of"]
    replay_at = kwargs["as_of"] + dt.timedelta(microseconds=(-receipt_microseconds) % 1_000_000)
    selection = SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=replay_at)
    data = load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[selection], now=replay_at)[0][1]
    projection = project_verified_research_inputs(data, owner_id=kwargs["owner_id"], graph_input_fields={"frame":FIELDS})
    assert projection.availability_index[0] == pd.Timestamp(kwargs["as_of"])
    assert data.binding["time_interpretation"]["actual_source_lag_seconds"] == (3 if receipt_microseconds else 2)
    assert projection.bar_open_index[0] < projection.availability_index[0]
    with pytest.raises(CanonicalDatasetRefused):
        load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
            selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address,
                as_of=kwargs["as_of"].replace(microsecond=0) - dt.timedelta(seconds=not receipt_microseconds))],
            now=kwargs["as_of"])
    from app.api.research_dataset_routes import _item
    from app.api.ir_experiment_routes import CanonicalDatasetSelection
    from research.domain.models import ResearchDatasetManifestV2
    item = _item(rs, es, rs.get(ResearchDatasetManifestV2,
        (kwargs["owner_id"], result.manifest.manifest_address)))
    cutoff = dt.datetime.fromisoformat(item.as_of)
    assert cutoff.microsecond == 0 and cutoff >= kwargs["recorded_at"]
    basis = max(kwargs["recorded_at"], dt.datetime.fromisoformat(result.manifest.availability_end))
    assert dt.timedelta(0) <= cutoff - basis < dt.timedelta(seconds=1)
    selection = CanonicalDatasetSelection(kind="canonical_manifest_v2",
        manifest_address=item.manifest_address, as_of=item.as_of)
    if cutoff > kwargs["as_of"]:
        with pytest.raises(CanonicalDatasetRefused):
            load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
                selections=[selection], now=kwargs["as_of"])
    later = load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[selection], now=cutoff)[0][1]
    assert later.binding["time_interpretation"]["actual_source_observed_at"] == kwargs["captured_at"].isoformat()


def test_current_capture_catalogue_cutoff_keeps_later_known_policy_available(authority_sessions):
    from app.api.research_dataset_routes import _item
    from research.data.provider_capture import publish_current_kite_capture
    from research.domain.models import ResearchDatasetManifestV2
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    kwargs["recorded_at"] = kwargs["captured_at"]
    policy = dataclasses.replace(a.load_missing_data_policy(es, kwargs["missing_data_policy_address"]),
        recorded_at=kwargs["captured_at"] + dt.timedelta(microseconds=500000))
    a.persist_missing_data_policy(es, policy)
    kwargs["missing_data_policy_address"] = policy.address
    result = publish_current_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    item = _item(rs, es, rs.get(ResearchDatasetManifestV2,
        (kwargs["owner_id"], result.manifest.manifest_address)))
    cutoff = dt.datetime.fromisoformat(item.as_of)
    assert cutoff >= policy.recorded_at and cutoff.microsecond == 0
    selection = SimpleNamespace(manifest_address=item.manifest_address, as_of=cutoff)
    assert load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[selection], now=kwargs["as_of"])[0][1].bar_count == 1


@pytest.mark.parametrize("change", ["ends_during_bar", "ends_before_capture", "quote_only"])
def test_current_capture_requires_current_historical_contract(authority_sessions, change):
    from app.market_data.authority import load_capability_profile
    from app.market_truth.identity import load_provider_identity, persist_provider_identity
    from research.data.provider_capture import CurrentCaptureRefused, publish_current_kite_capture
    es, rs = authority_sessions
    kwargs = _current_capture_source(es)
    profile = load_capability_profile(es, kwargs["capability_profile_address"], at_time=kwargs["as_of"])
    entity, product, contract = load_provider_identity(es, kwargs["context"].provider_contract_address)
    contract = dataclasses.replace(contract, effective_from=T0-dt.timedelta(seconds=1))
    if change == "quote_only":
        contract = dataclasses.replace(contract, permitted_uses=("QUOTE",))
    else:
        offset = 452 if change == "ends_during_bar" else 1
        contract = dataclasses.replace(contract, effective_to=kwargs["captured_at"]-dt.timedelta(seconds=offset))
    persist_provider_identity(es, entity, product, contract)
    profile = dataclasses.replace(profile, provider_contract_address=contract.address)
    persist_capability_profile(es, profile)
    kwargs["context"] = dataclasses.replace(kwargs["context"], provider_contract_address=contract.address)
    kwargs["capability_profile_address"] = profile.capability_profile_address
    with pytest.raises(CurrentCaptureRefused):
        publish_current_kite_capture(es, rs, **kwargs)


def _historical_capture_source(es, count=3, *, base_at=T0, **scope):
    kwargs = _current_capture_source(es, base_at=base_at, **scope)
    kwargs.pop("maximum_age_seconds")
    start = base_at + dt.timedelta(hours=4)
    rows = [[(start + dt.timedelta(minutes=15 * index)).isoformat(),
             100 + index, 102 + index, 99 + index, 101 + index, 1234 + index]
            for index in range(count)]
    kwargs.update(raw_response=json.dumps({"status": "success", "data": {"candles": rows}}).encode(),
        requested_start=start - dt.timedelta(minutes=15),
        requested_end=start + dt.timedelta(minutes=15 * count),
        captured_at=base_at + dt.timedelta(hours=10), recorded_at=base_at + dt.timedelta(hours=10, seconds=1),
        as_of=base_at + dt.timedelta(hours=10, seconds=2))
    return kwargs


@pytest.mark.parametrize("receipt_microseconds", [0, 123456])
def test_historical_capture_roundtrips_as_retrospective_provider_data(authority_sessions, receipt_microseconds):
    from app.db.models import AuthorityRawSegment
    from sqlalchemy import select
    from research.data.historical_capture import publish_historical_kite_capture
    es, rs = authority_sessions
    kwargs = _historical_capture_source(es)
    for name in ("captured_at", "recorded_at", "as_of"):
        kwargs[name] += dt.timedelta(microseconds=receipt_microseconds)
    result = publish_historical_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    replay_at = kwargs["as_of"] + dt.timedelta(microseconds=(-receipt_microseconds) % 1_000_000)
    data = load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=replay_at)],
        now=replay_at)[0][1]
    assert data.bar_count == 3 and [candle.close for candle in data.candles] == [101, 102, 103]
    assert kwargs["raw_response"] in es.scalars(select(AuthorityRawSegment.raw_bytes)).all()
    assert "current_capture" not in data.binding
    assert data.binding["historical_capture"]["requested_start"] == kwargs["requested_start"].isoformat()
    interpretation = data.binding["time_interpretation"]
    assert interpretation["retrospective_evaluation"] is True
    assert interpretation["capture_kind"] == "HISTORICAL_RESEARCH"
    assert interpretation["historical_source_availability"] == "NOT_SUPPLIED"
    assert interpretation["actual_source_observed_at"] == kwargs["captured_at"].isoformat()
    assert result.manifest.recorded_at == kwargs["recorded_at"].isoformat()
    projection = project_verified_research_inputs(data, owner_id=kwargs["owner_id"], graph_input_fields={"frame": FIELDS})
    assert projection.availability_index[0] == pd.Timestamp(T0 + dt.timedelta(hours=4, minutes=15))
    assert projection.availability_index[-1] < pd.Timestamp(kwargs["captured_at"])
    from app.api.research_dataset_routes import _item
    from research.domain.models import ResearchDatasetManifestV2
    item = _item(rs, es, rs.get(ResearchDatasetManifestV2, (kwargs["owner_id"], result.manifest.manifest_address)))
    assert item.source_type == "PROVIDER_AUTHORITY"
    assert item.historical_source_availability == "NOT_SUPPLIED"
    assert item.calendar_coverage == "NOT_ASSERTED"
    from app.api.ir_experiment_routes import CanonicalDatasetSelection
    cutoff = dt.datetime.fromisoformat(item.as_of)
    assert cutoff.microsecond == 0 and cutoff >= kwargs["recorded_at"]
    basis = max(kwargs["recorded_at"], dt.datetime.fromisoformat(result.manifest.availability_end))
    assert dt.timedelta(0) <= cutoff - basis < dt.timedelta(seconds=1)
    api_selection = CanonicalDatasetSelection(kind="canonical_manifest_v2",
        manifest_address=item.manifest_address, as_of=item.as_of)
    assert load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[api_selection], now=kwargs["as_of"])[0][1].bar_count == 3


@pytest.mark.parametrize("change,code", [
    ("empty", "HISTORICAL_CAPTURE_ROW_COUNT"),
    ("outside", "HISTORICAL_CAPTURE_OUTSIDE_REQUEST"),
    ("gap", "HISTORICAL_CAPTURE_SESSION_GAPS"),
    ("foreign", "HISTORICAL_CAPTURE_UNAVAILABLE"),
    ("future", "HISTORICAL_CAPTURE_UNAVAILABLE"),
    ("fractional_bar", "HISTORICAL_CAPTURE_BAR_PRECISION"),
    ("fractional_request", "HISTORICAL_CAPTURE_UNAVAILABLE"),
])
def test_historical_capture_refuses_bad_range_before_publication(authority_sessions, change, code):
    from research.data.historical_capture import HistoricalCaptureRefused, publish_historical_kite_capture
    from research.domain.models import ResearchDatasetManifestV2
    es, rs = authority_sessions
    kwargs = _historical_capture_source(es)
    document = json.loads(kwargs["raw_response"])
    if change == "empty":
        document["data"]["candles"] = []
    elif change == "gap":
        document["data"]["candles"].pop(1)
    elif change == "outside":
        kwargs["requested_start"] = kwargs["requested_end"]
    elif change == "foreign":
        kwargs["owner_id"] = "foreign"
    elif change == "future":
        kwargs["captured_at"] = kwargs["requested_start"]
    elif change == "fractional_bar":
        for row in document["data"]["candles"]:
            row[0] = (dt.datetime.fromisoformat(row[0]) + dt.timedelta(microseconds=1)).isoformat()
    elif change == "fractional_request":
        kwargs["requested_start"] += dt.timedelta(microseconds=1)
    kwargs["raw_response"] = json.dumps(document).encode()
    with pytest.raises(HistoricalCaptureRefused) as refused:
        publish_historical_kite_capture(es, rs, **kwargs)
    assert refused.value.code == code
    assert rs.query(ResearchDatasetManifestV2).count() == 0
    from app.db.models import AuthorityRawSegment
    assert es.query(AuthorityRawSegment).count() == 0


@pytest.mark.parametrize("change", ["reauthenticated", "revoked"])
def test_historical_capture_replays_retained_data_after_connection_changes(authority_sessions, change):
    from app.db.models import BrokerConnection
    from research.data.historical_capture import publish_historical_kite_capture
    es, rs = authority_sessions
    kwargs = _historical_capture_source(es)
    result = publish_historical_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    connection = es.get(BrokerConnection, kwargs["connection_id"])
    if change == "revoked":
        connection.status = "revoked"
    else:
        connection.last_authenticated_at = (kwargs["as_of"] + dt.timedelta(hours=1)).replace(tzinfo=None)
    connection.updated_at = (kwargs["as_of"] + dt.timedelta(hours=1)).replace(tzinfo=None)
    es.commit()
    data = load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=kwargs["as_of"])],
        now=kwargs["as_of"] + dt.timedelta(days=1))[0][1]
    assert data.bar_count == 3


@pytest.mark.parametrize("change", ["revoked", "late_authentication"])
def test_historical_capture_checks_connection_again_before_writes(authority_sessions, monkeypatch, change):
    from app.db.models import BrokerConnection, AuthorityRawSegment
    from research.data import historical_capture as history
    from research.domain.models import ResearchDatasetManifestV2
    es, rs = authority_sessions
    kwargs = _historical_capture_source(es)
    original = history._normalization
    def changed(*args):
        connection = es.get(BrokerConnection, kwargs["connection_id"])
        if change == "revoked":
            connection.status = "revoked"
        else:
            connection.last_authenticated_at = (kwargs["captured_at"] + dt.timedelta(seconds=1)).replace(tzinfo=None)
        es.flush()
        return original(*args)
    monkeypatch.setattr(history, "_normalization", changed)
    with pytest.raises(history.HistoricalCaptureRefused):
        history.publish_historical_kite_capture(es, rs, **kwargs)
    assert es.query(AuthorityRawSegment).count() == 0
    assert rs.query(ResearchDatasetManifestV2).count() == 0


def _historical_daily_source(es):
    from app.market_data.authority import load_capability_profile, load_provider_conformance
    from app.market_truth.authority import load_market_truth_snapshot
    kwargs = _historical_capture_source(es)
    alignment = a.load_alignment_policy(es, kwargs["alignment_policy_address"])
    truth = dataclasses.replace(load_market_truth_snapshot(es, alignment.truth_snapshot_address),
        effective_to=T0 + dt.timedelta(days=10))
    persist_market_truth_snapshot(es, truth)
    alignment = dataclasses.replace(alignment, resolution_seconds=86400, truth_snapshot_address=truth.address)
    a.persist_alignment_policy(es, alignment)
    kwargs["alignment_policy_address"] = alignment.address
    for kind in ("adjustment", "roll"):
        policy = getattr(a, f"load_{kind}_policy")(es, kwargs[f"{kind}_policy_address"])
        policy = dataclasses.replace(policy, truth_snapshot_addresses=(truth.address,))
        getattr(a, f"persist_{kind}_policy")(es, policy)
        kwargs[f"{kind}_policy_address"] = policy.address
    profile = load_capability_profile(es, kwargs["capability_profile_address"], at_time=kwargs["as_of"])
    conformance = load_provider_conformance(es, profile.conformance_evidence_address)
    coverage = tuple(dict(item, resolution_seconds=86400,
        history={"from": T0, "to": T0 + dt.timedelta(days=10), "bars": 21}) for item in conformance.coverage)
    conformance = dataclasses.replace(conformance, tested_resolutions=(86400,), coverage=coverage)
    persist_provider_conformance(es, conformance)
    offers = tuple(dict(item, timeframes=[86400], available_from=T0,
        available_to=T0 + dt.timedelta(days=10)) for item in profile.offers)
    profile = dataclasses.replace(profile, expires_at=T0 + dt.timedelta(days=10),
        conformance_evidence_address=conformance.address, offers=offers)
    persist_capability_profile(es, profile)
    kwargs["capability_profile_address"] = profile.capability_profile_address
    rows = [[(T0 + dt.timedelta(days=index)).isoformat(), 100, 102, 99, 101, 1234] for index in (1, 2, 4)]
    kwargs.update(raw_response=json.dumps({"status": "success", "data": {"candles": rows}}).encode(),
        requested_start=T0, requested_end=T0 + dt.timedelta(days=5),
        captured_at=T0 + dt.timedelta(days=6), recorded_at=T0 + dt.timedelta(days=6, seconds=1),
        as_of=T0 + dt.timedelta(days=6, seconds=2))
    return kwargs


def test_historical_daily_capture_preserves_date_gaps_without_claiming_a_calendar(authority_sessions):
    from research.data.historical_capture import publish_historical_kite_capture
    es, rs = authority_sessions
    kwargs = _historical_daily_source(es)
    result = publish_historical_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    data = load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
        selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=kwargs["as_of"])],
        now=kwargs["as_of"])[0][1]
    assert [candle.ts for candle in data.candles] == [T0 + dt.timedelta(days=index) for index in (1, 2, 4)]
    assert data.interval == "day"
    assert data.binding["historical_capture"]["calendar_coverage"] == "NOT_ASSERTED"


def test_historical_daily_capture_refuses_shifted_labels_before_writes(authority_sessions):
    from app.db.models import AuthorityRawSegment
    from research.domain.models import ResearchDatasetManifestV2
    from research.data.historical_capture import HistoricalCaptureRefused, publish_historical_kite_capture
    es, rs = authority_sessions
    kwargs = _historical_daily_source(es)
    document = json.loads(kwargs["raw_response"])
    for row in document["data"]["candles"]:
        row[0] = (dt.datetime.fromisoformat(row[0]) + dt.timedelta(hours=1)).isoformat()
    kwargs["raw_response"] = json.dumps(document).encode()
    with pytest.raises(HistoricalCaptureRefused) as refused:
        publish_historical_kite_capture(es, rs, **kwargs)
    assert refused.value.code == "HISTORICAL_CAPTURE_DAILY_LABEL"
    assert es.query(AuthorityRawSegment).count() == 0
    assert rs.query(ResearchDatasetManifestV2).count() == 0


@pytest.mark.parametrize("change", ["wrong_row_shape", "numeric_boolean", "invalid_json", "raw_type", "exceeds_entitled_bars"])
def test_historical_capture_rejects_malformed_or_unentitled_data(authority_sessions, change):
    from app.db.models import AuthorityRawSegment
    from research.data.historical_capture import HistoricalCaptureRefused, publish_historical_kite_capture
    es, rs = authority_sessions
    kwargs = _historical_capture_source(es, count=22 if change == "exceeds_entitled_bars" else 3)
    document = json.loads(kwargs["raw_response"])
    if change == "wrong_row_shape":
        document["data"]["candles"][0].append(123)
    elif change == "numeric_boolean":
        document["data"]["candles"][0][1] = True
    kwargs["raw_response"] = json.dumps(document).encode()
    if change == "invalid_json":
        kwargs["raw_response"] = b"invalid json"
    elif change == "raw_type":
        kwargs["raw_response"] = None
    with pytest.raises(HistoricalCaptureRefused):
        publish_historical_kite_capture(es, rs, **kwargs)
    assert es.query(AuthorityRawSegment).count() == 0


def test_historical_capture_rechecks_normalized_prices_against_retained_bytes(authority_sessions, monkeypatch):
    from research.data import provider_capture as capture
    from research.data.historical_capture import publish_historical_kite_capture
    es, rs = authority_sessions
    kwargs = _historical_capture_source(es)
    original = capture._normalized
    def altered(*args):
        observations = list(original(*args))
        observations[3] = dataclasses.replace(observations[3], numeric=valid(101.5))
        return tuple(observations)
    monkeypatch.setattr(capture, "_normalized", altered)
    result = publish_historical_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    with pytest.raises(CanonicalDatasetRefused):
        load_canonical_datasets(rs, execution_session=es, owner_id=kwargs["owner_id"],
            selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=kwargs["as_of"])],
            now=kwargs["as_of"])


def test_csv_shared_dependency_queries_are_bounded_and_fresh_after_reopen(authority_sessions):
    from collections import Counter
    from research.data.user_csv_import import prepare_user_csv, publish_user_csv
    from research.domain.strategy_admissions import load_verified_dataset_authority

    es, rs = authority_sessions
    raw = ("Symbol,Date,Open,High,Low,Close\n" + "\n".join(
        f"SELF,2026-01-{day:02d},100,102,99,101" for day in range(1, 13)) + "\n").encode()
    spec = UserCsvSpec("Synthetic latency check", "user-csv:XNSE:INDEX:SELF", "1",
        "SELF", "SELF", "XNSE", "INDEX",
        CsvColumnMapping("Symbol", "Date", "Open", "High", "Low", "Close"), date_format="%Y-%m-%d")
    observed = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
    queries = Counter()
    def count_shared(_conn, _cursor, statement, _parameters, _context, _many):
        for table in ("authority_provider_products", "authority_provider_contracts",
                      "authority_provider_entities", "authority_provider_aliases",
                      "authority_canonical_instruments", "authority_raw_segments"):
            if statement.startswith("SELECT") and f"FROM {table}" in statement:
                queries[table] += 1
    sqlalchemy_event.listen(es.bind, "before_cursor_execute", count_shared)
    try:
        imported = prepare_user_csv(es, owner_id="synthetic-owner", project_id="latency-project",
            raw=raw, spec=spec, observed_at=observed)
        es.commit()
        publish_user_csv(rs, es, imported)
        rs.commit()
    finally:
        sqlalchemy_event.remove(es.bind, "before_cursor_execute", count_shared)
    assert queries and max(queries.values()) <= 20, queries
    with Session(es.bind) as reopened_execution, Session(rs.bind) as reopened_research:
        loaded = load_verified_dataset_authority(reopened_research,
            owner_id="synthetic-owner", manifest_address=imported.manifest.manifest_address,
            execution_session=reopened_execution, at_time=imported.ready_as_of)
        assert loaded.manifest.canonical_bytes == imported.manifest.canonical_bytes
        assert loaded.object_bytes == tuple(value[1] for value in imported.segments.values())


def _retrospective_daily_source(es, *, count=3, owner='daily-history-owner', project='daily-history-project', interval='day',
                                physical=None, symbol='SELF', company='SYNTHETIC', captured=None,
                                entity_namespace='synthetic-daily-history'):
    from zoneinfo import ZoneInfo
    from app.db.models import Organization, Project, BrokerConnection
    from app.providers.connection_store import DATA_SCOPE_PREFIX
    from app.market_truth.identity import ProviderEntity, ProviderProduct, ProviderContract, persist_provider_identity
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from tests.test_connection_store import _store
    captured = captured or dt.datetime(2026, 9, 1, 12, 0, 0, 123456, tzinfo=dt.timezone.utc)
    granted = captured - dt.timedelta(hours=12)
    if es.get(Organization, owner) is None:
        es.add(Organization(organization_id=owner, name='Synthetic daily history')); es.flush()
    if es.get(Project, project) is None:
        es.add(Project(project_id=project, owner_id=owner, name='Daily history', description='', status='active')); es.flush()
    assert es.get(Project, project).owner_id == owner
    store = _store(es, owner)
    connection = es.query(BrokerConnection).filter(BrokerConnection.owner_id == owner,
        BrokerConnection.broker_account_id == store.broker_account_id,
        BrokerConnection.scope.like(DATA_SCOPE_PREFIX + '%'), BrokerConnection.status == 'active').one_or_none()
    if connection is None:
        connection = store.create_data_connection()
        connection.created_at = connection.updated_at = connection.last_authenticated_at = granted.replace(tzinfo=None)
    physical = physical or CanonicalPhysicalInstrument('synthetic-daily-history', '1', 'XNSE', 'EQUITY', 'SPOT', 'INR', None)
    entity = ProviderEntity(entity_namespace, 'kite', 'Synthetic provider authority')
    product = ProviderProduct(entity.address, 'kite-connect-v3', 'kite-connect', '3')
    contract = ProviderContract(owner, product.address, 'RESEARCH', ('HISTORICAL',), granted, None, address('synthetic-admitted-history-grant'))
    persist_canonical_instrument(es, physical); persist_provider_identity(es, entity, product, contract)
    start = captured.astimezone(ZoneInfo('Asia/Kolkata')).replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=count + 2)
    rows = [[(start + dt.timedelta(days=index + (index >= 2))).isoformat(),
             100 + index, 102 + index, 99 + index, 101 + index,
             0 if physical.asset_class == 'INDEX' else 1000 + index] for index in range(count)]
    raw = json.dumps({'status': 'success', 'data': {'candles': rows}}, separators=(',', ':')).encode()
    token = 256265 if physical.asset_class == 'INDEX' else 408065
    segment = 'INDICES' if physical.asset_class == 'INDEX' else 'NSE'
    csv = ('instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n'
           f'{token},1594,{symbol},{company},0,,0,0.05,1,EQ,{segment},NSE\n').encode()
    source = prepare_historical_attribution(owner_id=owner, connection_id=connection.id,
        entity=entity, product=product, contract=contract, instrument=physical,
        token=token, symbol=symbol, exchange='NSE', interval=interval,
        requested_start=(start-dt.timedelta(days=1)).astimezone(dt.timezone.utc),
        requested_end=captured.replace(hour=0, minute=0, second=0, microsecond=0),
        current_reference_bytes=csv, reference_received_at=captured-dt.timedelta(seconds=1),
        reference_recorded_at=captured-dt.timedelta(microseconds=1),
        historical_response_bytes=raw, captured_at=captured,
        recorded_at=captured+dt.timedelta(microseconds=1), as_of=captured+dt.timedelta(microseconds=2))
    return source, project


def test_retrospective_daily_authority_publishes_and_reopens_without_event_time_grant(authority_sessions):
    from research.data.provider_history_authority import prepare_historical_authority
    from research.data.historical_capture import publish_historical_kite_capture
    from app.api.research_dataset_routes import _item
    from research.domain.models import ResearchDatasetManifestV2
    es, rs = authority_sessions
    source, project = _retrospective_daily_source(es)
    kwargs = prepare_historical_authority(es, source)
    result = publish_historical_kite_capture(es, rs, project_id=project, **kwargs)
    es.commit(); rs.commit()
    item = _item(rs, es, rs.get(ResearchDatasetManifestV2, (source.context.owner_id, result.manifest.manifest_address)))
    cutoff = dt.datetime.fromisoformat(item.as_of)
    with Session(es.get_bind()) as reopened_es, Session(rs.get_bind()) as reopened_rs:
        _, data = load_canonical_datasets(reopened_rs, execution_session=reopened_es,
            owner_id=source.context.owner_id,
            selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=cutoff)], now=cutoff)[0]
        assert data.bar_count == 3
        assert [candle.close for candle in data.candles] == [101, 102, 103]
        assert [candle.volume for candle in data.candles] == [1000, 1001, 1002]
        assert data.binding['historical_capture']['calendar_coverage'] == 'NOT_ASSERTED'
        assert data.binding['historical_capture']['historical_source_availability'] == 'NOT_SUPPLIED'
        assert data.binding['time_interpretation']['retrospective_evaluation'] is True
        projection = project_verified_research_inputs(data, owner_id=source.context.owner_id,
            graph_input_fields={'frame': FIELDS})
        assert len(projection.availability_index) == 3
        assert projection.availability_index[-1] < pd.Timestamp(kwargs['captured_at'])
    assert item.bar_count == 3


def test_retrospective_daily_authority_rejects_intraday_even_at_midnight(authority_sessions):
    from sqlalchemy import select, func
    from app.db.models import AuthorityCapabilityProfile, AuthorityRawSegment
    from research.data.provider_history_authority import prepare_historical_authority
    from research.data.historical_capture import HistoricalCaptureRefused
    es, _ = authority_sessions
    source, _ = _retrospective_daily_source(es, count=1, interval='15minute')
    with pytest.raises(HistoricalCaptureRefused) as refused:
        prepare_historical_authority(es, source)
    assert refused.value.code == 'HISTORICAL_CAPTURE_DAILY_POLICY_REQUIRED'
    assert es.scalar(select(func.count()).select_from(AuthorityCapabilityProfile)) == 0
    assert es.scalar(select(func.count()).select_from(AuthorityRawSegment)) == 0


def test_retrospective_daily_authority_exact_retry_reuses_all_facts(authority_sessions):
    from sqlalchemy import select, func
    from app.db.models import AuthorityRawSegment, AuthorityProviderObservation, AuthorityNormalizedObservation
    from research.domain.models import ResearchDatasetManifestV2
    from research.data.provider_history_authority import prepare_historical_authority
    from research.data.historical_capture import publish_historical_kite_capture
    es, rs = authority_sessions
    source, project = _retrospective_daily_source(es)
    first = publish_historical_kite_capture(es, rs, project_id=project, **prepare_historical_authority(es, source))
    es.commit(); rs.commit()
    models = (AuthorityRawSegment, AuthorityProviderObservation, AuthorityNormalizedObservation)
    before = [es.scalar(select(func.count()).select_from(model)) for model in models]
    later = publish_historical_kite_capture(es, rs, project_id=project, **prepare_historical_authority(es, source))
    es.commit(); rs.commit()
    assert later.manifest == first.manifest
    assert [es.scalar(select(func.count()).select_from(model)) for model in models] == before
    assert rs.scalar(select(func.count()).select_from(ResearchDatasetManifestV2)) == 1
    schema = a.load_raw_schema(es, first.manifest.raw_schema_addresses[0])
    assert schema.schema_version == 'kite-historical-candle/3'
    assert schema.evidence_address == source.historical_response.address
    assert source.historical_response.raw_schema == 'kite-historical-http-response/3'
    assert es.scalar(select(func.count()).select_from(AuthorityRawSegment).where(
        AuthorityRawSegment.raw_bytes == source.historical_response.payload)) == 1


def test_retrospective_daily_authority_cannot_be_reused_as_current_capture(authority_sessions):
    from research.data.provider_history_authority import prepare_historical_authority
    from research.data.provider_capture import publish_current_kite_capture, CurrentCaptureRefused
    es, rs = authority_sessions
    source, project = _retrospective_daily_source(es)
    kwargs = prepare_historical_authority(es, source)
    kwargs.pop('requested_start'); kwargs.pop('requested_end')
    with pytest.raises(CurrentCaptureRefused) as refused:
        publish_current_kite_capture(es, rs, project_id=project, maximum_age_seconds=60, **kwargs)
    assert refused.value.code == 'CURRENT_CAPTURE_HISTORICAL_CONTEXT'


def _retrospective_bundle_fetch(es, *, empty_middle=False, symbol='INFY', count=5,
                                owner='daily-history-owner', project='daily-history-project',
                                entity_namespace='synthetic-daily-history'):
    from app.db.concurrency import begin_reservation
    from app.db.models import BrokerConnection
    from app.core.provider_selections import persist_provider_selection
    from app.providers.provider_instrument_reference import reference_from_row
    from app.market_truth.identity import load_provider_identity
    from app.market_truth.cash_reference import source_reference_for_symbol
    from app.market_data.kite_historical_attribution import prepare_historical_attribution, _reference_rows
    begin_reservation(es, scope="synthetic-history-bundle")
    instrument, definition_evidence = source_reference_for_symbol(symbol, 'NSE')
    source, project = _retrospective_daily_source(es, count=min(count, 5), owner=owner, project=project,
        physical=instrument, symbol=symbol, company='NIFTY 50' if instrument.asset_class == 'INDEX' else 'INFOSYS',
        entity_namespace=entity_namespace,
        captured=dt.datetime(2026, 9, 7, 12, 0, 0, 123456, tzinfo=dt.timezone.utc))
    document = json.loads(source.receipt.payload)
    reference_row = _reference_rows(source.current_reference.payload)[0]
    reference_row["instrument_token"] = int(reference_row["instrument_token"])
    connection = es.get(BrokerConnection, document["connection_id"])
    selected = persist_provider_selection(es, owner_id=source.context.owner_id,
        data_account_id=connection.broker_account_id, connection_id=connection.id,
        provider="ZERODHA", reference=reference_from_row(reference_row),
        observed_at=connection.created_at.replace(tzinfo=dt.timezone.utc))
    assert 2 <= count <= 4000
    split = count // 2
    from zoneinfo import ZoneInfo
    captured = dt.datetime.fromisoformat(document['historical_response']['received_at'])
    midnight = captured.astimezone(ZoneInfo('Asia/Kolkata')).replace(hour=0, minute=0, second=0, microsecond=0)
    first = midnight - dt.timedelta(days=count + 2)
    original_rows = [[(first + dt.timedelta(days=index + (index >= split))).isoformat(),
        100 + index, 102 + index, 99 + index, 101 + index,
        0 if instrument.asset_class == 'INDEX' else 1000 + index] for index in range(count)]
    entity, product, contract = load_provider_identity(es, source.context.provider_contract_address)
    start = (first-dt.timedelta(days=1)).astimezone(dt.timezone.utc)
    end = (midnight-dt.timedelta(seconds=1)).astimezone(dt.timezone.utc)
    third = dt.datetime.fromisoformat(original_rows[split][0]).astimezone(dt.timezone.utc)
    boundary = third - dt.timedelta(days=1) if empty_middle else third
    windows = [(start, boundary-dt.timedelta(seconds=1), original_rows[:split])]
    if empty_middle:
        windows.append((boundary, third-dt.timedelta(seconds=1), []))
    windows.append((third, end, original_rows[split:]))
    as_of = captured + dt.timedelta(seconds=len(windows), microseconds=2)
    sources, captures = [], []
    for index, (left, right, rows) in enumerate(windows):
        received = captured + dt.timedelta(seconds=index)
        recorded = received + dt.timedelta(microseconds=1)
        raw = json.dumps({'status':'success', 'data':{'candles':rows}}, separators=(',', ':')).encode()
        captures.append(SimpleNamespace(payload=raw, received_at=received, recorded_at=recorded,
            requested_start=left, requested_end=right, interval='day', row_count=len(rows)))
        if rows:
            sources.append(prepare_historical_attribution(owner_id=source.context.owner_id,
                connection_id=document['connection_id'], entity=entity, product=product, contract=contract,
                instrument=source.context.canonical_instrument, token=reference_row['instrument_token'], symbol=symbol, exchange='NSE',
                interval='day', requested_start=left, requested_end=right,
                current_reference_bytes=source.current_reference.payload,
                reference_received_at=dt.datetime.fromisoformat(document['current_reference']['received_at']),
                reference_recorded_at=source.current_reference.recorded_at,
                historical_response_bytes=raw, captured_at=received, recorded_at=recorded, as_of=as_of))
    return SimpleNamespace(owner_id=source.context.owner_id, project_id=project,
        selection_address=selected['selection_address'], data_account_id=connection.broker_account_id,
        connection_id=document['connection_id'], instrument=source.context.canonical_instrument,
        definition_evidence=canonical_json(definition_evidence).encode(),
        requested_start=start, requested_end=end, sources=tuple(sources), captures=tuple(captures))


@pytest.mark.parametrize('empty_middle', [False, True])
def test_historical_bundle_publishes_one_input_and_replays_original_response_clocks(authority_sessions, empty_middle):
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.domain.models import ResearchDatasetManifestV2
    from app.market_data.observations import load_provider_observation, load_raw_segment
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es, empty_middle=empty_middle)
    result = publish_historical_bundle(es, rs, fetch)
    es.commit(); rs.commit()
    assert rs.query(ResearchDatasetManifestV2).count() == 1
    from app.api.research_dataset_routes import _replay_cutoff
    cutoff = dt.datetime.fromisoformat(_replay_cutoff(result.manifest))
    with Session(es.get_bind()) as reopened_es, Session(rs.get_bind()) as reopened_rs:
        _, data = load_canonical_datasets(reopened_rs, execution_session=reopened_es,
            owner_id=fetch.owner_id, selections=[SimpleNamespace(
                manifest_address=result.manifest.manifest_address, as_of=cutoff)], now=cutoff)[0]
        assert [candle.close for candle in data.candles] == [101, 102, 103, 104, 105]
        assert [candle.volume for candle in data.candles] == [1000, 1001, 1002, 1003, 1004]
        binding = data.binding['historical_capture']
        assert binding['request_count'] == len(fetch.captures)
        assert binding['empty_request_count'] == int(empty_middle)
        assert binding['requested_start'] == fetch.requested_start.isoformat()
        assert binding['requested_end'] == fetch.requested_end.isoformat()
        assert [load_raw_segment(reopened_es, key).payload for key in binding['raw_capture_addresses']] == [
            item.payload for item in fetch.captures]
        observed = {load_provider_observation(reopened_es, key).available_at
            for key in result.manifest.provider_observation_addresses}
        assert observed == {item.received_at for item in fetch.captures if item.row_count}
        projection = project_verified_research_inputs(data, owner_id=fetch.owner_id,
            graph_input_fields={'frame':FIELDS})
        assert len(projection.availability_index) == 5
        assert projection.availability_index[-1] < min(observed)


def test_historical_bundle_refuses_missing_request_window_without_partial_facts(authority_sessions):
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.historical_capture import HistoricalCaptureRefused
    from app.db.models import AuthorityRawSegment, AuthorityProviderAlias
    from research.domain.models import ResearchDatasetManifestV2
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es, empty_middle=True)
    fetch.captures = (fetch.captures[0], fetch.captures[-1])
    with pytest.raises(HistoricalCaptureRefused) as refused:
        publish_historical_bundle(es, rs, fetch)
    assert refused.value.code == 'HISTORICAL_BUNDLE_REQUEST_GAP'
    assert es.query(AuthorityRawSegment).count() == es.query(AuthorityProviderAlias).count() == 0
    assert rs.query(ResearchDatasetManifestV2).count() == 0


def test_historical_bundle_recovers_after_research_commit_failure(authority_sessions):
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.domain.models import ResearchDatasetManifestV2
    from app.db.models import AuthorityRawSegment, AuthorityProviderObservation, AuthorityNormalizedObservation
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es)
    first = publish_historical_bundle(es, rs, fetch)
    es.commit()
    rs.rollback()  # A separate research-plane commit failed; retained source facts remain durable.
    assert rs.query(ResearchDatasetManifestV2).count() == 0
    models = (AuthorityRawSegment, AuthorityProviderObservation, AuthorityNormalizedObservation)
    counts = [es.query(model).count() for model in models]
    again = publish_historical_bundle(es, rs, fetch)
    es.commit(); rs.commit()
    assert again.manifest == first.manifest
    assert [es.query(model).count() for model in models] == counts
    assert rs.query(ResearchDatasetManifestV2).count() == 1


def _reopen_historical_bundle(es, rs, fetch, result):
    from app.api.research_dataset_routes import _replay_cutoff
    cutoff = dt.datetime.fromisoformat(_replay_cutoff(result.manifest))
    with Session(es.get_bind()) as reopened_es, Session(rs.get_bind()) as reopened_rs:
        return load_canonical_datasets(reopened_rs, execution_session=reopened_es, owner_id=fetch.owner_id,
            selections=[SimpleNamespace(manifest_address=result.manifest.manifest_address, as_of=cutoff)],
            now=cutoff)[0][1]


def test_postgresql_historical_bundle_restores_exact_publication_after_research_rollback(pg_sandbox):
    from app.db.models import AuthorityRawSegment
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.provider_history_publication import retain_history_publication, find_history_publication
    from research.domain.models import ResearchDatasetManifestV2
    ee, re = pg_sandbox.execution_engine, pg_sandbox.research_engine
    Base.metadata.create_all(ee)
    init_research_db(re)
    with Session(ee) as es, Session(re) as rs:
        fetch = _retrospective_bundle_fetch(es, empty_middle=True)
        result = publish_historical_bundle(es, rs, fetch)
        retain_history_publication(es, result, project_id=fetch.project_id,
            selection_address=fetch.selection_address, start=fetch.requested_start, end=fetch.requested_end)
        es.commit()
        rs.rollback()
        raw_count = es.query(AuthorityRawSegment).count()
        assert rs.query(ResearchDatasetManifestV2).count() == 0
    with Session(ee) as es, Session(re) as rs:
        prior = find_history_publication(es, owner_id=fetch.owner_id,
            selection_address=fetch.selection_address, start=fetch.requested_start, end=fetch.requested_end)
        assert prior[0].canonical_bytes == result.manifest.canonical_bytes
        restored = persist_verified_dataset_authority(rs, manifest=prior[0], segments=prior[1],
            execution_session=es, at_time=dt.datetime.fromisoformat(prior[0].recorded_at))
        es.commit()
        rs.commit()
        data = _reopen_historical_bundle(es, rs, fetch, restored)
        assert data.bar_count == 5 and data.binding['historical_capture']['empty_request_count'] == 1
        assert es.query(AuthorityRawSegment).count() == raw_count
        assert rs.query(ResearchDatasetManifestV2).count() == 1
        assert find_history_publication(es, owner_id='other-owner', selection_address=fetch.selection_address,
            start=fetch.requested_start, end=fetch.requested_end) is None


def _assert_no_bundle_publication(es, rs):
    from app.db.models import (AuthorityRawSegment, AuthorityProviderAlias, AuthorityProviderObservation,
        AuthorityNormalizedObservation, AuthorityMarketTruthSnapshot, AuthorityCapabilityProfile,
        AuthorityDatasetCreationEvidence)
    from research.domain.models import ResearchDatasetManifestV2
    for model in (AuthorityRawSegment, AuthorityProviderAlias, AuthorityProviderObservation,
                  AuthorityNormalizedObservation, AuthorityMarketTruthSnapshot, AuthorityCapabilityProfile,
                  AuthorityDatasetCreationEvidence):
        assert es.query(model).count() == 0, model.__name__
    assert rs.query(ResearchDatasetManifestV2).count() == 0


def test_historical_bundle_nifty_benchmark_reopens_beside_distinct_equity(authority_sessions):
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.canonical_dataset import project_verified_research_input_set
    from research.evaluation.phase5_runtime import _validate_verified_dataset
    es, rs = authority_sessions
    equity = _retrospective_bundle_fetch(es)
    benchmark = _retrospective_bundle_fetch(es, symbol='NIFTY 50')
    assert equity.connection_id == benchmark.connection_id
    assert equity.instrument.address != benchmark.instrument.address
    assert equity.sources[0].mapping.provider_token == '408065'
    assert benchmark.sources[0].mapping.provider_token == '256265'
    first = publish_historical_bundle(es, rs, equity)
    second = publish_historical_bundle(es, rs, benchmark)
    es.commit(); rs.commit()
    primary_data = _reopen_historical_bundle(es, rs, equity, first)
    benchmark_data = _reopen_historical_bundle(es, rs, benchmark, second)
    assert second.manifest.instrument_addresses == (benchmark.instrument.address,)
    assert benchmark_data.instrument_key == instrument_key(benchmark.instrument.address)
    assert [item.volume for item in benchmark_data.candles] == [0] * 5
    projected = project_verified_research_input_set({'frame': primary_data, 'benchmark': benchmark_data},
        owner_id=equity.owner_id, primary_input='frame',
        graph_input_fields={'frame': ('CLOSE',), 'benchmark': ('CLOSE',)})
    assert projected.inputs['benchmark']['close'].tolist() == [101, 102, 103, 104, 105]
    assert projected.inputs['benchmark']['close'].index.equals(projected.availability_index)
    bindings = projected.input_bindings.document['inputs']
    assert bindings['frame']['binding']['canonical_instrument_address'] == equity.instrument.address
    assert bindings['benchmark']['binding']['canonical_instrument_address'] == benchmark.instrument.address
    assert bindings['benchmark']['binding']['instrument']['role'] == 'benchmark'
    _validate_verified_dataset(projected)


@pytest.mark.parametrize('symbol', ['INFY', 'NIFTY 50'])
def test_historical_bundle_retained_definition_replays_after_catalogue_and_metadata_change(authority_sessions, monkeypatch, symbol):
    from app.market_truth import cash_reference
    from app.providers.connection_store import OwnedConnectionStore
    from app.db.models import BrokerConnection
    from app.market_data.observations import load_raw_segment
    from research.data.provider_history_bundle import publish_historical_bundle
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es, symbol=symbol)
    result = publish_historical_bundle(es, rs, fetch)
    transform = a.load_normalization_transform(es, result.manifest.normalization_transform_addresses[0])
    definition_address = dict(transform.parameters)['definition']
    original_definition = load_raw_segment(es, definition_address).payload
    es.get(BrokerConnection, fetch.connection_id).status = 'revoked'
    es.commit(); rs.commit()
    def forbidden(*_args, **_kwargs):
        raise AssertionError('saved replay must not fetch a current catalogue or definition')
    current_index = cash_reference.nifty_50_price_return_reference
    def changed_index_metadata():
        instrument, evidence = current_index()
        document = json.loads(canonical_json(evidence['document']))
        document['retrieved_on'] = '2099-01-01'
        document['sources'] = []
        return instrument, {'address': content_address(document), 'document': document}
    monkeypatch.setattr(cash_reference, 'nifty_50_price_return_reference', changed_index_metadata)
    monkeypatch.setattr(cash_reference, 'source_reference_for_symbol', forbidden)
    monkeypatch.setattr(cash_reference, '_REFERENCES', {})
    monkeypatch.setattr(OwnedConnectionStore, 'zerodha_data_runtime', forbidden)
    data = _reopen_historical_bundle(es, rs, fetch, result)
    assert data.bar_count == 5 and [item.close for item in data.candles] == [101, 102, 103, 104, 105]
    with Session(es.get_bind()) as reopened:
        assert load_raw_segment(reopened, definition_address).payload == original_definition == fetch.definition_evidence


@pytest.mark.parametrize('symbol', ['INFY', 'NIFTY 50'])
@pytest.mark.parametrize('change', ['semantic', 'hash', 'owner', 'selection'])
def test_historical_bundle_retained_definition_rejects_changed_meaning_hash_owner_or_selection(authority_sessions, symbol, change):
    from app.market_truth.identity import MarketTruthError, load_provider_identity, persist_provider_identity
    from research.data.provider_history_bundle import DEFINITION_SCHEMA, _retained_definition
    from research.data.historical_capture import HistoricalCaptureRefused
    es, _ = authority_sessions
    fetch = _retrospective_bundle_fetch(es, symbol=symbol)
    source = fetch.sources[0]
    document = json.loads(fetch.definition_evidence)
    reference = {'symbol': symbol, 'exchange': 'NSE'}
    context = source.context
    owner, contract_address = context.owner_id, context.provider_contract_address
    if change == 'semantic':
        interpretation = document['document']['interpretation']
        interpretation['isin' if symbol == 'INFY' else 'return_type'] = 'WRONG_SEMANTICS'
        document['address'] = content_address(document['document'])  # Valid hash cannot legitimize a different identity.
    elif change == 'hash':
        document['address'] = address('wrong-definition-hash')
    elif change == 'owner':
        entity, product, contract = load_provider_identity(es, contract_address)
        foreign = dataclasses.replace(contract, owner_id='foreign-definition-owner')
        persist_provider_identity(es, entity, product, foreign)
        owner, contract_address = foreign.owner_id, foreign.address
    else:
        reference['symbol'] = 'OTHER'
    recorded = dt.datetime.fromisoformat(json.loads(source.receipt.payload)['as_of'])
    raw = RawObservationSegment(owner, context.provider_product_address, contract_address,
        'application/json', DEFINITION_SCHEMA, canonical_json(document).encode(), recorded)
    persist_raw_segment(es, raw)
    with pytest.raises((MarketTruthError, HistoricalCaptureRefused)):
        _retained_definition(es, raw.address, source, reference, recorded)


@pytest.mark.parametrize('change', ['definition_bytes', 'selection_copy', 'selection_missing'])
def test_historical_bundle_full_reopen_refuses_corrupted_retained_dependencies(authority_sessions, change):
    from research.data.provider_history_bundle import publish_historical_bundle
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es)
    result = publish_historical_bundle(es, rs, fetch)
    transform = a.load_normalization_transform(es, result.manifest.normalization_transform_addresses[0])
    definition_address = dict(transform.parameters)['definition']
    es.commit(); rs.commit()
    # Simulate a corrupted isolated backup, not a supported mutation API.
    with es.get_bind().begin() as connection:
        if change == 'definition_bytes':
            connection.exec_driver_sql('DROP TRIGGER authority_raw_segments_refuse_update')
            connection.execute(text('UPDATE authority_raw_segments SET raw_bytes=:payload WHERE address=:address'),
                {'payload': b'corrupted-definition', 'address': definition_address})
        elif change == 'selection_copy':
            connection.exec_driver_sql('DROP TRIGGER owner_provider_instrument_selections_refuse_update')
            connection.execute(text('UPDATE owner_provider_instrument_selections SET reference_fingerprint=:fingerprint '
                'WHERE owner_id=:owner AND selection_address=:address'),
                {'fingerprint': address('wrong-selection-copy'), 'owner': fetch.owner_id, 'address': fetch.selection_address})
        else:
            connection.exec_driver_sql('DROP TRIGGER owner_provider_instrument_selections_refuse_delete')
            connection.execute(text('DELETE FROM owner_provider_instrument_selections WHERE owner_id=:owner AND selection_address=:address'),
                {'owner': fetch.owner_id, 'address': fetch.selection_address})
    with pytest.raises(CanonicalDatasetRefused):
        _reopen_historical_bundle(es, rs, fetch, result)


def _bundle_response_overlap(es, fetch):
    from app.market_truth.identity import load_provider_identity
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    source = fetch.sources[1]
    receipt = json.loads(source.receipt.payload)
    rows = [json.loads(fetch.captures[0].payload)['data']['candles'][-1],
            *json.loads(source.historical_response.payload)['data']['candles']]
    start = dt.datetime.fromisoformat(rows[0][0]).astimezone(dt.timezone.utc)
    raw = json.dumps({'status': 'success', 'data': {'candles': rows}}, separators=(',', ':')).encode()
    entity, product, contract = load_provider_identity(es, source.context.provider_contract_address)
    changed = prepare_historical_attribution(owner_id=fetch.owner_id, connection_id=fetch.connection_id,
        entity=entity, product=product, contract=contract, instrument=fetch.instrument,
        token=receipt['selection']['token'], symbol=receipt['selection']['symbol'], exchange='NSE', interval='day',
        requested_start=start, requested_end=fetch.requested_end,
        current_reference_bytes=source.current_reference.payload,
        reference_received_at=dt.datetime.fromisoformat(receipt['current_reference']['received_at']),
        reference_recorded_at=source.current_reference.recorded_at, historical_response_bytes=raw,
        captured_at=fetch.captures[1].received_at, recorded_at=fetch.captures[1].recorded_at,
        as_of=dt.datetime.fromisoformat(receipt['as_of']))
    fetch.sources = (fetch.sources[0], changed)
    fetch.captures[1].payload = raw
    fetch.captures[1].requested_start = start
    fetch.captures[1].row_count = len(rows)


@pytest.mark.parametrize('change,code', [('response_overlap', 'HISTORICAL_BUNDLE_OVERLAP'),
    ('request_overlap', 'HISTORICAL_BUNDLE_REQUEST_GAP'), ('foreign_selection', 'HISTORICAL_CAPTURE_UNAVAILABLE'),
    ('definition_mismatch', 'HISTORICAL_BUNDLE_DEFINITION_UNAVAILABLE')])
def test_historical_bundle_invalid_bindings_refuse_before_partial_facts(authority_sessions, change, code):
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.historical_capture import HistoricalCaptureRefused
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es)
    if change == 'response_overlap':
        _bundle_response_overlap(es, fetch)
    elif change == 'request_overlap':
        fetch.captures[1].requested_start = fetch.captures[0].requested_end
    elif change == 'foreign_selection':
        other = _retrospective_bundle_fetch(es, owner='other-bundle-owner', project='other-bundle-project')
        fetch.selection_address = other.selection_address
    else:
        envelope = json.loads(fetch.definition_evidence)
        envelope['document']['interpretation']['symbol'] = 'OTHER'
        envelope['address'] = content_address(envelope['document'])
        fetch.definition_evidence = canonical_json(envelope).encode()
    with pytest.raises(HistoricalCaptureRefused) as refused:
        publish_historical_bundle(es, rs, fetch)
    assert refused.value.code == code
    _assert_no_bundle_publication(es, rs)


def test_historical_bundle_2001_actual_rows_refuse_before_publication(authority_sessions):
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.historical_capture import HistoricalCaptureRefused
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es, count=2001)
    counts = [len(json.loads(item.payload)['data']['candles']) for item in fetch.captures]
    assert counts == [1000, 1001] and sum(counts) == 2001
    assert all(count <= 2000 for count in counts)
    with pytest.raises(HistoricalCaptureRefused) as refused:
        publish_historical_bundle(es, rs, fetch)
    assert refused.value.code == 'HISTORICAL_BUNDLE_ROW_LIMIT'
    _assert_no_bundle_publication(es, rs)


@pytest.mark.skipif(os.environ.get('PT_TEST_HISTORY_CAPACITY') != '1',
    reason='Set PT_TEST_HISTORY_CAPACITY=1 for the explicit once-only 2000-bar capacity check')
def test_historical_bundle_capacity_2000_publication_and_reopen(authority_sessions):
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.provider_history_publication import retain_history_publication, find_history_publication
    es, rs = authority_sessions
    fetch = _retrospective_bundle_fetch(es, count=2000)
    assert [len(json.loads(item.payload)['data']['candles']) for item in fetch.captures] == [1000, 1000]
    result = publish_historical_bundle(es, rs, fetch)
    retain_history_publication(es, result, project_id=fetch.project_id,
        selection_address=fetch.selection_address, start=fetch.requested_start, end=fetch.requested_end)
    es.commit(); rs.commit()
    with Session(es.get_bind()) as reopened:
        manifest, segments = find_history_publication(reopened, owner_id=fetch.owner_id,
            selection_address=fetch.selection_address, start=fetch.requested_start, end=fetch.requested_end)
        assert manifest.canonical_bytes == result.manifest.canonical_bytes
        assert tuple(segments[address][1] for address in manifest.segment_addresses) == result.object_bytes
    data = _reopen_historical_bundle(es, rs, fetch, result)
    assert data.bar_count == 2000
    assert data.candles[0].close == 101 and data.candles[-1].close == 2100
    assert data.candles[-1].volume == 2999
    assert len(result.manifest.provider_observation_addresses) == 10_000
    assert len(result.manifest.normalized_observation_addresses) == 10_000
    assert data.binding['historical_capture']['request_count'] == 2


def _fresh_monitoring_history(es, rs):
    from research.data.historical_capture import publish_historical_kite_capture
    kwargs = _historical_capture_source(es)
    completed = T0 + dt.timedelta(hours=4, minutes=45)
    kwargs.update(captured_at=completed + dt.timedelta(seconds=2, microseconds=123456),
                  recorded_at=completed + dt.timedelta(seconds=3, microseconds=123456),
                  as_of=completed + dt.timedelta(seconds=4, microseconds=123456))
    result = publish_historical_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    return kwargs, dict(owner_id=kwargs['owner_id'], manifest_address=result.manifest.manifest_address,
        instrument_address=kwargs['context'].canonical_instrument.address, timeframe_seconds=900,
        minimum_bars=3, maximum_age_seconds=60, cutoff_at=kwargs['as_of'],
        graph_input_fields={'frame': FIELDS})


def test_monitoring_prefix_keeps_completed_clock_and_original_source_receipts(authority_sessions):
    from app.monitoring.input_producer import load_monitoring_input_prefix
    es, rs = authority_sessions
    kwargs, request = _fresh_monitoring_history(es, rs)
    prefix = load_monitoring_input_prefix(rs, es, **request)
    assert prefix.bar_count == 3
    assert prefix.completed_at == T0 + dt.timedelta(hours=4, minutes=45)
    assert prefix.event_at == prefix.completed_at - dt.timedelta(minutes=15)
    assert prefix.available_at == kwargs['captured_at']
    assert prefix.recorded_at == kwargs['recorded_at']
    assert prefix.cutoff_at == kwargs['as_of']
    assert prefix.projection.availability_index[-1] == pd.Timestamp(prefix.completed_at)
    later = load_monitoring_input_prefix(rs, es, **{**request, 'cutoff_at': request['cutoff_at'] + dt.timedelta(seconds=1)})
    assert later.bar_identity == prefix.bar_identity
    assert later.observation_address == prefix.observation_address
    assert later.manifest_address == prefix.manifest_address


def test_monitoring_prefix_freshness_budget_is_explicit_without_changing_source_evidence(authority_sessions):
    from app.monitoring.input_producer import load_monitoring_input_prefix, _dataset
    es, rs = authority_sessions
    _, request = _fresh_monitoring_history(es, rs)
    data = _dataset(rs, es, request['owner_id'], request['manifest_address'], request['cutoff_at'])
    original = project_verified_research_inputs(data, owner_id=request['owner_id'], graph_input_fields={'frame': FIELDS})
    first = load_monitoring_input_prefix(rs, es, **request).projection
    wider = load_monitoring_input_prefix(rs, es, **{**request, 'maximum_age_seconds': 120}).projection
    assert original.source_provenance_json == first.source_provenance_json == wider.source_provenance_json
    assert original.source_provenance_address == first.source_provenance_address == wider.source_provenance_address
    assert original.input_digest == first.input_digest == wider.input_digest
    assert original.position_map_address == first.position_map_address == wider.position_map_address
    bindings = [value.input_bindings.document for value in (original, first, wider)]
    assert len({value['evaluation_context_address'] for value in bindings}) == 3
    assert len({value['dataset_context_address'] for value in bindings}) == 1
    assert [value['inputs']['frame']['binding']['freshness']['maximum_age_seconds'] for value in bindings] == [3, 60, 120]
    for invalid in (True, 0, -1, 86401, 60.0, '60', 1):
        with pytest.raises(CanonicalDatasetRefused):
            project_verified_research_inputs(data, owner_id=request['owner_id'], graph_input_fields={'frame': FIELDS},
                evaluation_freshness_seconds=invalid)


def test_monitoring_prefix_freshness_budget_cannot_relabel_nonhistorical_or_stale_authority(authority_sessions):
    from app.monitoring.input_producer import _dataset
    es, rs = authority_sessions
    manifest = seed_canonical(es, rs)
    data = load(es, rs, manifest)[0][1]
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_inputs(data, owner_id='synthetic-owner', graph_input_fields={'frame': FIELDS},
            evaluation_freshness_seconds=60)
    _, request = _fresh_monitoring_history(es, rs)
    completed = T0 + dt.timedelta(hours=4, minutes=45)
    at_limit = _dataset(rs, es, request['owner_id'], request['manifest_address'], completed+dt.timedelta(seconds=60))
    project_verified_research_inputs(at_limit, owner_id=request['owner_id'], graph_input_fields={'frame': FIELDS},
        evaluation_freshness_seconds=60)
    stale = _dataset(rs, es, request['owner_id'], request['manifest_address'], completed+dt.timedelta(seconds=60, microseconds=1))
    with pytest.raises(CanonicalDatasetRefused):
        project_verified_research_inputs(stale, owner_id=request['owner_id'], graph_input_fields={'frame': FIELDS},
            evaluation_freshness_seconds=60)


@pytest.mark.parametrize('change,code', [
    ('foreign', 'MONITORING_INPUT_AUTHORITY_INVALID'),
    ('instrument', 'MONITORING_INPUT_SCOPE_MISMATCH'),
    ('timeframe', 'MONITORING_INPUT_SCOPE_MISMATCH'),
    ('warmup', 'MONITORING_INPUT_WARMUP_REQUIRED'),
    ('stale', 'MONITORING_INPUT_STALE'),
    ('future_receipt', 'MONITORING_INPUT_AUTHORITY_INVALID'),
    ('naive', 'MONITORING_INPUT_CLOCK_INVALID'),
    ('bool_warmup', 'MONITORING_INPUT_WARMUP_INVALID'),
    ('bool_age', 'MONITORING_INPUT_FRESHNESS_INVALID'),
    ('unsupported_interval', 'MONITORING_INPUT_TIMEFRAME_INVALID'),
])
def test_monitoring_prefix_refuses_wrong_scope_incomplete_warmup_and_stale_source(authority_sessions, change, code):
    from app.monitoring.input_producer import load_monitoring_input_prefix, MonitoringInputRefused
    es, rs = authority_sessions
    _, request = _fresh_monitoring_history(es, rs)
    changes = {'foreign': {'owner_id': 'another-owner'},
        'instrument': {'instrument_address': address('different-instrument')},
        'timeframe': {'timeframe_seconds': 1800}, 'warmup': {'minimum_bars': 4},
        'stale': {'cutoff_at': T0 + dt.timedelta(hours=4, minutes=46, microseconds=1)},
        'future_receipt': {'cutoff_at': T0 + dt.timedelta(hours=4, minutes=45, seconds=3)},
        'naive': {'cutoff_at': request['cutoff_at'].replace(tzinfo=None)},
        'bool_warmup': {'minimum_bars': True}, 'bool_age': {'maximum_age_seconds': True},
        'unsupported_interval': {'timeframe_seconds': 60}}
    with pytest.raises(MonitoringInputRefused) as error:
        load_monitoring_input_prefix(rs, es, **{**request, **changes[change]})
    assert error.value.code == code


@pytest.mark.parametrize('change,code', [
    ({'minimum_bars': 2001}, 'MONITORING_INPUT_WARMUP_UNSUPPORTED'),
    ({'now': T0 - dt.timedelta(microseconds=1)}, 'MONITORING_INPUT_FUTURE_CUTOFF'),
    ({'now': T0.replace(tzinfo=None)}, 'MONITORING_INPUT_FUTURE_CUTOFF'),
])
def test_monitoring_prefix_rejects_impossible_requests_before_database_access(change, code):
    from app.monitoring.input_producer import load_monitoring_input_prefix, MonitoringInputRefused
    request = dict(owner_id='owner', manifest_address=address('manifest'),
        instrument_address=address('instrument'), timeframe_seconds=900,
        minimum_bars=3, maximum_age_seconds=60, cutoff_at=T0, now=T0,
        graph_input_fields={'frame': FIELDS})
    with pytest.raises(MonitoringInputRefused) as error:
        load_monitoring_input_prefix(None, None, **{**request, **change})
    assert error.value.code == code


def _dated_capture_source(es, seconds=1800, change=None):
    from app.market_data.authority import load_capability_profile, load_provider_conformance
    from app.market_truth.authority import load_market_truth_snapshot
    from app.market_truth.identity import Quality, Reconstruction
    from research.data.dated_session_binding import CALENDAR, SCHEMA, COMPLETION_SCHEMA
    from app.market_truth.dated_sessions import parse_dated_sessions
    kwargs = _historical_capture_source(es)
    context = kwargs['context']
    rows = []
    for offset in range(3):
        day = T0 + dt.timedelta(days=offset)
        opened, closed = day + dt.timedelta(hours=4), day + dt.timedelta(hours=4, minutes=45)
        rows.append(dict(date=day.date().isoformat(), status='CLOSED' if offset == 1 else 'OPEN',
            opens_at=None if offset == 1 else opened.isoformat(), closes_at=None if offset == 1 else closed.isoformat()))
    document = dict(schema=SCHEMA, instrument_address=context.canonical_instrument.address,
        venue_code='XNSE', timezone='UTC', provenance='SYNTHETIC',
        source_reference='Synthetic dated-session fixture; not exchange market data',
        recorded_at=T0.isoformat(), rows=rows)
    if change == 'foreign_calendar':
        document['instrument_address'] = address('foreign-calendar-instrument')
    if change == 'unknown_day':
        document['rows'].pop(1)
    raw = RawObservationSegment(context.owner_id, context.provider_product_address,
        context.provider_contract_address, 'application/json', SCHEMA, canonical_json(document).encode(), T0)
    persist_raw_segment(es, raw)
    evidence = [raw.address]
    if change not in {'foreign_calendar', 'unknown_day', 'missing_completion'}:
        calendar = parse_dated_sessions(raw.payload, instrument_address=context.canonical_instrument.address,
            venue_code='XNSE', timezone='UTC', as_of=T0, allow_synthetic=True)
        completion = dict(schema=COMPLETION_SCHEMA, calendar_address=calendar.address,
            product_address=context.provider_product_address, contract_address=context.provider_contract_address,
            resolution_seconds=seconds, completion_rule='SESSION_OPEN_CLIP_CLOSE_V1', provenance='SYNTHETIC')
        if change == 'wrong_completion_resolution':
            completion['resolution_seconds'] = 60
        if change == 'wrong_completion_product':
            completion['product_address'] = address('foreign-product')
        completion_raw = RawObservationSegment(context.owner_id, context.provider_product_address,
            context.provider_contract_address, 'application/json', COMPLETION_SCHEMA,
            canonical_json(completion).encode(), T0)
        persist_raw_segment(es, completion_raw)
        evidence.append(completion_raw.address)
    alignment = a.load_alignment_policy(es, kwargs['alignment_policy_address'])
    truth = load_market_truth_snapshot(es, alignment.truth_snapshot_address)
    truth = dataclasses.replace(truth, effective_to=T0+dt.timedelta(days=3), source_evidence=tuple(sorted(evidence)),
        quality=Quality.RECONSTRUCTED, reconstruction=Reconstruction('synthetic-sessions', '1', ('Synthetic fixture only',)))
    persist_market_truth_snapshot(es, truth)
    alignment = dataclasses.replace(alignment, calendar=CALENDAR, resolution_seconds=seconds,
        truth_snapshot_address=truth.address)
    a.persist_alignment_policy(es, alignment)
    kwargs['alignment_policy_address'] = alignment.address
    for key, loader, writer in (
        ('adjustment_policy_address', a.load_adjustment_policy, a.persist_adjustment_policy),
        ('roll_policy_address', a.load_roll_policy, a.persist_roll_policy)):
        policy = dataclasses.replace(loader(es, kwargs[key]), truth_snapshot_addresses=(truth.address,))
        writer(es, policy); kwargs[key] = policy.address
    profile = load_capability_profile(es, kwargs['capability_profile_address'], at_time=kwargs['as_of'])
    conformance = load_provider_conformance(es, profile.conformance_evidence_address)
    coverage = tuple({**dict(row), 'resolution_seconds': seconds,
        'history': {**dict(row['history']), 'to': (T0+dt.timedelta(days=3)).isoformat()}}
        for row in conformance.coverage)
    conformance = dataclasses.replace(conformance, tested_resolutions=(seconds,), coverage=coverage)
    persist_provider_conformance(es, conformance)
    profile = dataclasses.replace(profile, conformance_evidence_address=conformance.address,
        expires_at=T0+dt.timedelta(days=3), offers=tuple({**dict(row), 'timeframes': [seconds],
        'available_to': (T0+dt.timedelta(days=3)).isoformat()} for row in profile.offers))
    persist_capability_profile(es, profile); kwargs['capability_profile_address'] = profile.capability_profile_address
    candles = []
    for offset in (0, 2):
        for elapsed in range(0, 2700, seconds):
            event = T0+dt.timedelta(days=offset, hours=4, seconds=elapsed)
            candles.append([event.isoformat(), 100, 102, 99, 101, 1234])
    if change == 'missing_bar':
        candles.pop(1)
    if change == 'closed_day_bar':
        candles.insert(len(candles)//2, [(T0+dt.timedelta(days=1,hours=4)).isoformat(), 100,102,99,101,1234])
    completed = T0+dt.timedelta(days=2,hours=4,minutes=45)
    kwargs.update(raw_response=json.dumps({'status':'success','data':{'candles':candles}}).encode(),
        requested_start=T0+dt.timedelta(hours=4), requested_end=completed-dt.timedelta(seconds=1),
        captured_at=completed+dt.timedelta(seconds=2), recorded_at=completed+dt.timedelta(seconds=3),
        as_of=completed+dt.timedelta(seconds=4))
    return kwargs, candles


@pytest.mark.parametrize('seconds', [900, 1800, 3600])
def test_dated_session_capture_replays_gaps_and_clipped_terminal_into_monitoring(authority_sessions, seconds):
    from research.data.historical_capture import publish_historical_kite_capture
    from app.monitoring.input_producer import load_monitoring_input_prefix
    es, rs = authority_sessions
    kwargs, candles = _dated_capture_source(es, seconds)
    result = publish_historical_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    prefix = load_monitoring_input_prefix(rs, es, owner_id=kwargs['owner_id'],
        manifest_address=result.manifest.manifest_address,
        instrument_address=kwargs['context'].canonical_instrument.address,
        timeframe_seconds=seconds, minimum_bars=len(candles), maximum_age_seconds=60,
        cutoff_at=kwargs['as_of'], graph_input_fields=graph_input_fields or {'frame': FIELDS})
    completed = T0+dt.timedelta(days=2,hours=4,minutes=45)
    assert prefix.completed_at == completed
    assert prefix.bar_count == len(candles)
    assert prefix.available_at == kwargs['captured_at']
    assert prefix.recorded_at == kwargs['recorded_at']
    assert prefix.projection.availability_index[-1] == pd.Timestamp(completed)
    assert prefix.projection.availability_index[len(candles)//2-1] == pd.Timestamp(T0+dt.timedelta(hours=4,minutes=45))
    provenance = json.loads(prefix.projection.source_provenance_json)
    assert provenance['dated_sessions']['provenance'] == 'SYNTHETIC'
    assert provenance['dated_sessions']['completion_rule'] == 'SESSION_OPEN_CLIP_CLOSE_V1'


@pytest.mark.parametrize('change', ['missing_bar', 'closed_day_bar', 'foreign_calendar', 'unknown_day',
    'missing_completion', 'wrong_completion_resolution', 'wrong_completion_product'])
def test_dated_session_capture_refuses_unexplained_gaps_and_foreign_calendar(authority_sessions, change):
    from research.data.historical_capture import publish_historical_kite_capture, HistoricalCaptureRefused
    es, rs = authority_sessions
    kwargs, _ = _dated_capture_source(es, change=change)
    with pytest.raises(HistoricalCaptureRefused):
        publish_historical_kite_capture(es, rs, **kwargs)


@pytest.mark.parametrize('namespace', ['real-provider', 'synthetic-lookalike'])
def test_dated_session_mock_setting_cannot_grant_foreign_provider_synthetic_authority(authority_sessions, namespace):
    from app.market_truth.identity import load_provider_identity, persist_provider_identity
    from app.market_data.dated_session_clock import _fixture_identity
    es, _ = authority_sessions
    kwargs = _historical_capture_source(es)
    context = kwargs['context']
    entity, product, contract = load_provider_identity(es, context.provider_contract_address)
    entity = dataclasses.replace(entity, authority_namespace=namespace, entity_code=namespace)
    product = dataclasses.replace(product, entity_address=entity.address)
    contract = dataclasses.replace(contract, product_address=product.address)
    persist_provider_identity(es, entity, product, contract)
    with pytest.raises(ValueError, match='DATED_SESSION_BINDING_UNAVAILABLE'):
        _fixture_identity(*load_provider_identity(es, contract.address), context.owner_id)


@pytest.mark.parametrize('seconds', [900,1800,3600])
def test_dated_provider_authority_retains_receipt_clock_through_fresh_prefix(authority_sessions, seconds):
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from app.market_truth.identity import load_provider_identity
    from research.data.dated_session_binding import load_dated_session_binding
    from research.data.provider_history_authority import prepare_historical_authority
    from research.data.historical_capture import publish_historical_kite_capture
    from app.monitoring.input_producer import load_monitoring_input_prefix
    es, rs = authority_sessions
    original, rows = _dated_capture_source(es, seconds)
    context = original['context']
    entity, product, contract = load_provider_identity(es, context.provider_contract_address)
    clock_binding = load_dated_session_binding(es, owner_id=context.owner_id,
        alignment=a.load_alignment_policy(es, original['alignment_policy_address']),
        instrument=context.canonical_instrument, product_address=product.address,
        contract_address=contract.address, as_of=original['as_of'])
    reference = ('instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n'
                 '408065,1594,SELF,SYNTHETIC,0,,0,0.05,1,EQ,NSE,NSE\n').encode()
    source = prepare_historical_attribution(owner_id=context.owner_id, connection_id=original['connection_id'],
        entity=entity, product=product, contract=contract, instrument=context.canonical_instrument,
        token=408065, symbol='SELF', exchange='NSE', interval={900:'15minute',1800:'30minute',3600:'60minute'}[seconds],
        requested_start=original['requested_start'], requested_end=original['requested_end'],
        current_reference_bytes=reference, reference_received_at=original['captured_at']-dt.timedelta(seconds=1),
        reference_recorded_at=original['captured_at'], historical_response_bytes=original['raw_response'],
        captured_at=original['captured_at'], recorded_at=original['recorded_at'], as_of=original['as_of'],
        clock_binding=clock_binding)
    prepared = prepare_historical_authority(es, source)
    result = publish_historical_kite_capture(es, rs, project_id=original['project_id'], **prepared)
    es.commit(); rs.commit()
    with Session(es.get_bind()) as reopened_es, Session(rs.get_bind()) as reopened_rs:
        prefix = load_monitoring_input_prefix(reopened_rs, reopened_es, owner_id=context.owner_id,
            manifest_address=result.manifest.manifest_address, instrument_address=context.canonical_instrument.address,
            timeframe_seconds=seconds, minimum_bars=len(rows), maximum_age_seconds=60,
            cutoff_at=original['as_of'], graph_input_fields={'frame':FIELDS})
    assert prefix.bar_count == len(rows)
    assert prefix.completed_at == T0+dt.timedelta(days=2,hours=4,minutes=45)
    assert prefix.available_at == original['captured_at']
    assert prefix.recorded_at == original['recorded_at']
    assert json.loads(prefix.projection.source_provenance_json)['dated_sessions'] == clock_binding.metadata()


def _dated_bundle_fetch(es, seconds=1800, *, fresh=False):
    from app.market_data.dated_session_clock import SCHEMA, COMPLETION_SCHEMA, prepare_session_clock
    from app.market_truth.dated_sessions import parse_dated_sessions
    from app.market_truth.identity import load_provider_identity
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from research.data.provider_history_fetch import CurrentReferenceCapture, HistoricalResponseCapture
    fetch = _retrospective_bundle_fetch(es, entity_namespace='synthetic')
    original = fetch.sources[0]
    context = original.context
    entity, product, contract = load_provider_identity(es, context.provider_contract_address)
    captured = fetch.captures[0].received_at
    if fresh:
        captured = captured.replace(hour=4, minute=45, second=2)
    recorded = captured.replace(hour=0, minute=0, second=0, microsecond=0)
    first = recorded-dt.timedelta(days=1 if fresh else 2)+dt.timedelta(hours=4)
    days = [first+dt.timedelta(days=index) for index in range(3)]
    doc = dict(schema=SCHEMA, instrument_address=fetch.instrument.address, venue_code='XNSE', timezone='UTC',
        provenance='SYNTHETIC', source_reference='Synthetic rolling acquisition fixture',
        recorded_at=recorded.isoformat(), rows=[dict(date=day.date().isoformat(), status='OPEN',
        opens_at=day.isoformat(), closes_at=(day+dt.timedelta(minutes=45)).isoformat()) for day in days])
    calendar_raw = RawObservationSegment(fetch.owner_id, product.address, contract.address,
        'application/json', SCHEMA, canonical_json(doc).encode(), recorded)
    calendar = parse_dated_sessions(calendar_raw.payload, instrument_address=fetch.instrument.address,
        venue_code='XNSE', timezone='UTC', as_of=captured, allow_synthetic=True)
    completion = dict(schema=COMPLETION_SCHEMA, calendar_address=calendar.address,
        product_address=product.address, contract_address=contract.address, resolution_seconds=seconds,
        completion_rule='SESSION_OPEN_CLIP_CLOSE_V1', provenance='SYNTHETIC')
    completion_raw = RawObservationSegment(fetch.owner_id, product.address, contract.address,
        'application/json', COMPLETION_SCHEMA, canonical_json(completion).encode(), recorded)
    clock = prepare_session_clock(owner_id=fetch.owner_id, entity=entity, product=product, contract=contract,
        instrument=fetch.instrument, resolution_seconds=seconds, calendar_source=calendar_raw,
        completion_source=completion_raw, as_of=captured)
    persist_raw_segment(es, calendar_raw)
    persist_raw_segment(es, completion_raw)
    sources, captures = [], []
    interval = {900:'15minute', 1800:'30minute', 3600:'60minute'}[seconds]
    for index, day in enumerate(days[:2]):
        left = day if index == 0 else days[0]+dt.timedelta(minutes=45)
        right = day+dt.timedelta(minutes=45)-dt.timedelta(seconds=1)
        received = captured+dt.timedelta(seconds=index)
        reference = CurrentReferenceCapture(original.current_reference.payload + b'\n'*index,
            received-dt.timedelta(seconds=1), received, 'NSE')
        rows = [[(day+dt.timedelta(seconds=elapsed)).isoformat(), 100, 102, 99, 101+index, 1000]
            for elapsed in range(0,2700,seconds)]
        payload = json.dumps({'status':'success','data':{'candles':rows}}).encode()
        capture = HistoricalResponseCapture(payload, received, received+dt.timedelta(microseconds=1),
            left, right, interval, len(rows), reference)
        captures.append(capture)
        sources.append(prepare_historical_attribution(owner_id=fetch.owner_id, connection_id=fetch.connection_id,
            entity=entity, product=product, contract=contract, instrument=fetch.instrument,
            token=408065, symbol='INFY', exchange='NSE', interval=interval, requested_start=left, requested_end=right,
            current_reference_bytes=reference.payload, reference_received_at=reference.received_at,
            reference_recorded_at=reference.recorded_at, historical_response_bytes=payload,
            captured_at=received, recorded_at=capture.recorded_at, as_of=capture.recorded_at, clock_binding=clock))
    fetch.sources, fetch.captures = tuple(sources), tuple(captures)
    fetch.current_reference = captures[-1].current_reference
    fetch.requested_start, fetch.requested_end = captures[0].requested_start, captures[-1].requested_end
    return fetch


@pytest.mark.parametrize('seconds', [900,1800,3600])
@pytest.mark.parametrize('crop', [False,True])
def test_dated_historical_bundle_reopens_each_acquisition_reference_and_cropped_prefix(authority_sessions, seconds, crop):
    from research.data.provider_history_bundle import publish_historical_bundle
    from app.market_data.observations import load_provider_observation, load_raw_segment
    es, rs = authority_sessions
    fetch = _dated_bundle_fetch(es, seconds)
    per_day = len(range(0,2700,seconds))
    if crop:
        fetch.requested_start += dt.timedelta(seconds=seconds if per_day > 1 else 0)
    result = publish_historical_bundle(es, rs, fetch)
    es.commit(); rs.commit()
    data = _reopen_historical_bundle(es, rs, fetch, result)
    assert len(data.candles) == per_day*2-int(crop and per_day > 1)
    assert data.candles[-1].close == 102
    assert {load_provider_observation(es, key).available_at for key in result.manifest.provider_observation_addresses} == {
        item.received_at for item in fetch.captures}
    assert fetch.sources[0].current_reference.address != fetch.sources[1].current_reference.address
    for source in fetch.sources:
        assert load_raw_segment(es, source.current_reference.address) == source.current_reference
    assert data.binding['historical_capture']['requested_start'] == fetch.requested_start.isoformat()


@pytest.mark.parametrize('maximum_bars', [2,4,2000])
def test_dated_historical_bundle_second_cycle_reloads_and_rolls_without_rewriting_receipts(authority_sessions, maximum_bars):
    from app.api.research_dataset_routes import _replay_cutoff
    from research.data.provider_history_fetch import HistoricalFetchResult
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.monitoring_history_roll import load_retained_monitoring_history, append_monitoring_history
    es, rs = authority_sessions
    fetch = HistoricalFetchResult(**vars(_dated_bundle_fetch(es, 900)))
    first = dataclasses.replace(fetch, captures=fetch.captures[:1], sources=fetch.sources[:1],
        requested_end=fetch.captures[0].requested_end, current_reference=fetch.captures[0].current_reference)
    initial = publish_historical_bundle(es, rs, first)
    es.commit(); rs.commit()
    retained = load_retained_monitoring_history(es, rs, owner_id=fetch.owner_id, project_id=fetch.project_id,
        manifest_address=initial.manifest.manifest_address, as_of=dt.datetime.fromisoformat(_replay_cutoff(initial.manifest)))
    assert retained == first
    next_capture = dataclasses.replace(fetch, captures=fetch.captures[1:], sources=fetch.sources[1:],
        requested_start=fetch.captures[1].requested_start)
    rolled = append_monitoring_history(retained, next_capture, maximum_bars=maximum_bars)
    updated = publish_historical_bundle(es, rs, rolled)
    es.commit(); rs.commit()
    data = _reopen_historical_bundle(es, rs, rolled, updated)
    assert len(data.candles) == min(6, maximum_bars)
    assert data.candles[-1].close == 102
    assert rolled.captures[-1] == next_capture.captures[-1]
    assert rolled.sources[-1] == next_capture.sources[-1]
    assert len(_reopen_historical_bundle(es, rs, first, initial).candles) == 3


@pytest.mark.parametrize('change', ['owner_id','project_id','connection_id','selection_address','requested_start'])
def test_dated_historical_bundle_roll_refuses_cross_binding_and_window_gaps(authority_sessions, change):
    from research.data.provider_history_fetch import HistoricalFetchResult
    from research.data.monitoring_history_roll import append_monitoring_history
    from research.data.historical_capture import HistoricalCaptureRefused
    es, _ = authority_sessions
    fetch = HistoricalFetchResult(**vars(_dated_bundle_fetch(es)))
    first = dataclasses.replace(fetch, captures=fetch.captures[:1], sources=fetch.sources[:1],
        requested_end=fetch.captures[0].requested_end)
    following = dataclasses.replace(fetch, captures=fetch.captures[1:], sources=fetch.sources[1:],
        requested_start=fetch.captures[1].requested_start)
    value = getattr(following, change)
    replacement = value+dt.timedelta(seconds=1) if change == 'requested_start' else (
        value+1 if change == 'connection_id' else 'foreign')
    with pytest.raises(HistoricalCaptureRefused):
        append_monitoring_history(first, dataclasses.replace(following, **{change:replacement}))


@pytest.mark.parametrize('seconds', [900,1800,3600])
def test_dated_monitoring_request_clamps_to_completed_bar_open_and_clipped_session(authority_sessions, seconds):
    from research.data.provider_history_fetch import _monitoring_windows, HistoricalFetchRefused
    es, _ = authority_sessions
    fetch = _dated_bundle_fetch(es, seconds)
    clock = fetch.sources[0].clock_binding
    start = fetch.requested_start
    close = start+dt.timedelta(minutes=45)
    with pytest.raises(HistoricalFetchRefused, match='No new completed bar'):
        _monitoring_windows(start, close, fetch.captures[0].interval, clock,
            start+dt.timedelta(seconds=min(seconds,2700)-1))
    windows = _monitoring_windows(start, close, fetch.captures[0].interval, clock, close)
    assert windows == ((start, start+dt.timedelta(seconds=((2700-1)//seconds)*seconds)),)
    if seconds < 2700:
        first_completed = start+dt.timedelta(seconds=seconds)
        assert _monitoring_windows(start, close, fetch.captures[0].interval, clock, first_completed) == ((start,start),)


def test_dated_historical_bundle_refuses_reference_from_another_acquisition(authority_sessions):
    from app.db.models import AuthorityNormalizedObservation
    from research.domain.models import ResearchDatasetManifestV2
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.historical_capture import HistoricalCaptureRefused
    es, rs = authority_sessions
    fetch = _dated_bundle_fetch(es)
    replacement = dataclasses.replace(fetch.captures[0].current_reference, payload=fetch.captures[1].current_reference.payload)
    fetch.captures = (dataclasses.replace(fetch.captures[0], current_reference=replacement),
        fetch.captures[1])
    with pytest.raises(HistoricalCaptureRefused):
        publish_historical_bundle(es, rs, fetch)
    assert es.query(AuthorityNormalizedObservation).count() == 0
    assert rs.query(ResearchDatasetManifestV2).count() == 0


@pytest.mark.parametrize('change', [None,'owner','project','selection','connection','timeframe','stale','manifest'])
def test_dated_provider_watchlist_mapping_requires_exact_fresh_replayed_input(authority_sessions, change):
    from app.monitoring.provider_watchlist_binding import resolve_provider_watchlist_instrument
    from app.monitoring.watchlist_store import WatchlistMonitoringConflict
    from research.data.provider_history_bundle import publish_historical_bundle
    es, rs = authority_sessions
    fetch = _dated_bundle_fetch(es, fresh=True)
    result = publish_historical_bundle(es, rs, fetch)
    es.commit(); rs.commit()
    request = SimpleNamespace(owner_id=fetch.owner_id, project_id=fetch.project_id,
        member_key='PROVIDER_REFERENCE:'+fetch.selection_address, timeframe='30minute')
    spec = SimpleNamespace(data_connection_id=fetch.connection_id)
    now = fetch.captures[-1].recorded_at
    manifest_address = result.manifest.manifest_address
    if change == 'owner':
        request.owner_id = 'foreign-owner'
    if change == 'project':
        request.project_id = 'foreign-project'
    if change == 'selection':
        request.member_key = 'PROVIDER_REFERENCE:'+address('foreign-selection')
    if change == 'connection':
        spec.data_connection_id += 1
    if change == 'timeframe':
        request.timeframe = '15minute'
    if change == 'stale':
        now += dt.timedelta(seconds=61)
    if change == 'manifest':
        manifest_address = address('absent-manifest')
    arguments = dict(requested=request, assignment_spec=spec, policy={'maximum_age_seconds':60},
        manifest_address=manifest_address, now=now)
    if change is not None:
        with pytest.raises(WatchlistMonitoringConflict, match='mapping provenance'):
            resolve_provider_watchlist_instrument(es, rs, **arguments)
    else:
        assert resolve_provider_watchlist_instrument(es, rs, **arguments) == fetch.instrument.address


def _research_prefix_publish(es, rs, source, rows, *, lag=0, graph_input_fields=None):
    from research.data.historical_capture import publish_historical_kite_capture
    from app.monitoring.input_producer import load_monitoring_input_prefix
    opened = dt.datetime.fromisoformat(rows[-1][0])
    completed = opened + dt.timedelta(minutes=15)
    kwargs = {**source, 'raw_response': json.dumps({'status': 'success', 'data': {'candles': rows}}).encode(),
        'requested_start': dt.datetime.fromisoformat(rows[0][0]),
        'requested_end': completed - dt.timedelta(seconds=1),
        'captured_at': completed + dt.timedelta(seconds=2 + lag),
        'recorded_at': completed + dt.timedelta(seconds=3 + lag),
        'as_of': completed + dt.timedelta(seconds=4 + lag)}
    result = publish_historical_kite_capture(es, rs, **kwargs)
    es.commit(); rs.commit()
    request = dict(owner_id=source['owner_id'], manifest_address=result.manifest.manifest_address,
        instrument_address=source['context'].canonical_instrument.address, timeframe_seconds=900,
        minimum_bars=3, maximum_age_seconds=60, cutoff_at=kwargs['as_of'], graph_input_fields=graph_input_fields or {'frame': FIELDS})
    return load_monitoring_input_prefix(rs, es, **request), request


def _research_prefix_consumer(prefix, risk_policy='none'):
    """Describe pure replay inputs; this helper does not issue monitoring admission."""
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.ir.resource_plan import _canonical
    from app.monitoring.research_consumer import SCHEMA, _replay_policy
    from app.monitoring.research_prefix import ResearchReplayCheckpoint
    from app.monitoring.research_replay_state import ResearchReplayState
    from research.orchestrator.v2_preparation import execution_policy
    from research_tests.test_v2_graph_experiment_bridge import _saved_v2_boolean_graph
    document = _saved_v2_boolean_graph(REGISTRY)
    graph = resolve_v2(document, REGISTRY)
    owner = prefix.projection.manifest.owner_id
    consumer = _canonical(SCHEMA, {'owner_id': owner, 'assignment_id': 'research-prefix-assignment',
        'graph_version_address': graph.authored_ir_address,
        'resolved_graph_address': graph.resolved_graph_address,
        'graph_implementation_address': graph.implementation_closure_address,
        **_replay_policy({'execution_policy': execution_policy(10000.0, risk_policy),
            'settings_snapshot': {'schema': 'research-settings-snapshot/3'}})})
    state = ResearchReplayState(owner, 'research-prefix-assignment',
        prefix.projection.manifest.instrument_addresses[0], consumer.address, 0)
    return ResearchReplayCheckpoint(state), consumer, document, graph


def _research_prefix_advance(checkpoint, prefix, consumer, document, graph):
    from app.ir.library import REGISTRY
    from app.monitoring.research_prefix import advance_research_prefix, evaluate_research_prefix_outputs
    outputs = evaluate_research_prefix_outputs(prefix, consumer=consumer, graph_document=document, registry=REGISTRY)
    return advance_research_prefix(checkpoint, prefix=prefix, consumer=consumer,
        graph_document=document, outputs=outputs, timeframe_seconds=900)


def _research_prefix_issued_schedule(prefix, consumer, graph):
    from app.ir.library import REGISTRY
    from app.ir.evaluation_schedule import admit_evaluation_event
    from app.ir.resource_plan import compile_resource_plan
    from app.market_data.requirements import compile_data_requirement_plan
    from tests.test_v0_evaluation_schedule import _completed_schedule
    data = compile_data_requirement_plan(graph, registry=REGISTRY, input_bindings=prefix.projection.input_bindings)
    resource = compile_resource_plan(graph, data, REGISTRY, cache_bytes_upper_bound=1024,
        artifact_bytes_upper_bound=0, queue_concurrency_upper_bound=1)
    schedule = _completed_schedule((REGISTRY, graph, data, resource),
        owner_id=prefix.projection.manifest.owner_id, assignment_id=consumer.document['assignment_id'],
        freshness_ceiling_seconds=60)
    event = admit_evaluation_event(schedule, trigger='completed_bar', observation_address=prefix.observation_address,
        event_at=prefix.event_at, completed_at=prefix.completed_at, available_at=prefix.available_at,
        recorded_at=prefix.recorded_at, cutoff_at=prefix.cutoff_at, unit_contract_address=schedule.event_unit_address)
    return schedule, event


def _research_compiler_schedule(prefix, graph, consumer, instrument, policy=None):
    from app.ir.library import REGISTRY
    from app.ir.resource_plan import compile_resource_plan
    from app.market_data.requirements import compile_data_requirement_plan
    from app.monitoring.evaluation_policy import compile_monitoring_evaluation_policy
    from app.monitoring.research_schedule import compile_research_monitoring_schedule
    data = compile_data_requirement_plan(graph, registry=REGISTRY, input_bindings=prefix.projection.input_bindings)
    resource = compile_resource_plan(graph, data, REGISTRY, cache_bytes_upper_bound=1024,
        artifact_bytes_upper_bound=0, queue_concurrency_upper_bound=1)
    if policy is None:
        document = resource.document
        policy = compile_monitoring_evaluation_policy(owner_id=consumer.document['owner_id'],
            assignment_id=consumer.document['assignment_id'], initial_resource_plan_address=resource.plan_address,
            maximum_age_seconds=60, history_bytes_upper_bound=sum(row['bytes_upper_bound'] for row in document['history_requirements']),
            memory_bytes_upper_bound=document['memory_bytes_upper_bound'], cache_bytes_upper_bound=document['cache_bytes_upper_bound'],
            queue_concurrency_upper_bound=1, event_rate_events=1, event_rate_per_seconds=60)
    schedule, event = compile_research_monitoring_schedule(prefix=prefix, graph=graph, registry=REGISTRY,
        evaluation_policy=policy, canonical_instrument=instrument, timeframe_seconds=900)
    return policy, schedule, event


def _research_compiler_arguments(prefix, source):
    """Compiler scope fixture; the worker must separately reload actual research admission."""
    from app.ir.library import REGISTRY
    from app.ir.resource_plan import _canonical, _plain
    from app.monitoring.research_consumer import SCHEMA, research_consumer_implementation_address
    from app.monitoring.state_contracts import MonitoringAssignment
    from tests.test_v0_monitoring_persistence import _spec
    _, original, document, graph = _research_prefix_consumer(prefix)
    consumer = _canonical(SCHEMA, {**_plain(original.document), 'project_id': source['project_id'],
        'original_admission_address': address('compiler-admission-fixture'),
        'consumer_implementation_address': research_consumer_implementation_address()})
    policy, schedule, event = _research_compiler_schedule(prefix, graph, consumer, source['context'].canonical_instrument)
    spec = dataclasses.replace(_spec(consumer.document['assignment_id'], source['project_id']),
        graph_version_address=graph.authored_ir_address, resolved_graph_address=graph.resolved_graph_address,
        implementation_closure_address=graph.implementation_closure_address, registry_address=REGISTRY.registry_snapshot_address,
        research_admission_address=consumer.document['original_admission_address'],
        data_connection_id=source['connection_id'],
        resource_plan_address=policy.document['initial_resource_plan_address'], evaluation_trigger_address=policy.address)
    assignment = MonitoringAssignment(prefix.projection.manifest.owner_id, spec, 1, 'ACTIVE', None,
        prefix.completed_at, prefix.completed_at, None)
    return dict(assignment=assignment, consumer=consumer, prefix=prefix, graph=graph, graph_document=document,
        registry=REGISTRY, schedule=schedule, evaluation_event=event, evaluation_policy=policy,
        canonical_instrument=source['context'].canonical_instrument, timeframe_seconds=900, display_symbol='SELF')


@pytest.fixture
def research_compiler_sessions(tmp_path):
    from tests.test_v0_monitoring_persistence import _engine
    execution = _engine(tmp_path, 'research-compiler-execution.db')
    research = create_engine(f"sqlite:///{tmp_path/'research-compiler-research.db'}")
    init_research_db(research)
    with Session(execution) as es, Session(research) as rs:
        yield es, rs
    execution.dispose()
    research.dispose()


def test_research_prefix_compiler_persists_real_observed_tail_and_new_current_entry_after_missed_cycle(research_compiler_sessions):
    from app.monitoring.research_evaluation import compile_initial_research_monitoring_state, compile_research_monitoring_prefix
    from app.monitoring.research_runtime import persist_research_transitions
    from app.monitoring.repository import MonitoringRepository
    from app.monitoring.contracts import SignalAction, NoAlert, NoAlertCode, AlertDerived, StrategyState
    es, rs = research_compiler_sessions
    source = _historical_capture_source(es, count=7)
    rows = json.loads(source['raw_response'])['data']['candles']
    for row, prices in zip(rows[3:], ([103, 104, 99, 100], [100, 101, 97, 98], [99, 100, 97, 99], [100, 101, 98, 100]), strict=True):
        row[1:5] = prices
    first, _ = _research_prefix_publish(es, rs, source, rows[:3])
    arguments = _research_compiler_arguments(first, source)
    repository = MonitoringRepository(es, owner_id=source['owner_id'])
    assignment = repository.create_assignment(arguments['assignment'].spec, now=first.cutoff_at)
    arguments['assignment'] = assignment
    initial_args = {key: value for key, value in arguments.items() if key not in ('graph_document', 'display_symbol')}
    initial = compile_initial_research_monitoring_state(**initial_args)
    assert initial.snapshot_sequence == 0 and initial.checkpoint.state.position is None
    repository.append_state_snapshot(initial, created_at=first.cutoff_at)
    arguments.update(assignment=repository.get_assignment(initial.assignment_id), previous_snapshot=initial)
    first_steps = compile_research_monitoring_prefix(**arguments)
    assert len(first_steps) == 1 and first_steps[0].signal_event.action is SignalAction.BUY
    assert first_steps[0].signal_event.stop_loss.status == 'DISABLED'
    assert first_steps[0].next_snapshot.checkpoint.history_bars == 3
    _assert_research_compiler_scope_refusals(arguments, initial, initial_args)
    persist_research_transitions(repository, first_steps, created_at=first.cutoff_at)
    es.commit()
    fresh, request = _research_prefix_publish(es, rs, source, rows)
    policy, schedule, issued = _research_compiler_schedule(fresh, arguments['graph'], arguments['consumer'],
        arguments['canonical_instrument'], arguments['evaluation_policy'])
    with Session(es.get_bind()) as reopened:
        repository = MonitoringRepository(reopened, owner_id=source['owner_id'])
        previous = repository.get_latest_state(initial.assignment_id, initial.canonical_instrument_address)
        arguments.update(assignment=repository.get_assignment(initial.assignment_id), previous_snapshot=previous,
            prefix=fresh, schedule=schedule, evaluation_event=issued, evaluation_policy=policy)
        steps = compile_research_monitoring_prefix(**arguments)
        assert len(steps) == 4
        assert previous.strategy_state is steps[-1].next_snapshot.strategy_state is StrategyState.LONG
        assert all(isinstance(step.alert_result, NoAlert) and step.alert_result.code is NoAlertCode.REPLAY_CATCH_UP for step in steps[:-1])
        assert isinstance(steps[-1].alert_result, AlertDerived) and steps[-1].signal_event.action is SignalAction.BUY
        assert steps[-1].next_snapshot.checkpoint.state.position is None
        assert steps[-1].next_snapshot.checkpoint.state.pending.kind == 'ENTER'
        saved = persist_research_transitions(repository, steps, created_at=fresh.cutoff_at)
        reopened.commit()
        assert len(repository.list_alerts().items) == 2
        assert persist_research_transitions(repository, steps, created_at=fresh.cutoff_at) == saved
        arguments.update(assignment=repository.get_assignment(initial.assignment_id), previous_snapshot=steps[-1].next_snapshot)
        assert compile_research_monitoring_prefix(**arguments) == ()


def _assert_research_compiler_scope_refusals(arguments, initial, initial_arguments):
    from app.ir.resource_plan import _canonical, _plain
    from app.monitoring.research_evaluation import compile_initial_research_monitoring_state, compile_research_monitoring_prefix
    assignment, prefix = arguments['assignment'], arguments['prefix']
    consumer = arguments['consumer']
    changed_consumer = _canonical(consumer.schema, {**_plain(consumer.document), 'project_id': 'different-project'})
    changed_implementation = _canonical(consumer.schema, {**_plain(consumer.document),
        'consumer_implementation_address': address('different-consumer-code')})
    cases = ({'assignment': dataclasses.replace(assignment, owner_id='different-owner')},
        {'assignment': dataclasses.replace(assignment, lifecycle_state='PAUSED')},
        {'assignment': dataclasses.replace(assignment, current_state_snapshot_address=address('different-state'))},
        {'assignment': dataclasses.replace(assignment, spec=dataclasses.replace(assignment.spec, data_connection_id=999))},
        {'previous_snapshot': None}, {'consumer': changed_consumer}, {'consumer': changed_implementation},
        {'canonical_instrument': None}, {'graph': None}, {'registry': None}, {'evaluation_policy': None},
        {'prefix': dataclasses.replace(prefix, observation_address=address('different-receipts'))},
        {'prefix': dataclasses.replace(prefix, cutoff_at=prefix.cutoff_at+dt.timedelta(microseconds=1))},
        {'timeframe_seconds': 3600}, {'display_symbol': 'unsafe\nlabel'})
    for changes in cases:
        with pytest.raises(ValueError):
            compile_research_monitoring_prefix(**{**arguments, **changes})
    future_time = prefix.completed_at+dt.timedelta(seconds=1)
    future = dataclasses.replace(initial, effective_at=future_time,
        entry_reference=dataclasses.replace(initial.entry_reference, observed_at=future_time))
    with pytest.raises(ValueError, match='future'):
        compile_research_monitoring_prefix(**{**arguments, 'previous_snapshot': future,
            'assignment': dataclasses.replace(assignment, current_state_snapshot_address=future.address)})
    with pytest.raises(ValueError, match='already initialized'):
        compile_initial_research_monitoring_state(**{**initial_arguments, 'assignment': assignment})


def test_research_prefix_reopens_real_capture_then_fills_only_unconsumed_bars_and_dedupes_refetch(authority_sessions):
    from app.monitoring.research_prefix import ResearchReplayCheckpoint
    from app.monitoring.input_producer import load_monitoring_input_prefix
    es, rs = authority_sessions
    source = _historical_capture_source(es, count=6)
    rows = json.loads(source['raw_response'])['data']['candles']
    rows[3][4] = 102  # The saved falling(window=2) node needs two declines.
    rows[4][1:5] = [104, 106, 97, 98]
    rows[5][1:5] = [99, 101, 97, 98]
    first, first_request = _research_prefix_publish(es, rs, source, rows[:3])
    checkpoint, consumer, document, graph = _research_prefix_consumer(first)
    initial = _research_prefix_advance(checkpoint, first, consumer, document, graph)
    assert len(initial) == 1 and initial[0].checkpoint.history_bars == 3
    assert initial[0].transition.next_state.position is None
    assert initial[0].transition.next_state.pending.kind == 'ENTER'
    assert initial[0].bar.identity == first.bar_identity
    retained = canonical_json(initial[0].checkpoint.to_dict()).encode()
    _, request = _research_prefix_publish(es, rs, source, rows)
    with Session(es.get_bind()) as reopened_es, Session(rs.get_bind()) as reopened_rs:
        original = load_monitoring_input_prefix(reopened_rs, reopened_es, **first_request)
        assert original.projection.input_digest == first.projection.input_digest
        fresh = load_monitoring_input_prefix(reopened_rs, reopened_es, **request)
        checkpoint = ResearchReplayCheckpoint.from_json(retained)
        steps = _research_prefix_advance(checkpoint, fresh, consumer, document, graph)
    assert len(steps) == 3
    assert [step.checkpoint.history_bars for step in steps] == [4, 5, 6]
    assert [step.checkpoint.state.snapshot_sequence for step in steps] == [2, 3, 4]
    assert steps[0].transition.opened_position.entry_price == 103.0 * 1.00025
    assert len(steps[-1].transition.closed_trades) == 1
    assert steps[-1].transition.closed_trades[0].exit_price == 99.0 * .99975
    assert steps[-1].checkpoint.state.position is None
    refetch, _ = _research_prefix_publish(es, rs, source, rows, lag=10)
    assert refetch.manifest_address != fresh.manifest_address
    assert refetch.observation_address != fresh.observation_address
    assert _research_prefix_advance(steps[-1].checkpoint, refetch, consumer, document, graph) == ()


@pytest.mark.parametrize('change', ['old_close', 'old_volume', 'old_open', 'truncate'])
def test_research_prefix_refuses_changed_or_truncated_verified_warmup_history(authority_sessions, change):
    from app.monitoring.contracts import MonitoringContractError
    from research.data.historical_capture import HistoricalCaptureRefused
    es, rs = authority_sessions
    source = _historical_capture_source(es, count=4)
    rows = json.loads(source['raw_response'])['data']['candles']
    first, _ = _research_prefix_publish(es, rs, source, rows[:3])
    checkpoint, consumer, document, graph = _research_prefix_consumer(first)
    checkpoint = _research_prefix_advance(checkpoint, first, consumer, document, graph)[0].checkpoint
    changed = json.loads(json.dumps(rows))
    if change == 'truncate':
        changed = changed[1:]
    else:
        column = {'old_close': 4, 'old_volume': 5, 'old_open': 1}[change]
        changed[0][column] += .25
        with pytest.raises(HistoricalCaptureRefused) as error:
            _research_prefix_publish(es, rs, source, changed)
        assert error.value.code == 'HISTORICAL_CAPTURE_REVISION_REQUIRES_LINEAGE'
    fresh, _ = _research_prefix_publish(es, rs, source, changed if change == 'truncate' else rows)
    if change != 'truncate':
        field = {'old_close': 'close', 'old_volume': 'volume', 'old_open': 'open'}[change]
        candle = fresh.candles[0]
        fresh = dataclasses.replace(fresh, candles=(dataclasses.replace(candle,
            **{field: getattr(candle, field) + .25}), *fresh.candles[1:]))
    with pytest.raises(MonitoringContractError, match='history changed'):
        _research_prefix_advance(checkpoint, fresh, consumer, document, graph)


def test_research_prefix_uses_full_verified_warmup_for_original_ratchet_seed(authority_sessions):
    from app.backtest import engine
    es, rs = authority_sessions
    source = _historical_capture_source(es, count=18)
    rows = json.loads(source['raw_response'])['data']['candles']
    first, _ = _research_prefix_publish(es, rs, source, rows[:15])
    later, _ = _research_prefix_publish(es, rs, source, rows)
    atr = engine.wilder_atr(engine.prepare_signal_frame(later.candles), 14, seed_policy='sma')
    for risk_policy in ('pine-v4-ratchet/1', 'pine-v4-reversal/1'):
        checkpoint, consumer, document, graph = _research_prefix_consumer(first, risk_policy)
        initial = _research_prefix_advance(checkpoint, first, consumer, document, graph)
        assert len(initial) == 1 and initial[0].checkpoint.state.position is None
        steps = _research_prefix_advance(initial[0].checkpoint, later, consumer, document, graph)
        assert len(steps) == 3
        position = steps[0].checkpoint.state.position
        assert position.entry_atr.hex() == float(atr.iloc[15]).hex()
        assert position.ratchet_high_water == position.entry_price
        assert steps[-1].checkpoint.state.position.entry_atr == position.entry_atr


def test_research_prefix_evaluation_refuses_mutated_source_graph_and_owner(authority_sessions):
    from app.ir.library import REGISTRY
    from app.ir.resource_plan import _canonical, _plain
    from app.monitoring.research_prefix import evaluate_research_prefix_outputs
    from app.monitoring.contracts import MonitoringContractError
    es, rs = authority_sessions
    _, request = _fresh_monitoring_history(es, rs)
    from app.monitoring.input_producer import load_monitoring_input_prefix
    prefix = load_monitoring_input_prefix(rs, es, **request)
    _, consumer, document, _ = _research_prefix_consumer(prefix)
    close = prefix.projection.inputs['frame']['close']
    original = close.iloc[0]
    try:
        close.iloc[0] = original + .125
        with pytest.raises(MonitoringContractError, match='input values changed'):
            evaluate_research_prefix_outputs(prefix, consumer=consumer, graph_document=document, registry=REGISTRY)
    finally:
        close.iloc[0] = original
    shifted = dataclasses.replace(prefix, candles=(dataclasses.replace(prefix.candles[0],
        ts=prefix.candles[0].ts+dt.timedelta(seconds=1)), *prefix.candles[1:]))
    with pytest.raises(MonitoringContractError, match='bar clocks'):
        evaluate_research_prefix_outputs(shifted, consumer=consumer, graph_document=document, registry=REGISTRY)
    changed = json.loads(json.dumps(document))
    changed['nodes'][0]['parameters']['window'] = 3
    with pytest.raises(MonitoringContractError, match='graph differs'):
        evaluate_research_prefix_outputs(prefix, consumer=consumer, graph_document=changed, registry=REGISTRY)
    foreign = _canonical(consumer.schema, {**_plain(consumer.document), 'owner_id': 'foreign-owner'})
    with pytest.raises(MonitoringContractError, match='owner differs'):
        evaluate_research_prefix_outputs(prefix, consumer=foreign, graph_document=document, registry=REGISTRY)


def test_research_prefix_first_capture_interleaving_preserves_one_source_and_rolls_back_loser(authority_sessions, monkeypatch):
    from sqlalchemy import func, select
    from app.db.models import AuthorityProviderObservation, AuthorityRawSegment
    from research.data import historical_capture as history
    es, rs = authority_sessions
    source = _historical_capture_source(es, count=3)
    rows = json.loads(source['raw_response'])['data']['candles']
    changed = json.loads(json.dumps(rows))
    changed[0][4] += .25
    publish, winner = history._publish, {}

    def retained_counts():
        return tuple(es.scalar(select(func.count()).select_from(model))
            for model in (AuthorityProviderObservation, AuthorityRawSegment))

    def interleaved_publish(*args, **kwargs):
        if not winner:
            winner['started'] = True
            prefix, _ = _research_prefix_publish(es, rs, source, changed, lag=1)
            winner['close'] = prefix.candles[0].close
            winner['counts'] = retained_counts()
        return publish(*args, **kwargs)

    monkeypatch.setattr(history, '_publish', interleaved_publish)
    with pytest.raises(history.HistoricalCaptureRefused) as error:
        _research_prefix_publish(es, rs, source, rows)
    assert error.value.code == 'HISTORICAL_CAPTURE_REVISION_REQUIRES_LINEAGE'
    assert winner['close'] == changed[0][4]
    assert retained_counts() == winner['counts']


def test_research_prefix_refetch_refuses_known_correction_but_original_cutoff_replays(authority_sessions):
    from sqlalchemy import select
    from app.db.models import AuthorityProviderObservation
    from app.market_data.kite_observations import map_historical_candles
    from app.market_data.observations import persist_raw_segment, persist_provider_observation
    from app.monitoring.input_producer import load_monitoring_input_prefix
    from research.data.historical_capture import HistoricalCaptureRefused
    es, rs = authority_sessions
    source = _historical_capture_source(es, count=3)
    rows = json.loads(source['raw_response'])['data']['candles']
    first, request = _research_prefix_publish(es, rs, source, rows)
    anchor = es.scalar(select(AuthorityProviderObservation).where(
        AuthorityProviderObservation.owner_id == source['owner_id'],
        AuthorityProviderObservation.field == 'close',
        AuthorityProviderObservation.supersedes_address.is_(None))
        .order_by(AuthorityProviderObservation.event_time))
    corrected = json.loads(json.dumps(rows[:1]))
    corrected[0][4] += .25
    batch = map_historical_candles({'status': 'success', 'data': {'candles': corrected}},
        context=source['context'], resolution_seconds=900,
        available_at=first.cutoff_at+dt.timedelta(seconds=10),
        recorded_at=first.cutoff_at+dt.timedelta(seconds=11),
        as_of=first.cutoff_at+dt.timedelta(seconds=12))
    changed = next(item for item in batch.observations if item.field == 'close')
    for raw in batch.raw_segments:
        persist_raw_segment(es, raw)
    persist_provider_observation(es, dataclasses.replace(changed,
        correction_id=address('explicit-historical-correction'), supersedes_address=anchor.address))
    es.commit()
    original = load_monitoring_input_prefix(rs, es, **request)
    assert original.projection.input_digest == first.projection.input_digest
    with pytest.raises(HistoricalCaptureRefused) as error:
        _research_prefix_publish(es, rs, source, rows, lag=20)
    assert error.value.code == 'HISTORICAL_CAPTURE_REVISION_REQUIRES_LINEAGE'


def _research_retained_window(es, fetch, source, rows, start, end, received):
    from app.market_truth.identity import load_provider_identity
    from app.market_data.kite_historical_attribution import prepare_historical_attribution
    from research.data.provider_history_fetch import CurrentReferenceCapture, HistoricalResponseCapture
    entity, product, contract = load_provider_identity(es, source.context.provider_contract_address)
    reference = CurrentReferenceCapture(source.current_reference.payload,
        received-dt.timedelta(seconds=1), received, 'NSE')
    payload = json.dumps({'status': 'success', 'data': {'candles': rows}}).encode()
    captured = HistoricalResponseCapture(payload, received, received+dt.timedelta(microseconds=1),
        start, end, '15minute', len(rows), reference)
    attribution = prepare_historical_attribution(owner_id=fetch.owner_id, connection_id=fetch.connection_id,
        entity=entity, product=product, contract=contract, instrument=fetch.instrument,
        token=408065, symbol='INFY', exchange='NSE', interval='15minute', requested_start=start, requested_end=end,
        current_reference_bytes=reference.payload, reference_received_at=reference.received_at,
        reference_recorded_at=reference.recorded_at, historical_response_bytes=payload,
        captured_at=received, recorded_at=captured.recorded_at, as_of=captured.recorded_at,
        clock_binding=source.clock_binding)
    return attribution, captured


@pytest.mark.parametrize('receipt_offsets', [(-901, 2.1), (2.1, -901), (2.1, 2.1)])
def test_research_prefix_freshness_uses_when_the_whole_prefix_became_available(receipt_offsets):
    from research.data.canonical_dataset import _time_interpretation
    completed = dt.datetime(2026, 9, 7, 4, 45, tzinfo=dt.timezone.utc)
    receipts = [completed + dt.timedelta(seconds=offset) for offset in receipt_offsets]
    result = _time_interpretation(900, SimpleNamespace(calendar='NSE', timezone='Asia/Kolkata'),
        receipts, completed, historical={})
    assert result['actual_source_observed_at'] == max(receipts).isoformat()
    assert result['actual_source_lag_seconds'] == 3


def _research_retained_prefix_fetches(es):
    from research.data.provider_history_fetch import HistoricalFetchResult
    base = HistoricalFetchResult(**vars(_dated_bundle_fetch(es, 900, fresh=True)))
    previous_rows = json.loads(base.captures[0].payload)['data']['candles']
    today = json.loads(base.captures[1].payload)['data']['candles']
    today[0][1:5], today[1][1:5], today[2][1:5] = [101, 104, 100, 102], [102, 105, 101, 103], [104, 106, 100, 102]
    next_open = dt.datetime.fromisoformat(today[2][0])
    first_window = _research_retained_window(es, base, base.sources[0], previous_rows,
        base.captures[0].requested_start, base.captures[0].requested_end, next_open+dt.timedelta(seconds=2))
    second_window = _research_retained_window(es, base, base.sources[1], today[:2],
        base.captures[1].requested_start, next_open-dt.timedelta(seconds=1), next_open+dt.timedelta(seconds=3))
    first = dataclasses.replace(base, sources=(first_window[0], second_window[0]),
        captures=(first_window[1], second_window[1]), requested_end=second_window[1].requested_end,
        current_reference=second_window[1].current_reference)
    next_window = _research_retained_window(es, base, base.sources[1], today[2:], next_open,
        base.requested_end, next_open+dt.timedelta(minutes=15, seconds=2))
    later = dataclasses.replace(base, sources=(next_window[0],), captures=(next_window[1],),
        requested_start=next_open, current_reference=next_window[1].current_reference)
    return first, later


@pytest.mark.parametrize('maximum_bars', [2000, 4])
def test_research_prefix_uses_retained_provider_windows_for_next_observed_bar_and_refuses_rolling_reset(authority_sessions, maximum_bars):
    from app.monitoring.contracts import MonitoringContractError
    from app.monitoring.input_producer import load_monitoring_input_prefix
    from app.monitoring.provider_watchlist_binding import resolve_provider_watchlist_instrument
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.data.monitoring_history_roll import load_retained_monitoring_history, append_monitoring_history
    es, rs = authority_sessions
    first, acquired = _research_retained_prefix_fetches(es)
    initial = publish_historical_bundle(es, rs, first)
    es.commit(); rs.commit()
    cutoff = first.captures[-1].recorded_at.replace(microsecond=0)+dt.timedelta(seconds=2)
    request = dict(owner_id=first.owner_id, instrument_address=first.instrument.address,
        timeframe_seconds=900, minimum_bars=3, maximum_age_seconds=60, graph_input_fields={'frame': FIELDS})
    prefix = load_monitoring_input_prefix(rs, es, manifest_address=initial.manifest.manifest_address,
        cutoff_at=cutoff, **request)
    checkpoint, consumer, document, graph = _research_prefix_consumer(prefix)
    activation = _research_prefix_advance(checkpoint, prefix, consumer, document, graph)
    assert len(activation) == 1 and activation[0].checkpoint.history_bars == 5
    assert activation[0].checkpoint.state.position is None
    assert activation[0].checkpoint.state.pending.kind == 'ENTER'
    schedule, issued = _research_prefix_issued_schedule(prefix, consumer, graph)
    assert issued.completed_at == prefix.completed_at and issued.cutoff_at == prefix.cutoff_at
    assert schedule.maximum_age_seconds <= 60
    with Session(es.get_bind()) as reopened_es, Session(rs.get_bind()) as reopened_rs:
        retained = load_retained_monitoring_history(reopened_es, reopened_rs,
            owner_id=first.owner_id, project_id=first.project_id,
            manifest_address=initial.manifest.manifest_address, as_of=cutoff)
    assert retained == first
    rolled = append_monitoring_history(retained, acquired, maximum_bars=maximum_bars)
    assert rolled.captures[:2] == first.captures
    updated = publish_historical_bundle(es, rs, rolled)
    es.commit(); rs.commit()
    cutoff = acquired.captures[-1].recorded_at.replace(microsecond=0)+dt.timedelta(seconds=2)
    fresh = load_monitoring_input_prefix(rs, es, manifest_address=updated.manifest.manifest_address,
        cutoff_at=cutoff, **request)
    next_schedule, next_issued = _research_prefix_issued_schedule(fresh, consumer, graph)
    assert next_schedule.schedule_address != schedule.schedule_address
    assert next_issued.observation_address == fresh.observation_address
    selected = SimpleNamespace(owner_id=first.owner_id, project_id=first.project_id,
        member_key='PROVIDER_REFERENCE:'+first.selection_address, timeframe='15minute')
    assert resolve_provider_watchlist_instrument(es, rs, requested=selected,
        assignment_spec=SimpleNamespace(data_connection_id=first.connection_id), policy={'maximum_age_seconds':60},
        manifest_address=fresh.manifest_address, now=cutoff) == first.instrument.address
    if maximum_bars == 4:
        with pytest.raises(MonitoringContractError, match='history changed'):
            _research_prefix_advance(activation[0].checkpoint, fresh, consumer, document, graph)
        return
    assert set(initial.manifest.provider_observation_addresses) <= set(updated.manifest.provider_observation_addresses)
    steps = _research_prefix_advance(activation[0].checkpoint, fresh, consumer, document, graph)
    assert len(steps) == 1 and steps[0].checkpoint.history_bars == 6
    assert steps[0].checkpoint.state.position.entry_price == 104.0 * 1.00025
    assert _research_prefix_advance(steps[0].checkpoint, fresh, consumer, document, graph) == ()
