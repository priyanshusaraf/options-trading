# S4.6c Bounded Project Review Search Implementation Plan

**Goal:** Find verified project event summaries and active owner notes without widening the review
corpus or introducing a write/index lifecycle.

**Architecture:** Add a pure bounded normalizer, matcher and sealed keyset paginator. A closed
project route supplies verified event summaries and active owner notes, contains source failures,
and returns typed links. The frontend keeps search transient and independent from timeline filters,
pagination and saved views.

**Boundary:** Literal search over event summaries and active owner notes only. No raw graph,
evidence, scorecard, candidate-reason, global-operation or cross-project search; no new schema.

## Task 1: Pin the pure search contract

1. Start with tests for NFKC, case folding, whitespace collapse, length/control rejection and
   literal treatment of regex-like characters.
2. Test event/note result shapes, missing anchors, timestamp selection and the exact closed corpus.
3. Test match-offset/newest/kind/id ordering, 1-to-50 limits, sealed cursor integrity and
   query-bound cursor rejection.
4. Test 2,000-document source bounds and unchanged-corpus pagination without duplicates or gaps.

## Task 2: Add the closed server-authoritative route

1. Add `GET /projects/{project_id}/review/search` and its existing `/api/v1` mirror with only `q`,
   `limit` and `cursor`.
2. Require the existing review-read owner authorization and derive events through
   `project_review_source`; never accept client documents, event types or links.
3. Read active owner notes under project isolation, mark anchors from the current event map and
   exclude tombstones and corrupt note text.
4. Return stable invalid-query, source-limit and source-corruption feedback plus contained event
   `source_errors` without calling write or recomputation seams.

## Task 3: Add the accessible transient workflow

1. Add a labelled search field, submit and clear controls with retained input on failure.
2. Render event and note matches with kind, anchor state, timestamp and links to their existing
   timeline/note targets; provide exact empty, invalid and source-error states.
3. Add independent load-more behavior using the sealed search cursor.
4. Prove search does not mutate timeline filters/cursors, saved views, notes or queues and does not
   auto-run on reload.

## Task 4: Verify corpus and architecture guards

1. Prove excluded raw graph/evidence/scorecard/candidate/global/cross-project strings never appear.
2. Prove no database writes, IR edit/resolve, research operations, execution or index/table seams.
3. Prove source corruption containment, missing-note behavior and lossless ordinary reload.
4. Prove keyboard labels, live feedback and narrow-screen containment.

## Task 5: Close and continue

1. Run focused backend/frontend tests during implementation.
2. Run the applicable WS-04/07/08 backend regression plus the frontend suite, typecheck and build;
   do not repeat the full shared-persistence checkpoint because this slice has no schema or shared
   runtime change.
3. Update the execution plan and handoff once, commit deliberately, push, verify exact remote state
   and inspect exact-head CI.
4. Generate the next bounded checklist and continue unless its boundary requires an owner decision.
