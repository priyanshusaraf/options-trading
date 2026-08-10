# Strategy OS — current-state handoff, 2026-08-10

**Audience:** an incoming technical/product lead who has not read the chat history.
**Method:** reconstructed from code, migrations, tests, git and a live health probe. Docs were
audited *against* that reconstruction, not trusted. Where code and docs disagree, code wins and
the discrepancy is recorded. Anything not verified is marked **UNVERIFIED**.

Every material claim below cites a file, a migration, a test, or a command result.

---

## 0. Read this first: there are THREE different states of this system

This is the single most confusing thing about the repository right now, and it has already misled
one automated audit during the preparation of this document.

| | Location | Branch | Commit | Date |
|---|---|---|---|---|
| **Main checkout** | `~/dev/options-trading` | `feat/exec-completeness` | `58436bb` | 2026-08-09 |
| **Line of record** | `~/dev/options-trading/.claude/worktrees/codex-execution-foundation` | `codex/execution-foundation` | `e67ab84` | 2026-08-10 |
| **Production (VPS)** | DO Bangalore droplet | `feat/exec-completeness` | `6bb7e97` | **2026-08-02** |

`git worktree list` confirms all three. **All current work is in the worktree**, on
`codex/execution-foundation`, pushed to origin. If you `cd ~/dev/options-trading` and start
reading, you are looking at a week-old branch.

**Production is 185 commits and 8 days behind the line of record.** Measured, not inferred:

```
$ curl -s https://paper-trader.taile25969.ts.net/api/health
build.commit = 6bb7e97 · branch = feat/exec-completeness · deployed_at = 2026-08-02T02:12:55Z
uptime = 8.5 days · checks: database✓ engine_running✓ risk_lane✓ signal_lane✓ provider_auth✓ feed_quality✓

$ git rev-list --count 6bb7e97..HEAD   →  185
```

The live box is healthy and trading. Nothing from the last 8 days of work — including every
broker, tenancy and credential change described below — is deployed. That is deliberate: this
work sits behind owner gate #2 (material changes to live execution semantics).

---

## 1. Executive state

**What this actually is today:** a single-owner, single-process autonomous options/intraday-equity
trading engine that has been substantially rebuilt underneath into a Strategy-OS-shaped platform.
The *platform machinery* — typed immutable IR, content-addressed graph versions, execution
authority, provider capability model, broker registry, research evidence — is real and unusually
well-tested. The *product* — multiple users, multiple strategies, multiple brokers actually
placing orders — is not.

**Real, working, in production today:**
- A live-money engine on Zerodha Kite: options (long premium) and intraday equity, arm-gated,
  with durable entry lifecycle, protective stops, reconciliation and restart recovery.
- Paisa-exact net-of-charges accounting (`scripts/dryrun.py 700` → `LEDGER OK`).
- A backtest sweep across instruments × intervals with a content-addressed result cache.
- A research plane with walk-forward, PBO/CSCV, deflated Sharpe, immutable evidence and review
  snapshots — flag-gated off by default (`research_enabled=False`, `config.py:409`).
- A 28k-line operator frontend (cockpit, backtests, graph canvas, ~10k-line journal), used from
  a phone over Tailscale.

**Partially real:**
- **Multi-broker.** Three data adapters (Kite, Upstox, Dhan) pass one conformance contract; a
  broker registry exists; `make_broker` no longer names a broker. But only Kite has ever placed
  a real order, and there is no way to *authenticate* a non-data connection through the API.
- **The IR.** One graph exists (`app/ir/strategies/expanding_z.py`), from 15 components hardcoded
  in one Python module. Authoritative in **paper only**; live IR authority is owner gate #1 and
  deliberately absent.
- **Tenancy.** `broker_connections` (migration 0015) and `execution_intents.owner_id` (0016) are
  owner-scoped and genuinely well built. **Nothing else is.**

**Still mostly design:**
- Authentication, users, per-user isolation. Monte Carlo, component ablation, cross-instrument
  nodes, node authoring by a user, background job execution, resumability.

**What the next release can credibly contain:** a hardened single-owner product with a second
data provider selectable, the current live path unchanged, and the documentation telling the
truth. **It cannot credibly contain multiple users.** See §15.

---

## 2. Current architecture

One Python process. One SQLite file. One SPA served by that same process.

```
                    ┌─────────────────────────── uvicorn :8090 (ONE process) ──────────────────────────┐
  Kite / Upstox     │                                                                                  │
  / Dhan  ─────────►│  providers/          engine/                    api/          ws/                │
  (HTTP, throttled) │  ┌──────────────┐    ┌────────────────────┐    75 routes     one hub,            │
                    │  │MarketData    │───►│ Runner             │    12 modules    broadcasts to ALL   │
                    │  │Provider      │    │  ├ signal loop     │◄───┤             connected clients   │
                    │  │(capabilities)│    │  ├ risk loop       │    │                                 │
                    │  └──────────────┘    │  └ manual-detect   │    │                                 │
                    │  ┌──────────────┐    │                    │    │                                 │
                    │  │Connection    │───►│ broker_factory ────┼────┼──► PaperBroker | LiveBroker     │
                    │  │(broker,scope,│    │  (live gate)       │    │        │                        │
                    │  │ caps, creds) │    │                    │    │        ▼                        │
                    │  └──────────────┘    └────────────────────┘    │   ExecutionVenue ──► KiteVenue  │
                    │         │                                      │   (neutral verbs)   DhanVenue   │
                    │         ▼                                      │                                 │
                    │  connection_store ──► credential_vault (AES-256-GCM, key from env, never a row)  │
                    │                                                                                  │
                    │  ir/          research/         backtest/        ledger/       SPA (dist/)        │
                    │  IR language  evidence, WF,     sweep, cache,    journal       React, no router   │
                    │  1 graph      PBO, DSR          dataset store    (own db)                        │
                    └──────────────────────────────────────────────────────────────────────────────────┘
                                        │                    │                  │
                                  paper_trader.db      research.db         ledger.db
                                  (37 tables, WAL, synchronous=NORMAL)
```

**Three asyncio lanes** start at app startup (`app/main.py:119-129`): `run_signal_loop`,
`run_risk_loop`, `run_manual_detect_loop`. No Celery, no queue, no worker process, no scheduler.
The order-journal replay runs *before* the loops (`main.py:115`) so a crash mid-flight is
recoverable.

**Only the risk lane is fatal to readiness** (`app/engine/readiness.py`) — it manages open money.
A stalled signal lane is `degraded`, because it legitimately goes quiet overnight.

---

## 3. Repository map

```
paper-trader/
├── backend/            171 python modules, 329 test files
│   ├── app/
│   │   ├── api/        75 routes across 12 modules; principal.py is the (no-op) authz seam
│   │   ├── core/       config, execution_binding (GRANTS), execution_book, credential_vault,
│   │   │               paper_authority, instance_lock, runtime_config
│   │   ├── db/         models.py (37 tables), planes.py (ADR 0015 plane map), session.py
│   │   ├── engine/     12,370 lines. runner.py (3,079) + live_broker.py (2,221) dominate.
│   │   │               venue.py / kite_venue.py / dhan_venue.py = the wire boundary
│   │   ├── ir/         3,489 lines. schema, validate, resolve, runtime, hashing, edit, library
│   │   ├── backtest/   sweep, engine, premium, cache, dataset_store, identity
│   │   ├── providers/  3,676 lines. kite, upstox, dhan, mock, replay + connection/registry
│   │   ├── options/    picker.py, pricing.py (Black-Scholes, implied vol)
│   │   └── ledger/     the journal — own DB, own lane, never touches positions/trades
│   ├── research/       5,893 lines. orchestrator, pipeline, stats, strategy/builder
│   ├── migrations/     17 revisions, head 0016
│   ├── tests/          282 files       research_tests/  47 files
│   └── scripts/        deploy-adjacent + 7 mutation-sweep harnesses
├── frontend/           ~28,281 lines TS/TSX. React 18 + Vite. No router.
├── docs/               126 markdown files — see §14, several are actively misleading
└── scripts/deploy.sh   678 lines, ~12 guards. The most valuable ops asset in the repo.
```

---

## 4. Strategy / research system

### 4.1 There is one IR language but **three** strategy representations

| # | Representation | Where | Executes |
|---|---|---|---|
| 1 | Hand-written Python `Strategy` subclass | `app/strategy/registry/*.py` | paper **and live**, authoritative |
| 2 | Generated (blocks → emitted Python) | `research/strategy/builder/`, `generated_strategies` | paper and live, authoritative |
| 3 | **Component IR graph** | `app/ir/`, `graph_versions` | **paper only**, via a verified `IrPaperDeployment` |

Authority is decided at one line — `app/core/execution_binding.py:74-84`:

```python
GRANTS = frozenset({
    (SOURCE_HANDWRITTEN, PAPER, AUTHORITATIVE), (SOURCE_HANDWRITTEN, LIVE, AUTHORITATIVE),
    (SOURCE_GENERATED,   PAPER, AUTHORITATIVE), (SOURCE_GENERATED,   LIVE, AUTHORITATIVE),
    (SOURCE_IR_GRAPH,    PAPER, AUTHORITATIVE),   # owner-granted 2026-08-07
})
```

`(ir_graph, live, authoritative)` is **absent by design** and is owner gate #1.

**What actually trades live is hand-written Python.** The `Strategy` contract
(`app/strategy/registry/base.py:21 CANONICAL_COLUMNS`), not the IR, is the platform's real
lingua franca; `app/strategy/ir_adapter.py::IRGraphStrategy` converts a resolved graph *into*
that contract.

### 4.2 The IR's real size

- **One graph exists**: `app/ir/strategies/expanding_z.py` — `GRAPH` at `:230`, all 14 kernel
  `IMPLEMENTATIONS` at `:438`, `LIBRARY` at `:480`.
- **15 components, 14 implementations**, all from that one module. `app/ir/library.py:55`:
  `CONTRIBUTORS = (expanding_z,)`. Not a plugin system — no discovery, no entry points.
- **Components are not persisted at all.** No component table. Only whole *graphs* persist, as
  immutable content-addressed artefacts.
- **A user cannot create a node type without a commit.**

### 4.3 What is genuinely strong (do not rebuild)

- **Immutability enforced three ways** on `graph_versions`: an ORM `before_insert` listener that
  re-derives the content address (`models.py:992`), plus SQLite DDL triggers
  `graph_versions_refuse_update` / `_refuse_delete` (`models.py:1006-1023`), plus CHECK
  constraints pinning `json_extract(artifact_json,'$.identifier')` to the column.
- **One edit boundary** — `app/ir/edit.py:431 apply_batch()`, with an **AST guard** that parses
  the route module and asserts no other mutator is ever called
  (`tests/test_ir_edit_routes.py:912`).
- **Two independent optimistic-concurrency axes** — `base_revision` (semantic) and
  `base_presentation_revision`, returning distinct 409 codes. Presentation state is provably
  outside identity (F13).
- **Undo/redo is client-driven via inverse-operation receipts** (`edit.py:105`), not a
  server-side history table. Deliberate design, not an omission.
- IR invariants under test: F1–F13 conformance (51 tests), C1–C15 resolver (45), C8–C11 runtime
  (18), C13 provenance-blindness by AST, F14 result binding (19), platform-library identity (14).

### 4.4 Research plane status — evidence-backed

| Capability | Status |
|---|---|
| Graph editing | **IMPLEMENTED** |
| Component/node authoring | **NOT IMPLEMENTED** (requires a Python commit) |
| Backtests, OOS/walk-forward, PBO/CSCV | **IMPLEMENTED** |
| Evidence/findings, comparison, review snapshots, run history | **IMPLEMENTED** |
| Parameter optimization | **IMPLEMENTED for legacy strategies; STRUCTURALLY IMPOSSIBLE for IR graphs** |
| Monte Carlo | **NOT IMPLEMENTED** (zero hits repo-wide) |
| Component ablation | **NOT IMPLEMENTED** (zero hits repo-wide) |
| Multi-instrument research *as composition* | **NOT IMPLEMENTED** (independent runs + a beauty contest) |
| Background jobs | **NOT IMPLEMENTED** — the graph-experiment endpoint runs a full multi-instrument walk-forward **inside the HTTP request** (`ir_experiment_routes.py:319-360`) |
| Resumability | **NOT IMPLEMENTED** — `operations.py:299-311` marks an interrupted operation `failed` and starts fresh |
| Research "cache" | **PARTIAL and weaker than it reads** — `research/data/store.py:62 materialize()` refetches every time; only the *spec* is deduped by hash, the run always re-executes |

### 4.5 The most important unrecorded finding: **deflation cannot engage for IR graphs**

The 2026-08-01 deflation fix is real for the legacy pipeline (`research/pipeline/optimize.py:59`
computes `var_sr`; `run.py:350` passes it) and `research_tests/test_deflation_engages.py` passes
(12 tests, verified). **But it is structurally inert on the IR path:**

```
research/strategy/spec.py:36   _DEFINITIONS = {"trend_impulse_v3": …, "expanding_z_v4": …}
                               → param_space('ir.expanding_z') == {}    (verified live)
optimize.py:127                candidates = [...] or [{}]   → exactly one candidate
optimize.py:109                len(candidates) < 2 → perf_matrix empty
run.py:342                     gates["pbo"] = {"passed": False}   (fails closed)
```

And an IR graph **refuses parameters outright** — `ir_adapter.py:198-205` raises if `compute()`
is given any, because parameters bind at resolution (F14). So a graph experiment either runs with
`var_sr = 0.0` (the DSR degrades to a PSR against zero — exactly the bug that was fixed) or fails
the PBO gate closed and always archives.

**Whatever the IR research plane reports today is not deflated evidence.** This is recorded
nowhere in the docs.

### 4.6 Generation-2 IR structure search is built and called by nothing

`research/strategy/builder/{propose,ir_search,ir_evaluate}.py` are complete, documented and
tested — and have **no production caller**. The nightly generator still uses the old
block/Python-emitting builder. This is the codebase's documented defining defect
(the "unconsumed mechanism"), live again.

---

## 5. Backtest performance

**Measured today** with the repo's own harness (`scripts/sweep_benchmark.py`, machine loaded):

```
5,000 bars/cell, 6 repeats — p50 ms
identity 11.49 · frame 8.19 · signals 2.47 · simulate 25.06 · premium 33.10 · TOTAL 80.31

  100×5:    500 cells  compute    40s  I/O floor    200s  cold 0.07h
 1000×5:  5,000 cells  compute   402s  I/O floor  2,000s  cold 0.67h
10000×5: 50,000 cells  compute 4,016s  I/O floor 20,000s  cold 6.67h
```

This reproduces the recorded 80.32 ms/cell in
`docs/engineering/reference/backend-hardening-2026-08-08.md` §13.

### The headline: **the fast path exists and nothing can reach it**

The content-addressed dataset store, the pinned-run path (zero provider reads, bytes verified
five ways) and the multiprocess fan-out (measured **2.9–3.2×**) are all built, tested and
measured. But `SweepRequest` (`app/api/backtest_routes.py:57-66`) exposes **neither
`pinned_datasets` nor `workers`**. The only callers of `resolve_pinned_datasets` in the entire
repo are three test files.

Every sweep a user can actually start is **serial** and pays a full provider read per dataset
(`sweep.py:670`, throttled at 0.40 s — `kite.py:45`). `sweep.py:719-722` says it outright:
*"the sweep never reads the store back, so a refresh still costs its reads."*

### Why a "small parameter edit" is not cheap — two independent reasons

1. **Acquisition precedes the cache check.** `sweep.py:382` (`_prepare_dataset`) runs before
   `sweep.py:939` (`_reusable_values`). So the provider read, the 11.5 ms/cell
   `ordered_dataset_address` (Python `struct.pack` over every bar) and the 8.2 ms frame build are
   paid regardless of a cache hit.
2. **The cache key binds the source bytes of 11 modules.** `identity.py:209-228` +
   `transitive_module_source_digest` (`identity.py:167-207`) re-reads those files per cell
   (measured 0.379 ms/cell). **A comment fix in `metrics.py` invalidates every cached result for
   every instrument, interval and strategy.** Intentional (a stale-history bug shipped before,
   `cache.py:22-27`) and expensive.

Also: during market hours a new bar changes the dataset address → every execution address
changes → **every cell is cold even with zero edits**.

### Top provable bottlenecks

1. The unconditional provider read (0.40 s/dataset) — dominates every cold tier.
2. `simulate_premium`'s per-bar Python loop (`premium.py:239-240`) — 33.1 ms/cell, **41%**.
3. `run_trades`'s per-bar Python loop (`engine.py:320-321`) — 25.1 ms/cell, **31%**. `to_dict`
   and `ist_epoch` are paid twice on the identical frame.
4. Per-cell re-addressing of unchanged data (11.5 ms + 11 file reads).
5. `/api/backtest/results` (`backtest_routes.py:177`) hydrates **every row of a run** including
   four JSON blobs, then filters in Python — the same shape as the 2026-07-23 OOM outage, and the
   UI polls it *while a sweep runs*.

### Highest-leverage safe improvements (NOT implemented — owner's call)

1. **Expose `pinned_datasets` + `workers` on `SweepRequest`.** Near-zero cost, code exists,
   removes the I/O floor from reruns and unlocks the measured 2.9–3.2×. **Risk: raising workers
   on the 1 GB VPS that also runs live money is the 2026-07-23 OOM again** — gate by host.
2. Hoist `to_dict`/`ist_epoch` to once per (dataset, strategy) — ~30% of the two hot loops. Must
   be proven bit-identical; note the parity gate was once **vacuous** because `MockProvider`
   rounds to 2 dp — use `FullPrecisionMockProvider`.
3. Memoise the module digest per process, keyed on `(path, mtime_ns, size)`, failing *closed*.
4. Skip the premium replay when nothing consumes it — but this is a **cache-identity change**
   (bump `SCHEMA_VERSION`), not a perf tweak.
5. Index the reuse predicate; paginate `/api/backtest/results` in SQL.

**A language rewrite is not supported by the profile.** `docs/superpowers/specs/2026-08-10-full-universe-backtest-design.md`
§6: infinitely fast compute saves 17% of a cold run, and `bs_price` is already ~5% after the
`ndtr` fix (which was **232× faster and bit-identical** over 600,010 samples).

---

## 6. Execution and risk

### 6.1 Order lifecycle (live)

```
signal (completed candle only)
  → binding resolved + re-checked at point of use  (execution_binding.py:161 strategy_for_execution)
  → instrument/product resolution                  (venue.py tenor/protective-kind, neutral)
  → sizing against REAL broker margin              (order_margin probe; fails CLOSED to ₹0)
  → risk gates                                     (arm, daily-loss halt, gap halt, slots, cooldown)
  → ExecutionIntent persisted BEFORE submit        (execution_lifecycle.py create_intent)
  → execute_order: place ONCE, then poll           (order_executor.py — never retries a place)
  → protective stop (RESTING_STOP | SERVER_TRIGGER) via ExecutionVenue
  → fill booked at the REAL price; charges applied; ledger updated
  → restart: recover_journal replays WORKING rows before the loops start
```

**Never assumes a fill.** A poll TIMEOUT returns `TIMEOUT`, not `FILLED`
(`order_executor.py` docstring). A read failure is never reported as "no fill".

**Duplicate prevention:** `_inflight` map per tradingsymbol; a timed-out order is
cancelled/awaited before a new one is sent. Guarded by `tests/test_duplicate_order_prevention.py`.

### 6.2 Safety invariants verified in code

| Invariant | Where | State |
|---|---|---|
| ARM gates **entries only, never exits** | `process_entries` vs `mark_and_exit_positions` | ✅ |
| Ledger reconciles to the paisa | `scripts/dryrun.py 700` → **LEDGER OK** (run today) | ✅ |
| Paper/live books structurally separate, **failing closed to `live`** | `core/execution_book.py:48 resolve_book` — "`paper` must be spelled" | ✅ |
| Live requires 3 conditions + per-session ARM | `broker_factory.py:63 live_execution_enabled` | ✅ |
| Single instance | `core/instance_lock.py:26` advisory `flock` on the DB path | ✅ |
| Authority re-checked at point of use | `execution_binding.py:161` | ✅ |
| No `LiveBroker` under pytest | `broker_factory._refuse_live_broker_under_pytest` | ✅ (fired correctly during this session's work) |

### 6.3 The last 48 hours of execution work (all uncommitted → now committed, **not deployed**)

- **`LiveBroker` no longer speaks Kite.** Protective stops go through `ExecutionVenue`; six
  Kite-only verbs left the broker; raw `orders()`/`gtts()` dumps became normalised rows.
  Verified byte-identical for Kite by an independent execution-safety review, clause by clause.
- **Data provider ≠ execution broker.** `configured_execution_connection` resolves them
  separately; split routing is proven end-to-end (Upstox prices, Kite credential).
- **A broker registry** with one rule: SUPPORTED only if the adapter exists *and* passes
  conformance. `make_broker` no longer names a broker.
- **Durable per-owner connections**, AES-256-GCM, key from environment and never a row.
- **Two independent subagent reviews found four real defects**, including one *inside* the fix
  meant to close another. All fixed:
  - Revoking a connection **did not stop orders** — `_sync_token` discarded a `None` and kept the
    token cached at construction. Three docstrings asserted a refusal that did not exist.
  - The first fix was **inert in production** because `broker_factory` authenticated the wire
    object before constructing the client.
  - A stored connection carried **no tick reader** → the 0.05 grid → the 2026-07-15 naked-stop
    incident, reintroduced on the path the design *prefers*.
  - An explicitly-empty owner id resolved to the real owner (and a test pinned that as intended).

### 6.4 Remaining execution gaps

- **The plain-order verbs** (`place`/`status`/`cancel`/`orders`/`find_fill`) still go direct to
  the client rather than through the venue. Smaller than the protective-stop work was.
- **`deployments` has no `owner_id`** (`app/db/planes.py:63-79` names this).
- **F-1: exits have no durable intent.** Entries do. A kill -9 between an exit submit and the
  fill observation is not covered.
- **F-2: `synchronous=NORMAL` under WAL** (`db/session.py:36`) — a committed money transaction can
  be lost to a *host* failure. Process crashes are covered. ADR 0015 originally claimed this was
  fixed; it never was, and as written it is unimplementable while all three planes share one file.

---

## 7. Asset class and broker/provider matrix

### 7.1 Asset support (traced from code, not docs)

| Asset | Research | Backtest | Paper | Live | Proof |
|---|---|---|---|---|---|
| **Options (long premium)** | ✅ | **PARTIAL** — spot backtest refuses to model a premium path (`engine.py:56-64`); the synthetic-premium path (`premium.py`, BS on realised vol) is off the hot path | ✅ | ✅ **primary live path** | `options/picker.py`, `live_broker.py:1142` |
| **Intraday equity (MIS)** | ✅ | PARTIAL — sizes one unleveraged position, not MIS margin | ✅ | ✅ **trades real money today** | `equity_entry.py`, `live_broker.py:1246` |
| **Cash/delivery equity (CNC)** | ✅ | ✅ primary backtest instrument | ❌ | ❌ — `dhan_venue.py:47` "CNC is delivery equity, **which this system does not trade**" | `kite_venue.py:32-34` maps only MIS/NRML |
| **Futures** | ✅ | ✅ | ✅ but **FLAGGED OFF** (`index_futures_enabled=False`) | ❌ **and dangerously so** — `LiveBroker` does not implement `open_futures_position`; pinned in `KNOWN_UNIMPLEMENTED_VENUE_METHODS` (`broker_protocol.py:190-202`) with the note that enabling it *"would book a simulated position with no order behind it"* | |
| **MTF / funded** | ❌ | ❌ | ❌ | ❌ — `mtf_enabled` (`config.py:253`) is **read by nothing**. A correct carry model with no candidate generator | `models.py:401-412` |
| **Short selling** | ✅ | ✅ | ✅ equity | ✅ intraday equity only; **options are strictly long-premium** | `charges.py:93-99`, `live_broker.py:1598-1604` |
| **Overnight** | — | — | ✅ options | ✅ options; **force-flattened** for MIS equity and index futures | `runner.py:2113-2140` |

⚠️ **`intraday_enabled` defaults `False` in code** (`config.py:340`) and is `True` only via a
`runtime_config` DB row. **The segment carrying real money today is the one whose code default
says it is disabled.** A DB restore that loses overrides silently stops live intraday trading.

### 7.2 Broker / provider matrix

| Broker | Data | Execution | Auth | Products | Test coverage | Usable? |
|---|---|---|---|---|---|---|
| **Kite (Zerodha)** | ✅ full (history, quotes, chain, futures, account, margin) | ✅ **the only broker that has ever placed a real order** | daily OAuth (~06:00 IST expiry; headless login violates ToS) | options, MIS equity | conformance + MCX case + venue boundary | **production** |
| **Upstox** | ✅ history + quotes only | ❌ declares no execution | daily OAuth | — | conformance case + 13 adapter tests | **data only, not selected in production** |
| **Dhan** | ✅ history + quotes only | ✅ venue built & registered, **never used against the real API** | long-lived token **+ client_id** | intraday equity only — **no GTT equivalent, so no options** | conformance + 24 adapter + 27 venue tests, 13/13 mutations | **experimental** |
| angelone, fyers, fivepaisa, icici, kotak, groww | ❌ | ❌ | — | — | registry row only | **PLANNED** — refused at selection |

**Dhan's capability gap is stated, not papered over:** it has `STOP_LOSS_MARKET` (a resting stop)
but no standalone GTT; super orders bundle entry+stop+target and cannot attach to an open
position. `DhanVenue` declares `RESTING_STOP` only and **refuses `SERVER_TRIGGER` on every verb**
rather than substituting — the two have different ids, margin and reconciliation, and the broker
branches on the difference.

### 7.3 Provider/broker separation — does the architecture support the intended model?

**Mostly yes, and this is the strongest recent work.**

- ✅ Separate protocols: `providers/base.py::MarketDataProvider` vs `engine/venue.py::ExecutionVenue`.
- ✅ A `Connection` carries broker, scope, capabilities, late-bound credential, tick source.
- ✅ Capability declarations are explicit (19 capabilities, `providers/capabilities.py`) and held
  to a two-tier conformance contract that **fails an adapter which lies**.
- ✅ Canonical instrument identity is owned by Strategy OS; each adapter maps onto it and is
  forbidden from reading another provider's symbology.
- ✅ Split routing proven: `PT_PROVIDER=upstox` + `PT_EXECUTION_PROVIDER=kite`, resolved by the
  composition root, tested end-to-end.
- ❌ **The blocker: there is no way to authenticate a non-data connection.** `routes.py:147,158`
  reach `_runner(request).provider` — the *data* provider — for both `login_url` and
  `complete_session`. Under a split config, "Connect Kite" cannot reach the connection that
  places the orders. **The split config is usable only for a same-day process start and must not
  be set on the live box.**

---

## 8. Portfolio / domain model

```
Deployment (1) ──< Position ──< Trade          money plane, NO owner_id  ⚠
     │                                          (deployment_id is the only scoping)
     └──< ExecutionIntent ──< ExecutionOrderEvent    owner_id ✅ (0016), broker ✅, connection_scope ✅
BrokerConnection    owner_id ✅ (0015), (owner_id, scope) unique, credential encrypted
Project ──< GraphArtifact ──< GraphVersion (immutable, content-addressed)   NO owner_id ⚠
              └──< IrGraphLayout (presentation, separately revisioned, never hashed)
Project ──< ProjectReviewNote / SavedView / Snapshot                        NO owner_id ⚠
ExperimentRun ──< Finding (research.db, separate engine)                    NO owner_id ⚠
Watchlist ──< WatchlistMembership   ·   BacktestRun ──< BacktestResult      NO owner_id ⚠
```

**Three planes** (ADR 0015, `app/db/planes.py`, enforced by `tests/test_db_planes.py`):
money 15 tables · user 17 · market 5. Every table must be assigned or the build fails. **No new
cross-plane foreign key** is permitted — 7 pre-existing crossings are enumerated and ratcheted.

**Against the intended frontend direction** (global Home, multiple strategy workspaces, global
portfolio, cloning/marketplace): the domain model supports *multiple graphs per project*
cleanly, and `graph_artifacts.identifier` being a **global** primary key is the main contract
change you will need for cloning/sharing. Everything else needs an owner column first.

---

## 9. Frontend status

**Partially mature, and lopsided — not a shell.** ~28,281 lines, 22 test files. It genuinely
supports several V1 operator flows today and runs in production on a phone over Tailscale.

- React 18 + TypeScript 5.5 + Vite 5. Served **by FastAPI itself** in production
  (`PT_SERVE_FRONTEND`/`PT_FRONTEND_DIST`, `main.py:442-460`). Single 803 KB bundle, no splitting.
- **Twelve views, and no router.** Navigation is `useState('watchlist')` (`App.tsx:48`). No URL
  per view, no deep links, no back button, nothing shareable.
- **Auth is a build-time constant** — `VITE_PT_TOKEN` compiled into the bundle (`api.ts:1`),
  passed on the WebSocket as a **query parameter**. No login screen, no session, no rotation.
- Three coexisting design systems: bespoke Tailwind classes, shadcn/ui (11 primitives), and the
  ~10k-line journal with its own 5,000 lines of CSS held apart by a **custom 52-line PostCSS
  selector-rewriting plugin**.
- Graph canvas is real (drag, nudge, layout persistence, conflict handling) but **hardcoded to
  one graph and one project id** (`GraphView.tsx:62-63`). No picker.
- Research UI is large (1,271-line evidence panel) but hidden unless `research_enabled`.

**Verified today:** `npm run typecheck` → exit 0. `vitest run` → **223 tests passed, 22 files,
1.86s**.

⚠️ **Frontend green does not mean frontend works.** Vitest runs in `environment: 'node'` with
**no DOM** (`vitest.config.ts:16`); there is not a single `.test.tsx` and no Playwright. All 12
views, the WS provider and the entire journal have **zero render coverage**.

**Frontend is owner gate #7** — the owner takes it directly. Backend work stops at the API
boundary.

---

## 10. Data / database / migrations

- **SQLite**, WAL, `synchronous=NORMAL`, `busy_timeout=10000`, `foreign_keys=ON`
  (`db/session.py:33-37`). Three separate DBs: `paper_trader.db` (37 tables), `research.db`,
  `ledger.db`.
- **Migration head `0016`**, verified: `python -m app.db.migrate head` → `0016`. 17 revisions.
- Recent: `0014` execution lifecycle · `0015` `broker_connections` · `0016`
  `execution_intents.owner_id`.
- **Migrations are clean from zero to head** — `tests/test_schema_migrations.py` (22 tests) proves
  a fresh `create_all` and a migrated legacy DB produce the *same shape*, including indexes, and
  that rollbacks do not touch the money record. Downgrades from 0010 on are deliberately
  **rerunnable** (a rolled-back downgrade does not reliably restore dropped objects).
- **Schema debt:** no `owner_id` on ~20 user/money tables; `params_hash` unindexed with no
  composite index for the cache predicate; the pool is 15 connections against a 40-thread worker
  pool (do not raise without reading `backend-hardening-2026-08-08.md` §4.2).
- **ADR 0014**: SQLite stays until *topology* forces Postgres (multi-host workers), not headcount.
  The migration cost is dominated by ~18 SQLite-only `RAISE(ABORT,…)` immutability triggers.

---

## 11. Tests / CI evidence

Run today, from `paper-trader/backend`, with the project's authoritative command:

```
$ .venv/bin/python -m pytest tests research_tests
4,053 passed · 6 skipped · 104 warnings · 241s · EXIT 0

$ .venv/bin/python scripts/dryrun.py 700
RECONCILE cash vs expected: 187,733.06 vs 187,733.06 (diff -0.0000) · LEDGER OK ✓

$ .venv/bin/python scripts/backtest_smoke.py
net<gross where charged : OK ✓ · SWEEP OK ✓

$ .venv/bin/python -m app.db.migrate head        → 0016

frontend: npm run typecheck → exit 0 ; vitest run → 223 passed, 22 files, 1.86s
```

**There is no CI.** No GitHub Actions, no pipeline — `deploy.sh` runs the suite locally and
refuses to ship below `PT_MIN_TESTS` (default 1000).

**Mutation-sweep evidence** (7 harnesses under `backend/scripts/`, each mutates the
implementation and asserts the guard's *own* test reddens):

```
tenancy_mutations.py       24/24 RED     venue_seam_mutations.py    14/14 RED
dhan_venue_mutations.py    13/13 RED     split_routing_mutations.py  8/8  RED
connection_seam_mutations  11/11 RED     durability_posture          5/5  RED
```

⚠️ **A tooling hazard discovered today:** two mutation sweeps run concurrently will restore one's
mutant over the other's baseline **permanently**, and both print `RESTORED byte-identical: True`.
This silently removed credential destruction from `revoke()` during this session. All seven
scripts now take an exclusive `flock`; a second sweep refuses with rc=2 (verified). **Never let a
sweep report `SKIP` — a stale anchor means that behaviour is no longer proven guarded.**

---

## 12. Deployment / infrastructure

**One 1 GB DigitalOcean droplet (Bangalore), one systemd unit, one SQLite file, reachable only
over Tailscale.** App on `127.0.0.1:8090`, HTTPS via `tailscale serve`. **No Docker, no
docker-compose, no Kubernetes, no IaC, no reverse-proxy config in the repo.** The three mentions
of Kubernetes in the tree are all documents saying *don't*.

**Kubernetes is not justified and should not be added.** At this scale the constraint is a 1 GB
box shared with a live-money process, not orchestration.

**`scripts/deploy.sh` (678 lines) is the most valuable operational asset in the repo.** ~12
guards, each citing the specific incident that motivated it: exclude-list integrity (even element
count — an odd count means an `--exclude` lost its pattern), market-hours refusal with the parse
asserted *before* comparison, clean-tree with exit code captured *separately* from output, a
test-count floor and a literal `LEDGER OK` check, SPA built on the Mac (the droplet has OOM'd
twice holding real positions), rollback capture *before* overwrite, `rsync -rlptD` deliberately
**not `-a`** (which stamped Mac uid 501 on remote dirs), remote `pip install` *before* restart,
and a health check requiring commit match + `GET /` 200 (health returned 200 through both July
outages). `scripts/test_deploy_guards.sh` proves the guards can go red.

**⚠️ The things that keep production alive are not in version control:** the systemd unit,
`backup.sh`, the nightly cron, the production `.env`, and `access_token.json` exist **only on
that droplet**. There is **no restore runbook and no tested restore**. Lose the droplet and you
are reconstructing infrastructure from prose.

**Observability is one unstructured `StreamHandler`** (`core/logging.py:21`) → journald. **Zero
metrics** — no Prometheus, no `/metrics`, no OTel. The only thing that can say "no" is
`/api/health`, and it only became a real readiness probe *after* returning 200 through both July
outages.

---

## 13. Security / tenancy

### Verdict: **NOT multi-tenant safe. Not close.**

This is not "has gaps". The tenancy dimension does not exist on any object a user creates, and
the one identity the system models is a **process-global constant**, not a request-derived one.

- `app/api/principal.py:138-153` — `is_allowed()` is `return principal.is_owner`. The `action`
  argument is unused; the `resource` argument is **accepted and explicitly ignored**.
- `Principal.is_owner` is `True` for **both** kinds, so an unauthenticated caller on an
  auth-disabled box is an owner (`principal.py:58-59`).
- `Depends(get_principal)` appears in **one of twelve** route modules, and even there it resolves
  to the no-op above.
- **Auth is fail-open by default**: `api_token: str = ""` (`config.py:442`); `token_ok()` returns
  `True` when empty. With the default, anyone who can reach the port can
  `POST /api/execution/arm`, `POST /api/execution/kill`, `POST /api/positions/manual-open`, and
  `POST /api/settings` (arbitrary `runtime_config` overrides — live sizing, exits,
  `intraday_enabled` — applied immediately via `refresh_params()`).
- **The engine's owner is an env var, not the request's identity.** `live_broker.py:104`:
  `self.owner_id = get_settings().owner_id`. There is no path from an authenticated HTTP request
  to the owner whose credential places the order. Today's tenancy is *one owner per OS process*.
- **No rate limiting anywhere.** No CSRF story (safe today only because no cookie/session exists —
  introducing one makes every POST exposed). `/api/logs` serves the process-wide log buffer with
  no principal. The WS hub broadcasts to **all** connected clients with no filtering.
- `/api/session` is auth-exempt and accepts `?request_token=` from an unauthenticated caller to
  establish the live broker credential (justified for the OAuth redirect; mitigated only by the
  tailnet).

### What IS genuinely good (do not tear out)

`OwnedConnectionStore` and `credential_vault` are correct tenancy work: owner fixed at
construction with no unscoped read in existence; `ConnectionNotFound` deliberately conflates
"missing" and "someone else's"; the late `token_source` re-filters on owner **and** status on
every call so the check cannot go stale; reads bounded at the query; AES-256-GCM with the key
from environment and never a row; missing key is a refusal, never a plaintext fallback.
`tests/test_connection_store.py` has 30 adversarial tests.

### What is required before a second user

1. Real authentication (users, sessions, signup, rotation). `PT_API_TOKEN` is a deployment
   secret, not an identity system.
2. `owner_id` on ~20 tables — `projects`, `graph_artifacts`, `graph_versions`, all layouts,
   review objects, `deployments`, `positions`, `trades`, `backtest_runs/results`, `watchlists`,
   `signal_events`, `equity_snapshots`, `capital_state`, `order_journal`.
3. A request→owner binding so `Principal.id` reaches the store, the engine and every query.
4. A real `is_allowed` that consults `resource`.
5. Owner-scoped realtime (WS hub) and `/api/logs`.
6. Rate limiting; a CSRF story before any cookie.
7. **A fencing lease.** `2026-08-10-multi-user-failure-modes.md` F-5: *"There is no lease, no
   fence, no lock… Two engines on one Kite account double every order. This is currently
   prevented by luck and operator discipline."*
8. HTTP routes for `OwnedConnectionStore` — it currently has **none**, so users cannot create or
   revoke their own broker connections.

---

## 14. Documentation drift

126 markdown files. **Trust `.claude/rules/`, `WS-02-execution.md` and `docs/reports/README.md`
over the narrative docs.**

| Document | Class | Problem |
|---|---|---|
| `docs/product-overview.md` | **STALE-CONFLICTING — worst offender** | Business-facing. Title *"Autonomous Options Trading Platform"*; line 14 *"There is no human in the decision loop"*; lines 392/430 *"single-account and single-process **by design**"* — asserting the V1 blocker as an intentional feature. `CLAUDE.md` explicitly forbids this framing. A correction was designed in `docs/agent-guidance-review/…/06-current-vs-proposed.md:48` and never applied. |
| `docs/CONTINUE.md` | **STALE-CONFLICTING** | Says migration head `0014` (is 0016), names the wrong branch, and claims *"Broker expansion, authentication and tenancy remain deferred"* — false. This is the doc `CLAUDE.md` tells a session to read **first**. |
| `docs/ROADMAP.md` | **STALE-CONFLICTING** | Head `0014`, revision `1e96b52`, *"3,712 tests"* (measured: 4,053 passing / 4,059 collected). Its §1 (500-user target, cost blocker) is still correct. |
| `docs/rfcs/0001-component-ir.md:40` | **STALE — safety-relevant** | *"Nothing in production executes IR graphs."* False since 2026-08-07: `execution_binding.py:80` grants `(ir_graph, paper, authoritative)` and `runner.py:378` loads those adapters in the live process. Fix before it misleads a safety decision. |
| `docs/ARCHITECTURE.md:19`, `engine-internals.md:9` | CURRENT BUT PARTIAL | Lead with *"single-user autonomous trading platform"*, the framing `CLAUDE.md` forbids. |
| `docs/engineering/EXECUTION_PLAN.md` | HISTORICAL | Self-dated 2026-08-03 at a slice that closed a week ago, but `CLAUDE.md` points at it as the live programme. |
| `app/db/planes.py:63-79` | code comment now stale | Says `execution_intents` has no owner; 0016 added one. |
| `paper-trader/CLAUDE.md`, `.claude/rules/*` | **CURRENT + AUTHORITATIVE** | Head pinned at 0016 correctly; owner gates current. |
| `docs/reports/README.md` | **exemplary** | Explicitly marks five reports stale *with the specific false claim named*. The pattern the rest of `docs/` should copy. |

---

## 15. Current blockers, ranked

### Release blockers (cannot ship to any external user)
1. **No authentication and no tenancy.** §13. Not a hardening task — a schema dimension plus an
   identity binding that does not exist.
2. **No tested restore, and the backup script is not in git.** Lose the droplet, lose the
   product. §12.
3. **F-1 exits have no durable intent; F-2 a committed money transaction can be lost to host
   failure.** Unacceptable before holding anyone else's money.
4. **No fencing.** Two engines on one account double every order; prevented today by operator
   discipline.

### Serious, can ship behind a gate
5. **The backtest fast path is unreachable** — iterative reruns pay a full provider read. §5.
6. **Deflation is inert for IR graphs** — the research plane's headline number is not deflated on
   the plane the product is being built on. §4.5.
7. **No auth path for a non-data connection** — the split-broker config cannot be used in
   production. §7.3.
8. **Production is 185 commits behind** and on a different branch. §0.
9. **Frontend has no router and no login** — blocks every multi-user and support workflow. §9.

### Post-V1
10. Live IR authority (owner gate #1) · futures (built, off, and unsafe to enable) · MTF
    (unwired) · Monte Carlo, ablation, cross-instrument nodes · the remaining five brokers ·
    Postgres (ADR 0014's trigger has not fired).

---

## 16. Seven-day sequence to the strongest achievable V1

Framed honestly: **a coherent single-owner V1 this week, with the multi-user foundation started
but not claimed.** Attempting real multi-tenancy in seven days would produce a half-scoped
system that looks multi-user and is not — the worst possible outcome for a product holding
broker credentials.

| # | Item | Why | Files | Acceptance | Live-money? |
|---|---|---|---|---|---|
| 1 | **Fix the lying docs** (½ day) | `CONTINUE.md`/`ROADMAP.md`/`product-overview.md`/RFC §status actively mislead. A new lead reads these first. | `docs/CONTINUE.md`, `ROADMAP.md`, `product-overview.md`, `docs/rfcs/0001:40`, `planes.py:63` | Each states the true head (0016), branch, test count; product-overview reframed as Strategy OS with single-account named as a **gap**, not a design | No |
| 2 | **Backup into git + a restore drill** (½ day) | The only unknown-unknown that ends the company. F-3. | new `scripts/backup.sh`, runbook | `backup.sh` versioned; a restore into a scratch DB proven and the command recorded | No — but touches VPS ⇒ **owner gate #3** |
| 3 | **Expose `pinned_datasets` + `workers` on `SweepRequest`** (1 day) | Turns a built, tested, measured warm path into the product's iteration loop. Largest available latency win, no new algorithm. | `api/backtest_routes.py:57-81`, `backtest/sweep.py` | A rerun with unchanged data makes **zero provider reads** (harness already counts them); bit-identical to serial; workers gated by host so the 1 GB box stays at 1 | No |
| 4 | **Per-connection auth route** (1 day) | Without it the split-broker config cannot be used at all, and multi-broker is the headline. Backend half only — UI is gate #7. | new `api/connection_routes.py`, `providers/connection_store.py` | `POST /api/connections`, `/{id}/login`, `/{id}/session`, `DELETE /{id}` — all owner-scoped through `OwnedConnectionStore`; a Kite connection can be authenticated without touching the data provider | **Yes ⇒ owner approval** |
| 5 | **F-1 durable exit intents** (1½ days) | The path that must never fail is the least durable one. Entries are covered; exits are not. | `engine/execution_lifecycle.py`, `live_broker.py` close paths | A kill -9 between exit submit and fill observation recovers without double-selling; drill recorded | **Yes ⇒ owner approval** |
| 6 | **`owner_id` on `deployments` + the user plane** (1½ days) | The schema half of tenancy, done while it is small. Does *not* claim multi-user. | migration 0017, `models.py`, `planes.py` | Every user/money table has an indexed `owner_id` defaulting to `'owner'`; `test_db_planes.py` extended to assert it; migrations clean zero→head | No (additive, no backfill) |
| 7 | **Paginate `/api/backtest/results` in SQL** (½ day) | Same shape as the 2026-07-23 OOM, and the UI polls it during a sweep. | `api/backtest_routes.py:177` | Response bounded; survivorship counters preserved exactly; measured before/after | No |
| 8 | **Deploy the accumulated work** (½ day) | 185 commits behind. Every fix above is inert until deployed. | `scripts/deploy.sh` | Guards pass; `/api/health` reports the new commit; engine comes up DISARMED | **Yes ⇒ owner approval, gate #3** |

**Deliberately not in the week:** authentication, the frontend rewrite, the remaining five
brokers, live IR authority, Postgres, futures. Each is either an owner gate or larger than the
time available, and shipping half of any of them is worse than shipping none.

---

## 17. Owner decisions required

1. **Deploy the 185-commit backlog** — gate #3. Nothing since 2026-08-02 is live.
2. **F-1 durable exit intents** — changes the live exit path. Gate #2.
3. **Per-connection auth route** — creates a way to authenticate a real-money credential. Gate #2.
4. **`synchronous=FULL` for the money plane** — a global durability/throughput trade (all three
   planes share one file), or the physical plane split instead. Needs the write benchmark re-taken.
5. **Sweep worker count on the live box** — raising it is the 2026-07-23 OOM risk on a 1 GB
   droplet shared with the money path.
6. **Whether to hold other people's broker credentials at all** — regulatory/commercial, gate #6.
   The technical findings do not depend on the answer; the *deadline* for fixing them does.
7. **Live IR authority** `(ir_graph, live, authoritative)` — gate #1, still absent, should stay
   absent until the IR has more than one graph.

Not owner decisions: pagination, indexes, doc fixes, exposing sweep parameters.

---

## 18. Bottom-line assessment

**How close to a real private alpha?** For *one operator* — it is already there and has been
running live for six weeks. For *invited external users* — **not close**, and the gap is not
polish. It is authentication, an owner dimension on ~20 tables, a fencing lease, and a tested
restore. Call it 3–4 weeks of focused work, not one.

**How close to a commercial V1?** Further. Add per-user broker connection management with a UI,
durable exits, an off-box money store, observability, and a support story (which needs routing).
6–10 weeks, and the frontend is an owner-owned dependency on the critical path.

**The single biggest technical risk:** *the system's own defining defect — mechanisms that are
built, correct, tested, and connected to nothing.* It has now appeared in the venue seam, the
dataset store's fast path, the Generation-2 IR search, the MTF carry model, `ExecutionIntent.broker`,
and inside a security fix written to close it, all within one session. Three guards exist for
three of its shapes and it still recurs. **Assume any capability you read about is unwired until
you find the caller.**

**The single biggest product risk:** *the product is being built on the IR plane, and the IR plane
has one graph, no user-authorable nodes, and statistically inert evidence* (§4.5). If the pitch is
"build strategies from nodes and trust the research", all three of those must become true, and
none is a week's work.

**What the owner should focus on this week:** items 1, 2, 3 and 8 above — tell the truth in the
docs, make the backup real, make iteration fast, and get 185 commits of correctness onto the box.
Those four are cheap, none of them is an owner gate except the deploy, and together they convert
a large amount of finished-but-invisible work into something you can demonstrate.

---

*Prepared 2026-08-10 from `codex/execution-foundation` @ `e67ab84`. Every number in this document
was measured on that tree today; none is quoted from memory or from an older document.*
