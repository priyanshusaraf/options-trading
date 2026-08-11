"""What the scientist works on tonight.

`nightly._load_plan()` returned `[]` from M0 until 2026-08-01. Every guardrail,
gate and statistic in this package sat behind a scheduler that scheduled nothing,
so the cron one-shot was a well-tested no-op — the laboratory was built and the
experiment list was empty.

Two rules govern this module, and both are safety properties rather than features:

**Eligibility is a hard filter.** An instrument committed to a live watchlist is
off-limits for strategy development (owner's directive, 2026-07): we do not
re-litigate something that is already earning. The commodity sandbox
(`universe.ALWAYS_ALLOWED`) is the permanent exception so there is always
somewhere to try ideas. There is deliberately NO fallback to "everything" when
the eligible set is empty — a fallback there would point the research plane at
live positions, which is the one thing this whole package is isolated to prevent.

**`retest_priority` finally gets a consumer.** It has been written on every run
since M0 (`orchestrator/run.py:285`) and read by nothing, which is why a killed
idea was never actually revisited despite the decay-upward machinery existing to
ensure it would be. Ordering the plan by it is what closes that loop.

Sector seeding is NOT implemented, deliberately. The roadmap asks to seed from
the sector edge map ("bullion, capital-markets, PSU-financials first"), but no
sector metadata exists on `Instrument` and no map exists as data — it lives only
as prose in a roadmap paragraph. Inventing classifications here would be
fabricating the very input the ordering claims to use. The cold-start seed
therefore prefers the commodity sandbox (which IS the bullion set) and the rest
waits for real sector data.
"""
from __future__ import annotations

from research.domain.models import Hypothesis, ResearchProgram
from research.universe import ALWAYS_ALLOWED

# One night's budget. Unbounded, a single busy night starves every following one
# and the loop stops being nightly.
DEFAULT_MAX_EXPERIMENTS = 3
DEFAULT_INSTRUMENTS_PER_EXPERIMENT = 6

COLD_START_PROGRAM = "Autonomous nightly research"
COLD_START_HYPOTHESIS = (
    "the default strategy has exploitable edge on the research sandbox")


def _pick_instruments(eligible: set, limit: int) -> list:
    """Deterministic, sandbox-first selection.

    Sorted rather than arbitrary set order on purpose: two runs of the same night
    must schedule the same work, or a result cannot be reproduced from the plan
    that produced it.
    """
    sandbox = sorted(k for k in eligible if k in ALWAYS_ALLOWED)
    rest = sorted(k for k in eligible if k not in ALWAYS_ALLOWED)
    return (sandbox + rest)[:limit]


def build_plan(session, *, owner_id: str, eligible: set, strategy_key: str,
               interval: str = "day", days: int = 2000,
               max_experiments: int = DEFAULT_MAX_EXPERIMENTS,
               instruments_per_experiment: int = DEFAULT_INSTRUMENTS_PER_EXPERIMENT,
               ) -> list:
    """Tonight's experiments, highest `retest_priority` first.

    Returns items in the shape `orchestrator.run_nightly` consumes. An empty
    eligible universe yields an empty plan — a safe no-op, never a fallback.
    """
    instruments = _pick_instruments(set(eligible), instruments_per_experiment)
    if not instruments:
        return []

    open_hyps = (session.query(Hypothesis)
                 .filter(Hypothesis.owner_id == owner_id, Hypothesis.status == "open")
                 .order_by(Hypothesis.retest_priority.desc(), Hypothesis.id.asc())
                 .limit(max_experiments)
                 .all())

    if not open_hyps:
        # Cold start. Returning [] here would mean the loop can never start
        # itself — it would wait forever for a hypothesis only a human could
        # write, which is precisely the "autonomous research plane that never
        # ran" state this phase exists to end.
        return [_item(COLD_START_PROGRAM, COLD_START_HYPOTHESIS,
                      strategy_key, instruments, interval, days)]

    out = []
    for h in open_hyps:
        prog = (session.query(ResearchProgram)
                .filter_by(owner_id=owner_id, id=h.program_id).one_or_none())
        out.append(_item(prog.name if prog else COLD_START_PROGRAM, h.statement,
                         strategy_key, instruments, interval, days))
    return out


def _item(program: str, hypothesis: str, strategy_key: str,
          instruments: list, interval: str, days: int) -> dict:
    return {
        "program": program,
        "hypothesis": hypothesis,
        "strategy_key": strategy_key,
        "instruments": instruments,
        "interval": interval,
        "days": days,
        # The optimize path is where var_sr deflation and the PBO gate live. A
        # plan that ran single-pass validation would silently skip everything
        # Phase 0 built, and promote on an undeflated score.
        "optimize_search": True,
    }
