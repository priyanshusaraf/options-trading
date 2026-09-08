"""Fresh sealed math plus immutable independent baseline and actual consumers.

The prior independent harness is reused only after expected-seal.json authorship.
Its output root is redirected to this run; original oracle/native/RED files stay intact.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / '.agent/runs/post-phase5-indicator-accuracy-multi-output-correction-assurance'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


o = load('fresh_exact_oracle', ROOT / 'paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_correction_oracle.py')
h = load('immutable_independent_baseline', ROOT / 'paper-trader/backend/tests/test_indicator_accuracy_multi_output_assurance.py')
h.OUT = RUN / 'baseline-replay'
product = h.product
CASES = {p.stem: json.loads(p.read_text()) for p in sorted((RUN / 'expected').glob('*.json'))}


def adapted(case):
    return dict(case, data=case['input'], threshold='NONRECURSIVE' if case['component'] in
                ('BOLLINGER_BANDS','BOLLINGER_BANDWIDTH','BOLLINGER_PERCENT_B','DONCHIAN_CHANNELS','STOCHASTIC') else 'RECURSIVE')


def assert_arrays(result, case, tag):
    case = adapted(case)
    report = h.comparison(result, case['expected'], case)
    (RUN / 'comparisons' / (tag + '-' + case['id'] + '.json')).write_text(json.dumps(report, indent=2))
    actual = {port: [{'state': cell.state.value, 'value': cell.value} for cell in cells] for port,cells in result.items()}
    (RUN / 'actual-arrays' / (tag + '-' + case['id'] + '.json')).write_text(json.dumps(actual,allow_nan=False))
    assert not report.get('identity_error') and not report['failing_ports'], report


def test_fresh_expectation_seal_and_independent_scope():
    seal=json.loads((RUN/'expected-seal.json').read_text())
    assert hashlib.sha256((ROOT/seal['oracle_path']).read_bytes()).hexdigest()==seal['oracle_sha256']
    for path,digest in seal['artifacts_sha256'].items():assert hashlib.sha256((RUN/path).read_bytes()).hexdigest()==digest
    assert set(CASES[k]['component'] for k in CASES)==set(o.PORTS)==set(product.NAMES)
    assert sum(map(len,o.PORTS.values()))==19
    for name,p in o.DEFAULTS.items():
        assert product.parameters_for(name)==p
        assert set(product.SPECS[name]['outputs'])==set(o.PORTS[name])
        assert h.oracle.first_valid(name,p)==o.lookback(name,p)
        assert sorted(h.oracle.fields(name,p))==sorted(o.selected_fields(name,p))


@pytest.mark.parametrize('case_id', list(CASES))
def test_fresh_complete_arrays_through_actual_consumers(case_id):
    case=CASES[case_id]
    result,receipt=h.through_consumer(adapted(case))
    assert receipt['resolved_contract']['warmup_history']==o.lookback(case['component'],case['parameters'])
    assert receipt['resolved_contract']['output_warmup']==dict.fromkeys(o.PORTS[case['component']],o.lookback(case['component'],case['parameters']))
    assert_arrays(result,case,'fresh')


@pytest.mark.parametrize('name', list(o.PORTS))
def test_fresh_causal_stream_serialized_restart_and_reset(name):
    case=CASES[name+'-default-gaps'];p=case['parameters'];b=h.bind(name,p);data=h.frame(adapted(case))
    baseline=product.evaluate(name,p,data,bound_contract=b)
    points={1,o.lookback(name,p)-1,o.lookback(name,p),o.lookback(name,p)+1,59,60,61,129,130,131,200,220}
    state=product.MultiOutputState(name,p,b);actual={port:[] for port in o.PORTS[name]}
    for i,t in enumerate(data['frame']['close'].index):
        row={'frame':{f:series.iloc[i] for f,series in data['frame'].items()}}
        values=state.step(row,event_time=t)
        for port in actual:actual[port].append(values[port])
        if i in points:
            state=product.MultiOutputState.restore(name,p,b,json.loads(json.dumps(state.snapshot())))
            prefix=product.evaluate(name,p,{'frame':{f:s.iloc[:i+1] for f,s in data['frame'].items()}},bound_contract=b)
            for port in actual:assert prefix[port].tolist()==actual[port]
    for port in actual:assert actual[port]==baseline[port].tolist()
    assert_arrays(baseline,case,'stream')


@pytest.mark.parametrize('precision',[6,28,90])
def test_caller_decimal_context_cannot_change_corrected_outputs(precision):
    from decimal import localcontext,ROUND_FLOOR
    with localcontext() as context:
        context.prec=precision;context.rounding=ROUND_FLOOR
        for case_id in ['MACD-default-large','STOCH_RSI-default-impulse','STOCH_RSI-default-tiny_impulse']:
            case=CASES[case_id];result,_=h.through_consumer(adapted(case))
            assert_arrays(result,case,'context-'+str(precision))


@pytest.mark.parametrize('mutation',['schema','component','counter','history','decimal','digest','extra'])
def test_serialized_correction_state_rejects_corruption(mutation):
    name='STOCH_RSI';case=CASES[name+'-default-noisy'];p=case['parameters'];bound=h.bind(name,p)
    state=product.MultiOutputState(name,p,bound)
    for i in range(50):state.step({'frame':{'close':case['input']['close'][i]}},event_time=pd.Timestamp('2026-01-01T00:00Z')+pd.Timedelta(seconds=300*i))
    snapshot=json.loads(json.dumps(state.snapshot()))
    if mutation=='schema':snapshot['schema']='analytical-multi-output-state/1'
    elif mutation=='component':snapshot['component'][1]=1
    elif mutation=='counter':snapshot['seen']=True
    elif mutation=='history':snapshot['history']['rsi'].pop()
    elif mutation=='decimal':snapshot['numbers']['gain']='NaN'
    elif mutation=='digest':snapshot['payload_address']=h.addr('wrong-state-digest')
    else:snapshot['unrecognized']=True
    if mutation!='digest':snapshot['payload_address']=h.hashing.content_address({k:v for k,v in snapshot.items() if k!='payload_address'})
    with pytest.raises(h.node_contracts.NodeContractRefusal):product.MultiOutputState.restore(name,p,bound,snapshot)


def test_corrected_source_delta_and_preserved_accepted_identities():
    before=json.loads((RUN.parent/'post-phase5-indicator-accuracy-multi-output-correction/before/identities.json').read_text())
    decision_path=RUN.parent/'post-phase5-indicator-accuracy-multi-output-source-replan/decision.json'
    digest=hashlib.sha256(decision_path.read_bytes()).hexdigest()
    assert digest=='f954430f5b7981078faf609fba47a0754187f3923f2ae2dc596368a18c3e271a'
    decision=json.loads(decision_path.read_text())
    for name in o.PORTS:
        old=before['multi'][name];key=product.component_key(name);wanted=deepcopy(old['spec'])
        if name=='MACD':
            wanted.update(decision['corrected_target_delta']);wanted['source_addresses'].append('sha256:'+digest)
            assert product.CONTRACT_BINDINGS[key].source_contract_address!=old['source']
        else:assert product.CONTRACT_BINDINGS[key].source_contract_address==old['source']
        assert h.node_contracts._plain(product.SPECS[name])==wanted
        assert product.CONTRACT_BINDINGS[key].implementation_address!=old['binding']
        assert product.V2_IMPLEMENTATIONS[key].implementation_address!=old['implementation']
    from app.ir.library import REGISTRY
    from app.ir.first_party.analytical_v2 import core_math,recursive_state
    assert REGISTRY.registry_snapshot_address==before['registry']
    assert all(product.component_key(n) not in REGISTRY.v2_components for n in o.PORTS)
    for label,module in [('core',core_math),('recursive',recursive_state)]:
        for name,old in before[label].items():
            key=module.component_key(name)
            assert module.CONTRACT_BINDINGS[key].source_contract_address==old['source']
            assert module.CONTRACT_BINDINGS[key].implementation_address==old['binding']
            assert module.V2_IMPLEMENTATIONS[key].implementation_address==old['implementation']


def decode_saved(value):
    from app.ir import resolve
    from app.market_data.requirements import DataRequirementPlan
    if isinstance(value,list):return [decode_saved(v) for v in value]
    if not isinstance(value,dict):return value
    if 'dataclass' in value:
        classes={n:getattr(resolve,n) for n in ('ResolvedV2Graph','ResolvedV2Node','ResolvedV2Member','ResolvedV2Bundle')}
        classes['DataRequirementPlan']=DataRequirementPlan
        return classes[value['dataclass']](**{k:decode_saved(v) for k,v in value['fields'].items()})
    if 'mapping' in value:return {decode_saved(k):decode_saved(v) for k,v in value['mapping']}
    return tuple(decode_saved(v) for v in value['tuple'])


@pytest.mark.parametrize('name',list(o.PORTS))
def test_genuine_predecessor_graph_plan_receipt_and_state_refuse(name):
    from app.ir.registry import PlatformRegistry
    from app.ir.resolve import resolve_v2
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings,ResolvedNodeContract
    from app.market_data import requirements
    saved=json.loads((RUN.parent/'post-phase5-indicator-accuracy-multi-output-correction/before'/f'{name}.json').read_text())
    case=h.CASEMAP[saved['case_id']];p=case['parameters'];key=product.component_key(name)
    registry=PlatformRegistry(components={},bodies={},registrations={},v2_types=product.V2_TYPES,v2_components={key:product.V2_COMPONENTS[key]},node_contracts={key:product.NODE_CONTRACTS[key]},contract_bindings={key:product.CONTRACT_BINDINGS[key]},v2_implementations={key:product.V2_IMPLEMENTATIONS[key]})
    old_graph=decode_saved(saved['graph']);old_plan=decode_saved(saved['plan'])
    fact=h.node_contracts._plain(h.bind(name,p).document['input_binding']['ports']['frame']['binding'])
    context=canonical_input_bindings(owner_id=fact['owner_id'],dataset_context_address=fact['dataset_context_address'],evaluation_context_address=fact['evaluation_context_address'],bindings={'frame':fact},expected_source_addresses={'frame':h.hashing.content_address(fact)})
    with pytest.raises(requirements.DataRequirementRefusal):requirements.compile_data_requirement_plan(old_graph,registry=registry,input_bindings=context)
    with pytest.raises(requirements.DataRequirementRefusal):requirements.verify_data_requirement_plan(old_plan,old_graph,registry=registry,input_bindings=context)
    old_bound=ResolvedNodeContract(saved['receipt'],saved['receipt']['bound_contract_address'])
    with pytest.raises((ValueError,h.node_contracts.NodeContractRefusal)):product.evaluate(name,p,h.frame(case),bound_contract=old_bound)
    current=h.bind(name,p)
    for snapshot in saved['states'].values():
        with pytest.raises(h.node_contracts.NodeContractRefusal):product.MultiOutputState.restore(name,p,current,snapshot)
    result,_=h.through_consumer(case)
    assert not h.comparison(result,case['expected'],case)['failing_ports']


# Immutable earlier independent tests are rerun against CURRENT product bytes.
# Raw native and F03 failures remain ordinary failures, never xfail/skip/waivers.
for _name in dir(h):
    if _name.startswith('test_'):
        globals()['test_preserved_'+_name[5:]]=getattr(h,_name)


@pytest.mark.parametrize('case_id',list(h.CASEMAP))
@pytest.mark.parametrize('reference',['mathematical','native'])
def test_preserved_sealed_complete_arrays(case_id,reference):
    case=h.CASEMAP[case_id]
    if not h.excluded_combination(case):
        result=h.actual(case_id)
        payload={'case':case_id,'source_sha256':hashlib.sha256(Path(product.__file__).read_bytes()).hexdigest(),
                 'index':[x.isoformat() for x in next(iter(result.values())).index],
                 'outputs':{port:[{'state':v.state.value,'value':v.value} for v in cells] for port,cells in result.items()}}
        (RUN/'actual-arrays'/('preserved-'+case_id+'.json')).write_text(json.dumps(payload,allow_nan=False))
    h.test_sealed_complete_arrays(case_id,reference)
