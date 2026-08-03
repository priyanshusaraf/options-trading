# WS-04 — Editor (visual computational graph)

**Status:** not started
**Owner surface:** none yet. When it starts: `frontend/src/views/GraphView.tsx` (or
equivalent), plus whatever route serves a `GraphView` from the backend. The libraries it
consumes — `backend/app/ir/view.py`, `backend/app/ir/edit.py` — are **owned by WS-01**.
**Last verified:** 2026-08-03 · commit `cdbe686`

> This workstream is the human authoring surface for the Component IR: a canvas on which a
> strategy is a graph of boxes and wires rather than a Python file. The IR calls this one of
> its five planes (RFC 0001 §1.2) — the plane that **produces** artefacts. Today the plane
> exists only as two pure Python libraries and a script that writes an SVG to disk. There is
> no HTTP route and no React component, so nothing a user can click has ever touched the IR.

---

## 1. Vision

An author opens a strategy and sees what it actually computes: nodes laid out left-to-right in
dependency order, each labelled with the authored name, the component identifier and version it
resolves to, its bound parameters, its warmup in bars, and its cache identity. Edges show which
socket feeds which. Derived nodes and impure nodes are visually distinct from the rest, because
the two properties that most often surprise you — "this needs 200 bars before it says anything"
and "this reads account state, so it is not replayable" — are the two the picture should never
hide.

The author then edits on that canvas — add a node, wire it, override a parameter, box a few
nodes together for tidiness — and every edit either produces a conforming artefact or is
refused with the clause it would have broken. The canvas is not a code generator that emits
Python; it edits the IR directly, and the IR is the source of truth (RFC §1.1). What runs is a
resolution of the artefact the author saw.

The end state that makes this worth reaching: today a strategy change means editing Python in a
registry module that the engine auto-discovers, and the relationship between what you wrote and
what actually executes is carried entirely in your head. A visual editor over the IR makes that
relationship inspectable — and because the same resolution feeds the runtime and the research
plane (C12), the picture is not a documentation artefact that can drift. It is the thing.

## 2. Scope

**In scope.**

- The **UI surface** for authoring and inspecting IR graphs: canvas, node rendering, edge
  rendering, selection, drag, parameter inspector, validation error presentation.
- The **HTTP route(s)** that serve a `GraphView` to the browser and accept edits. None exist
  today; designing them is this workstream's first real decision.
- **Presentation-state persistence** (F13): a side table keyed by `instance_id`, holding
  positions, group boxes, collapse state and viewport. Deciding where it lives (which DB, which
  key namespace, what happens to an entry whose node was removed) is this workstream's problem.
- **Visual grouping** (F12) as an editor feature: the box, its label, its member set, and the
  rule that it is not a publishable or versionable thing.
- Surfacing `EditRejected` to a human: which clause, which JSON path, and what the author should
  do instead.

**Out of scope.**

- **The IR language, its validator, resolver, hashing, and the `view.py`/`edit.py` libraries
  themselves** — WS-01 Component IR. This workstream is a *consumer*. If `graph_view()` needs a
  new field, that is a WS-01 change with a WS-01 test, requested from here.
- **Executing a graph.** The editor produces artefacts; it never runs one. Execution properties
  and the runtime are WS-02 Execution.
- **Generating or searching for graphs.** A different plane (RFC §1.2); WS-03 Research owns
  proposal, search and the code-gen builder. C14 makes the boundary normative: components
  compute, searchers search.
- **Distributing a component someone else authored** — WS-05 Marketplace. A component the author
  wrote locally needs no trust model; one that arrived over a wire does.
- **Serving the built SPA, the reverse proxy, the deploy** — WS-06 Deployment / WS-07
  Infrastructure.
- **The existing trading dashboard** — WS-08 Cockpit UI. The editor will live inside the same
  React app and reuse its shadcn primitives and `lib/api.ts` client, but the dashboard's views,
  its `/ws` live state and its settings surface are not this workstream's to change.

## 3. Interfaces

**Exports** — nothing yet. This workstream has shipped no symbol, no route and no component, so
there is nothing another workstream may depend on. The first export will be the read-only graph
route named in §5; it is listed here only once it exists.

| Export | Guarantee |
|---|---|
| — | nothing yet |

**Consumes**

| Consumed | From | Why |
|---|---|---|
| `graph_view(graph, layout=None) -> GraphView` (`app/ir/view.py`) | WS-01 | Turns a `ResolvedGraph` into the view model. Layering is longest-path, so no edge points backwards; row order breaks ties on specification order, so the picture is a function of the graph and not of dict iteration. |
| `ViewNode`, `ViewEdge`, `GraphView` (`app/ir/view.py`) | WS-01 | The view model. `ViewNode` carries `instance_id`, `label`, `container`, `definition`, `params`, `warmup`, `purity`, `cache_id`, `derived`, `layer`, `row`, `placed`. `GraphView.layers` is derived. These field names are the wire contract for whatever JSON the route emits. |
| `Layout` (`app/ir/view.py`) | WS-01 | F13 in code: `positions` maps `instance_id → (x, y)`, sparse — an unmoved node keeps its derived position. `Layout.placed()` is the only lookup. |
| `to_svg(view) -> str` (`app/ir/view.py`) | WS-01 | A self-contained SVG: no external stylesheet, no script, no font file, light and dark via `prefers-color-scheme`. Useful as a zero-dependency first rendering and as the fallback for a headless context. |
| `add_node`, `remove_node`, `connect`, `disconnect`, `set_override`, `clear_override`, `group`, `rename` (`app/ir/edit.py`) | WS-01 | Every edit validates its result before returning and returns a **new** artefact rather than mutating its input (C2). Nodes are addressed by `instance_id`, never display name (F2). `remove_node` also drops every edge that touched the node and every group membership — one operation, because leaving them would dangle. |
| `EditRejected` (`app/ir/edit.py`) | WS-01 | The refusal type. Carries `.action` and `.violations` (a tuple of `Violation`, each with clause and JSON path). This is what the UI renders when an edit is illegal; it is not an internal detail. |
| `resolve(graph, library) -> ResolvedGraph` (`app/ir/resolve.py`) | WS-01 | The editor renders a *resolved* graph, not a raw artefact, because warmup, purity and cache identity only exist after resolution. |
| REST transport conventions (`frontend/src/lib/api.ts`), shadcn primitives (`frontend/src/components/ui/`) | WS-08 | The editor will be a route inside the existing SPA; it should not invent a second HTTP client or a second component vocabulary. |

**Depends on:** WS-01 (the whole consumed surface above), WS-08 (the app shell it will live in),
WS-07 (the FastAPI app that would host a route).

**Blocked by:** nothing external. The libraries it needs exist and are tested. What is missing is
a decision, not a dependency — see §8.

**Currently blocking:** nothing. No workstream is waiting on the editor.

## 4. Completed

**Nothing yet in this workstream.** Every artefact the editor would consume was built and is
owned by WS-01:

- `app/ir/view.py` — read-only view model plus SVG renderer, with derived layout (WS-01).
- `app/ir/edit.py` — eight validate-on-result edit functions plus `EditRejected` (WS-01).
- `scripts/render_ir_graph.py` — renders `expanding_z_v4` to a standalone SVG file; reads
  nothing from the network and touches no database (WS-01).
- `tests/test_ir_view.py`, `tests/test_ir_edit.py` — including
  `test_a_layout_does_not_change_the_graphs_content_address`, which is F13 asserted as an
  equality between content addresses before and after a layout is applied, and
  `test_renaming_does_change_the_artefacts_content_address`, its deliberate counterpart: a
  display name **is** part of the artefact even though nothing references it (F2), so a rename
  does move the hash (WS-01).

Verified 2026-08-03 at `cdbe686`: `grep -rn "app.ir" backend/app --include='*.py'` outside
`backend/app/ir/` returns exactly one hit, a comment in
`app/strategy/registry/expanding_z_v4.py`. `backend/app/api/routes.py` contains **zero**
references to `app.ir`. The IR is not reachable from the running application by any path.

## 5. Active roadmap

- [ ] **A read-only rendering of a `ResolvedGraph`.** One backend route that resolves a named
      IR strategy, calls `graph_view()`, and returns JSON with the `ViewNode`/`ViewEdge` field
      names verbatim; one React route that draws it. Per node show: instance path (`container`
      + `label`), `definition` (`identifier v<version>`), bound `params`, `warmup` in bars, and
      `cache_id`. Distinguish `derived` nodes and non-`pure` nodes visually, as `to_svg` already
      does. No editing, no dragging, no persistence. **This is the item that first makes the IR
      part of the running application** — today it is a library the app cannot see. Acceptance:
      `expanding_z_v4` renders in the browser with node count, edge count and total warmup
      matching `scripts/render_ir_graph.py` output for the same graph.
- [ ] **The layout side table (F13).** Persist `instance_id → (x, y)` beside the graph, keyed by
      `(graph identifier, version)`, and feed it to `graph_view(graph, layout=...)`. The
      constraint is load-bearing and already has a test at the library level: dragging a node
      MUST NOT change the graph's content address. Add the equivalent assertion at the route
      level — save a position, re-read the artefact, compare `content_address`. Sparse by
      construction: never write a row for a node the author has not moved, so an unmoved node
      keeps its derived position and the derived layout stays the default. Decide and write down
      what happens to an orphaned entry when its node is removed.
- [ ] **Mutation in the UI.** Wire the eight `edit.py` functions to canvas gestures: add,
      delete, connect, disconnect, set/clear override, group, rename. Every call returns a new
      artefact — the client must replace its copy, never patch in place (C2). Render
      `EditRejected` as the clause plus the JSON path, not as a generic failure toast; the
      violation names the rule the author broke and that is the whole value of it. Grouping is
      F12: a group boxes nodes for tidiness and is **neither versionable nor publishable** — the
      UI must not offer "publish this group" or "version this group", because offering it is how
      the distinction erodes.
- [ ] **Round-trip proof.** Author a graph entirely through the UI that is byte-identical, by
      content address, to a hand-written artefact for the same strategy. Until this passes, the
      editor is a viewer with buttons.

## 6. Acceptance criteria

Nothing in this workstream is done without all of:

```bash
# backend, from backend/
.venv/bin/python -m pytest -q tests/test_ir_view.py tests/test_ir_edit.py
.venv/bin/python -m pytest -q tests research_tests      # both suites, no regressions
.venv/bin/python scripts/render_ir_graph.py /tmp/ws04.svg

# frontend, from frontend/
npm run typecheck
npm test
npm run build
```

Plus, specific to this workstream:

- Any route added is exercised by a test in `backend/tests/`, not merely by hand.
- Any change that stores presentation state is accompanied by an assertion that the graph's
  `content_address` is unchanged across a store-and-reload cycle (F13).
- No change to `app/ir/view.py` or `app/ir/edit.py` lands from this workstream without the
  corresponding WS-01 test; those files are WS-01's surface.

## 7. Known technical debt

- **`scripts/render_ir_graph.py` hardcodes one strategy** (`app.ir.strategies.expanding_z`).
  Fine as a proof, useless as a tool the moment a second IR strategy exists. Cost of leaving it:
  none today. Trigger: a second graph in `app/ir/strategies/`.
- **`to_svg` styling is inline and duplicated from nothing** — it defines its own light/dark
  palette rather than the app's shadcn CSS variables. That is correct for a standalone file that
  must open in any browser with no stylesheet, and wrong the moment the same rendering appears
  inside the SPA. Trigger: the first roadmap item. Expect the browser rendering to be a separate
  implementation, not a reuse of `to_svg` — and expect that to be a deliberate second
  implementation of a picture, which is exactly the shape that produced the `candles.py` defect.
  If both survive, one of them must be derived from the other or pinned by a shared test.
- **`graph_view` assigns rows greedily per layer**, breaking ties on specification order. It is
  deterministic and readable, and it will produce crossing edges on any non-trivial graph. Cost:
  cosmetic until a graph gets wide. Trigger: a graph where the picture stops being legible.

## 8. Blockers

- **A deliberate decision, not an oversight: the IR is not wired into the running application.**
  There is no route and no React. This is the constitutional position — adoption in a running
  path is RFC 0001 Appendix C(d) and owner-blocked, and wiring the language into a production
  trading app ahead of that would create exactly the shape this codebase has already been burned by (a mechanism that exists,
  looks live, and is load-bearing before anyone agreed it should be). The first roadmap item is
  the moment that changes, and it needs an owner decision, not an implementation.
- **RFC 0001 is accepted** (2026-08-02, `97d6bbb`); the grammar the editor edits now moves only by
  amendment under RFC §6, not freely.

## 9. Future work

- **Subgraph navigation** — descend into a nested subgraph and back out. F11 nests by
  `(identifier, version)` reference, never by inlining, so the editor must show a nested graph
  as a reference with its own canvas rather than a flattened blob. Trigger: the first graph with
  a nested subgraph a human wants to edit.
- **Publish-a-subgraph-as-a-component.** C15 makes this a mechanical derivation from the
  declared interface, introducing no information the interface does not already carry — so it is
  a button, not a form. Trigger: an author wanting to reuse a box they drew.
- **Diffing two graph versions visually.** Trigger: the first migration under F1's version stamp.
- **Live overlay** — showing the current bar's value flowing through each node while the engine
  runs. Trigger: someone asking "why did it not fire?" and the answer needing more than logs.
  Note this crosses into WS-02 and would need a value-tap that C13 and C9 both survive.
