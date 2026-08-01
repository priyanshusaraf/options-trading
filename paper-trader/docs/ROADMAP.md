# Development Roadmap & Progress Tracker

> **This file is the agenda.** Every working session starts here: pick the top unchecked
> item in the active workstream, do it, check it off, update "Last verified". CLAUDE.md
> links here as the canonical "what's next". Keep this file honest — a checked box means
> *verified done* (tests green + the stated acceptance evidence), not "code written".

**Last verified: 2026-08-01** · Branch: `feat/exec-completeness` (VPS running **`eb88d4e`**,
deployed 2026-08-01 07:35 UTC via `scripts/deploy.sh`, exit 0, 1,307 tests passed in-deploy — confirmed by
`curl /api/health` on the box, which now also reports readiness) · Suites: `tests` +
`research_tests` exit 0, 116 frontend tests · `PT_RESEARCH_ENABLED=0` (research dormant).

Live probe at deploy time (Saturday, markets shut) — worth keeping, because it is the
scenario that would have broken a naive readiness probe:
```
health_code=200  {"status":"ok","markets_open":false,
 "loops":{"risk":{"age_seconds":0.41,"state":"ok","fatal":true},
          "signal":{"age_seconds":null,"state":"idle","fatal":false}},
 "failed_checks":[],"engine":{"armed":false,"provider":"kite"}}
```
The risk lane beats every tick with the market closed; the signal lane is silent and
correctly reads `idle`, not `stale`. A fatal signal lane would have 503'd this deploy.

> **2026-08-01 — a week of trust work landed** ahead of the E2/E3 queue, on the owner's
> instruction. What shipped, all TDD, all verified:
>
> 1. **Ledger honesty** — the cockpit reported ₹49,833 against a far smaller real account
>    for three weeks; E0.2's auto-reanchor was unreachable on a traded ledger. Now a daily,
>    flat-book, pre-first-trade re-anchor plus a visible drift badge. (`4c91e05`)
> 2. **Event-risk blackouts** — the owner's rules (EIA gas Thu / crude Wed with US DST,
>    NIFTY Tue options, SENSEX Thu, BANKNIFTY Wed, bullion options into expiry, stock
>    earnings days), one table shared by engine + backtester + UI. (`d1011c1`, `c1dd9f1`)
> 3. **C-P2 exit sweep** — replays real trades against candidate exit parameters. Found
>    the target is unreachable by construction and retuned the give-back lock.
>    (`eafd7bc`, `docs/2026-08-01-exit-sweep.md`)
> 4. **Reconciliation noise** — eleven false alarms per restart were the bot's own SL-M
>    orders and the owner's own positions; a real orphan would have been invisible in the
>    noise. (`ea500f0`)
> 5. **DB retention + `/api/storage`** — 108 MB and +5 MB/day on a 1 GB box with no resize
>    coming. Money record never pruned. (`1e8b64f`)
> 6. **Settings** — all 87 knobs documented with consequences, usable at 390px, and an
>    override that shadows a *changed* default is now flagged. (`a5239a1`)
> 7. **Journal** — a real walkthrough and three default sections instead of fourteen,
>    after a month at one row of production data. (`0d643cd`)
> 8. **Feature review** — `docs/2026-08-01-feature-review.md`.

> **The two things that gate everything else** (from the feature review):
> **(a)** deploy the above and CLEAR the `runtime_config` overrides
> `intraday_profit_lock_threshold=450` / `intraday_profit_lock_frac=0.3`, or the retuned
> exits are inert; **(b)** run the five-session no-touch trial. `TARGET` has fired zero
> times in 72 real trades and 45 of those exits were the owner closing by hand — until the
> bot's own exits are allowed to run and measured, "autonomous" is not a claim this
> project can make.

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
- [x] **Deploy these fixes — DONE 2026-08-01 06:59:50 UTC** (owner instruction, Saturday,
      markets shut). `scripts/deploy.sh` exit 0: guards 0-2 passed (42 exclude tokens/8
      required present; IST 1222 day 6 outside session; clean tree), both suites + dryrun
      green, SPA built on the Mac and shipped separately, `.env` verified present
      post-transfer, `GET /` 200, and `/api/health` reports the shipped SHA `4e9f125`.
      **This was the item gating the whole B workstream.** Everything committed on this
      branch since 2026-07-25 — the ten Workstream-B safety fixes, E0/E1, the week of trust
      work, and the two reliability fixes above — is now live. The engine is DISARMED, as it
      is on every start.

## Workstream C — Exit tuning (winners being cut; roadmap approved 2026-07-15)

- [x] P1 exit autopsy on real VPS trades (2026-07-15).
- [x] Bake the interim exit params in as code DEFAULTS (2026-07-21, PAYTM early-exit
      complaint): sl 0.008, target 0.03, lockstep_trigger 0.03, lock_threshold 600,
      lock_frac 0.3 (config.py). Purple bands widened to stay strictly wider than the
      new normal band: purple sl 0.015 / target 0.045. **NOTE:** any existing VPS
      `runtime_config` overrides for these keys still SHADOW the new defaults — clear
      them in Settings (or they must be re-set) after the next deploy+restart.
- [x] **P2 offline exit-param sweep — DONE 2026-08-01** (`eafd7bc`,
      `docs/2026-08-01-exit-sweep.md`). `scripts/exit_sweep.py` replays real trades against
      candidate parameters off the MFE/MAE telemetry. Answer: the target was UNREACHABLE
      (max favourable excursion ever = 1.216% of notional vs a 1.5% target), so zero TARGET
      exits was structural, not tuning. The give-back lock is the only lever that works —
      shipped 600→150 / 0.3→0.7, which turns those 22 replayable trades from −₹913 to +₹268.
      Ambiguous stop-vs-target orderings are reported as a band, never guessed. Sample is 22
      trades: a direction to test, NOT a proven setting.
- [ ] ~~P2 offline exit-param sweep on replayed VPS trades~~, walk-forward; add a
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
- [x] **DB-bloat — DECIDED AND BUILT 2026-08-01** (`1e8b64f`). It had reached **108 MB**
      (option_data 319k, signal_events 169k, equity_snapshots 133k) and the 2 GB resize is
      off the table (no budget), which settled the decision: retention, not migration.
      `engine/retention.py` ages telemetry out (90d) and DOWNSAMPLES the equity curve
      (7d full, then 1 row/15 min) rather than truncating history; the money record —
      trades, positions, order_journal, capital_state — is never pruned, with a test that
      says so. Runs daily from the signal lane with a flat book; `scripts/prune_db.py`
      does the one-off catch-up and the VACUUM. `/api/storage` makes the growth visible
      in-app, which is what was actually missing.
- [x] **DB session hygiene — DONE + DEPLOYED 2026-08-01 (`4e9f125`), TDD.** It was not "minor":
      `_upsert_state` handed an OPEN session back to four callers that each ended with
      `s.commit(); s.close()`, so any raise in between skipped the close and **leaked the
      pooled connection**. Reproduced before fixing — a failed watchlist write left
      `engine.pool.checkedout()` at 1 instead of 0. It is now a `@contextmanager` that
      commits inside the block and closes structurally, so the four call sites cannot forget;
      committing inside also means a caller's in-memory bookkeeping only runs if the write
      landed. Added `pool_pre_ping=True` (a pooled handle can outlive its file — predeploy
      restore, `prune_db.py` VACUUM) and `pool_timeout=10` (from 30: a request that cannot get
      a connection in 10s just holds a worker thread while the pool is already exhausted).
      Tests: `tests/test_db_session_hygiene.py` (9, incl. leak accounting, rollback, and
      "in-memory state must not advance past a failed write").
- [x] **Market-data validation at the Data seam — DONE + DEPLOYED 2026-08-01 (`eb88d4e`).**
      Candles reached `strat.signals` completely unchecked, through **two byte-identical
      converters** (`runner._to_df`, `backtest.engine._candles_to_df`) — nothing sorted them,
      de-duplicated them, or rejected a NaN close or an inverted high/low. Both are now thin
      aliases over `app/market_data/candles.py`, so a data fix cannot land in one plane and
      miss the other. **No-op on clean data, pinned by a test** asserting the frame is
      byte-identical to the old converter's — anything else would be a silent re-tuning of a
      live strategy. Repairs limited to the unambiguous: sort, de-dupe (last copy wins, since
      Kite revises the newest bar), and widen high/low to contain the bar's own open/close.
      Only missing/NaN/infinite or non-positive prices are dropped. The envelope repair was
      argued into existence by this repo's OWN fixtures —
      `test_backtest_ratchet_overlay.py` builds `(o=100.0, h=100.5, lo=98.5, c=97.9)`, a close
      below its own low; dropping it deleted the bar the test exists to exercise, and those
      two tests now pass **unchanged** under the repair. 31 tests.
      **Not yet done in this area:** no evidence has been gathered on whether REAL Kite
      history actually contains duplicates/gaps/inverted bars — the validator reports
      anomalies but nothing yet surfaces the report, so today it is a silent safety net.
      Wiring the report to the log/`/api/health` and measuring a week of live data is the
      obvious follow-up, and is what would turn "we are protected" into "here is how dirty
      the feed actually is". Replay mode and timezone auditing also remain untouched.
- [ ] **DB session hygiene — the broker's long-lived session (DELIBERATELY DEFERRED).**
      The other half of the item above, split out rather than silently dropped.
      `broker.s` is long-lived **by design** and it is load-bearing: E0.2's auto-reanchor had
      exactly one correct implementation because the write must go through the broker's own
      session (an Opus review caught a first cut that used a separate session —
      `expire_on_commit=False` left `broker.capital()` stale at ₹50k, so the next
      `snapshot()` clobbered the re-anchor back to the synthetic base). Context-managing it
      is a real refactor of the ledger's identity map, not a hygiene tweak, and it should be
      done deliberately with the reanchor/snapshot regression tests in front of it — not
      bundled into a session about connection counts.
- [x] **`deploy.sh` makes the rsync guards mechanical — DONE (`c3e1ac0`), verified
      2026-08-01 by reading the script, not by trusting this line.** Every guard this item
      asked for is in it: `--exclude '.env'` (:42), `access_token.json` (:44), BOTH DB globs
      `*.db` / `*.db-*` / `*.db.*` (:45-47), `--no-owner --no-group` in `RSYNC_FLAGS` (:317),
      and the post-deploy `curl /api/health` + a SEPARATE `curl /` (:578-586) that catches the
      broken-SPA signature health alone cannot see. Two outages came from a human forgetting a
      flag; none of these are prose any more. This box was left unchecked long after the work
      landed — the same drift CLAUDE.md warns about, in the file that is supposed to be the
      cure.
- [ ] **VPS pending OS reboot** (5 ESM security updates) — owner action, market-closed window.
- [x] Removed the copy-pasteable rsync at `docs/superpowers/plans/2026-07-10-vps-deployment.md`
      that omitted `--exclude .env`; it now points at `scripts/deploy.sh` (2026-07-28).
- [x] **`/api/health` is a real readiness probe — DONE + DEPLOYED 2026-08-01, TDD.**
      It reports DB reachability, the heartbeat age of **both** engine loops, provider auth
      status and armed state, and returns **503** when the DB is unreachable, the engine
      loops are stopped, or the fast risk lane is stale. Verdict logic is pure
      (`app/engine/readiness.py`, 22 unit tests); wiring is `tests/test_health_endpoint.py`
      (10 tests). Two findings from the build, both load-bearing:
      **(a)** the signal lane is reported but is deliberately **never fatal** — it
      legitimately stops beating overnight (`run_signal_loop` takes the `any_open`-false
      branch and never reaches `_beat_now`), and `deploy.sh` refuses to run *during* market
      hours, so a fatal signal lane would have 503'd on every legitimate deploy.
      **(b)** `_beat_now` stamps `provider.now()`, which under the mock is *simulated* time
      jumping a candle per tick; a budget measured against it reports a healthy dev engine as
      stale. The runner now keeps a parallel monotonic beat (`_beat_wall`) that readiness
      reads, so lane ages mean the same thing in every provider mode.
      Budgets are static `Settings` (`health_risk_stale_seconds` 90 /
      `health_signal_stale_seconds` 600 / `health_startup_grace_seconds` 45), deliberately
      **not** `runtime_config`-overridable so no DB row can silence a safety probe.
      `deploy.sh` now waits out a `starting` verdict instead of exiting on the first 200 —
      previously a process whose risk loop died at startup passed the deploy check.
      **`GET /` stays a separate check**: a broken SPA mount is invisible from this probe.
      **Acceptance, measured 2026-08-01 on the live VPS:** the healthy path is confirmed in
      production (200 / `status:"ok"`, both lanes correctly classified with the market shut —
      payload quoted at the top of this file), and `deploy.sh` consumed the verdict for the
      first time on that same deploy. **Still unexercised live: the 503 path.** It is proven
      in-process only; confirming it in production means deliberately stalling the risk lane
      on a real-money box, which is not worth doing on purpose. Treat the next genuine
      incident as the test and check the probe went red.

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
