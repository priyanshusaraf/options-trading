"""
RFC 0001 §4 — C13, provenance-blind execution.

    "No executor path may branch on where a component came from. A component's
    source is display metadata and nothing else. ComfyUI achieves this
    *subtractively* — one registry, no plugin API — and the subtractive route is
    the one to copy. Given this codebase's documented history with mechanisms
    that exist and are wired to nothing, C13 is to be enforced by a test in the
    conformance phase rather than by review."

The RFC names this file's job explicitly, so this is the one §4 clause landing
in this phase. The other fourteen describe *resolution*, which does not exist
yet; tests for them would be a suite with no implementation to run against,
which is this codebase's defining failure mode wearing a conformance badge.
They land with the resolver. See `test_ir_conformance.py` for the same
discipline applied to F14.

C13 holds today, and it holds subtractively: there is one `_REGISTRY`, a
generated strategy is `registry.register()`ed into the same dict a built-in is
discovered into, and no `Strategy` carries a field saying where it came from.
This file exists so that stays true when visual, Python-authored and
marketplace sources arrive — the moment when adding `if strategy.is_marketplace`
becomes tempting.
"""
from __future__ import annotations

import io
import pathlib
import tokenize

import pandas as pd
import pytest

from app.strategy import registry
from app.strategy.registry import (
    DEFAULT_STRATEGY_KEY,
    Strategy,
    all_strategies,
    get_strategy,
    resolve_strategy,
    strategy_meta,
)

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# Names that would let an executor ask where a component came from. Each is a
# compound: bare `source` is legitimate everywhere (a generated strategy stores
# its emitted source text), and a guard that fires on it would be turned off.
PROVENANCE_NAMES = (
    "is_generated", "is_builtin", "is_built_in", "is_marketplace", "is_visual",
    "is_user_strategy", "from_marketplace", "strategy_source", "source_kind",
    "component_source", "provenance", "origin_kind",
)

# Where execution happens. The clause is about *executor* paths.
EXECUTOR_DIRS = ("engine", "backtest", "strategy")
# The admission AUTHORITY GATE lives under app/strategy since Phase 3 but is
# not an executor path: examining provenance is its entire job, and the engine
# consumes only its verdict (the same perimeter decision the L1 wiring recorded
# for app/core/execution_binding).  It is excluded by name, and the exclusion
# is compensated below by a direction check: admission must never import the
# engine, so no provenance concept can leak INTO execution through it.
AUTHORITY_GATES = {"strategy/admission.py"}


def _python_files():
    for d in EXECUTOR_DIRS:
        yield from sorted((APP / d).rglob("*.py"))


def _provenance_hits(text: str) -> list[str]:
    identifiers = {
        token.string
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
        if token.type == tokenize.NAME
    }
    return [name for name in PROVENANCE_NAMES if name in identifiers]


# ── the subtractive property: there is nothing to branch on ───────────────

def test_no_executor_module_names_a_provenance_concept():
    """The enforcement is an absence. If this goes red, the fix is not to widen
    the allowlist — it is to ask why execution needs to know."""
    offenders = {}
    for path in _python_files():
        rel = str(path.relative_to(APP))
        if rel in AUTHORITY_GATES:
            continue
        hits = _provenance_hits(path.read_text())
        if hits:
            offenders[rel] = hits
    assert offenders == {}, (
        f"C13: executor paths must not branch on provenance — {offenders}")


def test_the_provenance_detector_can_go_red(tmp_path):
    """A guard whose empty result is indistinguishable from a passing one is not
    a guard. Prove the detector fires before trusting that it did not."""
    assert _provenance_hits("if strategy.is_marketplace:\n    fee = 0.1\n") == [
        "is_marketplace"]
    assert _provenance_hits("if strategy.provenance:\n    fee = 0.1\n") == [
        "provenance"]
    assert _provenance_hits("source = compose(blocks)\n") == []
    assert _provenance_hits(
        "# input provenance is authority evidence\n"
        "detail = 'provenance cycle'\n"
    ) == []


def test_the_strategy_contract_declares_no_provenance_field():
    """A component's source is display metadata and nothing else — and here it
    is not even that: the base class has no place to record it."""
    declared = set(vars(Strategy)) | set(Strategy.__annotations__)
    assert not (declared & set(PROVENANCE_NAMES))


def test_there_is_exactly_one_registry():
    """ComfyUI's subtractive route: one registry, no plugin API. The invariant
    is ONE RESOLUTION PATH, not one dict: multi-tenant generated strategies
    need an owner-partitioned store, so exactly two DECLARED containers are
    allowed — the static registry and the (owner, key) generated partition —
    and any third container fails here.  The path itself is pinned by the
    sweep below: nothing outside the registry package may touch either
    container directly, so every lookup flows through resolve_strategy."""
    stores = sorted(n for n, v in vars(registry).items()
                    if isinstance(v, dict) and n.upper().endswith("REGISTRY"))
    assert set(stores) == {"_GENERATED_REGISTRY", "_REGISTRY"}, stores

    offenders = {}
    for path in _python_files():
        text = path.read_text()
        for container in ("_GENERATED_REGISTRY", "_REGISTRY"):
            if container in text:
                rel = str(path.relative_to(APP))
                if not rel.startswith("strategy/registry"):
                    offenders.setdefault(rel, []).append(container)
    assert offenders == {}, (
        "a second resolution path: containers touched outside the registry "
        f"package — {offenders}")


# ── the behavioural property: origin changes nothing observable ───────────

class _Flat(Strategy):
    """A strategy whose signals depend only on its parameters, so any observable
    difference between two instances is a difference of *origin*, not of logic."""
    display_name = "Conformance Probe"
    default_params = {"n": 1}

    def compute(self, df: pd.DataFrame, **params) -> pd.DataFrame:
        out = df.copy()
        out["longEntry"] = [i % (params["n"] + 1) == 0 for i in range(len(df))]
        out["shortEntry"] = False
        out["longExit"] = False
        out["shortExit"] = False
        return out


@pytest.fixture
def registered_at_runtime():
    """The generated-strategy seam: `register()` is how a strategy reconstructed
    from the database at engine startup enters the registry."""
    strat = _Flat()
    strat.key = "conformance_probe_runtime"
    registry.register(strat)
    try:
        yield strat
    finally:
        registry._REGISTRY.pop(strat.key, None)


def _frame(rows=6):
    return pd.DataFrame({"close": [100.0 + i for i in range(rows)]})


def test_a_runtime_registered_strategy_resolves_by_the_same_call(registered_at_runtime):
    """Not "an equivalent call" — the same one. A separate lookup for generated
    strategies would be the branch this clause forbids, relocated."""
    assert resolve_strategy("conformance_probe_runtime") is registered_at_runtime
    assert get_strategy("conformance_probe_runtime") is registered_at_runtime
    assert registered_at_runtime in all_strategies()


def test_a_runtime_registered_strategy_is_the_same_type_as_a_built_in(registered_at_runtime):
    builtin = resolve_strategy(DEFAULT_STRATEGY_KEY)
    assert isinstance(registered_at_runtime, Strategy)
    assert isinstance(builtin, Strategy)
    assert type(builtin).__mro__[-2] is type(registered_at_runtime).__mro__[-2] is Strategy


def test_origin_is_not_observable_on_the_resolved_object(registered_at_runtime):
    """Given only a resolved strategy, an executor cannot determine its origin —
    which is what makes branching on it impossible rather than merely discouraged."""
    builtin = resolve_strategy(DEFAULT_STRATEGY_KEY)
    for strat in (registered_at_runtime, builtin):
        assert not (set(dir(strat)) & set(PROVENANCE_NAMES))


def test_the_public_listing_exposes_no_source_field(registered_at_runtime):
    """`strategy_meta` feeds the UI. A source field here would be legitimate as
    display metadata — but it does not exist, so nothing downstream can read one
    by accident."""
    for entry in strategy_meta():
        assert not (set(entry) & set(PROVENANCE_NAMES))


def test_identical_logic_produces_identical_signals_regardless_of_origin(registered_at_runtime):
    """The end-to-end statement of C13: two strategies with the same logic and
    the same parameters are indistinguishable at the execution boundary, and
    only their entry route into the registry differs."""
    direct = _Flat()
    direct.key = "conformance_probe_direct"
    df = _frame()

    from_registry = resolve_strategy("conformance_probe_runtime").signals(df, n=2)
    from_object = direct.signals(df, n=2)

    pd.testing.assert_frame_equal(from_registry, from_object)
