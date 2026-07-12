"""The declarative Composition spec + strict block-reference parsing.

A generated strategy is a Composition: four boolean clauses (long/short entry/exit),
each an AND (`all`) or OR (`any`) over block references. A reference is the compact
string form the design uses — `"ema_slope_up(50, 5)"` — parsed here into a structured
`BlockRef(name, args)`.

Parsing is a security gate in its own right: it accepts ONLY a single call to a
whitelisted block name with bounded positional NUMERIC args. An unknown name, a
non-numeric arg, keyword args, the wrong arity, or an out-of-bounds value all raise
before the ref can reach the emitter. `ast.parse` in `eval` mode is used purely to read
the literal — nothing is ever evaluated.
"""
from __future__ import annotations

import ast
import dataclasses

from research.strategy.builder.blocks import BLOCKS

# per-kind bounds — keep generated params sane (and warmups finite)
_LENGTH_MIN, _LENGTH_MAX = 2, 400
_THR_ABS_MAX = 10.0
_PCT_MIN, _PCT_MAX = 0.0, 100.0
_MULT_MIN, _MULT_MAX = 0.0, 20.0


@dataclasses.dataclass(frozen=True)
class BlockRef:
    name: str
    args: tuple


@dataclasses.dataclass(frozen=True)
class Clause:
    op: str            # "all" | "any"
    refs: tuple        # tuple[BlockRef], length >= 1


@dataclasses.dataclass(frozen=True)
class Composition:
    key: str
    long_entry: Clause
    short_entry: Clause
    long_exit: Clause
    short_exit: Clause

    def clauses(self) -> tuple:
        return (self.long_entry, self.short_entry, self.long_exit, self.short_exit)

    def block_refs(self) -> list:
        return [r for c in self.clauses() for r in c.refs]

    def max_warmup(self) -> int:
        return max((BLOCKS[r.name].warmup(r.args) for r in self.block_refs()), default=0)

    def to_dict(self) -> dict:
        def clause(c: Clause) -> dict:
            return {c.op: [ref_to_str(r) for r in c.refs]}
        return {"key": self.key,
                "longEntry": clause(self.long_entry),
                "shortEntry": clause(self.short_entry),
                "longExit": clause(self.long_exit),
                "shortExit": clause(self.short_exit)}

    @staticmethod
    def from_dict(d: dict) -> "Composition":
        return Composition(
            key=d["key"],
            long_entry=_clause_from_obj(d["longEntry"]),
            short_entry=_clause_from_obj(d["shortEntry"]),
            long_exit=_clause_from_obj(d["longExit"]),
            short_exit=_clause_from_obj(d["shortExit"]))


def _const_number(node: ast.AST):
    """Read a numeric literal, allowing a leading unary minus (negative thresholds)."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_const_number(node.operand)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    raise ValueError("block args must be numeric literals")


def _check_kind(block: str, pname: str, kind: str, val) -> None:
    if kind == "length":
        if not isinstance(val, int) or not (_LENGTH_MIN <= val <= _LENGTH_MAX):
            raise ValueError(f"{block}.{pname}: length must be an int in "
                             f"[{_LENGTH_MIN},{_LENGTH_MAX}], got {val!r}")
    elif kind == "thr":
        if abs(val) > _THR_ABS_MAX:
            raise ValueError(f"{block}.{pname}: |thr| must be <= {_THR_ABS_MAX}")
    elif kind == "pct":
        if not (_PCT_MIN < val <= _PCT_MAX):
            raise ValueError(f"{block}.{pname}: pct must be in ({_PCT_MIN},{_PCT_MAX}]")
    elif kind == "mult":
        if not (_MULT_MIN < val <= _MULT_MAX):
            raise ValueError(f"{block}.{pname}: mult must be in ({_MULT_MIN},{_MULT_MAX}]")


def parse_ref(text: str) -> BlockRef:
    """Parse a compact block reference. Raises ValueError on anything but a call to a
    whitelisted block with the right count of bounded numeric args."""
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except SyntaxError as e:
        raise ValueError(f"unparseable block ref {text!r}: {e}") from None
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        raise ValueError(f"not a block call: {text!r}")
    if node.keywords:
        raise ValueError("block refs take positional args only")
    name = node.func.id
    spec = BLOCKS.get(name)
    if spec is None:
        raise ValueError(f"unknown block {name!r}")
    args = tuple(_const_number(a) for a in node.args)
    if len(args) != len(spec.params):
        raise ValueError(f"{name} expects {len(spec.params)} args, got {len(args)}")
    for (pname, kind), val in zip(spec.params, args):
        _check_kind(name, pname, kind, val)
    return BlockRef(name, args)


def _clause_from_obj(o: dict) -> Clause:
    if "all" in o:
        op, items = "all", o["all"]
    elif "any" in o:
        op, items = "any", o["any"]
    else:
        raise ValueError("clause must have an 'all' or 'any' key")
    refs = tuple(parse_ref(r) for r in items)
    if not refs:
        raise ValueError("clause must reference at least one block")
    return Clause(op, refs)


def _fmt(val) -> str:
    return repr(val)


def ref_to_str(ref: BlockRef) -> str:
    return f"{ref.name}({', '.join(_fmt(a) for a in ref.args)})"
