"""Independent corrected-source assurance; expectations frozen before product read."""
import hashlib
import json
import ast
import copy
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import pytest
import pandas as pd
from app.ir import node_contracts, hashing
from app.ir.first_party.analytical_v2 import recursive_state as product
from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract, canonical_input_bindings
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2, ResolutionError
from app.ir.runtime import evaluate_v2
from app.market_data.requirements import DataRequirementPlan, DataRequirementRefusal, compile_data_requirement_plan, verify_data_requirement_plan
from research_tests import test_indicator_accuracy_recursive_sar_source_oracle as exact
from tests import test_indicator_accuracy_recursive_state_assurance as prior

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / '.agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-assurance'
CASES = json.loads((RUN/'exact-vectors.json').read_text())
COR = ROOT / '.agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-correction'
OLD = json.loads((COR/'before-consumers.json').read_text())['records']
DECISION = ROOT / '.agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-replan/decision.json'

def test_exact_oracle_sealed_before_product_inspection():
    seal = json.loads((RUN/'oracle-authorship-seal.json').read_text())
    assert hashlib.sha256(Path(exact.__file__).read_bytes()).hexdigest() == seal['oracle_sha256']
    assert hashlib.sha256((RUN/'exact-vectors.json').read_bytes()).hexdigest() == seal['vectors_sha256']
    assert {c['name'] for c in CASES} == set(exact.NAMES)

@pytest.mark.parametrize('case', CASES, ids=lambda c:c['id'])
def test_exact_complete_arrays(case):
    if not prior.relation_valid(case['name'],case['parameters']):
        with pytest.raises(node_contracts.NodeContractRefusal):
            product.parameters_for(case['name'],case['parameters'])
        return
    prior.compare(prior.evaluate(case),case['expected'])

def compiled(name, parameters=None):
    return _compiled(name,json.dumps(parameters,sort_keys=True))

@lru_cache(maxsize=64)
def _compiled(name, encoded):
    """Recompile the actual old authored shape with the same canonical input facts."""
    parameters=json.loads(encoded)
    key = product.component_key(name)
    registry = PlatformRegistry(components={}, bodies={}, registrations={},
        v2_types=product.V2_TYPES, v2_components={key:product.V2_COMPONENTS[key]},
        node_contracts={key:product.NODE_CONTRACTS[key]}, contract_bindings={key:product.CONTRACT_BINDINGS[key]},
        v2_implementations={key:product.V2_IMPLEMENTATIONS[key]})
    ports = node_contracts._plain(product.V2_COMPONENTS[key]['ports'])
    doc = dict(format_version=2,strategy_id='sar-source-contract-proof',strategy_version=1,
        metadata=dict(metadata_version=1,name='Source contract proof',description=None,tags=[]),
        graph_inputs=[p for p in ports if p['direction']=='input'],graph_outputs=[p for p in ports if p['direction']=='output'],
        nodes=[dict(node_id='n',component=dict(component_id=key[0],component_version=2),parameters={} if parameters is None else parameters)],
        edges=[dict(edge_id='in',source=dict(scope='graph_input',port_id='frame'),target=dict(scope='node',node_id='n',port_id='frame'),binding=dict(kind='single')),
               dict(edge_id='out',source=dict(scope='node',node_id='n',port_id='value'),target=dict(scope='graph_output',port_id='value'),binding=dict(kind='single'))])
    old_input = OLD[name]['receipt']['input_binding']
    facts = {p:copy.deepcopy(v['binding']) for p,v in old_input['ports'].items()}
    context = canonical_input_bindings(owner_id=old_input['owner_id'],dataset_context_address=old_input['dataset_context_address'],evaluation_context_address=old_input['evaluation_context_address'],bindings=facts,expected_source_addresses={p:hashing.content_address(f) for p,f in facts.items()})
    graph = resolve_v2(doc,registry)
    plan = compile_data_requirement_plan(graph,registry=registry,input_bindings=context)
    verify_data_requirement_plan(plan,graph,registry=registry,input_bindings=context)
    receipt = node_contracts._plain(plan.parameter_binding_provenance[0]['node_contract_binding'])
    assert receipt['input_binding'] == old_input
    return graph,registry,context,plan,ResolvedNodeContract(receipt,receipt['bound_contract_address'])

def test_only_declared_metadata_changed():
    before = (COR/'recursive_state-before.py').read_text()
    after = Path(product.__file__).read_text()
    def definitions(text):
        return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    assert definitions(before) == definitions(after)
    assert len(definitions(after)) == 19
    def specs(text):
        n = next(n for n in ast.parse(text).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SPECS' for t in n.targets))
        return ast.literal_eval(n.value.args[0])
    old,new = specs(before),specs(after)
    assert set(old) == set(new) == set(exact.NAMES)
    decision = json.loads(DECISION.read_text())
    expected = copy.deepcopy(old)
    expected['PARABOLIC_SAR'].update(decision['corrected_target_delta'])
    expected['PARABOLIC_SAR']['source_addresses'] += ('sha256:'+hashlib.sha256(DECISION.read_bytes()).hexdigest(),)
    assert expected == new
    for text in (before,after):
        assert 'prec=1536' in text

@pytest.mark.parametrize('name',exact.NAMES)
def test_source_and_transitive_identity_change(name):
    key = product.component_key(name)
    current = node_contracts._plain(product.source_contract(name))
    old = OLD[name]
    assert (product.CONTRACT_BINDINGS[key].source_contract_address != old['source_address']) == (name=='PARABOLIC_SAR')
    assert product.CONTRACT_BINDINGS[key].implementation_address != old['binding_identity']
    assert product.V2_IMPLEMENTATIONS[key].implementation_address != old['implementation_identity']
    if name=='PARABOLIC_SAR':
        assert {k:v for k,v in current.items() if k!='reference_provenance'} == {k:v for k,v in old['source_contract'].items() if k!='reference_provenance'}
        assert 'sha256:'+hashlib.sha256(DECISION.read_bytes()).hexdigest() in current['reference_provenance']
    else:
        assert current == old['source_contract']

@pytest.mark.parametrize('name',exact.NAMES)
@pytest.mark.parametrize('consumer',['plan','runtime','state'])
def test_actual_old_consumers_refuse(name,consumer):
    graph,registry,context,plan,bound = compiled(name)
    old = OLD[name]
    receipt = old['receipt']
    assert receipt['bound_contract_address'] == hashing.content_address({k:v for k,v in receipt.items() if k!='bound_contract_address'})
    assert old['snapshot']['payload_address'] == hashing.content_address({k:v for k,v in old['snapshot'].items() if k!='payload_address'})
    assert plan.authored_ir_address == old['plan']['authored_ir_address']
    assert receipt['bound_contract_address'] != bound.bound_contract_address
    if consumer=='plan':
        with pytest.raises(DataRequirementRefusal):
            verify_data_requirement_plan(DataRequirementPlan(**copy.deepcopy(old['plan'])),graph,registry=registry,input_bindings=context)
    elif consumer=='runtime':
        old_bound = ResolvedNodeContract(copy.deepcopy(receipt),receipt['bound_contract_address'])
        with pytest.raises(node_contracts.NodeContractRefusal):
            evaluate_v2(graph,prior.inputs(exact.original.fixture(size=40)),registry,evaluation_context_resolver=lambda *_:{'bound_contract':old_bound})
    else:
        with pytest.raises(node_contracts.NodeContractRefusal):
            product.RecursiveState.restore(name,old['parameters'],bound,copy.deepcopy(old['snapshot']))

@pytest.mark.parametrize('name',exact.NAMES)
def test_new_canonical_consumers_and_serialized_restart(name):
    c = next(c for c in CASES if c['id']==f'exact-{name}-mixed')
    graph,registry,context,plan,bound = compiled(name)
    inputs = prior.inputs(c['rows'])
    result = evaluate_v2(graph,inputs,registry,evaluation_context_resolver=lambda *_:{'bound_contract':bound})
    assert set(result) == {'value'}
    prior.compare(result['value'].tolist(),c['expected'])
    state = product.RecursiveState(name,c['parameters'],bound)
    actual = []
    first = exact.original.first_valid(name,c['parameters'])
    for i,r in enumerate(c['rows']):
        actual.append(state.step({'frame':r},event_time=inputs['frame']['close'].index[i])['value'])
        if i in {0,first-1,first,first+1,31,32,62}:
            snapshot=json.loads(json.dumps(state.snapshot(),allow_nan=False))
            state=product.RecursiveState.restore(name,c['parameters'],bound,snapshot)
            assert state.snapshot()==snapshot
    prior.compare(actual,c['expected'])

def test_legacy_core_and_default_registry_are_unchanged():
    from app.ir.library import REGISTRY,V2_CONTRIBUTORS
    from app.ir.first_party.analytical_v2 import core_math
    legacy=json.loads((ROOT/'.agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json').read_text())['records']
    assert len(legacy)==125
    for row in legacy:
        key=(row['component_id'],row['component_version'])
        current=dict(descriptor=node_contracts._plain(REGISTRY.v2_components[key]),node_contract=node_contracts._plain(REGISTRY.node_contracts[key]),
            node_contract_address=REGISTRY.node_contract_addresses[key],data_requirement=node_contracts._plain(REGISTRY.data_requirement_declarations[key]),
            data_requirement_address=REGISTRY.data_requirement_declaration_addresses[key],implementation_address=REGISTRY.v2_implementation_identities[key])
        assert current=={k:row[k] for k in current},row['name']
    core=json.loads((ROOT/'.agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/source-proof.json').read_text())['candidates']
    assert len(core)==58
    for row in core:
        key=core_math.component_key(row['name'])
        assert core_math.CONTRACT_BINDINGS[key].source_contract_address==row['source_contract']
        assert core_math.CONTRACT_BINDINGS[key].implementation_address==row['binding']
        assert core_math.V2_IMPLEMENTATIONS[key].implementation_address==row['implementation']
    assert REGISTRY.registry_snapshot_address=='sha256:bef51d976101e495d3666fb89e3a6f0be4ea6dbe87ad7a0d4f2f1c075a9812d0'
    assert product not in V2_CONTRIBUTORS
    assert all(product.component_key(n) not in REGISTRY.v2_components for n in exact.NAMES)

def test_native_assertion_cannot_be_requested():
    with pytest.raises(ResolutionError):
        compiled('PARABOLIC_SAR',{'native_parity':True})

@pytest.mark.parametrize('case',[c for c in CASES if c['id'].startswith('exact-SAR-') and prior.relation_valid(c['name'],c['parameters'])],ids=lambda c:c['id'])
def test_sar_exact_direction_reversal_clamp_state(case):
    trace=[]
    exact.rational_segment(case['name'],case['rows'],case['parameters'],trace)
    b=prior.bound(case['name'],case['parameters'])
    s=product.RecursiveState(case['name'],case['parameters'],b)
    index=prior.inputs(case['rows'])['frame']['close'].index
    for i,row in enumerate(case['rows']):
        got=s.step({'frame':row},event_time=index[i])['value']
        prior.compare([got],[case['expected'][i]])
        if not i: continue
        want=trace[i-1]
        doc=s.snapshot()
        assert doc['long']==(want['direction']==1)
        for key in ('ep','af'):
            assert Fraction(doc['numbers'][key])==want[key],(case['id'],i,key)
        actual=float(doc['numbers']['sar']); expected=float(want['next_sar'])
        assert abs(actual-expected)<=(1e-12 if not expected else 1e-10)
        if expected: assert abs(actual-expected)/abs(expected)<=1e-8
        s=product.RecursiveState.restore(case['name'],case['parameters'],b,json.loads(json.dumps(doc)))

def test_sar_trajectory_exercises_both_directions_reversals_and_clamps():
    traces=[]
    for c in CASES:
        if c['id'].startswith('exact-SAR-') and prior.relation_valid(c['name'],c['parameters']):
            exact.rational_segment(c['name'],c['rows'],c['parameters'],traces)
    assert {t['direction'] for t in traces}=={-1,1}
    assert any(t['reversal'] for t in traces) and any(not t['reversal'] for t in traces)
    assert any(t['clamped'] for t in traces) and any(not t['clamped'] for t in traces)

@pytest.mark.parametrize('name',exact.NAMES)
def test_declared_session_schedule_carries_and_explicit_gap_resets(name):
    # Synthetic authoritative schedule at the node boundary, not a claim about
    # an exchange/provider calendar. Session 2 is shortened; the weekend closure
    # is explicitly scheduled. Only a missing in-session slot is a DATA_GAP.
    sessions=[('2026-08-20T23:50Z',20),('2026-08-21T23:50Z',12),('2026-08-24T23:50Z',33)]
    scheduled=[pd.Timestamp(start)+pd.Timedelta(minutes=i) for start,n in sessions for i in range(n)]
    missing=45
    events=scheduled[:missing]+scheduled[missing+1:]
    assert len(events)==64
    c=next(c for c in CASES if c['id']==f'exact-{name}-mixed')
    data=prior.inputs(c['rows'],pd.DatetimeIndex(events))
    resets=[('DATA_GAP',) if i==missing else () for i in range(64)]
    want=exact.expected(name,c['rows'],c['parameters'],breaks=[missing])
    graph,registry,context,plan,bound=compiled(name)
    out=evaluate_v2(graph,data,registry,evaluation_context_resolver=lambda *_:{'bound_contract':bound,'resets':resets})
    prior.compare(out['value'].tolist(),want)
    prior.compare(out['value'].iloc[:missing].tolist(),c['expected'][:missing])
    state=product.RecursiveState(name,c['parameters'],bound)
    values=[]
    for i,row in enumerate(c['rows']):
        values.append(state.step({'frame':row},event_time=events[i],reset_reasons=resets[i])['value'])
        if i in {19,20,31,32,44,45,46}:
            state=product.RecursiveState.restore(name,c['parameters'],bound,json.loads(json.dumps(state.snapshot())))
        if i in {19,20,31,32,44,45,46,63}:
            prefix=product.evaluate(name,c['parameters'],prior.inputs(c['rows'][:i+1],pd.DatetimeIndex(events[:i+1])),bound_contract=bound,resets=resets[:i+1])
            prior.compare(prefix['value'].tolist(),want[:i+1])
    prior.compare(values,want)
