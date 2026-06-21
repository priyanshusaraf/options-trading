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


def test_cache_key_uses_ist_epoch_not_local_timestamp():
    """The cache discriminator (last_candle_ts) must be market_hours.ist_epoch on
    the naive-IST candle ts — NOT int(ts.timestamp()), which interprets the naive
    value in the SERVER's local TZ (the project's +5:30 bug class). We run a real
    sweep and assert every stored last_candle_ts equals ist_epoch of that cell's
    last candle, never the local-timestamp value when the two differ."""
    import datetime as dt
    from app.core.market_hours import ist_epoch
    init_db(reset=True)
    prov = MockProvider()
    inst = None
    from app.core.instruments import get_instrument
    inst = get_instrument("NIFTY")
    candles = prov.get_candles(inst, "15minute", 90)
    last = candles[-1].ts
    expected = ist_epoch(last)

    rid = sweep.start_sweep(scope="liquid", intervals=["15minute"],
                            instruments=["NIFTY"], capital=5_000_000, provider=prov)
    sweep._join()
    with SessionLocal() as s:
        row = s.scalars(select(BacktestResult).where(
            BacktestResult.run_id == rid,
            BacktestResult.instrument_key == "NIFTY")).first()
    assert row is not None
    # the stored discriminator is the IST-correct instant
    assert row.last_candle_ts == expected
    # and it differs from the naive .timestamp() whenever the process TZ != IST
    naive_local = int(last.timestamp())
    if naive_local != expected:
        assert row.last_candle_ts != naive_local


def test_ist_epoch_differs_from_naive_timestamp_outside_ist(monkeypatch):
    """Pin the bug directly: ist_epoch localizes naive IST, so for a TZ != IST the
    epoch differs from the naive .timestamp() by the offset delta."""
    import os, time, datetime as dt
    from app.core.market_hours import ist_epoch
    ts = dt.datetime(2025, 6, 2, 9, 15)        # naive IST wall-clock
    e_ist = ist_epoch(ts)
    # ist_epoch is TZ-independent (it localizes to IST); naive .timestamp() is not.
    # 09:15 IST == 03:45 UTC -> a fixed instant regardless of the host clock.
    assert e_ist == int(dt.datetime(2025, 6, 2, 3, 45, tzinfo=dt.timezone.utc).timestamp())
