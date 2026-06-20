"""Phase 2: the engine emits notifications on auto-open, on close, and when a
position nears its SL/TP (the owner's 'tell me when I'm near an exit' ask)."""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.notify.notifier import Notifier


def _runner_with_capture():
    init_db(reset=True)
    r = EngineRunner()
    sent: list[str] = []
    r.notifier = Notifier(sender=lambda t: sent.append(t))
    return r, sent


def _nearest_ce(r):
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    return inst, chain, q


def _stub_snapshot(r, premium):
    def fake(insts, positions):
        return {p.instrument_key: {"time": "t", "spot": 100.0,
                                   "option_premium": premium,
                                   "tradingsymbol": p.tradingsymbol}
                for p in positions}
    r.provider.live_snapshot = fake


def test_notifies_on_auto_open():
    r, sent = _runner_with_capture()
    r.armed = True                       # must be armed to auto-execute
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0,
                        "close": 100.0, "long_exit": False, "short_exit": False}
    r.process_entries()
    assert r.broker.position_for("NIFTY") is not None
    assert any("OPEN" in m for m in sent)


def test_notifies_when_nearing_stop_without_closing():
    r, sent = _runner_with_capture()
    inst, chain, q = _nearest_ce(r)
    pos = r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot, r.params)
    r.state["NIFTY"] = {"long_exit": False, "short_exit": False}
    # premium just above the stop (within the proximity zone) -> warn, don't close
    _stub_snapshot(r, premium=pos.stop_price * 1.05)
    r.mark_and_exit_positions()
    assert r.broker.position_for("NIFTY") is not None       # not closed
    assert any("STOP" in m for m in sent)                   # but warned


def test_notifies_on_stop_loss_close():
    r, sent = _runner_with_capture()
    inst, chain, q = _nearest_ce(r)
    pos = r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot, r.params)
    r.state["NIFTY"] = {"long_exit": False, "short_exit": False}
    _stub_snapshot(r, premium=pos.stop_price * 0.9)         # below the stop -> exit
    r.mark_and_exit_positions()
    assert r.broker.position_for("NIFTY") is None
    assert any("CLOSE" in m and "STOP_LOSS" in m for m in sent)
