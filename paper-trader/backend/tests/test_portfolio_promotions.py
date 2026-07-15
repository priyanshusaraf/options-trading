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


def test_deploying_a_generated_candidate_persists_it_for_the_engine(gen_client):
    from app.core.generated_strategies import register_all
    from app.db.session import SessionLocal
    from app.strategy.registry import get_strategy

    res = gen_client.post("/api/portfolio/promotions/1/deploy",
                          json={"watchlist_name": "GenBullion"}).json()
    assert res["generated"] is True and res["assigned"] == ["GOLDM"]
    # the composition was copied into the execution store; on the next startup the engine
    # reconstructs it and the gen_* key resolves to the REAL generated strategy
    with SessionLocal() as s:
        assert register_all(s) >= 1
    assert get_strategy("gen_api_test_v1").key == "gen_api_test_v1"
