"""The reinforcement loop: night N's plan must be a function of nights 1..N−1.

Until now the nightly re-rolled dice. It sampled compositions, evaluated them,
wrote Findings — and then the next night sampled from exactly the same
distribution, having learned nothing. Findings are free text, so nothing could
query "which block keeps dying on bullion?"; the knowledge existed as prose and
was unusable as input.

`research/knowledge.py` closes that. It counts outcomes per (block, instrument),
suppresses families with a well-powered negative record, and mutates survivors
so a working idea gets explored rather than merely re-observed.

The acceptance criterion is the roadmap's own, and it is stated as a pair
because either half alone proves nothing:

  - seed a POISONED family and watch it get suppressed,
  - seed a SURVIVOR and watch mutants of it appear.

A suppressor that suppresses everything would pass the first test alone.
"""
from __future__ import annotations

import pytest

from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import BlockEdge
from research.knowledge import (blocks_in, edge_report, mutate, record_outcome,
                                suppressed_blocks)


@pytest.fixture
def session(tmp_path):
    eng = make_engine(str(tmp_path / "research.db"))
    init_research_db(eng)
    with make_sessionmaker(eng)() as s:
        yield s


COMP = {
    "key": "gen_test",
    "longEntry": {"all": ["ema_slope_up(30, 5)", "rsi_gt(14, 55.0, 0, 2)"]},
    "shortEntry": {"all": ["ema_slope_down(30, 5)", "rsi_lt(14, 45.0, 0, 2)"]},
    "longExit": {"any": ["zscore_lt(50, 0.0)"]},
    "shortExit": {"any": ["zscore_gt(50, 0.0)"]},
}


# ── reading blocks out of a composition ─────────────────────────────────────

def test_blocks_in_extracts_every_block_family():
    assert blocks_in(COMP) == {"ema_slope_up", "ema_slope_down", "rsi_gt",
                               "rsi_lt", "zscore_lt", "zscore_gt"}


def test_blocks_in_ignores_parameters():
    """The family is the unit of knowledge — `rsi_gt(14,...)` and
    `rsi_gt(21,...)` are the same idea at different settings."""
    a = blocks_in({"longEntry": {"all": ["rsi_gt(14, 55.0, 0, 2)"]}})
    b = blocks_in({"longEntry": {"all": ["rsi_gt(21, 70.0, 3, 1)"]}})
    assert a == b == {"rsi_gt"}


def test_blocks_in_survives_junk():
    assert blocks_in({}) == set()
    assert blocks_in({"longEntry": {"all": []}}) == set()


# ── recording ───────────────────────────────────────────────────────────────

def test_recording_accumulates_per_block_and_instrument(session):
    record_outcome(session, COMP, "GOLDM", validated=False)
    record_outcome(session, COMP, "GOLDM", validated=False)
    record_outcome(session, COMP, "SILVERM", validated=True)
    row = session.get(BlockEdge, ("rsi_gt", "GOLDM"))
    assert (row.positive, row.negative) == (0, 2)
    assert session.get(BlockEdge, ("rsi_gt", "SILVERM")).positive == 1


def test_recording_is_idempotent_in_shape_not_in_count(session):
    """Two evaluations are two data points; the table must not collapse them."""
    for _ in range(5):
        record_outcome(session, COMP, "GOLDM", validated=False)
    assert session.get(BlockEdge, ("rsi_gt", "GOLDM")).negative == 5


# ── suppression, with a power floor ─────────────────────────────────────────

# A composition sharing COMP's non-RSI families, used to give those families a
# MIXED record so they do not qualify for suppression. Without this the whole
# vocabulary is equally awful and which families the cap keeps is an arbitrary
# tie-break — these tests would then be asserting the tie-break, not the rule.
SIBLING = {
    "key": "gen_sibling",
    "longEntry": {"all": ["ema_slope_up(30, 5)"]},
    "shortEntry": {"all": ["ema_slope_down(30, 5)"]},
    "longExit": {"any": ["zscore_lt(50, 0.0)"]},
    "shortExit": {"any": ["zscore_gt(50, 0.0)"]},
}


def _make_rsi_the_clear_loser(session, instrument="GOLDM"):
    """RSI fails everywhere; its siblings win about half the time."""
    for _ in range(12):
        record_outcome(session, COMP, instrument, validated=False)
    for _ in range(14):
        record_outcome(session, SIBLING, instrument, validated=True)


def test_a_well_powered_loser_is_suppressed(session):
    _make_rsi_the_clear_loser(session)
    assert "rsi_gt" in suppressed_blocks(session, "GOLDM")


def test_one_bad_night_does_not_suppress_a_family(session):
    """The failure mode this guards: suppressing on n=1 would let a single noisy
    evaluation permanently delete an idea from the search space."""
    record_outcome(session, COMP, "GOLDM", validated=False)
    assert suppressed_blocks(session, "GOLDM") == set()


def test_suppression_is_per_instrument_not_global(session):
    """'Which idea works WHERE' — a family that dies on gold must stay available
    on crude, or the map is just a global blocklist."""
    _make_rsi_the_clear_loser(session)
    assert "rsi_gt" in suppressed_blocks(session, "GOLDM")
    assert suppressed_blocks(session, "CRUDEOIL") == set()


def test_a_family_that_sometimes_works_is_not_suppressed(session):
    for _ in range(8):
        record_outcome(session, COMP, "GOLDM", validated=False)
    for _ in range(4):
        record_outcome(session, COMP, "GOLDM", validated=True)
    assert "rsi_gt" not in suppressed_blocks(session, "GOLDM")


def test_suppression_can_be_escaped_by_later_evidence(session):
    """Never permanently banned. A suppressed family that later validates must
    come back, mirroring how retest_priority decays UPWARD."""
    _make_rsi_the_clear_loser(session)
    assert "rsi_gt" in suppressed_blocks(session, "GOLDM")
    for _ in range(20):
        record_outcome(session, COMP, "GOLDM", validated=True)
    assert "rsi_gt" not in suppressed_blocks(session, "GOLDM")


# ── mutation ────────────────────────────────────────────────────────────────

def test_mutation_produces_a_different_but_valid_composition():
    from research.strategy.builder.grammar import Composition
    m = mutate(COMP, seed=1)
    assert m["key"] != COMP["key"]
    Composition.from_dict(m)          # raises if ungrammatical


def test_mutation_is_deterministic_per_seed():
    assert mutate(COMP, seed=5) == mutate(COMP, seed=5)


def test_different_seeds_give_different_mutants():
    keys = {mutate(COMP, seed=s)["key"] for s in range(12)}
    assert len(keys) > 1


def test_a_mutant_keeps_most_of_its_parent():
    """A 'mutation' that rewrites everything is just a new random draw, and the
    survivor's information is lost."""
    m = mutate(COMP, seed=3)
    shared = blocks_in(m) & blocks_in(COMP)
    assert len(shared) >= len(blocks_in(COMP)) - 2


# ── the acceptance criterion ────────────────────────────────────────────────

def test_a_poisoned_family_is_suppressed_and_a_survivor_is_mutated(session):
    """ACCEPTANCE (roadmap Workstream A, Phase 3): night N's plan is provably a
    function of nights 1..N−1's Findings.

    Both halves matter. A suppressor that suppressed everything would pass the
    first assertion on its own and have destroyed the search."""
    poisoned = {"key": "gen_bad", "longEntry": {"all": ["roc_gt(10, 0.0)"]},
                "shortEntry": {"all": ["roc_lt(10, 0.0)"]},
                "longExit": {"any": ["zscore_lt(50, 0.0)"]},
                "shortExit": {"any": ["zscore_gt(50, 0.0)"]}}
    for _ in range(15):
        record_outcome(session, poisoned, "GOLDM", validated=False)
    for _ in range(15):
        record_outcome(session, COMP, "GOLDM", validated=True)

    suppressed = suppressed_blocks(session, "GOLDM")
    assert "roc_gt" in suppressed, "the poisoned family survived"
    assert "rsi_gt" not in suppressed, "the survivor was suppressed too"

    mutant = mutate(COMP, seed=2)
    assert blocks_in(mutant) & blocks_in(COMP), "the mutant lost its parent entirely"


def test_the_edge_report_is_legible(session):
    """It gets rendered into the research report — a human has to be able to read
    'which idea works where' off it."""
    for _ in range(6):
        record_outcome(session, COMP, "GOLDM", validated=True)
    for _ in range(6):
        record_outcome(session, COMP, "SILVERM", validated=False)
    text = edge_report(session)
    assert "rsi_gt" in text
    assert "GOLDM" in text and "SILVERM" in text


def test_the_edge_report_is_empty_when_nothing_is_known(session):
    assert edge_report(session) == ""


# ── the exploration floor ───────────────────────────────────────────────────

def test_suppression_can_never_take_the_whole_vocabulary(session):
    """The failure that actually happened: on a universe where nothing works yet
    EVERY family accumulates a losing record. Unbounded, suppression took all
    four trend families at once — and since every composition structurally needs
    a trend block, the sampler could draw nothing and the nightly stopped
    exploring while reporting success."""
    everything = {"key": "gen_all",
                  "longEntry": {"all": ["ema_slope_up(30, 5)", "price_above_ema(50)",
                                        "rsi_gt(14, 55.0, 0, 2)", "roc_gt(10, 0.0)"]},
                  "shortEntry": {"all": ["ema_slope_down(30, 5)", "price_below_ema(50)"]},
                  "longExit": {"any": ["zscore_lt(50, 0.0)"]},
                  "shortExit": {"any": ["zscore_gt(50, 0.0)"]}}
    for _ in range(20):
        record_outcome(session, everything, "GOLDM", validated=False)
    families = blocks_in(everything)
    suppressed = suppressed_blocks(session, "GOLDM")
    assert suppressed, "nothing was suppressed despite a uniformly awful record"
    assert len(suppressed) < len(families), \
        "suppression consumed the entire vocabulary — the search would collapse"


def test_the_worst_offenders_are_the_ones_kept_suppressed(session):
    """When the cap bites, it must keep the strongest negative records and let
    the marginal ones back in — not an arbitrary subset."""
    bad = {"key": "b", "longEntry": {"all": ["roc_gt(10, 0.0)"]},
           "shortEntry": {"all": ["roc_lt(10, 0.0)"]},
           "longExit": {"any": ["zscore_lt(50, 0.0)"]},
           "shortExit": {"any": ["zscore_gt(50, 0.0)"]}}
    mixed = {"key": "m", "longEntry": {"all": ["rsi_gt(14, 55.0, 0, 2)"]},
             "shortEntry": {"all": ["rsi_lt(14, 45.0, 0, 2)"]},
             "longExit": {"any": ["zscore_lt(50, 0.0)"]},
             "shortExit": {"any": ["zscore_gt(50, 0.0)"]}}
    for _ in range(20):
        record_outcome(session, bad, "GOLDM", validated=False)
    for _ in range(9):
        record_outcome(session, mixed, "GOLDM", validated=False)
    record_outcome(session, mixed, "GOLDM", validated=True)
    sup = suppressed_blocks(session, "GOLDM")
    assert "roc_gt" in sup


def test_the_sampler_explores_anyway_rather_than_returning_nothing():
    """Suppression is a preference, never a cage. A night that searches nothing
    learns nothing, and the loop could never escape the state that silenced it."""
    from research.strategy.builder.blocks import BLOCKS
    from research.strategy.builder.search import sample_compositions
    everything = set(BLOCKS)
    out = sample_compositions(limit=4, seed=1, suppressed=everything)
    assert out, "the sampler returned nothing when all families were suppressed"
