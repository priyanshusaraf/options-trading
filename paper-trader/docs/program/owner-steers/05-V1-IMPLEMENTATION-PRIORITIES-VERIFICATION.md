# V1 Implementation Priorities & Verification Policy

## Goal

Preserve rigor where defects can lose money or invalidate research while preventing the project from spending disproportionate time/tokens proving low-impact details.

---

## 1. Risk-weighted verification

### Critical
Examples:
- order/position lifecycle;
- real-money execution;
- kill switch/protection;
- strategy causality;
- streaming/backtest parity;
- tenant isolation/auth;
- accounting/ledger;
- point-in-time market truth;
- dynamic contract identity;
- position ownership;
- irreversible data corruption.

Use:
- explicit invariants;
- RED -> GREEN;
- adversarial cases;
- integration proof;
- independent review;
- concurrency/recovery proof where relevant.

### Important
Examples:
- indicator math;
- backtest calculations;
- provider adapters;
- caching;
- event delivery;
- deployment preflight;
- billing/entitlements.

Use:
- focused unit/integration tests;
- regression tests for discovered bugs;
- representative cases;
- one review pass.

### Routine
Examples:
- ordinary CRUD;
- dashboard filters;
- noncritical workflow UI;
- navigation;
- presentation state.

Use:
- smoke tests / typecheck / existing affected suite;
- new tests only when cheap or protecting meaningful behaviour.

### Trivial
Examples:
- copy;
- spacing;
- icons;
- harmless styling.

Usually no dedicated tests.

---

## 2. Test rule

Every new test should protect a realistic failure hypothesis.

Do not maximize:
- test count;
- coverage percentage;
- environment combinations;
- theoretical edge-case permutations.

After two failed fix/test loops outside Critical work, reassess whether the test protects a real product requirement before spending more time.

Do not weaken Critical invariants because a test is difficult.

---

## 3. Test cadence

During implementation:
- directly affected tests.

At meaningful subsystem commit:
- affected subsystem suite.

At phase/release boundary:
- broad/full suite.

Do not run the entire repository after every harmless frontend or CRUD change.

---

## 4. First-party node conformance harness

Invest heavily once in reusable confidence.

For first-party analytical nodes:
- independent reference/golden values where practical;
- vector/batch result;
- streaming result;
- parity;
- warmup;
- missing/invalid data;
- causal declarations;
- representative edge cases.

Do not create bespoke giant test matrices per indicator when a shared harness can prove the same contract.

---

## 5. V1 product priorities

### Must have
- five node-family model;
- substantial first-party node library;
- node data/state/causal/resource contracts;
- strategy vs deployment separation;
- named instrument roles;
- dynamic derivative selectors;
- point-in-time market rulebook;
- historical contract/strike/lot/session correctness;
- provider capability matrix;
- Strategy Preflight;
- numeric validity system;
- position sizing;
- pyramiding primitives;
- arbitrary strategy-managed exits;
- protection semantics;
- incremental runtime and subscription sharing;
- resource planner/QoS;
- strategy confidentiality controls;
- version/provenance receipts.

### Can be deferred
- team/coworker sharing UX;
- marketplace;
- AI research agent;
- broad foreign-broker coverage;
- full confidential-compute/zero-knowledge execution;
- every obscure indicator;
- deep institutional integrations not required by launch cohort.

---

## 6. Implementation sequencing

1. Freeze contracts and acceptance scenarios.
2. Audit existing code against the steer before rebuilding anything.
3. Reuse suitable existing/open-source implementations where license-compatible.
4. Build the hidden foundations required by many nodes:
   - numeric validity;
   - node metadata contract;
   - point-in-time instrument/rule model;
   - provider capability model.
5. Expand first-party nodes through the shared conformance harness.
6. Implement strategy/deployment binding and preflight.
7. Implement dynamic derivative and order-flow structures.
8. Add resource planning, shared computation and QoS before broad live rollout.
9. Build/finish the user-facing workflow around research -> approve -> deploy.
10. Prove canonical acceptance scenarios.
11. Only then broaden less critical catalogue/integration coverage.

---

## 7. Canonical acceptance scenarios

### A. Reusable equity
One strategy, many SELF bindings, sizing, stops, pyramiding.

### B. Weekly-options/order-flow
Dynamic weekly contract resolution, historical strike/lot/session rules, ATM window, OI/depth, arbitrary exits, provider-aware protection, scheduled weekdays.

### C. Cross-market
Multiple data providers, different sessions/timezones, freshness and missing-data rules, one execution market.

These scenarios are architecture acceptance tests, not justification for exhaustive combinatorial testing.

---

## 8. Guard against scope drift

A newly discovered issue should be classified:

### Core-abstraction issue
Would make a major class of strategy impossible, unsafe or semantically wrong.
-> revisit design.

### Local implementation edge case
Can be handled within existing abstractions.
-> solve locally and continue.

Do not repeatedly reopen the entire architecture for local edge cases.
