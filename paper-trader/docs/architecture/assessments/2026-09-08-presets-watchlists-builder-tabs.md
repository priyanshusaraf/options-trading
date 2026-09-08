# Presets, watchlists and Build tabs: architecture assessment

Date: 8 September 2026. Assessment of current source and the accepted V0–V6 matrix. This document proposes the implementation changes; it does not claim they are implemented or change the release matrix by itself.

## Decision

Keep the canonical Component IR, validator, resolver, component registry machinery, immutable strategy versions, research-settings histories and monitoring contracts. Extend the product around them. No second strategy representation or execution engine is needed.

The requested behavior crosses preset packaging, user-private ownership, registry composition, watchlist association and editor session state. It cannot be delivered by adding a preset card, a watchlist filter or a tab bar alone. Rework the current watchlist association before finishing monitoring activation: strategy assignments must survive changes between Global, Strategy and Master views without creating duplicate evaluations or alerts.

## Product contracts

| Object | Contents and behavior |
| --- | --- |
| Built-in strategy preset | Versioned canonical strategy, preset-author-supplied strategy-local defaults, suggested instrument list, documentation and dependency requirements. Import creates an independent editable strategy and independent settings/list records. |
| My strategy preset | The same package kind, exported from a user's complete strategy and accessible only to that user. Changes produce new preset versions. |
| Built-in strategy component | Reusable typed graph body, declared inputs/outputs, internal node parameters and pinned component dependencies. Inserts into a strategy without changing its strategy-level settings or watchlist. |
| My strategy component | User-private reusable graph package produced through Export. Uses the same component contracts and validation as built-ins. |
| Strategy watchlist | Explicit instrument membership associated with one strategy. Two strategies may have completely different lists or share instruments. |
| Global watchlist | A manually managed personal list independent of one strategy. It is not the source of every strategy's membership. |
| Master watchlist | A derived view of all strategy watchlists, preserving their strategy associations. It is not another mutable membership list or another monitoring worker. Global membership is not silently included. |
| Build tab | Editor session state identifying a root strategy or one compound instance within it. It is not a strategy revision, component definition or dataset. |

A preset revision is immutable; an imported strategy is editable. These are compatible requirements. Editing import A must not change the template, import B, or an earlier experiment. Re-importing a selected preset revision starts from that revision's original defaults.

“Component presets bring no settings” means no strategy/account preference overrides. Their internal node parameters, ports and data requirements remain part of their mathematical definition.

## Current implementation and affected areas

| Area | Current source evidence | Required change |
| --- | --- | --- |
| Preset import | `app/api/ir_preset_routes.py:copy_preset` calls `original_strategy_presets.instantiate_preset` and `graph_artifacts.create_artifact`. Templates are frozen and imports are deep copies. | Extend the graph-only operation into an idempotent transaction creating graph, explicit local defaults and suggested-watchlist association. Retain template identity/version and return all created identities. |
| Initial preset experience | V3/V4 templates contain a single compound `rules` node. Their internal graph definitions already exist. | Open strategy imports as a readable full strategy diagram with explanations and meaningful input/output boundaries. Reuse those authored bodies; do not create another implementation of their calculations. Preserve existing imported graphs and verify V3/V4 arithmetic parity if built-in template structure changes. |
| Settings | `research/domain/settings.py` stores immutable workspace/strategy preference histories. Sparse strategy overrides inherit workspace values. | Materialize the complete intended preset defaults as local values. Allow explicit later editing or opting into inheritance. Snapshot effective settings on export. Keep account constraints and credentials outside the package. |
| Suggested instruments | `app/core/static_scopes.py` supports immutable owner/project membership revisions; provider selections require actual owned provider records. | Store portable suggestions in a template and resolve them into the importing user's instruments. Never copy another owner's selection address, connection ID or grant. Unresolved suggestions remain visible with a useful next action. |
| Watchlist hierarchy | Existing lists are project-scoped. New monitoring row preferences are keyed by owner/project/scope/member, with a per-row graph choice. | Add explicit personal/global and strategy associations while preserving historical membership snapshots. Allow independent row strategy choices in the Global view where appropriate, rather than making them the only strategy-to-list model. Strategy and Master rows already identify their source strategy; Master edits must update that source association. |
| Master view | No aggregate strategy-watchlist read model exists. | Aggregate by canonical instrument while retaining all strategy/timeframe result rows. Show conflicting results separately. Do not select a winner by symbol or collapse them into one signal. Route edits to the source list. |
| Compound navigation | `resolve.py:_expand_v2_node` already expands nested definitions, applies parameter bindings and preserves authored instance paths. The UI has parameter/help inspection. | Add an explicit Expand/Open component action opening a child Build tab for the specific instance. Returning to the parent still shows the compound node. Opening, closing or arranging tabs must not change executable identity. |
| Compound editing | The catalogue uses immutable registered definitions. Canvas `workingProjection` drops graph-input/output edges; mutation endpoints currently address node ports. | Render typed component boundaries and parameter bindings. Editing built-in/published internals creates a local draft/version and deliberately updates that parent instance's reference; it must not modify every use of the shared component. Boundary editing needs a supported semantic command contract. |
| Multiple Build tabs | `ResearchWorkspace` is keyed by project/graph. Switching sections unmounts Build; staged edits, layouts, selection and undo live inside the builder. Dataset selection is also local to the Backtest view. | Introduce a keyed editor-session controller retaining each tab's draft, undo/redo, viewport, selected dataset, settings context and pending requests. Handle dirty close, reopen, session changes and concurrent edits. Share immutable dataset references, not mutable editor state. |
| Shift+A | Five semantic families exist. The current catalogue includes compounds without a root-versus-component product role. | Add a separate Strategy components library category beside the five families. Include eligible built-in and user-private components only; root strategy presets remain in the preset library. This is not a sixth semantic node family. |
| User-private library and registry | `v2_editor_store` and catalogue/mutation paths use global `REGISTRY`. Frontend catalogue validation hardcodes built-in compound counts/identities. | Store private immutable component/preset revisions and compose a validated request-scoped registry view from permitted definitions. Keep one registry implementation and resolver. Replace hardcoded counts with validated catalogue identity/capability contracts; do not weaken component checks or add user definitions to a process-global catalogue. |
| Export | No connected private strategy/component export workflow was found. Existing Publish saves an immutable strategy version. | Add Export → My presets, with Strategy/Strategy component kinds. Export the whole root strategy document, including its pinned dependency closure; no implicit selection-only export. Root exports include local defaults/suggestions; component exports omit them. Validate component interfaces and unresolved edges. Keep Save version distinct from Export to library. |
| Privacy | `owner_id_for` returns the organisation ID. `created_by` is authorship, not an access restriction. | Add an individual-user boundary for private preset metadata, bodies, dependencies, search, import, export and resolver/cache access. Organisation-wide authorization alone does not satisfy individual privacy. Do not migrate shared graph ownership indiscriminately. |
| Plan limits | Plans have entitlement sets, but no saved-strategy count admission was found in either graph creation path. | Use one server-side strategy-slot admission for blank creation, duplication and preset import, including concurrency and exact retries. No separate import quota. Recommended unit: root strategy lineages, not tabs, versions or exported templates. Actual numerical limits must come from the product plan catalogue. |
| Research, monitoring and data | Runs retain exact graph/data/settings identity; signal events retain graph, dataset, assignment and state identity. | Preserve old results. Editing strategy, component reference, timeframe or settings requires the appropriate new version/revalidation. Sharing one dataset between tabs does not merge experiments. Master views must not create another activation or delivery path. |

Paths in this table are relative to `paper-trader/backend` for Python and `paper-trader/strategy-frontend/src` for frontend files.

## Identity, privacy and clone rules

Keep four identities distinct: preset package revision, imported strategy lineage/version, reusable component revision, and editor tab. A package hash may include settings, suggested lists and documentation; the canonical graph hash continues to describe graph content. Existing executable projection rules continue to determine execution identity.

Root import should be atomic within the existing application persistence boundary. A failed entitlement check or conflicting request must not leave an orphan graph, partial settings copy or unlinked watchlist. Each successful import receives independent identities. Import carries no existing monitoring activation, order authority, broker credential, or completed research result.

A user-private library must check both the workspace/organisation boundary and the individual creator/user boundary. The same check applies when resolving nested private dependencies, not just when listing cards. Cache keys and error responses must not reveal another user's component or preset. An organisation-visible graph must not silently share a user-private dependency. The proposed rule is that a graph containing private components has a coherent restricted audience for the graph and its dependency closure; list, open, resolve and run paths enforce that audience. Export/import does not broaden it. Explicit sharing is outside this scope. This requires a graph-access extension, not a blanket conversion of all existing organisation-owned graphs.

For compound editing, retain the published definition and the parent instance until the user accepts the new local reference. The default edit scope should be the opened instance. Changing all instances or updating a shared private component must be an explicit separate operation. Parent and child tabs cannot maintain independently diverging copies of the same editable body.

Export means publishing a snapshot into the user's own library. A downloadable file can be a separate future action; this assessment does not reinterpret private export as public distribution. To make a smaller component, use a separate draft/version, remove unnecessary material, validate its declared boundary, and export the whole resulting graph. The original strategy and its earlier version remain available.

## Relationship to V0–V6

The [current scope matrix](../../strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md) owns release classification. The latest requirements justify the following proposed amendments; these are not claims that the additions already exist.

| Requirement | Fit |
| --- | --- |
| Transparent root presets, independent defaults, editable copies, Build navigation and strategy/global/master lists | V0 authoring/onboarding and monitoring improvements. They make the existing invited-user journey understandable and usable. |
| Private strategy/component export and reuse | New explicit V0 authoring scope requested here. It shares package/version/dependency foundations with V3 Strategy Assets, but excludes public discovery, sales, licensing, reviews and cross-user distribution. |
| Master watchlist | V0 aggregate monitoring view. It is neither V1.5 dynamic discovery nor V2 allocation/hedge optimization. |
| Dynamic membership chosen from market conditions | Still V1.5. Preserve bounded fan-out, point-in-time membership, churn/resource/provider requirements for that release. |
| Public/paid strategy marketplace | Still V3. The owner vision's strategy packages already include graphs, components, list presets, parameters, documentation and requirements; reuse the local package foundation later. |
| Managed allocation, execution, institutional sharing and enterprise products | No advancement of their V1/V2/V3/V4/V5–V6 authority or commercial scope is implied. |

See [owner vision §13](../../program/owner-directions/2026-08-29/01-UPDATED-OWNER-VISION-V0-TO-V6.md) for the future asset marketplace and [maturity gates](../../program/owner-directions/2026-08-29/08-MATURITY-GATED-PRODUCT-SEQUENCE.md) for advancement requirements. The existing IR RFC already separates editor, language, runtime, research and distribution; nested references and presentation-independent identity support this design.

## Implementation order and acceptance

1. Define package kinds, private ownership, strategy-slot counting and global/strategy/master list associations. Amend the working scope after the assessment; retain historical records.
2. Implement atomic independent root imports with explicit defaults and suggested-list resolution. Prove repeated imports, editing one copy, and importing again retain the original selected template's values.
3. Move mutable editor state into keyed sessions, then add root and child tabs with visible component boundaries. Prove unsaved edits, undo, dataset choice and parent compound representation survive navigation; view-only expansion leaves graph identity unchanged.
4. Add private whole-document Export, immutable package revisions, dependency resolution and component insertion. Prove insertion changes only the destination graph, maps IDs without collisions, respects declared interfaces and preserves settings/list choices.
5. Present Strategy, Global and Master watchlists over the same attributable monitoring records; then complete fresh-data activation, evaluation and alerts against those associations.
6. Verify individual privacy including two users in the same organisation, cross-organisation denial, concurrent final-slot imports, dependency pinning, V3/V4 and strategy007 regressions, migration/restore and signed-in browser journeys. Apply the repository's complexity, coverage, mutation and independent-review requirements to changed code.

This is a meaningful expansion of V0 authoring work. The existing watchlist UI, provider search/history, canonical graph machinery, settings histories and monitoring result contracts remain useful. The new hierarchy and private component contracts must be settled before treating the current watchlist activation model as final.
