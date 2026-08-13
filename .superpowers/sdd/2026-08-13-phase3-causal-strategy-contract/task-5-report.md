# Phase 3 Task 5 implementation report

## Outcome

Task 5 adds mechanical `Composition` to Component IR v1 lowering. It uses the app-owned `REGISTRY`, defaults to the logical `SELF` role, preserves canonical clause/block order and exact bindings, and emits the four canonical outputs. It refuses empty or malformed clauses, unknown blocks, missing block registrations, and missing boolean logic registrations.

Generated research now creates `Composition → graph → causal admission → IRGraphStrategy`. Durable descriptors bind composition bytes, graph bytes/content address, and owner-scoped admission address. The worker reconstructs and checks the mechanical graph and receipt before provider data I/O. Emitted Python remains review text and legacy comparison material; `load.build_strategy` is documented as legacy comparison-only.

This remains causal admission only. It does not bind a physical instrument or provider symbol, claim point-in-time market truth, numeric validity, capability compatibility, resource planning, or complete Strategy Preflight. The separate Gen2 owner-scoped graph-worker authority remains Task 8 work.

## Critical failure hypotheses and evidence

- **H1 deterministic identity:** observed RED was `ModuleNotFoundError: research.strategy.builder.composition_ir`; deterministic lowering now passes.
- **H2 semantic parity:** lowered `IRGraphStrategy` canonical decisions equal the legacy Composition evaluator on a non-flat fixture.
- **H3 binding/input preservation:** mixed Composition checks canonical OHLCV input union, multi-parameter bindings, order, and forged wrong-arity refusal.
- **H4 closed vocabulary:** empty clause, unsupported block, missing each logic registration, and missing known block registration refuse before graph publication.
- **H5 authority:** generation imports app `REGISTRY`, does not import/call `build_strategy`, records graph/admission provenance, and forged durable graph or receipt cases refuse before provider access.
- **H6 no private component authority:** no research-local component library is constructed for generated lowering.

## Verification state

- `./.venv/bin/pytest -q research_tests/test_composition_ir.py`: **10 passed**.
- `./.venv/bin/pytest -vv -x research_tests/test_builder_generate.py::test_generated_work_does_not_execute_legacy_build_strategy`: **1 passed in 27.59s**. This is the one-composition integration proof that generation executes admitted IR without calling the legacy Python builder.
- Independent Critical review reran the 10 lowering tests and the authority-bearing generator cases: legacy `build_strategy` bypass, forged graph/admission refusal before provider I/O, durable descriptor round-trip, and operation descriptor-schema validation. All completed cleanly. The reviewer returned **SPEC PASS / QUALITY PASS** with no remaining Critical finding.
- The broad generator matrix was not used as an acceptance target. Every generated graph performs completed-prefix causal admission, so repeated full-matrix runs are expensive without protecting a distinct Task 5 failure hypothesis. Task 12 owns the Phase 3 broad boundary.
- `./.venv/bin/python -m py_compile research/strategy/builder/composition_ir.py research/orchestrator/generate.py research/domain/operations.py research/strategy/builder/load.py`: **PASS**.
- `git diff --check`: **PASS**.
- Protected inherited file hashes match the approved baseline.
- Staged files: none.

No broad backend, migration, or Phase 3 closure suite was run; Task 12 owns those phase-level boundaries.
