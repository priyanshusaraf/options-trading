# Initial priority reading map

The original twenty sources came from the mandatory starting set. The continuation
added the official DDIA 2e author page and exact PDF records for the three reviewed
papers. Seven first-party records are fully read. Numeric scores are present only
after source/code screening; title-only seeds retain nulls.

| Order | Source | Strategy OS question | Reading state |
| --- | --- | --- | --- |
| 1 | [How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) | Paused-worker writes and sink-side fences | fully_read |
| 2 | [Hermitage: Testing the “I” in ACID](https://martin.kleppmann.com/2014/11/25/hermitage-testing-the-i-in-acid.html) | Concrete anomalies, not isolation labels | fully_read |
| 3 | [New courses on distributed systems and elliptic curve cryptography](https://martin.kleppmann.com/2020/11/18/distributed-systems-and-elliptic-curves.html) | First-party route to Cambridge causal/failure foundations | fully_read; linked 91-page notes fully read and visually inspected |
| 4 | [Accounting for Computer Scientists](https://martin.kleppmann.com/2011/03/07/accounting-for-computer-scientists.html) | Exact units and conservation; existing financial objects only | not_read |
| 5 | [Using logs to build a solid data infrastructure (or: why dual writes are a bad idea)](https://martin.kleppmann.com/2015/05/27/logs-for-data-infrastructure.html) | Atomic source-of-truth change versus separate notification | not_read |
| 6 | [Please stop calling databases CP or AP](https://martin.kleppmann.com/2015/05/11/please-stop-calling-databases-cp-or-ap.html) | Specify safety and liveness rather than CAP shorthand | not_read |
| 7 | [Attiya and Welch: Sequential Consistency versus Linearizability](https://martin.kleppmann.com/2015/07/08/attiya-welch-at-papers-we-love.html) | Ordering and stale-read contracts for authority | not_read |
| 8 | [Transactions: Myths, Surprises and Opportunities](https://martin.kleppmann.com/2015/11/04/transactions-at-code-mesh.html) | Mixed transactions, retries, and real isolation | not_read |
| 9 | [Java's hashCode is not safe for distributed systems](https://martin.kleppmann.com/2012/06/18/java-hashcode-unsafe-for-distributed-systems.html) | Stable strategy/data/cache identity | not_read |
| 10 | [Schema evolution in Avro, Protocol Buffers and Thrift](https://martin.kleppmann.com/2012/12/05/schema-evolution-in-avro-protocol-buffers-thrift.html) | Old/new readers, semantic versioning, rollback | not_read |
| 11 | [Rethinking caching in web apps](https://martin.kleppmann.com/2012/10/01/rethinking-caching-in-web-apps.html) | Cache loss and rebuild without false results | not_read |
| 12 | [The probability of data loss in large clusters](https://martin.kleppmann.com/2017/01/26/data-loss-in-large-clusters.html) | Correlated loss and restore assumptions | not_read |
| 13 | [Making Sense of Stream Processing](https://martin.kleppmann.com/2016/05/24/making-sense-of-stream-processing.html) | Ordering, derived state and rebuildability | landing page not read; linked 183-page PDF fully read and visually inspected |
| 14 | [Online Event Processing: Achieving consistency where distributed transactions have failed](https://martin.kleppmann.com/2019/05/01/olep-cacm.html) | Atomic effects and multi-system boundary | landing page not read; linked 21-page PDF fully read and visually inspected |
| 15 | [Prediction: AI will make formal verification go mainstream](https://martin.kleppmann.com/2025/12/08/ai-formal-verification.html) | Bounded executable invariants and independent checks | not_read |
| 16 | [Six things I wish we had known about scaling](https://martin.kleppmann.com/2014/03/26/six-things-about-scaling.html) | Measure actual bottlenecks before infrastructure | not_read |
| 17 | [System operations over seven centuries](https://martin.kleppmann.com/2013/08/12/system-operations-over-seven-centuries.html) | Recovery and long-term operator obligations | not_read |
| 18 | [The complexity of user experience](https://martin.kleppmann.com/2012/10/08/complexity-of-user-experience.html) | Failure-state clarity and user-visible uncertainty | not_read |
| 19 | [Local-first software: You own your data, in spite of the cloud](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html) | Export/restore now, collaboration semantics later | landing page not read; linked 25-page PDF fully read and visually inspected |
| 20 | [Verifying distributed systems with Isabelle/HOL](https://martin.kleppmann.com/2022/10/12/verifying-distributed-systems-isabelle.html) | Proof/implementation correspondence; URL must be matched to inventory | not_read |
| 21 | [Designing Data-Intensive Applications, second edition](https://martin.kleppmann.com/2026/03/24/designing-data-intensive-applications-2e.html) | Official route to the mandatory public delta | fully_read author page; official TOC and exact companion references reviewed; book text unavailable |
