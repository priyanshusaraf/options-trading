# Task 3 brief: immutable structural admission and refusal codes

Implement Task 3 from `paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against starting commit `0afe4b1`.

Read the accepted design, full plan, progress ledger, and this brief completely. Preserve the four inherited protected files and approved hashes.

Risk classification: **Critical**. Structural admission decides whether a strategy with a specific owner, graph, implementation closure, provenance, mapping, history, and risk model may continue toward parity, backtest, shadow, paper, or deployment. An incomplete or forgeable receipt can admit the wrong executable strategy.

Required outcome:

- Add the complete stable `AdmissionRefusalCode` enum from the accepted design.
- Add immutable canonical input, evidence, structural, parity, and artifact types with sorted JSON-compatible `to_dict()` output.
- Keep structural admission separate from final parity admission. Structural evidence has no admission address; Task 4 remains the only normal constructor of final admitted artifacts.
- Validate IR and resolution through the one `PlatformRegistry`; freshly re-derive every implementation address and fail closed on stale or missing registrations.
- Require exact component input-socket declarations, pure completed-bar contracts, nonnegative delay, valid history, canonical output mapping and risk, and owner scope.
- Derive nested input provenance from graph wiring and boundaries. Callers cannot assert or override provenance.
- Hash owner identity into private admission artifacts.
- Structurally verify handwritten adapters and record their exact implementation identity plus equivalent IR evidence; never defer class resolution by strategy key.
- Keep Component IR format version 1.

Research consultation:

- Blocked capability: immutable owner-bound structural admission receipts over complete evidence.
- Current files: `app/strategy/admission.py`, `app/ir/resolve.py`, `app/strategy/ir_adapter.py`, and `tests/test_strategy_admission.py`.
- Reviewed sources: DVC Data review and Task 2 hashfile modules; OpenFGA review and the versioned model/check command modules named there.
- Adopted patterns: immutable content identity distinct from mutable names; exact version/model binding; validation before activation; incomplete input is a hard refusal.
- Rejected patterns: DVC workspace or object-store runtime, OpenFGA service or policy language, treating authorization as strategy safety, copying code, or adding dependencies.
- Reuse: reference-only, Apache-2.0; no source reuse planned.
- Smallest native change: canonical Strategy OS dataclasses and enums, structural inspection, derived provenance, and an explicit final-artifact constructor consuming Task 4 parity evidence.

Concrete failure hypotheses:

1. Missing or stale registration or causal contract is admitted.
2. Missing or extra node socket, or context masquerading as a socket, is admitted.
3. Nested graph provenance is caller-supplied, lost, cyclic, or bound to an undeclared root.
4. Same private evidence under different owners yields the same receipt address.
5. Impure, forming, future-delay, invalid-history, bad mapping, or bad risk reaches a structural receipt.
6. Final artifact accepts unequal parity decision addresses or exception text enters hashed bytes.
7. A handwritten key/version later resolves a different class without changing evidence.

Workflow:

1. Write the plan's behavioral tests first and capture the missing-module RED.
2. Implement in small affected-test cycles; do not add a broad refusal matrix beyond the concrete hypotheses.
3. Run `tests/test_strategy_admission.py` during development. At freeze run only the plan's Task 3 subsystem command, changed-file compilation, `git diff --check`, protected hashes, and staged check.
4. Write `task-3-report.md`, update the ledger, and stop uncommitted and unstaged for independent review.

Never edit or stage the four protected inherited files.
