# Strategy OS revised V1 progress mapper

Date: 24 August 2026
Status: canonical programme authority from Phase 5 onward
Repository baseline: `de6faae3e97cf5537338bee2143350e53f70da1c` on `codex/execution-foundation`

## Executive summary

Keep the accepted Phase 1–4 foundation and rebase the remaining programme into nine phases, Phases 5–13. The expanded V1 is a hybrid discretionary-systematic trading decision operating system. It adds Dynamic Watchlists, bounded point-in-time reference/events, temporal routing, selectivity-aware resource planning, provider price coherence, chart workspaces, normalized chart semantics, `OperatorThesis`, and expiring proposal/approval flows. It does not add general annotation backtesting, broad certified options execution, a general Workflow builder, a fundamentals terminal, AI chart interpretation, HFT claims, or a second strategy/runtime authority.

The first executable slice remains `phase5-graph-paper-attribution-schema`. It closes a real 71-character graph-address versus 64-character strategy-version defect and is necessary but non-enabling. The accepted Phase 5 language/resource architecture remains reusable input, but its old implementation ordering is superseded: Phase 5 must first close sizing, target-position, deterministic simultaneous admission, and transactional reservation correctness. Language/resource implementation moves into revised Phase 6.

No repository evidence supports the former 1 September target or a mid-September complete V1. The machine programme permits one active durable goal and serializes phase reviews, so the evidence-based private-V1 release window is **15 March to 30 June 2027**. This assumes the chart access/licence decision and the bounded reference/event data decision close by 11 September, the frontend owner gate opens when backend contracts freeze, the declared within-stage child lanes remain available, and each Critical gate needs at most one correction/recheck. If an external decision remains open after 11 September, the complete-V1 date is unbounded until the owner selects an approved route. A credible mid-September milestone is Phase 5 architecture plus the first schema/runtime and capital-contract work, not release.

## Exact repository and evidence state

| Fact | Current evidence |
| --- | --- |
| Worktree and repository root | `/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation`; both `pwd` and `git rev-parse --show-toplevel` agree. |
| Branch and commit | `codex/execution-foundation`; `de6faae3e97cf5537338bee2143350e53f70da1c`. |
| Worktree | Intended active Strategy OS worktree. The Desktop clone is frozen. Exact list: `.agent/runs/programme-rebase-2026-08-24/root/repository-context.log`. |
| Dirty state | Inherited and intentionally preserved. At package drafting: 195 tracked modified/added paths and 267 untracked paths; no deletion or rename. The tracked diff reports 13,053 insertions and 1,824 deletions. These counts include this documentation slice and are not a clean-release claim. |
| Documentation root | `paper-trader/docs`. Canonical release package: `paper-trader/docs/strategy-os-v1-v2-v3`. Programme authority: `paper-trader/docs/agent`. |
| Execution/research heads | Execution `0039`; research `0011`. The next existing execution migration is the blocked `0040` graph-paper attribution capsule. |
| Phase 1–4 gate | Accepted local foundation boundary. Review package `0e67dfce…`; recheck `d43994cc…`; separate SPEC PASS and QUALITY PASS. Current direct selectors also exit `0`. |
| Phase 5 state | Architecture packet accepted as `KEEP + HARDEN`; product implementation unstarted. Its language/resource contracts are retained and re-sequenced. |
| Model identifiers | Root configuration is `gpt-5.6-sol` with `xhigh`; subagent default is `gpt-5.6-sol` medium; critical reviewer is `gpt-5.6-sol` high. Exact log: `.agent/runs/programme-rebase-2026-08-24/root/model-identifiers.log`. No model configuration edit is required. |
| Deployability | Named local contracts only. Release deployability is open; production rehearsal unproven; deployment unauthorized. |

## Phase 1–4 preservation and closure

| Phase | Current classification | Evidence basis | New-direction follow-up |
| --- | --- | --- | --- |
| 1 — ownership and tenancy | `CLOSED WITH FOLLOW-UP` | Accepted ownership/session/API/cache/WebSocket isolation plus the current combined selector. | Apply the same owner, private-IP, event, export, cache, and IDOR rules to chart artifacts, theses, Universes, proposals, approvals, and provider facts. |
| 2 — PostgreSQL and concurrency | `CLOSED WITH FOLLOW-UP` | Three-plane profiles, leases/fencing/outboxes, copy/restore foundations, current heads and selector PASS. | Reuse leases, fences, outboxes and recovery rules for refresh jobs, reservations, proposals, activation, and new services. Production topology and recovery remain open. |
| 3 — causal admission and Component IR v2 | `CLOSED WITH FOLLOW-UP` | Accepted causal review and IR-v2 review, current causal selector PASS, one validator/resolver/registry/hash. | Extend the same IR and admission chain for roles, temporal nodes, Universe computation, normalized chart semantics, and resource requirements. |
| 4 — numeric, market truth and data authority | `CLOSED WITH FOLLOW-UP` | Accepted direct closure, exact protected hashes, SQLite/PostgreSQL migration selectors, numeric/research selector and integration selector PASS. | Extend canonical instruments, observations, truth, datasets and capabilities for point-in-time reference/events, Universe snapshots, price coherence and chart-semantic provenance. |

Detailed file, migration, test, artifact, and hash evidence is in `.agent/runs/programme-rebase-2026-08-24/phase_foundation_audit/report.md`. One caveat remains: a post-review edit changed the direct acceptance report hash while the reviewed package, verdict, frozen product/test bytes, protected bytes, heads and current selectors remain exact. Do not claim every package-listed evidence artifact is byte-identical.

## Preserved architecture invariants

1. One typed immutable Component IR, registry, validator, resolver, hash discipline and authored-to-resolved lineage.
2. Strategy, Universe, Operator Thesis, proposal, approval, Workflow context, deployment, portfolio admission, reservation, order, fill, position and money records are distinct facts.
3. Strategy OS owns canonical instruments; provider symbols and tokens stay at adapters.
4. Data provider and execution broker roles remain separate.
5. Presentation and vendor chart state never enter executable strategy identity.
6. Open positions retain the Strategy, deployment, thesis and exact physical instrument revisions that created them unless a separately reviewed takeover occurs.
7. Paper and live books remain separate and fail closed to live. Entry gates never remove risk-reducing exits.
8. Research approval remains immutable admission consumed at activation. Trade-proposal approval is a separate expiring, single-use fact with pre-execution revalidation.
9. Point-in-time causality, completed bars, explicit missing/stale semantics, exact provenance, and net-of-charges accounting remain mandatory where promised.
10. Redis or another hot store may accelerate reconstructible state only after measurement. PostgreSQL/object storage retain durable authority.

## Revised dependency graph and critical path

```text
Phase 1–4 accepted foundation
        |
        v
P5 identity/runtime debt -> sizing/target position -> admission/reservation/recovery
        |
        v
P6 language + temporal + ResourcePlan + research runtime
        |
        v
P7 point-in-time reference/events -> immutable scopes -> Dynamic Watchlists
        |
        v
P8 activation/readiness -> price coherence -> latency/preflight
        |
        v
P9 chart/thesis/proposal
        |
        v
P10 research integration
        |
        v
P11 integrated frontend
                      |
                      v
       P12 security/operations/deployability
                      |
                      v
         P13 canonical benchmarks/release
```

The machine critical path is fully serial across phase gates: P5 capital correctness → P6 resource/temporal contracts → P7 point-in-time Dynamic Watchlists → P8 readiness/coherence/preflight → P9 thesis/proposal contracts → P10 research integration → P11 integrated user journey → P12 release deployability → P13 release gate.

## Parallel lanes

- Lane A, serialized authority/schema: shared models, migrations, canonical identity, money, approval and deployment facts.
- Lane B, language/research: registry components, conformance, research execution and benchmark fixtures after shared contracts freeze.
- Lane C, provider/data: official-source capability mapping, BYOD/reference/event adapters, conformance and telemetry. Credentials and commercial data stay gated.
- Lane D, frontend: fixture-driven views and accessibility only after backend DTOs/state machines freeze and the owner opens the frontend gate.
- These lanes operate only as declared children inside the current durable stage. They do not make two programme phases active at once. One critical reviewer runs only after each integrated Critical slice and evidence package freeze. Shared schemas, authority, money, runtime and WebSocket semantics never have overlapping writers.

The normative per-subphase deltas, machine-stage linkage, write ownership, migrations, failure hypotheses, tests, rollout/rollback, exit artifacts and routes are in [V1-SUBPHASE-CONTRACT-MATRIX.md](V1-SUBPHASE-CONTRACT-MATRIX.md). A dynamic programme placeholder cannot become executable until its architecture stage generates the exact row-owned capsule or a valid combined capsule under that matrix's rule.

## Phase 5 — execution identity, sizing and deterministic capital admission

**Objective and user problem.** Ensure the same immutable strategy can request a dynamic target position while simultaneous candidates cannot reserve the same capital or lose attribution through restart.

**Preconditions and reusable code.** Accepted Phase 1–4; `execution_binding`, account leases/fencing, paper/live books, `allocator.py`, `CapitalState`, current position and intent records, the proposed capital reservation specification, and the existing Phase 5 graph-address/runtime capsules.

**Subphases.**

1. P5.1 graph-paper attribution schema (`0040`), full address/version separation, non-enabling.
2. P5.2 `P5-ADV-006-RUNTIME`, claim/death/reclaim/current-authority/fencing/exactly-once finalization, plus independent assurance.
3. P5.3 sizing and target-position architecture: fixed units/lots/capital/equity/risk/stop-distance/volatility, fees, caps, rounding, pending-order awareness, and existing-product compatibility.
4. P5.4 durable `CandidateIntent`, `DecisionBatch`, `PortfolioAdmissionDecision`, `CapitalReservation`, campaign/tranche seam and migration plan.
5. P5.5 PostgreSQL transaction implementation, stable tie-breakers, broker-uncertainty and restart/reconciliation behavior; paper shadow receipts before any behavior switch.
6. P5.6 phase integration and one money-critical review.

**Contracts, schemas and APIs.** Add separate content-addressed sizing policy/decision, target-position request, decision batch, reservation, and why-trade/why-not-trade receipts. Extend position lineage additively. Do not silently resize and do not let a signal own capital.

**Frontend.** Contract/read-model requirements only: sizing explanation, batch rank and reservation state. No frontend implementation in this phase.

**Deployment/security/provider/resource impact.** Architecture-changing and migration-required. Owner/account/fence identity is mandatory. Broker margin remains external final authority. No live behavior switch. Resource impact is bounded database contention and reconciliation work.

**Failure modes and tests.** Critical: two-actor contention, stale fence, duplicate batch, crash before/after send, ambiguous broker state, partial fill, cancel/fill crossing, external order, deterministic replay, exact held inventory, reservation mutation and exit availability. Important: rounding, caps, fees, reason text and read models. Use direct PostgreSQL transactions and reversible guard mutations.

**Benchmarks.** A, C and F sizing/admission; B and D remain research/paper; E proposal path later.

**Rollout/rollback and exit.** Additive schema; shadow decision receipts against current allocator; no live activation until owner gate. Rollback disables new admission writes but retains immutable decisions and reconciles any broker-touched reservation forward. Exit requires exact SQLite/PostgreSQL migrations, deterministic contention/recovery, persistent receipts, unchanged legacy behavior, and SPEC/QUALITY PASS.

**Model and parallelism.** User-owned architecture/money root: Sol xhigh. Delegated implementation: Sol medium. Independent review: Sol high. Sizing math can run beside graph-runtime work only before shared schema integration.

## Phase 6 — strategy language, temporal semantics and resource planning

**Objective and user problem.** Give traders a substantial first-party language, generic weekday/seasonal/event routing, and truthful resource requirements without a second DSL or node-count pricing fiction.

**Preconditions and reuse.** Phase 5; accepted Phase 5 language/resource architecture; `PlatformRegistry`, v2 resolver, `DataRequirementPlan`, vector and prefix runtimes, dataset/cache authorities, current durable research jobs.

**Subphases.**

1. P6.1 node contract, five visible families, named roles, state snapshot/reset and `ResourcePlan` identities.
2. P6.2 generic temporal/calendar/DTE/event-relative nodes and branch-level attribution.
3. P6.3 Type 2/4 analytical catalogue and conformance harness.
4. P6.4 Type 1/3/5 intent/state/derivatives catalogue and capability-gated outputs.
5. P6.5 vector/incremental parity, bounded sweeps/cache/artifacts, worker packaging and phase review.

**Changes.** Registry/schema extensions are additive; resource calibration and tier policy remain separate from semantic identity. First-party temporal nodes consume point-in-time calendar facts and cannot hardcode current expiry weekdays. Level 3/4 custom code remains unavailable or research-only behind a security gate.

**Frontend.** Descriptor/API contracts, catalog search/grouping and typed refusal shapes only.

**Deployment/security/provider/resource impact.** Architecture-changing; migrations only for durable snapshots/plans/catalogue if persistence requires them. Lock dependencies and define worker/queue/cache/artifact topology. Provider requirements name capabilities, not tokens. No commercial tier claim until calibration.

**Failures/tests.** Critical: causality, prefix parity, state restart/reset, cache identity and undeclared provider demand. Important: indicator math, warmup, validity, temporal/calendar routing, output mapping, stable resource accounting and at-limit/first-above cases. Routine: catalogue copy and grouping.

**Benchmarks.** A/B/F language coverage and the temporal branches in C/D/E.

**Rollout/rollback/exit.** Feature-gate catalogue families; old v1 components remain readable; no in-place semantic migration. Exit requires one production v2 catalogue, full registered-universe conformance, current cache identities, bounded research runtime evidence and review PASS.

**Model/parallelism.** Architecture and causal review at user-owned Sol xhigh; disjoint catalogue families may use Sol medium after contracts freeze.

## Phase 7 — point-in-time reference/events and Dynamic Watchlists

**Objective and user problem.** Let a trader define a bounded, explainable, reproducible Dynamic Watchlist without using current membership, current market cap or current events as historical truth.

**Preconditions and reuse.** Phase 6; canonical instruments/rulebook/observations/datasets/capabilities; watchlists as fixed aliases; three-plane durability decision; ResourcePlan.

**Subphases.**

1. P7.1 authority-fact durability ADR and bounded point-in-time reference/event contract.
2. P7.2 immutable `InstrumentScope`/Universe definition and static snapshot; operational canonical-instrument binding.
3. P7.3 BYOD-first and selected provider ingestion for market cap/free float, sector/industry, listing/tradability, earnings/corporate events and bounded economic events.
4. P7.4 Dynamic Watchlist definition/evaluation/rank/top-K, staged evaluation, hysteresis/residency/cooldown, leave policy, snapshots and receipts.
5. P7.5 recovery, point-in-time research replay, capacity gate and critical review.

**Changes.** Add immutable definitions/revisions/evaluations/snapshots and append-only event/reference facts with `observed_at`, `effective_at`, `published_at`, revision and source. Existing editable watchlists remain aliases. No general Workflow engine.

**Frontend.** Frozen APIs/read models only until owner gate: fixed/dynamic choice, filters, stage progress, rank reasons, snapshots, resource and eligibility states.

**Deployment/security/provider/resource impact.** Architecture-changing and migration-required. Data rights are an external gate. All new facts are tenant-scoped; current authority-fact plane placement needs an ADR. Staged evaluation and candidate bounds are mandatory before broad universe fan-out.

**Failures/tests.** Critical: survivorship, revised classifications, publication-time leakage, snapshot mutation, stable tie-breaks, concurrent refresh, restart, leave-with-open-position and cross-tenant disclosure. Important: filters/ranking/top-K, cadence, hysteresis and resource receipts. Mutation-test current-state substitution and omitted candidate populations.

**Benchmarks.** C is the vertical gate; A proves fixed adapter; F proves cross-market identity.

**Rollout/rollback/exit.** Start research-only with BYOD fixtures, then paper evaluation. Disable new refresh on rollback, preserve definitions/snapshots and keep deployments bound to exact prior snapshots. Exit requires point-in-time C research, recovery after state loss and no ambiguous current-membership fallback.

**Model/parallelism.** Market-truth architecture/root and final review: Sol xhigh. Reference schema is serialized; provider adapters and fixture-driven UX can run in parallel after it freezes.

## Phase 8 — selectivity, provider coherence, latency and preflight

**Objective and user problem.** Bound expensive data/computation, refuse entry until branches are ready, and prevent signals based on one provider from executing against materially incompatible prices from another.

**Preconditions and reuse.** Phase 7; ResourcePlan, capability profiles, canonical mappings, account leases, deployment/readiness and provider-health seams.

**Subphases.**

1. P8.1 activation-boundary and `OFF/WARM/ACTIVE/COOLDOWN/DATA_READY` contracts.
2. P8.2 runtime/subscription readiness, shared-calculation policy and recovery; Redis decision only after measurement.
3. P8.3 `PriceCoherencePolicy`, comparable field semantics, `DATA_DIVERGENT` state and persisted dual-observation receipt.
4. P8.4 latency/live-eligibility policy and instrumentation from receive through fill.
5. P8.5 resolved deployment/Execution Product Policy/provider capability/preflight receipts.
6. P8.6 recovery, adversarial assurance and review.

**Changes.** Activation remains explicit and cannot be inferred from ordinary conditionals. New entries block while warming or divergent; risk-reducing exits remain available. Provider fallback requires prior semantic approval and resynchronization. Bar-close and measured second-scale eligibility are valid; queue-sensitive/HFT is refused.

**Frontend.** Backend-owned block/degraded reasons and receipts only; later UI consumes them.

**Deployment/security/provider/resource impact.** Architecture-changing, provider-affecting and migration-required for durable decisions. No credentials or network calls in contract slices. Capacity, quotas, event rates, churn, order-action and turnover budgets must be measured.

**Failures/tests.** Critical: wrong mapping, stale/semantic field mismatch, price divergence, provider switch, lost warm state, readiness races, restart, exit path and stale approval inputs. Important: state transitions, resource receipts, shared-subscription tenancy and latency components. Mutate each hard block.

**Benchmarks.** B/C/D/E/F resource, readiness, provider and latency gates.

**Rollout/rollback/exit.** Start receipt-only/shadow; separately feature-gate activation, coherence and preflight decisions. Rollback disables new entries rather than silently weakening checks. Exit requires deterministic degraded behavior, current provider capability decisions, coherence and latency receipts, and review PASS.

**Model/parallelism.** Provider/latency/security architecture at user-owned Sol xhigh; telemetry adapters may run in parallel after policy fields freeze.

## Phase 9 — chart provider, Operator Thesis and hybrid approval

**Objective and user problem.** Let a discretionary trader preserve chart judgment while the machine monitors exact normalized semantics and creates an expiring, revalidated proposal without giving the chart library execution authority.

**Preconditions and reuse.** Phase 8 contracts; owner decision on TradingView access/licence and data display rights; layout-versus-semantic precedent; project ownership; research approval distinction; deployment/cockpit read models.

**Subphases.**

1. P9.1 chart-provider/access/licence ADR and pinned capability contract.
2. P9.2 `ChartWorkspace` plus separate opaque vendor layout/drawing artifacts and adapter.
3. P9.3 normalized allowlisted semantics: PriceLevel, PriceZone, TrendLine/Ray, TimeMarker/Window; structured bias/invalidation/TTL.
4. P9.4 immutable `OperatorThesis` revisions and lifecycle.
5. P9.5 proposal, approval TTL, reject/expire/supersede and immediate pre-execution revalidation.
6. P9.6 forward evidence, recovery, tenant/security and review.

**Changes.** Advanced Charts is conditional, not approved. Trading Platform and chart-owned Broker API are rejected for the V1 proposal path. Vendor locks and IDs are not authority. Fibonacci, channels, patterns and freehand remain visual-only or later seams until exact geometry evidence exists. No general annotation backtesting.

**Frontend.** Implementation remains owner-gated. Backend contracts and fixture-driven view states may precede vendor adoption; the chart canvas needs a keyboard-operable structured semantic table.

**Deployment/security/provider/resource impact.** Architecture-changing, licence-sensitive, frontend-affecting and migration-required. Proprietary bytes stay outside the public repository. CSP, artifact storage, privacy/IP, retention, backup/restore and vendor migrations need exact evidence.

**Failures/tests.** Critical: revision substitution, wrong instrument/provider/dataset, stale/expired approval, changed market/coherence/capital state, position version takeover, tenant leak and chart-to-order bypass. Important: drawing extraction, save/load/tombstones/groups, vendor upgrade/rollback and accessibility. Routine: visual styling.

**Benchmarks.** E is the vertical gate; D uses visual recorder only.

**Rollout/rollback/exit.** Visual-only workspace first, semantic extraction second, thesis monitoring third, paper proposal approval fourth. Each has an independent backend flag. Rollback preserves immutable artifacts and expires proposals; it never reinterprets vendor bytes or changes position ownership. Exit requires official access evidence, exact licence/data gate, allowlist conformance, proposal revalidation and SPEC/QUALITY PASS.

**Model/parallelism.** Vendor/security/approval architecture and final review at user-owned Sol xhigh. Adapter storage and fixture UX may run in parallel only after contracts freeze.

## Phase 10 — research and validation integration

**Objective and user problem.** Let users test every deterministic V1 capability honestly while accumulating prospective evidence for chart strategies that cannot be causally backtested.

**Preconditions and reuse.** Phases 6–9; existing experiments, trials, OOS, walk-forward, Monte Carlo, cache/dataset identities and forward paper receipts.

**Subphases.**

1. P10.1 point-in-time Dynamic Watchlist backtests and snapshot replay.
2. P10.2 temporal/reference/event research integration.
3. P10.3 options/OI/order-flow research only when historical data and licence permit it.
4. P10.4 bounded optimisation, parameter neighborhoods, locked OOS, walk-forward, Monte Carlo and trial evidence.
5. P10.5 forward-only chart/thesis/proposal/paper evidence and post-trade review.
6. P10.6 reconstruction receipt and Benchmarks A/C/F plus research/paper B/D/E.
7. P10.7 performance, causality, evidence and phase review.

**Changes.** Extend existing research ledger and cache identities; never fabricate unavailable history. Annotation-derived historical backtesting is excluded. Every branch retains attribution and effective search-space disclosures.

**Frontend.** Contract/read-model outputs; full integration waits for Phase 11.

**Deployment/security/provider/resource impact.** Migration-required where new receipts persist; worker packaging and storage/retention affected. Provider/data licence controls govern exports. Research QoS cannot delay live protection/reconciliation.

**Failures/tests.** Critical: point-in-time leakage, cache/provider blending, OOS contamination, thesis revision mismatch and replay identity. Important: ranking, optimizer bounds/budget, trial ordering, node math and performance. Routine: result presentation contracts.

**Rollout/rollback/exit.** Feature-gate new data domains; retain existing results; never rewrite evidence. Exit requires deterministic benchmark receipts, first-divergence tooling, no hindsight annotation claim and review PASS.

**Model/parallelism.** Research/market-truth critical work at user-owned Sol xhigh; independent benchmark and math lanes may run at Sol medium after data contracts freeze.

## Phase 11 — integrated hybrid-product frontend

**Objective and user problem.** Deliver one coherent Strategy workspace from chart thesis or systematic graph through research, Dynamic Watchlist, proposal, paper operation and review.

**Preconditions and reuse.** Frozen backend contracts from Phases 7–10 and explicit frontend owner gate. Reuse one React app, centralized API transport, server edit receipts, backend cockpit and accepted visual hierarchy.

**Subphases.**

1. P11.1 correct the WebSocket contract: one first-frame-authenticated, cursor-resumable socket; transport is not health.
2. P11.2 global shell and Strategy-local workspace with exact provenance.
3. P11.3 data/reference/event and fixed/dynamic Universe UX.
4. P11.4 chart workspace, structured semantic annotation and thesis lifecycle UX.
5. P11.5 alert/proposal/approval/paper cockpit and degraded states.
6. P11.6 accessibility, desktop/390 px, large-list/graph performance and usability benchmarks.
7. P11.7 integrated frontend review.

**Changes.** No frontend-owned readiness, authority or joined truth. Each value is current, Unknown, stale, refused or loading. A chart marker never routes an order.

**Deployment/security/provider/resource impact.** Compatible/API-affecting plus chart dependency/CSP/assets. Token-in-URL behavior must be removed. Strategy IP and vendor artifacts need private storage, bounded telemetry and cross-tenant tests.

**Failures/tests.** Critical: false live/ready/authority, stale approval, tenant leak and unsafe control. Important: API integration, resync/reconnect, all error states, drawing form parity, large data and accessibility. Routine: copy/layout.

**Benchmarks.** All A–F operator flows; B/D show research/paper-only eligibility.

**Rollout/rollback/exit.** Backend capability flags per surface; retain current shell/fallback chart during migration. Exit requires frontend test/type/build, browser flows, console/network clean, desktop and 390 px screenshots, benchmark-task completion and review PASS.

**Model/parallelism.** Owner-authorized frontend work may use Sol medium. Critical auth/security/final review uses user-owned Sol xhigh plus one Sol-high independent review.

## Phase 12 — tenancy, security, providers, operations and deployability

**Objective and user problem.** Make the integrated V1 safe for invitees and release-shaped operations without claiming deployment before the production evidence exists.

**Preconditions and reuse.** Integrated product contracts; Phase 1/2 foundations; deployability ledger; provider registry; three database planes; sanctioned deployment script.

**Subphases.**

1. P12.1 object-complete tenancy, authorization, IP privacy and break-glass policy.
2. P12.2 launch-provider/data conformance, credential rotation and rate/failure behavior.
3. P12.3 locked dependencies, reproducible artifacts, service topology and safe configuration.
4. P12.4 empty install, supported upgrades, backup/restore, cutover and forward-repair rollback.
5. P12.5 health/readiness, observability, retention, capacity, QoS and failure drills.
6. P12.6 production-shaped rehearsal without deployment; legal/commercial/data decision matrix clean.
7. P12.7 security/deployability review.

**Changes.** No new product abstraction. Complete the deployability contract for every affected service and schema. A second provider path must be selected from launch need and actual official capability, not broker count.

**Failures/tests.** Critical: IDOR/cache/event isolation, credentials, restore split-brain, migration partials, provider reconnect/reconciliation, capacity degradation and exact-build readiness. Important: logs/metrics/alerts, rotation and support diagnostics. Routine: admin CRUD.

**Benchmarks.** A–F under production-shaped topology with no real-money authority unless separately approved.

**Rollout/rollback/exit.** Only `scripts/deploy.sh`; no deployment in this phase without owner gate. Exit requires `release_deployable` evidence, not merely local runnability, and a clean matrix with no unowned blocker.

**Model/parallelism.** Security/migrations/provider/deployability architecture and final review at user-owned Sol xhigh. Disjoint provider, observability and documentation lanes can run at Sol medium after topology freezes.

## Phase 13 — canonical benchmarks and V1 release hardening

**Objective and user problem.** Prove the complete product through heterogeneous verticals and realistic adversarial failures, then freeze the exact release candidate.

**Subphases.**

1. P13.1 Benchmarks A–F at their declared eligibility levels.
2. P13.2 cross-benchmark security, ownership, reconciliation, recovery and degraded-state matrix.
3. P13.3 backend/research/frontend full suites, builds, deterministic smoke and performance ceilings.
4. P13.4 exact-build release-deployability, rollback and operator runbooks.
5. P13.5 one final independent critical review and owner release decision.

**Preconditions and reuse.** All prior phase reviews accepted; no unresolved Critical defect; every external decision either accepted with evidence or the affected capability explicitly removed from the claimed release, which would require a new owner scope decision.

**Failures/tests.** No new validator language. Use canonical verticals, direct guards, migration/recovery/concurrency tests, real browser flows and reversible mutations of named Critical guards.

**Rollout/rollback/exit.** Feature freeze, clean exact build, supported install/upgrade, rollback/forward-repair drill, signed evidence index, and owner go/no-go. No automatic deployment or live authority.

**Model/parallelism.** Root final review at user-selected Sol xhigh; one independent critical reviewer at the repository-supported Sol-high route.

## Release gates

1. Exact strategy, dataset, Universe, thesis, provider, deployment, capital and execution identities.
2. Deterministic sizing and simultaneous admission with transactional reservation/recovery.
3. Point-in-time Dynamic Watchlists/reference/events and no survivorship/current-state substitution.
4. Explicit activation/readiness, ResourcePlan, provider capability, price coherence and honest latency eligibility.
5. Versioned chart workspace plus bounded normalized semantics; no vendor blob in IR.
6. Proposal approval TTL and complete pre-execution revalidation; exits remain available.
7. Deterministic research loop for representable logic and prospective evidence for chart strategies.
8. Tenant/IP/credential isolation and truthful degraded states.
9. Canonical A–F benchmark evidence at the declared release eligibility.
10. Release-deployable production-shaped install/upgrade/backup/restore/rollback/health/capacity evidence.
11. Backend/research/frontend gates and final independent SPEC/QUALITY PASS.

## Explicit deferred scope

- V1.1 is retired as a separate feature boundary. The label may be used only for post-launch hardening, richer operators, additional low-risk chart semantics, provider breadth and UX polish.
- V1.5: certified liquid single-leg index-options execution and its extra options conformance.
- V2: deterministic Workflows, deeper fundamentals/events, diagnostics/counterfactuals, richer derivatives, optional causal annotation replay and richer chart semantics.
- V3/demand-led: AI chart interpretation, AI Research Agent, ML/model nodes, marketplace/managed models, advanced portfolio/Kelly, international/institutional/queue-position systems.
- Rejected: chart clone, TradingView website/widget data as automated strategy truth, chart-owned Broker API, direct webhook-to-order, silent provider switching, node-count pricing, opaque dealer-positioning fact, HFT/co-location claims, generic Workflow engine in the order path, second IR or authority, and proof recursion without a named Critical false-result hypothesis.

## Schedule basis and confidence

The window uses nine remaining integrated phases, 54 dependency-bearing subphases, four Critical migration/authority clusters, one owner-gated frontend phase, and two unresolved external data/vendor decisions. It follows the serial machine DAG. Each estimate below is elapsed working-day effort after allowed within-stage child parallelism and includes one proportional correction/recheck allowance for its Critical gate. The current tree has accepted local foundations but no committed Phase 5 product implementation and no release-deployability proof.

| Serial cluster | Working-day range | Cumulative working days from 25 Aug 2026 |
| --- | ---: | ---: |
| Phase 5 identity/runtime/capital | 12–18 | 12–18 |
| Phase 6 language/temporal/resource/research runtime | 15–22 | 27–40 |
| Phase 7 point-in-time data and Dynamic Watchlists | 18–28 | 45–68 |
| Phase 8 activation/coherence/latency/preflight | 15–22 | 60–90 |
| Phase 9 chart/thesis/proposal contracts | 18–28 | 78–118 |
| Phase 10 research/validation integration | 15–22 | 93–140 |
| Phase 11 integrated frontend/browser evidence | 18–28 | 111–168 |
| Phase 12 security/providers/deployability | 20–30 | 131–198 |
| Phase 13 benchmarks/release review | 10–15 | 141–213 |

At five working days per week, 141–213 working days place the serial completion range in March–June 2027. The canonical window rounds outward to **15 March–30 June 2027** for owner-gate and calendar variance. It becomes unbounded when a required vendor/data/frontend decision remains unresolved; it never silently substitutes a lower-scope product.

Confidence is medium-low until TradingView and data decisions close, medium after P7/P9 contract freezes, and high only after Phase 12 proves release deployability. No schedule authorizes deployment, live authority, orders or money.
