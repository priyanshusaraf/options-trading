---
name: implementation-slice
description: The default workflow for substantial engineering work in Strategy OS — any change beyond a typo or a one-line fix. Enforces understand-contract → smallest coherent slice → real behavioral evidence → independent review → exact-head closure. Tests alone never equal completion.
---

# Implementation slice

Use for substantial work. **Do not use for trivial edits** — a typo fix does not need an
architecture pass, and running the whole suite for one is waste, not rigour.

## 1. Understand the contract

What is the observable behaviour being changed, and who depends on it? Read the workstream
document and whatever it declares under *Depends on*. If the document is missing something you
need, that is a defect in the document — fix it there.

## 2. Inspect the affected architecture

Which invariants are in the blast radius (`CLAUDE.md`, the relevant `.claude/rules/` file)? For a
major decision, invoke `strategy-os-architecture-review` first.

## 3. Define observable success BEFORE writing code

> **What observable evidence would be different if this change actually works?**

Write it down. "The tests pass" is not an answer — the tests passing is how you check, not what
changed. Good answers name a number, a row, a rendered state, a refusal, a log line, a latency.

## 4. Implement the smallest coherent slice

One reviewable change. Do not bundle unrelated refactors. If you discover a second problem,
record it and finish the first.

## 5. Targeted automated evidence

TDD where it fits: watch the test fail for the intended reason first. Then:

- **Prove the guard can go red.** Suppress what it guards; the guard's *own* test must fail. A
  test that passes before and after your change proves nothing until a wrong change reddens it.
- Beware vacuous shapes: right-clause-wrong-cause · a fixture already corrupted by an earlier
  test · checking only the endpoints · a presence check masking a comparison · a case refused for
  the wrong reason · **a seed the ORM silently normalised** (`Model(col=None)` applies the column
  default, not NULL).
- Verification proportional to the contract. Focused tests plus the affected workstream's
  regression; the full suite only when a shared schema, runtime or safety boundary moved.

## 6. Real behavioral verification

Automated tests are one kind of evidence, not the only kind. Depending on what you touched:
run the app and drive the flow (`run-strategy-os`, `ui-acceptance`) · exercise the adapter against
a real response shape (`provider-adapter`) · produce before/after numbers on the same workload
(`performance-benchmark`) · reproduce the wrong number and show it become right
(`research-integrity`).

## 7. Independent review

Dispatch the agent whose domain you touched — `execution-safety-reviewer`,
`security-tenancy-reviewer`, `research-leakage-reviewer`, `ui-verifier`, `architecture-critic`.
**You are not an independent reviewer of your own diff.**

## 8. Fix findings, then close

Fix what the reviewer found. Then `ship-gate`. Do not declare done before it.
