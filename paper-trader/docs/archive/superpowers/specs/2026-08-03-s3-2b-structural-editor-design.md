# S3.2b Structural Editor and Presentation Groups Design

Date: 2026-08-03
Status: Accepted owner contract
Workstream: Strategy OS WS-04 / S3.2b

## Scope

S3.2b adds authored-node creation and removal, typed socket connection and disconnection, and visual-group management to the persistent editor. Semantic Component IR changes create immutable graph versions. Visual groups are revisioned presentation state beside sparse node positions and never enter executable graph content.

The user-visible scope is closed to:

- add and remove an authored node;
- connect and disconnect authored component sockets;
- create, rename and remove a visual group;
- add or remove authored nodes from visual groups;
- persist group frame and collapse state;
- accessible component, node and socket selection;
- exact request, IR-validation and revision-conflict feedback;
- undo and redo across semantic and presentation changes;
- lossless coherent reload.

Reusable subgraphs, nested component publication, execution, Python input, marketplace behavior and live adoption remain outside this slice.

## Reconciliation of `group()` with F12 and F13

RFC 0001 currently has a contradiction. Its graph grammar admits `groups`, and `app.ir.edit.group()` appends a group to graph JSON. F12 says a visual group is neither versionable nor publishable. F13 says presentation state persists beside the graph and is excluded from semantic hashing. Persisting the current `group()` result would make a cosmetic box create an immutable executable version and content address.

S3.2b resolves the contradiction as follows:

1. `app.ir.edit.group()` is deprecated as an executable edit and changed to reject every call with F12 guidance. It remains importable for one compatibility window so callers receive an explicit architectural refusal instead of an import failure or silent semantic change.
2. Non-empty `groups` in executable graph JSON are rejected by validation. The format-v1 `groups` key remains a legacy reserved field and canonical executable documents retain the existing empty list. This preserves all existing immutable version bytes and content addresses; S3.2b does not rewrite history.
3. New visual groups are stored only in presentation tables governed by the same presentation revision as positions.
4. RFC 0001 receives an erratum: the graph grammar's `group` production and the old primitive described a presentation concept in the executable structure. For format version 1, only the empty reserved field is conforming; the actual group record belongs to presentation state.
5. No hash function will strip arbitrary non-empty `groups` and then hash the rest. That approach could let different immutable JSON documents claim one executable identity. Rejection plus canonical empty storage prevents that identity alias.

The name `group` is not reassigned to reusable subgraphs or semantic composition. A future semantic concept needs a separate RFC, vocabulary and format version.

## Semantic operation contract

The semantic edit union extends the existing closed HTTP vocabulary with:

- `add_node`: authored `instance_id`, pinned component identifier/version, bounded overrides, optional domain and exact secret-parameter identifiers;
- `remove_node`: authored `instance_id`;
- `connect`: source authored instance/socket and target authored instance/socket;
- `disconnect`: the same exact edge identity.

Existing `set_display_name`, `set_override` and `clear_override` remain valid. Raw graph replacement, arbitrary graph fields, caller-selected graph versions, code and unknown operations remain forbidden.

The backend publishes component descriptors and graph-boundary descriptors in the coherent editor document. A component descriptor contains the pinned component identity, display name, declared parameters and authored input/output sockets with exact wire types and default-source status. Graph-boundary descriptors expose the current graph interface as `graph.input` producers and `graph.output` consumers. Authored-node descriptors expose their component sockets. The frontend renders only these descriptors. It does not infer socket existence, direction, compatibility, domain, derived topology or component defaults.

The server limits a semantic batch to 32 operations and applies the existing recursive JSON bounds to overrides. Instance, component, group and socket identifiers retain the 128-character request limit. Components must exist in the server library at the selected version.

Ordinary `add_node` and `connect` requests append in authored specification order. Canonical receipt inverses may also carry server-issued `node_index` and `edge_index` values. These bounded indexes restore the exact prior array order because format-v1 content addressing and deterministic row ordering include specification order. They are closed semantic fields, not raw JSON or client-selected versions.

## Final-state batch validation in `app.ir.edit`

The public `app.ir.edit` boundary gains a typed semantic-batch operation model and `apply_batch()` function. Individual legacy helpers keep their validate-on-result behavior. `apply_batch()` uses private pure transformers for each closed operation, then validates only the final graph with the real component library. The route resolves that final result before persistence.

This permits temporarily incomplete internal states such as adding a node before connecting its required input, or disconnecting an old source before connecting its replacement. These states exist only as local Python values inside one request. They are never stored as drafts, graph versions, responses or receipts.

`apply_batch()` returns either one final conforming graph or an `EditRejected`. Primitive-local refusals such as duplicate instance IDs and missing exact edges retain their operation index. Whole-result validation and resolution failures use a null operation index because no single operation is authoritative.

Removing a node uses the accepted IR removal transformer and removes every incident semantic edge in the same semantic operation. The presentation repository independently reconciles positions and group memberships inside the same database transaction.

Architecture guards require the route to call `app.ir.edit.apply_batch()`. Reimplementing node or edge mutation in the API or repository is forbidden.

## Canonical semantic inverses

The backend constructs the semantic inverse from exact pre-operation state while applying the batch. It reverses operation order:

- `add_node` inverts to `remove_node`;
- `remove_node` inverts to `add_node` with the exact component reference, overrides, domain, secret-parameter identifiers and original node index, followed by exact `connect` operations with original edge indexes for every removed incident edge;
- `connect` inverts to `disconnect`;
- `disconnect` inverts to `connect` at the original edge index;
- rename and override inverses retain the S3.2a rules.

The inverse itself is submitted through the same closed semantic batch and validated only in its final state. There is no `restore_graph`, raw node JSON replacement or client-supplied immutable version.

## Presentation model and migration

`IrGraphLayout` remains the presentation revision head for one immutable graph version. Its revision now governs one coherent presentation document containing:

- sparse authored-node positions;
- visual group records;
- group membership;
- group frame (`x`, `y`, `width`, `height`);
- group collapsed state.

Migration `0007` adds:

- `ir_graph_layout_groups`, keyed by graph identifier, graph version and group identifier, with display name, frame and collapsed state;
- `ir_graph_layout_group_members`, keyed by graph identifier, graph version, group identifier and authored instance identifier, with a cascading foreign key to its group.

The parent presentation head keeps its existing graph-version foreign key. Membership cannot use a database foreign key to authored nodes because nodes live inside immutable JSON. Repository validation therefore checks membership against the exact authored-node set before flush and again when constructing a response.

The migration is additive. Its downgrade removes only the group-member and group tables. Existing layouts, positions, graph versions, projects, experiments and money records remain. Model-to-migration equivalence and `0007 -> 0006 -> 0007` are required.

## Closed presentation operation contract

Presentation-only mutations use:

`POST /api/ir/projects/{project_id}/graphs/{identifier}/presentation-edits`

The versioned router mirrors it under `/api/v1`. The request carries the accepted graph draft revision, `base_presentation_revision`, and one to 32 closed operations. It carries no graph version; the server resolves the current immutable head from the accepted graph revision. The operations are:

- `create_group` with identifier, display name, optional authored members, validated frame and collapsed state;
- `rename_group`;
- `remove_group`;
- `add_group_member`;
- `remove_group_member`;
- `set_group_frame`;
- `set_group_collapsed`.

Presentation requests cannot change positions in this slice; the existing layout PUT remains the full sparse-position replacement API. Group edits preserve positions. Layout PUT preserves groups. Both advance the same presentation revision and therefore conflict rather than overwrite one another.

A presentation-only success does not create a graph version, advance the graph draft revision, change executable JSON or alter any executable identity. It returns the complete coherent editor document with unchanged graph identity and a new presentation revision.

Group identifiers are unique within the presentation document. Members must be authored nodes in the current immutable graph. Derived, unknown and removed nodes are rejected. A group may be empty. Removing a group removes its membership rows. A node may belong to more than one visual group because grouping is visual organization, not semantic containment.

Frames require finite coordinates, positive finite width and height, and the same bounded numeric policy as positions. Collapse state is an explicit boolean. No arbitrary visual metadata object is accepted.

## Atomic semantic publication and presentation reconciliation

Every semantic request carries `base_revision` and `base_presentation_revision` from one coherent editor document. A semantic publication uses one SQLAlchemy transaction:

1. verify active project ownership and graph ownership;
2. verify graph draft revision, published-head coherence and current immutable version;
3. load the source presentation head and verify its revision;
4. normalize the closed semantic batch and construct exact semantic inverses from the pre-operation graph;
5. call `app.ir.edit.apply_batch()` and validate only its final graph;
6. resolve the final graph and construct its server-derived view and descriptors;
7. compute the executable content address from the complete canonical graph JSON;
8. insert the immutable graph version;
9. copy the source presentation into a new presentation head for the new graph version;
10. remove positions and group memberships for authored nodes absent from the final graph;
11. apply an optional separately validated new-node position delta; otherwise added nodes receive no stored position;
12. flush the new presentation head, groups, memberships and positions;
13. advance graph head, published revision and draft revision;
14. construct the canonical receipt and complete editor response;
15. commit only after response validation succeeds.

The new presentation head starts at revision 1. The receipt records this exact resulting revision. A stale graph or presentation revision returns 409 and changes neither side.

Structural semantic actions are disabled while the browser has an unsaved local position draft. The user saves or reloads positions first. This prevents the frontend from pruning local positions by inferred topology. After semantic success it adopts the server's complete presentation document.

Failure seams after semantic-version insertion, before presentation reconciliation, during reconciliation, after presentation flush and during response construction must roll back graph version, graph head, graph revisions, presentation head, presentation revision, positions, groups and memberships.

## Presentation deltas and unified receipts

The coherent command receipt contains:

- `semantic_forward_operations`;
- `semantic_inverse_operations`;
- `presentation_delta` with exact forward and inverse closed presentation changes;
- base and resulting graph draft revisions;
- base and resulting graph versions;
- resulting executable content address;
- base and resulting presentation revisions.

The presentation delta is server-generated. It records exact before/after values needed to reproduce:

- position removal or restoration;
- group creation or removal;
- group display-name, frame and collapsed-state changes;
- membership addition or removal.

Receipt deltas use a closed reconciliation vocabulary: `set_position`, `clear_position`, `put_group`, `remove_group`, `add_group_member` and `remove_group_member`. `put_group` carries one complete validated group record. Ordinary group requests use the narrower user-facing presentation vocabulary. A semantic request may include only `set_position` for a node introduced by that same final batch; all other reconciliation operations are server-derived. Undo and redo may replay the exact receipt delta, still subject to current revisions, authored-node membership validation and final coherent-response validation. No arbitrary metadata or graph JSON is accepted.

For a semantic node removal, the forward delta removes its stored position and every membership; the inverse delta restores the exact prior position and memberships. For node addition, the forward delta is empty unless the request includes a validated position; the inverse removes that position when present. Identity-preserving semantic changes carry presentation state without a logical presentation delta even though the new version receives a fresh revision-1 presentation head.

For presentation-only commands, semantic arrays are empty and graph revision, version and content address are unchanged. For semantic commands, both semantic arrays and any reconciliation delta are present.

Undo submits the receipt's semantic inverse plus presentation inverse against the currently accepted graph and presentation revisions. Redo submits its semantic forward plus presentation forward. The backend applies and validates both; the frontend never calculates an inverse, topology or membership reconciliation. Every successful undo or redo returns a new canonical receipt and complete document.

If either half cannot be applied exactly, the whole command fails. Restoring only the semantic graph or only presentation state is forbidden.

## Coherent editor document

The S3.2a editor document is extended with:

- `component_catalogue` containing server-derived component, parameter and socket descriptors;
- `graph_sockets` containing server-derived graph-boundary input and output descriptors;
- authored-node socket descriptors;
- a presentation document containing `revision`, positions and groups;
- the unified command receipt.

The top-level graph version and presentation document graph version must match. The authored graph, resolved view, editable authored nodes, component catalogue and presentation memberships must all describe the same immutable graph version.

Every response model remains closed. The backend constructs the whole document before commit for mutations. GET rejects unpublished or incoherent graph heads as before and filters no invalid presentation state silently; invalid stored membership is an `EDITOR_DOCUMENT_FAILED` server error because accepting a partial presentation document would hide corruption.

## Frontend state and controls

The frontend continues to store a last accepted server document, one local command draft, server receipts, request identity and exact failure details. Successful responses replace the accepted authored graph, resolved view, component catalogue, presentation state, revisions and identities together. Stale responses are ignored.

Accessible controls use native labels, selects, buttons, field descriptions, disabled semantics, alerts and live status:

- component selection comes only from `component_catalogue`;
- add-node requests require an authored instance identifier and pinned component choice;
- remove-node controls list authored nodes only and state that incident edges will also be removed;
- connection controls select source output then compatible target input from server descriptors;
- disconnect controls list exact authored edges from the accepted authored graph;
- group controls create, rename and remove groups and manage authored-node membership;
- frame and collapse controls operate through presentation edits.

Client compatibility filtering is a convenience only. The backend performs authoritative socket and final-graph validation. Derived resolved nodes never appear in structural or grouping selectors.

Conflict, validation, server and network failures retain the command draft and accepted document. Explicit reload discards unresolved intent and history. A successful ordinary command clears redo. Structural commands are blocked while layout positions are locally dirty; presentation group commands use the accepted presentation revision and do not discard positions.

## Error contract

The existing closed editor envelope gains `PRESENTATION_REVISION_CONFLICT` with HTTP 409 and `current_presentation_revision`. Existing graph conflict, transition, request-validation, IR-validation and document-failure codes remain.

Request errors preserve operation index and structured path. IR primitive errors name their operation. Final-state graph validation and resolution use a null operation index. Presentation validation errors identify the presentation operation and exact group, member or frame path. No failure becomes a generic success with omitted fields.

## Required non-vacuous guards

Temporary mutations must prove these tests fail for the intended cause before restoration:

1. permit non-empty executable `groups` or hash presentation groups into graph JSON: the content-address exclusion guard fails;
2. skip `apply_batch()` final validation: an incomplete or incompatible final graph reaches the version seam and the guard fails;
3. commit the graph version before presentation reconciliation: the transaction rollback guard finds a new immutable version or advanced head;
4. stop pruning removed-node positions or memberships: the orphan guard fails;
5. omit the presentation inverse during undo: the restored graph has the wrong position or membership and the guard fails;
6. hash a projection while accepting multiple immutable JSON forms: the executable-identity alias guard fails;
7. mutate semantic JSON outside `app.ir.edit.apply_batch()`: the architecture guard fails.

Guards restore production code immediately and focused tests return green before the next change.

## Test and verification strategy

Backend test-first increments cover:

- explicit `group()` deprecation and rejection of non-empty executable groups;
- final-state semantic add/remove/connect/disconnect batches and exact inverses;
- component and socket descriptors;
- migration, model equivalence and downgrade/upgrade;
- closed presentation group operations and presentation conflicts;
- semantic publication plus position/group reconciliation in one transaction;
- unified receipts and semantic/presentation undo-redo;
- every rollback seam and immutable-version trigger;
- `/api` and `/api/v1` parity, ownership and archive behavior;
- content, cache, component and experiment identity exclusion.

Frontend increments cover typed contracts, structural and presentation command state, stale-response protection, exact feedback, accessible component/socket/group controls, dirty-layout blocking, server-authoritative replacement, unified undo/redo and lossless reload.

Use focused tests during implementation. At each backend or frontend deliverable run the WS-04 workstream regression. Because S3.2b changes migrations, shared persistence and safety boundaries, its completion checkpoint includes the entire backend and research suite, full frontend suite, TypeScript, production build, migration/database-safety regression and both deterministic smoke scripts. Nothing is deployed.

## Completion boundary

S3.2b is complete when a user can add or remove authored nodes, connect or disconnect server-described sockets, manage revisioned visual groups, receive exact refusals, reload losslessly and undo or redo with both semantic and presentation state restored. Only final valid semantic graphs become immutable versions. Presentation-only commands never change executable identity. Execution and research paths consume none of the new editor state.
