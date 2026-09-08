from dataclasses import replace
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).parent))
from foundation_native_state_contract import *
from foundation_native_state_declarations import declaration,scenario
def expected(dialect=Dialect.SQLITE,ident="owner-alpha"): return ExpectedNativeState.from_caller(scenario(dialect,ident),declaration(dialect))
def observed(e):
 tables=tuple(ObservedTableState(x.table.name,x.rows,x.owner_attribution,x.digest) for x in e.tables)
 return ObservedNativeState(e.scenario_id,e.dialect,tables,e.marker,e.schema_cookie,e.sequence_state,e.sequence_bindings,ObservedCatalogState(e.catalog.facts,"catalog"),e.authority,e.digest)
def test_closed_types_and_strict_wire_roundtrip():
 e=expected(); assert strict_from_wire(strict_to_wire(e))==e
 w=strict_to_wire(e); w["fields"].pop("digest")
 with pytest.raises(ValueError): strict_from_wire(w)
 w=strict_to_wire(e); w["fields"]["unknown"]=1
 with pytest.raises(ValueError): strict_from_wire(w)
def test_expected_set_precedes_locator_lease():
 states=tuple(expected(d,o) for d in Dialect for o in ("owner-alpha","owner-beta")); receipt=ExpectationSetReceipt(states,domain_digest("receipt",states)); plan=compile_observation_plan(receipt,"owner-alpha",Dialect.SQLITE)
 assert issue_locator_lease(receipt,plan,"opaque").locator=="opaque"
 with pytest.raises(ValueError): issue_locator_lease(ExpectationSetReceipt(states[:3],"short"),plan,"opaque")
def test_expected_constructor_rejects_observed_sources():
 with pytest.raises(TypeError): ExpectedNativeState.from_caller(observed(expected()),declaration(Dialect.SQLITE))
def test_comparator_rejects_each_native_state_fact():
 e=expected(); o=observed(e); assert compare_native_state(e,o).equal
 changes={"tables":replace(o,tables=()),"marker":replace(o,marker="bad"),"schema_cookie":replace(o,schema_cookie=1),"sequence_state":replace(o,sequence_state={"x":(1,None)}),"sequence_bindings":replace(o,sequence_bindings=()),"catalog":replace(o,catalog=ObservedCatalogState(("bad",),"x")),"authority":replace(o,authority="bad"),"digest":replace(o,digest="bad")}
 for name,changed in changes.items(): assert name in compare_native_state(e,changed).differences
