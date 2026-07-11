"""Fail-closed capital guardrails for the research plane.

Research is autonomous; capital allocation is not. This module makes that a
*structural* property rather than a convention: at startup the research process
asserts that it cannot reach the execution database, has not imported any
capital-moving module, and is not running with live execution enabled. Any
violation raises `ResearchIsolationError` and aborts the run — fail closed,
never fail open.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Mapping


class ResearchIsolationError(RuntimeError):
    """Raised when the research process is not provably isolated from capital."""


# Execution modules that can place, route, or manage orders (real or paper), or
# that bind the live broker. The research plane must never import any of these;
# presence in the process's module table means the isolation boundary was crossed.
FORBIDDEN_MODULES = (
    "app.engine.runner",
    "app.engine.broker_factory",
    "app.engine.broker",
    "app.engine.live_broker",
    "app.engine.order_executor",
    "app.engine.kite_order_client",
    "app.providers.live_kite",
)


def assert_distinct_databases(research_db: str, exec_db: str) -> None:
    """The research DB must resolve to a different file than the execution DB."""
    if os.path.realpath(research_db) == os.path.realpath(exec_db):
        raise ResearchIsolationError(
            f"research DB resolves to the execution DB ({exec_db!r}); refusing to "
            "run — the research plane must never open the money ledger."
        )


def assert_no_execution_engine_imported(loaded_modules: Mapping | None = None) -> None:
    """No capital-moving execution module may be imported in this process."""
    loaded = sys.modules if loaded_modules is None else loaded_modules
    hit = [m for m in FORBIDDEN_MODULES if m in loaded]
    if hit:
        raise ResearchIsolationError(
            f"forbidden execution module(s) imported in the research process: {hit}; "
            "the research plane must not import order/broker/runner code."
        )


def assert_capital_safe(env: Mapping | None = None) -> None:
    """The research process must not run with live execution enabled."""
    e = os.environ if env is None else env
    if str(e.get("PT_EXECUTION", "")).strip().lower() == "live":
        raise ResearchIsolationError(
            "PT_EXECUTION=live in the research process environment; refusing to run."
        )


def enforce(*, research_db: str, exec_db: str,
            loaded_modules: Mapping | None = None,
            env: Mapping | None = None) -> None:
    """Run every guardrail; raise on the first violation. Call at research startup."""
    assert_distinct_databases(research_db, exec_db)
    assert_no_execution_engine_imported(loaded_modules)
    assert_capital_safe(env)
