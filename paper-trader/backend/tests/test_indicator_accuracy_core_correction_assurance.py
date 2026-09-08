"""Fresh independent extension; historical assurance is imported read-only as a harness."""
from copy import deepcopy
from decimal import localcontext, Inexact, Rounded, ROUND_UP
import json
import math
import os
from pathlib import Path

import pandas as pd
import pytest
from research_tests import test_indicator_accuracy_core_correction_oracle as fresh
from tests import test_indicator_accuracy_core_math_assurance as old
from app.ir.first_party.analytical_v2 import core_math as core
from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings, ResolvedNodeContract
from app.ir.resolve import resolve_v2
from app.ir.runtime import evaluate_v2
from app.ir.validity import ValidityState
from app.market_data.requirements import compile_data_requirement_plan, verify_data_requirement_plan


def rows(data):
    return [{field:values[i] for field,values in data.items()} for i in range(len(data['close']))]

def runtime(name, parameters, data, timeframe=300):
    registry=old.candidate_registry(name);key=('analytical.'+name.lower(),2)
    ports=old.plain(core.V2_COMPONENTS[key]['ports'])
    ins=[p for p in ports if p['direction']=='input'];outs=[p for p in ports if p['direction']=='output']
    graph={'format_version':2,'strategy_id':'fresh-correction-assurance','strategy_version':1,
           'metadata':{'metadata_version':1,'name':'Fresh correction assurance','description':None,'tags':[]},
           'graph_inputs':ins,'graph_outputs':outs,
           'nodes':[{'node_id':'subject','component':{'component_id':key[0],'component_version':2},'parameters':parameters}],
           'edges':[{'edge_id':'input-'+p['port_id'],'source':{'scope':'graph_input','port_id':p['port_id']},'target':{'scope':'node','node_id':'subject','port_id':p['port_id']},'binding':{'kind':'single'}} for p in ins]+[{'edge_id':'output-'+p['port_id'],'source':{'scope':'node','node_id':'subject','port_id':p['port_id']},'target':{'scope':'graph_output','port_id':p['port_id']},'binding':{'kind':'single'}} for p in outs]}
    resolved=resolve_v2(graph,registry)
    facts=old.input_facts(name,timeframe=timeframe)
    context=canonical_input_bindings(owner_id='assurance-owner',dataset_context_address=old.mark('dataset'),evaluation_context_address=old.mark('evaluation'),bindings=facts,expected_source_addresses={k:old.address(v) for k,v in facts.items()})
    plan=compile_data_requirement_plan(resolved,registry=registry,input_bindings=context)
    verify_data_requirement_plan(plan,resolved,registry=registry,input_bindings=context)
    receipt=plan.parameter_binding_provenance[0]['node_contract_binding'];bound=ResolvedNodeContract(receipt,receipt['bound_contract_address'])
    actual=evaluate_v2(resolved,old.inputs_for(name,rows(data)),registry,evaluation_context_resolver=lambda node,inputs:{'bound_contract':bound})
    assert all(row['timeframe']==timeframe for row in receipt['bound_requirements'])
    return actual,receipt


def compare(name,actual,want,data,parameters,case,breaks=()):
    assert set(actual)==set(want)==set(old.oracle.declared_outputs(name)),(name,case,'output closure')
    index=old.index_for(len(data['close']));maximum_absolute=maximum_relative=0.;valid=0
    required=old.oracle.declared_inputs(name);begin=0
    states=[]
    for i in range(len(index)):
        if i in breaks:begin=i
        if any(not fresh.finite(data[f][i]) for f in required):begin=i+1;states.append('INVALID')
        elif i-begin<old.oracle.first_valid(name,parameters):states.append('INSUFFICIENT_HISTORY')
        else:states.append('MATHEMATICALLY_UNDEFINED')
    for port,expected in want.items():
        series=actual[port]
        assert isinstance(series,pd.Series) and series.index.equals(index) and series.name==port
        assert len(series)==len(expected)
        for i,(got,value) in enumerate(zip(series,expected)):
            identity=(name,case,parameters,port,i)
            state='VALID' if value is not None else states[i]
            assert got.state.value==state,(identity,'mask',got,state)
            assert got.causes==(),(identity,'causes',got.causes)
            if value is None:assert got.value is None,identity;continue
            valid+=1;absolute=abs(got.value-value);relative=absolute/abs(value) if value else 0.
            maximum_absolute=max(maximum_absolute,absolute);maximum_relative=max(maximum_relative,relative)
            assert absolute <= (1e-12 if value==0 else 1e-10),(identity,'absolute',got.value,value,absolute)
            if value:assert relative<=1e-9,(identity,'relative',got.value,value,relative)
    old.record('fresh-comparisons',dict(name=name,case=case,parameters=parameters,outputs=list(want),bars=len(index),valid_cells=valid,max_absolute_error=maximum_absolute,max_relative_error=maximum_relative))

CASES=[]
for fixture,data in fresh.fixtures().items():
    if fixture.startswith('near_flat'):
        names=('ALPHA','BETA','CCI','ZSCORE','VOLUME_ZSCORE','RESIDUAL','ROLLING_REGRESSION','PERCENT_RETURN','ROLLING_RETURN','ROC','LOG_RETURN','CORRELATION')
    elif fixture.startswith('exact_double'):names=('RESIDUAL','ROLLING_REGRESSION')
    elif fixture.startswith('constant_thirds'):names=('ALPHA','BETA')
    elif fixture.startswith('constant_'):names=('ALPHA','BETA','CCI','ZSCORE','VOLUME_ZSCORE','RESIDUAL','ROLLING_REGRESSION')
    elif fixture=='extreme_log':names=('LOG_RETURN',)
    elif fixture=='quantile_ties':names=('PERCENTILE',)
    elif fixture=='ols_long':names=('LINEAR_REGRESSION_SLOPE','LINEAR_REGRESSION_INTERCEPT')
    elif fixture=='two_point_correlation':names=('CORRELATION',)
    elif fixture=='mfi_small':names=('MFI',)
    for name in names:
        for window in ((4096,) if fixture=='ols_long' else (2,14)):
            CASES.append((name,fixture,window))

@pytest.mark.parametrize('name,fixture,window',CASES,ids=lambda v:str(v))
def test_fresh_complete_arrays_real_runtime(name,fixture,window):
    data=fresh.fixtures()[fixture];parameters={'window':window}
    want=fresh.expected(name,data,**parameters)
    actual,_=runtime(name,parameters,data)
    compare(name,actual,want,data,parameters,fixture)

@pytest.mark.parametrize('q',[None,0,0.,37,37.,37.5,50,50.,100,100.])
@pytest.mark.parametrize('timeframe',[60,300,3600])
def test_percentile_canonical_default_integer_float_receipts(q,timeframe):
    data=fresh.fixtures()['quantile_ties'];params={} if q is None else {'q':q}
    actual,receipt=runtime('PERCENTILE',params,data,timeframe)
    canonical=dict(receipt['parameters']);expected_q=50 if q is None else q
    assert canonical=={'q':expected_q,'window':14}
    assert type(canonical['q']) is type(expected_q)
    compare('PERCENTILE',actual,fresh.expected('PERCENTILE',data,q=50 if q is None else q),data,params,'canonical-q')

@pytest.mark.parametrize('name',['ALPHA','BETA','CCI','ZSCORE','VOLUME_ZSCORE','RESIDUAL','ROLLING_REGRESSION','PERCENT_RETURN','ROLLING_RETURN','ROC','LOG_RETURN'])
def test_fresh_prefix_gap_stream_and_serialized_restart(name):
    data=deepcopy(fresh.fixtures()['near_flat_1000000000000.0']);data[old.oracle.declared_inputs(name)[0]][18]=float('nan')
    parameters={'window':7};breaks=(30,);want=fresh.expected(name,data,7,breaks=breaks)
    index=old.index_for(len(data['close']));bound=old.binding(name,parameters);reset=[('DATA_GAP',) if i in breaks else () for i in range(len(index))]
    actual=core.evaluate(name,parameters,old.inputs_for(name,rows(data)),bound_contract=bound,resets=reset)
    compare(name,actual,want,data,parameters,'gap-array',breaks)
    for end in (1,7,8,18,19,29,31,39):
        prefix={f:v[:end] for f,v in data.items()}
        got=core.evaluate(name,parameters,old.inputs_for(name,rows(prefix)),bound_contract=bound,resets=reset[:end])
        compare(name,got,{p:v[:end] for p,v in want.items()},prefix,parameters,'causal-prefix',breaks)
    state=core.CoreMathState(name,parameters,bound);stream={p:[] for p in want}
    for i,row in enumerate(rows(data)):
        got=state.step(old.row_inputs(name,row),event_time=index[i],reset_reasons=reset[i])
        for p in stream:stream[p].append(got[p])
        if i in (0,5,6,7,18,19,29,30,31):state=core.CoreMathState.restore(name,parameters,bound,json.loads(json.dumps(state.snapshot())))
    compare(name,{p:pd.Series(v,index=index,name=p) for p,v in stream.items()},want,data,parameters,'restored-stream',breaks)

@pytest.mark.parametrize('name',['ALPHA','BETA','CCI','ZSCORE','VOLUME_ZSCORE','RESIDUAL','ROLLING_REGRESSION'])
def test_hostile_decimal_context_cannot_change_values_or_masks(name):
    data=fresh.fixtures()['near_flat_1000000000000.0'];params={'window':7};want=fresh.expected(name,data,7)
    bound=old.binding(name,params)
    with localcontext() as context:
        context.prec=2;context.rounding=ROUND_UP;context.Emin=-2;context.Emax=2
        context.traps[Inexact]=True;context.traps[Rounded]=True
        actual=core.evaluate(name,params,old.inputs_for(name,rows(data)),bound_contract=bound)
    compare(name,actual,want,data,params,'hostile-context')

def test_fresh_universe_matches_preserved_58_component_60_output_boundary():
    assert fresh.NAMES==old.NAMES==tuple(core.NAMES)
    old.test_complete_universe_and_legacy_identity_are_unpublished_and_unchanged()

def test_percentile_receipt_preserves_default_and_explicit_numeric_identity():
    default=old.binding('PERCENTILE');integer=old.binding('PERCENTILE',{'q':50});floating=old.binding('PERCENTILE',{'q':50.})
    assert default.bound_contract_address==integer.bound_contract_address
    assert integer.bound_contract_address!=floating.bound_contract_address
    assert json.dumps(old.plain(integer.document['parameters']),sort_keys=True)!=json.dumps(old.plain(floating.document['parameters']),sort_keys=True)

@pytest.mark.parametrize('name,value',[('CORRELATION',1.),('R_SQUARED',1.),('ROLLING_HEDGE_RATIO',2.),('BETA_ADJUSTED_SPREAD',0.)])
@pytest.mark.parametrize('exponent',[0,40,500,-500])
def test_existing_exact_line_identity_reaches_all_level_moment_consumers(name,value,exponent):
    # This uses the y=2x identity and exact binary vectors sealed before source
    # inspection. It checks sibling consumers without deriving from their output.
    data=fresh.fixtures()[f'exact_double_{exponent}'];params={'window':7}
    expected={'value':[None]*6+[value]*(len(data['close'])-6)}
    actual,_=runtime(name,params,data)
    compare(name,actual,expected,data,params,'exact-line-sibling')

def test_original_finite_precision_oracle_cannot_certify_constant_thirds():
    data=fresh.fixtures()['constant_thirds'];mismatches=[]
    for name in ('ALPHA','BETA'):
        for window in (2,14):
            exact=fresh.expected(name,data,window)['value']
            historical=old.oracle.scalar_series(name,rows(data),{'window':window})['value']
            mismatch=[i for i,(a,b) in enumerate(zip(exact,historical)) if (a is not None)!=(b.state=='VALID')]
            mismatches.append(dict(name=name,window=window,mask_mismatches=mismatch))
    assert any(x['mask_mismatches'] for x in mismatches)
    old.record('old-oracle-limit',{'fixture':'exact_thirds','cases':mismatches,'old_oracle_preserved':True})
