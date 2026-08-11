"""Phase 4: nothing reaches a human on backtest evidence alone.

A backtest is retrospective by construction — every parameter was chosen with the
whole series visible, and Phase 0's deflation and PBO can only DISCOUNT that, not
remove it. The one thing they cannot simulate is a session the strategy has never
seen. So a validated candidate now runs on a research-side paper book for N
sessions before anyone is asked to look at it, and arrives with an
expected-versus-realised comparison attached.

The acceptance criterion is a NEGATIVE one, which is the only kind that means
anything here: a candidate with too little shadow evidence must be ABSENT from
the approval queue.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import (ExperimentRun, ExperimentSpec, Hypothesis,
                                    PromotionCandidate, ResearchProgram)
from research.shadow import (MIN_SHADOW_SESSIONS, STATUS_PENDING, STATUS_SHADOW,
                             approval_queue, comparison, is_ready_for_approval,
                             promote_if_ready, record_session, shadow_record)

OWNER_ID = "test-owner"


@pytest.fixture
def session(tmp_path):
    eng = make_engine(str(tmp_path / "research.db"))
    init_research_db(eng)
    with make_sessionmaker(eng)() as s:
        yield s


def _candidate(session, status=STATUS_SHADOW):
    """Build the real Program -> Hypothesis -> Spec -> Run chain.

    research.db enforces foreign keys, so a candidate cannot dangle off an
    invented run_id — which is correct, and worth keeping rather than working
    around: a promotion with no traceable run is exactly what the immutable-spec
    lineage exists to prevent.
    """
    prog = ResearchProgram(owner_id=OWNER_ID, name="p", thesis="t")
    session.add(prog); session.flush()
    hyp = Hypothesis(owner_id=OWNER_ID, program_id=prog.id, statement="h")
    session.add(hyp); session.flush()
    spec = ExperimentSpec(owner_id=OWNER_ID, id=f"spec{hyp.id}", hypothesis_id=hyp.id)
    session.add(spec); session.flush()
    run = ExperimentRun(owner_id=OWNER_ID, spec_id=spec.id, status="completed")
    session.add(run); session.flush()
    c = PromotionCandidate(owner_id=OWNER_ID, run_id=run.id, parameterization_hash="h", status=status,
                           scorecard_json=json.dumps({"best": {"dsr": 0.9}}))
    session.add(c)
    session.flush()
    return c


def _run_sessions(session, cid, n, *, trades=6, wins=4, pnl=120.0, instrument="GOLDM"):
    base = dt.date(2026, 8, 3)
    for i in range(n):
        record_session(session, cid, session_date=base + dt.timedelta(days=i),
                       instrument_key=instrument, trades=trades, wins=wins, net_pnl=pnl)


# ── the gate ────────────────────────────────────────────────────────────────

def test_a_fresh_candidate_is_not_in_the_approval_queue(session):
    """ACCEPTANCE: validated is not the same as ready to ask a human."""
    _candidate(session)
    assert approval_queue(session) == []


def test_too_few_sessions_is_not_ready(session):
    c = _candidate(session)
    _run_sessions(session, c.id, MIN_SHADOW_SESSIONS - 1)
    ready, reason = is_ready_for_approval(session, c.id)
    assert ready is False
    assert "shadow session" in reason


def test_enough_sessions_promotes_into_the_queue(session):
    c = _candidate(session)
    _run_sessions(session, c.id, MIN_SHADOW_SESSIONS)
    assert promote_if_ready(session, c.id, {"hit_rate": 0.6, "avg_per_trade": 20.0})
    assert [x.id for x in approval_queue(session)] == [c.id]
    assert session.get(PromotionCandidate, c.id).status == STATUS_PENDING


def test_a_shadow_run_with_no_trades_is_not_evidence(session):
    """Five sessions in which nothing traded tested nothing at all."""
    c = _candidate(session)
    _run_sessions(session, c.id, MIN_SHADOW_SESSIONS, trades=0, wins=0, pnl=0.0)
    ready, reason = is_ready_for_approval(session, c.id)
    assert ready is False
    assert "no trades" in reason


def test_sessions_count_distinct_DATES_not_rows(session):
    """A candidate run on six instruments for ONE day has seen one session of
    unseen data, not six. Counting rows would let a wide universe manufacture the
    appearance of persistence in a single afternoon."""
    c = _candidate(session)
    for inst in ("GOLDM", "SILVERM", "CRUDEOIL", "COPPERM", "NATURALGAS", "BANKNIFTY"):
        record_session(session, c.id, session_date=dt.date(2026, 8, 3),
                       instrument_key=inst, trades=5, wins=3, net_pnl=50.0)
    assert shadow_record(session, c.id).sessions == 1
    assert is_ready_for_approval(session, c.id)[0] is False


def test_replaying_a_day_does_not_inflate_the_record(session):
    """Idempotent per (candidate, date, instrument) — a re-run must not make the
    evidence look better powered than it is."""
    c = _candidate(session)
    for _ in range(4):
        record_session(session, c.id, session_date=dt.date(2026, 8, 3),
                       instrument_key="GOLDM", trades=5, wins=3, net_pnl=50.0)
    rec = shadow_record(session, c.id)
    assert rec.sessions == 1 and rec.trades == 5


def test_promotion_is_not_repeatable(session):
    c = _candidate(session)
    _run_sessions(session, c.id, MIN_SHADOW_SESSIONS)
    assert promote_if_ready(session, c.id, {}) is True
    assert promote_if_ready(session, c.id, {}) is False


# ── the comparison a human actually reads ───────────────────────────────────

def test_the_comparison_puts_expected_next_to_realised(session):
    c = _candidate(session)
    _run_sessions(session, c.id, MIN_SHADOW_SESSIONS, trades=10, wins=5, pnl=100.0)
    cmp_ = comparison({"hit_rate": 0.7, "avg_per_trade": 30.0}, session, c.id)
    assert cmp_["expected_hit_rate"] == 0.7
    assert cmp_["realised_hit_rate"] == pytest.approx(0.5)
    assert cmp_["hit_rate_delta"] == pytest.approx(-0.2)
    assert cmp_["realised_avg_per_trade"] == pytest.approx(10.0)


def test_a_thin_shadow_sample_is_flagged_underpowered(session):
    """So nobody reads a 3-session agreement as confirmation."""
    c = _candidate(session)
    _run_sessions(session, c.id, 3, trades=2, wins=1, pnl=10.0)
    assert comparison({}, session, c.id)["underpowered"] is True


def test_the_comparison_is_attached_to_the_candidate_on_promotion(session):
    c = _candidate(session)
    _run_sessions(session, c.id, MIN_SHADOW_SESSIONS)
    promote_if_ready(session, c.id, {"hit_rate": 0.6, "avg_per_trade": 20.0})
    payload = json.loads(session.get(PromotionCandidate, c.id).scorecard_json)
    assert "shadow" in payload
    assert payload["shadow"]["sessions"] == MIN_SHADOW_SESSIONS
    assert payload["best"]["dsr"] == 0.9, "the original scorecard must survive"


# ── fail closed ─────────────────────────────────────────────────────────────

def test_an_unknown_candidate_is_never_promoted(session):
    assert promote_if_ready(session, 9999, {}) is False


def test_an_already_pending_candidate_is_not_re_promoted(session):
    c = _candidate(session, status=STATUS_PENDING)
    _run_sessions(session, c.id, MIN_SHADOW_SESSIONS)
    assert promote_if_ready(session, c.id, {}) is False


def test_the_orchestrator_queues_candidates_into_SHADOW_not_pending():
    """The gate only binds if candidates are born in shadow. Creating them as
    `pending` would leave this whole module decorative — the same
    present-but-unconsumed failure as var_sr and the block registry."""
    import inspect
    from research.orchestrator import run as run_mod
    src = inspect.getsource(run_mod.run_experiment)
    assert "status=STATUS_SHADOW" in src
    assert 'status="pending"' not in src
