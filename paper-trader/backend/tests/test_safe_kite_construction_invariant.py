"""F-10: the order-safe wrapper must be what actually gets constructed.

`SafePaperKite` is strong — it blocks the mutating SDK methods by name AND enforces a
fail-closed route allowlist at the transport chokepoint. Existing tests prove the wrapper
does what it claims. What they did not prove is that a `KiteProvider` built the normal way
is holding one, because most tests bypass `__init__` and assign `.kite` directly.

That gap is exactly the shape where a safety control quietly stops applying: the control
keeps passing its own tests while the thing in production is something else.

Two invariants here, and both can fail independently:

1. A `KiteProvider` constructed normally holds a `SafePaperKite`.
2. No module under `app/` or `scripts/` constructs a bare, order-capable `KiteConnect`.
   The live order path deliberately uses `LiveExecutionKite`, a *named* subclass that is
   reviewed as an execution seam; a raw `KiteConnect` is an unreviewed one. The ledger
   reconciliation script used to build a raw client for a single `margins()` read — it
   placed no order, but its type could.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.providers.kite import KiteProvider
from app.providers.safe_kite import OrderPlacementDisabled, SafePaperKite

BACKEND = pathlib.Path(__file__).resolve().parents[1]
# `safe_kite.py` is where the subclass is DEFINED; it is the one legitimate place the bare
# name is referenced as a base class.
_ALLOWED = {BACKEND / "app" / "providers" / "safe_kite.py"}


def test_a_normally_constructed_provider_holds_the_safe_wrapper():
    p = KiteProvider()
    assert isinstance(p.kite, SafePaperKite), (
        f"KiteProvider().kite is {type(p.kite).__name__}, not SafePaperKite — the order "
        f"allowlist is not applying to the object production actually uses")


def test_that_wrapper_actually_refuses_to_place_an_order():
    """Holding the right type is only worth something if the type still refuses."""
    p = KiteProvider()
    with pytest.raises(OrderPlacementDisabled):
        p.kite.place_order(variety="regular", exchange="NSE", tradingsymbol="INFY",
                           transaction_type="BUY", quantity=1, product="MIS",
                           order_type="MARKET")


def _bare_kiteconnect_constructions(path: pathlib.Path) -> list[int]:
    """Line numbers where `KiteConnect(...)` is CALLED (not subclassed) in `path`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else (
            fn.attr if isinstance(fn, ast.Attribute) else None)
        if name == "KiteConnect":
            hits.append(node.lineno)
    return hits


def test_no_module_constructs_a_bare_order_capable_kite_client():
    offenders = []
    for root in ("app", "scripts"):
        for path in sorted((BACKEND / root).rglob("*.py")):
            if path in _ALLOWED:
                continue
            for line in _bare_kiteconnect_constructions(path):
                offenders.append(f"{path.relative_to(BACKEND)}:{line}")
    assert not offenders, (
        "these construct a raw, order-capable KiteConnect instead of SafePaperKite or the "
        "reviewed LiveExecutionKite execution seam: " + ", ".join(offenders))
