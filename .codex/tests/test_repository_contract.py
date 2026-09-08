from __future__ import annotations

import json
import importlib.util
import shutil
import tempfile
import subprocess
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Codex and project runtimes are 3.11+
    tomllib = None


ROOT = Path(__file__).resolve().parents[2]


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise AssertionError(f"{path} does not contain JSON frontmatter")
    return json.loads(parts[1])


class RepositoryContractTests(unittest.TestCase):
    def test_preserved_sources_match_original_hashes_and_readable_copies(self) -> None:
        validator = ROOT / "paper-trader/docs/strategy-os-v1-v2-v3/validation/source_preservation.py"
        spec = importlib.util.spec_from_file_location("source_preservation", validator)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        manifest = json.loads((module.PRESERVATION / "manifest.json").read_text())
        for path in manifest["sources"]:
            with self.subTest(path=path):
                original = module.original_source(path)
                self.assertEqual(len(original), manifest["sources"][path]["original_bytes"])

    def test_preserved_sources_reject_archive_and_readable_tampering(self) -> None:
        validator = ROOT / "paper-trader/docs/strategy-os-v1-v2-v3/validation/source_preservation.py"
        spec = importlib.util.spec_from_file_location("source_preservation", validator)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        manifest = json.loads((module.PRESERVATION / "manifest.json").read_text())
        path = next(iter(manifest["sources"]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            preserved = root / "preservation"
            shutil.copytree(module.PRESERVATION, preserved)
            readable = root / path
            readable.parent.mkdir(parents=True)
            readable.write_bytes((ROOT / path).read_bytes() + b"changed content\n")
            with self.assertRaisesRegex(ValueError, "differs beyond whitespace"):
                module.original_source(path, root, preserved)
            readable.write_bytes((ROOT / path).read_bytes())
            manifest_path = preserved / "manifest.json"
            changed = json.loads(manifest_path.read_text())
            changed["sources"][path]["original_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "original source hash mismatch"):
                module.original_source(path, root, preserved)
            changed = json.loads(json.dumps(manifest))
            changed["sources"][path]["readable_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "readable source hash mismatch"):
                module.original_source(path, root, preserved)
            manifest_path.write_text(json.dumps(manifest))
            self.assertEqual(module.normalize_source(b"line  \r\n\r\n", "source.md"), b"line\\\n")
            archive = preserved / "originals.tar.gz"
            archive.write_bytes(archive.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "archive hash mismatch"):
                module.original_source(path, root, preserved)

    @unittest.skipIf(tomllib is None, "tomllib is unavailable on Python <3.11")
    def test_project_config_preserves_user_primary_choices_and_encodes_subagent_defaults(self) -> None:
        path = ROOT / ".codex" / "config.toml"
        self.assertTrue(path.is_file(), f"missing {path}")
        config = tomllib.loads(path.read_text())
        for key in ("model", "model_reasoning_effort", "plan_mode_reasoning_effort"):
            self.assertNotIn(key, config)
        expected = {
            "service_tier": "default",
            "project_doc_max_bytes": 12_288,
            "model_context_window": 272_000,
            "model_auto_compact_token_limit": 220_000,
            "model_auto_compact_token_limit_scope": "total",
            "tool_output_token_limit": 6_000,
        }
        for key, value in expected.items():
            self.assertEqual(config.get(key), value, key)

        self.assertFalse(config["memories"]["use_memories"])
        self.assertFalse(config["memories"]["generate_memories"])
        self.assertTrue(config["features"]["multi_agent"])
        self.assertTrue(config["features"]["goals"])
        self.assertTrue(config["features"]["plugins"])
        self.assertEqual(
            config["features"]["multi_agent_v2"],
            {
                "enabled": True,
                "max_concurrent_threads_per_session": 5,
                "expose_spawn_agent_model_overrides": True,
                "wait_agent_enabled": True,
                "non_code_mode_only": True,
            },
        )
        self.assertTrue(config["agents"]["enabled"])
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 5)
        self.assertEqual(config["agents"]["default_subagent_model"], "gpt-5.6-sol")
        self.assertEqual(config["agents"]["default_subagent_reasoning_effort"], "medium")
        self.assertFalse(config["agents"]["interrupt_message"])
        self.assertFalse(config["mcp_servers"]["node_repl"]["enabled"])
        self.assertFalse(config["mcp_servers"]["github"]["enabled"])

        expected_plugins = {
            "documents@openai-primary-runtime",
            "spreadsheets@openai-primary-runtime",
            "presentations@openai-primary-runtime",
            "engineering-skills@claude-code-skills",
            "context7@claude-plugins-official",
            "playwright@claude-plugins-official",
            "superpowers@claude-plugins-official",
            "browser@openai-bundled",
            "pdf@openai-primary-runtime",
            "visualize@openai-bundled",
            "template-creator@openai-primary-runtime",
            "computer-use@openai-bundled",
            "chrome@openai-bundled",
            "sites@openai-bundled",
        }
        self.assertEqual(set(config["plugins"]), expected_plugins)
        # Project preferences remain disabled while the global gate allows enabled user plugins.
        self.assertTrue(all(not item["enabled"] for item in config["plugins"].values()))

    @unittest.skipIf(tomllib is None, "tomllib is unavailable on Python <3.11")
    def test_custom_agents_pin_model_effort_permissions_and_mcp_state(self) -> None:
        expected = {
            "terra-worker.toml": ("terra-worker", "gpt-5.6-sol", "medium", "workspace-write"),
            "luna-worker.toml": ("luna-worker", "gpt-5.6-sol", "medium", "workspace-write"),
            "critical-reviewer.toml": (
                "critical-reviewer",
                "gpt-5.6-sol",
                "high",
                "read-only",
            ),
        }
        for filename, values in expected.items():
            path = ROOT / ".codex" / "agents" / filename
            self.assertTrue(path.is_file(), f"missing {path}")
            config = tomllib.loads(path.read_text())
            self.assertEqual(
                (
                    config["name"],
                    config["model"],
                    config["model_reasoning_effort"],
                    config["sandbox_mode"],
                ),
                values,
            )
            self.assertNotIn("mcp_servers", config)
            if filename in {"terra-worker.toml", "luna-worker.toml"}:
                instructions = config["developer_instructions"]
                for phrase in (
                    "assigned by the user or parent",
                    "exclusive write paths",
                    "write ownership is disjoint",
                    "expand scope",
                    "access live systems or credentials",
                    "perform destructive work",
                    "cross an owner gate",
                ):
                    self.assertIn(phrase, instructions)

    def test_repository_workflow_hooks_are_disabled(self) -> None:
        config = json.loads((ROOT / ".codex" / "hooks.json").read_text())
        self.assertEqual(config["hooks"], {})

    def test_agents_instruction_chains_stay_under_budget(self) -> None:
        root = ROOT / "AGENTS.md"
        paper = ROOT / "paper-trader" / "AGENTS.md"
        backend = ROOT / "paper-trader" / "backend" / "AGENTS.md"
        frontend = ROOT / "paper-trader" / "frontend" / "AGENTS.md"
        for path in (root, paper, backend, frontend):
            self.assertTrue(path.is_file(), f"missing {path}")

        chains = {
            "root": [root],
            "paper": [root, paper],
            "backend": [root, paper, backend],
            "frontend": [root, paper, frontend],
        }
        for name, paths in chains.items():
            size = sum(len(path.read_bytes()) for path in paths)
            self.assertLessEqual(size, 12_288, f"{name} chain is {size} bytes")

    def test_short_working_plan_and_legacy_resume_links_remain_available(self) -> None:
        plan = ROOT / "paper-trader" / "docs" / "agent" / "WORKING-PLAN.md"
        current = ROOT / "paper-trader" / "docs" / "agent" / "CURRENT.md"
        router = ROOT / "paper-trader" / "docs" / "agent" / "ROUTER.md"
        programme = ROOT / "paper-trader" / "docs" / "agent" / "programme" / "PROGRAMME.json"
        for path in (plan, current, router, programme):
            self.assertTrue(path.is_file(), f"missing {path}")

        # Startup stays small; historical state remains intact for explicit resumes.
        self.assertLessEqual(len(plan.read_bytes()), 6_144)
        self.assertLessEqual(len(router.read_bytes()), 4_096)
        state = frontmatter(current)
        programme_state = json.loads(programme.read_text())
        capsule = ROOT / state["active_capsule"]
        self.assertTrue(capsule.is_file(), f"missing {capsule}")
        task = frontmatter(capsule)
        self.assertEqual(state["programme"], "paper-trader/docs/agent/programme/PROGRAMME.json")
        self.assertIn(state["status"], {"ready", "active", "paused_owner_gate"})
        required = {
            "id",
            "phase",
            "status",
            "goal",
            "goal_contract",
            "risk_tags",
            "required_docs",
            "allowed_paths",
            "nonclaims",
            "owner_gates",
            "stop_conditions",
            "model_route",
            "parallel_budget",
            "assignments",
            "acceptance",
            "test_plan",
            "review",
        }
        self.assertEqual(required - set(task), set())
        self.assertEqual(task["id"], state["active_stage"])
        self.assertEqual(programme_state["current_stage_id"], task["id"])
        self.assertIn("critical", task["risk_tags"])
        self.assertLessEqual(task["parallel_budget"], 5)
        self.assertLessEqual(len(task["assignments"]), task["parallel_budget"])
        base = subprocess.run(
            ["git", "rev-parse", "--verify", f"{task['review']['base_sha']}^{{commit}}"],
            cwd=ROOT, capture_output=True, check=False,
        )
        self.assertEqual(base.returncode, 0, "review base must identify an existing commit")
        self.assertIsInstance(task["review"]["exclude_paths"], list)

    def test_programme_declares_goal_routes_and_phase_review_gates(self) -> None:
        path = ROOT / "paper-trader" / "docs" / "agent" / "programme" / "PROGRAMME.json"
        programme = json.loads(path.read_text())
        self.assertEqual(programme["controller"]["model"], "gpt-5.6-sol")
        self.assertEqual(programme["controller"]["reasoning_effort"], "medium")
        self.assertEqual(programme["controller"]["max_active_goals"], 1)
        stages = {stage["id"]: stage for stage in programme["stages"]}
        for phase in range(4, 11):
            self.assertEqual(stages[f"phase{phase}-architecture"]["model"], "gpt-5.6-sol")
            self.assertEqual(stages[f"phase{phase}-architecture"]["reasoning_effort"], "medium")
            review_id = "phase4-final-review-5" if phase == 4 else f"phase{phase}-review"
            self.assertEqual(stages[review_id]["model"], "gpt-5.6-sol")
            self.assertEqual(stages[review_id]["reasoning_effort"], "high")
            if phase >= 5:
                self.assertEqual(stages[f"phase{phase}-implementation"]["model"], "gpt-5.6-sol")
                self.assertEqual(stages[f"phase{phase}-implementation"]["reasoning_effort"], "medium")

    def test_agent_runtime_artifacts_are_ignored(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "-q", ".agent/runs/probe.log"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_retired_claude_harness_is_absent(self) -> None:
        tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        deleted = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=D"], cwd=ROOT, text=True).splitlines()
        retired_prefixes = ("paper-trader/CLAUDE.md", ".claude/")
        retired_tracked = {path for path in tracked if path == retired_prefixes[0] or path.startswith(retired_prefixes[1])}
        retired_deleted = {path for path in deleted if path == retired_prefixes[0] or path.startswith(retired_prefixes[1])}
        self.assertEqual(retired_tracked, retired_deleted)

    def test_durable_claude_rules_have_clause_level_dispositions(self) -> None:
        audit = ROOT / "paper-trader" / "docs" / "agent" / "CLAUDE_MIGRATION_AUDIT.md"
        text = audit.read_text()
        required_clauses = (
            "production-shaped prior schema",
            "restore-based rollback",
            "historical NULL",
            "mock-only reset",
            "direct SQL",
            "NULLIF",
            "LIMIT -1",
            "pool_size=5",
            "aggregate in SQL",
            "next-bar open",
            "adverse slippage",
            "event-blackout",
            "candle-to-frame",
            "research import direction",
        )
        for clause in required_clauses:
            with self.subTest(clause=clause):
                self.assertIn(clause, text)
        self.assertGreaterEqual(sum(text.count(f"| {label} |") for label in ("KEEP", "MOVE", "REWRITE", "REJECT")), 20)


if __name__ == "__main__":
    unittest.main()
