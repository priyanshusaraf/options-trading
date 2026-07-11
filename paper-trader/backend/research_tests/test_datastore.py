"""HistoricalDataStore — reproducibility is anchored here. A Dataset is a frozen,
content-hashed view of candles an experiment binds to; the hash changes iff the
underlying candles change (so a Kite backfill can't be silently reused).
"""
from research.data.store import StaticDataSource, content_hash, materialize


def test_content_hash_is_stable(candles_factory):
    c = candles_factory(100)
    assert content_hash(c) == content_hash(c)


def test_content_hash_changes_when_candles_change(candles_factory):
    a = candles_factory(100)
    b = candles_factory(100)
    b[-1].close += 1.0
    assert content_hash(a) != content_hash(b)


def test_materialize_builds_frozen_dataset(fake_inst, candles_factory):
    c = candles_factory(120)
    source = StaticDataSource({(fake_inst.key, "day"): c})
    ds = materialize(source, fake_inst, "day")
    assert ds.instrument_key == fake_inst.key
    assert ds.interval == "day"
    assert ds.bar_count == 120
    assert ds.content_hash == content_hash(c)
    assert ds.candles is c


def test_materialize_empty_source_is_safe(fake_inst):
    ds = materialize(StaticDataSource({}), fake_inst, "day")
    assert ds.bar_count == 0
    assert ds.candles == []
