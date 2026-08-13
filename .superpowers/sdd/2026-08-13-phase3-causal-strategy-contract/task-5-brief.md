# Task 5 brief: mechanical Composition-to-IR lowering

Implement Task 5 from
`paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against
starting commit `e69d9c1`.

Read the accepted Phase 3 design, full plan, progress ledger, V1 product-steer reconciliation, and
this brief completely. Preserve the four inherited protected files and their approved hashes.

Risk classification: **Critical**. A lowering defect can make the strategy researched or reviewed
different from the strategy backtested or later executed.

Required outcome:

- Lower every supported `Composition` mechanically into Component IR v1 through app-owned
  `REGISTRY` components only.
- Use `SELF` as the default logical instrument role. Do not resolve a physical instrument, broker
  symbol, or provider token in this task.
- Preserve deterministic clause and block ordering, parameter bindings, four canonical outputs,
  and the non-empty-clause invariant.
- Use registered `logic.and` and `logic.or`; do not synthesize local component definitions.
- Make graph bytes/content address/admission address the authority carried by search and generation.
  Generated Python remains review text and legacy comparison only.
- Retire new authority paths through `build_strategy`; Task 10 owns final downstream removal and
  legacy quarantine.
- Keep Component IR format version 1. Do not add deployment bindings, provider capability,
  point-in-time instruments, numeric validity, or resource preflight.

Concrete failure hypotheses:

1. The same semantic composition lowers to different canonical graph bytes or node IDs.
2. Lowered IR produces different canonical decisions from the existing Composition evaluator.
3. Parameter overrides, input union, or clause order are dropped or rebound.
4. Empty clauses or missing `logic.and`/`logic.or` registrations are accepted through a fallback.
5. Research search/generation still treats emitted Python or `build_strategy` as new-exposure
   authority instead of graph plus causal admission.
6. A research-local component library or physical instrument symbol bypasses app-owned registry
   and `SELF` role semantics.

Verification workflow:

1. Observe the missing-module RED first.
2. Add no test without naming one hypothesis above.
3. Run affected lowering/builder tests during implementation, the Task 5 subsystem suite at freeze,
   then compilation, diff, staged, and protected-hash checks.
4. Do not run broad backend, migration, or Phase 3 closure suites; Task 12 owns them.
5. Write `task-5-report.md`, update the ledger, and stop uncommitted/unstaged for independent
   review.
