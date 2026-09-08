"""#14 order-failure circuit breaker: repeated LIVE order failures must trip a
self-DISARM, not an infinite retry-with-alerts loop.

The failure class is systemic (expired/unauthorized token, IP not whitelisted,
margin exhausted, banned symbol): every order the bot sends dies the same way,
and each fresh signal fires another real order attempt. After
`order_failure_disarm_count` CONSECUTIVE failures the runner disarms itself and
alerts; the owner re-arms deliberately after fixing the cause (re-arm resets the
streak). Wiring tests per the #15 lesson."""
import datetime as dt

from app.core.logging import log
from app.core.market_hours import ist_epoch
from app.db.session import init_db
from app.db.models import LEGACY_DEPLOYMENT_ID
from app.core import paper_authority
from app.engine.live_broker import LiveBroker
from app.engine.runner import EngineRunner
from tests.admitted_entry import persist_admitted_entry


def _armed_runner(streak: int, threshold: int = 3, key="NIFTY"):
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.enabled = {key}
    r.products[key] = "equity_intraday"
    r.params = {**r.params, "intraday_enabled": True, "intraday_block_weekday": -1,
                "order_failure_disarm_count": threshold}
    r.armed = True
    r.broker.order_fail_streak = streak
    admission = persist_admitted_entry(r.broker.s)
    with r._session() as session:
        row = paper_authority.stage(
            session, project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key=key, interval="30minute",
            owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    from unittest.mock import patch
    with r._session() as session:
        decision = {"project_id": "test.admission.4c1029697ee358715d3a14a2",
                    "graph_identifier": "test.strategy.expanding_z_impulse", "graph_version": 1,
                    "content_address": admission["graph_address"],
                    "admission_address": admission["admission_address"], "decision": "approved"}
        with patch.object(paper_authority, "verified_decision", return_value=decision):
            paper_authority.activate(session, row.id, revision=row.revision,
                                     owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    r.refresh_paper_authority()
    bar = dt.datetime(2026, 7, 3, 10, 45)                     # completes 11:00 — fresh
    r.publish_signal(
        key, r._binding_for(key), {"signal": "LONG_ENTRY", "z": 2.5, "slope": 1.0, "close": 100.0,
                                   "time": ist_epoch(bar)})
    r.provider.now = lambda: dt.datetime(2026, 7, 3, 11, 1)   # Friday, mid-session
    return r, key


def _open_intraday(r):
    return [p for p in r.broker.open_positions() if p.segment == "equity_intraday"]


def test_streak_at_threshold_disarms_and_blocks_the_entry():
    r, key = _armed_runner(streak=3)
    r.process_entries()
    assert r.armed is False
    assert _open_intraday(r) == []
    assert "ORDER_CB_DISARM" in [e.get("event") for e in log.recent(80)]


def test_streak_below_threshold_stays_armed_and_enters():
    r, key = _armed_runner(streak=2)
    r.process_entries()
    assert r.armed is True
    assert _open_intraday(r) != []


def test_breaker_disabled_when_count_zero():
    r, key = _armed_runner(streak=99, threshold=0)
    r.process_entries()
    assert r.armed is True
    assert _open_intraday(r) != []


def test_rearm_resets_the_streak():
    r, key = _armed_runner(streak=5)
    r.process_entries()
    assert r.armed is False
    r.arm(True)
    assert getattr(r.broker, "order_fail_streak", 0) == 0


# ── the LiveBroker side: the streak counts CONSECUTIVE failures, any fill resets ──
class _Res:
    def __init__(self, status, filled):
        self.status, self.filled_qty = status, filled
        self.order_id, self.avg_price, self.reason = "OID", 0.0, ""


def test_live_broker_streak_counts_and_resets():
    lb = LiveBroker.__new__(LiveBroker)      # counter logic only — no broker session
    lb.order_fail_streak = 0
    lb._note_order_outcome(0)                # zero fill = failure
    lb._note_order_outcome(0)
    assert lb.order_fail_streak == 2
    lb._note_order_outcome(75)               # any real fill resets
    assert lb.order_fail_streak == 0
