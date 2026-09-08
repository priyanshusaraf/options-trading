# Scale 50 to 10,000: workload envelopes and measured triggers

Date: 2026-08-31
Status: planning hypotheses, not production capacity or pricing commitments

## Method

User count alone says little about load. The envelopes below give measurement
scenarios for a research-heavy product. They are not forecasts or entitlements.
Actual admission uses the canonical `ResourcePlan`, provider limits and measured
hardware/calibration identities.

Assumptions for one planning profile:

- 5–20 authored strategy versions per user;
- 5–20% concurrent active sessions at peak;
- 10–30% of active sessions running an interactive backtest;
- heavy optimizations admitted separately and bounded by tier/policy;
- BYOD/captured data dominates storage uncertainty;
- V0 monitoring is signal-only; execution workloads are separate V1 scenarios.

## Planning envelopes

| Registered users | Peak active sessions | Strategy versions | Concurrent interactive backtests | Heavy optimizations | Dataset/artifact envelope | Forward evaluations/events per second | Operational reading |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 50 | 3–10 | 250–1,000 | 1–3 | 0–2 | 50–500 GB | 10–200 | One modular monolith, PostgreSQL and bounded workers should be sufficient if claims/recovery pass. |
| 500 | 25–100 | 2,500–10,000 | 5–30 | 2–10 | 0.5–5 TB | 100–2,000 | Measure database pools, queue age, artifact/object storage and provider subscription sharing. |
| 2,000 | 100–400 | 10,000–40,000 | 20–120 | 8–40 | 2–20 TB | Separate worker processes/pools and object retention likely deserve investigation before services. |
| 5,000 | 250–1,000 | 25,000–100,000 | 50–300 | 20–100 | 5–50 TB | Read replicas/object-tier expansion may be investigated if transactional SLOs show pressure. |
| 10,000 | 500–2,000 | 50,000–200,000 | 100–600 | 40–200 | 10–100 TB | Domain/tenant partitioning and service extraction remain conditional on measured shared failure/scale, not automatic. |

Every range must be replaced by observed percentiles before adoption or pricing.

## Workload profiles

### Research-heavy

Measure graph compile/resolve, dataset load, evaluation CPU/memory, trial count,
artifact bytes, queue wait and deterministic reopen. Reject a result if its plan is
missing or the workload exceeds admission.

### CSV/BYOD-heavy

Measure upload bytes, decompressed bytes, row/column/cardinality, parser CPU/memory,
validation failures, deduplicated object storage, retention and backup/restore. No
upload limit follows from this document.

### Optimization-heavy

Measure population size, trial duration/distribution, checkpoints, cancellation,
reclaim, complete-trial persistence, queue fairness and resume identity. Heavy work
must not starve interactive research or future safety work.

### Signal/alert-heavy

Measure scope size, evaluation clocks, input fan-out, transitions, dedup/cooldown,
alert deliveries, unread state, WebSocket fan-out, reconnect/resync and staleness.

### Paper/live execution

Separate profile. Measure provider calls/subscriptions, admission transactions,
order/fill/postback/reconciliation rates, unknown states, protection latency and
database contention. V0 does not run this profile.

### Future Dynamic Watchlists

Measure definition count, member universe, filter/rank cost, refresh interval,
membership churn, shared inputs, subscription demand, snapshot bytes and rebuild.
Do not infer Redis from the feature name.

### Future options-chain/order-flow capture

Measure listed contracts, quote/depth rate, fields, compression, provider limits,
coverage/gaps, retention and data rights. Missing historical data remains missing.

### Future multi-strategy portfolio

Measure strategies/sleeves, risk snapshots, scenario/candidate count, feasibility,
solver time, explanation artifacts and admission conflicts. Solver infrastructure
requires a proven model and demand.

## Required measurement matrix

| Resource | Baseline and stress evidence |
| --- | --- |
| Database | CPU, I/O, storage growth, connection utilization, query p50/p95/p99, lock wait/deadlock/serialization, WAL/backup/restore time. |
| Jobs | Submitted/claimed/running/retried/cancelled/completed, queue depth/age, claim time, reclaim time, checkpoint bytes and recovery success. |
| Runtime | Evaluation/s, CPU time, RSS/heap, history/state bytes, cold/warm latency and deterministic equality. |
| Cache | Hit/miss, key cardinality, invalidation cause, rebuild time, stale refusal and authority-independent loss. |
| WebSocket | Connections, frames/s, queue depth, dropped/resync clients, encode CPU/memory and revocation latency. |
| Provider | Subscriptions, requests/s, errors/429s, reconnect, field/range entitlements, cost and shared-use rights. |
| Storage | Dataset/artifact/log/trace bytes, retention, compression, egress, backup set and restore throughput. |
| Operations | Alerts/incidents, manual reconciliations, support time, on-call staffing, failed deploy/rollback and recovery drill duration. |
| Unit economics | Measured quantities × dated approved rates, fixed/shared allocation, provider/licence/support/recovery uncertainty. |

## Investigation triggers

These are engineering investigation triggers, not live policy. An owner-set SLO may
replace them with a stricter value.

| Technology | `NOT NEEDED NOW` until this observed condition | Required evidence before `NEEDED NOW` |
| --- | --- | --- |
| Object-storage expansion | Database/artifact storage or backup duration threatens the declared RPO/RTO/retention objective. | Content-addressed upload/reopen, lifecycle, deletion, integrity, restore, egress/cost and provider review. |
| Read replica | Primary read CPU stays above 65% or named read p95 misses its SLO for 30 days after query/index/cache correction. | Exact replica-lag tolerance, routing, stale-state UI, failover and rollback. |
| Dedicated queue | p95 interactive job wait exceeds 30 seconds or p95 admitted batch wait exceeds 10 minutes at provisioned steady load after claim/index/worker tuning. | Claim/retry/cancel/fencing equivalence, migration, poison handling, restore, monitoring and owner. |
| Redis | A named reconstructible hot-state path misses its p99 latency/fan-out SLO by more than 2× after batching/indexing/process cache, at representative churn. | Complete key identity, TTL/stale policy, loss/rebuild, tenant isolation, memory ceiling, backup nonauthority, operations/cost. |
| Workflow engine | In a 1,000-run fault schedule, current job/checkpoint design cannot recover a named multi-step workflow within its objective after bounded correction. | Exact-commit/licence review, authority boundary, migration/rollback, retention, HA, observability, cost and owner approval. |
| Analytics database | Analytical queries consume over 25% of primary CPU/I/O or repeatedly violate transactional SLOs after offline extracts/read replicas. | ETL freshness/completeness, reconciliation, deletion/retention, dual-truth guard, restore, cost and owner. |
| Service extraction | One subsystem consumes over 30% of host resources or causes repeated shared-failure incidents, and independent scaling/isolation gives at least 2× headroom with accepted consistency. | API/versioning, partial failure, transactions/outbox, deployment/rollback, security, observability and staffing. |
| Sharding | Supported vertical/partitioned PostgreSQL cannot meet storage/CPU/lock/RTO objectives at forecast 2× load. | Tenant/domain key, move protocol, cross-shard prohibition/transactions, backup/restore and rollback. |
| Kubernetes | At least four independently owned deployables require different scaling/HA schedules and a staffed on-call team owns the control plane. | Cluster/security/network/storage/secret/upgrade/restore/cost/incident plan and simpler-host comparison. |

No trigger is currently proven crossed.

## Capacity test order

1. Freeze graph/data/method/calibration identities and expected outputs.
2. Measure one request/job on representative hardware.
3. Increase concurrency until the first declared SLO or resource ceiling fails.
4. Record queueing, refusal and recovery, not only successful throughput.
5. Repeat after the lowest-complexity correction.
6. Test cache loss, process restart and database contention.
7. Compare cost and operator burden.
8. Only then open a technology adoption gate.

## Pricing and cost nonclaim

This document does not set prices, quotas, subscription limits or provider plans.
Those decisions require dated costs, measured tenant distributions, support/recovery
burden, commercial approval and uncertainty analysis.
