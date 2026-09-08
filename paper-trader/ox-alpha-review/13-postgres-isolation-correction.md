# 13 — PostgreSQL Isolation & False-Green Correction Capsule

**Status:** ACTIVE — bounded correction authorized by owner directive (2026-08-22).
**Preserved evidence:** failed gate report copied to `.agent/runs/2026-08-22-postgres-isolation-correction/gate-report-failed.json`, sha256 `54b5c6c6b4ace5991767a7df0de563152ab4ddad6ca5becd5da2eaea6e09d5fb` (`gate-report-failed.sha256`). Gate verdict: `status = failed`, PG available and required, 103 commands completed, 5 command groups failed affecting 9 tests.

## Owner-accepted starting facts

1. Seven tests received PostgreSQL state left by another test (shared-cluster pollution across pytest processes).
2. One supposed PostgreSQL 0007 fixture uses present-day metadata with an old version marker (dishonest history).
3. One Phase 4 test expects execution head `0036`; current head is `0039`.
4. Known false greens: E1 cross-owner probe (runner swap makes it vacuous), G5 survivorship (total never read from stored run), B5 (single-process double-acquire is not a process-boundary proof), orphan callables hidden behind exception list, plane classification accepted without loss-review, C13 exclusion lacks the promised import-direction check, native-state projection contract hides behind one module-level skip.

## Allowed paths

- `tests/**`, `research_tests/**` — PG isolation migration, false-green rewrites, new shared sandbox module.
- `tests/conftest.py`, `research_tests/conftest.py` — sandbox fixture registration only.
- `app/db/planes.py` + its completeness test — plane reclassification strictly per the loss-review definition.
- Orphan callables' defining files — removal only if obsolete (owner-listed remedy); otherwise explicit nonclaim.
- `paper-trader/ox-alpha-review/*.md` — evidence docs; append-only for prior claims.
- `.agent/runs/2026-08-22-postgres-isolation-correction/**` — evidence.
- Product correction ONLY inside `research/domain/migrate.py` (or the single owning migration file) IF a genuine isolated historical fixture reproduces a trigger-idempotency defect, with the smallest possible diff.

## Forbidden (hard stops)

Phase 5 work · Recovery 9 verdicts · signing the migration-support decision · deploy/production/credentials/broker/live/arm/money · frontend code · stash/reset/clean/revert/overwrite of inherited work · commit/push/merge · hand-editing generated reports · converting required PG cases into skips or allowlisted failures.

## Evidence requirements

- Exact commands + exit codes in `devops-log.md` for every run.
- The nine tests proven: alone, grouped, reordered, repeated twice against one server with fresh sandboxes.
- Focused mutation checks that can go red, for every new guard (sandbox emptiness check, C13 direction check, E1 ownership vectors, G5 total tamper).
- Official gate PASS accepted only when: process exit 0 AND generated report says `status = passed`, PG available and required, no incomplete required command, no nonzero command exit, required PG cases ran (not skipped).

## Stopping conditions

1. A remaining test requires the PostgreSQL migration-matrix support policy → STOP, present exactly two options (support via genuine fixture + tested upgrade, or loud non-destructive refusal) and wait for owner.
2. One material failure survives initial correction plus one consolidated repair → STOP, replan; no recursive recovery chain.
3. Any fix requires a forbidden surface → STOP, report.

## Non-negotiable design rule

Isolation by unique per-test namespace (random names, verified-empty start, `finally` cleanup that runs on failure). No fixed database names. No broad cleanup that can touch another test's namespace. No teaching the product to accept mixed-plane databases.
