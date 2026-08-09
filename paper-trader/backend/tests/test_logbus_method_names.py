"""`LogBus` has `warn`. It does not have `warning`. Calling the wrong one crashes.

This is a nasty defect shape because it only fires on the *degradation* path. `sweep.py`
called `log.warning` in both of its "this dataset can't be addressed, carry on" handlers, so
the handler written to keep a sweep alive instead raised `AttributeError`, which `_run`
caught and turned into the whole sweep aborting with status `error`. It survived because
nothing in the suite had ever made `ordered_dataset_address` raise — the guard's own guard
was never exercised.

The check has to be type-aware, not a grep. The codebase's idiom is a module-level singleton
imported by name — `from app.core.logging import log` — but some modules use the standard
library's `logging.getLogger()` instead (`app/core/earnings.py`), where `.warning` is the
correct name and `.warn` is the deprecated one. A blanket ban on either spelling would be
wrong somewhere in the tree. So: find the names that actually refer to a `LogBus`, and hold
only those to the `LogBus` vocabulary.
"""
from __future__ import annotations

import ast
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[1]

# What LogBus actually exposes. Sourced from app/core/logging.py; if a method is added
# there, add it here — that is the point of the list being explicit.
LOGBUS_METHODS = {"emit", "error", "error_ratelimited", "info", "recent", "subscribe",
                  "trade", "unsubscribe", "warn"}
# Names a stdlib logger has that LogBus does not. These are the crash-on-degradation traps.
# `debug` is here deliberately: LogBus has no debug level, so `log.debug(...)` is the same
# AttributeError waiting on a path nobody exercises.
STDLIB_ONLY = {"warning", "exception", "critical", "fatal", "log", "debug"}


def _logbus_names(tree: ast.Module) -> set[str]:
    """Names in this module that refer to the project `LogBus`.

    The first version of this looked only for `x = get_logger(...)` and was therefore
    VACUOUS: almost nothing uses that. The codebase's actual idiom is a module-level
    singleton imported by name — `from app.core.logging import log` — which matched nothing,
    so the guard passed over the very file whose bug prompted it. Caught by mutating
    `sweep.py` back to `log.warning` and watching this test stay green.

    A module that rebinds the name to something else (`log = logging.getLogger(__name__)`,
    as `app/core/earnings.py` does) is not a LogBus module, and `.warning` is correct there.
    """
    names, rebound = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.core.logging":
            for a in node.names:
                if a.name in ("log", "get_logger"):
                    names.add(a.asname or a.name)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            called = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else None)
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if called == "get_logger":
                names |= targets
            else:
                rebound |= targets
    return names - rebound


def _offenders(path: pathlib.Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    bound = _logbus_names(tree)
    if not bound:
        return []
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in bound
                and node.func.attr in STDLIB_ONLY):
            out.append(f"{path.relative_to(BACKEND)}:{node.lineno} "
                       f"{node.func.value.id}.{node.func.attr}()")
    return out


def test_no_module_calls_a_stdlib_only_method_on_a_logbus():
    offenders = []
    for root in ("app", "scripts", "research"):
        base = BACKEND / root
        if base.exists():
            for path in sorted(base.rglob("*.py")):
                offenders.extend(_offenders(path))
    assert not offenders, (
        "LogBus has no such method — these raise AttributeError the moment they run, and "
        "they are all on error/degradation paths that tests rarely reach: "
        + ", ".join(offenders)
        + ". LogBus uses .warn(); .warning() is the stdlib spelling.")


def test_the_check_knows_what_logbus_actually_has():
    """Keeps the two name sets honest against the real class."""
    from app.core.logging import LogBus

    for name in LOGBUS_METHODS:
        assert hasattr(LogBus, name), f"LOGBUS_METHODS lists {name!r}, LogBus has no such attr"
    for name in STDLIB_ONLY:
        assert not hasattr(LogBus, name), (
            f"STDLIB_ONLY lists {name!r} as absent from LogBus, but LogBus now has it — "
            f"move it to LOGBUS_METHODS or the guard will reject valid calls")


def test_the_dataset_store_is_excluded_from_the_deploy_rsync():
    """A gitignored directory is NOT an rsync-excluded one, and that gap has bitten twice.

    `deploy.sh`'s own header records two outages of exactly this class (the clobbered
    `.env`, the uid-stamped directories). The sweep's content-addressed candle store is the
    next one waiting: measured at ~38 bytes/bar, a full 10,000 x 5 sweep run on the Mac is
    ~10 GB that a whole-tree rsync would push to a 1 GB droplet.

    This lives here rather than in a deploy-specific file because there is no deploy.sh
    test module yet; move it when one exists.
    """
    deploy = BACKEND.parent / "scripts" / "deploy.sh"
    body = deploy.read_text(encoding="utf-8")
    excludes = body.split("EXCLUDES=(", 1)[1].split("\n)", 1)[0]
    assert "backtest_datasets" in excludes, (
        "app/backtest/dataset_store.py writes candle blobs under backend/backtest_datasets/. "
        "It is gitignored, which does not stop rsync — add it to deploy.sh's EXCLUDES.")
