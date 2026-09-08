"""Pure immutable native-state contract.  It deliberately imports no database code."""
from __future__ import annotations
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

class Dialect(str, Enum): SQLITE="sqlite"; POSTGRESQL16="postgresql16"
class NativeTag(str, Enum): NULL="null"; INTEGER="integer"; REAL="real"; TEXT="text"; BLOB="blob"; BOOLEAN="boolean"
class OwnerPolicyKind(str, Enum): DIRECT="direct"; JOIN="join"; OWNERLESS="ownerless"; CLASSIFIED="classified"
DataObligation=Enum("DataObligation",{f"DATA_{i:02d}":f"DATA-{i:02d}" for i in range(1,25)},type=str)
CatalogObligation=Enum("CatalogObligation",{f"CAT_{i:02d}":f"CAT-{i:02d}" for i in range(1,40)},type=str)
def _freeze(v):
    if isinstance(v,Mapping): return MappingProxyType({str(k):_freeze(x) for k,x in v.items()})
    if isinstance(v,(list,tuple)): return tuple(_freeze(x) for x in v)
    if isinstance(v,(bytearray,memoryview)): return bytes(v)
    return v
def frozen(cls):
    original=getattr(cls,"__post_init__",None)
    def post(self):
        if original: original(self)
        for f in fields(self): object.__setattr__(self,f.name,_freeze(getattr(self,f.name)))
    cls.__post_init__=post; return dataclass(frozen=True)(cls)
@frozen
class NativeScalar: tag:NativeTag; value:Any
@frozen
class FrozenColumnDeclaration: name:str; declared_type:str; nullable:bool; default:NativeScalar|None=None
@frozen
class FrozenForeignKeyDeclaration: columns:tuple[str,...]; target_table:str; target_columns:tuple[str,...]
@frozen
class OwnerPolicy: kind:OwnerPolicyKind; owner_columns:tuple[str,...]=(); parent_table:str|None=None; parent_columns:tuple[str,...]=()
@frozen
class FrozenTableDeclaration: name:str; columns:tuple[FrozenColumnDeclaration,...]; primary_key:tuple[str,...]; foreign_keys:tuple[FrozenForeignKeyDeclaration,...]; owner_policy:OwnerPolicy
@frozen
class SequenceDeclaration: name:str; table:str; column:str; requires_is_called:bool
@frozen
class FrozenCatalogDeclaration: facts:tuple[str,...]
@frozen
class FrozenDialectDeclaration: dialect:Dialect; tables:tuple[FrozenTableDeclaration,...]; marker:str; schema_cookie:int|None; sequences:tuple[SequenceDeclaration,...]; catalog:FrozenCatalogDeclaration; authority:str
@frozen
class CallerTableRows: table:str; rows:tuple[tuple[NativeScalar,...],...]; owner_attribution:tuple[tuple[str|None,...],...]
@frozen
class CallerScenario: scenario_id:str; dialect:Dialect; table_rows:tuple[CallerTableRows,...]; sequence_state:Mapping[str,tuple[int,bool|None]]
@frozen
class ExpectedTableState: table:FrozenTableDeclaration; rows:tuple[tuple[NativeScalar,...],...]; owner_attribution:tuple[tuple[str|None,...],...]; digest:str
@frozen
class ExpectedNativeState:
    scenario_id:str; dialect:Dialect; declaration_digest:str; tables:tuple[ExpectedTableState,...]; marker:str; schema_cookie:int|None; sequence_state:Mapping[str,tuple[int,bool|None]]; sequence_bindings:tuple[SequenceDeclaration,...]; catalog:FrozenCatalogDeclaration; authority:str; digest:str
    @classmethod
    def from_caller(cls,scenario,declaration):
        if not isinstance(scenario,CallerScenario) or not isinstance(declaration,FrozenDialectDeclaration): raise TypeError("expected state accepts caller scenario and frozen declaration only")
        if scenario.dialect is not declaration.dialect: raise ValueError("dialect mismatch")
        supplied={r.table:r for r in scenario.table_rows}; names=tuple(t.name for t in declaration.tables)
        if set(supplied)!=set(names) or len(supplied)!=len(scenario.table_rows): raise ValueError("caller rows must cover each declared table exactly once")
        states=[]
        for table in declaration.tables:
            rows=supplied[table.name]
            if any(len(row)!=len(table.columns) for row in rows.rows) or len(rows.rows)!=len(rows.owner_attribution): raise ValueError("invalid caller table rows")
            states.append(ExpectedTableState(table,rows.rows,rows.owner_attribution,domain_digest("STRATEGY_OS_FOUNDATION_NATIVE_TABLE_V1\\0",(table,rows.rows,rows.owner_attribution))))
        dd=domain_digest("STRATEGY_OS_FOUNDATION_NATIVE_DECLARATION_V1\\0",declaration)
        payload=(scenario.scenario_id,scenario.dialect,dd,tuple(states),declaration.marker,declaration.schema_cookie,scenario.sequence_state,declaration.sequences,declaration.catalog,declaration.authority)
        return cls(scenario.scenario_id,scenario.dialect,dd,tuple(states),declaration.marker,declaration.schema_cookie,scenario.sequence_state,declaration.sequences,declaration.catalog,declaration.authority,domain_digest("STRATEGY_OS_FOUNDATION_NATIVE_STATE_V1\\0",payload))
@frozen
class ObservedTableState: table:str; rows:tuple[tuple[NativeScalar,...],...]; owner_attribution:tuple[tuple[str|None,...],...]; digest:str
@frozen
class ObservedCatalogState: facts:tuple[str,...]; digest:str
@frozen
class ObservedNativeState: scenario_id:str; dialect:Dialect; tables:tuple[ObservedTableState,...]; marker:str; schema_cookie:int|None; sequence_state:Mapping[str,tuple[int,bool|None]]; sequence_bindings:tuple[SequenceDeclaration,...]; catalog:ObservedCatalogState; authority:str; digest:str
@frozen
class ObservationPlan: scenario_id:str; dialect:Dialect; table_names:tuple[str,...]; sequence_names:tuple[str,...]; catalog_fact_names:tuple[str,...]
@frozen
class ExpectationSetReceipt: states:tuple[ExpectedNativeState,...]; digest:str
@frozen
class LocatorLease: receipt_digest:str; scenario_id:str; dialect:Dialect; locator:str
@frozen
class ObservationRequest: plan:ObservationPlan; lease:LocatorLease
@frozen
class ObservationResponse: observed:ObservedNativeState; request_digest:str
@frozen
class FreshProcessReceipt: parent_pid:int; child_pid:int; parent_nonce:str; child_nonce:str; request_digest:str; response_digest:str; observed_digest:str
@frozen
class ComparisonResult: equal:bool; differences:tuple[str,...]
@frozen
class DataConsumerSpec: obligation:DataObligation; table:str; rejection_code:str
@frozen
class CatalogConsumerSpec: obligation:CatalogObligation; fact:str; rejection_code:str
@frozen
class ObligationReceipt: obligation:str; accepted:bool; observed_digest:str
@frozen
class ClaimAttestation: receipts:tuple[ObligationReceipt,...]; digest:str
def strict_to_wire(value):
 def enc(v):
  if isinstance(v,Enum): return {"enum":v.__class__.__name__,"value":v.value}
  if isinstance(v,bytes): return {"bytes":v.hex()}
  if is_dataclass(v): return {"type":v.__class__.__name__,"fields":{f.name:enc(getattr(v,f.name)) for f in fields(v)}}
  if isinstance(v,Mapping): return {"mapping":[[k,enc(x)] for k,x in sorted(v.items())]}
  if isinstance(v,tuple): return {"tuple":[enc(x) for x in v]}
  if v is None or isinstance(v,(str,int,float,bool)): return v
  raise TypeError(f"unsupported strict wire value: {type(v).__name__}")
 wire=enc(value)
 # The root may be any COMPLETE encoded node — contract type, tuple,
 # mapping, bytes or enum — exactly the shapes strict_from_wire's decoder
 # consumes.  Rejecting every non-"type" root here made the module unable to
 # digest its own tuple payloads (ExpectedNativeState.from_caller).
 if (not isinstance(wire, Mapping) or set(wire) not in (
         {"type", "fields"}, {"tuple"}, {"mapping"},
         {"bytes"}, {"enum", "value"})):
  raise TypeError("strict wire root must be a contract type")
 return wire
_TYPES={n:v for n,v in globals().items() if isinstance(v,type) and is_dataclass(v)}; _ENUMS={n:v for n,v in globals().items() if isinstance(v,type) and issubclass(v,Enum)}
def strict_from_wire(wire):
 def dec(v):
  if v is None or isinstance(v,(str,int,float,bool)): return v
  if not isinstance(v,Mapping): raise ValueError("invalid strict wire shape")
  if set(v)=={"enum","value"}:
   if v["enum"] not in _ENUMS: raise ValueError("unknown enum")
   return _ENUMS[v["enum"]](v["value"])
  if set(v)=={"bytes"}: return bytes.fromhex(v["bytes"])
  if set(v)=={"tuple"}: return tuple(dec(x) for x in v["tuple"])
  if set(v)=={"mapping"}: return MappingProxyType({str(k):dec(x) for k,x in v["mapping"]})
  if set(v)=={"type","fields"}:
   cls=_TYPES.get(v["type"]); fs=v["fields"]
   if cls is None or not isinstance(fs,Mapping) or set(fs)!={f.name for f in fields(cls)}: raise ValueError("missing or unknown contract field")
   return cls(**{n:dec(x) for n,x in fs.items()})
  raise ValueError("invalid strict wire shape")
 return dec(wire)
def canonical_bytes(value): return json.dumps(strict_to_wire(value),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def domain_digest(domain,value): return sha256(domain.encode()+canonical_bytes(value)).hexdigest()
def compile_observation_plan(receipt,scenario_id,dialect):
 matches=[s for s in receipt.states if s.scenario_id==scenario_id and s.dialect is dialect]
 if len(matches)!=1: raise ValueError("receipt must contain exactly one expected state for plan")
 s=matches[0]; return ObservationPlan(scenario_id,dialect,tuple(x.table.name for x in s.tables),tuple(x.name for x in s.sequence_bindings),s.catalog.facts)
def issue_locator_lease(receipt,plan,locator):
 required={(d,o) for d in Dialect for o in ("owner-alpha","owner-beta")}; actual={(s.dialect,s.scenario_id) for s in receipt.states}
 if actual!=required or len(receipt.states)!=4: raise ValueError("all four expected states must finish before locator lease")
 if not isinstance(locator,str) or not locator or (plan.dialect,plan.scenario_id) not in actual: raise ValueError("invalid receipt-bound locator lease")
 return LocatorLease(receipt.digest,plan.scenario_id,plan.dialect,locator)
def compare_native_state(expected,observed):
 checks={"scenario":(expected.scenario_id,observed.scenario_id),"dialect":(expected.dialect,observed.dialect),"tables":(tuple((x.table.name,x.rows,x.owner_attribution,x.digest) for x in expected.tables),tuple((x.table,x.rows,x.owner_attribution,x.digest) for x in observed.tables)),"marker":(expected.marker,observed.marker),"schema_cookie":(expected.schema_cookie,observed.schema_cookie),"sequence_state":(expected.sequence_state,observed.sequence_state),"sequence_bindings":(expected.sequence_bindings,observed.sequence_bindings),"catalog":(expected.catalog.facts,observed.catalog.facts),"authority":(expected.authority,observed.authority),"digest":(expected.digest,observed.digest)}
 diffs=tuple(n for n,p in checks.items() if p[0]!=p[1]); return ComparisonResult(not diffs,diffs)
