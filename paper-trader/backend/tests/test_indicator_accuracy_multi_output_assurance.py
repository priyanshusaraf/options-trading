"""Independent assurance of sealed source vectors and canonical consumers."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import multi_output as product
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract
from app.ir.validity import ValidityState

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'.agent/runs/post-phase5-indicator-accuracy-multi-output-assurance'
sp=importlib.util.spec_from_file_location('sealed_independent_multi_oracle',ROOT/'paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_oracle.py')
oracle=importlib.util.module_from_spec(sp); sp.loader.exec_module(oracle)
CASES=json.loads((OUT/'expected-math.json').read_text())
NATIVE={c['id']:c for c in json.loads((OUT/'expected-native.json').read_text())}
CASEMAP={c['id']:c for c in CASES}

def addr(x): return hashing.content_address({'assurance_fixture':x})
def bind(c,p,*,timeframe=300,role='primary',change=None):
    fact={'schema':'canonical-input-binding/1','owner_id':'independent.assurance',
          'dataset_context_address':addr('dataset'),'evaluation_context_address':addr('eval'),
          'dataset_manifest_address':addr('manifest'),'market_truth_address':addr('truth'),
          'provider_product_address':addr('mock-product'),'provider_contract_address':addr('mock-contract'),
          'canonical_instrument_address':addr('instrument'),'instrument':{'role':role,'type':'PHYSICAL'},
          'timeframe':timeframe,'fields':sorted(f.upper() for f in oracle.fields(c,p)),
          'freshness':{'maximum_age_seconds':timeframe},'depth':{'kind':'NONE','levels':None},
          'session':'INSTRUMENT_CALENDAR','alignment':{'kind':'EXACT','maximum_skew_seconds':0},'derived_local':False}
    if change: change(fact)
    ports={'frame':{'source':{'scope':'graph_input','port_id':'frame'},'binding':fact,'binding_address':hashing.content_address(fact)}}
    context={'schema':'node-input-binding/1','owner_id':fact['owner_id'],'dataset_context_address':fact['dataset_context_address'],
             'evaluation_context_address':fact['evaluation_context_address'],'context_address':hashing.content_address(ports),'ports':ports}
    key=('analytical.'+c.lower(),2)
    return materialize_node_contract(product.source_contract(c),product.CONTRACT_BINDINGS[key],p,context)

def frame(case,index=None):
    index=pd.date_range('2026-01-29T19:00:00Z',periods=len(case['data']['close']),freq='5min') if index is None else index
    return {'frame':{f:pd.Series(values,index=index,dtype=object) for f,values in case['data'].items()}}

@lru_cache(maxsize=None)
def actual(case_id):
    case=CASEMAP[case_id]
    return product.evaluate(case['component'],case['parameters'],frame(case),bound_contract=bind(case['component'],case['parameters']))

def comparison(got,expected,case):
    errors=[]; summary={}
    if set(got)!=set(expected): return {'identity_error':{'actual':sorted(got),'expected':sorted(expected)}}
    for port,wanted in expected.items():
        if len(got[port])!=len(wanted): errors.append({'port':port,'shape_error':True}); continue
        assert got[port].index.equals(frame(case)['frame']['close'].index)
        mask_errors=[]; bad=[]; max_abs=0.; max_rel=0.
        for i,(value,want) in enumerate(zip(got[port],wanted)):
            valid=value.state is ValidityState.VALID
            if valid != (want is not None): mask_errors.append({'bar':i,'actual':value.state.value,'expected_valid':want is not None}); continue
            if want is None: continue
            error=abs(value.value-want); rel=error/abs(want) if want else None
            max_abs=max(max_abs,error); max_rel=max(max_rel,rel or 0.)
            if error>(1e-12 if want==0 else 1e-10) or (rel is not None and rel>(1e-9 if case['threshold']=='NONRECURSIVE' else 1e-8)):
                bad.append({'bar':i,'actual':value.value,'expected':want,'absolute_error':error,'relative_error':rel})
        summary[port]={'maximum_absolute_error':max_abs,'maximum_relative_error':max_rel,'mask_failures':mask_errors,'value_failures':bad,'valid_bars':sum(v is not None for v in wanted)}
        if mask_errors or bad: errors.append(port)
    return {'case':case['id'],'parameters':case['parameters'],'failing_ports':errors,'ports':summary}

def excluded_combination(case):
    p=case['parameters']; return case['component'] in ('MACD','PPO') and p['fast_length']>=p['slow_length']

@pytest.mark.parametrize('case_id',list(CASEMAP))
@pytest.mark.parametrize('reference',['mathematical','native'])
def test_sealed_complete_arrays(case_id,reference):
    case=CASEMAP[case_id]
    if excluded_combination(case):
        with pytest.raises((node_contracts.NodeContractRefusal,ValueError)): actual(case_id)
        return
    expected=case['expected'] if reference=='mathematical' else NATIVE[case_id]['raw_expected']
    if reference=='mathematical':
        rational=json.loads((OUT/'expected-rational-stochrsi.json').read_text())
        if case_id in rational:
            expected=rational[case_id]
            reference='rational-adjudicated'
    report=comparison(actual(case_id),expected,case)
    directory=OUT/'comparisons'; directory.mkdir(exist_ok=True)
    (directory/f'{reference}-{case_id}.json').write_text(json.dumps(report,indent=2)+'\n')
    assert not report.get('identity_error') and not report['failing_ports'], f'{reference} {case_id}: '+str({p:{k:len(v) if isinstance(v,list) else v for k,v in r.items()} for p,r in report['ports'].items()})

def test_sealed_oracle_and_unpublished_universe():
    seal=json.loads((OUT/'expected-seal.json').read_text())
    for f,h in seal['artifacts_sha256'].items(): assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert set(product.NAMES)==set(oracle.PORTS)
    assert sum(map(len,oracle.PORTS.values()))==19
    from app.ir.library import REGISTRY, V2_CONTRIBUTORS
    assert product not in V2_CONTRIBUTORS
    for c in oracle.PORTS:
        key=('analytical.'+c.lower(),2)
        assert key not in REGISTRY.v2_components
        assert product.parameters_for(c)==oracle.DEFAULTS[c]
        assert set(product.SPECS[c]['outputs'])==set(oracle.PORTS[c])

@pytest.mark.parametrize('c',list(oracle.PORTS))
def test_parameter_domain_and_named_ports(c):
    p=oracle.DEFAULTS[c]; desc=node_contracts._plain(product.descriptor(c))
    assert set(desc['parameters'])==set(p)
    assert {v['port_id'] for vparsed in [desc['ports']] for v in vparsed if v['direction']=='output'}==set(oracle.PORTS[c])
    for key,value in p.items():
        assert desc['parameters'][key]['default']==value
        invalid=[None,True,False,{},[], 'invalid']
        if not isinstance(value,str):
            minimum=1e-6 if key in ('deviations','multiplier') else 1 if 'smoothing' in key or key=='signal_length' else 2
            maximum=20 if key in ('deviations','multiplier') else 4096
            assert desc['parameters'][key]['domain']=={'minimum':minimum,'maximum':maximum}
            invalid += [float('nan'),float('inf'),float('-inf'),minimum-1,maximum+1]
            if key not in ('deviations','multiplier'): invalid += [2.,2.5]
        for v in invalid:
            with pytest.raises((node_contracts.NodeContractRefusal,ValueError)): product.parameters_for(c,p|{key:v})
    with pytest.raises((node_contracts.NodeContractRefusal,ValueError)): product.parameters_for(c,p|{'extra':4})
    assert product.parameters_for(c,{})==p

@pytest.mark.parametrize('c',list(oracle.PORTS))
@pytest.mark.parametrize('timeframe',[60,300,3600,86400])
def test_bound_fields_roles_timeframes(c,timeframe):
    p=oracle.DEFAULTS[c]; b=bind(c,p,timeframe=timeframe)
    doc=node_contracts._plain(b.document); resolved=doc['resolved_contract']
    assert resolved['warmup_history']==oracle.first_valid(c,p)
    assert resolved['output_warmup']=={k:oracle.first_valid(c,p) for k in oracle.PORTS[c]}
    assert doc['parameters']==p
    assert doc['input_binding']['ports']['frame']['binding']['timeframe']==timeframe
    assert product.fields_by_port(c,p)['frame']==tuple(sorted(f.upper() for f in oracle.fields(c,p)))
    with pytest.raises((node_contracts.NodeContractRefusal,ValueError)):
        product.MultiOutputState(c,p,bind(c,p,role='peer'))
    with pytest.raises((node_contracts.NodeContractRefusal,ValueError)):
        product.MultiOutputState(c,p,bind(c,p,change=lambda d:d.update(fields=[])))
    with pytest.raises((node_contracts.NodeContractRefusal,ValueError)):
        product.MultiOutputState(c,p,bind(c,p,change=lambda d:d.update(alignment={'kind':'ASOF','maximum_skew_seconds':1})))

@pytest.mark.parametrize('c',list(oracle.PORTS))
def test_missing_nonfinite_and_refusal_states(c):
    case=CASEMAP[c+'-default-noisy']; p=case['parameters']; start=oracle.first_valid(c,p)+3
    f=oracle.fields(c,p)[0]
    for value,state in [(None,ValidityState.MISSING),(float('nan'),ValidityState.INVALID),(float('inf'),ValidityState.INVALID),(-float('inf'),ValidityState.INVALID)]:
        d=frame(case); d['frame'][f].iloc[start]=value
        result=product.evaluate(c,p,d,bound_contract=bind(c,p))
        for port in oracle.PORTS[c]:
            assert result[port].iloc[start].state is state
            assert all(v.state is ValidityState.INSUFFICIENT_HISTORY for v in result[port].iloc[start+1:start+1+oracle.first_valid(c,p)])
    d=frame(case); del d['frame'][f]
    with pytest.raises(node_contracts.NodeContractRefusal): product.evaluate(c,p,d,bound_contract=bind(c,p))
    d=frame(case); d['frame'][f].index=d['frame'][f].index+pd.Timedelta(seconds=1)
    if len(oracle.fields(c,p))>1:
        with pytest.raises(node_contracts.NodeContractRefusal): product.evaluate(c,p,d,bound_contract=bind(c,p))
    else:
        shifted=product.evaluate(c,p,d,bound_contract=bind(c,p))
        assert all(v.index.equals(d['frame'][f].index) for v in shifted.values())

@pytest.mark.parametrize('c',list(oracle.PORTS))
def test_causal_prefix_and_restart_sessions(c):
    case=CASEMAP[c+'-default-missing']; p=case['parameters']; b=bind(c,p); d=frame(case); baseline=actual(case['id'])
    boundaries=sorted({1,oracle.first_valid(c,p),oracle.first_valid(c,p)+1,48,94,140,170})
    for size in boundaries:
        small={'frame':{k:v.iloc[:size] for k,v in d['frame'].items()}}
        got=product.evaluate(c,p,small,bound_contract=b)
        for port in oracle.PORTS[c]: assert got[port].tolist()==baseline[port].iloc[:size].tolist()
    state=product.MultiOutputState(c,p,b); outputs={port:[] for port in oracle.PORTS[c]}
    for i,t in enumerate(d['frame']['close'].index):
        row={'frame':{f:series.iloc[i] for f,series in d['frame'].items()}}
        got=state.step(row,event_time=t)
        for port in outputs: outputs[port].append(got[port])
        if i in boundaries:
            state=product.MultiOutputState.restore(c,p,b,json.loads(json.dumps(state.snapshot())))
    for port in outputs: assert outputs[port]==baseline[port].tolist()
    # Civil-date/short-session/holiday labels do not reset math; only canonical resets do.
    index=list(d['frame']['close'].index)
    for i in range(70,len(index)): index[i]+=pd.Timedelta(days=4)
    carried=product.evaluate(c,p,frame(case,pd.DatetimeIndex(index)),bound_contract=b)
    for port in outputs: assert carried[port].tolist()==baseline[port].tolist()
    for reason in ('DATA_GAP','EXPLICIT','IDENTITY_CHANGE'):
        reset_at=80; resets=[()]*len(index); resets[reset_at]=(reason,)
        reset=product.evaluate(c,p,d,bound_contract=b,resets=resets)
        tail={'frame':{k:v.iloc[reset_at:] for k,v in d['frame'].items()}}
        cold=product.evaluate(c,p,tail,bound_contract=b)
        for port in outputs: assert reset[port].iloc[reset_at:].tolist()==cold[port].tolist()
    snap=state.snapshot()
    with pytest.raises(node_contracts.NodeContractRefusal): product.MultiOutputState.restore(c,p,bind(c,p,timeframe=3600),snap)
    with pytest.raises(node_contracts.NodeContractRefusal): state.step(row,event_time=t)
    with pytest.raises(node_contracts.NodeContractRefusal): state.step(row,event_time=t+pd.Timedelta(minutes=5),event_kind='forming_bar')

def through_consumer(case,mutate=None,defaults=False,include_resource=False):
    from app.ir.registry import PlatformRegistry
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings, ResolvedNodeContract
    from app.market_data.requirements import compile_data_requirement_plan,verify_data_requirement_plan
    c=case['component']; p=case['parameters']; key=('analytical.'+c.lower(),2)
    registry=PlatformRegistry(components={},bodies={},registrations={},v2_types=product.V2_TYPES,v2_components={key:product.V2_COMPONENTS[key]},node_contracts={key:product.NODE_CONTRACTS[key]},contract_bindings={key:product.CONTRACT_BINDINGS[key]},v2_implementations={key:product.V2_IMPLEMENTATIONS[key]})
    ports=node_contracts._plain(product.V2_COMPONENTS[key]['ports'])
    doc={'format_version':2,'strategy_id':'independent-numerical-assurance','strategy_version':1,'metadata':{'metadata_version':1,'name':'Independent assurance','description':None,'tags':[]},
         'graph_inputs':[v for v in ports if v['direction']=='input'],'graph_outputs':[v for v in ports if v['direction']=='output'],
         'nodes':[{'node_id':'indicator','component':{'component_id':key[0],'component_version':2},'parameters':{} if defaults else p}],
         'edges':[{'edge_id':'input','source':{'scope':'graph_input','port_id':'frame'},'target':{'scope':'node','node_id':'indicator','port_id':'frame'},'binding':{'kind':'single'}}]+[{'edge_id':'out_'+port,'source':{'scope':'node','node_id':'indicator','port_id':port},'target':{'scope':'graph_output','port_id':port},'binding':{'kind':'single'}} for port in oracle.PORTS[c]]}
    fact=node_contracts._plain(bind(c,p).document['input_binding']['ports']['frame']['binding'])
    context=canonical_input_bindings(owner_id=fact['owner_id'],dataset_context_address=fact['dataset_context_address'],evaluation_context_address=fact['evaluation_context_address'],bindings={'frame':fact},expected_source_addresses={'frame':hashing.content_address(fact)})
    graph=resolve_v2(doc,registry); plan=compile_data_requirement_plan(graph,registry=registry,input_bindings=context); verify_data_requirement_plan(plan,graph,registry=registry,input_bindings=context)
    if include_resource:
        from app.ir.resource_plan import compile_resource_plan
        resource=compile_resource_plan(graph,plan,registry)
        assert resource.document['schema']=='resource-plan/1'
    receipt=node_contracts._plain(plan.parameter_binding_provenance[0]['node_contract_binding'])
    if mutate:
        mutate(receipt); receipt['bound_contract_address']=hashing.content_address({k:v for k,v in receipt.items() if k!='bound_contract_address'})
    bound=ResolvedNodeContract(receipt,receipt['bound_contract_address'])
    result=evaluate_v2(graph,frame(case),registry,evaluation_context_resolver=lambda node,inputs:{'bound_contract':bound})
    return result,receipt

@pytest.mark.parametrize('c',list(oracle.PORTS))
def test_actual_resolver_data_plan_runtime(c):
    case=CASEMAP[c+'-default-noisy']; result,receipt=through_consumer(case,defaults=True)
    assert not comparison(result,case['expected'],case)['failing_ports']
    assert receipt['parameters']==oracle.DEFAULTS[c]

@pytest.mark.parametrize('field',['source_contract_address','binding_implementation_address','warmup','parameters','owner','timeframe','role','fields','session','output'])
def test_runtime_rejects_self_readdressed_forgery(field):
    def corrupt(d):
        if field in ('source_contract_address','binding_implementation_address'): d[field]=addr('forged')
        elif field=='warmup': d['resolved_contract']['warmup_history']=0
        elif field=='output': d['resolved_contract']['output_warmup'].pop('signal')
        elif field=='parameters': d['parameters']['source']='open'
        elif field=='owner': d['input_binding']['owner_id']='different-owner'
        else:
            fact=d['input_binding']['ports']['frame']['binding']
            if field=='role': fact['instrument']['role']='peer'
            else: fact[field]={'timeframe':60,'fields':['OPEN'],'session':'UTC_DAY'}[field]
    with pytest.raises((ValueError,node_contracts.NodeContractRefusal)):
        through_consumer(CASEMAP['MACD-default-noisy'],mutate=corrupt)

@pytest.mark.parametrize('case_id',list(json.loads((OUT/'expected-rational-stochrsi.json').read_text())))
def test_exact_rational_stochrsi_adjudication(case_id):
    expected=json.loads((OUT/'expected-rational-stochrsi.json').read_text())[case_id]
    report=comparison(actual(case_id),expected,CASEMAP[case_id])
    (OUT/'comparisons'/f'rational-{case_id}.json').write_text(json.dumps(report,indent=2)+'\n')
    assert not report['failing_ports'], str({p:(len(v['value_failures']),v['maximum_absolute_error']) for p,v in report['ports'].items()})

def test_runtime_stochrsi_impulse_mathematical_regression():
    case=CASEMAP['STOCH_RSI-default-impulse']; expected=json.loads((OUT/'expected-rational-stochrsi.json').read_text())[case['id']]
    got,_=through_consumer(case)
    report=comparison(got,expected,case)
    (OUT/'comparisons'/'consumer-rational-STOCH_RSI-default-impulse.json').write_text(json.dumps(report,indent=2)+'\n')
    assert not report['failing_ports'], 'Real resolver/data/resource/runtime consumer violates exact constant-RSI window semantics'

@pytest.mark.parametrize('c',list(oracle.PORTS))
def test_exact_zero_undefined_states(c):
    case=CASEMAP[c+'-default-zero']; got=actual(case['id']); first=oracle.first_valid(c,case['parameters'])
    state=ValidityState.MATHEMATICALLY_UNDEFINED if c in ('BOLLINGER_PERCENT_B','BOLLINGER_BANDWIDTH','PPO') else ValidityState.VALID
    for port in oracle.PORTS[c]:
        assert all(v.state is ValidityState.INSUFFICIENT_HISTORY for v in got[port].iloc[:first])
        assert all(v.state is state for v in got[port].iloc[first:])
        if state is ValidityState.VALID: assert all(v.value==0 for v in got[port].iloc[first:])

@pytest.mark.parametrize('c',list(oracle.PORTS))
def test_actual_resource_plan_graph_input_integration(c):
    through_consumer(CASEMAP[c+'-default-noisy'],include_resource=True)
