# SDD ledger — plan: /Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation/paper-trader/docs/superpowers/plans/2026-08-12-phase2-postgresql-production-concurrency.md

## Task 1: complete

- Base commit: `be533a2fe903b861a4f15cec7c396a2af0d25263`
- Implementer: `/root/phase2_task1_impl`
- Review round 1: BLOCK — PostgreSQL JSON checks and partial indexes retained SQLite-only semantics.
- Fix round 1: portable JSONB checks, PostgreSQL partial-index predicates, immutable PostgreSQL triggers, reset safety, and full current-schema validation implemented.
- Review round 2: BLOCK — PostgreSQL deparsed JSONB casts would falsely fail exact CHECK validation.
- Fix round 2: bounded `CAST(column AS JSONB)` / `(column)::jsonb` canonicalization with realistic reflection fixture; same-name `CHECK(TRUE)` remains rejected.
- Final re-review: SPEC PASS / QUALITY PASS.
- Commits: `8b2014a feat(db): add PostgreSQL execution profile`; `d9b0656 fix(db): validate PostgreSQL schema semantics`.
- Verification: the final focused gate passed `37/37` against local PostgreSQL 16, including fresh create, structural validation, stamping, and idempotent restart. Changed modules compiled, all 45 model tables compiled for PostgreSQL, and `git diff --check` passed.
- PostgreSQL 16 is available through the isolated test database used by the optional `PT_TEST_POSTGRES_URL` gate. This proves the local profile and two-session semantics; it is not a managed-production deployment claim.
- Protected inherited dirty files must remain unstaged: `paper-trader/backend/app/engine/kite_venue.py`, `paper-trader/backend/app/engine/venue.py`, `paper-trader/backend/app/providers/brokers.py`, `paper-trader/backend/tests/test_broker_registry.py`.

## Task 2: complete

- Base commit: `d9b0656`.
- Implementer: `/root/phase2_task2_impl`.
- Independent review round 1: BLOCK — OAuth credential persistence could race connection revocation after revalidation, and executed Core DML was invisible to the pending-write fail-closed checks.
- Fix round 1: callback credential persistence is one active owner/account/auth-qualified conditional update; public SQLAlchemy session events preserve transaction write provenance across Core DML and flushes. Real SQLite/PostgreSQL regressions cover revoke-before-store and capital bootstrap after direct Core UPDATE; SQLite helper tests cover clean-read restart and mutation locking.
- Final re-review: SPEC PASS / QUALITY PASS. The reviewer reproduced both race orders for OAuth revocation and verified write-provenance lifecycle through flush, savepoint, root commit, and rollback.
- Retained evidence after review fixes: portable SQLite/PostgreSQL module `32` cases inside the affected regression gate; affected regression gate `267 passed`; earlier independent widened live gate `100 passed`; compileall and `git diff --check` passed.
- Commit subject: `feat(db): make shared mutations portable`.
- Commit: `c079001 feat(db): make shared mutations portable`.
- A broad `tests research_tests` run reached 96%, but its final exit status was not retained. It is explicitly inconclusive and is not reported as passing.

## Task 3: complete

- Base commit: `c079001`.
- Implementer: `/root/phase2_task3_impl2` (replacement after two disconnected streams made no Task 3 edits).
- Added authoritative `PT_RESEARCH_DATABASE_URL` and `PT_LEDGER_DATABASE_URL` with separate local SQLite path fallbacks; production requires PostgreSQL for enabled planes.
- Research and ledger PostgreSQL startup now branches before all historical SQLite migration/introspection. Empty schemas create current metadata, validate, stamp plane-owned markers, and restart idempotently. Managed current schemas validate read-only. Populated unmanaged, wrong-head, relationally tampered, or trigger-tampered schemas refuse without adoption.
- Research immutability has dialect-scoped SQLite DDL and PostgreSQL functions/triggers. All three database authorities are checked pairwise; a shared PostgreSQL database requires explicit, non-overlapping search paths. Ledger sessionmaker caching follows authority changes and disposes replaced engines.
- Independent review round 1: BLOCK — CHECK validation could accept CASE pass-through semantics; immutable-trigger validation checked names rather than enabled/event/link/function-body contracts; raw URLs leaked in research CLI output; repeated search-path/default-port and split `.env` authority paths could collapse plane isolation.
- Fix round 1: exact bounded CHECK canonicalization; full PostgreSQL trigger catalog contract; credential-safe authority labels; effective-final single-schema parsing; default-port normalization; shared core/standalone Pydantic plane settings; and one resolver for research startup/routes/read APIs.
- Re-review round 2: BLOCK — immutable-trigger catalog validation omitted `pg_trigger.tgqual`, so an otherwise exact `WHEN(FALSE)` trigger suppressed every refusal.
- Fix round 2: catalog validation now requires `pg_get_expr(tgqual, tgrelid) IS NULL`; the live regression first proves the conditional trigger permits an UPDATE, then proves startup refuses it.
- Retained final review-fix evidence: live PostgreSQL 16 focused schema/profile gate `38 passed, 13 skipped` across 51 collected tests. Affected SQLite/live concurrency gate `238 passed, 13 skipped` across 251 collected tests. Startup/guard/nightly gate `37 passed`. Changed modules compile and `git diff --check` passes.
- Final re-review: SPEC PASS / QUALITY PASS. Fresh focused live PostgreSQL gate exited 0 with 38 passed and 13 deliberate skips.
- No broad suite was attempted for Task 3. See `task-3-report.md`.

## Remaining tasks

- Task 3: PostgreSQL research and ledger planes — complete; commit subject `feat(db): add PostgreSQL private planes`.
- Task 4: verified SQLite-to-PostgreSQL copy and cutover.
- Task 5: account leases, fencing, and replicated API ownership.
- Task 6: shared event delivery and transactional outbox.
- Task 7: backup/restore, failure recovery, and production concurrency/load proof.
