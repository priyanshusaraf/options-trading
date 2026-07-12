"""Composition → real Python source.

The emitter templates a Composition into a single `compute(df, **params)` function that
references ONLY whitelisted block names, combines them with `&` (all) / `|` (any), and
returns the four canonical boolean columns as a dict. The output is deliberately
minimal — one function, no imports, no attribute access, no subscripting — so the AST
validator can prove it safe and the owner can read exactly what a generated strategy
does. The block arg values are baked in as numeric literals (the composition IS the
parameterization).
"""
from __future__ import annotations

from research.strategy.builder.grammar import Clause, Composition, ref_to_str

_COLUMNS = (("longEntry", "long_entry"), ("shortEntry", "short_entry"),
            ("longExit", "long_exit"), ("shortExit", "short_exit"))


def _ref_call(ref) -> str:
    # ref_to_str -> "ema_slope_up(50, 5)"; inject df as the first argument
    name, _, rest = ref_to_str(ref).partition("(")
    return f"{name}(df, {rest}" if rest != ")" else f"{name}(df)"


def _clause_expr(clause: Clause) -> str:
    joiner = " & " if clause.op == "all" else " | "
    parts = [_ref_call(r) for r in clause.refs]
    return joiner.join(parts) if len(parts) == 1 else "(" + joiner.join(parts) + ")"


def emit_source(comp: Composition) -> str:
    """Return the `compute(df, **params)` source for `comp`."""
    lines = ["def compute(df, **params):"]
    for col, attr in _COLUMNS:
        lines.append(f"    {col} = {_clause_expr(getattr(comp, attr))}")
    lines.append("    return {")
    for col, _ in _COLUMNS:
        lines.append(f'        "{col}": {col},')
    lines.append("    }")
    return "\n".join(lines) + "\n"
