# Crawl log and limits

Date: 28 August 2026. Collector: `scripts/crawl_inventory.py`; exporter: `scripts/export_inventory.py`. Full output: `.agent/runs/kleppmann-professional-review-20260828/root/corpus-crawl.log`.

## Observed coverage

- first_party_content_records: 373
- external_direct_links_pending_triage: 2016
- assets_inventoried: 459
- all_discovered_urls: 2848
- crawl_statuses: {"fetched": 368, "download_deferred": 4, "fetch_error": 1}
- review_statuses: {"not_read": 371, "fully_read": 2}
- tiers: {"UNSCREENED": 353, "TIER 0": 20}
- content_types: {"text/html": 339, "unknown": 5, "application/pdf": 29}
- byte_duplicates: 6
- first_party_html_frontier_pending: 0
- all_mandate_coverage_complete: false

The collector started from the homepage, archive, talks archive and the specified 2020 course announcement. It normalized first-party HTTP links to HTTPS, removed fragments, retained query strings, followed first-party content links serially, and recorded external links and image/media assets separately. It respected the fetched robots file, waited at least one second between its requests, cached bytes by SHA-256, imposed a 30 MiB per-response bound and a 700-fetch run limit. The queue exhausted before that limit.

The robots response was HTTP 200 and contained explanatory content-signal comments without a disallow rule or explicit content-signal restriction. Raw robots bytes are retained. No login, paywall or access control was bypassed.

Known limits: no PDF-annotation traversal, external recursive crawl, video transcription, script execution or archive expansion. Direct external links still need one-hop eligibility triage. Four archives/XML artifacts were inventoried but deliberately not fetched. An HTTP 404 remains recorded. Byte duplicates are identified; semantically repeated talks/editions still need review.

PDF metadata/text extraction covered 29 PDFs and 954 pages with bundled pypdf. Parser warnings are retained in `root/pdf-metadata.log`. Text extraction is not reading or visual inspection; PDF reviewed count is zero. Two web articles and their three technical images were actually read/inspected. No video or transcript is claimed reviewed.

## Reproduce without changing product dependencies

Run from the repository root:

```sh
python3 .codex/scripts/run_logged.py --task kleppmann-professional-review-20260828 --assignment root --label corpus-crawl-resume --cwd . -- python3 paper-trader/docs/research/kleppmann/scripts/crawl_inventory.py --cache .agent/runs/kleppmann-professional-review-20260828/cache --max-fetches 700
python3 .codex/scripts/run_logged.py --task kleppmann-professional-review-20260828 --assignment root --label export-manifest-resume --cwd . -- python3 paper-trader/docs/research/kleppmann/scripts/export_inventory.py --cache .agent/runs/kleppmann-professional-review-20260828/cache --output paper-trader/docs/research/kleppmann
```

A resume reuses successful/error records rather than silently re-fetching. A dated refresh or retry needs an explicit new cache/retry decision. Do not present a resumed cache as a fresh access timestamp.

## 29 August continuation

Capsule `kleppmann-corpus-artifacts-and-ddia2e` did not invoke
`crawl_inventory.py` and did not change the 373-record first-party frontier.
It read the existing external queue, produced `one-hop-triage.jsonl`, captured
selected public artifacts under its ignored evidence root, and reran only the
manifest exporter after updating explicit review records.

Current ledger: 2,016 external links triaged, zero pending triage; 117 bounded
candidates, 454 other deferred artifacts and 1,445 deferred bibliography/context
records. Seven first-party records are fully read. Four selected PDFs total 320
pages and have page-level direct visual receipts. These counts do not turn any
other fetched, extracted or triaged source into a reviewed source.
