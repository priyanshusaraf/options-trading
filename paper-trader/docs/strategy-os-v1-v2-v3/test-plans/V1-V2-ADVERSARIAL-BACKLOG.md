# V1 and V2 adversarial test backlog

Status: implementation-ready recommendations

No test was added or run in this documentation slice. The user authorized recommendations only. The highest-risk cases below include setup, action, expected result, and guard mutation so a future capsule can implement them without re-deciding the contract.

## Harness rules

- Use real domain services and persistence boundaries.
- Use deterministic fake providers and brokers.
- Open no live credential and send no live order.
- Run critical money tests on SQLite compatibility and isolated PostgreSQL 16 where the contract requires both.
- Log full output under the future capsule's ignored evidence directory.
- Kill and restore every mutated guard.
- Refuse aggregate counts as semantic proof.

## Tier 0 implementation-ready tests

### T0-01: one account, two actors, one reservation winner

Setup:

- one owner and broker account;
- current account lease holder;
- ₹8,000 locally reservable;
- two independent candidates requiring ₹6,000 each;
- fixed priority order.

Action:

- two database sessions attempt to admit the same frozen batch concurrently.

Expected:

- one current lease holder and one batch transaction win;
- exactly one candidate admits;
- exactly one reservation exists;
- rejected candidate records INSUFFICIENT_CAPITAL;
- no total active reservation exceeds ₹8,000.

Mutation:

- remove account lock or lease-epoch predicate.

Mutation expectation:

- test observes two admissions or an explicit invariant violation.

Owner: v1-portfolio-admission-reservation.

### T0-02: stale actor after takeover

Setup:

- actor A holds epoch 4;
- lease expires;
- actor B takes epoch 5.

Action:

- A attempts admission, reservation, command, and release.

Expected:

- every write refuses;
- no reservation or command changes;
- fence rejection is recorded;
- B remains current.

Mutation:

- remove fence epoch from one write predicate.

Expected mutation result:

- exact operation becomes possible and the test fails.

### T0-03: crash after reservation before broker send

Setup:

- committed RESERVED row;
- no execution command sent.

Action:

- terminate holder;
- take over at higher epoch;
- reconcile broker with no matching order.

Expected:

- reservation releases idempotently;
- no order is sent by recovery;
- candidate may be reconsidered only in a new batch.

Mutation:

- recovery retries the old candidate directly.

### T0-04: crash after send before acknowledgement

Setup:

- reservation and prepared command;
- fake broker accepts order and drops response.

Action:

- terminate holder;
- replacement reconciles by broker correlation key.

Expected:

- no duplicate order;
- command becomes acknowledged or resolved from broker fact;
- reservation remains active or consumes from fills.

Mutation:

- blind retry without reconciliation.

### T0-05: atomic basket cannot partially reserve

Setup:

- three-leg ATOMIC_BASKET;
- capital covers two legs only.

Action:

- run portfolio admission.

Expected:

- all legs reject;
- no reservation;
- reason names incomplete basket funding.

Mutation:

- insert per-leg greedy reservation.

### T0-06: silent resize refused

Setup:

- fixed-quantity independent candidate;
- capital covers half.

Action:

- run a policy implementation that returns smaller quantity.

Expected:

- admission refuses POLICY_VIOLATION;
- no reservation.

Mutation:

- remove explicit resizable-group check.

### T0-07: watchlist edit cannot mutate deployment Universe

Setup:

- editable watchlist with A and B;
- deployment bound to immutable snapshot of A and B.

Action:

- remove B and add C to the watchlist.

Expected:

- deployment still resolves A and B;
- new snapshot resolves A and C;
- addresses differ;
- B remains manageable if held.

Mutation:

- deployment reads current membership by watchlist ID.

### T0-08: dynamic candidate idempotency

Setup:

- exact Universe evaluation and Strategy version;
- candidate A ranked third.

Action:

- deliver discovery twice;
- restart between deliveries.

Expected:

- one CandidateInstance;
- one Workflow branch;
- at most one deployment command;
- duplicate receipt names existing identity.

Mutation:

- generate identity from current time or random UUID.

### T0-09: stale approval

Setup:

- approval binds candidate, Strategy, Universe evaluation, evidence, and proposed deployment.

Action:

- change Strategy version, Universe evaluation, evidence, provider binding, or risk policy one at a time.

Expected:

- each material change makes approval stale;
- execution path refuses before reservation.

Mutation:

- approval stores only boolean approved.

### T0-10: current-pairlist historical bias

Setup:

- historical membership differs from today's list;
- a delisted losing member exists.

Action:

- attempt Dynamic Universe backtest with today's list.

Expected:

- point-in-time replay refuses or includes historical member;
- current list can never produce an evidence-grade PASS.

Mutation:

- replace historical evaluation with current provider dump.

### T0-11: provider token reuse

Setup:

- provider token X maps to instrument A until time T;
- token X maps to instrument B after T.

Action:

- resolve before, at, and after T;
- load an old dataset and a current order.

Expected:

- half-open intervals select one mapping;
- old dataset stays on A;
- current order uses B only when its canonical target is B;
- overlapping mappings refuse.

Mutation:

- resolve token without effective time.

### T0-12: risk-reducing exit during entry block

Setup:

- open position;
- ARM off;
- provider capability degraded;
- reservation system blocked;
- valid risk-reducing exit route.

Action:

- request new entry and exit.

Expected:

- entry refuses;
- exit reaches normal execution and reconciliation.

Mutation:

- place reservation or ARM check around all commands.

## Tier 1 contract tests

| ID | Scenario | Expected result | Owner |
| --- | --- | --- | --- |
| T1-01 | equal candidate priority | stable canonical candidate address breaks tie | reservation capsule |
| T1-02 | broker margin drops after reservation | broker rejection recorded; unused reservation releases | reservation capsule |
| T1-03 | partial fill | consumed and released amounts sum to reservation | reservation capsule |
| T1-04 | cancel and fill cross | reducer converges to same exposure under both orders | execution lifecycle |
| T1-05 | external manual order changes margin | old batch not reused | reservation capsule |
| T1-06 | sector limit rejects top raw rank | reason names portfolio constraint | portfolio admission |
| T1-07 | duplicate decision batch | existing immutable decisions returned | reservation capsule |
| T1-08 | reservation expiry and late acknowledgement | reconciliation-required, not silent release | reservation capsule |
| T1-09 | open position leaves Universe | no new entry; position data and exit stay active | Universe capsule |
| T1-10 | ranking input order permuted | same rank and snapshot address | cross-sectional types |
| T1-11 | score tie at top-K boundary | explicit policy gives same members | Universe capsule |
| T1-12 | hysteresis threshold oscillation | bounded membership churn | Universe V2 |
| T1-13 | Workflow duplicate step | one domain receipt | Workflow boundary |
| T1-14 | Workflow cancel races complete | caller receives cancelled or too-late | Workflow boundary |
| T1-15 | Workflow retry after process death | no duplicate deployment or order | Workflow boundary |
| T1-16 | current research operation versus DBOS spike | same domain receipts under kill/restart | durable-work spike |
| T1-17 | cross-instrument missing bar | entry refuses under alignment policy | causal data |
| T1-18 | higher-timeframe forming bar | only last completed input reaches Strategy | causal data |
| T1-19 | future bars appended | earlier node outputs unchanged | every new component |
| T1-20 | recursive warmup | nested chain has correct first valid bar | IR causal |
| T1-21 | dataset correction | cache and assessment address change | data authority |
| T1-22 | missing manifest child | parent publication refuses | dataset authority |
| T1-23 | market-rule gap | no current-rule fallback | market truth |
| T1-24 | ReplayProvider sees future bar | test fails on cursor slice mutation | replay |
| T1-25 | general event replay order | identical event frontier after restart | V2 replay |
| T1-26 | browser socket connected, provider stale | UI displays stale, not live | realtime UI |
| T1-27 | subscription ack without event | state remains awaiting first event then stale | subscription planner |
| T1-28 | option window recenter | new contracts healthy before old exploratory removal | subscription planner |
| T1-29 | slow browser | engine loop and other clients remain current | WS manager |
| T1-30 | private stream loss | entries block and reconciliation starts | broker realtime |

## Tier 2 security and deployability tests

| ID | Scenario | Expected result | Owner |
| --- | --- | --- | --- |
| T2-01 | cross-tenant valid content address | not found or refused without disclosure | tenancy |
| T2-02 | revoked membership on open WebSocket | channel closes or reauthorizes before next private frame | tenancy |
| T2-03 | credential ciphertext tamper | decrypt refuses, no stale token reuse | credential |
| T2-04 | wrong broker builder | construction refuses before network call | broker registry |
| T2-05 | webhook replay | duplicate and stale requests refuse | external ingress V2 |
| T2-06 | chart revision after deployment | deployed dependency remains unchanged | chart V2 |
| T2-07 | custom code reads environment | sandbox refuses | custom code future |
| T2-08 | compressed upload exceeds ratio | quarantine and bounded refusal | data admission V2 |
| T2-09 | CSV formula export | formula neutralized | data admission V2 |
| T2-10 | unsupported migration marker | no schema or row write | foundation migration |
| T2-11 | migration interruption | restart reaches exact head or refuses safely | migration owner |
| T2-12 | clean restore | table, digest, trigger, sequence, and cross-plane checks pass | release deployability |
| T2-13 | old primary returns | higher epoch and network isolation prevent writes | restore |
| T2-14 | outbox duplicate after effect | consumer result remains one | outbox |
| T2-15 | poisoned outbox event | cursor does not advance silently | outbox |

## Reconstruction mutations

1. Change one node implementation under the same graph reference.
2. Change one dataset byte.
3. Change one market-rule record.
4. Change one fee rounding rule.
5. Change one candidate tie-break.
6. Change one fill timestamp.
7. Remove one reservation event.
8. Change one provider alias interval.

Each mutation must produce the expected first-divergence stage.

## Completion rule

An implementation capsule may claim one row only when:

- it implements the real boundary;
- the normal test passes;
- the named mutation fails it;
- restoration passes;
- evidence records exact code and test bytes;
- deployability impact is current;
- critical rows receive the required independent review.
