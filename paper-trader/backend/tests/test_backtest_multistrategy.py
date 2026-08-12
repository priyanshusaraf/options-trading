"""Multi-strategy sweep: one acquired dataset fans out across N strategies."""
from sqlalchemy import select

from app.backtest import cache, sweep
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.providers.mock import MockProvider
from app.strategy.registry import get_strategy
import json
import pytest


class CountingMockProvider(MockProvider):
    def __init__(self):
        super().__init__()
        self.candle_reads = []

    def get_candles(self, inst, interval, days, end=None):
        self.candle_reads.append((inst.key, interval, days, end))
        return super().get_candles(inst, interval, days, end=end)


_GENERATED = {
    "key": "gen_sweep_owner",
    "longEntry": {"all": ["ema_slope_up(50,5)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)"]},
    "longExit": {"any": ["zscore_lt(50,0.0)"]},
    "shortExit": {"any": ["zscore_gt(50,0.0)"]},
}


@pytest.mark.parametrize("workers", (1, 2))
def test_generated_sweep_resolves_and_worker_hydrates_only_the_requested_owner(workers):
    from app.core import generated_strategies
    from app.db.models import Organization
    from app.strategy import registry

    init_db(reset=True)
    other_composition = dict(_GENERATED)
    other_composition["longExit"] = {"any": ["zscore_lt(50,0.5)"]}
    with SessionLocal() as session:
        session.add(Organization(organization_id="owner.other", name="Other"))
        generated_strategies.save_generated(
            session, "gen_sweep_owner", json.dumps(_GENERATED), owner_id="owner")
        generated_strategies.save_generated(
            session, "gen_sweep_owner", json.dumps(other_composition),
            owner_id="owner.other")
        session.commit()
        generated_strategies.register_all(session, owner_id="owner")
        generated_strategies.register_all(session, owner_id="owner.other")
    try:
        with pytest.raises(Exception, match="refusing to substitute"):
            sweep.start_sweep(
                owner_id="owner.missing", scope="liquid", intervals=["15minute"],
                instruments=["NIFTY"], provider=MockProvider(),
                strategies=["gen_sweep_owner"], workers=workers)

        run_id = sweep.start_sweep(
            owner_id="owner.other", scope="liquid", intervals=["15minute"],
            instruments=["NIFTY"], provider=MockProvider(),
            strategies=["gen_sweep_owner"], workers=workers)
        sweep._join()
        with SessionLocal() as session:
            row = session.scalar(select(BacktestResult).where(
                BacktestResult.run_id == run_id,
                BacktestResult.strategy_key == "gen_sweep_owner"))
            assert row is not None and row.error == ""
    finally:
        registry._GENERATED_REGISTRY.pop(("owner", "gen_sweep_owner"), None)
        registry._GENERATED_REGISTRY.pop(("owner.other", "gen_sweep_owner"), None)


def test_default_strategy_signature_resolves_consistently():
    # with-or-without an explicit strategy, the current-schema hash is identical
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
    rid = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"], capital=50000,
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
    rid = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute"], capital=50000,
                            instruments=["NIFTY"], provider=prov)
    sweep._join()
    with SessionLocal() as s:
        rows = list(s.scalars(select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert rows and all(r.strategy_key == "trend_impulse_v3" for r in rows)
    assert len([r for r in rows if r.instrument_key == "NIFTY"]) == 1


def test_total_cell_count_includes_strategies():
    init_db(reset=True)
    prov = MockProvider()
    rid = sweep.start_sweep(owner_id="owner", scope="liquid", intervals=["15minute", "30minute"], capital=50000,
                            instruments=["NIFTY"], provider=prov,
                            strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()
    with SessionLocal() as s:
        run = s.get(BacktestRun, rid)
    assert run.total == 4   # 1 instrument × 2 intervals × 2 strategies
    assert run.done == 4
    assert set(run.to_dict()["strategies"]) == {"trend_impulse_v3", "expanding_z_v4"}


def test_multi_strategy_sweep_reads_each_dataset_once():
    init_db(reset=True)
    provider = CountingMockProvider()
    rid = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute", "30minute"], capital=50_000,
        instruments=["NIFTY"], provider=provider,
        strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()

    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert len(rows) == 4
    assert [(key, interval) for key, interval, _days, _end in provider.candle_reads] == [
        ("NIFTY", "15minute"),
        ("NIFTY", "30minute"),
    ]


def _result_artifact(row) -> dict:
    excluded = {"id", "run_id", "from_cache", "computed_at"}
    return {
        column.name: getattr(row, column.name)
        for column in BacktestResult.__table__.columns
        if column.name not in excluded
    }


def test_shared_acquisition_preserves_exact_cold_strategy_results():
    strategies = ["trend_impulse_v3", "expanding_z_v4"]
    init_db(reset=True)
    independent_provider = CountingMockProvider()
    independent = {}
    for strategy in strategies:
        rid = sweep.start_sweep(owner_id="owner",
            scope="liquid", intervals=["15minute"], capital=50_000,
            instruments=["NIFTY"], provider=independent_provider,
            strategies=[strategy])
        sweep._join()
        with SessionLocal() as session:
            row = session.scalar(select(BacktestResult).where(
                BacktestResult.run_id == rid,
                BacktestResult.strategy_key == strategy))
            independent[strategy] = _result_artifact(row)

    init_db(reset=True)
    shared_provider = CountingMockProvider()
    rid = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], capital=50_000,
        instruments=["NIFTY"], provider=shared_provider, strategies=strategies)
    sweep._join()
    with SessionLocal() as session:
        shared = {
            row.strategy_key: _result_artifact(row)
            for row in session.scalars(
                select(BacktestResult).where(BacktestResult.run_id == rid))
        }
    assert shared == independent


def test_provider_failure_is_read_once_and_fanned_out_per_strategy():
    class FailingProvider(CountingMockProvider):
        def get_candles(self, inst, interval, days, end=None):
            self.candle_reads.append((inst.key, interval, days, end))
            raise RuntimeError("dataset unavailable")

    init_db(reset=True)
    provider = FailingProvider()
    rid = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], instruments=["NIFTY"],
        provider=provider, strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert len(provider.candle_reads) == 1
    assert len(rows) == 2
    assert {row.error for row in rows} == {"candles: dataset unavailable"}


def test_thin_dataset_is_read_once_and_fanned_out_per_strategy():
    class ThinProvider(CountingMockProvider):
        def get_candles(self, inst, interval, days, end=None):
            rows = super().get_candles(inst, interval, days, end=end)
            return rows[:10]

    init_db(reset=True)
    provider = ThinProvider()
    rid = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], instruments=["NIFTY"],
        provider=provider, strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert len(provider.candle_reads) == 1
    assert len(rows) == 2
    assert {row.error for row in rows} == {"insufficient history"}


def test_out_of_range_window_is_fanned_out_without_provider_reads():
    init_db(reset=True)
    provider = CountingMockProvider()
    rid = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], instruments=["NIFTY"],
        provider=provider, start_date="2010-01-01", end_date="2010-01-31",
        strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == rid)))
    assert provider.candle_reads == []
    assert len(rows) == 2
    assert all("window older than Kite max" in row.error for row in rows)


def test_cold_sweep_builds_one_frame_and_evaluates_strategy_once(monkeypatch):
    from app.backtest import engine, premium

    init_db(reset=True)
    provider = CountingMockProvider()
    strategy = get_strategy("trend_impulse_v3")
    counts = {"engine_frame": 0, "premium_frame": 0, "signals": 0}
    original_engine_frame = engine._candles_to_df
    original_premium_frame = premium._candles_to_df
    original_signals = strategy.signals

    def engine_frame(candles):
        counts["engine_frame"] += 1
        return original_engine_frame(candles)

    def premium_frame(candles):
        counts["premium_frame"] += 1
        return original_premium_frame(candles)

    def signals(frame, **params):
        counts["signals"] += 1
        return original_signals(frame, **params)

    monkeypatch.setattr(engine, "_candles_to_df", engine_frame)
    monkeypatch.setattr(premium, "_candles_to_df", premium_frame)
    monkeypatch.setattr(strategy, "signals", signals)

    sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], instruments=["NIFTY"],
        provider=provider, strategies=[strategy.key])
    sweep._join()
    assert counts == {"engine_frame": 1, "premium_frame": 0, "signals": 1}

    counts.update(engine_frame=0, premium_frame=0, signals=0)
    sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], instruments=["NIFTY"],
        provider=provider, strategies=[strategy.key])
    sweep._join()
    assert counts == {"engine_frame": 0, "premium_frame": 0, "signals": 0}


def test_multiple_strategies_share_one_canonical_base_frame(monkeypatch):
    from app.backtest import engine, premium

    init_db(reset=True)
    provider = CountingMockProvider()
    counts = {"engine_frame": 0, "premium_frame": 0}
    original_engine_frame = engine._candles_to_df
    original_premium_frame = premium._candles_to_df

    def engine_frame(candles):
        counts["engine_frame"] += 1
        return original_engine_frame(candles)

    def premium_frame(candles):
        counts["premium_frame"] += 1
        return original_premium_frame(candles)

    monkeypatch.setattr(engine, "_candles_to_df", engine_frame)
    monkeypatch.setattr(premium, "_candles_to_df", premium_frame)
    sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], instruments=["NIFTY"],
        provider=provider,
        strategies=["trend_impulse_v3", "expanding_z_v4"])
    sweep._join()
    assert counts == {"engine_frame": 1, "premium_frame": 0}
