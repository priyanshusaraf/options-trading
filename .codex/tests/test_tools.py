from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_LOGGED = ROOT / ".codex" / "scripts" / "run_logged.py"
MAKE_REVIEW_PACKAGE = ROOT / ".codex" / "scripts" / "make_review_package.py"
SESSION_AUDIT = ROOT / ".codex" / "scripts" / "session_audit.py"
VALIDATOR = ROOT / ".codex" / "scripts" / "validate_agent_architecture.py"
PROMPT_AUDIT = ROOT / ".codex" / "scripts" / "prompt_input_audit.py"
PROGRAMME_DISPATCHER = ROOT / ".codex" / "scripts" / "programme_dispatcher.py"


class ScriptPresenceTests(unittest.TestCase):
    def test_required_scripts_exist(self) -> None:
        for script in (
            RUN_LOGGED,
            MAKE_REVIEW_PACKAGE,
            SESSION_AUDIT,
            VALIDATOR,
            PROMPT_AUDIT,
            PROGRAMME_DISPATCHER,
        ):
            with self.subTest(script=script.name):
                self.assertTrue(script.is_file(), f"missing {script}")


class LoggedRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not RUN_LOGGED.exists():
            self.skipTest("logged runner not implemented")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)

    def run_logged(self, *command: str, label: str = "probe") -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["STRATEGY_OS_RUN_ROOT"] = str(self.base / "runs")
        return subprocess.run(
            [
                sys.executable,
                str(RUN_LOGGED),
                "--task",
                "test-slice",
                "--assignment",
                "owner",
                "--label",
                label,
                "--cwd",
                str(self.base),
                "--",
                *command,
            ],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_success_writes_full_log_and_prints_compact_json(self) -> None:
        result = self.run_logged("/bin/sh", "-c", "printf alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["exit_code"], 0)
        self.assertNotIn("alpha", result.stdout)
        log = Path(summary["log"])
        self.assertEqual(log.read_text(), "alpha")

    def test_failure_preserves_exit_code_and_reports_tail_on_stderr(self) -> None:
        result = self.run_logged("/bin/sh", "-c", "printf boom >&2; exit 7")
        self.assertEqual(result.returncode, 7)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["exit_code"], 7)
        self.assertIn("boom", result.stderr)
        self.assertIn("boom", Path(summary["log"]).read_text())

    def test_rejects_unsafe_path_components(self) -> None:
        result = self.run_logged("/bin/true", label="../escape")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("safe", result.stderr.lower())

    def test_default_log_root_is_repository_root_even_from_a_subdirectory(self) -> None:
        repo = self.base / "repo"
        subdir = repo / "paper-trader" / "backend"
        subdir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        env = os.environ.copy()
        env.pop("STRATEGY_OS_RUN_ROOT", None)
        result = subprocess.run(
            [
                sys.executable,
                str(RUN_LOGGED),
                "--task",
                "test-slice",
                "--assignment",
                "owner",
                "--label",
                "probe",
                "--cwd",
                str(subdir),
                "--",
                "/usr/bin/true",
            ],
            cwd=subdir,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        log = Path(json.loads(result.stdout)["log"])
        self.assertEqual(log, repo.resolve() / ".agent" / "runs" / "test-slice" / "owner" / "probe.log")


class ReviewPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MAKE_REVIEW_PACKAGE.exists():
            self.skipTest("review package generator not implemented")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.repo = Path(self.tempdir.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        (self.repo / "tracked.txt").write_text("base\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.repo, check=True)
        self.base_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True
        ).strip()

    def test_package_covers_tracked_and_untracked_dirty_state(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n")
        (self.repo / "new.txt").write_text("new\n")
        evidence = self.repo / ".agent" / "runs" / "test" / "focused.log"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("1 passed\n")
        output = self.repo / ".agent" / "review-package.json"
        result = subprocess.run(
            [
                sys.executable,
                str(MAKE_REVIEW_PACKAGE),
                "--repo",
                str(self.repo),
                "--task-id",
                "test-slice",
                "--base",
                self.base_sha,
                "--acceptance-status",
                "focused-tests-pass",
                "--evidence",
                str(evidence.relative_to(self.repo)),
                "--owner-gate",
                "none crossed",
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        package = json.loads(output.read_text())
        self.assertEqual(package["task_id"], "test-slice")
        self.assertEqual(package["base_sha"], self.base_sha)
        self.assertEqual(package["changed_paths"], ["new.txt", "tracked.txt"])
        self.assertRegex(package["dirty_tree_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(package["acceptance_status"], "focused-tests-pass")
        self.assertEqual(package["evidence_logs"], [str(evidence.relative_to(self.repo))])
        self.assertEqual(
            package["evidence_sha256"],
            {str(evidence.relative_to(self.repo)): hashlib.sha256(evidence.read_bytes()).hexdigest()},
        )
        self.assertEqual(package["scope_prefixes"], [])
        self.assertEqual(package["excluded_paths"], [])

    def test_package_fingerprint_excludes_its_declared_location(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n")
        output = self.repo / ".review" / "critical.json"
        result = subprocess.run(
            [sys.executable, str(MAKE_REVIEW_PACKAGE), "--repo", str(self.repo), "--task-id", "test-slice", "--base", self.base_sha, "--acceptance-status", "pass", "--output", str(output)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(json.loads(output.read_text())["dirty_tree_fingerprint"], r"^[0-9a-f]{64}$")

    def test_package_can_limit_changed_paths_without_weakening_full_tree_fingerprint(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n")
        scoped = self.repo / "scoped"
        scoped.mkdir()
        (scoped / "new.txt").write_text("new\n")
        evidence = self.repo / ".agent" / "evidence.log"
        evidence.parent.mkdir()
        evidence.write_text("pass\n")
        output = self.repo / ".agent" / "review-package.json"
        result = subprocess.run(
            [
                sys.executable,
                str(MAKE_REVIEW_PACKAGE),
                "--repo",
                str(self.repo),
                "--task-id",
                "test-slice",
                "--base",
                self.base_sha,
                "--acceptance-status",
                "pass",
                "--evidence",
                str(evidence.relative_to(self.repo)),
                "--include",
                "scoped",
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        package = json.loads(output.read_text())
        self.assertEqual(package["changed_paths"], ["scoped/new.txt"])
        self.assertEqual(package["scope_prefixes"], ["scoped"])
        self.assertRegex(package["dirty_tree_fingerprint"], r"^[0-9a-f]{64}$")

    def test_package_records_exclusions_and_rejects_escaping_evidence(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n")
        scoped = self.repo / "scoped"
        scoped.mkdir()
        (scoped / "keep.txt").write_text("keep\n")
        (scoped / "future.txt").write_text("future\n")
        output = self.repo / ".agent" / "review-package.json"
        outside = self.repo.parent / "outside.log"
        outside.write_text("escape\n")
        result = subprocess.run(
            [
                sys.executable,
                str(MAKE_REVIEW_PACKAGE),
                "--repo",
                str(self.repo),
                "--task-id",
                "test-slice",
                "--base",
                self.base_sha,
                "--acceptance-status",
                "pass",
                "--include",
                "scoped",
                "--exclude",
                "scoped/future.txt",
                "--evidence",
                "../outside.log",
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence", result.stderr.lower())

        evidence = self.repo / ".agent" / "evidence.log"
        evidence.parent.mkdir(exist_ok=True)
        evidence.write_text("pass\n")
        result = subprocess.run(
            [
                sys.executable,
                str(MAKE_REVIEW_PACKAGE),
                "--repo",
                str(self.repo),
                "--task-id",
                "test-slice",
                "--base",
                self.base_sha,
                "--acceptance-status",
                "pass",
                "--include",
                "scoped",
                "--exclude",
                "scoped/future.txt",
                "--evidence",
                ".agent/evidence.log",
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        package = json.loads(output.read_text())
        self.assertEqual(package["changed_paths"], ["scoped/keep.txt"])
        self.assertEqual(package["excluded_paths"], ["scoped/future.txt"])


class PromptInputAuditTests(unittest.TestCase):
    def test_compares_same_build_baseline_without_retaining_prompt_text(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            current = base / "current"
            baseline = base / "baseline"
            for root in (current, baseline):
                for relative in (
                    "paper-trader/backend/app/ir",
                    "paper-trader/backend/app/engine",
                    "paper-trader/frontend",
                ):
                    (root / relative).mkdir(parents=True, exist_ok=True)
            fake = base / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os\n"
                "markers = 'Strategy OS agent contract Strategy OS product rules Backend execution rules "
                "architecting-strategy-os-phases executing-strategy-os-slices "
                "reviewing-strategy-os-critical-changes running-strategy-os-safely'\n"
                "if '/baseline/' in os.getcwd(): markers += ' ' + ('baseline-padding-' * 300)\n"
                "print(json.dumps([{'content': markers}]))\n"
            )
            fake.chmod(0o755)
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROMPT_AUDIT),
                    "--root",
                    str(current),
                    "--baseline-root",
                    str(baseline),
                    "--codex",
                    str(fake),
                    "--max-bytes",
                    "22000",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("baseline-padding", result.stdout)
            report = json.loads(result.stdout)
            self.assertGreater(report["baseline"]["max_bytes"], report["max_bytes"])
            self.assertGreater(report["reduction_percent"], 0)
            self.assertEqual(report["codex_binary"], str(fake))


class SessionAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        if not SESSION_AUDIT.exists():
            self.skipTest("session audit not implemented")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.sessions = Path(self.tempdir.name)

    def write_session(self, name: str, rows: list[dict]) -> None:
        path = self.sessions / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_ignores_token_count_records_with_null_info(self) -> None:
        self.write_session(
            "null-info.jsonl",
            [
                {
                    "timestamp": "2026-08-14T00:00:00Z",
                    "type": "event_msg",
                    "payload": {"type": "token_count", "info": None},
                }
            ],
        )
        result = subprocess.run(
            [sys.executable, str(SESSION_AUDIT), "--sessions-root", str(self.sessions), "--json"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tokens"]["total_tokens"], 0)

    def test_reports_tokens_models_compactions_and_clean_forks_without_prompt_text(self) -> None:
        self.write_session(
            "root.jsonl",
            [
                {
                    "timestamp": "2026-08-14T00:00:00Z",
                    "type": "turn_context",
                    "payload": {"model": "gpt-5.6-terra", "effort": "medium"},
                },
                {
                    "timestamp": "2026-08-14T00:00:01Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 100,
                                "cached_input_tokens": 40,
                                "cache_write_input_tokens": 0,
                                "output_tokens": 10,
                                "reasoning_output_tokens": 2,
                                "total_tokens": 110,
                            }
                        },
                    },
                },
                {
                    "timestamp": "2026-08-14T00:00:02Z",
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call",
                        "name": "spawn_agent",
                        "input": json.dumps(
                            {
                                "task_name": "worker-one",
                                "fork_turns": "none",
                                "model": "gpt-5.6-luna",
                                "reasoning_effort": "medium",
                                "message": "SECRET PROMPT CONTENT MUST NOT APPEAR",
                            }
                        ),
                    },
                },
                {"timestamp": "2026-08-14T00:00:03Z", "type": "compacted", "payload": {}},
                {
                    "timestamp": "2026-08-14T00:00:04Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 260,
                                "cached_input_tokens": 140,
                                "cache_write_input_tokens": 0,
                                "output_tokens": 25,
                                "reasoning_output_tokens": 5,
                                "total_tokens": 285,
                            }
                        },
                    },
                },
            ],
        )
        result = subprocess.run(
            [
                sys.executable,
                str(SESSION_AUDIT),
                "--sessions-root",
                str(self.sessions),
                "--since",
                "2026-08-14T00:00:00Z",
                "--until",
                "2026-08-14T01:00:00Z",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("SECRET PROMPT", result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["tokens"]["input_tokens"], 260)
        self.assertEqual(report["tokens"]["cached_input_tokens"], 140)
        self.assertEqual(report["tokens"]["output_tokens"], 25)
        self.assertEqual(report["compactions"], 1)
        self.assertEqual(report["child_launches"], 1)
        self.assertEqual(report["fork_turns"], {"none": 1})
        self.assertEqual(report["models"], {"gpt-5.6-terra/medium": 1})
        self.assertEqual(report["uncached_input_tokens"], 120)
        self.assertEqual(report["weighted_credits"], 120 + 14 + 25)

    def test_sums_final_session_totals_and_reports_duration_tool_output_and_fork_sizes(self) -> None:
        self.write_session(
            "first.jsonl",
            [
                {"timestamp": "2026-08-14T00:00:00Z", "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}}},
                {"timestamp": "2026-08-14T00:00:04Z", "type": "response_item", "payload": {"type": "custom_tool_call_output", "output": "four"}},
                {"timestamp": "2026-08-14T00:00:05Z", "type": "response_item", "payload": {"type": "custom_tool_call", "name": "spawn_agent", "input": json.dumps({"fork_turns": "3", "message": "DO NOT LEAK"})}},
                {"timestamp": "2026-08-14T00:00:06Z", "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 20, "output_tokens": 4, "total_tokens": 24}}}},
            ],
        )
        self.write_session(
            "second.jsonl",
            [{"timestamp": "2026-08-14T00:00:10Z", "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 30, "output_tokens": 5, "total_tokens": 35}}}}],
        )
        result = subprocess.run([sys.executable, str(SESSION_AUDIT), "--sessions-root", str(self.sessions), "--json"], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DO NOT LEAK", result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["tokens"]["input_tokens"], 50)
        self.assertEqual(report["tokens"]["output_tokens"], 9)
        self.assertEqual(report["duration_seconds"], 10)
        self.assertEqual(report["tool_output_bytes"], 4)
        self.assertEqual(report["fork_sizes"], {"3": 3})

    def test_recognizes_current_function_call_spawn_schema(self) -> None:
        self.write_session(
            "current.jsonl",
            [
                {
                    "timestamp": "2026-08-14T00:00:00Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "spawn_agent",
                        "arguments": json.dumps(
                            {
                                "task_name": "worker-one",
                                "fork_turns": "none",
                                "message": "PROMPT MUST NOT LEAK",
                            }
                        ),
                    },
                },
                {
                    "timestamp": "2026-08-14T00:00:01Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": {"content": ["12345"]},
                    },
                },
            ],
        )
        result = subprocess.run(
            [sys.executable, str(SESSION_AUDIT), "--sessions-root", str(self.sessions), "--json"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PROMPT MUST NOT LEAK", result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["child_launches"], 1)
        self.assertEqual(report["fork_turns"], {"none": 1})
        self.assertGreater(report["tool_output_bytes"], 0)


class ArchitectureValidatorTests(unittest.TestCase):
    def test_validator_accepts_installed_repository_contract(self) -> None:
        if not VALIDATOR.exists():
            self.skipTest("architecture validator not implemented")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--root", str(ROOT)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertLessEqual(report["max_agents_chain_bytes"], 12_288)
        expected_backend_chain = sum(
            path.stat().st_size
            for path in (
                ROOT / "AGENTS.md",
                ROOT / "paper-trader" / "AGENTS.md",
                ROOT / "paper-trader" / "backend" / "AGENTS.md",
            )
        )
        self.assertEqual(
            report["instruction_chain_bytes"]["paper-trader/backend"],
            expected_backend_chain,
        )
        self.assertEqual(report["max_agents_chain_bytes"], expected_backend_chain)
        self.assertEqual(report["retired_claude_harness"], [])
        self.assertTrue(report["toml_parsed"])

    def test_validator_reports_invalid_structured_files_missing_refs_and_secrets(self) -> None:
        if not VALIDATOR.exists():
            self.skipTest("architecture validator not implemented")
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / ".codex" / "hooks").mkdir(parents=True)
            (root / ".codex" / "scripts").mkdir(parents=True)
            (root / ".agents" / "skills" / "broken").mkdir(parents=True)
            (root / "paper-trader" / "docs" / "agent" / "tasks").mkdir(parents=True)
            (root / "paper-trader" / "docs" / "agent" / "programme").mkdir(parents=True)
            (root / "paper-trader" / "docs" / "program" / "owner-steers").mkdir(parents=True)
            (root / "AGENTS.md").write_text("root\n")
            (root / ".codex" / "config.toml").write_text('model = "unterminated\n')
            (root / ".codex" / "hooks.json").write_text("{not-json")
            (root / ".codex" / "hooks" / "agent_guard.py").write_text("# guard\n")
            (root / ".codex" / "hooks" / "compaction_guard.py").write_text("# guard\n")
            for name in ("run_logged.py", "make_review_package.py", "session_audit.py", "programme_dispatcher.py"):
                (root / ".codex" / "scripts" / name).write_text("# script\n")
            (root / ".agents" / "skills" / "broken" / "SKILL.md").write_text(
                "---\nname: broken\ndescription: broken\n---\n[missing](references/nope.md)\n"
            )
            (root / "paper-trader" / "docs" / "agent" / "CURRENT.md").write_text(
                '---\n{"active_capsule":"paper-trader/docs/agent/tasks/missing.md"}\n---\n'
            )
            source_path = "paper-trader/docs/program/owner-steers/source.md"
            (root / source_path).write_text("# Altered source\n")
            source_map = {
                "schema_version": 1,
                "sources": [
                    {
                        "id": "source",
                        "path": source_path,
                        "sha256": "0" * 64,
                        "sections": [{"level": 1, "heading": "Original source", "consumers": ["phase4"]}],
                    }
                ],
                "phase_views": {"phase4": [{"source_id": "source", "heading": "Original source"}]},
            }
            (root / "paper-trader" / "docs" / "agent" / "programme" / "SOURCE_MAP.json").write_text(json.dumps(source_map))
            programme = {
                "schema_version": 1,
                "current_stage_id": "phase4-architecture",
                "source_map": "paper-trader/docs/agent/programme/SOURCE_MAP.json",
                "stages": [
                    {
                        "id": "phase4-architecture",
                        "order": 1,
                        "phase": "phase4",
                        "kind": "phase_architecture",
                        "status": "ready",
                        "depends_on": [],
                        "capsule": "paper-trader/docs/agent/tasks/missing.md",
                        "model": "gpt-5.6-sol",
                        "reasoning_effort": "medium",
                    }
                ],
            }
            (root / "paper-trader" / "docs" / "agent" / "programme" / "PROGRAMME.json").write_text(json.dumps(programme))
            header = "".join(("Author", "ization"))
            credential = "".join(("Bearer ", "static-token-value-123456"))
            (root / "paper-trader" / "CLAUDE.md").write_text(
                f'{header} = "{credential}"\n'
            )
            result = subprocess.run(
                [sys.executable, str(VALIDATOR), "--root", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            failures = "\n".join(json.loads(result.stdout)["failures"])
            self.assertIn("invalid JSON", failures)
            self.assertIn("invalid TOML", failures)
            self.assertIn("missing skill reference", failures)
            self.assertIn("active capsule does not exist", failures)
            self.assertIn("owner source hash mismatch", failures)
            self.assertIn("programme capsule does not exist", failures)
            self.assertIn("likely static credential", failures)
            self.assertIn("retired Claude harness", failures)


if __name__ == "__main__":
    unittest.main()
