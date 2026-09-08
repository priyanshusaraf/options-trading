# Coordination map: first packet only

These rows describe inspected job boundaries. The rest of the mandatory object/transition universe is not classified yet.

| Transition | Invariant / weakest demonstrated model | Ordering / idempotency | Conflict / recovery truth | User uncertainty / proof |
| --- | --- | --- | --- | --- |
| Claim research run | Atomic conditional database update; at most one current claimant | Owner + run; unique current claim token | Lost race returns no claim; persisted run owns permission | Pending/running. Actual SQLite barrier probe; PostgreSQL engine proof still open. |
| Persist result batch | Transaction on authoritative run plus deduplicated cell writes | Owner + run + cell identity; token checked at database sink | Stale/cancelled writer refused; existing durable cells survive takeover | Progress derives from durable results. Selected batch/replacement tests. |
| Finish research run | Atomic fenced terminal state and transactional event production | Owner + run + terminal producer key | Only current unexpired claimant; terminal record is source of truth | Completion must follow committed result/status, not a local button or socket. Current consumer UX is not reviewed here. |
| WebSocket projection of completion | Proposed derived, recoverable fan-out, not new authority | Must recover from durable job status | Missing/out-of-order events must not change business truth | Requires separate actual-client reconnect test; no frontend change here. |

No claim of global linearizability, serializability across every object, or exactly-once delivery. Capital, OOS reveal, revisions, deployments, positions, notifications, telemetry and future graph collaboration require their own scoped classification and proof.
