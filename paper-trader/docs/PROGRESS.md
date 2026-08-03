# PROGRESS

**One page. What is built, what is running, what is blocked, what is next.**
Read this first, then go to your workstream — [`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md).

**Updated 2026-08-03** · branch `feat/exec-completeness` · S4.6a daily research review is complete
in the current publication commit; S4.6b durable notes and saved views is next.

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
| **Research** | Immutable graph runs, evidence/decisions/findings, operation receipts, version/evidence comparison and daily review aggregation complete |
| **Editor** | Durable semantic authoring, separately revisioned presentation state, undo/redo and lossless reload complete |
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
| `app/api/ir_routes.py`, `ir_experiment_routes.py` | Graph/editor reads plus closed graph-bound experiment, evidence, comparison and decision APIs |
| `app/api/ir_layout_routes.py`, `app/editor/layouts.py` | Closed, revision-checked sparse layout API and transactional store |
| `app/db/models.py`, migration `0005` | Layout head plus sparse authored-node coordinate rows |
| `frontend/src/views/GraphView.tsx`, `ResearchEvidencePanel.tsx` | Accessible graph authoring plus persisted research evidence, comparison and decisions |
| `.github/workflows/strategy-os-ci.yml` | Fail-closed push/PR checks for backend, research, smoke, frontend, type and build contracts |
| `research/…/ir_components.py` | All 23 research blocks, as components |
| `research/…/propose.py` | Structure search: five graph mutations |
| `research/…/ir_search.py` | Explores a lineage and binds every run to what produced it (F14) |
| `research/…/ir_strategy.py`, `ir_evaluate.py` | Scores explored graphs through the existing Gen-1 gates |
| `research/domain/models.py::Finding`, project-owned finding routes | Verified run-bound interpretations with immutable successor history |
| `research/operations.py`, operation status route | Locked, canonical current/last research attempts with safe read-only cockpit status |
| `app/editor/comparison.py`, version comparison route | Pure immutable graph structure/parameter/component diff composed with verified run evidence |
| `app/core/research_review.py`, review route | Derived project timeline, closed cursor/filters, current queues and separate global operations lane |

### The two results worth knowing

**`expanding_z_v4` — the strategy that books the trades — is expressed in the IR and produces
identical signals, bar for bar.** The authored artefact contains 19 node records and 47 edge
records; resolution produces the 18-node, 35-edge view rendered by the application. Signal
parity is checked over 400 bars against `ExpandingZImpulseV4.compute()`, and was proven able to
fail by mis-binding one parameter and by re-pointing one edge.

**`expanding_z_v4` is causal at every intermediate node.** "Signals fire only on completed
candles" used to be a convention; it is now measured — evaluate on a prefix of the bars and on
all of them, and every shared bar must agree. This is a new fact about production strategy code.

---

## 3. Blocked on the owner

These owner-gated production actions have been waiting several sessions. Development continues;
deployment cannot.

1. **Deploy the architecture migration** (phases A–H). Committed and verified, not on the box.
   Touches sizing, exits and order routing — the live-money rule stops it regardless of green
   tests.
2. **Adopt the IR runtime in a live path** (RFC Appendix C(d)). The parity evidence it needs now
   exists. Same rule.

Also outstanding, unchanged: VPS OS reboot (5 ESM security updates), droplet resize 1 GB → 2 GB.

---

## 4. Next

**S4.6b: durable review notes and saved views.** Define project/principal ownership and stable event
anchors first, then persist bounded non-executable annotations and reusable filters without hiding
or mutating the authoritative timeline and queues.

---

## 5. Verification state

```
$ .venv/bin/python -m pytest tests research_tests -q  # from backend/
2,856 passed · 6 skipped · EXIT 0

$ .venv/bin/python scripts/dryrun.py 700
LEDGER OK ✓ · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
SWEEP OK ✓ · EXIT 0

$ npm test && npm run typecheck && npm run build          # from frontend/
202 passed · TYPECHECK OK · BUILD OK
```

CI contract proof: removing `research_tests` from the backend workflow command turns
`test_ci_contract.py::test_backend_job_installs_requirements_and_names_both_test_roots` red for
the missing root; replacing official checkout with a SHA-pinned unapproved action turns the
action-origin guard red. Restoring both returns all six contract tests green. The current frontend
lock resolves with six `npm audit` findings (three moderate, two high, one critical); that
dependency-hardening slice remains open.

The first published Actions run found two environment-boundary tests that assumed
`PT_DISABLE_DOTENV` was absent. The tests now delete that variable explicitly while the workflow
retains its fail-closed global opt-out; `4f8fb9a` contains the correction.
The next Linux run exposed a distinct shutdown race: cancelling a lane abandoned its active
worker thread while it still held SQLite state. `b243b59` makes each lane drain blocking work and
waits for all three lanes before closing the broker session; the exact regression and the
CI-shaped complete suite pass.

Browser acceptance: desktop and 390×844 rendered 18 nodes, 35 edges and 35 connection rows with
no console errors or page-level horizontal overflow. The wide canvas scrolls inside its own
container on the phone.

S4.3 followed S4.2's full checkpoint with a 570-test WS-03/API regression (6 skips), all 204
frontend tests, typecheck and production build. Its successor insertion/CAS rollback proof and
provider/resolver/evaluator/gate spies are green. It changes no schema, execution path or safety
boundary, so the complete backend/runtime checkpoint was not repeated.

Two things about this suite, both learned the hard way:

- **It was intermittent** (two runs in five) until 2026-08-03. Schema resets and an abandoned
  shutdown worker could retain a connection that blocks `DROP TABLE` past the timeout. The known
  paths are fixed. If a run goes
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
