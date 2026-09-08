"""Guard against this codebase's defining failure: built, correct, unused.

Seven times in one session a mechanism turned out to be present, correct, and
consuming nothing:

  - `var_sr` computed nowhere, so DSR deflation silently never engaged while a
    docstring claimed a wider search raised the bar;
  - `neff` written at M0 with zero callers;
  - `retest_priority` written every run and read by nothing;
  - new strategy blocks the sampler could not reach;
  - `/api/health` and `/api/storage` data no screen displayed;
  - `PaperBroker.close()` that nothing called;
  - and `edge_weights()`, which I wrote and left unwired on the same day I
    committed three messages criticising the pattern.

Each looked implemented. Each did nothing. Unit tests pass happily on code with
no callers, so the tests are not what catches this — a call-graph check is.

The rule: a public callable in `app/` or `research/` must be referenced
somewhere. Decorator-registered functions (FastAPI routes, properties) are
exempt because their caller is the framework. Everything else that is genuinely
meant to be unreferenced goes in ACCEPTED below, with a reason — which forces
the question "why does this exist?" to be answered in writing rather than by
silence.
"""
from __future__ import annotations

import ast
import pathlib
import re

SCAN_ROOTS = ("app", "research")
REFERENCE_ROOTS = ("app", "research", "tests", "research_tests", "scripts")

# Known-unreferenced, deliberately. Each entry states WHY, because "it's fine"
# is exactly the reasoning that let the seven above accumulate.
ACCEPTED = {
    # A boolean convenience wrapper around validate_source(), which IS called and
    # raises. The sandbox perimeter is the raising version; this one is sugar.
    "is_safe",
    # Instrument ordering helper kept for the UI's benefit; harmless.
    "by_priority",
    # Symmetric counterpart to log.subscribe(). The engine never unsubscribes
    # (the bus lives as long as the process), but removing half a pair invites a
    # leak the day someone does.
    "unsubscribe",
    # 2026-08-22 owner correction: `find_reusable_phase4`, `peek_next_claimable_run`,
    # and `typed_row_digest` were REMOVED as obsolete duplication rather than
    # kept on this list. An exception entry means deferred, not resolved; all
    # three had zero production consumers.
}


def _public_callables() -> list[tuple[str, str, int]]:
    out = []
    for root in SCAN_ROOTS:
        for f in pathlib.Path(root).rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                tree = ast.parse(f.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name.startswith("_"):
                    continue          # private by intent
                if node.decorator_list:
                    continue          # the framework is the caller
                out.append((node.name, str(f), node.lineno))
    return out


def _corpus() -> list[tuple[str, str]]:
    files = []
    for root in REFERENCE_ROOTS:
        p = pathlib.Path(root)
        if not p.exists():
            continue
        for f in p.rglob("*.py"):
            if "__pycache__" not in str(f):
                files.append((str(f), f.read_text()))
    return files


def test_every_public_callable_has_a_caller():
    """The guard. A new mechanism nobody wired fails here instead of being
    discovered months later — or, as happened seven times today, by tripping
    over it."""
    corpus = _corpus()
    orphans = []
    for name, deffile, line in _public_callables():
        if name in ACCEPTED:
            continue
        hits = 0
        for fname, body in corpus:
            for m in re.finditer(rf"\b{re.escape(name)}\b", body):
                if fname == deffile and body[: m.start()].count("\n") + 1 == line:
                    continue          # the definition itself
                hits += 1
                break
            if hits:
                break
        if not hits:
            orphans.append(f"{deffile}:{line} {name}()")
    assert not orphans, (
        "public callables defined but referenced NOWHERE — either wire them, "
        "delete them, or add to ACCEPTED with a reason:\n  "
        + "\n  ".join(orphans))


def test_the_scan_actually_finds_things():
    """A guard that scans nothing passes forever. Pin that the scan sees a
    realistic number of callables and a corpus to check them against."""
    assert len(_public_callables()) > 200
    assert len(_corpus()) > 100


def test_accepted_entries_still_exist():
    """An ACCEPTED name that no longer exists is stale permission — it would
    silently cover a future function that happens to share the name."""
    defined = {n for n, _, _ in _public_callables()}
    # is_safe and friends may be decorated or private-adjacent; check the source
    # tree broadly rather than only the undecorated set.
    all_src = "\n".join(body for _, body in _corpus())
    for name in ACCEPTED:
        assert name in defined or f"def {name}" in all_src, \
            f"ACCEPTED entry {name!r} no longer exists — remove it"
