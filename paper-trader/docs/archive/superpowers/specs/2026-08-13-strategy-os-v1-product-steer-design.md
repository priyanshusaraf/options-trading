# Strategy OS V1 Product Steer Reconciliation

**Date:** 2026-08-13

**Decision:** preserve the ten-phase programme, but make the six owner-authored steer documents
the governing product direction wherever older roadmap language conflicts.

**Owner sources reconciled in full:**

- `00-STRATEGY-OS-PRODUCT-STEER.md`
- `01-STRATEGY-LANGUAGE-NODE-SYSTEM.md`
- `02-MARKET-TRUTH-DATA-CONTRACTS.md`
- `03-DEPLOYMENT-EXECUTION-TRUST.md`
- `04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md`
- `05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md`

This repository document is the durable programme interpretation of those sources. It does not
replace their detailed node catalogue or examples; phase-specific designs must trace applicable
requirements back to this reconciliation before implementation.

## 1. Product promise

Strategy OS lets a trader define one immutable strategy, prove that its data and market
requirements support its meaning, research it across temporary instrument bindings, and bind the
same approved version to shadow, paper, or live deployments without silently changing semantics.

The programme optimises, in order, for strategy correctness, historical truth, research/live
parity, real-money safety, provider portability, trader trust, interactive research speed, and
bounded infrastructure cost. Node count, test count, provider convenience, and architectural
novelty are not success measures.

## 2. Stable product boundaries

### 2.1 Five visible node families

Every user-visible node belongs to exactly one family:

1. execution and position;
2. indicators and derived features;
3. market structure, derivatives, and cross-instrument inputs;
4. price, instrument, and market data; or
5. logic, mathematics, temporal operations, and state.

Instrument resolution, point-in-time market rules, data contracts, causality, provider
capabilities, resource planning, numeric validity, and deployment binding remain hidden platform
layers. They are not a sixth user-facing family.

### 2.2 Strategy is not deployment

A strategy uses durable roles such as `SELF`, `BENCHMARK`, `HEDGE`, `UNDERLYING`, and
`EXECUTION_MARKET`. A deployment binds those roles to instruments, providers, an execution
account, mode, capital, scheduling, execution policy, protection policy, and resource limits.
Research may create temporary bindings without creating deployments. One strategy version may
have many deployments without cloning the graph.

### 2.3 Economic identity is not transport identity

Canonical instruments and derivative selection rules are durable economic identities. Broker
tokens and symbols are point-in-time transport mappings. Dynamic selectors may change their next
candidate, but a filled position remains attached to the exact resolved contract and the strategy
version that created it.

### 2.4 Admission is necessary, never sufficient

Phase 3 causal admission proves closed implementation identity, completed-bar causality, and
vector/streaming parity for an exact strategy artefact. It does not prove:

- point-in-time market truth;
- provider field or execution capability;
- cross-instrument freshness and alignment;
- numeric validity semantics beyond the currently admitted kernels;
- data sufficiency for a requested binding;
- resource affordability;
- order or protection compatibility; or
- production deployment readiness.

Strategy Preflight composes causal admission with those later receipts. No consumer may treat an
`admission_address` alone as permission to activate live trading.

## 3. Required node and data contracts

The completed Phase 3 causal contract is one part of the full first-party node contract. Before
the catalogue expands broadly, every first-party node must also declare its stable semantic
identity, family, typed inputs and outputs, required fields and resolution, initialization and
reset rules, completed/partial-bar policy, missing-data and numeric-validity policy, evaluation
triggers, research/paper/live eligibility, provider requirements, resource class, and test or
reference provenance.

The platform must preserve distinct validity states, including valid, missing, stale,
insufficient-history, mathematically-undefined, provider-unavailable, not-in-session, and
not-listed. It must not silently forward-fill, shorten warmups, invent historical universes, use
current market rules in the past, or synthesize unavailable order-flow data.

Point-in-time market truth includes actual sessions, expiries, listed strikes, lot and tick sizes,
listing dates, rule changes, adjustment policy, and provider mappings at timestamp `T`. Historical
contract-master evidence is preferred. Reconstruction is separately labelled and cannot be
presented as ground truth.

## 4. Runtime and deployment contracts

Research may use vector or batch execution. Live operation uses incremental state transitions and
dependency-aware invalidation. Both modes must remain semantically equivalent. Every deployment
compiles a resource plan covering subscriptions, history, state, fan-out, compute, storage,
provider quotas, and dynamic event load.

Runtime priority is:

1. existing-position protection, kill, and reconciliation;
2. live execution-critical data and evaluation;
3. paper and shadow;
4. interactive research;
5. batch optimisation;
6. nonessential visualisation.

Lower priorities degrade before protection or live evaluation. Shared calculations are permitted
only within ownership and data-licence boundaries. Cache identity includes every semantic input,
not merely a node name.

Deployment preflight must explain exact refusal or degraded-state reasons. It distinguishes
strategy-managed exits, software-managed hard protection, and broker/exchange-resident protection.
Unsupported execution semantics are refused or transformed only with an explicit user-visible
consequence. Concurrent deployments cannot reserve the same capital independently, and broker
netting cannot erase internal strategy/deployment ownership.

## 5. Ten-phase programme

| Phase | Outcome | Status at adoption |
| --- | --- | --- |
| 1 | Tenant, owner, account, authentication, and private-plane boundaries | complete |
| 2 | PostgreSQL profiles, concurrency, fencing, replica events, copy/restore, and local failure proof | implemented locally; production nonclaims remain |
| 3 | Closed causal node declarations, transitive implementation identity, immutable causal admission, independent vector/streaming parity, and authority wiring | in progress |
| 4 | Numeric validity, point-in-time instrument/rulebook truth, dataset provenance, and provider data-capability contracts; retain the completed content-addressed cache as one component | pending except existing cache foundation |
| 5 | Substantial first-party node library through one shared conformance harness, plus scalable content-addressed research and sweeps | partial foundations |
| 6 | Strategy/deployment separation, named instrument-role bindings, provider/execution bindings, sizing, protection intent, and complete Strategy Preflight | partial foundations |
| 7 | Dynamic derivatives and option/futures structures, incremental subscriptions, shared computation, resource planning, QoS, and production topology/failure proof | partial infrastructure foundations |
| 8 | Guided research-to-approval-to-deployment UX on the proven contracts | partial frontend foundation |
| 9 | Additional data and execution adapters through an explicit capability matrix | deferred |
| 10 | Commercial administration, entitlements, and production customer operations | partial identity foundation |

Each phase gets its own accepted design, risk classification, task plan, RED/GREEN implementation,
independent review, and evidence record. A later phase may use an earlier phase only after its named
gate passes.

### Interphase 3 → 4: Component IR v2 structural contract

**Status:** future / not started; approved design handoff; current terminal condition is Phase 3 only.

After Phase 3 Task 12 closes its narrow causal and v1 edge-safety gate, and before Phase 4 or
Phase 5 expands catalogue/persistence work, the platform will adopt the forward-only Component IR v2 Port contract in
`docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md`. This is a
structural prerequisite, not an eleventh phase and not a new acceptance claim for Phase 3.

IR v2 freezes v1 as readable, immutable legacy format and accepts new v2 artefacts only through a
format dispatcher. A published v2 topology, port set, nested interface, and branch manifest are
immutable; runtime may select only a predeclared branch. The extension does not convert v1 graphs,
claim v1 has the required Port semantics, broaden live authority, or satisfy any Phase 4 market
truth, Phase 5 catalogue, Phase 6 preflight, or Phase 7 runtime-economics gate.

## 6. Canonical V1 acceptance scenarios

The architecture is accepted only when it supports all three scenarios without provider-specific
strategy hacks:

1. A reusable equity strategy using `SELF`, EMA, RSI, ATR, sizing, stops, and pyramiding across
   many deployments without graph cloning.
2. An Indian weekly-options strategy using point-in-time expiry, strike, lot, session, OI, and
   depth truth; a dynamic selector; a frozen held contract; arbitrary exits; explicit protection;
   and scheduled trading days.
3. A cross-market strategy using multiple providers and sessions with explicit freshness,
   alignment, missing-data, and execution-market policies.

These are architecture acceptance scenarios, not instructions to build an exhaustive permutation
matrix.

## 7. Verification policy

Every task is classified before implementation:

- **Critical:** money, execution, protection, causality, vector/streaming parity, isolation,
  accounting, point-in-time truth, dynamic contract identity, position ownership, and irreversible
  corruption. Use explicit invariants, RED/GREEN, adversarial and integration proof, independent
  review, and concurrency/recovery proof where relevant.
- **Important:** indicator mathematics, backtests, providers, caches, events, preflight, and
  entitlements. Use focused representative tests, regression tests for observed failures, and one
  review pass.
- **Routine:** CRUD and ordinary workflow or presentation behavior. Prefer affected tests,
  typechecks, and smoke tests.
- **Trivial:** copy and harmless styling. Usually no dedicated test.

Every new test names a realistic failure hypothesis. After two failed test/fix loops outside a
Critical area, reassess the requirement before continuing. Run affected tests during work,
subsystem suites at meaningful commit boundaries, and broad suites at phase or release boundaries.

## 8. V1 nonclaims and deferrals

V1 does not claim cryptographic zero-knowledge execution while the server must decrypt a strategy
to run it. Team sharing UX, a marketplace, an AI research agent, broad foreign-broker support,
confidential compute, every obscure indicator, and deep institutional integrations remain deferred.
Ownership stays explicit so future revocable ACLs do not require rewriting strategy storage.

No staff-facing product feature may casually expose customer strategy contents. Ordinary support
uses scoped diagnostics and receipts; strategy storage access and broker-secret access remain
operationally separated; break-glass access is controlled and audited.

## 9. Phase 3 reconciliation

Tasks 1 through 3 remain valid and complete. Task 4 remains Critical and builds only the
independent causal parity lane of the future first-party conformance harness. Tasks 5 through 12
continue to bind causal admission through existing research, backtest, promotion, deployment, and
execution paths, but every such use is an additional necessary guard, never complete Strategy
Preflight.

Phase 3 must retain these explicit nonclaims in code documentation and closure evidence:

- the current fixture suite does not prove the eventual full node catalogue;
- scalar `NaN` behavior is not the future numeric-validity model;
- static OHLCV causality does not prove multi-provider alignment or point-in-time rules;
- a causally admitted graph is not automatically live-capable; and
- Phase 3 does not implement the dynamic derivative, provider, resource, or deployment contracts
  assigned to Phases 4, 6, and 7.

Phase 3 does require narrow v1 graph safety before it closes: direction refusal in library-aware
validation, resolution, and registry closure; duplicate-target refusal in validation plus
independent vector-runtime and prefix-reference defenses against last-write-wins collapse. The
resolved runtimes do not claim independent direction checks. A graph component's published v1
interface must also exactly equal its graph body's interface, and every declared graph output must
have exactly one producer. These requirements use the existing v1 interface and do not create v2
Ports, generalized cardinality, compatibility, or semantic-flow claims.

Phase 3 also does not add the Component IR v2 Port contract, richer Port/cardinality/compatibility
semantics, semantic-flow compound substitutability, fixed dynamic branches, or v1-to-v2 migration.
Those are the future, not-started interphase extension after Task 12. This nonclaim does not defer
the narrow v1 published-interface-to-body equality or exactly-one graph-output producer rule.
Causal admission must not be described as evidence that the v1 socket grammar carries the richer
v2 facts.
