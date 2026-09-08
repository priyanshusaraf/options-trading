Reference: [section index](../CANONICAL-BENCHMARKS-AND-ADVERSARIAL-TESTS.md). Read with its scope; this is not a new assignment.

# Strategy OS canonical benchmarks and adversarial tests

Date: 24 August 2026

Benchmarks are heterogeneous verticals, not claims of profitability. Each benchmark proves only the named product contracts. Critical tests protect money, causality, identity, tenancy, provider mapping, point-in-time truth, approval freshness, recovery and reconciliation. Important tests protect math, ranking, semantic conversion, activation, resource and UI contracts.

## Benchmark A — reusable static equity strategy

| Field | Contract |
| --- | --- |
| User thesis | One versioned EMA/RSI/ATR-style Strategy trades `SELF` across several exact equity bindings with sizing, stops/exits and evidence. |
| V1 eligibility | Research, alert, paper and only already-proven controlled execution paths. |
| Exact invariants | One graph version; roles bind separately; no graph clone; exact dataset/provider/rulebook; completed bars; target quantity and admission; exact deployment/signal/intent/fill/position attribution; net charges. |
| Data/provider requirements | Point-in-time listed/tradable equities, OHLCV, session/calendar, corporate actions, canonical provider mappings and execution capabilities. |
| Resource plan | Physical subscriptions after deduplication, bar trigger rate, warmup/state, deployment fan-out, order-action and pending-order ceilings. |
| Expected receipts | Strategy/admission, dataset/truth/capability, ResourcePlan, deployment/preflight, sizing, DecisionBatch/reservation, signal/intent/fill/trade and reconstruction receipt. |
| Failure modes | Role substitution, mutable watchlist, stale candle, cache blending, double capital use, changed Strategy version, wrong fill attribution, fee omission, restart. |
| Acceptance | One immutable Strategy produces the same admitted semantics in research/paper; multiple bindings remain independent; simultaneous capital is deterministic; restart and reconstruction agree. |
| Critical tests | Exact version/address, causal prefix, owner isolation, reservation contention, position ownership, recovery/reconciliation and money/fee equality. |
| Important tests | EMA/RSI/ATR references, warmup, sizing rounding, role UI/read model and explanation. |
| Does not prove | Dynamic Universes, chart semantics, derivatives data, cross-provider coherence for a split route, broad live eligibility or profitable alpha. |

## Benchmark B — NIFTY cross-expiry IV/order-flow strategy

| Field | Contract |
| --- | --- |
| User thesis | Observe underlying plus current/next expiry, bounded ATM/ITM/OTM windows and supported IV/OI/depth/flow fields; route by weekday/DTE/session and produce research/paper decisions. |
| V1 eligibility | Research, alert and paper/shadow where real data exists. Certified options execution is V1.5, not a V1 gate. |
| Exact invariants | Actual listed contracts and rulebook; provider-supplied versus derived Greeks; exact event times/freshness; stable selector/recenter policy; held contract never follows moving ATM; no invented aggressor flow; capability-gated outputs. |
| Data/provider requirements | Point-in-time contract masters, expiries/strikes/lot/tick/session, underlying, quotes, IV/OI/depth/flow and history only where licensed and present. |
| Resource plan | Maximum contracts/expiries/strikes/depth, event rate, warm/active footprint, subscription churn/hysteresis, state and expected duty cycle. |
| Expected receipts | Contract/truth/capability, selector candidates/rejections, ResourcePlan, activation/readiness, observations, branch attribution, research/paper result and exact-held contract receipt. |
| Failure modes | Current contract list projected backward, weekly-cycle hardcode, fake order flow, stale Greeks, option-window churn, missing lookback, wrong held exit, capability lie. |
| Acceptance | Unsupported fields refuse; actual supported data reproduces exact selector/branch decisions; resource ceilings hold; research/paper attribution is complete. |
| Critical tests | Contract identity over expiry/restart, point-in-time rulebook, stale/missing provider data, exact-held ownership, owner/licence isolation and no false live eligibility. |
| Important tests | Window ranking/ties, IV/OI math, DTE/calendar routing, activation hysteresis and resource receipts. |
| Does not prove | V1 live options safety, queue position, fills, multi-leg behavior, complete historical depth or dealer positioning. |

## Benchmark C — dynamic industry rotation with derivatives confirmation

| Field | Contract |
| --- | --- |
| User thesis | Point-in-time NSE scope → market-cap/listing filter → bar-level EMA/z-score/VWAP/price action → group by point-in-time industry → bounded leaders → derivative confirmation → event blackout → stable rank → at most one instrument per industry and three industries per day. |
| V1 eligibility | Deterministic research, alert, paper and only an eligible supported execution product after admission/preflight. |
| Exact invariants | Complete candidate population; point-in-time reference/industry/events; staged evaluation; stable tie-break; exact snapshot; research versus execution eligibility; target sizing; deterministic portfolio constraints; membership leave never erases open-position management. |
| Data/provider requirements | Canonical NSE universe, listing/tradability, market cap/free-float methodology, industry revisions, OHLCV, selected earnings/events, optional bounded derivative confirmation and provider rights. BYOD is acceptable. |
| Resource plan | Stage 1 full-scope cheap facts, bounded Stage 2 bars, top-N Stage 3 derivative breadth, maximum active candidates/subscriptions/events/state and expected duty cycle. |
| Expected receipts | Universe definition/evaluation/snapshot, per-stage pass/fail/reason/cost, rank/tie, ResourcePlan, event blackout, candidate lineage, sizing/admission/reservation and outcome. |
| Failure modes | Survivorship, revised taxonomy leak, current market cap, missing candidate, unstable tie, concurrent refresh, resource blowout, stale derivative input, position leaves Universe, sector concentration violation. |
| Acceptance | Same point-in-time inputs produce the same population/rank/snapshot; every exclusion is explained; resource stages are bounded; deterministic admission selects no more than declared quotas. |
| Critical tests | Publication-time leakage, snapshot immutability, complete population mutation, concurrent refresh/recovery, owner isolation, capital contention and open-position leave. |
| Important tests | Filter/rank math, tie-break, stage transitions, hysteresis/residency, resource receipts and UI reason contract. |
| Does not prove | A complete fundamentals terminal, dealer fact from OI, unlimited market scan, broad provider coverage or profitability. |

Any dealer-positioning feature in this benchmark is a named inference model with assumptions, inputs, version and uncertainty. It is never a raw OI fact.
