# ADR 0007: Daily review is a derived project timeline plus a global operations lane

- **Status:** Accepted for S4.6a
- **Date:** 2026-08-03
- **Owners:** WS-03 Research, WS-04 graph lineage and WS-08 product surface
- **Depends on:** ADRs 0002–0006

## Context

The product now persists immutable graph versions, graph-bound experiment runs and evidence,
successor-based findings, candidate decisions and one global current/last research operation
receipt. Each is trustworthy in its own ledger, but a user must scan several panels to answer:
what changed today, what failed, and what needs a decision?

These facts do not share one database. Graph versions live in the application database; runs,
findings and candidates live in `research.db`; the bounded operation receipt exists even when
research DB setup or planning fails. Creating another timeline table would duplicate facts and
introduce cross-database write coordination merely to support a read.

One contradiction must be resolved explicitly: an operation receipt has no project identity. A
zero-plan, planning failure or pre-spec collection failure cannot be attributed to any project.
Inferring ownership from its plan text or later run ids would turn a global scheduler fact into a
false project event.

## Rejected approaches

| Approach | Reason rejected |
|---|---|
| Persist a new timeline/event table | It duplicates existing ledgers and requires fallible dual writes across databases and a file receipt. |
| Assign every operation to the requested project | Operations have no project key and may fail before a graph-bound spec/run exists. |
| Copy evidence/results into timeline payloads | Exact evidence already has a content-addressed owner and can be linked by run id. |
| Treat the multi-store read as one atomic transaction | SQLite transactions cannot atomically snapshot two databases plus an independently replaced receipt file. |
| Add acknowledgement/read state in S4.6a | It is a new mutable product object with unresolved ownership and retention semantics. |
| Reuse the trading journal timeline | The local-first ledger application has different identity, storage and synchronization contracts. |

## Decision

### Ownership and source facts

The daily review response has two explicitly separate lanes:

1. a **project timeline** containing only facts whose persisted lineage proves ownership by the
   path project; and
2. a **global operations lane** containing verified current/last bounded research operation status.

Project events are derived, never copied, from:

- immutable `GraphVersion` publication rows owned through `GraphArtifact.project_id`;
- graph-bound `ExperimentRun` rows whose immutable recipe names the project;
- `Finding` rows whose evidence run names the project;
- `PromotionCandidate` creation and, when present, its canonical decision envelope, through its
  graph-bound run.

The global lane preserves `nightly | manual_script`, operation id, stage, state, plan address and
linked run ids exactly as ADR 0005 allows. It is never inserted into project event pagination or
counts. A corrupt operation receipt becomes a contained global source error; it does not erase a
valid project timeline.

### Derived event contract

Each project event has a deterministic id from its owning ledger key and event kind, a UTC
`occurred_at`, closed `type` and `status`, a bounded server-authored summary, and typed references
to existing graph version, run, finding or candidate reads. It carries no raw graph, evidence,
scorecard, statement search index or executable content.

Candidate creation and decision are separate events. A terminal candidate therefore retains when
it entered the queue and when the owner decided it. Finding successors remain separate immutable
events; active/superseded is current status derived from the successor link.

Events sort by `(occurred_at, event_id)` descending. The opaque cursor is a bounded canonical,
content-addressed encoding of the last returned sort key. Later events can arrive above a cursor
without moving the continuation below it. Invalid/tampered cursors fail closed. The first slice
supports bounded UTC date, event-type and status filters plus a maximum page size. Search, notes,
saved views, acknowledgements and snapshots remain later M6 work.

### Queues and source containment

Queues are current derived projections, not event history:

- global failed operation, if the verified last receipt failed;
- project runs requiring review or carrying safe failed evidence state;
- project candidates still pending;
- project findings with no successor.

A corrupt individual research row produces a bounded `source_errors` entry keyed by source/id and
is excluded from any queue that would require trusting it. Other valid events remain visible. A
missing research database is an empty research lane, not an application failure. The response
records an `as_of` timestamp but does not claim a cross-store atomic snapshot.

### API and product surface

One closed read-only project route accepts query filters/cursor only. It invokes no provider,
planner, resolver, evaluator, orchestrator or write seam. The product renders the global operation
status distinctly, then project queues and the paginated timeline. Typed references link back to
existing version, evidence, finding and candidate surfaces. There are no remote run, decision,
acknowledgement, execution or deployment writes in S4.6a.

## Rollback

No schema or source-ledger change. Reverting removes the derived route and surface. Existing graph,
research, finding, candidate and operation records remain unchanged.

## Guard proofs

S4.6a must prove:

1. global operations never acquire project identity or enter project pagination/counts;
2. deterministic ordering and cursor continuation remain stable when a newer event arrives;
3. tampered/oversized cursors and unbounded/unknown filters fail closed;
4. wrong-project facts remain hidden;
5. corrupt operation or one corrupt research row is contained without hiding valid sources;
6. candidate creation and decision retain separate timestamps/identities;
7. queues derive only from persisted current state and contain no duplicated evidence;
8. reads invoke no provider, planner, resolver, evaluator, orchestrator or write path.

## Boundary

S4.6a does not add notes, search, saved filters, snapshots, fork/restore, acknowledgements, a new
event database, scheduler controls, experiment start, execution, deployment, Python or marketplace
semantics.
