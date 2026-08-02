# Design — Component IR RFC v1.0

**Date:** 2026-08-02 · **Status:** approved design, ready for implementation planning

This document specifies **what the RFC must contain and how we will know it is finished**. It is
not the RFC. The deliverable it produces is a single normative document at
`paper-trader/docs/rfcs/0001-component-ir.md`.

---

## 1. What we are building, and why now

The evidence base is `~/dev/multiverse-of-ideas/reviews/` — nine systems read (ComfyUI, vectorbt,
NautilusTrader, Node-RED, Blender, Langflow, xyflow, Airflow, Prefect) plus the OpenAlgo teardown
in this repo's `docs/`. `_FINDINGS-component-ir.md` records 24 stable decisions and six honest
gaps, and argues that none of the gaps is large enough to materially change the language.
`_PATTERNS.md` records 14 reusable patterns (P1–P14). Those two files are the sole input; this
design adds no new architecture.

The recommendation those findings end on is *freeze the architecture and begin RFC v1.0*. This
design is that beginning.

**Deliverable:** a prose document. No schema, no validator, no runtime. Explicitly chosen by the
owner over a document-plus-executable-schema option.

**The risk that choice carries, stated once and then mitigated rather than re-argued.** This
codebase's signature defect is a mechanism that exists and is wired to nothing, and its worst
form is *prose that claims a wiring which does not exist* — a docstring asserted DSR deflation
was engaged while `var_sr` was computed nowhere, invalidating every research finding predating
2026-08. A normative document with nothing validating it is that failure mode by construction.

**The mitigation is structural, not a promise to be careful:**

1. The acceptance gate (§7) is an *expressiveness* test against a fixed set of real artefacts, so
   the document is falsifiable before it is accepted.
2. Appendix B requires every normative clause to trace to a decision in the findings. A clause
   that cannot be traced is someone's preference and is cut.
3. §5 of the RFC (Non-goals) and Appendix C (open questions) keep what v1 does *not* settle
   inside the document, where a reader will find it.
4. The conformance suite is named as an explicit follow-on phase in the roadmap, not assumed into
   existence. Until it exists, the RFC's status line says so in its own words.

Point 4 matters most: an unvalidated constitution is acceptable *if the document admits it*. It
becomes the old failure only if it claims enforcement it does not have.

---

## 2. Scope

**In scope:** one document defining the Component IR — the language every subsystem speaks.

**Out of scope, each its own later spec→plan→build cycle:** the component runtime, the visual
computational graph editor, Python component authoring, Research Plane Generation 2, the
experiment system, the marketplace, deployment, production adoption. The owner's roadmap lists
nine subsystems; that is a programme, not a specification. Only the first item is specified here.

**Deliberately not touched:** the live real-money execution path. Findings §6(d) classifies
"should the live engine execute IR graphs, and when" as a *migration* question rather than a
language question. It gets its own phase and its own parity evidence, in the compile-first /
adopt-second order `spec.py:30-33` already established.

---

## 3. The two ideas that organise the document

### 3.1 Format clauses vs Contract clauses

Decision 23 says the IR core stays minimal because every concept added is one we hand-write
migrations for forever — Blender pays 44,246 lines for this (P3). But that cost is paid **only
for concepts that get serialised into an artefact**. A guarantee costs nothing to migrate: "the
executor never branches on a component's provenance" adds zero bytes to a stored graph.

So the RFC has two kinds of normative clause, marked apart explicitly:

| | **Format clauses (§3)** | **Contract clauses (§4)** |
|---|---|---|
| What they are | What is written down and read back | Guarantees any conforming implementation must satisfy |
| Migration cost | Permanent — every addition is migrated forever | None |
| Discipline | Ruthless minimality | Completeness |
| Expressed as | A formal grammar plus prose | Observable properties, never algorithms |

This converts decision 23 from advice into a rule someone can apply under pressure: *additions to
§3 cost migrations forever; additions to §4 are free.* This distinction is load-bearing and must
be visible in the document's structure, not merely stated in its preface.

### 3.2 Specification → Resolution → Execution

Three stages, formally separated, and the separation stays visible throughout the document. Its
purpose is to prevent authoring concepts leaking into execution semantics.

| Stage | What it is | Governed by |
|---|---|---|
| **Specification** | A component's (and graph's) serialised form. The artefact. | Format clauses (§3) |
| **Resolution** | Transforms a specification into a fully bound executable graph — resolving component references, versions, kernels and dependencies. | Contract clauses (§4) |
| **Execution** | The runtime evaluates the resolved graph. | Contract clauses (§4); mechanism out of scope |

**Terminology reconciliation — deliberate and load-bearing.** The findings and patterns say
*lowering* (P5, P7); this design says *Resolution*. The RFC uses **Resolution** as the name of the
stage, and defines **lowering** once, as the name of one operation *within* resolution: the
deterministic structural expansion of nested references. Two names for one idea is precisely the
shape of the `candles.py` defect — two hand-written implementations of one concept — and a
constitution is the worst possible place to seed it. Appendix B carries the mapping so readers of
the findings are not lost.

The RFC does **not** prescribe how resolution works. Graph rewriting, lazy expansion,
canonicalisation, optimisation passes, or something not yet invented are all conforming, provided
the observable properties in §4 hold.

---

## 4. The RFC's structure

`paper-trader/docs/rfcs/0001-component-ir.md`. A new `rfcs/` directory — a constitution filed
among dated audit reports reads as another audit report. Numbered `0001` so the series can grow.

| § | Section | Kind |
|---|---|---|
| — | **Preface** — why the IR exists; why a language; why every subsystem speaks it; why Format vs Contract clauses | informative, precedes all normative text |
| 1 | Status, the central principle, the five planes, and Specification/Resolution/Execution | normative framing |
| 2 | Terminology and conformance language (RFC 2119 MUST / SHOULD / MAY) | normative framing |
| 3 | **Format clauses** — the serialised core, with an embedded formal grammar | normative, migratable |
| 4 | **Contract clauses** — observable properties every implementation must satisfy | normative, free |
| 5 | Non-goals — what v1 deliberately does not define, each with its reason | normative framing |
| 6 | Amendment procedure | normative |
| A | Worked examples — real current artefacts expressed in the IR | informative |
| B | Traceability — every clause → its decision/pattern; plus the lowering↔Resolution mapping | informative |
| C | Open questions carried forward — the six gaps, each with its revisit trigger | informative |

The Preface is informative and comes first so a future reader has context before formal language.
It must be short — its job is orientation, not persuasion; the argument already lives in the
findings.

---

## 5. RFC §1 — the central principle and the planes

### 5.1 The principle, stated near the top of the document

> **The Component IR is the canonical representation of strategy intent.**
>
> Not strategy execution. Not source code. Not UI state. Not runtime state.
>
> Every other representation — Python, visual graphs, marketplace packages, runtime objects,
> resolved graphs — either **produces** the IR, **consumes** the IR, or is **deterministically
> derived** from it. The IR itself is the source of truth.

### 5.2 The five planes

The IR must know nothing about UI, search algorithms, optimisation strategies, or marketplace
workflows. It defines the language all of them speak.

| Plane | Concern | Relationship to the IR |
|---|---|---|
| **Language** | The IR itself | *is* the IR |
| **Runtime** | How a resolved graph executes | consumes |
| **Research Plane** | How graphs are generated and searched | produces and consumes |
| **Editor** | How humans author graphs | produces |
| **Marketplace** | How components are distributed | transports |

This makes misfiling detectable rather than a matter of taste: **any clause naming a UI concern, a
search algorithm, an optimisation strategy, or a marketplace workflow is misfiled by
construction**, and the review gate checks for exactly that.

---

## 6. RFC §3 and §4 — required content

The clause lists below are the *required coverage*, not the finished text. Each entry names its
evidence. Anything not traceable does not go in.

### 6.1 §3 Format clauses — the serialised core

| # | Clause | Evidence |
|---|---|---|
| F1 | **Artefact envelope** — every stored artefact records its `format_version` and its kind | D3, P3 |
| F2 | **Component identity** — immutable `identifier` + `version`; body stored once, content-addressed; display name separate and mutable | D1, D2, P1, P2 |
| F3 | **Version records** — a version MAY record a parent version (fork); §6(a) notes this is derived, not observed | D1, gap (a) |
| F4 | **Declared interface** — a recursive tree of `Panel \| Socket` items; declared, never inferred from internals | D9, P10 |
| F5 | **Parameter schema** — bounded vocabulary of kinds; each parameter has identifier, kind, bounds, default, display name | D2, P1; existing `spec.py` KINDS |
| F6 | **`SECRET` parameter kind** — value is a reference; never serialised into an artefact | D16, P12 |
| F7 | **Wire types** — two axes (value type × structure type, the structure axis carrying at least `{scalar, series}`) plus a domain (instrument/timeframe), with inference; closed set, versioned, exact-matched. The *inference rules* are a layer above the format and are not frozen here — findings §6(b) | D11, D12, D22, P8 |
| F8 | **Default input sources** — an input declares where an unwired value comes from, making partially-wired graphs valid | D19, P14 |
| F9 | **Graph** — nodes (instance identifier + component reference + parameter overrides) and edges (source socket → target socket) | D1, D2 |
| F10 | **Overrides carry values only** — never kind, bounds, or label; structurally impossible to do otherwise | D15, P11 |
| F11 | **Static nesting by reference** — a node whose component resolves to a subgraph; by reference only, never inlined | D7, P5 |
| F12 | **Visual grouping is a separate construct** from semantic reuse | D18, P9 |
| F13 | **Presentation state separated** — semantic content is hashed; layout persists beside the graph keyed by stable identifier; ephemeral state is never persisted | D17, P13 |
| F14 | **Result binding** — every experiment/finding records the exact graph version and resolved component versions that produced it | D4, P2, P3 |

F14 is the clause our own history most demands: research findings predating 2026-08 are permanently
unattributable for exactly this reason, and Airflow's `DagVersion` retrofit proves the cost of
adding it late (D5, findings §3E).

### 6.2 §4 Contract clauses — observable properties

Stated as properties. Never as algorithms.

| # | Clause | Evidence |
|---|---|---|
| C1 | **Determinism** — the resolved graph is a deterministic function of the specification | D5, P5, P7 |
| C2 | **Side-effect freedom** — resolution has no observable effects | D5, P5 |
| C3 | **Semantic preservation** — resolution preserves the meaning of the specification | D5, P7 |
| C4 | **Provenance preservation** — every derived, expanded, or inserted element carries a back-reference to its definition; diagnostics speak the authored graph's vocabulary | D8, P6 |
| C5 | **Version identity preservation** — resolution preserves and records every resolved `(identifier, version)` | D1, D4, P2 |
| C6 | **No hidden state** — resolution introduces no state not derivable from the specification | D5 |
| C7 | **Reproducibility** — the same specification resolves identically; instance identifiers derive from the instance path, never from clocks or counters | D7, P5 |
| C8 | **Cache identity** — transitive over the upstream subgraph by default, and declarable per component | D13, P4 |
| C9 | **Purity as capability** — components are pure; impurity is a declared policy, never an escape hatch | D14, P4, findings §2F |
| C10 | **Warmup semantics** — warmup is derived per component and composes through the graph | D22 |
| C11 | **Lookahead prevention is structural**, not a convention a component can violate | D22 |
| C12 | **Research/live parity** — one resolution shared by both planes; this is what makes parity structural rather than tested | D6, P7 |
| C13 | **Provenance-blind execution** — no executor path branches on where a component came from; enforce with a test | D21, findings §2D |
| C14 | **Searcher boundary** — components compute; searchers search. Parameter sweeping is never a component's job | D20, findings §2E |
| C15 | **Subgraph/component equivalence** — publishing a subgraph as a component is a mechanical derivation from its declared interface, introducing no information the interface does not already carry | D10, P10 |

C14 names the trap we are currently in: the research plane inherited vectorbt's shape, where
sweeping is built into the component contract, which silently defines *search = parameter
sweeping* for everything downstream.

C15 is what makes components **decomposable** — a subgraph and a component are the same kind of
thing, so an indicator is itself a graph. This is the Generation-2 requirement `blocks.py` fails
today, and it is why "fork ATR, replace the smoothing" is currently unrepresentable rather than
merely unbuilt. It is a contract clause, not a marketplace concern: it constrains the language,
and distribution is a separate plane.

### 6.3 §5 Non-goals

Each stated with its reason: no runtime or execution mechanism; no migration machinery (adopt P3's
preconditions, defer the machinery to the first real migration — building it earlier is
speculative, per findings §6(c)); no marketplace trust model; no editor or UI concepts; no search
or optimisation strategy; **forward compatibility explicitly declined** (D24 — Blender's constraint
that an old binary must read a new file is not ours); no tick-level or intrabar semantics (D22
rests on our being completed-candle only; `reviews/nautilus-trader.md` §10 is the revisit trigger).

### 6.4 §6 Amendment procedure

What constitutes a breaking change to the language; erratum vs new RFC; how `format_version`
increments relate to amendments; who accepts an amendment; and the rule that every new capability
must either fit inside the IR or justify an RFC that changes it. A constitution that does not say
how it is amended gets amended informally — which is the drift this whole exercise exists to
prevent.

---

## 7. Acceptance — how we know it is done rather than merely written

Two gates, then owner acceptance.

### Gate 1 — Expressiveness (objective)

The language MUST be shown to express this fixed set of real artefacts, written out in Appendix A.
**Failure to express any one of them is a defect in the RFC, not in the example.**

1. The EMA-z strategy (the current default; real parameters)
2. An ATR indicator — decomposed, so that "fork ATR, replace the smoothing" is representable.
   `blocks.py` fails this today, which is why it is in the set
3. One generated strategy from the research plane's block grammar
4. One nested subgraph — exercising F11, C4 and C7 together
5. One multi-timeframe case — exercising the domain axis of F7

### Gate 2 — Adversarial review

A review pass hunting specifically for: underspecification; clauses admitting two readings;
clauses naming the wrong plane (§5.2); clauses in §3 that could live in §4 without weakening a
guarantee (each is a permanent migration liability); clauses with no Appendix B traceability; and
any claim of enforcement the document does not actually have.

### Gate 3 — Owner acceptance

### Explicitly **not** in the acceptance bar

Executable validation. The owner chose a document-only deliverable. The conformance suite is a
named follow-on phase, and until it exists the RFC's status section says so in its own words.

---

## 8. Constraints and preconditions

**The working tree is dirty — 48 files before this spec was added, the entire enterprise
architecture migration, Phases A–H
(`docs/2026-08-02-architecture-migration.md`), none of it committed and therefore none of it
deployed** (`deploy.sh` refuses a dirty tree). Phase E is this work's direct ancestor: `spec.py`
exists as a compiled contract that nothing executes.

This does not block the RFC — a document touches no code. It is recorded because the *next*
roadmap item (the runtime) cannot sensibly start on top of an unlanded migration, and because
committing this RFC means committing into a tree already carrying 48 uncommitted files. The
implementation plan must handle that explicitly rather than discover it.

**Repository boundary:** competitor code never enters the production tree. Only the prose reviews
cross over. The RFC cites reviews by path and quotes findings; it copies no code.

**Licence note carried from the library:** xyflow is MIT (the visual builder's rendering substrate
is a buy); vectorbt is Apache **+ Commons Clause** and is not open source — never a dependency.
Neither affects this document, and both are recorded so the next phase does not rediscover them.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| A prose constitution nothing validates drifts from reality | Gate 1 makes it falsifiable; the status section admits the absence of a conformance suite rather than implying one |
| §3 accumulates concepts that belong in §4, each costing migrations forever | The format/contract split is structural, and Gate 2 audits specifically for it |
| Clauses without evidence — preference dressed as finding | Appendix B traceability is mandatory; untraceable clauses are cut |
| Two names for one concept (lowering vs resolution) | Reconciled once in §3.2 above and mapped in Appendix B |
| Scope creep from the nine-subsystem roadmap into this document | §2 lists the eight out-of-scope subsystems by name |

---

## 10. Out of scope for this spec

The eight remaining roadmap subsystems (§2). The conformance suite. Any change to running code.
Any deployment.
