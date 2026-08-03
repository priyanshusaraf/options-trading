# S3.2b Structural Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add atomic authored-node and typed-edge editing plus revisioned presentation groups, with server-issued semantic and presentation inverses and no visual state in executable identity.

**Architecture:** `app.ir.edit.apply_batch()` is the only semantic mutation boundary and validates one final graph. The existing layout head becomes the revision head for positions and visual groups. One repository transaction publishes a semantic version and reconciles presentation state; presentation-only group commands advance only the presentation revision. The frontend replaces all accepted state from coherent server documents and replays server receipts for undo and redo.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite, pytest, React, TypeScript, Vite and Vitest.

## Global Constraints

- Raw graph replacement and client-selected immutable versions remain forbidden.
- Semantic operations are limited to `set_display_name`, `set_override`, `clear_override`, `add_node`, `remove_node`, `connect` and `disconnect`.
- Every semantic batch has 1-32 operations and persists only after final validation and resolution.
- Every semantic edit passes through `app.ir.edit.apply_batch()`.
- Non-empty executable `groups` are invalid; format-v1 canonical graph JSON retains only `groups: []`.
- Visual groups and positions share one presentation revision and never affect graph, component, cache, experiment or runtime identity.
- A structural semantic request carries graph and presentation base revisions but no graph version.
- Structural edits are unavailable while the frontend has an unsaved local position draft.
- Added nodes have no stored position unless the same request supplies a validated `set_position` delta.
- Removed nodes leave no position or group membership.
- Semantic and presentation changes, receipts and coherent response construction commit or roll back together.
- Use focused tests during implementation, WS-04 regression after each backend or frontend deliverable, and full acceptance only at the final shared-persistence checkpoint.
- Do not deploy or change execution, Python authoring, reusable subgraphs, marketplace behavior or live paths.

---

### Task 1: Retire executable visual groups at the IR boundary

**Files:**
- Modify: `docs/rfcs/0001-component-ir.md`
- Modify: `backend/app/ir/validate.py`
- Modify: `backend/app/ir/edit.py`
- Test: `backend/tests/test_ir_conformance.py`
- Test: `backend/tests/test_ir_edit.py`

**Interfaces:**
- Consumes: format-v1 `groups` legacy field and `EditRejected`.
- Produces: explicit F12 rejection for non-empty executable groups and deprecated `group()` behavior.

- [ ] **Step 1: Write the failing F12 tests**

Add tests equivalent to:

```python
def test_non_empty_groups_are_not_executable_graph_content(graph):
    graph["groups"] = [{
        "identifier": "g_visual", "display_name": "Visual", "members": ["n_ema"]
    }]
    violations = validate(graph, LIBRARY.components)
    assert [(v.clause, v.path) for v in violations] == [("F12", "$.groups")]


def test_legacy_group_primitive_refuses_executable_persistence(graph):
    with pytest.raises(EditRejected) as exc:
        group(graph, "g_visual", "Visual", ["n_ema"])
    assert exc.value.violations[0].clause == "F12"
    assert exc.value.violations[0].path == "$.groups"
    assert graph["groups"] == []
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_conformance.py tests/test_ir_edit.py -q
```

Expected: the non-empty graph validates and `group()` returns a graph, so both new assertions fail for the intended reason.

- [ ] **Step 3: Implement the explicit retirement**

In `validate.py`, reject any non-empty `groups` list once at `$.groups` with clause F12 and do not validate its old members as executable structure. In `edit.py`, retain the function name but raise:

```python
raise EditRejected(
    f"group({identifier!r})",
    [Violation(
        "F12", "$.groups",
        "visual groups are revisioned presentation state and cannot be executable graph content",
    )],
)
```

Update old group-positive tests to assert the refusal. Add an RFC erratum directly under F12 stating that format-v1 `groups` is a reserved empty compatibility field and visual-group records live beside layout state.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Prove presentation cannot alter executable identity**

Temporarily remove the non-empty-groups refusal and assert the new conformance test fails. Restore the refusal and rerun the focused tests green. This is guard proof 1.

- [ ] **Step 6: Commit**

```bash
git add docs/rfcs/0001-component-ir.md backend/app/ir/validate.py backend/app/ir/edit.py backend/tests/test_ir_conformance.py backend/tests/test_ir_edit.py
git commit -m "fix(ir): retire executable visual groups"
```

### Task 2: Add one final-state semantic batch primitive

**Files:**
- Modify: `backend/app/ir/edit.py`
- Create: `backend/tests/test_ir_edit_batch.py`
- Modify: `backend/tests/test_ir_edit_routes.py`

**Interfaces:**
- Consumes: existing pure node, override, edge and rename transformations plus `validate()`.
- Produces: `SocketRef`, seven frozen semantic operation dataclasses, `SemanticOperation`, `EditBatchResult`, and `apply_batch(graph, operations, components)`.

- [ ] **Step 1: Define tests for temporary incompleteness and exact inverses**

Create tests equivalent to:

```python
def test_add_then_connect_validates_only_the_final_graph(graph):
    result = apply_batch(graph, (
        AddNode("n_abs", "math.abs", 1, {}, None, ()),
        Connect(SocketRef("n_ema", "out"), SocketRef("n_abs", "in")),
        Connect(SocketRef("n_abs", "out"), SocketRef("n_long_exit", "reference")),
        Disconnect(SocketRef("n_ema", "out"), SocketRef("n_long_exit", "reference")),
    ), LIBRARY.components)
    assert validate(result.graph, LIBRARY.components) == []
    assert result.applied_operations[0].operation == "add_node"
    assert result.inverse_operations[-1] == RemoveNode("n_abs")


def test_remove_inverse_restores_exact_node_and_incident_edges(graph):
    result = apply_batch(graph, (RemoveNode("n_ema"),), LIBRARY.components)
    restored = apply_batch(result.graph, result.inverse_operations, LIBRARY.components)
    assert canonical_json(restored.graph) == canonical_json(graph)


def test_invalid_final_state_is_rejected_before_return(graph):
    with pytest.raises(EditRejected) as exc:
        apply_batch(graph, (Disconnect(
            SocketRef("n_ema", "out"), SocketRef("n_long_exit", "reference")
        ),), LIBRARY.components)
    assert exc.value.operation_index is None
```

- [ ] **Step 2: Run the new module and verify RED**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_edit_batch.py -q
```

Expected: import failure for missing batch types.

- [ ] **Step 3: Implement typed operations and private transformers**

Add frozen dataclasses with exact fields:

```python
@dataclass(frozen=True)
class SocketRef:
    instance_id: str
    socket: str

@dataclass(frozen=True)
class AddNode:
    operation: Literal["add_node"] = field(init=False, default="add_node")
    instance_id: str
    identifier: str
    version: int
    overrides: Mapping[str, Any]
    domain: Mapping[str, str] | None
    secret_params: tuple[str, ...]
```

Define corresponding `RemoveNode`, `Connect`, `Disconnect`, `SetDisplayName`, `SetOverride` and `ClearOverride`. Refactor existing helpers to call private `_add_node`, `_remove_node`, `_connect`, `_disconnect`, `_rename`, `_set_override` and `_clear_override` transformers before `_result()`.

Implement:

```python
@dataclass(frozen=True)
class EditBatchResult:
    graph: dict[str, Any]
    applied_operations: tuple[SemanticOperation, ...]
    inverse_operations: tuple[SemanticOperation, ...]

def apply_batch(
    graph: Mapping[str, Any],
    operations: Sequence[SemanticOperation],
    components: Mapping[tuple[str, int], Mapping[str, Any]],
) -> EditBatchResult:
    edited = _copy(graph)
    inverse: list[SemanticOperation] = []
    for index, operation in enumerate(operations):
        before = _copy(edited)
        try:
            edited = _apply_unchecked(edited, operation)
        except EditRejected as exc:
            raise EditRejected(exc.action, exc.violations, operation_index=index) from exc
        inverse[0:0] = _inverse_for(before, operation)
    violations = validate(edited, components)
    if violations:
        raise EditRejected("semantic_batch", violations, operation_index=None)
    return EditBatchResult(edited, tuple(operations), tuple(inverse))
```

Apply private transformations without intermediate `_result()` calls. Build each inverse from the exact graph immediately before that operation, prepend it to the inverse list, then call `validate(final, components)` once. `remove_node` inverse emits exact add-node state followed by every removed incident edge in deterministic canonical order.

- [ ] **Step 4: Run batch and legacy edit tests GREEN**

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_edit_batch.py tests/test_ir_edit.py tests/test_ir_edit_routes.py -q -k "batch or architecture or bypass"
```

- [ ] **Step 5: Run final-validation and bypass guard proofs**

Temporarily return before final `validate()`; the invalid-final-state test must fail because no rejection occurs. Restore it. Temporarily make the route architecture test accept direct `ir_edit.add_node`; it must fail its `apply_batch` source assertion. Restore and rerun green. These are guard proofs 2 and 7.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ir/edit.py backend/tests/test_ir_edit_batch.py backend/tests/test_ir_edit_routes.py
git commit -m "feat(ir): apply semantic edits as final-state batches"
```

### Task 3: Add presentation-group persistence and migration rollback

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/migrations/versions/20260803_0007_ir_visual_groups.py`
- Modify: `backend/app/editor/layouts.py`
- Modify: `backend/app/api/ir_layout_routes.py`
- Test: `backend/tests/test_schema_migrations.py`
- Create: `backend/tests/test_ir_presentation_repository.py`
- Test: `backend/tests/test_ir_layout_routes.py`

**Interfaces:**
- Consumes: `IrGraphLayout` revision head and sparse positions.
- Produces: `IrGraphLayoutGroup`, `IrGraphLayoutGroupMember`, `GroupFrame`, `VisualGroup`, and `Layout.groups`.

- [ ] **Step 1: Write failing migration and repository tests**

Add assertions equivalent to:

```python
def test_0007_round_trip_preserves_graphs_layouts_and_trades(alembic_db):
    upgrade("head")
    assert {"ir_graph_layout_groups", "ir_graph_layout_group_members"} <= table_names()
    downgrade("20260803_0006")
    assert "ir_graph_layout_groups" not in table_names()
    assert "ir_graph_layout_positions" in table_names()
    assert "trades" in table_names()
    upgrade("head")


def test_layout_loads_visual_groups_with_members(repository_graph):
    saved = save_presentation_groups(
        IDENTIFIER, VERSION, base_revision=0,
        groups=(VisualGroup(
            "g_signal", "Signal", GroupFrame(10, 20, 300, 180), False,
            ("n_ema", "n_impulse"),
        ),),
        valid_instance_ids=frozenset({"n_ema", "n_impulse"}),
    )
    assert saved.revision == 1
    assert saved.groups[0].members == ("n_ema", "n_impulse")
```

- [ ] **Step 2: Run focused migration/repository tests and verify RED**

```bash
cd backend
.venv/bin/python -m pytest tests/test_schema_migrations.py tests/test_ir_presentation_repository.py tests/test_ir_layout_routes.py -q
```

Expected: missing tables, models and group fields.

- [ ] **Step 3: Add closed relational models and migration**

Add `IrGraphLayoutGroup` with composite primary key `(graph_identifier, graph_version, identifier)`, `display_name`, finite frame columns and `collapsed`. Add `IrGraphLayoutGroupMember` with composite key including `instance_id` and a named cascading composite foreign key to the group. Migration upgrade creates group then member; downgrade drops member then group. Add matching indexes and constraints to model and migration.

- [ ] **Step 4: Extend the presentation dataclasses and load path**

In `layouts.py` add:

```python
@dataclass(frozen=True)
class GroupFrame:
    x: float
    y: float
    width: float
    height: float

@dataclass(frozen=True)
class VisualGroup:
    identifier: str
    display_name: str
    frame: GroupFrame
    collapsed: bool
    members: tuple[str, ...]
```

Add `groups: tuple[VisualGroup, ...] = ()` to `Layout`. Extend load functions and API responses with deterministic identifier/member ordering. Reject unknown membership in write paths; never filter it silently on coherent editor reads.

- [ ] **Step 5: Verify GREEN and model/migration equivalence**

Run the Step 2 command. Expected: all pass, including downgrade/upgrade.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/migrations/versions/20260803_0007_ir_visual_groups.py backend/app/editor/layouts.py backend/app/api/ir_layout_routes.py backend/tests/test_schema_migrations.py backend/tests/test_ir_presentation_repository.py backend/tests/test_ir_layout_routes.py
git commit -m "feat(editor): persist visual groups beside layouts"
```

### Task 4: Add closed presentation batches and exact deltas

**Files:**
- Modify: `backend/app/editor/layouts.py`
- Modify: `backend/app/api/ir_edit_routes.py`
- Test: `backend/tests/test_ir_edit_routes.py`
- Test: `backend/tests/test_ir_presentation_repository.py`

**Interfaces:**
- Consumes: current graph head, authored IDs and shared presentation revision.
- Produces: closed presentation operation models, `PresentationDelta`, `apply_presentation_batch_in_session()`, and POST `/presentation-edits`.

- [ ] **Step 1: Write failing group-command and conflict tests**

Add route tests equivalent to:

```python
def test_group_edits_advance_only_presentation_revision(client):
    before = _editor(client)
    response = client.post(_presentation_path(), json={
        "base_revision": before["draft_revision"],
        "base_presentation_revision": before["layout"]["revision"],
        "edits": [{
            "operation": "create_group", "identifier": "g_signal",
            "display_name": "Signal", "members": ["n_ema"],
            "frame": {"x": 10, "y": 20, "width": 300, "height": 180},
            "collapsed": False,
        }],
    })
    body = response.json()
    assert response.status_code == 201
    assert body["version"] == before["version"]
    assert body["draft_revision"] == before["draft_revision"]
    assert body["content_address"] == before["content_address"]
    assert body["layout"]["revision"] == before["layout"]["revision"] + 1


def test_group_member_must_be_authored_not_derived(client):
    response = _post_presentation(client, [{
        "operation": "add_group_member", "identifier": "g_signal",
        "instance_id": "n_atr/n_internal",
    }])
    assert response.status_code == 422
    assert response.json()["errors"][0]["path"][-1] == "instance_id"
```

Cover create, rename, remove, add/remove member, frame, collapse, duplicate IDs, finite positive frame, stale graph revision, stale presentation revision, `/api/v1`, archived ownership and closed extra fields.

- [ ] **Step 2: Run focused route/repository tests and verify RED**

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_edit_routes.py tests/test_ir_presentation_repository.py -q
```

- [ ] **Step 3: Implement closed request and delta models**

Define Pydantic discriminated models for `create_group`, `rename_group`, `remove_group`, `add_group_member`, `remove_group_member`, `set_group_frame`, `set_group_collapsed`, plus receipt reconciliation operations `set_position`, `clear_position` and `put_group`. Define:

```python
@dataclass(frozen=True)
class PresentationDelta:
    forward_operations: tuple[dict[str, Any], ...]
    inverse_operations: tuple[dict[str, Any], ...]
```

`apply_presentation_batch_in_session()` claims the current `IrGraphLayout.revision`, applies the batch, validates membership against exact authored IDs, flushes, and returns the full layout plus exact delta. Group-only operations preserve positions.

- [ ] **Step 4: Implement the presentation route**

Resolve the current version from graph ownership and graph revision; accept no version field. Build the coherent editor document before commit. Add `PRESENTATION_REVISION_CONFLICT` and nullable `current_presentation_revision` to the closed error envelope. Presentation-only receipts have empty semantic arrays and unchanged graph identity.

- [ ] **Step 5: Run focused tests GREEN**

Run the Step 2 command and the editor route versioning/import-closure tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/editor/layouts.py backend/app/api/ir_edit_routes.py backend/tests/test_ir_edit_routes.py backend/tests/test_ir_presentation_repository.py
git commit -m "feat(editor): add revisioned presentation group commands"
```

### Task 5: Publish semantic batches with atomic presentation reconciliation

**Files:**
- Modify: `backend/app/editor/graph_artifacts.py`
- Modify: `backend/app/editor/layouts.py`
- Modify: `backend/app/api/ir_edit_routes.py`
- Test: `backend/tests/test_ir_edit_routes.py`
- Test: `backend/tests/test_product_object_routes.py`
- Test: `backend/tests/test_ir_presentation_repository.py`

**Interfaces:**
- Consumes: `ir_edit.apply_batch()`, source presentation revision and optional new-node `set_position`.
- Produces: atomic graph publication, `carry_and_reconcile_presentation()`, and unified receipt fields.

- [ ] **Step 1: Write failing atomicity and reconciliation tests**

Add tests equivalent to:

```python
def test_remove_node_prunes_position_and_membership_in_same_publication(client):
    grouped = _create_group_and_position(client, "n_ema")
    response = _post_semantic(client, grouped, [{
        "operation": "remove_node", "instance_id": "n_ema"
    }])
    body = response.json()
    assert response.status_code == 201
    assert "n_ema" not in {p["instance_id"] for p in body["layout"]["positions"]}
    assert "n_ema" not in body["layout"]["groups"][0]["members"]
    delta = body["command_receipt"]["presentation_delta"]
    assert {op["operation"] for op in delta["inverse_operations"]} >= {
        "set_position", "add_group_member"
    }


def test_presentation_failure_rolls_back_inserted_graph_version(client, monkeypatch):
    before = _editor(client)
    monkeypatch.setattr(layouts, "_after_presentation_reconcile", _raise)
    response = _post_semantic(client, before, _valid_structural_batch())
    assert response.status_code == 500
    assert _editor(client) == before
    assert _version_count() == before["version"] - INITIAL_VERSION + 1
```

Also cover add without position, add with same-request position, group carry-forward, source-presentation CAS, failure after version insert, before reconcile, during reconcile, after flush and response construction.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_edit_routes.py tests/test_product_object_routes.py tests/test_ir_presentation_repository.py -q
```

- [ ] **Step 3: Extend the semantic request and receipt**

Semantic POST adds required `base_presentation_revision` and optional closed `presentation_edits`, restricted on ordinary publication to `set_position` for IDs introduced by the final semantic batch. Replace receipt fields with:

```python
semantic_forward_operations: list[SemanticEditRequest]
semantic_inverse_operations: list[SemanticEditRequest]
presentation_delta: PresentationDeltaResponse
base_revision: int
draft_revision: int
base_version: int
version: int
content_address: str
base_presentation_revision: int
presentation_revision: int
```

- [ ] **Step 4: Implement one repository transaction**

Change `apply_and_publish()` to claim both source revisions, call the semantic transform, insert the version, invoke `carry_and_reconcile_presentation()` inside the same session, advance the graph head and construct the response before commit. The presentation helper copies positions and groups, removes invalid authored IDs, applies validated new-node positions, records exact forward/inverse deltas and creates revision 1 on the new version.

- [ ] **Step 5: Run focused tests GREEN**

Run the Step 2 command plus `tests/test_ir_edit_batch.py`.

- [ ] **Step 6: Run transaction and orphan guard proofs**

Temporarily commit before reconciliation; the rollback test must find the inserted version or advanced head. Restore. Temporarily skip position/member pruning; the orphan test must fail. Restore and rerun. These are guard proofs 3 and 4.

- [ ] **Step 7: Commit**

```bash
git add backend/app/editor/graph_artifacts.py backend/app/editor/layouts.py backend/app/api/ir_edit_routes.py backend/tests/test_ir_edit_routes.py backend/tests/test_product_object_routes.py backend/tests/test_ir_presentation_repository.py
git commit -m "feat(editor): reconcile presentation in semantic publication"
```

### Task 6: Publish server-derived component and socket contracts

**Files:**
- Create: `backend/app/editor/descriptors.py`
- Modify: `backend/app/api/ir_edit_routes.py`
- Test: `backend/tests/test_ir_edit_routes.py`

**Interfaces:**
- Consumes: the exact `LIBRARY`, authored graph interface and component interfaces.
- Produces: component catalogue, graph-boundary sockets and authored-node socket descriptors in every editor document.

- [ ] **Step 1: Write failing coherent-descriptor tests**

Assert the editor GET returns deterministic component identifiers/versions, recursive parameters, exact input/output directions and wire types, default-source flags, graph input producers, graph output consumers, and only authored nodes. Assert a composite authored node exposes its declared component sockets rather than derived descendant sockets.

- [ ] **Step 2: Run the descriptor tests and verify RED**

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_edit_routes.py -q -k "descriptor or socket or component_catalogue"
```

- [ ] **Step 3: Implement one descriptor mapper**

Create closed dataclasses from recursive interface items. Export `component_catalogue(library: Library) -> tuple[ComponentDescriptor, ...]`, `graph_sockets(graph: Mapping[str, Any]) -> tuple[SocketDescriptor, ...]`, and `editable_nodes(graph: Mapping[str, Any], library: Library) -> tuple[EditableNode, ...]`.

Sort components by identifier/version and preserve declared interface order within each component. Reuse this mapper for parameters currently built inside `ir_edit_routes.py`.

- [ ] **Step 4: Run descriptor and route tests GREEN**

Run the Step 2 selection, then all `test_ir_edit_routes.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/editor/descriptors.py backend/app/api/ir_edit_routes.py backend/tests/test_ir_edit_routes.py
git commit -m "feat(editor): publish component and socket descriptors"
```

### Task 7: Prove unified semantic/presentation undo and redo

**Files:**
- Modify: `backend/app/api/ir_edit_routes.py`
- Modify: `backend/app/editor/layouts.py`
- Test: `backend/tests/test_ir_edit_routes.py`

**Interfaces:**
- Consumes: semantic inverse arrays and exact presentation delta operations from receipts.
- Produces: deterministic undo/redo through normal closed endpoints.

- [ ] **Step 1: Write failing round-trip receipt tests**

Create a graph with a positioned, grouped node. Remove it. Submit `semantic_inverse_operations` and `presentation_delta.inverse_operations` against the returned revisions. Assert the new coherent document has the original authored graph semantics, exact position and exact memberships. Redo with forward arrays and assert the removal returns. Add a presentation-only remove-group undo/redo test with empty semantic arrays.

- [ ] **Step 2: Run undo/redo tests and verify RED**

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_edit_routes.py -q -k "undo or redo or receipt"
```

- [ ] **Step 3: Accept only closed receipt delta operations**

Permit semantic undo requests to replay exact `set_position`, `clear_position`, `put_group`, `remove_group`, `add_group_member` and `remove_group_member` operations. Validate graph and presentation base revisions, membership and final document. Presentation-only undo uses `/presentation-edits`. Do not accept receipt-provided versions, content addresses or raw snapshots.

- [ ] **Step 4: Run focused tests GREEN**

Run the Step 2 selection and the complete editor route module.

- [ ] **Step 5: Prove incomplete undo goes red**

Temporarily discard presentation inverse operations during semantic undo. The round-trip must restore the graph but fail exact position/member assertions. Restore and rerun green. This is guard proof 5.

- [ ] **Step 6: Prove executable identity is one-to-one with immutable JSON**

Add a test that canonical stored graph JSON hashes to its declared content address, that non-empty groups are rejected rather than projected out, and that no two inserted versions with different canonical JSON claim one content address. Temporarily hash a projection that removes groups while permitting non-empty groups; the guard must fail. Restore. This is guard proof 6.

- [ ] **Step 7: Run the backend WS-04 regression and commit**

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_edit.py tests/test_ir_edit_batch.py tests/test_ir_view.py tests/test_ir_routes.py tests/test_ir_presentation_repository.py tests/test_ir_layout_routes.py tests/test_ir_edit_routes.py tests/test_product_object_routes.py -q
git add app/api/ir_edit_routes.py app/editor/layouts.py tests/test_ir_edit_routes.py
git commit -m "test(editor): prove semantic and presentation history"
```

### Task 8: Extend frontend transport and state for structural commands

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/irEditorApi.test.ts`
- Modify: `frontend/src/views/graphEditorState.ts`
- Modify: `frontend/src/views/graphEditorState.test.ts`
- Modify: `frontend/src/views/graphLayoutState.ts`
- Modify: `frontend/src/views/graphLayoutState.test.ts`

**Interfaces:**
- Consumes: coherent descriptors, structural operation union, presentation groups and unified receipts.
- Produces: typed semantic/presentation transports and server-authoritative command/history state.

- [ ] **Step 1: Write failing transport and state tests**

Add tests asserting semantic POST sends both accepted revisions and no graph version; presentation POST never changes graph identity; structural success replaces the entire document; remove-node success adopts server presentation instead of pruning locally; dirty layout blocks structural start; undo uses receipt semantic inverse plus presentation inverse; presentation-only undo uses the presentation endpoint; stale and failed responses retain accepted state and local intent.

- [ ] **Step 2: Run focused frontend tests and verify RED**

```bash
cd frontend
npm test -- --run src/lib/irEditorApi.test.ts src/views/graphEditorState.test.ts src/views/graphLayoutState.test.ts
```

- [ ] **Step 3: Add exact TypeScript contracts and transports**

Extend `IrEditorOperation`, descriptors, `IrGraphLayout`, `IrCommandReceipt` and error envelope. Add `postIrPresentationOperations()`. Semantic transport body is exactly:

```typescript
{
  base_revision: number
  base_presentation_revision: number
  edits: readonly IrEditorOperation[]
  presentation_edits: readonly IrPresentationDeltaOperation[]
}
```

It never sends `version`, authored graph, resolved view or content address.

- [ ] **Step 4: Extend state transitions**

Represent command kind (`semantic` or `presentation`) and retain the complete server receipt. `startPublish`, `startUndo` and `startRedo` select endpoint and exact forward/inverse arrays from that receipt. A structural start returns null while layout phase is dirty/saving/conflict/error. Matching success replaces the document and resets layout from the response for identity-changing operations.

- [ ] **Step 5: Run focused tests and typecheck GREEN**

```bash
cd frontend
npm test -- --run src/lib/irEditorApi.test.ts src/views/graphEditorState.test.ts src/views/graphLayoutState.test.ts
npm run typecheck
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/irEditorApi.test.ts frontend/src/views/graphEditorState.ts frontend/src/views/graphEditorState.test.ts frontend/src/views/graphLayoutState.ts frontend/src/views/graphLayoutState.test.ts
git commit -m "feat(editor): model structural and presentation commands"
```

### Task 9: Add accessible structural and visual-group controls

**Files:**
- Create: `frontend/src/views/GraphStructureControls.tsx`
- Create: `frontend/src/views/GraphStructureControls.test.ts`
- Create: `frontend/src/views/GraphGroupControls.tsx`
- Create: `frontend/src/views/GraphGroupControls.test.ts`
- Modify: `frontend/src/views/GraphEditControls.tsx`
- Modify: `frontend/src/views/GraphEditControls.test.ts`
- Modify: `frontend/src/views/GraphView.tsx`
- Modify: `frontend/src/views/GraphView.test.ts`

**Interfaces:**
- Consumes: accepted server component/socket/node/group descriptors and graph editor state callbacks.
- Produces: keyboard-operable add/remove/connect/disconnect/group UI with exact field-associated errors.

- [ ] **Step 1: Write failing static interaction-contract tests**

Assert persistent labels and native controls for component and version selection, instance ID, authored-node removal, source output, target input, exact edge disconnection, group create/rename/remove, authored membership, frame and collapse. Assert derived nodes never appear, incompatible client options are hidden only from server descriptors, structural controls disable on pending or dirty layout, and errors attach exact clause/path/message to the affected field.

- [ ] **Step 2: Run focused control tests and verify RED**

```bash
cd frontend
npm test -- --run src/views/GraphStructureControls.test.ts src/views/GraphGroupControls.test.ts src/views/GraphEditControls.test.ts src/views/GraphView.test.ts
```

- [ ] **Step 3: Implement structural controls**

Render component options from `component_catalogue`, graph boundaries from `graph_sockets`, authored nodes from `editable_nodes`, and disconnect choices from authored graph edges. Submit closed operations only. State explicitly that node removal also removes incident edges and reconciles presentation. Do not synthesize a view or socket validity.

- [ ] **Step 4: Implement group controls**

Render groups from accepted presentation state. Create with validated frame/collapse defaults, rename/remove by identifier, and add/remove authored members. Use the presentation transport and shared revision. Keep positions and group state server-issued after success.

- [ ] **Step 5: Wire GraphView and run focused tests GREEN**

Use one request identity across semantic, presentation and reload calls. Replace accepted state only from matching coherent responses. Run the Step 2 command and `npm run typecheck`.

- [ ] **Step 6: Run frontend WS-04 regression and commit**

```bash
cd frontend
npm test -- --run src/lib/irEditorApi.test.ts src/lib/irGraphApi.test.ts src/lib/irLayoutApi.test.ts src/views/graphEditorState.test.ts src/views/graphLayoutState.test.ts src/views/GraphEditControls.test.ts src/views/GraphStructureControls.test.ts src/views/GraphGroupControls.test.ts src/views/GraphView.test.ts
npm run typecheck
git add src/views/GraphStructureControls.tsx src/views/GraphStructureControls.test.ts src/views/GraphGroupControls.tsx src/views/GraphGroupControls.test.ts src/views/GraphEditControls.tsx src/views/GraphEditControls.test.ts src/views/GraphView.tsx src/views/GraphView.test.ts
git commit -m "feat(editor): add structural and visual-group controls"
```

### Task 10: Final guards, acceptance, coordination and publication

**Files:**
- Modify: `docs/engineering/EXECUTION_PLAN.md`
- Modify: `docs/engineering/workstreams/WS-04-editor.md`
- Modify: `docs/CONTINUE.md`
- Modify only if evidence changes: `docs/superpowers/specs/2026-08-03-s3-2b-structural-editor-design.md`

**Interfaces:**
- Consumes: all S3.2b commits and guard evidence.
- Produces: closure evidence, verified remote state and the next bounded checklist.

- [ ] **Step 1: Run all seven named guard proofs and restore production code**

Record the failing assertion for content-address contamination, missing final validation, out-of-transaction reconciliation, orphan retention, incomplete presentation undo, executable-identity aliasing and `app.ir.edit` bypass. Confirm `git diff --check` and search for every temporary mutation marker before continuing.

- [ ] **Step 2: Run backend focused and workstream regression**

```bash
cd backend
.venv/bin/python -m pytest tests/test_ir_conformance.py tests/test_ir_edit.py tests/test_ir_edit_batch.py tests/test_ir_view.py tests/test_ir_routes.py tests/test_ir_presentation_repository.py tests/test_ir_layout_routes.py tests/test_ir_edit_routes.py tests/test_product_object_routes.py -q
.venv/bin/python -m pytest tests/test_schema_migrations.py tests/test_migrate_schema_frozen.py tests/test_build_version.py -q
```

- [ ] **Step 3: Run frontend workstream regression and production build**

```bash
cd frontend
npm test -- --run src/lib/irEditorApi.test.ts src/lib/irGraphApi.test.ts src/lib/irLayoutApi.test.ts src/views/graphEditorState.test.ts src/views/graphLayoutState.test.ts src/views/GraphEditControls.test.ts src/views/GraphStructureControls.test.ts src/views/GraphGroupControls.test.ts src/views/GraphView.test.ts
npm run typecheck
npm run build
```

- [ ] **Step 4: Run the shared-persistence checkpoint**

```bash
cd backend
.venv/bin/python -m pytest tests research_tests --tb=short
.venv/bin/python scripts/dryrun.py 700
.venv/bin/python scripts/backtest_smoke.py

cd ../frontend
npm test -- --run
npm run typecheck
npm run build
```

- [ ] **Step 5: Update only the three coordination documents**

Mark S3.2b complete, record material guard and acceptance evidence, state that groups are presentation-only, preserve deployment/owner gates, and generate the next five-item bounded checklist from `EXECUTION_PLAN.md`. Do not propagate minor count changes elsewhere.

- [ ] **Step 6: Verify, commit deliberately and push**

```bash
git diff --check
git status --short
git add docs/engineering/EXECUTION_PLAN.md docs/engineering/workstreams/WS-04-editor.md docs/CONTINUE.md
git commit -m "docs(editor): close S3.2b structural slice"
git push origin feat/exec-completeness
git fetch origin feat/exec-completeness
git rev-list --left-right --count HEAD...origin/feat/exec-completeness
```

- [ ] **Step 7: Inspect the first Actions run and continue**

Find the run for exact HEAD, watch backend, frontend and deterministic-smoke to completion, fix any failure test-first, then begin the next unblocked slice. Stop only for a new contradictory owner-gated contract.
