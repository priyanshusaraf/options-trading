"""Independent consumers; oracle/vectors sealed before product inspection."""
import copy
from decimal import Decimal
from functools import lru_cache
import hashlib,json,math,time
from pathlib import Path
import pandas as pd
import pytest
from app.ir import hashing,node_contracts
from app.ir.first_party.analytical_v2 import recursive_state as product
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract,ResolvedNodeContract
from app.ir.validity import NumericValue,ValidityState
from research_tests import test_indicator_accuracy_recursive_state_oracle as oracle
ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'.agent/runs/post-phase5-indicator-accuracy-recursive-state-assurance'
CASES=json.loads((RUN/'expected-vectors.json').read_text())
NATIVE={r['id']:r['values'] for r in json.loads((RUN/'native-vectors.json').read_text())}

def fact(name,timeframe=60):
    address=lambda tag:hashing.content_address({'independent':tag})
    return {'schema':'canonical-input-binding/1','owner_id':'assurance.independent',
            **{k:address(k) for k in ('dataset_context_address','evaluation_context_address','dataset_manifest_address','market_truth_address','provider_product_address','provider_contract_address','canonical_instrument_address')},
            'instrument':{'role':'primary','type':'PHYSICAL'},'timeframe':timeframe,
            'fields':sorted(k.upper() for k in oracle.FIELDS[name]),
            'freshness':{'maximum_age_seconds':60},'depth':{'kind':'NONE','levels':None},
            'session':'INSTRUMENT_CALENDAR','alignment':{'kind':'EXACT','maximum_skew_seconds':0},'derived_local':False}
@lru_cache(maxsize=256)
def _bound(name,params,timeframe=60):
    p=json.loads(params);f=fact(name,timeframe)
    ports={'frame':{'source':{'scope':'graph_input','port_id':'frame'},'binding':f,'binding_address':hashing.content_address(f)}}
    ctx={'schema':'node-input-binding/1','owner_id':f['owner_id'],'dataset_context_address':f['dataset_context_address'],'evaluation_context_address':f['evaluation_context_address'],'context_address':hashing.content_address(ports),'ports':ports}
    return materialize_node_contract(product.source_contract(name),product.CONTRACT_BINDINGS[product.component_key(name)],p,ctx)
def bound(name,p):return _bound(name,json.dumps(p,sort_keys=True))
def inputs(rows,index=None):
    if index is None:index=pd.date_range('2026-08-20T00:00:00Z',periods=len(rows),freq='min')
    return {'frame':{k:pd.Series([r[k] for r in rows],index=index) for k in rows[0]}}
def relation_valid(n,p):
    if n in ('KAMA','CHAIKIN_OSCILLATOR'):return p['fast_length']<p['slow_length']
    if n=='PARABOLIC_SAR':return 0<p['start']<=p['maximum'] and 0<p['increment']<=p['maximum']
    return True
def evaluate(c):
    inp=inputs(c['rows']);resets=[('DATA_GAP',) if i in c.get('breaks',[]) else () for i in range(len(c['rows']))]
    out=product.evaluate(c['name'],c['parameters'],inp,bound_contract=bound(c['name'],c['parameters']),resets=resets)
    assert set(out)=={'value'};assert out['value'].name=='value';assert out['value'].index.equals(inp['frame']['close'].index)
    return out['value'].tolist()
def compare(actual,expected):
    assert len(actual)==len(expected)
    for i,(a,e) in enumerate(zip(actual,expected)):
        assert isinstance(a,NumericValue),(i,type(a))
        assert (a.state is ValidityState.VALID)==(e is not None),(i,a,e,'mask')
        if e is None:assert a.value is None;continue
        assert math.isfinite(a.value);err=abs(a.value-e)
        assert err <= (1e-12 if e==0 else 1e-10),(i,a.value,e,err,'absolute')
        if e:assert err/abs(e)<=1e-8,(i,a.value,e,err/abs(e),'relative')

def test_sealed_oracle_is_unchanged():
    seal=json.loads((RUN/'oracle-seal.json').read_text());assert not seal['product_helpers_read']
    for p,h in seal['artifacts'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_complete_arrays(case):
    n,p=case['name'],case['parameters']
    if not relation_valid(n,p):
        with pytest.raises(node_contracts.NodeContractRefusal):product.parameters_for(n,p)
        return
    expected=json.loads((RUN/'precision-supplement.json').read_text())['replacements'].get(case['id'],case['expected'])
    compare(evaluate(case),expected)
@pytest.mark.parametrize('name',oracle.NAMES)
def test_contract_parameters_bounds_and_outputs(name):
    target=next(r['target'] for r in json.loads((ROOT/'.agent/runs/post-phase5-indicator-accuracy-correction-replan/component-matrix.json').read_text())['records'] if r['name']==name)
    assert node_contracts._plain(product.SPECS[name]['parameters'])==oracle.PARAMS[name]==target['parameters']
    assert set(product.SPECS[name]['outputs'])=={'value'};assert tuple(product.SPECS[name]['inputs'])==oracle.FIELDS[name]
    assert dict(product.parameters_for(name,{}))==oracle.parameters(name)
    for k,sp in oracle.PARAMS[name].items():
        for bad in (True,False,None,'2',float('nan'),float('inf'),sp['minimum']-1,sp['maximum']+1):
            p=oracle.parameters(name);p[k]=bad
            with pytest.raises(node_contracts.NodeContractRefusal):product.parameters_for(name,p)
        if sp['type']=='exact_integer':
            p=oracle.parameters(name);p[k]=float(sp['default'])
            with pytest.raises(node_contracts.NodeContractRefusal):product.parameters_for(name,p)
    with pytest.raises(node_contracts.NodeContractRefusal):product.parameters_for(name,{'extraneous':2})
    for point in ('minimum','default','maximum'):
        p=oracle.parameters(name,point)
        if not relation_valid(name,p):continue
        b=bound(name,p);assert b.document['resolved_contract']['warmup_history']==oracle.first_valid(name,p)
        assert dict(b.document['resolved_contract']['output_warmup'])=={'value':oracle.first_valid(name,p)}
@pytest.mark.parametrize('name',oracle.NAMES)
@pytest.mark.parametrize('point',['minimum','default','maximum'])
def test_stream_restart_and_resource_bound(name,point):
    p=oracle.parameters(name,point)
    if not relation_valid(name,p):p={k:math.nextafter(0.,1.) for k in p}
    first=oracle.first_valid(name,p);n=max(130,first+45);rows=oracle.fixture(size=n)
    idx=inputs(rows)['frame']['close'].index;b=bound(name,p);s=product.RecursiveState(name,p,b)
    out=[];max_bytes=0;max_ns=0;breaks={first+10}
    checkpoints={0,1,max(0,first-1),first,first+1,first+10,first+11,n-2}
    for i,r in enumerate(rows):
        t=time.perf_counter_ns();out.append(s.step({'frame':r},event_time=idx[i],reset_reasons=('DATA_GAP',) if i in breaks else ())['value']);max_ns=max(max_ns,time.perf_counter_ns()-t)
        if i in checkpoints:
            doc=json.loads(json.dumps(s.snapshot()));max_bytes=max(max_bytes,len(json.dumps(doc).encode()));s=product.RecursiveState.restore(name,p,b,doc)
    compare(out,oracle.expected(name,rows,p,breaks))
    profile=product.source_contract(name)['resource_profile'];assert max_bytes<=profile['state_bytes_upper_bound'];assert max_ns/1000<=profile['compute_microseconds_per_event']
    assert len(s._history)<=p.get('window',0)+1 if name=='KAMA' else not s._history
@pytest.mark.parametrize('name',oracle.NAMES)
def test_all_prefixes_and_verified_session_carry(name):
    p=oracle.parameters(name,'minimum')
    if name=='PARABOLIC_SAR':p=oracle.parameters(name)
    rows=oracle.fixture(size=40);index=pd.date_range('2026-08-20T22:00:00Z',periods=40,freq='h');exp=oracle.expected(name,rows,p)
    for size in range(1,len(rows)+1):
        compare(product.evaluate(name,p,inputs(rows[:size],index[:size]),bound_contract=bound(name,p))['value'].tolist(),exp[:size])
    # Session transitions are carried with no reset; undeclared SESSION reset must refuse.
    with pytest.raises(node_contracts.NodeContractRefusal):
        product.evaluate(name,p,inputs(rows,index),bound_contract=bound(name,p),resets=[('SESSION',) if i in (2,20) else () for i in range(40)])
@pytest.mark.parametrize('name',oracle.NAMES)
def test_invalid_types_and_exact_states(name):
    p=oracle.parameters(name);b=bound(name,p);s=product.RecursiveState(name,p,b);r=oracle.fixture(size=1)[0];idx=pd.Timestamp('2026-08-20T00:00:00Z')
    with pytest.raises(node_contracts.NodeContractRefusal):s.step({'frame':r},event_time=idx,event_kind='forming_bar')
    with pytest.raises(node_contracts.NodeContractRefusal):s.step({'peer':r},event_time=idx)
    s.step({'frame':r},event_time=idx)
    with pytest.raises(node_contracts.NodeContractRefusal):s.step({'frame':r},event_time=idx)
    missing=dict(r);del missing[oracle.FIELDS[name][0]]
    with pytest.raises(node_contracts.NodeContractRefusal):s.step({'frame':missing},event_time=idx+pd.Timedelta(minutes=1))
    r[oracle.FIELDS[name][0]]=float('nan');y=s.step({'frame':r},event_time=idx+pd.Timedelta(minutes=2))['value'];assert y.state is not ValidityState.VALID and y.value is None
    doc=s.snapshot();assert doc['seen']==0
    for field,value in [('bound_contract_address','sha256:'+'0'*64),('seen',-1),('long',1),('numbers',{}),('payload_address','sha256:'+'0'*64)]:
        changed=copy.deepcopy(doc);changed[field]=value
        with pytest.raises(node_contracts.NodeContractRefusal):product.RecursiveState.restore(name,p,b,changed)

def through_runtime(name,p,data,*,change_bound=None):
    from app.ir.registry import PlatformRegistry
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
    from app.market_data.requirements import compile_data_requirement_plan,verify_data_requirement_plan
    key=product.component_key(name)
    registry=PlatformRegistry(components={},bodies={},registrations={},v2_types=product.V2_TYPES,
        v2_components={key:product.V2_COMPONENTS[key]},node_contracts={key:product.NODE_CONTRACTS[key]},
        contract_bindings={key:product.CONTRACT_BINDINGS[key]},v2_implementations={key:product.V2_IMPLEMENTATIONS[key]})
    ports=node_contracts._plain(product.V2_COMPONENTS[key]['ports']);ins=[x for x in ports if x['direction']=='input'];outs=[x for x in ports if x['direction']=='output']
    doc={'format_version':2,'strategy_id':'independent-recursive-proof','strategy_version':1,
         'metadata':{'metadata_version':1,'name':'Independent recurrence proof','description':None,'tags':[]},
         'graph_inputs':ins,'graph_outputs':outs,'nodes':[{'node_id':'n','component':{'component_id':key[0],'component_version':2},'parameters':p}],
         'edges':[{'edge_id':'input','source':{'scope':'graph_input','port_id':'frame'},'target':{'scope':'node','node_id':'n','port_id':'frame'},'binding':{'kind':'single'}},
                  {'edge_id':'output','source':{'scope':'node','node_id':'n','port_id':'value'},'target':{'scope':'graph_output','port_id':'value'},'binding':{'kind':'single'}}]}
    f=fact(name);ctx=canonical_input_bindings(owner_id=f['owner_id'],dataset_context_address=f['dataset_context_address'],evaluation_context_address=f['evaluation_context_address'],bindings={'frame':f},expected_source_addresses={'frame':hashing.content_address(f)})
    g=resolve_v2(doc,registry);plan=compile_data_requirement_plan(g,registry=registry,input_bindings=ctx);verify_data_requirement_plan(plan,g,registry=registry,input_bindings=ctx)
    receipt=node_contracts._plain(plan.parameter_binding_provenance[0]['node_contract_binding'])
    if change_bound:change_bound(receipt)
    b=ResolvedNodeContract(receipt,receipt['bound_contract_address'])
    result=evaluate_v2(g,data,registry,evaluation_context_resolver=lambda n,inp:{'bound_contract':b})
    return result,receipt,g

@pytest.mark.parametrize('name',oracle.NAMES)
@pytest.mark.parametrize('point',['minimum','default','maximum'])
def test_actual_resolver_compiler_runtime(name,point):
    p=oracle.parameters(name,point)
    if not relation_valid(name,p):p={k:math.nextafter(0.,1.) for k in p}
    rows=oracle.fixture(size=max(40,oracle.first_valid(name,p)+3));out,receipt,g=through_runtime(name,p,inputs(rows))
    assert set(out)=={'value'};compare(out['value'].tolist(),oracle.expected(name,rows,p))
    assert receipt['resolved_contract']['warmup_history']==oracle.first_valid(name,p)
    canonical=receipt['parameters'];assert dict(g.nodes[0].parameters)==canonical
    assert hashing.content_address(canonical)==hashing.content_address(dict(g.nodes[0].parameters))

@pytest.mark.parametrize('name',oracle.NAMES)
def test_forged_binding_rejected_by_actual_runtime(name):
    p=oracle.parameters(name);data=inputs(oracle.fixture(size=40))
    def forge(d):
        d['resolved_contract']['warmup_history']=0
        d['resolved_contract']['output_warmup']['value']=0
        d['bound_contract_address']=hashing.content_address({k:v for k,v in d.items() if k!='bound_contract_address'})
    if oracle.first_valid(name,p)>0:
        with pytest.raises(node_contracts.NodeContractRefusal):through_runtime(name,p,data,change_bound=forge)
    else:
        def wrong(d):d['source_contract_address']='sha256:'+'0'*64
        with pytest.raises(node_contracts.NodeContractRefusal):through_runtime(name,p,data,change_bound=wrong)

@pytest.mark.parametrize('parameter',[0,0.,-0.,1,1.,.125])
def test_sar_canonical_parameter_bytes(parameter):
    p=dict(start=parameter,increment=parameter,maximum=1.)
    if parameter==0:
        with pytest.raises(Exception):through_runtime('PARABOLIC_SAR',p,inputs(oracle.fixture(size=5)))
        return
    out,receipt,g=through_runtime('PARABOLIC_SAR',p,inputs(oracle.fixture(size=5)))
    restored=product.RecursiveState('PARABOLIC_SAR',dict(g.nodes[0].parameters),ResolvedNodeContract(receipt,receipt['bound_contract_address']))
    doc=restored.snapshot();product.RecursiveState.restore('PARABOLIC_SAR',dict(g.nodes[0].parameters),restored.bound_contract,doc)
    other=copy.deepcopy(doc);other['parameters']['start']=int(parameter) if type(parameter) is float and parameter==1 else float(parameter)
    if hashing.content_address(other['parameters'])!=hashing.content_address(doc['parameters']):
        other['payload_address']=hashing.content_address({k:v for k,v in other.items() if k!='payload_address'})
        with pytest.raises(node_contracts.NodeContractRefusal):product.RecursiveState.restore('PARABOLIC_SAR',dict(g.nodes[0].parameters),restored.bound_contract,other)

@pytest.mark.parametrize('name',oracle.NAMES)
@pytest.mark.parametrize('constant',[0.,math.nextafter(0.,1.),1e-300,1e300,float.fromhex('0x1.fffffffffffffp+1023')])
def test_extreme_constant_analytical_identities(name,constant):
    p=oracle.parameters(name);rows=[dict(close=constant,high=constant,low=constant,volume=1.) for _ in range(40)]
    first=oracle.first_valid(name,p);target=1. if name=='OBV' else constant if name in ('EMA','RMA_WILDER','KAMA','PARABOLIC_SAR') else 0.
    exp=[None if i<first else target for i in range(len(rows))]
    if constant==0 and name in ('NATR','CUMULATIVE_RETURN'):exp=[None]*40
    if constant==0 and name=='PRICE_VOLUME_TREND':exp=[0.]+[None]*39
    c=dict(name=name,parameters=p,rows=rows);compare(evaluate(c),exp)

@pytest.mark.parametrize('name',oracle.NAMES)
def test_intermediate_seed_trace(name):
    trace=json.loads((RUN/'intermediate-seeds.json').read_text())[name];p=trace['parameters']
    if not relation_valid(name,p):
        p=oracle.parameters(name);trace={'parameters':p,'trace':[]}
        oracle.segment(name,oracle.fixture(size=20),p,trace['trace'])
    rows=oracle.fixture(size=20);s=product.RecursiveState(name,p,bound(name,p));idx=inputs(rows)['frame']['close'].index
    aliases={'ema':'mean','kama':'mean','next_sar':'sar'}
    for i,r in enumerate(rows):
        y=s.step({'frame':r},event_time=idx[i])['value'];compare([y],[trace['trace'][i]['value']])
        doc=s.snapshot()
        for k,v in trace['trace'][i]['state'].items():
            if v=='None':continue
            if k=='long':assert doc['long']==(v=='True');continue
            key=aliases.get(k,k)
            if key not in doc['numbers']:continue
            expected=Decimal(v);actual=Decimal(doc['numbers'][key]);err=abs(actual-expected)
            assert err<=Decimal('1e-10'),(name,i,k,err)
            if expected:assert err/abs(expected)<=Decimal('1e-8')

@pytest.mark.parametrize('case',[c for c in CASES if c['id'].endswith(('zero','zero_close','nonfinite','invalid_range','negative_volume','gaps'))],ids=lambda c:c['id'])
def test_complete_validity_state_masks(case):
    p=case['parameters'];name=case['name'];got=evaluate(case);since=0;first=oracle.first_valid(name,p)
    for i,(r,a,e) in enumerate(zip(case['rows'],got,case['expected'])):
        bad=any(not math.isfinite(r[k]) for k in oracle.FIELDS[name])
        if 'high' in oracle.FIELDS[name]:bad=bad or r['low']>r['high']
        if 'volume' in oracle.FIELDS[name]:bad=bad or r['volume']<0
        if i in case.get('breaks',[]):since=0
        if bad:state=ValidityState.INVALID;since=0
        else:
            state=ValidityState.INSUFFICIENT_HISTORY if since<first else ValidityState.MATHEMATICALLY_UNDEFINED if e is None else ValidityState.VALID
            since+=1
        assert a.state is state,(name,i,a,state)

@pytest.mark.parametrize('name',oracle.NAMES)
def test_missing_stale_invalid_cells_and_index_guards(name):
    p=oracle.parameters(name);f=oracle.FIELDS[name][0];r=oracle.fixture(size=1)[0];b=bound(name,p)
    for value,state in [(None,ValidityState.MISSING),(True,ValidityState.INVALID),('abc',ValidityState.INVALID),(NumericValue(ValidityState.STALE),ValidityState.STALE)]:
        s=product.RecursiveState(name,p,b);row=dict(r);row[f]=value
        assert s.step({'frame':row},event_time=pd.Timestamp('2026-08-20T00:00:00Z'))['value'].state is state
    rows=oracle.fixture(size=5);data=inputs(rows);data['frame'][f]=data['frame'][f].set_axis(pd.date_range('2026-08-20',periods=5,freq='min'))
    with pytest.raises(node_contracts.NodeContractRefusal):product.evaluate(name,p,data,bound_contract=b)
    data=inputs(rows);data['frame'][f]=data['frame'][f].set_axis(data['frame'][f].index[::-1])
    with pytest.raises(node_contracts.NodeContractRefusal):product.evaluate(name,p,data,bound_contract=b)
    for reason in ('DATA_GAP','EXPLICIT','IDENTITY_CHANGE'):
        c=dict(name=name,parameters=p,rows=oracle.fixture(size=70));resets=[(reason,) if i==32 else () for i in range(70)]
        out=product.evaluate(name,p,inputs(c['rows']),bound_contract=b,resets=resets)['value'].tolist()
        compare(out,oracle.expected(name,c['rows'],p,[32]))

def test_long_near_equal_adosc_independent_reference():
    c=json.loads((RUN/'long-adosc-reference.json').read_text());compare(evaluate(c),c['expected'])

def test_measured_resources_are_within_declared_bounds():
    rows=json.loads((RUN/'resource-measurements.json').read_text())
    assert {(r['component'],r['point']) for r in rows}=={(n,p) for n in oracle.NAMES for p in ('minimum','default','maximum')}
    assert all(r['passed'] for r in rows)

@pytest.mark.parametrize('name',oracle.NAMES)
def test_bound_identity_timeframe_and_required_fields(name):
    p=oracle.parameters(name);b=bound(name,p)
    for field,value in [('instrument',{'role':'peer','type':'PHYSICAL'}),('alignment',{'kind':'EXACT','maximum_skew_seconds':1}),('fields',[])]:
        d=node_contracts._plain(b.document);d['input_binding']['ports']['frame']['binding'][field]=value
        d['bound_contract_address']=hashing.content_address({k:v for k,v in d.items() if k!='bound_contract_address'})
        with pytest.raises(node_contracts.NodeContractRefusal):product.RecursiveState(name,p,ResolvedNodeContract(d,d['bound_contract_address']))
    s=product.RecursiveState(name,p,b);s.step({'frame':oracle.fixture(size=1)[0]},event_time=pd.Timestamp('2026-08-20T00:00:00Z'));doc=s.snapshot()
    changed=_bound(name,json.dumps(p,sort_keys=True),300)
    assert changed.bound_contract_address!=b.bound_contract_address
    with pytest.raises(node_contracts.NodeContractRefusal):product.RecursiveState.restore(name,p,changed,doc)

@pytest.mark.parametrize('name',oracle.NAMES)
def test_caller_decimal_context_cannot_change_execution(name):
    import decimal
    p=oracle.parameters(name);c={'name':name,'parameters':p,'rows':oracle.fixture(size=40)}
    want=oracle.expected(name,c['rows'],p)
    with decimal.localcontext() as ctx:
        ctx.prec=6;ctx.rounding=decimal.ROUND_FLOOR
        compare(evaluate(c),want)

@pytest.mark.parametrize('name',['KAMA','CHAIKIN_OSCILLATOR'])
def test_length_relationships_refuse_through_actual_compiler(name):
    for f,s in [(2,2),(3,2),(4096,4096),(4096,2)]:
        p=oracle.parameters(name);p.update(fast_length=f,slow_length=s)
        with pytest.raises(node_contracts.NodeContractRefusal):product.parameters_for(name,p)
        with pytest.raises(Exception):through_runtime(name,p,inputs(oracle.fixture(size=30)))

@pytest.mark.parametrize('name',oracle.NAMES)
def test_omitted_parameters_are_resolved_to_canonical_defaults(name):
    rows=oracle.fixture(size=40);result,receipt,g=through_runtime(name,{},inputs(rows))
    assert receipt['parameters']==oracle.parameters(name)
    compare(result['value'].tolist(),oracle.expected(name,rows,oracle.parameters(name)))

@pytest.mark.parametrize('case_id',['PARABOLIC_SAR-default-large','PARABOLIC_SAR-default-offset'])
def test_sar_equal_factors_strict_native_parity_contract(case_id):
    """Accepted SAR authority explicitly promises strict TA parity at equal factors.

    Keep this RED while the promise is unsatisfied. Mathematical correctness and
    relative closeness cannot waive its unchanged absolute threshold.
    """
    case=next(c for c in CASES if c['id']==case_id)
    assert case['parameters']['start']==case['parameters']['increment']
    compare(evaluate(case),NATIVE[case_id])
