# Durable event delivery operations

Strategy OS has one durable outbox in each execution, research, and ledger plane. Each plane
orders only its own events. There is no cross-plane transaction or global order.

PostgreSQL `LISTEN/NOTIFY` reduces delivery latency. Notifications contain only the plane and a
high-water offset. Polling the fenced consumer cursor remains authoritative. SQLite uses polling
only and remains a local/single-node profile.

## Listener outage and replica restart

The managed delivery loop reconnects with bounded backoff and polls immediately after reconnect.
A missing or malformed notification does not skip an event. On shutdown the listener connection
is closed and the background task stops. After an unclean restart, an expired consumer lease is
claimed by the replacement and any event whose effect committed before cursor acknowledgement may
repeat. Projection refresh and cache invalidation are sequence-idempotent.

## Cursor reset and resync

Resume cursors are opaque and signed for the resolved plane, owner, and broker account. Reject a
foreign or malformed cursor before reading event rows. If retention has advanced beyond a valid
cursor, send a `resync` marker, reload the authorized durable snapshot, and issue a fresh cursor.
Never copy a cursor between accounts or edit its offset.

Set `PT_EVENT_CURSOR_SECRET` to at least 32 random characters in production. Every API replica
must use the same value, and it must remain stable across restarts. Rotating it deliberately
invalidates every outstanding cursor. Development uses a fixed non-secret fallback; never carry
that fallback into a production service role.

## Retention pressure

Healthy cursors pin the oldest event they still require. Abandoned cursors stop pinning after the
configured health window. Cleanup updates a scope-local retention watermark before deleting rows,
so a fully pruned scope still produces a truthful resync decision. Increase the catch-up window or
repair lagging consumers before increasing cleanup volume.

## Poisoned events

Do not edit an event payload in place. Payloads are content-addressed and bounded. A consumer that
cannot process a known schema/type should retain its cursor, expose the bounded last error, and
refuse advancement. Repair the producer/consumer code or use an operator-approved scoped snapshot
resync. Never skip an event by manually advancing a cursor without recording the incident.

## Privacy and observability

Private delivery is keyed by exact owner plus optional broker account. Public delivery uses a
closed event allowlist; no live ticks, quotes, credentials, request bodies, broker responses, raw
logs, or artifact bytes belong in the outbox. Metrics expose only host/plane aggregates such as
high-water offset, event age, cursor lag, active leases, cleanup count, reconnects, and resyncs.
Never label metrics with owner, account, event, aggregate, producer, or consumer identifiers.
