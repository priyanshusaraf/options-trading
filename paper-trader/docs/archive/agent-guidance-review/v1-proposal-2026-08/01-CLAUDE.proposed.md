# PROPOSED `CLAUDE.md` — not adopted

> This file is a **proposal** for `paper-trader/CLAUDE.md`. It is not loaded and not in force.
> The live file is unchanged. Adoption decision: [`07-adoption-recommendation.md`](07-adoption-recommendation.md).
> Everything below the line is written as it would appear if adopted.

---

# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

**Strategy OS — a visual, node-based platform for building, researching and running trading
strategies.** A trader connects indicators, price action, conditions, instruments, reusable
components, data sources and execution rules on a canvas; researches and backtests the result;
then deploys and monitors it through a supported broker.

The typed immutable IR, the resolver, research lineage, execution authority and provenance are
the **machinery underneath that experience**, not the product pitch. When a decision is between
"correct machinery" and "a graph a trader can actually build", both are required — but the
machinery exists to make the graph trustworthy, never the reverse.

The direction the architecture must keep room for, and does today:

```
NIFTY options + NIFTY futures + India VIX   →   trade SENSEX
Upstox market data   →   Strategy OS graph  →   Zerodha execution
```

Do not hard-code `strategy instrument == observed instrument == execution instrument`, and do
not hard-code `one user == one broker == data + execution + portfolio`. Both are false in the
target product and neither is true in the type system today (see `docs/engineering/reference/architecture-extension-review-2026-08-07.md` §C Drill 2).

**This is not greenfield, and one part of it trades real money.** The platform grew out of a bot
that has been trading Indian markets since 2026-06-29 — first real order 2026-07-13, running
24/7 on a Bangalore VPS, 72 real trades booked as of 2026-08-01, every one `mode='live'`. The
live order path (`LiveBroker`, `KiteOrderClient`, `LiveExecutionKite`) is in production use: it
is not untested and the next order is not its first. **Treat any change touching execution,
sizing, exits or routing as a production change**, and read `docs/PROGRESS.md` §1 before you
assume anything about what is running.

Two processes: FastAPI backend on **:8090**, Vite/React frontend on **:5173**. `:8000` is
deliberately free for an unrelated app in the parent repo.

## Who does what

| Surface | Owner |
|---|---|
| Backend, architecture, runtime, persistence, APIs, tests, migrations, reuse audits, CI, documentation | **Claude** |
| Frontend and UX implementation (`frontend/`) | **ChatGPT / Codex**, normally |

Claude still owns the *contracts* the frontend consumes — payload shapes, capability tables,
error taxonomies — and owns any backend change a frontend needs. Claude does not own the React.
When a cockpit need arises, the deliverable is a frozen backend contract plus fixtures, not a
component.

## Hard invariants

These must hold. Do not weaken any without an explicit instruction naming the invariant.

**Money**

1. **The ledger reconciles to the paisa:** `cash == initial + realized − Σ(open entry_cost)`.
   `scripts/dryrun.py 700` asserts it. Keep it green.
2. **ARM gates entries only — never exits.** The risk loop marks and exits regardless of arm
   state. Not getting out is worse than any other failure. Consequence: the persisted book must
   contain only positions the real account actually holds.
3. **Paper-by-default is structural, not procedural.** `SafePaperKite` hard-disables every
   order/GTT/MF/convert route. Live needs `PT_EXECUTION=live` ∧ `PT_LIVE_ACK=…` ∧
   `PT_PROVIDER=kite`, then a per-session ARM that resets on every process start. The shipped
   `backend/.env` satisfies all three.
4. **Paper and live are separate books.** `app/core/execution_book.py` answers "whose money is
   this" and the answer is the execution mode. Resolution **fails closed to `live`**, the
   strictest book. The other book's open rows are reported loudly, never silently adopted
   (ADR 0012 §6).
5. **Live/backtest parity.** The trailing-stop ratchet and strategy math are shared and
   parity-tested. A change to one lands in both.

**Authority**

6. **A source of logic gains the right to execute at exactly one reviewed line.** `GRANTS` in
   `app/core/execution_binding.py`. Source *and* mode are recomputed at the point of use, so a
   hand-built binding cannot launder itself past the gate (ADR 0012).
7. **`(ir_graph, live, authoritative)` is ABSENT and is the standing owner gate.** IR output may
   not influence live orders, positions, accounting, sizing, routing, exits, reconciliation or
   risk. `(ir_graph, paper, authoritative)` **is** granted, and even that requires a paper-authority
   record whose content address matches at the gate (ADR 0011, L1.3C).
8. **Execution is provenance-blind (C13).** No path under `app/engine/` branches on where a
   component came from. The one place that inspects a source lives in `app/core/`, outside the
   executor perimeter. Broker and connection capability checks must obey the same rule.

**Language**

9. **One of anything.** One IR, one validator, one `resolve()`, one hash, one component library
   (`app/ir/library.py`), one deployment authority, one research ledger. A second broker, a
   second data provider or a second canvas may not introduce a second executable graph schema,
   validator, ledger or execution path.
10. **Graph versions are immutable and content-addressed; presentation state lives beside them.**
    Dragging a node must not change its content address (F13). Results bind to the versions that
    produced them (F14).
11. **Research approval is admission, consumed once at activation — not a lease** (ADR 0013).
    Evidence and decisions are immutable and write-once. Newer contradicting research is an
    operator-visible *read*, never a control. Do not implement an evidence re-read on reload.
12. **The research plane stays isolated.** `research/guards.py` fail-closed; read-only bridges;
    `research/` imports `app.ir` and never the reverse.

**Delivery**

13. **Deploys go through `scripts/deploy.sh`.** Never bare-rsync. A bare rsync has already
    clobbered the production `.env`, and `rsync -a` as root stamped uid 501 onto remote
    directories. Both caused outages.
14. **The live-money rule is not delegable.** Any change affecting execution, routing, sizing,
    exits or live behaviour stops for explicit owner acknowledgement before deployment, even
    with every test green. Development, testing and commits continue; deployment does not.

## Evidence

Assertions are not evidence. Evidence is a reproducible command and its output.

- Tick a checkbox only with verified evidence, in the same commit as the work.
- **A green test can be vacuous.** Prove a guard can go red by suppressing what it guards and
  checking that guard's *own* test fails. Five shapes have been caught here that way, all of
  which looked exactly like passing tests.
- **Never assert deployment state from prose** — not from this file either. `curl /api/health`
  and compare the commit. That mistake once drove a week of decisions.
- Two measurement traps already paid for: a sweep grepping only `^FAILED` misses mutations that
  break a *fixture* (they report as `ERROR`), and `$?` after a pipeline is the **pipe's** exit
  code.

## Commands

Run from `backend/` or `frontend/` — never the repo root. `python` is not on `PATH`; use
`.venv/bin/python`.

**Backend** (`backend/`)
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                          # PT_PROVIDER, KITE_API_KEY, KITE_API_SECRET
.venv/bin/uvicorn app.main:app --port 8090    # --reload for dev
```

**Tests & headless proofs** (`backend/`) — never dump a full run into context.
```bash
.venv/bin/python -m pytest -q --tb=short > /tmp/pt.log 2>&1; grep -E "FAILED|ERROR" /tmp/pt.log
.venv/bin/python -m pytest tests research_tests     # BOTH suites
.venv/bin/python scripts/dryrun.py 700              # engine + ledger reconciliation
.venv/bin/python scripts/backtest_smoke.py          # sweep + net-of-charges invariant
.venv/bin/python -m app.db.migrate head             # migration head
```
`testpaths = tests` means bare `pytest` does **not** run `research_tests/`. `addopts = -q`
suppresses the count line — an `EXIT 0` with no summary is normal and is not evidence that
anything ran.

**Test isolation is an allowlist, and it lives at the rootdir.** `Settings.model_config` sets
`env_file=None` whenever `pytest` is in `sys.modules`, so under pytest the only config sources
are defaults and what a test sets. `backend/conftest.py` — the **rootdir** conftest, never a
deeper one — forces `PT_PROVIDER=mock`, `PT_EXECUTION=paper`, empty `PT_LIVE_ACK` and a per-run
temp `PT_DB_PATH` before any `app.*` import. It has to be at the root: the shipped `.env`
satisfies every live gate, so a suite root without the guard once resolved to live execution
against the production ledger. `PT_LIVE_ACK` is set **empty, not deleted** — pydantic-settings
falls back to `.env` when an OS var is absent.

**Frontend** (`frontend/`)
```bash
npm install && npm run dev     # :5173, proxies /api + /ws to :8090
npm run typecheck && npm test && npm run build
```

**Deploy** (from `paper-trader/`) — see `docs/operations.md`
```bash
scripts/deploy.sh [--dry-run|--force-market-hours|--prune]
```
It refuses during market hours and on a dirty tree, and there is deliberately no dirty-tree
override. It builds the SPA **locally** and ships `frontend/dist/` separately — never build on
the VPS, a 1 GB droplet that has OOM'd twice with the engine running.

## Repo map

| Path | What lives there |
|---|---|
| `backend/app/ir/` | The language: `schema`, `validate`, `resolve`, `runtime`, `kernels`, `experiment`, `edit`, `authoring`, and `library.py` — **the platform component library**. A strategy is not a registry |
| `backend/app/editor/` | Graph artefacts, drafts, layouts, comparison — authoring persistence |
| `backend/app/core/execution_binding.py` | The one decision: what runs here, and may it. `GRANTS` |
| `backend/app/core/paper_authority.py`, `shadow_deployments.py` | Managed IR deployments, with lifecycle capability tables |
| `backend/app/core/execution_book.py` | Whose money is this |
| `backend/app/engine/runner.py` | The two cooperative async loops (signal ~2.5 s, risk ~1 s) |
| `backend/app/engine/equity_entry.py`, `charges.py`, `event_risk.py`, `decision_kernel.py` | Entry, the segment-aware Indian charge stack, the blackout table, the one pure exit decision |
| `backend/app/market_data/candles.py` | **THE** candle→frame converter; `runner._to_df` and `backtest._candles_to_df` are thin aliases. Do not re-fork it |
| `backend/app/providers/` | `MarketDataProvider` seam — `safe_kite.py`, `factory.py` (process-wide singleton), `replay.py` |
| `backend/app/engine/broker_protocol.py` | `Broker` (domain verbs) vs `ExecutionVenue` (wire verbs). The only place MIS/NRML/GTT/SL-M are spelled |
| `backend/app/api/` | REST + both WebSockets; `principal.py` is the auth seam |
| `backend/app/db/`, `backend/migrations/` | Models and Alembic. Head is `0013` |
| `frontend/src/` | React + TS + Tailwind; one `/ws` in `state/LiveContext.tsx`, all REST via `lib/api.ts` |
| `research/` | Isolated research plane, own DB, fail-closed guards |

## The agenda

**Work is organised into eight workstreams.** Read
[`docs/engineering/WORKSTREAMS.md`](../../../engineering/WORKSTREAMS.md) to find yours.

An implementation session loads **three things**: `docs/ARCHITECTURE.md`, its workstream
document, and the documents that workstream lists under *Depends on*. Not the roadmap, not the
other seven. If a workstream document is missing something you need, that is a defect in the
document — fix it there.

| Document | When to read it |
|---|---|
| `docs/CONTINUE.md` | **first** — the resume point and the newest true state |
| `docs/PROGRESS.md` | the one-page state: built, running, blocked, next |
| `docs/ARCHITECTURE.md` | always — the invariants that cross every workstream |
| `docs/rfcs/0001-component-ir.md` | the constitution |
| `docs/engineering/decisions/` | **the ADRs — 0011 adoption gates, 0012 execution-state ownership, 0013 admission-not-lease.** Read the relevant one before touching authority, binding or approval. A question settled here is not re-litigated in a session |
| `docs/engineering/WORKSTREAMS.md` → `workstreams/WS-NN-*.md` | the agenda for one subsystem |
| `docs/engineering/EXECUTION_PLAN.md` | the sequential programme, gates and checkpoints |
| `docs/engineering/EXECUTIVE.md` | interfaces, sequencing, standing decisions |
| `docs/engineering/reference/architecture-extension-review-2026-08-07.md` | before proposing any product extension. Twelve directions already stress-tested against real code, with executed drills |
| `docs/reports/README.md` | frozen point-in-time reports. Never a source of current state; five are flagged stale |

Do not restate a workstream's contents here. Duplicating them into `CLAUDE.md` is how this file
drifted out of sync with reality before.

## Sizing, exits, and what production actually runs

Read `docs/PROGRESS.md` and `/api/settings` before reasoning about any number below.

- **equity_intraday is sized against real Zerodha margin, with NO leverage cap.** The
  `intraday_leverage` notional cap was removed 2026-07-22 (`0f93f9a`); it survives only as the
  probe seed and the paper/mock fallback. Do not reintroduce it as a binding cap. Deployable
  cash is clamped by real `live_balance` and **fails closed to ₹0** if funds cannot be read.
- **options: 1 lot, −30% / +60%** premium stop/target with a ratchet that never loosens. The
  widely-copied "−35%" is stale everywhere it appears (`config.py` is `0.30`). Positions with
  `entry_atr` skip the premium trail and use an ATR ratchet on spot.
- **`runtime_config` DB overrides shadow code defaults, and ten of them differ deliberately.**
  They are the owner's hand-set operating decisions from live trading experience — **not drift,
  not a defect list.** When this file and the box disagree, **fix the doc, never the box.** Do
  not clear an override to make a shipped default take effect without the owner naming that key.
  `intraday_enabled` is `False` in code and true only by DB row: clearing it would stop the
  segment that booked 70 of the 72 real trades. Clear one with `POST /api/settings/reset`, never
  by hand-editing the table.
- **Read the book before changing an exit.** Across all 72 trades `TARGET` has fired **zero**
  times; the largest favourable excursion ever recorded is 1.216% of notional against a 1.5%
  target, and the median trade travels further against you than for you
  (`docs/reports/2026-08-01-exit-sweep.md`). This is an entry-quality problem at least as much
  as an exit one.

## Conventions & gotchas

- **Kite access tokens expire ~06:00 IST daily.** Re-auth via **Connect Kite** each morning;
  headless auto-login violates Kite ToS, so this is permanent, not a gap.
- Signals fire only on **completed candles** during market hours — and for the IR reference
  artefact this is now *measured*, not conventional (C11 causality).
- **`/api/health` is a readiness probe**: 503 when the DB is unreachable, the engine loops are
  stopped, or the **fast risk lane** is stale. The signal lane is reported but never fatal.
  Budgets are static `Settings`, deliberately not `runtime_config`-overridable, so no DB row can
  silence the probe. **Still check `GET /` too** — a broken SPA mount is invisible from here,
  which is exactly how the `.env` outage hid.
- **`backend/VERSION` is generated per-deploy and gitignored**, read once at boot, exposed on
  `/api/health`, stamped on every `trades` row as `build_sha`. Three distinguishable values: a
  SHA, `'unknown'` (deployed outside `deploy.sh` — worth chasing), and NULL (predates the
  column). Never collapse the last two.
- Do not date a deploy from remote mtimes: `rsync -t` makes them the Mac's edit times.
- `KITE_*` and `TELEGRAM_*` are deliberately **not** `PT_`-prefixed (`validation_alias`).
- New tunable knob: add it to `Settings` *and* wire it through `runtime_config` if it should be
  live-editable, *and* give it a `settingsMeta` entry — an unclaimed key is an invisible key.
- All P&L / equity / backtest figures are **net** of the full charge stack.
- Commit and push only when asked. Working branch is a feature branch off `main`.

## Reuse-first policy

Before building commodity infrastructure — broker adapters, auth, symbol handling, job queues,
market-data plumbing — inspect, in order: **(1) Strategy OS itself, (2) OpenAlgo, (3)
`~/dev/multiverse-of-ideas`, (4) other relevant local or open-source projects.** Classify each
candidate **DIRECT REUSE / ADAPT-WRAP / REFERENCE ONLY / REJECT** and record the licence you
read. Do not reinvent solved plumbing; do not distort this architecture to copy outside code.

- Start at
  [`docs/engineering/reference/multiverse-index.md`](../../../engineering/reference/multiverse-index.md).
  Use the index before any broad exploration.
- **This codebase's architecture and hard invariants take precedence** over anything a reference
  project does, no matter how mature.
- **Only `reviews/` prose may cross into our code.** Nothing in `repos/` is copied, vendored or
  imported. Re-derive abstractions; never transcribe source.
- **Licensing is the reason, not caution.** OpenAlgo is **AGPL-3.0** — §13 triggers on merely
  serving users, which is fatal to a hosted product; it is a *behaviour* reference and a
  catalogue of solved problems, never a source tree. vectorbt carries a **Commons Clause** rider
  forbidding hosting fees. xyflow is **MIT** and is the one recorded buy-not-build. Never
  classify a licence by grep; read the file's first fifteen lines.
- **No reference project may introduce a second graph schema, ledger, validator, deployment
  model or execution authority.**
- Verified 2026-08-07: no reference source code exists in this repository. The only traces are
  two prose citations at `app/ir/validate.py:472` and `app/ir/schema.py:44`.

## Subagent rules

- Subagents must never run `git stash`, `git checkout -- .`, `git reset`, or anything else that
  mutates the shared working tree. Commit or hand off explicitly before dispatching.
- If a subagent produces no file writes after ~10 minutes, kill it and do the work directly.
- Prefer read-only subagents for exploration; have them write findings to a file rather than
  returning long prose.
- Settle "did I break this?" with a git worktree at HEAD, not by reasoning about it.
