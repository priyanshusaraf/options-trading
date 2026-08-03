# ADR 0010: Review snapshots are immutable stabilized observations

- **Status:** Accepted for S4.6d
- **Date:** 2026-08-03
- **Owners:** WS-08 review workflow, WS-04 project ownership and WS-07 persistence
- **Depends on:** ADR 0007 daily review, ADR 0008 review notes and ADR 0009 bounded search

## Context

The current review surface is intentionally derived from application graph records, research
records and active owner notes. A user needs to preserve what they reviewed on a given day even if
source statuses or notes later change. The application and research databases cannot provide one
atomic cross-store snapshot. Any design that records one `as_of` instant would claim consistency
the system cannot prove.

## Rejected approaches

| Approach | Reason rejected |
|---|---|
| Store a browser-submitted review document | The client could invent facts, queues, source errors or immutable identities. |
| Claim one atomic `as_of` timestamp | Application and research stores have independent transactions. |
| Capture after one source read | A publication or research decision during note capture could produce an avoidably mixed observation. |
| Capture when a source is corrupt or unavailable | A historical object would certify a partial review without a trustworthy completeness boundary. |
| Copy raw graph JSON, evidence, scorecards or decision reasons | A review snapshot needs the closed review projection, not executable or sensitive source documents. |
| Include global operation receipts | Installation-wide operational state is not a project-owned review fact. |
| Treat captured queues as current | Queue membership is authoritative only when derived from current source state. |
| Make snapshot content a graph version or experiment input | Historical review context cannot affect executable, cache, component or experiment identity. |
| Add restore or fork behavior to capture | Applying historical state has separate authority, conflict and provenance requirements. |

## Decision

### Historical object and content

A snapshot is an append-only project-owned application record with a server id, owner label,
validated capture key, capture start/completion timestamps, canonical manifest and manifest content
address. The capture key is a UUID generated once by the client for transport idempotency only. It
cannot select a snapshot id, source version or content address. Repeating the same project/capture
key returns the completed record; reusing it with different intent fails closed.

The schema-versioned manifest contains only:

- the project id;
- the complete bounded set of verified S4.6a event projections, in canonical event-id order;
- `captured_queues` containing the three project queues from ADR 0007, explicitly historical;
- active owner notes with id, immutable anchor, body, revision, anchor state and update time; and
- an empty source-error list proving capture refused partial sources.

Graph references inside verified event and queue projections retain identifier, immutable version
and content address for provenance. Raw graph JSON, parameters, evidence, scorecards, finding
statements, candidate decision reasons, global operations, saved views, search text/results,
deleted notes and every other project's data are excluded. Label, capture key, server snapshot id
and capture window are record metadata outside the manifest content address. Two captures of the
same review content therefore share a content address while remaining distinct historical records.

### Stabilized capture, not atomic time

Capture records `capture_started_at` before the first source read and `capture_completed_at` after
manifest finalization immediately before the immutable row is flushed. It performs:

1. one closed project review source read;
2. one application transaction that verifies the active project and capture-key state, reads active
   owner notes, performs a second closed source read, compares both canonical source projections,
   builds and validates the manifest, and inserts the immutable row; and
3. one commit of the note observation and snapshot row.

Any source error, source difference, corrupt note, size breach, key conflict or insertion failure
rolls back the application transaction. Matching reads reject an observed mid-capture change but do
not create a cross-database lock. The response calls this a `capture_window`, never an `as_of`
instant. A source can change immediately after the second read; the stored object remains an exact
record of the validated observation, not current truth.

Capture accepts at most 2,000 events and 2,000 active notes, with the existing queue bounds checked
separately. Exceeding a bound refuses capture. Canonical ordering and validation happen on the
server before hashing and insertion.

### Bounded, self-verifying reads

`content_address(v)` is `sha256(canonical_json(v))`, so already-canonical stored bytes hash to
their own declared address. Reads exploit this at two different costs:

- **List** returns at most `MAX_SNAPSHOT_LISTING` (100) metadata records, newest first, and
  verifies each by hashing the stored manifest bytes. It never parses or rebuilds a manifest, so
  a listing stays constant-size per row however large the captured review was. A byte-level match
  proves the row is identical to what validation accepted on insert.
- **Read-one** additionally re-runs full semantic validation and compares the rebuilt address.

Every read therefore verifies the content address; only the single-record read pays for semantic
revalidation. A row whose bytes no longer match its declared address is reported as
`integrity: "corrupt"` in the listing and refused on read. Corruption is **contained, not
propagated**: one damaged record must never withhold the rest of a project's review history, and
the surface disables opening it rather than rendering unverified content.

### Lifecycle and API

Capture requires an active project and the normalized durable owner. List/read remain available for
archived projects. S4.6d exposes create, list metadata and read-one only. There is no update, delete,
restore, fork, acknowledgement or queue mutation route. The UI labels every opened object
“Historical capture”, shows its capture window and never mixes captured queue counts into current
queues.

Migration `0009` is additive. Empty downgrade returns exactly to `0008`; populated downgrade
refuses rather than discard historical review records. Software rollback may leave the unused table
in place. A destructive schema rollback requires export and verified restore.

## Guard proofs

S4.6d must prove:

1. different first/second source projections reject capture without a row;
2. any source error, corrupt note or bound breach rejects capture without a row;
3. failure after snapshot flush rolls back the whole application transaction;
4. client bodies cannot supply events, queues, notes, content addresses, snapshot ids or versions;
5. capture-key retries are idempotent and conflicting reuse cannot create or alter a row;
6. canonical-equivalent manifests share content identity and any allowed content difference changes
   it;
7. snapshots cannot change graph, component, cache, experiment, evidence or current queue identity;
8. archived and cross-project capture/read rules are exact;
9. raw artefacts, global operations, saved views, search state and decision reasons are absent; and
10. capture/list/read call no IR edit/resolve, research orchestration, execution, deployment, broker
    or capital seam.

Seam guards must patch the binding the call path actually resolves. `app/editor/graph_artifacts.py`
does `from app.ir.resolve import resolve`, so patching `app.ir.resolve.resolve` leaves its own
reference intact and the guard silently never fires; patching a name that does not exist at all
(via `hasattr`, or `raising=False`) is the same failure wearing a passing test. Every seam guard
in this slice patches the resolved binding with `raising=True`, so a renamed or deleted seam
breaks the guard instead of quietly hollowing it out.

### Accepted residual risks

Review event summaries are composed by `project_review_source` and frozen verbatim into a
content-addressed manifest. `ExperimentRun.decision` is an unconstrained `String(16)` in the
research database, so S4.6d narrows it to the orchestrator's own vocabulary
(`propose|archive|needs_review`) before it can reach a summary; an unrecognised value degrades to
the run status rather than being copied out unvalidated. Summaries remain length-bounded by
`MAX_SUMMARY`, so this path cannot carry a payload — only a short label.

The immutability triggers are `execute_if(dialect="sqlite")`. On another backend only the Python
`before_insert` identity check survives, so a port must re-establish append-only enforcement in
the database rather than assume it.

## Boundary

S4.6d adds immutable review capture/list/read only. Snapshot comparison, export, deletion,
retention automation, fork/restore, collaboration, execution and deployment remain out of scope.
