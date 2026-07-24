# Development Roadmap & Progress Tracker

> **This file is the agenda.** Every working session starts here: pick the top unchecked
> item in the active workstream, do it, check it off, update "Last verified". CLAUDE.md
> links here as the canonical "what's next". Keep this file honest — a checked box means
> *verified done* (tests green + the stated acceptance evidence), not "code written".

**Last verified: 2026-07-20** · Branch: `feat/exits-journal` (deployed whole-tree to VPS
2026-07-18 04:45 IST) · Suite: 800+ backend tests green · VPS: healthy, 0 engine errors
since restart, `PT_API_TOKEN` set, `PT_RESEARCH_ENABLED=0` (research dormant in prod).

> **2026-07-24 — Workstream E added** (P&L integrity → daily profit-lock → futures/MTF
> capital scaling). Two of its Phase-0 items are **live real-money P&L-misreporting bugs**;
> see the priority note in that workstream. Since 07-20 the only landed work has been the
> 07-22/23 memory-leak outage fixes (WS hub + analytics ORM scans) — no roadmap-item
> progress; the checkboxes below are still accurate.

---

## Where the project stands (one paragraph)

The **execution plane works and is live**: 24/7 VPS engine, real-money path armed daily by
the owner, journal v2, shadcn UI, safety fixes from three audit rounds deployed. **Primary
mission (owner, 2026-07-24): make the software itself COMPLETE and trustworthy before
anything else** — close the live safety bugs (Workstream B), fix the real-money P&L
misreporting, add daily profit-protection, and build out the futures/MTF segments for bigger
capital (Workstream E). The **research plane (Workstream A) is explicitly downgraded to the
LAST piece of work** — the laboratory is production-grade but the scientist was never switched
on; that is real but no longer urgent. Do not spend sessions on Workstream A until B, E, C,
and D are done.

**Active order (highest first): B (safety, on-fire items) → E (P&L integrity, profit-lock,
futures, MTF) → C (exit tuning) → D (UI) → A (research plane, last).**

---

## Workstream A — Research plane: switch on the scientist  ← **DOWNGRADED: DO LAST (owner, 2026-07-24)**

> **Deferred to the end.** Not urgent; the primary objective is now execution-plane
> completeness (B → E → C → D). Leave `PT_RESEARCH_ENABLED=0`; do not open this workstream
> until everything above it is done. The phases below are preserved as-is for when we get here.

**Vision (owner, 2026-07-20):** a reiterative, reinforcing research loop — generate its own
strategy ideas (including *formula-level* indicator variants, not just parameter tweaks),
test which idea works where, learn from past failures, shadow-paper-validate survivors
against expectations, then seek owner approval with a plain-language explanation.

**Deprioritized within this vision:** the UI→deployed-Python auto-bridge. Approved
strategies get handcoded into `app/strategy/registry/` (drop a module with `STRATEGY`,
auto-discovered). Composition *generation* stays core — only the auto-deploy leg is parked.

### Phase 0 — Honest statistics *(do first; everything downstream inherits its trust)*
- [ ] Thread real trial counts: one search session = one trial family; `n_trials` =
      compositions × param draws × folds actually evaluated, passed into `build_scorecard`
      (today `run_generated` scores each composition with `n_trials=1`).
- [ ] Compute `var_sr` across the session's trial Sharpes and pass it through (today it
      defaults to `0.0`, which makes `expected_max_sharpe()` return 0 → **deflation never
      engages anywhere**). Fix the false claim in `builder/search.py`'s docstring.
- [ ] Implement PBO via CSCV over the existing walk-forward folds (`research/stats/`);
      gate promotion candidates on PBO ≤ threshold.
- [ ] Wire `stats/neff.py` (correlated-universe effective-N) into the evidence gate.
- [ ] Fix the known optimizer objective bug: `pipeline/optimize.py::_objective` = raw
      expectancy; replace with trade-count-aware objective (t-stat or bootstrap-LB).
- **Acceptance:** a synthetic no-edge universe swept with a wide search produces **zero**
  promotion candidates; the same sweep with deflation stubbed off produces several.
  TDD in `research_tests/`.

### Phase 1 — Turn the nightly loop on (shadow mode)
- [ ] Implement `nightly._load_plan()`: open hypotheses ordered by `retest_priority` ×
      research-eligible universe (permanent commodity sandbox + instruments not committed
      to a live watchlist; seed from the sector edge map — bullion, capital-markets,
      PSU-financials first).
- [ ] Nightly invokes `run_generated` (not just handwritten strategies) on that plan.
- [ ] Decide + document where the cron runs (VPS 19:00 IST as designed, or Mac against
      cached candles). Flag on **in shadow**: reports + research.db only, nothing deployed.
- **Acceptance:** after one week, research.db holds a real Findings corpus from unattended
  runs; reports land in `PT_RESEARCH_REPORT_DIR`.

### Phase 2 — Widen the idea space (incl. formula-level variation)
- [ ] New blocks (each a pure, tested function in `builder/blocks.py`): RSI, volume/OBV,
      opening-range breakout, gap, time-of-day window, candle structure.
- [ ] **Price-source as a block parameter** (`close | hl2 | hlc3 | ohlc4`) and
      **smoothing-kind as a parameter** (`sma | ema | wilder | hull`) — this is the
      owner's "modified-RSI" ask generalized: hundreds of lawful indicator variants,
      still whitelisted, still auditable.
- [ ] Replace the fixed 18-combo enumerate grid with seeded random sampling within
      grammar bounds (deterministic per seed; breadth feeds Phase-0 deflation).
- **Acceptance:** nightly explores new compositions each night; DSR bar visibly rises
  with search breadth (log the deflation benchmark per session).

### Phase 3 — Close the reinforcement loop (make it *learn*)
- [ ] Generation READS knowledge: mutate surviving compositions (param nudges, single
      block swaps); suppress block-families that repeatedly die on an instrument cluster.
- [ ] `retest_priority` finally gets its consumer (today: written, never read).
- [ ] Maintain a `block-family × instrument` edge map table — "which idea works where" —
      used as sampling weights and rendered in the research report.
- **Acceptance:** night N's plan is provably a function of nights 1..N−1's Findings
  (test: seed a poisoned family, watch it get suppressed; seed a survivor, watch mutants).

### Phase 4 — Shadow-paper stage before approval
- [ ] New candidate state between "validated" and "pending approval": auto-run on a
      research-side paper book against live candles for N sessions (research plane only —
      never the live engine's book).
- [ ] Surface to owner only with a shadow-vs-backtest scorecard: hit rate, avg R,
      expectancy vs confidence bands ("did reality match the promise").
- [ ] Reuse `strategy/explain.py` for the plain-language "what it does" at approval time.
- **Acceptance:** no candidate reaches the approval queue without ≥N shadow sessions and
  an expected-vs-realized comparison attached.

### Phase 5 — Regime conditioning *(only after 0–3 produce trustworthy data)*
- [ ] Label bars into regimes (trend/chop × vol buckets); evaluate blocks per regime;
      let the generator condition on current regime. (Regime labels multiply trial count —
      which is why Phase 0 must exist first.)

### Isolation rules for ALL research-plane work (verified holding 2026-07-20)
1. `app/` may import `research/` **only** via the read-only bridge
   (`app/core/research_read.py`, `app/core/generated_strategies.py`,
   surfaced by `app/api/portfolio_routes.py`). Nothing else.
2. `research/` may import from `app/` **only** pure/read-only seams: `app.core.config`,
   `app.core.market_hours`, backtest kernels via `research/evaluation/kernels.py`, and
   the strategy registry. Never broker/runner/db.session — `research/guards.py` enforces
   this fail-closed; do not weaken it.
3. Separate DBs (`research.db` vs `paper_trader.db`), separate tests
   (`pytest research_tests` vs `pytest`), separate flag (`PT_RESEARCH_ENABLED`, **off in
   prod until Phase 1 shadow mode is deliberately enabled**).
4. Every session ends with BOTH suites green + `scripts/dryrun.py 700` ledger-exact.
   Research work must produce an empty diff under `backend/app/` except the sanctioned
   bridge/kernel files above.

---

## Workstream B — Safety backlog (from the 2026-07-18 review; full report in
`docs/2026-07-18-safety-research-product-review.md`)

- [ ] **E1 (worst, silent, still live):** poisoned open-position key aborts the risk
      loop's mark/exit for the WHOLE book (`runner.py:465` unguarded
      `get_instrument(k)`). Fix: per-position try/except + refuse instrument removal
      while a position is open. **Operational rule until fixed: never remove/deactivate
      an instrument that has an open position.**
- [x] E2 `PT_API_TOKEN` fail-open — verified CLOSED on VPS 2026-07-20 (64-char token set).
- [ ] E3 options GTT stop divergence (modify-reject only logs; no cancel+replace).
- [ ] E4 phantom close: `routes.py:603` returns `{closed:true}` on failed close.
- [ ] E7 equity SHORT charge legs hardcoded BUY/SELL; E8 `account_pnl` LONG-only sign.
- [ ] E9 options entry-LIMIT tick rounding; E10 overnight flatten has no segment filter.
- [ ] VPS pending OS reboot (5 ESM security updates) — owner action, DO console,
      market-closed window.
- [ ] One-off `journal_days already exists` create_all race at startup — make idempotent.

## Workstream C — Exit tuning (winners being cut; roadmap approved 2026-07-15)

- [x] P1 exit autopsy on real VPS trades (2026-07-15).
- [x] Bake the interim exit params in as code DEFAULTS (2026-07-21, PAYTM early-exit
      complaint): sl 0.008, target 0.03, lockstep_trigger 0.03, lock_threshold 600,
      lock_frac 0.3 (config.py). Purple bands widened to stay strictly wider than the
      new normal band: purple sl 0.015 / target 0.045. **NOTE:** any existing VPS
      `runtime_config` overrides for these keys still SHADOW the new defaults — clear
      them in Settings (or they must be re-set) after the next deploy+restart.
- [ ] P2 offline exit-param sweep on replayed VPS trades, walk-forward; add a
      BE-arming-threshold knob; finer `exit_reason` tags. (Opus-tier judgment task.)
      **Blocked on Workstream E-Phase-0 peak-excursion (MFE/MAE) telemetry** — give-back is
      unmeasurable from the trade log until that lands. Live evidence (07-24): the managed
      profit-capture path is effectively inert — over 33 live intraday trades not one closed
      on `TARGET` or a managed profit-locking stop; winners leaked out via EOD square-off /
      external reconcile (avg net ₹12.6/trade). Likely root: `intraday_profit_lock_threshold`
      ₹600 sits *above* the typical winner, so the tight lock never arms in the ₹0–600 band.
- [ ] P5 MTF (Margin Trading Facility) engine — spec gate first, built last. **→ moved
      to Workstream E-Phase 3 (un-parked 2026-07-24, owner wants it for bigger capital).**

## Workstream E — P&L integrity → daily profit-lock → capital scaling (futures/MTF)

**Owner directive (2026-07-24).** A cluster added after a live-trading session: two of these
are **real-money correctness bugs** (P&L is being *misreported*), one is a profit-protection
feature the owner explicitly wants, and two are new capital-scaling segments for when the book
grows. **This is dependency-ordered on purpose — accurate P&L is the foundation every later
phase inherits. Do NOT build the daily profit-lock, futures, or MTF on top of an inaccurate
P&L base.** The goal is to write one "goal prompt" later that executes this whole workstream in
bulk; keep each phase spec'd tightly enough for that.

**Priority note (RESOLVED, owner 2026-07-24):** **all of Workstream E outranks the research
plane** — E is part of "make the software complete", A is now last. Within the active order
(B → E → C → D → A): E0 is a live real-money correctness defect, do it first; then E1, E2, E3
in sequence. This whole workstream is the target of the eventual bulk "goal prompt".

### Phase E0 — P&L integrity *(FOUNDATION; real-money correctness — B-tier priority)*
- [ ] **Exit booked at the TRUE fill, not the last mark.** `live_broker.reconcile_orphans`
      books an options `RECONCILED_EXTERNAL_EXIT` at `pos.last_premium` (the last mark) —
      `live_broker.py:865,901` — so a manual/external close is mis-priced. The equity R3 path
      already fetches the resting SL-M's real avg fill (`live_broker.py:879-895`); generalize
      that: on any reconcile/manual/external close, read the actual fill from the order status
      / day's tradebook for that symbol and book at that price. Fall back to last mark only if
      unavailable, and TAG the trade as an estimate. **Owner evidence (2026-07-24):** SENSEX
      put exited at +₹792 pre-charges; bot recorded ~₹1,000. Overlaps safety E4 (phantom close).
- [ ] **Equity curve anchored to the REAL account value, not the ₹50k synthetic base.**
      `analytics.equity_curve` + `initial_capital=50_000` (`config.py:49`) drive the curve off
      the seeded ledger. In live mode the baseline must be the real broker equity (drive it via
      the existing `ledger_reconcile.plan_reanchor` on live start / funds refresh) and each
      point = cash + open-position MTM net of charges from actual account funds — not the
      synthetic 50k ledger. Frontend reads the corrected backend values, so this fixes the UI too.
- [ ] **Peak-excursion telemetry** (carried over from the 2026-07-24 exit-tuning thread):
      record MFE (high-water) + MAE per trade. Prerequisite for measuring give-back — feeds
      both Workstream C-P2 and Phase E1. (No high_water is stored today, so give-back is
      currently unmeasurable from the trade log.)
- **Acceptance:** a reconciled/manual exit books within a paisa of the injected broker fill
  (mock: fill price ≠ last mark → the trade records the fill, not the mark); a fresh live
  account's equity curve starts at real funds, not ₹50k; every closed trade has mfe/mae
  populated. TDD in `tests/`; `dryrun.py 700` still ledger-exact.

### Phase E1 — Daily profit-lock (portfolio high-water give-back guard)
- [ ] The symmetric twin of the existing `daily_loss_halt` (`risk_controls.py:165`): a
      `daily_profit_lock` that tracks the day's realized+unrealized **high-water**; once daily
      P&L clears `daily_profit_lock_pct` of **daily deployed capital**, arm a floor at
      `daily_profit_giveback_frac` of the peak; if the day retraces to the floor →
      **square off ALL open positions and halt new entries for the rest of the day**. Sits next
      to `max_daily_loss` / `max_open_drawdown` / `max_round_trips_per_day` (already in config);
      new knobs live-editable via `runtime_config`, `0 = off`.
- **DESIGN DECISIONS (RESOLVED, owner 2026-07-24):**
    - **Base = daily *deployed* capital, NOT total account equity.** If the owner only puts
      10% of the account to work that day, the % is measured against *that* deployed sum, so
      the lock respects the chosen risk. (Implementation: track the day's committed capital —
      Σ margin/entry-cost actually deployed — as the denominator; decide the exact definition
      when there are partial exits/re-entries during the build.)
    - **Give-back action = FLATTEN ALL + HALT.** On breaching the floor, square off every open
      position (all segments) and block new entries for the remainder of the session. This is
      the one exit path where the ARM gate does not apply (exits always run — see Safety model),
      so it works even when disarmed.
    - **High-water trails up:** a new intraday peak raises the floor; the lock never loosens.
- **Owner story (2026-07-24):** bot was up ~₹1,400 (~1.5% of deployed) early, then over-traded
      it back down with decent-loss trades; owner wanted to lock ~₹700 (≈half the peak) and stop.
- **Acceptance:** replay a day that peaks at +2% then reverses → guard armed halts entries at
  the give-back floor and the day closes ≥ floor; guard off reproduces the full give-back. TDD.

### Phase E2 — Index-futures segment *(aligns with the index-first product direction)*
- [ ] New segment `index_futures`, on its own entry/mark/exit path (mirror how
      `equity_intraday` is isolated so the options path stays untouched). Lot sizes +
      SPAN+exposure margin sizing; futures charge legs in `charges.py` (already segment-aware);
      MTM on the futures LTP; direction-aware SL/TP + lockstep reuse. **Spec gate first**
      (owner + Fable review) before any build. Index ranks above stock futures per the
      CLAUDE.md index-first direction.
- [ ] **INTRADAY-ONLY, NO ROLLOVERS, NEVER HOLD TO DELIVERY (owner, 2026-07-24).** The
      strategy is still primarily intraday: futures positions are force-flat before close like
      equity_intraday; the engine performs **no rollover** to the next series, ever. **Hard
      guard: refuse to open (or force-close) any futures contract inside its physical-delivery
      window** — this matters for MCX commodity futures (e.g. gold near-month enters a
      compulsory-delivery/tender period before expiry). During the build, look up the exact
      per-instrument delivery/tender-start rules (MCX staggered-delivery calendar for
      commodities; cash-settled index futures have no delivery risk) and encode a
      `no_delivery_window` block driven by that calendar. Prefer cash-settled index futures;
      any deliverable contract must be blocked in its delivery window.
- [ ] **Accurate P&L** (owner emphasis — "that's where the money is"): futures P&L =
      (exit−entry)×lot×qty net of the full F&O charge stack; SPAN+exposure margin sizing must
      be modeled correctly (this is the tricky part). Verify both against a real contract note.
      Depends on E0.
- **Acceptance:** `dryrun.py 700` stays paisa-exact with a futures position open; modeled
  charges + margin match a real F&O contract note within tolerance; a deliverable contract in
  its delivery window is refused/force-closed by the guard (TDD with a stubbed calendar).

### Phase E3 — MTF (Margin Trading Facility) segment *(un-parks C-P5; built last)*
- [ ] New `mtf` product: pledge/funded delivery positions, broker interest/carry-cost accrual
      modeled into P&L, multi-day position lifecycle, margin/haircut. **Spec gate first, built
      last** — the most complex; interest accrual makes P&L multi-day. Bigger-capital feature
      (owner: "with bigger capital we'd actually wanna trade these").
- **Acceptance:** a multi-day MTF position accrues the correct daily interest cost in the
  ledger; P&L net of carry matches a hand-computed example. TDD.

## Workstream D — UI typography & palette

- [ ] Extract font + color scheme from the owner's reference site
      (`ag-website-git-main-match-up.vercel.app` — behind Vercel deployment protection;
      needs the Chrome extension or owner-supplied font names). **Fonts first; palette
      later.**
- [ ] Apply fonts app-wide (self-host via `@fontsource/*`, wire into
      `tailwind.config.js` + `index.css`; the VPS serves the built dist, so no CDN
      dependency). Keep the established chip/dense-table conventions
      (see `WatchlistView.tsx` header comment).
- [ ] Palette pass after fonts, mapped onto the existing shadcn CSS variables
      (remember: `muted` is a load-bearing Tailwind color — merge, don't replace).
- [ ] Mobile 390px one-handed check (never verified; extension can't reflow viewport —
      check on the actual phone).

## Parked / deprioritized (deliberate — don't burn sessions here)

- UI→deployed-Python codegen bridge (owner, 2026-07-20: handcoding approved strategies
  is fine; the approve→deploy bridge that exists already is enough).
- Stock-specific options work (CLAUDE.md: equity/index-first; options index-only, later).
- Product avenues from the 2026-07-18 review (revisit after Workstream A ships).

---

## Session protocol (how we maximise return per Claude session)

1. Read CLAUDE.md, then this file. Work the **topmost unchecked item of the highest
   active workstream** (A unless something in B is on fire).
2. TDD; both test suites + `dryrun.py 700` green before any "done" claim.
3. Update this tracker in the same commit as the work (checked box = verified evidence).
4. Deploys to the VPS are whole-tree rsync + restart — see the deploy mechanics note in
   the session memory; never deploy with an un-armed-safe book assumption; `.env`, DBs,
   and `access_token.json` are excluded by the rsync filter.
5. Model split (owner directive): Fable = advisor/architect/review, Sonnet = build,
   Opus = optimization judgment.
