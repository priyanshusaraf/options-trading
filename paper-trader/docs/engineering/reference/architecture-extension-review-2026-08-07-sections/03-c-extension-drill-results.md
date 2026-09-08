Reference: [section index](../architecture-extension-review-2026-08-07.md). Read with its scope; this is not a new assignment.

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
