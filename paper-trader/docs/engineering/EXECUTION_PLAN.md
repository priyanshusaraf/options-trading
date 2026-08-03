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
- **Current slice:** S4.6b durable review notes and saved views
- **Next product checkpoint:** a user can retain project-owned review context and repeat a bounded
  review without weakening the server-derived timeline or current queues.

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
| S0.4 | Add fail-closed CI for deterministic backend, frontend and migration checks | S0.3 | done — published; dotenv boundary corrected at `4f8fb9a`, shutdown worker race at `b243b59` |
| S1.1 | Persist sparse layout records and expose closed layout read/write contracts | S0.4, F13, WS-07 migrations | done — verified, documented and published |
| S1.2 | Load, drag and conflict-safe save node positions in the React viewer | S1.1 | done — verified, documented and published |
| S2.1 | Accept the minimum product-object architecture and persistence contract | S1.1 evidence | done — ADR 0001 accepted |
| S2.2 | Persist projects, graph artefacts and immutable graph versions | S2.1 | done — verified locally; publication in this slice commit |
| S3.1 | Add a closed editing API over `app/ir/edit.py` with immutable version writes | S2.2 | done — verified locally; publication in this slice commit |
| S3.2a | Add graph rename and parameter override editing, validation feedback and local history | S3.1 | done — backend `7cc6525`, frontend `197c4e9` |
| S3.2b | Add structural node/edge/group editing and accessible connection controls | S3.2a | done — atomic semantic/presentation history published |
| S3.3 | Prove visual/hand-authored content-address equivalence and lossless reload | S3.2b | done — canonical equivalence and fresh-connection reload proved |
| S4.1 | Bind immutable graph versions to the existing research experiment flow | S3.3 | done — exact immutable provenance and closed start API verified |
| S4.2 | Surface evidence, rejection reasons, comparison and deployment-candidate decisions | S4.1 | done — verified and published |
| S4.3 | Add project-owned findings and immutable interpretation history | S4.2 | done — verified and published |
| S4.4 | Make bounded research operations and failures observable | S4.3 | done — verified in the safety checkpoint; publication in this slice commit |
| S4.5 | Compare immutable graph versions and their persisted experiment evidence | S4.4 | done — verified; publication in this slice commit |
| S4.6a | Add a daily research review read model and actionable queues | S4.5 | done — verified and published in this slice commit |
| S4.6b | Persist project review notes and saved filter views | S4.6a | active — bounded checklist generated |

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

**User-visible outcome.** A moved node position survives reload while the strategy's executable
identity remains byte-for-byte unchanged. Viewport state stays outside this slice.

**Architectural boundary.** WS-07 owns the SQLAlchemy model and Alembic revision. WS-04 owns a
small layout repository/service and HTTP contracts. WS-01's `Layout` and `graph_view()` remain
unchanged unless their existing export is demonstrably insufficient. The fixed graph catalogue
remains read-only; this slice stores presentation state only.

**Data contract.**

- Keep a layout head keyed by `(graph_identifier, graph_version)` with its update timestamp and
  monotonic revision. Store finite numeric `x` and `y` in sparse child rows keyed by
  `(graph_identifier, graph_version, instance_id)`. The parent is necessary because an empty
  layout still needs a revision for optimistic concurrency.
- Store only moved authored instance IDs. A missing row means derived placement.
- `GET` returns the current sparse layout plus revision. `PUT` replaces the sparse layout under
  an expected revision; stale revisions return 409 and never partially write.
- Reject unknown graph identifiers/versions, unknown or derived-only instance IDs, duplicate IDs,
  non-finite coordinates and extra request fields.
- Orphan policy: reads filter rows that no longer match an authored instance; a successful write
  deletes those rows transactionally. Graph-version creation later performs eager cleanup. This
  keeps an old layout harmless without coupling layout persistence to graph mutation that does
  not exist yet.

**Implemented files.** `backend/app/db/models.py`, Alembic revision `0005`,
`backend/app/editor/layouts.py`, `backend/app/api/ir_layout_routes.py`, the fixed
`backend/app/ir/catalogue.py`, route registration, `tests/test_ir_layout_routes.py`,
schema-migration tests and WS-04/07 docs.

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
required before release, revision `0005` drops the position table and then the layout-head table.
The downgrade/upgrade test proves the trades table remains present. No existing money record is
rewritten.

**Implementation evidence, 2026-08-03.** The closed GET/PUT contract, sparse replacement,
revision conflict, validation, orphan filtering/cleanup, `/api/v1` mirror and graph/component/
cache/experiment identity proof pass. A mutation that inserted layout into the graph hash input
failed the identity proof on the expected mismatch. Model/migration equivalence and the
`0005 → 0004 → 0005` rollback path pass. The complete backend and research run is 2,719 passed
and 6 skipped; both deterministic smoke scripts pass.

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

**Next bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Add typed layout GET/PUT transport and an explicit conflict/error taxonomy.
2. [x] Load sparse coordinates beside the immutable graph and prove identity fields do not move.
3. [x] Add pointer and keyboard movement for authored nodes with a visible dirty state.
4. [x] Save against `base_revision`; retain local work on conflict/error and support retry/reload.
5. [x] Run component, accessibility, 390px, full frontend and applicable backend regressions;
   update handoff evidence, commit and push.

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

**S2.1 decision evidence, 2026-08-03.**
[ADR 0001](decisions/0001-product-object-contract.md) rejects Project/watchlist execution roots,
mutable versions, presentation-inside-IR, duplicate research ledgers, auto-active promotion and a
generic JSON object store. It accepts the existing research records and `Deployment` root, defines
all eight product identities/lifecycles, and fixes the S2.2 migration and rollback boundary.

**S2.2 bounded checklist.**

1. [x] Add Project, graph artefact and immutable graph-version model/migration tests.
2. [x] Seed the fixed catalogue graph and attach existing layouts without touching money records.
3. [x] Implement draft revision and atomic publish repositories with direct-SQL immutability proof.
4. [x] Add closed Project/graph draft/version APIs and invalid ownership/conflict paths.
5. [x] Run persistence/workstream regressions, migration rollback, docs, bounded commit and push.

**S2.2 completion evidence, 2026-08-03.** Revision `0006` seeds the fixed graph, gives layouts a
real graph-version owner and quarantines pre-existing orphans for reversible downgrade. SQLite
checks row/JSON identity and refuses graph-version UPDATE/DELETE. Repository tests prove stale
draft rejection and rollback after a flushed version insert. The HTTP surface creates projects and
initial drafts, publishes by base revision and reads immutable versions; it deliberately exposes
no raw draft-replacement route. The IR/persistence workstream regression and full backend/frontend
acceptance checkpoint pass. No execution or research path reads the new records.

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

**S3.1 bounded checklist.**

1. [x] Inventory the existing `app/ir/edit.py` primitives and define one closed request union.
2. [x] Apply each request to the owned draft through `app/ir/edit.py`, never by raw replacement.
3. [x] Validate and atomically publish the resulting server-versioned graph under `base_revision`.
4. [x] Return exact rejection clauses/paths and cover stale, ownership and arbitrary-input failures.
5. [x] Prove the no-bypass guard, run backend editor regressions, document, commit and push.

**S3.1 completion evidence, 2026-08-03.** The closed request union covers all eight existing edit
primitives. A bounded batch keeps intermediate add/connect states out of persistence and publishes
one fully validated, resolved graph version. The route accepts no graph/version source fields,
returns exact F7/F9/C5 clause and path data, and hides cross-project artefacts. AST and runtime
guards require `app.ir.edit` plus the single atomic repository method. Injected failure after the
version insert rolls back the draft, revision and current-version pointer. Editor/IR regression and
full backend/frontend acceptance pass; execution still reads none of these records.

**S3.2a bounded checklist.**

1. [x] Add a typed frontend edit-batch transport and exact 409/422 error decoding.
2. [x] Add accessible graph-name and node-override controls backed by the server revision.
3. [x] Use backend-issued canonical receipts for deterministic undo/redo requests.
4. [x] Retain local intent on conflict/failure and present exact clause/path feedback.
5. [x] Run focused and workstream regressions, full checkpoint acceptance, document, commit and push.

**S3.2a completion evidence, 2026-08-03.** The backend exposes one coherent editor document and
accepts only rename and set/clear override operations for this slice. It validates and constructs
the resolved view, editable authored-node descriptors, canonical inverse receipt and sparse layout
before committing one immutable version. Failure injection after version insertion, layout
preparation and response construction proves full rollback. The React editor replaces accepted
state only from that document, preserves dirty layout coordinates across graph rekeying, retains
failed command intent, ignores stale responses and submits undo/redo from server receipts. Focused
editor, layout, migration and workstream regressions pass. The shared-persistence checkpoint passed
2,774 backend tests with 6 skips, all 189 frontend tests, typecheck, production build and both
deterministic smoke scripts. No execution path changed and nothing was deployed.

**S3.2b bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Add typed structural batches for add/remove node, connect/disconnect and group.
2. [x] Add accessible component selection, node create/remove and group membership controls.
3. [x] Add accessible socket selection and connect/disconnect controls.
4. [x] Extend canonical inverse receipts and define changed-node sparse-layout reconciliation.
5. [x] Prove exact failure retention, run applicable regressions, document, commit and push.

**S3.2b completion evidence, 2026-08-03.** Semantic add/remove/connect/disconnect batches validate
only their final graph through `app.ir.edit.apply_batch()` and publish one immutable version.
Visual groups are separately revisioned presentation state and never enter graph, component,
cache, experiment or runtime identity. One transaction inserts the semantic version, reconciles
positions and group memberships, advances both heads when required and constructs the coherent
response. Exact receipts replay semantic and presentation forward/inverse batches for lossless
undo and redo. Server-derived component, graph-boundary and authored-socket descriptors drive the
accessible React controls. Seven negative guards proved content-address isolation, final-state
validation, transaction atomicity, orphan pruning, two-sided undo, executable-identity uniqueness
and the `app.ir.edit` boundary. Acceptance passed 2,794 backend tests with 6 skips, all 195
frontend tests, typecheck, production build and both deterministic smoke scripts.

**S3.3 bounded checklist, generated from this plan on 2026-08-03.**

1. [ ] Define one hand-authored reference graph and an equivalent closed editor command history.
2. [ ] Prove the editor-produced canonical graph has the same executable content address at the
       same server-issued version, with presentation state excluded from both inputs.
3. [ ] Prove service/database reload preserves authored graph bytes, descriptors, positions,
       groups, revisions and deterministic undo/redo inputs without client reconstruction.
4. [ ] Add explicit mismatch diagnostics for semantic, ordering and presentation-contamination
       failures while keeping raw graph replacement and client-selected versions forbidden.
5. [x] Run the S3.3 focused and WS-04 regressions, update the three coordination documents,
       commit deliberately, push, inspect Actions and continue into the next unblocked slice.

**S3.3 completion evidence, 2026-08-03.** One independently constructed hand-authored reference
and one closed add/connect/disconnect/remove history produce byte-identical canonical executable
JSON and the same content address at the same server-issued version. Positions and visual groups
are present before publication, reconcile when their node is removed and remain absent from the
identity oracle. Disposing database connections and reloading preserves graph bytes, descriptors,
positions, groups and revisions; the persisted receipt then restores semantic and presentation
state without client reconstruction. Deterministic diagnostics distinguish semantic content,
node order, edge order, presentation contamination and executable identity. The focused proof and
187-test WS-04 regression pass; no shared persistence schema or runtime path changed, so the full
checkpoint was not repeated after S3.2b's immediately preceding green checkpoint.

**S4.1 bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Reconcile immutable graph identity, project ownership and the existing research experiment
       contract; write the S4.1 design record and test-first implementation plan.
2. [x] Define the minimum persisted binding from experiment to graph identifier, version, content
       address, versioned dataset identity and explicit cost assumptions without duplicating the
       research ledger or gate pipeline.
3. [x] Add a closed project-owned API that starts the existing experiment flow from a published
       immutable graph version and rejects drafts, archived owners, unknown versions and raw graph
       payloads with exact feedback.
4. [x] Prove persisted resolution, data, cost and statistical-gate evidence remains reproducible
       across reload and cannot silently follow a newer graph version.
5. [x] Run focused WS-03/WS-04/WS-07 regressions, update the three coordination documents, commit,
       push, inspect Actions and continue; do not adopt the IR runtime in live execution.

**S4.1 completion evidence, 2026-08-03.**
[ADR 0002](decisions/0002-graph-version-research-binding.md) accepts copied immutable provenance
across the application/research database boundary and rejects duplicate ledgers, cross-database
foreign keys, mutable-head binding, raw graph input and a second gate pipeline. The closed
project-owned start route persists canonical graph, resolution, dataset, cost, gate, hypothesis
and build provenance in the existing immutable `ExperimentSpec`; reload and newer-head tests prove
the selected version cannot move. Three deliberate mutations made the content-address, closed-body
and resolution-evidence guards fail. The full checkpoint passed: 2,813 backend/research tests plus
6 skips, dry-run `LEDGER OK`, 16/16 backtest smoke `SWEEP OK`, 195 frontend tests, typecheck and
production build. Live execution and IR runtime adoption remain untouched.

**S4.2 bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Reconcile the existing ExperimentSpec/Run, Finding, PromotionCandidate and shadow-state
       contracts with S4.2; write the evidence/decision design record and test-first plan.
2. [x] Add closed project-owned read APIs for experiment summary and detail that expose persisted
       qualification failures, walk-forward gates, DSR/PBO/N_eff, regimes, breadth, explanation,
       graph/data/cost provenance and terminal errors without recomputing evidence.
3. [x] Add deterministic comparison over two immutable experiment specs/runs: graph structure and
       parameters, component versions, dataset identity, costs, gates and result deltas, with
       explicit incomparable reasons instead of inferred equivalence.
4. [x] Surface the evidence and exact rejection reasons accessibly in the product, and reconcile
       candidate creation/decision with the existing shadow and human-approval state machine; no
       approval may activate a deployment or bypass shadow evidence.
5. [x] Prove reload, ownership, legacy-unbound, pending/terminal decision, raw-evidence and stale
       revision guards; run focused then workstream regression, update handoff once, commit/push,
       inspect exact-head CI and continue without adopting the IR runtime in live execution.

**S4.2 completion evidence, 2026-08-03.** ADR 0003 accepts canonical content-addressed terminal
evidence in the existing run checkpoint and canonical candidate decisions appended to the existing
server scorecard. Completed and controlled-failed runs persist exact provenance and structured
outcomes; running, failed, completed, corrupt and legacy-unbound states remain distinct. Closed
project-owned list/detail/comparison/decision routes never recompute evidence, reject raw evidence
or scorecards, and use pending-only compare-and-swap decisions with a bounded reason. The product
surface shows exact failures, gates, DSR/PBO/N_eff, provenance, comparison and accessible decisions.
The older combined approval/deployment write is closed; its preview remains read-only. The full
checkpoint passed 2,856 tests plus 6 skips, all 202 frontend tests, typecheck, production build,
`LEDGER OK` and 16/16 `SWEEP OK`. Execution, orders, arming and live IR adoption remain untouched.

**S4.3 bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Reconcile the existing `Finding` lifecycle with graph-owned runs, terminal evidence and ADR
       0001; record a narrow test-first design without creating a parallel knowledge ledger.
2. [x] Add closed project-owned finding reads and creation from a verified terminal run; accept
       interpretation intent only and derive all run/graph/evidence identity on the server.
3. [x] Implement revision by immutable successor plus `superseded_by`, preserving the original
       finding and rejecting cross-project, legacy, running, corrupt and stale revision requests.
4. [x] Surface active and superseded finding history accessibly beside experiment and candidate
       evidence, with lossless reload and no evidence recomputation or client identity claims.
5. [x] Run focused and WS-03/04/07/08 regressions, update coordination once, commit/push, inspect
       exact-head CI and continue; do not create or activate a deployment or adopt the IR runtime.

**S4.3 completion evidence, 2026-08-03.** ADR 0004 retains the existing Finding ledger and treats
`evidence_run_id` as the canonical same-database lineage to immutable spec provenance and verified
terminal evidence. Closed project-owned routes list, load and create interpretations from completed
verified runs only. Revision inserts a successor and compare-and-swaps `superseded_by` in one
transaction; stale and injected post-insert failures create no orphan and never rewrite the original
semantic fields or evidence run. Reads are provider/resolver/evaluator/gate-free. The product shows
automated and authored active/superseded history, exact evidence address and accessible create/
revision controls with retained intent on conflict. The 570-test WS-03/API regression completed with
6 skips; all 204 frontend tests, typecheck and build pass. No schema/runtime/safety boundary changed,
so S4.2's immediately preceding full checkpoint remains the major-checkpoint baseline.

**S4.4 bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Reconcile `run_nightly`, research CLI/plans, provider collection, run failure evidence and
       current operational entry points; record a narrow design before changing behavior.
2. [x] Define one bounded server-owned operation receipt for scheduled/manual research attempts,
       including plan identity, build, provider mode, start/end state and safe failure summary,
       without duplicating ExperimentRun or accepting arbitrary executable plans.
3. [x] Add closed read/status APIs and deterministic mock-run coverage; expose collection/data-
       quality and terminal pipeline failures without credentials, tracebacks or provider payloads.
4. [x] Surface last/active operation, per-experiment progress and exact safe failure feedback
       accessibly; keep execution, deployment, arming and orders outside the surface.
5. [x] Prove restart/reload, concurrent-attempt, stale-status, raw-plan and research/execution
       isolation guards; run applicable regressions, publish, inspect CI and continue.

**S4.4 completion evidence, 2026-08-03.** ADR 0005 adds one canonical, content-addressed,
mode-0600 current/last receipt beside `research.db` and one real non-blocking OS lock shared by
nightly and manual entry points. Isolation and the disabled-plane gate run before receipt writes.
Only bounded server-owned plan summaries, stable stage failures and committed ExperimentRun ids
persist; tracebacks, credentials, provider payloads and HTTP plan/control input remain excluded.
The closed read-only status route and `/api/v1` mirror verify the receipt without invoking research,
and the cockpit contains corrupt status separately from experiment history. Overlap, stale-owner,
atomic reload, overflow, corruption, freeze and isolation guards pass. The safety checkpoint passed
2,883 backend/research tests plus 6 skips, all 208 frontend tests, typecheck, production build,
`LEDGER OK` and 16/16 `SWEEP OK`.

**S4.5 bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Reconcile the existing run-evidence comparator, immutable graph-version store, Component IR
       identity rules and presentation-state exclusion; record the missing comparison contract.
2. [x] Define one pure server-derived comparison document for two project-owned immutable graph
       versions and optional persisted runs, separating structure, parameters, component versions,
       data identity, gates/costs and results without accepting graph/evidence identity from clients.
3. [x] Add closed read/compare APIs and guard wrong-project, missing, corrupt, legacy and
       incomparable inputs; reads must not resolve, execute, collect, evaluate or mutate state.
4. [x] Surface accessible version/run selection and exact difference categories with lossless reload,
       explicit incomparable reasons and no presentation contamination or execution controls.
5. [x] Prove canonical ordering, same-version equivalence, presentation-only invariance and
       client-identity rejection; run applicable regressions, publish, inspect CI and continue.

**S4.5 completion evidence, 2026-08-03.** ADR 0006 retains the accepted verified-evidence
comparator and adds a pure immutable-IR comparator over server-loaded graph documents. Authored
nodes and edges compare by stable identity/endpoints; component refs, parameters, interface,
metadata and exact document/order identity remain separate categories. Content-address mismatch
and executable `groups` contamination fail closed. A closed version-list read and combined
comparison verify project ownership, canonical graph bytes and optional paired run bindings against
both recipe and signed evidence provenance. Reads call no resolver, provider, orchestrator or
presentation store. The product offers accessible left/right versions and optional run evidence,
with exact incomparable reasons and no execution controls. The 141-test WS-03/04/API regression and
all 209 frontend tests, typecheck and build pass. No schema/runtime/safety boundary changed after
S4.4's immediately preceding full checkpoint and fully green Actions run `30819757907`.

**S4.6a bounded checklist, generated from this plan on 2026-08-03.**

1. [x] Reconcile projects, bounded operation receipts, graph-bound runs, findings, candidate
       decisions and immutable version events; define which existing ledger owns each timeline fact.
2. [x] Record a closed project-owned daily-review read model with deterministic event identity,
       ordering, cursor pagination, bounded date/type/status filters and actionable queue semantics.
3. [x] Add one read-only aggregation API that derives events and queues from existing stores without
       copying evidence, accepting client state, recomputing research or mutating acknowledgements.
4. [x] Surface an accessible timeline plus failed-operation, review-needed, pending-decision and
       active-finding queues with exact links back to existing evidence/version views.
5. [x] Prove stable pagination, cross-project isolation, corrupt-source containment, no provider/
       resolver/evaluator calls and narrow-screen behavior; verify, publish, inspect CI and continue.

**S4.6a completion evidence, 2026-08-03.** ADR 0007 assigns only lineage-proven facts to the
project timeline and keeps the canonical current/last operation receipt in a separately labeled
global lane. The read model verifies immutable graph bytes, run/finding/candidate provenance and
candidate decision addresses; derives current queues in one research session; and contains corrupt
rows without copying raw evidence, scorecards or finding statements. Project events use closed UTC
identities, deterministic descending ordering, a content-addressed opaque cursor and bounded
type/status/date filters. The read-only `/api/ir/projects/{project_id}/review` route and `/api/v1`
mirror reject unknown fields and never call resolution, data collection, research orchestration or
write seams. The accessible product surface renders four queues, project events, exact run/version
navigation, filters, polling and stable older-page continuation with narrow-screen containment.
The final focused set passed 13 backend and 17 frontend tests; the combined WS-03/04/API regression
passed 104 tests and all 212 frontend tests, typecheck and build pass. No schema, migration,
execution or shared-runtime boundary changed, so S4.4's 2,883-pass checkpoint remains current.

**S4.6b bounded checklist, generated from this plan on 2026-08-03.**

1. [ ] Reconcile event identity, project ownership, authenticated principal semantics, retention and
       event disappearance before allowing review notes or saved views to persist.
2. [ ] Record a closed contract that keeps notes and saved filters non-executable, separately
       revisioned and unable to acknowledge, hide or mutate authoritative queues.
3. [ ] Add reversible persistence plus optimistic APIs for bounded project notes and named saved
       filter views; prove cross-project isolation, stale-write rejection and migration equivalence.
4. [ ] Add accessible create/edit/delete note and save/apply/delete view workflows while preserving
       exact server validation feedback and lossless reload.
5. [ ] Prove annotations cannot change graph/evidence/cache/experiment identity or source events;
       run the schema checkpoint, publish, inspect exact-head CI and continue to bounded search.

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
