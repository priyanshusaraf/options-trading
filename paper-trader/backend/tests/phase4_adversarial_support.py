"""Shared runners for independently attributable Phase 4 adversarial rows.

The row tests deliberately call existing public-seam tests in a fresh pytest
process.  This keeps each matrix row independently selectable while rerunning
the real current-byte seams instead of copying product behavior into fixtures.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


BACKEND = Path(__file__).resolve().parents[1]


def run_current_nodes(nodes: Iterable[str]) -> str:
    """Run exact current-byte nodes and reject non-execution dispositions."""
    selected = tuple(nodes)
    assert selected
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-vv", "-rA", *selected],
        cwd=BACKEND,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    transcript = result.stdout + result.stderr
    print(transcript)
    lowered = transcript.lower()
    assert result.returncode == 0, transcript
    for forbidden in (" skipped", " xfailed", " xpassed", " deselected"):
        assert forbidden not in lowered, transcript
    for node in selected:
        assert node in transcript, f"selected node absent from transcript: {node}\n{transcript}"
    return transcript


def run_disposable_postgres_nodes(nodes: Iterable[str]) -> str:
    """Run exact nodes in one fresh disposable PostgreSQL 16 cluster."""
    selected = tuple(nodes)
    assert selected
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_disposable_postgres.py",
            "--",
            sys.executable,
            "-m",
            "pytest",
            "-vv",
            "-rA",
            *selected,
        ],
        cwd=BACKEND,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    transcript = result.stdout + result.stderr
    print(transcript)
    lowered = transcript.lower()
    assert result.returncode == 0, transcript
    for forbidden in (" skipped", " xfailed", " xpassed", " deselected"):
        assert forbidden not in lowered, transcript
    for node in selected:
        assert node in transcript, f"selected node absent from transcript: {node}\n{transcript}"
    return transcript
