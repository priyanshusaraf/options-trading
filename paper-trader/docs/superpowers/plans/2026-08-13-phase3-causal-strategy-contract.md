# Phase 3 Causal Strategy Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require one owner-scoped immutable causal admission artefact across strategy publication, research, backtest, promotion, deployment, and execution.

**Architecture:** Component IR format v1 stays unchanged. Closed causal facts and transitive implementation identities live in the kernel registry; an admission service resolves a graph, runs an independent prefix-only reference against the vectorised runtime, and emits an immutable content-addressed receipt. Every authority boundary binds and re-verifies that receipt, while exact legacy rows may be backfilled and all others remain quarantined.

**Tech Stack:** Python 3.11, pandas, SQLAlchemy 2, Alembic, FastAPI/Pydantic, pytest, SQLite, PostgreSQL/psycopg.

**Spec:** `paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md`

## Global Constraints

- Keep `app.ir.schema.SUPPORTED_FORMAT_VERSION == 1`; do not add causal fields to serialised IR.
- Production resolves and executes only through `app.ir.library.REGISTRY`; spec and callable maps are derived views of immutable registrations.
- EMA, Wilder smoothing, and RSI are causal-recursive and must pass vector-versus-initializer/update/step parity.
- Admission addresses use `sha256:<64 lowercase hex>` and include `owner_id` in canonical bytes.
- Missing, unknown, unchecked, impure, hidden-context, external-series, or stale declarations fail closed.
- A decision on completed bar `t` may first fill on bar `t+1`.
- Generated Python is diagnostic text only; `Composition` lowers mechanically to IR.
- Existing rows without exact proof remain readable but cannot gain or regain authority or open new exposure.
- Risk reduction and recovery for existing positions must not depend on successful admission.
- Do not touch `app/engine/kite_venue.py`, `app/engine/venue.py`, `app/providers/brokers.py`, or `tests/test_broker_registry.py`.
- Do not implement Phase 5 performance work, Phase 8 frontend work, Phase 9 brokers, marketplace, billing, or live-IR grant expansion.
- Every production change follows red, observed failure, minimal green, focused regression, then commit.

## File structure

- `backend/app/ir/causal.py`: closed bounded-history and recursive-state declarations.
- `backend/app/ir/implementation_identity.py`: canonical transitive callable/module identity.
- `backend/app/ir/registry.py`: immutable registration record and production registry transport.
- `backend/app/ir/contributors/generated_blocks.py`: app-owned generated block vocabulary and registrations shared with research.
- `backend/app/ir/streaming_reference.py`: independent completed-prefix and recursive-step graph evaluator.
- `backend/app/strategy/admission.py`: artefact, refusal vocabulary, admit, verify, canonical decisions.
- `backend/research/strategy/builder/composition_ir.py`: deterministic Composition-to-IR lowering.
- `backend/app/core/strategy_admissions.py`: execution-plane immutable receipt repository.
- `backend/research/domain/admissions.py`: research-plane immutable receipt repository.
- `backend/migrations/versions/20260813_0034_strategy_admissions.py`: execution schema.
- `backend/research/domain/migrations/0005_strategy_admissions.py`: research schema.
- Existing editor, research, backtest, promotion, shadow, paper, deployment, and execution files only wire these focused units.

---

### Task 1: Closed bounded and recursive causal declarations

**Files:**
- Create: `paper-trader/backend/app/ir/causal.py`
- Modify: `paper-trader/backend/app/ir/kernels.py`
- Modify: `paper-trader/backend/app/ir/authoring.py`
- Modify: `paper-trader/backend/app/ir/runtime.py`
- Create: `paper-trader/backend/app/ir/contributors/__init__.py`
- Create: `paper-trader/backend/app/ir/contributors/generated_blocks.py`
- Modify: `paper-trader/backend/app/ir/strategies/expanding_z.py`
- Modify: `paper-trader/backend/research/strategy/builder/blocks.py`
- Modify: `paper-trader/backend/research/strategy/builder/ir_components.py`
- Test: `paper-trader/backend/tests/test_ir_causal_contract.py`
- Test: `paper-trader/backend/research_tests/test_block_declared_inputs.py`

**Interfaces:**
- Produces: `BoundTerm`, `HistoryBound`, `RecursiveStateContract`, `CausalContract`, `BlockCausalDisposition`, `CausalDeclarationError`, `causal_contract(*, node_input_sockets, context_inputs, history, output_delay_bars=0, recursive_state=None)`.
- Changes: `KernelSpec.causal: CausalContract | None`; old omitted metadata is representable for discovery but inadmissible later.
- Makes the generated block definitions app-owned; research modules re-export them and do not define a second vocabulary.
- Changes the vector kernel signature to `(params, node_inputs, context_inputs)` for every kernel; no two-argument fallback remains.

- [ ] **Step 1: Write failing closed-contract tests**

```python
def test_causal_contract_rejects_future_or_hidden_dependencies():
    with pytest.raises(CausalDeclarationError, match="output_delay_bars"):
        causal_contract(node_input_sockets=("close",), history=HistoryBound("bounded"),
                        output_delay_bars=-1)
    with pytest.raises(CausalDeclarationError, match="context_inputs"):
        causal_contract(node_input_sockets=("close",), context_inputs=("wall_clock",),
                        history=HistoryBound("bounded"))

def test_parameter_history_is_exact_and_closed():
    bound = HistoryBound("bounded", constant=1,
                         terms=(BoundTerm("length"), BoundTerm("lookback"),))
    assert bound.bars({"length": 50, "lookback": 5}) == 56
    with pytest.raises(CausalDeclarationError, match="undeclared"):
        bound.bars({"length": 50})

def test_recursive_mode_requires_all_state_functions():
    with pytest.raises(CausalDeclarationError, match="recursive_state"):
        causal_contract(node_input_sockets=("close",),
                        history=HistoryBound("causal_recursive"))
```

- [ ] **Step 2: Run the new tests and observe the missing-module failure**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_causal_contract.py research_tests/test_block_declared_inputs.py`

Expected: FAIL because `app.ir.causal` and the new fields do not exist.

- [ ] **Step 3: Implement the closed values and registry seam**

```python
ALLOWED_CONTEXT_INPUTS = frozenset({"bar_timestamp"})
HISTORY_MODES = frozenset({"bounded", "causal_recursive"})

@dataclass(frozen=True)
class HistoryBound:
    mode: str
    constant: int = 0
    terms: tuple[BoundTerm, ...] = ()

    def bars(self, params: Mapping[str, Any]) -> int:
        if self.mode not in HISTORY_MODES or self.constant < 0:
            raise CausalDeclarationError("history declaration is invalid")
        total = self.constant
        for term in self.terms:
            if term.parameter not in params:
                raise CausalDeclarationError(
                    f"history parameter {term.parameter!r} is undeclared")
            value = params[term.parameter]
            if isinstance(value, bool) or int(value) != value:
                raise CausalDeclarationError("history parameters must be integers")
            total += int(value) * term.multiplier
        if total < 0 or total > MAX_HISTORY_BARS:
            raise CausalDeclarationError("evaluated history is outside the closed range")
        return total
```

Extend `KernelSpec` with `causal: CausalContract | None = None`; extend `_FIELDS` with only
`causal`. Keep `None` so legacy registry construction can be inspected; Task 3 admission rejects
it. Implement the exact initializer/state type/encoder/update/step signatures from the design. Enforce
that bounded mode has no recursive state and causal-recursive mode has all four functions.

- [ ] **Step 4: Move the builder vocabulary into the app and declare every block exactly**

Move `BlockSpec`, block functions, helper tables, and `BLOCKS` to
`app/ir/contributors/generated_blocks.py`. Research `blocks.py` re-exports those exact objects and
`ir_components.py` becomes a compatibility re-export. Add `history: HistoryBound`, retain `inputs`,
and map `needs_clock=True` to `context_inputs=("bar_timestamp",)`. For example:

```python
"roc_gt": BlockSpec(
    roc_gt,
    (("length", "length"), ("thr", "thr")),
    lambda a: int(a[0]) + 1, (10, 0.0), "momentum",
    inputs=("close",),
    history=HistoryBound("bounded", constant=1,
                         terms=(BoundTerm("length"),))),
```

EMA, Wilder smoothing, and both RSI blocks use `HistoryBound("causal_recursive", ...)` with exact
initializer, state type, JSON state encoder, update, and step functions. Rolling blocks use bounded history.
The clock-aware steps consume `context["bar_timestamp"]`; the adapter passes the current series
index and never calls a clock. Update `runtime.evaluate` to derive a timestamp context series from
the common validated input index and pass only declared context. Mechanically add the third argument
to all shipped kernels, empty when undeclared. Do not infer reads from source during admission.

Implement the complete literal disposition manifest from design §5.3. Every block has either an
`admitted(contract, dependencies)` or `quarantined(reason)` entry. EMA slope blocks retain an EMA and deque;
z-score/cross/still-expanding retain the recursive `adjust=False` EMA, exact rolling close deque,
and where required the prior z-score; ATR blocks retain Wilder state; RSI's state
supports every source/smoothing choice; opening-range state resets from recorded session date.
Port regime labelling/constants to app-owned code and implement exact expanding-median state. Remove
the runtime `from research.regime` import. If regime vector/step parity is not exact, mark it
`quarantined(...)`, keep that disposition in the exhaustive manifest, and make lowering refuse it
with `COMPONENT_QUARANTINED`; never admit a partial contract.

Add exhaustive guards and parameterized tests:

```python
assert set(CAUSAL_MANIFEST) == set(BLOCKS)
assert set(BLOCK_DEPENDENCIES) == set(BLOCKS)
admitted = {name for name, disposition in CAUSAL_MANIFEST.items()
            if disposition.status == "admitted"}
assert set(BLOCK_REGISTRATIONS) == {
    BLOCK_COMPONENTS[name].body_ref for name in admitted
}
```

Unit-test each recursive initializer/update/step transition here, including all-choice RSI,
two-session opening-range reset, and expanding-median regime state. Task 4 performs the independent
vector-versus-prefix parity proof after the reference evaluator exists.

- [ ] **Step 5: Run focused tests and the reachable-block guard**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_causal_contract.py research_tests/test_block_declared_inputs.py research_tests/test_every_block_is_reachable.py tests/test_ir_authoring.py tests/test_ir_runtime.py tests/test_ir_strategy_parity.py`

Expected: PASS; every reachable block has exact declared inputs and a contract.

- [ ] **Step 6: Commit**

```bash
git add paper-trader/backend/app/ir/causal.py paper-trader/backend/app/ir/kernels.py paper-trader/backend/app/ir/authoring.py paper-trader/backend/app/ir/runtime.py paper-trader/backend/app/ir/contributors/__init__.py paper-trader/backend/app/ir/contributors/generated_blocks.py paper-trader/backend/app/ir/strategies/expanding_z.py paper-trader/backend/research/strategy/builder/blocks.py paper-trader/backend/research/strategy/builder/ir_components.py paper-trader/backend/tests/test_ir_causal_contract.py paper-trader/backend/research_tests/test_block_declared_inputs.py
git commit -m "feat(strategy): declare closed causal kernel contracts"
```

### Task 2: Immutable production registrations and transitive identity

**Files:**
- Create: `paper-trader/backend/app/ir/implementation_identity.py`
- Create: `paper-trader/backend/app/ir/registry.py`
- Modify: `paper-trader/backend/app/ir/kernels.py`
- Modify: `paper-trader/backend/app/ir/authoring.py`
- Modify: `paper-trader/backend/app/ir/contributors/generated_blocks.py`
- Modify: `paper-trader/backend/app/ir/strategies/expanding_z.py`
- Modify: `paper-trader/backend/app/ir/library.py`
- Test: `paper-trader/backend/tests/test_ir_implementation_identity.py`
- Test: `paper-trader/backend/tests/test_ir_platform_library.py`
- Test: `paper-trader/backend/tests/test_ir_strategy_parity.py`

**Interfaces:**
- Produces: `implementation_address(implementation: object, boundary: DependencyBoundary, recursive_state: RecursiveStateContract | None = None) -> str`.
- Produces: `DependencyBoundary`, immutable `KernelRegistration`, `PlatformRegistry`, and `registered_kernel(*, body_ref, implementation, causal, dependency_boundary, warmup=0, purity="pure", cache_identity="transitive", cache_key=None)`.
- Produces: `app.ir.library.REGISTRY`; `LIBRARY` and `IMPLEMENTATIONS` are derived read-only views.

- [ ] **Step 1: Write failing identity tests**

```python
def test_helper_change_changes_transitive_identity():
    def helper_a(value): return value + 1
    def helper_b(value): return value + 2
    def kernel_a(params, inputs): return {"out": helper_a(inputs["close"])}
    def kernel_b(params, inputs): return {"out": helper_b(inputs["close"])}
    a = DependencyBoundary("declared_objects", (helper_a,))
    b = DependencyBoundary("declared_objects", (helper_b,))
    assert implementation_address(kernel_a, a) != implementation_address(kernel_b, b)

def test_address_cannot_be_forged():
    with pytest.raises(TypeError):
        registered_kernel(body_ref=BODY, implementation=_kernel, causal=_contract(),
                          dependency_boundary=BOUNDARY,
                          implementation_address="sha256:" + "0" * 64)

def test_undeclared_global_and_closure_dependencies_refuse():
    with pytest.raises(ImplementationUnidentified, match="undeclared"):
        registered_kernel(body_ref=BODY, implementation=kernel_using_helper,
                          causal=_contract(),
                          dependency_boundary=DependencyBoundary("declared_objects", ()))

def test_spec_and_callable_travel_in_one_registration():
    registration = registered_kernel(body_ref=BODY, implementation=_kernel,
                                     causal=_contract(),
                                     dependency_boundary=BOUNDARY)
    assert registration.spec.causal == _contract()
    assert registration.implementation is _kernel
```

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_implementation_identity.py`

Expected: FAIL on missing functions.

- [ ] **Step 3: Implement canonical transitive hashing**

```python
IDENTITY_SCHEME = "ir-kernel-implementation/1"

def implementation_address(implementation: object,
                           boundary: DependencyBoundary,
                           recursive_state: RecursiveStateContract | None = None) -> str:
    payload = {
        "scheme": IDENTITY_SCHEME,
        "implementation": closed_object_identity(implementation, boundary),
        "recursive_state": recursive_state_identity(recursive_state, boundary),
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()
```

`object_identity` accepts functions and classes under `declared_objects`; hashes normalized source,
defaults, annotations, closure values, and recursively declared dependencies; and raises
`ImplementationUnidentified` instead of falling back to `repr`, module name, or `unknown`. Inspect
bytecode global reads and closure variables. Reject missing and extra declarations, dynamic global
or module lookup, and runtime import. Under `defining_module`, reject closures and hash the complete
module file bytes plus distribution version. Sort dependency identities before hashing.

- [ ] **Step 4: Build the single registration transport and production registry**

```python
registration = registered_kernel(
    body_ref=body_ref,
    implementation=fn,
    causal=causal,
    dependency_boundary=dependency_boundary,
    warmup=warmup,
    purity=purity,
    cache_identity=cache_identity,
    cache_key=cache_key,
)
```

`PlatformRegistry` accepts registrations plus components/bodies and exposes derived `library` and
`implementations` mappings. Change contributor contract to `REGISTRATIONS`; `compose` refuses a
spec/callable/body mismatch before producing `REGISTRY`. No production admission function accepts
independent maps.

For generated blocks, dependency boundaries include the block function and every helper returned
by a closed `BLOCK_DEPENDENCIES[name]` mapping. Add a guard that every `BLOCKS` key appears. Add
`generated_blocks` literally to `app.ir.library.CONTRIBUTORS`; research uses `REGISTRY` from that
module and never composes a private library.

Create production `logic.and` and `logic.or` components in the app-owned contributor. Both have
`left,right` boolean sockets. Register both as pure bounded-zero completed-bar kernels with zero
delay and closed defining-module boundaries. Add
a closure guard requiring exact component identities, body refs, registrations, and callable views:

```python
LOGIC_IDENTIFIERS = {"logic.and", "logic.or"}
assert LOGIC_IDENTIFIERS <= {key[0] for key in COMPONENTS}
assert {COMPONENTS[key]["body"]["ref"] for key in LOGIC_IDENTIFIERS} <= set(REGISTRATIONS)
```

- [ ] **Step 5: Register the complete existing expanding-z contributor**

Replace its independent `KERNELS`/`IMPLEMENTATIONS` construction with registrations for EMA, true
range, Wilder, z-score, absolute value, adaptive threshold, scalar value, scale, drift/range ATR,
comparison, impulse, entry, and exit. EMA and Wilder register recursive initializer/state encoder/
update/step implementations. Declare every helper from `app.strategy.registry.expanding_z_v4` or
choose `defining_module` and hash that complete module. Add an exhaustive assertion:

```python
assert set(REGISTRATIONS) == {
    component["body"]["ref"] for component in COMPONENTS
    if component["body"]["body"] == "kernel"
}
```

Refactor wrappers before deriving identity: move `import pandas as pd` to module scope; statically
import `_rma`, `zscore`, `adaptive_threshold`, `drift_score`, `range_in_atr`, `impulse`,
`directional_entry`, `displacement_lost`, and `_as_bool`; call these bound names directly instead of
`impl.*`; remove every runtime import. Use `DependencyBoundary("defining_module", objects=(...))`
with exact helpers and pandas/numpy modules. Add a test that replaces the actual imported `_rma`
helper after registration, re-derives identity, and gets a different address plus
`IMPLEMENTATION_STALE`; a dummy helper does not satisfy this test.

- [ ] **Step 6: Run focused, contributor, and parity tests**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_implementation_identity.py tests/test_ir_authoring.py tests/test_ir_platform_library.py tests/test_ir_strategy_parity.py research_tests/test_ir_block_components.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/ir/implementation_identity.py paper-trader/backend/app/ir/registry.py paper-trader/backend/app/ir/kernels.py paper-trader/backend/app/ir/authoring.py paper-trader/backend/app/ir/contributors/generated_blocks.py paper-trader/backend/app/ir/strategies/expanding_z.py paper-trader/backend/app/ir/library.py paper-trader/backend/tests/test_ir_implementation_identity.py paper-trader/backend/tests/test_ir_platform_library.py paper-trader/backend/tests/test_ir_strategy_parity.py
git commit -m "feat(strategy): bind transitive kernel implementation identity"
```

### Task 3: Immutable admission artefact and stable refusal codes

**Files:**
- Create: `paper-trader/backend/app/strategy/admission.py`
- Modify: `paper-trader/backend/app/ir/resolve.py`
- Modify: `paper-trader/backend/app/strategy/ir_adapter.py`
- Test: `paper-trader/backend/tests/test_strategy_admission.py`

**Interfaces:**
- Produces `IRGraphAdmissionInput`, `HandwrittenAdapterInput`, `SourceEvidence`, `ResolvedComponentIdentity`, `InputProvenance`, `AdmittedKernelIdentity`, `StructuralAdmission`, `StructuralDecision`, `ParityEvidence`, `AdmittedStrategyArtifact`, and `AdmissionRefusalCode` from spec §6.2.
- Produces: `canonical_decisions(frame: pd.DataFrame) -> bytes`.
- Produces: `inspect_strategy(*, owner_id, source_input, registry) -> StructuralDecision`.
- Produces: `derive_input_provenance(graph: ResolvedGraph) -> tuple[InputProvenance, ...]`.
- Consumes: `ResolvedGraph`, causal `KernelSpec`s, implementation addresses, `column_mapping`, `validate_risk_model`.

- [ ] **Step 1: Write failing refusal and address tests**

```python
def test_missing_contract_refuses_without_an_artifact(graph_and_library):
    graph, registry = graph_and_library
    decision = inspect_strategy(owner_id="owner-a",
                                source_input=IRGraphAdmissionInput(graph, {}, None),
                                registry=registry_without_one_contract(registry))
    assert decision.structural is None
    assert decision.refusal_code is AdmissionRefusalCode.CONTRACT_MISSING

def test_owner_is_part_of_private_admission_address(admittable_graph):
    a = artifact_fixture(owner_id="owner-a", graph=admittable_graph)
    b = artifact_fixture(owner_id="owner-b", graph=admittable_graph)
    assert a.admission_address != b.admission_address

def test_contract_names_node_sockets_and_provenance_is_derived(nested_graph):
    structural = inspect_strategy(owner_id="owner-a",
        source_input=IRGraphAdmissionInput(nested_graph.graph, {}, None),
        registry=nested_graph.registry).structural
    close_input = next(p for p in structural.input_provenance
                       if p.node_path == "nested/z" and p.socket == "source")
    assert close_input.root_market_inputs == ("close",)
    assert close_input.source_paths == (("$input.close", "nested.input", "nested/z.source"),)

def test_missing_or_extra_node_socket_declaration_refuses(graph_case):
    assert inspect_with_contract(graph_case, sockets=()).refusal_code == \
        AdmissionRefusalCode.INPUT_UNDECLARED
    assert inspect_with_contract(graph_case, sockets=("close", "ghost")).refusal_code == \
        AdmissionRefusalCode.CONTRACT_INVALID
```

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_strategy_admission.py`

Expected: FAIL because the admission module does not exist.

- [ ] **Step 3: Implement canonical artefact data**

```python
class AdmissionRefusalCode(str, Enum):
    IR_INVALID = "IR_INVALID"
    RESOLUTION_FAILED = "RESOLUTION_FAILED"
    COMPONENT_QUARANTINED = "COMPONENT_QUARANTINED"
    CONTRACT_MISSING = "CONTRACT_MISSING"
    CONTRACT_INVALID = "CONTRACT_INVALID"
    INPUT_UNDECLARED = "INPUT_UNDECLARED"
    CONTEXT_UNDECLARED = "CONTEXT_UNDECLARED"
    EXTERNAL_SERIES_UNRESOLVED = "EXTERNAL_SERIES_UNRESOLVED"
    IMPURE_KERNEL = "IMPURE_KERNEL"
    IMPLEMENTATION_UNIDENTIFIED = "IMPLEMENTATION_UNIDENTIFIED"
    IMPLEMENTATION_STALE = "IMPLEMENTATION_STALE"
    HISTORY_INVALID = "HISTORY_INVALID"
    OUTPUT_DELAY_INVALID = "OUTPUT_DELAY_INVALID"
    OUTPUT_MAPPING_INVALID = "OUTPUT_MAPPING_INVALID"
    STREAMING_DIVERGENCE = "STREAMING_DIVERGENCE"
    VECTOR_EVALUATION_FAILED = "VECTOR_EVALUATION_FAILED"
    REFERENCE_EVALUATION_FAILED = "REFERENCE_EVALUATION_FAILED"
    OWNER_SCOPE_INVALID = "OWNER_SCOPE_INVALID"
    ARTEFACT_MISMATCH = "ARTEFACT_MISMATCH"
    RECEIPT_STALE = "RECEIPT_STALE"
```

Use tuples and `MappingProxyType` internally. `to_dict()` emits sorted JSON-compatible data.
`admission_address` hashes `to_dict()` including owner. Never store exception text in hashed data.

- [ ] **Step 4: Implement structural admission before parity**

Validate IR, resolve it from `PlatformRegistry.library`, require a complete registration and
freshly re-derived implementation address for every resolved body,
compare `node_input_sockets` exactly with component interface and runtime wiring, require pure/completed-bar/nonnegative
delay, evaluate history bounds, validate canonical mapping/risk, and assemble identities. Leave the
parity evidence fields unset in `StructuralAdmission`; it is not an `AdmittedStrategyArtifact` and
has no admission address. Task 4 is the only constructor for the final artefact.

Derive `InputProvenance` recursively through ordinary edges, nested graph boundaries, and default
sources. Root names come only from the graph interface. Derived outputs union upstream roots;
scalars have no roots. Refuse cycles, missing paths, undeclared roots, and context-as-socket. Include
every source path in canonical artifact bytes; callers cannot supply or override provenance.

- [ ] **Step 5: Implement canonical artefact construction from structural and parity evidence**

```python
def admitted_artifact(structural: StructuralAdmission,
                      parity: ParityEvidence) -> AdmittedStrategyArtifact:
    if parity.reference_decision_address != parity.vector_decision_address:
        raise AdmissionRefused(AdmissionRefusalCode.STREAMING_DIVERGENCE,
                               "canonical decision addresses differ")
    return AdmittedStrategyArtifact.from_evidence(structural, parity)
```

For `HandwrittenAdapterInput`, structurally verify the strategy key/version, derive the adapter
implementation address from its closed dependency boundary, and inspect the equivalent IR input.
Record both identities in `SourceEvidence`; do not resolve a handwritten class from a key later.

- [ ] **Step 6: Run focused tests**

Run: `cd paper-trader/backend && pytest -q tests/test_strategy_admission.py tests/test_ir_adapter.py tests/test_ir_runtime.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/strategy/admission.py paper-trader/backend/app/ir/resolve.py paper-trader/backend/app/strategy/ir_adapter.py paper-trader/backend/tests/test_strategy_admission.py
git commit -m "feat(strategy): define immutable causal admission receipts"
```

### Task 4: Independent prefix reference, parity suite, and causal mutations

**Files:**
- Create: `paper-trader/backend/app/ir/streaming_reference.py`
- Create: `paper-trader/backend/app/strategy/causal_fixtures.py`
- Create: `paper-trader/backend/scripts/causal_admission_mutations.py`
- Modify: `paper-trader/backend/app/strategy/admission.py`
- Test: `paper-trader/backend/tests/test_ir_streaming_reference.py`
- Test: `paper-trader/backend/tests/test_causal_admission_mutations.py`
- Test: `paper-trader/backend/research_tests/test_block_causal_parity.py`

**Interfaces:**
- Produces: `evaluate_prefix_stream(graph, inputs, registry) -> EvaluationResult`.
- Produces: `CausalFixture`, `CausalFixtureSuite`, immutable `FIXTURE_SUITES`, and `FIXTURE_SUITES.require("causal-fixtures/1")`.
- Produces the final `admit_strategy(*, owner_id, source_input, registry) -> AdmissionDecision` and `verify_admission(*, artifact, owner_id, source_input, registry) -> None` interfaces from spec §6.2; neither accepts a suite or parity bypass.

- [ ] **Step 1: Write failing independence and contamination tests**

```python
def test_reference_does_not_call_vector_runtime(monkeypatch, graph_case):
    monkeypatch.setattr("app.ir.runtime.evaluate",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("vector called")))
    result = evaluate_prefix_stream(**graph_case)
    assert len(result.outputs["longEntry"]) == len(graph_case["inputs"]["close"])

def test_recursive_vector_matches_initializer_update_step(recursive_case):
    vector = evaluate(recursive_case.graph, recursive_case.inputs,
                      recursive_case.registry.implementations)
    stepped = evaluate_prefix_stream(recursive_case.graph, recursive_case.inputs,
                                     recursive_case.registry)
    assert canonical_node_values(vector) == canonical_node_values(stepped)

def test_timestamp_context_is_the_current_recorded_index(clock_graph):
    result = evaluate_prefix_stream(clock_graph.graph, clock_graph.inputs,
                                    clock_graph.registry)
    assert list(result.outputs["seen_timestamp"]) == list(clock_graph.inputs["close"].index)

@pytest.mark.parametrize("name", sorted(ADMITTED_BLOCK_NAMES))
def test_every_admitted_block_vector_matches_independent_reference(name, block_fixture):
    assert_block_parity(name, block_fixture(name))

def test_quarantined_blocks_refuse_lowering():
    for name in QUARANTINED_BLOCK_NAMES:
        assert_lowering_refuses(name, AdmissionRefusalCode.COMPONENT_QUARANTINED)

@pytest.mark.parametrize("mutation", ["negative_shift", "centered_window", "bfill",
                                       "future_join", "global_normalize"])
def test_future_contamination_is_rejected(mutation, admitted_case):
    decision = run_freshly_registered_mutation(mutation, admitted_case)
    assert decision.artifact is None
    assert decision.refusal_code is AdmissionRefusalCode.STREAMING_DIVERGENCE

def test_post_registration_callable_change_is_stale(admitted_case):
    decision = run_unregistered_callable_change(admitted_case)
    assert decision.artifact is None
    assert decision.refusal_code is AdmissionRefusalCode.IMPLEMENTATION_STALE

@pytest.mark.parametrize("mutation", ["omit_node_socket", "add_ghost_socket",
                                       "bypass_root_provenance"])
def test_socket_and_provenance_mutations_are_rejected(mutation, admitted_case):
    decision = run_structural_mutation(mutation, admitted_case)
    assert decision.artifact is None
    assert decision.refusal_code in {
        AdmissionRefusalCode.INPUT_UNDECLARED,
        AdmissionRefusalCode.CONTRACT_INVALID,
        AdmissionRefusalCode.ARTEFACT_MISMATCH,
    }
```

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_streaming_reference.py tests/test_causal_admission_mutations.py research_tests/test_block_causal_parity.py`

Expected: FAIL on missing reference and mutation modules.

- [ ] **Step 3: Implement the independent evaluator**

Implement its own topological sort, wiring map, graph-input binding, per-node invocation, output
binding, bounded prefix cache, and recursive state table. It may import `ResolvedGraph`,
`ResolvedNode`, and registration types;
it must not import `evaluate`, `_compute`, `_inputs_for`, or `Cache` from `app.ir.runtime`.

```python
for end in range(1, input_length + 1):
    prefix = {name: value.iloc[:end].copy() for name, value in inputs.items()}
    context = {"bar_timestamp": next(iter(prefix.values())).index[-1]}
    produced = _evaluate_one_completed_bar(graph, prefix, context, registry, states)
    for name, (instance, socket) in graph.outputs.items():
        streams[name].append(produced[instance][socket].iloc[-1])
```

For bounded nodes call the registered vector implementation with only the prefix. For recursive
nodes initialize once, encode state, call update once, call step once, and retain the next state.
Compare every recursive node's vector output with step output after warmup before graph outputs.
Reject absent, duplicated, non-monotonic, or timezone-ambiguous index context.

In `test_block_causal_parity.py`, run every admitted manifest disposition through both evaluators.
Add explicit parameter coverage for every RSI `source × smooth` choice, an opening-range fixture
that crosses two session boundaries, and a long regime fixture that changes its expanding median.
The admitted-name set is derived from the exhaustive manifest, so a newly added block cannot evade
parity. A quarantined disposition is tested only for deterministic lowering refusal.

- [ ] **Step 4: Add deterministic fixtures and byte comparison**

Seed random frames with `numpy.random.default_rng(20260813)`. Define suite bytes in the app module,
register the literal `(suite_id, suite_address)` in an immutable mapping, and expose no public suite
constructor to production admission. Canonicalize UTC timestamp integer
nanoseconds plus `longEntry`, `shortEntry`, `longExit`, `shortExit` as bytes in that order. Require
identical address, index, length, and flags; do not call `Series.equals` after dtype coercion.

Implement `admit_strategy` by loading the registered suite internally, calling `inspect_strategy`,
running both evaluators on every fixture,
building `ParityEvidence`, and calling `admitted_artifact`. Implement `verify_admission` by repeating
that process and requiring the recomputed address to equal the supplied artefact address. Map a
structural refusal, evaluator exception, or byte mismatch to its stable refusal code; there is no
flag or callback that skips parity.

- [ ] **Step 5: Add the mutation command and prove every mutant dies**

The command first changes an actual statically imported expanding-z helper after its registration
and requires `IMPLEMENTATION_STALE`.
It then creates five fresh `KernelRegistration` records with newly derived addresses for the
negative-shift, centered-window, backward-fill, future-join, and global-normalization callables;
each must reach parity and fail `STREAMING_DIVERGENCE`. Return nonzero if either identity class or
any causal mutant survives. Test each path directly.

Also mutate the local socket declaration by omission and addition, and bypass one nested
root-provenance edge. These must fail structurally before parity. The provenance mutant must alter
the derived path in production code, not pass caller-supplied fake provenance.

Add handwritten adapter parity: exact `expanding_z_v4` key/version and adapter implementation must
match its equivalent IR at the byte level across the registered suite. Assert the artifact runtime
factory returns `IRGraphStrategy`; do not execute the handwritten class for new exposure.

Run: `cd paper-trader/backend && python scripts/causal_admission_mutations.py --json`

Expected: JSON reports `identity_killed: 1`, `causal_killed: 5`, `survived: 0`; exit 0.

- [ ] **Step 6: Run parity regressions**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_streaming_reference.py tests/test_causal_admission_mutations.py tests/test_ir_strategy_parity.py tests/test_handwritten_strategy_causality.py research_tests/test_block_causal_parity.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/ir/streaming_reference.py paper-trader/backend/app/strategy/causal_fixtures.py paper-trader/backend/app/strategy/admission.py paper-trader/backend/scripts/causal_admission_mutations.py paper-trader/backend/tests/test_ir_streaming_reference.py paper-trader/backend/tests/test_causal_admission_mutations.py paper-trader/backend/research_tests/test_block_causal_parity.py
git commit -m "feat(strategy): prove prefix and vector decision parity"
```

### Task 5: Mechanical Composition-to-IR lowering

**Files:**
- Create: `paper-trader/backend/research/strategy/builder/composition_ir.py`
- Modify: `paper-trader/backend/research/strategy/builder/ir_search.py`
- Modify: `paper-trader/backend/research/orchestrator/generate.py`
- Modify: `paper-trader/backend/research/strategy/builder/load.py`
- Test: `paper-trader/backend/research_tests/test_composition_ir.py`
- Test: `paper-trader/backend/research_tests/test_builder_integration.py`

**Interfaces:**
- Produces: `composition_to_ir(comp: Composition, *, identifier: str, version: int = 1, instrument: str = "*", timeframe: str = "*") -> dict[str, Any]`.
- Search/generation produces graph plus admission address; emitted source remains review text only.
- Consumes only `app.ir.library.REGISTRY`; no research-local component library is accepted.

- [ ] **Step 1: Write failing determinism and semantic parity tests**

```python
def test_same_composition_lowers_to_same_ir_bytes():
    first = composition_to_ir(COMPOSITION, identifier="gen.example")
    second = composition_to_ir(Composition.from_dict(COMPOSITION.to_dict()),
                               identifier="gen.example")
    assert canonical_json(first) == canonical_json(second)

def test_lowered_ir_matches_existing_composition_flags(frame):
    legacy = build_strategy(COMPOSITION).signals(frame)
    graph = composition_to_ir(COMPOSITION, identifier="gen.example")
    ir = IRGraphStrategy(graph, ir_library()).signals(frame)
    assert_frame_equal(ir[list(CANONICAL_COLUMNS)], legacy[list(CANONICAL_COLUMNS)])
```

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q research_tests/test_composition_ir.py`

Expected: FAIL because `composition_ir` does not exist.

- [ ] **Step 3: Implement deterministic lowering**

Use canonical clause order `long_entry`, `short_entry`, `long_exit`, `short_exit`; deterministic node
IDs `c{clause_index}_b{block_index}`; explicit boundary nodes; and the app-owned registered
`logic.and` and `logic.or` components. Create only inputs in the union of app-owned
`BlockSpec.inputs`. Validate with `app.ir.library.REGISTRY.library` and return canonical JSON
round-tripped to a dict. A test searches production code for another `compose(...)` call and permits
only `app.ir.library` and isolated unit-test fixtures.

Preserve the existing non-empty-clause invariant: reject an empty clause during Composition parsing
and again at the lowering boundary. One-block clauses wire directly; multiple blocks become a
deterministic left-associated chain of `logic.and` or `logic.or` binary nodes. Before lowering,
assert both logic component identities resolve from production `REGISTRY`; do not synthesize
component dictionaries inside the lowerer. Add an empty-clause refusal test, one-, two-, and
four-block lowering tests, and one refusal test for each removed logic registration.

- [ ] **Step 4: Remove generated Python from authority decisions**

Keep `emit_source` and `compile_composition` for display and legacy comparison. Change search and
generation descriptors to carry `graph`, `graph_content_address`, and `admission_address`.
`build_strategy` must be marked legacy-only and must not be called by promotion, new backtests, or
deployment after Task 10.

- [ ] **Step 5: Run builder and IR suites**

Run: `cd paper-trader/backend && pytest -q research_tests/test_composition_ir.py research_tests/test_builder_integration.py research_tests/test_ir_search.py research_tests/test_builder_generate.py tests/test_ir_strategy_parity.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add paper-trader/backend/research/strategy/builder/composition_ir.py paper-trader/backend/research/strategy/builder/ir_search.py paper-trader/backend/research/orchestrator/generate.py paper-trader/backend/research/strategy/builder/load.py paper-trader/backend/research_tests/test_composition_ir.py paper-trader/backend/research_tests/test_builder_integration.py
git commit -m "feat(research): lower compositions mechanically into component IR"
```

### Task 6: Execution-plane admission persistence and migration 0034

**Files:**
- Modify: `paper-trader/backend/app/db/models.py`
- Create: `paper-trader/backend/app/core/strategy_admissions.py`
- Create: `paper-trader/backend/migrations/versions/20260813_0034_strategy_admissions.py`
- Modify: `paper-trader/backend/app/db/planes.py`
- Test: `paper-trader/backend/tests/test_strategy_admission_repository.py`
- Test: `paper-trader/backend/tests/test_schema_migrations.py`
- Test: `paper-trader/backend/tests/test_postgres_execution_schema.py`
- Test: `paper-trader/backend/tests/test_postgres_plane_schemas.py`

**Interfaces:**
- Produces: `StrategyAdmission` model and repository `put`, `get`, `require_current`.
- Adds nullable `admission_address: str | None` fields listed in design §9.1.

- [ ] **Step 1: Write failing repository and schema tests**

```python
def test_admission_is_owner_scoped_and_immutable(session, artifact):
    put(session, artifact)
    assert get(session, owner_id=artifact.owner_id,
               admission_address=artifact.admission_address) is not None
    assert get(session, owner_id="other",
               admission_address=artifact.admission_address) is None
    with pytest.raises(Exception, match="immutable"):
        session.execute(update(StrategyAdmission).values(artifact_json="{}"))

def test_direct_sql_update_and_delete_are_refused(connection, stored_artifact):
    original = connection.execute(text(
        "SELECT artifact_json FROM strategy_admissions "
        "WHERE owner_id=:owner AND admission_address=:address"), stored_artifact.key).scalar_one()
    with pytest.raises(DBAPIError):
        connection.execute(text(
            "UPDATE strategy_admissions SET artifact_json='{}' "
            "WHERE owner_id=:owner AND admission_address=:address"), stored_artifact.key)
    connection.rollback()
    assert read_artifact_json(connection, stored_artifact.key) == original
```

Assert migration heads `0034` and all exact columns/types/nullability in both dialects.

- [ ] **Step 2: Verify red on SQLite**

Run: `cd paper-trader/backend && pytest -q tests/test_strategy_admission_repository.py tests/test_schema_migrations.py`

Expected: FAIL because the model and migration are absent.

- [ ] **Step 3: Implement model, immutable repository, and migration**

```python
class StrategyAdmission(Base):
    __tablename__ = "strategy_admissions"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    admission_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    contract_suite: Mapped[str] = mapped_column(String(32), nullable=False)
    parity_suite: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

The migration uses additive nullable consumer columns, `CHECK(length(admission_address)=71)` where
portable, composite owner/address indexes, SQLite `BEFORE UPDATE/DELETE` immutable triggers, and a
PostgreSQL `BEFORE UPDATE OR DELETE` trigger function that raises SQLSTATE `55000`. Test direct SQL
UPDATE and DELETE against both dialects and verify the original bytes remain. `put` canonicalizes
and verifies the address before insert; exact duplicate insert is
idempotent, differing bytes at the same key refuse.

- [ ] **Step 4: Classify the admission table as USER and consumer columns in their existing planes**

Update `app/db/planes.py` and its exhaustive tests. `strategy_admissions` is `USER`. The research
database has its own research-plane receipt table. The execution-side receipt describes private
strategy proof; money rows merely reference its address.

- [ ] **Step 5: Run SQLite and live PostgreSQL migration tests**

Run: `cd paper-trader/backend && pytest -q tests/test_strategy_admission_repository.py tests/test_schema_migrations.py tests/test_db_planes.py`

Run with the configured test URL: `cd paper-trader/backend && PT_TEST_POSTGRES_URL="$PT_TEST_POSTGRES_URL" pytest -q tests/test_postgres_execution_schema.py tests/test_postgres_plane_schemas.py tests/test_strategy_admission_repository.py`

Expected: PASS in both dialects.

- [ ] **Step 6: Commit**

```bash
git add paper-trader/backend/app/db/models.py paper-trader/backend/app/core/strategy_admissions.py paper-trader/backend/migrations/versions/20260813_0034_strategy_admissions.py paper-trader/backend/app/db/planes.py paper-trader/backend/tests/test_strategy_admission_repository.py paper-trader/backend/tests/test_schema_migrations.py paper-trader/backend/tests/test_postgres_execution_schema.py paper-trader/backend/tests/test_postgres_plane_schemas.py
git commit -m "feat(strategy): persist immutable execution admission receipts"
```

### Task 7: Research-plane admission persistence and migration 0005

**Files:**
- Modify: `paper-trader/backend/research/domain/models.py`
- Create: `paper-trader/backend/research/domain/admissions.py`
- Create: `paper-trader/backend/research/domain/migrations/0005_strategy_admissions.py`
- Modify: `paper-trader/backend/research/domain/migrate.py`
- Test: `paper-trader/backend/research_tests/test_strategy_admissions.py`
- Test: `paper-trader/backend/research_tests/test_operation_migration.py`
- Test: `paper-trader/backend/research_tests/test_postgres_operation_concurrency.py`

**Interfaces:**
- Produces: `ResearchStrategyAdmission`, `store_admission`, `load_admission`, `require_admission`.
- Adds `admission_address: str | None` to `ExperimentRun` and `PromotionCandidate`.

- [ ] **Step 1: Write failing research ownership and migration tests**

```python
def test_research_receipt_cannot_cross_owner(session, artifact):
    store_admission(session, artifact)
    assert load_admission(session, owner_id="other",
                          admission_address=artifact.admission_address) is None

def test_candidate_address_must_match_its_run(session, run, candidate):
    candidate.admission_address = "sha256:" + "1" * 64
    with pytest.raises(AdmissionBindingError):
        require_candidate_admission(session, candidate, owner_id=run.owner_id)

def test_research_admission_refuses_direct_sql_mutation(connection, stored):
    with pytest.raises(DBAPIError):
        connection.execute(text(
            "DELETE FROM research_strategy_admission "
            "WHERE owner_id=:owner AND admission_address=:address"), stored.key)
```

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q research_tests/test_strategy_admissions.py research_tests/test_operation_migration.py`

Expected: FAIL on missing table and migration head.

- [ ] **Step 3: Implement research store and migration**

Mirror canonical validation and append-only behavior from Task 6 without importing execution-plane
sessions or models. Migration `0005` follows `0004`, adds the table and nullable run/candidate
columns, and leaves existing rows null. Install both SQLite immutable triggers and a PostgreSQL
trigger function; direct SQL UPDATE and DELETE tests must fail and retain original bytes.

- [ ] **Step 4: Run SQLite and live PostgreSQL research tests**

Run: `cd paper-trader/backend && pytest -q research_tests/test_strategy_admissions.py research_tests/test_operation_migration.py research_tests/test_models.py`

Run: `cd paper-trader/backend && PT_TEST_POSTGRES_URL="$PT_TEST_POSTGRES_URL" pytest -q research_tests/test_postgres_operation_concurrency.py research_tests/test_strategy_admissions.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add paper-trader/backend/research/domain/models.py paper-trader/backend/research/domain/admissions.py paper-trader/backend/research/domain/migrations/0005_strategy_admissions.py paper-trader/backend/research/domain/migrate.py paper-trader/backend/research_tests/test_strategy_admissions.py paper-trader/backend/research_tests/test_operation_migration.py paper-trader/backend/research_tests/test_postgres_operation_concurrency.py
git commit -m "feat(research): persist owner-scoped causal admissions"
```

### Task 8: Editor publication and research worker enforcement

**Files:**
- Modify: `paper-trader/backend/app/editor/graph_artifacts.py`
- Modify: `paper-trader/backend/app/api/ir_edit_routes.py`
- Modify: `paper-trader/backend/research/orchestrator/graph_experiment.py`
- Modify: `paper-trader/backend/research/strategy/builder/ir_evaluate.py`
- Modify: `paper-trader/backend/research/domain/operations.py`
- Test: `paper-trader/backend/tests/test_ir_edit_routes.py`
- Test: `paper-trader/backend/research_tests/test_graph_experiment.py`
- Test: `paper-trader/backend/research_tests/test_operation_claim_contract.py`

**Interfaces:**
- `Publication` carries `admission_address: str`.
- Research operation generated descriptors require `graph_content_address` and `admission_address`.
- Workers call `require_admission` before provider construction.

- [ ] **Step 1: Write failing publication and stale-worker tests**

```python
def test_editor_does_not_publish_when_admission_refuses(client, future_graph):
    response = client.post(EDIT_URL, json=future_graph)
    assert response.status_code == 422
    assert response.json()["code"] == "STREAMING_DIVERGENCE"
    assert current_version() == PREVIOUS_VERSION

def test_worker_refuses_forged_receipt_before_provider(monkeypatch, operation):
    monkeypatch.setattr(operation, "admission_address", "sha256:" + "0" * 64)
    provider = Mock(side_effect=AssertionError("provider constructed"))
    assert run_item(operation, provider_factory=provider).code == "RECEIPT_STALE"
    provider.assert_not_called()
```

Add three independent mutations that remove editor publication admission, research enqueue binding,
research worker reload, and research worker verification. Name their kills
`bypass_editor_publish`, `bypass_research_enqueue`, `bypass_research_worker` (the worker mutation
must cover both load and verify in separate assertions under that seam). Each matching test must go
red when its own seam is removed while the others remain intact.

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_edit_routes.py research_tests/test_graph_experiment.py research_tests/test_operation_claim_contract.py`

Expected: the new assertions fail because publication/workers do not bind admission.

- [ ] **Step 3: Admit atomically during publication**

In `publish_draft` and `apply_and_publish`, call admission after semantic validation and before
inserting `GraphVersion`. Store the execution receipt and address on the version in the same
transaction. Map `AdmissionRefused` to the existing structured 422 envelope using the stable code.
Keep the edited draft when admission refuses; do not advance published revision/current version.

- [ ] **Step 4: Bind and verify graph experiments and operation items**

At enqueue, store the research receipt and its address in the exact graph descriptor. At claim,
load owner-scoped graph bytes and receipt, call `verify_admission`, then construct any provider.
Record stable refusal code in the durable item error and projection event.

- [ ] **Step 5: Run focused editor/research tests**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_edit_routes.py tests/test_graph_artifacts.py tests/test_ir_editor_equivalence.py research_tests/test_graph_experiment.py research_tests/test_ir_evaluate.py research_tests/test_operation_claim_contract.py research_tests/test_operations.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add paper-trader/backend/app/editor/graph_artifacts.py paper-trader/backend/app/api/ir_edit_routes.py paper-trader/backend/research/orchestrator/graph_experiment.py paper-trader/backend/research/strategy/builder/ir_evaluate.py paper-trader/backend/research/domain/operations.py paper-trader/backend/tests/test_ir_edit_routes.py paper-trader/backend/research_tests/test_graph_experiment.py paper-trader/backend/research_tests/test_operation_claim_contract.py
git commit -m "feat(strategy): enforce admission at publication and research execution"
```

### Task 9: Backtest admission, cache identity, and next-bar execution

**Files:**
- Modify: `paper-trader/backend/app/api/backtest_routes.py`
- Modify: `paper-trader/backend/app/backtest/repository.py`
- Modify: `paper-trader/backend/app/backtest/identity.py`
- Modify: `paper-trader/backend/app/backtest/sweep.py`
- Modify: `paper-trader/backend/app/backtest/engine.py`
- Test: `paper-trader/backend/tests/test_backtest_admission.py`
- Test: `paper-trader/backend/tests/test_backtest_cache.py`
- Test: `paper-trader/backend/tests/test_backtest_fill_timing.py`

**Interfaces:**
- `enqueue_run(session, *, owner_id, scope, intervals, capital, total, admission_address, now=None, **values)` requires a current owner-scoped receipt.
- Add required keyword `admission_address: str` to the existing `execution_result_address` signature and include it in canonical identity.
- Results copy `BacktestRun.admission_address`.

- [ ] **Step 1: Write failing enqueue, cache, and same-bar tests**

```python
def test_backtest_without_admission_is_rejected(session):
    with pytest.raises(AdmissionRequired):
        enqueue_run(session, owner_id="owner-a", scope="NIFTY", intervals="5minute",
                    admission_address=None)

def test_admission_change_forces_cache_miss(base_manifest):
    first = execution_result_address(**base_manifest, admission_address=ADDRESS_A)
    second = execution_result_address(**base_manifest, admission_address=ADDRESS_B)
    assert first != second

def test_signal_on_t_cannot_fill_on_t(frame, admitted_strategy):
    trades = run_trades(frame, admitted_strategy)
    assert trades[0].entry_time == frame.index[1]
```

Add independent `bypass_backtest_enqueue` and `bypass_backtest_worker` mutations. Each removes only
its named check and must make its corresponding test fail without relying on the other check.

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_backtest_admission.py tests/test_backtest_cache.py tests/test_backtest_fill_timing.py`

Expected: new admission tests fail; existing timing behavior is recorded before mutation.

- [ ] **Step 3: Require admission at enqueue and re-verify in worker**

API resolves graph/version under owner, loads receipt, calls `verify_admission`, then enqueues.
Worker repeats verification before dataset/provider access. A failed item records stable code and no
result. Pass the address into every cache manifest and result row.

- [ ] **Step 4: Add a same-bar mutation probe**

Add a local mutation helper that changes the entry index from `signal_index + 1` to `signal_index`.
The timing test must fail under the mutation. Keep production code on the existing next-open path.

Run: `cd paper-trader/backend && pytest -q tests/test_backtest_admission.py tests/test_backtest_cache.py tests/test_backtest_fill_timing.py tests/test_backtest_pinned.py`

Expected: PASS; mutation subtest reports the same-bar mutant killed.

- [ ] **Step 5: Commit**

```bash
git add paper-trader/backend/app/api/backtest_routes.py paper-trader/backend/app/backtest/repository.py paper-trader/backend/app/backtest/identity.py paper-trader/backend/app/backtest/sweep.py paper-trader/backend/app/backtest/engine.py paper-trader/backend/tests/test_backtest_admission.py paper-trader/backend/tests/test_backtest_cache.py paper-trader/backend/tests/test_backtest_fill_timing.py
git commit -m "feat(backtest): bind results and cache reuse to causal admission"
```

### Task 10: Promotion, shadow, paper, and deployment authority

**Files:**
- Modify: `paper-trader/backend/app/core/research_read.py`
- Modify: `paper-trader/backend/app/core/shadow_deployments.py`
- Modify: `paper-trader/backend/app/core/paper_authority.py`
- Modify: `paper-trader/backend/app/core/deploy_bridge.py`
- Modify: `paper-trader/backend/app/core/deployments.py`
- Modify: `paper-trader/backend/app/api/ir_experiment_routes.py`
- Test: `paper-trader/backend/tests/test_shadow_deployments.py`
- Test: `paper-trader/backend/tests/test_paper_authority_runtime.py`
- Test: `paper-trader/backend/tests/test_portfolio_promotions.py`
- Test: `paper-trader/backend/tests/test_strategy_admission_authority.py`

**Interfaces:**
- Promotion decisions and deployment requests carry `admission_address`.
- Shadow/paper stage stores the address; activate/resume verify graph, research evidence, and local receipt.
- `DeployRequest.admission_address: str` is mandatory for non-legacy deployment.

- [ ] **Step 1: Write failing mismatch and bypass tests**

```python
def test_shadow_refuses_evidence_for_same_graph_with_other_admission(session, staged):
    staged.admission_address = ADDRESS_A
    research_decision(admission_address=ADDRESS_B)
    with pytest.raises(EvidenceUnverified, match="admission"):
        activate(session, staged.id, revision=0, owner_id=OWNER,
                 broker_account_id=ACCOUNT)

def test_resume_rechecks_stale_receipt(session, paused):
    replace_registered_helper()
    with pytest.raises(NotAdmissible, match="RECEIPT_STALE"):
        resume(session, paused.id, revision=paused.revision,
               owner_id=OWNER, broker_account_id=ACCOUNT)

def test_shadow_refuses_evidence_with_different_graph_address(session, staged):
    research_decision(content_address=OTHER_GRAPH_ADDRESS,
                      admission_address=staged.admission_address)
    with pytest.raises(EvidenceUnverified, match="content"):
        activate(session, staged.id, revision=0, owner_id=OWNER,
                 broker_account_id=ACCOUNT)
```

Add explicit missing-address, forged-address, graph-address mismatch, candidate/run mismatch, and
cross-owner cases for both shadow and paper. Add separate kills for promotion approval, shadow
activate, shadow resume, paper activate, paper resume, deploy bridge, and deployment strategy write.
Each mutation removes only its named check and its matching test must fail while all other gates
remain intact.

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_shadow_deployments.py tests/test_paper_authority_runtime.py tests/test_portfolio_promotions.py tests/test_strategy_admission_authority.py`

Expected: new assertions fail because the complete receipt is not wired.

- [ ] **Step 3: Bind promotion to experiment admission**

`decide_project_candidate` permits approval only when candidate, run, graph provenance, and
owner-scoped receipt have the same non-null address and `verify_admission` succeeds. Git SHA remains
recorded provenance. Return `ADMISSION_REQUIRED` or `RECEIPT_STALE`, never a generic approval.

- [ ] **Step 4: Replace warmup-only shadow/paper admission**

Replace `_admission_for` with full receipt verification plus the existing instrument-history
admission. Store `row.admission_address` at stage. At activate/resume require:

```python
approved_address == row.graph_content_address
decision["admission_address"] == row.admission_address
local_artifact.admission_address == row.admission_address
verify_admission(artifact=local_artifact, owner_id=row.owner_id,
                 source_input=IRGraphAdmissionInput(graph, parameters, risk_model),
                 registry=REGISTRY)
```

Do not require the research database during runtime reload after activation; use the local verified
receipt. New activation/resume still verifies research approval.

Apply the graph-address equality explicitly to `shadow_deployments._require_evidence`; do not rely
on identifier/version. Keep the existing paper equality and add the same admission equality to
both paths.

- [ ] **Step 5: Require receipt in deployment bridges**

Add address to `DeployRequest`, `Deployment`, and all binding writes. Reject absent/null for new
deployments. `deploy_bridge` converts watchlist selection into a canonical receipt-bearing
deployment. `instrument_state`, watchlist lifecycle, and graph current-version pointers cannot
grant authority alone. Generated Python registrations become history/read compatibility only; new
generated work runs its mechanically lowered admitted IR. Unknown fallback is retired. The default
route goes through `ensure_legacy_deployment`, which pins the admitted expanding-z equivalent and
receipt; otherwise it remains quarantined.

Update `BINDING_MECHANISMS` and add a source-inventory test that scans every strategy-bearing model
column and resolver. Any new source without an explicit canonical/rerouted/retired disposition
fails.

- [ ] **Step 6: Run authority suites**

Run: `cd paper-trader/backend && pytest -q tests/test_shadow_deployments.py tests/test_paper_authority_runtime.py tests/test_portfolio_promotions.py tests/test_strategy_admission_authority.py tests/test_execution_binding.py`

Expected: PASS; every bypass mutant is killed.

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/core/research_read.py paper-trader/backend/app/core/shadow_deployments.py paper-trader/backend/app/core/paper_authority.py paper-trader/backend/app/core/deploy_bridge.py paper-trader/backend/app/core/deployments.py paper-trader/backend/app/api/ir_experiment_routes.py paper-trader/backend/tests/test_shadow_deployments.py paper-trader/backend/tests/test_paper_authority_runtime.py paper-trader/backend/tests/test_portfolio_promotions.py paper-trader/backend/tests/test_strategy_admission_authority.py
git commit -m "feat(strategy): enforce admission through promotion and deployment"
```

### Task 11: Execution binding, immutable attribution, and legacy quarantine

**Files:**
- Modify: `paper-trader/backend/app/core/execution_binding.py`
- Modify: `paper-trader/backend/app/engine/execution_lifecycle.py`
- Modify: `paper-trader/backend/app/engine/runner.py`
- Modify: `paper-trader/backend/app/engine/live_broker.py`
- Modify: `paper-trader/backend/app/engine/broker.py`
- Create: `paper-trader/backend/scripts/backfill_strategy_admissions.py`
- Test: `paper-trader/backend/tests/test_execution_binding.py`
- Test: `paper-trader/backend/tests/test_execution_admission_attribution.py`
- Test: `paper-trader/backend/tests/test_strategy_admission_backfill.py`
- Test: `paper-trader/backend/tests/test_execution_lifecycle_recovery.py`
- Test: `paper-trader/backend/tests/test_adopt_pending_wiring.py`

**Interfaces:**
- `ExecutionBinding.admission_address: str | None`.
- `strategy_for_execution(binding, *, admission_loader) -> Strategy` verifies current receipt.
- `NewExecutionIntent.admission_address: str` is required; the existing `ExecutionLifecycleStore.create_intent(request, context, now)` persists it.
- Backfill CLI supports `--dry-run-json PATH` and `--apply` as mutually exclusive modes.

- [ ] **Step 1: Write failing binding, attribution, and recovery tests**

```python
def test_binding_without_receipt_cannot_open_exposure(binding):
    binding = replace(binding, admission_address=None)
    with pytest.raises(AuthorityNotGranted, match="ADMISSION_REQUIRED"):
        strategy_for_execution(binding, admission_loader=loader)

def test_entry_intent_copies_admission_address(lifecycle, binding):
    request = dataclasses.replace(VALID_INTENT_REQUEST,
                                  admission_address=binding.admission_address)
    intent = lifecycle.create_intent(request, {}, NOW)
    assert intent.admission_address == binding.admission_address

def test_legacy_position_can_exit_while_new_entry_is_blocked(legacy_position, runner):
    runner.process_exit(legacy_position)
    assert legacy_position.closed_at is not None
    assert runner.try_entry(legacy_position.instrument_key).code == "ADMISSION_REQUIRED"

def test_late_fill_copies_original_intent_receipt(live_broker, admitted_intent):
    position = live_broker.adopt_fill_for(admitted_intent.client_intent_id)
    assert position.admission_address == admitted_intent.admission_address
```

Add separate mutations and tests for execution binding, live-intent creation, paper position
creation, late-fill adoption, and trade attribution. Removing one seam must not be caught only by an
earlier seam; construct the test at that seam with an otherwise valid receipt-bearing input and
assert the missing propagation or refusal directly.

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_execution_binding.py tests/test_execution_admission_attribution.py tests/test_execution_lifecycle_recovery.py`

Expected: admission-specific tests fail.

- [ ] **Step 3: Verify at the last pre-exposure boundary**

After existing source/mode/authority checks, `strategy_for_execution` loads the receipt under
`binding.owner_id`, checks its address, graph/adapter identity, and current registry. `runner` calls
this before signal-driven entry creation and returns the admitted `IRGraphStrategy` runtime for new
exposure, including the expanding-z handwritten adapter. Exit, protection, reconciliation, and
recovery paths do not call the admission gate.

- [ ] **Step 4: Propagate immutable attribution**

Require `admission_address` in `NewExecutionIntent`; `live_broker.py::_execute_entry` takes it from
the canonical binding, not a strategy key lookup. Thread the receipt through every options, equity,
futures, reinforcement, and manual-open method in `broker.py`. All `Position(...)` constructors
require it or copy the exact intent. All `Trade(...)` constructors copy the source position/intent.
Late-fill adoption reloads the original intent; journal/lifecycle recovery preserves its receipt.
Never consult current deployment state to attribute an old fill. Refuse overwriting a non-null
address. API/read models expose it.

- [ ] **Step 5: Implement exact dry-run-first backfill**

```python
def classify(row, *, owner_id, graph, parameters, risk_model,
             registry) -> BackfillDecision:
    source_input = IRGraphAdmissionInput(
        graph=graph, parameters=parameters, risk_model=risk_model)
    decision = admit_strategy(owner_id=owner_id,
                              source_input=source_input,
                              registry=registry)
    if decision.artifact is None:
        return BackfillDecision("quarantined", None, decision.refusal_code.value)
    if row.graph_content_address != decision.artifact.graph_address:
        return BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
    return BackfillDecision("exact", decision.artifact.admission_address, "")
```

Dry run emits counts and row identities without writing. `--apply` writes the immutable receipt and
fills a dependent row only when every exact field matches. Never infer from `admission_ok`, key,
version, or approval alone. Add explicit adapters: `expanding_z_v4` points to its proven IR graph;
`trend_impulse_v3` returns `LEGACY_UNADMITTED`.

Implement and test one predicate per consumer: graph version; backtest run; backtest result;
deployment; shadow deployment; paper deployment; execution intent; position; trade. Use the exact
predicate table in design §9.3. For each, add a positive exact case and one missing historical fact
that remains quarantined. In particular, current deployment state never proves a historical intent,
position, or trade.

- [ ] **Step 6: Run execution/backfill tests**

Run: `cd paper-trader/backend && pytest -q tests/test_execution_binding.py tests/test_execution_admission_attribution.py tests/test_strategy_admission_backfill.py tests/test_execution_lifecycle_recovery.py tests/test_adopt_pending_wiring.py tests/test_handwritten_strategy_causality.py tests/test_ir_strategy_parity.py`

Expected: PASS; expanding-z admits, trend-impulse is explicitly quarantined, existing exits work.

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/core/execution_binding.py paper-trader/backend/app/engine/execution_lifecycle.py paper-trader/backend/app/engine/runner.py paper-trader/backend/app/engine/live_broker.py paper-trader/backend/app/engine/broker.py paper-trader/backend/scripts/backfill_strategy_admissions.py paper-trader/backend/tests/test_execution_binding.py paper-trader/backend/tests/test_execution_admission_attribution.py paper-trader/backend/tests/test_strategy_admission_backfill.py paper-trader/backend/tests/test_execution_lifecycle_recovery.py paper-trader/backend/tests/test_adopt_pending_wiring.py
git commit -m "feat(execution): require causal receipts for new exposure"
```

### Task 12: Phase 3 mutation gate, operations record, and full closure

**Files:**
- Create: `paper-trader/backend/scripts/phase3_causal_gate.py`
- Create: `paper-trader/docs/operations/strategy-admission.md`
- Create: `paper-trader/docs/reports/2026-08-13-phase3-causal-strategy-contract.md`
- Modify: `paper-trader/docs/ROADMAP.md`
- Modify: `paper-trader/docs/CONTINUE.md`
- Test: `paper-trader/backend/tests/test_phase3_causal_gate.py`

**Interfaces:**
- `phase3_causal_gate.py --json PATH` runs contract, parity, authority, ownership, stale-receipt,
  Composition, next-bar, and mutation gates and writes exact command evidence.

- [ ] **Step 1: Write a failing gate-manifest test**

```python
REQUIRED_KILLS = {
    "negative_shift", "centered_window", "bfill", "future_join",
    "global_normalize", "missing_declaration", "stale_actual_expanding_z_helper",
    "omit_node_socket", "add_ghost_socket", "bypass_root_provenance",
    "forged_receipt", "cross_owner_receipt", "same_bar_fill",
    "bypass_editor_publish", "bypass_research_enqueue", "bypass_research_worker",
    "bypass_backtest_enqueue", "bypass_backtest_worker", "bypass_promotion_approval",
    "bypass_shadow_activate", "bypass_shadow_resume", "bypass_paper_activate",
    "bypass_paper_resume", "bypass_deploy_bridge", "bypass_deployment_write",
    "bypass_execution_binding", "bypass_live_intent", "bypass_paper_position",
    "bypass_late_fill_adoption", "bypass_trade_attribution",
}

def test_gate_reports_every_required_mutation(tmp_path):
    report = run_gate(tmp_path / "gate.json")
    assert set(report["mutations"]) == REQUIRED_KILLS
    assert all(item["killed"] for item in report["mutations"].values())
```

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_phase3_causal_gate.py`

Expected: FAIL because the gate does not exist.

- [ ] **Step 3: Implement the bounded gate**

Use `subprocess.run` with explicit argument arrays and timeouts. Record command, exit code, duration,
test counts, schema heads, and mutation results. Refuse success if a required command was skipped,
timed out, or produced no tests. Do not claim managed production or Phase 5 performance.

- [ ] **Step 4: Run focused SQLite closure**

Run: `cd paper-trader/backend && pytest -q tests/test_ir_causal_contract.py tests/test_ir_implementation_identity.py tests/test_strategy_admission.py tests/test_ir_streaming_reference.py tests/test_causal_admission_mutations.py tests/test_strategy_admission_repository.py tests/test_ir_edit_routes.py tests/test_backtest_admission.py tests/test_strategy_admission_authority.py tests/test_execution_admission_attribution.py tests/test_strategy_admission_backfill.py research_tests/test_composition_ir.py research_tests/test_strategy_admissions.py research_tests/test_graph_experiment.py`

Expected: PASS with nonzero collected tests and no unexpected warnings.

- [ ] **Step 5: Run live PostgreSQL closure**

Run: `cd paper-trader/backend && PT_TEST_POSTGRES_URL="$PT_TEST_POSTGRES_URL" pytest -q tests/test_postgres_execution_schema.py tests/test_postgres_plane_schemas.py tests/test_strategy_admission_repository.py research_tests/test_postgres_operation_concurrency.py research_tests/test_strategy_admissions.py`

Expected: PASS; execution head `0034`, research head `0005`.

- [ ] **Step 6: Run mutation and full regression gates**

Run: `cd paper-trader/backend && python scripts/causal_admission_mutations.py --json`

Expected: all named causal mutants killed.

Run: `cd paper-trader/backend && python scripts/phase3_causal_gate.py --json ../docs/reports/phase3-causal-gate.json`

Expected: exit 0; every required mutation killed and every required suite executed.

Run: `cd paper-trader/backend && pytest -q tests research_tests`

Expected: PASS except explicitly environment-skipped tests; record exact counts.

- [ ] **Step 7: Run protected-file and diff checks**

Run: `git diff --check && git status --short && git diff --name-only 9b8b0f7 -- paper-trader/backend/app/engine/kite_venue.py paper-trader/backend/app/engine/venue.py paper-trader/backend/app/providers/brokers.py paper-trader/backend/tests/test_broker_registry.py`

Expected: `git diff --check` is silent; only the pre-existing protected modifications remain and
their hashes match the worktree baseline recorded before Phase 3.

- [ ] **Step 8: Write truthful operations and evidence documents**

Document receipt lookup, refusal codes, quarantine inspection, dry-run/apply backfill, stale-helper
re-admission, rollback, and the fact that risk-reducing exits remain available. In the report paste
exact test counts and command outputs. Mark Phase 3 complete in `ROADMAP.md` only if every acceptance
item in the design has direct evidence; otherwise leave it partial and list the failed gate.

- [ ] **Step 9: Commit**

```bash
git add paper-trader/backend/scripts/phase3_causal_gate.py paper-trader/backend/tests/test_phase3_causal_gate.py paper-trader/docs/operations/strategy-admission.md paper-trader/docs/reports/2026-08-13-phase3-causal-strategy-contract.md paper-trader/docs/reports/phase3-causal-gate.json paper-trader/docs/ROADMAP.md paper-trader/docs/CONTINUE.md
git commit -m "docs(strategy): record Phase 3 causal admission evidence"
```

## Final rejection-before-acceptance review

Before accepting the phase, a reviewer must independently trace one admitted graph and one refused
graph through publication, research, backtest, promotion, paper activation, binding, and intent.
For each hop, compare owner, graph address, admission address, implementation address, and suite
version. Search for all writes to `strategy_key`, `strategy_version`, `graph_content_address`, and
`admission_address`; any new-exposure path that can omit the receipt keeps Phase 3 open.

Do not spend another review loop on cosmetic DDL reflection or exotic interrupted SQLite recovery
unless it can falsify causality, ownership, authentication, money safety, irreversible data loss,
or execution state.
