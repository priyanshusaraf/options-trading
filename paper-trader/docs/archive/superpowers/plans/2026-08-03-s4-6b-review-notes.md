# S4.6b Review Notes and Saved Views Implementation Plan

**Goal:** Persist bounded project review context and reusable filters without changing source facts,
queues or executable identity.

**Architecture:** Add two application-DB product tables behind one repository and closed project
routes. Note anchors are verified against the derived S4.6a event set at creation; later reads mark
missing anchors without copying source summaries. Saved views persist only validated filter fields.

**Boundary:** Event-linked notes and named saved filters. No search, acknowledgement, queue hiding,
snapshot, fork/restore, research execution or deployment control.

## Task 1: Pin persistence and migration behavior

1. Start with model/migration tests for exact table shape, restrictive project ownership and head
   revision `0008`.
2. Prove empty `0008 → 0007 → 0008`, populated downgrade refusal and money/graph/layout retention.
3. Add note and saved-view records with server ids, normalized owner actor, revision, timestamps and
   tombstones; add a partial unique active-view name index.
4. Re-run fresh/model versus migrated-schema equivalence.

## Task 2: Implement the optimistic repository test-first

1. Test create/list/update/delete and lossless fresh-session reload for both object types.
2. Test stale update/delete, wrong project, archived-project writes and active-name conflict with no
   partial mutation.
3. Test immutable note anchors, canonical saved filters, tombstone exclusion and id non-reuse.
4. Test missing-anchor projection independently from mutable source summaries.

## Task 3: Add closed principal-aware APIs

1. Add closed note and saved-view CRUD routes plus `/api/v1` mirrors.
2. Require the existing owner principal seam for writes and normalize both owner modes to one
   durable actor.
3. Derive note event type server-side from the current project event set; reject invented,
   wrong-project and global-operation ids.
4. Reject unknown fields, cursors, invalid filters and stale revisions with stable feedback.

## Task 4: Add accessible workflows

1. Load notes and views beside the daily review without inserting them into event counts/cursors.
2. Add event note create/edit/delete controls with retained draft on validation/conflict failure.
3. Add saved-view create/apply/delete controls that call the existing review endpoint only.
4. Show missing anchors explicitly and preserve narrow-screen containment and lossless reload.

## Task 5: Verify, publish and continue

1. Prove identity invariance, queue non-interference and no IR/research/execution write calls.
2. Run focused tests, WS-04/07/08 regression and the schema/shared-persistence full checkpoint.
3. Update coordination once, commit deliberately, push, verify remote and inspect exact-head CI.
4. Generate the next bounded checklist for review search without starting snapshots or fork/restore.
