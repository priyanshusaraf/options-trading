Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

## 18. Phase-aware source requirements

### 18.1 V0 — research-first launch

Mandatory focus:

- exact strategy/dataset/engine identity;
- time alignment and anti-look-ahead;
- deterministic and resumable research jobs;
- tenant isolation and secure file/data handling;
- data retention/deletion/export;
- numeric semantics for costs and research metrics;
- failure-aware UX;
- SLOs, observability, restore drills, and support receipts;
- software-supply-chain baseline;
- clean seams for future execution without building it.

Required source set:

```text
Kleppmann + DDIA 2e
PostgreSQL official docs
Jepsen concepts
AWS Builders' Library
Google SRE
OWASP / NIST / CISA / SLSA
OpenTelemetry
FoundationDB testing concepts
NautilusTrader / LEAN / Freqtrade research-semantics references
Hypothesis
```

Stripe/Modern Treasury/TigerBeetle are used to audit existing financial objects and future seams, not to force a full execution ledger into V0.

### 18.2 V1 — controlled execution and capital authority

Add mandatory deep review of:

```text
Stripe Ledger and idempotency
Modern Treasury ledger and reconciliation series
TigerBeetle guarantees
AWS idempotency/retry/overload material
PostgreSQL serializable behavior
TLA+ model of capital admission/order lifecycle
NautilusTrader execution and reconciliation
Official broker/exchange specifications
```

### 18.3 V1.1 — Dynamic Watchlists / Universes

Prioritize:

- staged evaluation;
- bounded fan-out;
- shuffle sharding;
- tenant resource isolation;
- queue backlogs;
- leases and deduplication;
- rank/membership snapshot identity;
- hysteresis and churn;
- recovery after hot-state loss.

### 18.4 V1.5 — certified index-options execution

Prioritize:

- exact contract identity and market-rulebook truth;
- quote freshness and liquidity;
- conservative fill/slippage assumptions;
- latency and partial fills;
- option-selector receipts;
- exact-held-contract exits;
- broker conformance and reconciliation;
- official exchange and broker sources over blogs.

Use hftbacktest/LEAN/NautilusTrader as implementation references, not as substitutes for Indian point-in-time market truth.

### 18.5 V2 — Workflows, diagnostics, collaboration, richer intelligence

Prioritize:

- Temporal/DBOS/Restate comparison;
- local-first/CRDT research;
- semantic graph conflict handling;
- recommendation governance and feedback loops;
- event/fundamental point-in-time data;
- workflow versioning and human approvals.

### 18.6 V3 — marketplace, managed models, ML/AI, international scale

Prioritize:

- ownership and rights provenance;
- independently verifiable evidence;
- conflicts of interest and ranking governance;
- group access/key lifecycle;
- data portability and provider switching;
- model artifact provenance;
- legal/regulatory architecture;
- scale-led, measured infrastructure only.

---

## 19. Ongoing professional reference process

Create:

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

### 19.1 `source-registry.yaml` fields

Each source family must record:

```text
source_id
name
canonical_root
author_or_organisation
authority_type
primary_or_secondary
technical_domains
product_versions
required_articles_or_sections
current_version_or_date
last_checked
license
vendor_incentive_or_bias
known_limitations
status
owner
```

### 19.2 Claim registry

Every external claim that materially influences architecture must have:

```text
claim_id
claim
source_id
exact citation / page / section
source date/version
Strategy OS invariant
repository evidence
counterevidence or disagreement
applicability decision
release classification
ADR/test/issue links
verification status
```

### 19.3 Source admission rule

No external recommendation enters the codebase merely because a respected engineer or company uses it.

Required chain:

```text
SOURCE CLAIM
→ SYSTEM MODEL AND ASSUMPTIONS
→ STRATEGY OS FAILURE HYPOTHESIS
→ CURRENT CODE EVIDENCE
→ SMALLEST SAFE DESIGN
→ TEST / MODEL / BENCHMARK
→ MIGRATION AND ROLLBACK
→ IMPLEMENT OR REJECT
```

### 19.4 Two-source rule for high-risk changes

For real-money, authority, irreversible data, security, or research-validity changes, require at least:

- one conceptual/independent source; and
- one primary implementation source, official specification, or direct experiment.

Examples:

```text
Kleppmann/Jepsen principle
+
PostgreSQL behavior test
```

```text
Stripe/Modern Treasury ledger pattern
+
Strategy OS invariant/property tests
```

```text
AWS retry guidance
+
actual broker/provider idempotency semantics
```

### 19.5 Conflict rule

When sources disagree:

1. record the disagreement;
2. identify different system assumptions;
3. prefer official current behavior for the actual dependency;
4. reproduce behavior locally where possible;
5. choose the weakest architecture that satisfies Strategy OS invariants;
6. do not resolve disagreement by authority count or reputation.

### 19.6 Refresh cadence

This is not a background promise. Run an explicit reference refresh:

- at the start of a major phase;
- before a release freeze;
- after a serious incident or discovered architectural bug;
- before adopting a major database, queue, workflow, security, or observability dependency;
- when a provider announces a semantic API/capability change.

Each refresh produces a dated report with:

- sources checked;
- versions/dates changed;
- newly relevant findings;
- outdated advice;
- architecture implications;
- explicit no-change decisions.

### 19.7 Anti-cargo-cult constraints

Do not infer that Strategy OS needs:

- microservices;
- Kafka;
- Redis;
- Kubernetes;
- event sourcing everywhere;
- CRDTs;
- TLA+ for every feature;
- a custom ledger database;
- Aeron or lock-free queues;
- Temporal/DBOS/Restate;
- multi-region deployment;
- local-first sync;
- cryptographic proofs;
- a zero-trust marketing claim;
- HFT infrastructure.

Every adoption needs measured pressure or a correctness requirement.

---
