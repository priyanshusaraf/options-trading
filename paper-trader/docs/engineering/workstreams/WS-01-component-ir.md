# WS-01 — Component IR

**Status:** active
**Owner surface:** `backend/app/ir/` (`schema.py`, `validate.py`, `resolve.py`, `kernels.py`,
`runtime.py`, `experiment.py`, `hashing.py`, `authoring.py`, `view.py`, `edit.py`,
`strategies/expanding_z.py`) · `backend/tests/test_ir_*.py` ·
`backend/scripts/render_ir_graph.py` · `docs/rfcs/0001-component-ir.md`
**Last verified:** 2026-08-03 · commit `cdbe686`

> The Component IR is a small language for saying what a trading strategy *is*, separately from
> any code that runs it. A strategy is written as a graph: typed components with declared
> interfaces, wired socket to socket, with parameters bound at each node. A **resolver** turns
> that specification into a fully bound `ResolvedGraph`; a **runtime** evaluates that graph into
> pandas series. The point is that one written artefact can then be validated, versioned,
> content-addressed, drawn, mutated by a search process, and bound to the experiment that
> measured it — instead of each of those subsystems inventing its own private notion of what a
> strategy is. The language is defined by RFC 0001, which is normative; this workstream is the
> implementation of that RFC and nothing else.

---

## 1. Vision

Done looks like this: every clause of RFC 0001 is enforced by a mechanism rather than asserted by
a docstring, and every subsystem that has an opinion about strategies — the editor, the research
proposer, the experiment record, eventually the live engine — speaks this one format, so that
"add a capability" means "express it in the IR or amend the IR", with no third path (RFC §6.2).

The concrete end state for WS-01 specifically:

- A strategy the platform actually trades is expressible, and is proven bar-for-bar equal to the
  hand-written implementation it replaces. (Reached: `expanding_z_v4`.)
- Resolution is a pure function of `(specification, library)` — one resolution shared by research
  and live (C12), no clock, no counter, no plane flag — so the same artefact resolves identically
  everywhere and forever.
- Lookahead, warmup and cache identity are properties the *language* guarantees, not habits an
  author has to remember. A component that reads the future is caught by a check, not by review.
- A result can never outlive the versions that produced it: every experiment and finding carries
  a binding derived from the resolved graph (F14).

What this is worth: the codebase's defining defect is mechanisms that are correct and wired to
nothing. A format nothing evaluates is exactly that shape, which is why each phase here shipped
its consumer alongside it — the resolver with a runtime, the runtime with a real strategy, the
editor's read half with the write half. The remaining, deliberately unbuilt consumer is the live
engine (§8).

## 2. Scope

**In scope.**

- The format itself: RFC 0001 §3, clauses F1–F14 — the artefact grammar, component identity and
  versioning, declared interfaces, wire types, overrides, nesting, grouping, presentation state,
  result binding.
- Resolution: §4 clauses C1–C15 — determinism, purity, provenance preservation, instance
  identifiers, warmup composition, cache identity, lookahead prevention, the searcher boundary,
  subgraph/component equivalence.
- The kernel registry (`kernels.py`): where a leaf implementation declares warmup, purity and
  cache identity, keyed by content address.
- The runtime (`runtime.py`): evaluation of a `ResolvedGraph`, memoisation, and the causality
  check.
- The experiment/finding binding (`experiment.py`) — the *record type and its validation*, not
  the running of experiments.
- Content addressing (`hashing.py`).
- Python component authoring (`authoring.py`).
- `strategies/expanding_z.py` — the reference artefact, and the parity proof against the shipped
  strategy.

**Out of scope.**

- **The visual editor UI** — routes, React, drag-and-drop, undo stack: **WS-04 Editor**. Note the
  split precisely: `app/ir/view.py` (`graph_view`, `to_svg`, `Layout`) and `app/ir/edit.py` (the
  mutation functions) are **libraries owned by WS-01 and consumed by WS-04**. WS-04 may depend on
  their signatures; it may not fork them or reimplement graph mutation, because a second
  implementation of §3 is the defect C12 exists to prevent.
- **The research plane's use of the IR** — the 23-block component library
  (`research/strategy/builder/ir_components.py`), the structure proposer
  (`research/strategy/builder/propose.py`), and binding research runs through
  `experiment.py`: **WS-03 Research Plane**. WS-01 owns the language those consume; the direction
  of dependency is fixed — `research/` imports `app.ir`, never the reverse.
- **Adoption by the live engine** — the engine still calls `Strategy.compute()`. Making a real
  trading path evaluate an IR graph is RFC 0001 Appendix C(d), belongs to **WS-02 Execution &
  Brokers**, and is owner-blocked (§8).
- Marketplace, distribution and sandboxing of third-party components (RFC Appendix C(f)).

## 3. Interfaces

**Exports.** Anything not listed here is internal to `app/ir/` and may change without notice
(everything prefixed `_`, and the whole of `schema.py` beyond the predicates named below).

| Export | Guarantee |
|---|---|
| `validate.validate(artefact, library=None) -> list[Violation]` | Returns every §3 violation in document order, or `[]`. Without a `library`, F7 and F8 are *not* checked — see `unchecked_clauses()`. Never raises on malformed input; a non-mapping is reported as an F1 violation. |
| `validate.Violation(clause, path, message)` | A frozen record naming the clause (`"F7"`) and the JSON path (`"$.edges[1].domain.timeframe"`). Callers may match on `clause` and `path`; `message` is prose and may change. |
| `validate.clauses_violated(artefact, library=None) -> set[str]` | The set of clause names violated. Convenience over `validate`. |
| `validate.unchecked_clauses(library=None) -> set[str]` | Clauses this run could not check and therefore did **not** pass. An unchecked clause is never silently reported as passing. |
| `validate.ENFORCED_CLAUSES` / `ELSEWHERE_ENFORCED_CLAUSES` / `UNENFORCEABLE_CLAUSES` / `LIBRARY_DEPENDENT_CLAUSES` | The bookkeeping of which clause is enforced where. Every clause F1–F14 is in exactly one category; a test asserts nothing is simply absent. `UNENFORCEABLE_CLAUSES` is currently empty. |
| `resolve.resolve(spec, library, parameters=None) -> ResolvedGraph` | The **single** resolution (C12). A deterministic, side-effect-free function of `(spec, library, parameters)`: no clock, counter, random, environment or file read. Does not mutate `spec`. Raises `ResolutionError(clause, path, message)` with the path in the *authored* vocabulary (C4). |
| `resolve.Library(components, bodies, kernels)` | Everything resolution is allowed to read: components by `(identifier, version)`, graph bodies by content address, `KernelSpec`s by content address. Frozen. |
| `resolve.ResolvedGraph` | Frozen. `identifier`, `version`, `nodes`, `edges`, `versions` (every resolved component version, C5), `inputs`, `outputs`; `.warmup` composes the deepest chain (C10); `.node(instance_id)`. Constructed in exactly one place in the tree — a guard test fails on a second construction (C12). |
| `resolve.ResolvedNode` | Frozen leaf: `instance_id` (the instance path joined by `/`), `path`/`definition` as C4 back-references, `body_ref`, bound `params`, `domain`, `warmup`, `purity`, `cache_id`, `derived_from`; `.authored_root`. |
| `resolve.ResolvedEdge` | Frozen: `source`/`target` as `(instance_id, socket)`, `declared_in`, `derived`. |
| `resolve.topological_order(ids, edges) -> list[str]` | A stable evaluation order; raises on a cycle. Used by the runtime and by the view so both agree on order. |
| `resolve.publish(graph) -> component_def` and `resolve.body_for(graph) -> (address, body)` | C15: publishing a subgraph as a component is mechanical and has no options. `body_for` gives the `Library.bodies` entry that `publish`'s reference points at. |
| `resolve.BOUNDARY_INPUT` / `BOUNDARY_OUTPUT` (`"graph.input"` / `"graph.output"`) | Reserved component **identifiers** a body graph uses to attach its interface to internal nodes. Resolution elides them: no `ResolvedGraph` ever contains one. They are values, not grammar — §3 is untouched (RFC §6.3). |
| `kernels.kernel_spec(**fields) -> KernelSpec` | Builds a declaration from a **closed** field set (`warmup`, `purity`, `cache_identity`, `cache_key`). An unknown field raises `KernelDeclarationError("C9", …)` — an open field set is C9's escape hatch waiting to happen. |
| `kernels.KernelSpec` | `warmup` may be an `int` or a callable of the node's bound parameters (`warmup_for(params)`); `purity` is `PURE` or one of `IMPURITY_POLICIES`; `cache_identity` is `transitive` or `declared` (and `declared` must carry a `cache_key`). |
| `kernels.kernel_registry(entries) -> dict[str, KernelSpec]` | A content-address → spec registry, every entry validated at construction. |
| `kernels.check_warmup(warmup, where)` | C11: warmup is a non-negative integer of bars. A negative warmup is a read of the future. |
| `runtime.evaluate(graph, inputs, implementations, cache=None) -> EvaluationResult` | Evaluates a resolved graph over one series per declared graph input. A kernel is found **only** by its body's content address (C13); an unregistered address raises rather than falling back. Raises `EvaluationError(clause, instance_id, message)`. |
| `runtime.EvaluationResult` | `outputs` (declared graph outputs), `values` (every node, every socket), `warmup`, `cache_hits`; `.settled()` drops the unwarmed prefix, so reading an unwarmed indicator stops being the caller's job to remember (C10). |
| `runtime.Cache` | C8 memoisation keyed on the identity resolution computed. A node whose kernel declares an impurity is never memoised. Passing a shared `Cache` across evaluations is how a parameter sweep gets cheap without the sweep living inside the component (C14). |
| `runtime.check_causality(graph, inputs, implementations, prefixes=None)` | Raises `EvaluationError("C11", …)` unless every value is a function of the bars up to and including it. Compares **every node's every socket** on a prefix against the full run — not just the outputs, because a forward read can cancel downstream. Scalars are compared whole. |
| `experiment.record(experiment_id, graph, inputs, result) -> ExperimentRecord` | F14. The binding is **derived** from the `ResolvedGraph` — there is deliberately no parameter for passing versions in. Records graph version, every component version, every node's cache identity, and a data digest. |
| `experiment.conclude(finding_id, experiment, claim) -> Finding` | A finding carries its experiment's binding, so a claim that outlived a re-parameterised run is detectable. |
| `experiment.validate_experiment(record, graph=None) -> list[Violation]` | Structural check without `graph`; with `graph`, checks the binding is *correct*, not merely present. F14's failure mode is a stale field. |
| `experiment.validate_finding(finding, experiment=None) -> list[Violation]` | Same shape for findings. |
| `experiment.data_digest(inputs) -> str` | Content address of the bars a run used, hashed by value in name order — the same data through a different loader digests the same. |
| `hashing.content_address(value) -> "sha256:<64 hex>"` | The address of a value, not of how it was written. |
| `hashing.canonical_json(value) -> str` | Byte-stable rendering: sorted keys, no spaces, no NaN. Reformatting an artefact must never change its address. |
| `authoring.component(identifier, *, interface, …)` | Decorator returning an `AuthoredComponent`. The interface is **declared** and the function checked against it, never inferred (F4). A kernel that ignores a declared input, or reads one it never declared, is refused at import. Body address is the source's content address; `closes_over=` must be supplied by a factory-built kernel or every sibling shares one address. |
| `authoring.library(components, extra=None) -> (Library, implementations)` | The `(Library, implementations)` pair the resolver and runtime want, keyed by body address only (C13). Refuses two components sharing one body address while declaring different kernels; sharing an address with an identical declaration (an alias) stays legal. |
| `authoring.socket()` / `parameter()` / `panel()` / `wire()` | Interface-item constructors. Produce plain dicts that `validate()` accepts. |
| `authoring.AuthoredComponent` | `definition`, `spec`, `kernel`, `.key`, `.body_ref`, and `unchecked` — which parts of the interface check could not be verified because the kernel reaches inputs/params dynamically. Reports *unchecked*, never *passed*. |
| `view.graph_view(graph, layout=None) -> GraphView` | A view model derived from dependency structure alone. Labels use the authored vocabulary (C4): `n_atr/n_smooth` is *n_smooth* in *n_atr*. Layering is a pure function of the graph, so reordering the specification never moves a node between layers. |
| `view.to_svg(view) -> str` | A self-contained SVG: no external stylesheet, script or font. Text is truncated to its box — SVG text does not clip, so spill is silent. |
| `view.Layout(positions)` | F13's presentation state: sparse, keyed by `instance_id`, living **beside** the graph. Arranging nodes cannot change the artefact's content address or any downstream cache identity. |
| `edit.add_node` / `remove_node` / `set_override` / `clear_override` / `connect` / `disconnect` / `group` / `rename` | Every edit returns a **new** artefact and mutates nothing (C2's discipline applied to editing), addresses nodes by instance identifier and never by display name (F2), and validates its result before returning — an edit whose result would violate §3 raises `EditRejected` naming the clause instead of returning something a caller could persist. `remove_node` drops the node, its edges and its group membership in one operation, so no invalid intermediate state exists. |
| `edit.EditRejected` | Carries `action` and the `violations` tuple. |
| `strategies.expanding_z`: `GRAPH`, `COMPONENTS`, `LIBRARY`, `IMPLEMENTATIONS`, `KERNELS` | The reference artefact. Its kernels **call** the strategy's own functions; they do not restate the arithmetic. |

**Consumes.**

| Consumed | From | Why |
|---|---|---|
| `app/strategy/registry/expanding_z_v4.py` — `ExpandingZImpulseV4`, `default_params`, and the seven extracted pure functions (`zscore`, `adaptive_threshold`, `drift_score`, `range_in_atr`, `impulse`, `directional_entry`, `displacement_lost`) | WS-02 (strategy registry) | The reference artefact binds its kernels to these; a second copy of the arithmetic would make the parity test compare a copy to its original. **A change to any of these seven signatures breaks the parity test by design.** |
| `pandas` | third party | Series are the runtime's value type. |
| RFC 0001 | `docs/rfcs/0001-component-ir.md` | Normative. Every mechanism here names the clause it enforces. |

**Depends on:** WS-02 only for the strategy functions named above, and only in the reference
artefact and its test.
**Blocked by:** nothing, for the items in §5. The final adoption step is blocked — see §8.
**Currently blocking:** WS-04 Editor (has no other source of graph read/write); WS-03 Research
Plane (its block components, proposer, and the not-yet-done F14 binding of research runs all sit
on these exports).

## 4. Completed

Newest first. Test counts are from `pytest --collect-only` at `cdbe686`; the full IR suite
(`backend/tests/test_ir_*.py`) is **242 tests, exit 0**, verified 2026-08-03.

- **F8's converse enforced — 2026-08-03** (found by WS-03's proposer). An input that is neither
  wired nor given a default source is a socket nothing feeds: such a graph validates, **resolves
  cleanly**, and raises only when a kernel reaches for it. F8 therefore joins F7 as
  library-dependent — which sockets a node has lives in the component — and is reported
  *unchecked* without a library rather than passing. Appendix A.4 and A.5's fixtures were
  abbreviations that omitted their bar wiring; they are now complete artefacts.

- **Python component authoring — `c234e70`, 2026-08-02.** `app/ir/authoring.py` +
  `tests/test_ir_authoring.py`, 19 tests. Before this, a kernel was a bare function someone
  remembered to put in a dict under the right address, with its interface written out elsewhere
  and nothing checking the two agreed. The interface is declared and the **function** checked
  against it, not the reverse: F4 exists because an inferred interface changes whenever the
  internals do, so renaming a local would silently republish a different contract. Two facts worth
  keeping: this is the **first second way to make a component**, and therefore the first time
  C13's provenance-blind guard is load-bearing rather than precautionary — an authored component
  lands in the same two dicts a built-in lands in, keyed by content address and nothing else. And
  sandboxing is deliberately **absent**: RFC Appendix C(f) puts it on the kernel registry and
  triggers it on third-party distribution; locally-authored components are code the owner already
  runs. The sweep found a vacuous test of its own — the no-output case was being refused for a
  different reason (reading an input it declared), so deleting the no-output check left the suite
  green.

- **Warmup derived from bound parameters — `3b2b752`, 2026-08-02.** A real defect in what the
  earlier phases had built. `KernelSpec.warmup` was an integer, so the registry gave each
  component a constant taken from the strategy's *defaults* — a node overriding `ema_length` to
  200 still claimed it warmed up in 50 bars. Nothing would have reported it: the backtest would
  have read 150 bars of an unwarmed EMA and looked entirely plausible, the worst shape a defect
  can have here. C10 says warmup is **derived** per component, and it now is — `warmup` may be a
  function of the node's bound parameters, evaluated during resolution and range-checked there
  (C11: a function returning a negative is the same read of the future a negative constant was).
  Proven by a test that goes red against the constant it replaced.

- **The editor plane, writing half — `49e9ded`, 2026-08-02.** `app/ir/edit.py` + `Layout` in
  `view.py` + `tests/test_ir_edit.py`, 17 tests. `validate()` had existed since the format phase
  **with nothing calling it on a write path**, because there was no write path. The property now
  is that an invalid artefact cannot be stored: an edit whose result violates §3 raises, naming
  the clause. Typing a parameter grid into an override is refused as C14 at the edit, not
  discovered later. Every edit returns a new artefact and mutates nothing, so undo is keeping
  references rather than inverting operations. Removing a node removes its edges and its group
  membership in one operation — offering them separately would hand a UI an invalid intermediate
  state to store. **F13 is now asserted in the only form that can go red:** a graph with a
  hand-arranged `Layout` and the same graph without one have the **same content address**, and
  every cache identity downstream of a dragged node is unchanged — which is exactly the failure
  the clause exists to prevent ("dragging a node changes its hash and silently defeats cache
  identity"). The layout is sparse, so arranging two nodes does not take ownership of the other
  sixteen.

- **The editor plane, read-only — `dec854b`, 2026-08-02.** `app/ir/view.py` +
  `backend/scripts/render_ir_graph.py` + `tests/test_ir_view.py`, 17 tests. A `ResolvedGraph`
  becomes a view model and a self-contained SVG, so a strategy's structure can be **looked at**
  rather than only asserted about; `expanding_z_v4` renders as 18 nodes across 6 layers.
  - *There is no presentation state, which is why none can drift.* F13 keeps coordinates out of
    the artefact and the conforming default is to not have them at all, so position is a pure
    function of dependency structure. One test asserts the schema has nowhere to put a
    coordinate; another asserts that reordering the specification does not move a node between
    layers — if it did, editing an unrelated part of the file would redraw everything and a diff
    of two renders would be meaningless.
  - *The picture speaks the authored vocabulary (C4),* and carries what resolution computed and a
    reader of the source cannot: warmup, purity, cache identity.
  - *Caught by its own test, not by looking:* the first render spilled
    `indicator.adaptive_threshold v1` out through the right edge of its box. SVG text does not
    clip, so nothing failed and the picture was wrong while looking fine. There is now a geometry
    test over every text element in every box, proven red by suppressing truncation.

- **F14 enforced — `baef1c2`, 2026-08-02.** `app/ir/experiment.py` + `tests/test_ir_experiment.py`,
  23 tests. F14 binds every experiment and finding to the versions that produced it, and had been
  recorded *unenforceable* through the format and resolver phases because there was no experiment
  artefact. **The answer was never to widen §3** — an experiment is not a component or a graph,
  and admitting one would have bought a migration liability forever. The RFC's own note says F14
  becomes enforceable when the experiment system defines a record; this is that record.
  `format_version` does not move.
  - *The binding is derived, not supplied.* `record()` takes a `ResolvedGraph` and reads the
    versions off it. Which is why the record reaches `smoothing.wilder` — a component that
    appears nowhere in the specification's node list and is known only because resolution walked
    the ATR's body (C5).
  - *Five parts, each load-bearing:* graph version, every component version, every node's cache
    identity (transitive over its upstream, C8), the data digest, and the id. A record naming
    graph version 3 of a graph that resolved as 4 passes every structural check and is caught
    only against the graph.
  - *"And every finding."* A `Finding` carries its experiment's binding, so a claim that outlived
    a re-parameterised run is detected. That is the state this repository is in for everything
    before 2026-08 (see the research.db note in §7).
  - *The sweep found a vacuous guard of its own:* every test of `node_identities` emptied it,
    which trips the presence check, so deleting the comparison against the resolved graph left
    the suite green. There is now a test for identities that are present and wrong.
  - `UNENFORCEABLE_CLAUSES` became **empty**, and a bookkeeping test asserts every one of F1–F14
    is enforced here, enforced elsewhere and named, or declared unenforceable and named. Nothing
    may be simply absent.

- **The derived-parameter gap closed — `110e978`, 2026-08-02.** Writing the strategy graph turned
  up the one thing it could not express: `exit_abs`'s floor is `min_abs_z * 0.25`, and since an
  override carries a value only (F10), the graph first carried the literal `0.15` — correct at the
  shipped `min_abs_z = 0.60` and silently wrong the moment anyone moved it. **The resolution was
  not to weaken F10**, which is what protects a component author's constraints: a multiplication
  is a computation and C14 says components compute, so two new components — `value.scalar` (a
  parameter, on a wire) and `math.scale` — make the exit thresholds *track* `min_abs_z` instead of
  remembering one of its values. Verified by moving `min_abs_z` to 1.20 with the contraction exit
  switched on (the only configuration where the exit threshold reaches an output — there is a test
  asserting that too) and re-checking bar-for-bar parity against
  `compute(min_abs_z=1.20, use_absz_contraction_exit=True)`; proven able to fail by setting the
  scale factor to 0. **This is the first use of F7's `scalar` structure axis**, declared since the
  format phase and never exercised — the runtime had assumed every value was a series. It now
  checks what is checkable (a series is bar-aligned, a scalar is passed through), and
  `check_causality` compares scalars whole, because a scalar derived from the bars is the sharpest
  lookahead there is: one number that saw everything.

- **`expanding_z_v4` expressed in the IR and proven equal to the strategy — `e97ed72`,
  2026-08-02.** `app/ir/strategies/expanding_z.py` + `tests/test_ir_strategy_parity.py`, now 21
  tests. Appendix A.1 expressed this strategy as a sketch inside a markdown document, which proves
  what its author believed. This is the real artefact: 15 component definitions, 17 authored nodes
  plus two boundary nodes, 47 authored edges, the 15 real parameters read off `default_params`
  rather than restated — resolving to 18 nodes and 35 edges, evaluated, and asserted **equal to
  `ExpandingZImpulseV4.compute()` bar for bar** over 400 bars, with entries firing on the fixture
  so the comparison is not two constant series.
  - *The kernels are bound to the strategy's own functions, not rewritten.* Seven expressions were
    extracted out of `compute()` into named pure functions (`zscore`, `adaptive_threshold`,
    `drift_score`, `range_in_atr`, `impulse`, `directional_entry`, `displacement_lost`);
    `compute()` calls them and so do the kernels. A second copy of the arithmetic would be the
    `candles.py` defect, and the parity test would then be comparing a copy to its original. What
    is under test is the **language**.
  - *Proven able to fail.* Binding `n_entry_thr` to `exit_pct`, and re-pointing one edge from
    `n_ema` to `n_z`, each turn the parity test red.
  - *A new fact about production strategy code, not only about the IR:* `check_causality` finds
    `expanding_z_v4` causal at every node — its "signals fire only on completed candles" claim is
    now measured rather than conventional. The check is proven able to go red on this graph by
    making the EMA peek one bar ahead.
  - *C8's economics, demonstrated:* moving `entry_pct` recomputes the threshold, the impulse and
    the two entry predicates, and reuses the EMA, ATR, z-score, drift and range. That is what
    makes a sweep cheap without building the sweep into the indicator (C14).
  - *`indicator.atr.wilder`'s body is a graph, and the strategy proves it pays.* The ATR here is
    A.2's decomposition — true range into a Wilder smoothing — not a leaf, so forking it to an EMA
    smoothing is a component-reference change.

- **The component runtime — `df0bf6c`, 2026-08-02.** `app/ir/runtime.py` +
  `tests/test_ir_runtime.py`, 20 tests. Built immediately after the resolver and on purpose: a
  `ResolvedGraph` nothing evaluates is a correct mechanism wired to nothing, which is this
  codebase's defining defect. It evaluates A.4's graph with real kernels — Wilder's ATR decomposed
  into true range and a smoothing, instantiated at 7 and 21 — so the resolver's outputs stop being
  structure and start being numbers.
  - *Three §4 clauses become empirical rather than declared.* **C10:** composed warmup names the
    unsettled prefix and `settled()` removes it. **C8/C9:** evaluation memoises on the cache
    identity resolution computed, and never memoises a node whose kernel declares an impurity
    policy — caching a declared impurity is caching a lie. **C11:** `check_causality` evaluates on
    a prefix of the bars and on all of them and demands the shared bars match, so a kernel that
    reads ahead is caught whatever its author intended. Three real shapes are tested: `shift(-1)`,
    a centred rolling window, and a whole-series normalisation.
  - *The causality check was written the easy way first and a test caught it.* Comparing only the
    graph's **outputs** calls the normalisation case causal: dividing both branches by a max
    neither bar knew yet leaves `fast > slow` identical. It now compares **every node's** every
    socket.
  - *Every guarantee proven load-bearing.* Nine suppressions — cache lookup, cache key (instance
    id instead of identity), the purity gate, warmup, the index check, the every-node comparison,
    the reference series, the kernel lookup, the missing-input check — each turns its own test red.
  - *C13 holds subtractively.* The runtime's only key for a kernel is its body's content address.
    A component's origin is not representable there, so no execution path can branch on it, and an
    unregistered address fails rather than falling back.

- **The resolver, and §4's remaining fourteen clauses with it — `126c9cf`, 2026-08-02.**
  `app/ir/resolve.py`, `app/ir/kernels.py`, `app/ir/hashing.py` +
  `tests/test_ir_resolution.py`, now 50 tests. The order was forced and the reason held: C1–C12,
  C14 and C15 all constrain *resolution*, so they land with the thing that makes them testable
  rather than as a suite with nothing to run against.
  - *Appendix A.4 is the executed acceptance case,* not a sketch. Two instances of one definition
    resolve to `n_fast/n_smooth` and `n_slow/n_smooth`, stay distinguishable at lengths 7 and 21
    (C4), keep those identifiers across re-resolution and across a reordering of the node list
    (C7), and a kernel missing from the registry is reported at `n_fast/n_smooth` — the authored
    vocabulary — rather than against a node the author never placed (C4).
  - *Every clause is proven load-bearing.* Suppressing each of C1–C11, C14 and C15 one at a time
    turns that clause's **own** test red. The sweep found a **vacuous test of its own**: the C2
    no-mutation check compared a deep copy taken after other tests had already resolved the shared
    fixture, and a resolver that eats its input does so on the first call and is idempotent after.
    It now also resolves the shared specification and asserts it is still intact. C12 was proven
    red by planting a second `ResolvedGraph(` construction under `app/engine/`.
  - *Two clauses are enforced as an absence,* which is the stronger form: C12 by there being
    exactly one construction of a resolved graph in the tree (the `candles.py` defect was two
    hand-written implementations of one idea), and C6 by the resolver's source containing no
    clock, counter, random, environment or file read at all.
  - *One erratum, no `format_version` change.* Building the resolver found that A.2's
    `override length ← length` was inexpressible: the validator enforced F10 as "no mapping may be
    an override value" rather than as F10's actual text (no kind, no bounds, no display name).
    Recorded as **RFC 0001 §6.3 E1**. The accepted reference forms are a closed set
    (`schema.VALUE_REFERENCE_FORMS`), so "any mapping" is still refused. F8's `default_source`
    also gained a shape — a component reference and a socket — because resolution has to insert
    something and take the value from somewhere.
  - *Boundary nodes and kernel declarations were added without touching §3.* `graph.input` and
    `graph.output` are reserved *identifiers*, not grammar constructs; warmup, purity and cache
    identity live in the kernel registry, which §2 already says supplies kernels. Both are
    recorded in §6.3 so a reader of the format knows where they live.

- **Conformance suite for §3, and C13 — `34a4765`, 2026-08-02.** `app/ir/schema.py` (the closed
  vocabularies) + `app/ir/validate.py` + three test files (now 51 + 15 + 9 tests).
  **F1–F13 are enforced mechanically**; each violation names its clause and path, so a failure
  reads `F7 at $.edges[1].domain.timeframe` rather than as a schema error about a key.
  - *Appendix A is executed, not asserted.* All five worked artefacts are real data in
    `tests/test_ir_corpus.py`: A.1–A.4 validate, and A.5's final edge is rejected on the **domain
    axis specifically** — the test pins the path and both timeframes, so a validator checking only
    value and structure (which would pass that graph) fails here.
  - *Every clause is proven load-bearing.* Suppressing any one of F1–F13 turns the suite red. That
    sweep found a **vacuous test of its own**: the F9 uniqueness check passed under mutation
    because renaming a node also orphaned an edge, and the dangling edge raised F9 anyway. Now
    asserted by path.
  - *An unchecked clause is not a passing clause.* F7's edge type-matching needs a component
    library; without one `unchecked_clauses()` reports F7 rather than staying silent. F14 was
    recorded as not enforceable at all at this point, and `UNENFORCEABLE_CLAUSES` asserted that as
    a fact rather than leaving it implicit.
  - *C13 (provenance-blind execution) holds, subtractively.* One `_REGISTRY`; a generated strategy
    is `register()`ed into the same dict a built-in is discovered into; no `Strategy` carries a
    field naming its origin. Guard proven red by planting `if strategy.is_marketplace:` in
    `engine/exit_monitor.py`.

- **RFC 0001 — `97d6bbb`, accepted 2026-08-02.** 14 Format clauses (the serialised core, with an
  EBNF grammar), 15 Contract clauses (observable properties, no mechanism), non-goals, amendment
  procedure. Gate 1 (expressiveness) met by expressing five real artefacts; Gate 2 (adversarial
  review) met; Gate 3 (owner acceptance) recorded against the owner's standing directive that the
  architectural phase is complete and the RFCs define the architecture. Evidence base is
  `~/dev/multiverse-of-ideas/reviews/` (nine systems read). Spec:
  `docs/superpowers/specs/2026-08-02-component-ir-rfc-v1-design.md` · Plan:
  `docs/superpowers/plans/2026-08-02-component-ir-rfc-v1.md`.

- **Housekeeping — `cdbe686`, 2026-08-03.** Comment essays stripped from `app/ir/`: −1,300 lines
  of prose, zero code change.

## 5. Active roadmap

- [ ] **Narrow the F4 rule for dynamically-adapted kernels.** `AuthoredComponent.unchecked`
      currently reports "the interface check could not conclude" for any kernel that reaches
      `inputs`/`params` dynamically — which is honest but is now the common case for
      factory-built components. Decide whether the language should offer a way for such a kernel
      to *declare* what it reaches (still a declaration, so F4 holds), or whether `unchecked`
      stays the permanent answer. This is the WS-01 half of WS-03's "narrow each block's declared
      inputs" item; the block declarations themselves are WS-03's.
- [ ] **Decide the display-name/content-address question** (§7). Either amend RFC §3 so cosmetic
      metadata is excluded from the hashed body, or record in §6.3 that a rename mints a new
      address and that this is intended. It is currently only *pinned* by a test.
- [ ] **A worked `publish()` round trip in the reference artefact.** C15 is tested against
      synthetic graphs only. Publishing `indicator.atr.wilder`'s body as a standalone component
      and re-resolving `expanding_z_v4` against it — asserting bar-for-bar identical output —
      would make subgraph/component equivalence an empirical property of a real strategy rather
      than of a fixture.
- [ ] **Multi-timeframe resolution.** F7's domain axis is enforced (A.5's ill-typed edge is
      rejected), but nothing yet *resolves* a graph whose nodes sit on different timeframes —
      there is no resampling component and no rule for what an edge across timeframes would mean
      if it were legal. Needed before any 15m/30m composite strategy can be expressed.
- [ ] **A second reference artefact from a different strategy family.** `expanding_z_v4` is the
      only strategy expressed in the IR, so every expressiveness claim rests on one shape. The
      next-best candidate is `trend_impulse_v3` (the default registry strategy). Expect it to find
      a gap, as `expanding_z_v4` found the derived-parameter one.

## 6. Acceptance criteria

A change in WS-01 is done when all of the following are true, run from `backend/`:

```bash
.venv/bin/python -m pytest tests/test_ir_authoring.py tests/test_ir_conformance.py \
  tests/test_ir_contract_c13.py tests/test_ir_corpus.py tests/test_ir_edit.py \
  tests/test_ir_experiment.py tests/test_ir_resolution.py tests/test_ir_runtime.py \
  tests/test_ir_strategy_parity.py tests/test_ir_view.py -q       # 242 passed at cdbe686
.venv/bin/python -m pytest tests research_tests -q                # both suites, exit 0
.venv/bin/python scripts/render_ir_graph.py /tmp/expanding_z_v4.svg   # reference artefact still draws
```

Plus, specific to this workstream and not negotiable:

1. **Every clause is accounted for.** `ENFORCED_CLAUSES ∪ ELSEWHERE_ENFORCED_CLAUSES ∪
   UNENFORCEABLE_CLAUSES` covers F1–F14, and the bookkeeping test in `test_ir_conformance.py`
   passes. A clause may not be silently absent.
2. **A new guard is proven able to go red.** Suppress the mechanism, watch the test fail on the
   right clause *and the right path*, restore. A test that passes for the wrong reason has already
   shipped four times in this workstream (F9 by path, C2's stale deep copy, C11's outputs-only
   comparison, F14's emptied identities, authoring's no-output case) — assume it will happen
   again and assert on the path, not just the clause.
3. **No new construct without an RFC amendment.** If a capability does not fit the language,
   RFC §6.2 says there are two paths and no third: express it in the IR unchanged, or write the
   amendment. Adding a key to `schema.py` that §3 does not describe is the drift this RFC exists
   to make visible.
4. **`format_version` moves only with an amendment and a migration pass** (RFC §6.1).
5. **`app/ir/` imports nothing from `app/engine/`, `app/backtest/` or `research/`.** The IR is a
   language, not an executor; the dependency runs one way.

## 7. Known technical debt

- **F7 edge type-matching is only checked when a library is supplied.** `validate(artefact)` with
  no library does not check that a wire's two ends agree — it reports F7 (and now F8) as
  *unchecked*. Cost of leaving it: a caller that ignores `unchecked_clauses()` will read "no
  violations" as "conforming", which it is not. Trigger to fix: the first persistence layer or API
  that stores artefacts, where a library is not necessarily at hand. The honest interim rule is
  that any caller storing an artefact must call `unchecked_clauses()` and refuse a non-empty set.
- **Nothing in production imports `app/ir/`.** The only importers are the IR's own tests,
  `backend/scripts/render_ir_graph.py`, and WS-03's research code (`ir_components.py`,
  `propose.py`) with its tests. No engine, route, or backtest path reaches it. This is deliberate
  (see §8), but it means every guarantee in §3 is verified against tests and one script, never
  against production traffic. Cost: the language is unexercised by the pressures that actually
  break formats — persistence, migration, concurrent editors. Trigger: WS-02's adoption decision,
  or WS-04 putting a UI in front of it.
- **The reference artefact hand-builds its artefacts instead of using `authoring.py`.**
  `strategies/expanding_z.py` predates the authoring layer and constructs its components with
  private `_component`/`_socket`/`_param` helpers and `content_address(identifier)` as a stand-in
  body address, rather than `component()`/`library()`. Cost: two ways to make a component in the
  tree, and the reference artefact demonstrates the older one. Trigger: any change to the
  authoring contract, which would then need making in two places.
- **Components declaring more inputs than they read.** In WS-03's derived block library every one
  of the 23 components declares the whole OHLCV frame, because a single adapter rebuilds it —
  which makes every block look like it depends on volume. The declarations live in WS-03's files,
  but the rule is WS-01's: F4 forbids inferring the interface from the body, so the fix must be a
  narrower *declaration*, not inference. (The reference artefact is not affected — `expanding_z`
  declares exactly `high`, `low`, `close`.) Cost: dependency structure is wrong wherever it is
  read, including the drawn graph. Trigger: any structure search that reasons about which inputs
  a component needs.
- **A display-name change mints a new content address.** F2 requires the display name to be *in*
  the artefact and F13 hashes the artefact, so a cosmetic rename produces a new body address. It
  breaks no reference — the graph resolves identically — but whether it *should* change the
  address is undecided; a test in `test_ir_edit.py` pins current behaviour so the question stays
  visible, and deciding it is an amendment matter under RFC §6. Cost: renaming a component in an
  editor would invalidate every cache entry downstream of it. Trigger: the editor UI shipping a
  rename affordance (WS-04), or the first persistent artefact store.
- **`research.db` findings before 2026-08 have no F14 binding at all** and cannot be given one
  retrospectively. They are not a WS-01 defect but they are the reason F14 exists; do not use
  them as a baseline. WS-03 owns re-running anything that matters.

## 8. Blockers

- **Adoption in a live path is owner-blocked.** The engine still calls `compute()`. Making a
  real-money path evaluate an IR graph is RFC 0001 **Appendix C(d)** and needs owner
  acknowledgement before any deploy *regardless of green tests*. The parity evidence such a change
  would need already exists (`test_ir_strategy_parity.py`). This item belongs to **WS-02**; WS-01
  supplies the runtime and the proof and does not decide it.
- Nothing else. Every item in §5 can be started without an external decision.

## 9. Future work

Named and deliberately not scheduled. These map onto RFC Appendix C's open questions.

- **Fork semantics beyond a parent pointer** (Appendix C(a)). F3 records `parent_version` and
  nothing more. Scheduled when two people — or a marketplace — need to reconcile divergent
  versions of one component.
- **Field and structure inference rules** (Appendix C(b)). Currently every wire type is declared.
  Scheduled if authoring friction is measured to be the thing slowing component creation.
- **Migration machinery** (Appendix C(c)). `format_version` is 1 and has never moved; a reader
  rejects a version it does not understand and there is no migration pass because nothing has
  needed one. Scheduled by the first breaking amendment — which RFC §6.1 says must ship with it.
- **Tick-level and intrabar strategies** (Appendix C(e)). The runtime's value type is a bar-indexed
  series and C11's causality check is defined over bars. Scheduled if the product moves below the
  candle.
- **Marketplace trust and sandboxing** (Appendix C(f)). `authoring.py` deliberately does not
  sandbox: locally-authored components are code the owner already runs. Scheduled by the first
  component originating outside this repository.
- **Persistence.** There is no artefact store — graphs live in Python modules and test fixtures.
  Scheduled by WS-04 needing to save what a user drew.

---

*Constitutional document for this workstream:* [`docs/rfcs/0001-component-ir.md`](../../rfcs/0001-component-ir.md).
Clause numbers used throughout (F1–F14, C1–C15) are its, and it is normative where this document
and it disagree.
