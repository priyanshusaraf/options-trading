# C-P2 — Exit-parameter sweep on real trades (2026-08-01)

*Method: `scripts/exit_sweep.py`, replaying the production ledger's own MFE/MAE telemetry.
Sample: 70 closed `equity_intraday` trades, of which **22 carry excursion telemetry** and
can be replayed (48 predate it, 2026-07-24, and are excluded — not zero-filled).*

## The finding that explains everything

How far the real trades actually travelled, as a fraction of entry notional:

| | median | p75 | max |
|---|---|---|---|
| peak **in your favour** (MFE) | 0.286% (₹164) | 0.513% | **1.216%** |
| worst **against you** (MAE) | 0.427% (₹208) | 0.616% | 1.115% |

Two things fall straight out of that table.

**1. The take-profit was mathematically unreachable.** The live target is **1.5% of
notional** (was 3% before 2026-07-31). The largest favourable excursion in the entire
replayable book is **1.216%**. Not one trade ever came close to the target — which is
precisely why `TARGET` has fired **zero times in 72 real trades**. This was never a tuning
problem to be nudged; the level was outside the range the strategy's trades actually
occupy.

**2. These trades go against you more than they go for you.** Median adverse excursion
(0.427%) exceeds median favourable excursion (0.286%). No exit policy can fix that — it is
an entry-quality property. Exits decide how much of the available move you keep; they
cannot manufacture a move that isn't there. Treat everything below as damage control on
the current signal, not as a route to a positive edge.

## What the sweep says

| policy | replayed P&L | win% | exits |
|---|---|---|---|
| **live today** — SL 0.8% / TP 1.5% / lock ₹450×0.3 | −₹590 | 36% | 17 actual, 4 stop, **1 lock** |
| lower the target — SL 0.8% / TP 0.6% | −₹911 | 36% | 5 target, 13 actual, 4 stop |
| target + lock — SL 0.8% / TP 0.6% / ₹150×0.5 | −₹585 | 55% | 5 target, 4 lock, 4 stop |
| tighter stop — SL 0.5% / TP 0.6% / ₹150×0.5 | −₹1,249 | 45% | *(untrustworthy — see below)* |
| **lock-led — SL 0.8% / TP 1.5% / ₹150×0.7** | **+₹268** | 55% | 8 lock, 10 actual, 4 stop |
| grid maximum — SL 0.8% / TP 1.5% / ₹100×0.85 | +₹778 | 64% | 11 lock, 7 actual, 4 stop |
| no target at all — SL 0.8% / TP ∞ / ₹150×0.7 | +₹268 | 55% | *identical to lock-led* |

Actual booked result over the same 22 trades: **−₹913**.

Three conclusions:

- **The give-back lock is the only lever that works.** Peaks are small (₹164 median), so
  the only way to convert them is a floor that keeps most of a small peak. Moving the
  threshold from ₹450 to ₹150 and the fraction from 0.3 to 0.7 flips −₹913 to +₹268.
- **The target is inert.** "TP 1.5%" and "no target at all" produce *identical* results —
  further proof the level is outside the trades' range. Lowering it to 0.6% makes it fire
  five times and makes things **worse** (−₹911): it cuts the few trades that were still
  developing without touching the losses.
- **A tighter stop is worse.** At 0.5% the stop sits inside the median adverse excursion,
  so it converts ordinary noise into realised losses (6 stop-outs, −₹1,249) — and it is
  the only policy the sweep marks **untrustworthy**, because two trades would have touched
  both the stop and the target and their ordering is unknowable.

## What shipped

`config.py` defaults changed:

```
intraday_profit_lock_threshold  600.0 → 150.0
intraday_profit_lock_frac         0.3 → 0.7
```

The grid maximum (₹100 × 0.85) scores higher but is a fitted extreme on 22 trades; ₹150 ×
0.7 is a rounder point on the same slope and is what shipped. Stop and target are
**unchanged** — the data supports no move on either, and the target's irrelevance is a
signal problem, not a settings problem.

> **These defaults are inert in production until the VPS overrides are cleared.**
> `runtime_config` currently holds `intraday_profit_lock_threshold=450` and
> `intraday_profit_lock_frac=0.3`, which shadow the code. Clear both from Settings (or
> the DB) or nothing changes. This exact trap has bitten this project before.

## What this method can and cannot tell you

- MFE and MAE are two scalars, **not a path**. When a candidate stop and target would both
  have been touched, which came first is unknowable. The sweep reports that as an explicit
  band, always headlines the pessimistic end, and marks any result leaning on those trades
  `trustworthy=False`. It never picks a side quietly.
- **Half the sample still ends on the owner's manual exits.** 10 of 22 replayed trades exit
  as `ACTUAL` — meaning the human closed them. So this measures how the parameters would
  have modified the book we have; it cannot tell you what a fully autonomous bot produces.
  Only the no-touch trial can answer that.
- **22 trades is a small sample.** This is a direction to test, not a validated setting.
