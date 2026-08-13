# Task 7 report: research-plane immutable admission persistence

Risk classification: **Critical**. A mutable, forged, or cross-owner research receipt could let a
finding or promotion claim causal authority for different strategy bytes.

## Scope delivered

- Added research migration `0005` and made it the research schema head.
- Added `ResearchStrategyAdmission` and a research-local repository with `store_admission`,
  `load_admission`, `require_admission`, and `require_candidate_admission`. It canonicalizes receipt
  bytes, re-derives the address, and refuses any mismatch or conflicting retry.
- Kept research receipts physically and logically separate from execution persistence. The repository
  uses research models only and imports no execution session or execution receipt model.
- Added nullable, strict-format `admission_address` columns to experiment runs and promotion
  candidates. Null remains explicit `LEGACY_UNADMITTED`; migration never creates proof for old rows.
- Added SQLite and PostgreSQL append-only database triggers. The research receipt PostgreSQL trigger
  raises SQLSTATE `55000`; startup validates exact enabled state, timing/events, no `WHEN`, linked
  function, and function body.
- Candidate admission requires one owner, an existing same-owner run, identical candidate/run
  addresses, and a matching owner-local receipt. The receipt is returned as the verified evidence.
- Preserved historical migration preflight. A real 0004 schema is validated before migration 0005;
  marker-rewind recovery accepts only the exact already-known 0005 additive receipt state, never
  arbitrary extra columns or triggers.

Causal admission remains proof of Phase 3 causality only. It does not create complete Strategy
Preflight, point-in-time market truth, provider capability, role binding, resource planning, or
execution authority.

## RED/GREEN evidence

Observed RED before production implementation:

```text
research_tests/test_strategy_admissions.py collection failed:
ModuleNotFoundError: No module named 'research.domain.admissions'
```

The first focused green run then exposed a real current-schema defect: research migration check
validation attempted to stringify custom SQL expressions without the active dialect. The validator
now compiles those checks with the active dialect; this preserves exact comparison rather than
loosening the contract.

Focused SQLite/recovery boundary:

```text
./.venv/bin/python -m pytest -q \
  research_tests/test_operation_migration.py \
  research_tests/test_operation_migration_recovery.py \
  research_tests/test_strategy_admissions.py \
  research_tests/test_models.py \
  research_tests/test_postgres_operation_concurrency.py \
  tests/test_outbox_plane_models.py
39 passed, 1 skipped
```

The checks cover owner isolation, exact duplicate/retry, same-key conflicting bytes, forged
addresses, SQLite direct SQL UPDATE/DELETE retention, run/candidate/owner binding, malformed
consumer addresses, fresh head `0005`, actual `0004 -> 0005` null preservation, historical
recovery preflight, and same-name inert PostgreSQL trigger catalog forms.

Live local PostgreSQL 16 proof:

```text
PT_TEST_POSTGRES_URL=<local PostgreSQL 16 URL> \
  ./.venv/bin/python -m pytest -q \
  research_tests/test_postgres_operation_concurrency.py \
  research_tests/test_strategy_admissions.py
15 passed
```

The live receipt test uses a unique schema, validates the current schema trigger catalog, stores a
receipt through the repository, issues raw SQL UPDATE and DELETE, observes SQLSTATE `55000` for
each, rolls each transaction back, and reads the same artifact bytes afterward. The unique schema
is removed in cleanup.

`tests/test_outbox_plane_models.py` also updates its stale schema-head assertions from execution
`0033` to `0034` and research `0004` to `0005`. This is Task 6/Task 7 schema-head compatibility,
not a new execution behavior change.

## Freeze checks

- `python -m py_compile` passed for the new repository, model, migration runner, migration, and
  focused tests.
- `git diff --check` passed.
- Protected inherited SHA-256 values match their approved baseline.
- Independent final review returned **SPEC PASS / QUALITY PASS** with no remaining Critical
  finding. No files are staged and no commit has been created.
