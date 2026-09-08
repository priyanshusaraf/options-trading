# Academic PDF and course-notes packet

## Decision summary

The academic sources strengthen five bounded contracts: explicit time dimensions,
operation-specific concurrency, complete trial populations, selection-free OOS,
and deterministic failure testing. They do not justify a temporal database,
distributed transaction system, stream processor, proof assistant or new runtime.

## PDF inspection ledger

| Source | Pages/sections inspected | Figures/formulas | Applicability |
| --- | --- | --- | --- |
| Kulkarni and Michels, *Temporal features in SQL:2011* | PDF pp. 33–41: periods, application time, system versioning, bitemporal queries | Closed-open intervals; start-before-end constraint; application/system-time query example | `ADAPT AS BOUNDED INTERNAL CONTRACT`: explicit columns, effective-dated facts and cutoff queries. |
| Bailey and López de Prado, *Deflated Sharpe Ratio* | PDF pp. 2–12, especially multiple testing and DSR equations | Expected maximum Sharpe and DSR inputs; equation screenshots inspected | `DIRECTLY APPLY IN CURRENT STACK`: persist complete trial population and distribution inputs before accepting a DSR claim. |
| Bailey et al., *Probability of Backtest Overfitting* | PDF pp. 1–13, CSCV/PBO definitions | IS-optimal/OOS-rank definition and PBO framework; equation screenshots inspected | `DIRECTLY APPLY IN CURRENT STACK`: immutable candidate matrix, split population and selection rule. |
| Bailey et al., *Backtest overfitting in financial markets* | Introduction and multiple-testing discussion | No new formula adopted | `ADD TEST/OBSERVABILITY ONLY`: preserve every attempted trial and repeated OOS access. |
| Bailis et al., *Coordination Avoidance in Database Systems* | Abstract, invariant-confluence framing and conclusions | No implementation copied | `REFERENCE ONLY`: coordinate only predicates that can violate named invariants. |
| Gray, *A Transaction Model* | Abstract and contents covering restart, serial history, locks and deadlock | No implementation copied | `REFERENCE ONLY`: transaction, external effect and recovery remain separate proof boundaries. |
| Lamport, *Time, Clocks, and the Ordering of Events* | Official abstract/metadata | No algorithm imported | `REFERENCE ONLY`: timestamps cannot reconcile independently delivered broker facts. |
| Akidau et al., *The Dataflow Model* | Abstract and event-time/late-data system model | No Beam implementation reviewed | `REFERENCE ONLY`: completion/availability/correction policy, without Beam machinery. |
| Cambridge Distributed Systems notes | Inherited Chat 1 full 91-page visual review | Clocks, transactions, replication, failure models | `RETAIN CHAT 1`: conceptual counter-source; not Strategy OS architecture authority. |

## Temporal model conclusion

The smallest sufficient Strategy OS model is not a generic bitemporal database.
The repository needs exact meanings for:

```text
event/effective time      when the market or rule fact applies
completed time            when an interval is final under its contract
available/publication time when the source could first reveal it
recorded/transaction time when Strategy OS persisted this version
revision identity         which correction/version is being used
knowledge cutoff          which recorded facts a historical run may see
```

Closed-open periods and a start-before-end constraint are useful where a rule or
instrument master has an effective interval. Immutable addressed snapshots remain
preferable for research evidence. A system-versioned table is only reconsidered if
current correction queries become unmaintainable and a direct migration comparison
shows lower risk than explicit version rows.

## Research-validity conclusion

DSR and PBO are properties of a declared experiment population, not adornments on
one selected result.

- DSR requires the effective number/dependence of trials, dispersion of trial
  Sharpes, sample length and non-normal return moments.
- PBO/CSCV requires the full candidate performance matrix and a fixed selection
  rule across symmetric IS/OOS partitions.
- Neither method repairs OOS that already influenced qualification or selection.
- Repeated OOS access changes the evidence state and must remain in history.
- A statistically correct method cannot repair impossible contract history,
  provider substitution, omitted costs or same-bar execution leakage.

## Coordination and testing conclusion

Use the weakest contract that protects the named invariant:

| Invariant | Minimum evidence direction |
| --- | --- |
| Capital cannot be double reserved | One transaction over exact available-capital predicate plus concurrent/restart histories. |
| One job claimant may finalize | Owner/token/expiry predicate, bounded termination and PostgreSQL process-kill takeover. |
| A duplicate request cannot change intent | Token plus stored canonical parameter bytes and mismatch refusal. |
| UI projection may lag | Durable source fact, bounded cursor/resync and explicit stale state. |
| Broker terminal observations conflict | Preserve raw facts and versioned reconciliation partial order; wall-clock ordering is insufficient. |

FoundationDB’s testing work supports deterministic seeds and fault schedules, but a
repository-wide simulator would exceed the current failure model. Direct process,
transaction and mutation probes remain the proportional choice.

## Inspection limitations

- SQL:2011 PDF extracted text was inspected for all relevant pages; screenshot
  retrieval timed out for later pages, so visual review is incomplete.
- DSR and PBO equation pages received screenshot receipts, but no independent
  numerical re-derivation was performed in this source packet.
- Gated DDIA second-edition text remains unread and is not used.
- Statistical method acceptance still needs code-level reconstruction and synthetic
  counterexamples in the current repository.
