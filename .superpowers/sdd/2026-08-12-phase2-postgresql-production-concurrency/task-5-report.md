# Task 5 implementation report

## Authority model

Revision `0032` adds one durable lease per owner/account, sparse transition history, and bounded
command/control evidence. Claims use short SQLite immediate transactions or PostgreSQL row locks,
database time, permanent monotonic epochs, recovery-first takeover, and exact token predicates.
History excludes heartbeats. Commands store digests and bounded correlation identity, never raw
broker requests or credentials.

`FencedBrokerGateway` prepares, rechecks, releases, and journals every wrapped LiveBroker client
place/cancel and venue protective place/cancel/modify call. Network ambiguity becomes
`sent_unknown`; failure to persist ambiguity leaves `prepared`; both require recovery. Successful
commands remain acknowledged until token-fenced durable money/evidence commits resolve them.
LiveBroker binds its SQLAlchemy session to the exact lease token, covering ORM flush and Core DML
commit provenance.

For V1, a protective modify/cancel without a method-specific durable evidence seam remains
`acknowledged`; it does not stop the healthy current holder. On takeover it keeps the new holder
in `recovering`, its age remains operator-visible, and `reconcile_prior_command` either resolves
it from an exact broker/protective snapshot or moves the lease to `blocked` with a bounded reason.
No unrelated commit can falsely resolve it.

Recovery requires one exact signed broker position and one live protective identity with the
same id, kind, quantity, side, and trigger as the durable position. Opposite-side, oversized,
dead, stale-trigger, missing, duplicate, or unreadable representations block. The strict startup
snapshot now invokes prior-command reconciliation in production: exact broker id/tag evidence or
an exact absent cancel target resolves under the new epoch; uncorrelated evidence blocks.

Controls execute only the current durable `control_revision`. Older prepared controls are
terminalized as superseded, gaps or duplicate current revisions refuse, and completion verifies
the current desired revision/state before changing effective or process-local state. A tag-only
pending entry survives KILL cancellation until it gains a broker identity or is reconciled.

Final review hardening binds capital bootstrap before any live or leased paper construction can
create money state; stale SQLite/PostgreSQL epochs create zero capital rows. Plain local
`PaperBroker` construction retains its explicit non-leased compatibility path. ARM/DISARM now
commit the deployment projection, revision-qualified command resolution, and effective lease
state in one fenced transaction; the local runner flag changes only after that commit. KILL also
queries scoped WORKING journal rows, unresolved lifecycle facts, and unresolved broker commands
before the same durable completion. A partial KILL atomically persists Deployment disarmed,
effective disabled, and a failed command outcome; the local runner stays disarmed. Liquidation
failure can never restore the prior armed state.

The database cannot prevent an already-released stale broker HTTP request. It prevents the old
epoch from recording lifecycle, journal, position, trade, capital, or protective state and forces
the new epoch to reconcile before activation.

PostgreSQL API replicas default to API-only. Explicit account workers claim one configured account.
Durable status and ARM/DISARM/KILL requests work without a local runner. The holder claims controls
once, persists arm state before changing its local flag, and refuses to resolve a partial kill.
Heartbeat loss stops the runner. Recovery failure blocks the lease and starts no loops.

## TDD and failpoint evidence

- Missing model/repository was captured before production implementation.
- SQLite tests cover one-winner claims, stale heartbeat/money writes, recovery gating, all five
  broker mutation shapes, uncertain send/no retry, ack-before-evidence loss, late prior-epoch
  effects, acknowledged-to-resolved evidence ordering, takeover control survival, double claim,
  control-idempotency collisions, truthful desired/effective arm state, strict partial KILL, and
  exact or discrepant prior-command reconciliation.
- Live PostgreSQL tests use two sessions for one-winner claim, database-time expiry, takeover,
  stale rejection, exact-once control claim, independent-account progress, and the commit/takeover
  interleaving. An old bound money transaction holds the exact lease row lock through commit, so
  takeover waits: the old commit either linearizes before the epoch increment or, if takeover wins
  first, stale DML cannot commit afterward.
- Existing live broker/lifecycle/API isolation regressions remained green after perimeter wiring.

Commands retained during implementation:

```
PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/postgres \
  .venv/bin/python -m pytest tests/test_execution_leases.py tests/test_execution_controls.py \
  tests/test_postgres_execution_leases.py tests/test_execution_http_isolation.py \
  tests/test_execution_control.py tests/test_api_auth.py tests/test_kite_order_client.py -q
# 112 passed

PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/postgres \
  .venv/bin/python -m pytest tests/test_postgres_execution_leases.py tests/test_postgres_execution_schema.py -q
# 23 passed

.venv/bin/python -m pytest tests/test_execution_http_isolation.py tests/test_broker_factory.py \
  tests/test_execution_connection.py tests/test_live_entry_durability.py \
  tests/test_execution_lifecycle_recovery.py -q
# 72 passed

.venv/bin/python -m pytest tests/test_db_planes.py tests/test_database_copy_contract.py \
  tests/test_schema_migrations.py -q \
  -k '0032 or current_head or head_revision or database_copy or table_planes'
# 15 passed, 4 deliberate PostgreSQL-only skips

.venv/bin/python -m compileall -q app tests/test_execution_leases.py \
  tests/test_execution_controls.py tests/test_postgres_execution_leases.py
git diff --check
# passed
```

Changed implementation paths are the lease models/migration/repository, LiveBroker composition,
runner assignment/startup, durable execution API boundary, plane map, focused tests, and this
runbook. No frontend or Task 6 outbox was added.

Protected inherited files retain exact hashes:

- `app/engine/kite_venue.py`: `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
- `app/engine/venue.py`: `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
- `app/providers/brokers.py`: `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
- `tests/test_broker_registry.py`: `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`
