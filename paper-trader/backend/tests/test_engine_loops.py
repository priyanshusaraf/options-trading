"""Split engine lanes: decomposition parity, per-instrument intervals,
entry blocks, trailing-stop integration, and the async iterations."""
import asyncio

from sqlalchemy import select

from app.db.session import init_db, SessionLocal
from app.db.models import InstrumentState
from app.engine.runner import EngineRunner
from app.core import config


def _runner():
    init_db(reset=True)
    return EngineRunner()


def test_runner_has_split_methods_and_state():
    r = _runner()
    for m in ("scan_signals", "mark_and_exit_positions", "process_entries",
              "set_interval", "set_entries_blocked", "run_risk_loop", "run_signal_loop"):
        assert hasattr(r, m)
    assert isinstance(r.intervals, dict)
    assert r.health is not None
    assert r._lock is not None


def test_tick_still_advances_and_keeps_ledger_valid():
    r = _runner()
    for _ in range(120):
        r.tick(); r.provider.advance()
    assert r.broker.reconcile()["diff"] == 0.0
    assert r.tick_count == 120


def test_interval_default_and_set():
    r = _runner()
    assert r._interval_for("NIFTY") == config.DEFAULT_LIVE_INTERVAL
    r.set_interval("NIFTY", "60minute")
    assert r._interval_for("NIFTY") == "60minute"
    with SessionLocal() as s:
        assert s.get(InstrumentState, "NIFTY").live_interval == "60minute"
    r.set_interval("NIFTY", "1minute")   # unsupported -> clamped to default
    assert r._interval_for("NIFTY") == config.DEFAULT_LIVE_INTERVAL


def test_entries_blocked_prevents_open():
    r = _runner()
    with SessionLocal() as s:
        for st in s.scalars(select(InstrumentState)):
            st.entries_blocked = True
        s.commit()
    r.entry_blocks = r._load_entry_blocks()
    for _ in range(200):
        r.tick(); r.provider.advance()
    assert len(r.broker.open_positions()) == 0


def test_trailing_stop_ratchets_on_marks():
    r = _runner()
    inst = r.provider  # alias not needed; open a position via the broker directly
    from app.core.instruments import get_instrument
    nifty = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(nifty)
    q = chain.quotes[0]
    pos = r.broker.open_position(nifty, "LONG", q, "t", r.provider.now(), chain.spot)
    base_stop = pos.stop_price
    # simulate the premium climbing well past the first trail trigger
    r.broker.mark(pos, premium=q.ltp * 1.30, spot=chain.spot, now=r.provider.now())
    r._apply_trailing(pos)
    assert pos.stop_price > base_stop          # ratcheted up
    assert pos.stop_price >= pos.entry_premium  # locked into profit territory


def test_async_iterations_run():
    r = _runner()
    for _ in range(160):
        r.tick(); r.provider.advance()
    asyncio.run(_drive(r))
    assert isinstance(r.position_ticks, dict)
    assert r.broker.reconcile()["diff"] == 0.0


async def _drive(r):
    await r._risk_iteration()
    await r._signal_iteration()
