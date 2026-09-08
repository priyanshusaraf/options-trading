"""Validate the documentation-only Strategy OS release architecture package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from source_preservation import original_source


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[2]
MEMO = ROOT / "strategyos-v1-v1.1-v1.5-v2-v3-product-architecture-memo-2026-08-24.md"
SUPERSEDED_MEMO = ROOT / "strategyos-v1-v2-v3-product-architecture-memo-2026-08-19.md"
EXPECTED_MEMO_SHA256 = "087d87df2658398f89ef6b3b5a4551bac28efa2855a2d7e1e2693d63047657d8"

REQUIRED = (
    "README.md",
    "SOURCE-REGISTER.md",
    "STRATEGY_OS_HYBRID_PRODUCT_DIRECTION_AND_V1_PROGRAMME_REBASE_2026-08-24.md",
    "STRATEGY_OS_GRAND_PRODUCT_VISION_2026-08-11.md",
    "STRATEGY_OS_V1_PRODUCT_SCOPE_AND_SEQUENCE_2026-08-11.md",
    "REVISED-V1-PROGRESS-MAPPER-2026-08-24.md",
    "V1-V1.5-V2-V3-SCOPE-DECISION-MATRIX.md",
    "V1-SUBPHASE-CONTRACT-MATRIX.md",
    "CURRENT-REPOSITORY-GAP-MAP.md",
    "CONTRACT-AND-ADR-PLAN.md",
    "CANONICAL-BENCHMARKS-AND-ADVERSARIAL-TESTS.md",
    "CANONICAL-DOCUMENT-RECONCILIATION.md",
    "EXECUTIVE-SYNTHESIS.md",
    "TOP-FINDINGS.md",
    "CURRENT-STATE-AND-RISK-MAP.md",
    "REMEDIATION-PLAN.md",
    "CEO-PRIOR-ART-GATE.proposed.md",
    "repo-index.yaml",
    "strategyos-v1-v1.1-v1.5-v2-v3-product-architecture-memo-2026-08-24.md",
    "adr/0001-PRESERVE-V1-AS-ADDITIVE-FOUNDATION.md",
    "adr/0002-ONE-IR-DISTINCT-PRODUCT-OBJECTS.md",
    "adr/0003-DURABLE-PORTFOLIO-ADMISSION-AND-RESERVATION.md",
    "adr/0004-KEEP-DOMAIN-JOBS-BEFORE-WORKFLOW-DEPENDENCY.md",
    "architecture/CAPITAL-CONTENTION-AND-RESERVATION-SPEC.md",
    "architecture/DATABASE-AUTHORITY-MATRIX.md",
    "architecture/REALTIME-STATE-MACHINES.md",
    "architecture/RECONSTRUCTION-RECEIPT-SPEC.md",
    "architecture/OBSERVABILITY-AND-SLO-PLAN.md",
    "architecture/SECURITY-THREAT-MODEL.md",
    "architecture/FAILURE-SCENARIO-CATALOGUE.md",
    "architecture/DEPLOYABILITY-IMPACT.md",
    "architecture/UNIVERSE-WORKFLOW-ARCHITECTURE.md",
    "architecture/V1-V2-DECISION-MATRIX.md",
    "comparison-packets/AUTHORIZATION.md",
    "comparison-packets/BROKER-AND-REALTIME.md",
    "comparison-packets/DATA-OPTIMISATION-EVIDENCE.md",
    "comparison-packets/TRADING-SEMANTICS.md",
    "comparison-packets/VISUAL-AND-INTERACTION.md",
    "comparison-packets/WORKFLOW-DURABLE-EXECUTION.md",
    "ux/INTERACTION-AUDIT.md",
    "ux/TASK-BENCHMARK.md",
    "market/COMPETITOR-MAP.md",
    "market/CUSTOMER-JOBS-AND-SEGMENTS.md",
    "market/CATCH-UP-AND-MOAT-ANALYSIS.md",
    "discovery/NEW-REPOSITORY-BACKLOG.md",
    "discovery/TOOL-ASSET-SCORECARD.md",
    "repo-reviews/README.md",
    "repo-reviews/BACKTRADER-AND-FREQTRADE-TARGETED-REVIEW.md",
    "test-plans/V1-V2-ADVERSARIAL-BACKLOG.md",
    "validation/check_architecture_docs.py",
)

OWNER_DECISIONS = {
    "adr/0001-PRESERVE-V1-AS-ADDITIVE-FOUNDATION.md": (
        "V1 remains the accepted base.",
        "Do not reopen accepted work without a named contradiction and transitive evidence.",
        "Keep non-OHLCV product support in V2.",
    ),
}
FINAL_PRIORITIES = {
    "MUST FIX BEFORE DEPENDENT FEATURE WORK",
    "HIGH-PRIORITY HARDENING",
    "PROVEN SAFE AS IMPLEMENTED",
    "BOUNDED SPIKE REQUIRED",
    "TEST GAP",
    "DOCUMENTATION GAP",
    "REFERENCE ONLY",
    "REJECT",
}

LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SCORE = re.compile(r"^\s+score:\s+\{([^}]+)\}\s*$", re.MULTILINE)
CURRENT_PATH = re.compile(r"`(paper-trader/[^`]+)`")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_links(errors: list[str]) -> int:
    checked = 0
    for document in sorted(ROOT.rglob("*.md")):
        text = document.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            plain = target.split("#", 1)[0]
            if not plain:
                continue
            checked += 1
            resolved = (document.parent / plain).resolve()
            if not resolved.exists():
                errors.append(
                    f"broken link in {document.relative_to(ROOT)}: {target}"
                )
    return checked


def validate_repo_index(errors: list[str]) -> tuple[int, int, int]:
    path = ROOT / "repo-index.yaml"
    text = path.read_text(encoding="utf-8")
    names = re.findall(r"^  - name:\s+(.+?)\s*$", text, flags=re.MULTILINE)
    if len(names) != 33:
        errors.append(f"repo-index expected 33 entries, found {len(names)}")
    if len(set(names)) != len(names):
        errors.append("repo-index contains duplicate names")

    score_count = 0
    for row in SCORE.findall(text):
        fields: dict[str, int] = {}
        for item in row.split(","):
            key, value = item.strip().split(":", 1)
            fields[key.strip()] = int(value.strip())
        total = fields.pop("total", None)
        if total is None or sum(fields.values()) != total:
            errors.append(f"repo-index score does not add up: {row}")
        score_count += 1
    if score_count != len(names):
        errors.append(
            f"repo-index expected one score for every entry, found {score_count}"
        )

    local_paths = re.findall(
        r"^\s+local_path:\s+(.+?)\s*$", text, flags=re.MULTILINE
    )
    commits = re.findall(
        r"^\s+commit:\s+([0-9a-f]{12,40})\s*$", text, flags=re.MULTILINE
    )
    licences = re.findall(r"^\s+licence:\s+(.+?)\s*$", text, flags=re.MULTILINE)
    if len(local_paths) != len(names):
        errors.append(
            f"repo-index expected one local path for every entry, found {len(local_paths)}"
        )
    if len(commits) != len(names):
        errors.append(
            f"repo-index expected one commit for every entry, found {len(commits)}"
        )
    if len(licences) != len(names):
        errors.append(
            f"repo-index expected one licence for every entry, found {len(licences)}"
        )
    for raw in local_paths:
        if not Path(raw).exists():
            errors.append(f"repo-index local path is absent: {raw}")

    heads_checked = 0
    for raw, recorded in zip(local_paths, commits, strict=False):
        if not Path(raw).is_dir():
            continue
        result = subprocess.run(
            ["git", "-C", raw, "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"repo-index local path is not a readable Git clone: {raw}")
            continue
        actual = result.stdout.strip()
        heads_checked += 1
        if not actual.startswith(recorded):
            errors.append(
                f"repo-index commit drift for {raw}: expected {recorded}, found {actual}"
            )
    return len(names), score_count, heads_checked


def validate_owner_decisions(errors: list[str]) -> int:
    checked = 0
    for relative, decisions in OWNER_DECISIONS.items():
        path = ROOT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for decision in decisions:
            checked += 1
            if decision not in text:
                errors.append(f"owner decision is absent from {relative}: {decision}")
    return checked


def validate_risk_priorities(errors: list[str]) -> int:
    path = ROOT / "CURRENT-STATE-AND-RISK-MAP.md"
    if not path.is_file():
        return 0
    checked = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| R-"):
            continue
        checked += 1
        priority = line.split("|")[-2].strip()
        if priority not in FINAL_PRIORITIES:
            errors.append(f"risk finding has invalid final priority: {line}")
    if checked < 14:
        errors.append(f"expected at least 14 classified risk findings, found {checked}")
    return checked


def validate_current_paths(errors: list[str]) -> int:
    path = ROOT / "TOP-FINDINGS.md"
    if not path.is_file():
        return 0
    references = CURRENT_PATH.findall(path.read_text(encoding="utf-8"))
    for relative in references:
        if not (REPOSITORY_ROOT / relative).is_file():
            errors.append(f"top finding references an absent current file: {relative}")
    return len(references)


def validate_memo_source(errors: list[str]) -> None:
    if MEMO.is_file():
        try:
            original = original_source(MEMO.relative_to(REPOSITORY_ROOT).as_posix())
            if hashlib.sha256(original).hexdigest() != EXPECTED_MEMO_SHA256:
                errors.append("memo original hash does not match the supplied source")
        except (ValueError, KeyError, OSError) as exc:
            errors.append(f"memo source preservation failed: {exc}")


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required artifact: {relative}")

    validate_memo_source(errors)
    if SUPERSEDED_MEMO.exists():
        errors.append("superseded product memo is still present")

    links_checked = validate_links(errors)
    repo_count, score_count, repo_heads_checked = validate_repo_index(errors)
    owner_decisions_checked = validate_owner_decisions(errors)
    risk_priorities_checked = validate_risk_priorities(errors)
    current_paths_checked = validate_current_paths(errors)

    programme_path = REPOSITORY_ROOT / "paper-trader" / "docs" / "agent" / "programme" / "PROGRAMME.json"
    programme = json.loads(programme_path.read_text(encoding="utf-8"))
    completion_text = " ".join(programme.get("completion_conditions", []))
    if "Phase 5 through Phase 13" not in completion_text:
        errors.append("programme completion conditions do not require revised Phase 5-13 reviews")
    if "v1-release-review" not in completion_text:
        errors.append("programme completion conditions do not require the terminal v1-release-review")
    if programme.get("stages", [])[-1].get("id") != "v1-release-review":
        errors.append("programme terminal stage is not v1-release-review")

    subphase_text = (ROOT / "V1-SUBPHASE-CONTRACT-MATRIX.md").read_text(encoding="utf-8")
    subphase_ids = re.findall(r"^\| (P(?:5|6|7|8|9|10|11|12|13)\.\d+)\b", subphase_text, flags=re.MULTILINE)
    if len(subphase_ids) != 54 or len(set(subphase_ids)) != 54:
        errors.append(f"expected 54 unique subphase contracts, found {len(subphase_ids)} rows and {len(set(subphase_ids))} unique IDs")

    comparison_count = len(list((ROOT / "comparison-packets").glob("*.md")))
    if comparison_count != 6:
        errors.append(f"expected six comparison packets, found {comparison_count}")

    failure_text = (
        ROOT / "architecture" / "FAILURE-SCENARIO-CATALOGUE.md"
    ).read_text(encoding="utf-8")
    failure_count = len(
        re.findall(r"^\| F-\d{3} \|", failure_text, flags=re.MULTILINE)
    )
    if failure_count < 30:
        errors.append(f"expected at least 30 failure scenarios, found {failure_count}")

    test_text = (
        ROOT / "test-plans" / "V1-V2-ADVERSARIAL-BACKLOG.md"
    ).read_text(encoding="utf-8")
    test_count = len(
        re.findall(r"^### T0-\d{2}:", test_text, flags=re.MULTILINE)
    ) + len(
        re.findall(r"^\| T[12]-\d{2} \|", test_text, flags=re.MULTILINE)
    )
    if test_count < 30:
        errors.append(f"expected at least 30 adversarial tests, found {test_count}")

    result = {
        "root": str(ROOT),
        "required_artifacts": len(REQUIRED),
        "markdown_files": len(list(ROOT.rglob("*.md"))),
        "relative_links_checked": links_checked,
        "owner_decisions_checked": owner_decisions_checked,
        "risk_priorities_checked": risk_priorities_checked,
        "repo_entries": repo_count,
        "repo_heads_checked": repo_heads_checked,
        "repo_scores_checked": score_count,
        "comparison_packets": comparison_count,
        "current_paths_checked": current_paths_checked,
        "failure_scenarios": failure_count,
        "adversarial_tests": test_count,
        "memo_readable_sha256": sha256(MEMO) if MEMO.is_file() else None,
        "memo_original_expected_sha256": EXPECTED_MEMO_SHA256,
        "superseded_memo_absent": not SUPERSEDED_MEMO.exists(),
        "programme_completion_requires_phase13": "Phase 5 through Phase 13" in completion_text,
        "programme_completion_requires_release_review": "v1-release-review" in completion_text,
        "subphase_contract_rows": len(subphase_ids),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
