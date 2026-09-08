# Current state and risk map

> **Historical inspection state.** This 22 August map is retained as repository evidence. Its active-stage statements and deferrals of Dynamic Watchlists, bounded non-OHLCV reference/events and chart semantics are superseded. Use [CURRENT-REPOSITORY-GAP-MAP.md](CURRENT-REPOSITORY-GAP-MAP.md) for current classifications.

## Current architecture

    Browser
      |
      | REST through the shared API client
      | one private WebSocket
      v
    FastAPI control process
      |
      +--> execution database
      |      users, projects, graph versions, layouts
      |      deployments, signals, intents, order events
      |      positions, trades, capital, connections
      |      leases, commands, execution outbox
      |
      +--> research database
      |      programmes, hypotheses, specs, runs, trials
      |      findings, candidates, research operations
      |      dataset manifests, admissions, research outbox
      |
      +--> ledger database
      |      journal snapshot, artifacts, manual fills
      |      ledger outbox
      |
      +--> research and backtest workers
      |
      +--> one fenced execution holder per broker account
              |
              +--> market-data provider
              +--> execution venue
              +--> broker account reconciliation

The current application combines several logical planes in the execution database while research and journal storage already have separate physical authorities. The deployment ledger correctly rejects release and production claims.

## Component map

| Component | Owner and authority | Process and scaling | Persistence and recovery | Health and failure consequence |
| --- | --- | --- | --- | --- |
| Browser shell | presentation only | one React app per browser | local presentation plus server facts | Current client reports socket connected, but does not model full feed health |
| API/control plane | server request authority | FastAPI process | durable database writes and outboxes | Readiness checks database and engine lanes; several later production checks remain open |
| Component IR | repository and immutable graph records | pure validation, resolution, and evaluation calls | graph versions, admissions, registry snapshots | Refuses unknown format, component, body, or stale identity |
| Research plane | research database | durable operation claims and bounded workers | item checkpoints, runs, trials, findings, outbox | Can reclaim expired work; generic Workflow orchestration is absent |
| Market data | provider adapter and Phase 4 authority facts | current engine polls candles; richer authority is data driven | raw, normalized, manifest, truth, and capability facts | Unknown, stale, invalid, and unavailable facts fail closed |
| Execution control | account lease and epoch | one current actor per broker account | lease, command journal, execution intent, immutable order events | Stale actors are fenced; broker-side requests already sent still require reconciliation |
| Portfolio admission | EngineRunner and allocator | in-process batch per scan | logs only before intent creation | No durable decision batch or capital reservation |
| Deployment | deployment service | current runner scans active bindings | deployment row plus admission address | Static watchlist membership can change below a deployment |
| WebSocket fan-out | WSManager | one sender task per client | no durable browser offset for ordinary live frames | Slow clients are evicted; state frames coalesce; logs are bounded |
| Provider registry | broker registry and adapters | process data provider plus execution connection | connection rows and encrypted credentials | Supported versus planned is explicit; five-broker V1 coverage is incomplete |
| Observability | in-process log bus, health, readiness, outbox metrics | process-local plus HTTP | bounded memory logs and durable domain events | No complete production metrics, SLO, retention, or alert stack |

## Implementation state by memo area

| Area | State | Source-backed finding |
| --- | --- | --- |
| Strategy definition and immutable graph | IMPLEMENTED BUT INSUFFICIENTLY PROVEN | v1 is integrated; v2 contracts and persistence exist, while the complete v2 authority path still refuses runtime |
| Static portfolio universe | PARTIAL | mutable UniverseInstrument, UniversePreference, Watchlist, and membership records exist |
| Versioned Universe definition and snapshot | ABSENT | no immutable Universe definition, evaluation, membership snapshot, or rank receipt exists |
| Cross-sectional types | CONTRACT ONLY | v2 type registry and many-input assembly can host set, map, and ranked values; no production types or components exist |
| Workflow definition and instance | ABSENT | durable research operations and deployment services exist, but no versioned end-to-end Workflow object exists |
| Deployment lifecycle | PARTIAL | draft, active, paused, and archived exist; dynamic candidate lineage and idempotent instance identity do not |
| Portfolio admission | PARTIAL | signal candidates and deterministic priority allocation exist in process |
| Capital reservation | ABSENT | no durable reservation aggregate or decision-batch receipt exists |
| Canonical physical instrument authority | IMPLEMENTED BUT INSUFFICIENTLY PROVEN | Phase 4 canonical identities and provider aliases exist; the operational Instrument still carries provider-era fields |
| Provider capability model | PARTIAL | flat adapter capabilities and rich Phase 4 data profiles exist; one composite Strategy Preflight is not release-ready |
| Five target brokers | PARTIAL | Kite and Dhan support data and execution; Upstox supports data; Groww and Angel One are planned |
| Candle replay | IMPLEMENTED BUT INSUFFICIENTLY PROVEN | replay is completed-candle only and cannot price option or futures contracts |
| General event replay | ABSENT | no shared event log covers Universe changes, external observations, or chart artifacts |
| Multi-rate runtime | CONTRACT ONLY | causal declarations, dependency topology, and an independent prefix evaluator exist; the normal runtime still walks the graph per evaluation |
| Dynamic subscriptions | ABSENT | data requirements and capability offers form an insertion point; desired and actual live subscriptions are not planned or persisted |
| Non-OHLCV product support | DEFERRED BY OWNER | generic authority concepts exist, but current V1 storage and replay payloads are candle shaped |
| Semantic chart artifacts | ABSENT | chart annotation snapshots and vendor adapters do not exist |
| Reconstruction receipt | PARTIAL | many required identities exist across admissions and result keys; no unified export or full independent interpreter exists |
| Three-plane deployment | IMPLEMENTED BUT INSUFFICIENTLY PROVEN | local PostgreSQL 16 evidence exists; release deployability remains rejected and production rehearsal unproven |
| Accepted visual direction | CONTRACT ONLY | the standalone prototype covers 14 surfaces and records QA; production adoption remains owner-gated |

## Fixed-instrument assumptions found

| Assumption | Current location | V2 consequence |
| --- | --- | --- |
| Current provider dump defines the backtest universe | app/backtest/universe.py | Historical membership and delistings cannot be reconstructed |
| Watchlist membership is mutable | app/core/watchlists.py and watchlist_membership | A deployment cannot prove the exact set it ran |
| One instrument belongs to at most one watchlist | WatchlistMembership primary key | Multi-stage or multi-Workflow eligibility cannot share membership |
| A watchlist binds exactly one strategy | Watchlist model | Universe and Strategy lifecycles remain collapsed |
| Runner loops over a current enabled set | EngineRunner.scan_signals and process_entries | Universe changes have no versioned event or evaluation receipt |
| Backtest run stores instruments as CSV text | BacktestRun.instruments | Large, ranked, historical Universes need a separate immutable binding |
| Execution intent represents one ENTRY in one instrument | ExecutionIntent constraint and columns | Candidate batches and atomic groups have no parent identity |
| Allocation priority comes from mutable instrument facts | app/engine/allocator.py and Instrument.priority | Replays can change if priority changes |

## Scalar and time-series assumptions found

| Assumption | Current location | Finding |
| --- | --- | --- |
| Public dataset bytes are timestamp plus five floating OHLCV values | app/backtest/dataset_store.py | V1 remains candle only by owner decision |
| Legacy dataset identity hashes five candle floats | app/backtest/identity.py | A later data domain needs a new versioned identity scheme |
| Phase 4 normalized observations contain NumericValue | app/market_data/observations.py | Numeric market fields are supported; general typed external values are not |
| Data requirement field is a closed market-field vocabulary | app/ir/registry.py | Fundamentals and events should enter through a new versioned data-domain contract |
| v2 type references are registry-defined | app/ir/formats/v2.py | Cross-sectional types can be added without a second IR |

## Risk register

| ID | Severity | Evidence class | Risk | Current control | Recommended disposition | Final priority |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | Critical | CONFIRMED DEFECT | Portfolio decisions and capital use have no durable admission or reservation fact | account single-writer lease and deterministic in-process allocator | REFACTOR before broader live concurrency or dynamic candidates | MUST FIX BEFORE DEPENDENT FEATURE WORK |
| R-02 | High | CONFIRMED DEFECT | Deployment can reference mutable watchlist membership | strategy and admission identities are pinned | REFACTOR in V1 with immutable Universe snapshot | MUST FIX BEFORE DEPENDENT FEATURE WORK |
| R-03 | High | LIKELY RISK | Dynamic candidate creation can duplicate or lose lifecycle attribution | deployment name uniqueness and execution intent IDs | REFACTOR with candidate-instance and idempotency identity | MUST FIX BEFORE DEPENDENT FEATURE WORK |
| R-04 | High | CONFIRMED DEFECT | Operational instrument path still holds provider-era symbology | Phase 4 canonical identity and resolver seam | KEEP + HARDEN in V1 | HIGH-PRIORITY HARDENING |
| R-05 | High | CONFIRMED DEFECT | Five-broker V1 target is incomplete | honest registry refusal | KEEP + HARDEN through exact adapter capsules | HIGH-PRIORITY HARDENING |
| R-06 | High | LIKELY RISK | Current-pairlist or current-provider data can create biased historical Universe replay | no Dynamic Universe backtest claim exists | DEFER product, define point-in-time Universe evidence before V2 | MUST FIX BEFORE DEPENDENT FEATURE WORK |
| R-07 | High | LIKELY RISK | A Workflow engine could bypass admission or deployment safety by writing tables | existing deployment services and authority checks | KEEP + HARDEN one command boundary | MUST FIX BEFORE DEPENDENT FEATURE WORK |
| R-08 | Medium | ALREADY SAFELY HANDLED | Cross-sectional value types could require a second language | registry-defined v2 type references and cardinality bundles | KEEP one IR and add types later | PROVEN SAFE AS IMPLEMENTED |
| R-09 | Medium | HYPOTHESIS REQUIRING TEST | Full graph recomputation may become too costly for cross-sectional V2 | dependency topology and causal contracts exist | measure first; compile a runtime plan only when V2 load justifies it | BOUNDED SPIKE REQUIRED |
| R-10 | Medium | CONFIRMED DEFECT | Browser socket connectivity can read as realtime health | backend health facts exist separately | KEEP + HARDEN client state model | HIGH-PRIORITY HARDENING |
| R-11 | Medium | CONFIRMED DEFECT | Full reconstruction claim cannot be exported or checked independently | exact identities and prefix evaluator exist | KEEP + HARDEN receipt and first-divergence tooling | HIGH-PRIORITY HARDENING |
| R-12 | Medium | ALREADY SAFELY HANDLED | Non-OHLCV scope could expand V1 | owner explicitly deferred it | DEFER to V2 | PROVEN SAFE AS IMPLEMENTED |
| R-13 | Medium | LIKELY RISK | General workflow dependency could become production infrastructure before need is proven | current durable research operations exist | require bounded DBOS, Temporal, or Restate spike before adoption | BOUNDED SPIKE REQUIRED |
| R-14 | Low | ALREADY SAFELY HANDLED | Visual redesign could discard accepted styling | standalone design prototype is explicit | preserve styling; audit interaction only | PROVEN SAFE AS IMPLEMENTED |

## What can continue safely

- Foundation critical-closure work can continue inside its active capsule.
- V1 graph, causality, research, dataset, tenancy, provider, and deployment work can continue only through their existing programme dependencies and owner gates.
- Documentation and isolated architecture review can continue without changing runtime or authority.
- V2 product implementation must not start from this directory.

## What must stop

- Any claim that current watchlists are a Dynamic Universe.
- Any claim that current in-memory allocation is durable portfolio admission.
- Any claim that a connected browser socket proves healthy market data.
- Any claim that Component IR v2 is an operational production runtime.
- Any claim that local PostgreSQL evidence makes the release deployable.
- Any attempt to add non-OHLCV V1 scope after the owner's deferral.
