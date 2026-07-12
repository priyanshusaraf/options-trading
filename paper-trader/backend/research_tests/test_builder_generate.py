"""The generate-and-evaluate orchestrator: the bot enumerates its own compositions,
persists each (so a candidate can carry its exact composition to the human), and runs
each through the identical research gauntlet. This is 'the bot generates its own
strategies and they actually run' end to end."""
import datetime as dt
import json
import math

from research.data.store import StaticDataSource, materialize
from research.domain.models import (
    ExperimentRun,
    GeneratedStrategyRecord,
    PromotionCandidate,
)
from research.orchestrator.generate import run_generated
from research.strategy.builder.grammar import Composition


def _osc_candles(Candle, n=700):
    base = dt.datetime(2024, 1, 1, 9, 15)
    return [Candle(base + dt.timedelta(minutes=15 * i),
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0)) - 0.4,
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0)) + 0.9,
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0)) - 0.9,
                   (100 + 0.15 * i + 6 * math.sin(i / 9.0))) for i in range(n)]


def test_run_generated_evaluates_and_persists_compositions(
        research_session, inst_factory, candles_factory):
    Candle = type(candles_factory(1)[0])
    keys = ["GOLDM", "SILVERM"]                       # the always-allowed research sandbox
    src = StaticDataSource({(k, "day"): _osc_candles(Candle) for k in keys})
    instruments = [inst_factory(k) for k in keys]

    reports = run_generated(research_session, src, instruments, "day", limit=4,
                            git_commit="gen", min_trades=1, n_folds=3,
                            min_positive_fold_frac=0.0)

    assert len(reports) == 4
    # every evaluated strategy is a generated one and was run to completion
    assert all(r["explanation"]["strategy_key"].startswith("gen_") for r in reports)
    assert research_session.query(ExperimentRun).count() == 4

    # each generated strategy's composition is persisted and round-trips to a Composition
    recs = research_session.query(GeneratedStrategyRecord).all()
    assert len(recs) == 4
    for rec in recs:
        comp = Composition.from_dict(json.loads(rec.composition_json))
        assert comp.key == rec.key
        assert "def compute(df" in rec.source          # the emitted source is stored too

    # any candidate that cleared validation is human-gated, never auto-deployed
    for cand in research_session.query(PromotionCandidate).all():
        assert cand.status == "pending"


def test_run_generated_respects_the_limit(research_session, inst_factory, candles_factory):
    Candle = type(candles_factory(1)[0])
    src = StaticDataSource({("GOLDM", "day"): _osc_candles(Candle)})
    reports = run_generated(research_session, src, [inst_factory("GOLDM")], "day",
                            limit=2, git_commit="g", min_trades=1, n_folds=3,
                            min_positive_fold_frac=0.0)
    assert len(reports) == 2
    assert research_session.query(GeneratedStrategyRecord).count() == 2
