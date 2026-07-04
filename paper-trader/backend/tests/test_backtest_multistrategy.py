"""Multi-strategy sweep: every instrument runs across N strategies, each result
tagged with its strategy_key. Critical back-compat: the default (v3) cache
signature must stay byte-identical so the owner's large existing cache of v3
results is NOT silently invalidated."""
from sqlalchemy import select

from app.backtest import cache, sweep
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.providers.mock import MockProvider
from app.strategy.registry import get_strategy


def test_v3_cache_signature_is_preserved():
    # with-or-without the new strategy arg, the default v3 hash must be identical
    legacy = cache.params_signature(50000, window="1y")
    v3 = cache.params_signature(50000, window="1y", strategy=get_strategy("trend_impulse_v3"))
    assert legacy == v3


def test_different_strategies_get_distinct_signatures():
    v3 = cache.params_signature(50000, window="1y", strategy=get_strategy("trend_impulse_v3"))
    v4 = cache.params_signature(50000, window="1y", strategy=get_strategy("expanding_z_v4"))
    assert v3 != v4


def test_sweep_runs_each_instrument_across_multiple_strategies():
    init_db(reset=True)
    prov = MockProvider()
    rid = sweep.start_sweep(scope="liquid", intervals=["15minute"], capital=50000,
                            instruments=["NIFTY"], provider=prov,
                            strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()
    with SessionLocal() as s:
        rows = list(s.scalars(select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert {r.strategy_key for r in rows} == {"trend_impulse_v3", "expanding_z_v4"}
    nifty = [r for r in rows if r.instrument_key == "NIFTY"]
    assert len(nifty) == 2  # one row per (instrument, interval, strategy)
    assert {r.strategy_key for r in nifty} == {"trend_impulse_v3", "expanding_z_v4"}


def test_sweep_defaults_to_single_v3_when_no_strategies():
    init_db(reset=True)
    prov = MockProvider()
    rid = sweep.start_sweep(scope="liquid", intervals=["15minute"], capital=50000,
                            instruments=["NIFTY"], provider=prov)
    sweep._join()
    with SessionLocal() as s:
        rows = list(s.scalars(select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert rows and all(r.strategy_key == "trend_impulse_v3" for r in rows)
    assert len([r for r in rows if r.instrument_key == "NIFTY"]) == 1


def test_total_cell_count_includes_strategies():
    init_db(reset=True)
    prov = MockProvider()
    rid = sweep.start_sweep(scope="liquid", intervals=["15minute", "30minute"], capital=50000,
                            instruments=["NIFTY"], provider=prov,
                            strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()
    with SessionLocal() as s:
        run = s.get(BacktestRun, rid)
    assert run.total == 4   # 1 instrument × 2 intervals × 2 strategies
    assert run.done == 4
    assert set(run.to_dict()["strategies"]) == {"trend_impulse_v3", "expanding_z_v4"}
