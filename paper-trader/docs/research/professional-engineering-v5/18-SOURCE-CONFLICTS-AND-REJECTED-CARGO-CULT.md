# Source conflicts and rejected cargo cult

## Resolution method

Conflicts are resolved by source assumptions and direct repository tests, not by
reputation count. External sources may challenge an implementation but do not
change the active release or authorize infrastructure.

| Conflict | Source positions | Strategy OS evidence/model | Resolution |
| --- | --- | --- | --- |
| Serializable everywhere vs weaker contracts | PostgreSQL/Jepsen define stronger histories; Bailis shows some invariants can avoid coordination. | Money, unique identity, ownership and finalization need exact predicates; UI/outbox delivery can be at least once and rebuildable. | Coordinate named critical predicates, not the whole product. |
| Advisory locks vs row predicates | PostgreSQL permits advisory locks but makes them voluntary and bounded. | Strategy OS already stores owner/token/expiry rows. | Prefer atomic row predicates; advisory locks only for a proven awkward invariant. |
| Generic bitemporal platform vs explicit fields | Temporal literature separates valid/system time; SQL:2011 supplies temporal tables. | Strategy OS uses immutable addressed snapshots and bounded effective-time fields. | Keep explicit times/version rows. Revisit system-versioned tables only on proven query/migration pain. |
| Retry until success vs timeout ambiguity | AWS retries are effective when idempotent; broker docs separate transport/OMS/exchange truth. | Order side effects can occur before timeout. | Retry safe reads/jobs; reconcile order submits. |
| Exactly once claims | Workflow/ledger vendors use transactional checkpoints or journals; external calls remain failure boundaries. | Current jobs/outbox use database predicates; broker effects are external. | Say exactly once only for one proven local transaction. Use idempotency plus reconciliation elsewhere. |
| Temporal/DBOS/Restate adoption | Each offers durable recovery. | Temporal adds service/event history; DBOS adds checkpoint tables and distributed recovery coordination; Restate adds log server, RocksDB and Raft. | `NOT NEEDED NOW`. Keep contract lessons and measured trigger. |
| Kafka/event sourcing | Uber/Stripe use immutable streams at enormous scale. | Strategy OS has one database, bounded outbox and no measured bus bottleneck. | Reject bus and repository-wide event sourcing. Preserve specific immutable facts. |
| Redis hot state | Redis can accelerate caches/streams. | No measured Dynamic Watchlist or fan-out threshold; authority must remain reconstructible. | Reject now. Future cache only after loss/rebuild and latency evidence. |
| Microservices | GitHub/Shopify/Uber extracted or partitioned after measured scale/failure boundaries. | Current system benefits from one transaction topology and small operating team. | Keep modular monolith; preserve extraction seams without deployables. |
| Kubernetes | Large companies operate fleets and independent services. | Strategy OS has no accepted multi-service scheduling requirement. | Reject until deployable count, HA and staffing trigger exists. |
| Custom financial database | TigerBeetle/Uber stores enforce financial invariants at scale. | Existing PostgreSQL ledger/capital authorities are canonical and V0 live execution is denied. | Reference only; do not introduce a second money source of truth. |
| Formal verification tooling | Lamport/Isabelle sources improve model discipline. | Current bugs are reproducible with small state-machine and concurrency tests; no formal-tool ownership exists. | Use explicit transition tables and generative tests; defer tool adoption. |
| DSR/PBO as badges | Papers require full populations and assumptions. | Current trial reconstruction and OOS isolation are incomplete. | Refuse the labels until exact evidence is reconstructible. |
| Current contract dump as historical truth | Provider/exchange pages expose current instruments; NSE circulars change rules over time. | Point-in-time contract masters are not wired for broad derivatives. | Refuse unsupported history; capture effective-dated masters prospectively. |
| Graceful degradation by changing semantics | SRE sources allow cheaper results for suitable services. | Trading/research semantics cannot silently drop required data or switch provider. | Degrade by refusal, staleness or deferring work, never semantic substitution. |

## New-component exception result

No candidate passes all eight gates:

1. No current measured bottleneck requires a new component.
2. Existing-stack bounded corrections have not been exhausted.
3. Simpler alternatives remain available.
4. Operational ownership is not defined.
5. Migration/rollback has not been tested.
6. Licence/cost/vendor-exit/data-governance work is incomplete.
7. No adoption trigger is currently crossed.
8. No owner approval for a component exists.

Therefore:

```text
Kafka / event bus              REJECT NOW
Redis authority or cache       REJECT NOW
Temporal                       REFERENCE ONLY
DBOS                           REFERENCE ONLY; bounded future spike trigger
Restate                        REJECT NOW
new ledger database            REJECT NOW
analytics database/data lake   REJECT NOW
service extraction             DEFER UNTIL MEASURED BOUNDARY
Kubernetes                     DEFER UNTIL MULTI-DEPLOYABLE OPERATING NEED
formal proof platform          DEFER; use stateful tests first
```

## Conflicts still needing owner/provider decisions

- Required connected-session revocation latency.
- Backup/PITR/RPO/RTO objectives and deployment topology.
- Broker/provider retention, tag uniqueness and unknown-submit reconciliation
  details under each commercial contract.
- Licensed historical options/OI/depth/corporate-action sources and retention.
- Future execution P0/P1 latency and capacity targets.
- Legal/regulatory/commercial interpretation of execution, managed models and
  data redistribution.
