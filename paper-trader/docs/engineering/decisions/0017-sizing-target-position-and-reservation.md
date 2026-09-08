# ADR 0017: Sizing, target position and capital reservation are separate durable facts

- **Status:** FROZEN FOR PHASE 5 IMPLEMENTATION; NO BEHAVIOR SWITCH
- **Date:** 2026-08-25
- **Depends on:** ADR 0012, ADR 0016, account execution leases, execution intent/event lifecycle

## Context

The current allocator accepts fixed-cost candidates, sorts by canonical instrument
priority, greedily funds a subset under shortfall, never silently resizes, and
drops unfunded candidates for that cycle. It is in-process and cannot prove which
simultaneous candidate set, capital snapshot or pending order produced a result.
Dynamic target positions therefore require durable decision and reservation facts
before they can become authoritative.

## Decision

Keep the allocator as the compatibility policy. Add distinct content-addressed
facts for sizing, target request, closed batch admission and reservation. The
account execution lease remains the sole actor/fence authority. `CapitalState`
remains book cash/P&L authority. `ExecutionIntent` and `ExecutionOrderEvent`
remain order and fill evidence. A reservation is a bounded claim against available
entry capital, not cash, a signal, a position or a broker order.

## Sizing hierarchy

One `SizingPolicy` selects exactly one primary mode:

1. fixed units or fixed lots;
2. fixed capital amount;
3. percentage of available book capital;
4. percentage of account equity;
5. risk budget divided by explicit stop distance;
6. volatility-target quantity from an addressed volatility input.

All modes then apply explicit ordered constraints: resolved product lot/step,
integer rounding, minimum quantity, per-position and portfolio caps, fees,
slippage/safety buffer, concentration limits and available margin. Every dynamic
numeric input is finite, typed, timestamped and source-addressed. Missing or
invalid stop, volatility, price, equity, fee or margin facts refuse; zero is never
invented as a safe default.

`SizingDecision` records requested and rounded quantities, every input address,
binding constraint, policy address, reason code and digest. Silent resize is
forbidden. Resizing exists only for an explicitly `RESIZABLE` intent group and
records requested versus admitted quantity.

## Target position and pending orders

`TargetPositionRequest` records a signed desired quantity for one owner, account,
book, deployment, strategy attribution, canonical instrument and resolved product.
It does not mutate `Position`.

The executable delta is derived from:

```text
target quantity
- exact held quantity
- same-direction unresolved/pending quantity
+ opposite-direction unresolved/pending quantity
= requested delta
```

Held quantity comes from the operational `Position`; pending quantity comes from
`ExecutionIntent`, `ExecutionOrderEvent` and unresolved `AccountExecutionCommand`
facts. The derivation records the complete identities used. A pending/held
contradiction or broker-uncertain command blocks new entries and additions. A
risk-reducing target delta remains available through the existing exit/reduction
authority and does not wait for entry reservation.

## Closed batch admission

The durable facts are:

- immutable `CandidateIntent` for each sizing/target request;
- immutable `DecisionBatch` with owner/account/book/currency, current fence epoch,
  capital/margin/pending/reservation snapshots, candidate-set digest, policies and
  deterministic tie-break tuple;
- immutable `PortfolioAdmissionDecision` for each candidate;
- `CapitalReservationHead`, one lock/revision row per owner/account/book/currency;
- `CapitalReservation`, one current reservation with monotone revision;
- append-only `CapitalReservationEvent` transitions and why/why-not receipt.

The head serializes decisions; it does not own cash. Candidate, batch, decision,
reservation, command, intent, fill and position remain separate identities.

## Deterministic policy

Compatibility mode is `FUND_ALL_ELSE_PRIORITY_GREEDY_NO_RESIZE`. Ranking freezes
group semantics, current canonical instrument priority, optional explicit score,
freshness deadline, deployment id, candidate semantic address and final digest.
The full tuple is stored before evaluation. Database order, arrival order, Python
hash order and worker identity never decide a tie.

Groups are `INDEPENDENT`, `ATOMIC` or explicitly `RESIZABLE`. Atomic groups are
all-or-none. Resizable groups use the sizing policy's integer/lot quantizer and
cannot cross minimums or caps.

## PostgreSQL transaction and fencing

For one owner/account/book/currency:

1. verify the current `LeaseToken` and fence epoch;
2. lock `CapitalReservationHead` with `SELECT ... FOR UPDATE`;
3. re-read `CapitalState`, active reservations, unresolved commands/intents and
   addressed broker margin snapshot;
4. insert the immutable closed candidate set and batch digest;
5. reject stale/non-finite inputs;
6. evaluate every group with the frozen stable tuple;
7. insert all decisions and admitted reservations;
8. increment the head revision;
9. commit batch, decisions, reservations, events and outbox together.

No broker or provider I/O occurs while the transaction is open. Submission begins
after commit and requires the active reservation, current fence, exact decision,
command idempotency key and target quantity. SQLite uses the existing reservation
primitive only for local equivalence; direct PostgreSQL concurrency is the
authoritative transaction proof.

## Reservation lifecycle and recovery

States are `held`, `submission_pending`, `partially_consumed`, `consumed`,
`released` and `reconciliation_required`. Expiry is a reconciliation trigger, not
proof of release. No state is deleted.

- `held -> submission_pending` only with a prepared fenced command;
- acknowledgement/fill consumes the exact quantity/capital monotonically;
- known rejection or proved-no-order may release;
- timeout, sent-unknown, fence takeover, external-order conflict, cancel/fill
  crossing or stale broker snapshot enters `reconciliation_required`;
- replacement epochs retain old reservations until broker evidence proves release;
- new entries block while uncertain reserved capital may exist;
- risk-reducing exits remain available.

Duplicate candidate/batch/command delivery converges through content identity,
unique constraints and idempotency keys. A stale fence can write no batch,
decision, reservation, command or state event.

## Rollout boundary

Phase 5 may create additive schema, direct transaction evidence and paper/shadow
receipts that compare the new decision to the current allocator. It may not make
the new result authoritative for live or paper order selection. Any behavior
switch requires a separate owner decision after the money-critical review.
