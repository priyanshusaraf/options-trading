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
| Task 2 implementation identity | Immutable callable identity that changes when any accepted helper, state transition, module, or dependency changes | DVC Data review plus `hashfile/obj.py`, `hashfile/db/__init__.py`, `hashfile/cache.py`, `hashfile/status.py`, `hashfile/transfer.py`; Dagster review plus the Task 1 graph/definition modules | Separate logical names from immutable content identity; keep caches as accelerators rather than authority; keep definitions, invocation, and validation distinct; reject incomplete dependency closure | Reference-only; DVC Data and Dagster are Apache-2.0; no copied code or dependency | Derive a native semantic implementation address from callable/state/dependency closure. A body ref or source-file digest alone is insufficient, and manual dependency tuples are inputs to validation rather than trusted truth. |

| Task | Status | Commit | Evidence |
| --- | --- | --- | --- |
| 1. Closed bounded and recursive causal declarations | completed | `ba6ed7c` | **Critical:** independent final review SPEC PASS / QUALITY PASS. Exact reproduced parity RED/GREEN recorded in `task-1-report.md`; 253 passed, 6 skipped inventory; compile/diff/protected hashes green. Task 2 watchpoint: identity closure must derive or reject module globals rather than trust manual dependency tuples. |
| 2. Immutable production registrations and transitive identity | completed | pending scoped commit | **Critical:** independent final review SPEC PASS / QUALITY PASS. Behavioral missing-module RED, class-method-helper RED/GREEN, focused identity GREEN, and 110-test Task 2 subsystem GREEN recorded in `task-2-report.md`. Single 39-record platform registry, deep immutable views, exact dependency/body closure, logic kernels, all generated blocks, complete expanding-z registrations, and real `_rma` stale-address proof. Compile/diff/protected hashes green. |
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
