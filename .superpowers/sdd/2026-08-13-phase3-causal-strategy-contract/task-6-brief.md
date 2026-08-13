# Task 6 brief: execution-plane immutable admission persistence

Implement Task 6 from
`paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against
starting commit `0ac276c`.

Read the accepted Phase 3 design, full plan, progress ledger, V1 product-steer reconciliation, and
this brief completely. Preserve the four inherited protected files and their approved hashes.

Risk classification: **Critical**. A forged, mutable, or cross-owner admission receipt could grant
later research, backtest, deployment, or execution authority to strategy bytes that were never
causally admitted.

Required outcome:

- Add execution-plane migration `0034`, make it the current head, and persist immutable
  owner-scoped `StrategyAdmission` receipts.
- Implement repository `put`, `get`, and `require_current`. Canonicalize and independently verify
  artifact identity before insert. Exact duplicate insertion is idempotent; same key with different
  bytes refuses.
- Enforce append-only receipt bytes in the database, not only the ORM: SQLite and PostgreSQL must
  reject direct `UPDATE` and `DELETE` while retaining byte-identical rows.
- Add nullable `String(71)` admission-address columns to every execution consumer listed in design
  section 9.1. Null remains `LEGACY_UNADMITTED`; this task does not invent or backfill receipts.
- Classify `strategy_admissions` as `USER`; keep existing consumer tables in their current planes.
- Keep admission proof distinct from complete Strategy Preflight. Do not add provider, point-in-time
  data, role binding, resource, or derivatives authority.

Concrete failure hypotheses:

1. A receipt can be read or required under another owner.
2. Same owner/address can be overwritten with different artifact bytes or metadata.
3. Direct SQL can update/delete a receipt in SQLite or PostgreSQL despite ORM guards.
4. A malformed or noncanonical artifact, or an artifact whose hash does not match its address, can
   be stored.
5. Migration `0034` has wrong head, columns, types, nullability, checks, triggers, or table-plane
   classification in one dialect.
6. Adding nullable consumer columns mutates legacy rows or incorrectly treats null as admitted.

Verification workflow:

1. Observe repository/schema RED before production implementation.
2. Add no matrix without a named hypothesis above.
3. Use affected SQLite tests while implementing; run current-head/schema/plane tests at freeze.
4. Use the configured live PostgreSQL URL for exact direct-SQL immutability and schema semantics.
5. Do not run broad backend or historical migration matrices; Task 12 owns the phase boundary.
6. Write `task-6-report.md`, update the ledger, and stop uncommitted/unstaged for independent
   review.
