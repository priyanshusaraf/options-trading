"""Declaration-only test inputs; no database authority appears here."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from foundation_native_state_contract import *
def declaration(dialect):
 table=FrozenTableDeclaration("example",(FrozenColumnDeclaration("id","integer",False),),("id",),(),OwnerPolicy(OwnerPolicyKind.DIRECT,("id",)))
 # One real declared sequence: with an empty sequences tuple the comparator's
 # "sequence_bindings" check compares () to () and the mutation test for that
 # fact is vacuous (DP-014 shape — presence mistaken for witness authority).
 sequences=(SequenceDeclaration("example_id_seq","example","id",True),)
 return FrozenDialectDeclaration(dialect,(table,),"0011" if dialect is Dialect.SQLITE else "0010",68 if dialect is Dialect.SQLITE else None,sequences,FrozenCatalogDeclaration(("example-table",)),"frozen-test-authority")
def scenario(dialect,scenario_id): return CallerScenario(scenario_id,dialect,(CallerTableRows("example",((NativeScalar(NativeTag.INTEGER,1),),),(("owner",),)),),{})
