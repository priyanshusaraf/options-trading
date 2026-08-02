"""A registered block that the search never draws is a block that does not exist.

This is the ninth instance of this repository's defining defect (see
`tests/test_no_unconsumed_mechanisms.py` for the eighth): a mechanism built,
tested, correct, and wired to nothing. Here the wiring gap is one step subtler than
a function with no callers, which is why the existing guard could not see it —
every block in `BLOCKS` *has* a caller. `BLOCKS` is read by the emitter, the
grammar, the validator and the explainer. What a block can lack is a *draw*: if
`sample_compositions` never emits a reference to it, the nightly search will never
evaluate it, and the block is decoration.

That had already happened, twice, before this test existed:

  - The RSI family (Phase 2) was registered and never sampled, because the search
    was a fixed 3x3x2 grid of hand-written strings. Fixed 2026-08-01 by adding
    seeded sampling — and the fix's own docstring then claimed sampling "draws from
    the block registry rather than a fixed list", "which is what makes a new block
    reachable the moment it is registered."
  - **That claim was false when it was written.** `_mirror_momentum` and `_filter`
    are still hand-written string templates; they merely draw from a wider set of
    them. Measured 2026-08-02 across 200 seeds: seven of twenty-three registered
    blocks were unreachable, four of which (`atr_pct_lt`, `gap_up_pct`,
    `gap_down_pct`, `still_expanding_z`) had been dead since the day they landed.

A docstring asserting a property is not the property. This test is the mechanism
that makes the claim true, and it is the reason the claim may be written down.

**Adding a block to `BLOCKS` now fails the build until the search can draw it.**
That is the intended friction: registering is the easy half, and it is the half
that looks finished.
"""
from __future__ import annotations

import pytest

from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.search import sample_compositions

# Blocks deliberately excluded from the random draw, with the reason. Empty today.
# An entry here is a decision on the record — the point is that excluding a block
# has to be a choice someone made and justified, not an oversight nobody noticed.
NOT_SAMPLED: dict[str, str] = {}

SEEDS = 200
PER_SEED = 8


def _drawn() -> set[str]:
    names: set[str] = set()
    for seed in range(SEEDS):
        for comp in sample_compositions(PER_SEED, seed):
            names.update(r.name for r in comp.block_refs())
    return names


def test_every_registered_block_can_be_drawn_by_the_search():
    unreachable = sorted(set(BLOCKS) - _drawn() - set(NOT_SAMPLED))
    assert not unreachable, (
        f"registered but never sampled in {SEEDS} seeds: {unreachable}. "
        "The nightly will never evaluate these. Either wire them into "
        "`_mirror_trend`/`_mirror_momentum`/`_filter` in search.py, or add them to "
        "NOT_SAMPLED with a reason."
    )


def test_the_exclusion_list_only_names_real_blocks():
    """A stale exclusion silently re-hides a block that was later wired in."""
    unknown = sorted(set(NOT_SAMPLED) - set(BLOCKS))
    assert not unknown, f"NOT_SAMPLED names blocks that no longer exist: {unknown}"


def test_a_drawn_composition_is_grammar_valid_for_every_block():
    """Reachability is worthless if the draw emits a reference the grammar rejects:
    the nightly would simply raise on that seed. `Composition.from_dict` parses on
    construction, so getting here at all proves it — this asserts the coverage that
    makes that proof mean something."""
    seen = _drawn()
    assert len(seen) >= len(BLOCKS) - len(NOT_SAMPLED)


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_sampling_stays_deterministic_per_seed(seed):
    """Widening the draw is allowed to change WHAT a seed produces; it is never
    allowed to make a seed non-reproducible. A composition that cannot be
    regenerated from its seed cannot be reproduced, which is the premise the whole
    research plane rests on."""
    a = [c.key for c in sample_compositions(6, seed)]
    b = [c.key for c in sample_compositions(6, seed)]
    assert a == b
