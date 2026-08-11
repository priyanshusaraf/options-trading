# Task 1A.3 report: structural graph/layout identities

## Pre-production inventory

Recorded before any production edit. Starting commit is `228fba9`; the only dirty files are the
four protected broker/provider files listed in the programme ledger. The verified test
interpreter is `/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python`
(`Python 3.13.5`).

### Structural schema and ORM consumers

- `projects` in `app/db/models.py:1033` has global `project_id`, `owner_id`, and
  `uq_projects_owner_name`. It lacks the `(owner_id, project_id)` candidate key required by
  owner-consistent descendants.
- `graph_artifacts` in `app/db/models.py:1055` has global PK `identifier`, global
  `projects.project_id` FK, and `ix_graph_artifacts_project_id`. It must become PK
  `(owner_id, identifier)` and use `(owner_id, project_id) -> projects`.
- `graph_versions` in `app/db/models.py:1086` has global PK
  `(graph_identifier, version)`, FK `graph_identifier -> graph_artifacts.identifier`,
  `ix_graph_versions_content_address`, JSON/identity/visibility checks, and immutable update
  and delete triggers. It must become `(owner_id, graph_identifier, version)` with a composite
  artifact FK while preserving checks, index, and trigger SQL.
- Layout identity chain in `app/db/models.py:1153-1264`:
  `ir_graph_layouts`; `ir_graph_layout_positions`; `ir_graph_layout_groups`;
  `ir_graph_layout_group_members`; `ir_graph_layout_orphan_archive`; and
  `ir_graph_layout_position_orphan_archive`. Every PK lacks `owner_id`. The first four use
  graph/layout FKs; the two archives have no parent FK. Group constraints and all row values
  need preservation.
- MONEY-plane `ir_paper_deployments` (`app/db/models.py:1550`) and
  `ir_shadow_deployments` (`app/db/models.py:1702`) each have a global
  `(graph_identifier, graph_version) -> graph_versions` FK. Both already store `owner_id`,
  graph identifier, graph version, graph content address, project id, and their authority
  state. Revision 0021 must retain provenance values and remove only the graph FK. It must not
  add a cross-plane composite FK. `ir_shadow_divergences` (`:1488`) records only
  `graph_address`, so it has no graph identity FK to rebuild.

### Migration and DDL consumers

- `migrations/versions/20260812_0020_user_project_ownership.py` is the direct predecessor. It
  supplies restart helpers, the graph content index, and the immutable trigger manifest, but it
  only rebuilds `projects` and `graph_versions`.
- Historical DDL defining graph/layout identities is in revisions `0005`, `0006`, and `0007`.
  `0011` and `0013` define the shadow and paper graph foreign keys. `0010` defines divergence
  provenance by graph content address only. Revisions `0017` through `0020` own the relevant
  MONEY and USER roots.
- `tests/test_schema_migrations.py` contains the migration fixture, direct SQL identity
  assertions, historical rollback cases, trigger checks, and restart-shape tests. It has 1,742
  lines; new 0020-to-0021 coverage belongs here. `tests/test_user_plane_tenant_isolation.py`
  holds the owner repository contract and is the correct location for the valid same-identifier
  tenant RED.

### Repository and query consumers

- `app/editor/graph_artifacts.py` has all graph create/load/save/publish/list/catalogue paths.
  Current global composite loads are at `session.get(GraphArtifact, identifier)` (lines 295 and
  708) and `session.get(GraphVersion, (identifier, version))` (332, 563, 722); its joins use
  only identifier (353, 593, 610, 639, 669). Its updates predicate only identifier/project id
  (381 and 508). All need owner-bearing keys/predicates; catalogue seeding is the sole allowed
  `LEGACY_OWNER_ID` bootstrap boundary.
- `app/editor/layouts.py` has all layout head/position/group/member loads, writes, updates and
  deletes. Its owner gate currently joins graph tables by identifier alone (92-101), and every
  layout lookup/write key currently omits owner (116-173, 400-753). Each needs `owner_id` in the
  identity and first SQL owner predicate.
- `app/core/paper_authority.py` loads graph versions with `session.get(GraphVersion,
  (graph_identifier, graph_version))` in `_graph_version` (452) from stage, activate, active
  bindings, and adapter reconstruction. It must resolve by the MONEY row's retained `owner_id`
  without creating a foreign key or changing authority state semantics.
- `app/core/shadow_deployments.py` has the same global `_graph_version` lookup (362), reached
  from shadow stage/activate/list/adapter paths, and needs the same owner-bearing by-value
  resolution.
- Direct model/import consumers outside these repositories are
  `app/api/ir_experiment_routes.py`, `app/api/product_object_routes.py`,
  `app/core/execution_binding.py`, and `app/core/review_aggregation.py`. They require a
  post-change key audit but are not new ownership authorities.
- Route/composition callers of graph/layout repositories include
  `app/api/ir_edit_routes.py`, `ir_experiment_routes.py`, `ir_layout_routes.py`,
  `product_object_routes.py`, `research_review_routes.py`, and `routes.py`.

### Test and operational consumers

- Graph/layout/IR route and presentation consumers include
  `test_graph_artifacts.py`, `test_graph_version_comparison.py`, `test_ir_edit_routes.py`,
  `test_ir_layout_routes.py`, `test_ir_editor_equivalence.py`, `test_ir_experiment*.py`,
  `test_ir_platform_library.py`, `test_research_review*_routes.py`, and
  `test_review_snapshot_routes.py`.
- The affected execution-attribution gates are `test_execution_attribution.py`,
  `test_execution_binding.py`, `test_paper_authority*.py`,
  `test_shadow_deployments.py`, `test_shadow_deployment_engine.py`, and
  `test_execution_cockpit.py`.
- Protected and out-of-scope files remain untouched: `app/engine/kite_venue.py`,
  `app/engine/venue.py`, `app/providers/brokers.py`, and `tests/test_broker_registry.py`.

## Observable success definition

Two owners can persist the same graph identifier/version and overlapping layout child IDs while
all caller-scoped reads/writes return their own rows. The canonical graph bytes and content address
remain identical for byte-identical graphs. A 0020 database upgrades with every legacy graph,
layout, timestamp, revision, visibility, and MONEY provenance value intact and owned by
`LEGACY_OWNER_ID`; downgrade either round-trips a sole legacy lineage or refuses before DDL.

## TDD status

### Observed RED before production edits

The verified interpreter ran the same-identifier node and it failed at owner B's
`create_artifact`: `GraphConflict: graph draft is at revision 0`. This was the intended global
artifact-key failure. The independent migration RED failed with
`AssertionError: 0021 must backfill an owner identity on graph_artifacts`; it was not a collection
or dependency failure.

### Implemented contract

- Revision `0021` rebuilds the USER graph/layout identity chain, backfills `LEGACY_OWNER_ID`,
  restores immutable graph triggers/indexes, and adds the project owner/project candidate key.
- Paper and shadow deployment graph provenance remains value data. Their graph foreign keys are
  removed on upgrade and restored on a lossless legacy downgrade; neither table gains a USER-plane
  graph foreign key.
- Graph/layout repositories use owner-bearing primary keys and predicates. Catalogue seeding names
  `LEGACY_OWNER_ID` only at the bootstrap seam.
- Paper and shadow revalidation resolve an immutable version by the retained MONEY owner value, so
  ambiguous same identifier/version rows fail closed without changing execution authority fields.

### Verification

All commands used the verified Python 3.13.5 interpreter:

```text
pytest -q tests/test_schema_migrations.py --tb=short       # 50 passed
pytest -q [execution attribution/binding, paper authority, shadow deployment, cockpit]  # 242 passed
pytest -q [tenant, graph, layout, IR route/presentation/equivalence/library]  # 133 passed
python -m compileall -q app migrations tests
git diff --check
```

The graph/layout and execution commands only emit the existing Starlette/httpx deprecation warning.
