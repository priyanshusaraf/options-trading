Reference: [section index](../00-PRIOR-RESEARCH-QUALITY-AUDIT.md). Read with its scope; this is not a new assignment.

## Metadata and reproducibility audit

The old manifest is reproducible from an ignored crawl cache plus tracked review overlays. Its scripts use no product dependency. The final validators check counts, unique IDs, links, selected required fields, page receipts, and current file existence.

The manifest does not meet the V5 metadata standard:

| Defect | Count out of 373 |
| --- | ---: |
| Missing title | 22 |
| Missing author | 235 |
| Missing publication date | 115 |
| Date inferred only from URL path | 258 |
| Missing page or slide count | 344 |
| Licence not verified | 109 |
| Transcript availability unknown | 373 |
| Unscreened relevance | 349 |
| Not read | 366 |

The prior source registry contains 57 entries but mixes source families, concrete artifacts, and local evidence receipts. It uses its earlier schema consistently enough for that programme, but it does not expose the V5 fields for exact inspected locations, figures, system model, relevance score, confidence, or notes path.

Reproducibility limits remain:

- A validator can prove that a page was flagged inspected; it cannot reproduce the human act of looking at it.
- The generated manifest depends on ignored raw bytes. The raw cache exists in this worktree, but the tracked repository alone is not a complete replay package.
- The old validation enforces complete fields only for the nine KCA continuation claims, not for every claim in the registry.
- Line references remain syntactically valid, but implementation state has moved since 2026-08-29.

## Claim-registry quality

The registry contained 29 claims at audit start.

- Three claims, AUTH-001 through AUTH-003, have no `citation` field.
- Thirteen claims lack both `system_assumptions` and `failure_hypothesis` fields.
- No claim has an explicit `Codex inference` field.
- `ZERODHA_CHARGES_20260829.artifact_sha256` contains only 57 hexadecimal characters. The original captured file hashes to `a93bf79732b9b6d4f6df7f6e7df756f14d05bb4a94d08a5951a20439d874aafb`; the registry dropped seven characters and its validator did not detect the malformed digest.
- Every repository-evidence path exists and every named line is within the current file length. This proves path integrity, not that the current lines still mean what the older report said.
- NMT-001, NMT-003, and NMT-004 retain `correction pending` language even though `CURRENT.md` records accepted correction verdicts for all three.

The most serious problem is semantic. A typical prior claim combines four different facts:

1. a source-supported principle;
2. a Strategy OS failure hypothesis;
3. a repository-specific inference or direct probe;
4. a recommended release response.

V5 must store those as separate fields. A table-of-contents heading, general incident, or canonicalization rule cannot carry the repository-specific conclusion by itself.

## Deterministic 20-claim citation sample

Method: shuffle all 29 claim records with Python `random.Random(20260831)` and inspect the first 20. Exact records and method are in `citation-sample.log`. The audit independently reopened public primary sources or exact local receipts. `fresh-source-hashes.log`, `sampled-pdf-text.log`, the rendered page evidence, and the public-source access record support these dispositions.

| Claim | Status | Audit result |
| --- | --- | --- |
| KCL-002 | VERIFIED AND RETAINED | The Hermitage article explicitly argues for precise, executable concurrency histories against actual database behavior. SQLite evidence still does not prove PostgreSQL crash or failover behavior. |
| NMT-004 | REPOSITORY HAS CHANGED | Python and Zerodha sources support explicit decimal/rounding controls and the cited public rates. The old claim mixed source evidence with effective-dating and refusal recommendations. The repository now records the charge correction as accepted. |
| NMT-005 | VERIFIED BUT MISAPPLIED | NASA pages 63 and 73-74 support dimension consistency at interfaces and a 4.45x unit failure. They do not prescribe Strategy OS graph typing. The graph-language response remains a repository inference and future verification task. |
| KCL-001 | VERIFIED AND RETAINED | The locking article directly supports rejecting stale effects at the protected sink. Exact random-token equality is Strategy OS's local database design, not a universal replacement for monotonic fencing across independent sinks. |
| KCA-007 | SOURCE DOES NOT SAY THIS | The official DDIA 2e contents name “Sharding for Multitenancy.” A heading alone does not establish the prior claim that tenant isolation and physical sharding are separate decisions, even though that recommendation is sensible for this repository. |
| NUM-006 | VERIFIED AND RETAINED | The exact local receipt and hash support the attributed correction-owner statement. It remains a report of local work pending its declared independent assurance, not a fresh external-source claim. |
| NUM-004 | VERIFIED AND RETAINED | The exact local receipt supports the attribution and preserves the pending-assurance limit. |
| KCA-003 | VERIFIED BUT MISAPPLIED | OLEP and the stream-processing text support durable facts, asynchronous projections, duplicate delivery, lag, and rebuildability. They do not name Strategy OS monitoring signal, alert, delivery-attempt, and attention objects. Those distinctions are a repository inference. |
| KCA-008 | SOURCE DOES NOT SAY THIS | DDIA 2e chapter-14 headings mention accountability, feedback loops, privacy, and consent. They do not by themselves support policy versioning, ranking provenance, or conflict-disclosure requirements. |
| NMT-002 | SOURCE DOES NOT SAY THIS | Freqtrade supports look-ahead detection; pandas defines backward as-of matching. Neither source states `available_at >= completed_at`. The direct Strategy OS probe may support that project invariant, but it does not repair the source attribution. |
| NUM-003 | REQUIRES FRESH TEST | The exact local receipt reports the cancellation finding and proposed rational-moment approach, but the prior registry indexer did not inspect the formulas, oracle, or numerical result. |
| NMT-006 | VERIFIED BUT MISAPPLIED | Kite Connect explicitly warns that derivative instrument tokens may be reused after expiry, and pandas documents backward matching. These sources do not prove all listed Strategy OS identity, missing-state, prefix, and capability controls are correct. That conclusion needs direct repository evidence. |
| AUTH-003 | VERIFIED AND RETAINED | RFC 9106 section 5.3 and the stored installed-library probe have identical expected and actual Argon2id tags. The claim-registry entry still needs an exact citation field. |
| NUM-002 | REPOSITORY HAS CHANGED | Python 3.13 documents exact float-to-Decimal conversion and explicit contexts. The registry points to earlier correction bytes; the inherited repository now contains the later accepted F04 state, so current applicability needs exact-hash revalidation. |
| NUM-007 | REQUIRES FRESH TEST | The exact local receipt reports seven-consumer impact evidence, but the prior indexer did not inspect the arrays, oracles, or numerical results. |
| AUTH-001 | VERIFIED AND RETAINED | OWASP says SameSite is defense in depth, recommends origin checks, and documents session-bound CSRF tokens. The registry lacks a citation and incorrectly points its repository evidence only to an Argon2 probe; fix that traceability. |
| AUTH-002 | VERIFIED AND RETAINED | Pinned pyca source calls constant-time `bytes_eq`; the stored wrapper hash and installed-library probe match. The registry needs the exact source-code citation instead of a null citation. |
| NMT-001 | REPOSITORY HAS CHANGED | RFC 8785 supports deterministic canonicalization, not the `recorded_at` versus knowledge-cutoff model. The direct repository probe supplied the failure evidence. The repository now records NMT-001 as accepted, so the old pending status is stale. |
| KCA-001 | VERIFIED AND RETAINED | Cambridge pages 30-31 directly distinguish time-of-day and monotonic clocks and explain negative elapsed durations after clock steps. |
| KCA-006 | SOURCE DOES NOT SAY THIS | The DDIA 2e contents name durable execution and event-driven architecture. The conclusion that this is an evidence requirement rather than a dependency mandate is Strategy OS policy, not a quoted source claim. |

Sample totals after reconciliation: 8 `VERIFIED AND RETAINED`, 3 `VERIFIED BUT MISAPPLIED`, 4 `SOURCE DOES NOT SAY THIS`, 2 `REQUIRES FRESH TEST`, and 3 `REPOSITORY HAS CHANGED`.

An independent read-only shadow audit used a different deterministic SHA-256 ranking and reached the same central defects: source/inference conflation, table-of-contents overreach, stale numerical applicability, and the malformed Zerodha digest. Its receipts are `.agent/runs/ultra-backend-v5-chat1/prior-audit/citation-verdicts.md` and `quality-audit.md`. V5 treats those as counter-review evidence, not automatic truth.

### Additional high-impact Kleppmann dispositions

The random sample omitted several Kleppmann claims, so this audit also reopened them:

| Claim | Status | Audit result |
| --- | --- | --- |
| KCA-002 | VERIFIED BUT MISAPPLIED | The sources support ordered logs, at-least-once delivery, lag, and rebuildable projections. “Keep the current outbox” still depends on direct repository evidence. |
| KCA-004 | VERIFIED BUT MISAPPLIED | *Local-First Software* says some same-property conflicts require application or user resolution. It does not prove the current graph compare-and-swap path is correct or prescribe Strategy OS semantic refusal. |
| KCA-005 | SOURCE DOES NOT SAY THIS | NFR chapter headings do not establish the repository's adoption gate or user-scale assumptions. |
| KCA-009 | VERIFIED AND RETAINED | The old packet represented the Redlock disagreement and scoped the local conditional database sink correctly. No Redis adoption follows. |
| NMT-003 | REPOSITORY HAS CHANGED | RFC 8785 confirms both IEEE positive and negative zero serialize as JSON `0`. The old repository defect was direct-probe evidence, and the repository now records the correction as accepted. |
| NMT-007 | VERIFIED BUT MISAPPLIED | Unicode and ISO material support locale/currency separation at presentation and interchange boundaries. They do not prove the complete V0 implementation. |
