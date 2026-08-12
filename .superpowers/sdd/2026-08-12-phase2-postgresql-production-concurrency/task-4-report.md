# Phase 2 Task 4 implementation report

Date: 2026-08-13

Status: implementation and bounded verification complete; uncommitted and stopped for independent review.

## Delivered

- `app/db/copy_contract.py` owns an offline, fail-closed three-plane copy contract. Sources are
  explicit, absolute, pairwise-distinct SQLite files opened with URI `mode=ro`, `query_only=ON`
  and foreign keys enabled. The normal source engine hooks and all migrations are bypassed.
- Source inventory is exact: execution metadata plus `alembic_version`; research metadata plus
  its SQLite `(version,schema_cookie)` marker; markerless ledger metadata only. Unknown proof,
  temp, interrupted rebuild or leftover copy tables refuse.
- Sources must match current heads/contracts. Execution requires Alembic `0031`; research requires
  `0003` plus its live schema cookie; ledger reports `unversioned/current-model-validated`.
  Read-only reflection checks columns, PKs, FKs, unique/check constraints and indexes.
- Destinations must be explicit, pairwise-separated PostgreSQL authorities and entirely empty.
  The existing current-schema initializers create, validate and stamp them. Execution uses the
  no-seed `init_schema` path, not `session.init_db`.
- Metadata dependency order drives bounded `fetchmany`/executemany batches. PK order and metadata
  column order define typed SHA-256 digests. Raw JSON text and bytes stay unchanged; floats use
  exact IEEE hexadecimal form; invalid loose values and non-finite floats refuse.
- Every single-integer generated PK sequence is discovered with `pg_get_serial_sequence`, repaired,
  reported, and independently verified so its next value exceeds the copied maximum.
- Verification covers exact counts, PK sets, typed row/table digests, owner/account partition
  counts, PostgreSQL constraints, semantic account ownership, credential ciphertext/key-id pairing
  and configured-key readiness, and selected public computation, graph/review and research-spec
  content addresses.
- Source stability uses a held read transaction, start/end `data_version`, database/WAL identity,
  size/mtime and SHA-256 evidence. A concurrent commit rolls back the active destination plane.
- The deterministic canonical JSON report contains build/tool versions, UTC bounds, redacted
  source/destination identities, separate source/destination heads, workload/batch sizes, summaries,
  sequence evidence and a final SHA-256 content address. It excludes URLs, identifiers, tokens,
  ciphertext, artifact bytes and raw secrets. The CLI publishes success atomically and never writes
  a success report after refusal.
- `docs/operations/postgresql-cutover.md` documents freeze, backups, rehearsal, destination creation,
  report verification, activation/adversarial tenant checks, quarantine after a partial multi-plane
  run, rollback-by-URL and the prohibition on automatic reverse copy.

## Independent review round 1

Review blocked on three reproduced defects. Each received a behavioral RED before its fix:

1. A non-null SQL `Date` called `date.isoformat(timespec=...)` and raised `TypeError`. Date and
   DateTime now have separate canonical encodings; the live fixture copies a non-null
   `deployments.halted_on` value.
2. FK-valid cross-tenant links could pass when the FK named only a scalar local identifier. Exact
   REDs covered an `org-a/account-a` execution intent pointing at an `org-b/account-b` deployment
   and an org-a OAuth callback linked to org-b session/connection rows. The verifier now applies a
   bounded declarative semantic graph: broker account ownership, shared scope agreement on every
   execution-plane FK, explicit connection-scope/OAuth links, and active-session membership state.
3. A later SQLite source could change after all-plane preflight but before its turn and become the
   accepted per-plane baseline. The copy now captures DB/WAL stat+hash evidence for all sources
   immediately after outer preflight and verifies each expected snapshot before initializing that
   plane's destination. A live later-plane mutation RED now refuses before destination initialization.

Destination redaction also stopped hashing credentials or secret query values. It hashes only the
credential-free physical authority and explicit application schema identity; two URLs that differ
only by username/password/`sslpassword` now produce the same report identity.

## Independent review round 2

Review reproduced three further gaps before the fixes:

1. Source 1 could change immediately after its `_copy_one` returned while source 2 copied, and the
   tool still emitted `cutover_ready`. The tool now rechecks every source against the all-plane
   freeze snapshot after every sequential copy and before report construction. Any drift refuses;
   already committed destinations are explicitly quarantined.
2. An execution intent could name the right broker-account row while carrying a different
   `account_scope`. The semantic graph now requires intent owner, account, broker and
   `account_scope == broker_accounts.external_account_id`. The populated fixture uses the actual
   external account identity, and a `WRONG-EXTERNAL-ACCOUNT` RED proves refusal.
3. A position or trade could share owner/account with an intent but cross deployments. The shared
   semantic scope now includes `deployment_id` and `broker`. A focused position RED proves a
   same-owner/same-account cross-deployment intent link refuses. The adjacent load-bearing links
   remain covered: order journal/deployment, deployment/account, intent/deployment/account/
   connection, and execution event/intent.

## Independent review round 3

The final bounded authority audit added four concrete relations, each with a behavioral RED before
the fix:

1. After all plane copies, every ledger owner/account identity must exist in execution
   `broker_accounts`, and every research owner must exist in execution `organizations`. The copy
   and independent verifier now stream hashed identity sets from all three destinations and refuse
   missing cross-plane authorities. This check runs before the final all-source freeze check and
   report construction.
2. Paper and shadow IR deployments must resolve to a `graph_versions` row with the same owner,
   graph identifier, version and content address. Mismatched or absent graph authority refuses.
3. Non-null `deployments.watchlist_id` must resolve to a same-owner watchlist.
4. Non-null `strategy_lifecycle.deployed_watchlist_id` must resolve to a same-owner watchlist.

The research cross-plane mutation regression uses an unreferenced research-program probe so the
cross-plane validator, rather than a child-table foreign key, is the component under test.

## TDD and mutation evidence

The first RED was:

```text
tests/test_database_copy_contract.py::test_copy_refuses_a_missing_sqlite_source...
ModuleNotFoundError: No module named 'app.db.copy_contract'
```

The focused live test then exposed and fixed a false source-mutation refusal caused by reader-owned
SQLite `-shm` mtime changes. The final six-case copy gate passed against PostgreSQL 16. It covers:

- missing source before any destination open;
- dedicated read-only source and unknown/temp-table refusal;
- report content-address mutation;
- preflight before destination initialization;
- a 57-row, two-tenant copy with active/revoked sessions and OAuth states, two encrypted broker connections and
  accounts, capital, deployments, execution intents/immutable order events, research programs,
  hypotheses, immutable specs/trials, runs, durable operation items/events, completed/cancelled
  backtest runs/results, public computation evidence, graph versions, review snapshots, ledger
  snapshots, binary artifacts and claimed/unclaimed manual fills;
- same local identifiers across owners where composite identity permits;
- digest mutation, omitted report table, semantic owner/account mismatch, credential-pair damage,
  sequence skew/restore, complete verifier pass and second-invocation refusal;
- a concurrent SQLite writer commit after snapshot acquisition, with refusal and destination
  transaction rollback.

Command and result:

```text
PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test \
  .venv/bin/python -m pytest tests/test_database_copy_contract.py -q
19 passed in 8.43s
```

## Focused verification

The bounded schema/profile/tenant gate ran against unique PostgreSQL 16 schemas:

```text
PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test \
  .venv/bin/python -m pytest \
  tests/test_database_copy_contract.py tests/test_plane_database_profiles.py \
  tests/test_postgres_plane_schemas.py tests/test_postgres_execution_schema.py \
  tests/test_research_tenant_isolation.py tests/ledger/test_tenant_scope.py \
  tests/test_money_repository_isolation.py
149 passed, 13 skipped in 16.18s
```

The skips are the existing wrong-plane parametrization and one frozen historical research contract.
Changed Python modules compiled successfully. `git diff --check` passed with no output. No broad
suite was attempted.

## Changed paths

- `paper-trader/backend/app/db/copy_contract.py`
- `paper-trader/backend/scripts/copy_sqlite_to_postgres.py`
- `paper-trader/backend/tests/test_database_copy_contract.py`
- `paper-trader/docs/operations/postgresql-cutover.md`
- `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/progress.md`
- `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/task-4-report.md`

## Limits and operational boundary

Independent PostgreSQL destinations cannot commit atomically as one transaction. A later-plane
failure quarantines all destinations from that run; operators must recreate them and rerun. No URL
switch is valid until one final all-plane report verifies. This task does not implement online
dual-write, CDC, reverse copy or production activation. PostgreSQL is production-ready only after
the documented real restore/copy rehearsal succeeds.

## Protected inherited files

The task did not edit or stage the four inherited files. Hashes remain:

- `app/engine/kite_venue.py`: `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
- `app/engine/venue.py`: `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
- `app/providers/brokers.py`: `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
- `tests/test_broker_registry.py`: `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`

Nothing is staged or committed.
