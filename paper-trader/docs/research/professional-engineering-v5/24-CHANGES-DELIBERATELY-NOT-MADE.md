# Changes deliberately not made

## Product fixes not made without a capsule

| Candidate | Why not changed here | Required next authority |
| --- | --- | --- |
| OOS selection isolation | Critical research behavior, method/evidence identity and old-result labeling need one coherent correction. Current path is concurrently dirty. | New V0 research-validity correction capsule and review. |
| V0 legacy sweep denial | Shared release-profile/API boundary is concurrently owned and must preserve standard-profile compatibility. | New release-profile/backtest correction capsule. |
| ResourcePlan bridge | Accepted F03 inputs are protected and have an existing named owner. | Separate F03 correction lineage with exact protected hashes. |
| Recipe collision guard/address | Equality guard is small, but full-address migration may affect persisted identity and old readers. | Identity/persistence capsule; migration-safety review if schema changes. |
| Claim-race timeout | Root cause is unknown and another task owns inherited concurrency bytes. | Diagnose/localize under active owner before any code/test change. |
| Terminal execution conflict | V1 money/execution boundary is denied in V0 and requires raw-event/projection migration policy. | V1 execution capsule and integrated critical review. |
| Observation availability ordering | Current Q03 is contained; producer/forming-state inventory is incomplete. | Provider/market-truth capsule before capture expansion. |

## Technologies rejected now

| Technology/refactor | Decision | Revisit trigger |
| --- | --- | --- |
| Kafka/event bus | `REJECT` | Multiple owned services and measured event/recovery needs exceed the database outbox. |
| Redis authority/cache | `REJECT NOW` | Named reconstructible hot-state path misses measured SLO after simpler fixes; loss/rebuild is proven. |
| Temporal | `REFERENCE ONLY` | Current job/checkpoint model fails an accepted multi-step requirement and service ownership exists. |
| DBOS | `REFERENCE ONLY` | Bounded non-money kill/restart spike shows a material advantage over corrected current jobs. |
| Restate | `REJECT NOW` | Log server, RocksDB, Raft, partitioning and authority migration all pass the component gate. |
| New financial database | `REJECT` | PostgreSQL ledger fails a proven invariant after bounded correction and owner/legal gates. |
| Generic bitemporal database | `REJECT` | Explicit time/version rows cannot meet a proven current query/correction need. |
| Analytics database/data lake | `REJECT NOW` | Analytical load materially harms transactional SLOs after extracts/replicas. |
| Read replica | `DEFER` | Named read SLO and sustained primary pressure cross the scale trigger. |
| Sharding/pods | `DEFER` | Single supported PostgreSQL fails capacity/RTO after vertical/index/partition corrections. |
| Microservices | `DEFER` | A subsystem needs independent scale/failure/security ownership with accepted consistency. |
| Kubernetes | `DEFER` | Several deployables and staffed platform/on-call ownership exist. |
| Repository-wide event sourcing/CQRS | `REJECT` | No current failure needs duplicate read/write models or universal logs. |
| CRDT/local-first collaboration | `REJECT` | Executable graph conflicts need refusal/versioning; current server authority is intentional. |
| Formal proof platform | `DEFER` | State-machine/property/concurrency tests cannot cover a named critical invariant and tool ownership exists. |
| New language/runtime or rewrite | `REJECT` | Profiling proves the runtime is the dominant cost and bounded optimization cannot meet it. |

## Future products deliberately not built

- Dynamic Watchlists and opportunity discovery: V1.5.
- Certified bounded single-leg index-options execution: V1.5.
- Active Portfolio and hedge intelligence: V2.
- Strategy Asset Marketplace and Managed Model Allocation: V3.
- Certified multi-leg/institutional/fund infrastructure: V4.
- Enterprise treasury and market-risk OS: V5/V6.

Only identity, evidence, authority, exposure and ownership seams already needed by
current releases were documented. No empty future domain model was created.

## External actions not taken

- No provider, broker, paid data, customer account, credential, VPS or production
  environment was contacted.
- No dependency, repository, package, service, plan or cloud resource was installed
  or purchased.
- No legal, regulatory, commercial, data-rights or pricing decision was assumed.
- No deployment, migration, backup, restore or live order was performed.
