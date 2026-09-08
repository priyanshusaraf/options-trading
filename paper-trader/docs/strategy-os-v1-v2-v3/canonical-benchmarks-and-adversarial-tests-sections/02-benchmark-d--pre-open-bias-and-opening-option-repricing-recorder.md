Reference: [section index](../CANONICAL-BENCHMARKS-AND-ADVERSARIAL-TESTS.md). Read with its scope; this is not a new assignment.

## Benchmark D — pre-open bias and opening option-repricing recorder

| Field | Contract |
| --- | --- |
| User thesis | Observe declared pre-open and market-open inputs, warm exact contracts, record quotes/depth/latency and compare a pre-open bias with opening option repricing. |
| V1 eligibility | Prospective recorder, research and shadow/paper only. Explicitly not V1 live. |
| Exact invariants | Actual session events; exact instruments/contracts; no data before availability; warm/readiness state; receive/evaluate timestamp chain; honest data gaps and non-HFT eligibility. |
| Data/provider requirements | Licensed GIFT Nifty/futures/index/option observations where selected, pre-open/open calendar, quotes/depth and provider timestamp quality. |
| Resource plan | Bounded pre-open instruments/contracts, WARM interval/lookback, peak open event rate, storage, clock quality and subscription confirmation. |
| Expected receipts | Provider/truth/capability, activation/readiness, raw/normalized observations, latency components, recorder artifact, research/shadow result and refusal eligibility. |
| Failure modes | Future/open leakage, clock skew, late subscription, missing first event, stale depth, timestamp misinterpretation, provider disconnect and false subsecond/live claim. |
| Acceptance | Recorder captures exact available observations and gap states, reconstructs after restart, reports measured latency and refuses unsupported execution eligibility. |
| Critical tests | Availability causality, contract mapping, clock/timezone, restart/correction lineage and no path to live order authority. |
| Important tests | Warm-state transitions, storage bounds, display timelines and marketable-limit policy simulation. |
| Does not prove | Profitable opening edge, exact fills, exchange queue position, live V1 suitability or options certification. |

## Benchmark E — operator-defined chart thesis with automated confirmation

| Field | Contract |
| --- | --- |
| User thesis | User creates and locks bounded chart semantics; price approaches a declared zone; expensive confirmation warms; machine explains a qualifying setup and issues an expiring proposal; user approves/rejects; system revalidates before paper/eligible action. |
| V1 eligibility | Forward monitoring, alert, proposal, paper/shadow and only separately eligible controlled execution. No general historical annotation backtest. |
| Exact invariants | Separate vendor/semantic storage; exact `OperatorThesis` revision; Strategy/provider/dataset/Universe binding; explicit activation/readiness; proposal TTL; revalidation of price/spread/liquidity/capital/freshness/position/provider/coherence; open position retains creating revisions. |
| Data/provider requirements | Approved chart library and data display rights; canonical chart datafeed; forward market/confirmation data; execution reference where applicable. |
| Resource plan | Workspace/artifact bounds, drawing count/autosave rate, confirmation branch warm/peak demand, proposal/action limits and expected duty cycle. |
| Expected receipts | Vendor artifact, normalized semantics, thesis lock/successor, activation/readiness, explanation, proposal, approval/rejection/expiry, revalidation, paper/action and post-trade review. |
| Failure modes | Vendor blob in IR, snapped-point mismatch, wrong instrument/timeframe, thesis edit mutates position, vendor lock treated as authority, stale approval, chart marker routes order, tenant leak, vendor-version migration loss. |
| Acceptance | Allowlisted semantics round-trip and normalize deterministically; locked revision is immutable; proposal expires; every material change makes approval stale; revalidation precedes action; chart provider has no execution authority. |
| Critical tests | Revision/owner/provider substitution, approval expiry/staleness, price coherence, capital/revalidation, position-version ownership, chart-to-order bypass and artifact restore. |
| Important tests | Drawing create/edit/save/load/tombstone/group, semantic math, activation, keyboard structured alternative, CSP and React lifecycle. |
| Does not prove | Hindsight chart validity, unsupported drawings, TradingView parity, Pine/alerts/Strategy Tester, AI interpretation or broad live authority. |

## Benchmark F — cross-market signal, different execution instrument/provider

| Field | Contract |
| --- | --- |
| User thesis | Observe one or more BSE/NSE/other-market derivative or context inputs while trading a separately bound cash/future instrument through another execution provider. |
| V1 eligibility | Research, alert, paper and controlled eligible execution where exact products/providers pass. |
| Exact invariants | Observed instrument ≠ thesis instrument ≠ execution instrument is supported; canonical mappings; time/session/freshness alignment; independent data/execution providers; PriceCoherencePolicy; exact target sizing and attribution. |
| Data/provider requirements | Licensed observed fields, canonical mappings across venues, comparable executable-side bid/ask/reference, clocks, sessions and provider capability. |
| Resource plan | Cross-market subscriptions, fan-out, event/skew checks, provider quotas, readiness and fallback prohibition. |
| Expected receipts | Role/binding, mapping, observation/alignment, capability, ResourcePlan, price coherence, latency/preflight, signal, sizing/admission/reservation, intent/fill/position. |
| Failure modes | Wrong contract mapping, stale market, incompatible LTP/mid/bid/ask, silent fallback, clock skew, provider split-brain, cache owner/provider omission and execution target substitution. |
| Acceptance | A materially divergent or stale executable reference blocks entry with `DATA_DIVERGENT`; safe exits remain; all three instrument roles and both provider roles remain attributable through fill. |
| Critical tests | Mapping, age/skew/divergence, provider failure/reconnect, owner isolation, cache identity, capital contention, exact fill attribution and exit behavior. |
| Important tests | Capability compilation, resource accounting, latency display, reason UX and bounded user thresholds. |
| Does not prove | Universal provider compatibility, data rights, queue-sensitive execution, seamless fallback or profitable cross-market edge. |
