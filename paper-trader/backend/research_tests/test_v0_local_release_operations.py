"""Research-plane assertions for the closed V0 local release evidence plan."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/v0_local_release_evidence.py"


def _module():
    spec = importlib.util.spec_from_file_location("q14_research_release_evidence", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


evidence = _module()


def test_research_head_and_current_migration_authority_are_closed_inputs():
    assert "paper-trader/backend/research/domain/migrate.py" in evidence.REPOSITORY_FILES
    assert "paper-trader/backend/research/domain/migrations/__init__.py" in evidence.REPOSITORY_FILES
    assert "paper-trader/backend/research_tests/test_foundation_direct_migration_0011.py" in evidence.REPOSITORY_FILES


def test_preflight_requires_real_pg16_research_restart_and_plane_contracts():
    steps = evidence.preflight_steps()
    pg = next(step for step in steps if step.label == "postgresql16-three-plane-upgrade-restore")
    assert pg.argv[:3] == ("$PYTHON", "scripts/run_disposable_postgres.py", "--")
    assert any("clean_postgresql16_reaches_exact_0011" in item for item in pg.argv)
    assert any("postgresql_interruption_rolls_back" in item for item in pg.argv)
    assert any("version_only_marker_and_sqlite_cookie" in item for item in pg.argv)
    policy = evidence._resource_policy()
    assert policy["max_child_memory_bytes"] == 2 * 1024 * 1024 * 1024
    assert policy["query_budget"]["authority"] == evidence.QUERY_BUDGET_AUTHORITY
    assert policy["query_budget"]["max_statements"] == 24


def test_receipt_preserves_historical_security_operations_gates():
    blockers = set(evidence.HISTORICAL_RELEASE_BLOCKERS)
    assert "inherited_broker_check_copy_refusal_open" in blockers
    assert "fixed_0041_capital_test_red_open" in blockers
    claims = evidence._claims("PASS")
    assert claims["highest_readiness_level"] == "locally_runnable"
    assert claims["release_deployable"] is False
    assert claims["production_rehearsed"] is False
    assert claims["deployed"] is False


def test_no_test_plan_command_can_name_provider_vps_or_deployment_action():
    forbidden = ("kite", "upstox", "dhan", "zerodha", "ssh", "deploy.sh", "systemctl")
    argv = " ".join(part for step in evidence.preflight_steps() for part in step.argv).lower()
    assert not any(value in argv for value in forbidden)
