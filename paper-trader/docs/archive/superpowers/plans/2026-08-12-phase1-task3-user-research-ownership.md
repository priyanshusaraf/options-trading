# Phase 1 Task 3 USER/Research Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make product, graph, review, strategy configuration and research-root identities
organization-owned without changing canonical strategy bytes or exposing private-content
existence across tenants.

**Architecture:** Add structural owner dimensions at persistence roots and all descendant lookup
keys, then require keyword-only owner scope at repository boundaries. Keep graph ownership and
visibility as provenance outside canonical IR. Split the work into three independently reviewable
migrations: graph/review ownership, product configuration ownership, and versioned research-root
ownership.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pytest, SQLite compatibility during
Phase 1; PostgreSQL support begins in Phase 2.

## Global Constraints

- Preserve every live-money safety invariant in `paper-trader/CLAUDE.md`.
- Do not edit or deploy the owner's live environment or credentials.
- No production code may be written before its failing behavioral test is observed.
- Never add a decorative owner column above a globally singleton child key.
- Never accept `owner_id` from an untrusted request body.
- Task 3 repositories require keyword-only `owner_id`; Task 5 will resolve it from real sessions.
- New cross-plane relations are by value, never foreign key.
- Preserve canonical graph/component bytes and `content_address`; owner and visibility are
  provenance and must not enter the hash.
- Private content has no global hash lookup, existence response or cross-tenant dedup entitlement.
- “Published graph revision” remains an immutable executable revision, not public visibility.
- Keep Task 3 reads private-only. Do not implement sharing, public discovery or marketplace flows.
- Preserve uncommitted changes in `app/engine/{venue,kite_venue}.py`,
  `app/providers/brokers.py`, and `tests/test_broker_registry.py`.

---

### Task 1: Own projects, graph versions, layouts and reviews

**Accepted execution decomposition:** this dependency is delivered through independently runnable
and reviewed slices. Task 1A.1 owns the project root and graph repository access; Task 1A.2 scopes
layout repositories; Task 1A.3 rebuilds graph/layout identities so owners may reuse graph
identifiers; research roots then land before review persistence so review aggregation never mixes
owned graphs with globally scanned research rows. The final Task 1 acceptance criteria remain
unchanged.

**Files:**
- Create: `backend/migrations/versions/20260812_0020_user_graph_review_ownership.py`
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/editor/graph_artifacts.py`
- Modify: `backend/app/editor/layouts.py`
- Modify: `backend/app/core/review_state.py`
- Modify: `backend/app/core/review_snapshot_store.py`
- Modify only proven callers under `backend/app/core/review_aggregation.py` and `backend/app/api/`
- Create: `backend/tests/test_user_plane_tenant_isolation.py`
- Modify: `backend/tests/test_schema_migrations.py`
- Modify: focused graph/layout/review tests when explicit scope changes their call contract

**Interfaces:**
- Consumes: `Organization.organization_id` and `LEGACY_OWNER_ID` from tenancy roots.
- Produces: required keyword-only `owner_id: str` on project, graph, layout and review stores.
- Produces: structural `(owner_id, graph_identifier, ...)` identities for graph descendants.
- Produces: private-only immutable graph-version visibility provenance.
- Preserves: exact `draft_json`, `artifact_json`, snapshot manifests and graph content addresses.

- [ ] **Step 1: Write two-tenant repository tests**

  Add fixtures that create `owner.a` and `owner.b`, use the same project name and graph
  identifier, publish byte-identical graphs, then assert:

  ```python
  assert graph_a.content_address == graph_b.content_address
  assert load_version(project_a, "same.graph", 1, owner_id="owner.a").project_id == project_a
  with pytest.raises(GraphVersionNotFound):
      load_version(project_a, "same.graph", 1, owner_id="owner.b")
  with pytest.raises(TypeError):
      load_version(project_a, "same.graph", 1)
  ```

  Cover layout heads/positions/groups, note IDs, saved-view IDs/names, snapshot IDs/capture keys,
  project listing/status and every direct graph version load. A wrong owner must produce the same
  not-found class as an absent object.

- [ ] **Step 2: Write migration RED tests**

  Build a real `0019` database with projects, drafts, published versions, layout children, review
  children and immutable snapshots. Upgrade to `0020` and assert every byte, timestamp and content
  address is unchanged and all owner values equal `LEGACY_OWNER_ID`. Assert exact composite keys,
  foreign keys, tenant-local indexes, private-only visibility default/check and immutable triggers.
  Inject failures after SQLite temp creation and rename for a graph parent and immutable child;
  retry must converge to the fresh-`0020` contract.

- [ ] **Step 3: Run the intended RED gate**

  ```bash
  /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest -q \
    tests/test_user_plane_tenant_isolation.py tests/test_schema_migrations.py \
    tests/test_graph_artifacts.py tests/test_ir_layout_routes.py \
    tests/test_review_state.py tests/test_review_snapshot_store.py --tb=short
  ```

  Accept only behavioral failures caused by missing owner identity/predicates or revision `0020`.

- [ ] **Step 4: Implement revision 0020 and ORM identities**

  Rebuild in parent-to-child order. Use same-plane organization foreign keys for USER roots and
  owner-bearing composite foreign keys for graph/layout/review descendants. Preserve MONEY-plane
  graph provenance by value. Backfill legacy ownership explicitly, restore historical indexes and
  immutable triggers from a migration-local manifest, make rebuilds restartable, and refuse
  downgrade when owner dimensions would collapse.

- [ ] **Step 5: Thread owner through repositories**

  Change each public service signature to place `owner_id` after `*`, for example:

  ```python
  def load_version(project_id: str, identifier: str, version: int, *, owner_id: str) -> PublishedGraph:
      ...
  ```

  Include owner in the first project/artifact/version/layout/review SQL query. Do not expose a
  global `content_address` lookup. Existing API composition may pass the trusted development owner
  explicitly until Task 5 replaces it with a real principal.

- [ ] **Step 6: Prove GREEN and canonical parity**

  Re-run Step 3, the IR authoring/parity/comparison suites and `python -m app.db.migrate head`.
  Add a direct before/after SHA-256 assertion over stored canonical JSON.

- [ ] **Step 7: Commit the accepted slice**

  Commit only Task 1 files as `feat(tenancy): own graph and review artifacts` after independent
  spec and code-quality review.

### Task 2: Own watchlists, strategy state, generated strategies and runtime configuration

**Files:**
- Create: `backend/migrations/versions/20260812_0021_user_strategy_config_ownership.py`
- Modify: `backend/app/db/models.py`, `backend/app/db/planes.py`
- Modify: `backend/app/core/watchlists.py`
- Modify: `backend/app/core/strategy_archive.py`
- Modify: `backend/app/core/generated_strategies.py`
- Modify: `backend/app/core/runtime_config.py`
- Modify only direct composition callers under `backend/app/api/`, `backend/app/engine/` and
  `backend/app/core/deploy_bridge.py`
- Extend: `backend/tests/test_user_plane_tenant_isolation.py`
- Modify: migration, watchlist, strategy archive, generated strategy and runtime config tests

**Interfaces:**
- Consumes: organization ownership and Task 1 scoped graph provenance.
- Produces: tenant-local watchlist names, membership instrument keys, strategy keys and runtime
  config keys.
- Produces: organization-aware generated-strategy resolution; no process-global same-key overwrite.
- Preserves: MONEY-plane deployment/account scope and existing execution authority gates.

- [ ] **Step 1: Write collision and guessed-ID tests**

  Prove two owners can independently use `default`, the same instrument membership, strategy key,
  generated key and runtime-config key. Prove every wrong-owner read/update/delete returns no row
  or the existing not-found class and every unscoped call raises `TypeError`.

- [ ] **Step 2: Write revision 0021 migration tests and observe RED**

  Seed `0020` watchlists, memberships, lifecycle, generated strategy and runtime-config rows;
  verify exact payload preservation, tenant-local uniqueness, owner-consistent parent relations,
  restart recovery and lossy-downgrade refusal. Run:

  ```bash
  /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest -q \
    tests/test_user_plane_tenant_isolation.py tests/test_schema_migrations.py \
    tests/test_watchlists.py tests/test_watchlist_conflicts.py tests/test_strategy_archive.py \
    tests/test_portfolio_routes.py tests/test_scoped_config.py --tb=short
  ```

- [ ] **Step 3: Implement structural ownership**

  Rebuild watchlist parent/children and lifecycle relations together. Add owner to generated
  strategy identity and runtime config identity. Backfill legacy rows, restore indexes and refuse
  downgrade collisions. Do not create a USER-to-MONEY foreign key.

- [ ] **Step 4: Replace global strategy/config stores**

  Require owner on repository calls and partition any in-process generated strategy or effective
  config cache by owner. Resolve one owner's strategy key without registering or returning another
  owner's object. Keep execution authority checks unchanged.

- [ ] **Step 5: Run focused and execution regression gates**

  Re-run Step 2 plus deployment binding, paper authority, runner and portfolio suites. Inspect SQL
  for owner predicates at the initial lookup, not post-load checks.

- [ ] **Step 6: Commit the accepted slice**

  Commit only Task 2 files as `feat(tenancy): own strategy configuration` after independent review.

### Task 3: Version and own research roots

**Files:**
- Create: `backend/research/domain/migrate.py`
- Create: `backend/research/domain/migrations/0001_owner_scoped_roots.py`
- Modify: `backend/research/domain/base.py`
- Modify: `backend/research/domain/models.py`
- Modify: repositories that create/read research programs, hypotheses, experiment specifications,
  generated strategy/source roots and reusable block definitions
- Modify: `backend/app/core/research_read.py` only for Task 3 root/project predicates
- Create: `backend/tests/test_research_tenant_isolation.py`
- Modify: existing research-domain migration/strategy/review tests

**Interfaces:**
- Consumes: organization value ownership; research DB remains physically separate in Phase 1.
- Produces: explicit research schema versioning and keyword-only owner scope on research roots.
- Produces: tenant-local research names and non-probeable content-address locators.
- Defers: experiment-run/job/trial/finding/candidate/shadow visibility and operation files to Task 4.

- [ ] **Step 1: Write research schema and isolation RED tests**

  Create a pre-versioned legacy `research.db`, migrate it, and verify preserved programs,
  hypotheses, specs, generated strategy/source and block rows. Create two owners with identical
  names/content and prove wrong-owner guessed IDs and hashes reveal no row. Require `owner_id` in
  each repository signature.

- [ ] **Step 2: Run the research RED gate**

  ```bash
  /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest -q \
    tests/test_research_tenant_isolation.py tests/test_research_review.py \
    tests/test_research_review_routes.py tests/test_research_flag.py research_tests --tb=short
  ```

- [ ] **Step 3: Add an idempotent research migration boundary**

  Record an explicit schema version in `research.db`; upgrade legacy unversioned tables by copying
  exact rows into owner-scoped tables under `LEGACY_OWNER_ID`. Never rely on `create_all()` to alter
  existing tables. Recovery must handle a persisted temp table and refuse lossy downgrade.

- [ ] **Step 4: Scope research root repositories**

  Add owner to the first SQL predicate for programs, hypotheses, specs, generated roots and block
  definitions. Replace recipe-JSON-only project filtering with an indexed owner/project predicate
  where Task 3 owns the root; leave Task 4 run/evidence visibility changes explicit in its ledger.

- [ ] **Step 5: Run Task 3 acceptance**

  Run Step 2, all application graph/layout/review/strategy focused suites from Tasks 1-2, the full
  non-process backend/research suite, and the isolated process-worker backtest gate. Run
  `compileall -q app research migrations tests research_tests` and `git diff --check`.

- [ ] **Step 6: Run independent adversarial review and commit**

  Review migration recovery, SQL-first tenant predicates, canonical-byte parity, hash/existence
  responses, cross-plane relations and protected-file scope. Fix every load-bearing finding, then
  commit as `feat(tenancy): own research roots` and mark Phase 1 Task 3 complete.
