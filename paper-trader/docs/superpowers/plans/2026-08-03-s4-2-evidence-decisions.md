# S4.2 Evidence, Comparison and Candidate Decision Implementation Plan

**Goal:** Persist and surface the exact evidence behind graph-bound research runs, compare two runs
without false equivalence, and enforce the existing shadow-to-human candidate gate on every path.

**Architecture:** The existing orchestrator writes a canonical, content-addressed terminal
evidence envelope to `ExperimentRun.checkpoint_json`. Closed project-owned read routes verify and
return that persisted evidence. A pure comparator diffs verified immutable recipes/evidence. The
existing PromotionCandidate state machine receives pending-only compare-and-swap decisions; no new
ledger or execution behavior is introduced.

**Boundary:** Evidence/read/decision only. No graph execution on reads, raw evidence input,
deployment activation, arming, orders, Python or live IR-runtime adoption.

## Task 1: Close the shadow direct-id bypass

**Files:**

- Modify: `backend/app/core/research_read.py`
- Modify: `backend/app/api/portfolio_routes.py`
- Modify: `backend/tests/test_portfolio_promotions.py`
- Extend: `backend/research_tests/test_shadow.py`

1. [x] Add failing tests proving direct lookup, dry-run deploy and committed deploy cannot see or
   approve `shadow`, `approved` or `rejected` candidates.
2. [x] Require `pending` in both `get_promotion` and the compare-and-swap approval write.
3. [x] Prove a stale status change between lookup and approval cannot stage or approve a candidate.
4. [x] Run focused portfolio/shadow tests, including `/api/v1` mirroring.

## Task 2: Persist canonical terminal evidence

**Files:**

- Create: `backend/research/evidence.py`
- Modify: `backend/research/orchestrator/run.py`
- Modify: `backend/research_tests/test_orchestrator.py`
- Create: `backend/research_tests/test_evidence.py`

1. [x] Add failing tests for canonical envelope construction, content-address verification, corruption,
   legacy missing evidence and JSON bounds.
2. [x] Extend the orchestrator's per-instrument record so qualification failures and validation
   failures retain exact structured values, not only prose.
3. [x] Persist success evidence, regimes, breadth and exact explanation before the terminal commit.
4. Persist a bounded failed-run envelope and `status=failed` for controlled pipeline failures.
5. Prove a failure while writing evidence cannot leave a completed run without verified evidence.

## Task 3: Add closed project-owned evidence reads

**Files:**

- Extend: `backend/app/api/ir_experiment_routes.py`
- Create or extend: `backend/app/core/research_read.py`
- Extend: `backend/tests/test_ir_experiment_routes.py`

1. Add failing list/detail tests for completed, failed, running and legacy-unbound graph runs.
2. [x] Verify project ownership from immutable graph provenance and hide cross-project run ids.
3. [x] Return persisted evidence only; guard with spies proving no provider, resolver, evaluator or gate
   is called during reads.
4. [x] Add exact malformed/corrupt-evidence feedback and `/api/v1` parity.

## Task 4: Implement deterministic comparison

**Files:**

- Create: `backend/research/compare.py`
- Create: `backend/research_tests/test_compare.py`
- Extend: `backend/app/api/ir_experiment_routes.py`
- Extend: `backend/tests/test_ir_experiment_routes.py`

1. Add table-driven failing tests for graph, component/node, dataset, cost, gate, build and result
   differences plus exact equality.
2. Mark changed dataset/cost/gate dimensions incomparable rather than emitting misleading
   performance deltas.
3. Expose one closed project-owned comparison route over two verified persisted runs.
4. Reject legacy, corrupt, running, cross-project and client-supplied evidence.

## Task 5: Add explicit candidate decisions and the product evidence surface

**Files:**

- Modify: `backend/app/core/research_read.py`
- Extend: `backend/app/api/ir_experiment_routes.py`
- Modify: relevant frontend API/state/view files and focused tests

1. Add a pending-only decision request with expected status and bounded reason; reject stale,
   shadow and terminal candidates without mutating scorecards.
2. Persist canonical decision evidence while preserving the original server scorecard.
3. Surface run evidence, exact rejection reasons, comparison and candidate state accessibly; keep
   all final topology/evidence/state authority on the server.
4. Prove approval records research intent only and creates no active/armed deployment or order.

## Task 6: Regression, publication and continuation

1. Run focused tests during each task and WS-03/04/07/08 regression at the slice boundary.
2. Run the full checkpoint because terminal research persistence and the candidate safety boundary
   changed.
3. Update the three coordination documents once with final evidence, commit deliberately, push,
   verify remote exact head and inspect GitHub Actions.
4. Generate the next bounded checklist from `EXECUTION_PLAN.md` and continue unless an owner-gated
   live-runtime boundary is reached.
