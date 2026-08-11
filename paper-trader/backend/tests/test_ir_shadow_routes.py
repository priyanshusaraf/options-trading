"""L1 Stage 1 — the observability contract.

Stage 1 adds no frontend (owner constraint 10). What it does add is the read surface a
frontend, a report or an operator would use, and the numbers Stage 1 is judged on must be
readable from it. This endpoint is read-only by construction: there is no route that can
enable, disable or otherwise steer the shadow lane — the flag is a `runtime_config` key and
goes through the existing settings route.
"""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.api.routes import router
from app.db.session import init_db
from app.engine import ir_shadow, ir_shadow_store
from app.engine.ir_shadow_metrics import ShadowMetrics
from app.db.models import LEGACY_BROKER_ACCOUNT_ID, LEGACY_OWNER_ID
from tests.legacy_money_scope import LegacyMoneyScope

ir_shadow_store = LegacyMoneyScope(
    ir_shadow_store, "record", "recent", "counts_by_reason", "prune")


class FakeRunner:
    def __init__(self):
        self.owner_id = LEGACY_OWNER_ID
        self.broker_account_id = LEGACY_BROKER_ACCOUNT_ID
        self.shadow_metrics = ShadowMetrics()
        self.params = {"ir_shadow_enabled": False}
        self.strategy_keys = {"NIFTY": "expanding_z_v4", "GOLDM": "trend_impulse_v3"}


def client() -> tuple[TestClient, FakeRunner]:
    from fastapi import FastAPI

    init_db(reset=True)
    app = FastAPI()
    app.include_router(router)
    runner = FakeRunner()
    app.state.runner = runner
    return TestClient(app), runner


def divergence(reason=ir_shadow.FLAG_DIVERGENCE, bar=None):
    now = dt.datetime(2026, 8, 4, 10, 30)
    flags = dict.fromkeys(("longEntry", "shortEntry", "longExit", "shortExit"), False)
    return ir_shadow.ShadowObservation(
        instrument_key="NIFTY", bar_time=bar or now, observed_at=now,
        authoritative_strategy_key="expanding_z_v4",
        shadow_strategy_key="ir.strategy.expanding_z_impulse",
        graph_address="sha256:abc", authoritative={**flags, "longEntry": True},
        ir=flags, warmup_state="settled", declared_warmup=302, frame_bars=400,
        frame_id="sha256:frame", frame_first_ts=now, frame_last_ts=now,
        reason=reason, detail="longEntry: authoritative=True ir=False",
        eval_seconds=0.012)


def test_the_endpoint_reports_every_number_stage_1_is_judged_on():
    api, runner = client()
    runner.shadow_metrics.observe(divergence(ir_shadow.AGREEMENT), market_open=True)
    runner.shadow_metrics.loop(iteration_seconds=1.0, shadow_seconds=0.1,
                               budget_seconds=2.5)

    body = api.get("/api/ir-shadow").json()

    metrics = body["metrics"]
    assert metrics["agreement_rate"] == 1.0
    assert "by_reason" in metrics
    assert metrics["insufficient_history_in_hours"] == 0
    assert set(metrics["eval_seconds"]) == {"count", "p50", "p95", "max"}
    assert metrics["loop"]["shadow_share_p95"] == 0.1 / 2.5


def test_the_endpoint_says_whether_the_lane_is_even_on():
    """An agreement rate means nothing without knowing whether the lane ran at all."""
    api, runner = client()
    assert api.get("/api/ir-shadow").json()["enabled"] is False
    runner.params["ir_shadow_enabled"] = True
    assert api.get("/api/ir-shadow").json()["enabled"] is True


def test_the_endpoint_names_which_instruments_are_actually_shadowed():
    """Production's default strategy has no IR mirror, so "no disagreements" is usually a
    statement about coverage rather than about agreement. The coverage must be visible."""
    api, _ = client()
    body = api.get("/api/ir-shadow").json()
    assert body["coverage"]["shadowed"] == ["NIFTY"]
    assert body["coverage"]["unmirrored"] == ["GOLDM"]
    assert body["coverage"]["pairings"] == ["expanding_z_v4"]


def test_recorded_disagreements_are_readable_with_their_full_attribution():
    api, _ = client()
    ir_shadow_store.record(divergence(), market_open=True)

    (row,) = api.get("/api/ir-shadow").json()["divergences"]

    assert row["reason"] == ir_shadow.FLAG_DIVERGENCE
    assert row["graph_address"] == "sha256:abc"
    assert row["frame_id"] == "sha256:frame"
    assert row["authoritative"]["longEntry"] is True
    assert row["ir"]["longEntry"] is False
    assert row["warmup_state"] == "settled"
    assert row["declared_warmup"] == 302
    assert row["market_open"] is True


def test_a_refusal_reads_as_an_absent_verdict_not_a_false_one():
    api, _ = client()
    refusal = divergence(ir_shadow.INSUFFICIENT_HISTORY)
    refusal = ir_shadow.ShadowObservation(**{**refusal.__dict__, "ir": None,
                                             "warmup_state": "insufficient"})
    ir_shadow_store.record(refusal, market_open=True)

    (row,) = api.get("/api/ir-shadow").json()["divergences"]
    assert row["ir"] is None
    assert row["authoritative"] is not None    # the authoritative verdict is still known
    assert row["warmup_state"] == "insufficient"


def test_the_endpoint_offers_no_way_to_steer_the_lane():
    """Constraint 8: the flag lives in `runtime_config` and moves through the settings
    route. A second control surface would be a second way to turn it on."""
    api, _ = client()
    for method in (api.post, api.put, api.delete, api.patch):
        assert method("/api/ir-shadow").status_code in (404, 405)


def test_a_rejected_pairing_is_visible_beside_the_shadowed_ones():
    """An instrument can be mirrored AND not observed — the admission contract refused it,
    or the feed contradicted admission and it was demoted. Without this those two facts read
    identically to "shadowed and agreeing"."""
    api, runner = client()
    runner.shadow_metrics.rejected("NIFTY", "NIFTY: 30minute on NSE yields about 273 bars")

    body = api.get("/api/ir-shadow").json()

    assert body["coverage"]["rejected"] == {
        "NIFTY": "NIFTY: 30minute on NSE yields about 273 bars"}
    assert body["metrics"]["rejected_pairings"] == 1
    # Still listed as shadowed — it has a mirror. The two answer different questions.
    assert body["coverage"]["shadowed"] == ["NIFTY"]
