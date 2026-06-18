# Autonomous Options Paper-Trading Platform

A single-user, localhost trading bot. It runs the EMA50 + displacement (z-score)
strategy on a set of underlyings, and **whenever a signal fires it autonomously
picks the best-value option contract and paper-executes a 1-lot order** — no
human in the loop. You only choose, up front, which instruments are allowed to
trade. Everything else (signal → contract selection → fill → exits → analytics)
happens on its own.

Starting capital is **₹50,000**. Nothing is ever sent to a real account.

> It runs today with **zero setup and no Kite account** via a built-in synthetic
> market (`MockProvider`). When you get a Kite Connect subscription, flip one
> config value and the identical engine runs on live data.

---

## Quick start (no Kite needed)

Two processes. Backend on **:8090**, frontend on **:5173** (8000 is left alone
for the unrelated `stock-market-analyst` app).

**1. Backend**
```bash
cd paper-trader/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8090
```

**2. Frontend** (new terminal)
```bash
cd paper-trader/frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The synthetic market starts immediately: signals
fire, contracts get picked, trades open and close, and the dashboard fills in
within a minute. Adjust the demo speed with `PT_MOCK_TICK_SECONDS` (seconds of
real time per simulated candle; default 3).

---

## The four views

| View | What it shows |
|------|---------------|
| **Monitor** | Top panel to enable/disable any of the 11 instruments, then a live tile grid. Each tile has the ticker (position long/short, capital invested, option bought + premium), z/slope/price, and a **SPOT ⇄ OPT** chart toggle. Click a tile to expand it — that's the only time a per-instrument WebSocket opens, streaming live ticks for that one instrument. |
| **Engine / Logs** | Per-instrument strategy state every tick (close, EMA50, z, z[-1], slope, trend, signal, exit flags, open position) beside a live log of every OPEN/CLOSE/skip/drop. |
| **Options Calc** | For each instrument, the full candidate-contract table the picker evaluated — strike, LTP, OI, spread%, IV, delta, and which rows passed the liquidity floor / delta band — with the chosen contract highlighted and the reason. |
| **Dashboard** | Portfolio equity curve, per-instrument equity curves, win rate, expectancy, avg win/loss, best/worst instrument, **commissions paid**, per-instrument table, and recent trades. |

---

## How the bot decides

1. **Signal** — `strategy/signals.py` (the original strategy, math unchanged) on
   **15-minute** candles (30-minute also allowed; nothing faster). A long entry
   needs EMA50 sloping up + z crossing above +1; short is the mirror.
2. **Best-value contract** — `options/picker.py`: CE for long / PE for short;
   keep contracts with **OI ≥ 500** and **bid-ask spread ≤ 3%**, then pick the
   one whose **delta is closest to 0.50** (within 0.35–0.65). Balances directional
   punch against premium cost and avoids illiquid strikes.
3. **Capital allocation** — `engine/allocator.py`: if cash covers every signal
   firing this tick, take them all. Under a shortfall, fund strictly by liquidity
   **priority** (NIFTY → GOLD MINI → SILVER MINI → CRUDE OIL → BANKNIFTY →
   NATURAL GAS → SENSEX → COPPER MINI → ZINC → LEAD → DHANIYA) until cash runs
   out. Anything unfunded is **dropped, never queued** — only a fresh signal opens
   a new position.
4. **Fill** — `engine/broker.py` simulates a fill at the contract LTP, books
   realistic charges, and deducts from the capital ledger. Always **1 lot**.
5. **Exit** — `engine/exit_monitor.py`: close on premium **−35% stop** or **+60%
   target**, OR the strategy's own exit on the underlying — whichever comes first.

Positions carry across days until they exit. In **Kite mode the book persists**
across restarts (realized P&L compounds). In **mock mode the book resets each
launch** (the synthetic clock restarts each run, so a persisted mock position
would be mispriced).

---

## Charges

Modelled on Zerodha's schedule in `engine/charges.py`, segment-aware (NFO / BFO /
MCX / NCDEX): flat ₹20 brokerage per order, transaction tax on the sell leg only
(STT for equity F&O, CTT for MCX, exempt for NCDEX agri), exchange + SEBI fees,
18% GST on those, and stamp duty on the buy leg. **Rates are indicative — verify
against your contract notes and tune the one schedule dict as needed.**

---

## Going live with Kite

1. `cp .env.example .env`, set `PT_PROVIDER=kite`, `KITE_API_KEY`,
   `KITE_API_SECRET`.
2. Register the redirect `http://127.0.0.1:8090/api/session` in your Kite app.
3. Start the backend, open the dashboard, click **Connect Kite**, finish OAuth.

The engine then resolves index spot / nearest-month MCX futures, live option
chains, lot sizes and tokens dynamically from Kite's instrument dump. If an
instrument has no live chain (e.g. an illiquid agri month, or a segment your
account can't trade), it's simply skipped and logged.

> Confirm your Kite account has the **MCX** (and NCDEX agri, for DHANIYA) segments
> enabled, or those instruments won't resolve a chain.

---

## Config

All knobs live in `backend/app/core/config.py`, overridable via `.env` /
`PT_*` env vars (see `.env.example`): capital, −35/+60 stop/target, target delta
0.50 ± 0.15, OI ≥ 500, spread ≤ 3%, interval (15/30 min), and the mock clock
speed. The instrument universe and priority order are in
`backend/app/core/instruments.py`.

---

## Verify it yourself

```bash
cd backend
.venv/bin/python -m pytest                 # 30 unit tests (picker, charges, allocator, exits, ...)
.venv/bin/python scripts/dryrun.py 700     # headless end-to-end + capital-ledger reconciliation
```

The dry-run runs the real engine against the mock for N ticks and asserts the
ledger invariant `cash == initial + realized − Σ(open entry_cost)` to the paisa.

> **Note:** the mock market is a synthetic development stand-in to exercise the
> software end-to-end. Its P&L is **not** indicative of real performance — real
> results only come from live Kite data.
