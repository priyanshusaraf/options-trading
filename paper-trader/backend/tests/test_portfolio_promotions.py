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


_GEN_COMP = {
    "key": "gen_api_test_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}


def _seed_generated_candidate(path: str) -> int:
    """A candidate for a bot-GENERATED strategy, with its composition persisted."""
    from research.domain.models import GeneratedStrategyRecord
    from research.strategy.builder.grammar import Composition
    from research.strategy.builder.load import build_strategy
    eng = make_engine(path)
    init_research_db(eng)
    Session = make_sessionmaker(eng)
    with Session() as s:
        prog = ResearchProgram(name="Generated", thesis="")
        s.add(prog)
        s.flush()
        hyp = Hypothesis(program_id=prog.id, statement="generated has edge")
        s.add(hyp)
        s.flush()
        recipe = {"strategy": "gen_api_test_v1", "params": {}, "interval": "30minute"}
        sid = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()[:32]
        s.add(ExperimentSpec(id=sid, hypothesis_id=hyp.id,
                             recipe_json=json.dumps(recipe), git_commit="gen"))
        s.flush()
        run = ExperimentRun(spec_id=sid, status="completed", decision="propose")
        s.add(run)
        s.flush()
        strat = build_strategy(Composition.from_dict(_GEN_COMP))
        s.add(GeneratedStrategyRecord(key="gen_api_test_v1",
                                      composition_json=json.dumps(_GEN_COMP),
                                      source=strat.source))
        s.add(PromotionCandidate(
            run_id=run.id, parameterization_hash="pg",
            qualifying_universe_json=json.dumps(["GOLDM"]),
            scorecard_json=json.dumps({"best": {"instrument": "GOLDM", "dsr": 0.3},
                                       "validated": [{"instrument": "GOLDM", "dsr": 0.3,
                                                      "scorecard": {}}]}),
            status="pending"))
        s.commit()
        return run.id


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


def _set_candidate_status(path: str, candidate_id: int, status: str) -> None:
    eng = make_engine(path)
    Session = make_sessionmaker(eng)
    with Session.begin() as session:
        session.get(PromotionCandidate, candidate_id).status = status
    eng.dispose()


@pytest.fixture(autouse=True)
def _research_on(monkeypatch):
    # this file exercises the research-plane API itself; lift the freeze gate
    # (PT_RESEARCH_ENABLED, default off — see tests/test_research_flag.py)
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "research_enabled", True)


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


def test_committed_candidate_bridge_is_closed_before_research_decision(client):
    c, cid = client
    response = c.post(
        f"/api/portfolio/promotions/{cid}/deploy",
        json={"watchlist_name": "Bullion"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "PROMOTION_DECISION_REQUIRED"
    assert c.get("/api/portfolio/watchlists").json()["watchlists"] == []
    assert c.get("/api/portfolio/promotions").json()["promotions"][0]["id"] == cid


def test_candidate_bridge_preview_remains_read_only(client):
    c, cid = client
    response = c.post(
        f"/api/portfolio/promotions/{cid}/deploy",
        json={"watchlist_name": "Bullion", "dry_run": True},
    )
    assert response.status_code == 200
    assert set(response.json()["accepted"]) == {"SILVERM", "GOLDM"}
    assert c.get("/api/portfolio/watchlists").json()["watchlists"] == []


def test_deploy_unknown_promotion_returns_error(client):
    c, _ = client
    response = c.post("/api/portfolio/promotions/9999/deploy",
                      json={"watchlist_name": "X"})
    assert response.status_code == 409
    assert response.json()["code"] == "PROMOTION_NOT_PENDING"


@pytest.mark.parametrize("candidate_status", ["shadow", "approved", "rejected"])
def test_direct_id_cannot_stage_a_candidate_outside_the_pending_queue(
        client, candidate_status, monkeypatch):
    c, cid = client
    from research.config import research_db_path

    _set_candidate_status(research_db_path(), cid, candidate_status)
    response = c.post(
        f"/api/portfolio/promotions/{cid}/deploy",
        json={"watchlist_name": "Bypass"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "PROMOTION_NOT_PENDING",
        "message": "promotion is not pending human approval",
    }
    assert c.get("/api/portfolio/watchlists").json()["watchlists"] == []


@pytest.fixture
def gen_client(tmp_path, monkeypatch):
    rdb = str(tmp_path / "research.db")
    monkeypatch.setenv("PT_RESEARCH_DB_PATH", rdb)
    _seed_generated_candidate(rdb)
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    app.state.runner = EngineRunner()
    yield TestClient(app)
    from app.strategy import registry
    registry._REGISTRY.pop("gen_api_test_v1", None)


def test_generated_promotion_surfaces_composition_and_exact_explanation(gen_client):
    p = gen_client.get("/api/portfolio/promotions").json()["promotions"][0]
    assert p["generated"] is True
    assert p["composition"]["key"] == "gen_api_test_v1"
    assert "def compute(df" in p["generated_source"]
    # the explanation is composition-exact (mentions the real block math), not generic
    assert "EMA(50)" in " ".join(p["explanation"]["rules"])


def test_generated_candidate_cannot_cross_into_execution_before_decision(gen_client):
    response = gen_client.post(
        "/api/portfolio/promotions/1/deploy",
        json={"watchlist_name": "GenBullion"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "PROMOTION_DECISION_REQUIRED"
    assert gen_client.get("/api/portfolio/watchlists").json()["watchlists"] == []
