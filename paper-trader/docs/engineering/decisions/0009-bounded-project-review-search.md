# ADR 0009: Project review search is a bounded derived read

- **Status:** Accepted for S4.6c
- **Date:** 2026-08-03
- **Owners:** WS-08 product surface, WS-04 project ownership and WS-07 read integrity
- **Depends on:** ADR 0007 daily review read model and ADR 0008 review notes

## Context

The daily review now has verified project events and durable owner notes. Users need to find that
small body of review writing without turning executable or research artefacts into a general search
corpus. Search must preserve the authority boundary: it may locate already-readable text, but it
cannot recompute facts, broaden project access, mutate queues or create another source of truth.

## Rejected approaches

| Approach | Reason rejected |
|---|---|
| Search raw graph JSON, evidence, scorecards or candidate reasons | These documents may contain large, sensitive or executable detail outside the review-summary contract. |
| Search global operation receipts | They are installation-scoped operational state, not project review facts. |
| Build a new search table or external index | S4.6c does not need another persistence lifecycle, freshness contract or deletion path. |
| Let the browser filter loaded timeline pages | Results would depend on pagination, stale client state and text the server did not authorize as a corpus. |
| Accept regex, fuzzy expressions or client-selected ranking | These widen resource and interpretation risk without a current product need. |
| Save search text inside S4.6b saved views | Saved views have a closed filter contract; changing it silently would alter their durable semantics. |
| Return copied event summaries for missing note anchors | A missing source must remain explicit rather than presenting stale text as a current fact. |

## Decision

### Closed corpus

Search is a project-scoped server read over two document kinds only:

1. the `summary` of each currently verified S4.6a project event; and
2. the `body` of each active review note owned by the normalized durable `owner`.

Event references are used only to form existing product links. Graph JSON, parameters, content
addresses as text, research evidence, scorecards, rejection/candidate reasons, findings bodies,
operation receipts, saved-view names, deleted notes and every other project's data are excluded.
An active note whose event has disappeared remains searchable as owner writing and returns
`anchor_state = missing`; no absent summary is copied into the result.

### Query, matching and order

The closed query has `q`, `limit` and optional `cursor`. `q` must contain 2 to 120 Unicode code
points after NFKC normalization, case folding and whitespace collapse. Control characters are
rejected. Matching applies the same normalization to the one allowed text field and uses literal
substring containment only. Regex, wildcards, Boolean syntax and fuzzy expansion have no special
meaning.

Each match has a deterministic rank tuple: match offset ascending, document timestamp descending,
kind (`event` before `note`) and stable result id. Event time is `occurred_at`; note time is its
latest persisted `updated_at`. The response limit is 1 to 50. A sealed keyset cursor contains the
normalized-query content address and the final rank tuple, so it cannot be reused for another query
or edited by the client. Search reads at most 2,000 verified events and 2,000 active notes; exceeding
either bound fails closed with an exact source-limit error rather than returning an undisclosed
partial corpus.

### Source containment and authority

The endpoint derives events through the existing read aggregator and notes through the application
repository. It returns contained `source_errors` for unavailable graph/research sources while
searching the remaining verified corpus. A corrupt note row fails the note source explicitly and
cannot hide valid event matches. Project absence and authorization use the existing exact seams.

Search never calls IR editing or resolution, research orchestration, execution, broker, deployment,
queue mutation or any write repository. It creates no table, index, migration or durable query.
Presentation polling and saved filters remain independent of search state.

## Guard proofs

S4.6c must prove:

1. NFKC/case/whitespace equivalents produce the same query identity and results;
2. stable order and sealed cursors neither duplicate nor skip an unchanged corpus and reject use
   with another query;
3. raw graphs, evidence, scorecards, candidate reasons, global operations, saved views, deleted
   notes and cross-project text cannot appear;
4. missing-anchor notes remain searchable without an invented event summary;
5. corrupt or unavailable event sources are contained and reported, while corrupt note state is
   reported without exposing unverified text;
6. search performs no database write, source recomputation, IR edit/resolve, research operation or
   execution call;
7. search state does not alter timeline pagination, saved views, queues or executable/research
   identity;
8. invalid, empty, oversized and control-character queries receive exact closed feedback; and
9. the accessible UI retains the query on failure, links results to existing review objects and
   remains contained at narrow width and after reload.

## Boundary

S4.6c adds transient bounded review search only. It does not add full-text indexing, raw artefact
search, saved searches, snapshots, fork/restore, acknowledgements, collaboration, execution or
deployment behavior.
