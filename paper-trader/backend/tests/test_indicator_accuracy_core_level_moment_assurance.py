"""Fresh exact expected vectors sealed before corrected product inspection."""
import json
import math
from pathlib import Path
import pandas as pd
import pytest
from tests import test_indicator_accuracy_core_math_assurance as baseline
from tests import test_indicator_accuracy_core_correction_assurance as harness
from research_tests import test_indicator_accuracy_core_level_moment_oracle as oracle
from app.ir.first_party.analytical_v2 import core_math as core

RUN=baseline.ROOT / '.agent/runs/post-phase5-indicator-accuracy-core-level-moment-assurance'
VECTORS=json.loads((RUN/'fresh-vectors.json').read_text())

def data_for(vector):
    y=vector['primary'];return {f:(vector['peer'] if f=='peer' else y) for f in ('open','high','low','close','volume','peer')}

def wanted(vector):
    return {p:[v if math.isfinite(v) else None for v in a] for p,a in vector['expected'].items()}

def check(vector,actual,data=None,case=None):
    if vector['component']=='VOLUME_ZSCORE' and any(v<0 for v in vector['primary']):
        # The sealed vectors express pure mathematics, not permission for negative
        # traded volume. Reuse the immutable independent oracle's ingress states;
        # recompute exact math after those invalid bars reset contiguous history.
        sanitized=[v if v>=0 else math.nan for v in vector['primary']]
        values=oracle.expectation('VOLUME_ZSCORE',sanitized,window=vector['window'])['value']
        states=baseline.oracle.scalar_series('VOLUME_ZSCORE',harness.rows(data_for(vector)),{'window':vector['window']})['value']
        expected={'value':[baseline.oracle.Cell(cell.state,values[i] if cell.state=='VALID' else None,cell.causes) for i,cell in enumerate(states)]}
        baseline.compare('VOLUME_ZSCORE',actual,expected,baseline.index_for(len(sanitized)),case=case or vector['case'],parameters={'window':vector['window']})
        return
    harness.compare(vector['component'],actual,wanted(vector),data or data_for(vector),
                    {'window':vector['window'],**({'ddof':vector['ddof']} if vector['component']=='COVARIANCE' else {})},case or vector['case'])

@pytest.mark.parametrize('vector',VECTORS,ids=lambda v:f"{v['component']}-{v['case']}-w{v['window']}-d{v['ddof']}")
def test_sealed_exact_arrays_through_resolver_compiler_runtime(vector):
    data=data_for(vector);params={'window':vector['window']}
    if vector['component']=='COVARIANCE':params['ddof']=vector['ddof']
    actual,receipt=harness.runtime(vector['component'],params,data)
    check(vector,actual)
    assert receipt['parameters']==params

STREAM_VECTORS=[v for v in VECTORS if v['window']==3 and v['case'] in ('adjacent-positive-1.0','adjacent-negative-1.0','gap-nan','positive-third-return')]
@pytest.mark.parametrize('vector',STREAM_VECTORS,ids=lambda v:f"{v['component']}-{v['case']}-d{v['ddof']}")
def test_exact_prefix_stream_and_json_restart(vector):
    name=vector['component'];data=data_for(vector);rows=harness.rows(data);params={'window':3}
    if name=='COVARIANCE':params['ddof']=vector['ddof']
    bound=baseline.binding(name,params);index=baseline.index_for(len(rows));state=core.CoreMathState(name,params,bound)
    result={p:[] for p in vector['expected']}
    for i,row in enumerate(rows):
        got=state.step(baseline.row_inputs(name,row),event_time=index[i])
        for p in result:result[p].append(got[p])
        if i in (0,1,2,3,4,5,6,10,11,12,13,16):
            state=core.CoreMathState.restore(name,params,bound,json.loads(json.dumps(state.snapshot())))
    check(vector,{p:pd.Series(v,index=index,name=p) for p,v in result.items()},case='json-restart-'+vector['case'])
    for end in (1,2,3,4,6,7,12,13,17):
        prefix={**vector,'primary':vector['primary'][:end],'peer':vector['peer'][:end],
                'expected':{p:a[:end] for p,a in vector['expected'].items()}}
        actual=core.evaluate(name,params,baseline.inputs_for(name,rows[:end]),bound_contract=bound)
        check(prefix,actual,case='prefix-'+vector['case'])

def test_new_oracle_seal_is_independent_and_unchanged():
    import hashlib
    seal=json.loads((RUN/'oracle-preinspection-seal.json').read_text())
    assert hashlib.sha256(Path(oracle.__file__).read_bytes()).hexdigest()==seal['oracle_sha256']
    assert hashlib.sha256((RUN/'fresh-vectors.json').read_bytes()).hexdigest()==seal['vectors_sha256']
    assert seal['product_helpers_inspected'] is seal['implementation_tests_inspected'] is False

@pytest.mark.parametrize('name',oracle.LEVEL)
@pytest.mark.parametrize('window',[2,14,4096])
@pytest.mark.parametrize('pattern',['adjacent-large','constant-extreme'])
def test_measured_f04_finite_scale_resources(name,window,pattern):
    import time
    import tracemalloc
    for ddof in ([0,1] if name=='COVARIANCE' else [0]):
        params={'window':window,**({'ddof':ddof} if name=='COVARIANCE' else {})}
        bound=baseline.binding(name,params);state=core.CoreMathState(name,params,bound)
        base=math.ldexp(1.,500)
        x=[1e300 if pattern=='constant-extreme' else base+math.ulp(base)*(i%17) for i in range(window+4)]
        y=x if pattern=='constant-extreme' else [2*v for v in x]
        data={f:(x if f=='peer' else y) for f in ('open','high','low','close','volume','peer')}
        rows=harness.rows(data);index=baseline.index_for(len(rows))
        for i in range(window):state.step(baseline.row_inputs(name,rows[i]),event_time=index[i])
        tracemalloc.start();duration=[]
        for i in range(window,len(rows)):
            start=time.perf_counter_ns();state.step(baseline.row_inputs(name,rows[i]),event_time=index[i]);duration.append((time.perf_counter_ns()-start)/1000)
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        snapshot=state.snapshot();size=baseline.deep_bytes(snapshot);history=baseline.deep_bytes(snapshot['rows'])
        encoded=len(json.dumps(snapshot,separators=(',',':')).encode());profile=bound.document['resolved_contract']['resource_profile']
        receipt=dict(name=name,parameters=params,pattern=pattern,max_event_us=max(duration),history_bytes=history,state_bytes=size,encoded_bytes=encoded,allocation_peak_bytes=peak,declared_profile=baseline.plain(profile))
        baseline.record('f04-resources',receipt)
        assert len(snapshot['rows'])==window
        assert max(duration)<=profile['compute_microseconds_per_event'],receipt
        assert max(size,encoded)<=profile['state_bytes_upper_bound'],receipt
        assert history<=profile['history_bytes_upper_bound'],receipt
        assert size+peak<=profile['memory_bytes_upper_bound'],receipt

@pytest.mark.parametrize('name',baseline.NAMES)
def test_all_58_components_60_outputs_through_actual_runtime(name):
    rows=baseline.oracle.fixture_rows(40,'jagged')
    data={key:[row[key] for row in rows] for key in rows[0]}
    actual,receipt=harness.runtime(name,{},data)
    expected=baseline.oracle.scalar_series(name,rows,{})
    baseline.compare(name,actual,expected,baseline.index_for(len(rows)),case='all-58-actual-runtime')
    assert receipt['component']=={'component_id':'analytical.'+name.lower(),'component_version':2}

def test_all_candidate_source_contracts_and_implementation_bindings_stay_sealed():
    previous=json.loads((RUN.parent/'post-phase5-indicator-accuracy-core-level-moment-correction/source-proof.json').read_text())
    assert len(previous['candidates'])==58
    for row in previous['candidates']:
        registry=baseline.candidate_registry(row['name']);key=('analytical.'+row['name'].lower(),2)
        assert registry.node_contract_addresses[key]==row['source_contract']
        assert registry.v2_implementation_registrations[key].implementation_address==row['implementation']
        assert core.CONTRACT_BINDINGS[key].implementation_address==row['binding']
