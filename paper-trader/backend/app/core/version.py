"""Build provenance — which commit is this process running?

`scripts/deploy.sh` writes `backend/VERSION` on every deploy:

    commit=2b3356d
    branch=feat/exec-completeness
    deployed_at=2026-07-28T04:30:00Z
    deployed_by=priyanshusaraf@mac

The file is gitignored and generated per-deploy, so it is absent in a dev
checkout and in tests — that is normal and must not break anything. What it must
NEVER do is fail quietly: a running engine that cannot name its own build is
writing untraceable rows into a paisa-exact ledger, so a missing or unparseable
VERSION is logged at ERROR every time it is consulted fresh.

Unresolvable builds stamp the literal string `UNKNOWN` ("unknown"), never NULL.
NULL in `trades.build_sha` has exactly one meaning — the row predates the column
(pre-2026-07-28) and therefore *cannot* be attributed. A process that ran without
a readable VERSION is a different fact: the row was written by an identified
process whose build we failed to capture. Collapsing both onto NULL would make
"we never recorded this" indistinguishable from "we recorded that we could not
tell", and only the second one is a bug worth chasing.

The parsed value is cached for the process lifetime. That is deliberate: the
stamp on a trade should be the build that is *running*, not whatever a
mid-session rsync happened to leave on disk.
"""
from __future__ import annotations

from pathlib import Path

from app.core.logging import log

# backend/app/core/version.py -> backend/VERSION
_VERSION_PATH = Path(__file__).resolve().parents[2] / "VERSION"

# Stamped when a process is running but cannot name its own build. Distinct from
# NULL, which means "this row predates build provenance entirely". Kept short and
# lowercase so it can never be mistaken for a real abbreviated SHA (hex only).
UNKNOWN = "unknown"

_cache: dict | None = None


def parse_version_file(path: Path) -> dict:
    """Parse a `key=value` VERSION file. Returns {} for anything unusable.

    Unusable means: absent, unreadable, or missing the one key that matters
    (`commit`). A file without a commit is not partially useful — it cannot
    identify the build — so it is treated the same as no file at all.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    info: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key:
            info[key] = value

    if not info.get("commit"):
        return {}
    return info


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = parse_version_file(_VERSION_PATH)
        if not _cache:
            log.error(
                f"VERSION unreadable or missing at {_VERSION_PATH} — this build "
                f"cannot be identified. Trades written by this process will carry "
                f"build_sha='{UNKNOWN}' (NULL means 'predates the column', which is "
                f"a different thing). Deploy via scripts/deploy.sh to stamp it."
            )
    return _cache


def reset_cache() -> None:
    """Test seam — forces the next read to hit disk again."""
    global _cache
    _cache = None


def get_build_sha() -> str:
    """The commit this process is running, or UNKNOWN if it cannot be determined.

    Never returns None: this is the default for `trades.build_sha`, and a NULL
    there is reserved for rows written before the column existed.
    """
    return _load().get("commit") or UNKNOWN


def get_build_info() -> dict:
    """Full build metadata for /api/health. Always returns the same shape.

    `commit` uses the same UNKNOWN sentinel as the ledger stamp, so what
    /api/health reports and what lands in `trades.build_sha` cannot disagree.
    deploy.sh compares this to the SHA it shipped — "unknown" fails that
    comparison loudly, which is the intent.
    """
    info = _load()
    return {
        "commit": info.get("commit") or UNKNOWN,
        "branch": info.get("branch") or None,
        "deployed_at": info.get("deployed_at") or None,
        "deployed_by": info.get("deployed_by") or None,
    }


def log_build_banner() -> None:
    """Called once at boot. Loud either way — the SHA is the thing you need in
    the journal when reconstructing what a trade was executed by."""
    info = get_build_info()
    if info["commit"] != UNKNOWN:
        log.info(
            f"BUILD {info['commit']} ({info['branch'] or 'unknown branch'}) "
            f"deployed {info['deployed_at'] or '?'} by {info['deployed_by'] or '?'}"
        )
    else:
        log.warn(
            f"BUILD UNKNOWN — no usable VERSION file. Trades will be recorded with "
            f"build_sha='{UNKNOWN}' and cannot be traced to a commit."
        )
