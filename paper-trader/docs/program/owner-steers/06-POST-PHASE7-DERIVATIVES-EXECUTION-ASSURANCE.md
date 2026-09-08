# Post-Phase-7 Derivatives and Execution Assurance Steer

## Goal

Record the owner's execution-concurrency, account-risk, derivatives-capacity, and tier-economics concerns now, preserve the proof seams while Phases 5 through 7 are built, and run one independent Critical assurance audit after Phase 7 review. The examples below start the investigation. They do not limit it.

---

## 1. Timing and authority

This steer was authorized on 2026-08-18.

- Do not expand the active Phase 4 correction with this work.
- Phases 5 through 7 must preserve the identities, authority records, reservations, telemetry, and test hooks needed to prove the contract.
- Run the full assurance audit only after `phase7-review` returns separate SPEC and QUALITY PASS verdicts on a current evidence package.
- Keep Phase 8 blocked until the audit completes and every Critical finding closes through a bounded correction and independent review.
- The audit must search beyond the owner's examples and challenge Phase 5 through 7 acceptance claims rather than inherit them as facts.

---

## 2. Current evidence boundary

As of 2026-08-18, the repository contains useful attribution, deployment, position, transaction, and PostgreSQL locking foundations. It does not yet prove the complete contract in this steer.

In particular, current evidence does not establish:

- one cross-process entry-authority lease for an exact account, book, mode, and canonical instrument;
- one atomic account-wide capital and risk reservation shared by concurrent deployments;
- crash-safe reservation release and reconciliation across every order outcome;
- production-sized derivatives and tier-concurrency envelopes;
- provider-quota, cache, database, queue, and cost behavior during extreme options-market bursts.

SQLite remains useful for fast deterministic tests. It cannot prove the concurrency contract. Critical concurrency and migration claims require disposable PostgreSQL multi-session and multi-process evidence.

No current Phase 4 acceptance, local test, or schema foundation implies that these later execution and capacity requirements already pass.

---

## 3. Entry authority and position ownership

### Entry-authority lease

At most one active deployment may hold entry authority for the exact key:

`(owner_id, broker_account_id, execution_mode_or_book, canonical_instrument_address)`

The canonical instrument is the exact physical contract. A display symbol, provider token, rolling selector, underlying label, or alias must never become the lock key.

Activation, replacement, pause, retirement, expiry, roll, and recovery must serialize against this key. Concurrent contenders produce one winner and a stable typed refusal for every loser. A stale worker must not regain authority after its lease epoch or fencing token expires.

### Position succession

An open position remains owned by the deployment and immutable strategy version that created it.

- A replaced or retired deployment may retain exit, protection, cancel, and reconciliation authority for its existing positions.
- It must not retain new-entry authority after replacement.
- A new deployment must not silently take over an old position.
- Any takeover requires an explicit, reviewed migration record that preserves both old and new lineage.
- Risk-reducing exits remain available even when entry limits, tier limits, provider limits, or account reservations block new risk.

### Research and shadow coexistence

Research and non-money shadow evaluation may coexist on the same instrument when tenant, data, and compute limits allow it. They must not acquire money authority or interfere with the single entry-authoritative deployment.

### Concurrent bindings

- One account may run different strategies on different canonical instruments concurrently.
- One immutable strategy version may have separate deployment bindings for several canonical instruments without cloning or mutating the graph.
- Signals on those bindings may occur at the same time.
- Every binding keeps independent strategy, deployment, instrument, order, fill, position, and exit attribution.
- Admission still depends on one atomic account-wide reservation and every account, tenant, broker, provider, and tier limit.

### Broker netting and internal books

The broker may expose a net position while Strategy OS retains separate virtual deployment books. Broker netting must not erase the creator version, entry allocation, fill lineage, exit ownership, realized and unrealized P&L, fees, or protection state of any virtual book.

---

## 4. Owner seed scenarios

These scenarios are mandatory but not exhaustive.

1. Different strategies on GOLD and CRUDEOIL produce simultaneous buy signals in one permitted account. Both proceed when one atomic account reservation proves sufficient funds and all aggregate limits. If funds or risk capacity cover only one, the result follows a documented deterministic admission policy and never double-spends.
2. One immutable strategy version runs through three distinct instrument bindings. All three may emit buy or sell signals concurrently. Each binding executes or refuses independently while one account aggregate gate protects capital, margin, loss, exposure, order-rate, open-position, and provider limits.
3. Two deployments contend for entry authority on the same exact account, book, mode, and canonical instrument. Exactly one wins. The loser receives a typed conflict and cannot submit a new entry through retries, stale workers, aliases, or another process.

---

## 5. Mandatory adversarial discovery matrix

The post-Phase-7 audit must extend this matrix when repository inspection reveals another plausible failure pattern.

### Instrument and contract identity

- provider aliases, renamed symbols, and duplicate tokens;
- same display label for distinct venues or contracts;
- underlying versus exact future or option contract confusion;
- weekly and monthly expiry overlap;
- expiry, delisting, corporate action, roll, and selector re-resolution;
- stale contract masters and provider disagreement;
- deep-ITM and deep-OTM exact contracts;
- one selector resolving differently across activation, restart, and order submission.

### Deployment and control-plane races

- simultaneous activate, replace, pause, resume, retire, and kill actions;
- two processes or regions attempting the same lease;
- stale lease renewal, worker reclaim, clock skew, and fencing-epoch rollback;
- strategy-version publication while positions remain open;
- restart during activation or authority transfer;
- duplicate, reordered, delayed, or replayed commands;
- old commands arriving after a newer desired state.

### Order lifecycle and reconciliation

- duplicate signals and idempotency-key collisions;
- publish-success followed by local mark failure;
- broker timeout with an ambiguous acknowledgement;
- reject, cancel, cancel-replace, partial fill, multiple fills, and out-of-order updates;
- process death before and after reservation, submission, acknowledgement, fill, and release;
- provider reconnect with missed events;
- external manual orders or positions;
- broker correction, bust, or delayed fee posting;
- retry storms without duplicate money effects.

### Account-wide capital and risk

- simultaneous signals that fit separately but not together;
- cash, margin, collateral, haircut, fees, taxes, slippage, and unsettled-funds changes;
- limits for gross and net exposure, sector or underlying concentration, leverage, daily loss, open orders, open positions, and order rate;
- reservations that expire, leak, over-release, or survive a crash;
- external balance or position changes after preflight;
- fair deterministic allocation when demand exceeds capacity;
- account-level kill, broker restriction, or exchange limit changes during open orders.

### Multi-leg and portfolio actions

- option spreads, hedged futures, baskets, and paired or cross-market trades;
- ordered lease acquisition that cannot deadlock;
- partial-leg execution and compensation policy;
- atomic versus explicitly non-atomic semantics;
- shared underlying exposure across nominally different instruments;
- exits and protection that need several instruments or accounts.

### Safety and degraded operation

- entry blocked while exit, cancel, protection, and reconciliation remain available;
- stale market data, stale account state, stale margin, and split data/execution providers;
- service, database, cache, queue, network, and provider partial outages;
- queue backlog, starvation, priority inversion, and noisy neighbors;
- operator kill and automated risk stop racing with a new signal;
- paper, shadow, and live books crossing or sharing state incorrectly.

### Derivatives-market and tier stress

- market-open, market-close, expiry-day, expiry-roll, event-day, and volatility-halt bursts;
- rapid ATM movement and option-window churn;
- concurrent exact quotes, broad and narrow chains, OI, Greeks, depth, and trade-flow requests;
- multiple underlyings and expiries per tenant;
- held-contract data competing with exploratory windows;
- cache stampedes, cold starts, mass reconnects, and provider throttling;
- Standard, Pro, and Desk admitted maxima, ordinary use, simultaneous conjunctive maxima, and deliberate abuse;
- cross-tenant isolation, fairness, bounded queues, recovery, and cost under sustained and burst load.

### Observability and economics

- exact attribution from request and signal through reservation, order, fill, position, exit, and release;
- lease epoch, reservation state, refusal reason, and reconciliation state visible without exposing strategy IP;
- per-tier physical subscription, event, compute, memory, database, cache, queue, storage, and provider cost;
- p50, p95, p99, saturation point, recovery time, error and degradation counts;
- alarms for leaked reservations, conflicting authority, reconciliation drift, starvation, and provider-budget exhaustion.

---

## 6. Requirements carried through Phase 5

Phase 5 must preserve the information needed for later enforcement without adding runtime authority:

- exact canonical instrument roles and separately addressed deployment bindings;
- per-family and fully lowered node counts, compound depth, edges, fan-out, trigger rates, state, history, subscription, and provider requirements;
- resource profiles for every first-party and custom node;
- stable identities for strategy semantics, ResourcePlan, provider requirement, and tier policy;
- no hidden cost through reusable components, nested compounds, dynamic windows, or custom nodes.

---

## 7. Requirements carried through Phase 6

Phase 6 owns the deployment and preflight contract needed by this audit:

- the exact entry-authority lease and fencing model;
- distinct immutable bindings for one strategy across several instruments;
- explicit creator-version ownership and exit-only succession;
- atomic account-wide capital and risk reservations;
- deterministic conflict and insufficient-capacity decisions;
- idempotent reservation, order, fill, release, and reconciliation lifecycles;
- provider, account, tenant, strategy, deployment, and tier limits enforced conjunctively;
- no live or paper money action before every authority and reservation gate passes.

---

## 8. Requirements carried through Phase 7

Phase 7 owns measured derivatives and runtime evidence:

- physical upstream footprint separated from per-tenant requests and downstream compute;
- safe deduplication without sharing tenant authority or licensed data unlawfully;
- priority and backpressure that preserve positions, exits, protection, kill, and reconciliation;
- measured Standard, Pro, and Desk envelopes with explicit headroom and refusal behavior;
- reproducible workload definitions, durations, repetitions, hardware and service configuration, fixture or approved provider contract, and cost formulas;
- recovery and steady-state evidence after bursts, failure, and reconnect.

---

## 9. Post-Phase-7 audit gate

The audit runs as a fresh independent Sol-high task after `phase7-review` dual PASS. It is read-only in its first pass and must not become an uncontrolled rewrite.

The audit must:

- reconstruct the final Phase 5 through 7 contract from code, schemas, migrations, frontend boundaries, tests, telemetry, and current evidence;
- reproduce all owner seed scenarios through real authority and persistence paths;
- search the complete relevant foundation for each discovered Critical defect pattern;
- run the broader adversarial matrix and add justified cases discovered during inspection;
- use disposable PostgreSQL with genuinely concurrent sessions or processes for authority and reservation claims;
- distinguish repository fact, measured evidence, inference, policy, historical claim, and unknown;
- produce a risk-ranked finding register and transitive evidence-invalidation map;
- measure tier and derivatives envelopes instead of inferring them from local unit tests;
- issue no production-readiness, live-authority, provider-capability, or commercial-price claim without the named evidence and owner decisions.

---

## 10. Acceptance evidence

The post-Phase-7 assurance gate requires:

- exact intake and final tree fingerprints and a machine-readable evidence manifest;
- direct one-winner same-instrument authority evidence under PostgreSQL contention;
- simultaneous different-instrument and one-strategy/many-instrument evidence with sufficient and insufficient account capacity;
- crash, retry, partial-fill, cancel, reject, timeout, restart, reclaim, and stale-command evidence;
- exit and protection continuity under every entry-blocking condition exercised;
- derivative identity, expiry, roll, alias, and provider ambiguity evidence;
- tier-specific sustained and burst workload measurements with p95 and p99, saturation, recovery, and cost;
- proof of bounded queues, memory, connections, reservations, and provider demand after recovery;
- exact Critical closure or an evidence-backed no-Critical disposition before Phase 8.

---

## 11. Nonclaims and owner gates

- Recording this steer does not authorize current implementation, frontend work, provider or broker integration, credentials, deployment, production access, live orders, money movement, or commercial pricing.
- Phase 5 through 7 may implement only their accepted bounded capsules and must stop at their existing owner gates.
- The post-Phase-7 audit may diagnose and propose bounded corrections. It may not implement or redesign product code in its first pass.
- Any material change to live sizing, routing, execution, protection, account-risk policy, provider adoption, legal or regulatory treatment, pricing, or production infrastructure requires the existing owner gate.
- A successful local or disposable-environment test does not establish release deployability or production readiness.
