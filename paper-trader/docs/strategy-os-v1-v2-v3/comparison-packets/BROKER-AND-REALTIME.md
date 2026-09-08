# Broker and realtime comparison packet

## V1 broker truth

| Broker | Data | Execution | Auth shape | Current status |
| --- | --- | --- | --- | --- |
| Zerodha Kite | yes | yes | daily OAuth | supported reference path |
| Dhan | yes | yes, with explicit protection limits | long-lived key plus client ID | supported |
| Upstox | yes | no | daily OAuth | supported data only |
| Groww | no | no | long-lived key | planned |
| Angel One | no | no | TOTP session | planned |

The registry is honest. The five-broker V1 product requirement is not complete.

## Comparison

| Source | Strong pattern | Rejection or limit |
| --- | --- | --- |
| OpenAlgo | fixed broker-adapter shape and broad operational experience | AGPL, single-user architecture, mutable control-flow product |
| pyKiteConnect | separate REST and ticker clients, desired subscription replay | vendor dictionaries, process-global callback runtime, no durable order lifecycle |
| Upstox SDK | generated endpoint types, separate market and private streams, intentional disconnect | vendor-shaped models and synchronous listener dispatch |
| Dhan SDK | broker correlation ID and separate order-update stream | SDK-owned event loops and generic response envelopes |
| CCXT | native, absent, unknown, emulated, and constrained capabilities | crypto semantics and a very broad interface |
| Hummingbot | in-flight, cached, and lost orders; startup restore | pair-string identity and distributed mutable truth |
| vn.py | request, update, fill, and venue lowering separation | process-local event bus and current-state dictionaries |
| LEAN | data subscription and brokerage are separate first-class roles | engine replacement would duplicate Strategy OS |

## Provider contract decision

Keep four roles distinct:

1. market data;
2. execution;
3. account and portfolio;
4. instrument resolution.

One connection may serve several roles. A deployment resolves each role explicitly. Shared code never branches on broker name.

The current flat adapter capability set remains a compatibility declaration. The Phase 4 CapabilityProfile and CapabilityAssessment are the stronger data-side authority. V1 Strategy Preflight should compose:

- exact strategy data requirements;
- exact connected provider profiles;
- execution-venue capability;
- instrument mappings;
- account ownership;
- protection policy;
- order-type support;
- resource plan;
- current capability evidence and expiry.

## Broker conformance contract

Each supported broker must prove:

- documented authentication flow and expiry;
- credential rotation and revocation;
- canonical instrument mapping with effective intervals;
- historical and live data field semantics;
- interval and range limits;
- public market and private order streams;
- subscription acknowledgement and first event;
- heartbeat, reconnect, and stale detection;
- rate-limit and throttling behavior;
- order placement acknowledgement;
- client and venue correlation identity;
- modify, cancel, partial fill, and late fill;
- uncertain submit reconciliation;
- postback and polling convergence;
- margin query semantics;
- protection survival and explicit refusal;
- restart recovery;
- raw payload containment;
- no cross-owner or cross-account use.

## Broker connection state machine

    DISCONNECTED
      → AUTHENTICATING
      → CONNECTING
      → CONNECTED
      → HEALTHY

Failure branches:

    AUTHENTICATING → AUTH_FAILED
    CONNECTING → COOLDOWN
    CONNECTED → RECONNECTING
    HEALTHY → STALE
    STALE → RECONNECTING
    any active state → REQUESTED_STOP → DISCONNECTED

Connected is transport state. Healthy requires an accepted authenticated session and current evidence.

## Market subscription state machine

    DESIRED
      → SUBSCRIBE_SENT
      → ACKNOWLEDGED
      → AWAITING_FIRST_EVENT
      → HEALTHY
      → STALE
      → RESYNCING

Removal:

    HEALTHY
      → UNSUBSCRIBE_SENT
      → REMOVED

Held-position and protection subscriptions outrank discovery subscriptions. The planner must subscribe replacement contracts before dropping old contracts and apply hysteresis around dynamic windows.

## Browser realtime state

Current backend fan-out is strong:

- per-tenant channels;
- one sender task per client;
- latest-wins state coalescing;
- bounded non-coalesced logs;
- send timeouts and eviction;
- shared serialization.

The current client reduces its transport state to connected true or false. V1 UI hardening should distinguish:

- transport connected;
- authenticated;
- subscribed;
- snapshot loaded;
- provider healthy;
- feed fresh;
- sequence gap;
- reconnecting;
- resync required;
- failed.

The backend owns these facts. The frontend must show Unknown when it lacks one.

## Provider error taxonomy

| Class | Examples | Default action |
| --- | --- | --- |
| AUTHENTICATION | expired token, revoked key | stop new work, request re-authentication |
| ENTITLEMENT | field or market unavailable | fail preflight or degrade only when policy permits |
| RATE_LIMIT | quota, burst, cooldown | bounded retry with shared backoff |
| TRANSPORT | timeout, reset, DNS | reconnect and mark stale |
| DATA_GAP | missing sequence, empty frame, correction | block dependent entries, resync |
| SEMANTIC_CHANGE | timestamp or field meaning changed | Level 2 or 3 compatibility review |
| ORDER_REJECTED | broker rejected known request | terminal decision with reason |
| ORDER_UNCERTAIN | submit outcome unknown | reconcile before retry |
| PARTIAL_FILL | some quantity filled | update exposure and reservation |
| PROVIDER_BUG | malformed or contradictory payload | quarantine payload and fail closed |

## Regression corpus

1. Reconnect restores desired subscriptions but does not claim continuity.
2. First event never arrives after acknowledgement.
3. Public stream stays healthy while private stream fails.
4. Token rotates while the process remains alive.
5. Old provider token is reused for a new instrument.
6. Broker accepts placement but response is lost.
7. Duplicate postback arrives.
8. Fill arrives after cancellation.
9. Rate limit affects data but not risk-reducing exit.
10. Capability declaration says depth exists while conformance returns none.
11. Upstox data plus Kite execution resolves the same canonical instrument through different aliases.
12. Dhan protection cannot satisfy an options requirement and preflight refuses.

## Verdict

KEEP + HARDEN the provider architecture. Finish Upstox execution, Groww, and Angel One through separate V1 conformance capsules. Do not broaden the core broker interface for logo count.
