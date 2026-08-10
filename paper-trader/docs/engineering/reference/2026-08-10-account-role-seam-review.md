# The account / role seam — architecture review

**Date:** 2026-08-10
**Question:** how should Strategy OS model broker connections, account actors and role bindings,
and what does OpenAlgo teach us about it?
**Verdict:** **REFACTOR — one narrow correction.** Scope below.

---

## 0. What was already settled, and is not re-litigated here

- **The roles doctrine is already written and already enforced.** `app/providers/capabilities.py`
  opens by stating that market data, account/portfolio, execution and instrument resolution are
  distinct roles *because* "one user may hold several connections and use them for different
  jobs — market data from one broker, execution at another." The conformance contract
  (`tests/provider_conformance.py`, 2026-08-09) holds every adapter to it.
- **OpenAlgo is REJECT for code, REFERENCE ONLY for behaviour.** AGPL-3.0; §13's network clause
  triggers on serving users over a network, so a hosted Strategy OS would have to publish its
  complete corresponding source. Teardown §0, and the reuse matrix in the 2026-08-07 extension
  review. Re-derive, never transcribe.
- **The OpenAlgo teardown exists** (`docs/reports/2026-08-02-openalgo-competitive-teardown.md`,
  784 lines) and its R1–R4 already name what to take. This review does not repeat it.

## 1. What is actually true today

| Fact | Evidence |
|---|---|
| Execution identity is derived from the *data* object | `broker_factory.py:84` — `token = getattr(provider, "access_token", None)`; the order client is then built from that token |
| A non-Kite provider silently yields a paper broker | `broker_factory.py:78` — `if live_execution_enabled() and caps.provider_supports(provider, LIVE_EXECUTION)`, else `return PaperBroker(...)`. No refusal, no log |
| The data provider is a process-wide singleton chosen by one env var | `providers/factory.py:11` `get_provider()`, `s.provider` ∈ {replay, kite, mock} |
| …but it is reached from only **four** files | `providers/factory.py`, `backtest/sweep.py`, `engine/runner.py`, `api/backtest_routes.py` |
| The money records already carry the seam's vocabulary | `ExecutionIntent.broker`, `.account_scope`, `.connection_scope` (`db/models.py:164-166`), migration `0014` |
| Restart recovery is already scoped by it | `execution_lifecycle.py:458-470` `unresolved_entries(deployment_id, account_scope, connection_scope)` |
| …but every live entry writes one constant | `live_broker.py:60` `KITE_LEGACY_CONNECTION_SCOPE = "kite:legacy"`, written at `:152` |
| Deployments already carry an account | `db/models.py:111` `account_id`, default `"default"` |
| The execution layering is already correct | `broker_protocol.py` — `Broker` (domain verbs) → `ExecutionVenue` (wire verbs) → `KiteVenue`; `VENUE_FACING_METHODS` fails the build on an inherited venue method |

**Read that table as one sentence.** Every layer *except one* already names the connection as a
first-class thing. The schema names it, recovery queries it, the venue protocol is factored for
it, and the capability vocabulary was written for it. The single place where the abstraction
collapses is the constructor: `make_broker(provider, …)` takes the data provider and pulls the
execution credential off it. That is the defect. It is roughly one function wide.

This is the codebase's own defining defect class, third shape — **a mechanism that is built and
correct but is never given real data**. `connection_scope` is a live example: three call sites,
one constant value.

## 2. Invariants in the blast radius

From `CLAUDE.md` — **Providers**: "Data provider ≠ execution broker · Strategy OS owns canonical
instrument identity, never a provider's symbol or token · multiple provider connections per
account must remain architecturally possible · a strategy may observe different instruments from
its execution target."

The correction does not weaken that invariant; it is the first slice that makes the first clause
*true in code* rather than true in prose. **Money** is untouched: `execution_book.py` decides
whose money it is by execution mode, and a connection is not a mode. **Authority** is untouched:
`AUTHORITY_BY_SOURCE` grants by `(source, execution_mode)`, and adding a connection dimension to
the *builder* does not add one to the grant. Explicitly: this slice must not introduce a second
execution authority, and does not.

## 3. What OpenAlgo actually teaches — and where it must not be followed

**Their broker layer is the crown jewel and their account model is not.**

`database/auth_db.py:505-525` is candid in its own comment: "OpenAlgo is single-user/single-broker
per instance, so all devices share ONE server-side broker WebSocket feed." `Auth.query.filter_by(name=name).first()`
— one row, one session. Their scaling answer to 500 users is 500 deployments. Teardown §7 already
recorded the consequence: *"OpenAlgo cannot become a hosted multi-tenant Strategy OS without a
rewrite of its session, worker, and licence model. That is not a temporary gap. It is the shape of
the building."*

So: **do not look to OpenAlgo for the account-actor model. There isn't one.** Take these instead,
all already catalogued as R1–R4:

| Take | Why it applies to phase 6 |
|---|---|
| **R1 — uniform broker plugin contract as a typed capability protocol** | We have the vocabulary (`capabilities.py`) and the conformance suite. Their 36 adapters prove the directory contract makes broker #2 a known-shape task. Their weakness — startup-only discovery, env-gated, no version negotiation — is what our typed protocol should fix |
| **R2 — canonical symbol as a structured value with venue projections** | This *is* the queued `spot_symbol`/`option_name` relocation. Their `NIFTY28MAR2420800CE` string re-encodes structure into text and re-parses it. Keep `(underlying, expiry, strike, right, segment)` structured, render only at the venue boundary. Upstox's `SEGMENT|ISIN` keys — underivable from a tradingsymbol — are the second real mapping that makes the relocation provable |
| **R3 — fan-in bus topology (SUB binds, PUBs connect)** | The 500-user correction requires market data fanned in *once per distinct instrument set* and broadcast. Adopt the topology behind an interface now; ZMQ later is a one-file change. Steal their failure story verbatim: a PUB that binds makes `subscribe` succeed while no tick is ever delivered |
| **R4 — single-flight coalescing with *shared failure*** | Directly attacks the measured backtest I/O floor (83% of a cold 10,000×5 run is provider wait). Sharing the failure is the non-obvious half and the reason it survives rate limits |

## 4. Challenge

- **What breaks if we do nothing?** Upstox cannot ship — not because its adapter is wrong (it is
  written and parked at `58436bb` on `feat/exec-completeness`) but because selecting it would
  build no live broker and fall silently to paper. Multi-account is impossible. And one of the
  three named attacks on the cold-backtest I/O floor is parallel data connections, which needs
  exactly this. Three roadmap items are blocked on one function.
- **Seam or feature?** Seam — and it is the cheap-now/expensive-later kind. Every additional
  entry path written before the seam is another site to correct after it.
- **Second schema / validator / resolver / hash / ledger / deployment model / execution authority?**
  None. The schema exists (`0014`), the deployment model exists, authority is untouched. If a
  proposal in this area introduces a second one, it is disqualified — say so and stop.
- **Proportional to scale?** The narrow correction is proportional to *two* connections, which is
  what Upstox creates. The actor-per-account topology is proportional to 500 users and belongs in
  phase 7, not here. Do not build the actor supervisor in this slice.
- **Cost of being wrong, and does it grow?** Grows. The correction touches a constructor today;
  after phase 7 it would touch a supervisor, a lease and a fencing protocol.

## 5. Verdict — REFACTOR, narrowly

**Correct `make_broker` so execution identity comes from a connection, not from the data provider
object.** Everything else in phase 6 defers with a named home.

In scope:

1. A `Connection` value — broker, credentials, declared capability set, stable `connection_scope`
   string. One per (account, broker). The vocabulary already exists in `capabilities.py`.
2. `make_broker(connection, …)` instead of reaching into `provider.access_token`. The data
   provider and the execution connection become two arguments that *may* be the same connection
   and need not be.
3. **A non-executing connection must refuse, loudly, not fall to paper.** The current silent
   `PaperBroker` fallback is the defect that parked Upstox.
4. `connection_scope` written from the connection rather than the `kite:legacy` constant, with
   that constant retained as the documented value for pre-existing rows.

Out of scope, deferred with homes: account actors, leases and fencing (**phase 7**); Postgres as
shared authority (**ADR 0014** — defer, trigger is topology or contention); the `spot_symbol` /
`option_name` relocation (**R2**, its own slice, provable against Upstox's `SEGMENT|ISIN`);
market-data fan-in (**R3**, phase 7); credential encryption at rest (**phase 10**).

**What must not change:** paper/live book separation; `AUTHORITY_BY_SOURCE` and its
`(source, execution_mode)` shape; the `Broker` → `ExecutionVenue` layering and
`VENUE_FACING_METHODS`; canonical instrument identity; the exit lane's freedom from ARM gating.

**What would prove it:** a test in which the data role resolves to one connection and the
execution role to a different one, and the intent row records the execution connection's scope —
failing today because both come from one object. Plus a mutation proving the loud refusal red:
point a deployment at a data-only connection and assert it refuses rather than returning a
`PaperBroker`. Plus byte-identical behaviour for the existing Kite-only path — same
`connection_scope`, same orders — since that is the live-money path.

**Not a deployment.** Nothing here goes to the box; the live build is `6bb7e97` (2026-08-02) and
this branch is 177 commits ahead of it.
