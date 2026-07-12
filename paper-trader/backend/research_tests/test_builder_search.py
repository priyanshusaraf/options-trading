"""The generator: a bounded, deterministic enumeration of economically-sensible
compositions (a trend gate + a momentum trigger, mirrored for shorts, with sensible
exits). The load-bearing guarantee is that EVERY composition it emits compiles to a
valid, sandboxed, runnable strategy — the bot can only ever produce safe code."""
from research.strategy.builder.grammar import Composition
from research.strategy.builder.load import build_strategy
from research.strategy.builder.search import enumerate_compositions


def test_enumeration_is_bounded_and_uniquely_keyed():
    comps = enumerate_compositions(limit=10)
    assert 0 < len(comps) <= 10
    keys = [c.key for c in comps]
    assert len(keys) == len(set(keys))            # no duplicate keys
    assert all(isinstance(c, Composition) for c in comps)


def test_enumeration_is_deterministic():
    a = [c.key for c in enumerate_compositions(limit=12)]
    b = [c.key for c in enumerate_compositions(limit=12)]
    assert a == b


def test_every_generated_composition_compiles_to_a_safe_runnable_strategy():
    # this is the safety contract: nothing the generator emits can fail validation
    for comp in enumerate_compositions(limit=64):
        strat = build_strategy(comp)               # emits + validates + sandboxes
        assert strat.key == comp.key
        assert "def compute(df" in strat.source


def test_short_side_mirrors_the_long_side():
    for comp in enumerate_compositions(limit=24):
        long_names = {r.name for r in comp.long_entry.refs}
        short_names = {r.name for r in comp.short_entry.refs}
        # a long that uses an *_up / *_gt / price_above block has a *_down / *_lt / below mirror
        assert len(long_names) == len(short_names)
        assert "up" not in " ".join(short_names)   # short side never references an 'up' block
