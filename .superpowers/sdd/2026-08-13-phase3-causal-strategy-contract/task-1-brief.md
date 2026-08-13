# Task 1 brief: closed bounded and recursive causal declarations

Implement Task 1 from `paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against starting commit `5b8ae1d`.

The accepted design is `paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md`. It is authoritative. Read both documents completely before editing.

Required outcome:

- Add closed immutable bounded-history and causal-recursive declarations.
- Distinguish exact node input sockets from context inputs; `bar_timestamp` must come from the completed prefix index through an explicit context channel.
- Require a complete recursive initializer, canonical state type/encoder, update, and step contract.
- Add an exhaustive typed disposition manifest for every current builder block. Each block is admitted with truthful bounded or recursive semantics, or explicitly quarantined with a stable reason.
- Keep EMA, z-score wrappers that depend on EMA, Wilder ATR, RSI smoothing, session opening range, and causal expanding-median regime logic honest. Do not label recursive implementations bounded.
- Preserve IR format version 1.
- Do not add the production registry/contributor bridge from Task 2 prematurely except for minimal type seams that Task 1 explicitly requires.

Risk classification: **Critical**. A false causal or recursive declaration can make backtest results diverge from streaming, paper, and live execution. Verification should target concrete parity, hidden-dependency, timestamp, and state-corruption hypotheses. Test count and exotic combinations are not objectives by themselves.

Research consultation for this slice:

- Blocked capability: exact causal-recursive kernel declarations and executable per-bar state transitions.
- Current contracts/files: `app/ir/causal.py`, `app/ir/kernels.py`, `app/ir/runtime.py`, `app/ir/contributors/generated_blocks.py`, `research/strategy/builder/blocks.py`, and `research/regime.py`.
- Reviewed read-only sources: XState's `createMachine.ts`, `StateMachine.ts`, `StateNode.ts`, and `transition.ts`; Dagster's `graph_definition.py`, `dependency.py`, `composition.py`, `definitions_class.py`, and `assets/graph/asset_graph.py`.
- Adopted patterns: pure deterministic state transition functions; persisted state bound to an explicit implementation contract; construction-time rejection of missing, conflicting, or unmapped dependencies.
- Rejected patterns: replacing Component IR with XState actors or Dagster graphs, adding either dependency, copying upstream implementations, decorator DSL authority, and arbitrary effectful state machines.
- Reuse classification: reference-only. XState is MIT and Dagster is Apache-2.0; no source reuse is planned.
- Smallest native change: preserve IR v1, add exact immutable state contracts and app-owned recursive state machines, and keep the exhaustive disposition manifest fail-closed.
- Proof: observed RED for each recursive family, exact state type and closed-JSON encoder checks, deterministic transition tests, recorded-timestamp-only session resets, completed-prefix vector agreement, future-mutation resistance, and quarantine exclusion from registration/lowering/admission.

Workflow and evidence:

1. Write behavioral tests first and run them to capture the expected RED.
2. Implement the narrow Task 1 contract.
3. Run the focused commands named in Task 1 plus existing builder reachability/authoring regressions.
4. Run `git diff --check`, compile changed Python, and verify protected hashes.
5. Write `task-1-report.md` here with exact RED and GREEN evidence, deviations, and remaining Task 2 dependencies.
6. Stop uncommitted and unstaged for independent review.

Never edit or stage the four protected inherited files.
