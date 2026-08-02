"""Phase E — StrategySpec as the single execution contract.

The claim under test is the one the remaining phases depend on: **every strategy,
whatever its source, compiles into one specification.** If a built-in and a
generated strategy cannot be described by the same structure, then a visual
strategy and a marketplace strategy will each need their own execution path, and
"one execution engine" is not achievable.

The second claim is that compiling changed nothing. A compiled spec describes what
the platform already does; it does not propose new behaviour.
"""
from __future__ import annotations

import pytest

from app.strategy import spec as sp
from app.strategy.registry import all_strategies, get_strategy, strategy_meta


@pytest.mark.parametrize("strategy", all_strategies(), ids=lambda s: s.key)
def test_every_registered_strategy_compiles(strategy):
    """The load-bearing test. Parametrised over the registry rather than a fixed
    list, so a strategy added later is covered automatically — including generated
    ones, which is the point."""
    compiled = sp.compile_spec(strategy)
    assert compiled.metadata.key == strategy.key
    assert compiled.metadata.version == strategy.version
    assert callable(compiled.signal_fn)
    # Every default_params entry must be described by the schema, or the spec is
    # not a complete description of the strategy.
    described = {p.name for p in compiled.params}
    assert described == set(strategy.default_params), \
        f"{strategy.key}: schema and default_params disagree"


@pytest.mark.parametrize("strategy", all_strategies(), ids=lambda s: s.key)
def test_compiled_defaults_match_the_strategys_own_defaults(strategy):
    """Compiling must not re-tune anything."""
    assert sp.compile_spec(strategy).defaults() == dict(strategy.default_params)


def test_a_spec_is_serialisable():
    """A marketplace listing is metadata + params + policies. If a spec cannot be
    turned into data it cannot be published, reviewed or diffed."""
    payload = sp.compile_spec(get_strategy("trend_impulse_v3")).to_dict()
    assert payload["metadata"]["key"] == "trend_impulse_v3"
    assert payload["metadata"]["version"]
    assert {p["name"] for p in payload["params"]} == {
        "ema_length", "z_length", "entry_z", "slope_lookback"}
    for block in ("entry", "exit", "sizing"):
        assert isinstance(payload[block], dict)


def test_parameter_kinds_carry_units_not_just_types():
    """"It's a float" does not tell an editor whether 0.8 means 80% or 0.8 ATR.
    A visual builder and a Python editor both render from the KIND."""
    compiled = sp.compile_spec(get_strategy("trend_impulse_v3"))
    assert compiled.param("ema_length").kind == sp.LENGTH
    assert compiled.param("entry_z").kind == sp.THRESHOLD


def test_bounds_are_enforced_not_advisory():
    """A marketplace strategy's parameters are edited by someone who did not write
    it. Bounds are part of the contract."""
    p = sp.compile_spec(get_strategy("trend_impulse_v3")).param("ema_length")
    assert p.validate(50) == 50
    with pytest.raises(ValueError, match="below minimum"):
        p.validate(1)
    with pytest.raises(ValueError, match="above maximum"):
        p.validate(10_000)


def test_resolve_params_falls_back_rather_than_raising():
    """This is the read path — the engine, mid-loop. One bad parameter must not
    stop the process managing open positions. (The write path calls
    ParamSpec.validate directly and surfaces the error to whoever typed it.)"""
    compiled = sp.compile_spec(get_strategy("trend_impulse_v3"))
    resolved = compiled.resolve_params({"ema_length": 99_999, "z_length": 20})
    assert resolved["ema_length"] == compiled.param("ema_length").default, \
        "an out-of-bounds override must fall back to the default"
    assert resolved["z_length"] == 20, "a valid sibling must still apply"
    assert set(resolved) == set(compiled.defaults()), \
        "resolution must return the FULL parameter set, not just what was overridden"


def test_unknown_override_keys_are_ignored_not_injected():
    compiled = sp.compile_spec(get_strategy("trend_impulse_v3"))
    assert "nonsense" not in compiled.resolve_params({"nonsense": 1})


def test_exit_policy_is_the_decision_kernels_not_a_second_one():
    """A spec describing exits in its own vocabulary would need translating into
    the kernel's, and the translation is what would drift."""
    from app.engine.decision_kernel import ExitPolicy
    assert isinstance(sp.compile_spec(get_strategy("trend_impulse_v3")).exit,
                      ExitPolicy)


def test_a_strategy_declaring_a_risk_model_compiles_to_a_ratchet_exit():
    ratchet_strategies = [s for s in all_strategies()
                          if getattr(s, "risk_model", None) is not None]
    if not ratchet_strategies:
        pytest.skip("no strategy declares a risk_model in this build")
    assert sp.compile_spec(ratchet_strategies[0]).exit.ratchet is True


def test_default_policies_reproduce_current_platform_behaviour():
    """Compiling describes what the platform does today. Every guard on, sizing
    left to the engine — anything else would be this phase quietly changing
    real-money behaviour."""
    compiled = sp.compile_spec(get_strategy("trend_impulse_v3"))
    assert compiled.entry.respect_entry_window is True
    assert compiled.entry.respect_event_blackouts is True
    assert compiled.entry.respect_gap_guard is True
    assert compiled.sizing.model == sp.PLATFORM_DEFAULT


def test_strategy_meta_exposes_the_spec_without_dropping_what_was_there():
    """The spec is ADDED to the listing, never substituted — existing consumers
    read `default_params` and must keep working."""
    rows = strategy_meta()
    assert rows
    for row in rows:
        assert {"key", "version", "display_name", "default_params"} <= set(row)
        assert row.get("spec") is not None, f"{row['key']} failed to compile"
        assert row["spec"]["metadata"]["key"] == row["key"]
