"""#2: a manual close (cockpit) or an external/reconciled exit auto-blocks same-day
re-entry for that symbol, so the live signal can't immediately re-open what the owner
exited (the PAYTM/IREDA thrash from 2026-06-30).

The manual-close route is async + grabs the engine lock; driving it through Starlette's
TestClient portal deadlocked intermittently inside the full suite, so we await the route
coroutine directly with a tiny fake Request instead — same code path, no portal."""
import asyncio
from types import SimpleNamespace

from app.api.routes import close_position
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def _open_nifty(r):
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot, r.params)


def _fake_request(r):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runner=r)))


def test_manual_close_blocks_reentry():
    r = _runner()
    _open_nifty(r)
    assert "NIFTY" not in r.entry_blocks
    res = asyncio.run(close_position("NIFTY", _fake_request(r)))
    assert res.get("closed") is True
    assert res.get("entries_blocked") is True
    assert "NIFTY" in r.entry_blocks            # re-entry now blocked for the day


def test_reconciled_external_exit_blocks_reentry():
    r = _runner()
    assert "NIFTY" not in r.entry_blocks
    r.broker.reconcile_orphans = lambda now: ["NIFTY"]   # simulate an external exit booked
    r._maybe_reconcile_orphans()
    assert "NIFTY" in r.entry_blocks


def test_reconcile_no_orphans_leaves_blocks_empty():
    r = _runner()
    r.broker.reconcile_orphans = lambda now: []
    r._maybe_reconcile_orphans()
    assert r.entry_blocks == set()
