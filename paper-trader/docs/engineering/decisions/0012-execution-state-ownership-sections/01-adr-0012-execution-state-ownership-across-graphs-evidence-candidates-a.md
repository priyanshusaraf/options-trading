Reference: [section index](../0012-execution-state-ownership.md). Read with its scope; this is not a new assignment.

# ADR 0012: Execution-state ownership across graphs, evidence, candidates and deployments

- **Status:** **ACCEPTED and WIRED (2026-08-04).** The binding contract and the authority
  gate are implemented, **and the engine now consults them** — every strategy-selection
  decision in `EngineRunner` passes through `execution_binding.bind`, proven equivalent to
  the resolution it replaced. Every transition that would let IR output reach an order
  remains **owner-gated** and unbuilt.
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

It began as a **description with a gate attached**. As of the wiring slice it is the
selection path itself: `EngineRunner` holds no other. An equivalence test pins that the
contract's answer and `get_strategy`'s answer are the same object for every assignment the
engine can hold, which is what made replacing the call site acceptable in a live-money
engine. A description that drifts from what it describes is worse than none, so that test
is still the contract's spine.

### 2.0 The wiring, and why the contract had to be split in two

Shipping the contract without a caller reproduced the defect it was written to fix: a
correct mechanism wired to nothing. Consulting it, however, could not mean two database
reads per instrument per ~2.5 s tick — that would have made "route the engine through the
contract" mean "slow the engine down", and the wiring would have been rejected for a reason
unrelated to whether the contract is right.

So the contract is split along **decision vs lookup**, and there is still exactly one
decision:

| | what it is | who calls it |
|---|---|---|
| `bind(...)` | the decision — precedence, resolution, authority — over values already in hand | `EngineRunner._binding_for`, from its in-memory config |
| `resolve_binding(session, ...)` | the same decision, with the deployment pin and the instrument assignment read from the database | callers holding a session and no cached config |

`resolve_binding` is now `bind` plus two reads, and a test pins that both produce an equal
binding for the same inputs. Two entry points that could disagree would be two resolvers
again.

**Precedence, final form:** deployment pin → per-instrument assignment (including the active
watchlist overlay) → platform default. Narrowest that *spoke*, not narrowest that exists.

**The engine also consults the deployment pin now** — the first time mechanism #1 has had a
production caller. It is resolved once at boot, not per tick. This is behaviour-preserving
by contract and by measurement: the legacy deployment has `strategy_key = NULL`, no
production path writes it (`create_deployment` is the only writer and the legacy row is
seeded by `ensure_legacy_deployment`), so the pin is `None` and resolution falls through to
the instrument exactly as before. It is deliberately **not** wrapped in a `try`: swallowing
an unresolvable pin would resolve a contradiction in favour of the weaker claim.

### 2.0b Two paths that must not converge, and one that must

- **A refusal is not a substitution.** When the gate refuses an instrument, the scan skips
  that instrument and logs (rate-limited). It does not fall back to the default — that is
  the silent-substitution class the fail-closed registry split exists to prevent — and it
  does not abort the scan, because one refused instrument has no claim over the rest of the
  book and invariant 2 forbids blocking exits.
- **Authority is re-checked where it is used.** `strategy_for_execution` recomputes the
  source from the key and requires the `(source, authority)` pair to be in `GRANTS`. A
  binding is a plain dataclass; without this, any resolver — drifted, stubbed, or written by
  a future caller — could grant execution by assigning a field.
- **Every writer of an engine assignment passes the same gate.** `set_strategy`,
  `universe_resolver.add_instrument`, `watchlists.create_watchlist` and `deploy_bridge.deploy`
  all call `assert_may_execute`. The read side already refuses; these make the refusal happen
  once, when somebody asks, instead of once per scan for the life of the row. The API surfaces
  it as **409 with the reason**, by catching `AuthorityNotGranted` — no route tests for a
  namespace itself.

### 2.0c RFC 0001 C13, and why this does not violate it

C13 forbids executor paths branching on where a component came from. The authority gate
*does* branch on source, so the boundary matters: it lives in `app/core/`, outside the
executor perimeter (`engine/`, `backtest/`, `strategy/`), and the engine consumes only the
verdict — it asks "may this execute", never "where did this come from". The C13 conformance
test caught the first draft of the wiring on the vocabulary alone, which is the guard working
as designed.

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
