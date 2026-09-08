# S4.6a Daily Research Review Read Model Implementation Plan

**Goal:** Derive one trustworthy project timeline and actionable queues from existing ledgers while
keeping global operation status explicitly unowned by any project.

**Architecture:** Build a pure normalization/pagination layer over one read from the application
graph store, one research DB session and the verified operation receipt. Persist nothing new.

**Boundary:** Read-only timeline, filters, cursor and queues. No notes/search/saved views,
acknowledgements, snapshots, fork/restore, scheduler or execution controls.

## Task 1: Define and test deterministic event/cursor primitives

1. Add closed event and reference shapes with bounded summaries and UTC timestamps.
2. Add canonical ordering and a content-addressed opaque cursor over the final sort key.
3. Prove stable continuation after insertion above the cursor and reject tamper/overflow.
4. Add bounded date/type/status filter validation and deterministic application order.

## Task 2: Derive project events in source-owned reads

1. Add a project-owned immutable graph-version identity/timestamp read.
2. In one research session derive graph-bound runs, findings, candidate creation and decision events.
3. Preserve separate candidate creation/decision and finding successor identities.
4. Contain corrupt rows as bounded source errors while retaining unrelated valid events.

## Task 3: Add global operations and current queues

1. Load verified current/last operation status as a separately labeled global lane.
2. Never include operation state in project event counts, filters, cursors or ownership claims.
3. Derive review-needed runs, pending candidates, active findings and failed-operation queues without
   copying raw evidence or scorecards.
4. Contain corrupt/missing operation state without hiding the project response.

## Task 4: Add the closed API and accessible surface

1. Add one read-only project review route plus `/api/v1` mirror under the research gate.
2. Reject unknown query fields, invalid cursors and cross-project claims with stable feedback.
3. Render global operation status, queue counts/items, filters and paginated project events with
   exact links to existing version/evidence/finding/candidate views.
4. Preserve narrow-screen containment and add no mutation or scheduler/execution controls.

## Task 5: Verify, publish and continue

1. Run focused primitive/source/API/UI tests and WS-03/04/08 regression at closure.
2. Run a full checkpoint only if implementation changes schema, shared persistence/runtime or safety.
3. Update coordination once, commit deliberately, push, verify remote, inspect exact-head CI and
   continue into the next unblocked M6 slice.
