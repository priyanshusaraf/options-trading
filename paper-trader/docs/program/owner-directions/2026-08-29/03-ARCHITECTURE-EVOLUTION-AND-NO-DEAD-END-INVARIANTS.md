# Strategy OS — Architecture Evolution and No-Dead-End Invariants

**Date:** 29 August 2026\
**Status:** Future-compatibility architecture addendum\
**Purpose:** Identify the minimum conceptual seams required by the updated V0–V6 product vision while explicitly preventing later ambitions from bloating the current release.

---

## 0. Governing rule

> Preserve what must remain representable; do not build what is not yet justified.

A future feature creates a current architectural requirement only when an existing assumption would otherwise force a destructive migration, erase identity, weaken safety, or make the future concept impossible.

Do not implement marketplaces, arbitrary multi-leg execution, portfolio optimization, managed money, or enterprise treasury in V0 merely because their object names appear here.

---

# 1. Existing foundations to retain

The current Strategy OS steers already establish strong invariants:

- one immutable strategy representation across research and operation;
- strategy definition distinct from deployment;
- named instrument roles;
- provider-neutral canonical instrument identity;
- point-in-time market truth;
- explicit data validity, freshness, and causality;
- data-provider and execution-broker separation;
- capability-driven preflight;
- strategy/deployment capital hierarchy;
- exact position ownership despite broker netting;
- immutable node/strategy versions;
- evidence lineage;
- durable truth separate from reconstructible hot state;
- risk-weighted verification;
- bounded runtime and resource planning.

The new vision extends these foundations. It does not invalidate them.

---

# 2. Updated canonical concept map

The long-term domain can be expressed through the following layers.

```text
AUTHORING AND RESEARCH
Strategy
StrategyRevision
Component / NodeVersion
InstrumentScope
Dataset / DataObservation
Experiment / EvidenceProfile
SignalMonitor
SignalEvent / SignalAlert

OPERATION AND EXECUTION
Deployment
EconomicIntent
ExecutionProductPolicy
ExecutionStructurePolicy
PortfolioAdmission
PositionCampaign
PositionLeg / PositionSlice / ExactInventory
OrderIntent / BrokerOrder / Fill
ReconciliationReceipt

PORTFOLIO
Portfolio
PortfolioSleeve
PortfolioSnapshot
RiskModelSnapshot
PortfolioMandate
CandidateActionSet
OptimizationRun
ProposedPortfolioRevision
RebalancePlan

MARKETPLACE
AllocatableProduct
StrategyAssetListing
ManagedModelListing
License / RightsManifest
DisclosureProfile
CapacitySnapshot
AllocationRecommendation

ENTERPRISE TREASURY
EconomicExposure
EnterpriseExposureBook
TreasuryMandate
HedgeCandidate
HedgeProgramme
ApprovalPolicy
Counterparty / VenueBinding
HedgeEffectivenessReceipt
```

Not every object requires its own table or service today. The map defines semantic boundaries and future relationships.

---

# 3. Signal and alert seam for V0

V0 needs a real operational endpoint without public execution.

Required separation:

```text
StrategyRevision
→ SignalMonitor
→ SignalEvent
→ SignalAlert
→ Delivery/Attention State
```

A signal event is a durable strategy output. An alert is a user-facing attention object derived from it. Websocket/email/push delivery is not the canonical truth.

Required invariants:

1. A signal does not imply execution permission.
2. A duplicate evaluation or delivery does not create duplicate canonical outcomes.
3. Alert read/acknowledged state does not mutate the strategy result.
4. Alert expiry is explicit.
5. An alert can always identify the strategy revision, input context, and reason receipt that created it.
6. Alert storage and event delivery remain tenant-isolated.
7. A monitor can be paused or retired without rewriting the strategy.

---

# 4. Strategy, economic intent, and execution structure

Do not permanently encode:

```text
one strategy signal = one order
```

Use the more general contract:

```text
one StrategySignal
→ zero, one, or many EconomicIntents
→ zero, one, or many PositionCampaigns
→ zero, one, or many OrderIntents
```

## 4.1 StrategySignal

What the market logic concludes:

- economic instrument or thesis;
- direction/structure preference;
- desired risk or exposure;
- horizon;
- confidence/evidence references;
- timestamp and validity.

## 4.2 ExecutionProductPolicy

Which product expresses a simple intent:

- cash;
- intraday;
- MTF;
- future;
- selected option;
- no trade.

## 4.3 ExecutionStructurePolicy

How a later multi-leg structure is selected and constrained:

- eligible structure families;
- exact leg-selection rules;
- payoff/risk limits;
- liquidity;
- Greeks;
- final and interim margin;
- broker combo capability;
- sequencing;
- partial-fill recovery;
- no-trade fallback.

Strategy logic should not be polluted with broker-specific order orchestration.

---

# 5. Position Campaign / Economic Position

A campaign represents one economic thesis or hedge even when it contains many instruments and orders.

Suggested hierarchy:

```text
PositionCampaign
├── campaign identity and owner
├── creating strategy/portfolio/hedge decision
├── immutable opening policy revisions
├── desired aggregate exposure/payoff
├── PositionLeg A
│   └── exact inventory slices and fills
├── PositionLeg B
│   └── exact inventory slices and fills
└── aggregate risk, P&L, lifecycle, and evidence
```

Required future states:

```text
PROPOSED
PREFLIGHTING
CAPITAL_RESERVED
ENTERING
PARTIALLY_FILLED
TEMPORARILY_UNHEDGED
HEDGED
ACTIVE
ADJUSTING
ROLLING
EXITING
PARTIALLY_EXITED
RECOVERY_REQUIRED
CLOSED
FAILED
```

Current storage should avoid assumptions that prevent:

- more than one exact physical instrument per economic position;
- multiple tranches;
- leg ratios;
- campaign-level P&L/risk;
- partial closure;
- roll/adjustment lineage;
- independent strategy ownership despite broker netting.

V0 only needs the seam. Future execution releases certify behavior incrementally.

---

# 6. Margin, liquidity, and interim-state correctness

For a multi-leg strategy, final margin is not enough.

Future preflight must evaluate:

```text
final structure requirement
+
worst permitted intermediate legging state
+
slippage/recovery buffer
+
MTM liquidity reserve
+
pending-order awareness
```

Do not hard-code “buy first, then sell” as a universal rule. Instead:

1. inspect provider combination/basket capabilities;
2. model exact structure and temporary exposures;
3. compile a safe execution plan;
4. reserve capital transactionally;
5. reject if no safe route exists;
6. preserve every action and recovery decision.

Current code should keep margin estimation and capital admission behind interfaces that can later accept a complete campaign plan rather than one order only.

---

# 7. Portfolio as an active control plane

Do not model Portfolio forever as a dashboard projection.

Future-compatible concepts:

```text
PortfolioDefinition
PortfolioSleeve
PortfolioSnapshot
RiskModelSnapshot
PortfolioMandate
CandidateActionSet
OptimizationRun
ProposedPortfolioRevision
RebalancePlan
```

## 7.1 PortfolioSleeve

A sleeve may be:

- native Strategy OS strategy/deployment;
- imported holdings;
- external fund/model;
- manual/legacy strategy;
- cash/collateral;
- hedge programme.

The system should preserve visibility/confidence metadata rather than treating all sleeves as equally observable.

## 7.2 RiskModelSnapshot

Risk inputs are versioned estimates:

- beta/factors;
- covariance/correlation;
- volatility;
- Greeks;
- liquidity;
- drawdown/tail scenarios;
- capacity;
- estimation method/window;
- confidence and provenance.

Do not attach one mutable “beta” field to a strategy and treat it as eternal truth.

## 7.3 ProposedPortfolioRevision

An optimization result is a proposal, not an automatic mutation.

It must preserve:

- starting snapshot;
- mandate;
- candidate set;
- model/solver version;
- selected weights/actions;
- before/after risk;
- costs, liquidity, margin;
- uncertainty and robustness;
- binding constraints;
- approval state.

---

# 8. Strategic allocation versus real-time admission

Portfolio optimization and live capital admission are different layers.

```text
Portfolio policy and target allocation
        ↓
Strategy/deployment budgets
        ↓
Signal and sizing request
        ↓
Real-time portfolio admission
        ↓
Transactional reservation
        ↓
Execution delta
```

The optimizer must not bypass the authoritative admission ledger.

Track separately:

- capital budget;
- risk budget;
- exposure budget;
- liquidity budget;
- turnover budget;
- runtime/data-resource budget.

---

# 9. Marketplace object boundary

The future marketplace has two products with a shared allocation interface.

## 9.1 AllocatableProduct

Common profile:

- identity and provenance;
- version;
- economic role/exposure;
- risk snapshot;
- evidence profile;
- fees/costs;
- capacity;
- liquidity/lock-up;
- eligibility;
- conflict disclosure.

## 9.2 StrategyAssetListing

Additional fields:

- package manifest;
- graph/components/configurations;
- data/provider requirements;
- license and modification rights;
- local import/preflight compatibility;
- update policy.

The buyer owns/operates the imported instance under the license.

## 9.3 ManagedModelListing

Additional fields:

- operator;
- regulated/legal route;
- investment terms;
- current capacity;
- current disclosures;
- allocation availability;
- custody/authority boundary.

The investor receives exposure, not necessarily the strategy source.

Do not let a generic “marketplace listing” table erase these differences.

---

# 10. Ownership and authority matrix

Future roles may differ:

```text
strategy author
strategy/package owner
marketplace seller/licensor
package buyer
portfolio owner
broker account owner
model operator
regulated manager
outside investor
corporate treasury owner
advisor/fund manager
```

Architecture should avoid assuming that one user permanently occupies all roles.

Every action must specify:

- who owns the artifact;
- who may view it;
- who may modify it;
- who may deploy it;
- who may execute;
- who bears capital/risk;
- who approves;
- who receives economics;
- which evidence/disclosures are visible.

V0 need not build full organizational ACLs. Ownership identifiers and authority boundaries must not make later roles impossible.

---

# 11. Enterprise exposure and treasury seam

A later enterprise input is not necessarily a traded instrument.

`EconomicExposure` may represent:

- forecast fuel consumption;
- USD receivable;
- floating-rate debt;
- commodity procurement;
- foreign subsidiary cash flows;
- contractual indexation;
- counterparty or liquidity concentration.

It requires:

- legal entity/business unit;
- risk-factor mapping;
- forecast quantity and confidence;
- effective period;
- currency/unit;
- source-system revision;
- natural offsets;
- existing hedges;
- accounting/policy metadata.

A future `TreasuryMandate` constrains permissible hedge candidates, ratios, counterparties, collateral, accounting, and approval.

Do not force enterprise exposures into the current canonical instrument table as fake exchange securities. Preserve a future generalized observation/exposure boundary.

---

# 12. Data and evidence implications

The expanded product requires current contracts to remain generic enough for:

- scalar/time-series/cross-sectional data;
- events;
- option chains/order books;
- risk-model snapshots;
- strategy evidence;
- marketplace disclosures;
- enterprise forecasts and contractual exposures.

Every decision-relevant input should preserve, where applicable:

```text
value
unit/currency
source
canonical economic identity
observed_at
effective_at
published_at
ingested_at
revision
validity
freshness
confidence
```

Do not silently treat:

- current holdings as forecast exposure;
- model estimate as ground truth;
- stale disclosure as current risk;
- backtest as live evidence;
- fund label as look-through economic exposure.

---

# 13. Recommendation governance

Future recommendation systems must remain bounded and inspectable.

Required rules:

1. Generate new candidates or proposals; never silently mutate approved/deployed artifacts.
2. Preserve exact diff, model, source evidence, and post-hoc status.
3. Revalidate after recommendation-induced change.
4. Show multiple solution classes and infeasibility.
5. Disclose platform economic interests.
6. Allow users to exclude platform-owned products.
7. Distinguish uncertainty and evidence quality.
8. Require explicit approval before portfolio, capital, or execution changes.
9. Record rejected recommendations and reasons where appropriate.
10. Monitor feedback loops, crowding, and capacity once recommendations affect marketplace behavior.

---

# 14. Runtime and deployment boundary

The updated vision does not justify premature distributed infrastructure.

Default:

- modular monolith or current application topology;
- authoritative transactional database;
- durable artifact/object storage;
- existing background-job mechanism where adequate;
- bounded worker pools;
- reconstructible caches;
- process-local hot state where safe;
- explicit resource QoS;
- scale only under measured pressure.

No new Kafka, microservices, Kubernetes, workflow platform, Redis cluster, event-sourcing rewrite, CRDT layer, or HFT stack should enter because a V5/V6 concept exists.

Future seams should be interfaces and durable identities, not idle infrastructure.

---

# 15. Verification implications

Use risk-weighted verification.

## Critical now or before reachability

- tenant isolation;
- auth/session/entitlements;
- signal/alert identity;
- research causality and evidence;
- migration/data durability;
- capital reservation and order lifecycle before public execution;
- multi-leg recovery before multi-leg live release;
- marketplace rights/allocations before outside capital;
- treasury approval/accounting before enterprise execution.

## Future research seams

- object contracts;
- refusal states;
- migration compatibility;
- representative model tests;
- ADRs and explicit triggers.

Do not create exhaustive implementation tests for products that are not yet implemented.

---

# 16. Required architecture audit questions

Codex should inspect the current repository and answer:

1. Does signal monitoring have a canonical durable event distinct from delivery/UI state?
2. Can one strategy result eventually create N execution intents?
3. Is execution-product selection separate from strategy signal logic?
4. Can current position storage later represent campaigns, legs, and tranches?
5. Can margin/admission accept a future campaign plan and worst interim state?
6. Does broker netting erase internal ownership?
7. Is Portfolio only a projection, or can a future active revision object be added cleanly?
8. Are risk estimates versionable and provenance-aware?
9. Can external sleeves exist without pretending to have look-through state?
10. Can strategy owner differ from account/deployment owner?
11. Can marketplace origins, licenses, and clone lineage be represented?
12. Can managed products remain distinct from downloadable assets?
13. Can platform recommendation conflicts be disclosed?
14. Can non-security economic exposures later exist without abusing instrument identity?
15. Which assumptions are truly destructive versus safely deferrable?

For each finding classify:

```text
CURRENT V0 DEFECT
V0 SEAM REQUIRED
V1 EXECUTION REQUIREMENT
V1.5 DERIVATIVES REQUIREMENT
V2 PORTFOLIO REQUIREMENT
V3 MARKETPLACE REQUIREMENT
V4 INSTITUTIONAL/MULTI-LEG REQUIREMENT
V5/V6 ENTERPRISE REQUIREMENT
SAFE TO DEFER
REJECTED OVERENGINEERING
```

---

# 17. Required bounded ADRs

Create ADRs only where current code needs a durable decision. Likely candidates:

1. Signal Event and Alert responsibility boundary.
2. Economic Intent versus Execution Product/Structure Policy.
3. Position Campaign and exact-leg lineage seam.
4. Campaign-aware capital/margin preflight seam.
5. Portfolio Snapshot, Risk Snapshot, and Proposed Revision seam.
6. External Portfolio Sleeve confidence/visibility model.
7. AllocatableProduct split: Strategy Asset versus Managed Model.
8. Recommendation authority and platform-conflict disclosure.
9. Generalized Economic Exposure seam for future treasury products.
10. Maturity-gated release ownership and non-implementation boundary.

An ADR should not add empty framework code merely to create a future noun.

---

# 18. Definition of success

The architecture succeeds when:

- V0 becomes simpler and more coherent;
- signal/alerts become a complete endpoint;
- V1 execution planning continues without conflict;
- future multi-leg, portfolio, marketplace, and treasury products remain representable;
- no later ambition forces speculative infrastructure into V0;
- every added abstraction has a current or unavoidable migration purpose;
- the codebase remains understandable by a small engineering team.
