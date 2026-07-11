"""The nightly cron entry point (foundations stub): it must enforce the capital
guardrails before doing anything, then initialise research.db. Run in a fresh
interpreter so the guardrails see a real, uncontaminated module table.
"""
import os
import subprocess
import sys


def _run(env_extra):
    env = {**os.environ, "PYTHONPATH": "."}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "research.nightly"],
                          capture_output=True, text=True, env=env)


def test_nightly_initialises_research_db(tmp_path):
    research_db = str(tmp_path / "research.db")
    r = _run({"PT_RESEARCH_DB_PATH": research_db,
              "PT_DB_PATH": str(tmp_path / "paper_trader.db"),
              "PT_EXECUTION": "paper"})
    assert r.returncode == 0, r.stderr
    assert os.path.exists(research_db)


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
