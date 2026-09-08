"""Implementation-owner specification tests; separate assurance remains required.

The short vectors are hand-derived rational values, not candidate output. Native
vectors, when invoked, are produced by the pinned isolated executor with no import
of the candidate. Neither constitutes the later independent-owner verdict.
"""
from copy import deepcopy
import decimal
from fractions import Fraction as F
import json
import math
import os
from pathlib import Path

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import recursive_state as rec
from app.ir.first_party.analytical_v2.contracts import materialize_node_contract, ResolvedNodeContract
from app.ir.validity import NumericValue, ValidityState


NAMES = tuple("""ACCUMULATION_DISTRIBUTION ADX ATR CHAIKIN_OSCILLATOR CUMULATIVE_RETURN
EMA KAMA MA_SLOPE MINUS_DI NATR OBV PARABOLIC_SAR PLUS_DI PRICE_MA_DISTANCE
PRICE_VOLUME_TREND RMA_WILDER RSI""".split())
WINDOW = frozenset("ADX ATR EMA KAMA MA_SLOPE MINUS_DI NATR PLUS_DI PRICE_MA_DISTANCE RMA_WILDER RSI".split())
H = ValidityState.INSUFFICIENT_HISTORY
U = ValidityState.MATHEMATICALLY_UNDEFINED
I = ValidityState.INVALID
M = ValidityState.MISSING
RUN = Path(__file__).resolve().parents[3] / ".agent/runs/post-phase5-indicator-accuracy-recursive-state"


def address(label):
    return hashing.content_address({"recursive_test_fact": label})


def fact(fields, timeframe=900):
    return {"schema": "canonical-input-binding/1", "owner_id": "org.recursive",
            "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
            "dataset_manifest_address": address("manifest"), "market_truth_address": address("market-truth"),
            "provider_product_address": address("provider-product"), "provider_contract_address": address("provider-contract"),
            "canonical_instrument_address": address("primary"), "instrument": {"role": "primary", "type": "PHYSICAL"},
            "timeframe": timeframe, "fields": sorted(fields), "freshness": {"maximum_age_seconds": 900},
            "depth": {"kind": "NONE", "levels": None}, "session": "INSTRUMENT_CALENDAR",
            "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}, "derived_local": False}


def binding(name, parameters=None, *, timeframe=900, alter=None):
    source = fact(rec.fields_by_port(name)["frame"], timeframe)
    if alter:
        alter(source)
    ports = {"frame": {"source": {"scope": "graph_input", "port_id": "frame"},
                       "binding": source, "binding_address": hashing.content_address(source)}}
    context = {"schema": "node-input-binding/1", "owner_id": "org.recursive",
               "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
               "context_address": hashing.content_address(ports), "ports": ports}
    return materialize_node_contract(rec.source_contract(name), rec.CONTRACT_BINDINGS[rec.component_key(name)],
                                     rec.parameters_for(name, parameters), context)


def parameters(name, window=2):
    if name == "CHAIKIN_OSCILLATOR":
        return {"fast_length": 2, "slow_length": 3}
    return {"window": window} if name in WINDOW else {}


def first(name, p):
    w = p.get("window", 14)
    if name == "ADX":
        return 2*w-1
    if name in {"ATR", "KAMA", "MA_SLOPE", "MINUS_DI", "NATR", "PLUS_DI", "RSI"}:
        return w
    if name in {"EMA", "PRICE_MA_DISTANCE", "RMA_WILDER"}:
        return w-1
    if name == "CHAIKIN_OSCILLATOR":
        return p.get("slow_length", 10)-1
    return 1 if name == "PARABOLIC_SAR" else 0


def frame(close=None, *, count=5, flat=None, index=None):
    c = list(close) if close is not None else [float(flat)]*count if flat is not None else ([2.,4.,8.,4.,2.] * ((count+4)//5))[:count]
    index = pd.date_range("2025-01-02T10:00:00Z", periods=len(c), freq="15min") if index is None else index
    return {"frame": {"close": pd.Series(c,index=index),
                      "high": pd.Series(c if flat is not None else [v+3 for v in c], index=index),
                      "low": pd.Series(c if flat is not None else [v-1 for v in c], index=index),
                      "volume": pd.Series([1.] * len(c) if flat is not None else [float(i+1) for i in range(len(c))],index=index)}}


def evaluate(name, p=None, inputs=None, **kwargs):
    p = parameters(name) if p is None else p
    inputs = frame() if inputs is None else inputs
    return rec.evaluate(name, p, inputs, bound_contract=binding(name,p), **kwargs)


def compare(actual, expected, index):
    assert set(actual) == {"value"}
    series = actual["value"]
    assert series.index.equals(index) and series.name == "value" and len(series) == len(expected)
    for bar, (got, want) in enumerate(zip(series, expected)):
        assert isinstance(got, NumericValue), bar
        if isinstance(want, ValidityState):
            assert got.state is want and got.value is None, (bar, got, want)
        else:
            assert got.state is ValidityState.VALID and math.isfinite(got.value), (bar, got, want)
            target = float(want)
            error = abs(got.value - target)
            assert error <= (1e-12 if target == 0 else 1e-10), (bar, got, target)
            if target:
                assert error / abs(target) <= 1e-8, (bar, got, target)


# C=[2,4,8,4,2], H=C+3, L=C-1, V=[1,2,3,4,5], w=2.
# AD uses -1/2 of volume. ADOSC uses fast=2, slow=3, first-AD seeds.
GOLDEN = {
    "ACCUMULATION_DISTRIBUTION": [F(-1,2), F(-3,2), -3, -5, F(-15,2)],
    "ADX": [H,H,H,F(800,13),F(15550,273)],
    "ATR": [H,H,6,F(11,2),F(19,4)],
    "CHAIKIN_OSCILLATOR": [H,H,F(-7,18),F(-17,27),F(-71,81)],
    "CUMULATIVE_RETURN": [0,1,3,1,0],
    "EMA": [H,3,F(19,3),F(43,9),F(79,27)],
    "KAMA": [H,H,F(52,9),F(16636,2883),F(106244,25947)],
    "MA_SLOPE": [H,H,F(10,3),F(-14,9),F(-50,27)],
    "MINUS_DI": [H,H,0,F(1600,39),F(3200,71)],
    "NATR": [H,H,75,F(275,2),F(475,2)],
    "OBV": [1,3,6,2,-3],
    "PARABOLIC_SAR": [H,1,1.12,1.5152,11],
    "PLUS_DI": [H,H,F(1000,19),F(1000,39),F(1000,71)],
    "PRICE_MA_DISTANCE": [H,1,F(5,3),F(-7,9),F(-25,27)],
    "PRICE_VOLUME_TREND": [0,2,5,3,F(1,2)],
    "RMA_WILDER": [H,3,F(11,2),F(19,4),F(27,8)],
    "RSI": [H,H,100,F(300,7),F(300,11)],
}


def test_scope_unpublished_and_immutable():
    from app.ir.library import REGISTRY, V2_CONTRIBUTORS
    assert tuple(sorted(GOLDEN)) == NAMES == rec.NAMES
    assert rec not in V2_CONTRIBUTORS
    assert all(rec.component_key(name) not in REGISTRY.v2_components for name in NAMES)
    assert sum(rec.SPECS[n]["decision"] == "KEEP" for n in NAMES) == 2
    with pytest.raises(TypeError):
        rec.SPECS["EMA"]["parameters"]["window"]["default"] = 2


@pytest.mark.parametrize("name", NAMES)
def test_hand_derived_complete_arrays(name):
    inputs = frame()
    compare(evaluate(name, inputs=inputs), GOLDEN[name], inputs["frame"]["close"].index)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("kind", ["default", "minimum", "maximum"])
@pytest.mark.parametrize("level", [0., 6.])
def test_all_parameter_extremes_flat_complete_arrays(name, kind, level):
    p = {} if kind == "default" else parameters(name, 2 if kind == "minimum" else 4096)
    if name == "CHAIKIN_OSCILLATOR" and kind == "maximum":
        p = {"fast_length":4095, "slow_length":4096}
    if name == "KAMA" and kind == "maximum":
        p.update(fast_length=4095, slow_length=4096)
    if name == "PARABOLIC_SAR" and kind != "default":
        p = {"start":1., "increment":1., "maximum":1.} if kind == "maximum" else {"start":math.ulp(0.),"increment":math.ulp(0.),"maximum":math.ulp(0.)}
    warmup = first(name,p)
    data = frame(count=warmup+3,flat=level)
    target = level if name in {"EMA","RMA_WILDER","KAMA","PARABOLIC_SAR"} else 1. if name == "OBV" else 0.
    expected = [H]*warmup + [target]*3
    if level == 0 and name in {"CUMULATIVE_RETURN","NATR"}:
        expected = [H]*warmup + [U]*3
    if level == 0 and name == "PRICE_VOLUME_TREND":
        expected = [0.,U,U]
    compare(evaluate(name,p,data), expected, data["frame"]["close"].index)
    bound = binding(name,p,timeframe=3600)
    assert bound.document["resolved_contract"]["warmup_history"] == warmup
    assert dict(bound.document["resolved_contract"]["output_warmup"]) == {"value":warmup}


@pytest.mark.parametrize("name", NAMES)
def test_parameter_refusals_and_binding_replay(name):
    with pytest.raises(node_contracts.NodeContractRefusal):
        rec.parameters_for(name,{"not_a_parameter":1})
    for key, spec in rec.SPECS[name]["parameters"].items():
        bad = [True,False,None,"2",float("nan"),float("inf"),spec["minimum"]-1,spec["maximum"]+1]
        if spec["type"] == "exact_integer":
            bad += [2.,2.5]
        for value in bad:
            with pytest.raises(node_contracts.NodeContractRefusal):
                rec.parameters_for(name,{key:value})
            canonical = dict(rec.parameters_for(name)); canonical[key] = value
            with pytest.raises((ValueError,TypeError)):
                rec._binding_rule(name)(canonical,{})
    if name in {"KAMA","CHAIKIN_OSCILLATOR"}:
        invalid = [{"fast_length":2,"slow_length":2},{"fast_length":30,"slow_length":2}]
    elif name == "PARABOLIC_SAR":
        invalid = [{"start":0},{"increment":0},{"start":.5,"maximum":.1},{"increment":.5,"maximum":.1}]
    else:
        invalid = []
    for p in invalid:
        with pytest.raises(node_contracts.NodeContractRefusal):
            rec.parameters_for(name,p)
        canonical = dict(rec.parameters_for(name)); canonical.update(p)
        with pytest.raises(ValueError):
            rec._binding_rule(name)(canonical,{})
    with pytest.raises(node_contracts.NodeContractRefusal):
        rec.RecursiveState(name,{},None)


@pytest.mark.parametrize("name", NAMES)
def test_context_independent_arithmetic(name):
    data = frame(count=33)
    baseline = evaluate(name,inputs=data)
    with decimal.localcontext() as ctx:
        ctx.prec = 3; ctx.rounding = decimal.ROUND_DOWN
        ctx.traps[decimal.Inexact] = True
        assert evaluate(name,inputs=data)["value"].tolist() == baseline["value"].tolist()


@pytest.mark.parametrize("name", NAMES)
def test_causal_prefix_stream_restart_resets(name):
    p = parameters(name)
    data = frame(count=26)
    # An overnight, shortened and holiday-spanning canonical sequence: closures
    # are not gaps. The DATA_GAP event at 19 is an explicit producer fact.
    idx = pd.DatetimeIndex([pd.Timestamp("2025-01-02T14:00:00Z") + pd.Timedelta(minutes=15*i) for i in range(8)] +
                           [pd.Timestamp("2025-01-03T09:00:00Z") + pd.Timedelta(minutes=15*i) for i in range(5)] +
                           [pd.Timestamp("2025-01-06T09:00:00Z") + pd.Timedelta(minutes=15*i) for i in range(13)])
    for series in data["frame"].values(): series.index = idx
    field = rec.SPECS[name]["inputs"][0]
    data["frame"][field].iloc[7] = float("nan")
    resets = [()] * 26; resets[19] = ("DATA_GAP",); resets[23] = ("IDENTITY_CHANGE",)
    bound = binding(name,p)
    batch = rec.evaluate(name,p,data,bound_contract=bound,resets=resets)
    state = rec.RecursiveState(name,p,bound)
    for i,timestamp in enumerate(idx):
        row = {"frame":{key:series.iloc[i] for key,series in data["frame"].items()}}
        assert state.step(row,event_time=timestamp,reset_reasons=resets[i])["value"] == batch["value"].iloc[i]
        document = json.loads(json.dumps(state.snapshot(),allow_nan=False))
        state = rec.RecursiveState.restore(name,p,bound,document)
        prefix = {"frame":{key:series.iloc[:i+1] for key,series in data["frame"].items()}}
        assert rec.evaluate(name,p,prefix,bound_contract=bound,resets=resets[:i+1])["value"].tolist() == batch["value"].iloc[:i+1].tolist()
    # Immutable numeric ingress distinguishes None (MISSING) from NaN (INVALID).
    assert batch["value"].iloc[7].state is I
    with pytest.raises(node_contracts.NodeContractRefusal):
        rec.RecursiveState.restore(name,p,binding(name,p,timeframe=60),document)
    for key, value in (("extra",0),("seen",True),("seen",99999),("last_time",None),("history",[1.]*5000),("poisoned",1)):
        damaged = deepcopy(document); damaged[key] = value
        with pytest.raises(node_contracts.NodeContractRefusal): rec.RecursiveState.restore(name,p,bound,damaged)
    for value in ("NaN","Infinity","1e99999999","1."+"0"*2000,"01"):
        damaged = deepcopy(document); damaged["numbers"][next(iter(damaged["numbers"]))] = value
        with pytest.raises(node_contracts.NodeContractRefusal): rec.RecursiveState.restore(name,p,bound,damaged)


@pytest.mark.parametrize("name",NAMES)
def test_input_validity_and_refusals(name):
    p = parameters(name); bound = binding(name,p)
    timestamp = pd.Timestamp("2025-01-02T10:00:00Z")
    raw = {key:series.iloc[0] for key,series in frame()["frame"].items()}
    for field in rec.SPECS[name]["inputs"]:
        missing = dict(raw); del missing[field]
        with pytest.raises(node_contracts.NodeContractRefusal):
            rec.RecursiveState(name,p,bound).step({"frame":missing},event_time=timestamp)
        for value, want in ((float("nan"),I),(None,M),(float("inf"),I),(float("-inf"),I),(True,I)):
            invalid = dict(raw); invalid[field]=value
            got = rec.RecursiveState(name,p,bound).step({"frame":invalid},event_time=timestamp)["value"]
            assert got.state is want and got.value is None
    if "volume" in rec.SPECS[name]["inputs"]:
        invalid = dict(raw,volume=-1)
        assert rec.RecursiveState(name,p,bound).step({"frame":invalid},event_time=timestamp)["value"].state is I
    for altered in ({"peer":raw}, {}, {"frame":raw,"peer":raw}):
        with pytest.raises(node_contracts.NodeContractRefusal):
            rec.RecursiveState(name,p,bound).step(altered,event_time=timestamp)
    state = rec.RecursiveState(name,p,bound)
    with pytest.raises(node_contracts.NodeContractRefusal): state.step({"frame":raw},event_time=timestamp,event_kind="tick")
    with pytest.raises(node_contracts.NodeContractRefusal): state.step({"frame":raw},event_time="2025-01-01")
    with pytest.raises(node_contracts.NodeContractRefusal): state.step({"frame":raw},event_time=timestamp,reset_reasons=("SESSION",))
    state.step({"frame":raw},event_time=timestamp)
    with pytest.raises(node_contracts.NodeContractRefusal): state.step({"frame":raw},event_time=timestamp)


def test_undefined_cumulative_addend_is_not_skipped():
    data = frame([2.,0.,4.,8.,16.])
    compare(evaluate("PRICE_VOLUME_TREND",{},data),[0,-2,U,U,U],data["frame"]["close"].index)
    compare(evaluate("PRICE_VOLUME_TREND",{},data,resets=[(),(),(),("EXPLICIT",),()]),[0,-2,U,0,5],data["frame"]["close"].index)
    zeros = frame([0.,2.,4.])
    compare(evaluate("CUMULATIVE_RETURN",{},zeros),[U,U,U],zeros["frame"]["close"].index)


def test_small_returns_and_exact_zero_rsi():
    values = [1.+i*2**-52 for i in range(8)]
    data = frame(values)
    expected = [F(float(v))-1 for v in values]
    compare(evaluate("CUMULATIVE_RETURN",{},data),expected,data["frame"]["close"].index)
    pvt = [F(0)]
    for i in range(1,len(values)):
        pvt.append(pvt[-1]+(F(values[i])-F(values[i-1]))/F(values[i-1])*(i+1))
    compare(evaluate("PRICE_VOLUME_TREND",{},data),pvt,data["frame"]["close"].index)
    compare(evaluate("RSI",{"window":2},data),[H,H]+[100]*6,data["frame"]["close"].index)


def test_kama_extended_lengths_from_rational_definition():
    data = frame([2.,4.,8.,4.,2.,9.,3.,1.,1.,1.,1.])
    prices = [F(v) for v in data["frame"]["close"]]
    for fast, slow in ((1,2),(3,7),(4095,4096)):
        expected = [H,H]
        previous = prices[1]
        for t in range(2,len(prices)):
            path = abs(prices[t]-prices[t-1])+abs(prices[t-1]-prices[t-2])
            er = F(1) if path == 0 else abs(prices[t]-prices[t-2])/path
            weight = (er*(F(2,fast+1)-F(2,slow+1))+F(2,slow+1))**2
            previous = previous*(1-weight)+prices[t]*weight
            expected.append(previous)
        compare(evaluate("KAMA",{"window":2,"fast_length":fast,"slow_length":slow},data),expected,data["frame"]["close"].index)


def test_sar_extended_factor_reversal_and_clamps():
    # C's initial clamp uses bar1 twice. With start=1/8, increment=1/4:
    # first SAR=1, next=1.75, then AF=3/8 -> next min(5.21875,3,7)=3;
    # equality penetration at bar3 reverses to EP=11, bar4 remains short.
    data = frame()
    compare(evaluate("PARABOLIC_SAR",{"start":.125,"increment":.25,"maximum":.75},data),
            [H,1,F(7,4),11,11],data["frame"]["close"].index)


from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.runtime import evaluate_v2
from app.ir.hashing import content_address
from app.ir.first_party.analytical_v2.contracts import canonical_input_bindings
from app.market_data.requirements import compile_data_requirement_plan, verify_data_requirement_plan


def through_runtime(name, parameters, inputs):
    """Build the real receipt without the candidate's parameter helper."""
    from app.ir.node_contracts import _plain
    key = ('analytical.' + name.lower(), 2)
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=rec.V2_TYPES,
        v2_components={key:rec.V2_COMPONENTS[key]}, node_contracts={key:rec.NODE_CONTRACTS[key]},
        contract_bindings={key:rec.CONTRACT_BINDINGS[key]}, v2_implementations={key:rec.V2_IMPLEMENTATIONS[key]})
    ports = _plain(rec.V2_COMPONENTS[key]['ports'])
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
    sources = {role:fact([field.upper() for field in columns])
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


@pytest.mark.parametrize("name",NAMES)
def test_actual_resolver_compiler_runtime(name):
    data=frame()
    compare(through_runtime(name,parameters(name),data),GOLDEN[name],data["frame"]["close"].index)
    # Resolver default parameters must replay through the evaluator unchanged.
    defaults=frame(count=34,flat=6.)
    expected=6. if name in {"EMA","RMA_WILDER","KAMA","PARABOLIC_SAR"} else 1. if name=="OBV" else 0.
    warmup=first(name,{})
    compare(through_runtime(name,{},defaults),[H]*warmup+[expected]*(34-warmup),defaults["frame"]["close"].index)


def test_integer_sar_parameters_replay_without_numeric_coercion():
    data=frame()
    for value in (1,1.):
        p={"start":value,"increment":value,"maximum":value}
        assert through_runtime("PARABOLIC_SAR",p,data)["value"].tolist()==evaluate("PARABOLIC_SAR",p,data)["value"].tolist()
    p={"start":1,"increment":1,"maximum":1}
    bound=binding("PARABOLIC_SAR",p);state=rec.RecursiveState("PARABOLIC_SAR",p,bound)
    doc=state.snapshot();doc["parameters"]["start"]=1.
    doc["payload_address"]=content_address({k:v for k,v in doc.items() if k!="payload_address"})
    with pytest.raises(node_contracts.NodeContractRefusal):rec.RecursiveState.restore("PARABOLIC_SAR",p,bound,doc)


@pytest.mark.parametrize("name",NAMES)
def test_wrong_role_binding_and_receipt_tamper(name):
    p=parameters(name);data=frame()
    with pytest.raises(node_contracts.NodeContractRefusal):
        bound=binding(name,p,alter=lambda src:src["instrument"].update(role="peer"))
        rec.evaluate(name,p,data,bound_contract=bound)
    good=binding(name,p)
    for key,value in (("warmup_history",0),("resource_profile",{}),("state_reset_policy",{"schema":"state-reset-policy/2","reasons":[]})):
        doc=node_contracts._plain(good.document);doc["resolved_contract"][key]=value
        doc["bound_contract_address"]=content_address({k:v for k,v in doc.items() if k!="bound_contract_address"})
        forged=ResolvedNodeContract(doc,doc["bound_contract_address"])
        if key=="warmup_history" and first(name,p)==0:continue
        with pytest.raises(node_contracts.NodeContractRefusal):rec.evaluate(name,p,data,bound_contract=forged)


@pytest.mark.parametrize("name",NAMES)
def test_extreme_constants_and_impulse_decay(name):
    for level in (math.ldexp(1.,-500),math.ldexp(1.,500),-math.ldexp(1.,500),math.ulp(0.)):
        data=frame(count=36,flat=level)
        p=parameters(name)
        target=level if name in {"EMA","RMA_WILDER","KAMA","PARABOLIC_SAR"} else 1. if name=="OBV" else 0.
        compare(evaluate(name,p,data),[H]*first(name,p)+[target]*(36-first(name,p)),data["frame"]["close"].index)


@pytest.mark.parametrize("name",["EMA","RMA_WILDER","PRICE_MA_DISTANCE","MA_SLOPE"])
@pytest.mark.parametrize("window",[2,14,4096])
def test_impulse_and_monotone_closed_form(name,window):
    # Seed on a ramp, then remain at its seed mean: exact fixed point. An
    # impulse of 1 after seed has geometric weights, written independently.
    seed=F(window+1,2)
    prices=[float(i+1) for i in range(window)]+[float(seed+1)]+[float(seed)]*8
    weight=F(1,window) if name=="RMA_WILDER" else F(2,window+1)
    means=[seed]+[seed+weight*(1-weight)**i for i in range(9)]
    expected=[H]*(window-1)
    for k,value in enumerate(means):
        if name=="MA_SLOPE":expected.append(H if k==0 else value-means[k-1])
        elif name=="PRICE_MA_DISTANCE":expected.append(F(prices[window-1+k])-value)
        else:expected.append(value)
    data=frame(prices)
    compare(evaluate(name,{"window":window},data),expected,data["frame"]["close"].index)


@pytest.mark.parametrize("name",NAMES)
@pytest.mark.parametrize("variant",["default","maximum"])
def test_restart_at_parameter_domain_boundaries(name,variant):
    p={} if variant=="default" else parameters(name,4096)
    if variant=="maximum" and name=="CHAIKIN_OSCILLATOR":p={"fast_length":4095,"slow_length":4096}
    if variant=="maximum" and name=="KAMA":p.update(fast_length=4095,slow_length=4096)
    first_bar=first(name,p);count=first_bar+5
    data=frame(count=count,flat=7.)
    bound=binding(name,p);state=rec.RecursiveState(name,p,bound)
    empty=state.snapshot();state=rec.RecursiveState.restore(name,p,bound,json.loads(json.dumps(empty)))
    target=7. if name in {"EMA","RMA_WILDER","KAMA","PARABOLIC_SAR"} else 1. if name=="OBV" else 0.
    for i,timestamp in enumerate(data["frame"]["close"].index):
        row={"frame":{key:series.iloc[i] for key,series in data["frame"].items()}}
        cell=state.step(row,event_time=timestamp)["value"]
        assert cell.state is (H if i<first_bar else ValidityState.VALID)
        if i>=first_bar:assert cell.value==target
        if i in {0,first_bar-1,first_bar,first_bar+1,count-1}:
            snapshot=json.loads(json.dumps(state.snapshot(),allow_nan=False))
            state=rec.RecursiveState.restore(name,p,bound,snapshot)


@pytest.mark.parametrize("name",NAMES)
def test_invalid_and_explicit_reset_restart_known_warmup(name):
    p=parameters(name);warmup=first(name,p);count=warmup*3+9
    data=frame(count=count,flat=6.)
    invalid_bar=warmup+2;reset_bar=2*warmup+6
    field=rec.SPECS[name]["inputs"][0];data["frame"][field].iloc[invalid_bar]=float("inf")
    resets=[()]*count;resets[reset_bar]=("EXPLICIT",)
    target=6. if name in {"EMA","RMA_WILDER","KAMA","PARABOLIC_SAR"} else 1. if name=="OBV" else 0.
    expected=[];age=0
    for i in range(count):
        if i==invalid_bar:expected.append(I);age=0;continue
        if i==reset_bar:age=0
        expected.append(H if age<warmup else target);age+=1
    compare(evaluate(name,p,data,resets=resets),expected,data["frame"]["close"].index)


def test_pinned_directional_seed_intermediate_states():
    data=frame();bound=binding("ADX",{"window":2});state=rec.RecursiveState("ADX",{"window":2},bound)
    expected=[(0,0,0,0,0),(2,0,5,0,0),(5,0,F(19,2),100,0),
              (F(5,2),4,F(39,4),0,F(800,13)),(F(5,4),4,F(71,8),0,F(15550,273))]
    for i,timestamp in enumerate(data["frame"]["close"].index):
        state.step({"frame":{k:s.iloc[i] for k,s in data["frame"].items()}},event_time=timestamp)
        saved=state.snapshot()["numbers"]
        for key,want in zip(("plus","minus","tr","dx_sum","adx"),expected[i]):
            got=float(decimal.Decimal(saved[key]));assert abs(got-float(want))<=1e-12,(i,key,got,want)


@pytest.mark.parametrize("name",NAMES)
def test_named_field_index_contract(name):
    data=frame();p=parameters(name);field=rec.SPECS[name]["inputs"][0]
    for index in (pd.RangeIndex(5),pd.date_range("2025-01-01",periods=5),pd.DatetimeIndex([pd.Timestamp("2025-01-01T00:00:00Z")]*5)):
        changed=deepcopy(data);changed["frame"][field].index=index
        with pytest.raises(node_contracts.NodeContractRefusal):evaluate(name,p,changed)
    if len(rec.SPECS[name]["inputs"])>1:
        changed=deepcopy(data);changed["frame"][field].index+=pd.Timedelta(seconds=1)
        with pytest.raises(node_contracts.NodeContractRefusal):evaluate(name,p,changed)


def test_adosc_near_equal_maximum_lengths_closed_form():
    # AD_t=-(t+1), seeded at -1. EMA(n)_t=AD_t+(n-1)/2*(1-(1-2/(n+1))**t).
    # This independent closed form avoids recurrence/implementation reuse.
    data=frame([100.]*8210);data["frame"]["volume"][:]=2.
    expected=[H]*4095
    with decimal.localcontext() as context:
        context.prec=120
        rf=1-decimal.Decimal(2)/4096;rs=1-decimal.Decimal(2)/4097
        for t in range(4095,8210):
            expected.append(float(decimal.Decimal(4094)/2*(1-rf**t)-decimal.Decimal(4095)/2*(1-rs**t)))
    compare(evaluate("CHAIKIN_OSCILLATOR",{"fast_length":4095,"slow_length":4096},data),expected,data["frame"]["close"].index)
