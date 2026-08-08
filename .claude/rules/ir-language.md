---
description: The Component IR — schema, validator, resolver, hashing, editor persistence
paths:
  - "paper-trader/backend/app/ir/**"
  - "paper-trader/backend/app/editor/**"
  - "paper-trader/backend/app/api/ir_*.py"
---

# The Component IR

`docs/rfcs/0001-component-ir.md` is the constitution. Where any other document disagrees with it,
the RFC wins and the other document is the defect. All 29 normative clauses are enforced by tests,
each proven able to fail.

## One of anything

One IR · one validator · one `resolve()` · one hash · one component library
(`app/ir/library.py`) · one deployment authority · one research ledger. A second executable graph
schema, validator, resolver or statistical-gate pipeline is an architectural defect regardless of
which workstream adds it.

`app/ir/library.py` is **the platform component library**. A strategy is not a registry — six
production call sites used to take their vocabulary from one strategy's module and were corrected
(G-1, 2026-08-07). Do not reintroduce that coupling.

## Identity rules

- **Graph versions are immutable and content-addressed.** Append-only; CHECK constraints pin
  identifier and version to the stored bytes.
- **Presentation state lives beside the graph, never inside it** (F13). Dragging a node must not
  change its content address. Layouts and visual groups are separately revisioned.
- **Results bind to the versions that produced them** (F14) — graph version, every resolved
  component version, node identities and a data digest, all *derived from resolution*, never
  supplied by a caller.
- Every edit goes through `app/ir/edit.py::apply_batch`, never around it. An AST guard enforces it.
- `resolve()` is pure: no plane, no mode, no clock, no counter (C12, C7).

## Causality is measured, not assumed

C11: evaluate on the first *n* bars and on all of them; the first *n* results must agree at
**every node**, not just the outputs. A new kernel lands with this proof.

Do **not** reuse an `evaluate()` `Cache` across frames. `Cache` is keyed on `node.cache_id`, which
is fixed at resolution and carries nothing about the input data — reusing one returns the previous
frame's series with every node reporting a hit. A guard test pins this hazard.

## Cross-domain work

Instrument and timeframe identity participate in the type system (F7); an accidental cross-domain
edge **fails closed**. That is not the same as multi-instrument composition, which is not
implemented.

Intentional cross-domain behaviour arrives as **explicitly typed cross-domain operators** whose
declared interface may consume distinct domains while preserving their identities — ratio, spread,
normalised difference, comparison, correlation, beta-adjusted difference. **Never relax F7
globally** to make one strategy work. Do not design an operator family before a real strategy
needs one node.
