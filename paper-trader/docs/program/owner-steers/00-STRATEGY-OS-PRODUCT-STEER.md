# Strategy OS — Product Architecture Steer

## Purpose

This document freezes the product direction for the next implementation phase.

The system is no longer a single autonomous options bot. It is a **Strategy Operating System** in which a trader can define a strategy once, research it across many instruments, inspect and improve it, then bind the exact approved strategy version to one or many live deployments without rewriting it.

The highest-level product promise is:

> A trader should be able to express what they mean, have Strategy OS prove that the required data and market structure actually support that meaning, and move the exact same strategy from research to shadow, paper and live without silent semantic changes.

Do not optimize for node count, test count, broker-specific convenience, or architectural cleverness. Optimize for:
1. strategy correctness;
2. historical truth;
3. live/backtest semantic parity;
4. real-money safety;
5. data/provider portability;
6. user trust;
7. interactive research speed;
8. bounded infrastructure cost.

---

## 1. The five user-facing node families

Every visible strategy node should fit into one of these categories.

### Type 1 — Execution & Position

What should be traded and how should the resulting position be managed?

Examples:
- Buy / Sell / Long / Short
- Enter / Exit
- Market / Limit / Stop / Stop-limit
- Quantity / lots / capital sizing / risk sizing
- Stop loss / take profit / breakeven / trailing stop
- Partial exit
- Pyramiding / scale in / scale out
- Reverse
- Time exit
- Session/expiry exit
- Broker-resident protection request
- Position state
- Portfolio/account risk guards

Type 1 nodes create **execution intent**. They do not directly call a broker-specific API.

### Type 2 — Indicators & Derived Features

Reusable mathematical transformations over market, position or cross-instrument data.

Examples:
- SMA, EMA, RMA/Wilder, KAMA
- ATR, RSI, CCI, ADX, Parabolic SAR
- Bollinger, Keltner, Donchian
- VWAP, anchored VWAP, OBV
- z-score, percentile, correlation, covariance
- regression, beta, residual, rolling hedge ratio
- realized volatility estimators
- market/session-derived features

First-party nodes are versioned, tested primitives. Users may fork them.

### Type 3 — Market Structure, Derivatives & Cross-Instrument

Nodes that define or aggregate another market, derivative structure, basket, option chain, futures curve or order-book structure.

Examples:
- another equity/index/future/option as an input
- peer basket
- option expiry selector
- strike selector
- ATM ± N strike window
- delta/DTE-based option selection
- option chain
- OI / change in OI
- IV / skew / term structure
- Greeks
- futures basis / curve
- top-of-book / depth / ladder
- bid/ask imbalance
- microprice
- cross-instrument order flow
- relative value structures

This family includes using ICICI/Bandhan prices or option data to trade HDFC.

### Type 4 — Price, Instrument & Market Data

Primitive market/instrument inputs.

Examples:
- OHLCV
- LTP
- bid / ask / mid / spread
- volume / OI
- session open/high/low
- previous session fields
- timeframe
- market clock
- DTE
- expiry/session calendar
- instrument metadata
- resampling

Type 4 answers: **what field from what instrument at what time?**

### Type 5 — Logic, Math & State

How the trader combines information and remembers prior events.

Examples:
- IF / ELSE IF / ELSE
- AND / OR / NOT / XOR
- >, >=, <, <=, =, !=
- +, -, *, /, power, log, abs
- min / max / sum / mean
- cross above / cross below
- bars since / time since
- A then B
- N of last M
- debounce / cooldown / hysteresis
- latch / toggle
- user-defined variables/state
- weekday/session gates
- Is Valid / Is Missing / Is Stale

---

## 2. Hidden platform layers

Do not expose these as a sixth node family. They are platform responsibilities.

### A. Instrument Resolver
Maps durable economic intent to the actual tradable contract at a point in time.

### B. Point-in-Time Market Rulebook
Knows the market rules that were actually in force at each historical timestamp.

### C. Data Contract Engine
Determines the fields, history, freshness, resolution and provider capability required by every node.

### D. Causality Engine
Prevents lookahead and undeclared historical/future access.

### E. Provider Capability Matrix
Tracks what each connected provider can supply live/historically and what each execution broker can express.

### F. Subscription & Resource Planner
Compiles broker subscription load, compute load, state size and storage cost before deployment.

### G. Numeric Validity System
Distinguishes valid, missing, stale, undefined and unavailable values.

### H. Deployment Binding System
Binds a reusable strategy version to instruments, providers, accounts, capital and mode.

---

## 3. Strategy definition is not deployment

A strategy normally trades `SELF` / `PRIMARY`, not a hardcoded symbol.

Example strategy:
- Close(SELF) -> EMA(50)
- RSI(SELF, 14)
- IF conditions -> BUY SELF
- Exit graph -> SELL SELF

A deployment binds:
- `SELF = HDFCBANK`
- strategy version
- parameter overrides
- data provider
- execution broker/account
- shadow/paper/live mode
- capital/risk allocation
- schedule
- execution/protection policy

The same strategy version may have many deployments without cloning the graph.

### Two equivalent UI entry points

From an instrument:
> HDFCBANK -> Add Strategy -> choose strategy -> configure -> deploy

From a strategy:
> Strategy -> Deployments -> Add Instrument -> configure -> deploy

Research uses temporary bindings across a universe and does not create permanent deployments.

---

## 4. Named secondary instrument roles

Strategies may define reusable roles such as:
- SELF
- BENCHMARK
- PEER_A
- PEER_B
- HEDGE
- SIGNAL_MARKET
- UNDERLYING
- EXECUTION_MARKET

Deployment maps those roles to actual instruments.

Hardcoded instruments remain allowed where the economic relationship is itself part of the strategy.

---

## 5. Dynamic derivative identity

Strategies should refer to selection rules, not fragile broker symbols.

Good:
- nearest eligible weekly call
- ATM + 2 strikes
- target delta 0.35 ± 0.05
- 3–8 DTE
- front-month future
- second monthly future

Bad:
- a provider token
- a symbol that expires next week
- today's strike list embedded into the graph

The economic selector remains stable. The physical instrument changes.

### Critical invariant

A dynamic selector may change after entry. A held position's identity may not.

If `Current ATM Call` changes after spot moves, `POSITION.INSTRUMENT` must still point to the exact contract actually filled.

---

## 6. Options lifecycle model

Separate four concepts:

1. **Signal universe** — instruments/contracts observed for signals.
2. **Entry selector** — rule choosing the actual contract to trade.
3. **Held position** — exact instrument filled.
4. **Management universe** — information allowed to influence exits.

Example:
- signal universe: NIFTY + ATM ± 5 calls/puts
- entry selector: nearest weekly 0.45–0.55 delta call
- held position: the exact resolved contract
- management universe: held option + NIFTY + current ATM ± 3 chain

Option exits may depend on:
- premium
- underlying
- option-chain state
- IV/Greeks
- OI/order-flow changes
- liquidity
- time
- DTE
- arbitrary strategy state

Stop/TP nodes are convenience primitives, not the only exit mechanism.

---

## 7. Position and strategy state

State is first-class.

Families include:
- indicator state
- strategy state
- session state
- position state
- execution state
- portfolio state
- derivative-selection state
- user-defined state

Every stateful node declares reset semantics:
- never
- session
- position close
- expiry/roll
- N bars/minutes
- explicit event

Open positions remain owned by the strategy version that created them unless the user performs an explicit reviewed takeover.

---

## 8. Trust is a product requirement

Senior traders will not trust a platform merely because the backtest is correct.

Trust requirements:
- no silent changes to deployed strategy semantics;
- immutable/versioned strategy artifacts;
- exact provenance for data, node versions and provider adapters;
- clear explanation of why a strategy is blocked/degraded;
- visible distinction between broker-resident and software-managed protection;
- reproducible historical results;
- explicit position attribution;
- ability to inspect what data was used and why an action occurred;
- support/admin tooling must not casually expose strategy source/graph contents;
- strategy data encrypted at rest and tenant-isolated;
- access to secrets and strategy content separated operationally;
- break-glass access tightly controlled and audited;
- no internal product feature may allow staff to browse customer strategy IP.

Do **not** claim cryptographic zero-knowledge/operator-blind execution in V1 if Strategy OS servers must decrypt and execute the strategy. A stronger architecture such as local runners/confidential compute may be explored later.

Coworker/team strategy sharing is **post-V1**. Design ownership identifiers so ACL sharing can be added later without rewriting strategy storage, but do not spend V1 scope implementing sharing UX or collaboration.

---

## 9. V1 acceptance scenarios

### Scenario A — reusable equity strategy
EMA + RSI + ATR, trades SELF, deployed unchanged across many equities, with sizing, stops and pyramiding.

### Scenario B — Indian options/order-flow strategy
Trades a dynamically resolved weekly option; observes ATM ± N calls/puts, OI and depth; has historical point-in-time expiry/strike/lot/session rules; arbitrary exit logic; broker-resident or software-managed protection; runs only on configured weekdays.

### Scenario C — cross-market strategy
Trades one market using multiple external markets/providers with different timezones, sessions, freshness and missing-data behaviour.

If the architecture cannot express all three cleanly without broker-specific hacks, revisit the abstraction before expanding implementation.

---

## 10. Non-negotiable product rules

1. Never silently substitute unavailable data.
2. Never silently forward-fill trading-critical data.
3. Never use today's market rules to reconstruct the past.
4. Never use current contract lists as historical universes.
5. Never let custom code fetch arbitrary broker data outside declared inputs.
6. Never silently change a deployed node implementation.
7. Never treat a provider token as canonical instrument identity.
8. Never let one deployment's heavy research work delay live protection.
9. Never evaluate a multi-instrument condition on materially stale/misaligned inputs without an explicit policy.
10. Never equate `NaN`, market closed, contract nonexistent and provider outage.
