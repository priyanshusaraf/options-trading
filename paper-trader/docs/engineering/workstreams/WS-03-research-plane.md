# WS-03 — Research Plane

**Status:** active
**Owner surface:** `backend/research/`, `backend/research_tests/`, `docs/research/ARCHITECTURE.md`, `backend/app/core/research_read.py` (read-only bridge), `backend/app/core/generated_strategies.py` (read-only bridge)
**Last verified:** 2026-08-03 · commit `cdbe686`

> This workstream is the **laboratory**: an autonomous quantitative-research process that
> runs after the market closes, invents and tests strategy ideas against historical bars,
> judges them with statistics that are honest about how many things were tried, remembers
> what failed, and queues survivors for a human to approve. It is a *separate process* with
> its *own database*. It cannot open a position, cannot import the broker, and cannot write
> execution state — not by convention but by a fail-closed guard that aborts the run. The
> only path from a research result to real money is a human reading a report, a human
> committing a strategy file, and a human re-arming the engine.

---

## 1. Vision

A reiterative, reinforcing research loop (owner, 2026-07-20): it generates its own strategy
ideas — including **formula-level** indicator variants and, in Generation 2, novel
*structures* — tests which idea works where, learns from its own failures, shadow-validates
survivors against their own backtested expectations on sessions they have never seen, and
then asks the owner for approval with a plain-language explanation.

"Done" is a loop that runs unattended every night and whose output a sceptic would trust:
every number deflated for the size of the search that produced it, every finding bound to
the exact graph and component versions that produced it (RFC 0001 F14), every promotion
carrying the evidence of the sessions it survived. The measure of success is not the number
of strategies produced but **reliable knowledge per unit of compute** — the corpus of
negative findings is as valuable as the positive ones, because it is what stops tomorrow's
search from re-walking today's dead ends.

Generation 1 searched *parameters* over a fixed grammar of hand-written string templates.
Generation 2 searches *structure* over Component IR graphs. The end state is a nightly that
proposes graph mutations, evaluates them under gates that already work, and cannot record a
finding that is not bound to what produced it.

## 2. Scope

### The isolation rule — read this before anything else

**Research is autonomous; capital allocation is NOT.** This is Hard Invariant 5 in
`CLAUDE.md` and it is structural, not procedural:

1. **`research/guards.py` is fail-closed and runs first.** `enforce()` is the first thing
   `nightly.main()` calls, before the freeze gate, before the DB is created. It asserts
   three things and raises `ResearchIsolationError` on the first violation:
   - `assert_distinct_databases` — `research.db` must not `realpath` to the execution DB.
   - `assert_no_execution_engine_imported` — none of `guards.FORBIDDEN_MODULES` may be in
     `sys.modules`: `app.engine.runner`, `app.engine.broker_factory`, `app.engine.broker`,
     `app.engine.live_broker`, `app.engine.order_executor`, `app.engine.kite_order_client`,
     `app.providers.live_kite`. Anything that can place, route, or manage an order.
   - `assert_capital_safe` — `PT_EXECUTION=live` in the research process aborts the run.
2. **`PT_RESEARCH_ENABLED=0`.** `Settings.research_enabled` defaults to `False`
   (`app/core/config.py:386`). With it off, the cron one-shot prints and returns 0 — no
   `research.db` is created or touched. It stays `0` on the production VPS permanently
   (see §5/§8: the cron runs on the Mac).
3. **Separate DBs, separate suites, separate config.** `research.db`
   (`PT_RESEARCH_DB_PATH`) vs `paper_trader.db`. `pytest research_tests` vs `pytest`
   (`testpaths = tests`, so bare `pytest` does **not** run this workstream's suite).
   `research/config.py` reads only `PT_RESEARCH_*` and deliberately does not import
   `app.core.config` for its own settings.
4. **Bridges are read-only and one-directional.** `app/` may reach `research/` only through
   `app/core/research_read.py` and `app/core/generated_strategies.py` (surfaced by
   `app/api/portfolio_routes.py`). `research/` may import from `app/` only pure/read-only
   seams — the complete list, verified 2026-08-03 by grepping every `from app.` in
   `backend/research/`: `app.core.config`, `app.core.instruments`, `app.core.market_hours`,
   `app.backtest.engine`, `app.backtest.metrics`, `app.strategy.registry`,
   `app.ir.authoring`, `app.ir.edit`. Never broker, runner, or `app.db.session` (which binds
   the execution engine at import time — that is *why* the ban is on the import, not on a
   call).
5. **`research/` imports `app.ir`, never the reverse.** The IR is a language, not an
   executor; consuming it does not cross the capital boundary. A dependency in the other
   direction would put the execution plane behind research code and is forbidden.
6. **Research work must produce an empty diff under `backend/app/`**, except the sanctioned
   bridge and kernel files named above.

### In scope

- **Generation**: the block library (`strategy/builder/blocks.py`, 23 blocks), the grammar,
  seeded composition sampling (`search.py`), emission + AST validation + sandboxed load
  (`emit.py`, `validate.py`, `load.py`), explanation (`describe.py`).
- **Generation 2 structure search**: blocks as IR components (`ir_components.py`) and the
  graph mutation proposer (`propose.py`).
- **Statistics**: DSR/PSR (`stats/dsr.py`), PBO via CSCV (`stats/pbo.py`), effective sample
  size (`stats/neff.py`), bootstrap evidence floors (`stats/evidence.py`), retest priority
  decay (`stats/retest.py`).
- **The pipeline**: qualify → optimize → validate (outer walk-forward) → score
  (`research/pipeline/`, `research/evaluation/`), orchestrated by
  `research/orchestrator/{run,generate,report}.py`.
- **The nightly loop**: `nightly.py` (cron one-shot + guards + freeze gate), `plan.py`
  (what to work on tonight), `universe.py` (what it may work on).
- **Shadow mode** (`shadow.py`), **regime conditioning** (`regime.py`), **knowledge
  feedback** (`knowledge.py`), and the research domain model (`research/domain/`).

### Out of scope

| You might expect it here | It lives in | Note |
|---|---|---|
| The Component IR **language** — schema, validate, resolve, edit, hashing, runtime, `experiment.py` | **WS-01 (Component IR)**, `backend/app/ir/`, RFC `docs/rfcs/0001-component-ir.md` | WS-03 *consumes* it. `ir_components.py` uses `app.ir.authoring`; `propose.py` routes every mutation through `app.ir.edit` and owns **no** opinion about the format (a second implementation of §3 is the defect C12 exists to prevent; a test greps for one). |
| Anything that **moves capital** — engine, broker, sizing, exits, orders, the live ledger | **WS-02 (Execution)** | Structural, fail-closed boundary. See the isolation rule above. Research proposes; a human commits a strategy file into `app/strategy/registry/` and re-arms. |
| The database — schema, migrations, retention, storage budget | **WS-07 (Infrastructure & Persistence)** | `research.db` has its own `Base` (`research/domain/base.py`) and is deliberately not the execution schema, but DB *policy* is WS-07's. |
| The approval **UI** / research cockpit screens | **WS-08 (Cockpit UI)** | The read-only bridge already exposes the promotion queue; no React route renders it. |
| Auto-deploying an approved strategy to production Python | **Parked by the owner.** | Composition *generation* stays core; the UI→deployed-Python auto-bridge is deprioritised. Approved strategies are hand-coded into `app/strategy/registry/`. |

## 3. Interfaces

**Exports**

| Export | Guarantee |
|---|---|
| `research.guards.enforce(...)` / `ResearchIsolationError` / `FORBIDDEN_MODULES` | Fail-closed. Raises on the first violation, never warns. `FORBIDDEN_MODULES` may grow; removing an entry requires an owner decision naming the invariant. |
| `research.db` schema (`research/domain/models.py`) | Read-only to the rest of the repo. Programs, Hypotheses, ExperimentSpec/Run, Trials, Scorecards, `PromotionCandidate`, `Finding`, `research_block_edge`, `research_shadow_session`. |
| `research.shadow.approval_queue(session)` | Returns **only** `pending` candidates. A `shadow` candidate is never in the queue; the only transition is `promote_if_ready`. |
| `research.strategy.builder.ir_components.derive_all()` / `derive()` / `groups()` | 23 block components, one per registered block, bar-for-bar equivalent to calling the block. `groups()` is metadata *about* components, never a field on them (C13). |
| `research.strategy.builder.propose.{propose, lineage, MUTATIONS, Vocabulary, Proposal}` | Every returned graph has passed `app.ir.edit`'s legality checks. Seeded and replay-exact. **Proposes only — never scores** (C14; a test greps for `sharpe`/`fitness`/`objective`/`rank`). |
| `research.stats.*` | Pure, deterministic, no I/O. `pbo_gate` fails **closed** on a matrix it cannot evaluate. |
| `research.regime.label_regimes` | Pure, no look-ahead (expanding volatility median, pinned by a truncation test). Warmup bars are `unknown`, never `chop`. |
| `python -m research.nightly` | The only sanctioned entry point. Guards first, freeze gate second. |

**Consumes**

| Consumed | From | Why |
|---|---|---|
| `app.ir.authoring` (`component`, `parameter`, `socket`, `wire`) | WS-01 | Derive the block library as typed, versioned components. |
| `app.ir.edit` (`add_node`, `remove_node`, `connect`, `disconnect`, `set_override`, `EditRejected`) | WS-01 | The proposer's only mutation primitives — legality is WS-01's to decide. |
| `app.ir.experiment` (F14 binding) | WS-01 | **Not yet consumed.** This is the topmost item in §5. |
| `app.backtest.engine`, `app.backtest.metrics` | WS-02 (pure kernels) | Simulation math is reused, never duplicated, via `research/evaluation/kernels.py`. |
| `app.strategy.registry` | WS-02 | The handwritten baseline strategy and the canonical column contract. |
| `app.core.config` / `app.core.instruments` / `app.core.market_hours` | WS-02 | Read-only. `app.core.config` binds no DB engine — that is the reason it is allowed and `app.db.session` is not. |
| `app.providers.factory.get_provider()` | WS-02 | Candle source for the collection phase only (`KiteDataSource`). `PT_PROVIDER=mock` makes a nightly run fully offline and deterministic. |
| Watchlist snapshot JSON (`PT_RESEARCH_WATCHLIST_SNAPSHOT`) | WS-02 exports it | Research must never open the execution ledger to learn what is committed live. |

**Depends on:** WS-01 (Component IR), WS-02 (pure kernels + the exported snapshot), WS-07 (DB policy)
**Blocked by:** nothing in code. Two owner decisions are outstanding — see §8.
**Currently blocking:** nothing. No other workstream waits on this one; the plane changes no running behaviour.

## 4. Completed

Newest first. Dates are the dates the work landed.

### Generation 2 — structure search over Component IR graphs

- **F8's converse is enforced — 2026-08-03, `15125b6`.** An input that is neither wired nor
  given a default source is a socket nothing feeds: such a graph validates, **resolves
  cleanly**, and raises the moment a kernel reaches for it. The proposer produced one within
  its first hundred mutations. F8 now joins F7 as library-dependent (which sockets a node has
  lives in the component) and is reported *unchecked* without a library rather than passing
  silently. The RFC's Appendix A.4/A.5 fixtures were abbreviations that omitted their bar
  wiring; they are now complete artefacts. *This defect was found by building the proposer,
  not by reading the spec.*
- **The structure proposer — 2026-08-03, `15125b6`.**
  `research/strategy/builder/propose.py` + `research_tests/test_ir_propose.py`, **16 tests
  (verified: `pytest research_tests/test_ir_propose.py --collect-only` → 16)**. Five
  mutations — `add_predicate`, `drop_predicate`, `swap_predicate`, `rewire`, `retune` —
  every one going through `app/ir/edit.py`.
  - **1,000 random mutations, every one asserted through `validate → resolve → evaluate`.**
    All three, deliberately: a graph can pass the format and be unresolvable, or resolve and
    have a socket nothing feeds. Plus a guard that all five mutations fire across those
    seeds, and a 40-step lineage, since mutations compound.
  - *Legality before objective.* A proposer that emits illegal graphs makes every downstream
    statistic meaningless, and confidence in recorded numbers cannot be retrofitted — this
    platform has already paid that price once (see §7).
  - *Deterministic.* Seeded throughout, replay-exact, with a test grepping for unseeded
    `Random`, clocks and uuids. F14 binds findings to what produced them; a clock-seeded
    proposer makes that binding a fiction.
  - *`rewire` is the mutation Generation 1 could not express at all* — there was no
    representation in which "move this predicate elsewhere in the structure" is sayable.
  - Every mutation preserves the invariant that each node input is fed — **stricter** than
    RFC §3, which admits dangling inputs that cannot be evaluated.
- **The block library as IR components — 2026-08-03, `0dd7a4d`.**
  `research/strategy/builder/ir_components.py` + `research_tests/test_ir_block_components.py`,
  **36 tests (verified by `--collect-only`)**. All **23 blocks** derive into versioned,
  typed, composable components (verified: `len(BLOCKS) == len(derive_all()) == 23`). This is
  step one of Generation 2 for the reason C14 gives: Generation 1 searches *parameters* over
  a fixed grammar, and structure search is not reachable from a design where components
  sweep themselves.
  - *The derivation is mechanical.* Identifier from the block name, parameters and kinds
    from `BlockSpec.params`, defaults from `sample_args`, warmup from `BlockSpec.warmup`.
    Nothing is invented; the tests read expectations off `BlockSpec` rather than restating
    them, so a block that gains a parameter fails until it is carried across.
  - **Equivalence, not resemblance:** each of the 23 components is asserted to compute
    *exactly* what calling the block computes, **bar for bar, on 320 real bars** — plus a
    guard that the fixture makes ≥60% of them fire, so it is not 23 comparisons of all-False
    columns. The adapter calls `BlockSpec.fn`; a second implementation would show up here.
  - **A live defect found and fixed: all 23 components initially shared one body address.**
    They are built by one shared adapter, so their *source* is identical, and F2 addresses
    the body by its content — a registry keyed by that address silently kept the last one,
    discarding 22 kernels and 22 warmups. `component(closes_over=...)` now makes what a
    factory-built kernel closes over part of its address (`closes_over={"block": name, "fn":
    _block_source(spec)}`), and `library()` refuses two components claiming one address with
    *different* kernel declarations. Sharing an address stays legal where it is correct — an
    alias — and there is a test for that.
  - *An honesty guard rather than a weakened one:* one adapter serves all 23 blocks, so it
    reaches `inputs`/`params` dynamically and the F4 interface check cannot conclude
    anything. It reports `unchecked` rather than passing silently, and a control test asserts
    hand-authored components are still fully checked.

### Workstream A — Phases 0–5, "switch on the scientist"

Re-prioritised 2026-08-01 by the owner ("research plan is the biggest feature that we
havent done anything for"), superseding the 2026-07-24 "do research last" directive.

**Phase 0 — honest statistics (2026-08-01).** Everything downstream inherits its trust.
- **`var_sr` computed and passed through.** *The item that made the whole lab dishonest*:
  `expected_max_sharpe()` returns exactly 0 whenever `var_sr` is 0, so the DSR degraded to a
  PSR against zero on **every candidate ever scored**, and widening the search moved the bar
  not at all. The DSR *math* was correct all along (its unit tests passed untouched) — only
  the wiring was missing, which is why it survived so long. `OptimizationResult.var_sr` now
  computes the population variance of the trial Sharpes (recorded on each `Trial` as
  `is_sharpe`, **not** back-derived from the objective, which is `-inf` for sub-floor trials
  and would poison the variance); `orchestrator/run.py` passes it. The `search.py` docstring
  that claimed "a wider search raises the significance bar" was corrected in place, noting it
  had been false for as long as it was written.
- **Real trial counts threaded.** `run_generated` enumerates N compositions and keeps the
  best, but each was scored by its own `run_experiment`, which sees only its own parameter
  grid — every composition was priced as though it were the only thing ever tried,
  understating selection bias by exactly N. `sibling_trials` (default 1, so single-strategy
  runs are untouched) multiplies the deflation count. `n_trials` is now
  compositions × candidates × folds.
- **PBO via CSCV** (`research/stats/pbo.py`, pure and deterministic). PBO answers what the
  DSR cannot: not "is this Sharpe big enough given N tries" but "does the in-sample ranking
  carry *any* out-of-sample information, or does picking the winner just pick noise?"
  Computed over **contiguous equal blocks** of the series (default 8-16) rather than the
  walk-forward folds, deliberately — CSCV needs 8-16 sub-periods for the combination count to
  mean anything while `n_folds` is 3-4. `optimize()` retains the (sub-period × candidate)
  `perf_matrix`; the orchestrator gates on `pbo ≤ 0.30` and **fails closed** — a matrix that
  cannot be evaluated (single candidate, too little data) does not pass. Two properties
  measured rather than assumed: pure noise averages **PBO 0.453 over 40 draws**, and a
  selection driven purely by local noise scores **1.000**. The per-draw spread on noise is
  0.09–0.89, so the null is asserted on the **mean across draws**; a per-seed assertion would
  be asserting something false. 16 tests.
- **`stats/neff.py` wired.** It had existed since M0 with **no consumer**. Its place is the
  promotion step: `run_experiment` validates per instrument then takes
  `max(validated, key=dsr)` — a selection exactly like picking the best of N parameter draws,
  entirely unaccounted. Deflating by raw N would overstate the fix because these names move
  together, so N_eff is the honest count (ρ ≈ 0.4 turns 200 large-caps into ~2.5 independent
  bets). New `mean_pairwise_correlation` (aligns series on their common **recent tail** —
  different history depths would otherwise compare different calendar periods) feeds
  `effective_sample_size`; the promotion record carries
  `breadth: {n_validated, mean_correlation, n_effective}`. **A bug caught in review:** the
  first cut reused the loop variable `var_sr` for the cross-instrument deflation, which would
  have applied whichever instrument was iterated *last* — its parameter-search dispersion —
  to a decision about instruments. Dispersion is now measured across the instruments
  (`breadth_var_sr`), pinned by test. 9 tests.
- **Optimizer objective** was already `metrics.consistency × √n` (a trade-count-aware
  t-statistic, not raw expectancy) since `1ec5188`; verified by reading the code, and the
  stale `Trial.is_objective` comment saying "expectancy" was corrected.
- *Acceptance*: a synthetic no-edge universe swept wide produces **zero** promotion
  candidates; the same sweep with deflation stubbed off produces several
  (`research_tests/test_deflation_engages.py`).

**Phase 1 — the nightly loop, shadow mode (2026-08-01).**
- **`nightly._load_plan()` no longer returns `[]`** (`9596995`). It had since M0, so every
  guardrail, gate and statistic sat behind a scheduler that scheduled nothing — the cron
  one-shot was a well-tested no-op. New `research/plan.py` orders OPEN hypotheses by
  `retest_priority`, giving that field its **first consumer** (written on every run since M0,
  read by nothing, which is why a killed idea was never actually revisited). Eligibility is a
  **hard filter with no fallback to "everything"**: an empty eligible universe yields an
  empty plan, because a fallback there would point research at live positions. Cold start
  seeds one hypothesis on the commodity sandbox. Bounded per night (3 experiments × 6
  instruments) and deterministic (sorted, sandbox-first). 14 tests.
  - *Sector seeding deliberately NOT implemented*: no sector metadata exists on `Instrument`
    and no edge map exists as data — it lives only as prose. Inventing classifications would
    fabricate the very input the ordering claims to use.
- **The loop ran end to end — first time, 2026-08-01**, verified by execution rather than by
  test: a real invocation produced `research.db` with 1 program, 1 hypothesis and **6
  Findings**, plus `report_run_1.md`. Promotion was correctly **none** — the synthetic market
  has no exploitable edge, which is the right answer and a useful no-false-promotion signal.
  Note the mock returns a fixed 966-bar series regardless of interval, so instruments were
  rejected for insufficient trades (1–5 against a 20 floor); that is a property of the
  synthetic data, not of the strategy.
- **Nightly invokes `run_generated` on the plan** — `nightly._run_generation`, `d2f42f8`
  (2026-08-01). **The ROADMAP box for this is still unticked; the code is present and
  bounded by `PT_RESEARCH_GENERATE_LIMIT` (default 8).** It reuses the plan's instrument set
  so generation and the handwritten baseline are evaluated on exactly the same universe, and
  passes the composition count into `sibling_trials`, so a wider search genuinely raises the
  bar it must clear.
- **Where the cron runs — DECIDED 2026-08-01: NOT the production VPS.** The droplet is 1 GB
  and has OOM'd twice; a research sweep (`n_folds × n_candidates` backtests plus
  `n_blocks × n_candidates` more for the PBO matrix) is far heavier than the Vite build that
  already took live positions down. The live risk lane must beat every second; research has
  no deadline that justifies risking it. Runs on the Mac; `PT_RESEARCH_ENABLED` stays `0` on
  the VPS. Reasoning in `docs/operations.md`.

**Phase 2 — widen the idea space (2026-08-01 → 2026-08-02).**
- **New blocks**: RSI as a whole family, `volume_surge`, `gap_up_pct`/`gap_down_pct`,
  `body_frac_gt` — library 13 → 19. All pure and warmup-safe (a comparison against NaN yields
  False, never a phantom True). The RSI threshold is declared `pct`, not `thr`, because `thr`
  is bounded to |x| ≤ 10 for z-scores while RSI reads 0–100.
- **Opening-range breakout + time-of-day window — 2026-08-02, `83be178`.** Library 19 → 23
  and, for the first time, complete. Two hazards the pure bar-math blocks never had.
  **Look-ahead**: an opening range is the only construct that summarises a group of bars and
  then asks other bars about it; computed the obvious way (groupby-max-broadcast) bar 2 would
  "break out" of a range including bar 8, and the leak would be invisible because the
  backtest would simply look good. The range is built via `.where(inside)` **before** the
  groupwise max, and no bar inside the window can fire. **The host clock**: these read the
  wall clock recorded ON THE BAR and never call a clock function — asserted under `TZ=UTC`,
  `Asia/Kolkata` and `America/New_York`. Both fail closed. `minute` is a new grammar kind
  because no existing one could express one: `length` caps at 400, `thr` at |10|, `pct` at
  100, `choice` at 15 — and the market opens at minute **555**.
- **Every registered block is REACHABLE — 2026-08-02, and it was not before.** Seven of
  twenty-three registered blocks were **never drawn** across 200 seeds; four (`atr_pct_lt`,
  `gap_up_pct`, `gap_down_pct`, `still_expanding_z`) were dead from the day they landed.
  `search.py`'s own comment claimed sampling "draws from the registry itself, which is what
  makes a new block reachable the moment it is registered" — **false the day it was written**:
  the draw functions are hand-written string templates, so registering a block buys a
  whitelist entry, not a draw. The comment is corrected and
  `research_tests/test_every_block_is_reachable.py` fails the build on the next one. All 23
  now draw, with mirror pairs balanced (a long/short asymmetry in a draw arm does not fail
  loudly — it yields a strategy that trades one side by accident).
- **`volume_surge` had no volume — FIXED 2026-08-02.** It read **False on every real frame
  that has ever existed**: Kite returns a volume on every historical bar, but
  `candles_to_df` built the frame from five keys and `volume` was not one of them. The
  unconsumed-mechanism guard structurally cannot see this shape — `volume_surge` *has*
  callers; what it lacked was **data**. The cost was not a missing feature: a composition
  containing it produces zero signals, so the nightly burned trials on candidates that were
  never candidates — and every one still counted toward the deflation trial count, making the
  DSR bar *harder to clear* for the compositions that were real. `volume` is now in
  `FRAME_COLUMNS`; the price columns are asserted unchanged, because a moved price column
  would move every live signal and every stored backtest result.
- **Price-source × smoothing-kind as parameters.** `close|hl2|hlc3|ohlc4` ×
  `sma|ema|wilder|hull` = 16 lawful variants of a single block. **Encoded as bounded INTEGER
  codes, not strings, and that is load-bearing**: the emitted `compute` is AST-validated
  against numeric literals only, so a string parameter would have opened that perimeter.
  Codes clamp rather than raise (a generated composition must never crash the nightly on an
  arithmetic accident), and code 0 is the conventional reading in both families, so adding
  the parameter never silently re-tunes an existing composition. **A real bug this
  surfaced:** Hull smoothing (`2·MA(n/2) − MA(n)`) can overshoot below zero, which drove RSI
  to **−22**; gains and losses are non-negative by definition, so the averages are now floored
  at zero.
- **Seeded random sampling.** `sample_compositions(limit, seed)` draws from the block
  registry rather than a fixed list of hand-written strings — the old 3×3×2 grid named its
  blocks as literal strings, so adding the Phase-2 vocabulary widened the whitelist and
  changed the search **not at all**. Same shape as the `var_sr` bug: present, correct,
  unreachable. Deterministic per seed, duplicate keys skipped (they would collide in
  `research_generated_strategy` and silently overwrite each other), bounded attempts.
  `PT_RESEARCH_SEARCH_SEED` unset keeps the deterministic grid as a stable control. Verified
  end to end: seed 11 produced 6 distinct compositions spanning RSI variants across three
  price sources and four smoothings.

**Phase 3 — the reinforcement loop (2026-08-01).**
- **Generation READS knowledge.** `research/knowledge.py` + `research_block_edge`. Counts
  **block families** rather than compositions (a composition is a one-off; a family is the
  level at which a lesson generalises), suppresses families with a well-powered negative
  record on an instrument, and mutates survivors with *small* nudges (a mutation that
  rewrites everything is just a fresh random draw). Qualification failures are recorded too,
  not only validation failures — otherwise the map is blind to every idea that never produced
  enough trades to be judged, which on real data is most of them.
  **THE BUG THIS SHIPPED WITH, CAUGHT BY RUNNING IT:** the obvious implementation destroys
  the search. On a universe where nothing works yet, every family accumulates a losing
  record — suppression took **all four trend families at once**, and since every composition
  structurally requires a trend block, the sampler could draw NOTHING; night 4 ran 1
  experiment instead of 6 while reporting success. Two guards: a `MAX_SUPPRESSED_FRACTION`
  (0.4) exploration floor applied worst-ranked-first, and a last-resort fallback where the
  sampler explores anyway if suppression blocked every lawful draw — **logged loudly**,
  because a silent override makes the next person unable to explain why a suppressed family
  reappeared. Suppression is a preference, never a cage.
- **`block-family × instrument` edge map**, rendered into every generated run's report as
  "which idea works where", alongside the families suppressed for that run — a reinforcement
  loop nobody can read is one nobody can debug. `edge_weights()` exposes Laplace-smoothed
  per-family weights bounded to [0.25, 2.0], a deliberate exploration floor. Verified across
  four consecutive nightly runs on the same DB: 90 edge rows accumulated, and night 4's
  behaviour provably differed from night 1's.

**Phase 4 — shadow-paper stage (2026-08-01).**
- **A `shadow` state between validated and pending.** `research/shadow.py` +
  `research_shadow_session`. Candidates are born `shadow`, not `pending`: a validated
  candidate has only cleared a **retrospective** bar (every parameter chosen with the whole
  series visible; deflation and PBO discount that, they cannot remove it). It must survive
  sessions it has never seen. Never touches the execution plane — no order, no position, no
  row in `paper_trader.db`. Fails closed: too few sessions, no trades, or an unreadable
  record all mean NOT ready. **Two details that decide whether the gate is real**: sessions
  count **distinct dates**, not rows (a candidate run on six instruments for one day has seen
  one session, not six), and recording is idempotent per (candidate, date, instrument) so
  replaying a day cannot inflate the evidence. `MIN_SHADOW_SESSIONS = 5`.
- **Shadow-vs-backtest comparison.** `comparison()` puts expected next to realised (hit rate,
  avg per trade, deltas, net P&L) and is attached to the candidate on promotion, preserving
  the original scorecard. Deliberately **reported, not judged** — inventing a pass mark for
  how closely a small shadow sample must track a backtest would be false precision. Carries
  an explicit `underpowered` flag.
- *Acceptance MET*: `approval_queue()` returns only `pending`, and the only path from
  `shadow` to `pending` is `promote_if_ready`. Pinned by a **negative** test — a fresh
  validated candidate is ABSENT from the queue.

**Phase 5 — regime conditioning (2026-08-01).**
- **Bars labelled into regimes.** `research/regime.py`: trend/chop × volatility, per bar,
  pure and deterministic. Trend uses **Kaufman's efficiency ratio** (net displacement ÷ path
  walked) rather than ADX — a single bounded number with no smoothing constants, so labels
  are reproducible instead of parameter-sensitive. The volatility split is **relative to the
  instrument's own history**: an absolute ATR% threshold would label every commodity "high"
  and every index "low", describing the universe rather than the market state.
  **No look-ahead, pinned by test:** the volatility median is **expanding**, not a full-series
  quantile — a quantile would make bar 10's label depend on bar 900's volatility, leaking the
  future invisibly because the leak would live in the *labelling* rather than the strategy.
  The test truncates the series and asserts surviving labels are unchanged. 15 tests.
- **Per-regime context in every run report.** Real output: COPPERM 64 `trend_hi` vs CRUDEOIL
  81 `chop_hi` on the same window — visibly different markets, which no aggregate shows.
- **The generator CONDITIONS on regime.** A `regime_is(code)` block lets a composition say
  "only trade this in high-volatility trends", and the sampler draws it. Choosing *which* of
  four regimes is itself a selection, so `run_generated` multiplies `sibling_trials` by 4 —
  but **only for compositions that actually use the block**, because inflating every
  candidate merely because the feature exists would deflate ideas that never made that
  choice. *This is why Phase 5 was gated behind Phase 0*: before deflation genuinely engaged,
  regime conditioning would have been a machine for manufacturing regime-specific mirages.
  Safety property pinned by test: a frame the labeller cannot read yields **no signal**, never
  an unconditional one — a broken filter must narrow the strategy to nothing rather than
  silently deleting the condition it was added to impose. The four blocks are proven to
  partition the labelled bars exactly.

**Earlier (M0 → 2026-07-20).** Foundations on `feat/research-plane`: own `research.db` with
its own `Base`, immutable content-hashed `ExperimentSpec` + mutable `ExperimentRun`,
fail-closed guardrails, pure-kernel reuse, the `DataSource` seam with a real candle content
hash, the watchlist-eligibility rule and the permanent commodity sandbox
(`GOLDM, SILVERM, CRUDEOIL, NATURALGAS, COPPERM`). Design and the nine adversarial reviews
that shaped it: `docs/research/ARCHITECTURE.md`.

## 5. Active roadmap

- [x] **Every run binds to what produced it (F14) — DONE 2026-08-03.**
      `research/strategy/builder/ir_search.py` + `research_tests/test_ir_search.py`, 15 tests.
      `explore()` walks `propose.lineage()` and, for the seed graph and every proposal,
      validates → resolves → evaluates → `experiment.record()`. The binding is derived from
      *that step's* `ResolvedGraph`; nothing is passed in. Deterministic — one seed threaded
      through, no RNG, clock or uuid in the module.
      - Built **before** any search objective, deliberately: a run recorded without a binding is
        permanently unattributable, and this repository already owns a corpus with that defect.
      - Seven suppressions, each with its mutation target asserted present first, each turning
        its own test red: the legality check, pairing a record with the wrong step's graph,
        dropping the inputs from the digest, ignoring the seed, a constant experiment id,
        dropping the observation, and planting a `SHARPE_FLOOR` (C14 guard).
      - *Named `ir_search.py`, not `search.py`.* `search.py` already exists and is Generation 1's
        live composition sampler, imported by `orchestrator/generate.py` and six test modules.
        Overwriting it would have deleted the generator the nightly runs on.
      - **Two findings worth carrying.** A lineage returns to earlier structures (add a
        predicate, drop it again), so bindings are *not* all-distinct across a walk — that is the
        address being correct rather than colliding, and the test asserts the converse (one
        binding never covers two different graphs) over a canonical node/edge form, because
        `edit.py` leaves edge *list order* differing between otherwise identical graphs. And
        `ExperimentRecord.binding` covers identities, versions and the data digest but **no
        edges** — it survives a `rewire` only because `ResolvedNode.cache_id` folds in upstream
        cache ids. F14's wiring sensitivity is therefore a property of *resolution*, not of the
        record shape. Anyone setting a component's `cache_identity` to `"declared"` breaks that
        transitivity and should know it.

- [ ] **Bind every research run through `app/ir/experiment.py` (F14).** *This comes before a
      search objective, and the ordering is not stylistic.* F14 requires every experiment and
      every finding to record the exact graph version and every resolved component version
      that produced it; `app/ir/experiment.py` derives that binding from a `ResolvedGraph` —
      `record()` has no parameter for the versions, because a record that can be *told* its
      versions can be told last week's, and stale-not-missing is the failure that has actually
      happened here. **Versioning's value is retrospective: adding it late leaves every prior
      run permanently unattributable, and this platform has already paid that exact price
      once** (§7 — every Finding predating 2026-08 is unusable as a baseline). A search loop
      that runs before binding manufactures a second corpus with the same defect, at a much
      higher rate. Concretely: `research/` currently imports `app.ir.authoring` and
      `app.ir.edit` and **not** `app.ir.experiment` (verified 2026-08-03 by grepping every
      `from app.` in `backend/research/`). The work is to make the orchestrator record an
      `ExperimentRecord` per run and a `Finding` carrying that record's `binding`, and to make
      it impossible to persist a Finding without one.
- [ ] **The Generation-2 search loop.** With binding in place: propose → resolve → evaluate →
      score through the existing gates (qualify, walk-forward, DSR with `sibling_trials`, PBO
      ≤ 0.30 fail-closed, N_eff breadth), feed accepted graphs back through `knowledge.py`,
      and keep the objective *outside* `propose.py` — C14 says the proposer proposes and does
      not score, and a test greps for that.
- [x] **Each block declares the inputs it reads — DONE 2026-08-03.** `BlockSpec` gained
      `inputs` and `needs_clock`; `derive()` builds sockets from the declaration and the adapter
      rebuilds only those columns. **45 declared sockets across 23 blocks, down from 115** — most
      read `close` alone. F4 is respected: the declaration is authoritative and the
      implementation is checked against it, never inferred from it.
      - *Verified empirically, not by AST.* `regime_is` reaches through `research/regime.py` and
        the opening-range blocks through helpers, so a syntactic check would have to chase every
        call across every module and would still miss a dynamic one. Instead each block runs on a
        frame containing only what it declared and must produce the identical series
        (`research_tests/test_block_declared_inputs.py`).
      - *Under-declaration is the failure that matters, and it is silent.* Several of these
        blocks fail **closed** on a missing column — `volume_surge` reads False, `time_of_day`
        returns all-False — so an under-declared block would not raise. It would quietly switch
        a filter off, and a generated strategy would lose a condition somebody added on purpose.
      - **The bar clock is not a socket.** F7's value types are float/int/bool and a datetime is
        none of them, so declaring `date` as a wire would have needed a format amendment.
        It is the series *index*: `needs_clock` says a block reads it, and the adapter supplies
        it from the index. No amendment needed.
      - *Two wrong tests written before the right one, both recorded in the file.* Perturbing a
        column by a positive affine transform proves nothing — `close > EMA(close)` is invariant
        under it. And a removal check calls `rsi_gt` over-declared at its sample args, because
        `source=0` reads only `close` while `source=3` (ohlc4) reads all four; a declaration
        covers the whole parameter domain, so choice-carrying blocks are checked across every
        lawful choice value instead.
- [ ] **Surface `strategy/explain.py` on the approval queue.** The plain-language explanation
      is already rendered into every run report by `report._render_explanation`; what remains
      is showing it where the human actually decides.
- [ ] **A week of unattended nightly runs on real Kite candles** (Phase 1's stated
      acceptance): `research.db` holding a real Findings corpus, reports landing in
      `PT_RESEARCH_REPORT_DIR`. The mock provider's fixed 966-bar series cannot produce one —
      every instrument is rejected for insufficient trades, which measures the fixture, not
      the strategy.
- [ ] **Sector seeding of the plan**, once sector metadata exists on `Instrument` as data
      rather than as prose in a roadmap paragraph. Deliberately not faked.

## 6. Acceptance criteria

A change in this workstream is done when **all** of the following are true.

**The isolation rule still holds — this is non-negotiable and comes first.**
```bash
# from backend/
.venv/bin/python -m pytest research_tests/test_guards.py research_tests/test_env_is_never_live.py
git diff --stat -- backend/app/          # empty, except the sanctioned bridge/kernel files
grep -rn "from app\.\|import app\." backend/research   # only the seams listed in §3
```
- `research/guards.py` stays fail-closed. Do not weaken `FORBIDDEN_MODULES`, do not turn a
  raise into a warning, do not add a "skip guards in dev" flag.
- `PT_RESEARCH_ENABLED` stays `0` on the production VPS.
- `research.db` never resolves to `paper_trader.db`.
- `research/` may import `app.ir`; `app/ir` (and everything else under `app/`) must never
  import `research/` except through `app/core/research_read.py` and
  `app/core/generated_strategies.py`.

**Both suites green, plus the ledger proof.**
```bash
# from backend/
.venv/bin/python -m pytest research_tests --tb=line      # 405 passed (2026-08-03, cdbe686)
.venv/bin/python -m pytest tests research_tests           # BOTH — bare pytest skips research_tests
.venv/bin/python scripts/dryrun.py 700                    # ledger paisa-exact
```
Note `testpaths = tests` in `pytest.ini`: a bare `pytest` does **not** run this workstream's
suite. Note also that `addopts = -q` plus a second `-q` on the command line suppresses the
pass/fail summary line entirely — run without the extra `-q` if you want to see the count.

**New statistics or gates:**
- Pure and deterministic — no clock, no unseeded `Random`, no uuid, no I/O.
- Fail **closed**: an input that cannot be evaluated does not pass (`pbo_gate` is the
  reference implementation of this discipline).
- Null behaviour measured, not assumed: a statistic must be shown to report *not-clean* on
  noise. Assert on the mean across draws where the per-draw spread makes a per-seed
  assertion false.

**New blocks:**
- Registered, warmup-safe (NaN comparisons yield False), reachable by the sampler
  (`test_every_block_is_reachable.py` fails the build otherwise), and given data that
  actually exists in `FRAME_COLUMNS`.
- If it derives to a component, it must be bar-for-bar equivalent to the block on a fixture
  that makes it fire.

**New mutations or IR consumption:**
- Route through `app/ir/edit.py`. A second implementation of the format is a defect; a test
  greps for one.
- Seeded and replay-exact.
- The proposer must not score. `sharpe`, `fitness`, `objective`, `rank` do not appear in
  `propose.py`, and a test asserts it.

**Every claim in this document carries its command and output.** No mechanism is called done
without a consumer: unit tests pass happily on code with no callers, on code with callers but
no data, and on code registered but never drawn.

## 7. Known technical debt

- **Every research Finding recorded before 2026-08 is unusable as a baseline.** DSR deflation
  never engaged: `var_sr` was computed nowhere, so `expected_max_sharpe()` returned 0 and the
  DSR degraded to a PSR against zero on every candidate ever scored — while a docstring
  claimed a wider search raised the bar. *Cost of leaving it:* zero if the old corpus is
  never trusted; catastrophic if it is used as prior evidence, because those numbers are
  confidently wrong in the optimistic direction. *Trigger:* any decision that reaches for a
  pre-2026-08 Finding. **This is precisely why F14 binding is the next item in §5** — the
  reason those runs are unusable is that nothing records what produced them, so they cannot
  even be re-scored.
- **`Vocabulary.families` defaults to `None` with a `# type: ignore[assignment]`**
  (`propose.py:34`). A `Mapping` field typed non-optional and defaulted to `None`; any caller
  that reads it without passing one gets an `AttributeError` at a distance rather than a type
  error at the boundary. *Trigger:* the first mutation that wants family-aware swaps
  (e.g. "swap within family") — make it `Mapping[...] = MappingProxyType({})` or genuinely
  optional then.
- **`DOMAIN` in `ir_components.py:20` is unused.** Verified: the only occurrence in
  `backend/research/` is its definition; `_bar_domain()` beside it is also unreferenced.
  Dead constants next to live ones invite someone to read them as the configured default.
  *Trigger:* the first per-instrument/per-timeframe component derivation — either use it or
  delete it.
- **Every derived component declares the whole OHLCV frame** (`BAR_INPUTS`), not the inputs
  its block actually reads, because the adapter rebuilds the full frame to call
  `BlockSpec.fn`. *Cost:* the interface over-declares, so F4's guarantee (the interface is
  declared and exact) is weaker than it looks, and a structure search cannot reason about
  which nodes genuinely need volume. *Trigger:* any component-level dependency analysis, or
  the first data source that cannot supply one of the five columns. Fix belongs in the
  blocks' own declarations — inferring from the body is what F4 forbids.
- **The F4 interface check reports `unchecked` for all 23 derived components**, because one
  adapter serves all of them and reaches `inputs`/`params` dynamically. This is honest rather
  than wrong, but it means the derived half of the library is exempt from a check the
  hand-authored half passes. *Trigger:* narrowing the declared inputs above would make
  per-block adapters plausible and the check meaningful.
- **The ROADMAP box for "nightly invokes `run_generated`" is unticked while the code exists**
  (`nightly._run_generation`, `d2f42f8`). Prose drift of exactly the kind this repo has been
  bitten by; recorded here rather than silently ticked elsewhere.
- **`search.py` draw functions are hand-written string templates**, so registering a block
  buys a whitelist entry, not a draw. `test_every_block_is_reachable.py` now fails the build
  on a missed one, which makes the defect visible rather than absent. *Trigger:* Generation
  2's structure search replaces string templates with graph mutation, at which point this
  disappears with the templates.
- **The permissive watchlist-snapshot fallback.** A missing snapshot means "nothing known to
  be committed", so an unconfigured nightly treats every instrument as research-eligible. It
  logs loudly ("this run may develop strategies on LIVE instruments") but it is safe in the
  *permissive* direction, which is the opposite of every other default in this package.
  *Trigger:* the first nightly run against a real, populated execution side.

## 8. Blockers

- **Owner decision — when shadow mode is deliberately switched on.** `PT_RESEARCH_ENABLED`
  stays `0` until then. Nothing in code blocks it; flipping it is an operating decision.
- **Real candles for an unattended week.** Phase 1's acceptance cannot be met on the mock
  provider (fixed 966-bar series → every instrument rejected for insufficient trades). The
  cron runs on the Mac by decision, so the Mac must be up and Kite-authenticated for the
  window. This is an operational commitment, not a code task.
- **WS-01 owns `app/ir/experiment.py`.** The F14 binding work in §5 consumes it; a change to
  its record shape is WS-01's to make and must land with this workstream's consumer updated.
- **Sector metadata does not exist as data** (WS-07 / execution side). Sector seeding of the
  plan is blocked on it, and will not be faked.

## 9. Future work

Named, deliberately not scheduled.

- **A research cockpit frontend.** No route, no React. The read-only bridge already exposes
  the promotion queue and the run reports; nothing renders them. *Trigger:* the first
  promotion candidate that reaches `pending` from a real corpus.
- **Float-valued outputs in the block library.** There is not one: Wilder ATR is a private
  helper, so ATR cannot be named, shared, or forked. This is *the* Generation-2
  decomposability gap — structure search over predicates only is a much smaller space than
  structure search over signals. *Trigger:* the search loop plateauing on boolean-only
  structures.
- **Executable swappable slots / the primitive taxonomy** (W3 in `ARCHITECTURE.md`), cut from
  v1 and to be reintroduced with the builder milestone, gated on designing the grammar first.
  Generation 2's components are the modern form of this; revisit the taxonomy once the search
  loop exists.
- **Options research.** Deferred and index-only per the 2026-07 product pivot; the
  synthetic-premium path stays dormant. *Trigger:* the owner re-prioritising options, which
  currently run with `max_open_positions=0`.
- **Versioned dataset views** (W13), deferred until a second data source exists. Today:
  the `DataSource` seam plus a real candle content-hash.
- **FDR across final candidates.** DSR handles the trial count and PBO handles ranking
  stability; a false-discovery-rate control across the surviving candidates of a night is the
  third leg and is not built. *Trigger:* a night that produces more than a handful of
  survivors — which has never happened.
