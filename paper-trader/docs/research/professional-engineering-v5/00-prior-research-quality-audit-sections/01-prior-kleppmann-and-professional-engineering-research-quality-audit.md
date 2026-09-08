Reference: [section index](../00-PRIOR-RESEARCH-QUALITY-AUDIT.md). Read with its scope; this is not a new assignment.

# Prior Kleppmann and professional-engineering research quality audit

Date: 2026-08-31\
Status: COMPLETE FOR PRIOR-RESEARCH QUALITY; fresh thematic review remains separate\
Repository baseline: `codex/execution-foundation` at `de6faae3e97cf5537338bee2143350e53f70da1c`, with inherited dirty work preserved

## Verdict

The previous programme produced useful, reproducible intake evidence. It did not complete the claimed wider Kleppmann mandate, and its own reports usually say so. Retain the raw corpus inventory, fetch hashes, page-level PDF receipts, inaccessible-source record, bounded source notes, and anti-overengineering decisions.

Do not accept the old claim registry as decision-grade without correction. It mixes source claims, Codex inference, Strategy OS recommendations, local receipts, and implementation state in one `claim` field. Several citations support only the general principle, not the Strategy OS-specific sentence. The registry also contains stale implementation states because NMT-001, NMT-003, and NMT-004 have since passed accepted correction gates.

The full prior corpus review remains incomplete:

- 373 first-party records were inventoried.
- 368 were fetched, but only seven were marked fully read.
- 29 PDFs were fetched or extracted; four PDFs, 320 pages in total, carry direct visual-review receipts.
- 2,016 external one-hop links were classified, not reviewed. Of those, 117 were admitted as bounded candidates.
- 127 video records and one transcript candidate were inventoried. No video or transcript was reviewed.
- 349 of 373 first-party records remain `UNSCREENED`; 366 remain `not_read`.

The prior work therefore passes as bounded intake and selected-source review. It fails as a complete corpus review or complete source-to-code audit.

## Authority and artifact set audited

The audit inspected the following prior-research families:

- `paper-trader/docs/research/kleppmann/`, including the V2 mandate, intake capsule, corpus manifests, crawl log, one-hop triage, source-review records, PDF and licence ledgers, source notes, gap matrices, verification reports, and all six audit scripts.
- `paper-trader/docs/engineering-references/`, including the professional engineering programme, source and claim registries, reading packets, source notes, refresh reports, and rejected-pattern records.
- `paper-trader/docs/program/owner-directions/2026-08-29/05-PROFESSIONAL-ENGINEERING-CORPUS-REVIEW-V4.md`.
- The current `CURRENT.md`, matching programme stage, and active capsule for implementation-state drift.
- The 20-claim deterministic random sample recorded at `.agent/runs/kleppmann-reaudit-v5/prior-research-audit/citation-sample.log`.

The earlier reports say the V3 prompt and standalone simplicity directive were unavailable. A fresh filesystem search again found neither file. The V2 prompt, V4 brief, professional engineering programme, and 2026-08-30 owner addendum are available. This audit does not silently reconstruct the missing documents from summaries.

## Corpus-root and retrieval audit

### Roots claimed and actually used

The old crawler starts from four first-party roots:

- `https://martin.kleppmann.com/`
- `https://martin.kleppmann.com/archive.html`
- `https://martin.kleppmann.com/talks.html`
- `https://martin.kleppmann.com/2020/11/18/distributed-systems-and-elliptic-curves.html`

The crawler recursively follows first-party HTML, records external links and assets, serializes access status, and never marks a fetch as a review. That boundary is sound.

The earlier crawl did not use a sitemap. A fresh request on 2026-08-31 returned HTTP 404 for `/sitemap.xml`. The old crawl also deliberately deferred XML and archive payloads, so it could not have used a sitemap even if one had appeared through an HTML edge. The publication index was reached through the homepage. The talks index and course page were explicit roots. Selected GitHub artifacts were reviewed later at exact commits, but no GitHub-profile-wide inventory was performed.

The fresh `robots.txt` contained content-signal explanatory text and no `User-agent`, `Disallow`, or crawl-delay directive. The fresh crawl remains serial with a minimum one-second delay.

### Opened versus listed

The old manifest makes the distinction correctly:

- `crawl_status=fetched` means bytes were retrieved.
- `review_status=fully_read` appears for only seven first-party records.
- `one-hop disposition` means triage only.
- `visuals_inspected` remains false unless a separate review record says otherwise.

This is materially better than title-only research. The weakness is coverage, not dishonesty about coverage.

### PDF, figure, and video handling

The prior intake extracted text from 29 PDFs and 954 pages, while explicitly recording zero deep visual reviews at that stage. The continuation then marked four exact PDFs fully read and visually inspected:

| Source | Pages | Fresh SHA-256 match on 2026-08-31 | Prior visual receipt |
| --- | ---: | --- | --- |
| Cambridge *Distributed Systems* notes | 91 | `4a754e36358948d4f98cb26fb8ecd44d868024d3bb0f26db30851158ddea3064` | All pages rendered; 34 embedded image objects |
| *Making Sense of Stream Processing* | 183 | `13793a2c25d6f707e91dfc17884eebc8cc9fc69473156c3ab851ca73117572b2` | All pages rendered; 130 embedded image objects |
| *Online Event Processing* | 21 | `f4b10a04ab4408e99d317ec2ee1d44efa991af1396856f12c8b188c8393fde79` | All pages rendered; 48 embedded image objects |
| *Local-First Software* | 25 | `60c6e47c3b648fbe73c1613f28251bd5c3f4c3ecd534127653684ee3194c9aa2` | All pages rendered; 25 embedded image objects |

The fresh downloads match every prior PDF hash. This audit independently reopened exact cited pages and rendered selected figures. It confirmed the monotonic-clock discussion, OLEP log/subscriber recovery model, stream-to-UI materialized-view discussion, and local-first conflicting-value limitation.

No prior video had a transcript or detailed viewing record. The programme correctly avoids claims based on talk titles.
