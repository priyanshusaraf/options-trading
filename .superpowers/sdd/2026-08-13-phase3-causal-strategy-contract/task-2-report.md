# Phase 3 Task 2 implementation report

## Outcome

Task 2 now binds each executable Component IR kernel to one immutable
`KernelRegistration`. `app.ir.library.REGISTRY` is the single platform authority; its
`LIBRARY` and `IMPLEMENTATIONS` names are read-only views derived from the same records.
Component IR remains format version 1.

The implementation identity uses canonical JSON plus SHA-256 over source, defaults,
annotations, closures, bytecode-derived globals, exact declared dependencies, recursive state
functions/types/encoder, and either declared-object closure or complete defining-module bytes.
It rejects missing or extra declarations, unsupported closure values, runtime imports, dynamic
global lookup, and dynamic module attribute lookup. No `repr`, module-name-only, or unknown
fallback exists.

The production registry contains the complete expanding-z contributor, every admitted generated
block, and `logic.and` / `logic.or`. Platform construction rejects stale or forged registration
addresses, split specs/callables, missing or extra registrations, missing/orphan/forged graph
bodies, and nested mutation of component bytes.

## TDD evidence

Initial RED, before production changes:

```text
.venv/bin/pytest -q tests/test_ir_implementation_identity.py
ModuleNotFoundError: No module named 'app.ir.implementation_identity'
```

Focused GREEN after the first identity/registration cycle:

```text
.venv/bin/pytest -q tests/test_ir_implementation_identity.py
4 passed
```

Subsequent behavioral REDs and fixes covered:

- Python 3.13 `inspect.getclosurevars` reported `LOAD_ATTR fabs` as an unbound global. The
  detector now intersects unbound names with actual `LOAD_GLOBAL`/`LOAD_NAME` bytecode reads.
- A module captured as a nonlocal could use dynamic `getattr(module, params[...])`. The detector
  now rejects nonliteral module lookup for both global and nonlocal module bindings.
- A public `KernelRegistration` constructor could carry a forged address. `PlatformRegistry`
  freshly derives every address and refuses stale or forged records.
- Top-level mapping proxies still allowed nested component mutation. Registry construction now
  recursively clones and freezes component and graph-body values.
- Graph body maps could omit, add, or forge bytes under an address. Registry construction now
  requires exact component/body closure and verifies each graph content address.
- `defining_module` accepted closures. It now rejects them; generated adapters use an exact
  declared-object boundary, while expanding-z wrappers use the complete defining-module boundary.
- A declared recursive state class was initially identified from class source without traversing
  the globals read by its user-defined methods. A reproduced `State.signal() -> helper()` case now
  rejects an omitted helper and changes address when the exact declared helper changes. Method
  traversal is limited to code from the class's own source file, so generated dataclass methods
  from `<string>` or `dataclasses.py` remain intrinsic rather than creating false dependencies.

The actual statically imported `expanding_z._rma` helper was replaced with a closure-free changed
implementation. A fresh exact dependency boundary derived a different implementation address,
and the old registration was rejected as stale. This test does not use a dummy helper.

Affected Task 2 subsystem GREEN:

```text
.venv/bin/pytest -q tests/test_ir_implementation_identity.py tests/test_ir_authoring.py \
  tests/test_ir_platform_library.py tests/test_ir_strategy_parity.py \
  research_tests/test_ir_block_components.py
110 passed
```

## Contributor and closure evidence

- `app.ir.library.CONTRIBUTORS` literally contains `generated_blocks` and `expanding_z`.
- The platform registry contains 39 registrations and derives both compatibility views.
- Generated-block dependency discovery reaches real `bisect`, `numpy`, `pandas`, `warnings`,
  recursive state callables/types/encoders, and the app-owned block helpers. The manual
  `BLOCK_DEPENDENCIES` table is not trusted as identity authority.
- Expanding-z wrappers import `_rma`, `zscore`, `adaptive_threshold`, `drift_score`,
  `range_in_atr`, `impulse`, `directional_entry`, `displacement_lost`, and `_as_bool` statically.
  There is no runtime strategy import or module-qualified helper dispatch.
- Both logic components declare exact `left,right` inputs, `out`, bounded-zero history,
  completed-bar input, pure execution, and zero output delay.

## Research provenance

The accepted review of DVC Data and Dagster remained reference-only. The implementation adopted
only the documented patterns: logical names are separate from immutable content identity, caches
are not authority, validation completes before publication, and incomplete dependency state is a
hard failure. No research repository was imported, copied, modified, or added as a dependency.

## Scope and deviations

No Task 3 admission behavior or later Phase 3 work was implemented. The four protected inherited
files were not edited or staged during this task. Existing worktree changes in those files were
preserved byte-for-byte. No production caller composes another platform library. `authoring.library`
remains a local test/authoring compatibility helper and is not production authority.
