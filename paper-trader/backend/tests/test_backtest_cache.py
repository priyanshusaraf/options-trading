"""Backtest result cache: stable signature + reuse on an unchanged second sweep."""
from sqlalchemy import select

from app.db.session import init_db, SessionLocal
from app.backtest import cache, sweep
from app.db.models import BacktestResult
from app.providers.mock import MockProvider


def test_params_signature_stable_and_sensitive():
    a = cache.params_signature(50000)
    b = cache.params_signature(50000)
    c = cache.params_signature(60000)
    assert a == b and a != c


def test_second_sweep_reuses_cache():
    init_db(reset=True)
    prov = MockProvider()
    sweep.start_sweep(scope="liquid", intervals=["15minute"], capital=50000, provider=prov)
    sweep._join()
    rid2 = sweep.start_sweep(scope="liquid", intervals=["15minute"], capital=50000, provider=prov)
    sweep._join()
    with SessionLocal() as s:
        rows2 = list(s.scalars(select(BacktestResult).where(BacktestResult.run_id == rid2)))
    assert rows2
    # the second, unchanged sweep must reuse at least one prior result
    assert any(r.from_cache for r in rows2 if not r.error)
    # and the reused metrics must match the originals (same instrument/interval)
    with SessionLocal() as s:
        first = s.scalars(select(BacktestResult).where(
            BacktestResult.run_id == 1, BacktestResult.from_cache == False)).first()
    cached = next(r for r in rows2 if r.from_cache and r.instrument_key == first.instrument_key)
    assert round(cached.net_pnl, 2) == round(first.net_pnl, 2)
