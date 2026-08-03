# S4.5 Immutable Version and Evidence Comparison Implementation Plan

**Goal:** Let a user compare two project-owned immutable Component IR versions and, when selected,
their verified persisted experiment evidence without recomputation or presentation contamination.

**Architecture:** Add one pure raw-IR comparator beside the graph store and compose it at the API
edge with the accepted S4.2 evidence comparator. The server loads and verifies all identities.
Layouts and visual groups are never loaded.

**Boundary:** Version listing, closed comparison, and an accessible read-only surface. No schema,
resolver/runtime execution, collection, experiment start, merge/restore, deployment or orders.

## Task 1: Build the pure immutable graph comparator

1. [x] Add failing tests for exact equality and deterministic response order.
2. [x] Index authored nodes by instance id and edges by canonical endpoint; report add/remove topology.
3. [x] Separate component-ref, override, interface, metadata and exact identity/order differences.
4. [x] Reject presentation contamination and invalid declared content address rather than normalizing it.

## Task 2: Add server-owned version reads and comparison

1. [x] Add a closed version-list read returning version and content address under project ownership.
2. [x] Add a closed comparison request with two identifier/version selectors and paired optional run ids.
3. [x] Load and verify immutable graph rows, hide wrong-project selections and reject all raw identity,
   graph, evidence, result and presentation claims.
4. [x] When runs are selected, require verified terminal evidence and exact graph-binding agreement,
   then compose the existing evidence comparator without recomputation.

## Task 3: Prove failure and read-only boundaries

1. [x] Cover missing, cross-project, corrupt-address, contaminated, running, legacy and corrupt evidence.
2. [x] Prove one-sided run selection and run/version mismatch fail closed.
3. [x] Spy resolver, provider, orchestrator, evaluator and write seams; none may run during comparison.
4. [x] Retain the existing run-only comparison response and `/api/v1` mirrors unchanged.

## Task 4: Add the accessible comparison surface

1. [x] Add typed version-list and combined comparison transports.
2. [x] Provide accessible left/right immutable version and optional run selection beside research history.
3. [x] Render exact structural/component/parameter/data/gate/result categories and incomparable reasons.
4. [x] Preserve narrow-screen containment, reload selection from server-owned lists and expose no
   execution, publish, merge, restore, deployment or order controls.

## Task 5: Verify, publish and continue

1. [x] Run focused comparator/API/UI tests during implementation and WS-03/04/08 regressions at closure.
2. [x] Use the S4.4 full safety checkpoint unless S4.5 changes shared persistence/runtime/safety.
3. [x] Update coordination once, commit deliberately, push, verify remote, inspect exact-head CI and
   continue into the next unblocked slice.
