# Strategy OS — Kleppmann + Professional Engineering Review Prompt V2

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [Strategy OS — Kleppmann + Professional Engineering Review Prompt V2](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md) | 1194 |
| [3. Build a machine-readable corpus manifest](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md) | 809 |
| [6. Mandatory Strategy OS audit domains](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md) | 1504 |
| [6.16 Backup, restore, correlated failure, and disaster recovery](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/04-616-backup-restore-correlated-failure-and-disaster-recovery.md) | 794 |
| [9. Test and fault-injection programme](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md) | 1015 |
| [14. Definition of done](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md) | 1529 |
| [16.7 Credential, device, session, and key lifecycle](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/07-167-credential-device-session-and-key-lifecycle.md) | 761 |
| [17. Professional engineering source registry](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md) | 948 |
| [18. Phase-aware source requirements](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md) | 787 |
| [20. Additional required outputs from Codex](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/10-20-additional-required-outputs-from-codex.md) | 214 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="strategy-os--kleppmann--professional-engineering-review-prompt-v2"></a>

[Strategy OS — Kleppmann + Professional Engineering Review Prompt V2](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#strategy-os--kleppmann--professional-engineering-review-prompt-v2)

<a id="strategy-os--martin-kleppmann-corpus-review-failure-discovery-and-industrial-hardening-mandate"></a>

[Strategy OS — Martin Kleppmann Corpus Review, Failure Discovery, and Industrial Hardening Mandate](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#strategy-os--martin-kleppmann-corpus-review-failure-discovery-and-industrial-hardening-mandate)

<a id="0-non-negotiable-working-rules"></a>

[0. Non-negotiable working rules](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#0-non-negotiable-working-rules)

<a id="1-read-the-strategy-os-authorities-first"></a>

[1. Read the Strategy OS authorities first](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#1-read-the-strategy-os-authorities-first)

<a id="2-corpus-scope-crawl-the-website-as-a-graph-not-as-a-homepage"></a>

[2. Corpus scope: crawl the website as a graph, not as a homepage](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#2-corpus-scope-crawl-the-website-as-a-graph-not-as-a-homepage)

<a id="21-bounded-recursive-crawl-policy"></a>

[2.1 Bounded recursive-crawl policy](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#21-bounded-recursive-crawl-policy)

<a id="22-pdf-slide-graph-image-and-video-handling"></a>

[2.2 PDF, slide, graph, image, and video handling](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#22-pdf-slide-graph-image-and-video-handling)

<a id="23-copyright-and-licensing"></a>

[2.3 Copyright and licensing](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/01-strategy-os--kleppmann--professional-engineering-review-prompt-v2.md#23-copyright-and-licensing)

<a id="3-build-a-machine-readable-corpus-manifest"></a>

[3. Build a machine-readable corpus manifest](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#3-build-a-machine-readable-corpus-manifest)

<a id="4-relevance-scoring-and-reading-depth"></a>

[4. Relevance scoring and reading depth](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#4-relevance-scoring-and-reading-depth)

<a id="41-mandatory-tier-0-starting-set"></a>

[4.1 Mandatory Tier 0 starting set](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#41-mandatory-tier-0-starting-set)

<a id="foundations-partial-failure-clocks-replication-consistency"></a>

[Foundations, partial failure, clocks, replication, consistency](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#foundations-partial-failure-clocks-replication-consistency)

<a id="transactions-locking-and-financial-correctness"></a>

[Transactions, locking, and financial correctness](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#transactions-locking-and-financial-correctness)

<a id="logs-cdc-events-derived-state-and-dual-write-failures"></a>

[Logs, CDC, events, derived state, and dual-write failures](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#logs-cdc-events-derived-state-and-dual-write-failures)

<a id="schema-caching-deterministic-identity-and-compatibility"></a>

[Schema, caching, deterministic identity, and compatibility](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#schema-caching-deterministic-identity-and-compatibility)

<a id="verification-and-testability"></a>

[Verification and testability](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#verification-and-testability)

<a id="scale-operations-and-product-trust"></a>

[Scale, operations, and product trust](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#scale-operations-and-product-trust)

<a id="ux-and-failure-communication"></a>

[UX and failure communication](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#ux-and-failure-communication)

<a id="future-collaborationoffline-seamsnot-current-v0-mandates"></a>

[Future collaboration/offline seams—not current V0 mandates](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#future-collaborationoffline-seamsnot-current-v0-mandates)

<a id="5-core-research-questions"></a>

[5. Core research questions](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/02-3-build-a-machine-readable-corpus-manifest.md#5-core-research-questions)

<a id="6-mandatory-strategy-os-audit-domains"></a>

[6. Mandatory Strategy OS audit domains](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#6-mandatory-strategy-os-audit-domains)

<a id="61-database-transactions-and-isolation"></a>

[6.1 Database transactions and isolation](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#61-database-transactions-and-isolation)

<a id="62-capital-admission-and-double-spend-prevention"></a>

[6.2 Capital admission and double-spend prevention](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#62-capital-admission-and-double-spend-prevention)

<a id="63-distributed-locks-leases-and-fencing"></a>

[6.3 Distributed locks, leases, and fencing](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#63-distributed-locks-leases-and-fencing)

<a id="64-idempotency-retries-and-timeout-ambiguity"></a>

[6.4 Idempotency, retries, and timeout ambiguity](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#64-idempotency-retries-and-timeout-ambiguity)

<a id="65-orders-fills-positions-and-reconciliation"></a>

[6.5 Orders, fills, positions, and reconciliation](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#65-orders-fills-positions-and-reconciliation)

<a id="66-event-logs-cdc-dual-writes-and-materialized-views"></a>

[6.6 Event logs, CDC, dual writes, and materialized views](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#66-event-logs-cdc-dual-writes-and-materialized-views)

<a id="67-time-clocks-causality-and-market-event-semantics"></a>

[6.7 Time, clocks, causality, and market event semantics](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#67-time-clocks-causality-and-market-event-semantics)

<a id="68-market-truth-research-validity-and-replay"></a>

[6.8 Market truth, research validity, and replay](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#68-market-truth-research-validity-and-replay)

<a id="69-schema-evolution-and-rolling-deployment"></a>

[6.9 Schema evolution and rolling deployment](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#69-schema-evolution-and-rolling-deployment)

<a id="610-caches-and-deterministic-identity"></a>

[6.10 Caches and deterministic identity](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#610-caches-and-deterministic-identity)

<a id="611-background-jobs-optimisation-and-queue-semantics"></a>

[6.11 Background jobs, optimisation, and queue semantics](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#611-background-jobs-optimisation-and-queue-semantics)

<a id="612-websockets-realtime-ui-and-user-trust"></a>

[6.12 Websockets, realtime UI, and user trust](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#612-websockets-realtime-ui-and-user-trust)

<a id="613-tenant-isolation-confidentiality-and-support-tooling"></a>

[6.13 Tenant isolation, confidentiality, and support tooling](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#613-tenant-isolation-confidentiality-and-support-tooling)

<a id="614-provider-partial-failure-and-degraded-operation"></a>

[6.14 Provider partial failure and degraded operation](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#614-provider-partial-failure-and-degraded-operation)

<a id="615-backpressure-load-shedding-and-scale-economics"></a>

[6.15 Backpressure, load shedding, and scale economics](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/03-6-mandatory-strategy-os-audit-domains.md#615-backpressure-load-shedding-and-scale-economics)

<a id="616-backup-restore-correlated-failure-and-disaster-recovery"></a>

[6.16 Backup, restore, correlated failure, and disaster recovery](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/04-616-backup-restore-correlated-failure-and-disaster-recovery.md#616-backup-restore-correlated-failure-and-disaster-recovery)

<a id="617-ux-edge-cases-and-operational-communication"></a>

[6.17 UX edge cases and operational communication](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/04-616-backup-restore-correlated-failure-and-disaster-recovery.md#617-ux-edge-cases-and-operational-communication)

<a id="618-formal-methodsbounded-risk-weighted-use"></a>

[6.18 Formal methods—bounded, risk-weighted use](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/04-616-backup-restore-correlated-failure-and-disaster-recovery.md#618-formal-methodsbounded-risk-weighted-use)

<a id="7-required-contingency-catalogue"></a>

[7. Required contingency catalogue](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/04-616-backup-restore-correlated-failure-and-disaster-recovery.md#7-required-contingency-catalogue)

<a id="8-source-to-code-traceability"></a>

[8. Source-to-code traceability](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/04-616-backup-restore-correlated-failure-and-disaster-recovery.md#8-source-to-code-traceability)

<a id="9-test-and-fault-injection-programme"></a>

[9. Test and fault-injection programme](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#9-test-and-fault-injection-programme)

<a id="critical-paths"></a>

[Critical paths](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#critical-paths)

<a id="important-paths"></a>

[Important paths](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#important-paths)

<a id="routine-paths"></a>

[Routine paths](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#routine-paths)

<a id="10-implementation-gate"></a>

[10. Implementation gate](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#10-implementation-gate)

<a id="101-implement-now-only-when"></a>

[10.1 Implement now only when](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#101-implement-now-only-when)

<a id="102-do-not-implement-now-merely-because"></a>

[10.2 Do not implement now merely because](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#102-do-not-implement-now-merely-because)

<a id="103-explicit-anti-cargo-cult-rules"></a>

[10.3 Explicit anti-cargo-cult rules](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#103-explicit-anti-cargo-cult-rules)

<a id="11-commit-and-migration-discipline"></a>

[11. Commit and migration discipline](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#11-commit-and-migration-discipline)

<a id="12-required-deliverables"></a>

[12. Required deliverables](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#12-required-deliverables)

<a id="13-required-final-response"></a>

[13. Required final response](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#13-required-final-response)

<a id="a-repository-context"></a>

[A. Repository context](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#a-repository-context)

<a id="b-corpus-coverage"></a>

[B. Corpus coverage](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#b-corpus-coverage)

<a id="c-highest-impact-newly-discovered-contingencies"></a>

[C. Highest-impact newly discovered contingencies](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#c-highest-impact-newly-discovered-contingencies)

<a id="d-confirmed-bugs-and-gaps"></a>

[D. Confirmed bugs and gaps](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#d-confirmed-bugs-and-gaps)

<a id="e-changes-made"></a>

[E. Changes made](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#e-changes-made)

<a id="f-changes-deliberately-not-made"></a>

[F. Changes deliberately not made](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#f-changes-deliberately-not-made)

<a id="g-verification"></a>

[G. Verification](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#g-verification)

<a id="h-release-map"></a>

[H. Release map](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#h-release-map)

<a id="i-residual-risk"></a>

[I. Residual risk](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/05-9-test-and-fault-injection-programme.md#i-residual-risk)

<a id="14-definition-of-done"></a>

[14. Definition of done](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#14-definition-of-done)

<a id="addendum-v2--missing-kleppmann-themes-and-the-strategy-os-professional-engineering-reference-programme"></a>

[ADDENDUM V2 — Missing Kleppmann Themes and the Strategy OS Professional Engineering Reference Programme](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#addendum-v2--missing-kleppmann-themes-and-the-strategy-os-professional-engineering-reference-programme)

<a id="15-why-this-addendum-exists"></a>

[15. Why this addendum exists](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#15-why-this-addendum-exists)

<a id="16-mandatory-new-kleppmannddia-audit-domains"></a>

[16. Mandatory new Kleppmann/DDIA audit domains](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#16-mandatory-new-kleppmannddia-audit-domains)

<a id="161-exact-numeric-representation-dimensions-and-rounding"></a>

[16.1 Exact numeric representation, dimensions, and rounding](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#161-exact-numeric-representation-dimensions-and-rounding)

<a id="162-coordination-budget-and-convergence-map"></a>

[16.2 Coordination budget and convergence map](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#162-coordination-budget-and-convergence-map)

<a id="163-mandatory-ddia-second-edition-delta-review"></a>

[16.3 Mandatory DDIA second-edition delta review](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#163-mandatory-ddia-second-edition-delta-review)

<a id="164-data-governance-and-complete-information-lifecycle"></a>

[16.4 Data governance and complete information lifecycle](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#164-data-governance-and-complete-information-lifecycle)

<a id="165-provider-portability-sovereignty-and-clean-exit"></a>

[16.5 Provider portability, sovereignty, and clean exit](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#165-provider-portability-sovereignty-and-clean-exit)

<a id="166-tamper-evident-evidence-and-independently-verifiable-receipts"></a>

[16.6 Tamper-evident evidence and independently verifiable receipts](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/06-14-definition-of-done.md#166-tamper-evident-evidence-and-independently-verifiable-receipts)

<a id="167-credential-device-session-and-key-lifecycle"></a>

[16.7 Credential, device, session, and key lifecycle](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/07-167-credential-device-session-and-key-lifecycle.md#167-credential-device-session-and-key-lifecycle)

<a id="168-semantic-conflicts-in-future-collaborative-strategy-graphs"></a>

[16.8 Semantic conflicts in future collaborative strategy graphs](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/07-167-credential-device-session-and-key-lifecycle.md#168-semantic-conflicts-in-future-collaborative-strategy-graphs)

<a id="169-locale-currency-timezone-and-input-ambiguity"></a>

[16.9 Locale, currency, timezone, and input ambiguity](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/07-167-credential-device-session-and-key-lifecycle.md#169-locale-currency-timezone-and-input-ambiguity)

<a id="1610-recommendation-governance-and-feedback-loops"></a>

[16.10 Recommendation governance and feedback loops](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/07-167-credential-device-session-and-key-lifecycle.md#1610-recommendation-governance-and-feedback-loops)

<a id="1611-software-supply-chain-integrity"></a>

[16.11 Software supply-chain integrity](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/07-167-credential-device-session-and-key-lifecycle.md#1611-software-supply-chain-integrity)

<a id="17-professional-engineering-source-registry"></a>

[17. Professional engineering source registry](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#17-professional-engineering-source-registry)

<a id="171-tier-a--continuous-core-authorities"></a>

[17.1 Tier A — continuous core authorities](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#171-tier-a--continuous-core-authorities)

<a id="a1-martin-kleppmann-cambridge-course-material-and-ddia-2e"></a>

[A1. Martin Kleppmann, Cambridge course material, and DDIA 2e](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a1-martin-kleppmann-cambridge-course-material-and-ddia-2e)

<a id="a2-aws-builders-library"></a>

[A2. AWS Builders' Library](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a2-aws-builders-library)

<a id="a3-google-site-reliability-engineering-books-and-workbook"></a>

[A3. Google Site Reliability Engineering books and workbook](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a3-google-site-reliability-engineering-books-and-workbook)

<a id="a4-jepsen-and-official-postgresql-concurrency-documentation"></a>

[A4. Jepsen and official PostgreSQL concurrency documentation](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a4-jepsen-and-official-postgresql-concurrency-documentation)

<a id="a5-stripe-engineering-modern-treasury-and-tigerbeetle"></a>

[A5. Stripe Engineering, Modern Treasury, and TigerBeetle](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a5-stripe-engineering-modern-treasury-and-tigerbeetle)

<a id="a6-foundationdb-deterministic-simulation-and-testing-material"></a>

[A6. FoundationDB deterministic simulation and testing material](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a6-foundationdb-deterministic-simulation-and-testing-material)

<a id="a7-owasp-cisa-nist-ssdf-and-slsa"></a>

[A7. OWASP, CISA, NIST SSDF, and SLSA](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a7-owasp-cisa-nist-ssdf-and-slsa)

<a id="a8-opentelemetry-specifications"></a>

[A8. OpenTelemetry specifications](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#a8-opentelemetry-specifications)

<a id="172-tier-b--targeted-architecture-and-verification-authorities"></a>

[17.2 Tier B — targeted architecture and verification authorities](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#172-tier-b--targeted-architecture-and-verification-authorities)

<a id="b1-temporal-dbos-and-restate-official-documentation"></a>

[B1. Temporal, DBOS, and Restate official documentation](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#b1-temporal-dbos-and-restate-official-documentation)

<a id="b2-tla-hillel-wayne-and-hypothesis"></a>

[B2. TLA+, Hillel Wayne, and Hypothesis](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#b2-tla-hillel-wayne-and-hypothesis)

<a id="b3-martin-fowlers-distributed-systems-patterns-and-evolutionary-migration-material"></a>

[B3. Martin Fowler's distributed-systems patterns and evolutionary migration material](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#b3-martin-fowlers-distributed-systems-patterns-and-evolutionary-migration-material)

<a id="b4-cloudflare-github-shopify-and-other-transparent-engineering-postmortems"></a>

[B4. Cloudflare, GitHub, Shopify, and other transparent engineering postmortems](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#b4-cloudflare-github-shopify-and-other-transparent-engineering-postmortems)

<a id="173-tier-c--trading-runtime-and-research-validity-authorities"></a>

[17.3 Tier C — trading-runtime and research-validity authorities](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#173-tier-c--trading-runtime-and-research-validity-authorities)

<a id="c1-nautilustrader"></a>

[C1. NautilusTrader](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#c1-nautilustrader)

<a id="c2-quantconnect-lean"></a>

[C2. QuantConnect LEAN](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#c2-quantconnect-lean)

<a id="c3-freqtrade"></a>

[C3. Freqtrade](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#c3-freqtrade)

<a id="c4-hftbacktest"></a>

[C4. hftbacktest](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#c4-hftbacktest)

<a id="c5-jane-street-engineering-mechanical-sympathy-and-aeron"></a>

[C5. Jane Street engineering, Mechanical Sympathy, and Aeron](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/08-17-professional-engineering-source-registry.md#c5-jane-street-engineering-mechanical-sympathy-and-aeron)

<a id="18-phase-aware-source-requirements"></a>

[18. Phase-aware source requirements](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#18-phase-aware-source-requirements)

<a id="181-v0--research-first-launch"></a>

[18.1 V0 — research-first launch](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#181-v0--research-first-launch)

<a id="182-v1--controlled-execution-and-capital-authority"></a>

[18.2 V1 — controlled execution and capital authority](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#182-v1--controlled-execution-and-capital-authority)

<a id="183-v11--dynamic-watchlists--universes"></a>

[18.3 V1.1 — Dynamic Watchlists / Universes](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#183-v11--dynamic-watchlists--universes)

<a id="184-v15--certified-index-options-execution"></a>

[18.4 V1.5 — certified index-options execution](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#184-v15--certified-index-options-execution)

<a id="185-v2--workflows-diagnostics-collaboration-richer-intelligence"></a>

[18.5 V2 — Workflows, diagnostics, collaboration, richer intelligence](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#185-v2--workflows-diagnostics-collaboration-richer-intelligence)

<a id="186-v3--marketplace-managed-models-mlai-international-scale"></a>

[18.6 V3 — marketplace, managed models, ML/AI, international scale](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#186-v3--marketplace-managed-models-mlai-international-scale)

<a id="19-ongoing-professional-reference-process"></a>

[19. Ongoing professional reference process](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#19-ongoing-professional-reference-process)

<a id="191-source-registryyaml-fields"></a>

[19.1 `source-registry.yaml` fields](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#191-source-registryyaml-fields)

<a id="192-claim-registry"></a>

[19.2 Claim registry](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#192-claim-registry)

<a id="193-source-admission-rule"></a>

[19.3 Source admission rule](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#193-source-admission-rule)

<a id="194-two-source-rule-for-high-risk-changes"></a>

[19.4 Two-source rule for high-risk changes](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#194-two-source-rule-for-high-risk-changes)

<a id="195-conflict-rule"></a>

[19.5 Conflict rule](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#195-conflict-rule)

<a id="196-refresh-cadence"></a>

[19.6 Refresh cadence](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#196-refresh-cadence)

<a id="197-anti-cargo-cult-constraints"></a>

[19.7 Anti-cargo-cult constraints](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/09-18-phase-aware-source-requirements.md#197-anti-cargo-cult-constraints)

<a id="20-additional-required-outputs-from-codex"></a>

[20. Additional required outputs from Codex](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/10-20-additional-required-outputs-from-codex.md#20-additional-required-outputs-from-codex)

<a id="21-final-addendum-instruction"></a>

[21. Final addendum instruction](strategy_os_kleppmann_and_professional_engineering_review_prompt_v2_2026-08-28-sections/10-20-additional-required-outputs-from-codex.md#21-final-addendum-instruction)
