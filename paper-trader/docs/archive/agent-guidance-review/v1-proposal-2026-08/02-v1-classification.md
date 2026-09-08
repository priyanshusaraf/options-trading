# 02 — V1 classified, and challenged

Every idea in the 2026-08-08 V1 brief, classified **IMPLEMENT NOW / CREATE SEAM NOW / SAFE TO
DEFER / SPECULATIVE**, with the specific code that supports or blocks it.

Where a classification differs from the owner's stated V1 priority, that is marked
**⚠ CHALLENGE** and argued. The brief asked for this; it is not resistance to the direction.

**The direction itself is sound and the architecture supports it.** The 2026-08-07 architecture
review already stress-tested twelve candidate directions against real code and found **no
foundational contradiction**. What follows disputes *scope and sequence for September*, not the
product.

---

## 0. The headline judgement

> **September V1 is coherent as a direction and not coherent as a scope.**

Four weeks (2026-08-08 → first week of September) against nine major items, at this
repository's demonstrated pace, is roughly 3–4× over-committed. The evidence for the pace is in
the tree: `CONTINUE.md` and `EXECUTION_PLAN.md` record one bounded slice per session with a full
checkpoint, and the L1 band (L1.2 → L1.4, one subsystem — execution binding, books and paper
authority) consumed 2026-08-04 → 2026-08-07 across four increments and three migrations. That is
the *right* pace: it is what produces non-vacuous guards and paisa-exact ledgers. Doubling it by
lowering the evidence bar would trade the single most valuable property of this codebase for a
date.

Two items in the V1 list are also **not engineering-limited at all** and cannot be compressed by
working harder:

- **Payments/subscriptions** implies charging Indian users for order routing. `product-overview.md`
  §6 already flags broker-level algo registration / order tagging as unconfirmed. That is an
  owner-and-legal gate.
- **Two production deployments have been owner-blocked for several sessions** (the eight-phase
  architecture migration; the VPS reboot and 1 GB → 2 GB resize). Nothing engineered in August
  reaches a user until those clear. **This is the actual critical path for a September release,
  and it is not a coding task.**

A defensible September V1 is stated at the end of this document (§6).

---

## 1. IMPLEMENT NOW

Work that should start immediately, is architecturally supported, and unblocks the rest.

### 1.1 Canonical instrument identity across providers
**Why now:** every other V1 item silently depends on it. Multi-broker without it forks symbol
handling per adapter; cross-instrument without it cannot say what "NIFTY" means to two feeds;
the canonical-instrument table is the thing OpenAlgo built first and correctly (`SymToken`:
canonical symbol → `brsymbol`/`brexchange`/`token`/`lotsize`/`tick_size`).
**What exists:** `Instrument` is a contract-ish key today; the architecture review's row 12 says
plainly "no dataset identity". L3 owns this at product-outcome resolution only.
**Smallest V1 form:** a canonical instrument registry with a stable identity, per-connection
symbol mapping, and lot/tick metadata. **Not** corporate actions, calendars, back-adjustment or
continuous futures — those are L3 proper.
**Risk if skipped:** the most expensive kind. Symbol handling written twice is the `candles.py`
defect at ten times the size.

### 1.2 Reusable components / subgraphs V1
**Why now:** it is nearly free, and it is the single most visible piece of the "visual platform"
identity. Drill 4 (2026-08-07) proved `publish()` already derives a component from a graph
mechanically, reproduces the shipped ATR body address **exactly**, and re-resolves to
byte-identical node and cache ids. C15 already makes a subgraph and a component the same kind of
thing.
**What is missing is not language.** It is: a place to store a user's components, a "collapse
selection into a component" editor operation, and the component appearing in the palette
(`descriptors.component_catalogue`, now correctly fed by `app/ir/library.py` after G-1).
**Explicitly not in V1:** packaging, signing, sandboxing, permissions, hiding internals,
marketplace, DRM. Those are L4 and WS-05 says the transport must not ship without the sandbox.
**Also closes** WS-01 §5's open "worked `publish()` round trip" item.

### 1.3 Connections as first-class objects, with declared capabilities
**Why now:** it is the model change that makes "Upstox data → Zerodha execution" expressible,
and it is cheap because the seams already exist and are already separate:
`app/providers/base.py::MarketDataProvider` (data) and
`app/engine/broker_protocol.py::Broker` / `ExecutionVenue` (execution) were never one interface.
**What V1 adds:** a `Connection` record — an account's credentialed link to a provider — that
declares a capability set (`live_data`, `historical_data`, `depth`, `option_chain`, `execution`,
`positions`, `funds`), plus resolution of "which connection serves this need for this
deployment". Multiple connections per account falls out of the same model.
**The real blocker to name:** `providers/factory.py` is a **process-wide singleton** with one
Kite token. Multiple connections is a model change *and* a lifetime change. Budget for it.
**C13 applies:** a capability check may not appear under `app/engine/`. It resolves in
`app/core/` and the engine consumes the verdict, exactly like `execution_binding`.

### 1.4 A second broker — exactly one
See §2.1 for the challenge to "several". Implementing one second broker end-to-end
(recommendation: **Upstox**, because it is the owner's own stated data-side example) is what
proves the connection/capability contract. A conformance suite that both brokers pass is the
deliverable, not the count.

### 1.5 Auth and ownership — the minimum that is real
**Why now:** it is a hard prerequisite for *anything* multi-user, including payments, and it is
the item most likely to be under-estimated.
**What exists:** `app/api/auth.py` is **one shared bearer token** (`PT_API_TOKEN`; empty
disables auth). `app/api/principal.py` deliberately built the seam — a `Principal` on every
request, `ANONYMOUS_OWNER` rather than `None`, scopes modelled and unused. That seam is good and
was built for exactly this moment.
**What V1 must add:** real accounts, credentials, sessions, and an owner column on the objects
that need one. **The blocker with teeth:** `graph_artifacts.identifier` is a **global primary
key** (gap G-5) and every table in the application database is global. Retrofitting an owner
scope touches `graph_versions`'s composite PK and `ir_paper_deployments.graph_identifier`.
**Free hedge, worth taking this week regardless of adoption:** identifiers are already dotted
namespaces, so prefixing them per owner costs nothing now and removes the collision entirely.

### 1.6 Cockpit frontend — as a backend deliverable
The backend cockpit contract is frozen (`WS-02` §3a, `WS-08` §3a; lifecycle capability tables
landed at `b47e8f5`). Under the agent-surface split, **Claude's V1 obligation here is contract
stability, fixtures and any backend gap the frontend hits** — not React. This is a re-scoping,
not a de-prioritisation: the cockpit is still a V1 release blocker, it is just mostly someone
else's keyboard.
**One genuine Claude item:** the frontend's own known debt is recorded in `CONTINUE.md` §3 —
six `npm audit` findings (three moderate, two high, one critical) and a 227.39 kB gzip bundle
over the 200 kB budget. A launch ships neither. Dependency hardening is backend-adjacent work
Claude can do.

---

## 2. CREATE SEAM NOW

Name the boundary, write the contract, build nothing.

### 2.1 Multi-broker breadth — ⚠ CHALLENGE
> V1 asks for "multi-broker architecture + several major Indian brokers".

**Take the architecture; refuse the count.** The OpenAlgo teardown is unambiguous and was
written by this project: 35 broker plugins is *"a moat built of labour, not architecture"*, and
each adapter is four directories (auth, orders, data, funds, margin, GTT; symbol master;
streaming). Delivering "several" in four weeks means either shallow adapters that fail on the
long tail — token refresh in flight, partial fills, rejection storms, GTT semantics, lot-size
drift — or displacing everything else in V1.

The long tail is not hypothetical here: `product-overview.md` §7 records that even for **Kite**,
after 50 real orders, "token-refresh-in-flight, the circuit breakers, and the
repeated-broker-rejection branch have still never run for real."

**Seam:** the capability protocol + a conformance suite every adapter must pass. **Implement:**
one second broker (§1.4). **Defer:** brokers three through N, each as an independent, boring,
post-V1 slice. Shipping two brokers that are correct beats five that are plausible.

### 2.2 Cross-instrument: split observation from execution target — ⚠ CHALLENGE
> V1 asks for "cross-instrument strategies V1" with `NIFTY options + NIFTY futures + India VIX →
> trade SENSEX`.

**These are two features and the brief treats them as one.** The architecture review keeps them
apart as rows 4 and 5 for good reason:

| | Multi-instrument **observation** | Cross-instrument **execution target** |
|---|---|---|
| Language | Supported — `domain` is part of the type (F7) | Supported |
| Runtime | Blocked, **cheaply**: `runtime.py` contains neither `domain` nor `instrument`; `evaluate()` takes one flat mapping. Multi-domain means keying inputs by `(domain, name)` — confined to one file | n/a |
| Acquisition | Blocked: `scan_signals` is one instrument, one interval, one `history_days` | n/a |
| Backtest | Blocked: `app/backtest/engine.py:2` says "Single-instrument backtest" | n/a |
| Binding | — | **Blocked.** `ExecutionBinding` and `PaperBinding` carry a single `instrument_key`; observed and traded are the same field |
| Money | Unaffected — `positions.instrument_key` is the *traded* instrument and always was | **This is a money-path change** |

**Proposal:** observation is a real V1 candidate (runtime keying + per-domain acquisition +
multi-series backtest — bounded, and none of it touches money). The **execution target** gets a
declared field and a paper-only path in V1, and reaches live only through the standing owner
gate.

**And heed the amendment the owner already accepted.** Amendment A-1 of the architecture review
says cross-domain behaviour must arrive as *explicitly typed cross-domain operations*, never by
relaxing F7 globally — and that **none should be designed until a real strategy needs one.**
V1's `NIFTY + VIX → SENSEX` example is that strategy. Write it as a concrete target artefact
first; let it dictate the one cross-domain node the language needs. Do not design a family.

### 2.3 Strategy OS authority into live execution — ⚠ CHALLENGE on framing
> V1 asks for "integration with existing live execution when explicitly approved".

The seam is already built and already gated, and the framing in the brief slightly understates
what stands between here and there. `(ir_graph, live, authoritative)` is **absent from `GRANTS`,
designed nowhere, and reachable only through three independent reviewed changes** (the grant, a
table whose CHECK permits it, and a service able to write it). `CONTINUE.md` §4 states the
prerequisite plainly: **the next deliverable is a written design, not code** — six enumerated
items, owner-approved before any live adoption begins.

**Classification: CREATE SEAM NOW = write that design.** It is a genuinely good use of V1 time
and costs no live risk. **Do not classify live IR authority itself as V1 scope.** A first
release does not need it: the product is a visual platform whose strategies research, backtest,
paper-trade and deploy. The owner's own bot keeps trading its hand-written strategy meanwhile,
which is the correct hedge.

### 2.4 Layered global/portfolio/strategy/position constraints
`app/core/scoped_config.py` already resolves Platform → Deployment → Instrument, narrowest wins,
through one validation gate. The seam exists. **The rule that must land with the first populated
narrow scope:** a narrower scope may only *tighten* a safety key (gap G-6 — today a deployment
could set a looser `max_daily_loss` than the platform; unreachable only because every narrow
scope is empty). Add the rule, not the scopes.

### 2.5 Multi-leg outputs — spreads, baskets, hedges, rolls
Already correctly handled: G-2 named the signal → intent → order boundary in `WS-02` §3 on
2026-08-07, with three invariants and four assumptions later slices may not deepen. **Nothing
more is needed for V1.** Do not build `ExecutionIntent`; do enforce the four forbidden
assumptions at review.

### 2.6 The job/worker boundary
`app/backtest/sweep.py` is a **process-global singleton** — `raise RuntimeError("a sweep is
already running")` is per *process*, not per user (gap G-3). The second concurrent user's
backtest fails outright. For a multi-user September this stops being theoretical.
**Seam only:** new long-running work must be written so it *could* become a claimed job — i.e.
not as a second module-global singleton. **Explicitly do not introduce** queues, workers,
microservices, Postgres or distributed execution. The review is emphatic and so is the outage
history: this system's real scaling failures have been *query shape* and *memory*, never
architecture.

### 2.7 Typed non-OHLCV data sources
`FRAME_COLUMNS` is `date, OHLCV`. This is **not** a language limit — Drill 1 authored, validated,
resolved and evaluated a component taking `bid/ask/bid_qty/ask_qty` with **zero repository
edits**, and `IRGraphStrategy.required_inputs` comes from the graph, not a fixed tuple. The gap
is the frame contract plus acquisition, and the `volume` addition of 2026-08-02 is the precedent
for widening it. Widen it when a V1 strategy needs one column; do not build a data-source
framework.

---

## 3. SAFE TO DEFER

Named, homed, and deliberately not in V1.

| Item | Home | Why deferring is safe |
|---|---|---|
| Order-flow / depth / OFI as strategy inputs | L3 | The platform already *reads* depth for routing; nothing forces a wrong answer today |
| Level-2 history | L3 | The brief already excludes it |
| Futures back-adjustment, continuous contracts, corporate actions, calendars | L3 | No dataset identity exists yet; §1.1 is the prerequisite, not this |
| Marketplace, packaging, signing, DRM, permissions | L4 / WS-05 | WS-05 §1: a transport without a sandbox "is the fastest available way to lose the account" |
| Distributed backtesting | — | Explicitly excluded by the brief. Correct |
| Automatic lead-lag discovery | Research plane | Speculative until cross-instrument observation exists |
| Node-scoped durable state | G-8 | `KernelSpec`'s field set is closed and refuses unknown fields, so adding one later is local and guarded. Prefer the pure model; the evidence that justifies the contract is a component that genuinely cannot be expressed in it |
| Postgres migration | — | The trigger is a measured lock-wait, not a headcount |
| ≥20 genuine market sessions, dataset cleaning, native OHLCV replay fidelity | WS-02 | Already deferred by owner decision 2026-08-04 |

**IF/ELSE/AND/OR/XOR, nested and stateful conditions, candlestick and price-action nodes** are
deferred in a different and happier sense: they are **already supported by the language** and
need only new components. `bool` is a closed value type, `predicate.*` components exist,
`where(cond,a,b)` is a kernel, and a "true for 10 consecutive bars" predicate was verified to
resolve, evaluate and pass the C11 causality check. Add each one when a strategy needs it —
which, for a visual platform, will be soon and cheaply. **This is a V1 content task, not a V1
architecture task**, and it is where the visible product value per hour is highest.

---

## 4. SPECULATIVE

Do not design these. Recording them so nobody builds them under another name.

- A general cross-domain operator *family* (comparison, synchronisation, normalisation,
  cross-domain predicates) before one real strategy needs one node.
- A node-scoped durable-state contract.
- Multi-tenant data isolation beyond an owner column.
- An `ExecutionIntent` object before a second leg exists.
- A second execution engine, event sourcing, a message broker, microservices.
- Tick-level or intrabar semantics — RFC §5(7) excludes them; C10 and C11 rest on completed
  candles only.

---

## 5. Conflicts and dependencies the brief does not name

**5.1 Hosting: the owner's live account and a multi-user product cannot share one box.**
Hard invariant 2 says nothing may block an exit. The V1 product invites strangers to run
backtests and research on a 1 GB droplet that has OOM'd twice with the engine running, where a
sweep already shares the process with the risk lane. **A V1 that onboards users onto the box
that trades the owner's money is a safety regression regardless of code quality.** The decision
— separate deployments, or accept the coupling — is an owner decision and should be made before,
not after, the first customer.

**5.2 Payments presuppose accounts presuppose tenancy, which the plan calls L5.**
V1 promotes the *last* band of `EXECUTION_PLAN.md` §5 ahead of L2 (cockpit) and L3 (data
identity). That is a legitimate business call, but it should be made explicitly: the plan's
ordering was derived from dependency readiness, and inverting it means accepting that auth,
billing and multi-broker land on a data layer that is still implicit.

**5.3 The `Instrument` question sits under both §1.1 and L3, and only one of them can own it.**
Recommendation: V1 takes a bounded slice (identity + per-connection mapping + lot/tick), and
`EXECUTION_PLAN.md` L3 keeps everything temporal. Write that boundary down or it will be
rediscovered as a conflict.

**5.4 Deployment debt is the real September risk.** Nothing in this document is on the box.
`PROGRESS.md` §1 says "Deployed from this branch: **nothing.**" A release in the first week of
September requires the owner-blocked items to clear in August, and requires at least one
rehearsal deploy of a large accumulated diff — which is exactly the shape of change
`scripts/deploy.sh` and the live-money rule were built to slow down.

**5.5 An honest look at what V1 does *not* fix.** The platform still has no verified
net-of-cost edge, and `TARGET` has fired zero times in 72 live trades. A visual builder makes it
easier to author strategies whose edge is equally unproven. That is not an argument against V1 —
research, backtesting and admission are precisely how the product answers it — but "does it
work?" is the question the OpenAlgo teardown identifies as the category-winning one, and V1's
scope contains no item that improves the *answer*, only items that improve the *asking*.

---

## 6. A September V1 that is deliverable

Offered as the counter-proposal the brief invited. Same direction, cut to fit.

**Ship:**

1. Canonical instrument identity (bounded) — §1.1
2. Connections with declared capabilities; multiple per account; data role separated from
   execution role — §1.3
3. **One** second broker end-to-end + a conformance suite both pass — §1.4
4. Reusable components/subgraphs V1 (store, collapse-to-component, palette) — §1.2
5. A meaningful set of logic / price-action / candlestick components — §3, cheap and highly
   visible
6. Auth, accounts, ownership columns, identifier namespacing — §1.5
7. Cockpit frontend to a frozen contract (ChatGPT/Codex), plus dependency and bundle hardening
   (Claude) — §1.6
8. The written live-adoption design, owner-reviewed, unimplemented — §2.3

**Seam only:** cross-instrument execution target; layered-constraint narrowing rule; job
boundary hygiene; multi-leg (already done).

**Cut from V1:** brokers 3…N; live IR authority; payments *until the regulatory question has an
owner answer*; cross-instrument execution on the live path; order flow; marketplace.

**Do first, this week, because everything else waits on them:** identifier namespacing (free),
the canonical instrument slice, and getting the owner-blocked deploys unblocked.
