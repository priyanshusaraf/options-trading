# CONTINUE

Session handoff. Four things. Rewritten on every stop.

**For project state read [`PROGRESS.md`](PROGRESS.md). To implement, read
[`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md) and go to your workstream.** This
file is the resume point, not the overview.

---

## 1. Current phase

**The engineering workflow has just been reorganised.** Implementation is now distributed
across eight workstreams under `docs/engineering/`; the architecture stays singular. An
implementation session loads three documents — `ARCHITECTURE.md`, its own workstream, and
whatever that workstream declares under *Depends on* — instead of a 1,279-line roadmap.

Before that, in this session: the **Component IR reached completion as a language**. RFC 0001
is Accepted and all 29 normative clauses (14 Format, 15 Contract) are enforced by tests, each
proven able to fail. Ten IR modules, the live strategy expressed in the IR with bar-for-bar
parity, the block library derived as 23 components, and a structure proposer.

**Nothing in this session is deployed.** `backend/app/ir/` is imported only by its own tests
and one script. The engine still calls `compute()`.

## 2. Last verified commit

`` — the F14 run binding. Preceded by `1f0dade` (report triage), `daacb66` (the
workstream reorganisation) and `cdbe686` (the comment trim).

Preceded by `15125b6` (structure proposer + F8's converse), `0dd7a4d`
(block library as IR components), `c234e70` (Python authoring + the flake fix), `baef1c2` (F14),
`dec854b`/`49e9ded` (editor plane), `df0bf6c` (runtime), `126c9cf` (resolver).

Branch `feat/exec-completeness`, **not pushed**, ~80 commits ahead of `main`.

The VPS build was **not measured this session.** `curl localhost:8090/api/health` on the box is
the only answer — never read it off a document.

## 3. Last acceptance command and output

```
$ .venv/bin/python -m pytest tests research_tests -q     # from backend/
PYTEST EXIT: 0 · 0 FAILED/ERROR (grepped, both FAILED and ERROR) · 2,612 collected

$ .venv/bin/python scripts/dryrun.py 700
RECONCILE cash vs expected: 187,733.06 vs 187,733.06 (diff -0.0000) · LEDGER OK ✓ · EXIT 0

$ .venv/bin/python scripts/backtest_smoke.py
net<gross where charged : OK ✓ · SWEEP OK ✓ · EXIT 0
```

Guards proven able to fail rather than merely observed passing: all 29 RFC clauses, the runtime
(nine suppressions), the strategy parity claim (three), the editor write path (three), authoring
(five), F8's converse (two), and warmup-from-bound-parameters.

Five shapes of **vacuous test** were caught this session by suppression sweeps and fixed —
right-clause-wrong-cause, a fixture already corrupted by an earlier test, checking only the
endpoints, a presence check masking a comparison check, and a case refused for the wrong reason.
All look exactly like passing tests.

Two measurement traps hit this session, both worth not repeating: a sweep grepping only
`^FAILED` misses mutations that break a **fixture** (those report as `ERROR`), and `$?` after a
pipeline is the pipe's exit code, not the command's.

## 4. Next concrete action

**WS-03 Research Plane — the search loop.** F14 binding landed 2026-08-03
(`research/strategy/builder/ir_search.py`): every explored graph is validated, resolved,
evaluated and recorded with a binding derived from its own `ResolvedGraph`. Now an objective can
be added on top, and only now — a run recorded without a binding is permanently unattributable.

Two things the binding work turned up, both in WS-03 §5:
`ExperimentRecord.binding` covers identities, versions and the data digest but **no edges**; it
survives a `rewire` only because `ResolvedNode.cache_id` folds in upstream cache ids. F14's
wiring sensitivity is a property of *resolution*, not of the record. Setting any component's
`cache_identity` to `"declared"` breaks that, and whoever does it should know.

Then, in the owner's order:

1. **WS-08 Cockpit UI** — typography and palette.
3. **WS-04 Editor** — read-only graph rendering in the app. The libraries exist and are tested;
   there is no route and no React yet, which is the first thing that would make the IR part of
   the running application.

Blocked on the owner, several sessions old — `PROGRESS.md` §3 and `ROADMAP.md` §2:

1. **Deploying the eight-phase architecture migration.** Committed, verified, off the box.
   Touches sizing, exits and order routing.
2. **Adopting the IR runtime in a live path.** RFC Appendix C(d); parity evidence now exists.
3. **VPS OS reboot** and **droplet resize 1 GB → 2 GB**.

> Environment notes: `python` is not on `PATH` — use `.venv/bin/python` from `backend/`. Under
> `-q` this suite's final "N passed" line does not reach the log, so the exit code plus
> `grep -cE '^(FAILED|ERROR)'` is the evidence.
