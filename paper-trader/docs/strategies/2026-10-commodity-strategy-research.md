# Commodity strategy research — MCX NG / crude / gold (October 2026)

**Goal (owner's brief):** five meaningfully different, OHLCV-only strategies for MCX
commodities (primary: NATGASMINI and GOLDPETAL; also CRUDEOILM, SILVERMIC), built in
layers so that each component's contribution is measured, each mapped to the market
regime it is for — and at least one profitable **after charges** on gold, natural gas
or crude.

**Short answer:** see [§6 Verdict](#6-verdict). Most textbook intraday ideas (VWAP-slope
trend, SuperTrend, squeeze breakout, session-VWAP fades) do **not** survive the MCX
mini-contract cost stack out-of-sample. What did survive was found by measuring
components first: **multi-session shock reversal** (crude, NG up-spikes), **swing
reversion to a 10-day VWAP after a climax push** (NG), and the **MCX overnight-gap
structure in gold**.

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
up-spikes (OOS shorts +₹41k, longs −₹2k). Crude and gold lose OOS → **NG only**.
Caveats: ~10 trades/year; adverse excursions can be large (OOS max DD ₹43k on one lot).

### 4.5 `shock_reversal` / `spike_fade` — multi-session fade of a volatility-shock day  ✅ (crude, NG)

*Regime:* EXPANSION (a shock day) → reversion over the next sessions. One value per
completed session: z = session return / stdev of the previous 60 session returns; the
decision is taken on the session's last bar (exchange schedule, no look-ahead), filled
at the next session's open, held 3 sessions, closed near the close.

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
| `spike_fade` on **crude, never tuned on crude** | IS +22k (PF 1.53) → **OOS +33.7k (PF 2.42)**, **positive in all 8 years 2019–2026** |

Final defaults on corrected data (all three timeframes agree within a few %):

| Strategy × instrument | IS net / PF | OOS net / PF / trades | OOS max DD | 2× slippage OOS | P(OOS>0) |
|---|---|---|---|---|---|
| `shock_reversal` × CRUDEOILM | +₹27–28k / 2.0–2.1 | **+₹16–17k / 2.1 / 17** | ₹8.1k | +₹15.6k | 0.89 |
| `spike_fade` × NATGASMINI | +₹164–167k / 2.6–2.7 | **+₹11–14k / 1.15–1.19 / 43** | ₹42k | +₹8–11k | 0.62–0.64 |
| `spike_fade` × CRUDEOILM | +₹22–23k / 1.53 | **+₹32–34k / 2.3–2.4 / 30** | ₹17k | +₹31–32k | 0.90–0.91 |

Per year (₹, 60m): `shock_reversal` crude 2019 +0.1k, 2020 +6.4k, 2021 +12.5k, 2022
+6.5k, 2023 +0.1k, 2024 −0.4k, 2025 −1.8k, 2026 +20.5k · `spike_fade` NG 2019 +2.2k,
2020 −0.6k, 2021 +18.3k, 2022 +120k, 2023 +0.3k, 2024 −5.0k, 2025 +31.7k, 2026
−24.1k · `spike_fade` crude 2019 +2.5k, 2020 +8.7k, 2021 +0.3k, 2022 +7.4k, 2023 +2.0k,
2024 +11.2k, 2025 +7.5k, 2026 +13.5k.

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

1. **`spike_fade` (Energy Up-Spike Fade)** — NATGASMINI OOS +₹13k (PF 1.17); on
   CRUDEOILM (never tuned there) OOS +₹34k (PF 2.42), positive in all 8 years.
2. **`shock_reversal`** — CRUDEOILM OOS +₹16k (PF 2.11), IS +₹28k (PF 2.13).
3. **`vwap_band_reversion`** — NATGASMINI OOS +₹21k…+₹36k (PF 1.26–1.46).

A pre-declared book of 1 lot each (`shock_reversal` crude + `spike_fade` NG +
`vwap_band_reversion` NG) was **positive in every calendar year 2019–2026**: IS
+₹346k (daily Sharpe 1.48, max DD ₹38k), OOS +₹65k (Sharpe 0.55, max DD ₹75k);
monthly correlation crude vs NG legs ≈ 0. (Swapping the crude leg to `spike_fade`
after seeing its result gives OOS +₹83k, Sharpe 0.66 — post-hoc, so not the headline.)

**Not met on gold.** No gold strategy was robust: the only real gold component is the
MCX overnight drift, which GOLDPETAL's cost structure eats; on GOLDM it works only in
the 2024–26 bull market.

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

## 7. Full evaluation matrix

`research/commodity/final_eval.py` (default params, corrected data). Columns: IS net ₹
(PF) | OOS net ₹ (PF) / trades / max DD ₹ | OOS at 2× slippage | bootstrap P(OOS > 0).

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
| shock_reversal | NATGASMINI | 15m | -62.6k (0.282) | -34.9k (0.386) / 14 / 45.7k | -35.8k | 0.154 |
| shock_reversal | NATGASMINI | 30m | -57.0k (0.289) | -36.4k (0.37) / 14 / 46.9k | -37.3k | 0.149 |
| shock_reversal | NATGASMINI | 60m | -56.3k (0.289) | -39.0k (0.331) / 14 / 49.0k | -39.9k | 0.117 |
| shock_reversal | CRUDEOILM | 15m | +27.0k (2.007) | +17.0k (2.153) / 17 / 8.1k | +16.4k | 0.895 |
| shock_reversal | CRUDEOILM | 30m | +27.1k (2.012) | +16.2k (2.107) / 17 / 8.2k | +15.6k | 0.887 |
| shock_reversal | CRUDEOILM | 60m | +28.4k (2.13) | +16.3k (2.108) / 17 / 8.2k | +15.6k | 0.888 |
| shock_reversal | GOLDPETAL | 15m | -0.5k (0.64) | -1.7k (0.471) / 19 / 2.3k | -1.8k | 0.13 |
| shock_reversal | GOLDPETAL | 30m | -0.5k (0.656) | -1.8k (0.459) / 19 / 2.4k | -1.9k | 0.124 |
| shock_reversal | GOLDPETAL | 60m | -0.5k (0.659) | -1.7k (0.47) / 19 / 2.3k | -1.8k | 0.128 |
| shock_reversal | GOLDM | 15m | -33.7k (0.733) | -150.6k (0.515) / 19 / 218.5k | -154.5k | 0.159 |
| shock_reversal | GOLDM | 30m | -31.1k (0.751) | -154.8k (0.503) / 19 / 222.3k | -158.7k | 0.149 |
| shock_reversal | GOLDM | 60m | -31.8k (0.752) | -146.9k (0.515) / 19 / 214.0k | -150.8k | 0.156 |
| spike_fade | NATGASMINI | 15m | +165.9k (2.665) | +13.6k (1.186) / 43 / 42.2k | +11.2k | 0.638 |
| spike_fade | NATGASMINI | 30m | +164.5k (2.636) | +10.9k (1.146) / 43 / 43.9k | +8.5k | 0.615 |
| spike_fade | NATGASMINI | 60m | +167.5k (2.688) | +13.0k (1.174) / 43 / 42.9k | +10.6k | 0.633 |
| spike_fade | CRUDEOILM | 15m | +22.7k (1.534) | +31.9k (2.271) / 30 / 17.5k | +30.6k | 0.897 |
| spike_fade | CRUDEOILM | 30m | +22.4k (1.532) | +33.4k (2.413) / 30 / 16.6k | +32.2k | 0.913 |
| spike_fade | CRUDEOILM | 60m | +22.0k (1.528) | +33.7k (2.418) / 30 / 16.7k | +32.4k | 0.914 |
| spike_fade | GOLDPETAL | 15m | -0.7k (0.736) | -1.4k (0.78) / 42 / 3.4k | -1.7k | 0.326 |
| spike_fade | GOLDPETAL | 30m | -0.7k (0.739) | -1.5k (0.762) / 42 / 3.4k | -1.8k | 0.315 |
| spike_fade | GOLDPETAL | 60m | -0.8k (0.728) | -1.5k (0.767) / 42 / 3.4k | -1.7k | 0.319 |
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

## 8. Reproduce

```bash
cd paper-trader/research/commodity
./download_dukascopy.sh                 # 2019-2026 5m bars → data/raw (rate-limited; refetch_months.py fills gaps)
../../backend/.venv/bin/python build_dataset.py      # → data/mcx/*_{5,15,30,60}m.pkl  (MCX session, INR, rolls)
../../backend/.venv/bin/python final_eval.py         # the §7 matrix
../../backend/.venv/bin/python portfolio.py          # per-year, regime attribution, books
```
Component studies: `features.py`, `session.py`, `hours.py`, `gold_usd_gap.py`,
`gold_night.py`, `overnight2.py`, `ng_shock.py`. Silver was not evaluated: the
Dukascopy download was rate-limited and did not complete in this session.

