"""Strategy definitions: primitive taxonomy TAGS (semantic, seeds the future builder)
+ a bounded, constrained parameter search space. No executable slot machinery in v1 —
the strategy stays an opaque compute(); only its searchable surface is declared.
"""
from research.strategy.spec import ParamSpec, definition, grid, is_valid, param_space


def test_definition_carries_primitive_tags():
    d = definition("trend_impulse_v3")
    assert "Trend" in d.primitives


def test_param_space_marks_optimizable_params():
    assert param_space("trend_impulse_v3")["ema_length"].optimizable


def test_grid_is_cartesian_product_of_values():
    sp = {"a": ParamSpec("a", "int", 50, values=[30, 50]),
          "b": ParamSpec("b", "float", 1.0, values=[0.75, 1.0, 1.5])}
    g = grid(sp)
    assert len(g) == 6
    assert {"a": 30, "b": 0.75} in g


def test_grid_skips_non_optimizable_and_valueless():
    sp = {"a": ParamSpec("a", "int", 50, values=[30, 50]),
          "c": ParamSpec("c", "int", 5, values=None)}
    assert all(set(x) == {"a"} for x in grid(sp))


def test_default_strategy_space_is_small_and_bounded():
    assert 1 <= len(grid(param_space("trend_impulse_v3"))) <= 64


def test_is_valid_enforces_v4_cross_field_constraint():
    assert is_valid("expanding_z_v4", {"entry_pct": 65, "exit_pct": 35}) is True
    assert is_valid("expanding_z_v4", {"entry_pct": 30, "exit_pct": 40}) is False


def test_unknown_strategy_has_empty_space_and_is_valid():
    assert grid(param_space("nope")) == [{}]
    assert is_valid("nope", {"anything": 1}) is True
