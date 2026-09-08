# Strategy OS — Coherent Product Architecture and Release Evolution Memo

**Date:** 24 August 2026\
**Status:** Canonical replacement product-direction memo for architecture, implementation, design, research, and subagent work\
**Supersedes:** `strategyos-v1-v2-v3-product-architecture-memo-2026-08-19.md`\
**Purpose:** Consolidate the accepted Strategy OS product model, the latest owner decisions, the V1 ten-phase release discipline, the V1.1 Dynamic Watchlist direction, the V1.5 options-execution boundary, and the V2/V3 expansion path into one coherent memo that prevents both premature implementation and future architectural dead ends.

---

## 0. Authority, precedence, and interpretation

This memo replaces the 19 August 2026 V1→V2→V3 memo as the current product-evolution and architecture directive.

It does **not** discard the technical invariants established in:

1. `00-STRATEGY-OS-PRODUCT-STEER.md`
2. `01-STRATEGY-LANGUAGE-NODE-SYSTEM.md`
3. `02-MARKET-TRUTH-DATA-CONTRACTS.md`
4. `03-DEPLOYMENT-EXECUTION-TRUST.md`
5. `04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md`
6. `05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md`
7. `STRATEGY_OS_GRAND_PRODUCT_VISION_2026-08-11.md`
8. `STRATEGY_OS_V1_PRODUCT_SCOPE_AND_SEQUENCE_2026-08-11.md`

Where timing, scope, or version labels conflict, use this precedence:

1. the latest explicit owner decision;
2. this memo;
3. current accepted architecture steers and ADRs;
4. the current ten-phase V1 implementation programme;
5. older product-scope documents where not superseded.

The phrase **“preserve the seam now”** means:

> Remove assumptions that would force a destructive rewrite later, but do not build the future product before its release boundary.

It does not mean:

> Implement every plausible future feature in V1.

This distinction is central to every decision below.

---

# 1. Executive decision

Strategy OS remains a broad, asset-class-neutral trading decision operating system rather than an options bot, a charting clone, a generic no-code builder, or a broker terminal.

The full product lifecycle is:

```text
IDEA
  ↓
STRATEGY DEFINITION
  ↓
DATA AND INSTRUMENT BINDING
  ↓
BACKTEST
  ↓
OPTIMISATION
  ↓
VALIDATION
  ↓
EVIDENCE
  ↓
RESEARCH / SIGNAL / EXECUTION
  ↓
MONITORING
  ↓
RECONCILIATION
  ↓
REVIEW
  ↓
IMPROVEMENT
```

The longer-term operational lifecycle is broader:

```text
DEFINE STRATEGY
      ↓
SELECT OR DISCOVER ELIGIBLE INSTRUMENTS
      ↓
RESEARCH AND VALIDATE
      ↓
PORTFOLIO ADMISSION
      ↓
BIND EXECUTION PRODUCT
      ↓
PREFLIGHT
      ↓
DEPLOY
      ↓
MONITOR / INVALIDATE / RETIRE
      ↓
REVIEW STRATEGY, UNIVERSE, WORKFLOW, AND EXECUTION
```

The product therefore converges on these first-class concepts:

1. **Strategy** — the market logic and decision process.
2. **Instrument Scope / Universe** — which economic instruments are eligible.
3. **Workflow** — the durable lifecycle around discovery, research, approval, admission, deployment, monitoring, and retirement.
4. **Deployment** — the operational binding of an immutable strategy to concrete instruments, providers, account, capital, risk, mode, and execution policy.
5. **Execution Product Policy** — how an economic signal is expressed through cash, intraday, MTF, futures, options, or a later multi-leg structure.
6. **Portfolio Admission** — whether the portfolio can accept the requested exposure.
7. **Evidence** — the exact data, models, trials, assumptions, decisions, and outcomes that support or contradict trust.

The product moat is the coherence among these objects:

> Strategy OS should let a trader express the information behind a decision, prove that the required data and market structure support it, validate it honestly, select an appropriate execution product, and operate the exact approved revision without losing identity, evidence, or safety.

---

# 2. Product thesis and boundaries

## 2.1 What Strategy OS is

Strategy OS is intended to combine:

- visual and Python strategy authoring;
- typed strategy semantics;
- bring-your-own-data;
- cross-instrument research;
- fast backtesting;
- bounded optimisation;
- parameter-neighbourhood analysis;
- locked out-of-sample testing;
- walk-forward validation;
- Monte Carlo and execution stress;
- immutable evidence lineage;
- signal-only operation;
- provider-neutral deployment;
- risk and capital admission;
- execution truth;
- monitoring, reconciliation, journal, and review;
- later Dynamic Watchlists, Workflows, recommendations, and marketplaces.

## 2.2 What Strategy OS is not

It should not become:

- a TradingView clone;
- a Sensibull clone;
- a Screener clone;
- an MT5 clone;
- a Bloomberg clone;
- a broker-specific terminal;
- an opaque AI strategy generator;
- an automatic data-mining machine;
- a direct webhook-to-order bridge;
- a social-trading product before research and execution trust are established;
- a distributed-systems showcase built before actual scale requires it.

Specialist products can remain better at specialist jobs. Strategy OS should make specialist information and execution surfaces interoperable inside one versioned decision process.

---

# 3. Canonical long-term object model

## 3.1 Strategy

A Strategy answers:

> Given valid, sufficiently fresh inputs and an eligible economic context, what does this trading logic want to do?

It may contain:

- technical inputs;
- price action;
- cross-instrument inputs;
- VIX or volatility regimes;
- order-book or genuine trade-flow inputs where supported;
- fundamental and event inputs later;
- stateful and temporal logic;
- entry and exit intent;
- risk and sizing intent;
- chart-derived conditions later;
- custom declared features.

A Strategy should normally use named roles such as:

```text
SELF
UNDERLYING
BENCHMARK
SIGNAL_MARKET
REGIME_SOURCE
HEDGE
EXECUTION_MARKET
```

The observed instrument, underlying thesis instrument, and execution instrument may be different.

## 3.2 Instrument Scope / Universe

An Instrument Scope answers:

> Which instruments may this strategy consider?

The public product should eventually offer two modes:

```text
A. Fixed Instruments
B. Dynamic Watchlist
```

Internally, both should conform to a common abstraction:

```text
InstrumentScope
├── StaticUniverse
└── DynamicUniverse
```

V1 may expose only static bindings while preserving this interface. V1.1 adds the public Dynamic Watchlist experience.

## 3.3 Workflow

A Workflow answers:

> What durable sequence must occur before, during, and after a candidate is allowed to operate?

Examples:

```text
discover
→ rank
→ research
→ validate
→ approve
→ admit
→ deploy
→ monitor
→ invalidate
→ retire
→ review
```

Product Workflows are deterministic orchestration objects. They are **not AI workflows**.

The strategy graph and workflow engine must remain separate:

- strategy runtime: market causality, low-latency evaluation, position decisions;
- workflow runtime: durable jobs, retries, approvals, budgets, deadlines, lifecycle transitions.

## 3.4 Deployment

A Deployment binds:

- immutable strategy revision;
- named instrument roles;
- static or future dynamic Instrument Scope;
- data-provider bindings;
- execution broker/account;
- research, signal, paper, or live mode;
- capital allocation;
- sizing policy;
- execution product policy;
- order and protection policy;
- schedule;
- provider capability receipt;
- resource plan;
- exact market-rulebook and adapter versions.

## 3.5 Execution Product Policy

An Execution Product Policy answers:

> Given an economic signal, what tradable product should express it and under what selection, liquidity, risk, and order constraints?

Examples:

```text
Cash delivery
Cash intraday
MTF
Front-month future
Selected single-leg index option
Later multi-leg derivative structure
```

This is distinct from the Strategy itself.

A strategy may be evaluated on RELIANCE, NIFTY, India VIX, and order flow, while the execution policy chooses:

- RELIANCE cash;
- RELIANCE MTF;
- RELIANCE future;
- a selected RELIANCE option later;
- a NIFTY or SENSEX option in the certified options release.

## 3.6 Portfolio Admission

Signal generation and portfolio admission remain separate.

A valid signal may still be rejected or resized because of:

- insufficient cash or margin;
- strategy/deployment allocation limits;
- simultaneous reservation conflicts;
- sector or factor concentration;
- correlated exposure;
- gross/net exposure limits;
- liquidity;
- provider capability;
- protection capability;
- stale data;
- resource limits.

## 3.7 Position, tranche, and inventory identity

The current invariant remains:

> A dynamic selector may change after entry. A held instrument’s identity may not.

The architecture should distinguish:

```text
Position Campaign / Economic Position
└── Position Slice / Tranche
    └── Exact Canonical Instrument Filled
```

V1 does not need advanced multi-contract pyramiding, but storage and accounting should not assume forever that one economic thesis can only own one physical instrument row.

## 3.8 Data Observation and Evidence

Every decision-relevant observation should be capable of carrying:

```text
value
source
canonical instrument or series
observed_at
effective_at
published_at where relevant
ingested_at
revision/version
freshness
validity
semantic unit
```

Every meaningful result should preserve:

```text
strategy revision
node versions
dataset versions
instrument mappings
market-rulebook version
provider/adapter versions
cost and slippage models
search history
validation policy
execution receipts
```

---

# 4. Release architecture

The roadmap now has explicit intermediate releases because some capabilities are valuable but too dangerous or broad to force into initial V1.

## 4.1 V1 — complete the ten-phase core product

V1 proves the full research-to-endpoint loop with a coherent web product.

V1 must include or preserve:

- typed, immutable strategy identity;
- first-party node system;
- arbitrary and cross-instrument data inputs;
- backtesting and bounded optimisation;
- parameter-neighbourhood analysis;
- locked OOS;
- walk-forward;
- basic Monte Carlo and execution stress;
- exact evidence persistence;
- research, signal, and controlled execution endpoints;
- Phase 5 position sizing and deterministic capital admission;
- provider/data/execution separation;
- canonical instrument identity;
- point-in-time market truth;
- basic India VIX data and reusable derived nodes where the data contract is reliable;
- asset-class-neutral economic intent;
- safe static instrument bindings through a future-compatible Instrument Scope seam;
- launch presets created near release rather than allowed to distract core architecture work.

V1 does **not** require:

- public Dynamic Watchlists;
- full Workflow builder;
- Strategy Diagnostics and recommendations;
- advanced Kelly/distribution calibration;
- stock or commodity option execution;
- multi-leg derivatives;
- dynamic cross-contract options pyramiding;
- exchange queue-position simulation;
- marketplace;
- AI Research Agent;
- ML-oriented model nodes;
- broad international support.

## 4.2 V1.1 — Dynamic Watchlists and bounded Universe product

V1.1 introduces the user-facing Dynamic Watchlist / Dynamic Universe flow:

- filter;
- rank;
- top-K;
- refresh schedule;
- candidate lifecycle;
- hysteresis;
- minimum residency;
- research vs execution eligibility;
- resource budgets;
- open-position leave policy;
- durable snapshots and audit receipts.

It may also expose bounded improvements to the platform options-selector configuration, but not unlimited user-authored chain computation by default.

## 4.3 V1.5 — certified options execution

Options execution is removed from the V1 release gate and placed behind a dedicated certification release.

V1.5 should initially support only a deliberately narrow, liquid, single-leg index-options surface where market truth, data, liquidity checks, broker behavior, and selector semantics can be proven.

The release candidate scope is:

- NIFTY index options;
- BANKNIFTY index options where currently listed expiries and liquidity qualify;
- SENSEX index options;
- only actually listed weekly/monthly/other approved expiries according to the point-in-time market rulebook;
- one-leg entry and exact-held-contract exit;
- no implicit cross-contract pyramiding;
- platform selector strongly recommended and available by default;
- custom selector allowed only through declared, preflighted contracts;
- conservative order and liquidity policies.

As of 24 August 2026, the exchange specifications indicate that NIFTY has weekly and monthly options, SENSEX has weekly and monthly options, and BANKNIFTY’s standard listed cycle is monthly/quarterly rather than a normal weekly cycle. Strategy OS must use current and historical exchange contract truth rather than hard-code the product labels in this paragraph.

Stock options, commodity options, complex spreads, calendar spreads, and broad advanced derivative execution remain later work.

## 4.4 V2 — discovery, orchestration, intelligence, and diagnostics

V2 focuses on:

- full Dynamic Universe expansion;
- deterministic Strategy Workflows;
- fundamentals and events;
- Strategy Diagnostics and Counterfactual Lab;
- richer derivatives and OI intelligence;
- derivative-informed Universes;
- chart annotations as semantic strategy inputs;
- TradingView/external-signal boundaries;
- strategy and workflow version analytics;
- deeper VIX and volatility intelligence;
- internal literature-informed recommendations grounded in Strategy OS evidence;
- stronger multi-asset and portfolio research.

## 4.5 V3 — ecosystem, ML, marketplace, and scale-led expansion

V3 is demand-led and may include:

- Strategy Asset Marketplace;
- Managed Model Allocation marketplace through an appropriate legal/regulated structure;
- platform-published strategies;
- creator economics;
- ML/model-derived nodes, including Kronos-like references;
- AI Research Agent;
- portfolio-of-strategies allocation;
- advanced distribution-based sizing and portfolio Kelly;
- international markets and brokers;
- MT5 or other ecosystem bridges;
- institutional data and connectivity where real customers require them;
- deeper queue/fill/capacity modeling where data and strategy horizons justify it.

---

# 5. V1 ten-phase discipline and immediate scope corrections

V1 remains a ten-phase implementation programme. This memo does not authorize agents to invent a replacement phase plan from the older August 11 schedule.

The current owner decision is explicit:

> Position sizing, capital allocation, and simultaneous-admission correctness belong in V1 Phase 5.

Phase 5 must therefore treat sizing as a first-class system rather than a quantity field.

## 5.1 Phase 5 minimum sizing contract

V1 should support:

- fixed units;
- lots;
- fixed capital;
- percentage of equity or deployment allocation;
- risk percentage;
- stop-distance sizing;
- volatility sizing;
- minimum/maximum caps;
- lot and tick constraints;
- fee/slippage buffers;
- deterministic quantity rounding;
- atomic or transactionally safe capital reservation;
- simultaneous candidate admission with stable tie-breakers;
- persistent sizing/admission receipts.

The architecture should permit a sizing node to consume a dynamic numeric input and produce a target quantity/risk request, even if advanced adaptive sizing is deferred.

## 5.2 V1 options correction

Previous documents treated weekly-options execution as a canonical V1 acceptance scenario. The latest owner decision narrows this:

- options data structures, selector semantics, contract truth, and execution-product separation remain important architectural work;
- broad live options execution is **not** a V1 release gate;
- certified index-options execution moves to V1.5;
- V1 should not be delayed by stock-option, commodity-option, multi-leg, or cross-contract pyramiding complexity.

## 5.3 V1 Dynamic Watchlist correction

V1 should preserve a generic Instrument Scope / Universe reference, but the public Dynamic Watchlist product is V1.1.

Do not build the full filter/rank/refresh UI in V1.

Do not persist static watchlists in a way that forces every deployment and strategy record to assume a permanent fixed array forever.

## 5.4 V1 presets correction

Presets remain a launch requirement for onboarding but are not an architecture workstream.

They can be produced near launch because they are normal Strategy OS objects:

```text
create
→ validate
→ document
→ bundle
```

Core development should not repeatedly reopen template discussions before the launch-content phase.

## 5.5 V1 recommendation correction

Strategy Diagnostics, automated counterfactual suggestions, and literature-informed recommendation intelligence are V2.

V1 should retain the evidence required later:

- branch attribution;
- long/short attribution;
- trade-level reasons;
- regime/time/instrument breakdowns;
- costs/slippage by branch;
- exact strategy and candidate identity.

It should not build the recommendation system now.

## 5.6 V1 pyramiding and downsizing correction

Previous documents treated broad pyramiding primitives as V1 must-have scope. The latest owner decision supersedes that release requirement.

V1 must still support safe position closure, exact inventory ownership, and whatever basic partial reduction is required by its approved execution paths. It should preserve a future-compatible target-position and tranche/lineage seam during Phase 5.

However, the following are not V1 release gates:

- polished user-configurable pyramiding workflows;
- adaptive confidence-driven upsizing and downsizing;
- repeated intraday rebalance policies;
- options additions that may resolve a different contract;
- multi-contract campaign analytics.

These can be added after the sizing, reservation, position, and evidence foundations are proven.

---

# 6. Dynamic Watchlists / Dynamic Universes — V1.1 product model

## 6.1 User interpretation

Before deployment, the user chooses:

```text
Where should this strategy run?

A. Fixed Instruments
B. Dynamic Watchlist
```

### Fixed Instruments

The user explicitly selects one or more instruments.

### Dynamic Watchlist

The user configures an eligibility and ranking policy that refreshes on a declared schedule.

The strategy is then evaluated against the selected candidates.

## 6.2 Dynamic Watchlist setup page

The setup flow should ask for:

### Base market scope

Examples:

- all NSE equities;
- all NSE F&O underlyings;
- a sector;
- a user watchlist;
- a provider-supported set;
- later a derivative contract or underlying universe.

### Eligibility filters

Examples:

- price range;
- market cap;
- average traded value;
- minimum history;
- listed/tradable state;
- broker execution support;
- technical conditions;
- fundamental conditions later;
- event exclusions later;
- derivative-derived conditions later.

### Ranking

Examples:

- relative volume;
- momentum;
- volatility expansion;
- liquidity;
- execution-cost estimate;
- sector-relative strength;
- option OI or IV features later.

### Selection

- top-K;
- bottom-K;
- percentile;
- per-sector quota;
- maximum active candidates;
- minimum score;
- tie-breaker.

### Refresh policy

- once per day;
- once per week;
- session open or custom market time;
- bar interval;
- event-driven later;
- manual refresh.

### Churn controls

- separate enter and leave thresholds;
- minimum residency;
- debounce;
- cooldown;
- ranking persistence;
- maximum replacements per refresh.

### Resource budget

- maximum candidates evaluated;
- maximum expensive features;
- maximum deep subscriptions;
- maximum concurrent research jobs;
- maximum active deployments;
- provider quota ceiling.

### Open-position leave policy

If an instrument leaves the Dynamic Watchlist:

```text
NO_NEW_ENTRIES
CONTINUE_NORMAL_MANAGEMENT
CONTROLLED_EXIT
REQUIRE_APPROVAL
```

Universe membership must not erase or misattribute an open position.

## 6.3 Candidate lifecycle

A candidate should have durable identity and explicit state, for example:

```text
DISCOVERED
QUALIFIED
RANKED
SELECTED
RESEARCH_PENDING
RESEARCH_PASS
RESEARCH_FAIL
ADMISSION_PENDING
ADMITTED
REJECTED
ACTIVE
LEFT_UNIVERSE
RETIRED
```

The full Workflow state machine remains V2, but V1.1 Dynamic Watchlists need enough state to make refreshes idempotent and explainable.

## 6.4 Research Universe vs Execution Universe

The Dynamic Watchlist may research more instruments than it can execute.

Example:

```text
Research Universe:
All NSE equities

Execution Universe:
Only F&O underlyings supported by the selected broker and liquidity policy
```

This prevents broker limitations from defining the user’s research worldview.

## 6.5 Staged evaluation

Dynamic Watchlists should use staged filtering:

```text
Stage 1: cheap static/reference filters
Stage 2: bar-level technical filters
Stage 3: expensive live/derivative/event data
Stage 4: research and portfolio admission
```

The planner should compile this execution order rather than evaluate every expensive condition over every symbol.

## 6.6 Derivative-informed Dynamic Watchlists

A future Dynamic Watchlist may rank **underlyings** using derivative data:

- IV percentile;
- skew;
- futures basis;
- OI migration;
- option liquidity;
- derivative volume concentration;
- put/call structure.

The output may still be:

```text
ranked_set<Underlying>
```

The strategy may then trade the equity, MTF, future, or an option chosen by the execution-product selector.

A more advanced version may output actual derivative contracts, but that should remain a separate typed Universe mode.

---

# 7. Redis and stateful runtime architecture

## 7.1 Decision

Redis is a strong candidate for Strategy OS’s **hot operational-state and coordination layer**, especially for Dynamic Watchlists, stateful runtime behavior, shared calculations, leases, cooldowns, rank sets, and event fan-out.

Redis must **not** become the sole authoritative record for money, strategy identity, order lifecycle, or evidence.

The core rule is:

> PostgreSQL/durable storage owns truth. Redis accelerates and coordinates recoverable operational state.

## 7.2 Storage responsibility split

### PostgreSQL or another transactional durable database — authoritative

Use for:

- strategy definitions and revisions;
- Universe definitions and revisions;
- Workflow definitions and revisions;
- deployment definitions;
- provider bindings;
- durable Universe snapshots;
- candidate decisions and reasons;
- orders, fills, positions, and reconciliation;
- capital allocation and reservation ledger;
- sizing/admission receipts;
- approvals;
- audit history;
- ownership and tenancy;
- marketplace provenance later.

### Object storage / durable artifact store — authoritative for large artifacts

Use for:

- imported datasets;
- backtest artifacts;
- optimisation result bundles;
- large evidence reports;
- converted local research documents where appropriate;
- model artifacts later.

### Redis — hot, recoverable operational state

Use for:

- current Dynamic Watchlist membership;
- candidate rank sets;
- refresh leases and deduplication keys;
- cooldowns, debounce, hysteresis, and minimum-residency timers;
- hot workflow/candidate lookup;
- stateful node checkpoints where cross-worker access is required;
- current session state;
- subscription registries;
- shared indicator/result caches;
- rate limits and resource semaphores;
- idempotency markers;
- job dispatch and consumer coordination where appropriate;
- ephemeral UI/live-state fan-out;
- hot provider capability/status state;
- current market snapshots where loss can be reconstructed.

### In-process memory — hottest execution state

Use for:

- per-event incremental indicator state;
- current book reducers;
- latency-sensitive strategy evaluation;
- local pending computation;
- derived features used within one runtime worker.

Do not force every tick or every node update through a remote Redis round trip. Redis should coordinate workers and persist/recover operational checkpoints, not become the inner loop of every indicator.

## 7.3 Dynamic Universe use of Redis

A practical V1.1 shape is:

```text
UniverseDefinition + Revision          → PostgreSQL
Scheduled Refresh Job                  → durable job record
Raw candidate computation              → worker/runtime
Ranked candidates                       → Redis sorted set
Membership / residency / cooldown       → Redis hashes/sets with TTL
Durable UniverseSnapshot                → PostgreSQL/object artifact
Candidate decision receipts             → PostgreSQL
Events for downstream workers           → Redis Stream or durable queue
UI updates                              → Pub/Sub or websocket fan-out
```

Redis keys must include:

```text
tenant_id
universe_revision
snapshot_id or session_id
instrument identity
semantic version where relevant
```

No cross-tenant shared key may expose private strategy or candidate state.

## 7.4 Streams, Pub/Sub, and queues

Use Pub/Sub only for ephemeral fan-out where message loss is acceptable, such as:

- UI invalidation;
- noncritical presence/status;
- refresh notifications that can be re-read from durable state.

Use Redis Streams or another durable queue for work that needs:

- consumer groups;
- replay;
- acknowledgements;
- retry;
- ordered event processing within a declared scope.

Even when Streams are used, the durable business record must still land in the authoritative database where financial or audit correctness matters.

## 7.5 Locks, leases, and capital correctness

Redis leases are suitable for:

- preventing duplicate Universe refreshes;
- one-worker ownership of a candidate evaluation;
- scheduled-task coordination;
- nonfinancial deduplication.

Do not make a distributed Redis lock the only protection for:

- capital reservation;
- order admission;
- fill accounting;
- position ownership;
- irreversible money movement.

Those require a transactional authoritative ledger, stable idempotency keys, and recovery-safe state transitions.

Redis may provide a fast reservation preview or contention signal, but the final accepted reservation must be committed transactionally.

## 7.6 Failure and recovery invariant

If Redis is lost or flushed:

- no strategy definition is lost;
- no order or fill is lost;
- no position ownership is lost;
- no capital reservation truth is lost;
- no research evidence is lost;
- no approval is lost;
- Dynamic Watchlists rehydrate from the latest durable snapshot and definitions;
- stateful runtimes enter a declared recovering/warming state;
- new entries may be blocked until required state is restored;
- risk-reducing exits remain possible where safe data and execution paths exist.

This should be an acceptance test.

## 7.7 Persistence, availability, and eviction

Redis persistence and replication may improve recovery, but they do not change the responsibility split.

Operational requirements should include:

- explicit AOF/RDB policy;
- replication/high-availability plan appropriate to release scale;
- backups where justified;
- memory ceilings;
- dedicated key namespaces;
- `noeviction` or carefully separated instances for operational keys that cannot disappear unpredictably;
- TTL only where expiry is part of the data contract;
- metrics for memory, latency, evictions, reconnects, stream lag, and blocked consumers.

## 7.8 Adoption boundary

Redis is not a V1 release requirement merely because it is architecturally attractive.

Adopt it when one or more measured needs exist:

- multiple runtime workers need shared hot state;
- Dynamic Watchlists require ranked sets and leases;
- job coordination exceeds the current durable-job system;
- subscription sharing needs cross-process coordination;
- latency or database load demonstrates clear benefit.

Before production adoption:

1. define the state-store interface;
2. write failure/recovery tests;
3. benchmark representative loads;
4. review the exact Redis distribution and license selected;
5. decide single-instance/Sentinel/Cluster topology only from measured scale and availability needs.

---

# 8. Asset-class-neutral strategy and execution architecture

Strategy OS is not an options platform.

It must support or remain capable of supporting:

- cash equities;
- intraday equities;
- MTF;
- futures;
- options;
- later multi-leg derivatives and portfolio structures.

The architecture should separate:

```text
Instrument Scope / Universe
        ↓
Strategy Signal on Economic Instrument(s)
        ↓
Desired Direction / Risk / Horizon
        ↓
Execution Product Policy
        ↓
Exact Tradable Instrument Resolver
        ↓
Portfolio Admission
        ↓
Order Planning and Execution
```

## 8.1 Cash and intraday

Primary concerns:

- quantity/notional;
- spread and slippage;
- market/session rules;
- product eligibility;
- capital and settlement;
- session exit where applicable.

## 8.2 MTF

Additional concerns:

- provider support;
- financing/carry;
- margin requirements;
- overnight eligibility;
- product-specific restrictions;
- account capability.

## 8.3 Futures

Additional concerns:

- contract multiplier;
- margin;
- expiry;
- actual tradable contract;
- continuous research series versus executable contract;
- roll policy;
- basis;
- slippage and depth.

## 8.4 Options

Additional concerns:

- strike and expiry selection;
- DTE;
- moneyness and delta;
- IV and Greeks;
- spread and depth;
- volume and OI;
- quote freshness;
- nonlinear risk;
- rapidly changing exposure;
- contract churn;
- path-dependent additions and exits;
- market impact and fill uncertainty.

This is why options execution receives a dedicated V1.5 certification boundary.

---

# 9. Options strategy and execution architecture

## 9.1 Central product insight

Most options traders do not base an entire strategy only on the option premium series.

A common structure is:

```text
Underlying / index / VIX / market structure / order flow
        ↓
Economic directional or volatility thesis
        ↓
Option execution policy
        ↓
Exact contract selection
```

Strategy OS must support option-data-driven strategies, but it should not force the strategy signal to be generated from the derivative itself.

## 9.2 Mandatory separation

Use distinct objects or typed layers:

```text
StrategySignal
- economic instrument / underlying
- direction or structure intent
- timestamp
- horizon
- desired risk/exposure
- evidence references

OptionExecutionPolicy
- eligible underlying/index
- expiry policy
- option type
- strike/moneyness/delta policy
- Greek/IV constraints
- liquidity constraints
- order constraints
- fallback/no-trade policy

ResolvedOptionSelection
- exact contract
- exact quote and chain snapshot
- selector revision
- reasons and rejected alternatives
```

## 9.3 Options selector panel

When a user chooses options as the trading product, Strategy OS should present an explicit selector panel.

The product message should be clear:

> Options require an execution-selection policy. Strategy OS provides a first-party selector. Advanced users may define their own declared selector, but deploying options without a valid liquidity, contract, and order policy is unsafe and should not be treated as a normal default.

The platform selector should support, as data and provider capability permit:

- underlying/index;
- call/put;
- listed expiry policy;
- DTE range;
- weekly/monthly/other allowed cycle;
- strike offset;
- ATM/moneyness;
- target delta;
- gamma/theta/vega constraints;
- IV and IV rank/percentile where valid;
- premium range;
- minimum volume;
- minimum OI;
- maximum spread in absolute and percentage terms;
- minimum depth;
- maximum quote age;
- maximum estimated slippage;
- lot size and capital/margin impact;
- order type/limit logic;
- no-trade fallback.

Provider-supplied Greeks and locally derived Greeks must be distinguishable.

## 9.4 Platform selector vs custom selector

The user may choose:

```text
A. Strategy OS Recommended Selector
B. Custom Selector
```

A custom selector must declare:

- required data fields;
- history/freshness requirements;
- evaluation trigger;
- maximum chain window;
- resource class;
- deterministic ranking/tie-breaking;
- missing-data behavior;
- live/research eligibility;
- fallback/no-trade behavior.

Custom logic must not bypass:

- provider capability preflight;
- market-rulebook truth;
- liquidity constraints required by account/platform policy;
- capital admission;
- tenant/resource limits;
- execution authority.

## 9.5 No blind option market entry

The default should not be:

```text
signal → buy whatever is ATM at market
```

A conservative default should prefer:

- valid, sufficiently fresh quotes;
- bounded spread;
- sufficient liquidity/depth;
- explicit slippage tolerance;
- limit or marketable-limit behavior where supported;
- no-trade when a safe contract cannot be resolved.

A user may choose a more aggressive policy only through an explicit, auditable decision and subject to broker/exchange capability.

## 9.6 Selection receipt

Every options entry should preserve:

```text
strategy revision
signal timestamp
underlying state
selector revision
contract-master/rulebook version
candidate contracts considered
rejection reasons
selected contract
quote snapshot
spread/depth/volume/OI
IV/Greeks and their source
estimated slippage
lot and capital impact
provider and adapter version
order policy
```

## 9.7 V1.5 certified scope

V1.5 should target liquid index options first.

The exact allowed contracts must be generated from the point-in-time market rulebook and live provider capability, not from permanent hard-coded assumptions.

Initial product policy:

- NIFTY, BANKNIFTY, and SENSEX index options are the intended certification set;
- only currently listed and sufficiently liquid expiries;
- weekly only where the exchange actually lists weekly contracts;
- monthly/quarterly where listed and supported;
- single-leg directional execution;
- no multi-leg strategy guarantee;
- no stock-option or commodity-option guarantee;
- no cross-contract pyramiding in the first certified release;
- exact-held-contract reductions and exits only.

## 9.8 Multi-leg and specialist analytics

Calendar spreads, verticals, straddles, strangles, volatility surfaces, and multi-leg risk require:

- strategy-level structure identity;
- leg-aware margin and fill modeling;
- partial-leg failure handling;
- net Greek and scenario risk;
- combo-order capability where available;
- complex reconciliation;
- more sophisticated analytics.

Until Strategy OS certifies those semantics, the product may recommend that users validate complex structures with a specialist options analytics platform, for example Sensibull where suitable and currently available. Such a recommendation is not an integrated Strategy OS guarantee.

---

# 10. Position sizing and adaptive capital allocation

## 10.1 V1 Phase 5 foundation

V1 Phase 5 should model:

```text
Account/portfolio hard limits
→ strategy allocation
→ deployment allocation
→ trade sizing request
→ portfolio admission
→ atomic capital reservation
→ admitted target quantity/risk
```

The strategy requests exposure. The portfolio/account layer remains authoritative.

## 10.2 Future conviction-to-capital architecture

A later advanced stack may be:

```text
Typed evidence contributions
→ directional conviction
→ calibrated probability/return distribution
→ sizing policy
→ target position
→ risk and portfolio caps
→ execution delta
```

Evidence may include:

- death cross within a declared window;
- VWAP direction;
- trend/momentum;
- order-book or genuine flow evidence;
- NIFTY movement;
- India VIX regime;
- cross-market confirmation;
- custom declared nodes.

The system should distinguish:

```text
Raw Evidence Score
Calibrated Edge or Probability
Conditional Return Distribution
Kelly or Other Requested Fraction
Final Admitted Fraction
```

A user-defined score is not an objective platform guarantee.

## 10.3 Kelly and other models

Kelly is one optional sizing policy, not the master sizing system.

Future policies may include:

- confidence tiers;
- fixed fractional risk;
- volatility targeting;
- fractional Kelly;
- uncertainty-shrunk Kelly;
- empirical-distribution Kelly;
- drawdown-aware sizing;
- portfolio-level allocation;
- later multivariate Kelly.

Full calibration, distribution mapping, and automated sizing diagnostics belong after V1, likely across V1.x/V2/V3 depending complexity and validation.

## 10.4 Target-position seam

Even if V1 does not expose advanced adaptive sizing, the architecture should prefer:

```text
current position
pending orders
reserved capital
desired target
→ safe execution delta
```

rather than treating every sizing output as an isolated immediate order.

This makes future controlled additions and reductions additive rather than destructive.

---

# 11. Pyramiding, downsizing, and options-specific position complexity

## 11.1 Generic rule

A future sizing policy may increase or decrease target exposure over time.

Any implementation must include:

- maximum additions;
- maximum reductions;
- cooldowns;
- hysteresis;
- minimum meaningful delta;
- daily turnover limits;
- pending-order awareness;
- capital reservation;
- persistent reasons;
- backtest/live parity.

## 11.2 Options complication

If the original option was ATM at entry, it may later be ITM or OTM.

An additional entry could reasonably choose:

- the same held contract;
- the new ATM contract;
- a slightly OTM contract;
- a target-delta contract;
- no addition because the original structure no longer exists.

Those are different economic policies.

A reduction is not symmetrical. It must close actual held inventory unless the strategy explicitly intends to open a new short leg.

Therefore:

> Selection rules may open or add exposure. Reduction rules must resolve against actual held positions unless a distinct new-position intent exists.

## 11.3 Release boundary

V1/V1.5 do not need advanced cross-contract options pyramiding.

The first certified options release may restrict:

- no pyramiding; or
- additions only to the exact held contract; and
- reductions only from exact held inventory.

The persistence model should still permit future position campaigns with multiple exact tranches.

---

# 12. India VIX and reusable derived-data architecture

## 12.1 V1 bounded support

India VIX should enter as a normal point-in-time data series with:

- source;
- timestamp;
- freshness;
- historical provenance;
- provider capability;
- cross-instrument role binding.

V1 can expose generic derived nodes such as:

- change;
- percent/log return;
- rolling mean/EMA;
- distance from mean;
- z-score;
- percentile/rank;
- slope;
- shock;
- consecutive rise/fall;
- threshold cross;
- regime with hysteresis;
- VIX versus realized-volatility spread/ratio where inputs are valid.

## 12.2 User-defined use cases

VIX may be used as:

- regime input;
- entry/exit filter;
- sizing/risk modifier;
- mean-reversion signal;
- cross-market confirmation;
- input to another instrument’s strategy.

Example:

```text
India VIX unusually low
AND RELIANCE makes an extreme move
AND RELIANCE option liquidity/IV policy qualifies
→ evaluate an option-selling or directional hypothesis
```

Strategy OS should make the relationship testable without asserting that the relationship is universally valid.

## 12.3 Generic data-domain lesson

The same architecture should later support:

- yield curves;
- spreads;
- breadth;
- macro series;
- credit indicators;
- DV01 and duration-related data;
- custom proprietary factors.

V1 need not implement those domains. It must avoid assuming that every input is only an OHLCV scalar series.

---

# 13. Queueing theory, low latency, and what not to build yet

Queueing appears in three different systems.

## 13.1 Research/job queues

V1 already needs:

- durable heavy jobs;
- concurrency limits;
- cancellation;
- retries;
- resumability;
- user/resource quotas;
- deterministic job identity.

## 13.2 Market-data/runtime queues

The runtime needs:

- dependency-aware incremental evaluation;
- trigger-specific nodes;
- backpressure;
- subscription sharing;
- priority/QoS;
- bounded option-window churn;
- separate strategy and UI update rates.

## 13.3 Exchange order queues

Advanced execution models may later include:

- queue position;
- fill probability;
- partial-fill timing;
- cancel/replace effects;
- latency;
- adverse selection;
- book evolution while resting.

This is important for passive, lower-latency, and illiquid strategies, especially options. It is too complex and data-dependent to build before product validation.

## 13.4 Preserve now

Record enough order lifecycle truth for future modeling:

```text
decision_time
intent_created_time
risk_admitted_time
order_submitted_time
broker_ack_time
exchange_ack_time where available
first_fill_time
last_fill_time
cancel_requested_time
cancel_confirmed_time
modifications
partial fills
visible quote/depth where available
fill/slippage model version
provider/adapter version
```

Keep pluggable:

```text
FillModel
LatencyModel
SlippageModel
```

Do not hard-code immediate fills as a universal truth.

---

# 14. Research validity and industrial-standard comparison programme

Backtesting and validation are mature disciplines. Strategy OS should not invent correctness standards in isolation.

A dedicated advanced subagent should produce a **Research Validity and Backtest Semantics packet** rather than generic repository summaries.

## 14.1 Required comparison areas

### Causality and data truth

- future leakage;
- completed/forming bars;
- cross-timeframe alignment;
- cross-instrument skew;
- survivorship bias;
- delistings;
- corporate actions;
- point-in-time universes;
- futures/options contract identity.

### Execution simulation

- market/limit/stop semantics;
- intrabar ambiguity;
- bid/ask versus last-price fills;
- partial fills;
- latency;
- cancel/replace;
- spread;
- slippage;
- fees;
- market impact;
- options liquidity.

### Validation procedure

- locked OOS;
- walk-forward;
- nested selection where required;
- purging/embargo where appropriate;
- Monte Carlo method identity;
- parameter neighborhoods;
- multiple-testing population;
- DSR/PBO where valid;
- holdout contamination.

### Reproducibility

- deterministic seeds;
- parallelism;
- exact data/engine identity;
- caches;
- restart/resume;
- failed-trial handling;
- candidate lineage.

## 14.2 Required outputs

- Strategy OS research invariants;
- semantics matrix;
- golden acceptance scenarios;
- adversarial tests;
- performance benchmarks;
- explicit rejected patterns;
- ADRs;
- implementation gaps and migration plan.

---

# 15. External references and competitor intelligence

Every external source must be reviewed for exact commit, license, reusable patterns, unsafe assumptions, and integration risk.

## 15.1 Immediate V1/V1.x engineering references

### KalshiMarketMaker

Use for:

- market-worker lifecycle;
- selection/deselection;
- safe cleanup;
- retry/backoff;
- order cancellation;
- subscription lifecycle.

Do not treat it as a complete canonical order-book engine without proof.

### Vibe-Trading

Use for:

- serious adjacent competitive intelligence;
- research workspace architecture;
- provenance and durable research state;
- India-market and options comparison;
- agent-tool boundaries.

Do not infer that Strategy OS needs AI workflows in V1.

### AKQuant

Use for:

- computation kernels;
- batch/stream parity;
- indicator golden tests;
- walk-forward and factor primitives;
- performance spikes.

### PaperTrade-India

Use for:

- Indian market-rule test scenarios;
- costs and settlement;
- broker-like rejections;
- idempotency;
- ledgers;
- recovery and concurrency cases.

Verify every rule against official point-in-time sources.

### RQAlpha

Use for:

- modular simulation hooks;
- risk and transaction-cost interfaces;
- event-loop boundaries.

Treat license/commercial constraints separately.

### Quant_modeller

Use for:

- OOS, walk-forward, Monte Carlo, robustness, and noise-injection comparison;
- validation-rigor test ideas.

### PentPort

Investigate specifically for:

- paper account state;
- concurrency;
- order/capital admission;
- database contention;
- simultaneous user/runtime behavior;
- ledger and recalculation patterns.

Do not reduce its relevance to competitions or growth loops.

### fxDreema

Use for:

- visual strategy-builder UX;
- block discovery;
- progressive disclosure;
- reusable logic;
- variable handling;
- connection feedback;
- nonprogrammer execution semantics.

It validates demand for visual strategy construction; it does not erase Strategy OS’s broader evidence and operating-system thesis.

## 15.2 V1.1/V2 references

### InStock / myhhub-stock

Use when designing Dynamic Watchlists and broad screener/filter UX.

### PickMyTrade

Use for external-signal/webhook and broker-automation UX in V2. External signals must still enter normal authority, risk, and admission paths.

### awesome-systematic-trading

Use as a discovery index and knowledge-base seed, not as an authority.

### AlphaInsider, Oxfordstrat, QuantifiedStrategies

Use for:

- strategy-catalog research;
- preset inspiration;
- evidence presentation;
- future creator/marketplace research.

Any product strategy implementation must be independently formalized, attributed where appropriate, and validated through Strategy OS.

### OpenBB

Use for provider normalization, schema design, data-to-agent surfaces, and capability architecture. Any production integration requires a deliberate license decision.

### AnyDoc

Use as a local document-conversion component, not as a knowledge-validation engine.

## 15.3 V3 references

### Kronos

Use for future:

- model-derived feature nodes;
- probabilistic forecasts;
- regime embeddings;
- anomaly scores;
- ML research inputs.

Today, only preserve a clean model-node contract and run narrow isolated spikes where useful.

### xalpha

Revisit for portfolio/account/marketplace-related work.

### QuantTradingOS and related agent frameworks

Use for agent context, domain-skill retrieval, and research orchestration prior art, not as a replacement for Strategy OS semantics.

---

# 16. Local books and research knowledge pipeline

The books corpus is an **internal local-LLM research asset**, not a customer product.

The intended flow is:

```text
Private/local source documents
→ local conversion
→ local retrieval/context
→ extracted concepts, formulas, methods, failure modes, and UX insights
→ independent Strategy OS verification
→ internal docs, tests, or later recommendations
```

No book content is exposed to users through Strategy OS.

Raw source documents should stay outside normal shared product repositories and customer-facing databases.

Suggested local structure:

```text
books/
├── catalog/
├── private-source-manifests/
├── converted-private/
├── extracted-claims/
├── formulas/
├── research-methods/
├── failure-modes/
├── strategy-hypotheses/
├── ux-insights/
├── test-candidates/
└── implementation-notes/
```

Extracted material should distinguish:

```text
SOURCE CLAIM
AUTHOR OPINION
FORMULA
RESEARCH METHOD
IMPLEMENTATION PATTERN
KNOWN FAILURE MODE
STRATEGY HYPOTHESIS
UX INSIGHT
```

and:

```text
STRATEGY OS VERIFIED
PARTIALLY VERIFIED
UNVERIFIED
CONTRADICTED
NOT APPLICABLE
```

The later recommendation system should combine literature knowledge with the exact user strategy and Strategy OS evidence. It should never treat source authority as a substitute for testing.

---

# 17. Presets and onboarding

Presets should be prepared near launch because they are lightweight normal strategy objects.

Their role is:

- remove the blank canvas;
- teach graph semantics;
- show cross-instrument inputs;
- demonstrate backtesting and validation;
- allow safe experimentation;
- communicate the difference between research, signal, and execution.

A small launch set may include:

- starter z-score + trend filter;
- trend following;
- opening-range breakout;
- VWAP mean reversion;
- momentum/relative strength;
- India VIX regime filter;
- OI-confirmed research example where data is supported;
- research-only cross-market example.

Every template should carry an honest status such as:

```text
EDUCATIONAL
PLATFORM BACKTESTED
OOS VALIDATED
WALK-FORWARD VALIDATED
PAPER OBSERVED
FORWARD OBSERVED
```

Templates are not guaranteed alpha.

---

# 18. Strategy Diagnostics and Counterfactual Lab — V2

V2 may detect:

- long/short asymmetry;
- regime concentration;
- time-of-day concentration;
- instrument concentration;
- cost/slippage drag;
- unstable parameter regions;
- excessive turnover;
- insufficient evidence;
- one-instrument domination;
- correlated portfolio exposure;
- exit inefficiency;
- data-quality weaknesses.

Canonical example:

```text
VWAP mean-reversion strategy
- long below VWAP - 2 ATR
- short above VWAP + 2 ATR

Observed:
- long branch positive
- short branch produces excessive trades and degrades results

Recommendation:
- create a long-only candidate
- label it post-hoc
- preserve exact graph diff
- require new frozen validation
```

The system must never silently mutate an approved or deployed strategy.

A recommendation produces a new candidate revision with a declared validation plan.

---

# 19. Strategy Workflows — V2

Workflows are deterministic lifecycle orchestration.

Potential states:

```text
DISCOVERED
RESEARCH_PENDING
RESEARCHING
RESEARCH_PASS
RESEARCH_FAIL
AWAITING_APPROVAL
ADMISSION_PENDING
ADMITTED
REJECTED
DEPLOYING
ACTIVE
INVALIDATED
RETIRED
FAILED
```

Capabilities:

- branching;
- retries;
- deadlines;
- human approval;
- resource budgets;
- time/session semantics;
- portfolio admission;
- durable why-trade/why-not-trade evidence;
- versioning and comparison.

A Workflow may reference a Universe and Strategy; it does not replace either.

---

# 20. Fundamentals, events, chart semantics, and derivative intelligence — V2

## 20.1 Fundamentals

Point-in-time values may include:

- ROCE;
- ROE;
- debt/equity;
- revenue/EPS growth;
- valuation ratios;
- sector-relative percentiles;
- promoter/shareholding changes;
- filing and earnings dates.

Every value must preserve what was knowable at historical time T.

## 20.2 Events

A unified event model may include:

```text
CorporateEvent
EarningsEvent
CorporateActionEvent
ExchangeEvent
MacroEvent
EconomicReleaseEvent
NewsEvent
```

Scheduled-event logic must not pretend to know future unscheduled news.

## 20.3 Chart semantics

Chart objects may later become immutable strategy inputs:

- trendline;
- Fibonacci level;
- support/resistance zone;
- horizontal level;
- chart thesis with TTL/invalidation.

Rendering remains adapter-owned. Strategy OS owns semantic identity and versioning.

## 20.4 Derivatives intelligence

V2 may add:

- multi-strike OI;
- OI topology and wall migration;
- IV rank/percentile;
- skew and term structure;
- option-chain nodes;
- derivative-informed Dynamic Universes;
- visual and machine-readable chain analytics.

These are separate from the narrower V1.5 certified execution scope.

---

# 21. Marketplace and creator economy — V3

The V3 marketplace has two distinct products.

## 21.1 Strategy Asset Marketplace

A creator may sell or license a package containing:

- strategy graph;
- components;
- parameters;
- Universe configuration;
- sizing/risk policy;
- dashboards/layouts;
- documentation;
- evidence profile;
- provider/data requirements.

A buyer may import and modify it according to the license, then run it on their own account/desktop/infrastructure through Strategy OS.

## 21.2 Managed Model Allocation

A creator may keep the strategy private and allow investors to allocate capital to the managed model.

This requires separate treatment for:

- strategy operator;
- investor/account ownership;
- execution authority;
- fee arrangement;
- risk and capacity;
- disclosures;
- permissions;
- jurisdiction-specific legal/regulatory requirements.

It must not be implemented as merely an “Invest” button on a downloadable strategy listing.

## 21.3 Platform economics

Strategy OS may take a cut from:

- strategy sales;
- subscription/access fees;
- creator services;
- managed-model platform economics where legally supported;
- platform-owned strategies.

The platform must disclose whether a strategy is:

```text
PLATFORM_BUILT
THIRD_PARTY_CREATOR
USER_PRIVATE
```

Marketplace recommendations must not secretly favor platform-owned strategies.

## 21.4 Seam now

Current architecture should preserve:

- immutable ownership;
- origin/provenance;
- clone lineage;
- packageable artifacts;
- strategy owner separate from deployment/account owner;
- explicit rights metadata.

Do not build commerce, DRM, public sharing, or managed-capital operation before V3 demand and legal design justify them.

---

# 22. Runtime economics and resource planning

Every strategy/deployment should compile a resource plan containing:

- subscriptions;
- data resolutions;
- history;
- state size;
- event frequency;
- option-window churn;
- compute class;
- storage;
- custom-code limits;
- provider quota use;
- estimated internal cost class.

QoS remains:

```text
P0 existing-position protection and reconciliation
P1 live execution-critical data/evaluation
P2 paper/shadow
P3 interactive research
P4 optimisation/Monte Carlo
P5 UI/nonessential analytics
```

Dynamic Watchlists and options selectors must be constrained by:

- candidate limits;
- staged filters;
- subscription limits;
- bounded chain windows;
- shared computations;
- cache identity;
- tenant/data-license boundaries;
- resource ceilings.

---

# 23. Migration and no-dead-end rules

The immediate architectural job is not to build all future features. It is to eliminate destructive assumptions.

## 23.1 Preserve now

### Instrument Scope

Static bindings should be representable through a generic future-compatible scope reference.

### Execution Product Policy

Do not embed option selection directly inside generic strategy signal logic or broker adapters.

### State-store interface

Stateful runtime code should not depend directly on Redis-specific commands throughout core semantics. Use bounded adapters/repositories.

### Durable truth

Money, orders, positions, strategy versions, approvals, and evidence must remain durable and reconstructible without Redis.

### Position lineage

Do not assume one economic thesis can own only one physical instrument forever.

### Cross-instrument roles

Observed, underlying, regime, and execution instruments must remain separable.

### Data domains

Do not assume all strategy inputs are candles or update at one cadence.

### Provider capability

Data and execution roles remain separate and capability-driven.

### Replay

Replay should be extensible beyond candles to:

- events;
- Universe refreshes;
- selector decisions;
- order lifecycle;
- state transitions.

### Fill/latency models

Keep model identity pluggable even if V1 ships simple versions.

## 23.2 Do not build now

- full Dynamic Universe builder in V1;
- full Workflow builder in V1;
- Redis Cluster by default;
- exchange queue-position simulator;
- stock/commodity options execution;
- multi-leg options;
- advanced cross-contract pyramiding;
- recommendation engine;
- ML node marketplace;
- public strategy marketplace;
- managed-capital platform;
- institutional connectivity without demand.

---

# 24. Canonical acceptance scenarios

## Scenario A — reusable static equity strategy

One strategy uses SELF and is researched across many equities, then statically deployed with exact bindings, sizing, stops, and attribution.

## Scenario B — deterministic concurrent capital admission

Two deployments signal simultaneously with insufficient aggregate capital.

The system:

- uses one consistent account snapshot;
- applies a versioned admission policy;
- reserves capital transactionally;
- resizes or rejects deterministically;
- records reasons;
- remains correct after restart.

## Scenario C — cross-market VIX strategy

A strategy observes:

- India VIX;
- NIFTY;
- RELIANCE;

and trades a chosen supported execution product while enforcing timestamp skew, freshness, and provider provenance.

## Scenario D — V1.1 Dynamic Watchlist

A daily Universe:

- scans a defined market;
- applies cheap then expensive filters;
- ranks candidates;
- selects top-K;
- persists a snapshot;
- uses hysteresis and residency;
- explains entry/leave decisions;
- does not corrupt open positions;
- rehydrates after Redis loss.

## Scenario E — V1.5 liquid index option

A strategy signal is generated from an index/underlying and regime inputs.

The options policy:

- resolves only actually listed contracts;
- applies delta/IV/liquidity/spread/freshness constraints;
- chooses an exact contract;
- uses a conservative order policy;
- records a selection receipt;
- closes only the exact held contract;
- blocks execution when no safe contract qualifies.

## Scenario F — Redis recovery

Redis becomes unavailable or loses hot state.

The system:

- preserves all durable financial and evidence truth;
- blocks unsafe new entries where state is incomplete;
- reconstructs Dynamic Watchlists from durable definitions/snapshots;
- restores runtime state through declared recovery procedures;
- continues or exits existing positions according to explicit degraded-state policy.

## Scenario G — research-validity packet

A fixed strategy is run through:

- baseline;
- bounded optimisation;
- parameter neighbourhood;
- locked OOS;
- walk-forward;
- Monte Carlo;
- cost/slippage stress;
- complete trial lineage.

The system may conclude that no candidate improves the baseline.

---

# 25. Codex architecture and research directive

When this memo is attached to Codex, the immediate task is not to implement every release.

Codex must:

1. read all nine canonical product/architecture documents first;
2. treat this memo as the current scope/timing authority;
3. print and verify the exact repository/worktree context;
4. audit current code before proposing replacement architecture;
5. identify fixed-watchlist assumptions;
6. identify whether an `InstrumentScope` seam already exists;
7. identify whether strategy signal and execution-product selection are separated;
8. audit the existing options engine in detail rather than assuming its semantics;
9. map current option selector fields, data sources, ranking, liquidity checks, and failure modes;
10. verify exact-held-contract identity across backtest, paper, live, restart, reconciliation, and exits;
11. identify whether current position storage can later support multiple exact tranches;
12. audit Phase 5 sizing and capital-reservation contracts;
13. prove deterministic simultaneous admission;
14. assess whether sizing can consume dynamic numeric inputs and emit target exposure/quantity;
15. assess current VIX data availability and the smallest V1 generic-node implementation;
16. define a state-store abstraction and evaluate Redis as hot operational state, not authoritative financial truth;
17. produce a Redis failure/recovery ADR and tests before adoption;
18. avoid Redis in the per-tick inner loop unless measured evidence justifies it;
19. preserve a future Dynamic Watchlist implementation through additive contracts only;
20. explicitly remove broad options execution from V1 release gates and place certified index options in V1.5;
21. verify current exchange contract availability through official point-in-time sources;
22. run the advanced backtesting/research-validity subagent;
23. review KalshiMarketMaker, Vibe-Trading, AKQuant, PaperTrade-India, RQAlpha, Quant_modeller, PentPort, fxDreema, and the other classified references for their stated purpose;
24. record exact commits, licenses, files, tests, and rejected patterns;
25. preserve options research and selector architecture without building stock/commodity/multi-leg execution now;
26. preserve Dynamic Universe, Workflow, recommendations, ML, and marketplace seams without implementing their full product surfaces;
27. return every finding as one of:
    - MUST CHANGE IN V1;
    - V1 IMPLEMENTATION ALREADY REQUIRED;
    - V1.1;
    - V1.5;
    - V2;
    - V3 / DEMAND-LED;
    - REJECT;
    - REQUIRES LEGAL OR COMMERCIAL DECISION;
28. provide file-level changes, schema impact, migrations, rollback, tests, and failure modes for every V1 change;
29. explicitly reject premature infrastructure and feature work;
30. keep V1 shippable.

---

# 26. Required ADRs and supporting documents

Codex should create or update bounded ADRs for:

1. **Instrument Scope:** static V1 binding through future-compatible Universe interface.
2. **Redis Responsibility Boundary:** operational hot state versus authoritative durable truth.
3. **Dynamic Watchlist State Model:** definitions, snapshots, membership, ranking, residency, refresh, and recovery.
4. **Strategy Signal vs Execution Product Policy:** asset-class-neutral separation.
5. **Options Selector Contract:** platform selector, custom selector, preflight, and selection receipts.
6. **Options Release Boundary:** V1.5 liquid index options; stock/commodity/multi-leg later.
7. **Position/Tranche Lineage:** exact-held identity and future multi-contract seam.
8. **Phase 5 Sizing and Capital Reservation:** deterministic concurrent admission.
9. **VIX Data and Generic Derived Nodes:** bounded V1 implementation.
10. **Fill/Latency/Slippage Model Identity:** simple now, pluggable later.
11. **Research Validity Standard:** OOS, walk-forward, Monte Carlo, multiple testing, and reproducibility.
12. **Private Knowledge Pipeline:** local-only source material and derived internal knowledge.

---

# 27. Open questions

These do not block the direction but must remain explicit.

1. Which exact static Instrument Scope interface already exists in current code?
2. Does the current options engine operate on underlying signals, option signals, or both?
3. Which Greeks are provider-supplied versus locally calculated?
4. What quote/depth/OI history is reliably available for V1.5 research and paper/live parity?
5. Which brokers can support conservative index-option order semantics and reliable order updates?
6. Should V1.5 initially allow only monthly contracts, or weekly where exchange/provider liquidity is proven?
7. Is same-contract addition permitted in V1.5, or should all option pyramiding be disabled initially?
8. Which database currently owns capital reservation and how are simultaneous signals serialized?
9. What stateful runtime data must survive process restart versus session restart?
10. Which state is shared across workers and therefore benefits from Redis?
11. Does the current durable-job system already cover enough coordination to delay Redis until V1.1?
12. What is the measured event rate and memory cost of Dynamic Watchlist candidates?
13. Which Universe snapshots must be fully persisted for replay and audit?
14. How will derivative-informed Universes distinguish underlying output from contract output?
15. Which VIX provider offers reliable point-in-time history and live freshness for the launch cohort?
16. Which advanced backtesting repositories reveal actual correctness improvements rather than only feature breadth?
17. What legal/regulated structure would be required before managed model allocation can exist?
18. Which marketplace artifacts may be modified after purchase and how is provenance preserved?
19. Which future model nodes should be research-only versus live-eligible?
20. What product demand justifies deeper queue-position modeling?

---

# 28. Final product statement

The updated Strategy OS north star is:

> Strategy OS is a trading decision operating system. It lets a trader formalize a strategy independently of the product used to execute it, bind that strategy to fixed instruments or a later Dynamic Watchlist, validate it against point-in-time market truth, size and admit exposure safely, resolve the correct tradable instrument, and preserve enough evidence to understand exactly why the system did or did not act.

The immediate objective is a correct, coherent V1.

The architectural objective is that V1 becomes the first stable layer of:

```text
V1      — trusted strategy research, evidence, sizing, and endpoints
V1.1    — Dynamic Watchlists / bounded Universes
V1.5    — certified liquid index-options execution
V2      — Workflows, diagnostics, fundamentals/events, richer derivatives
V3      — marketplace, managed models, ML/AI, international and scale-led expansion
```

The governing principle remains:

> Build the minimum complete release now, preserve the right abstractions for later, and never let speculative future capability force either premature implementation or an expensive production rewrite.

---

# Appendix A — Redis implementation notes

Official Redis documentation describes:

- Streams as append-only event structures with consumer/replay capabilities;
- Pub/Sub as an at-most-once messaging mechanism suitable for ephemeral fan-out;
- RDB and AOF persistence options with explicit durability/performance tradeoffs;
- optimistic transactions and distributed-lock patterns;
- replication, Sentinel, and Cluster as different availability/scaling tools.

Reference links:

- <https://redis.io/docs/latest/develop/data-types/streams/>
- <https://redis.io/docs/latest/develop/pubsub/>
- <https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/>
- <https://redis.io/docs/latest/develop/using-commands/transactions/>
- <https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/>
- <https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/>
- <https://redis.io/legal/licenses/>

The exact Redis version, topology, security configuration, and license must be explicitly selected rather than assumed.

# Appendix B — current index-options scope note

As of 24 August 2026, current official exchange specifications indicate:

- NSE NIFTY 50 options include weekly and monthly contracts;
- NSE BANKNIFTY options are listed on monthly and longer cycles rather than the normal weekly cycle;
- BSE SENSEX options include weekly and monthly contracts.

Reference links:

- <https://www.nseindia.com/static/products-services/equity-derivatives-contract-specifications>
- <https://www.nseindia.com/static/products-services/equity-derivatives-nifty50>
- <https://www.nseindia.com/static/products-services/equity-derivatives-banknifty>
- <https://www.bseindia.com/static/markets/derivatives/derireports/contractindex>

These links are current-state references only. Strategy OS must always use point-in-time contract masters and rulebook versions for historical and live operation.
