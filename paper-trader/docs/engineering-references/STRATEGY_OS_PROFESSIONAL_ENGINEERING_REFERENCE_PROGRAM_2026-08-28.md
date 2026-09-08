# Strategy OS — Professional Engineering Reference Programme

**Date:** 28 August 2026\
**Purpose:** Maintain a durable, phase-aware body of professional technical guidance for Strategy OS without turning external blogs into architecture-by-authority.

## 1. Core principle

Strategy OS should use external research and production experience through this chain:

```text
external claim
→ assumptions and system model
→ Strategy OS failure hypothesis
→ repository evidence
→ smallest safe change
→ test/model/benchmark
→ migration and rollback
→ implementation or explicit rejection
```

The programme exists to preserve professional guidance throughout the product lifecycle while keeping the current research-first V0 shippable.

## 2. What the original Kleppmann review underweighted

| Area | V0 relevance | Later relevance | Concrete project action |
|---|---:|---:|---|
| Exact numeric and unit semantics | High | Critical for execution | Define Money/Price/Quantity/Rate/Bps types, storage and rounding rules; property-test fees, P&L, tick and lot boundaries. |
| Coordination vs convergence map | High | Critical | Classify every important transition by the weakest safe consistency model. |
| DDIA 2e delta | High | High | Review new material on NFRs, durable workflows, multitenancy, randomized testing, provider trade-offs, privacy and feedback loops. |
| Data governance/lifecycle | High | High | Inventory purpose, access, retention, export, deletion, backup retention and restore behavior. |
| SLOs and semantic reliability | High | High | Define research-correctness, job-durability, latency, stale-data and restore objectives. |
| Credential/key lifecycle | High | Critical | Rotation, revocation, recovery, expiry and break-glass state machines. |
| Provider portability/exit | Medium | High | User export, clean-environment restore and provider compatibility receipts. |
| Tamper-evident evidence | Medium | High | Hash/sign evidence manifests; defer custom cryptography. |
| Semantic graph conflicts | Medium seam | High for collaboration | No silent last-write-wins; separate layout convergence from executable semantic changes. |
| Locale/time/currency boundaries | High | High | Locale-safe CSV and display, UTC/event-time rules, timezone/session correctness. |
| Recommendation feedback loops | Preserve evidence | Critical V2/V3 | Post-hoc labels, graph diffs, fresh validation, consent and conflict disclosure. |
| Software supply chain | High | Critical before execution | Lockfiles, scans, SBOM, provenance, signed/traceable releases and dependency rollback. |

## 3. Source families and their assigned jobs

### Distributed data and correctness

- Martin Kleppmann website, Cambridge course material, DDIA 2e.
- Jepsen consistency models and analyses.
- Official PostgreSQL concurrency, isolation and locking documentation.

### Production reliability and operations

- AWS Builders' Library.
- Google SRE books/workbook.
- OpenTelemetry specifications.
- Cloudflare, GitHub and Shopify engineering/postmortem archives.

### Money, authority and reconciliation

- Stripe Engineering: Ledger, idempotency, migrations and API design.
- Modern Treasury ledger/accounting/reconciliation series.
- TigerBeetle documentation and independent Jepsen analysis.

### Security and software supply chain

- OWASP ASVS and Cheat Sheet Series.
- CISA Secure by Design.
- NIST Secure Software Development Framework.
- SLSA specification.
- Trail of Bits articles where directly relevant and technically reproducible.

### Formal and generative verification

- Leslie Lamport's TLA+ material.
- Hillel Wayne's applied formal-methods material.
- Hypothesis property-based and rule-based stateful testing.
- FoundationDB deterministic simulation/testing material.

### Durable jobs and workflows

- Temporal, DBOS and Restate official documentation, evaluated comparatively against the current job system.

### Trading runtime and research validity

- NautilusTrader.
- QuantConnect LEAN.
- Freqtrade look-ahead and recursive-analysis tooling.
- hftbacktest for later latency/queue-model work.
- Jane Street engineering, Mechanical Sympathy and Aeron only where measured performance needs justify them.

## 4. Phase map

### V0

Focus on:

- research identity and reproducibility;
- anti-look-ahead and time semantics;
- exact cost/numeric rules;
- durable jobs;
- tenant security and data lifecycle;
- observability, SLOs and restore drills;
- supply-chain baseline;
- clear user uncertainty states.

Do not build live execution, a distributed event platform, CRDT collaboration, HFT infrastructure or a workflow platform merely because these sources discuss them.

### V1 execution

Add deep ledger, idempotency, concurrency, reconciliation, broker semantics, TLA+ and fault-injection work before real capital authority becomes reachable.

### V1.1 Dynamic Watchlists

Add bounded fan-out, staged evaluation, tenant isolation, leases, queue/backlog behavior, churn/hysteresis and hot-state recovery.

### V1.5 options

Add exact contract truth, quote freshness, liquidity, partial fills, fill/slippage/latency models, conservative order policy and exact-held-contract reconciliation.

### V2

Add durable product workflows, semantic collaboration, diagnostics/recommendation governance, events/fundamentals and richer derivative intelligence.

### V3

Add marketplace rights/provenance, managed-model legal boundaries, independently verifiable evidence, group access/key lifecycle, ML artifact provenance and demand-led scale.

## 5. Required repository structure

```text
docs/engineering-references/
├── 00-README.md
├── source-registry.yaml
├── claim-registry.jsonl
├── reading-packets/
├── source-notes/
├── incident-library/
├── rejected-patterns/
└── refresh-reports/
```

## 6. Review gates

A high-risk external recommendation requires:

1. an exact source and version/date;
2. its assumptions and failure model;
3. one Strategy OS invariant;
4. repository file/line evidence;
5. a realistic adversarial test or model;
6. migration and rollback;
7. a release classification;
8. an explicit rejection of larger unnecessary infrastructure.

For real-money, authority, irreversible data, security and research-validity changes, use a two-source rule: one conceptual/independent source plus one official implementation source or direct experiment.

## 7. Refresh policy

Run a dated reference refresh:

- at the beginning of a major phase;
- before release freeze;
- after a serious incident or newly discovered architecture bug;
- before adopting a major database, queue, workflow, security or observability dependency;
- after a material broker/provider capability change.

This is an explicit task, not an assumed background process.

## 8. Anti-cargo-cult rule

The reference programme does not imply Strategy OS needs microservices, Kafka, Kubernetes, Redis, event sourcing everywhere, CRDTs, Temporal, a custom ledger database, Aeron, local-first sync, cryptographic proofs, multi-region deployment or HFT infrastructure.

Adopt a technology only for a measured bottleneck or a proven correctness requirement.
