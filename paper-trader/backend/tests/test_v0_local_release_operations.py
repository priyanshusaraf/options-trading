"""Closed local release-evidence interface and adversarial guard tests."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest


DEFAULT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/v0_local_release_evidence.py"
SCRIPT = Path(os.environ.get("Q14_EVIDENCE_SCRIPT", DEFAULT_SCRIPT))


def _module():
    spec = importlib.util.spec_from_file_location("q14_v0_local_release_evidence", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


evidence = _module()


def _checkout() -> Path:
    return Path(__file__).resolve().parents[3]


def _frontend(tmp_path: Path) -> Path:
    root = tmp_path / "frontend"
    root.mkdir()
    (root / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
    return root


def _run_cli(*argv: str, env: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, str(DEFAULT_SCRIPT), *argv], cwd=_checkout() / "paper-trader/backend",
        env=env, check=False, capture_output=True, text=True, timeout=90,
    )


def test_inventory_receipt_bytes_are_deterministic_in_fresh_processes(tmp_path):
    frontend = _frontend(tmp_path)
    first, second = tmp_path / "one", tmp_path / "two"
    common = (
        "inventory", "--checkout-root", str(_checkout()), "--frontend-root", str(frontend),
        "--observed-at", "2026-08-29T00:00:00Z",
    )
    one = _run_cli(*common, "--output-root", str(first), "--output-name", "receipt.json")
    two = _run_cli(*common, "--output-root", str(second), "--output-name", "receipt.json")
    assert (one.returncode, one.stdout, one.stderr) == (0, "", "")
    assert (two.returncode, two.stdout, two.stderr) == (0, "", "")
    assert (first / "receipt.json").read_bytes() == (second / "receipt.json").read_bytes()


def test_inventory_records_presence_only_and_never_environment_values(monkeypatch, tmp_path):
    frontend = _frontend(tmp_path)
    secret = "q14-secret-must-never-appear"
    env = dict(os.environ, PT_PROVIDER=secret, PT_LIVE_ACK=secret, KITE_API_KEY=secret)
    output = tmp_path / "receipt"
    result = _run_cli(
        "inventory", "--checkout-root", str(_checkout()), "--frontend-root", str(frontend),
        "--output-root", str(output), "--observed-at", "2026-08-29T00:00:00Z", env=env,
    )
    assert result.returncode == 0
    encoded = (output / "inventory.json").read_text()
    assert secret not in encoded + result.stdout + result.stderr
    presence = json.loads(encoded)["answer"]["inventory"]["safe_configuration_presence"]
    assert presence["PT_PROVIDER"] is True and presence["PT_LIVE_ACK"] is True
    assert "KITE_API_KEY" not in presence


def test_closed_inputs_refuse_symlink_traversal_special_and_output_recursion(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    root.mkdir()
    real = root / "real"
    real.write_text("x")
    (root / "link").symlink_to(real)
    with pytest.raises(evidence.EvidenceRefusal, match="symlink"):
        evidence._safe_regular_file(root, "link")
    with pytest.raises(evidence.EvidenceRefusal, match="unsafe"):
        evidence._safe_regular_file(root, "../escape")
    directory = root / "directory"
    directory.mkdir()
    with pytest.raises(evidence.EvidenceRefusal, match="non-regular"):
        evidence._safe_regular_file(root, "directory")
    with pytest.raises(evidence.EvidenceRefusal, match="cannot equal"):
        evidence._validate_output(root, root, "receipt.json")
    with pytest.raises(evidence.EvidenceRefusal, match="plain filename"):
        evidence._validate_output(root, tmp_path / "output", "nested/receipt.json")


def test_safe_subprocess_environment_is_closed_and_three_plane(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_DANGEROUS_NEW_SETTING", "secret")
    monkeypatch.setenv("KITE_API_SECRET", "secret")
    monkeypatch.setenv("HOME", "/must/not/be/repurposed")
    monkeypatch.setenv("CODEX_HOME", "/must/not/be/repurposed")
    env = evidence._safe_environment(tmp_path)
    assert "PT_DANGEROUS_NEW_SETTING" not in env
    assert "KITE_API_SECRET" not in env
    assert "HOME" not in env and "CODEX_HOME" not in env
    assert env["PT_DISABLE_DOTENV"] == "1"
    assert env["PT_PROVIDER"] == "mock" and env["PT_EXECUTION"] == "paper"
    assert env["PT_LIVE_ACK"] == ""
    assert len({env["PT_DB_PATH"], env["PT_LEDGER_DB_PATH"], env["PT_RESEARCH_DB_PATH"]}) == 3


def test_preflight_plan_is_closed_structured_and_covers_existing_authorities():
    steps = evidence.preflight_steps()
    assert len(steps) == 3 and len({step.label for step in steps}) == 3
    flattened = [part for step in steps for part in step.argv]
    assert not any(part in {"sh", "bash", "zsh", "-c"} for part in flattened)
    assert "scripts/run_disposable_postgres.py" in flattened
    assert "tests/test_v0_release_profile.py" in flattened
    assert "tests/test_postgresql_restore_live.py::test_pg16_dump_restore_three_plane_generation_is_digest_identical" in flattened
    assert any(part.startswith("research_tests/test_foundation_direct_migration_0011.py::") for part in flattened)
    assert any("interruption_rolls_back" in part for part in flattened)
    assert any("no_provider_broker_order_live" in part for part in flattened)
    assert evidence.QUERY_BUDGET_AUTHORITY in flattened
    assert evidence._resource_policy()["query_budget"] == {
        "cli_direct_database_queries": 0,
        "authority": evidence.QUERY_BUDGET_AUTHORITY,
        "max_statements": 24,
    }
    for owned in (
        "paper-trader/backend/scripts/v0_local_release_evidence.py",
        "paper-trader/backend/tests/test_v0_local_release_operations.py",
        "paper-trader/backend/research_tests/test_v0_local_release_operations.py",
    ):
        assert owned in evidence.REPOSITORY_FILES


def _minimal_inventory_answer():
    return {
        "schema": evidence.ANSWER_SCHEMA, "kind": "inventory", "status": "PASS",
        "inventory": {}, "claims": evidence._claims("INVENTORY_ONLY"),
    }


def test_guard_receipt_digest_accepts_exact_and_refuses_tamper(tmp_path, monkeypatch, capsys):
    answer = _minimal_inventory_answer()
    receipt = evidence._receipt(answer, "2026-08-29T00:00:00Z")
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(evidence, "_recompute_bound_files", lambda *_args: None)
    monkeypatch.setattr(evidence, "collect_inventory", lambda *_args: {})
    args = SimpleNamespace(
        checkout_root=str(tmp_path), frontend_root=str(tmp_path), receipt=str(path),
        require_signed=False,
    )
    assert evidence.verify_receipt_command(args) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True
    receipt["answer"]["claims"]["release_deployable"] = True
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(evidence.EvidenceRefusal, match="digest"):
        evidence.verify_receipt_command(args)


def test_verify_rejects_extra_fields_and_unsigned_when_required(tmp_path, monkeypatch):
    answer = _minimal_inventory_answer()
    receipt = evidence._receipt(answer, "2026-08-29T00:00:00Z")
    receipt["extra"] = "not allowed"
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    args = SimpleNamespace(
        checkout_root=str(tmp_path), frontend_root=str(tmp_path), receipt=str(path),
        require_signed=False,
    )
    with pytest.raises(evidence.EvidenceRefusal, match="missing or extra"):
        evidence.verify_receipt_command(args)
    receipt.pop("extra")
    path.write_text(json.dumps(receipt), encoding="utf-8")
    args.require_signed = True
    with pytest.raises(evidence.EvidenceRefusal, match="no signing-key lifecycle"):
        evidence.verify_receipt_command(args)


def _preflight_args(tmp_path):
    return argparse.Namespace(
        checkout_root=str(tmp_path), frontend_root=str(tmp_path),
        output_root=str(tmp_path / "output"), output_name="preflight.json",
        observed_at="2026-08-29T00:00:00Z",
        step_timeout=evidence.DEFAULT_STEP_TIMEOUT_SECONDS,
    )


def _patch_preflight(monkeypatch, tmp_path):
    monkeypatch.setattr(evidence, "_safe_root", lambda value, **_kwargs: Path(value))
    monkeypatch.setattr(evidence, "collect_inventory", lambda *_args: {"closed": True})
    monkeypatch.setattr(evidence, "preflight_steps", lambda: (evidence.Step("guard", ("$PYTHON",)),))


def test_failed_step_cannot_produce_pass_receipt(tmp_path, monkeypatch):
    _patch_preflight(monkeypatch, tmp_path)
    result = {
        "label": "guard", "argv": ["$PYTHON"], "returncode": 1,
        "timeout_seconds": evidence.DEFAULT_STEP_TIMEOUT_SECONDS,
        "termination": "completed", "artifacts": {},
    }
    result["result_address"] = evidence._address(result)
    monkeypatch.setattr(evidence, "run_step", lambda *_args, **_kwargs: result)
    assert evidence.preflight_command(_preflight_args(tmp_path)) == 1
    receipt = json.loads((tmp_path / "output/preflight.json").read_text())
    assert receipt["answer"]["status"] == "FAIL"
    assert receipt["answer"]["claims"]["highest_readiness_level"] == "none"
    assert receipt["answer"]["claims"]["release_deployable"] is False


def test_guard_interruption_writes_explicit_incomplete_receipt(tmp_path, monkeypatch):
    _patch_preflight(monkeypatch, tmp_path)
    result = {
        "label": "guard", "argv": ["$PYTHON"], "returncode": 130,
        "timeout_seconds": evidence.DEFAULT_STEP_TIMEOUT_SECONDS,
        "termination": "interrupted", "artifacts": {},
    }
    result["result_address"] = evidence._address(result)
    monkeypatch.setattr(
        evidence, "run_step",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(evidence.StepInterrupted(result)),
    )
    assert evidence.preflight_command(_preflight_args(tmp_path)) == 130
    receipt = json.loads((tmp_path / "output/preflight.json").read_text())
    assert receipt["answer"]["status"] == "INCOMPLETE"
    assert receipt["answer"]["attempted_step"] == "guard"
    assert receipt["answer"]["steps"] == []
    assert receipt["answer"]["attempted_result"] == result


def _artifact_record(path: Path, data: bytes) -> dict:
    path.write_bytes(data)
    return {"file": path.name, "bytes": len(data), "sha256": evidence._sha256_bytes(data)}


def _valid_preflight_receipt(tmp_path: Path):
    receipt_path = tmp_path / "receipt.json"
    artifacts = tmp_path / "receipt.artifacts"
    artifacts.mkdir()
    results = []
    for index, step in enumerate(evidence.preflight_steps()):
        stdout_name, stderr_name = evidence._artifact_names(index, step.label)
        result = {
            "label": step.label,
            "argv": list(step.argv),
            "returncode": 0,
            "timeout_seconds": evidence.DEFAULT_STEP_TIMEOUT_SECONDS,
            "termination": "completed",
            "artifacts": {
                "stdout": _artifact_record(artifacts / stdout_name, f"{step.label}: pass\n".encode()),
                "stderr": _artifact_record(artifacts / stderr_name, b""),
            },
        }
        result["result_address"] = evidence._address(result)
        results.append(result)
    answer = {
        "schema": evidence.ANSWER_SCHEMA,
        "kind": "preflight",
        "status": "PASS",
        "inventory": {},
        "steps": results,
        "attempted_step": evidence.preflight_steps()[-1].label,
        "attempted_result": None,
        "resource_policy": evidence._resource_policy(),
        "claims": evidence._claims("PASS"),
    }
    receipt = evidence._receipt(answer, "2026-08-29T00:00:00Z")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path, receipt


def _reseal(receipt: dict, path: Path) -> None:
    for result in receipt["answer"]["steps"]:
        body = {key: value for key, value in result.items() if key != "result_address"}
        result["result_address"] = evidence._address(body)
    receipt["answer_address"] = evidence._address(receipt["answer"])
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_review_forged_pass_and_each_semantic_escalation_are_refused(tmp_path, monkeypatch, capsys):
    path, original = _valid_preflight_receipt(tmp_path)
    monkeypatch.setattr(evidence, "_recompute_bound_files", lambda *_args: None)
    monkeypatch.setattr(evidence, "collect_inventory", lambda *_args: {})
    args = SimpleNamespace(
        checkout_root=str(tmp_path), frontend_root=str(tmp_path), receipt=str(path),
        require_signed=False,
    )
    assert evidence.verify_receipt_command(args) == 0
    capsys.readouterr()
    mutations = {
        "forged true argv": lambda value: value["answer"]["steps"][0].update(
            {"argv": ["/usr/bin/true"]}
        ),
        "timeout": lambda value: value["answer"]["steps"][0].update(
            {"timeout_seconds": 30}
        ),
        "attempted": lambda value: value["answer"].update(
            {"attempted_step": evidence.preflight_steps()[0].label}
        ),
        "resource": lambda value: value["answer"].update(
            {"resource_policy": {"fabricated": True}}
        ),
        "readiness": lambda value: value["answer"]["claims"].update(
            {"release_deployable": True, "v0_complete": True}
        ),
        "artifact digest": lambda value: value["answer"]["steps"][0]["artifacts"]["stdout"].update(
            {"sha256": "f" * 64}
        ),
    }
    for name, mutate in mutations.items():
        forged = copy.deepcopy(original)
        mutate(forged)
        _reseal(forged, path)
        with pytest.raises(evidence.EvidenceRefusal):
            evidence.verify_receipt_command(args)


def _child_is_gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def _wait_child_gone(pid: int) -> bool:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if _child_is_gone(pid):
            return True
        time.sleep(0.05)
    return _child_is_gone(pid)


def _run_fast_exit_overflow(tmp_path, monkeypatch, *, cap: int, iterations: int):
    monkeypatch.setattr(evidence, "DEFAULT_STEP_TIMEOUT_SECONDS", 3)
    monkeypatch.setattr(evidence, "MAX_STEP_OUTPUT_BYTES", cap)
    results = []
    for index in range(iterations):
        artifact_root = tmp_path / f"fast-exit-{cap}-{index}"
        artifact_root.mkdir()
        results.append(evidence.run_step(
            evidence.Step("fast-overflow", (
                "$PYTHON", "-c",
                f"import sys; sys.stdout.buffer.write(b'x'*{cap + 1}); sys.stdout.flush()",
            )),
            backend=_checkout() / "paper-trader/backend",
            env=evidence._safe_environment(tmp_path / f"env-{cap}-{index}"),
            timeout=3, artifact_root=artifact_root, step_index=0,
        ))
    return results


def test_reduced_cap_fast_exit_overflow_dominates_completed_result(tmp_path, monkeypatch):
    results = _run_fast_exit_overflow(tmp_path, monkeypatch, cap=4096, iterations=20)
    assert all(result["termination"] == "output_overflow" for result in results)
    assert all(result["returncode"] == 125 for result in results)
    assert all(
        sum(item["bytes"] for item in result["artifacts"].values()) == 4096
        for result in results
    )


def test_configured_cap_fast_exit_overflow_is_never_completed(tmp_path, monkeypatch):
    cap = evidence.MAX_STEP_OUTPUT_BYTES
    results = _run_fast_exit_overflow(tmp_path, monkeypatch, cap=cap, iterations=6)
    assert all(result["termination"] == "output_overflow" for result in results)
    assert all(result["returncode"] == 125 for result in results)
    assert all(
        sum(item["bytes"] for item in result["artifacts"].values()) == cap
        for result in results
    )


def test_post_exit_overflow_cleans_stubborn_descendant_without_signalling_unrelated_group(
    tmp_path, monkeypatch,
):
    unrelated_signal = tmp_path / "unrelated.signal"
    unrelated_ready = tmp_path / "unrelated.ready"
    unrelated = subprocess.Popen(
        [sys.executable, "-c", (
            "import pathlib,signal,sys,time;"
            "signal.signal(signal.SIGTERM,lambda *_:pathlib.Path(sys.argv[1]).write_text('TERM'));"
            "signal.signal(signal.SIGINT,lambda *_:pathlib.Path(sys.argv[1]).write_text('INT'));"
            "pathlib.Path(sys.argv[2]).write_text('ready');"
            "time.sleep(300)"
        ), str(unrelated_signal), str(unrelated_ready)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    helper = tmp_path / "post-exit-group.py"
    descendant_pid = tmp_path / "descendant.pid"
    helper.write_text(
        "import pathlib,subprocess,sys\n"
        "child=subprocess.Popen([sys.executable,'-c',"
        "'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(300)'],"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
        "sys.stdout.buffer.write(b'x'*4097); sys.stdout.flush()\n",
        encoding="utf-8",
    )
    try:
        deadline = time.monotonic() + 3
        while not unrelated_ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert unrelated_ready.exists()
        artifact_root = tmp_path / "post-exit-artifacts"
        artifact_root.mkdir()
        monkeypatch.setattr(evidence, "DEFAULT_STEP_TIMEOUT_SECONDS", 3)
        monkeypatch.setattr(evidence, "MAX_STEP_OUTPUT_BYTES", 4096)
        result = evidence.run_step(
            evidence.Step("post-exit-overflow", ("$PYTHON", str(helper), str(descendant_pid))),
            backend=_checkout() / "paper-trader/backend",
            env=evidence._safe_environment(tmp_path / "post-exit-env"),
            timeout=3, artifact_root=artifact_root, step_index=0,
        )
        assert result["termination"] == "output_overflow"
        assert result["returncode"] == 125
        assert _wait_child_gone(int(descendant_pid.read_text()))
        assert unrelated.poll() is None
        assert not unrelated_signal.exists()
    finally:
        if unrelated.poll() is None:
            os.killpg(unrelated.pid, signal.SIGKILL)
        unrelated.wait(timeout=3)


@pytest.mark.parametrize("mode,expected_code,expected_termination", [
    ("timeout", 124, "timeout"),
    ("overflow", 125, "output_overflow"),
    ("memory", 126, "memory_overflow"),
])
def test_timeout_and_overflow_kill_the_whole_child_group(
    tmp_path, monkeypatch, mode, expected_code, expected_termination,
):
    helper = tmp_path / "group.py"
    pid_file = tmp_path / "grandchild.pid"
    helper.write_text(
        "import pathlib,signal,subprocess,sys,time\n"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        "child=subprocess.Popen([sys.executable,'-c',"
        "'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(300)'])\n"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
        "sys.stdout.flush()\n"
        "if sys.argv[2]=='overflow':\n"
        "    sys.stdout.buffer.write(b'x'*1048576); sys.stdout.flush()\n"
        "if sys.argv[2]=='memory':\n"
        "    payload=bytearray(128*1024*1024)\n"
        "time.sleep(300)\n",
        encoding="utf-8",
    )
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    monkeypatch.setattr(evidence, "DEFAULT_STEP_TIMEOUT_SECONDS", 1)
    if mode == "overflow":
        monkeypatch.setattr(evidence, "MAX_STEP_OUTPUT_BYTES", 4096)
    if mode == "memory":
        monkeypatch.setattr(evidence, "MAX_CHILD_MEMORY_BYTES", 64 * 1024 * 1024)
    result = evidence.run_step(
        evidence.Step("group-guard", ("$PYTHON", str(helper), str(pid_file), mode)),
        backend=_checkout() / "paper-trader/backend", env=evidence._safe_environment(tmp_path),
        timeout=1, artifact_root=artifact_root, step_index=0,
    )
    assert result["returncode"] == expected_code
    assert result["termination"] == expected_termination
    assert sum(item["bytes"] for item in result["artifacts"].values()) <= evidence.MAX_STEP_OUTPUT_BYTES
    assert _wait_child_gone(int(pid_file.read_text()))


def test_child_memory_ceiling_policy_is_exact_and_supported():
    policy = evidence._resource_policy()
    assert policy["max_child_memory_bytes"] == 2 * 1024 * 1024 * 1024
    assert policy["memory_enforcement"] == (
        "live POSIX ps process-tree RSS ceiling with group termination"
    )


def test_output_normalisation_removes_only_host_noise():
    first = (
        b"2026-08-29 15:20:01.123 IST [12345] LOG port 54321 "
        b"127.0.0.1:54321 pt_harness_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa in 1.25s\n"
    )
    second = (
        b"2026-08-30 01:02:03.999 IST [98765] LOG port 61234 "
        b"127.0.0.1:61234 pt_harness_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb in 9.75s\n"
    )
    assert evidence._normalise_evidence_output(first, checkout=_checkout()) == evidence._normalise_evidence_output(
        second, checkout=_checkout()
    )


def test_guard_release_profile_and_no_execution_environment(tmp_path):
    env = evidence._safe_environment(tmp_path)
    assert env["PT_RELEASE_PROFILE"] == "v0_research_signal"
    assert env["PT_EXECUTION"] == "paper"
    assert env["PT_EXECUTION_PROVIDER"] == ""
    assert env["PT_EXECUTION_CONNECTION"] == ""
    assert env["PT_LIVE_ACK"] == ""


def test_guard_plane_separation(tmp_path):
    env = evidence._safe_environment(tmp_path)
    assert len({env["PT_DB_PATH"], env["PT_LEDGER_DB_PATH"], env["PT_RESEARCH_DB_PATH"]}) == 3


def test_guard_migration_head_is_bound():
    assert "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py" in evidence.REPOSITORY_FILES
    assert "paper-trader/backend/research/domain/migrations/__init__.py" in evidence.REPOSITORY_FILES


def test_six_genuine_isolated_mutations_kill_their_guard_without_setup_error(tmp_path):
    source = DEFAULT_SCRIPT.read_text(encoding="utf-8")
    cases = {
        "release": (
            '"PT_EXECUTION": "paper"', '"PT_EXECUTION": "live"',
            "test_guard_release_profile_and_no_execution_environment",
        ),
        "digest": (
            'receipt["answer_address"] != _address(receipt["answer"])',
            'receipt["answer_address"] == _address(receipt["answer"])',
            "test_guard_receipt_digest_accepts_exact_and_refuses_tamper",
        ),
        "planes": (
            'str(temp_root / "ledger.sqlite")', 'str(temp_root / "execution.sqlite")',
            "test_guard_plane_separation",
        ),
        "head": (
            'paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py',
            'paper-trader/backend/migrations/versions/20260829_0043_browser_auth.mutated',
            "test_guard_migration_head_is_bound",
        ),
        "interruption": (
            'status = "INCOMPLETE"', 'status = "PASS"',
            "test_guard_interruption_writes_explicit_incomplete_receipt",
        ),
        "post_join_overflow": (
            'if termination == "completed" and overflow.is_set():',
            'if False and termination == "completed" and overflow.is_set():',
            "test_reduced_cap_fast_exit_overflow_dominates_completed_result",
        ),
    }
    for name, (before, after, test_name) in cases.items():
        assert source.count(before) == 1, name
        mutant = tmp_path / f"{name}.py"
        mutant.write_text(source.replace(before, after, 1), encoding="utf-8")
        env = dict(os.environ, Q14_EVIDENCE_SCRIPT=str(mutant))
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", f"tests/test_v0_local_release_operations.py::{test_name}"],
            cwd=_checkout() / "paper-trader/backend", env=env, check=False,
            capture_output=True, text=True, timeout=90,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 1, (name, output)
        assert output.count("FAILED tests/test_v0_local_release_operations.py::") == 1, (name, output)
        assert "ERROR" not in output and "SKIPPED" not in output, (name, output)


def test_readiness_claims_are_permanently_bounded():
    passing = evidence._claims("PASS")
    assert passing["highest_readiness_level"] == "locally_runnable"
    assert all(passing[key] is False for key in (
        "release_deployable", "production_rehearsed", "deployed", "provider_approved",
        "legally_approved", "v0_complete",
    ))
