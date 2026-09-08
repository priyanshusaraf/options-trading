"""A fresh checkout restores sealed inputs and rejects altered or unsafe bundles."""
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from tests.indicator_assurance_fixtures import restore_assurance_inputs


def _bundle(tmp_path, *, name='.agent/runs/fixture/input.json', data=b'{"expected":3}'):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    archive = bundle / 'sealed-inputs.tar.gz'
    with tarfile.open(archive, 'w:gz') as output:
        item = tarfile.TarInfo(name)
        item.size = len(data)
        output.addfile(item, io.BytesIO(data))
    index = {'schema': 'indicator-assurance-fixtures/1',
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'files': [{'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}],
        'output_directories': ['.agent/runs/fixture/output']}
    (bundle / 'manifest.json').write_text(json.dumps(index))
    return bundle, index


def test_fresh_checkout_restores_exact_sealed_inputs_and_replay_preserves_them(tmp_path):
    root = tmp_path / 'checkout'
    restore_assurance_inputs(root)
    manifest = json.loads((Path(__file__).parent / 'fixtures/indicator_accuracy/manifest.json').read_text())
    for item in manifest['files']:
        assert hashlib.sha256((root / item['path']).read_bytes()).hexdigest() == item['sha256']
    restore_assurance_inputs(root)
    assert all((root / name).is_dir() for name in manifest['output_directories'])


@pytest.mark.parametrize('changed', ['archive_sha256', 'file_sha256', 'size', 'extra_member'])
def test_altered_bundle_refuses_before_restoring_input(tmp_path, changed):
    bundle, index = _bundle(tmp_path)
    if changed == 'archive_sha256':
        index['archive_sha256'] = '0' * 64
    elif changed == 'extra_member':
        index['files'] = []
    else:
        index['files'][0]['sha256' if changed == 'file_sha256' else 'size'] = '0' * 64 if changed == 'file_sha256' else 999
    (bundle / 'manifest.json').write_text(json.dumps(index))
    root = tmp_path / 'checkout'
    with pytest.raises(ValueError):
        restore_assurance_inputs(root, bundle)
    assert not root.exists()


@pytest.mark.parametrize('name', ['../escape', '/escape', '.agent/runs/../../escape', 'paper-trader/backend/app.py'])
def test_bundle_cannot_write_outside_ignored_fixture_locations(tmp_path, name):
    bundle, _ = _bundle(tmp_path, name=name)
    with pytest.raises(ValueError, match='fixture path'):
        restore_assurance_inputs(tmp_path / 'checkout', bundle)
    assert not (tmp_path / 'escape').exists()


def test_existing_local_input_is_never_overwritten(tmp_path):
    bundle, _ = _bundle(tmp_path)
    root = tmp_path / 'checkout'
    target = root / '.agent/runs/fixture/input.json'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'local work')
    with pytest.raises(ValueError, match='local assurance input differs'):
        restore_assurance_inputs(root, bundle)
    assert target.read_bytes() == b'local work'


def test_fixture_parent_symlink_cannot_redirect_writes(tmp_path):
    bundle, _ = _bundle(tmp_path)
    root = tmp_path / 'checkout'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / '.agent').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='symlinks'):
        restore_assurance_inputs(root, bundle)
    assert list(outside.iterdir()) == []
