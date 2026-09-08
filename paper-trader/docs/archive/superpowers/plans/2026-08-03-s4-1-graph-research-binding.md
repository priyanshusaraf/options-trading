# S4.1 Immutable Graph-Version Research Binding Implementation Plan

**Goal:** Start the existing research experiment flow from one project-owned immutable graph
version while persisting exact graph, resolution, data, cost and gate provenance.

**Architecture:** A closed FastAPI route loads a project-owned `GraphVersion` from the application
database, materializes bounded datasets through the server provider, derives resolution and F14
evidence, and calls the existing research orchestrator in `research.db`. The immutable
`ExperimentSpec.recipe_json` is extended; no new experiment or gate ledger is introduced.

**Boundary:** Research evaluation only. No deployment creation, runtime adoption, execution,
orders, Python input, raw graph replacement or presentation identity.

## Task 1: Pin the immutable recipe contract

**Files:**

- Modify: `backend/research_tests/test_orchestrator.py`
- Modify: `backend/research/orchestrator/run.py`

1. [x] Add a failing test proving every result-affecting dataset, cost and gate assumption is present
   in canonical `recipe_json` and changes `ExperimentSpec.id` when changed.
2. [x] Add explicit `slippage_bps` and `slippage_multiplier` inputs and pass them through both fixed and
   optimized validation paths.
3. [x] Record complete dataset identity, cost assumptions and gate inputs while preserving spec reuse
   for identical recipes.
4. [x] Run `pytest research_tests/test_orchestrator.py -q`.

## Task 2: Derive graph and F14 provenance

**Files:**

- Create: `backend/research/orchestrator/graph_experiment.py`
- Create: `backend/research_tests/test_graph_experiment.py`

1. [x] Add failing tests for exact graph id/version/content address, resolved component versions,
   node cache identities and per-dataset F14 digests.
2. [x] Add negative tests for mismatched content address and a graph that cannot map to the Strategy
   interface; prove no ExperimentSpec or Run is written.
3. [x] Implement a pure binding builder that resolves with the existing Component IR library, derives
   F14 records from exact candle series, and calls `run_experiment` with the resulting provenance.
4. [x] Prove presentation metadata cannot enter the spec or change its id.
5. [x] Run the focused graph-experiment tests.

## Task 3: Add the closed project-owned API

**Files:**

- Create: `backend/app/api/ir_experiment_routes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/editor/graph_artifacts.py`
- Create: `backend/tests/test_ir_experiment_routes.py`

1. [x] Add failing route tests for the unversioned and `/api/v1` paths and the exact success response.
2. [x] Add failing guard tests for archived project, wrong owner, unpublished artefact, unknown version,
   research-disabled state, raw graph/client identity fields and invalid bounded inputs.
3. [x] Add a read-only store function that returns an exact owned immutable version and distinguishes
   unpublished from unknown-version state.
4. [x] Implement the closed request/response models, provider materialization, isolated research
   session and call into the graph-experiment service.
5. [x] Prove the route loads the selected version once and does not follow a newer head published
   during the experiment.
6. [x] Run the focused route tests and API-versioning coverage.

## Task 4: Prove reload and negative guards

**Files:**

- Extend: `backend/tests/test_ir_experiment_routes.py`
- Extend: `backend/research_tests/test_graph_experiment.py`

1. [x] Dispose both database engines and reload the persisted spec/run.
2. [x] Assert exact graph, resolution, dataset, cost and gate evidence after reload.
3. [x] Publish a newer graph version and prove the earlier spec remains pinned to the selected version
   and content address.
4. [x] Run deliberate negative mutations proving: client graph input is rejected; graph hash mismatch
   fails before a run; omitted final graph resolution fails; costs or gates omitted from the recipe
   collapse spec identity; and a second scoring path is not called.

## Task 5: Regression, publication and continuation

1. [x] Run focused WS-03, WS-04 and WS-07 tests, including IR conformance, graph persistence,
   migrations, research orchestrator, graph binding and route/versioning tests.
2. [x] Because this slice changes shared research persistence provenance and the API boundary, run the
   full backend/research acceptance checkpoint. Run frontend typecheck/tests only if the frontend
   surface changes.
3. [x] Update `docs/engineering/EXECUTION_PLAN.md`, `docs/engineering/workstreams/WS-03-research-plane.md`
   and `docs/CONTINUE.md` once with stable evidence.
4. [x] Commit deliberately, push `feat/exec-completeness`, verify the remote head and inspect the exact
   GitHub Actions run.
5. [x] Generate the next bounded checklist from `EXECUTION_PLAN.md` and continue into it unless a
   genuine owner-gated blocker is reached.
