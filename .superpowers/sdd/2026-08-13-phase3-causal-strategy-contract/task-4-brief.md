# Task 4 brief: independent prefix parity and adversarial causal gate

Implement Task 4 from `paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against starting commit `e04ffc6`.

Read the accepted design, full plan, progress ledger, and this brief completely. Preserve the four inherited protected files and approved hashes.

Risk classification: **Critical**. This is the proof boundary between whole-frame research/backtest evaluation and completed-bar streaming semantics. A false pass can make a strategy look valid in research while trading different signals live.

V1 steer reconciliation:

- Keep this task on the causal parity boundary. Do not pull point-in-time market rules, provider
  capabilities, named deployment roles, dynamic derivatives, subscription planning, or resource
  preflight into Task 4.
- Treat `CausalFixtureSuite` as the causal lane of the future shared node conformance harness, not
  proof of the eventual first-party catalogue.
- Preserve exact missing-value behavior between the two current evaluators, but do not claim scalar
  `NaN` implements the later closed numeric-validity states.
- `admit_strategy` produces causal admission only. It cannot by itself authorise paper/live
  activation or satisfy complete Strategy Preflight.
- Add no tests merely to mirror the steer documents. The nine concrete causal failure hypotheses
  below remain the bounded verification scope.

Required outcome:

- Implement an independent reference evaluator that does not import or call the vector runtime, its cache, or its private wiring helpers.
- For bounded kernels, evaluate only the declared completed prefix. For recursive kernels, use the registered initializer, state encoder, update, and step exactly once per completed bar.
- Require one shared timezone-aware, monotonic, unique recorded index and transport only the declared current `bar_timestamp` context.
- Compare recursive node streams before graph decisions so downstream logic cannot hide divergence.
- Add one immutable app-owned fixture suite and load it internally; callers cannot supply a fixture suite or bypass parity.
- Implement final `admit_strategy` and `verify_admission` by recomputing structural identity and parity, then comparing exact owner-bound admission addresses.
- Add the bounded mutation command: one stale registered helper plus five freshly identified future-reading kernels. Every mutant must die for the correct identity or parity reason.
- Prove the shipped admitted block manifest against the independent evaluator. Quarantined blocks must remain unavailable.
- Handwritten `expanding_z_v4` may be admitted only after exact adapter-versus-equivalent-IR decision parity, and new exposure returns `IRGraphStrategy`.
- Keep Component IR format version 1. Do not add persistence or downstream authority wiring; later tasks own those boundaries.

Research consultation:

- Blocked capability: independent detection of whole-frame lookahead and deterministic recursive transitions.
- Current files: `app/ir/runtime.py`, `app/ir/streaming_reference.py`, `app/strategy/causal_fixtures.py`, `app/strategy/admission.py`, the generated block manifest, and the Task 4 tests/script.
- Reviewed sources: Strategy OS reuse-intelligence audit; VectorBT review and `vectorbt/indicators/factory.py`; XState review and `packages/core/src/transition.ts`.
- Adopted patterns: named input/parameter/output separation; compare an optimized whole-array path against a separate oracle; pure deterministic `(state,event)->next state/output` transitions; side-effect-free reference evaluation.
- Rejected patterns: VectorBT runtime classes, in-place public outputs, parameter grids inside component execution, XState as the IR/runtime, external dependencies, or source copying.
- Reuse: reference-only. VectorBT is Apache-2.0 plus Commons Clause and must never be a dependency; XState is MIT but no code is needed. No source reuse is planned.

Concrete failure hypotheses:

1. The reference evaluator calls or shares private logic/cache with the vector runtime, so the same defect passes twice.
2. A bounded node sees rows after the current completed bar, or recursive state updates more than once per bar.
3. Missing, duplicated, non-monotonic, timezone-ambiguous, or mismatched input indexes are accepted.
4. A recursive node diverges but downstream boolean logic masks it.
5. Fixture suite selection or parity evidence is caller-controlled, mutable, stale, or excluded from the receipt.
6. Fresh negative-shift, centered-window, backfill, future-join, or global-normalization kernels survive admission.
7. A post-registration helper mutation reaches parity instead of failing implementation freshness.
8. Admitted block manifest entries, including RSI choices/session reset/regime state, diverge between vector and step semantics.
9. Handwritten adapter bytes differ from equivalent IR while still producing an admitted artifact or handwritten runtime authority.

Risk-weighted workflow:

1. Write the plan's missing-module/independence RED first.
2. Implement in small affected-test cycles. Add no test without naming which hypothesis above it protects.
3. During development run the exact affected node or file. At freeze run only the Task 4 parity subsystem command, mutation command, changed-file compilation, `git diff --check`, protected hashes, and staged check.
4. Do not run the full backend or historical migration suites; Task 12/Phase 3 closure owns broad verification.
5. Write `task-4-report.md`, update the ledger, and stop uncommitted and unstaged for independent review.

Never edit or stage the four protected inherited files.
