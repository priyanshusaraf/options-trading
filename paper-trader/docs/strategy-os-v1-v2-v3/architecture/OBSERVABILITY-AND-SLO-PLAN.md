# Observability and SLO plan

## Current state

Current strengths:

- readiness can fail;
- risk and signal lane heartbeats are separate;
- provider health distinguishes quote and candle failures;
- feed anomalies remain visible after repair;
- WebSocket clients have bounded queues and send timeouts;
- domain events use durable outboxes;
- account execution leases and research claims expose current holders;
- repeated errors are rate limited;
- build identity reaches health and money records.

Current gaps:

- the main log bus is process-local and memory bounded;
- no complete metrics exporter or trace context exists;
- no production alert routing is proven;
- no retained SLO or capacity evidence exists;
- browser transport health and provider freshness are not one truthful state;
- database, job, event, and subscription capacity do not share one operating view;
- release deployability and production rehearsal remain open.

## Service objectives

These are proposed V1 and V2 targets. They are not current promises.

| Service objective | Proposed indicator | Initial target |
| --- | --- | --- |
| Existing-position protection | age of risk-lane heartbeat while any position is open | 99.95 percent under 30 seconds; zero silent misses |
| Order reconciliation | oldest unresolved acknowledged or uncertain command | 99.9 percent under 60 seconds outside broker outage |
| Live input freshness | age versus each strategy requirement | 99.9 percent within declared budget; otherwise entries blocked |
| Execution command durability | prepared command lost before resolution | zero |
| Research job durability | terminal job without durable terminal receipt | zero |
| Interactive API | non-heavy request latency | p95 under 500 milliseconds on reference load |
| Graph edit | accepted or refused command response | p95 under 750 milliseconds excluding network |
| WebSocket delivery | state projection age for healthy client | p95 under 2 seconds |
| Outbox delivery | oldest healthy consumer lag | p95 under 5 seconds for control events |
| Backup currency | age of last verified generation | less than policy limit; production value owner-defined |
| Restore | successful clean-target rehearsal | required at release cadence |

Percent targets require measured denominators and exclusion rules before release. Do not put them in marketing until production evidence exists.

## Metrics

### Process and service

- uptime;
- build identity;
- role;
- restart count;
- CPU, memory, file descriptors;
- event-loop lag;
- task count;
- graceful-shutdown duration.

### Database

- pool used, available, timeout, and wait;
- transaction duration;
- deadlock and serialization retry count;
- database size and growth;
- WAL size and age;
- schema head;
- backup age;
- restore rehearsal age;
- sequence and outbox high-water.

### Research

- pending, running, completed, failed, cancelled operations;
- lease age and takeovers;
- item checkpoint age;
- trial throughput;
- cache hit;
- dataset object bytes;
- evidence finalization latency.

### Execution

- lease state and epoch changes;
- command states;
- uncertain command age;
- order and fill reconciliation age;
- open positions without current protection evidence;
- admission batch size;
- active reservation amount and age;
- rejected candidates by bounded reason class;
- risk-reducing exit latency.

### Provider and realtime

- auth state;
- reconnect attempts;
- desired and actual subscriptions;
- first-event latency;
- last-event age;
- sequence gaps;
- provider request rate and errors;
- throttling;
- browser client count;
- queue depth;
- coalesced and dropped UI frames;
- slow-client evictions.

Do not label metrics with owner, account, Strategy, instrument, order, or candidate identifiers. Use bounded logs and domain records for those details.

## Tracing

Use one correlation chain:

    request
    → Workflow command
    → research operation
    → candidate
    → admission batch
    → reservation
    → execution command
    → broker event
    → fill
    → position and money update

Trace IDs aid diagnostics. They are not domain identity or authority.

## Structured logs

Every log record should have:

- timestamp;
- level;
- event code;
- service role;
- build;
- correlation ID;
- bounded state and reason;
- safe owner or account class only when policy permits;
- error class;
- stack reference.

Never log:

- bearer;
- credential;
- ciphertext;
- strategy graph or source;
- raw broker response by default;
- private dataset values;
- full request body.

## Alerts

Critical:

- risk lane stale with open position;
- execution lease blocked;
- uncertain broker command past threshold;
- position protection unknown;
- database authority or schema head invalid;
- restore or backup verification failed.

High:

- private order stream stale;
- provider semantic change Level 2 or 3;
- reservation reconciliation required;
- outbox consumer lag past control threshold;
- research or execution database capacity near limit.

Medium:

- repeated provider reconnect;
- public market feed gap;
- research job takeover spike;
- cache or object-store growth;
- UI slow-client evictions.

An alert must name:

- what is affected;
- current risk;
- automatic action already taken;
- operator action;
- evidence link;
- suppression and recovery condition.

## Dashboards

1. Protection and execution:
   positions, protection state, lease, commands, orders, reconciliation.

2. Provider and realtime:
   auth, subscriptions, freshness, gaps, reconnects, rate limits.

3. Research:
   jobs, claims, checkpoints, trials, cache, artifacts.

4. Data and database:
   heads, pool, size, WAL, outbox, backup, restore.

5. Release:
   running build, migrations, readiness, frontend, rollback posture.

## Tool posture

- OpenTelemetry Collector: REFERENCE, then bounded adoption when trace and metric producers exist.
- Prometheus and Grafana: expected commodity choices, but adoption needs a deployment capsule.
- Do not add a collector merely to create an empty pipeline.
- Keep structured domain evidence authoritative even when traces expire.

## Tests

1. Critical alert fires when risk lane is stale with an open position.
2. Same stale state at market close still remains critical for open risk.
3. Provider outage blocks entries but not risk-reducing exits.
4. Metric labels contain no customer identifiers.
5. WebSocket log drop exposes a dropped count.
6. Outbox lag recovers and alert clears.
7. Backup age alert cannot accept an unsigned development manifest as production evidence.
8. Trace correlation loss does not break domain attribution.
9. Log redaction catches bearer and WebSocket payload.
10. Readiness cannot stay green when schema head is stale.

## Deployment impact

Architecture-changing service and configuration work. Exact future capsule: v1-observability-and-slo-foundation. It cannot claim release readiness until production-shaped evidence exists.
