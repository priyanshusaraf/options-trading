# Residual risk and open questions

## Blocking residual risks

1. Confirmatory OOS remains invalid on the legacy experiment path.
2. V0 still exposes the legacy current-universe sweep policy.
3. Published graph experiments still omit the canonical `ResourcePlan`.
4. Current SQLite claim-race evidence does not terminate; PostgreSQL contention and
   process-kill/takeover are unproved.
5. Frontend product acceptance, browser evidence and the active V0 successor chain
   remain owned by the convergence task.
6. Backup/restore, RPO/RTO, production configuration, deployment and rollback are
   not proved in a release environment.

## Important hardening risks

- Forced experiment-ID collision reuses different recipe bytes.
- Optimization population/order and DSR/PBO inputs may not reconstruct after
  restart/evolution.
- IID trade bootstrap assumptions are unstated and untested on dependent trades.
- General completed-observation constructors permit impossible availability order.
- Provider semantic-change invalidation is not proved across every result.
- Logs/traces/uploads/custom nodes have not received a full scoped ASVS/data-flow
  matrix.

## Future execution risks

- Cancel/complete order observations can yield a contradictory full-fill state.
- Broker tag/history retention and timeout reconciliation vary by provider and need
  contract/conformance evidence.
- Connected WebSocket revocation latency is an owner/security decision.
- Capital admission is a correct-looking foundation but intentionally unwired and
  not PostgreSQL/live proved.
- P0/P1 protection/reconciliation isolation is unmeasured.
- Exact held-contract exits, partial fills, margin and option liquidity are not
  certified.

## Provider and data questions

- Which provider contracts permit storage/replay of historical options, OI, depth
  and order-flow data, and for how long?
- What exact historical contract-master, corporate-action and rulebook source is
  licensed for each instrument family?
- What request tag uniqueness/retention and order-history recovery guarantee does
  each broker expose after the trading day?
- Which missing fields are absent versus reported zero?
- What material provider semantic change forces result/deployment revalidation?

## Owner decisions required

- Serialize the four V0 correction capsules and assign path ownership.
- Set connected-session revocation objective.
- Set backup/PITR/RPO/RTO and restore-drill objectives.
- Set future execution protection/reconciliation latency and capacity objectives.
- Approve licensed data/provider contracts and redistribution/retention policy.
- Decide commercial quotas/pricing only after measured cost envelopes.
- Decide legal/regulatory/custody/suitability structure before managed allocation,
  outside capital or fund operation.

## Evidence still required

| Area | Missing proof |
| --- | --- |
| Research | OOS suffix invariance, exact optimizer reconstruction, DSR/PBO population, dependent resampling and full cost/fill identity. |
| Database | Current migration heads, zero/current-state forward migration, rollback and PostgreSQL concurrency histories. |
| Jobs | Bounded claim race, process death at transaction boundaries, poison/cancel/reclaim and exact terminal evidence. |
| Tenancy | Full A/B surface matrix including artifacts, exports, sockets, cache, analytics and support. |
| Security | Scoped ASVS 5.0.0 requirement matrix, dependency/SBOM/advisories, upload/custom-code and redaction sentinels. |
| Provider | Official capability/version/limits, real adapter conformance with authorized fixtures and semantic-change classification. |
| Execution | Unknown-submit, duplicate/out-of-order/correction state machine, exact position ownership, ledger conservation and degraded exits. |
| Recovery | Three-plane PostgreSQL backup/restore, outbox resync, unresolved-order/capital recovery and exact artifact reconstruction. |
| Capacity | Representative hardware/resource calibration, concurrency breaking point, queue age, database contention and unit costs. |
| Frontend | Type/test/build and safe authenticated browser journeys over current accepted backend contracts. |

## Environment limitations

- The worktree remains extensively dirty and concurrently modified.
- Chat 2 had no collision-free product capsule.
- No Docker/PostgreSQL release environment, provider network, licensed dataset,
  live broker or deployment target was used.
- Important PDF text was inspected, but SQL:2011 later-page screenshots timed out.
- DDIA second-edition book text remained unavailable.
- Source findings cannot establish profitability or production readiness.

## Next safe sequence

1. Finish the active V0 frontend/product recovery and freeze shared hashes.
2. Materialize correction capsules C1–C3, then C4, with one owner at a time.
3. Run RED-to-GREEN focused and subsystem evidence for each.
4. Localize the claim-race timeout before queue/workflow decisions.
5. Complete release security/deployability/restore/capacity matrices.
6. Only then make a V0 release decision.
