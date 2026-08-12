# Task 1B.2 report — tenant-owned review persistence and search

## Scope delivered

- Added migration `0022` from `0021`, rebuilding review notes, saved views, and snapshots with owner-first composite keys and composite project foreign keys.
- Backfilled owner from each parent project, preserved canonical payload columns and snapshot bytes, restored snapshot immutability triggers, and preserved SQLite foreign-key state.
- Added keyword-only `owner_id` to review repositories and scoped project lookups, row lookups, CAS mutations, capture retries, note capture, and listing queries.
- Routes derive and pass `owner_id_for(principal)` across notes, views, snapshots, search, and timeline composition. `created_by` remains `"owner"`.

## TDD evidence

Repository RED before production edits:

```text
TypeError: create_note() got an unexpected keyword argument 'owner_id'
1 failed in 5.58s
```

Migration RED before production edits:

```text
AssertionError: assert 'note_id' == 'owner_id'
1 failed, 5 warnings in 2.34s
```

### Evidence-only follow-up — round 4

The migration and repositories were already accepted as correct, so this round made no production change and had no natural implementation RED. It added boundary tests first, then proved them with controlled production mutations that were immediately restored:

- Replacing the note-create route's resolved owner with a literal made the all-route propagation test fail for both API prefixes. The exact failure was `create_note` receiving `owner.mutated` instead of `owner.spy` at call index 9.
- Replacing the note-list owner predicate with a literal owner made the explicit same-ID owner-B list empty. The real repository test failed before any update or delete.
- Restoring `PRAGMA foreign_keys` to `ON` unconditionally after successful 0022 upgrade made the OFF matrix fail: the observed value was `1`, expected `0`.

Each mutated production file was restored to its pre-mutation SHA-256 before the green gates:

```text
research_review_routes.py  cdd6778a549159fda57f1740f7f7e40e7c77733200755bf24e7ed14914b7eb9c
review_state.py            aa10164405862a907b21f06586187e372a07553e230a64f7cce21b341412d9dd
20260812_0022_review_state_owner.py
                           082bd9c53b9ca31a71fcbe227e0864227d461d8dfed0a1a535934cdb18356311
```

### Evidence-only follow-up — round 5

- The explicit same-ID fixture now asserts that `list_snapshots()` returns
  `snapshot.explicit.shared` for both supplied owners. This closes the listing
  boundary alongside the existing get and idempotent-capture assertions.
- Mutating `list_snapshots()` from `ProjectReviewSnapshot.owner_id == owner_id`
  to `ProjectReviewSnapshot.owner_id == "owner.mutated"` made the fixture fail:
  the owner-A listing was `()` where the expected tuple contained
  `snapshot.explicit.shared`. The production file was then restored exactly.

```text
review_snapshot_store.py  de8d608c5b21325398052eda38f92b1749a9908fe4b86e6b92dea2977cb55a3d
```

## Recovery matrix

- Populated 0021 upgrade preserves exact note/view/snapshot fields, timestamps, JSON, manifest bytes, content address, revision, and deleted state: passed.
- Fresh versus upgraded full review schema contract parity: passed.
- Source plus stale temp is source-authoritative and clears its stale proof; source-absent temp is promoted only with the migration-local proof: passed.
- Before an upgrade proof is written, the migration independently derives the expected ownerful target rows from the authoritative 0021 review/project join and compares its canonical count/digest to the copied temp. A post-copy payload mutation therefore refuses before source drop.
- Proofs carry an explicit direction and logical target schema digest. Upgrade proof validates only ownerful 0022 temps; downgrade proof validates only 0021 legacy temps. Before a downgrade source drop, the migration compares the legacy temp to a deterministic ownerful-source projection, records a `down` proof, and retries from a source-absent legacy temp safely.
- Unproven and malformed-but-payload-proven source-absent temps refuse before DDL, retaining tables, proof, and Alembic version: passed.
- Upgrade and downgrade stale/completed-temp recovery covers every review table: passed (6 cases).
- Injected upgrade and downgrade rebuild interruption restores caller FK state with both `PRAGMA foreign_keys=ON` and `OFF`: passed (4 cases).
- Successful upgrade and downgrade preserve caller FK state with both `PRAGMA foreign_keys=ON` and `OFF`: passed (4 cases).
- Legacy `0021 -> 0022 -> 0021 -> 0022` rows: passed.
- The successful 0022→0021 leg restores the exact pre-upgrade review schema and rows, and removes all rebuild-proof bookkeeping before Alembic completion: passed.
- Unsafe downgrade preflight runs before recovery, FK-mode changes, or DDL. It rejects an unrepresentable authoritative source while retaining a stale temp, schema, FK mode, and version byte-for-byte: passed.
- Cross-owner composite project FK is rejected for notes, saved views, and snapshots: passed.

## Caller audit

- `review_state.py`: all note/view repository operations require owner and put owner first in list, get, and CAS predicates or composite keys.
- `review_snapshot_store.py`: capture/idempotent retry, note selection, list, and get all use owner scope first.
- Real owner-A/owner-B rows now seed the same explicit note/view/snapshot IDs and capture key. Real list, update, delete, snapshot get, and idempotent retry operations run under both owners; raw rows show that each operation leaves the foreign owner's fields unchanged.
- Note delete, saved-view update/delete, snapshot get, foreign project reads, snapshot retries, and potential capture conflicts have the same absent public shape. The tests assert exact 404 status/body pairs, omit revision/time/content fields, and leave every persisted row unchanged.
- `research_review_routes.py`: a parameterized owner spy covers both `/api/ir` and `/api/v1/ir` for timeline, search, all read endpoints, note POST/PATCH/DELETE, saved-view POST/PATCH/DELETE, snapshot POST, and individual snapshot GET. It asserts the complete ordered owner-bearing call list.
- `review_aggregation.py` already takes owner scope.

## Changed files

### Original implementation

- `backend/migrations/versions/20260812_0022_review_state_owner.py`
- `backend/app/db/models.py`
- `backend/app/core/review_state.py`
- `backend/app/core/review_snapshot_store.py`
- `backend/app/api/research_review_routes.py`
- Focused migration, tenant-isolation, review repository, and route tests.

### Evidence-only follow-up — round 4

- `backend/tests/test_research_review_routes.py`
- `backend/tests/test_user_plane_tenant_isolation.py`
- `backend/tests/test_schema_migrations.py`
- This report.

No production migration, repository, model, or route file changed in this follow-up.

### Evidence-only follow-up — round 5

- `backend/tests/test_user_plane_tenant_isolation.py`
- This report.

No production file changed in this follow-up.

## Verification

- Historical implementation gate: 167 collected and passed (exit 0): `test_schema_migrations.py` (131), `test_user_plane_tenant_isolation.py` (13), `test_research_review_routes.py` (8), `test_review_state.py` (6), and `test_review_snapshot_store.py` (9). It ran with `/tmp/codex-review-0022-venv/bin/python` because the system `python3` is Python 3.9 and cannot import the project's modern union annotations.
- Round-4 tenant/review gate: 77 passed (exit 0): `test_user_plane_tenant_isolation.py` (15), `test_research_review_routes.py` (12), `test_review_state.py` (6), `test_review_snapshot_store.py` (9), `test_review_state_routes.py` (6), `test_review_snapshot_routes.py` (7), `test_review_search.py` (6), `test_review_search_routes.py` (7), `test_review_snapshot_manifest.py` (5), and `test_research_review.py` (4).
- Round-4 migration gate: 26 passed (exit 0): `/tmp/codex-review-0022-venv/bin/python -m pytest tests/test_schema_migrations.py -k 'revision_0022' -q`.
- The two new route/repository cases passed as 6 parameterized cases. The new successful and existing failing FK-state matrices passed as 8 parameterized cases.
- `/tmp/codex-review-0022-venv/bin/python -m compileall -q app migrations tests research research_tests`: passed.
- `git diff --check`: passed.
- Round-5 tenant/review gate: 77 passed (exit 0): `/tmp/codex-review-0022-venv/bin/python -m pytest tests/test_user_plane_tenant_isolation.py tests/test_research_review_routes.py tests/test_review_state.py tests/test_review_snapshot_store.py tests/test_review_state_routes.py tests/test_review_snapshot_routes.py tests/test_review_search.py tests/test_review_search_routes.py tests/test_review_snapshot_manifest.py tests/test_research_review.py -q`.
- Round-5 migration gate: 26 passed (exit 0): `/tmp/codex-review-0022-venv/bin/python -m pytest tests/test_schema_migrations.py -k 'revision_0022' -q`.
- Pre-edit expanded focused baseline: 188 passed and 1 failed. `tests/test_schema_migrations.py::test_revision_0020_downgrade_retry_promotes_completed_0019_temp_tables` fails because its deliberately incomplete `graph_versions__0019` temporary table makes 0022's `PRAGMA foreign_key_check` raise `foreign key mismatch`. This is outside the 0022 review ownership slice and no production change was authorized for it.
- A previous full `pytest -q` reached 100% with one unrelated failure: `tests/test_db_planes.py::test_the_grandfathered_crossings_are_all_real` reports four stale legacy entries in `GRANDFATHERED_CROSS_PLANE_FKS` for `ir_paper_deployments`/`ir_shadow_deployments`. The same isolated node fails unchanged in a clean detached worktree at review baseline commit `6fd9fe56f1de38398921c037c66e2ef3ef5c3f97`; it is outside the review-tenancy slice.

## Deferred semantics and concerns

- Task 5 authentication and user attribution remain deferred. `created_by` is still the durable literal `"owner"`, never tenant identity.
- Snapshot manifest JSON and content-address inputs remain owner-free.
- The four pre-existing broker/provider worktree changes were not edited or staged.
