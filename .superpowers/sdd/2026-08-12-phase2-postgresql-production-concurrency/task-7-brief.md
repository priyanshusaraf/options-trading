### Task 7: PostgreSQL restore, disaster recovery, and measured workload proof

**Base commit:** the reviewed Task 6 outbox/event-delivery commit; resolve and record its exact SHA
before implementation.

**Primary artifacts:**

- Create a PostgreSQL-to-PostgreSQL backup/restore verifier which reuses Task 4's typed digest,
  relational, content-address and cross-plane ownership primitives without pretending SQLite copy
  verification is backup verification.
- Add local PostgreSQL 16 logical-backup/clean-restore automation and operator runbooks for backup,
  restore, old-primary isolation, execution-cell recovery and managed PITR rehearsal.
- Add failure drills for account leases, broker ambiguity, backtest/research jobs, outbox consumers,
  API replicas and scoped WebSocket catch-up.
- Add a bounded workload harness with explicit workload vectors and real latency, contention,
  memory, delivery, recovery and cost measurements.
- Add a PostgreSQL CI service gate for the fast restore/concurrency contracts. Keep managed backup,
  PITR and production failover claims capability-gated and evidence-driven.

**Produces:** a clean PostgreSQL restore can be proven to contain the same three-plane tenant,
money, authentication, execution, research, ledger and content identities as one quiesced backup
generation; service failures recover through existing fences/cursors rather than duplicates; and
capacity is reported by workload vector rather than a product/user ceiling.

#### Truthful capability boundary

- Task 4 proves a read-only SQLite-to-PostgreSQL cutover. Do not call or wrap `verify_planes()` as
  a PostgreSQL backup verifier; it requires SQLite sources and answers a different question.
- Local PostgreSQL 16 may prove `pg_dump`/`pg_restore` into brand-new isolated schemas/databases,
  current-schema validation, typed digests, sequence safety and application recovery.
- The current development Compose service has no WAL archive or managed immutable backup store.
  It cannot prove PITR, geographic durability, encrypted off-account retention or production RPO.
- A managed-production PITR claim requires an actual rehearsal artifact: provider/cluster identity,
  immutable encrypted backup generation, WAL/archive range, target timestamp, before/after marker,
  restore logs, verifier result, measured RPO/RTO and old-primary isolation. If unavailable, report
  `UNPROVEN`, never green or inferred from a logical restore.
- Independently writable execution/research/ledger databases have no atomic cross-plane snapshot.
  A coherent generation requires a documented maintenance window that quiesces API mutations,
  execution cells, job workers/schedulers and outbox dispatchers before each plane backup, records
  generation identity, and keeps them quiesced until all plane artifacts finish. Do not claim
  otherwise without one physical database snapshot or coordinated snapshot support.
- Restoration never starts an application, worker or execution cell against a target until the
  full independent and cross-plane verifier returns cutover-ready.

#### Restore manifest and verifier

Create `backend/app/db/restore_contract.py`, `backend/scripts/verify_postgresql_restore.py`, focused
tests and a signed/canonical manifest. Reuse Task 4's canonical typed row encoding and semantic
validators by extracting stable pure helpers where necessary. Do not weaken Task 4.

The manifest binds one backup generation and contains only redacted authorities and safe evidence:

- manifest schema version, generation id, creation/start/end times, source build and PostgreSQL
  major version;
- per-plane safe physical/schema identity, current marker/head and full expected table inventory;
- table row counts, ordered PK-set digests and typed row digests;
- owner/account partition counts, active/revoked authentication/session counts, money/book counts,
  execution lease/history/command-journal state, job/outbox/cursor counts and content-address sets;
- sequence/identity high-water evidence required to prove the next insert cannot collide;
- cross-plane execution organizations, research owners and ledger `(owner, account)` identities;
- artifact/graph/research content-address verification summaries;
- backup artifact identifiers and SHA-256 digests, but no token, ciphertext, artifact bytes, raw
  row, connection password, query secret or full URL;
- canonical manifest content address and an operator-provided signing key/signature interface. A
  local unsigned development report is labeled unsigned and never satisfies production approval.

The verifier must:

- accept only three fresh isolated PostgreSQL targets with the expected explicit search paths;
- refuse a target containing unknown/current application activity or a target whose restore
  generation does not match the manifest;
- run each plane's current-schema/head/trigger validation, recompute all counts/digests/PK sets,
  validate content addresses and sequence safety, then run cross-plane identity/ownership checks;
- validate Task 5 lease/command evidence and Task 6 outbox/head/cursor identities, not merely table
  presence;
- produce one atomic redacted verification report with `cutover_ready` true only after every plane
  and cross-plane check succeeds;
- never mutate the backup source, a SQLite compatibility database or a protected working-tree file.

Refuse missing/mixed generations, absent plane, wrong head, unexpected table, nonempty pre-restore
target, row/PK/digest/content mutation, cross-tenant owner/account link, cross-plane identity break,
sequence collision, invalid manifest signature and source/target authority overlap.

#### Backup, restore and PITR runbooks

Create `docs/operations/postgresql-backup-restore.md` and bounded scripts using argument arrays and
credential-safe environment/process handling. Never print a password-bearing URL or pass secrets in
an observable shell command when a `.pgpass`/provider secret mechanism is available.

Document and automate where locally possible:

1. refuse unknown schema/build state and prove all three current heads;
2. enter maintenance, reject new writes, drain workers/outboxes, disarm and release/block execution
   cells, and record the last durable offsets/leases;
3. create separate plane backups under one generation, hash them and write the manifest;
4. restore into brand-new isolated targets using a restore-only identity with no application/broker
   credentials;
5. run the verifier before networking/application credentials are attached;
6. isolate/demote the old primary, update authorities, start API replicas first, then outbox/job
   consumers, then execution holders in `recovering`;
7. reconcile and explicitly activate accounts one by one; observe before ending maintenance;
8. rollback by authority switch only when no new writes/effects occurred, otherwise stop and follow
   an incident/reconciliation procedure. Never automatic reverse-copy production writes.

For managed PITR, rehearse a known durable marker before and after a target timestamp, restore to a
clean cluster, prove the correct side of the marker, run the full verifier, and record actual RPO,
RTO and data-loss window. Missing archive/retention/encryption/cross-account controls are failed or
unproven capabilities, not documentation-only successes.

#### Execution disaster recovery

Use the reviewed Task 5 authority model; do not add an alternate recovery lock.

- Infrastructure first prevents the old database/API/cell from accepting traffic. Database fencing
  cannot recall a broker request already released while an old epoch was current.
- A restored lease that says `active` is historical evidence, not permission to resume. On first
  post-restore boot, a boot-unique holder must take a strictly higher epoch and remain `recovering`.
- Old token heartbeat, command transition and durable money/evidence commits fail. Its gateway makes
  no new broker call once fenced.
- Reconcile prior `prepared`, `sent_unknown`, `acknowledged` and working lifecycle/journal evidence
  against broker orders, positions and protective inventory. Preserve known protection. Ambiguity
  becomes `blocked`; no new entry is released.
- Only the new holder may perform reviewed recovery risk reduction on verified bot-owned quantities.
  Activation follows explicit evidence and is measured. Broker HTTP remains non-fencing; state this.

Drill crash after PREPARED, after send/before acknowledgement, after acknowledgement/before evidence,
late old response, heartbeat loss, old-primary reappearance, recovery read outage, protective-state
ambiguity and store-before/fence-after races. Prove no duplicate entry/close/stop and record recovery
duration. Use a deterministic fake broker for adversarial interleavings and live PostgreSQL for the
durable races; do not send real broker orders.

#### Job, event and API-replica recovery

- Backtest and research: kill a worker after claim, during work and after durable result before ack;
  successor claims only expired work, old token cannot publish/complete/cancel, and the terminal
  result is single or content-identical under its durable identity. Record takeover time.
- Task 6 events: commit then kill before delivery, after local effect before cursor ack, during
  listener outage and after retention passes a cursor. Another replica catches up through polling,
  duplicate delivery is idempotent, gaps force scoped resync, and no private byte/count crosses
  owner/account scope.
- API replica: remove a nonholder and the current execution holder independently. Durable reads and
  accepted controls stay available on another replica; broker I/O occurs only on the current holder;
  desired-disable/kill survives takeover and executes once.
- If Task 6's outbox/cursor/gateway interface is absent or not reviewed, these event tests are
  `BLOCKED_BY_TASK6` and Task 7 cannot be accepted. Do not replace them with mocks that prove only a
  proposed interface.

#### Workload harness

Create `backend/scripts/phase2_load.py`, a reusable structured workload definition, fast contract
tests and machine-readable reports. Every run records build, environment, database profile, warm-up,
duration, deterministic seed and configured vector:

- tenants and accounts, API replicas, execution cells and job workers;
- request mix and concurrency by scoped endpoint family;
- backtest/research job mix, cost weights, claim contention and cancellation rate;
- active WebSocket channels/subscriptions, event/state rate and payload bytes;
- database pool size/overflow/timeouts, outbox batch/retention and queue/admission bounds.

Provide named presets including a small CI contract, a `validation-500` tenant/API/event tier and a
50-account execution-authority soak. Presets are validation points, never product caps or hidden
admission constants. CLI overrides every dimension within explicit operator safety bounds.

Measure from real clocks/instrumentation:

- request and job p50/p95/p99 latency, throughput, errors, timeouts and admission rejections;
- pool checkout wait and timeout per plane; PostgreSQL lock/advisory/row-wait samples under the test
  role; connection counts;
- process RSS or container/cgroup memory, bounded queue depth and worker/event lag;
- sent and received WebSocket bytes, fanout serialization count and disconnect/backpressure rate;
- lease/job/outbox takeover and recovery duration, oldest unknown command/event age;
- compute, memory, database/storage, backup/WAL and egress quantities plus an explicit dated price
  input snapshot. Do not invent a universal cloud cost.

A required measurement that cannot be obtained is `UNMEASURED` and fails the applicable production
capacity claim; it is never recorded as zero. Reports separate saturation, rejection and failure.
Bounded overload must reject/degrade predictably without cross-tenant data, money mutation, duplicate
work or unbounded queue/RSS growth. There is no requirement to make every overloaded request succeed.

#### CI and deployment integration

- Add a PostgreSQL 16 CI service with non-secret test authorities and explicit per-plane schemas.
  Run fresh/current schema gates, the fast logical backup/restore verifier, core lease/job/outbox
  races and the small workload contract. Keep timing-stable long soaks and managed PITR in scheduled
  or operator rehearsal jobs.
- Update deployment preflight to recognize PostgreSQL authorities, current heads, backup capability,
  maintenance state and migration/restore order. Retain SQLite backup behavior only for the local
  profile; do not imply it protects a PostgreSQL deployment.
- Production startup refuses when required restore-generation/maintenance safety markers say the
  target is quarantined or unverified. Avoid a permanent operational dependency on a local report
  file; bind approval to durable deployment configuration/evidence.

#### Test-first acceptance

- Capture REDs for absent restore verifier, mixed generation, mutated money/auth/content rows,
  sequence collision, restored-active lease reuse, old-token write, job double publish, event loss,
  foreign resume cursor, unbounded queue and missing metric reported as zero.
- Run a local PG16 `pg_dump`/`pg_restore` three-plane fixture containing at least two tenants, two
  accounts, active/revoked sessions, money/book state, Task 5 lease/command ambiguity, Task 6
  outbox/cursors, research jobs/results and ledger artifacts. Restore to clean schemas and verify.
- Mutate one load-bearing identity/digest/sequence per class and prove refusal; keep ordinary DDL
  recovery proof proportional.
- Run the execution/job/event failpoints above in independent sessions and processes where process
  death matters. A mutation removing a fence/token/cursor/digest/queue bound must turn its named gate
  red.
- Run the small CI workload twice for determinism/tolerance; run the 500 validation tier and
  50-account soak once with retained machine-readable reports. Do not repeat long tests for ceremony.
- Run focused Phase 2 schema/copy/tenant/auth/money/execution/research/ledger/outbox gates,
  compilation and `git diff --check`. One bounded broad suite may run once and must be reported
  truthfully if incomplete.
- Stop uncommitted for independent Sol review.

#### Exclusions and nonclaims

- No frontend work, Kubernetes migration, real-money load test, broker-side fencing claim or fixed
  user/product ceiling.
- No claim of managed PITR, geographic failover, RPO/RTO, cost or horizontal WebSocket continuity
  without the corresponding retained environment evidence.
- No exotic historical SQLite migration matrix beyond regressions needed to keep the local profile.
- Never touch or stage the four inherited protected venue/provider/test files.

#### Report

Write `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/task-7-report.md` with
backup/manifest/restore contract, exact local and managed evidence, RPO/RTO/nonclaims, disaster and
takeover results, workload vectors, raw metric/report artifact paths, cost assumptions, RED/GREEN and
mutation evidence, changed files and protected hashes. Stop uncommitted for independent review.
