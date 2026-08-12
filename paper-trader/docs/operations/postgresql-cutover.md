# PostgreSQL cutover from SQLite

PostgreSQL becomes authoritative only after a completed rehearsal and a fresh copy report whose
content address verifies. Keep the three SQLite files and their backups unchanged until the
rollback window closes.

## Prerequisites

- Rehearse this procedure against a restored copy of production. A code-only or empty-database
  test does not make PostgreSQL production-ready.
- Install PostgreSQL 16 or newer, the application build being deployed, and its exact migration
  head. Provision three empty databases or three explicit, non-overlapping schemas.
- Set `PT_CREDENTIAL_KEY` to the key used by encrypted `broker_connections` rows. The copy checks
  key fingerprints without decrypting or reporting credentials.
- Record backup locations, restore commands, operator names, maintenance start, application build,
  and the expected execution/research/ledger source paths.

## Freeze and copy

1. Stop API, worker, scheduler, research, ledger and broker processes. Confirm that no process can
   write any SQLite plane. This tool is offline: separate files cannot provide one atomic
   cross-plane snapshot.
2. Take recoverable copies of the database files plus any live `-wal` files. Record SHA-256 hashes.
3. Create fresh empty PostgreSQL destinations. Do not reuse a failed or partially copied schema.
4. From `paper-trader/backend`, run:

   ```bash
   .venv/bin/python scripts/copy_sqlite_to_postgres.py \
     --execution-source /absolute/frozen/paper_trader.db \
     --execution-destination "$NEW_PT_DATABASE_URL" \
     --research-source /absolute/frozen/research.db \
     --research-destination "$NEW_PT_RESEARCH_DATABASE_URL" \
     --ledger-source /absolute/frozen/ledger.db \
     --ledger-destination "$NEW_PT_LEDGER_DATABASE_URL" \
     --batch-size 500 \
     --report /absolute/secure/cutover-report.json
   ```

5. Require exit zero and one report with `cutover_ready: true`. Independently verify its
   `content_address`, all three schema heads, complete table inventory, row/PK/digest summaries,
   partition counts, relationship checks, source stability, credential-key readiness and every
   sequence result. The report contains redacted authorities and summaries, never credentials,
   bearer plaintext, ciphertext, artifact bytes or raw identifiers.

A failed later plane or a source-stability failure found by the final all-plane recheck can leave an
earlier plane committed. Treat every destination from that run as quarantined and non-cutover-ready.
Clear by dropping and recreating the exact test-owned schemas, then repeat from step 3. There is no
in-place resume and no success report is valid before that final source recheck.

## Activate and challenge

1. Set `PT_DATABASE_URL`, `PT_RESEARCH_DATABASE_URL` and `PT_LEDGER_DATABASE_URL` to the verified
   destinations in one controlled configuration change. Keep the old SQLite paths recorded but
   inactive.
2. Start one API instance with workers still stopped. Require schema/current-head health and no
   initialization or adoption warning.
3. Test active and revoked sessions. For both copied tenants, verify own-project, own-research,
   own-account, own-capital and own-ledger reads. Challenge each endpoint with the other tenant's
   identifiers and an absent identifier; both must refuse or return not found without disclosure.
4. Verify both broker accounts and credential readiness without placing an order. Then start one
   worker and scheduler. Confirm pending/running/completed/cancelled jobs and research operations,
   immutable evidence reads, ledger artifact retrieval, and manual-fill claims.
5. Perform one explicitly approved low-risk write per plane and confirm generated integer keys do
   not collide. Record health output and the report content address in the change record.

## Rollback

Stop all PostgreSQL-backed processes. Restore the three service URLs to the frozen SQLite
authorities and start the previous application build. PostgreSQL writes made after activation are
not copied back automatically. Decide separately whether they are disposable, require manual
reconciliation, or require an audited forward repair. Never reverse-copy a partially written
PostgreSQL database into SQLite.

Keep the failed PostgreSQL destinations quarantined for investigation. The original backups and
their hashes are the rollback evidence.
