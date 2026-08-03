# S4.6d Immutable Project Review Snapshots Implementation Plan

**Goal:** Preserve a bounded historical daily review without claiming cross-store atomic time or
creating a restore path.

**Architecture:** Add one append-only application table for canonical server-derived manifests.
Capture performs two matching source reads around one application transaction that reads active
notes and inserts the snapshot. Source errors and changes fail closed. The UI keeps historical and
current queues visibly separate.

**Boundary:** Capture, list and open only. No update/delete, comparison, export, restore, fork,
acknowledgement, raw artefact storage, research execution or deployment behavior.

## Task 1: Pin canonical snapshot content test-first

1. Test the exact closed manifest fields, canonical event/note ordering and queue bounds.
2. Test graph-reference provenance while rejecting raw graph, evidence, scorecard, decision-reason,
   global-operation, saved-view and search fields.
3. Test identical content addresses for canonical-equivalent input and address changes for every
   allowed semantic content field.
4. Test missing-anchor notes remain explicit and source errors refuse manifest creation.

## Task 2: Add reversible append-only persistence

1. Write migration `0009` and model tests for restrictive project ownership, immutable manifest,
   unique project/capture key and required capture window.
2. Prove fresh/migrated schema equivalence, `0009 → 0008 → 0009` when empty, populated downgrade
   refusal and money/graph/layout/review-state retention.
3. Add repository capture/list/read with active-project capture and archived-project reads.
4. Prove idempotent capture-key retry, conflicting reuse, cross-project isolation, direct-update
   refusal and lossless fresh-session reload.

## Task 3: Implement stabilized capture transaction

1. Start with failure tests for source-before/source-after mismatch, source errors, corrupt notes and
   event/note/queue bounds.
2. Read active notes and insert the snapshot in one application transaction between the two source
   observations.
3. Add a post-flush failure seam and prove the inserted row and all transaction state roll back.
4. Record an honest capture window and never expose an atomic `as_of` claim.

## Task 4: Add closed APIs and accessible history

1. Add principal-aware create/list/read routes plus `/api/v1` mirrors. Create accepts only label and
   UUID capture key.
2. Return stable incomplete-source, source-changed, conflict, corrupt-record and bound feedback.
3. Add labelled capture controls, immutable history and an opened historical panel with capture
   window, events, notes and historical queue counts.
4. Keep current review polling, queues, notes, saved views and search independent; retain capture
   intent on failure and contain narrow screens.

## Task 5: Verify, publish and continue

1. Prove identity isolation, closed corpus and no IR/research/execution write or recompute seams.
2. Run focused tests, WS-04/07/08 regression and the full shared-persistence checkpoint because
   migration `0009` adds durable historical state.
3. Update coordination once, commit deliberately, push, verify exact remote state and inspect
   exact-head CI.
4. Generate and continue into a separately designed fork/restore boundary unless evidence exposes
   an owner-gated authority decision.
