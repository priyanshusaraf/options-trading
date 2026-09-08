"""Exact two-record source correction and genuine captured old/current consumers."""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / '.agent/runs/post-phase5-indicator-accuracy-multi-output-band-ppo-source-correction'
spec = importlib.util.spec_from_file_location('preserved_correction_consumers', ROOT / 'paper-trader/backend/tests/test_indicator_accuracy_multi_output_correction.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
product = t.product


@pytest.mark.parametrize('name', product.NAMES)
def test_old_consumers_refuse_and_current_arrays_state_remain_exact(name):
    saved = json.loads((RUN / 'before' / (name + '.json')).read_text())
    current = t.consumer(t.h.CASEMAP[saved['case_id']])
    old_plan, old_graph = t.decode(saved['plan']), t.decode(saved['graph'])
    with pytest.raises(t.requirements.DataRequirementRefusal):
        t.requirements.verify_data_requirement_plan(old_plan, current['graph'], registry=current['registry'], input_bindings=current['context'])
    with pytest.raises(t.requirements.DataRequirementRefusal):
        t.requirements.compile_data_requirement_plan(old_graph, registry=current['registry'], input_bindings=current['context'])
    with pytest.raises((ValueError, t.node_contracts.NodeContractRefusal)):
        t.consumer(t.h.CASEMAP[saved['case_id']], receipt=saved['receipt'])
    old_bound = t.ResolvedNodeContract(saved['receipt'], saved['receipt']['bound_contract_address'])
    with pytest.raises((ValueError, t.node_contracts.NodeContractRefusal)):
        product.MultiOutputState(name, saved['receipt']['parameters'], old_bound)
    for snapshot in saved['states'].values():
        with pytest.raises(t.node_contracts.NodeContractRefusal):
            product.MultiOutputState.restore(name, saved['receipt']['parameters'], current['bound'], snapshot)
    case = t.h.CASEMAP[saved['case_id']]
    report = t.h.comparison(current['result'], case['expected'], case)
    assert not report.get('identity_error') and not report['failing_ports'], report
    actual = {port: {'index': [v.isoformat() for v in cells.index], 'values': [v.value for v in cells],
                     'states': [v.state.value for v in cells]} for port, cells in current['result'].items()}
    assert actual == saved['runtime']
    data = t.h.frame(case)
    state = product.MultiOutputState(name, case['parameters'], current['bound'])
    for i, time in enumerate(data['frame']['close'].index):
        values = state.step({'frame': {k: v.iloc[i] for k, v in data['frame'].items()}}, event_time=time)
        assert all(values[k] == current['result'][k].iloc[i] for k in values)
        if str(i) in saved['states']:
            snapshot = json.loads(json.dumps(state.snapshot()))
            # Only identity-bearing fields may differ; all retained numerical state stays exact.
            old = saved['states'][str(i)]
            for field in old:
                if field not in {'bound_contract_address', 'payload_address'}:
                    assert snapshot[field] == old[field], field
            state = product.MultiOutputState.restore(name, case['parameters'], current['bound'], snapshot)


def test_exact_two_source_records_and_nine_identity_transitions():
    before = json.loads((RUN / 'before/identities.json').read_text())
    path = RUN.parent / 'post-phase5-indicator-accuracy-multi-output-band-ppo-source-replan/decision.json'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == '2ca3e31e074984d1545af8a0a98ea718fbaf2ad093552ec651672df8ae6213f1'
    decision = json.loads(path.read_text())
    for name, old in before['multi'].items():
        key = product.component_key(name)
        expected = deepcopy(old['spec'])
        if name in decision['corrected_target_delta']:
            expected.update(decision['corrected_target_delta'][name])
            expected['source_addresses'].append('sha256:' + digest)
            assert product.CONTRACT_BINDINGS[key].source_contract_address != old['source']
        else:
            assert product.CONTRACT_BINDINGS[key].source_contract_address == old['source']
        assert t.node_contracts._plain(product.SPECS[name]) == expected
        assert product.CONTRACT_BINDINGS[key].implementation_address != old['binding']
        assert product.V2_IMPLEMENTATIONS[key].implementation_address != old['implementation']


def test_all_function_class_bytes_and_nonmetadata_module_bytes_preserved():
    old = (RUN / 'multi_output.before.py').read_text()
    new = Path(product.__file__).read_text()
    def segments(source):
        return [ast.get_source_segment(source, n) for n in ast.walk(ast.parse(source))
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    assert segments(new) == segments(old)
    def without_specs(source):
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                    and any(isinstance(k, ast.Name) and k.id == 'SPECS' for k in n.targets))
        lines = source.splitlines(keepends=True)
        return ''.join(lines[:node.lineno-1] + lines[node.end_lineno:])
    assert without_specs(new) == without_specs(old)


def test_legacy_core_recursive_and_default_registry_remain_unpublished_exact():
    from app.ir.library import REGISTRY
    from app.ir.first_party.analytical_v2 import core_math, recursive_state
    before = json.loads((RUN / 'before/identities.json').read_text())
    assert REGISTRY.registry_snapshot_address == before['registry']
    assert all(product.component_key(n) not in REGISTRY.v2_components for n in product.NAMES)
    for label, module, count in [('core', core_math, 58), ('recursive', recursive_state, 17)]:
        assert len(before[label]) == count
        for name, old in before[label].items():
            key = module.component_key(name)
            assert module.CONTRACT_BINDINGS[key].source_contract_address == old['source']
            assert module.CONTRACT_BINDINGS[key].implementation_address == old['binding']
            assert module.V2_IMPLEMENTATIONS[key].implementation_address == old['implementation']
            assert t.node_contracts._plain(module.SPECS[name]) == old['spec']
    legacy = json.loads((RUN.parent / 'post-phase5-indicator-accuracy-correction-replan/current-catalogue.json').read_text())['records']
    assert len(legacy) == 125
    for row in legacy:
        key = (row['component_id'], row['component_version'])
        actual = {'descriptor': t.node_contracts._plain(REGISTRY.v2_components[key]),
                  'node_contract': t.node_contracts._plain(REGISTRY.node_contracts[key]),
                  'node_contract_address': REGISTRY.node_contract_addresses[key],
                  'data_requirement': t.node_contracts._plain(REGISTRY.data_requirement_declarations[key]),
                  'data_requirement_address': REGISTRY.data_requirement_declaration_addresses[key],
                  'implementation_address': REGISTRY.v2_implementation_identities[key]}
        assert all(value == row[field] for field, value in actual.items()), row['name']
