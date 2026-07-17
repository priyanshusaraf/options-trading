# Journal v2 — a day feed you actually want to write in

**Date:** 2026-07-18
**Branch:** `feat/exits-journal`
**Status:** Approved design, ready for implementation plan

## Problem

Two problems, one view.

1. **White borders "in random places."** shadcn primitives (`Card`, `Dialog`, `Select`
   content, `Badge`) use a bare `border` class. `tailwind.config` defines a `border`
   *color token* (`hsl(var(--border))` → the dark `#232733` edge) but `index.css` is
   missing the canonical shadcn base rule that makes bare `border` *use* that token. So
   bare borders fall back to Tailwind Preflight's default `borderColor.DEFAULT`
   (`gray-200`, near-white). Result: near-white borders on every migrated view.

2. **The Journal is a stack of forms, not a place to think.** It exposes quick-add
   trade, missed-setup form, and a by-tag stats table — but there is nowhere to just
   *write*: no daily market narrative, no timestamped mid-session notes, no persistent
   directional bias. The owner currently keeps this in a Google Sheet (per-instrument
   tabs; a `6 month view / 1 month view` bias at the top; then dated blocks of
   `Date / View / trades taken / premium / reason / result`). The freeform "View"
   narrative — the ranting — has no home in the app.

## Scope & non-goals

- **Purely a personal tool.** The journal is fully decoupled from the trading engine.
  The bot is autonomous and is **never** biased by anything written here. No engine
  coupling of any kind is in scope. The journal keeps its own isolated `journal.db`;
  the engine never imports `app.journal`.
- **In scope:** the white-border fix; a day-feed redesign of `JournalView.tsx`;
  daily market-view narrative; timestamped quick notes; persistent 6M/1M horizon bias;
  folding existing trades + missed setups into the day feed; a light lifetime-stats strip.
- **Out of scope:** the heavy "by-tag performance" table (dropped — noise for a personal
  journal); any new bot/research integration; changing how manual trades are entered
  (manual quick-add stays); frontend automated tests (no runner exists per CLAUDE.md).

## Design

### 1. White-border fix

Add the standard shadcn base rule to `frontend/src/index.css`:

```css
@layer base { * { @apply border-border; } }
```

Every bare `border` now resolves to the dark edge token. Fixes `Card`, `Dialog`,
`Select`, `Badge` at once. Verify each migrated view renders seam-free (drive the app,
not just typecheck).

### 2. The reorganization: a day feed

`JournalView.tsx` is restructured from a form stack into a **reverse-chronological feed
of days**, mirroring how the owner's sheet reads top to bottom.

**Header strip** (always visible)
- **Horizon bias**: two editable chips — `6M ▲ bullish` · `1M ▬ neutral`. Click to edit
  stance (free text) + a one-line note. Persists; editable anytime.
- **Lifetime mini-stats**: net P&L · win rate · number of days journaled. (No by-tag
  table.)

**Day feed** (cards, newest first; "Today" pinned at top and auto-created on first write)
Each day card, top to bottom:
- **Date + weekday**, with a day net-P&L badge.
- **Market view** — a large free-text box ("what I'm feeling"); autosaves on blur.
  This is the ranting.
- **Notes thread** — timestamped quick notes droppable anytime, each with an optional
  mood emoji + optional instrument tag; an inline `＋ note` composer. Mid-session rants
  land here.
- **Trades taken** — compact rows auto-pulled from existing journal trades dated that
  day (symbol · direction · lots · entry→exit · net P&L · tag), plus the existing manual
  quick-add to log one.
- **Missed setups** dated that day, folded into the same timeline (distinct row style).
- **Result** — a short autosaving box (the sheet's `result:` row).

Nothing is filed manually: everything dated to a day (trades, missed, notes) collects
under that day automatically.

### 3. Data model (all in the isolated `journal.db`)

New tables, alongside the existing `JournalInstrument` / `JournalTrade` /
`JournalMissed` / `JournalTag` / `JournalView` (all unchanged):

- `JournalDay(entry_date DATE primary key, market_view TEXT nullable,
  result TEXT nullable, created_at, updated_at)` — **upsert by date** (idempotent).
- `JournalNote(id PK, noted_at DATETIME, body TEXT, instrument_symbol FK→journal_instruments nullable,
  mood VARCHAR nullable)` — the quick notes. Grouped into days by the calendar date of
  `noted_at`.
- `JournalBias(horizon VARCHAR primary key — '6M' | '1M', stance VARCHAR,
  note TEXT nullable, updated_at)` — seeded with `6M` and `1M` rows on first run.

`JournalTrade` continues to bind to the internal `JournalView` for FK integrity; that
machinery is untouched. The old `JournalView` (append-only horizon/thesis) is **not**
surfaced in v2 — `JournalBias` is the display bias. `JournalTrade` and `JournalMissed`
are **grouped into** the day feed by their `entry_time` / `seen_at` date, never
duplicated.

### 4. API (`app/journal/routes.py`, prefix `/api/journal`)

One read endpoint the UI leans on:

- `GET /api/journal/feed?limit=N` →
  ```
  { "bias":  [ {horizon, stance, note, updated_at}, … ],
    "stats": {net_pnl, win_rate, days_journaled, trades},
    "days":  [ {date, market_view, result, net_pnl,
                notes:   [ {id, noted_at, body, instrument_symbol, mood}, … ],
                trades:  [ … existing trade dict … ],
                missed:  [ … existing missed dict … ] }, … ] }
  ```
  A single fetch renders the whole feed. Days are newest-first; a date with any note,
  trade, or missed row appears even without a `JournalDay` narrative row.

Granular writes (each opens its own `journal.db` session, as existing handlers do):
- `POST /api/journal/days` — upsert `{entry_date, market_view?, result?}`.
- `POST /api/journal/notes` — `{body, noted_at?, instrument_symbol?, mood?}`; unknown
  instrument → 400.
- `DELETE /api/journal/notes/{id}` — 404 if absent.
- `GET /api/journal/bias` and `PUT /api/journal/bias/{horizon}` — `{stance, note?}`;
  unknown horizon → 400.

Existing endpoints (`/trades`, `/trades/{id}/close`, `/trades/open-mtm`, `/missed`,
`/instruments`, `/stats`) remain for the quick-add flows. `/stats` may be reused inside
`/feed` for the lifetime strip.

### 5. Frontend

Rewrite `frontend/src/views/JournalView.tsx` around the feed. Reuse existing shadcn
primitives (`Card`, `Input`, `Button`, `Badge`) and the existing `lib/api.ts` +
`lib/types.ts` (add the new DTOs and calls). Autosave textareas on blur (debounce not
required — blur is enough). One `GET /feed` on mount + a 15s refresh (matching the
current interval), and re-fetch after any write. No new frontend libraries.

### 6. Testing (TDD, backend `pytest`, journal suite already isolated)

Red-first, in `backend/tests/journal/`:
- **db/models:** new tables create; `JournalBias` seeds `6M`/`1M`; `JournalDay` upsert by
  date is idempotent (second upsert updates, does not duplicate).
- **service:** note CRUD; `feed` assembly groups trades/notes/missed under the correct
  calendar date; per-day `net_pnl` correct; days with only notes still appear.
- **routes:** happy path for `/feed`, `/days`, `/notes` (add/delete), `/bias`
  (get/put); validation (unknown instrument on a note → 400, unknown horizon → 400,
  delete missing note → 404).

The engine's `dryrun.py` ledger invariant and full offline suite must stay green —
journal changes touch only `app/journal/*` and its own DB, so they should be unaffected;
run the full suite to confirm.

## Risks

- **Existing `JournalView` FK on trades.** Do not drop or rename `journal_views`; the
  new bias table is additive. Verify trade quick-add still resolves its default view.
- **Timezone/date grouping.** Group notes/trades/missed by *local* calendar date
  consistently (the codebase already uses `dt.datetime.now()` naive-local throughout the
  journal). Match that convention; a note's day = `noted_at.date()`.
- **Migration on a live journal.db.** New tables are created by `init_journal_db`
  (`create_all` is additive). No destructive migration; existing rows untouched.
