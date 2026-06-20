"""The engine respects the adaptive router (skips entries the router rejects) and
halts new entries once today's realized loss breaches the daily cap. Both only
gate NEW entries — existing positions are still managed."""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.engine.execution_policy import OrderPlan


def _runner():
    init_db(reset=True)
    r = EngineRunner()
    r.arm(True)
    return r


def _long_signal(r):
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0,
                        "close": 100.0, "long_exit": False, "short_exit": False}


def test_engine_skips_entry_when_router_says_skip(monkeypatch):
    r = _runner()
    from app.engine import runner as rmod
    monkeypatch.setattr(rmod, "plan_order",
                        lambda *a, **k: OrderPlan("SKIP", None, "spread too wide (test)", 0.4))
    _long_signal(r)
    r.process_entries()
    assert r.broker.position_for("NIFTY") is None      # router vetoed the ugly book


def test_daily_loss_halt_blocks_new_entries():
    r = _runner()
    r.params["max_daily_loss"] = 100.0
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    now = r.provider.now()
    pos = r.broker.open_position(inst, "LONG", q, "t", now, chain.spot, r.params)
    r.broker.close_position(pos, q.ltp * 0.5, "STOP_LOSS", now, chain.spot)  # realize a loss
    assert r.broker.position_for("NIFTY") is None
    _long_signal(r)
    r.process_entries()
    assert r.broker.position_for("NIFTY") is None      # halted for the day, no re-entry
