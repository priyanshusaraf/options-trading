"""Stage 0 parity and safety evidence for the shared IR strategy adapter.

This suite replaces a parity claim that was weaker than its reputation. The previous
proof (`test_ir_strategy_parity.py`) compared `evaluate()` against the hand-written
strategy over 400 bars of a **synthetic sine wave**, one instrument, one interval, with
two of fifteen parameters ever moved — and it **bypassed the adapter entirely**, so the
adapter's warmup masking, frame contract, identity and risk model were outside the claim.

What is proven here, through `IRGraphStrategy` itself:

- parity on **real recorded market series** across several instruments, on the settled
  region, with the warmup mask asserted exactly rather than assumed;
- parity under parameter changes, including a length parameter that moves warmup;
- every failure mode is a **typed refusal**, never a silent all-False frame.

**On the data.** `tests/data/real_spot_series.csv` is real spot recorded from Kite between
2026-06-22 and 2026-07-08 (six instruments). It is a genuine close series; `open`, `high`,
`low` and `volume` are **reconstructed deterministically** from it, because per-bar OHLCV
was not recoverable offline. Reconstruction is stated rather than hidden: for parity it is
sound — both implementations receive the identical frame, so any divergence is theirs — and
the real close path exercises autocorrelation, gaps and flat stretches a sine wave cannot.
"""
from __future__ import annotations

import csv
import pathlib

import pandas as pd
import pytest

from app.ir.resolve import resolve
from app.ir.runtime import Cache, EvaluationError, evaluate
from app.ir.strategies.expanding_z import GRAPH, IMPLEMENTATIONS, LIBRARY
from app.strategy.ir_adapter import (
    IRGraphStrategy,
    InsufficientHistory,
    InvalidRiskModel,
    MissingGraphInput,
    UnmappableGraph,
    column_mapping,
    validate_risk_model,
)
from app.strategy.registry.base import CANONICAL_COLUMNS
from app.strategy.registry.expanding_z_v4 import STRATEGY as HANDWRITTEN

DATA = pathlib.Path(__file__).parent / "data" / "real_spot_series.csv"

RISK_MODEL = {
    "atr_length": 14, "initial_risk_atr": 1.5, "trail_start_r": 1.0, "trail_atr": 2.5,
    "use_mfe_capture_floor": True, "capture_start_r": 2.0, "capture_pct": 0.5,
}


def real_series() -> dict[str, list[float]]:
    """Real recorded spot closes, by instrument, in timestamp order."""
    out: dict[str, list[float]] = {}
    with DATA.open() as handle:
        for row in csv.DictReader(handle):
            out.setdefault(row["instrument_key"], []).append(float(row["spot"]))
    return out


def frame(closes: list[float]) -> pd.DataFrame:
    """A production-shaped frame: RangeIndex plus a `date` column, six OHLCV fields."""
    close = pd.Series(closes, dtype=float)
    prev = close.shift(1).fillna(close.iloc[0]) if len(close) else close
    spread = close.abs() * 0.0005
    return pd.DataFrame({
        "date": pd.date_range("2026-06-22 09:15", periods=len(close), freq="15min",
                              tz="Asia/Kolkata"),
        "open": prev,
        "high": pd.concat([close, prev], axis=1).max(axis=1) + spread,
        "low": pd.concat([close, prev], axis=1).min(axis=1) - spread,
        "close": close,
        "volume": pd.Series(1000.0, index=close.index),
    })


def adapter(graph=GRAPH) -> IRGraphStrategy:
    return IRGraphStrategy(graph, (LIBRARY, IMPLEMENTATIONS))


def with_risk_model(model=RISK_MODEL) -> dict:
    return {**GRAPH, "risk_model": model}


def single_output_graph() -> dict:
    """A different topology: one unnamed boolean output, which must bind to longEntry."""
    graph = {**GRAPH}
    keep = {"longEntry"}
    graph["interface"] = [
        item for item in GRAPH["interface"]
        if item.get("direction") != "output" or item["identifier"] in keep
    ]
    graph["edges"] = [
        edge for edge in GRAPH["edges"]
        if not (edge["target"]["instance"] == "io_out"
                and edge["target"]["socket"] not in keep)
    ]
    return graph


# ---------------------------------------------------------------- parity, real data

@pytest.mark.parametrize("instrument", ["NATURALGAS", "SILVERM", "GOLDM"])
def test_parity_with_the_handwritten_strategy_on_real_recorded_series(instrument):
    """The adapter and the live strategy agree bar for bar on every settled bar."""
    strategy = adapter()
    df = frame(real_series()[instrument])
    assert len(df) > strategy.declared_warmup, "fixture must reach the settled region"

    produced = strategy.compute(df)
    expected = HANDWRITTEN.compute(df.copy())
    settled = slice(strategy.declared_warmup, None)

    for column in CANONICAL_COLUMNS:
        pd.testing.assert_series_equal(
            produced[column].iloc[settled], expected[column].iloc[settled].astype(bool),
            check_names=False, obj=f"{instrument}:{column}")


def test_the_warmup_mask_is_exact_and_not_merely_assumed():
    """Warmup rows are False by construction (C10); settled rows are the graph's own."""
    strategy = adapter()
    df = frame(real_series()["SILVERM"])
    warmup = strategy.declared_warmup

    produced = strategy.compute(df)

    for column in CANONICAL_COLUMNS:
        assert not produced[column].iloc[:warmup].any(), f"{column} fired inside warmup"
    # The mask must not be doing the work: the settled region has to carry real signal.
    assert produced[list(CANONICAL_COLUMNS)].iloc[warmup:].to_numpy().any(), (
        "no signal after warmup — parity would be vacuous")


def test_parity_survives_parameter_changes_including_one_that_moves_warmup():
    df = frame(real_series()["NATURALGAS"])

    for overrides in ({"entry_pct": 90.0}, {"min_abs_z": 1.2},
                      {"ema_length": 20}, {"atr_length": 7, "z_length": 30}):
        graph = {**GRAPH, "identifier": f"{GRAPH['identifier']}.v"}
        strategy = IRGraphStrategy(graph, (LIBRARY, IMPLEMENTATIONS))
        strategy.resolved = resolve(graph, LIBRARY, overrides)
        strategy.declared_warmup = strategy.resolved.warmup
        if len(df) <= strategy.declared_warmup:
            continue
        produced = strategy.compute(df)
        expected = HANDWRITTEN.compute(df.copy(), **overrides)
        settled = slice(strategy.declared_warmup, None)
        for column in CANONICAL_COLUMNS:
            pd.testing.assert_series_equal(
                produced[column].iloc[settled], expected[column].iloc[settled].astype(bool),
                check_names=False, obj=f"{overrides}:{column}")


def test_a_different_topology_binds_and_still_matches_its_own_output():
    """A graph declaring one unnamed output binds it to longEntry and leaves the rest False."""
    strategy = adapter(single_output_graph())
    df = frame(real_series()["GOLDM"])

    produced = strategy.compute(df)
    expected = HANDWRITTEN.compute(df.copy())
    settled = slice(strategy.declared_warmup, None)

    pd.testing.assert_series_equal(
        produced["longEntry"].iloc[settled], expected["longEntry"].iloc[settled].astype(bool),
        check_names=False)
    for column in ("shortEntry", "longExit", "shortExit"):
        assert not produced[column].any(), f"{column} must stay False when unbound"


# ------------------------------------------------------- insufficient history is loud

def test_short_real_frames_refuse_rather_than_returning_silence():
    """The defect this replaces: 134 real bars against a 302-bar warmup returned four
    all-False columns forever, indistinguishable from a genuine flat market."""
    strategy = adapter()
    for instrument in ("NIFTY", "BANKNIFTY"):
        df = frame(real_series()[instrument])
        assert len(df) <= strategy.declared_warmup

        with pytest.raises(InsufficientHistory) as raised:
            strategy.compute(df)
        assert str(len(df)) in str(raised.value)
        assert str(strategy.declared_warmup) in str(raised.value)


def test_the_boundary_between_refusal_and_evaluation_is_exact():
    strategy = adapter()
    closes = real_series()["SILVERM"]
    warmup = strategy.declared_warmup

    with pytest.raises(InsufficientHistory):
        strategy.compute(frame(closes[:warmup]))
    with pytest.raises(InsufficientHistory):
        strategy.compute(frame(closes[:warmup + 0]))
    produced = strategy.compute(frame(closes[:warmup + 1]))
    assert len(produced) == warmup + 1
    assert not produced[list(CANONICAL_COLUMNS)].iloc[:warmup].to_numpy().any()


def test_an_empty_frame_refuses_instead_of_returning_an_empty_success():
    with pytest.raises(InsufficientHistory):
        adapter().compute(frame([]))


# --------------------------------------------------------------------- risk model

def test_a_declared_risk_model_reaches_the_strategy_contract():
    """Without this the live ATR ratchet (`runner.py:478-487`) silently disables."""
    assert adapter().risk_model is None
    carried = adapter(with_risk_model()).risk_model
    assert carried == RISK_MODEL
    assert set(carried) == set(HANDWRITTEN.risk_model), (
        "an IR risk model must carry the same keys the live ratchet reads")


@pytest.mark.parametrize("broken, reason", [
    ({k: v for k, v in RISK_MODEL.items() if k != "trail_atr"}, "missing"),
    ({**RISK_MODEL, "surprise": 1}, "unknown"),
    ({**RISK_MODEL, "atr_length": -14}, "positive"),
    ({**RISK_MODEL, "atr_length": 14.5}, "whole number"),
    ({**RISK_MODEL, "capture_pct": "half"}, "must be a number"),
    ({**RISK_MODEL, "use_mfe_capture_floor": 1}, "must be a bool"),
    ("not-a-mapping", "must be a mapping"),
])
def test_a_malformed_risk_model_is_refused_not_degraded_to_none(broken, reason):
    with pytest.raises(InvalidRiskModel, match=reason):
        validate_risk_model(broken, "ir.test")


def test_an_absent_risk_model_is_explicit_rather_than_accidental():
    assert validate_risk_model(None, "ir.test") is None


# ----------------------------------------------------------------------- identity

def test_the_key_is_stable_across_edits_while_the_version_tracks_content():
    """Embedding the content address in the key orphans every persisted binding on the
    first edit, and the registry then silently substitutes the default strategy."""
    original = adapter()
    edited = adapter({**GRAPH, "display_name": "Edited display name"})

    assert original.key == edited.key == "ir.strategy.expanding_z_impulse"
    assert original.version != edited.version
    assert original.version == original.address
    assert original.address.startswith("sha256:")


def test_two_different_graphs_do_not_share_a_version():
    assert adapter().version != adapter(single_output_graph()).version


# ------------------------------------------------------- frames, errors, component failure

def test_a_frame_missing_a_declared_input_names_the_input():
    df = frame(real_series()["SILVERM"]).drop(columns=["close"])
    with pytest.raises(MissingGraphInput, match="close"):
        adapter().compute(df)


def test_a_graph_only_requires_the_inputs_it_declares():
    """The graph declares high/low/close; demanding open and volume too would fail frames
    that are perfectly serviceable."""
    strategy = adapter()
    assert set(strategy.required_inputs) == {"high", "low", "close"}
    df = frame(real_series()["SILVERM"]).drop(columns=["open", "volume"])
    assert strategy.compute(df)[list(CANONICAL_COLUMNS)].shape[1] == 4


def test_parameters_cannot_be_applied_to_an_already_resolved_graph():
    with pytest.raises(ValueError, match="bound at resolution"):
        adapter().compute(frame(real_series()["SILVERM"]), ema_length=10)


def test_a_missing_component_implementation_surfaces_a_closed_error():
    strategy = adapter()
    strategy.implementations = {}
    with pytest.raises(EvaluationError) as raised:
        strategy.compute(frame(real_series()["SILVERM"]))
    assert raised.value.clause == "C13"
    assert raised.value.instance_id


def test_a_failing_kernel_propagates_rather_than_being_swallowed():
    strategy = adapter()
    body = next(iter(strategy.implementations))

    def exploding(_params, _inputs):
        raise ZeroDivisionError("kernel failed")

    strategy.implementations = {**strategy.implementations, body: exploding}
    with pytest.raises(ZeroDivisionError):
        strategy.compute(frame(real_series()["SILVERM"]))


def test_unmappable_outputs_are_refused_with_the_offending_names():
    with pytest.raises(UnmappableGraph, match="half-names"):
        column_mapping(("longEntry", "somethingElse"))
    with pytest.raises(UnmappableGraph, match="cannot bind"):
        column_mapping(("a", "b"))
    assert column_mapping(("only",)) == {"longEntry": "only"}


# ------------------------------------------------------------- state and cache safety

def test_the_adapter_carries_no_state_between_calls():
    strategy = adapter()
    a, b = frame(real_series()["SILVERM"]), frame(real_series()["NATURALGAS"])

    first_a = strategy.compute(a)
    strategy.compute(b)
    second_a = strategy.compute(a)

    for column in CANONICAL_COLUMNS:
        pd.testing.assert_series_equal(first_a[column], second_a[column])


def test_the_input_frame_is_never_mutated():
    strategy = adapter()
    df = frame(real_series()["SILVERM"])
    before = df.copy()

    strategy.compute(df)

    pd.testing.assert_frame_equal(df, before)


def test_a_cache_shared_across_frames_would_be_wrong_so_the_adapter_never_shares_one():
    """`Cache` is keyed on `node.cache_id`, fixed at resolution and carrying nothing about
    the input data. Reusing one across frames returns the FIRST frame's series for the
    second — every node a hit, every value wrong. This pins the hazard so that passing a
    persistent cache "for performance" cannot be done quietly."""
    graph = resolve(GRAPH, LIBRARY)
    a = frame(real_series()["SILVERM"])
    b = frame(real_series()["NATURALGAS"])
    series = lambda df: {f: pd.Series(df[f].to_numpy(), index=df.index)
                         for f in ("high", "low", "close")}

    shared = Cache()
    first = evaluate(graph, series(a), IMPLEMENTATIONS, shared)
    reused = evaluate(graph, series(b), IMPLEMENTATIONS, shared)
    honest = evaluate(graph, series(b), IMPLEMENTATIONS)

    assert reused.outputs["longEntry"].equals(first.outputs["longEntry"])
    assert not reused.outputs["longEntry"].equals(honest.outputs["longEntry"])
    assert len(reused.cache_hits) > 0

    # The adapter must therefore produce the honest result for the second frame.
    strategy = adapter()
    strategy.compute(a)
    assert strategy.compute(b)["longEntry"].iloc[graph.warmup:].to_numpy().tolist() == \
        honest.outputs["longEntry"].iloc[graph.warmup:].astype(bool).to_numpy().tolist()


# ------------------------------------------------- live / backtest warmup agreement

def test_backtest_and_live_agree_on_which_bars_count():
    """Hard invariant 4. `compute_signals` trims warmup by dropping rows where indicator
    columns are NaN, but the adapter emits only the four booleans — so `warm_cols` is
    empty and nothing is trimmed, leaving the backtest replaying warmup bars the live
    lane masks to False. A strategy that declares its warmup must be trimmed by it."""
    from app.backtest.engine import compute_signals
    from app.providers.base import Candle

    strategy = adapter()
    closes = real_series()["SILVERM"]
    df = frame(closes)
    candles = [
        Candle(ts=row.date, open=row.open, high=row.high, low=row.low,
               close=row.close, volume=row.volume)
        for row in df.itertuples()
    ]

    trimmed = compute_signals(candles, strategy, {})

    assert len(trimmed) == len(df) - strategy.declared_warmup, (
        "the backtest must drop exactly the bars the live lane treats as unsettled")
    assert not trimmed.empty


# ------------------------------------------------------- registry: no silent substitution

def test_an_unregistered_ir_key_refuses_instead_of_trading_the_default_strategy():
    """A graph-backed key that falls back is the drift defect: the engine trades v3 while
    every trade row and every config still names the graph. Hand-written keys keep their
    deliberate fail-safe; the IR namespace cannot have one."""
    from app.strategy.registry import (
        DEFAULT_STRATEGY_KEY, StrategyNotFound, get_strategy, resolve_strategy,
    )

    with pytest.raises(StrategyNotFound):
        get_strategy("ir.strategy.not_registered")
    with pytest.raises(StrategyNotFound):
        resolve_strategy("ir.strategy.not_registered", allow_fallback=True)

    # Unchanged for everything else: an unknown hand-written key still falls back, and
    # None still means "give me the default".
    assert get_strategy("no_such_handwritten_strategy").key == DEFAULT_STRATEGY_KEY
    assert get_strategy(None).key == DEFAULT_STRATEGY_KEY


def test_a_registered_ir_strategy_resolves_normally():
    from app.strategy.registry import _REGISTRY, get_strategy, resolve_strategy

    strategy = adapter()
    _REGISTRY[strategy.key] = strategy
    try:
        assert get_strategy(strategy.key) is strategy
        assert resolve_strategy(strategy.key) is strategy
    finally:
        _REGISTRY.pop(strategy.key, None)


# ------------------------------------ Stage 0 changes nothing the live engine executes

def test_stage_0_leaves_the_live_execution_path_untouched():
    """Stage 0 adds a shared adapter and one warmup rule. It must not have altered the
    engine, order lifecycle, accounting, reconciliation, exits, kill controls or the
    deployment gate. The live lane still resolves and runs the hand-written strategy."""
    import inspect

    from app.engine import broker_factory, runner
    from app.strategy.registry import DEFAULT_STRATEGY_KEY, get_strategy

    # No execution module imports the adapter or the IR language.
    for module in (runner, broker_factory):
        source = inspect.getsource(module)
        assert "ir_adapter" not in source, f"{module.__name__} must not bind the adapter yet"
        assert "app.ir" not in source, f"{module.__name__} must not import the IR runtime yet"

    # The default live strategy is unchanged and still hand-written.
    live = get_strategy(DEFAULT_STRATEGY_KEY)
    assert live.key == DEFAULT_STRATEGY_KEY == "trend_impulse_v3"
    assert type(live).__module__.startswith("app.strategy.registry")

    # expanding_z_v4 still declares the risk model the live ratchet reads.
    from app.strategy.registry.expanding_z_v4 import STRATEGY as v4
    assert v4.risk_model and set(v4.risk_model) >= {"atr_length", "trail_atr"}
    # ...and it declares no warmup, so the backtest still trims it exactly as before.
    assert getattr(v4, "declared_warmup", None) is None


def _imports_of(path) -> set[str]:
    import ast
    modules: set[str] = set()
    for node in ast.walk(ast.parse(pathlib.Path(path).read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_the_shared_adapter_imports_neither_research_nor_execution():
    """Checked by parsing imports, not by grepping text: the adapter's own docstring
    mentions research and the order path, and a substring guard would pass on a real
    violation while failing on prose."""
    import app.strategy.ir_adapter as module

    imported = _imports_of(module.__file__)

    assert not [m for m in imported if m.startswith(("research", "app.engine"))]
    assert {"app.ir.resolve", "app.ir.runtime", "app.strategy.registry.base"} <= imported


def test_the_ir_language_core_does_not_depend_on_the_strategy_layer():
    """`app/ir/*.py` is the language and must stay the lowest layer.

    `app/ir/strategies/` is deliberately exempt: its kernels delegate to the hand-written
    implementation so the two planes cannot drift apart by construction. That exemption is
    also why the shared adapter lives in `app/strategy/` rather than in `app/ir/` — the
    binding layer already points the other way, and putting the adapter inside `app.ir`
    would tangle the two directions further for no gain.
    """
    import app.ir

    core = pathlib.Path(app.ir.__file__).parent
    offenders = {
        path.name: sorted(m for m in _imports_of(path)
                          if m.startswith(("app.strategy", "research", "app.engine")))
        for path in sorted(core.glob("*.py"))
    }
    assert not {name: mods for name, mods in offenders.items() if mods}

    binding = core / "strategies" / "expanding_z.py"
    assert any(m.startswith("app.strategy") for m in _imports_of(binding)), (
        "the binding layer is expected to import the strategy it mirrors")
    assert not [m for m in _imports_of(binding)
                if m.startswith(("research", "app.engine"))]
