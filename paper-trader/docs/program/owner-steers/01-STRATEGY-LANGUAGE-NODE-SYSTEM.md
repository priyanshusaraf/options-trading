# Strategy Language & Node System Steer

## Goal

Build a first-party strategy language deep enough that most advanced traders do not need custom code for common technical, statistical, stateful, execution or derivative workflows.

Users may still create custom nodes, but first-party nodes should reduce:
- formula errors;
- wrong warmups;
- lookahead;
- bad missing-data treatment;
- inefficient recomputation;
- provider-specific data fetching;
- live/backtest drift.

---

## 1. Node contract required for every first-party node

Every node declares:

- stable node ID;
- semantic version;
- category;
- input types;
- output types;
- required market fields;
- required resolution;
- warmup/history semantics;
- recursive/rolling/stateless classification;
- state initialization;
- state reset policy;
- completed-bar/partial-bar policy;
- missing-data policy;
- numeric validity policy;
- causal declaration;
- evaluation triggers;
- streaming implementation support;
- vector/batch implementation support;
- live/paper/research eligibility;
- provider capability requirements;
- estimated resource class;
- test/reference provenance.

The graph compiler aggregates these into a whole-strategy requirement set.

---

## 2. First-party indicator starter pack

Do not implement every obscure indicator solely to inflate node count. Target broad professional coverage with well-specified primitives.

### Moving averages
- SMA
- EMA
- RMA / Wilder MA
- WMA
- VWMA
- DEMA
- TEMA
- HMA
- KAMA
- ZLEMA
- VIDYA
- T3

### Trend
- ADX
- +DI
- -DI
- Aroon Up/Down/Oscillator
- Parabolic SAR
- Supertrend
- Ichimoku components
- Vortex +VI/-VI
- moving-average slope
- price/MA distance
- trend persistence

### Momentum
- RSI
- Stochastic
- Stoch RSI
- ROC
- Momentum
- CCI
- Williams %R
- MFI
- MACD
- PPO
- TRIX
- TSI
- CMO
- Ultimate Oscillator
- Fisher Transform

### Volatility
- True Range
- ATR
- NATR
- rolling standard deviation
- rolling variance
- Bollinger Bands
- Bollinger Bandwidth
- %B
- Keltner Channels
- Donchian Channels
- historical/realized volatility
- EWMA volatility
- volatility rank
- volatility percentile

### Advanced realized-vol estimators
- Parkinson
- Garman-Klass
- Rogers-Satchell
- Yang-Zhang

### Volume / participation
- VWAP
- anchored VWAP
- VWMA
- OBV
- Accumulation/Distribution
- Chaikin Money Flow
- Chaikin Oscillator
- Price Volume Trend
- Force Index
- Ease of Movement
- Klinger Oscillator
- relative volume
- volume z-score
- rolling volume percentile

### Price transforms
- Open
- High
- Low
- Close
- HL2
- HLC3
- OHLC4
- typical price
- weighted close
- midpoint

### Statistics
- rolling mean
- rolling median
- rolling min/max
- percentile
- percentile rank
- z-score
- MAD
- skew
- kurtosis
- covariance
- correlation
- autocorrelation
- rolling rank
- variance ratio where appropriate

### Regression / relative value
- linear-regression slope
- intercept
- R²
- residual
- beta
- alpha
- rolling regression
- rolling hedge ratio
- spread
- ratio
- beta-adjusted spread

### Returns
- point change
- percent return
- log return
- cumulative return
- rolling return

### Market/session structure
- session open
- session high/low
- previous session OHLC
- opening range
- gap
- rolling high/low
- distance from session high/low
- bars since session open
- time to session close

### Pattern/event primitives
- cross above
- cross below
- rising
- falling
- inside bar
- outside bar
- gap up/down
- selected candle patterns

Pattern nodes must never imply predictive value. They are merely deterministic feature definitions.

---

## 3. Type 3 derivative/microstructure library

### Option structure
- expiry list
- nearest/next/far expiry
- DTE selector
- ATM
- ATM ± N strikes
- moneyness selector
- delta-target selector
- call/put selector
- option-chain slice
- straddle/strangle selector

### Options analytics
- IV
- delta
- gamma
- theta
- vega
- rho
- IV rank/percentile
- skew
- term structure
- synthetic future
- put-call parity deviation
- straddle price
- chain OI
- PCR by OI
- PCR by volume
- OI concentration
- change in OI
- strike-level volume/OI ratios

Provider-supplied and locally derived fields must be distinguishable.

### Futures
- front/next/far contract
- days to expiry
- basis
- annualized basis
- calendar spread
- roll selector
- continuous research series
- actual tradable mapped contract

### Order book / ladder
- best bid/ask
- spread
- bid/ask quantity
- depth level N
- N-level cumulative bid/ask depth
- depth imbalance
- weighted depth imbalance
- microprice
- book slope
- liquidity concentration
- depth-weighted spread
- provider total buy/sell quantity where available

Do not call all ladder-derived metrics “order flow.”

### Trade-flow features where the provider truly supplies enough data
- aggressor buy/sell flow
- volume delta
- trade imbalance
- cumulative delta

If aggressor-side information cannot be established from the available feed, the node must be unsupported rather than simulated and mislabeled.

---

## 4. Type 1 execution starter pack

### Entry/exit
- Buy / Sell
- Enter Long / Enter Short
- Close Position
- Reverse
- Flatten deployment/account

### Order type
- Market
- Limit
- Stop
- Stop-limit
- IOC/validity where capability exists
- marketable-limit policy

### Position sizing
- fixed units
- lots
- fixed capital
- % of equity
- % risk
- stop-distance risk sizing
- volatility sizing
- max capital cap
- min/max lot constraints

### Protection
- fixed stop %
- point stop
- ATR stop
- take profit %
- risk/reward target
- trailing %
- trailing points
- ATR trail
- breakeven
- multiple targets
- partial exit
- maximum holding time
- session exit
- expiry exit

### Pyramiding / scaling
- add position
- scale by fixed amount
- scale by %
- add only when profitable
- max additions
- max total risk
- aggregate stop handling

### Position/portfolio inputs
- quantity
- average price
- entry price
- MFE
- MAE
- unrealized P&L
- realized P&L
- bars/time in position
- additions count
- account equity
- available margin
- deployment P&L
- daily P&L
- exposure
- drawdown

---

## 5. Type 5 logic, temporal and state pack

### Boolean / comparison
AND, OR, NOT, XOR, >, >=, <, <=, =, !=, between.

### Arithmetic
+, -, *, /, modulo, power, log, sqrt, abs, clamp, round.

### Reducers
min, max, sum, average, count, any, all.

### Temporal
lag N, previous value, bars since, time since, A then B, A within N bars of B.

### Confirmation
N consecutive bars, N of last M, rising/falling for N bars.

### Noise/state control
debounce, cooldown, hysteresis, latch, resettable latch, toggle, counter, state-machine primitives.

### Scheduling
weekday gate, session gate, date range, time range, DTE gate, minutes-from-open, minutes-to-close.

### Validity
Is Valid, Is Missing, Is Stale, Is Undefined, If Missing, explicit fallback.

---

## 6. Custom-node hierarchy

### Level 1 — Fork first-party node
Safest customization. Inherits input/data/state contracts.

### Level 2 — Formula node
Expression over declared inputs.

### Level 3 — Sandboxed custom Python
Advanced flexibility over declared inputs/state only.

### Level 4 — External signal
Timestamped webhook/API input under an explicit data contract.

Do not permit custom strategy code to:
- open arbitrary broker connections;
- fetch undeclared historical data;
- perform hidden external HTTP calls by default;
- read another tenant's data;
- bypass time/causality rules;
- place orders directly.

Custom nodes must have CPU, memory, state-size and evaluation-rate limits and may be marked research-only if they cannot meet live latency/safety requirements.

---

## 7. Numerical validity

Do not collapse all invalid values to NaN.

Represent at least:
- VALID
- MISSING
- STALE
- INSUFFICIENT_HISTORY
- MATHEMATICALLY_UNDEFINED
- PROVIDER_UNAVAILABLE
- NOT_IN_SESSION
- NOT_LISTED

Examples:
- 5/0 -> undefined unless Safe Divide policy supplied
- 0/0 -> undefined
- infinity/infinity -> undefined
- z-score with zero std -> undefined
- correlation with constant series -> undefined
- log of invalid domain -> undefined

Required invalid inputs normally block new entries. Users may explicitly wire fallback logic.

---

## 8. Node versioning

A deployed strategy references immutable semantic node versions.

If an indicator implementation is corrected:
- keep `indicator.v1`;
- release `indicator.v2`;
- tell affected users a new version exists;
- do not silently migrate existing strategy artifacts;
- require revalidation before live migration where semantics change.

This applies to indicator, logic, execution, data-alignment and derivative-selector nodes.
