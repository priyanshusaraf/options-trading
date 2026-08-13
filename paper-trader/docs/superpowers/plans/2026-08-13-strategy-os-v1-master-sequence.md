# Strategy OS V1 Master Sequence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> execute one accepted phase plan task-by-task. This file sequences phase plans; it is not a
> substitute for a phase-specific design or implementation plan.

**Goal:** deliver the complete Strategy OS V1 product through Phase 10 without accepting a later
phase claim before its dependencies are proven.

**Architecture:** keep the product as a modular platform with separate strategy, deployment,
market-truth, provider, execution, and resource authorities. Each phase produces one independently
reviewable capability and evidence gate. Later phases compose earlier immutable receipts rather
than recreating their logic.

**Tech Stack:** Python, FastAPI, SQLAlchemy, PostgreSQL/SQLite development profiles, React/Vite,
Component IR v1, durable plane-local events, and provider adapters.

**Spec:** `paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-v1-product-steer-design.md`

## Global constraints

- Preserve the five visible node families and keep platform layers hidden.
- Strategy definitions remain separate from deployment bindings.
- Causal admission is necessary but never sufficient for live activation.
- Canonical instrument identity is never a broker token.
- Filled positions retain exact contract, strategy-version, deployment, and account attribution.
- Never silently substitute data, rules, providers, order semantics, or protection guarantees.
- Run risk-weighted verification and require rejection-before-acceptance evidence.
- Do not touch inherited protected files unless a later owner-approved phase explicitly removes
  that guard.
- Retain honest nonclaims for managed production, capacity, cost, and provider breadth until their
  named evidence exists.

---

### Phase 1: Ownership and tenant foundation

**Status:** complete.

**Gate:** owner/account-scoped private data, authentication, jobs, APIs, exports, caches,
WebSockets, and two-tenant adversarial isolation.

### Phase 2: PostgreSQL and production-concurrency foundation

**Status:** implemented and locally verified; managed deployment claims remain open.

**Gate:** three PostgreSQL plane profiles, verified copy/restore, fenced account authority,
replica-safe events, takeover/recovery proof, and bounded load evidence.

### Phase 3: Causal strategy admission

**Status:** in progress under
`paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md`.

**Gate:** immutable causal declarations and implementation identity; independent vector/streaming
parity; immutable owner-scoped admission; admission required at research, backtest, promotion,
deployment, and execution boundaries; legacy uncertainty quarantined.

**Nonclaim:** no complete market-data, provider-capability, resource, or live-preflight proof.

### Phase 4: Market truth, numeric validity, and data capability

**Prerequisite:** Phase 3 accepted.

**Design must cover:** closed validity states; point-in-time instrument masters and market
rulebooks; historical contract, strike, lot, session, and adjustment truth; cross-instrument and
cross-timeframe alignment; dataset provenance; provider live/historical capability; and the
existing content-addressed cache as a consumer of these identities.

**Gate:** historical replay refuses present-day rule substitution, invented contracts, silent
forward-fill, ambiguous invalid values, and capability overclaims.

### Phase 5: First-party language and scalable research

**Prerequisite:** Phase 4 accepted.

**Design must cover:** the five-family node metadata contract; substantial professional indicator,
logic, state, execution-intent, and market-structure primitives; one shared conformance harness;
content-addressed datasets; bounded parallel sweeps; and research cost measurement.

**Gate:** representative independent mathematical references, vector/streaming parity, warmup and
validity behavior, causal declarations, and measured research tiers. Catalogue size is not a gate.

### Phase 6: Deployment binding and Strategy Preflight

**Prerequisite:** Phases 3 through 5 accepted.

**Design must cover:** `SELF` and named secondary roles; temporary research bindings; immutable
deployment bindings; provider and account roles; position sizing and capital reservation;
execution/protection intent; open-position version ownership; provider compatibility; exact block
and degraded-state reasons; and preflight receipts.

**Gate:** one strategy version can bind safely to many instruments and accounts without graph
cloning, capital double reservation, silent semantic transformation, or old-position takeover.

### Phase 7: Dynamic derivatives, incremental runtime, and operational economics

**Prerequisite:** Phase 6 accepted.

**Design must cover:** point-in-time option/futures selectors; signal, entry, held-position, and
management universes; recenter and roll policies; order-book capability truth; dependency-aware
incremental evaluation; shared calculations within licence boundaries; dynamic subscriptions;
resource plans and ceilings; runtime QoS; provider fallback; production-like topology, failure,
capacity, and cost evidence.

**Gate:** canonical options/order-flow and cross-market scenarios work without broker-specific
strategy hacks, held contracts never drift with selectors, and lower-priority work cannot starve
protection or live evaluation.

### Phase 8: Guided trader workflow

**Prerequisite:** backend contracts required by the target workflow are accepted.

**Design must cover:** five-family authoring, data and validity explanations, research evidence,
approval, strategy-to-deployment and instrument-to-strategy entry points, preflight, degraded
states, position attribution, and why-an-action-fired receipts without exposing strategy IP.

**Gate:** representative traders can complete research to controlled deployment and understand
every refusal, degradation, and protection guarantee.

### Phase 9: Provider and broker breadth

**Prerequisite:** capability matrix, preflight, and runtime resource contracts accepted.

**Design must cover:** additional data and execution providers through stable capability and
instrument-mapping interfaces, material-change classification, reconciliation, order semantics,
and provider-specific limitations without provider-specific graph semantics.

**Gate:** a second production provider/broker satisfies the same contracts and refusal behavior;
adapter changes cannot silently alter deployed meaning.

### Phase 10: Commercial administration and production customer operations

**Prerequisite:** product safety, tenancy, deployment, and operating evidence accepted.

**Design must cover:** entitlements, billing, customer administration, production identity
operations, support diagnostics, strategy-IP confidentiality controls, audited break glass, and
capability tiers backed by measured resource economics.

**Gate:** commercial controls cannot weaken tenant, money, strategy-IP, or execution boundaries;
operational claims match deployed evidence.

## Programme closure

V1 closes only after the reusable-equity, weekly-options/order-flow, and cross-market scenarios all
pass their architecture acceptance gates; every phase has an accepted evidence report; broad
release verification passes; and outstanding managed-production, capacity, recovery, cost, and
provider nonclaims are either proven or explicitly outside the launch scope.
