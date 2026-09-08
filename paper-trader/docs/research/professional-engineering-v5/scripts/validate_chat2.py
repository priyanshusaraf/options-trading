"""Dependency-free validation for Strategy OS Chat 2 V5 deliverables."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "docs/research/professional-engineering-v5"
ARCH = ROOT / "docs/architecture"
SOURCE_REGISTRY = ROOT / "docs/engineering-references/source-registry.yaml"
CLAIM_REGISTRY = ROOT / "docs/engineering-references/claim-registry.jsonl"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def markdown_relative_links(path: Path) -> list[Path]:
    targets: list[Path] = []
    for raw in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
        target = raw.strip().split("#", 1)[0]
        if not target or "://" in target or target.startswith(("#", "repository:")):
            continue
        targets.append((path.parent / target).resolve())
    return targets


def main() -> None:
    required_packet = [
        "13-BROADER-SOURCE-CATALOG.md",
        "13-BROADER-SOURCE-REGISTRY.json",
        "14-ACADEMIC-PDF-AND-COURSE-NOTES-PACKET.md",
        "15-SENIOR-ENGINEER-AND-COMPANY-PRACTICES-PACKET.md",
        "16-QUANT-RESEARCH-VALIDITY-PACKET.md",
        "17-SECURITY-RELIABILITY-AND-SUPPLY-CHAIN-PACKET.md",
        "18-SOURCE-CONFLICTS-AND-REJECTED-CARGO-CULT.md",
        "19-SOURCE-TO-CODE-MATRIX.md",
        "20-CONSOLIDATED-SOURCE-TO-DECISION-MATRIX.md",
        "20-CHAT2-CLAIM-REGISTRY.jsonl",
        "21-CONFIRMED-BACKEND-RISK-REGISTER.md",
        "22-IMPLEMENTATION-CANDIDATE-GATE.md",
        "23-CHANGES-MADE-AND-VERIFICATION.md",
        "24-CHANGES-DELIBERATELY-NOT-MADE.md",
        "25-RESIDUAL-RISK-AND-OPEN-QUESTIONS.md",
    ]
    required_arch = [
        ARCH / "intelligence/index.md",
        ARCH / "FUTURE-RELEASE-BACKEND-SEAMS-AND-ADOPTION-TRIGGERS.md",
        ARCH / "SCALE-50-TO-10000-MEASURED-TRIGGERS.md",
        ROOT / "docs/strategy-os-v1-v2-v3/adr/README.md",
    ]
    required = [PACKET / name for name in required_packet] + required_arch
    missing = [str(path) for path in required if not path.is_file()]
    require(not missing, f"missing deliverables: {missing}")

    detailed_sources = json.loads((PACKET / required_packet[1]).read_text())
    require(detailed_sources["count"] == 52, "detailed source count")
    source_rows = detailed_sources["sources"]
    require(len(source_rows) == 52, "detailed source rows")
    source_ids = [row["id"] for row in source_rows]
    require(len(source_ids) == len(set(source_ids)), "duplicate detailed source ID")
    require(
        {"database", "temporal", "reliability", "money", "quant", "security", "workflow", "scale"}
        <= {row["family"] for row in source_rows},
        "missing source family",
    )

    detailed_claims = jsonl(PACKET / "20-CHAT2-CLAIM-REGISTRY.jsonl")
    require(len(detailed_claims) == 10, "detailed Chat 2 claim count")
    require(len({row["claim_id"] for row in detailed_claims}) == 10, "duplicate Chat 2 claim")

    standing_sources = json.loads(SOURCE_REGISTRY.read_text())["sources"]
    standing_claims = jsonl(CLAIM_REGISTRY)
    require(len(standing_sources) == 69, "standing source count")
    require(len(standing_claims) == 53, "standing claim count")
    require(len({row["source_id"] for row in standing_sources}) == 69, "standing source IDs")
    require(len({row["claim_id"] for row in standing_claims}) == 53, "standing claim IDs")
    require(
        sum(row["source_id"] == "STRATEGY_OS_CHAT2_V5_BROADER_SOURCES_20260831"
            for row in standing_sources) == 1,
        "missing standing source bundle",
    )
    require(
        sum(row["claim_id"].startswith("CHAT2-V5-") for row in standing_claims) == 10,
        "standing Chat 2 claims",
    )

    markdown = [path for path in required if path.suffix == ".md"]
    prohibited = re.compile(
        r"\b(?:delve|foster|leverage)\b|it's worth noting|importantly",
        re.IGNORECASE,
    )
    offenders = [str(path) for path in markdown if prohibited.search(path.read_text())]
    require(not offenders, f"plain-writing guard: {offenders}")

    broken: list[str] = []
    for path in markdown:
        for target in markdown_relative_links(path):
            if not target.exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    require(not broken, f"broken relative links: {broken}")

    intelligence = (ARCH / "intelligence/index.md").read_text()
    require(intelligence.count("```mermaid") >= 10, "architecture diagram count")
    for marker in [
        "BROKEN",
        "PARTIAL",
        "UNKNOWN",
        "DEFERRED BY DESIGN",
        "PROVEN WORKING",
    ]:
        require(marker in intelligence, f"missing diagnosis marker: {marker}")

    decisions = (PACKET / "20-CONSOLIDATED-SOURCE-TO-DECISION-MATRIX.md").read_text()
    for marker in ["Redis", "Temporal", "DBOS", "Restate", "Kafka", "V0 blocker"]:
        require(marker in decisions, f"missing decision marker: {marker}")

    print(json.dumps({
        "deliverables": len(required),
        "detailed_sources": len(source_rows),
        "detailed_claims": len(detailed_claims),
        "standing_sources": len(standing_sources),
        "standing_claims": len(standing_claims),
        "mermaid_diagrams": intelligence.count("```mermaid"),
        "relative_links_checked": sum(len(markdown_relative_links(path)) for path in markdown),
        "source_registry_sha256": hashlib.sha256(SOURCE_REGISTRY.read_bytes()).hexdigest(),
        "claim_registry_sha256": hashlib.sha256(CLAIM_REGISTRY.read_bytes()).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
