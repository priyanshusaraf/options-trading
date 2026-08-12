# Execution lease operations

Each live execution worker must set `PT_EXECUTION_WORKER=worker`,
`PT_EXECUTION_OWNER_ID`, `PT_EXECUTION_BROKER_ACCOUNT_ID`, and a stable
`PT_EXECUTION_CELL_ID`. PostgreSQL API replicas default to API-only and do not claim accounts or
construct brokers. Local SQLite retains its single-node compatibility worker when the role is
unset.
Shared API replicas set `PT_EXECUTION_WORKER=api`. Unknown role values refuse at boot.

The durable account row is the status authority. A claim starts in `recovering`; startup reads the
journal, lifecycle facts, broker order book, account positions, and protective inventory. Any
unreadable input, unresolved command/intent, working journal row, or unaccounted bot-tagged order
blocks activation. It does not start the signal or risk loops.

Workers heartbeat every ten seconds against database time. Heartbeat loss stops the local runner.
A takeover increments the permanent fence epoch and re-enters recovery. Pending operator controls
are re-fenced to the new holder. ARM, DISARM, and KILL are durable requests; an API-only replica
returns an accepted identity and never claims broker success.

`prepared`, `sent_unknown`, and `acknowledged` broker commands block activation. Never blindly
retry them. Correlate the stored intent tag/order identity with the venue order book, positions,
and protective inventory, then record an explicit resolution or block the lease. Preserve known
exchange protection. Do not blanket-cancel stops.

An acknowledged protective modify or cancel can remain unresolved while the current healthy
holder continues managing the account. It becomes a hard recovery gate only after a takeover:
the new epoch remains `recovering`, and the command age is visible in shared metrics. Resolve it
only from an exact broker/protective snapshot through the prior-command reconciliation path. If
the snapshot is missing, unreadable, or discrepant, move the lease to `blocked` with the bounded
operator-visible reason instead of activating or retrying the mutation.

An exact snapshot means signed broker quantity equals the durable direction and quantity, and the
protective row has the same live id, kind, quantity, side, and trigger. Oversized coverage is not
treated as equivalent. Dead, stale-trigger, duplicate, missing, or ambiguous rows block. Startup
consumes prior commands through this snapshot path; there is no separate raw-SQL or blind operator
override.

Capital bootstrap is a money write and therefore carries the same token as later fills. A stale
worker cannot create a missing ledger row during construction. Control completion is likewise one
transaction: deployment arm projection, current command resolution, and effective lease state
either commit together or remain unchanged. KILL resolves only after scoped journal, lifecycle,
broker-command, open-position, inflight, and pending-entry evidence is empty; partial risk
reduction keeps desired state disabled and records failure without claiming completion.

The database rejects stale durable writes. It cannot recall a broker HTTP request released while
an epoch was current. A request that completes at the broker after takeover may still have an
external effect; the old worker cannot persist money state, and the new epoch must reconcile that
effect before entries resume.

Bounded shared metrics must aggregate claim, takeover, recovery, block, fence rejection, lease age,
unknown-command age, reconciliation discrepancies, and control age. Do not label metrics with raw
owner, account, worker, command, order, or broker-tag values.
