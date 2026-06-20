"""Phase 3 control plane: the bot must not auto-open a trade until the owner ARMS
it, it keeps managing/alerting open positions either way, and a KILL switch
instantly disarms and squares everything off."""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.notify.notifier import Notifier


def _runner():
    init_db(reset=True)
    return EngineRunner()


def _long_signal(r):
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0,
                        "close": 100.0, "long_exit": False, "short_exit": False}


def _open_nifty(r):
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    return r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot, r.params)


def test_disarmed_by_default_no_auto_open():
    r = _runner()
    assert r.armed is False
    _long_signal(r)
    r.process_entries()
    assert r.broker.position_for("NIFTY") is None      # signal seen, but NOT taken


def test_armed_opens():
    r = _runner()
    r.arm(True)
    assert r.armed is True
    _long_signal(r)
    r.process_entries()
    assert r.broker.position_for("NIFTY") is not None


def test_disarmed_still_exits_existing_position():
    r = _runner()
    pos = _open_nifty(r)                                # opened manually while disarmed
    r.state["NIFTY"] = {"long_exit": False, "short_exit": False}
    assert r.armed is False

    def fake(insts, positions):
        return {p.instrument_key: {"time": "t", "spot": 100.0,
                                   "option_premium": pos.stop_price * 0.9,
                                   "tradingsymbol": p.tradingsymbol} for p in positions}
    r.provider.live_snapshot = fake
    r.mark_and_exit_positions()
    assert r.broker.position_for("NIFTY") is None       # protective stop still fires when disarmed


def test_kill_squares_off_and_disarms():
    r = _runner()
    r.arm(True)
    _open_nifty(r)
    assert len(r.broker.open_positions()) == 1
    closed = r.kill()
    assert r.armed is False
    assert "NIFTY" in closed
    assert len(r.broker.open_positions()) == 0


def test_arm_kill_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    r = _runner()
    app.state.runner = r
    c = TestClient(app)
    assert c.get("/api/execution/state").json()["armed"] is False
    assert c.post("/api/execution/arm", json={"armed": True}).json()["armed"] is True
    assert r.armed is True
    _open_nifty(r)
    res = c.post("/api/execution/kill").json()
    assert res["killed"] is True and res["armed"] is False
    assert "NIFTY" in res["squared_off"]
    assert r.broker.position_for("NIFTY") is None


def test_arm_and_kill_notify():
    r = _runner()
    sent: list[str] = []
    r.notifier = Notifier(sender=lambda t: sent.append(t))
    r.arm(True)
    assert any("ARM" in m.upper() for m in sent)
    r.kill()
    assert any("KILL" in m.upper() for m in sent)
