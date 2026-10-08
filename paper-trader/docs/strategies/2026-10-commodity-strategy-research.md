# Commodity strategy research — MCX NG / crude / gold (October 2026)

**Goal (owner's brief):** five meaningfully different, OHLCV-only strategies for MCX
commodities (primary: NATGASMINI and GOLDPETAL; also CRUDEOILM, SILVERMIC), built in
layers so that each component's contribution is measured, each mapped to the market
regime it is for — and at least one profitable **after charges** on gold, natural gas
or crude.

**Short answer:** see [§6 Verdict](#6-verdict). Most textbook intraday ideas (VWAP-slope
trend, SuperTrend, squeeze breakout, session-VWAP fades) do **not** survive the MCX
mini-contract cost stack out-of-sample. What did survive was found by measuring
components first: **multi-session fades of energy shocks** (`spike_fade` on NG and crude,
`shock_reversal` on crude) and **swing reversion to a 10-day VWAP after a climax push**
(`vwap_band_reversion`, NG). They hold on real NYMEX bars, on broad parameter
plateaus, and on the bot's options path once each strategy carries its own option-exit
policy (§6b–§6c) — and on **real MCX prints** (§6e): every strategy that passed made
money there, every one that failed lost. Gold's calendar effect (`gold_month_turn`) did
not survive the real-MCX check; silver has no strategy (§6d).

---

## 1. Data — and why it is a proxy

The cloud session had no Kite login, so MCX prints were not available. Instead:

| MCX contract | Proxy source (Dukascopy, 5-minute bars, 2019-01 → 2026-10) | ₹ conversion |
|---|---|---|
| NATGASMINI (250 mmBtu) | NYMEX natural gas CFD (`gascmdusd`) | × USDINR |
| CRUDEOILM (10 bbl) | WTI CFD (`lightcmdusd`) | × USDINR |
| GOLDPETAL (1 g), GOLDM (100 g) | spot gold (`xauusd`) | × USDINR × 1.06 / 31.1035 (≈ import-duty premium) |
| SILVERMIC (1 kg) | spot silver (`xagusd`) — download rate-limited, incomplete | × USDINR × 1.06 × 32.1507 |

Processing (`research/commodity/build_dataset.py`):
* bars kept only inside the **MCX session** — 09:00 IST to 23:30 (US daylight time)
  or 23:55 (US standard time) — and resampled to 15m/30m/60m bars anchored at 09:00
  IST, as Kite builds MCX candles;
* **USDINR** (Yahoo daily) is interpolated across Indian FX hours (09:00→17:00 IST), so
  rupee drift is not dumped into the overnight gap (an early version did exactly that
  and overstated every overnight hold by ≈1.6 bps/night — caught and fixed);
* **futures rolls** (NG 46, crude 10 detected gaps ≥ 1.5% at the daily reopen) stay at
  their true price level; the harness removes the roll gap from any trade held across
  a roll (a trader rolls the position — the contract spread is not P&L);
* volume = Dukascopy tick volume (used only relatively: VWAP weights, volume gates).

Limits to keep in mind: the proxy follows the international contract, not MCX's own
order book; MCX-specific gaps, circuit limits, holidays and the MCX–COMEX basis are not
modelled. **Re-validate every strategy on real Kite MCX candles before use** — the
strategies are registered in the platform, so the Backtests view can do that directly
(Kite gives ~200 days of 15m history).

## 2. Method

* Every number comes from the platform's own engine (`app/backtest/engine.simulate`):
  next-bar-open fills, close-confirmed exits, 1 lot, the full Zerodha MCX futures
  charge stack (`engine/charges.py`) **plus slippage per side** (NG 0.04%, gold petal
  0.03%, crude 0.03%, silver 0.02%, GOLDM 0.01%); a 2× slippage stress is reported too.
* **In-sample (IS) = 2019–2023, out-of-sample (OOS) = 2024-01 → 2026-10.** Parameters
  were chosen on IS only; each candidate was looked at OOS once. Plateaus were preferred
  over peaks; config counts are reported per strategy.
* Component analysis first: before building strategies, each candidate component was
  measured on its own (decile tables of forward returns, event studies), so the
  strategies were built on components that showed a signal.
* Engine extensions added for this work (opt-in; existing strategies are unchanged and
  the full test suite passes): volume reaches strategies, `pyramiding` (`longAdd` /
  `shortAdd` columns, one order per leg), `session_flat` (MIS-style square-off at the
  last bar of the day), `slippage_pct`.

### The cost hurdle (decides almost everything)

Round-trip charges from `engine/charges.py` at 2026 prices, before slippage:

| Contract | Notional | Round-trip charges | bps |
|---|---|---|---|
| GOLDPETAL (1 g) | ₹13,000 | ₹11.4 | 8.8 |
| GOLDGUINEA (8 g) | ₹104,000 | ₹65 | 6.3 |
| GOLDM (100 g) | ₹13 lakh | ₹271 | 2.1 |
| NATGASMINI | ₹75,000 | ₹60 | 8.0 |
| CRUDEOILM | ₹60,000 | ₹53 | 8.8 |
| SILVERMIC | ₹1.5 lakh | ₹73 | 4.9 |

With slippage a round trip costs **≈ 14–15 bps** on the small contracts. A 15-minute
ATR is only 10–40 bps (gold ≈ 10). So an intraday idea needs a raw edge far larger
than most technical patterns have; the profitable designs hold for **days** or trade
**rarely**.

## 3. Component analysis — what carries information

(15m unless stated; forward returns in bps from the next bar's open; scripts in
`research/commodity/`.)

| Component | Finding |
|---|---|
| VWAP slope (vwap − vwap[10]) / ATR, alone | ±5 bps across deciles, no stable sign IS vs OOS — below cost |
| Distance from VWAP, RSI, 4/16-bar momentum, candle body, close location | same: noise-level alone |
| **RSI divergence against a sloped VWAP** | a bullish divergence while vslope < 0 was followed by **−4.8 bps (IS) / −10.2 bps (OOS)** over 8 bars: the divergence is a *failed reversal*; the VWAP trend resumes |
| Variance ratio / autocorrelation of 15m returns | ≈ 1.0 / ≈ 0 — close to a random walk in both NG and crude |
| Daily time-series momentum (sign of 5…120-day return) | no stable sign IS vs OOS on NG or crude |
| Time of day | NG/crude 15m moves 2–4× larger 17:00–23:30 IST (US session) than 09:00–16:00 |
| NG 16:00 IST "hour effect" | +9 bps in every period on the proxy, **not confirmed on real NYMEX bars** — dropped |
| EIA report bar follow-through (NG Thu, crude Wed) | none |
| **Gold MCX overnight gap** (close → next open) | **+5.3 bps/night in USD, t = 4.2, positive every year 2019–2026**, while gold's in-session MCX hours lost money in 2021, 2022, 2023 and 2026. Above its 100-hour EMA: +4.3 bps (IS) / +11.9 bps (OOS) per night |
| Crude MCX overnight gap | +11.6 bps/night, t = 2.5, not a roll artefact — but below cost on CRUDEOILM |
| **Shock days** (session return z ≥ 1.5–2 vs 60-day vol) | crude: up-shocks −126…−200 bps and down-shocks +51…+147 bps over the next 3 sessions, **same sign IS and OOS**; NG: up-spikes faded in both periods, down-spikes did not |
| Squeeze / compression (coil, BB-in-KC) | tight coils did **not** predict larger moves (volatility clustering) |
| Regime at entry (see §5) | trend tools lose money on entries taken when the TREND label is already on (late) |

Two look-ahead traps were found and removed during the work (a close-of-bar condition
used with an open-of-bar entry; the daily-FX overnight artefact). Results quoted here
are after both fixes.

## 4. The five strategies (+ one structural carry)

All six are registered in `backend/app/strategy/registry/` (assign them per instrument
in the platform like any other strategy). "Final" numbers below are each strategy's
**default parameters** on the corrected data, ₹ per 1 lot, net of charges + slippage
(`research/commodity/final_eval.py` → full matrix in §7).

### 4.1 `vwap_slope_divergence` — VWAP slope + RSI divergence (the owner's idea)

*Regime:* trending sessions. *Construction:* `vslope = (VWAP − VWAP[10]) / ATR`, RSI(14)
divergence detected on the current bar (no pivot lag), candle close-location,
pyramiding, ratchet stop.

Layer study (NATGASMINI / CRUDEOILM, 15m, session VWAP, flat at session end; IS → OOS net ₹):

| Layer | NG IS | NG OOS | Crude IS | Crude OOS |
|---|---|---|---|---|
| L0 bare: trade the sign of vslope | −121k | −81k | −129k | −109k |
| L1 + slope threshold 1.0 ATR | −59k | −60k | −89k | −62k |
| L2 trigger = **failed divergence** (divergence against the VWAP trend → enter WITH the trend) | −128k | −66k | −45k | −83k |
| L2r textbook reading (buy the bullish divergence) | −39k | −46k | −102k | −71k |
| L4 + candle close-location ≤ 0.35 (no rejection wick) | −53k | −26k | −2k | −23k |
| L6 + ratchet exit (1.5 ATR stop → Chandelier) | −14k | −17k | −3k | −15k |
| L7 + pyramiding (2 adds) | −34k | −20k | −4k | −20k |
| VWAP-pullback trigger (trend session, tag VWAP, close back) | 0 of 192 IS configs profitable | | | |

(Layer rows L0–L7 were run before the FX correction, which changes overnight results
only; all these variants are intraday and flat at the close.)

The intraday version does not clear costs on any layer. Moving to a **120-bar rolling
VWAP on 30m bars with overnight holds** (an IS grid of 192 configs) gives the final
default: **NG 30m IS +₹73k (PF 1.23) → OOS +₹18k (PF 1.10)**, but only +₹3k at 2×
slippage and a bootstrap P(OOS>0) of 0.69; crude and gold lose. Most of the NG IS
profit is 2022. **Verdict: not deployable.** Useful component findings: (a) RSI
divergence against a sloped VWAP is a *continuation* signal, not a reversal; (b) the
candle filter and the ratchet each cut losses substantially; (c) pyramiding never helped.

### 4.2 `adaptive_supertrend` — Adaptive SuperTrend (port of deepaksingh-fx/ibkr-forex-dynamic)

*Regime:* sustained trend. Faithful port (7 SuperTrend variants, rolling flip-to-flip
scoring, auto-selection, RSI/MACD filters, close-TSL) kept as `FAITHFUL_PARAMS`.

| Layer (NG 15m/30m) | IS | OOS |
|---|---|---|
| faithful port | −108k / +18k | −107k / −22k |
| classic ST(10,3) only | −54k / +178k | −36k / +14k |
| + auto method selection | worse in most cells | worse |
| + RSI/MACD + 1.5-ATR TSL | +26k / +26k | −217k / −56k |
| wider band (×5) + ADX ≥ 20 + volume gate (**default**) | +178k / +170k | −33k / −60k |

Auto-selection, the filters and the tight trailing stop all *hurt*. Final default on
corrected data: NG OOS −₹17k…−₹73k, crude ≈ 0 to −₹51k. Gold: OOS profit only in 2026.
Regime attribution: SuperTrend entries taken when the TREND label is already on lost
money on NG (IS −₹13k, OOS −₹38k) — by then the move is mature. **Verdict: no edge on
these markets after costs.**

### 4.3 `vol_squeeze_breakout` — volatility-compression breakout

*Regime:* squeeze → expansion. Self-derived "coil ratio": box width over the last ~30 h
divided by the expected range of those same clock slots (removes the 2–4× US-vs-Indian
hours vol difference). Entry on a close beyond a coiled box; exit on a close back
through the box midpoint.

Layers (60m, values before the FX fix): L0 break + opposite-break exit NG IS +129k / OOS
−59k; **L1 + midpoint failure exit** NG IS +198k / OOS +13k; close-location, drift
filter, US-session window, pyramiding, ratchet, session-flat all improved IS and
worsened OOS (classic overfit). Key component finding: **tight coils did not predict
larger moves** on these proxies. Final default on corrected data: NG OOS −₹3k…−₹30k,
crude −₹49k…−₹56k, gold ≈ +₹1k. **Verdict: no edge.** (The natural squeeze trade is a
long straddle — not testable on the underlying.)

### 4.4 `vwap_band_reversion` — swing reversion to a 10-day VWAP after a climax push  ✅ (NG)

*Regime:* the end of a violent one-way push (climax) inside a range. Fade a close
beyond the 10-session rolling VWAP ± 2.75σ, but only when the stretch was reached
impulsively (efficiency ratio over 20 bars ≥ 0.5); one extra lot at 3.5σ; exit back at
the VWAP; no stop (stops lost money in IS); holds ~3 sessions (up to weeks).

| Layer (30m) | NG IS | NG OOS | Crude IS | Crude OOS |
|---|---|---|---|---|
| L0 session VWAP ± 2σ, flat at day end | −263k | −133k | −185k | −125k |
| L2 + flat-VWAP gate | −62k | −44k | −47k | −21k |
| L4 anchor = 10-day rolling VWAP, hold overnight | +76k | +14k | +25k | −1k |
| L5c + climax-push filter | +118k | +23k | +39k | +2k |
| **L6 + scale-in at 3.5σ (default)** | **+135k** | **+39k** | +45k | +10k |

Final default on corrected data: **NATGASMINI IS +₹85k…+₹150k (PF 1.9–2.6) → OOS
+₹21k…+₹36k (PF 1.26–1.46) on 15m/30m/60m**, OOS positive in 2024, 2025 and 2026,
robust to 2× slippage, bootstrap P(OOS>0) 0.69–0.78. NG profit comes from fading
up-spikes (30m OOS: shorts +₹38.2k, longs −₹2.0k). (The layer table above was produced
by the research agent before the FX correction; the final row's numbers are on
corrected data.) Crude and gold lose OOS → **NG only**.
Caveats: ~10 trades/year; adverse excursions can be large (OOS max DD ₹43k on one lot).

### 4.5 `shock_reversal` / `spike_fade` — multi-session fade of a volatility-shock day  ✅ (crude, NG)

*Regime:* EXPANSION (a shock day) → reversion over the next sessions. One value per
completed session: z = session return / stdev of the previous 60 session returns; held
3 sessions, closed near the close. The layer study below used the original timing
(decide on the session's last bar, fill at the next open); the shipped default enters on
the next session's 09:30 bar instead, because the live engine cannot act on a signal
from the closing candle — see §6b.

IS grid (180 configs, 60m): NG **short side profitable in all 24 cells** (z 1.5–2.5 ×
hold 1–5 × both shock definitions); NG long side mostly lost. Crude positive for both
sides around z 1.5–2.0, hold 2–3.

| Layer (IS → OOS, 60m) | Result |
|---|---|
| crude, both sides, session z ≥ 2, hold 3 | IS +26k (PF 1.59) → OOS +8.9k (PF 1.25) |
| + fade only shocks AGAINST the 20-session trend (**`shock_reversal` default**) | IS +28k (PF 2.13, every IS year +) → **OOS +16.3k (PF 2.11)** |
| + fade only shocks WITH the trend | IS +11k — rejected |
| + pyramid on a 2nd shock | crude IS worse; NG IS better but **OOS −₹6k** — rejected |
| + 6-ATR catastrophic stop | ≈ no change — off |
| NG, short only, close-to-close z ≥ 1.5 (gap clipped ±1.5%), hold 3 (**`spike_fade` default**) | IS +167k (PF 2.69) → **OOS +13.0k (PF 1.17)** |
| `spike_fade` on **crude, never tuned on crude** | IS +22k (PF 1.53) → **OOS +33.7k (PF 2.42)**, positive in 7 of 8 years (2019 ≈ −₹0.5k) |

Final defaults (live-compatible `next_session` timing) on corrected data — all three
timeframes agree within a few %:

| Strategy × instrument | IS net / PF | OOS net / PF / trades | OOS max DD | 2× slippage OOS | P(OOS>0) |
|---|---|---|---|---|---|
| `shock_reversal` × CRUDEOILM | +₹25–27k / 1.9–2.0 | **+₹15–16k / 2.0–2.1 / 17** | ₹8.5k | +₹14–16k | 0.88–0.89 |
| `spike_fade` × NATGASMINI | +₹163–168k / 2.6–2.7 | **+₹14–17k / 1.19–1.24 / 43** | ₹41–43k | +₹11–15k | 0.64–0.67 |
| `spike_fade` × CRUDEOILM | +₹22k / 1.51–1.53 | **+₹32–33k / 2.3–2.4 / 30** | ₹16–18k | +₹31–32k | 0.90–0.92 |

Per year (₹, 60m, corrected data): `shock_reversal` crude 2019 +1.4k, 2020 +4.4k, 2021
+14.1k, 2022 +0.4k, 2023 +6.2k, 2024 +0.6k, 2025 −2.9k, 2026 +17.1k · `spike_fade` NG
2019 +2.0k, 2020 −0.5k, 2021 +33.3k, 2022 +130.1k, 2023 +3.5k, 2024 +0.5k, 2025 +36.2k,
2026 −19.5k · `spike_fade` crude 2019 −0.5k, 2020 +8.4k, 2021 +4.2k, 2022 +4.5k, 2023
+5.6k, 2024 +13.4k, 2025 +9.8k, 2026 +9.5k. (An earlier version of this report quoted
per-year figures from a run on the pre-FX-fix data and called `spike_fade` crude
"positive in all 8 years"; on the corrected data 2019 is slightly negative.)

Gold: both variants lose — gold shocks do not revert (no fade on gold).

### 4.6 `session_gap_carry` — own the hours MCX is shut (structural, gold)

*Regime:* any — a clock effect. Enter long two bars before the MCX close when price is
above its 100-hour EMA, exit at the next session's open. Built on the strongest single
component found (gold's overnight gap, t = 4.2, positive every year), but the edge per
night (≈ 3–5 bps IS) is smaller than GOLDPETAL's ~15 bps round trip:

| Contract (15m, default) | IS | OOS |
|---|---|---|
| GOLDPETAL | −₹3.2k (PF 0.52) | −₹1.8k |
| GOLDM (100 g, ~2 bps charges) | −₹12.8k (PF 0.97) | +₹275k (PF 1.28, P 0.94) |
| CRUDEOILM / NATGASMINI | lose | lose |

On GOLDM it is break-even before 2024 (−₹30k in each of 2021 and 2022) and very
profitable in the 2024–26 bull market — **regime-dependent, not deployable as is**.
Keep it as a research lead: the drift is real; the open question is a cheaper way to
hold it (e.g. carry only on nights where the drift historically concentrates).


### 4.7 `gold_month_turn` — own gold across the turn of the month only  ❌ not deployable (failed real-MCX check, §6e)

*Regime:* any — a calendar/flow effect. Found by a dedicated gold research pass (≈ 206
configs; components first). Long GOLDPETAL from one bar before the close of the
month's **last business day** to the **3rd session** of the new month (exit on the
09:30 bar, live-compatible); ~12% time in market, one trade a month, no short side.

| Component (daily, 2019-26) | IS | OOS |
|---|---|---|
| month-turn window, INR proxy | +63 bps / month (t 2.7, 62% win) | +77 bps (t 2.7, 65%) |
| same, pure USD | +47 | +67 |
| random same-length long windows | +14 | +33 |
| daily trend, oversold dip-buy, hour/day-of-week, month-end short | rejected (unstable or below cost) | |

| GOLDPETAL, 60m, 1 lot | IS (2019-23) | OOS (2024-26) |
|---|---|---|
| buy-and-hold | +₹2,730 (DD ₹1,097) | +₹7,787 (DD ₹4,658) |
| buy-and-hold × 12% exposure | +₹335 | +₹912 |
| **`gold_month_turn` default** | **+₹852, PF 1.71, 57 trades, DD ₹277** | **+₹1,528, PF 2.01, 29 trades, DD ₹1,033** |
| … minus futures carry (≈ 1.8 bps/calendar day) | +₹670 | +₹1,301 |
| GOLDGUINEA / GOLDM | +₹7.2k / +₹111k | +₹13.2k / +₹186k |

Positive every calendar year 2019–2026 (incl. flat 2021 and the 2026 drop), 15m/30m
agree, 2× slippage still positive, bootstrap P(>0) 0.93–0.98.

**Independent check on unseen data (2005–2018, USD daily, identical daily method):**
+16.6 bps per month-turn (t 1.3) vs +9.0 bps for random windows → excess **+7.5 bps**,
against +41 bps (2019–23) and +20 bps (2024–26). The effect is much weaker outside the
period it was found in (selection bias + a smaller true effect): on GOLDPETAL's ~15 bps
round trip the 2005–2018 version would have been about break-even. **Verdict: was a
low-conviction calendar overlay; it then lost on real MCX GOLDPETAL prints (§6e) →
not deployable.** Note: the gold proxy is spot — futures carry has been
subtracted above; trade the MCX contract that stays live through the month turn.

## 5. Regime → strategy map

`app/strategy/regime.py` labels each bar from OHLCV only — **TREND** (ADX ≥ 25 and
efficiency ratio ≥ 0.30), **EXPANSION** (ATR5/ATR50 ≥ 1.4), **SQUEEZE** (Bollinger width in
its lowest 20%), **CHOP** (ADX < 20 and ER < 0.20), else NEUTRAL — and
`research/commodity/regime_attrib.py` splits every strategy's trades by the label of
the signal bar. On NG 15m the bars split NEUTRAL 33%, TREND 27%, SQUEEZE 19%,
EXPANSION 11%, CHOP 10%.

What the attribution and the results say:

| Market state (technical) | What worked here | What did not |
|---|---|---|
| **Violent push / shock** — EXPANSION, or a TREND label reached by a multi-σ stretch | **fade it**: `spike_fade` (NG, crude), `shock_reversal` (crude), `vwap_band_reversion` (NG). Their winning entries sit in TREND/EXPANSION bars: they fade the climax, not the trend | — |
| **Sustained, orderly trend** (ADX ≥ 25, high ER, low z) | gold only, weakly (SuperTrend + ADX ≥ 25; gold overnight carry) | SuperTrend/VWAP-slope entries *after* the TREND label is on (late) lost on NG and crude |
| **Squeeze** | nothing on futures (needs bought options/straddles) | coil/BB-KC breakouts |
| **Chop / balanced (CHOP, NEUTRAL)** | **stand aside** | session-VWAP fades lose even before costs |

How to use it (no cross-strategy switching): assign `spike_fade` to NATGASMINI and
CRUDEOILM (or `shock_reversal` to crude) and `vwap_band_reversion` to NATGASMINI —
these trade rarely (~10–15 trades a year each) and only after a shock/climax, so they
are flat in chop by construction. Use `latest_regime(df)` as a dashboard read of what
an instrument has been doing (share of each regime over the last 250 bars) when
deciding assignments — e.g. a market spending most of its time in TREND is a poor
home for the fade strategies.


## 6. Verdict

**Requirement met — profitable after charges on crude and natural gas, in-sample AND
out-of-sample:**

1. **`spike_fade` (Energy Up-Spike Fade)** — NATGASMINI OOS +₹14–17k (PF 1.19–1.24);
   on CRUDEOILM (never tuned there) OOS +₹32–33k (PF 2.3–2.4), 7 of 8 years positive.
2. **`shock_reversal`** — CRUDEOILM OOS +₹15–16k (PF 2.0–2.1), IS +₹25–27k (PF 1.9–2.0).
3. **`vwap_band_reversion`** — NATGASMINI OOS +₹21k…+₹36k (PF 1.26–1.46); 98% of its
   parameter neighbourhood is profitable in both periods (§6b).

All three keep the same sign on real NYMEX bars (§6b). A pre-declared book of 1 lot
each (`shock_reversal` crude + `spike_fade` NG + `vwap_band_reversion` NG, live-
compatible timing) was **positive in every calendar year 2019–2026**: IS +₹345k (daily
Sharpe 1.46, max DD ₹39k), OOS +₹68k (Sharpe 0.57, max DD ₹73k); monthly correlation of
the crude leg with the NG legs ≈ 0. (Swapping the crude leg to `spike_fade` after seeing
its result gives OOS +₹86k, Sharpe 0.69 — post-hoc, so not the headline.)

**On the bot's options path** (§6c) the three shock-family legs stay profitable IS and
OOS once each strategy carries its own option-exit policy (the global −35%/+60% exits
destroyed them): spike_fade NG OOS +₹13k, spike_fade crude +₹34k, shock_reversal crude
+₹11k, each with ≈ ₹2–4k premium per lot and a worst OOS drawdown of ₹5.5–6.9k.
`vwap_band_reversion` works on ~30-day options (OOS +₹10.7k) — it declares that tenor.

**Gold: no deployable strategy.** `gold_month_turn` (§4.7) passed the proxy test
(2019–2026, after charges, slippage and futures carry) but its edge was only ~7.5 bps a
month above random timing on unseen 2005–2018 data, and it LOST on real MCX GOLDPETAL
prints Dec-2025 → Oct-2026 (§6e). Not deployable. The gold MCX overnight drift is real but too small for GOLDPETAL's costs (and
partly offset by futures carry).

**Silver: no strategy** (§6d) — the fades lose on silver too; the trend tools' gains are the
2026 blow-off alone.

**Honest caveats.**
* Small samples: 10–15 trades/year per strategy; OOS P(total > 0) by bootstrap is
  0.6–0.9, not 0.99. NG's IS profit is concentrated in 2022.
* Proxy data (international contracts × USDINR). **Before any live use: re-run these
  strategies on real Kite MCX candles in the Backtests view, then paper-trade.**
* The live engine trades *options* on signals and does not implement the backtest-only
  declarations (`pyramiding`, `session_flat`); the multi-session hold of these
  strategies maps to holding a futures position (or a longer-dated option).
* One lot of NATGASMINI moved ₹40–75k against the OOS book at worst — size it to the
  account, not to the average trade.

**Recommended next steps.** (1) Run the Backtests sweep for `spike_fade`,
`shock_reversal`, `vwap_band_reversion` on Kite MCX 15m/30m data (200 days) and compare
to §7. (2) Paper-trade `spike_fade` on NATGASMINI + CRUDEOILM. (3) Gold: test the
overnight carry on GOLDM with real MCX prints, and research the cheaper "hold the drift"
variants. (4) Re-run `final_eval.py` quarterly.

## 6b. Robustness and live-readiness checks (added 2026-10-08)

### Independent data: real NYMEX bars (Yahoo Finance, 60m, 2024-05 → 2026-10)

The same strategies, unchanged, on a second data source — real exchange prints and
real exchange volume (`research/commodity/build_yahoo.py`, `crosscheck_yahoo.py`).
Yahoo's continuous contract switches at ~07:00 UTC (12:30 IST, *inside* the MCX
session) the day after expiry, so rolls are found from the NYMEX expiry calendar and
ratio back-adjusted; compare PF / return per trade (back-adjustment rescales older
rupee levels a little).

| Strategy × instrument | Dukascopy, same window | Yahoo NYMEX |
|---|---|---|
| `spike_fade` × NG | +₹29.5k, PF 1.56, 35 trades | **+₹43.1k, PF 5.9**, 19 trades, every year + |
| `spike_fade` × crude | +₹34.7k, PF 2.53 | **+₹54.7k, PF 7.4**, every year + |
| `shock_reversal` × crude | +₹18.8k, PF 2.53 | **+₹8.7k, PF 1.52** |
| `vwap_band_reversion` × NG | +₹39.6k, PF 1.68 | **+₹78.4k, PF 3.6**, every year + |
| `vwap_slope_divergence` / `adaptive_supertrend` / `trend_impulse_v3` × NG | all lose | all lose |

Same ranking on both sources. Yahoo trade counts are small, so its high PFs are not
precise estimates — the point is that the sign and ordering hold on real exchange data.

### Parameter neighbourhoods (Dukascopy, 2019-2026; `research/commodity/neighbourhood.py`)

Every combination around each default (z threshold, hold, volatility window, gap clip
/ trend window; for band reversion: anchor days, band k, push ER, add k):

| Strategy | Neighbours | IS > 0 | OOS > 0 | both > 0 | note |
|---|---|---|---|---|---|
| `vwap_band_reversion` × NG 30m | 81 | 98% | **100%** | **98%** | broad plateau |
| `spike_fade` × NG 60m | 144 | **100%** | 67% | 67% | median OOS +₹9k |
| `shock_reversal` × crude 60m | 144 | 57% | 94% | 53% | hold = 3 is the IS plateau; 4–5 lose IS |
| `spike_fade` × crude 60m | 144 | 51% | 69% | 41% | z 1.5–1.75 and hold 3 good; z 1.25 loses |

The NG strategies sit on broad plateaus. The crude results are real but parameter-
sensitive (mainly the hold length) — treat crude as the weaker leg.

### Live-engine compatibility — two fixes

1. **Entry timing.** The live engine drops a signal it sees more than 5 minutes after
   its candle closed, never opens outside the session, and opens nothing before
   09:30. The shock strategies originally decided on the session's LAST bar (which
   closes at the 23:30/23:55 exchange close) and filled at the next open — a timing
   the live engine can never execute. New default `decide_at="next_session"`: decide
   on the completed shock session, enter on the next session's first bar ending at or
   after 09:30 IST (`entry_minute`). It keeps the edge (15m, IS → OOS):
   `shock_reversal` crude +₹25.1k → +₹16.4k (PF 2.08); `spike_fade` NG +₹164k →
   +₹16.4k (PF 1.23); `spike_fade` crude +₹21.9k → +₹31.8k (PF 2.26). (Deciding one
   bar before the close instead — `penultimate` — hurt crude: the shorts then carry
   crude's positive overnight drift.)
2. **History length.** The runner fetched 30 calendar days of candles (≈ 21 MCX
   sessions); the shock strategies need ≥ 30 sessions for their volatility norm, so
   they could never have signalled live. A strategy can now declare
   `min_history_days` (shock strategies: 120); `runner.history_days_for()` fetches the
   larger of that and `history_days`, capped at Kite's per-request maximum for the
   interval (15m: 200 days, 5m: 100).

Still to keep in mind for live use: the engine trades **options** on these signals,
with its own −35%/+60% premium stop/target, overnight-holding rules and expiry
guards; the backtests here trade the underlying. Paper-trade first.

## 6c. The options path — how the bot actually trades these signals (added 2026-10-08)

The live bot does not trade the futures: on each signal it BUYS an ATM CE (long) or PE
(short) and manages the premium with a global −35% stop, +60% target and a ratcheting
trail. Re-run through the platform's synthetic-premium backtest
(`app/backtest/premium.py`: Black-Scholes on realised vol × 1.15, option charges,
half-spread each side, ~14-day options; trades held across a futures roll dropped —
`research/commodity/premium_eval.py`, `premium_grid.py`, `premium_final.py`):

**With the bot's global exits the edge disappears** — 87–98% of trades hit the −35%
premium stop on noise before the multi-session reversion arrives (2% spread):

| Strategy | global −35%/+60%/trail: IS → OOS | strategy exits only: IS → OOS |
|---|---|---|
| spike_fade × NG | +₹12.6k → **−₹3.5k** | +₹101.5k → +₹16.0k |
| spike_fade × crude | −₹5.9k → +₹7.9k | +₹11.0k → +₹35.3k |
| shock_reversal × crude | −₹1.7k → −₹0.6k | +₹15.9k → +₹10.5k |
| vwap_band_reversion × NG | −₹6.4k → +₹3.3k | +₹44.2k → +₹5.3k |

**Platform change:** a strategy can now declare `option_exits` (premium stop, target or
`None`, trail on/off). The live entry applies it (`runner.option_entry_params`; a `None`
target sets the position's existing `no_take_profit` flag; `trail_allowed` skips the
percent trail for that position) and the premium backtest uses it by default. Chosen
on IS only (stop × option-tenor grid; every stop from −50% to none was profitable for
the shock family): shock family −65% disaster stop, no target, no trail;
`vwap_band_reversion` and `gold_month_turn` −95%, no target, no trail.

Results with the shipped policies (options path):

| Strategy (options) | IS | OOS | OOS @ 6% spread | OOS max DD | premium / lot |
|---|---|---|---|---|---|
| **spike_fade × NG 15m** | +₹110k (PF 3.1) | **+₹13.1k (PF 1.45)** | +₹5.7k | ₹6.9k | ~₹4.2k |
| **spike_fade × crude 15m** | +₹12.2k (PF 1.45) | **+₹33.9k (PF 3.05)** | +₹31.7k | ₹5.5k | ~₹2.2k |
| **shock_reversal × crude 15m** | +₹16.4k (PF 1.96) | **+₹11.1k (PF 2.11)** | +₹8.8k | ₹5.8k | ~₹2.3k |
| vwap_band_reversion × NG 30m, ~14-day options | +₹43.4k (PF 1.79) | +₹4.4k (PF 1.15) | +₹0.4k | ₹12.6k | ~₹3.9k |
| **vwap_band_reversion × NG 30m, ~30-day options** (`option_tenor_days = 30`) | +₹53.2k (PF 2.24) | **+₹10.7k (PF 1.43)** | +₹4.8k | ₹9.7k | ~₹5.7k |
| gold_month_turn × GOLDM 60m | +₹29.7k (PF 1.34) | +₹34.0k (PF 1.21) | +₹6.2k | ₹112.7k | ~₹12.5k |

Reading it: the **shock family on options** is the best fit for a ₹50k account — ~₹2–4k
of premium per lot, worst OOS drawdown ₹5.5–6.9k (vs ₹17–41k for one futures lot), and
it survives a 6% spread. `vwap_band_reversion` holds for days to weeks, so it needs a
longer-dated option: a strategy can now declare `option_tenor_days` (live: the provider
picks the earliest expiry at least that far out; premium backtest: the default option
life). At ~30 days (the in-sample best of 14/21/30) it is usable on options too (OOS
+₹10.7k, PF 1.43; 2019, 2023 and 2026 slightly negative). `gold_month_turn` failed its real-MCX check and is not deployable (§6e).

Not modelled: MCX option liquidity (check the bid-ask on NATGASMINI/CRUDEOILM options in
the Options Calc view before relying on the 2–6% spread assumption), whether MCX lists
options on each mini contract (the live picker uses whatever the Kite instrument dump
holds — verify), and the bot's overnight-holding rules (positions > 10% of capital need a
reinforcement to carry; ~₹2–4k of premium on ₹50k is within the 10% auto-hold limit).

## 6d. Silver (added 2026-10-08)

The Dukascopy silver download stayed rate-limited, so silver was tested on **Yahoo COMEX
SI=F hourly bars** (2024-05 → 2026-10; contract rolls found from the COMEX active-month
calendar and ratio-adjusted; ₹/kg = $/oz × USDINR × 32.15 × 1.06). No strategy was ever
tuned on silver, so all of this is out-of-sample (`research/commodity/silver_check.py`).
Buy-and-hold 1 kg: +₹112.6k (+132%), max drawdown ₹192k.

| Strategy (defaults, 60m) | futures | options (4% spread) |
|---|---|---|
| spike_fade | −₹15.6k (PF 0.65) | −₹9.6k |
| shock_reversal | −₹17.5k (PF 0.15) | −₹11.1k |
| vwap_band_reversion | −₹81.7k (PF 0.39) | −₹36.3k |
| gold_month_turn | +₹5.1k (PF 1.08) | −₹24.0k |
| trend_impulse_v3 / vol_squeeze_breakout / adaptive_supertrend / vwap_slope_divergence | +₹55k … +₹176k, but lose in 2024 and 2025 — nearly all from the 2026 blow-off and crash | all lose |

**Verdict: no silver strategy.** The fade family fails on silver as it does on gold —
precious-metal spikes do not revert like energy spikes. The trend tools' silver profit is
one extreme year (2026), not an edge, and they lose on the options path. More history (the
Dukascopy 2019–2026 set) would be needed before trusting any silver result.

## 6e. Validation on REAL MCX data (added 2026-10-08)

Two public, login-free sources made a real-MCX check possible from this environment:

**1. Kite's MCX instrument list** (`https://api.kite.trade/instruments/MCX`, the list the
live option picker reads) — which contracts actually have options:

| Contract | Options listed | Strike step | Option expiry vs futures |
|---|---|---|---|
| NATGASMINI | yes (524 contracts) | ₹5 | monthly, ~4 days before the futures |
| CRUDEOILM | yes (1,100) | ₹50 | monthly, ~4 days before the futures |
| GOLDM | yes (706) | ₹500 per 10 g | monthly |
| GOLDPETAL, GOLDGUINEA, SILVERMIC | **no** | — | futures only |

The list reports `lot_size = 1` for every MCX contract. **This exposed a platform bug:**
the Backtests universe (`backtest/universe._mcx_commodities`) and the "add instrument"
catalog took that 1 as the lot, so every Kite-backed MCX backtest — and any MCX
instrument added from the UI — would have computed P&L for one unit instead of one lot
(250× too small for NATGASMINI, 10× for CRUDEOILM/GOLDM). Fixed with a contract
multiplier table (`core/instruments.MCX_UNITS_PER_LOT`, `mcx_lot_size`); stored MCX rows
with lot 1 are repaired on load. (The live option picker already patched this itself.)

**2. Real MCX futures prints** — Moneycontrol's public chart API serves 15-minute bars per
MCX contract (`research/commodity/fetch_mcx_moneycontrol.py`: contracts found from the
MCX expiry rules, bars re-stamped from END to START time, session-filtered, stitched
front-month with the roll measured as the contract spread on the last common bar). Only
recent contracts are served, so the windows are short: NATGASMINI 2025-12-18 → 2026-10-08,
CRUDEOILM 2026-03-04 → 2026-10-08, GOLDPETAL 2025-12-01 → 2026-10-08. No volume field.

Results on real MCX prints (defaults, 1 lot, full charges + slippage; options = synthetic
premium at a 4% spread; `real_mcx_check.py`, `real_mcx_gold.py`):

| Strategy | Real MCX futures | Real MCX options |
|---|---|---|
| **spike_fade × NATGASMINI** | **+₹13.3k** (5 trades) | **+₹6.9k** |
| **spike_fade × CRUDEOILM** | **+₹13.3k** (6 trades, PF 4.8) | **+₹7.0k** |
| **shock_reversal × CRUDEOILM** | **+₹3.2k** (1 trade) | **+₹1.0k** |
| **vwap_band_reversion × NATGASMINI** | **+₹32.1k** (9 trades, PF 5.2) | **+₹4.2k** |
| vwap_slope_divergence × NG | −₹27.6k | −₹20.1k |
| adaptive_supertrend × NG | −₹57.1k | −₹20.0k |
| vol_squeeze_breakout × NG | −₹23.5k | −₹7.7k |
| trend_impulse_v3 × NG / crude | −₹30.2k / −₹5.9k | −₹69.7k / −₹51.1k |
| gold_month_turn × GOLDPETAL | −₹0.5k (9 trades, PF 0.66) | GOLDM: −₹75.0k |

**Every strategy that passed the proxy research made money on real MCX prints, and every
one that failed lost** — the verdicts carry over to the real exchange. The samples are
tiny (1–9 trades per cell over 7–10 months), so this confirms direction, not the size of
the edge. `gold_month_turn` failed its real-data window (Jan-2026 crash month) and is
downgraded to not deployable. Real MCX gold traded ~9% above the proxy level (MCX premium
over landed gold larger than the 6% assumed) — a scaling difference, not a sign change.

**3. Real MCX option bid-ask — not obtainable without a login.** Moneycontrol serves
MCX futures bars only: its option symbols (`NATGASMINI_2026-10-23_MCX_CE_315`) are
rejected and its `commodityoption` feed is "invalid" for MCX. Kite's quote API needs the
daily access token. So, instead of the real spread, the research gives the **break-even
spread** — the round-trip bid-ask (as % of the option mid) at which each strategy's OOS
options P&L reaches zero (`research/commodity/spread_breakeven.py`; each strategy's shipped
`option_exits` / `option_tenor_days`; OOS 2024-01 → 2026-10, Dukascopy proxy):

| Strategy (options) | 2% | 4% | 6% | 8% | 10% | 15% | 20% | break-even |
|---|---|---|---|---|---|---|---|---|
| spike_fade × NATGASMINI 15m | +13.1k | +9.4k | +5.7k | +1.9k | −1.8k | −11.2k | −21.7k | **≈ 9%** |
| spike_fade × CRUDEOILM 15m | +33.9k | +31.9k | +31.7k | +29.7k | +27.7k | +22.6k | +17.5k | > 20% |
| shock_reversal × CRUDEOILM 15m | +11.1k | +10.0k | +8.8k | +7.6k | +6.4k | +3.5k | +0.5k | ≈ 20% |
| vwap_band_reversion × NATGASMINI 30m | +10.7k | +7.8k | +4.8k | +1.9k | −1.0k | −8.3k | −15.7k | **≈ 9%** |

How to use it: in the Options Calc view, read the ATM CE/PE bid and ask of the contract
the bot would pick: its spread % is (ask − bid) / LTP, the same `spread_pct` the picker
uses. The crude strategies stay profitable
with almost any realistic spread. The two NATGASMINI strategies need the spread **below
~5%** to keep at least half of their edge, and they **lose above ~9%** — if NATGASMINI
options quote wider than that, trade those two signals on the futures instead, or not at
all. (The live picker already rejects any contract whose spread is above `max_spread_pct`,
3% by default, so on a wide day the bot skips the trade instead of paying the spread. If
the real MCX spreads sit above 3% most of the time, the bot will rarely trade these
signals at all — raise `max_spread_pct` in Settings only up to the break-even above.)

## 6f. Paper-trading replay — the LIVE engine on real MCX bars (added 2026-10-08)

Real-time paper trading needs a Kite login and weeks of market hours. The closest
step possible here is a **replay**: the real `EngineRunner` (PaperBroker, armed,
₹50k, one instrument per run) driven over the real MCX 15m prints of §6e by
`app/providers/replay.ReplayProvider` (`backend/scripts/replay_mcx.py`). The engine
takes its live path end to end: candle fetch with `min_history_days`, the stale-signal
and 09:30 entry-window guards, the expiry and weekday guards, the option chain with
`option_tenor_days`, the picker, per-strategy `option_exits`, mark-to-market stops,
the overnight square-off rules, and the capital ledger. Option prices are synthetic
(Black-Scholes on trailing realised vol ×1.15, 2% spread); option expiry = futures
expiry − 2 business days; a held option is priced off its own futures month.

**Signals:** the live engine sees the same entry signals as the backtest — spike_fade
NG 6/6, spike_fade crude 6/6, shock_reversal 1/1 (vwap_band_reversion 119/125 entry
bars; the 6 misses are at the very start of the data, short of its 580-bar anchor).
Each is seen ~1 minute after its candle closes and fills at the next bar's open, as
in the backtest. **All four ledgers reconciled to the paisa.**

**Three live-engine bugs found and fixed** (tests in `tests/test_mcx_replay_fixes.py`):
1. `core/market_hours` closed MCX at 23:30 all year. MCX closes at 23:55 while New
   York is on standard time (Nov → Mar), so in winter the engine stopped scanning
   25 minutes early: it never saw the last two 15m bars (the exit bar of
   spike_fade/shock_reversal) and squared off overnight positions early. Now
   `session_window()` follows the US DST rule, the same as `ta.mcx_close_minute`.
2. The live candle frame (`runner._to_df`) dropped `volume`, so VWAP strategies ran
   live on equal weights while both backtest paths used volume. Now included.
3. The entry signal "reinforced" its own position: the latest completed candle stays
   the same for a whole interval, so the signal that opened the trade was re-read as
   a fresh same-direction signal on every loop until the next candle, and a +10%
   premium move then locked the stop above entry. Now only a candle completed after
   the fill can reinforce (`_fresh_since_fill`).

Also changed: `shock_reversal` / `spike_fade` declare `option_tenor_days = 14` (the
option life the premium backtest already assumed). Without it the live bot SKIPPED
every signal in the last ~3 days of an option cycle (`entry_min_days_to_expiry`)
instead of using the next expiry.

**Results with the platform's default risk settings** (real MCX window, 1 lot, 2%
spread; the backtest column is `run_premium` on the same bars):

| Cell | Live engine, default settings | Live engine, settings below | Backtest |
|---|---|---|---|
| spike_fade × NATGASMINI | 5 trades, +₹5.1k | 6 trades, +₹8.2k | 6 trades, +₹7.3k |
| spike_fade × CRUDEOILM | 4 trades, +₹4.9k | 6 trades, +₹8.6k | 6 trades, +₹7.5k |
| shock_reversal × CRUDEOILM | 1 trade, −₹0.1k | 1 trade, +₹1.1k | 1 trade, +₹1.2k |
| vwap_band_reversion × NATGASMINI | 10 trades, +₹2.0k | 8 trades, +₹4.4k | 6 trades, +₹4.4k |

With the default settings the strategies stay profitable but lose ~30–100% of the
edge, because three global risk settings (owner policy — NOT changed) cut them:

1. **`overnight_auto_pct = 0.10`** — an option above 10% of capital without a
   reinforcement is squared off at the first close. A 14-day crude ATM option costs
   ₹6–9k and a 30-day NG option ₹5–7k (> ₹5k), so most 3-session fades were closed
   on day 1 (`OVERNIGHT_SQUAREOFF`). These strategies are multi-session by design.
2. **`intraday_block_weekday = 1`** — no new entries on Tuesday (meant for NIFTY
   expiry) also blocks MCX. A shock on a Monday always enters on a Tuesday, so it is
   always lost (3 of 12 spike_fade signals here).
3. **`max_holding_days = 5`** cut vwap_band_reversion's longer holds. It counted
   CALENDAR days while `core/config.py` documents trading days; fixed — the runner
   now counts weekdays held (`np.busday_count`), so a weekend no longer uses up two
   days of the cap (test in `tests/test_overnight_multiday.py`).

"Settings below" = `overnight_auto_pct 0.25`, `intraday_block_weekday −1`,
`max_holding_days 30` — then the live engine tracks the backtest closely (the extra
vwap trades are the two roll-spanning trades the backtest drops). These are global
settings (Settings view), so they also apply to every other instrument: decide them
as a risk-policy choice, or run these strategies in a separate paper instance.

Not covered by the replay: the NIFTY gap guard (no NIFTY prints; on Kite it can also
block MCX entries); `KiteProvider` quotes the near-month future as the chain's spot
even for a later-month chain, so a 30-day-tenor pick uses the near-month price
(the replay copies this behaviour).

## 7. Full evaluation matrix

`research/commodity/final_eval.py` → `results/final_eval.json` (default params incl. the
live-compatible shock timing, corrected data). Columns: IS net ₹ (PF) | OOS net ₹ (PF) /
trades / max DD ₹ | OOS at 2× slippage | bootstrap P(OOS > 0).

| Strategy | Instrument | tf | IS | OOS | OOS 2× slip | P(OOS>0) |
|---|---|---|---|---|---|---|
| vwap_slope_divergence | NATGASMINI | 15m | -20.7k (0.96) | -71.2k (0.756) / 556 / 92.3k | -101.3k | 0.015 |
| vwap_slope_divergence | NATGASMINI | 30m | +73.0k (1.232) | +18.1k (1.101) / 281 / 37.2k | +2.9k | 0.691 |
| vwap_slope_divergence | NATGASMINI | 60m | -10.6k (0.959) | -35.1k (0.787) / 153 / 36.9k | -43.1k | 0.198 |
| vwap_slope_divergence | CRUDEOILM | 15m | -92.1k (0.692) | -20.2k (0.892) / 561 / 55.9k | -42.0k | 0.247 |
| vwap_slope_divergence | CRUDEOILM | 30m | -45.4k (0.767) | -53.1k (0.675) / 288 / 54.5k | -64.3k | 0.095 |
| vwap_slope_divergence | CRUDEOILM | 60m | -44.9k (0.675) | -28.5k (0.769) / 143 / 42.7k | -34.2k | 0.234 |
| vwap_slope_divergence | GOLDPETAL | 15m | -4.5k (0.569) | -3.4k (0.801) / 526 / 4.3k | -6.6k | 0.099 |
| vwap_slope_divergence | GOLDPETAL | 30m | -2.0k (0.704) | -0.6k (0.938) / 265 / 2.5k | -2.3k | 0.382 |
| vwap_slope_divergence | GOLDPETAL | 60m | -1.1k (0.765) | -0.8k (0.886) / 128 / 2.4k | -1.6k | 0.322 |
| adaptive_supertrend | NATGASMINI | 15m | +117.4k (1.215) | -73.0k (0.786) / 342 / 86.7k | -91.0k | 0.054 |
| adaptive_supertrend | NATGASMINI | 30m | +189.9k (1.633) | -24.7k (0.895) / 176 / 49.1k | -33.9k | 0.305 |
| adaptive_supertrend | NATGASMINI | 60m | +124.8k (1.62) | -16.7k (0.882) / 72 / 57.0k | -20.5k | 0.36 |
| adaptive_supertrend | CRUDEOILM | 15m | -8.5k (0.972) | -51.2k (0.769) / 308 / 60.4k | -63.3k | 0.098 |
| adaptive_supertrend | CRUDEOILM | 30m | -68.3k (0.704) | +0.4k (1.003) / 144 / 33.2k | -5.1k | 0.468 |
| adaptive_supertrend | CRUDEOILM | 60m | -30.6k (0.77) | -3.6k (0.951) / 56 / 26.3k | -5.7k | 0.451 |
| adaptive_supertrend | GOLDPETAL | 15m | -0.6k (0.939) | -4.1k (0.707) / 245 / 4.7k | -5.6k | 0.029 |
| adaptive_supertrend | GOLDPETAL | 30m | -0.9k (0.867) | +2.5k (1.272) / 116 / 1.7k | +1.8k | 0.791 |
| adaptive_supertrend | GOLDPETAL | 60m | -0.4k (0.924) | +0.9k (1.132) / 64 / 2.5k | +0.5k | 0.615 |
| adaptive_supertrend | GOLDM | 15m | +180.7k (1.223) | -150.1k (0.878) / 245 / 288.7k | -199.2k | 0.25 |
| adaptive_supertrend | GOLDM | 30m | +22.6k (1.036) | +378.0k (1.445) / 116 / 135.7k | +354.6k | 0.889 |
| adaptive_supertrend | GOLDM | 60m | +26.9k (1.06) | +154.9k (1.249) / 64 / 237.4k | +142.2k | 0.705 |
| vol_squeeze_breakout | NATGASMINI | 15m | +194.6k (2.056) | -9.2k (0.911) / 74 / 55.0k | -13.1k | 0.362 |
| vol_squeeze_breakout | NATGASMINI | 30m | +191.5k (2.185) | -3.1k (0.97) / 72 / 57.8k | -6.9k | 0.452 |
| vol_squeeze_breakout | NATGASMINI | 60m | +207.7k (2.368) | -30.5k (0.751) / 74 / 70.0k | -34.3k | 0.195 |
| vol_squeeze_breakout | CRUDEOILM | 15m | -3.8k (0.965) | -53.4k (0.438) / 104 / 62.3k | -57.3k | 0.009 |
| vol_squeeze_breakout | CRUDEOILM | 30m | +6.5k (1.062) | -56.4k (0.436) / 102 / 65.0k | -60.2k | 0.004 |
| vol_squeeze_breakout | CRUDEOILM | 60m | -3.4k (0.968) | -48.5k (0.473) / 93 / 58.9k | -52.1k | 0.009 |
| vol_squeeze_breakout | GOLDPETAL | 15m | -1.1k (0.736) | +1.1k (1.159) / 79 / 2.0k | +0.6k | 0.617 |
| vol_squeeze_breakout | GOLDPETAL | 30m | -1.8k (0.595) | +1.3k (1.227) / 70 / 2.0k | +0.9k | 0.663 |
| vol_squeeze_breakout | GOLDPETAL | 60m | -2.5k (0.463) | +0.8k (1.128) / 67 / 1.7k | +0.4k | 0.571 |
| vwap_band_reversion | NATGASMINI | 15m | +101.1k (1.911) | +30.5k (1.341) / 33 / 39.9k | +28.2k | 0.744 |
| vwap_band_reversion | NATGASMINI | 30m | +150.2k (2.631) | +36.1k (1.461) / 30 / 43.2k | +34.0k | 0.782 |
| vwap_band_reversion | NATGASMINI | 60m | +84.6k (1.865) | +21.3k (1.262) / 26 / 47.8k | +19.5k | 0.687 |
| vwap_band_reversion | CRUDEOILM | 15m | +39.5k (1.553) | -29.5k (0.639) / 32 / 49.7k | -31.2k | 0.285 |
| vwap_band_reversion | CRUDEOILM | 30m | +46.1k (1.733) | -8.3k (0.892) / 32 / 40.0k | -10.1k | 0.48 |
| vwap_band_reversion | CRUDEOILM | 60m | +72.7k (2.58) | -31.4k (0.589) / 24 / 47.7k | -32.7k | 0.242 |
| vwap_band_reversion | GOLDPETAL | 15m | +0.8k (1.236) | -5.0k (0.405) / 34 / 6.1k | -5.2k | 0.048 |
| vwap_band_reversion | GOLDPETAL | 30m | +0.8k (1.273) | -7.8k (0.211) / 29 / 8.3k | -8.1k | 0.004 |
| vwap_band_reversion | GOLDPETAL | 60m | +1.4k (1.546) | -6.0k (0.287) / 30 / 6.2k | -6.2k | 0.006 |
| shock_reversal | NATGASMINI | 15m | -61.8k (0.287) | -33.3k (0.402) / 14 / 43.9k | -34.1k | 0.165 |
| shock_reversal | NATGASMINI | 30m | -56.2k (0.295) | -34.8k (0.386) / 14 / 45.1k | -35.6k | 0.159 |
| shock_reversal | NATGASMINI | 60m | -54.4k (0.299) | -37.6k (0.34) / 14 / 47.8k | -38.5k | 0.121 |
| shock_reversal | CRUDEOILM | 15m | +25.1k (1.883) | +16.4k (2.084) / 17 / 8.5k | +15.8k | 0.888 |
| shock_reversal | CRUDEOILM | 30m | +25.2k (1.891) | +15.6k (2.039) / 17 / 8.5k | +14.9k | 0.881 |
| shock_reversal | CRUDEOILM | 60m | +26.5k (2.018) | +14.8k (2.005) / 17 / 8.5k | +14.2k | 0.877 |
| shock_reversal | GOLDPETAL | 15m | -0.5k (0.626) | -1.7k (0.493) / 19 / 2.3k | -1.8k | 0.14 |
| shock_reversal | GOLDPETAL | 30m | -0.5k (0.642) | -1.7k (0.481) / 19 / 2.4k | -1.8k | 0.134 |
| shock_reversal | GOLDPETAL | 60m | -0.5k (0.635) | -1.7k (0.484) / 19 / 2.3k | -1.8k | 0.133 |
| shock_reversal | GOLDM | 15m | -35.5k (0.719) | -146.0k (0.538) / 19 / 218.6k | -149.9k | 0.166 |
| shock_reversal | GOLDM | 30m | -32.8k (0.737) | -150.2k (0.525) / 19 / 222.4k | -154.1k | 0.162 |
| shock_reversal | GOLDM | 60m | -34.9k (0.727) | -148.4k (0.528) / 19 / 217.7k | -152.3k | 0.163 |
| spike_fade | NATGASMINI | 15m | +164.4k (2.631) | +16.4k (1.226) / 43 / 41.3k | +14.0k | 0.661 |
| spike_fade | NATGASMINI | 30m | +163.0k (2.604) | +13.6k (1.186) / 43 / 43.0k | +11.2k | 0.64 |
| spike_fade | NATGASMINI | 60m | +168.4k (2.667) | +17.2k (1.237) / 43 / 41.6k | +14.8k | 0.665 |
| spike_fade | CRUDEOILM | 15m | +21.9k (1.507) | +31.8k (2.264) / 30 / 17.6k | +30.6k | 0.899 |
| spike_fade | CRUDEOILM | 30m | +21.6k (1.507) | +33.4k (2.442) / 30 / 16.2k | +32.1k | 0.916 |
| spike_fade | CRUDEOILM | 60m | +22.1k (1.528) | +32.7k (2.374) / 30 / 16.0k | +31.4k | 0.91 |
| spike_fade | GOLDPETAL | 15m | -0.7k (0.732) | -1.3k (0.792) / 42 / 3.4k | -1.6k | 0.339 |
| spike_fade | GOLDPETAL | 30m | -0.7k (0.735) | -1.4k (0.774) / 42 / 3.4k | -1.7k | 0.321 |
| spike_fade | GOLDPETAL | 60m | -0.8k (0.706) | -1.5k (0.759) / 42 / 3.5k | -1.8k | 0.313 |
| session_gap_carry | NATGASMINI | 15m | -51.0k (0.859) | -85.0k (0.633) / 354 / 87.3k | -104.5k | 0.004 |
| session_gap_carry | NATGASMINI | 30m | -74.8k (0.82) | -75.9k (0.672) / 357 / 78.7k | -95.7k | 0.015 |
| session_gap_carry | NATGASMINI | 60m | -40.7k (0.906) | -67.4k (0.707) / 349 / 74.9k | -86.7k | 0.023 |
| session_gap_carry | CRUDEOILM | 15m | -42.8k (0.756) | -12.1k (0.909) / 361 / 41.3k | -26.6k | 0.358 |
| session_gap_carry | CRUDEOILM | 30m | -48.8k (0.752) | -11.8k (0.916) / 363 / 47.5k | -26.3k | 0.35 |
| session_gap_carry | CRUDEOILM | 60m | -46.5k (0.769) | -15.5k (0.898) / 368 / 39.0k | -30.3k | 0.326 |
| session_gap_carry | GOLDPETAL | 15m | -3.2k (0.517) | -1.8k (0.852) / 429 / 3.2k | -4.4k | 0.158 |
| session_gap_carry | GOLDPETAL | 30m | -3.3k (0.525) | -2.1k (0.837) / 423 / 3.4k | -4.6k | 0.127 |
| session_gap_carry | GOLDPETAL | 60m | -3.4k (0.531) | -1.0k (0.917) / 417 / 3.1k | -3.6k | 0.273 |
| session_gap_carry | GOLDM | 15m | -12.8k (0.973) | +275.0k (1.278) / 429 / 207.3k | +188.5k | 0.938 |
| session_gap_carry | GOLDM | 30m | -25.0k (0.951) | +245.8k (1.241) / 423 / 219.5k | +160.5k | 0.906 |
| session_gap_carry | GOLDM | 60m | -28.1k (0.948) | +344.8k (1.339) / 417 / 221.4k | +260.1k | 0.969 |
| trend_impulse_v3 | NATGASMINI | 15m | -22.9k (0.98) | -77.4k (0.881) / 1091 / 107.1k | -135.7k | 0.149 |
| trend_impulse_v3 | NATGASMINI | 30m | +96.5k (1.125) | -90.0k (0.809) / 542 / 111.6k | -118.9k | 0.075 |
| trend_impulse_v3 | NATGASMINI | 60m | +116.9k (1.216) | -85.2k (0.741) / 285 / 124.9k | -100.4k | 0.045 |
| trend_impulse_v3 | CRUDEOILM | 15m | -88.3k (0.858) | -52.9k (0.874) / 1118 / 87.3k | -96.1k | 0.121 |
| trend_impulse_v3 | CRUDEOILM | 30m | -13.4k (0.966) | -39.7k (0.864) / 553 / 69.1k | -61.0k | 0.173 |
| trend_impulse_v3 | CRUDEOILM | 60m | -19.9k (0.927) | -14.7k (0.927) / 292 / 54.2k | -26.0k | 0.367 |
| trend_impulse_v3 | GOLDPETAL | 15m | -8.0k (0.653) | -4.1k (0.881) / 993 / 7.2k | -10.1k | 0.143 |
| trend_impulse_v3 | GOLDPETAL | 30m | -3.7k (0.745) | +0.3k (1.015) / 506 / 2.8k | -2.7k | 0.531 |
| trend_impulse_v3 | GOLDPETAL | 60m | -2.0k (0.799) | -1.4k (0.923) / 272 / 4.0k | -3.1k | 0.351 |

## 7b. Longer real-MCX validation (your next step, needs Kite)

§6e already ran the strategies on ~7–10 months of real MCX prints from a public source.
Kite gives a longer, cleaner history (with volume) — use it to grow the sample:

1. **Backtests view → strategies:** select `spike_fade`, `shock_reversal`,
   `vwap_band_reversion` on NATGASMINI and CRUDEOILM (`gold_month_turn` on GOLDM only
   to grow its sample — it is not deployable, §6e). Prefer the **60m interval** — Kite serves 400 days of
   60m history but only 200 days of 15m, and the shock strategies spend their first ~30
   sessions warming up their volatility norm. Expect few trades (≈ 10–15 a year per
   strategy): judge the sign and the profit factor against §4.5/§7, not the rupee total.
2. **Premium (options) column:** the sweep's premium path now applies each strategy's own
   `option_exits` and `option_tenor_days`, matching what the live bot will do (§6c).
3. **Options Calc view:** before paper trading, confirm the bot finds an option chain for
   each instrument and check the real bid-ask spread against the break-even spreads in
   §6e (≈ 9% for the NATGASMINI strategies, ≈ 20% or more for crude).
4. **Paper trade** with the strategy assigned per instrument (Home/Monitor) — first
   decide the three risk settings in §6f, or most multi-session trades are cut on day 1. The live
   engine fetches the extra history the shock strategies need (`min_history_days`),
   enters at 09:30 the session after a shock, and uses the strategy's option exits.

(The mock provider used in tests serves only a few sessions of NSE-hours candles, so a
mock sweep of these strategies shows zero trades — that is expected, not a failure.)

## 8. Reproduce

```bash
cd paper-trader/research/commodity
./download_dukascopy.sh                 # 2019-2026 5m bars → data/raw (rate-limited; refetch_months.py fills gaps)
../../backend/.venv/bin/python build_dataset.py      # → data/mcx/*_{5,15,30,60}m.pkl  (MCX session, INR, rolls)
../../backend/.venv/bin/python final_eval.py         # the §7 matrix
../../backend/.venv/bin/python portfolio.py          # per-year, regime attribution, books
../../backend/.venv/bin/python neighbourhood.py      # parameter-neighbourhood robustness
../../backend/.venv/bin/python verify_gold_month_turn.py   # carry adjustment + 2005-2018 check (needs data/d1/xauusd_d1.csv)
../../backend/.venv/bin/python build_yahoo.py NG=F:NATGASMINI CL=F:CRUDEOILM   # needs data/yahoo/*.json
COMMODITY_DATA=<root whose mcx/ -> yahoo_mcx/> ../../backend/.venv/bin/python crosscheck_yahoo.py
```
Component studies: `features.py`, `session.py`, `hours.py`, `gold_usd_gap.py`,
`gold_night.py`, `overnight2.py`, `ng_shock.py`. Silver: `silver_check.py` on the Yahoo SI=F set (§6d); the Dukascopy silver download was
rate-limited and did not complete in this session.

