# Source-of-truth and derived-state map

Date: 2026-08-31\
Rule: a fast or user-visible representation does not become authority by being convenient

## Map

| Domain fact | Authoritative producer/store | Derived or hot state | Rebuild/recovery rule | Current verdict |
| --- | --- | --- | --- | --- |
| User/organization/membership | USER-plane SQL rows and authenticated principal resolution | Request principal, browser session projection | Reload and reauthorize from durable membership/session state | CLEAN in scoped review; broad security audit separate |
| Canonical instrument | `canonical-instrument/1` bytes and authority table | Core `Instrument` projection for the bounded simulator | Reload exact address; provider token never substitutes | CLEAN |
| Provider rights/product/mapping | provider entity/product/contract/alias authority facts | Adapter lookup and request-specific mapping | Resolve temporal alias with evidence; refuse overlaps and missing rights | CLEAN structurally; conformance unverified |
| Market rulebook | `market-truth-snapshot/3` and revision records | Resolved rule at one instant | Re-run resolution at the same cutoff; never consult current state | CLEAN structurally; historical coverage unverified |
| Raw market bytes | immutable raw segment and byte digest/range | Parsed provider observation | Reload exact segment and verify range digest | CLEAN |
| Provider observation | immutable provider-observation fact | Request frame/input projection | Follow supersession and raw dependency chain at cutoff | AT RISK on time ordering |
| Normalized observation | immutable normalized fact with algorithm/policy/truth/source identities | `DataObservation`, candle row, pandas series | Reload exact inputs and transformations; correction policy must be explicit | CLEAN in Q03; general revision projection incomplete |
| Dataset | immutable segment and manifest facts in execution/research planes | `CanonicalDataset`, candle tuple, dataframe | Reload owner-scoped manifest, bytes, facts, policies, and rows; verify copied columns | CLEAN WITH NARROW SCOPE |
| Static instrument scope | immutable revision and membership address | Current named scope/head | Reopen exact revision; current head must not rewrite old evidence | CLEAN structurally |
| Authored strategy | immutable graph/version content | Draft/editor state and layout | Publish new semantic version; layout remains presentation | CLEAN |
| Registry and implementation | registry snapshot, component version, implementation closure | In-process implementation maps/cache | Reload exact closure/source or fail cold | CLEAN in inspected paths |
| Resolved graph/admission | immutable resolved identity and causal admission receipt | Runtime strategy object | Reconstruct from authored graph, registry, declarations, and admission | CLEAN; admission is not deployment authority |
| Experiment spec | immutable recipe row | Current Python recipe dict | Reopen exact canonical recipe and verify address before reuse | VIOLATED on forced collision |
| Experiment run | mutable lifecycle row plus terminal evidence | In-process stage and pending edge deltas | Failed and completed states persist; terminal evidence names recipe and results | AT RISK when spec collision or OOS claim is wrong |
| Optimization trials | immutable per-fold rows | In-memory `Trial`, performance matrix, Sharpe vector | Reconstruct exact population/statistics from stored spec/trials and build | PARTIAL / under-proven |
| Research findings/candidate | durable rows linked to evidence run | Review queues and summaries | Preserve negative/rejected trials and shadow gate; no auto-deploy | CLEAN structurally |
| Backtest cache | durable result row keyed by complete result address where Phase 4 applies | In-memory node cache and reusable result lookup | Recompute from exact data/implementation/policy; cache loss cannot erase evidence | CLEAN for Phase 4; legacy semantic coverage at risk |
| IR node cache | process-local `Cache` keyed by resolved node cache identity | Series outputs | Fresh cache per evaluation/prefix check; no durable authority | CLEAN for inspected use |
| WebSocket/UI | manager queues, browser state, view projections | Live frames, loading/stale/Unknown views | Reconnect/catch up from durable facts; frames never become business truth | V0 legacy WebSockets denied; product event stream later |
| Outbox/change events | transaction-bound plane-local change fact | PostgreSQL notification/wakeup, polling cursor | Poll durable outbox; idempotently apply; accept duplicate delivery | CLEAN in prior bounded audit |
| Paper/live orders and positions | execution/ledger SQL facts and broker reconciliation | Runner caches and broker snapshots | Separate paper/live books; reconcile external effects; exact position ownership | Outside Pass A; audited in Pass B |

## Derived-state rules

1. Every derived value names all answer-changing inputs or remains nonauthoritative.
2. A cache hit never proves the underlying authority still exists. The verified Phase 4 path reloads it before minting reusable identity.
3. Notification delivery is a wake-up, not the source fact.
4. WebSocket and browser state may be stale and must show that uncertainty.
5. A dataset update or provider correction creates new immutable evidence. It never mutates an old result in place.
6. Current universe membership, tokens, symbols, strike grids, fees, and sessions cannot reconstruct historical truth.
7. Process-local state may accelerate evaluation but cannot own money, position, strategy, or evidence truth.

## Rebuildability questions by failure

| Failure | Expected recovery | Evidence state |
| --- | --- | --- |
| Process restart during canonical data load | Reload immutable owner-scoped authorities; no provider fallback | Strong static/test evidence in Q03 path |
| Cache loss | Recompute from exact graph/data/policies | Strong for Phase 4; legacy cache may lack semantic facts |
| Notification loss | Poll durable outbox | Existing bounded tests inspected; not rerun in Pass A |
| Provider correction | Preserve old source/correction chain and create new dataset/result identity | Authority seam exists; general consumer policy incomplete |
| Spec-ID collision | Refuse mismatched stored recipe | Current implementation fails |
| Search code changes | Reconstruct old candidate population from build/spec/trials | Under-proven |
| OOS contamination | Cannot repair by relabelling; create a newly sealed confirmatory trial | Current legacy pipeline fails |
| Legacy V0 sweep | Refuse or route through canonical manifest before dispatch | Current route policy fails |

## Technologies rejected

The current database, immutable fact model, verified loader, and outbox can satisfy the named present invariants. No source establishes a need for Kafka, Redis authority, a workflow engine, universal event sourcing/CQRS, a second database, or service extraction.

Future Dynamic Watchlist hot state may use a cache only after durable snapshot/replay, measured fan-out, loss recovery, tenant isolation, and an explicit adoption gate. The current product classification is V1.5, not the retired V1.1 bucket.
