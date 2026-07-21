# Development Roadmap & Progress Tracker

> **This file is the agenda.** Every working session starts here: pick the top unchecked
> item in the active workstream, do it, check it off, update "Last verified". CLAUDE.md
> links here as the canonical "what's next". Keep this file honest — a checked box means
> *verified done* (tests green + the stated acceptance evidence), not "code written".

**Last verified: 2026-07-20** · Branch: `feat/exits-journal` (deployed whole-tree to VPS
2026-07-18 04:45 IST) · Suite: 800+ backend tests green · VPS: healthy, 0 engine errors
since restart, `PT_API_TOKEN` set, `PT_RESEARCH_ENABLED=0` (research dormant in prod).

---

## Where the project stands (one paragraph)

The **execution plane works and is live**: 24/7 VPS engine, real-money path armed daily by
the owner, journal v2, shadcn UI, safety fixes from three audit rounds deployed. The
**research plane is the point of the software and is the underdeveloped half**: the
laboratory (isolation, sandbox, experiment ledger, walk-forward gates, human-gated
promotion) is production-grade, but the scientist inside it was never switched on — the
nightly plan is empty, the idea space is a fixed 18-combo grid over 13 close-price blocks,
knowledge is write-only (nothing reads Findings/retest_priority), and the anti-overfitting
statistics never actually engage. Closing that gap is the primary mission of every session
until further notice.

---

## Workstream A — Research plane: switch on the scientist  ← **PRIMARY FOCUS**

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
- [ ] P5 MTF (Margin Trading Facility) engine — spec gate first, built last. **Parked.**

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
