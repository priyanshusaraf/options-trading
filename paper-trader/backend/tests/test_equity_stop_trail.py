"""#18 WIRING: when the lockstep band ratchets an intraday stop, the runner must push
the new stop to the exchange backstop (the resting SL-M for live) — otherwise the
server-side stop stays at the loose entry level while the bot's own stop tightens.
The broker-level SL-M re-price is covered in test_live_broker.py; this proves
_apply_lockstep actually calls it when (and only when) the stop moves."""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner_with_long_equity():
    init_db(reset=True)
    r = EngineRunner()
    inst = get_instrument("NIFTY")
    pos = r.broker.open_equity_position(inst, "LONG", 100.0, 500, "NSE_INTRADAY",
                                        "t", r.provider.now(), params={})
    # pin the worked-example geometry: ₹10k margin, band SL 99 / TP 102.
    pos.entry_premium, pos.qty = 100.0, 500
    pos.entry_charges, pos.entry_cost = 0.0, 10000.0
    pos.stop_price, pos.target_price = 99.0, 102.0
    calls = []
    r.broker.update_stop_protection = lambda p, lp: calls.append(p.stop_price)
    return r, pos, calls


def test_lockstep_ratchet_syncs_the_exchange_stop():
    r, pos, calls = _runner_with_long_equity()
    pos.last_premium = 102.0            # +₹1000 = 5 steps → stop ratchets 99 → 101
    r._apply_lockstep(pos)
    assert pos.stop_price == 101.0      # the software stop tightened
    assert calls == [101.0]             # ...and was pushed to the exchange backstop


def test_lockstep_flat_does_not_touch_the_exchange_stop():
    r, pos, calls = _runner_with_long_equity()
    pos.last_premium = 100.0            # no profit → no ratchet → no exchange churn
    r._apply_lockstep(pos)
    assert pos.stop_price == 99.0
    assert calls == []
