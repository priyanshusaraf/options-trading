# Visual and interaction comparison packet

## Product boundary

The owner already selected a visual direction. This packet does not propose a restyle.

It compares interaction behavior from:

- the current production frontend;
- the standalone Strategy OS visual prototype;
- xyflow;
- Blender Geometry Nodes;
- Node-RED;
- ComfyUI;
- Langflow;
- XState;
- OpenAlgo.

## Current product versus accepted prototype

| Area | Current production frontend | Standalone prototype | Recommendation |
| --- | --- | --- | --- |
| Global navigation | flat tab list with many product surfaces | clear global rail and strategy-local navigation | adopt prototype information hierarchy in a future frontend capsule |
| Strategy context | one Strategy Graph tab | strategy workspace across overview, build, backtest, research, deploy, paper, signal, and live | preserve exact object and version context |
| Graph editing | custom SVG layout, semantic edit commands, layout saves, undo and redo | xyflow movement, resize, reconnect, insert-on-drop, palette, inspector, focus mode | retain canonical backend edit seam; use xyflow as a view layer |
| Evidence | separate panels and research views | visible lifecycle and evidence depth | keep claim → explanation → evidence → raw record |
| Mobile | dedicated top bar; tables guarded for local scroll; backtests disabled | Today, Live, and Activity companion at 390 by 844 | keep mobile for awareness and safe controls, not material graph edits |
| Realtime | one WebSocket and backend health facts | explicit operational states in fixtures | expose transport, subscription, freshness, and provider state separately |

## Repository patterns

| Pattern | Source | Decision |
| --- | --- | --- |
| Editor node is a view model; semantic data stays opaque | xyflow | adopt |
| Presentation state stays outside executable identity | xyflow and current IR layout tables | keep |
| Component author declares ordered parameter panels | Blender | adopt |
| Stable identifier differs from display label | Blender | keep |
| Visual grouping differs from reusable semantic component | Node-RED | keep |
| Nested expansion happens deterministically before execution | Node-RED and Blender | keep |
| One registry drives palette, validator, and runtime | ComfyUI, corrected by Strategy OS versioning | keep |
| Runtime graph expansion changes what ran | ComfyUI | reject |
| Source code embedded in saved nodes | Langflow | reject |
| Pure state transition returns explicit effects | XState | adapt for bounded stateful UI and Workflow controls |
| Inspector, insertable edge, shortcuts, and in-editor execution log | OpenAlgo | adapt behavior, not code or style |

## Graph behavior specification

The frontend should support:

- searchable node palette and Shift+A;
- drag, keyboard, and single-pointer move alternatives;
- type-aware connection hints;
- canonical server validation;
- insert a node on an edge;
- reconnect or remove an edge;
- inspector generated from component descriptors;
- inline values where useful;
- undo and redo as draft edit batches;
- focused graph mode;
- minimap and outline for large graphs;
- find node, find dependency, and trace downstream;
- error localization to authored node and port;
- graph version diff;
- presentation layout save independent from graph identity;
- clear draft, published, admitted, and deployed states;
- no mutation of an admitted or deployed artifact.

## Accessibility findings

Verified local UI guidance returned these high-severity controls:

- pointer dragging needs a single-pointer alternative;
- every operation needs complete keyboard access;
- focus order should match visual order;
- every custom control needs a visible focus state;
- nav-heavy screens should expose a skip-to-main action;
- asynchronous status changes should use one meaningful live status instead of many competing live regions.

The local guidance search returned no relevant match for advanced progressive disclosure after one narrower retry. The progressive-disclosure recommendation therefore comes from the canonical product direction, the accepted prototype, and repository evidence rather than that data set.

## Proposed performance budget

These are acceptance targets for a future measured frontend capsule, not current PASS claims.

| Scenario | Initial budget |
| --- | --- |
| Pointer move on a 300-node visible graph | no sustained frame below 45 frames per second |
| Keyboard command response | visible response within 100 milliseconds |
| Search over 1,000 component descriptors | result list within 100 milliseconds after debounce |
| Open inspector | within 150 milliseconds |
| Save layout | immediate optimistic state; server outcome visible within network-bound timing |
| Load 1,000-node graph | first usable canvas within 2 seconds on the release reference machine |
| Long tables over 100 rows | virtualized or paginated |
| Background job progress | updates coalesced; no layout shift or focus movement |
| Mobile 390 by 844 | no page-level horizontal overflow |

The future capsule must profile before optimizing. It may revise these budgets with recorded hardware and workload.

## Interaction states

Every write interaction should expose:

    IDLE
      → EDITING
      → VALIDATING
      → SAVING
      → SAVED

Failure branches:

    VALIDATING → REFUSED with field or graph location
    SAVING → CONFLICT with current revision
    SAVING → TRANSPORT_ERROR with retry

Deployment interactions should expose:

    DRAFT
      → PREFLIGHTING
      → REFUSED or ELIGIBLE
      → AWAITING_APPROVAL
      → ADMITTED
      → DEPLOYING
      → ACTIVE

No color alone carries these distinctions.

## Rejections

- no new visual style direction;
- no backend semantics recreated in React;
- no graph coordinates in executable identity;
- no drag-only editor;
- no permanent right rail competing with the primary workspace;
- no generic success state when authority is unknown;
- no V2 Dynamic Universe or Workflow UI before backend identity and lifecycle contracts.

## Verdict

KEEP the accepted styling direction. KEEP + HARDEN interaction behavior. Frontend implementation remains owner-gated.
