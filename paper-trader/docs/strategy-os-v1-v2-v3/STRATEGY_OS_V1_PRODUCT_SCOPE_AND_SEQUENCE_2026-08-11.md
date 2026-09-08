# Strategy OS — V1 Product Scope, Sequencing, and Release Plan

**Date:** 11 August 2026\
**Target:** First week of September 2026\
**Status:** Project-management baseline for V1\
**Purpose:** Define exactly what Strategy OS V1 is, what order work should proceed in, what constitutes release readiness, and which attractive ideas must not enter the V1 critical path.

---

# 1. V1 mission

V1 must prove that Strategy OS is a coherent product rather than a collection of trading infrastructure.

The product promise for V1 is:

> **A trader can visually build or modify a strategy, use platform or user-provided data, test it across instruments, run a bounded parameter optimisation, inspect robustness and out-of-sample evidence, preserve the exact research history, and then choose whether the strategy remains research, generates signals, or moves into an authorised execution workflow.**

That is the V1.

V1 is **not** defined by:

- number of brokers;
- number of indicators;
- number of order types;
- AI features;
- a marketplace;
- institutional infrastructure.

---

# 2. Current-state assumptions

This plan assumes the latest project state documented across the August 8–11 handoffs.

The following foundations are treated as substantially real and should be reused rather than rebuilt:

- typed Component IR;
- validation/resolution/content addressing;
- immutable executable graph versions;
- graph editing and persistence;
- research experiment binding;
- exact graph provenance;
- dataset/data-window identity foundations;
- costs/capital/gate identity;
- experiment evidence;
- findings and review history;
- research approval/rejection;
- paper execution integration;
- canonical execution binding;
- strategy/version execution attribution;
- safety and authority separation;
- deterministic test/replay foundations;
- operational cockpit backend;
- existing Zerodha/live-trading machinery outside the new V1 UX.

The cockpit backend was documented as frozen and ready for frontend work.

The existing architecture has already survived explicit stress-testing against:

- cross-instrument logic;
- reusable components;
- richer strategy state;
- multi-provider separation;
- future execution expansion.

Therefore:

> **Do not reopen the foundational architecture without concrete evidence that the new V1 requirements cannot be represented.**

The project has already paid the cost of building the hard architectural base.

V1 should now turn it into a product.

---

# 3. V1 product loop

The user-facing V1 loop is:

```text
START / CONTINUE
      ↓
STRATEGY WORKSPACE
      ↓
BUILD / MODIFY GRAPH
      ↓
SELECT / IMPORT DATA
      ↓
SELECT RESEARCH UNIVERSE
      ↓
BACKTEST
      ↓
OPTIMISATION LAB
      ↓
VALIDATION
      ↓
EVIDENCE / CANDIDATE COMPARISON
      ↓
CHOOSE OUTCOME
 ┌──────────┼───────────┐
 ↓          ↓           ↓
RESEARCH   SIGNAL     PAPER / LIVE*
                         ↓
                    MONITOR / REVIEW

* live only behind explicit proven authority gates
```

If the user can complete this loop cleanly, V1 has achieved its purpose.

---

# 4. V1 scope classification

Use four categories throughout development.

## IMPLEMENT NOW

Required for V1 product identity or release correctness.

## CREATE SEAM NOW

Do not build the whole future capability, but avoid making it expensive to add later.

## SAFE TO DEFER

Valid idea; does not belong on V1 critical path.

## REJECT FOR V1

Actively refuse because it adds risk without proving the product.

---

# 5. V1 — IMPLEMENT NOW

## 5.1 Coherent frontend shell

V1 needs a recognisable product structure.

Primary surfaces:

- Home;
- Strategies;
- Research;
- Live;
- Portfolio/Review.

Secondary surfaces/utilities:

- Data;
- Broker Connections;
- Journal/History;
- Notifications;
- Settings;
- Help.

The product must preserve global → strategy → research-session context.

A strategy must feel like a first-class workspace.

---

## 5.2 Strategy workspace

Each strategy needs an integrated workspace with access to:

- graph;
- parameters;
- data/universe;
- backtests;
- experiments;
- optimisation;
- validation;
- evidence/findings;
- signal/deployment state;
- analytics;
- version history.

V1 does not need every tab to be equally deep.

It does need the object model and navigation to make sense.

---

## 5.3 Starter strategy

Ship a real starter strategy based on the existing z-score + EMA/trend-slope logic.

The starter strategy should:

- be a normal strategy object;
- be cloneable;
- be editable;
- run through the normal backtester;
- be optimisable;
- demonstrate evidence;
- be usable in the supported signal/deployment modes.

Purpose:

> remove the blank-canvas problem and teach the product through the product.

Do not market the bundled strategy as guaranteed alpha.

---

## 5.4 Research plane UX

The research plane remains the product's densest and most differentiated surface.

V1 requirements:

- graph editing remains central;
- major panels can expand/focus;
- instrument/universe selection is visible;
- backtest results are contextual;
- comparison is easy;
- optimisation is an explicit workflow;
- validation results are accessible from the strategy;
- research history persists.

The sketches remain the visual baseline.

Do not simplify the research plane by deleting advanced functionality.

Use progressive disclosure.

---

## 5.5 Backtest responsiveness

Backtest latency is a V1 product requirement.

V1 should distinguish:

### Interactive run

Normal parameter/graph iteration.

Aim for fast reruns through:

- reuse;
- caching;
- incremental work where valid;
- avoiding repeated data parsing;
- avoiding repeated identical computations.

### Heavy research job

User explicitly launches:

- optimisation;
- walk-forward;
- Monte Carlo;
- broad robustness analysis.

These may take substantially longer.

The UI must clearly distinguish intentional heavy jobs from slow normal interaction.

Measure actual latency before introducing major new infrastructure.

---

## 5.6 Bring-your-own-data / CSV

V1 should allow a user to import a historical dataset for research.

V1-facing capability should include:

- CSV upload/import;
- column mapping;
- timestamp mapping;
- timezone;
- interval/frequency metadata;
- instrument or logical-series identity;
- OHLCV recognition where present;
- arbitrary additional feature columns;
- basic data-quality validation;
- durable dataset identity/version;
- date range/row count/quality summary.

The uploaded dataset should enter the normal Strategy OS research flow.

Do not implement a separate "CSV backtester."

Uploaded data is another data source.

---

## 5.7 Cross-instrument research V1

Cross-instrument strategy logic belongs in V1.

Scope it to deterministic historical/bar-oriented research first.

The V1 system should support:

- multiple named series/instruments;
- explicit strategy inputs;
- observed instrument distinct from execution target;
- deterministic timestamp alignment;
- anti-look-ahead rules;
- cross-instrument comparisons/transforms sufficient to prove the model.

Potential initial operations:

- compare;
- ratio;
- spread;
- normalized difference;
- correlation or rolling relationship if already supported cleanly.

Do not make full tick/depth data a dependency.

---

## 5.8 Arbitrary feature inputs

CSV/imported data may contain non-OHLCV fields.

V1 should preserve and expose those fields as usable strategy inputs when type-compatible.

Examples:

- sentiment;
- breadth;
- custom factor;
- proprietary signal;
- macro series.

This is necessary for bring-your-own-data to be genuinely useful.

---

## 5.9 Bounded Optimisation Lab

This is a V1-defining feature.

The optimiser is not an AI strategy inventor.

The user provides the strategy hypothesis and controls what may change.

### Required setup

User chooses:

- base strategy/version;
- research universe;
- mutable parameters;
- min/max boundaries or explicit permitted values;
- optional step/granularity;
- run budget;
- whether individual sensitivity is included;
- whether combined parameter interaction testing is included;
- acceptance criteria.

Example:

```text
EMA period:       30 → 80
Z threshold:      1.2 → 3.0
ATR multiplier:   1.0 → 3.0

Run budget:       1,000
Universe:         20 instruments

Individual:       ON
Combined:         ON
```

The graph structure remains locked unless the user manually changes it.

---

## 5.10 Optimisation baseline

Every optimisation job starts from an exact baseline.

The baseline must record:

- strategy version;
- original parameters;
- selected datasets;
- selected instruments;
- costs;
- slippage assumptions;
- test period;
- core performance metrics.

Every candidate should be comparable against the base case.

The optimiser must not be forced to recommend a changed strategy.

Valid result:

> No tested candidate materially improved the baseline.

---

## 5.11 Individual parameter sensitivity

V1 should test one mutable parameter at a time while holding others constant.

The output should show:

- sensitivity curve;
- performance degradation;
- stable ranges;
- thresholds/regions where behaviour changes;
- per-instrument effect where useful.

This is required before combined-search results can be interpreted intelligently.

---

## 5.12 Combined parameter search

V1 should support combined parameter exploration.

A full Cartesian grid is not always feasible.

The system should respect the run budget.

Candidate-generation methods can be selected based on dimensionality and budget.

The product requirement is not a particular algorithm.

The product requirement is:

> Explore interactions within the user's authorised bounds without pretending that an impossible full search was performed.

The run record should state what search method was actually used.

---

## 5.13 Cross-instrument optimiser gates

This is required.

The optimiser should not rank a candidate only by pooled return.

Allow qualification criteria at three levels.

### Per-instrument

Examples:

- maximum drawdown;
- minimum trades;
- minimum profit factor;
- minimum Sharpe;
- positive expectancy.

### Cross-instrument

Examples:

- at least N of 20 profitable;
- at least N of 20 beat baseline;
- no more than N fail a metric;
- at least N meet minimum trade count.

### Aggregate

Examples:

- median Sharpe;
- median return improvement;
- portfolio drawdown;
- aggregate cost drag.

The user can edit thresholds.

Strategy OS may provide sensible defaults/presets.

---

## 5.14 Parameter neighbourhood analysis

This is V1 core.

Do not end optimisation with:

> Best parameters = X.

Show:

- best point;
- stable region;
- neighbouring pass rate;
- sensitivity;
- local variance;
- robust parameter ranges.

V1 should explicitly favour explainable robustness over isolated historical peaks.

Heatmaps or equivalent views should be used where dimensions permit.

---

## 5.15 Locked OOS

V1 should allow a final out-of-sample region to remain unavailable to the optimiser.

The system should preserve:

- development window;
- OOS window;
- frozen strategy version;
- reveal state;
- OOS result.

Do not allow the optimisation engine to rank candidates using the locked OOS data.

If a user modifies the strategy after seeing OOS, the software should make clear that the original OOS interpretation has been contaminated.

---

## 5.16 Basic walk-forward validation

V1 should provide a bounded walk-forward workflow.

User configures:

- training/development window;
- test window;
- step.

The system repeatedly:

```text
uses past data
→ selects/optimises within policy
→ freezes result
→ evaluates next unseen window
→ advances
```

V1 output should include:

- number of windows;
- per-window results;
- stitched unseen-period curve;
- consistency summary.

Do not build every academic walk-forward variant in V1.

---

## 5.17 Basic Monte Carlo

V1 should provide a deliberately narrow Monte Carlo/stress capability.

Prioritise:

### Trade bootstrap / resampling

Show plausible outcome and drawdown distributions based on observed strategy trades.

### Execution stress

Perturb:

- slippage;
- fees/spread;
- missed trades/fills where modelled.

Do not make synthetic stochastic market generation a release dependency.

Monte Carlo complements the optimiser.

It is not the optimiser.

---

## 5.18 DSR

Include DSR in V1 **only if the experiment/trial population can be defined and recorded correctly**.

The project already has strong experiment identity foundations, which makes this plausible.

V1 UI should show:

- raw Sharpe;
- number/effective set of trials considered;
- DSR result/interpretation;
- concise explanation.

Correctness is more important than shipping the acronym.

If the trial population cannot be defined honestly, hide the metric rather than publish nonsense.

---

## 5.19 Evidence persistence

Optimisation and validation results must persist.

Do not treat overnight jobs as disposable reports.

Evidence should bind:

- exact strategy version;
- datasets;
- instruments;
- search boundaries;
- run budget;
- search method;
- candidate trials;
- costs/slippage;
- gates;
- validation configuration;
- outputs.

This is how the research moat becomes real.

---

## 5.20 Candidate comparison

The end of the research pipeline should allow comparison of finalists.

Useful columns/sections include:

- base;
- candidate parameters;
- raw performance;
- median cross-instrument performance;
- profitable-instrument count;
- instruments beating baseline;
- drawdown;
- trade count;
- neighbourhood stability;
- OOS;
- walk-forward;
- Monte Carlo;
- DSR;
- data-quality warnings.

The user chooses.

The system may recommend.

It should explain the recommendation.

---

## 5.21 Research-only mode

V1 must permit a strategy to stop at evidence.

Do not show research-only users a product that constantly asks them to connect a broker.

A user with only uploaded data should still be able to complete:

```text
build
→ backtest
→ optimise
→ validate
→ compare
→ preserve
```

---

## 5.22 Signal-only mode

V1 should support signal as a distinct strategy outcome.

At minimum, Strategy OS should be able to represent and record attributable signals without routing orders.

Signal mode can initially surface signals through:

- product UI;
- product event/log;
- existing notification path if appropriate.

External webhook/export breadth can wait.

Architecture must keep:

```text
signal != execution permission
```

---

## 5.23 Reusable components V1

A minimal reusable-component workflow remains high value because it directly reduces graph complexity.

Desired minimal V1:

```text
select subgraph
→ define typed inputs/outputs
→ publish/version component
→ reuse component in another graph
```

Do not build:

- marketplace licensing;
- paid sealed components;
- DRM.

---

## 5.24 Logical composition V1

Ensure the visual language has enough deterministic composition to express useful real strategies.

V1 baseline should include/retain appropriate forms of:

- AND;
- OR;
- NOT;
- comparisons;
- thresholds;
- IF-style routing/selection where semantically clean.

Do not delay V1 for every possible stateful/event-sequence construct.

---

## 5.25 Data-provider / execution-broker separation

V1 architecture must preserve distinct roles.

A connection should not automatically mean:

> this provider owns every data/execution/account function.

Provider capability declarations and provenance should remain explicit.

This is required even if V1 only exposes a limited UI for mixing providers.

---

## 5.26 Canonical instrument identity

Required for:

- CSV mapping;
- cross-instrument research;
- multiple brokers;
- different data/execution providers.

Provider-specific tokens must remain edge mappings.

Do not let new frontend work reintroduce broker-specific identity into strategy graphs.

---

## 5.27 Broker V1: Zerodha + one second real adapter

V1 should **not** attempt all major brokers.

The V1 objective is to prove that the abstraction is real.

### Zerodha

Retain as the existing baseline.

### Upstox

Preferred second adapter because it provides a meaningful independent provider path and lowers user onboarding/API-cost friction.

Definition of success:

- capability declaration;
- instrument mapping;
- data path where supported;
- execution path where supported/approved;
- postback/order-lifecycle semantics;
- conformance tests;
- no core `if broker == ...` contamination.

If adding the second provider requires broad core rewrites, the abstraction is not yet good enough.

### Dhan

Treat as stretch/V1.1 unless implementation is already sufficiently mature and isolated.

Do not let Dhan block the release.

---

## 5.28 Operational cockpit frontend

The backend cockpit is already documented as ready.

Build the actual UX.

Global Live should answer:

- what is deployed;
- paper/live;
- armed/disarmed;
- broker/data connection state;
- open positions;
- open/recent orders;
- risk alerts;
- reconciliation/execution problems.

Strategy Live should answer:

- what version is deployed;
- provider bindings;
- instruments;
- positions/trades;
- risk;
- live vs research state.

Do not recreate backend lifecycle logic in the frontend.

---

## 5.29 Research → deployment integrity

For any execution-capable V1 path, preserve:

```text
exact approved strategy version
→ exact deployment binding
→ exact runtime identity
→ exact order/fill attribution
```

Research evidence must never silently grant execution authority.

Approval is admission.

Execution lifecycle state remains its own authority.

---

## 5.30 Auth, ownership and tenancy

Commercial/multi-user V1 cannot rely on single-owner assumptions.

Required:

- authentication;
- explicit ownership;
- tenant-safe strategy reads/writes;
- dataset ownership;
- experiment ownership;
- broker connection ownership;
- deployment ownership;
- event/socket isolation;
- credential isolation;
- no cross-user leakage.

Do not overbuild enterprise RBAC.

Do make basic tenancy real.

---

## 5.31 Onboarding

The first-run flow should not begin with an empty graph.

A good V1 flow:

1. sign in;
2. see starter strategy;
3. open strategy workspace;
4. inspect graph;
5. change a parameter;
6. run backtest;
7. compare result;
8. select/add instruments or import data;
9. optionally launch optimisation;
10. understand research / signal / execution choices.

---

## 5.32 Product telemetry

Instrument the V1 so the first users answer product questions.

Measure:

- time to first strategy open;
- time to first backtest;
- normal backtest latency;
- warm rerun latency;
- parameter iterations;
- optimisation launches;
- optimisation completion/review;
- CSV import success/failure;
- cross-instrument usage;
- focused-panel usage;
- strategy return frequency;
- signal-mode usage;
- deployment usage;
- abandonment points.

Do not collect unnecessary private trading content merely because telemetry is useful.

---

## 5.33 Error handling

V1 must explain failures.

High-priority user-facing errors include:

- invalid graph;
- insufficient warm-up;
- bad/missing data;
- timestamp alignment failure;
- invalid CSV mapping;
- optimiser configuration too large;
- research job failure;
- broker authentication;
- unsupported provider capability;
- stale data;
- deployment refusal;
- reconciliation issue.

A serious research product cannot respond with generic "Something went wrong."

---

# 6. CREATE SEAM NOW, DO NOT FULLY BUILD

These ideas should influence interfaces but not become V1 projects.

## 6.1 More brokers

Design adapters/capabilities so Dhan/FYERS/Angel can follow.

Do not implement all three on the V1 critical path.

## 6.2 Rich derivatives datasets

Allow schemas/identity to represent:

- futures contracts;
- expiry;
- strike;
- option type;
- OI;
- IV/Greeks.

Do not require a complete historical derivatives warehouse for launch.

## 6.3 Multi-leg economic intent

Do not hard-code the core execution model so one signal can only ever become one order.

But do not build full multi-leg orchestration for V1.

## 6.4 Order flow

Preserve typed non-OHLCV data inputs.

Do not build full historical depth/TBT ingestion.

## 6.5 External signal/input contract

Signal events should already have identities/provenance that can later feed:

- webhooks;
- local agents;
- AmiBroker;
- Python;
- Excel.

Do not launch all connectors.

## 6.6 Marketplace provenance

Strategies/components should be cloneable/versionable.

Do not build marketplace commerce.

## 6.7 Desktop/local worker

Keep data/research contracts compatible with a future local worker.

Do not build desktop V1.

## 6.8 AI Research Agent

The deterministic optimiser/validation system should expose clear interfaces a later agent can invoke.

Do not put an LLM in the critical loop.

---

# 7. SAFE TO DEFER

Move these out of V1 unless they are already nearly finished and isolated.

- PBO;
- Dhan beyond stretch;
- FYERS;
- Angel One;
- every-broker parity;
- advanced multi-timeframe/event-sequence language;
- full futures roll engine;
- historical options/IV surface system;
- full slippage-learning model;
- multi-leg spreads/baskets;
- advanced portfolio optimisation;
- order-flow research;
- L2/TBT;
- automatic lead-lag discovery;
- dynamic execution-instrument optimisation;
- AmiBroker/AFL integration;
- Python/Excel local agent;
- generic authenticated webhooks;
- marketplace;
- strategy DRM;
- desktop client;
- distributed backtesting;
- institutional FIX;
- CTCL;
- DMA;
- drop-copy;
- SOR;
- co-location;
- custom institutional OMS/OEMS;
- autonomous AI strategy invention.

---

# 8. REJECT FOR V1

Do not spend V1 time on:

- 30-broker checkbox race;
- rebuilding TradingView;
- arbitrary AI chat features;
- social trading;
- marketplace launch;
- Kafka because "we may scale";
- Kubernetes because "we may scale";
- microservice extraction without measured need;
- custom data feed without rights;
- direct external webhook-to-order execution;
- opaque all-in-one strategy score;
- optimiser that simply returns maximum Sharpe;
- broker-specific semantics inside core IR;
- full institutional infrastructure.

---

# 9. V1 sequencing

The work should proceed in dependency order.

Parallel work is allowed where boundaries are stable, but do not let frontend and backend agents independently invent competing contracts.

---

# PHASE 0 — Scope and current-state lock

**Target:** 11–12 August

## Goal

Stop architecture/product drift before implementation accelerates.

## Actions

1. Adopt the two new canonical product documents:
   - Grand Product Vision;
   - V1 Product Scope/Sequence.
2. Mark older single-options-bot product descriptions as historical/reference verticals.
3. Reconcile current repository state against the V1 plan.
4. Inventory what already exists for:
   - CSV/data import;
   - cross-instrument IR;
   - optimisation;
   - OOS;
   - reusable components;
   - signal-only output;
   - broker adapters;
   - auth/tenancy.
5. Produce one gap map:
   - EXISTS;
   - PARTIAL;
   - MISSING;
   - BLOCKED.
6. Freeze V1 scope after this gap map.

## Exit condition

Every new engineering task can point to a V1 requirement.

No feature is added simply because it is interesting.

---

# PHASE 1 — Product shell and research UX

**Target:** 12–16 August

## Goal

Make the existing backend foundations visible as one coherent product.

## Primary lane

Frontend / Codex.

## Deliverables

- global navigation;
- Home shell;
- strategy workspace context;
- research plane adaptation to sketches;
- focused/expanded research panels;
- starter-strategy flow;
- initial backtest-result presentation;
- cockpit frontend;
- deterministic "continue where I left off";
- research/job status surfaces.

## Backend lane

Only add missing contracts.

Do not redesign the research backend to satisfy frontend shortcuts.

## Exit condition

A user can:

```text
open product
→ enter strategy
→ edit graph/parameter
→ run existing backtest
→ inspect result
→ see execution/cockpit state
```

without understanding repository internals.

---

# PHASE 2 — Data workspace and cross-instrument V1

**Target:** 14–20 August

Can overlap Phase 1 once frontend contracts stabilise.

## Goal

Make the research plane independent of platform-owned data and prove multiple-series strategies.

## Backend deliverables

- CSV admission/import contract;
- durable dataset identity;
- source/raw artifact provenance;
- normalised dataset representation;
- schema/column mapping;
- basic data-quality checks;
- arbitrary features;
- explicit timestamps/timezones;
- cross-series alignment rules;
- canonical instrument/logical series mapping;
- anti-look-ahead invariants;
- cross-instrument evaluation path.

## Frontend deliverables

Data workspace:

```text
Connected data
Uploaded data
+ Import
```

Import flow:

```text
file
→ map columns
→ set time semantics
→ map instrument/series
→ validate
→ review warnings
→ admit
```

Strategy graph:

- choose inputs from multiple admitted series;
- clearly distinguish observed data from execution target.

## Exit condition

A user can upload two or more datasets and run one strategy whose decision depends on more than one series without look-ahead contamination.

---

# PHASE 3 — Backtest performance and Optimisation Lab core

**Target:** 18–24 August

## Goal

Turn the backtester into an interactive research engine plus explicit overnight heavy-workflow engine.

## Step 1: profile

Measure:

- data load;
- feature computation;
- strategy evaluation;
- repeated parameter run;
- persistence;
- frontend/API overhead.

Do not optimise blind.

## Step 2: warm-research improvements

Reuse safe work between related runs.

Potential areas to evaluate:

- admitted Parquet/columnar representation;
- DuckDB slicing;
- feature caching;
- indicator/cache identity;
- vectorised kernels;
- Numba only where profiling warrants it;
- parallelism only where determinism/resource safety remain clear.

## Step 3: optimiser setup

Build the persisted optimisation job/spec:

- strategy version;
- mutable parameters;
- bounds;
- universe;
- run budget;
- acceptance criteria;
- search method;
- status/progress;
- trial records.

## Step 4: baseline

Exact baseline across selected instruments.

## Step 5: individual sensitivity

One parameter at a time.

## Step 6: combined search

Search combinations within the user's run budget.

## Step 7: cross-instrument qualification

Reject candidates using configured per-instrument, cross-instrument and aggregate gates.

## Exit condition

A user can launch a 20-instrument bounded optimisation job, leave it running as an explicit heavy workflow, return later, and inspect persisted baseline, trials and qualified candidates.

The exact maximum practical run count is determined by measured performance, not marketing.

---

# PHASE 4 — Robustness and Validation Lab

**Target:** 22–28 August

Depends on persisted optimisation trials.

## Goal

Stop V1 from becoming another historical-peak optimiser.

## Deliverables

### Parameter neighbourhood

- local robustness analysis;
- stable-region identification;
- visual map where useful;
- sensitivity summary.

### Locked OOS

- protected OOS configuration;
- frozen candidate;
- reveal/evidence semantics.

### Walk-forward

- basic rolling/expanding configuration;
- per-window results;
- stitched unseen performance.

### Monte Carlo

- trade bootstrap/resampling;
- drawdown distribution;
- simple execution stress.

### DSR

- only after trial-count/selection population semantics are proven.

### Candidate comparison

Compare finalists and baseline across all evidence.

## Exit condition

The optimiser no longer ends with "highest Sharpe wins."

It ends with evidence about:

- robustness;
- cross-market consistency;
- OOS;
- walk-forward;
- uncertainty;
- search bias.

---

# PHASE 5 — Research / Signal / Deployment endpoints

**Target:** 25–30 August

## Goal

Make the three strategy outcomes explicit.

## Research only

Strategy can remain in research/evidence state indefinitely.

## Signal

Add a strategy output mode that records/surfaces typed signals without broker authority.

## Paper deployment

Use the existing Strategy OS authority/execution path.

## Live deployment

Do not broadly enable by assumption.

For live-capable users, prove the exact chain:

```text
approved graph/version
→ deployment
→ canonical binding
→ live signal
→ risk/authority
→ broker order
→ fill
→ attribution
→ reconciliation
→ replay/evidence
```

The live gate remains an explicit owner/safety decision.

## Exit condition

The frontend and backend both understand that:

```text
research
signal
execution
```

are distinct destinations, not "deployment levels."

---

# PHASE 6 — Reusable components and strategy-language polish

**Target:** 25–31 August

May run in parallel if IR foundation already makes this small.

## Goal

Make real graph construction manageable.

## Deliverables

- publish/version reusable subgraph;
- typed component inputs/outputs;
- insert/reuse;
- sufficient logical composition;
- graph clarity/focused views.

## Scope control

If reusable-component publication becomes a major new compiler/runtime project, push the full UI to V1.1 and preserve the underlying seam.

Do not jeopardise the research pipeline.

---

# PHASE 7 — Provider/broker V1

**Target:** 26 August–1 September

## Goal

Prove provider neutrality without entering a broker-count race.

## Zerodha

- preserve proven existing path;
- ensure V1 deployment/cockpit integrates correctly.

## Upstox

- official SDK/API reference first;
- instrument mapping;
- capability model;
- data/execution path as supported;
- lifecycle semantics;
- conformance tests.

## Dhan

Only if:

- implementation is isolated;
- core V1 work is closed;
- no release delay.

Otherwise V1.1.

## Exit condition

Adding provider #2 did not require polluting core strategy/research/execution code.

---

# PHASE 8 — Multi-user/commercial hardening

**Target:** 28 August–2 September

## Goal

Make the web product safe for real invitees.

## Required

- auth;
- ownership;
- tenant-safe data access;
- credential isolation;
- broker connection ownership;
- dataset/research/deployment scoping;
- safe websockets/events;
- sensible rate/resource limits for heavy jobs;
- job ownership;
- clear errors;
- onboarding;
- docs;
- basic product telemetry.

## Payments

If first-week September release is invite-only/private alpha:

> payment integration is **not** allowed to delay V1 product validation.

Preserve entitlements/account-plan seams.

Add payment collection when users are actually being charged.

If V1 is defined as paid public access, billing becomes a commercial release gate.

---

# PHASE 9 — Integration, hardening and release freeze

**Target:** 1–5 September

## Rule

No new features.

## Test the actual user journeys

### Journey A — platform-data researcher

```text
sign in
→ starter strategy
→ modify
→ backtest
→ optimise
→ validate
→ save evidence
```

### Journey B — BYOD researcher

```text
sign in
→ import CSV
→ map/validate
→ cross-instrument strategy
→ backtest
→ optimise
→ validate
```

### Journey C — signal user

```text
validated strategy
→ signal mode
→ signal appears
→ no broker order
```

### Journey D — paper trader

```text
validated strategy
→ deploy paper
→ cockpit
→ position/order/evidence attribution
```

### Journey E — live-capable controlled validation

Only if explicitly approved:

```text
exact candidate
→ authority
→ one controlled live path
→ order/fill
→ reconcile
→ replay
```

## Hardening checks

- migrations from zero;
- auth/ownership;
- no cross-tenant leakage;
- dataset hash/provenance;
- anti-look-ahead tests;
- optimisation determinism/identity;
- job restart/failure behaviour;
- baseline/trial persistence;
- OOS isolation;
- broker conformance;
- paper/live structural guards;
- kill switch;
- order lifecycle;
- reconciliation;
- frontend build/type/tests;
- backend/research tests;
- deterministic smoke/replay.

## Exit condition

V1 can be handed to invitees without developers explaining every workflow live.

---

# 10. Critical dependency graph

```text
Existing IR / evidence foundation
            │
            ├───────────────┐
            ↓               ↓
     Frontend product   Data/BYOD layer
            │               │
            └───────┬───────┘
                    ↓
          Cross-instrument research
                    ↓
          Fast/reusable backtesting
                    ↓
          Persisted optimiser trials
                    ↓
        Parameter neighbourhoods
                    ↓
       OOS / walk-forward / MC / DSR
                    ↓
           Candidate comparison
                    ↓
    Research / Signal / Deployment split
                    ↓
     Broker + cockpit integration
                    ↓
        Multi-user hardening
                    ↓
             V1 release
```

Do not build later layers before their evidence inputs exist.

---

# 11. Parallel agent ownership

The project has benefited from clear agent separation.

## ChatGPT / Codex lane

Prefer for:

- frontend;
- UX;
- product shell;
- research-plane presentation;
- candidate-comparison UI;
- data-import UI;
- optimisation/validation UX;
- cross-surface integration.

## Claude/backend lane

Prefer for:

- IR/backend contracts;
- data admission;
- dataset identity;
- cross-instrument semantics;
- optimiser backend;
- research jobs;
- statistical implementation;
- migrations;
- provider adapters;
- execution/risk;
- tests;
- hardening;
- docs.

## Coordination rule

One agent owns a contract at a time.

Do not let frontend invent fake backend semantics because another agent is busy.

---

# 12. V1 release gates

A feature can exist without being a release gate.

The following are actual V1 gates.

## Gate A — strategy identity

A graph edited in the UI maps to the exact executable strategy version used in research.

## Gate B — dataset identity

Research evidence can identify exact input data.

## Gate C — anti-look-ahead

Cross-series historical research cannot silently consume future observations.

## Gate D — backtest usability

Normal research iteration is acceptably responsive and heavy workflows are explicit.

## Gate E — optimiser integrity

The optimiser:

- honours user bounds;
- honours run budget;
- records trials;
- compares baseline;
- applies qualification rules;
- does not lie about search coverage.

## Gate F — robustness

At least:

- parameter neighbourhood;
- locked OOS;
- basic walk-forward;
- basic Monte Carlo

are operational.

DSR is a gate only if exposed in UI.

If exposed, it must be correct.

## Gate G — research outcome separation

Research-only and signal-only do not accidentally obtain execution authority.

## Gate H — paper execution

Paper deployment preserves exact strategy/version attribution and lifecycle.

## Gate I — provider architecture

At least the existing broker plus one independent provider path prove the abstraction without core contamination.

## Gate J — tenancy

Invitees cannot access each other's:

- strategies;
- datasets;
- experiments;
- connections;
- deployments;
- events.

## Gate K — UX

A new user can complete core flows from the interface without repository knowledge.

---

# 13. Things that are NOT V1 release gates

Do not block release on:

- PBO;
- Dhan;
- FYERS;
- Angel;
- marketplace;
- AI Research Agent;
- full order flow;
- tick data;
- full options historical data;
- every asset-class execution route;
- MTF;
- multi-leg orchestration;
- AmiBroker;
- Excel;
- generic webhooks;
- desktop;
- distributed backtesting;
- FIX;
- CTCL;
- Kubernetes;
- Kafka.

---

# 14. V1 quality bar for the Optimisation Lab

The Optimisation Lab is the largest new research feature.

It should be considered V1-ready only when the following statements are true.

1. A user can select exactly which parameters may change.
2. The user controls the permitted boundaries/values.
3. The user selects the instrument universe.
4. The user controls or sees the run budget.
5. The base strategy is preserved.
6. Individual sensitivity is available.
7. Combined exploration is available.
8. Every tested candidate has durable identity.
9. The search method is recorded.
10. Per-instrument results remain visible.
11. Cross-instrument acceptance rules work.
12. Aggregate metrics cannot hide complete cross-market failure.
13. Robust parameter regions can be distinguished from isolated peaks.
14. The optimiser may recommend the baseline.
15. The user can compare finalists.
16. Optimisation results survive closing/reopening the product.
17. Heavy runs have clear status/progress/failure state.
18. Research evidence records how the candidate was discovered.

---

# 15. V1 quality bar for BYOD

BYOD is ready only when:

1. user can import a CSV;
2. timestamp is explicit;
3. timezone is explicit;
4. logical series/instrument identity is explicit;
5. OHLC fields can be mapped;
6. extra feature fields are preserved;
7. bad data produces useful warnings/errors;
8. the admitted dataset receives durable identity;
9. a backtest can use it;
10. a cross-instrument backtest can combine it with another admitted series;
11. old evidence remains tied to the old dataset version after a new upload.

---

# 16. V1 quality bar for cross-instrument

Cross-instrument V1 is ready only when:

1. one strategy can request two or more series;
2. series identities are explicit;
3. different providers/files do not change the strategy's semantic identity;
4. alignment is deterministic;
5. look-ahead is prevented;
6. missing/stale-data behaviour is explicit;
7. the traded target can differ from observed sources;
8. results/evidence list the input series used.

---

# 17. V1 quality bar for validation

Validation is ready only when the system can answer:

- Did nearby parameters work?
- Did this beat the user's baseline?
- Did it work across enough of the selected instruments?
- Did it survive locked OOS?
- Did repeated walk-forward windows survive?
- How uncertain are drawdown/outcomes under basic Monte Carlo?
- How many alternatives were searched?
- What assumptions/data warnings apply?

The user should not need a statistics degree to understand the answers.

Advanced metrics can be expanded.

Core reasoning should be plain.

---

# 18. V1 infrastructure stance

Keep infrastructure proportional to the first release.

Requirements:

- supervised processes;
- health/readiness;
- safe secrets/config;
- job durability appropriate to heavy research;
- resource controls;
- database backups;
- logging;
- crash recovery;
- secure file handling;
- isolation between users.

Do not introduce distributed systems merely because the optimiser can run 1,000 backtests.

First:

- profile;
- reuse computations;
- optimise data layout;
- parallelise safely on one machine/process model where appropriate;
- measure actual queue/compute pressure.

Scale architecture after the product generates evidence that scale is needed.

---

# 19. Private-alpha feedback agenda

The first users should specifically answer whether the new product thesis is correct.

Observe:

## Research

- Do users understand the graph?
- Do they import data?
- Do they use cross-instrument logic?
- Do they trust the dataset warnings?
- How fast do normal iterations feel?

## Optimisation

- Do they understand mutable vs locked parameters?
- Do they define boundaries comfortably?
- Do they understand run budgets?
- Do they use cross-instrument gates?
- Do they choose robust candidates instead of top-return candidates?
- Do they understand "baseline is still best" as a valid outcome?

## Validation

- Do parameter neighbourhoods change user decisions?
- Do users understand OOS?
- Do they use walk-forward?
- Does Monte Carlo change risk perception?
- Is DSR useful or confusing?

## Endpoints

- How many users stop at research?
- How many want signals?
- How many want broker execution?
- Which broker demand is real?

These answers should control V1.1 more than the pre-launch wishlist.

---

# 20. V1.1 priority queue

Assuming V1 works, evaluate next in this approximate order.

1. PBO.
2. Dhan adapter.
3. Better realised-slippage telemetry and execution stress.
4. Richer multi-timeframe/stateful graph logic.
5. Multi-leg strategy intent.
6. Futures contract/roll research.
7. Better historical options/IV datasets.
8. FYERS/Angel based on alpha demand.
9. External signal/API seam.
10. AmiBroker/Python/Excel interoperability.
11. Order-flow data pilot if data rights and user demand justify it.

This list should be reordered from actual alpha evidence.

---

# 21. Explicit later-version queue

Keep out of near-term planning:

- AI Research Agent;
- automatic strategy-structure mutation;
- automatic lead-lag discovery at scale;
- dynamic execution-instrument optimisation;
- marketplace;
- strategy creator economics;
- DRM;
- public sharing/social;
- desktop/local compute tier;
- distributed research cluster;
- TBT/depth warehouse;
- smart order routing;
- institutional OMS/OEMS;
- FIX;
- CTCL;
- DMA;
- drop-copy;
- co-location.

These may become major future products.

They should not steal September.

---

# 22. PM decision rules

When a new idea appears before V1, ask in this order.

## 1. Does it prove the V1 promise?

If no, defer.

## 2. Does it fix a correctness/safety problem?

If yes, prioritise.

## 3. Does it prevent a later foundational rewrite?

If yes, create the seam now but defer the complete feature.

## 4. Does a real V1 user need it?

If no evidence, defer.

## 5. Is it merely impressive?

If yes, defer.

## 6. Can it be added after launch without invalidating current strategy/data/evidence identity?

If yes, defer safely.

---

# 23. V1 product statement

By release, Strategy OS should credibly be described as:

> **A visual strategy research and operating environment for systematic traders. Users can build or modify versioned strategies, use connected or uploaded data, combine multiple instruments and custom features, backtest and run bounded parameter optimisation across a chosen universe, inspect parameter robustness and out-of-sample evidence, preserve the exact research lineage, and then keep the strategy as research, use it for signals, or move it into a controlled execution workflow.**

Do not describe V1 as:

> an autonomous AI trader

or:

> a universal broker platform

or:

> an institutional OMS.

Those descriptions would pull the product away from what V1 is actually proving.

---

# 24. V1 completion checklist

## Product / frontend

- [ ] coherent global shell;
- [ ] strategy workspace;
- [ ] research plane aligned to sketches;
- [ ] focused/expanded views;
- [ ] starter strategy;
- [ ] cockpit frontend;
- [ ] candidate comparison;
- [ ] clear research/signal/deploy choices;
- [ ] onboarding;
- [ ] useful error states.

## Data

- [ ] CSV import;
- [ ] mapping;
- [ ] arbitrary features;
- [ ] dataset identity/version;
- [ ] quality warnings;
- [ ] canonical instrument/logical series;
- [ ] cross-instrument alignment;
- [ ] anti-look-ahead tests.

## Backtest

- [ ] normal-run performance measured;
- [ ] safe reuse/caching;
- [ ] explicit heavy-job workflow;
- [ ] exact cost assumptions;
- [ ] cross-instrument support.

## Optimisation

- [ ] baseline;
- [ ] user-defined mutable parameters;
- [ ] user-defined ranges;
- [ ] run budget;
- [ ] individual sensitivity;
- [ ] combined search;
- [ ] trial persistence;
- [ ] per-instrument metrics;
- [ ] cross-instrument gates;
- [ ] aggregate gates;
- [ ] progress/failure status.

## Validation

- [ ] parameter neighbourhoods;
- [ ] locked OOS;
- [ ] basic walk-forward;
- [ ] basic Monte Carlo;
- [ ] DSR if correctness bar met;
- [ ] evidence persistence.

## Strategy language

- [ ] existing typed IR preserved;
- [ ] sufficient logical composition;
- [ ] minimal reusable components if feasible without destabilisation.

## Endpoints

- [ ] research-only;
- [ ] signal-only;
- [ ] paper deploy;
- [ ] live route remains explicit/owner-gated.

## Provider/broker

- [ ] data/execution separation;
- [ ] canonical identity;
- [ ] capability model;
- [ ] Zerodha path;
- [ ] Upstox second-path proof;
- [ ] common conformance tests.

## Security/commercial

- [ ] auth;
- [ ] ownership;
- [ ] tenant isolation;
- [ ] credential isolation;
- [ ] research-job ownership/resource limits;
- [ ] telemetry;
- [ ] docs;
- [ ] payment only if paid launch requires it.

## Hardening

- [ ] migrations;
- [ ] backend/research tests;
- [ ] frontend test/type/build;
- [ ] deterministic smoke;
- [ ] authority guards;
- [ ] paper/live separation;
- [ ] reconciliation;
- [ ] no critical security gaps;
- [ ] no unresolved release-blocking UX failures.

---

# 25. Final project-management judgment

The V1 critical path should now be dominated by four things:

```text
1. COHERENT PRODUCT UX

2. DATA + CROSS-INSTRUMENT RESEARCH

3. BOUNDED OPTIMISATION + ROBUSTNESS VALIDATION

4. SAFE OPTIONAL SIGNAL/EXECUTION ENDPOINTS
```

Everything else should justify why it deserves to interrupt one of those four.

The most important new scope decision is that the **Optimisation Lab is no longer a vague future autonomous-research idea**.

It is a deterministic V1 product:

> the user supplies the hypothesis, parameters, bounds, instruments, run budget and acceptance rules; Strategy OS systematically maps the parameter landscape, compares every candidate with the baseline, rejects weak cross-market outcomes, finds stable parameter neighbourhoods, and hands the user a small set of evidence-backed finalists.

That feature, combined with bring-your-own-data, cross-instrument research, locked OOS, walk-forward and basic Monte Carlo, gives the research plane a coherent reason to exist even for users who never connect a broker.

That is the shape V1 should now take.
