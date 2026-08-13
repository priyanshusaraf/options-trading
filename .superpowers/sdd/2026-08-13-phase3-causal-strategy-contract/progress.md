paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md

# Phase 3 causal strategy contract execution ledger

- Starting commit: `5b8ae1d`
- Protected inherited files: `app/engine/kite_venue.py`, `app/engine/venue.py`, `app/providers/brokers.py`, `tests/test_broker_registry.py`
- Review rule: each task requires observed RED, focused GREEN, independent specification and quality review, protected-file hash check, and a scoped commit.
- Research rule: substantial slices consult at most three relevant read-only repository reviews, then the exact named upstream modules, and record the fit without importing research repositories.
- Verification rule: classify each task as Critical, Important, Routine, or Trivial before implementation. Add tests only for a concrete failure hypothesis, run affected tests during implementation, subsystem suites at commit boundaries, and broad suites at phase/release boundaries. After two failed test/fix loops outside a Critical area, reassess whether the test protects a real requirement. Preserve maximum rigor for money, tenant isolation, irreversible state, authentication, and backtest-to-live strategy parity.

## Compact research provenance

| Slice | Blocked capability | Sources inspected | Adopted pattern | Reuse | Decision |
| --- | --- | --- | --- | --- | --- |
| Task 1 causal declarations | Exact recursive per-bar state and closed construction-time validation | XState review plus `createMachine.ts`, `StateMachine.ts`, `StateNode.ts`, `transition.ts`; Dagster review plus `graph_definition.py`, `dependency.py`, `composition.py`, `definitions_class.py`, `assets/graph/asset_graph.py` | Pure `(state, event) -> (next state, outputs/actions)` transitions; definitions stay separate from invocation; reject incomplete or conflicting dependency declarations before execution | Reference-only; XState MIT, Dagster Apache-2.0; no copied code or dependency | Keep Component IR v1 and implement native immutable recursive contracts. Do not replace the registry, add an actor runtime, or treat a DAG framework as strategy authority. |

| Task | Status | Commit | Evidence |
| --- | --- | --- | --- |
| 1. Closed bounded and recursive causal declarations | completed | pending scoped commit | **Critical:** independent final review SPEC PASS / QUALITY PASS. Exact reproduced parity RED/GREEN recorded in `task-1-report.md`; 253 passed, 6 skipped inventory; compile/diff/protected hashes green. Task 2 watchpoint: identity closure must derive or reject module globals rather than trust manual dependency tuples. |
| 2. Immutable production registrations and transitive identity | pending | — | — |
| 3. Immutable admission artefact and refusal codes | pending | — | — |
| 4. Independent prefix reference, parity, and mutations | pending | — | — |
| 5. Mechanical Composition-to-IR lowering | pending | — | — |
| 6. Execution-plane persistence and migration 0034 | pending | — | — |
| 7. Research-plane persistence and migration 0005 | pending | — | — |
| 8. Editor publication and research enforcement | pending | — | — |
| 9. Backtest admission, cache identity, and next-bar execution | pending | — | — |
| 10. Promotion, shadow, paper, and deployment authority | pending | — | — |
| 11. Execution attribution and legacy quarantine | pending | — | — |
| 12. Mutation gate and Phase 3 closure | pending | — | — |
