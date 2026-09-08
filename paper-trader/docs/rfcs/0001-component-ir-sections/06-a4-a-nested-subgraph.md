Reference: [section index](../0001-component-ir.md). Read with its scope; this is not a new assignment.

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
