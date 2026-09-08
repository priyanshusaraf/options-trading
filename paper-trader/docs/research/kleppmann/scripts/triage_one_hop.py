#!/usr/bin/env python3
"""Classify the recorded one-hop queue without crawling or fetching it.

This is an overlay on the immutable crawl export. It separates artifact type,
bounded-review eligibility and actual review state. A triage disposition is not a
claim that a source was retrieved, read, licensed for reuse or applicable.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import urllib.parse


DDIA_2E_PAGE = (
    "https://martin.kleppmann.com/2026/03/24/"
    "designing-data-intensive-applications-2e.html"
)


def artifact_id(url: str) -> str:
    return "kh-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def classify(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.lower()
    whole = url.lower()
    if "transcript" in whole or "caption" in whole:
        return "transcript"
    if path.endswith(".pdf") or host in {
        "arxiv.org",
        "doi.org",
        "dx.doi.org",
        "dl.acm.org",
    } or "usenix.org" in host:
        return "paper_or_pdf"
    if host.endswith("cam.ac.uk") and any(
        marker in whole
        for marker in ("teaching", "course", "lecture", "materials", "concdissys")
    ):
        return "course_material"
    if host in {"speakerdeck.com", "slideshare.net"} or any(
        marker in path for marker in ("/slides/", "-slides", "slides.")
    ):
        return "slide_deck"
    if host in {
        "youtube.com",
        "youtube-nocookie.com",
        "youtu.be",
        "vimeo.com",
        "player.vimeo.com",
    }:
        return "video"
    if host in {"github.com", "gist.github.com", "gitlab.com", "codeberg.org"}:
        return "code_or_research_artifact"
    if host in {"dataintensive.net", "oreilly.com"}:
        return "official_book_material"
    return "supporting_web_reference"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--priority", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()

    queue = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    priority = json.loads(args.priority.read_text(encoding="utf-8"))
    high_priority_parents = {row["url"] for row in priority}
    high_priority_parents.add(DDIA_2E_PAGE)
    review_path = args.reviews or (args.output.parent / "licensed-artifact-reviews.json")
    review_doc = (json.loads(review_path.read_text(encoding="utf-8"))
                  if review_path.exists() else {"artifacts": []})
    reviews = {row["url"]: row for row in review_doc["artifacts"]}

    rows = []
    for source in queue:
        url = source["url"]
        category = classify(url)
        parents = sorted(set(source.get("source_pages", [])))
        priority_edges = sorted(set(parents) & high_priority_parents)
        is_artifact = category != "supporting_web_reference"
        if is_artifact and priority_edges:
            disposition = "ADMIT_BOUNDED_ONE_HOP_CANDIDATE"
            reason = "Direct artifact/course/media edge from a Tier 0 or DDIA 2e source."
        elif is_artifact:
            disposition = "DEFER_OTHER_ONE_HOP_ARTIFACT"
            reason = "Recorded artifact edge, but not required by this capsule's highest-priority packet."
        else:
            disposition = "DEFER_BIBLIOGRAPHY_OR_CONTEXT"
            reason = "General external reference; not an admitted primary artifact for this bounded packet."
        record = {
                "artifact_id": artifact_id(url),
                "url": url,
                "source_pages": parents,
                "category": category,
                "disposition": disposition,
                "disposition_reason": reason,
                "priority_source_edges": priority_edges,
                "retrieval_status": "not_attempted_by_triage",
                "review_status": "not_read",
                "visuals_inspected": False,
                "licence_status": "not_checked",
                "notes_path": None,
            }
        if url in reviews:
            review = reviews[url]
            record.update({
                "retrieval_status": review["retrieval_status"],
                "review_status": review["review_status"],
                "visuals_inspected": review["visuals_inspected"],
                "licence_status": review["licence_status"],
                "notes_path": review["notes_path"],
                "exact_identity": review["exact_identity"],
                "reuse_disposition": review["reuse_disposition"],
            })
        rows.append(record)

    args.output.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    summary = {
        "schema": "kleppmann-one-hop-triage/1",
        "input_records": len(queue),
        "output_records": len(rows),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "html_crawl_rerun": False,
        "categories": dict(Counter(row["category"] for row in rows)),
        "dispositions": dict(Counter(row["disposition"] for row in rows)),
        "reviewed_queue_records": sum(row["review_status"] != "not_read" for row in rows),
        "supplemental_reviewed_artifacts": sum(
            url not in {row["url"] for row in rows} for url in reviews),
        "state_warning": (
            "Triage is not retrieval, reading, visual inspection, licence permission, "
            "claim admission or product authority."
        ),
    }
    args.summary.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
