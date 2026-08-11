# Phase 1 Multi-user Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make owner and broker-account identity structural across persistence, repositories,
APIs, caches and WebSocket delivery, ending with an adversarial two-tenant isolation gate.

**Architecture:** `Organization` is the tenant and existing `owner_id` values refer to it by
value across physical-plane boundaries. `User` reaches organizations through `Membership`;
`BrokerAccount` scopes money state independently of credentials. Repository queries require
scope before data is loaded, and the centralized principal policy authorizes the scoped object.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pytest, SQLite compatibility during
Phase 1; PostgreSQL support begins in Phase 2.

## Global Constraints

- Preserve every live-money safety invariant in `paper-trader/CLAUDE.md`.
- Do not edit or deploy the owner's live environment or credentials.
- No production code may be written before its failing behavioral test is observed.
- Never add a decorative owner column above a globally singleton key.
- Never accept `owner_id` or `broker_account_id` from an untrusted request body.
- Authorization decisions remain centralized in `app/api/principal.py::is_allowed`.
- New cross-plane relations are by value, never foreign key.
- Preserve current uncommitted changes in `app/engine/{venue,kite_venue}.py`,
  `app/providers/brokers.py`, and `tests/test_broker_registry.py`.

---

### Task 1: Tenancy roots and account-scoped singleton money state

**Files:**
- Create: `backend/migrations/versions/20260811_0018_tenancy_roots_and_account_state.py`
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/planes.py`
- Modify: `backend/app/db/session.py`
- Modify: direct key consumers in `backend/app/core/execution_book.py`,
  `backend/app/core/scoped_config.py`, `backend/app/core/execution_binding.py`,
  `backend/app/core/paper_authority.py`, `backend/app/core/universe_resolver.py`, and
  `backend/app/engine/runner.py` only when the failing tests prove the old key is used
- Modify: `backend/tests/test_money_plane_ownership.py`
- Modify: `backend/tests/test_schema_migrations.py`
- Create: `backend/tests/test_tenancy_roots.py`
- Create: `backend/tests/test_account_scoped_state.py`

**Interfaces:**
- Produces: `Organization(organization_id, name, status, created_at, updated_at)`,
  `User(user_id, email_normalized, display_name, status, created_at, updated_at)`,
  `Membership(organization_id, user_id, role, status, created_at, updated_at)`, and
  `BrokerAccount(broker_account_id, owner_id, broker, external_account_id, display_name, status,
  created_at, updated_at)` ORM models.
- Produces: `LEGACY_USER_ID = "owner-user"` and `LEGACY_BROKER_ACCOUNT_ID = "account.default"`.
- Produces: account-scoped helpers whose scope argument is keyword-only; no helper may silently
  default to another tenant after this task.
- Changes identities to `(broker_account_id, book)`, `(owner_id, instrument_key)`, and
  `(broker_account_id, day)`.

- [ ] **Step 1: Write the migration and model contract tests**

  Add literal assertions that the four root tables exist, every legacy identity is seeded, and
  the three replacement keys exactly match the tuples above. Seed pre-0018 rows with raw SQL,
  upgrade to `0018`, and assert every financial value and timestamp is unchanged while the new
  scope equals the legacy constant.

- [ ] **Step 2: Verify RED for the intended missing behavior**

  Run:

  ```bash
  /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest \
    tests/test_tenancy_roots.py tests/test_account_scoped_state.py \
    tests/test_money_plane_ownership.py tests/test_schema_migrations.py -q
  ```

  Expected: failures naming absent root tables/models, old singleton keys, or migration head
  `0017`; collection/import errors are not an acceptable RED.

- [ ] **Step 3: Add the four models and revision 0018**

  Use `active|disabled` for organization/user/account status, `active|invited|revoked` for
  membership status, and `owner|admin|member|viewer` for membership role. User email is globally
  unique after trim+lower normalization. Broker accounts are unique on
  `(owner_id, broker, external_account_id)`. Do not create a money-to-user cross-plane foreign
  key. Copy legacy rows explicitly during SQLite table rebuilds. Refuse a downgrade that would
  collapse more than one scoped row onto an old singleton key.

- [ ] **Step 4: Update direct singleton-state consumers**

  Every `session.get(CapitalState, ...)`, `session.get(InstrumentState, ...)`, and
  `session.get(DailyAccountSnapshot, ...)` must provide the declared scope. Default seeds use the
  legacy constants only at the compatibility boundary; request/runtime code receives scope from
  its caller.

- [ ] **Step 5: Verify GREEN and migration parity**

  Re-run the Step 2 command, then:

  ```bash
  /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m app.db.migrate head
  ```

  Expected: all focused tests pass and migration head reports `0018`.

- [ ] **Step 6: Run affected execution regressions**

  ```bash
  /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest \
    tests/test_book_isolation.py tests/test_capital_books.py tests/test_execution_binding.py \
    tests/test_paper_authority.py tests/test_paper_authority_runtime.py \
    tests/test_account_pnl.py tests/test_daily_reanchor.py tests/test_daily_profit_lock.py \
    tests/test_scoped_config.py -q
  ```

- [ ] **Step 7: Commit the coherent slice**

  Stage only Task 1 files and commit with `feat(tenancy): root money state in customer accounts`.

### Task 2: Owner/account-scope every money repository and execution read

**Files:**
- Modify: `backend/app/core/deployments.py`, `execution_book.py`
- Modify: `backend/app/engine/{broker,analytics,execution_lifecycle,live_broker,runner}.py`
- Modify: money-reading API modules under `backend/app/api/`
- Test: `backend/tests/test_money_repository_isolation.py`
- Test: existing deployment, lifecycle, analytics, broker and route suites

**Interfaces:**
- Consumes: Task 1 owner/account identities.
- Produces: keyword-only owner/account arguments on every money repository read/write.
- Produces: tenant-local deployment name uniqueness.

- [ ] Write two-tenant tests using identical deployment names, instruments and modes; a wrong
  scope must return no row rather than loading then refusing it.
- [ ] Run the focused tests and observe failures on global queries.
- [ ] Add scope predicates at repository boundaries and thread scope from engine bindings.
- [ ] Re-run focused tests plus lifecycle recovery and accounting regressions.
- [ ] Commit as `feat(tenancy): isolate money repositories by account`.

**Recovery follow-up (2026-08-11, local only):** revision `0019` now resumes safely after
SQLite interrupts its deployment rebuild or an account-table batch rebuild. If both source and
temporary tables remain, it discards the stale temporary table; if only the temporary rebuilt
table remains, it promotes it. The resumed migration restores deployment/account indexes and
the immutable-event guards. Four injected interruption points passed (deployment temp creation,
deployment rename, positions temp creation, positions rename), as did the full migration suite
(29 tests), lifecycle/recovery (65), telemetry/live-entry (18), and position/book isolation (24).
`NewExecutionIntent` and the lot-size repair boundary now require explicit owner/account scope.
No frontend work or deployment was performed.

**Recovery hardening (2026-08-12):** `0019` now treats every SQLite batch rebuild as
restartable. Its explicit historical index manifest restores all legacy, account-scope,
unique, and partial indexes after a retry; it does not consult current ORM metadata. Default
removal now also recovers stale batch tables for deployments, every money table,
`instrument_state`, `capital_state`, and `daily_account_snapshot`. Injected failures after
account-table renames and at default-removal CREATE/RENAME boundaries converge to the exact
fresh-0019 table contract, including defaults, foreign keys, unique rules, and index SQL.
The migration suite passed (34 tests), as did account/money isolation (106 tests) and
`compileall`; no frontend work or deployment was performed.

### Task 3: Own product, graph, research and review objects

**Files:**
- Create: next Alembic revision
- Modify: `backend/app/db/models.py`, `app/db/planes.py`
- Modify: repositories under `backend/app/editor/`, `backend/app/core/research_*`, and
  `backend/research/`
- Test: `backend/tests/test_user_plane_tenant_isolation.py`
- Test: existing graph, layout, review, research and migration suites

**Interfaces:**
- Consumes: organization identity.
- Produces: owner-scoped project, graph, watchlist, strategy, research and review identities.
- Preserves: executable graph bytes and content addresses; owner is provenance, not graph content.

- [ ] Write tests proving two organizations can use identical human-facing names and cannot
  read each other's guessed project/graph/review IDs.
- [ ] Observe RED on global keys and unscoped repositories.
- [ ] Add owner dimensions and tenant-local unique constraints without altering canonical IR.
- [ ] Update repositories so scope is present in the query that loads the object.
- [ ] Prove existing graph content addresses are byte-identical after migration.
- [ ] Run focused user-plane, migration and IR regressions; commit.

### Task 4: Own backtests, jobs and reusable caches

**Files:**
- Create: next Alembic revision
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/backtest/{cache,sweep,dataset_store}.py`
- Modify: research/background operation stores
- Test: `backend/tests/test_tenant_backtest_isolation.py`

**Interfaces:**
- Produces: owner-scoped run/job/result visibility.
- Preserves: content-addressed market datasets may be physically shared, but authorization and
  result visibility are tenant-scoped; a cache hit may reuse computation without returning
  another tenant's row identity or private parameters.

- [ ] Write a poisoned-cache test where two owners have the same public dataset/strategy inputs
  but different private run identities; neither list/detail endpoint may return the other's row.
- [ ] Observe RED on current tenantless run/result queries.
- [ ] Add ownership and scoped repositories while retaining honest content-address reuse.
- [ ] Run cache, pinned, parallel, batch-persistence and research-operation regressions; commit.

### Task 5: Resolve real principals and enforce scoped APIs/exports

**Files:**
- Modify: `backend/app/api/principal.py`, middleware/auth modules and route dependencies
- Create: `UserSession` persistence with an opaque 256-bit bearer token stored only as SHA-256,
  explicit expiry and revocation timestamps, and an active-organization binding
- Test: `backend/tests/test_cross_tenant_idor.py`
- Test: `backend/tests/test_principal.py` and all route suites

**Interfaces:**
- Consumes: User/Membership/Organization.
- Produces: a principal with user identity, active organization, membership role and scopes;
  HTTP and WebSocket authentication resolve the same `UserSession` record.
- Preserves: one `is_allowed` policy boundary and an explicit unauthenticated development mode
  that cannot be enabled in production configuration.

- [ ] Write guessed-ID and wrong-membership tests for every resource family before route changes.
- [ ] Observe 200/global-read failures under the wrong principal.
- [ ] Resolve authenticated sessions to memberships and inject scope into repository calls.
- [ ] Reject disabled-auth configuration in production service roles.
- [ ] Run route/import/auth regressions and commit.

### Task 6: Partition WebSockets, exports and in-memory caches

**Files:**
- Modify: `backend/app/ws/manager.py`, WebSocket routes, export endpoints and answer-changing caches
- Test: `backend/tests/test_tenant_websocket_isolation.py`
- Test: `backend/tests/test_tenant_cache_keys.py`

**Interfaces:**
- Produces: tenant/account channels derived from the resolved principal.
- Produces: cache keys containing every answer-changing owner/account dimension.

- [ ] Connect two authenticated tenants and prove a private event for A is never delivered to B.
- [ ] Poison each audited cache under A and prove B cannot receive A's private value.
- [ ] Observe current global fan-out/key failures.
- [ ] Partition channels and keys, keeping shared public market data explicitly public.
- [ ] Run WebSocket, cache, export and load regressions; commit.

### Task 7: Phase 1 adversarial gate

**Files:**
- Create: `backend/tests/test_phase1_multi_tenant_gate.py`
- Modify: Phase 1 documentation and current-state handoff

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: one executable two-tenant proof used as the Phase 2 prerequisite.

- [ ] Exercise identical names/IDs across two tenants for projects, graphs, deployments,
  connections, account state, backtests and jobs.
- [ ] Attempt guessed IDs, wrong account bindings, direct repository calls, cache poisoning and
  WebSocket observation; every cross-tenant action must refuse or return no row.
- [ ] Run the full backend and research suites.
- [ ] Run `scripts/dryrun.py 700` and require `LEDGER OK` with zero drift.
- [ ] Run `scripts/backtest_smoke.py` and require `SWEEP OK`.
- [ ] Run the independent security-tenancy review and fix all load-bearing findings.
- [ ] Commit the Phase 1 gate and update the programme ledger before Phase 2.
