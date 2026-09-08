import json
import os

import pytest

from research.operations import (
    OperationAlreadyRunning,
    OperationStateCorrupt,
    ResearchOperationRecorder,
    acquire_operation_lock,
    decode_operation_state,
    empty_operation_state,
    encode_operation_state,
    safe_plan_summary,
)


def test_operation_state_is_canonical_content_addressed_and_closed():
    state = empty_operation_state()
    raw = encode_operation_state(state)
    envelope = json.loads(raw)

    assert set(envelope) == {"schema_version", "content_address", "operations"}
    assert envelope["schema_version"] == 1
    assert envelope["content_address"].startswith("sha256:")
    assert envelope["operations"] == {"active": None, "last": None}
    assert decode_operation_state(raw) == state

    for changed in (
        raw + "\n",
        raw.replace('"schema_version":1', '"schema_version":2'),
        raw.replace('"active":null', '"active":null,"client_plan":{}'),
        raw.replace("sha256:", "sha256:tampered"),
    ):
        with pytest.raises(OperationStateCorrupt):
            decode_operation_state(changed)


def test_plan_items_and_terminal_state_are_closed(tmp_path):
    path = tmp_path / "operations.json"
    recorder = ResearchOperationRecorder.start(
        path, trigger="nightly", build="a", provider_mode="mock",
        now=lambda: "2026-08-03T10:00:00Z",
    )
    plan = safe_plan_summary([{
        "program": "P", "hypothesis": "H", "strategy_key": "S",
        "instruments": [], "interval": "day", "days": 30,
    }])
    plan["items"][0]["provider_payload"] = "forbidden"
    with pytest.raises(OperationStateCorrupt):
        recorder.set_plan(plan)

    invalid_terminal = dict(recorder.state["active"])
    invalid_terminal.update({"state": "completed", "completed_at": None})
    with pytest.raises(OperationStateCorrupt):
        encode_operation_state({"active": None, "last": invalid_terminal})


def test_recorder_writes_mode_0600_and_reloads_exact_state(tmp_path):
    path = tmp_path / "research.operations.json"
    lock_path = tmp_path / "research.operations.lock"
    plan = safe_plan_summary([{
        "program": "Nightly",
        "hypothesis": "Evidence survives reload",
        "strategy_key": "trend_impulse_v3",
        "instruments": [type("Inst", (), {"key": "GOLDM"})()],
        "interval": "day",
        "days": 30,
        "optimize_search": True,
    }])

    with acquire_operation_lock(lock_path):
        recorder = ResearchOperationRecorder.start(
            path,
            trigger="nightly",
            build="abc123",
            provider_mode="mock",
            operation_id="op-1",
            now=lambda: "2026-08-03T10:00:00Z",
        )
        recorder.set_plan(plan)
        recorder.transition("experiments")
        recorder.add_completed_run(41)
        recorder.complete(now=lambda: "2026-08-03T10:01:00Z")

    assert oct(path.stat().st_mode & 0o777) == "0o600"
    state = decode_operation_state(path.read_text())
    assert state["active"] is None
    assert state["last"] == {
        "operation_id": "op-1",
        "trigger": "nightly",
        "state": "completed",
        "stage": "completed",
        "started_at": "2026-08-03T10:00:00Z",
        "completed_at": "2026-08-03T10:01:00Z",
        "build": "abc123",
        "provider_mode": "mock",
        "plan": plan,
        "completed_run_ids": [41],
        "failure": None,
    }


def test_process_lock_refuses_overlap_without_mutating_receipt(tmp_path):
    path = tmp_path / "operations.json"
    lock_path = tmp_path / "operations.lock"

    with acquire_operation_lock(lock_path):
        recorder = ResearchOperationRecorder.start(
            path, trigger="nightly", build="a", provider_mode="mock",
            operation_id="active", now=lambda: "2026-08-03T10:00:00Z",
        )
        before = path.read_bytes()
        with pytest.raises(OperationAlreadyRunning):
            with acquire_operation_lock(lock_path):
                pass
        assert path.read_bytes() == before
        recorder.complete(now=lambda: "2026-08-03T10:00:01Z")


def test_stale_active_is_reconciled_only_after_new_owner_has_lock(tmp_path):
    path = tmp_path / "operations.json"
    lock_path = tmp_path / "operations.lock"
    with acquire_operation_lock(lock_path):
        ResearchOperationRecorder.start(
            path, trigger="nightly", build="old", provider_mode="mock",
            operation_id="stale", now=lambda: "2026-08-03T09:00:00Z",
        )

    assert decode_operation_state(path.read_text())["active"]["operation_id"] == "stale"

    with acquire_operation_lock(lock_path):
        ResearchOperationRecorder.start(
            path, trigger="nightly", build="new", provider_mode="mock",
            operation_id="fresh", now=lambda: "2026-08-03T10:00:00Z",
        )
        state = decode_operation_state(path.read_text())
        assert state["active"]["operation_id"] == "fresh"
        assert state["last"]["operation_id"] == "stale"
        assert state["last"]["state"] == "failed"
        assert state["last"]["failure"] == {
            "stage": "startup",
            "code": "RESEARCH_OPERATION_INTERRUPTED",
            "message": "previous research operation ended without a terminal receipt",
        }


def test_failure_receipt_is_stable_bounded_and_contains_no_exception(tmp_path):
    path = tmp_path / "operations.json"
    lock_path = tmp_path / "operations.lock"
    with acquire_operation_lock(lock_path):
        recorder = ResearchOperationRecorder.start(
            path, trigger="manual_script", build="a", provider_mode="kite",
            operation_id="failed", now=lambda: "2026-08-03T10:00:00Z",
        )
        recorder.transition("collection")
        recorder.fail(now=lambda: "2026-08-03T10:00:02Z")

    raw = path.read_text()
    assert "credential=secret" not in raw
    failure = decode_operation_state(raw)["last"]["failure"]
    assert failure == {
        "stage": "collection",
        "code": "RESEARCH_COLLECTION_FAILED",
        "message": "research collection failed",
    }


def test_safe_plan_summary_contains_server_fields_not_objects_or_candles():
    instrument = type("Inst", (), {"key": "SILVERM", "credential": "secret"})()
    summary = safe_plan_summary([{
        "program": "P",
        "hypothesis": "H",
        "strategy_key": "strategy",
        "instruments": [instrument],
        "interval": "30minute",
        "days": 180,
        "optimize_search": True,
        "params": {},
        "seed": 0,
        "min_trades": 20,
        "n_folds": 4,
        "min_positive_fold_frac": 0.6,
        "capital": 100000.0,
        "candles": ["provider payload"],
    }])

    assert summary["experiment_count"] == 1
    assert summary["items"] == [{
        "program": "P",
        "hypothesis": "H",
        "strategy_key": "strategy",
        "instrument_keys": ["SILVERM"],
        "interval": "30minute",
        "days": 180,
        "optimize_search": True,
        "params": {},
        "seed": 0,
        "min_trades": 20,
        "n_folds": 4,
        "min_positive_fold_frac": 0.6,
        "capital": 100000.0,
    }]
    assert summary["content_address"].startswith("sha256:")
    assert "secret" not in json.dumps(summary)
    assert "provider payload" not in json.dumps(summary)

    with pytest.raises(OperationStateCorrupt):
        safe_plan_summary([{}] * 65)


@pytest.mark.parametrize("bad", [
    {"program": "P", "hypothesis": "H", "strategy_key": "S", "instruments": [],
     "interval": "day", "days": True},
    {"program": "P", "hypothesis": "H", "strategy_key": "S", "instruments": [],
     "interval": "day", "days": -1},
    {"program": "P", "hypothesis": "H", "strategy_key": "S", "instruments": "not-a-list",
     "interval": "day", "days": 1},
])
def test_safe_plan_summary_rejects_invalid_admission_fields_before_provider_work(bad):
    with pytest.raises(OperationStateCorrupt):
        safe_plan_summary([bad])


def test_missing_receipt_is_explicit_never_run(tmp_path):
    path = tmp_path / "absent.json"
    assert not os.path.exists(path)
    assert ResearchOperationRecorder.load(path) == empty_operation_state()


def test_oversized_receipt_fails_before_unbounded_decode(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b"x" * 256_001)
    with pytest.raises(OperationStateCorrupt, match="size limit"):
        ResearchOperationRecorder.load(path)


def test_interrupted_file_mirror_replace_preserves_previous_canonical_receipt(tmp_path, monkeypatch):
    """An interrupted optional mirror write cannot leave a torn authority hint."""
    from research import operations
    path = tmp_path / "mirror.json"
    recorder = ResearchOperationRecorder.start(path, trigger="nightly", build="b", provider_mode="mock",
                                              now=lambda: "2026-08-29T00:00:00Z")
    before = path.read_bytes()

    def interrupted_replace(*_):
        raise OSError("injected local mirror interruption")

    monkeypatch.setattr(operations.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="injected local mirror interruption"):
        recorder.transition("planning")
    assert path.read_bytes() == before
    assert ResearchOperationRecorder.load(path)["active"]["stage"] == "startup"
    assert list(tmp_path.glob(".*.tmp")) == []
    assert path.stat().st_mode & 0o777 == 0o600


def test_file_mirror_cannot_restore_cancelled_database_claim(tmp_path):
    from research.domain.base import init_research_db, make_engine, make_sessionmaker
    from research.domain.operations import DurableOperationRecorder, ResearchOperationRepository
    engine = make_engine(str(tmp_path / "authority.db"))
    init_research_db(engine)
    try:
        with make_sessionmaker(engine)() as session:
            repo = ResearchOperationRepository(session)
            durable = DurableOperationRecorder.start(repo, owner_id="owner", operation_id="mirror",
                trigger="nightly", plan={}, build="b", provider_mode="mock", worker_id="worker")
            path = tmp_path / "mirror.json"
            mirror = ResearchOperationRecorder.start(path, trigger="nightly", build="b", provider_mode="mock",
                operation_id="mirror", now=lambda: "2026-08-29T00:00:00Z")
            assert repo.request_cancel("mirror", owner_id="owner")
            mirror.complete(now=lambda: "2026-08-29T00:00:01Z")
            assert ResearchOperationRecorder.load(path)["last"]["state"] == "completed"
            with pytest.raises(RuntimeError, match="claim was lost"):
                durable.complete()
            assert repo.get("mirror", owner_id="owner").status == "cancelled"
    finally:
        engine.dispose()
