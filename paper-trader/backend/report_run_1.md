# Research report

- **Program:** Autonomous nightly research
- **Hypothesis:** the default strategy has exploitable edge on the research sandbox
- **Spec:** `f6c3d61ad3fa2b8f3d29e7523ae88536`  ·  commit `8baf4847cd28aedbc3791e504244d85198363d1a`  ·  run #1
- **Decision:** archive  ·  bars evaluated: 966

## How this strategy works
**Trend Impulse V3 (EMA-z)** — `trend_impulse_v3`

**Thesis:** Price that breaks decisively away from its own trend line tends to keep moving in the direction of that trend — momentum, filtered by trend so only breakouts that agree with the prevailing drift are taken.

**Primitives:** Trend · MeanReversion · Confirmation

**Logic (with this run's parameters):**
1. Trend filter — EMA(50) of close; the trend is UP when that EMA is above its own value 5 bars ago, DOWN when below.
2. Displacement — z = (close − EMA) ÷ the 50-bar population standard deviation of close: how many standard deviations price sits from its trend line.
3. Enter long — only in an up-trend, on the bar z crosses above +1.0 and is still rising (a fresh, still-expanding breakout away from the trend).
4. Enter short — the mirror image: in a down-trend, z crosses below −1.0 with the displacement widening.
5. Exit long — z falls back below 0 (price has returned to its EMA) or the trend flips down; short exits mirror this. The edge is 'expired' once price re-converges.

> Parameters were optimized within a bounded grid per walk-forward fold; the values above are the search base — see the OptimizationTrial ledger for each fold's winner.

_Not modelled: position size is 1 lot and P&L is additive; stops, targets and trailing are the engine's risk overlay, not the strategy — the backtest measures the raw signal edge._

## Validated candidates (0)
- none cleared the validation gates

## Promotion proposal
- none

## Rejected (6) — negative evidence
- COPPERM: insufficient trades (1<20)
- CRUDEOIL: insufficient trades (3<20)
- GOLDM: insufficient trades (3<20)
- NATURALGAS: insufficient trades (5<20)
- SILVERM: insufficient trades (2<20)
- BANKNIFTY: insufficient trades (4<20)

## Qualifying universe (0)
- none
