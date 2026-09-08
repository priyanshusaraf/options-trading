# Coordination, consistency, and idempotency map

This map names guarantees per operation. It avoids global “strong/eventual” or CP/AP labels. “Proven” means only the named code and focused local evidence, not deployment readiness.

| Operation / predicate | Durable authority | Coordination boundary | Idempotency / ordering key | Retry rule | Current evidence | Decision |
|---|---|---|---|---|---|---|
| Publish/reuse experiment specification | `ExperimentSpec` | Database uniqueness by owner/spec ID | Truncated 128-bit recipe digest | Reuse existing row | Forced collision RED; see KPV5-A-001 | Compare canonical bytes and migrate additively to full address. |
| Published graph research admission | Admission artifact plus graph/data provenance | Receipt verification before data use | Admission and graph content addresses | Refuse stale receipt | Positive receipt tests; ResourcePlan absent | Existing F03 must join accepted ResourcePlan before execution. |
| Backtest run claim | Backtest run row | Conditional update and claim token | owner + run + claim token | Expired claim may be replaced; stale token refuses | Current first SQLite claim-race test times out; earlier shadow evidence predates later dirty edits | Reconcile the inherited concurrency change, then add PostgreSQL process-kill/takeover evidence. |
| Research operation claim | Operation/item rows | owner-scoped pending/running quotas, advisory/transaction lock, claim token | owner + operation + item + token | Heartbeat/reclaim; terminal state refuses stale writes | Focused SQLite suite | Retain; prove PostgreSQL contention and failover. |
| Outbox append | Plane-specific outbox tables in same transaction | Caller-owned database transaction | producer key; aggregate sequence; plane offset | Duplicate producer returns existing fact; consumer effect receipt dedupes | Focused outbox tests inherited; static review | Retain database outbox. No event-bus adoption. |
| Outbox delivery | Durable consumer cursor/receipt | Lease token around bounded claim batch | consumer + event + effect key | Re-poll after crash; duplicate effect suppressed | Code path inspected | Notification remains hint only. Restore proof pending. |
| WebSocket projection | Database projection | None for correctness; local bounded queue only | server-derived owner/account channel + signed resume cursor | Drop/coalesce stale frames; resync from durable state | Focused manager/tenant tests | Correct derived-state posture; specify connected-session revocation. |
| Execution intent creation | `ExecutionIntent` + initial event | Database transaction before external submit | random client intent ID + broker tag | Retry only generated local identity collision | Focused lifecycle tests | Retain. Broker tag namespace limits remain unresolved. |
| Broker submit | Broker plus durable local intent | Single external send; no resend after ambiguity | client intent/broker tag; broker order ID after ack | Poll only; uncertainty blocks and reconciles | Synthetic order/recovery tests | Correct fail-closed shape; no live conformance claim. |
| Broker observation reduction | Immutable `ExecutionOrderEvent` | Per-intent insertion sequence | source + source event ID; cumulative fill | Exact duplicate accepted; conflict refuses or records anomaly | KPV5-B-002 RED | Define terminal status/conflict lattice. |
| Capital admission | Reservation head, capital state, batch/decision/reservation records | owner/account/book/currency lock + lease fence + one transaction | batch and candidate content addresses; head revision | Exact duplicate returns stored decision; conflicting duplicate refuses | Focused SQLite tests, PostgreSQL cases unavailable | Foundation retained, still unwired. |
| Risk-reducing action | Candidate purpose and existing ownership | Must not wait for new capital | candidate/reservation/position lineage | Fail closed on ownership uncertainty, but exit authority stays available | Static capital/lifecycle review | Preserve entry-only ARM/capital gating. |
| Position close ownership | Durable bot position plus live account read | Exact contract/side/quantity check | position/campaign and broker account scope | No order if read missing or quantity insufficient | Focused reconcile tests | Retain; broker net positions do not reassign virtual ownership. |
| Cache read | Rebuildable result/cache rows | No money authority | Complete owner/data/policy/engine/plan key required | Miss/rebuild; corrupt value refuses | Partial positive tests | Audit each consumer; KPV5-A-007 and F03 remain. |

## Where coordination is required

1. Capital availability, active reservations, and unresolved broker work form one serialized predicate per owner/account/book/currency. The database row/advisory lock is the authority; an in-memory/distributed lock would only be a wake-up optimization.
2. Claim ownership and terminal job writes require fencing because a stale worker can continue after lease expiry.
3. External order submission cannot be made transactional with the local database. The safe contract is durable intent first, send once, persist acknowledgement when possible, then reconcile ambiguity.
4. WebSocket fan-out, cache invalidation, and PostgreSQL notification do not require consensus. Durable offsets and reloadable projections tolerate duplicates and missed hints.

## Failure-state vocabulary required before V1 execution

`PENDING`, `SUBMITTING`, `ACKNOWLEDGED`, `WORKING`, `PARTIALLY_FILLED`, `COMPLETE`, `CANCELLED`, `REJECTED`, and `RECONCILIATION_REQUIRED` must have a declared transition/conflict model. Arrival order cannot decide contradictory terminal facts. The current reducer names anomalies but can combine `CANCELLED` with a complete fill.

## No-technology decision

The existing PostgreSQL/SQLite transaction, outbox, claim-token, and bounded-queue primitives cover current needs. A queue, cache, stream broker, or consensus system needs a measured failure that these primitives cannot meet and a separate dependency/licence/deployability gate.
