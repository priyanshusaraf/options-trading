### Task 6: Transactional outboxes and shared scoped event delivery

**Base commit:** the reviewed Task 5 account-lease commit; resolve and record its exact SHA before
implementation.

**Primary artifacts:**

- Add the same small outbox/stream-head/consumer-cursor contract to the execution, research and
  ledger planes, using each plane's own metadata and current-schema startup path.
- Create a portable outbox repository and dispatcher with PostgreSQL `LISTEN/NOTIFY` as a wake-up
  only and polling as the authority. SQLite remains polling-only.
- Add a replica-local scoped event gateway which consumes durable events, refreshes durable
  projections and feeds the existing bounded/latest-wins `WSManager` channels.
- Wire a bounded set of load-bearing mutation seams in each plane and add live PostgreSQL plus
  SQLite delivery, crash, privacy and cache-invalidation tests.
- Modify no frontend code and never touch or stage the four inherited protected files.

**Produces:** committed mutations and their scoped projection changes can be observed by any API
replica after a local process dies or misses a notification. Delivery is at least once, consumers
are idempotent, and an event never becomes a second database authority.

#### Non-negotiable boundaries

- There is no cross-plane atomic transaction or fabricated global event order. Each plane commits
  and orders only its own events. A failure after one plane commits is reported as that plane's
  committed state, not rolled back or mirrored into another plane.
- Do not persist high-rate runner snapshots, option ticks, quotes, raw `LogBus` records, provider
  payloads, credentials, OAuth state, session tokens, request bodies, broker responses or mutable
  in-memory logs. `LogBus` remains privileged process-local telemetry until every producer has a
  verified scope.
- The outbox carries bounded change facts. A WebSocket replica receives a durable event and then
  reloads the authorized durable projection; it does not trust an event payload as the current
  account state.
- PostgreSQL notifications contain only a plane identifier and high-water offset. They are
  emitted inside the writer transaction so PostgreSQL releases them only after commit. Lost or
  duplicate notifications are harmless because polling/cursors remain authoritative.
- SQLite remains a local/test/single-node profile. It uses short polling and no imitation of
  PostgreSQL notification semantics.
- Events are explicitly `private` or `market_public`. `private` always has a non-empty owner scope;
  account-scoped events also have a broker-account scope. Only a closed allowlist may emit
  `market_public`; caller-provided classification is rejected.
- Keep payloads secret-free, schema-versioned, bounded and canonical. Do not use tenant/account,
  event, worker or aggregate identifiers as uncontrolled shared metric labels.

#### Durable model per plane

Use plane-local table names and metadata, but one shared interface and semantic contract:

`OutboxStreamHead`:

- composite `(aggregate_type, aggregate_id)` identity inside the plane;
- positive monotonic `last_sequence` and updated timestamp;
- locked in the same transaction that allocates the next aggregate sequence.

`OutboxEvent`:

- database-generated positive monotonic plane offset plus random/UUID event id;
- `classification` (`private | market_public`), non-null normalized scope key, owner id and optional
  account id;
- aggregate type/id and positive aggregate sequence;
- closed bounded event type, positive schema version, canonical bounded JSON payload and lowercase
  `sha256:` content address;
- producer/idempotency identity, created timestamp and retention class;
- unique `(aggregate_type, aggregate_id, aggregate_sequence)`, event id and producer identity;
- indexes for plane offset, scope+offset and retention cutoff.

`OutboxConsumerCursor` and `OutboxConsumerReceipt`:

- bounded internal consumer identity, lease owner/token/expiry, next or last committed offset,
  heartbeat and last error projection;
- receipt/idempotency identity for effects that cannot be made sequence-idempotent directly;
- a consumer advances its cursor only after its local effect commits. A crash before cursor advance
  may repeat delivery and must not repeat the effect.

Keep internal consumer leases separate from Task 5 account execution leases. Outbox consumers
never obtain broker authority.

#### Repository and transaction API

Create a small shared repository module whose methods operate on an injected `Session` and the
plane-specific mapped classes. Required interfaces:

- `append(session, *, classification, owner_id, broker_account_id, aggregate_type,
  aggregate_id, event_type, schema_version, payload, producer_key) -> EventIdentity`;
- `claim_batch(session, *, consumer_id, limit, lease_seconds) -> ClaimedBatch` using SQLite short
  reservation or PostgreSQL `FOR UPDATE SKIP LOCKED` without holding a lock while doing WebSocket
  or network work;
- `ack(session, claim_token, event_id, effect_key=...)` and cursor advancement with exact lease
  fencing;
- `release/expire` and bounded retention cleanup which refuses to delete events still required by
  a healthy cursor;
- `read_scoped_after(session, principal_scope, offset, limit)` which applies scope predicates in
  SQL before returning any event and reports a snapshot-resync requirement when retention passed
  the cursor.

`append` must be called inside the same transaction as the state mutation. It must reject an
ambient standalone/autocommit use unless the caller explicitly owns a transaction. Duplicate
producer keys return the original identity only when all immutable event fields match; otherwise
they fail closed.

#### Producer seams

Wire a deliberately bounded set that proves the architecture without turning every row into an
event:

Execution plane:

- Task 5 lease projection changes, control requests/results and blocked/recovery state;
- execution intent/order-lifecycle terminal or ambiguity changes;
- position/trade/capital projection changes;
- backtest enqueue/cancel/terminal changes;
- deployment, graph publication, owner runtime config, universe preference and broker-connection
  readiness changes needed for replica cache refresh.

Research plane:

- durable operation claim/stage/item/terminal changes, findings/spec/run completion and promotion
  decisions. Existing `ResearchOperationEvent` remains scheduler/audit evidence; the outbox may
  reference its committed sequence but does not reinterpret it as delivery authority.

Ledger plane:

- snapshot version changes, artifact metadata/content address only, and manual-fill detection or
  claim transitions. Never place artifact bytes or raw broker/order payloads in an event.

Market-public events:

- only canonical, owner-independent cache invalidation metadata whose answer is already explicitly
  public. Live prices/ticks and private universe preferences do not qualify.

At each seam prove rollback removes both the state mutation and event. Avoid a generic ORM hook
that guesses event meaning from dirty rows; call the typed append method from reviewed repository
transactions.

#### Dispatcher, replica gateway and WebSocket contract

- PostgreSQL listener uses a dedicated autocommit connection per plane. Reconnect with bounded
  exponential backoff, discard notification payloads other than plane/high-water hints, and poll
  immediately after reconnect.
- Every dispatcher always performs a bounded database query from its fenced cursor even after a
  notification. It polls periodically when no notification arrives.
- The API replica authorizes owner/account scope before adding an event to its local gateway.
  Private events map only to the existing exact `(owner_id, broker_account_id)` channel or an
  owner-only channel designed for owner resources. Public events use the already explicit public
  market channel.
- Durable projection events trigger a fresh scoped database read and then the existing local
  latest-wins state/tick queue. Preserve one local serialization per broadcast and bounded pending
  work for 250+ connections.
- Client resume cursors are signed/opaque or server-bound to the resolved principal scope. A
  guessed, mutated or foreign cursor is indistinguishable from absent/invalid and never broadens a
  query. If its offset was retained away, return/emit a resync marker and a fresh scoped snapshot.
- Cache invalidators use `(classification, owner/account scope, cache namespace, durable version)`.
  Duplicate and old aggregate sequences are no-ops. They never evict or hydrate another tenant's
  entry.

#### Retention, observability and operating contract

- Define explicit bounded retention by class and a minimum catch-up window. Healthy consumer
  cursors pin only the window they still need; abandoned consumers expire and cannot retain the
  table forever.
- Expose bounded host/plane aggregates: append rate/failures, oldest undelivered age, cursor lag,
  claim/takeover, duplicate delivery, resync, listener reconnect/lost-notify recovery, cleanup and
  payload rejection. Do not label metrics by raw scope, aggregate, event or consumer id.
- Add an operator runbook covering listener outage, cursor reset/resync, retention pressure,
  poisoned-event block/refusal, replica restart, and the absence of cross-plane ordering.

#### Test-first acceptance

- Capture behavioral REDs for missing outbox, state commit without event, event visible after
  rollback, duplicate side effect, foreign cursor read, lost-notify stall and tenantless cache key.
- Run SQLite and live PostgreSQL tests showing state+event commit atomically and rollback together.
- On PostgreSQL, prove notification is not received before commit and is absent after rollback;
  then deliberately drop notifications and prove polling catches every committed offset.
- Use two independent dispatcher sessions to prove `SKIP LOCKED` assigns an event once per claim,
  a crashed consumer's lease expires, another resumes, and stale claim tokens cannot ack/advance.
- Deliver duplicates and aggregate sequences out of order; projections/cache effects converge once
  without rollback or cross-tenant eviction.
- Kill/restart a replica between local effect and cursor ack; repeated delivery produces no
  duplicate durable or client-visible transition beyond the allowed latest-wins refresh.
- Prove `/api` and `/api/v1` plus WebSocket resume paths reject a foreign/guessed cursor before any
  payload or count is read. Same event/aggregate ids may exist in two tenants without collision.
- Re-run the existing 250+250 exact-channel isolation test and assert one serialization, bounded
  pending work and no B delivery for an A event.
- Prove a retained-away cursor emits resync then reloads only its owner/account snapshot.
- Test payload size, schema/type allowlist, JSON finiteness, secret-key rejection and content-address
  validation. Mutation tests removing scope, cursor-fence or transaction coupling must turn the
  focused gate red.
- Run focused auth/tenant/execution/research/ledger/cache/WS gates, live PostgreSQL concurrency,
  compilation and `git diff --check`. One bounded broad run is optional; do not repeat it for
  ceremony.
- Stop uncommitted for independent Sol review.

#### Exclusions

- No raw tick/log/event firehose, Kafka, Redis or new external broker.
- No frontend changes.
- No cross-plane transaction, total order or exactly-once claim.
- No Task 7 backup/load certification.
- No product/user-count cap; limits are operational workload/admission bounds.
- Never touch or stage the protected venue/provider/test files.

#### Report

Write `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/task-6-report.md`
with model/table contracts, exact producer seams, transaction boundaries, PostgreSQL notification
and polling behavior, retention/resync rules, RED/GREEN evidence, live commands/results, deliberate
non-claims, changed paths and protected hashes. Stop uncommitted for independent review.
