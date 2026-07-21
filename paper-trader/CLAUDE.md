# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-user, localhost autonomous **options paper-trading** platform on live Zerodha Kite
Connect data. It runs the EMA50 + displacement (z-score) strategy across a portfolio of
underlyings and, on every signal, autonomously picks the best-value option contract and
paper-executes a 1-lot order — no human in the loop. **No real capital ever moves by
default** (see Safety model). Starting capital is ₹50,000, persisted across restarts.

Two processes: a FastAPI backend on **:8090** and a Vite/React frontend on **:5173**.
`:8000` is intentionally left free for an unrelated analyst app in the parent repo.

> **Product direction (from 2026-07):** near-term focus is **equity + index research
> and trading on the underlying — NOT stock-specific options.** Options stay fully
> supported and are **not** being removed or degraded, but they drop to the lowest
> priority and are treated as **index-only** for the foreseeable future (index
> futures/spot first; index options much later). New research and strategy work should
> target the equity/index underlying unless a task explicitly says otherwise. This
> also means the mature *spot* backtester now tests the actual traded instrument for
> equities, so the historic "backtests spot but trades options" validation gap does
> not apply to the equity/index universe.

## What to work on next — the agenda

**`docs/ROADMAP.md` is the canonical, always-current agenda and progress tracker.** Read
it at the start of every session and work the topmost unchecked item of the highest
active workstream (Workstream A — switching on the research plane's autonomous loop —
unless a safety item is on fire). Check boxes only with verified evidence (tests green +
the phase's stated acceptance), and update the tracker in the same commit as the work.
Research-plane work must respect the isolation rules listed there (read-only bridges
only; `research/guards.py` stays fail-closed; both test suites + `dryrun.py 700` green).

## Commands

Run everything from `backend/` or `frontend/` — never the repo root.

**Backend** (`backend/`)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                          # set PT_PROVIDER, KITE_API_KEY, KITE_API_SECRET
.venv/bin/uvicorn app.main:app --port 8090    # add --reload for dev
```

**Frontend** (`frontend/`)
```bash
npm install
npm run dev          # :5173, proxies /api + /ws to :8090
npm run typecheck    # tsc --noEmit — there is no test suite or linter on the frontend
npm run build
```

**Tests & headless proofs** (`backend/`) — pytest is configured (`pythonpath=.`, `testpaths=tests`):
```bash
.venv/bin/python -m pytest                       # full suite (~67 files, all offline/mock)
.venv/bin/python -m pytest tests/test_picker.py  # one file
.venv/bin/python -m pytest -k allocator          # by name
.venv/bin/python scripts/dryrun.py 700           # headless engine + capital-ledger reconciliation
.venv/bin/python scripts/backtest_smoke.py       # headless sweep + net-of-charges invariant
```
Both scripts force the mock provider (no Kite, no network). The dry-run asserts the ledger
invariant `cash == initial + realized − Σ(open entry_cost)` to the paisa — keep it true.

## Architecture

### The autonomous engine (`backend/app/engine/runner.py`)
`EngineRunner` is the brain. `main.py`'s lifespan starts **two cooperative async loops** as
background tasks, serialised by one `asyncio.Lock` over a shared DB session:

- **Signal loop** (`run_signal_loop`, ~2.5s) — the slow lane. Per iteration: refresh runtime
  params, refresh live account funds, reconcile orphans, `scan_signals()` (recompute strategy
  on completed candles), `process_entries()` (open new positions), sweep the option-chain
  research cache, handle overnight square-off/gap, snapshot equity.
- **Risk loop** (`run_risk_loop`, ~1s) — the fast lane. `mark_and_exit_positions()` marks open
  positions to market, ratchets the trailing stop, and fires SL/TP. Runs the blocking
  live-order poll off the event loop (`asyncio.to_thread`) so a slow broker poll never freezes
  WebSocket heartbeats. This lane produces the live cockpit position feed.

`tick()` runs all three passes in sequence and exists only for the dry-run and tests.
Per-instrument config (enabled, live interval, entry blocks, product, strategy, priority/
overtrade flags) is loaded into the runner and mutated through its `set_*` methods, which
write through to `InstrumentState`.

### Provider abstraction (`backend/app/providers/`)
The engine only ever touches the `MarketDataProvider` interface (`base.py`), so switching from
mock to live Kite is a single config flag (`PT_PROVIDER`) with zero engine changes. `factory.py`
is a process-wide singleton: `mock` (synthetic market, default — now only for tests + dry-run)
or `kite` (live Zerodha). Kite is **market data only** (quotes, historical candles, instrument
dump); IV/greeks are computed locally via Black-Scholes (`options/pricing.py`) because Kite
sells neither.

### Safety model — paper by default, two gates for live (read before touching execution)
- **`SafePaperKite`** (`providers/safe_kite.py`) subclasses `KiteConnect` and hard-disables every
  order/GTT/MF/convert endpoint *and* enforces a fail-closed route allowlist in `_request`. Any
  attempt to place a real order raises. This is the data provider in normal operation.
- **Broker selection** (`engine/broker_factory.py`): `PaperBroker` (simulates fills internally)
  unless **BOTH** `PT_EXECUTION=live` **and** `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY` are set **and**
  the provider is `kite` → then `LiveBroker` places real orders via `LiveExecutionKite`.
- On top of that, the **ARM-to-trade gate**: the engine always scans/marks/exits/alerts but never
  *opens* a new position until explicitly armed. It is **disarmed on every process start** — you
  arm each session — and the kill switch disarms it again. Live entries are further gated by the
  daily-loss halt, adaptive order routing, and an ownership guard.
- **ARM gates entries only — not exits.** `mark_and_exit_positions` (risk loop) marks every open
  position to market and fires SL/TP/square-off *regardless of arm state* (gate is in
  `process_entries` at `runner.py:506,532`). Consequence for live: **the persisted book must contain
  only positions the real account actually holds before `PT_EXECUTION=live`**, or the engine will
  place real orders to flatten phantom rows. Reconcile/clear the ledger before flipping to live.
- **Live execution has never placed a real order.** The whole live path (`LiveBroker`,
  `KiteOrderClient`, `LiveExecutionKite`) is exercised only against a mock order client in tests.
  The first real order is its first real-world test, on a strategy with no validated track record.

### Going live (operational checklist — read `Safety model` first)
1. **Whitelist the static IP** in the Kite developer console (order routes reject otherwise). Owner-only.
2. **Re-auth Kite** that morning via the **Connect Kite** button — the access token expires ~06:00 IST
   daily and is stored in `backend/access_token.json` (`{date, access_token}`); the order client reads
   it live via `token_source`, so a re-login flows through without a backend restart.
3. **Clean the book** — the live ledger must hold only positions the real account holds (see ARM note
   above). `capital_state` and `positions` carry over across restarts in non-mock mode.
4. **Set `PT_EXECUTION=live`** in `backend/.env` (`PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY` + `PT_PROVIDER=kite`
   must already be set) and restart the backend. Logs print `🔴 LIVE EXECUTION ENABLED` when armed.
5. **ARM** from the cockpit (disarmed on every start). KILL disarms + squares off everything.

### Config layering (`backend/app/core/`)
- `config.py` — `Settings` (pydantic-settings), the static base. All knobs documented here with
  recommended defaults; overridable via `.env` / `PT_*` env vars. **Note:** `KITE_*` and
  `TELEGRAM_*` are deliberately *not* `PT_`-prefixed (`validation_alias`).
- `runtime_config.py` — DB-backed (`runtime_config` table) live overrides editable from the
  **Settings** view with no restart. `effective(settings)` merges base + overrides into the
  `params` dict the engine reads; the signal loop calls `refresh_params()` every iteration so
  edits take effect on the next loop. When adding a tunable knob, add it to `Settings` *and* wire
  it through `runtime_config` if it should be live-editable.

### Strategy registry (`backend/app/strategy/registry/`)
Drop a module exposing a module-level `STRATEGY` (a `Strategy` instance) and it is auto-discovered
and registered by `.key`. Default is `trend_impulse_v3`. Resolution is fail-safe — an unknown/None
key falls back to the default so a stale per-instrument assignment can never crash a tick or
backtest. The default strategy keeps the exact v3 chart payload; others go through the generic
`_generic_latest` path reading canonical flag columns.

### Two trading segments
- **options** (default) — buy CE on long / PE on short, 1 lot, −35%/+60% premium stop/target with
  a ratcheting trailing stop. Picker (`options/picker.py`) keeps OI ≥ 500 and spread ≤ 3%, then
  picks delta closest to 0.50.
- **equity_intraday** (MIS, opt-in via `intraday_enabled`) — margin-sized at 5x leverage, hard cap
  of 3 concurrent, direction-aware SL/TP on spot, force-flat before close, never trailed/reinforced.
  Handled on a separate code path (`engine/equity_entry.py`, `_mark_exit_equity`) so the options
  path is untouched.

### Backtests (`backend/app/backtest/`)
Sweeps the strategy on the **underlying** (option history is unavailable) across the liquid
universe × six timeframes, net of charges. Runs in a background thread (Kite calls block and are
throttled), writes progress to the `BacktestRun` row for a UI progress bar, and caches each
`(instrument, interval)` cell in `BacktestResult` so reruns are instant. Winners can be promoted to
the live portfolio.

### Persistence (`backend/app/db/`)
SQLite via SQLAlchemy (`paper_trader.db`, gitignored along with `-wal`/`-shm`). `init_db(reset=...)`
resets **only** in mock mode (the mock's sim-clock restarts each process, so a persisted mock
position would be mispriced); live persists the book across restarts so realized P&L compounds. Key
tables: `positions`, `trades`, `capital_state`, `instrument_state`, `universe_instruments` (the
DB-backed live universe — the seed lives in `core/instruments.py`), `equity_snapshots`,
`runtime_config`, `option_data` (growing research cache), `backtest_runs`/`backtest_results`,
`signal_events`, `daily_account_snapshot`.

### API + frontend
`api/routes.py` (REST + the two WebSockets) and `api/backtest_routes.py` (prefix `/api/backtest`).
`/ws` pushes engine `state` + `log` + `position_ticks`; `/ws/instrument/{key}` is opened only when a
tile is expanded and streams that one instrument's ticks. The runner is reached via
`request.app.state.runner`.

Frontend (`frontend/src/`) is React + TypeScript + Tailwind, charts via `lightweight-charts`. A
single `LiveProvider` (`state/LiveContext.tsx`) holds the `/ws` connection and feeds every view;
all REST calls go through `lib/api.ts`. Tabs are wired in `App.tsx`; each tab is one file under
`views/`.

## Conventions & gotchas
- **Kite access tokens expire ~06:00 IST daily.** Re-auth via the **Connect Kite** button each
  morning (headless auto-login violates Kite ToS). Live signals fire only on completed candles
  during market hours; off-hours the engine idles.
- Strategy is valid only on 15m/30m candles; nothing faster for signals. Per-instrument *live*
  interval may be 5/15/30/60m.
- Charges (`engine/charges.py`) model Zerodha's segment-aware schedule; all P&L/equity/backtest
  figures are **net** of the full stack. Rates are indicative — verify against contract notes.
- Telegram notifications are optional (`notify/`); blank creds = silently off, engine unaffected.
- Commit/push only when asked; the working branch here is a feature branch off `main`.
