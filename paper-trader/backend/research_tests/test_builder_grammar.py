"""The declarative Composition grammar + strict block-reference parsing. A ref is a
string like `"ema_slope_up(50,5)"`; parsing accepts ONLY a call to a whitelisted block
name with bounded numeric args — anything else (unknown name, wrong arity, a non-numeric
arg, an injection attempt) is rejected before it can reach the emitter."""
import pytest

from research.strategy.builder.grammar import (
    BlockRef,
    Composition,
    parse_ref,
    ref_to_str,
)


def test_parse_valid_ref():
    ref = parse_ref("ema_slope_up(50, 5)")
    assert ref == BlockRef("ema_slope_up", (50, 5))


def test_parse_allows_negative_threshold():
    ref = parse_ref("zscore_lt(50, -1.5)")
    assert ref.name == "zscore_lt" and ref.args == (50, -1.5)


def test_parse_rejects_unknown_block():
    with pytest.raises(ValueError):
        parse_ref("os_system(1)")


def test_parse_rejects_injection_attempt():
    with pytest.raises(ValueError):
        parse_ref("__import__('os')")


def test_parse_rejects_wrong_arity():
    with pytest.raises(ValueError):
        parse_ref("ema_slope_up(50)")            # needs 2 args


def test_parse_rejects_non_numeric_arg():
    with pytest.raises(ValueError):
        parse_ref("ema_slope_up(df, 5)")         # Name arg, not a constant


def test_parse_rejects_out_of_bounds_length():
    with pytest.raises(ValueError):
        parse_ref("price_above_ema(1)")          # length must be >= 2


def test_ref_to_str_roundtrips():
    for text in ("ema_slope_up(50, 5)", "zscore_cross_up(50, 1.0)", "zscore_lt(50, -1.5)"):
        assert parse_ref(ref_to_str(parse_ref(text))) == parse_ref(text)


_SPEC = {
    "key": "gen_trend_z_v1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}


def test_composition_roundtrips_dict():
    comp = Composition.from_dict(_SPEC)
    assert comp.key == "gen_trend_z_v1"
    assert comp.long_entry.op == "all"
    assert {r.name for r in comp.long_entry.refs} == {"ema_slope_up", "zscore_cross_up"}
    # to_dict -> from_dict is stable
    assert Composition.from_dict(comp.to_dict()) == comp


def test_composition_rejects_empty_clause():
    bad = dict(_SPEC, longEntry={"all": []})
    with pytest.raises(ValueError):
        Composition.from_dict(bad)


def test_max_warmup_is_the_longest_block_window():
    comp = Composition.from_dict(_SPEC)
    # longest block is ema_slope_up(50,5) -> 55; zscore(50) -> 51
    assert comp.max_warmup() == 55
