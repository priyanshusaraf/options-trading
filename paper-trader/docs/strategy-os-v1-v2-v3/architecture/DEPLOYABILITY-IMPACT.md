# Deployability impact

> **Ownership update.** The deployment obligations remain valid, but rows labelled V2 Dynamic Universe, non-OHLCV or chart artifacts now belong to revised V1 Phases 7–9 for their bounded surfaces. Use the revised mapper for exact owners.

## Current verdict

| Evidence level | Verdict |
| --- | --- |
| locally runnable | proven only for the named local contracts in the deployability ledger |
| release deployable | rejected and open |
| production rehearsed | unproven |
| deployed | not authorized for the current dirty tree |

This documentation slice has deployment impact: none.

It changes no runtime, schema, migration, configuration, dependency, service, provider, infrastructure, frontend, credential, production, live authority, order path, or money behavior.

## Recommendation impact matrix

| Recommendation | Impact | Affected deployment dimensions | Required future evidence | Exact proposed capsule |
| --- | --- | --- | --- | --- |
| Immutable static Universe binding | migration-required | migrations, backup, restore, health, rollback | empty install, current upgrade, legacy compatibility, clean restore | v1-static-universe-version-binding |
| Candidate-instance lineage | migration-required | migrations, retention, privacy, projections | owner isolation, exact attribution, old-row null compatibility | v1-dynamic-candidate-lineage |
| Portfolio admission and reservations | architecture-changing and migration-required | money schema, services, concurrency, health, observability, rollback | PostgreSQL account lock, crash recovery, broker uncertainty, critical review | v1-portfolio-admission-reservation |
| Workflow command boundary | compatible or migration-required | service role, job recovery, health | duplicate, retry, cancel, restart, stale approval | v1-workflow-invocation-boundary |
| Canonical instrument operational binding | architecture-changing and migration-required | schema, providers, migrations, data cutover | mapping parity, token reuse, held identity, rollback | v1-canonical-instrument-operational-binding |
| Upstox execution | architecture-changing | dependency, provider, credential, network, health | official API conformance, restart, rate limit, protection | v1-upstox-execution-conformance |
| Groww support | architecture-changing | same as above | exact current docs, auth, data, execution, mapping | v1-groww-provider-and-execution-conformance |
| Angel One support | architecture-changing | same as above | TOTP secret, session, data, execution, mapping | v1-angelone-provider-and-execution-conformance |
| Reconstruction receipt | compatible or migration-required | artifacts, storage, retention, licence | export rehash, independent runner, licence gate | v1-reconstruction-receipt-export |
| Realtime client state | compatible | API, frontend, health | desktop, 390 px, reconnect, stale, unknown | v1-realtime-health-state-contract |
| Observability foundation | architecture-changing service and config | build, services, health, security, retention | production-shaped metrics, alerts, no customer labels | v1-observability-and-slo-foundation |
| V2 cross-sectional types | compatible registry extension until persistence changes | build, runtime, test | exact types, deterministic order, parity | v2-cross-sectional-type-pack |
| V2 Dynamic Universe | architecture-changing and migration-required | services, data, storage, capacity, provider | point-in-time replay, budgets, subscriptions, load | v2-dynamic-universe-engine |
| V2 Workflow templates | architecture-changing and migration-required | services, queues, migrations, health | durable step and command recovery | v2-workflow-templates |
| V2 non-OHLCV data | architecture-changing and migration-required | schemas, data rights, storage, providers, capacity | point-in-time revision, replay, export licence | v2-external-data-domains |
| V2 chart artifacts | architecture-changing and licence-sensitive | frontend dependency, storage, security, vendor licence | immutable artifact, adapter, commercial licence gate | v2-chart-thesis-artifacts |

## Build obligations

Future implementation slices must:

- pin backend and frontend dependencies;
- preserve exact build identity;
- produce reproducible artifacts;
- include component and implementation closure where semantics change;
- record third-party notices;
- reject a dirty deployment tree.

## Configuration obligations

New features must use:

- environment or secret-store credentials;
- closed settings with safe defaults;
- explicit service roles;
- production refusal for mock or SQLite ambiguity;
- feature flags only for unfinished non-authoritative capability;
- no flag that weakens live money safety.

## Migration obligations

Each schema slice must:

- use an explicit migration;
- query and record actual heads;
- prove empty install;
- prove every supported upgrade start;
- refuse unsupported and partial states before writes;
- preserve legacy rows and money attribution;
- prove restart;
- exercise downgrade or restore-based rollback;
- update backup and restore manifests;
- keep model and migration schemas equal.

The active foundation gate makes prior research migration support claims stale. No new capsule may rely on them until closure.

## Service obligations

Potential new roles:

- Universe evaluator;
- Workflow coordinator;
- subscription planner;
- observability collector.

Do not create a separate service until one process role can no longer meet measured isolation, recovery, or capacity requirements.

Each role needs:

- dependency order;
- lease or single-writer rule;
- startup validation;
- readiness and liveness;
- graceful drain;
- restart and takeover;
- resource budget;
- structured diagnostics.

## Security obligations

- no static credentials;
- exact owner and account scope;
- TLS and network exposure plan;
- least-privilege database roles;
- secret rotation;
- audit for consequential commands;
- support access policy;
- dependency and image inventory;
- strategy-content privacy;
- external-data licence and permitted-use enforcement.

## Capacity obligations

Before Dynamic Universe or multi-rate runtime:

- measure symbols and fields per user;
- provider subscription limits;
- event rate;
- node evaluations;
- CPU and memory;
- database connections;
- queue depth;
- cache and object growth;
- research contention with live lanes;
- degradation order.

P0 protection and reconciliation must retain priority under every load test.

## Rollout and rollback

Money and authority changes use:

1. architecture acceptance;
2. schema-only or shadow facts;
3. paper evidence;
4. exact parity with current behavior;
5. controlled activation behind owner gate;
6. observation;
7. independent critical review where required;
8. release review;
9. separate deployment approval.

If a new authority has committed broker or money effects, rollback means forward reconciliation. It never means deleting facts or reverse-copying ambiguous state.

## Current open dimensions

The current deployability ledger assigns these homes:

- Phase 5: reproducible research workers, queues, cache, artifact storage.
- Phase 6: deployment binding, configuration, preflight, health, service topology.
- Phase 7: CPU, memory, disk, database, subscription, queue, latency, and cost capacity.
- Phase 8: truthful operator preflight, degradation, recovery, and error UX.
- Phase 9: provider credentials, network behavior, capability drift, fallback.
- Phase 10: tenant operations, retention, support, audit, runbooks.
- V1 release: clean production-shaped install, upgrade, backup, restore, rollback, security, observability, capacity, and exact-build smoke.

This plan does not move any obligation to a vague later phase.
