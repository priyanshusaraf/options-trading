# Backtester audit — 2026-08-01

Audit of `app/backtest/` against the ten dimensions in the owner's Phase-1 brief:
look-ahead/survivorship bias, fills, commissions, slippage, latency, partial fills,
leverage, pyramiding, options, statistics.

**Method:** read the code, not the docstrings — then test the claim. Each verdict below
cites the file and line that supports it. One defect was found and fixed under TDD in the
same session; the rest are either clean, or *structural divergences between the backtest and
the live engine* that are not bugs but will mislead anyone reading a backtest number as a
live expectation.

**Headline:** the backtester is more honest than most. No look-ahead. Full charge stack on
both legs, direction-aware. Statistics that label their own limitations. The one real defect
— zero execution cost on the spot path — mattered a great deal, because the strategy's entire
measured edge is smaller than a plausible round trip.

---

## Verdicts

| # | Dimension | Verdict |
|---|---|---|
| 1 | Look-ahead bias | **Clean** |
| 2 | Survivorship bias | **Present, structural** — universe is currently-listed names |
| 3 | Fills | **Clean/conservative**, but no intrabar stop (diverges from live) |
| 4 | Commissions | **Clean** — full segment-aware stack, both legs, direction-aware |
| 5 | Slippage | **WAS A DEFECT — FIXED 2026-08-01** |
| 6 | Latency | **Implicitly one bar**; no sub-bar model. Acceptable at 15m, stated |
| 7 | Partial fills | **Not modelled** (live has them) |
| 8 | Leverage | **No relationship to live sizing** — the biggest interpretive trap |
| 9 | Pyramiding | **Not modelled** — one position, no reinforcement |
| 10 | Options | **Two paths**; the spot path deliberately tests the underlying |
| 11 | Statistics | **Clean and self-documenting** |

---

## 1. Look-ahead bias — CLEAN

The strongest result of the audit, and worth stating positively because it is the failure
that would invalidate everything else.

- **Fills are next-bar-open.** A decision confirmed on bar `i` sets `pending` and executes at
  bar `i+1`'s open (`engine.py:255-281`). No same-bar fills — explicit Pine parity with
  `process_orders_on_close=false`.
- **Exit decisions start the bar AFTER the fill** (`engine.py:287`, `if i > pos["entry_idx"]`),
  so a position cannot be managed on its own entry bar.
- **Every strategy indicator is backward-looking.** A scan for forward-looking operations —
  `shift(-N)`, `rolling(center=True)`, `bfill`/`backfill` — returns nothing across
  `app/strategy/` and `app/backtest/`. Every shift in `expanding_z_v4.py` is `.shift(1)` or
  `.shift(2)`, i.e. *prior* bar values (lines 34, 42, 106-107, 120-123).
- **ATR is causal** (`wilder_atr`), and the ratchet's risk units freeze at the fill bar
  (`engine.py:274`).
- **Computing signals over the full series then slicing is safe here.** `compute_signals`
  deliberately computes over the FULL candle series before walk-forward folds slice it
  (`engine.py:188-205`). That would leak with a non-causal indicator, but every indicator in
  use depends only on bars ≤ i, so bar `i`'s value is identical whether or not later bars
  exist. The docstring's stated reason — seed consistency, since slicing first would shift
  path-dependent EMA/ATR seeds — is correct.

## 2. Survivorship bias — PRESENT AND STRUCTURAL

The tradable universe is a curated seed list of instruments that exist *today*
(`app/core/instruments.py`, `app/backtest/universe.py`), and history is pulled from Kite per
current instrument. Nothing delisted, merged, or renamed can ever appear.

This is not fixable with the current data source and is **not** a code defect — but any
cross-sectional claim ("this strategy works on PSU financials") inherits it. For a
single-name intraday strategy on large, liquid, still-listed names the practical distortion is
small. It would become serious the moment the research plane starts ranking a broad universe.

## 3. Fills — CLEAN, but the live engine exits differently

The state machine is conservative and correct for what it models. One divergence is worth
knowing about, and it is not small:

**The backtest never models an intrabar stop.** The ratchet trails on the bar's high/low, then
confirms `stop_hit(close)` (`engine.py:290-293`) and fills at the *next* bar's open. The live
engine places a real exchange SL-M that triggers **intrabar**, the moment price touches the
trigger. So on the same price path:

- Live exits at the stop price, mid-bar.
- The backtest keeps the position to the bar close, then exits at the next open.

Neither is wrong — the backtest is deliberately Pine-parity — but they are *different
strategies* on any bar with a sharp reversal. A gap through the stop favours the live SL-M; a
wick that recovers favours the backtest. Backtest exit statistics should not be read as
predictions of live exit behaviour.

## 4. Commissions — CLEAN

`_close` charges both legs through the full Zerodha stack (`engine.py:335-336`), with
`entry_side`/`exit_side` derived from direction, so a SHORT is charged sell-to-open /
buy-to-cover. This matches the live `charges.legs_for(direction)` fix (safety item E7) rather
than duplicating a subtly different model. Charges are computed on the *actually transacted*
price, which after this session's fix means the slipped fill, not the clean open.

## 5. Slippage — WAS A DEFECT, FIXED

**The finding.** `app/backtest/premium.py` has modelled a half-spread on entry and every exit
since it was written (lines 146-148, 221, 255+). `app/backtest/engine.py` — the **spot**
backtester — filled at the exact bar open with **zero execution cost**. Per the 2026-07
product direction, the spot path is the one that tests the instrument actually traded for the
equity/index universe. So the backtests that inform live equity trading were the ones with no
cost model.

**Why it matters more than usual here.** The retuned intraday exits are a 0.8% stop and a 1.5%
target, and the 2026-08-01 excursion sweep found the largest favourable excursion ever
recorded was **1.216% of notional**. The live engine caps a marketable limit at
`exec_max_slippage_pct = 1%`. An unmodelled round trip anywhere in that range is not a
rounding error — it is the same order of magnitude as the edge being measured.

**The fix.** `slipped()` applies an adverse, direction-aware cost to every fill — entry, exit,
and the `OPEN_AT_END` close — at half the round-trip per side, mirroring `premium.py`'s
structure. New `Settings.backtest_slippage_pct`, default **0.0005 (5 bps round trip)**, a
defensible figure for liquid NSE cash intraday. **Set it to `0.0` to reproduce every
pre-2026-08-01 number exactly** — that escape hatch is tested, so this change stays
falsifiable.

Sensitivity, measured on mock data (absolute values meaningless, the *slope* is the point):

```
NIFTY, 8 trades      0 bps: -41,078      5 bps: -48,268 (-7,191)     20 bps: -69,840
SILVERM, 2 trades    0 bps: +22,636      5 bps: +22,192   (-444)     20 bps: +20,861
```

At the shipped default, NIFTY moves ~₹900/trade. Any conclusion that survives 0 bps but not
5 bps was never real.

**Note the interaction with cash-equity sizing:** quantity is `floor(capital / fill_price)`,
so a long paying more per share now affords *fewer* shares. That is economically correct and
deliberate — sizing off the clean open would let a backtest deploy capital it does not have.
It does mean long and short trades in the same market carry different quantities; the
symmetry test uses a fixed-lot instrument so the cost itself is what gets compared.

## 6. Latency — IMPLICIT, ADEQUATE

There is no explicit latency model, but the next-bar-open fill rule imposes a full bar (15m)
between decision and execution — far more conservative than real order latency. Sub-bar
latency is unmodelled and immaterial at this timeframe. No action.

## 7. Partial fills — NOT MODELLED

`_position` returns a single all-or-nothing quantity (`engine.py:87-96`). The live engine
handles partial fills and flows leftover cash to the next name. A backtest therefore assumes
perfect fill of the whole position at one price. For liquid names at these sizes this is
mild; it would matter for illiquid names or larger capital.

## 8. Leverage — THE BIGGEST INTERPRETIVE TRAP

`backtest_qty` is explicitly **leverage-free** (`engine.py:66-77`): cash equities get
`floor(capital / price)` shares, F&O gets exactly one lot. The backtest holds **one position
at a time**, using the full nominal capital.

Production does something entirely different: `equity_intraday` sizes against **real MIS
margin** with **no leverage cap** (removed 2026-07-22), targeting ~₹10,000 of margin per name
(live override), across **4 concurrent positions**.

So a backtest models one unleveraged position; live runs up to four leveraged ones. **A
backtest `return_pct` is not a prediction of live account return, and its `net_pnl` is not a
prediction of live rupees.** Both are statements about the strategy's raw edge per unit of
price movement — which is what the module docstring says it is for, and it is the right
choice for isolating edge. The danger is purely in reading it as something else. This is the
single most important caveat in this document.

## 9. Pyramiding — NOT MODELLED

Entries are gated on `pos is None` (`engine.py:298`), so there is exactly one position and no
scaling in. The live engine supports reinforcement (options path). Backtests cannot say
anything about reinforcement performance. Consistent with the "one realistic position"
sizing model; noted for completeness.

## 10. Options — TWO PATHS, DELIBERATELY

- `engine.py` trades the **underlying**. Options history is largely unavailable, so this
  measures the strategy's raw edge on the price series. It is now the primary path, since the
  product direction is equity/index on the underlying.
- `premium.py` is the synthetic-premium path (Black-Scholes, IV/RV multiplier, spread,
  expiry). It models spread and expiry properly.

The `option_cost` returned by `simulate` is an **affordability estimate only** — an ATM
Black-Scholes premium at realised vol, ~14 DTE (`engine.py:118-133`). It is not a pricing
engine and no trade is priced from it.

## 11. Statistics — CLEAN AND SELF-DOCUMENTING

Unusually careful. Specifically:

- **Drawdown is close-to-close on the trade equity curve, and says so** (`metrics.py:86-91`),
  with `worst_mae_pct` provided as the true intra-trade companion. Most backtesters silently
  report the flattering one.
- **`consistency` is explicitly labelled "NOT a Sharpe ratio"** (`metrics.py:95`).
- **`sharpe` is a per-trade mean/std annualised by trade frequency** (`×√(trades/year)`) and
  labelled as such (`metrics.py:96`). This assumes independent trades — standard practice,
  worth remembering before quoting it.
- `profit_factor` is `None` rather than infinity when there are no losses (`metrics.py:174`).
- `win_rate_realised` / `return_pct_realised` exclude the open-at-end trade, so an
  unrealised position cannot inflate the headline.

No defects found. No action.

---

## What was changed in this session

1. **Slippage model added to the spot backtester** (§5) — TDD, 10 tests, default 5 bps
   round trip, `0.0` reproduces all prior numbers.

## What is left, in priority order

1. ~~**Backtest/live sizing parity (§8)**~~ — **DONE 2026-08-01**,
   `app/backtest/live_equivalent.py`. `project()` converts a backtest's per-share edge into
   what the live margin model would have sized, with concurrency, and returns the scale
   factor between the two models.
   It takes per-share MIS margin as an **input and refuses to guess it** — that number comes
   from a real `order_margins()` probe, and inventing a leverage figure here would
   manufacture exactly the false precision this audit exists to remove. No margin, no
   number. The linearity caveat (no market impact modelled) is a FIELD on the result rather
   than a docstring, so a projection cannot be separated from its assumptions on the way
   into a report and quietly become a fact. 9 tests, including that a losing edge projects a
   LARGER loss when levered — a projection that only scaled winners would be a marketing
   tool, not a model.
   Still to do: call it from the backtest payload once a live margin quote is available
   there.
2. **Intrabar stop modelling (§3)** — an option to fill the ratchet stop at the trigger price
   intrabar rather than confirming on close, so backtest exits can be compared like-for-like
   with the live SL-M.
3. **Partial fills (§7)** — low priority at current size.
4. **Survivorship (§2)** — becomes important only when the research plane ranks a broad
   universe. Worth a note in the research report rather than code.
