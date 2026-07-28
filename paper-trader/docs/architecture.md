# Architecture

*Relocated from `CLAUDE.md` on 2026-07-28 so it loads on demand rather than in every session.
Facts contradicted by [`audit/ground-truth-2026-07-28.md`](audit/ground-truth-2026-07-28.md)
were corrected during the move; those corrections are marked **(corrected 2026-07-28)**.*

## What this is

A single-user autonomous trading platform on live Zerodha Kite Connect data. It runs the
EMA50 + displacement (z-score) strategy across a portfolio of underlyings and, on every
signal, autonomously picks an instrument and executes an order — no human in the loop.

**It runs on a DigitalOcean droplet, not localhost** (corrected 2026-07-28 — the old
"localhost / single local process" framing was false; see
[`operations.md`](operations.md)). It is **executing real money**: `backend/.env` ships
`PT_EXECUTION=live` + `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY`, and the production database
holds 34 real trades and 50 real broker order IDs (audit §3). The synthetic ₹50,000
starting capital is still the ledger seed and is persisted across restarts — note this
means the reported equity curve is anchored to ₹50k, not to real broker equity (audit §2,
an open code bug).

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
> not apply to the equity/index universe. (Borne out by the book: 33 of 34 real trades
> are `equity_intraday`, 1 is options.)

## The autonomous engine (`backend/app/engine/runner.py`)

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

## Provider abstraction (`backend/app/providers/`)

The engine only ever touches the `MarketDataProvider` interface (`base.py`), so switching from
mock to live Kite is a single config flag (`PT_PROVIDER`) with zero engine changes. `factory.py`
is a process-wide singleton: `mock` (synthetic market — now only for tests + dry-run)
or `kite` (live Zerodha, the production setting). Kite is **market data only** (quotes,
historical candles, instrument dump); IV/greeks are computed locally via Black-Scholes
(`options/pricing.py`) because Kite sells neither.

## Safety model — the gates, and which of them are currently open

**Read this before touching execution code. Real money is at stake right now.**

- **`SafePaperKite`** (`providers/safe_kite.py`) subclasses `KiteConnect` and hard-disables every
  order/GTT/MF/convert endpoint *and* enforces a fail-closed route allowlist in `_request`. Any
  attempt to place a real order through it raises. This is the **data** provider.
- **Broker selection** (`engine/broker_factory.py`): `PaperBroker` (simulates fills internally)
  unless **BOTH** `PT_EXECUTION=live` **and** `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY` are set **and**
  the provider is `kite` → then `LiveBroker` places real orders via `LiveExecutionKite`.
  **All three conditions are satisfied in the shipped `backend/.env`** (corrected 2026-07-28 —
  the old "no real capital ever moves by default" line described the fallback posture, not the
  shipped configuration).
- **The live order path is proven in production, not untested** (corrected 2026-07-28). It has
  placed **50 real orders** and booked **34 real trades** between 2026-07-13 and 2026-07-22
  (`mode='live'` on every `Trade` row in the production snapshot; `order_journal` carries
  19-digit exchange order IDs). Every trade in the production database is live; there are zero
  paper rows. The previous claim that "the first real order is its own first real-world test"
  was false and is retracted.
- **ARM-to-trade gate**: the engine always scans/marks/exits/alerts but never *opens* a new
  position until explicitly armed. It is **disarmed on every process start** — you arm each
  session — and the kill switch disarms it again. Live entries are further gated by the
  daily-loss halt, adaptive order routing, and an ownership guard.
- **ARM gates entries only — not exits.** `mark_and_exit_positions` (risk loop) marks every open
  position to market and fires SL/TP/square-off *regardless of arm state* (the arm checks live in
  `process_entries`, defined at `runner.py:750`, with checks around `runner.py:885, 911, 979,
  1039` — line numbers corrected 2026-07-28). Consequence: **the persisted book must contain
  only positions the real account actually holds**, or the engine will place real orders to
  flatten phantom rows.
- **Max-open-drawdown guard is ON** (corrected 2026-07-28): `max_open_drawdown = 2_500.0`,
  enabled 2026-07-17 by commit `0778f4d`. Docs that call it "shipped disabled" are stale.

## Config layering (`backend/app/core/`)

- `config.py` — `Settings` (pydantic-settings), the static base. All knobs documented here with
  recommended defaults; overridable via `.env` / `PT_*` env vars. **Note:** `KITE_*` and
  `TELEGRAM_*` are deliberately *not* `PT_`-prefixed (`validation_alias`).
- `runtime_config.py` — DB-backed (`runtime_config` table) live overrides editable from the
  **Settings** view with no restart. `effective(settings)` merges base + overrides into the
  `params` dict the engine reads; the signal loop calls `refresh_params()` every iteration so
  edits take effect on the next loop. When adding a tunable knob, add it to `Settings` *and* wire
  it through `runtime_config` if it should be live-editable.

**Documented defaults are not production values.** As of the 2026-07-23 snapshot the production
`runtime_config` table holds six overrides; three of them change documented numbers
(audit §7.6 / Appendix A):

| Knob | `config.py` default | Production |
|---|---|---|
| `intraday_max_positions` | 3 | **4** |
| `intraday_entry_cutoff_minutes` | 25.0 | **60** |
| `max_daily_loss` | 5000.0 | **2000** |

No `intraday_leverage`, `stop_loss_pct`, or `target_pct` override exists in production — those
run at their `config.py` defaults.

## Strategy registry (`backend/app/strategy/registry/`)

Drop a module exposing a module-level `STRATEGY` (a `Strategy` instance) and it is auto-discovered
and registered by `.key`. Default is `trend_impulse_v3`. Resolution is fail-safe — an unknown/None
key falls back to the default so a stale per-instrument assignment can never crash a tick or
backtest. The default strategy keeps the exact v3 chart payload; others go through the generic
`_generic_latest` path reading canonical flag columns.

## Two trading segments

- **options** — buy CE on long / PE on short, 1 lot, **−30%/+60%** premium stop/target
  (corrected 2026-07-28 — `config.py:50` is `stop_loss_pct = 0.30`; the widely-copied "−35%" is
  stale everywhere it appears) with a ratcheting trailing stop that never loosens. Picker
  (`options/picker.py`) keeps OI ≥ 500 and spread ≤ 3%, then picks delta closest to 0.50.
  **Undocumented second mode:** if `pos.entry_atr is not None` the premium trail is skipped
  entirely and the position is governed by an ATR ratchet on the underlying spot
  (`backtest/ratchet.py`) — this applies to `expanding_z_v4` positions only.
- **equity_intraday** (MIS, opt-in via `intraday_enabled`) — **sized against real Zerodha
  margin with no leverage cap** (corrected 2026-07-28; the "5x leverage" cap was removed
  2026-07-22 by `0f93f9a`). Sizing chain: deployable cash is clamped by real
  `margins()["equity"]["available"]["live_balance"]` and **fails closed to ₹0** if funds can't be
  read; target margin per name is `intraday_max_margin = 7,000` (purple names
  `intraday_purple_margin = 10,000`); quantity comes from a real `kite.order_margins()` MARKET/MIS
  probe; picks below the `intraday_min_margin = 2,500` dust floor are skipped; leftover cash is
  deployed to the next name. `intraday_leverage = 5.0` survives **only** as the probe seed and as
  the paper/mock fallback when a live margin quote is unavailable. Concurrency cap is 3 by
  default, **4 in production**. Direction-aware SL/TP on spot, force-flat before close, never
  trailed/reinforced. Handled on a separate code path (`engine/equity_entry.py`,
  `_mark_exit_equity`) so the options path is untouched.

## Backtests (`backend/app/backtest/`)

Sweeps the strategy on the **underlying** (option history is unavailable) across the liquid
universe × six timeframes, net of charges. Runs in a background thread (Kite calls block and are
throttled), writes progress to the `BacktestRun` row for a UI progress bar, and caches each
`(instrument, interval)` cell in `BacktestResult` so reruns are instant. Winners can be promoted to
the live portfolio.

## Persistence (`backend/app/db/`)

SQLite via SQLAlchemy (`paper_trader.db`, gitignored along with `-wal`/`-shm`). `init_db(reset=...)`
resets **only** in mock mode (the mock's sim-clock restarts each process, so a persisted mock
position would be mispriced); live persists the book across restarts so realized P&L compounds. Key
tables: `positions`, `trades`, `capital_state`, `instrument_state`, `universe_instruments` (the
DB-backed live universe — the seed lives in `core/instruments.py`), `equity_snapshots`,
`runtime_config`, `option_data` (growing research cache), `backtest_runs`/`backtest_results`,
`signal_events`, `daily_account_snapshot`, and (added to this list 2026-07-28 — previously
omitted) `watchlists`, `watchlist_membership`, `strategy_lifecycle`, `generated_strategies`,
`order_journal`, `earnings_events`.

**The `order_journal` table is built and in production use** (58 rows, 50 with real broker order
IDs) — docs describing it as a deferred design are stale.

Database growth is an open problem — see [`ROADMAP.md`](ROADMAP.md), Workstream F.

## API + frontend

`api/routes.py` (REST + the two WebSockets) and `api/backtest_routes.py` (prefix `/api/backtest`).
`/ws` pushes engine `state` + `log` + `position_ticks`; `/ws/instrument/{key}` is opened only when a
tile is expanded and streams that one instrument's ticks. The runner is reached via
`request.app.state.runner`.

Frontend (`frontend/src/`) is React + TypeScript + Tailwind, charts via `lightweight-charts`. A
single `LiveProvider` (`state/LiveContext.tsx`) holds the `/ws` connection and feeds every view;
all REST calls go through `lib/api.ts`. Tabs are wired in `App.tsx`; each tab is one file under
`views/`.
