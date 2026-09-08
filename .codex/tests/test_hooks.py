from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
AGENT_GUARD = ROOT / ".codex" / "hooks" / "agent_guard.py"
COMPACTION_GUARD = ROOT / ".codex" / "hooks" / "compaction_guard.py"
PONYTAIL_GUARD = ROOT / ".codex" / "hooks" / "ponytail_review_guard.py"


def load_ponytail_guard():
    spec = importlib.util.spec_from_file_location("ponytail_review_guard", PONYTAIL_GUARD)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Ponytail guard")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capsule_text(assignments: list[dict], *, budget: int | None = None) -> str:
    metadata = {
        "id": "test-slice",
        "phase": "test",
        "status": "active",
        "goal": "Exercise the agent budget guard.",
        "risk_tags": ["routine"],
        "required_docs": [],
        "allowed_paths": ["src", "tests"],
        "nonclaims": ["No future-phase work."],
        "owner_gates": [],
        "stop_conditions": ["Stop on undeclared scope."],
        "model_route": {"owner": "gpt-5.6-terra", "reasoning_effort": "medium"},
        "parallel_budget": len(assignments) if budget is None else budget,
        "assignments": assignments,
        "acceptance": ["The guard enforces the capsule."],
        "test_plan": ["Run the hook unit tests."],
        "review": {
            "required": True,
            "assignment_id": "critical-review",
            "agent": "critical-reviewer",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "high",
            "package": ".agent/review-package.json",
            "base_sha": "HEAD",
            "review_paths": [],
            "exclude_paths": [],
        },
    }
    return f"---\n{json.dumps(metadata, indent=2)}\n---\n\n# Test capsule\n"


def assignment(
    identifier: str,
    write_path: str,
    *,
    agent: str = "terra-worker",
    reasoning_effort: str = "medium",
    escalation_reason: str = "",
) -> dict:
    return {
        "id": identifier,
        "agent": agent,
        "mode": "write",
        "depends_on": [],
        "read_paths": [write_path],
        "write_paths": [write_path],
        "output": f".agent/runs/test-slice/{identifier}/report.md",
        "reasoning_effort": reasoning_effort,
        "escalation_reason": escalation_reason,
    }


class HookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.state = self.base / "state"
        self.state.mkdir()
        self.capsule = self.base / "capsule.md"

    def run_hook(
        self,
        script: Path,
        payload: dict,
        *,
        repo: Path | None = None,
        capsule_override: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update({
            "STRATEGY_OS_AGENT_STATE_DIR": str(self.state),
            "STRATEGY_OS_REPO_ROOT": str(repo or ROOT),
        })
        if capsule_override:
            env["STRATEGY_OS_CAPSULE_PATH"] = str(self.capsule)
        else:
            env.pop("STRATEGY_OS_CAPSULE_PATH", None)
        return subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    @staticmethod
    def agent_payload(
        task_name: str,
        *,
        session: str = "session-one",
        fork_turns: str = "none",
        model: str = "gpt-5.6-terra",
        reasoning_effort: str = "medium",
        agent_type: str | None = "terra-worker",
    ) -> dict:
        tool_input = {
            "task_name": task_name,
            "fork_turns": fork_turns,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "message": "Read the declared capsule assignment and execute only that scope.",
        }
        if agent_type is not None:
            tool_input["agent_type"] = agent_type
        return {
            "session_id": session,
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "tool_input": tool_input,
        }

    def assert_denied(self, result: subprocess.CompletedProcess[str], phrase: str) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        decision = body["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn(phrase.lower(), decision["permissionDecisionReason"].lower())


class PonytailReviewGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guard = load_ponytail_guard()

    def test_commit_diff_contains_only_staged_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            path = repo / "sample.txt"
            path.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "sample.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            path.write_text("staged\n", encoding="utf-8")
            subprocess.run(["git", "add", "sample.txt"], cwd=repo, check=True)
            path.write_text("unstaged\n", encoding="utf-8")

            diff, scope = self.guard.commit_diff(repo)

            self.assertIn(b"+staged", diff)
            self.assertNotIn(b"unstaged", diff)
            self.assertIn("staged changes", scope)

    def test_review_runner_uses_ephemeral_read_only_codex_and_reads_result(self) -> None:
        def fake_runner(command, **kwargs):
            result_path = Path(command[command.index("-o") + 1])
            result_path.write_text(self.guard.LEAN, encoding="utf-8")
            self.assertIn("--ephemeral", command)
            self.assertIn("read-only", command)
            self.assertIn(b"diff", kwargs["input"])
            return subprocess.CompletedProcess(command, 0, b"", b"")

        with (
            mock.patch.object(self.guard, "codex_path", return_value="/bin/echo"),
            mock.patch.object(self.guard.subprocess, "run", side_effect=fake_runner),
        ):
            review = self.guard.run_review(b"diff", "test scope")

        self.assertEqual(review, self.guard.LEAN)

    def test_native_git_hooks_call_the_shared_guard(self) -> None:
        for name, action in (("pre-commit", "commit"), ("pre-push", "push")):
            hook = ROOT / ".githooks" / name
            self.assertTrue(hook.is_file())
            content = hook.read_text(encoding="utf-8")
            self.assertIn("ponytail_review_guard.py", content)
            self.assertIn(action, content)

    def test_git_hooks_skip_ai_review_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_git = Path(directory) / "git"
            fake_git.write_text('#!/bin/sh\n[ "$*" = "diff --cached --check" ]\n')
            fake_git.chmod(0o755)
            for name in ("pre-commit", "pre-push"):
                result = subprocess.run(
                    ["/bin/sh", str(ROOT / ".githooks" / name)],
                    env={"PATH": directory}, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_finding_denies_commit_before_git_runs(self) -> None:
        with (
            mock.patch.object(self.guard.sys, "argv", [str(PONYTAIL_GUARD), "commit"]),
            mock.patch.object(self.guard, "git_root", return_value=ROOT),
            mock.patch.object(self.guard, "commit_diff", return_value=(b"diff", "staged changes")),
            mock.patch.object(self.guard, "run_review", return_value="L1: shrink: extra layer. Inline it.\nnet: -3 lines possible."),
        ):
            self.assertEqual(self.guard.main(), 1)


class AgentGuardTests(HookTestCase):
    def test_script_exists(self) -> None:
        self.assertTrue(AGENT_GUARD.is_file(), f"missing {AGENT_GUARD}")

    def test_discovers_active_capsule_when_environment_is_absent(self) -> None:
        repo = self.base / "repo"
        capsule = repo / "paper-trader" / "docs" / "agent" / "capsules" / "slice.md"
        capsule.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        current = repo / "paper-trader" / "docs" / "agent" / "CURRENT.md"
        current.write_text("---\n" + json.dumps({"active_capsule": "paper-trader/docs/agent/capsules/slice.md"}) + "\n---\n")
        env = os.environ.copy()
        env.pop("STRATEGY_OS_CAPSULE_PATH", None)
        env.pop("STRATEGY_OS_REPO_ROOT", None)
        env["STRATEGY_OS_AGENT_STATE_DIR"] = str(self.state)
        result = subprocess.run([sys.executable, str(AGENT_GUARD)], input=json.dumps(self.agent_payload("worker-1")), text=True, capture_output=True, env=env, cwd=repo, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_implicit_historical_capsule_does_not_veto_direct_assignment(self) -> None:
        repo = self.base / "repo"
        capsule = repo / "paper-trader" / "docs" / "agent" / "capsules" / "slice.md"
        capsule.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        capsule.write_text(capsule_text([assignment("capsule-worker", "src/one")]))
        self.capsule.write_text(capsule.read_text())
        current = repo / "paper-trader" / "docs" / "agent" / "CURRENT.md"
        current.write_text("---\n" + json.dumps({"active_capsule": "paper-trader/docs/agent/capsules/slice.md"}) + "\n---\n")

        direct = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("direct-parent-workstream"),
            repo=repo,
            capsule_override=False,
        )
        explicit = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("direct-parent-workstream", session="explicit"),
            repo=repo,
        )

        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertEqual(direct.stdout, "")
        self.assert_denied(explicit, "assignment is not declared in capsule")

        capsule.unlink()
        missing = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("direct-parent-workstream", session="missing"),
            repo=repo,
            capsule_override=False,
        )
        current.write_text("invalid current metadata")
        malformed = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("direct-parent-workstream", session="malformed"),
            repo=repo,
            capsule_override=False,
        )
        self.capsule.unlink()
        explicit_missing = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("direct-parent-workstream", session="explicit-missing"),
            repo=repo,
        )

        self.assertEqual(missing.stdout, "", missing.stderr)
        self.assertEqual(malformed.stdout, "", malformed.stderr)
        self.assert_denied(explicit_missing, "invalid capsule")

    def test_allows_five_declared_clean_workers_and_rejects_a_sixth(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        assignments = [assignment(f"worker-{index}", f"src/part-{index}") for index in range(1, 7)]
        self.capsule.write_text(capsule_text(assignments, budget=5))

        for index in range(1, 6):
            result = self.run_hook(AGENT_GUARD, self.agent_payload(f"worker-{index}"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")

        result = self.run_hook(AGENT_GUARD, self.agent_payload("worker-6"))
        self.assert_denied(result, "parallel budget")

    def test_accepts_native_spawn_aliases_and_rejects_duplicate_ids_or_invalid_budget(self) -> None:
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        payload = self.agent_payload("worker-1")
        payload["tool_name"] = "collaborationspawn_agent"
        self.assertEqual(self.run_hook(AGENT_GUARD, payload).stdout, "")
        duplicate = capsule_text([assignment("worker-1", "src/one"), assignment("worker-1", "src/two")])
        self.capsule.write_text(duplicate)
        self.assert_denied(self.run_hook(AGENT_GUARD, self.agent_payload("worker-1", session="duplicate")), "duplicate")
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")], budget=6))
        self.assert_denied(self.run_hook(AGENT_GUARD, self.agent_payload("worker-1", session="budget")), "parallel budget")

    def test_spawn_agent_with_hidden_route_fields_is_rewritten_to_declared_route(self) -> None:
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        payload = self.agent_payload("worker-1", agent_type=None)
        payload["tool_name"] = "collaborationspawn_agent"
        payload["tool_input"].pop("model")
        payload["tool_input"].pop("reasoning_effort")
        result = self.run_hook(AGENT_GUARD, payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")
        self.assertEqual(output["updatedInput"]["agent_type"], "terra-worker")
        self.assertEqual(output["updatedInput"]["model"], "gpt-5.6-terra")
        self.assertEqual(output["updatedInput"]["reasoning_effort"], "medium")
        self.assertEqual(output["updatedInput"]["fork_turns"], "none")

    def test_optional_native_trace_records_route_without_copying_prompt(self) -> None:
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        trace = ROOT / ".agent" / "test-hook-trace.jsonl"
        self.addCleanup(lambda: trace.unlink(missing_ok=True))
        payload = self.agent_payload("worker-1")
        payload["tool_name"] = "collaborationspawn_agent"
        payload["tool_input"]["message"] = "SENSITIVE PROMPT TEXT"
        env = os.environ.copy()
        env.update(
            {
                "STRATEGY_OS_CAPSULE_PATH": str(self.capsule),
                "STRATEGY_OS_AGENT_STATE_DIR": str(self.state),
                "STRATEGY_OS_REPO_ROOT": str(ROOT),
                "STRATEGY_OS_HOOK_TRACE": str(trace),
            }
        )
        result = subprocess.run(
            [sys.executable, str(AGENT_GUARD)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(trace.read_text())
        self.assertEqual(record["task_name"], "worker-1")
        self.assertEqual(record["tool_name"], "collaborationspawn_agent")
        self.assertIn("message", record["tool_input_keys"])
        self.assertNotIn("SENSITIVE", trace.read_text())

    def test_rejects_duplicate_assignment(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        first = self.run_hook(AGENT_GUARD, self.agent_payload("worker-1"))
        self.assertEqual(first.stdout, "")
        second = self.run_hook(AGENT_GUARD, self.agent_payload("worker-1"))
        self.assert_denied(second, "already dispatched")

    def test_malformed_state_fails_closed(self) -> None:
        assignments = [assignment("worker-1", "src/one"), assignment("worker-2", "src/two")]
        self.capsule.write_text(capsule_text(assignments))
        self.assertEqual(self.run_hook(AGENT_GUARD, self.agent_payload("worker-1")).stdout, "")
        state_files = list(self.state.glob("*.json"))
        self.assertEqual(len(state_files), 1)
        state_files[0].write_text("not-json")
        result = self.run_hook(AGENT_GUARD, self.agent_payload("worker-2"))
        self.assert_denied(result, "state")

    def test_parallel_launches_cannot_race_past_budget(self) -> None:
        assignments = [assignment(f"worker-{index}", f"src/{index}") for index in range(10)]
        self.capsule.write_text(capsule_text(assignments, budget=1))
        env = os.environ.copy()
        env.update(
            {
                "STRATEGY_OS_CAPSULE_PATH": str(self.capsule),
                "STRATEGY_OS_AGENT_STATE_DIR": str(self.state),
                "STRATEGY_OS_REPO_ROOT": str(ROOT),
            }
        )
        processes: list[subprocess.Popen[str]] = []
        for index in range(10):
            process = subprocess.Popen(
                [sys.executable, str(AGENT_GUARD)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            processes.append(process)
        time.sleep(0.05)
        outputs = []
        for index, process in enumerate(processes):
            stdout, stderr = process.communicate(json.dumps(self.agent_payload(f"worker-{index}")), timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            outputs.append(stdout)
        self.assertEqual(sum(not output for output in outputs), 1)
        self.assertEqual(sum("parallel budget" in output.lower() for output in outputs), 9)

    def test_rejects_overlapping_write_ownership(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        assignments = [
            assignment("worker-1", "src/shared"),
            assignment("worker-2", "src/shared/child.py"),
        ]
        self.capsule.write_text(capsule_text(assignments))
        result = self.run_hook(AGENT_GUARD, self.agent_payload("worker-1"))
        self.assert_denied(result, "overlapping write ownership")

    def test_rejects_assignment_until_dependency_report_exists(self) -> None:
        first = assignment("worker-1", "src/one")
        second = assignment("worker-2", "src/two")
        second["depends_on"] = ["worker-1"]
        first["output"] = ".agent/runs/test-slice/worker-1/report.md"
        self.capsule.write_text(capsule_text([first, second]))
        blocked = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("worker-2", session="dependency"),
            repo=self.base,
        )
        self.assert_denied(blocked, "dependency report")
        report = self.base / first["output"]
        report.parent.mkdir(parents=True)
        report.write_text("complete\n")
        allowed = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("worker-2", session="dependency"),
            repo=self.base,
        )
        self.assertEqual(allowed.stdout, "", allowed.stderr)

    def test_rejects_full_history_fork(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        result = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("worker-1", fork_turns="all"),
        )
        self.assert_denied(result, "fork_turns")

    def test_requires_clean_fork_and_declared_agent_route(self) -> None:
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        invalid_fork = self.run_hook(AGENT_GUARD, self.agent_payload("worker-1", fork_turns="2"))
        self.assert_denied(invalid_fork, "fork_turns")
        wrong_type = self.run_hook(AGENT_GUARD, self.agent_payload("worker-1", session="type", agent_type="other"))
        self.assert_denied(wrong_type, "agent type")
        wrong_model = self.run_hook(AGENT_GUARD, self.agent_payload("worker-1", session="model", model="gpt-5.6-sol"))
        self.assert_denied(wrong_model, "model")

    def test_rejects_undeclared_high_and_all_xhigh_or_max_effort(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        self.capsule.write_text(capsule_text([assignment("worker-1", "src/one")]))
        high = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("worker-1", reasoning_effort="high"),
        )
        self.assert_denied(high, "high reasoning")

        for effort in ("xhigh", "ultra", "max"):
            self.state.mkdir(exist_ok=True)
            result = self.run_hook(
                AGENT_GUARD,
                self.agent_payload("worker-1", session=f"session-{effort}", reasoning_effort=effort),
            )
            self.assert_denied(result, effort)

    def test_allows_declared_high_effort_escalation(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        self.capsule.write_text(
            capsule_text(
                [
                    assignment(
                        "worker-1",
                        "src/one",
                        reasoning_effort="high",
                        escalation_reason="Terra medium failed the recorded reproduction twice.",
                    )
                ]
            )
        )
        result = self.run_hook(
            AGENT_GUARD,
            self.agent_payload("worker-1", reasoning_effort="high"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_rejects_reviewer_before_package_exists(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        self.capsule.write_text(capsule_text([]))
        payload = self.agent_payload(
            "critical-review",
            model="gpt-5.6-sol",
            reasoning_effort="high",
            agent_type="critical-reviewer",
        )
        result = self.run_hook(AGENT_GUARD, payload, repo=self.base)
        self.assert_denied(result, "review package")

    def test_rejects_reviewer_with_stale_fingerprint(self) -> None:
        if not AGENT_GUARD.exists():
            self.skipTest("agent guard not implemented")
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "file.txt").write_text("base\n")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        (repo / "file.txt").write_text("changed\n")
        evidence = repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        package = repo / ".agent" / "review-package.json"
        package.parent.mkdir(exist_ok=True)
        package.write_text(
            json.dumps(
                {
                    "task_id": "test-slice",
                    "base_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
                    "dirty_tree_fingerprint": "stale",
                    "scope_prefixes": [],
                    "excluded_paths": [],
                    "changed_paths": ["file.txt"],
                    "acceptance_status": "focused-tests-pass",
                    "evidence_logs": [".agent/evidence.log"],
                    "evidence_sha256": {".agent/evidence.log": hashlib.sha256(evidence.read_bytes()).hexdigest()},
                    "open_findings": [],
                    "owner_gates": [],
                }
            )
        )
        metadata = json.loads(capsule_text([]).split("---")[1])
        metadata["review"]["package"] = ".agent/review-package.json"
        self.capsule.write_text(f"---\n{json.dumps(metadata)}\n---\n")
        payload = self.agent_payload(
            "critical-review",
            model="gpt-5.6-sol",
            reasoning_effort="high",
            agent_type="critical-reviewer",
        )
        result = self.run_hook(AGENT_GUARD, payload, repo=repo)
        self.assert_denied(result, "fingerprint")

    def test_allows_generator_package_at_declared_non_agent_path(self) -> None:
        generator = ROOT / ".codex" / "scripts" / "make_review_package.py"
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "file.txt").write_text("base\n")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        (repo / "file.txt").write_text("changed\n")
        evidence = repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        package = repo / ".review" / "critical.json"
        result = subprocess.run([sys.executable, str(generator), "--repo", str(repo), "--task-id", "test-slice", "--base", "HEAD", "--acceptance-status", "pass", "--evidence", ".agent/evidence.log", "--output", str(package)], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(capsule_text([]).split("---")[1])
        metadata["review"]["package"] = ".review/critical.json"
        self.capsule.write_text(f"---\n{json.dumps(metadata)}\n---\n")
        payload = self.agent_payload("critical-review", model="gpt-5.6-sol", reasoning_effort="high", agent_type="critical-reviewer")
        reviewed = self.run_hook(AGENT_GUARD, payload, repo=repo)
        self.assertEqual(reviewed.stdout, "", reviewed.stderr)

    def test_reviewer_requires_exact_route_matching_task_paths_and_evidence(self) -> None:
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "file.txt").write_text("changed\n")
        package = repo / ".review.json"
        package.write_text(json.dumps({"task_id": "wrong", "dirty_tree_fingerprint": "", "changed_paths": [], "evidence_logs": ["missing.log"]}))
        self.capsule.write_text(capsule_text([]))
        bad = self.run_hook(AGENT_GUARD, self.agent_payload("critical-review", model="gpt-5.6-terra", reasoning_effort="medium", agent_type="terra-worker"), repo=repo)
        self.assert_denied(bad, "agent type")

    def test_reviewer_rejects_paths_outside_declared_review_scope(self) -> None:
        generator = ROOT / ".codex" / "scripts" / "make_review_package.py"
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "outside.txt").write_text("base\n")
        subprocess.run(["git", "add", "outside.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        (repo / "outside.txt").write_text("changed\n")
        evidence = repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        package = repo / ".agent" / "review-package.json"
        subprocess.run(
            [sys.executable, str(generator), "--repo", str(repo), "--task-id", "test-slice", "--base", "HEAD", "--acceptance-status", "pass", "--evidence", ".agent/evidence.log", "--output", str(package)],
            check=True,
        )
        metadata = json.loads(capsule_text([]).split("---")[1])
        metadata["review"]["review_paths"] = ["scoped"]
        self.capsule.write_text(f"---\n{json.dumps(metadata)}\n---\n")
        payload = self.agent_payload("critical-review", model="gpt-5.6-sol", reasoning_effort="high", agent_type="critical-reviewer")
        self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), "scope")

    def test_commit_bound_reviewer_accepts_exact_package_and_rejects_tampering(self) -> None:
        generator = ROOT / ".codex" / "scripts" / "make_review_package.py"
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "file.txt").write_text("base\n")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        (repo / "file.txt").write_text("changed\n")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "head"], cwd=repo, check=True)
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        evidence = repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        package = repo / ".agent" / "review-package.json"

        def generate() -> None:
            subprocess.run(
                [
                    sys.executable,
                    str(generator),
                    "--repo",
                    str(repo),
                    "--task-id",
                    "test-slice",
                    "--base",
                    base_sha,
                    "--head",
                    head_sha,
                    "--acceptance-status",
                    "pass",
                    "--evidence",
                    ".agent/evidence.log",
                    "--output",
                    str(package),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )

        metadata = json.loads(capsule_text([]).split("---")[1])
        metadata["review"]["base_sha"] = base_sha
        self.capsule.write_text(f"---\n{json.dumps(metadata)}\n---\n")
        payload = self.agent_payload(
            "critical-review",
            model="gpt-5.6-sol",
            reasoning_effort="high",
            agent_type="critical-reviewer",
        )

        generate()
        exact = self.run_hook(AGENT_GUARD, payload, repo=repo)
        self.assertEqual(exact.stdout, "", exact.stderr)

        for field, value, message in (
            ("changed_paths", [], "declared review scope"),
            ("complete_changed_paths", [], "complete paths"),
            ("commit_diff_sha256", "0" * 64, "diff digest"),
        ):
            generate()
            tampered = json.loads(package.read_text())
            tampered[field] = value
            package.write_text(json.dumps(tampered))
            payload["session_id"] = f"tampered-{field}"
            self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), message)

        generate()
        (repo / "file.txt").write_text("dirty after package\n")
        payload["session_id"] = "dirty-tracked"
        self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), "clean tracked")
        subprocess.run(["git", "restore", "file.txt"], cwd=repo, check=True)

        generate()
        (repo / "later.txt").write_text("later\n")
        subprocess.run(["git", "add", "later.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "later"], cwd=repo, check=True)
        payload["session_id"] = "stale-head"
        self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), "reviewed head")

    def test_current_routes_exact_orchestration_review_capsule_through_native_guard(self) -> None:
        generator = ROOT / ".codex" / "scripts" / "make_review_package.py"
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "file.txt").write_text("base\n")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        (repo / "file.txt").write_text("changed\n")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "head"], cwd=repo, check=True)
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        evidence = repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        package = repo / ".agent" / "review-package.json"
        subprocess.run(
            [
                sys.executable,
                str(generator),
                "--repo",
                str(repo),
                "--task-id",
                "v1-goal-orchestration",
                "--base",
                base_sha,
                "--head",
                head_sha,
                "--acceptance-status",
                "pass",
                "--evidence",
                ".agent/evidence.log",
                "--output",
                str(package),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        task_root = repo / "paper-trader" / "docs" / "agent" / "tasks"
        task_root.mkdir(parents=True)
        route = task_root / "v1-goal-orchestration.md"
        metadata = json.loads(capsule_text([]).split("---")[1])
        metadata["id"] = "v1-goal-orchestration"
        metadata["review"].update({
            "assignment_id": "v1_goal_orchestration_critical_review",
            "base_sha": base_sha,
        })
        route.write_text(f"---\n{json.dumps(metadata)}\n---\n")
        current = repo / "paper-trader" / "docs" / "agent" / "CURRENT.md"
        current.write_text(
            "---\n"
            + json.dumps({
                "active_capsule": "paper-trader/docs/agent/tasks/missing.md",
                "review_capsules": {
                    "v1_goal_orchestration_critical_review": "paper-trader/docs/agent/tasks/v1-goal-orchestration.md"
                },
            })
            + "\n---\n"
        )
        payload = self.agent_payload(
            "v1_goal_orchestration_critical_review",
            model="gpt-5.6-sol",
            reasoning_effort="high",
            agent_type="critical-reviewer",
        )
        result = self.run_hook(
            AGENT_GUARD,
            payload,
            repo=repo,
            capsule_override=False,
        )
        self.assertEqual(result.stdout, "", result.stderr)

    def test_reviewer_is_limited_to_initial_review_plus_one_recheck(self) -> None:
        generator = ROOT / ".codex" / "scripts" / "make_review_package.py"
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "file.txt").write_text("base\n")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        (repo / "file.txt").write_text("changed\n")
        evidence = repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        package = repo / ".agent" / "review-package.json"
        subprocess.run(
            [sys.executable, str(generator), "--repo", str(repo), "--task-id", "test-slice", "--base", "HEAD", "--acceptance-status", "pass", "--evidence", ".agent/evidence.log", "--output", str(package)],
            stdout=subprocess.DEVNULL,
            check=True,
        )
        self.capsule.write_text(capsule_text([]))
        payload = self.agent_payload("critical-review", model="gpt-5.6-sol", reasoning_effort="high", agent_type="critical-reviewer")
        self.assertEqual(self.run_hook(AGENT_GUARD, payload, repo=repo).stdout, "")
        payload["session_id"] = "another-session"
        self.assertEqual(self.run_hook(AGENT_GUARD, payload, repo=repo).stdout, "")
        payload["session_id"] = "third-session"
        self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), "initial review plus one recheck")

    def test_reviewer_binds_base_scope_and_evidence_digest(self) -> None:
        generator = ROOT / ".codex" / "scripts" / "make_review_package.py"
        repo = self.base / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "scoped").mkdir()
        (repo / "scoped" / "file.txt").write_text("base\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        (repo / "scoped" / "file.txt").write_text("changed\n")
        evidence = repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        package = repo / ".agent" / "review-package.json"
        command = [
            sys.executable,
            str(generator),
            "--repo",
            str(repo),
            "--task-id",
            "test-slice",
            "--base",
            "HEAD",
            "--acceptance-status",
            "pass",
            "--evidence",
            ".agent/evidence.log",
            "--include",
            "scoped",
            "--output",
            str(package),
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        metadata = json.loads(capsule_text([]).split("---")[1])
        metadata["review"]["review_paths"] = ["scoped"]
        self.capsule.write_text(f"---\n{json.dumps(metadata)}\n---\n")
        payload = self.agent_payload("critical-review", model="gpt-5.6-sol", reasoning_effort="high", agent_type="critical-reviewer")

        tampered = json.loads(package.read_text())
        tampered["changed_paths"] = []
        package.write_text(json.dumps(tampered))
        self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), "changed paths")

        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        tampered = json.loads(package.read_text())
        tampered["base_sha"] = "0" * 40
        package.write_text(json.dumps(tampered))
        self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), "base sha")

        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        evidence.write_text("changed after packaging\n")
        self.assert_denied(self.run_hook(AGENT_GUARD, payload, repo=repo), "evidence digest")


class CompactionGuardTests(HookTestCase):
    def test_script_exists(self) -> None:
        self.assertTrue(COMPACTION_GUARD.is_file(), f"missing {COMPACTION_GUARD}")

    def test_repeated_auto_compaction_allows_work_without_state(self) -> None:
        if not COMPACTION_GUARD.exists():
            self.skipTest("compaction guard not implemented")
        payload = {
            "session_id": "compact-session",
            "hook_event_name": "PreCompact",
            "trigger": "auto",
        }
        first = self.run_hook(COMPACTION_GUARD, payload)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_hook(COMPACTION_GUARD, payload)
        for result in (first, second):
            body = json.loads(result.stdout)
            self.assertTrue(body["continue"])
            self.assertIn("working-plan", body["systemMessage"].lower())
            self.assertIn("actual state", body["systemMessage"].lower())
        self.assertEqual(list(self.state.iterdir()), [])

    def test_manual_compaction_does_not_consume_auto_budget(self) -> None:
        if not COMPACTION_GUARD.exists():
            self.skipTest("compaction guard not implemented")
        manual = {
            "session_id": "manual-session",
            "hook_event_name": "PreCompact",
            "trigger": "manual",
        }
        automatic = dict(manual, trigger="auto")
        manual_result = self.run_hook(COMPACTION_GUARD, manual)
        self.assertEqual(manual_result.stdout, "")
        first_auto = self.run_hook(COMPACTION_GUARD, automatic)
        self.assertTrue(json.loads(first_auto.stdout)["continue"])

    def test_malformed_payload_is_a_no_op(self) -> None:
        for payload in ("not json", "[]"):
            result = subprocess.run(
                [sys.executable, str(COMPACTION_GUARD)],
                input=payload,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
