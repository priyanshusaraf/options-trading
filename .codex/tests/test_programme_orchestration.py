from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRAMME_DIR = ROOT / "paper-trader" / "docs" / "agent" / "programme"
OWNER_DIR = ROOT / "paper-trader" / "docs" / "program" / "owner-steers"

INDICATOR_CORRECTION_STAGES = tuple(
    "post-phase5-indicator-accuracy-" + suffix
    for suffix in (
        "contract-foundation", "contract-assurance",
        "core-math", "core-parameter-correction",
        "core-return-stability-correction", "core-level-moment-correction", "core-level-moment-assurance",
        "recursive-state", "recursive-sar-source-replan", "recursive-sar-source-correction", "recursive-sar-source-assurance",
        "multi-output", "multi-output-source-replan", "multi-output-correction",
        "multi-output-band-ppo-source-replan", "multi-output-band-ppo-source-correction", "multi-output-band-ppo-source-assurance",
        "session-data", "session-prefix-fresh-assurance",
        "remaining-oracles", "remaining-oracles-assurance",
        "registry-lineage-integration", "complete-universe-assurance", "final-review",
    )
)


EXPECTED_SOURCES = {
    "product_architecture": (
        "00-STRATEGY-OS-PRODUCT-STEER.md",
        "2f51a019870c94996d77c24c3f92821f7097c8703cebed0b617850187226115d",
        {"phase4", "phase5", "phase6", "phase7", "phase8", "phase9", "phase10", "v1_release"},
    ),
    "strategy_language": (
        "01-STRATEGY-LANGUAGE-NODE-SYSTEM.md",
        "9be080888822fae23e196fa78c445eb0933886229749d4d2421a77a230f7f306",
        {"ir_v2", "phase5", "phase6", "phase7", "phase8"},
    ),
    "market_truth": (
        "02-MARKET-TRUTH-DATA-CONTRACTS.md",
        "ee91b160d50dbcdb78889521f31f6560d8e312caf92f26047996eab20e54fd27",
        {"phase4", "phase6", "phase7", "phase9", "v1_release"},
    ),
    "deployment_trust": (
        "03-DEPLOYMENT-EXECUTION-TRUST.md",
        "6151b1d2ebb6a587255754c651564874c21f43e3ec9e6ca9a4b9bbd7e28b0805",
        {"phase3", "phase6", "phase7", "phase8", "phase9", "phase10"},
    ),
    "runtime_economics": (
        "04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
        "932b0281ce6fc2468b3b960e1da4e72ac0f3c0de0acbbfb8bea9188812f6a3a1",
        {"phase4", "phase5", "phase6", "phase7", "phase9", "phase10"},
    ),
    "verification_policy": (
        "05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
        "bd15bb27284b7e4f467673a491c4c1b556565c9d7b342966ccd695a2b924fad5",
        {"phase3", "ir_v2", "phase4", "phase5", "phase6", "phase7", "phase8", "phase9", "phase10", "v1_release"},
    ),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def frontmatter(path: Path) -> dict:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) != 3:
        raise AssertionError(f"{path} lacks JSON/YAML-compatible frontmatter")
    return json.loads(parts[1])


def headings(path: Path) -> list[tuple[int, str]]:
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if match:
            found.append((len(match.group(1)), match.group(2)))
    return found


class SourceMapTests(unittest.TestCase):
    def test_owner_sources_are_exact_and_every_heading_is_routed(self) -> None:
        source_map = load_json(PROGRAMME_DIR / "SOURCE_MAP.json")
        self.assertEqual(source_map["schema_version"], 1)
        indexed = {item["id"]: item for item in source_map["sources"]}
        self.assertEqual(set(indexed), set(EXPECTED_SOURCES))

        for source_id, (filename, digest, required_consumers) in EXPECTED_SOURCES.items():
            with self.subTest(source=source_id):
                path = OWNER_DIR / filename
                self.assertTrue(path.is_file(), f"missing owner source {path}")
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
                record = indexed[source_id]
                self.assertEqual(record["path"], path.relative_to(ROOT).as_posix())
                self.assertEqual(record["sha256"], digest)
                mapped = [(section["level"], section["heading"]) for section in record["sections"]]
                self.assertEqual(mapped, headings(path))
                self.assertTrue(all(section["consumers"] for section in record["sections"]))
                consumers = {consumer for section in record["sections"] for consumer in section["consumers"]}
                self.assertTrue(required_consumers <= consumers, (source_id, required_consumers - consumers))

    def test_phase_views_reference_real_mapped_sections(self) -> None:
        source_map = load_json(PROGRAMME_DIR / "SOURCE_MAP.json")
        sections = {
            (source["id"], section["heading"])
            for source in source_map["sources"]
            for section in source["sections"]
        }
        for phase, entries in source_map["phase_views"].items():
            self.assertTrue(entries, phase)
            for entry in entries:
                self.assertIn((entry["source_id"], entry["heading"]), sections)


class ProgrammeContractTests(unittest.TestCase):
    def test_programme_orders_dependencies_and_keeps_future_work_blocked(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        self.assertEqual(programme["schema_version"], 1)
        stages = programme["stages"]
        self.assertEqual([stage["order"] for stage in stages], list(range(1, len(stages) + 1)))
        indexed = {stage["id"]: stage for stage in stages}
        self.assertEqual(len(indexed), len(stages))
        current_id = programme["current_stage_id"]
        self.assertIn(current_id, indexed)
        current = indexed[current_id]
        self.assertIn(
            current["status"],
            {"ready", "correction", "review", "active", "paused_owner_gate"},
        )
        expected_active = [current_id] if current["status"] == "active" else []
        self.assertEqual([stage["id"] for stage in stages if stage["status"] == "active"], expected_active)
        self.assertTrue(all(stage["status"] == "blocked" for stage in stages[current["order"]:]))

        seen = set()
        for index, stage in enumerate(stages):
            expected = [] if index == 0 else [stages[index - 1]["id"]]
            self.assertEqual(stage["depends_on"], expected, stage["id"])
            self.assertTrue(set(stage["depends_on"]) <= seen, stage["id"])
            seen.add(stage["id"])

        self.assertLess(
            indexed["phase3-4-ir-v2-acceptance"]["order"],
            indexed["phase4-architecture"]["order"],
        )

    def test_every_phase_has_sol_high_review_and_sol_medium_architecture(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        stages = programme["stages"]
        for phase in range(4, 11):
            architecture = next(stage for stage in stages if stage["id"] == f"phase{phase}-architecture")
            review_id = "phase4-final-review-5" if phase == 4 else f"phase{phase}-review"
            review = next(stage for stage in stages if stage["id"] == review_id)
            self.assertEqual((architecture["model"], architecture["reasoning_effort"]), ("gpt-5.6-sol", "medium"))
            self.assertEqual((review["model"], review["reasoning_effort"]), ("gpt-5.6-sol", "high"))
            self.assertEqual(review["kind"], "phase_review")
            if phase == 4:
                self.assertEqual(review["status"], "accepted")
                self.assertIn("root_acceptance", review["acceptance"])
            else:
                self.assertIn(f"phase{phase}-implementation", review["depends_on"])

    def test_current_and_executable_capsules_use_goal_contract(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        current = frontmatter(ROOT / "paper-trader" / "docs" / "agent" / "CURRENT.md")
        self.assertEqual(current["programme"], "paper-trader/docs/agent/programme/PROGRAMME.json")

        current_stage = next(stage for stage in programme["stages"] if stage["id"] == programme["current_stage_id"])
        self.assertEqual(current_stage["capsule"], current["active_capsule"])
        capsule = frontmatter(ROOT / current_stage["capsule"])
        self.assertEqual(capsule["id"], current_stage["id"])
        self.assertEqual(capsule["goal_contract"]["create_before_work"], True)
        self.assertTrue(capsule["goal_contract"]["stopping_condition"])
        self.assertEqual(capsule["model_route"]["owner"], "gpt-5.6-sol")
        expected_effort = "high" if current_stage["kind"] == "phase_review" else "medium"
        self.assertEqual(
            capsule["model_route"]["owner_reasoning_effort"], expected_effort)

    def test_failed_phase4_routes_are_complete_history_not_executable_authority(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        historical_ids = {
            "phase4-review",
            "phase4-review-recheck",
            "phase4-review-recovery",
            "phase4-final-review-2",
            "phase4-final-review-3",
            "phase4-final-review-4",
        }
        executable = {stage["id"]: stage for stage in programme["stages"]}
        historical = {
            item.get("id"): item
            for item in programme["historical_blocked_reviews"]
            if isinstance(item, dict)
        }
        self.assertTrue(historical_ids.isdisjoint(executable))
        self.assertTrue(historical_ids <= set(historical))
        for stage_id in historical_ids:
            with self.subTest(stage=stage_id):
                row = historical[stage_id]
                self.assertEqual(row["status"], "blocked")
                self.assertEqual(row["historical_classification"]["original_status"], "blocked")
                self.assertFalse(row["historical_classification"]["executable_acceptance"])
                self.assertTrue(row["historical_classification"]["verdict_or_stop_preserved"])

        expected = {
            "phase4-review-correction": (
                ["phase4-implementation"], ["phase4-review"]),
            "phase4-v2-durable-graph-integration": (
                ["phase4-review-correction"],
                ["phase4-review-recheck", "phase4-review-recovery", "phase4-final-review-2"]),
            "phase4-loader-authority-recovery-correction": (
                ["phase4-authority-integration-gate"], ["phase4-final-review-3"]),
            "phase4-research-receipt-authority-architecture-correction": (
                ["phase4-adversarial-matrix-closure"], ["phase4-final-review-4"]),
        }
        for stage_id, (dependency, history) in expected.items():
            with self.subTest(successor=stage_id):
                self.assertEqual(executable[stage_id]["depends_on"], dependency)
                self.assertEqual(executable[stage_id]["historical_predecessors"], history)
                self.assertEqual(
                    executable[stage_id]["dependency_before_history_normalization"],
                    [history[-1]])

        first_unfinished = next(
            stage for stage in programme["stages"] if stage["status"] != "accepted")
        self.assertEqual(first_unfinished["id"], programme["current_stage_id"])
        self.assertIn(first_unfinished["id"], {
            "phase5-capital-assurance-replan",
            "phase5-capital-assurance-recovery-correction",
            "phase5-capital-broad-compatibility-provider-leak-correction",
            "phase5-capital-assurance-final-review",
            "phase5-implementation",
            "phase5-integration-evidence-recovery-replan",
            "phase5-capital-plane-ownership-correction",
            "phase5-cache-version-contract-correction",
            "phase5-stale-compatibility-fixture-correction",
            "phase5-process-state-isolation-correction",
            "phase5-language-resource-contracts",
            "phase5-language-resource-assurance",
            "phase5-provider-evidence-compatibility",
            "phase5-first-party-analytical-catalogue",
            "phase5-state-execution-derivatives-catalogue",
            "phase5-custom-node-contracts",
            "phase5-research-execution",
            "phase5-research-parity-assurance",
            "phase5-bounded-sweeps-cache-artifacts",
            "phase5-research-runtime-packaging-recovery-replan",
            "phase5-research-runtime-packaging-recovery-correction",
            "phase5-canonical-scenario-gate",
            "phase5-scenario-assurance",
            "phase5-review",
            "post-phase5-indicator-accuracy-audit",
            "post-phase5-indicator-accuracy-correction-replan",
            "strategy-os-v0-release-audit",
            "strategy-os-v0-release-profile-foundation",
            "strategy-os-v0-verified-language-catalogue",
            "strategy-os-v0-canonical-research-spine",
            "strategy-os-v0-zerodha-data-static-scope",
            "strategy-os-v0-chart-annotation-replay",
            "strategy-os-v0-robustness-lab",
            "strategy-os-v0-monitoring-signals-review",
            "strategy-os-v0-frontend-convergence",
            "strategy-os-v0-precision-slate-shell-foundation",
            "strategy-os-v0-frontend-integration-closure",
            "strategy-os-v0-security-operations-deployability",
            "strategy-os-v0-golden-benchmarks-release",
            "strategy-os-v0-review",
            "phase6-architecture",
        } | set(INDICATOR_CORRECTION_STAGES))

    def test_owner_authorized_capital_recovery_lineage_is_serial_and_dispatchable(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        stages = programme["stages"]
        indexed = {stage["id"]: stage for stage in stages}
        historical = {
            item.get("id"): item
            for item in programme["historical_blocked_reviews"]
            if isinstance(item, dict)
        }
        self.assertNotIn("phase5-capital-admission-assurance", indexed)
        exhausted = historical["phase5-capital-admission-assurance"]
        self.assertEqual(exhausted["status"], "blocked")
        self.assertFalse(
            exhausted["historical_classification"]["executable_acceptance"])
        self.assertTrue(
            exhausted["historical_classification"]["verdict_or_stop_preserved"])
        self.assertEqual(
            indexed["phase5-capital-assurance-replan"]["historical_predecessors"],
            ["phase5-capital-admission-assurance"],
        )
        self.assertNotIn("phase5-capital-assurance-recovery-correction", indexed)
        blocked_correction = historical[
            "phase5-capital-assurance-recovery-correction"]
        self.assertEqual(blocked_correction["status"], "blocked")
        self.assertEqual(blocked_correction["verdict"], "CORRECTION_BLOCKED")
        self.assertFalse(
            blocked_correction["historical_classification"]["executable_acceptance"])
        self.assertTrue(
            blocked_correction["historical_classification"]["verdict_or_stop_preserved"])
        provider_correction = indexed[
            "phase5-capital-broad-compatibility-provider-leak-correction"]
        self.assertEqual(
            provider_correction["depends_on"],
            ["phase5-capital-assurance-replan"],
        )
        self.assertEqual(
            provider_correction["historical_predecessors"],
            ["phase5-capital-assurance-recovery-correction"],
        )
        self.assertEqual(
            provider_correction["write_paths"],
            ["paper-trader/backend/tests/test_execution_control.py"],
        )
        self.assertEqual(
            indexed["phase5-capital-assurance-final-review"]["depends_on"],
            ["phase5-capital-broad-compatibility-provider-leak-correction"],
        )
        integration = indexed["phase5-implementation"]
        self.assertEqual(
            integration["depends_on"],
            ["phase5-scenario-assurance"],
        )
        self.assertEqual(
            integration["failed_attempt"]["verdict"],
            "EVIDENCE_CURRENT_FAIL",
        )
        self.assertEqual(
            integration["failed_attempt"]["phase_tier_failures"], 169)
        self.assertFalse(integration["failed_attempt"]["executable_acceptance"])
        integration_replan = indexed["phase5-integration-evidence-recovery-replan"]
        self.assertEqual(
            integration_replan["depends_on"],
            ["phase5-capital-assurance-final-review"],
        )
        self.assertEqual(
            integration_replan["historical_predecessors"],
            ["phase5-implementation"],
        )
        recovery_order = [
            "phase5-integration-evidence-recovery-replan",
            "phase5-capital-plane-ownership-correction",
            "phase5-cache-version-contract-correction",
            "phase5-stale-compatibility-fixture-correction",
            "phase5-process-state-isolation-correction",
            "phase5-language-resource-contracts",
            "phase5-language-resource-assurance",
            "phase5-provider-evidence-compatibility",
            "phase5-first-party-analytical-catalogue",
            "phase5-state-execution-derivatives-catalogue",
            "phase5-custom-node-contracts",
            "phase5-research-execution",
            "phase5-research-parity-assurance",
            "phase5-bounded-sweeps-cache-artifacts",
            "phase5-research-runtime-packaging-recovery-replan",
            "phase5-research-runtime-packaging-recovery-correction",
            "phase5-canonical-scenario-gate",
            "phase5-scenario-assurance",
            "phase5-implementation",
            "phase5-review",
        ]
        for predecessor, successor in zip(recovery_order, recovery_order[1:]):
            self.assertEqual(indexed[successor]["depends_on"], [predecessor])
        current_id = programme["current_stage_id"]
        if current_id in recovery_order:
            current_index = recovery_order.index(current_id)
            self.assertTrue(all(
                indexed[item]["status"] == "accepted"
                for item in recovery_order[:current_index]
            ))
            self.assertIn(indexed[current_id]["status"], {
                "ready", "correction", "review", "active", "paused_owner_gate",
            })
            self.assertTrue(all(
                indexed[item]["status"] == "blocked"
                for item in recovery_order[current_index + 1:]
            ))
        else:
            self.assertTrue(all(
                indexed[item]["status"] == "accepted"
                for item in recovery_order
            ))
        self.assertEqual(
            indexed["phase5-review"]["depends_on"],
            ["phase5-implementation"],
        )
        self.assertEqual(
            indexed["phase5-capital-assurance-final-review"]["rechecks_remaining"],
            0,
        )

        controller = ROOT / ".agent/programme/programme-contract-test-controller.json"
        self.assertFalse(controller.exists())
        result = subprocess.run([
            sys.executable,
            str(ROOT / ".codex/scripts/programme_dispatcher.py"),
            "--root", str(ROOT),
            "--active-goal-count", "0",
            "--controller-state", str(controller),
            "--json",
        ], cwd=ROOT, text=True, capture_output=True, check=False)
        action = json.loads(result.stdout)
        self.assertEqual(action["stage_id"], programme["current_stage_id"])
        current = indexed[programme["current_stage_id"]]
        if current["status"] in {"paused_owner_gate", "active", "blocked"}:
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(action["action"], "pause")
            if current["status"] == "paused_owner_gate":
                self.assertIn("owner gate", action["reason"])
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(action["action"], "dispatch")
            self.assertIn(action["stage_id"], {
                "phase5-capital-assurance-replan",
                "phase5-capital-assurance-recovery-correction",
                "phase5-capital-broad-compatibility-provider-leak-correction",
                "phase5-capital-assurance-final-review",
                "phase5-implementation",
                "phase5-integration-evidence-recovery-replan",
                "phase5-capital-plane-ownership-correction",
                "phase5-cache-version-contract-correction",
                "phase5-stale-compatibility-fixture-correction",
                "phase5-process-state-isolation-correction",
                "phase5-review",
            } | set(INDICATOR_CORRECTION_STAGES))
        self.assertFalse(controller.exists())

    def _assert_auth_dataset_parallel_boundary(self, programme, stage, capsule) -> None:
        """Only the sealed Q01/Q03 writers may accompany corrected numerical assurance."""
        origin_stage_id = "post-phase5-indicator-accuracy-multi-output-correction-assurance"
        stage_id = stage["id"]
        self.assertEqual(stage_id, "post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance")
        self.assertEqual(programme["current_stage_id"], stage_id)
        self.assertEqual(stage["status"], "active")
        self.assertEqual(capsule["numerical_parallel_budget"], 0)
        decision_path = ROOT / ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/leaf-decision.json"
        authority = {"path": str(decision_path.relative_to(ROOT)),
                     "sha256": "ffbb88cf2c2fa4c016d1e1368ba3d5a23c5e5f60947f10e0f46b737281d20e3e"}
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(capsule["parallel_auth_dataset_authority"], authority)
        self.assertEqual(stage["parallel_auth_dataset_authority"], authority)
        self.assertEqual(digest(decision_path), authority["sha256"])
        decision = load_json(decision_path)
        self.assertEqual(decision["primary_stage"], origin_stage_id)
        self.assertEqual(decision["decision"], "AUTHORIZE_EXACT_QUEUED_LEAVES")
        self.assertEqual(decision["maximum_assignments"], 2)
        self.assertEqual(decision["numerical_parallel_budget"], 0)
        self.assertTrue(decision["existing_assignments_retired"])
        for claim in ("public_capability_opening", "publication", "deployment", "v0_complete"):
            self.assertFalse(decision[claim])
        replan = ROOT / ".agent/runs/strategy-os-v0-parallel-workstream-replan"
        self.assertEqual(digest(replan / "closure-seal.json"), decision["replan_seal_sha256"])
        self.assertEqual(digest(replan / "queue.json"), decision["queue_sha256"])
        expected = {leaf["assignment"]: leaf for leaf in decision["leaves"]}
        self.assertEqual(set(expected), {"v0_auth_session_transport", "v0_canonical_dataset_bridge"})
        self.assertEqual({leaf["queue_id"] for leaf in expected.values()}, {"Q01", "Q03"})
        addendum_path = ROOT / ".agent/runs/strategy-os-v0-q03-schema-role-clarification/decision.json"
        addendum_ref = {"path": str(addendum_path.relative_to(ROOT)),
                        "sha256": "2ae577e076fd2080642ceebbeb69f45775f8f31fe1ca1570eb5a1f9962e9e41c"}
        self.assertEqual(capsule["parallel_auth_dataset_schema_addendum"], addendum_ref)
        self.assertEqual(stage["parallel_auth_dataset_schema_addendum"], addendum_ref)
        self.assertEqual(digest(addendum_path), addendum_ref["sha256"])
        addendum = load_json(addendum_path)
        self.assertEqual(addendum["old_decision_sha256"], authority["sha256"])
        self.assertEqual(addendum["decision"], "CLARIFY_PROVIDER_PROVENANCE_VS_INDEX_ENCODING")
        self.assertEqual(addendum["changed_leaf"], "v0_canonical_dataset_bridge")
        self.assertTrue(addendum["same_goal_and_write_paths"])
        for claim in ("source_product_changes", "publication", "deployment", "v0_complete"):
            self.assertFalse(addendum[claim])
        original_leaf = expected[addendum["changed_leaf"]]
        self.assertEqual(addendum["old_contract_sha256"], original_leaf["contract"]["sha256"])
        for key in original_leaf.keys() - {"draft_capsule", "draft_sha256", "contract"}:
            self.assertEqual(addendum["leaf"][key], original_leaf[key])
        expected[addendum["changed_leaf"]] = addendum["leaf"]
        cold_path = ROOT / ".agent/runs/strategy-os-v0-q03-cold-admission-clarification/decision.json"
        cold_ref = {"path": str(cold_path.relative_to(ROOT)),
                    "sha256": "8ecdc007a7351785fa39676eaca6b7d0a4ac45383f4050db0cae716e0e5601b8"}
        self.assertEqual(capsule["parallel_auth_dataset_cold_admission_addendum"], cold_ref)
        self.assertEqual(stage["parallel_auth_dataset_cold_admission_addendum"], cold_ref)
        self.assertEqual(digest(cold_path), cold_ref["sha256"])
        cold = load_json(cold_path)
        self.assertEqual(cold["decision"], "CLARIFY_COLD_ADMISSION_PREPARE_THEN_PERSIST")
        self.assertEqual(cold["previous_schema_addendum_sha256"], addendum_ref["sha256"])
        self.assertEqual(cold["changed_leaf"], addendum["changed_leaf"])
        self.assertEqual(cold["same_owner_task"], addendum["same_owner_task"])
        self.assertTrue(cold["same_goal_and_write_paths"])
        self.assertEqual(cold["old_contract_sha256"], addendum["leaf"]["contract"]["sha256"])
        for claim in ("source_product_changes_by_coordinator", "publication", "deployment", "v0_complete"):
            self.assertFalse(cold[claim])
        for key in addendum["leaf"].keys() - {"draft_capsule", "draft_sha256", "contract"}:
            self.assertEqual(cold["leaf"][key], addendum["leaf"][key])
        expected[cold["changed_leaf"]] = cold["leaf"]
        carry_path = ROOT / ".agent/runs/strategy-os-v0-source-assurance-routing/carry-decision.json"
        carry_ref = {"path": str(carry_path.relative_to(ROOT)),
                     "sha256": "7bdf37b60e3bf3f9cd4cc83a620934cf72799b59f23057a20e7dfc04b67bdd77"}
        self.assertEqual(capsule["parallel_carry_in"], carry_ref)
        self.assertEqual(stage["parallel_carry_in"], carry_ref)
        self.assertEqual(digest(carry_path), carry_ref["sha256"])
        carry = load_json(carry_path)
        self.assertEqual((carry["from"], carry["to"]),
                         ("post-phase5-indicator-accuracy-multi-output-band-ppo-source-correction", stage_id))
        self.assertEqual(carry["owner_task"], capsule["owner_task"])
        self.assertEqual(carry["assignments"], capsule["assignments"])
        self.assertEqual(carry["auth_dataset_authority"], authority)
        self.assertEqual(carry["schema_addendum"], addendum_ref)
        self.assertEqual(carry["cold_admission_addendum"], cold_ref)
        self.assertEqual(carry["numerical_parallel_budget"], 0)
        self.assertEqual(carry["implementation_seal_sha256"],
                         "6ad75d40a76ebb0bb6f883082dcec0a99fec29b5b878d5fe668970e5c93e5f7a")
        self.assertNotEqual(carry["implementation_owner"], carry["owner_task"])
        for claim in ("path_ownership_changes", "numerical_acceptance", "publication", "deployment"):
            self.assertFalse(carry[claim])
        self.assertEqual(carry["source_decision_sha256"],
                         "2ca3e31e074984d1545af8a0a98ea718fbaf2ad093552ec651672df8ae6213f1")
        assignments = capsule["assignments"]
        self.assertEqual(len(assignments), 2)
        self.assertEqual(capsule["parallel_budget"], 2)
        self.assertEqual({row["id"] for row in assignments}, set(expected))
        self.assertEqual(stage["parallel_assignments"], assignments)
        self.assertEqual(programme["parallel_development"]["active_assignments"], assignments)
        current = frontmatter(ROOT / "paper-trader/docs/agent/CURRENT.md")
        self.assertEqual(current["parallel_development"]["active_assignments"], assignments)
        self.assertEqual(current["parallel_development"]["auth_dataset_authority"], authority)
        self.assertEqual(current["parallel_development"]["auth_dataset_schema_addendum"], addendum_ref)
        self.assertEqual(programme["parallel_development"]["auth_dataset_schema_addendum"], addendum_ref)
        self.assertEqual(current["parallel_development"]["auth_dataset_cold_admission_addendum"], cold_ref)
        self.assertEqual(programme["parallel_development"]["auth_dataset_cold_admission_addendum"], cold_ref)
        owned = [(ROOT / path).resolve() for path in capsule["allowed_paths"]]
        owners = {capsule["owner_task"], capsule["coordinator"]}
        frontend = Path("/Users/priyanshusaraf/dev/strategy-os-frontend").resolve()
        for row in assignments:
            leaf = expected[row["id"]]
            self.assertEqual(row["kind"], "bounded_parallel_implementation")
            self.assertEqual((row["model"], row["reasoning_effort"], row["fork_turns"]),
                             ("gpt-5.6-sol", "medium", "none"))
            self.assertIsInstance(row["owner_task"], str)
            self.assertTrue(row["owner_task"])
            self.assertNotIn(row["owner_task"], owners)
            owners.add(row["owner_task"])
            self.assertFalse(row["primary_programme_owner"])
            self.assertEqual(row["capsule"], leaf["capsule_path"])
            self.assertEqual(row["allowed_paths"], leaf["allowed_paths"])
            draft_path = ROOT / leaf["draft_capsule"]
            self.assertEqual(digest(draft_path), leaf["draft_sha256"])
            self.assertEqual(digest(ROOT / leaf["contract"]["path"]), leaf["contract"]["sha256"])
            draft = frontmatter(draft_path)
            side = frontmatter(ROOT / row["capsule"])
            for key in ("allowed_paths", "new_paths", "scope", "acceptance", "dependency_gate",
                        "protected_paths", "contract", "required_docs", "stable_input_hashes"):
                self.assertEqual(side[key], draft[key])
            self.assertEqual(side["owner_task"], row["owner_task"])
            self.assertEqual(side["parallel_budget"], 0)
            self.assertEqual(side["assignments"], [])
            self.assertEqual(side["programme_assignment"]["parent_stage"], origin_stage_id)
            self.assertEqual(side["programme_assignment"]["assignment_id"], row["id"])
            self.assertFalse(side["programme_assignment"]["primary_programme_owner"])
            self.assertEqual((side["model_route"]["owner"], side["model_route"]["owner_reasoning_effort"]),
                             ("gpt-5.6-sol", "medium"))
            review = side["review"]
            self.assertTrue(review["required"])
            self.assertEqual((review["agent"], review["model"], review["reasoning_effort"], review["max_rechecks"]),
                             ("critical-reviewer", "gpt-5.6-sol", "high", 1))
            self.assertEqual(review["verdicts"], ["SPEC", "QUALITY"])
            dependency = next(s for s in programme["stages"] if s["id"] == side["dependency_gate"])
            self.assertEqual(dependency["status"], "accepted")
            if row["id"] == "v0_auth_session_transport":
                self.assertEqual(side["schema_ownership"], draft["schema_ownership"])
                self.assertEqual(review["cross_repository_review"], draft["review"]["cross_repository_review"])
            else:
                self.assertFalse(side["schema_changes"])
                self.assertEqual(side["contract_clarification"], addendum_ref)
                self.assertEqual(side["admission_order_clarification"], cold_ref)
                self.assertEqual(row["owner_task"], addendum["same_owner_task"])
            for raw in row["allowed_paths"]:
                path = Path(raw) if Path(raw).is_absolute() else ROOT / raw
                resolved = path.resolve()
                self.assertEqual(resolved, path.absolute(), "symlink or relative-path escape")
                self.assertTrue(resolved.is_relative_to(ROOT) or
                                row["id"] == "v0_auth_session_transport" and resolved.is_relative_to(frontend))
                self.assertFalse(any(resolved == p or resolved in p.parents or p in resolved.parents
                                     for p in owned), "overlapping writers")
                owned.append(resolved)
                if raw not in side["new_paths"] and not raw.startswith(".agent/"):
                    self.assertTrue(path.is_file(), raw)
            for stable in leaf["stable_inputs"]:
                path = Path(stable["path"])
                self.assertEqual(digest(path if path.is_absolute() else ROOT / path), stable["sha256"])

    def _assert_completed_remaining_oracles(self, stage, capsule, assurance) -> None:
        # The implementation capsule preserves its dispatch-time side work.
        # Acceptance comes from the later independent assurance, not those slots.
        self.assertEqual(stage["status"], "accepted")
        self.assertEqual(capsule["status"], "implementation_complete_pending_assurance")
        self.assertEqual(capsule["parallel_budget"], 4)
        self.assertEqual([row["id"] for row in capsule["assignments"]], [
            "v0_data_only_connection", "v0_local_release_operations",
            "v0_frontend_route_attribution_correction", "v0_monitoring_intent_contract",
        ])
        result = capsule["implementation_result"]
        self.assertEqual(result["closure_seal_sha256"],
                         "b9164d768ec23315d28c00644b204677ea6e8bb6889a07ebd1fa9d08e2e535ae")
        self.assertEqual(hashlib.sha256((ROOT / result["closure_seal"]).read_bytes()).hexdigest(),
                         result["closure_seal_sha256"])
        self.assertFalse(result["independent_assurance"])
        self.assertFalse(result["publication"])
        self.assertFalse(result["deployment"])
        self.assertEqual(assurance["status"], "accepted")
        self.assertEqual(assurance["depends_on"], [stage["id"]])
        self.assertNotEqual(assurance["owner_task"], stage["owner_task"])
        accepted = assurance["assurance_result"]
        self.assertEqual(accepted["verdict"], "ASSURANCE PASS")
        self.assertEqual(accepted["closure_seal_sha256"],
                         "b7ce6f3559b4482f5ce5af23fe848131548d3634e27b8060f15c84e957a2683c")
        self.assertFalse(accepted["publication"])
        self.assertFalse(accepted["deployment"])

    def _assert_session_prefix_successor(self, stage, capsule, implementation) -> None:
        """The accepted successor preserves the two rejected assurance records."""
        self.assertEqual(stage["status"], "accepted")
        self.assertEqual(capsule["status"], "completed")
        self.assertEqual(capsule["verdict"], "ASSURANCE PASS")
        correction = stage["previous_assurance"]
        self.assertEqual(capsule["dependency_gate"], "post-phase5-indicator-accuracy-session-prefix-correction")
        self.assertEqual(frontmatter(ROOT / correction["capsule"])["id"], capsule["dependency_gate"])
        self.assertEqual(stage["component_scope"], implementation["component_scope"])
        self.assertEqual(len(stage["component_scope"]), 31)
        self.assertTrue(capsule["independence"]["owner_must_differ"])
        self.assertFalse(capsule["independence"]["history_fork"])
        self.assertEqual(capsule["independence"]["product_edits"], 0)
        self.assertIn("paper-trader/backend/app", capsule["protected_paths"])
        self.assertEqual((capsule["model_route"]["owner"], capsule["model_route"]["owner_reasoning_effort"]),
                         ("gpt-5.6-sol", "medium"))
        closure = capsule["closure"]
        result = stage["assurance_result"]
        self.assertEqual(result["closure_seal_sha256"],
                         "9e83c61486d7b58a3ed500418cff5709e671653f674f5b6900a4d319f56d35ab")
        self.assertEqual(hashlib.sha256((ROOT / closure["closure_seal"]).read_bytes()).hexdigest(),
                         result["closure_seal_sha256"])
        seal = load_json(ROOT / closure["closure_seal"])
        self.assertEqual(seal["verdict"], "ASSURANCE PASS")
        self.assertEqual(seal["counts"]["decisions"], 31)
        self.assertEqual(seal["counts"]["corrected_session_open"], 8)
        for claim in ("publication", "deployment"):
            self.assertFalse(result[claim])
            self.assertFalse(closure[claim])
            self.assertFalse(seal[claim])
        for suffix in ("session-data-assurance", "session-data-fresh-assurance"):
            rejected = frontmatter(ROOT / f"paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-{suffix}.md")
            self.assertEqual(rejected["status"], "rejected")

    def _assert_completed_session_data_boundary(self, stage, capsule) -> None:
        """Verify retained stage evidence without making it today's active owner."""
        self.assertEqual(stage["status"], "accepted")
        self.assertEqual(capsule["status"], "accepted")
        self.assertEqual(stage["parallel_carry_in"], capsule["parallel_carry_in"])
        carry = capsule["parallel_carry_in"]
        self.assertEqual(hashlib.sha256((ROOT / carry["path"]).read_bytes()).hexdigest(), carry["sha256"])
        decision = load_json(ROOT / carry["path"])
        self.assertEqual(decision["decision"], "ACCEPT_MULTI_OUTPUT_SOURCE_ASSURANCE_AND_START_SESSION_DATA")
        self.assertEqual(decision["to"], stage["id"])
        for claim in ("publication", "deployment", "v0_complete"):
            self.assertFalse(decision[claim])
        serial = capsule["serial_context_binding_correction"]
        self.assertEqual(stage["serial_context_binding_correction"], serial)
        self.assertFalse(serial["session_product_frozen"])
        self.assertEqual(hashlib.sha256((ROOT / serial["path"]).read_bytes()).hexdigest(), serial["sha256"])
        assurance = serial["assurance"]
        self.assertEqual(assurance["status"], "accepted")
        self.assertEqual(assurance["seal_sha256"],
                         "4c04161d7d390914981f8f8fe56eee549faf0cca854267d4fbcb61e21e2b91ef")
        seal_path = ROOT / assurance["seal"]
        self.assertEqual(hashlib.sha256(seal_path.read_bytes()).hexdigest(), assurance["seal_sha256"])
        seal = load_json(seal_path)
        self.assertEqual(seal["verdict"], "ASSURANCE PASS")
        self.assertFalse(seal["publication"])
        self.assertEqual(seal["counts"]["legacy_identities_exact"], 125)
        self.assertEqual(seal["counts"]["candidate_binding_contracts_exact"], 84)
        self.assertEqual(stage["parallel_assignments"], capsule["assignments"])

    def _assert_session_data_parallel_boundary(self, programme, stage, capsule) -> None:
        """Carry the two unrelated V0 leaves without widening numerical ownership."""
        import hashlib

        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(stage["id"], "post-phase5-indicator-accuracy-session-data")
        self.assertEqual(programme["current_stage_id"], stage["id"])
        self.assertEqual(stage["status"], "active")
        self.assertEqual(capsule["status"], "active")
        self.assertEqual(capsule["owner_task"], "01a04ac0-ee97-7230-9ffb-1f4e6cdbf1d6")
        self.assertEqual(capsule["numerical_parallel_budget"], 0)
        self.assertEqual(capsule["parallel_budget"], 2)

        decision_path = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-data/coordinator/decision.json"
        ref = {"path": str(decision_path.relative_to(ROOT)),
               "sha256": "bfd15300a9691fbce64348338ba2e79cf28355622e93bdd488f0edf089d90392"}
        self.assertEqual(digest(decision_path), ref["sha256"])
        self.assertEqual(capsule["parallel_carry_in"], ref)
        self.assertEqual(stage["parallel_carry_in"], ref)
        current = frontmatter(ROOT / "paper-trader/docs/agent/CURRENT.md")
        self.assertEqual(current["active_stage"], stage["id"])
        self.assertEqual(current["active_capsule"],
                         "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-data.md")
        self.assertEqual(current["parallel_development"]["current_carry"], ref)
        self.assertEqual(programme["parallel_development"]["current_carry"], ref)
        decision = load_json(decision_path)
        self.assertEqual(decision["decision"], "ACCEPT_MULTI_OUTPUT_SOURCE_ASSURANCE_AND_START_SESSION_DATA")
        self.assertEqual((decision["from"], decision["to"]),
                         ("post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance",
                          stage["id"]))
        self.assertEqual(decision["assurance_seal_sha256"],
                         "4f936a7df88c636953cabb9057d7ad65afbaef7586b3289fea95de4c3c711a32")
        self.assertEqual(digest(ROOT / decision["assurance_seal"]), decision["assurance_seal_sha256"])
        self.assertEqual(decision["historical_red"], {"native": 20, "F03": 9, "archived_old_source": 1})
        self.assertEqual(decision["q01_authority_resolution"]["sha256"],
                         "77419c37626400eac23efb6f42d708b2fc6884323630931eb3220b304730f882")
        self.assertEqual(decision["q01_authority_resolution"]["corrected_package_sha256"],
                         "05b8bc5dfeefe869cba3444ee560e9a3a906beaf6144fa40b6ea26f6a4d4b889")
        self.assertEqual(decision["q01_authority_resolution"]["recheck_request_sha256"],
                         "352cd9681fdd78f5a6be9403de0e71b8dc0708795ff89bffc64fe46903cd4d09")
        self.assertEqual(decision["q01_authority_resolution"]["recheck_routing"], {
            "path": ".agent/runs/strategy-os-v0-auth-session-transport/recheck-routing.json",
            "sha256": "05f9d3d71dd16e40671610844aa003bb23597628a454b2c34ad7c9258a7dccce",
            "review_iteration": 2,
            "used": 1,
            "remaining": 0,
            "same_authoritative_reviewer": True,
        })
        self.assertEqual(decision["q03_review_routing"]["sha256"],
                         "57755d149ea2d53ef41fcc9a91f83a974d65c36867d34558ea6ae5363167e37e")
        self.assertEqual(decision["q03_review_routing"]["duplicate_reviewers"], 0)
        q03_addendum_path = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-data/coordinator/q03-review-addendum.json"
        q03_addendum_ref = {"path": str(q03_addendum_path.relative_to(ROOT)),
                            "sha256": "b6f637d626bbe0ef5d3b7268b1a1f83a7625dbd74e9a88e7ab64e5b487752bf7"}
        self.assertEqual(digest(q03_addendum_path), q03_addendum_ref["sha256"])
        self.assertEqual(capsule["parallel_q03_review_addendum"], q03_addendum_ref)
        self.assertEqual(stage["parallel_q03_review_addendum"], q03_addendum_ref)
        self.assertEqual(current["parallel_development"]["q03_review_addendum"], q03_addendum_ref)
        self.assertEqual(programme["parallel_development"]["q03_review_addendum"], q03_addendum_ref)
        q03_addendum = load_json(q03_addendum_path)
        self.assertEqual(q03_addendum["q03_review_result"]["sha256"],
                         "f3cbdf3b532197923319d33ff3a8ce18da0126f1f39eafc86c94faf546a8acc2")
        self.assertEqual(q03_addendum["q03_correction"]["sha256"],
                         "1e71fd528843d738fce3787759bed4124f56202eaed94835379455904dc37a2b")
        self.assertEqual((q03_addendum["q03_review_result"]["SPEC"],
                          q03_addendum["q03_review_result"]["QUALITY"],
                          q03_addendum["q03_review_result"]["final"]),
                         ("PASS", "FAIL", "FAIL"))
        self.assertFalse(q03_addendum["q03_acceptance"])
        recovery_path = ROOT / ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/routing/decision.json"
        recovery_ref = {"path": str(recovery_path.relative_to(ROOT)),
                        "sha256": "0ec242dfe91a931354d80b1819f6b6923d20192adfc611a06020b9b5a4f963b1"}
        recovery = load_json(recovery_path)
        self.assertEqual(digest(recovery_path), recovery_ref["sha256"])
        self.assertEqual(capsule["parallel_q01_evidence_recovery"], recovery_ref)
        self.assertEqual(stage["parallel_q01_evidence_recovery"], recovery_ref)
        self.assertEqual(current["parallel_development"]["q01_evidence_recovery"], recovery_ref)
        self.assertEqual(programme["parallel_development"]["q01_evidence_recovery"], recovery_ref)
        self.assertEqual(recovery["exhausted_recheck"], {"SPEC": "PASS", "QUALITY": "FAIL",
            "product_findings_open": 0, "rechecks_used": 1, "rechecks_remaining": 0})
        recovery_capsule = frontmatter(ROOT / recovery["assignment"]["capsule"])
        self.assertEqual(recovery_capsule["status"], "accepted")
        self.assertEqual(recovery_capsule["owner_task"], recovery["assignment"]["owner_task"])
        self.assertEqual(recovery_capsule["allowed_paths"], recovery["assignment"]["allowed_paths"])
        self.assertEqual(recovery_capsule["acceptance_result"]["verdict_sha256"],
                         "8576d6db175ea4e6287b19d32ca4b270b273ed959099bbd7d04ac224e77405c9")
        correction_path = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/routing/decision.json"
        correction_ref = {"path": str(correction_path.relative_to(ROOT)),
                          "sha256": "432a852ebe62d604837e41618ff7b8b24c08d12bcacaf8be06b2f62a942dafbe"}
        correction = load_json(correction_path)
        self.assertEqual(digest(correction_path), correction_ref["sha256"])
        self.assertEqual(correction["decision"],
                         "FREEZE_SESSION_DATA_AND_ROUTE_SERIAL_THREE_FIELD_GRAMMAR_CORRECTION")
        self.assertEqual(correction["owner_task"], "01a04b00-dbce-7d40-a15d-2234b756bce2")
        self.assertTrue(correction["session_data_product_frozen"])
        serial = capsule["serial_context_binding_correction"]
        self.assertEqual({key: serial[key] for key in ("path", "sha256")}, correction_ref)
        self.assertEqual(stage["serial_context_binding_correction"], serial)
        correction_capsule = frontmatter(ROOT / serial["capsule"])
        self.assertEqual(correction_capsule["status"], "assigned_waiting_sealed_START")
        self.assertEqual(correction_capsule["owner_task"], correction["owner_task"])
        self.assertEqual(correction_capsule["allowed_paths"], correction["allowed_paths"])
        self.assertEqual(correction_capsule["parallel_budget"], 0)
        self.assertEqual(correction_capsule["assignments"], [])
        loader_path = ROOT / ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/review-correction/loader-amendment/decision.json"
        loader_ref = {"path": str(loader_path.relative_to(ROOT)),
                      "sha256": "10f0ca0bb91d7572714cfb5ff9e808b98320bc1d7c9ceec31aa05e44889ff2f4"}
        loader = load_json(loader_path)
        self.assertEqual(digest(loader_path), loader_ref["sha256"])
        self.assertEqual(capsule["parallel_q03_loader_amendment"], loader_ref)
        self.assertEqual(stage["parallel_q03_loader_amendment"], loader_ref)
        self.assertEqual(current["parallel_development"]["q03_loader_amendment"], loader_ref)
        self.assertEqual(programme["parallel_development"]["q03_loader_amendment"], loader_ref)
        self.assertEqual(loader["decision"], "AUTHORIZE_REQUEST_LOCAL_POST_VERIFICATION_MEMO_ONLY")
        self.assertTrue(loader["same_reviewer_recheck"])
        self.assertEqual(decision["q02_pre_dispatch"]["status"],
                         "QUEUED_REBIND_REQUIRED_AFTER_Q01_ACCEPTANCE")
        self.assertFalse(decision["q02_pre_dispatch"]["active_assignment"])
        for claim in ("publication", "deployment", "v0_complete"):
            self.assertFalse(decision[claim])

        transition_assignments = decision["parallel_assignments"]
        assignments = capsule["assignments"]
        transition_q03 = next(row for row in transition_assignments if row["id"] == "v0_canonical_dataset_bridge")
        current_q03 = next(row for row in programme["parallel_development"]["completed_assignments"]
                           if row["id"] == "v0_canonical_dataset_bridge")
        ignored_q03 = {"status", "allowed_paths", "SPEC", "QUALITY", "review_seal_sha256"}
        self.assertEqual({key: value for key, value in transition_q03.items() if key not in ignored_q03},
                         {key: value for key, value in current_q03.items() if key not in ignored_q03})
        self.assertEqual(current_q03["allowed_paths"], transition_q03["allowed_paths"] + [
            "paper-trader/backend/app/market_data/observations.py",
            "paper-trader/backend/research/domain/strategy_admissions.py",
        ])
        self.assertEqual(assignments, [])
        self.assertEqual(assignments, stage["parallel_assignments"])
        self.assertEqual(assignments, programme["parallel_development"]["active_assignments"])
        self.assertEqual(assignments, current["parallel_development"]["active_assignments"])
        self.assertEqual(current_q03["status"], "accepted")
        q03_capsule = frontmatter(ROOT / current_q03["capsule"])
        self.assertEqual(q03_capsule["status"], "accepted")
        self.assertEqual(q03_capsule["acceptance_result"]["recheck_seal_sha256"],
                         "6a9ef774e8c5ccfc8320c342cb3364ba9385290a0e2b07fa5d15d5f2ca17177b")
        owned = [(ROOT / path).resolve() for path in capsule["allowed_paths"]]
        frontend = Path("/Users/priyanshusaraf/dev/strategy-os-frontend").resolve()
        for row in assignments:
            self.assertEqual((row["model"], row["reasoning_effort"], row["fork_turns"]),
                             ("gpt-5.6-sol", "medium", "none"))
            self.assertFalse(row["primary_programme_owner"])
            for raw in row["allowed_paths"]:
                path = Path(raw) if Path(raw).is_absolute() else ROOT / raw
                resolved = path.resolve()
                self.assertTrue(resolved.is_relative_to(ROOT) or
                                row["id"] == "v0_auth_session_transport" and resolved.is_relative_to(frontend))
                self.assertFalse(any(resolved == p or resolved in p.parents or p in resolved.parents
                                     for p in owned), "overlapping session-data/parallel writers")
                owned.append(resolved)

    def _assert_parallel_leaf_boundary(self, programme, stage, capsule) -> None:
        import hashlib

        self.assertIn(stage["id"], {
            "post-phase5-indicator-accuracy-multi-output",
            "post-phase5-indicator-accuracy-multi-output-assurance",
        })
        self.assertEqual(programme["current_stage_id"], stage["id"])
        self.assertEqual(stage["status"], "active")
        self.assertEqual(capsule["numerical_parallel_budget"], 0)
        authority = capsule["parallel_leaf_authority"]
        self.assertEqual(authority, stage["parallel_leaf_authority"])
        self.assertFalse(authority["public_capability_opening"])
        self.assertFalse(authority["publication"])
        self.assertFalse(authority["deployment"])
        replan = ROOT / ".agent/runs/strategy-os-v0-parallel-workstream-replan"
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        parent_stage = stage["id"]
        carried_ids = set()
        queued_extension = None
        if capsule.get("parallel_queue_extension"):
            queued_path = ROOT / ".agent/runs/strategy-os-v0-parallel-next-leaf-materialization/leaf-decision.json"
            self.assertEqual(capsule["parallel_queue_extension"], {
                "path": str(queued_path.relative_to(ROOT)),
                "sha256": "b71c1c0404ecbd601b26938aacf86ca5c16da60a3d73a169bdde0bc52daa5b6c",
            })
            self.assertEqual(digest(queued_path), capsule["parallel_queue_extension"]["sha256"])
            queued_extension = load_json(queued_path)
            self.assertEqual(stage["id"], "post-phase5-indicator-accuracy-multi-output-assurance")
            self.assertEqual(queued_extension["primary_stage"], stage["id"])
            self.assertEqual(queued_extension["decision"], "AUTHORIZE_EXACT_QUEUED_LEAVES")
            self.assertEqual({row["queue_id"] for row in queued_extension["leaves"]}, {"Q04", "Q06"})
            self.assertEqual({row["assignment"] for row in queued_extension["leaves"]}, {"v0_annotation_geometry", "v0_worker_quota_recovery"})
            self.assertTrue(queued_extension["existing_owners_and_paths_unchanged"])
            self.assertEqual(queued_extension["maximum_assignments"], 4)
            self.assertEqual(queued_extension["numerical_parallel_budget"], 0)
            self.assertFalse(queued_extension["public_capability_opening"])
            self.assertFalse(queued_extension["publication"])
            self.assertFalse(queued_extension["deployment"])
        if stage["id"] == "post-phase5-indicator-accuracy-multi-output-assurance":
            carry_path = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output/routing/carry-decision.json"
            self.assertEqual(capsule["parallel_carry_in"], {
                "path": str(carry_path.relative_to(ROOT)),
                "sha256": "32270b3a3b7476a35a4c96100b86057f70e7869bfc57f4c634eda413c1bca131",
            })
            self.assertEqual(digest(carry_path), capsule["parallel_carry_in"]["sha256"])
            carry = load_json(carry_path)
            self.assertEqual(carry["to"], stage["id"])
            self.assertEqual(carry["from"], "post-phase5-indicator-accuracy-multi-output")
            self.assertEqual(capsule["owner_task"], carry["owner_task"])
            self.assertEqual(digest(ROOT / carry["predecessor_seal"]), carry["predecessor_seal_sha256"])
            self.assertFalse(carry["numerical_independent_acceptance"])
            self.assertFalse(carry["public_capability_opening"])
            self.assertFalse(carry["path_ownership_changes"])
            self.assertEqual(carry["numerical_parallel_budget"], 0)
            carried_ids = {"v0_static_scope_foundation", "v0_static_scope_authorization"}
            queued_ids = {row["assignment"] for row in queued_extension["leaves"]} if queued_extension else set()
            self.assertEqual({a["id"] for a in capsule["assignments"]}, carried_ids | queued_ids)
            self.assertEqual(len(capsule["assignments"]), len(carry["assignments"]) + len(queued_ids))
            carried = [row for row in capsule["assignments"] if row["id"] in carried_ids]
            for actual, original in zip(carried, carry["assignments"], strict=True):
                # Progress status may advance; identity, route and ownership cannot.
                self.assertEqual({k: v for k, v in actual.items() if k != "status"},
                                 {k: v for k, v in original.items() if k != "status"})
            predecessor = next(item for item in programme["stages"] if item["id"] == carry["from"])
            self.assertEqual(predecessor["status"], "accepted")
            prior_capsule = frontmatter(ROOT / predecessor["capsule"])
            self.assertEqual(prior_capsule["assignments"], [])
            self.assertEqual(prior_capsule["parallel_budget"], 0)
            self.assertEqual(prior_capsule["parallel_carry_out"], capsule["parallel_carry_in"])
            parent_stage = carry["from"]
        self.assertEqual(digest(replan / "closure-seal.json"),
                         "37fe5c736a1ae169e08be985ec27fcf615b377419977e577da4445ff1da334ec")
        sealed = load_json(replan / "closure-seal.json")
        self.assertEqual(digest(replan / "leaf-ownership.json"), sealed["artifacts_sha256"]["leaf-ownership.json"])
        self.assertEqual(digest(replan / "leaf-ownership.json"), authority["ownership_sha256"])
        expected = {leaf["assignment"]: leaf for leaf in load_json(replan / "leaf-ownership.json")}
        if authority.get("addenda"):
            addition = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/static-authorization/decision.json"
            self.assertEqual(authority["addenda"], [{"path": str(addition.relative_to(ROOT)),
                "sha256": "33cd9d89e098086073372b0d4bb08d67a22ff4e12884b7161413be9567e199db"}])
            self.assertEqual(digest(addition), authority["addenda"][0]["sha256"])
            amendment = load_json(addition)
            self.assertEqual(amendment["decision"], "AUTHORIZE_BOUNDED_CORRECTION")
            self.assertFalse(amendment["public_capability_opening"])
            accepted = programme["parallel_leaf_acceptances"][amendment["requires_leaf_acceptance"]]
            self.assertEqual(accepted["status"], "accepted")
            self.assertEqual(digest(ROOT / accepted["closure_seal"]), amendment["predecessor_seal_sha256"])
            self.assertNotIn(amendment["replaces_completed_assignment"], [row["id"] for row in capsule["assignments"]])
            expected[amendment["leaf"]["assignment"]] = amendment["leaf"]
            if authority.get("path_input_addendum"):
                path_input = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/static-authorization/path-input/decision.json"
                self.assertEqual(authority["path_input_addendum"], {"path": str(path_input.relative_to(ROOT)),
                    "sha256": "345be871b2762caf5f1a54b33f2c197ab0d9769d8d98e7cb974e994f562f50a3"})
                self.assertEqual(digest(path_input), authority["path_input_addendum"]["sha256"])
                transport = load_json(path_input)
                self.assertEqual(transport["superseded_leaf_definition_sha256"], digest(addition))
                self.assertTrue(transport["same_owner_and_goal"])
                self.assertFalse(transport["public_capability_opening"])
                prior = programme["parallel_leaf_acceptances"][transport["requires_completed_assignment"]]
                self.assertEqual(prior["status"], "accepted")
                self.assertEqual(digest(ROOT / prior["closure_seal"]), transport["predecessor_seal_sha256"])
                self.assertNotIn(transport["requires_completed_assignment"], [row["id"] for row in capsule["assignments"]])
                expected[transport["leaf"]["assignment"]] = transport["leaf"]
        if queued_extension:
            self.assertEqual(digest(replan / "queue.json"), queued_extension["queue_sha256"])
            geometry_contract = ROOT / ".agent/runs/strategy-os-v0-parallel-next-leaf-materialization/geometry-contract.md"
            self.assertEqual(digest(geometry_contract), queued_extension["geometry_contract_sha256"])
            for leaf in queued_extension["leaves"]:
                self.assertNotIn(leaf["assignment"], expected)
                expected[leaf["assignment"]] = leaf
        self.assertEqual(set(authority["permitted_assignment_ids"]), set(expected))
        assignments = capsule["assignments"]
        self.assertEqual(assignments, stage["parallel_assignments"])
        self.assertEqual(assignments, programme["parallel_development"]["assignments"])
        self.assertEqual(capsule["parallel_budget"], len(assignments))
        self.assertTrue(1 <= len(assignments) <= 4)
        ids = [row["id"] for row in assignments]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids) <= set(expected))
        owned = [(ROOT / path).resolve() for path in capsule["allowed_paths"][:2]]
        frontend = Path("/Users/priyanshusaraf/dev/strategy-os-frontend").resolve()
        for row in assignments:
            leaf = expected[row["id"]]
            self.assertEqual(row["kind"], "bounded_parallel_implementation")
            self.assertEqual((row["model"], row["reasoning_effort"], row["fork_turns"]), ("gpt-5.6-sol", "medium", "none"))
            self.assertFalse(row["primary_programme_owner"])
            self.assertIsInstance(row["owner_task"], str)
            self.assertTrue(row["owner_task"])
            self.assertEqual(row["capsule"], leaf["capsule_path"])
            self.assertEqual(row["allowed_paths"], leaf["allowed_paths"])
            side = frontmatter(ROOT / row["capsule"])
            draft_path = ROOT / leaf["draft_capsule"] if "draft_capsule" in leaf else replan / "drafts" / Path(row["capsule"]).name
            self.assertEqual(digest(draft_path), leaf["draft_sha256"] if "draft_sha256" in leaf else sealed["artifacts_sha256"]["drafts/" + draft_path.name])
            draft = frontmatter(draft_path)
            for key in ("allowed_paths", "scope", "acceptance", "dependency_gate", "new_paths"):
                self.assertEqual(side[key], draft[key])
            self.assertEqual(side["owner_task"], row["owner_task"])
            self.assertEqual(side["parallel_budget"], 0)
            self.assertEqual(side["assignments"], [])
            self.assertFalse(side["programme_assignment"]["primary_programme_owner"])
            self.assertEqual(side["programme_assignment"]["parent_stage"], parent_stage if row["id"] in carried_ids else stage["id"])
            dependency = next(item for item in programme["stages"] if item["id"] == side["dependency_gate"])
            self.assertEqual(dependency["status"], "accepted")
            for raw in row["allowed_paths"]:
                path = Path(raw) if Path(raw).is_absolute() else ROOT / raw
                resolved = path.resolve()
                self.assertEqual(resolved, path.absolute(), "symlink or relative-path escape")
                self.assertTrue(resolved.is_relative_to(ROOT) or
                                row["id"] == "v0_shell_access_revalidation" and resolved.is_relative_to(frontend))
                self.assertFalse(any(resolved == other or resolved in other.parents or other in resolved.parents for other in owned), "overlapping writers")
                owned.append(resolved)
                if raw not in side["new_paths"] and not raw.startswith(".agent/"):
                    self.assertTrue(path.is_file(), raw)
        # Leaf implementations must not silently open the server capabilities.
        profile = "paper-trader/backend/app/core/release_profile.py"
        pinned = next(item["sha256"] for leaf in expected.values() for item in leaf["stable_inputs"] if item["path"] == profile)
        self.assertEqual(digest(ROOT / profile), pinned)

    def test_indicator_accuracy_plan_is_complete_serial_and_gates_catalogue(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        indexed = {stage["id"]: stage for stage in programme["stages"]}
        rejected_id = "post-phase5-indicator-accuracy-core-math-assurance"
        self.assertNotIn(rejected_id, indexed)
        rejected = next(item for item in programme["historical_blocked_reviews"]
                        if item["id"] == rejected_id)
        self.assertEqual(rejected["verdict"], "ASSURANCE REJECT")
        self.assertFalse(rejected["historical_classification"]["executable_acceptance"])
        self.assertEqual(rejected["replacement_chain"], [
            "post-phase5-indicator-accuracy-core-parameter-correction",
            "post-phase5-indicator-accuracy-core-return-stability-correction",
            "post-phase5-indicator-accuracy-core-correction-assurance",
        ])
        latest_rejected_id = "post-phase5-indicator-accuracy-core-correction-assurance"
        self.assertNotIn(latest_rejected_id, indexed)
        latest_rejected = next(item for item in programme["historical_blocked_reviews"]
                               if item["id"] == latest_rejected_id)
        self.assertEqual(latest_rejected["verdict"], "ASSURANCE REJECT")
        self.assertFalse(latest_rejected["historical_classification"]["executable_acceptance"])
        self.assertEqual(latest_rejected["replacement_chain"], [
            "post-phase5-indicator-accuracy-core-level-moment-correction",
            "post-phase5-indicator-accuracy-core-level-moment-assurance",
        ])
        recursive_rejected_id = "post-phase5-indicator-accuracy-recursive-state-assurance"
        self.assertNotIn(recursive_rejected_id, indexed)
        recursive_rejected = next(item for item in programme["historical_blocked_reviews"]
                                  if item["id"] == recursive_rejected_id)
        self.assertEqual(recursive_rejected["verdict"], "ASSURANCE REJECT")
        self.assertFalse(recursive_rejected["historical_classification"]["executable_acceptance"])
        self.assertEqual(recursive_rejected["replacement_chain"], [
            "post-phase5-indicator-accuracy-recursive-sar-source-replan",
            "post-phase5-indicator-accuracy-recursive-sar-source-correction",
            "post-phase5-indicator-accuracy-recursive-sar-source-assurance",
        ])
        multi_rejected_id = "post-phase5-indicator-accuracy-multi-output-assurance"
        self.assertNotIn(multi_rejected_id, indexed)
        multi_rejected = next(item for item in programme["historical_blocked_reviews"]
                              if item["id"] == multi_rejected_id)
        self.assertEqual(multi_rejected["verdict"], "ASSURANCE REJECT")
        self.assertFalse(multi_rejected["historical_classification"]["executable_acceptance"])
        self.assertEqual(multi_rejected["replacement_chain"], [
            "post-phase5-indicator-accuracy-multi-output-source-replan",
            "post-phase5-indicator-accuracy-multi-output-correction",
            "post-phase5-indicator-accuracy-multi-output-correction-assurance",
        ])
        source_decision = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output-source-replan/decision.json"
        self.assertEqual(hashlib.sha256(source_decision.read_bytes()).hexdigest(),
                         "f954430f5b7981078faf609fba47a0754187f3923f2ae2dc596368a18c3e271a")
        source_stage = indexed["post-phase5-indicator-accuracy-multi-output-source-replan"]
        self.assertEqual(source_stage["status"], "accepted")
        for identifier in ("post-phase5-indicator-accuracy-multi-output-correction",
                           "post-phase5-indicator-accuracy-multi-output-correction-assurance"):
            record = indexed.get(identifier) or next(item for item in programme["historical_blocked_reviews"]
                                                     if item["id"] == identifier)
            bound_capsule = frontmatter(ROOT / record["capsule"])
            self.assertEqual(bound_capsule["source_decision"], {
                "path": str(source_decision.relative_to(ROOT)),
                "sha256": "f954430f5b7981078faf609fba47a0754187f3923f2ae2dc596368a18c3e271a",
            })
        band_rejected_id = "post-phase5-indicator-accuracy-multi-output-correction-assurance"
        self.assertNotIn(band_rejected_id, indexed)
        band_rejected = next(item for item in programme["historical_blocked_reviews"] if item["id"] == band_rejected_id)
        self.assertEqual(band_rejected["verdict"], "ASSURANCE REJECT")
        self.assertFalse(band_rejected["historical_classification"]["executable_acceptance"])
        self.assertEqual(band_rejected["replacement_chain"], [
            "post-phase5-indicator-accuracy-multi-output-band-ppo-source-replan",
            "post-phase5-indicator-accuracy-multi-output-band-ppo-source-correction",
            "post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance",
        ])
        band_decision = ROOT / ".agent/runs/post-phase5-indicator-accuracy-multi-output-band-ppo-source-replan/decision.json"
        self.assertEqual(hashlib.sha256(band_decision.read_bytes()).hexdigest(),
                         "2ca3e31e074984d1545af8a0a98ea718fbaf2ad093552ec651672df8ae6213f1")
        for identifier in band_rejected["replacement_chain"][1:]:
            bound_capsule = frontmatter(ROOT / indexed[identifier]["capsule"])
            self.assertEqual(bound_capsule["source_decision"], {
                "path": str(band_decision.relative_to(ROOT)),
                "sha256": "2ca3e31e074984d1545af8a0a98ea718fbaf2ad093552ec651672df8ae6213f1",
            })
        predecessor = "post-phase5-indicator-accuracy-correction-replan"
        for stage_id in INDICATOR_CORRECTION_STAGES:
            self.assertIn(stage_id, indexed)
            stage = indexed[stage_id]
            self.assertEqual(stage["depends_on"], [predecessor])
            capsule = frontmatter(ROOT / stage["capsule"])
            if stage_id == "post-phase5-indicator-accuracy-session-prefix-fresh-assurance":
                self._assert_session_prefix_successor(stage, capsule, indexed[predecessor])
                predecessor = stage_id
                continue
            self.assertEqual(capsule["dependency_gate"], predecessor)
            if stage_id == "post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance" and capsule.get("parallel_auth_dataset_authority"):
                if stage["status"] == "active":
                    self._assert_auth_dataset_parallel_boundary(programme, stage, capsule)
                else:
                    self.assertEqual(stage["status"], "accepted")
                    self.assertEqual(capsule["status"], "accepted")
                    self.assertEqual(capsule["acceptance_result"]["closure_seal_sha256"],
                                     "4f936a7df88c636953cabb9057d7ad65afbaef7586b3289fea95de4c3c711a32")
            elif stage_id == "post-phase5-indicator-accuracy-session-data" and capsule.get("parallel_carry_in"):
                if stage["status"] == "active":
                    self._assert_session_data_parallel_boundary(programme, stage, capsule)
                else:
                    self._assert_completed_session_data_boundary(stage, capsule)
            elif stage_id in {"post-phase5-indicator-accuracy-multi-output", "post-phase5-indicator-accuracy-multi-output-assurance"} and capsule.get("parallel_leaf_authority") and capsule.get("assignments"):
                self._assert_parallel_leaf_boundary(programme, stage, capsule)
            elif stage_id == "post-phase5-indicator-accuracy-multi-output" and capsule.get("parallel_carry_out"):
                self.assertEqual(stage["status"], "accepted")
                self.assertEqual(capsule["parallel_budget"], 0)
                self.assertEqual(capsule["assignments"], [])
                self.assertEqual(capsule["parallel_carry_out"], {
                    "path": ".agent/runs/post-phase5-indicator-accuracy-multi-output/routing/carry-decision.json",
                    "sha256": "32270b3a3b7476a35a4c96100b86057f70e7869bfc57f4c634eda413c1bca131",
                })
            elif stage_id == "post-phase5-indicator-accuracy-multi-output" and capsule.get("parallel_development_authorization"):
                # The owner opened one unrelated read-only dependency replan,
                # not another numerical writer or an early catalogue gate.
                self.assertEqual(capsule["numerical_parallel_budget"], 0)
                self.assertEqual(capsule["parallel_budget"], 1)
                self.assertEqual(len(capsule["assignments"]), 1)
                assignment = capsule["assignments"][0]
                self.assertEqual(assignment["id"], "v0_parallel_dependency_replan")
                self.assertEqual(assignment["kind"], "bounded_read_only_architecture")
                self.assertFalse(assignment["primary_programme_owner"])
                self.assertEqual((assignment["model"], assignment["reasoning_effort"], assignment["fork_turns"]),
                                 ("gpt-5.6-sol", "medium", "none"))
                side_path = "paper-trader/docs/agent/tasks/strategy-os-v0-parallel-workstream-replan.md"
                side_run = ".agent/runs/strategy-os-v0-parallel-workstream-replan"
                self.assertEqual(assignment["capsule"], side_path)
                self.assertEqual(assignment["allowed_paths"], [side_path, side_run])
                self.assertEqual(stage["parallel_assignments"], capsule["assignments"])
                side = frontmatter(ROOT / side_path)
                self.assertEqual(side["allowed_paths"], assignment["allowed_paths"])
                self.assertEqual(side["parallel_budget"], 0)
                self.assertEqual(side["assignments"], [])
                self.assertEqual(side["programme_assignment"]["parent_stage"], stage_id)
                self.assertEqual(side["programme_assignment"]["assignment_id"], assignment["id"])
                for protected in ("paper-trader/backend", "paper-trader/frontend",
                                  "/Users/priyanshusaraf/dev/strategy-os-frontend",
                                  "paper-trader/docs/agent/CURRENT.md",
                                  "paper-trader/docs/agent/programme/PROGRAMME.json"):
                    self.assertIn(protected, side["protected_paths"])
                    self.assertIn(protected, assignment["protected_paths"])
            elif stage_id == "post-phase5-indicator-accuracy-remaining-oracles":
                self._assert_completed_remaining_oracles(
                    stage, capsule, indexed[stage_id + "-assurance"])
            else:
                self.assertEqual(capsule["parallel_budget"], 0)
                self.assertEqual(capsule["assignments"], [])
            self.assertIn("paper-trader/backend/app/ir/first_party/analytical.py", capsule["protected_paths"])
            self.assertEqual(capsule["component_scope"], stage["component_scope"])
            self.assertEqual(capsule["model_route"]["owner"], "gpt-5.6-sol")
            self.assertEqual(capsule["model_route"]["owner_reasoning_effort"], "high" if stage_id.endswith("-final-review") else "medium")
            predecessor = stage_id
        self.assertEqual(indexed["strategy-os-v0-verified-language-catalogue"]["depends_on"], [predecessor])

        # Independent source enumeration: do not trust the generated matrix count.
        tree = ast.parse((ROOT / "paper-trader/backend/app/ir/first_party/analytical.py").read_text())
        assignments = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
                       for target in node.targets if isinstance(target, ast.Name)}
        text = next(node.value for node in ast.walk(assignments["REQUIRED_NAMES"])
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and "ACCUMULATION_DISTRIBUTION" in node.value)
        expected = set(text.split()) | set(ast.literal_eval(assignments["CAPABILITY_GATED_NAMES"]))
        self.assertEqual(len(expected), 125)
        assigned = []
        owned_paths = set()
        for suffix in ("core-math", "recursive-state", "multi-output", "session-data", "remaining-oracles"):
            row = indexed["post-phase5-indicator-accuracy-" + suffix]
            assigned.extend(row["component_scope"])
            capsule = frontmatter(ROOT / row["capsule"])
            product_paths = {path for path in capsule["allowed_paths"] if path.startswith("paper-trader/backend/")}
            self.assertTrue(product_paths)
            self.assertTrue(owned_paths.isdisjoint(product_paths))
            owned_paths.update(product_paths)
            assurance_id = ("post-phase5-indicator-accuracy-core-level-moment-assurance" if suffix == "core-math" else
                            "post-phase5-indicator-accuracy-recursive-sar-source-assurance" if suffix == "recursive-state" else
                            "post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance" if suffix == "multi-output" else
                            "post-phase5-indicator-accuracy-session-prefix-fresh-assurance" if suffix == "session-data" else row["id"] + "-assurance")
            assurance_stage = indexed[assurance_id]
            assurance = frontmatter(ROOT / assurance_stage["capsule"])
            if suffix == "session-data":
                self.assertEqual(assurance_stage["component_scope"], row["component_scope"])
                self.assertTrue(assurance["independence"]["owner_must_differ"])
            else:
                self.assertEqual(assurance["component_scope"], row["component_scope"])
                self.assertIn("different owner", assurance["independence"])
        self.assertEqual(len(assigned), 125)
        self.assertEqual(set(assigned), expected)
        final = frontmatter(ROOT / indexed[predecessor]["capsule"])
        self.assertEqual(final["review"]["verdicts"], ["SPEC", "QUALITY"])
        self.assertEqual(final["review"]["agent"], "critical-reviewer")
        self.assertEqual(final["review"]["max_rechecks"], 1)
        self.assertTrue(any("analytical_v2" in path for path in final["review"]["review_paths"]))
        self.assertNotIn("post-phase5-indicator-accuracy-deferred-source-replan", indexed)

    def test_accepted_failed_recheck_capsules_bind_fresh_successor_passes(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        for stage in programme["stages"]:
            capsule_value = stage.get("capsule")
            if not isinstance(capsule_value, str):
                continue
            capsule_path = ROOT / capsule_value
            if capsule_path.suffix != ".md":
                continue
            capsule = frontmatter(capsule_path)
            if stage["status"] != "accepted" or capsule["status"] != "failed_recheck_exhausted":
                continue
            with self.subTest(stage=stage["id"]):
                lineage = stage["acceptance_lineage"]
                self.assertEqual(lineage["source_capsule_status"], "failed_recheck_exhausted")
                self.assertEqual(lineage["disposition"], "discharged_by_fresh_successor")
                successor_capsule = ROOT / lineage["successor_capsule"]
                successor = frontmatter(successor_capsule)
                self.assertEqual(successor["status"], "accepted")
                self.assertEqual(
                    hashlib.sha256(successor_capsule.read_bytes()).hexdigest(),
                    lineage["successor_capsule_sha256"],
                )
                verdict = ROOT / lineage["successor_verdict"]
                self.assertTrue(verdict.is_file())
                self.assertEqual(
                    hashlib.sha256(verdict.read_bytes()).hexdigest(),
                    lineage["successor_verdict_sha256"],
                )
                self.assertEqual(lineage["spec"], "PASS")
                self.assertEqual(lineage["quality"], "PASS")
                self.assertEqual(lineage["open_findings"], 0)

    def _assert_historical_leaf_dispatch(self, suffix, queue_id, assignment_id, decision_sha, rebind_sha):
        """Original queueing and later dispatch are separate retained facts."""
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        current = frontmatter(ROOT / "paper-trader/docs/agent/CURRENT.md")
        folder = ROOT / f".agent/runs/strategy-os-v0-{suffix}-materialization"
        decision_path = folder / "leaf-decision.json"
        ref = {"path": str(decision_path.relative_to(ROOT)), "sha256": decision_sha}
        self.assertEqual(programme["parallel_development"]["queued_materializations"][queue_id], ref)
        self.assertEqual(current["parallel_development"]["queued_materializations"][queue_id], ref)
        self.assertEqual(hashlib.sha256(decision_path.read_bytes()).hexdigest(), decision_sha)
        decision = load_json(decision_path)
        self.assertEqual((decision["queue_id"], decision["assignment"]), (queue_id, assignment_id))
        self.assertEqual(decision["status"], "QUEUED_NOT_DISPATCHED")
        for claim in ("active_assignment", "publication", "deployment", "v0_complete"):
            self.assertFalse(decision[claim])
        self.assertNotIn(assignment_id, {row["id"] for row in programme["parallel_development"]["active_assignments"]})
        capsule = frontmatter(ROOT / decision["capsule_path"])
        self.assertEqual(capsule["programme_assignment"]["assignment_id"], assignment_id)
        self.assertFalse(capsule["programme_assignment"]["primary_programme_owner"])
        self.assertEqual(capsule["allowed_paths"], decision["allowed_paths"])
        self.assertEqual(capsule["new_paths"], decision["new_paths"])
        self.assertEqual(hashlib.sha256((ROOT / decision["contract"]["path"]).read_bytes()).hexdigest(),
                         decision["contract"]["sha256"])
        self.assertEqual((capsule["review"]["agent"], capsule["review"]["model"],
                          capsule["review"]["reasoning_effort"], capsule["review"]["max_rechecks"]),
                         ("critical-reviewer", "gpt-5.6-sol", "high", 1))
        self.assertEqual(capsule["parallel_budget"], 0)
        self.assertEqual(capsule["assignments"], [])
        self.assertFalse(capsule["stable_inputs_rebind_at_dispatch"])
        binding = capsule["stable_input_rebind"]
        self.assertEqual(binding["status"], "accepted")
        self.assertTrue(binding["actual_start"])
        rebind_path = ROOT / binding["path"]
        self.assertEqual(rebind_path, folder / "stable-input-rebind.json")
        self.assertEqual(hashlib.sha256(rebind_path.read_bytes()).hexdigest(), rebind_sha)
        rebind = load_json(rebind_path)
        self.assertEqual(rebind["queue_id"], queue_id)
        self.assertEqual(rebind["decision"], "STABLE_INPUTS_REBOUND_DISPATCH_ALLOWED")
        self.assertEqual(rebind["status"], "ACTUAL_START_ALLOWED")
        self.assertEqual(rebind["owner_task"], capsule["programme_assignment"]["owner_task"])
        self.assertEqual(rebind["allowed_paths"], capsule["allowed_paths"])
        self.assertFalse(rebind["deployment"])
        for raw in decision["allowed_paths"]:
            path = ROOT / raw
            self.assertEqual(path.resolve(), path.absolute(), "dispatch path escapes through a symlink")
            self.assertTrue(path.resolve().is_relative_to(ROOT))
        return capsule, decision

    def test_q14_historical_dispatch_preserves_rejected_recheck_and_successor(self) -> None:
        capsule, decision = self._assert_historical_leaf_dispatch(
            "local-release-operations", "Q14", "v0_local_release_operations",
            "11dc26472752a4eaaf2ec14609fa1fda8aafac74bc50608aadcc73699f93ca34",
            "2bc6a85ee6fd274bf77690ddbc4555f8b866c173ae911ccb765f2720cbbe85e5")
        self.assertEqual(decision["decision"], "MATERIALIZE_Q14_AWAIT_REVIEWED_SLOT")
        self.assertFalse(decision["public_capability_opening"])
        self.assertEqual(capsule["status"], "rejected_replan_required")
        result = capsule["exhausted_recheck"]
        self.assertEqual(result["verdict"], "SPEC FAIL / QUALITY FAIL")
        self.assertEqual((result["rechecks_used"], result["rechecks_remaining"]), (1, 0))
        self.assertEqual(result["finding"], "F3-OUTPUT-EXIT-RACE")
        self.assertEqual(result["verdict_sha256"],
                         "5fb543b1b345b72ace441b5f98cbf8b419d1346e46738ccad3103726baaf5a9d")
        self.assertEqual(hashlib.sha256((ROOT / result["verdict_path"]).read_bytes()).hexdigest(),
                         result["verdict_sha256"])
        successor = frontmatter(ROOT / result["successor"])
        self.assertEqual(successor["id"], "strategy-os-v0-local-release-output-exit-race-correction")

    def test_q02_historical_dispatch_preserves_local_acceptance_without_capability_opening(self) -> None:
        capsule, decision = self._assert_historical_leaf_dispatch(
            "data-only-connection", "Q02", "v0_data_only_connection",
            "d743dcfb0c52bbb01c249758476df956c26818765b30cfbce424a5e6f931a352",
            "d67a76bbd26a8d4cc79ef0d04739b47ccf49e74efff78508d55ed6e87d1de3ff")
        self.assertEqual(decision["decision"], "MATERIALIZE_Q02_AWAIT_Q01_REVIEWED_SLOT")
        self.assertFalse(decision["capability_open"])
        self.assertFalse(decision["provider_network"])
        self.assertEqual(capsule["status"], "accepted")
        result = capsule["final_review"]
        self.assertEqual(result["verdict"], "SPEC PASS / QUALITY PASS")
        self.assertEqual((result["rechecks_used"], result["rechecks_remaining"]), (1, 0))
        self.assertEqual(result["verdict_sha256"],
                         "36c0f3aa79e962d406e94a3b48f632fa913ee915d08d5ea02ebc49aa2e1f90f9")
        self.assertEqual(hashlib.sha256((ROOT / result["verdict_path"]).read_bytes()).hexdigest(),
                         result["verdict_sha256"])
        self.assertFalse(result["capability_open"])
        self.assertFalse(result["deployment"])



if __name__ == "__main__":
    unittest.main()
