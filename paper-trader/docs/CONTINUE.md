# CONTINUE

Session handoff. Exactly four things. Rewritten on every stop.

---

## 1. Current phase

**Strategy OS — Component IR. The language is finished, and every clause in it is enforced.**

RFC 0001 is **Accepted** (Gate 3 recorded 2026-08-02 against the owner's standing directive that
the architectural phase is complete — one line at the top of the RFC says so, and it is the line
to correct if that reading was too broad). **All fourteen format clauses and all fifteen contract
clauses are now enforced mechanically**, F14 included. `UNENFORCEABLE_CLAUSES` is empty.

Five things landed this session, in order, each the consumer of the one before — deliberately,
because a correct mechanism wired to nothing is this repo's defining defect:

1. **The resolver** (`app/ir/resolve.py`, `kernels.py`, `hashing.py`) — the single resolution.
2. **The component runtime** (`app/ir/runtime.py`) — evaluates a resolved graph, and turns C8,
   C9, C10 and C11 from declarations into measurements.
3. **`expanding_z_v4` as a real IR graph** (`app/ir/strategies/expanding_z.py`) — 15 components,
   17 nodes, 47 edges, equal to `ExpandingZImpulseV4.compute()` bar for bar.
4. **The derived-parameter gap closed** — `value.scalar` → `math.scale`, so the exit thresholds
   track `min_abs_z` instead of remembering one of its values. First use of F7's `scalar` axis.
5. **F14 enforced** (`app/ir/experiment.py`) — an experiment record whose binding is *derived*
   from the resolved graph, so it cannot be told the wrong versions.
6. **The editor plane, read-only** (`app/ir/view.py`) — a resolved graph as a view model and a
   self-contained SVG. Layout is derived from the dependency structure, so F13's "no
   presentation state in the artefact" holds by there being none at all.

**Nothing in production evaluates IR graphs.** The engine still calls `compute()`; `app/ir/` is
imported only by its own tests. Adoption is RFC Appendix C(d) and stops for the owner.

Running alongside, committed and undeployed: the **enterprise architecture migration** (phases
A–H). Phase I (engine decomposition, `EngineRunner` ~2,450 lines) is not started and is
deliberately lowest priority.

---

## 2. Last verified commit

`dec854b` — the editor plane, read-only. Preceded by `baef1c2` (F14 enforced). Preceded by `110e978` (the derived-parameter gap closed) and
`e97ed72` (`expanding_z_v4` expressed in the IR and proven equal to the strategy).
Preceded by `df0bf6c` (the component runtime), `126c9cf` (the resolver), `34a4765` (§3
conformance), `cc53bba` (architecture migration), `97d6bbb` (RFC 0001).

Branch `feat/exec-completeness`, **not pushed**.

The VPS build was **not measured this session**. ROADMAP.md said `8cee4e9` and an earlier version
of this file said `4e9f125`; both are prose, and prose is how the last deployment-state error
survived a week. `curl /api/health` on the box is the only answer.

---

## 3. Last acceptance command and its output

```
$ .venv/bin/python -m pytest tests research_tests -q
PYTEST EXIT: 0
FAIL/ERROR lines: 0          (grepped, not eyeballed)
collected: 2,503             (--collect-only, summed per file)

$ .venv/bin/python scripts/dryrun.py 700
  RECONCILE cash vs expected: 187,733.06 vs 187,733.06  (diff -0.0000)
  LEDGER OK ✓
DRYRUN EXIT: 0

$ .venv/bin/python scripts/backtest_smoke.py
  net<gross where charged : OK ✓
  SWEEP OK ✓
SMOKE EXIT: 0
```

Guards proven able to fail, not merely observed passing:

- **§4, all fifteen clauses.** Suppressing each of C1–C11, C14, C15 one at a time turns that
  clause's **own** test red — swept all of them. C12 proven red by planting a second
  `ResolvedGraph(` construction under `app/engine/`; C13 (previous phase) by planting
  `if strategy.is_marketplace:` in `app/engine/exit_monitor.py`.
- **The runtime.** Nine suppressions — cache lookup, cache key, purity gate, warmup, index check,
  every-node causality comparison, reference series, kernel lookup, missing-input check — each
  turn their own test red.
- **The strategy parity claim.** Binding `n_entry_thr` to `exit_pct`, re-pointing one edge from
  `n_ema` to `n_z`, and setting `n_exit_floor`'s scale factor to 0, each turn the bar-for-bar
  parity test red. The fixture is checked for firing signals, so parity is not two constant
  series agreeing.
- **F14.** Suppressing each of its six checks — the graph comparison, the component-version
  comparison, the node-identity comparison, the finding-binding comparison, and the presence
  checks — turns its own test red.
- **The renderer.** Suppressing label truncation turns the box-geometry test red. That test
  exists because the first render spilled a definition out through the edge of its box and
  nothing failed — SVG text does not clip, so the picture was wrong and looked fine.
- **§3, F1–F13**, swept in the earlier phase.

Three vacuous tests were found by those sweeps and fixed, all worth remembering:

- C2's no-mutation check deep-copied the shared fixture *after* other tests had resolved it, and
  a resolver that eats its input does so on the first call and is idempotent after.
- `check_causality` compared only the graph's **outputs**, which calls a whole-series
  normalisation causal: divide both branches by a max neither bar knew yet and the comparison
  between them is unchanged. It now compares every node's every socket.
- F14's `node_identities` check: every test of it emptied the mapping, which trips the *presence*
  check, so deleting the comparison against the resolved graph left the suite green. Identities
  that are present and **wrong** are the interesting case, and there is now a test for them.

> Note for the next session: `python` is not on `PATH` — use `.venv/bin/python` from `backend/`.
> A backgrounded `python … | tail` returns the **pipe's** exit code; capture `$?` from pytest
> directly. Under `-q` this suite's final "N passed" line does not reach the log, so the exit
> code plus `grep -cE '^FAILED|^ERROR'` is the evidence, not a summary line.

---

## 4. Next concrete action

**The writing half of the editor plane: graph editing, and where presentation state lives.**

Reading a graph is done. Editing is where the architecture actually gets tested, because it is
the first time anything mutates an artefact, and F13 is waiting for it: "presentation state MUST
persist **beside** the graph, keyed by stable identifier, and is not part of the artefact
grammar." Today there is no presentation state at all — `view.py` derives position — and that is
the conforming default. The moment a human drags a node, a side table appears, and the test that
matters is that dragging does **not** change the graph's content address.

Concretely, in this order:

1. A mutation API over a graph-def — add node, remove node, connect, disconnect, override — that
   returns a **new** artefact and validates it, so an edit that would break §3 is refused rather
   than stored. `validate()` already exists; nothing calls it on a write path because there is no
   write path.
2. A layout side table keyed by `instance_id`, with the test above: same graph, different
   positions, identical `content_address`.
3. Only then the frontend. The backend has no IR route yet, deliberately — `app/ir/` is imported
   by its own tests and by `scripts/render_ir_graph.py`, and adding a route is the first thing
   that would make this workstream part of the running application.

Two things are deliberately **not** next, and one of them needs the owner:

1. **Adopting the runtime in a live path.** RFC Appendix C(d). A production change to a
   real-money path; owner acknowledgement before any deploy, regardless of green tests. The
   parity evidence it would need now exists.
2. **Deploying the architecture migration.** Eight phases committed, verified, and not on the
   box. `deploy.sh` refuses a dirty tree, which was the only reason they had not shipped; that
   reason is gone. It touches sizing, exits and order routing — all three stop for owner
   acknowledgement under the live-money rule. **This is the one item that genuinely needs the
   owner and has needed them for three sessions.**
