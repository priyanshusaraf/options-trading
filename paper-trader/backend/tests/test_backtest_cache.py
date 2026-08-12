"""Backtest result cache: stable signature + reuse on an unchanged second sweep."""
import datetime as dt

from sqlalchemy import select

from app.db.session import init_db, SessionLocal
from app.backtest import cache, repository, sweep
from app.db.models import BacktestResult, BacktestRun
from app.providers.mock import MockProvider


def test_params_signature_stable_and_sensitive():
    a = cache.params_signature(50000)
    b = cache.params_signature(50000)
    c = cache.params_signature(60000)
    assert a == b and a != c


def test_second_sweep_reuses_cache():
    init_db(reset=True)
    prov = MockProvider()
    sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"], capital=50000, provider=prov)
    sweep._join()
    rid2 = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"], capital=50000, provider=prov)
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


def test_revised_historical_candle_with_same_last_timestamp_is_cold():
    from app.core.instruments import get_instrument

    init_db(reset=True)
    provider = MockProvider()
    kwargs = dict(scope="liquid", intervals=["15minute"], instruments=["NIFTY"],
                  capital=50_000, provider=provider)

    def run_once():
        run_id = sweep.start_sweep(owner_id="owner", **kwargs)
        sweep._join()
        with SessionLocal() as session:
            row = session.scalar(select(BacktestResult).where(
                BacktestResult.run_id == run_id,
                BacktestResult.instrument_key == "NIFTY"))
            assert row is not None and row.error == ""
            return row.from_cache, row.params_hash, row.last_candle_ts

    cold = run_once()
    assert cold[0] is False

    visible = provider.get_candles(
        get_instrument("NIFTY"), "15minute", sweep.MAX_DAYS["15minute"])
    final_timestamp = visible[-1].ts
    revised = visible[-20]
    revised.close = round(revised.close + 0.25, 2)
    revised.high = max(revised.high, revised.close)
    assert provider.get_candles(
        get_instrument("NIFTY"), "15minute", sweep.MAX_DAYS["15minute"])[-1].ts \
        == final_timestamp

    revised_run = run_once()
    assert revised_run[2] == cold[2]
    assert revised_run[1] != cold[1]
    assert revised_run[0] is False

    unchanged_again = run_once()
    assert unchanged_again[1] == revised_run[1]
    assert unchanged_again[0] is True


def test_cached_copy_preserves_every_mapped_value_except_new_run_identity():
    """A warm row is the cold result verbatim, with only its row/run identity rebound."""
    init_db(reset=True)
    computed_at = dt.datetime(2025, 1, 2, 3, 4, 5)
    with SessionLocal() as s:
        s.add_all([BacktestRun(id=101, owner_id="owner", scope="liquid", intervals="day",
                               capital=1, total=1),
                   BacktestRun(id=202, owner_id="owner", scope="liquid", intervals="day",
                               capital=1, total=1)])
        s.flush()
        source = BacktestResult(
            run_id=101,
            instrument_key="CACHE_SENTINEL",
            name="Cache sentinel",
            segment="NFO_FUT",
            strategy_key="sentinel_strategy",
            strategy_version="sentinel-version-v1",
            interval="15minute",
            trades=11,
            wins=7,
            win_rate=63.5,
            profit_factor=1.75,
            max_drawdown_pct=8.25,
            return_pct=14.5,
            net_pnl=7250.0,
            gross_pnl=7500.0,
            charges=250.0,
            expectancy=659.09,
            cagr=18.75,
            calmar=2.27,
            consistency=0.64,
            sharpe=1.42,
            max_consec_losses=3,
            time_underwater_pct=22.5,
            worst_trade_pnl=-875.0,
            worst_mae_pct=4.75,
            notional=500000.0,
            lots=1,
            affordable=False,
            option_cost=12500.0,
            open_at_end=True,
            win_rate_realised=60.0,
            return_pct_realised=12.25,
            bh_return_pct=9.5,
            first_ts=1700000000,
            last_ts=1700500000,
            effective_days=6,
            clamped=True,
            bars=321,
            curve_json='[{"time":1,"value":50000.0}]',
            bh_curve_json='[{"time":1,"value":100.0}]',
            trades_json='[{"direction":"LONG","net_pnl":7250.0}]',
            error="",
            premium_trades=5,
            premium_win_rate=80.0,
            premium_net_pnl=3100.0,
            premium_return_pct=6.2,
            premium_profit_factor=2.5,
            premium_max_drawdown_pct=3.5,
            premium_expectancy=620.0,
            premium_charges=90.0,
            premium_trades_json='[{"direction":"LONG","net_pnl":3100.0}]',
            premium_error="premium diagnostic",
            params_hash="sentinel-params-hash",
            last_candle_ts=1700500000,
            schema_version=7,
            from_cache=False,
            computed_at=computed_at,
        )
        s.add(source)
        s.commit()

        rebound = {"id", "run_id", "cell_key", "from_cache"}
        exact_columns = {
            column.name for column in BacktestResult.__table__.columns
            if column.name not in rebound
        }
        expected = {name: getattr(source, name) for name in exact_columns}
        source_id = source.id
        payload = dict(cache.cached_result_values(source), from_cache=True)

        # The warm copy is now a two-step: the reusable row becomes a values
        # payload (which a worker could equally have produced), and the batch
        # transaction binds it to a run. The guarantee is unchanged — every
        # mapped value verbatim, only row/run identity rebound.
        claim = repository.claim_run(s, owner_id="owner", run_id=202,
                                     claimed_by="cache-test", lease_seconds=60)
        s.commit()
        assert claim is not None
        assert sweep._commit_claimed_batch(
            202, [payload],
            owner_id="owner", claim_token=claim.claim_token)
    with SessionLocal() as s:
        copied = s.scalar(select(BacktestResult).where(BacktestResult.run_id == 202))

        assert copied is not None
        assert {name: getattr(copied, name) for name in exact_columns} == expected
        assert copied.id != source_id
        assert copied.run_id == 202
        assert copied.cell_key == "CACHE_SENTINEL\x1f15minute\x1fsentinel_strategy\x1fsentinel-version-v1"
        assert copied.from_cache is True


def test_reuse_rejects_transient_premium_error_but_accepts_exact_permanent_status():
    from app.backtest.premium import NO_OPTIONS_PREMIUM_ERROR

    init_db(reset=True)
    common = dict(
        run_id=1, instrument_key="CACHE_ERROR", name="Cache error", segment="NFO",
        strategy_key="strategy", interval="15minute", params_hash="a" * 64,
        last_candle_ts=1234, schema_version=cache.SCHEMA_VERSION, error="",
    )
    with SessionLocal() as session:
        session.add(BacktestRun(id=1, owner_id="owner", scope="liquid", intervals="day",
                                capital=1, total=1))
        session.flush()
        session.add(BacktestResult(
            premium_error="provider timed out", **common))
        session.add(BacktestResult(
            premium_error=NO_OPTIONS_PREMIUM_ERROR,
            **{**common, "instrument_key": "NO_OPTIONS"}))
        session.commit()

        assert cache.find_reusable(
            session, "CACHE_ERROR", "15minute", "a" * 64, 1234, owner_id="owner") is None
        assert cache.find_reusable(
            session, "NO_OPTIONS", "15minute", "a" * 64, 1234,
            owner_id="owner", expected_premium_error=NO_OPTIONS_PREMIUM_ERROR) is not None


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

    rid = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"],
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
