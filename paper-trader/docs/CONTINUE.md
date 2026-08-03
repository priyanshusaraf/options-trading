# CONTINUE

Session handoff. Four things. Rewritten on every stop.

**For project state read [`PROGRESS.md`](PROGRESS.md). To implement, read
[`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md) and go to your workstream.** This
file is the resume point, not the overview.

---

## 1. Current phase

**WS-04 Editor is active.** The first application consumer of the Component IR is committed: a
single read-only JSON route over the resolved `expanding_z_v4` graph. It is mounted on `/api` and
`/api/v1`, resolves only a fixed repository-owned catalogue, and has no execution, broker,
provider, database or order dependency.

**Nothing in this session is deployed.** The engine still calls `compute()`; the route is a
viewer and does not adopt the IR runtime in a live path.

## 2. Last verified commit

`049b699` — read-only IR graph API route, its closed response contract and 14 route tests.

Branch `feat/exec-completeness`, 89 commits ahead of `main`, one commit ahead of origin before
the documentation update. The working tree contains only the current documentation edits.

The VPS build was **not measured this session.** `curl localhost:8090/api/health` on the box is
the only answer — never read it off a document.

## 3. Last acceptance command and output

```
$ .venv/bin/python -m pytest tests research_tests -q     # from backend/
PYTEST EXIT: 0 · 0 FAILED/ERROR (grepped, both FAILED and ERROR) · 2,700 collected

$ .venv/bin/python scripts/dryrun.py 700
RECONCILE cash vs expected: 187,733.06 vs 187,733.06 (diff -0.0000) · LEDGER OK ✓ · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
net<gross where charged : OK ✓ · SWEEP OK ✓ · EXIT 0
```

New route guards proven able to fail rather than merely observed passing: unversioned
registration, `/api/v1` mirroring, complete serialization including cache identity, read-only
graph identity, and library-dependent F7 validation. The fixed catalogue also rejects unknown
identifiers before `resolve()` is reached.

Five shapes of **vacuous test** were caught this session by suppression sweeps and fixed —
right-clause-wrong-cause, a fixture already corrupted by an earlier test, checking only the
endpoints, a presence check masking a comparison check, and a case refused for the wrong reason.
All look exactly like passing tests.

Two measurement traps hit this session, both worth not repeating: a sweep grepping only
`^FAILED` misses mutations that break a **fixture** (those report as `ERROR`), and `$?` after a
pipeline is the pipe's exit code, not the command's.

## 4. Next concrete action

**WS-04 Editor — implement the React graph view.**

Add typed `getIrGraph()` transport in `frontend/src/lib/api.ts`, then a read-only graph view in
the existing tab shell. Render nodes by authored instance path; show definition, all bound
parameters, warmup, purity and full cache identity; draw edges and show source/target sockets in
an accessible connection table. Derived and impure states need text labels as well as visual
distinction. Keep the deterministic backend layer/row positions, add no graph library, and add
no editing, dragging or persistence yet.

After the browser workflow passes typecheck, tests and build, update these handoff documents and
continue to the F13 layout side table.

WS-08's typography item is **externally blocked**: it needs the owner's reference site.

Blocked on the owner, several sessions old — `PROGRESS.md` §3 and `ROADMAP.md` §2:

1. **Deploying the eight-phase architecture migration.** Committed, verified, off the box.
   Touches sizing, exits and order routing.
2. **Adopting the IR runtime in a live path.** RFC Appendix C(d); parity evidence now exists.
3. **VPS OS reboot** and **droplet resize 1 GB → 2 GB**.

> Environment notes: `python` is not on `PATH` — use `.venv/bin/python` from `backend/`. Under
> `-q` this suite's final "N passed" line does not reach the log, so the exit code plus
> `grep -cE '^(FAILED|ERROR)'` is the evidence. Count **both**: a mutation that breaks a fixture
> reports as ERROR, and a sweep grepping only FAILED reads it as vacuous.
