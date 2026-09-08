"""Restore sealed test inputs without accepting local logs or regenerating oracles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def _fixture_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or relative.parts[:2] != ('.agent', 'runs'):
        raise ValueError('invalid assurance fixture path')
    target = root.joinpath(*relative.parts)
    if any(parent.is_symlink() for parent in (target, *target.parents)):
        raise ValueError('assurance fixtures cannot follow symlinks')
    return target


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _restore_input(root: Path, archive: tarfile.TarFile, member: tarfile.TarInfo, expected: dict) -> None:
    if not member.isfile() or member.size != expected['size']:
        raise ValueError('assurance fixture type or size differs')
    target = _fixture_path(root, member.name)
    source = archive.extractfile(member)
    if source is None:
        raise ValueError('assurance fixture content is missing')
    data = source.read()
    if _digest(data) != expected['sha256']:
        raise ValueError('sealed assurance fixture content differs')
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError(f'local assurance input differs from sealed fixture: {member.name}')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output:
        output.write(data)


def restore_assurance_inputs(root: Path, bundle: Path | None = None) -> None:
    """Materialize exact historical inputs at their original logical locations."""
    root = root.resolve()
    bundle = bundle or Path(__file__).parent / 'fixtures' / 'indicator_accuracy'
    index = json.loads((bundle / 'manifest.json').read_text())
    if index['schema'] != 'indicator-assurance-fixtures/1':
        raise ValueError('unknown assurance fixture schema')
    archive_path = bundle / 'sealed-inputs.tar.gz'
    if _digest(archive_path.read_bytes()) != index['archive_sha256']:
        raise ValueError('sealed assurance archive differs')
    expected = {entry['path']: entry for entry in index['files']}
    if len(expected) != len(index['files']):
        raise ValueError('duplicate assurance fixture manifest path')
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) != len(expected) or {member.name for member in members} != set(expected):
            raise ValueError('assurance archive members differ from manifest')
        for member in members:
            _restore_input(root, archive, member, expected[member.name])
    for directory in index['output_directories']:
        _fixture_path(root, directory).mkdir(parents=True, exist_ok=True)
