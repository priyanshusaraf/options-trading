"""A generated strategy is the riskiest kind (bot-written), so its 'how this works'
explanation must be EXACT — derived from the composition itself, every rule mapping to a
named block with its real params. The constrained grammar makes this faithful by
construction: the explanation can't drift from what the code does."""
from research.strategy.builder.describe import describe_ref, explain_composition
from research.strategy.builder.grammar import Composition, parse_ref

_SPEC = {
    "key": "gen_trend_z_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}


def test_describe_ref_is_plain_language_with_real_params():
    d = describe_ref(parse_ref("ema_slope_up(50, 5)"))
    assert "EMA(50)" in d and "rising" in d.lower()
    z = describe_ref(parse_ref("zscore_cross_up(50, 1.0)"))
    assert "1.0" in z and "cross" in z.lower()


def test_explain_composition_maps_every_clause():
    ex = explain_composition(Composition.from_dict(_SPEC))
    assert ex.strategy_key == "gen_trend_z_v1"
    assert ex.thesis
    # primitives are derived from the blocks actually used
    assert "Trend" in ex.primitives and "Momentum" in ex.primitives
    joined = " ".join(ex.rules).lower()
    for token in ("enter long", "enter short", "exit long", "exit short"):
        assert token in joined
    # the real params surface in the rules (EMA length, z threshold)
    assert "ema(50)" in joined and "1.0" in " ".join(ex.rules)
    # and it is candid about being machine-generated
    assert "generat" in (ex.thesis + ex.caveats).lower()


def test_explanation_for_dispatches_on_generated_strategies():
    from research.strategy.builder.describe import explanation_for
    from research.strategy.builder.load import build_strategy
    gen = build_strategy(Composition.from_dict(_SPEC))
    ex = explanation_for(gen, {})
    assert ex.strategy_key == "gen_trend_z_v1" and ex.rules
    # a hand-written strategy still routes through the authored explanation
    from research.evaluation import kernels
    hand = kernels.get_strategy("trend_impulse_v3")
    ex2 = explanation_for(hand, dict(hand.default_params))
    assert ex2.strategy_key == "trend_impulse_v3"
