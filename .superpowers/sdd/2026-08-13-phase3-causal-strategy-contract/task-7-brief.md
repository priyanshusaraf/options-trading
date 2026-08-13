# Task 7 brief: research-plane immutable admission persistence

Implement Task 7 from
`paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against
starting commit `0b82cfc`.

Read the accepted Phase 3 design, full plan, progress ledger, V1 product-steer reconciliation, and
this brief completely. Preserve the four inherited protected files and their approved hashes.

Risk classification: **Critical**. A mutable, forged, or cross-owner research receipt could let a
finding or promotion claim causal authority for different strategy bytes.

Required outcome:

- Add research migration `0005`, make it the research head, and persist immutable owner-scoped
  `ResearchStrategyAdmission` receipts without importing execution-plane sessions or models.
- Implement `store_admission`, `load_admission`, and `require_admission` using the same canonical
  identity semantics proven in Task 6. Exact retries converge; conflicting bytes refuse.
- Add nullable, strict-format `admission_address` to experiment runs and promotion candidates.
  Existing rows remain null and explicit `LEGACY_UNADMITTED`.
- Database triggers must reject direct `UPDATE` and `DELETE` in SQLite and PostgreSQL while
  retaining byte-identical rows. PostgreSQL startup must validate the full trigger contract in the
  current research schema, including enabled state, exact events/timing, no `WHEN`, correct linked
  function, and SQLSTATE `55000`.
- Candidate/run binding must never cross owner or accept a candidate address different from its
  supporting run/receipt.
- Keep research and execution receipt stores physically and logically separate.

Concrete failure hypotheses:

1. Another owner can load or require a private research receipt.
2. Same owner/address can be replaced with different bytes or metadata.
3. Direct SQL can mutate/delete a receipt, or a same-name inert PostgreSQL trigger passes startup.
4. Migration `0005` has wrong table/columns/checks/head or diverges between fresh and upgraded
   SQLite/PostgreSQL schemas.
5. A promotion candidate can cite a receipt different from its run, owner, graph, or immutable
   research receipt.
6. Null legacy rows are treated as admitted or rewritten during migration.

Verification workflow:

1. Observe missing research store/head RED before production implementation.
2. Add no matrix without a named hypothesis above.
3. Run affected SQLite repository/migration tests while implementing.
4. At freeze, run the exact live PostgreSQL raw-mutation and current-schema contract in one unique
   research schema using the known local PostgreSQL 16 service.
5. Do not run broad backend or historical migration matrices; Task 12 owns the phase boundary.
6. Write `task-7-report.md`, update the ledger, and stop uncommitted/unstaged for independent
   review.
