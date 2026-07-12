"""The static security boundary over emitted strategy source.

Generated strategies are real Python that gets `exec`'d, so this validator is
fail-closed: it accepts ONLY the exact shape the emitter produces and rejects
everything else. Two passes, defense in depth:

  1. A global allow-list of AST node *types* — any node whose type is not in
     `_ALLOWED_NODES` (Import, Attribute, Subscript, Lambda, comprehensions, control
     flow, f-strings, …) is rejected outright, plus a scan that bans any identifier or
     string containing `__` (dunders / name-mangling breakouts).
  2. A structural pass: the module must be exactly one `def compute(df, **params)`
     whose body is a run of `name = <clause>` assignments (clauses are calls to
     whitelisted blocks combined only with `&`, `|`, `~`, and numeric literals) followed
     by a single `return { <canonical column> : <local> }`.

Combined with the no-builtins exec namespace in `load.py`, generated code is
structurally incapable of imports, I/O, attribute access, or calling anything but the
vetted block library.
"""
from __future__ import annotations

import ast

from research.strategy.builder.blocks import block_names

_CANONICAL = frozenset({"longEntry", "shortEntry", "longExit", "shortExit"})

# Every AST node type that may legally appear. Anything else → reject.
_ALLOWED_NODES = frozenset({
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg,
    ast.Assign, ast.Return, ast.Dict,
    ast.Call, ast.Name, ast.Constant,
    ast.BinOp, ast.BitAnd, ast.BitOr,
    ast.UnaryOp, ast.Invert, ast.USub,
    ast.Load, ast.Store,
})


class UnsafeStrategyError(ValueError):
    """Raised when emitted source violates the allow-list. Never suppress — a violation
    means the source could do something outside the vetted block grammar."""


def _is_dunder(s: str) -> bool:
    return "__" in s


def _reject(msg: str):
    raise UnsafeStrategyError(msg)


def _is_number(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float)) and not isinstance(node.value, bool))


def _check_call_arg(node: ast.AST) -> None:
    """A block arg is `df`, a numeric literal, or a negated numeric literal — nothing
    else (no nested calls, no other names, no expressions)."""
    if isinstance(node, ast.Name) and node.id == "df":
        return
    if _is_number(node):
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and _is_number(node.operand):
        return
    _reject("block arguments must be df or numeric literals")


def _check_clause(node: ast.AST, allowed: frozenset) -> None:
    """A clause expression: a whitelisted block call, or clauses combined with & / | / ~."""
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            _reject("only direct calls to named blocks are allowed")
        if node.func.id not in allowed:
            _reject(f"call to non-whitelisted name {node.func.id!r}")
        if node.keywords:
            _reject("block calls take positional args only")
        for a in node.args:
            _check_call_arg(a)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            _reject("clauses may combine only with & or |")
        _check_clause(node.left, allowed)
        _check_clause(node.right, allowed)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
        _check_clause(node.operand, allowed)
        return
    _reject(f"disallowed clause expression: {type(node).__name__}")


def _check_signature(fn: ast.FunctionDef) -> None:
    if fn.name != "compute":
        _reject("the single function must be named 'compute'")
    if fn.decorator_list:
        _reject("decorators are not allowed")
    if fn.returns is not None:
        _reject("return annotations are not allowed")
    a = fn.args
    if a.posonlyargs or a.kwonlyargs or a.kw_defaults or a.defaults or a.vararg:
        _reject("compute must be compute(df, **params) exactly")
    if len(a.args) != 1 or a.args[0].arg != "df" or a.args[0].annotation is not None:
        _reject("compute's only positional arg must be 'df'")
    if a.kwarg is not None and (a.kwarg.arg != "params" or a.kwarg.annotation is not None):
        _reject("the only allowed kwarg sink is **params")


def _check_body(fn: ast.FunctionDef, allowed: frozenset) -> None:
    body = fn.body
    if not body or not isinstance(body[-1], ast.Return):
        _reject("compute must end in a return")
    assigned: set[str] = set()
    for stmt in body[:-1]:
        if not isinstance(stmt, ast.Assign):
            _reject(f"only assignments allowed before the return, got {type(stmt).__name__}")
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            _reject("assignment target must be a single name")
        target = stmt.targets[0].id
        if target in ("df", "params"):
            _reject("cannot rebind df/params")
        assigned.add(target)
        _check_clause(stmt.value, allowed)

    ret = body[-1].value
    if not isinstance(ret, ast.Dict):
        _reject("compute must return a dict of the canonical columns")
    keys = []
    for k in ret.keys:
        if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
            _reject("return dict keys must be string literals")
        keys.append(k.value)
    if set(keys) != _CANONICAL:
        _reject(f"return dict keys must be exactly {sorted(_CANONICAL)}")
    for v in ret.values:
        if not (isinstance(v, ast.Name) and v.id in assigned):
            _reject("return dict values must be locals assigned above")


def validate_source(source: str, allowed_blocks=None) -> None:
    """Validate emitted `compute` source against the allow-list. Raises
    UnsafeStrategyError on any violation; returns None if safe."""
    allowed = block_names() if allowed_blocks is None else frozenset(allowed_blocks)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise UnsafeStrategyError(f"syntax error: {e}") from None

    # Pass 1 — global node-type allow-list + dunder ban (defense in depth).
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            _reject(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and _is_dunder(node.id):
            _reject(f"dunder identifier: {node.id}")
        if isinstance(node, ast.arg) and _is_dunder(node.arg):
            _reject("dunder argument name")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _is_dunder(node.value):
            _reject("dunder string literal")

    # Pass 2 — structural: exactly one def compute, block-clause assigns, dict return.
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        _reject("module must contain exactly one function definition")
    fn = tree.body[0]
    _check_signature(fn)
    _check_body(fn, allowed)


def is_safe(source: str, allowed_blocks=None) -> bool:
    try:
        validate_source(source, allowed_blocks)
        return True
    except UnsafeStrategyError:
        return False
