# Instrument Intelligence — design

**Date:** 2026-06-26
**Branch:** `feat/live-cockpit`
**Status:** approved design, pre-implementation

Three related features that help the owner decide which instruments to keep, drop,
or trust, and how each is actually performing. All three are **segment-aware**
(options + MIS intraday-equity), not options-only. Backend is built **test-first**
(repo convention; no Alembic — additive idempotent migrations in
`app/db/session.py::_migrate_schema`). Frontend verified with `tsc --noEmit` + `vite build`.

## Shared architectural decision

Extend existing endpoints rather than build parallel ones:
- `/api/signals` already serves the Watchlist rows → extend with signal counts + flag.
- `/api/dashboard` already serves analytics → extend with a `period` filter.
- `/api/portfolio/add` already adds one instrument with a carried interval → extend the
  add path to also carry `strategy_key` + `product`.

Only two genuinely new endpoints: per-instrument detail (`GET /api/instrument/{key}`)
and bulk-add (`POST /api/portfolio/add-bulk`). This keeps the frontend's existing 5s
polling intact and follows the Phase 3/4 patterns already in the codebase.

Setters mirror the existing `set_priority_flag` / `set_strategy` pattern in
`runner.py` (upsert `InstrumentState` + update the live in-memory dict so the next
tick honors the change without a restart). IST time uses
`app.core.market_hours.now_ist()` per `[[timestamp-ist-convention]]` — never naive
`pd.Timestamp().timestamp()`.

---

## Feature 1 — Overtrading red flag (advisory; auto-suggest + manual confirm)

**Intent:** surface instruments firing too many signals (churn) so the owner can
consider removing them. Advisory only — the engine's behavior does **not** change.

### Data — signal counts
`SignalEvent` rows are already written per fresh entry crossover + reinforcement
(`runner.py::_record_signal`, indexed by `instrument_key`). New:

```
analytics.signal_counts(s, now, rolling_days=7) -> dict[str, {"today": int, "rolling": int}]
```
- `today` = `SignalEvent` rows with `time >= IST start-of-today`.
- `rolling` = rows with `time >= now - rolling_days`.
- Computed in one query, grouped by `instrument_key`. Instruments with no signals
  return `{today: 0, rolling: 0}`.

### Model / engine
- Add `overtrade_flag: bool` (default `False`) to `InstrumentState` (model field +
  one line in `_migrate_schema` additions: `("overtrade_flag", "BOOLEAN DEFAULT 0")`).
- `runner.set_overtrade_flag(key, flag)` mirrors `set_priority_flag` (upsert +
  `self.overtrade_flags[key] = flag`); load the dict at startup alongside `priority_flags`.

### Endpoints
- `/api/signals` rows gain: `signals_today`, `signals_rolling`, `overtrade_flag`,
  `overtrade_suggested` (= `today >= overtrade_today_threshold OR rolling >=
  overtrade_rolling_threshold`).
- `POST /api/instruments/{key}/overtrade {flag: bool}` → `set_overtrade_flag`
  (validate key in universe, mirror the priority endpoint).

### Settings (overridable + bounded, new "Overtrading guard" group)
| key | default | bounds |
|---|---|---|
| `overtrade_today_threshold` | 5 | (0, 200) |
| `overtrade_rolling_threshold` | 15 | (0, 1000) |
| `overtrade_rolling_days` | 7 | (1, 90) |

A threshold of 0 disables that arm of the suggestion (never suggests on it).

### Watchlist UI (`WatchlistView.tsx`)
- A red-dot toggle (🔴 / ○) immediately beside the existing 🟣 priority toggle, wired
  to `POST .../overtrade` with optimistic update + reconcile (same pattern as
  `togglePriority`).
- Two small count badges per row: `today · 7d` signal counts.
- When `overtrade_suggested` is true, the count badge renders red and the dot shows a
  hint state — but `overtrade_flag` only changes when the owner clicks. No engine effect.

---

## Feature 2 — Per-instrument breakdown + drill-down

**Intent:** see exactly how each instrument traded — full stats + every trade — across
a selectable time period, not just all-time.

### Period selector
- `/api/dashboard` gains `?period=all|today|7d|30d` (default `all`). Trades are filtered
  by `exit_time >= cutoff` where cutoff derives from `now_ist()` (today = IST
  start-of-day; 7d/30d = now − N days). `all` = no cutoff.
- The cutoff also slices the realized curves and per-instrument table. For the headline
  MTM equity curve (`EquitySnapshot`), the same cutoff filters the snapshot series by time.
- `analytics` helpers (`summary`, `per_instrument_curves`, `recent_trades`, the curve
  functions) gain an optional `since: datetime | None` arg threaded from the route;
  `since=None` preserves today's behavior exactly (back-compatible).
- Dashboard UI: a period toggle row (All-time / Today / 7d / 30d) alongside the existing
  segment + strategy selectors; the selection scopes the whole view.

### Richer per-instrument stats
`summary`'s `per_instrument[key]` block gains: `gross`, `charges`, `avg_pnl`
(net/trades), `avg_win`, `avg_loss`, `expectancy`, `avg_holding_minutes`. Existing
fields (`trades`, `wins`, `net`, `win_rate`) unchanged.

### Detail endpoint
`GET /api/instrument/{key}?segment=&strategy=&period=` →
```
{ "key", "name", "segment", "stats": {<full per-instrument stat block>},
  "trades": [<that instrument's trades, newest first>] }
```
Reuses `recent_trades` filtered to a single `instrument_key`, honoring
segment/strategy/period. `stats` reuses the per-instrument computation on that
instrument's filtered trades.

### UI — `InstrumentDetail` modal
Clicking a row in the Dashboard "Per-instrument performance" table opens a modal (same
structure/styling as the Backtests `Drill` modal): a full stat grid on top, a scrollable
trade list below. The modal inherits the dashboard's current segment / strategy / period
filters. New isolated component; the table rows become buttons that set the selected key.

---

## Feature 3 — Bulk-add backtest winners

**Intent:** from a market-wide sweep, add the top N best **instruments** to the
watchlist in one action, each preset to the strategy + timeframe it backtested best in.

### Selection (client-side, in `BacktestsView`)
The view already holds the filtered/sorted result set. A new "Add top [N]" control
(numeric input, default 5):
1. Collapse results to **best-per-instrument**: for each `instrument_key`, keep the
   single row with the best value of the *current sort metric* (across all intervals ×
   strategies). Honors the grid's current ascending/descending direction.
2. Take the top N instruments by that metric.
3. Open an **add-preview modal**.

### Add-preview modal
Lists the N winners; each row shows:
- inferred **product**: Options if the instrument `has_options`, else Intraday-equity
  (MIS) — with a per-row override dropdown (Options ↔ Intraday-equity).
- its best **strategy** (`strategy_key`) and best **interval**.
- an **affordability badge** + an **Include** checkbox. The checkbox decides whether
  this instrument is added at all. Over-budget rows are **pre-unchecked** (skipped by
  default) but can be re-checked to include. Every **included** instrument is added AND
  enabled for live trading (the owner chose "add enabled, skip over-budget" — not
  "add disabled for review"). There is no per-row enabled/disabled distinction.
  - Over-budget = ATM-option cost > budget for Options product (existing
    `affordable_options` from the result), or for Intraday-equity, cannot be sized
    within the margin band (min-margin × leverage < 1 share at the last price). For
    most cash equities intraday affordability is effectively always true.
- Confirm → posts only the included rows to the bulk endpoint; shows the
  `{added, skipped}` result (server-side `skipped` covers duplicates / unknown keys /
  resolution failures, since over-budget names are already excluded client-side).

### Endpoint
`POST /api/portfolio/add-bulk` body:
```
{ "items": [ { "key", "interval", "strategy_key", "product", "on_home": true } ] }
```
For each item: add to the universe (via `universe_resolver.add_instrument`, extended to
accept `strategy_key` + `product`), set product + strategy + interval on the runner, and
enable it in the live engine (every added item is enabled — over-budget names were
already excluded client-side). Returns `{ "added": [...], "skipped": [{key, reason}] }`.
Server re-validates the universe key and product value defensively; `skipped` covers
duplicates / unknown keys / resolution failures.

### Extensions to existing code
- `universe_resolver.add_instrument(key, provider, on_home, interval, strategy_key=None,
  product=None)` — set the extra `InstrumentState` fields when provided (today it only
  carries interval).
- `/api/portfolio/add` (single) gains optional `strategy_key` + `product` for parity,
  so the existing Drill "+ add to portfolio" button can also carry the drilled
  strategy. Backward-compatible (both optional).

---

## Testing

Backend (test-first, pytest):
- `signal_counts` windowing: today vs rolling boundaries (IST), per-instrument grouping,
  zero-signal instruments.
- `overtrade_flag` set/persist + `/api/instruments/{key}/overtrade`; `overtrade_suggested`
  threshold logic (today arm, rolling arm, 0 disables).
- Dashboard `period` filter: `all` unchanged; `today`/`7d`/`30d` cutoffs filter trades,
  curves, per-instrument table; richer per-instrument stat fields correct.
- `GET /api/instrument/{key}`: filters to one instrument; honors segment/strategy/period;
  stat block + trade list correct.
- `add-bulk`: carries strategy + product + interval and enables each added item;
  duplicate / unknown-key handling lands in `skipped`; `{added, skipped}` shape correct.
  Single-add parity for the new optional `strategy_key` + `product` fields.
- Settings: new overtrade keys overridable + bounds reject out-of-range.

Frontend: `npm run typecheck` + `npm run build` clean.

## Out of scope / non-goals
- No automatic red-flagging or auto-blocking (advisory + manual only).
- No engine behavior change from the red flag.
- No new live-order paths (LIVE MIS still deferred per the program memory).
- No change to the backtest computation or its cache signature.
