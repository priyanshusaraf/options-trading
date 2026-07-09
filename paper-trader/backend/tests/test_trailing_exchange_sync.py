"""Options mirror of test_equity_stop_trail.py's self-heal wiring: _apply_trailing
must check for a missing exchange-side backstop every tick, not only when the
premium ratchet actually moves the stop — otherwise a position whose initial GTT
placement failed (and that never ratchets, e.g. stays flat/underwater) never gets
the backstop retried (the 2026-07-08 LODHA class of failure, on the equity side)."""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner_with_long_option():
    init_db(reset=True)
    r = EngineRunner()
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    pos = r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot)
    return r, pos


def test_apply_trailing_self_heals_a_missing_backstop_even_when_flat():
    r, pos = _runner_with_long_option()
    update_calls, ensure_calls = [], []
    r.broker.update_stop_protection = lambda p, lp: update_calls.append(p.stop_price)
    r.broker.ensure_stop_protection = lambda p, lp: ensure_calls.append(p.stop_price)
    pos.last_premium = pos.entry_premium   # flat -> no ratchet
    r._apply_trailing(pos)
    assert update_calls == []              # no ratchet -> the ratchet path is untouched
    assert ensure_calls == [pos.stop_price]  # but the self-heal check ran anyway
