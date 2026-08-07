# Architecture extension review — 2026-08-07

**Scope.** A bounded architecture and reuse audit taken at `75809a3` (L1.3C, migration head `0013`),
before L1.4 begins. It stress-tests the built architecture against twelve candidate product
directions (A–L) that the owner is exploring, and asks one question of each: *does today's code
provide a clean extension point, or would it create expensive coupling later?*

**Status.** Inspection and documentation only. **Zero production files changed.** Every claim below
is followed by the command that produced it or the file and line that shows it. Where a probe was
needed, it was run from a scratchpad, never added to the tree.

**What this review is not.** It is not a proposal to redesign anything. The candidate directions are
hypotheses, not requirements. The default answer here is *defer*, and it is the answer for most of
them.

**Headline.** The architecture is healthy for the expanded direction. The language (RFC 0001)
already carries the vocabulary for the two capabilities that looked most threatening —
cross-domain *typing* and subgraph packaging — and both were verified by execution, not by reading.
There are **no** CHANGE NOW findings and **three** at CREATE SEAM NOW (G-1, G-2, G-3). Everything
else defers.

---

## Amendments — 2026-08-07, after owner review

This review was accepted, with its central conclusion intact: **no foundational contradiction
exists, and the current IR/research/execution spine should be preserved.** Four readings were
tightened because they were carrying more weight than the evidence supports. The findings and their
urgency classifications are unchanged.

| # | What was too strong | The precise claim |
|---|---|---|
| **A-1** | That F7 makes cross-instrument work "already supported" | Instrument/domain identity **participates in the type system**, and *accidental* cross-domain wiring **fails closed**. Multi-instrument strategy *composition* is not implemented. See §C Drill 2 and the principle below |
| **A-2** | That the ten-bar drill shows "stateful nodes are supported" | **Data-derived** state is expressible in the pure kernel model. It does not follow that all stateful strategy behaviour is. See §D G-8 |
| **A-3** | That the headline's finding counts were right | Corrected above: zero CHANGE NOW, three CREATE SEAM NOW |
| **A-4** | That "no external code should be adopted" is a rule | It is a conclusion **about G-1 and G-2 only**. Project reuse policy is unchanged. See §E |

**A-1 — the cross-domain principle, recorded (no runtime change, no design).**

> Arbitrary domain mismatch remains illegal. Future cross-instrument behaviour is to be introduced
> through **explicitly typed cross-domain operations** — nodes whose declared interface is permitted
> to consume distinct domains while preserving their identities — rather than by weakening F7
> globally.

RFC 0001 A.5 already states the mechanism for the timeframe axis ("an explicit resampling component
whose declared interface changes the timeframe domain"); this generalises the same shape to the
instrument axis. Conceptually such nodes might one day cover comparison, synchronisation,
normalisation or cross-domain predicates. **None of them is designed here, and none should be
designed until a real strategy needs one.** The principle exists so the first person who needs one
does not reach for the shortcut of relaxing F7, which would silently re-admit the accidental
mismatches the axis exists to catch.

---

## A. Current architecture map

The full path, from what a user draws to what a money record says. Each arrow is a real call, with
the file that makes it.

```
   authored graph (React canvas)
        │   frontend/src/views/GraphView.tsx — server-driven; no node vocabulary in the client
        ▼
   persisted draft                       graph_artifacts.draft_json      (optimistic revision)
        │   app/editor/graph_artifacts.py · app/api/ir_edit_routes.py
        │   every edit goes through app/ir/edit.py:apply_batch, never around it
        ▼
   immutable graph version               graph_versions.artifact_json    (append-only)
        │   canonical JSON + content address; CHECK constraints pin identifier/version to the bytes
        │   presentation state lives apart: ir_graph_layouts / _positions / _groups  (F13)
        ▼
   IR resolution                         app/ir/resolve.py:resolve(spec, library)
        │   pure: no plane, no mode, no clock, no counter (C12, C7)
        │   → 18 nodes, 35 edges, warmup 302 for the reference artefact  [measured]
        ▼
   runtime strategy                      app/strategy/ir_adapter.py:IRGraphStrategy
        │   presents a ResolvedGraph behind the Strategy contract
        │   key   = ir.<identifier>          — stable across edits, so persisted rows keep resolving
        │   version = graph content address  — so an edit still changes (key, version)
        ▼
   deployment                            ir_paper_deployments            (migration 0013)
        │   app/core/paper_authority.py — staged / paper_active / paused / retired
        │   verified: content address re-derived from bytes at activation AND at every reload
        │   verified: research lineage approves this exact artefact (core/research_read.py)
        │   verified: warmup admission against instrument+interval (engine/ir_shadow.py:admit)
        ▼
   canonical execution binding           app/core/execution_binding.py
        │   ONE decision: bind(deployment_pin, assigned_key, paper_authority)
        │   precedence: paper-authority record > deployment pin > instrument row > platform default
        │   gate: strategy_for_execution() recomputes source AND mode, then checks GRANTS
        │   GRANTS (measured) = {handwritten,generated}×{paper,live} + (ir_graph, paper)
        │                       (ir_graph, live) is ABSENT — the standing owner gate
        ▼
   signal publication                    app/engine/runner.py:scan_signals → publish_signal
        │   signal and its binding written through one door; a signal with no binding cannot open
        ▼
   execution                             process_entries → execution_policy.plan_order
        │                                → broker (PaperBroker | LiveBroker)
        │                                → ExecutionVenue → KiteVenue     (broker_protocol.py)
        ▼
   fill                                  positions row: strategy_key + strategy_version + mode
        ▼
   position / trade / accounting         app/core/execution_book.py decides whose money it is
                                         book = execution mode; fails closed to `live`
                                         capital_state and equity_snapshots are book-scoped (0012)
```

Three properties of this map are worth stating because they are what make the rest of this review
short:

1. **There is one resolver, one validator, one hash, one registry, one deployment authority and one
   research ledger.** The project's standing "one of anything" rule holds today. `execution_binding.
   BINDING_MECHANISMS` even enumerates the six legacy things that claim to answer "what runs here",
   so adding a seventh is a visible edit rather than a new table appearing.
2. **Authority is checked where it is used, not where it is produced.** `strategy_for_execution`
   recomputes the source from the key and the mode from settings, and refuses anything outside
   `GRANTS`. A binding is a plain dataclass, so a field is treated as a claim. This is why granting
   a new capability execution rights is a reviewed code edit and cannot become a config row.
3. **Execution is provenance-blind (C13).** No path under `app/engine/` branches on where a
   component came from. The one place that inspects a source lives in `app/core/`, outside the
   executor perimeter.

---

## B. Capability compatibility matrix

| # | Capability | Current support | Likely extension | Blocker | Urgency | Recommended action |
|---|---|---|---|---|---|---|
| 1 | New indicator node | **Yes at the language level** — authored, validated, resolved and evaluated in a probe with zero production edits | `@component` + kernel + one library entry | The library the *platform* offers is `expanding_z`'s, hardcoded at 5 call sites | **CREATE SEAM NOW** | Introduce a platform component library module; leave the components where they are |
| 2 | New logic node (AND/OR/NOT/XOR/IF/ELSE) | **Yes** — `bool` is a closed value type; `predicate.*` components already exist | New components only. IF/ELSE over boolean series is `where(cond,a,b)`, a kernel | None | SAFE TO DEFER | Add when a strategy needs one |
| 3 | Nested / sustained / stateful conditions | **Yes** — verified: a "true for 10 consecutive bars" predicate resolves, evaluates and passes the C11 causality check | New components only | None | SAFE TO DEFER | Add when needed |
| 4 | Multi-instrument observation | **Language yes, runtime no.** F7's `domain` axis is enforced; `runtime.py` never mentions `domain` or `instrument` | Key runtime inputs by `(domain, socket)`; acquire a frame per domain | Runtime input keying; `scan_signals` fetches one instrument's candles | SAFE TO DEFER | Already on WS-01 §5 as "Multi-timeframe resolution". Do it there, not now |
| 5 | Cross-instrument execution (observe NIFTY, trade SENSEX) | **No** — `Position.instrument_key` is the observed *and* traded instrument | An explicit execution-target declaration on the graph or the deployment | #4, plus the binding is keyed on one `instrument_key` | SAFE TO DEFER | Depends on #4; do not pre-build |
| 6 | Multiple timeframes | **Language yes** — RFC A.5 is exactly this case and the ill-typed edge is rejected | An explicit resampling component whose interface changes the timeframe domain | No resampling component; no rule for what a legal cross-timeframe edge means | SAFE TO DEFER | Already WS-01 §5 |
| 7 | Order-flow source (depth, OFI, volume delta) | **Partial.** The platform already reads bid/ask/depth/OI (`OptionQuote`, `execution_policy.plan_order`) but the strategy language cannot see it | A typed data-source contract; the frame contract widens | `FRAME_COLUMNS` is `date,OHLCV`; the adapter reads `df[field]` | SAFE TO DEFER | L3 owns this ("first-class data layer") |
| 8 | Typed non-OHLCV inputs | **Yes, structurally** — the adapter uses `self.required_inputs` from the *graph*, not a fixed OHLCV tuple | Add the column to `FRAME_COLUMNS`; precedent exists (`volume`, 2026-08-02) | None | SAFE TO DEFER | Follow the `volume` precedent when a source arrives |
| 9 | Multi-leg intent (spreads, hedges, baskets) | **No.** `Position` is single-leg; `Candidate(instrument_key, direction, cost)`; strategy output is 4 booleans | A structured `ExecutionIntent` between signal and order, and a position group | Both the strategy output contract and the money schema | **CREATE SEAM NOW** (name the boundary) / defer the feature | Document signal→intent→order as a named boundary before L1.4 adds order-lifecycle code across it |
| 10 | Reusable component / subgraph | **Already supported.** `publish()` + `body_for()` reproduce the shipped ATR body address exactly; re-resolution yields identical node and cache ids | Nothing at the language level | Packaging, signing, permissions, hiding internals — all L4 | SAFE TO DEFER | Close WS-01 §5's "worked `publish()` round trip" when convenient |
| 11 | Layered risk / constraint policies | **Partial.** `app/core/scoped_config.py` already resolves Platform → Deployment → Instrument, narrowest wins, validated through one gate | Add scopes to `SCOPES`; a narrowing rule for safety keys | Narrower scopes may currently *widen* a safety limit | SAFE TO DEFER | Add a monotonic-narrowing rule when the second scope is populated |
| 12 | Back-adjusted / continuous futures | **No** — no dataset identity; `Instrument` is a contract-ish key | Separate raw / executable / analytical series identities | Nothing forces a wrong answer today | SAFE TO DEFER | L3 owns this explicitly |
| 13 | Auth / multi-tenancy | **Seam exists, unpopulated.** `Principal` is on every request (`api/principal.py`); `deployments.account_id` exists | Add an owner scope; namespace identifiers | `graph_artifacts.identifier` is a **global** PK | SAFE TO DEFER | Namespace identifiers by convention now (free); schema later |
| 14 | Increased backtest history | Works; per-`(instrument, interval)` cache | More history / more cells | Single-process, one sweep at a time | SAFE TO DEFER | See §F |
| 15 | ~100-user concurrency | **No** — one SQLite file, one process, one Kite token, one global sweep worker | A job queue and a per-tenant data boundary | `sweep.py` raises `"a sweep is already running"` process-wide | **CREATE SEAM NOW** (job boundary only) | See §F |

---

## C. Extension-drill results

All five drills were executed against the real language where execution was possible. The scripts
lived in the session scratchpad and are not in the repository.

### Drill 1 — add one ordinary new indicator (`DepthWeightedMidPrice`)

**Result: EXTENSION-FRIENDLY at the language level; one unnecessary coupling at the platform level.**

The node was authored, validated, resolved and evaluated **without touching a single file in the
repository**:

```
$ PYTHONPATH=. .venv/bin/python <scratchpad>/drill.py
DRILL1/5 authored components: ['indicator.depth_weighted_mid', 'predicate.gt', 'predicate.sustained']
DRILL1/5 unchecked clauses: () ()
DRILL1 validate violations: NONE
DRILL1 resolved: 3 nodes, warmup 13
DRILL1 evaluated, true bars: 49
```

Note what that proves beyond "it works". The component takes `bid`, `ask`, `bid_qty`, `ask_qty` —
**not OHLCV** — and nothing objected. `app/ir/authoring.py:component()` checked the kernel's
signature, content-addressed its source, validated the definition against §3, and statically
verified that the kernel reads every input it declared and nothing it did not (F4). Warmup composed
through the graph automatically (3 + 10 = 13). This is very close to the "implement contract →
register → available" ergonomics the requirement asks for.

**What would actually need editing to make it available *through the system*.** This is the finding:

| Layer | Needs an edit? | Why |
|---|---|---|
| `app/ir/schema.py` | **No** | No new key; wire types and kinds already cover it |
| `app/ir/validate.py` | **No** | Reads the schema tables; does not hard-code a vocabulary |
| `app/ir/resolve.py` | **No** | Generic over the library |
| `app/ir/runtime.py` | **No** | Keyed by content address only (C13) |
| `app/ir/kernels.py` | **No** | `warmup=lambda p: ...` already supported |
| Persistence | **No** | `graph_versions` stores bytes; no per-node schema |
| Backtest | **No** | Runs whatever `Strategy` it is handed |
| API | **No** | `component_catalogue` is derived from the library (`app/editor/descriptors.py`) |
| Frontend | **No** | Server-driven; `GraphView.tsx` has no node vocabulary |
| **The component library** | **Yes — and this is the problem** | There is no platform library. There is one *strategy's* library standing in for one |

`app/ir/strategies/expanding_z.py` is imported as the platform's component library at five
production call sites:

- `app/api/ir_edit_routes.py:20` — `from app.ir.strategies.expanding_z import LIBRARY`; used at
  `:486`, `:491`, `:538`, `:637`, `:655` — this is what the editor's whole component palette comes
  from
- `app/editor/graph_artifacts.py:19` — `GRAPH, LIBRARY`
- `app/engine/ir_shadow.py:238`, `:271` — `GRAPH, IMPLEMENTATIONS, LIBRARY`
- `app/core/paper_authority.py:311` — `IMPLEMENTATIONS, LIBRARY`, inside `adapter_for`, which is on
  the **paper-authoritative** path
- `app/ir/catalogue.py:12` — returns a one-entry table keyed on `expanding_z.GRAPH["identifier"]`

So adding a platform-wide indicator today means adding it to one strategy's `COMPONENTS` list, which
is the wrong home and will be visibly the wrong home the moment a second strategy exists. WS-01 §5
already queues "a second reference artefact from a different strategy family" — that slice will hit
this. See gap **G-1**.

### Drill 2 — observe NIFTY, execute SENSEX

**Result: BOUNDED EXTENSION at the language level; the runtime and acquisition are the real work.
Not a foundational blocker.**

The language already refuses the dangerous version of this:

```
DRILL2 cross-instrument edge violations:
  ["F7 at $.edges[4].domain.instrument: 'NIFTY' does not match 'SENSEX';
    the domain is part of the type"]
```

**Read this claim precisely (amendment A-1).** What is demonstrated is that instrument identity
participates in the type system and that *accidental* cross-instrument wiring **fails closed**.
That is a genuinely strong foundation, and it is all it is. It is **not** a demonstration that
multi-instrument strategy composition works — there is no component that may legally consume two
domains, no runtime that can hold two domains' series, and no acquisition path that fetches them.

RFC 0001 A.5 states the mechanism for the timeframe axis: a legal crossing requires an explicit
component whose declared interface changes the domain. Intentional cross-instrument composition will
require the same shape on the instrument axis — explicitly typed cross-domain operations, not a
global relaxation of F7. That principle is recorded in the Amendments section. **It is not designed
here and must not be designed until a strategy needs it.**

What breaks, traced:

| Layer | Status |
|---|---|
| Graph representation | **Compatible.** `NODE_KEYS` includes `domain`; `resolve.py:229` merges inherited and pinned domains; `resolve.py:487` puts the domain into the node's cache identity |
| Validator | **Compatible and actively protective** (above) |
| Resolver | **Compatible.** Domain is propagated and hashed |
| Runtime | **Blocked, cheaply.** Measured: `runtime.py` contains neither the string `domain` nor `instrument`. `evaluate(graph, inputs: Mapping[str, pd.Series], ...)` takes one flat mapping of graph-input names. Multi-domain evaluation means keying inputs by `(domain, name)` — a change confined to one file |
| Execution binding | **Blocked.** `ExecutionBinding` and `PaperBinding` both carry a single `instrument_key`. The observed set and the execution target are the same field |
| `EngineRunner` | **Blocked.** `scan_signals` is `for key in self.enabled:` → `prov.get_candles(inst, interval, days)` → one frame → `strat.signals(frame)` |
| History / warmup acquisition | **Blocked.** One instrument, one interval, one `history_days`. `ir_shadow.admit()` decides admission for one `(instrument, interval)` pair |
| Persistence | **Compatible.** No schema change needed to *observe* several instruments |
| Research binding | **Compatible.** Experiment binding is to the graph version, not to an instrument |
| Backtest | **Blocked.** `app/backtest/engine.py:2` — "Single-instrument backtest" |
| Replay / deployment | **Blocked** via the same single-instrument binding |
| Money attribution | **Compatible, and this is the important one.** `positions.instrument_key` is the *traded* instrument and always was. Observing more instruments does not disturb attribution, because attribution never claimed to describe the inputs |

Classification: **requires a bounded extension**, spread over runtime keying, frame acquisition and
the binding's instrument field. None of it is a foundational contradiction, because the type system
already prevents the incorrect version and money attribution is already keyed on the traded
instrument rather than the observed one. **Do not start it now.** It is WS-01 §5 work and should
follow the multi-timeframe resolution slice already queued there.

### Drill 3 — produce a two-leg option spread

**Result: REQUIRES A BOUNDED EXTENSION. The largest genuine gap in this review, and the one worth
naming before L1.4.**

Traced end to end:

| Stage | Today | Two-leg needs |
|---|---|---|
| Signal | 4 booleans — `CANONICAL_COLUMNS = ('longEntry','shortEntry','longExit','shortExit')` | Something that can name legs |
| Intent | **Does not exist as an object.** `process_entries` goes from a `self.state` entry straight to picking a contract and sizing it | A structured intent: N legs, ratios, atomicity |
| Allocation | `Candidate(instrument_key, direction, cost)` — one cost, funded greedily and independently (`allocator.py:31`) | All-or-nothing funding of a leg set |
| Order | `plan_order` decides MARKET / LIMIT / SKIP per order | Per-leg routing plus a group outcome |
| Fill | `broker.open_position(...)` writes one `positions` row | N rows plus a group id |
| Position | Single-leg by construction: `option_type`, `tradingsymbol`, `strike`, `expiry`, one `direction`, one `qty`, one `entry_premium` | A position group with net P&L |
| Accounting | `unrealized_pnl()` is per-row and segment-aware | Net across the group; margin benefit is a group property |

Two things make this **not** a foundational blocker:

- The **venue layer already exists and is correctly shaped.** `app/engine/broker_protocol.py`
  separates domain verbs (`Broker`) from wire verbs (`ExecutionVenue`), and explicitly reasons about
  branching on the *kind* of protective order rather than on "is this equity_intraday". Multi-leg is
  the same kind of extension that layering anticipated.
- `StrategySpec` (`app/strategy/spec.py`) already separates *declared* entry / exit / sizing policy
  from execution arithmetic, and its docstring already states the principle: the strategy declares,
  the engine owns the arithmetic, "because that is broker and account knowledge a strategy has no
  business holding."

What is missing is not a design — it is a **name**. There is no object between "signal" and "order",
so L1.4's order-lifecycle work will be written directly against the four-boolean contract on one
side and single-leg `Position` rows on the other. Every line written across that undeclared boundary
is a line that a later intent object has to unpick. See gap **G-2**. The recommendation is to
document the boundary, not to build the object.

### Drill 4 — package a subgraph as a reusable component

**Result: ALREADY SUPPORTED at the language level.** This was the pleasant surprise.

```
$ PYTHONPATH=. .venv/bin/python <scratchpad>/drill4.py
published component identifier: indicator.atr.wilder.body v 1
body is content-addressed     : sha256:3c8c4bb76f862ecd347 ...
matches the shipped ATR ref   : True
interface carried forward     : 5 items
body kind                     : graph
re-resolve identical node ids : True
re-resolve identical cache ids: True
```

`resolve.py:publish()` derives a component-def from a graph-def mechanically, with no options (C15),
and `body_for()` gives the content-addressed body. Run against the reference artefact's ATR body,
`publish()` reproduces the **exact body address the shipped `ATR` component already carries**, and
re-resolving the whole strategy through the published component yields byte-identical instance ids
and cache ids.

So the requested properties map onto things that already exist:

| Component property wanted | Where it already lives |
|---|---|
| Typed inputs / outputs | The interface's `wire_type` — value × structure × domain, closed and exact-matched (F7) |
| Parameters | Interface `parameter` items with `kind` and `bounds` (F5) |
| Version | `(identifier, version)` plus `parent_version` (F3) |
| Content identity | The body's content address (F2) |
| Internal state | Nothing needed today — see Drill 5 |
| Hidden internals | A body ref is an address; a consumer resolves it only if the library holds it |
| Permissions / distribution | **Not present.** This is L4 (packaging, signing, sandboxing) and is correctly deferred there |

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

What already exists, and is worth knowing before anyone builds anything:

- **Position-scoped runtime state already has a durable home** — the live ATR ratchet persists
  `entry_atr`, `ratchet_hw`, `spot_stop`, `ratchet_last_bar_ts` on the `positions` row. This is an
  existing execution-state contract that merely needs documenting, not a new one.
- **Deployment-scoped lifecycle state already has one too** — `ir_paper_deployments` carries
  `state`, `revision`, verified addresses and evidence, and reloads deterministically after restart.
- **Impurity is already declarable at the node level** — `KernelSpec.purity` accepts
  `('account_state', 'broker_state', 'wall_clock')` [measured], and an impure node is excluded from
  the cache.

What does **not** exist is *node-scoped durable* state, and nothing needs it. The Nautilus review
(`reviews/nautilus-trader.md` §9B) recommends adopting reset semantics "even though nothing needs it
yet"; `KernelSpec`'s field set is closed and refuses unknown fields, so adding one later is local and
guarded. **Recommendation: do not add it until a component requires it.** Prefer the pure model;
when something genuinely cannot be expressed in it, that is the evidence that justifies the
contract, and not before.

### G-4 — `runtime.evaluate` is domain-blind.

**Urgency: SAFE TO DEFER.** Measured: `runtime.py` contains neither `domain` nor `instrument`, while
resolution propagates domains and hashes them into cache identity. This is not a defect — it is the
correct staging (the type system leads, the runtime follows) — but it should be recorded so nobody
reads "domains are enforced" as "multi-domain evaluation works". Already covered by WS-01 §5's
multi-timeframe item; this review adds the measurement.

### G-5 — `graph_artifacts.identifier` is a global primary key.

**Urgency: SAFE TO DEFER, with a free hedge.** Two tenants could not both own
`strategy.expanding_z_impulse`. Retrofitting a tenant scope would touch `graph_versions`'s composite
PK and `ir_paper_deployments.graph_identifier`. **The free hedge is a convention, not a schema
change:** identifiers are already dotted namespaces, so prefixing them per owner costs nothing now
and removes the collision entirely. Everything else needed for tenancy already has a seam —
`Principal` on every request (`api/principal.py`), `deployments.account_id`, and `scoped_config`'s
scope chain.

### G-6 — Narrower config scopes can widen a safety limit.

**Urgency: SAFE TO DEFER.** `scoped_config.SCOPES` is `(platform, deployment, instrument)`, narrowest
wins, and every scope validates through the same `OVERRIDABLE`/`BOUNDS` gate — which is the right
design and explicitly reuses rather than reinvents. But "narrowest wins" means a deployment could set
a *looser* `max_daily_loss` than the platform. Today this is unreachable: narrower scopes are empty
everywhere (`params_json` is `"{}"` on every row) and `resolve()` with no scope arguments is asserted
byte-identical to the old `effective()`. The rule to add — **a narrower scope may only tighten a
safety key** — belongs with the slice that first populates a narrower scope, not before.

### G-7 — The strategy language cannot see market data the platform already has.

**Urgency: SAFE TO DEFER.** `OptionQuote` carries `bid`, `ask`, `volume`, `oi`, and
`execution_policy.plan_order` reads top-of-book and depth to route orders. None of it reaches a
strategy: `FRAME_COLUMNS` is `date, open, high, low, close, volume`. Importantly this is **not** a
language limitation — Drill 1 proved a component taking `bid`/`ask`/`bid_qty`/`ask_qty` validates and
evaluates, and `IRGraphStrategy.required_inputs` is derived from the graph rather than from a fixed
OHLCV tuple. The gap is the frame contract and the acquisition path, and the `volume` addition of
2026-08-02 is the precedent for how to widen it. L3 owns this.

---

## E. Reuse matrix

Licences were verified by reading each file's first lines, per the standing method warning — never
by pattern match.

| Source | Feature of interest | Licence (verified) | Class | Adaptation | Invariant at risk | Recommendation |
|---|---|---|---|---|---|---|
| **nautilus_trader** | Reset semantics; per-component warmup; injected clock; one path for research and live | **LGPL-3.0** (`repos/nautilus_trader/LICENSE`, read) | **REFERENCE ONLY** | Re-derive from `reviews/nautilus-trader.md` §9 prose | Vendoring or deriving inherits obligations; linking alone is permitted but pulls a second execution engine in | Read §9B before any stateful-component work. Do not depend on it |
| **xyflow** (React Flow) | Graph rendering substrate | **MIT** (`repos/xyflow/LICENSE`, read) | **DIRECT REUSE** (as a dependency) | Standard npm dependency | None | The one legitimate buy-not-build. Already the recorded position |
| **openalgo** | Indian broker adapters, order lifecycle, symbol handling | **AGPL-3.0** (`~/dev/openalgo/README.md:389` → `License.md`) | **REJECT** for code; reference only for behaviour | None permissible | §13's network clause triggers on merely *serving* users — fatal to a hosted product | Teardown already exists at `docs/reports/2026-08-02-openalgo-competitive-teardown.md`. Never import |
| **vectorbt** | Vectorised indicator composition | **Apache-2.0 + Commons Clause** (`_meta/LICENCES.md`, method-verified) | **REJECT** | None | Commons Clause forbids "fees for hosting" — precisely the hosted Strategy OS case | Already cited as the *counter-example* justifying C14 at `app/ir/validate.py:472`. Correct use |
| **comfyui** | Custom nodes indistinguishable from built-ins; cache keys | **GPL-3.0** | **REFERENCE ONLY** | Prose only | Copyleft | Its lesson is already absorbed — C13 and content-addressed kernels are exactly this |
| **backtrader** | Line/indicator abstraction | **GPL-3.0** (read) | **REFERENCE ONLY** | Prose only; **currently unreviewed** | Copyleft | Do not review speculatively (index §5). Trigger: a concrete L1 question |
| **freqtrade** | Deployment/rollback ergonomics | **GPL-3.0** (read) | **REFERENCE ONLY** | Prose only; **currently unreviewed** | Copyleft | Plausible trigger: if the staged L1 rollout wants prior art |
| **node-red** | Subflows-as-nodes; package mechanics | Apache-2.0 | **REFERENCE ONLY** | Prose only | None (permissive) | Relevant to direction J when L4 starts, not before |
| **blender** (geometry nodes) | Node groups, exposed inputs | GPL-2.0+ | **REFERENCE ONLY** | Prose only | Copyleft | Already absorbed into F13 and the group model |

**Reuse conclusion — scoped (amendment A-4).** For the capabilities examined in *this* review, and
specifically for the **G-1 and G-2 corrections**, no external code should be adopted: existing
Strategy OS primitives (`Library`, `resolve()`, `authoring.component()`, the content-address scheme)
are better suited than anything outside, and the two areas where reuse would be most tempting —
broker adapters (OpenAlgo) and execution semantics (Nautilus) — carry the most hostile licences for
a hosted product.

**This is a conclusion about these findings, not a project-wide rule.** Do not quote it as one. The
standing project policy is unchanged and remains:

> Before building commodity infrastructure, inspect (1) Strategy OS itself, (2) OpenAlgo,
> (3) `~/dev/multiverse-of-ideas` and other relevant local clones, (4) suitable external
> open-source implementations. Classify each candidate **DIRECT REUSE / ADAPT/WRAP /
> REFERENCE ONLY / REJECT**. Licence compatibility is mandatory. Differentiated Strategy OS
> architecture must not be distorted merely to reuse outside code.

That policy applies in full to the commodity infrastructure this review defers — the job/worker
boundary (G-3), auth and tenancy (G-5), typed data sources and market calendars (L3), packaging and
signing (L4). Several of those are exactly the areas where buying beats building, and the answer
there is expected to differ from the answer here.

The library's existing rule ("only `reviews/` prose may cross") stands, and this audit found nothing
to change about it. Independently re-verified: the tree contains no reference source code, only the
two prose citations at `app/ir/validate.py:472` and `app/ir/schema.py:44`.

The one genuine reuse recommendation in scope is the one already recorded: **xyflow, MIT, as a
dependency**.

---

## F. Scaling assessment — roughly 100 serious users

The workload: research experiments, backtests, paper strategies, eventually a few live strategies,
market-data consumption, stored evidence.

**Verdict: a modular monolith is the right shape and should stay. Three things need a boundary; none
needs a service.**

| Concern | Today | At ~100 users | Action |
|---|---|---|---|
| **Backtests** | `sweep.py` — one global worker, `raise RuntimeError("a sweep is already running")` | **Hard failure.** The second user is refused | The one real bottleneck. A `jobs` table + claiming worker, in-process. **G-3** |
| **Concurrent runtimes** | One `EngineRunner`, two async lanes (~2.5 s signal, ~1 s risk), one deployment | Per-deployment loops or a scheduler | Deferrable — `Deployment` already exists as the execution root and `deployment_id` is already on `positions`/`trades` |
| **Market-data fan-out** | `get_provider()` — a process-wide singleton, one Kite token | One token per user; fan-out per instrument, not per user | Deferrable. The `MarketDataProvider` seam is the right boundary and already exists |
| **Broker rate limits** | Per-process, implicit | Per-account budgeting | Deferrable; belongs with the second broker account |
| **Job isolation** | None — a sweep shares the process with the risk lane | A failing job must not touch the risk lane | Same fix as G-3. Note hard invariant 2: nothing may block an exit |
| **Large artifacts** | `graph_versions.artifact_json`, `backtest_results` in SQLite | Fine at this scale | Watch, don't act. The 2026-07-23 outage was full-table ORM scans, already fixed with SQL aggregates |
| **Restart / recovery** | Strong. Disarm on start, journal recovery, orphan reconciliation, book-scoped ledgers, `foreign_book_positions` reported at startup and on `/api/health` | Unchanged | None |
| **User isolation** | None. `Principal` exists but every table is global | Owner scoping | **G-5.** Namespace identifiers now (free), schema later |
| **DB contention** | One SQLite file, WAL, `busy_timeout=10000`, `pool_timeout=10`, `pool_pre_ping` | SQLite is plausible at 100 users with WAL if writes stay short; the *write* path is the engine, not the users | Do not migrate speculatively. The trigger is a measured lock-wait, not a headcount |

**Explicitly not recommended:** microservices, event sourcing, a second execution engine, a message
broker, or a Postgres migration. None has a demonstrated need, and the 2026-07-23 outage post-mortem
shows this system's real scaling failures have been *query shape* (full-table ORM scans) and
*memory*, not architecture.

**Boundaries worth having clean now, in one repository and one deployment:** the job/worker boundary
(G-3), the platform component library (G-1), and the signal→intent→order boundary (G-2).

---

## G. Recommended sequence

**Outcome 2 — make one small bounded architectural correction first, then proceed to L1.4.**

Not outcome 3. No foundational contradiction was found. The two capabilities that looked most likely
to produce one — cross-instrument typing and reusable subgraph components — were both tested by
execution and both came back better than expected: the domain axis already makes a cross-instrument
edge a *type error*, and `publish()` already reproduces the shipped ATR body address exactly.

Not outcome 1 only because G-1 is five import lines today and will be more after the next queued
WS-01 slice, and because G-2 costs nothing but must land before L1.4 writes order-lifecycle code
across an unnamed boundary.

**Sequence:**

1. **G-1 — platform component library** (bounded, mechanical). A module owning the platform
   `(Library, implementations)` pair; the five imports repointed at it; the strategy's components
   stay where they are. Acceptance: reference artefact content address and all 18 node cache ids
   byte-identical, `test_ir_strategy_parity.py` green, and a new import guard proven able to go red.
2. **G-2 — name the signal → intent → order boundary** in `WS-02-execution.md`. Documentation only.
3. **Then L1.4, unchanged in scope.**

### Closure — 2026-08-07

Both corrections are **done**, and this section is the record rather than the plan.

- **G-1 shipped.** `app/ir/library.py` composes the platform `(Library, IMPLEMENTATIONS)` pair from
  an explicit `CONTRIBUTORS` tuple and refuses contributor disagreement. All six production call
  sites — the five above plus `research/orchestrator/graph_experiment.py` — take their library from
  it. Identity is byte-identical across the correction, measured by fingerprint over the graph's
  canonical JSON, content address, every component body ref, and every resolved node id, cache id,
  body ref and warmup: `1077ee8cdb53641e9451956994b6800a5c48a8bce6c2625ba3ea44f07c853590` before
  and after. `tests/test_ir_platform_library.py` pins it, and its seam guard was proven able to go
  red by restoring the old import.
- **G-2 shipped as a contract**, at `WS-02-execution.md` §3, "The execution lifecycle boundary".
  No code was required: L1.4 was inspected against its four forbidden assumptions first and deepens
  none of them.
- **G-3 deliberately untouched**, per the amended entry above.

Deferred with a named home, not forgotten: multi-instrument runtime and multi-timeframe resolution
(WS-01 §5); typed data sources, dataset identity, futures continuity and temporal semantics (L3);
component packaging, permissions and marketplace (L4); auth and tenancy (L5 / G-5); the job queue
(G-3, before the second concurrent user, not before).

**Unchanged by this review:** `(ir_graph, live, authoritative)` remains **NOT APPROVED** and is not
designed here. Nothing in this document proposes a change to sizing, routing, risk, live-order
authority, broker behaviour or any real-money path.

---

## Appendix — files inspected

**IR / language.** `app/ir/schema.py`, `validate.py`, `resolve.py`, `runtime.py`, `kernels.py`,
`hashing.py`, `authoring.py`, `catalogue.py`, `edit.py`, `strategies/expanding_z.py`.

**Strategy.** `app/strategy/ir_adapter.py`, `spec.py`, `identity.py`, `registry/__init__.py`,
`registry/base.py`.

**Execution / core.** `app/core/execution_binding.py`, `paper_authority.py`, `execution_book.py`,
`scoped_config.py`, `app/engine/runner.py`, `broker.py`, `broker_protocol.py`, `execution_policy.py`,
`allocator.py`, `ir_shadow.py`.

**Data / persistence.** `app/providers/base.py`, `app/market_data/candles.py`, `app/db/models.py`,
`app/db/session.py`, `app/backtest/engine.py`, `app/backtest/sweep.py`,
`migrations/versions/` (0001–0013).

**API / editor / frontend.** `app/api/ir_edit_routes.py`, `principal.py`, `auth.py`,
`app/editor/descriptors.py`, `frontend/src/views/GraphView.tsx`.

**Documents.** `docs/ARCHITECTURE.md`, `docs/CONTINUE.md`, `docs/engineering/EXECUTION_PLAN.md`,
`docs/rfcs/0001-component-ir.md`, `docs/engineering/workstreams/WS-01-component-ir.md`,
`docs/engineering/decisions/0011`, `0012`, `docs/engineering/reference/multiverse-index.md`.

**Reference library.** `~/dev/multiverse-of-ideas/_meta/LICENCES.md`,
`reviews/nautilus-trader.md`, and the licence files of `nautilus_trader`, `xyflow`, `backtrader`,
`freqtrade`; `~/dev/openalgo/README.md`.

**Probes run** (scratchpad only, never added to the tree): a resolution/measurement probe, a
three-drill language probe (Drills 1, 2, 5) and a publish round-trip probe (Drill 4). All output is
quoted inline above.
