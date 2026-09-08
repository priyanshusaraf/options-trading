# 09 — Owner Decision Record: Supported Research-Migration Contract

**Status:** PROPOSED by ox-alpha, 2026-08-21 — requires owner sign-off per the foundation
audit's own off-ramp ("The owner must either prove an independently projected supported old
database or explicitly narrow the supported contract with safe operational handling").

## Context

A-01 (Critical) is **closed in product code** as of this session: the seeded genuine-0005
SQLite upgrade now reaches 0010 with the exact canonical trigger contract
(`research_tests/test_foundation_a01_migration_upgrade.py`, mutation-proven). What remains
open is the **evidence question** A-03/A-04: proving populated-old upgrades for every
historical prefix without hybrid fixtures.

## The decision requested

Adopt this supported-migration contract for the research plane (and mirror it in the
execution plane's migration docs):

1. **Fresh install** at current head — supported, tested (existing `test_empty_sqlite_upgrade…`).
2. **Forward upgrade** from the immediately preceding head (N−1 → N) — supported, tested by
   replaying migrations forward from empty through N−1 (this IS genuine history for catalog
   objects), seeded with the state-contract corpus (immutable catalog authority +
   parameterized contract-valid user rows + deterministic witnesses — already designed in
   `phase1-4-foundation-research-migration-native-state-contract-core`).
3. **Multi-stage forward upgrade** (0005 → head) — supported on the demonstrated path
   (this session's regression), extended prefix-by-prefix as the fixture machinery lands.
4. **Anything older, or a database that fails its declared prefix validation** — **not
   migrated. Restore-based instead**: refuse loudly with the exact validator reason, and
   direct the operator to restore from backup + re-attach. Never silently reinterpret.

## Why narrowing is safe here

- The runner already refuses anything that is not an exact declared prefix — the contract
  only *names* what the code already enforces.
- The live production research DB is at head; no production database sits on an unsupported
  prefix. (Verified claim scope: this branch's docs; the VPS state remains owner-verified.)
- The audit explicitly offered this route as the alternative to proving an unbounded
  historical universe — the universe that produced nine rejected harness recoveries.

## What this unlocks

With 1–4 adopted, the remaining A-04 reds (the seven `_make_populated_0007`-family tests)
are reclassified from "blocking defects" to **owned fixture-repair work inside the
forward-replay harness capsule**, and Phase 5's gate condition (foundation closure) can be
satisfied on the narrowed contract with an independent re-audit recheck.
