Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

# Strategy OS — Kleppmann + Professional Engineering Review Prompt V2

**Supersedes for future runs:** `STRATEGY_OS_KLEPPMANN_CODEX_DEEP_REVIEW_PROMPT.md`\
**Usage:** Give this complete file to Codex from the Strategy OS repository root.\

The original mandate is retained below, followed by a mandatory V2 addendum that adds the missing Kleppmann themes and a phase-aware professional engineering reference programme.

---

# Strategy OS — Martin Kleppmann Corpus Review, Failure Discovery, and Industrial Hardening Mandate

You are the principal distributed-systems architect, adversarial reviewer, reliability engineer, and implementation owner for Strategy OS.

Your task is **not** to skim a few Martin Kleppmann articles and write a generic systems-design summary. Treat the complete public corpus reachable from Martin Kleppmann’s website as a structured research programme, use it to attack Strategy OS’s current assumptions, discover realistic bugs and omitted contingencies, improve user-facing failure handling, and make bounded, evidence-backed code changes that preserve the current release sequence.

The required outcome is:

```text
EXHAUSTIVE CORPUS INVENTORY
        ↓
RELEVANCE AND EVIDENCE RANKING
        ↓
DEEP REVIEW OF HIGH-VALUE SOURCES
        ↓
STRATEGY OS ARCHITECTURE + CODE MAPPING
        ↓
ADVERSARIAL FAILURE HYPOTHESES
        ↓
TESTS THAT REPRODUCE REAL FAILURES
        ↓
BOUNDED FIXES / ADRs / DEFERRED WORK
        ↓
VERIFIED INDUSTRIAL-HARDENING REPORT
```

Do not confuse “industrial-grade” with “more infrastructure.” The goal is better correctness, recoverability, observability, explainability, and scale readiness—not Kafka, Redis, microservices, Kubernetes, CRDTs, consensus, or formal proof merely because they appear in the source material.

---

## 0. Non-negotiable working rules

1. Work from the actual Strategy OS repository root.
2. Before any research or code change, print and record:
   - `pwd`;
   - repository root;
   - current branch;
   - current commit;
   - `git status --short`;
   - active worktrees;
   - remotes;
   - runtime/toolchain versions;
   - detected frontend, backend, database, queue/job, cache, websocket, broker, and deployment technologies.
3. Locate and obey any active capsule, goal, phase, ADR, repository-review gate, or project-specific agent instructions. Do not bypass them.
4. Preserve all unrelated user work. Never reset, clean, discard, or overwrite uncommitted changes.
5. Prefer a dedicated branch/worktree such as:

```text
audit/kleppmann-systems-hardening
```

6. Audit before rewriting. Do not infer architecture from filenames or old documentation when current code can answer the question.
7. The latest explicit owner decision outranks every older document. The current delivery direction is a constrained research-first V0, with real-money execution not broadly enabled at V0 launch, Zerodha as the initial broker path, and future execution/provider seams preserved. Do not let this review pull speculative distributed infrastructure into V0.
8. Correctness issues in research identity, data truth, job durability, tenant isolation, evidence, migrations, or currently reachable money paths may still be immediate blockers.
9. For execution code that is not currently public V0 scope, produce precise invariants, adversarial tests, ADRs, and a sequenced hardening plan; implement only changes that are clearly safe, foundational, and compatible with the current phase.
10. Never fabricate having read an inaccessible page, watched a video without a usable transcript, inspected a figure you only saw as extracted text, or verified a claim you did not verify.
11. Do not ask broad clarification questions. Make the best evidence-based decision, record uncertainty, and continue.

---

## 1. Read the Strategy OS authorities first

Find and read the current versions of these documents before interpreting any external source:

```text
00-STRATEGY-OS-PRODUCT-STEER.md
01-STRATEGY-LANGUAGE-NODE-SYSTEM.md
02-MARKET-TRUTH-DATA-CONTRACTS.md
03-DEPLOYMENT-EXECUTION-TRUST.md
04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md
05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md
STRATEGY_OS_GRAND_PRODUCT_VISION_2026-08-11.md
STRATEGY_OS_V1_PRODUCT_SCOPE_AND_SEQUENCE_2026-08-11.md
strategyos-v1-v1.1-v1.5-v2-v3-product-architecture-memo-2026-08-24(1).md
```

Also locate all newer owner decisions, active phase documents, accepted ADRs, implementation handoffs, and repository-state reports. Where timing or version labels conflict, use this precedence:

```text
latest explicit owner decision
→ latest accepted canonical memo
→ current ADRs and active capsule
→ current implementation state
→ older scope documents
```

Create a short `CURRENT_AUTHORITY_MAP.md` that states which source currently governs:

- V0 scope;
- V1 execution scope;
- V1.1/V1.5 boundaries;
- data truth;
- position sizing/capital reservation;
- runtime state and Redis boundaries;
- provider/broker architecture;
- verification policy;
- tenancy and strategy confidentiality;
- current phase and release gates.

Do not reopen settled product architecture unless a concrete code-level contradiction or unrepresentable requirement is proven.

---

## 2. Corpus scope: crawl the website as a graph, not as a homepage

Start from:

```text
https://martin.kleppmann.com/
https://martin.kleppmann.com/archive.html
https://martin.kleppmann.com/talks.html
https://martin.kleppmann.com/2020/11/18/distributed-systems-and-elliptic-curves.html
```

The corpus includes:

- every post in the full blog archive;
- every entry in the talks archive;
- the homepage publication list;
- all first-party paper/PDF links;
- slide decks;
- transcripts;
- diagrams, graphs, and figures;
- public lecture notes and course pages directly linked by the site;
- public code/artifact repositories directly linked by a high-relevance source;
- official video transcripts where available;
- direct supporting resources needed to understand a high-priority claim.

### 2.1 Bounded recursive-crawl policy

“Review everything” must be made finite and auditable:

1. **Exhaustively inventory every first-party content URL** under `martin.kleppmann.com` reachable from the homepage, blog archive, talks archive, and publication list.
2. Follow direct first-party sublinks recursively, including `/papers/*.pdf`, slides, transcripts, and downloadable artifacts.
3. Follow external links one hop when they are:
   - the actual paper/slides/course notes for a first-party entry;
   - an official Cambridge course resource;
   - an official author artifact or repository;
   - required to understand a high-priority Strategy OS implication.
4. Do not recursively crawl the entire bibliography or internet. Put potentially useful second-hop references in a deferred bibliography with a reason.
5. Respect robots directives, rate limits, licensing, and normal site load. Cache downloads locally and avoid repeated requests.
6. Deduplicate canonical URLs, mirrors, repeated talks, alternate slide formats, and the same paper linked from multiple pages.
7. Record inaccessible, dead, login-gated, or transcript-less sources instead of silently dropping them.

### 2.2 PDF, slide, graph, image, and video handling

For every PDF or slide deck:

- record URL, title, author, date, page/slide count, source page, license if visible, and checksum;
- extract text with `pdftotext` or an equivalent;
- render pages/slides containing diagrams, tables, timelines, architecture maps, state machines, consistency models, transaction histories, or graphs;
- inspect those visuals directly rather than relying only on text extraction;
- for high-priority PDFs, read every page;
- for medium-priority PDFs, inspect the abstract, introduction, core model, diagrams, failure analysis, conclusions, and relevant sections;
- cite exact page and section in every derived claim.

For videos:

- prefer an official transcript, accompanying paper, accompanying slides, or a complete written transcript;
- use auto-generated transcripts only with an explicit reliability note;
- do not claim to have reviewed visual demonstrations that are not represented in the transcript/slides;
- repeated deliveries of the same talk should be deduplicated unless one has materially updated content.

For web-page images and graphs:

- download/render them;
- inspect labels, axes, state transitions, arrows, and examples;
- record what the visual adds beyond the surrounding prose.

### 2.3 Copyright and licensing

- Record the license for each artifact where available.
- Use the corpus for analysis, citations, tests, and architecture reasoning.
- Do not vendor papers, decks, or large copied passages into the Strategy OS repository unless the license and project policy clearly permit it.
- Do not download or rely on pirated copies of *Designing Data-Intensive Applications*. Use only lawfully available first-party/public material and any book copy the repository owner has legitimately provided.
- Paraphrase. Quote only short passages when necessary, with attribution.

---
