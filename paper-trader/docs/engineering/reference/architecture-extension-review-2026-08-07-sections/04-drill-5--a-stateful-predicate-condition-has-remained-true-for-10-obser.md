Reference: [section index](../architecture-extension-review-2026-08-07.md). Read with its scope; this is not a new assignment.

What would be required to turn a three-node fragment into a marketplace component is therefore
almost entirely *outside* the language: a package format, signing, a trust model and an external-code
policy. The RFC's own Appendix C(f) and the execution plan's L4 both already own that. **No
architectural change is needed now.**

The one honest caveat, already recorded as WS-01 §5 technical debt: C15 is otherwise tested only
against synthetic graphs. This drill is the first time it has been exercised on the real reference
artefact, and it passed.

### Drill 5 — a stateful predicate ("condition has remained true for 10 observations")

**Result: this class of state — data-derived state — is ALREADY SUPPORTED.** Amendment A-2: that
is a narrower claim than "stateful nodes are supported", and the distinction is drawn in full at
gap **G-8**. What the drill proves is that state which is a deterministic function of the input
series needs no new contract. It proves nothing about state that is not.

```
DRILL1/5 unchecked clauses: () ()
DRILL5 causality (C11) over the stateful predicate: PASS
```

The runtime is whole-series: every scan re-derives the frame and re-evaluates the whole graph. So
"state" of this kind is not process state at all — it is a **function of the data**, expressed with
causal primitives (`rolling`, `shift`, `expanding`). `check_causality` proves it: evaluating on the
first *n* bars must give byte-identical results to the first *n* bars of the full run, checked at
every node, not just the outputs.

That answers the restart and replay questions directly:

| Question | Answer |
|---|---|
| Explicit lifecycle? | Not needed for data-derived state; it is recomputed every scan |
| Checkpointable? | Yes trivially — there is nothing to checkpoint |
| Survives restart? | Yes, provided history ≥ warmup. `ir_shadow.admit()` already checks that **before activation** rather than discovering it from a refusal mid-session |
| Deterministic replay? | Yes, and enforced (C11) |
| Hidden in Python process state? | **No, and structurally so.** A kernel takes exactly `(params, inputs)` — `authoring.py:_check_signature` refuses any other signature, "nothing that would let it behave differently depending on where it was used" |
| Clean future home? | Yes for the exception case — see below |

The exception is state that genuinely *cannot* be recomputed from the window: something that must
remember an event older than `history_days`. Two things already cover this:

- **Position-scoped state has a durable home.** The live ATR ratchet persists `entry_atr`,
  `ratchet_hw`, `spot_stop` and `ratchet_last_bar_ts` on the `positions` row.
- **Impure state is declarable.** `KernelSpec.purity` accepts `('account_state', 'broker_state',
  'wall_clock')` [measured], and an impure node is excluded from the cache (`runtime.py:_compute`).

What does *not* exist is node-scoped durable state. The Nautilus review (`reviews/nautilus-trader.md`
§9B) already recommends adopting mandatory reset semantics "as an IR-level requirement, even though
nothing needs it yet", and that recommendation has not been taken up: `KernelSpec` fields are
`['warmup', 'purity', 'cache_identity', 'cache_key']` [measured]. Adding one is cheap and local —
the field set is closed and `kernel_spec()` raises `KernelDeclarationError` on anything outside it,
so the extension point is already guarded. **SPECULATIVE** until a component needs it.

---

## D. Architecture gap register

### G-1 — There is no platform component library. One strategy's library is standing in for one.

**Urgency: CREATE SEAM NOW.**

- **Evidence.** Five production call sites import `app.ir.strategies.expanding_z`'s `LIBRARY` /
  `IMPLEMENTATIONS` / `GRAPH` as though it were the platform's: `api/ir_edit_routes.py:20`,
  `editor/graph_artifacts.py:19`, `engine/ir_shadow.py:238,271`, `core/paper_authority.py:311`,
  `ir/catalogue.py:12`. `catalogue()` returns a table with exactly one entry.
- **Affected code.** The editor's entire component palette (`descriptors.component_catalogue(
  LIBRARY)` at `ir_edit_routes.py:655`), and — more seriously — `paper_authority.adapter_for`, which
  is on the paper-**authoritative** path.
- **Consequence.** Adding any platform-level node means editing one strategy's file. When a second
  strategy artefact arrives (already queued as WS-01 §5), either the library forks — two component
  libraries, which the "one of anything" rule forbids — or `expanding_z.py` silently becomes the
  platform library while still being named a strategy. The second outcome is more likely and worse,
  because nothing would report it.
- **Answers to the six questions.**
  1. *What is blocked?* Routine node/indicator addition — direction B, the stated major product
     requirement — and the second reference artefact.
  2. *Which code creates the block?* The five imports above.
  3. *Why can this not wait?* Because it gets more expensive per call site, and the next queued
     WS-01 slice adds call sites. It is five imports today.
  4. *Smallest correction?* A module that owns the platform `(Library, implementations)` pair and
     composes the strategy's components into it. **Move nothing**; change the five imports to point
     at the new module, which initially re-exports exactly what they import today. Byte-identical
     behaviour.
  5. *What must not change?* The reference artefact's content address (`sha256:d78b424e8247…`), every
     node cache id, `paper_authority.adapter_for`'s three-way address verification, and C13 — the
     runtime must still know a kernel by its address and nothing else.
  6. *What tests prove it?* `test_ir_strategy_parity.py` (bar-for-bar output unchanged); a new
     assertion that the graph's content address and all 18 node cache ids are identical before and
     after; a guard that `app/api/`, `app/editor/`, `app/engine/` and `app/core/` import the platform
     library rather than `app.ir.strategies.*` directly — proven able to go red by restoring one old
     import.
- **Blast radius.** Five import lines plus one new module. No schema, no migration, no execution
  behaviour, no money path.

### G-2 — The signal → intent → order boundary is real but unnamed.

**Urgency: CREATE SEAM NOW (as documentation, not code).**

- **Evidence.** Drill 3. There is no object between a `self.state` entry and `broker.open_position`.
  `Candidate` carries `(instrument_key, direction, cost)`; `Position` is single-leg.
- **Affected code.** `runner.process_entries`, `allocator.allocate`, `execution_policy.plan_order`,
  `broker.open_*_position`, the `positions` schema.
- **Consequence.** L1.4 is scheduled to add "futures accounting, venue support, protective-band
  parity, multi-timeframe lifecycle, reconciliation, broker errors and deterministic order state"
  (EXECUTION_PLAN §5 L1). All of that is written across this boundary. Written without the boundary
  named, order-lifecycle state will attach to single-leg `Position` rows, and a later multi-leg
  intent has to unpick it.
- **Answers to the six questions.**
  1. *What is blocked?* Direction H — spreads, hedges, baskets, roll and close intents.
  2. *Which code creates the block?* The absence of an intent object, plus `positions` having no
     group concept.
  3. *Why can this not wait?* The *feature* can and should wait. The *boundary* cannot, because
     L1.4 writes across it. This is why the recommendation is a document, not an object.
  4. *Smallest correction?* One section in `docs/engineering/workstreams/WS-02-execution.md` naming
     the four stages, stating that order-lifecycle state belongs to the order/fill stage rather than
     to `Position`, and recording that a leg-group id is the anticipated extension point. **No
     code.**
  5. *What must not change?* Nothing — this is documentation.
  6. *What tests prove it?* None; it is a design constraint on the next slice, checked at review.
- **Blast radius.** One document section. Zero code.

### G-3 — Backtests are a process-global singleton.

**Urgency: recorded now, built later. Explicitly NOT part of any current slice.**

- **Evidence.** `app/backtest/sweep.py:103-137` — module-level `_running`, `_worker`, `_state_lock`,
  and `raise RuntimeError("a sweep is already running")`. One sweep per **process**, not per user.
- **Consequence.** The second concurrent user's backtest fails outright. Correct and harmless for a
  single-user system; wrong for a multi-user hosted one.
- **Where it belongs.** The future **job/worker boundary**, alongside any other long-running work
  that outlives a request. Not a slice of its own yet.
- **What must NOT be introduced while it waits** — worker infrastructure, queues, microservices,
  Postgres, distributed execution. None of them has a demonstrated need at one user, and this
  finding is not a licence to build any of them early.
- **The only thing that matters today.** New long-running work should be written so it *could*
  become a claimed job — i.e. not as a second module-global singleton.
- **Blast radius when eventually done.** One table, one loop, one API shape. No execution path.

### G-8 — "Stateful nodes are supported" is true only of data-derived state.

**Urgency: SAFE TO DEFER. Do not build a state contract now.**

Amendment A-2. Drill 5 succeeded, and the success generalises less far than it first appears. Two
kinds of state must be kept apart:

**Data-derived state — already supported, and the preferred form.** State that is a deterministic
function of the input series: true for N bars, rolling maximum, previously crossed, persistence over
a bounded window. It needs no contract because it is not state — it is a computation. It replays
deterministically (C11 enforces it), survives restart provided history ≥ warmup (`ir_shadow.admit`
checks that before activation), and cannot hide in the process because a kernel takes exactly
`(params, inputs)` and `authoring.py:_check_signature` refuses any other signature. **Prefer this
form wherever the behaviour can be expressed in it.**

**Runtime / event / execution state — not supported, and not needed yet.** State not reconstructible
from the current data window: an armed/disarmed strategy state, a lifecycle that depends on fills or
order events, a persistent event automaton, anything that must survive restart independently of
market history. The pure kernel model does not express this and should not be stretched to.
