"""A research result is only trustworthy if a human can read what the strategy
actually does and the exact logic (with the real parameters) it used. `explain`
turns a (strategy_key, params) pair into a faithful, plain-language explanation —
thesis, primitives, the numbered rules with live params interpolated, and a
'what's not modelled' caveat. It must never crash on an unknown strategy.
"""
import dataclasses

from research.evaluation import kernels
from research.orchestrator.report import render_markdown
from research.strategy.explain import StrategyExplanation, explain


def test_trend_impulse_interpolates_live_params():
    ex = explain("trend_impulse_v3",
                 {"ema_length": 70, "z_length": 50, "entry_z": 1.5, "slope_lookback": 5})
    assert isinstance(ex, StrategyExplanation)
    assert ex.strategy_key == "trend_impulse_v3"
    assert ex.thesis                       # non-empty economic rationale
    assert "Trend" in ex.primitives
    blob = " ".join(ex.rules)
    assert "EMA(70)" in blob               # the ACTUAL ema length, not the default
    assert "1.5" in blob                   # the ACTUAL entry threshold
    assert "50-bar" in blob                # the ACTUAL z window
    assert ex.caveats                      # must state what is NOT modelled


def test_trend_impulse_default_params_differ_from_optimized():
    a = " ".join(explain("trend_impulse_v3", {"ema_length": 50, "z_length": 50,
                                              "entry_z": 1.0, "slope_lookback": 5}).rules)
    b = " ".join(explain("trend_impulse_v3", {"ema_length": 70, "z_length": 30,
                                              "entry_z": 1.5, "slope_lookback": 5}).rules)
    assert "EMA(50)" in a and "EMA(70)" in b   # explanation tracks the params, not a fixed string


def test_expanding_z_explains_its_own_machinery():
    ex = explain("expanding_z_v4", dict(kernels.get_strategy("expanding_z_v4").default_params))
    assert "Volatility" in ex.primitives
    blob = " ".join(ex.rules).lower()
    assert "percentile" in blob            # the adaptive threshold is its signature
    assert "atr" in blob                   # ATR-normalized drift / risk overlay
    assert ex.caveats


def test_unknown_strategy_is_graceful():
    ex = explain("nope_not_real", {})
    assert ex.strategy_key == "nope_not_real"
    assert ex.rules                        # a generic, non-crashing line — never empty
    assert isinstance(ex.primitives, list)


def test_explanation_is_serialisable_for_the_report_dict():
    d = dataclasses.asdict(explain("trend_impulse_v3", {"ema_length": 50, "z_length": 50,
                                                       "entry_z": 1.0, "slope_lookback": 5}))
    assert set(d) >= {"strategy_key", "display_name", "thesis", "primitives", "rules", "caveats"}


def test_report_renders_the_strategy_explanation_section():
    report = {
        "program": "P", "hypothesis": "H", "spec_id": "abc", "git_commit": "c",
        "run_id": 1, "decision": "propose", "total_bars": 100,
        "validated": [], "rejected": [], "qualified": [], "promotion": None,
        "explanation": dataclasses.asdict(
            explain("trend_impulse_v3", {"ema_length": 70, "z_length": 50,
                                         "entry_z": 1.5, "slope_lookback": 5})),
    }
    md = render_markdown(report)
    assert "How this strategy works" in md
    assert "EMA(70)" in md                 # the live params reach the rendered report
    assert "Thesis" in md
