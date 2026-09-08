# Phase 5 capital-admission architecture

Date: 2026-08-25\
Decision: **KEEP + HARDEN**\
Highest architecture claim: **implementation-bound; no behavior switch**

## Operator outcome

When several strategies request entries or target-position changes at the same
time, Strategy OS can explain the complete candidate set, sizing inputs, stable
rank, admitted/rejected quantity, capital held, pending-order adjustment and
recovery state. A restart can reconstruct the same decision and cannot spend the
same capital twice. Existing paper/live positions, fills, exits and allocator
behavior remain authoritative until a separate owner-gated behavior switch.

## Existing architecture retained

The current system already has the authorities that must remain singular:

| Fact | Existing owner | P5 treatment |
| --- | --- | --- |
| What strategy executes | `execution_binding.bind` | unchanged; every new fact copies exact binding/attribution |
| One execution actor | `AccountExecutionLease` and fence epoch | sole admission writer fence |
| Broker mutation/recovery | `AccountExecutionCommand` | linked to reservation after commit; not replaced |
| Entry request and order evidence | `ExecutionIntent` + append-only `ExecutionOrderEvent` | pending/fill source for target delta and recovery |
| Book cash/P&L | `CapitalState(owner, account, paper/live book)` | remains cash authority; reservation is not cash |
| Current held inventory | `Position` | remains operational aggregate |
| Realized money | `Trade` and ledger facts | unchanged; additive lineage only |
| Current simultaneous allocation policy | `allocator.allocate` | compatibility oracle: fund all, else priority-greedy, no resize |

Audit evidence is `.agent/runs/phase5-capital-admission-architecture/audit.json`,
SHA-256 `7d2976881fcc0f74b860f6851e0243cf5b36c762ad1208855f58de2adb071346`.
It finds the allocator has one production call, the execution binding remains
canonical, and none of the proposed capital facts exists today.

## Invariants

1. Strategy, execution binding, product resolution, sizing, target request,
   candidate, batch decision, reservation, broker command, order/fill, position,
   campaign/tranche and money record remain separate facts.
2. Owner, broker account, paper/live book, deployment, strategy attribution,
   canonical instrument and fence epoch are exact at every write.
3. The account execution lease is the sole actor authority. A reservation never
   grants strategy or broker authority.
4. `CapitalState` owns cash. A reservation owns only a bounded entry-capital
   claim computed from an addressed snapshot.
5. `Position` owns current operational inventory. Campaign/tranche lineage never
   becomes a second position aggregate.
6. Broker margin is external final authority. No local estimate forces a broker
   order.
7. Paper and live books remain structurally separate and fail closed to live.
8. Entry admission cannot block marking, cancellation, reconciliation or
   risk-reducing exits.
9. No float, unordered collection, database row order, arrival order or worker
   identity decides capital rank or money equality.
10. Phase 5 records paper/shadow comparison receipts only. No new decision becomes
    authoritative for order selection without a later explicit owner gate.

## Architecture

```text
ExecutionBinding
      |
      v
ExecutionProductPolicy -> ResolvedExecutionProduct
      |
      v
SizingPolicy + addressed inputs -> SizingDecision
      |
      v
TargetPositionRequest -- held Position + pending intent/command evidence
      |
      v
CandidateIntent[] -> immutable DecisionBatch
      |
      v   current AccountExecutionLease + locked CapitalReservationHead
PortfolioAdmissionDecision[] + CapitalReservation[] + events/outbox
      |
      v   after commit only
AccountExecutionCommand -> ExecutionIntent/Event -> FillAllocation
      |
      v
Position operational aggregate + Campaign/Tranche lineage + Trade
```

There is no provider or broker call inside product resolution, sizing or the
admission transaction. Addressed market/margin facts are inputs obtained before
the transaction. Order submission is after commit.

## Contract shapes

### Execution Product Policy

ADR 0016 defines one pure policy seam. It consumes an exact binding, canonical
signal instrument, explicit decision time, addressed market/capability evidence,
owner/account/book/deployment and target purpose. It returns one resolved canonical
execution product with lot/step/tick constraints or a typed refusal.

Product policy does not size, reserve, submit, select a strategy or query a
provider. Current options/equity/futures logic is wrapped as compatibility
adapters and proved equivalent before any caller moves.

### SizingPolicy and SizingDecision

`SizingPolicy` is immutable and content-addressed. One primary sizing mode is
selected: fixed units/lots, fixed capital, capital percentage, equity percentage,
risk/stop-distance or volatility target. The policy explicitly orders:

- product lot/quantity step;
- integer rounding direction;
- minimum quantity/notional;
- per-position, strategy, sector and portfolio caps;
- fees, slippage and capital safety buffer;
- margin and availability constraint;
- group-resize permission.

All money values use integer minor units with ISO currency. Quantities are signed
integers. Rates use bounded fixed-point integers with declared scale. Price, stop
and volatility values use canonical fixed-point representation plus source,
observed/effective time and digest. Boolean values cannot enter numeric fields.
Non-finite, stale, absent or contradictory inputs refuse.

`SizingDecision` records policy/request/product addresses, every input digest,
requested raw quantity, rounded quantity, required capital, fees, caps, binding
constraint, reason code, decision time and digest. It is evidence, not an order.

### TargetPositionRequest

The request carries exact owner/account/book, deployment and strategy attribution,
canonical instrument, resolved product, signed desired quantity, policy/decision,
purpose, group and digest. It is single-use in one candidate/batch identity.

The target delta uses exact held quantity plus unresolved order quantities from
`ExecutionIntent`, `ExecutionOrderEvent` and `AccountExecutionCommand`. All source
identities enter the digest. Unknown broker state blocks entry/addition; reductions
use the existing risk-reducing path.

### CandidateIntent

An immutable pre-order fact with:

- candidate id and semantic/content address;
- owner/account/book/currency and current fence epoch observed;
- deployment, exact strategy/admission/graph attribution;
- canonical signal and resolved execution instruments;
- product, sizing decision and target request addresses;
- direction/purpose, requested quantity and required capital minor units;
- group id and `INDEPENDENT|ATOMIC|RESIZABLE` semantics;
- freshness deadline and complete frozen rank tuple;
- held/pending evidence digest and created time.

It cannot hold or mutate capital.

### DecisionBatch

An immutable closed set with:

- batch id, owner/account/book/currency and accepted lease epoch;
- decision/effective time;
- `CapitalState` identity/revision or snapshot digest;
- broker margin amount/source/time/digest;
- active-reservation total and reservation-head revision;
- safety buffer and portfolio/risk/product/sizing policy addresses;
- sorted candidate semantic addresses and candidate-set digest;
- contention policy and stable tie-break policy version;
- terminal `decided|refused` state, refusal reason and digest.

Candidate membership is immutable after insertion. A duplicate batch digest for
the same account/fence/policy converges or refuses conflicting bytes.

### PortfolioAdmissionDecision

One immutable row per batch/candidate with `admitted|rejected|resized`, requested
and admitted quantity, required/held capital, score/rank tuple, binding constraints,
reason code/explanation, reservation id if admitted and digest. Every batch has one
decision for every candidate; no partial batch commit is valid.

### CapitalReservationHead

One row per owner/account/book/currency, FK-bound to the account, with monotone
revision and update time. It is the PostgreSQL row lock and replay cursor. It does
not store or derive cash.

### CapitalReservation and event

The reservation carries owner/account/book/currency, batch/candidate/decision,
estimated and consumed minor units, requested/admitted/consumed quantity, state,
fence epoch, expiry/reconcile times, command id and monotone revision. An append-
only event records every transition, evidence digest, actor epoch, reason and time.

States:

```text
held -> submission_pending -> partially_consumed -> consumed
  |             |                    |
  +-----------> released <-----------+
                ^
any uncertain/expired/taken-over state -> reconciliation_required
reconciliation_required -> partially_consumed | consumed | released
```

Expiry never releases by itself. Release requires exact evidence that no pending
order or exposure can consume the reservation.

### Campaign, tranche and fill allocation

ADR 0018 keeps `Position` operational. Add immutable campaign and tranche lineage
plus a unique fill-allocation mapping. Existing rows remain visible with null or
`legacy_unattributed` lineage; no quantity/time/key inference is accepted.

## Deterministic admission policy

The compatibility policy is
`FUND_ALL_ELSE_PRIORITY_GREEDY_NO_RESIZE/1`:

1. evaluate atomic groups first as closed units;
2. if all valid candidates fit, admit all;
3. on shortfall, sort by the stored tuple:
   group priority, canonical instrument priority, explicit score, freshness,
   deployment id, candidate semantic address, final content digest;
4. admit greedily; never solve a max-fill optimization;
5. reject unfunded candidates for this batch;
6. resize only when group semantics and sizing policy explicitly allow it, with
   integer lot/step constraints and visible requested/admitted quantities.

Replay uses only durable batch facts and must produce byte-identical decisions,
reasons and reservations.

## Concurrency proof

The accepted writer is one caller-owned PostgreSQL transaction:

1. verify the current account lease token, holder and fence epoch;
2. `SELECT ... FOR UPDATE` the exact reservation head;
3. re-read current book capital, active reservations, unresolved intents/commands
   and addressed margin evidence;
4. verify the immutable candidate set and freshness;
5. insert the closed batch;
6. evaluate all groups using the stored tuple;
7. insert every decision, admitted reservation and initial event;
8. increment the head revision and append one owner/account outbox change;
9. commit atomically.

Unique constraints cover candidate semantic identity, batch content identity,
batch/candidate decision, reservation/decision, and event idempotency. A stale
lease/fence, head-revision race, duplicate conflicting byte set, or invalid numeric
fact has zero batch, decision, reservation, head or outbox effect.

Direct PostgreSQL tests use two sessions and two processes. Removing the account
head lock must admit double capital and fail the test. Removing the lease predicate
must let a stale actor write and fail. SQLite local tests use the shared reservation
primitive but do not receive production-concurrency credit.

## Pending-order and broker-uncertainty behavior

An admitted reservation is necessary but not sufficient for entry submission.
The command gateway requires the same owner/account/book, decision, reservation,
target delta, lease epoch and idempotency key. Sent-unknown, partial fill, late
acknowledgement, cancel/fill crossing, external order and takeover never trigger
blind retry or automatic release. They mark reconciliation required, retain the
conservative reservation and block new entries until broker evidence resolves the
amount. Fills consume monotonically and link to tranche allocation.

## Why-trade and why-not-trade receipt

The batch receipt is reconstructed from immutable candidate, sizing, target,
capital, pending-order, policy and rank facts. It reports:

- accepted/rejected/resized result and reason code;
- requested/admitted quantity and capital;
- stable rank and binding constraints;
- reservation/current state;
- pending/held evidence identities;
- exact strategy/product/sizing/policy addresses;
- replay digest.

Operator-facing read models are contracts only in Phase 5. No frontend work is
authorized.

## Migration and rollback

Execution migration `0041` is additive. Research remains at `0011`. New tables
use owner/account FKs, fixed-point/minor-unit constraints, content-digest checks,
immutability triggers and append-only events. Nullable additive links may be added
to `AccountExecutionCommand`, `ExecutionIntent`, `Position` and `Trade`; historical
bytes are preserved and no lineage is inferred.

Required evidence:

- empty install and exact-0040 upgrade on SQLite and PostgreSQL 16;
- transaction interruption/restart and model-DDL/constraint parity;
- destructive downgrade refusal after new facts exist;
- clean backup/restore comparison for all new rows, keys, sequences, functions,
  triggers and heads;
- code rollback disables new shadow writes but preserves decisions/reservations;
- broker-touched reservations use forward reconciliation, never deletion.

No production cutover, retained/encrypted backup, service topology, credentials,
capacity or live readiness claim follows. Exact future owners appear in the plan
and task capsules.

## Complete failure and test matrix

Required direct cases include:

1. fixed units/lots/capital/equity/risk/volatility sizing and every invalid numeric;
2. fees, caps, lot/step rounding and no-silent-resize mutation;
3. held plus pending target-delta parity for options/equity/futures;
4. two candidates/one fundable and fund-all compatibility;
5. stable equal-priority tie and deterministic replay;
6. independent, atomic and resizable groups;
7. two processes and two instances race one account;
8. stale lease/fence and duplicate batch/candidate;
9. crash before command, after send and before acknowledgement;
10. sent-unknown, broker reject, margin fall, partial fill, late acknowledgement,
    expiry, cancel/fill crossing and external order;
11. opposing strategies/campaigns share an instrument/account;
12. exact held inventory through add, partial reduce and close;
13. legacy rows remain visible and unattributed;
14. risk-reducing exit remains possible during every admission/reconciliation block;
15. mutations remove head lock, fence, uniqueness, payload identity, no-resize,
    pending-order subtraction, conservative uncertainty and exit bypass;
16. SQLite/PostgreSQL migration, interruption, restore and rollback evidence;
17. shadow decisions are byte-compared with the current allocator and can never
    control an order.

## Deployment impact

Classification is `architecture-changing` and `migration-required` for
implementation. The only Phase 5 runtime claim is locally runnable paper/shadow
evidence. Exact implementation capsules own build/dependency, migration,
transaction, shadow/recovery and assurance rows. `phase5-research-runtime-
packaging` retains production worker/service packaging where applicable. Phase 6
and V1 retain topology, configuration, health, security, deployment, rollback and
release rehearsal. Actual deployment remains owner-gated.

## Owner gates and nonclaims

Stop before a schema/product path not owned by an implementation capsule, any
authoritative paper/live behavior switch, material live sizing/routing/risk/
execution decision, broker behavior, order, customer money, provider networking,
credentials, deployment, production data, destructive migration, frontend or
legal/commercial decision.

This architecture does not claim that a production executor, capability sandbox,
service, deployment or live capital admission exists. It authorizes only the
dependency-ordered implementation and evidence slices in the accompanying plan.

## Verdict

`KEEP + HARDEN`. The present seam need is durable deterministic admission under
the existing account lease, not a new allocator, money ledger, position aggregate
or execution path. The smallest safe sequence is pure contracts, additive schema,
unwired transaction service, paper/shadow comparison and independent assurance,
followed by the sole final Phase 5 review.
