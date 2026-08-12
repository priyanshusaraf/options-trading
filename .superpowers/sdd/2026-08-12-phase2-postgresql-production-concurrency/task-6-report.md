# Task 6 report: transactional outboxes and scoped replica delivery

## Base and boundaries

- Base commit: `6c73d618500f6dd8dc061c158a37bfeb18175040`.
- No frontend code changed.
- The protected venue/provider/test files retain their inherited hashes and remain unstaged.
- Each database plane owns its own tables, offsets, aggregate sequences, cursor leases, receipts,
  retention watermarks, notification channel, and repository instance. No cross-plane atomicity or
  total order is claimed.

## Durable contract

Each plane now owns five tables: stream heads, events, consumer cursors, consumer receipts, and
scope-local retention watermarks. Events have an AUTOINCREMENT/identity plane offset, UUID event
identity, exact private scope or closed public classification, aggregate sequence, closed type,
schema version, canonical bounded payload, content address, producer identity, timestamp, and
retention class. Execution uses Alembic head `0033`; research uses head `0004`; ledger uses head
`0002`.

`OutboxRepository.append` requires an explicit caller-owned transaction. The state write and event
therefore commit or roll back together. PostgreSQL uses an advisory producer-key lock, idempotent
stream-head creation, and a locked stream head. Exact retries return the original identity;
changed immutable content fails closed. SQLite uses AUTOINCREMENT so cleanup cannot reuse offsets.

Consumer cursor claims use a separate lease and exact token/expiry fence. PostgreSQL creates new
cursors with `ON CONFLICT DO NOTHING` before `FOR UPDATE SKIP LOCKED`; SQLite uses its serialized
writer reservation. Acknowledge records an effect receipt and advances only the next plane offset.
Heartbeat, release, expiry takeover, stale-token refusal, at-least-once replay, cleanup pinning, and
scope-local retained-away resync are covered. Resync decisions use applicable owner-wide and
account-specific prune watermarks only; sparse global offsets never imply a tenant-local gap. A
fully pruned scope advances the returned cursor through its watermark rather than resyncing forever.

## Producer seams

- Execution: lease claim/takeover/activate/block/release, control request/result, command
  preparation/acknowledged evidence, ambiguity, terminal transitions, and prior-epoch reconciliation.
- Research: operation enqueue plus scheduler stage/item/terminal evidence, including cancellation reconciliation;
  the outbox references the committed `ResearchOperationEvent` sequence.
- Ledger: snapshot versions, artifact content-address metadata/deletion, and manual-fill claims.

These are deliberate typed calls, not generic ORM hooks. Raw ticks, quotes, LogBus entries,
provider payloads, credentials, OAuth/session state, broker responses, request bodies, artifact
bytes, and mutable logs are excluded.

## Delivery and resume

PostgreSQL emits `pg_notify` inside the writer transaction. A dedicated psycopg3 autocommit
connection listens per plane. Notifications only shorten the wait; every wake, reconnect, and
periodic timeout executes a bounded database poll. SQLite never imitates notification semantics.
The app lifespan starts boot-unique managed consumers for execution, research, and ledger on both
API-only and worker replicas and closes them on shutdown.

The replica gateway authorizes event scope, reloads a durable projection, deduplicates by scope,
aggregate type/id and sequence, invalidates the replica-local projection cache, then feeds the
existing bounded/latest-wins `WSManager` channel with the distinct `projection_event` message type.
It never overloads the existing full-runner `state` message with a partial projection.

HTTP (`/api/execution/events` and `/api/v1/execution/events`) and WebSocket resume cursors are
signed for plane plus resolved owner/account. Supplied foreign or mutated cursors fail closed before
an outbox read or WS channel registration. Retained-away valid cursors emit a resync marker before
the fresh scoped snapshot. `PT_EVENT_CURSOR_SECRET` is required for production, shared across API
replicas, and stable across restarts; development alone uses an explicit fixed fallback.

No current-frontend refresh claim is made: the existing frontend does not consume
`projection_event`. Phase 3 must handle the typed invalidation and fetch/reload the projection.

## RED/GREEN evidence

Behavioral REDs were observed for the missing module, absent per-plane models, stale schema heads,
transactionless append, rollback visibility, duplicate producer conflicts, unsafe payloads,
scope leaks, stale acknowledgements, offset reuse, missing listener, missing producer seams,
concurrent first stream allocation, concurrent producer retry, and concurrent first cursor claim.

Latest retained focused evidence before review:

- SQLite contract/model/delivery/product seam and affected auth/tenant/research/ledger/WS gate:
  `300 passed, 5 deliberate skips` across 305 collected tests.
- Live PostgreSQL outbox/lease/money/schema/profile gate: `57 passed, 12 deliberate skips` across
  69 collected tests, including notification timing/rollback, listener wake under the five-second
  fallback, first-stream concurrency, producer retry/conflict, and initial cursor claim.
- Changed Python modules compiled and `git diff --check` is part of the final freeze gate.

## Changed paths

- Contract/delivery: `app/events/{outbox,planes,delivery}.py` and `app/events/__init__.py`.
- Execution schema/factories: `app/db/{models,planes}.py` and Alembic `0033`.
- Research schema/factories: `research/domain/{models,migrate,operations}.py` and migration `0004`.
- Ledger schema/factories: `app/ledger/{db,models,service}.py`.
- Typed execution producers: `app/execution/leases.py`.
- Replica lifecycle/resume boundary: `app/main.py`, `app/api/{routes,principal}.py`, and
  `app/core/config.py`.
- Tests/runbook: `tests/test_outbox_*`, `tests/test_postgres_outbox.py`,
  `tests/test_task6_tenant_channels.py`, `tests/test_user_sessions.py`, `.env.example`, and
  `docs/operations/durable-event-delivery.md`.

Protected inherited dirty paths remained untouched and unstaged. Final expected hashes:

- `app/engine/kite_venue.py`: `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
- `app/engine/venue.py`: `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
- `app/providers/brokers.py`: `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
- `tests/test_broker_registry.py`: `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`

## Deliberate non-claims

This task does not claim Kafka/Redis semantics, exactly-once delivery, cross-plane ordering,
managed-production failover, raw market/log streaming, backup/PITR certification, or Task 7 load
and disaster-recovery proof. Payload facts trigger durable reloads and never become a second state
authority.
