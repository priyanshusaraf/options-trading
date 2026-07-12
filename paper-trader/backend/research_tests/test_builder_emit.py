"""The emitter turns a Composition into real, readable `compute(df, **params)` Python
source that references ONLY whitelisted blocks and returns the four canonical columns.
The source must be syntactically valid and structurally minimal (one function, no
imports, no attribute/subscript escapes) so the AST validator can vet it."""
import ast

from research.strategy.builder.emit import emit_source
from research.strategy.builder.grammar import Composition

_SPEC = {
    "key": "gen_trend_z_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}


def test_emitted_source_is_valid_python():
    src = emit_source(Composition.from_dict(_SPEC))
    compile(src, "<gen>", "exec")            # must parse & compile


def test_emitted_source_has_single_compute_function():
    src = emit_source(Composition.from_dict(_SPEC))
    tree = ast.parse(src)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert len(tree.body) == 1 and len(funcs) == 1 and funcs[0].name == "compute"


def test_emitted_source_references_the_blocks_and_canonical_columns():
    src = emit_source(Composition.from_dict(_SPEC))
    for block in ("ema_slope_up", "zscore_cross_up", "zscore_lt", "zscore_gt"):
        assert block + "(df," in src.replace(" ", "").replace("df,", "df, ") or block in src
    for col in ("longEntry", "shortEntry", "longExit", "shortExit"):
        assert col in src


def test_emitted_source_has_no_imports_or_dunders():
    src = emit_source(Composition.from_dict(_SPEC))
    assert "import" not in src
    assert "__" not in src


def test_all_clause_uses_and_any_clause_uses_or():
    src = emit_source(Composition.from_dict(_SPEC))
    tree = ast.parse(src)
    assigns = {t.id: n.value for n in ast.walk(tree)
               if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    # an "all" clause with 2 blocks -> BitAnd; "any" -> BitOr
    assert isinstance(assigns["longEntry"], ast.BinOp)
    assert isinstance(assigns["longEntry"].op, ast.BitAnd)
    assert isinstance(assigns["longExit"].op, ast.BitOr)
