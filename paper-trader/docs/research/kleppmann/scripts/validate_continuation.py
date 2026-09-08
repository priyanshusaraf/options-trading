#!/usr/bin/env python3
"""Validate the bounded artifact/DDIA continuation without product imports."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[5]
CORPUS = ROOT / "paper-trader/docs/research/kleppmann"
REFERENCES = ROOT / "paper-trader/docs/engineering-references"


def json_doc(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def relative_links(path: Path) -> list[Path]:
    missing = []
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]+)?\)", path.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("mailto:"):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            missing.append(resolved)
    return missing


def main() -> None:
    manifest = jsonl(CORPUS / "corpus-manifest.jsonl")
    triage = jsonl(CORPUS / "one-hop-triage.jsonl")
    deferred = jsonl(CORPUS / "deferred-external-links.jsonl")
    coverage = json_doc(CORPUS / "coverage.json")
    triage_summary = json_doc(CORPUS / "artifact-triage-summary.json")
    pdfs = json_doc(CORPUS / "pdf-review-ledger.json")
    source_reviews = json_doc(CORPUS / "source-reviews.json")
    source_registry = json_doc(REFERENCES / "source-registry.yaml")
    claims = jsonl(REFERENCES / "claim-registry.jsonl")
    gap = json_doc(CORPUS / "architecture-gap-matrix.json")

    assert len(manifest) == 373
    assert len({row["source_id"] for row in manifest}) == 373
    assert len({row["canonical_url"] for row in manifest}) == 373
    with (CORPUS / "corpus-manifest.csv").open(newline="", encoding="utf-8") as handle:
        assert sum(1 for _ in csv.DictReader(handle)) == 373

    assert len(deferred) == len(triage) == 2016
    assert {row["url"] for row in deferred} == {row["url"] for row in triage}
    assert triage_summary["input_records"] == triage_summary["output_records"] == 2016
    assert triage_summary["input_sha256"] == hashlib.sha256(
        (CORPUS / "deferred-external-links.jsonl").read_bytes()
    ).hexdigest()
    assert triage_summary["html_crawl_rerun"] is False
    assert sum(triage_summary["categories"].values()) == 2016
    assert sum(triage_summary["dispositions"].values()) == 2016

    assert coverage["first_party_content_records"] == 373
    assert coverage["external_direct_links_recorded"] == 2016
    assert coverage["external_direct_links_triaged"] == 2016
    assert coverage["external_direct_links_pending_triage"] == 0
    assert coverage["html_crawl_rerun_for_continuation"] is False
    assert coverage["review_statuses"] == {"not_read": 366, "fully_read": 7}
    assert coverage["selected_pdf_count_directly_inspected"] == 4
    assert coverage["selected_pdf_pages_directly_inspected"] == 320

    assert pdfs["totals"] == {"pdfs": 4, "pages": 320, "embedded_image_objects": 237}
    for row in pdfs["sources"]:
        receipt = ROOT / row["receipt"]
        assert receipt.is_file()
        review = json_doc(receipt)
        assert review["page_count"] == row["pages"]
        assert review["source_sha256"] == row["sha256"]
        assert len(review["pages"]) == row["pages"]
        assert all(page["direct_visual_inspection"] for page in review["pages"])
        assert review["visual_state"] == "direct_contact_sheet_inspection_complete"

    manifest_urls = {row["canonical_url"] for row in manifest}
    assert set(source_reviews) <= manifest_urls
    for row in manifest:
        if row["review_status"] == "fully_read":
            assert source_reviews[row["canonical_url"]]["status"] == "fully_read"

    source_ids = [row["source_id"] for row in source_registry["sources"]]
    assert len(source_ids) == len(set(source_ids))
    required_sources = {
        "CAMBRIDGE_DISTSYS_2022",
        "KLEPPMANN_STREAM_PROCESSING_2016",
        "KLEPPMANN_OLEP_2019",
        "KLEPPMANN_LOCAL_FIRST_2019",
        "HERMITAGE_F029BEC8",
        "DDIA2_OFFICIAL_TOC_2026",
        "DDIA2_REFERENCES_1752CBD0",
        "REDLOCK_COUNTERANALYSIS_2016_CURRENT",
    }
    assert required_sources <= set(source_ids)

    claim_ids = [row["claim_id"] for row in claims]
    assert len(claim_ids) == len(set(claim_ids))
    required_claims = {f"KCA-{number:03d}" for number in range(1, 10)}
    assert required_claims <= set(claim_ids)
    required_fields = {
        "claim_id", "claim", "source_id", "citation", "source_date_version",
        "system_assumptions", "strategy_os_invariant", "failure_hypothesis",
        "repository_evidence", "smallest_safe_response", "verification",
        "migration_rollback", "release_owner", "applicability_decision",
        "release_classification", "verification_status",
    }
    source_id_set = set(source_ids)
    for row in claims:
        if row["claim_id"] not in required_claims:
            continue
        assert required_fields <= set(row), row["claim_id"]
        assert row["source_id"] in source_id_set
        assert row["repository_evidence"]
        for supporting in row.get("supporting_source_ids", []):
            assert supporting in source_id_set

    gap_ids = [row["finding_id"] for row in gap]
    assert len(gap_ids) == len(set(gap_ids))
    assert {f"KREF-{number:03d}" for number in range(1, 9)} <= set(gap_ids)

    inaccessible = (CORPUS / "inaccessible-sources.md").read_text(encoding="utf-8")
    assert "unavailable and not read" in inaccessible
    assert "HTTP 403" in inaccessible
    assert "2,016 external links now have reproducible triage" in inaccessible

    markdown = [
        CORPUS / "00-README.md",
        CORPUS / "02-STRATEGY-OS-CONTINGENCY-CATALOGUE.md",
        CORPUS / "04-ARCHITECTURE-GAP-MATRIX.md",
        CORPUS / "05-PRIORITY-READING-MAP.md",
        CORPUS / "07-IMPLEMENTATION-AND-MIGRATION-PLAN.md",
        CORPUS / "12-DDIA-2E-DELTA-FOR-STRATEGY-OS.md",
        CORPUS / "21-CORPUS-ARTIFACTS-AND-DDIA2E-REVIEW.md",
        CORPUS / "source-notes/2026-08-29-artifacts-and-ddia2e.md",
        REFERENCES / "00-README.md",
        REFERENCES / "reading-packets/2026-08-29-kleppmann-artifacts-ddia2e.md",
        REFERENCES / "rejected-patterns/2026-08-29-corpus-artifacts-and-ddia2e.md",
    ]
    missing = [(path, target) for path in markdown for target in relative_links(path)]
    assert not missing, missing

    print(json.dumps({
        "verdict": "PASS",
        "manifest_records": len(manifest),
        "triage_records": len(triage),
        "fully_read_first_party_records": coverage["review_statuses"]["fully_read"],
        "pdfs_directly_inspected": pdfs["totals"]["pdfs"],
        "pages_directly_inspected": pdfs["totals"]["pages"],
        "new_claims": sorted(required_claims),
        "new_findings": [f"KREF-{number:03d}" for number in range(4, 9)],
        "html_crawl_rerun": False,
        "product_changes": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
