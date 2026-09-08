# Security, reliability and supply-chain packet

## Scope and nonclaim

This is a source packet for the later repository matrix. It is not a full ASVS
level review, penetration test, privacy/legal assessment, SBOM, production SLO or
deployment approval.

## Scoped security baseline

Use ASVS 5.0.0 identifiers only after the exact requirement JSON/PDF is loaded.
The repository review must cover:

| Surface | Required direct evidence |
| --- | --- |
| API objects | Synthetic tenants A/B, guessed IDs, list/count/pagination/bulk/export, positive same-owner control and zero side effects. |
| Jobs | Owner-scoped submit/claim/status/cancel/artifact/finalize, membership removal and restart. |
| WebSockets | Handshake owner scope, channel binding, resume cursor, revocation/expiry bound and no post-revoke frame. |
| Caches/public computation | Complete answer identity, private-input eligibility and no metadata leak. |
| Uploads/custom nodes | Authorization, type/size/decompression/resource ceilings, safe filenames/storage, parser isolation and cleanup. |
| Support/admin | Least privilege, time-bounded approval, audit trail and diagnostics without strategy/result/credential access. |
| Logs/traces | No strategy source, datasets, tokens, sessions, credentials, bank facts or private payloads. |

Chat 1 found private channels bounded and V0-denied, but connected-session
revocation is unspecified for future execution profiles. This needs an owner-set
revocation objective and direct socket tests, not an inferred polling interval.

## Reliability baseline

| Failure | Required contract |
| --- | --- |
| Remote timeout | Preserve uncertainty; reconcile external state; no blind resend. |
| Duplicate request | Same caller/token and same canonical intent return the same logical effect; mismatch refuses. |
| Worker crash | Durable claim/checkpoint identifies permissible takeover; stale claimant cannot finalize. |
| Queue overload | Bound queue age/depth and shed deferrable research before safety work in execution-enabled profiles. |
| Cache loss | Rebuild from addressed durable truth or expose degraded/unavailable state. |
| Provider outage | No semantic fallback or mock substitution; exact typed refusal. |
| Restore | Reconstruct strategy, dataset, evidence, order, fill, position and ledger attribution on supported databases. |

Current evidence cannot close claim fencing: the isolated SQLite claim-race test
timed out and PostgreSQL process-kill/takeover was unavailable.

## Supply-chain baseline

SLSA provenance is useful only when verified against expected source, builder,
parameters and artifact digest. Required release evidence should bind:

```text
source commit and dirty-state policy
dependency/lockfile and SBOM digests
builder/workflow identity and version
test/review evidence identity
frontend/backend artifact digests
database heads and configuration digest
deployment target and rollback receipt
```

NIST SSDF is a practice vocabulary, not a pass badge. The dependency review must
still inspect exact direct/transitive versions, licences, advisories, vendored
assets and rollback. No dependency was added in this programme.

## Observability baseline

Use stable internal semantic names before any telemetry vendor decision. Record:

- request/job/run/order/reconciliation IDs and release/resource-plan addresses;
- stage latency, queue age, claim age, retry count and refusal reason;
- stale/missing/unknown/ambiguous semantic states;
- tenant-safe cardinality and redacted errors;
- release and schema correlation;
- user-impact and correctness SLOs, not uptime alone.

Telemetry remains derived operational evidence. It never authorizes a strategy,
proves a fill or replaces durable ledger/research facts.

## Immediate source-backed gaps

1. Connected WebSocket session revocation is a future missing invariant.
2. The canonical graph-experiment route omits the accepted ResourcePlan.
3. The current claim-race gate does not terminate under the final dirty-tree state.
4. Restore and PostgreSQL failover evidence remain unavailable.
5. Full ASVS, SBOM/licence and privacy-flow matrices are still required before a
   release claim.
