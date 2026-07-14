"""Fix F (2026-07-14): the 15-min option-chain research sweep must NOT hold the shared
engine lock. On 2026-07-13 `risk_loop_stalled` fired 24× — every sweep held `self._lock`
across ~30s of blocking Kite fetches, and the risk loop needs that same lock to mark
positions and fire SL/TP, so open positions went UNMANAGED for 30s+ every 15 min.

`persist_chain` uses its own SessionLocal and the sweep never touches the shared engine
session, so it needs no lock at all — it now runs off the lock (same sweep, same data,
same cadence; owner chose to leave the sweep itself as-is)."""
import asyncio

from app.db.session import init_db
from app.engine.runner import EngineRunner


def test_option_sweep_runs_off_the_engine_lock():
    init_db(reset=True)
    r = EngineRunner()
    r.params["option_cache_enabled"] = True
    r._next_cache_sweep_epoch = 0.0          # force the sweep to run this iteration
    seen = {}

    def spy(now=None):
        seen["locked"] = r._lock.locked()    # is the shared engine lock held right now?
        return 0

    r.cache_option_chains = spy
    asyncio.run(r._signal_iteration())
    assert seen.get("locked") is False       # sweep ran WITHOUT the risk-loop-blocking lock


def test_signal_iteration_blocking_no_longer_runs_the_sweep():
    # the lock-held body must not include the sweep (that's what starved the risk loop)
    init_db(reset=True)
    r = EngineRunner()
    r.params["option_cache_enabled"] = True
    r._next_cache_sweep_epoch = 0.0
    calls = {"n": 0}
    r.cache_option_chains = lambda now=None: calls.__setitem__("n", calls["n"] + 1) or 0
    r._signal_iteration_blocking()           # the under-lock body, called directly
    assert calls["n"] == 0                    # sweep is NOT part of the locked body
