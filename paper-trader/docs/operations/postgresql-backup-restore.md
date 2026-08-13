# PostgreSQL backup, restore, and disaster recovery

This runbook covers a coordinated logical backup of the execution, research, and ledger planes.
It proves a clean PostgreSQL 16 restore. It does not prove managed PITR, geographic durability,
off-account retention, production RPO/RTO, or broker-side fencing.

## Preconditions and authority boundary

All three source URLs must name PostgreSQL and one explicit private `search_path`. Use separate
databases in production. The local proof may share a PostgreSQL server, but the restore target must
be a new physical database. The verifier refuses a target with the source physical authority.

The source databases are independently writable. A coherent generation therefore needs one
maintenance window:

1. Reject API mutations and retain the maintenance evidence address.
2. Stop schedulers from claiming new work. Drain or release backtest and research claims.
3. Stop outbox dispatchers after recording each durable cursor.
4. Disarm execution accounts. Resolve or block broker ambiguity, stop the cells, and release their
   leases. Record the last epoch and command states.
5. Keep all writers stopped until all three dump artifacts finish.

Do not treat three dumps taken while writers continue as one generation.

## Local PostgreSQL 16 backup

Set `PT_DATABASE_URL`, `PT_RESEARCH_DATABASE_URL`, and `PT_LEDGER_DATABASE_URL` through a secret
store. The command reads them from the environment and never places a password-bearing URL in its
argument list. When a URL carries a password, the helper creates a mode-0600 temporary pgpass file
and removes it after the child process exits.

Prepare a small JSON maintenance evidence file:

```json
{"quiesced":true,"evidence_address":"sha256:<64-lowercase-hex>"}
```

Run:

```bash
python scripts/postgresql_backup_restore.py backup \
  --generation restore-20260813-a \
  --directory /var/lib/strategy-os/backups \
  --maintenance-evidence /run/strategy-os/maintenance.json \
  --pg-dump /usr/lib/postgresql/16/bin/pg_dump
```

The output directory contains three custom-format dumps and `manifest.json`. The manifest binds
schema heads, complete table inventories, ordered typed-row and primary-key digests, owner/account
partitions, authentication/session state, execution leases and command journals, jobs, outbox
cursors/receipts, content addresses, sequence high-water evidence, artifact SHA-256 values and
cross-plane identities. It contains no URL, token, password, ciphertext, raw row, or artifact byte.

Set `PT_RESTORE_SIGNING_KEY` to produce an HMAC-signed operator manifest. An unsigned local manifest
is labelled `unsigned-development` and cannot satisfy `--require-signed`.

## Clean restore and verifier gate

Create a new physical PostgreSQL database with the same three plane schema names. Give the restore
identity no application or broker credentials. Set `RESTORE_PT_DATABASE_URL`,
`RESTORE_PT_RESEARCH_DATABASE_URL`, and `RESTORE_PT_LEDGER_DATABASE_URL` to that database and its
explicit schemas.

```bash
python scripts/postgresql_backup_restore.py restore \
  --manifest /var/lib/strategy-os/backups/restore-20260813-a/manifest.json \
  --output /var/lib/strategy-os/evidence/restore-20260813-a.json \
  --pg-restore /usr/lib/postgresql/16/bin/pg_restore \
  --require-signed
```

The tool validates the closed manifest schema, content address, signature and artifact inventory
before opening a target or running `pg_restore`. It then requires fresh targets, restores the three
schema-qualified dumps, and runs independent current-head, trigger, typed digest, relational,
content-address, sequence and cross-plane verification. No application starts until the atomic
report has `cutover_ready=true`.

## Authority switch and service order

1. Isolate the old primary at the network and database authority layers. Broker HTTP cannot be
   recalled after an old current epoch sent it.
2. Bind the deployment to `PT_RESTORE_SAFETY_STATE=verified`, the retained
   `PT_RESTORE_GENERATION_ID`, `PT_RESTORE_VERIFICATION_ADDRESS`, and
   `PT_RESTORE_OLD_PRIMARY_ISOLATED=1`.
3. Start API-only replicas. Check durable reads and controls.
4. Start outbox and job consumers. They resume from durable cursors and expired claims.
5. Start one execution holder per account. Restore boot takes the existing lease row at a strictly
   higher epoch and remains `recovering` and disabled.
6. Reconcile prepared, sent-unknown and acknowledged commands, working lifecycle records, broker
   orders, positions and protective inventory. Preserve known protection. Block ambiguity.
7. Activate each account explicitly after evidence is complete. Observe before ending maintenance.

An old token cannot heartbeat, transition a command, or commit money/evidence after the new epoch.
The new holder may make reviewed risk-reduction calls for verified bot-owned quantities. Database
fencing does not fence a broker HTTP request that was already sent.

## Failure drills

For each release, retain timings and results for:

- execution crash after PREPARED, after send, after broker acknowledgement, and before evidence;
- late old response, heartbeat loss, read outage, protective ambiguity, and old-primary return;
- job death after claim, during work, and after durable result before acknowledgement;
- event death before delivery, after local effect before cursor acknowledgement, listener outage,
  duplicate delivery, and retention gap with scoped resync;
- removal of an API nonholder and the current execution holder.

Use deterministic fake brokers. Never send real orders during a drill.

## Rollback

Switch authority back only when the restored target accepted no writes or broker effects. If either
occurred, stop both sides and follow incident reconciliation. Never reverse-copy production writes
automatically.

## Managed PITR capability

Managed PITR stays `UNPROVEN` until a retained rehearsal records provider/cluster identity,
immutable encrypted backup generation, WAL range, target timestamp, before/after durable markers,
restore logs, verifier report, measured RPO/RTO, off-account retention and old-primary isolation.
A local logical restore does not satisfy that claim.
