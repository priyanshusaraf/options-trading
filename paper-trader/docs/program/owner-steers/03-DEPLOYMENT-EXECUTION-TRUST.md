# Deployment, Execution & Trader Trust Steer

## Goal

Make deployment understandable, reversible and safe enough that an experienced trader can trust Strategy OS with real capital without surrendering ownership of strategy IP.

---

## 1. Deployment object

A deployment binds:

- immutable strategy version;
- instrument-role bindings;
- parameter overrides;
- data provider bindings;
- execution account/broker;
- shadow/paper/live mode;
- capital allocation;
- sizing policy;
- schedule;
- execution policy;
- protection policy;
- resource plan;
- provider compatibility receipt.

A strategy may have many deployments.

---

## 2. Deployment preflight

Before paper/live activation, compile and display:

- strategy causality status;
- indicator warmup/history sufficiency;
- live-field availability;
- historical-field availability;
- instrument/contract resolution;
- point-in-time rule compatibility;
- cross-instrument freshness/alignment rules;
- provider subscription usage;
- expected compute/resource class;
- execution order compatibility;
- protection compatibility;
- account/risk constraints;
- estimated earliest valid evaluation;
- backtest/paper/live eligibility.

No generic “deployment failed.” Give the trader the actual reason.

---

## 3. Position sizing hierarchy

Risk hierarchy:

Account/portfolio hard limits
-> strategy allocation
-> deployment allocation
-> trade sizing

Sizing nodes may support:
- fixed quantity/lots;
- fixed capital;
- equity percentage;
- risk percentage;
- stop-distance sizing;
- volatility sizing;
- max/min caps.

Concurrent deployments must not independently reserve the same capital.

---

## 4. Multi-strategy position ownership

Use virtual strategy/deployment books with explicit attribution.

If Strategy A is long HDFC and Strategy B is short HDFC:
- retain separate strategy ownership/state;
- reconcile against broker-level net position;
- do not let broker netting erase strategy analytics or exit ownership.

Execution/account aggregation may net externally where required, but internal ownership remains explicit.

---

## 5. Open-position version ownership

Default:
> An open position remains managed by the strategy version that created it.

Publishing/deploying V8 does not silently alter V7 positions.

Optional reviewed takeover/migration may be added later.

---

## 6. Protection semantics

Distinguish:

### Strategy-managed exits
Arbitrary graph-driven exits.

### Software-managed hard protection
Strategy OS watches conditions and submits protection orders.

### Broker/exchange-resident protection
Protection persists independently of the Strategy OS application where broker capability supports it.

User-facing protection node expresses intent, not broker vocabulary.

Examples:
- hard stop;
- target;
- trailing behaviour;
- persistence requirement;
- fallback policy.

The adapter compiles the intent to supported provider primitives.

Do not pretend two brokers provide equivalent guarantees if they do not.

Allow a deployment policy such as:
> hard protection must survive Strategy OS process failure.

If the provider cannot satisfy that requirement, the live deployment should fail preflight rather than silently weakening protection.

---

## 7. Order semantics

Execution intent may include:
- market;
- limit;
- stop;
- stop-limit;
- marketable-limit;
- validity where supported;
- slippage tolerance;
- partial-fill handling;
- cancel/replace policy.

Unsupported semantics must be rejected or explicitly transformed with user-visible consequences. Never silently substitute a materially different order type.

---

## 8. Pyramiding and scaling

Support:
- add only on renewed signal;
- add only when profitable;
- fixed/fractional add size;
- maximum additions;
- maximum total risk;
- aggregate stop management;
- partial scale-out;
- re-entry of exited size where explicitly designed.

All additions remain attributed to the deployment/position lineage.

---

## 9. Degraded deployment states

Do not model only LIVE/DEAD.

Useful states include:
- warming up;
- healthy;
- waiting for market;
- waiting for contract roll;
- data degraded;
- stale;
- provider limited;
- execution degraded;
- protection degraded;
- suspended;
- recovering.

Permissions under degraded states must be explicit.

Examples:
- UI disconnect -> continue trading;
- noncritical historical API outage after warmup -> continue;
- signal data stale -> block new entries;
- position protection data stale -> highest-severity escalation;
- execution broker disconnected -> block new orders and run recovery policy.

---

## 10. Senior-trader trust requirements

### Strategy IP confidentiality
V1:
- no support/admin/product UI may display customer strategy graph/source;
- encrypt strategy artifacts at rest;
- strict tenant ownership checks;
- separate strategy storage access from broker-secret access;
- production access should be least-privilege;
- privileged break-glass actions logged and tightly controlled;
- ordinary support workflows must operate through diagnostics/receipts without reading strategy contents.

Do not market V1 as cryptographic zero-knowledge if server-side execution requires plaintext at runtime.

Post-V1 options:
- team/coworker ACL sharing;
- revocable permissions;
- view/use/edit/deploy rights;
- organization-owned strategy assets;
- local runner or confidential-compute investigation for stronger operator-blind guarantees.

### No silent semantic change
- strategy versions immutable;
- node versions immutable;
- provider adapter/material data changes trigger compatibility review;
- open positions remain on creating strategy version.

### Reproducibility
A trader can inspect:
- what strategy version ran;
- what node versions ran;
- what data/provider/version ran;
- what market-rule snapshot applied;
- what contract was selected;
- why the order/exit occurred.

### Explainability without exposing secrets
The system should be able to explain “why did this trade fire?” from evaluation receipts, without requiring internal staff to read strategy source.

### User control
- arm/disarm;
- kill switch;
- suspend deployment;
- paper/shadow before live;
- explicit migration/upgrade actions;
- visible block reasons.

---

## 11. Sharing scope

Coworker/team sharing is **not V1**.

Do not spend current scope on collaboration UI.

However:
- keep strategy ownership explicit;
- avoid schema assumptions that one user is the permanent only principal;
- leave room for future ACL grants and organization ownership.

Future sharing should be explicit, revocable and permission-scoped. No implicit sharing through common accounts.
