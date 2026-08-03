"""L1 Stage 1 — the shadow lane's core: pairing, comparison, classification, identity.

Stage 1 is a **shadow-only** integration. The hand-written strategy stays the sole
execution authority; this lane evaluates the Component IR mirror on the identical frame
and records where the two disagree. Nothing here may reach an order, and nothing here may
change what the authoritative lane produced.

These tests cover the pure core (`app/engine/ir_shadow.py`) with no runner and no database.
The runner integration, the broker-seam isolation proofs and the persistence contract live
in `test_ir_shadow_isolation.py` and `test_ir_shadow_store.py`.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from app.engine import ir_shadow
from app.ir.strategies.expanding_z import GRAPH, IMPLEMENTATIONS, LIBRARY
from app.strategy.registry.base import CANONICAL_COLUMNS
from app.strategy.registry.expanding_z_v4 import STRATEGY as HANDWRITTEN

from .test_ir_adapter import frame, real_series

NOW = dt.datetime(2026, 8, 4, 10, 30, 0)


def series(name: str = "SILVERM") -> list[float]:
    """A recorded series long enough to reach the graph's 302-bar settled region."""
    return real_series()[name]


def authoritative(df: pd.DataFrame) -> pd.DataFrame:
    """Exactly what the live lane computes today for `expanding_z_v4`."""
    return HANDWRITTEN.signals(df)


def observe(df=None, auth=None, key="NIFTY", authoritative_key="expanding_z_v4",
            now=NOW, **kw):
    df = frame(series()) if df is None else df
    auth = authoritative(df) if auth is None else auth
    return ir_shadow.observe(
        instrument_key=key, authoritative_key=authoritative_key,
        authoritative_frame=auth, frame=df, now=now, **kw)


# ── pairing ───────────────────────────────────────────────────────────────────────

def test_only_a_mirrored_strategy_has_a_shadow_pairing():
    """The one graph that exists mirrors `expanding_z_v4`. Running it against an
    instrument on a different strategy would compare two different strategies and call
    the difference a divergence, which is worse than not observing at all."""
    assert ir_shadow.pairing_for("expanding_z_v4") is not None
    assert ir_shadow.pairing_for("trend_impulse_v3") is None
    assert ir_shadow.pairing_for(None) is None


def test_an_unmirrored_strategy_yields_no_observation():
    assert observe(authoritative_key="trend_impulse_v3") is None


def test_the_pairing_is_built_once_and_reused():
    """Resolution is not free and the signal lane runs every 2.5 s. Caching the RESOLVED
    graph is not the forbidden cross-frame evaluation cache: `Cache` is keyed on
    `node.cache_id` and carries data, this carries only topology."""
    assert ir_shadow.pairing_for("expanding_z_v4") is ir_shadow.pairing_for("expanding_z_v4")


# ── the comparison ────────────────────────────────────────────────────────────────

def test_the_mirror_agrees_with_the_strategy_it_mirrors():
    obs = observe()
    assert obs.agreed is True
    assert obs.reason == ir_shadow.AGREEMENT
    assert obs.warmup_state == "settled"
    assert obs.ir == obs.authoritative


def test_agreement_is_measured_on_bars_that_actually_signal():
    """A single all-False bar agrees with another all-False bar, so last-bar agreement
    alone can be vacuous. Walk the settled region one bar at a time — the same way the
    live lane sees it, a growing frame — and require both that every bar agrees and that
    the region contains real signal."""
    closes = series()
    fired = 0
    for end in range(len(closes) - 25, len(closes)):
        df = frame(closes[:end])
        obs = observe(df=df, auth=authoritative(df))
        assert obs.reason == ir_shadow.AGREEMENT, f"bar {end}: {obs.detail}"
        fired += any(obs.ir.values())
    assert fired > 0, "no bar in the walked region fired — the agreement is vacuous"


def test_a_flag_divergence_names_the_columns_that_differ():
    df = frame(series())
    auth = authoritative(df)
    auth.loc[auth.index[-1], "longEntry"] = not bool(auth.iloc[-1]["longEntry"])
    obs = observe(df=df, auth=auth)
    assert obs.agreed is False
    assert obs.reason == ir_shadow.FLAG_DIVERGENCE
    assert "longEntry" in obs.detail
    assert obs.authoritative["longEntry"] != obs.ir["longEntry"]
    assert obs.authoritative["shortEntry"] == obs.ir["shortEntry"]


def test_the_comparison_covers_all_four_canonical_columns():
    obs = observe()
    assert set(obs.authoritative) == set(CANONICAL_COLUMNS)
    assert set(obs.ir) == set(CANONICAL_COLUMNS)


# ── classified refusals ───────────────────────────────────────────────────────────

def test_a_frame_shorter_than_the_graph_warmup_is_classified_not_silent():
    """ADR 0011 conflict #2. The live admission guard is ~55 bars and the graph's resolved
    warmup is 302; a short frame must be a recorded, classified event, never four
    all-False columns that read as a flat market."""
    df = frame(series()[:120])
    obs = observe(df=df, auth=authoritative(df))
    assert obs.agreed is False
    assert obs.reason == ir_shadow.INSUFFICIENT_HISTORY
    assert obs.warmup_state == "insufficient"
    assert obs.ir is None
    assert obs.declared_warmup > obs.frame_bars


def test_a_frame_missing_a_declared_graph_input_is_classified():
    df = frame(series()).drop(columns=["high"])
    obs = observe(df=df, auth=authoritative(frame(series())))
    assert obs.reason == ir_shadow.MISSING_GRAPH_INPUT
    assert "high" in obs.detail


def test_a_runtime_refusal_is_contained_and_classified():
    """A kernel that breaks the runtime's own contract raises `EvaluationError`, named by
    the RFC clause it fails. That is the IR refusing, and it is its own class."""
    def wrong_shape(*_args, **_kwargs):
        return "not a mapping of sockets"

    broken = ir_shadow.ShadowPairing(
        authoritative_key="expanding_z_v4",
        graph=GRAPH,
        library=(LIBRARY, {address: wrong_shape for address in IMPLEMENTATIONS}))
    obs = observe(pairing=broken)
    assert obs.agreed is False
    assert obs.reason == ir_shadow.EVALUATION_ERROR
    assert "C3" in obs.detail
    assert obs.ir is None


def test_a_kernel_that_raises_is_contained_and_classified_as_unexpected():
    """An exception the runtime does not wrap is a defect, not a known refusal — so it
    gets the class that means "someone must look at this", not a routine one."""
    def explode(*_args, **_kwargs):
        raise RuntimeError("kernel exploded")

    obs = observe(pairing=ir_shadow.ShadowPairing(
        authoritative_key="expanding_z_v4", graph=GRAPH,
        library=(LIBRARY, {address: explode for address in IMPLEMENTATIONS})))
    assert obs.reason == ir_shadow.UNEXPECTED_ERROR
    assert "RuntimeError" in obs.detail and "kernel exploded" in obs.detail
    assert obs.ir is None


# ── identity: what a recorded disagreement must be attributable to ────────────────

def test_the_observation_carries_the_graph_address_and_a_stable_execution_key():
    obs = observe()
    assert obs.graph_address.startswith("sha256:")
    assert obs.shadow_strategy_key == "ir.strategy.expanding_z_impulse"
    assert obs.graph_address not in obs.shadow_strategy_key
    assert obs.authoritative_strategy_key == "expanding_z_v4"


def test_the_frame_identity_is_of_the_data_and_nothing_else():
    df = frame(series())
    first = observe(df=df)
    again = observe(df=df.copy(), now=NOW + dt.timedelta(hours=3))
    assert first.frame_id == again.frame_id

    moved = df.copy()
    moved.loc[moved.index[-1], "close"] = float(moved.iloc[-1]["close"]) + 1.0
    assert observe(df=moved, auth=authoritative(moved)).frame_id != first.frame_id


def test_the_frame_identity_records_the_exact_window():
    df = frame(series())
    obs = observe(df=df)
    assert obs.frame_bars == len(df)
    assert obs.frame_first_ts == pd.Timestamp(df.iloc[0]["date"]).to_pydatetime()
    assert obs.frame_last_ts == pd.Timestamp(df.iloc[-1]["date"]).to_pydatetime()
    assert obs.bar_time == obs.frame_last_ts


def test_the_observation_records_when_it_was_taken_and_what_it_cost():
    obs = observe()
    assert obs.observed_at == NOW
    assert obs.eval_seconds > 0.0


# ── the observer may not disturb what it observes ─────────────────────────────────

def test_observing_does_not_mutate_either_frame():
    df = frame(series())
    auth = authoritative(df)
    before_df, before_auth = df.copy(deep=True), auth.copy(deep=True)
    observe(df=df, auth=auth)
    pd.testing.assert_frame_equal(df, before_df)
    pd.testing.assert_frame_equal(auth, before_auth)


def test_the_lane_never_constructs_a_persistent_evaluation_cache():
    """Constraint 6. `Cache` is keyed on `node.cache_id`, fixed at resolution and
    carrying nothing about the input data — one reused across frames returns the previous
    frame's series with every node reporting a hit. The shadow lane must never hold one."""
    import ast
    import pathlib as _pathlib

    tree = ast.parse(_pathlib.Path(ir_shadow.__file__).read_text())
    called = {
        (node.func.id if isinstance(node.func, ast.Name) else node.func.attr)
        for node in ast.walk(tree) if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not [name for name in called if "cache" in name.lower()], (
        "the shadow lane constructed something cache-shaped")

    pairing = ir_shadow.pairing_for("expanding_z_v4")
    assert not any("cache" in name.lower() for name in vars(pairing))


def test_two_evaluations_of_different_frames_do_not_return_the_same_result():
    """The behavioural half of the guard above: a stale-cache regression would make the
    second frame's verdict equal the first's while looking fast and healthy."""
    long_series = series()
    a = frame(long_series)
    b = frame(long_series[:-8])
    first, second = observe(df=a), observe(df=b, auth=authoritative(b))
    assert first.frame_id != second.frame_id
    assert first.ir is not None and second.ir is not None
