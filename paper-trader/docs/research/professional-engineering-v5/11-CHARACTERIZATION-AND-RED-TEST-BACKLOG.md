# Characterization and RED-test backlog

Chat 1 added five audit-only tests. They are deliberately outside the production test directories and must remain RED until their named owner implements the response. A red characterization is evidence of current behavior, not a passing gate.

## Tests added in Chat 1

| Priority | Test | Current result | Finding | Chat 2 acceptance |
|---|---|---|---|---|
| P0 | `characterization/test_oos_qualification_contamination.py` | RED: qualification observes the same full 400 rows later labelled OOS | KPV5-A-002 | Mutating the sealed OOS suffix cannot change qualification, search, or candidate selection. |
| P0 | `characterization/test_v0_legacy_sweep_route.py` | RED: V0 has no denial rule for `POST /api/backtest/sweep` | KPV5-A-003 | Both API prefixes refuse before dispatch/provider access; canonical manifest route remains available. |
| P1 | `characterization/test_experiment_spec_collision.py` | RED: two forced distinct recipes reuse one spec | KPV5-A-001 | Full address plus canonical-byte mismatch refusal, including legacy compatibility. |
| P0 | `characterization/test_graph_resource_plan_boundary.py` | RED: published graph entry point has no resource-plan boundary | KPV5-B-001 / existing F03 | Exact plan is reconstructed, verified, persisted in spec/evidence and mutated across every dimension. |
| Future P0 | `characterization/test_execution_terminal_observation_conflict.py` | RED: full fill remains labelled `CANCELLED` | KPV5-B-002 | Explicit status/conflict lattice yields a coherent `COMPLETE` or `RECONCILIATION_REQUIRED`, never contradictory state. |

Evidence logs:

- `.agent/runs/kleppmann-reaudit-v5/pass-a/red-experiment-spec-collision.log`
- `.agent/runs/kleppmann-reaudit-v5/pass-a/red-oos-qualification-contamination-recheck.log`
- `.agent/runs/kleppmann-reaudit-v5/pass-a/red-v0-legacy-sweep-policy.log`
- `.agent/runs/kleppmann-reaudit-v5/pass-b-runtime/red-pass-b-characterizations.log`

## First implementation tests for Chat 2

### V0 release blockers

1. **OOS selection isolation**
   - Construct identical train prefixes with adversarially different OOS suffixes.
   - Assert identical qualification, optimization population/order, chosen parameters and pre-OOS evidence.
   - Persist every screened candidate and peek; label exploratory if the boundary is not implemented.
2. **Legacy route negative reachability**
   - Test `/api/backtest/sweep` and `/api/v1/backtest/sweep` under V0.
   - Spy on provider, universe, queue and repository; all remain untouched after refusal.
   - Keep the standard-profile compatibility case separate.
3. **F03 ResourcePlan integration**
   - Test exact graph/registry/data/role/plan identity, missing/forged/stale plan, every family/total/window/provider bound, result identity, cache key and restart.
   - Preserve the existing nine F03 RED consumers and the programme’s named owner.
4. **Completed/available invariant if provider capture enters V0**
   - Constructor, decoder, persistence, capture producer, alignment, prefix and export cases.
   - Forming values use a separate contract; historical invalid facts remain preserved but inadmissible.

### V0 research hardening

5. **Spec identity collision**
   - Force digest collision independent of cryptographic probability.
   - Verify stored canonical bytes before reuse and prove additive legacy lookup/rollback.
6. **Optimization reconstruction**
   - Kill/restart after each trial and candidate boundary.
   - Reconstruct exact resolved search space, candidate order, `is_sharpe`, DSR/PBO input matrix, selected candidate and terminal gate from stored evidence.
7. **Dependent-trade evidence**
   - IID control, autocorrelated clusters, overlapping holding periods and regime blocks.
   - Record method/seed/block rule in evidence before adopting a replacement bootstrap.
8. **PostgreSQL job claims**
   - Two OS processes against PostgreSQL 16; kill before/after claim, heartbeat, item write, terminal write and outbox ack.
   - Assert exactly one winning token and one coherent terminal evidence set.

### V1 execution foundation

9. **Execution observation model**
   - Generate duplicate, delayed, lower-cumulative, cancel/complete, reject/fill, correction and broker-ID-change sequences.
   - Check invariants: fill never decreases, raw facts remain immutable, contradictory terminal facts cannot look resolved, booking/protection gaps block.
10. **Unknown submit recovery**
    - Crash after intent commit, wire accept, broker ID return, local ack, first fill, protection ack and booking.
    - Test zero/one/multiple exact tag matches and provider tag retention namespace.
11. **Capital contention and recovery**
    - Simultaneous batches at identical head revision; deterministic ranking, atomic groups, risk-reduction availability, partial consumption, uncertain submit, expiry and stale fence.
    - PostgreSQL is required before a live integration claim.
12. **P0/P1 QoS**
    - Saturate research, WebSocket encoding, outbox and database pool while measuring protection/reconciliation latency.
    - Establish a failing threshold before choosing process isolation, reserved pools, admission changes or new infrastructure.
13. **WebSocket revocation**
    - Revoke one/all sessions, expire, remove membership and rotate credentials while the socket is connected.
    - Assert no private frame after the declared bound and multi-replica disconnect/resync behavior.

### Recovery and deployment evidence

14. **Three-plane backup/restore**
    - Restore exact schema/head into an isolated PostgreSQL environment.
    - Reconcile outbox offsets/receipts, job claims, graph/data/result identity, unresolved execution, reservations and positions.
15. **Retention and resync**
    - Advance outbox retention watermark past a client cursor; assert explicit resync and current durable projection, not partial replay.
16. **Provider outage/reconnect**
    - Provider-specific disconnect, token expiry, rate limit, subscription churn, semantic-version change and stale-data receipts.

## Existing focused suites run in Chat 1

| Suite | Result | Limit |
|---|---|---|
| Capital admission/schema/recovery/shadow | 67 passing, 3 skipped PostgreSQL cases | SQLite-focused; no live/runtime wiring. |
| Tenant channels, WebSocket manager, V0 release profile | 43 passing | V0 negative authority and local queue behavior only. |
| Execution lifecycle/recovery/leases/restore/live durability | 132 passing, 1 failing | The isolated failure is an inherited current-tree contract mismatch: `test_paper_entry_remains_unlinked` expects no paper intent, while dirty `broker.py` now creates one. It reproduces alone. Do not classify until the active capsule reconciles the intended paper-lifecycle contract. |
| Backtest/research job claims | Combined run was terminated after more than ten minutes; isolated first backtest claim-race case timed out after 45 seconds | Current inherited-tree validation failure. Evidence: `backtest-job-claims-timeboxed.log`. Localize before relying on earlier shadow positives; PostgreSQL remains unavailable. |

## Explicit non-tests

- No live broker/provider call, credentials, VPS, deployment, migration, backup, restore or external infrastructure was touched.
- Source titles, model classes, skipped tests and static comments do not count as passing evidence.
- No characterization test authorizes production changes outside the relevant capsule and owner gates.
