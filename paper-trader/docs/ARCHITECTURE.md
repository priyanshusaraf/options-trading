# ARCHITECTURE

**The architecture is singular. The implementation is distributed.**

This document is the shared frame every workstream works inside. It is deliberately short:
it states the invariants that hold across all of them and nothing else. Detail belongs in
the workstream documents.

- The constitution is [`rfcs/0001-component-ir.md`](rfcs/0001-component-ir.md). Where this
  document and the RFC disagree, the RFC wins and this document is the defect.
- Engine internals live in
  [`engineering/reference/engine-internals.md`](engineering/reference/engine-internals.md).
- Who builds what: [`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md).

---

## 1. What the system is

A single-user autonomous trading platform for Indian markets, being rebuilt as a **Strategy
Operating System**: strategies are composed, versioned, searched and executed as artefacts in
one language rather than as four kinds of hard-coded thing.

It trades real capital today. That fact constrains every decision below.

## 2. The five planes

RFC 0001 §1.2. Every subsystem is one of these, and a normative clause may not name a concern
from another.

| Plane | Concern | Relationship to the IR | Workstream |
|---|---|---|---|
| **Language** | the IR itself | *is* the IR | WS-01 |
| **Runtime** | how a resolved graph executes | consumes | WS-01 (evaluator), WS-02 (live) |
| **Research** | how graphs are generated and searched | produces and consumes | WS-03 |
| **Editor** | how humans author graphs | produces | WS-04 |
| **Marketplace** | how components are distributed | transports | WS-05 |

WS-06 (Deployment), WS-07 (Infrastructure) and WS-08 (Cockpit UI) are not planes. They are the
substrate the planes run on, and they carry no language concerns.

## 3. Invariants that cross every workstream

These are not style. Breaking one is an architectural defect regardless of which workstream
does it.

1. **The Component IR is the canonical representation of strategy intent.** Every other
   representation produces it, consumes it, or is deterministically derived from it.
2. **Deployment is the execution root.** Projects are editor-level organisational objects
   only. Packages distribute reproducible research environments, never live execution state.
3. **Strategies express intent; execution determines implementation.** Execution products,
   brokers and venues belong to the execution architecture and never to the strategy language.
4. **Execution is provenance-blind (C13).** No executor path may branch on where a component
   came from. Enforced subtractively — there is nothing to branch on — and by a test that
   greps for the concept.
5. **One resolution (C12).** Research and live share a single `resolve()`. There is exactly one
   construction of a resolved graph in the tree, and a test asserts it. Two hand-written
   implementations of one idea is the `candles.py` defect this rule exists because of.
6. **Presentation state lives beside the graph, never inside it (F13).** Dragging a node must
   not change its content address.
7. **Results bind to the versions that produced them (F14).** Every experiment and finding
   carries the graph version, every resolved component version, node identities and a data
   digest — derived from resolution, never supplied by a caller.
8. **Linear instruments are first priority.** Future derivative engines must extend this
   architecture rather than force a redesign.

## 4. The live-money rule

Any change affecting execution, order routing, sizing, exits or live trading behaviour **stops
for explicit owner acknowledgement before deployment**, even when every test passes.

Development, testing and commits continue normally. Deployment does not. This rule sits above
every workstream's own acceptance criteria and cannot be discharged by them.

## 5. Evidence

Assertions are not evidence. Evidence is a reproducible command and its output.

- Tick a checkbox only with verified evidence, in the same commit as the work.
- **A green test can be vacuous.** Prove a guard can go red by suppressing the thing it guards
  and checking that guard's *own* test fails. Counting green runs is not a substitute — five
  shapes of vacuous test have been caught here that way.
- **Never assert deployment state from prose.** `curl /api/health` and compare the commit.

## 6. How this document changes

Through RFC amendment (RFC 0001 §6), not through editing. A new capability either fits inside
the existing architecture or arrives with an RFC that amends it. There is no third path, and
the executive layer's job is to make a capability that quietly extends the architecture
distinguishable from ordinary work.
