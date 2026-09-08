Reference: [section index](../0001-component-ir.md). Read with its scope; this is not a new assignment.

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
