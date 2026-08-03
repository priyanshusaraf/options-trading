# CONTINUE

Session handoff. Four things. Rewritten on every stop.

**For project state read [`PROGRESS.md`](PROGRESS.md). To implement, read
[`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md) and go to your workstream.** This
file is the resume point, not the overview.

---

## 1. Current phase

**WS-04 Editor is active.** Its first vertical slice is committed end to end: one read-only JSON
route over the resolved `expanding_z_v4` graph and a native HTML/SVG viewer in the existing
`Strategy Graph` tab. The route is mounted on `/api` and `/api/v1`, resolves only a fixed
repository-owned catalogue, and has no execution, broker, provider, database or order
dependency.

**Nothing in this session is deployed.** The engine still calls `compute()`; the route is a
viewer and does not adopt the IR runtime in a live path.

## 2. Last verified commit

`f61dfe4` — typed read-only React graph viewer, transport/render tests and tab integration.
Preceded by `000075d` (route handoff documentation) and `049b699` (the closed graph API and 14
route tests).

Branch `feat/exec-completeness`, 92 commits ahead of `main`. The working tree contains only the
current documentation edits.

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

$ npm test && npm run typecheck && npm run build          # from frontend/
153 passed · TYPECHECK OK · BUILD OK
```

Live-browser acceptance used a dotenv-disabled mock/paper backend with temporary databases.
Desktop and 390×844 rendered 18 node articles, 35 SVG paths and 35 connection rows with no
console errors. At phone width the 2,216px canvas stayed inside a 356px scroller and the page did
not overflow.

New route guards proven able to fail rather than merely observed passing: unversioned
registration, `/api/v1` mirroring, complete serialization including cache identity, read-only
graph identity, and library-dependent F7 validation. The fixed catalogue also rejects unknown
identifiers before `resolve()` is reached.

Frontend guards were also observed red before implementation: missing graph transport, missing
canvas module, missing tab wiring, non-semantic node cards, collapsed impurity policy, absent
state presenter and absent scroller containment. The reviewed result has no remaining Critical
or Important finding.

Five shapes of **vacuous test** were caught this session by suppression sweeps and fixed —
right-clause-wrong-cause, a fixture already corrupted by an earlier test, checking only the
endpoints, a presence check masking a comparison check, and a case refused for the wrong reason.
All look exactly like passing tests.

Two measurement traps hit this session, both worth not repeating: a sweep grepping only
`^FAILED` misses mutations that break a **fixture** (those report as `ERROR`), and `$?` after a
pipeline is the pipe's exit code, not the command's.

## 4. Next concrete action

**WS-04 Editor — implement the F13 layout side table.**

Choose the presentation-state store and add a sparse record keyed by graph identifier/version
and `instance_id`; store only positions the user has moved. Define what happens to orphaned rows
after a node is removed. Feed the stored `Layout` to `graph_view()` without adding graph fields.
The acceptance proof must save a position, reload both layout and artefact, and show that the
graph's `content_address` is unchanged. Do not add drag gestures until this route/store boundary
and proof exist.

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
