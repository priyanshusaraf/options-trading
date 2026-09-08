"""Correction regressions against immutable independently authored source vectors."""
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
import importlib.util
import hashlib
import json
import math
from pathlib import Path

import pytest

from app.ir import hashing, node_contracts, resolve
from app.ir.first_party.analytical_v2 import multi_output as product
from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings, ResolvedNodeContract
from app.ir.registry import PlatformRegistry
from app.ir.runtime import evaluate_v2
from app.market_data import requirements

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / '.agent/runs/post-phase5-indicator-accuracy-multi-output-correction'
spec = importlib.util.spec_from_file_location('preserved_multi_assurance_helpers', ROOT / 'paper-trader/backend/tests/test_indicator_accuracy_multi_output_assurance.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def encode(value):
    if is_dataclass(value):
        return {'dataclass': type(value).__name__, 'fields': {f.name: encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, Mapping):
        return {'mapping': [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, tuple):
        return {'tuple': [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if 'dataclass' in value:
        classes = {name: getattr(resolve, name) for name in ('ResolvedV2Graph', 'ResolvedV2Node', 'ResolvedV2Member', 'ResolvedV2Bundle')}
        classes['DataRequirementPlan'] = requirements.DataRequirementPlan
        return classes[value['dataclass']](**{k: decode(v) for k, v in value['fields'].items()})
    if 'mapping' in value:
        return {decode(k): decode(v) for k, v in value['mapping']}
    return tuple(decode(v) for v in value['tuple'])


def consumer(case, *, receipt=None):
    c, p = case['component'], case['parameters']
    key = product.component_key(c)
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=product.V2_TYPES,
        v2_components={key: product.V2_COMPONENTS[key]}, node_contracts={key: product.NODE_CONTRACTS[key]},
        contract_bindings={key: product.CONTRACT_BINDINGS[key]}, v2_implementations={key: product.V2_IMPLEMENTATIONS[key]})
    ports = node_contracts._plain(product.V2_COMPONENTS[key]['ports'])
    document = {'format_version': 2, 'strategy_id': 'multi-output-correction', 'strategy_version': 1,
        'metadata': {'metadata_version': 1, 'name': 'Correction fixture', 'description': None, 'tags': []},
        'graph_inputs': [v for v in ports if v['direction'] == 'input'],
        'graph_outputs': [v for v in ports if v['direction'] == 'output'],
        'nodes': [{'node_id': 'indicator', 'component': {'component_id': key[0], 'component_version': 2}, 'parameters': p}],
        'edges': [{'edge_id': 'input', 'source': {'scope': 'graph_input', 'port_id': 'frame'},
                   'target': {'scope': 'node', 'node_id': 'indicator', 'port_id': 'frame'}, 'binding': {'kind': 'single'}}]
        + [{'edge_id': 'out_' + port, 'source': {'scope': 'node', 'node_id': 'indicator', 'port_id': port},
            'target': {'scope': 'graph_output', 'port_id': port}, 'binding': {'kind': 'single'}} for port in h.oracle.PORTS[c]]}
    fact = node_contracts._plain(h.bind(c, p).document['input_binding']['ports']['frame']['binding'])
    context = canonical_input_bindings(owner_id=fact['owner_id'], dataset_context_address=fact['dataset_context_address'],
        evaluation_context_address=fact['evaluation_context_address'], bindings={'frame': fact},
        expected_source_addresses={'frame': hashing.content_address(fact)})
    graph = resolve.resolve_v2(document, registry)
    plan = requirements.compile_data_requirement_plan(graph, registry=registry, input_bindings=context)
    requirements.verify_data_requirement_plan(plan, graph, registry=registry, input_bindings=context)
    receipt = receipt or node_contracts._plain(plan.parameter_binding_provenance[0]['node_contract_binding'])
    bound = ResolvedNodeContract(receipt, receipt['bound_contract_address'])
    result = evaluate_v2(graph, h.frame(case), registry, evaluation_context_resolver=lambda node, inputs: {'bound_contract': bound})
    return {'registry': registry, 'authored': document, 'context': context, 'graph': graph, 'plan': plan, 'receipt': receipt, 'bound': bound, 'result': result}


def test_stochrsi_exact_ratio_regression():
    case = h.CASEMAP['STOCH_RSI-default-impulse']
    expected = json.loads((h.OUT / 'expected-rational-stochrsi.json').read_text())[case['id']]
    got = consumer(case)['result']
    report = h.comparison(got, expected, case)
    assert not report['failing_ports'], report


@pytest.mark.parametrize('name', product.NAMES)
def test_genuine_old_consumers_refuse_and_current_consumers_succeed(name):
    saved = json.loads((RUN / 'before' / (name + '.json')).read_text())
    current = consumer(h.CASEMAP[saved['case_id']])
    old_plan, old_graph = decode(saved['plan']), decode(saved['graph'])
    with pytest.raises(requirements.DataRequirementRefusal):
        requirements.verify_data_requirement_plan(old_plan, current['graph'], registry=current['registry'], input_bindings=current['context'])
    with pytest.raises(requirements.DataRequirementRefusal):
        requirements.compile_data_requirement_plan(old_graph, registry=current['registry'], input_bindings=current['context'])
    with pytest.raises((ValueError, node_contracts.NodeContractRefusal)):
        consumer(h.CASEMAP[saved['case_id']], receipt=saved['receipt'])
    old_bound = ResolvedNodeContract(saved['receipt'], saved['receipt']['bound_contract_address'])
    with pytest.raises((ValueError, node_contracts.NodeContractRefusal)):
        product.MultiOutputState(name, saved['receipt']['parameters'], old_bound)
    for snapshot in saved['states'].values():
        with pytest.raises(node_contracts.NodeContractRefusal):
            product.MultiOutputState.restore(name, saved['receipt']['parameters'], current['bound'], snapshot)
    report = h.comparison(current['result'], h.CASEMAP[saved['case_id']]['expected'], h.CASEMAP[saved['case_id']])
    assert not report['failing_ports'], report


def test_exact_source_delta_and_all_defining_module_identities_move():
    before = json.loads((RUN / 'before/identities.json').read_text())
    path = RUN.parent / 'post-phase5-indicator-accuracy-multi-output-source-replan/decision.json'
    decision = json.loads(path.read_text())
    digest = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
    for name, old in before['multi'].items():
        key = product.component_key(name)
        expected = old['spec']
        if name == 'MACD':
            expected = expected | decision['corrected_target_delta']
            expected['source_addresses'] = expected['source_addresses'] + [digest]
            assert product.CONTRACT_BINDINGS[key].source_contract_address != old['source']
        else:
            assert product.CONTRACT_BINDINGS[key].source_contract_address == old['source']
        assert node_contracts._plain(product.SPECS[name]) == expected
        assert product.CONTRACT_BINDINGS[key].implementation_address != old['binding']
        assert product.V2_IMPLEMENTATIONS[key].implementation_address != old['implementation']
    from app.ir.library import REGISTRY
    from app.ir.first_party.analytical_v2 import core_math, recursive_state
    assert REGISTRY.registry_snapshot_address == before['registry']
    for label, module in [('core', core_math), ('recursive', recursive_state)]:
        for name, old in before[label].items():
            key = module.component_key(name)
            assert module.CONTRACT_BINDINGS[key].source_contract_address == old['source']
            assert module.CONTRACT_BINDINGS[key].implementation_address == old['binding']
            assert module.V2_IMPLEMENTATIONS[key].implementation_address == old['implementation']
    for name in product.NAMES:
        assert product.component_key(name) not in REGISTRY.v2_components


def ratio_case(kind, initial=(0., 7., 3.)):
    p = dict(h.oracle.DEFAULTS['STOCH_RSI'])
    if kind == 'minimum':
        p = dict(rsi_length=2, stochastic_length=2, k_smoothing=1, d_smoothing=1)
    elif kind == 'maximum':
        p = {key: 4096 for key in p}
    count = h.oracle.first_valid('STOCH_RSI', p) + 80
    values = list(initial) + [initial[-1]] * (count - len(initial))
    return {'id': 'exact-ratio-' + kind, 'component': 'STOCH_RSI', 'parameters': p,
            'data': {'close': values}, 'threshold': 'RECURSIVE'}


@pytest.mark.parametrize('kind', ['minimum', 'default', 'maximum'])
def test_constant_ratio_exact_zero_full_masks_and_restart(kind):
    case = ratio_case(kind)
    p = case['parameters']
    first = h.oracle.first_valid('STOCH_RSI', p)
    expected = {port: [None] * first + [0.] * (len(case['data']['close']) - first) for port in ('k', 'd')}
    # The gain/loss ratio is mathematically unchanged by every post-seed bar.
    data = h.frame(case)
    bound = h.bind('STOCH_RSI', p)
    state = product.MultiOutputState('STOCH_RSI', p, bound)
    outputs = {port: [] for port in expected}
    for i, time in enumerate(data['frame']['close'].index):
        result = state.step({'frame': {'close': case['data']['close'][i]}}, event_time=time)
        for port in outputs:
            outputs[port].append(result[port])
        if i in {p['rsi_length'] - 1, p['rsi_length'], first - 1, first, first + 40}:
            state = product.MultiOutputState.restore('STOCH_RSI', p, bound, json.loads(json.dumps(state.snapshot())))
    got = {port: h.pd.Series(cells, index=data['frame']['close'].index) for port, cells in outputs.items()}
    assert not h.comparison(got, expected, case)['failing_ports']
    assert all(cell.value == 0. for cells in got.values() for cell in cells if cell.state is h.ValidityState.VALID)


@pytest.mark.parametrize('direction', [-math.inf, math.inf])
@pytest.mark.parametrize('level', [3., 1e-100, 1e100])
def test_meaningful_one_ulp_movement_is_not_flat(direction, level):
    case = ratio_case('default', (0., level * 2, level))
    values = case['data']['close'][:80]
    if direction == -math.inf:
        values[50:55] = [math.nextafter(level, math.inf)] * 5
    values[55:] = [math.nextafter(level, direction)] * (len(values) - 55)
    case['data']['close'] = values
    sp = importlib.util.spec_from_file_location('sealed_fraction_adjudicator', h.OUT / 'rational_stochrsi.py')
    rational = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(rational)
    expected = rational.calculate(case)
    assert any(v is not None and v > 0 for cells in expected.values() for v in cells)
    result = consumer(case)['result']
    report = h.comparison(result, expected, case)
    assert not report['failing_ports'], report


@pytest.mark.parametrize('kind', ['minimum', 'default', 'maximum'])
def test_one_ulp_pulse_has_exact_window_support(kind):
    case = ratio_case(kind)
    p = case['parameters']
    first = h.oracle.first_valid('STOCH_RSI', p)
    change = first + 2
    width, smooth_k, smooth_d = p['stochastic_length'], p['k_smoothing'], p['d_smoothing']
    count = change + width + smooth_k + smooth_d + 3
    case['data']['close'] = [0., 7., 3.] + [3.] * (change - 3) + [math.nextafter(3., math.inf)] * (count - change)
    # A positive price change strictly raises a non-extremal RSI. With all later
    # changes zero, the stochastic numerator equals its range until the old RSI
    # leaves the window: exactly width-1 raw values of 100, then exact zero.
    raw_counts = [int(change <= i < change + width - 1) for i in range(count)]
    prefix = [0]
    for value in raw_counts:
        prefix.append(prefix[-1] + value)
    k_counts = [prefix[i + 1] - prefix[max(0, i + 1 - smooth_k)] for i in range(count)]
    k_prefix = [0]
    for value in k_counts:
        k_prefix.append(k_prefix[-1] + value)
    expected = {'k': [None if i < first else 100 * k_counts[i] / smooth_k for i in range(count)],
                'd': [None if i < first else 100 * (k_prefix[i + 1] - k_prefix[max(0, i + 1 - smooth_d)]) / (smooth_k * smooth_d) for i in range(count)]}
    data, bound = h.frame(case), h.bind('STOCH_RSI', p)
    state = product.MultiOutputState('STOCH_RSI', p, bound)
    cells = {'k': [], 'd': []}
    for i, time in enumerate(data['frame']['close'].index):
        got = state.step({'frame': {'close': case['data']['close'][i]}}, event_time=time)
        for port in cells:
            cells[port].append(got[port])
        if i in {change - 1, change, change + width - 2, change + width - 1}:
            state = product.MultiOutputState.restore('STOCH_RSI', p, bound, json.loads(json.dumps(state.snapshot())))
    got = {port: h.pd.Series(values, index=data['frame']['close'].index) for port, values in cells.items()}
    report = h.comparison(got, expected, case)
    assert not report['failing_ports'], report


@pytest.mark.parametrize('precision', [6, 28, 90])
def test_caller_decimal_context_does_not_change_correction(precision):
    import decimal
    case = h.CASEMAP['STOCH_RSI-default-noisy']
    with decimal.localcontext() as context:
        context.prec = precision
        context.rounding = decimal.ROUND_UP
        got = consumer(case)['result']
    report = h.comparison(got, case['expected'], case)
    assert not report['failing_ports'], report
