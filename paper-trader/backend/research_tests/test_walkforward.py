"""Walk-forward evaluation over the reuse seam. The equivalence test is the proof
that the engine.py extraction is faithful: computing signals once and replaying
trades over the full window must reproduce simulate() exactly. The fold tests pin
chronological, disjoint OOS windows — the substrate the validation gate stands on.
"""
import dataclasses
import datetime as dt
from types import SimpleNamespace

import pandas as pd

from research.evaluation import kernels
from research.evaluation import walkforward as walkforward_module
from research.evaluation.walkforward import signal_window, walk_forward
from app.core.market_hours import ist_epoch


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


def test_walk_forward_replays_only_the_locked_validation_suffix(
        fake_inst, candles_factory):
    candles = candles_factory(400)
    validation_start = candles[280].ts
    strat = _strat()
    res = walk_forward(
        candles, fake_inst, strat, dict(strat.default_params), n_folds=4,
        capital=50_000, evaluation_start=validation_start, evaluation_bars=120,
    )

    assert sum(fold.n_bars for fold in res.folds) == 120
    assert res.folds[0].start_ts == ist_epoch(validation_start)
    assert all(
        trade.entry_time >= res.folds[0].start_ts
        for fold in res.folds for trade in fold.trades
    )


def test_locked_validation_handles_empty_and_warmup_heavy_windows(
        fake_inst, candles_factory):
    candles = candles_factory(80)
    strategy = _strat()
    params = dict(strategy.default_params)

    assert walk_forward(
        candles, fake_inst, strategy, params, n_folds=2,
        evaluation_start=None, evaluation_bars=0,
    ).folds == []
    warmup_heavy = walk_forward(
        candles, fake_inst, strategy, params, n_folds=2,
        evaluation_start=candles[1].ts, evaluation_bars=79,
    )
    assert warmup_heavy.folds
    assert warmup_heavy.folds[0].start_ts > ist_epoch(candles[1].ts)


def test_locked_validation_accepts_matching_timezone_aware_dates(
        fake_inst, candles_factory):
    timezone = dt.timezone(dt.timedelta(hours=5, minutes=30))
    candles = [dataclasses.replace(candle, ts=candle.ts.replace(tzinfo=timezone))
               for candle in candles_factory(100)]
    strategy = _strat()
    result = walk_forward(
        candles, fake_inst, strategy, dict(strategy.default_params), n_folds=2,
        evaluation_start=candles[70].ts, evaluation_bars=30,
    )
    assert sum(fold.n_bars for fold in result.folds) == 30


def test_signal_window_keeps_columns_and_normalizes_positional_index():
    start = dt.datetime(2026, 1, 1, 9, 15)
    signals = pd.DataFrame({
        "date": [start + dt.timedelta(minutes=5 * offset) for offset in range(4)],
        "signal": ["warmup", "first", "second", "outside"],
    }, index=[10, 20, 30, 40])

    empty = signal_window(signals, expected_bars=0)
    selected = signal_window(
        signals, start_at=signals.iloc[1]["date"],
        stop_before=signals.iloc[3]["date"], expected_bars=2,
    )

    assert empty.empty and list(empty.columns) == ["date", "signal"]
    assert list(empty.index) == []
    assert selected["signal"].tolist() == ["first", "second"]
    assert list(selected.columns) == ["date", "signal"]
    assert list(selected.index) == [0, 1]


def test_walk_forward_preserves_defaults_policy_and_exact_fold_boundaries(monkeypatch):
    start = dt.datetime(2026, 1, 1, 9, 15)
    signals = pd.DataFrame({
        "date": [start + dt.timedelta(days=offset) for offset in range(10)],
    }, index=range(10, 20))
    risk_model = {"policy": "declared"}
    strategy = SimpleNamespace(risk_model=risk_model)
    replayed = []
    metric_capitals = []

    monkeypatch.setattr(
        walkforward_module.kernels, "compute_signals",
        lambda *_args, **_kwargs: signals,
    )
    monkeypatch.setattr(
        walkforward_module.kernels, "backtest_charge_segment", lambda _inst: "NSE_EQ",
    )

    def run_trades(window, _inst, _segment, capital, policy, *, replay_policy=None):
        assert replay_policy is None
        replayed.append((len(window), list(window.index), list(window.columns),
                         capital, policy))
        return []

    def compute_metrics(_trades, capital):
        metric_capitals.append(capital)
        return SimpleNamespace(trades=0, expectancy=0.0)

    monkeypatch.setattr(walkforward_module.kernels, "run_trades", run_trades)
    monkeypatch.setattr(walkforward_module.kernels, "compute_metrics", compute_metrics)

    result = walk_forward([], object(), strategy, {})

    assert [fold.fold_index for fold in result.folds] == [0, 1, 2, 3]
    assert [fold.n_bars for fold in result.folds] == [2, 2, 2, 4]
    assert [fold.start_ts for fold in result.folds] == [
        ist_epoch(signals.iloc[index]["date"]) for index in [0, 2, 4, 6]
    ]
    assert [fold.end_ts for fold in result.folds] == [
        ist_epoch(signals.iloc[index]["date"]) for index in [1, 3, 5, 9]
    ]
    assert replayed == [
        (2, [0, 1], ["date"], 50_000.0, risk_model),
        (2, [0, 1], ["date"], 50_000.0, risk_model),
        (2, [0, 1], ["date"], 50_000.0, risk_model),
        (4, [0, 1, 2, 3], ["date"], 50_000.0, risk_model),
    ]
    assert metric_capitals == [50_000.0] * 4

    assert walk_forward([], object(), strategy, {}, n_folds=0).folds == []
    assert len(walk_forward([], object(), SimpleNamespace(), {}, n_folds=1).folds) == 1

    monkeypatch.setattr(
        walkforward_module.kernels, "compute_signals",
        lambda *_args, **_kwargs: signals.iloc[:2],
    )
    assert len(walk_forward([], object(), SimpleNamespace(), {}, n_folds=2).folds) == 2


def test_every_walkforward_fold_preserves_explicit_replay_policy(monkeypatch, fake_inst, candles_factory):
    strategy = _strat()
    monkeypatch.setattr(strategy, "replay_policy", "pine-reversal-fixed-unit/1", raising=False)
    seen = []
    def replay(*args, **kwargs):
        seen.append(kwargs["replay_policy"])
        return []
    monkeypatch.setattr(kernels, "run_trades", replay)
    result = walk_forward(candles_factory(100), fake_inst, strategy,
                          dict(strategy.default_params), n_folds=3)
    assert len(result.folds) == 3
    assert seen == ["pine-reversal-fixed-unit/1"] * 3



def test_percentage_policy_reaches_simulate_qualification_folds_and_every_optimizer_replay(monkeypatch, fake_inst, candles_factory):
    from research.pipeline.qualify import qualify_instrument
    from research.pipeline.optimize import optimize
    from app.engine.decision_kernel import protective_band_document
    from app.backtest import engine
    from app.strategy.registry.base import Strategy

    class Protected(Strategy):
        key = "trend_impulse_v3"
        default_params = {}
        protective_band_document = None
        def signals(self, frame, **params):
            frame = frame.copy()
            for name in ("longEntry", "shortEntry", "longExit", "shortExit"):
                frame[name] = False
            frame.loc[frame.index[::4], "longEntry"] = True
            frame["close"] = 103.0
            frame["open"] = 100.0
            frame["high"] = 104.0
            frame["low"] = 99.0
            return frame

    strategy = Protected()
    strategy.protective_band_document = protective_band_document(.01, .02)
    strategy.replay_slippage_pct = .0005
    candles = candles_factory(80)
    expected = {"stop_loss_pct": .01, "take_profit_pct": .02, "slippage_pct": .0005}
    original = engine.run_trades
    seen = []
    def replay(*args, **kwargs):
        assert {name: kwargs[name] for name in expected} == expected
        seen.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(engine, "run_trades", replay)
    monkeypatch.setattr(kernels, "run_trades", replay)
    trades, _ = kernels.simulate(candles, fake_inst, "day", strategy=strategy)
    assert trades[0].reason == "TARGET"
    # All consumers receive the same frozen base fill spread.
    seen.clear()
    qualify_instrument(candles, fake_inst, "day", strategy, {}, development_bars=80)
    assert len(seen) == 1
    seen.clear()
    result = walk_forward(candles, fake_inst, strategy, {}, n_folds=2)
    assert len(seen) == 2 and result.folds[0].trades[0].reason == "TARGET"
    seen.clear()
    from research.strategy.spec import ParamSpec
    optimize(candles, fake_inst, strategy,
             space={"entry_z": ParamSpec("entry_z", "float", 1.0, values=[1.0, 2.0])},
             n_folds=2, pbo_blocks=2)
    assert len(seen) == 12  # 4 IS + 2 OOS + 2 final + 4 PBO
