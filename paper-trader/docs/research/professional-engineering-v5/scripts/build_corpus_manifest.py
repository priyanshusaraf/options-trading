#!/usr/bin/env python3
"""Build the V5 corpus manifest from fresh crawl evidence and explicit reviews.

The crawler inventory records retrieval only. This producer never upgrades a source
to reviewed from its title, fetch status, prior review, or the existence of cached
bytes. V5 review state comes only from the explicit override file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


FIELDS = [
    "source_id",
    "title",
    "author_presenter",
    "organisation_institution",
    "canonical_url",
    "publication_update_date",
    "publication_date_basis",
    "access_date",
    "content_type",
    "primary_secondary_status",
    "license_reuse_note",
    "availability_status",
    "pages_sections_timestamps_inspected",
    "figures_tables_inspected",
    "system_problem_context",
    "strategy_os_relevance_score",
    "confidence",
    "notes_path",
    "v5_review_status",
    "prior_review_status",
    "prior_source_id",
    "sha256",
    "discovered_from",
]


def source_id(url: str) -> str:
    return "KPV5-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16].upper()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def publication_date(url: str, old: dict, override: dict) -> tuple[str, str]:
    if override.get("publication_update_date"):
        return (
            str(override["publication_update_date"]),
            str(override.get("publication_date_basis", "explicit V5 source inspection")),
        )
    match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if match:
        return "-".join(match.groups()), "URL path; page text not independently rechecked"
    if old.get("published_date"):
        return str(old["published_date"]), str(
            old.get("published_date_basis") or "prior manifest; not independently rechecked"
        )
    return "UNAVAILABLE", "not established"


def serial(value: object) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None or value == "":
        return "UNAVAILABLE"
    return str(value)


def row_for(url: str, fresh: dict, old: dict, override: dict) -> dict[str, str]:
    first_party = bool(fresh.get("first_party", urlsplit(url).hostname == "martin.kleppmann.com"))
    pub_date, pub_basis = publication_date(url, old, override)
    content_type = override.get("content_type") or fresh.get("content_type") or old.get("content_type")
    accessed = override.get("access_date") or fresh.get("accessed_at") or old.get("accessed_date")
    if isinstance(accessed, str) and len(accessed) >= 10:
        accessed = accessed[:10]
    old_license = old.get("license")
    if old_license and old_license != "UNAVAILABLE":
        old_license_text = old.get("license_basis") or old_license
    elif first_party and content_type == "text/html":
        old_license_text = "Website default CC BY 3.0; separately linked artifacts excluded"
    else:
        old_license_text = "NOT VERIFIED"
    title = override.get("title") or fresh.get("title") or old.get("title")
    author = override.get("author_presenter") or old.get("authors")
    organisation = override.get("organisation_institution")
    if not organisation and first_party:
        organisation = "Martin Kleppmann personal website"
    prior_status = old.get("review_status", "NO_PRIOR_RECORD")
    return {
        "source_id": source_id(url),
        "title": serial(title),
        "author_presenter": serial(author or "UNVERIFIED"),
        "organisation_institution": serial(organisation or "UNVERIFIED"),
        "canonical_url": url,
        "publication_update_date": pub_date,
        "publication_date_basis": pub_basis,
        "access_date": serial(accessed),
        "content_type": serial(content_type),
        "primary_secondary_status": serial(
            override.get("primary_secondary_status") or ("PRIMARY_FIRST_PARTY" if first_party else "PRIMARY_LINKED_ARTIFACT")
        ),
        "license_reuse_note": serial(override.get("license_reuse_note") or old_license_text),
        "availability_status": serial(
            override.get("availability_status") or fresh.get("status") or "V5_DIRECT_REVIEW_NO_CRAWL_RECORD"
        ),
        "pages_sections_timestamps_inspected": serial(
            override.get("pages_sections_timestamps_inspected") or "NOT_INSPECTED_BY_V5"
        ),
        "figures_tables_inspected": serial(
            override.get("figures_tables_inspected") or "NOT_INSPECTED_BY_V5"
        ),
        "system_problem_context": serial(
            override.get("system_problem_context") or "NOT_ASSESSED"
        ),
        "strategy_os_relevance_score": serial(
            override.get("strategy_os_relevance_score") or "UNSCORED"
        ),
        "confidence": serial(override.get("confidence") or "UNASSESSED"),
        "notes_path": serial(override.get("notes_path") or "NOT_REVIEWED"),
        "v5_review_status": serial(override.get("v5_review_status") or "INVENTORIED_ONLY"),
        "prior_review_status": serial(prior_status),
        "prior_source_id": serial(old.get("source_id") or "NO_PRIOR_RECORD"),
        "sha256": serial(override.get("sha256") or fresh.get("checksum") or old.get("checksum")),
        "discovered_from": serial(fresh.get("source_pages") or old.get("discovered_from") or []),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--prior-manifest", required=True, type=Path)
    parser.add_argument("--review-overrides", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    prior_rows = read_jsonl(args.prior_manifest)
    prior = {row["canonical_url"]: row for row in prior_rows}
    override_doc = json.loads(args.review_overrides.read_text(encoding="utf-8"))
    overrides = {row["canonical_url"]: row for row in override_doc["sources"]}

    selected_urls = {
        url
        for url, item in inventory.items()
        if item.get("kind") == "content" and item.get("first_party")
    }
    selected_urls.update(overrides)
    rows = [
        row_for(url, inventory.get(url, {}), prior.get(url, {}), overrides.get(url, {}))
        for url in sorted(selected_urls)
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    result = {
        "schema": "strategy-os-kleppmann-corpus-manifest-v5/1",
        "records": len(rows),
        "first_party_records": sum(
            inventory.get(row["canonical_url"], {}).get("first_party", False)
            for row in rows
        ),
        "v5_reviewed_records": sum(row["v5_review_status"] != "INVENTORIED_ONLY" for row in rows),
        "inventory_sha256": hashlib.sha256(args.inventory.read_bytes()).hexdigest(),
        "prior_manifest_sha256": hashlib.sha256(args.prior_manifest.read_bytes()).hexdigest(),
        "review_overrides_sha256": hashlib.sha256(args.review_overrides.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
