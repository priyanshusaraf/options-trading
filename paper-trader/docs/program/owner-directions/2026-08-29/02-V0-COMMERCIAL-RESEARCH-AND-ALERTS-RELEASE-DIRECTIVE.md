# Strategy OS — V0 Commercial Research and Alerts Release Directive

**Date:** 29 August 2026\
**Status:** Current owner-directed V0 product brief\
**Purpose:** Convert the research-first V0 into a coherent, commercially operable product without dragging controlled execution, Dynamic Watchlists, marketplace, or later institutional complexity into the launch path.

---

## 0. V0 mission

V0 must answer one market question:

> Will serious Indian discretionary-systematic traders repeatedly use and pay for a visual research, evidence, and signal-monitoring environment that helps them move from an idea to an explainable alert without granting public real-money execution authority?

V0 is not a demo. It must be a complete commercial research product.

The primary user journey is:

```text
LAND
→ SIGN IN
→ UNDERSTAND THE PRODUCT
→ OPEN OR CREATE A STRATEGY
→ BUILD WITH FIVE NODE FAMILIES
→ SELECT SUPPORTED DATA/INSTRUMENTS
→ BACKTEST
→ INSPECT EVIDENCE
→ SAVE/VERSION
→ ACTIVATE SIGNAL MONITORING
→ RECEIVE ALERTS
→ UNDERSTAND WHY AN ALERT FIRED
→ RETURN TO RESEARCH
```

---

# 1. Explicit scope boundary

## V0 includes

- a coherent web product shell;
- login and account lifecycle;
- Google sign-in where compatible with the existing auth architecture;
- ownership, tenancy, and secure sessions;
- payments in Razorpay Test Mode and a production-ready entitlement seam;
- a minimal admin/support panel;
- onboarding and a starter strategy;
- the five user-facing node families functioning coherently;
- strategy creation, editing, validation, versioning, and persistence;
- supported static instrument/data selection;
- cost-aware backtesting and existing bounded research/validation capabilities that are genuinely complete;
- signal-only monitoring;
- a first-class Alerts Inbox and alert detail experience;
- research/evidence history;
- product telemetry;
- useful errors, support receipts, backups, deployment readiness, and privacy controls.

## V0 does not include

- public real-money execution authority;
- arbitrary options or futures live execution;
- multi-leg orchestration;
- a public Dynamic Watchlist builder unless the owner explicitly re-enters it into V0 after repository review;
- strategy marketplace;
- managed-money allocation;
- portfolio optimization;
- AI strategy invention;
- speculative microservices, Kafka, Kubernetes, or distributed-system replatforming;
- broker-count expansion as a launch objective;
- direct webhook-to-order behavior.

V0 may preserve existing paper/internal execution machinery and future seams. It must not expose those seams as public live authority.

---

# 2. V0 product surfaces

A recommended V0 information architecture is:

```text
Home
Strategies
Research
Alerts
Portfolio / Review
Data / Connections
Billing
Settings
Help
```

Admin is a separate authorized surface.

## 2.1 Home

A briefing, not a metric wall.

Useful items:

- continue last strategy/research session;
- backtest or optimization completed;
- new unread alerts;
- strategy monitoring state;
- data/provider attention needed;
- billing/account attention;
- data-quality or job failures;
- evidence requiring review.

## 2.2 Strategies

- list and search strategies;
- show immutable/versioned identity clearly;
- create, clone, archive;
- show last research activity and monitoring state;
- enter the strategy workspace.

## 2.3 Strategy workspace

At minimum:

- Overview;
- Graph;
- Data/Instruments;
- Backtests/Research;
- Evidence;
- Alerts/Monitoring;
- Version history;
- Settings/permissions as needed.

Do not scatter one strategy across unrelated pages without context.

## 2.4 Research

The dense product surface:

- graph editing;
- parameter editing;
- data/instrument binding;
- backtest launch and results;
- baseline comparison;
- existing validation tools that meet correctness requirements;
- persisted run status;
- clear heavy-job versus interactive-run behavior;
- evidence and reproducibility.

## 2.5 Alerts

A dedicated inbox and detail view described below.

## 2.6 Portfolio / Review

V0 can remain bounded, but should avoid being a dead analytics screen.

It may show:

- strategies being monitored;
- assigned notional/research budgets if they exist;
- alert counts;
- aggregate simulated/research metrics;
- strategy status and review actions.

It should preserve the later active-portfolio seam without implementing optimization now.

## 2.7 Billing

- plan and entitlement state;
- test checkout during integration;
- invoice/payment history available to the user where supported;
- clear success, pending, failed, cancelled, and access-expiry states;
- no silent access grant based only on client-side checkout success.

---

# 3. Five node families — V0 quality requirement

The existing product language defines five visible families:

1. Execution & Position;
2. Indicators & Derived Features;
3. Market Structure, Derivatives & Cross-Instrument;
4. Price, Instrument & Market Data;
5. Logic, Math & State.

V0 does not need every future node, but each family shown in the UI must work according to its declared contract.

## 3.1 Required node contract behavior

Every exposed node should have:

- stable ID and semantic version;
- typed inputs and outputs;
- declared data fields;
- warm-up/history requirements;
- causal/completed-bar policy;
- missing/invalid-data behavior;
- evaluation trigger;
- research/signal eligibility;
- error messages;
- vector/batch and streaming parity where both are exposed;
- resource class where relevant;
- tests or reference provenance.

## 3.2 V0 execution-node treatment

Execution/position nodes may remain part of the language because the strategy definition must preserve economic intent. However:

- V0 monitor mode compiles them to signal/economic-intent output, not public broker order authority;
- unsupported live semantics must not appear enabled;
- UI labels must distinguish “signal,” “proposal,” “paper,” and “live” capability;
- no hidden broker call should be reachable from a V0 public entitlement.

## 3.3 Conformance audit

Codex must produce a node-family matrix:

```text
node
family
visible in UI?
implemented?
tested?
research eligible?
signal eligible?
paper/live path reachable?
known incorrect semantics?
user-facing error quality?
V0 action
```

Do not claim a family is working because one node renders on the canvas.

---

# 4. Signal monitoring and Alerts Inbox

## 4.1 Canonical objects

Introduce or verify a separation among:

```text
StrategyRevision
SignalMonitor / signal-mode binding
SignalEvent
SignalAlert
AlertDeliveryAttempt
AlertRead/Acknowledgement state
```

The canonical signal event should survive UI delivery failure.

A suggested `SignalAlert` contract:

```text
id
owner_id / tenant_id
strategy_id
strategy_revision_id
monitor_id
signal_event_id
canonical instrument roles
signal type / direction
severity / priority
event_time
effective_time
observed_at / emitted_at
expires_at
status
idempotency_key
input freshness summary
reason/evaluation receipt reference
snapshot/evidence reference
created_at / updated_at
```

## 4.2 Alert states

At minimum:

```text
NEW
READ
ACKNOWLEDGED
DISMISSED
EXPIRED
```

Signal validity and user attention state should remain distinct. Reading an alert does not make it valid; expiry does not mean the user has read it.

## 4.3 Inbox UX

Required:

- chronological list;
- unread count;
- filters by strategy, instrument, direction/type, state, and time;
- clear freshness/expiry treatment;
- pagination or virtualized list if needed;
- empty states;
- loading and degraded states;
- durable read state;
- direct link into alert detail.

## 4.4 Alert detail

Should answer:

- which strategy revision produced this alert?
- what exact instrument(s) and roles were involved?
- when was the signal valid?
- what conditions were satisfied?
- what data was stale/missing/valid?
- which parameters and state mattered?
- what evidence or prior research is linked?
- was this only an alert, a proposal, paper action, or something else?
- what can the user do next?

V0 next actions should be bounded:

- open strategy;
- open relevant research/evidence;
- open chart/market context if available;
- mark read/acknowledge/dismiss;
- pause or edit monitor;
- create a new research revision.

Do not add a disguised live-order button.

## 4.5 Alert correctness

Test:

- duplicate evaluation/delivery;
- process restart;
- stale data;
- event arriving late;
- strategy revision changed after alert;
- deleted/archived strategy;
- alert read from two devices;
- tenant isolation;
- monitor paused during evaluation;
- time-zone/session boundaries;
- expired alert;
- websocket disconnect/reconnect;
- database transaction failure;
- UI receives duplicate events.

## 4.6 Initial delivery channels

V0 default:

```text
canonical database event
→ in-product Alerts Inbox
→ optional websocket invalidation/update
```

Email, push, SMS, WhatsApp, and webhooks should be later adapters unless already safe and nearly complete.

---

# 5. Authentication, ownership, and tenancy

V0 is a multi-user commercial system even without public execution.

Required:

- secure sign-up/sign-in;
- Google sign-in where compatible;
- explicit user/tenant ownership on strategies, datasets, jobs, alerts, billing, and connections;
- server-side authorization checks;
- session expiry and revocation;
- CSRF/CORS/cookie policy appropriate to the stack;
- rate limits for auth and expensive jobs;
- no cross-tenant websocket/event leakage;
- account deletion/export/retention design;
- audit trail for privileged admin actions;
- secret and credential isolation.

Google identity should use a maintained provider/library path and backend token/session verification rather than trusting client-provided user IDs.

Do not build enterprise RBAC for V0. Do not leave ownership implicit.

---

# 6. Razorpay payments and entitlement model

Because the owner now treats a paid V0 as a commercial release, payments are a V0 workstream.

## 6.1 Boundary

Begin and finish the integration in **Razorpay Test Mode**. Do not enable live keys or real charges without a separate explicit owner go-live gate.

## 6.2 Minimal domain model

Prefer explicit internal objects rather than reading Razorpay on every request:

```text
Plan
Price / external_plan_mapping if subscriptions are used
CustomerBillingProfile
CheckoutAttempt / PaymentOrder
Payment
Subscription if applicable
WebhookEvent
Entitlement
BillingAuditEvent
```

The application remains authoritative for product entitlements; Razorpay events are external facts used to update them under verified, idempotent rules.

## 6.3 Required flow

For one-time access or a subscription, adapt to the actual commercial decision:

```text
user authenticated
→ server creates Razorpay order/subscription using Test key
→ frontend opens Razorpay Checkout with public Key ID
→ server verifies checkout/payment signature
→ webhook confirms canonical payment/subscription state
→ idempotent entitlement transition
→ user sees billing state
```

Never expose the Key Secret in frontend code, logs, screenshots, chat, or repository history.

## 6.4 Webhooks

Required:

- raw request body retained for signature verification;
- webhook secret separate from API Key Secret;
- signature verification before state changes;
- durable event identity;
- idempotent duplicate handling;
- out-of-order event handling;
- retry-safe processing;
- audit record;
- replay/manual recovery procedure;
- entitlement not granted solely from an unverified frontend callback.

## 6.5 Test matrix

At minimum:

- checkout success;
- user closes checkout;
- payment failure;
- authorized but not captured where applicable;
- captured success;
- duplicate webhook;
- delayed webhook;
- out-of-order webhook;
- invalid signature;
- wrong amount/currency/order ID;
- network timeout after customer action;
- browser refresh during checkout;
- same order submitted twice;
- subscription active, pending, halted, cancelled, completed as applicable;
- entitlement expiry/revocation;
- admin reconciliation;
- secret absent or misconfigured.

---

# 7. Minimal admin/support panel

The V0 admin surface should solve real operational needs without exposing customer strategy IP by default.

Authorized operators may need to see:

- user/account identity and status;
- plan and entitlement status;
- payment/subscription state;
- webhook processing state;
- failed jobs;
- alert-delivery health;
- provider/data connection health;
- aggregate usage/resource information;
- support receipts and error IDs;
- account suspension/reactivation actions;
- audit history.

By default, admin/support must **not** display:

- full strategy graphs/source;
- raw customer datasets;
- broker secrets;
- Razorpay secrets;
- unrestricted impersonation.

Any break-glass access must be explicit, logged, time-limited, and justified.

---

# 8. Research correctness remains the product moat

V0 should retain or complete, according to actual implementation maturity:

- immutable strategy and node identity;
- dataset/provider identity;
- point-in-time and anti-look-ahead behavior;
- explicit warm-up and missing-data semantics;
- net-of-cost backtests;
- reproducible engine/model version;
- baseline comparison;
- parameter sensitivity and neighborhoods where ready;
- locked OOS, walk-forward, Monte Carlo, and search history only where correct and usable;
- persisted jobs and evidence;
- clear failure state.

Do not expose half-correct advanced metrics merely to expand the feature list.

Every visible metric must be defined, reproducible, and attributable.

---

# 9. V0 onboarding

A recommended first-run experience:

1. Sign in with Google or supported alternative.
2. See a concise product explanation: build, test, monitor, receive alerts.
3. Open a real starter strategy.
4. Inspect the five node families in context.
5. Change one parameter or condition.
6. Run a small backtest.
7. Compare the result to the baseline.
8. Save a revision.
9. Activate signal monitoring on a supported instrument.
10. Receive or preview a representative alert.
11. Open the alert detail and understand why it exists.
12. See the upgrade/billing state at the appropriate moment.

Avoid an empty graph as the first experience.

---

# 10. Telemetry and validation questions

Track only data needed to answer product questions.

Examples:

- sign-up completion;
- time to first strategy open;
- time to first edit;
- time to first successful backtest;
- research job completion/failure;
- strategy save/version frequency;
- monitor activation;
- alert generation, open, acknowledgement, and return-to-strategy;
- payment funnel state;
- trial-to-paid conversion;
- weekly retained researchers;
- repeated alert users;
- support/error frequency;
- UI abandonment points;
- expensive job and storage cost per active user.

Do not collect raw strategy content or private trading logic merely for analytics.

Key V0 hypotheses:

- Do users understand the node model?
- Do they trust the research output?
- Does the Alerts Inbox create a recurring reason to return?
- Are explanations sufficient?
- Will users pay without public execution?
- Which missing workflow blocks retention?
- Which UI surfaces are confusing?
- Which future execution requests are real rather than hypothetical?

---

# 11. Reliability and operations

V0 release readiness requires:

- health/readiness checks;
- supervised app and worker processes;
- durable/recoverable research jobs;
- database backups and a tested restore;
- schema migration from zero and representative current state;
- structured logs and error IDs;
- telemetry/redaction policy;
- secure file/data handling;
- rate/resource limits;
- email/support recovery path;
- secrets outside source control;
- deployment rollback;
- basic incident runbook;
- no cross-tenant leakage;
- no public live-order route.

The goal is not distributed-system prestige. It is understandable operation by a small team.

---

# 12. V0 acceptance journeys

## Journey A — new paid researcher

```text
Google sign-in
→ starter strategy
→ modify
→ backtest
→ inspect evidence
→ test checkout/payment
→ entitlement becomes active
→ research remains available after reload
```

## Journey B — signal-monitoring user

```text
open validated strategy
→ activate signal monitor
→ strategy emits signal
→ canonical alert persists
→ Alerts Inbox updates
→ user opens detail
→ explanation identifies exact strategy revision and conditions
→ no order is sent
```

## Journey C — failure and recovery

```text
research job or alert worker fails
→ UI shows actionable state
→ job/event resumes or is safely retried
→ no duplicate canonical result
→ user does not lose strategy/evidence
```

## Journey D — billing ambiguity

```text
customer completes/attempts checkout
→ browser callback is interrupted
→ webhook arrives later or is retried
→ verified idempotent state reconciles
→ entitlement is correct
→ admin can inspect the decision
```

## Journey E — tenant isolation

```text
User A and User B own strategies, alerts, jobs, and billing records
→ API, websocket, admin, and direct-ID probes cannot leak data across users
```

---

# 13. Release gates

V0 is not ready until all are true:

1. Five node families shown to users have a verified conformance matrix.
2. A new user can complete the core flow without repository knowledge.
3. Normal research is acceptably responsive; heavy jobs are explicit.
4. Research output binds exact strategy/data/engine assumptions.
5. Signal monitoring cannot obtain public execution authority.
6. Alerts are durable, attributable, deduplicated, filterable, and explainable.
7. Google/auth sessions are server-verified and tenant-safe.
8. Razorpay Test Mode integration passes signature, webhook, duplicate, failure, and reconciliation tests.
9. Entitlements are server-authoritative and idempotent.
10. Admin support works without casually exposing strategy IP or secrets.
11. Backups, restore, migrations, logging, and rollback are exercised.
12. No critical security or cross-tenant defect remains.
13. Product telemetry can measure activation, retention, alert use, and payment conversion.
14. The public UI contains no accidental live-order route.

---

# 14. Required Codex outputs for the V0 lane

Create:

```text
docs/v0/
├── 00-CURRENT-V0-AUTHORITY.md
├── 01-V0-USER-JOURNEYS.md
├── 02-V0-GAP-MATRIX.md
├── 03-FIVE-NODE-FAMILY-CONFORMANCE.md
├── 04-SIGNAL-AND-ALERT-CONTRACT.md
├── 05-ALERTS-INBOX-UX-SPEC.md
├── 06-AUTH-TENANCY-AND-SESSION-AUDIT.md
├── 07-BILLING-ENTITLEMENT-AND-WEBHOOK-SPEC.md
├── 08-ADMIN-SUPPORT-BOUNDARY.md
├── 09-V0-OBSERVABILITY-BACKUP-AND-RECOVERY.md
├── 10-V0-RELEASE-GATES.md
└── 11-V0-FINAL-VERIFICATION-REPORT.md
```

Before code changes, classify every requirement:

```text
EXISTS AND VERIFIED
EXISTS BUT UNVERIFIED
PARTIAL
MISSING
BLOCKED ON OWNER CREDENTIAL/ACTION
DEFERRED OUTSIDE V0
```

Then produce a dependency-ordered implementation plan with exact write scopes and no competing agents editing the same contract.
