# Strategy OS — V1 Architecture Continuity Lane

**Date:** 29 August 2026\
**Status:** Parallel planning/audit lane\
**Purpose:** Continue serious V1 execution and architecture planning while V0 delivery proceeds, without allowing V1 or V6 concepts to steal the V0 critical path.

---

## 0. Mission

You are the V1 architecture continuity agent.

Your work is to keep the controlled-execution programme coherent and current while another lane ships the research-first V0.

You are not the V0 feature owner. You may inspect all code, create V1 planning/ADR documents in your assigned path, and raise current V0 blockers. You must not modify V0-owned contracts or shared schemas without orchestration approval.

---

# 1. Read and reconcile authority

Read the nine canonical documents, current progress mapper, active capsules, accepted ADRs, and the 29 August owner-direction package.

Preserve accepted Phase 1–4 work unless a concrete core-abstraction defect is proven.

Do not trust old dates, version labels, or status statements without current repository evidence.

Create:

```text
docs/v1-architecture/00-CURRENT-V1-AUTHORITY-AND-STATUS.md
```

It must state:

- what is accepted;
- what is partial;
- what is active;
- what is blocked;
- what older documents are superseded;
- what V0 work overlaps V1 foundations;
- exact repository evidence.

---

# 2. V1 mission

V1 adds controlled operational authority to the validated research product.

The intended flow is:

```text
approved immutable strategy revision
→ strategy signal/economic intent
→ sizing request / target position
→ portfolio admission
→ transactional capital reservation
→ provider/account preflight
→ paper/shadow
→ bounded live authority where certified
→ order lifecycle
→ fills and exact inventory
→ monitoring and degraded states
→ reconciliation
→ evidence and review
```

V1 should not pretend that every asset class, broker, order type, or multi-leg structure is certified.

---

# 3. Core V1 architecture workstreams

## 3.1 Strategy/economic-intent/execution separation

Verify:

- strategy signal is provider-neutral;
- economic intent does not directly call broker APIs;
- execution-product selection is explicit;
- unsupported semantics fail preflight;
- signal/proposal/paper/live authority remains distinct;
- exact version/evidence chain survives.

Preserve a future `ExecutionStructurePolicy` seam, but do not implement arbitrary multi-leg orchestration in V1.

## 3.2 Sizing and target position

Verify or define:

```text
current exact inventory
+
pending orders
+
reserved capital
+
desired target quantity/risk
→ safe execution delta
```

Required sizing modes should follow current owner-approved V1 scope and actual progress mapper. At minimum review:

- fixed units/lots;
- fixed capital;
- equity/allocation percentage;
- risk percentage;
- stop-distance;
- volatility;
- caps and lot/tick rounding;
- cost/slippage buffer;
- dynamic numeric input seam;
- deterministic reason receipt.

## 3.3 Portfolio admission and concurrency

The canonical simultaneous-signal case remains critical:

```text
Two or more deployments signal against one account snapshot.
Aggregate requested capital exceeds availability.
```

Prove:

- one consistent account/capital snapshot;
- versioned admission policy;
- stable tie-breaker;
- atomic/transactional reservation;
- pending-order awareness;
- deterministic resize/reject;
- idempotency;
- crash/restart recovery;
- durable reasons;
- no reliance on an ephemeral distributed lock as sole correctness.

## 3.4 Provider capability and preflight

Compile:

- data requirements;
- live versus historical capability;
- subscriptions/quotas;
- instrument/contract mapping;
- order types and modify/cancel semantics;
- margin APIs;
- partial fills;
- protection durability;
- account state;
- resource plan;
- earliest valid evaluation;
- failure/refusal reason.

No silent provider fallback or semantic downgrade.

## 3.5 Order lifecycle and timeout ambiguity

Model explicit states and transitions for:

- intent created;
- admitted;
- submitted;
- unknown/timeout;
- acknowledged;
- partially filled;
- filled;
- cancel requested;
- cancelled;
- rejected;
- recovery/reconciliation.

Never equate request timeout with order failure.

## 3.6 Exact position ownership

Verify:

- exact canonical filled instrument;
- strategy/deployment/campaign attribution;
- open position remains owned by creating revision;
- broker netting does not erase internal books;
- restart/reconciliation does not reassign ownership;
- current storage can later add tranches/legs without destructive rewrite.

## 3.7 Protection and degraded states

Distinguish:

- strategy-managed exits;
- software-managed hard protection;
- broker/exchange-resident protection.

Review declared behavior under:

- UI disconnect;
- data stale/outage;
- execution broker outage;
- process restart;
- historical-provider outage after warm-up;
- position-protection data failure;
- account state uncertainty;
- Redis/cache loss if present.

## 3.8 Reconciliation and evidence

A user must be able to determine:

- which strategy revision acted;
- which data/adapter/rulebook version applied;
- why capital was accepted/rejected;
- what order was sent;
- what the broker/exchange reported;
- what was filled;
- what inventory Strategy OS believes exists;
- how differences were reconciled.

---

# 4. V1 and future multi-leg boundary

The updated vision makes multi-leg support inevitable later, but it is not a V1 release requirement.

Preserve now:

- one signal may create N intents;
- capital/margin preflight can later consume a campaign plan;
- exact inventory supports future leg/tranche lineage;
- execution adapter advertises combo/basket capabilities;
- order/fill identity does not assume one campaign has one child order;
- evidence supports parent/child relationships.

Do not build now:

- arbitrary spread authoring;
- structure optimizer;
- net-Greek campaign runtime;
- partial-leg recovery engine;
- broad options margin simulation;
- multi-leg live certification.

Document adoption dependencies for V4 or the owner-selected later release.

---

# 5. V1 and V0 overlap

The following V0 work may become V1 foundation and should be coordinated rather than duplicated:

- auth/session/tenant isolation;
- immutable strategy identity;
- signal event and Alerts Inbox;
- billing/entitlement roles;
- admin audit and support receipts;
- durable jobs;
- data validity/causality;
- observability/backups/migrations;
- provider/data identity;
- five-node-family conformance.

V1 should consume the same canonical signal/event identity rather than create an execution-only duplicate.

---

# 6. V1 architecture audit outputs

Create:

```text
docs/v1-architecture/
├── 00-CURRENT-V1-AUTHORITY-AND-STATUS.md
├── 01-V1-END-TO-END-EXECUTION-MODEL.md
├── 02-SIGNAL-ECONOMIC-INTENT-EXECUTION-POLICY.md
├── 03-SIZING-TARGET-POSITION-AND-PENDING-ORDER-MODEL.md
├── 04-CAPITAL-ADMISSION-CONCURRENCY-AND-RECOVERY.md
├── 05-PROVIDER-PREFLIGHT-AND-CAPABILITY-MATRIX.md
├── 06-ORDER-LIFECYCLE-TIMEOUT-AND-IDEMPOTENCY.md
├── 07-POSITION-OWNERSHIP-AND-RECONCILIATION.md
├── 08-PROTECTION-AND-DEGRADED-STATE-MATRIX.md
├── 09-V0-TO-V1-MIGRATION-AND-COMPATIBILITY.md
├── 10-FUTURE-MULTI-LEG-SEAM-NON-IMPLEMENTATION-ADR.md
├── 11-V1-ADVERSARIAL-TEST-PLAN.md
├── 12-V1-RELEASE-AND-OPERATIONAL-GATES.md
└── 13-FINAL-V1-ARCHITECTURE-DECISION-REPORT.md
```

---

# 7. Risk-weighted tests

Critical proofs should include realistic failures, not test-count inflation.

At minimum plan or verify:

- simultaneous capital requests;
- stale account snapshot;
- duplicate signal/intent;
- process death after reservation;
- broker timeout then late acknowledgement;
- duplicate/reordered postback;
- partial fill then restart;
- cancel/replace race;
- provider capability loss;
- stale or misaligned market input;
- broker net position differs from internal books;
- open position on old strategy revision after new deployment revision;
- kill switch during in-flight orders;
- migration from current representative state;
- tenant isolation in APIs/events/admin;
- deterministic replay/evidence.

Use actual PostgreSQL/SQLite/provider adapter behavior where relevant rather than only mocks.

---

# 8. Parallel work and write ownership

This lane is planning/read-only until the orchestrator assigns an implementation capsule.

Rules:

- do not edit V0 alerts, billing, auth, or admin code owned by another lane;
- do not edit shared migrations or core IR concurrently;
- raise collision candidates immediately;
- one agent owns a contract at a time;
- use a dedicated worktree/branch;
- small commits tied to finding IDs;
- no unrelated cleanup.

---

# 9. Final classification

Every item must be classified:

```text
V0 BLOCKER
V0 SHARED FOUNDATION
V1 MUST IMPLEMENT
V1 ALREADY CORRECT
V1 HARDENING
V1.5 OPTIONS/DYNAMIC-UNIVERSE DEPENDENCY
V2 PORTFOLIO DEPENDENCY
V4 MULTI-LEG/INSTITUTIONAL SEAM
SAFE TO DEFER
REJECTED OVERENGINEERING
OWNER DECISION REQUIRED
```

The intended outcome is a V1 plan that remains serious and current without causing V0 to become an execution launch.
