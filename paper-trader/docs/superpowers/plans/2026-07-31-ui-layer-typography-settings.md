# UI Layer: Typography + Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the app-wide monospace-at-14px UI with frmp2's self-hosted Geist sans/mono type system where mono is reserved for numbers, then rebuild the 67-knob Settings wall as a searchable, collapsible, unit-aware panel with a visible override state and an inline `--font-scale` control.

**Architecture:** Typography is delivered as CSS custom properties (`--font`, `--mono`, `--font-scale`) declared in `frontend/src/index.css`, surfaced to Tailwind as the `font-app` / `font-mono` / `font-sans` families plus three rem-based micro sizes, and applied through the existing `@layer components` legacy classes (`.card .tile .badge .btn .stat-label .stat-value`) so every un-migrated view moves with them. The mono→sans flip is made safe by one lever: every numeric cell in this codebase already carries the literal `tabular-nums` class, so a single `[class~="tabular-nums"] { font-family: var(--mono) }` rule keeps the numbers mono while prose and chrome go sans. Settings is then rebuilt on top of that scale as a client-side filtered, grouped view over the unchanged `GET/POST /api/settings` contract, with one additive backend field (`overridden`) so a DB-shadowed default is visible without inference.

**Tech Stack:** React 18.3 + TypeScript 5.5 + Vite 5.3 + Tailwind 3.4 (preflight ON) + shadcn/ui primitives + `@fontsource-variable/geist` / `@fontsource-variable/geist-mono`; FastAPI + SQLAlchemy on the backend (`app/core/runtime_config.py`), pytest for the one backend change.

## Global Constraints

- Mobile/desktop split is a **JS breakpoint at 768px** in `frontend/src/App.tsx:32-44` (`window.matchMedia('(min-width: 768px)')`) swapping `TopBar`/`MobileTopBar`. Do not add a second, different breakpoint; any new responsive rule uses Tailwind's `md:` prefix, which is also 768px.
- The frontend has **NO test runner and NO linter**. The only gates are `npm run typecheck` (`tsc --noEmit`) and `npm run build`, both run from `paper-trader/frontend/`. Do not add vitest, jest, eslint or prettier in this workstream.
- **Fonts must be self-hosted/bundled.** The production box is tailnet-only; a CDN font request fails outright. Use the `@fontsource-variable/*` npm packages imported from `src/main.tsx`, exactly as frmp2 does in `react-site/src/main.jsx:5-6`. Never add a `<link>` to fonts.googleapis.com or any external host.
- **The dual palette in `frontend/tailwind.config.js` must keep working.** Legacy tokens (`bg panel panel2 edge up down muted`) and additive shadcn HSL-var tokens coexist; `muted` is MERGED (`{ DEFAULT: '#8b93a7', foreground: 'hsl(var(--muted-foreground))' }`), not replaced. Do not remove, rename, or re-point any existing colour token — un-migrated views depend on them.
- **The journal is excluded.** `frontend/src/views/JournalView.tsx` keeps its own visual language per spec §4's exception and decision D1. Do not edit it in any task in this plan.
- **Commit only when the owner asks.** Every task below ends with an exact `git add` + `git commit` command; run it only on explicit instruction. Working branch is `feat/exec-completeness`.
- **Deploy only via `scripts/deploy.sh`** (hard invariant 6), run from `paper-trader/`. Never bare-rsync.
- **Never build the SPA on the VPS.** `scripts/deploy.sh` runs `npm run build` on the Mac and ships `frontend/dist/` in a separate targeted rsync. The droplet is 1GB and has OOM'd twice.
- Backend behaviour is out of scope except the single additive `overridden` field in `runtime_config.schema()` (Task 6). No change to engine, sizing, exits, bounds, or the `OVERRIDABLE` tuple.
- The dev server binds to the Tailscale interface (`vite.config.ts` `HOST = '100.120.27.71'`). Visual checks are at **`http://100.120.27.71:5173`**, or run `VITE_HOST=127.0.0.1 npm run dev` and use `http://127.0.0.1:5173`.

---

## File Structure

| File | Created / Modified | Responsibility |
|---|---|---|
| `frontend/package.json` | Modified | Adds `@fontsource-variable/geist` and `@fontsource-variable/geist-mono` dependencies. |
| `frontend/src/main.tsx` | Modified | Imports the two woff2 font packages before `./index.css` so the `@font-face` rules are bundled. |
| `frontend/src/index.css` | Modified | Declares `--font`, `--mono`, `--font-scale`; sets `html`/`body`/heading/table base type; adds the `[class~="tabular-nums"]` mono rule; re-expresses `.card .tile .badge .btn .stat-label .stat-value`; adds `.title-page .title-section .title-sub .num`. |
| `frontend/tailwind.config.js` | Modified | Adds `fontFamily: { app, mono, sans }` bound to the CSS vars, and `fontSize: { micro, nano, pico }` in rem so they track `--font-scale`. |
| `frontend/index.html` | Modified | Inline pre-paint script that reads `pt.ui.v1` from localStorage and stamps `--font-scale` on `<html>` before first paint. |
| `frontend/src/lib/appearance.ts` | **Created** | `FontScale` type, `FONT_SCALES`, `readFontScale()`, `applyFontScale()` — the single source of truth for the localStorage key and the CSS variable. |
| `frontend/src/lib/knobFormat.ts` | **Created** | `formatKnobValue(key, value, type)` — the pure unit-affordance formatter (percent sign convention, `min`/`s`/`d` suffixes, `₹` Indian grouping, zero-sentinel labels, weekday names). |
| `frontend/src/lib/settingsMeta.ts` | **Created** | `META` (label + help per knob, moved out of the view and extended to cover every `OVERRIDABLE` key), `GROUP_DEFS` (ordered groups with `danger` tier), `groupOf(key)` with a catch-all so no knob is invisible. |
| `frontend/src/lib/types.ts` | Modified | `SettingRow` gains the `overridden: boolean` field. |
| `frontend/src/views/SettingsView.tsx` | Rewritten | Search box, collapsible groups with per-group override counts, danger tier, inline field errors, current-vs-default, labelled reset, Appearance card hosting the font-scale knob. |
| `frontend/src/views/WatchlistView.tsx` | Modified | Moves the row-level `tabular-nums` onto the numeric cells so the mixed-content row goes sans; micro-size class migration. |
| `frontend/src/components/LogStream.tsx` | Modified | Pins the log body to `font-mono`; micro-size class migration. |
| `frontend/src/views/PortfolioView.tsx` | Modified | Pins the generated-Python `<pre>` to `font-mono`; micro-size class migration. |
| `frontend/src/views/CalendarView.tsx` | Modified | Day-number and weekday-header digits get `tabular-nums`; micro-size class migration. |
| `frontend/src/views/{ActivePositionsView,TradesView,EngineView,DashboardView,BacktestsView,BulkAddModal,OptionsCalcView}.tsx`, `frontend/src/components/{TopBar,MobileTopBar}.tsx`, `frontend/src/components/ui/badge.tsx` | Modified | Mechanical `text-[11px]`→`text-micro`, `text-[10px]`→`text-nano`, `text-[9px]`→`text-pico` migration so every size tracks `--font-scale`. |
| `backend/app/core/runtime_config.py` | Modified | `schema()` emits an additive `"overridden": bool` per row. |
| `backend/tests/test_runtime_config.py` | Modified or **Created** | One pytest asserting `overridden` is `True` only when a `runtime_config` row exists, including the same-as-default case. |

**Files deliberately NOT touched:** `frontend/src/views/JournalView.tsx` (journal exception), every other `backend/app/**` module, `scripts/deploy.sh`, `backend/app/api/routes.py`.

---

### Task 1: Self-host Geist and declare the type tokens (no visual change yet)

**Files:**
- Modify: `frontend/package.json:12-28` (dependencies block)
- Modify: `frontend/src/main.tsx:1-5`
- Modify: `frontend/src/index.css:8-38` (`@layer base`)
- Modify: `frontend/tailwind.config.js:42-44` (`fontFamily`)
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Produces CSS custom properties: `--font`, `--mono`, `--font-scale` (declared on `:root` in `index.css`).
- Produces Tailwind families: `font-app`, `font-mono`, `font-sans`.
- Consumes: nothing.

- [ ] **Step 1: Install the two font packages.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend
npm install @fontsource-variable/geist@^5.3.0 @fontsource-variable/geist-mono@^5.3.0
```
This must be run on the Mac with network access; it writes woff2 files into `node_modules` which Vite then bundles into `dist/assets`. Confirm the packages landed:
```bash
ls node_modules/@fontsource-variable/geist/files/*.woff2 | head -3
ls node_modules/@fontsource-variable/geist-mono/files/*.woff2 | head -3
```

- [ ] **Step 2: Import the fonts from `main.tsx`, before the stylesheet.**

Replace the whole of `frontend/src/main.tsx` with:
```tsx
import { createRoot } from 'react-dom/client'
// Self-hosted Geist woff2 (mirrors frmp2 react-site/src/main.jsx). The production
// box is tailnet-only: an external font request would simply fail, so these MUST
// stay npm packages bundled by Vite and must never become a CDN <link>.
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(<App />)
```

- [ ] **Step 3: Declare the font custom properties in `index.css`.**

In `frontend/src/index.css`, inside the existing `:root` block in `@layer base`, add the three properties immediately after the opening brace, above `--background`:
```css
  :root {
    /* ── typography (adopted from frmp2 react-site/src/styles/style.css) ──
       The family names below are exactly what @fontsource-variable/geist and
       @fontsource-variable/geist-mono register. Sans is for UI and prose; mono
       is reserved for numbers, where tabular-nums earns it. */
    --font: "Geist Variable", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --mono: "Geist Mono Variable", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    /* Settings-controlled text size. Every rem in the app is relative to this
       (see the `html` rule below), and index.html stamps the stored value on
       <html> before first paint so there is no flash. */
    --font-scale: 1;

    --background: 220 17% 4%;      /* = #0a0b0e, the existing `bg` */
```

- [ ] **Step 4: Bind the families into Tailwind.**

In `frontend/tailwind.config.js`, replace the `fontFamily` block:
```js
      fontFamily: {
        // Bound to the CSS custom properties declared in src/index.css so the
        // family can be swapped in one place. `app` is the spec's name for the
        // UI/prose face; `sans` aliases it so shadcn primitives and any stray
        // `font-sans` resolve to Geist rather than the Tailwind default stack.
        app: 'var(--font)',
        sans: 'var(--font)',
        mono: 'var(--mono)',
      },
```

- [ ] **Step 5: Verify — build passes and Geist is actually bundled.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
ls dist/assets | grep -i geist | head -5
```
Expect `tsc --noEmit` silent, `vite build` reporting `built in …`, and at least two `geist-*.woff2` files in `dist/assets`. If the `grep` is empty, the `main.tsx` imports did not take — fix before continuing.

- [ ] **Step 6: Visual check — nothing has changed yet.**
Run `npm run dev`, open `http://100.120.27.71:5173`, view **Watchlist** and **Trade Log**. The whole app must still render monospace at 14px exactly as before this task: `body` still says `font-mono text-sm`, so this task is intentionally invisible. If anything moved, a token was mis-bound.

- [ ] **Step 7: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx frontend/src/index.css frontend/tailwind.config.js && git commit -m "feat(ui): self-host Geist and declare --font/--mono/--font-scale tokens"
```

---

### Task 2: Rem-based micro sizes so every size tracks `--font-scale`

**Files:**
- Modify: `frontend/tailwind.config.js` (add `fontSize` to `theme.extend`)
- Modify: `frontend/src/views/ActivePositionsView.tsx`, `TradesView.tsx`, `CalendarView.tsx`, `EngineView.tsx`, `PortfolioView.tsx`, `DashboardView.tsx`, `WatchlistView.tsx`, `BacktestsView.tsx`, `SettingsView.tsx`, `BulkAddModal.tsx`; `frontend/src/components/LogStream.tsx`, `TopBar.tsx`, `MobileTopBar.tsx`, `ui/badge.tsx`
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: `--font-scale` (Task 1).
- Produces Tailwind size utilities: `text-micro` (0.6875rem ≈ 11px), `text-nano` (0.625rem ≈ 10px), `text-pico` (0.5625rem ≈ 9px).

**Why:** `text-[11px]`, `text-[10px]` and `text-[9px]` are absolute pixels. They would not respond to `--font-scale` at all, which would make the WS-4 font-scale knob silently do nothing to the app's densest labels. There are 53 `text-[11px]` (4 of them inside the excluded `JournalView.tsx`), 6 `text-[10px]` and 2 `text-[9px]` — so **57** occurrences get migrated and 4 stay put.

- [ ] **Step 1: Add the three sizes to Tailwind.**

In `frontend/tailwind.config.js`, inside `theme.extend`, directly after the `fontFamily` block added in Task 1:
```js
      fontSize: {
        // Rem, not px, so these track html{font-size: calc(16px * var(--font-scale))}.
        // Values are the previous hard-coded pixel sizes at scale 1: 11/10/9px.
        micro: ['0.6875rem', { lineHeight: '1rem' }],
        nano: ['0.625rem', { lineHeight: '0.875rem' }],
        pico: ['0.5625rem', { lineHeight: '0.75rem' }],
      },
```

- [ ] **Step 2: Migrate every hard-coded micro size EXCEPT the journal.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend/src
FILES=$(grep -rl 'text-\[11px\]\|text-\[10px\]\|text-\[9px\]' views components | grep -v 'JournalView.tsx')
echo "$FILES"
for f in $FILES; do
  perl -pi -e 's/text-\[11px\]/text-micro/g; s/text-\[10px\]/text-nano/g; s/text-\[9px\]/text-pico/g' "$f"
done
```
Expected `$FILES`: `views/ActivePositionsView.tsx views/TradesView.tsx views/CalendarView.tsx views/EngineView.tsx views/PortfolioView.tsx views/DashboardView.tsx views/WatchlistView.tsx views/BacktestsView.tsx views/SettingsView.tsx views/BulkAddModal.tsx components/LogStream.tsx components/TopBar.tsx components/MobileTopBar.tsx components/ui/badge.tsx` (order may differ).

- [ ] **Step 3: Prove the migration is complete and the journal is untouched.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend/src
echo "remaining outside journal (must be 0):"; grep -rn 'text-\[11px\]\|text-\[10px\]\|text-\[9px\]' views components | grep -v JournalView | wc -l
echo "journal untouched (must be 4):"; grep -c 'text-\[11px\]' views/JournalView.tsx
echo "new classes present (must be 57):"; grep -rho 'text-micro\|text-nano\|text-pico' views components | wc -l
```

- [ ] **Step 4: Verify.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
```

- [ ] **Step 5: Visual check — pixel-identical.**
Open `http://100.120.27.71:5173`, view **Engine / Logs** and **Backtests**. Every small label must render at exactly the same size as before (11px/10px/9px at `--font-scale: 1`). This task is another intentionally invisible one; a visible size shift means a rem value is wrong.

- [ ] **Step 6: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/tailwind.config.js frontend/src/views frontend/src/components && git commit -m "refactor(ui): rem-based micro/nano/pico sizes so all type tracks --font-scale"
```

---

### Task 3: The migration — flip `body` off `font-mono` (RISKY, sequenced)

**Files:**
- Modify: `frontend/src/index.css:8-47` (`@layer base` + `@layer components`)
- Modify: `frontend/src/views/WatchlistView.tsx:293,306`
- Modify: `frontend/src/components/LogStream.tsx:52`
- Modify: `frontend/src/views/PortfolioView.tsx:81`
- Modify: `frontend/src/views/CalendarView.tsx:114,128`
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: `--font`, `--mono`, `--font-scale` (Task 1); `text-micro`/`text-nano`/`text-pico` (Task 2).
- Produces component classes: `.title-page`, `.title-section`, `.title-sub`, `.num`; and the re-expressed `.card`, `.tile`, `.badge`, `.btn`, `.stat-label`, `.stat-value`.

**This is the risky step.** Read the whole regression table below before editing anything.

#### What regresses when `body` loses `font-mono`, and how each is fixed — all inside this task

| # | Surface | What breaks | Fix (in this task) |
|---|---|---|---|
| 1 | Every numeric cell that already carries the literal class `tabular-nums` (35 sites across TradesView, EngineView, DashboardView, BacktestsView, OptionsCalcView, BulkAddModal, InstrumentDetailModal, ActivePositionsView, TopBar, MobileTopBar, WatchlistView, SettingsView) | Would go proportional and lose column alignment | Step 2's `[class~="tabular-nums"] { font-family: var(--mono) }` rule — they stay mono automatically, no per-view edit |
| 2 | `WatchlistView.tsx:293` — `tabular-nums` sits on the whole `<TableRow>`, which also holds instrument names, badges and a `<select>` | Rule #1 would keep the ENTIRE mixed-content row monospace | Step 4: remove `tabular-nums` from the row, add it to the numeric `z` cell at `:306` |
| 3 | `LogStream.tsx:52` — the log body has no `tabular-nums` | Engine log output would render proportional; log lines are terminal output and must stay mono | Step 5: add `font-mono` to the scroll container |
| 4 | `PortfolioView.tsx:81` — the generated-Python `<pre>` has no `tabular-nums` | Source code would render proportional | Step 6: add `font-mono` |
| 5 | `CalendarView.tsx:114,128` — weekday headers and day numbers have no `tabular-nums` | Day digits in the 7-column grid would go proportional and jitter | Step 7: add `tabular-nums` to both |
| 6 | `DashboardView.tsx:250`, `OptionsCalcView.tsx:65` — already explicitly `font-mono` | Nothing; `font-mono` now resolves to `var(--mono)` | none |
| 7 | `.stat-value` (`index.css:46`) uses `@apply tabular-nums`, which does NOT put the literal class in the DOM, so rule #1 misses it | Every TopBar/tile stat number would go proportional | Step 3: `.stat-value` gains an explicit `font-mono` in its `@apply` |
| 8 | `thead th` across TradesView, EngineView, DashboardView, OptionsCalcView, BulkAddModal, BacktestsView, WatchlistView | Header casing changes to uppercase with letterspacing (this is the intended new look) | Step 2's `thead th` rule; confirm in the screenshot pass, no per-view edit |
| 9 | `body` font-size goes from `text-sm` (0.875rem) to `1rem`, line-height to 1.65 | Any text WITHOUT an explicit size class grows ~14%; dense grids mostly carry `text-xs`/`text-micro` and are unaffected | Step 2 adds `table { line-height: 1.45 }` to keep grids tight; anything still too airy is fixed in Task 5's screenshot pass |
| 10 | `frontend/src/views/JournalView.tsx` | Would inherit sans like everything else | **Excluded by spec §4 / decision D1.** Do not edit it. It is the old journal and WS-1 deletes it; leaving it inheriting the new body font is acceptable and explicitly out of scope here. |

- [ ] **Step 1: Change the `body` rule.**

In `frontend/src/index.css`, replace line 11:
```css
  body { @apply bg-bg text-zinc-200 font-mono text-sm; }
```
with:
```css
  /* The single line that made the entire cockpit monospace at 14px. Sans is now
     the UI and prose face; mono is reserved for numbers (see the tabular-nums
     rule in @layer components below). */
  body {
    @apply bg-bg text-zinc-200 font-app;
    font-size: 1rem;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }
```

- [ ] **Step 2: Add the `html` scale hook, the heading scale, and the table rules.**

In `frontend/src/index.css`, inside `@layer base`, directly after the `* { @apply border-border; }` line and before the new `body` rule, insert:
```css
  /* Every rem in the app is relative to this, so the Settings text-size knob
     scales body copy, headings, micro-labels and tables together. */
  html { font-size: calc(16px * var(--font-scale, 1)); }

  h1, h2, h3, h4 { line-height: 1.25; font-weight: 650; letter-spacing: -0.015em; }
  h1 { font-size: 1.9rem; }
  h2 { font-size: 1.35rem; }
  h3 { font-size: 1.08rem; }

  /* Body line-height 1.65 is right for prose and far too airy for a 12-column
     ops grid, so tables opt back down. Header treatment follows the spec but is
     sized in `em`, NOT the spec's 0.85rem: every table in this app sets its own
     size (text-xs / text-micro) on the <table>, and an absolute rem here would
     ENLARGE headers past their own body rows. */
  table { line-height: 1.45; }
  thead th { font-weight: 650; text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.92em; }
```

- [ ] **Step 3: Re-express the legacy component classes in the new scale, and add the new ones.**

Replace the whole `@layer components` block in `frontend/src/index.css`:
```css
@layer components {
  .card { @apply bg-panel border border-edge rounded-lg; }
  .tile { @apply bg-panel border border-edge rounded-lg p-3 flex flex-col gap-2; }
  .badge { @apply text-nano uppercase tracking-wide px-1.5 py-0.5 rounded font-semibold; }
  .btn { @apply px-2.5 py-1 rounded border border-edge bg-panel2 hover:border-zinc-500 text-xs transition-colors; }
  /* Micro-label, per the spec's 0.72–0.78rem / 700 / 0.09em uppercase recipe. */
  .stat-label { @apply text-micro uppercase text-muted font-bold; letter-spacing: 0.09em; }
  /* @apply does NOT put a literal `tabular-nums` class in the DOM, so the
     attribute rule below cannot see it — the font-mono here is load-bearing. */
  .stat-value { @apply text-lg font-semibold font-mono tabular-nums; }

  /* Heading scale for views that need real headings. Named `title-*` rather than
     `h-*` so nothing collides with Tailwind's height utilities. */
  .title-page { @apply font-semibold text-zinc-100; font-size: 1.9rem; line-height: 1.25; letter-spacing: -0.015em; }
  .title-section { @apply font-semibold text-zinc-100; font-size: 1.35rem; line-height: 1.25; letter-spacing: -0.015em; }
  .title-sub { @apply font-semibold text-zinc-100; font-size: 1.08rem; line-height: 1.3; letter-spacing: -0.01em; }

  /* Explicit opt-in for new numeric code. */
  .num { @apply font-mono tabular-nums; }

  /* THE migration lever. Every numeric cell in this codebase already opted into
     `tabular-nums`, so this one rule keeps 35 sites monospace while prose and
     chrome go sans. It lives in @layer components, BELOW @layer utilities, so a
     view can still override with an explicit `font-app`. Attribute form (not
     `.tabular-nums`) is used so it only matches the literal DOM class and never
     an @apply'd one — see .stat-value above. */
  [class~="tabular-nums"] { font-family: var(--mono); }
}
```

- [ ] **Step 4: Fix regression #2 — WatchlistView's mixed-content row.**

In `frontend/src/views/WatchlistView.tsx`, change line 293 from:
```tsx
                className={cn('border-t border-edge tabular-nums cursor-pointer hover:bg-panel2/50',
```
to:
```tsx
                // `tabular-nums` deliberately does NOT live on the row: index.css maps
                // that class to the mono face, and this row also holds instrument
                // names, badges and a <select>. It sits on the numeric cell instead.
                className={cn('border-t border-edge cursor-pointer hover:bg-panel2/50',
```
and change line 306 from:
```tsx
                <TableCell className="text-right">{num(r.z)}</TableCell>
```
to:
```tsx
                <TableCell className="text-right tabular-nums">{num(r.z)}</TableCell>
```

- [ ] **Step 5: Fix regression #3 — the engine log stays mono.**

In `frontend/src/components/LogStream.tsx`, line 52, change:
```tsx
      <div ref={ref} className="flex-1 overflow-auto text-micro leading-relaxed space-y-0.5" style={{ maxHeight: '74vh' }}>
```
to:
```tsx
      {/* Terminal output: mono is not decoration here, it keeps timestamps and
          bracketed instrument tags in fixed columns. */}
      <div ref={ref} className="flex-1 overflow-auto font-mono text-micro leading-relaxed space-y-0.5" style={{ maxHeight: '74vh' }}>
```
(Note the class is already `text-micro` after Task 2.)

- [ ] **Step 6: Fix regression #4 — generated Python stays mono.**

In `frontend/src/views/PortfolioView.tsx`, line 81, change:
```tsx
            <pre className="bg-panel2 border border-edge rounded p-2 text-micro overflow-x-auto text-zinc-300">
```
to:
```tsx
            <pre className="bg-panel2 border border-edge rounded p-2 font-mono text-micro overflow-x-auto text-zinc-300">
```

- [ ] **Step 7: Fix regression #5 — calendar digits stay aligned.**

In `frontend/src/views/CalendarView.tsx`, line 114, change:
```tsx
      <div className="grid grid-cols-7 gap-1 text-pico text-muted mb-1">
```
to:
```tsx
      <div className="grid grid-cols-7 gap-1 text-pico text-muted mb-1 tabular-nums">
```
and line 128, change:
```tsx
              <span className="absolute inset-0 flex items-center justify-center text-pico text-zinc-200/90 font-medium">{dnum}</span>
```
to:
```tsx
              <span className="absolute inset-0 flex items-center justify-center text-pico text-zinc-200/90 font-medium tabular-nums">{dnum}</span>
```

- [ ] **Step 8: Verify the build.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
```

- [ ] **Step 9: Visual check — the load-bearing one.**
Run `npm run dev` and open `http://100.120.27.71:5173`. Confirm, in this order:
1. **Trade Log** — the column headers read `EXIT TIME`, `UNDERLYING`, `NET P&L` in uppercase sans with visible letterspacing; the `Net P&L`, `Spot %` and `Option %` columns are still monospace with digits in fixed columns; the `Reason` column (`sl_hit`, `target`) is now sans.
2. **Watchlist** — instrument names, the `INTRA`/`OPT` chips and the strategy `<select>` are all sans; only the `z` column is mono. The row must NOT be monospace end to end.
3. **Engine / Logs** — the live log pane is still fully monospace and its timestamps line up.
4. **Dashboard** — the TopBar `Equity` / `Realized P&L` figures are mono; the `Equity` / `Realized P&L` labels above them are uppercase sans micro-labels.
5. **Calendar** — the 7-column day grid digits are evenly spaced, no jitter between `11` and `22`.
6. **Portfolio** (only if `PT_RESEARCH_ENABLED=1`; skip otherwise) — "View generated Python" renders monospace.
7. Resize the browser below 768px and repeat 1–4 against `MobileTopBar`: the stat strip figures stay mono, the drawer nav labels are sans.

- [ ] **Step 10: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/src/index.css frontend/src/views/WatchlistView.tsx frontend/src/views/PortfolioView.tsx frontend/src/views/CalendarView.tsx frontend/src/components/LogStream.tsx && git commit -m "feat(ui): sans for UI and prose, mono reserved for numbers"
```

---

### Task 4: Apply the heading scale to the section titles that need it

**Files:**
- Modify: `frontend/src/views/WatchlistView.tsx:425`, `BulkAddModal.tsx:49`, `InstrumentDetailModal.tsx:27`, `BacktestsView.tsx:627`, `CalendarView.tsx:60`, `OptionsCalcView.tsx:39`
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: `.title-section`, `.title-sub` (Task 3).
- Produces: nothing new.

**Context:** the app contains **zero** `<h1>`–`<h4>` elements; every heading is a `<span>`/`<div>` styled ad hoc, most commonly `text-lg font-semibold text-zinc-100`. Replacing those five with `.title-section` gives them the real 1.35rem/650/−0.015em treatment and makes them scale with `--font-scale`.

- [ ] **Step 1: WatchlistView expanded-instrument title.**
`frontend/src/views/WatchlistView.tsx:425`, change:
```tsx
            <span className="text-lg font-semibold text-zinc-100">{st?.name || k}</span>
```
to:
```tsx
            <span className="title-section">{st?.name || k}</span>
```

- [ ] **Step 2: BulkAddModal title.**
`frontend/src/views/BulkAddModal.tsx:49`, change:
```tsx
          <span className="text-lg font-semibold text-zinc-100">Add top {rows.length} to portfolio</span>
```
to:
```tsx
          <span className="title-section">Add top {rows.length} to portfolio</span>
```

- [ ] **Step 3: InstrumentDetailModal title.**
`frontend/src/views/InstrumentDetailModal.tsx:27`, change:
```tsx
          <span className="text-lg font-semibold text-zinc-100">{d?.name || instrumentKey}</span>
```
to:
```tsx
          <span className="title-section">{d?.name || instrumentKey}</span>
```

- [ ] **Step 4: BacktestsView result title.**
`frontend/src/views/BacktestsView.tsx:627`, change:
```tsx
            <span className="text-lg font-semibold text-zinc-100">{cur.name || cur.instrument_key}</span>
```
to:
```tsx
            <span className="title-section">{cur.name || cur.instrument_key}</span>
```

- [ ] **Step 5: CalendarView page header.**
`frontend/src/views/CalendarView.tsx:60`, change:
```tsx
        <span className="font-semibold text-zinc-100">Daily P&amp;L calendar</span>
```
to:
```tsx
        <span className="title-sub">Daily P&amp;L calendar</span>
```

- [ ] **Step 6: OptionsCalcView section header.**
`frontend/src/views/OptionsCalcView.tsx:39`, change:
```tsx
          <div className="text-sm font-semibold text-zinc-100">{sel} — last evaluation</div>
```
to:
```tsx
          <div className="title-sub">{sel} — last evaluation</div>
```

- [ ] **Step 7: Verify.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
```

- [ ] **Step 8: Visual check.**
Open `http://100.120.27.71:5173`, click a Watchlist row to expand it: the instrument name renders sans-serif at 1.35rem (measure in DevTools: computed `font-size: 21.6px` at `--font-scale: 1`) with negative letterspacing, while the `Spot` and `Option` values beside it stay mono with `tabular-nums`. Then open **Calendar**: "Daily P&L calendar" renders at 1.08rem (17.28px).

- [ ] **Step 9: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/src/views && git commit -m "feat(ui): apply the new heading scale to view section titles"
```

---

### Task 5: WS-3 screenshot pass, desktop and phone

**Files:**
- Modify: whichever views the pass finds broken (expected: none to three; likely candidates are density regressions from `body { line-height: 1.65 }` in `ActivePositionsView` and `EngineView`)
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: nothing new. This task's deliverable is the screenshot set plus any fixes it forces.

- [ ] **Step 1: Start the dev server against a live backend.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/backend && .venv/bin/uvicorn app.main:app --port 8090 &
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run dev
```

- [ ] **Step 2: Capture desktop (1440×900) — nine views.**
Open `http://100.120.27.71:5173` at 1440×900 and screenshot each tab in this order, saving to `/tmp/ws3-desktop-<view>.png`: **Watchlist, Active Positions, Engine / Logs, Options Calc, Backtests, Trade Log, Calendar, Dashboard, Settings**. For each, check the three invariants:
   - every column of digits is monospace and vertically aligned;
   - no label, button text, or help text is monospace;
   - no card's content overflows its border, and no row wraps that did not wrap before.

- [ ] **Step 3: Capture phone (390×844) — the same set minus Backtests.**
Resize to 390×844 (below the 768px breakpoint, so `MobileTopBar` renders). Screenshot to `/tmp/ws3-phone-<view>.png`: **Watchlist, Active Positions, Engine / Logs, Options Calc, Trade Log, Calendar, Dashboard, Settings**. Backtests correctly shows "Backtests is desktop-only — open this on your Mac" (`App.tsx:67-69`); screenshot that too and confirm it reads as sans prose, not monospace. Check additionally:
   - the MobileTopBar stat strip scrolls horizontally without the page scrolling horizontally;
   - the `☰` drawer nav labels are sans and legible.

- [ ] **Step 4: Fix any density regression found, with explicit sizes.**
If a surface reads too airy, the cause is `body { line-height: 1.65 }` reaching an element with no explicit `leading-*`. Fix at the container, not by lowering the body value — e.g. add `leading-snug` to the offending card. Record each fix here as you make it. If nothing is broken, write "no fixes required" and move on.

- [ ] **Step 5: Verify.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
ls /tmp/ws3-desktop-*.png /tmp/ws3-phone-*.png | wc -l   # expect 18
```

- [ ] **Step 6: Commit (only when the owner asks; skip if Step 4 changed nothing).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/src && git commit -m "fix(ui): density fixes found in the WS-3 screenshot pass"
```

---

### Task 6: Make a runtime override visible in the API contract

**Files:**
- Modify: `backend/app/core/runtime_config.py:198-213` (`schema()`)
- Modify/Create: `backend/tests/test_runtime_config.py`
- Modify: `frontend/src/lib/types.ts:184`
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/backend && .venv/bin/python -m pytest tests/test_runtime_config.py -q` and `cd ../frontend && npm run typecheck`

**Interfaces:**
- Produces: `SettingRow.overridden: boolean` (TS), `"overridden"` key in each `schema()` row (Python).
- Consumed by: Tasks 8, 9, 10.

**Why this is not cosmetic.** `schema()` currently returns `default` (code default) and `value` (effective). The frontend infers "overridden" as `String(value) !== String(default)` (`SettingsView.tsx:86`). That inference is **wrong whenever a DB row stores a value equal to the code default** — the row exists, shadows the default forever, and the UI shows nothing. Per CLAUDE.md, shipping a new default silently has no effect when a stale override exists; a silently shadowed default has already cost this project time. The API must report the fact, not a guess.

- [ ] **Step 1: Emit the flag from `schema()`.**

In `backend/app/core/runtime_config.py`, replace the body of `schema()`:
```python
def schema() -> list[dict]:
    """Per-field metadata for the Settings UI: key, type, default, current value,
    and whether a runtime_config ROW exists for it.

    `overridden` is deliberately not `value != default`: a stored row whose value
    equals the code default still shadows that default forever, so shipping a new
    default silently has no effect. The UI must be able to show that fact.
    """
    s = get_settings()
    eff = effective(s)
    stored = get_overrides()
    rows = []
    for k in OVERRIDABLE:
        default = getattr(s, k)
        rows.append({
            "key": k,
            "type": ("bool" if isinstance(default, bool) else
                     "int" if isinstance(default, int) else
                     "float" if isinstance(default, float) else "str"),
            "default": default,
            "value": eff[k],
            "overridden": k in stored,
        })
    return rows
```

- [ ] **Step 2: Add the pytest.**

Append to `backend/tests/test_runtime_config.py` (create the file with this content if it does not exist):
```python
from app.core import runtime_config


def _row(key: str) -> dict:
    return next(r for r in runtime_config.schema() if r["key"] == key)


def test_schema_reports_overridden_false_with_no_row():
    runtime_config.clear_override("max_open_positions")
    assert _row("max_open_positions")["overridden"] is False


def test_schema_reports_overridden_true_for_a_changed_value():
    runtime_config.set_override("max_open_positions", 7)
    row = _row("max_open_positions")
    assert row["overridden"] is True
    assert row["value"] == 7
    runtime_config.clear_override("max_open_positions")


def test_schema_reports_overridden_true_even_when_it_equals_the_default():
    """The case value != default cannot detect: a stored row that shadows the
    code default forever, so a shipped default change silently has no effect."""
    from app.core.config import get_settings
    default = getattr(get_settings(), "max_open_positions")
    runtime_config.set_override("max_open_positions", default)
    row = _row("max_open_positions")
    assert row["value"] == row["default"] == default
    assert row["overridden"] is True
    runtime_config.clear_override("max_open_positions")
    assert _row("max_open_positions")["overridden"] is False


def test_every_overridable_key_has_the_flag():
    rows = runtime_config.schema()
    assert len(rows) == len(runtime_config.OVERRIDABLE)
    assert all(isinstance(r["overridden"], bool) for r in rows)
```

- [ ] **Step 3: Extend the TS type.**

In `frontend/src/lib/types.ts`, replace line 184:
```ts
export interface SettingRow { key: string; type: 'bool' | 'int' | 'float' | 'str'; default: any; value: any }
```
with:
```ts
export interface SettingRow {
  key: string
  type: 'bool' | 'int' | 'float' | 'str'
  default: any
  value: any
  /** True iff a `runtime_config` ROW exists for this key — NOT `value !== default`.
   *  A stored row equal to the code default still shadows it forever. */
  overridden: boolean
}
```

- [ ] **Step 4: Verify both sides.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/backend && .venv/bin/python -m pytest tests/test_runtime_config.py -q
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck
```
`npm run typecheck` is expected to FAIL at this point only if some other file constructs a `SettingRow` literal. Check with `grep -rn "SettingRow" frontend/src`; if the only uses are `SettingsView.tsx` (which reads rows from the API and never constructs one), typecheck passes clean.

- [ ] **Step 5: Confirm the full backend suite is still green.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/backend && .venv/bin/python -m pytest tests research_tests -q --tb=short > /tmp/pt.log 2>&1; tail -3 /tmp/pt.log; grep -A5 FAILED /tmp/pt.log
```

- [ ] **Step 6: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add backend/app/core/runtime_config.py backend/tests/test_runtime_config.py frontend/src/lib/types.ts && git commit -m "feat(settings): report whether a runtime_config row exists, not value != default"
```

---

### Task 7: `formatKnobValue` — the unit-affordance formatter

**Files:**
- Create: `frontend/src/lib/knobFormat.ts`
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: `SettingRow['type']` (Task 6).
- Produces: `formatKnobValue(key: string, value: unknown, type: SettingRow['type']): string`, and the exported constants `PCT_NEGATIVE`, `PCT_POSITIVE`, `RUPEE_KEYS`, `ZERO_LABEL`, `WEEKDAYS`. Consumed by Task 9.

The function is **pure**: same inputs, same output, no DOM, no state, no `Intl` locale detection (the locale is pinned to `en-IN`).

#### Input → output table (this is the contract; verify every row in Task 9's Step 8)

| `key` | `type` | `value` | Expected output |
|---|---|---|---|
| `stop_loss_pct` | `float` | `0.30` | `−30%` |
| `intraday_stop_loss_pct` | `float` | `0.008` | `−0.8%` |
| `intraday_purple_stop_loss_pct` | `float` | `0.015` | `−1.5%` |
| `target_pct` | `float` | `0.60` | `+60%` |
| `intraday_target_pct` | `float` | `0.03` | `+3%` |
| `trail_step_lock_pct` | `float` | `0.10` | `+10%` |
| `overnight_auto_pct` | `float` | `0.10` | `10%` |
| `daily_profit_giveback_frac` | `float` | `0.5` | `50%` |
| `intraday_profit_lock_frac` | `float` | `0.3` | `30%` |
| `daily_profit_lock_pct` | `float` | `0.0` | `off` |
| `reinforce_cooldown_minutes` | `int` | `15` | `15 min` |
| `intraday_entry_cutoff_minutes` | `float` | `25.0` | `25 min` |
| `reentry_cooldown_minutes` | `float` | `0` | `off` |
| `max_stale_seconds` | `float` | `90` | `90 s` |
| `position_loop_seconds` | `float` | `1.0` | `1 s` |
| `max_holding_days` | `int` | `5` | `5 d` |
| `max_holding_days` | `int` | `0` | `no cap` |
| `overtrade_rolling_days` | `int` | `7` | `7 d` |
| `max_daily_loss` | `float` | `2000` | `₹2,000` |
| `max_daily_loss` | `float` | `0` | `off` |
| `capital_reserve` | `float` | `125000` | `₹1,25,000` |
| `intraday_max_margin` | `float` | `7000` | `₹7,000` |
| `intraday_profit_lock_threshold` | `float` | `600.0` | `₹600` |
| `max_capital_per_trade` | `float` | `0` | `no cap` |
| `intraday_leverage` | `float` | `5` | `5×` |
| `gtt_stop_enabled` | `bool` | `true` | `on` |
| `trail_enabled` | `bool` | `false` | `off` |
| `max_open_positions` | `int` | `3` | `3` |
| `max_open_positions` | `int` | `0` | `unlimited` |
| `intraday_max_positions` | `int` | `4` | `4` |
| `intraday_block_weekday` | `int` | `1` | `Tue` |
| `intraday_block_weekday` | `int` | `-1` | `off` |
| `entry_window_start` | `str` | `"09:30"` | `09:30` |
| `expiry_day_block_keys` | `str` | `"NIFTY"` | `NIFTY` |
| `intraday_override_date` | `str` | `""` | `—` |
| `max_reinforcements` | `int` | `3` | `3` |
| `exec_min_top_qty_lots` | `float` | `1.0` | `1` |
| any | any | `null`/`undefined` | `—` |

- [ ] **Step 1: Write the file.**

Create `frontend/src/lib/knobFormat.ts`:
```ts
import type { SettingRow } from './types'

/** Stops whose stored fraction is a LOSS: 0.30 reads as −30%. */
export const PCT_NEGATIVE = new Set([
  'stop_loss_pct',
  'intraday_stop_loss_pct',
  'intraday_purple_stop_loss_pct',
])

/** Targets / locks whose stored fraction is a GAIN: 0.60 reads as +60%. */
export const PCT_POSITIVE = new Set([
  'target_pct',
  'intraday_target_pct',
  'intraday_purple_target_pct',
  'trail_trigger_pct',
  'trail_first_step_lock_pct',
  'trail_step_lock_pct',
  'reinforce_lock_pct',
  'reinforce_min_profit_pct',
  'reinforce_tp_extend_pct',
  'reinforce_tp_max_pct',
])

/** Rupee amounts — rendered with Indian digit grouping (1,25,000 not 125,000). */
export const RUPEE_KEYS = new Set([
  'max_capital_per_trade',
  'max_daily_loss',
  'max_open_drawdown',
  'bot_capital_cap',
  'capital_reserve',
  'intraday_min_margin',
  'intraday_max_margin',
  'intraday_purple_margin',
  'intraday_profit_lock_threshold',
])

/** Knobs where 0 is a sentinel, and the word it means. Checked BEFORE units. */
export const ZERO_LABEL: Record<string, string> = {
  max_open_positions: 'unlimited',
  intraday_max_positions: 'none',
  max_capital_per_trade: 'no cap',
  max_holding_days: 'no cap',
  bot_capital_cap: 'no cap',
  max_daily_loss: 'off',
  max_open_drawdown: 'off',
  daily_profit_lock_pct: 'off',
  reentry_cooldown_minutes: 'off',
  max_signal_age_minutes: 'off',
  gap_guard_pct: 'off',
  order_failure_disarm_count: 'off',
  overtrade_today_threshold: 'off',
  overtrade_rolling_threshold: 'off',
  max_round_trips_per_day: 'off',
  entry_min_days_to_expiry: 'off',
}

/** Mon=0 … Sun=6, matching config.py `intraday_block_weekday`. */
export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Trim a float to at most `d` decimals with no trailing zeros: 0.8 -> "0.8", 30 -> "30". */
function trim(n: number, d = 2): string {
  return String(Number(n.toFixed(d)))
}

function percent(n: number, sign: '' | '+' | '−'): string {
  return `${sign}${trim(Math.abs(n) * 100)}%`
}

/**
 * Render a runtime knob's STORED value as the thing it actually means.
 * Pure: no DOM, no state, locale pinned to en-IN. The stored value is unchanged —
 * this is display only. See the input/output table in the WS-4 plan.
 */
export function formatKnobValue(
  key: string,
  value: unknown,
  type: SettingRow['type'],
): string {
  if (value === null || value === undefined) return '—'

  if (type === 'bool') return value ? 'on' : 'off'

  if (type === 'str') {
    const s = String(value)
    return s === '' ? '—' : s
  }

  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return String(value)

  // Weekday sentinel is its own thing: -1 = off, 0..6 = a day name.
  if (key === 'intraday_block_weekday') {
    if (n < 0) return 'off'
    return WEEKDAYS[n] ?? String(n)
  }

  // Zero sentinels outrank units: "off" beats "0 min".
  if (n === 0 && key in ZERO_LABEL) return ZERO_LABEL[key]

  if (RUPEE_KEYS.has(key)) {
    return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })
  }

  if (key === 'intraday_leverage') return `${trim(n)}×`

  if (PCT_NEGATIVE.has(key)) return percent(n, '−')
  if (PCT_POSITIVE.has(key)) return percent(n, '+')
  if (key.endsWith('_pct') || key.endsWith('_frac')) return percent(n, '')

  if (key.endsWith('_minutes')) return `${trim(n)} min`
  if (key.endsWith('_seconds')) return `${trim(n)} s`
  if (key.endsWith('_days')) return `${trim(n)} d`

  return trim(n)
}
```

- [ ] **Step 2: Verify it compiles.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
```
`build` at this point will tree-shake the module out because nothing imports it yet; that is expected. The gate here is that `tsc --noEmit` is silent.

- [ ] **Step 3: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/src/lib/knobFormat.ts && git commit -m "feat(settings): pure formatKnobValue unit-affordance formatter"
```

---

### Task 8: Settings metadata — labels, help, groups, danger tier, catch-all

**Files:**
- Create: `frontend/src/lib/settingsMeta.ts`
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Produces: `KnobMeta` type, `META: Record<string, KnobMeta>`, `GROUP_DEFS: GroupDef[]`, `DANGER_KEYS: Set<string>`, `groupOf(key: string): string`, `searchHaystack(key: string): string`. Consumed by Task 9.

**Two real gaps this closes.** (a) The current `GROUPS` in `SettingsView.tsx:69-80` do not match every `OVERRIDABLE` key: `daily_profit_lock_pct`, `daily_profit_giveback_frac`, `gap_guard_enabled`, `gap_guard_pct`, `gap_guard_resume`, `gap_guard_index`, `entry_min_days_to_expiry`, `max_signal_age_minutes`, `entry_window_start`, `expiry_day_block_keys`, `order_failure_disarm_count` and `max_round_trips_per_day` match no group and are therefore **invisible in the UI today**. (b) There is no danger tier at all. `groupOf` has a catch-all so a knob added to `OVERRIDABLE` later can never silently disappear again.

- [ ] **Step 1: Create the file — types, danger tier, and group definitions.**

Create `frontend/src/lib/settingsMeta.ts` starting with:
```ts
export interface KnobMeta { label: string; help: string }

export interface GroupDef {
  /** Stable id, used as the collapse-state key. */
  id: string
  title: string
  /** Danger groups render separated, with a red rule, and open by default. */
  danger?: boolean
  match: (key: string) => boolean
}

/**
 * Anything that can halt or unhalt trading, or that bounds real capital.
 * Spec §5 names the first six explicitly; the rest are the other halt/unhalt
 * levers in `OVERRIDABLE` and belong in the same tier by the same reasoning.
 */
export const DANGER_KEYS = new Set([
  'max_daily_loss',
  'max_open_drawdown',
  'bot_capital_cap',
  'capital_reserve',
  'gtt_stop_enabled',
  'intraday_enabled',
  'daily_profit_lock_pct',
  'daily_profit_giveback_frac',
  'order_failure_disarm_count',
  'max_round_trips_per_day',
  'gap_guard_enabled',
  'gap_guard_pct',
  'gap_guard_resume',
  'gap_guard_index',
  'intraday_block_weekday',
  'expiry_day_block_keys',
  'intraday_override_date',
  'entry_window_start',
  // Both live in the `dayshape` danger group below, so they carry the tier too.
  'max_signal_age_minutes',
  'entry_min_days_to_expiry',
])

const CATCH_ALL_ID = 'other'

export const GROUP_DEFS: GroupDef[] = [
  {
    id: 'halts', title: 'Halts & capital limits', danger: true,
    match: (k) => ['max_daily_loss', 'max_open_drawdown', 'bot_capital_cap', 'capital_reserve',
      'gtt_stop_enabled', 'intraday_enabled', 'daily_profit_lock_pct',
      'daily_profit_giveback_frac', 'order_failure_disarm_count',
      'max_round_trips_per_day'].includes(k),
  },
  {
    id: 'dayshape', title: 'Day-shape guards', danger: true,
    match: (k) => k.startsWith('gap_guard_') ||
      ['intraday_block_weekday', 'expiry_day_block_keys', 'intraday_override_date',
        'entry_window_start', 'max_signal_age_minutes', 'entry_min_days_to_expiry'].includes(k),
  },
  { id: 'risk', title: 'Risk & cadence', match: (k) => ['stop_loss_pct', 'target_pct', 'max_stale_seconds', 'position_loop_seconds', 'signal_loop_seconds'].includes(k) },
  { id: 'limits', title: 'Position & trade limits', match: (k) => ['max_open_positions', 'reentry_cooldown_minutes', 'max_capital_per_trade'].includes(k) },
  { id: 'intraday', title: 'Intraday equity (MIS)', match: (k) => k.startsWith('intraday_') },
  { id: 'trail', title: 'Trailing stop', match: (k) => k.startsWith('trail_') },
  { id: 'reinforce', title: 'Reinforcement', match: (k) => k.startsWith('reinforce_') || k === 'max_reinforcements' },
  { id: 'overnight', title: 'Overnight holding', match: (k) => k.startsWith('overnight_') || ['max_holding_days', 'square_off_buffer_minutes', 'block_overnight_into_weekend'].includes(k) },
  { id: 'exec', title: 'Order execution', match: (k) => k.startsWith('exec_') },
  { id: 'overtrade', title: 'Overtrading guard', match: (k) => k.startsWith('overtrade_') },
  { id: 'notify', title: 'Notifications', match: (k) => k.startsWith('notify_') || k === 'alert_proximity_pct' },
  { id: 'cache', title: 'Option-data cache', match: (k) => k.startsWith('option_cache_') },
  // Catch-all — MUST stay last and MUST match everything, so a knob added to
  // OVERRIDABLE later can never silently vanish from the UI the way twelve of
  // them did before this rewrite.
  { id: CATCH_ALL_ID, title: 'Other', match: () => true },
]

export function groupOf(key: string): string {
  return (GROUP_DEFS.find((g) => g.match(key)) ?? GROUP_DEFS[GROUP_DEFS.length - 1]).id
}
```

**Ordering note:** `GROUP_DEFS` is scanned top-down and the first match wins, so `intraday` must sit BELOW `halts`/`dayshape` (which claim `intraday_enabled`, `intraday_block_weekday` and `intraday_override_date`) and above nothing that also starts with `intraday_`. Do not reorder.

- [ ] **Step 2: Append the `META` map — the 67 existing entries verbatim plus the 12 missing ones.**

Append to `frontend/src/lib/settingsMeta.ts`:
```ts
/** Human label + one-line doc per knob. Moved verbatim out of SettingsView.tsx
 *  (the help text there was already good) and extended to cover every key in
 *  runtime_config.OVERRIDABLE. Anything unlisted still renders with its raw key. */
export const META: Record<string, KnobMeta> = {
  reinforce_enabled: { label: 'Reinforcement enabled', help: 'Same-direction signal on a held winner strengthens management (no added qty).' },
  reinforce_min_profit_pct: { label: 'Min profit to reinforce', help: 'Position must be at least this far in profit before a reinforcement counts. Recommended 0.10.' },
  reinforce_lock_pct: { label: 'SL lock per reinforcement', help: 'Each reinforcement locks the stop to entry×(1+count×this). 0.05 ⇒ entry 300→SL 315.' },
  reinforce_extend_tp: { label: 'Extend target on reinforce', help: 'Push the take-profit out as confirmations stack (safe: stop is already locked in profit).' },
  reinforce_tp_extend_pct: { label: 'TP extension per reinforce', help: 'Fraction of entry added to the target each reinforcement. Recommended 0.20.' },
  reinforce_tp_max_pct: { label: 'TP extension cap', help: 'Target never extends beyond entry×(1+this). Recommended 1.50 (theta limits the upside of waiting).' },
  reinforce_cooldown_minutes: { label: 'Reinforcement cooldown', help: 'Minimum gap between counted reinforcements. Recommended 15.' },
  max_reinforcements: { label: 'Max reinforcements', help: 'Cap on confirmations per trade. Recommended 3.' },
  overnight_enabled: { label: 'Overnight holding enabled', help: 'Allow eligible positions to carry past session close.' },
  overnight_auto_pct: { label: 'Auto-overnight ≤ % capital', help: 'Positions this small auto-hold overnight. Recommended 0.10.' },
  overnight_max_pct: { label: 'Never overnight > % capital', help: 'Hard cap — bigger positions never carry, even reinforced. Recommended 0.25.' },
  overnight_min_reinforcements: { label: 'Reinforcements for mid-size', help: 'Positions between the two thresholds need this many reinforcements to carry. Recommended 1.' },
  overnight_min_days_to_expiry: { label: 'Min days to expiry', help: 'Force square-off if expiry is closer than this — avoids the theta cliff. Recommended 2.' },
  block_overnight_into_weekend: { label: 'Block weekend carry', help: 'Square off on Fridays (3 days of theta over a weekend). Default off.' },
  max_holding_days: { label: 'Max holding period', help: 'Hard cap — long options bleed; close dead-money trades. Recommended 5.' },
  square_off_buffer_minutes: { label: 'Square-off buffer', help: 'Decide hold-vs-close this long before session close. Recommended 15.' },
  trail_enabled: { label: 'Trailing stop enabled', help: 'Continuously ratchet the stop up as profit thresholds are crossed.' },
  trail_trigger_pct: { label: 'Trail trigger step', help: 'Profit per ratchet step (fraction of entry).' },
  trail_first_step_lock_pct: { label: 'Trail first-step lock', help: 'Gentle stop lock at the first +10% profit step (fraction of entry). Recommended 0.025.' },
  trail_step_lock_pct: { label: 'Trail step lock', help: 'From the 2nd step on, the stop trails this fraction of entry behind each step — no upper cap. Recommended 0.10.' },
  option_cache_enabled: { label: 'Option-data cache', help: 'Persist every downloaded chain into a growing local research dataset.' },
  option_cache_snapshot_minutes: { label: 'Cache snapshot cadence', help: 'At most one chain snapshot per instrument per this many minutes.' },
  stop_loss_pct: { label: 'Initial stop', help: 'Initial premium stop below entry, as a fraction (0.30 = −30%).' },
  target_pct: { label: 'Initial target', help: 'Initial premium target above entry, as a fraction (0.60 = +60%).' },
  max_open_positions: { label: 'Max concurrent positions', help: 'Cap how many positions the bot holds at once — stops a single trending day becoming many correlated bets. 0 = unlimited.' },
  reentry_cooldown_minutes: { label: 'Re-entry cooldown', help: 'After a stop-out on an instrument, block new entries on it for this long — avoids the chop re-entry trap. 0 = off.' },
  max_capital_per_trade: { label: 'Max capital per trade', help: 'Skip a signal whose 1-lot cost exceeds this — bounds single-trade exposure. 0 = no cap.' },
  max_stale_seconds: { label: 'Max stale mark', help: 'A mark older than this is stale — no SL/TP fires on it.' },
  position_loop_seconds: { label: 'Risk loop cadence', help: 'Fast lane: mark + trail + SL/TP.' },
  signal_loop_seconds: { label: 'Signal loop cadence', help: 'Slow lane: scan candles + entries.' },
  notify_enabled: { label: 'Notifications enabled', help: 'Master switch for Telegram alerts. No-op unless TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set in .env.' },
  notify_on_signal: { label: 'Alert on every signal', help: 'Also ping on each fresh entry signal — can be noisy. Default off.' },
  alert_proximity_pct: { label: 'Near-SL/TP alert threshold', help: 'Warn when the premium comes within this fraction of the stop or target level. Recommended 0.10 (10%).' },
  exec_market_max_spread_pct: { label: 'Market-order max spread', help: 'Send a MARKET order only when the bid-ask spread is at/under this fraction; wider routes a capped limit instead. Recommended 0.01 (1%).' },
  exec_limit_max_spread_pct: { label: 'Skip-entry spread', help: 'Above this spread an entry is SKIPPED — too illiquid to enter safely (e.g. some commodity options). Recommended 0.05 (5%).' },
  exec_max_slippage_pct: { label: 'Limit slippage cap', help: 'A marketable-limit order is capped this far off the mid price. Recommended 0.01 (1%).' },
  exec_min_top_qty_lots: { label: 'Min top-of-book (lots)', help: 'Require this many lots on the touch to send a MARKET order; a thinner book routes a capped limit. Recommended 1.' },
  max_daily_loss: { label: 'Daily loss halt', help: 'Stop opening new trades for the rest of the day once realized net loss reaches this. 0 = off. Recommended 5000.' },
  max_open_drawdown: { label: 'Open drawdown halt', help: "Stop opening new trades once today's realized + unrealized (open MTM) loss reaches this. 0 = off. Recommended 2500 — half the daily loss halt, since open MTM bleeds faster than realized." },
  bot_capital_cap: { label: 'Bot capital cap', help: 'Hard ceiling on what the bot may ever deploy. 0 = no extra cap. Protects your capital even if Kite briefly mis-reports margin.' },
  capital_reserve: { label: 'Capital reserve', help: 'Live: account margin kept free for your own trades — the bot never dips into it.' },
  gtt_stop_enabled: { label: 'Exchange-side GTT stop', help: 'Live only: also place a Good-Till-Triggered stop on Zerodha so the position is protected even if the bot/laptop/internet goes down. Trails with the bot stop; cancelled when the bot exits.' },
  intraday_enabled: { label: 'Intraday equity enabled', help: 'Master switch for the MIS intraday-equity segment. Off = only options trade. Flag instruments as INTRA on the Watchlist to route them here.' },
  intraday_max_positions: { label: 'Max concurrent intraday trades', help: 'Hard cap on simultaneous MIS positions (purple-priority names included). Recommended 3 — keeps costs down.' },
  intraday_min_margin: { label: 'Min margin / trade', help: 'Dust floor only — a trade smaller than this (e.g. a partial funded by leftover cash) is skipped so charges don’t eat it. Keep LOW so partial fills still open. Recommended 2500.' },
  intraday_max_margin: { label: 'Max margin / trade', help: 'Target REAL margin deployed per (non-purple) intraday trade — qty sized so Zerodha blocks about this much; the broker’s own MIS multiplier sets the notional. Recommended 7000.' },
  intraday_purple_margin: { label: 'Purple margin / trade', help: 'Target REAL margin for a purple-flagged priority name — always taken, sized larger than normal names. Recommended 10000.' },
  intraday_leverage: { label: 'Intraday leverage', help: 'Fallback estimate ONLY (no longer caps live sizing) — used for paper/mock and if a live margin quote fails. Keep near Zerodha’s real ~5×. Recommended 5.' },
  intraday_square_off_buffer_minutes: { label: 'Intraday square-off before close', help: 'Force every MIS position flat this long before the session close — MIS cannot carry overnight. Recommended 15.' },
  intraday_entry_cutoff_minutes: { label: 'Intraday entry cutoff before close', help: 'Open no NEW MIS position within this long of the session close — there is not enough runway left to reach the target. Production overrides this to 60.' },
  intraday_stop_loss_pct: { label: 'Intraday stop', help: 'Stop as a fraction of entry price (0.01 = −1%). Tight, unlike the option-premium stop.' },
  intraday_target_pct: { label: 'Intraday target', help: 'Target as a fraction of entry price (0.02 = +2%). The starting top of the lockstep band.' },
  intraday_purple_stop_loss_pct: { label: 'Purple intraday stop', help: 'Stop for a purple-flagged priority name, as a fraction of entry — deliberately wider than the normal intraday stop. Default 0.015.' },
  intraday_purple_target_pct: { label: 'Purple intraday target', help: 'Target for a purple-flagged priority name, as a fraction of entry — wider than normal. Default 0.045.' },
  intraday_lockstep_enabled: { label: 'Lockstep band', help: 'Once an equity position is in profit, ratchet the stop AND target together (break-even floored), so winners lock in and keep room to run. On by default.' },
  intraday_lockstep_trigger_pct: { label: 'Lockstep step (% of margin)', help: 'Each step of this much margin-profit slides the SL+TP one notch in your favour (0.02 = every +2% of margin, e.g. +₹200 on ₹10k). Recommended 0.02.' },
  intraday_profit_lock_threshold: { label: 'Intraday profit-lock threshold', help: 'Once unrealized profit on an MIS position clears this rupee amount, lock a positive buffer above costs so the trade cannot round-trip to a loss.' },
  intraday_profit_lock_frac: { label: 'Intraday profit-lock fraction', help: 'Fraction of the favourable move locked in once the threshold above is cleared. 0.3 = keep at least 30% of the best move.' },
  overtrade_today_threshold: { label: 'Overtrade suggest — today', help: 'Suggest the red overtrading flag when an instrument fires at least this many entry signals today. 0 disables. Advisory only — never blocks trading.' },
  overtrade_rolling_threshold: { label: 'Overtrade suggest — rolling', help: 'Suggest red when signals over the rolling window reach this many. 0 disables.' },
  overtrade_rolling_days: { label: 'Overtrade rolling window', help: 'Length of the rolling window for the signal-count suggestion.' },
  entry_min_days_to_expiry: { label: 'Min days to expiry to OPEN', help: 'Refuse to open an option within this many days of expiry (theta cliff): blocks 0/1/2-DTE. 0 = off.' },
  intraday_block_weekday: { label: 'Sit-out weekday', help: 'Sit out this weekday entirely (Mon..Sun). Default Tue, the NIFTY expiry day. Scoped by the instrument list below. Off = trade every day.' },
  expiry_day_block_keys: { label: 'Sit-out applies to', help: "Which instruments sit out that weekday: '*' = the whole book; otherwise a comma-separated instrument-key list. Blank fails safe to '*'." },
  intraday_override_date: { label: 'Sit-out override date', help: "'YYYY-MM-DD' to allow entries despite the weekday block, that one day only. Self-expires — clear it when done." },
  max_signal_age_minutes: { label: 'Max signal age', help: 'Act on a crossover only within this long of its candle COMPLETING; anything older is history and is never entered. 0 = off.' },
  entry_window_start: { label: 'No entries before', help: 'IST wall-clock time before which no NEW entry opens. The session opens 09:15 and the first minutes are erratic. Blank = off.' },
  gap_guard_enabled: { label: 'Opening-gap guard', help: 'Pause new entries after a large index gap on the open, until the resume time below.' },
  gap_guard_pct: { label: 'Gap threshold', help: '|open − prev_close| / prev_close that counts as a gap, in percent. 0 = off.' },
  gap_guard_resume: { label: 'Gap guard resumes at', help: 'IST wall-clock time at which new entries resume after a gap day is detected.' },
  gap_guard_index: { label: 'Gap guard index', help: 'Instrument key whose open vs previous close defines "the market gapped". Default NIFTY.' },
  order_failure_disarm_count: { label: 'Order-failure circuit breaker', help: 'DISARM the bot after this many CONSECUTIVE live order failures (systemic: bad token, IP, or margin). Re-arm manually after fixing. 0 = off.' },
  max_round_trips_per_day: { label: 'Max round trips / day', help: 'Halt NEW entries once this many round trips have completed today. 0 = off.' },
  daily_profit_lock_pct: { label: 'Daily profit lock — arm at', help: "Arm the day's give-back halt once profit reaches this fraction of daily deployed capital (0.02 = 2%). 0 = off." },
  daily_profit_giveback_frac: { label: 'Daily profit lock — give back at most', help: "Once armed, square off everything if the day retraces to this fraction of its peak P&L. 0.5 = give back at most half." },
}

/** Lower-cased key + label + help, for the search filter. */
export function searchHaystack(key: string): string {
  const m = META[key]
  return `${key} ${m?.label ?? ''} ${m?.help ?? ''}`.toLowerCase()
}
```

- [ ] **Step 3: Verify.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
```

- [ ] **Step 4: Prove every `OVERRIDABLE` key has a `META` entry.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader
python3 - <<'PY'
import re, pathlib
rc = pathlib.Path('backend/app/core/runtime_config.py').read_text()
block = rc.split('OVERRIDABLE = (')[1].split(')\n')[0]
keys = set(re.findall(r'"([a-z_]+)"', block))
meta = pathlib.Path('frontend/src/lib/settingsMeta.ts').read_text()
have = set(re.findall(r'^  ([a-z_]+): \{ label:', meta, re.M))
print("OVERRIDABLE:", len(keys), "META:", len(have))
print("missing from META:", sorted(keys - have))
print("META keys not overridable:", sorted(have - keys))
PY
```
Both "missing" lists must print `[]`.

- [ ] **Step 5: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/src/lib/settingsMeta.ts && git commit -m "feat(settings): extract knob metadata, add danger tier and a catch-all group"
```

---

### Task 9: Rebuild SettingsView — search, collapsible groups, inline errors

**Files:**
- Rewrite: `frontend/src/views/SettingsView.tsx` (all 145 lines)
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: `SettingRow` incl. `overridden` (Task 6); `formatKnobValue` (Task 7); `META`, `GROUP_DEFS`, `DANGER_KEYS`, `groupOf`, `searchHaystack` (Task 8); `getSettings`, `setSetting`, `resetSetting` from `../lib/api`; `Badge`, `badgeVariants`, `Card`, `cn`.
- Produces: the `SettingsView` default export. Task 10 adds one card to it.

**Real API contract** (`backend/app/api/routes.py:772-800`, do not guess):
- `GET /api/settings` → `{ "params": SettingRow[] }`, `SettingRow = { key, type: 'bool'|'int'|'float'|'str', default, value, overridden }`.
- `POST /api/settings` body `{ key, value }` → `{ key, value: string }` on success, **or `{ error: string }` with HTTP 200** on rejection (`runtime_config.set_override` returns the error dict; the route does not raise). Two rejection sources: `'<key>' is not an overridable parameter` and `<key> must be between <lo> and <hi> (got <n>)` from `BOUNDS` in `runtime_config.py:66-126`.
- `POST /api/settings/reset` body `{ key }` → `{ key, reset: true }`. Never errors.
- Both mutating routes call `_runner(request).refresh_params()`, so every value applies live with no restart — the honest framing at the old `:130-131` must be preserved.

- [ ] **Step 1: Replace the whole file — imports, `Row`, inline error state.**

Write `frontend/src/views/SettingsView.tsx`:
```tsx
import { useEffect, useMemo, useState } from 'react'
import { getSettings, setSetting, resetSetting } from '../lib/api'
import type { SettingRow } from '../lib/types'
import { formatKnobValue } from '../lib/knobFormat'
import { META, GROUP_DEFS, DANGER_KEYS, groupOf, searchHaystack } from '../lib/settingsMeta'
import { Badge, badgeVariants } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

function Row({ r, onSaved }: { r: SettingRow; onSaved: () => void }) {
  const [v, setV] = useState(r.value)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setV(r.value); setErr(null) }, [r.value])
  const m = META[r.key] || { label: r.key, help: '' }
  const danger = DANGER_KEYS.has(r.key)

  // Rejection arrives as { error } with HTTP 200 (routes.py:783-788). Show it
  // under the field instead of throwing a modal — the old window.alert(res.error)
  // stole focus and hid which knob was rejected.
  const save = (val: any) =>
    setSetting(r.key, val).then((res: any) => {
      if (res && res.error) {
        setV(r.value)
        setErr(String(res.error))
      } else {
        setErr(null)
        onSaved()
      }
    }).catch((e) => setErr(String(e?.message || e)))

  return (
    <div className={cn('flex items-start gap-3 py-2 border-t border-edge/50',
      danger && 'border-l-2 border-l-down/40 pl-2')}>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-zinc-200">
          {m.label}
          {r.overridden && (
            <Badge variant="chip" className="bg-blue-500/15 text-blue-300 ml-2"
              title="A runtime_config row exists for this key. It shadows the code default permanently — shipping a new default will NOT take effect until this is reset.">
              overridden
            </Badge>
          )}
          {danger && (
            <Badge variant="chip" className="bg-down/15 text-down ml-2"
              title="This knob can halt or unhalt trading, or bounds real capital.">
              danger
            </Badge>
          )}
        </div>
        <div className="text-micro text-muted">{m.help}</div>
        {err && (
          <div role="alert" className="text-micro text-down mt-1">
            Rejected — {err}. Value reverted to {formatKnobValue(r.key, r.value, r.type)}.
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {r.type === 'bool' ? (
          <button onClick={() => { setV(!v); save(!v) }}
            className={cn(badgeVariants({ variant: 'chip' }), v ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted')}>
            {v ? 'on' : 'off'}
          </button>
        ) : r.type === 'str' ? (
          <input type="text" value={v ?? ''}
            onChange={(e) => setV(e.target.value)}
            onBlur={() => save(v)} onKeyDown={(e) => e.key === 'Enter' && save(v)}
            className={cn('w-28 bg-panel2 border rounded px-2 py-1 text-xs',
              err ? 'border-down' : 'border-edge')} />
        ) : (
          <input type="number" value={v} step={r.type === 'int' ? 1 : 'any'}
            onChange={(e) => setV(r.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
            onBlur={() => save(v)} onKeyDown={(e) => e.key === 'Enter' && save(v)}
            className={cn('w-24 bg-panel2 border rounded px-2 py-1 text-xs tabular-nums',
              err ? 'border-down' : 'border-edge')} />
        )}
        {/* Units as affordances: the stored value is unchanged, only its reading. */}
        <span className="w-28 text-right text-micro tabular-nums text-zinc-300"
          title={`stored value: ${String(r.value)}`}>
          {formatKnobValue(r.key, r.value, r.type)}
        </span>
        <span className="w-28 text-right text-micro tabular-nums text-muted"
          title={`code default: ${String(r.default)}`}>
          default {formatKnobValue(r.key, r.default, r.type)}
        </span>
        <button disabled={!r.overridden}
          onClick={() => resetSetting(r.key).then(() => { setErr(null); onSaved() })}
          title={r.overridden ? 'Delete the runtime_config row and fall back to the code default' : 'No override stored'}
          className={cn('btn text-micro', r.overridden ? 'text-zinc-200' : 'opacity-30')}>
          Reset to default
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Append the group component with its override count and collapse state.**
```tsx
function Group({ id, title, danger, rows, open, onToggle, onSaved }: {
  id: string; title: string; danger?: boolean; rows: SettingRow[]
  open: boolean; onToggle: (id: string) => void; onSaved: () => void
}) {
  const overridden = rows.filter((r) => r.overridden).length
  return (
    <Card className={cn('p-3', danger && 'border-down/40')}>
      <button onClick={() => onToggle(id)}
        className="w-full flex items-center gap-2 text-left">
        <span className="text-muted w-3">{open ? '▾' : '▸'}</span>
        <span className="title-sub">{title}</span>
        {danger && <Badge variant="chip" className="bg-down/15 text-down">danger</Badge>}
        <span className="ml-auto flex items-center gap-2">
          {overridden > 0 && (
            <Badge variant="chip" className="bg-blue-500/15 text-blue-300"
              title="Knobs in this group with a stored runtime_config row shadowing the code default">
              {overridden} overridden
            </Badge>
          )}
          <span className="text-micro text-muted tabular-nums">{rows.length}</span>
        </span>
      </button>
      {open && rows.map((r) => <Row key={r.key} r={r} onSaved={onSaved} />)}
    </Card>
  )
}
```

- [ ] **Step 3: Append the view itself — search, collapse map, danger separation.**
```tsx
export default function SettingsView() {
  const [rows, setRows] = useState<SettingRow[]>([])
  const [q, setQ] = useState('')
  // Collapsed by default (spec §5). Danger groups open by default: a halt knob
  // you cannot see is the failure mode this redesign exists to prevent.
  const [openIds, setOpenIds] = useState<Set<string>>(
    () => new Set(GROUP_DEFS.filter((g) => g.danger).map((g) => g.id)))
  const load = () => getSettings().then((d) => setRows(d.params || []))
  useEffect(() => { load() }, [])

  const needle = q.trim().toLowerCase()
  const matched = useMemo(
    () => (needle ? rows.filter((r) => searchHaystack(r.key).includes(needle)) : rows),
    [rows, needle])

  const byGroup = useMemo(() => {
    const m = new Map<string, SettingRow[]>()
    for (const r of matched) {
      const g = groupOf(r.key)
      if (!m.has(g)) m.set(g, [])
      m.get(g)!.push(r)
    }
    return m
  }, [matched])

  const toggle = (id: string) =>
    setOpenIds((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })

  const totalOverridden = rows.filter((r) => r.overridden).length
  const dangerDefs = GROUP_DEFS.filter((g) => g.danger)
  const tuningDefs = GROUP_DEFS.filter((g) => !g.danger)

  return (
    <div className="flex flex-col gap-3">
      <Card className="p-3 flex flex-col gap-2">
        <div className="stat-label">Manual override — every value applies live, no code changes or restart</div>
        <div className="text-micro text-muted">
          Defaults shown are the recommended values; override any of them and the engine picks it up on the next loop.
          {totalOverridden > 0 && (
            <> <b className="text-blue-300">{totalOverridden} knob{totalOverridden === 1 ? '' : 's'} currently overridden</b> —
            a stored override shadows the code default permanently, so a shipped default change has no effect until it is reset.</>
          )}
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={`Search ${rows.length} settings by name, key or help text…`}
          className="w-full bg-panel2 border border-edge rounded px-3 py-2 text-sm" />
        {needle && (
          <div className="text-micro text-muted tabular-nums">
            {matched.length} of {rows.length} match “{q.trim()}”
          </div>
        )}
      </Card>

      {/* Danger tier, visually separated from the tuning knobs (spec §5). */}
      {dangerDefs.map((g) => {
        const group = byGroup.get(g.id) || []
        if (!group.length) return null
        return <Group key={g.id} id={g.id} title={g.title} danger rows={group}
          open={!!needle || openIds.has(g.id)} onToggle={toggle} onSaved={load} />
      })}

      <div className="stat-label mt-2">Tuning</div>

      {tuningDefs.map((g) => {
        const group = byGroup.get(g.id) || []
        if (!group.length) return null
        return <Group key={g.id} id={g.id} title={g.title} rows={group}
          open={!!needle || openIds.has(g.id)} onToggle={toggle} onSaved={load} />
      })}

      {matched.length === 0 && (
        <Card className="p-6 text-center text-muted">no setting matches “{q.trim()}”</Card>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Verify.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
grep -c "window.alert" src/views/SettingsView.tsx   # must be 0
```

- [ ] **Step 5: Visual check — hierarchy and search.**
With the backend running, open `http://100.120.27.71:5173` → **Settings**.
1. Two danger cards (`Halts & capital limits`, `Day-shape guards`) render at the top with a red border, expanded, each row carrying a red left rule and a `danger` chip.
2. Below the `TUNING` micro-label, every other group renders **collapsed**, showing only its title, its `N overridden` chip where applicable, and its knob count.
3. Group titles render sans-serif at 1.08rem (`.title-sub`); the numbers column beside every input is mono with `tabular-nums`.

- [ ] **Step 6: Visual check — search.**
Type `margin` in the search box. Only knobs whose key, label or help text mentions margin remain; every group containing a match auto-expands; the counter reads `N of M match “margin”` where `M` equals `len(runtime_config.OVERRIDABLE)` (confirm with `cd backend && .venv/bin/python -c "from app.core import runtime_config as r; print(len(r.OVERRIDABLE))"`) and `0 < N < M`. Type `zzzz`: the "no setting matches" card renders and no group is shown.

- [ ] **Step 7: Visual check — inline error replaces the modal.**
Find **Risk & cadence → Risk loop cadence**. Its bound is `(0.5, 600.0)` (`runtime_config.py:89`). Type `0.1` and press Enter. **No browser modal appears.** A red line renders under the help text reading `Rejected — position_loop_seconds must be between 0.5 and 600.0 (got 0.1). Value reverted to 1 s.` and the input border turns red. Press Escape / click elsewhere, then set it back to a valid value and confirm the error clears.

- [ ] **Step 8: Visual check — the `formatKnobValue` contract table.**
Walk the table in Task 7 against the rendered UI. At minimum confirm these six by eye:
`Initial stop` reads **−30%** (not `0.3`); `Intraday stop` reads **−0.8%**; `Initial target` reads **+60%**; `Daily loss halt` reads **₹2,000** (production override) with Indian grouping; `Intraday square-off before close` reads **15 min**; `Sit-out weekday` reads **Tue**. Hover any of them: the tooltip shows `stored value: 0.3` etc., proving the stored value is unchanged.

- [ ] **Step 9: Visual check — override visibility against production reality.**
Per CLAUDE.md, production overrides `intraday_max_positions` (4), `intraday_entry_cutoff_minutes` (60) and `max_daily_loss` (2000). Against a DB carrying those rows: the `Halts & capital limits` header shows `1 overridden`, `Intraday equity (MIS)` shows `2 overridden` while still collapsed, and each of the three rows carries the blue `overridden` chip with a working `Reset to default` button. On a clean dev DB with no overrides, every count is absent and every reset button is at 30% opacity.

- [ ] **Step 10: Visual check — phone.**
Resize below 768px. Group headers wrap without horizontal page scroll; the value / default / reset cluster stays on one line or wraps cleanly below the label. If it overflows, add `flex-wrap` to the `Row` control cluster and re-verify — that is the expected fix.

- [ ] **Step 11: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/src/views/SettingsView.tsx && git commit -m "feat(settings): searchable collapsible panel with danger tier, units and inline errors"
```

---

### Task 10: The `--font-scale` knob, applied before first paint

**Files:**
- Create: `frontend/src/lib/appearance.ts`
- Modify: `frontend/index.html`
- Modify: `frontend/src/views/SettingsView.tsx` (add one import and one card)
- Verify: `cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: `--font-scale` (Task 1), `html { font-size: calc(16px * var(--font-scale, 1)) }` (Task 3), `SettingsView` (Task 9).
- Produces: `FONT_SCALE_KEY = 'pt.ui.v1'`, `type FontScale`, `FONT_SCALES`, `readFontScale()`, `applyFontScale(scale)`.

**Why an inline script and not a `useEffect`:** frmp2 applies the scale in `index.html` before React mounts (`react-site/index.html:19-29`) precisely so the page never paints at the wrong size and then jump. Reproduce that mechanism. This knob is **client-side only** — it is not in `runtime_config.OVERRIDABLE`, has no engine meaning, and must never be sent to `/api/settings`.

- [ ] **Step 1: Create the appearance module — one place that owns the key and the variable.**

Create `frontend/src/lib/appearance.ts`:
```ts
/** localStorage key. MUST match the literal in index.html's pre-paint script. */
export const FONT_SCALE_KEY = 'pt.ui.v1'

export type FontScale = 0.875 | 1 | 1.125 | 1.25

export const FONT_SCALES: { value: FontScale; label: string }[] = [
  { value: 0.875, label: 'Compact' },
  { value: 1, label: 'Default' },
  { value: 1.125, label: 'Large' },
  { value: 1.25, label: 'Largest' },
]

const isFontScale = (n: unknown): n is FontScale =>
  FONT_SCALES.some((s) => s.value === n)

/** Read the stored scale, falling back to 1 on absent/corrupt/blocked storage. */
export function readFontScale(): FontScale {
  try {
    const raw = localStorage.getItem(FONT_SCALE_KEY)
    const st = raw ? JSON.parse(raw) : null
    const fs = st && st.fontScale
    if (isFontScale(fs)) return fs
  } catch { /* private mode / disabled storage — fall through */ }
  return 1
}

/** Persist and apply. Every rem in the app is relative to --font-scale via the
 *  `html { font-size: calc(16px * var(--font-scale, 1)) }` rule in index.css. */
export function applyFontScale(scale: FontScale): void {
  document.documentElement.style.setProperty('--font-scale', String(scale))
  try {
    localStorage.setItem(FONT_SCALE_KEY, JSON.stringify({ fontScale: scale }))
  } catch { /* storage blocked — the in-session change still applies */ }
}
```

- [ ] **Step 2: Apply it before first paint.**

Replace `frontend/index.html` in full:
```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Options Paper Trader</title>
    <script>
      /* Apply the Settings text-size scale BEFORE first paint, so the page never
         renders at the default size and then jumps. Mirrors frmp2's
         react-site/index.html. The key and the shape are owned by
         src/lib/appearance.ts (FONT_SCALE_KEY = 'pt.ui.v1'); if you change one,
         change the other. Deliberately dependency-free and try/catch-wrapped:
         this runs before any bundle and must never block the app from booting. */
      (function () {
        try {
          var raw = localStorage.getItem('pt.ui.v1');
          var st = raw ? JSON.parse(raw) : null;
          var fs = st && st.fontScale;
          if (typeof fs === 'number' && fs > 0 && fs <= 2) {
            document.documentElement.style.setProperty('--font-scale', fs);
          }
        } catch (e) {}
      })();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Add the Appearance card to SettingsView.**

In `frontend/src/views/SettingsView.tsx`, add to the import block:
```tsx
import { FONT_SCALES, readFontScale, applyFontScale, type FontScale } from '../lib/appearance'
```
Add this component immediately above `export default function SettingsView()`:
```tsx
// Client-side only: the text scale is a browser preference, NOT a runtime_config
// knob. It never touches /api/settings and has no engine meaning.
function AppearanceCard() {
  const [scale, setScale] = useState<FontScale>(() => readFontScale())
  const pick = (s: FontScale) => { setScale(s); applyFontScale(s) }
  return (
    <Card className="p-3 flex flex-col gap-2">
      <div className="stat-label">Appearance — this browser only, applied instantly</div>
      <div className="text-micro text-muted">
        Scales every size in the cockpit together (body copy, headings, micro-labels, tables).
        Stored locally and re-applied before the page paints, so there is no flash on reload.
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-zinc-200 mr-1">Text size</span>
        {FONT_SCALES.map((s) => (
          <button key={s.value} onClick={() => pick(s.value)}
            className={cn(badgeVariants({ variant: 'chip' }),
              scale === s.value ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted hover:text-zinc-200')}>
            {s.label}
          </button>
        ))}
        <span className="text-micro text-muted tabular-nums ml-1">×{scale}</span>
      </div>
    </Card>
  )
}
```
Then render it as the FIRST child inside the view's root, immediately after `<div className="flex flex-col gap-3">`:
```tsx
      <AppearanceCard />
```

- [ ] **Step 4: Verify.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
grep -c "pt.ui.v1" index.html src/lib/appearance.ts   # each must be 1
```

- [ ] **Step 5: Visual check — the knob works everywhere, including micro-labels.**
Open **Settings**, click **Largest**. Confirm immediately:
- the Settings help text, group titles and the stat micro-labels all grow together;
- switch to **Trade Log**: the table, including the 11px `text-micro` labels migrated in Task 2, has grown proportionally (this is what the Task-2 rem migration bought — verify by inspecting a `text-micro` element: computed `font-size` should read `13.75px` at ×1.25, not `11px`);
- switch to **Engine / Logs**: the log pane text grew and is still monospace.

- [ ] **Step 6: Visual check — no flash on reload.**
With **Largest** selected, hard-reload the page (⌘⇧R). The app must paint at the large size on the FIRST frame — no visible jump from default to large. Then run in DevTools console `localStorage.removeItem('pt.ui.v1')` and reload: the app returns to ×1.

- [ ] **Step 7: Verify the fallback is safe.**
In DevTools console: `localStorage.setItem('pt.ui.v1', 'not json')` then reload. The app must boot normally at ×1 with no console error from the inline script. Then `localStorage.setItem('pt.ui.v1', JSON.stringify({fontScale: 99}))` and reload — the inline script's `fs <= 2` guard and `readFontScale`'s `isFontScale` check both reject it, so the app stays at ×1 and is not rendered unusable.

- [ ] **Step 8: Commit (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git add frontend/index.html frontend/src/lib/appearance.ts frontend/src/views/SettingsView.tsx && git commit -m "feat(settings): --font-scale text-size knob applied before first paint"
```

---

### Task 11: Final gate — full verification across both workstreams

**Files:**
- Modify: only what this task's checks force
- Verify: the commands in each step below

**Interfaces:**
- Consumes: everything from Tasks 1–10.
- Produces: nothing new.

- [ ] **Step 1: Frontend gates.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && npm run typecheck && npm run build
```
Both must exit 0. There is no test runner and no linter — these are the only two gates and they are non-negotiable.

- [ ] **Step 2: Backend suite (the one file this plan touched, plus the whole thing).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/backend
.venv/bin/python -m pytest tests research_tests -q --tb=short > /tmp/pt.log 2>&1; tail -3 /tmp/pt.log; grep -A5 FAILED /tmp/pt.log
.venv/bin/python scripts/dryrun.py 700
```
`dryrun.py 700` must end with the ledger reconciliation OK line (hard invariant 1). Nothing in this plan touches the engine, so a failure here means something unrelated is broken — do not ship over it.

- [ ] **Step 3: Prove the journal exception held.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git diff --stat main -- frontend/src/views/JournalView.tsx
```
Must print nothing. JournalView is excluded by spec §4 and decision D1.

- [ ] **Step 4: Prove no CDN font request exists.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend
grep -rn "fonts.googleapis\|fonts.gstatic\|@import url(" index.html src/ && echo "FOUND — fix before deploy" || echo "clean: no external font request"
ls dist/assets/*.woff2 | wc -l   # must be > 0: the fonts are bundled
```
The box is tailnet-only; an external font request would silently fail and the app would fall back to the system stack.

- [ ] **Step 5: Prove no `window.alert` survived in Settings.**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend && grep -rn "window.alert" src/views/SettingsView.tsx || echo "clean"
```

- [ ] **Step 6: Deploy (only when the owner asks).**
```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && scripts/deploy.sh --dry-run
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && scripts/deploy.sh
```
`deploy.sh` builds the SPA on the Mac and ships `frontend/dist/` in a separate targeted rsync — never build on the VPS (1GB droplet, OOM'd twice). It refuses during market hours and on a dirty tree. **After the deploy, verify with `GET /` as well as `/api/health`** — `/api/health` is a liveness stub that returned 200 through both 2026-07 outages. No new env var is introduced by this plan, so the VPS `.env` needs no hand edit.

---

## Self-review

### Spec §4 (Typography, WS-3) → task mapping

| Spec requirement | Where |
|---|---|
| Root cause: `index.css:11` `body { font-mono text-sm }` | Task 3 Step 1 |
| `--font` / `--mono` values verbatim from frmp2 | Task 1 Step 3 |
| `html { font-size: calc(16px * var(--font-scale, 1)) }` | Task 3 Step 2 |
| `body { font-size: 1rem; line-height: 1.65; -webkit-font-smoothing: antialiased }` | Task 3 Step 1 |
| `h1..h4` 1.25 / 650 / −0.015em; h1 1.9rem, h2 1.35rem, h3 1.08rem | Task 3 Step 2 (base) + Task 3 Step 3 (`.title-page/.title-section/.title-sub`) + Task 4 (applied) |
| Micro-labels 0.72–0.78rem / 700 / 0.09em uppercase | Task 3 Step 3, `.stat-label` |
| Table `th` 650 / uppercase / 0.04em | Task 3 Step 2 |
| Sans for UI and prose, mono reserved for numbers | Task 3 Steps 1–7 |
| `fontFamily: { app: 'var(--font)', mono: 'var(--mono)' }` | Task 1 Step 4 |
| Self-hosted `@fontsource` woff2, no CDN | Task 1 Steps 1–2; enforced Task 11 Step 4 |
| `--font-scale` applied pre-paint from localStorage, becomes a Settings knob | Task 10 |
| Legacy `@layer components` classes re-expressed | Task 3 Step 3 |
| Screenshot pass across 8 views, desktop and phone | Task 5 |
| Journal keeps its own language | Global Constraints; enforced Task 11 Step 3 |

### Spec §5 (Settings, WS-4) → task mapping

| Spec requirement | Where |
|---|---|
| Search across key, label and help text | Task 8 `searchHaystack` + Task 9 Step 3 |
| Collapsible groups, collapsed by default, "N overridden" count | Task 9 Steps 2–3 |
| Danger tier visually separated (the six named knobs + halt/unhalt levers) | Task 8 `DANGER_KEYS`/`GROUP_DEFS` + Task 9 Steps 1–3 |
| Units as affordances (`−30%`, `15 min`, `₹` Indian grouping) | Task 7, with the full input→output table |
| Current vs default inline, `overridden` badge kept, reset given a real label | Task 9 Step 1 (`Reset to default`) |
| Replace `window.alert(res.error)` with an inline field error | Task 9 Step 1; enforced Task 11 Step 5 |
| Preserve "every value applies live, no restart" framing | Task 9 Step 3 |
| Make a `runtime_config` override *visible* | Task 6 (API `overridden`) + Task 9 Steps 1–3 + Step 9's production-reality check |
| Real `SettingRow` type and real API contract, not guessed | Task 6 Step 3 + the contract block above Task 9 Step 1 |

### Gaps found and fixed while writing this plan

1. **Twelve knobs are invisible in the UI today.** `GROUPS` in `SettingsView.tsx:69-80` matches no group for `daily_profit_lock_pct`, `daily_profit_giveback_frac`, all four `gap_guard_*`, `entry_min_days_to_expiry`, `max_signal_age_minutes`, `entry_window_start`, `expiry_day_block_keys`, `order_failure_disarm_count` and `max_round_trips_per_day`. Several of them can halt trading. Fixed by `GROUP_DEFS`' catch-all group plus explicit `Halts` / `Day-shape guards` groups, with a script (Task 8 Step 4) proving `META` covers every `OVERRIDABLE` key.
2. **`overridden` cannot be inferred from `value !== default`.** A stored row equal to the code default shadows it forever and rendered nothing. Fixed by the additive backend field (Task 6) with a pytest for exactly that case.
3. **53 `text-[11px]` + 6 `text-[10px]` + 2 `text-[9px]` are absolute pixels**, so the `--font-scale` knob would have silently done nothing to the app's densest labels. Fixed by the rem migration in Task 2, sequenced BEFORE the body flip.
4. **`.stat-value` uses `@apply tabular-nums`, which does not emit a DOM class,** so the `[class~="tabular-nums"]` mono lever would have missed every TopBar and tile figure. Fixed by adding an explicit `font-mono` to `.stat-value` (Task 3 Step 3, regression #7).
5. **`WatchlistView.tsx:293` puts `tabular-nums` on a whole mixed-content row**, which the mono lever would have kept entirely monospace. Fixed by moving the class to the `z` cell (Task 3 Step 4).
6. **`SettingsView` had no `str` input path** — six `OVERRIDABLE` keys are strings (`expiry_day_block_keys`, `intraday_override_date`, `entry_window_start`, `gap_guard_resume`, `gap_guard_index`) and the old `<input type="number">` would have corrupted them. Fixed in Task 9 Step 1.

### Deliberate deviations from the spec, with reasons

- **Table `th` is sized `0.92em`, not the spec's `0.85rem`.** Every table in paper-trader sets its own size on the `<table>` (`text-xs` / `text-micro`); an absolute `0.85rem` header would render *larger* than its own body rows. The relative unit preserves the spec's intent (headers slightly smaller than body, uppercase, 650, 0.04em) in a dense grid.
- **`table { font-size: 0.92rem }` from the spec is not adopted** for the same reason — it would enlarge every grid. `table { line-height: 1.45 }` is adopted instead, to keep `body`'s 1.65 out of the data grids.
- **Heading classes are named `.title-page` / `.title-section` / `.title-sub`,** not `h1`/`h2`/`h3` usage, because the app contains zero `<h1>`–`<h4>` elements. The base `h1..h4` rules are still installed for any future markup.
