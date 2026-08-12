"""The nightly cron entry point (foundations stub): it must enforce the capital
guardrails before doing anything, then initialise research.db. Run in a fresh
interpreter so the guardrails see a real, uncontaminated module table.
"""
import os
import subprocess
import sys


def _run(env_extra, tmp_path=None):
    """Run the cron one-shot in a fresh interpreter.

    ALWAYS redirect the report directory. Until 2026-08-01 `_load_plan()` returned
    [] so a nightly run wrote nothing, and this harness could safely inherit cwd.
    Now that the plan is real, an unredirected run drops report_*.md into the repo
    working tree — which dirties it, and `deploy.sh` refuses to ship a dirty tree
    with no override. A test that silently breaks every future deploy is a worse
    bug than the one it was written to catch.
    """
    env = {**os.environ, "PYTHONPATH": "."}
    if tmp_path is not None:
        env.setdefault("PT_RESEARCH_REPORT_DIR", str(tmp_path))
        env.setdefault(
            "PT_RESEARCH_OPERATION_RECEIPT", str(tmp_path / "operations.json")
        )
        env.setdefault(
            "PT_RESEARCH_OPERATION_LOCK", str(tmp_path / "operations.lock")
        )
        # Generation is the expensive half and this harness only asserts the
        # entry point wires up; keep the subprocess quick.
        env.setdefault("PT_RESEARCH_GENERATE_LIMIT", "0")
    env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "research.nightly"],
                          capture_output=True, text=True, env=env)


def test_nightly_initialises_research_db(tmp_path):
    research_db = str(tmp_path / "research.db")
    r = _run({"PT_RESEARCH_DB_PATH": research_db,
              "PT_DB_PATH": str(tmp_path / "paper_trader.db"),
              "PT_EXECUTION": "paper",
              "PT_RESEARCH_OWNER_ID": "test-owner",
              "PT_RESEARCH_ENABLED": "1"}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert os.path.exists(research_db)
    from research.domain.base import make_engine, make_sessionmaker
    from research.domain.operations import ResearchOperationRepository
    engine = make_engine(research_db)
    with make_sessionmaker(engine)() as session:
        state = ResearchOperationRepository(session).latest(owner_id="test-owner")
    engine.dispose()
    assert state.status == "completed"
    assert state.trigger == "nightly"
    assert state.plan["content_address"].startswith("sha256:")
    assert state.completed_run_ids


def test_nightly_skips_when_research_disabled(tmp_path):
    # freeze flag (default off): the cron one-shot exits cleanly WITHOUT creating
    # or touching research.db — the plane is dormant, not broken. The guardrails
    # still run first (see the fail-closed tests below, which pass no flag).
    research_db = str(tmp_path / "research.db")
    r = _run({"PT_RESEARCH_DB_PATH": research_db,
              "PT_DB_PATH": str(tmp_path / "paper_trader.db"),
              "PT_EXECUTION": "paper",
              "PT_RESEARCH_ENABLED": "0"}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "skipped" in r.stdout
    assert not os.path.exists(research_db)
    assert not os.path.exists(tmp_path / "operations.json")


def test_nightly_fails_closed_when_research_db_equals_execution_db(tmp_path):
    shared = str(tmp_path / "paper_trader.db")
    r = _run({"PT_RESEARCH_DB_PATH": shared, "PT_DB_PATH": shared,
              "PT_EXECUTION": "paper"})
    assert r.returncode != 0
    assert "resolves to the execution DB" in (r.stderr + r.stdout)


def test_nightly_fails_closed_on_live_execution_env(tmp_path):
    r = _run({"PT_RESEARCH_DB_PATH": str(tmp_path / "research.db"),
              "PT_DB_PATH": str(tmp_path / "paper_trader.db"),
              "PT_EXECUTION": "live"})
    assert r.returncode != 0
    assert "PT_EXECUTION=live" in (r.stderr + r.stdout)
