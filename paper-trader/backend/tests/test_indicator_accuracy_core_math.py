"""Implementation-owner checks, NOT the separate numerical assurance verdict.

Golden arrays below are hand-calculated from the accepted formula definitions.
They never import/reuse a product formula to construct an expected number.
No TA-Lib execution or external parity is claimed by this file.
"""
from copy import deepcopy
import json
import math
import os

import pandas as pd
import pytest

from app.ir.first_party.analytical_v2 import core_math as core
from app.ir.first_party.analytical_v2.contracts import (
    canonical_input_bindings, materialize_node_contract, ResolvedNodeContract,
)
from app.ir.hashing import content_address
from app.ir.node_contracts import NodeContractRefusal
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.runtime import evaluate_v2
from app.ir.validity import NumericValue, ValidityState
from app.market_data.requirements import compile_data_requirement_plan, verify_data_requirement_plan


NAMES = tuple("""ALPHA BETA BETA_ADJUSTED_SPREAD CCI CHAIKIN_MONEY_FLOW
CORRELATION COVARIANCE CROSS_ABOVE CROSS_BELOW FALLING GAP GAP_DOWN GAP_UP
HL2 HLC3 INSIDE_BAR LINEAR_REGRESSION_INTERCEPT LINEAR_REGRESSION_SLOPE
LOG_RETURN MAD MFI MIDPOINT MOMENTUM OHLC4 OUTSIDE_BAR PERCENTILE PERCENTILE_RANK
PERCENT_RETURN POINT_CHANGE RATIO RELATIVE_VOLUME RESIDUAL RISING ROC
ROLLING_HEDGE_RATIO ROLLING_HIGH ROLLING_LOW ROLLING_MAX ROLLING_MEAN
ROLLING_MEDIAN ROLLING_MIN ROLLING_RANK ROLLING_REGRESSION ROLLING_RETURN
ROLLING_STDDEV ROLLING_VARIANCE ROLLING_VOLUME_PERCENTILE R_SQUARED SMA
TREND_PERSISTENCE TRUE_RANGE TYPICAL_PRICE VOLUME_ZSCORE VWMA WEIGHTED_CLOSE
WILLIAMS_R WMA ZSCORE""".split())

LAG = frozenset("ALPHA BETA FALLING LOG_RETURN MFI MOMENTUM PERCENT_RETURN POINT_CHANGE RISING ROC ROLLING_RETURN TREND_PERSISTENCE".split())
ONE = frozenset("CROSS_ABOVE CROSS_BELOW GAP GAP_DOWN GAP_UP INSIDE_BAR OUTSIDE_BAR TRUE_RANGE".split())
ZERO = frozenset("HL2 HLC3 MIDPOINT OHLC4 RATIO TYPICAL_PRICE WEIGHTED_CLOSE".split())
NO_WINDOW = ONE | ZERO
WINDOW_ONE = frozenset("FALLING LOG_RETURN MOMENTUM PERCENT_RETURN POINT_CHANGE RISING ROC ROLLING_RETURN TREND_PERSISTENCE".split())
PEER = frozenset("ALPHA BETA BETA_ADJUSTED_SPREAD CORRELATION COVARIANCE CROSS_ABOVE CROSS_BELOW RATIO RESIDUAL ROLLING_HEDGE_RATIO ROLLING_REGRESSION R_SQUARED".split())
BOOLEAN = frozenset("CROSS_ABOVE CROSS_BELOW FALLING GAP_DOWN GAP_UP INSIDE_BAR OUTSIDE_BAR RISING".split())
H = ValidityState.INSUFFICIENT_HISTORY
U = ValidityState.MATHEMATICALLY_UNDEFINED
M = ValidityState.MISSING
I = ValidityState.INVALID


def addr(label):
    return content_address({"core_math_test_fact": label})


def fact(role, fields, timeframe=900):
    return {"schema": "canonical-input-binding/1", "owner_id": "org.core-math",
            "dataset_context_address": addr("dataset"), "evaluation_context_address": addr("evaluation"),
            "dataset_manifest_address": addr("manifest"), "market_truth_address": addr("market-truth"),
            "provider_product_address": addr("provider-product"), "provider_contract_address": addr("provider-contract"),
            "canonical_instrument_address": addr(role), "instrument": {"role": role, "type": "PHYSICAL"},
            "timeframe": timeframe, "fields": list(sorted(fields)), "freshness": {"maximum_age_seconds": 900},
            "depth": {"kind": "NONE", "levels": None}, "session": "INSTRUMENT_CALENDAR",
            "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}, "derived_local": False}


def bind(name, parameters=None, *, timeframe=900, alter=None):
    # Use actual /2 materialization, not a handcrafted receipt or fake source hash.
    ports = {}
    for port, fields in core.fields_by_port(name).items():
        source = fact("primary" if port == "frame" else port, fields, timeframe)
        if alter:
            alter(port, source)
        ports[port] = {"source": {"scope": "graph_input", "port_id": port},
                       "binding": source, "binding_address": content_address(source)}
    context = {"schema": "node-input-binding/1", "owner_id": "org.core-math",
               "dataset_context_address": addr("dataset"), "evaluation_context_address": addr("evaluation"),
               "context_address": content_address(ports), "ports": ports}
    return materialize_node_contract(core.source_contract(name), core.CONTRACT_BINDINGS[core.component_key(name)],
                                     core.parameters_for(name, parameters), context)


def params(name, window=2, **extra):
    return {**({} if name in NO_WINDOW else {"window": window}), **extra}


def bars(name, *, flat=False, zero=False, count=5):
    c = [0.0] * count if zero else [6.0] * count if flat else ([2., 4., 8., 4., 2.] * ((count + 4) // 5))[:count]
    index = pd.date_range("2025-01-02T10:00:00Z", periods=count, freq="15min")
    data = {"close": c, "high": c if flat or zero else [v + 2 for v in c],
            "low": c if flat or zero else [v - 2 for v in c],
            "open": c if flat or zero else [v + 1 for v in c],
            "volume": [0.] * count if zero else [10.] * count if flat else [float(i + 1) for i in range(count)]}
    result = {"frame": {key: pd.Series(value, index=index) for key, value in data.items()}}
    if name in PEER:
        result["peer"] = {"close": pd.Series([v / 2 for v in c], index=index)}
    return result


def run(name, parameters=None, inputs=None, **kwargs):
    parameters = params(name) if parameters is None else parameters
    inputs = bars(name) if inputs is None else inputs
    return core.evaluate(name, parameters, inputs, bound_contract=bind(name, parameters), **kwargs)


# Fixture: primary [2,4,8,4,2], peer [1,2,4,2,1], H/L=C+/-2,
# O=C+1, V=[1,2,3,4,5], window=2. Fractions written explicitly.
GOLDEN = {
    "ALPHA": [H, H, U, 0., U], "BETA": [H, H, U, 1., U],
    "BETA_ADJUSTED_SPREAD": [H, 0., 0., 0., 0.],
    "CCI": [H, 200/3, 200/3, -200/3, -200/3],
    "CHAIKIN_MONEY_FLOW": [H, 0., 0., 0., 0.],
    "CORRELATION": [H, 1., 1., 1., 1.], "COVARIANCE": [H, .5, 2., 2., .5],
    "CROSS_ABOVE": [H, False, False, False, False], "CROSS_BELOW": [H, False, False, False, False],
    "FALLING": [H, H, False, False, True],
    "GAP": [H, 3., 5., -3., -1.],
    "GAP_DOWN": [H, False, False, True, True], "GAP_UP": [H, True, True, False, False],
    "HL2": [2.,4.,8.,4.,2], "HLC3": [2.,4.,8.,4,2],
    "INSIDE_BAR": [H,False,False,False,False],
    "LINEAR_REGRESSION_INTERCEPT": [H,2.,4.,8.,4.], "LINEAR_REGRESSION_SLOPE": [H,2.,4.,-4.,-2.],
    "LOG_RETURN": [H,H,1.3862943611198906,0.,-1.3862943611198906],
    "MAD": [H,1.,2.,2.,1.], "MFI": [H,H,100.,60.,0.],
    "MIDPOINT": [2.,4.,8.,4.,2.], "MOMENTUM": [H,H,6.,0.,-6.],
    "OHLC4": [2.25,4.25,8.25,4.25,2.25], "OUTSIDE_BAR": [H,False,False,False,False],
    "PERCENTILE": [H,3.,6.,6.,3.], "PERCENTILE_RANK": [H,100.,100.,50.,50.],
    "PERCENT_RETURN": [H,H,3.,0.,-.75], "POINT_CHANGE": [H,H,6.,0.,-6.],
    "RATIO": [2.,2.,2.,2.,2.], "RELATIVE_VOLUME": [H,4/3,6/5,8/7,10/9],
    "RESIDUAL": [H,0.,0.,0.,0.], "RISING": [H,H,True,False,False],
    "ROC": [H,H,3.,0.,-.75], "ROLLING_HEDGE_RATIO": [H,2.,2.,2.,2.],
    "ROLLING_HIGH": [H,4.,8.,8.,4.], "ROLLING_LOW": [H,2.,4.,4.,2.],
    "ROLLING_MAX": [H,4.,8.,8.,4.], "ROLLING_MEAN": [H,3.,6.,6.,3.],
    "ROLLING_MEDIAN": [H,3.,6.,6.,3.], "ROLLING_MIN": [H,2.,4.,4.,2.],
    "ROLLING_RANK": [H,2.,2.,1.,1.],
    "ROLLING_REGRESSION": {"intercept":[H,0.,0.,0.,0.],"residual":[H,0.,0.,0.,0.],"slope":[H,2.,2.,2.,2.]},
    "ROLLING_RETURN": [H,H,3.,0.,-.75], "ROLLING_STDDEV": [H,1.,2.,2.,1.],
    "ROLLING_VARIANCE": [H,1.,4.,4.,1.], "ROLLING_VOLUME_PERCENTILE": [H,100.,100.,100.,100.],
    "R_SQUARED": [H,1.,1.,1.,1.], "SMA": [H,3.,6.,6.,3.],
    "TREND_PERSISTENCE": [H,H,1.,0.,1.], "TRUE_RANGE": [H,4.,6.,6.,4.],
    "TYPICAL_PRICE": [2.,4.,8.,4.,2.], "VOLUME_ZSCORE": [H,1.,1.,1.,1.],
    "VWMA": [H,10/3,32/5,40/7,26/9], "WEIGHTED_CLOSE": [2.,4.,8.,4.,2.],
    "WILLIAMS_R": [H,-100/3,-25.,-75.,-200/3], "WMA": [H,10/3,20/3,16/3,8/3],
    "ZSCORE": [H,1.,1.,-1.,-1.],
}


def compare(actual, expected, index, *, exact=False):
    if not isinstance(expected, dict):
        expected = {"value": expected}
    assert tuple(actual) == tuple(sorted(expected))
    for port, cells in expected.items():
        assert actual[port].index.equals(index)
        assert actual[port].name == port
        assert len(actual[port]) == len(cells)
        for i, (got, want) in enumerate(zip(actual[port], cells)):
            assert isinstance(got, NumericValue), (port, i)
            if isinstance(want, ValidityState):
                assert got.state is want and got.value is None, (port, i, got, want)
            else:
                assert got.state is ValidityState.VALID, (port, i, got, want)
                if type(want) is bool:
                    assert type(got.value) is bool and got.value is want, (port, i)
                else:
                    error = abs(got.value - want)
                    if exact or want == 0:
                        assert error <= 1e-12, (port, i, got, want)
                    else:
                        assert error <= 1e-10 and error / abs(want) <= 1e-9, (port, i, got, want)


def test_complete_scope_and_unpublished_candidates():
    from app.ir.library import REGISTRY, V2_CONTRIBUTORS
    assert tuple(sorted(GOLDEN)) == tuple(sorted(NAMES)) == core.NAMES
    assert len(NAMES) == 58 and core not in V2_CONTRIBUTORS
    assert all(core.component_key(name) not in REGISTRY.v2_components for name in NAMES)
    assert sum(core.SPECS[n]["decision"] == "KEEP" for n in NAMES) == 20
    with pytest.raises(TypeError):
        core.SPECS["SMA"]["parameters"]["window"]["default"] = 4


@pytest.mark.parametrize("name", NAMES)
def test_complete_hand_calculated_arrays(name):
    inputs = bars(name)
    compare(run(name, inputs=inputs), GOLDEN[name], inputs["frame"]["close"].index, exact=name in BOOLEAN or name in NO_WINDOW)


@pytest.mark.parametrize("name", ["ROLLING_VARIANCE", "ROLLING_STDDEV", "COVARIANCE", "PERCENTILE"])
def test_nondefault_mathematical_variants(name):
    cases = {"ROLLING_VARIANCE": ({"ddof":1}, [H,2.,8.,8.,2.]),
             "ROLLING_STDDEV": ({"ddof":1}, [H,math.sqrt(2),math.sqrt(8),math.sqrt(8),math.sqrt(2)]),
             "COVARIANCE": ({"ddof":1}, [H,1.,4.,4.,1.]),
             "PERCENTILE": ({"q":25.}, [H,2.5,5.,5.,2.5])}
    extra, values = cases[name]
    inputs = bars(name)
    compare(run(name, params(name, **extra), inputs), values, inputs["frame"]["close"].index)


UNDEFINED_FLAT = frozenset("ALPHA BETA BETA_ADJUSTED_SPREAD CORRELATION RESIDUAL ROLLING_HEDGE_RATIO ROLLING_REGRESSION R_SQUARED VOLUME_ZSCORE ZSCORE".split())
FLAT_PRICE = frozenset("HL2 HLC3 LINEAR_REGRESSION_INTERCEPT MIDPOINT OHLC4 PERCENTILE ROLLING_HIGH ROLLING_LOW ROLLING_MAX ROLLING_MEAN ROLLING_MEDIAN ROLLING_MIN SMA TYPICAL_PRICE VWMA WEIGHTED_CLOSE WMA".split())


def flat_value(name, window, zero):
    if name in UNDEFINED_FLAT or zero and name in {"RATIO", "LOG_RETURN", "PERCENT_RETURN", "ROC", "ROLLING_RETURN", "VWMA", "RELATIVE_VOLUME", "CHAIKIN_MONEY_FLOW"}:
        return U
    if name in BOOLEAN:
        return False
    if name in FLAT_PRICE:
        return 0. if zero else 6.
    if name == "RATIO":
        return 2.
    if name == "RELATIVE_VOLUME":
        return 1.
    if name == "ROLLING_RANK":
        return (window + 1) / 2
    if name in {"PERCENTILE_RANK", "ROLLING_VOLUME_PERCENTILE"}:
        return 50 + 50 / window
    return 0.


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("window", [None, 2, 4096])
@pytest.mark.parametrize("zero", [False, True])
def test_defaults_maximum_and_flat_zero_complete_masks(name, window, zero):
    chosen = {} if window is None else params(name, window)
    size = 14 if window is None else window
    first = 0 if name in ZERO else 1 if name in ONE else size if name in LAG else size - 1
    inputs = bars(name, flat=True, zero=zero, count=first + 3)
    value = flat_value(name, size, zero)
    values = [H] * first + [value] * 3
    want = {port: values for port in ("intercept", "residual", "slope")} if name == "ROLLING_REGRESSION" else values
    compare(run(name, chosen, inputs), want, inputs["frame"]["close"].index, exact=name in BOOLEAN or name in NO_WINDOW)


@pytest.mark.parametrize("name", NAMES)
def test_parameters_and_exact_data_contract(name):
    key = core.component_key(name)
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=core.V2_TYPES,
        v2_components={key: core.V2_COMPONENTS[key]}, node_contracts={key:core.NODE_CONTRACTS[key]},
        contract_bindings={key:core.CONTRACT_BINDINGS[key]}, v2_implementations={key:core.V2_IMPLEMENTATIONS[key]})
    assert key in registry.v2_implementations
    default = core.parameters_for(name)
    assert ("window" in default) is (name not in NO_WINDOW)
    if "window" in default:
        assert default["window"] == 14
        minimum = 1 if name in WINDOW_ONE else 2
        for bad in (True, 2.0, minimum-1,4097,None,"2"):
            with pytest.raises(NodeContractRefusal): core.parameters_for(name,{"window":bad})
        assert core.parameters_for(name,{"window":minimum})["window"] == minimum
    for bad in ({"capability_verified":True},{"unrecognized":2}):
        with pytest.raises(NodeContractRefusal): core.parameters_for(name,bad)
    if name in {"ROLLING_STDDEV","ROLLING_VARIANCE","COVARIANCE"}:
        for bad in (True,1.0,2,-1,None):
            with pytest.raises(NodeContractRefusal): core.parameters_for(name,{"ddof":bad})
    if name == "PERCENTILE":
        for bad in (True,-.01,100.01,float("nan"),float("inf"),None):
            with pytest.raises(NodeContractRefusal): core.parameters_for(name,{"q":bad})
    bound = bind(name, params(name), timeframe=3600)
    first = 0 if name in ZERO else 1 if name in ONE else 2 if name in LAG else 1
    assert bound.document["resolved_contract"]["warmup_history"] == first
    assert set(bound.document["resolved_contract"]["output_warmup"].values()) == {first}
    assert all(row["timeframe"] == 3600 and row["history"]["warmup_bars"] == first for row in bound.document["bound_requirements"])
    assert set(bound.document["input_binding"]["ports"]) == ({"frame","peer"} if name in PEER else {"frame"})
    with pytest.raises(NodeContractRefusal): core.CoreMathState(name, params(name), None)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("missing,state", [(None,M),(float("nan"),I),(float("inf"),I),(-float("inf"),I),(True,I)])
def test_gap_invalidity_and_rewarm_complete_arrays(name, missing, state):
    inputs = bars(name, flat=True, count=9)
    port, fields = next(iter(core.fields_by_port(name).items()))
    field = fields[0].lower()
    inputs[port][field] = inputs[port][field].astype(object)
    inputs[port][field].iloc[3] = missing
    first = 0 if name in ZERO else 1 if name in ONE else 2 if name in LAG else 1
    values = [H if i<first or 3<i<4+first else state if i==3 else flat_value(name,2,False) for i in range(9)]
    want = {port:values for port in ("intercept","residual","slope")} if name == "ROLLING_REGRESSION" else values
    compare(run(name, params(name), inputs), want, inputs["frame"]["close"].index)


@pytest.mark.parametrize("name", NAMES)
def test_missing_fields_roles_alignment_and_prefix_restart(name):
    inputs = bars(name, count=9)
    p= params(name); bound=bind(name,p)
    batch=run(name,p,inputs)
    for port, fields in core.fields_by_port(name).items():
        broken=deepcopy(inputs); del broken[port][fields[0].lower()]
        with pytest.raises(NodeContractRefusal): run(name,p,broken)
    broken=deepcopy(inputs); port=next(iter(core.fields_by_port(name))); field=core.fields_by_port(name)[port][0].lower()
    broken[port][field].index=broken[port][field].index[::-1]
    with pytest.raises(NodeContractRefusal):run(name,p,broken)
    if name in PEER:
        broken=deepcopy(inputs);broken["peer"]["close"].index += pd.Timedelta(seconds=1)
        with pytest.raises(NodeContractRefusal):run(name,p,broken)
        with pytest.raises(NodeContractRefusal):bind(name,p,alter=lambda port,f: f["instrument"].update(role="primary") if port=="peer" else None)
        mismatch=bind(name,p,alter=lambda port,f:f.update(timeframe=60) if port=="peer" else None)
        with pytest.raises(NodeContractRefusal):core.CoreMathState(name,p,mismatch)
    state=core.CoreMathState(name,p,bound)
    index=inputs["frame"]["close"].index
    for i,time in enumerate(index):
        prefix={port:{field:series.iloc[:i+1] for field,series in columns.items()} for port,columns in inputs.items()}
        pref=run(name,p,prefix)
        row={port:{field:series.iloc[i] for field,series in columns.items()} for port,columns in inputs.items()}
        stepped=state.step(row,event_time=time)
        for port in batch:
            assert list(pref[port])==list(batch[port].iloc[:i+1])
            assert stepped[port]==batch[port].iloc[i]
        snapshot=json.loads(json.dumps(state.snapshot(),allow_nan=False))
        state=core.CoreMathState.restore(name,p,bound,snapshot)
        changed=deepcopy(snapshot);changed['bound_contract_address']=addr('wrong')
        with pytest.raises(NodeContractRefusal):core.CoreMathState.restore(name,p,bound,changed)
    with pytest.raises(NodeContractRefusal):state.step(row,event_time=index[-1])
    with pytest.raises(NodeContractRefusal):state.step(row,event_time=index[-1]+pd.Timedelta(minutes=15),event_kind="partial_bar")


def test_mfi_small_flow_boundary_and_rank_ties():
    inputs=bars("MFI",count=3)
    inputs['frame']['volume']=pd.Series([0.,0.,.1],index=inputs['frame']['close'].index)
    compare(run("MFI",inputs=inputs),[H,H,0.],inputs['frame']['close'].index)
    inputs['frame']['volume'].iloc[2]=.125
    compare(run("MFI",inputs=inputs),[H,H,100.],inputs['frame']['close'].index)
    inputs=bars('ROLLING_RANK');inputs['frame']['close']=pd.Series([1.,2.,2.,1.,2.],index=inputs['frame']['close'].index)
    compare(run('ROLLING_RANK',inputs=inputs),[H,2.,1.5,1.,2.],inputs['frame']['close'].index)


@pytest.mark.parametrize('name',NAMES)
def test_explicit_gap_reset_and_adjacent_sessions(name):
    inputs=bars(name,flat=True,count=7);index=inputs['frame']['close'].index
    # A synthetic verified overnight/session closure is not a DATA_GAP. No civil
    # date or timeframe inference may reset ordinary core math.
    shifted=pd.DatetimeIndex(list(index[:3])+[t+pd.Timedelta(days=3) for t in index[3:]])
    for frame in inputs.values():
        for series in frame.values():series.index=shifted
    first=0 if name in ZERO else 1 if name in ONE else 2 if name in LAG else 1
    values=[H]*first+[flat_value(name,2,False)]*(7-first)
    want={port:values for port in ('intercept','residual','slope')} if name=='ROLLING_REGRESSION' else values
    compare(run(name,inputs=inputs),want,shifted)
    resets=[()]*7;resets[3]=('DATA_GAP',)
    values=[H if i<first or 3<=i<3+first else flat_value(name,2,False) for i in range(7)]
    want={port:values for port in ('intercept','residual','slope')} if name=='ROLLING_REGRESSION' else values
    compare(run(name,inputs=inputs,resets=resets),want,shifted)


def test_safe_environment():
    assert os.environ['PT_PROVIDER']=='mock'
    assert os.environ['PT_EXECUTION']=='paper'
    assert os.environ['PT_LIVE_ACK']==''


@pytest.mark.parametrize('name', ['ALPHA', 'BETA', 'ROLLING_HEDGE_RATIO', 'ROLLING_REGRESSION', 'RESIDUAL', 'BETA_ADJUSTED_SPREAD'])
def test_return_beta_is_not_level_regression_or_inverted_roles(name):
    inputs = bars(name)
    index = inputs['frame']['close'].index
    inputs['frame']['close'] = pd.Series([100., 300., 600., 300., 900.], index=index)
    inputs['peer']['close'] = pd.Series([100., 200., 200., 100., 150.], index=index)
    # Return pairs: x=[1,0,-.5,.5], y=[2,1,-.5,2]. Two-point OLS
    # yields (slope, intercept)=(1,1),(3,1),(2.5,.75).
    values = {
        'ALPHA': [H,H,1.,1.,.75], 'BETA': [H,H,1.,3.,2.5],
        'ROLLING_HEDGE_RATIO': [H,2.,U,3.,12.],
        'BETA_ADJUSTED_SPREAD': [H,-100.,U,0.,-900.],
        'RESIDUAL': [H,0.,U,0.,0.],
        'ROLLING_REGRESSION': {'intercept':[H,-100.,U,0.,-900.], 'residual':[H,0.,U,0.,0.], 'slope':[H,2.,U,3.,12.]},
    }
    compare(run(name,inputs=inputs), values[name], index)


@pytest.mark.parametrize('name', sorted(WINDOW_ONE))
def test_one_bar_lags_are_real_supported_variants(name):
    values = {
        'MOMENTUM':[H,2.,4.,-4.,-2.], 'POINT_CHANGE':[H,2.,4.,-4.,-2.],
        'LOG_RETURN':[H,.6931471805599453,.6931471805599453,-.6931471805599453,-.6931471805599453],
        'PERCENT_RETURN':[H,1.,1.,-.5,-.5], 'ROC':[H,1.,1.,-.5,-.5], 'ROLLING_RETURN':[H,1.,1.,-.5,-.5],
        'RISING':[H,True,True,False,False], 'FALLING':[H,False,False,True,True],
        'TREND_PERSISTENCE':[H,1.,1.,1.,1.],
    }
    inputs = bars(name)
    compare(run(name, {'window':1}, inputs), values[name], inputs['frame']['close'].index)


@pytest.mark.parametrize('name', ['CROSS_ABOVE','CROSS_BELOW','INSIDE_BAR','OUTSIDE_BAR'])
def test_predicate_true_false_equality_and_unknown(name):
    inputs = bars(name)
    index = inputs['frame']['close'].index
    if name.startswith('CROSS'):
        inputs['frame']['close'] = pd.Series([1.,2.,2.,0.,1.],index=index)
        inputs['peer']['close'] = pd.Series([1.,1.,1.,1.,1.],index=index)
        want = [H,True,False,False,False] if name=='CROSS_ABOVE' else [H,False,False,True,False]
    else:
        inputs['frame']['high'] = pd.Series([5.,4.,6.,6.,8.],index=index)
        inputs['frame']['low'] = pd.Series([1.,2.,0.,0.,-1.],index=index)
        want = [H,True,False,False,False] if name=='INSIDE_BAR' else [H,False,True,False,True]
    compare(run(name, inputs=inputs), want, index)


@pytest.mark.parametrize('name', NAMES)
def test_serialized_restart_at_gap_reset_and_session_boundaries(name):
    inputs = bars(name, flat=True, count=9)
    port, fields = next(iter(core.fields_by_port(name).items()))
    field = fields[0].lower()
    inputs[port][field] = inputs[port][field].astype(object)
    inputs[port][field].iloc[3] = None
    index = inputs['frame']['close'].index
    shifted = pd.DatetimeIndex(list(index[:6]) + [t + pd.Timedelta(days=2) for t in index[6:]])
    for frame in inputs.values():
        for series in frame.values(): series.index = shifted
    resets = [()] * 9
    resets[6] = ('DATA_GAP',)
    p = params(name)
    bound = bind(name,p)
    batch = core.evaluate(name,p,inputs,bound_contract=bound,resets=resets)
    state = core.CoreMathState(name,p,bound)
    for i, timestamp in enumerate(shifted):
        row = {port:{field:series.iloc[i] for field,series in frame.items()} for port,frame in inputs.items()}
        step = state.step(row,event_time=timestamp,reset_reasons=resets[i])
        assert step == {port:series.iloc[i] for port,series in batch.items()}
        document = json.loads(json.dumps(state.snapshot(),allow_nan=False))
        state = core.CoreMathState.restore(name,p,bound,document)
    with pytest.raises(NodeContractRefusal):
        core.CoreMathState.restore(name,p,bind(name,p,timeframe=60),document)
    oversized = deepcopy(document)
    oversized['rows'] *= state.capacity + 1
    with pytest.raises(NodeContractRefusal): core.CoreMathState.restore(name,p,bound,oversized)
    opened = deepcopy(document)
    opened['unknown'] = 1
    with pytest.raises(NodeContractRefusal): core.CoreMathState.restore(name,p,bound,opened)


@pytest.mark.parametrize('q,want', [(0.,[H,2.,4.,4.,2.]), (100.,[H,4.,8.,8.,4.])])
def test_percentile_endpoints(q,want):
    inputs = bars('PERCENTILE')
    compare(run('PERCENTILE',{'window':2,'q':q},inputs),want,inputs['frame']['close'].index)


@pytest.mark.parametrize('field', ['implementation','memory','fields','mode'])
def test_rehashed_binding_receipt_cannot_weaken_contract(field):
    from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract
    from app.ir.node_contracts import _plain
    bound = bind('SMA', {'window':2})
    document = _plain(bound.document)
    if field == 'implementation':
        document['binding_implementation_address'] = addr('forged-implementation')
    elif field == 'memory':
        document['resolved_contract']['resource_profile']['memory_bytes_upper_bound'] = 0
    elif field == 'fields':
        document['resolved_contract']['required_market_fields'] = []
    else:
        document['resolved_contract']['mode_eligibility']['live'] = True
    document['bound_contract_address'] = content_address({k:v for k,v in document.items() if k!='bound_contract_address'})
    forged = ResolvedNodeContract(document,document['bound_contract_address'])
    with pytest.raises(NodeContractRefusal):core.CoreMathState('SMA',{'window':2},forged)


def core_through_canonical_runtime(name, parameters, inputs):
    """Build the real receipt without the candidate's parameter helper."""
    from app.ir.node_contracts import _plain
    key = ('analytical.' + name.lower(), 2)
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=core.V2_TYPES,
        v2_components={key:core.V2_COMPONENTS[key]}, node_contracts={key:core.NODE_CONTRACTS[key]},
        contract_bindings={key:core.CONTRACT_BINDINGS[key]}, v2_implementations={key:core.V2_IMPLEMENTATIONS[key]})
    ports = _plain(core.V2_COMPONENTS[key]['ports'])
    input_ports = [deepcopy(port) for port in ports if port['direction']=='input']
    output_ports = [deepcopy(port) for port in ports if port['direction']=='output']
    document = {
        'format_version':2, 'strategy_id':'core-canonical-parameters', 'strategy_version':1,
        'metadata':{'metadata_version':1,'name':'Core canonical parameters','description':None,'tags':[]},
        'graph_inputs':input_ports, 'graph_outputs':output_ports,
        'nodes':[{'node_id':'probe','component':{'component_id':key[0],'component_version':2},'parameters':parameters}],
        'edges':[
            {'edge_id':'in-' + port['port_id'],'source':{'scope':'graph_input','port_id':port['port_id']},
             'target':{'scope':'node','node_id':'probe','port_id':port['port_id']},'binding':{'kind':'single'}} for port in input_ports
        ] + [
            {'edge_id':'out-' + port['port_id'],'source':{'scope':'node','node_id':'probe','port_id':port['port_id']},
             'target':{'scope':'graph_output','port_id':port['port_id']},'binding':{'kind':'single'}} for port in output_ports
        ],
    }
    sources = {role:fact('primary' if role == 'frame' else role, [field.upper() for field in columns])
               for role, columns in inputs.items()}
    primary = sources['frame']
    context = canonical_input_bindings(owner_id=primary['owner_id'],
        dataset_context_address=primary['dataset_context_address'], evaluation_context_address=primary['evaluation_context_address'],
        bindings=sources, expected_source_addresses={role:content_address(source) for role, source in sources.items()})
    graph = resolve_v2(document, registry)
    plan = compile_data_requirement_plan(graph, registry=registry, input_bindings=context)
    verify_data_requirement_plan(plan, graph, registry=registry, input_bindings=context)
    receipt = plan.parameter_binding_provenance[0]['node_contract_binding']
    bound = ResolvedNodeContract(receipt, receipt['bound_contract_address'])
    outputs = evaluate_v2(graph, inputs, registry,
        evaluation_context_resolver=lambda node, inputs:{'bound_contract':bound})
    return outputs


def percentile_through_canonical_runtime(parameters, prices):
    index = pd.date_range('2025-01-02T10:00:00Z', periods=len(prices), freq='15min')
    return core_through_canonical_runtime('PERCENTILE', parameters, {'frame':{'close':pd.Series(prices,index=index)}}), index


@pytest.mark.parametrize('parameters,prices,want', [
    ({}, list(range(1,18)), [H]*13+[7.5,8.5,9.5,10.5]),
    ({'window':2}, [2,4,8,4,2], [H,3,6,6,3]),
    ({'window':2,'q':50}, [2,4,8,4,2], [H,3,6,6,3]),
    ({'window':2,'q':50.0}, [2,4,8,4,2], [H,3,6,6,3]),
    ({'window':2,'q':0}, [2,4,8,4,2], [H,2,4,4,2]),
    ({'window':2,'q':100}, [2,4,8,4,2], [H,4,8,8,4]),
    ({'window':2,'q':25.5}, [2,4,8,4,2], [H,2.51,5.02,5.02,2.51]),
], ids=['all-defaults','default-q','integer-q','float-q','minimum-q','maximum-q','fractional-q'])
def test_percentile_preserves_canonical_parameters_through_real_runtime(parameters, prices, want):
    actual, index = percentile_through_canonical_runtime(parameters, prices)
    compare(actual, want, index)


STABILITY_NAMES = ('ALPHA', 'BETA', 'LOG_RETURN', 'PERCENT_RETURN', 'ROC', 'ROLLING_RETURN',
                   'CCI', 'RESIDUAL', 'ROLLING_REGRESSION', 'VOLUME_ZSCORE', 'ZSCORE', 'MAD')


def near_flat_rows(length):
    rows = []
    for i in range(length):
        close = 100 + (((i * 7) % 19) + i) / 1e8
        peer = 200 + (((i * 11) % 23) + 2 * i) / 1e8
        volume = 300 + (((i * 13) % 29) + 3 * i) / 1e8
        rows.append(dict(open=close, high=close, low=close, close=close, peer=peer, volume=volume))
    return rows


@pytest.mark.parametrize('name', STABILITY_NAMES)
@pytest.mark.parametrize('choice', ('minimum', 'default', 'maximum'))
def test_small_signal_complete_arrays_through_canonical_runtime(name, choice):
    # Expected values remain owned by the sealed independent specification.
    # This permanent consumer regression does not supply new assurance authority.
    from tests import test_indicator_accuracy_core_math_assurance as assurance
    parameters = {key: spec[choice] for key, spec in assurance.oracle.parameter_specs(name).items()}
    rows = near_flat_rows(max(73, assurance.oracle.first_valid(name, parameters) + 4))
    index = assurance.index_for(len(rows))
    expected = assurance.oracle.scalar_series(name, rows, parameters)
    actual = core_through_canonical_runtime(name, parameters, assurance.inputs_for(name, rows, index))
    assurance.compare(name, actual, expected, index, case='small-signal-runtime-' + choice, parameters=parameters)


@pytest.mark.parametrize('name', ('ALPHA', 'BETA', 'CCI', 'RESIDUAL', 'ROLLING_REGRESSION', 'VOLUME_ZSCORE', 'ZSCORE'))
def test_precision_workspace_ignores_and_preserves_hostile_decimal_context(name):
    import decimal
    from tests import test_indicator_accuracy_core_math_assurance as assurance
    rows = near_flat_rows(37)
    expected = assurance.oracle.scalar_series(name, rows)
    bound = assurance.binding(name)
    with decimal.localcontext() as context:
        context.prec = 2
        context.rounding = decimal.ROUND_UP
        context.Emax, context.Emin = 2, -2
        context.traps[decimal.Inexact] = context.traps[decimal.FloatOperation] = True
        before = str(context)
        actual = core.evaluate(name, {}, assurance.inputs_for(name, rows), bound_contract=bound)
        assert str(context) == before
    assurance.compare(name, actual, expected, assurance.index_for(len(rows)), case='hostile-decimal-context')


@pytest.mark.parametrize('name', ('LOG_RETURN', 'PERCENT_RETURN', 'ROC', 'ROLLING_RETURN'))
def test_return_signed_zero_and_ratio_overflow_underflow_endpoints(name):
    from tests import test_indicator_accuracy_core_math_assurance as assurance
    prices = [1e308, -1e308, 0.0, 5e-324, 1e-300, 1e308, 1e-300, 1.0, math.nextafter(1.0, 2.0)]
    assurance.evaluate_compare(name, [{'close': price} for price in prices], {'window':1}, case='finite-endpoint-extremes')


@pytest.mark.parametrize('name', ('ALPHA', 'BETA'))
@pytest.mark.parametrize('window', (7, 14))
def test_constant_exact_fractional_peer_returns_have_zero_variance(name, window):
    # All peer prices are exactly representable integers. Every adjacent
    # ratio is exactly 1/3, so the variance is exactly zero, independently
    # of any finite-precision oracle or candidate mean calculation.
    inputs = bars(name, count=20)
    index = inputs['frame']['close'].index
    inputs['peer']['close'] = pd.Series([float(3 ** (19-i)) for i in range(20)], index=index)
    compare(run(name, {'window':window}, inputs), [H] * window + [U] * (20-window), index)


@pytest.mark.parametrize('name', ('CCI', 'ZSCORE', 'VOLUME_ZSCORE'))
@pytest.mark.parametrize('price', (5e-324, 1e-300, 1e308))
def test_constant_extreme_finite_normalized_windows(name, price):
    inputs = bars(name, count=18, flat=True)
    for column in inputs['frame'].values():
        column[:] = price
    index = inputs['frame']['close'].index
    compare(run(name, {'window':14}, inputs), [H]*13 + [0.0 if name == 'CCI' else U]*5, index)


@pytest.mark.parametrize('name', ('RESIDUAL', 'ROLLING_REGRESSION'))
@pytest.mark.parametrize('window', (2, 14))
def test_exact_linear_large_levels_keep_exact_zero_residual(name, window):
    inputs = bars(name, count=31)
    index = inputs['frame']['close'].index
    peer = [math.ldexp(1 + i / 8192, 990) for i in range(len(index))]
    inputs['peer']['close'] = pd.Series(peer, index=index)
    inputs['frame']['close'] = pd.Series([2 * v for v in peer], index=index)
    # Multiplication by two is exact binary scaling here; y=2x gives exact
    # slope two, intercept zero and residual zero at every complete window.
    zeros = [H]*(window-1) + [0.0]*(len(index)-window+1)
    expected = {'intercept': zeros, 'residual': zeros, 'slope': [H]*(window-1)+[2.0]*(len(index)-window+1)} if name == 'ROLLING_REGRESSION' else zeros
    compare(run(name, {'window':window}, inputs), expected, index)


LEVEL_MOMENT_NAMES = ('BETA_ADJUSTED_SPREAD', 'CORRELATION', 'COVARIANCE',
                      'LINEAR_REGRESSION_INTERCEPT', 'LINEAR_REGRESSION_SLOPE',
                      'ROLLING_HEDGE_RATIO', 'R_SQUARED')


@pytest.mark.parametrize('name', LEVEL_MOMENT_NAMES)
@pytest.mark.parametrize('exponent', (-500, 0, 40, 500))
def test_level_moment_closed_forms_cross_real_consumers(name, exponent):
    count, window = 31, 7
    inputs = bars(name, count=count)
    index = inputs['frame']['close'].index
    x = [math.ldexp(1 + i*2**-50, exponent) for i in range(count)]
    y = [2*v for v in x]
    inputs['frame']['close'] = pd.Series(y, index=index)
    if name in PEER:
        inputs['peer']['close'] = pd.Series(x, index=index)
    # Exact y=2x and equally spaced binary levels. Population covariance for
    # seven points is 2*d^2*(7^2-1)/12 = 8*d^2. Tiny covariance rounds to
    # float64 zero but positive exact variance still defines correlation/slope.
    fixed = {'BETA_ADJUSTED_SPREAD': 0.0, 'CORRELATION': 1.0,
             'COVARIANCE': math.ldexp(1.0, 2*exponent-97),
             'LINEAR_REGRESSION_SLOPE': math.ldexp(1.0, exponent-49),
             'ROLLING_HEDGE_RATIO': 2.0, 'R_SQUARED': 1.0}
    wanted = [H]*(window-1) + ([y[i-window+1] for i in range(window-1,count)]
                              if name == 'LINEAR_REGRESSION_INTERCEPT' else [fixed[name]]*(count-window+1))
    compare(core_through_canonical_runtime(name, {'window':window}, inputs), wanted, index)


@pytest.mark.parametrize('name', ('CORRELATION', 'R_SQUARED'))
def test_adjacent_float_two_point_correlation_is_exact(name):
    inputs = bars(name, count=2)
    index = inputs['frame']['close'].index
    inputs['peer']['close'] = pd.Series([1.0, 1.0+2**-52], index=index)
    inputs['frame']['close'] = pd.Series([1.0, 1.0+2**-51], index=index)
    compare(core_through_canonical_runtime(name, {'window':2}, inputs), [H,1.0], index)


@pytest.mark.parametrize('ddof', (0,1))
def test_covariance_does_not_multiply_rounded_mean_errors(ddof):
    inputs = bars('COVARIANCE', count=3)
    index = inputs['frame']['close'].index
    unit = 2**-52
    inputs['peer']['close'] = pd.Series([1.0,1.0+unit,1.0+3*unit], index=index)
    inputs['frame']['close'] = pd.Series([1.0,1.0+2*unit,1.0+3*unit], index=index)
    # Centered cross-products sum to (13/3)*unit^2 exactly.
    want = math.ldexp(13 / (3*(3-ddof)), -104)
    compare(core_through_canonical_runtime('COVARIANCE', {'window':3,'ddof':ddof}, inputs), [H,H,want], index)


def test_time_regression_intercept_avoids_a_rounded_level_mean():
    inputs = bars('LINEAR_REGRESSION_INTERCEPT', count=3)
    index = inputs['frame']['close'].index
    base, unit = 2**40, 2**-12
    inputs['frame']['close'] = pd.Series([base,base+2*unit,base+3*unit], index=index)
    # Exact intercept is base+unit/6, whose nearest float64 is base.
    compare(core_through_canonical_runtime('LINEAR_REGRESSION_INTERCEPT', {'window':3}, inputs), [H,H,float(base)], index)


@pytest.mark.parametrize('name', LEVEL_MOMENT_NAMES)
def test_constant_large_levels_keep_their_mathematical_masks(name):
    inputs = bars(name, count=18, flat=True)
    for frame in inputs.values():
        for column in frame.values():
            column[:] = 1e308
    index = inputs['frame']['close'].index
    value = (1e308 if name == 'LINEAR_REGRESSION_INTERCEPT' else 0.0
             if name in {'COVARIANCE','LINEAR_REGRESSION_SLOPE'} else U)
    compare(core_through_canonical_runtime(name, {'window':14}, inputs), [H]*13+[value]*5, index)
