# S3.2a Editor Interaction Design

Date: 2026-08-03
Status: Approved design
Workstream: Strategy OS S3.2a

## Context

S3.1 publishes validated batches of the eight closed IR edit primitives into an immutable graph lineage. The current frontend still reads the fixed Python catalogue graph, while persistent project graphs, graph versions, and draft revisions live behind separate product-object APIs. The existing layout API also accepts only the fixed catalogue version.

That split prevents the editor from adopting a newly published persistent version as one coherent state. A second fetch would create a race between authored graph data, resolved view data, draft revision, graph version, and layout. Patching the resolved view in the browser would duplicate backend validation and resolution rules and could not safely recompute derived nodes, layers, warmup, or cache identity.

S3.2a therefore adds a server-owned editor document and limits interactive editing to graph rename and parameter overrides. Structural node, edge, and group editing remains S3.2b.

## Product boundary

S3.2a delivers:

- a persisted editor document containing the authored graph and its resolved view;
- accessible graph-name and authored-node parameter-override controls;
- exact validation and conflict feedback;
- deterministic command-based undo and redo through new immutable versions;
- sparse layout continuity across identity-preserving edits;
- explicit reload behavior after conflicts or external lineage changes.

S3.2a does not add:

- structural node, edge, or group controls;
- raw graph replacement;
- client-selected graph versions for publication;
- client-side validation or resolution as an authority;
- execution, code evaluation, Python input, or live-money behavior;
- layout coordinates in graph identity or content addressing.

## Rejected alternatives

### Separate authored and resolved fetches

Fetching a persistent authored graph and a catalogue-derived view independently can combine different revisions and versions. It also needs extra loading and partial-failure states. The editor document keeps the state atomic.

### Optimistic browser-side view patching

Updating the current resolved view from edit intent would reproduce resolver semantics in TypeScript. It cannot reliably update derived topology, parameter binding, warmup, layers, or cache identity. The backend remains the only authority for the resolved view.

### Snapshot-only undo and redo

Replacing a draft with an earlier raw snapshot would bypass the closed edit vocabulary and weaken auditability. Undo and redo instead send inverse and forward edit batches through the same validation and publication path as ordinary edits.

## Backend design

### Coherent editor document

Add `GET /api/ir/projects/{project_id}/graphs/{identifier}/editor` for a persistent graph draft. The existing API-version mirroring also exposes the route under `/api/v1`. Its response contains:

- project identifier;
- graph identifier;
- current draft revision;
- current immutable version and content address;
- the persisted authored graph;
- the backend-resolved graph view used by the existing viewer.

The existing `POST /api/ir/projects/{project_id}/graphs/{identifier}/edits` endpoint returns the same coherent document after a successful publication. The frontend can therefore adopt one response without a follow-up read. The existing fixed-catalogue view route remains available as a compatibility path.

The persisted view builder reuses the existing IR graph validation, component-library resolution, and graph-view response mapping. It does not add a second response model or resolver implementation with different semantics.

### Edit and publication transaction

Every mutation supplies the server-issued draft revision. The backend maps each discriminated edit item to exactly one existing primitive, validates and resolves the final graph, inserts a new immutable graph version, advances the draft revision and current pointer, and constructs the returned editor document.

These writes remain one database transaction. A failure after version insertion must leave the version table, draft content, draft revision, current pointer, and layout lineage unchanged. Existing immutable-version update and delete protections remain in force.

The request continues to accept bounded batches of one to 32 edits. S3.2a uses rename, set-override, and clear-override operations. No route accepts an entire replacement graph.

### Persisted layout lookup and carry-forward

Layout reads and writes resolve persistent graph versions instead of requiring the fixed catalogue version. They validate authored node identifiers against the selected persisted graph version and keep the existing optimistic layout revision contract.

After a successful publication, the repository compares the old and new authored node-identifier sets. If the sets are identical, it copies the prior version's sparse positions into a layout for the new version inside the publication transaction. S3.2a rename and override edits meet this condition. If node identity changes, the repository does not infer structural reconciliation; S3.2b will define that policy.

The copied layout starts a new version-scoped layout revision. Graph hashing and content addressing continue to exclude layout coordinates.

## Frontend design

### Typed transport

Add typed transport for the editor document and edit-batch response. The transport distinguishes:

- successful coherent document responses;
- HTTP 409 revision conflicts;
- HTTP 422 validation failures with exact clause and path data;
- non-JSON server failures;
- network failures.

The transport sends the complete edit batch and the last server-issued draft revision. It never sends a graph version as publication authority.

### Editor state

The graph screen owns an editor state with:

- the last accepted editor document;
- idle, submitting, conflict, validation-error, and transport-error phases;
- a user-facing message with clause and path where available;
- an undo stack and a redo stack.

Existing sparse layout editing remains a separate state machine. A graph-edit failure does not discard the current graph, layout, or command history.

After a successful identity-preserving graph edit, the frontend rekeys its current sparse positions to the returned graph version. Dirty positions remain dirty and can be saved against the new version. Clean positions remain clean because the server copied the same persisted positions to the new version in the publication transaction. An explicit reload reads the new version-scoped layout from the layout endpoint. The frontend never inserts positions into graph content.

### Accessible rename and override controls

The graph-name form has an explicit label, input, and submit button. Each authored node exposes override controls for parameters known from the resolved view. Derived nodes do not expose edit controls.

Override input uses JSON syntax so strings, numbers, booleans, null, arrays, and objects retain their types. Invalid JSON is rejected locally without a request; backend validation remains authoritative for valid JSON values. Clear-override is a distinct accessible action.

Submitting controls and history controls use native disabled semantics while a request is active. Validation and conflict messages use an alert region and include the exact backend clause and path when present.

### Command history

Each successful user command stores a forward edit batch and an inverse edit batch:

- rename inverts to the prior display name;
- set override inverts to the prior explicit value, or to clear when no explicit value existed;
- clear override inverts to set with the prior explicit value.

History changes only after backend success. Undo submits the inverse batch using the current server revision, then moves the command to the redo stack. Redo submits the forward batch and moves the command back to the undo stack. Each success creates a new immutable graph version; undo never deletes or rewinds lineage.

A 409, 422, or transport failure leaves both history stacks unchanged. An explicit reload adopts the latest server document and clears both stacks because commands derived from the earlier lineage may no longer be safe.

## Error and concurrency behavior

- A stale draft revision returns 409 with the authoritative current revision and no partial write.
- An invalid edit returns the existing F7, F9, or C5 clause and path data and no partial write.
- A network or unparseable response retains the last accepted document and permits retry or reload.
- Reload is explicit after conflict. It replaces the document, reloads the version-scoped layout, and clears command history.
- The UI does not silently overwrite a concurrent editor's publication.

## Verification

Focused backend tests cover:

- reading the seeded persistent editor document;
- coherent authored and resolved data for the current draft;
- edit responses returning the new coherent document;
- old immutable versions remaining readable;
- sparse layout carry-forward without graph-identity changes;
- transaction rollback after injected failure;
- exact conflict, validation clause, and path responses;
- refusal of raw replacement and client-selected publication versions.

Focused frontend tests cover:

- success, 409, 422, non-JSON, and network transport results;
- semantic rename and override controls;
- exclusion of edit controls from derived nodes;
- invalid JSON causing no request;
- forward and inverse batch construction;
- history movement only after success;
- graph, layout, and history retention on failure;
- explicit reload clearing unsafe history;
- dirty and clean layout rebasing after publication.

Guard tests must fail if the persisted editor path bypasses backend resolution, if the frontend omits the batch or draft revision, or if undo replaces graph snapshots instead of calling the closed edit API.

Implementation uses focused tests while code changes are in progress. At slice completion it runs the editor/IR workstream regression. Because this slice joins shared persistence, resolution, and layout behavior, it also runs the full backend and frontend acceptance suites before publication.

## Completion boundary

S3.2a is complete when a user can load a persistent graph draft, rename it, set and clear typed parameter overrides, undo and redo those commands through immutable publications, preserve sparse layout positions across those edits, and recover explicitly from exact validation or revision conflicts without losing the accepted local state. Structural editing begins only in S3.2b.
