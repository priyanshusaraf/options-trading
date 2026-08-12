### Task 5: Durable account leases, fenced execution, and replicated control authority

**Base commit:** `8e520ff`

**Primary artifacts:**

- Add current execution-plane lease, sparse history, and command-journal models plus migration
- Create `paper-trader/backend/app/execution/leases.py`
- Create one fenced broker mutation gateway and route every real outbound mutation through it
- Replace process-global API execution authority with durable account-scoped status and control work
- Add two-session SQLite/PostgreSQL races, failpoint recovery tests, and an operator runbook
- Modify only execution/account/control code required by this authority boundary

**Produces:** one durable lease row per `(owner_id, broker_account_id)` with a monotonically
increasing fence epoch, current cell/worker identity, database-clock heartbeat/expiry, recovery
state, and sparse transition evidence. A worker may submit to a broker or mutate durable execution
state only through an explicit current lease token. A takeover remains `recovering` until prior
commands, order lifecycle evidence, broker orders, positions, and protective inventory reconcile.

#### Honest safety boundary

The database can reject stale durable authority and stale writes. It cannot recall a network
request that a worker released while its epoch was current and that reaches a broker after a new
epoch takes over. Broker tags are correlation evidence, not fencing or idempotency unless a venue
documents otherwise.

- Every outbound mutation first records a durable, epoch-stamped command in a short transaction.
- The gateway rechecks the exact lease immediately before network I/O.
- A network exception or lost acknowledgement becomes `sent_unknown`; the command is never
  retried blindly.
- Takeover blocks new entries until every prior prepared/unknown/working command and broker-visible
  effect is resolved.
- Absolute stale-send prevention is claimed only for a future fencing-aware broker gateway or a
  venue-enforced idempotency key. It is not claimed for ordinary broker HTTP APIs in this task.

#### Durable model

`AccountExecutionLease` has a composite tenant/account identity and FK, a permanent positive
monotonic fence epoch, `idle | recovering | active | blocked` state, stable cell and boot-unique
worker identity, bounded host diagnostics, database-clock claim/heartbeat/expiry timestamps,
recovery/reconciled evidence, bounded block reason, desired execution state and control revision.
It is never deleted or epoch-reused. Index expiry/state and worker ownership and close the state,
timestamp and epoch contracts with database checks.

`AccountExecutionLeaseHistory` is sparse and bounded to claim, takeover, recovery completion,
block, release, cancellation and fence rejection. Heartbeats do not create unbounded history.

`AccountExecutionCommand` is money-safety evidence, not the Task 6 event outbox. It stores an
immutable command/idempotency identity, owner/account/fence/cell/worker, kind and durable target,
request digest, safe broker tag or documented venue idempotency key, bounded state/timestamps/error
code and broker order/protective identity. It stores no credential, raw request secret, unbounded
payload or high-cardinality metric label.

Stamp the fence epoch on existing execution intent, immutable order event and order-journal evidence
required to reconstruct authority. Historic rows remain explicit pre-fence evidence and force
recovery rather than receiving a fabricated epoch.

#### Lease and transaction contract

- PostgreSQL uses row locks and `FOR UPDATE SKIP LOCKED`; bounded row creation may use the existing
  advisory-lock seam. SQLite uses short `BEGIN IMMEDIATE` transactions.
- Database time decides expiry. Host clocks are diagnostic only.
- Exact-account claim races have one winner. Takeover increments the epoch exactly once and enters
  `recovering`, never directly `active`.
- Heartbeat, activation, release, block, command transitions, lifecycle writes, position/trade/
  capital booking and protective-id persistence predicate on the exact current lease token.
- A stale worker cannot append evidence or commit money state. Heartbeat loss strips mutation
  capability and stops its runner.
- Sessions and locks stay short. No database lock crosses broker/provider network I/O.

#### Broker mutation perimeter

Route every real external mutation through one closed `FencedBrokerGateway`:

1. entry and exit placement;
2. inflight/working-entry and partial-close cancellation;
3. protective-stop placement;
4. protective-stop cancellation, including resync and close-before-cancel;
5. protective-stop modification for both resting and server-trigger paths.

Thin Kite/Dhan transports do not obtain authority independently. Keep full command/intent identity
in the database. A short venue tag may contain a bounded epoch component and intent hash for
correlation, but is never described as idempotency without a venue guarantee.

#### Recovery and emergency behavior

- Claim/takeover enters `recovering`; entries are denied.
- Replay every prior-epoch prepared, unknown and working command; correlate tag/order ids; inspect
  broker orderbook, bot-owned positions and protective inventory.
- Preserve known exchange protection. Do not blanket-cancel or replace stops.
- Repair evidence only under the new epoch. Ambiguous or unreadable broker state becomes `blocked`.
- The new epoch may perform narrow recovery risk reduction after proving bot-owned identity and
  quantity: cancel a known working entry, close verified owned quantity or restore a missing known
  stop. The old epoch gets no emergency exception.
- Crash after prepare, after send/before acknowledgement and after acknowledgement/before durable
  persistence must converge without blind duplicate submission.

#### Replicated control API contract

- `app.state.runner` and another process's in-memory runner are not shared authority.
- The lease row is the durable cell/status projection. A supervisor maps only its owned lease to a
  local runner.
- API replicas read account-scoped durable status and never fall back to a local legacy runner for
  a foreign or remote account.
- ARM, DISARM, KILL and supported close actions become durable account-scoped controls with
  idempotency identity, expected revision/epoch, actor and status. A non-holder replica returns an
  accepted request identity, not a false broker-success claim.
- The holder executes and records each control once. Disarm persists desired-disabled state;
  effective arm requires successful recovery.
- Preserve roles/scopes and foreign-equals-absent behavior for `/api` and `/api/v1`.
- Shared WebSocket/event delivery remains Task 6.

#### Test-first acceptance

- Capture behavioral REDs for missing repository/model, double winner, stale durable write,
  unfenced broker call, direct API runner fallback and ambiguous-send retry.
- Run exact-account two-session races on SQLite and live PostgreSQL for claim, heartbeat, expiry,
  takeover, release, block and control claim. Different accounts progress independently and the
  PostgreSQL scheduler uses SKIP LOCKED.
- Transport spies cover place, cancel and protective place/cancel/modify. A stale token makes zero
  calls; a current recovered token reaches each once.
- Failpoints cover prepare-before-send, send-before-ack, ack-before-evidence, late prior-epoch
  effect, ambiguous cancel/modify, recovery outage and new-epoch risk reduction.
- A late prior-epoch effect blocks new entries until reconciliation resolves it.
- Prove lifecycle/journal/position/trade/capital/protective-id mutations are token-qualified.
- Two API replicas share durable status/control without invoking one process's runner. Foreign
  tenant/account controls remain absent/forbidden with zero mutation.
- Add a non-vacuous mutation that removes a lease predicate or transport guard and makes the gate
  fail.
- Run focused money/execution/concurrency/auth gates, live PostgreSQL races, compilation and
  `git diff --check`. A long broad suite is optional once, not repeated for ceremony.
- Stop uncommitted for independent Sol review.

#### Metrics and operator evidence

Expose bounded host aggregates and owner-local status for claim, takeover, recovery, blocked,
fence rejection, heartbeat/lease age, recovery duration, sent-unknown age, reconciliation
discrepancy and control age. Do not label shared metrics by raw owner, account, worker, command,
order or broker tag. Document recovery/block/takeover and the external-broker fencing limitation.

#### Exclusions

- No Task 6 outbox, LISTEN/NOTIFY or cross-replica WebSocket delivery.
- No Task 7 backup/load program.
- No frontend changes.
- No broker-side fencing claim where the broker lacks it.
- No fixed user or 500-tier product cap.
- Never touch or stage the four inherited protected files.

#### Report

Write `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/task-5-report.md` with
the exact authority model, RED/GREEN/failpoint evidence, live PostgreSQL commands/results, every
guarded external mutation, API changes, external-broker limitation, changed paths and protected
hashes. Stop uncommitted for independent review.
