from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRAMME_DIR = ROOT / "paper-trader" / "docs" / "agent" / "programme"
OWNER_DIR = ROOT / "paper-trader" / "docs" / "program" / "owner-steers"


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
        self.assertEqual(programme["current_stage_id"], "phase3-task12-correction-1")
        stages = programme["stages"]
        self.assertEqual([stage["order"] for stage in stages], list(range(1, len(stages) + 1)))
        indexed = {stage["id"]: stage for stage in stages}
        self.assertEqual(len(indexed), len(stages))
        self.assertEqual(indexed["phase3-task12-correction-1"]["status"], "ready")
        self.assertTrue(all(stage["status"] == "blocked" for stage in stages[1:]))

        seen = set()
        for stage in stages:
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
            review = next(stage for stage in stages if stage["id"] == f"phase{phase}-review")
            self.assertEqual((architecture["model"], architecture["reasoning_effort"]), ("gpt-5.6-sol", "medium"))
            self.assertEqual((review["model"], review["reasoning_effort"]), ("gpt-5.6-sol", "high"))
            self.assertEqual(review["kind"], "phase_review")
            self.assertIn(f"phase{phase}-implementation", review["depends_on"])

    def test_current_and_executable_capsules_use_goal_contract(self) -> None:
        programme = load_json(PROGRAMME_DIR / "PROGRAMME.json")
        current = frontmatter(ROOT / "paper-trader" / "docs" / "agent" / "CURRENT.md")
        self.assertEqual(current["programme"], "paper-trader/docs/agent/programme/PROGRAMME.json")
        self.assertEqual(current["active_capsule"], "paper-trader/docs/agent/tasks/phase3-task12-correction-1.md")

        current_stage = next(stage for stage in programme["stages"] if stage["id"] == programme["current_stage_id"])
        self.assertEqual(current_stage["capsule"], current["active_capsule"])
        capsule = frontmatter(ROOT / current_stage["capsule"])
        self.assertEqual(capsule["id"], current_stage["id"])
        self.assertEqual(capsule["goal_contract"]["create_before_work"], True)
        self.assertTrue(capsule["goal_contract"]["stopping_condition"])
        self.assertEqual(capsule["model_route"]["owner"], "gpt-5.6-terra")
        self.assertEqual(capsule["model_route"]["owner_reasoning_effort"], "medium")


if __name__ == "__main__":
    unittest.main()
