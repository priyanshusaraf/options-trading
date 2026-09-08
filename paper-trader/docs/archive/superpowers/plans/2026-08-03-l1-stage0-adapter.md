# L1 Stage 0 — production-grade IR strategy adapter (implementation plan)

**Status: COMPLETE, 2026-08-03.** Approved for Stage 0 only. The live engine remains the
sole execution authority: nothing binds a graph to an instrument, and no order, paper, shadow
or live path consumes the adapter.

**Goal:** make an IR graph safely bindable as a `Strategy` and rebuild the parity claim honestly.
**No live behaviour changes in this stage** — nothing binds an IR graph to an instrument.

**Boundary:** adapter, identity, warmup, `risk_model`, caching and parity evidence only. No
shadow lane (Stage 1), no paper adoption (Stage 2), no live adoption (Stage 3), no change to
order routing, sizing, exits or the ledger.

---

## Task 1: Move the adapter to the shared side of the isolation boundary

1. Failing test first: an `app.`-side import of the adapter, asserting `research.guards`
   `FORBIDDEN_MODULES` is not violated in either direction.
2. **Placed at `app/strategy/ir_adapter.py`, not `app/ir/`** — corrected during
   implementation. `app/ir/strategies/expanding_z.py` already imports
   `app.strategy.registry` (its kernels delegate to the hand-written implementation so the
   planes cannot drift), so putting the adapter inside `app.ir` would deepen that tangle.
   The language core `app/ir/*.py` imports neither `app.strategy`, `research` nor
   `app.engine`, and an AST-based test now enforces exactly that.
   Research **subclasses** the shared adapter rather than duplicating it.
3. Prove the research plane still passes `research_tests/test_ir_evaluate.py` unchanged.
4. Prove no `app/engine/*` module imports `research.*` as a result.

## Task 2: Warmup must be loud, never silently all-False

1. Failing test: a frame shorter than the resolved warmup (302 bars) must raise or emit a
   distinguishable log — not return four all-False columns.
2. Failing test: the live admission guard (`runner.py:444`, ~55 bars) must not admit a frame the
   bound graph cannot serve. Pin the interaction explicitly.
3. Implement, then mutate the guard away and prove both tests go red.

## Task 3: Carry `risk_model` so the ATR ratchet survives

1. Failing test: an IR strategy declaring a risk model exposes `risk_model` with the seven
   required keys (`base.py:33-36`), and the runner's ratchet path activates for it.
2. Failing test: the ratchet **cannot** be silently absent — suppress the carry and prove red.
3. Decide and record where the declaration lives on the graph, so it is part of content identity
   rather than a wrapper-side afterthought.

## Task 4: One warmup-trim rule for live and backtest

1. Failing test: for one graph and one frame, live and backtest agree on the trimmed bar set.
2. Fix `compute_signals`' `warm_cols` dependence on indicator columns the adapter does not emit
   (`backtest/engine.py:218`, `premium.py:214`) — either emit them or trim on declared warmup.
3. Mutate the rule and prove the parity test fails. This closes a **latent hard-invariant-4
   violation** and is the highest-value item in the stage.

## Task 5: Stable identity, no silent v3 fallback

1. Failing test: an unregistered or drifted `ir.*` key **refuses or alarms** rather than being
   coerced to the default (`runner.py:362`, `universe_resolver.py:95-96`).
2. Adopt the generated-strategy identity scheme — stable `key`, versioned content
   (`generated_strategies.py:36-46`) — so editing a graph does not orphan every persisted
   `InstrumentState.strategy_key`.
3. Failing test: editing a graph keeps existing bindings resolvable, with the version changing.

## Task 6: Cost inside the signal-loop budget — **task withdrawn as wrong**

The instruction to "pass a persistent `Cache`" was a defect in this plan and in ADR 0011 §3
conflict #7. `Cache` is keyed on `node.cache_id`, fixed at resolution and carrying nothing
about the input data, so a cache reused across frames returns the previous frame's series —
measured: every one of 18 nodes a hit, every value stale. Implementing it would have produced
silently wrong live signals.

A fresh cache per evaluation is therefore correct, and memoisation still works within one
evaluation. The hazard is pinned by a guard test so it cannot be "optimised" back in.
Per-scan cost measurement moves to Stage 1, where there is a live lane to measure against.

## Task 7: Rebuild the parity claim honestly

1. Parity **through `IRGraphStrategy`**, not `evaluate()` — the adapter's warmup masking, NaN
   coercion and frame contract must be inside the claim.
2. On **real recorded candles**, multiple instruments, more than one interval.
3. Across a parameter sweep — at minimum every length parameter that changes warmup, not the two
   currently moved.
4. Including gaps, holidays, session boundaries and short frames.
5. `Strategy`-interface conformance: `signals()` enforcement, `key`/`version`/`risk_model`,
   registry discovery.
6. Correct the parity module's docstring claim of "real candle data" once it is true.

## Task 8: Verify, document, publish

1. Run the eight ADR 0011 §7 proofs that apply to this stage, each proven red then restored.
2. Full backend/research suite, frontend suite, typecheck, build, both deterministic smokes.
3. Update ADR 0011 status, the three coordination documents and WS-01/WS-02.
4. Commit deliberately, push, verify remote equality, inspect exact-head CI.
5. **Stop.** Stage 1 (shadow lane) is a separate slice with its own design review.
