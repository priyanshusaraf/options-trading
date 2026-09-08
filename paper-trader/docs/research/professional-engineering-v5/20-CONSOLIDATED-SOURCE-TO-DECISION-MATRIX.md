# Consolidated source-to-decision matrix

| Candidate | Reachable current failure | Sources under matching assumptions | Smallest coherent response | Compatibility/migration/rollback | Release decision |
| --- | --- | --- | --- | --- | --- |
| Isolate OOS from qualification | Every legacy run qualifies on the same rows later called OOS | DSR and PBO papers; direct row-span RED | Split/seal selection boundaries before qualification, or label old/current output exploratory | New method/spec identity; never relabel old evidence; rollback disables confirmatory claim | `APPLY IN CURRENT STACK`, V0 blocker |
| Deny legacy sweep in V0 | V0 policy permits `POST /api/backtest/sweep` | Temporal/market-truth sources; NSE effective rule changes; direct policy RED | Deny both prefixes before provider/universe/queue/repository dispatch, preserve standard profile | No data migration; rollback re-enables only standard-profile compatibility | `APPLY IN CURRENT STACK`, V0 blocker |
| Bind ResourcePlan to graph research | Published graph route omits plan input/evidence | Google SRE overload; Strategy OS canonical ResourcePlan; structural RED | Reconstruct/verify one canonical plan and bind its address into spec/result/refusal | Additive evidence/address if persistence changes; old evidence remains limited | `APPLY UNDER EXISTING F03 OWNER`, V0 blocker |
| Collision-safe experiment identity | Forced distinct recipes reuse one 128-bit ID row | AWS idempotent API parameter equality; stable canonical hash principle | Compare stored canonical recipe on reuse and refuse mismatch; plan additive 256-bit address | Preserve legacy IDs/rows; no rewrite; rollback stops new-address writes | `APPLY`, V0 low-regression hardening after owner gate |
| Completed/available ordering | Constructors accept impossible ordering; current Q03 contained | SQL temporal/event-time sources | Inventory producers/forming semantics, then validate completed observations | Preserve invalid historical facts but make them inadmissible; version projection if needed | `SEAM/PROVIDER CAPTURE`, not current generic fix |
| Optimization reconstruction | Omitted population/order/stat inputs may block replay | DSR/PBO; immutable/rebuildable state sources | First reconstruct from current stored evidence; persist only irreconstructible inputs | Additive method/evidence version; old rows retain limitation | `TEST/OBSERVABILITY FIRST`, V0 hardening |
| Fix cancel/complete reducer | Full fill can remain CANCELLED | Lamport/event-ordering; Kite order/trade semantics; direct RED | Versioned terminal conflict partial order or `RECONCILIATION_REQUIRED`, raw events retained | Projection/reducer version; no raw-event rewrite | `V1 EXECUTION`, defer from V0 |
| Localize claim-race timeout | Current SQLite test fails to terminate; cause unknown | PostgreSQL locking/isolation, Jepsen histories, DBOS/Temporal recovery comparisons | Diagnose exact lock/thread path, then bounded SQLite and PostgreSQL process tests | No migration until cause is known | `BLOCKED VALIDATION`, separate active owner |
| Connected socket revocation | Future socket checks auth once | OWASP authorization/ASVS | Owner declares revocation bound; server disconnect/revalidation tests | Likely no schema change; preserve session audit | `V1 SECURITY`, owner decision |
| P0/P1 QoS | Future risk only, no current execution worker | Google SRE/AWS queue backlog; GitHub/Shopify measured-scale sources | Benchmark existing process/database resources before choosing isolation | Configuration/process boundary first; infrastructure only after trigger | `MEASURE/DEFER` |

## Component decisions

| Component | Decision now | Evidence needed to change decision |
| --- | --- | --- |
| Redis | `NOT NEEDED NOW` | Measured reconstructible hot-state latency/fan-out gap, loss/rebuild proof and operating owner. |
| Dedicated queue | `NOT NEEDED NOW` | Current PostgreSQL claims cannot meet bounded throughput/recovery after correction. |
| Temporal | `REFERENCE ONLY` | Multi-step workflows exceed current job model, service ownership and migration/rollback are accepted. |
| DBOS | `REFERENCE ONLY` | Non-money kill/restart spike beats current jobs on a named requirement without splitting authority. |
| Restate | `REJECT NOW` | Would require log server, RocksDB, Raft, partitioning and a new authority model. |
| Kafka/event bus | `REJECT NOW` | No measured event volume or independent-service topology requires it. |
| Analytics database/data lake | `REJECT NOW` | PostgreSQL/object artifacts cannot meet measured analytical workload after tuning. |
| Read replica | `DEFER` | Primary read pressure measured and named reads tolerate replica lag. |
| Sharding/pods | `DEFER` | Single supported PostgreSQL cannot meet measured CPU/storage/lock/RTO needs after simpler fixes. |
| Service extraction/Kubernetes | `DEFER` | Independent scale/failure/security ownership plus multi-deployable operating staff exist. |
| New ledger database | `REJECT NOW` | Existing PostgreSQL ledger fails a proven financial invariant after bounded correction and owner/legal gates pass. |

## Complexity outcome before implementation

```text
new deployables:               0
new stateful infrastructure:   0
new databases:                 0
new queues/event buses:        0
new production dependencies:   0
new sources of truth:          0
accepted current-stack fixes:  4 V0 candidates, each requiring an exact capsule
future-only findings:          execution conflict, socket revocation, QoS
```
