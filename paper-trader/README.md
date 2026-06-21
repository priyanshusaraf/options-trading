# Autonomous Options Paper-Trading Platform (live Kite data)

A single-user, localhost trading bot. It runs the EMA50 + displacement (z-score)
strategy on a portfolio of underlyings, and **whenever a signal fires it
autonomously picks the best-value option contract and paper-executes a 1-lot
order** — no human in the loop. Everything (signal → contract selection → fill →
exits → analytics) happens on its own.

Starting capital is **₹50,000**. It now runs on **live Zerodha Kite Connect**
market data.

> ## 🔒 No real capital, ever
> This platform places **no real orders**. The Kite client is `SafePaperKite`,
> a subclass that **hard-disables every order-placement endpoint** (`place_order`,
> `modify_order`, `cancel_order`, `exit_order`, all GTT/MF/convert methods) — any
> such call raises immediately. Kite is used for **market data only** (quotes,
> historical candles, instrument dumps). Fills are simulated internally against
> the live LTP. There is no code path to the exchange's order book.

---

## Quick start

Two processes. Backend on **:8090**, frontend on **:5173**.

**1. Backend**
```bash
cd paper-trader/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # set PT_PROVIDER=kite, KITE_API_KEY, KITE_API_SECRET
.venv/bin/uvicorn app.main:app --port 8090
```

**2. Frontend** (new terminal)
```bash
cd paper-trader/frontend
npm install
npm run dev
```

**3. Connect Kite (daily)** — open **http://localhost:5173**, click **Connect
Kite**, finish the Zerodha OAuth + 2FA. Register the redirect
`http://127.0.0.1:8090/api/session` in your Kite developer app first.

> Kite access tokens **expire ~06:00 IST daily**, so you re-click *Connect Kite*
> each morning (headless auto-login violates Kite's ToS). Live signals only fire
> on **completed 15/30-min candles during market hours** (NSE/BSE 09:15–15:30,
> MCX to ~23:30, NCDEX to ~17:00) — off-hours the engine idles.

The mock synthetic market (`MockProvider`) is retained only for the test suite
and the headless dry-run — it is no longer a running mode.

---

## The eight views

| View | What it shows |
|------|---------------|
| **Home** | Your customizable portfolio universe — a grid of pinned instruments with live signal and position (chartless; click any tile to open the detail chart). Add any instrument (by symbol or from a backtest winner); it joins the live universe and is options-traded if it has listed F&O, or tracked-only if not. Remove with ✕. |
| **Active Positions** | The trading cockpit. Every open position with entry/live LTP, spot, unrealized P&L, the **trailing/ratcheted stop**, target, distance-to-stop/target, holding time, freshness/stale age, reinforcement count and overnight badge — plus manual **Close now**, **Disable entries**, and **Manual paper entry**. Tops out with an intraday-vs-overnight analytics strip. |
| **Monitor** | A lightweight **signal-first list** of the whole universe (signal, z/trend, per-instrument live timeframe, position?, options?, data-health) with filters (active positions / signals now / stale / options-tradable / enabled). Rows never fetch charts — click a row to open the detail modal, which lazy-loads the underlying + option charts and a per-instrument live WebSocket. |
| **Engine / Logs** | Per-instrument strategy state every tick beside a live log of every OPEN/CLOSE/skip/drop. |
| **Options Calc** | The full candidate-contract table the picker evaluated — strike, LTP, OI, spread%, IV, delta, liquidity/delta pass — with the chosen (≈ATM, delta-0.50) contract highlighted and the reason. |
| **Backtests** | Sweep the EMA50+z-score strategy (on the **underlying**) across the liquid universe × all timeframes (1m/5m/15m/30m/1h/day), net of charges. Filter by win rate / profit factor / max drawdown / return %, drill into any equity curve + trade list, and **add a winner to your live portfolio**. |
| **Dashboard** | Portfolio equity curve, per-instrument curves, win rate, expectancy, and a prominent **commissions & cost** strip (gross vs net, charges paid, charge drag) — every figure is net of the full charge stack. |
| **Settings** | Manual-override mode: every reinforcement / overnight / trailing-stop / risk / cadence / option-cache parameter, grouped and documented, **editable live with no code change or restart** (each shows the recommended default and a one-click reset). The engine picks up changes on the next loop. |

---

## How the bot decides (live)

1. **Signal** — `strategy/signals.py` on **15-minute** candles (30-minute also
   allowed; nothing faster). A long entry needs EMA50 sloping up + z crossing
   above +1; short is the mirror.
2. **Best-value contract** — `options/picker.py`: CE for long / PE for short;
   keep contracts with **OI ≥ 500** and **bid-ask spread ≤ 3%**, then pick the
   one whose **delta is closest to 0.50** (within 0.35–0.65). IV/greeks are
   computed locally (Black-Scholes) from the live LTP — Kite provides neither.
3. **Capital allocation** — `engine/allocator.py`: fund every signal if cash
   allows; under a shortfall, fund strictly by liquidity priority until cash runs
   out. Unfunded signals are **dropped, never queued**.
4. **Fill** — `engine/broker.py` simulates a fill at the live contract LTP, books
   realistic charges, and deducts from the capital ledger. Always **1 lot**.
5. **Exit** — `engine/exit_monitor.py`: close on premium **−35% stop** or **+60%
   target**, OR the strategy's own exit on the underlying — whichever comes first.
   The stop is **trailed upward** as profit thresholds are crossed (ratchets only,
   never loosens), so a runner locks in gains.

The book persists across restarts (realized P&L compounds). Tracking-only
instruments (no listed options) show signals + charts but are never options-traded.

## Live trade management

A fast **risk loop** (≈1 s, throttled to Kite limits) marks every open position,
ratchets the trailing stop, and fires SL/TP — **separately** from the slower
**signal loop** that scans completed candles for entries. Positions are therefore
managed far quicker than the old single 30-second tick. The engine never fires a
stop on a **stale or missing** price, and surfaces provider health to the UI.

- **Trailing stop** — each profit step locks the stop higher (defaults reproduce
  entry 400 → SL 410/420/…/460). Never loosens.
- **Reinforcement** — a fresh *same-direction* crossover on an open winner does
  **not** add quantity (no pyramiding). It strengthens management: ratchets the
  stop further into profit (e.g. entry 300 → SL 315), optionally extends the
  target, and increments a reinforcement count — gated by a min-profit floor, a
  cooldown, and a max-count cap.
- **Overnight holding** — positions ≤10 % of capital auto-hold overnight; 10–25 %
  require ≥1 reinforcement; >25 % never carry. Near-expiry (<2 days) or
  long-held (≥5 days) positions are force-squared-off (theta/expiry are the real
  risks for option buyers). Ineligible positions are paper-closed just before
  session close.
- **Intraday vs overnight analytics** — every trade is tagged and its overnight
  gap contribution recorded, so you can see where the edge actually comes from.
- **Option-data research cache** — every downloaded chain is appended to a
  growing local `option_data` history (throttled to a snapshot cadence) for
  reuse and research.
- **Per-instrument live timeframes** — each instrument scans on its own interval
  (5/15/30/60 min), carried over when a backtest winner is promoted.

**Every** parameter above lives in `core/config.py` with documented recommended
defaults and is overridable **live** from the **Settings** view (persisted in the
`runtime_config` table) — no code edits or restart.

---

## Backtest sweep

The Backtests view runs the strategy on the **underlying** (options history is
mostly unavailable) across the **liquid universe** (indices + NSE F&O stock
underlyings + liquid MCX/NCDEX commodities) × six timeframes. Each cell:

- **Sized to capital, no leverage** — each position is the largest whole number
  of F&O lots that fits inside the backtest's `capital` (cash equities: whole
  shares ≤ capital). An instrument whose single lot already costs more than the
  capital is reported as `lot > capital — not tradable at this size`
  (`affordable = False`), never silently sized to one lot. `capital` is the
  capital available to the backtest, **not** an account base; Return % / equity /
  CAGR compound on each position's own notional, so Net P&L is shown beside that
  notional, not against any fixed account figure.
- **Pure-strategy exits** — enter on the crossover, exit on the z/EMA reversal.
  No option-premium stop/target (those don't map to the underlying).
- **Net of charges** via the underlying charge schedules (equity delivery with
  dual-leg STT + DP charges; futures with 0.02% STT) — so curves aren't smoothed
  by ignoring fees.

Metrics: trades, win rate, **profit factor**, **max drawdown**, return %,
expectancy, CAGR. Filter, sort, drill in, and promote winners to the live
portfolio. The sweep runs in the background with a progress bar and caches
results (reruns are instant). A **FULL MARKET** scope (all NSE/BSE equities) is
available but slow.

---

## Charges

Modelled on Zerodha's schedule in `engine/charges.py`, segment-aware. **Options**
(NFO/BFO/MCX/NCDEX, what the live engine trades): flat ₹20 brokerage, STT/CTT on
the sell leg (0.10% NSE options, post-Oct-2024), exchange + SEBI fees, 18% GST,
stamp duty on buy. **Underlying** (what the backtest trades): equity delivery
(₹0 brokerage, 0.10% STT both legs, ₹13.5 DP on sell) and futures
(min(₹20, 0.03%), 0.02% STT sell). Portfolio P&L, equity curves, and all backtest
metrics are **net** of this full stack. **Rates are indicative — verify against
your contract notes and tune the one schedule dict as needed.**

---

## Config

All knobs live in `backend/app/core/config.py`, overridable via `.env` /
`PT_*` env vars (see `.env.example`): provider, capital, −35/+60 stop/target,
target delta 0.50 ± 0.15, OI ≥ 500, spread ≤ 3%, interval (15/30 min). The seed
universe lives in `backend/app/core/instruments.py`; the live universe is
DB-backed (`universe_instruments`) and grows as you add instruments.

---

## Stop-loss / take-profit control

Two levels, both live-editable:

- **Global default** — `stop_loss_pct` / `target_pct` in the **Settings** view set
  the −%/+% applied to **every new entry** (bounds-validated). Defaults −35% / +60%.
- **Per-position** — on the **Active Positions** cockpit each open position has an
  editable **Set SL / TP** row: type a new stop and target premium and hit *Set*.
  A hand-set **target is pinned** (a reinforcement won't push it out); the trailing
  stop still ratchets upward from wherever you put it.

## Notifications (Telegram, free)

Get a phone ping when a position **nears its SL/TP**, plus on every fill and exit —
so you don't have to watch the screen.

1. Message **@BotFather** → `/newbot` → copy the **bot token**.
2. Message your new bot once, then open
   `https://api.telegram.org/bot<token>/getUpdates` and copy the `chat.id`.
3. Put both in `backend/.env` as `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` and
   restart the backend. (Blank = notifications off; the engine is unaffected.)

Tune in **Settings → Notifications**: `alert_proximity_pct` (how close to the
SL/TP level triggers the "approaching" warning — default 10%) and `notify_on_signal`
(also ping on each fresh entry signal; off by default). The "approaching" alert
fires **once** on entering the zone and re-arms when the premium leaves it.

---

## Verify it yourself

```bash
cd backend
.venv/bin/python -m pytest                 # unit tests (picker, charges, allocator,
                                           #   exits, backtest, SafePaperKite, hours, …)
.venv/bin/python scripts/dryrun.py 700     # headless engine + capital-ledger reconciliation
.venv/bin/python scripts/backtest_smoke.py # headless sweep + net-of-charges invariant
```

The dry-run asserts the ledger invariant `cash == initial + realized − Σ(open
entry_cost)` to the paisa. Both headless scripts force the mock provider — no Kite,
no network. (The mock's P&L is a synthetic dev stand-in, **not** indicative of
real performance — real results only come from live Kite data.)
