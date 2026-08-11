# Task 1A.1 fix round 1A report

## Scope completed

- Added the missing `Project` join to `list_project_version_events`. The query now
  constrains the joined project row by both project id and owner id, so a second
  project owned by the same organization cannot duplicate an event.
- Retained the duplicate-event regression. It creates two same-owner projects and
  asserts that the published graph event for the first project appears once.
- Removed the `partial(..., owner_id="owner")` fixture from
  `test_graph_artifacts.py`. Every graph repository call in that file now supplies
  `owner_id` explicitly.
- Converted the missed review state, review snapshot, research-review source, and
  experiment test callers to explicit graph ownership.
- Replaced graph-route `LEGACY_OWNER_ID` use with
  `Depends(get_principal)` and `owner_id_for(principal)` in product-object, editor,
  experiment, and layout routes. Request models remain closed and do not accept an
  owner id.
- Changed review aggregation to require `owner_id`. Review routes thread the
  trusted principal owner into graph-version aggregation. Snapshot capture passes
  that owner only to its default graph source loader; review persistence and
  research aggregation remain unchanged.
- Added route regressions that create a graph under a configured non-legacy owner.
  Before the route changes, editor, layout, and experiment reads each returned 404;
  after the changes, each route reaches the owned graph successfully.

## TDD evidence

The new principal regressions were run before their route implementation:

```text
tests/test_ir_edit_routes.py::test_editor_routes_load_a_graph_owned_by_the_resolved_principal: 404, expected 200
tests/test_ir_layout_routes.py::test_layout_routes_load_a_graph_owned_by_the_resolved_principal: 404, expected 200
tests/test_ir_experiment_routes.py::test_experiment_route_loads_a_graph_owned_by_the_resolved_principal: 404, expected 201
```

The review aggregation regression also failed before implementation with:

```text
TypeError: project_review_source() got an unexpected keyword argument 'owner_id'
```

All four regressions passed after the minimal owner-composition changes.

## Verification

Required test command:

```text
168 passed
```

The run emitted one existing FastAPI `TestClient` deprecation warning.

Additional targeted verification:

```text
tests/test_review_state.py tests/test_review_snapshot_store.py
tests/test_review_snapshot_routes.py tests/test_research_review_sources.py
27 passed
```

`python -m compileall -q app` completed successfully.

The AST caller inventory checked 85 calls to strict public graph repository APIs:

- 81 calls pass `owner_id` explicitly.
- 4 calls omit it deliberately inside `pytest.raises(TypeError)` assertions in
  `test_user_plane_tenant_isolation.py`; they prove the strict API rejects an
  unscoped caller.
- Unexpected omitted calls: 0.

`rg` found no `LEGACY_OWNER_ID` use in the changed graph route modules or review
aggregation. `git diff --check` completed without whitespace errors.

## Boundaries preserved

- No migration 0020 or schema migration test changed.
- The four protected broker/provider files were not edited or staged by this fix.
