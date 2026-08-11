"""/api/storage — the DB reached 108 MB on a 1 GB droplet with nothing in the product
ever reporting its size. Growth was only visible by SSH. This makes the cost of the
telemetry (and of the deliberate option-chain research sweep) legible in the app."""
import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.db.session import SessionLocal
from app.db.models import BrokerAccount, Organization, Trade
from app.engine.runner import EngineRunner
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _runner():
    init_db(reset=True)
    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")


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


def test_storage_counts_money_rows_only_for_the_runners_account():
    """A storage response for account.default must not disclose a second book's trades."""
    import datetime as dt
    with SessionLocal() as s:
        s.add(Organization(organization_id="other", name="Other"))
        s.add(BrokerAccount(broker_account_id="account.other", owner_id="other",
                            broker="kite", external_account_id="other", display_name="Other"))
        s.add(Trade(owner_id="other", broker_account_id="account.other", deployment_id=1,
                    instrument_key="X", direction="LONG", option_type="EQ", tradingsymbol="X",
                    exchange="NSE", segment="equity_intraday", strike=0, expiry=dt.date.today(),
                    qty=1, entry_premium=1, entry_cost=1, entry_spot=1, entry_time=dt.datetime.now(),
                    exit_premium=1, exit_charges=0, exit_spot=1, exit_time=dt.datetime.now(),
                    exit_reason="test", gross_pnl=0, charges_total=0, net_pnl=0, return_pct=0,
                    holding_minutes=1, win=False, mode="paper"))
        s.commit()
    assert client.get("/api/storage").json()["tables"][-2]["rows"] == 0
