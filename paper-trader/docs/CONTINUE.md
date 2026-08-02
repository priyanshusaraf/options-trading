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
6. **The editor plane, both halves** (`app/ir/view.py`, `app/ir/edit.py`) — a resolved graph as
   a view model and a self-contained SVG, and mutation that validates before it returns. F13 is
   asserted as an equality of content addresses: an arranged graph and an unarranged one are the
   same artefact.
7. **Python component authoring** (`app/ir/authoring.py`) — a decorator that produces a
   conforming component from a declared interface and a function, and checks the function
   satisfies the declaration rather than inferring it. The first second way to make a component,
   and therefore the first time C13's guard is load-bearing rather than precautionary.
8. **Two defects in what was already built:** warmup was a constant where C10 says derived, and
   the suite failed two runs in five.

**Nothing in production evaluates IR graphs.** The engine still calls `compute()`; `app/ir/` is
imported only by its own tests. Adoption is RFC Appendix C(d) and stops for the owner.

Running alongside, committed and undeployed: the **enterprise architecture migration** (phases
A–H). Phase I (engine decomposition, `EngineRunner` ~2,450 lines) is not started and is
deliberately lowest priority.

---

## 2. Last verified commit

`` — Python component authoring, and the second half of the flake fix.
Preceded by `3b2b752` (warmup derived from bound parameters; the first half) and
`49e9ded` (the editor plane, writing half). Preceded by `dec854b` (its reading half). Preceded by `baef1c2` (F14 enforced). Preceded by `110e978` (the derived-parameter gap closed) and
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
collected: 2,539             (--collect-only, summed per file)
   run four times consecutively after the flake fix, EXIT 0 every time

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
- **Warmup.** Restoring the constant it replaced turns the bound-parameter test red.
- **The editor.** Suppressing the write-path validation, the cascade that removes a deleted
  node's edges, and the stored-position lookup each turn their own tests red.
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

**The suite is no longer intermittent, and the first attempt at saying so was wrong.** It failed
roughly two runs in five with "database is locked": `DROP TABLE` needs an exclusive lock, and in
WAL mode a connection still holding a transaction blocks it past the 10s `busy_timeout`. Two
places reset the schema — `test_init_db_guard.py` explicitly, and `test_health_endpoint.py` via
its `TestClient` lifespan. Isolating the first was recorded as the fix on the strength of five
clean runs; the second then erred on its own. Both halves are now in: the guard test has its own
database, and `init_db(reset=True)` disposes the pool before dropping. **A two-in-five flake
cannot be proven fixed by green runs** — the ordering is asserted directly instead. If a full run
goes red again, check it is not this shape before believing it, and note that a *live* session
still holds a checked-out connection no `dispose()` can reclaim (close your brokers).

> Note for the next session: `python` is not on `PATH` — use `.venv/bin/python` from `backend/`.
> A backgrounded `python … | tail` returns the **pipe's** exit code; capture `$?` from pytest
> directly. Under `-q` this suite's final "N passed" line does not reach the log, so the exit
> code plus `grep -cE '^FAILED|^ERROR'` is the evidence, not a summary line.

---

## 4. Next concrete action

**Python component authoring — the fourth way to make a component, and the one that decides
whether C13 survives contact with reality.**

The Language plane is finished and both halves of the editor plane exist as libraries. What the
platform still cannot do is let a person write a component. Today a kernel is a Python function
registered in a dict by content address; there is no path from "here is my indicator" to a
component with a declared interface, a version and a body address.

The pieces already exist and are the reason this is next rather than large:

- the **AST allow-list sandbox** in the research plane's code-gen builder is, per RFC 0001
  Appendix C(f), "stronger than anything in the nine systems studied — none of them sandbox user
  code at all". It constrains what a *kernel* may do, which is a property of the kernel registry,
  exactly where this work lands.
- `app/ir/edit.py` already refuses to store a non-conforming artefact, so authoring can reuse the
  gate rather than inventing a second one.
- **C13 is the clause under test.** A Python-authored component must land in the *same* registry
  a built-in lands in, with no field saying where it came from — the existing guard greps for
  exactly that and will go red if authoring introduces one. That guard was written before there
  was a second source of components; this is the first time it is load-bearing rather than
  precautionary.

Start with the derivation: given a decorated function, produce the component-def (interface from
the signature and annotations, body address from the source's content hash, version from the
registry's existing entries under that identifier), and assert `validate()` accepts it. Then the
registration path, through the sandbox.

Two things are deliberately **not** next, and one of them needs the owner:

1. **Adopting the runtime in a live path.** RFC Appendix C(d). A production change to a
   real-money path; owner acknowledgement before any deploy, regardless of green tests. The
   parity evidence it would need now exists.
2. **Deploying the architecture migration.** Eight phases committed, verified, and not on the
   box. `deploy.sh` refuses a dirty tree, which was the only reason they had not shipped; that
   reason is gone. It touches sizing, exits and order routing — all three stop for owner
   acknowledgement under the live-money rule. **This is the one item that genuinely needs the
   owner and has needed them for three sessions.**
