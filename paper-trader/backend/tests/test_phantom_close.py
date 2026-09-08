"""E4 — a manual close that the broker REFUSED must not be reported as success.

The route discarded `broker.close_position`'s return value and unconditionally logged
MANUAL CLOSE, blocked same-day re-entry, nulled the WS display state and answered
`{"closed": true}`. LiveBroker returns None on real failure paths (ownership guard,
SL-M-cancel abort, account re-check), so with real money the cockpit said "closed"
while the position was still open at the exchange — and the owner lost the display
state they needed to act on it.
"""
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app
from app.core import paper_authority
from app.db.models import LEGACY_DEPLOYMENT_ID
from tests.admitted_entry import persist_admitted_entry


def _client():
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    admission = persist_admitted_entry(r.broker.s)
    with r._session() as session:
        row = paper_authority.stage(
            session, project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY", interval="30minute",
            owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    from unittest.mock import patch
    with r._session() as session, patch.object(
            paper_authority, "verified_decision",
            return_value={"project_id": "test.admission.4c1029697ee358715d3a14a2",
                          "graph_identifier": "test.strategy.expanding_z_impulse",
                          "graph_version": 1, "content_address": admission["graph_address"],
                          "admission_address": admission["admission_address"],
                          "decision": "approved"}):
        paper_authority.activate(session, row.id, revision=row.revision,
                                 owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    r.refresh_paper_authority()
    app.state.runner = r
    r.arm(True)
    return TestClient(app), r


def _open(c):
    op = c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}).json()
    assert op.get("opened") is True, op


def test_refused_close_is_reported_as_a_failure_not_a_success():
    c, r = _client()
    _open(c)
    r.broker.close_position = lambda *a, **k: None      # broker refuses the close

    res = c.post("/api/positions/NIFTY/close").json()

    assert res.get("closed") is not True, f"phantom close reported as success: {res}"
    assert "error" in res, f"failure must be surfaced to the cockpit: {res}"


def test_refused_close_leaves_the_position_visible_and_unblocked():
    """The owner must still be able to see and retry the position they failed to close."""
    c, r = _client()
    _open(c)
    r.state.setdefault("NIFTY", {})["position"] = {"tradingsymbol": "X"}
    r.broker.close_position = lambda *a, **k: None

    c.post("/api/positions/NIFTY/close")

    assert r.broker.position_for("NIFTY") is not None      # still open, as it truly is
    assert r.state["NIFTY"]["position"] is not None, (
        "display state was nulled for a position that never closed")
    assert "NIFTY" not in r.entry_blocks, (
        "a failed close must not block same-day re-entry")


def test_a_real_close_still_succeeds():
    """Guard against over-correcting: the happy path must be untouched."""
    c, r = _client()
    _open(c)

    res = c.post("/api/positions/NIFTY/close").json()

    assert res.get("closed") is True, res
    assert r.broker.position_for("NIFTY") is None
    assert "NIFTY" in r.entry_blocks
