"""Walk-forward evaluation over the reuse seam. The equivalence test is the proof
that the engine.py extraction is faithful: computing signals once and replaying
trades over the full window must reproduce simulate() exactly. The fold tests pin
chronological, disjoint OOS windows — the substrate the validation gate stands on.
"""
from research.evaluation import kernels
from research.evaluation.walkforward import walk_forward


def _strat():
    return kernels.get_strategy("trend_impulse_v3")


def test_run_trades_after_compute_signals_matches_simulate(fake_inst, candles_factory):
    candles = candles_factory(300)
    strat = _strat()
    params = dict(strat.default_params)
    ref_trades, _ = kernels.simulate(candles, fake_inst, "day", capital=50_000,
                                     strategy=strat, params=params)
    sig = kernels.compute_signals(candles, strat, params)
    seg = kernels.backtest_charge_segment(fake_inst)
    trades = kernels.run_trades(sig, fake_inst, seg, 50_000,
                                getattr(strat, "risk_model", None))
    assert [t.to_dict() for t in trades] == [t.to_dict() for t in ref_trades]


def test_walk_forward_produces_n_folds(fake_inst, candles_factory):
    strat = _strat()
    res = walk_forward(candles_factory(400), fake_inst, strat,
                       dict(strat.default_params), n_folds=4, capital=50_000)
    assert len(res.folds) == 4
    assert all(f.metrics is not None for f in res.folds)


def test_walk_forward_folds_are_chronological_and_disjoint(fake_inst, candles_factory):
    strat = _strat()
    res = walk_forward(candles_factory(400), fake_inst, strat,
                       dict(strat.default_params), n_folds=4, capital=50_000)
    ends = [f.end_ts for f in res.folds]
    starts = [f.start_ts for f in res.folds]
    assert starts == sorted(starts) and ends == sorted(ends)   # chronological
    for f in res.folds:
        for t in f.trades:
            assert f.start_ts <= t.entry_time <= f.end_ts       # trades stay in-fold


def test_walk_forward_no_folds_when_folds_exceed_bars(fake_inst, candles_factory):
    # more folds than available signal bars -> each fold would be empty -> none returned
    strat = _strat()
    res = walk_forward(candles_factory(80), fake_inst, strat,
                       dict(strat.default_params), n_folds=1000, capital=50_000)
    assert res.folds == []
