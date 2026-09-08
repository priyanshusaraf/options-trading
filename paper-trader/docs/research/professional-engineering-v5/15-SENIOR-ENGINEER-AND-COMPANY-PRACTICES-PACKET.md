# Senior-engineer and company-practices packet

## Transfer rules

Company sources describe systems at different scale, staffing and failure models.
This packet adopts invariants only when a current Strategy OS failure hypothesis
exists. It rejects machinery whose operating assumptions do not transfer.

## Practices that transfer now

| Source | Actual system model | Transferable practice | Repository application |
| --- | --- | --- | --- |
| AWS idempotent APIs | Large multi-service control planes with automatic retries | Caller-scoped token, stored original parameters, duplicate mismatch refusal | Forced experiment-ID collision and future order retries require canonical-byte comparison. |
| AWS retry/backoff | Remote calls fail transiently and clients can amplify load | Deadline, bounded attempts, backoff/jitter, retry only safe operations | Provider reads/jobs may retry; unknown broker submit must reconcile. |
| Google SRE overload | Shared services with queues, retries and resource exhaustion | Test breaking point; reject/shear low-priority work before collapse | Measure research/optimization pressure before any P0/P1 QoS mechanism. |
| Stripe Ledger | Billions of heterogeneous payment events and external reports | Separate clearing, timeliness and completeness; immutable reconstruction | Add reconciliation classifications/metrics over existing order/fill/ledger facts. |
| Stripe online migrations | Hundreds of millions of live objects | Expand, compare, cut reads, cut writes, contract last | Required for any experiment-identity or evidence-schema correction. |
| Modern Treasury/TigerBeetle | Financial ledgers with pending and posted states | Balanced atomic entries, immutable posted facts, append corrections | Preserve existing Strategy OS ledger and reservation authority; add state-machine tests. |
| Zerodha Kite | OMS, exchange and postback/trade paths have distinct truth | Placement is not execution; partial trades and daily history require local custody | Unknown submit, order-history reconciliation and fill identity are mandatory for V1. |
| GitHub database partitioning | ~1.2M queries/s after years of vertical scaling | Establish virtual domains before physical partitioning | Keep plane/domain boundaries; no sharding at current scale. |
| Shopify modular monolith | Multi-million-line Rails codebase and hundreds of developers | Enforce internal boundaries; extract only for measured isolation/scale | Keep one Strategy OS backend and authority model. |
| Shopify pods | Vertical database limit already exhausted | Tenant-local failure domains after measured shared-store limits | Future trigger only; not implied by 10,000 users. |
| Uber payments | Trillion-entry/billion-entity, multi-region payment platform | Zero-sum, immutable changelog, provider reconciliation | Transfer accounting invariants only; reject Kafka/custom ledger/workflow machinery. |

## Practices that do not transfer directly

- GitHub/Shopify sharding followed measured primary-database limits and incident
  domains. Strategy OS has no comparable workload evidence.
- Uber’s Kafka, Cadence, DynamoDB and custom LedgerStore support massive payments
  scale and specialized audit requirements. They would multiply Strategy OS sources
  of truth and operational burden.
- Stripe’s federated ledger observes many independently owned payment systems.
  Strategy OS should first keep its existing order/fill/position/ledger boundaries
  coherent in one topology.
- Google/AWS multi-cluster controls assume fleet-level staffing and operations.
  Strategy OS needs simple bounded queues, capacity measurements and explicit
  degraded states before shuffle sharding or complex schedulers.

## Current implementation implications

1. Fix/contain the five Chat 1 direct RED findings inside named V0/V1 owners.
2. Keep current PostgreSQL-backed jobs and database outbox while testing claim
   termination, restart, queue age and reconstruction.
3. Add no deployable, database, queue, cache or workflow engine.
4. Treat provider transport success, OMS acknowledgement, exchange order, trade,
   position and accounting as distinct observations.
5. Prefer explicit schema/domain boundaries now so future extraction remains
   possible without implementing extraction.

## Adoption triggers

| Technology | Revisit only when |
| --- | --- |
| Read replica | Measured read workload saturates primary after query/index/cache correction, and replica staleness is acceptable for named reads. |
| Sharding/pods | A single supported PostgreSQL deployment cannot meet measured storage/CPU/lock/RTO requirements and tenant/domain keys are already isolated. |
| Dedicated queue/workflow | Current claims, leases, cancellation, checkpoints and recovery fail a named requirement after bounded correction; operating owner and migration exist. |
| Redis | A measured reconstructible hot-state latency/fan-out target cannot be met in-process/PostgreSQL and loss/rebuild behavior is proven. |
| Service extraction | A subsystem needs independent scaling/failure/security ownership and cross-boundary consistency is explicitly modeled. |
| Kubernetes | Multiple owned deployables and scheduling/availability needs exceed simpler host/process deployment, with staffing and incident evidence. |
