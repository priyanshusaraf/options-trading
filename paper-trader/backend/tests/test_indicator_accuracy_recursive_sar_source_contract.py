"""Source/consumer regressions for the explicitly corrected mathematical SAR.

Historical native failures remain in their immutable independent suite. These
tests do not claim native parity or create numerical expected vectors.
"""
from copy import deepcopy
import json
import pandas as pd
import pytest

from app.ir import hashing,node_contracts
from app.ir.first_party.analytical_v2 import recursive_state as rec
from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract,canonical_input_bindings
from app.ir.registry import PlatformRegistry
from app.ir.resolve import ResolutionError,resolve_v2
from app.ir.runtime import evaluate_v2
from app.market_data.requirements import compile_data_requirement_plan,verify_data_requirement_plan

DECISION_ADDRESS='sha256:4d5d654326d8665fc94f44aaf08736305d59843e2cd9ecbd726de143ebec5e0e'


def data(count=40):
    index=pd.date_range('2026-08-20T00:00:00Z',periods=count,freq='min')
    close=[100.+(i*7%19)/4 for i in range(count)]
    return {'frame':{'close':pd.Series(close,index=index),'high':pd.Series([v+3 for v in close],index=index),
                     'low':pd.Series([v-1 for v in close],index=index),'volume':pd.Series([float(i+1) for i in range(count)],index=index)}}


def compiled(name='PARABOLIC_SAR',parameters=None):
    parameters={} if parameters is None else parameters
    key=rec.component_key(name)
    registry=PlatformRegistry(components={},bodies={},registrations={},v2_types=rec.V2_TYPES,
        v2_components={key:rec.V2_COMPONENTS[key]},node_contracts={key:rec.NODE_CONTRACTS[key]},
        contract_bindings={key:rec.CONTRACT_BINDINGS[key]},v2_implementations={key:rec.V2_IMPLEMENTATIONS[key]})
    ports=node_contracts._plain(rec.V2_COMPONENTS[key]['ports'])
    doc={'format_version':2,'strategy_id':'sar-source-contract-proof','strategy_version':1,
         'metadata':{'metadata_version':1,'name':'Source contract proof','description':None,'tags':[]},
         'graph_inputs':[p for p in ports if p['direction']=='input'],'graph_outputs':[p for p in ports if p['direction']=='output'],
         'nodes':[{'node_id':'n','component':{'component_id':key[0],'component_version':2},'parameters':parameters}],
         'edges':[{'edge_id':'in','source':{'scope':'graph_input','port_id':'frame'},'target':{'scope':'node','node_id':'n','port_id':'frame'},'binding':{'kind':'single'}},
                  {'edge_id':'out','source':{'scope':'node','node_id':'n','port_id':'value'},'target':{'scope':'graph_output','port_id':'value'},'binding':{'kind':'single'}}]}
    address=lambda tag:hashing.content_address({'source_contract_fixture':tag})
    f={'schema':'canonical-input-binding/1','owner_id':'org.source-contract-fixture',
       **{k:address(k) for k in ('dataset_context_address','evaluation_context_address','dataset_manifest_address','market_truth_address','provider_product_address','provider_contract_address','canonical_instrument_address')},
       'instrument':{'role':'primary','type':'PHYSICAL'},'timeframe':60,'fields':list(rec.fields_by_port(name)['frame']),
       'freshness':{'maximum_age_seconds':60},'depth':{'kind':'NONE','levels':None},'session':'INSTRUMENT_CALENDAR',
       'alignment':{'kind':'EXACT','maximum_skew_seconds':0},'derived_local':False}
    context=canonical_input_bindings(owner_id=f['owner_id'],dataset_context_address=f['dataset_context_address'],evaluation_context_address=f['evaluation_context_address'],
        bindings={'frame':f},expected_source_addresses={'frame':hashing.content_address(f)})
    graph=resolve_v2(doc,registry)
    plan=compile_data_requirement_plan(graph,registry=registry,input_bindings=context)
    verify_data_requirement_plan(plan,graph,registry=registry,input_bindings=context)
    receipt=node_contracts._plain(plan.parameter_binding_provenance[0]['node_contract_binding'])
    bound=ResolvedNodeContract(receipt,receipt['bound_contract_address'])
    return graph,registry,context,plan,bound


def test_explicit_mathematical_source_provenance():
    target=rec.SPECS['PARABOLIC_SAR']
    assert target['source']=='SPEC' and target['variant']=='parabolic_sar-mathematical-v2'
    assert DECISION_ADDRESS in target['source_addresses']
    assert DECISION_ADDRESS in rec.source_contract('PARABOLIC_SAR')['reference_provenance']
    assert 'no universal binary64 TA-Lib parity claim' in target['zero_undefined_policy']
    assert 'Strict TA parity applies when start=increment' not in target['zero_undefined_policy']


@pytest.mark.parametrize('parameters',[{}, {'start':1,'increment':1,'maximum':1}, {'start':.125,'increment':.25,'maximum':.75}])
def test_corrected_claim_reaches_actual_compiler_and_runtime(parameters):
    graph,registry,context,plan,bound=compiled(parameters=parameters)
    assert DECISION_ADDRESS in bound.document['resolved_contract']['reference_provenance']
    assert bound.document['source_contract_address']==rec.CONTRACT_BINDINGS[rec.component_key('PARABOLIC_SAR')].source_contract_address
    output=evaluate_v2(graph,data(),registry,evaluation_context_resolver=lambda n,inputs:{'bound_contract':bound})
    direct=rec.evaluate('PARABOLIC_SAR',parameters,data(),bound_contract=bound)
    assert output['value'].tolist()==direct['value'].tolist()
    assert output['value'].iloc[0].value is None and all(v.value is not None for v in output['value'].iloc[1:])


def test_caller_cannot_assert_native_parity_as_a_parameter():
    with pytest.raises(ResolutionError):compiled(parameters={'native_parity':True})


# Frozen OLD_SAR constants below are generated from a verified real compiler
# receipt and real stream checkpoint BEFORE the source correction. They are
# identity fixtures, not numerical expected vectors or fabricated hashes.
def test_real_old_sar_receipt_refuses_at_actual_runtime():
    graph,registry,context,plan,bound=compiled()
    old=ResolvedNodeContract(deepcopy(OLD_SAR_RECEIPT),OLD_SAR_RECEIPT['bound_contract_address'])
    assert hashing.content_address({k:v for k,v in OLD_SAR_RECEIPT.items() if k!='bound_contract_address'})==old.bound_contract_address
    assert old.bound_contract_address!=bound.bound_contract_address
    with pytest.raises(node_contracts.NodeContractRefusal):
        evaluate_v2(graph,data(),registry,evaluation_context_resolver=lambda n,inputs:{'bound_contract':old})


def test_real_old_sar_state_refuses_new_source_identity():
    graph,registry,context,plan,bound=compiled()
    assert hashing.content_address({k:v for k,v in OLD_SAR_STATE.items() if k!='payload_address'})==OLD_SAR_STATE['payload_address']
    with pytest.raises(node_contracts.NodeContractRefusal):
        rec.RecursiveState.restore('PARABOLIC_SAR',dict(graph.nodes[0].parameters),bound,deepcopy(OLD_SAR_STATE))
    state=rec.RecursiveState('PARABOLIC_SAR',dict(graph.nodes[0].parameters),bound)
    rows=data(3)
    for i,t in enumerate(rows['frame']['close'].index):state.step({'frame':{k:s.iloc[i] for k,s in rows['frame'].items()}},event_time=t)
    fresh=json.loads(json.dumps(state.snapshot(),allow_nan=False))
    assert rec.RecursiveState.restore('PARABOLIC_SAR',dict(graph.nodes[0].parameters),bound,fresh).snapshot()==fresh


OLD_SAR_RECEIPT = {'binding_implementation_address': 'sha256:c2f3835d57eeb3b334b9dfc14d6861217194b60a20fcbfd135c9562c93f2d99a',
 'bound_contract_address': 'sha256:837102ae8cfa82b891be7600e3c6714be973f3134a4f9fab6693ba516097111e',
 'bound_requirements': [{'alignment': {'kind': 'EXACT', 'maximum_skew_seconds': 0},
                         'depth': {'kind': 'NONE', 'levels': None},
                         'derived_local': False,
                         'field': 'HIGH',
                         'freshness': {'maximum_age_seconds': 60},
                         'history': {'minimum_bars': 1, 'warmup_bars': 1},
                         'instrument': {'role': 'primary', 'type': 'PHYSICAL'},
                         'requirement_id': 'frame_high',
                         'session': 'INSTRUMENT_CALENDAR',
                         'timeframe': 60},
                        {'alignment': {'kind': 'EXACT', 'maximum_skew_seconds': 0},
                         'depth': {'kind': 'NONE', 'levels': None},
                         'derived_local': False,
                         'field': 'LOW',
                         'freshness': {'maximum_age_seconds': 60},
                         'history': {'minimum_bars': 1, 'warmup_bars': 1},
                         'instrument': {'role': 'primary', 'type': 'PHYSICAL'},
                         'requirement_id': 'frame_low',
                         'session': 'INSTRUMENT_CALENDAR',
                         'timeframe': 60}],
 'component': {'component_id': 'analytical.parabolic_sar', 'component_version': 2},
 'input_binding': {'context_address': 'sha256:c7ff3ccd3c7a3df27edf0800bf721a804e44671ec81411070c39bd5b649dd157',
                   'dataset_context_address': 'sha256:6cbcc10e09fe832f7b63fb87745643bdb0455611482b993142ad4d4a5a856d2b',
                   'evaluation_context_address': 'sha256:3807509b8d9ae16bc13cffba7ad6065ad3e1a53a16a143feb16e33baab0543e6',
                   'owner_id': 'org.source-contract-fixture',
                   'ports': {'frame': {'binding': {'alignment': {'kind': 'EXACT',
                                                                 'maximum_skew_seconds': 0},
                                                   'canonical_instrument_address': 'sha256:d50229a4ff74e02dc2c1a4393d25bef16f1baefa2be4b956472d182186a50182',
                                                   'dataset_context_address': 'sha256:6cbcc10e09fe832f7b63fb87745643bdb0455611482b993142ad4d4a5a856d2b',
                                                   'dataset_manifest_address': 'sha256:c4608986d5d49f3ae8b3237ca3b32de58c36a2aa6985f241483b4a64097e0cea',
                                                   'depth': {'kind': 'NONE', 'levels': None},
                                                   'derived_local': False,
                                                   'evaluation_context_address': 'sha256:3807509b8d9ae16bc13cffba7ad6065ad3e1a53a16a143feb16e33baab0543e6',
                                                   'fields': ['HIGH', 'LOW'],
                                                   'freshness': {'maximum_age_seconds': 60},
                                                   'instrument': {'role': 'primary',
                                                                  'type': 'PHYSICAL'},
                                                   'market_truth_address': 'sha256:1385c2b34ff82570b11c713194db0b26b3e5540e6da965e3db43e9a125e5d871',
                                                   'owner_id': 'org.source-contract-fixture',
                                                   'provider_contract_address': 'sha256:48732d2249fd99d1e7e2de8bbdf8cfd203f303a0614a1b19f1813c7a96f38671',
                                                   'provider_product_address': 'sha256:9be6fa3267185e8f008c9315ddb940e4899addc95a9771e37dc151759655bab3',
                                                   'schema': 'canonical-input-binding/1',
                                                   'session': 'INSTRUMENT_CALENDAR',
                                                   'timeframe': 60},
                                       'binding_address': 'sha256:0f00107260eea09e58d69bf47cdafea95d1900db4d79f1fb2a4c3d615a4d1b87',
                                       'source': {'port_id': 'frame', 'scope': 'graph_input'}}},
                   'schema': 'node-input-binding/1'},
 'parameters': {'increment': 0.02, 'maximum': 0.2, 'start': 0.02},
 'resolved_contract': {'bar_policy': 'COMPLETED_ONLY',
                       'batch_support': True,
                       'causal_declaration': 'COMPLETED_EVENT_PREFIX',
                       'evaluation_triggers': ['completed_bar'],
                       'execution_form': 'RECURSIVE',
                       'input_types': {'frame': 'analytical.market_frame/series'},
                       'missing_data_policy': 'PROPAGATE',
                       'mode_eligibility': {'live': False, 'paper': False, 'research': True},
                       'numeric_validity_policy': 'EXPLICIT_VALIDITY',
                       'output_types': {'value': 'analytical.float64/series'},
                       'output_warmup': {'value': 1},
                       'provider_requirements': [],
                       'reference_provenance': ['sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                                'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                                'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                                'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                                'sha256:b025f526992ba240b329d2ef5124cc73dcb9c4e5970a12e812ad2f863ec8ea5a',
                                                'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                                'sha256:e6a9d8379d2b007464259896389fa287102301259697695baaf1ee01aba29a9b'],
                       'required_market_fields': ['high', 'low'],
                       'required_resolution': {'alignment': 'BAR_CLOSE', 'timeframe_seconds': 60},
                       'resource_profile': {'compute_microseconds_per_event': 200000,
                                            'fanout_upper_bound': 1,
                                            'history_bytes_upper_bound': 66048,
                                            'memory_bytes_upper_bound': 1050624,
                                            'state_bytes_upper_bound': 131584,
                                            'storage_bytes_per_day_upper_bound': 0,
                                            'subscription_count_upper_bound': 1},
                       'semantic_version': 2,
                       'stable_node_id': 'analytical.parabolic_sar',
                       'state_initialization': {'initial_state_address': None,
                                                'schema': 'state-initialization/1'},
                       'state_reset_policy': {'reasons': ['DATA_GAP',
                                                          'EXPLICIT',
                                                          'IDENTITY_CHANGE'],
                                              'schema': 'state-reset-policy/2'},
                       'streaming_support': True,
                       'visible_family': 'TYPE_2',
                       'warmup_history': 1},
 'schema': 'resolved-node-contract/1',
 'source_contract_address': 'sha256:6a85c3548e38697ee04f2935a4aba917411b6b12177b37814645bfeba13f1168'}

OLD_SAR_STATE = {'bound_contract_address': 'sha256:837102ae8cfa82b891be7600e3c6714be973f3134a4f9fab6693ba516097111e',
 'component': ['analytical.parabolic_sar', 2],
 'history': [],
 'last_time': '2026-08-20T00:01:00+00:00',
 'long': True,
 'numbers': {'af': '0.0200000000000000004163336342344337026588618755340576171875',
             'ep': '104.75',
             'sar': '99.115000000000000002393918396847993790288455784320831298828125'},
 'parameters': {'increment': 0.02, 'maximum': 0.2, 'start': 0.02},
 'payload_address': 'sha256:031c591f2f02eb1f3bfbbc93db9c04c1b515f9915526f451ce5f40e3670ed923',
 'poisoned': False,
 'previous': {'high': 104.75, 'low': 100.75},
 'schema': 'analytical-recursive-state/2',
 'seen': 2}
