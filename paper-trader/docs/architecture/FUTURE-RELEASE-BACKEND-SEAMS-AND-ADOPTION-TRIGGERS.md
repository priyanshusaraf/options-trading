# Future-release backend seams and adoption triggers

Date: 2026-08-31
Status: architecture guidance; no implementation or deployment authority

## Release-label correction

The Chat 2 prompt used an older standalone V1.1 bucket. The accepted 29 August
scope reconciliation retires V1.1 and places Dynamic Watchlists in V1.5 alongside
bounded discovery/derivatives. This document follows the accepted V0–V6 sequence
without discarding the prompt’s requested capability analysis.

## Cross-release invariants

- One typed immutable IR, validator, resolver, hash and component registry.
- Strategy, graph, dataset, experiment, deployment, signal, order, position and
  money records remain distinct facts with exact attribution.
- Strategy OS owns canonical instruments; provider symbols/tokens are temporal
  adapter mappings.
- Market-data provider and execution broker remain separate roles.
- Research/live semantics use completed causal inputs and versioned method identity.
- Paper and live books remain separate; V0 has no public execution authority.
- Admission, requested assignment, resolved authority and observed broker truth are
  separate.
- Durable truth is authoritative; cache, runtime and realtime projections rebuild
  or expose an explicit degraded state.
- No release label, date or user count activates infrastructure or authority.

## V0 — commercial research, evidence, monitoring and alerts

| Dimension | Required contract |
| --- | --- |
| Capability | Owner-scoped projects/graphs, verified language, admitted datasets, deterministic research, robustness evidence, monitoring-only signals/alerts, auth/Test Mode billing/admin. |
| Data/point-in-time | Canonical persisted manifests, completed bars, exact availability/correction cutoff, supported contract refusal, no current-universe fallback. |
| Identity/provenance | Graph/component/build/dataset/rulebook/cost/method/seed/trial/evidence addresses; full recipe equality on reuse. |
| Runtime/state | Durable bounded research jobs, claims, cancel/reclaim, immutable evidence, explicit empty/unavailable/error states. |
| Authority/transactions | Tenant-scoped research writes; monitoring cannot reach account, capital, broker, order or position authority. |
| Security/tenancy | Server-derived owner, synthetic A/B isolation, secure sessions, redacted support/telemetry, bounded uploads. |
| Observability/recovery | Queue age/claim state/refusal reasons, deterministic reopen, three-plane backup/restore and rollback evidence. |
| Smallest seam now | Fix OOS contamination, deny legacy sweep, bind ResourcePlan, add recipe-byte collision refusal. |
| Do not build | Live execution, Dynamic Watchlists, options execution, Redis, workflow platform, service extraction, solver, marketplace or AI agents. |
| Release gate | Exact V0 capsules, current PostgreSQL validation, browser golden path, security/deployability evidence and independent review where triggered. |
| Unresolved risk | Current claim-race timeout, frontend/product acceptance, provider/data rights, restore and production-shaped evidence. |

## V1 — controlled execution and broader research/provider foundations

| Dimension | Required contract |
| --- | --- |
| Capability | Bounded paper/live paths by certified asset/provider; sizing, deterministic capital admission, provider preflight, order lifecycle, reconciliation and degraded states. |
| Data/point-in-time | Licensed historical breadth, exact forward capabilities, clock/freshness/session rules and provider semantic version. |
| Identity/provenance | Economic intent, requested/admitted target, account/broker route, request/attempt/order/trade/fill, exact position/tranche and ledger attribution. |
| Runtime/state | Single-writer/fencing, unknown-submit recovery, protection/reconciliation restart, warm/degraded states and risk-reducing exit availability. |
| Authority/transactions | One capital predicate and reservation lifecycle; no blind resend; ARM gates entries only. |
| Security/tenancy | Credential rotation, step-up/break-glass, active socket revocation, owner/account isolation and operator-safe diagnostics. |
| Observability/recovery | Unknown-order age, reconciliation lag, protection state, reservation exposure, provider disconnect and exact restore. |
| Smallest seam now | Preserve raw execution observations and reducer version, canonical capital/position identities and provider capability receipts. |
| Do not build | Broad live asset coverage, distributed workflow/bus, portfolio solver, marketplace or multi-leg campaigns. |
| Adoption trigger | Exact asset/provider path passes synthetic fault/restart, PostgreSQL contention, capacity and owner gates. |
| Unresolved risk | Broker tag/history retention, timeout ambiguity, terminal conflict semantics, actual provider conformance and live operations staffing. |

## V1.5 — Dynamic Watchlists and certified bounded single-leg index options

| Dimension | Required contract |
| --- | --- |
| Capability | Point-in-time universe definition/snapshots, filter/rank/top-K, churn/hysteresis and certified liquid index-option execution. |
| Data/point-in-time | Effective listings, strikes, tick/lot/expiry/rulebook, OI/depth/freshness/liquidity, membership snapshots and provider/data rights. |
| Identity/provenance | Definition, input snapshot, rank/tie policy, member changes, selector receipt, exact selected/held contract and leave/open-position policy. |
| Runtime/state | Bounded fan-out, evaluation budget, hot-state recovery, membership dedupe and exact held-contract exits. |
| Authority/transactions | Discovery remains non-authoritative; option execution passes V1 sizing/admission/preflight and conservative order rules. |
| Security/tenancy | Owner-scoped definitions/snapshots/subscriptions; provider entitlement and confidential strategy filters. |
| Observability/recovery | Churn, evaluation lag, dropped/refused members, subscription limits, spread/liquidity failures and rebuild receipts. |
| Smallest seam now | Generic immutable scope/snapshot/identity and exact held-instrument roles; no empty future models. |
| Do not build | Broad stock/commodity/multi-leg options execution or Redis merely for hypothetical fan-out. |
| Redis investigation trigger | Measured in-process/PostgreSQL design misses an owner-set fan-out latency/throughput objective after batching/indexing, and loss/rebuild plus cost/ownership are proven. |
| Unresolved risk | Licensed historical options/depth, provider limits, conservative fill model, churn economics and open-position leave policy. |

## V2 — active portfolio and hedge intelligence

| Dimension | Required contract |
| --- | --- |
| Capability | Sleeves, immutable portfolio/risk snapshots, feasibility, alternative hedge/mitigation candidates and human-approved proposed revisions. |
| Data/point-in-time | Cross-asset exposures, correlations/scenarios, fundamentals/events/derivatives under licensed effective-dated truth. |
| Identity/provenance | Portfolio/sleeve/risk snapshot, objective/constraints/solver/method/scenario and proposal identity. |
| Runtime/state | Deterministic diagnostics/workflows may orchestrate existing authorities but cannot mutate them silently. |
| Authority/transactions | Proposals remain non-authoritative until normal transaction-time sizing/admission/execution. |
| Security/tenancy | Portfolio/confidential-exposure isolation and consented external-signal/data flows. |
| Observability/recovery | Infeasibility explanation, stale inputs, proposal lineage and recomputation. |
| Smallest seam now | Generic exposure/risk/evidence addresses and human-approved proposal boundary. |
| Do not build | Solver service, workflow engine or diagnostics product before exact candidate/constraint demand. |
| Adoption trigger | Repeated user demand plus a proven model that existing synchronous/batch jobs cannot express or recover safely. |

## V3 — marketplace and managed allocation

| Dimension | Required contract |
| --- | --- |
| Capability | Downloadable Strategy Assets and separately governed Managed Model Allocation. |
| Prerequisites | Proven V0/V1 evidence, package rights/licences, fraud/dispute/support, versioned import/preflight and demand. |
| Identity/provenance | Author/package/version/dependencies/data rights/evidence/requirements; purchase never grants execution authority. |
| Authority/security | Operator, author, buyer/investor, custodian, broker and execution authority remain distinct. |
| Smallest seam now | Export/import manifests and provenance fields only where current V0 artifacts already need them. |
| Do not build | Marketplace schemas, payments, managed capital or AI agents in current releases. |
| Owner gates | Legal, commercial, suitability, custody, fees, conflicts, support and regulated structure. |

## V4 — certified multi-leg, institutional and fund infrastructure

| Dimension | Required contract |
| --- | --- |
| Capability | Structure-certified multi-leg `EconomicPosition` over exact existing campaigns/legs, institutional/private deployments and fund/desk tooling. |
| Identity/provenance | Exact legs/tranches/ratios, intermediate margin/exposure, partial-fill sequence and aggregate reconciliation. |
| Authority/transactions | Structure-specific admission and unwind; no reinterpretation of historical single-instrument `PositionCampaign`. |
| Security/operations | Staffed confidentiality, governance, incident, capacity and contract boundaries. |
| Smallest seam now | Reserve additive future parent identity in documentation; keep current campaign meaning frozen. |
| Do not build | Generic multi-leg engine or outside-capital/fund wrapper. |
| Owner gates | Structure order, provider combo support, operational team and legal/fiduciary form. |

## V5/V6 — enterprise treasury and market-risk OS

| Dimension | Required contract |
| --- | --- |
| Capability | Versioned business exposures/mandates, multi-entity/OTC/accounting/approval/global-jurisdiction workflows and natural mitigations. |
| Identity/provenance | Economic exposure is not a fake exchange instrument; entity, mandate, accounting, counterparty and policy facts remain explicit. |
| Authority/security | Enterprise IAM, segregation of duties, approvals, audit and jurisdiction-specific controls. |
| Smallest seam now | None beyond generic evidence/authority/exposure concepts already required earlier. |
| Do not build | ERP replacement, treasury integrations, OTC schemas or global-provider mesh. |
| Owner gates | Demand, experts, accounting/legal/regulatory decisions, data rights, funding and operating organization. |

## Technology adoption matrix

| Technology | Current decision | Exact revisit trigger | Simpler alternatives first | New failure modes |
| --- | --- | --- | --- | --- |
| Redis | `NOT NEEDED NOW` | Named hot-state/fan-out SLO fails after in-process/PostgreSQL batching/indexing and rebuild proof exists. | Process cache, database index/materialized read, subscription sharing. | Stale/evicted state, split authority, restore and cluster operations. |
| Dedicated queue | `NOT NEEDED NOW` | Corrected PostgreSQL claims cannot meet measured wait/recovery/fairness objective. | Claim indexes, bounded workers, separate pools/processes, admission. | Broker/service outage, duplicate delivery, migration and monitoring. |
| Temporal/DBOS/Restate | `REFERENCE ONLY/REJECT NOW` | Multi-step interactive workflows fail current checkpoint/recovery model and owned operations/migration exist. | Explicit job state machine, checkpoints, outbox, shorter jobs. | New authority/history, nondeterminism, control plane, retention and upgrades. |
| Read replica | `DEFER` | Sustained primary read CPU/latency exceeds objective after query/index/cache fixes and named reads tolerate lag. | Query/index corrections, bounded cache, pagination. | Replica lag, stale evidence, failover/connection routing. |
| Analytics database | `DEFER` | Analytical workload materially harms transactional SLOs after object exports/replicas. | Offline artifacts, PostgreSQL views, scheduled extracts. | Dual truth, ETL lag, retention and cost. |
| Sharding | `DEFER` | Supported single PostgreSQL cannot meet storage/CPU/lock/RTO after vertical/index/partition corrections. | Vertical scaling, archiving, partitioning, workload isolation. | Cross-shard transactions, tenant moves, restore and routing. |
| Service extraction | `DEFER` | Named subsystem needs independent scale/failure/security ownership and cross-boundary consistency is accepted. | Modular boundaries, process/pool isolation. | Network partial failure, deployment/version skew and observability. |
| Kubernetes | `DEFER` | Several independently owned deployables require scheduling/HA and staffed operations. | systemd/process manager, containers on one host, managed service. | Control-plane, networking, secrets, upgrades and incident burden. |
