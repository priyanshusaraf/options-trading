# WS-08 — Cockpit UI (the trading dashboard)

**Status:** active
**Owner surface:** `frontend/` — all of it. `src/views/`, `src/components/`, `src/ledger/`,
`src/lib/`, `src/state/`, `index.css`, `tailwind.config.js`, `components.json`, `vite.config.ts`,
`vitest.config.ts`.
**Last verified:** 2026-08-03 · commit `cdbe686`

> This is the screen the owner actually looks at. It is a React + TypeScript SPA that renders
> everything the trading engine knows — open positions, the equity curve, the trade book, the
> watchlists, the backtests, the settings knobs, the engine logs and the readiness verdict — and
> is the only way to arm the bot, connect Kite each morning, and change a live parameter. It is
> shipped, deployed, and in daily production use: the VPS serves the built `dist/` at
> `https://paper-trader.taile25969.ts.net`, and "run the bot" means opening this app on a phone.

---

## 1. Vision

The cockpit answers three questions without an ssh session: **is it working right now**, **what
is it holding**, and **what is it about to do**. A pane that cannot answer one of those does not
earn its place.

"Done" is not a feature list — it is a standard. Every number on screen is either true or
visibly marked as unknown, and there is no third state. A stale reading renders as **Unknown**,
never as the last good value wearing a green badge, because a confidently wrong dashboard is
worse than a blank one: it is the failure mode that hid both 2026-07 outages, where a liveness
stub returned 200 through the whole incident. Every knob that governs real money is visible and
labelled in prose that says what happens if you move it, not merely what it is named. The layout
works one-handed at 390px, because the moment it matters most is closing a position from a phone.

Aesthetically: dense, monospace, chip-and-table, dark. Information per square inch is the metric.
The typography and palette pass is the one open piece of that and is deliberately last — the
numbers were made correct first.

## 2. Scope

**In scope.**

- Every view under `src/views/` — Dashboard, ActivePositions, Trades, Ledger, Portfolio,
  Watchlist, Backtests, Engine, Calendar, OptionsCalc, Settings, and their modals.
- The **live state layer**: `state/LiveContext.tsx` holds the single `/ws` connection and
  distributes engine state to the tree. One connection, one context — a second WebSocket
  anywhere in the app is a defect.
- The **REST client**: all HTTP goes through `lib/api.ts`. A `fetch` call outside it is a defect.
- Pure client-side domain logic that must not be re-derived on the server: `lib/health.ts`
  (readiness verdict presentation), `lib/format.ts`, `lib/settingFormat.ts`, `lib/liveSeries.ts`,
  `lib/storage.ts`, and the `src/ledger/domain/` module.
- The **settings surface** and its visibility guarantees — `views/settingsMeta.ts`,
  `views/overridable.ts`, `views/SettingsView.tsx`.
- shadcn primitives in `src/components/ui/`, the Tailwind theme, the CSS variables, typography.
- Mobile: `components/MobileTopBar.tsx`, `src/ledger/mobile/`, and the 390px layout guard.
- The frontend build and its checks: `npm run typecheck`, `npm test`, `npm run build`.

**Out of scope.**

- **The REST and WebSocket API itself** — the routes, their payload shapes, the broadcast hub.
  Owned by WS-02 Execution (`backend/app/api/routes.py`) and WS-07 Infrastructure
  (`backend/app/ws/manager.py`). This workstream consumes them and must not reshape a payload to
  suit a component; ask for the change there.
- **The readiness verdict logic.** `backend/app/engine/readiness.py` decides ok/degraded/down and
  `/api/health` answers 503 on a stale risk lane. `lib/health.ts` renders that verdict; it does
  not compute a second opinion.
- **Which settings exist and what they do.** `Settings` + `runtime_config` are backend
  (WS-02/WS-07). This workstream owns whether each one is *visible and explained*.
- **The visual graph editor.** WS-04 Editor. It will live inside this SPA and reuse these
  primitives, but its canvas, its route and its presentation-state persistence are that
  workstream's.
- **Research-plane UI.** WS-03 Research.
- **Serving `dist/`, the deploy, the tailnet, the SPA mount.** WS-06 Deployment / WS-07
  Infrastructure. Note the failure mode that binds them: `scripts/deploy.sh` builds the SPA
  **locally** and rsyncs `frontend/dist/` separately, because a Vite build on the 1GB droplet has
  OOM'd with the engine running. Never build on the VPS.

## 3. Interfaces

**Exports** — what other workstreams may depend on.

| Export | Guarantee |
|---|---|
| `frontend/dist/` | A static SPA bundle with **no CDN dependency** — everything is self-hosted, because the VPS serves the built output on a tailnet. WS-06 ships this directory; nothing else in `frontend/` is a deploy artefact. |
| `state/LiveContext.tsx` | Exactly one `/ws` connection for the whole app. Any new view consumes this context rather than opening its own socket. |
| `lib/api.ts` | The single REST surface. Every backend call in the app goes through it, so a change to auth, base URL or error handling has one site. |
| `views/overridable.ts` (`OVERRIDABLE`) | The list of settings keys the backend exposes as live-editable. It is the input to the settings-visibility tests — it must track the backend, and `settingsMeta.test.ts` fails the build when it does not. |
| `components/ui/*` | shadcn primitives. WS-04's editor should build on these rather than introduce a second component vocabulary. |

**Consumes**

| Consumed | From | Why |
|---|---|---|
| `GET /api/health` | WS-02 | Readiness. 503 when the DB is unreachable, the loops are stopped, or the fast risk lane is stale. Also carries `build.commit` / `build.branch` / `build.deployed_at`, which is how the app reports which build it is talking to. |
| `GET /api/status`, `/api/dashboard`, `/api/signals`, `/api/trades`, `/api/settings`, `POST /api/settings/reset`, `/api/event-risk`, backtest routes | WS-02 | Everything the views render. `POST /api/settings/reset` is the *only* sanctioned way to clear an override — it calls `refresh_params()` so the running engine picks the change up without a restart. Never offer a UI path that writes `runtime_config` any other way. |
| `/ws` broadcast | WS-07 (`app/ws/manager.py`) | Live engine state. The hub coalesces and bounds its queues; the client must tolerate dropped intermediate frames. |
| The `dist/` mount and tailnet URL | WS-06 | The app is only reachable because the backend mounts the SPA. A broken mount is invisible from `/api/health` — that is exactly how the `.env` outage hid — so a post-deploy check must curl `/`, not only `/api/health`. |

**Depends on:** WS-02 (REST payloads and the `/api/health` route, settings), WS-06 (the
`/api/health` *contract*, which WS-06 specifies because `deploy.sh` polls it), WS-07 (`/ws` hub).

**Blocked by:** the owner, for one item only — the **typography and palette extraction**. The
reference site `ag-website-git-main-match-up.vercel.app` sits behind Vercel deployment
protection, so the font names and palette values cannot be read without either a browser
extension with access or the owner simply supplying them. Nothing else is blocked.

**Currently blocking:** nothing today. It will block **WS-04 Editor**, which has no surface of
its own and is specified to live inside this SPA and reuse `lib/api.ts` and
`components/ui/`.

## 4. Completed

Newest first.

- **390px option-chain overflow fixed + a regression guard** — `c7026a9`, 2026-08-02.
  `views/mobileLayout.test.ts` (3 tests) walks every `src/views/*.tsx` source via
  `import.meta.glob(..., '?raw')` and fails if a raw `<table>` is added without a horizontal
  scroll wrapper. Doing the check found the app in better shape than the roadmap implied — there
  was already a `MobileTopBar` with drawer navigation and the dense tables already sat in scroll
  containers — with one exception: `OptionsCalcView`'s 6-column option chain, which pushed the
  whole page body sideways on a phone. **The lasting value is the regression guard, not the
  fix**: a table added later looks fine on the laptop it was written on, and nobody opens the
  phone until the morning they need to close a position from it. The test uses `import.meta.glob`
  rather than `node:fs` deliberately — the frontend tsconfig ships no Node types, and adding a
  dependency to run a lint-shaped test was the wrong trade. **Note precisely what this does not
  cover:** it is a source-level guard. The *one-handed check on the actual phone* is still
  unverified (§5).
- **System health panel** — `23d5b76`, 2026-08-01. The backend had reported DB reachability, both
  loop heartbeat ages, provider auth and candle-feed anomalies since the readiness probe landed,
  and **none of it was visible in the app** — answering "is it working right now?" meant ssh +
  curl. `components/SystemHealth.tsx` + `lib/health.ts` (pure, 14 tests) put it on the Engine
  view. Three judgement calls, all pinned by test because they are the parts that can mislead:
  a lane that has **never** beaten renders "never", not "0s" (which reads as "just now" — the
  exact inversion); an unreadable probe renders **Unknown**, never the last good verdict, because
  a stale green badge is worse than an honest question mark; and a stale lane is **red only when
  it is the lane that matters for money** (risk stale = stops not firing), amber otherwise. It
  polls on its own timer rather than riding the WS state — a health panel that only updates while
  the engine is well tells you nothing on the day it matters.
- **Settings-knob visibility guard** — 2026-08-01. Two drift modes had shipped, both of which
  hid a knob governing a bot trading real money. See §6 for the mechanism and §7 for the half
  that is structural rather than tested.
- **The ledger sub-application** (`src/ledger/`) — its own shell, block editor, data grid,
  command palette, quick capture, walkthrough, IndexedDB store and domain layer, with the
  heaviest test coverage in the frontend (`domain.test.ts` alone is 49 tests).

Verified 2026-08-03 at `cdbe686`:

```
$ cd frontend && npm test
 Test Files  10 passed (10)
      Tests  143 passed (143)
```

## 5. Active roadmap

Migrated from `docs/ROADMAP.md` "Workstream D — UI". Ordered; the topmost unchecked item is what
an implementation agent picks up.

- [ ] **Extract font + colour scheme from the owner's reference site.**
      `ag-website-git-main-match-up.vercel.app`, behind Vercel deployment protection — needs the
      Chrome extension or owner-supplied font names. **Fonts first; palette later.** This is the
      blocked item (§3, §8); it needs information, not code.
- [ ] **Apply fonts app-wide.** Self-host via `@fontsource/*` — the VPS serves the built dist on
      a tailnet, so a CDN font is not merely a preference issue, it is a dependency that will not
      resolve. Wire into `tailwind.config.js` (`theme.extend.fontFamily`, currently only
      `mono: ['ui-monospace','SFMono-Regular','Menlo','monospace']`) and `index.css` (whose
      `body` rule is `@apply bg-bg text-zinc-200 font-mono text-sm`). Keep the established
      chip/dense-table conventions — see the header comment in `views/WatchlistView.tsx`.
- [ ] **Palette pass, after fonts.** Map onto the existing shadcn CSS variables
      (`--background`, `--card`, `--radius`, …) that `tailwind.config.js` already reads through
      `hsl(var(--…))`. **`muted` is a load-bearing Tailwind colour — merge, don't replace.**
- [ ] **Mobile 390px one-handed check on the actual phone.** Still never verified. The extension
      cannot reflow the viewport and `mobileLayout.test.ts` is a source-level guard, not a
      rendering. What is being checked: can every action needed to close a position be reached
      with one thumb, without horizontal scroll, on a 390px-wide screen.

## 6. Acceptance criteria

From `frontend/`, all three, every change:

```bash
npm run typecheck    # tsc --noEmit
npm test             # vitest — 143 passing at cdbe686
npm run build
```

Plus, specific to this workstream:

- **The settings-knob visibility guard must stay green and must stay strict.**
  `views/settingsMeta.test.ts` (7 tests) fails the build when: a key in `OVERRIDABLE` has no
  `META` entry (it would render as its raw key); a `META` entry names a key the backend no longer
  exposes; a `DANGER_KEYS` entry is not a real overridable knob; a knob has no `detail`; `detail`
  merely repeats `help`; `detail` is under 40 characters; or a `label` is identical to the key.
  The rule behind all seven: a knob that moves real money must say what happens when you move it,
  in the direction you would move it.
- **Keep the `['Other', () => true]` catch-all at the end of `GROUPS` in `SettingsView.tsx`.**
  Its comment states the rule — *an unclaimed key is an invisible key*. The profit-lock knob
  matched no group and rendered **nowhere** while still governing a live bot. This is the other
  drift mode, and it is guarded structurally by the catch-all rather than by a test (§7).
- **A live-money reading may never render a stale value as if it were fresh.** Unknown is a
  first-class state. `lib/health.ts` is the reference implementation; new panels follow it.
- Any new backend call goes through `lib/api.ts`; any new live subscription goes through
  `LiveContext`.
- Do not build on the VPS. `scripts/deploy.sh` builds `dist/` locally and ships it.

## 7. Known technical debt

- **The invisible-key drift mode is guarded by a comment, not a test.** `settingsMeta.test.ts`
  covers the *raw key* mode (no `META` entry) thoroughly, but no test asserts that every
  `OVERRIDABLE` key matches a `GROUPS` predicate — the guarantee rests entirely on the
  `['Other', () => true]` catch-all continuing to exist. Cost of leaving it: a future refactor
  that "tidies up" the catch-all silently reintroduces the exact defect that produced an
  invisible profit-lock knob on a live bot. Trigger: any edit to `GROUPS`. The fix is small —
  assert every `OVERRIDABLE` key is claimed by some group, with the catch-all removed.
- **`views/overridable.ts` is a hand-maintained mirror of the backend's overridable key set.**
  It drifts silently until `settingsMeta.test.ts` catches the mismatch, and it only catches it
  after someone updates one side. Trigger: a knob added backend-side that nobody mirrors.
- **`lib/health.ts` re-expresses readiness semantics client-side.** It is pure and tested (14
  tests), and it is still a second reading of a verdict `app/engine/readiness.py` already
  computes. Two hand-written implementations of one idea is the shape that produced the
  `candles.py` defect. Cost: low while the backend sends a verdict and the client only presents
  it. Trigger: the client ever *deciding* rather than presenting.
- **No end-to-end or component-render tests.** Everything green is pure logic plus a
  source-scanning lint test; no view is ever mounted in CI. A view can be structurally broken
  with the suite fully green. Trigger: the first regression that ships past a green suite.

## 8. Blockers

- **Reference-site typography and palette are unreadable** — `ag-website-git-main-match-up.vercel.app`
  is behind Vercel deployment protection. Resolvable only by the owner: supply the font names and
  palette values, or grant access. This blocks the top three roadmap items in order.
- **The 390px one-handed check needs the physical phone.** Not resolvable from a laptop; the
  extension cannot reflow the viewport.

## 9. Future work

- **Component-render tests** (Testing Library or Playwright). Trigger: the first user-visible
  regression that a green suite let through.
- **A host for WS-04's graph canvas** — route, layout shell, reuse of `components/ui/`. Trigger:
  WS-04's first roadmap item starting.
- **Surfacing `build.commit` in the UI**, not just in `/api/health`. Deployment state is already
  answerable in one curl; putting it on screen removes the curl. Trigger: the next time someone
  asks "is this the new build?" and answers it from prose.
- **An override-vs-default diff view.** The Settings screen already flags an override whose value
  differs from the shipped default in amber; a single screen listing all ten current divergences
  would make the operating configuration legible at a glance. Trigger: an eleventh override, or
  the next time a doc and the box disagree.
