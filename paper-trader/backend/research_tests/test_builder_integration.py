"""End-to-end: a bot-generated strategy is a first-class citizen of the research
gauntlet. A GeneratedStrategy flows through run_experiment exactly like a hand-written
one — qualify → (validate) → score → deposit Findings → return a report — with nothing
downstream aware it was machine-composed. This is the proof that generated Python
'actually runs' and can become a human-reviewable PromotionCandidate."""
import datetime as dt
import math

from research.data.store import StaticDataSource, materialize
from research.domain.models import ExperimentRun, Finding, PromotionCandidate
from research.orchestrator.run import run_experiment
from research.strategy.builder.grammar import Composition
from research.strategy.builder.load import build_strategy

_SPEC = {
    "key": "gen_trend_z_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}


def _osc_candles(Candle, n=700):
    base = dt.datetime(2024, 1, 1, 9, 15)
    out = []
    for i in range(n):
        px = 100.0 + 0.15 * i + 6.0 * math.sin(i / 9.0)
        out.append(Candle(base + dt.timedelta(minutes=15 * i), px - 0.4, px + 0.9, px - 0.9, px))
    return out


def test_generated_strategy_runs_through_run_experiment(
        research_session, inst_factory, candles_factory):
    Candle = type(candles_factory(1)[0])
    strat = build_strategy(Composition.from_dict(_SPEC))
    keys = ["OSA", "OSB"]
    src = StaticDataSource({(k, "day"): _osc_candles(Candle) for k in keys})
    datasets = [(inst_factory(k), materialize(src, inst_factory(k), "day")) for k in keys]

    report = run_experiment(
        research_session, program_name="Generated", strategy=strat,
        hypothesis_statement="a bot-composed trend/z strategy has edge",
        datasets=datasets, params={}, git_commit="gen", seed=1,
        min_trades=1, n_folds=3, min_positive_fold_frac=0.0)

    run = research_session.query(ExperimentRun).one()
    assert run.status == "completed"
    assert run.decision in ("propose", "archive")
    # the pipeline recorded knowledge for the generated strategy on each instrument
    assert research_session.query(Finding).count() == 2
    # generated strategies get an explanation too (generic fallback for a non-authored key)
    assert report["explanation"]["strategy_key"] == "gen_trend_z_v1"
    assert report["explanation"]["rules"]
    # if anything validated, it is a normal human-gated candidate (never auto-deployed)
    for cand in research_session.query(PromotionCandidate).all():
        assert cand.status == "pending"
