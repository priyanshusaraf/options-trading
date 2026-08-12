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
import re
import sys
from collections.abc import Mapping

from sqlalchemy.engine import make_url


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


def _postgres_authority(url: str) -> tuple:
    parsed = make_url(url)
    return (
        parsed.get_backend_name(), (parsed.host or "").lower(),
        parsed.port or 5432, parsed.database,
    )


def _search_path(url: str) -> tuple[str, ...] | None:
    parsed = make_url(url)
    raw_options = parsed.query.get("options")
    if not raw_options:
        return None
    options = raw_options if isinstance(raw_options, tuple) else (raw_options,)
    declared = []
    for option in options:
        declared.extend(re.findall(
            r"(?:^|\s)-c(?:\s+)?search_path\s*=\s*([^\s]+)",
            str(option),
        ))
    if not declared:
        return None
    # PostgreSQL applies repeated -c settings in order; the final value wins.
    schemas = tuple(
        part.strip().strip('"').lower()
        for part in declared[-1].split(",") if part.strip()
    )
    # Shared-plane URLs must name one explicit application schema. Default and
    # implicit namespaces can overlap through search-path resolution.
    if len(schemas) != 1 or schemas[0] in {"public", "$user"}:
        return None
    return schemas


def assert_distinct_database_authorities(first: str, second: str) -> None:
    """Refuse one physical authority unless explicit PostgreSQL schemas differ."""
    first_url = first if "://" in first else f"sqlite:///{first}"
    second_url = second if "://" in second else f"sqlite:///{second}"
    left = make_url(first_url)
    right = make_url(second_url)
    if left.get_backend_name() == right.get_backend_name() == "sqlite":
        assert_distinct_databases(left.database or "", right.database or "")
        return
    if left.get_backend_name() != "postgresql" or right.get_backend_name() != "postgresql":
        return
    if _postgres_authority(first_url) != _postgres_authority(second_url):
        return
    left_path, right_path = _search_path(first_url), _search_path(second_url)
    if not left_path or not right_path or set(left_path) & set(right_path):
        raise ResearchIsolationError(
            "equal PostgreSQL database authorities require explicit, different search_path schemas"
        )


def assert_pairwise_database_authorities(
    execution: str, research: str, ledger: str,
) -> None:
    """Keep all three logical planes distinct, including shared-server schemas."""
    authorities = (execution, research, ledger)
    for left in range(len(authorities)):
        for right in range(left + 1, len(authorities)):
            assert_distinct_database_authorities(authorities[left], authorities[right])


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


def enforce(*, research_db: str, exec_db: str, ledger_db: str | None = None,
            loaded_modules: Mapping | None = None,
            env: Mapping | None = None) -> None:
    """Run every guardrail; raise on the first violation. Call at research startup."""
    assert_distinct_database_authorities(research_db, exec_db)
    if ledger_db is not None:
        assert_pairwise_database_authorities(exec_db, research_db, ledger_db)
    assert_no_execution_engine_imported(loaded_modules)
    assert_capital_safe(env)
