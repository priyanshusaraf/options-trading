# PROGRESS

**One page. What is built, what is running, what is blocked, what is next.**
Read this first, then go to your workstream — [`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md).

**Updated 2026-08-03** · branch `feat/exec-completeness` · 89 commits ahead of `main`.

---

## 1. Is the live bot OK?

| | |
|---|---|
| Trading | Real money, live since 2026-06-29. 72 trades booked, net **−₹166.37** |
| Runs on | DO Bangalore VPS, 24/7. Backend :8090 |
| VPS build | **not measured this session.** `curl localhost:8090/api/health` is the only answer — never read it off a doc |
| Deployed from this branch | **nothing.** Everything below is local |

Nothing in the Strategy OS work touches the running bot. One read-only API route now imports
`backend/app/ir/`; the engine still calls the hand-written strategy and no live path consumes IR.

---

## 2. Where the Strategy OS stands

Work is organised into **eight workstreams** — see
[`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md). Each is independently maintainable;
the architecture is singular.


RFC 0001 (the Component IR) is **Accepted**, and **all 29 normative clauses are enforced by
tests** — 14 Format, 15 Contract. Each clause's own test was proven able to fail by suppressing
that clause's implementation.

| Plane (RFC §1.2) | State |
|---|---|
| **Language** | Done — format, resolver, runtime, experiment binding |
| **Research** | Gen 2 functionally complete; remaining work is operational runs and explanations |
| **Editor** | Read-only backend route done; **React view next** |
| **Runtime** | Evaluates graphs; **not adopted by the live engine** |
| **Marketplace** | Not started |

### Built (all verified, all committed, none deployed)

| Module | What it is |
|---|---|
| `app/ir/schema.py`, `validate.py` | The format, as a validator. F1–F13 |
| `app/ir/resolve.py` | The single resolution. Lowers nesting by instance path |
| `app/ir/kernels.py` | What a kernel declares: warmup, purity, cache identity |
| `app/ir/runtime.py` | Evaluates a resolved graph; catches lookahead by measurement |
| `app/ir/experiment.py` | F14 — binds a result to every version that produced it |
| `app/ir/view.py` | A graph as a view model and a self-contained SVG |
| `app/ir/edit.py` | Mutation that cannot return a non-conforming artefact |
| `app/ir/authoring.py` | Write a component in Python |
| `app/ir/strategies/expanding_z.py` | The live strategy, as a graph |
| `app/api/ir_routes.py` | One read-only, fixed-catalogue route for the resolved graph view |
| `research/…/ir_components.py` | All 23 research blocks, as components |
| `research/…/propose.py` | Structure search: five graph mutations |
| `research/…/ir_search.py` | Explores a lineage and binds every run to what produced it (F14) |
| `research/…/ir_strategy.py`, `ir_evaluate.py` | Scores explored graphs through the existing Gen-1 gates |

### The two results worth knowing

**`expanding_z_v4` — the strategy that books the trades — is expressed in the IR and produces
identical signals, bar for bar.** 15 components, 17 nodes, 47 edges, checked over 400 bars
against `ExpandingZImpulseV4.compute()`. Proven able to fail by mis-binding one parameter and by
re-pointing one edge.

**`expanding_z_v4` is causal at every intermediate node.** "Signals fire only on completed
candles" used to be a convention; it is now measured — evaluate on a prefix of the bars and on
all of them, and every shared bar must agree. This is a new fact about production strategy code.

---

## 3. Blocked on the owner

Both have been waiting several sessions. Development continues; deployment cannot.

1. **Deploy the architecture migration** (phases A–H). Committed and verified, not on the box.
   Touches sizing, exits and order routing — the live-money rule stops it regardless of green
   tests.
2. **Adopt the IR runtime in a live path** (RFC Appendix C(d)). The parity evidence it needs now
   exists. Same rule.

Also outstanding, unchanged: VPS OS reboot (5 ESM security updates), droplet resize 1 GB → 2 GB.

---

## 4. Next

**WS-04 Editor: render the resolved `expanding_z_v4` graph in React.** Use the existing REST
client and app shell; show authored instance paths, sockets, parameters, warmup, purity and cache
identity. Keep this slice read-only. Layout persistence follows only after the viewer is real.

---

## 5. Verification state

```
$ .venv/bin/python -m pytest tests research_tests -q      # from backend/
PYTEST EXIT: 0 · 0 FAILED/ERROR · 2,700 collected

$ .venv/bin/python scripts/dryrun.py 700
LEDGER OK ✓ · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
SWEEP OK ✓ · EXIT 0
```

Two things about this suite, both learned the hard way:

- **It was intermittent** (two runs in five) until 2026-08-03. Two places reset the schema, and a
  connection holding a lock blocks `DROP TABLE` past the timeout. Both are fixed. If a run goes
  red, check it is not that shape first.
- **A green test can be vacuous.** Five distinct shapes have been caught here by mutating the
  implementation and checking the clause's *own* test goes red. Counting green runs is not
  evidence; suppression sweeps are.

---

## 6. How the docs relate

Implementation work loads **three documents**: `ARCHITECTURE.md`, one workstream document, and
whatever that workstream declares under *Depends on*. Nothing else.

| File | Purpose |
|---|---|
| `PROGRESS.md` | this page — the at-a-glance state |
| `ARCHITECTURE.md` | the invariants that cross every workstream |
| `engineering/WORKSTREAMS.md` | the eight streams and which owns what |
| `engineering/workstreams/WS-NN-*.md` | the whole agenda for one subsystem |
| `engineering/EXECUTIVE.md` | coordination: interfaces, sequencing, drift |
| `engineering/DEPENDENCIES.md` | the dependency graph |
| `ROADMAP.md` | cross-workstream order and owner blockers only |
| `CONTINUE.md` | session handoff: last verified commit, acceptance run, next action |
| `rfcs/0001-component-ir.md` | the constitution |
| `reports/` | point-in-time audits and reviews, indexed in `reports/README.md`. Five are flagged as containing stale claims — read the header before acting on one |
| `../CLAUDE.md` | how to work in this repo; live-money invariants |
