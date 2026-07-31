"""schema() must report an override EXPLICITLY, not leave the UI to infer it.

The inference `value != default` is wrong in the one case that matters: an
override stored equal to the code default shadows that default forever while
displaying as untouched. Shipping a new default then silently has no effect.
"""
import pytest

from app.core import runtime_config as rc


@pytest.fixture(autouse=True)
def no_stored_overrides(monkeypatch):
    """schema() reads the runtime_config table. These tests are about its
    SHAPE, not about DB state, so the store is stubbed empty by default and
    the tests that care patch it themselves."""
    monkeypatch.setattr(rc, "get_overrides", lambda: {})


def test_every_overridable_key_appears():
    keys = {r["key"] for r in rc.schema()}
    assert keys == set(rc.OVERRIDABLE)


def test_rows_carry_the_overridden_flag():
    for r in rc.schema():
        assert "overridden" in r, f"{r['key']} has no overridden flag"


def test_untouched_keys_are_not_marked_overridden(monkeypatch):
    monkeypatch.setattr(rc, "get_overrides", lambda: {})
    assert all(r["overridden"] is False for r in rc.schema())


def test_a_stored_override_is_marked_even_when_it_equals_the_default(monkeypatch):
    """The whole reason this flag exists."""
    key = next(iter(rc.OVERRIDABLE))
    from app.core.config import get_settings
    default = getattr(get_settings(), key)
    monkeypatch.setattr(rc, "get_overrides", lambda: {key: str(default)})

    row = next(r for r in rc.schema() if r["key"] == key)
    assert row["overridden"] is True
    # …and it is indistinguishable from the default by value alone, which is
    # exactly why inferring it was broken.
    assert str(row["value"]) == str(row["default"])


def test_a_differing_override_is_also_marked(monkeypatch):
    monkeypatch.setattr(rc, "get_overrides", lambda: {"max_open_positions": "7"})
    row = next(r for r in rc.schema() if r["key"] == "max_open_positions")
    assert row["overridden"] is True
    assert row["value"] == 7
