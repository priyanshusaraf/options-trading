# Capital contention and reservation specification

Status: architecture recommendation

Risk: critical money and authority boundary

## Decision

Keep the account execution lease as the single-writer authority. Add a durable portfolio-admission batch and account capital-reservation ledger before dynamic candidates or broader multi-instance live work.

The current in-process allocator remains the compatibility policy:

- fund all candidates when capital covers all;
- otherwise use deterministic priority subset;
- do not resize silently;
- drop unfunded candidates for that decision cycle.

The new facts make that decision replayable and recoverable.

## Conceptual separation

    strategy signal
      → CandidateIntent
      → DecisionBatch
      → PortfolioAdmissionDecision
      → CapitalReservation
      → ExecutionAuthorization
      → broker command
      → order events and fills
      → reservation consumption or release

A signal does not own capital.

## Durable facts

### CandidateIntent

- candidate_intent_id;
- owner and broker account;
- candidate-instance address;
- deployment;
- exact Strategy and admission;
- canonical execution instrument;
- direction;
- requested quantity or sizing intent;
- estimated capital;
- group ID and group semantics;
- freshness deadline;
- frozen priority inputs;
- created time;
- content digest.

### DecisionBatch

- decision_batch_id;
- owner and broker account;
- account lease epoch;
- decision time;
- margin snapshot and source;
- existing reservation total;
- safety buffer;
- portfolio and risk policy versions;
- candidate-set digest;
- contention policy;
- tie-break policy;
- terminal status;
- content digest.

### PortfolioAdmissionDecision

- decision ID;
- batch and candidate;
- admitted, rejected, or resized;
- admitted quantity;
- required capital;
- score and rank inputs;
- binding constraints;
- reason code and explanation;
- reservation ID when admitted.

### CapitalReservation

- reservation ID;
- owner and broker account;
- batch and candidate;
- currency;
- estimated amount;
- consumed amount;
- state;
- fence epoch;
- created time;
- expiry;
- broker command ID;
- release or consumption reason;
- last reconciliation time;
- revision.

## Intent-group semantics

| Group type | Rule |
| --- | --- |
| ATOMIC_BASKET | All legs admit and reserve together or every leg rejects |
| INDEPENDENT_CANDIDATES | A deterministic subset may admit |
| RESIZABLE_ALLOCATION | Quantity may change only under an explicit sizing policy |

No unlabelled group exists.

## Contention policies

| Policy | V1 status | Rule |
| --- | --- | --- |
| BASKET_OR_NONE | supported architecture | reject incomplete basket |
| PRIORITY_SUBSET | default | deterministic greedy subset |
| MAXIMIZE_ADMISSION_SCORE_UNDER_CAPITAL | later opt-in | solver receipt and stable tie-break required |
| PRO_RATA_RESIZE | later opt-in | explicit group and integer-lot policy required |
| REJECT_EXCESS | supported architecture | reject after available amount is used |
| HUMAN_APPROVAL | supported architecture | hold no capital until an approved reservation command |

## Deterministic rank

Recommended ordered tuple:

1. policy priority class;
2. frozen Universe or Workflow rank;
3. normalized portfolio-admission score;
4. explicit user secondary rank;
5. canonical candidate-intent address.

Do not use:

- worker arrival;
- thread timing;
- database insertion order;
- unordered map iteration;
- broker response order;
- random UUID order.

The current instrument priority may feed priority class, but the batch freezes its value and policy version.

## Reservation balance

At transaction time:

    broker-reported available margin
    - active local reservations
    - conservative safety buffer
    = locally reservable capital

The broker remains final authority. The local ledger prevents Strategy OS actors from overcommitting the same observed amount.

## Concurrency proof

The proposed proof has four layers:

1. Account execution lease:
   one current actor per owner and broker account, with fence epoch.

2. Database transaction:
   lock the account reservation head or use a transaction-scoped account lock.

3. Closed batch:
   insert the immutable candidate set and policy before individual decisions.

4. Unique idempotency:
   candidate semantic identity and batch ID prevent duplicate admission and reservation.

Transaction outline:

1. Verify current lease token and epoch.
2. Lock the account reservation head.
3. Re-read current broker snapshot and active reservations.
4. Refuse stale candidate inputs.
5. Evaluate the complete batch deterministically.
6. Insert all decisions.
7. Insert reservations for admitted candidates.
8. Update the reservation head revision.
9. Commit decisions and reservations together.

Order submission occurs after commit. Each command must present an active reservation and matching fence epoch.

## Reservation state machine

    RESERVED
      → SUBMISSION_PENDING
      → SUBMITTED_UNKNOWN or ACKNOWLEDGED
      → PARTIALLY_CONSUMED
      → CONSUMED

Release branches:

    RESERVED → EXPIRED
    RESERVED → RELEASED
    SUBMISSION_PENDING → RELEASED when no command left the process
    ACKNOWLEDGED → RELEASED after confirmed broker rejection or cancellation
    PARTIALLY_CONSUMED → RELEASED for the unused balance after terminal reconciliation

Blocked branch:

    any uncertain state → RECONCILIATION_REQUIRED

The reservation record is never deleted.

## Broker uncertainty

Margin can change because of:

- price movement;
- another fill;
- manual or external order;
- fee or haircut change;
- broker-side reservation;
- stale account snapshot;
- partial fill;
- rejected or delayed request.

Controls:

- configurable safety buffer;
- bounded snapshot age;
- broker correlation key;
- query before retry;
- idempotent release;
- partial consumption;
- reconciliation before reconsideration;
- no automatic duplicate submission.

An external manual order may reduce available margin after local reservation. Broker rejection remains a normal terminal outcome. Strategy OS records it and releases or recalculates under a new batch. It does not reuse the old snapshot.

## Risk-reducing exits

ARM and reservation gates control entries only.

Risk-reducing exits:

- do not need a new entry reservation;
- remain available while new entries are blocked;
- may release existing reserved or consumed exposure after broker confirmation;
- retain exact position ownership and account lease checks.

## Why-trade and why-not-trade receipt

Each batch exposes:

- account and decision time;
- margin snapshot and age;
- existing reservations;
- safety buffer;
- candidate intents;
- group semantics;
- contention policy;
- complete rank tuple;
- portfolio constraints;
- admitted and rejected quantity;
- reservation result;
- broker outcome;
- consumption or release.

Example user explanation:

    ABC admitted for 143 shares.
    XYZ rejected because only ₹8,000 was locally reservable and ABC ranked first
    under Account Allocation Policy version 3.

## Recovery

After process death:

1. replacement takes the account lease at a higher epoch;
2. reconcile old-epoch commands and broker orders;
3. retain known active reservations;
4. release only when broker evidence proves no exposure or pending order;
5. mark ambiguous reservations reconciliation-required;
6. block new entries while uncertain reserved capital could exist;
7. keep risk-reducing exits available.

## Required tests

1. Two simultaneous candidates, one fundable.
2. Equal priority resolved by the complete stable tuple.
3. Atomic basket with insufficient capital.
4. Resizable group with integer-share and lot constraints.
5. Two application instances race the same account.
6. Stale lease attempts reservation.
7. Worker dies after reservation, before command.
8. Worker dies after command send, before acknowledgement.
9. Broker margin falls after reservation.
10. Partial fill consumes part of reservation.
11. Broker rejects one admitted candidate.
12. Reservation expiry races late acknowledgement.
13. Duplicate candidate delivery.
14. Duplicate batch submission.
15. Cancel and fill cross.
16. External manual order changes margin.
17. Opposing strategies share an account.
18. Sector constraint rejects higher raw priority.
19. Database failover after commit and before response.
20. Deterministic replay produces the same decisions.
21. Mutation removes account lock and the concurrency test fails.
22. Mutation removes fence check and the stale actor test fails.
23. Mutation permits silent resize and the group test fails.
24. Risk-reducing exit remains possible during admission block.

## Migration and rollback

Deployment impact: architecture-changing and migration-required.

Migration:

- add new tables and indexes;
- leave current intents and allocations unchanged;
- start as shadow receipt-only for paper mode;
- compare new decisions with current allocator;
- enable new writes only after exact parity for PRIORITY_SUBSET;
- do not enable live behavior without owner approval and critical review.

Rollback:

- disable new admission command;
- preserve all new records;
- return new entries to the current allocator only before any live authority switch;
- if new reservations reached broker effects, use forward repair and reconciliation, not reverse deletion.

## Verdict

REFACTOR. This is a V1 architecture and safety boundary. Implementation requires a dedicated owner and one independent critical review.
