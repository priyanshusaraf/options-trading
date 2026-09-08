# Strategy OS contract and ADR plan

Date: 24 August 2026
Decision: `KEEP + HARDEN`

## Existing decisions to retain or amend

| Existing decision | Disposition | Required reconciliation |
| --- | --- | --- |
| Engineering ADR 0001 — product-object contract | `KEEP + HARDEN` | Preserve Project, immutable GraphVersion, research ledger and Deployment root. Add Universe, Operator Thesis, proposal and reservation as distinct facts. |
| Engineering ADR 0002 — immutable graph-version research binding | `KEEP` | Extend evidence bindings with exact Universe/reference/thesis inputs; no client-supplied identity. |
| Engineering ADR 0003 — research evidence and candidate decisions | `KEEP` | Preserve research approval; explicitly distinguish it from expiring trade proposal approval. |
| Engineering ADR 0011 — staged IR runtime adoption | `KEEP + HARDEN` | Preserve shadow → paper → owner-gated live progression and one execution path. Rebase the old stage labels under revised Phases 5–8. |
| Engineering ADR 0012 — execution-state ownership | `KEEP` | Canonical binding remains the only selection/attribution authority. New objects reference it; none writes broker orders directly. |
| Engineering ADR 0013 — research approval is admission, not lease | `KEEP` | New proposal approval is a separate short-lived, single-use fact. Do not turn research rows into a runtime kill switch. |
| Engineering ADR 0014 — SQLite until topology forces PostgreSQL | `SUPERSEDE CURRENT TOPOLOGY CLAIM` | The trigger fired and three PostgreSQL planes now exist locally. Retain its invariant analysis, but use the deployability ledger for current database truth. |
| Engineering ADR 0015 — three planes/credential home | `KEEP + AMEND` | Keep credentials in MONEY. Resolve whether accepted market-truth/evidence facts are truly re-fetchable before retention/topology claims. |
| Package ADR 0001 — preserve V1 additive foundation | `KEEP + AMEND` | Remove old timing that defers Dynamic Universes, non-OHLCV and chart artifacts wholesale. Preserve the no-rewrite/no-duplicate rule. |
| Package ADR 0002 — one IR, distinct objects | `KEEP` | Dynamic Watchlists use the existing IR for pure computation; approval and Workflow effects remain domain commands. |
| Package ADR 0003 — durable admission/reservation | `PROMOTE / IMPLEMENT IN PHASE 5` | This is the accepted capital foundation; add sizing/target-position and pending-order semantics. |
| Package ADR 0004 — domain jobs before Workflow dependency | `KEEP` | No general Workflow dependency enters V1 or the live order path. |

## ADRs required before implementation

| ID / proposed file | Decision to freeze | Why an ADR is required | Phase gate |
| --- | --- | --- | --- |
| ADR-H01 `V1-PRODUCT-OBJECT-BOUNDARIES` | Strategy, InstrumentScope/Universe, Operator Thesis, proposal/approval, Workflow context, Deployment, Execution Product Policy, admission and reservation identities | Prevents object collapse and duplicate authority. | Before new shared schemas in P5/P7/P9 |
| ADR-H02 `AUTHORITY-FACT-DURABILITY` | Which canonical instruments, provider contracts, observations, truth, datasets and capability evidence are MARKET versus USER/MONEY durability, backup and retention | Current plane classification is unresolved and data rights affect reconstructibility. | P7.1 before reference/event storage |
| ADR-H03 `EXECUTION-PRODUCT-POLICY` | Asset-neutral signal → product policy → resolved tradable instrument; policy identity, selector, liquidity/order constraints and refusal | Current product selection is mutable/distributed and future target positions depend on it. | P5 architecture; implementation before P8 preflight |
| ADR-H04 `SIZING-TARGET-POSITION-AND-RESERVATION` | Sizing hierarchy, dynamic numeric inputs, target position, pending orders, stable tie-break, DecisionBatch and CapitalReservation state machine | Money/concurrency boundary; extends package ADR 0003. | P5 before migration/implementation |
| ADR-H05 `POSITION-CAMPAIGN-TRANCHE-LINEAGE` | Operational Position aggregate versus immutable campaign, tranche, fill allocation and exact-held inventory | Prevents future additions/reductions from changing physical ownership. | P5/P8 before target-delta execution |
| ADR-H06 `POINT-IN-TIME-REFERENCE-AND-EVENTS` | Versioned schemas, publication/effective/observed times, corrections, projections, provider/BYOD source and research/live eligibility | Avoids current facts masquerading as historical truth. | P7.1 |
| ADR-H07 `DYNAMIC-WATCHLIST-STATE` | Definition revisions, evaluation attempt, stages, rank/top-K/ties, snapshots, membership events, residency/cooldown, leave policy and recovery | Dynamic Watchlists move into V1 and mutable watchlists are unsafe authority. | P7.2 before schema |
| ADR-H08 `SELECTIVITY-ACTIVATION-AND-RESOURCE-PLANNING` | Explicit activation boundary, OFF/WARM/ACTIVE/COOLDOWN/DATA_READY, readiness barrier, ResourcePlan linkage and temporal non-reordering | Ordinary conditionals cannot imply safe laziness. | P8.1 |
| ADR-H09 `HOT-STATE-RESPONSIBILITY` | In-process versus Redis/interface versus PostgreSQL/object storage, recovery and eviction | Prevents Redis fashion/adoption and financial authority drift. | P8.2 only after measurements |
| ADR-H10 `PROVIDER-PRICE-COHERENCE` | Comparable fields, signal/execution sources, mapping, age/skew/divergence, hard blocks, exit policy, degraded state and receipt | Missing Critical safety control for split routing. | P8.3 before eligible execution/preflight |
| ADR-H11 `LATENCY-AND-LIVE-ELIGIBILITY` | Timestamp chain, age budgets, reaction horizon, order-action/turnover ceilings, eligibility classes and HFT refusal | Prevents unsupported latency/live claims. | P8.4 |
| ADR-H12 `CHART-PROVIDER-ADAPTER-AND-ACCESS` | Selected product, exact access/licence gate, capabilities, asset hosting, CSP, version pin/migration and proposal-only boundary | Licence-sensitive vendor dependency. | P9.1; owner/legal/commercial decision required |
| ADR-H13 `CHART-WORKSPACE-DUAL-STORAGE` | `VendorChartArtifact` versus normalized semantics, owner/version/content identity, save/load/tombstones/groups and migration | Vendor blobs cannot be executable truth. | P9.2 |
| ADR-H14 `OPERATOR-THESIS-AND-SEMANTIC-ANNOTATIONS` | Allowlisted semantic union, geometry, instrument/timeframe/provider/data binding, lifecycle, TTL, successor behavior and position ownership | New V1 first-class executable input. | P9.3 before persistence/API |
| ADR-H15 `TRADE-PROPOSAL-APPROVAL-REVALIDATION` | Proposal/approval states, TTL, actor/reason, single use, material-address binding, revalidation and reject/expire behavior | Prevents stale human approval and avoids overloading research admission. | P9.5 |
| ADR-H16 `FORWARD-CHART-EVIDENCE` | Shadow/paper/proposal/approval/post-trade receipts, prospective datasets and replay boundary | Chart strategies need evidence without hindsight backtests. | P9/P10 |
| ADR-H17 `V1-V1.5-OPTIONS-BOUNDARY` | V1 data-input eligibility and recorder benchmarks versus V1.5 certified single-leg index-options execution | Prevents broad options execution from re-entering V1. | Before P8 product policy and P13 release claims |
| ADR-H18 `BROWSER-REALTIME-CONTRACT` | One first-frame-authenticated cursor/resync socket; transport/auth/subscription/freshness/provider health states | Current frontend/backend contract is contradicted and chart work would deepen it. | P11.1 before chart frontend |

## Minimum contract shapes

### Chart provider port

```text
ChartProviderCapabilities
  product_kind
  library_version
  single_chart_layouts
  multi_chart_layouts
  drawing_tools
  drawing_events
  separate_drawing_storage
  templates
  proposal_markers_without_trading
  csp_nonce
  same_origin_iframe
```

The port uses Strategy OS concepts, not vendor method names. Unsupported capabilities return `false`; no generic “TradingView supported” flag exists. Advanced Charts is conditional. Trading Platform broker/order methods are outside V1.

### Vendor chart artifact

```text
VendorChartArtifact
  owner / workspace
  vendor_product / exact_library_version
  canonical instrument binding + adapter symbol
  layout / chart / pane / sharing-mode identity
  opaque layout state
  opaque separate drawing/group state
  content address / created / superseded / restore status
  executable_authority = none
```

### Normalized semantic annotations

V1 executable candidates are `PriceLevel`, `PriceZone`, `TrendLine`, `Ray`, `TimeMarker`, and `TimeWindow`. Every object carries owner, canonical instrument or named role, timeframe, session/timezone/adjustment policy, chart data provider/dataset identity, finite normalized geometry, semantic kind/version, source vendor artifact/drawing references, extractor version and content address. Channel and Fibonacci remain visual-only/seam until exact spikes pass. Freehand/text/pattern tools never become semantic authority automatically.

### Operator Thesis

```text
OperatorThesis
  thesis_id / revision / owner
  canonical instrument or named role
  timeframe / session / timezone / adjustment
  chart provider / dataset / vendor artifact
  normalized semantic addresses
  directional bias / invalidation / TTL
  effective_from / expires_at / created_at / locked_at
  DRAFT / LOCKED / ACTIVE / SUPERSEDED / EXPIRED / INVALIDATED / RETIRED
  Strategy / Deployment bindings
```

Locking freezes a revision. Editing creates a successor. An open position keeps the creating revision unless a separately reviewed takeover occurs.

### Proposal and approval

```text
TradeProposal
  proposal_address / owner / account
  exact Strategy / thesis / Universe / provider / market snapshot
  exact intended action / product policy / sizing request
  created_at / expires_at / idempotency key / state

ProposalApproval
  proposal_address / actor / decision / reason
  decided_at / valid_until / expected revision
  PENDING / APPROVED / REJECTED / EXPIRED / SUPERSEDED / CONSUMED

ProposalRevalidation
  exact current mapping / price coherence / spread / liquidity
  capital / reservation / data freshness / provider health / position state
  accepted or typed refusal / checked_at / receipt address
```

Approval cannot call a broker directly. A changed material address or expired TTL requires a new proposal or approval; risk-reducing exits do not depend on it.

### Dynamic Watchlist

```text
UniverseDefinitionRevision
  base scope / filters / rank / top-K / tie-break
  cadence / stages / resource budget
  hysteresis / residency / cooldown / leave policy

UniverseEvaluation
  definition / time / knowledge cutoff / exact inputs
  complete candidate population
  per-stage pass/fail/reason/cost
  rank/tie facts / selected set / algorithm

UniverseSnapshot
  research or execution purpose
  exact canonical members / rank facts / exclusions
  content address
```

Editable watchlists remain aliases. Deployments bind snapshots. Membership changes never erase exact held positions.

### Point-in-time reference/events

All facts carry `observed_at`, `effective_at`, `published_at` when applicable, revision/correction lineage, provider/source/evidence identity and availability. V1 schemas cover only market cap/free-float methodology, sector/industry, listing/tradability, earnings/corporate events and bounded economic-event categories. Provider acquisition remains a separate external decision.

### Activation and resource planning

Compile-time: explicit activation prerequisite, warm policy, lookback, startup latency, maximum age, cooldown/hysteresis, resource footprint and entry behavior while warming. Runtime: `OFF`, `WARM`, `ACTIVE`, `COOLDOWN`, plus `DATA_READY` barrier and typed block reason. In-process state owns per-event hot computation; any shared hot store is recoverable; PostgreSQL/object storage own durable definitions, transitions requiring audit, reservations and evidence.

### Price coherence

Bind canonical instrument/contract, signal observation/address, execution-side observation/address, comparable field semantics, age/skew/divergence thresholds, platform maxima, user bounds, breach state and receipt. Buy uses fresh ask/suitable executable reference; sell uses fresh bid/suitable reference. Wrong mapping, stale execution quote, incompatible fields and extreme divergence are hard blocks. New entries stop; safe risk-reducing actions remain available.

### Latency and live eligibility

Record provider receive, evaluation, admission, intent, submit, broker acknowledgement and fills. Compile maximum input/cross-provider/decision/signal ages, reaction horizon, action and turnover limits, pending orders and queue sensitivity. Classes are `BAR_CLOSE_LIVE`, `SECOND_SCALE_LIVE`, `SUBSECOND_RESEARCH_PAPER_ONLY`, and `QUEUE_SENSITIVE_UNSUPPORTED` until measurements justify otherwise.

### V1/V1.5 options boundary

V1 can represent and research exact derivative observations/selectors where data exists, and can use them to trade another supported product. Benchmark D is recorder/shadow only. V1.5 owns certified single-leg liquid index-options selection, order behavior, exact held-contract management, protection and reconciliation. Stock/commodity/multi-leg breadth stays later.

### Forward chart evidence and replay

Bind exact thesis revision, semantic annotations, vendor artifact provenance, forward observations, proposal/rejection/approval/revalidation, paper/shadow outcome, actual execution where eligible and post-trade review. General hindsight-drawn historical annotation testing is excluded. Replay covers the prospective events Strategy OS actually recorded.

## Migration and review policy

- Every new durable fact uses additive tables/nullable references; no ambiguous historical backfill.
- Legacy paths remain explicit and never acquire new authority by inference.
- Schema changes prove empty install, supported upgrade, restart, constraints, PostgreSQL semantics, backup/restore and rollback/forward-repair.
- Money, authority, market truth, approval, tenancy, recovery and provider-coherence slices receive one integrated independent review after product/test bytes and evidence freeze.
- No validator of a validator is added unless a named Critical hypothesis shows an ordinary reviewed test can falsely pass.
