# S3.2a Editor Interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one server-authoritative editor document with display-name and authored-parameter editing, canonical undo/redo receipts, exact errors, and transactionally coherent sparse layout.

**Architecture:** The edit route accepts only three S3.2a operations and delegates each to an existing IR primitive. The persistence transaction builds the immutable version, fresh version-scoped layout, resolved view, canonical receipt, and Pydantic response before commit. The frontend holds local intent and receipt history but replaces canonical state only from the latest accepted editor document.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, SQLite, pytest, React 18, TypeScript 5.5, Vitest, Vite.

## Global Constraints

- Implement the final contract in `docs/superpowers/specs/2026-08-03-s3-2a-editor-interaction-design.md`.
- S3.2a accepts only `set_display_name`, `set_override`, and `clear_override`; S3.2b owns structural editing.
- No raw replacement, client publication version, executable code, deployment, or live-money behavior.
- The backend owns validation, resolution, derived state, versions, revisions, content address, and canonical inverses.
- Editor documents always pair authored graph, resolved view, and layout with one immutable graph version.
- Carried layout starts at revision 1 and never inherits the prior version's counter.
- Focused tests drive implementation. Run WS-04 and database regressions at slice completion, then full acceptance and deterministic smoke checks.

## File map

- `backend/app/api/ir_routes.py`: reusable graph-to-view mapper.
- `backend/app/api/ir_edit_routes.py`: closed operation models, canonical errors/receipts, editor GET and POST.
- `backend/app/main.py`: path-scoped request-validation normalization for editor edit routes.
- `backend/app/api/ir_layout_routes.py`: persisted-version layout lookup.
- `backend/app/editor/graph_artifacts.py`: head coherence, canonical inverse construction inputs, transaction and response factory.
- `backend/app/editor/layouts.py`: session-scoped layout snapshot and fresh-revision carry-forward.
- `backend/tests/test_ir_edit_routes.py`: endpoint contract, guards, receipts, rollback seams.
- `backend/tests/test_ir_layout_routes.py`: persisted versions and executable-identity separation.
- `backend/tests/test_graph_artifacts.py`: storage invariants and immutable triggers.
- `backend/tests/test_schema_migrations.py`: SQLite foreign-key migration/rollback coverage.
- `frontend/src/lib/api.ts` and `frontend/src/lib/irEditorApi.test.ts`: typed editor transport.
- `frontend/src/views/graphEditorState.ts` and test: request identity, local intent, receipts, undo/redo/reload.
- `frontend/src/views/GraphEditControls.tsx` and test: accessible S3.2a controls.
- `frontend/src/views/graphLayoutState.ts`, `GraphView.tsx`, and tests: coherent adoption and dirty layout rebasing.
- `docs/engineering/EXECUTION_PLAN.md`, WS-04 workstream document, and `docs/CONTINUE.md`: final evidence and next bounded checklist.

---

### Task 1: Pin the closed backend request and error contract

**Files:**
- Modify: `backend/app/api/ir_edit_routes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_ir_edit_routes.py`

**Interfaces:**
- Consumes: `ir_edit.rename`, `ir_edit.set_override`, `ir_edit.clear_override`.
- Produces: `SetDisplayNameEdit`, `SetOverrideEdit`, `ClearOverrideEdit`, `EditorErrorEnvelope`, `EditorErrorItem`, and structured JSON paths.

- [ ] **Step 1: Write failing closed-vocabulary tests**

Add parametrized tests that accept the three S3.2a operations and reject `rename`, add/remove node, connect/disconnect, group, raw `graph`, `version`, unknown operations, and extra fields with `REQUEST_VALIDATION_FAILED`. Pin batch sizes 0, 1, 32, and 33.

```python
assert _post(client, 0, {"operation": "set_display_name", "display_name": "Edited"}).status_code == 201
for operation in ("rename", "add_node", "remove_node", "connect", "disconnect", "group", "python"):
    response = _post(client, 0, {"operation": operation})
    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"
```

- [ ] **Step 2: Write failing exact-error and JSON-bound tests**

Pin `DRAFT_REVISION_CONFLICT`, `REQUEST_VALIDATION_FAILED`, and `IR_VALIDATION_FAILED` envelopes, including nullable fields and structured paths. Test unknown parameter, wrong type, unknown node, derived node, NaN, Infinity, depth 9, 257 composite entries, and a 4,097-character string.

```python
body = _post(client, 0, {
    "operation": "set_override", "instance_id": "n_ema",
    "parameter": "length", "value": "wrong",
}).json()
assert body["code"] == "IR_VALIDATION_FAILED"
assert body["errors"][0]["operation_index"] == 0
assert isinstance(body["errors"][0]["path"], list)
```

- [ ] **Step 3: Run tests red**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ir_edit_routes.py -q`

Expected: current eight-operation union and legacy error bodies fail the new assertions.

- [ ] **Step 4: Implement the request boundary**

Replace the route union with:

```python
EditRequest = Annotated[
    SetDisplayNameEdit | SetOverrideEdit | ClearOverrideEdit,
    Field(discriminator="operation"),
]

class GraphEditRequest(_ClosedModel):
    base_revision: int = Field(ge=0)
    edits: list[EditRequest] = Field(min_length=1, max_length=32)
```

Map `set_display_name` to `ir_edit.rename`. Add a recursive pre-primitive value checker with exact limits from the design. Reject non-finite floats before canonical JSON or hashing.

- [ ] **Step 5: Implement one error envelope**

```python
class EditorErrorItem(_ClosedModel):
    operation_index: int | None
    clause: str | None
    path: list[str | int]
    message: str

class EditorErrorEnvelope(_ClosedModel):
    code: str
    message: str
    current_revision: int | None = None
    errors: list[EditorErrorItem] = Field(default_factory=list)
```

Catch primitive failures per operation so the index is exact. Use null index for final whole-graph validation/resolution. Add a path parser for `$.nodes.n_ema.overrides.length` and bracket indexes. Normalize request-model failures for both route mirrors through a path-scoped `RequestValidationError` handler registered in `app.main`; delegate non-editor validation to FastAPI's default handler.

- [ ] **Step 6: Run focused contract tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ir_edit.py tests/test_ir_edit_routes.py tests/test_api_versioning.py -q`

Expected: all selected tests pass and the AST guard sees only the three permitted primitives.

---

### Task 2: Build coherent documents and canonical receipts inside the transaction

**Files:**
- Modify: `backend/app/api/ir_routes.py`
- Modify: `backend/app/api/ir_edit_routes.py`
- Modify: `backend/app/editor/graph_artifacts.py`
- Modify: `backend/app/editor/layouts.py`
- Modify: `backend/tests/test_graph_artifacts.py`
- Modify: `backend/tests/test_ir_edit_routes.py`

**Interfaces:**
- Consumes: the Task 1 operation union and existing graph validator/resolver.
- Produces: `EditorSnapshot`, `EditResult`, `CommandReceipt`, `EditorDocumentResponse`, `load_layout_in_session()`, `load_editor_snapshot()`, and generic `apply_and_publish(..., response_factory)`.

- [ ] **Step 1: Write failing GET coherence tests**

Pin `/api` and `/api/v1` parity, active ownership, unpublished and divergent-draft 409 codes, and the full response model.

```python
body = client.get(EDITOR_URL).json()
assert body["identifier"] == IDENTIFIER
assert body["display_name"] == GRAPH["display_name"]
assert body["draft_revision"] == 0
assert body["version"] == GRAPH["version"]
assert body["authored_graph"]["version"] == body["view"]["version"] == body["layout"]["graph_version"]
assert body["command_receipt"] is None
```

- [ ] **Step 2: Write failing receipt tests**

Pin normalized applied operations and backend inverses for display name, an existing override, a previously inherited override, clear override, and a mixed batch. Assert each result's revision, version, and content address equal the enclosing document.

```python
receipt = _post(client, 0, {"operation": "set_override", "instance_id": "n_ema", "parameter": "length", "value": 60}).json()["command_receipt"]
assert receipt["applied_operations"] == [{"operation": "set_override", "instance_id": "n_ema", "parameter": "length", "value": 60}]
assert receipt["inverse_operations"] == [{"operation": "set_override", "instance_id": "n_ema", "parameter": "length", "value": 50}]
```

- [ ] **Step 3: Write failing response-construction rollback test**

Inject a response factory that raises after version insertion and assert graph version, draft JSON, head pointer, published revision, draft revision, layout rows, and positions remain unchanged.

```python
with pytest.raises(RuntimeError, match="response failed"):
    store.apply_and_publish(
        CATALOGUE_PROJECT_ID, IDENTIFIER, base_revision=0,
        transform=lambda graph: ir_edit.rename(graph, "No commit"),
        response_factory=lambda publication, layout: (_ for _ in ()).throw(RuntimeError("response failed")),
    )
```

- [ ] **Step 4: Run tests red**

Run: `cd backend && .venv/bin/python -m pytest tests/test_graph_artifacts.py tests/test_ir_edit_routes.py -q`

Expected: missing editor route, receipt, response factory, and rollback behavior.

- [ ] **Step 5: Extract one graph-view mapper**

Move the existing complete field-by-field `IrGraphResponse` construction into:

```python
def graph_response(graph: Mapping[str, Any], library: Library) -> IrGraphResponse:
    violations = validate(graph, library.components)
    if violations:
        raise GraphViewRejected(violations)
    return _view_response(graph, graph_view(resolve(graph, library)))
```

Keep the fixed catalogue route's 404/500 compatibility behavior. Persistent routes call the same mapper.

- [ ] **Step 6: Add the session-scoped layout reader**

Implement `layouts.load_layout_in_session(session, identifier, version, valid_instance_ids)` with the same ordered filtering as `load_layout()` and no nested session. Make `load_layout()` delegate to it. A missing head returns revision 0 and no positions.

- [ ] **Step 7: Implement snapshot, receipt, and response factory**

`load_editor_snapshot()` opens one session, verifies active project, ownership, current version, and `published_revision == draft_revision`, then reads the immutable graph and layout in that session. Define `EditorDocumentResponse` with the exact design fields, including backend-derived `editable_nodes` for composite authored components that have no one-to-one resolved-view node.

Define the transform result before changing persistence:

```python
@dataclass(frozen=True)
class EditResult:
    graph: dict[str, Any]
    applied_operations: tuple[dict[str, Any], ...]
    inverse_operations: tuple[dict[str, Any], ...]
```

Change persistence to a generic result:

```python
T = TypeVar("T")

def apply_and_publish(
    project_id: str,
    identifier: str,
    *,
    base_revision: int,
    transform: Callable[[dict[str, Any]], EditResult],
    response_factory: Callable[[EditPublication, layouts.Layout], T],
) -> T:
```

`EditResult` holds the edited graph plus normalized applied and inverse operations built from the exact pre-edit graph. Invoke `response_factory` after flushes and pointer updates but before leaving `SessionLocal.begin()`. The API factory resolves the graph, builds Pydantic receipt/document models, and returns the validated response.

- [ ] **Step 8: Run focused coherent-document tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_graph_artifacts.py tests/test_ir_routes.py tests/test_ir_edit_routes.py -q`

Expected: coherent GET/POST, receipt, response-construction rollback, immutability, ownership, and archive tests pass.

---

### Task 3: Fresh-revision layout carry-forward and backend proof

**Files:**
- Modify: `backend/app/editor/layouts.py`
- Modify: `backend/app/editor/graph_artifacts.py`
- Modify: `backend/app/api/ir_layout_routes.py`
- Modify: `backend/tests/test_ir_edit_routes.py`
- Modify: `backend/tests/test_ir_layout_routes.py`
- Modify: `backend/tests/test_schema_migrations.py`

**Interfaces:**
- Consumes: the Task 2 transaction session and immutable graph version.
- Produces: `carry_layout_forward()` and persisted-version layout lookup.

- [ ] **Step 1: Write failing layout-coherence tests**

Cover source layout revisions 0 and greater than 1. Both identity-preserving results must have version-scoped revision 1; positions copy only from authored IDs.

```python
body = _post(client, 0, {"operation": "set_display_name", "display_name": "New"}).json()
assert body["layout"] == {
    "graph_identifier": IDENTIFIER,
    "graph_version": GRAPH["version"] + 1,
    "revision": 1,
    "positions": [],
}
```

Save a source layout through revisions 1 and 2, publish, and assert copied positions with revision 1. Use direct S3.1 persistence with a changed node set and assert revision 0 with no positions. Assert layout changes leave graph content address, cache IDs, experiment binding, and runtime output unchanged.

- [ ] **Step 2: Write both layout rollback seam tests**

Inject after graph-version insertion and after the new layout head/positions are flushed. Assert no target version, layout head, or position survives and all artefact fields retain their prior values.

- [ ] **Step 3: Verify tests fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ir_layout_routes.py tests/test_ir_edit_routes.py -k "layout or rollback" -q`

Expected: current route rejects edited versions and no carry-forward occurs.

- [ ] **Step 4: Implement session-scoped layout functions**

```python
def carry_layout_forward(
    session: Session,
    graph_identifier: str,
    from_version: int,
    to_version: int,
    valid_instance_ids: frozenset[str],
) -> Layout:
    target = IrGraphLayout(
        graph_identifier=graph_identifier,
        graph_version=to_version,
        revision=1,
        updated_at=dt.datetime.now(dt.UTC).replace(tzinfo=None),
    )
    session.add(target)
    rows = session.scalars(select(IrGraphLayoutPosition).where(
        IrGraphLayoutPosition.graph_identifier == graph_identifier,
        IrGraphLayoutPosition.graph_version == from_version,
    ).order_by(IrGraphLayoutPosition.instance_id))
    session.add_all([IrGraphLayoutPosition(
        graph_identifier=graph_identifier,
        graph_version=to_version,
        instance_id=row.instance_id,
        x=row.x,
        y=row.y,
    ) for row in rows if row.instance_id in valid_instance_ids])
    session.flush()
    _after_layout_prepare(session, target)
    return load_layout_in_session(
        session, graph_identifier, to_version, valid_instance_ids
    )
```

Define `_after_layout_prepare(session, layout)` as a no-op failure-injection seam. Never open or commit a nested session. A missing source produces revision 1 with no children.

- [ ] **Step 5: Resolve routes from persisted versions**

Add `load_published_graph(identifier, version)` backed by globally unique `GraphArtifact.identifier` and the composite `GraphVersion` key. Replace the Python catalogue lookup in `ir_layout_routes.py`; retain existing 404 and authored-ID validation.

- [ ] **Step 6: Run focused and database-safety tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest \
  tests/test_graph_artifacts.py tests/test_ir_edit_routes.py tests/test_ir_layout_routes.py \
  tests/test_migration.py tests/test_schema_migrations.py tests/test_db_session_hygiene.py -q
```

Expected: all selected tests pass with SQLite foreign keys enabled, including upgrade/downgrade and immutable UPDATE/DELETE refusal.

- [ ] **Step 7: Run non-vacuous backend guards**

Temporarily bypass revision comparison, accept a raw graph field, add layout to graph hashing, and move response construction after commit. Run each named test to see red, then restore the mutation:

```bash
cd backend && .venv/bin/python -m pytest tests/test_ir_edit_routes.py -k "stale or raw_replacement or response_construction" -q
cd backend && .venv/bin/python -m pytest tests/test_ir_layout_routes.py -k "identity" -q
```

- [ ] **Step 8: Commit and push the backend slice**

```bash
git add backend/app/api/ir_routes.py backend/app/api/ir_edit_routes.py backend/app/api/ir_layout_routes.py backend/app/editor/graph_artifacts.py backend/app/editor/layouts.py backend/app/main.py backend/tests/test_graph_artifacts.py backend/tests/test_ir_edit_routes.py backend/tests/test_ir_layout_routes.py backend/tests/test_schema_migrations.py
git diff --cached --check
git commit -m "feat(editor): publish coherent editor documents"
git push origin feat/exec-completeness
```

---

### Task 4: Typed editor transport

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/irEditorApi.test.ts`

**Interfaces:**
- Consumes: the final Task 3 GET, POST, receipt, and error schemas.
- Produces: `IrEditorDocument`, `IrEditorOperation`, `IrCommandReceipt`, `EditorApiError`, `getIrEditorDocument()`, and `postIrEditorOperations()`.

- [ ] **Step 1: Write failing success and taxonomy tests**

Mock fetch and pin URL encoding, authorization, full request body, coherent success, each 409 code, both 422 codes, non-JSON 500, and rejected network requests.

```typescript
await postIrEditorOperations('project.catalogue', 'strategy.example', 3, [
  { operation: 'set_display_name', display_name: 'Renamed' },
])
expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
  base_revision: 3,
  edits: [{ operation: 'set_display_name', display_name: 'Renamed' }],
})
```

- [ ] **Step 2: Verify transport tests fail**

Run: `cd frontend && npm test -- --run src/lib/irEditorApi.test.ts`

Expected: the new exports do not exist.

- [ ] **Step 3: Implement exact types and transport**

Define authored node, editable-node parameter descriptors, authored graph, coherent document, receipt, error item, envelope, and this closed operation union:

```typescript
export type IrEditorOperation =
  | { readonly operation: 'set_display_name'; readonly display_name: string }
  | { readonly operation: 'set_override'; readonly instance_id: string; readonly parameter: string; readonly value: unknown }
  | { readonly operation: 'clear_override'; readonly instance_id: string; readonly parameter: string }
```

`EditorApiError` exposes category `conflict`, `validation`, `non-json-server`, or `network` and retains the parsed envelope when one exists. Encode project and identifier path segments. Never send graph version or authored graph.

- [ ] **Step 4: Run transport regression and typecheck**

Run: `cd frontend && npm test -- --run src/lib/irEditorApi.test.ts src/lib/irGraphApi.test.ts src/lib/irLayoutApi.test.ts && npm run typecheck`

Expected: selected tests and typecheck pass.

---

### Task 5: Request-safe local intent and canonical receipt history

**Files:**
- Create: `frontend/src/views/graphEditorState.ts`
- Create: `frontend/src/views/graphEditorState.test.ts`
- Modify: `frontend/src/views/graphLayoutState.ts`
- Modify: `frontend/src/views/graphLayoutState.test.ts`

**Interfaces:**
- Consumes: Task 4 transport models.
- Produces: `GraphEditorState`, command drafts, request identity, publish success/failure, undo/redo/reload, and coherent layout adoption.

- [ ] **Step 1: Write failing phase and stale-response tests**

Pin all eight phases and require matching request identity before a response can replace accepted state. Resolve request 1 after request 2 and assert request 1 is ignored.

```typescript
const first = startPublish(ready, displayNameDraft('First'))
const second = startPublish(first.state, displayNameDraft('Second'))
const acceptedSecond = acceptPublication(second.state, second.requestId, SECOND_DOCUMENT)
expect(acceptPublication(acceptedSecond, first.requestId, FIRST_DOCUMENT)).toBe(acceptedSecond)
```

- [ ] **Step 2: Write failing intent, history, and reload tests**

Validation, conflict, and transport failures retain the draft and receipt stacks. Conflict blocks another publish. Successful ordinary edit pushes the server receipt and clears redo. Undo sends the top receipt's inverse against the current accepted revision. Redo sends its applied operations. Reload success discards draft/history and invalidates older request IDs.

- [ ] **Step 3: Write failing layout-adoption tests**

For clean state, adopt the response layout. For dirty state, retain local positions but replace identifier, graph version, and base revision with response layout values and remain dirty. Assert no transition synthesizes content address or resolved view from layout.

- [ ] **Step 4: Verify state tests fail**

Run: `cd frontend && npm test -- --run src/views/graphEditorState.test.ts src/views/graphLayoutState.test.ts`

Expected: the state module and coherent layout adoption do not exist.

- [ ] **Step 5: Implement immutable state transitions**

```typescript
export type EditorPhase =
  | 'loading' | 'ready-clean' | 'ready-dirty' | 'saving'
  | 'conflicted' | 'validation-error' | 'transport-error' | 'reloading'

export interface GraphEditorState {
  readonly phase: EditorPhase
  readonly accepted: IrEditorDocument | null
  readonly draft: EditorCommandDraft | null
  readonly undo: readonly IrCommandReceipt[]
  readonly redo: readonly IrCommandReceipt[]
  readonly nextRequestId: number
  readonly pendingRequestId: number | null
  readonly failure: EditorApiError | null
}
```

All transition functions return new objects. Publication functions receive a persistence callback for focused tests. Build undo/redo requests only from server receipts. Do not generate inverse operations in TypeScript.

- [ ] **Step 6: Run state tests and wrong-inverse guard**

Run: `cd frontend && npm test -- --run src/views/graphEditorState.test.ts src/views/graphLayoutState.test.ts && npm run typecheck`

Temporarily change the undo selector to use applied operations and prove the undo test fails, then restore it.

---

### Task 6: Accessible controls and coherent screen integration

**Files:**
- Create: `frontend/src/views/GraphEditControls.tsx`
- Create: `frontend/src/views/GraphEditControls.test.ts`
- Modify: `frontend/src/views/GraphView.tsx`
- Modify: `frontend/src/views/GraphView.test.ts`

**Interfaces:**
- Consumes: Tasks 4 and 5 transport/state functions and existing layout movement/save behavior.
- Produces: accessible display-name and parameter controls wired to the project editor document.

- [ ] **Step 1: Write failing semantic rendering tests**

Use static rendering to pin persistent labels, inherited/default and overridden indicators, JSON input names, set/clear buttons, field-associated errors, native disabled state, alerts/status, reload, undo/redo, and absence of controls on derived nodes.

```typescript
expect(html).toContain('<label for="graph-display-name"')
expect(html).toContain('Inherited/default')
expect(html).toContain('Explicit override')
expect(html).toContain('aria-label="Set n_ema length override"')
expect(html).toContain('aria-label="Clear n_ema length override"')
expect(html).not.toContain('Set n_atr/n_smooth length override')
```

Pin keyboard-operable native buttons and `aria-describedby` connections from validation messages to affected fields.

- [ ] **Step 2: Write failing integration tests**

Assert initial load calls only `getIrEditorDocument()` and does not call fixed `getIrGraph()`. Pin display-name save, parameter set/clear, success adoption, failure retention, undo/redo requests, redo clearing, conflict blocking, explicit reload, stale response protection, and dirty layout preservation.

- [ ] **Step 3: Verify component tests fail**

Run: `cd frontend && npm test -- --run src/views/GraphEditControls.test.ts src/views/GraphView.test.ts`

Expected: controls do not exist and GraphView still loads the fixed graph and a separate initial layout.

- [ ] **Step 4: Implement focused controls**

```typescript
export function GraphEditControls({
  state, onDraft, onPublish, onUndo, onRedo, onReload,
}: {
  state: GraphEditorState
  onDraft: (draft: EditorCommandDraft) => void
  onPublish: () => void
  onUndo: () => void
  onRedo: () => void
  onReload: () => void
})
```

Render controls only from the server's `editable_nodes` descriptors. Use each descriptor's bound value, default, kind, and explicit-override flag; do not infer component interfaces from resolved descendants. Parse override inputs as JSON into local command intent; invalid JSON becomes field validation without a request. Do not render structural controls.

- [ ] **Step 5: Integrate the coherent document**

Set `PROJECT_ID = 'project.repository_catalogue'`. Initial load uses only `getIrEditorDocument(PROJECT_ID, GRAPH_IDENTIFIER)`. Render `accepted.view` and `accepted.layout`. Publishing uses `accepted.draft_revision`; success adopts the complete response only through the request-ID guard. Explicit reload replaces the whole document and clears local intent/history. Existing layout PUT remains available for layout-only saves against the accepted document's layout revision.

- [ ] **Step 6: Run focused frontend tests**

Run:

```bash
cd frontend && npm test -- --run \
  src/lib/irEditorApi.test.ts src/views/graphEditorState.test.ts \
  src/views/graphLayoutState.test.ts src/views/GraphEditControls.test.ts \
  src/views/GraphView.test.ts && npm run typecheck
```

Expected: all selected tests and typecheck pass.

- [ ] **Step 7: Prove stale-response guard non-vacuous**

Temporarily remove the request-ID comparison, run the stale-response test and observe failure, then restore it and rerun green.

- [ ] **Step 8: Commit and push frontend slice**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/irEditorApi.test.ts frontend/src/views/graphEditorState.ts frontend/src/views/graphEditorState.test.ts frontend/src/views/graphLayoutState.ts frontend/src/views/graphLayoutState.test.ts frontend/src/views/GraphEditControls.tsx frontend/src/views/GraphEditControls.test.ts frontend/src/views/GraphView.tsx frontend/src/views/GraphView.test.ts
git diff --cached --check
git commit -m "feat(editor): add persistent name and override editing"
git push origin feat/exec-completeness
```

---

### Task 7: Regression, acceptance, documentation, and continuation

**Files:**
- Modify: `docs/engineering/EXECUTION_PLAN.md`
- Modify: `docs/engineering/workstreams/WS-04-editor.md`
- Modify: `docs/CONTINUE.md`
- Modify architecture documentation only if a durable invariant is absent there.

**Interfaces:**
- Consumes: verified backend and frontend commits.
- Produces: final evidence, remote confirmation, CI inspection, and bounded S3.2b checklist.

- [ ] **Step 1: Run WS-04 backend regression**

```bash
cd backend && .venv/bin/python -m pytest \
  tests/test_graph_artifacts.py tests/test_product_object_routes.py \
  tests/test_ir_authoring.py tests/test_ir_conformance.py tests/test_ir_contract_c13.py \
  tests/test_ir_edit.py tests/test_ir_edit_routes.py tests/test_ir_layout_routes.py \
  tests/test_ir_resolution.py tests/test_ir_routes.py tests/test_ir_runtime.py \
  tests/test_ir_strategy_parity.py tests/test_ir_view.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run migration and database-safety regression**

Run: `cd backend && .venv/bin/python -m pytest tests/test_migration.py tests/test_schema_migrations.py tests/test_migrate_schema_frozen.py tests/test_db_session_hygiene.py tests/test_sqlite_busy_timeout.py -q`

Expected: all selected tests pass with FK, rollback, and immutable triggers intact.

- [ ] **Step 3: Run complete frontend acceptance**

Run: `cd frontend && npm test -- --run && npm run typecheck && npm run build`

Expected: complete test suite, typecheck, and production build pass. Record an unchanged bundle-size warning without treating it as an S3.2a failure.

- [ ] **Step 4: Run complete backend/research acceptance**

Run: `cd backend && .venv/bin/python -m pytest tests research_tests --tb=short`

Expected: complete suite passes. Do not propagate minor count changes to unrelated docs.

- [ ] **Step 5: Run deterministic smoke checks**

Use the existing repository commands recorded in `docs/engineering/EXECUTION_PLAN.md` for deterministic ledger and backtest smoke. Require `LEDGER OK` and `SWEEP OK`; do not deploy.

- [ ] **Step 6: Update final documentation once**

Record the final contract and evidence in WS-04, mark S3.2a complete in the execution plan, and update `CONTINUE.md`. Make S3.2b active with exactly this bounded checklist:

```markdown
1. [ ] Add typed structural batches for add/remove node, connect/disconnect, and group.
2. [ ] Add accessible component selection, node creation/removal, and group membership controls.
3. [ ] Add accessible source/target socket selection and connect/disconnect controls.
4. [ ] Extend canonical inverse receipts and define changed-node sparse-layout reconciliation.
5. [ ] Prove exact failure retention, run regressions, document, commit, and push.
```

- [ ] **Step 7: Commit integration documentation**

```bash
git add docs/engineering/EXECUTION_PLAN.md docs/CONTINUE.md
git add docs/engineering/workstreams/WS-04-editor.md
git diff --cached --check
git diff --cached --stat
git commit -m "docs(editor): close S3.2a interaction slice"
```

- [ ] **Step 8: Push, verify, and inspect CI**

```bash
git push origin feat/exec-completeness
git fetch origin feat/exec-completeness
git rev-parse HEAD
git rev-parse origin/feat/exec-completeness
git rev-list --left-right --count origin/feat/exec-completeness...HEAD
gh run list --branch feat/exec-completeness --commit "$(git rev-parse HEAD)" --limit 1
```

Require equal hashes and `0 0`. Watch the first run for that head to completion. If it fails, use systematic debugging and the GitHub CI workflow before changing code.

- [ ] **Step 9: Continue into S3.2b**

Start checklist item 1 with a fresh design pass. Stop only for an explicit owner decision, deployment, live-money behavior, or another genuine owner-gated boundary.
