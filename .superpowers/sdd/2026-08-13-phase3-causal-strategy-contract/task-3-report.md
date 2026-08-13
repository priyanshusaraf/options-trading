# Phase 3 Task 3 implementation report

## Outcome

Task 3 now provides fail-closed structural admission without performing parity evaluation.
`app.strategy.admission` defines the complete stable refusal vocabulary; deeply immutable,
canonical evidence and receipt types; owner-bound artifact addressing; deterministic canonical
decision bytes; structural graph and handwritten-adapter inspection; and the explicit
`admitted_artifact(structural, parity)` hand-off owned by Task 4.

Structural inspection validates the root IR and every reached nested graph body, resolves only
through `PlatformRegistry`, freshly derives implementation identities, checks exact component,
contract, and runtime sockets, derives nested root provenance, validates history, mapping, risk,
purity, completed-bar timing, and delay, and refuses stale or incomplete evidence before parity.
Resolution now retains every reached component path and body reference, including graph-bodied and
default-source components, so changing nested bytes changes structural evidence even when the leaf
execution topology remains the same. Component IR remains format version 1.

## TDD evidence

The required initial RED was observed before production code existed:

```text
.venv/bin/pytest -q tests/test_strategy_admission.py
ModuleNotFoundError: No module named 'app.strategy.admission'
```

Subsequent focused RED/GREEN cycles covered these concrete failure hypotheses:

- missing causal contracts, missing/extra sockets, and exact stale registrations refuse;
- nested provenance is derived through graph boundaries, while wired scalar kernels retain an
  explicit zero-root source path;
- reached nested bodies must validate and must match their published interface;
- reached nested component body references enter structural evidence;
- owner identity changes the final receipt address and nested canonical mappings are immutable;
- direct final-artifact construction cannot bypass parity-address equality;
- canonical decisions normalize timestamps to UTC nanoseconds and use fixed boolean-column order;
- a handwritten adapter cannot claim a different key/version, while a valid adapter records its
  exact executable identity and equivalent graph;
- a self-referential graph component was reproduced ending in uncaught `RecursionError`; the
  resolver now detects an active body-reference cycle and raises typed `ResolutionError`, which
  structural admission maps to `RESOLUTION_FAILED`.

Final focused admission GREEN:

```text
.venv/bin/pytest -q tests/test_strategy_admission.py
16 passed
```

Exact Task 3 subsystem freeze:

```text
.venv/bin/pytest -q tests/test_strategy_admission.py tests/test_ir_adapter.py tests/test_ir_runtime.py
75 passed
```

The existing adapter failure-injection test was updated to the already-required three-argument
vector-kernel signature. No production adapter behavior changed.

## Freeze checks

- Changed Python compilation with `.venv/bin/python -m py_compile`: PASS.
- `git diff --check`: PASS.
- Staged files: none.
- Protected inherited hashes match the approved baseline:
  - `app/engine/kite_venue.py`: `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
  - `app/engine/venue.py`: `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
  - `app/providers/brokers.py`: `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
  - `tests/test_broker_registry.py`: `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`

## Scope and next boundary

No prefix/reference evaluator, fixture registry, parity-running admission service, verification
service, persistence, or authority wiring was implemented. Task 4 owns those behaviors. The work
is intentionally uncommitted and unstaged for independent specification and quality review.

The DVC Data and OpenFGA research remained reference-only. No code, dependency, service, policy
language, or repository content was copied or introduced.

Independent final review: **SPEC PASS / QUALITY PASS**. The reviewer reproduced the recursion
bypass before the fix and verified the typed refusal afterward.
