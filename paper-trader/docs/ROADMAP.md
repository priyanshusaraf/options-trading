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

**All code items CLOSED 2026-07-25 (TDD, each defect reproduced RED before the fix).
Committed, suite green, NOT yet deployed — the live VPS process runs the old code until
an rsync + `systemctl restart paper-trader`.**

- [x] **E1 (was the worst, silent, live):** poisoned open-position key aborted the risk
      loop's mark/exit for the WHOLE book. `runner._resolve_or_skip()` now resolves
      per-position and alerts once; `square_off_intraday` falls back to the NSE clock
      rather than skipping (MIS cannot legally carry); `remove_instrument` refuses while
      a position is open. **The operational rule "never remove an instrument with an open
      position" is retired.** `tests/test_poisoned_position_key.py`
- [x] E2 `PT_API_TOKEN` fail-open — verified CLOSED on VPS 2026-07-20 (64-char token set).
- [x] E3 options GTT stop divergence — `_resync_option_gtt` mirrors the equity
      cancel+replace, refuses a second GTT if the cancel fails, and leaves the id None so
      the self-heal retries. `tests/test_option_gtt_ratchet_sync.py`
- [x] E4 phantom close — the route checks the broker return; a refused close answers
      `{error, closed:false}` and keeps display state + re-entry intact. Frontend `act()`
      surfaces the error (no frontend test harness exists — UI half is test-unverified).
      `tests/test_phantom_close.py`
- [x] E6 options orphan mislabelled the bot's OWN GTT fill as an external exit (corrupted
      exit-reason analytics + false same-day re-entry block). New `client.gtt_status()`
      (a trigger_id is not an order_id); conservative fallback keeps the block on any
      failed read. `tests/test_option_gtt_fill_reconcile.py`
- [x] E7 equity SHORT charge legs — new `charges.legs_for(direction)` used on all three
      equity paths, so a SHORT is charged SELL-to-open / BUY-to-cover and `net_pnl`
      reconciles against the contract note. `tests/test_equity_short_charge_legs.py`
- [x] E8 `account_pnl` LONG-only sign — defers to `Position.unrealized_pnl()`.
      `tests/test_account_pnl_short_sign.py`
- [x] E9 options entry-LIMIT tick rounding — `place()` snaps `limit_price` to the real
      per-instrument tick. `tests/test_limit_price_tick.py`
- [x] E10 overnight flatten segment filter — `square_off_for_overnight` skips
      `equity_intraday` (it was closing equity for "expiry too close (0d < 2d)");
      `square_off_intraday` is the sole MIS authority.
      `tests/test_overnight_segment_filter.py`
- [x] `journal_days already exists` create_all race — `_get_sessionmaker()` was an
      unlocked lazy singleton (reproduced 8/8 concurrent inits); now double-checked
      locking, publishing the sessionmaker last. `tests/journal/test_init_race.py`
- [ ] **VPS pending OS reboot (5 ESM security updates) — OWNER ACTION**, DO console,
      market-closed window.
- [ ] **Deploy these fixes** — `scripts/deploy.sh` (it runs both suites + dryrun,
      restarts, and verifies `.env`, the built SPA, `GET /`, `/api/health`, and the
      reported build SHA). Never hand-roll the rsync.

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
- [x] **Exit booked at the TRUE fill, not the last mark.** (2026-07-24, built by Sonnet 5,
      reviewed by Opus.) `live_broker.reconcile_orphans` now asks the broker's order book for
      the real SELL fill before booking an options external/reconciled close — new
      `KiteOrderClient.find_fill(symbol, side)` scans today's COMPLETE orders; books at that
      fill (not `last_premium`) when found, else falls back to the mark AND tags the trade
      `exit_price_estimated=True`. The equity R3 fallbacks (stop-status read fail / stop still
      resting) and the manual paper-close override are tagged estimates too. New `Trade.
      exit_price_estimated` column (+ additive migration). Evidence: `test_live_broker.py`
      proves a mock fill of 123.45 ≠ mark is booked at 123.45 with estimated=False, and the
      no-fill path books the mark with estimated=True; equity R3 real-fill stays estimated=False.
      Full suite green + `dryrun.py 700` LEDGER OK (diff +0.0000). ORIGINAL SPEC:
      books an options `RECONCILED_EXTERNAL_EXIT` at `pos.last_premium` (the last mark) —
      `live_broker.py:865,901` — so a manual/external close is mis-priced. The equity R3 path
      already fetches the resting SL-M's real avg fill (`live_broker.py:879-895`); generalize
      that: on any reconcile/manual/external close, read the actual fill from the order status
      / day's tradebook for that symbol and book at that price. Fall back to last mark only if
      unavailable, and TAG the trade as an estimate. **Owner evidence (2026-07-24):** SENSEX
      put exited at +₹792 pre-charges; bot recorded ~₹1,000. Overlaps safety E4 (phantom close).
- [x] **Equity curve anchored to the REAL account value, not the ₹50k synthetic base.**
      (2026-07-24, built by Sonnet 5, reviewed by Opus.) New `EngineRunner._maybe_auto_reanchor`
      fires ONCE on a fresh live account — inside the live-only `_maybe_refresh_funds`, gated on
      book FLAT + untouched synthetic base (`initial_capital==50k`, `realized_pnl==0`, zero
      `trades` rows) — and re-anchors `capital_state` to the real broker equity (`funds["net"]`)
      via the existing `ledger_reconcile.plan_reanchor`. `snapshot()`'s `cash+mtm` formula is
      unchanged, so the curve then opens at real funds. Write goes THROUGH the broker's own
      long-lived session (Opus review caught a first cut that wrote via a separate session:
      `expire_on_commit=False` left `broker.capital()` stale at ₹50k → next `snapshot()`/close
      would clobber the reanchor back to the synthetic base; regression test now asserts through
      the broker session + a post-reanchor `snapshot().equity==real`). NEVER fires once any live
      trade history / open position exists — that stays the owner's `scripts/reconcile_ledger.py`
      path. Mock/paper is a no-op (dryrun still starts at ₹50k, LEDGER OK diff +0.0000).
      Tests: `test_auto_reanchor.py` (6 cases). ORIGINAL SPEC:
      `analytics.equity_curve` + `initial_capital=50_000` (`config.py:49`) drive the curve off
      the seeded ledger. In live mode the baseline must be the real broker equity (drive it via
      the existing `ledger_reconcile.plan_reanchor` on live start / funds refresh) and each
      point = cash + open-position MTM net of charges from actual account funds — not the
      synthetic 50k ledger. Frontend reads the corrected backend values, so this fixes the UI too.
- [x] **Peak-excursion telemetry** — DONE 2026-07-24 (built by Sonnet 5, reviewed by Opus).
      New `Position.mfe`/`mae` + `Trade.mfe`/`mae` (₹ unrealized-P&L excursion, segment/
      direction-aware via `unrealized_pnl()`), updated at the single `mark()` chokepoint and
      copied onto every Trade at close (incl. both partial-close paths). Additive migrations.
      **Opus review caught a hot-path regression:** the mock's `np.float64` premiums leaked
      through into the `mfe/mae` ORM writes and intermittently corrupted SQLAlchemy's
      unit-of-work bookkeeping → `StaleDataError` on the `mark_and_exit_positions` commit
      (deterministic at `PYTHONHASHSEED=6`, clean on baseline). Fixed by casting to Python
      `float`; guarded by two regression tests (`test_mark_stores_python_float_not_numpy` +
      a seed-6 dryrun subprocess). Pure telemetry — ledger untouched: `dryrun.py 700` LEDGER OK
      across seeds incl. the former failure seed. Tests: `test_excursion.py` (8 cases).
      ORIGINAL SPEC:
      record MFE (high-water) + MAE per trade. Prerequisite for measuring give-back — feeds
      both Workstream C-P2 and Phase E1. (No high_water is stored today, so give-back is
      currently unmeasurable from the trade log.)
- **Acceptance:** a reconciled/manual exit books within a paisa of the injected broker fill
  (mock: fill price ≠ last mark → the trade records the fill, not the mark); a fresh live
  account's equity curve starts at real funds, not ₹50k; every closed trade has mfe/mae
  populated. TDD in `tests/`; `dryrun.py 700` still ledger-exact.

### Phase E1 — Daily profit-lock (portfolio high-water give-back guard)
- [x] DONE 2026-07-24 (built by Sonnet 5, reviewed by Opus). Pure `daily_profit_lock`
      in `risk_controls.py` (twin of `daily_loss_halt`) + runner state (`_pl_high_water`,
      `_pl_deployed_peak`, `_pl_halted_date`, reset each session) maintained every risk tick
      in `_maybe_profit_lock`; on give-back breach it calls a new `_square_off_all` (factored
      out of `kill()`, now the single flatten impl) and sets a sticky session halt that
      `_entries_halted`/`halt_status` honour. **Denominator = PEAK CONCURRENT deployed capital
      today** (max Σ open entry_cost; not cumulative, so re-entries don't inflate it — Opus
      decision). Knobs `daily_profit_lock_pct` (fraction, 0=off) + `daily_profit_giveback_frac`
      in config + runtime_config (live-editable, bounded). Default off → zero behavior change
      (verified: full suite green, `dryrun.py 700` LEDGER OK across seeds 6/11/17/29). Tests:
      `test_daily_profit_lock.py` (12: pure off-switches/arming/exact-floor/trailing +
      runner climb→giveback flatten+block, guard-off reproduces give-back, high-water never
      loosens, kill() still flattens post-refactor). **Owner tuning caveat (flagged by Opus):**
      early-day, peak-concurrent-deployed can be small, so a low `lock_pct` may arm+halt the
      whole session on a tiny peak; consider a future `min_deployed` floor knob. ORIGINAL SPEC:
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

> **SPEC WRITTEN + OPUS-REVIEWED, AWAITING OWNER/FABLE + A CONTRACT NOTE (2026-07-24).**
> Full spec: `docs/2026-07-24-E2-index-futures-spec.md` (Sonnet-drafted, Opus-reviewed).
> **The build is gated — not started — for two mandate reasons:** (1) the acceptance bullet
> "margin+charges match a real F&O contract note within tolerance" is unverifiable in-repo
> (the paper SPAN margin is a flagged **12%-of-notional estimate**; SENSEX **`BFO_FUT`
> charges don't exist yet**); the owner must supply a real Zerodha index-futures contract
> note (or a live `order_margins()` reading) to confirm those numbers. (2) the roadmap's own
> "spec gate first (owner + Fable review)" — several defaults (margin %, position/margin
> tiers, paper-only-first) need owner sign-off. Spec also surfaced a real build item: **futures
> LTP isn't fetchable today** (marking to spot mis-prices by the basis → needs a new provider
> method). Isolation, `NFO_FUT` charges, delivery-guard (no-op for cash-settled index +
> stubbed commodity calendar), force-flat/no-rollover, and dryrun-exactness ARE all buildable
> and verifiable now — the build plan (13 TDD steps) is in the spec, ready to execute once the
> gate clears. E3 (MTF) is even more contract-note-dependent (carry/interest, haircut) and stays last.
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

## Workstream F — Infrastructure, persistence & deploy safety (unscheduled)

Carried forward 2026-07-28 from the
[2026-07-23 memory-leak post-mortem](incidents/2026-07-23-memory-leak.md) when it was moved
out of `CLAUDE.md`. Operational detail in `docs/operations.md`. None of these are scheduled
against B/E/C/D — pick them up when one becomes urgent.

- [ ] **Resize the droplet 1GB → 2GB — OWNER ACTION** (DO console). The 2026-07-23 OOM was
      caused by two memory leaks, both fixed and deployed, but 1GB leaves no headroom.
- [ ] **Decide the DB-bloat approach — OWNER DECISION, then build.** `paper_trader.db` is
      ~45MB, +~5MB/day, from unbounded append-only `option_data` (~154k), `signal_events`
      (~86k), `equity_snapshots` (~72k). Candidates: retention/pruning, a split archive DB,
      or moving the time-series off SQLite. Owner wants a rethink, not a patch. NOT DECIDED.
- [ ] **DB session hygiene (minor).** Context-manage `_upsert_state` (`runner.py`) and the
      broker's long-lived session; add `pool_pre_ping`; lower `pool_timeout`.
- [ ] **Write `deploy.sh`** so the `--exclude .env --exclude '*.db*' --exclude
      access_token.json` + `--no-o --no-g` guards are mechanical instead of prose, and the
      post-deploy `curl /` + `curl /api/health` check is part of the script. Two outages so
      far have come from a human forgetting a flag.
- [ ] **VPS pending OS reboot** (5 ESM security updates) — owner action, market-closed window.
- [x] Removed the copy-pasteable rsync at `docs/superpowers/plans/2026-07-10-vps-deployment.md`
      that omitted `--exclude .env`; it now points at `scripts/deploy.sh` (2026-07-28).
- [ ] **Make `/api/health` a real readiness probe.** It is currently `{"ok": True}` plus the
      build stamp — a liveness stub that returned 200 throughout *both* 2026-07 outages, which
      is why the deploy script has to curl `GET /` separately to detect a broken deploy. It
      should report DB reachability, the heartbeat age of **both** engine loops, provider
      status, and armed state — and return **non-200 when the fast lane is stale**, since a
      stalled risk loop means stops are not firing on real money. The engine already collects
      all of this (`HealthTracker`, `engine/health.py`, the runner's loop timestamps); it just
      is not exposed. Raised during the 2026-07-28 deploy-hardening review.

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
4. Deploys to the VPS are whole-tree rsync + restart — full mechanics, flags, and
   post-deploy checks in `docs/operations.md`. Never deploy with an un-armed-safe book
   assumption. **There is no rsync filter and no deploy script** — excluding `.env`, the
   DBs, and `access_token.json` is a rule a human has to remember on every deploy, and
   forgetting it has taken the VPS down twice (corrected 2026-07-28; this line previously
   asserted the filter existed).
5. Model split (owner directive): Fable = advisor/architect/review, Sonnet = build,
   Opus = optimization judgment.
