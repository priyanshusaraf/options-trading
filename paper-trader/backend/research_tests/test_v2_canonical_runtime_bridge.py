from types import SimpleNamespace
from copy import deepcopy

import pandas as pd
import pytest

from app.ir.incremental_runtime import IncrementalRuntimeRefusal, _common_index, _prefix_value
from app.ir.hashing import content_address


def _runtime_shell():
    return SimpleNamespace(nodes=()), SimpleNamespace(node_contracts={})


def test_nested_named_field_frames_share_one_clock_and_slice_every_series():
    index = pd.date_range("2026-01-01T09:16:00Z", periods=4, freq="15min")
    inputs = {
        "frame": {
            "open": pd.Series([100.0, 101.0, 102.0, 103.0], index=index),
            "close": pd.Series([101.0, 102.0, 103.0, 104.0], index=index),
        }
    }
    graph, registry = _runtime_shell()

    assert _common_index(graph, inputs, registry).equals(index)
    prefix = _prefix_value(inputs, 2, index)
    assert prefix["frame"]["open"].index.equals(index[:2])
    assert prefix["frame"]["close"].tolist() == [101.0, 102.0]
    assert inputs["frame"]["close"].tolist() == [101.0, 102.0, 103.0, 104.0]


def test_nested_named_field_frames_refuse_unequal_or_malformed_indexes():
    index = pd.date_range("2026-01-01T09:16:00Z", periods=3, freq="15min")
    graph, registry = _runtime_shell()
    with pytest.raises(IncrementalRuntimeRefusal, match="causal UTC sequence"):
        _common_index(graph, {
            "frame": {
                "open": pd.Series([1.0, 2.0, 3.0], index=index),
                "close": pd.Series([1.0, 2.0], index=index[:2]),
            }
        }, registry)
    with pytest.raises(IncrementalRuntimeRefusal, match="causal UTC sequence"):
        _common_index(graph, {
            "frame": {"close": pd.Series(
                [1.0, 2.0, 3.0], index=index.tz_localize(None),
            )}
        }, registry)


@pytest.mark.parametrize("module_name,component,prices,expected", [
    ("core_math", "sma", [1.0, 2.0, 3.0, 4.0], 3.5),
    ("recursive_state", "ema", [2.0, 4.0, 8.0, 4.0], 43.0 / 9.0),
])
def test_current_windowed_and_stateful_analytical_v2_execute_with_bound_contract_and_per_bar_parity(
    module_name, component, prices, expected,
):
    import importlib
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
    from app.ir.incremental_runtime import (
        CancellationToken, accept_research_resource_plan, evaluate_incremental_v2,
    )
    from app.ir.registry import PlatformRegistry
    from app.ir.resolve import resolve_v2
    from app.market_data.requirements import compile_data_requirement_plan
    from research.evaluation.phase5_runtime import execute_research
    from research_tests.test_phase5_research_execution import _dataset_inputs, _policy

    core = importlib.import_module(f"app.ir.first_party.analytical_v2.{module_name}")
    key = (f"analytical.{component}", 2)
    registry = PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=core.V2_TYPES,
        v2_components={key: core.V2_COMPONENTS[key]},
        node_contracts={key: core.NODE_CONTRACTS[key]},
        contract_bindings={key: core.CONTRACT_BINDINGS[key]},
        v2_implementations={key: core.V2_IMPLEMENTATIONS[key]},
    )
    from app.ir.node_contracts import _plain
    ports = deepcopy(_plain(core.V2_COMPONENTS[key]["ports"]))
    input_port = next(port for port in ports if port["direction"] == "input")
    output_port = next(port for port in ports if port["direction"] == "output")
    graph = resolve_v2({
        "format_version": 2, "strategy_id": "v2-runtime-bridge",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "V2 runtime bridge",
                     "description": None, "tags": []},
        "graph_inputs": [input_port], "graph_outputs": [output_port],
        "nodes": [{"node_id": "probe", "component": {
            "component_id": key[0], "component_version": key[1],
        }, "parameters": {"window": 2}}],
        "edges": [
            {"edge_id": "input", "source": {"scope": "graph_input", "port_id": "frame"},
             "target": {"scope": "node", "node_id": "probe", "port_id": "frame"},
             "binding": {"kind": "single"}},
            {"edge_id": "output", "source": {"scope": "node", "node_id": "probe", "port_id": "value"},
             "target": {"scope": "graph_output", "port_id": "value"},
             "binding": {"kind": "single"}},
        ],
    }, registry)
    index = pd.date_range("2026-01-01T00:00:00Z", periods=4, freq="min")
    inputs = {"frame": {"close": pd.Series(prices, index=index)}}
    dataset = _dataset_inputs(length=4, inputs=inputs)
    fact = {
        "schema": "canonical-input-binding/1", "owner_id": "owner-a",
        "dataset_context_address": content_address({"fixture": "dataset-context"}),
        "evaluation_context_address": content_address({"fixture": "evaluation-context"}),
        "dataset_manifest_address": dataset.manifest.manifest_address,
        "market_truth_address": dataset.manifest.truth_snapshot_addresses[0],
        "provider_product_address": dataset.manifest.provider_product_addresses[0],
        "provider_contract_address": dataset.manifest.provider_contract_addresses[0],
        "canonical_instrument_address": dataset.manifest.instrument_addresses[0],
        "instrument": {"role": "primary", "type": "PHYSICAL"},
        "timeframe": 60, "fields": ["CLOSE"],
        "freshness": {"maximum_age_seconds": 0},
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False,
    }
    bindings = canonical_input_bindings(
        owner_id="owner-a", dataset_context_address=fact["dataset_context_address"],
        evaluation_context_address=fact["evaluation_context_address"],
        bindings={"frame": fact},
        expected_source_addresses={"frame": content_address(fact)},
    )
    data_plan = compile_data_requirement_plan(
        graph, registry=registry, input_bindings=bindings,
    )
    plan = accept_research_resource_plan(
        graph, data_plan, registry, input_bindings=bindings,
    )
    policy = _policy(graph, registry, plan, dataset, maximum_events=4)
    result = execute_research(graph, registry, plan, dataset, policy)
    assert result.document["event_count"] == 4
    assert result.batch_output_document == result.incremental_output_document
    assert result.batch_outputs["value"].index.equals(index)
    assert result.batch_outputs["value"].iloc[-1].value == pytest.approx(expected)
    assert execute_research(graph, registry, plan, dataset, policy).result_address \
        == result.result_address
    cancelled = execute_research(
        graph, registry, plan, dataset, policy,
        cancellation=CancellationToken(cancel_after_events=2),
    )
    assert cancelled.document["status"] == "CANCELLED"
    assert cancelled.document["event_count"] == 2
    assert inputs["frame"]["close"].tolist() == prices

    future_index = index.append(pd.DatetimeIndex([index[-1] + pd.Timedelta(minutes=1)]))
    future_inputs = {"frame": {"close": pd.Series(
        [*prices, prices[-1] + 1000.0], index=future_index,
    )}}
    future = evaluate_incremental_v2(
        graph, future_inputs, registry, plan, event_kind="completed_bar",
        maximum_events=5,
        evaluation_context_resolver=lambda node, assembled: {
            "bound_contract": __import__(
                "app.ir.first_party.analytical_v2.contracts", fromlist=["ResolvedNodeContract"]
            ).ResolvedNodeContract(
                data_plan.parameter_binding_provenance[0]["node_contract_binding"],
                data_plan.parameter_binding_provenance[0]["node_contract_binding"]["bound_contract_address"],
            )
        },
    )
    assert future.outputs["value"].iloc[:4].equals(result.incremental_outputs["value"])


@pytest.mark.parametrize('codec', [
    'strategy-os-observation-candle-index/1',
    'strategy-os-observation-candle-index/2',
])
@pytest.mark.parametrize('offset,accepted', [(0, True), (-1, False), (172800, False)])
def test_observation_clock_authority_uses_availability_window(codec, offset, accepted):
    from research.evaluation.phase5_runtime import _verify_input_window, ResearchExecutionRefusal

    graph, registry = _runtime_shell()
    start = pd.Timestamp('2026-01-02T00:00:00Z')
    index = pd.DatetimeIndex([start + pd.Timedelta(seconds=offset)])
    dataset = SimpleNamespace(
        source_codec=codec,
        input_bindings=SimpleNamespace(document={'inputs': {'frame': {'binding': {'timeframe': 86400}}}}),
        manifest=SimpleNamespace(
            event_start='2026-01-01T00:00:00Z', event_end='2026-01-03T00:00:00Z',
            availability_start=('2026-04-01T00:00:00Z' if codec.endswith('/2') else start.isoformat()),
            availability_end=('2026-04-01T00:00:01Z' if codec.endswith('/2') else (start + pd.Timedelta(days=2)).isoformat()),
        ),
        inputs={'frame': {'close': pd.Series([100.0], index=index)}},
    )
    policy = {'event_start': start.isoformat(),
              'event_end': (start + pd.Timedelta(days=2)).isoformat(),
              'maximum_events': 1}
    if accepted:
        _verify_input_window(graph, registry, dataset, policy)
    else:
        with pytest.raises(ResearchExecutionRefusal, match='timestamps escape'):
            _verify_input_window(graph, registry, dataset, policy)


@pytest.mark.parametrize('mismatch', [
    None, 'owner_id', 'mode', 'truth_snapshot_addresses', 'adjustment_policy_address',
    'missing_data_policy_address', 'alignment_policy_address', 'resource_bindings',
    'session_policy_address', 'resampling_policy_address',
])
def test_bound_dataset_policy_preserves_owner_and_evaluation_authority(mismatch):
    from research.evaluation.phase5_runtime import _verify_dataset_policy, ResearchExecutionRefusal

    manifest = SimpleNamespace(owner_id='owner-a', mode='RESEARCH',
        truth_snapshot_addresses=('truth-a',), adjustment_policy_address='adjust-a',
        missing_data_policy_address='missing-a', alignment_policy_address='align-a')
    bindings = {'frame': 'binding-a'}
    dataset = SimpleNamespace(manifest=manifest, input_bindings=bindings,
        session_policy_address='session-a', resampling_policy_address='resample-a')
    plan = SimpleNamespace(input_bindings=bindings)
    policy = {**vars(manifest), 'session_policy_address': 'session-a',
              'resampling_policy_address': 'resample-a'}
    if mismatch == 'resource_bindings':
        plan.input_bindings = {'frame': 'binding-b'}
    elif mismatch == 'mode':
        manifest.mode = 'LIVE'
    elif mismatch:
        policy[mismatch] = ('truth-b',) if mismatch == 'truth_snapshot_addresses' else 'different'
    if mismatch:
        with pytest.raises(ResearchExecutionRefusal):
            _verify_dataset_policy(dataset, plan, policy)
    else:
        _verify_dataset_policy(dataset, plan, policy)


@pytest.mark.parametrize('mismatch', [None, 'instrument', 'field', 'source', 'address', 'fields'])
def test_input_binding_refuses_unattributable_fields(mismatch):
    from research.evaluation.phase5_runtime import _verify_input_binding, ResearchExecutionRefusal

    source = {'binding_address': 'binding-a', 'binding': {'fields': ['close']}}
    dataset = SimpleNamespace(
        manifest=SimpleNamespace(instrument_addresses=('instrument-a',), fields=('close',)),
        input_bindings=SimpleNamespace(document={'inputs': {'benchmark': source}}),
    )
    binding = {'instrument_address': 'instrument-a', 'fields': ['close'],
               'binding_address': 'binding-a'}
    if mismatch == 'instrument': binding['instrument_address'] = 'instrument-b'
    elif mismatch == 'field': binding['fields'] = ['volume']
    elif mismatch == 'source': dataset.input_bindings.document['inputs'].clear()
    elif mismatch == 'address': source['binding_address'] = 'binding-b'
    elif mismatch == 'fields': source['binding']['fields'] = ['volume']
    if mismatch:
        with pytest.raises(ResearchExecutionRefusal):
            _verify_input_binding(dataset, 'benchmark', binding)
    else:
        _verify_input_binding(dataset, 'benchmark', binding)


@pytest.mark.parametrize('timeframes', [[], [0], [-1], [True], [1.5], [86400, 900], [10**30], None])
def test_retrospective_clock_refuses_unverified_or_ambiguous_timeframes(timeframes):
    from research.evaluation.phase5_runtime import _manifest_clock_window, ResearchExecutionRefusal

    bindings = None if timeframes is None else SimpleNamespace(document={'inputs': {
        str(i): {'binding': {'timeframe': value}} for i, value in enumerate(timeframes)
    }})
    dataset = SimpleNamespace(source_codec='strategy-os-observation-candle-index/2',
        input_bindings=bindings, manifest=SimpleNamespace(
            event_start='2026-01-01T00:00:00Z', event_end='2026-01-03T00:00:00Z',
            availability_start='2026-04-01T00:00:00Z', availability_end='2026-04-01T00:00:01Z'))
    with pytest.raises(ResearchExecutionRefusal, match='retrospective evaluation'):
        _manifest_clock_window(dataset)
