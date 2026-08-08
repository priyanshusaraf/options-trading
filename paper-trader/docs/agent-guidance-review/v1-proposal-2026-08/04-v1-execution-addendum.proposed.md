# PROPOSED addendum to `docs/engineering/EXECUTION_PLAN.md` — not adopted

> The plan is unchanged. This proposes a **successor to §5 (Later product sequence) only**, plus
> two corrections to §3 and the header. §1 (operating rules), §2, §4, §6, §7, §8 and §9 are
> correct as written and should survive verbatim — in particular §1's "no slice may create a
> second executable graph schema, validator, resolver or statistical-gate pipeline" and §9's
> nine-point completion record.

---

## A. Two corrections to the existing plan

### A.1 The header is a week stale

```
- **Status date:** 2026-08-03
- **Current slice:** S4.6d immutable project review snapshots
```

S4.6d is complete. Since then, eight increments landed (G-1, G-2, L1.2, L1.2b, L1.3A, L1.3B,
L1.3C, L1.4), three migrations (`0011`, `0012`, `0013`) and three ADRs (0011, 0012, 0013).

### A.2 §3's slice table stops before the work that has dominated the last week

The L1 execution band exists in §5 as a **single paragraph at product-outcome resolution**, while
in reality it has been executed as named, individually verified slices. §1 says later stages
"stay at product-outcome resolution until earlier work supplies evidence that makes detailed
planning defensible" — that evidence now exists, and the plan has not absorbed it.

**Proposed addition to §3** (record, not re-plan):

| Slice | Outcome | Depends on | Status |
|---|---|---|---|
| G-1 | Platform component library; a strategy stops serving as the registry | S4.6d | done — `app/ir/library.py`, identity byte-identical (`1077ee8c…`) |
| G-2 | Name the signal → intent → order boundary | — | done — `WS-02` §3, documentation only |
| L1.1 | Shared IR strategy adapter with an honest parity claim | S4.6d | done — Stage 0 |
| L1.2 | Canonical execution selection authority, wired into `EngineRunner` | L1.1 | done — ADR 0012, `execution_binding.py` |
| L1.2b | Execution attribution carried from scan to fill | L1.2 | done — no schema change |
| L1.3A | Managed shadow deployment binding | L1.2b | done — migration `0011` |
| L1.3B | Separated execution books; authority becomes `(source, mode)` | L1.3A | done — migration `0012`, fails closed to `live` |
| L1.3C | Grant `(ir_graph, paper, authoritative)` | L1.3B | done — migration `0013`, `paper_authority.py` |
| L1.4 | Paper-authority runtime hardening | L1.3C | done — 29 deterministic tests; one real defect found and fixed |
| L1.5 | **The written live-adoption design** (`CONTINUE.md` §4, six items) | L1.4 | **ready — owner-gated on approval of the design, not of code** |

---

## B. Proposed successor to §5 — the V1-oriented sequence

The existing L1–L5 bands were ordered by **dependency readiness**. The V1 direction reorders by
**release value**, which is a legitimate change and should be recorded as one rather than
absorbed silently. The most consequential consequence: **parts of L5 (accounts, billing,
additional brokers) move ahead of L2 (cockpit) and L3 (data identity)**, so auth and multi-broker
will land on a data layer that is still partly implicit. That is acceptable if and only if §V1.1
below lands first.

### V1 — first serious release, target first week of September 2026

Ordered by what unblocks the most downstream work. Rationale, classification and the challenges
to this scope are in [`02-v1-classification.md`](02-v1-classification.md).

| # | Slice | Product acceptance | Depends on |
|---|---|---|---|
| **V1.1** | **Canonical instrument identity** | One instrument has one identity across providers; each connection maps it to its own symbol/token/lot/tick; no adapter carries its own symbol logic | none — **do this first** |
| **V1.2** | **Connections and capabilities** | An account holds several credentialed connections; each declares `live_data / historical_data / depth / option_chain / execution / positions / funds`; a deployment resolves data and execution roles independently; a strategy requests semantic data and never names a broker | V1.1 |
| **V1.3** | **Second broker + conformance suite** | Two adapters pass one suite; the suite fails an adapter that lies about a capability | V1.2 |
| **V1.4** | **Reusable components V1** | A selection becomes a versioned component with a typed interface, stored per owner, appearing in the palette, with identical content address and identical re-resolution | none (language already supports it) |
| **V1.5** | **Component vocabulary** | IF/ELSE/AND/OR/NOT/XOR, sustained and nested conditions, candlestick and price-action nodes — each a component, no language change | V1.4 for the store; otherwise none |
| **V1.6** | **Accounts and ownership** | Real principals, credentials, sessions; owner scope on projects, artefacts, versions, deployments and connections; identifiers namespaced per owner | none — **namespacing is free and should land immediately** |
| **V1.7** | **Cockpit to a frozen contract** | Health, deployments, positions, orders, reconciliation, approval queues and lifecycle actions render truthfully; every number is true or visibly Unknown | backend contract frozen 2026-08-08 |
| **V1.8** | **Launch hardening** | Dependency findings closed, bundle inside budget, error taxonomy reaching users unchanged, onboarding docs, deployment UX | V1.2, V1.6 |
| **V1.9** | **Live-adoption design, written and owner-reviewed** | The six items of `CONTINUE.md` §4 exist as a document. **No code.** | L1.4 |

**Seams created in V1, features deferred:** cross-instrument execution target (declared field,
paper-only path); the narrower-scope-may-only-tighten rule for `scoped_config`; job-boundary
hygiene (no new module-global singletons); multi-leg (already contracted in `WS-02` §3).

**Explicitly not in V1:** brokers 3…N; live IR authority; payments until the regulatory question
has an owner answer; order flow and Level-2 history; marketplace, packaging, signing, DRM;
distributed backtesting; automatic lead-lag discovery.

### V1-adjacent, owner-gated, and on the critical path

Not engineering slices. Nothing reaches a user until they clear.

1. **Deploy the eight-phase architecture migration** — committed, verified, off the box for
   several sessions. Touches sizing, exits and routing.
2. **VPS OS reboot** (5 ESM security updates) and **droplet resize 1 GB → 2 GB**.
3. **Hosting posture** — whether the multi-user product shares a box with the owner's live
   trading engine. See [`02-v1-classification.md`](02-v1-classification.md) §5.1. A backtest
   sweep already shares the process with the risk lane, and hard invariant 2 says nothing may
   block an exit.
4. **Regulatory position on charging for order routing** in India (broker-level algo
   registration / order tagging), which `docs/product-overview.md` §6 has flagged as unconfirmed
   since 2026-07.

### V2 — after the release

- **Cross-instrument observation**: runtime input keying by `(domain, name)`, per-domain frame
  acquisition, multi-series backtest. Driven by one concrete target artefact
  (`NIFTY + VIX → SENSEX`), which dictates the single cross-domain node the language needs.
  Introduce it as an **explicitly typed cross-domain operation**; never relax F7 globally
  (architecture review, Amendment A-1).
- **Cross-instrument execution target on the live path** — owner-gated; splits observed from
  traded in `ExecutionBinding`.
- **Live IR authority** — three independent reviewed changes, after V1.9's design is approved.
- Brokers 3…N, each an independent boring slice.
- Payments, once §V1-adjacent 4 is answered.

### L2–L5 — unchanged in content, re-labelled in order

The existing L2 (cockpit and operational review), L3 (first-class data layer), L4 (packaging and
marketplace) and L5 (distribution and ecosystem) descriptions in `EXECUTION_PLAN.md` §5 remain
correct and should not be rewritten. Under V1 their **order** changes:

| Band | Was | Under V1 |
|---|---|---|
| L2 cockpit | after L1 | partly pulled into V1.7; the rest unchanged |
| L3 data layer | third | **split** — instrument identity pulled into V1.1; everything temporal (calendars, sessions, corporate actions, back-adjustment, replay, retention) stays in L3, after V1 |
| L4 packaging/marketplace | fourth | unchanged. WS-05 must not start without the sandbox policy |
| L5 distribution | last | **partly pulled into V1** — accounts, additional brokers, onboarding. Billing and enterprise controls stay in L5 |

**§7's product-level checkpoints stay as they are.** C4 (reversible execution) is where the V1
live-adoption design lands; C5 (product operations) is what V1.7 advances. Do not renumber them.
