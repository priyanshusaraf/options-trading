Reference: [section index](../architecture-extension-review-2026-08-07.md). Read with its scope; this is not a new assignment.

What already exists, and is worth knowing before anyone builds anything:

- **Position-scoped runtime state already has a durable home** — the live ATR ratchet persists
  `entry_atr`, `ratchet_hw`, `spot_stop`, `ratchet_last_bar_ts` on the `positions` row. This is an
  existing execution-state contract that merely needs documenting, not a new one.
- **Deployment-scoped lifecycle state already has one too** — `ir_paper_deployments` carries
  `state`, `revision`, verified addresses and evidence, and reloads deterministically after restart.
- **Impurity is already declarable at the node level** — `KernelSpec.purity` accepts
  `('account_state', 'broker_state', 'wall_clock')` [measured], and an impure node is excluded from
  the cache.

What does **not** exist is *node-scoped durable* state, and nothing needs it. The Nautilus review
(`reviews/nautilus-trader.md` §9B) recommends adopting reset semantics "even though nothing needs it
yet"; `KernelSpec`'s field set is closed and refuses unknown fields, so adding one later is local and
guarded. **Recommendation: do not add it until a component requires it.** Prefer the pure model;
when something genuinely cannot be expressed in it, that is the evidence that justifies the
contract, and not before.

### G-4 — `runtime.evaluate` is domain-blind.

**Urgency: SAFE TO DEFER.** Measured: `runtime.py` contains neither `domain` nor `instrument`, while
resolution propagates domains and hashes them into cache identity. This is not a defect — it is the
correct staging (the type system leads, the runtime follows) — but it should be recorded so nobody
reads "domains are enforced" as "multi-domain evaluation works". Already covered by WS-01 §5's
multi-timeframe item; this review adds the measurement.

### G-5 — `graph_artifacts.identifier` is a global primary key.

**Urgency: SAFE TO DEFER, with a free hedge.** Two tenants could not both own
`strategy.expanding_z_impulse`. Retrofitting a tenant scope would touch `graph_versions`'s composite
PK and `ir_paper_deployments.graph_identifier`. **The free hedge is a convention, not a schema
change:** identifiers are already dotted namespaces, so prefixing them per owner costs nothing now
and removes the collision entirely. Everything else needed for tenancy already has a seam —
`Principal` on every request (`api/principal.py`), `deployments.account_id`, and `scoped_config`'s
scope chain.

### G-6 — Narrower config scopes can widen a safety limit.

**Urgency: SAFE TO DEFER.** `scoped_config.SCOPES` is `(platform, deployment, instrument)`, narrowest
wins, and every scope validates through the same `OVERRIDABLE`/`BOUNDS` gate — which is the right
design and explicitly reuses rather than reinvents. But "narrowest wins" means a deployment could set
a *looser* `max_daily_loss` than the platform. Today this is unreachable: narrower scopes are empty
everywhere (`params_json` is `"{}"` on every row) and `resolve()` with no scope arguments is asserted
byte-identical to the old `effective()`. The rule to add — **a narrower scope may only tighten a
safety key** — belongs with the slice that first populates a narrower scope, not before.

### G-7 — The strategy language cannot see market data the platform already has.

**Urgency: SAFE TO DEFER.** `OptionQuote` carries `bid`, `ask`, `volume`, `oi`, and
`execution_policy.plan_order` reads top-of-book and depth to route orders. None of it reaches a
strategy: `FRAME_COLUMNS` is `date, open, high, low, close, volume`. Importantly this is **not** a
language limitation — Drill 1 proved a component taking `bid`/`ask`/`bid_qty`/`ask_qty` validates and
evaluates, and `IRGraphStrategy.required_inputs` is derived from the graph rather than from a fixed
OHLCV tuple. The gap is the frame contract and the acquisition path, and the `volume` addition of
2026-08-02 is the precedent for how to widen it. L3 owns this.

---

## E. Reuse matrix

Licences were verified by reading each file's first lines, per the standing method warning — never
by pattern match.

| Source | Feature of interest | Licence (verified) | Class | Adaptation | Invariant at risk | Recommendation |
|---|---|---|---|---|---|---|
| **nautilus_trader** | Reset semantics; per-component warmup; injected clock; one path for research and live | **LGPL-3.0** (`repos/nautilus_trader/LICENSE`, read) | **REFERENCE ONLY** | Re-derive from `reviews/nautilus-trader.md` §9 prose | Vendoring or deriving inherits obligations; linking alone is permitted but pulls a second execution engine in | Read §9B before any stateful-component work. Do not depend on it |
| **xyflow** (React Flow) | Graph rendering substrate | **MIT** (`repos/xyflow/LICENSE`, read) | **DIRECT REUSE** (as a dependency) | Standard npm dependency | None | The one legitimate buy-not-build. Already the recorded position |
| **openalgo** | Indian broker adapters, order lifecycle, symbol handling | **AGPL-3.0** (`~/dev/openalgo/README.md:389` → `License.md`) | **REJECT** for code; reference only for behaviour | None permissible | §13's network clause triggers on merely *serving* users — fatal to a hosted product | Teardown already exists at `docs/reports/2026-08-02-openalgo-competitive-teardown.md`. Never import |
| **vectorbt** | Vectorised indicator composition | **Apache-2.0 + Commons Clause** (`_meta/LICENCES.md`, method-verified) | **REJECT** | None | Commons Clause forbids "fees for hosting" — precisely the hosted Strategy OS case | Already cited as the *counter-example* justifying C14 at `app/ir/validate.py:472`. Correct use |
| **comfyui** | Custom nodes indistinguishable from built-ins; cache keys | **GPL-3.0** | **REFERENCE ONLY** | Prose only | Copyleft | Its lesson is already absorbed — C13 and content-addressed kernels are exactly this |
| **backtrader** | Line/indicator abstraction | **GPL-3.0** (read) | **REFERENCE ONLY** | Prose only; **currently unreviewed** | Copyleft | Do not review speculatively (index §5). Trigger: a concrete L1 question |
| **freqtrade** | Deployment/rollback ergonomics | **GPL-3.0** (read) | **REFERENCE ONLY** | Prose only; **currently unreviewed** | Copyleft | Plausible trigger: if the staged L1 rollout wants prior art |
| **node-red** | Subflows-as-nodes; package mechanics | Apache-2.0 | **REFERENCE ONLY** | Prose only | None (permissive) | Relevant to direction J when L4 starts, not before |
| **blender** (geometry nodes) | Node groups, exposed inputs | GPL-2.0+ | **REFERENCE ONLY** | Prose only | Copyleft | Already absorbed into F13 and the group model |

**Reuse conclusion — scoped (amendment A-4).** For the capabilities examined in *this* review, and
specifically for the **G-1 and G-2 corrections**, no external code should be adopted: existing
Strategy OS primitives (`Library`, `resolve()`, `authoring.component()`, the content-address scheme)
are better suited than anything outside, and the two areas where reuse would be most tempting —
broker adapters (OpenAlgo) and execution semantics (Nautilus) — carry the most hostile licences for
a hosted product.

**This is a conclusion about these findings, not a project-wide rule.** Do not quote it as one. The
standing project policy is unchanged and remains:

> Before building commodity infrastructure, inspect (1) Strategy OS itself, (2) OpenAlgo,
> (3) `~/dev/multiverse-of-ideas` and other relevant local clones, (4) suitable external
> open-source implementations. Classify each candidate **DIRECT REUSE / ADAPT/WRAP /
> REFERENCE ONLY / REJECT**. Licence compatibility is mandatory. Differentiated Strategy OS
> architecture must not be distorted merely to reuse outside code.

That policy applies in full to the commodity infrastructure this review defers — the job/worker
boundary (G-3), auth and tenancy (G-5), typed data sources and market calendars (L3), packaging and
signing (L4). Several of those are exactly the areas where buying beats building, and the answer
there is expected to differ from the answer here.

The library's existing rule ("only `reviews/` prose may cross") stands, and this audit found nothing
to change about it. Independently re-verified: the tree contains no reference source code, only the
two prose citations at `app/ir/validate.py:472` and `app/ir/schema.py:44`.

The one genuine reuse recommendation in scope is the one already recorded: **xyflow, MIT, as a
dependency**.

---
