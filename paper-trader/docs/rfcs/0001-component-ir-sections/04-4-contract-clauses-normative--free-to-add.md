Reference: [section index](../0001-component-ir.md). Read with its scope; this is not a new assignment.

## 4. Contract clauses (normative — free to add)

Every clause in this section states an **observable property** that a conforming implementation
must exhibit. None prescribes a mechanism. These clauses are free: they add nothing to an artefact
and therefore require no migration, so this section is completed thoroughly where §3 is minimised
ruthlessly.

> **All fifteen are enforced as of 2026-08-02**, against `backend/app/ir/resolve.py` and its
> kernel registry, by `backend/tests/test_ir_resolution.py` (C1–C12, C14, C15) and
> `test_ir_contract_c13.py` (C13). Each clause's own test was proven able to fail by suppressing
> that clause's implementation one at a time. Two clauses are enforced as an **absence** rather
> than a behaviour, which is the stronger form: C12 by there being exactly one construction of a
> resolved graph anywhere in the tree, and C13 by no executor path having a provenance concept
> to branch on.

| # | Clause | Evidence |
|---|---|---|
| C1 | Resolution is deterministic | D5, P5, P7 |
| C2 | Resolution is free of side effects | D5, P5 |
| C3 | Resolution preserves semantics | D5, P7 |
| C4 | Derived elements carry back-references | D8, P6 |
| C5 | Resolution preserves and records version identity | D1, D4, P2 |
| C6 | Resolution introduces no hidden state | D5 |
| C7 | Resolution is reproducible; ids derive from the instance path | D7, P5 |
| C8 | Cache identity is transitive by default, declarable per component | D13, P4 |
| C9 | Components are pure; impurity is a declared policy | D14, P4 |
| C10 | Warmup is derived per component and composes | D22 |
| C11 | Lookahead is prevented structurally | D22 |
| C12 | Research and live share one resolution | D6, P7 |
| C13 | Execution is provenance-blind | D21 |
| C14 | Components compute; searchers search | D20 |
| C15 | Publishing a subgraph is a mechanical derivation | D10, P10 |

**C1 — Determinism.** The resolved graph MUST be a deterministic function of the specification.

**C2 — Side-effect freedom.** Resolution MUST NOT produce observable side effects.

**C3 — Semantic preservation.** Resolution MUST preserve the semantics of the specification. The
specification remains the source of truth; the resolved graph is derived and MUST NOT be authored,
edited, or persisted as a source of truth.

**C4 — Provenance preservation.** Every derived, expanded, or inserted element MUST carry a
back-reference to the definition it came from. Diagnostics MUST speak the authored graph's
vocabulary, not the resolved graph's. Node-RED's `_alias` and `path` are the model (P6). This
clause MUST land together with nesting, never after it: retrofitting means every diagnostic path
is wrong first.

**C5 — Version identity preservation.** Resolution MUST preserve and record every resolved
`(identifier, version)` pair.

**C6 — No hidden state.** Resolution MUST NOT introduce state that is not derivable from the
specification.

**C7 — Reproducibility.** The same specification MUST resolve identically. Instance identifiers
MUST derive from the instance path, and MUST NOT derive from clocks, counters, or randomness. If
they did, re-resolution would not be byte-identical and replay would be impossible.

**C8 — Cache identity.** Cache identity MUST be transitive over the upstream subgraph by default,
and MAY be declared per component. Transitivity makes correctness automatic under composition —
the property Prefect lacks, whose `TaskSource` explicitly excludes nested tasks. Declarability
handles components whose identity genuinely is not their inputs. Neither ComfyUI nor Prefect has
both; this clause takes both.

**C9 — Purity.** Components MUST be pure. Impurity MUST be expressible only as a **declared
policy**, and MUST NOT be available as an escape hatch. ComfyUI's `IS_CHANGED` is the
counter-example: it makes the cache correct while destroying its value as a provenance claim. A
declared policy keeps the claim intact.

**C10 — Warmup.** Warmup MUST be derived per component and MUST compose through the graph.

**C11 — Lookahead.** Lookahead MUST be prevented structurally. A component MUST NOT be able to
violate it by convention. Nautilus obtains this property by identity — it is structurally
impossible there — and this clause is the price of choosing whole-series wires instead (§2A of the
findings).

**C12 — Research/live parity.** Research and live MUST share **one** resolution.

This is what makes parity structural rather than tested. The precedent is this project's own: the
`candles.py` defect came from **two hand-written implementations** of one idea, not from a
compilation step. Parity does not require interpreting the authored graph — that framing was a
false dichotomy, disproven by Blender, the most mature node system in existence, which lowers.
What parity requires is one resolution used by both planes.

**C13 — Provenance-blind execution.** No executor path may branch on where a component came from.
A component's source is display metadata and nothing else. ComfyUI achieves this *subtractively* —
one registry, no plugin API — and the subtractive route is the one to copy. Given this codebase's
documented history with mechanisms that exist and are wired to nothing, C13 is to be enforced by a
test in the conformance phase rather than by review.

**C14 — Searcher boundary.** Components compute; searchers search. Parameter sweeping MUST NOT be
part of a component's contract.

This clause names a trap the platform is currently inside. vectorbt builds parameter grids into
the indicator contract itself, which silently defines *search = parameter sweeping* for everything
downstream — and the research plane inherited that shape. Structure search is not reachable from a
design where components sweep themselves.

**C15 — Subgraph/component equivalence.** Publishing a subgraph as a component MUST be a
mechanical derivation from its declared interface, introducing no information the interface does
not already carry.

C15 is what makes components **decomposable**: a subgraph and a component are the same kind of
thing, so an indicator is itself a graph. This is the Generation-2 requirement the current block
library fails — see Appendix A.2 — and it is a language clause rather than a marketplace concern,
because distribution is a separate plane (§1.2).

---
