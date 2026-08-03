# S4.4 Research Operations Observability Implementation Plan

**Goal:** Make bounded nightly/manual research attempts, progress and safe failure state durable and
visible without turning the product into a remote arbitrary-work controller.

**Architecture:** A canonical content-addressed mode-0600 JSON document stores one active and one
last operation beside research.db. An OS file lock serializes processes. ExperimentRun remains the
only experiment evidence ledger; operation receipts reference its run ids.

**Boundary:** Read-only operations status plus entry-point instrumentation. No SQL schema, remote
start/cancel/retry, raw plan, credentials, execution, deployment, arming, orders or IR adoption.

## Task 1: Build and verify the receipt store

1. [x] Add failing tests for canonical envelope/address validation, closed schema, bounds, atomic mode,
   missing state and corruption.
2. [x] Add a real non-blocking process lock and prove overlap refusal leaves active state unchanged.
3. [x] Reconcile stale `active=running` only while holding the lock; preserve it as interrupted `last`.
4. [x] Persist closed stage transitions, safe failure and completed run ids through atomic replace.

## Task 2: Instrument bounded entry points

1. [x] Refactor nightly into a testable operation body without weakening isolation/freeze ordering.
2. [x] Derive canonical safe plan summaries and provider mode from server-owned objects only.
3. [x] Add optional `run_nightly` progress reporting after each committed run and record generation ids.
4. [x] Instrument `research.nightly` and `scripts/research_run.py` with the shared lock/receipt contract.
5. [x] Prove zero-plan success, collection/pipeline/generation failure, interruption and exact mock
   success/reload; never persist traceback, exception secrets or provider payloads.

## Task 3: Add closed status reads

1. [x] Add read-only `/api/research/operations/status` and `/api/v1` mirror under the research gate.
2. [x] Return verified active/last state or explicit never-run state; corrupt state returns stable 409.
3. [x] Guard with spies proving no provider, planner, orchestrator, evaluator, gate or execution call.
4. [x] Prove no POST/PUT/DELETE/raw-plan operation route exists.

## Task 4: Add the accessible operations surface

1. [x] Add typed read-only transport and exact corrupt/unavailable feedback.
2. [x] Show active/last stage, trigger, build/provider mode, plan identity/summary, linked run ids and
   safe failure message beside research history.
3. [x] Cover never-run, active, success, failure, corrupt and narrow-screen states accessibly.
4. [x] Keep all run controls absent and link completed ids to the existing evidence surface.

## Task 5: Verify, publish and continue

1. [x] Run focused tests during implementation and WS-03/07/08 regression at the boundary.
2. [x] Run the full checkpoint if entry-point or isolation changes affect shared safety/runtime; otherwise
   use the immediately preceding full checkpoint plus workstream and subprocess guards.
3. [x] Update coordination once, commit/push, verify remote, inspect exact-head Actions and continue.
