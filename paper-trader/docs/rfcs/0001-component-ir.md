# RFC 0001 — The Component IR

**Status:** Proposed — Gates 1 and 2 met; pending owner acceptance
**Version:** 1.0 · **Date:** 2026-08-02
**Supersedes:** nothing · **Amended by:** nothing

> **§3 is enforced. §4 is not, with one exception.** As of 2026-08-02 a conformance suite
> exists — `backend/app/ir/` plus `backend/tests/test_ir_{conformance,corpus,contract_c13}.py`.
> It mechanically validates artefacts against **F1–F13**, executes all five Appendix A
> artefacts as real data rather than sketches, and enforces **C13**. Suppressing any single
> clause turns that suite red, so the checks are known to be load-bearing rather than merely
> present.
>
> Two gaps are recorded rather than glossed, and both are asserted by tests so they cannot be
> mistaken for coverage. **F14 is not enforceable** — it binds experiments and findings to the
> versions that produced them, and the grammar has no experiment artefact to validate; it
> becomes enforceable when the experiment system defines one. **F7's edge type-matching needs a
> component library** — given one, exact matching on all three axes is checked; given none, F7
> is reported *unchecked* rather than passing silently.
>
> **§4's other fourteen clauses remain a claim, not a fact.** They constrain *resolution*, and
> no resolver exists. They are a named follow-on phase, landing with the implementation that
> makes them testable.

---

## Preface (informative)

### Why the Component IR exists

Nine systems were read in full before a line of this document was written — ComfyUI, vectorbt,
NautilusTrader, Node-RED, Blender, Langflow, xyflow, Airflow, Prefect — across four domains and
three decades of combined history, plus an earlier teardown of OpenAlgo. The evidence and the
per-system reviews live in `~/dev/multiverse-of-ideas/reviews/`; the distilled conclusions are in
`_FINDINGS-component-ir.md` and `_PATTERNS.md`. This document cites them and does not reproduce
them.

The finding all nine converge on is an absence. **Not one of them has both a durable component
and a real composition model.** Some compose but cannot say durably what they composed; some have
reusable units but no graph. The table in `_FINDINGS-component-ir.md` §1 is the evidence. That
gap is what this language exists to close.

### Why we are introducing a language

The platform is being rebuilt around Components → Graphs → Experiments → Deployments. Today it is
built around strategies, and the cost of that is visible in the code: four sources of strategy —
built-in, generated, visual, Python, marketplace — each reduce to the same four boolean columns
and then run one hard-coded risk model. That is four skins on one strategy, not four strategies.

A language is what lets a strategy say what it is: its parameters, its structure, its
composition, its version. Without one, every subsystem invents its own private answer.

### Why every subsystem speaks it

The runtime, the research plane, the editor and the marketplace are **interfaces over one
language**, not four abstractions that happen to cooperate. Each either produces the IR, consumes
it, or is deterministically derived from it. Where two subsystems need to agree about a strategy,
they agree in this language or they do not agree at all.

### Why this document distinguishes Format clauses from Contract clauses

Blender carries **44,246 lines** of version-migration code across releases 2.50→5.30 — rewrite
passes that carry old files forward, forever, one per concept the format ever admitted. That is
the true price of a language, and it is the reason §3 of this document is kept small.

But that price is paid **only for what is serialised**. A guarantee costs nothing to migrate:
"the executor never branches on a component's provenance" adds no bytes to a stored graph and
will never need a rewrite pass. So this constitution has two kinds of normative clause and marks
them apart:

- **§3 Format clauses** — what is written down and read back. Each is a permanent migration
  liability. Minimised ruthlessly.
- **§4 Contract clauses** — guarantees any conforming implementation must satisfy. Free.
  Completed thoroughly.

The practical rule this yields, and the reason the split is structural rather than stylistic:
*additions to §3 cost migrations forever; additions to §4 cost nothing.* A designer under time
pressure can apply that rule without re-deriving the argument.

---

## 1. Scope, principle, and planes

### 1.1 The central principle

> **The Component IR is the canonical representation of strategy intent.**
>
> Not strategy execution. Not source code. Not UI state. Not runtime state.
>
> Every other representation — Python, visual graphs, marketplace packages, runtime objects,
> resolved graphs — either **produces** the IR, **consumes** the IR, or is **deterministically
> derived** from it. The IR itself is the source of truth.

### 1.2 The five planes

| Plane | Concern | Relationship to the IR |
|---|---|---|
| **Language** | The IR itself | *is* the IR |
| **Runtime** | How a resolved graph executes | consumes |
| **Research Plane** | How graphs are generated and searched | produces and consumes |
| **Editor** | How humans author graphs | produces |
| **Marketplace** | How components are distributed | transports |

**A normative clause MUST NOT name a UI concern, a search algorithm, an optimisation strategy, or
a marketplace workflow.** Such a clause is misfiled, and the presence of one is a defect in this
document rather than a matter of taste.

The IR knows nothing about how a graph is drawn, how one is searched for, how one is optimised, or
how one is sold. It defines the language all four speak.

### 1.3 Specification → Resolution → Execution

Three stages, formally separated. The separation exists to prevent authoring concepts leaking into
execution semantics.

| Stage | What it is | Governed by |
|---|---|---|
| **Specification** | The serialised form of a component or graph. The artefact. | §3 |
| **Resolution** | Transforms a specification into a fully bound executable graph, resolving component references, versions, kernels and dependencies. | §4 |
| **Execution** | The runtime evaluates the resolved graph. | §4; mechanism out of scope |

> This RFC does **not** prescribe how resolution is performed. Graph rewriting, lazy expansion,
> canonicalisation, optimisation passes, or a mechanism not yet invented are all conforming,
> provided the observable properties in §4 hold.

### 1.4 What this RFC does not cover

The runtime, the visual editor, Python component authoring, Research Plane Generation 2, the
experiment system, the marketplace, deployment, and production adoption each require their own
RFC or specification. See §5.

---

## 2. Terminology and conformance

### 2.1 Conformance language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be
interpreted as described in RFC 2119. They are normative only when uppercase.

### 2.2 Terms

**Artefact** — a serialised component or graph, together with its envelope.

**Component** — a named, versioned, reusable unit. Data first; a callable only after resolution.

**Specification** — the serialised form of a component or graph. What is stored.

**Resolution** — the stage that transforms a specification into a fully bound executable graph.

**Lowering** — **one operation within resolution**: the deterministic structural expansion of
nested references. Lowering is *part of* resolution and MUST NOT be used as a synonym for it.

**Execution** — evaluation of a resolved graph by a runtime.

**Resolved graph** — the output of resolution. Never authored, never edited, never a source of
truth.

**Graph** — a set of nodes and edges, itself referenceable as a component.

**Node** — one instance of a component within a graph.

**Socket** — a typed input or output on a component's interface.

**Parameter** — a tunable value on a component's interface, carrying a kind.

**Identifier** — an immutable, opaque string used for reference. Never renamed, never reused.

**Display name** — a human-facing label. Freely editable. Never referenced.

**Version** — an integer distinguishing bodies of one identifier.

**Kernel** — an opaque leaf implementation of a component body, supplied by a registry.

**Subgraph** — a component whose body is a graph.

**Override** — a value supplied by a referencing graph for a parameter of a referenced component.

**Plane** — one of the five domains in §1.2.

---

## 3. Format clauses (normative — every clause here is migrated forever)

Every clause in this section describes something written into an artefact and read back. Each one
is a permanent migration liability: a concept admitted here is a concept whose rewrite pass we
hand-write for as long as the format lives. Blender carries 44,246 lines of such passes.

**A clause belongs in §3 only if the guarantee it supports is impossible without serialising it.**
If it can live in §4, it MUST live in §4.

### 3.1 Grammar

The following EBNF is the normative structural definition. The clauses in §3.2 constrain it.

```ebnf
artefact       = envelope , ( component-def | graph-def ) ;
envelope       = format-version , artefact-kind ;
format-version = integer ;
artefact-kind  = "component" | "graph" ;

component-def  = identifier , version , display-name , interface , body ;
identifier     = opaque-string ;          (* immutable; never reused, never renamed *)
display-name   = human-string ;           (* freely editable; never referenced *)
version        = integer , [ parent-version ] ;
parent-version = integer ;                (* fork: records its parent *)
body           = kernel-ref | graph-ref ; (* content-addressed; stored once *)

interface      = { interface-item } ;
interface-item = panel | socket | parameter ;
panel          = identifier , display-name , { interface-item } ;   (* recursive *)
socket         = identifier , display-name , direction , wire-type ,
                 [ default-source ] ;
direction      = "input" | "output" ;
parameter      = identifier , display-name , kind , [ bounds ] , default ;
kind           = "length" | "thr" | "pct" | "mult" | "choice"
               | "minute" | "bool" | "secret" ;

wire-type      = value-type , structure-type , domain ;
structure-type = "scalar" | "series" | "auto" ;
domain         = instrument-domain , timeframe-domain ;

graph-def      = identifier , version , display-name , interface ,
                 { node } , { edge } , { group } ;
node           = instance-id , component-ref , { override } ;
component-ref  = identifier , version ;   (* by reference; never inlined *)
override       = parameter-identifier , value ;   (* value only *)
edge           = socket-ref , socket-ref ;        (* source , target *)
socket-ref     = instance-id , socket-identifier ;
group          = identifier , display-name , { instance-id } ;  (* visual only *)

(* Presentation state is deliberately absent from this grammar. See F13. *)
```

### 3.2 Clauses

| # | Clause | Evidence |
|---|---|---|
| F1 | Artefact envelope: `format_version` and kind | D3, P3 |
| F2 | Component identity: immutable identifier, version, content-addressed body, separate display name | D1, D2, P1, P2 |
| F3 | A version MAY record a parent version | D1 |
| F4 | The interface is declared, recursive, never inferred | D9, P10 |
| F5 | Parameters carry identifier, display name, kind, bounds, default | D2, P1 |
| F6 | `secret` is a kind whose value is a reference | D16, P12 |
| F7 | Wire types: value × structure × domain, closed and exact-matched | D11, D12, D22, P8 |
| F8 | Inputs MAY declare a default source | D19, P14 |
| F9 | A graph is nodes and edges | D1, D2 |
| F10 | Overrides carry values only | D15, P11 |
| F11 | Nesting is by reference | D7, P5 |
| F12 | Visual grouping is distinct from semantic reuse | D18, P9 |
| F13 | Semantic content is hashed; presentation state is stored beside | D17, P13 |
| F14 | Every experiment and finding binds to the versions that produced it | D4, P2, P3 |

**F1 — Artefact envelope.** Every artefact MUST record the `format_version` that wrote it and its
kind. A reader MUST reject an artefact whose `format_version` it does not understand, and MUST NOT
attempt to interpret it partially. This is the precondition for all future migration (P3); without
it, no rewrite pass can know what it is rewriting.

**F2 — Component identity.** A component MUST carry an `identifier` that is immutable, assigned at
creation, and never reused for a different component. A component MUST carry a `version`
distinguishing bodies under that identifier. The body MUST be stored once and content-addressed.
A component MUST carry a `display-name` that is separate from the identifier, freely editable, and
that **MUST NOT be referenced by anything**.

The `identifier` ≠ `display-name` split (P1, Blender's `bNodeTreeInterfaceSocket`) is the cheapest
high-value clause in this document. It costs one field now. Without it, the first rename by a
component author breaks every graph and every stored experiment that referenced the renamed
element — and in a forkable library, renames are routine.

**F3 — Fork.** A version MAY record a parent version. Fork semantics beyond the parent pointer are
out of scope; see Appendix C(a).

**F4 — Declared interface.** A component's interface MUST be **declared** as a recursive tree of
panel and socket items. It MUST NOT be inferred from the component's internals. An inferred
interface changes whenever internals change, which is catastrophic for a published component; a
declared one is a contract the internals must satisfy. Panels are structural, not decorative: at
roughly thirty parameters a flat list is unusable, and the organisation belongs to the component's
author rather than to whichever editor happens to render it (P10).

**F5 — Parameters.** A parameter MUST carry an identifier, a display name, a kind drawn from the
closed vocabulary in the grammar, optional bounds, and a default. The kind is required and is not
redundant with the value's type: "it is a float" does not tell a consumer whether `0.8` means 80%
or 0.8 ATR. Bounds are part of the contract rather than advice, because a published component's
parameters are edited by someone who did not write it.

**F6 — Secrets.** `secret` is a parameter kind whose value is a **reference**. A secret value
MUST NOT appear in any artefact, under any circumstances. This makes the safe path the only
representable one (P12).

**F7 — Wire types.** A wire type MUST be the product of three axes: a **value type**, a
**structure type**, and a **domain**. The structure axis MUST carry at least `scalar` and `series`,
plus `auto` for inference. The domain MUST carry an instrument and a timeframe.

The set of value types MUST be **closed, versioned, and exact-matched**. There MUST NOT be a
wildcard type, overlap matching, or coercion by string comparison. This is the strictest and least
extensible part of the IR, deliberately: ComfyUI's validator accepts comma-separated strings and
`*` as Any, matches by overlap, and carries three compatibility shims — one of which depends on
third-party code subclassing `str` to override `__ne__`. Their ecosystem froze their core. Blender
makes a similar stringly-typed choice and survives it only because socket types are added by one
closed team, which is a mitigation an open ecosystem does not get.

The *inference rules* for the structure axis are a layer above this format and are not frozen
here. The two-axis **shape** is what this clause fixes. See Appendix C(b).

**F8 — Default input sources.** An input MAY declare a default **source**, not merely a default
value. A graph whose unwired inputs all declare sources MUST be valid. This makes graph mutation a
local edit rather than a constraint-satisfaction problem, and is an explicit Generation-2 enabler
(P14).

**F9 — Graph.** A graph MUST consist of nodes and edges. A node MUST carry an instance identifier,
a component reference, and its overrides.

**F10 — Overrides.** An override MUST carry a **value only**. It MUST NOT carry a kind, bounds, or
a display name. The author's constraints are the only thing protecting a user of a component they
did not write (P11). This also matches this platform's operating reality: deployment-level
configuration overrides are deliberate value decisions, not redefinitions of what a knob means.

**F11 — Nesting by reference.** A graph MUST reference a nested subgraph by `(identifier,
version)`. A subgraph MUST NOT be inlined into a referencing graph. Inlining makes sharing,
deduplication and fork-expression impossible — Langflow inlines full source per node, with the
result that every graph is already a fork and the concept loses meaning (P2).

**F12 — Visual grouping.** Visual grouping MUST be a construct distinct from semantic reuse. A
group MUST NOT be versionable or publishable. If grouping-for-tidiness were also the reuse unit,
every cosmetic box would become a versionable artefact and the version history would fill with
noise (P9).

**F13 — Presentation state.** Semantic content MUST be hashed. Presentation state MUST persist
**beside** the graph, keyed by stable identifier, and is not part of the artefact grammar.
Ephemeral state MUST NOT be persisted. Without this separation, dragging a node changes its hash
and silently defeats cache identity (C8).

**F14 — Result binding.** Every experiment and every finding MUST record the exact graph version
and every resolved component version that produced it.

F14 carries the heaviest evidential weight in this document. Airflow needed `DagVersion` bound to
**task instances** — execution history, not merely definitions — and reached it only after roughly
a decade, by retrofit. Versioning's value is retrospective, so adding it late leaves every prior
run permanently unattributable. **This platform has already paid that exact price**: every
research finding recorded before 2026-08 is unusable as a baseline for this reason. The clause
exists so it is not paid twice.

---

## 4. Contract clauses (normative — free to add)

Every clause in this section states an **observable property** that a conforming implementation
must exhibit. None prescribes a mechanism. These clauses are free: they add nothing to an artefact
and therefore require no migration, so this section is completed thoroughly where §3 is minimised
ruthlessly.

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

## 5. Non-goals

Each is excluded deliberately, with its reason.

1. **No runtime or execution mechanism.** §4 states properties; how they are achieved belongs to
   the runtime's own RFC.
2. **No migration machinery.** The preconditions are adopted now — F1's version stamp and F2's
   stable identifiers. The machinery waits for the first real migration, because building rewrite
   infrastructure before there is anything to rewrite is speculative.
3. **No marketplace trust or sandboxing model.** Sandboxing constrains what a component *kernel*
   may do. That is a property of the kernel registry, not of the graph language.
4. **No editor or UI concepts.** A different plane (§1.2).
5. **No search or optimisation strategy.** A different plane; C14 makes the boundary normative.
6. **Forward compatibility is explicitly declined.** Backward compatibility is adopted: newer
   readers MUST carry older artefacts forward. Forward compatibility — an older reader
   interpreting a newer artefact — is **not** promised. Blender accepts that constraint because an
   old binary must open a new file; that is not our situation, and assuming otherwise would
   constrain the format permanently for no benefit.
7. **No tick-level or intrabar semantics.** C10 and C11 rest on this platform acting on completed
   candles only. `~/dev/multiverse-of-ideas/reviews/nautilus-trader.md` §10 is the recorded trigger
   to revisit if that ever changes.

---

## 6. Amendment procedure

### 6.1 Change classes

**Erratum** — corrects wording without changing any conforming artefact or implementation. No
`format_version` increment.

**Non-breaking amendment** — adds an optional construct, or a clause no existing artefact
violates. `format_version` increments; older artefacts remain readable unchanged.

**Breaking amendment** — changes or removes an existing construct, or adds a required one.
`format_version` increments **and** a migration pass MUST ship with it. Per §5(6), no forward
compatibility is promised: a reader of an older `format_version` MUST reject a newer artefact
rather than guess at it.

### 6.2 Process

> Every new platform capability MUST either fit inside this IR unchanged, or be accompanied by an
> RFC that amends it. There is no third path. A capability that quietly extends the language
> without an amendment is architectural drift, and this section exists to make that
> distinguishable from ordinary work rather than to forbid it in spirit only.

An amendment is accepted by the owner. An amendment MUST pass the same expressiveness gate this
document passed: every example in Appendix A MUST be re-expressed under the amended language, and
a failure to express any of them is a defect in the amendment.

---

## Appendix A — Worked examples (informative)

These five artefacts are the **acceptance set**. A failure to express any one of them is a defect
in this RFC, not in the example. Each uses real parameters from the running system, not plausible
ones.

### A.1 The EMA-z strategy (`expanding_z_v4`)

Expressed as a `graph-def` whose interface declares the strategy's fifteen real parameters, and
whose nodes reference indicator and predicate components. Abbreviated to its shape:

```
graph-def
  identifier    "strategy.expanding_z_impulse"
  version       4
  display-name  "Expanding Z Impulse V4"
  interface
    panel "trend"      → parameter ema_length      length  default 50
                       → parameter slope_lookback  length  default 5
    panel "zscore"     → parameter z_length        length  default 50
                       → parameter adapt_length    length  default 200
                       → parameter entry_pct       pct     default 65.0
                       → parameter exit_pct        pct     default 35.0
                       → parameter min_abs_z       thr     default 0.60
    panel "volatility" → parameter atr_length      length  default 14
                       → parameter min_drift_atr   mult    default 0.08
                       → parameter max_signal_atr  mult    default 2.75
    panel "behaviour"  → parameter require_expansion         bool default true
                       → parameter allow_reexpansion         bool default true
                       → parameter use_absz_contraction_exit bool default false
                       → parameter exit_on_drift_flip        bool default true
                       → parameter exit_on_ema_cross         bool default true
    socket longEntry   output  wire-type(bool, series, (instrument, timeframe))
    socket shortEntry  output  wire-type(bool, series, (instrument, timeframe))
    socket longExit    output  wire-type(bool, series, (instrument, timeframe))
    socket shortExit   output  wire-type(bool, series, (instrument, timeframe))
  node  n_ema   → component-ref (indicator.ema, 1)     override length ← ema_length
  node  n_z     → component-ref (indicator.zscore, 1)  override length ← z_length
  ...
  edge  (n_ema.out) → (n_z.reference)
```

**Red state recorded and resolved.** The first attempt failed: the grammar's `kind` list omitted
`bool`, and five of this strategy's fifteen parameters are booleans (`require_expansion`,
`allow_reexpansion`, `use_absz_contraction_exit`, `exit_on_drift_flip`, `exit_on_ema_cross`). The
real `KINDS` tuple in the running system already carries it. Resolved by adding `"bool"` to F5's
vocabulary — a grammar correction, not a new clause, and therefore no new migration liability.

**Observation, not a defect.** The four canonical output sockets are exactly the four boolean
columns the current engine contract mandates. The IR expresses them as ordinary typed output
sockets, which means the four-column contract becomes a convention of one component family rather
than a property of the language. That is the intended direction and requires no clause.

### A.2 A decomposed ATR indicator

```
component-def
  identifier    "indicator.atr.wilder"
  version       1
  display-name  "ATR (Wilder)"
  interface
    socket    high    input  wire-type(float, series, (instrument, timeframe))
    socket    low     input  wire-type(float, series, (instrument, timeframe))
    socket    close   input  wire-type(float, series, (instrument, timeframe))
    parameter length  length default 14
    socket    atr     output wire-type(float, series, (instrument, timeframe))
  body graph-ref →
        node n_tr     → component-ref (indicator.true_range, 1)
        node n_smooth → component-ref (smoothing.wilder, 1)  override length ← length
        edge (n_tr.out) → (n_smooth.in)
```

**This is the example the acceptance set exists for.** Because the body is a graph rather than a
kernel, "fork ATR, replace the smoothing" is a new version of `indicator.atr.wilder` whose
`n_smooth` node references `smoothing.ema` instead — expressible as a component reference change,
with F3 recording the parent.

**Red state recorded — a defect in the current system, not in the RFC.** The running block library
has no ATR *component* at all. Wilder's ATR is a private helper (`_atr`), and every public block
returns `Series[bool]`: ATR appears only inside boolean predicates such as `atr_pct_lt(length,
max_pct)` and `range_atr_lt(length, mult)`. There is no float-valued output anywhere in the
vocabulary, so a value like ATR cannot be named, shared, or forked today. The IR expresses this
artefact without amendment — F7's value axis already admits float-valued series. **The gap is in
`blocks.py`, which is precisely the Generation-2 failure C15 exists to close.** No clause was
added.

### A.3 A generated strategy from the block grammar

A generated strategy composes named blocks with bounded numeric arguments. Each block becomes a
`component-ref` with overrides; the composition becomes edges:

```
graph-def
  identifier   "generated.<content-hash>"
  version      1
  node n_1 → component-ref (block.atr_pct_lt, 1)    override length ← 14, max_pct ← 3.0
  node n_2 → component-ref (block.range_atr_lt, 1)  override length ← 14, mult   ← 0.8
  node n_3 → component-ref (logic.and, 1)
  edge (n_1.out) → (n_3.a)
  edge (n_2.out) → (n_3.b)
```

**Observation.** Each block's `BlockSpec` already declares `(param_name, kind)` pairs drawn from
the same bounded vocabulary as F5 — `length`, `pct`, `mult`. The block registry is therefore
already most of a component interface; what it lacks is F2's version and F4's declared panels.

**Red state recorded and resolved without a clause.** Generated strategies currently identify
themselves by a content hash over their source. Under F2 that is the *body's* content address, not
the identity: identity is `(identifier, version)`. Expressible as written above — the hash becomes
the identifier's suffix and the version starts at 1. This is the concrete case D-disproof (d) in
the findings warned about: identity MUST NOT be the definition, because reformatting would
otherwise be a semantic change.

### A.4 A nested subgraph

A graph referencing A.2 twice, at two lengths:

```
graph-def
  identifier "strategy.dual_atr_filter"
  node n_fast → component-ref (indicator.atr.wilder, 1)  override length ← 7
  node n_slow → component-ref (indicator.atr.wilder, 1)  override length ← 21
  edge (n_fast.atr) → (n_cmp.a)
  edge (n_slow.atr) → (n_cmp.b)
```

This exercises F11, C4 and C7 together. After resolution, an observer MUST be able to see:

- every node expanded from `indicator.atr.wilder` traceable to its definition, and to *which*
  instance it came from — `n_fast` and `n_slow` expand from the same definition and MUST remain
  distinguishable (C4);
- identical instance identifiers on a second resolution of the same specification, because they
  derive from the instance path — `n_fast/n_smooth`, `n_slow/n_smooth` — rather than from a
  counter (C7);
- an error inside the smoothing node reported against the authored graph's vocabulary, naming
  `n_fast`, not against a generated node the author never placed (C4).

No mechanism is prescribed for how any of this is achieved.

### A.5 A multi-timeframe case

```
node n_5m  → component-ref (indicator.ema, 1)  override length ← 20
             domain (NIFTY, 5m)
node n_15m → component-ref (indicator.ema, 1)  override length ← 20
             domain (NIFTY, 15m)
node n_cmp → component-ref (compare.gt, 1)
edge (n_5m.out)  → (n_cmp.a)     -- domain (NIFTY, 5m)
edge (n_15m.out) → (n_cmp.b)     -- domain (NIFTY, 15m)   ✗ ill-typed
```

The final edge is **ill-typed under F7**: both wires carry `float` values with `series` structure,
and would connect under a one-axis type system, but their domains differ. Comparing a 5-minute
series to a 15-minute series is exactly the class of error that produces a plausible backtest and
an unreproducible live result. Making it a *type* error rather than a runtime surprise is the
purpose of the domain axis.

Expressing this requires an explicit resampling component whose declared interface changes the
timeframe domain — which the language already admits, because the domain is part of the wire type
and a component's interface declares its sockets' wire types.

---

## Appendix B — Traceability (informative)

**A clause with no traceable decision or pattern is a preference, not a finding, and MUST be cut.**
Decisions `D#` refer to `~/dev/multiverse-of-ideas/reviews/_FINDINGS-component-ir.md` §4; patterns
`P#` to `_PATTERNS.md`.

| Clause | Statement | Decision | Pattern |
|---|---|---|---|
| F1 | Artefact records format version and kind | D3 | P3 |
| F2 | Immutable identifier, version, content-addressed body | D1, D2 | P1, P2 |
| F3 | A version may record its parent | D1 | P2 |
| F4 | Interface is declared, not inferred | D9 | P10 |
| F5 | Parameters carry a kind from a closed vocabulary | D2 | P1 |
| F6 | Secrets are references, never values | D16 | P12 |
| F7 | Two-axis typing plus domain, closed and exact | D11, D12, D22 | P8 |
| F8 | Inputs declare a default source | D19 | P14 |
| F9 | A graph is nodes and edges | D1 | P2 |
| F10 | Overrides carry values only | D15 | P11 |
| F11 | Nesting by reference, never inlined | D7 | P5 |
| F12 | Visual grouping ≠ semantic reuse | D18 | P9 |
| F13 | Semantic hashed; presentation stored beside | D17 | P13 |
| F14 | Results bind to the versions that produced them | D4 | P2, P3 |
| C1 | Resolution is deterministic | D5 | P5, P7 |
| C2 | Resolution has no side effects | D5 | P5 |
| C3 | Resolution preserves semantics | D5 | P7 |
| C4 | Derived elements carry back-references | D8 | P6 |
| C5 | Version identity preserved and recorded | D1, D4 | P2 |
| C6 | No hidden state introduced | D5 | P5 |
| C7 | Reproducible; ids from the instance path | D7 | P5 |
| C8 | Transitive by default, declarable per component | D13 | P4 |
| C9 | Pure components; impurity declared as policy | D14 | P4 |
| C10 | Warmup derived per component, composes | D22 | P8 |
| C11 | Lookahead prevented structurally | D22 | P8 |
| C12 | One resolution shared by research and live | D6 | P7 |
| C13 | Executor never branches on provenance | D21 | P2 |
| C14 | Sweeping belongs to the searcher | D20 | P4 |
| C15 | Publishing a subgraph is mechanical | D10 | P10 |

### B.1 Terminology mapping

The findings and patterns use different words for the same things. A reader moving between the two
documents needs this table.

| This RFC | The findings / patterns | Note |
|---|---|---|
| **Resolution** | "lowering" (P5, P7, D5, D6) | the whole stage |
| **Lowering** | part of "lowering" | one operation within resolution: deterministic structural expansion of nested references |
| **Specification** | "the recorded graph", "the authored graph" | |
| **Resolved graph** | "the executed graph", "the evaluation graph" | |

The narrowing of "lowering" is deliberate. Two names for one concept is the shape of the
`candles.py` defect — two hand-written implementations of one idea — and a constitution is the
worst place to seed it.

---

## Appendix C — Open questions carried forward (informative)

These are carried **inside** the constitution deliberately. A frozen architecture that hides its
own soft spots is how drift begins. Each names the trigger that would reopen it.

### C(a) Fork semantics beyond a parent pointer

No system studied has a real fork relation — Langflow makes every graph a fork, the rest have
none. The parent-pointer model in F3 is therefore *derived* rather than *observed*.
**Trigger:** the first request for merge, rebase, or divergence display. Additive metadata on a
version record; not a change to how graphs reference components.

### C(b) Field and structure inference rules in our domain

Blender's `Auto` inference proves inference works, but their rules concern geometry domains, not
bars and instruments. Ours must be derived from our own semantics. F7 freezes the two-axis
**shape**; the inference algorithm sits above the format.
**Trigger:** the first component that cannot declare its structure.

### C(c) Migration machinery

The preconditions (F1, F2) are adopted; the machinery is deferred.
**Trigger:** the first breaking amendment.

### C(d) Whether and when the live engine executes IR graphs

C12 says it eventually must. That is a production change to a real-money path and needs its own
phase with its own parity evidence, in the compile-first / adopt-second order this platform already
uses for the decision kernel and the strategy specification. **This is a migration question, not a
language question.**
**Trigger:** its own phase.

### C(e) Tick-level and intrabar strategies

C10 and C11 rest on this platform acting on completed candles only.
**Trigger:** any intrabar strategy. `~/dev/multiverse-of-ideas/reviews/nautilus-trader.md` §10 is
the note to whoever revisits it.

### C(f) Marketplace trust and sandboxing at scale

The existing AST allow-list is stronger than anything in the nine systems studied — none of them
sandbox user code at all. Sandboxing constrains what a *kernel* may do, which is a property of the
kernel registry rather than of the graph language.
**Trigger:** third-party component distribution.
