# OpenAlgo — Competitive Architecture Teardown

**Date:** 2026-08-02
**Subject:** `~/dev/openalgo` (marketcalls/openalgo), running locally at `http://127.0.0.1:5000/`
**Purpose:** not a code review. A competitor teardown whose only output is *what we build next.*
**Method:** source read of the backend (`app.py`, `services/`, `blueprints/`, `database/`, `portfolio/`,
`sandbox/`, `broker/`), the React frontend (`frontend/src/`), and the project's own `CLAUDE.md`
and `okf/` knowledge base. Every claim below cites the file it came from.

---

## 0. The legal constraint, stated first because it shapes everything

OpenAlgo is **AGPL-3.0** (`License.md:1`). Not MIT, not Apache.

- **Copying code** into our platform makes our platform AGPL — and because AGPL's §13 network
  clause triggers on *serving users over a network*, a hosted Strategy OS would have to publish
  its complete corresponding source. That kills the marketplace and the SaaS path.
- **Copying ideas, workflows, architecture, and UX patterns is unrestricted.** Copyright does not
  cover architecture. This teardown therefore treats OpenAlgo as a *specification of what users
  expect* and a *catalogue of solved problems*, never as a source tree to lift from.
- One practical exception: `openalgo.ta` is published as a separate pip package (`pyproject.toml`
  pins it; `services/indicator_service.py` imports `from openalgo import ta`). If that package
  carries a permissive licence, it is consumable as a dependency. **Verify the package licence
  before any dependency decision — do not infer it from the platform's licence.** (Unverified as
  of this document; I read the platform licence, not the package's.)

**Rule for everything below:** re-derive, never transcribe.

---

## 1. What OpenAlgo actually is

Not a strategy platform. **A broker abstraction layer with products bolted on.** Its own
`CLAUDE.md` is candid about this — "several products in one self-hosted instance, all sharing a
single broker session and WebSocket feed":

| Surface | Route | What it is |
|---|---|---|
| Unified Broker API | `/api/v1/` | 36-broker normalized REST — the actual product |
| Python Strategy Host | `/python` | in-browser editor, scripts run as isolated subprocesses |
| Flow (no-code builder) | `/flow` | node graph → order execution |
| Options Suite | `/tools` | 15 analytical tools (chain, greeks, GEX, vol surface, max pain…) |
| Charting Terminal | `/trading` | chart trading via `openalgo-charts` |
| Scalping Terminal | `/scalping` | keyboard-driven index-options scalping |
| Portfolio Backtester | React page | long-only weights backtester (unrelated to Flow) |
| MCP servers | stdio + `/mcp` | AI-agent-addressable trading surface |

The strategic read: OpenAlgo monetizes *connectivity*, and everything else is a demand generator
for it. That is a different business from ours. **We are not competing with OpenAlgo. We are
competing with the thing OpenAlgo's users will want after Flow disappoints them.**

### Deployment and runtime model

- Flask + React 19, gunicorn `--worker-class eventlet -w 1` in production.
- **Single worker is mandatory** — Flask-SocketIO state is in-process and unshareable.
- **No `asyncio` anywhere.** Eventlet monkey-patches the stdlib; `async`/`await` breaks in
  production but works on the dev server. Their own `CLAUDE.md` calls this "the single most
  common way a change passes locally and fails on deploy."
- Six isolated SQLite databases (`openalgo.db`, `logs.db`, `latency.db`, `health.db`,
  `sandbox.db`) plus `historify.duckdb`. `NullPool` always, never `StaticPool`.
- Ports: app 5000, WebSocket proxy 8765, ZeroMQ 5555.

---

## 2. Subsystem-by-subsystem architecture review

### 2.1 Broker integration layer — *their crown jewel*

`broker/` holds **36 broker plugins** (aliceblue → zerodha), each with an identical four-directory
contract:

```
broker/<name>/
  api/         auth_api, order_api, data, funds, margin_api, gtt_api
  mapping/     transform_data, order_data, margin_data, gtt_data   (broker ⇄ OpenAlgo)
  database/    master_contract_db                                  (symbol universe loader)
  streaming/   <name>_websocket, <name>_adapter, <name>_mapping     (tick normalization)
```

Above it sits a normalized vocabulary: a canonical symbol format
(`NIFTY28MAR2420800CE`, `BANKNIFTY24APR24FUT`), a `SymToken` table mapping OpenAlgo symbol →
`brsymbol`/`brexchange`/`token`/`lotsize`/`tick_size`, and fixed order constants
(`CNC`/`NRML`/`MIS`, `MARKET`/`LIMIT`/`SL`/`SL-M`).

**Assessment: genuinely excellent, and the one place where their lead is unbridgeable by cleverness.**
36 broker integrations is 36 units of grinding, undifferentiated, high-maintenance work. We have
one (Kite). This is a *moat built of labour*, not architecture.

The architecture is only good, not great: plugin discovery happens at startup only, gated by a
`VALID_BROKERS` env var, with no runtime registration and no version negotiation. But the
directory contract is disciplined enough that adding a broker is a known-shape task — hence a
`broker-integration` skill in their `.claude/skills/`.

### 2.2 Market-data pipeline — three layers, one strong idea

1. **Broker adapters** (`broker/*/streaming/`) connect proprietary feeds, normalize ticks. Capacity
   `MAX_SYMBOLS_PER_WEBSOCKET (1000) × MAX_WEBSOCKET_CONNECTIONS (3)` = 3000 symbols/broker.
2. **ZeroMQ bus** (port 5555) decouples feed from delivery so the adapter never blocks on a slow
   client.
3. **WebSocket proxy** (`websocket_proxy/server.py`, port 8765) owns client connections,
   subscriptions and per-symbol throttling.

The load-bearing invariant, stated in their `CLAUDE.md` and worth internalizing: **the SUB binds
and every PUB connects.** Fan-in, not fan-out. Many publishers across processes share one fixed
port with no contention. If a publisher binds instead, two processes race for the port, the loser
silently slides to the next port while the SUB stays put — and `subscribe` succeeds while *no
ticks are ever delivered*. Works on the single-process dev server; broken only under eventlet.

A second good invariant: **multi-device login must not tear down the shared feed.** A second
device resuming a session re-persists the same token, and `upsert_auth` is also what publishes
`CACHE_INVALIDATE_ALL`. They gate the teardown on a *decrypted-plaintext* token comparison —
Fernet ciphertext is non-deterministic, so comparing encrypted blobs would falsely fire every time.

**Assessment: the strongest piece of engineering in the repo.** Both invariants are failure modes
we will hit the moment we have more than one data consumer, and both are documented with the
symptom, not just the rule.

### 2.3 Flow — the no-code builder (the reason we are here)

**Frontend.** React 19 + `@xyflow/react` v12 + Zustand + TanStack Query + Radix/shadcn + Tailwind 4.
~60 node components under `frontend/src/components/flow/nodes/`, a drag-and-drop `NodePalette`
(624 lines), a `ConfigPanel` (3,840 lines), an `ExecutionLogPanel`, an `InsertableEdge` (drop a
node onto a wire), keyboard shortcuts, minimap, JSON import/export.

**Backend.** `services/flow_executor_service.py` (3,137 lines), `flow_workflow_validator.py` (875),
`flow_scheduler_service.py` (321, APScheduler with a SQLAlchemy jobstore), `flow_price_monitor_service.py`
(491), `flow_order_update_monitor_service.py` (345), `database/flow_db.py` (500).

**Node taxonomy** (from `flow_workflow_validator.VALID_NODE_TYPES`, 60 types):

- *Triggers:* `start` (schedule), `webhookTrigger`, `priceAlert`, `orderUpdateTrigger`
- *Data:* `getQuote`, `getDepth`, `history`, `multiQuotes`, `optionChain`, `syntheticFuture`,
  `orderBook`, `tradeBook`, `positionBook`, `holdings`, `funds`, `margin`
- *Compute:* `indicator`, `mathExpression`, `barOffset`, `priorPeriodOhlc`, `variable`
- *Conditions & logic:* `priceCondition`, `varCondition`, `positionCheck`, `fundCheck`,
  `timeWindow`, `timeCondition`, `andGate`, `orGate`, `notGate`
- *Actions:* `placeOrder`, `smartOrder`, `optionsOrder`, `optionsMultiOrder`, `basketOrder`,
  `splitOrder`, `modifyOrder`, `cancelOrder`, `cancelAllOrders`, `closePositions`
- *Streaming:* `subscribeLtp`, `subscribeQuote`, `subscribeDepth`, `unsubscribe`
- *Side effects:* `log`, `httpRequest`, `telegramAlert`, `whatsappAlert`, `delay`, `waitUntil`
- *Cosmetic:* `group`

#### The central architectural fact: **this is a control-flow graph, not a dataflow graph**

This single decision explains almost every strength and every ceiling of Flow, so it deserves
precision.

Edges carry **control**, not data. Node outputs are written into a **flat, global,
string-keyed variable bag**:

```python
class WorkflowContext:
    def __init__(self):
        self.variables: dict[str, Any] = {}      # flow_executor_service.py:71
        self.condition_results: dict[str, bool] = {}
```

A node declares an `outputVariable` name (a free-text string the user types), and downstream nodes
reference it by **string interpolation** — `{{rsi.value}}`, `{{quote.ltp}}` — resolved at runtime
by a regex path walker (`_walk_path`, `resolve_raw`, `interpolate`).

Execution is a **recursive depth-first walk with side effects**:

```python
def execute_node_chain(node_id, nodes, edge_map, incoming_edge_map, executor, context,
                       visited_count, depth=0):
    if depth > MAX_NODE_DEPTH:          # 100
    if total_visits >= MAX_NODE_VISITS: # 500
    ...
    if   node_type == "start":     ...
    elif node_type == "placeOrder": ...
    # ~130 more elif branches
    for edge in edges_to_follow:
        execute_node_chain(edge["target"], ...)   # recurse
```

**What this costs them, concretely:**

1. **No types.** A socket is a socket. Nothing prevents wiring an order book into a math
   expression. The only validation is *structural* — `flow_workflow_validator.py` checks shape,
   known node types, edge endpoints, the one-trigger rule — and its own docstring concedes it
   "validates structure, not trading semantics."
2. **A typo is a silent runtime failure.** `{{rsi.vaule}}` resolves to `_UNRESOLVED` and
   stringifies through. They *patched the worst case* — a condition node that could not evaluate
   takes **neither** branch rather than the false branch, with an excellent comment explaining
   that on `RSI < 70 → BUY else SELL`, a typo'd variable would otherwise "silently fire the SELL."
   That is a good fix to a problem a typed graph would not have.
3. **No memoization — a node reachable by two paths executes twice.** They discovered this and
   patched *only the logic gates*, via a re-entrancy guard on `condition_results` plus a
   "wait for all inputs" check. The comment is the confession:

   > "the gate fired on partial inputs ('A AND B' firing on A alone) AND fired again for each
   > remaining input, duplicating whatever is downstream — **two orders from one crossover.**"

   The patch covers gates. It does not cover `placeOrder`. A diamond in the graph with an order
   node at the join still fires twice. `MAX_NODE_VISITS = 500` is a runaway backstop, not a
   semantics.
4. **The gate-waiting hack is a scheduler simulated by re-entrancy.** In a topologically scheduled
   dataflow engine, "wait until all inputs are ready" is the scheduler's *definition*, not a
   special case for three node types.
5. **No composition.** The `group` node is a **colored resizable rectangle** (`GroupNode.tsx` —
   `NodeResizer` + border colour + a label). It is not an encapsulated subgraph with an
   interface. There are no node groups, no subgraphs, no reusable composites, no library.
   A user who builds a good "ATM straddle with SL" cannot package it.
6. **Blocking sleeps inside the graph.** `delay` and `waitUntil` block the walk, holding the
   per-workflow lock and a worker slot under `-w 1` eventlet.
7. **Whole-graph locking.** `get_workflow_lock(workflow_id)` — a concurrent trigger is *rejected*
   ("Workflow is already running"), not queued. No partial re-execution, no incremental
   evaluation, no cross-run caching of node outputs.

#### The second central fact: **Flow has no versioning and no backtest**

```python
class FlowWorkflow(Base):                       # database/flow_db.py:78
    nodes = Column(JSON, default=list)
    edges = Column(JSON, default=list)
    updated_at = Column(DateTime, onupdate=func.now())
```

The graph is a **mutable JSON blob updated in place.** `FlowWorkflowExecution` references
`workflow_id`, not a graph version. Therefore:

- **You cannot answer "what logic placed this order" after any edit.** Edit the graph, and every
  past execution now points at logic that no longer exists.
- No history, no diff, no rollback, no branching, no A/B, no lineage.
- Nothing to attach an experiment to, because there is no immutable identity to attach it *to*.

This is precisely the defect our own audit named C4 and fixed with content-addressed identity
(`app/strategy/identity.py`): *"a strategy's identity today is a mutable string… redeploying an
edited strategy under the same key silently rewrites history — every past trade attributed to
`gen_x` now points at different logic, and no backtest, attribution report or performance claim
can be falsified afterwards."*

**And you cannot backtest a Flow. At all.** I looked specifically:

- `okf/skills/backtesting.md` is a *link to an external doc* about a VectorBT agent skill.
- `examples/python/backtesting_vectorbt.py` is a standalone example script.
- `portfolio/` + `PortfolioBacktester.tsx` is a **different product**: a long-only,
  daily-bar, weights-and-rebalancing investor backtester. It shares no code, no data model and no
  concept with Flow.

So a Flow strategy's only validation path is **forward time in sandbox or live.** That is the
single largest gap in the product, and the largest opening for us.

#### What Flow gets right (and we should take)

- **One validation chokepoint.** `validate_workflow(strict=True)` is called inside
  `execute_workflow`, *before* the execution record is created — so schedules, webhooks, price
  alerts, order-update triggers and "Run Now" are all covered by one check, and a rejected run is
  never logged as one that started. The comment says why: "Guarding the HTTP routes alone left the
  background triggers unchecked."
- **Multi-modal triggering as first-class node types**, not settings: schedule (APScheduler with a
  persistent SQLAlchemy jobstore, `coalesce=True`, `max_instances=1`, `misfire_grace_time=60`),
  webhook (per-workflow token + secret, payload-or-URL auth), price monitor, order-update monitor.
- **Errored conditions take neither branch.** Ship this reasoning verbatim into our kernel.
- **Frontend/backend node-list parity enforced by test** (`VALID_NODE_TYPES` ↔ `nodes/index.ts`).
  Treating the symptom, but at least treating it.
- **JSON import/export** of an entire graph — shareable strategies without a marketplace.
- **`InsertableEdge`** — drop a node directly onto a wire and it splices in. Small, delightful.
- **Single-flight + short-TTL history cache with shared failure** (`indicator_service.py`).
  Under broker rate limits (Dhan 1 req/s on quotes, Zerodha 1 req/s on some paths, a process-wide
  ~350ms gate) a graph asking for RSI + SMA + ATR on one symbol would otherwise issue four
  identical history calls per run. Concurrent misses collapse into one call and **every waiter
  receives the failure too** — because errors are deliberately not cached, so a naive
  lock-and-retry would stampede exactly when the broker is already throttling.

### 2.4 Python Strategy Host

`blueprints/python_strategy.py` — in-browser CodeMirror editor; each strategy runs as a **separate
OS subprocess** with `RLIMIT_AS` (memory), `RLIMIT_CPU`, `RLIMIT_NOFILE (256)`, `RLIMIT_NPROC (256)`
via `preexec_fn`, stdout redirected to a log file (never `PIPE`, to avoid FD/deadlock issues),
scheduled on IST times, atomic temp-file-then-rename writes.

**Assessment: process isolation is the *right* answer for arbitrary user code and a different
answer from ours.** We use an AST allow-list plus a no-builtins `exec` — a *static* boundary that
proves the code cannot import, do I/O, or call anything but vetted blocks. Theirs is a *dynamic*
boundary that lets users write anything and contains the blast radius with rlimits.

Ours is stronger for *generated* strategies (provably safe, auditable, cheap). Theirs is stronger
for *user-authored* strategies (no expressiveness ceiling). **A Strategy OS needs both tiers, and
we currently have only one.** See roadmap A3.

### 2.5 Sandbox engine

`sandbox/` — 7,110 lines: `order_manager`, `position_manager`, `execution_engine`,
`websocket_execution_engine`, `fund_manager`, `holdings_manager`, `squareoff_manager`,
`catch_up_processor`, with dedicated threads. ₹1 crore notional capital, exchange-aligned auto
square-off, **fully isolated in its own `sandbox.db`**, shared by every surface (Flow, Python
host, API, scalping).

**Assessment: the "isolation by separate database" pattern is right and matches our research-plane
instinct.** But note what it *is*: a forward-time paper simulator, not a backtester. It answers
"what would this have done since I turned it on", never "what would this have done in 2023."

### 2.6 Portfolio backtester — the best-reasoned code in the repo

`portfolio/` (2,949 lines): `engine`, `costs`, `data`, `rebalance`, `walkforward`, `attribution`,
`crisis`, `health`, `insights`, `compare`, `analytics`, `grouping`, `holdings`.

This is a **drift-and-reset weights simulation**, deliberately not order-level. Held weights drift
with prices and snap to target on rebalance dates. What makes it good:

- **Costs modelled, not assumed away.** Turnover and cost drag are first-class outputs, computed
  against a cost-free twin that rebalances on the same sessions "so the difference is costs and
  nothing else." The Indian cost schedule splits buy and sell legs because **stamp duty is charged
  on the buy leg only**, and counts per-order brokerage from the number of holdings that actually
  changed, not from traded value.
- **Attribution that sums.** `contribution_pct` sums to the portfolio return — "which is the
  property that makes it an attribution rather than a list of individual performances."
- **Walk-forward reports `positive_share`**, not just the mean: "an allocation that was positive
  in 9 of 10 windows is a different proposition from one that was positive in 5, even at the same
  average."
- **Block bootstrap, not i.i.d.** Drawing single days independently destroys volatility clustering
  and makes drawdowns look milder than markets produce. Fixed seed, and the reason is stated:
  "a risk number that changes each time it is looked at invites re-rolling until it flatters."

**Assessment: intellectually honest quant work, and closer to our research plane's values than to
the rest of their own codebase.** It is also *orphaned* — nothing else in OpenAlgo uses it. Take
the reasoning; it belongs in our tearsheets.

### 2.7 Options suite, scalping, charting, MCP

Fifteen analytical tools (option chain, greeks, OI tracker, max pain, vol surface, GEX, IV smile,
gamma density, arbitrage, synthetic future). Keyboard-driven scalping terminal that resolves
underlying/expiry/strike and refuses CNC on index options. **MCP servers — stdio (local), HTTP,
and OAuth** (`mcp/mcpserver.py`, `blueprints/mcp_http.py`, `blueprints/mcp_oauth.py`).

**Assessment: the MCP surface is the most strategically interesting thing here after the brokers.**
They have made the entire trading platform addressable by AI agents. Given where the industry is
going, that is a durable distribution advantage and it is cheap for us to match.

### 2.8 Engineering practice (worth stealing wholesale)

- **FD hygiene as an institutional discipline.** Production is one gunicorn worker that never
  restarts, so any leak accumulates to "too many open files." Every engine/session/socket/
  subprocess/thread goes through a shared factory, and there is an `fd-audit` skill run after any
  change touching those. Five distinct session-cleanup layers.
- **Errors to `log/errors.jsonl`**, one JSON object per line with traceback + Flask request
  context; `logger.exception()` always, `traceback` and `print()` banned.
- **CI force-adds `frontend/dist/` back to `main`** so production servers and backend contributors
  need no Node.js — `git pull` is the canonical upgrade path.
- **Testing:** Vitest + Playwright + `@axe-core` accessibility tests as a named script.

---

## 3. Feature comparison matrix

Legend: ●●● strong / ●● partial / ● token / ○ absent

| Capability | OpenAlgo | Ours (today) | Ours (planned) | Verdict |
|---|---|---|---|---|
| **Broker integrations** | ●●● 36, uniform plugin contract | ● 1 (Kite) | ●● venue seam exists (`broker_protocol.py`, `venue.py`, `kite_venue.py`) | **They win, decisively** |
| Symbol normalization across brokers | ●●● canonical format + `SymToken` | ● Kite-native | ●● | They win |
| Market-data transport | ●●● ZMQ bus + WS proxy, 3000 sym | ●● in-process, WS hub | ●● | They win |
| Order routing / smart order | ●●● incl. basket, split, GTT, options multi-leg | ●● equity + options, real margin probe | ●●● | They win on breadth |
| **Visual node builder** | ●● 60 nodes, control-flow graph | ○ not built | ●●● typed dataflow graph | They ship, we design |
| **Node abstractions** | ● untyped sockets, cosmetic groups | ●● typed `ParamSpec` kinds exist | ●●● | **We win on the primitive** |
| **Custom Python nodes** | ●● subprocess-isolated scripts (not nodes) | ●● AST-validated codegen | ●●● both tiers | Split |
| **Strategy compiler** | ○ graph interpreted by 130-branch elif | ●●● grammar → emit → AST → no-builtins exec | ●●● | **We win, decisively** |
| **Backtesting a built strategy** | ○ none | ●●● spot + synthetic premium, net of charges | ●●● | **We win, decisively** |
| Portfolio backtesting (weights) | ●●● cost-honest, WF + Monte Carlo | ○ | ●● | They win |
| **Versioning of strategies/graphs** | ○ mutable JSON blob | ●●● sha256 content identity | ●●● | **We win, decisively** |
| **Experiment tracking** | ○ | ●●● Program→Hypothesis→ImmutableSpec→Run→Finding | ●●● | **We win, decisively** |
| Statistical validation (DSR/PBO/WF) | ● in portfolio product only | ●● built; DSR historically inert pre-2026-08 | ●●● | We win, with a caveat |
| Automatic strategy generation | ○ | ●● bounded deterministic search | ●●● | **We win** |
| Live/backtest parity | ○ no backtest to have parity with | ●●● hard invariant, parity-tested | ●●● | **We win** |
| Ledger integrity / charge model | ●● sandbox funds manager | ●●● paisa-exact, full Indian stack | ●●● | We win |
| Paper-safety architecture | ●● separate `sandbox.db` | ●●● fail-closed route allowlist + 3 env gates + ARM | ●●● | We win |
| Deployment / provenance | ●● git pull + dist in repo | ●●● `build_sha` per trade, readiness probe, guarded deploy | ●●● | We win |
| Scheduling | ●●● APScheduler, persisted jobstore | ●● engine loops | ●●● | They win |
| Webhook / external ingress | ●●● TradingView, Chartink, Amibroker, Excel | ○ | ●● | They win |
| **AI-agent surface (MCP)** | ●●● stdio + HTTP + OAuth | ○ | ●● | **They win** |
| Indicator library | ●●● Rust-backed `openalgo.ta`, 8 categories | ●● block library (~15 blocks) | ●●● | They win on breadth |
| Options analytics | ●●● 15 tools | ●● picker + local BS pricing | ●● | They win |
| Multi-tenant / marketplace | ○ single-user by design | ○ | ●●● | **Open field** |
| Runtime config / live tuning | ●● settings DB | ●●● `runtime_config` + amber drift flags | ●●● | We win |
| Accessibility / e2e testing | ●● axe + Playwright | ● vitest + typecheck | ●● | They win |
| Async architecture | ○ eventlet, no asyncio, `-w 1` ceiling | ●●● FastAPI/asyncio native | ●●● | **We win structurally** |

**Summary:** they own *connectivity, breadth, and distribution*. We own *rigour, reproducibility,
and the compiler*. Those are not the same market position, and ours is the harder one to copy —
36 broker adapters is a hiring problem; a content-addressed, statistically-deflated research plane
is a taste problem.

---

## 4. Workflow comparison

### Building a strategy

| Step | OpenAlgo | Ours |
|---|---|---|
| Author | drag nodes, fill a 3,840-line config panel | write a `Strategy` class, or let the generator enumerate compositions |
| Validate logic | structural check only (shape, node types, one trigger) | AST allow-list + grammar bounds + block warmup safety |
| Test before money | **nothing** — sandbox forward-time only | backtest sweep, net of charges, walk-forward, DSR |
| Version | none — JSON overwritten | sha256 content hash of behaviour |
| Deploy | toggle `is_active`, APScheduler job registered | deployment record + registry + `build_sha` stamped on every trade |
| Monitor | execution log rows | live cockpit, journal, ledger reconciliation, readiness probe |
| Improve | edit the graph in place (history destroyed) | new spec → new run → Finding, lineage preserved |

Their loop is **build → hope → watch**. Ours is **hypothesize → generate → validate → deflate →
promote → attribute**. The gap in their loop is exactly where trader money is lost, and it is not
an oversight they can patch cheaply — it requires an immutable graph identity and a
graph-executable-in-simulation, neither of which their architecture has.

### Research

OpenAlgo has **no research plane**. Nothing generates candidates, nothing tracks a hypothesis,
nothing deflates for multiple testing, nothing records negative results. The closest artifacts are
`portfolio/walkforward.py` and `portfolio/crisis.py` — both scoped to a static weights allocation,
both disconnected from strategy construction.

Our `research/` (on `feat/research-plane`) already has: `ResearchProgram → Hypothesis →
ExperimentSpec (immutable, content-hashed, SQLite-trigger-enforced) → ExperimentRun → Finding →
PromotionCandidate`, with `stats/dsr.py`, `stats/pbo`-adjacent machinery, `neff`, `retest`,
`evaluation/walkforward.py`, and a `pipeline/` of qualify → optimize → validate → score.

**Caveat we must not paper over:** per our own memory, DSR deflation never actually engaged
before 2026-08 (`var_sr` computed nowhere → benchmark pinned at 0), so pre-2026-08 findings in
`research.db` are unvalidated. The *architecture* is ahead of OpenAlgo by a category. The
*verified operation* of some of it is not yet ahead of anything, and we should say so internally.

---

## 5. UI/UX comparison

**Where OpenAlgo's Flow is better than what we will build by default:**

1. **Progressive disclosure via a categorized palette.** Nodes are grouped in tabbed categories
   with icon + label + one-line description on each drag handle. A new user can read the palette
   like a menu.
2. **Config-in-a-side-panel, not on the node.** Nodes stay small and readable; configuration lives
   in an inspector. This is the correct pattern and matches Blender's N-panel.
3. **`InsertableEdge`** — drop a node onto an existing wire to splice it in.
4. **Execution log docked in the editor.** You run and watch in the same view — no context switch.
5. **Keyboard shortcuts with a discoverable cheat-sheet** (`FlowKeyboardShortcuts.tsx`).
6. **Import/export JSON from the editor toolbar**, so a strategy is a shareable file on day one.
7. **Accessibility taken seriously** — axe-core in both unit and e2e tests.

**Where it is weak, and where the bar is therefore low:**

1. **No undo/redo.** Confirmed — `flowWorkflowStore.ts` has no history stack, and the editor has no
   undo handler. In a visual editor this is not a missing feature, it is a missing organ.
2. **The config panel is a wall.** 61 `nodeType ===` branches in one 3,840-line component means
   every node's UI was hand-written into a shared file; consistency is by discipline, not by
   construction.
3. **No node search / command palette** (`cmdk` is a dependency but not wired into the palette).
4. **No graph-level overview** beyond a minimap: no outline, no dependency view, no "what feeds
   this."
5. **No data preview on sockets.** You cannot hover a connection and see what flowed through it.
   In a typed dataflow graph this is nearly free and it is the single highest-value debugging
   affordance a node editor can have.
6. **No diff view, no history, no versions** — because the data model has none.
7. **Fragile node IDs.** `let nodeId = 0` at module scope, reseeded on load by regex-matching
   `node_(\d+)` over existing IDs. Use UUIDs.

---

## 6. Technical-debt comparison

| Dimension | OpenAlgo | Ours |
|---|---|---|
| Largest module | `flow_executor_service.py` 3,137 L; `ConfigPanel.tsx` 3,840 L | `runner.py` 2,490 L; `live_broker.py` 1,134 L |
| Dominant smell | **definition duplicated across 5 sites in 2 languages** | **unconsumed mechanisms** (built, correct, wired to nothing) |
| Dispatch style | ~130-branch `elif` chain; 61-branch JSX chain | registry + protocol seams (`broker_protocol`, `venue`, `decision_kernel`) |
| Dead/duplicate code | `telegram_bot_service.py` + `_fixed.py` + `_v2.py` coexist | historically: mechanisms with no callers; now guarded by 3 checks |
| Schema migrations | `upgrade/` scripts, no framework in evidence | Alembic (`alembic.ini`, `migrations/`, `db/migrate.py`) |
| Runtime ceiling | eventlet + `-w 1`, no asyncio, in-process SocketIO state | FastAPI/asyncio; single-process by choice, not by constraint |
| Dev/prod divergence | **structural** — asyncio works in dev, breaks in prod | low; same runtime both sides |
| Test posture | pytest + vitest + playwright + axe | pytest (two suites) + vitest + dryrun/backtest headless proofs |
| Config drift | env + settings DB | `runtime_config` overrides shadow defaults — **10 live overrides**, now amber-flagged in UI |

**The single most important debt lesson from their repo — the "five-site node definition":**

Adding one Flow node requires edits in:
1. `frontend/src/components/flow/nodes/<X>Node.tsx` (the visual)
2. `frontend/src/components/flow/nodes/index.ts` (registration)
3. `frontend/src/components/flow/panels/NodePalette.tsx` (palette entry, icon, colour, copy)
4. `frontend/src/components/flow/panels/ConfigPanel.tsx` (a new `nodeType ===` branch)
5. `services/flow_executor_service.py` (a new `elif` branch + an `execute_*` method)
6. `services/flow_workflow_validator.py` (`VALID_NODE_TYPES`)

Six sites, two languages, and a **parity test to catch the drift it makes inevitable.** They are
testing the symptom of a missing abstraction. With 60 nodes today, the marginal cost of node 61 is
already high; at the 300 nodes a Blender-style system implies, this design does not survive.

**This is the mistake we must not make.** One declarative node manifest; everything else derived.

---

## 7. Long-term scalability comparison

| Axis | OpenAlgo ceiling | Our ceiling |
|---|---|---|
| Concurrency | hard: `-w 1` gunicorn, in-process SocketIO state | soft: asyncio; horizontal split needs a broadcast bus |
| Users | **architectural: single-user, single broker session per deployment** | multi-tenant is a design decision we have not foreclosed |
| Node count | superlinear cost (6 edit sites/node) | flat, if manifest-driven |
| Graph size | recursion-depth 100, visit-cap 500, no memoization, whole-graph lock | topological scheduler + memoization = linear in nodes |
| Backtest throughput | n/a (no backtest) | sweep + per-`(instrument, interval)` cache; parallelizable |
| Broker count | proven to 36 | 1, seam exists |
| Data volume | duckdb for history (good call) | SQLite; DB-bloat redesign is a known open item |
| Marketplace | **impossible** — AGPL + single-user | open, if we keep our licence position clean |

The decisive line: **OpenAlgo cannot become a hosted multi-tenant Strategy OS** without a rewrite
of its session, worker, and licence model. That is not a temporary gap. It is the shape of the
building.

---

## 8. Reusable ideas — what to adopt, and how it must evolve in our platform

Ordered by value to us. "Evolve into" is mandatory — none of these should land as a copy.

| # | Their idea | Evolve into |
|---|---|---|
| R1 | Uniform broker plugin contract (`api/mapping/database/streaming`) | **A formal `Venue` capability protocol** — declared capabilities (`supports_gtt`, `supports_basket`, `tick_size_rule`, `product_types`) that the engine *queries*, not assumes. We already started this (`broker_protocol.py`, `venue.py`). Their contract is a directory convention; ours should be a typed interface with a conformance test suite any new venue must pass — so venue #2 is a weekend, not a quarter. |
| R2 | Canonical symbol format + `SymToken` mapping | **A `Instrument` value type with venue-specific projections**, not a string format. A string format re-encodes structure into text and then re-parses it (`NIFTY28MAR2420800CE`). Keep `(underlying, expiry, strike, right, segment)` structured; render the string only at the venue boundary. |
| R3 | ZMQ fan-in bus (SUB binds, PUBs connect) + WS proxy | **Adopt the topology, not the transport.** Our tick path is in-process today; the moment there are two consumers (engine + research replay, or engine + a second strategy runner), we need the decoupling. Start with an in-process async fan-out behind an interface, so swapping in ZMQ later is a one-file change. Steal the invariant *and its failure story* verbatim into our docs. |
| R4 | Single-flight + short-TTL cache with **shared failure** | **A `MarketDataGateway` with request coalescing.** Directly applicable: our sweep and research plane both hammer the same candles. The "share the failure too" detail is the non-obvious part and the reason it works under rate limits. |
| R5 | Validation at the single execution chokepoint | **Validate in `EngineRunner.process_entries`/deploy path, not in the API route.** We have more trigger paths than they do (signal loop, risk loop, backtest, sweep, research). One chokepoint, `strict=True`, before any record is created. |
| R6 | Errored condition takes *neither* branch | **Promote to a kernel invariant.** `decision_kernel` should have an explicit `UNDECIDED` outcome distinct from `False`. Silent false is how a typo becomes a SELL. |
| R7 | Multi-modal triggers as first-class objects | **A `Trigger` type in the strategy spec** — schedule, webhook, price level, order event, and (ours) *research promotion*. Persist scheduler jobs like they do (`coalesce`, `max_instances=1`, `misfire_grace_time`) — those three flags are exactly the settings that stop a missed cron from firing five times at once. |
| R8 | Graph JSON import/export | **Export the *spec*, not the graph** — an immutable, content-hashed, signed bundle (graph + params + block versions + data window). Sharing a mutable JSON blob is how OpenAlgo lost provenance; sharing a content-addressed bundle is a marketplace primitive on day one. |
| R9 | MCP surface (stdio + HTTP + OAuth) | **Expose our research plane over MCP, not just the trading API.** "Ask Claude to run a walk-forward on hypothesis 12" is a differentiator; "ask Claude to place an order" is table stakes and a liability. Read-only tools first. |
| R10 | Config in an inspector panel; small nodes | **Adopt the pattern, invert the implementation.** Their inspector is hand-written per node; ours must be *generated* from the node manifest's typed parameter list — which we already have the vocabulary for (`ParamSpec` kinds: LENGTH/THRESHOLD/PERCENT/MULTIPLIER/CHOICE/MINUTE/BOOLEAN). |
| R11 | `InsertableEdge`, keyboard shortcuts, palette categories, execution log in-editor | Adopt nearly as-is — these are UX table stakes we would otherwise skip. Add the things they lack: undo/redo, command palette, socket data preview. |
| R12 | Portfolio backtester's cost honesty | **Fold into our tearsheets:** cost drag vs a cost-free twin, attribution that sums to portfolio return, `positive_share` across walk-forward windows, block-bootstrap Monte Carlo with a fixed seed. We already model the full Indian charge stack; we do not yet *report the drag as a first-class number.* |
| R13 | Subprocess isolation with rlimits for user code | **Tier 2 of a two-tier code model.** Tier 1 = AST-validated generated blocks (ours, provably safe, backtestable). Tier 2 = arbitrary user Python in a resource-limited subprocess for the expressiveness ceiling. Keep tier 2 out of the AGPL question by writing it ourselves; the pattern is public knowledge. |
| R14 | `fd-audit`-style standing discipline; `errors.jsonl` | Adopt the *practice*. Our equivalent already exists in spirit (unconsumed-mechanism guards); a structured JSONL error sink with request context would have shortened both July outages. |
| R15 | Ship the built SPA so servers need no Node | We already build locally and rsync `dist/` — same conclusion, reached independently, for the same reason (a Vite build on a 1GB droplet has OOM'd us). Note it as convergent evidence, not a change. |

---

## 9. Everything worth ignoring

- **Eventlet / gunicorn `-w 1` / no-asyncio.** A permanent tax and a permanent scaling ceiling.
  We are asyncio-native. Never trade that away.
- **60 nodes wired by an `elif` chain.** The node count is impressive; the mechanism is a trap.
- **String-interpolated variables as the data plane.** `{{rsi.value}}` is a scripting language
  wearing a graph costume. It is the reason nothing in Flow can be type-checked, previewed,
  cached, or composed.
- **The cosmetic `group` node.** A coloured rectangle named "group" actively teaches users the
  wrong mental model of what grouping means.
- **Six SQLite databases as a design pattern.** Their motivation is isolation; the cost is no
  cross-database transactions, six init paths, six backup stories. Isolate by *schema and access
  policy*, and reserve a separate database for a genuinely separate lifecycle (which is exactly
  what our `research.db` is, and that one is justified).
- **Per-workflow stored API keys.** A graph that carries its own credential is an authorization
  object; deployments should hold credentials, artifacts should not.
- **Whole-graph mutex + "already running" rejection.** Should be a queue with a policy
  (skip / queue / cancel-previous), declared per trigger.
- **Their scalping/charting/options-tools surface area.** Fifteen analytical tools is a different
  product. Building it would blur what we are.
- **Multiple live copies of a service** (`telegram_bot_service{,_fixed,_v2}.py`). Ordinary rot, but
  a reminder: our own defining defect is the adjacent one — mechanisms that exist and are wired to
  nothing.
- **Any of their source code.** AGPL. Non-negotiable.

---

## 10. Architectural mistakes to avoid (the distilled list)

1. **Do not build a control-flow graph.** Build a typed dataflow graph. Everything else follows.
2. **Do not put node outputs in a global string-keyed bag.** Values flow on typed edges.
3. **Do not execute by recursive DFS with side effects.** Topologically schedule; memoize per run.
   Their "two orders from one crossover" bug is the canonical symptom, and their fix covers only
   three node types.
4. **Do not define a node in more than one place.** One manifest → visual, inspector, palette,
   validator, executor, docs, and the JSON schema all derive from it.
5. **Do not store a graph as a mutable blob.** Content-hash it; executions reference the hash.
6. **Do not ship a builder without a backtester.** A builder that can only be validated forward in
   live time is a machine for generating expensive lessons.
7. **Do not let "group" mean "rectangle."** A group must be an encapsulated subgraph with a typed
   interface, or the word poisons the concept.
8. **Do not treat an unevaluable condition as false.** Neither branch. Ever.
9. **Do not ship a visual editor without undo/redo.**
10. **Do not let a graph carry a credential.**
11. **Do not accept structural dev/prod runtime divergence.** They knowingly did, and their own
    docs call it their most common failure mode.
12. **Do not solve duplication with a parity test.** A parity test that must exist is a design
    telling you what it needs.

---

## 11. Prioritized adoption roadmap

Sequenced by *what unblocks the most downstream work*, not by effort. Phase A is the foundation
the visual layer stands on; building the visual layer first would repeat OpenAlgo's mistake at
higher resolution.

### Phase A — Foundations the node system requires (before any canvas code)

- **A1. The Node Manifest.** One declarative registry: node key, category, typed input sockets,
  typed output sockets, parameter list (reusing `ParamSpec` kinds), purity flag, cost hint, docs
  string, version. Everything derives from it: TS types, palette, inspector, validator, executor
  dispatch, JSON schema, and the marketplace listing. *Acceptance: adding a node is a one-file
  change plus a test; a codegen step emits the TS types, and CI fails if they drift.*
- **A2. The type system for sockets.** Reuse and extend the spec vocabulary we already have.
  Minimum socket kinds: `Series[float]`, `Series[bool]`, `Scalar`, `Instrument`, `Frame(OHLCV)`,
  `Signal`, `OrderIntent`, `Params`. **Series-vs-scalar must be in the type**, because the
  difference between "RSI" and "RSI right now" is where beginners lose money.
- **A3. Graph → Composition compiler.** The graph must compile down to the *existing* grammar and
  emitter (`research/strategy/builder/`), not to a new interpreter. This is the highest-leverage
  decision in the whole plan: it means a visual strategy is instantly backtestable, DSR-deflatable,
  content-hashable, and deployable through machinery that already exists and is already tested.
  *Acceptance: a graph and its equivalent hand-written composition produce byte-identical emitted
  source and identical backtest equity curves.*
- **A4. Content-addressed graph identity + immutable graph versions.** Reuse `identity.py`.
  Every save mints a version; runs, backtests, deployments and trades reference the hash.
  *Acceptance: given a trade, reconstruct the exact graph that produced it.*
- **A5. `UNDECIDED` in the decision kernel** (adopts R6). Small, cheap, safety-critical.

### Phase B — The canvas (only after A)

- **B1. Editor shell:** React Flow canvas, manifest-driven palette with search/command-palette,
  generated inspector, minimap, `InsertableEdge`, keyboard shortcuts + cheat sheet.
- **B2. Undo/redo** as a first-class store concern (command pattern over the graph, not a naive
  state stack).
- **B3. Type-aware connection validation** — reject invalid wires at drag time with a reason,
  not at run time with a silent unresolved variable.
- **B4. Socket data preview** — hover a wire, see the last N values / the series head. This is our
  answer to their non-existent debugging story and is nearly free in a typed dataflow engine.
- **B5. Live evaluation on historical data as you build.** Because A3 makes every graph
  backtestable, the canvas can show an equity curve *while editing*. OpenAlgo structurally cannot
  do this. **This is the demo that wins the category.**

### Phase C — Composition (the Blender half of the vision)

- **C1. Node Groups as real subgraphs.** Select nodes → collapse into a group with an explicit
  typed interface (promoted inputs/outputs), reusable across graphs, content-hashed
  independently, versioned independently. *The interface is the contract; the body is
  substitutable.*
- **C2. A group library** — user-local first, shared later. This is the marketplace's true unit:
  not "strategies", but *reusable computations*. Far more tradeable, far less dangerous.
- **C3. Custom Python nodes, two tiers.** Tier 1: AST-validated, whitelisted-block Python that
  compiles into the grammar (safe, backtestable, promotable to live). Tier 2: arbitrary Python in
  a resource-limited subprocess (expressive, sandbox/paper only, never auto-promotable). **The
  tier must be visible on the node**, and tier 2 must be structurally barred from the live path —
  in the same fail-closed way `SafePaperKite` bars order routes today.
- **C4. Graph diff + version timeline** — "what changed between v3 and v4, and what did it do to
  the equity curve."

### Phase D — Research plane × graph

- **D1. Every graph version is an `ExperimentSpec`.** The visual builder becomes a *hypothesis
  authoring tool*; saving a graph proposes an experiment.
- **D2. Parameter sweeps over graph sockets** — mark a parameter as swept, and the research plane
  enumerates, folds, deflates. Trial count feeds DSR, so a wider search raises the bar rather than
  manufacturing a winner (the principle already in `search.py`).
- **D3. Automatic graph mutation** — the generator proposes *graph edits* (swap this trend gate,
  add this filter), not just compositions from a fixed enumeration. Lineage via
  `parent_spec_id`, which the schema already has.
- **D4. Comparison view** — N graph versions on one tearsheet: equity, drawdown, cost drag,
  `positive_share`, DSR. Adopt R12's honesty standards.
- **D5. Fix and verify DSR deflation before any of D2–D4 is trusted.** Per our own memory, `var_sr`
  was computed nowhere and the benchmark was pinned at 0, so pre-2026-08 findings are unvalidated.
  A research plane that deflates incorrectly is worse than one that does not deflate at all,
  because it launders overfitting as significance. **This is a prerequisite, not a follow-up.**

### Phase E — Reach (parallelizable, lower architectural risk)

- **E1. Venue #2** through the capability protocol + conformance suite (R1). Proves the seam.
- **E2. Market-data gateway** with request coalescing and shared failure (R4).
- **E3. Webhook ingress** — TradingView/Chartink-shaped, per-deployment token + secret (R7/R8).
- **E4. MCP surface** over the research plane, read-only first (R9).
- **E5. Signed, content-addressed strategy bundles** — the marketplace primitive (R8).

**Deliberately not on this roadmap:** an options analytics suite, a scalping terminal, a charting
terminal, 36 broker integrations. Those are OpenAlgo's business, and chasing them is how we
become a worse OpenAlgo instead of a better category.

---

## 12. If I were building the world's best Strategy Operating System after studying OpenAlgo, this is exactly what I would build next

Studying OpenAlgo settles one question: **the visual builder is not the product.** They built the
best one in Indian retail algo trading — 60 nodes, a polished canvas, six trigger modalities, 36
brokers behind it — and it still cannot answer the only question a trader actually has: *does this
work?* Not "did it run", not "did it place the order". **Does it work.**

So here is what I would build, in one sentence: **a typed computational graph whose every version
is an immutable, content-addressed, backtestable, statistically-deflated experiment — where the
canvas is a view onto the compiler, and the compiler is already the thing that runs real money.**

Concretely, and in this order:

**1. The manifest and the socket type system — before a single line of canvas code.**
One declarative node definition, everything else generated. Types on sockets, with
`Series` vs `Scalar` in the type. This is the decision that makes the difference between 300 nodes
being *easy* and 300 nodes being *impossible*, and it is invisible in a demo, which is exactly why
OpenAlgo skipped it and why we must not.

**2. Compile the graph into the grammar we already have — do not write a graph interpreter.**
This is the keystone. OpenAlgo's graph is interpreted by a 3,137-line `elif` chain that can only
run forward in live time. Ours should lower into `Composition` → `emit_source()` → AST allow-list →
no-builtins `exec` — the path that is already backtested, already content-hashed, already
parity-tested against the live engine, already deployable. The moment that lowering works, a
visual strategy inherits, *for free*: the spot and synthetic-premium backtesters, the full Indian
charge stack, walk-forward, DSR, the immutable experiment ledger, `build_sha` provenance, and the
paisa-exact ledger invariant. **Nobody else in this market can offer that, because nobody else
built the compiler first.** We did, by accident of caring about the research plane before the UI —
and that accident is now the entire strategic advantage.

**3. Make the canvas show the equity curve while you edit.**
Not a "Backtest" button. A live tearsheet in the corner of the editor that updates as you wire.
Change the z-threshold from 1.0 to 1.5 and watch the curve, the drawdown, the cost drag and the
trade count move. OpenAlgo structurally cannot do this — no graph backtester, no memoization, no
types. It is the single most compelling thing a Strategy OS can put on a screen, and it falls out
of steps 1 and 2 almost for free.

**4. Make groups real, and make the group the marketplace unit.**
Blender's actual insight is not "nodes" — it is *node groups*: an encapsulated subgraph with a
typed interface that composes exactly like a primitive. Ship that and the platform stops being a
strategy builder and becomes a **language**, with a growing vocabulary its users write. And the
tradeable artifact becomes a *reusable computation* — "Nifty expiry-day volatility regime filter",
content-hashed, versioned, with its own tearsheet — rather than a whole strategy. That is a far
better marketplace: more composable, more evaluable, and far less likely to sell someone a
black-box account-killer.

**5. Two tiers of Python, and make the tier structural.**
Tier 1 compiles into the vetted grammar: provably safe, backtestable, promotable to real money.
Tier 2 is arbitrary Python in a resource-limited subprocess: expressive, sandbox-only, and
**barred from the live path by construction** — the same fail-closed discipline as `SafePaperKite`,
not a checkbox. OpenAlgo has only tier 2 and no way to backtest it; a tier-1/tier-2 split is how
you get both the ceiling and the safety.

**6. Close the loop: every graph save is a hypothesis.**
Save → `ExperimentSpec` (immutable, content-hashed, git commit + rule-set versions + seed) → run →
Finding, with negative results first-class and lineage through `parent_spec_id`. Then let the
generator mutate *graphs*, not just compositions, with the trial count feeding the deflation so a
wider search raises the significance bar. **Fix and verify DSR first** — a research plane that
deflates wrongly launders overfitting as significance, which is worse than not deflating at all.

**7. Only then, reach.** Venue #2 through a capability protocol with a conformance suite. Webhook
ingress. MCP over the research plane. Signed strategy bundles. Each of these is a business
decision; none of them is an architectural risk once 1–6 exist.

**What I would explicitly refuse to build**, having seen where it leads: a fifteen-tool options
analytics suite, a scalping terminal, a charting terminal, and thirty-six broker adapters. That is
OpenAlgo's business and they are winning it. Ours is the question they cannot answer.

The final framing, and the one worth putting on a wall:

> **OpenAlgo built a way to express a strategy. We should build a way to *know* one.**
> They connect a trader to 36 brokers. We should connect a trader to the truth about their own
> ideas — reproducibly, with the overfitting deflated out, with every claim falsifiable after the
> fact because the graph that made it can never be silently edited.
>
> The visual node layer is not the product. **It is the interface to the product.** The product is
> the compiler, the ledger of experiments, and the fact that the thing you drew is the same thing
> that traded.

---

### Appendix: evidence index

| Claim | Source |
|---|---|
| AGPL-3.0 | `License.md:1` |
| 36 broker plugins, uniform contract | `broker/` (36 dirs); `broker/zerodha/{api,mapping,database,streaming}` |
| Control-flow graph, global variable bag | `services/flow_executor_service.py:71` (`WorkflowContext`) |
| Recursive DFS, depth 100 / 500 visits | `flow_executor_service.py:2777–2800` |
| "two orders from one crossover" | `flow_executor_service.py` gate comment, ~L2926 |
| Errored condition takes neither branch | `flow_executor_service.py` condition-filter comment |
| Validation at the single chokepoint | `flow_executor_service.execute_workflow` |
| No graph versioning (mutable JSON) | `database/flow_db.py:78–98` |
| 60 node types | `services/flow_workflow_validator.py:25–89` |
| ConfigPanel 3,840 L / 61 branches | `frontend/src/components/flow/panels/ConfigPanel.tsx` |
| No undo/redo | `frontend/src/stores/flowWorkflowStore.ts` (no history state) |
| `group` is cosmetic | `frontend/src/components/flow/nodes/GroupNode.tsx` |
| Fragile node IDs | `frontend/src/pages/flow/FlowEditor.tsx:86–87,173–177` |
| Single-flight history cache | `services/indicator_service.py` |
| Subprocess rlimits | `blueprints/python_strategy.py:331–418` |
| Sandbox engine 7,110 L, isolated DB | `sandbox/` |
| Portfolio backtester quality | `portfolio/engine.py`, `portfolio/walkforward.py` |
| No flow backtesting | `okf/skills/backtesting.md` (external link); `examples/python/backtesting_vectorbt.py` |
| Eventlet / `-w 1` / no asyncio | OpenAlgo `CLAUDE.md`, "Runtime Constraints" |
| ZMQ SUB-binds invariant | OpenAlgo `CLAUDE.md`, "Invariants" |
| Our compiler | `research/strategy/builder/{grammar,emit,validate,load,search,blocks}.py` (branch `feat/research-plane`) |
| Our content identity | `backend/app/strategy/identity.py` |
| Our typed param vocabulary | `backend/app/strategy/spec.py:55–98` |
| Our immutable experiment ledger | `research/domain/models.py` (SQLite `RAISE(ABORT)` triggers) |
| DSR historically inert pre-2026-08 | project memory: `research-findings-pre-2026-08-are-unvalidated` |
