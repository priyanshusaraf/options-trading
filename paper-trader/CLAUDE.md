# CLAUDE.md

Always-on guidance for Strategy OS. Everything task-specific lives in `.claude/rules/`
(auto-loads by path), `.claude/skills/` (loads on invocation), and the docs pointed at below.

## What this is

**Strategy OS — a visual, node-based platform for building, researching and running trading
strategies.** A trader connects indicators, price action, conditions, instruments, reusable
components, data sources and execution rules on a canvas; researches and backtests the graph;
then deploys and monitors it through a supported broker.

The typed immutable IR, resolver, research lineage, execution authority and provenance are the
**machinery underneath that experience** — not the product identity. Do not reason about this
repo as the older autonomous options bot.

**One part of it trades real money.** Live since 2026-06-29 on a Bangalore VPS; the live order
path (`LiveBroker`, `KiteOrderClient`, `LiveExecutionKite`) is in production use. Treat any
change touching execution, sizing, exits or routing as a production change.

Two processes: FastAPI backend on **:8090**, Vite/React frontend on **:5173**.

## Core invariants

Never weaken one without an explicit instruction naming it.

**Language.** One graph/IR language · one validator, resolver and hash · immutable executable
graph versions · presentation state never enters identity · results bind to the versions that
produced them.

**Authority.** Canonical execution binding is the single decision of what runs where ·
requested assignment ≠ resolved executable strategy · strategy ≠ graph ≠ deployment ≠ evidence
≠ authority · exact execution attribution from scan to fill · admission-only research approval
(consumed once at activation, never a lease) · exact content-address match when authority is
granted or re-granted · no stale signals survive authority withdrawal · **no silent live IR
authority**.

**Money.** Paper and live are structurally separate books, failing closed to `live` · the
ledger reconciles to the paisa · ARM gates entries only, never exits · deterministic replay and
accounting where promised.

**Providers.** Data provider ≠ execution broker · Strategy OS owns canonical instrument
identity, never a provider's symbol or token · multiple provider connections per account must
remain architecturally possible · a strategy may observe different instruments from its
execution target.

**Delivery.** Deploys go only through `scripts/deploy.sh` · exact-head CI before meaningful
closure.

## Owner gates — stop and ask

1. Enabling `(ir_graph, live, authoritative)` — live IR authority. Absent by design.
2. Material changes to live sizing, routing, risk or execution semantics.
3. Anything touching the owner's live-money VPS environment or its credentials.
4. Destructive database or infrastructure operations.
5. Adopting licence-sensitive code (OpenAlgo is AGPL-3.0).
6. Regulatory, legal, commercial or customer-real-money decisions.
7. **Frontend code (2026-08-09).** The owner takes this up directly. Backend work stops at the
   API boundary; write frontend requirements into the design notes and stop there.

Development, testing and commits continue normally at these gates. Deployment does not.

## How to work here

**Evidence, not assertion.** Every claim about state, test results, or whether a fix worked is
followed by the exact command and its output. Say "unverified" if you did not run it. Re-run
the original repro before saying fixed.

**A green test can be vacuous.** Prove a guard can go red by suppressing what it guards and
checking that guard's *own* test fails. Five shapes have been caught here that way.

**Tests are not completion.** Ask what observable evidence would differ if the change actually
works, then go get it. Use `.claude/skills/implementation-slice` for substantial work and
`ship-gate` before declaring done.

**Verification is proportional.** Do not run the whole repo for a typo. Select evidence
matching the affected contract.

**Never assert deployment state from prose** — including from this file. `curl /api/health` and
compare the commit.

**Reuse-first.** Before building commodity infrastructure inspect, in order: Strategy OS
itself, OpenAlgo (`~/dev/openalgo`, AGPL-3.0 — behaviour reference only, never copy code),
`~/dev/multiverse-of-ideas`, then other open source. Classify DIRECT REUSE / ADAPT-WRAP /
REFERENCE ONLY / REJECT and record the licence you read.

**Independent review.** A reviewer should not be the author. Dispatch the relevant agent in
`.claude/agents/` rather than reviewing your own diff.

## Commands

Run from `backend/` or `frontend/` — never the repo root. `python` is not on `PATH`; use
`.venv/bin/python`. **macOS has no `timeout`** — do not use it in commands.

```bash
# backend/
.venv/bin/python -m pytest tests research_tests   # BOTH suites; bare pytest skips research_tests
.venv/bin/python scripts/dryrun.py 700            # engine + ledger reconciliation → LEDGER OK
.venv/bin/python scripts/backtest_smoke.py        # sweep + net-of-charges → SWEEP OK
.venv/bin/python -m app.db.migrate head           # migration head (currently 0015)
# frontend/
npm test && npm run typecheck && npm run build
# paper-trader/
scripts/deploy.sh                                 # the ONLY sanctioned deploy path
```

`addopts = -q` suppresses the count line — `EXIT 0` with no summary is normal, not evidence
that nothing ran. A backgrounded `cmd | tail` reports the **pipe's** exit code. A mutation that
breaks a fixture reports as `ERROR`, not `FAILED` — grep both.

Starting the app for real verification: `.claude/skills/run-strategy-os`.

## Documentation map

| Document | When |
|---|---|
| `docs/CONTINUE.md` | **first** — the resume point and newest true state |
| `docs/PROGRESS.md` | one-page state: built, running, blocked, next |
| `docs/ARCHITECTURE.md` | the invariants that cross every workstream |
| `docs/rfcs/0001-component-ir.md` | the constitution |
| `docs/engineering/decisions/` | ADRs — 0011 adoption gates, 0012 execution-state ownership, 0013 admission-not-lease. A question settled here is not re-litigated in a session |
| `docs/engineering/WORKSTREAMS.md` → `workstreams/WS-NN-*.md` | the agenda for one subsystem |
| `docs/engineering/EXECUTION_PLAN.md` | the sequential programme and gates |
| `docs/engineering/reference/architecture-extension-review-2026-08-07.md` | before proposing any product extension — twelve directions already stress-tested against real code |
| `docs/engineering/reference/backend-hardening-2026-08-08.md` | current security/perf/leakage findings and benchmarks |
| `docs/reports/README.md` | frozen point-in-time reports; never current state |

An implementation session loads `docs/ARCHITECTURE.md`, its workstream document, and whatever
that workstream declares under *Depends on*. Not the roadmap, not the other seven.

## Conventions

- **Kite tokens expire ~06:00 IST daily**; re-auth via Connect Kite. Headless auto-login
  violates Kite ToS — permanent, not a gap.
- **`runtime_config` DB rows shadow code defaults, and ten differ deliberately.** They are the
  owner's hand-set trading decisions. When this file and the box disagree, **fix the doc**.
  Never clear an override without the owner naming that key. `intraday_enabled` is `False` in
  code and true only by DB row.
- Signals fire only on **completed candles**.
- All P&L, equity and backtest figures are **net** of the full Indian charge stack.
- `KITE_*` and `TELEGRAM_*` are deliberately not `PT_`-prefixed.
- Commit and push only when asked. Work on a feature branch off `main`.

## Subagent rules

- Never run `git stash`, `git checkout -- .`, `git reset`, or anything else that mutates the
  shared working tree.
- Prefer read-only subagents for exploration; have them write findings to a file.
- Settle "did I break this?" with a git worktree at HEAD, not by reasoning about it.
