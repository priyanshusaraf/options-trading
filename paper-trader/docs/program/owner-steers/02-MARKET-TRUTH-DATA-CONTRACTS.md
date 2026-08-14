# Market Truth & Data Contracts Steer

## Goal

Historical and live strategy evaluation must reflect the market structure that actually existed at each timestamp. “Data available today” and “rules today” must never be projected backwards by accident.

---

## 1. Point-in-time market rulebook

The rulebook must be queried by timestamp and canonical instrument identity.

Track, where relevant:
- trading sessions;
- pre/post/auction phases;
- holidays and special sessions;
- expiry conventions;
- weekly/monthly contract cycles;
- actual listed expiries;
- strike intervals;
- actual listed strikes;
- lot size;
- tick size;
- freeze quantity;
- contract listing/delisting dates;
- derivative eligibility;
- settlement/exercise properties where strategy outcomes depend on them;
- margin/product constraints where modeled;
- historical brokerage/tax/fee schedule;
- corporate actions;
- index/universe membership where used in point-in-time research.

A strategy backtest must not expect bars in periods when the market was not open.

---

## 2. Historical derivative truth

For options and futures, prefer actual historical contract-master records over reconstructed rules.

The system must be able to answer:

> Which exact contracts actually existed and were tradable at timestamp T?

This prevents:
- using a modern strike interval in the past;
- inventing strikes that did not exist;
- using a modern lot size historically;
- assuming today's expiry weekday historically;
- using today's futures/option universe to avoid delisted/expired contracts.

If actual contract-master history is unavailable, reconstruction must be explicitly labeled and must not pretend to be ground truth.

---

## 3. Strike-grid evolution

Strike spacing is time-varying and often price/regime dependent.

Do not derive historical strike availability from today's price or today's grid.

A selector such as `ATM ± 5` must operate over the actual strike set available at that timestamp.

---

## 4. Contract identity

Canonical identity is not a broker token.

Store durable economic identity plus point-in-time provider mappings.

Provider exchange tokens/symbols are ephemeral transport identifiers.

The resolver must tolerate:
- expiry;
- relisting;
- token reuse;
- symbol-format changes;
- provider metadata changes.

---

## 5. Futures and continuous series

Separate:
- research signal series;
- actual tradable contract.

Support explicit roll policies:
- expiry roll;
- fixed lead;
- volume;
- OI;
- user-defined logic.

Continuous-series adjustments must be explicit because roll gaps can create false indicator signals.

---

## 6. Option-window policies

Dynamic structures such as `ATM ± N` need explicit recenter semantics.

Possible policies:
- session lock;
- evaluation-dynamic;
- threshold recenter;
- entry lock;
- explicit user event.

Historical replay and live evaluation must use the same policy.

Maintain subscription hysteresis/prefetch buffers internally to avoid repeated subscribe/unsubscribe churn near strike boundaries.

---

## 7. Data sufficiency

Every node declares history requirements.

Before backtest or deployment, calculate the full graph's requirements.

Example:
- SMA(200), daily, requires 200 valid completed observations before first evaluation.
- recursive indicators declare initialization/warmup semantics rather than falsely claiming a finite exact history window.

If data is insufficient:
- do not shorten the indicator silently;
- do not zero-fill;
- do not invent values;
- report earliest valid evaluation or incompatibility.

---

## 8. Live versus historical capability

Provider capability is two-dimensional.

A field may be:
- available live;
- unavailable historically;
- available historically only to a limited depth/range;
- available only at a lower resolution;
- derived locally rather than provider-supplied.

A strategy may therefore be:
- research/backtest capable;
- paper capable;
- live capable;
independently.

If historical order-book data does not exist, do not synthesize fake order flow. Offer prospective recording or a different licensed provider.

---

## 9. Missing-data semantics

Distinguish:
- NOT_IN_SESSION
- NOT_LISTED
- NO_TRADE
- MISSING
- PROVIDER_UNAVAILABLE
- STALE
- INVALID
- INSUFFICIENT_HISTORY

Do not default forward-fill trading-critical data.

Forward fill, interpolation or fallback must be explicit and included in strategy/data provenance.

---

## 10. Cross-instrument alignment

A multi-instrument strategy must declare:
- maximum input age;
- maximum timestamp skew;
- bar alignment policy;
- timezone/session handling;
- stale-input behaviour.

Having a last-known value for every leg does not mean the values represent the same market state.

Default entry behaviour under materially stale/misaligned required inputs: block new entry.

---

## 11. Cross-timeframe causality

Default higher-timeframe input:
> last completed higher-timeframe observation.

If a user chooses a partial/forming bar:
- label it as realtime/repainting capable;
- historical replay must emulate only information known at each historical instant.

No higher-timeframe future leakage.

---

## 12. Corporate actions

Corporate actions may affect more than adjusted equity prices.

Where applicable, track effects on:
- price history;
- derivative strikes;
- contract adjustments;
- lot sizes;
- deliverables;
- indicator continuity.

Research results must record adjustment policy.

---

## 13. Dataset provenance

Every research/backtest result should retain:
- data provider;
- dataset/version identity;
- time range;
- instrument-master version/snapshot;
- market-rulebook version;
- price adjustment policy;
- missing-data policy;
- resampling policy;
- node library versions.

This allows later explanation if the same backtest changes after a data-provider correction or migration.

---

## 14. Provider capability changes

Classify provider changes by semantic impact.

### Level 0 — transparent
No strategy meaning changes. Adapt internally.

### Level 1 — operational
Meaning unchanged; limits/transport behaviour changed. Continue if requirements remain satisfied.

### Level 2 — material capability change
Could change strategy behaviour. Revalidate affected deployments and notify user.

### Level 3 — semantic break
Required behaviour can no longer be guaranteed. Block affected live deployment with an actionable explanation.

Do not disable deployments for trivial provider changes. Do not ignore meaningful semantic changes.

Record provider adapter versions in deployment receipts.
