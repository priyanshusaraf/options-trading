# ADR 0008: Review notes and saved views are project-owned non-authoritative state

- **Status:** Accepted for S4.6b
- **Date:** 2026-08-03
- **Owners:** WS-08 product surface, WS-04 project ownership and WS-07 persistence
- **Depends on:** ADR 0007 daily review read model

## Context

S4.6a derives a trustworthy project timeline and current queues from source ledgers. A repeatable
research day also needs durable human context and reusable filters. Neither belongs in graph IR,
research evidence or the derived event stream. Notes and saved views are user-authored product
state; treating them as source facts would let presentation intent rewrite research history.

The application currently has one human owner represented by either the authenticated `owner`
principal or the explicit `anonymous-owner` principal when authentication is disabled. Those are
two authentication postures for the same owner, not separate durable data owners.

## Rejected approaches

| Approach | Reason rejected |
|---|---|
| Store notes inside graph, evidence, finding or candidate JSON | It rewrites executable or research identity and creates a second mutation path into source ledgers. |
| Put notes in `research.db` | Review annotations are product state and must not make the research plane depend on application identity or UI lifecycle. |
| Let a note acknowledge or hide a queue item | Queues describe current persisted state. A note cannot make a failed run, pending decision or active finding resolved. |
| Persist an opaque review query string | It accepts unknown fields, cursors and future semantics without validation. |
| Copy event summaries into note rows | A stale copy could be presented as current source truth after a run/finding status changes. |
| Treat `owner` and `anonymous-owner` as different durable owners | Enabling authentication would make the same human lose access to data created in local mode. |
| Cascade-delete annotations when a source event disappears | Source retention or restore would silently erase human context. |
| Add search, acknowledgements, snapshots or fork/restore here | Each has separate indexing, authority or transactional contracts and would widen this persistence slice. |

## Decision

### Ownership and identity

Review notes and saved views live in the application database under a real `Project`. Reads remain
available for archived projects; writes require an active project and the existing owner
authorization seam. Durable `created_by` is normalized to `owner` for both current owner principal
forms. Authentication posture is not data ownership.

A note has a server-generated opaque id and an immutable anchor `(project_id, event_id,
event_type)`. Creation accepts only `event_id`; the server derives and verifies the type from the
current S4.6a project event set. Global operation receipts cannot be note anchors because they are
not project events. Later source status changes do not change the anchor. If retention, restore or
source corruption makes the event unavailable, the note remains visible with `anchor_state =
missing`; the server does not invent or preserve a stale event summary.

A saved view has a server-generated opaque id, project-scoped name and one canonical closed filter
document containing only event type, status, UTC after/before and limit. Cursors are transient
positions and cannot be saved. Filter validation is the same validation used by the review route.

### Mutation and lifecycle

Both objects use integer optimistic revisions. Create starts at revision zero. Update requires the
exact base revision and advances once atomically. The note anchor and saved-view id/project owner
never change. Delete is a revision-checked tombstone so stale writers cannot recreate or overwrite
deleted state and ids are never reused. Normal list/read responses exclude tombstones.

Notes are bounded plain text. They carry no executable JSON, HTML, Python, credentials, raw
evidence or client-declared source identity. Saved views carry no cursor, sort expression, SQL,
search expression or queue visibility state. Applying a view only issues the existing S4.6a read
with its validated filters.

### Isolation and identity

These tables have restrictive project foreign keys and no foreign key into graph or research
facts. They are excluded from graph canonical JSON, content addresses, components, node caches,
experiments, evidence and runtime. No note or view operation imports or calls IR edit, resolution,
research orchestration, execution, deployment, broker or capital code.

## Transactions, migration and rollback

Each note or view mutation is one application-database transaction with a compare-and-swap update.
No cross-database atomicity is claimed. Migration `0008` is additive and touches no existing row.
An empty `0008` downgrade drops both tables and returns exactly to `0007`. A populated downgrade
must refuse rather than discard user writing; software rollback leaves the additive tables unused,
and schema rollback after real use requires an exported backup and verified restore.

## Guard proofs

S4.6b must prove:

1. notes and views cannot alter graph/evidence/cache/experiment identity;
2. global operations and wrong-project or invented event ids cannot become note anchors;
3. stale update/delete requests make no partial change;
4. a disappeared source event leaves its note visible as missing without a copied summary;
5. saved views reject cursors, unknown fields, unsupported values and invalid date ranges;
6. notes and views cannot hide, acknowledge or change authoritative queues;
7. authenticated and auth-disabled owner modes address the same durable data;
8. migration/model equivalence, empty downgrade and populated-downgrade refusal preserve existing
   money, graph and layout rows;
9. routes cannot call source writes, IR edit/resolve, research orchestration or execution seams.

## Boundary

S4.6b adds event-linked notes and named saved filter views only. Search, acknowledgements, queue
dismissal, snapshots, fork/restore, collaboration, execution and deployment remain out of scope.
