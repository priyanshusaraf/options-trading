"""Shared fixtures for the research-plane test suite (run: `pytest research_tests`).

Each test gets a throwaway file-backed research.db (WAL needs a real file), with
the full research schema created — including the immutability triggers. Also
provides deterministic synthetic candles + a fake instrument for offline
evaluation tests (no provider, no network).
"""
import dataclasses
import datetime as dt

import pytest

from research.domain.base import init_research_db, make_engine, make_sessionmaker


@dataclasses.dataclass
class Candle:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float


class FakeInst:
    """Minimal instrument for offline backtests — the fields simulate()/run_trades()
    actually read."""
    segment = "NSE"
    lot_size = 1
    strike_step = 1.0
    has_options = False
    key = "TEST"
    name = "TEST"


def make_series(n=300):
    """Deterministic candles with alternating up/down trend regimes, long enough to
    clear the EMA50 warmup and produce trades across multiple walk-forward folds."""
    base = dt.datetime(2024, 1, 1, 9, 15)
    out, px = [], 100.0
    for i in range(n):
        px += 1.0 if (i // 15) % 2 == 0 else -0.8
        out.append(Candle(base + dt.timedelta(days=i), px, px + 1.0, px - 1.0, px + 0.5))
    return out


@pytest.fixture
def fake_inst():
    return FakeInst()


@pytest.fixture
def candles_factory():
    return make_series


@pytest.fixture
def research_session(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as s:
        yield s
