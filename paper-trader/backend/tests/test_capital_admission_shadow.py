from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.models import DecisionBatchRecord
from app.execution.capital_shadow import (
    AllocatorCandidate,
    ComparisonItem,
    ShadowRefused,
    compare_paper_shadow,
    observe_current_allocator,
)
from tests.test_capital_admission import (
    _admit,
    _batch,
    _candidate,
    _seed_candidates,
    admission_store,
)


def _paper_batch(admission_store):
    _engine, sessions, leases, token = admission_store
    candidates = (
        _candidate(1, cost=70_000, priority=1),
        _candidate(2, cost=50_000, priority=5),
    )
    _seed_candidates(sessions, candidates)
    result = _admit(sessions, leases, token, _batch(token, candidates))
    current = observe_current_allocator((
        AllocatorCandidate("candidate-1", "NIFTY", "LONG", 2, 70_000),
        AllocatorCandidate("candidate-2", "BANKNIFTY", "LONG", 3, 50_000),
    ), available_cash_minor=100_000)
    return sessions, result, current


def test_paper_shadow_reconstructs_exact_allocator_outcome_and_why_receipt(
        admission_store):
    sessions, result, current = _paper_batch(admission_store)
    with sessions() as session:
        before = session.scalar(select(func.count()).select_from(DecisionBatchRecord))
        receipt = compare_paper_shadow(
            session, batch_id=result.decision_batch_id, current=current)
        after = session.scalar(select(func.count()).select_from(DecisionBatchRecord))
    assert receipt.parity and receipt.current_json == receipt.admission_json
    assert before == after == 1
    assert [row.status for row in receipt.why] == ["admitted", "rejected"]
    assert receipt.why[0].reservation_state == "held"
    assert receipt.why[1].reservation_id is None
    assert receipt.replay_digest.startswith("sha256:")
    assert receipt.receipt_address.startswith("sha256:")


def test_shadow_mismatch_is_visible_and_never_changes_admission(admission_store):
    sessions, result, current = _paper_batch(admission_store)
    forged = tuple(
        ComparisonItem(
            row.candidate_intent_id,
            "admitted" if row.status == "rejected" else row.status,
            row.requested_quantity,
            row.requested_quantity,
            row.required_capital_minor,
            row.required_capital_minor,
            "ADMITTED",
        ) if row.status == "rejected" else row
        for row in current
    )
    with sessions() as session:
        receipt = compare_paper_shadow(
            session, batch_id=result.decision_batch_id, current=forged)
        stored = session.get(DecisionBatchRecord, result.decision_batch_id)
    assert not receipt.parity
    assert stored.batch_address == result.batch_address and stored.status == "decided"


def test_shadow_refuses_live_batch_before_any_other_read():
    class StubSession:
        @staticmethod
        def get(_model, _identity):
            return SimpleNamespace(book="live")

    with pytest.raises(ShadowRefused, match="PAPER_SHADOW_ONLY"):
        compare_paper_shadow(StubSession(), batch_id="live", current=())


def test_shadow_modules_are_not_imported_by_runtime_provider_or_broker_paths():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    names = ("capital_shadow", "capital_recovery", "position_lineage")
    for prefix in ("engine", "providers", "core"):
        for path in (root / prefix).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)) \
                        and any(name in ast.unparse(node) for name in names):
                    offenders.append(path.relative_to(root).as_posix())
    assert offenders == []

    forbidden = ("app.engine.runner", "app.engine.live_broker", "app.providers",
                 "requests", "httpx")
    for name in names:
        path = root / "execution" / f"{name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [ast.unparse(node) for node in ast.walk(tree)
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        assert not any(term in statement for term in forbidden for statement in imports)


@pytest.mark.parametrize(
    ("costs", "available", "expected"),
    (
        ((40_000, 30_000), 100_000, ("admitted", "admitted")),
        ((70_000, 30_000), 100_000, ("admitted", "admitted")),
        ((80_000, 30_000), 100_000, ("admitted", "rejected")),
        ((120_000, 30_000), 100_000, ("rejected", "admitted")),
        ((40_000, 30_000), 0, ("rejected", "rejected")),
    ),
)
def test_complete_allocator_matrix_matches_byte_for_byte(
        admission_store, costs, available, expected):
    _engine, sessions, leases, token = admission_store
    candidates = (
        _candidate(1, cost=costs[0], priority=1),
        _candidate(2, cost=costs[1], priority=5),
    )
    _seed_candidates(sessions, candidates)
    batch = _batch(token, tuple(reversed(candidates)), margin_minor=available)
    admitted = _admit(sessions, leases, token, batch)
    current = observe_current_allocator(tuple(reversed((
        AllocatorCandidate("candidate-1", "NIFTY", "LONG", 2, costs[0]),
        AllocatorCandidate("candidate-2", "BANKNIFTY", "LONG", 3, costs[1]),
    ))), available_cash_minor=available)
    with sessions() as session:
        receipt = compare_paper_shadow(
            session, batch_id=admitted.decision_batch_id, current=current)
    assert receipt.parity
    assert tuple(row.status for row in receipt.why) == expected


def test_offline_shadow_script_only_compares_supplied_bytes(tmp_path):
    fixture = tmp_path / "shadow.json"
    fixture.write_text(json.dumps({
        "current": [{"candidate": "a", "status": "admitted"}],
        "admission": [{"candidate": "a", "status": "admitted"}],
    }), encoding="utf-8")
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run([
        sys.executable, "scripts/capital_admission_shadow.py", str(fixture),
    ], cwd=backend, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["parity"] is True
