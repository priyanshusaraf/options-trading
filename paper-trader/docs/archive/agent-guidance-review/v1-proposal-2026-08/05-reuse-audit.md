# 05 — Reuse-first audit for V1 commodity infrastructure

**Scope.** Only the commodity infrastructure V1 introduces: broker adapters, connection/auth
plumbing, canonical instrument identity, market-data fan-out, job boundaries, payments, and the
graph-rendering substrate. The differentiated core — IR, resolver, validator, hashing, research
gates, execution binding — is deliberately **out of scope**: the 2026-08-07 architecture review
concluded for G-1/G-2 that existing Strategy OS primitives beat anything outside, and that
conclusion stands for the language.

**Method.** Licences read from the file, never pattern-matched. The recorded reason: grepping
vectorbt's `LICENSE.md` for "Apache License" matched the *embedded* Apache text and reported it
as permissive — it is Apache **plus a Commons Clause rider** that is not open source.

**Verified in this session:** `~/dev/openalgo/LICENSE` first lines read → GNU **AGPL-3.0**;
`~/dev/openalgo/broker/` listing → **35 broker plugin directories**.
**Verified previously and re-quoted, not re-read here:** the licence ledger at
`~/dev/multiverse-of-ideas/_meta/LICENCES.md`, recorded 2026-08-02 by reading each file at a
pinned commit.

---

## 1. The matrix

| Candidate | For which V1 need | Licence | Class | Recommendation |
|---|---|---|---|---|
| **Strategy OS itself** | canonical instrument identity, connections, capability gating, job boundary | ours | **DIRECT REUSE** | See §2 — most of V1's "new" infrastructure already has a seam here |
| **xyflow (React Flow)** | the canvas | **MIT** (read at clone) | **DIRECT REUSE (dependency)** | The one legitimate buy-not-build, already the recorded position. Frontend surface — ChatGPT/Codex |
| **OpenAlgo** | 35 Indian broker adapters, symbol master, order/funds/margin normalisation, WebSocket fan-out | **AGPL-3.0** (read this session) | **REJECT for code · REFERENCE ONLY for behaviour** | See §3. Its §13 network clause triggers on *serving users* — fatal to a hosted product. Its architecture and failure modes are free to learn from; its files may never enter this tree |
| `openalgo.ta` (separate pip package) | indicator library | **UNVERIFIED** | **UNCLASSIFIED — do not use until read** | The teardown flagged this in 2026-08 and it is still unverified. Do not infer it from the platform licence. Also note: we do not need it — indicators are components |
| **nautilus_trader** | execution semantics, reset semantics, per-component warmup, one path for research and live | **LGPL-3.0** | **REFERENCE ONLY** | Read `reviews/nautilus-trader.md` §9B before any stateful-component work. Do not depend on it — it pulls in a second execution engine |
| **vectorbt** | vectorised indicator composition | Apache-2.0 **+ Commons Clause** | **REJECT** | Commons Clause forbids "fees for hosting" — exactly the hosted case. Already cited as the counter-example justifying C14 |
| **backtrader** | line/indicator abstraction | **GPL-3.0** | **REFERENCE ONLY**, currently unreviewed | Do not review speculatively. Trigger: a concrete V1.5 component-vocabulary question |
| **freqtrade** | deployment/rollback ergonomics, exchange abstraction | **GPL-3.0** | **REFERENCE ONLY**, currently unreviewed | Plausible trigger: V1.2's connection lifecycle and V1.8's deployment UX |
| **node-red** | subflows-as-nodes, package mechanics | Apache-2.0 | **REFERENCE ONLY** | Relevant to V1.4 reusable components — and to L4 when it starts |
| **blender** (geometry nodes) | node groups, promoted interfaces | GPL-2.0+ | **REFERENCE ONLY** | Already absorbed into F13 and the group model. Re-read for V1.4's collapse-to-component UX |
| **langflow**, **airflow**, **prefect** | job/worker patterns | MIT / Apache-2.0 | **REFERENCE ONLY** | Only if the job boundary is ever built. G-3 forbids building it now |
| **Broker vendor SDKs** (e.g. Upstox, Angel One official Python SDKs) | V1.3's second broker | **UNVERIFIED, per vendor** | **CANDIDATE — ADAPT-WRAP** | See §4. Most Indian broker SDKs are permissive, but *read each one* before depending on it |
| **Payment provider SDK** (Razorpay / Stripe) | V1 payments | **UNVERIFIED** | **DEFER** | Blocked upstream on the regulatory question, not on a licence |

---

## 2. DIRECT REUSE — inside Strategy OS

The reuse-first rule points at our own tree first, and for V1 that is the highest-yield
direction. Four V1 items have an existing seam that must be extended rather than replaced:

| V1 need | Existing seam | Rule |
|---|---|---|
| Data role vs execution role | `app/providers/base.py::MarketDataProvider` and `app/engine/broker_protocol.py::Broker` / `ExecutionVenue` — **already separate interfaces** | Do not merge them into a "connection interface". A connection *holds* capabilities; it is not a third protocol |
| Capability gating | `app/core/execution_binding.py` — authority recomputed at the point of use, refused against `GRANTS` | Capability resolution belongs in `app/core/`, never under `app/engine/`. C13 |
| Layered constraints | `app/core/scoped_config.py` — Platform → Deployment → Instrument, narrowest wins, one validation gate | Add scopes to `SCOPES`; add the narrowing rule. Do not build a second config system |
| Auth / ownership | `app/api/principal.py` — a `Principal` on every request, `ANONYMOUS_OWNER` rather than `None`, scopes modelled and unused | The seam was built for this. Populate it; do not replace it |
| Deterministic replay | `app/providers/replay.py` (WS-07-owned) | A second broker's historical path uses this, not its own |
| Symbol → frame conversion | `app/market_data/candles.py` — **THE** converter | A second provider must not fork it. This is the `candles.py` defect the invariant exists for |

**The single most important reuse rule for V1:** a second broker and a second data provider are
**new implementations of existing protocols**, not new subsystems. The moment an adapter grows
its own symbol table, its own charge model, its own frame converter or its own order path, the
"one of anything" invariant is broken and the second one is the one nobody tests.

---

## 3. OpenAlgo — REFERENCE ONLY, and what specifically to take

Copyright does not cover architecture. **Re-derive, never transcribe.** With that constraint,
these are the things worth learning, each already documented in
`docs/reports/2026-08-02-openalgo-competitive-teardown.md`:

**Take (as behaviour and as a specification of user expectation):**

- **The adapter directory contract.** Each broker as a fixed shape — auth, orders, data, funds,
  margin, GTT; a symbol-master loader; a streaming adapter with tick normalisation. That
  disciplined shape is why "add a broker" is a known task for them. Re-derive it as our
  capability protocol + conformance suite (V1.3).
- **A canonical symbol vocabulary above the adapters.** Their `SymToken` maps canonical symbol →
  `brsymbol` / `brexchange` / `token` / `lotsize` / `tick_size`. This is precisely V1.1, and the
  fact that they built it *before* the adapters is the sequencing lesson.
- **Two hard-won invariants for market-data fan-out**, both of which we will hit the moment
  there is more than one data consumer: the **SUB binds and every PUB connects** (fan-in, not
  fan-out — a publisher that binds lets a second process silently slide to another port while
  `subscribe` succeeds and *no ticks are ever delivered*); and **multi-device login must not
  tear down the shared feed**, gated on a *decrypted-plaintext* token comparison because
  ciphertext is non-deterministic.
- **The failure catalogue of an untyped control-flow builder**, which is our differentiator
  stated as their bug list: a typo resolving to `_UNRESOLVED` and stringifying through; a
  diamond firing an order node twice ("two orders from one crossover"); a gate firing on partial
  inputs; `MAX_NODE_VISITS = 500` as a runaway backstop rather than a semantics.

**Do not take:** any file, any adapter, any function. And do not take their *product* shape —
an options analytics suite, a scalping terminal, a charting terminal and 36 integrations are
their business, and chasing them is how this becomes a worse OpenAlgo instead of a different
category.

**The honest strategic read, recorded in the teardown and worth repeating in a V1 context:**
their 35 adapters are *a moat built of labour, not architecture*. V1 cannot out-labour it in
four weeks and should not try. Two correct brokers plus a conformance suite is a defensible
position; five plausible ones is not.

---

## 4. The one genuinely open reuse question in V1

**Broker vendor SDKs for V1.3.** Indian brokers publish official Python SDKs, and using one is
ADAPT-WRAP by nature: it belongs *behind* `ExecutionVenue`, never in front of it, exactly as
`kite_venue.py` is the only place `MIS`/`NRML`/GTT/SL-M are spelled today.

Before depending on any of them:

1. Read the licence file's first fifteen lines. Do not infer it.
2. Check whether it forces an event loop, a threading model or a global session — the
   `providers/factory.py` process-wide singleton is already a V1.2 problem and a second SDK
   with the same habit compounds it.
3. Confirm it does not require an intermediary service that would put a third party between the
   platform and the user's account.
4. Record the classification in `docs/engineering/reference/multiverse-index.md` or a successor
   index, so the next session does not re-derive it.

**Unresolved and deliberately not guessed here:** the licence of every specific vendor SDK, and
the licence of `openalgo.ta`. Neither was read in this session, and neither should be treated as
known until it is.
