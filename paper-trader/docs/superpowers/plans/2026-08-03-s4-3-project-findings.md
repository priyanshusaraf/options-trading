# S4.3 Project-owned Findings Implementation Plan

**Goal:** Let a user record, inspect and revise interpretations of verified graph-bound experiment
evidence without copying identity, recomputing evidence or rewriting history.

**Architecture:** Keep the existing `Finding` table. `evidence_run_id` is the canonical same-database
lineage to immutable ExperimentSpec provenance and verified terminal evidence. Closed project-owned
routes derive the binding server-side. Revision inserts a successor and compare-and-swaps the old
row's `superseded_by` in one transaction.

**Boundary:** Findings only. No new ledger/schema, experiment recomputation, candidate transition,
deployment state, execution, orders, Python input or live IR-runtime adoption.

## Task 1: Add verified project-owned finding reads

**Files:** `backend/app/core/research_read.py`, `backend/app/api/ir_experiment_routes.py`, focused tests.

1. [x] Add failing list/detail tests for automated and authored findings with exact run/spec/evidence/
   graph binding and active/superseded state.
2. [x] Hide cross-project ids and fail closed on corrupt or missing linked provenance/evidence.
3. [x] Guard reads with spies proving no provider, resolver, evaluator, gate or orchestrator runs.
4. [x] Mirror the closed contract under `/api/v1`.

## Task 2: Create findings from verified completed runs

1. [x] Add failing tests for bounded non-blank statement and positive/negative polarity.
2. [x] Reject client ids, hypothesis, confidence, graph/binding/evidence, timestamps and successor input.
3. [x] Require project-owned `completed` status plus verified terminal evidence; reject running, failed,
   corrupt, legacy-unbound and unknown runs exactly.
4. [x] Derive hypothesis, evidence confidence and binding on the server and commit one existing Finding.

## Task 3: Revise through an atomic immutable successor

1. [x] Add failing happy-path and reload tests proving the original semantic fields never change.
2. [x] Insert the successor against the same run/hypothesis and compare-and-swap
   `expected_superseded_by=null` in one transaction.
3. [x] Prove stale/terminal revision creates no orphan successor and cannot change evidence run/project.
4. [x] Inject failure after successor insertion and prove both writes roll back.

## Task 4: Add the accessible finding surface

1. Add typed finding list/create/revise transport that submits interpretation intent only.
2. Show automated/authored active and superseded history beside the selected run's evidence.
3. Add accessible statement/polarity creation and active-finding revision controls with exact
   server feedback and retained input on failure.
4. Prove lossless reload, narrow-screen containment and no client binding construction.

## Task 5: Verify, publish and continue

1. Run focused tests during implementation and WS-03/04/07/08 regression at the slice boundary.
2. Run the complete checkpoint only if implementation changes shared persistence/runtime/safety;
   otherwise rely on S4.2's immediately preceding full checkpoint plus focused workstream evidence.
3. Update coordination once, commit deliberately, push, verify exact remote and inspect Actions.
4. Generate the next bounded checklist from `EXECUTION_PLAN.md` and continue unless an owner-gated
   production boundary is reached.
