# USER/Research Ownership Design

## Purpose

Phase 1 Task 3 makes customer-created product and research objects structurally owned by an
organization. It closes global project, graph, layout, watchlist, strategy, research and review
lookups before authentication, jobs or frontend contracts are built on top of them.

This design does not own backtest/job/result visibility, implement authentication, partition
WebSockets, or create sharing and marketplace mechanics. Those remain Tasks 4-6.

## Ownership rules

- `owner_id` is the organization value used at USER-plane repository boundaries.
- USER-plane foreign keys to `organizations.organization_id` are allowed because both tables are
  in the same plane. Cross-plane relations remain stable values rather than foreign keys.
- Every public repository operation requires keyword-only `owner_id`.
- Ownership is part of the SQL predicate that loads the object. Code must not load a global row
  and reject it afterwards.
- Opaque globally generated row IDs may remain global primary keys, but direct lookup always
  includes `owner_id`. Human identifiers and names are unique only inside one owner.
- Graph identifiers and their version/layout descendants use structural owner scope so separate
  organizations may use the same graph identifier safely.
- Legacy rows backfill to `LEGACY_OWNER_ID`. Runtime callers must pass scope explicitly; only
  bootstrap/migration compatibility code may name the legacy constant.

## Canonical graph identity and private IP

`owner_id`, project membership, actor identity and access policy are provenance. They do not enter
canonical graph JSON, component JSON or `content_address`. Two owners may independently create
byte-identical graphs with the same content address, but no API or repository may answer a global
hash lookup or reveal whether the other copy exists.

The existing term “published graph revision” means an immutable executable revision. It does not
mean public access. Task 3 keeps all graphs private and adds a private-only visibility seam at the
immutable version boundary. There is no shared/public discovery, transition API or cross-owner
read. A later reviewed release model may expand this to:

```text
PRIVATE → explicit SHARED grant
PRIVATE → explicit PUBLISHED release/projection
```

Publishing must eventually create a separately authorised projection of one frozen version; it
must not mutate source ownership or expose related datasets, research, credentials or history.

## Relational application database

The next Alembic revision rebuilds affected SQLite tables in dependency order and preserves all
payloads and timestamps:

1. `projects` gains `owner_id`; project names become tenant-local.
2. `graph_artifacts` becomes owner-scoped, and graph versions/layout heads/positions/groups/group
   members/orphan archives carry the same owner key through composite foreign keys.
3. review notes, saved views and immutable snapshots gain owner scope. Capture-key and live-name
   uniqueness become tenant-local. Legacy actor values remain preserved; actor/principal
   resolution is completed in Task 5.
4. watchlists, memberships, strategy lifecycle rows, generated strategy rows and runtime config
   gain owner scope. Watchlist name, strategy key and runtime-config key are tenant-local.
5. by-value graph provenance held by MONEY-plane deployment rows remains byte-preserving and is
   not converted into a cross-plane foreign key.

Every SQLite rebuild is restart-safe, recreates historical indexes and immutable triggers, and
refuses a lossy downgrade once multiple owner dimensions cannot fit the prior global identity.

## Research database

The separate `research.db` currently relies on `create_all()` and global identities. Task 3 adds
an explicit versioned migration boundary for research metadata rather than silently changing ORM
tables.

Research roots and immutable specifications gain owner provenance:

- research programs and hypotheses;
- experiment specifications;
- generated strategy/source records;
- reusable research block definitions.

Human names become tenant-local. Content hashes may remain integrity fields but are never global
lookup capabilities. Task 4 carries ownership into experiment runs, trials, findings, promotion
candidates, shadow sessions, backtest evidence and operation/job files when it implements their
visibility and lifecycle repositories.

## Repository and service contract

Task 3 threads keyword-only `owner_id` through:

- graph/project creation, listing, status changes, draft/version loads, publishing and comparison;
- graph layout load/save/reconciliation and presentation edits;
- watchlist, strategy archive/lifecycle, generated strategy and runtime-config stores;
- review state, note, saved-view, snapshot, aggregation and search stores;
- research program/spec/generated-source roots and project-bound research reads.

API routes may temporarily obtain the legacy development owner through the existing trusted
composition boundary. They must pass it explicitly. Task 5 replaces that boundary with a real
session principal and active organization; request bodies never choose `owner_id`.

## Failure and privacy behavior

- A wrong owner receives the same not-found/refusal result as an absent object.
- Errors never name another owner or disclose another tenant's hash, row count or existence.
- No source, graph JSON, review manifest or standard response gains ownership fields unless the
  authenticated owner-facing contract requires them.
- No plaintext graph/source payload is added to logs.
- Existing immutable graph and snapshot corruption checks remain active after migration.

## Acceptance tests

The Task 3 gate creates two organizations that deliberately reuse project names, graph
identifiers, graph bytes, watchlist names, strategy keys, review names and research names. It
proves:

- unscoped repository calls fail at the Python boundary;
- every wrong-owner direct load returns no row/refuses before content is materialized;
- graph versions, layouts, reviews, watchlists, strategy state and research roots are isolated;
- identical graph bytes retain identical canonical addresses across owners and migration;
- no hash/existence side channel is exposed;
- all existing graph, layout, review, research and migration regressions pass;
- downgrade and injected-restart tests preserve data or refuse loss explicitly.

## Deferred boundaries

- Task 4: backtests, jobs, optimiser/validation evidence, result visibility and private cache hits.
- Task 5: real user sessions, membership roles, actor attribution, route authorization and IDOR.
- Task 6: WebSocket/log fan-out, exports, in-memory caches and privileged-access audit events.
- Later security/publication work: encryption/key management, sharing grants, public releases,
  licensing, revocation, discovery and marketplace behavior.
