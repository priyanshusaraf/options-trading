"""Dependency-free validation for the V5 Kleppmann audit packet."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "docs/research/professional-engineering-v5"
SOURCE_PATH = ROOT / "docs/engineering-references/source-registry.yaml"
CLAIM_PATH = ROOT / "docs/engineering-references/claim-registry.jsonl"

SOURCE_FIELDS = {
    "source_id",
    "primary_or_secondary",
}
V5_SOURCE_FIELDS = {
    "source_id",
    "title",
    "author_or_presenter",
    "organisation_or_institution",
    "canonical_url",
    "publication_or_update_date",
    "access_date",
    "content_type",
    "primary_or_secondary",
    "license_or_reuse_note",
    "availability_status",
    "locations_inspected",
    "figures_tables_inspected",
    "system_problem_context",
    "strategy_os_relevance_score",
    "confidence",
    "notes_path",
}
CLAIM_FIELDS = {
    "claim_id",
    "source_id",
    "exact_location",
    "concise_source_supported_claim",
    "source_assumption_system_model",
    "codex_inference",
    "strategy_os_repository_mapping",
    "potential_failure_hypothesis",
    "current_future_release_classification",
    "recommended_response",
    "verification_required",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    sources_doc = json.loads(SOURCE_PATH.read_text())
    sources = sources_doc["sources"]
    source_ids = [row["source_id"] for row in sources]
    require(len(source_ids) == len(set(source_ids)), "duplicate source_id")
    for row in sources:
        require(SOURCE_FIELDS <= row.keys(), f"base source shape: {row.get('source_id')}")
        if row["source_id"].endswith("_V5") or row["source_id"].startswith("STRATEGY_OS_V5_"):
            missing = V5_SOURCE_FIELDS - row.keys()
            require(not missing, f"V5 source fields {row['source_id']}: {sorted(missing)}")
        digest = row.get("artifact_sha256")
        if digest is not None:
            require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
                    f"bad artifact_sha256: {row['source_id']}")

    claims = [json.loads(line) for line in CLAIM_PATH.read_text().splitlines() if line.strip()]
    claim_ids = [row["claim_id"] for row in claims]
    require(len(claim_ids) == len(set(claim_ids)), "duplicate claim_id")
    for row in claims:
        require(row["source_id"] in set(source_ids),
                f"unknown source {row['claim_id']}: {row['source_id']}")
        if row["claim_id"].startswith("KPV5-"):
            missing = CLAIM_FIELDS - row.keys()
            require(not missing, f"claim fields {row.get('claim_id')}: {sorted(missing)}")

    with (PACKET / "01-KLEPPMANN-CORPUS-MANIFEST.csv").open(newline="") as handle:
        manifest = list(csv.DictReader(handle))
    require(len(manifest) == 375, f"manifest count: {len(manifest)}")
    manifest_ids = [row["source_id"] for row in manifest]
    require(len(manifest_ids) == len(set(manifest_ids)), "duplicate manifest source_id")
    required_manifest = {
        "source_id", "title", "author_presenter", "organisation_institution",
        "canonical_url", "access_date", "content_type", "primary_secondary_status",
        "license_reuse_note", "availability_status", "pages_sections_timestamps_inspected",
        "figures_tables_inspected", "system_problem_context", "strategy_os_relevance_score",
        "confidence", "notes_path", "v5_review_status", "sha256",
    }
    for row in manifest:
        missing = [field for field in required_manifest if not row[field].strip()]
        require(not missing, f"manifest blank {row['source_id']}: {missing}")
        digest = row["sha256"]
        require(
            digest == "UNAVAILABLE"
            or (len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)),
            f"manifest digest {row['source_id']}",
        )

    required_docs = ["00", *[f"{index:02d}" for index in range(2, 13)]]
    present = {path.name[:2] for path in PACKET.glob("*.md")}
    require(set(required_docs) <= present, f"missing numbered documents: {set(required_docs) - present}")

    print(json.dumps({
        "sources": len(sources),
        "claims": len(claims),
        "v5_claims": sum(row["claim_id"].startswith("KPV5-") for row in claims),
        "manifest_rows": len(manifest),
        "manifest_reviewed": sum(row["v5_review_status"] != "INVENTORIED_ONLY" for row in manifest),
        "numbered_documents": len(list(PACKET.glob("*.md"))),
        "source_registry_sha256": hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(),
        "claim_registry_sha256": hashlib.sha256(CLAIM_PATH.read_bytes()).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
