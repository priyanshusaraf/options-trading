# Development Roadmap & Progress Tracker

> **This file is the agenda.** Every working session starts here: pick the top unchecked
> item in the active workstream, do it, check it off, update "Last verified". CLAUDE.md
> links here as the canonical "what's next". Keep this file honest — a checked box means
> *verified done* (tests green + the stated acceptance evidence), not "code written".

**Last verified: 2026-08-02** · Branch: `feat/exec-completeness` · VPS build **not measured this
session** — this file said `8cee4e9` and CONTINUE.md said `4e9f125`, which is exactly why neither
is repeated here. `curl /api/health` on the box is the only answer. Backend suites
`tests` + `research_tests`: **2,485 collected, PYTEST EXIT 0**, `dryrun.py 700` LEDGER OK,
`backtest_smoke.py` SWEEP OK · `PT_RESEARCH_ENABLED=0` · `index_futures_enabled=False`.

---

## Strategy OS — Component IR (new workstream, 2026-08-02)

**RFC 0001: [`docs/rfcs/0001-component-ir.md`](rfcs/0001-component-ir.md).** Status **Accepted
2026-08-02** — Gate 3 recorded against the owner's standing directive that the architectural
phase is complete and the RFCs define the architecture. The RFC says so in one line at the top;
if that reading is wrong, correct that line. Evidence base is
`~/dev/multiverse-of-ideas/reviews/` (nine systems read; 24 stable decisions, 14 patterns, six
honest gaps).

- [x] **RFC 0001 — the Component IR.** 14 Format clauses (the serialised core, with an EBNF
      grammar), 15 Contract clauses (observable properties, no mechanism), non-goals, amendment
      procedure. Gate 1 (expressiveness) met: five real artefacts expressed — `expanding_z_v4`
      with its real fifteen parameters, a decomposed Wilder ATR, a generated block-grammar
      strategy, a nested subgraph, a multi-timeframe ill-typed edge. Gate 2 (adversarial review)
      met. **Gate 3 — owner acceptance — is outstanding.**
      Spec: `docs/superpowers/specs/2026-08-02-component-ir-rfc-v1-design.md` ·
      Plan: `docs/superpowers/plans/2026-08-02-component-ir-rfc-v1.md`
- [x] **Conformance suite for §3, and C13.** `app/ir/schema.py` (the closed vocabularies) +
      `app/ir/validate.py` (the validator) + three test files, 67 tests. **F1–F13 are now
      enforced mechanically**; each returns violations naming its clause and path, so a failure
      reads `F7 at $.edges[1].domain.timeframe` rather than as a schema error about a key.
      - *Appendix A is executed, not asserted.* All five worked artefacts are real data in
        `tests/test_ir_corpus.py`: A.1–A.4 validate, and A.5's final edge is rejected on the
        **domain axis specifically** — the test pins the path and both timeframes, so a
        validator checking only value and structure (which would pass that graph) fails here.
      - *Every clause is proven load-bearing.* Suppressing any one of F1–F13 turns the suite
        red — swept all thirteen. That sweep found a **vacuous test of its own**: the F9
        uniqueness check passed under mutation because renaming a node also orphaned an edge,
        and the dangling edge raised F9 anyway. Now asserted by path.
      - *An unchecked clause is not a passing clause.* F7's edge type-matching needs a
        component library; without one `unchecked_clauses()` reports F7 rather than staying
        silent. **F14 is not enforceable at all** — the grammar has no experiment artefact —
        and `UNENFORCEABLE_CLAUSES` records that as a fact a test asserts.
      - *C13 (provenance-blind execution) holds, subtractively.* One `_REGISTRY`; a generated
        strategy is `register()`ed into the same dict a built-in is discovered into; no
        `Strategy` carries a field naming its origin. Guard proven red by planting
        `if strategy.is_marketplace:` in `engine/exit_monitor.py`.
- [x] **The resolver, and §4's remaining fourteen clauses with it — DONE 2026-08-02.**
      `app/ir/resolve.py` (the single resolution), `app/ir/kernels.py` (the registry that
      declares warmup, purity and cache identity), `app/ir/hashing.py` (canonical content
      addressing), and `tests/test_ir_resolution.py` — 52 tests. The order was forced and the
      reason held: C1–C12, C14 and C15 all constrain *resolution*, so they land with the thing
      that makes them testable rather than as a suite with nothing to run against.
      - *Appendix A.4 is the executed acceptance case,* not a sketch. Two instances of one
        definition resolve to `n_fast/n_smooth` and `n_slow/n_smooth`, stay distinguishable at
        lengths 7 and 21 (C4), keep those identifiers across re-resolution and across a
        reordering of the node list (C7), and a kernel missing from the registry is reported at
        `n_fast/n_smooth` — the authored vocabulary — rather than against a node the author
        never placed (C4).
      - *Every clause is proven load-bearing.* Suppressing each of C1–C11, C14 and C15 one at a
        time turns that clause's **own** test red — swept all of them. The sweep found a
        **vacuous test of its own**: the C2 no-mutation check compared a deep copy taken after
        other tests had already resolved the shared fixture, and a resolver that eats its input
        does so on the first call and is idempotent after. It now also resolves the shared
        specification and asserts it is still intact. C12 was proven red by planting a second
        `ResolvedGraph(` construction under `app/engine/`.
      - *Two clauses are enforced as an absence,* which is the stronger form: C12 by there being
        exactly one construction of a resolved graph in the tree (the `candles.py` defect was
        two hand-written implementations of one idea), and C6 by the resolver's source
        containing no clock, counter, random, environment or file read at all.
      - *One erratum, no `format_version` change.* Building the resolver found that A.2's
        `override length ← length` was inexpressible: the validator enforced F10 as "no mapping
        may be an override value" rather than as F10's actual text (no kind, no bounds, no
        display name). Recorded as RFC 0001 §6.3 E1. The accepted reference forms are a closed
        set, so "any mapping" is still refused. F8's `default_source` also gained a shape —
        a component reference and a socket — because resolution has to insert something and
        take the value from somewhere.
      - *Boundary nodes and kernel declarations were added without touching §3.* `graph.input`
        and `graph.output` are reserved *identifiers*, not grammar constructs; warmup, purity
        and cache identity live in the kernel registry, which §2 already says supplies kernels.
        Both are recorded in §6.3 so a reader of the format knows where they live.
- [x] **The component runtime — DONE 2026-08-02.** `app/ir/runtime.py` +
      `tests/test_ir_runtime.py`, 20 tests. Built immediately after the resolver and on purpose:
      a `ResolvedGraph` nothing evaluates is a correct mechanism wired to nothing, which is the
      shape of this codebase's defining defect. It evaluates A.4's graph with real kernels —
      Wilder's ATR decomposed into true range and a smoothing, instantiated at 7 and 21 — so the
      resolver's outputs stop being structure and start being numbers.
      - *Three §4 clauses become empirical rather than declared.* **C10:** composed warmup names
        the unsettled prefix, and `settled()` removes it, so reading an unwarmed indicator stops
        being the caller's job to remember. **C8/C9:** evaluation memoises on the cache identity
        resolution computed, and never memoises a node whose kernel declares an impurity policy —
        caching a declared impurity is caching a lie. **C11:** `check_causality` evaluates the
        graph on a prefix of the bars and on all of them and demands the shared bars match, so a
        kernel that reads ahead is caught whatever its author intended. Three real shapes are
        tested: `shift(-1)`, a centred rolling window, and a whole-series normalisation.
      - *The causality check was written the easy way first and a test caught it.* Comparing only
        the graph's **outputs** calls the normalisation case causal: dividing both branches by a
        max neither bar knew yet leaves `fast > slow` identical. It now compares **every node's**
        every socket.
      - *Every guarantee proven load-bearing.* Nine suppressions — cache lookup, cache key
        (instance id instead of identity), the purity gate, warmup, the index check, the
        every-node comparison, the reference series, the kernel lookup, the missing-input check —
        each turns its own test red.
      - *C13 holds subtractively again.* The runtime's only key for a kernel is its body's
        content address. A component's origin is not representable there, so no execution path
        can branch on it, and an unregistered address fails rather than falling back.
- [x] **`expanding_z_v4` expressed in the IR, and proven equal to the strategy — DONE
      2026-08-02.** `app/ir/strategies/expanding_z.py` + `tests/test_ir_strategy_parity.py`,
      19 tests. Appendix A.1 expressed this strategy as a sketch inside a markdown document,
      which proves what its author believed. This is the real artefact: 15 components, 17 nodes,
      47 edges, the 15 real parameters read off `default_params` rather than restated — resolved,
      evaluated, and asserted **equal to `ExpandingZImpulseV4.compute()` bar for bar** over 400
      bars, with entries firing on the fixture so the comparison is not two constant series.
      - *The kernels are bound to the strategy's own functions, not rewritten.* Seven expressions
        were extracted out of `compute()` into named pure functions (`zscore`,
        `adaptive_threshold`, `drift_score`, `range_in_atr`, `impulse`, `directional_entry`,
        `displacement_lost`); `compute()` calls them and so do the kernels. A second copy of the
        arithmetic would be the `candles.py` defect, and the parity test would then be comparing
        a copy to its original. What is under test is the **language**.
      - *Proven able to fail.* Binding `n_entry_thr` to `exit_pct`, and re-pointing one edge from
        `n_ema` to `n_z`, each turn the parity test red.
      - *A new fact about production strategy code, not only about the IR:* `check_causality`
        finds `expanding_z_v4` causal at every node — its "signals fire only on completed
        candles" claim is now measured rather than conventional. The check is proven able to go
        red on this graph by making the EMA peek one bar ahead.
      - *C8's economics, demonstrated:* moving `entry_pct` recomputes the threshold, the impulse
        and the two entry predicates, and reuses the EMA, ATR, z-score, drift and range. That is
        what makes a sweep cheap without building the sweep into the indicator (C14).
- [x] **The derived-parameter gap, closed — DONE 2026-08-02.** Writing the strategy graph turned
      up the one thing it could not express: `exit_abs`'s floor is `min_abs_z * 0.25`, and since
      an override carries a value only (F10), the graph first carried the literal `0.15` —
      correct at the shipped `min_abs_z = 0.60` and silently wrong the moment anyone moved it.
      **The resolution was not to weaken F10**, which is what protects a component author's
      constraints. A multiplication is a computation, and C14 says components compute: two new
      components, `value.scalar` (a parameter, on a wire) and `math.scale`, so the exit
      thresholds now *track* `min_abs_z` instead of remembering one of its values.
      - Verified by moving `min_abs_z` to 1.20 with the contraction exit switched on — which is
        the only configuration where the exit threshold reaches an output, and there is a test
        asserting that too — and re-checking bar-for-bar parity against
        `compute(min_abs_z=1.20, use_absz_contraction_exit=True)`. Proven able to fail by setting
        the scale factor to 0.
      - **This is the first use of F7's `scalar` structure axis.** It had been declared since the
        format phase and never exercised, and the runtime had assumed every value was a series.
        It now checks what is checkable — a series is bar-aligned, a scalar is passed through —
        and `check_causality` compares scalars whole, because a scalar derived from the bars is
        the sharpest lookahead there is: one number that saw everything.
- [x] **F14 enforced — the last unenforced clause in the RFC. DONE 2026-08-02.**
      `app/ir/experiment.py` + `tests/test_ir_experiment.py`, 23 tests. F14 binds every
      experiment and finding to the versions that produced it, and it had been recorded as
      *unenforceable* through the format and resolver phases because there was no experiment
      artefact. **The answer was never to widen §3** — an experiment is not a component or a
      graph, and admitting one would have bought a migration liability forever. The RFC's own
      note says F14 becomes enforceable when the *experiment system* defines a record; this is
      that record. `format_version` does not move.
      - *The binding is derived, not supplied.* `record()` takes a `ResolvedGraph` and reads the
        versions off it; there is no parameter for passing them in. F14's real failure mode is a
        **stale** field, not a missing one — which is why the record reaches
        `smoothing.wilder`, a component that appears nowhere in the specification's node list and
        is only known because resolution walked the ATR's body (C5).
      - *Five parts, each load-bearing:* the graph version, every component version, every node's
        cache identity (transitive over its upstream, C8), the data digest, and the id. A record
        naming graph version 3 of a graph that resolved as 4 passes every structural check and is
        caught only against the graph — which is the case the tests are built around.
      - *"And every finding."* A `Finding` carries its experiment's binding, so a claim that
        outlived a re-parameterised run is detected. That is the state this repository is in for
        everything before 2026-08.
      - *The sweep found a vacuous guard of its own:* every test of `node_identities` emptied it,
        which trips the presence check, so deleting the comparison against the resolved graph
        left the suite green. There is now a test for identities that are present and wrong.
      - `UNENFORCEABLE_CLAUSES` is now **empty**, and a bookkeeping test asserts every one of
        F1–F14 is enforced here, enforced elsewhere and named, or declared unenforceable and
        named. Nothing may be simply absent.
- [ ] **Adopt the runtime in a live path — NOT DONE, and it stops for the owner.** The engine
      still calls `compute()`; `app/ir/` is imported only by its own tests. This is RFC 0001
      Appendix C(d), a production change to a real-money path: it needs owner acknowledgement
      before any deploy regardless of green tests. The parity evidence it would need now exists.
- [ ] The seven remaining Strategy-OS subsystems — visual computational graph, Python component
      authoring, Research Plane Gen 2, experiment system, marketplace, deployment, production
      adoption — **each need their own spec → plan → build cycle.** That list is a programme, not
      a roadmap item. (The component runtime, which used to head this list, is done above.)

**This workstream still changes no running behaviour.** `backend/app/ir/` is imported only by
its own tests: no engine, route, or backtest path reaches it. It is a validator and a resolver
for a format nothing yet stores. The two places it touches existing code are read-only — the C13
and C12 guards *grep* `app/engine`, `app/backtest`, `app/strategy` and `research/` without
importing or altering them. Nothing was deployed and the VPS is unaffected.

Two findings about the *current*
system fell out of writing the worked examples, both recorded in Appendix A rather than fixed
here: the block library has no float-valued output at all (Wilder ATR is a private helper, so ATR
cannot be named, shared, or forked — the Gen-2 decomposability gap), and generated strategies
identify themselves by a content hash over source, which RFC 0001 F2 makes the body's address
rather than the identity.

> **2026-08-01/02 — a long autonomous session. 52 commits, every one deployed and verified.**
> What changed, and what did NOT:
>
> **Phase 1 (stabilization) is fully verified**, not merely read: readiness probe
> (`/api/health` can now say no), a real connection leak in `_upsert_state`, the candle
> validation seam, feed-quality reporting, the backtester audit (slippage was entirely
> unmodelled on the spot path), a timezone audit, replay mode, and the deterministic-execution
> audit — which found the **kill switch** could abort halfway and leave positions open while
> looking like success.
>
> **Workstream A (research plane) is complete, Phases 0–5.** The headline finding: DSR
> deflation had **never engaged** — `var_sr` was computed nowhere, so the lab silently
> overstated every finding it made while a docstring claimed otherwise. **Treat any Finding
> in `research.db` predating 2026-08-01 as unvalidated, not as a baseline.**
>
> **Workstream E2 (index futures) is complete and OFF.** All twelve build steps, ledger
> paisa-exact through profit/loss/short/force-flat round trips with the flag ON in test.
> Step 13 (owner review) is the only thing between it and live. **E3's carry model** is built
> and off; its lifecycle semantics need owner intent, not more code.
>
> **The pattern worth carrying forward:** seven mechanisms were found built, correct, and
> wired to NOTHING (`var_sr`, `neff`, `retest_priority`, new blocks the sampler couldn't
> reach, `/api/health` + `/api/storage` data no screen showed, `PaperBroker.close()`, and
> `edge_weights()` — the last one committed during this very session, hours after the pattern
> was named). Unit tests pass happily on code with no callers.
> `tests/test_no_unconsumed_mechanisms.py` now fails the build on the eighth.

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
> not intervening.
>
> **What to check on the next trading session, in order** (all three were built during the
> 2026-08-01/02 session and NONE could be observed on a closed Saturday market — absence of
> evidence, not evidence of absence):
> 1. **Connect Kite**, then `curl /api/status` → `ledger_drift` should appear and sit near
>    zero. The ledger-honesty fix is deployed but its effect has never been seen: the
>    re-anchor reads live Kite funds, so with no valid token `_account_funds` was `None` and
>    the field was simply absent.
> 2. `curl /api/health` → `provider_feed`, and grep the log for `FEED_QUALITY`. This is the
>    first real answer to "is Kite's candle history actually dirty?" — the validator has been
>    repairing silently and nobody has ever seen the report.
> 3. The retuned **150 / 0.7** give-back lock takes its first live session.
>
> `TARGET` has fired zero
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
- [x] **Opening-range breakout + time-of-day window — DONE 2026-08-02 (`83be178`), TDD.**
      The library is 19 → 23 blocks and, for the first time, complete: every registered
      block is reachable by the search.
      Session awareness carries two hazards the pure bar-math blocks never had.
      **Look-ahead:** an opening range is the only construct in the library that
      summarises a group of bars and then asks other bars about it. Computed the obvious
      way — groupby, max, broadcast — bar 2 of the session would "break out" of a range
      that includes bar 8, and the leak would be invisible because the backtest would
      simply look good. The range is built via `.where(inside)` BEFORE the groupwise max,
      and no bar inside the window can fire; both pinned by test.
      **The host clock:** the timezone audit found a live stop that would have silently
      stopped firing on a rebuilt UTC droplet. A time-of-day filter invites exactly that
      bug, so these read the wall clock recorded ON THE BAR and never call a clock
      function — asserted under `TZ=UTC`, `Asia/Kolkata` and `America/New_York`.
      Both fail closed (a frame they cannot place in time reads False, never True), and
      `minute` is a new grammar kind because no existing one could express one: `length`
      caps at 400, `thr` at |10|, `pct` at 100, `choice` at 15 — and the market opens at
      minute **555**. Same mistake as declaring the RSI threshold a `thr`, one step on.
- [x] **Every registered block is REACHABLE — DONE 2026-08-02, and it was not before.**
      Building the two blocks above surfaced the real defect. Seven of twenty-three
      registered blocks were **never drawn by the search** across 200 seeds — four of them
      (`atr_pct_lt`, `gap_up_pct`, `gap_down_pct`, `still_expanding_z`) dead since the day
      they landed. `search.py`'s own comment claimed sampling "draws from the registry
      itself, which is what makes a new block reachable the moment it is registered."
      **That was false the day it was written** — the draw functions are hand-written
      string templates, so registering a block buys a whitelist entry, not a draw. The
      comment is corrected in place, and
      `research_tests/test_every_block_is_reachable.py` fails the build on the next one,
      which is what makes the corrected claim safe to write down.
      All 23 now draw, with mirror pairs balanced (a long/short asymmetry in a draw arm
      does not fail loudly — it yields a strategy that trades one side by accident).
- [x] **`volume_surge` had no volume — FIXED 2026-08-02.** It read **False on every real
      frame that has ever existed**. Kite has returned a volume on every historical bar
      since `kite.py:360` was written; `candles_to_df` built the frame from five keys and
      `volume` was not one of them. The unconsumed-mechanism guard structurally cannot see
      this shape — `volume_surge` *has* callers; what it lacked was **data**.
      The cost was not a missing feature. A composition containing it produces zero
      signals, so the nightly burned trials on candidates that were never candidates —
      and every one still counted toward the deflation trial count, making the DSR bar
      *harder to clear* for the compositions that were real. `volume` is now in
      `FRAME_COLUMNS`; the price columns are asserted unchanged, because a moved price
      column would move every live signal and every stored backtest result.
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
- [x] **Shadow state between validated and pending — DONE 2026-08-01.** `research/shadow.py`
      + `research_shadow_session`. Candidates are now born `shadow`, not `pending`: a
      validated candidate has only cleared a RETROSPECTIVE bar (every parameter chosen with
      the whole series visible; deflation and PBO discount that, they cannot remove it). It
      must survive sessions it has never seen before a human is asked.
      Never touches the execution plane — no order, no position, no row in
      `paper_trader.db`. Fails closed: too few sessions, no trades, or an unreadable record
      all mean NOT ready.
      **Two details that decide whether the gate is real:** sessions count DISTINCT DATES,
      not rows (a candidate run on six instruments for one day has seen one session, not six
      — counting rows would let a wide universe fake persistence in an afternoon), and
      recording is idempotent per (candidate, date, instrument) so replaying a day cannot
      inflate the evidence.
- [x] **Shadow-vs-backtest comparison — DONE 2026-08-01.** `comparison()` puts expected next
      to realised (hit rate, avg per trade, deltas, net P&L) and is attached to the candidate
      on promotion, preserving the original scorecard. Deliberately REPORTED, not judged:
      inventing a pass mark for how closely a small shadow sample must track a backtest would
      be false precision. It carries an explicit `underpowered` flag so nobody reads a
      3-session agreement as confirmation.
- [ ] Reuse `strategy/explain.py` for the plain-language "what it does" at approval time.
      (Already rendered into every run report by `report._render_explanation`; what remains
      is surfacing it on the approval queue itself.)
- **Acceptance: MET.** `approval_queue()` returns only `pending`, and the only path from
  `shadow` to `pending` is `promote_if_ready`, which requires ≥`MIN_SHADOW_SESSIONS` distinct
  sessions with real trades and attaches the comparison. Pinned by a negative test — a fresh
  validated candidate is ABSENT from the queue — which is the only kind of assertion that
  means anything here.

### Phase 5 — Regime conditioning *(only after 0–3 produce trustworthy data)*
- [x] **Label bars into regimes — DONE 2026-08-01.** `research/regime.py`: trend/chop ×
      volatility, per bar, pure and deterministic. Trend uses Kaufman's efficiency ratio
      (net displacement ÷ path walked) rather than ADX — a single bounded number with no
      smoothing constants, so labels are reproducible instead of parameter-sensitive. The
      volatility split is RELATIVE to the instrument's own history: an absolute ATR%
      threshold would label every commodity "high" and every index "low", and the map would
      describe the universe rather than the market state.
      **No look-ahead, pinned by test:** the volatility median is EXPANDING, not a
      full-series quantile — a quantile would make bar 10's label depend on bar 900's
      volatility, leaking the future into every conditional result invisibly, because the
      leak would live in the labelling rather than the strategy. The test truncates the
      series and asserts surviving labels are unchanged. Warmup bars are `unknown`, never
      "chop". 15 tests.
- [x] **Per-regime context reported — DONE 2026-08-01.** Every run report now carries the
      regime distribution per instrument. Real output: COPPERM 64 `trend_hi` vs CRUDEOIL 81
      `chop_hi` on the same window — the instruments are in visibly different markets, which
      no aggregate statistic shows.
- [x] **Generator CONDITIONS on regime — DONE 2026-08-01, wired together with the
      deflation as promised.** New `regime_is(code)` block lets a composition say "only trade
      this idea in high-volatility trends", and the sampler draws it. Choosing WHICH of four
      regimes is itself a selection, so `run_generated` multiplies `sibling_trials` by 4 —
      but **only for compositions that actually use the block**, because inflating every
      candidate merely because the feature exists would deflate ideas that never made that
      choice.
      This is why Phase 5 was gated behind Phase 0: before deflation genuinely engaged (it
      did not until today), regime conditioning would have been a machine for manufacturing
      regime-specific mirages.
      Safety property pinned by test: a frame the labeller cannot read yields **no signal**,
      never an unconditional one. A broken filter must narrow the strategy to nothing rather
      than silently deleting the condition it was added to impose. The four blocks are also
      proven to partition the labelled bars exactly — mutually exclusive, jointly covering
      everything that is not `unknown`.
      **Workstream A is now complete: Phases 0 through 5.**

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
- [~] **New segment `index_futures` — FOUNDATION BUILT 2026-08-01, SEGMENT OFF.**
      **ALL TWELVE BUILD STEPS DONE 2026-08-01, deployed, `index_futures_enabled=False`.**
      Step 13 — owner + Fable review before the flag flips — is the ONLY thing left, and it
      is deliberately not mine to do.
      Step 12's proof runs with the flag **ON**: open → mark → exit, with the ledger
      invariant asserted at every stage, across profit, loss, SHORT and force-flat round
      trips. That is the test that catches what no unit test can — a segment whose parts are
      each correct and which together lose a rupee.
      **Two real defects the build surfaced, both about defaults rather than logic:**
      `index_futures_max_margin` defaulted to ₹25,000 when one NIFTY lot blocks ~₹216,000 —
      enabled, the segment would have silently never traded and looked BROKEN rather than
      off. And the same arithmetic says plainly that **a ₹50,000 account cannot trade index
      futures at all**; it is refused on affordability, which is the concrete reason this was
      always scoped as a bigger-capital feature.
      - **Step 1 — delivery-window guard (`engine/delivery_calendar.py`).** Built FIRST
        because the failure it prevents is not a losing trade: an MCX contract held through
        its compulsory tender period is an obligation to deliver physical metal. A no-op for
        cash-settled index futures, but tested against a calendar that actually bites — a
        guard only ever exercised against the always-None calendar is a guard nobody has
        tested. **Unknown means UNSAFE** (a calendar that raises or returns junk = refuse),
        and the polarity is deliberate: `True` means safe, so a caller who forgets to negate
        gets a refusal rather than an unguarded position. 9 tests.
      - **Step 2 — `BFO_FUT` charge schedule.** SENSEX futures had NO schedule, so a P&L
        computed for one would have booked the trade as free. BSE's derivatives txn charge is
        unverified against a contract note, so it is set equal to NSE's — the model must never
        UNDER-charge, since an optimistic cost model flatters everything built on it, and a
        test pins `BFO >= NFO`.
      - **Step 3 — futures LTP seam.** `get_futures_ltp` on the provider interface, concrete
        and returning `None` (not abstract — an earlier cut made it abstract by accident and
        broke provider construction everywhere, nine tests at once; there is now a test
        pinning that a new optional seam cannot do that). `None` means "I cannot price a
        future", so the caller refuses; falling back to spot would be the mis-pricing wearing
        a working provider's clothes. The mock's synthetic basis DECAYS to zero at expiry,
        because convergence at settlement is the one property a test must rely on.
      - **Steps 5 + 11 — broker open/close, ledger paisa-exact.** A near-copy of the equity
        pair rather than a shared generic, so the live equity path is never one refactor away
        from a futures change. **Margin is REQUIRED with no fallback** — SPAN is
        portfolio-scanned and instrument-specific, so a guessed figure would be a fabricated
        number sitting in the ledger. The invariant is asserted before open, after open,
        after a mark and after close; and separately, that only the MARGIN leaves cash —
        ₹1.2 crore of notional against ₹25k of margin would take the account deeply negative
        on the first contract if it leaked.
      - **Step 6 — margin-based P&L.** `MARGIN_SEGMENTS` is a named set, not a repeated
        literal: one method calling futures margined while the other called them fully paid
        would inflate equity by the notional on every tick. Half that test file proves the
        options and equity paths did not move.
      - **Step 4 — config knobs, every one inert.** Concurrency starts at **1**: a new
        leveraged segment earns its width, and inheriting 4 from the equity segment would not
        be a decision. `index_futures_margin_pct` is a flagged paper-only SPAN estimate; live
        sizing must use a broker `order_margins()` quote.
      **Step 13 (owner + Fable review) still gates the flag ever flipping true.** The build
      landing does not change that.
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

## Workstream D — UI

- [x] **System health panel — DONE 2026-08-01.** The backend has reported DB reachability,
      both loop heartbeat ages, provider auth and candle-feed anomalies since the readiness
      probe landed, and **none of it was visible in the app** — answering "is it working right
      now?" meant ssh + curl. `components/SystemHealth.tsx` + `lib/health.ts` (pure, 14 tests)
      put it on the Engine view.
      Three judgement calls, all pinned by test because they are the parts that can mislead:
      a lane that has NEVER beaten renders "never", not "0s" (which would read as "just now" —
      the exact inversion); an unreadable probe renders **Unknown**, never the last good
      verdict, because a stale green badge is worse than an honest question mark; and a stale
      lane is red only when it is the lane that matters for money (risk = stops not firing),
      amber otherwise. It polls on its own timer rather than riding the WS state — a health
      panel that only updates while the engine is well tells you nothing on the day it matters.

### Typography & palette



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
- [x] **Timezone audit — DONE 2026-08-01.** Measured, not assumed: the production droplet
      is set to **IST**, while DigitalOcean droplets default to **UTC**. So a rebuild,
      restore or replacement of that box would come up 5.5 hours off and nothing in the
      codebase would notice — correctness rested partly on a machine setting.
      The core is genuinely host-independent (`market_hours` uses an explicit `+05:30`
      tzinfo, `now_ist()` is tz-aware, `ist_epoch` localises naive candle stamps as IST) and
      `tests/test_timezone_independence.py` now runs that logic under `TZ=UTC`,
      `Asia/Kolkata` and `America/New_York` to keep it that way.
      **One real hazard found and fixed:** `broker.mark()` stamped `last_mark_time` from the
      provider's IST clock but FELL BACK to naive host-local. On a UTC host those differ by
      19,800s, and the mark-staleness guard compares them — a just-taken mark would read as
      stale, and `is_stale` suppresses SL/TP. A stop silently not firing on real money,
      triggered by nothing more than rebuilding the droplet. The fallback is now IST.
- [x] **Replay mode — DONE 2026-08-01.** `app/providers/replay.py` +
      `PT_PROVIDER=replay`. Re-runs a recorded session bar by bar against the real engine:
      when the bot does something surprising on a live day, the only honest way to understand
      it is to feed it that day again, identically, as many times as needed — and a mock
      market cannot reproduce a real Monday.
      **The property the whole thing rests on is NO LOOK-AHEAD:** `get_candles` returns
      history up to and including the cursor and not one bar further. A replay that leaked
      future bars would make the engine appear to make decisions it could never have made
      live, and would look like a perfectly successful replay while doing it. `now()` returns
      the RECORDED bar's timestamp, so market hours, the square-off deadline and every
      staleness check behave as they did on the day.
      **It structurally cannot trade:** `is_authenticated()` is always False, and
      `make_broker()` refuses a real `LiveBroker` without an authenticated kite provider. It
      also refuses to price futures rather than inventing a basis — fabricated data in a tool
      whose entire purpose is fidelity would defeat the point.
      Format is deliberately boring JSON so a day can be captured from a Kite dump, a CSV
      export or a hand-written regression case without a schema migration. 13 tests.
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
