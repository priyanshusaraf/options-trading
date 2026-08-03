# WS-04 — Editor (visual computational graph)

**Status:** active
**Owner surface:** `backend/app/api/ir_routes.py`, `backend/app/api/ir_layout_routes.py`,
`backend/app/editor/`, their backend tests, `frontend/src/views/GraphView.tsx` and its
transport/tests. Next: S3.3 visual/hand-authored equivalence and lossless reload. The
libraries it consumes — `backend/app/ir/view.py`, `backend/app/ir/edit.py` — are **owned by
WS-01**.
**Last verified:** 2026-08-03 · S3.2b complete

> This workstream is the human authoring surface for the Component IR: a canvas on which a
> strategy is a graph of boxes and wires rather than a Python file. The IR calls this one of
> its five planes (RFC 0001 §1.2) — the plane that **produces** artefacts. The resolved view
> model now has a read-only HTTP route and a React canvas in the existing application shell.
> Sparse positions and visual groups now persist through one presentation revision. Semantic
> node/edge edits publish immutable versions and reconcile presentation in the same transaction.

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
- The **HTTP route(s)** that serve a `GraphView` to the browser and accept edits. The first
  read-only route exists; write routes wait until the viewer and layout separation are proven.
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

**Exports**

| Export | Guarantee |
|---|---|
| `GET /api/ir/graphs/{identifier}` and `/api/v1/ir/graphs/{identifier}` | Resolves only a fixed repository-owned graph catalogue and returns the complete `GraphView` contract under a closed response schema. It is read-only, validates with the real component library, and imports no engine, broker, provider, database or order surface. Unknown identifiers fail with 404 before `resolve()` is called. |
| `GET`/`PUT /api/ir/graphs/{identifier}/versions/{version}/layout` and `/api/v1` mirrors | Reads or atomically replaces sparse moved-node coordinates. The document carries a monotonic revision; stale writes return 409. Unknown graphs/versions, derived or unknown IDs, duplicates, non-finite coordinates and extra fields are refused. |
| `app/editor/layouts.py` | Loads valid sparse positions, filters orphaned IDs on read and replaces all position rows in the same transaction that advances the revision. |
| `GraphView` in the `Strategy Graph` tab | Fetches the fixed graph through the typed REST client and renders a read-only native HTML/SVG canvas. Node cards expose authored paths, definition, every bound parameter, warmup, exact purity policy and full cache identity. Wires are decorative; an accessible table exposes every source and target socket. |

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

**Blocked by:** nothing external. Live-engine adoption remains separately owner-gated — see §8.

**Currently blocking:** nothing. No workstream is waiting on the editor.

## 4. Completed

**Read-only application route — `049b699`, 2026-08-03.** One GET route exposes the repository's
`expanding_z_v4` graph as the exact `GraphView` JSON contract: 18 resolved nodes, 35 resolved
edges, six layers and 302 bars of composed warmup. It is mounted on `/api` and `/api/v1`, uses a
closed response model, validates F7/F8 with the component mapping, and rejects unknown client
identifiers before resolution. Audit removed catalogue and SVG endpoints from the first cut
because the accepted slice requires one JSON route and neither extra endpoint had a consumer.
Fourteen route tests cover registration, fixed-catalogue access, read-only graph identity,
ordered serialization, errors, response schema and the fresh-process import closure.

**Read-only React viewer — `f61dfe4`, 2026-08-03.** The existing desktop and mobile tab shell
now opens `Strategy Graph`. A typed client fetches the fixed route and rejects non-success
responses. The canvas renders native semantic node cards and SVG Bézier wires without a graph
dependency; an accessible connections table carries socket direction. It shows the complete
inspection contract, keeps the exact impurity policy in text, and has explicit loading, error,
empty and edge-free states. Seven render tests, two transport tests and a shell wiring guard
were added. The complete frontend suite is 153 passing tests; typecheck and the production build
pass. Live-browser acceptance at desktop and a 390×844 override rendered 18 node articles, 35
wires and 35 connection rows with no console errors. At the phone width the 2,216px canvas sits
inside a 356px scroller while the page itself does not overflow.

The underlying editor libraries remain owned by WS-01:

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

Verified 2026-08-03 through `f61dfe4`: `app.api.ir_routes` loads no `app.engine`, `app.providers`,
`app.broker`, `app.db` or `app.options` module in a fresh process. The IR is reachable through a
read-only application route, but the engine still does not consume it.

**Sparse layout persistence and closed API — current S1.1 slice, 2026-08-03.** Alembic `0005`
adds a layout head keyed by graph identifier/version and child coordinates keyed by authored
instance ID. An empty layout retains a revision. GET returns revision zero without creating a
row; PUT replaces the sparse set under `base_revision`, and a stale write returns 409 without a
partial change. Reads filter orphaned IDs and the next successful write deletes them. The fixed
catalogue moved to `app/ir/catalogue.py` so graph and layout routes resolve the same repository
object without coupling the read-only graph route to the database. The identity proof saves,
reloads and renders a moved position while graph content address, component versions, node cache
identities and experiment binding remain unchanged. Revision downgrade removes only the two
layout tables and preserves the money record.

**Persistent rename and override interaction — S3.2a, 2026-08-03.** A coherent editor GET and
closed mutation POST now carry authored graph state, resolved view, editable parameter descriptors,
sparse layout and canonical command receipts. Rename and set/clear override publish one immutable
version under the draft revision. Response-construction, version-insert and layout-preparation
failures roll back the whole transaction. The React surface renders authored parameters only,
retains invalid or rejected intent, reports exact clauses and paths, guards stale responses and
uses backend receipts for undo/redo. Backend `7cc6525` and frontend `197c4e9` are published; the
shared-persistence acceptance checkpoint and deterministic smoke checks pass.

**Structural and visual-group interaction — S3.2b, 2026-08-03.** Add/remove node and typed
connect/disconnect operations now pass only through the final-state `app.ir.edit.apply_batch()`
boundary. Visual groups live beside layouts and are excluded from every executable identity.
Semantic publication and presentation reconciliation share one rollback boundary; exact receipts
restore both halves during undo/redo. The editor document publishes server-derived component and
socket descriptors, and React exposes accessible structural, membership, frame and collapse
controls without inferring topology. Seven named negative guards passed after restoration. Full
acceptance passed 2,794 backend tests with 6 skips, 195 frontend tests, typecheck, production build
and both deterministic smoke scripts.

## 5. Active roadmap

- [x] **Read-only backend route for a `ResolvedGraph`.** One backend route resolves a named
      repository graph, calls `graph_view()`, and returns the complete `ViewNode`/`ViewEdge`
      contract. Committed as `049b699`; full backend acceptance passed.
- [x] **React rendering of the `ResolvedGraph`.** Draw the JSON contract in the existing app.
      Per node show: instance path (`container`
      + `label`), `definition` (`identifier v<version>`), bound `params`, `warmup` in bars, and
      `cache_id`. Distinguish `derived` nodes and non-`pure` nodes visually, as `to_svg` already
      does. No editing, no dragging, no persistence. **This is the item that first makes the IR
      usable through the running application.** Acceptance:
      `expanding_z_v4` renders in the browser with node count, edge count and total warmup
      matching `scripts/render_ir_graph.py` output for the same graph. Use `lib/api.ts` and the
      existing shadcn primitives; add no graph library in this read-only slice. Committed as
      `f61dfe4`; browser acceptance matched 18 nodes, 35 edges, six layers and 302 bars.
- [x] **The layout side table (F13).** Persist `instance_id → (x, y)` beside the graph, keyed by
      `(graph identifier, version)`, and feed it to `graph_view(graph, layout=...)`. The
      constraint is load-bearing and already has a test at the library level: dragging a node
      MUST NOT change the graph's content address. Add the equivalent assertion at the route
      level — save a position, re-read the artefact, compare `content_address`. Sparse by
      construction: never write a row for a node the author has not moved, so an unmoved node
      keeps its derived position and the derived layout stays the default. Decide and write down
      what happens to an orphaned entry when its node is removed. Implemented in the current
      S1.1 slice with optimistic concurrency, orphan filtering/cleanup and migration rollback.
- [x] **Conflict-safe layout interaction.** Load the sparse layout into the existing viewer,
      move authored nodes by pointer and keyboard, and save the complete sparse set against its
      revision. Show unsaved, saving, saved, conflict and error states. A 409 or network failure
      must preserve the user's local positions and offer an explicit reload/retry path. Published
      through `22a148f`.
- [x] **Mutation in the UI.** Rename and set/clear override are complete. Structural
      add, delete, connect, disconnect and group operations are wired to accessible controls. Every call
      returns a new artefact; the client replaces accepted state from the coherent response and
      never patches that state in place (C2). Render `EditRejected` as the clause plus JSON path,
      not as a generic failure. Grouping remains subject to the F12 executable-versus-presentation
      boundary. S3.2b resolves groups as separately revisioned presentation state and publishes
      semantic changes with atomic presentation reconciliation.
- [ ] **Round-trip proof.** Author a graph entirely through the UI that is byte-identical, by
      content address, to a hand-written artefact for the same strategy. Until this passes, the
      editor is a viewer with buttons.

## 6. Acceptance criteria

Nothing in this workstream is done without all of:

```bash
# backend, from backend/
.venv/bin/python -m pytest -q tests/test_ir_view.py tests/test_ir_edit.py
.venv/bin/python -m pytest -q tests/test_ir_layout_routes.py tests/test_schema_migrations.py
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
- **`to_svg` styling is inline and duplicated from the React canvas** — it defines its own light/dark
  palette rather than the app's shadcn CSS variables. That is correct for a standalone file that
  must open in any browser with no stylesheet. The browser viewer deliberately implements the
  picture separately so it can expose semantic cards and a socket table. Counts and warmup are
  pinned through route and browser acceptance, but visual layout equivalence is not. Trigger for
  consolidation: the first drift in node placement or edge routing between the two renderers.
- **`graph_view` assigns rows greedily per layer**, breaking ties on specification order. It is
  deterministic and readable, and it will produce crossing edges on any non-trivial graph. Cost:
  cosmetic until a graph gets wide. Trigger: a graph where the picture stops being legible.

## 8. Blockers

- **No blocker for the read-only editor workflow.** The owner explicitly authorised the
  application-level viewer. It does not execute a graph or change live trading behaviour.
  Adoption by the live engine remains a separate owner-gated migration under RFC Appendix C(d).
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
