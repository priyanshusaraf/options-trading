"""One admitted strategy per durable backtest run."""
from sqlalchemy import select

from app.backtest import cache, sweep
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.providers.mock import MockProvider
from app.strategy.registry import get_strategy
import pytest


class CountingMockProvider(MockProvider):
    def __init__(self):
        super().__init__()
        self.candle_reads = []

    def get_candles(self, inst, interval, days, end=None):
        self.candle_reads.append((inst.key, interval, days, end))
        return super().get_candles(inst, interval, days, end=end)


def _start(admitted_backtest_receipt, provider, **kwargs):
    strategies = kwargs.pop("strategies", None)
    intervals = kwargs.pop("intervals", ["15minute"])
    return sweep.start_sweep(
        owner_id="owner", scope="liquid", intervals=intervals,
        instruments=["NIFTY"], provider=provider,
        strategies=strategies, **kwargs,
        **admitted_backtest_receipt())


def test_default_strategy_signature_resolves_consistently():
    # with-or-without an explicit strategy, the current-schema hash is identical
    legacy = cache.params_signature(50000, window="1y")
    v3 = cache.params_signature(50000, window="1y", strategy=get_strategy("trend_impulse_v3"))
    assert legacy == v3


def test_different_strategies_get_distinct_signatures():
    v3 = cache.params_signature(50000, window="1y", strategy=get_strategy("trend_impulse_v3"))
    v4 = cache.params_signature(50000, window="1y", strategy=get_strategy("expanding_z_v4"))
    assert v3 != v4


def test_multiple_strategies_are_refused_before_provider_io(admitted_backtest_receipt):
    """One receipt names one executable IR graph; it cannot authorize two runs."""
    init_db(reset=True)
    class Provider(MockProvider):
        def get_candles(self, *_args, **_kwargs):
            raise AssertionError("multiple strategies must refuse before provider I/O")
    with pytest.raises(Exception, match="ADMISSION_REQUIRED"):
        _start(admitted_backtest_receipt, Provider(),
               strategies=["trend_impulse_v3", "expanding_z_v4"])


def test_one_admitted_strategy_produces_one_row(admitted_backtest_receipt):
    init_db(reset=True)
    prov = MockProvider()
    rid = _start(admitted_backtest_receipt, prov, capital=50000)
    sweep._join()
    with SessionLocal() as s:
        rows = list(s.scalars(select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert rows and len({row.strategy_key for row in rows}) == 1
    assert len([r for r in rows if r.instrument_key == "NIFTY"]) == 1


def test_one_admitted_strategy_counts_each_interval_once(admitted_backtest_receipt):
    init_db(reset=True)
    prov = MockProvider()
    rid = _start(admitted_backtest_receipt, prov, intervals=["15minute", "30minute"], capital=50000)
    sweep._join()
    with SessionLocal() as s:
        run = s.get(BacktestRun, rid)
    assert run.total == run.done == 2
    assert run.to_dict()["strategies"] == [run.strategies]


def test_one_strategy_sweep_reads_each_dataset_once(admitted_backtest_receipt):
    init_db(reset=True)
    provider = CountingMockProvider()
    rid = _start(admitted_backtest_receipt, provider,
                 intervals=["15minute", "30minute"], capital=50_000)
    sweep._join()

    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert len(rows) == 2
    assert [(key, interval) for key, interval, _days, _end in provider.candle_reads] == [
        ("NIFTY", "15minute"),
        ("NIFTY", "30minute"),
    ]


def test_provider_failure_produces_one_admitted_strategy_refusal(admitted_backtest_receipt):
    class FailingProvider(CountingMockProvider):
        def get_candles(self, inst, interval, days, end=None):
            self.candle_reads.append((inst.key, interval, days, end))
            raise RuntimeError("dataset unavailable")

    init_db(reset=True)
    provider = FailingProvider()
    rid = _start(admitted_backtest_receipt, provider)
    sweep._join()
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert len(provider.candle_reads) == 1
    assert len(rows) == 1
    assert {row.error for row in rows} == {"candles: dataset unavailable"}


def test_thin_dataset_produces_one_admitted_strategy_refusal(admitted_backtest_receipt):
    class ThinProvider(CountingMockProvider):
        def get_candles(self, inst, interval, days, end=None):
            rows = super().get_candles(inst, interval, days, end=end)
            return rows[:10]

    init_db(reset=True)
    provider = ThinProvider()
    rid = _start(admitted_backtest_receipt, provider)
    sweep._join()
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert len(provider.candle_reads) == 1
    assert len(rows) == 1
    assert {row.error for row in rows} == {"insufficient history"}


def test_out_of_range_window_refuses_without_provider_reads(admitted_backtest_receipt):
    init_db(reset=True)
    provider = CountingMockProvider()
    rid = _start(admitted_backtest_receipt, provider,
                 start_date="2010-01-01", end_date="2010-01-31")
    sweep._join()
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert provider.candle_reads == []
    assert len(rows) == 1
    assert all("window older than Kite max" in row.error for row in rows)
