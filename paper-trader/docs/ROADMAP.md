# Development Roadmap & Progress Tracker

> **This file is the agenda.** Every working session starts here: pick the top unchecked
> item in the active workstream, do it, check it off, update "Last verified". CLAUDE.md
> links here as the canonical "what's next". Keep this file honest — a checked box means
> *verified done* (tests green + the stated acceptance evidence), not "code written".

**Last verified: 2026-08-01** · Branch: `feat/exec-completeness` (VPS running **`d4dfd86`+**,
deployed 2026-08-01 via `scripts/deploy.sh`, exit 0, 1,3xx tests passed in-deploy — confirmed by
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

> **Gate (a) is CLOSED as of 2026-08-01** (owner: "go for all of it"). Deployed, and both
> `runtime_config` overrides cleared via `POST /api/settings/reset` — which also calls
> `refresh_params()`, so the running engine took them without a restart. Verified on the box
> via `/api/settings`: `intraday_profit_lock_threshold value=150.0 overridden=false`,
> `intraday_profit_lock_frac value=0.7 overridden=false`. **The retuned give-back lock is now
> live and will act on Monday's session** — this is the first change to how the bot takes
> profit since the sweep, and it is running on a 22-trade sample, so watch it.
>
> **(b) STILL OPEN — the five-session no-touch trial.** `TARGET` has fired zero times in 72
> real trades and 45 of those exits were the owner closing by hand; until the bot's own exits
> are allowed to run and be measured, "autonomous" is not a claim this project can make. No
> amount of engineering substitutes for this, and it is owner-only: it costs five sessions of
> not intervening. `TARGET` has fired zero
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

**Active order REVISED by the owner 2026-08-01** ("research plan is the biggest feature that
we havent done anything for, work towards it please"; "exit tuning is fine we can get back to
it"; "ui is still left to be done"):

**A (research plane — now a PRIORITY, no longer last) → D (UI) → E (futures/MTF) → C (exit
tuning, parked by the owner).**

The previous order (B → E → C → D → A) came from the owner's 2026-07-24 directive and is
superseded. B is closed apart from the OS reboot. Workstream A's Phase 0 is the correct entry
point and is not optional: `var_sr` defaults to 0.0, so `expected_max_sharpe()` returns 0 and
**deflation never engages anywhere** — the lab currently overstates every finding it makes.
Switching the scientist on before fixing that would generate confident nonsense at scale.

---

## Workstream A — Research plane: switch on the scientist  ← **PRIORITY (owner, 2026-08-01)**

> **Re-prioritised 2026-08-01**, superseding the 2026-07-24 "do last" directive. The owner:
> "research plan is the biggest feature that we havent done anything for, work towards it
> please." Phase 0 (honest statistics) first — everything downstream inherits its trust, and
> today deflation never engages, so the lab overstates its own findings. `PT_RESEARCH_ENABLED`
> stays 0 until Phase 1 shadow mode is deliberately switched on.

**Vision (owner, 2026-07-20):** a reiterative, reinforcing research loop — generate its own
strategy ideas (including *formula-level* indicator variants, not just parameter tweaks),
test which idea works where, learn from past failures, shadow-paper-validate survivors
against expectations, then seek owner approval with a plain-language explanation.

**Deprioritized within this vision:** the UI→deployed-Python auto-bridge. Approved
strategies get handcoded into `app/strategy/registry/` (drop a module with `STRATEGY`,
auto-discovered). Composition *generation* stays core — only the auto-deploy leg is parked.

### Phase 0 — Honest statistics *(do first; everything downstream inherits its trust)*
- [x] **Thread real trial counts — DONE 2026-08-01.** `run_generated` enumerates N
      compositions and keeps the best, but each is scored by its own `run_experiment`, which
      can only see its own parameter grid — so every composition was priced as though it were
      the only thing ever tried, understating the selection bias by exactly N. New
      `sibling_trials` parameter (default 1, so single-strategy runs are untouched) multiplies
      the deflation count; `run_generated` passes `len(compositions)`. `n_trials` is now
      compositions × candidates × folds.
- [x] **Compute `var_sr` and pass it through — DONE 2026-08-01.** This was the item that
      made the whole lab dishonest: `expected_max_sharpe()` returns exactly 0 whenever
      `var_sr` is 0, so the DSR degraded to a PSR against zero on **every candidate ever
      scored**, and widening the search moved the bar not at all. The DSR *math* was correct
      all along (its unit tests passed untouched) — only the wiring was missing, which is
      why it survived so long. `OptimizationResult.var_sr` now computes the population
      variance of the trial Sharpes (recorded on each `Trial` as `is_sharpe`, not
      back-derived from the objective, which is `-inf` for sub-floor trials and would poison
      the variance), and `orchestrator/run.py` passes it. The `search.py` docstring that
      claimed "a wider search *raises* the significance bar" is corrected in place, with the
      note that it was false for as long as it was written.
- [x] **PBO via CSCV — DONE 2026-08-01.** `research/stats/pbo.py`, pure and deterministic.
      PBO answers what the DSR cannot: not "is this Sharpe big enough given N tries" but
      "does the IN-SAMPLE ranking carry any out-of-sample information at all, or does picking
      the winner just pick noise?" A search can clear every other gate and still be pure
      overfit if the ranking scrambles.
      Computed over CONTIGUOUS equal blocks of the series (default 8) rather than the
      walk-forward folds, deliberately: CSCV needs 8-16 sub-periods for the combination count
      to mean anything, while `n_folds` is 3-4. `optimize()` now retains the
      (sub-period × candidate) `perf_matrix`; the orchestrator gates on `pbo ≤ 0.30` and
      **fails CLOSED** — a matrix that cannot be evaluated (single candidate, too little
      data) does not pass, same discipline as `research/guards.py`.
      **Two properties pinned by test, both measured rather than assumed:** pure noise
      averages **PBO 0.453 over 40 draws** (a statistic that reported "clean" on randomness
      would launder noise into confidence), and a selection driven purely by local noise —
      each strategy spiking in one distinct block — scores **1.000**. Note the per-draw
      spread on noise is 0.09-0.89, so the null is asserted on the MEAN across draws; a
      per-seed assertion would be asserting something false. 16 tests.
- [x] **Wire `stats/neff.py` — DONE 2026-08-01.** It had existed since M0 with NO consumer.
      The place it belongs turned out to be the promotion step: `run_experiment` validates
      per instrument and then does `max(validated, key=dsr)` — picking the best of N, which
      is a selection exactly like picking the best of N parameter draws, and it was entirely
      unaccounted. Deflating by raw N would overstate the fix because these names move
      together, so N_eff is the honest count (rho ~ 0.4 turns 200 large-caps into ~2.5
      independent bets). New `mean_pairwise_correlation` (aligns series on their common
      RECENT tail — different history depths would otherwise compare different calendar
      periods) feeds `effective_sample_size`; the promotion record now carries
      `breadth: {n_validated, mean_correlation, n_effective}` so a reviewer can see that
      "validated on 12 instruments" was really ~N_eff independent bets. 9 tests.
      **A bug caught in review of this change:** the first cut reused the loop variable
      `var_sr` for the cross-instrument deflation, which would have applied whichever
      instrument was iterated LAST — its parameter-search dispersion — to a decision about
      instruments. The pool the winner came from is the instruments, so the dispersion is now
      measured across them (`breadth_var_sr`), pinned by test.
- [x] **Optimizer objective — ALREADY DONE (`1ec5188`), verified by reading the code
      2026-08-01, not by trusting this file.** `_objective` is `metrics.consistency ×
      √n` — a trade-count-aware t-statistic, not raw expectancy. This box sat unchecked long
      after the work landed. (The `Trial.is_objective` comment still said "expectancy"; also
      corrected.)
- **Acceptance:** a synthetic no-edge universe swept with a wide search produces **zero**
  promotion candidates; the same sweep with deflation stubbed off produces several.
  TDD in `research_tests/`.

### Phase 1 — Turn the nightly loop on (shadow mode)
- [x] **`nightly._load_plan()` — DONE 2026-08-01.** It returned `[]` from M0 until today, so
      every guardrail, gate and statistic in this package sat behind a scheduler that
      scheduled nothing: the cron one-shot was a well-tested no-op. New `research/plan.py`
      orders OPEN hypotheses by `retest_priority` — **which finally gives that field its
      first consumer** (written on every run since M0, read by nothing, which is why a killed
      idea was never actually revisited). Eligibility is a HARD filter with deliberately no
      fallback to "everything": an empty eligible universe yields an empty plan, because a
      fallback there would point research at live positions. Cold start seeds one hypothesis
      on the sandbox so the loop can start itself. Bounded per night (3 experiments × 6
      instruments) and deterministic (sorted, sandbox-first) so a result is reproducible from
      the plan that produced it. 14 tests.
      **Sector seeding deliberately NOT implemented:** the roadmap asks to seed from the
      sector edge map, but no sector metadata exists on `Instrument` and no map exists as
      data — it lives only as prose in this file. Inventing classifications would fabricate
      the very input the ordering claims to use. The cold-start seed prefers the commodity
      sandbox (which IS the bullion set); the rest waits for real sector data.
- [x] **The nightly loop RUNS end to end — first time, 2026-08-01.** Verified by execution,
      not by test: a real invocation produced `research.db` with 1 program, 1 hypothesis and
      **6 Findings**, plus `report_run_1.md`. `_make_source()` builds a `KiteDataSource` over
      the same provider seam the engine uses, so `PT_PROVIDER=mock` is a fully offline,
      deterministic run. Promotion was correctly **none** — the synthetic market has no
      exploitable edge for this strategy, which is the right answer and a useful sanity
      signal (no false promotion on noise).
      Note the mock returns a fixed 966-bar series regardless of interval, so every
      instrument was rejected for insufficient trades (1-5 vs a 20 floor). That is a property
      of the synthetic data, not of the strategy — a real signal needs Kite candles.
- [ ] Nightly invokes `run_generated` (composition search) on that plan, not just the
      handwritten strategy. `build_plan` currently schedules one registered `strategy_key`;
      wiring the generator in is what makes the loop actually *explore*.
- [x] **Where the cron runs — DECIDED 2026-08-01: NOT the production VPS.** Full reasoning in
      `docs/operations.md`. The droplet is 1 GB and has OOM'd twice; the resize is off the
      table; a Vite build there can already take live positions down, and a research sweep is
      far heavier (`n_folds × n_candidates` backtests, plus `n_blocks × n_candidates` more
      for the PBO matrix since today). The live risk lane must beat every second and research
      has no deadline that justifies risking it. Runs on the Mac; `PT_RESEARCH_ENABLED` stays
      `0` on the VPS. Shadow mode confirmed: writes `research.db` + a report per run, queues
      `PromotionCandidate` as `pending`, deploys nothing.
- **Acceptance:** after one week, research.db holds a real Findings corpus from unattended
  runs; reports land in `PT_RESEARCH_REPORT_DIR`.

### Phase 2 — Widen the idea space (incl. formula-level variation)
- [x] **New blocks — MOSTLY DONE 2026-08-01.** Added RSI (as a whole family, see below),
      `volume_surge`, `gap_up_pct`/`gap_down_pct`, `body_frac_gt`. The library went 13 → 19
      blocks. All pure, warmup-safe (a comparison against NaN yields False, never a phantom
      True), and registered with sample args that are themselves tested.
      Two subtleties worth keeping: `volume_surge` reads FALSE when the feed carries no
      volume column — absent data must never manufacture an entry — and the RSI threshold is
      declared `pct`, not `thr`, because `thr` is bounded to |x|≤10 for z-scores while RSI
      reads 0-100 (a 70 threshold would have been rejected by the wrong bound).
      **Still missing: opening-range breakout and time-of-day window.** Both need session
      awareness (IST open, per-segment hours) rather than pure bar math, so they are a
      different shape of change and are deliberately left.
- [ ] Opening-range breakout + time-of-day window blocks (need session/timezone awareness,
      not just bar math — see above).
- [x] **Price-source + smoothing-kind as parameters — DONE 2026-08-01.** The owner's
      "modified-RSI" ask generalised: `close|hl2|hlc3|ohlc4` × `sma|ema|wilder|hull` = 16
      lawful variants of a single block, still whitelisted, still auditable in `blocks.py`.
      **Encoded as bounded INTEGER codes, not strings, and that is load-bearing:** the
      emitted `compute` is AST-validated against numeric literals only
      (`validate.py:53-54`), so a string parameter would have meant opening that perimeter.
      Codes clamp rather than raise — a generated composition must never crash the nightly on
      an arithmetic accident — and code 0 is the conventional reading in both families, so
      adding the parameter never silently re-tunes an existing composition.
      **A real bug this surfaced:** Hull smoothing (`2·MA(n/2) − MA(n)`) can overshoot below
      zero, which drove RSI to **−22** in testing. Gains and losses are non-negative by
      definition, so the averages are now floored at zero — the overshoot is an artifact of
      the smoother, and an RSI outside [0,100] would have silently corrupted every threshold
      built on it.
- [x] **Seeded random sampling — DONE 2026-08-01.** `sample_compositions(limit, seed)` draws
      from the BLOCK REGISTRY rather than a fixed list of hand-written strings. This was not
      optional: the old 3×3×2 grid names its blocks as literal strings, so adding the Phase-2
      vocabulary widened the whitelist and **changed the search not at all** — the RSI family
      was registered and never sampled. Same shape as the `var_sr` bug: present, correct,
      unreachable.
      Deterministic per seed (a composition that cannot be regenerated from its seed cannot be
      reproduced, which is the premise the whole plane rests on), duplicate keys skipped (they
      would collide in `research_generated_strategy` and silently overwrite each other), and
      bounded attempts so an unlucky seed cannot spin. `PT_RESEARCH_SEARCH_SEED` unset keeps
      the deterministic grid as a stable control.
      Verified end-to-end: seed 11 produced 6 distinct compositions spanning RSI variants
      across three price sources and four smoothings, plus volume and body filters — all
      emitted → AST-validated → sandboxed → evaluated.
- **Acceptance:** nightly explores new compositions each night; DSR bar visibly rises
  with search breadth (log the deflation benchmark per session).

### Phase 3 — Close the reinforcement loop (make it *learn*)
- [x] **Generation READS knowledge — DONE 2026-08-01.** `research/knowledge.py` +
      `research_block_edge`. Counts BLOCK FAMILIES rather than compositions (a composition is
      a one-off; a family is the level at which a lesson generalises), suppresses families
      with a well-powered negative record on an instrument, and mutates survivors with small
      nudges (a mutation that rewrites everything is just a fresh random draw). Qualification
      failures are recorded too, not only validation failures — otherwise the map is blind to
      every idea that never produced enough trades to be judged, which on real data is most
      of them.
      **THE BUG THIS SHIPPED WITH, CAUGHT BY RUNNING IT:** the obvious implementation
      destroys the search. On a universe where nothing works yet, every family accumulates a
      losing record — suppression took **all four trend families at once**, and since every
      composition structurally requires a trend block, the sampler could draw NOTHING. Night
      4 ran 1 experiment instead of 6 while reporting success. Two guards now: a
      `MAX_SUPPRESSED_FRACTION` exploration floor (worst-ranked first, so the cap keeps the
      strongest negative records), and a last-resort fallback where the sampler explores
      anyway if suppression has blocked every lawful draw — logged loudly, because a silent
      override makes the next person unable to explain why a suppressed family reappeared.
      Suppression is a preference, never a cage.
- [x] **`retest_priority` has its consumer** — landed in Phase 1's `build_plan`, which orders
      open hypotheses by it. Written on every run since M0 and read by nothing until then.
- [x] **`block-family × instrument` edge map — DONE 2026-08-01.** `research_block_edge`,
      rendered into every generated run's report as "which idea works where", alongside the
      families suppressed for that run. A reinforcement loop nobody can read is one nobody can
      debug: this table is what explains why tonight's search avoided something last night
      tried. `edge_weights()` exposes Laplace-smoothed per-family weights bounded to
      [0.25, 2.0] — a deliberate exploration floor so knowledge tilts the search without
      collapsing it onto the first success.
      Verified across four consecutive nightly runs on the same DB: 90 edge rows accumulated,
      and night 4's behaviour provably differed from night 1's.
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

> **CONTRACT-NOTE GATE LIFTED 2026-08-01.** The owner pushed back — "why do you need the
> contract note from me anyways, i feel you should be able to get it from a couple of web
> queries" — and is right. Zerodha publishes its F&O rate card and margin figures, and NSE
> publishes SPAN+exposure; those are a legitimate basis for building and verifying the charge
> and margin model. What a personal contract note would add is confirmation against one real
> account's fills, which is a nice-to-have, not a prerequisite. Source the published rates,
> build the model, and state the source and date in the code.
>
> **SPEC WRITTEN + OPUS-REVIEWED (2026-07-24).**
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
- [x] **Feed quality is VISIBLE — DONE + DEPLOYED 2026-08-01 (`2a8fcc8`).** The validator
      above returned a report that nothing consumed, so a broken feed would have been
      corrected silently every 2.5s forever. The live scan now validates once, builds the
      frame from the result (`frame_from`, so the hot path does not validate twice per
      instrument per tick), and records per-instrument anomalies in `FeedQuality`. They
      surface as `provider_feed` in `/api/health` and mark the probe **degraded, never
      unready** — the bars were repaired before any strategy saw them, so it is a reason to
      look, not to 503 and fail a deploy. Logging is throttled by anomaly SIGNATURE: a
      repeating problem logs once, a changed one logs again, and a recovered feed drops out
      of the report (a stale alarm that never clears is how a warning light stops being
      believed). 13 tests.
      **Still open — the actual measurement.** As of deploy, `provider_feed` is `{}`, but
      markets were shut, so that is "the scan has not run", NOT "the feed is clean". The
      question this was built to answer — does real Kite history contain duplicates, gaps or
      inverted bars — needs a week of live sessions. Check `/api/health` `provider_feed` and
      grep the log for `FEED_QUALITY`.
      **Untouched in this area:** replay mode, and a deliberate timezone audit.
- [x] **Backtester audit — DONE + DEPLOYED 2026-08-01 (`c7e5217`).** All ten Phase-1
      dimensions, verdicts cited to file and line:
      `docs/2026-08-01-backtester-audit.md`. Came out well — **no look-ahead** (next-bar-open
      fills, exit decisions start the bar after the fill, every strategy shift backward, no
      `shift(-1)`/`center=True`/backfill anywhere), full direction-aware charge stack on both
      legs, and statistics that label their own limits (drawdown explicitly close-to-close
      with `worst_mae_pct` alongside; `consistency` explicitly not-a-Sharpe).
      **One real defect, fixed:** the SPOT backtester filled at the exact bar open with ZERO
      execution cost, while `premium.py` had modelled a spread since it was written — so every
      equity_intraday backtest was optimistic. Against a 0.8% stop / 1.5% target and a
      largest-ever favourable excursion of 1.216%, an unmodelled round trip is the same order
      as the edge. `Settings.backtest_slippage_pct` defaults to 5 bps; `0.0` reproduces all
      prior numbers exactly. 10 tests.
      **Documented, not fixed (divergences, not bugs):** backtest sizing has no relationship
      to live sizing (one unleveraged full-capital position vs up to four MIS-margin ones), so
      a backtest `return_pct` is NOT a live account-return prediction — the biggest
      interpretive trap in the system; no intrabar stop (live uses an exchange SL-M that fires
      mid-bar); no partial fills; no pyramiding; structural survivorship in the curated
      universe.
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
