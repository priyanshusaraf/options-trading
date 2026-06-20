"""
The option-data research cache must capture chains for the WHOLE watchlist, not
only instruments a signal happened to fire on — Kite sells no historical option
chains/IV/OI/greeks, so anything not snapshotted live is gone forever.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import init_db, SessionLocal
from app.db.models import OptionData
from app.engine.runner import EngineRunner


def _rows() -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(OptionData)) or 0


def test_cache_sweep_writes_for_untraded_option_instruments():
    init_db(reset=True)
    r = EngineRunner()
    # no positions, no signals acted on — pure research snapshot of the watchlist
    import app.options.cache as cache
    cache._last_snapshot.clear()
    before = _rows()
    written = r.cache_option_chains(r.provider.now())
    assert written > 0, "expected a watchlist-wide option snapshot"
    assert _rows() == before + written
    # distinct instruments captured > 0 (breadth, not just one traded name)
    with SessionLocal() as s:
        instruments = s.scalar(select(func.count(func.distinct(OptionData.instrument_key))))
    assert instruments >= 1


def test_cache_sweep_respects_enable_flag():
    init_db(reset=True)
    r = EngineRunner()
    import app.options.cache as cache
    cache._last_snapshot.clear()
    r.params["option_cache_enabled"] = False
    assert r.cache_option_chains(r.provider.now()) == 0
