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

### 2.4 The registry of mechanisms

`BINDING_MECHANISMS` names all six, as `table.column`, with a test asserting each still
exists. Adding a seventh is a deliberate edit with a test to justify it. This is the "no
second deployment model" rule enforced rather than asserted — and it fails loudly if a
column is renamed, so it cannot pass forever while describing a schema nobody has.

## 3. The smallest safe paper/shadow deployment architecture

Recorded now, gated at each step. **§3.1 is built (L1.3A, 2026-08-07). §3.2 onward is not,
and is the owner's decision.**

1. **A deployment may name a graph version, and still not execute it.** — **BUILT (L1.3A).**
   Implemented as `ir_shadow_deployments` (migration `0011`) plus
   `app/core/shadow_deployments.py`, rather than by overloading `deployments.strategy_key`
   as this ADR originally sketched. The reason for the change is §3.1a below.
### 3.1a Why L1.3A did not overload `deployments.strategy_key`

The original sketch was "set the deployment's key to `ir.<identifier>` and let the gate
refuse it". Building it exposed why that is wrong, and the correction is worth recording:

- **A `Deployment` row cannot hold the lineage.** Project, graph identifier, graph version,
  content address, evidence run, candidate, admission verdict and shadow lifecycle are
  eight facts with nowhere to live. Encoding them in the key is §2.1's forbidden move —
  one layer asserting another's fact — and it is how the whole defect class starts.
- **The two lifecycles are different.** A deployment is draft/active/paused/archived and
  *armed*. A shadow binding is staged/shadow-active/paused/retired and has no arm state,
  because there is nothing to arm. Sharing a state column would have made "armed" mean two
  things.
- **The refusal would have been a runtime one.** With a separate table the mode and
  authority columns are CHECK-constrained, so the database refuses to widen them at all.

This is **not** a second deployment model. `ir_shadow_deployments` has a foreign key to
`deployments` and describes an *observer attached to a book*, not a book. It creates no
orders, holds no capital, has no arm state, and appears in `BINDING_MECHANISMS` as
observation rather than as an answer to "what executes here" — the engine's authoritative
selection does not consult it.

### 3.1b What L1.3A verifies, and when

| checked | at stage | at activate | at every reload |
|---|---|---|---|
| graph version exists | yes | yes | yes |
| content address re-derived from the stored bytes | yes | yes | yes |
| instrument and interval are real | yes | — | — |
| research decision approves *this* project/graph/version | — | yes | no — recorded |
| warmup/history admission | — | yes | — |
| source/mode/authority is the one reviewed triple | — | yes | yes |

Evidence is verified once and **recorded**, not re-read on reload: the approval lineage
lives in the research plane's own database (hard invariant 5), and a control-loop boundary
is the wrong place for a cross-plane read. The graph address *is* re-derived on every
reload, because it is local, cheap, and the thing that can move underneath a live binding.

A binding that fails reload verification is **dropped and reported**
(`runner.shadow_deployment_problems`), never repaired. Silently rebinding to whatever bytes
are present now is the silent-substitution failure this project has closed in the registry,
in selection and in attribution; it does not get to reappear in observation.

2. **Paper authority is a source-and-mode pair, never a source alone.** — **NOT BUILT.
   Owner-gated.** L1.3A deliberately stops here. `shadow_deployments` has no mode
   parameter, no authority parameter, and the columns are CHECK-constrained, so granting
   paper authority requires a reviewed change in three independent places: the schema, the
   service, and `AUTHORITY_BY_SOURCE`. The smallest safe
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
authority. The wiring changed **which code answers "what runs here"**, not what the answer
is: the equivalence test covers the whole space of values `strategy_keys` can hold — unset,
the default, another registered strategy, and a stale key that no longer resolves — and in
every case the engine selects the same `Strategy` *object* it selected before.

### 4.1 Execution attribution — found here, closed in the next slice

**L1.2 canonicalised execution selection authority. The following slice canonicalises
execution attribution.**

The divergence this ADR originally recorded: selection went through the binding while the
intraday and futures entry paths still stamped `strategy_key=self.strategy_keys.get(key)` —
the raw assigned key — onto the position. For a stale assignment those disagree. The engine
trades the default (fail-safe, deliberate, unchanged) while the position and every trade row
descending from it claimed the key that *failed to resolve*. That is the misattribution shape
the registry docstring warns about, surviving in the one place nothing checked.

It is now closed. The binding that produced a signal is carried from the scan to the fill and
is what the money record is attributed to. The five identities stay separate — requested
assignment (`instrument_state.strategy_key`), executed strategy (`positions`/`trades`), graph
content identity, deployment identity, and authority — and no field was added or repurposed.

Three consequences worth stating:

- **`publish_signal` is the only door.** A signal state and the binding that produced it are
  written together, because `process_entries` opens from `self.state` and attributes from the
  binding. A state entry with no binding is a signal whose author is unknown; the entry paths
  refuse to open on one rather than guessing. Nineteen test call sites moved to this door —
  they had been constructing a state the engine cannot reach.
- **A refusal now withdraws the previous answer.** `self.state` survives a skipped scan, so
  refusing to evaluate an instrument without also dropping its last signal would let
  `process_entries` open on a signal produced while it was still authorised.
- **The identity is captured at the signal, not resolved at the fill.** Re-resolving would
  attribute the trade to whatever is configured by the time it fills, which is not what
  produced it.

### 4.1a A shared-state leak the slice uncovered

Ten attribution tests failed in the suite and passed in isolation, all reporting "no
intraday position opened". The cause was not attribution at all: five wiring test files pin
a session time with `r.provider.now = lambda: <fixed datetime>`, and `get_provider()` returns
a **process-wide singleton**. Sixteen call sites, none restoring — so the last writer froze
the clock at 09:20 for the rest of the run, and every later entry was refused by the 09:30
entry-window gate. The failure pointed at the innocent test.

Fixed in the rootdir `conftest.py` with an autouse fixture that restores the provider's
`now` after every test, rather than at the sixteen sites: the leak is the shape, not the
site. This is the same family as the cursor leak (`test_execution_attribution` pins and
restores `_cursor` for the same reason) and the third time this singleton has cost a
debugging session.

### 4.1b Historical rows: measured, not assumed

Existing rows *may* contain incorrect attribution — any row written while an instrument was
assigned a key the registry could not resolve. Measured on the production ledger
(2026-08-04, read-only):

```
sqlite3 'file:/opt/paper-trader/backend/paper_trader.db?mode=ro' \
  "SELECT COALESCE(strategy_key,'<NULL>'), COUNT(*), SUM(mode='live') FROM trades GROUP BY 1;"
<NULL>|22|22
expanding_z_v4|50|50
```

All 72 live trades carry either `NULL` — the documented "the engine default produced this"
encoding, coalesced to `trend_impulse_v3` by `analytics.py`, `models.py` and `sweep.py` — or a
registered key. **No production row carries an unregistered key, so the defect was latent and
never fired.** No migration and no repair tool: nothing is known to be wrong, and where a row
could be wrong the correct identity is *not* deterministically derivable (a key unregistered
today may have been registered when the row was written, and the reverse).

One benign discontinuity: from this slice forward an unassigned instrument records the
resolved key explicitly rather than `NULL`. Both read identically everywhere in the codebase,
so `NULL` now simply means "written before 2026-08-04". No schema change was required — the
model already keeps requested assignment and executed identity in different tables.

### 4.2 Remaining unconsumed mechanisms

- `strategy_lifecycle.deployed_watchlist_id` (#4) remains a record, not a resolver — by
  design; it is named in `BINDING_MECHANISMS` so it cannot quietly become one.
- `graph_artifacts.current_version` (#6) is consumed only by the shadow lane. It becomes a
  binding input at Stage 2, which is owner-gated.
- `deployments.strategy_key` (#1) now **has** a production caller for the first time, but
  only ever resolves to `None` today, because no production path writes it. A deployment
  that pins a strategy is exercised by tests, not by the running system.

## 5. Owner gates

Explicit approval is required before any change that lets IR output place, modify, cancel,
route or size orders; influence positions or accounting; alter exits, reconciliation or risk
controls; become authoritative in paper, shadow-to-order or live execution; or change
live-money behaviour. In code, all of those begin at one line: moving `SOURCE_IR_GRAPH` out
of `SHADOW` in `AUTHORITY_BY_SOURCE`.

## 6. L1.3B — the execution book

### 6.1 The inventory, before any semantics changed

Every read and write of money state, and whether the execution mode was explicit, implicit,
absent or inconsistent **before** this slice.

| Money state | Where | Mode/book status before |
|---|---|---|
| open positions (`positions`) | `PaperBroker.open_positions` / `position_for` — the chokepoint for ~35 call sites in `runner.py`, `routes.py`, `live_broker.py` | **absent.** `mode` was written on every row and read by no position query. The docstring stated the assumption out loud: "at most ONE open position per instrument across the whole system" |
| closed trades (`trades`) | `analytics.py` (11 queries), `runner._today_net_realized`, `_today_round_trips`, `routes.py:96`, `routes.py:958` | **inconsistent.** Exactly two of fourteen filtered: `recent_trades(mode=…)` (optional) and the bot-vs-you feed (`mode == 'live'`, correct). The daily-loss breaker and the round-trip cap counted both books |
| cash + realised P&L (`capital_state`) | `broker.capital()`, `analytics.capital_dict`/`account_pnl`, `session.py` seed + repair, `scripts/reconcile_ledger.py` | **unrepresentable.** One row, `id=1`, hardcoded at six sites, mutated in place |
| equity curve (`equity_snapshots`) | written once in `broker.snapshot()`, read by `analytics.equity_curve` | **absent.** No discriminator column at all |
| orders / intents / fills (`order_journal`) | `LiveBroker` only (write, `recover_journal`, orphan scan) + `ledger/detect.py` | **implicit but sound** — the paper broker has no order client and never writes a row |
| account totals (`daily_account_snapshot`) | `routes.py:96` | cross-book by nature: it records the *real Kite account*, not a book |
| ledger reconciliation / drift | `should_reanchor(is_live=…)`, `plan_reanchor` | **explicit at the decision, absent at the data** — it branched on `is_live` and then read the single shared `capital_state` |
| restart / open-position reconstruction | `broker.open_positions()` via the risk lane; `_repair_open_position_lot_sizes` | **absent** |
| square-off and exits | `runner.py` lines 1796/1825/1863/1880/1909/2047 — all `broker.open_positions()` | **absent** |
| risk exposure / deployable capital | `runner.deployable_cash`, `_open_unrealized`, `capital.deployable_capital` | **absent** |
| analytics + journal/review feeds | `analytics.py`, `ledger/` lane | intentionally cross-book, but nowhere stated |

### 6.2 Is `mode` sufficient?

**The value is right; its reach was not.** `mode ∈ {paper, live}` already names the book on
the two tables that matter most, and this slice adds no second abstraction — the book *is*
the execution mode, given one name and one resolver.

What `mode` alone could not represent, precisely: invariants 3 and 4 are not query
predicates. `capital_state.cash` and `capital_state.realized_pnl` are **aggregates mutated in
place on a single row**, so there is no `WHERE` clause to add — a paper fill would debit the
live ledger's cash no matter how many reads were filtered. `equity_snapshots` had no
discriminator to filter on either. Those two tables are why the slice includes a migration
rather than only call-site changes.

### 6.3 Final semantics per query

Isolated (the book predicate is now mandatory, not opt-in): position lookup, open positions,
exit and square-off scans, restart reconstruction, deployable capital, the daily-loss breaker,
the round-trip cap, `capital_dict`, `account_pnl`, the equity curve, re-anchor and ledger
drift.

Deliberately cross-book, and now documented as such rather than merely unfiltered:
`universe_resolver`'s "is this instrument in use" guard (removing an instrument with *any*
open position is the hazard, whichever book holds it), the reporting surfaces in
`analytics.py` and `/api/analytics/*`, the journal/review feeds, and
`daily_account_snapshot`, which describes the real account rather than a book.

### 6.4 The one tension, resolved deliberately

`open_positions` previously argued for unscoped reads: a read that *misses* a position is a
position nobody marks, ratchets or exits, and hard invariant 2 says not getting out is worse
than any other failure. Book scoping makes that miss possible.

It is still correct, because the paper broker cannot exit a live position — it holds no order
client. "Exiting" one would write a close into the ledger while the contract stayed open at
Zerodha, turning a visible orphan into an invisible one. So the scope is enforced and the
residual is made **loud** instead: `foreign_book_positions()` reports open rows belonging to
the other book, surfaced at startup and on `/api/health`.

### 6.5 Authority is now a (source, mode) pair

`GRANTS` moves from `(source, authority)` to `(source, execution_mode, authority)`.
`(ir_graph, paper)` **is not granted** and `(ir_graph, live)` **is not granted**; IR remains
refused in every mode. An unknown, missing or malformed mode resolves to `live` — the safe
direction — and never to paper, so a misconfigured process fails closed rather than inheriting
whatever paper would permit.

The managed-shadow object is untouched. `ir_shadow_deployments` is not widened into a paper
deployment table: it is an observer attached to a deployment, with no capital, no orders, no
arm state and no authority. Paper authority, if ever granted, flows through the canonical
Deployment/execution-binding path — the subject of the next design, not this slice.


## 7. L1.3C — IR paper authority

### 7.1 The grant, and what makes it safe to make

The owner granted `(ir_graph, paper, authoritative)` on 2026-08-07. `(ir_graph, live,
authoritative)` remains **absent** and is the next owner gate.

The grant was a one-line edit because L1.3B had already done the expensive part. Paper
authority is only meaningful if a paper fill cannot touch the live ledger, and §6 made that
structural: separate `capital_state` rows, a mandatory book predicate on every position
read, book-scoped risk controls. Without it, granting IR paper authority would have meant
granting it access to the same cash the live book spends.

### 7.2 The grant is necessary and deliberately not sufficient

This slice registers graph adapters, so `ir.<identifier>` now resolves in the one strategy
registry. If membership in `GRANTS` were the whole test, `POST /api/instruments/NIFTY/
strategy {ir.…}` would be an authoritative paper assignment — the exact hazard L1.2 closed.

So a graph-backed binding must pass two further checks at the point of use, both recomputed
rather than read off the binding:

1. **Origin.** Only `ORIGIN_PAPER_AUTHORITY` — a verified `ir_paper_deployments` record. An
   instrument row, a watchlist, the platform default and the fail-safe fallback all refuse.
2. **Exact content address.** The adapter's `version` *is* the graph's content address, so
   comparing it against the address the deployment approved binds authority to bytes rather
   than to a name.

`AUTHORITY_BY_SOURCE` is unchanged and still maps `ir_graph` to `SHADOW`. It answers a
different question — "may anyone with route access assign this source to an instrument" —
and the answer is still no. Collapsing the two maps is how the write-side gate would open.

### 7.3 Where authority lives, and why it is a third table

`ir_paper_deployments` (migration `0013`) binds eleven identities: project, deployment,
instrument, interval, graph identifier, graph version, content address, stable strategy key,
evidence lineage, paper mode, authoritative verdict, plus revision and lifecycle state.

**Not a wider CHECK on `ir_shadow_deployments`.** That object is an observer — no capital,
no orders, no arm state, no authority, and a service with no mode parameter. One row meaning
either "watched" or "traded" depending on a column is the collapse this ADR keeps refusing.

**Not a second deployment model.** The `Deployment` row still owns the account, universe,
parameters, allocation and arm. This attaches to one and adds only what a `Deployment`
cannot carry.

**Why the lifecycle is per-binding rather than `Deployment.status`.** The engine pins
`deployment_id = LEGACY_DEPLOYMENT_ID`; one deployment runs and every instrument in the book
shares its status, so pausing one graph by pausing that deployment would stop the whole
book. Same finding as §3.1a, same resolution.

### 7.4 Exact-version semantics

The content address is verified in **three independent places**: at activation, on every
reload (`active_bindings`), and at the authority gate against the adapter the registry
actually resolves. The first two protect the record; the last protects the trade.

Publishing a new graph version does nothing to an existing deployment — it names v1 and
keeps naming v1. Authority is re-granted by staging and activating a new binding, or it is
gone. A mismatch fails closed: the instrument stops trading rather than silently trading the
default, which is the posture a deployment pin already takes.

No client may supply `execution_mode`, `authority`, `runtime_source`, `strategy_key` or
`graph_content_address`. The mode and authority are the reviewed grant; the key and the
address are derived from the artefact the request names.

### 7.5 Rollback

`retire(..., restore_strategy_key=...)` is the only place authority is handed back, and the
argument is **required** — `None` means "there was no previous authority", a key means "put
this back". Neither is inferred. A target that cannot itself hold authority is refused, so
rolling back onto a graph key cannot re-grant through the door left shut. Retirement is
terminal, money records are never rewritten, and the API gives it its own route rather than
a shared transition shape that would let the target be omitted.

### 7.6 Two defects this slice found

**Option fills were unattributed.** All three entry paths resolved the canonical binding and
refused to open without it (L1.2b), but the options path never carried it onto the row —
every option `Position` was written with `strategy_key=NULL`. Latent, because production
runs `max_open_positions=0`; reachable the moment a graph became authoritative.
`strategy_version` was stamped on **no** path at all, which meant no money record could name
the graph version that produced it — precisely what exact-version authority is for. Both are
now carried through options, equity and futures, and onto the `Trade` row at close.

**`LiveBroker` would have raised `TypeError` on every real order.** Adding those parameters
updated `PaperBroker` and the `Broker` protocol — and `test_broker_protocol` compared the
protocol only against the *paper* implementation, so the live override's signature drifted
invisibly. `test_the_live_broker_accepts_everything_the_paper_broker_does` closes it. This is
the same shape as the unconsumed-mechanism defect class: a guard that checks the safe half.

### 7.7 What remains before live authority can even be designed

- Zero paper coverage in production today; this slice makes it possible, not present.
- The live grant would need its own `(ir_graph, live, authoritative)` entry, a table whose
  CHECK permits it, and a service able to write it — three reviewed changes, by design.
- Live authority additionally reaches `LiveBroker`, `KiteOrderClient` and the real order
  seam, none of which paper authority touches. That is a different risk surface and a
  separate design.
