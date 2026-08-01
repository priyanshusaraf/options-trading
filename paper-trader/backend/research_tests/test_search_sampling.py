"""Seeded random sampling — so a widened vocabulary is actually reachable.

`enumerate_compositions` walks a fixed 3x3x2 grid of hand-picked block strings.
Adding blocks to `blocks.BLOCKS` therefore widened the *whitelist* and changed
the search not at all: Phase 2's RSI family, volume and gap blocks were emitted
into the registry and never sampled. Same shape as the `var_sr` bug — present,
correct, unreachable.

Sampling must be DETERMINISTIC per seed. A composition that cannot be
regenerated from its seed cannot be reproduced, and reproducibility is the whole
premise of the research plane (immutable specs, content-hashed datasets).

It must also stay inside the grammar: every sampled composition is built through
`Composition.from_dict`, so anything ungrammatical raises at construction rather
than reaching the sandbox.
"""
from __future__ import annotations

import pytest

from research.strategy.builder.grammar import Composition
from research.strategy.builder.search import enumerate_compositions, sample_compositions


def test_sampling_is_deterministic_per_seed():
    a = sample_compositions(limit=8, seed=42)
    b = sample_compositions(limit=8, seed=42)
    assert [c.key for c in a] == [c.key for c in b]
    assert [c.to_dict() for c in a] == [c.to_dict() for c in b]


def test_different_seeds_explore_different_ideas():
    a = {c.key for c in sample_compositions(limit=12, seed=1)}
    b = {c.key for c in sample_compositions(limit=12, seed=2)}
    assert a != b


def test_every_sampled_composition_is_grammar_valid():
    """Built through Composition.from_dict, so an ungrammatical draw raises here
    rather than reaching the sandbox."""
    for c in sample_compositions(limit=25, seed=7):
        assert isinstance(c, Composition)
        assert Composition.from_dict(c.to_dict()).key == c.key


def test_keys_are_unique_within_a_draw():
    """Duplicate keys would collide in research_generated_strategy and one
    composition would silently overwrite another's record."""
    keys = [c.key for c in sample_compositions(limit=30, seed=3)]
    assert len(keys) == len(set(keys))


def test_the_sampler_reaches_the_phase_2_vocabulary():
    """The point of the exercise. Over a decent draw the new blocks must actually
    appear — otherwise widening BLOCKS was cosmetic."""
    seen = set()
    for seed in range(12):
        for c in sample_compositions(limit=12, seed=seed):
            seen.update(str(c.to_dict()).split("("))
    blob = " ".join(seen)
    assert "rsi_gt" in blob or "rsi_lt" in blob, "the RSI family is never sampled"


def test_formula_variants_are_actually_varied():
    """Source/smoothing codes must move across draws, or every RSI sampled is the
    same RSI and the 'family' is one member."""
    codes = set()
    for seed in range(15):
        for c in sample_compositions(limit=10, seed=seed):
            for clause in c.to_dict().values():
                if isinstance(clause, dict):
                    for ref in list(clause.values())[0]:
                        if ref.startswith("rsi_"):
                            codes.add(ref)
    assert len(codes) >= 3, f"RSI variants collapsed to {codes}"


def test_a_zero_limit_returns_nothing():
    assert sample_compositions(limit=0, seed=1) == []


def test_the_deterministic_enumerator_still_exists():
    """The fixed grid stays as a stable baseline — a reproducible control the
    sampler can be compared against."""
    assert len(enumerate_compositions(limit=5)) == 5
