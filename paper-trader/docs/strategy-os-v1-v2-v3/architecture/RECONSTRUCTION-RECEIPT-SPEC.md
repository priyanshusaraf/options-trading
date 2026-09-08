# Reconstruction receipt specification

## Goal

Given the same exact semantics, data, market rules, costs, sizing, and event order, Strategy OS and an independent implementation should reach the same user-visible decision and money result.

This is an architecture target. The current repository does not yet satisfy the full claim.

## Equivalence levels

### Level 1: deterministic Strategy OS rerun

Require:

- identical valid evaluation times;
- identical node outputs where material;
- identical signals;
- identical portfolio admission;
- identical reservations;
- identical execution intents;
- identical simulated fills;
- identical positions;
- identical fees and money values;
- identical final metrics;
- identical event identities where promised.

### Level 2: independent implementation

An independent Python or spreadsheet path should produce:

- identical signal decisions;
- identical quantities;
- identical trade ledger;
- identical fees and rounded money values;
- identical final P&L.

### Level 3: declared numeric tolerance

Tolerance is permitted only for intermediate floating-point values when:

- the receipt names the tolerance and comparison rule;
- no downstream branch changes;
- thresholds use canonical behavior;
- money, lot, tick, and exchange rounding remain exact.

## Receipt envelope

Proposed schema: reconstruction-receipt/1

### Strategy and graph

- owner;
- Strategy ID and immutable version;
- authored graph address;
- resolved graph address;
- format version;
- registry snapshot address;
- component and implementation closure;
- admission address;
- authored-to-resolved topology address;
- parameter bindings and provenance.

### Universe and Workflow

- Universe definition and evaluation address;
- research or execution snapshot;
- rank and tie-break policy;
- candidate-instance address;
- Workflow definition and instance;
- step receipts;
- approval address;
- portfolio policy and decision-batch address.

Static V1 runs may use an immutable static Universe snapshot and no Workflow address.

### Data and market truth

- dataset manifest and segment addresses;
- raw and normalized observation addresses where applicable;
- provider entity, product, contract, and alias;
- canonical instrument addresses;
- market-truth snapshot;
- calendar and session policy;
- timezone;
- interval and timestamp meaning;
- completed-bar rule;
- alignment policy;
- stale and missing-data policy;
- adjustment and roll policy;
- correction lineage;
- warmup and earliest valid evaluation.

### Research

- research programme, hypothesis, spec, and run;
- exact search-space definition;
- sampler and version;
- random seed;
- trial population;
- failed and pruned trial policy;
- locked OOS state and reveal history;
- walk-forward policy;
- Monte Carlo method and seed;
- baseline identity;
- number of tested hypotheses;
- selected candidate and decision.

### Simulation and execution

- engine build and source identity;
- evaluation algorithm;
- next-bar or other fill policy;
- slippage model;
- fee and tax schedule;
- position-sizing policy;
- portfolio admission policy;
- contention policy;
- capital reservation policy;
- tie-break rules;
- order intent and lowering policy;
- partial-fill and cancel policy;
- price, quantity, tick, lot, and money rounding;
- broker capability and execution adapter version.

### Runtime and environment

- build commit and artifact digest;
- Python, operating system, architecture, and dependency lock;
- database schema heads;
- service role;
- deterministic environment variables;
- locale and timezone;
- reference-runner version.

Secrets, provider tokens, customer strategy plaintext, and private raw data do not enter the receipt.

## Current source mapping

| Receipt area | Current source |
| --- | --- |
| graph and implementation | IR graph versions, registry snapshot, resolution, implementation identity |
| causal admission | StrategyAdmission |
| data and market truth | DatasetManifest, capability assessment, market truth, observation authority |
| backtest computation | execution_result_address and BacktestComputation |
| research | ExperimentSpec, ExperimentRun, OptimizationTrial, Finding, PromotionCandidate |
| deployment | Deployment, IR paper deployment, execution binding |
| order lifecycle | ExecutionIntent and ExecutionOrderEvent |
| money | positions, trades, capital state, charges |
| build | VERSION and build SHA fields |

The gap is assembly into one closed receipt and independent consumption of it.

## Reconstruction export

Suggested package:

    receipt.json
    strategy-ir.json
    resolved-topology.json
    registry-manifest.json
    universe-snapshot.json
    workflow-receipts.json
    dataset-manifest.json
    market-truth-manifest.json
    evaluation-policy.json
    cost-and-slippage.json
    expected-node-events.parquet
    expected-decision-ledger.parquet
    expected-orders.csv
    expected-fills.csv
    expected-trades.csv
    reference-runner/
    README.md

Every file has a content address. The root receipt lists all members and publishes only after every child verifies.

## Licence and privacy gate

Before export:

- check provider redistribution rights;
- omit or transform licensed raw data when redistribution is not permitted;
- retain a manifest that explains the missing licensed member;
- keep strategy content private by default;
- require owner action for a full private export;
- remove credentials and provider tokens;
- protect broker account identifiers;
- record encryption and retention policy.

A receipt may prove identity without redistributing raw provider bytes.

## Reference interpreters

### Path A: current vector runtime

Fast research and accepted Strategy OS semantics.

### Path B: completed-prefix reference

The current independent graph walk already checks causal evaluation and recursive state.

### Path C: independent trade and money runner

Add a deliberately simple runner that consumes canonical decisions and independently applies:

- portfolio admission;
- sizing;
- fill timing;
- slippage;
- fees;
- position transitions;
- capital;
- metrics.

Path C must not import the optimized backtest engine's private calculation helpers.

### Spreadsheet path

For small golden cases, provide flat inputs and formulas that an experienced user can inspect. Do not force every advanced graph into a spreadsheet.

## First-divergence report

Compare in order:

1. input event identity;
2. aligned observation;
3. node input;
4. node output and validity;
5. Strategy state;
6. signal;
7. candidate intent;
8. portfolio decision;
9. reservation;
10. execution command;
11. fill;
12. position;
13. fees;
14. capital;
15. final metrics.

Report:

- first divergent event;
- expected and actual address;
- authored and resolved node;
- exact timestamp;
- upstream dependencies;
- tolerance rule if any;
- downstream claims invalidated.

Do not report only a final P&L mismatch.

## Golden scenarios

1. EMA and RSI equity Strategy.
2. Cross-instrument signal with a separate execution target.
3. Missing and stale input.
4. Completed higher timeframe.
5. Corporate action.
6. Futures roll.
7. Dynamic option selector with fixed held contract.
8. Partial fill.
9. Fee and tax rounding.
10. Direction-aware adverse slippage.
11. Same-bar stop and target ambiguity.
12. Simultaneous capital contention.
13. Atomic basket refusal.
14. Locked OOS reveal.
15. Walk-forward.
16. Monte Carlo seed.
17. Parallel trial ordering.
18. Universe membership change in V2.

## Acceptance

V1 architecture accepts this receipt only when:

- one closed schema maps every current identity;
- the export rehashes correctly after process death;
- the reference runner reproduces all V1 golden cases;
- a deliberate semantic mutation creates the expected first divergence;
- a missing receipt member refuses;
- protected and licensed data handling passes owner review.

## Deployment impact

Compatible for in-memory assembly. Migration-required if receipts or exports gain new durable tables. No production readiness follows from a local reconstruction PASS.
