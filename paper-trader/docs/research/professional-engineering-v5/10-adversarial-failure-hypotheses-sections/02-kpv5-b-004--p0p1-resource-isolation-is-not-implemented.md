Reference: [section index](../10-ADVERSARIAL-FAILURE-HYPOTHESES.md). Read with its scope; this is not a new assignment.

### KPV5-B-004 — P0/P1 resource isolation is not implemented

| Field | Decision |
|---|---|
| New/prior relation | Confirms future runtime-economics owner steer; not a V0 live defect. |
| Source claim/location/assumptions | Partial-failure/backpressure principles; assumes concurrent safety and research workloads. |
| Code evidence | Bounded local queues/quotas exist; no shared priority scheduler; V0 denies execution worker. |
| Failure and consequence | Research/UI saturation delays future protection or reconciliation. |
| Severity / likelihood / reachability | Critical future consequence; zero current V0 execution reachability; likelihood requires measurement. |
| Classification / release | **RECOVERY/CAPACITY GAP**; **V1 FOUNDATION / EXECUTION**. |
| Smallest safe response / proof | Measure shared CPU/DB/pool contention and reserve capacity at existing boundaries before adding infrastructure. |
| Migration/rollback/confidence | Configuration/process isolation first; infrastructure requires separate gate. HIGH topology, LOW likelihood estimate. |

### KPV5-B-005 — active WebSocket session revocation is unspecified

| Field | Decision |
|---|---|
| New/prior relation | New bounded tenancy/session seam; V0 denial contains it. |
| Source claim/location/assumptions | Durable/volatile and observable uncertainty principles; session policy itself is repository/product authority. |
| Code evidence | Auth once in `app/api/principal.py:477-497`; loops in `app/api/routes.py:1236-1263`; no periodic revocation check. |
| Failure and consequence | Revoked/expired bearer keeps receiving private projections until disconnect. |
| Severity / likelihood / reachability | Security-relevant future path; V0 sockets denied; duration depends connection lifetime. |
| Classification / release | **MISSING INVARIANT**; **V1 FOUNDATION / EXECUTION**. |
| Smallest safe response / proof | Owner specifies revocation latency; deterministic revoke/expiry/membership-change socket tests and server disconnect signal. |
| Migration/rollback/confidence | Likely no schema migration; retain durable session audit. HIGH static gap, policy unresolved. |

### KPV5-B-006 — deterministic capital admission is not runtime authority

| Field | Decision |
|---|---|
| New/prior relation | Confirms canonical invariant and correct future staging; rejects a completeness claim. |
| Source claim/location/assumptions | Operation-specific coordination principle; assumes simultaneous admissions. |
| Code evidence | `app/execution/capital_admission.py:530-822`; no production caller of `admit_closed_batch`; recovery is paper-only. |
| Failure and consequence | A future runner bypasses reservations or cannot recover a live reservation. Current V0 cannot reach it. |
| Severity / likelihood / reachability | Critical future money seam; zero current reachability; certain integration work remains. |
| Classification / release | **ALREADY CORRECT FOUNDATION + RECOVERY GAP**; **V1 FOUNDATION / EXECUTION**. |
| Smallest safe response / proof | Integrate only under named future capsule with simultaneous contention, submit ambiguity, partial consumption, release and restart evidence. |
| Migration/rollback/confidence | Expand-contract only; feature remains disabled on rollback. HIGH. |

## Answers to the 48 adversarial questions

### Time and market truth (1-8)

| # | Answer |
|---|---|
| 1 | Several typed envelopes exist, not one universal envelope. Q03 is narrow and strict; general observation semantics differ. |
| 2 | Event, completion, availability and recorded/knowledge-cutoff concepts exist, but provider publication/correction is not carried uniformly. |
| 3 | The accepted canonical loader can reconstruct its narrow snapshot as-of a cutoff; the repository cannot make this claim for every historical query. |
| 4 | Addressed rulebook/provider/correction facts support versioning; general projection and real provider capture remain incomplete. Old evidence must not be rewritten. |
| 5 | Current Q03 requires completed bars and checks cutoff; legacy sweep/provider paths can bypass accepted authority and are V0-blocking. |
| 6 | Canonical alignment has explicit exactness/freshness rules; no universal skew policy exists for every consumer. |
| 7 | Typed validity distinguishes multiple states in canonical runtime, but all legacy/provider consumers were not proved. |
| 8 | V0 legacy sweep can use current provider universe/tokens or curated fallback, KPV5-A-003. |

### Identity and provenance (9-16)

| # | Answer |
|---|---|
| 9 | Canonical executable graph content, parameters, resolved component/implementation closure and accepted data/policy identities change executable identity. |
| 10 | Published graph provenance refuses presentation fields; layout is separate. Spec collision and missing plan identity remain. |
| 11 | Component versions and node identities are recorded in graph provenance; complete consumer proof was not rerun. |
| 12 | Data, costs, slippage, build and seed are partly bound; ResourcePlan and exact search history/stat vectors are incomplete. |
| 13 | Addressed immutable manifests prevent silent mutation in the accepted path; no universal provider/import proof. |
| 14 | Strong Phase 4 cache keys exist; complete cache-consumer audit and F03 plan identity remain open. |
| 15 | WebSocket/cache views are derived; optimization reconstruction and full restore are under-proved. |
| 16 | Provider evidence identities exist, but semantic-change invalidation across all results/deployments is not proved. |

### Transactions, concurrency, money (17-25)

| # | Answer |
|---|---|
| 17 | Capital/reservation/unresolved-work predicates, worker claims, execution lease and outbox sequence/cursor writes require database transaction/fencing protection. |
| 18 | Closed-batch admission locks a scoped head and revision; focused tests support it. It is unwired and PostgreSQL contention was unavailable. |
| 19 | No inspected money boundary uses an in-memory lock as final authority. |
| 20 | Claim/event/intent keys are durable and scoped in inspected paths; spec digest collision and broker-tag namespace remain limits. |
| 21 | One send, timeout marked uncertain, no assumed fill, later reconciliation. |
| 22 | Intent persists first; if broker acceptance precedes ack persistence, entry stays blocked and exact-tag reconciliation is attempted. |
| 23 | Exact duplicate IDs dedupe and fill regressions flag anomalies; terminal conflict KPV5-B-002 is defective. |
| 24 | Exact contract/position/campaign ownership is retained; account net quantity only guards whether a close is safe. No virtual ownership transfer found. |
| 25 | Position/tranche attribution carries strategy revision/admission/graph identity; no silent takeover was found in inspected lineage. |

### Jobs and runtime (26-34)

| # | Answer |
|---|---|
| 26 | Static predicates intend to prevent double claim/stale write, but the current first SQLite claim-race test times out. PostgreSQL failover remains unproved. |
| 27 | Backtest/research use explicit pending/running/cancelled/failed/completed and retry/reclaim predicates; exact models differ by subsystem. |
| 28 | Pinned data/engine/seed and claim facts exist, but exact search population/stat reconstruction and ResourcePlan bridge remain incomplete. |
| 29 | V0 has no live protection worker. Future P0/P1 isolation is not implemented or measured. |
| 30 | WebSocket and outbox queues are bounded; no system-wide provider/research admission proof. |
| 31 | Accepted incremental research exists; no accepted live runtime exists, so live whole-graph claim is unavailable. |
| 32 | Focused vector/prefix/stream parity foundations exist; full current suite was not rerun. |
| 33 | Accepted research snapshots reconstruct exact inputs or refuse; future live warming/recovery policy is unavailable. |
| 34 | WebSockets and caches reload or derive from durable state and are not authorities. |

### Security, tenancy, future seams (35-48)

| # | Answer |
|---|---|
| 35 | Inspected job/event/money queries carry owner and needed account scope; no repository-wide proof. |
| 36 | Logged break-glass support access was not established; no claim is made. |
| 37 | Strategy artifacts and connection/credential records are separate; no credential was read. |
| 38 | Custom nodes use declared ResourcePlan/data contracts and refusal checks; import sandbox escape was not re-audited. |
| 39 | Outbox redaction/validation exists; logs/traces were not exhaustively scanned, so privacy-safe logging is unproved. |
| 40 | Session expiry/revocation is durable for new HTTP/WS auth; active socket revocation timing is unspecified. Provider credential rotation was not exercised. |
| 41 | Current V0 datasets are narrow; IR roles/scope facts are extensible, but static legacy watchlist/provider paths remain. |
| 42 | Additive addressed Universe/InstrumentScope facts are feasible; no destructive migration is required now. |
| 43 | Signal instrument and execution product identities are separate in IR/execution foundation. |
| 44 | Position campaign/tranche lineage provides a future multi-leg/economic parent seam without changing exact child ownership. |
| 45 | No current workflow engine. A future workflow must call existing authority boundaries; no bypass is acceptable. |
| 46 | Addressed provider/data requirement/manifest facts provide a seam; data rights and exact time models remain owner/provider decisions. |
| 47 | No Dynamic Watchlist snapshot exists. V1.1 must persist definition, inputs, rank, hysteresis, lease and leave policy before claiming replay. |
| 48 | Owner/organization/account scoping supports growth, but marketplace/managed/enterprise authority is future and cannot be inferred complete. |
