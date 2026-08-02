# Component IR RFC v1.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `paper-trader/docs/rfcs/0001-component-ir.md` — the normative, constitutional
specification of the Component IR, accepted against an objective expressiveness gate.

**Architecture:** One prose document, layered: informative Preface → normative framing (§1–2) →
**Format clauses** §3, the serialised core, carrying an embedded EBNF grammar → **Contract
clauses** §4, observable properties only → Non-goals §5 → Amendment procedure §6 → informative
appendices A (worked examples), B (traceability), C (open questions). The §3/§4 split is
load-bearing: additions to §3 cost hand-written migrations forever, additions to §4 cost nothing.

**Tech Stack:** Markdown. EBNF for the format grammar. RFC 2119 conformance language. No code, no
schema, no validator — the deliverable is a document by explicit owner decision.

## Global Constraints

- **Spec:** `paper-trader/docs/superpowers/specs/2026-08-02-component-ir-rfc-v1-design.md`. Every
  requirement below traces to it.
- **Evidence base (read-only, another repo):** `~/dev/multiverse-of-ideas/reviews/_FINDINGS-component-ir.md`
  (24 decisions D1–D24, six gaps) and `~/dev/multiverse-of-ideas/reviews/_PATTERNS.md` (P1–P14).
  **Cite by path and quote prose. Never copy competitor code into this repo.**
- **Commits require explicit owner approval.** `CLAUDE.md` says commit only when asked. Commit
  commands appear in each task but MUST NOT be run without the owner saying so.
- **Touch no running code.** This plan creates and edits documentation only. No file under
  `paper-trader/backend/app/` or `paper-trader/frontend/` is modified by any task.
- **The working tree is already dirty** (~48 files, the uncommitted enterprise architecture
  migration Phases A–H). Never run `git add -A` or `git commit -a`. Stage only the exact paths
  named in a task.
- **Conformance language:** RFC 2119 — MUST / MUST NOT / SHOULD / SHOULD NOT / MAY. Uppercase only
  when normative.
- **Terminology, fixed:** the stage is **Resolution**. **Lowering** is one operation within it
  (deterministic structural expansion of nested references). The findings say "lowering" for the
  whole stage; Appendix B carries the mapping. Never use the two words interchangeably.
- **Clause IDs are stable:** Format clauses `F1`–`F14`, Contract clauses `C1`–`C15`. Each appears
  exactly once in its §3/§4 table and exactly once in Appendix B.
- **Plane discipline:** no normative clause may name a UI concern, a search algorithm, an
  optimisation strategy, or a marketplace workflow.

---

## File Structure

| Path | Responsibility |
|---|---|
| `paper-trader/docs/rfcs/` | New directory. The RFC series. |
| `paper-trader/docs/rfcs/0001-component-ir.md` | The entire deliverable. Single file — it is one constitution, and splitting it was considered and rejected during brainstorming. |
| `paper-trader/docs/ROADMAP.md` | Modified once, in Task 8: record RFC v1.0 and name the conformance suite as a follow-on. |

The RFC is one file by design. It is expected to reach roughly 900–1,400 lines; that is
acceptable for a document whose whole purpose is to be read start-to-finish once and then cited
by section forever.

---

### Task 1: Scaffold, Preface, and normative framing (§1–§2)

**Files:**
- Create: `paper-trader/docs/rfcs/0001-component-ir.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the section headings `## 1.`…`## 6.`, `## Appendix A/B/C`, exactly as later tasks
  will fill them. The status block. The terminology definitions every later clause uses:
  *component, specification, resolution, lowering, execution, artefact, graph, node, socket,
  parameter, identifier, version, display name, plane*.

- [ ] **Step 1: Create the directory and the document skeleton**

Create `paper-trader/docs/rfcs/0001-component-ir.md` with every heading present and empty, in this
exact order, so later tasks never invent structure:

```markdown
# RFC 0001 — The Component IR

**Status:** Draft · **Version:** 1.0 · **Date:** 2026-08-02
**Supersedes:** nothing · **Amended by:** nothing

## Preface (informative)
## 1. Scope, principle, and planes
## 2. Terminology and conformance
## 3. Format clauses (normative — every clause here is migrated forever)
## 4. Contract clauses (normative — free to add)
## 5. Non-goals
## 6. Amendment procedure
## Appendix A — Worked examples (informative)
## Appendix B — Traceability (informative)
## Appendix C — Open questions carried forward (informative)
```

- [ ] **Step 2: Write the status block honestly**

Immediately under the status line, state the enforcement position in the document's own words.
This is the mitigation for the document-only deliverable and MUST NOT be softened:

```markdown
> **This RFC is normative prose. No conformance suite exists yet.** Nothing mechanically
> validates an artefact against §3, and nothing mechanically checks an implementation against
> §4. A conformance suite is a named follow-on phase, not an assumption of this document. Until
> it exists, conformance is a claim made by an implementer, not a fact established by a test.
```

- [ ] **Step 3: Write the Preface (informative, ≤ 600 words)**

Four questions, in order, each a short subsection. Orientation, not persuasion — the argument
already lives in the findings.

1. *Why the Component IR exists* — nine systems were studied across four domains; not one has
   both a durable component and a real composition model. Reference the table in
   `_FINDINGS-component-ir.md` §1 rather than reproducing it.
2. *Why we are introducing a language* — the platform is being rebuilt around
   Components → Graphs → Experiments → Deployments. Four sources of strategy (built-in,
   generated, visual, Python, marketplace) that each reduce to booleans and then run one
   hard-coded risk model are four skins on one strategy.
3. *Why every subsystem speaks it* — the runtime, research plane, editor and marketplace are
   interfaces over one language, not four abstractions.
4. *Why the constitution distinguishes Format clauses from Contract clauses* — Blender carries
   44,246 lines of version-migration code (P3). That cost is paid only for what is *serialised*.
   Guarantees are free. So §3 is minimised ruthlessly and §4 is completed thoroughly.

- [ ] **Step 4: Write §1 — the central principle, verbatim**

The principle is fixed text and MUST appear exactly as written in the spec:

```markdown
> **The Component IR is the canonical representation of strategy intent.**
>
> Not strategy execution. Not source code. Not UI state. Not runtime state.
>
> Every other representation — Python, visual graphs, marketplace packages, runtime objects,
> resolved graphs — either **produces** the IR, **consumes** the IR, or is **deterministically
> derived** from it. The IR itself is the source of truth.
```

- [ ] **Step 5: Write §1's five-plane table and the misfiling rule**

| Plane | Concern | Relationship to the IR |
|---|---|---|
| Language | The IR itself | *is* the IR |
| Runtime | How a resolved graph executes | consumes |
| Research Plane | How graphs are generated and searched | produces and consumes |
| Editor | How humans author graphs | produces |
| Marketplace | How components are distributed | transports |

Follow it with the normative rule: *A normative clause MUST NOT name a UI concern, a search
algorithm, an optimisation strategy, or a marketplace workflow. Such a clause is misfiled.*

- [ ] **Step 6: Write §1's Specification → Resolution → Execution separation**

Three stages as a table (specification = the serialised form, governed by §3; resolution =
transforms a specification into a fully bound executable graph by resolving component references,
versions, kernels and dependencies, governed by §4; execution = the runtime evaluates the resolved
graph). Then the normative sentence:

> This RFC does **not** prescribe how resolution is performed. Graph rewriting, lazy expansion,
> canonicalisation, optimisation passes, or a mechanism not yet invented are all conforming,
> provided the observable properties in §4 hold.

- [ ] **Step 7: Write §2 — terminology and conformance**

Define RFC 2119 usage. Then define every term later clauses depend on, each in one or two
sentences: *component, specification, resolution, lowering, execution, artefact, graph, node,
socket, parameter, identifier, version, display name, plane, kernel, subgraph, override*.
`lowering` MUST be defined explicitly as *one operation within resolution — the deterministic
structural expansion of nested references* — and MUST NOT be used as a synonym for resolution.

- [ ] **Step 8: Verify the skeleton is complete and ordered**

Run:
```bash
grep -n '^#\{1,2\} ' paper-trader/docs/rfcs/0001-component-ir.md
```
Expected: the eleven headings from Step 1, in that exact order, none missing, none added.

- [ ] **Step 9: Verify no term is used before it is defined**

Run:
```bash
grep -n -iE '\b(lowering|resolution|kernel|subgraph|override)\b' paper-trader/docs/rfcs/0001-component-ir.md | head -40
```
Expected: no occurrence of any of these terms in the Preface or §1 that §2 does not define. If §1
uses a term §2 defines later, that is acceptable (§2 is the glossary), but a term used *nowhere*
in §2 is a defect — add the definition.

- [ ] **Step 10: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md
git commit -m "docs(rfc): RFC 0001 skeleton — the principle, the planes, and the three stages"
```

---

### Task 2: §3 Format clauses and the EBNF grammar

**Files:**
- Modify: `paper-trader/docs/rfcs/0001-component-ir.md` (§3)

**Interfaces:**
- Consumes: §2's terminology.
- Produces: clause IDs `F1`–`F14`, and the EBNF production names Appendix A's worked examples must
  conform to: `artefact`, `envelope`, `component-def`, `interface`, `panel`, `socket`,
  `parameter`, `wire-type`, `graph-def`, `node`, `component-ref`, `override`, `edge`, `group`.

- [ ] **Step 1: Write the §3 preamble — the cost rule**

Open §3 with the rule that makes decision 23 operational:

> Every clause in this section describes something written into an artefact and read back. Each
> one is a permanent migration liability: a concept admitted here is a concept whose rewrite pass
> we hand-write for as long as the format lives. Blender carries 44,246 lines of such passes.
> **A clause belongs in §3 only if the guarantee it supports is impossible without serialising
> it.** If it can live in §4, it MUST live in §4.

- [ ] **Step 2: Write the EBNF grammar**

Insert this grammar as the normative structural definition. Prose clauses F1–F14 then constrain it.

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
               | "minute" | "secret" ;

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

- [ ] **Step 3: Write clauses F1–F14 as a table, then one normative paragraph each**

Each clause gets a row (ID, one-line statement, evidence) and then a paragraph containing at least
one MUST/MUST NOT sentence. Required content:

| # | Must assert | Evidence |
|---|---|---|
| F1 | Every artefact records `format_version` and kind. A reader MUST reject an artefact whose `format_version` it does not understand. | D3, P3 |
| F2 | `identifier` is immutable and never reused; `version` distinguishes bodies; the body is stored once, content-addressed; `display-name` is separate, editable, and MUST NOT be referenced by anything. | D1, D2, P1, P2 |
| F3 | A version MAY record a parent version. Fork semantics beyond the parent pointer are out of scope (Appendix C(a)). | D1, gap (a) |
| F4 | The interface is **declared**, a recursive tree of `Panel \| Socket` items. It MUST NOT be inferred from internals. | D9, P10 |
| F5 | Parameters carry identifier, display name, kind from a closed vocabulary, optional bounds, and a default. Kind is required — "it is a float" does not tell an editor whether `0.8` means 80% or 0.8 ATR. | D2, P1 |
| F6 | `secret` is a parameter kind whose value is a **reference**. A secret value MUST NOT appear in any artefact. | D16, P12 |
| F7 | A wire type is value type × structure type × domain. Structure carries at least `{scalar, series}` plus `auto` for inference. Domain carries instrument and timeframe. The set of value types is **closed, versioned, and exact-matched** — no wildcard, no overlap matching, no coercion by string comparison. | D11, D12, D22, P8 |
| F8 | An input MAY declare a default **source**, not merely a default value. A graph with unwired inputs that declare sources is valid. | D19, P14 |
| F9 | A graph is nodes and edges. A node carries an instance identifier, a component reference, and overrides. | D1, D2 |
| F10 | An override carries a **value only**. It MUST NOT carry kind, bounds, or display name. | D15, P11 |
| F11 | Nesting is **by reference**. A subgraph MUST NOT be inlined into a referencing graph. | D7, P5 |
| F12 | Visual grouping is a distinct construct from semantic reuse. A group MUST NOT be versionable or publishable. | D18, P9 |
| F13 | Semantic content is hashed. Presentation state persists **beside** the graph, keyed by stable identifier, and is not part of the artefact grammar. Ephemeral state is never persisted. | D17, P13 |
| F14 | Every experiment and every finding MUST record the exact graph version and every resolved component version that produced it. | D4, P2, P3 |

- [ ] **Step 4: Write the F14 rationale paragraph**

F14 carries the highest evidential weight in the document and MUST state why in the RFC itself:
Airflow needed `DagVersion` bound to *task instances* — execution history, not just definitions —
and got there only after a decade (D5, findings §3E). This project has already paid the same
price: every research finding in `research.db` predating 2026-08 is permanently unattributable.
Versioning's value is retrospective, so adding it late leaves every prior run unusable.

- [ ] **Step 5: Verify every F clause ID appears exactly once**

Run:
```bash
for i in $(seq 1 14); do
  printf 'F%-3s %s\n' "$i" "$(grep -c "\bF$i\b" paper-trader/docs/rfcs/0001-component-ir.md)"
done
```
Expected: each count ≥ 1 (Appendix B adds a second occurrence in Task 7). A count of 0 is a
missing clause.

- [ ] **Step 6: Verify no §3 clause names another plane**

Run:
```bash
sed -n '/^## 3\./,/^## 4\./p' paper-trader/docs/rfcs/0001-component-ir.md \
  | grep -n -iE 'marketplace|editor|UI|user interface|search|optimis|optimiz'
```
Expected: no hits in normative text. A hit is a misfiled clause per §1's rule — move it or cut it.
Hits inside an explicit "this is not a §3 concern" sentence are acceptable; judge each.

- [ ] **Step 7: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md
git commit -m "docs(rfc): §3 format clauses — the serialised core, and its grammar"
```

---

### Task 3: Expressiveness gate, part 1 — the red state that drives §3

**Files:**
- Modify: `paper-trader/docs/rfcs/0001-component-ir.md` (Appendix A examples 1–2; §3 as driven)
- Read: `paper-trader/backend/app/strategy/spec.py`,
  `paper-trader/backend/app/strategy/registry/`,
  `paper-trader/backend/research/strategy/builder/blocks.py`

**Interfaces:**
- Consumes: the EBNF production names and F1–F14 from Task 2.
- Produces: Appendix A examples 1 and 2, and any F-clause corrections they force.

**This is the plan's test cycle.** The spec states: *failure to express any named artefact is a
defect in the RFC, not in the example.* Do not adjust an example to fit the language.

- [ ] **Step 1: Read the real artefacts before writing anything**

Run:
```bash
sed -n '1,120p' paper-trader/backend/app/strategy/spec.py
grep -rn 'def signals' paper-trader/backend/app/strategy/registry/ | head
grep -n 'atr\|ATR' paper-trader/backend/research/strategy/builder/blocks.py | head -20
```
Use the real parameter names and real defaults. An example with invented parameters proves nothing.

- [ ] **Step 2: Express example 1 — the EMA-z strategy — against the grammar**

Write it as a concrete artefact conforming to `graph-def`, using the real parameters
(`ema_length`, `z_length`, `entry_z`, `slope_lookback`). Walk it production by production.

- [ ] **Step 3: Record every point where the language could not express it**

For each failure write one line: *what could not be said, and which clause would be needed.* Do
not fix anything yet. This is the red state and it MUST be written down before it is resolved —
an undocumented gap that is silently patched is how a clause without evidence enters the document.

- [ ] **Step 4: Express example 2 — a decomposed ATR indicator**

ATR MUST be expressible as a `graph-def`, not an opaque leaf, such that "fork ATR, replace the
smoothing" is representable. `blocks.py` fails this today — that is precisely why this example is
in the acceptance set. Record failures as in Step 3.

- [ ] **Step 5: Resolve each recorded failure by amending §3, minimally**

For each failure, decide: does resolving it require **serialising** something new? If not, it
belongs in §4 (defer it to Task 4 and note it). If yes, add the minimum to §3 and give it the next
free `F` id. Every addition MUST carry evidence from `_FINDINGS-component-ir.md` or `_PATTERNS.md`.
An addition with no evidence is a preference — cut it and re-express the example.

- [ ] **Step 6: Re-walk both examples against the amended grammar**

Expected: both express cleanly, with no remaining recorded failure that is not explicitly deferred
to §4 with a named clause.

- [ ] **Step 7: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md
git commit -m "docs(rfc): express the EMA-z strategy and a decomposed ATR; amend §3 where they could not be said"
```

---

### Task 4: §4 Contract clauses

**Files:**
- Modify: `paper-trader/docs/rfcs/0001-component-ir.md` (§4)

**Interfaces:**
- Consumes: §1's Specification/Resolution/Execution separation; any clause Task 3 deferred here.
- Produces: clause IDs `C1`–`C15`.

- [ ] **Step 1: Write the §4 preamble — properties, never algorithms**

> Every clause in this section states an **observable property** that a conforming implementation
> must exhibit. None prescribes a mechanism. These clauses are free: they add nothing to an
> artefact and therefore require no migration, so this section is completed thoroughly where §3
> is minimised ruthlessly.

- [ ] **Step 2: Write clauses C1–C15, each with at least one MUST sentence**

| # | Must assert | Evidence |
|---|---|---|
| C1 | The resolved graph MUST be a deterministic function of the specification. | D5, P5, P7 |
| C2 | Resolution MUST be free of observable side effects. | D5, P5 |
| C3 | Resolution MUST preserve the specification's semantics. | D5, P7 |
| C4 | Every derived, expanded, or inserted element MUST carry a back-reference to the definition it came from. Diagnostics MUST speak the authored graph's vocabulary, not the resolved graph's. | D8, P6 |
| C5 | Resolution MUST preserve and record every resolved `(identifier, version)`. | D1, D4, P2 |
| C6 | Resolution MUST NOT introduce state that is not derivable from the specification. | D5 |
| C7 | The same specification MUST resolve identically. Instance identifiers MUST derive from the instance path — never from clocks, counters, or randomness. | D7, P5 |
| C8 | Cache identity MUST be transitive over the upstream subgraph by default, and MAY be declared per component. | D13, P4 |
| C9 | Components MUST be pure. Impurity MUST be a declared policy and MUST NOT be available as an escape hatch. | D14, P4 |
| C10 | Warmup MUST be derived per component and MUST compose through the graph. | D22 |
| C11 | Lookahead MUST be prevented structurally. A component MUST NOT be able to violate it by convention. | D22 |
| C12 | Research and live MUST share one resolution. | D6, P7 |
| C13 | No executor path may branch on a component's provenance. | D21, findings §2D |
| C14 | Components compute; searchers search. Parameter sweeping MUST NOT be part of a component's contract. | D20, findings §2E |
| C15 | Publishing a subgraph as a component MUST be a mechanical derivation from its declared interface, introducing no information the interface does not already carry. | D10, P10 |

- [ ] **Step 3: Write the C12 rationale paragraph**

C12 is what makes research/live parity **structural rather than tested**. State the precedent
plainly: the `candles.py` defect this project already suffered came from two hand-written
implementations of one idea, not from a compilation step. Parity does not require interpreting the
authored graph — the interpret-versus-compile framing was a false dichotomy, disproven by Blender,
the most mature node system in existence, which lowers. What parity requires is *one* resolution
used by both planes.

- [ ] **Step 4: Write the C9 rationale paragraph**

ComfyUI's `IS_CHANGED` escape hatch makes the cache correct while destroying its value as a
provenance claim. Prefect shows the principled alternative: declare identity as a policy. Neither
system has both transitivity and declarability — C8 and C9 together take both.

- [ ] **Step 5: Write the C13 enforcement note**

D21's evidence is ComfyUI achieving provenance-blindness *subtractively* — one registry, no plugin
API. State that `StrategyMetadata.source` is display-only, and that given this codebase's history
with unconsumed mechanisms, C13 is to be enforced by a test in the conformance phase rather than
by review.

- [ ] **Step 6: Verify every C clause ID appears, and that §4 prescribes no mechanism**

Run:
```bash
for i in $(seq 1 15); do
  printf 'C%-3s %s\n' "$i" "$(grep -c "\bC$i\b" paper-trader/docs/rfcs/0001-component-ir.md)"
done
sed -n '/^## 4\./,/^## 5\./p' paper-trader/docs/rfcs/0001-component-ir.md \
  | grep -n -iE 'algorithm|implemented by|the runtime should use|pass over|traverse'
```
Expected: every C id present. The second command should return nothing in normative text — a hit
means a clause has drifted from property into mechanism.

- [ ] **Step 7: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md
git commit -m "docs(rfc): §4 contract clauses — the guarantees, stated as properties"
```

---

### Task 5: Expressiveness gate, part 2 — the examples that exercise §4

**Files:**
- Modify: `paper-trader/docs/rfcs/0001-component-ir.md` (Appendix A examples 3–5; §3/§4 as driven)
- Read: `paper-trader/backend/research/strategy/builder/grammar.py`,
  `paper-trader/backend/app/core/generated_strategies.py`

**Interfaces:**
- Consumes: F1–F14, C1–C15.
- Produces: Appendix A examples 3, 4, 5, complete.

- [ ] **Step 1: Read the real block grammar and a real generated strategy**

Run:
```bash
sed -n '1,80p' paper-trader/backend/research/strategy/builder/grammar.py
head -60 paper-trader/backend/app/core/generated_strategies.py
```

- [ ] **Step 2: Express example 3 — a real generated strategy from the block grammar**

Use an actual generated strategy, not a plausible one. Record failures as in Task 3 Step 3.

- [ ] **Step 3: Express example 4 — a nested subgraph**

This example MUST exercise F11 (nesting by reference), C4 (back-references survive expansion) and
C7 (instance ids derive from the instance path) together. Show the authored form and describe —
without prescribing an algorithm — what an observer must be able to see after resolution: every
expanded node traceable to its definition, and identical ids on a second resolution.

- [ ] **Step 4: Express example 5 — a multi-timeframe case**

Exercises F7's domain axis. Show two instruments or two timeframes flowing through typed wires,
and where the domain makes an otherwise-valid connection ill-typed.

- [ ] **Step 5: Resolve recorded failures, minimally, with evidence**

For each recorded failure, decide: does resolving it require **serialising** something new? If
not, it belongs in §4 — add it there with the next free `C` id. If yes, add the minimum to §3 with
the next free `F` id. Every addition MUST carry evidence from
`~/dev/multiverse-of-ideas/reviews/_FINDINGS-component-ir.md` or `_PATTERNS.md`. An addition with
no evidence is a preference — cut it and re-express the example without it.

- [ ] **Step 6: Verify Gate 1 is met**

All five named artefacts express cleanly. Run:
```bash
sed -n '/^## Appendix A/,/^## Appendix B/p' paper-trader/docs/rfcs/0001-component-ir.md \
  | grep -c '^### '
```
Expected: `5`. Fewer means the acceptance set is incomplete.

- [ ] **Step 7: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md
git commit -m "docs(rfc): the remaining three worked examples — Gate 1 met"
```

---

### Task 6: §5 Non-goals and §6 Amendment procedure

**Files:**
- Modify: `paper-trader/docs/rfcs/0001-component-ir.md` (§5, §6)

**Interfaces:**
- Consumes: all clauses.
- Produces: the amendment vocabulary Appendix C references — *erratum*, *non-breaking amendment*,
  *breaking amendment*.

- [ ] **Step 1: Write §5 — each non-goal with its reason**

Seven, each one or two sentences:

1. **No runtime or execution mechanism** — §4 states properties; how they are achieved is the
   runtime's RFC.
2. **No migration machinery** — the preconditions (F1's version stamp, F2's stable identifiers)
   are adopted now; the machinery waits for the first real migration. Building it earlier is
   speculative (findings §6(c)).
3. **No marketplace trust or sandboxing model** — it constrains what a component *kernel* may do,
   a property of the kernel registry, not of the graph language (findings §6(f)).
4. **No editor or UI concepts** — a different plane.
5. **No search or optimisation strategy** — a different plane; and C14 makes the boundary
   normative.
6. **Forward compatibility is explicitly declined** — D24. Blender's constraint, that an old
   binary must read a newer file, is not ours. Backward compatibility is adopted; forward
   compatibility is not, and this MUST be stated so no future reader assumes it.
7. **No tick-level or intrabar semantics** — C10/C11 rest on our being completed-candle only.
   `~/dev/multiverse-of-ideas/reviews/nautilus-trader.md` §10 is the recorded trigger to revisit.

- [ ] **Step 2: Write §6 — what counts as a breaking change**

Define three change classes normatively:

- **Erratum** — corrects wording without changing any conforming artefact or implementation. No
  `format_version` increment.
- **Non-breaking amendment** — adds an optional construct or a new clause that no existing
  artefact violates. `format_version` increments; older artefacts remain readable unchanged.
- **Breaking amendment** — changes or removes an existing construct, or adds a required one.
  `format_version` increments **and** a migration pass MUST ship with it. Per §5(6), no forward
  compatibility is promised: a reader of an older `format_version` MUST reject a newer artefact
  rather than guess.

- [ ] **Step 3: Write §6's process rule**

> Every new platform capability MUST either fit inside this IR unchanged, or be accompanied by an
> RFC that amends it. There is no third path. A capability that quietly extends the language
> without an amendment is architectural drift, and this section exists to make that
> distinguishable from ordinary work rather than to forbid it in spirit only.

State who accepts an amendment (the owner) and that an amendment MUST pass the same expressiveness
gate the original did, re-run over Appendix A's examples.

- [ ] **Step 4: Verify §5 and §6 are complete**

Run:
```bash
sed -n '/^## 5\./,/^## 6\./p' paper-trader/docs/rfcs/0001-component-ir.md | grep -c '^[0-9]\.'
grep -n -iE 'erratum|non-breaking amendment|breaking amendment' paper-trader/docs/rfcs/0001-component-ir.md
```
Expected: `7` non-goals; all three change classes defined.

- [ ] **Step 5: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md
git commit -m "docs(rfc): §5 non-goals and §6 amendment procedure"
```

---

### Task 7: Appendices B and C

**Files:**
- Modify: `paper-trader/docs/rfcs/0001-component-ir.md` (Appendix B, Appendix C)

**Interfaces:**
- Consumes: every clause ID, F1–F14 and C1–C15.
- Produces: the traceability table that Task 8's review audits against.

- [ ] **Step 1: Write Appendix B — the traceability table**

One row per clause: `clause id | statement in ≤10 words | decision (D#) | pattern (P#) | source file`.
Source is `~/dev/multiverse-of-ideas/reviews/_FINDINGS-component-ir.md` or `_PATTERNS.md`.

**A clause with no traceable decision or pattern is a preference, not a finding. Cut it.** This is
the rule that keeps the constitution evidence-backed rather than tasteful.

- [ ] **Step 2: Write Appendix B's terminology mapping**

A short table reconciling this RFC's vocabulary with the findings', so a reader moving between
them is not misled:

| This RFC | The findings / patterns | Note |
|---|---|---|
| Resolution | "lowering" (P5, P7, D5, D6) | the whole stage |
| Lowering | part of "lowering" | one operation *within* resolution: deterministic structural expansion of nested references |
| Specification | "the recorded graph", "the authored graph" | |
| Resolved graph | "the executed graph", "the evaluation graph" | |

- [ ] **Step 3: Write Appendix C — the six open questions**

One subsection each, restating findings §6(a)–(f) with an explicit **revisit trigger**:

- (a) Fork semantics beyond a parent pointer — trigger: the first request for merge, rebase, or
  divergence display.
- (b) Field/structure inference rules in our domain — trigger: the first component that cannot
  declare its structure. The two-axis *shape* is frozen; the inference algorithm is not.
- (c) Migration machinery — trigger: the first breaking amendment.
- (d) Whether and when the live engine executes IR graphs — trigger: its own phase, with its own
  parity evidence, in the compile-first/adopt-second order. This is a migration question, not a
  language question.
- (e) Tick-level / intrabar strategies — trigger: any intrabar strategy.
  `reviews/nautilus-trader.md` §10 is the note to whoever revisits it.
- (f) Marketplace trust and sandboxing at scale — trigger: third-party component distribution.

State plainly that these are carried *inside* the constitution deliberately: a frozen architecture
that hides its own soft spots is how drift begins.

- [ ] **Step 4: Verify every clause is traceable**

Run:
The check MUST look inside Appendix B only — §3 and §4 have their own clause tables, so an
unscoped grep would pass on those and prove nothing:

```bash
sed -n '/^## Appendix B/,/^## Appendix C/p' paper-trader/docs/rfcs/0001-component-ir.md > /tmp/appendix-b.txt
for i in $(seq 1 14); do grep -q "^| F$i " /tmp/appendix-b.txt || echo "MISSING TRACE: F$i"; done
for i in $(seq 1 15); do grep -q "^| C$i " /tmp/appendix-b.txt || echo "MISSING TRACE: C$i"; done
```
Expected: no output. Any `MISSING TRACE` line names a clause with no evidence row — add the row or
cut the clause.

Prove the check can go red before trusting it — delete one row from Appendix B, re-run, confirm it
names that exact clause, then restore it. An empty result looks identical to a passing one.

- [ ] **Step 5: Verify Appendix C covers all six gaps**

Run:
```bash
sed -n '/^## Appendix C/,$p' paper-trader/docs/rfcs/0001-component-ir.md | grep -c '^### '
```
Expected: `6`.

- [ ] **Step 6: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md
git commit -m "docs(rfc): appendices B and C — traceability, and the gaps kept in view"
```

---

### Task 8: Gate 2 — adversarial review, fixes, and roadmap entry

**Files:**
- Modify: `paper-trader/docs/rfcs/0001-component-ir.md` (as review requires)
- Modify: `paper-trader/docs/ROADMAP.md`

**Interfaces:**
- Consumes: the complete document.
- Produces: a document ready for owner acceptance (Gate 3).

- [ ] **Step 1: Review for the six named defect classes**

Read the whole document once per lens, recording findings before fixing any:

1. **Underspecification** — a clause an implementer could satisfy while doing the wrong thing.
2. **Two readings** — a clause two careful implementers could read differently. Pick one reading
   and make it explicit.
3. **Wrong plane** — any normative clause naming UI, search, optimisation, or marketplace.
4. **Misfiled to §3** — any format clause whose guarantee survives if it moves to §4. Each one is
   a permanent migration liability; moving it is free.
5. **Untraceable** — any clause absent from Appendix B.
6. **Overclaimed enforcement** — any sentence implying validation the document does not have.
   The status block's admission MUST remain true of the whole document.

- [ ] **Step 2: Run the mechanical checks over the finished document**

```bash
grep -c 'TBD\|TODO\|FIXME\|XXX' paper-trader/docs/rfcs/0001-component-ir.md
sed -n '/^## 3\./,/^## 5\./p' paper-trader/docs/rfcs/0001-component-ir.md \
  | grep -n -iE 'marketplace|editor|user interface|search algorithm|optimis|optimiz'
grep -n 'lowering' paper-trader/docs/rfcs/0001-component-ir.md
```
Expected: `0` placeholders; no plane violations in normative text; every `lowering` occurrence
consistent with §2's narrow definition and never standing in for resolution.

- [ ] **Step 3: Fix every recorded finding**

Fix inline. For each fix that removes or moves a clause, update Appendix B in the same edit so
traceability never goes stale.

- [ ] **Step 4: Flip the status line to Accepted-pending-owner**

Change `**Status:** Draft` to `**Status:** Proposed — Gates 1 and 2 met; pending owner acceptance`.
Do **not** write `Accepted`. Gate 3 is the owner's, and a document that accepts itself is exactly
the overclaim §1's status block forbids.

- [ ] **Step 5: Record it in the roadmap**

Add to `paper-trader/docs/ROADMAP.md` a short entry: RFC 0001 written, Gates 1 and 2 met, pending
owner acceptance; and **name the conformance suite as the next item** — an executable schema and
validator for §3, plus tests for the mechanically checkable contract clauses (C7 reproducibility,
C13 provenance-blindness). Note explicitly that until it exists, §3/§4 conformance is a claim and
not a fact. Also record that the eight remaining roadmap subsystems each need their own
spec→plan→build cycle.

- [ ] **Step 6: Verify the roadmap entry does not overstate**

Run:
```bash
grep -n -A12 'RFC 0001' paper-trader/docs/ROADMAP.md
```
Expected: the entry says *pending owner acceptance*, and does not describe the RFC as enforced,
validated, or adopted by any running code. Nothing in the engine changed in this plan.

- [ ] **Step 7: Commit (owner approval required — do not run unprompted)**

```bash
git add paper-trader/docs/rfcs/0001-component-ir.md paper-trader/docs/ROADMAP.md
git commit -m "docs(rfc): adversarial review pass; RFC 0001 proposed, pending acceptance"
```

---

## Verification summary

| Gate | Check | Where |
|---|---|---|
| 1 — Expressiveness | Five named real artefacts express cleanly; a failure is a defect in the RFC | Tasks 3, 5 |
| 2 — Adversarial review | Six defect classes; mechanical placeholder, plane and terminology checks | Task 8 |
| 3 — Owner acceptance | Owner reads and accepts | after Task 8 |
| Traceability | Every F1–F14 and C1–C15 has an Appendix B row | Task 7 Step 4 |
| Honesty | The document never claims enforcement it lacks | Task 1 Step 2, Task 8 Steps 1.6 and 4 |
| No code touched | No file under `backend/app/` or `frontend/` modified | all tasks |
