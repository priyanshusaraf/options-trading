# Roadmap: exit-policy retune · UI overhaul · trade journal · MTF engine

**Date:** 2026-07-15 · **Status:** approved (gating decisions below) · **Author:** Fable 5 (advisor) with owner

**Owner decisions (2026-07-15):** VPS read-only access granted, anytime ·
MTF = Zerodha Margin Trading Facility confirmed · no merge to main — new work
on `feat/exits-journal` off `feat/research-plane` head; research plane resumes later.

## Context

Live session 2026-07-15 surfaced a systematic exit problem: winners are not being
ridden (DLF realized +183 vs ~+600 available; MARUTI similar) and several trades
were scratched at +30-40 — below round-trip costs. Separately: the UI needs a full
redesign (desktop + mobile), the strategy-developer/research plane is being frozen,
a discretionary trade journal has been spec'd (see
`docs/superpowers/specs/` journal design, this session), and an MTF product path
is wanted.

## Diagnosis (code-level, to be confirmed against VPS data in P1)

All three exit mechanisms live in `backend/app/engine/equity_entry.py` and are
driven by `Settings` knobs (`core/config.py:174-186`):

1. **Break-even floor arms on the first lockstep step.**
   `intraday_lockstep_trigger_pct = 0.02` → one step per 2% of margin = **₹160 on
   ₹8k**. `lockstep_band` floors the stop at `breakeven_price` as soon as
   `slide > 0`, i.e. the moment a trade is +₹160. Entry-zone chop then exits at
   ≈ +costs → the observed +30-40 scratches ("closed randomly").
2. **Profit-lock frac 0.5 structurally cuts winners.**
   `intraday_profit_lock_threshold = 200`, `intraday_profit_lock_frac = 0.5`:
   past +₹200 the stop is floored at entry + costs + 50% of the favourable move,
   ratcheting on every new high. Intraday trends routinely retrace 40-60% →
   the lock fires on healthy pullbacks → DLF +183 instead of +600.
3. **Base stop inside noise.** `intraday_stop_loss_pct = 0.01` (1% of price) is
   below typical intraday ATR for many liquid NSE names; `intraday_target_pct =
   0.02` caps the initial band at 1:2.

Key asset: `lockstep_band`, `equity_exit`, `resolve_sltp`, `equity_stop_target`
are **pure functions** — an offline simulator can replay live trades and sweep
parameters through the exact production code path.

## Phases

### P0 — Hygiene & research-plane freeze (small; do first)

- **Owner decision 2026-07-15: no merge.** `feat/research-plane` stays open —
  more work is planned there later. All new work (P1-P4) happens on a new
  branch cut from its current head: **`feat/exits-journal`**. (Backup note:
  nothing is pushed to origin yet; owner will push when ready.)
- **Freeze the strategy-developer/research plane**: feature flag (e.g.
  `PT_RESEARCH_UI=false` default) that hides its tabs and skips starting its
  loops. No code deleted; its tests keep running; branch stays as-is.
- Agents: 1 Sonnet 5 subagent, TDD; Fable reviews.

### P1 — Exit autopsy on real trades (needs owner OK for VPS read-only access)

- `scp` read-only slices from the VPS: `trades`, `positions`, `order_journal`,
  `signal_events` for the last ~10 sessions + relevant journalctl windows. No
  writes, no restarts.
- Replay every closed intraday trade through the pure exit kernels against
  Kite 1-minute candles for that day: classify the true exit cause
  (BE-floor / profit-lock / base SL / TP / strategy-exit / square-off /
  exchange SL-M divergence), record MFE/MAE, and compute counterfactual P&L
  with each mechanism disabled.
- **Fan-out (Workflow):** one Sonnet 5 agent per instrument-day replay;
  Opus 4.8 synthesizes loss attribution ("profit-lock cost ₹X over N trades;
  BE-floor cost ₹Y").
- Deliverable: `docs/exit-autopsy-2026-07.md` — confirmed mechanism ranking.

### P2 — Exit-policy optimizer → new defaults (the money fix)

- Build an offline **exit-policy simulator** in `backend/scripts/` reusing the
  pure kernels + Kite minute data (60-day API limit for 1m; 15m for longer
  lookback). Entries = the recorded live entries (P1) plus backtest-signal
  entries for sample size.
- Sweep (grid + walk-forward, net of charges):
  `intraday_stop_loss_pct`, `intraday_target_pct`,
  `intraday_lockstep_trigger_pct`, `intraday_profit_lock_threshold`,
  `intraday_profit_lock_frac`, **new knob: BE-floor arming threshold**
  (floor at break-even only once profit ≥ k × round-trip costs, not on step 1),
  and an ATR-scaled stop variant vs fixed-%.
- Objective: maximize expectancy subject to max-drawdown and scratch-rate
  constraints; strict walk-forward (train/validate split by date) to avoid
  overfitting to one week.
- **Agents:** Sonnet 5 builds the harness (TDD); fan-out Sonnet 5 sweep
  runners; **Opus 4.8 judges the parameter frontier**; Fable reviews and
  owner signs off on final values.
- Implementation: new knobs added to `Settings` **and** `runtime_config`
  (live-editable, per repo convention); finer `exit_reason` tags
  (`LOCKSTEP_BE`, `PROFIT_LOCK`, …) so future autopsies are one query;
  full suite + `scripts/dryrun.py` ledger invariant green.
- Deploy: rsync + restart off-market hours; verify log markers (established
  routine per 2026-07-14 deploy).

### P3 — UI overhaul (runs in parallel with P2; frontend-only)

- **Foundation first, one agent, reviewed before fan-out:** shadcn/ui onto the
  existing Tailwind 3.4 / React 18 / Vite stack; design tokens + dark theme;
  responsive app shell — bottom tab bar on mobile, sidebar/top bar on desktop;
  typography, spacing, card/table/sheet primitives. `LiveContext` and
  `lib/api.ts` untouched.
- **Per-view re-skin fan-out** in worktree-isolated Sonnet 5 agents, priority
  order: Watchlist → Positions → **Backtests (mobile-first: launch + monitor a
  sweep from the phone)** → Trades → Dashboard/Performance → Settings → Engine.
- Each view agent must pass `npm run typecheck` and produce 390px-width
  Playwright screenshots; Fable reviews every screenshot before merge.
- Acceptance: every view usable one-handed at 390px over the tailnet.

### P4 — Trade journal build (after P3 foundation lands)

- Build per the approved design from this session: own `journal.db`,
  append-only views (long-term + current horizons), trades bound to the view
  live at entry, live MTM via the existing provider, manual-or-computed P&L
  (manual = net, charges never double-applied), setup-tag attribution,
  performance net of real charges via `engine/charges.py`.
- Journal instrument list is its own (GOLDM, SILVERM, **CRUDEOILM, NATGASM**
  minis — note the bot's universe has full-size CRUDEOIL/NATURALGAS, wrong
  multipliers for the owner's manual trading), specs resolved from the Kite
  instruments dump.
- Mobile-first on the new design system. Sonnet 5 agents per layer (backend
  TDD, then frontend); Fable reviews.

### P5 — MTF engine (spec gate before any code)

- **Assumption to confirm:** MTF = Zerodha Margin Trading Facility —
  leveraged *delivery* (product=MTF), positions held days-weeks, interest
  ~0.04%/day on the funded amount, MTF-approved NSE list only.
- This is a new product path, not a tweak: no intraday force-flat, overnight
  gap risk policy, interest accrual in `charges.py`, margin/pledge mechanics,
  swing-horizon exits on 60m/daily bars, sizing rules.
- Process: brainstorm → spec → TDD build mirroring the `equity_intraday`
  separation pattern (own module, own tests, options/intraday paths untouched).
  Paper-validated before any live MTF order.

## Model & agent orchestration (owner directive)

| Role | Model | Used for |
|---|---|---|
| Advisor / architect / reviewer | **Fable 5** (main session) | specs, plans, diff + screenshot review, final calls |
| Implementation subagents | **Sonnet 5** | all TDD build work, view re-skins, sweep runners, replay agents |
| Optimization / judgment | **Opus 4.8** | P1 loss-attribution synthesis, P2 parameter-frontier analysis |

Fan-outs run as Workflows (P1 replay, P2 sweep, P3 view re-skins with worktree
isolation). Everything else is single subagents with Fable review between steps.

## Sequencing & rationale

```
P0 ──► P1 ──► P2 ──────────► deploy exit fix
 └────► P3 ─────► P4                    └──► P5 (spec anytime, build last)
```

P1/P2 first — the exit policy is losing money every live session. P3 is
frontend-only and parallels P2 safely. P4 rides on P3's foundation. P5 is new
capability and goes last, but its spec conversation can happen whenever.

## Risks

- **Minute-data limit:** Kite serves ~60 days of 1m candles → sweep uses 1m for
  recent window + 15m for longer validation.
- **Overfit:** walk-forward split + out-of-sample holdout; Opus judges frontier
  stability, not just peak expectancy.
- **Whole-tree deploys:** VPS deploy is rsync of everything → UI and engine
  changes ship together; deploy only off-market, verify markers each time.
- **Unpushed production branch (P0):** single biggest current risk; fixed first.
