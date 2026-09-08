"""Pipeline stages: qualification (where does the edge live?), validation (hard
gates before ranking), scoring (DSR-primary rank + Pareto front). The pure gate/
scoring logic is tested with injected data; qualify()/validate() are smoke-tested
end-to-end over synthetic candles.
"""
import dataclasses

from research.evaluation import kernels
from research.pipeline.qualify import qualification_gate, qualify, qualify_instrument
from research.pipeline.score import build_scorecard, pareto_front, rank
from research.pipeline.validate import slippage_stressed_nets, validate


# ---- qualification gate ----
def test_qualification_gate_passes_strong_edge():
    ok, reason = qualification_gate([3.0] * 60, min_trades=30, seed=1)
    assert ok and reason == "qualified"


def test_qualification_gate_rejects_too_few_trades():
    ok, reason = qualification_gate([3.0] * 10, min_trades=30, seed=1)
    assert not ok and "insufficient" in reason


def test_qualification_gate_rejects_unconfident_edge():
    ok, reason = qualification_gate([10.0, -9.5] * 30, min_trades=30, seed=1)
    assert not ok and "confidently" in reason


# ---- slippage stress ----
@dataclasses.dataclass
class _T:
    net_pnl: float
    notional: float
    entry_price: float = 100.0
    qty: int = 1


def test_slippage_stress_kills_thin_edge():
    trades = [_T(net_pnl=50.0, notional=100_000.0)] * 20
    stressed = slippage_stressed_nets(trades, slippage_bps=5.0, mult=2.0)
    # round-trip cost 2*5bps*100k*2 = 200 > 50 profit -> negative
    assert all(s < 0 for s in stressed)


# ---- scorecard / ranking / pareto ----
def _metrics(consistency, trades, calmar=1.0, return_pct=10.0):
    m = kernels.BTMetrics()
    m.consistency = consistency
    m.trades = trades
    m.calmar = calmar
    m.return_pct = return_pct
    return m


def test_build_scorecard_computes_dsr():
    sc = build_scorecard("A", _metrics(0.2, 200), n_trials=1)
    assert sc.dsr > 0.9
    assert sc.components["trades"] == 200


def test_rank_orders_by_dsr_descending():
    a = build_scorecard("A", _metrics(0.25, 200))
    b = build_scorecard("B", _metrics(0.05, 200))
    assert [s.key for s in rank([b, a])] == ["A", "B"]


def test_pareto_front_excludes_dominated():
    hi = build_scorecard("HI", _metrics(0.3, 200, calmar=3.0))
    lo = build_scorecard("LO", _metrics(0.1, 200, calmar=0.5))
    front = {s.key for s in pareto_front([hi, lo], dims=[("dsr", True), ("calmar", True)])}
    assert "HI" in front and "LO" not in front


# ---- integration over synthetic candles ----
def test_qualify_and_validate_run_end_to_end(fake_inst, candles_factory):
    strat = kernels.get_strategy("trend_impulse_v3")
    candles = candles_factory(400)
    outcome = qualify([(fake_inst, candles)], strat, dict(strat.default_params),
                      interval="day", min_trades=1, seed=1)
    assert len(outcome.evaluations) == 1
    v = validate(candles, fake_inst, strat, dict(strat.default_params),
                 n_folds=4, min_oos_trades=1, min_positive_fold_frac=0.0)
    assert isinstance(v.passed, bool)
    assert {"min_oos_trades", "temporal_stability", "confident_edge",
            "slippage_stress_2x"} <= set(v.gates)


def test_qualification_is_independent_of_locked_validation_prices(
        fake_inst, candles_factory):
    candles = candles_factory(400)
    cutoff = 280
    changed = candles[:cutoff] + [
        dataclasses.replace(
            candle, open=candle.open * 10, high=candle.high * 10,
            low=candle.low * 10, close=candle.close * 10,
        )
        for candle in candles[cutoff:]
    ]
    strategy = kernels.get_strategy("trend_impulse_v3")
    kwargs = {
        "min_trades": 1,
        "development_end": candles[cutoff].ts,
        "development_bars": cutoff,
    }

    original = qualify_instrument(
        candles, fake_inst, "day", strategy, dict(strategy.default_params), **kwargs,
    )
    altered = qualify_instrument(
        changed, fake_inst, "day", strategy, dict(strategy.default_params), **kwargs,
    )

    assert original.qualified == altered.qualified
    assert original.net_pnls == altered.net_pnls


def test_qualification_preserves_explicit_replay_policy(monkeypatch, fake_inst, candles_factory):
    strategy = kernels.get_strategy("trend_impulse_v3")
    monkeypatch.setattr(strategy, "replay_policy", "pine-reversal-fixed-unit/1", raising=False)
    seen = []
    def replay(*args, **kwargs):
        seen.append(kwargs["replay_policy"])
        return []
    monkeypatch.setattr(kernels, "run_trades", replay)
    candles = candles_factory(100)
    qualify_instrument(candles, fake_inst, "day", strategy, dict(strategy.default_params),
                       development_end=candles[80].ts, min_trades=1)
    assert seen == ["pine-reversal-fixed-unit/1"]
