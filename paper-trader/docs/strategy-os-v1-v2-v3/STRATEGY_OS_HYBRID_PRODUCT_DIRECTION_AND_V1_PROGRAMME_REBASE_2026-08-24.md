# Strategy OS — Hybrid Product Direction, Expanded V1 Scope, and Programme Rebase Addendum

**Date:** 24 August 2026\
**Status:** Owner-directed product addendum and mandatory input to the revised progress mapper\
**Purpose:** Consolidate the product decisions made after the current 24 August architecture memo, define the revised V1 product boundary, and specify what the repository/programme audit must now account for from Phase 5 onward.\
**Applies to:** Product strategy, architecture, design, frontend, backend, data, research, execution, infrastructure, testing, documentation, Codex/subagent work, and release planning.

---

## 0. Authority, precedence, and interpretation

This addendum must be read together with the nine existing canonical documents:

1. `00-STRATEGY-OS-PRODUCT-STEER.md`
2. `01-STRATEGY-LANGUAGE-NODE-SYSTEM.md`
3. `02-MARKET-TRUTH-DATA-CONTRACTS.md`
4. `03-DEPLOYMENT-EXECUTION-TRUST.md`
5. `04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md`
6. `05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md`
7. `STRATEGY_OS_GRAND_PRODUCT_VISION_2026-08-11.md`
8. `STRATEGY_OS_V1_PRODUCT_SCOPE_AND_SEQUENCE_2026-08-11.md`
9. `strategyos-v1-v1.1-v1.5-v2-v3-product-architecture-memo-2026-08-24(1).md`

Where scope, timing, or version labels conflict, use this order:

1. latest explicit owner decision;
2. this addendum;
3. the 24 August architecture memo;
4. the technical steers and accepted ADRs;
5. the earlier ten-phase programme and August 11 documents where not superseded.

This addendum does **not** discard the accepted work through Phase 4. That work remains valuable and should be preserved unless a concrete core-abstraction defect is demonstrated.

This addendum also does **not** authorize undisciplined feature accumulation. It defines a wider but bounded product. The implementation programme must now be rebased so that the new scope is sequenced correctly, built thoroughly, and tested according to realistic risk rather than arbitrary test volume.

---

# 1. Executive product decision

Strategy OS should no longer be framed primarily as a product that asks discretionary traders to become fully automated traders.

The strongest initial product identity is:

> **A hybrid discretionary-systematic trading decision operating system.**

The product should allow a trader to preserve the parts of trading where human context and judgment are strongest, while delegating the parts where machines are strongest.

```text
HUMAN
- forms a market thesis;
- chooses important instruments and regimes;
- draws or selects chart context;
- defines support, resistance, trend, Fibonacci, invalidation, and bias;
- decides which opportunities deserve attention;
- may approve or reject a proposed trade.

MACHINE
- watches many instruments and data domains simultaneously;
- evaluates indicators, price action, derivatives, OI, order flow, and events;
- checks freshness, provider coherence, liquidity, and account risk;
- enforces timing, sizing, exits, and operational rules;
- alerts, proposes, or executes within declared authority;
- preserves exact evidence and replay.
```

The core product promise becomes:

> **Turn your market thesis into a system. Keep your judgment where it matters; use machine vigilance, evidence, and execution discipline everywhere else.**

This is not a compromise between manual and algorithmic trading. Properly implemented, it is a stronger operating model than either one in isolation.

---

# 2. The complete strategy stack

The product should be capable of combining five major sources of trading reasoning:

```text
1. CHART / OPERATOR CONTEXT
   - user-defined levels, zones, trendlines, Fibonacci structures, bias, invalidation;

2. PRICE ACTION / MARKET STRUCTURE
   - OHLCV, gaps, ranges, breakouts, candlestick patterns, session structure;

3. INDICATORS / STATISTICS
   - trend, momentum, volatility, regression, z-scores, correlations, regimes;

4. DERIVATIVES / OI / ORDER-FLOW INTELLIGENCE
   - options chains, expiries, strikes, IV, Greeks, OI, futures basis, depth,
     genuine trade flow where the provider supports it;

5. FUNDAMENTALS / REFERENCE DATA / EVENTS
   - market capitalization, sector/industry, earnings, corporate actions,
     scheduled economic events, and other point-in-time filters.
```

Not every strategy needs all five layers. The product is complete because it can combine them when the trader's thesis requires them, not because every template forces all five into every graph.

Risk, capital admission, execution-product selection, order semantics, monitoring, reconciliation, and evidence remain platform operating layers around the strategy rather than additional sources of market reasoning.

---

# 3. Revised market wedge and adoption ladder

A large part of the Indian trading market may resist a product positioned as a complete replacement for discretionary judgment. Strategy OS should therefore support a gradual adoption ladder:

```text
DRAW / DEFINE THESIS
        ↓
MACHINE MONITORING
        ↓
ALERT ONLY
        ↓
TRADE PROPOSAL + HUMAN APPROVAL
        ↓
BOUNDED AUTOMATION
        ↓
FULLY SYSTEMATIC DEPLOYMENT WHERE APPROPRIATE
```

The same strategy should be able to end in any of these operating modes:

1. **Research only** — no live monitoring or order authority.
2. **Monitor and alert** — the system identifies a qualifying setup and explains it.
3. **Propose and confirm** — the system prepares an exact, expiring trade proposal; the user approves or rejects it; the system revalidates before execution.
4. **Paper/shadow** — the system observes and records expected behavior without real-money authority.
5. **Bounded automatic execution** — the system executes only within the deployment's data, capital, latency, provider, order, and protection contracts.

The proposal/approval path is now a first-class V1 product requirement. Approval must never execute a stale proposal without rechecking price, spread, liquidity, capital, data freshness, position state, and provider health.

---

# 4. TradingView-based chart integration: product direction

## 4.1 Do not build a charting engine from scratch

Strategy OS should integrate a mature charting library rather than attempt to reproduce TradingView's chart engine, drawing toolbar, rendering behavior, layout system, and indicator UI.

TradingView is the preferred integration direction, subject to an explicit product, technical, licensing, and access review.

The official TradingView materials currently describe:

- Advanced Charts with a large set of drawing tools and custom-data integration;
- APIs for creating and interacting with drawings;
- save/load mechanisms for chart layouts, drawing templates, and indicator templates;
- an option to store drawings separately from chart layouts and associate them with symbols;
- a Trading Platform library that adds direct trading-oriented functionality;
- a separate open-source Lightweight Charts library with a different capability envelope.

Relevant official references for the implementation audit:

- <https://www.tradingview.com/charting-library-docs/latest/introduction/>
- <https://www.tradingview.com/charting-library-docs/latest/ui_elements/drawings/>
- <https://www.tradingview.com/charting-library-docs/latest/ui_elements/drawings/drawings-api/>
- <https://www.tradingview.com/charting-library-docs/latest/saving_loading/>
- <https://www.tradingview.com/charting-library-docs/latest/saving_loading/saving_drawings_separately/>
- <https://www.tradingview.com/charting-library-docs/latest/saving_loading/save-load-adapter/>
- <https://www.tradingview.com/free-charting-libraries/>
- <https://www.tradingview.com/charting-library-docs/latest/quick-start>

The audit must not assume that an embedded TradingView library exposes every capability available on tradingview.com. It must verify the exact library, access terms, supported drawings, event APIs, save/load behavior, custom-data requirements, indicator limitations, trading hooks, redistribution constraints, and branding obligations.

Zerodha's current support material confirms that Kite offers TradingView charts as one of its charting options, but Strategy OS must independently establish its own permitted integration route and contracts:

- <https://support.zerodha.com/category/trading-and-markets/charts-and-orders/charts/articles/how-do-i-switch-to-tradingview-charts>
- <https://support.zerodha.com/category/trading-and-markets/charts-and-orders/charts/articles/trade-from-charts-on-tradingview>

## 4.2 Preserve a chart-provider adapter boundary

TradingView should be the preferred implementation, not a permanent core-domain dependency.

Strategy OS should own:

- chart workspace identity;
- ownership and tenancy;
- canonical instrument and provider bindings;
- operator-thesis identity;
- normalized semantic annotation objects;
- strategy-node bindings;
- approval and execution authority;
- evidence, audit, and replay.

The chart library should own:

- rendering;
- drawing interactions;
- viewport behavior;
- chart-native layouts and templates;
- supported chart styles and visual tooling.

A chart-provider adapter should isolate vendor-specific APIs, storage formats, event names, version changes, and licensing assumptions.

## 4.3 Store two related artifacts

Where the chosen chart library permits it, Strategy OS should retain:

### A. Vendor chart state

Used to reconstruct the user's visual workspace:

- layout;
- drawings;
- drawing groups;
- indicator templates;
- chart settings;
- supported workspace state.

This state is vendor/version-specific and should not itself become executable strategy semantics.

### B. Normalized semantic strategy inputs

Used by Strategy OS nodes and receipts:

```text
PriceLevel
PriceZone
TrendLine / Ray
Channel
FibonacciStructure
TimeMarker / TimeWindow
OperatorBias
InvalidationRule
ThesisExpiry / TTL
AnnotationGroup / ThesisRevision
```

Only drawing types that Strategy OS can normalize deterministically should become executable inputs.

Unsupported or purely visual drawings may still be saved in the chart workspace but must not silently influence strategy evaluation.

## 4.4 V1 chart semantics are forward/live inputs, not historical backtesting features

V1 should **not** attempt general historical backtesting of user-drawn trendlines, Fibonacci structures, support/resistance zones, or discretionary annotations.

Reasons:

- the user may draw with future chart information visible;
- historical reconstruction of discretionary intent is expensive and easy to contaminate;
- the first-release ROI is low;
- chart-first traders can inspect historical charts themselves;
- systematic users primarily need backtestable price action, indicators, event data, and candlestick-pattern nodes.

Therefore:

```text
V1
- chart workspace;
- drawing persistence;
- bounded semantic extraction;
- lock/version/activate/expire;
- live/forward monitoring;
- alert, approval, paper, and eligible execution;
- forward evidence collection.

NOT V1
- general annotation-derived historical backtests;
- pretending hindsight drawings are causal;
- AI inference from chart screenshots or arbitrary freehand marks;
- complete TradingView feature parity.
```

Candlestick patterns and other deterministically defined price-action nodes remain normal backtestable strategy primitives.

Historical annotation replay may be evaluated later only if usage evidence justifies it and causality can be preserved through a point-in-time replay workflow.

## 4.5 Operator Thesis object

A locked chart context should become a versioned `OperatorThesis` or equivalent first-class object.

Minimum V1 fields should include:

```text
thesis_id
revision
owner / tenant
canonical instrument or named role
timeframe
chart data provider / dataset identity
session / timezone / adjustment policy
directional bias
normalized semantic annotations
invalidation conditions
effective_from
expires_at / TTL
created_at
locked_at
status
strategy/deployment bindings
vendor chart-state reference
```

Suggested states:

```text
DRAFT
LOCKED
ACTIVE
SUPERSEDED
EXPIRED
INVALIDATED
RETIRED
```

A chart change after locking creates a new revision. It must not silently mutate the strategy revision or an existing position.

The default invariant remains:

> An open position stays managed by the strategy, deployment, and Operator Thesis revisions that created it unless an explicit reviewed takeover occurs.

## 4.6 Expand the semantic inventory only after an API audit

The initial examples—support, resistance, trendlines, Fibonacci levels, and zones—are not the complete product surface. The chart-integration audit must inventory the available TradingView drawing and chart APIs and classify each candidate as:

```text
V1 EXECUTABLE SEMANTIC INPUT
V1 VISUAL-ONLY PERSISTENCE
V1.5 OR V2 EXECUTABLE INPUT
RESEARCH SPIKE
REJECT / UNSUPPORTED
```

Selection criteria:

- actual user value;
- deterministic geometry and semantics;
- ability to persist and reconstruct;
- ability to bind to canonical instrument/timeframe/data provenance;
- safe use in live/forward evaluation;
- implementation cost;
- vendor API stability;
- ability to explain and test behavior.

Do not front-load obscure drawing tools merely because the library provides them.

---

# 5. V1 Dynamic Watchlists / Dynamic Universes

The latest owner decision moves the public Dynamic Watchlist product into V1.

V1 must support both:

```text
A. Fixed Instruments
B. Dynamic Watchlist
```

The existing `InstrumentScope` / `Universe` abstraction remains correct. The version label changes.

A V1 Dynamic Watchlist should support a bounded but real workflow:

- base market scope;
- point-in-time eligibility filters;
- ranking;
- top-K / percentile / bounded selection;
- refresh cadence;
- stable tie-breakers;
- candidate limits;
- hysteresis, cooldown, and minimum residency where needed;
- explicit leave policy for open positions;
- durable definition revision;
- durable universe snapshot;
- candidate pass/fail/rank reasons;
- research versus execution eligibility;
- provider and resource requirements.

The product must support staged evaluation:

```text
STAGE 1 — cheap reference/static filters
STAGE 2 — bar-level technical and price-action filters
STAGE 3 — expensive derivatives, order-flow, or event inputs
STAGE 4 — portfolio admission and deployment
```

This is required both for understandable product behavior and for bounded runtime economics.

---

# 6. Bounded V1 fundamentals, reference data, and events

Moving Dynamic Watchlists into V1 requires enough point-in-time reference and event data to make cross-sectional filtering credible.

V1 should implement a bounded layer including, where reliable data contracts exist:

- point-in-time market capitalization;
- shares-outstanding/free-float methodology where relevant;
- sector and industry classification with revision identity;
- listing and tradability status;
- earnings announcement schedule;
- selected corporate events and corporate actions;
- bounded scheduled economic-event categories;
- provider/source provenance;
- `observed_at`, `effective_at`, `published_at`, and revision semantics where relevant.

V1 does **not** need to become a complete financial-statements, estimates, transcript, or macroeconomic terminal.

The distinction is:

```text
V1
- enough reference/event truth for Dynamic Watchlists, eligibility,
  blackouts, grouping, ranking, and evidence.

V2+
- deep financial statements;
- broad fundamental factor libraries;
- analyst estimates and transcript intelligence;
- full event knowledge graph;
- automated fundamental recommendations.
```

User-provided datasets should remain a first-class route where platform-owned data is unavailable or commercially unsuitable.

---

# 7. Temporal, weekday, seasonal, and cyclical strategies

V1 must allow the user to define different logic by trading day and by broader calendar/market phase.

The product should not hardcode five unrelated strategy types. It should provide generic temporal routing and reusable subgraphs.

Minimum V1 primitives:

```text
TradingDayOfWeek
MonthOfYear
Quarter
DateRange
WeekOfMonth
SessionPhase
MinutesFromOpen
MinutesToClose
DTE / ExpiryPhase
DaysBeforeEvent
DaysAfterEvent
UserDefinedSeasonalRegime
Calendar Router / Branch
```

Example:

```text
Monday      → options/volatility subgraph
Wednesday   → another expiry-cycle subgraph
Friday      → no-entry or different management subgraph
January–March → momentum regime
June–July     → another declared strategy regime
```

These are user hypotheses, not platform claims.

All calendar behavior must use point-in-time exchange calendars and market rules rather than assuming that the civil weekday permanently determines expiry or session behavior.

Research evidence should retain branch-level attribution because numerous weekday and seasonal branches increase the effective strategy search space and overfitting risk.

---

# 8. Selectivity-aware execution planning

## 8.1 Core decision

The more expensive data and computation that must remain active concurrently, the higher the platform cost.

The more expensive branches can be safely and causally gated behind selective low-cost prerequisites, the lower the expected runtime cost.

The correct concept is:

> **Selectivity-aware execution planning.**

This is more precise than saying that every visually sequential strategy is automatically cheaper.

## 8.2 V1 branch activation states

A bounded version belongs in V1:

```text
OFF
WARM
ACTIVE
COOLDOWN
```

Possible meaning:

- `OFF`: no expensive subscription or downstream computation;
- `WARM`: bounded data and state are maintained to satisfy declared activation latency/lookback;
- `ACTIVE`: full branch requirements are subscribed and evaluated;
- `COOLDOWN`: state/subscriptions remain temporarily to prevent churn before returning to WARM/OFF.

The transition to `ACTIVE` must include a readiness barrier:

```text
activation prerequisite
→ contracts/series resolve
→ subscriptions confirm
→ required lookback/state becomes valid
→ DATA_READY
→ branch may qualify a new entry
```

Until data is ready, the system must display an actionable block reason rather than silently evaluating incomplete inputs.

## 8.3 Explicit activation boundaries

A normal conditional node does not automatically imply that upstream data acquisition may be stopped.

Strategy OS needs an explicit activation/subgraph contract that can declare:

```text
activation prerequisite
warm policy
lookback requirement
startup-latency tolerance
maximum quote/data age
cooldown/hysteresis
resource footprint
entry behavior while warming
```

The compiler must not reorder or deactivate logic if doing so changes temporal semantics.

For example:

```text
A THEN B WITHIN 5 MINUTES
```

may require observing A before another cheap gate becomes true. Turning A's data off would change the strategy.

## 8.4 V1 versus later optimization

V1 should include:

- precompiled graph/runtime plans;
- declared activation boundaries;
- OFF/WARM/ACTIVE/COOLDOWN;
- bounded prefetch/warm state;
- dependency-aware incremental evaluation;
- shared calculations/subscriptions within permitted boundaries;
- staged Dynamic Watchlist evaluation;
- resource receipts and limits.

Later releases may add:

- cost/selectivity estimates learned from observed behavior;
- automated branch-planning suggestions;
- speculative prefetch based on proximity/probability;
- more sophisticated plan optimization;
- automatic safe predicate reordering where mathematical equivalence is proven.

Do not permit “optimistic” preparation to become optimistic financial execution. Orders, irreversible state changes, and final capital admission still require fully valid conditions.

---

# 9. Runtime economics and resource limits

Raw node count is not the primary cost metric.

A large arithmetic graph may be cheap; a small graph that subscribes to many option contracts, depth feeds, or high-frequency custom nodes may be expensive.

Resource planning should focus on:

```text
physical subscriptions after deduplication
instrument fan-out
option contracts / strikes / expiries
market-depth levels and feeds
events per second
evaluations per second
state and lookback size
custom-code CPU/memory/time
peak active footprint
expected active footprint / duty cycle
subscription churn
historical-data demand
order/cancel/modify activity
storage and telemetry
provider quotas
```

Reasonable guardrails may still exist for total graph size, nesting, and compile safety, but customer tiers and live eligibility should not be based primarily on node count.

Limits should be aligned to node families:

- Market Data: instruments, feeds, resolutions, events, physical subscriptions;
- Derivatives/Market Structure: contracts, expiries, strike width, depth, churn;
- Indicators: state, lookback, complexity, input frequency;
- Logic/State: temporal memory, active branches, state-machine complexity;
- Execution: order actions, pending orders, turnover, positions, re-entry frequency;
- Custom nodes: CPU, memory, state size, wall-clock and permissions.

The resource receipt should distinguish:

```text
logical requests
physical subscriptions
always-on footprint
warm footprint
peak active footprint
expected duty cycle
peak and expected events/second
latency class
provider quota class
```

---

# 10. Latency, order frequency, and non-HFT positioning

Strategy OS is not an HFT, co-location, exchange-queue, or latency-arbitrage platform.

A Mumbai server can reduce part of the network path but cannot guarantee:

- broker processing latency;
- exchange acknowledgement latency;
- fill time;
- queue position;
- deterministic market-data delivery;
- sub-second edge preservation.

V1 must provide honest latency and live-eligibility contracts instead of marketing claims.

Every live deployment should declare or compile:

```text
maximum input age
maximum cross-provider timestamp skew
maximum decision age
maximum signal age at submission
minimum useful reaction horizon
order-action budget
turnover/re-entry budget
fill/queue sensitivity
```

The platform should measure and display separate latency components where possible:

```text
data-provider receive latency
strategy evaluation latency
risk/capital-admission latency
order submission latency
broker acknowledgement latency
fill timing (observed, not guaranteed)
```

Possible coarse eligibility labels:

```text
BAR-CLOSE LIVE
SECOND-SCALE LIVE
SUBSECOND RESEARCH/PAPER ONLY
QUEUE-SENSITIVE UNSUPPORTED
```

Exact boundaries must come from measured provider/broker/runtime telemetry and applicable exchange/broker constraints.

The platform should impose conservative order-action, cancel/modify, pending-order, and turnover ceilings. External exchange/broker ceilings are not the same as safe product defaults.

---

# 11. Provider heterogeneity and cross-provider price coherence

Data providers and execution brokers may be different, and their capability sets may differ materially.

Every data-dependent node must declare:

```text
required field
required resolution
required history
required depth
maximum age
maximum skew
provider-supplied versus locally derived
research/paper/live eligibility
```

The provider capability matrix remains mandatory.

A disclaimer is not an adequate response to material price mismatches.

V1 must include a cross-provider `PriceCoherencePolicy` or equivalent pre-trade contract with:

```text
signal provider
execution broker/reference feed
canonical instrument mapping
semantically comparable price fields
maximum age
maximum timestamp skew
maximum divergence
behavior on breach
open-position/risk-reducing policy
receipt/audit fields
```

The system should compare executable-side semantics where appropriate:

- buy intent against a fresh ask or suitable executable reference;
- sell intent against a fresh bid or suitable executable reference;
- not a stale LTP against an unrelated mid/ask/bid.

A material breach should place the deployment in a declared state such as `DATA_DIVERGENT`, block new entries, preserve risk-reducing actions where safe, alert the user, and persist both observations and timestamps.

Do not silently switch data providers mid-session unless the user approved a semantically compatible fallback and the resynchronization policy is defined.

Some non-overridable safety failures should remain platform hard stops:

- wrong canonical instrument or contract;
- unresolved mapping;
- materially stale execution quote;
- extreme or unexplained price divergence;
- incompatible semantic fields;
- provider state insufficient for safe execution.

Legal terms should disclose third-party data, broker, latency, and execution risk, but legal text must not replace engineering controls.

---

# 12. Revised V1 research and backtesting boundary

V1 retains the full deterministic research loop for strategy components that can be represented causally and supported by point-in-time data:

- price action;
- indicators/statistics;
- Dynamic Watchlists;
- cross-instrument inputs;
- bounded fundamentals/reference/events;
- options/futures/OI/order-flow only where real historical data exists;
- bounded optimisation;
- parameter neighborhoods;
- locked OOS;
- walk-forward;
- Monte Carlo/execution stress;
- evidence lineage.

V1 should not spend release-critical time building historical chart-annotation backtests.

For hybrid chart strategies, V1 evidence should come from:

- forward monitoring;
- shadow/paper observation;
- proposal and approval receipts;
- actual chart/thesis revisions;
- post-trade review;
- prospective datasets recorded by Strategy OS.

If historical options depth, signed flow, or another required field does not exist, Strategy OS must not fabricate it. It should mark the strategy's eligibility honestly and offer prospective recording where appropriate.

---

# 13. Revised execution boundary

## 13.1 V1

V1 should support:

- research-only;
- signal/alert;
- proposal + human approval;
- paper/shadow;
- controlled live paths already proven safe for their asset class, provider, latency, and order semantics;
- options and derivatives data as signal/confirmation inputs where provider contracts allow;
- exact strategy, thesis, universe, provider, and deployment attribution.

## 13.2 V1.5

Certified options execution remains a dedicated later boundary.

V1.5 should initially focus on a narrow, liquid, single-leg index-options surface with verified:

- point-in-time contracts;
- quote/liquidity semantics;
- broker behavior;
- order policies;
- exact-held-contract management;
- provider capability;
- latency eligibility;
- reconciliation and protection.

The 09:15 opening option-repricing idea remains a valuable prospective recorder/research/shadow benchmark, not a V1 live promise.

Options data may still contribute to decisions that trade cash equities, intraday products, MTF, or futures in V1 where those execution paths are supported.

---

# 14. Canonical strategy benchmarks after this addendum

The revised programme should use a small set of heterogeneous vertical benchmarks plus focused invariant tests.

## Benchmark A — Reusable static equity strategy

Proves:

- reusable named roles;
- cross-instrument research;
- sizing;
- stops/exits;
- evidence;
- static deployments.

## Benchmark B — NIFTY cross-expiry IV/order-flow strategy

Proves:

- dynamic derivative data structures;
- current/next expiry observations;
- ATM/ITM/OTM windows;
- IV/OI/depth/flow semantics;
- historical analogue artifacts;
- temporal gates;
- exact contract identity;
- resource planning.

Research/paper may precede certified options execution.

## Benchmark C — Dynamic industry rotation with derivatives confirmation

Conceptual flow:

```text
point-in-time NSE universe
→ market-cap/reference filter
→ EMA slope + z-score + VWAP/price-action filter
→ group by point-in-time industry
→ select bounded industries
→ inspect top industry leaders
→ bounded options/futures/OI confirmation
→ event blackout
→ rank candidates
→ at most one instrument per industry
→ at most three industries/day
→ intraday execution
→ sector-index-conditioned target sizing where available
```

Proves:

- Dynamic Watchlists;
- point-in-time reference/event data;
- staged evaluation;
- industry taxonomy;
- peer roles;
- derivative confirmation;
- ranking and tie-breakers;
- portfolio constraints;
- target-position sizing;
- expensive resource ceilings.

“Dealer positioning” must be represented only as an explicit inference model with declared assumptions, never as a raw fact derived from OI alone.

## Benchmark D — Pre-open bias and opening option-repricing recorder

Proves:

- pre-open/market-open events;
- GIFT Nifty/futures/index alignment;
- quote/depth recording;
- contract warming;
- latency receipts;
- marketable-limit policy;
- shadow/paper evidence;
- refusal of unsupported live latency claims.

This is research/shadow-first and not a V1 live requirement.

## Benchmark E — Operator-defined chart thesis with automated confirmation

Conceptual flow:

```text
user opens chart
→ creates and locks semantic chart thesis
→ price approaches declared zone
→ expensive derivatives branch warms
→ price enters/qualifies
→ options/OI/order-flow/broader-market confirmation activates
→ system emits explanation and expiring proposal
→ user approves or rejects
→ system revalidates
→ paper or eligible execution
→ position remains bound to creating revisions
```

Proves:

- TradingView/chart integration;
- vendor-state persistence;
- normalized semantic annotations;
- Operator Thesis versioning;
- conditional resource activation;
- machine confirmation;
- human approval TTL and revalidation;
- exact attribution and replay.

## Benchmark F — Cross-market derivative signal, different execution instrument

Example:

```text
BSE options/derivative data
+
other market context
→ CDSL or another separately bound execution instrument
```

Proves:

- observed instrument != thesis instrument != execution instrument;
- cross-market provider capability;
- timestamp/freshness alignment;
- independent data and execution providers;
- price-coherence protection.

---

# 15. Revised release boundaries

## V1 — focused but materially wider complete product

V1 now includes or must preserve:

- accepted Phase 1–4 foundations;
- coherent product UX and strategy workspaces;
- typed/versioned strategy language;
- cross-instrument roles;
- price action, indicators, candlestick patterns, and state/temporal logic;
- bounded derivatives/OI/order-flow data inputs where supported;
- Dynamic Watchlists / Dynamic Universes;
- point-in-time market-cap, sector/industry, earnings/event/reference subset;
- TradingView-preferred chart integration, subject to access/license/API audit;
- saved chart workspaces plus bounded semantic annotation inputs;
- Operator Thesis versioning;
- no general annotation-derived historical backtesting;
- alert/signal, proposal + human approval, paper/shadow, and controlled eligible execution;
- weekday, seasonal, DTE, and event-relative routing;
- Phase 5 sizing, target-position seam, and deterministic concurrent capital admission;
- selectivity-aware OFF/WARM/ACTIVE/COOLDOWN activation;
- staged universe evaluation;
- provider capability matrix;
- cross-provider price coherence;
- resource planning, QoS, limits, and cost telemetry foundation;
- non-HFT latency eligibility and honest runtime receipts;
- bounded optimisation and validation;
- exact evidence lineage and replay foundations;
- security, tenancy, IP confidentiality, and operational trust.

## V1.1

Dynamic Watchlists no longer belong exclusively to V1.1.

The revised programme may:

- retire the V1.1 label;
- or reserve it for post-launch hardening, richer universe operators, additional chart semantics, provider breadth, and UX improvements.

The progress mapper must make this explicit rather than leaving contradictory labels in canonical documentation.

## V1.5

- certified liquid index-options execution;
- additional options-selector certification;
- stricter options latency/liquidity/order conformance;
- exact held-contract protection and reconciliation;
- only additional chart semantics that are low-risk and justified by usage;
- no obligation to implement historical chart-annotation backtesting.

## V2

- deterministic product Workflows;
- richer fundamentals and events;
- Strategy Diagnostics and Counterfactual Lab;
- richer derivatives/OI intelligence;
- chart-annotation replay/backtesting only if validated as worthwhile;
- more semantic chart objects and external-signal/chart interoperability;
- deeper portfolio/research intelligence;
- richer adaptive sizing;
- recommendations grounded in exact evidence.

## V3 / demand-led

- AI interpretation of freehand charts or images;
- AI Research Agent;
- ML/model nodes;
- marketplace and managed models;
- advanced portfolio allocation/Kelly;
- international markets and institutional integrations;
- queue-position and low-latency models where data and demand justify them.

---

# 16. Programme rebase requirement

The original ten-phase programme is no longer automatically assumed to be sufficient.

The correct instruction is:

> Preserve and verify the accepted work through Phase 4. Re-audit and re-sequence Phase 5 onward against the new product direction. Add phases or subphases where dependency clarity, safety, or implementation quality requires them. Do not retain ten phases merely for cosmetic continuity.

The revised programme must answer:

- what already exists and is reusable;
- what contracts are missing;
- what new object models and migrations are required;
- which frontend and backend lanes can proceed in parallel;
- what must precede Dynamic Watchlists, chart semantics, or hybrid approval;
- how Phase 5 sizing/admission interacts with the new workflows;
- how provider/resource planning is introduced before expensive live breadth;
- how new benchmarks prove the architecture;
- what exact release gates define a complete V1;
- what is deliberately pushed to V1.5, V2, or V3;
- what the new evidence-based release window should be.

The previous 1 September target is no longer authoritative. A quality-driven target around mid-September after the owner's exams is acceptable, but the repository audit must produce a credible schedule rather than simply moving the date.

---

# 17. Engineering and testing policy

The project must return to building the product rather than repeatedly constructing validators of validators that do not protect meaningful behavior.

## 17.1 Risk-weighted verification remains mandatory

### Critical

Examples:

- money and capital admission;
- order/position ownership;
- provider/instrument mapping;
- price coherence;
- causality/point-in-time truth;
- chart-thesis revision binding;
- human-approval freshness;
- live/backtest parity where promised;
- tenant isolation;
- recovery and reconciliation;
- dynamic-universe snapshot correctness.

Use explicit invariants, adversarial cases, integration/recovery/concurrency proof, and independent review.

### Important

Examples:

- indicator and ranking math;
- chart semantic conversion;
- provider adapters;
- resource receipts;
- activation-state transitions;
- cache identity;
- candidate ranking/tie-breakers.

Use focused unit/integration tests and regressions for realistic failure hypotheses.

### Routine/trivial

Use affected tests, typecheck, smoke tests, and existing suites. Do not create elaborate meta-validation systems for copy, layout, ordinary CRUD, or harmless presentation state.

## 17.2 Test cadence

- directly affected tests during implementation;
- subsystem suites at meaningful commits;
- broad/full suites at phase and release boundaries;
- golden vertical benchmarks plus small invariant-specific adversarial tests;
- no arbitrary coverage or test-count objectives.

## 17.3 Avoid validator recursion

Do not add another validation layer merely to validate an existing validator unless a concrete critical failure mode requires it.

Prefer:

```text
clear contract
+ one authoritative validation path
+ direct realistic tests
+ receipts and observability
```

rather than:

```text
validator
→ validator wrapper
→ validator checker
→ checker verifier
```

---

# 18. LLM and subagent policy

The implementation programme should use higher-capability models for consequential work.

Owner decision:

- **Sol Medium is the minimum model level** used by the application/agent programme;
- **xhigh is the preferred highest-effort setting** for architecture, critical correctness, security, market truth, concurrency, migrations, and release review.

Before changing model configuration, verify the exact identifiers exposed by the current orchestration stack rather than guessing spellings.

Subagents should be used for bounded, evidence-producing tasks:

- repository audit;
- exact prior-art review;
- provider/API contract comparison;
- threat/failure modeling;
- targeted test design;
- migration review;
- frontend interaction review.

Do not create agent chains whose primary purpose is to verify other agents without a real critical risk hypothesis.

The accepted prior-art gate remains in force, but it should be proportional. Review the repositories and official APIs that materially affect the feature; record exact commits, licenses, patterns, rejected assumptions, and required tests; then proceed.

---

# 19. Non-negotiable implementation rules

1. Do not rebuild accepted Phase 1–4 foundations without concrete evidence.
2. Do not clone TradingView; integrate through a bounded chart-provider adapter.
3. Do not assume library access, licensing, or feature parity before verification.
4. Do not make vendor chart-state blobs the executable strategy language.
5. Do not silently convert unsupported drawings into strategy semantics.
6. Do not claim historical validity for hindsight-drawn chart annotations.
7. Do not make chart-annotation backtesting a V1 release gate.
8. Do not hardcode Dynamic Watchlists as permanent symbol arrays.
9. Do not use current sector membership, market cap, events, or contract rules as historical truth.
10. Do not run expensive universe/derivative stages across the full market when staged evaluation can preserve semantics.
11. Do not infer lazy activation from an ordinary conditional block if temporal meaning may change.
12. Do not treat Redis as the authoritative store for money, orders, positions, strategies, approvals, or evidence.
13. Do not price or limit primarily by raw node count.
14. Do not silently switch providers or accept semantically incompatible prices.
15. Do not use a disclaimer as a substitute for provider-coherence controls.
16. Do not market Strategy OS as HFT or promise exact sub-second fills.
17. Do not broadly enable live options execution in V1.
18. Do not let a human approval execute a stale proposal without revalidation.
19. Do not let a new chart/thesis revision silently alter an open position.
20. Do not let research/optimisation workloads delay live protection or reconciliation.
21. Do not build deep fundamentals, AI chart inference, marketplace, or institutional infrastructure before their release boundary.
22. Do not maximize tests, validators, brokers, drawings, or nodes as vanity metrics.
23. Do build the minimum complete vertical that proves each product capability truthfully.

---

# 20. Required programme/documentation outputs

The next architecture/planning pass must produce, at minimum:

1. **Current repository and Phase 1–4 verification map**
   - what exists;
   - what is partial;
   - what is missing;
   - what is obsolete;
   - what must remain untouched.

2. **Revised progress mapper from Phase 5 onward**
   - phases/subphases;
   - dependencies;
   - owners/agent lanes;
   - deliverables;
   - migrations;
   - acceptance scenarios;
   - exit gates;
   - risk/test level;
   - rollback;
   - estimated sequence and release window.

3. **V1 / V1.5 / V2 / V3 scope matrix**
   - including explicit handling of the former V1.1 label.

4. **Contract and ADR plan** for:
   - chart-provider adapter;
   - Operator Thesis and semantic annotations;
   - chart-state persistence;
   - proposal/human approval and TTL;
   - Dynamic Watchlists in V1;
   - point-in-time reference/events;
   - branch activation/resource planning;
   - provider price coherence;
   - latency/live eligibility;
   - revised options boundary.

5. **Golden benchmark and adversarial-test plan**
   - Benchmarks A–F;
   - realistic failure hypotheses;
   - no validator-of-validator work unless critical.

6. **Canonical-document reconciliation plan**
   - which documents remain authoritative;
   - which sections require amendment;
   - which older version labels are superseded;
   - no contradictory scope guidance left for future agents.

---

# 21. Final product statement

The updated V1 product should credibly be understood as:

> **A hybrid trading decision operating system in which a trader can build systematic logic, scan a dynamic point-in-time universe, combine chart context, price action, indicators, fundamentals/events, and derivatives intelligence, then choose whether the result remains research, becomes an alert, becomes an expiring trade proposal for human approval, or proceeds through a controlled execution path. Strategy OS preserves exact strategy, chart-thesis, data, provider, universe, capital, and execution identity while planning resources and refusing conditions it cannot support honestly.**

The immediate goal is not to ship every future capability.

The immediate goal is to rebase the programme so that this wider product is built in the correct order, with sufficient rigor, without returning to low-value meta-validation work or sacrificing forward momentum.
