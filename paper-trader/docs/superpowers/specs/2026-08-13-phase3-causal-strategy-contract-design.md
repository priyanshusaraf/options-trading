# Phase 3 Causal Strategy Contract Design

**Date:** 2026-08-13

**Branch:** `codex/execution-foundation`

**Starting commit:** `9b8b0f7a639b9b687089f7ba7e5a1ec4dde502ba`

**Decision rule:** reject an execution claim until the exact strategy artefact, causal declarations, implementation identities, and streaming parity evidence agree.

## 1. Outcome

Phase 3 makes one immutable admitted strategy artefact the prerequisite for research evidence,
backtests, promotion, shadow evaluation, paper authority, deployment, and execution attribution.
An admitted artefact proves that a closed Component IR v1 graph resolved only to registered pure
kernels with complete causal declarations, and that an independent prefix-only reference produced
the same canonical decisions as the vectorised runtime on the versioned adversarial suite.

The phase does not claim that arbitrary Python is causal. User-created strategies enter through
Component IR. A `Composition` becomes a Component IR graph mechanically. Generated Python remains
human-readable diagnostic output and has no authority. A handwritten strategy can enter only as an
adapter whose declared IR equivalent and parity evidence are part of the admission artefact.

This is a **causal admission** receipt, not complete Strategy Preflight. It is an additional
necessary guard at every named boundary and is never sufficient permission for live activation.
Point-in-time market truth, numeric-validity semantics, provider capabilities, named instrument
roles and deployment bindings, resource plans, execution/protection compatibility, and production
readiness remain governed by the V1 steer reconciliation and later phases.

## 2. Scope

### In scope

- Closed bounded-history and recursive-state causal metadata in one production kernel registry,
  outside the RFC 0001 serialised format.
- Exact local node-input sockets, recursively derived root-market provenance, declared context,
  bounded or causal-recursive history, completed-bar output timing, and admissible purity.
- Transitive implementation identity for every resolved kernel.
- An independent prefix-only reference evaluator and canonical decision comparison.
- Owner-scoped immutable admission artefacts with stable refusal codes.
- Mechanical `Composition` to Component IR lowering.
- Admission enforcement in editor publication, graph experiments, research search, backtest
  admission and workers, candidate approval, shadow and paper deployment, general deployment,
  execution binding, and order attribution.
- Execution migration `0034` and research migration `0005`.
- Exact legacy backfill where proof can be recomputed and quarantine everywhere else.
- Mutation gates for causal contamination, stale evidence, ownership, authority bypass, and
  same-bar fills.

### Out of scope

- Phase 5 sweep fan-out, batching, datasets, or performance tiers.
- Phase 8 frontend redesign or novice workflow.
- Phase 9 broker adapters.
- A new IR format, Python language sandbox, general multi-series language, marketplace, billing,
  live IR authority expansion, or a rewrite of exit and sizing policy.
- Proving broker observations or arbitrary external data causal.
- The full first-party node conformance harness, closed validity-state model, point-in-time
  instrument/rulebook model, provider capability matrix, dynamic derivative selectors, subscription
  planner, or complete deployment preflight.

## 3. Governing constraints

1. `SUPPORTED_FORMAT_VERSION` remains `1`. No causal field is added to an IR artefact.
2. RFC 0001 §3 remains unchanged. Causal facts live in registry metadata because they describe an
   implementation, not authored graph bytes.
3. An admission address has the `sha256:<64 lowercase hex>` form and is scoped to one owner.
4. Admission is immutable. Re-admitting changed graph bytes, parameters, contracts, helper code,
   output mapping, or suite versions creates another address.
5. Unknown, missing, unchecked, impure, or hidden dependencies refuse admission.
6. Backtest and execution consume the same admitted graph semantics. There is no second signal
   engine for research.
7. A decision on completed bar `t` may first fill on bar `t+1`.
8. Existing rows without exact proof remain readable but cannot be activated, resumed, promoted,
   newly backtested, or used to open an order.
9. No work touches the protected broker/venue files named by the Phase 2 worktree guard.
10. An `admission_address` proves only the causal artefact described here. Existing authority
    boundaries keep every other money, account, history, and execution check; later phases add the
    remaining Strategy Preflight receipts.

## 4. Decisions and rejected alternatives

### 4.1 Registry metadata, not IR v2

`KernelSpec` gains one required `CausalContract` and one derived implementation address. The graph
continues to point to a content-addressed kernel body. This preserves IR v1 and lets the registry
reject a body whose executable implementation or declaration moved.

Adding causal fields to every component artefact was rejected. It would make implementation facts
author-controlled serialised claims and create a permanent migration burden without proving the
registered callable obeys them.

### 4.2 Proof receipt, not `causal_ok`

Admission produces canonical `AdmittedStrategyArtifact` bytes and their content address. Consumers
bind the address, then re-derive and compare the receipt at authority boundaries.

A boolean `causal_ok` was rejected. It does not identify which graph, helper code, parameter
binding, contract, or test suite was checked and becomes stale silently.

### 4.3 Independent completed-prefix and recursive-step execution, not sliced vector output

The reference evaluator independently reconstructs graph wiring and topological evaluation. A
bounded-history kernel receives only the completed prefix `0..t`. A causal-recursive kernel runs
its registered initializer once, then its registered state update and output step once per completed
bar. Timestamp context is transported as the current bar's recorded timestamp, never obtained from
the wall clock. The reference never evaluates the full frame and slices it.

Calling the vectorised runtime once and comparing slices was rejected because both sides would
share the same future-contaminated result. Treating EMA, Wilder smoothing, or RSI as a bounded
window was rejected because their state depends on the complete causal prefix even after their
warmup. Re-running their vector function on an arbitrary short window is not the same algorithm.

### 4.4 Mechanical Composition lowering, not generated Python authority

`composition_to_ir(comp)` constructs boundary inputs, one node per block reference, deterministic
boolean combiners, and the four canonical outputs in stable order. It resolves through the same
library and is admitted through the same service. `emit_source()` may still display or archive
readable Python, but no promotion or execution identity derives from it.

Keeping generated Python as an executable second representation was rejected because emitter,
AST, block, and IR semantics could drift while retaining the same strategy label.

### 4.5 Fail closed at every grant or use of authority

Editor publication refuses an unadmittable immutable version. A worker verifies the address again
before expensive execution. Activation and resume verify it again before granting authority.
Execution verifies it at binding consumption and copies it into the entry intent.

Checking only at publication was rejected. Registry code, helpers, receipts, or ownership may
change after publication; every boundary must reject stale or forged evidence.

### 4.6 Exact backfill only

The migrations add nullable columns and immutable stores. A separate backfill command loads each
owner's exact graph bytes and current registry, performs full admission, and writes only matching
addresses. It does not infer an address from a key, version number, old `admission_ok`, or evidence
status. Null means `LEGACY_UNADMITTED`.

Mass-hashing historical labels was rejected because it would convert missing proof into plausible
proof. Migration-time evaluation was rejected because Alembic must not execute strategy code.

### 4.7 One production registry record, not parallel spec/callable maps

Every executable body is transported as one immutable `KernelRegistration`. It keeps the
declaration, callable, recursive reference implementation when applicable, closed dependency
boundary, and derived implementation address together. `LIBRARY` and `IMPLEMENTATIONS` remain
read-only compatibility views derived from the records; nobody may assemble them independently.

The current split maps were rejected as an admission input because a caller could combine a new
callable with an old declaration or address. A best-effort `inspect.getsource` hash was rejected
because undeclared closure or module state could still change behavior.

### 4.8 Admitted IR executes new exposure

For a handwritten adapter, the handwritten class is a parity oracle and attribution source, not
the execution callable. After admission, new exposure executes the admitted equivalent IR graph.
This removes a permanent two-runtime choice at the money boundary. Existing legacy positions keep
their recorded runtime for risk reduction and recovery.

## 5. Causal registry contract

`app/ir/causal.py` defines closed immutable values:

```python
JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

@dataclass(frozen=True)
class BoundTerm:
    parameter: str
    multiplier: int = 1

@dataclass(frozen=True)
class HistoryBound:
    mode: Literal["bounded", "causal_recursive"]
    constant: int = 0
    terms: tuple[BoundTerm, ...] = ()

@dataclass(frozen=True)
class RecursiveStateContract:
    initializer: Callable[[Mapping[str, JSONValue]], object]
    state_type: type
    state_encoder: Callable[[object], JSONValue]
    update: Callable[[object, Mapping[str, JSONValue],
                      Mapping[str, JSONScalar], Mapping[str, JSONScalar]], object]
    step: Callable[[object, Mapping[str, JSONValue],
                    Mapping[str, JSONScalar], Mapping[str, JSONScalar]],
                   Mapping[str, JSONScalar]]

@dataclass(frozen=True)
class CausalContract:
    node_input_sockets: tuple[str, ...]
    context_inputs: tuple[Literal["bar_timestamp"], ...] = ()
    history: HistoryBound = HistoryBound(mode="bounded")
    output_delay_bars: int = 0
    input_bar: Literal["completed"] = "completed"
    purity: Literal["pure"] = "pure"
    recursive_state: RecursiveStateContract | None = None
```

`HistoryBound.bars(params)` rejects negative results, booleans, undeclared parameters, non-integral
values, and overflow above the configured history ceiling. `bounded` requires
`recursive_state is None`. `causal_recursive` requires the initializer, state type/encoder, update,
and step. The initializer
receives bound parameters only. `update` receives the prior state, parameters, current-bar local
node-input values, and current-bar declared context, and returns the next state. `step` receives that
next state and the same current-bar node-input values and returns current outputs. `state_encoder` must produce
closed JSON data used to check deterministic state. Initializer and update outputs must be exact
instances of `state_type`; the type implementation and encoder are independently identified. None may read a series,
future row, clock, broker, account, environment, filesystem, or network.

EMA, Wilder smoothing, and RSI declare `causal_recursive`; their vector implementation must match
initializer → update → step on every bar after the declared warmup. Rolling z-score, rolling
percentiles, fixed shifts, and finite lookbacks declare `bounded`. A recursive declaration never
means “unchecked state” and does not waive vector-versus-step parity.

`node_input_sockets` names the exact leaf-component input socket identifiers, not OHLCV fields. A
socket may receive a root graph series, another node's derived series, or a scalar. Admission
requires exact equality between this tuple, the component interface input sockets, and runtime
wiring. Missing and extra declarations both refuse.

Root market provenance is derived, never asserted by the kernel. Resolution traces each leaf input
socket backward through every edge, nested graph boundary, and default source to root graph inputs.
It records the sorted root set and full source path per socket. A derived output carries the union
of its inputs' provenance; scalar parameters/values carry an empty set. Cycles, unbound paths,
context masquerading as a socket, or roots absent from the graph interface refuse.

The only initial context field is `bar_timestamp`. The adapter transports each input series index value to
the reference and vector context channels and refuses a missing, non-monotonic, duplicated, or
timezone-ambiguous timestamp. A kernel declaring no timestamp context receives none. Account state,
broker state, wall clock, environment,
filesystem, network, unresolved external series, and undeclared dataframe columns are inadmissible.
`output_delay_bars` must be a non-negative integer. Phase 3 admits only `pure` kernels even though
the older cache registry still describes other impurity policies.

The production transport is:

```python
VectorKernel = Callable[
    [Mapping[str, JSONValue], Mapping[str, pd.Series], Mapping[str, pd.Series]],
    Mapping[str, pd.Series],
]

@dataclass(frozen=True)
class DependencyBoundary:
    mode: Literal["declared_objects", "defining_module"]
    objects: tuple[object, ...] = ()

@dataclass(frozen=True)
class KernelRegistration:
    body_ref: str
    spec: KernelSpec
    implementation: VectorKernel
    dependency_boundary: DependencyBoundary
    implementation_address: str

def registered_kernel(*, implementation: VectorKernel,
                      causal: CausalContract,
                      dependency_boundary: DependencyBoundary,
                      warmup: int | Callable[[Mapping[str, Any]], int] = 0,
                      cache_identity: str = "transitive",
                      cache_key: str | None = None) -> KernelRegistration
```

`registered_kernel` derives the implementation address; a caller cannot supply it. Under
`declared_objects`, it inspects closure variables, bytecode global reads, defaults, annotations,
and referenced modules. Builtins and immutable JSON scalars are canonicalized automatically. Every
other nonlocal/global/module dependency must appear in `objects`; extra declared objects also
refuse. Each declared application callable/class is recursively inspected. Under
`defining_module`, the complete implementation module file is always hashed and `objects` still
lists external application helpers and third-party modules it reads. Application helpers are
recursively closed; third-party modules bind canonical distribution name, version, and module
path. Under `declared_objects`, the function bytes and complete declared closure are hashed without
automatically widening to its whole module. Dynamic lookup through `globals`, `getattr(module, dynamic)`,
`eval`, or import inside the kernel refuses because the dependency boundary is not closed.

The registration address binds the implementation, all recursive initializer/state type and
encoder/update/step implementations, and the complete accepted dependency closure. Admission re-derives it and
rejects a stale registration. The block contributor lists the underlying block function and every
helper it uses, so changing `_smooth`, `_source`, or another helper changes the address.

`PlatformRegistry` owns `Mapping[str, KernelRegistration]`. Resolution reads the `spec` view and
runtime reads the `implementation` view from the same record. Contributor modules expose
`REGISTRATIONS` plus components/bodies; `app.ir.library.compose` builds the one registry and derives
`LIBRARY`/`IMPLEMENTATIONS` compatibility views. Production admission accepts `PlatformRegistry`,
not arbitrary separate maps.

The vector runtime calls every kernel as `(params, node_inputs, context_inputs)`. It derives the
`bar_timestamp` context series from the common validated input index and supplies it only when the
contract declares it. Kernels that declare no context receive an empty mapping. All shipped
two-argument kernels are mechanically changed to accept and ignore the third mapping; there is no
introspection fallback that sometimes calls two arguments and sometimes three.

## 5.1 App-owned contributors

Generated blocks move to `app/ir/contributors/generated_blocks.py`. That module owns the block
definitions, helper dependency boundaries, Component IR components, and registrations. Research
`blocks.py` and `ir_components.py` import and re-export these app-owned definitions; `app` never
imports `research`. `generated_blocks` is added literally to `app.ir.library.CONTRIBUTORS`, next to
`expanding_z`. Editor, research, backtest, shadow, paper, deployment, and execution all consume
`app.ir.library.REGISTRY`; no production caller composes a private library.

Before any admission is enabled, every existing kernel in
`app/ir/strategies/expanding_z.py` receives a complete registration and dependency boundary: EMA,
true range, Wilder, z-score, absolute value, adaptive threshold, scalar value, scale, drift/range
ATR, comparison, impulse, entry, and exit. EMA and Wilder use recursive-state declarations. Any
missing expanding-z registration keeps the platform registry build red.

The expanding-z contributor removes runtime imports and module-qualified helper lookup. It imports
pandas and each strategy helper statically at module load, then wrappers call those bound names.
Each wrapper uses `DependencyBoundary("defining_module", objects=(...))`: the complete wrapper
module, exact application helper callables, and pandas/numpy distribution identities enter the
address. Mutating the actual `_rma`, `zscore`, `adaptive_threshold`, `drift_score`, `range_in_atr`,
`impulse`, `directional_entry`, `displacement_lost`, or `_as_bool` helper changes the derived
address. The stale-helper test mutates one of these real imported helpers, not a dummy function.

## 5.2 Boolean composition contributor

The app-owned contributor creates and registers `logic.and` and `logic.or` before Composition
lowering is enabled. Both have exact boolean input sockets `left,right` and output `out`; clauses
with multiple blocks lower to a deterministic left-associated chain. Both are pure, bounded-zero,
completed-bar, zero-delay registrations with closed defining-module boundaries. The contributor
guard requires both component identities, body references, registrations, and implementations;
removing either makes platform registry construction and lowering tests fail. The existing grammar
invariant remains unchanged: every Composition clause contains at least one block. Parsing and
lowering both refuse an empty clause; Phase 3 adds no constant boolean component.

## 5.3 Exhaustive generated-block causal manifest

`generated_blocks.py` carries one literal `CAUSAL_MANIFEST` disposition for every `BLOCKS` entry.
A disposition is either `admitted(contract, dependencies)` or `quarantined(reason)`; it cannot be
omitted or inferred from warmup. All entries below are admitted when their stated parity proof
passes. The exhaustive initial manifest is:

```python
@dataclass(frozen=True)
class BlockCausalDisposition:
    status: Literal["admitted", "quarantined"]
    contract: CausalContract | None
    quarantine_reason: str | None
```

`admitted` requires a contract and no reason. `quarantined` requires a non-empty stable reason and
no contract or registration. Construction rejects every other combination.

| Blocks | Mode and state/history |
|---|---|
| `ema_slope_up`, `ema_slope_down` | `causal_recursive`: EMA state plus a parameter-sized deque of prior EMA values for `lookback`. |
| `price_above_ema`, `price_below_ema` | `causal_recursive`: EMA state parameterized by `length`. |
| `zscore_gt`, `zscore_lt` | `causal_recursive`: recursive `adjust=False` EMA plus a `length` close deque for population standard deviation. |
| `zscore_cross_up`, `zscore_cross_down` | `causal_recursive`: the same EMA/window state plus the prior computed z-score needed for the crossing test. |
| `roc_gt`, `roc_lt` | `bounded`: `length+1` closes. |
| `atr_pct_lt`, `range_atr_lt` | `causal_recursive`: previous close, Wilder ATR state parameterized by `length`, and current high/low/close. |
| `still_expanding_z` | `causal_recursive`: the same EMA/window state plus one prior absolute z-score for the current-versus-prior comparison. |
| `rsi_gt`, `rsi_lt` | `causal_recursive`: the `source` choice derives current price; state selected by the `smooth` parameter covers SMA deque, EMA accumulator, Wilder accumulator, or Hull WMA deques; length is bound. Every choice passes the same vector-versus-step suite. |
| `volume_surge` | `bounded`: `length` volume values. |
| `gap_up_pct`, `gap_down_pct` | `bounded`: prior close plus current open. |
| `body_frac_gt` | `bounded`: current open/high/low/close only. |
| `time_of_day` | `bounded-zero`: current `bar_timestamp` context only; `close` remains its declared alignment socket. |
| `opening_range_break_up`, `opening_range_break_down` | `causal_recursive`: session date, within-session position, first `bars` high/low extrema, completion flag, current close, and current `bar_timestamp`. State resets only on a recorded session-date change. |
| `regime_is` | `causal_recursive`: efficiency-ratio close/path deque, ATR-percent true-range deque, and causal expanding-median state over observed ATR percentages. |

The regime functions and constants move from `research/regime.py` into app-owned
`generated_blocks.py` (or an app-owned helper module in the same contributor). Research imports the
app-owned functions. `regime_is` contains no runtime `research` import. Its expanding median step
stores observed historical ATR percentages in canonical sorted JSON state and computes the exact
median used by the vector implementation. If exact vector/step parity cannot be achieved, its
manifest disposition is changed to `quarantined("regime vector/step parity unavailable")` and any
Composition containing it refuses `COMPONENT_QUARANTINED`; it remains present in the exhaustive
manifest and may not receive a weaker declaration.

The manifest guard is exact:

```python
assert set(CAUSAL_MANIFEST) == set(BLOCKS)
assert set(BLOCK_DEPENDENCIES) == set(BLOCKS)
admitted = {name for name, disposition in CAUSAL_MANIFEST.items()
            if disposition.status == "admitted"}
assert set(BLOCK_REGISTRATIONS) == {
    BLOCK_COMPONENTS[name].body_ref for name in admitted
}
```

Parameterized tests execute every manifest entry at its sample parameters through vector and
bounded-prefix/recursive-step evaluation. Separate tests exercise every RSI `source × smooth`
choice, opening-range session reset, and regime expanding-median history.

## 6. Admission model

### 6.1 Stable refusal vocabulary

`AdmissionRefusalCode` is a closed string enum:

- `IR_INVALID`
- `RESOLUTION_FAILED`
- `CONTRACT_MISSING`
- `CONTRACT_INVALID`
- `COMPONENT_QUARANTINED`
- `INPUT_UNDECLARED`
- `CONTEXT_UNDECLARED`
- `EXTERNAL_SERIES_UNRESOLVED`
- `IMPURE_KERNEL`
- `IMPLEMENTATION_UNIDENTIFIED`
- `IMPLEMENTATION_STALE`
- `HISTORY_INVALID`
- `OUTPUT_DELAY_INVALID`
- `OUTPUT_MAPPING_INVALID`
- `STREAMING_DIVERGENCE`
- `VECTOR_EVALUATION_FAILED`
- `REFERENCE_EVALUATION_FAILED`
- `OWNER_SCOPE_INVALID`
- `ARTEFACT_MISMATCH`
- `RECEIPT_STALE`

Messages add detail but APIs, metrics, tests, and stored refusals use the stable code.

### 6.2 Public interfaces

```python
@dataclass(frozen=True)
class ResolvedComponentIdentity:
    node_path: str
    identifier: str
    version: int
    body_ref: str
    bound_parameters: Mapping[str, JSONValue]

@dataclass(frozen=True)
class InputProvenance:
    node_path: str
    socket: str
    root_market_inputs: tuple[str, ...]
    source_paths: tuple[tuple[str, ...], ...]

@dataclass(frozen=True)
class AdmittedKernelIdentity:
    body_ref: str
    implementation_address: str
    causal_contract: Mapping[str, JSONValue]
    evaluated_history_bars: int

@dataclass(frozen=True)
class StructuralAdmission:
    owner_id: str
    source: Literal["ir_graph", "handwritten_adapter"]
    graph_identifier: str
    graph_version: int
    graph_address: str
    resolved_components: tuple[ResolvedComponentIdentity, ...]
    input_provenance: tuple[InputProvenance, ...]
    bound_parameters: Mapping[str, JSONValue]
    kernels: tuple[AdmittedKernelIdentity, ...]
    canonical_mapping: Mapping[str, str]
    declared_warmup: int
    risk_model: Mapping[str, JSONValue] | None

@dataclass(frozen=True)
class StructuralDecision:
    structural: StructuralAdmission | None
    refusal_code: AdmissionRefusalCode | None
    detail: str

@dataclass(frozen=True)
class ParityEvidence:
    fixture_suite_address: str
    reference_decision_address: str
    vector_decision_address: str

@dataclass(frozen=True)
class IRGraphAdmissionInput:
    graph: Mapping[str, JSONValue]
    parameters: Mapping[str, JSONValue]
    risk_model: Mapping[str, JSONValue] | None

@dataclass(frozen=True)
class HandwrittenAdapterInput:
    strategy_key: str
    strategy_version: str
    adapter_implementation: object
    adapter_dependencies: DependencyBoundary
    equivalent_ir: IRGraphAdmissionInput

@dataclass(frozen=True)
class SourceEvidence:
    source: Literal["ir_graph", "handwritten_adapter"]
    strategy_key: str
    strategy_version: str
    adapter_implementation_address: str | None
    adapter_decision_address: str | None

@dataclass(frozen=True)
class AdmittedStrategyArtifact:
    scheme: Literal["strategy-admission/1"]
    owner_id: str
    source: Literal["ir_graph", "handwritten_adapter"]
    source_evidence: SourceEvidence
    graph_identifier: str
    graph_version: int
    graph_address: str
    resolved_components: tuple[ResolvedComponentIdentity, ...]
    input_provenance: tuple[InputProvenance, ...]
    bound_parameters: Mapping[str, JSONValue]
    kernels: tuple[AdmittedKernelIdentity, ...]
    canonical_mapping: Mapping[str, str]
    declared_warmup: int
    risk_model: Mapping[str, JSONValue] | None
    contract_suite: Literal["causal-contract/1"]
    parity_suite: Literal["prefix-vector-parity/1"]
    fixture_suite_address: str
    reference_decision_address: str
    vector_decision_address: str

    @property
    def admission_address(self) -> str:
        return content_address(self.to_dict())

@dataclass(frozen=True)
class AdmissionDecision:
    artifact: AdmittedStrategyArtifact | None
    refusal_code: AdmissionRefusalCode | None
    detail: str

@dataclass(frozen=True)
class CausalFixture:
    name: str
    inputs: Mapping[str, pd.Series]

@dataclass(frozen=True)
class CausalFixtureSuite:
    scheme: Literal["causal-fixtures/1"]
    fixtures: tuple[CausalFixture, ...]

    @property
    def address(self) -> str:
        return content_address(canonical_fixture_manifest(self))

def inspect_strategy(*, owner_id: str,
                     source_input: IRGraphAdmissionInput | HandwrittenAdapterInput,
                     registry: PlatformRegistry) -> StructuralDecision:
    return AdmissionService(FIXTURE_SUITES.require("causal-fixtures/1")).inspect(
        owner_id=owner_id, source_input=source_input, registry=registry)

def admit_strategy(*, owner_id: str,
                   source_input: IRGraphAdmissionInput | HandwrittenAdapterInput,
                   registry: PlatformRegistry) -> AdmissionDecision:
    return AdmissionService(FIXTURE_SUITES.require("causal-fixtures/1")).admit(
        owner_id=owner_id, source_input=source_input, registry=registry)

def verify_admission(*, artifact: AdmittedStrategyArtifact, owner_id: str,
                     source_input: IRGraphAdmissionInput | HandwrittenAdapterInput,
                     registry: PlatformRegistry) -> None:
    AdmissionService(FIXTURE_SUITES.require("causal-fixtures/1")).verify(
        artifact=artifact, owner_id=owner_id,
        source_input=source_input, registry=registry)
```

The canonical artifact includes owner identity. Identical private graph bytes owned by two users
therefore have different admission addresses and cannot disclose cross-owner existence through a
lookup. `verify_admission` recomputes all deterministic identity fields and raises a typed refusal;
it does not trust persisted JSON or a caller-supplied address. `FIXTURE_SUITES` is an immutable
app-owned registry with one literal suite identifier/address pair. Production APIs do not accept a
fixture object or suite address from a caller. A suite change requires a reviewed registry edit and
creates new admissions.

For `HandwrittenAdapterInput`, admission derives the adapter implementation address under the same
closed dependency rules, evaluates its exact `(strategy_key, strategy_version)` across the fixture
suite, admits the equivalent IR, and requires byte-identical adapter, vector-IR, and recursive/
prefix-reference decisions. All three decision addresses and the adapter identity enter
`SourceEvidence`. A forged equivalent graph, stale class version, or adapter drift refuses. The
runtime object returned for new exposure is `IRGraphStrategy(equivalent_ir, REGISTRY)`, not the
handwritten class. `expanding_z_v4` is the initial allowed adapter. `trend_impulse_v3` has no
equivalent input and remains `LEGACY_UNADMITTED`.

### 6.3 What the address binds

- canonical graph bytes and graph content address;
- graph identifier/version and exact bound parameters;
- every resolved component `(identifier, version)`, body reference, and resolved node path;
- exact node input socket declarations and recursively derived root-market source paths;
- every closed causal contract and evaluated history bound;
- every derived transitive vector and recursive initializer/state/update/step implementation address;
- for a handwritten adapter, exact strategy key/version, adapter implementation address,
  equivalent graph identity, and adapter-versus-IR decision address;
- canonical output-to-signal mapping, declared warmup, and validated risk model;
- admission, contract, and parity scheme versions;
- the adversarial fixture-suite address;
- byte-canonical decision streams from reference and vectorised execution.

Canonical decisions encode index timestamps and the four canonical boolean columns in fixed order.
NaN, dtype, timezone, or index differences refuse; comparison does not rely on pandas' permissive
coercion.

## 7. Reference and vectorised parity

`app/ir/streaming_reference.py` implements its own edge map, interface binding, topological walk,
bounded-prefix cache, and recursive state table. For each completed bar, it gives a bounded kernel
only its declared prefix. For a recursive kernel it initializes once, canonicalizes state, calls
`update` once, then calls `step` once. It transports `bar_timestamp` from that bar's series index.
It appends current output to the canonical stream and never imports `app.ir.runtime.evaluate`.

Admission compares the vector implementation of each recursive node directly with its registered
initializer/update/step stream before comparing graph decisions. This prevents downstream logic
from masking a recursive indicator divergence. It also compares state bytes across two independent
step runs to reject nondeterministic state.

The fixture suite is deterministic, app-owned, immutable, and loaded only from
`FIXTURE_SUITES.require("causal-fixtures/1")`. It contains monotonic, alternating,
constant, gapped, duplicated-value, regime-change, session-boundary, NaN-prefix, and seeded random
OHLCV frames. Prefixes cover warmup boundaries, parameter-derived history boundaries, and the full
frame. Its manifest includes exact canonical input bytes and expected timestamp context. Admission
evaluates every fixture through both runtimes and requires identical node and decision bytes.

The mutation command has two distinct classes. A callable changed after registration without a new
record must fail `IMPLEMENTATION_STALE` before evaluation. A future-reading callable freshly
registered with a newly derived address and truthful dependency closure must pass identity checks
and then fail `STREAMING_DIVERGENCE`. The freshly registered mutations cover negative shift,
centered rolling window, backward fill, future join, and global normalization. This distinction
proves identity freshness and causality independently.

## 8. Mechanical Composition lowering

`research/strategy/builder/composition_ir.py` exposes:

```python
def composition_to_ir(comp: Composition, *, identifier: str,
                      version: int = 1,
                      instrument: str = "SELF",
                      timeframe: str = "*") -> dict[str, Any]:
    return CompositionLowerer(
        identifier=identifier, version=version,
        instrument=instrument, timeframe=timeframe).lower(comp)
```

The lowerer:

`SELF` is a logical strategy role, not a physical symbol. Phase 6 owns durable role-to-instrument
deployment bindings; this lowerer never resolves a provider token or contract.

1. round-trips `Composition.to_dict()` through `Composition.from_dict()`;
2. creates boundary inputs only for the union of referenced blocks' declared inputs;
3. creates deterministic block node IDs from canonical clause, position, and block reference;
4. refuses any empty clause, wires a one-block clause directly, and creates closed `logic.and` or
   `logic.or` IR nodes for multi-block clauses instead of embedding Python;
5. wires exactly `longEntry`, `shortEntry`, `longExit`, and `shortExit` outputs;
6. carries parameter values as node overrides and no executable source;
7. validates the resulting graph as IR v1, resolves it, and returns canonical graph data.

The same composition always yields the same graph bytes for the same identifier/version. Search,
evaluation, and promotion use this graph. `emit_source()` output can be stored beside it for review
but changing that text cannot change admission or execution.

## 9. Persistence

### 9.1 Execution plane migration `20260813_0034_strategy_admissions.py`

Create `strategy_admissions` with composite primary key `(owner_id, admission_address)`, graph
identity/address columns, canonical `artifact_json`, scheme versions, and `created_at`. Add an
owner-local unique identity over `(owner_id, graph_identifier, graph_version, admission_address)`.
The table is classified `USER`. SQLite `BEFORE UPDATE/DELETE` triggers and PostgreSQL
`BEFORE UPDATE OR DELETE` trigger functions raise on direct SQL. ORM guards are additional checks,
not the immutable boundary. Tests issue direct SQL UPDATE and DELETE in both dialects and require
failure plus byte-identical retained rows.

Add nullable `String(71)` `admission_address` columns to:

- `graph_versions`;
- `backtest_runs` and `backtest_results`;
- `deployments`;
- `ir_shadow_deployments` and `ir_paper_deployments`;
- `positions`, `trades`, and `execution_intents`.

Each new authoritative write requires a same-owner `strategy_admissions` row. Cross-database
research evidence cannot use a foreign key, so activation verifies the research receipt through
the read-only bridge and records the locally verified execution-plane receipt.

### 9.2 Research plane migration `0005_strategy_admissions.py`

Create `research_strategy_admission` with composite primary key `(owner_id, admission_address)`,
canonical artifact JSON, graph identity/address, suite versions, and creation time. Make it
append-only with SQLite and PostgreSQL database triggers, proved by direct SQL tests. Add nullable
`String(71)` `admission_address` to `research_experiment_run` and
`research_promotion_candidate`.

Research never writes execution-plane admissions. Promotion carries a research receipt address;
the execution boundary recomputes and stores its own same-owner receipt before authority changes.

### 9.3 Legacy quarantine

Null admission addresses mean `LEGACY_UNADMITTED`. Read APIs expose that state. They do not invent a
receipt. New enqueue, approval, stage, activation, resume, deployment, binding, or entry-intent
writes reject it with `ADMISSION_REQUIRED`.

`scripts/backfill_strategy_admissions.py` admits exact existing graph versions owner by owner and
fills dependent rows only when their graph identifier, version, content address, owner, parameter
binding, and evidence address all match. It supports dry-run JSON output and an explicit apply
mode. Rows that cannot be proven remain unchanged and appear in a quarantine report. The initial
handwritten `expanding_z_v4` adapter may be admitted after its IR parity gate passes.
`trend_impulse_v3` remains legacy-unadmitted until it has an IR equivalent and exact parity proof.

The exact per-consumer proof predicates are:

| Consumer | Address may be filled only when |
|---|---|
| `GraphVersion` | Owner matches; canonical `artifact_json` hashes to stored graph address; current production registry admits those exact bytes and parameters. |
| `BacktestRun` | Its immutable request/provenance names the same owner, graph address, bound parameters, strategy key/version, and engine manifest as the recomputed receipt. A legacy run lacking any one field stays null. |
| `BacktestResult` | Its parent run is exact; result owner/run and recorded strategy key/version match; its execution-result manifest recomputes with the same admission address. |
| `Deployment` | Owner/account scope matches; its pinned strategy key/version and immutable graph address identify the receipt. A mutable key without pinned version/address stays null. |
| `IrShadowDeployment` | Owner, graph identifier/version/address, interval, parameters, and verified research decision all match; the decision names the same admission address. |
| `IrPaperDeployment` | The shadow predicate holds, and paper authority/evidence fields identify the same immutable graph and receipt. |
| `ExecutionIntent` | Stored owner/account, strategy key/version, graph address, parameters, and deployment receipt snapshot at `created_at` all agree. Current mutable deployment state is not historical proof. |
| `Position` | It references an exact admitted `ExecutionIntent`, or an immutable paper-open event containing the same receipt; strategy key/version agree. Merely matching the current deployment is insufficient. |
| `Trade` | Its source position or entry intent has an exact receipt and the trade copies the same owner/account, entry identity, strategy key/version, and address. Rows without a durable source stay null. |

Backfill is bounded to these predicates, SQLite/current PostgreSQL schemas, and the shipped
expanding-z equivalent. It does not prove interrupted exotic migrations or invent historical data.

## 10. End-to-end wiring

### Editor publication

`apply_and_publish` validates and admits the proposed immutable graph in the same transaction that
publishes `GraphVersion`. A refusal preserves the draft revision but does not advance
`current_version`. The API returns HTTP 422 with the stable refusal code and path/detail.

### Research and experiments

Graph experiments and Composition search admit before scheduling evaluation. The operation item
and experiment run bind `admission_address`. Workers load the owner-scoped receipt, verify it
against current graph and registry, and refuse stale work before provider access.

### Backtests

Backtest enqueue requires an admitted artifact and stores its address. The worker re-verifies it
before dataset/provider acquisition and includes it in `execution_result_address`. Results copy
the address. Cache reuse with a missing or different admission address is a cold miss.

### Promotion

A promotion candidate copies the exact experiment admission address. Approval fails if its receipt
is absent, stale, owner-mismatched, or no longer matches the experiment and graph. Git SHA remains
review provenance but is not causal proof.

### Shadow and paper

Stage records the graph and admission addresses. Activate and resume re-derive graph bytes, verify
the owner-local execution receipt, and require the approved research decision to name the same
graph address and admission semantics. This closes the present shadow path where graph/evidence
checks can agree on graph identity without binding the complete causal receipt. Specifically,
`shadow_deployments._require_evidence` gains the same nonempty
`decision.content_address == row.graph_content_address` check already present on the paper path,
then also requires decision and row admission addresses to match. Neither equality is inferred from
identifier/version.

### Deployment and execution

`ExecutionBinding` gains `admission_address`. `strategy_for_execution` rejects an absent, stale,
forged, or owner-mismatched receipt after its existing source/mode/authority checks. Successful
entry creation copies the address into `ExecutionIntent`, and derived positions/trades retain it.
Risk-reducing exits for an existing legacy position remain allowed; quarantine blocks new exposure,
not recovery or exit.

The authority inventory is closed and tested:

| Existing source | Phase 3 disposition |
|---|---|
| `deployments.strategy_key/version` | Canonical only with the deployment's admission address and immutable graph/source evidence. |
| `ir_paper_deployments` | Canonical paper authority after activation/resume verification. |
| `instrument_state.strategy_key` | Selection input only; it must resolve through an owner/account deployment receipt and cannot grant authority alone. |
| `watchlists.strategy_key` and lifecycle archive | Selection/history only. `deploy_bridge` creates or updates a receipt-bearing deployment; direct watchlist authority is retired. |
| `generated_strategies.key` and runtime registry | Read/history compatibility only. New generated work lowers to admitted IR; direct generated-Python authority is retired. |
| platform default and unknown-key fallback | Default may open only through the admitted expanding-z adapter receipt on the canonical legacy deployment. Unknown fallback is retired for new exposure. |
| graph artifact current version | Publication pointer only; never authority without an admission receipt and deployment. |

`BINDING_MECHANISMS` is updated to name these sources and a guard fails if another strategy-bearing
column or resolver appears without a disposition. `ensure_legacy_deployment` pins the admitted
expanding-z equivalent and its address. A legacy row that cannot be rerouted stays readable and
quarantined.

The producer inventory is also closed. `app/engine/live_broker.py::_execute_entry` obtains the
receipt from the canonical binding and stores it on `NewExecutionIntent`. All option, equity,
futures, reinforcement, manual-open, and partial-open `Position(...)` constructors in
`app/engine/broker.py` require a receipt argument or copy it from the exact intent. Every
`Trade(...)` constructor copies from its source position/intent. Late-fill adoption in
`LiveBroker.adopt_pending_entries` loads the original intent and copies its receipt; it never reads
the current deployment. Journal/lifecycle recovery preserves the intent receipt. Reconciliation
may close or protect a legacy position with null receipt but cannot turn it into new exposure.

## 11. Failure behavior

- Missing declaration: refuse `CONTRACT_MISSING` before evaluation.
- Missing/extra node socket or invalid root provenance: refuse `INPUT_UNDECLARED`,
  `CONTRACT_INVALID`, or `ARTEFACT_MISMATCH`; undeclared context refuses `CONTEXT_UNDECLARED`.
- Impure or external dependency: refuse before running user logic.
- Vector/reference difference: refuse `STREAMING_DIVERGENCE` and persist no admitted artefact.
- Receipt missing or stale at a worker: fail the item without provider or broker access.
- Receipt missing during activation/resume: remain staged/paused and record refusal detail.
- Receipt mismatch at execution: disarm/block the binding; existing risk reduction continues.
- Same-bar fill request: backtest refuses it; next-bar-open remains mandatory.
- Research plane unavailable during runtime reload: use the locally verified execution receipt;
  only a new authority grant needs the research bridge.

## 12. Acceptance and mutation gates

Phase 3 closes only when all of these pass:

1. Every reachable admitted kernel has a complete closed causal contract and derived transitive
   implementation identity; every executable body travels in one immutable registration.
2. EMA, Wilder, and RSI vector outputs match their initializer/state/update/step streams, state is
   deterministic, and timestamp context equals the current recorded bar index.
3. Missing declarations, hidden dataframe/context reads, impurity, unresolved external series,
   negative history, and negative output delay refuse with stable codes.
4. Every leaf contract exactly names local input sockets; nested resolution derives immutable root
   market source paths. Missing/extra socket and provenance-bypass mutations fail.
5. Reference prefix/step evaluation never imports or calls the vector evaluator.
6. All admitted graphs produce byte-identical canonical decisions across the registered fixture suite.
7. An actual expanding-z helper mutation after registration fails `IMPLEMENTATION_STALE`; freshly
   registered negative shift, centered window, backward fill, future join, and global-normalization
   implementations fail `STREAMING_DIVERGENCE`.
8. `Composition` lowering is deterministic and its IR/vector result matches current Composition
   semantics before generated Python loses authority.
9. Production `logic.and` and `logic.or` resolve as bounded-zero registered components, their
   removal makes lowering fail, and empty Composition clauses remain invalid at parse and lowering.
10. `CAUSAL_MANIFEST`, dependencies, and blocks have identical exhaustive keysets. The admitted
    subset has exactly matching components and registrations; every quarantined subset member
    refuses lowering. Every admitted block passes vector/reference parity, including RSI choices,
    opening-range session state, and regime expanding median.
11. `app.ir.library.REGISTRY` includes app-owned generated blocks and fully declared expanding-z
    kernels; no production path composes another library or imports research at runtime.
12. The expanding-z handwritten adapter matches equivalent IR, and new exposure executes admitted
   IR. Trend-impulse remains explicitly quarantined.
13. Editor, experiment, search, backtest, promotion, shadow, paper, deployment, and execution tests
   each prove a missing or forged address is rejected.
14. Stale helper code changes the admission address; a stale receipt refuses.
15. Cross-owner receipt lookup and use fail without revealing whether another owner's address exists.
16. Graph/evidence/admission mismatches fail activation and resume.
17. Individual bypass mutations are killed at editor publish, research enqueue, research worker,
    backtest enqueue, backtest worker, promotion approval, shadow activate, shadow resume, paper
    activate, paper resume, deploy bridge, deployment strategy write, execution binding, live intent
    creation, paper position creation, late-fill adoption, and trade attribution. One aggregate
    bypass test cannot satisfy this gate.
18. Backtest decisions on bar `t` cannot fill before `t+1`; a same-bar mutation fails.
19. Execution migration head is `0034`; research migration head is `0005`; SQLite and live
    PostgreSQL upgrade/current-schema tests agree on the new constraints, and direct SQL cannot
    update or delete either admission table.
20. Legacy-unadmitted rows remain readable, cannot open new exposure, and can still exit or recover.
21. `expanding_z_v4` adapter admission passes. `trend_impulse_v3` is reported as quarantined, not
    silently admitted.

## 13. Completion evidence

The implementation report must record exact commands and results for focused unit tests, both
database dialects, cross-owner tests, the mutation command, Composition parity, full backend and
research suites, and the next-bar-open invariant. A green ordinary suite without mutation kills is
not Phase 3 evidence.
