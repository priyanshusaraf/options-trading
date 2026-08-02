# Production Architecture Audit — pre-Phase 3/5/6/9/13

**Date:** 2026-08-02 · **Branch:** `feat/exec-completeness` · **Scope:** architecture only.
Style, naming, comments, docs, dead code and cleanup are deliberately not reported.

**Reviewed:** `backend/app/{engine,api,db,core,strategy,backtest,providers,ledger}`,
`backend/research/**`, `frontend/src/**`.

---

## Executive summary

This is a **single-account, single-book, single-process trading bot with an unusually
good research laboratory bolted beside it**. The engineering quality *within* each
module is high — fail-closed safety gates, an instance lock, an order journal,
schema-additive migrations, real reconciliation. That quality is not the question.

The question asked was whether the current decisions get more expensive after
Phases 3/5/6/9/13. The answer is that **five load-bearing identity decisions are
wrong for the target product**, and every one of them is cheap to change now and
extremely expensive after a marketplace exists:

1. A **position is identified by instrument**, not by a deployment. Two strategies can
   never hold the same underlying, and the API path `/api/positions/{key}` bakes that
   into the public contract.
2. There is **no broker interface** — `LiveBroker` inherits from the paper simulator,
   and Zerodha vocabulary (GTT trigger ids, MIS/NRML, exchange codes) reaches into the
   ORM and the engine.
3. The **strategy contract is four boolean columns**. It cannot express exits, sizing,
   risk, or even its own parameters — so visual/Python/marketplace strategies cannot
   be different from each other in any way that matters.
4. **Strategy identity is an unversioned mutable string with a silent fallback** to the
   default strategy. Under a marketplace this is a real-money correctness bug, not a
   design smell.
5. **All configuration is process-global.** There is no scope at which a deployment
   could have its own parameters.

Findings 1, 3, 4 and 5 are all facets of one missing concept: **the Deployment** —
"this strategy, at this version, with these params, on these instruments, on this
account, with this book." Introducing that one entity now is the single highest-value
change available, and it is the prerequisite for Phases 3, 5, 6 and 13.

---

# CRITICAL

## C1 — A position is keyed by instrument; there is no deployment/account dimension

**Problem.** `positions.instrument_key` is the de-facto identity of the open book.
`PaperBroker.position_for(key)` (`engine/broker.py:45`) selects a single row by
instrument; `runner.process_entries` builds `held = {p.instrument_key: p}`
(`runner.py:945`); `scan_signals` builds `opens` the same way (`runner.py:371`);
`open_position` refuses entry if `position_for(inst.key) is not None`
(`broker.py:206`). The REST surface hard-codes it too — `/api/positions/{key}/close`,
`/sltp`, `/no-take-profit`. `capital_state` is a **single row fetched as `id=1`**
(`broker.py:37`), so there is exactly one cash balance for the whole system, and
`watchlist_membership` uses `instrument_key` as the **primary key** so an instrument
belongs to at most one watchlist and therefore at most one strategy
(`core/watchlists.py:11`).

**Why it matters.** "Multiple simultaneous live strategies" is not a feature that can
be added on top of this; it is excluded by the data model. Two strategies that both
like RELIANCE cannot both hold it. One strategy's drawdown consumes another's cash
with no attribution. There is no boundary at which an enterprise customer, a
marketplace subscription, or a sub-account could exist.

**Long-term consequence.** After Phase 13, every position row, every trade row, every
equity snapshot, every REST path and every frontend view assumes one book. Adding the
deployment dimension then means a data migration of the money record *plus* a
breaking API version *plus* a frontend rewrite, executed against live capital.

**Recommended solution.** Introduce a `Deployment` entity now (id, strategy_key,
strategy_version, account_id, params_json, universe, status, capital_allocation) and
add `deployment_id` as a **non-null FK on `positions`, `trades`, `equity_snapshots`,
`signal_events`, `order_journal`**. Backfill every existing row to a single
`deployment_id=1` ("legacy default") — the current behaviour becomes one deployment,
so nothing changes operationally on day one. Move `capital_state` from a singleton
row to one row per deployment (or per account, with per-deployment allocation).
Re-key position lookups to `(deployment_id, instrument_key)` and add REST paths
`/api/deployments/{id}/positions/{key}`, keeping the old ones as aliases into
deployment 1.

**Migration effort today:** ~1–2 weeks. Additive columns, one backfill, mechanical
lookup re-keying, and the API alias keeps the frontend working unchanged.
**Effort after Phases 3/5/6/9/13:** 2–4 months, and it is a migration of the money
record under live capital with a mandatory API break.
**Blocks continued development:** **Yes** — Phase 3 (unified strategy representation)
cannot define what a strategy instance *is* without it.

---

## C2 — No broker abstraction; `LiveBroker` inherits the paper simulator, and Kite vocabulary reaches the ORM

**Problem.** There is no `Broker` interface or Protocol. `class LiveBroker(PaperBroker)`
(`engine/live_broker.py:35`) — the real-money execution class inherits from the
simulator and overrides ~15 of its ~25 methods, while silently inheriting the rest
(`capital()`, `mark()`, `snapshot()`, `reconcile()`, `book_partial_close*`,
`reinforce_position`). The correct seam exists but is too narrow: `OrderClient`
(`engine/order_executor.py:45`) declares only `place`/`status`/`cancel`, while
`LiveBroker` calls `place_stop_gtt`, `modify_stop_gtt`, `delete_gtt`,
`place_stop_order`, `gtt_status`, `find_fill` directly on the Kite client. Broker
concepts have leaked further out than the engine: `Position.gtt_trigger_id`
(`db/models.py`) is a **Zerodha GTT id stored in the domain model**, and
`kite_order_client.product_for_segment()` returns Kite product codes (`MIS`/`NRML`)
that the engine passes around as if they were domain terms.

**Why it matters.** Phase 9 asks whether adding Dhan/Fyers/Angel/IB requires modifying
existing execution logic. It does, in three places at once: a new broker must subclass
`PaperBroker` (inheriting simulator semantics it does not want), must implement
Kite's GTT/SL-M protection model (IB has neither — it has bracket/OCA orders), and
must find somewhere to put its own protection-order id because the column is named
after Zerodha's.

**Long-term consequence.** Each new broker becomes another 1,100-line subclass with
its own copy of journalling, in-flight tracking, orphan reconciliation and stop
resync — the exact logic that has already produced production incidents. Enterprise
multi-broker then means N divergent implementations of the money path.

**Recommended solution.** Define an explicit `Broker` **Protocol** (the domain-facing
verbs: `open`, `close`, `partial_close`, `mark`, `ensure_protection`,
`update_protection`, `reconcile`, `recover`) and a separate `ExecutionVenue` Protocol
(the wire-facing verbs: `place`, `cancel`, `status`, `place_protective_stop`,
`modify_protective_stop`, `cancel_protective_stop`, `positions`, `funds`,
`margin_probe`, `tick_size`). Make `PaperBroker` and `LiveBroker` two *siblings* over
one shared `BrokerCore` that owns ledger bookkeeping; move Kite specifics behind
`KiteVenue`. Rename `Position.gtt_trigger_id` → `protective_order_id` (+
`protective_order_kind`) and translate `MIS`/`NRML` from a neutral
`product`/`tenor` enum at the venue boundary.

**Migration effort today:** ~2–3 weeks. Mostly mechanical extraction; the test suite
(1,618 backend tests) is strong enough to make it safe.
**Effort after remaining phases:** 2–3 months, done while N broker integrations and
marketplace strategies depend on the current inherited semantics.
**Blocks continued development:** **Yes for Phase 9.** No for 3/5/6, but doing 9 first
is cheaper than retrofitting.

---

## C3 — The strategy contract cannot express risk, exits, sizing, or its own parameters

**Problem.** `Strategy.signals()` returns a DataFrame with four boolean columns
(`strategy/registry/base.py`); the docstring states outright that "Direction/stop/target
sizing is NOT the strategy's job; the engine owns the risk layer." That was the right
call for one hand-written strategy. It is the wrong contract for four strategy
*sources*. Consequences visible in the code today:

- **Only the default strategy receives parameters.** `scan_signals` passes
  `ema_length/z_length/entry_z/slope_lookback` from global `Settings` when
  `strat.key == DEFAULT_STRATEGY_KEY`, and calls `strat.signals(frame_from(candles))`
  with **no parameters at all** for every other strategy (`runner.py:403-411`). A
  marketplace strategy cannot be tuned, and two deployments of the same strategy
  cannot differ.
- **Exits are the engine's, not the strategy's.** All trade management lives in
  `runner._apply_trailing`, `_apply_lockstep`, `_mark_exit_equity`,
  `_mark_exit_futures` and the `evaluate_exit`/`equity_exit` helpers. The one escape
  hatch — `Strategy.risk_model` — is a fixed-shape dict (`atr_length`,
  `trail_start_r`, `capture_pct`…) that describes exactly one ratchet design and is
  honoured **only in the backtest overlay and one hard-coded branch** of the live
  engine.
- **Sizing is the engine's.** `_intraday_margin_sizer` / `_futures_margin_sizer` are
  runner methods keyed by segment.

**Why it matters.** Phase 3 asks for one representation covering visual, Python,
marketplace and generated strategies; Phase 5/6 let users author them. If a user's
strategy cannot say "exit after 3 bars", "risk 0.5% per trade", or "my z-threshold is
1.4", then the builder and the editor are pickers for entry conditions only, and every
strategy on the marketplace behaves identically once in a trade.

**Long-term consequence.** The pressure will be released the only way the current
shape allows: more `if strategy_key == …` branches inside `process_entries` and
`mark_and_exit_positions`, which are already 340 and 90 lines of segment branching.
Every marketplace strategy then becomes a modification to shared, real-money code.

**Recommended solution.** Widen the contract to a **StrategySpec** with four declared
parts — `signals` (as today), `entry_policy` (sizing model + filters), `exit_policy`
(a *declarative* set of exit rules the engine interprets: fixed pct, ATR, ratchet,
time-stop, flag-exit), and a **typed parameter schema** (name, kind, bounds, default)
that the builder, the editor, the backtester and the settings UI all read. Pass
resolved params to `signals()` for *every* strategy, not just the default. The
research plane's `blocks.py`/`grammar.py` already proves the pattern — a bounded,
typed, validated vocabulary — so lift that idea into `app/strategy` and let
`Composition` be one *producer* of a StrategySpec rather than a parallel universe.

**Migration effort today:** ~3–4 weeks. Two strategies to port, one exit-policy
interpreter to write around logic that already exists.
**Effort after remaining phases:** 4–6 months plus a compatibility shim for every
published strategy, or a marketplace v2 with a hard break.
**Blocks continued development:** **Yes.** This *is* Phase 3; getting it wrong makes
Phases 5, 6 and 13 build on sand.

---

## C4 — Strategy identity is an unversioned mutable string that silently falls back to the default

**Problem.** `get_strategy(key)` returns the **default strategy** for any unknown or
`None` key (`strategy/registry/__init__.py`), and the docstring calls this "fail-safe."
`GeneratedStrategyRow` has `key` as its primary key with **no version and no content
hash**; deployed generated strategies are reconstructed at startup, and if a row fails
to rebuild the startup handler logs an error and continues (`main.py:66-74`). Positions
and trades store `strategy_key` as a plain nullable string with no FK.

**Why it matters.** Fail-safe is the correct posture for a single owner running one
strategy he wrote. Under a marketplace it inverts: a strategy that fails to load, or
whose key was renamed, or that was withdrawn by its author, does not stop — **it
trades the platform's default strategy with the customer's real capital, and the
trade rows say it was the customer's strategy.** With `generated_strategies.key` as a
PK and no version, redeploying an edited strategy silently rewrites history: past
trades attributed to `gen_x` now point at different logic, so every backtest,
attribution report and marketplace performance claim becomes unfalsifiable.

**Long-term consequence.** This is the class of defect that ends in a regulatory
conversation, not a bug report. It also makes "hundreds of crores of client capital"
uninsurable: you cannot prove which code executed which trade.

**Recommended solution.** Make strategy identity `(key, version)` where `version` is
immutable and content-addressed (hash of the composition/source + param schema).
Store `strategy_version` alongside `strategy_key` on positions, trades and
deployments. **Replace the silent fallback with a fail-closed resolution** for any
non-default, deployment-bound strategy: unresolvable ⇒ the deployment is halted and
alerted, never substituted. Keep the fallback only for the legacy per-instrument
default path, and log it loudly. `build_sha` already on `trades` shows the instinct is
there — extend it to the strategy artifact.

**Migration effort today:** ~1 week. Additive columns, one resolution change, tests.
**Effort after remaining phases:** 1–2 months plus a re-attribution of published
performance across every marketplace listing — some of which will be unrecoverable.
**Blocks continued development:** **Yes for Phase 13**, and it should not wait —
generated strategies can already be deployed today.

---

## C5 — All configuration is process-global; there is no per-strategy or per-deployment scope

**Problem.** `Settings` (`core/config.py`, 522 lines, ~87 knobs) is a process
singleton; `runtime_config` is a **flat global key/value table**; `effective(settings)`
merges them into one `params` dict that the runner refreshes each iteration and every
subsystem reads. Every risk and behaviour knob — `intraday_max_positions`,
`max_daily_loss`, `stop_loss_pct`, `entry_window_start`, `trail_*`,
`intraday_profit_lock_*`, `gap_guard_*` — is global. `arm`, the kill switch and the
daily-loss halt are likewise **single global flags on the runner**.

**Why it matters.** Every one of these is conceptually a property of a *deployment*.
Two live strategies with different risk profiles cannot coexist: they share one stop
loss percentage, one daily loss limit, one arm switch, one concurrency cap. An
enterprise customer cannot be given a risk envelope. A marketplace strategy cannot
ship with its own recommended parameters, because there is nowhere to put them.

**Long-term consequence.** The kill switch is the sharpest case: after Phase 13 it is
either all-or-nothing for every customer strategy, or it needs re-plumbing through
every call site that currently reads `self.armed`.

**Recommended solution.** Three-level resolution — **platform defaults → deployment
overrides → instrument overrides** — behind one `params_for(deployment, instrument)`
accessor, with `runtime_config` becoming the platform level and gaining a
`scope`/`scope_id` column. Give `arm`/`halt`/`kill` a per-deployment state alongside
the global master switch (global kill must remain, and must remain the strongest).
Note the existing owner rule that the 10 live `runtime_config` overrides are
deliberate decisions — they migrate to platform scope unchanged.

**Migration effort today:** ~2 weeks, mostly threading one accessor through the runner.
**Effort after remaining phases:** 2–3 months touching every engine call site plus the
settings UI plus every deployment's stored config.
**Blocks continued development:** **Yes** — pairs with C1; a deployment without its own
parameters is not a deployment.

---

## C6 — The backtester is a second, divergent implementation of trade management

**Problem.** `backtest/engine.py` re-implements entry and exit independently of the
live engine and says so: *"the option-premium stop/target of the LIVE engine is not
modelled here."* The backtest honours strategy flags plus the ATR-ratchet overlay; the
live engine honours a premium stop/target, a percentage trailing ratchet, a lockstep
SL/TP band, a profit-lock give-back rule, event blackouts, a gap guard, an entry
window, a stale-signal guard and a re-entry cooldown. Sizing differs too — the
backtest is fixed one-lot and leverage-free, while live sizing runs a real
`order_margins()` probe. Two of these code paths are already known to disagree
(`docs/2026-08-01-backtester-audit.md`: slippage was entirely unmodelled on the spot
path).

**Why it matters.** In a marketplace, the backtest number *is the product*. If the
simulator and the executor are different programs, published performance is not a
prediction of live behaviour, and the divergence is invisible — it shows up as
customer P&L, months later.

**Long-term consequence.** Every fix to live exit logic silently invalidates every
published backtest, and there is no mechanism that would tell you.

**Recommended solution.** Extract a **pure decision kernel** — `(position_state,
bar/quote, params) → Decision(hold | exit(reason) | adjust_stop(px))` — used
*verbatim* by both the backtester and `mark_and_exit_positions`. The live side keeps
its I/O, broker calls and journalling around the kernel; the backtest side keeps its
fill model. Add a **parity test** that replays real closed trades through the kernel
and asserts the backtester reproduces the live exits (the C-P2 exit sweep already
replays real trades — this is a small extension of machinery that exists). Where a
rule genuinely cannot be simulated, make that explicit in the result payload rather
than absent.

**Migration effort today:** ~3 weeks.
**Effort after remaining phases:** 3–5 months, and it must be done *while* customers
are trading against the numbers you are about to correct.
**Blocks continued development:** **No for 3/5/6/9. Yes for Phase 13** — do not open a
marketplace on unverified numbers.

---

## C7 — Persistence: single-file SQLite, an exclusive per-process lock, and hand-rolled additive-only migrations

**Problem.** Three SQLite files (`paper_trader.db`, `ledger.db`, `research.db`) with
three separate declarative bases — the isolation is good and deliberate. The problems
are underneath it:
- `db/session.py:110 _migrate_schema()` is a **hand-maintained dict of `ADD COLUMN`
  statements** — explicitly "no Alembic in this project". It can only add columns. It
  cannot rename, drop, change a type, add a constraint, or back out. There is no
  schema version number, so there is no way to ask a database what shape it is.
- `core/instance_lock.py` takes an **exclusive flock on the DB path**, so exactly one
  backend process may run per database. That is exactly right today (two processes
  would double-trade one account) and is a hard ceiling on "thousands of deployments."
- `capital_state` singleton and `positions` keyed by instrument (see C1) mean the
  schema has no tenancy dimension at all.
- `backtest_results` (~120 columns judging by the model) couples the storage schema
  directly to one metric set; a new metric means a new column via the same dict.

**Why it matters.** Every one of C1–C5's fixes is a schema change of a kind the current
migration mechanism **cannot express**. The first `NOT NULL` FK, the first rename
(`gtt_trigger_id` → `protective_order_id`), the first constraint — each needs the
SQLite 12-step table-rebuild dance, hand-written, against the live money record.

**Long-term consequence.** Either migrations stay additive forever (schema accretes
until it is unreadable) or the first real migration is authored under pressure with
production capital in the tables.

**Recommended solution.** Adopt **Alembic now**, while the schema is small and there is
one deployment to migrate: stamp the current schema as the baseline revision, keep the
existing additive dict as revision 1, and require every future change to be a revision
with an `upgrade`/`downgrade`. Add a `schema_version` row. Plan the **Postgres path**
explicitly (not necessarily executed now): keep SQLAlchemy dialect-neutral, avoid
SQLite-only pragmas outside the connection hook, and treat the single-writer flock as a
documented v1 constraint with a named exit — because enterprise, multi-account and
"thousands of deployments" all require multi-writer storage and horizontal processes.

**Migration effort today:** ~1 week for Alembic + baseline. Postgres portability is a
separate, later project (~4–6 weeks) but the choices that make it possible are free
today.
**Effort after remaining phases:** 2–4 months, executed against customer data.
**Blocks continued development:** **Yes, practically** — C1/C4/C5 all need migrations
this mechanism cannot write.

---

# HIGH

## H1 — Bidirectional dependency between the execution plane and the research plane

**Problem.** `research/` imports `app/` (`evaluation/kernels.py` → `app.backtest.engine`;
`strategy/builder/load.py` → `app.strategy.registry.base`; `nightly.py` →
`app.core.config`, `app.providers.factory`) **and** `app/` imports `research/`
(`core/research_read.py` → `research.domain.models`, `research.strategy.explain`;
`core/generated_strategies.py` → `research.strategy.builder.{grammar,load}`;
`api/portfolio_routes.py` reads research.db). The intent — research reuses pure
execution kernels, execution reads research results — is sound, but it is implemented
as a package-level cycle.

**Why it matters.** The execution process **imports the laboratory to reconstruct a
deployed strategy at startup**. That means the research plane's code is in the
real-money process's import graph and failure surface. It also means neither plane can
be deployed, versioned or run independently, which the multi-machine future requires.

**Long-term consequence.** Phase 6 (Python editor) and Phase 13 make this worse: the
strategy *compiler* would live on the research side while the *executor* needs it at
boot.

**Recommended solution.** Extract a third package — `core_kernels` (or `platform/`) —
holding the strategy contract, the block library, the composition grammar, the decision
kernel (C6) and the charge/metrics math. Both planes depend on it; **neither depends on
the other**. Research writes promotion candidates; execution reads a *serialized
artifact* (composition JSON + version hash + params), never the builder module. Add an
import-direction test — the codebase already fails builds on unconsumed mechanisms, so
the pattern is established.

**Effort today:** ~2 weeks (mostly moves). **After remaining phases:** 2–3 months.
**Blocks development:** No, but it compounds with C3 — do it as part of Phase 3.

## H2 — `EngineRunner` is a god object (2,433 lines, ~90 methods)

**Problem.** One class owns: per-instrument config loading and mutation, signal
computation, three separate entry pipelines (options / equity intraday / index
futures), three exit pipelines, margin sizing, the daily-loss halt, the gap guard, the
event-risk gate, the order circuit breaker, profit-lock, overnight square-off, funds
refresh, ledger re-anchoring, telemetry pruning, option-chain caching, health beats,
watchdogs, the arm/kill switches and the DB session lifetime. `process_entries` alone
is ~340 lines of sequential guard clauses; extension has been by `if segment == …`
branching three times already.

**Why it matters.** Every new strategy type, segment, broker or deployment target
lands in this file, and this file is the real-money path. It cannot be unit-tested per
concern, cannot be reasoned about by an external developer, and cannot be parallelised.

**Recommended solution.** Decompose along the seams the code already implies:
`SignalScanner`, `EntryPipeline` (with a per-segment `SegmentAdapter` registered rather
than branched), `PositionManager`, `RiskGovernor` (halt/gap/event/circuit-breaker as a
composable chain of `EntryGate` objects), `AccountSync`, `HealthReporter`. Keep
`EngineRunner` as the loop scheduler that wires them.

**Effort today:** ~3–4 weeks. **After remaining phases:** 3–4 months.
**Blocks development:** No — but every deferred week adds branches to the same file.

## H3 — No API versioning, no tenancy, and internal state on the public surface

**Problem.** ~45 flat `/api/*` routes with no version prefix. Resource identity is the
instrument (`/api/positions/{key}/close`), which C1 will break. `/api/status` and the
`state` WebSocket message broadcast the runner's internal dict — including
implementation fields like `_ratchet_atr`. The engine is reached from routes as a
process singleton (`app.state.runner`). Auth is **one shared bearer token**
(`api/auth.py`) with **no identity, no roles, no per-resource authorization**, and it
is disabled entirely when unset. Ledger routes (`/snapshot`, `/artifacts`) are mounted
on a different prefix convention from everything else.

**Why it matters.** Phase 13 requires "who is asking" on every request. Permissions and
enterprise licensing have no seam to attach to — there is no principal in the system.
And without a version prefix, the C1 re-keying is an unannounceable break.

**Recommended solution.** Move everything to `/api/v1/*` **now**, while the only client
is your own frontend (a mechanical prefix + one constant in `lib/api.ts`). Introduce a
`Principal` resolved by middleware (single-owner token maps to principal 1) and pass it
to routes, so authorization has a place to exist before it has rules. Define explicit
response DTOs for `status`/`dashboard`/`positions` instead of serializing engine
internals.

**Effort today:** ~1–2 weeks. **After remaining phases:** 2–3 months plus a public
breaking change.
**Blocks development:** No, but the versioning prefix should be done before Phase 3
touches routes.

## H4 — Segment branching is the extension mechanism for asset classes

**Problem.** `options | equity_intraday | index_futures` appear as string literals with
`if` branches in `process_entries`, `mark_and_exit_positions` (`runner.py:568-572`),
the broker (`open_equity_position` / `open_futures_position` / `close_*` as separate
methods), charges, and the models. Each new segment was added by duplicating a lane.

**Why it matters.** "Multiple exchanges" and "multiple brokers" both multiply into this.
US equities, crypto or NSE currency each mean another triple of branches across the
runner and another pair of broker methods.

**Recommended solution.** A `SegmentAdapter` interface (`size()`, `price()`,
`open()`, `mark()`, `exit_rules()`, `charge_segment()`, `session_hours()`) registered
by key — the same registry pattern already used successfully for strategies. Collapse
the broker's six `open_*/close_*` methods into two that take an adapter.

**Effort today:** ~2 weeks. **After:** 2 months. **Blocks development:** No.

## H5 — Frontend has no routing, no server-state layer, and two parallel app architectures

**Problem.** `App.tsx` holds the active tab in `useState` with a literal `TABS` array
and a chain of `{tab === 'x' && <View/>}` — **no router**, so nothing is deep-linkable
or bookmarkable, and the back button does nothing. There is no data-fetching/caching
layer (no react-query/SWR); each view calls `lib/api.ts` and manages its own loading
state; a single `LiveContext` carries WebSocket state. Separately, `frontend/src/ledger`
is a **second application** with its own shell, router-ish surface stack, store,
domain layer and keymap (~6,000 lines) mounted outside `<main>`.

**Why it matters.** Phases 5, 6 and 13 are all frontend-heavy — a visual builder, a code
editor, a marketplace, and per-deployment dashboards. Every one of them needs URLs
(`/strategies/{id}/edit`, `/marketplace/{listing}`, `/deployments/{id}`). Retrofitting
routing means touching every view's mount assumption.

**Recommended solution.** Adopt a router (React Router or TanStack Router) and make
tabs routes now; adopt a server-state library so cache invalidation stops being
per-view `useEffect`; establish one feature-folder convention and migrate the ledger
sub-app onto it rather than leaving two idioms.

**Effort today:** ~2 weeks. **After remaining phases:** 2–3 months across a much larger
surface. **Blocks development:** No — but it blocks Phase 5/6 being pleasant.

## H6 — There is no durable decision log; provenance stops at the order

**Problem.** `order_journal` (excellent) records the *order* lifecycle and drives crash
recovery. `signal_events` records signals. But the **decision** — which deployment,
which strategy version, which parameter set, which gates passed, why this size — is
reconstructable only from unstructured log lines. Position state transitions are
in-place mutations of a mutable ORM row (`stop_price`, `high_water_premium`,
`ratchet_hw` are overwritten), so the history of a stop's movement is not recoverable.
`replay.py` exists as a *provider*, so market data can be replayed, but engine
decisions cannot be re-derived and compared.

**Why it matters.** With client capital, "why did the system do this?" must be
answerable from data, not from grep. It is also the only way to verify C6's
backtest/live parity, and the substrate any enterprise audit or dispute needs.

**Recommended solution.** Append-only `decision_events` (deployment_id,
strategy_version, instrument, bar_ts, decision, params_hash, gate_results,
inputs_hash). Keep positions as the current-state projection over it. This is a small
table with a large payoff and pairs naturally with C1's `deployment_id`.

**Effort today:** ~1–2 weeks. **After:** 1–2 months, and the history before it is lost
either way. **Blocks development:** No.

## H7 — Broker/venue failure semantics are inherited rather than declared

**Problem.** `LiveBroker` overrides ~15 of `PaperBroker`'s methods; the rest are
inherited *as simulation*. `mark()`, `reinforce_position()`, `book_partial_close()`
and `snapshot()` run the simulator's arithmetic in the live path. That happens to be
correct today because those operations are pure bookkeeping — but it is correct **by
coincidence of the current method list**, not by contract. Nothing fails if a future
`PaperBroker` method that *should* have hit the wire is left uninherited-and-unnoticed.

**Why it matters.** This is the same shape as the "unconsumed mechanism" defect class
this codebase has already been bitten by three times: something looks wired and isn't.
With four brokers it becomes four independent chances to inherit a simulation into a
real-money path.

**Recommended solution.** Falls out of C2's `BrokerCore` + `Broker` Protocol split:
every method is either explicitly *bookkeeping* (shared) or explicitly *venue*
(abstract, must be implemented). Add a test that asserts no venue-facing method is
inherited from the paper implementation.

**Effort today:** included in C2. **After:** included in C2. **Blocks development:** No.

---

# MEDIUM (defer past v1)

- **M1 — Watchlist single-membership.** `watchlist_membership.instrument_key` as PK
  encodes "one instrument, one strategy" structurally. Correct under today's conflict
  rules, obsolete the moment C1 lands; convert to `(deployment_id, instrument_key)`.
- **M2 — `backtest_results` wide-column schema.** ~120 columns growing by additive
  ALTER. Fine now; move metrics to a versioned JSON payload + a few indexed columns
  before external developers publish results.
- **M3 — Ledger sub-app duplication.** `app/ledger` (backend) and `src/ledger`
  (frontend) are a well-isolated second application. The isolation is a feature; the
  duplicated idioms (own store, own domain layer, own keymap) are a maintenance cost
  once external developers arrive.
- **M4 — Notification coupling.** `self.notifier` is called from inside decision code
  in the runner. Fine at one channel; becomes a fan-out problem with customers.
  Emit events (H6) and let a notifier subscribe.
- **M5 — Provider factory is a process-wide singleton.** Correct for one account;
  blocks per-tenant data providers and per-deployment replay. Follows C1 naturally.

# LOW

- **L1 —** `/api/portfolio/*` is split across `routes.py` and `portfolio_routes.py`
  with different ownership conventions; consolidate when H3 versioning happens.
- **L2 —** `strategies/*.pine` (six Pine files) are the source of truth for strategy
  *intent* but have no mechanical relationship to the Python implementations. Phase 3
  should decide whether Pine is an import format or documentation.

---

# Answers to the specific questions asked

**3. Can one execution engine support visual + Python + marketplace + generated
strategies?** *Not as designed.* The registry and the sandboxed generated-strategy path
(AST allow-list, no-builtins exec, `register()` seam) are genuinely good and prove the
loading mechanism works. The blocker is the **contract**, not the loader: a strategy
can only say *when to be long or short*. It cannot carry parameters (non-default
strategies are invoked with none at all), cannot define exits, cannot define sizing,
and has no version. Four sources of strategy that all reduce to the same four boolean
columns and then run the platform's single hard-coded risk model are four skins on one
strategy. Fix C3 + C4 and the answer becomes yes.

**4. Would adding Dhan/Fyers/Angel/IB require modifying existing execution logic?**
*Yes, in three places.* (a) There is no `Broker` interface — a new broker must subclass
`PaperBroker` and inherit simulator methods. (b) Protective-stop semantics are Kite's
(GTT + SL-M) and are called directly, not through the `OrderClient` Protocol, which
covers only place/status/cancel. (c) Kite vocabulary is in the domain model
(`Position.gtt_trigger_id`) and in engine-level helpers (`product_for_segment` →
`MIS`/`NRML`). **The missing abstraction is a two-level split: a domain `Broker`
Protocol over shared ledger bookkeeping, and an `ExecutionVenue` Protocol that owns
order placement, protective orders, funds, margin probes and tick sizes.**

**5. Is there exactly one source of truth per concern?** Mostly yes, with two real
exceptions. Clean: watchlists (`watchlists` + membership), journal (`ledger.db`, well
isolated), research (`research.db`). Not clean: **portfolio/positions/capital**, where
the persisted book, the broker's long-lived session, `runner.state`,
`runner.position_ticks` and the real Zerodha account are five views with reconciliation
logic gluing them (this is why re-anchoring and orphan reconciliation exist, and both
have produced incidents); and **strategy lifecycle**, split across
`strategy_lifecycle`, `generated_strategies`, `research_promotion_candidate`, the
in-memory registry, `instrument_state.strategy_key` and `watchlists.strategy_key` — six
places, no single authority, no version.

**7. Determinism / recovery / replay.** Order-level recovery is genuinely strong
(`order_journal` + `recover_journal` before the loops start + the instance flock).
Decision-level determinism is not present: there is no decision log (H6), positions are
mutated in place so stop history is unrecoverable, and the two lanes share one DB
session under one `asyncio.Lock`, which is correct-by-serialization but is also the
reason concurrency cannot grow beyond one process.

**10. Extensibility verdict.** New datasets: fine (the `MarketDataProvider` ABC is the
best abstraction in the codebase). New strategy types: blocked by C3/C4. New brokers:
blocked by C2. New deployment targets / thousands of deployments: blocked by C1/C5/C7.
Marketplace: blocked by C4/C6. Permissions & enterprise licensing: no seam exists at
all (H3) — there is no principal in the system.

---

# Final verdict

| Dimension | Score | One-line justification |
|---|---:|---|
| **Architecture** | **5/10** | Excellent seams where they exist (providers, ledger/research isolation, strategy registry, order journal); the central identity model is single-tenant, single-book, single-process. |
| **Maintainability** | **6/10** | Unusually strong tests (1,618 backend + 143 frontend) and unusually honest docs offset a 2,433-line god object and a 1,005-line route module. |
| **Enterprise Readiness** | **2/10** | No tenancy, no principal, no roles, one shared bearer token, one SQLite file behind an exclusive process lock. |
| **Technical Debt** | **6/10** | *(higher = less debt)* Debt is concentrated and named rather than diffuse; almost all of it is structural, not rot. |
| **Extensibility** | **4/10** | Data providers extend cleanly; strategies, brokers, segments and deployments each require editing shared real-money code. |
| **Operational Robustness** | **8/10** | The strongest dimension: fail-closed gates, instance lock, readiness probe that can say no, order journal recovery, circuit breakers, reconciliation, retention. Capped only by single-process/single-file storage. |

**Recommended sequence before Phase 3 begins:**

1. **C7 (Alembic baseline)** — 1 week. Nothing else can migrate without it.
2. **C1 (Deployment entity + `deployment_id`)** — 2 weeks. Everything else attaches here.
3. **C4 (strategy versioning + fail-closed resolution)** — 1 week. Cheapest critical, and
   it is a live correctness issue today, not only a Phase 13 issue.
4. **C5 (scoped configuration)** — 2 weeks. Completes the Deployment concept.
5. **C3 (StrategySpec)** — 3–4 weeks. *This is Phase 3*, now on solid ground.
6. **H3 (`/api/v1` + Principal)** — 1 week, before routes multiply.
7. **C2 (Broker/Venue split)** — 3 weeks. *This is Phase 9*; do it before Phase 5/6 add
   surface area.
8. **C6 (shared decision kernel + parity test)** — 3 weeks. Gate for Phase 13.

Roughly **4 months of structural work** now, against an estimated **12–18 months** of
equivalent change after Phases 3/5/6/9/13 ship — most of it executed against live
customer capital and published performance claims.
