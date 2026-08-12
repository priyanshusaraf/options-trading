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
- A broad `tests research_tests` run reached 96%, but its final exit status was not retained. It is explicitly inconclusive and is not reported as passing.

## Remaining tasks

- Task 3: PostgreSQL research and ledger planes.
- Task 4: verified SQLite-to-PostgreSQL copy and cutover.
- Task 5: account leases, fencing, and replicated API ownership.
- Task 6: shared event delivery and transactional outbox.
- Task 7: backup/restore, failure recovery, and production concurrency/load proof.
