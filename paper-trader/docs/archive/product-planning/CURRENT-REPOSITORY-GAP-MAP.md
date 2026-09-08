# Strategy OS current repository gap map

Date: 24 August 2026
Baseline: current dirty worktree at `de6faae3e97cf5537338bee2143350e53f70da1c`

This map separates code that exists from contracts that are only documented. `PARTIAL` never means release-ready. The detailed read-only audit is `.agent/runs/programme-rebase-2026-08-24/object_runtime_gap_audit/report.md`.

## Foundation and current product objects

| Requirement | State | Exact repository evidence | Required disposition |
| --- | --- | --- | --- |
| Strategy/project/draft/immutable revision | `EXISTS` | `backend/app/db/models.py` `Project`, `GraphArtifact`, `GraphVersion`, `IrV2GraphVersion`, `StrategyAdmission`; publication/API and v2 round-trip tests. | Extend product metadata by exact references. Do not create another strategy identity. |
| One IR/registry/validator/resolver/hash | `EXISTS` | `backend/app/ir/schema.py`, `registry.py`, `resolve.py`, `runtime.py`, `hashing.py`. | Keep. All temporal, Universe and chart-semantic computation uses this family. |
| Operational v2 runtime/catalogue | `PARTIAL` | v2 grammar and resolver exist; production registry has v1 contributors only; `backend/app/ir/v2_graph_versions.py` ends at `V2_RUNTIME_UNAVAILABLE`. | Close existing graph attribution and runtime capsules, then populate one catalogue. |
| Named instrument roles | `PARTIAL` | `backend/app/market_data/requirements.py` carries role/type and data requirements; no durable role/binding-input object. | Extend `DataRequirementPlan`; add role/cardinality/binding requirement in revised Phase 6. |
| Deployment and exact paper/shadow graph binding | `PARTIAL` | `backend/app/db/models.py` `Deployment`, `IrPaperDeployment`, `IrShadowDeployment`; `backend/app/core/execution_binding.py`; attribution tests. | Preserve Deployment root; add exact Universe/product/provider/coherence/latency/reservation references. |
| Research approval/admission | `EXISTS` | `PromotionCandidate`, `research_read`, ADR 0013, paper authority activation/reload. | Keep immutable admission semantics. Do not reuse it as trade proposal approval. |
| Signal and execution authority separation | `EXISTS` | `execution_binding.py`, `paper_authority.py`, paper/live grants and tests. | Extend with proposal and pre-execution revalidation before authority. |
| Evidence/receipts | `PARTIAL` | Strategy/research admissions, dataset creation evidence, outbox receipts, experiments/findings. | Add one reconstruction binder/export after new identities exist; do not create another ledger. |

## Core defects that precede dependent work

| Defect | State | Exact evidence | Required owner |
| --- | --- | --- | --- |
| 71-character graph address routed toward 64-character strategy-version fields | `CONTRADICTED` | `IrV2GraphVersion.graph_address` versus `Deployment`, `ExecutionIntent` and `Position.strategy_version` in `backend/app/db/models.py`. | Existing `phase5-graph-paper-attribution-schema`; no v2 money consumer first. |
| Mutable generated-strategy row overwrites executable history | `CONTRADICTED` | `backend/app/db/models.py` `GeneratedStrategy`; research generated model/upsert. | Existing `phase6-generated-strategy-version-lineage`, re-sequenced under revised programme. |
| Mutable watchlist can remain a deployment input | `CONTRADICTED` | `Deployment.watchlist_id`, `WatchlistMembership`, `backend/app/core/watchlists.py`. | Immutable static scope/snapshot before Dynamic Watchlists. |
| Operational money objects still carry provider-shaped identity | `PARTIAL` | `ExecutionIntent` and `Position` instrument key/tradingsymbol/exchange; canonical Phase 4 identity exists separately. | Add nullable canonical physical address, dual-read compatibility and refusal of ambiguous backfill. |
| Execution product is mutable instrument config | `PARTIAL` | `InstrumentState.product` and runner asset branches; no immutable product policy decision. | Execution Product Policy ADR before target-position/product integration. |
| Authority/evidence facts classified as re-fetchable market state | `BLOCKED BY EXTERNAL DECISION` | `backend/app/db/planes.py` classification and unresolved loss-review comment. | Authority-fact durability ADR before retention/topology claims. |

## Expanded V1 domains

| Requirement | State | Exact repository evidence | Gap / next contract |
| --- | --- | --- | --- |
| Fixed watchlists and manual universe | `EXISTS` | `UniverseInstrument`, `UniversePreference`, `Watchlist`, `WatchlistMembership`; `watchlists.py`; tests. | Compatibility adapter only; not point-in-time Dynamic Universe authority. |
| Immutable InstrumentScope/Universe definition and snapshot | `MISSING` | No durable version/evaluation/member-snapshot authority. | Add content-addressed definition/revision/snapshot using canonical instruments. Migration required. |
| Dynamic Watchlist definition/rank/top-K/cadence | `MISSING` | Current watchlist has direct members only; `research/universe.py` reads flat set. | Add staged evaluation, stable tie-breaks, immutable snapshots and candidate decisions. |
| Hysteresis/residency/cooldown/open-position leave policy | `MISSING` | No corresponding durable policy or receipt. | Add to Universe definition identity and execution snapshot behavior. |
| Point-in-time market cap/free float/industry/listing | `MISSING` | Phase 4 rulebook is extensible; no bounded schemas or revision history. | New point-in-time rule/reference schemas plus BYOD/provider ingestion. |
| Earnings/corporate/economic events | `PARTIAL` | `EarningsEvent` is an informational mutable cache; `event_risk.py` has static blackout rules. | Append-only event facts with publication/effective/revision/source identity; projection may remain mutable. |
| Temporal routing | `PARTIAL` | v2 `temporal` family; generated `time_of_day` and session blocks; static weekday rules. | Generic weekday/month/quarter/session/DTE/event-relative/calendar-router catalogue. |
| ResourcePlan and physical resource policy | `MISSING` | Resolver safety ceilings and job concurrency exist; no `resource-plan/1`, calibration or tier decision. | Implement accepted Phase 5 resource contract in revised Phase 6. |
| Durable node-state snapshot/reset | `MISSING` | Streaming reference state is process-local; job checkpoints are not node semantic state. | Add immutable state snapshot and canonical reset schedule. |
| OFF/WARM/ACTIVE/COOLDOWN/DATA_READY | `MISSING` | Deployment/paper/shadow lifecycles exist but are different authority states. | Explicit activation descriptor, readiness barrier, runtime state and receipts. |
| Shared subscriptions/calculations | `PARTIAL` | Data requirements and current adapter fan-out provide seams; no cross-process planner. | Derived resource/runtime plan; preserve tenant/data-licence boundary. |
| Redis adoption | `SAFE TO DEFER` | No required shared-state ceiling has been measured. | Keep an interface; decide only after capacity evidence and recovery tests. |
| Data/execution provider separation | `EXISTS` | `providers/capabilities.py`, `connection.py`, `instrument_resolver.py`; split-routing tests. | Complete exact connected-provider preflight and remove legacy provider-derived execution default on new paths. |
| Provider capability matrix | `PARTIAL` | Phase 4 data capability facts plus adapter capability doctrine. | Compile exact node/deployment requirements against current provider product/contract and mode. |
| PriceCoherencePolicy | `MISSING` | Split routing exists; no dual-price comparable-field, divergence or receipt code. | Critical ADR, policy, durable receipt, `DATA_DIVERGENT`, entry block and exit-safe behavior. |
| Latency instrumentation | `PARTIAL` | Data age/skew, signal staleness, decision time/price and fill slippage exist. | Add receive/evaluate/admit/submit/ack/fill timestamps and calibrated policy. |
| Live eligibility classes/order-action limits | `MISSING` | No compiled reaction horizon, action/turnover budget or queue-sensitivity decision. | Add bar-close/second-scale/research-only/unsupported classification from measured facts. |
| Execution Product Policy | `PARTIAL` | Order execution policy exists; asset-product selection is distributed in mutable config/runner branches. | New immutable policy and resolved decision. Broad options remains V1.5. |
| Sizing hierarchy | `PARTIAL` | Equity/futures sizing functions and allocation config exist. | Normalize fixed, capital, equity, risk, stop-distance, volatility and caps into versioned policy/decision. |
| Target-position/campaign/tranche identity | `MISSING` | `Position` is one mutable aggregate; reinforcement counters and partial close exist. | Add target request, campaign and immutable tranche/fill allocation seam; no inferred historical tranches. |
| Deterministic simultaneous admission | `PARTIAL` | `backend/app/engine/allocator.py` gives a deterministic in-memory priority subset. | Freeze candidate set/policy/rank in durable `DecisionBatch`. |
| Transactional capital reservation | `MISSING` | `CapitalState` aggregate and account lease exist; no reservation lifecycle. | Add account/fence-scoped reservation transaction, recovery and reconciliation. |
| Chart renderer | `EXISTS` | `frontend/src/components/Charts.tsx`, `lightweight-charts ~4.2.0`. | Display helper only; not a drawing engine/provider adapter. |
| Chart workspace/provider adapter | `MISSING` | No workspace identity, vendor version/capability, save/load or adapter port. | Conditional Advanced Charts adapter after external gate; visual-only phase first. |
| Vendor layout/drawing persistence | `MISSING` | Graph layout persistence is a reusable precedent, not chart persistence. | Separate opaque vendor layout/drawing artifacts with owner/version/tombstone/recovery rules. |
| Normalized semantic annotations | `MISSING` | No PriceLevel/Zone/TrendLine/TimeWindow domain objects. | Allowlisted server normalization; vendor visual fields never enter IR identity. |
| Operator Thesis | `MISSING` | Journal has client-side free-text thesis only; not canonical or authoritative. | New immutable revision/lifecycle with instrument/timeframe/provider/data/bias/invalidation/TTL/bindings. |
| Expiring trade proposal and approval | `MISSING` | Research candidate decision exists; notification/Telegram alerts exist. | Separate proposal/approval/expiry/revalidation facts and single-use idempotency. |
| Forward chart evidence | `MISSING` | Paper/shadow and evidence primitives exist separately. | Bind exact thesis/proposal/approval/paper/post-trade receipts; no general historical annotation test. |

## Frontend and operational gaps

| Requirement | State | Evidence | Gap |
| --- | --- | --- | --- |
| One application shell | `EXISTS` | `frontend/src/App.tsx`. | Flat tabs; no project/Strategy-local context. |
| Central REST transport | `PARTIAL` | `frontend/src/lib/api.ts`; journal has independent fetch path. | Consolidate response/refusal handling before new chart client. |
| One authenticated resumable WebSocket | `CONTRADICTED` | `LiveContext.tsx` opens `/ws`; `WatchlistView.tsx` opens `/ws/instrument/{key}`; both put token in URL while backend requires first-frame auth. | Correct before chart feature work; implement cursor/resync and separate transport from health. |
| Backend execution cockpit | `EXISTS` backend / `MISSING` frontend | `backend/app/engine/cockpit.py` and API routes; current frontend “Cockpit” is journal. | Consume one backend read model; rename surfaces clearly. |
| Strategy workspace | `PARTIAL` | Graph, research, portfolio and operational views exist separately. | Integrate after backend domain contracts freeze. |
| Dynamic Universe UI | `MISSING` | Current manual watchlist only. | Contract-first; staged reasons and immutable snapshot provenance. |
| Chart/thesis/proposal UI | `MISSING` | Current chart modal has no persistence/semantics/approval. | Owner-gated Phase 11 after Phase 9 contracts. |
| Accessibility and 390 px behavior | `PARTIAL` | Graph keyboard movement and responsive shell exist; chart semantics absent. | Structured alternative to canvas, focus/live-region/zoom/single-pointer and measured tasks. |

## Deployability and external decisions

| Requirement | State | Evidence / blocker |
| --- | --- | --- |
| Named local contracts runnable | `EXISTS` | Current direct foundation selectors exit `0`. |
| Release deployability | `MISSING` | Deployment ledger retains build/config/migration/backup/restore/service/health/security/observability/capacity/rollback gaps. |
| Production rehearsal | `MISSING` | No production-shaped complete rehearsal or current RPO/RTO. |
| TradingView access/licence | `BLOCKED BY EXTERNAL DECISION` | Restricted repositories and terms; exact agreement/public/paywall/attribution/hosting decision absent. |
| Reference/event/options/depth data rights | `BLOCKED BY EXTERNAL DECISION` | Source, point-in-time reliability, automated use, storage, display, export and cost not selected. |
| Frontend implementation | `BLOCKED BY EXTERNAL DECISION` | Repository owner gate requires explicit authorization after contracts freeze. |
| Live authority and material sizing/routing/risk/execution changes | `BLOCKED BY EXTERNAL DECISION` | Separate owner gate; this programme package grants none. |

## Classification conclusion

The expanded direction exposes six core persisted/authority defects, but none requires rebuilding Phases 1–4. Everything else is an additive object, local implementation gap, missing product surface, future seam, explicit deferral or external decision. The safe response is `KEEP + HARDEN`, then execute the revised dependency order.
