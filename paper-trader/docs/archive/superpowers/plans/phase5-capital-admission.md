# Phase 5 capital-admission implementation plan

Date: 2026-08-25\
Architecture: `paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md`

## Dependency order

```text
P5.4 architecture
  -> sizing/product/target contracts
  -> additive execution schema 0041
  -> fenced PostgreSQL admission transaction
  -> paper-shadow and recovery evidence
  -> independent capital assurance + one critical review
  -> Phase 5 evidence-integration gate
  -> sole Phase 5 final review
```

Every slice is serial. The shared money/schema boundary has no parallel writer.
No slice makes the new decision authoritative for order selection.

## Slice 1: product, sizing and target-position contracts

Capsule: `phase5-sizing-target-position-contracts`

Observable result: pure typed functions reproduce current options/equity/futures
quantity/product behavior, calculate every declared sizing mode, and derive a
pending-order-aware target delta without database or broker I/O.

Owned product paths:

- `paper-trader/backend/app/execution/product_policy.py`;
- `paper-trader/backend/app/execution/sizing.py`;
- `paper-trader/backend/app/execution/target_position.py`;
- `paper-trader/backend/app/execution/capital_compatibility.py`;
- `paper-trader/backend/tests/test_execution_product_policy.py`;
- `paper-trader/backend/tests/test_sizing_target_position.py`;
- `paper-trader/backend/tests/test_allocator.py`.

Direct evidence covers fixed units/lots/capital/equity/risk/volatility, finite
numeric boundaries, fixed-point/minor-unit arithmetic, fees/caps, lot/step
rounding, options/equity/futures compatibility, held and pending deltas, strategy
attribution, and exit independence. Mutations remove no-resize, pending subtraction
and numeric refusal guards.

No existing runner, broker, model, migration or order path changes.

## Slice 2: additive capital schema and migration

Capsule: `phase5-capital-admission-schema`

Observable result: execution migration `0041` and ORM models carry the exact
immutable policies/requests/candidates/batches/decisions, reservation head/current/
events, campaign/tranche/fill allocations and nullable legacy links. No product
writer consumes the new tables.

Owned paths:

- `paper-trader/backend/app/db/models.py`;
- `paper-trader/backend/migrations/versions/20260825_0041_capital_admission.py`;
- `paper-trader/backend/tests/test_capital_admission_schema.py`;
- `paper-trader/backend/tests/test_schema_migrations.py`;
- `paper-trader/backend/tests/test_postgres_execution_schema.py`;
- `paper-trader/backend/tests/test_postgresql_restore_live.py`;
- `paper-trader/backend/tests/test_database_copy_contract.py`.

Evidence requires empty/exact-0040 SQLite and PostgreSQL 16 upgrades,
interruption/restart, constraints/triggers/index/FK/model parity, complete row and
sequence preservation, destructive downgrade refusal, clean restore and mutation
of every critical constraint. Research head remains `0011`.

Deployment impact: `migration-required`, locally runnable only. Production data,
backup retention, cutover and rollback rehearsal remain unclaimed.

## Slice 3: fenced admission transaction

Capsule: `phase5-capital-admission-transaction`

Observable result: one repository/service can persist a complete deterministic
batch and reservations under the current account lease and reservation-head lock.
It is not wired to the runner or broker.

Owned paths:

- `paper-trader/backend/app/execution/capital_admission.py`;
- `paper-trader/backend/app/execution/leases.py`;
- `paper-trader/backend/tests/test_capital_admission.py`;
- `paper-trader/backend/tests/test_capital_admission_postgresql.py`;
- `paper-trader/backend/tests/test_execution_leases.py`;
- `paper-trader/backend/tests/test_postgres_execution_leases.py`;
- `paper-trader/backend/tests/test_portable_concurrency_integration.py`.

Direct PostgreSQL tests cover two-instance double-spend contention, stale fence,
closed batch, stable tie, duplicate convergence, complete rollback, failover-
after-commit response loss, active reservation balance and exact outbox. SQLite is
local parity only. Mutations remove the head lock, lease fence, complete-batch
write, payload identity and unique idempotency.

No provider/broker I/O occurs. The service cannot submit an order.

## Slice 4: paper-shadow, reservation recovery and lineage

Capsule: `phase5-capital-admission-shadow-recovery`

Observable result: an explicit paper/mock harness records new admission receipts
beside the current allocator result and proves byte-equivalent compatibility.
Reservation/command/fill fixtures drive every recovery transition and campaign/
tranche allocation. The new decision cannot control the current allocator or an
order.

Owned paths:

- `paper-trader/backend/app/execution/capital_shadow.py`;
- `paper-trader/backend/app/execution/capital_recovery.py`;
- `paper-trader/backend/app/execution/position_lineage.py`;
- `paper-trader/backend/scripts/capital_admission_shadow.py`;
- `paper-trader/backend/tests/test_capital_admission_shadow.py`;
- `paper-trader/backend/tests/test_capital_admission_recovery.py`;
- `paper-trader/backend/tests/test_position_campaign_lineage.py`;
- `paper-trader/backend/tests/test_money_repository_isolation.py`;
- `paper-trader/backend/tests/test_book_isolation.py`.

Required cases: current allocator parity, crash before command, sent-unknown,
partial fill, broker rejection, margin fall, late acknowledgement, expiry,
cancel/fill crossing, external order, takeover, opposing campaigns, addition,
partial reduction, full close, exact held inventory, legacy visibility and
risk-reducing exit during every entry block. Provider, live broker and order
submission functions are tripwired.

No runner/live-broker callsite is added. Shadow generation is explicit and
paper/mock-only.

## Slice 5: capital assurance and critical review

Capsule: `phase5-capital-admission-assurance`

Product and tests are read-only. The owner freezes all prior hashes, independently
recomputes policies, states, transitions, consumers, side effects, tables and
writer callsites, reruns decisive SQLite/PostgreSQL traces, audits mutations and
builds the exact package. One `critical-reviewer` on Sol high returns separate
SPEC and QUALITY verdicts. One focused recheck is permitted after a bounded
finding-owned correction; a second rejection stops for replanning.

Acceptance is only `locally_runnable`, migration-required, paper-shadow evidence.
No behavior switch follows.

## Slice 6: Phase 5 integration and final review

`phase5-implementation` remains the read-only evidence integration gate and now
depends on accepted capital assurance. It freezes all accepted Phase 5 hashes,
deployment obligations and the final review package.

`phase5-review` remains the sole Sol-high phase review. Its package includes the
capital ADRs, design, implementation plan, migration, transaction, shadow/recovery
and assurance evidence. SPEC and QUALITY must both pass before Phase 6 may become
ready. Phase review grants no deployment, production, live, order or money
authority.

## Migration, deployment and rollback ownership

| Dimension | Current owner | Exact evidence |
| --- | --- | --- |
| Build/dependencies | each implementation capsule | no new dependency unless declared and locked; pure Python preferred |
| Schema/migration | `phase5-capital-admission-schema` | SQLite/PostgreSQL empty/upgrade/restart/restore/downgrade refusal |
| Transaction/lease | `phase5-capital-admission-transaction` | real two-session/process PostgreSQL contention and mutations |
| Recovery/observability | `phase5-capital-admission-shadow-recovery` | state receipts, uncertainty, outbox/metrics diagnostics |
| Service topology/config/security | Phase 6 and V1 release | unproven in Phase 5 |
| Capacity | Phase 7 plus V1 release | only bounded local transaction evidence in Phase 5 |
| Production rollout/rollback | Phase 6/V1 and explicit owner gate | no deployment in Phase 5 |

Code rollback disables new shadow writes, preserves immutable decisions and
reservations, and forward-reconciles broker-touched facts. A destructive schema
downgrade is not the rollback path.

## Owner gates

Stop before live/paper authoritative behavior switch, material sizing/routing/
risk/execution changes, broker/order/customer-money effects, credentials,
provider networking, production data, destructive migration, deployment,
frontend, licence-sensitive adoption or legal/commercial decisions.

## Completion evidence

Architecture acceptance requires:

- three frozen ADRs and one unified design;
- exact serial capsules and programme dependency order;
- complete path ownership with no overlapping concurrent writer;
- all 24 contention/reservation tests plus sizing/product/lineage additions;
- reversible lock, fence, payload, no-resize, pending-order, conservative-release
  and exit-availability mutations;
- deployment matrix with no vague future owner;
- architecture validator, programme tests, protected hashes and clean diff.
