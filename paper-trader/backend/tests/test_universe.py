"""The dynamic universe: the curated seed is trimmed (LEAD/ZINC/DHANIYA gone),
seed instruments all have options, and the homepage set is a subset."""
from app.core.instruments import (
    SEED_INSTRUMENTS,
    all_instruments,
    home_instruments,
)


def test_trim_removed_illiquid_names():
    keys = {i.key for i in all_instruments()}
    assert {"LEAD", "ZINC", "DHANIYA"} & keys == set()
    assert len(SEED_INSTRUMENTS) == 8


def test_seed_instruments_have_options():
    assert all(i.has_options for i in SEED_INSTRUMENTS.values())


def test_priorities_are_unique_and_dense():
    pris = sorted(i.priority for i in SEED_INSTRUMENTS.values())
    assert pris == list(range(1, 9))  # 1..8, no gaps


def test_home_is_subset_of_universe():
    home = {i.key for i in home_instruments()}
    assert home and home <= {i.key for i in all_instruments()}
    assert "NIFTY" in home
