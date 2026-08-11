"""/api/event-risk — the cockpit's answer to "why isn't the bot trading this?".

An invisible safety rule is indistinguishable from a broken bot. This endpoint is the
only thing that makes a sit-out explainable before it happens.
"""
import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _runner():
    init_db(reset=True)
    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")


def _get(day):
    resp = client.get(f"/api/event-risk?day={day}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_thursday_lists_sensex_and_the_natgas_window():
    body = _get("2026-08-06")
    by_key = {i["key"]: i for i in body["instruments"]}
    assert "SENSEX" in by_key
    assert by_key["SENSEX"]["blackouts"][0]["all_day"] is True

    gas = by_key["NATURALGAS"]["blackouts"][0]
    assert gas["all_day"] is False
    assert gas["from"].endswith("19:30:00")
    assert gas["to"].endswith("20:01:00")
    assert gas["flatten_before"] is True


def test_wednesday_lists_crude_and_banknifty_not_sensex():
    body = _get("2026-08-05")
    keys = {i["key"] for i in body["instruments"]}
    assert {"CRUDEOIL", "BANKNIFTY"} <= keys
    assert "SENSEX" not in keys


def test_a_quiet_day_lists_nothing():
    body = _get("2026-08-07")          # a Friday
    assert body["instruments"] == []


def test_every_rule_is_published_so_the_ui_can_explain_itself():
    body = _get("2026-08-07")
    kinds = {r["kind"] for r in body["rules"]}
    assert {"us_report", "weekday", "pre_expiry", "earnings"} == kinds
    assert all(r["label"] for r in body["rules"])


def test_calendar_health_is_reported_not_hidden():
    """A silently stale earnings calendar would mean stocks trade through results with
    the UI implying they're protected."""
    body = _get("2026-08-06")
    assert "earnings_calendar" in body
    assert set(body["earnings_calendar"]) == {"known", "of_stocks"}


def test_bad_day_is_rejected_not_silently_defaulted():
    assert client.get("/api/event-risk?day=notadate").status_code == 400
