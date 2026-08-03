# Strategy Operating System execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` for the active
> slice. Create a separate detailed test-first plan before implementing any later slice whose
> contracts are not specified at near-term resolution here.

**Goal:** Deliver a coherent Strategy Operating System through ordered, independently verified
vertical slices without crossing live-money gates.

**Architecture:** The Component IR is the common language; editor, research, execution and
distribution produce or consume it through declared workstream interfaces. Mutable presentation
and organisational state sits beside immutable executable graph versions, and deployment remains
the execution root.

**Tech stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite, pytest, React,
TypeScript, Vite and Vitest.

- **Plan owner:** engineering executive layer
- **Status date:** 2026-08-03
- **Branch:** `feat/exec-completeness`
- **Current slice:** S1.1 sparse layout persistence and API
- **Next product checkpoint:** a user can move a graph node, save and reload the layout, and
  prove that executable identity did not change.

This is the sequential completion plan for the Strategy Operating System. It coordinates the
workstreams; it does not replace their contracts or the Component IR RFC. Near-term slices are
specified at implementation resolution. Later stages stay at product-outcome resolution until
earlier work supplies evidence that makes detailed planning defensible.

## 1. Operating rules

- The Component IR remains the common language. No slice may create a second executable graph
  schema, validator, resolver or statistical-gate pipeline.
- A slice is complete only after focused tests, invalid-path tests, applicable regression checks,
  guard-failure proof, documentation, a bounded commit and a verified remote push.
- Presentation state is mutable and stored beside executable artefacts. It never contributes to
  graph, experiment, component or node-cache identity.
- Research may consume `app.ir`; `app.ir` never consumes research. Research stays isolated from
  execution, broker and capital-allocation modules.
- Local implementation and release preparation continue without deployment approval. Live-money
  execution, sizing, routing, reconciliation, risk-control and IR-runtime changes stop at the
  production boundary for owner approval.
- Every database change uses Alembic, proves upgrade from the current schema and a production-shaped
  prior schema, proves downgrade or documents why rollback is restore-based, and keeps model and
  migration schemas equal.
- `docs/CONTINUE.md` is the executable handoff. This plan records programme order; the handoff
  records the exact resume command and latest evidence.

Status values are `done`, `active`, `ready`, `blocked`, and `later`. `Blocked` names the gate;
`later` means dependencies are deliberately incomplete, not abandoned.

## 2. Product outcomes and workstream ownership

| Outcome | Owning streams | Completion checkpoint |
|---|---|---|
| Stable programme and trustworthy delivery | Executive, WS-06, WS-07 | Remote state, CI, handoff and branch-integration strategy agree with the repository |
| Durable visual authoring | WS-04 with WS-01 and WS-07 contracts | A graph can be laid out, edited, validated, versioned and reproduced by content address |
| End-to-end research decision flow | WS-03, WS-04, WS-07 | An immutable graph version can run an experiment whose evidence supports an explicit approval or rejection |
| Versioning and daily review | WS-04, WS-08, WS-07 | Users can compare versions, findings and approval history without reconstructing provenance |
| Reversible execution integration | WS-01, WS-02, WS-06, WS-07 | Local parity, replay, shadow and rollback evidence is complete before any live adoption |
| Operational cockpit | WS-08 with WS-02/06/07 | Health, deployments, orders, positions, reconciliation, alerts and approval queues are visible |
| First-class data identity | WS-07, WS-03, WS-02 | Datasets have explicit identity, lineage, validation, replay and retention boundaries |
| Safe packaging and marketplace | WS-05 with WS-01/03/07 | Signed, reproducible packages install under a defined trust and sandbox policy |
| Distribution and ecosystem | Executive plus affected streams | External APIs, integrations and commercial controls build on stable product objects and security contracts |

## 3. Current and near-term sequence

| Slice | Outcome | Depends on | Status |
|---|---|---|---|
| S0.1 | Verify authoritative checkout, Git/worktree/remote state and WS-04 commits | none | done |
| S0.2 | Independently verify and push the read-only graph API/viewer stack | S0.1 | done — remote at `071a1a1` |
| S0.3 | Reconcile coordination documents and establish this master plan | S0.2 | done — `4c0eda2` |
| S0.4 | Add fail-closed CI for deterministic backend, frontend and migration checks | S0.3 | done — workflow and contract test in the current CI slice |
| S1.1 | Persist sparse layout records and expose closed layout read/write contracts | S0.4, F13, WS-07 migrations | active |
| S1.2 | Load, drag and conflict-safe save node positions in the React viewer | S1.1 | later |
| S2.1 | Accept the minimum product-object architecture and persistence contract | S1.1 evidence | later |
| S2.2 | Persist projects, graph artefacts and immutable graph versions | S2.1 | later |
| S3.1 | Add a closed editing API over `app/ir/edit.py` with immutable version writes | S2.2 | later |
| S3.2 | Add typed visual mutations, validation feedback, undo/redo and accessible controls | S3.1 | later |
| S3.3 | Prove visual/hand-authored content-address equivalence and lossless reload | S3.2 | later |
| S4.1 | Bind immutable graph versions to the existing research experiment flow | S3.3 | later |
| S4.2 | Surface evidence, rejection reasons, comparison and deployment-candidate creation | S4.1 | later |

### S0.3 — programme reconciliation and execution plan

**Problem.** Coordination documents contradict landed code and cannot reliably hand work to a
new session.

**User-visible outcome.** None directly. Engineering can resume without re-discovering which
editor, research and UI capabilities already exist.

**Boundary and likely files.** Documentation only:
`docs/PROGRESS.md`, `ROADMAP.md`, `CONTINUE.md`, `engineering/WORKSTREAMS.md`,
`engineering/EXECUTIVE.md`, `engineering/DEPENDENCIES.md`, and WS-01/03/04/08 documents.

**Acceptance and evidence.**

- Record 19 authored nodes/47 authored edges separately from 18 resolved view nodes/35 view
  edges, derived from `expanding_z.GRAPH` and `graph_view(resolve(...))`.
- Remove the duplicate incomplete WS-03 F14 item; its completed item and interface contract must
  agree.
- Record the read-only application route in WS-01 and component-render tests in WS-08.
- Make WS-04 status, dependencies, next slice and last verified commit agree across executive
  documents.
- `rg` searches for the rejected stale phrases return no live-state claims.
- Inspect the documentation diff, commit it alone and verify the remote branch contains it.

**Rollback.** Revert the documentation commit. No runtime or migration state changes.

### S0.4 — fail-closed continuous integration

**Problem.** The branch has no repository CI, so local acceptance claims are not enforced on
future pushes or integration work.

**User-visible outcome.** Regressions in the Strategy OS, live-safety guards, migrations or the
frontend block integration before review.

**Boundary and likely files.** `.github/workflows/strategy-os-ci.yml`, a parsed contract test,
and CI documentation in this plan/`CONTINUE.md`. Do not change product behaviour in this slice.

**Acceptance and evidence.**

- Backend job installs the declared requirements, runs `tests` and `research_tests`, and fails
  when no tests are collected. It includes architecture/import guards and migration/model
  equivalence. The repository has no backend lockfile; locking remains a named hardening task.
- Deterministic smoke job runs `scripts/dryrun.py 700` and `scripts/backtest_smoke.py` with mock
  provider and no secrets.
- Frontend job uses the repository lockfile, then runs the complete Vitest suite, TypeScript
  checking and production build.
- No command hides an earlier exit code through a pipeline or optional skip. Credential-dependent
  checks are named and excluded rather than reported green.
- Guard-failure proof: temporarily point one job at a nonexistent test directory or suppress a
  required command in a local copy; the CI validation check must fail for the intended reason.
- Run the workflow-equivalent commands locally, inspect the workflow syntax and commit/push the
  slice separately.

**Migration and rollback.** None. Revert the workflow commit if the runner environment is
incorrect; local acceptance commands remain authoritative until the corrected workflow lands.

### S1.1 — sparse layout persistence and API

**Problem.** The graph viewer derives every position on each read. It cannot preserve a user's
layout, and the persistence boundary required by F13 is unproven.

**User-visible outcome.** A moved node position and justified viewport state survive reload while
the strategy's executable identity remains byte-for-byte unchanged.

**Architectural boundary.** WS-07 owns the SQLAlchemy model and Alembic revision. WS-04 owns a
small layout repository/service and HTTP contracts. WS-01's `Layout` and `graph_view()` remain
unchanged unless their existing export is demonstrably insufficient. The fixed graph catalogue
remains read-only; this slice stores presentation state only.

**Data contract.**

- Key each record by `(graph_identifier, graph_version, instance_id)` with finite numeric `x`
  and `y`, an update timestamp and a monotonic revision used for optimistic concurrency.
- Store only moved authored instance IDs. A missing row means derived placement.
- `GET` returns the current sparse layout plus revision. `PUT` replaces the sparse layout under
  an expected revision; stale revisions return 409 and never partially write.
- Reject unknown graph identifiers/versions, unknown or derived-only instance IDs, duplicate IDs,
  non-finite coordinates and extra request fields.
- Orphan policy: reads filter rows that no longer match an authored instance; a successful write
  deletes those rows transactionally. Graph-version creation later performs eager cleanup. This
  keeps an old layout harmless without coupling layout persistence to graph mutation that does
  not exist yet.

**Likely files.** `backend/app/db/models.py`, a new Alembic revision,
`backend/app/api/ir_layout_routes.py` or a focused layout module beside `ir_routes.py`, route
registration, `tests/test_ir_layout_routes.py`, schema-migration tests and WS-04/07 docs.

**Test-first acceptance.**

- Start with route/repository tests for empty read, save/reload, sparse replacement, stale-write
  conflict, invalid coordinates, unknown node/version and orphan cleanup.
- Add a migration upgrade test from revision `0004`, empty-database/model equivalence and
  idempotent application evidence.
- Save a position, reload both artefact and layout, resolve/render with the layout, and assert the
  graph content address, component versions, node cache identities and experiment binding are
  unchanged. Also assert the view's `placed` coordinate changed so the proof is not vacuous.
- Guard-failure proof: deliberately pass layout into the graph artefact or content-address input
  in a temporary mutation; the identity test must fail while the placement assertion still passes.
- Focused checks: layout route/repository, IR view/edit, migration equivalence and route-import
  closure. Regression: complete backend and research suites plus both deterministic smoke scripts.

**Rollback.** API and code revert cleanly. The additive table may remain unused; if downgrade is
required before release, the revision drops only the layout table. No existing money record is
rewritten.

### S1.2 — frontend layout load, drag and save

**Problem.** Backend persistence alone has no user workflow.

**User-visible outcome.** The viewer loads stored positions, supports keyboard and pointer moves,
shows unsaved/saving/saved/conflict/error states, and reloads exactly where the user left it.

**Boundary and likely files.** Extend `frontend/src/lib/api.ts` with closed layout transport
types; keep interaction logic in a focused graph-layout hook/module; keep semantic cards and the
connections table in `GraphView.tsx`. No executable graph mutation enters this slice.

**Acceptance.** Component-render tests cover initial layout, pointer and keyboard move, save,
reload, 409 conflict, retry and API failure. A layout-only before/after fixture has identical
graph identity fields. Full frontend tests, typecheck, build and 390px containment pass. A
suppressed save call must turn the reload test red. Rollback is a frontend/API revert; stored
layout rows remain valid.

### S2.1–S2.2 — minimum durable product objects

**Problem.** A fixed Python graph cannot support editing, immutable version history, research
binding or deployment approval.

**Outcome and boundary.** Accept a focused RFC amendment or architecture record defining Project,
Graph artefact, Graph version, Layout, Experiment, Finding, Deployment candidate and Deployment.
Project stays organisational; graph artefact is editable; graph version is immutable; layout is
mutable/non-executable; experiment binds immutable graph/code/data identity; finding interprets
evidence; candidate records approval; deployment holds runtime configuration and operational
state. Extend the existing `Deployment` entity rather than creating a second deployment model.

**Acceptance.** Closed persistence models and APIs enforce immutability, ownership, version
conflicts and legal state transitions. Existing databases migrate without rewriting the money
record. Model/migration equivalence, upgrade/downgrade, conflict/orphan and invalid-transition
tests pass. Mutation or direct SQL attempts that would rewrite an immutable graph version fail.

### S3.1–S3.3 — real visual authoring

**Problem.** The current surface inspects a graph but cannot produce one.

**Outcome and boundary.** Closed edit requests map one-to-one onto `app/ir/edit.py`; every accepted
edit creates a validated immutable graph version under optimistic concurrency. The UI offers typed
sockets, valid/invalid wire previews, component search, parameter editing, rename where legal,
grouping, undo/redo and accessible keyboard operation. `EditRejected` clauses and JSON paths reach
the user unchanged. No arbitrary Python execution or client-supplied version identity is accepted.

**Acceptance.** Every edit primitive has success, rejection and stale-version tests. Save/reload is
lossless. An entirely visual construction matches an equivalent hand-authored artefact's content
address; layout differences do not affect it; semantically identical operation orders do not create
false executable differences; illegal edits fail before persistence. Suppressing validation or
bypassing `app/ir/edit.py` must make an architecture guard fail.

## 4. Medium-term sequence

These slices become detailed plans only after S3.3 provides a stable authoring/version contract.

| Order | Slice | Product acceptance | Primary dependencies |
|---|---|---|---|
| M1 | Project → graph → experiment workflow | A user creates/opens a project and immutable graph version, selects versioned data and starts an experiment | S2.2, S3.3, WS-03 existing runner |
| M2 | Evidence and rejection surface | Net-of-cost results, qualification, walk-forward, DSR, PBO, N_eff, regimes, breadth, explanations and failures appear from the existing pipeline | M1, WS-03 gates/explain |
| M3 | Findings and approval | A finding records interpretation; approval/rejection records reason and immutable evidence; approval can create a deployment candidate | M2, product-object state machine |
| M4 | Reproducible operations | Nightly real-candle runs, data-quality reports, scheduler health, failures and sector seeding are visible and replayable | M1, WS-03/07 data contracts |
| M5 | Version and experiment comparison | Structural, parameter, component-version, data-identity and result diffs explain what changed and why confidence moved | M2, immutable versions |
| M6 | Daily review workflow | Timeline, notes, search, filters, queues, snapshots and fork/restore support a repeatable research day | M3, M5 |

Medium-term completion requires the full checkpoint in `docs/PROGRESS.md`: create/open, edit,
validate, version, experiment, inspect evidence, compare, approve/reject and create a deployment
candidate without leaving the product.

## 5. Later product sequence

### L1 — execution integration

Define StrategySpec and graph-version-to-candidate/deployment contracts, then add futures
accounting, venue support, protective-band parity, multi-timeframe lifecycle, reconciliation,
broker errors and deterministic order state through reversible local slices. Prepare parity,
replay, shadow, migration, rollback, health and observability evidence. Live IR-runtime adoption,
material futures/MTF behavior and any sizing/routing/risk change remain owner-gated at deployment.

### L2 — cockpit and operational review

Expose system health, strategies, deployments, graph versions, orders, positions,
reconciliations, risk controls, broker state, alerts, candidates, journals, approval queues,
deployment history and rollback state. Finish typography/palette when reference access exists;
physical-device checks improve evidence but do not block unrelated local work.

### L3 — first-class data layer

Make sources, instruments, venues, products, resolutions, calendars, sessions, corporate actions,
candle validation, missing-data policy, timestamp/feature/dataset identity, caches, lineage,
provenance, replay, live/historical boundaries, experiment binding and retention explicit. Data
identity must replace implicit path/timestamp/runtime-argument mixtures before ecosystem work.

### L4 — packaging and marketplace

Sequence security policy and threat model before format and transport: manifest, graph/component
dependencies, reproducibility, compatibility, signing, conformance, sandboxing, external-code
policy, install/publish/catalogue/version/deprecation/rollback, then licensing, entitlement,
review, moderation and audit. External packages receive no implicit broker, credential, capital,
filesystem, network or production-deployment authority. Legal/commercial policy and acceptance of
external-code risk are owner-gated when the concrete choice is reached.

### L5 — distribution and ecosystem

Only after core authoring, research, versioning and deployment workflows are coherent: additional
brokers, webhooks, external APIs, agent research interfaces, collaboration, sharing, import/export,
templates, onboarding, accounts, entitlements, billing, audit exports and enterprise controls.
Prioritise each by measured product value, dependency readiness and operational safety.

## 6. Integration, migration and deployment gates

- The feature branch is 92 commits ahead of local `main` at plan creation. Reducing that number is
  not itself an objective. After CI is green, group history into reviewable workstream milestones,
  measure `origin/main` divergence and decide whether repository policy calls for a staged
  integration branch or pull requests. Do not rebase, force-push or merge incidentally.
- Before every schema slice, capture current head, migration head, prior-schema fixture and restore
  path. Before a risky migration, push the preceding verified slice.
- Credential-dependent Kite/VPS checks never masquerade as CI. Record them as production
  verification, run through sanctioned tools and only after the relevant owner gate.
- Production deployments use `scripts/deploy.sh`, a measured `/api/health`, `/` SPA check, log and
  invariant inspection, and a recorded deployed commit. No Strategy OS slice in the current or
  near-term sequence authorises a live deployment.

## 7. Product-level checkpoints

| Checkpoint | Required evidence | Status |
|---|---|---|
| C0 Repository trust | Correct worktree, clean state, focused WS-04 tests, remote at expected commit | done |
| C1 Layout separation | Move/save/reload with identity-invariance and conflict/orphan proofs | pending S1 |
| C2 Durable authoring | Immutable versions, legal edits, undo/redo, lossless reload, hand-authored equivalence | pending S2–S3 |
| C3 Research decision | Versioned experiment, full evidence, comparison, approval/rejection, deployment candidate | pending M1–M5 |
| C4 Reversible execution | Parity, replay, shadow, rollback and observability complete locally | pending L1; deployment owner-gated |
| C5 Product operations | Cockpit and data identity support daily operation without prose reconstruction | pending L2–L3 |
| C6 Ecosystem safety | Reproducible signed packages and explicit trust/commercial controls | pending L4–L5 |

## 8. Deferred work and reasons

- Marketplace UI waits for package, signing, sandbox and external-code policy contracts.
- A second broker abstraction waits for a second concrete broker integration.
- Live IR adoption, material futures/MTF behavior and architecture migration deployment wait for
  owner approval at the production boundary, not for local engineering.
- WS-08 typography/palette waits for reference-site access or owner-supplied values; other cockpit
  and editor work continues.
- Pre-2026-08 research findings remain unsuitable as baselines because their provenance and gates
  cannot be repaired retrospectively; rerun any result that matters.
- Display-name/content-address semantics remain pinned by current tests until the first persistent
  artefact/rename workflow supplies evidence for an RFC amendment.

## 9. Per-slice completion record

For each completed slice, update its status and record in the owning workstream and
`docs/CONTINUE.md`:

1. focused red/green test evidence;
2. invalid and failure-path evidence;
3. non-vacuous guard proof;
4. applicable regression and deterministic smoke results;
5. migration/data inspection where relevant;
6. files and contracts changed;
7. commit and verified remote state;
8. deployment state and owner blockers;
9. exact next command for the next slice.
