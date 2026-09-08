"""Validate readable whitespace copies against exact archived source bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tarfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PRESERVATION = REPOSITORY_ROOT / "paper-trader/docs/source-preservation"


def normalize_source(data: bytes, path: str) -> bytes:
    """Preserve Markdown hard breaks while normalizing CRLF and trailing EOF blanks."""
    data = data.replace(b"\r\n", b"\n")
    lines = data.split(b"\n")
    if path.endswith(".md"):
        lines = [line[:-2] + b"\\" if line.endswith(b"  ") else line for line in lines]
    return b"\n".join(lines).rstrip(b"\n") + b"\n"


def original_source(path: str, root: Path = REPOSITORY_ROOT,
                    preservation: Path = PRESERVATION) -> bytes:
    """Return exact historical bytes only after archive and readable-copy validation."""
    manifest = json.loads((preservation / "manifest.json").read_text())
    archive = preservation / "originals.tar.gz"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("original archive hash mismatch")
    entry = manifest["sources"][path]
    with tarfile.open(archive, "r:gz") as bundle:
        source = bundle.extractfile(path)
        if source is None:
            raise ValueError(f"missing original source: {path}")
        original = source.read()
    if hashlib.sha256(original).hexdigest() != entry["original_sha256"]:
        raise ValueError(f"original source hash mismatch: {path}")
    readable = (root / path).read_bytes()
    if readable != normalize_source(original, path):
        raise ValueError(f"readable source differs beyond whitespace normalization: {path}")
    if hashlib.sha256(readable).hexdigest() != entry["readable_sha256"]:
        raise ValueError(f"readable source hash mismatch: {path}")
    return original
