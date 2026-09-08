# MASTER PROMPT — Strategy OS Vision Rebase, V0 Commercial Release, Parallel Architecture Review, and V1 Continuity

You are the principal programme orchestrator, product-architecture owner, and integration authority for Strategy OS.

This is not a request for a generic roadmap or a broad repository rewrite. It is a coordinated programme with four simultaneous objectives:

```text
A. Update and reconcile the complete Strategy OS product vision through V6.
B. Move the research-first commercial V0 toward release now.
C. Run deep architecture, systems-design, and professional-engineering reviews in parallel.
D. Continue V1 controlled-execution architecture planning without contaminating V0 scope.
```

The owner wants maximum useful parallelism, but not uncontrolled agents editing the same contracts. Parallelize research, inventory, analysis, benchmarks, and disjoint implementation. Serialize shared schemas, canonical interfaces, migrations, and merge authority.

---

## 0. Required attachments and reading order

Read every attached file before making a product or architecture decision.

### Existing canonical sources

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

### New owner-direction package

```text
00-README-FIRST.md
01-UPDATED-OWNER-VISION-V0-TO-V6.md
02-V0-COMMERCIAL-RESEARCH-AND-ALERTS-RELEASE-DIRECTIVE.md
03-ARCHITECTURE-EVOLUTION-AND-NO-DEAD-END-INVARIANTS.md
04-SCALE-AND-SYSTEMS-DESIGN-50-TO-10000-USERS-BRIEF.md
05-PROFESSIONAL-ENGINEERING-CORPUS-REVIEW-V4.md
06-V1-ARCHITECTURE-CONTINUITY-LANE.md
07-RAZORPAY-GOOGLE-AUTH-AND-ADMIN-WORKSTREAM.md
08-MATURITY-GATED-PRODUCT-SEQUENCE.md
```

### Recovered prior professional-engineering files

```text
STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V3_SIMPLICITY_GUARDED_2026-08-28.md
STRATEGY_OS_PROFESSIONAL_ENGINEERING_REFERENCE_PROGRAM_2026-08-28.md
STRATEGY_OS_CODEX_SIMPLICITY_AND_ANTI_OVERENGINEERING_DIRECTIVE_2026-08-28.md
```

Also locate and read:

- the latest progress mapper/programme authority;
- current active goal/capsule and phase gates;
- Phase 1–4 completion/handoff evidence;
- all accepted ADRs;
- current architecture-intelligence packages;
- frontend/design authority and actual frontend repositories/worktrees;
- current auth, billing, admin, signal, alert, node, data, research, provider, execution, and deployment code;
- current repository-state and dirty-worktree reports;
- any newer owner decisions.

Use precedence:

```text
latest explicit owner decision
→ this 29 August owner-direction package for product scope and intent
→ latest accepted progress mapper for actual implementation state
→ active goal/capsule and accepted ADRs
→ canonical technical steers
→ older scope/version documents where not superseded
```

Do not assume any file is current merely because it says “canonical.” Resolve conflicts explicitly.

---

## 1. Record repository context before all work

Print and persist:

```text
pwd
git rev-parse --show-toplevel
current branch and commit
git status --short
git worktree list
remotes
runtime/toolchain versions
frontend/backend/database/job/cache/websocket/broker/deployment technologies actually found
```

Preserve every unrelated modification and untracked file. Never reset, clean, discard, overwrite, or silently migrate inherited work.

If the repository uses active capsules/goals or one-durable-goal rules, obey them. Create documentation/research worktrees that do not violate programme ownership. Do not bypass the project’s repository-review gate.

---

## 2. Current owner decisions — binding summary

### 2.1 Product identity

Strategy OS is an operating system for market-related capital and risk decisions, beginning with systematic/discretionary-systematic traders and expanding only after trust and demand are earned.

The durable lifecycle is:

```text
idea/exposure/mandate
→ formal definition
→ data and market truth
→ research/validation
→ candidate actions or structures
→ portfolio feasibility/admission
→ recommendation and authority
→ signal/execution/allocation
→ monitoring/reconciliation
→ evidence/review
```

### 2.2 V0 is now the immediate commercial focus

V0 is a research, evidence, signal-monitoring, and alerts product.

It must include:

- coherent web application and onboarding;
- authentication, ownership, tenancy, and secure sessions;
- Google sign-in where compatible with the actual stack;
- Razorpay Test Mode integration, billing state, and entitlements;
- a minimal admin/support panel;
- all five user-facing node families functioning coherently according to their contracts;
- supported strategy creation/versioning and research;
- cost-aware backtests and only those advanced validation features that are genuinely correct and usable;
- signal monitoring;
- a first-class Alerts Inbox;
- alert detail explaining exact strategy revision, conditions, data freshness, and reason/evidence receipt;
- useful errors, telemetry, backups, restore, migration, support, and release readiness.

V0 has **no public real-money execution authority**. Existing internal/paper/execution foundations may remain, but no public route may accidentally bypass the V0 boundary.

The purpose of V0 is to validate product-market fit, UI comprehension, recurring research/alert usage, trust, retention, and willingness to pay.

### 2.3 Alerts are a first-class V0 product surface

Do not treat signals as log lines.

Create or verify a canonical separation:

```text
StrategyRevision
→ SignalMonitor
→ SignalEvent
→ SignalAlert
→ delivery/read/acknowledgement state
```

Alerts must be durable, tenant-safe, deduplicated, filterable, expirable, attributable, and explainable. A signal is not execution authority.

### 2.4 Long-term V0→V6 direction

The provisional product ladder is:

```text
V0 — commercial research, evidence, signals, Alerts Inbox, auth/payments/admin; no public live orders.

V1 — controlled operation/execution: sizing, target position, capital admission, provider preflight, paper/shadow, bounded live authority, order lifecycle, reconciliation, security.

V1.5 — Dynamic Watchlists and derivative depth: advanced screening, richer nodes/data/providers, certified bounded single-leg options execution.

V2 — active Portfolio and hedge intelligence: external sleeves, RiskModelSnapshots, allocation/feasibility, multiple solution classes, ProposedPortfolioRevisions, workflows/diagnostics.

V3 — two marketplace products: Strategy Asset Marketplace for downloadable/importable packages and Managed Model Allocation for outside investors through appropriate regulated structures; creator economics and portfolio-of-strategies.

V4 — certified multi-leg Position Campaigns, advanced arbitrage/hedging, institutional/fund tooling, and platform/partner-operated products where legally and operationally ready.

V5/V6 — corporate Treasury and Enterprise Market-Risk OS: operating exposures, TreasuryMandates, hedge programmes, multi-entity/OTC/accounting/governance, and global expansion.
```

These labels are provisional. Sequence by dependencies and maturity, not dates.

### 2.5 Key long-term concepts

Preserve, without implementing now:

- Dynamic Watchlists that evolve from instrument screens to opportunity/structure/portfolio-admissible candidate engines;
- equity cash-futures arbitrage as a reference vertical;
- multi-leg options/futures/cash structures such as verticals, calendars, butterflies, condors, futures calendars, baskets, rolls, collars, pairs, and hedges;
- one economic Position Campaign owning many exact legs/orders/fills;
- final and worst-intermediate-state margin, liquidity, slippage, partial-fill recovery, aggregate P&L/Greeks, exact reconciliation;
- speculation, hedging, and arbitrage on one common engine;
- Portfolio evolving from passive analytics into an active capital/risk control plane;
- allocation among existing strategies plus recommendations for eligible new strategies/instruments/hedges;
- LP/QP/MIP/scenario-based optimization as appropriate, with honest feasible/infeasible explanations;
- immutable RiskModelSnapshots and uncertainty;
- external/native/opaque PortfolioSleeves;
- ProposedPortfolioRevisions requiring human approval;
- several solution classes rather than one opaque optimum;
- Strategy Asset Marketplace packages containing graphs, components, watchlist presets, optimized configurations, sizing/risk settings, evidence, requirements, and documentation;
- Managed Model Allocation for outside investors specifying beta, asset exposure, arbitrage allocation, derivatives limits, liquidity/lock-up, horizon, risk, and evidence constraints;
- platform conflict disclosures and no covert preference for Strategy OS-owned products;
- institutional bulk licensing/private deployments for funds/managers;
- proprietary, partner, white-label, co-managed, or platform-operated funds later;
- ultimate corporate treasury exposure management across FX, rates, commodities, fuel, procurement, receivables/payables, debt, basis, volume, counterparty, and liquidity risk;
- natural hedges and business mitigations alongside derivatives;
- global expansion through integrations, rights, jurisdictions, accounting, and market semantics rather than a new core thesis.

### 2.6 Codebase and agentic compounding

The owner expects codebase reuse and improving agent workflows to accelerate progress. Do not interpret that as permission to lower financial/security correctness or implement the terminal vision early.

Move quickly on learning, bounded building, tests, user feedback, and documentation. Move deliberately on money paths, irreversible migrations, external capital, and complex execution.

---

## 3. Multi-agent/worktree topology

Use separate subagents or equivalent isolated worktrees. If the environment cannot spawn subagents, emulate the lanes sequentially and say so; do not fabricate parallel execution.

### Agent 0 — Programme Orchestrator and Merge Authority

Responsibilities:

- authority map;
- dependency graph;
- write ownership;
- contract freeze;
- collision resolution;
- classification and sequencing;
- merge/integration decisions;
- owner-decision queue;
- final reports.

Agent 0 should avoid broad implementation. It is the only authority that assigns shared schema/contract changes.

### Agent A — V0 Product and Release Owner

Owns:

- end-to-end V0 user journeys;
- product shell/onboarding;
- node-family conformance coordination;
- research/evidence UX integration;
- V0 scope/refusal;
- release gates;
- product telemetry;
- final V0 integration plan.

Dedicated path/worktree suggestion:

```text
plan/v0-commercial-research-release
```

### Agent B — Signal and Alerts Owner

Owns:

- SignalMonitor/SignalEvent/SignalAlert contracts;
- deduplication and persistence;
- Alerts Inbox APIs and UI;
- alert detail and reason receipts;
- websocket/catch-up behavior;
- alert lifecycle tests.

Suggested worktree:

```text
feature/v0-signal-alerts
```

Do not edit auth/billing schemas unless assigned by Agent 0.

### Agent C — Auth, Razorpay, Entitlements, and Admin Owner

Owns:

- current auth/tenant audit;
- Google sign-in integration;
- Razorpay Test Mode checkout/order/subscription path chosen from actual product decisions;
- webhook signature/idempotency/reconciliation;
- internal entitlements;
- billing UI;
- minimal admin/support boundary;
- secret handling and live-mode gate.

Suggested worktree:

```text
feature/v0-auth-billing-admin
```

### Agent D — Architecture Evolution Owner

Initially read-only, documentation/ADR path only.

Owns:

- new object model/seams;
- signal versus economic intent;
- ExecutionProductPolicy/ExecutionStructurePolicy;
- PositionCampaign/leg/tranche future compatibility;
- Portfolio/RiskSnapshot/ProposedRevision seams;
- marketplace type split;
- enterprise EconomicExposure seam;
- no-dead-end gap matrix.

Suggested worktree:

```text
audit/architecture-v0-v6-evolution
```

Do not implement future nouns. Raise only proven destructive assumptions.

### Agent E — Systems Design and Scale Owner

Initially read-only plus benchmark scripts in an isolated path.

Owns:

- actual topology and sources of truth;
- workload models for 50/500/2,000/5,000/10,000 users;
- research-heavy, alerts-heavy, and future execution-heavy profiles;
- performance/capacity experiments;
- data/provider constraints;
- cost/unit economics;
- team/funding triggers;
- measurable architecture adoption triggers;
- explicit changes not required.

Suggested worktree:

```text
audit/systems-scale-50-10000
```

### Agent F — Kleppmann and Professional Engineering Corpus Owner

Read-only with respect to production code until findings are assigned.

Owns:

- exhaustive bounded corpus inventory;
- PDFs, slides, diagrams, graphs, transcripts, and artifacts;
- DDIA 2e delta;
- similar professional sources;
- source/claim registry;
- repository mapping;
- failure hypotheses;
- V0→V6 classification;
- cargo-cult rejection.

Use both the recovered V3 prompt and `05-PROFESSIONAL-ENGINEERING-CORPUS-REVIEW-V4.md`.

Suggested worktree:

```text
audit/kleppmann-professional-engineering-v4
```

### Agent G — V1 Architecture Continuity Owner

Read-only/planning until assigned implementation.

Owns:

- current V1 authority/status;
- sizing/target-position/capital admission;
- provider preflight;
- order lifecycle/idempotency;
- exact position ownership;
- reconciliation/protection/degraded states;
- V0→V1 migration;
- future multi-leg seam without multi-leg implementation.

Suggested worktree:

```text
plan/v1-execution-architecture-continuity
```

### Agent H — Integration, Security, and Verification Owner

Owns independent review after contracts and implementations exist:

- cross-lane contract compatibility;
- migration tests;
- auth/tenant security;
- payment/entitlement adversarial cases;
- alert duplicates/restarts;
- node conformance;
- V0 no-execution proof;
- full user journeys;
- build/type/test/deploy/rollback evidence.

Suggested worktree:

```text
audit/v0-integration-assurance
```

---

## 4. Parallelism and collision rules

1. Begin all lanes with read-only inventory and documents.
2. Agent 0 creates `WORKSTREAM-OWNERSHIP-AND-COLLISION-MATRIX.md` before implementation.
3. Only one agent owns each shared contract, table, migration sequence, API namespace, or canonical document at a time.
4. Research agents do not opportunistically fix production code.
5. A confirmed blocker is handed to Agent 0 with exact files, test, migration, and collision analysis.
6. Shared schema changes are serialized.
7. Frontend may use typed mocks only from a frozen contract; it may not invent backend semantics.
8. Use small commits tied to finding/requirement IDs.
9. Do not mix unrelated cleanup.
10. Preserve active capsule/phase gates.
11. Every lane states whether it actually ran in parallel; do not claim delegation that the environment did not perform.

The desired parallel pattern is:

```text
parallel discovery/research/UX planning
→ authority and contract freeze
→ disjoint implementation
→ independent assurance
→ controlled merge
```

not:

```text
many agents editing the same repository and hoping Git resolves architecture
```

---

## 5. Phase 0 — mandatory programme lock before implementation

Agent 0 must produce:

```text
docs/programme/2026-08-29/
├── 00-REPOSITORY-CONTEXT.md
├── 01-CURRENT-AUTHORITY-MAP.md
├── 02-WORKSTREAM-OWNERSHIP-AND-COLLISION-MATRIX.md
├── 03-CURRENT-PRODUCT-AND-CODE-GAP-MAP.md
├── 04-V0-DEPENDENCY-ORDER.md
├── 05-V1-PARALLEL-CONTINUITY-BOUNDARY.md
├── 06-OWNER-DECISIONS-AND-SECRETS-QUEUE.md
└── 07-PROGRAMME-STATUS-DASHBOARD.md
```

Gap-map statuses:

```text
EXISTS AND VERIFIED
EXISTS BUT UNVERIFIED
PARTIAL
MISSING
BLOCKED ON OWNER ACTION/CREDENTIAL
BLOCKED ON EXTERNAL PROVIDER/RIGHTS
DEFERRED
CONTRADICTED BY CURRENT CODE
```

Do not begin broad feature work until the active capsule and write ownership are compatible.

---

## 6. V0 implementation order

Adapt to actual dependencies, but prefer:

### 6.1 Foundation and authority

- auth/session/tenant audit;
- product entitlement boundary;
- V0 no-public-execution feature/authority gate;
- migration and ownership map.

### 6.2 Node/research product integrity

- five-node-family matrix;
- fix only exposed V0 correctness/usability gaps;
- research flow and evidence persistence;
- performance profiling before optimization.

### 6.3 Signal and alert contracts

- canonical SignalEvent/SignalAlert;
- persistence, deduplication, TTL, reasons;
- API and event delivery.

### 6.4 Auth/billing/admin

- Google sign-in using existing maintained stack;
- Razorpay Test Mode keys and integration;
- webhook verification and idempotent entitlements;
- billing UI;
- admin/support controls and audit.

### 6.5 Alerts UI and onboarding

- inbox;
- detail view;
- filtering/read/acknowledgement;
- return-to-strategy/evidence;
- starter flow and representative alert.

### 6.6 Operational hardening

- backups/restore;
- migrations from zero/current state;
- structured errors/logs;
- SLOs/telemetry;
- rate/resource limits;
- security tests;
- deployment/rollback;
- user-journey assurance.

No stage may expose public execution to make the product look more complete.

---

## 7. Browser-assisted Razorpay/Google task

If browser control is available:

1. Navigate to the intended Razorpay account.
2. Pause for the owner to select/sign in and complete password/OTP/2FA.
3. Explicitly switch to Test Mode.
4. Generate Test API keys through the current official dashboard path.
5. Never paste or print the Key Secret.
6. Store it directly in the approved local/deployment secret store.
7. Configure a distinct test webhook secret and endpoint.
8. Create a test subscription plan only if the current V0 business model is recurring and the amount/cadence are already owner-approved.
9. Return a redacted setup receipt showing mode, key-ID suffix, webhook URL/status, and missing owner decisions.
10. Do not enter Live Mode, submit KYC/bank changes, or make real charges.

If browser control is unavailable, do not claim completion. Produce the exact owner handoff, prepare the code/config with secret placeholders, and continue all non-secret work.

The owner must retain control at login, OTP/2FA, key generation, live-mode, bank, KYC, and irreversible account actions.

---

## 8. Architecture and V1 non-contamination rule

The long-term vision changes what must remain representable, not what V0 must implement.

Do not pull into V0:

- Dynamic Watchlist product;
- public live execution;
- multi-leg campaigns;
- portfolio optimizer;
- marketplace;
- managed models/funds;
- enterprise treasury;
- global broker infrastructure;
- speculative distributed systems.

Raise a V0 architecture change only when current code:

- makes signal/alert correctness impossible;
- breaks tenant/research/payment correctness;
- permanently assumes one signal equals one broker order;
- destroys exact position/strategy/data identity;
- makes later additive migration genuinely impossible;
- contains a confirmed critical security/correctness defect.

Otherwise document the seam and defer implementation.

---

## 9. Professional engineering review requirements

Agent F must not stop at the Martin Kleppmann homepage.

It must inventory the site graph, archives, talks, first-party PDFs, slides, diagrams, figures, course resources, linked primary artifacts, and usable transcripts under the bounded crawl policy.

It must also maintain a professional reference programme using primary/official sources such as:

- Jepsen and PostgreSQL official docs;
- AWS Builders' Library;
- Google SRE;
- OpenTelemetry;
- Stripe/Modern Treasury/TigerBeetle for money and reconciliation;
- OWASP, CISA, NIST, SLSA;
- TLA+/Hillel Wayne/Hypothesis/FoundationDB testing;
- Temporal/DBOS/Restate only as comparative references;
- LEAN, NautilusTrader, Freqtrade, hftbacktest, and official broker/exchange docs for trading semantics.

Every external claim must become:

```text
source and exact location
→ system assumptions
→ Strategy OS failure hypothesis
→ actual repository evidence
→ narrowest safe response
→ test/model/benchmark
→ release owner
→ migration/rollback
→ implemented/deferred/rejected
```

No architecture by authority.

---

## 10. Scale review requirements

Agent E must model approximately 50, 500, 2,000, 5,000, and 10,000 users, but use workload dimensions rather than user count alone.

Include:

- DAU/concurrency;
- research jobs and dataset size;
- signal monitors and alert bursts;
- websocket sessions;
- provider subscriptions/quotas;
- storage growth;
- future deployments/orders/fills;
- billing/admin/support load;
- p50/p95/p99;
- database and worker limits;
- cost per user/job/monitor/deployment;
- team and funding triggers;
- security/recovery maturity;
- measurable infrastructure-adoption triggers.

Default to preserving the current simple topology unless measured evidence requires change.

---

## 11. V1 continuity requirements

Agent G must keep V1 planning alive in parallel.

It must deeply review:

- sizing and target-position semantics;
- simultaneous capital admission and transaction boundaries;
- pending orders and idempotency;
- provider capability/preflight;
- order timeout ambiguity;
- partial fills/cancel-replace;
- exact position ownership;
- protection/degraded states;
- reconciliation and evidence;
- V0→V1 migration;
- future multi-leg seams.

It may not expose broad public execution in V0 or implement multi-leg structures merely because the future vision now includes them.

---

## 12. Required classification system

Every finding, feature, source-derived suggestion, and code change must be classified:

```text
V0 RELEASE BLOCKER
V0 MUST IMPLEMENT
V0 HARDENING
V0 SHARED FOUNDATION
V1 CONTROLLED EXECUTION
V1.5 DISCOVERY/OPTIONS
V2 PORTFOLIO/HEDGE INTELLIGENCE
V3 MARKETPLACE/MANAGED ALLOCATION
V4 MULTI-LEG/INSTITUTIONAL/FUND
V5/V6 ENTERPRISE TREASURY
SAFE TO DEFER
REJECTED OVERENGINEERING
REQUIRES OWNER DECISION
REQUIRES LEGAL/COMMERCIAL/DATA-RIGHTS DECISION
ALREADY CORRECT
```

Do not silently change a release label. Record rationale and authority.

---

## 13. Testing and verification policy

Use risk-weighted testing.

### Critical

- auth/session/tenant isolation;
- payment/webhook/entitlement state;
- strategy/data/evidence identity;
- anti-look-ahead;
- alert deduplication/restart;
- migrations/data loss;
- V0 no-execution authority;
- future capital/order/ledger paths before reachability.

Require realistic failure hypotheses, RED→GREEN where a bug exists, database/integration proof, and recovery tests.

### Important

- node math and conformance;
- research calculations;
- API/UI alert workflows;
- provider adapters;
- caching;
- product telemetry.

Use focused unit/integration/regression tests.

### Routine/trivial

Use typecheck/build/smoke and affected tests. Do not maximize test count.

---

## 14. Mandatory final outputs

At the end of the first orchestration cycle, return:

### A. Programme status

- exact lanes actually launched;
- whether parallel subagents/worktrees were available;
- branch/worktree/commit for each;
- current active capsule compliance;
- collisions and resolutions.

### B. Vision update

- files created/updated;
- authority changes;
- V0→V6 map;
- unresolved product/version conflicts.

### C. V0 release state

- end-to-end gap matrix;
- completed code/UX;
- auth/billing/admin status;
- Razorpay Test Mode status with secrets redacted;
- node-family status;
- Alerts Inbox status;
- tests and user journeys;
- blockers and owner actions.

### D. Architecture review

- confirmed destructive assumptions;
- seams documented;
- changes made versus deferred;
- no-dead-end proof;
- complexity delta.

### E. Systems design and scale

- actual topology;
- stage models;
- bottlenecks;
- costs and funding/team triggers;
- infrastructure adoption registry;
- changes explicitly not needed.

### F. Professional corpus review

- coverage counts;
- PDFs/visuals examined;
- highest-impact findings;
- repository mappings;
- source registry;
- cargo-cult changes rejected;
- remaining inaccessible material.

### G. V1 continuity

- current status;
- architecture decisions;
- shared V0 foundations;
- critical tests/plans;
- no-contamination assurance.

### H. Verification

List exact commands/results for:

- backend/frontend tests;
- type/build;
- migrations;
- auth/tenant/security;
- payment/webhook;
- alert duplicates/restart;
- research identity/causality;
- deployment smoke/rollback;
- benchmarks where performed.

### I. Residual risk

State what was not proven. Never convert missing evidence into confidence.

End with:

```text
STRATEGY OS PROGRAMME OUTCOME

V0 user journey status:
V0 public execution authority reachable? YES/NO
Google auth status:
Razorpay Test Mode status:
Alerts Inbox status:
Five node families status:
Critical blockers:
Owner actions required:
Parallel lanes actually completed:
Shared-contract collisions prevented:
Architecture components added/removed:
Professional sources/PDFs inventoried and reviewed:
Scale stages modeled:
V1 planning status:
Future seams preserved:
Future features deliberately not built:
Next exact implementation capsule:
```

---

## 15. Begin now

Start by:

1. printing repository/worktree context;
2. locating the active programme/capsule;
3. reading all authority documents;
4. creating the authority map and ownership/collision matrix;
5. launching the read-only discovery phase for Agents A–G in parallel where the environment genuinely supports it;
6. returning the first programme checkpoint before any shared schema migration or broad implementation.

Do not ask a broad “what should I do?” clarification. Make evidence-based decisions, isolate genuine owner-only actions, and proceed.
