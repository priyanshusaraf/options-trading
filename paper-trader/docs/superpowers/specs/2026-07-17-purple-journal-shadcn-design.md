# Design: purple SL/TP tiering · trade journal · shadcn UI · residual autopsy fixes

**Date:** 2026-07-17 · **Status:** approved by owner 2026-07-16 (four AskUserQuestion
gates) · **Branch:** `feat/exits-journal` · **Author:** Fable 5 (advisor); Sonnet 5
implements TDD; Opus 4.8 judges P1/P2 analytics.

This spec is also the **session handoff document**: §1 states exactly where the
project stands so any agent can pick up mid-stream.

---

## 1. Status snapshot (as of 2026-07-17 morning)

**DONE (committed on `feat/exits-journal`, NOT yet deployed to the VPS):**

- P0 research-plane freeze (`3d45660`, `8ebdc5e`) — `PT_RESEARCH_ENABLED` default off.
- 2026-07-16 autopsy safety fixes (plan: `../plans/2026-07-16-autopsy-safety-fixes.md`):
  - per-instrument tick size on every exchange-stop price — `f354d1f` + `b00c649`;
  - `intraday_leverage` as a binding notional cap (+ dust-floor follow-ups) —
    `cefa966`, `78c329f`, `f1add14`;
  - own SL-M fills booked `STOP_LOSS`, not `RECONCILED_EXTERNAL_EXIT`, and no
    false re-entry block — `51aa07b`.
- Multi-lens VPS log/DB autopsy (Jul 13–15) — ranked findings in the 2026-07-16
  session workflow output; headline numbers repeated in §7 below.

**⚠️ DEPLOY GAP (owner action, off-market only):** the VPS still runs the
2026-07-14 09:33 deploy. Everything above — including the tick-size fix that stops
LT/MARUTI trading naked and the square-off-window entry block (`64183f1`) — is
**not in force live** until the next rsync + restart + journalctl marker check.
Until then, consider blocking LT and MARUTI from `equity_intraday`.

**IN FLIGHT (this spec):** §2 purple SL/TP tiering · §3 residual log fixes ·
§4 shadcn foundation + view re-skins · §5 trade journal · §6 H13 order journal ·
§7 P1 exit-autopsy replay.

**DEFERRED (explicit owner decisions):** P2 exit-policy optimizer (next session,
fed by §7); P5 MTF engine (spec conversation first); research-plane resumption
(frozen); C6 synthetic-premium (inert without a vol surface); slippage telemetry;
controlled live test-fire; SEBI/Zerodha algo-registration confirmation (owner).

**Git:** local `feat/exits-journal` is ahead of origin by the 6 safety commits —
push approved by owner, happens with this spec's commit. The VPS has no git;
deploys are whole-tree rsync, so **any** deploy ships everything on the branch.

---

## 2. Purple SL/TP tiering

Purple (`InstrumentState.priority_flag`) currently affects only slot priority and
margin (`intraday_purple_margin`). Exit geometry is global: 1% SL / 2% TP
(`config.py:184-185`) for every name. Owner: purple names are higher-conviction and
more volatile — they need wider bands (SL 1.5%, TP 3%).

**Knobs** (both in `Settings` + `runtime_config` OVERRIDABLE/BOUNDS, live-editable,
Settings-view labels like the existing purple-margin knob):

- `intraday_purple_stop_loss_pct: float = 0.015`
- `intraday_purple_target_pct: float = 0.03`

**Entry-time binding.** The percentages a position was opened with are frozen onto
the row: new nullable `Position.entry_sl_pct` / `Position.entry_tp_pct` columns
(+ `app/db/session.py:_migrate_schema`, mirror `tests/test_migration.py`).
Rationale: the lockstep ratchet **recomputes the initial band from percentages every
tick** (`runner.py:521-522` → `lockstep_band(sl_pct=…, tp_pct=…)`), so an open
position must not change shape when the flag is toggled mid-trade.

**Wiring:**

1. `runner.process_entries` (intraday branch) resolves the pct pair by
   `pick.is_purple` and passes it to `broker.open_equity_position`, which gains
   optional `sl_pct`/`tp_pct` parameters (default `None` → current params lookup,
   so every existing caller/test is unchanged) and persists them on the row.
   `equity_stop_target` (`broker.py:115`) is called with the resolved pair.
2. `runner._apply_lockstep` passes the frozen pct into `lockstep_band` when the
   column is non-NULL, else the global knob (explicit `is None` check, not a falsy
   `or`) — legacy rows (NULL) behave exactly as today.
3. The exchange SL-M flows from `pos.stop_price` unchanged (and now lands on the
   real tick grid per `f354d1f`). No new sync work.
4. Log marker on purple entries: `purple band SL 1.5% / TP 3.0%` (grep-able for
   deploy verification).

**Tests (TDD):** purple entry gets 1.5/3.0 and persists the pcts; normal entry
gets 1/2 with NULL-compatible behavior; mid-trade flag toggle does NOT change an
open position's band or ratchet math; lockstep on a purple position derives the
band from the frozen pcts; runtime_config override of the purple knobs applies to
NEW entries only; migration test for the two columns.

Note for P2: the optimizer will sweep the purple pair independently of the normal
pair — another reason for explicit knobs over a multiplier.

---

## 3. Residual autopsy fixes (small batch)

1. **Token-storm short-circuit** (autopsy rank 5). ~3,800 lines/morning of
   per-instrument `historical_data failed: Incorrect api_key or access_token`
   between ~09:00 and re-auth, with zero backoff. Fix: one engine-wide
   "token known-bad" latch — on an auth-classified failure, the signal loop skips
   per-instrument historical fetches and logs ONE suppression line
   (`token invalid — pausing market-data sweep until re-auth`), retrying one probe
   per loop; any success clears the latch (mirror the proven `margins()`
   suppress-until-recovers pattern from `a05125f`). Tests: storm collapses to
   1 line + probe; recovery resumes the sweep; non-auth errors unaffected.
2. **H15 — enable `max_open_drawdown`.** Knob exists (`config.py:147`, 0 = off,
   already live-editable). Set default **₹2,500** (half the ₹5k daily-loss halt —
   open MTM bleeds faster than realized) and surface it in the Settings view help
   text. Owner can retune live. Test: breach halts NEW entries, exits unaffected.
3. **Log-noise demotion** (autopsy medium): uvicorn access-log lines for the
   polling GETs (`/api/execution/state`, `/api/status`, `/api/signals`, …) drop to
   DEBUG via access-log filter; SL-M placement failures rate-limit to one ERROR
   per order-id per minute (state, not spam — the 1,820× LT repeat buried the
   journal). Tests: filter passes non-polling routes; rate-limiter emits 1/min.

Explicitly **not** in this batch (parked for P2 prep): `signal_events`
acted/note instrumentation, `risk_loop_stalled` cause tagging, finer
`exit_reason` taxonomy (`LOCKSTEP_BE`, `PROFIT_LOCK`, …) — the last lands with P2
per the roadmap.

---

## 4. shadcn foundation + per-view re-skins (P3)

Stack (verified `frontend/package.json`): React 18.3 + TypeScript 5.5 + Vite 5 +
Tailwind **3.4.7**. Approach: shadcn/ui with the Tailwind-v3-compatible CLI
generation — **no Tailwind v4 upgrade**.

**Foundation (one agent, Fable-reviewed before any fan-out):**

- `tsconfig` paths + `vite.config` alias (`@/` → `src/`) — required by the CLI.
- Deps: `tailwindcss-animate`, `class-variance-authority`, `clsx`,
  `tailwind-merge`, `lucide-react`, Radix primitives as pulled by components.
- `components.json`, design tokens as CSS variables (dark theme default —
  keep the current near-black/zinc mood), `cn()` util.
- Primitives: Button, Card, Badge, Table, Tabs, Sheet, Dialog, Input, Select,
  Switch, Toast/Sonner, Skeleton.
- Responsive app shell: bottom tab bar ≤768px / left sidebar on desktop, replacing
  the current tab strip in `App.tsx`. **`LiveContext` and `lib/api.ts` untouched.**
- Acceptance: `npm run typecheck` + `npm run build` green; 390px + 1280px
  Playwright screenshots reviewed.

**Per-view re-skins (after foundation approval): worktree-isolated Sonnet agents**,
priority order: Watchlist → Positions → **Journal (new, §5)** → Backtests
(mobile-first: launch + monitor a sweep from the phone) → Trades →
Dashboard/Performance → Settings → Engine. Each agent: one view file, typecheck
green, 390px screenshot; Fable reviews every screenshot before merge. Acceptance:
every view usable one-handed at 390px over the tailnet.

---

## 5. Trade journal (P4; owner chose **executed + missed** v1)

Purpose: log the owner's **manual/physical trades** (commodity minis) and the
setups they *didn't* take, so "what's happening and what's missing" is measurable.

**Isolation:** own SQLite `journal.db` beside `paper_trader.db`, separate
SQLAlchemy Base (same pattern as `research.db`); the engine never reads it; the
journal never touches engine tables or the broker. Journal API failures must never
affect the trading loops.

**Instruments:** the journal's own list, seeded GOLDM / SILVERM / **CRUDEOILM /
NATGASM** (the bot's universe carries full-size CRUDEOIL/NATURALGAS — wrong
multipliers for manual trading). Specs (lot size, tick, expiry series) resolved
from the Kite instruments dump at add-time; owner can add/remove instruments via
the API. Charges via `engine/charges.py` `MCX_FUT` schedule.

**Tables** (`backend/app/journal/models.py` or `backend/journal/` mirroring the
research layout — implementer's call, isolation rules above are what matter):

- `journal_instruments` — symbol, exchange, lot_size, tick_size, multiplier,
  active flag.
- `journal_views` — append-only horizons (e.g. "long-term", "current-week"):
  name, thesis note, created_at, retired_at (NULL = live). Trades bind to the view
  **live at entry**; retiring a view never rewrites history.
- `journal_trades` — instrument, direction, lots, entry_price, entry_time,
  exit_price/exit_time (NULL = open), view_id, setup_tag, notes,
  `manual_net_pnl` (nullable) — when set it IS the net figure (charges never
  double-applied); otherwise net = gross − `compute_charges` both legs.
- `journal_missed` — instrument, direction, seen_at, setup_tag, skip_reason,
  hypothetical_entry (nullable), notes.
- `setup_tags` — curated list w/ free-add.

**Live MTM:** open journal trades marked via the existing provider quote path
(read-only), surfaced in the UI with unrealized net P&L.

**API:** `/api/journal/*` — CRUD for trades/missed/views/tags/instruments +
`/api/journal/stats` (per-tag win rate, expectancy, net P&L; per-view breakdown;
missed-P&L summary where hypothetical_entry exists). All figures net of charges.

**UI:** new Journal tab on the §4 foundation, mobile-first: one-thumb quick-add
(instrument → direction → lots → price, defaults from live quote), open-trades
card with MTM, tag/missed stats, view switcher. 390px screenshot gate like every
re-skin.

**Tests:** charge math against `MCX_FUT` (paisa-exact), manual-vs-computed P&L
exclusivity, view binding immutability, stats math, API round-trips; frontend
typecheck.

---

## 6. H13 — persisted order journal

Build exactly per the existing Fable spec in `docs/audit-remaining-impl-guide.md`
(§H13): `OrderJournal` table, write-through WORKING→TERMINAL around every real
order, `recover_journal()` on startup before the loops, tag sweep, journal I/O
never blocks an order. One Sonnet agent, TDD, the spec's test list is the
acceptance bar. (Note: the engine DB already has an `order_journal` table on the
VPS snapshot — implementer must reconcile the existing schema/rows with the spec
rather than assume a fresh table.)

---

## 7. P1 — exit-autopsy replay (analysis, no engine code)

Autopsy already established the headline on Jul-15's 9 trades: **gross +₹134,
charges ₹359, net −₹225** — charges ≈ 2.7× the gross edge, with winners ratcheted
to scratch (HEG trailed to +0.08%; DLF capped at +1.64% vs the 2% target). P1
deepens this over ~10 sessions: replay every closed intraday trade through the
pure kernels (`lockstep_band`, `equity_exit`) against Kite 1-minute candles,
classify true exit cause (BE-floor / profit-lock / base SL / TP / strategy /
square-off / SL-M divergence), record MFE/MAE, compute counterfactual P&L per
mechanism disabled. Fan-out as a Workflow per the approved roadmap (one agent per
instrument-day; Opus synthesizes loss attribution). Needs a valid Kite token for
candles; without one, replay degrades to DB+journal-only classification.
Deliverable: `docs/exit-autopsy-2026-07.md` → feeds P2's optimizer.

---

## 8. Sequencing, verification, deploy

```
§2 purple ─┐
§3 residuals ─┼─ backend batch (parallel Sonnet agents, TDD) ─┐
§6 H13 ─┘                                                     ├─► full suite +
§4 foundation ─► review ─► view fan-out (worktrees) ─► Journal UI ┘   dryrun 700 +
§5 journal backend (parallel with §4) ──────────────────────────┘   typecheck
§7 P1 replay workflow — anytime (read-only)
```

- Every backend batch: full pytest suite + `scripts/dryrun.py 700` ledger
  invariant + `scripts/backtest_smoke.py`; frontend: `npm run typecheck` + build.
- Each fix carries a grep-able log marker (VPS deploy verification is
  marker-based; no git on the VPS).
- Commits: one per task, `fix(...)`/`feat(...)` style; push to
  `origin/feat/exits-journal` as batches land (owner approved).
- **Deploy:** owner-gated, off-market only — rsync whole tree + systemd restart +
  journalctl marker check (the 2026-07-14 routine). First post-deploy morning:
  verify `SL-M stop placed` for an LT/MARUTI-class name and the purple band marker.
