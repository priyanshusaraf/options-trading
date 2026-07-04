"""/api/signals carries signal counts + overtrade suggestion; flag toggle endpoint."""
from fastapi.testclient import TestClient

from app.db.models import SignalEvent
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def test_signals_carry_counts_and_suggestion_and_flag():
    c, r = _client()
    c.post("/api/settings", json={"key": "overtrade_today_threshold", "value": "2"})
    now = r.provider.now()
    with SessionLocal() as s:
        for _ in range(3):
            s.add(SignalEvent(time=now, instrument_key="GOLDM", signal="LONG_ENTRY"))
        s.commit()
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert rows["GOLDM"]["signals_today"] >= 3
    assert rows["GOLDM"]["overtrade_suggested"] is True
    assert rows["GOLDM"]["overtrade_flag"] is False
    assert c.post("/api/instruments/GOLDM/overtrade", json={"flag": True}).json()["overtrade_flag"] is True
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert rows["GOLDM"]["overtrade_flag"] is True


def test_overtrade_unknown_instrument_rejected():
    c, _ = _client()
    assert "error" in c.post("/api/instruments/NOPE/overtrade", json={"flag": True}).json()
