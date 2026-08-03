# ADR 0012: Execution-state ownership across graphs, evidence, candidates and deployments

- **Status:** **ACCEPTED for the non-authoritative half (2026-08-04).** The binding contract
  and the authority gate are implemented; the engine's own resolution is unchanged. Every
  transition that would let IR output reach an order remains **owner-gated** and unbuilt.
- **Date:** 2026-08-04
- **Owners:** WS-02 execution, WS-01 Component IR, WS-03 research plane
- **Depends on:** ADR 0011 (staged IR adoption; Stage 1 engineering-closed 2026-08-04),
  RFC 0001, the Phase B deployment object
- **Reference prior art:** `~/dev/multiverse-of-ideas/reviews/nautilus-trader.md` §9D (one
  execution path, explicitly staged) — advisory. No reference project's deployment model is
  adopted; the standing rule is one of anything.

---

## 1. The problem, stated as it actually is

**Six mechanisms already express some part of "what strategy runs where."** They were built
at different times, each defensible alone:

| # | Mechanism | Identity it carries | Failure posture |
|---|---|---|---|
| 1 | `deployments.strategy_key` (+ `strategy_version`) | `(key, version)` | fail-closed (`resolve_deployment_strategy`) |
| 2 | `instrument_state.strategy_key` | key only | fail-safe: unknown → default |
| 3 | `watchlists.strategy_key` + memberships | key only | via #2 |
| 4 | `strategy_lifecycle.deployed_watchlist_id` | key only | none — it is a record, not a resolver |
| 5 | `generated_strategies.key` | key PK; version recorded but overwritten in place | fail-safe on rebuild failure |
| 6 | `graph_artifacts.current_version` → `graph_versions` | `(identifier, version)` + content address | append-only, immutable |

**The finding that organises this ADR:** `resolve_deployment_strategy` has tests and **no
production caller.** Verified 2026-08-04 —
`grep -rn "resolve_deployment_strategy" --include=*.py` outside its own module returns only
`tests/test_deployments.py`. The engine resolves per instrument from #2/#3. So the object
the architecture calls "THE primary execution object" **does not decide what executes.**

That is this codebase's defining defect (a correct mechanism wired to nothing) sitting under
the deployment model itself. Adding a seventh mechanism for IR-backed strategies would make
it worse and would breach the standing "no second deployment model" rule.

## 2. Decision

**One binding contract, one authority gate, no new execution path.**

`app/core/execution_binding.py` answers, for one instrument under one deployment: which
strategy key, at which content version, from which source, decided by which layer, with what
reason — and whether that source is allowed to execute at all.

It is a **description with a gate attached**, not a new resolver. The engine's own path is
untouched, and an equivalence test pins that the contract's answer and `get_strategy`'s
answer are the same object for every assignment the engine can hold. A description that
drifts from what it describes is worse than none, so that test is the contract's spine.

### 2.1 Ownership — who owns which fact

| Layer | Owns | Does **not** own |
|---|---|---|
| **Immutable graph versions** (`graph_versions`) | the *logic*, content-addressed and append-only | whether it runs, where, or with whose capital |
| **Approved research evidence** (research plane) | whether the logic is *worth* running | whether it *may* run — evidence is an input to a decision, never the decision |
| **Deployment candidates** (`strategy_lifecycle`, promotions) | the *proposal*, and its human-gated review state | execution; the deploy bridge writes declarative config only |
| **Deployments** (`deployments`) | *which strategy, at which version, on which account, over which universe, with what allocation, armed or not* | the logic itself, and the authority of its source |
| **Legacy authoritative strategy** (per-instrument / watchlist) | what actually executes **today** | nothing else; it is the incumbent, not the model |
| **The IR shadow lane** | *observation* — evaluate, compare, classify, record | everything else. It reaches no order seam, by four proofs |

The rule that makes this a model rather than a list: **logic, worth, proposal, placement and
authority are five separate facts, and no layer may assert one it does not own.** Every
defect this project has recorded in the area comes from one layer asserting another's fact —
a graph key that resolved to the default asserted *placement* over *logic*; a generated row
overwritten in place asserted *logic* over *identity*.

### 2.2 The authority gate

`AUTHORITY_BY_SOURCE` maps a source of logic to whether it may execute:

```
handwritten -> authoritative
generated   -> authoritative
ir_graph    -> shadow          # ADR 0011 Stage 1: observed, recorded, never executed
```

Resolving a binding whose source is not authoritative raises `AuthorityNotGranted` — its own
type, because "this logic may not trade" and "this logic does not exist" call for different
actions.

**This is the gate's whole point.** Once Stage 2 registers a graph-backed strategy, nothing
else in the system would stop an ordinary `POST /api/instruments/NIFTY/strategy` from making
it authoritative: the registry resolves it and the engine trades it. With the gate, the path
to live IR execution runs through a reviewed edit to one table in one module — which is
exactly the Stage 2/3 decision ADR 0011 reserves to the owner — rather than through a config
row nobody reviews.

`resolve_shadow_binding` deliberately bypasses the gate: refusing authority must not refuse
observation, or the gate would undo the shadow lane it exists to protect.

### 2.3 Failure posture, which differs by layer on purpose

- **A deployment pin that will not resolve raises.** A deployment is a promise about which
  strategy is trading; substituting the default makes the promise false while the trade rows
  still name the customer's strategy.
- **A per-instrument assignment that will not resolve falls back — and says so.** One stale
  config row must not stop the book trading. The binding reports `origin=fallback` with the
  key that was asked for, so the substitution is visible instead of the default being
  presented as though it had been chosen.
- **A graph-backed key never falls back**, at either layer.

### 2.4 The registry of mechanisms

`BINDING_MECHANISMS` names all six, as `table.column`, with a test asserting each still
exists. Adding a seventh is a deliberate edit with a test to justify it. This is the "no
second deployment model" rule enforced rather than asserted — and it fails loudly if a
column is renamed, so it cannot pass forever while describing a schema nobody has.

## 3. The smallest safe paper/shadow deployment architecture

Recorded now, built later, gated at each step. **No part of this is implemented by this ADR.**

1. **A deployment may name a graph version, and still not execute it.**
   `deployments.strategy_key = "ir.<identifier>"` plus `strategy_version = <content
   address>`. Resolution passes through the same gate, so today it raises. Nothing new is
   stored, and nothing new is needed: `(key, version)` already is the execution artefact.
2. **Paper authority is a source-and-mode pair, never a source alone.** The smallest safe
   grant is not "`ir_graph` is authoritative" but "`ir_graph` is authoritative **when
   `PT_EXECUTION=paper`**" — i.e. the gate consults execution mode, and fails closed when it
   cannot determine it. `SafePaperKite` and `PaperBroker` already provide the containment;
   the gate provides the selection, and it must fail closed rather than open.
3. **One deployment, one instrument, one graph version.** Rollback is reassigning the
   deployment's key — no deploy, no restart, matching the existing per-instrument path.
4. **Every transition is version-bound.** A graph edit mints a new version, so it cannot
   inherit the previous version's authority. That falls out of `(key, version)` identity and
   requires no new mechanism.
5. **Observability before authority.** A deployment running a graph in paper must publish
   the same evidence the shadow lane does — agreement, classifications, cost — under the
   same contract, or the promotion has no basis.

**Not in this design, deliberately:** a second ledger, a second broker, a second candidate
lifecycle, a parallel "IR engine", or any code path that duplicates order lifecycle,
accounting, reconciliation, exits, kill controls or rollback. Every one of those already
exists once and stays that way. The engine remains authoritative until a later,
explicitly-approved authority transition.

## 4. What this ADR does not change

The order lifecycle, accounting, reconciliation, exits, kill controls, rollback and
deployment authority are untouched. The hand-written strategy remains the sole execution
authority. `resolve_binding` is not called by the engine — wiring the engine to it is the
next slice and is a behaviour-preserving refactor with its own equivalence proof, not a
change of authority.

## 5. Owner gates

Explicit approval is required before any change that lets IR output place, modify, cancel,
route or size orders; influence positions or accounting; alter exits, reconciliation or risk
controls; become authoritative in paper, shadow-to-order or live execution; or change
live-money behaviour. In code, all of those begin at one line: moving `SOURCE_IR_GRAPH` out
of `SHADOW` in `AUTHORITY_BY_SOURCE`.
