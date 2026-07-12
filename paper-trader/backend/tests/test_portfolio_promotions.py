"""Promotions API — the read side of the approve→deploy bridge. GET surfaces the
research plane's pending PromotionCandidates (read from research.db, joined to their
spec for strategy/params + a plain-language explanation); POST .../deploy stages the
validated universe into a watchlist and records the human approval back on the
candidate. No order is ever placed and capital is never touched."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    Hypothesis,
    PromotionCandidate,
    ResearchProgram,
)


def _seed_research_db(path: str) -> int:
    eng = make_engine(path)
    init_research_db(eng)
    Session = make_sessionmaker(eng)
    with Session() as s:
        prog = ResearchProgram(name="Trend", thesis="")
        s.add(prog)
        s.flush()
        hyp = Hypothesis(program_id=prog.id, statement="EMA trend persists")
        s.add(hyp)
        s.flush()
        recipe = {"strategy": "trend_impulse_v3", "params": {"ema_length": 50},
                  "interval": "30minute"}
        sid = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()[:32]
        s.add(ExperimentSpec(id=sid, hypothesis_id=hyp.id,
                             recipe_json=json.dumps(recipe), git_commit="abc"))
        s.flush()
        run = ExperimentRun(spec_id=sid, status="completed", decision="propose")
        s.add(run)
        s.flush()
        cand = PromotionCandidate(
            run_id=run.id, parameterization_hash="p1",
            qualifying_universe_json=json.dumps(["SILVERM", "GOLDM"]),
            scorecard_json=json.dumps({
                "best": {"instrument": "SILVERM", "dsr": 0.4},
                "validated": [{"instrument": "SILVERM", "dsr": 0.4, "scorecard": {}},
                              {"instrument": "GOLDM", "dsr": 0.2, "scorecard": {}}]}),
            status="pending")
        s.add(cand)
        s.commit()
        return cand.id


@pytest.fixture
def client(tmp_path, monkeypatch):
    rdb = str(tmp_path / "research.db")
    monkeypatch.setenv("PT_RESEARCH_DB_PATH", rdb)
    cid = _seed_research_db(rdb)
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    app.state.runner = EngineRunner()
    return TestClient(app), cid


def test_promotions_lists_pending_with_explanation_and_validated_universe(client):
    c, cid = client
    res = c.get("/api/portfolio/promotions").json()
    assert len(res["promotions"]) == 1
    p = res["promotions"][0]
    assert p["id"] == cid
    assert p["strategy_key"] == "trend_impulse_v3"
    assert p["interval"] == "30minute"
    assert {v["instrument"] for v in p["validated_universe"]} == {"SILVERM", "GOLDM"}
    # the plain-language explanation travels with the candidate
    assert p["explanation"]["strategy_key"] == "trend_impulse_v3"
    assert p["explanation"]["thesis"]


def test_promotions_empty_when_no_research_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_RESEARCH_DB_PATH", str(tmp_path / "absent.db"))
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    app.state.runner = EngineRunner()
    c = TestClient(app)
    assert c.get("/api/portfolio/promotions").json()["promotions"] == []


def test_deploy_promotion_stages_watchlist_and_approves_candidate(client):
    c, cid = client
    res = c.post(f"/api/portfolio/promotions/{cid}/deploy",
                 json={"watchlist_name": "Bullion"}).json()
    assert set(res["assigned"]) == {"SILVERM", "GOLDM"}
    assert "staged" in res["note"]
    # the validated universe is now a live watchlist bound to the candidate's strategy
    wls = c.get("/api/portfolio/watchlists").json()["watchlists"]
    bullion = next(w for w in wls if w["name"] == "Bullion")
    assert set(bullion["instruments"]) == {"SILVERM", "GOLDM"}
    assert bullion["strategy_key"] == "trend_impulse_v3"
    # the candidate is recorded approved and no longer shows as pending
    assert c.get("/api/portfolio/promotions").json()["promotions"] == []


def test_deploy_unknown_promotion_returns_error(client):
    c, _ = client
    res = c.post("/api/portfolio/promotions/9999/deploy",
                 json={"watchlist_name": "X"}).json()
    assert "error" in res
