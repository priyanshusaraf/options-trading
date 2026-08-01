"""/api/storage — the DB reached 108 MB on a 1 GB droplet with nothing in the product
ever reporting its size. Growth was only visible by SSH. This makes the cost of the
telemetry (and of the deliberate option-chain research sweep) legible in the app."""
import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _runner():
    init_db(reset=True)
    app.state.runner = EngineRunner()


def test_reports_size_and_what_is_growing():
    b = client.get("/api/storage").json()
    assert b["size_mb"] >= 0
    names = {t["name"] for t in b["tables"]}
    assert {"option_data", "signal_events", "equity_snapshots", "trades"} <= names


def test_marks_which_tables_retention_will_and_will_not_touch():
    """The money record must be visibly exempt — someone reading this screen has to be
    able to tell that pruning cannot eat their trade history."""
    b = client.get("/api/storage").json()
    by = {t["name"]: t for t in b["tables"]}
    assert by["trades"]["pruned"] is False
    assert by["order_journal"]["pruned"] is False
    assert by["option_data"]["pruned"] is True


def test_publishes_the_active_retention_policy():
    b = client.get("/api/storage").json()
    r = b["retention"]
    assert r["enabled"] is True
    assert r["option_data_days"] == 90
    assert r["equity_full_days"] == 7
    assert "last_run" in r
