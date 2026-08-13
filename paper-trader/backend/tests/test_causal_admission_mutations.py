"""Adversarial admission mutations for the independent causal parity gate."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.strategy.admission import AdmissionRefusalCode
from scripts import causal_admission_mutations as mutations


def test_post_registration_expanding_z_helper_mutation_is_stale() -> None:
    """Hypothesis 7: changing a registered helper cannot reach parity evaluation."""
    decision = mutations.stale_helper_decision()

    assert decision.artifact is None
    assert decision.refusal_code is AdmissionRefusalCode.IMPLEMENTATION_STALE


@pytest.mark.parametrize("name", mutations.FRESH_MUTATION_NAMES)
def test_fresh_future_reading_kernels_fail_independent_parity(name: str) -> None:
    """Hypothesis 6: newly identified lookahead code must die after fresh identity."""
    decision = mutations.fresh_mutation_decision(name)

    assert decision.artifact is None
    assert decision.refusal_code is AdmissionRefusalCode.STREAMING_DIVERGENCE


def test_mutation_command_reports_every_required_kill() -> None:
    """The command fails closed unless stale identity and all five causal kills occur."""
    report = mutations.run_mutations()

    assert report["identity_killed"] == 1
    assert report["causal_killed"] == 5
    assert report["survived"] == 0


def test_mutation_command_has_the_documented_json_exit_contract() -> None:
    """Hypothesis 7: the reviewed command itself cannot silently bypass a kill."""
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/causal_admission_mutations.py", "--json"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "causal_killed": 5,
        "identity_killed": 1,
        "survived": 0,
    }
