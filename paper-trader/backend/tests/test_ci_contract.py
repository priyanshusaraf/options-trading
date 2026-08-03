"""CI must run the repository's deterministic acceptance checks fail-closed."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "strategy-os-ci.yml"
PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
EXPECTED_ACTIONS = {
    "backend": {"actions/checkout", "actions/setup-python"},
    "deterministic-smoke": {"actions/checkout", "actions/setup-python"},
    "frontend": {"actions/checkout", "actions/setup-node"},
}


def _workflow() -> dict:
    with WORKFLOW_PATH.open(encoding="utf-8") as handle:
        return yaml.load(handle, Loader=yaml.BaseLoader)


def _run_steps(job: dict) -> list[dict]:
    return [step for step in job["steps"] if "run" in step]


def _commands(job: dict) -> list[str]:
    return [step["run"].strip() for step in _run_steps(job)]


def test_ci_runs_on_every_push_and_pull_request_with_read_only_permissions():
    workflow = _workflow()

    assert set(workflow["on"]) == {"push", "pull_request"}
    assert workflow["permissions"] == {"contents": "read"}


def test_ci_has_only_the_three_required_fail_closed_jobs():
    jobs = _workflow()["jobs"]

    assert set(jobs) == {"backend", "deterministic-smoke", "frontend"}
    for job in jobs.values():
        assert job["runs-on"] == "ubuntu-latest"
        assert int(job["timeout-minutes"]) > 0
        assert "continue-on-error" not in job
        for step in job["steps"]:
            assert "continue-on-error" not in step


def test_every_third_party_action_is_pinned_to_a_full_commit_sha():
    for name, job in _workflow()["jobs"].items():
        actions = [step["uses"] for step in job["steps"] if "uses" in step]
        assert actions
        assert all(PINNED_ACTION.fullmatch(action) for action in actions), actions
        assert {action.partition("@")[0] for action in actions} == EXPECTED_ACTIONS[name]


def test_backend_job_installs_requirements_and_names_both_test_roots():
    backend = _workflow()["jobs"]["backend"]

    assert _commands(backend) == [
        "python -m pip install -r requirements.txt",
        "python -m pytest tests research_tests --tb=short",
    ]
    assert all(
        step["working-directory"] == "paper-trader/backend"
        for step in _run_steps(backend)
    )


def test_dotenv_opt_out_is_scoped_to_non_pytest_smoke_processes():
    """Pytest must be able to simulate the production dotenv branch.

    Root conftest already removes dotenv from the test process before app imports.
    A workflow-level opt-out leaks into tests that temporarily remove pytest from
    ``sys.modules`` and makes the production boundary impossible to exercise.
    """
    workflow = _workflow()
    jobs = workflow["jobs"]

    assert "PT_DISABLE_DOTENV" not in workflow.get("env", {})
    assert "PT_DISABLE_DOTENV" not in jobs["backend"].get("env", {})
    assert jobs["deterministic-smoke"]["env"]["PT_DISABLE_DOTENV"] == "1"


def test_deterministic_smoke_job_runs_both_secret_free_proofs():
    smoke = _workflow()["jobs"]["deterministic-smoke"]

    assert smoke["needs"] == "backend"
    assert _commands(smoke) == [
        "python -m pip install -r requirements.txt",
        "python scripts/dryrun.py 700",
        "python scripts/backtest_smoke.py",
    ]
    assert all(
        step["working-directory"] == "paper-trader/backend"
        for step in _run_steps(smoke)
    )


def test_frontend_job_uses_lockfile_and_runs_tests_types_and_build():
    frontend = _workflow()["jobs"]["frontend"]

    assert _commands(frontend) == [
        "npm ci",
        "npm test",
        "npm run typecheck",
        "npm run build",
    ]
    assert all(
        step["working-directory"] == "paper-trader/frontend"
        for step in _run_steps(frontend)
    )
