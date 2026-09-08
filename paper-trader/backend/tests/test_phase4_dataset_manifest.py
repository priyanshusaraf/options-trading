import pytest

from app.backtest.dataset_store import DatasetManifest


def _address(char):
    return "sha256:" + char * 64


def _manifest(**changes):
    values = dict(owner_id="owner-a", dataset_address="a" * 64,
                  provider_dataset_version="provider-dataset/1", instruments=("NSE:ABC",),
                  fields=("CLOSE",), range_start="2026-01-01T00:00:00Z",
                  range_end="2026-01-02T00:00:00Z", segment_digests=(_address("1"),),
                  instrument_master_address=_address("2"), rulebook_snapshot_address=_address("3"),
                  adjustment_policy_address=_address("4"), roll_policy_address=_address("5"),
                  missing_data_policy_address=_address("6"), alignment_policy_address=_address("7"),
                  resampling_policy_address=_address("8"), timezone="Asia/Kolkata",
                  collection_algorithm_version="collect/1", import_algorithm_version="import/1")
    values.update(changes)
    return DatasetManifest(**values)


def test_manifest_is_immutable_owner_scoped_and_correction_sensitive():
    first = _manifest()
    assert first == _manifest()
    assert hash(first) == hash(_manifest())
    assert first != _manifest(owner_id="owner-b")
    assert first != object()
    assert len({first, _manifest(), _manifest(owner_id="owner-b")}) == 2
    assert first.address() == _manifest().address()
    assert first.address() != _manifest(segment_digests=(_address("9"),)).address()
    assert first.address() != _manifest(owner_id="owner-b").address()


def test_manifest_refuses_incomplete_or_secret_like_identity():
    with pytest.raises(ValueError):
        _manifest(instruments=())
    with pytest.raises(ValueError):
        _manifest(segment_digests=("provider-token-123",))
    with pytest.raises(ValueError):
        _manifest(range_start="2026-01-03T00:00:00Z")
    with pytest.raises(ValueError):
        _manifest(timezone="Not/A_Zone")
    with pytest.raises(ValueError):
        _manifest(instruments=(object(),))
    with pytest.raises(ValueError):
        _manifest(segment_digests=())
