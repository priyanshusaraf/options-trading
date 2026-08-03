"""The nightly plan — what the scientist actually works on tonight.

`nightly._load_plan()` returned `[]`. Every guardrail, every gate, every
statistic fixed in Phase 0 sat behind a scheduler that scheduled nothing, so the
cron one-shot has always been a well-tested no-op.

Two rules the plan must obey, and both are safety properties rather than
features:

1. **Eligibility is a hard filter, not a preference.** An instrument committed to
   a live watchlist is off-limits for strategy development (owner's directive) —
   we do not re-litigate something already earning. The commodity sandbox is the
   permanent exception. A plan that leaked a committed instrument would have the
   research plane quietly optimising against live positions.
2. **`retest_priority` finally gets a consumer.** It has been written on every
   run since M0 and read by nothing, which is why a killed idea was never
   actually revisited. Ordering by it is what closes that loop.
"""
from __future__ import annotations

import datetime as dt

import pytest

from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import Hypothesis, ResearchProgram
from research.plan import build_plan


@pytest.fixture
def session(tmp_path):
    eng = make_engine(str(tmp_path / "research.db"))
    init_research_db(eng)
    with make_sessionmaker(eng)() as s:
        yield s


def _hyp(session, statement, priority, status="open"):
    prog = session.query(ResearchProgram).first()
    if prog is None:
        prog = ResearchProgram(name="test-program", thesis="t")
        session.add(prog)
        session.flush()
    h = Hypothesis(program_id=prog.id, statement=statement,
                   status=status, retest_priority=priority)
    session.add(h)
    session.flush()
    return h


# ── eligibility is a hard filter ────────────────────────────────────────────

def test_a_committed_instrument_never_reaches_the_plan(session):
    _hyp(session, "h1", 1.0)
    plan = build_plan(session, eligible={"GOLDM", "SILVERM"}, strategy_key="s")
    assert plan
    for item in plan:
        assert "RELIANCE" not in item["instruments"]
        assert set(item["instruments"]) <= {"GOLDM", "SILVERM"}


def test_an_empty_eligible_universe_produces_no_plan(session):
    """Nothing to research is a safe no-op, not an error and not a fallback to
    'everything' — a fallback here would target live instruments."""
    _hyp(session, "h1", 1.0)
    assert build_plan(session, eligible=set(), strategy_key="s") == []


# ── retest_priority gets its consumer ───────────────────────────────────────

def test_hypotheses_are_ordered_by_retest_priority(session):
    _hyp(session, "low", 0.1)
    _hyp(session, "high", 9.0)
    _hyp(session, "mid", 1.0)
    plan = build_plan(session, eligible={"GOLDM"}, strategy_key="s", max_experiments=3)
    assert [p["hypothesis"] for p in plan] == ["high", "mid", "low"]


def test_only_open_hypotheses_are_scheduled(session):
    _hyp(session, "open-one", 1.0, status="open")
    _hyp(session, "already-supported", 9.0, status="supported")
    _hyp(session, "rejected", 8.0, status="rejected")
    plan = build_plan(session, eligible={"GOLDM"}, strategy_key="s")
    assert [p["hypothesis"] for p in plan] == ["open-one"]


def test_the_plan_is_bounded(session):
    """A nightly run has a budget. Unbounded, one busy night starves every
    following one and the loop stops being nightly."""
    for i in range(20):
        _hyp(session, f"h{i}", float(i))
    plan = build_plan(session, eligible={"GOLDM"}, strategy_key="s", max_experiments=3)
    assert len(plan) == 3


def test_instruments_per_experiment_is_bounded(session):
    _hyp(session, "h", 1.0)
    eligible = {f"INST{i}" for i in range(50)}
    plan = build_plan(session, eligible=eligible, strategy_key="s",
                      instruments_per_experiment=6)
    assert len(plan[0]["instruments"]) == 6


def test_instrument_selection_is_deterministic(session):
    """Two runs of the same night must schedule the same work, or a result is not
    reproducible from the plan that produced it."""
    _hyp(session, "h", 1.0)
    eligible = {f"INST{i}" for i in range(50)}
    a = build_plan(session, eligible=eligible, strategy_key="s")
    b = build_plan(session, eligible=eligible, strategy_key="s")
    assert a[0]["instruments"] == b[0]["instruments"]


# ── cold start ──────────────────────────────────────────────────────────────

def test_a_database_with_no_hypotheses_seeds_one(session):
    """First ever run. Returning [] would mean the loop can never start itself —
    it would wait forever for a hypothesis only a human could write."""
    plan = build_plan(session, eligible={"GOLDM", "SILVERM"}, strategy_key="s")
    assert len(plan) == 1
    assert plan[0]["instruments"]
    assert plan[0]["hypothesis"]


def test_the_cold_start_seed_prefers_the_research_sandbox(session):
    """The sandbox is permanently research-eligible, so seeding there cannot
    collide with anything the owner has committed."""
    plan = build_plan(session, eligible={"GOLDM", "SILVERM", "SOMEEQUITY"},
                      strategy_key="s", instruments_per_experiment=2)
    assert set(plan[0]["instruments"]) <= {"GOLDM", "SILVERM"}


# ── shape the orchestrator expects ──────────────────────────────────────────

def test_plan_items_carry_every_key_run_nightly_reads(session):
    _hyp(session, "h", 1.0)
    item = build_plan(session, eligible={"GOLDM"}, strategy_key="trend_impulse_v3")[0]
    for k in ("program", "hypothesis", "strategy_key", "instruments", "interval"):
        assert k in item, f"run_nightly reads {k!r}"
    assert item["strategy_key"] == "trend_impulse_v3"


def test_the_plan_asks_for_the_optimizing_path(session):
    """PBO and var_sr deflation only exist on the optimize path — a plan that ran
    single-pass validation would silently skip everything Phase 0 built."""
    _hyp(session, "h", 1.0)
    assert build_plan(session, eligible={"GOLDM"}, strategy_key="s")[0]["optimize_search"] is True


# ── the cron one-shot actually loads a plan now ─────────────────────────────

def test_nightly_load_plan_is_wired_to_the_builder():
    """The whole point of this phase: `_load_plan` returned [] from M0 until
    2026-08-01, so every guardrail and gate sat behind a scheduler that
    scheduled nothing."""
    import inspect
    from research import nightly
    src = inspect.getsource(nightly._load_plan)
    assert "build_plan" in src
    assert "eligible_for_research" in src
    assert "return []" not in src


def test_nightly_warns_when_it_cannot_read_what_is_committed():
    """A missing snapshot fails PERMISSIVE (everything eligible), which is the
    unsafe direction — 'nothing is committed' and 'I could not read what is
    committed' look identical downstream. It must at least say so."""
    import inspect
    from research import nightly
    src = inspect.getsource(nightly._load_plan)
    assert "WARNING" in src and "LIVE" in src


def test_the_freeze_flag_still_gates_the_whole_run():
    """Phase 1 is shadow mode: reports + research.db only. The flag must still be
    the thing that decides whether any of this runs at all."""
    import inspect
    from research import nightly
    src = inspect.getsource(nightly.main)
    assert "research_enabled" in src
    assert "enforce(" in src


# ── generation: the loop must EXPLORE, not re-measure one idea ──────────────

def test_nightly_runs_generated_compositions_too():
    """Running only the handwritten strategy every night is not research, it is
    monitoring. Generation is what makes this a search."""
    import inspect
    from research import nightly
    assert "run_generated" in inspect.getsource(nightly._run_generation)
    assert "_run_generation" in inspect.getsource(nightly._run_enabled_operation)


def test_generation_reuses_the_plan_universe():
    """Generation and the handwritten baseline must be evaluated on the SAME
    instruments, or a difference in results could just be a difference in what
    they were run on."""
    import inspect
    src = __import__("research.nightly", fromlist=["x"])
    body = inspect.getsource(src._run_generation)
    assert 'plan[0]["instruments"]' in body
    assert 'plan[0]["interval"]' in body


def test_generation_can_be_switched_off():
    """It is the expensive half — each composition is a full pipeline pass over
    every instrument. A limit of 0 must leave a plain baseline run."""
    from research.config import nightly_generate_limit
    assert nightly_generate_limit({"PT_RESEARCH_GENERATE_LIMIT": "0"}) == 0
    assert nightly_generate_limit({}) > 0


def test_a_bad_generate_limit_falls_back_rather_than_crashing_the_cron():
    from research.config import DEFAULT_GENERATE_LIMIT, nightly_generate_limit
    assert nightly_generate_limit({"PT_RESEARCH_GENERATE_LIMIT": "banana"}) == \
        DEFAULT_GENERATE_LIMIT
    assert nightly_generate_limit({"PT_RESEARCH_GENERATE_LIMIT": "-5"}) == 0


def test_the_nightly_test_harness_never_writes_reports_into_the_repo():
    """Regression guard for a self-inflicted deploy outage.

    `test_nightly` runs the cron one-shot as a subprocess with cwd = backend/.
    While `_load_plan()` returned [] that wrote nothing. The moment the plan
    became real (2026-08-01) it started dropping report_*.md into the working
    tree — and `deploy.sh` refuses a dirty tree with NO override, so a passing
    test suite would have blocked every deploy. It failed a real deploy before
    it was caught."""
    import inspect
    from research_tests import test_nightly
    src = inspect.getsource(test_nightly._run)
    assert "PT_RESEARCH_REPORT_DIR" in src, \
        "the nightly harness must redirect reports away from the repo"
