# Parameter Optimiser — Suggestive Report (defaults sanity-check)

**Date:** 2026-06-21
**Status:** SUGGESTIVE ONLY — base values stay as-is; this is for the owner to eyeball.
**Scope:** the Settings-view risk parameters (SL/TP, trailing, daily-loss, position
limits, reinforcement, overnight). **Not** the strategy (ema/z/entry_z/slope) — frozen.

---

## The honest constraint first (read this)

**You cannot empirically optimise these parameters with the *current* backtest.**
The sweep simulates the EMA-z signal on the **underlying** with pure strategy-reversal
exits — it does **not** apply the option premium stop-loss, take-profit, trailing,
daily-loss halt, reinforcement, or overnight rules at all. Those only exist in the
**live engine**, on the **option premium**. So:

- The only parameters the current backtest actually exercises are the *strategy*
  ones (which we're not touching).
- Every SL/TP/daily-loss/etc. value below is reasoned from **option-buying first
  principles**, not fitted to data.
- To truly optimise them you need an **option backtest**, which needs **recorded
  option chains** (IV/OI/greeks). We just started capturing those for the whole
  watchlist (2026-06-21). In a few weeks–months there's enough to build it, then
  grid-search the params. The "real optimiser" section at the end describes that path.

So treat this as: *do the current defaults make sense?* (mostly yes) and *what
ranges would I test once the option backtest exists?*

---

## Cluster 1 — Stop-loss / take-profit (option premium)  ·  default −35% / +60%

**Evaluation:** sane and roughly 1.7:1 reward:risk. Two forces bound it:
- **Round-trip charges** are a *fixed* hit (~₹40–50 brokerage + STT/GST/stamp) plus
  spread. On a cheap premium that's a big %, so a *tight* stop (−15/−20%) churns
  straight into costs. Don't go below ~−25%.
- **Theta**: an ATM (delta ~0.5) bought option loses time value daily; the target
  must be reachable before theta eats the move. +60% on a short-dated ATM needs a
  real underlying push.

**Suggest testing:** stop **−30% to −45%**; target **+50% to +120%** — *and* the new
per-position **no-take-profit** for overnight trend runners (you already have it).
The decisive empirical input is the **MFE distribution** (how far option premiums
actually run before reversing) — needs option data.

**Watch:** the `target_pct` bound is (0.001, 10.0) and the UI takes a fraction —
a fat-finger `35` instead of `0.35` = a 1000%-clamped (effectively no) target.
Tighten/relabel (also flagged in the trader review).

## Cluster 2 — Trailing stop  ·  trigger 10%/step, lock 2.5%/step, target 60%

**Evaluation:** conservative and correct in spirit (ratchets up, never loosens, can't
end a reinforced trade as a loss). The 2.5%/step lock is gentle — on a fast mover it
gives back more than necessary; on a choppy one it's about right.

**Suggest testing:** **lock 2.5%–5%/step**; trigger **8%–12%**. For trend names
(commodities, indices in a regime) a tighter lock captures more; for choppy names a
looser lock avoids getting shaken out. This is exactly where **per-instrument** tuning
will pay once the option backtest exists.

## Cluster 3 — Daily-loss halt  ·  default ₹5,000 (= 10% of ₹50k)

**Evaluation:** reasonable circuit breaker (~2–3 stop-outs). Two gaps:
- It's **realized-only** — you can be deep in *open* drawdown with the halt never
  tripping. Add an **equity (realized + unrealized) drawdown halt** too.
- It's a flat rupee value, not a % of equity — scale it to capital.

**Suggest:** **6–10% of current equity**, and on halt optionally **also disarm/flatten**
(a trader who hits the daily stop usually wants to be done for the day).

## Cluster 4 — Position & trade limits  ·  (new, default off)

With ₹50k and 1-lot options costing ~₹2k–15k each you're capital-bounded to ~3–10
positions anyway, but correlated index signals (NIFTY/BANKNIFTY/FINNIFTY CE) can all
fire at once = one big directional bet.

**Suggest:** `max_open_positions` **4–6**; `max_capital_per_trade` **~₹15–20k** (so one
pricey index option can't eat 40% of capital); `reentry_cooldown_minutes` **30–60**
(1–2 candles on 15/30m) to dodge whipsaw re-entry after a stop-out.

## Cluster 5 — Reinforcement  ·  min profit 10%, lock 5%/reinf, max 3, cooldown 15m

**Evaluation:** well-designed (no pyramiding; only strengthens management; the 5%/step
lock clears round-trip charges so a reinforced trade can't net-lose). Defaults are good.

**Suggest testing:** `max_reinforcements` **2–4**; `reinforce_min_profit_pct` **8–15%**.
Low impact vs clusters 1–3.

## Cluster 6 — Overnight holding  ·  auto ≤10%, max 25%, min DTE 2, max hold 5d

**Evaluation:** correctly centres on the real option-buyer killers (theta + expiry).
Two tweaks worth testing:
- **min days-to-expiry 2 → 3**: a 1-DTE long option bleeds viciously; 2 is tight.
- **max holding days 5 → 3–4** for short-dated options (theta compounds); pair with the
  no-TP-overnight feature so a *news* runner is the deliberate exception.

---

## Priority (impact on P&L smoothness)
1. **Daily-loss: add an open-drawdown halt + scale to equity.** (biggest tail-risk gap)
2. **SL/TP + trailing lock.** (shapes every trade's outcome)
3. **Position/per-trade caps + cooldown.** (kills concentration & whipsaw)
4. Overnight DTE/hold tweaks · 5. Reinforcement (fine as-is).

---

## The real optimiser (once option chains are recorded)
1. Build an **option backtest**: replay recorded chains (or reprice via the recorded
   IV surface) so SL/TP/trailing/theta/overnight actually apply on the *premium*.
2. **Grid / Bayesian search** the risk params per instrument-class (index / commodity /
   stock).
3. **Objective = risk-adjusted, not raw return** — optimise **Calmar (return/maxDD)** or
   a Sharpe-like consistency score, matching your "smooth curve" philosophy. Raw return
   alone overfits to a few lucky tails.
4. **Walk-forward / out-of-sample**, and prefer **broad plateaus** of good params over
   sharp peaks (a peak that only works on one window is overfit).
5. Re-run quarterly as regimes change.

Until then: the current defaults are reasonable; the highest-value *real* change is the
open-drawdown daily halt, which doesn't need the option backtest.
