"""Phase 1: per-position SL/TP — the owner can set the stop/target on any open
position, and an owner-set target survives a reinforcement (the stop still
ratchets)."""
import datetime as dt

from fastapi.testclient import TestClient

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def _open(c):
    return c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}).json()


def test_set_position_sltp_absolute():
    c, r = _client()
    assert _open(c).get("opened") is True
    res = c.post("/api/positions/NIFTY/sltp",
                 json={"stop_price": 100.0, "target_price": 900.0}).json()
    assert res.get("ok") is True
    pos = r.broker.position_for("NIFTY")
    assert pos.stop_price == 100.0 and pos.target_price == 900.0


def test_set_position_sltp_by_pct():
    c, r = _client()
    _open(c)
    pos = r.broker.position_for("NIFTY")
    entry = pos.entry_premium
    res = c.post("/api/positions/NIFTY/sltp",
                 json={"stop_pct": 0.30, "target_pct": 0.50}).json()
    assert res.get("ok") is True
    pos = r.broker.position_for("NIFTY")
    assert abs(pos.stop_price - entry * 0.70) < 1e-6
    assert abs(pos.target_price - entry * 1.50) < 1e-6


def test_set_position_sltp_rejects_inverted():
    c, r = _client()
    _open(c)
    res = c.post("/api/positions/NIFTY/sltp",
                 json={"stop_price": 900.0, "target_price": 100.0}).json()
    assert "error" in res


def test_set_position_sltp_no_position():
    c, r = _client()
    res = c.post("/api/positions/NIFTY/sltp", json={"stop_price": 1.0, "target_price": 2.0}).json()
    assert "error" in res


def test_manual_target_survives_reinforcement():
    """An owner-set target is not auto-extended by a reinforcement; the stop still
    ratchets into profit."""
    init_db(reset=True)
    r = EngineRunner()
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    pos = r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot)
    pos.manual_target = True
    pos.target_price = q.ltp * 1.40
    pinned_target = pos.target_price
    base_stop = pos.stop_price
    r.broker.commit()
    # profitable mark -> a reinforcement
    r.broker.mark(pos, premium=q.ltp * 1.25, spot=chain.spot, now=r.provider.now())
    r.broker.commit()
    r.broker.reinforce_position(pos, r.params, r.provider.now())
    pos = r.broker.position_for("NIFTY")
    assert pos.target_price == pinned_target     # owner target untouched
    assert pos.stop_price > base_stop            # stop still ratcheted
