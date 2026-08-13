# Task 7 report: PostgreSQL restore, disaster recovery, and workload proof

## Status

Task 7 is committed at `30acb45` (`test(operations): prove PostgreSQL restore readiness`). The
separate final Phase 2 closure diff remains frozen uncommitted for independent review.

The local PostgreSQL 16 logical restore contract is implemented and exercised against a clean new
physical database. Managed PITR, geographic failover, encrypted off-account retention, production
RPO/RTO, production capacity, universal cost and broker-side fencing are not proven.

## Backup and restore contract

`app/db/restore_contract.py` is PostgreSQL-to-PostgreSQL. It does not call Task 4's
`verify_planes()`. Task 4 now exports pure typed row, streamed table, semantic ownership,
content-address, constraint, sequence and identity-set helpers. The copy contract remains
SQLite-to-PostgreSQL.

The manifest binds one quiesced generation and all three planes. It records redacted logical and
physical authority hashes, schema heads, full inventories, ordered PK and typed-row digests,
owner/account partitions, auth/session state, execution lease and command state, jobs, outbox
cursors/receipts, content-address sets, sequence evidence, artifact digests and cross-plane owner
identities. Closed-schema validation rejects unknown fields, missing or mixed generations, unsafe
URL/secret-shaped fields and incomplete inventories. Canonical SHA-256 and an operator HMAC signing
interface protect the whole body. Unsigned output is labelled `unsigned-development`.

The restore CLI verifies the closed schema, content address and signature before resolving a target
or running `pg_restore`. It verifies each artifact digest, requires a fresh explicit-schema target,
restores custom-format artifacts, and runs an independent read-only verifier. The verifier refuses
source/target logical or physical authority overlap, wrong head, unknown table, digest/PK/content
mutation, unsafe sequence, relational/tenant break or cross-plane identity break. It produces one
atomic redacted report with `cutover_ready=true` only after every plane and cross-plane check.

## Local PostgreSQL evidence

- PostgreSQL client tools: local `pg_dump` and `pg_restore` 16.14.1.
- Live source capture fixture: two organizations, two broker accounts, active and revoked sessions,
  two capital books, research programs, ledger snapshots, and execution/research/ledger outbox
  events. Current manifest covered 53 execution, 18 research and 8 ledger payload tables.
- Live clean restore: source and target were UUID-bound independent databases. Three schema-qualified
  custom dumps restored to the same plane schema names in the fresh target. Current head/trigger,
  typed digest, sequence and cross-plane checks passed. The test destroys only its UUID-bound
  databases after terminating their sessions.
- Focused live command:
  `PT_TEST_POSTGRES_URL=postgresql+psycopg://... .venv/bin/python -m pytest tests/test_postgresql_restore_live.py -q`
  returned `1 passed`.

The source fixture and clean restore use fake/domain data only. They do not contact a broker.

## Execution, jobs, events, and replicas

Verified restore boot is deployment-gated by a generation id, verifier report content address and
explicit old-primary isolation. `app.main.lifespan` routes a worker through
`claim_restored_execution_lease`, never the normal claim path. That helper enters the existing Task
5 row lock, increments the historical epoch, leaves the account `recovering` and disabled, records
the restore evidence in lease history, re-fences pending controls and makes the old token stale.
Normal reconciliation still controls activation. Broker HTTP is not fenced after release from an
old current epoch.

Existing Task 5 and Task 6 reviewed mechanisms remain the recovery authority:

- stale execution tokens cannot heartbeat, transition commands or commit bound money/evidence;
- replacement job claims only expired work, stale tokens cannot publish/finish, and durable cell
  identities prevent duplicate results;
- polling catches committed outbox work after notification loss, effect-before-ack is idempotently
  retried, cursor claims fence replacement consumers, retention gaps force scoped resync, and resume
  cursors bind owner/account;
- API-only replicas read durable execution status and accept durable controls without constructing a
  broker.

Focused combined recovery gate returned `59 passed` across Task 7 contracts plus existing job and
event delivery suites. Full process-death timing and production service-removal rehearsals remain an
operator environment exercise; this report does not invent those durations.

## Workload evidence

The reusable vectors are `ci`, `validation-500`, and `execution-50-soak`. They are validation points,
not product caps. CLI overrides every dimension within high operator safety bounds.

Retained local reports:

- `evidence/task-7/ci-contract-seed17.json`: 64 attempted/completed, 0 failed/rejected;
- `evidence/task-7/validation-500-seed17.json`: 2,000 attempted/completed, 0 failed/rejected;
- `evidence/task-7/execution-50-soak-seed17.json`: 1,500 attempted/completed, 0 failed/rejected.

These in-process contract runs measure real wall-clock latency/throughput, errors, admission
rejections, RSS, bounded queue state, WebSocket bytes and fanout serialization. They do not exercise
real HTTP replicas, PostgreSQL pools or broker cells. Pool/lock waits, WAL/backup quantities,
recovery timing and dated cloud cost inputs are `UNMEASURED`, so every retained report correctly has
`production_capacity_claim_ready=false`. No zero substitutes for an unavailable metric.

## CI and operations

`.github/workflows/strategy-os-ci.yml` adds PostgreSQL 16 with non-production test credentials. It
runs the live logical restore, manifest/tool contracts, core execution lease/outbox/job SQL gates,
and the deterministic small workload twice. Long tiers and managed PITR stay outside pull-request
timing gates.

Runbooks:

- `docs/operations/postgresql-backup-restore.md`
- `docs/operations/phase2-capacity-rehearsal.md`

They define maintenance/quiescence, credential handling, restore identity, verifier-before-start,
old-primary isolation, API/outbox/job/execution startup order, explicit account reconciliation,
rollback refusal after new effects, PITR evidence, failure drills and capacity measurement gaps.

## RED/GREEN evidence

Initial focused RED failed collection for exactly the absent restore contract, load contract and
restore takeover seams. The backup-tool test independently reddened for its absent module. The
direct load CLI then exposed an actual `sys.path` launch defect; all three retained runs failed until
the wrapper inserted the backend root. The invalid-manifest spy proves schema/signature refusal
causes zero target resolution and zero restore calls.

Final focused Task 7 helper/preflight/boot/recovery/load gate: `22 passed`. Final live PostgreSQL 16
three-plane restore: `1 passed`. Final combined restore/lease/outbox/job gate: `59 passed`.

## Nonclaims

- Managed PITR: `UNPROVEN`.
- Geographic failover and off-account durability: `UNPROVEN`.
- Production RPO/RTO and recovery durations: `UNMEASURED`.
- Production workload/cost approval: `UNMEASURED` and not ready.
- Broker-side fencing: not provided.
- `validation-500` and `execution-50-soak`: validation points, not limits.

## Changed files

Task 7 adds the restore, backup, load, DR, tests, CI and runbook files shown by the final staged diff.
It also updates `app/core/config.py`, `app/main.py`, `app/execution/leases.py` and exports pure Task 4
integrity helpers from `app/db/copy_contract.py`.

Protected inherited files remain unstaged and byte-identical to their required hashes:

- `kite_venue.py`: `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
- `venue.py`: `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
- `brokers.py`: `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
- `test_broker_registry.py`: `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`
