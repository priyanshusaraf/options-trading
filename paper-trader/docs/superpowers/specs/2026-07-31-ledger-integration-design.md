# THE LEDGER — integration design

**Date:** 2026-07-31
**Status:** awaiting owner sign-off
**Supersedes:** `2026-07-17-purple-journal-shadcn-design.md`, `2026-07-18-journal-v2-day-feed-design.md`

Replace the existing paper-trader trade journal with THE LEDGER (`/Users/priyanshusaraf/dev/trade-journal`),
wire it to the Kite account so the owner's discretionary trades are detected automatically and
prompted for reasoning, make reason-capture work on a phone, and — separately — fix the app-wide
typography and the Settings panel.

---

## 1. Owner decisions taken

Recorded because they close forks that would otherwise be re-litigated:

| # | Decision | Consequence |
|---|---|---|
| D1 | The journal is a **full-bleed sub-app keeping THE LEDGER's own visual language** | Two looks in one product, deliberately. The visual break signals "journalling, not monitoring". |
| D2 | **Capture-first mobile**; desktop for analysis | Four purpose-built phone screens, not a responsive port of 12 desktop surfaces. |
| D3 | Kite fills **auto-create** journal trades, then the journal chases for the why | The owner never types a price. Fact layer is broker-sourced. |
| D4 | **Post-hoc reasoning is acceptable.** No capture-latency tracking, no post-hoc badge | See §8 for the one measurement consequence. |

---

## 2. What the recon established

### 2.1 The existing journal is disposable

- **15 files, ~2,030 lines**, all under `backend/app/journal/`, `backend/tests/journal/`,
  `frontend/src/views/JournalView.tsx`.
- **Exactly 5 edit sites outside it**: `backend/app/main.py:28` (import), `:167` (router mount);
  `frontend/src/App.tsx:9` (import), `:21` (TABS entry), `:64` (render). Plus two dead blocks:
  `frontend/src/lib/api.ts:180-222` and `frontend/src/lib/types.ts:200-302`.
- **The engine never writes to it.** Zero `app.journal` imports in `app/engine/*`, `app/api/*`,
  `app/db/*`. Its own docstrings state the isolation as intent.
- **Zero user data.** `backend/journal.db` contains 4 seed instruments and 2 bias rows, on a
  *pre-multi-book* schema (no `journal_books` table), mtime matching `tests/journal/test_init_race.py`.
  It is a leaked test artifact. Per auto-memory `journal-unused-on-vps`, no `journal.db` exists in
  production at all.
- 71 tests vanish with `backend/tests/journal/`. No test outside that directory imports `app.journal`.

**Trap — do not delete:** `backend/tests/test_order_journal.py` and `app/db/models.py:615` `OrderJournal`
are an unrelated broker-order crash-recovery log, replayed at boot (`main.py:97-104`) and driven from
`live_broker.py`, `order_executor.py`, `kite_order_client.py`. They share only the English word "journal".
Likewise every `PRAGMA journal_mode=WAL` and every `journalctl` reference.

One cosmetic residue: `backend/tests/test_equity_short_charge_legs.py:7` cites `journal/pnl.py` as a
correctness reference for direction-aware charge legs. Reword that docstring.

### 2.2 THE LEDGER

Vite 5 + React 18.3 + TS 5.6, **zero runtime dependencies beyond react/react-dom**. ~19,000 lines
across 51 `src/` files. One test file (`src/domain/domain.test.ts`, 493 lines) covering metrics,
ticket grammar, query language and dates — and **nothing** covering `actions.ts`, `store.ts`, or any
component.

Portable core (zero imports from React or `data/`): `src/domain/{metrics,query,ticketGrammar,taxonomy,dates,ids}.ts`
— 1,540 lines. `metrics.ts` alone is 669 lines and is the highest-value asset in that repo.

**Responsiveness: none.** One `@media` rule in 19k lines and it is `prefers-reduced-motion`. Zero
`matchMedia`, zero touch handlers. Structural blockers: `body{overflow:hidden}`; the shell grid
consumes 264px of chrome before content (644px with the inspector open); `DataGrid` is a fixed-pixel
column grid with a ~676px minimum plus mouse-drag resize/reorder; the year heatmap is `repeat(12,16px)`;
six flows use `window.prompt()`. Making all surfaces genuinely mobile is a 5–7 week job producing a
*second design*, not a responsive one — hence D2.

### 2.3 Kite

Already in place, verified in code:

- Every bot order is tagged `TAG = "pt-bot"` (`app/engine/live_broker.py:28`), applied at 5 placement
  sites (`:380`, `:436`, `:516`, `:632`, `:700`), reaching the wire at `kite_order_client.py:169-171`.
- Every placed order's broker `order_id` is recorded in `order_journal` (`app/db/models.py:615`),
  **indexed on `order_id`**, written before placement and stamped on ack (`order_executor.py:67-74`).
- The read routes needed are **already on the SafePaperKite allowlist** (`app/providers/safe_kite.py:57-58`):
  `orders`, `order.info`, `trades`, `order.trades`, `portfolio.positions`, `portfolio.holdings`.
  **This feature requires no change to the safety perimeter.**
- `live_broker.py:247-260` already runs the inverse sweep (tagged order with no journal row). The
  manual detector is its complement.

Three hard constraints:

1. **Kite's orderbook is same-day only.** No historical order/trade API beyond the current trading
   day. Anything not captured before ~midnight is gone from the API forever. → the detector must
   persist raw detections on first sight, and must run at least once near session close.
2. **GTT-fired stops carry no tag.** Zerodha creates the resulting order server-side and the GTT API
   has no tag field (`kite_order_client.py:89-103`). This is the one real hole in tag-based
   classification, and it affects the options/NRML book.
3. **HTTP postbacks are impossible.** The VPS is tailnet-only, backend bound to `127.0.0.1:8090`
   (`scripts/deploy.sh:30`). Zerodha's servers cannot reach it. Polling or `KiteTicker` only.

`kite.trades()`, `kite.order_trades()` and `kite.holdings()` are **never called today**. `KiteTicker`
is not used anywhere in the repo.

---

## 3. Architecture

### 3.1 Persistence — move the blob, do not rewrite the app

THE LEDGER persists as **one debounced JSON snapshot under one IndexedDB key**
(`src/data/idb.ts`: `DB_NAME='the-ledger'`, `STORE='snapshot'`, `KEY='db'`). All 43 mutators go
through a single write path, `mutate(label, fn)` in `src/data/store.ts`. Every business rule the
product depends on — the thesis lock and its blockers, off-book/no-thesis/over-limit auto-tagging,
regime inheritance at trade timestamp, playbook revision diffing, risk-envelope breach — lives inside
those closures.

**Therefore: we do not build 43 REST endpoints and reimplement those rules in Python.** We change
the storage target of one file.

```
GET  /api/journal/snapshot   → 200 { version: int, payload: <DB> }   (404 → client seeds)
PUT  /api/journal/snapshot   → If-Match: <version>
                               200 { version: version+1 }
                               409 on version mismatch
```

`src/data/idb.ts` becomes a thin HTTP client with the same `loadSnapshot`/`saveSnapshot`/`clearSnapshot`
signatures. `store.ts`, `actions.ts`, all 43 mutators, the undo/redo stack, and every surface are
**untouched**.

Backend: one table in a journal-owned SQLite DB.

```sql
CREATE TABLE journal_snapshot (
  id         INTEGER PRIMARY KEY CHECK (id = 1),
  version    INTEGER NOT NULL,
  payload    TEXT    NOT NULL,   -- JSON
  updated_at DATETIME NOT NULL
);
```

**Accepted costs, stated plainly:**

- *Last-write-wins across devices.* Mitigated by optimistic concurrency: a 409 tells the client its
  base version is stale and it reloads. For one user on two devices this is acceptable; a merge
  strategy is out of scope.
- *The blob must stay small.* `store.ts` `structuredClone`s the entire DB twice per mutation and
  holds up to 60 snapshots on the undo stack. Fine at the seed's ~173 trades; it is why §3.2 exists.
- *`schedulePersist()`'s 250ms debounce becomes a network write.* Raise to ~1.5s and make the
  existing `sync` state (`'saving' | 'synced' | 'offline' | 'error'`) reflect HTTP reality. The status
  dot already reports save state honestly — keep that true.

### 3.2 Screenshots leave the snapshot

`Artifact.data` is currently a **base64 data URL stored inside the snapshot blob**. With a 250ms
debounce, every save rewrites every screenshot. This is fine locally and untenable over HTTP.

```sql
CREATE TABLE journal_artifact (
  id         TEXT PRIMARY KEY,   -- LEDGER's uid()
  mime       TEXT NOT NULL,
  bytes      BLOB NOT NULL,
  created_at DATETIME NOT NULL
);
```

```
POST   /api/journal/artifacts        (multipart) → { id }
GET    /api/journal/artifacts/{id}   → the bytes, with a long cache header
DELETE /api/journal/artifacts/{id}
```

The snapshot keeps only `Artifact` metadata; `data` becomes the URL `/api/journal/artifacts/{id}`.
`Vault.tsx`'s `addArtifact` (FileReader → data URL) uploads first, then stores the id.
`deleteArtifact` deletes server-side.

**This is not optional.** Without it the snapshot reaches megabytes within a week of normal use.

### 3.3 Mounting — full-bleed, CSS scoped, keymap gated

`/journal` renders THE LEDGER's own shell at full viewport with its own materials (D1). Four
isolation problems, from the recon, each with its fix:

| Problem | Evidence | Fix |
|---|---|---|
| `base.css` resets `html,body,#root{height:100%}` and `body{overflow:hidden}` — breaks host page scrolling app-wide | `src/styles/base.css` | Move the reset off `body` onto `.ledger-root` |
| ~40 unscoped utility names (`.grid`, `.panel`, `.chip`, `.label`, `.num`, `.badge`, `.toast`, `.empty`, `.stat`, `.surface`) collide with Tailwind in **both** directions | `base.css` + 10 component CSS files, BEM-ish global classes, no hashing | Prefix every LEDGER selector under `.ledger-root` at build time via PostCSS |
| `useKeymap` installs one `window` keydown that `preventDefault`s bare `t/o/n/j/k/space/x/e/f/?//` and ⌘K/⌘E/⌘Z/⌘\/⌘./⌘1-9 — hijacks the host app | `src/keys/useKeymap.ts`, 393 lines, `[]` deps, no scope prop | Mount/unmount with the route so the listener exists only while the journal is on screen |
| `useAppearance` writes `document.documentElement.dataset.{theme,density,cvd}`, stomping host theming | `src/app/App.tsx` | Stamp the same attributes on `.ledger-root`; tokens already key off `:root[data-*]` and become `.ledger-root[data-*]` under the same prefixing pass |
| `store.ts` registers `window` online/offline listeners **at import time**, unconditionally | `src/data/store.ts` module scope | Acceptable — idempotent and cheap. Leave. |
| `Timeline.tsx` adds its own `wheel` (`passive:false`) and `keydown` listeners | `src/surfaces/Timeline.tsx` | Scoped to the surface's own mount; unmounts with the route |
| `App.tsx` hijacks `window.location.hash` via a `hashchange` listener | `src/app/App.tsx` | paper-trader has no router (a `useState` tab switcher, `App.tsx:47`), so there is nothing to fight. Namespace the hash to `#/journal/...` |

**Deleted on port:** `src/app/auth.ts` (110 lines of client-side fake login) and the credential
display in `Login.tsx`. The app already gates every `/api/*` route behind `Bearer PT_API_TOKEN`
(`main.py:134-158`). Keeping a second, fake gate that prints `admin/admin@123` on screen is worse
than no gate.

**Seed data:** `buildSeed()` is the default value of the module-level `db` and the fallback in
`boot()`, and `uiState` hard-codes `instrumentId: 'bnf'` as the initial route — with an empty DB,
eight surfaces `return null` and there is no UI anywhere to create an instrument. So the first-boot
path must seed **instruments, playbook and settings** (real, owner-relevant: Nifty, Bank Nifty, and
the MCX MINI contracts the owner actually trades) while seeding **zero trades and zero sessions**.
The demo's 173 generated trades are not shipped.

### 3.4 Kite manual-trade detection

Strictly **read-and-record**. It must never write `positions`/`trades`, and must never influence
`can_bot_close()` — `app/engine/reconcile.py` is the ownership boundary, and a detector bug that
reached it would become a real-money bug. Detections live in the journal DB, where the existing
package isolation (separate `DeclarativeBase`, separate engine, engine never imports the package)
already enforces the separation structurally.

```
 poll kite.orders() + kite.trades()   (~30s lane + a forced run near session close)
                  │
                  ▼
   classify(order, bot_order_ids, bot_gtt_ids) → pure function over dicts
                  │
      ┌───────────┼───────────────┬────────────────────┐
     BOT        MANUAL                            NEEDS_REVIEW
    (drop)   → journal_manual_fill            → journal_manual_fill, flagged
                  │
       LEDGER Inbox surface pulls unclaimed rows
                  │
       materialised through the existing addTrade() → broker fills in the Fact layer
```

**Classification rule, fail-closed:**

> An order is MANUAL iff `tag != "pt-bot"` **AND** `order_id ∉ order_journal` **AND** it is not
> attributable to a bot GTT for the same symbol/day.
> An order failing exactly one test is `NEEDS_REVIEW` — never silently either side.

**The GTT check needs a durable record it does not currently have.** `Position.gtt_trigger_id`
exists (`app/db/models.py:109`) but is **set to `None` on every exit path** (`live_broker.py:504`,
`:614`, `:850`, `:877`). A GTT that fires, closes the position and clears the id leaves nothing behind
to attribute the resulting order to — which is precisely the case the check must catch. So WS-2 must
either (a) record GTT trigger ids in a durable append-only table at placement time, or (b) treat *any*
untagged order matching a symbol the bot held that day as `NEEDS_REVIEW` rather than `MANUAL`.
Option (b) is cheaper and fail-closed; option (a) is more precise. Decide in the WS-2 plan —
do not build the check against the live `positions` row, which is the obvious wrong answer.

The asymmetry is deliberate: a bot trade mislabelled manual costs a confusing prompt; a manual trade
mislabelled bot silently corrupts the bot's P&L attribution. This mirrors the "flag, don't act"
convention already used at `reconcile.py:59-63` and `runner.py:1441-1448`.

The classifier is a **pure function over dicts** — no DB, no Kite, no I/O — so it is exhaustively
unit-testable against fixtures. This is the repo's strongest existing convention (`reconcile.py`).

```sql
CREATE TABLE journal_manual_fill (
  order_id      TEXT PRIMARY KEY,        -- UNIQUE ⇒ idempotent re-polling
  tradingsymbol TEXT NOT NULL,
  exchange      TEXT NOT NULL,
  product       TEXT,
  side          TEXT NOT NULL,           -- BUY | SELL
  qty           INTEGER NOT NULL,
  avg_price     REAL,
  order_ts      DATETIME,
  fill_ts       DATETIME,
  verdict       TEXT NOT NULL,           -- MANUAL | NEEDS_REVIEW
  raw           TEXT NOT NULL,           -- the whole Kite dict, for forensics
  claimed_trade TEXT,                    -- LEDGER trade id once materialised
  seen_at       DATETIME NOT NULL
);
```

```
GET  /api/journal/manual-fills?unclaimed=true   → rows for the Inbox
POST /api/journal/manual-fills/{order_id}/claim → { trade_id }
```

**Fill aggregation.** A single manual order can fill in tranches, and `kite.trades()` is the only
place tranche detail lives (`fill_timestamp`, per-tranche `average_price` — confirmed by the SDK's
`_format_response` datetime-field list, `kiteconnect/connect.py:448-462`). Rows are grouped by
`order_id`; BUY/SELL orders on the same symbol are then paired into round trips to fit
`Trade`'s `legs[]` shape. This is real work and is the largest single risk in WS-2.

**Scheduling.** A new async lane that **never takes `runner._lock`** — it touches a different
database entirely, so it genuinely does not need it. (The 2026-07-13 `risk_loop_stalled` incident was
a sweep holding the engine lock for 30s; do not repeat the shape.) No throttle category exists for
order/portfolio reads in `providers/kite.py:37-38`; 30s matches the `positions()` cadence that has
run in production without 429s. Do not invent a tighter one.

**Off-Kite behaviour.** `MockProvider` has no orders; the lane must no-op cleanly so the test suite
and `scripts/dryrun.py` stay green.

**Two facts to verify against one live authenticated call before building** — both cheap, both change
the design if they come back the wrong way:

1. Does `kite.trades()` echo the `tag` field? `orders()` demonstrably does (production code reads it
   at `kite_order_client.py:206`). If `trades()` does not, tag classification runs on `orders()` and
   joins to `trades()` by `order_id`.
2. Do `placed_by`/`guid` exist on the order object, and does `placed_by` differ between an API order
   and an app-placed one? If so that is a third independent signal and would plug the GTT hole.

**v2 (not in this spec):** `KiteTicker.on_order_update` (`kiteconnect/ticker.py:265,711-713`) fires
for **every** order on the account, including ones placed from the Zerodha app, and needs no
instrument subscription. It is the right long-term transport — "prompt me while I still remember" —
but it is a genuinely new subsystem (a second consumer of the daily token, a background thread,
reconnect handling) and is deferred.

### 3.5 Mobile capture shell

Four purpose-built screens under `.ledger-mobile`, below 768px — not a responsive port:

1. **Pending** — trades awaiting a reason. Thumb-sized rows, one tap to answer entry-why and exit-why.
2. **Capture** — quick observation / mistake / question, reusing `QuickCapture`'s inference rules.
3. **Today** — thesis read-only, append-only stream (`appendToSession`).
4. **Timeline** — read-only month view.

Everything else renders an honest "open this on your Mac" — the pattern `App.tsx:67-69` already uses
for Backtests. The prose surfaces (Review, Guide, PeriodReview) already sit at `max-width:68ch`
single-column and come along nearly free; they are a stretch goal, not a commitment.

The six `window.prompt()` flows (exit price ×2, tags ×2, level entry, doc title, regime why, query
name, artifact reparent) are replaced with inline controls on any path reachable from mobile.

---

## 4. Typography (WS-3)

**Root cause:** `frontend/src/index.css:11` is

```css
body { @apply bg-bg text-zinc-200 font-mono text-sm; }
```

The entire paper-trader UI is monospace at 14px — headings, labels, prose, all of it. That is the
whole problem.

Adopt frmp2's system (`/Users/priyanshusaraf/dev/frmp2/react-site/src/styles/style.css`):

```css
--font: "Geist Variable", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--mono: "Geist Mono Variable", ui-monospace, "SF Mono", Menlo, Consolas, monospace;

html { scroll-behavior: smooth; font-size: calc(16px * var(--font-scale, 1)); }
body { font-size: 1rem; line-height: 1.65; -webkit-font-smoothing: antialiased; }

h1,h2,h3,h4 { line-height: 1.25; font-weight: 650; letter-spacing: -0.015em; }
h1 { font-size: 1.9rem; }  h2 { font-size: 1.35rem; }  h3 { font-size: 1.08rem; }

/* micro-labels */  font-size: 0.72–0.78rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
/* tables */        font-size: 0.92rem;  th: 0.85rem / 650 / uppercase / 0.04em
```

Rules:

- **Sans for UI and prose. Mono reserved for numbers**, where `tabular-nums` earns it. Wire
  `fontFamily: { app: 'var(--font)', mono: 'var(--mono)' }` into `tailwind.config.js` as frmp2 does.
- **Self-hosted `@fontsource` woff2, no CDN.** The box is tailnet-only; an external font request
  would simply fail. frmp2 already ships Geist this way.
- `--font-scale` is applied before first paint from localStorage (frmp2's `index.html` inline script)
  and becomes a **Settings knob**, tying WS-3 to WS-4.
- The existing `@layer components` classes (`.card`, `.tile`, `.badge`, `.btn`, `.stat-label`,
  `.stat-value`, `index.css:42-49`) are re-expressed in the new scale so every un-migrated view moves
  with them.

This touches every view. It needs a screenshot pass across Dashboard / Trades / Watchlist / Portfolio
/ Engine / Calendar / Backtests / Settings at desktop and phone widths, not just a config edit.

**Exception:** the journal keeps its own glass/paper mono+serif language per D1. The break is intentional.

---

## 5. Settings (WS-4)

`frontend/src/views/SettingsView.tsx` — 145 lines, 67 knobs, 10 groups, rendered as one flat wall of
number inputs. The per-knob help text (`META`, `:10-67`) is genuinely good; what is missing is
hierarchy, safety tiering, and unit affordances.

Redesign:

- **Search/filter** across key, label and help text. At 67 knobs this is the single biggest win.
- **Collapsible groups**, collapsed by default, each showing an "N overridden" count so a drifted
  group is visible without opening it.
- **Danger tier, visually separated** from tuning knobs: `max_daily_loss`, `max_open_drawdown`,
  `bot_capital_cap`, `capital_reserve`, `gtt_stop_enabled`, `intraday_enabled`, and anything that can
  halt or unhalt trading.
- **Units as affordances.** A `_pct` knob renders `−30%`, not `0.30`; a `_minutes` knob renders
  `15 min`; a `₹` knob renders grouped Indian digits. The stored value is unchanged.
- **Current vs default inline**, with the `overridden` badge kept (`:101`) and the reset control
  given a real label rather than a chip.
- **Replace `window.alert(res.error)`** (`:91`) with an inline field error. Out-of-bounds rejection
  currently reverts the value and throws a modal.
- Preserve the honest framing already at `:130-131`: every value applies live, no restart.

Note for the plan, from CLAUDE.md: `runtime_config` DB overrides shadow code defaults, and production
currently overrides `intraday_max_positions` (4), `intraday_entry_cutoff_minutes` (60) and
`max_daily_loss` (2000). The redesign must make an override *visible*, because a silently shadowed
default has already cost this project time.

---

## 6. Workstreams

| | Workstream | Depends on | Size |
|---|---|---|---|
| **WS-1** | Delete old journal; port LEDGER; server snapshot; artifacts out of blob; CSS scoping; keymap gating; real seed | — | Large |
| **WS-2** | Kite detection lane; classifier; fill aggregation; Inbox reason capture; mobile capture shell | WS-1 | Large |
| **WS-3** | Typography overhaul, app-wide (journal excepted) | — | Small |
| **WS-4** | Settings redesign | WS-3 | Small |

WS-3 and WS-4 are fully independent of WS-1/WS-2 and can run in parallel from the start.

Each workstream gets its own implementation plan. WS-1 and WS-2 are specified together here because
WS-2's Inbox is meaningless without WS-1's store.

---

## 7. Testing

The frontend has **no test runner and no linter** — `npm run typecheck` (`tsc --noEmit`) is the only
gate (CLAUDE.md). THE LEDGER brings vitest and one 493-line domain test file. Position:

- **Port `domain.test.ts` as-is** and keep vitest for the journal. It is the only frontend test
  infrastructure this repo will have; it earns its place.
- **Add tests for `actions.ts`**, which today has none, covering the rules that D1 preserves: lock
  blockers, off-book/no-thesis/over-limit auto-tagging, regime inheritance, risk breach. These are
  the product's actual invariants and they are currently untested.
- **Backend**: the classifier gets exhaustive pure-function tests over Kite-shaped dicts, including
  every failure mode in §3.4 — untagged GTT fill, crash-orphaned `order_id=None`, tranche fills,
  same-symbol bot-and-manual overlap. Snapshot concurrency gets a 409 test.
- `scripts/dryrun.py 700` must stay green (hard invariant 1) and the new lane must no-op under the
  mock provider.
- Both suites run: `pytest tests research_tests` — `testpaths=tests` means bare `pytest` skips the
  research suite.

---

## 8. Consequence of D4, recorded once

D4 accepts reasoning written after the fact, with no capture-latency tracking and no post-hoc marking.

`metrics.ts` contains two analyses — `calibration` and thesis accuracy — that measure *belief stated
before the outcome was known*. Fed post-hoc reasons they will still render numbers, but those numbers
describe something different from what the panel names claim.

Resolution: keep both panels, label them honestly as to what they now measure, and stamp
`entryNoteLockedAt` at save time. Everything else in the engine — R distribution, expectancy grid,
exit quality, mistake ledger, adherence, behavioural sequences, the two ledgers — is unaffected,
because none of them depend on when the note was written.

---

## 9. Deployment notes

From `scripts/deploy.sh` and CLAUDE.md — these have each caused a production incident:

1. **`*.db` is excluded from rsync.** Any schema change must ship as *code* and self-apply. The
   journal already has the pattern: `init_journal_db()` → `migrate_journal_db()` with `PRAGMA table_info`
   column checks. `create_all` silently skips existing tables and is not a migration.
2. **`PT_JOURNAL_DB_PATH` must be pinned to an absolute path in the VPS `.env` before anything starts
   auto-writing rows.** It currently defaults to the bare relative `"journal.db"`, which lands wherever
   systemd's `WorkingDirectory` points — a restart under a different cwd would silently start a second,
   empty journal.
3. **`.env` is excluded from the deploy.** Any new env var must be added to the VPS `.env` by hand.
   This is the single most-repeated deploy failure in this repo's history.
4. **The SPA is built on the Mac** and shipped by a separate targeted rsync. Never build on the VPS —
   1GB droplet, has OOM'd twice.
5. **Verify with `GET /` as well as `/api/health`.** `/api/health` is a liveness stub that returned 200
   through both 2026-07 outages.
6. Deploy only via `scripts/deploy.sh` (hard invariant 6).

---

## 10. Explicitly out of scope

- `KiteTicker.on_order_update` real-time transport (§3.4 v2).
- Multi-device merge/CRDT sync. Optimistic concurrency with 409-and-reload only.
- OCR on screenshots — `Artifact.ocrText` stays empty, as in the source design.
- Timeline day-zoom price track — needs intraday data the journal does not hold.
- Making the Blotter, Research Bench or the Timeline year view usable on a phone.
- Any change to bot execution, sizing, or exits. The detector is read-only by construction.
