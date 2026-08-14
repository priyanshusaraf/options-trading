from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = ROOT / ".codex" / "scripts" / "programme_dispatcher.py"


class ProgrammeDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.repo = Path(self.tempdir.name)
        (self.repo / "paper-trader" / "docs" / "agent" / "programme").mkdir(parents=True)
        (self.repo / "paper-trader" / "docs" / "agent" / "tasks").mkdir(parents=True)
        (self.repo / ".agent" / "programme").mkdir(parents=True)
        self.capsule_path = "paper-trader/docs/agent/tasks/correction.md"
        self.write_capsule(self.capsule_path)
        self.write_source_map()

    def write_capsule(self, relative: str) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "id": Path(relative).stem,
            "goal": "Repair the rejected gate with current evidence.",
            "goal_contract": {
                "create_before_work": True,
                "stopping_condition": "Complete only after the exact gate passes.",
            },
        }
        path.write_text(f"---\n{json.dumps(data)}\n---\n", encoding="utf-8")

    def write_source_map(self) -> None:
        data = {
            "schema_version": 1,
            "sources": [
                {
                    "id": "verification",
                    "path": "paper-trader/docs/source.md",
                    "sha256": "0" * 64,
                    "sections": [
                        {"level": 2, "heading": "Gate", "consumers": ["phase3", "phase4"]}
                    ],
                }
            ],
            "phase_views": {
                "phase3": [{"source_id": "verification", "heading": "Gate"}],
                "phase4": [{"source_id": "verification", "heading": "Gate"}],
            },
        }
        (self.repo / "paper-trader" / "docs" / "agent" / "programme" / "SOURCE_MAP.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def stage(
        self,
        stage_id: str,
        order: int,
        *,
        status: str,
        depends_on: list[str],
        kind: str = "correction",
        capsule: str | None = None,
        model: str = "gpt-5.6-terra",
        effort: str = "medium",
        phase: str = "phase3",
    ) -> dict:
        return {
            "id": stage_id,
            "order": order,
            "phase": phase,
            "kind": kind,
            "status": status,
            "depends_on": depends_on,
            "capsule": capsule,
            "model": model,
            "reasoning_effort": effort,
            "source_view": phase,
        }

    def write_programme(self, stages: list[dict], current: str, status: str = "active") -> None:
        data = {
            "schema_version": 1,
            "programme_id": "test",
            "status": status,
            "current_stage_id": current,
            "source_map": "paper-trader/docs/agent/programme/SOURCE_MAP.json",
            "controller": {"max_active_goals": 1},
            "policies": {"require_phase_review": True},
            "stages": stages,
        }
        (self.repo / "paper-trader" / "docs" / "agent" / "programme" / "PROGRAMME.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def run_dispatcher(self, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(DISPATCHER), "--root", str(self.repo), "--json", *args],
            text=True,
            capture_output=True,
            check=False,
        )
        return result, json.loads(result.stdout)

    def test_ready_stage_dispatches_exact_route_and_goal_contract(self) -> None:
        self.write_programme(
            [self.stage("correction", 1, status="ready", depends_on=[], capsule=self.capsule_path)],
            "correction",
        )
        result, action = self.run_dispatcher("--claim")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(action["action"], "dispatch")
        self.assertEqual((action["model"], action["reasoning_effort"]), ("gpt-5.6-terra", "medium"))
        self.assertEqual(action["capsule"], self.capsule_path)
        self.assertIn("Complete only after the exact gate passes", action["goal_objective"])
        controller = json.loads(
            (self.repo / ".agent" / "programme" / "controller.json").read_text()
        )
        self.assertEqual(controller["active_goal"]["stage_id"], "correction")
        self.assertEqual(controller["active_goal"]["status"], "reserved")

        second_result, second = self.run_dispatcher("--claim")
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        self.assertEqual(second["action"], "monitor")

        bind_result, bound = self.run_dispatcher(
            "--bind-thread", action["claim_id"], "thread-123"
        )
        self.assertEqual(bind_result.returncode, 0, bind_result.stderr)
        self.assertEqual(bound["action"], "monitor")
        controller = json.loads(
            (self.repo / ".agent" / "programme" / "controller.json").read_text()
        )
        self.assertEqual(controller["active_goal"]["thread_id"], "thread-123")
        self.assertEqual(controller["active_goal"]["status"], "running")

        update_result, updated = self.run_dispatcher(
            "--update-lease", action["claim_id"], "completed"
        )
        self.assertEqual(update_result.returncode, 0, update_result.stderr)
        self.assertEqual(updated["action"], "recorded")
        self.assertEqual(updated["status"], "completed")

        stopped_result, stopped = self.run_dispatcher("--claim")
        self.assertNotEqual(stopped_result.returncode, 0)
        self.assertEqual(stopped["action"], "pause")
        self.assertIn("not advanced", stopped["reason"])

    def test_existing_goal_monitors_and_second_goal_pauses(self) -> None:
        self.write_programme(
            [self.stage("correction", 1, status="ready", depends_on=[], capsule=self.capsule_path)],
            "correction",
        )
        one_result, one = self.run_dispatcher("--active-goal-count", "1")
        two_result, two = self.run_dispatcher("--active-goal-count", "2")
        self.assertEqual(one_result.returncode, 0)
        self.assertEqual(one["action"], "monitor")
        self.assertNotEqual(two_result.returncode, 0)
        self.assertEqual(two["action"], "pause")

    def test_later_phase_cannot_run_before_interphase_and_review_dependencies(self) -> None:
        phase3 = self.stage("phase3-review", 1, status="accepted", depends_on=[], kind="phase_review", capsule=self.capsule_path, model="gpt-5.6-sol", effort="high")
        interphase = self.stage("ir-review", 2, status="blocked", depends_on=["phase3-review"], kind="phase_review", capsule=self.capsule_path, model="gpt-5.6-sol", effort="high", phase="phase3")
        phase4 = self.stage("phase4-architecture", 3, status="ready", depends_on=["ir-review"], kind="phase_architecture", capsule=self.capsule_path, model="gpt-5.6-sol", effort="medium", phase="phase4")
        self.write_programme([phase3, interphase, phase4], "phase4-architecture")
        result, action = self.run_dispatcher("--claim")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(action["action"], "pause")
        self.assertIn("dependency", action["reason"].lower())

    def test_phase_review_is_dispatched_with_sol_high_before_next_phase(self) -> None:
        architecture = self.stage("phase4-architecture", 1, status="accepted", depends_on=[], kind="phase_architecture", capsule=self.capsule_path, model="gpt-5.6-sol", effort="medium", phase="phase4")
        implementation = self.stage("phase4-implementation", 2, status="accepted", depends_on=["phase4-architecture"], kind="implementation_sequence", capsule=self.capsule_path, phase="phase4")
        review = self.stage("phase4-review", 3, status="review", depends_on=["phase4-implementation"], kind="phase_review", capsule=self.capsule_path, model="gpt-5.6-sol", effort="high", phase="phase4")
        next_phase = self.stage("phase5-architecture", 4, status="blocked", depends_on=["phase4-review"], kind="phase_architecture", capsule=self.capsule_path, model="gpt-5.6-sol", effort="medium", phase="phase4")
        self.write_programme([architecture, implementation, review, next_phase], "phase4-review")
        result, action = self.run_dispatcher("--claim")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(action["action"], "dispatch")
        self.assertEqual((action["model"], action["reasoning_effort"]), ("gpt-5.6-sol", "high"))

    def test_owner_gate_and_stale_lease_pause_without_duplicate_dispatch(self) -> None:
        self.write_programme(
            [self.stage("correction", 1, status="paused_owner_gate", depends_on=[], capsule=self.capsule_path)],
            "correction",
        )
        gate_result, gate = self.run_dispatcher()
        self.assertNotEqual(gate_result.returncode, 0)
        self.assertEqual(gate["action"], "pause")

        self.write_programme(
            [self.stage("correction", 1, status="ready", depends_on=[], capsule=self.capsule_path)],
            "correction",
        )
        stale = datetime.now(timezone.utc) - timedelta(hours=7)
        controller = {
            "active_goal": {
                "thread_id": "thread-1",
                "stage_id": "correction",
                "status": "running",
                "updated_at": stale.isoformat(),
            }
        }
        (self.repo / ".agent" / "programme" / "controller.json").write_text(json.dumps(controller))
        lease_result, lease = self.run_dispatcher()
        self.assertNotEqual(lease_result.returncode, 0)
        self.assertEqual(lease["action"], "pause")
        self.assertIn("stale", lease["reason"].lower())

    def test_missing_capsule_fails_closed_and_complete_programme_stops(self) -> None:
        self.write_programme(
            [self.stage("correction", 1, status="ready", depends_on=[], capsule="paper-trader/docs/agent/tasks/missing.md")],
            "correction",
        )
        missing_result, missing = self.run_dispatcher("--claim")
        self.assertNotEqual(missing_result.returncode, 0)
        self.assertEqual(missing["action"], "pause")

        self.write_programme(
            [self.stage("release", 1, status="accepted", depends_on=[], capsule=None, kind="release_review", model="gpt-5.6-sol", effort="high")],
            "release",
            status="complete",
        )
        complete_result, complete = self.run_dispatcher()
        self.assertEqual(complete_result.returncode, 0)
        self.assertEqual(complete["action"], "complete")

    def test_false_completion_and_skipped_predecessor_fail_closed(self) -> None:
        self.write_programme(
            [self.stage("release", 1, status="ready", depends_on=[], capsule=self.capsule_path, kind="release_review", model="gpt-5.6-sol", effort="high")],
            "release",
            status="complete",
        )
        false_result, false = self.run_dispatcher("--claim")
        self.assertNotEqual(false_result.returncode, 0)
        self.assertEqual(false["action"], "pause")
        self.assertIn("complete", false["reason"].lower())

        first = self.stage("first", 1, status="accepted", depends_on=[], capsule=self.capsule_path)
        second = self.stage("second", 2, status="accepted", depends_on=["first"], capsule=self.capsule_path)
        third = self.stage("third", 3, status="ready", depends_on=["first"], capsule=self.capsule_path)
        self.write_programme([first, second, third], "third")
        skipped_result, skipped = self.run_dispatcher("--claim")
        self.assertNotEqual(skipped_result.returncode, 0)
        self.assertEqual(skipped["action"], "pause")
        self.assertIn("predecessor", skipped["reason"].lower())

    def test_unknown_goal_state_pauses_without_atomic_claim(self) -> None:
        self.write_programme(
            [self.stage("correction", 1, status="ready", depends_on=[], capsule=self.capsule_path)],
            "correction",
        )
        result, action = self.run_dispatcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(action["action"], "pause")
        self.assertIn("unknown", action["reason"].lower())

    def test_phase_view_returns_only_exact_routed_sections(self) -> None:
        self.write_programme(
            [self.stage("correction", 1, status="ready", depends_on=[], capsule=self.capsule_path)],
            "correction",
        )
        result, view = self.run_dispatcher("--phase-view", "phase4")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(view["phase"], "phase4")
        self.assertEqual(
            view["required_docs"],
            [{"path": "paper-trader/docs/source.md", "sections": ["Gate"]}],
        )


if __name__ == "__main__":
    unittest.main()
