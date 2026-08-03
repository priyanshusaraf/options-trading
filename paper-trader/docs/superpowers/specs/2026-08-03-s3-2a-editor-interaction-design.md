# S3.2a Editor Interaction Design

Date: 2026-08-03
Status: Final accepted contract
Workstream: Strategy OS WS-04 / S3.2a

## Scope

S3.2a adds a persistent editor workflow for graph display names and authored-node parameter overrides. It does not add node, edge, or group editing. The backend remains the authority for validation, component resolution, derived topology, parameter binding, warmup, layers, cache identity, content addressing, immutable publication, and draft revision advancement.

The frontend holds local intent, command history, and presentation state. It does not construct an executable graph, patch a resolved view after publication, or infer server state from separate authored and resolved reads.

## State model

The existing product-object layer supports a newly created artefact with no published version. It also contains internal `save_draft()` support, although no raw draft-replacement HTTP route is exposed. Removing that storage capability would redesign the S2.2 product-object contract, so S3.2a does not remove it.

An artefact becomes editor-enabled after its first publication. For an editor-enabled artefact:

- `current_version` points to the immutable editable lineage head;
- `draft_revision` is the monotonic concurrency revision for that head;
- `published_revision` must equal `draft_revision`;
- every accepted S3.2a batch creates one immutable version and atomically advances all three fields;
- the S3.2a editor never creates an unpublished mutable executable snapshot.

`GET /editor` returns `409 EDITOR_NOT_PUBLISHED` when `current_version` is null and `409 EDITOR_HAS_UNPUBLISHED_DRAFT` when the stored draft revision differs from the published revision. This rejects an incoherent read instead of pairing a mutable draft with a different immutable version.

## Naming contract

The external operation is `set_display_name`. It maps one-to-one to the existing `app.ir.edit.rename()` primitive, whose documented behavior changes only `graph["display_name"]`.

The operation does not change:

- the stable graph artefact identifier;
- the IR graph identifier;
- project ownership;
- route identity;
- layout foreign keys or lineage selection;
- node instance identifiers;
- experiment lookup identity.

The display name is executable artefact content. Changing it therefore creates a new immutable graph version and content address. The operation name states the mutable field and avoids implying an identifier change.

## Closed edit vocabulary

The S3.2a edit endpoint accepts only:

- `set_display_name`;
- `set_override`;
- `clear_override`.

It accepts one to 32 operations. The HTTP model rejects S3.1 structural operations, raw graph fields, client versions, unknown operations, arbitrary code, and extra fields. Each accepted request item maps to exactly one existing IR primitive. Structural operations remain available only as internal S3.1 vocabulary until S3.2b defines their product controls and layout reconciliation.

Override values must be canonical JSON. Values may contain at most eight nested composite levels, 256 total list items and object entries, and strings of at most 4,096 characters. Object keys use the existing parameter-name limit. NaN and Infinity are rejected recursively. The real component/version library and existing IR validation and resolution path reject unknown parameter keys, invalid types, constraints, unknown nodes, and derived-node identifiers.

## Coherent editor document

Add:

`GET /api/ir/projects/{project_id}/graphs/{identifier}/editor`

The existing versioned-router mechanism mirrors it under `/api/v1`. The response contains:

- `project_id`;
- stable `identifier`;
- mutable `display_name`;
- `draft_revision`;
- current immutable `version`;
- executable `content_address`;
- `authored_graph` from that immutable version;
- `view` resolved from that exact authored graph;
- `layout` for that exact identifier and version;
- `command_receipt`, which is null on GET.

The response is the only canonical frontend read model. The existing fixed-catalogue graph route remains as a compatibility route. Persistent and catalogue views share one field-by-field graph-view mapper.

Layout in the response is presentation state, not executable state. It remains excluded from graph and component hashing, content address, cache identity, experiment binding, runtime inputs, and runtime outputs.

## Canonical command receipt

A successful POST returns the complete editor document plus a canonical receipt:

- normalized `applied_operations`;
- canonical `inverse_operations`;
- `base_revision`;
- resulting `draft_revision`;
- resulting graph `version`;
- resulting `content_address`.

The backend constructs inverses from the exact accepted pre-edit graph inside the publication transaction:

- `set_display_name` inverts to the prior display name;
- `set_override` inverts to the prior explicit value, or `clear_override` when none existed;
- `clear_override` inverts to `set_override` with the prior explicit value.

The backend does not accept an inverse supplied by the frontend. Undo posts the receipt's inverse batch against the exact resulting draft revision. Redo posts the prior receipt's applied batch against the current exact revision. Each successful undo or redo returns a new canonical receipt and immutable version.

A conflict blocks publication and the frontend never silently rebases. A new successful ordinary edit clears redo. Validation, server, and network failures retain local command intent and both stacks. Explicit reload is the only action that discards unresolved intent and invalidates history after an external lineage change.

## Closed error contract

Editor-operation errors use one envelope:

```json
{
  "code": "IR_VALIDATION_FAILED",
  "message": "Graph validation failed",
  "current_revision": null,
  "errors": [
    {
      "operation_index": 0,
      "clause": "F8",
      "path": ["nodes", "n_ema", "parameters", "span"],
      "message": "Expected an integer greater than zero"
    }
  ]
}
```

The accepted codes are:

- `DRAFT_REVISION_CONFLICT` with HTTP 409 and `current_revision`;
- `EDITOR_NOT_PUBLISHED` with HTTP 409;
- `EDITOR_HAS_UNPUBLISHED_DRAFT` with HTTP 409;
- `REQUEST_VALIDATION_FAILED` with HTTP 422 for closed-envelope, batch, bounds, and JSON-value failures;
- `IR_VALIDATION_FAILED` with HTTP 422 for primitive, graph, parameter, and resolution failures;
- `EDITOR_DOCUMENT_FAILED` with HTTP 500 when a coherent response cannot be built.

Every envelope has `code`, `message`, nullable `current_revision`, and an `errors` list. Each error has nullable `operation_index`, nullable `clause`, a structured path of strings and integer indexes, and a message. Primitive failures record their operation index. Whole-result validation and resolution failures use a null operation index because no single operation is authoritative.

Request-model validation for both `/api` and `/api/v1` edit paths is normalized to this envelope. The frontend adds separate `non-json-server` and `network` transport categories because those failures cannot carry the server envelope.

## Layout snapshot and carry-forward

Every editor document includes an `IrLayoutResponse` whose identifier and version must equal the document identifier and version.

When old and new authored node-identifier sets are identical:

- the backend creates a layout head for the new graph version in the graph publication transaction;
- the new head always starts at layout revision 1;
- valid sparse positions from the old version are copied;
- the old version's layout concurrency counter is not inherited;
- a missing or empty old layout becomes an explicit new revision-1 head with no positions.

When node identity changes, no layout head or positions are inferred. A later read returns the existing explicit missing-layout representation: revision 0 with no positions. S3.2a rejects identity-changing operations, but the repository rule is pinned now because S3.1 can exercise the persistence function and S3.2b will rely on it.

Dirty frontend positions are local presentation intent. After an identity-preserving graph edit succeeds, the frontend keeps those positions, adopts the response's new layout revision and graph version, and remains layout-dirty. A clean frontend adopts the response layout directly.

## Transaction and response-construction boundary

One successful edit transaction:

1. verifies active project ownership and artefact ownership;
2. verifies the supplied draft revision and published-head coherence;
3. normalizes every request item and constructs canonical inverse operations from the pre-edit graph;
4. maps every item to one accepted IR primitive;
5. applies the full batch;
6. validates the authored graph with the real component library;
7. resolves it and constructs the graph view;
8. computes the executable content address;
9. inserts the immutable graph version;
10. prepares and flushes layout carry-forward when node identity is unchanged;
11. advances the head pointer, published revision, and draft revision;
12. constructs and validates the full editor response and command receipt;
13. commits only after response construction succeeds.

The persistence function accepts a typed response factory and invokes it while its SQLAlchemy transaction remains open. This keeps Pydantic response construction out of the storage module while proving it occurs before commit.

Failure-injection seams exist after graph-version insertion, after layout preparation, and during response construction. Any failure leaves immutable versions, draft JSON, draft revision, published revision, head pointer, layout head, layout revision, and positions unchanged. Tests run with SQLite foreign keys enabled. Existing immutable-version UPDATE and DELETE refusal triggers remain unchanged.

## Frontend state and stale-response protection

The frontend state records:

- phase: `loading`, `ready-clean`, `ready-dirty`, `saving`, `conflicted`, `validation-error`, `transport-error`, or `reloading`;
- last accepted editor document;
- local command draft;
- undo and redo receipt stacks;
- monotonically increasing request identity;
- conflict, validation, or transport details.

Only a successful response whose request identity matches the latest pending request can replace the accepted document. A stale response is ignored. Conflict blocks further publication until explicit reload. Validation and transport failures retain the command draft. Reload replaces the whole document, discards local command intent, clears both history stacks, and advances request identity so older responses cannot land afterward.

The frontend never patches the resolved graph view. It replaces canonical authored, resolved, version, revision, content-address, and persisted-layout state only from a complete accepted editor document.

## Accessible controls

The display-name field has a persistent label, inherited current value, field-associated validation, submit status, and pending disabled state. Each authored node lists resolved parameter values and clearly labels whether each value is inherited/default or explicitly overridden. Override values use JSON input to retain types. Set and clear actions are keyboard operable and have screen-reader labels.

Undo, redo, reload, conflicts, validation details, and save status use native buttons, disabled semantics, alert/status regions, and visible text. Derived nodes never receive override controls. Structural controls are absent.

## Verification

Backend focused tests pin coherent GET and POST documents, `/api` and `/api/v1` parity, same-version authored/view/layout state, display-name semantics, set/clear/mixed batches, batch bounds, closed operations, recursive JSON bounds, exact error envelopes, parameter validation, ownership, archive behavior, monotonic versioning, content addressing, carry-forward revision 1, explicit empty layout, identity-changing no-copy behavior, three rollback seams, response-construction rollback, SQLite foreign keys, and immutable-version triggers.

Frontend focused tests pin typed transport categories, stale-response rejection, local-intent retention, exact conflict and validation details, display name, typed set/clear controls, inherited versus overridden presentation, canonical receipts, undo, redo, redo clearing, reload invalidation, keyboard and screen-reader semantics, derived-node exclusion, dirty and clean layout adoption, and layout exclusion from executable identity.

Non-vacuous guards temporarily suppress draft-revision validation, add layout to content hashing, use the wrong prior override for an inverse, accept a stale response, accept raw replacement, and fail response construction. Each mutation must make its named test red before restoration.

During implementation, run focused editor, IR, persistence, and frontend tests. At completion run WS-04 regression, migration/database-safety regression, complete frontend tests, TypeScript checking, production build, complete backend and research acceptance, deterministic ledger smoke, and deterministic backtest smoke. Do not deploy.

## Completion boundary

S3.2a is complete when a user can load one coherent persistent editor document, set its display name, set and clear authored parameter overrides, retain unresolved intent across failures, detect and explicitly reload after conflicts, undo and redo through new immutable publications, retain sparse layout across identity-preserving versions, and prove presentation state never changes executable identity. S3.2b begins with structural editing and changed-node layout reconciliation.
