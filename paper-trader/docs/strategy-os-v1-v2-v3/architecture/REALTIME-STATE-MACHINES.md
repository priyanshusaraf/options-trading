# Realtime state machines

## Decision

Model broker transport, authentication, market subscription, feed freshness, internal delivery, and browser connection as separate state machines.

A connected socket does not prove:

- authentication;
- subscription;
- first event;
- sequence continuity;
- fresh data;
- broker order health;
- browser projection currency.

## Broker session

States:

    DISCONNECTED
    AUTHENTICATING
    CONNECTING
    CONNECTED
    HEALTHY
    STALE
    RECONNECTING
    COOLDOWN
    AUTH_FAILED
    FAILED
    REQUESTED_STOP

Transitions:

| From | Event | To | Required fact |
| --- | --- | --- | --- |
| DISCONNECTED | start | AUTHENTICATING | connection identity and current credential source |
| AUTHENTICATING | accepted | CONNECTING | authenticated session receipt |
| AUTHENTICATING | rejected | AUTH_FAILED | bounded provider reason |
| CONNECTING | socket open | CONNECTED | transport generation |
| CONNECTED | first accepted provider message | HEALTHY | source time and receive time |
| HEALTHY | freshness budget exceeded | STALE | last accepted message |
| HEALTHY or STALE | transport close | RECONNECTING | reason and attempt |
| RECONNECTING | retry budget delay | COOLDOWN | next attempt time |
| COOLDOWN | timer | AUTHENTICATING or CONNECTING | credential policy |
| any active | operator stop | REQUESTED_STOP | actor and command |
| REQUESTED_STOP | closed | DISCONNECTED | close receipt |

An intentional disconnect never fights an automatic reconnect.

## Market subscription

States:

    DESIRED
    SUBSCRIBE_PENDING
    SUBSCRIBE_SENT
    ACKNOWLEDGED
    AWAITING_FIRST_EVENT
    HEALTHY
    STALE
    GAP_DETECTED
    RESYNCING
    UNSUBSCRIBE_PENDING
    REMOVED
    REFUSED

The desired set is durable policy. The actual set is provider observation.

Each subscription records:

- owner and provider product;
- canonical instrument;
- provider alias and effective interval;
- field and depth;
- cadence;
- priority;
- reason: protection, live strategy, paper, research, or UI;
- request generation;
- acknowledgement;
- first and last event;
- sequence or gap state;
- current cost and quota.

Priority order:

1. existing-position protection;
2. order and account reconciliation;
3. live execution inputs;
4. paper;
5. interactive research;
6. discovery and ranking;
7. UI-only analytics.

## Dynamic option window

When the center changes:

1. calculate new desired window;
2. include a prefetch buffer;
3. subscribe missing contracts;
4. wait for acknowledgement and first acceptable event;
5. switch evaluation dependency;
6. retain held-position contracts regardless of selector movement;
7. unsubscribe retired exploratory contracts after hysteresis.

The selector never changes held identity.

## Private order stream

States:

    DISCONNECTED
    CONNECTING
    AUTHENTICATED
    SNAPSHOT_PENDING
    RECONCILING
    HEALTHY
    STALE
    RECOVERING
    BLOCKED

The stream is healthy only after:

- authentication;
- current orders and positions snapshot;
- replay or deduplication of received events;
- local intent reconciliation;
- sequence gap decision.

A market-data stream may be healthy while the private order stream is not.

## Internal stream and outbox

The durable event path uses:

    LOCAL_TRANSACTION
      → OUTBOX_COMMITTED
      → CLAIMED
      → EFFECT_APPLIED
      → CURSOR_ACKNOWLEDGED

Crash after effect but before acknowledgement may repeat the event. Every consumer remains idempotent.

High-volume market ticks may use a non-durable coalescing channel. Trading-critical commands, order events, fills, reservations, and authority changes do not.

## Browser connection

States:

    DISCONNECTED
    CONNECTING
    CONNECTED
    AUTHENTICATED
    SUBSCRIBED
    SNAPSHOT_PENDING
    CURRENT
    STALE
    RESYNC_REQUIRED
    RECONNECTING
    FAILED

The current production client exposes only connected true or false. A future API should provide one closed realtime status:

- transport generation;
- authenticated organization and account scope;
- subscribed channels;
- snapshot version;
- source high-water mark;
- last update time;
- provider health;
- feed freshness;
- current resync requirement.

The frontend does not infer these values.

## Queue and overflow policy

| Event family | Capacity | Overflow |
| --- | --- | --- |
| UI state snapshots | one per type | latest wins |
| UI price ticks | bounded per instrument | sample or coalesce |
| UI logs | bounded FIFO | drop oldest with visible dropped count |
| order and fill events | durable | no silent drop |
| reservation and admission events | durable | no silent drop |
| authority and credential events | durable | no silent drop |
| research progress | bounded durable or coalesced projection | final receipt never drops |

Every queue exports depth, age, dropped count, and oldest item age without owner labels in metrics.

## Error taxonomy

| Error | State effect |
| --- | --- |
| auth rejected | AUTH_FAILED; no automatic credential guessing |
| entitlement missing | REFUSED for exact capability |
| subscription quota | REFUSED or lower-priority eviction under reviewed policy |
| missing first event | AWAITING_FIRST_EVENT then STALE |
| sequence gap | GAP_DETECTED then RESYNCING |
| slow browser | evict browser only |
| malformed provider payload | quarantine and mark source degraded |
| provider semantic change | capability change Level 2 or 3 |
| private stream loss | block new orders and reconcile |
| market stream loss with open position | highest-severity protection path |

## Required tests

1. Socket open without authentication.
2. Authentication succeeds, subscription never acknowledges.
3. Acknowledgement arrives, first event never arrives.
4. First event arrives, then feed becomes stale.
5. Sequence gap after reconnect.
6. Intentional stop during reconnect.
7. Market stream healthy, private stream stale.
8. Slow browser cannot delay engine.
9. Coalesced UI ticks report dropped count.
10. Order events never use a coalescing queue.
11. Held-position subscription survives Universe removal.
12. Option-window change subscribes before it drops.
13. Provider alias changes during reconnect.
14. Browser reconnect requires snapshot resync.
15. Tenant cannot subscribe to another account.

## Deployment impact

Compatible when limited to API and UI truth. Dynamic provider subscriptions and new service roles are architecture-changing and belong to V2.
