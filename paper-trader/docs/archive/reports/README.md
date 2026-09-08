# docs/reports — point-in-time reports

Everything here is **frozen**. A report is true on its date and is never rewritten; when it
stops being true it gets a header saying so, and the header is the only edit ever made to it.
Nothing in this directory is a source of current state. For that, read
[`../PROGRESS.md`](../../agent/STATUS.md), [`../ARCHITECTURE.md`](../../ARCHITECTURE.md), and the eight
[workstream documents](../../engineering/WORKSTREAMS.md).

**Reading a path inside a report body.** These files were written when they lived in `docs/`,
and their bodies were not rewritten when they moved here on 2026-08-03. Any citation of the
form `docs/<name>.md` inside a report body now resolves to `docs/reports/<name>.md` — five such
citations remain, in `2026-07-28-platform-status-report.md`,
`2026-08-02-production-architecture-audit.md` and `audit-fix-tracker.md`. Everything outside
this directory that referenced a moved file was updated.

Status key:

- **current** — a point-in-time report whose claims still hold; safe to read as written.
- **superseded** — its content now lives in a workstream document; kept for the history and
  the rationale. Carries a dated header.
- **stale** — it makes specific claims that are now **false** and that someone could act on.
  Carries a prominent `SUPERSEDED / CONTAINS STALE CLAIMS` header naming them.

| Report | Date | What it is | Status |
|---|---|---|---|
| [`pre-live-audit-2026-07-09-recovered.md`](pre-live-audit-2026-07-09-recovered.md) | 2026-07-09 | The 12-lens pre-live audit: 33/100 mean readiness, 74 raw findings, 26 confirmed, recovered from the workflow journal. The origin of the C/H/M finding numbers used everywhere else. | current |
| [`audit-fix-tracker.md`](audit-fix-tracker.md) | 2026-07-10 | Batch-by-batch tracker of the 26 confirmed pre-live audit findings, each with its fix commit. | superseded (WS-02 §4) |
| [`audit-deferred-design.md`](audit-deferred-design.md) | 2026-07-10 | Design specs for the audit findings too large to fix in one pass — H13 order journal, H16 partial close, C6, H2, H9. | superseded (all but C6 are built) |
| [`audit-remaining-impl-guide.md`](audit-remaining-impl-guide.md) | 2026-07-10 | Fable-advisor implementation guide for the four items still open after 22 fixes; the spec H13/H2/H9 were built from. | superseded (only C6 remains, deliberately inert) |
| [`deep-research-roadmap-2026-07-05.md`](deep-research-roadmap-2026-07-05.md) | 2026-07-05 | Decision-ready external research review: edge validation, out-of-sample discipline, execution friction, monetisation and the Indian regulatory path. Written pre-live; already carried its own 2026-07-28 partial-correction banner. | superseded (WS-02, WS-03) |
| [`2026-07-18-safety-research-product-review.md`](2026-07-18-safety-research-product-review.md) | 2026-07-18 | Multi-agent safety review of the live branch: 10 essential defects (E1–E10), a re-verdict on four past failure classes, research-plane maturity, product avenues. | **stale** — describes a leverage cap that was removed 2026-07-22 and must not return |
| [`2026-07-24-E2-index-futures-spec.md`](2026-07-24-E2-index-futures-spec.md) | 2026-07-24 | Design spec for the `index_futures` segment: isolation, sizing, charges, force-flat, 13 TDD steps. | **stale** — says "no code written"; all 12 build steps shipped 2026-08-01 |
| [`2026-07-28-platform-status-report.md`](2026-07-28-platform-status-report.md) | 2026-07-28 | Business-case plus engineering status report written for an external reader: differentiators, architecture, roadmap, candid gap list. | **stale** — deploy state, E2 status and the "most valuable next action" are all overtaken |
| [`2026-08-01-backtester-audit.md`](2026-08-01-backtester-audit.md) | 2026-08-01 | Audit of `app/backtest/` against ten dimensions (look-ahead, fills, commissions, slippage, latency, partials, leverage, pyramiding, options, statistics). Found and fixed zero-slippage on the spot path. | current |
| [`2026-08-01-exit-sweep.md`](2026-08-01-exit-sweep.md) | 2026-08-01 | Exit-parameter sweep replaying the production ledger's own MFE/MAE telemetry. The evidence that the 1.5% target was mathematically unreachable. | current |
| [`2026-08-01-feature-review.md`](2026-08-01-feature-review.md) | 2026-08-01 | Feature-level review — every user-facing capability judged against live row counts from the production DB, including what is dead weight. | current |
| [`2026-08-02-execution-determinism-audit.md`](2026-08-02-execution-determinism-audit.md) | 2026-08-02 | Verification of deterministic execution: kill switch, duplicate orders, arm/disarm, retries, reconnects. Found and fixed the kill-switch defect. | current |
| [`2026-08-02-production-architecture-audit.md`](2026-08-02-production-architecture-audit.md) | 2026-08-02 | Architecture-only audit ahead of Phases 3/5/6/9/13; the five load-bearing identity decisions that get expensive later. Source of the migration below. | current |
| [`2026-08-02-architecture-migration.md`](2026-08-02-architecture-migration.md) | 2026-08-02 | Working record of migration phases A–H, each additive with an equivalence test. | **stale** — opens "Nothing in this migration is committed"; false since `cc53bba` |
| [`2026-08-02-monday-watch-list.md`](2026-08-02-monday-watch-list.md) | 2026-08-02 | Operational brief for the first trading session after a 60-commit window: what could break, the symptom, and the rollback. | current |
| [`2026-08-04-l1-stage1-shadow.md`](2026-08-04-l1-stage1-shadow.md) | 2026-08-04 | L1 Stage 1 evidence: the shadow-only IR lane — isolation proofs, nine mutations watched turning guards red, measured agreement and loop cost, and the two owner decisions Stage 1 cannot close without. | current |
| [`2026-08-02-openalgo-competitive-teardown.md`](2026-08-02-openalgo-competitive-teardown.md) | 2026-08-02 | Competitor architecture teardown of OpenAlgo (AGPL — ideas only, never code), read as a specification of what users expect. | current |
| [`STATUS.html`](../../reports/STATUS.html) | 2026-07-25 | Standalone HTML status board: KPIs, open items, gates. Was the at-a-glance view before `PROGRESS.md` existed. | **stale** — frozen 2026-07-25 snapshot; trade counts and deploy state are wrong |

Related directories that are **not** reports: [`../incidents/`](../../incidents) (post-mortems,
still live operational reading), [`../audit/`](../../audit)
(`docs/audit/ground-truth-2026-07-28.md`, the measured-state reference), [`../superpowers/`](../../superpowers) (session plans and specs).
