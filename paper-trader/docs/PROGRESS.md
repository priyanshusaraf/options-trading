# PROGRESS

**One page. What is built, what is running, what is blocked, what is next.**
Read this first, then go to your workstream — [`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md).

**Updated 2026-08-09** · branch `feat/exec-completeness`

**The L1 band is closed through L1.4 and is no longer the resume point.** IR paper authority
(`ir_graph, paper, authoritative`) is granted, bound, hardened and proven recoverable;
`(ir_graph, live, authoritative)` remains **absent by design** and is an owner gate, not a task
queued for a session to pick up. A session arriving here should **not** resume at L1 Stage 1,
shadow adoption, or live-authority design.

**The current phase is provider maturity, tenancy, execution integrity and measured research
performance** — the agenda is §4. Its first slice is done: a semantic **provider conformance
contract** now holds every adapter to one contract and catches adapters that lie about, or
silently under-declare, a capability. **Four defects, all fixed in the slice** — replay's
`option_ltp` signature (open option positions never marked in a replay), the mock's undeclared
futures pricing, Kite resolving index futures against the cash exchange, and — found by
independent review, the worst of them — a futures entry path that invented *today* as the
contract expiry and booked a position at exactly spot. Details and the five gaps left open:
[`engineering/reference/backend-hardening-2026-08-08.md`](engineering/reference/backend-hardening-2026-08-08.md) §9.

**Nothing in this phase is deployed.** "No live-money path changed" would be too strong, and
was corrected on review: `ProviderReadError` **does** change the live candle-read failure path —
a failed read now raises where it used to return `[]`, which is what makes the engine's existing
health-failure and expired-token latch reachable. It changes that path in the *safe* direction
and touches no order routing, sizing or exit logic, but it is a live-path change and must be
described as one.

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
| **Research** | Immutable graph runs, evidence/decisions/findings, operation receipts, comparison, daily review, notes, saved views, bounded search and immutable historical snapshots complete |
| **Editor** | Durable semantic authoring, separately revisioned presentation state, undo/redo and lossless reload complete |
| **Runtime** | Evaluates graphs; bindable as a `Strategy` via the shared adapter, but **not adopted by the live engine** — no order, paper, shadow or live path consumes it |
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
| `app/core/review_state.py`, migration `0008` | Project-owned optimistic review notes and canonical saved filters outside source/executable identity |
| `app/core/review_search.py`, review search route | Unicode-stable bounded search over verified summaries and active owner notes only |
| `app/core/review_snapshot.py`, `review_snapshot_store.py`, migration `0009` | Append-only content-addressed historical review captures, verified on every read and contained when corrupt |
| `app/strategy/ir_adapter.py` | A resolved graph behind the `Strategy` contract: stable identity, loud refusal of insufficient history, carried `risk_model`, declared-input frame contract. Shared by research; consumed by no execution path |

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

**The agenda is [`CONTINUE.md`](CONTINUE.md) §4** — provider maturity, then tenancy, execution
integrity and measured backtest performance. In order: settle `get_candles`'s missing failure
channel, then Upstox data-only, then the `spot_symbol`/`option_name` relocation. The provider
conformance contract that gates all of it is done; the five gaps it left open are named in
[`engineering/reference/backend-hardening-2026-08-08.md`](engineering/reference/backend-hardening-2026-08-08.md) §9.4.

The rest of this section is **history**. L1 is closed and is not a resume point.

**L1.4 — paper-authority runtime hardening — is closed (2026-08-07).** Exact-version IR paper
authority is now proven deterministic, isolated, attributable and recoverable through the
operational conditions an operator actually creates: restart and exact reload, withdrawal
mid-session, a position open under a paused/retired/unverifiable deployment, disarm, refused
and failed entries, square-off, and paper/live book isolation. 29 deterministic tests; no
market data or broker observation required.

It found one real defect. `refresh_paper_authority` withdrew a deployment's *authority* but not
the *signal it had already authored*, and those routes run between a scan and an entry pass —
so a retired graph could still open a position carrying its identity. Fixed by
`_withdraw_superseded_signals`; mutations proved the guards red and were restored. Hard
invariant 2 (exits are never gated) is proven to survive every form of withdrawal.

**The "evidence reload gap" L1.4 reported is not a defect.**
[ADR 0013](engineering/decisions/0013-research-approval-is-admission-not-a-lease.md) settles the
lifetime question: research approval is an **admission prerequisite consumed once at activation**,
not a continuously evaluated lease. Evidence and decisions are immutable and write-once, so there
is no "withdraw approval" operation — only a newer decision, which correctly blocks a *new*
deployment and a *resume* while leaving an already-active one running until a human pauses or
retires it. Restart is already research-independent, measured with every research door trapped.
Newer contradicting research is an operator-visible **read**, never a control.
`(ir_graph, live, authoritative)` remains **NOT APPROVED** and is designed nowhere.

**A pre-L1.4 architecture review was taken and its two corrections are closed (2026-08-07).**
The review (`engineering/reference/architecture-extension-review-2026-08-07.md`) stress-tested
twelve candidate product directions against the built code and found **no foundational
contradiction** — the IR/research/execution spine is preserved. Two bounded corrections
followed, and both are done:

- **G-1** — `app/ir/library.py` is now the platform component library. Six production call
  sites previously took their component vocabulary from one *strategy's* module, including
  `paper_authority.adapter_for` on the paper-authoritative path; all six now go through the
  platform boundary, which composes contributors and refuses disagreement. The correction is
  provably mechanical: the reference artefact's canonical bytes, content address, component
  body refs and every resolved node id, cache id and warmup are byte-identical before and
  after (fingerprint `1077ee8c…`). No schema change.
- **G-2** — the signal → intent → order lifecycle is now a written contract in
  `WS-02-execution.md` §3. Documentation only; L1.4 was inspected against it first and
  deepens none of the four assumptions it forbids.

Deferred with named homes and explicitly **not** to be built early: multi-instrument runtime
and multi-timeframe resolution (WS-01 §5), typed non-OHLCV data sources and dataset identity
(L3), multi-leg intent (WS-02, when a second leg exists), component packaging and permissions
(L4), auth/tenancy (L5), and the job/worker boundary that the process-global backtest sweep
singleton will eventually need (G-3 — no queues, workers, Postgres or services now).

**Execution-state ownership is now defined and gated** (ADR 0012,
`app/core/execution_binding.py`): one typed binding contract across immutable graph versions,
research evidence, candidates, deployments, the legacy authoritative strategy and the shadow
lane, plus one place — `AUTHORITY_BY_SOURCE` — where a source of logic is granted the right
to execute. `ir_graph` is `shadow` there, so every ADR 0011 owner gate begins at one reviewed
line, proven by a mutation.

**The engine now consults it.** Every strategy-selection decision in `EngineRunner` passes
through `execution_binding.bind`, and an AST guard fails the build if the runner calls a
resolver directly or stops calling the contract. Equivalence is proven across the whole space
of assignments the engine can hold — unset, default, another strategy, a stale key — so the
selection path changed and the selection did not. The deployment pin has a production caller
for the first time (`NULL` today, so behaviour is unchanged). A refusal skips the instrument
and substitutes nothing.

**And attribution follows selection.** L1.2 canonicalised execution selection authority; the
next slice canonicalised execution attribution. The binding that produced a signal is carried
from the scan to the fill, so a stale assignment no longer trades the default while the money
record names the key that failed to resolve. `publish_signal` writes the signal and its
binding through one door — a state entry with no binding is a signal whose author is unknown,
and the entry paths refuse to open on one. No schema change and no migration: all 72
production live trades already carry a valid key or the documented `NULL`, so the defect was
latent (ADR 0012 §4.1b).

**L1.3A made the shadow pairing a server-owned record.** `ir_shadow_deployments`
(migration `0011`) + `app/core/shadow_deployments.py`: an approved immutable graph version
bound to an instrument and interval in shadow mode, with verified evidence lineage, a
staged / shadow-active / paused / retired lifecycle, revision-guarded transitions, warmup
admission checked before activation, and deterministic reload after restart.
`execution_binding.shadow_source_for` is the single boundary the observer asks — managed
deployments outrank the legacy key pairing, which stays as the *named* fallback. Loading
happens at the `run_signal_loop` startup boundary, not in the constructor.

**Authority is refused three times, independently:** `AUTHORITY_BY_SOURCE`, database CHECK
constraints on `execution_mode`/`authority`, and a service with no mode parameter.

**L1.3B separated the execution books.** `app/core/execution_book.py` is the one place that
answers "whose money is this", and the answer is the execution mode — no new abstraction,
because `positions.mode` and `trades.mode` already named it correctly. What was missing was
reach: the discriminator was written on every fill and read by *no* position query, and it
did not exist at all on `capital_state` (one row, `id=1`, mutated in place) or
`equity_snapshots`. Migration `0012` adds it to both; `broker.open_positions`/`position_for`
scope every one of ~35 call sites from one chokepoint; the daily-loss breaker, the
round-trip cap, re-anchor, ledger drift, restart reconstruction and the startup lot-size
repair each count only their own book. Resolution fails closed to `live` — the strictest
book — so a blank or malformed `PT_EXECUTION` can never inherit paper's permissions.

Scoping the exit lane makes an orphan possible, and that was chosen deliberately: a paper
broker holds no order client, so "closing" a live position writes a close that never
happened. `foreign_book_positions` reports the other book's open rows at engine startup and
on `/api/health` — loud instead of silent (ADR 0012 §6.4).

**Authority is now a reviewed `(source, execution_mode)` pair.** `GRANTS` carries triples,
and `(ir_graph, paper)` is **absent** — L1.3B made the gate mode-aware precisely so that
granting IR paper authority later is one visible line rather than a side effect. The gate
recomputes both source and mode at the point of use, so a hand-built binding cannot launder
itself past it.

**L1.3C granted `(ir_graph, paper, authoritative)`.** An approved immutable graph version
can now be authoritative for one instrument **in the paper book** — the first slice where IR
output creates execution state. `ir_paper_deployments` (migration `0013`) +
`app/core/paper_authority.py`: eleven identities, staged / paper-active / paused / retired,
revision-guarded, evidence verified through the read-only bridge, and the content address
checked in three independent places (activation, every reload, and the authority gate
against the adapter the registry resolves).

The grant is **not sufficient on its own**. Because this slice registers graph adapters, a
plain instrument assignment would otherwise become authoritative — so a graph-backed binding
must also carry `ORIGIN_PAPER_AUTHORITY` and match the approved content address exactly. A
published edit therefore does not inherit authority; it is re-granted or it is gone.

Rollback names its target: `retire(..., restore_strategy_key=...)` is required, `None` means
"no previous authority", and nothing is inferred at runtime. Money records are never
rewritten.

**Two defects the slice found and fixed.** Option fills were written with
`strategy_key=NULL` (the path resolved the binding, refused without it, then dropped it), and
`strategy_version` was stamped on no entry path at all. And `LiveBroker` would have raised
`TypeError` on every real order once those parameters were added, because the protocol guard
compared only the *paper* implementation — now closed by
`test_the_live_broker_accepts_everything_the_paper_broker_does`.

**The live owner gate: `(ir_graph, live, authoritative)`.** Absent, unbuilt, and reachable
only through three independent reviewed changes — the grant, a table whose CHECK permits it,
and a service able to write it. Live authority additionally reaches `LiveBroker`,
`KiteOrderClient` and the real order seam, none of which paper authority touches.

**Deferred by owner decision (2026-08-04), and not on the critical path:** ≥ 20 genuine
market sessions, cleaning or expanding the recorded dataset, native OHLCV replay fidelity,
long-duration production shadow statistics, frontend settings controls, usability testing.
Revisit before authority promotion, production deployment or commercial validation.

Still true and worth knowing: **nothing is shadowed in production.** The default
`trend_impulse_v3` has no IR mirror, and assigning `expanding_z_v4` to an instrument changes
what it trades — an owner decision, not a slice's.

## 5. Verification state

Latest, 2026-08-09, after the provider conformance slice:

```
$ .venv/bin/python -m pytest tests research_tests      # from backend/
3,595 passed · 6 skipped · EXIT 0                      (169s)

$ .venv/bin/python scripts/dryrun.py 700
RECONCILE cash vs expected: 187,733.06 vs 187,733.06 (diff -0.0000) · LEDGER OK · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
SWEEP OK ✓ · EXIT 0

$ .venv/bin/python scripts/provider_conformance_mutations.py
8/8 mutations reddened their own guard and were restored · suite green · EXIT 0
```

Exact-head Actions run **`31303084479` on `ca6f231` is green** across backend, frontend and
deterministic smoke — the verification gap this phase carried is closed.

Earlier baseline, retained for comparison:

```
$ .venv/bin/python -m pytest tests research_tests -q  # from backend/
3,098 passed · 6 skipped · EXIT 0

$ .venv/bin/python scripts/dryrun.py 700
LEDGER OK ✓ · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
SWEEP OK ✓ · EXIT 0

$ npm test && npm run typecheck && npm run build          # from frontend/
222 passed · TYPECHECK OK · BUILD OK          (frontend untouched by L1 Stage 1)

$ .venv/bin/python scripts/ir_shadow_replay.py     # L1 Stage 1 measurement
110/110 settled bars agree · 0 unexplained · eval p95 3.8 ms · loop share 1.46% · EXIT 0

$ .venv/bin/python scripts/ir_shadow_mutations.py  # L1 Stage 1 guard proofs
all 12 guards reddened on their own defect and were restored · EXIT 0
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
