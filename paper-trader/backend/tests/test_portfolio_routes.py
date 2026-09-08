"""Portfolio API: deploy (preview + commit), watchlists/archive reads, and lifecycle
status control. Deploy is staged config only — the endpoint never arms or trades."""
import pytest
from unittest.mock import patch

from app.core import paper_authority
from app.core.config import get_settings
from app.db.models import LEGACY_DEPLOYMENT_ID
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient
from tests.admitted_entry import persist_admitted_entry


@pytest.fixture(autouse=True)
def _research_on(monkeypatch):
    # this file exercises the research-plane API itself; lift the freeze gate
    # (PT_RESEARCH_ENABLED, default off — see tests/test_research_flag.py)
    monkeypatch.setattr(get_settings(), "research_enabled", True)


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    with SessionLocal() as session:
        admission = persist_admitted_entry(session)
        rows = [paper_authority.stage(
            session,
            project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key=instrument_key,
            interval="30minute", owner_id="owner", broker_account_id="account.default",
        ) for instrument_key in ("GOLDM", "SILVERM")]
        session.commit()
        decision = {
            "project_id": "test.admission.4c1029697ee358715d3a14a2",
            "graph_identifier": "test.strategy.expanding_z_impulse", "graph_version": 1,
            "content_address": admission["graph_address"],
            "admission_address": admission["admission_address"], "decision": "approved",
        }
        with patch.object(paper_authority, "verified_decision", return_value=decision):
            for row in rows:
                paper_authority.activate(
                    session, row.id, revision=row.revision, owner_id="owner",
                    broker_account_id="account.default")
        session.commit()
    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    app.state._test_admission = admission
    return TestClient(app)


def _body(**values):
    admission = app.state._test_admission
    return {"strategy_key": admission["strategy_key"],
            "admission_address": admission["admission_address"],
            "broker_account_id": "account.default", **values}


def test_deploy_dry_run_previews_without_writing():
    c = _client()
    body = _body(watchlist_name="Bullion",
                 proposals=[{"instrument_key": "GOLDM", "score": 0.8}], dry_run=True)
    res = c.post("/api/portfolio/deploy", json=body).json()
    assert res["dry_run"] is True and res["accepted"] == ["GOLDM"]
    assert c.get("/api/portfolio/watchlists").json()["watchlists"] == []   # nothing written


def test_deploy_commits_and_shows_in_watchlists_and_archive():
    c = _client()
    body = _body(watchlist_name="Bullion",
                 proposals=[{"instrument_key": "GOLDM", "score": 0.8},
                            {"instrument_key": "SILVERM", "score": 0.7}], source="builtin")
    res = c.post("/api/portfolio/deploy", json=body).json()
    assert set(res["assigned"]) == {"GOLDM", "SILVERM"}
    assert "staged" in res["note"]
    wls = c.get("/api/portfolio/watchlists").json()["watchlists"]
    assert wls[0]["name"] == "Bullion"
    assert set(wls[0]["instruments"]) == {"GOLDM", "SILVERM"}
    arch = c.get("/api/portfolio/archive").json()["strategies"]
    assert any(a["strategy_key"] == app.state._test_admission["strategy_key"]
               and a["status"] == "running" for a in arch)


def test_deploy_blocks_an_incumbent():
    c = _client()
    c.post("/api/portfolio/deploy", json=_body(
        watchlist_name="A", proposals=[{"instrument_key": "SILVERM", "score": 0.9}]))
    res = c.post("/api/portfolio/deploy", json=_body(
        watchlist_name="B", proposals=[{"instrument_key": "SILVERM", "score": 0.99},
                                         {"instrument_key": "GOLDM", "score": 0.5}])).json()
    assert res["assigned"] == ["GOLDM"]
    assert any(r["instrument"] == "SILVERM" and r["reason"] == "incumbent"
               for r in res["rejected"])


def test_watchlist_status_can_be_paused():
    c = _client()
    c.post("/api/portfolio/deploy", json=_body(
        watchlist_name="Bullion", proposals=[{"instrument_key": "GOLDM", "score": 0.8}]))
    res = c.post("/api/portfolio/watchlists/Bullion/status", json={"status": "paused"}).json()
    assert res["status"] == "paused"


def test_archive_lifecycle_transitions_and_rejects_illegal():
    c = _client()
    c.post("/api/portfolio/deploy", json=_body(
        watchlist_name="Bullion", proposals=[{"instrument_key": "GOLDM", "score": 0.8}]))
    key = app.state._test_admission["strategy_key"]
    ok = c.post(f"/api/portfolio/archive/{key}/status",
                json={"status": "probation"}).json()
    assert ok["status"] == "probation"
    bad = c.post(f"/api/portfolio/archive/{key}/status",
                 json={"status": "candidate"}).json()                        # probation->candidate illegal
    assert "error" in bad
