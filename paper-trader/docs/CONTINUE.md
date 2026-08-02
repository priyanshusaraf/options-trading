# CONTINUE

Session handoff. Exactly four things. Rewritten on every stop.

---

## 1. Current phase

**Strategy OS — Component IR.** RFC 0001 is written (Gates 1 and 2 met, **Gate 3 — owner
acceptance — still outstanding**), and its **§3 conformance suite now exists**: F1–F13 are
enforced mechanically, Appendix A's five artefacts run as real data, and C13
(provenance-blind execution) is guarded.

Running alongside, and now committed: the **enterprise architecture migration** (phases A–H).
It was sitting entirely uncommitted in the working tree at session start. Phase I (engine
decomposition, `EngineRunner` ~2,450 lines) is not started and is deliberately lowest priority.

**Nothing in either workstream is deployed.** `app/ir/` is imported only by its own tests.

---

## 2. Last verified commit

`0fbb6dd` — `feat(ir): §3 stops being a claim and becomes a test`

Preceded by `cc53bba` (the eight-phase architecture migration) and `97d6bbb` (RFC 0001).
Branch `feat/exec-completeness`, **not pushed**, and the VPS is running `4e9f125`.

---

## 3. Last acceptance command and its output

```
$ .venv/bin/python -m pytest tests research_tests -q
PYTEST EXIT: 0          (0 FAILED, 0 ERROR)

$ .venv/bin/python scripts/dryrun.py 700
  RECONCILE cash vs expected: 187,733.06 vs 187,733.06  (diff -0.0000)
  LEDGER OK ✓
DRYRUN EXIT: 0

$ .venv/bin/python scripts/backtest_smoke.py
  net<gross where charged : OK ✓
  SWEEP OK ✓
SMOKE EXIT: 0

$ .venv/bin/python -m pytest tests/test_ir_conformance.py tests/test_ir_corpus.py \
      tests/test_ir_contract_c13.py
67 passed
```

Guards proven able to fail, not merely observed passing:

- Suppressing **any one** of F1–F13 turns the IR suite red — swept all thirteen.
  That sweep caught a vacuous test of its own (F9 uniqueness passed under mutation because
  renaming a node also orphaned an edge, which raised F9 anyway); it now asserts by path.
- Planting `if strategy.is_marketplace:` in `app/engine/exit_monitor.py` fails the C13 guard.

> Note for the next session: `python` is not on `PATH` in this shell — use
> `.venv/bin/python` from `backend/`. A backgrounded `python … | tail` returns the *pipe's*
> exit code, so two "exit 0" suite runs early in this session had in fact never executed.
> Capture `$?` from pytest directly.

---

## 4. Next concrete action

**Work the topmost unchecked item: the resolver, and §4's remaining fourteen clauses with it.**

The order is forced, and the reason is written into the roadmap item: C1–C12, C14 and C15 all
constrain *resolution*. There is no resolver, so tests for them would assert against nothing —
a conformance suite with no implementation to run against is this codebase's documented
unconsumed-mechanism defect wearing a conformance badge. C13 was separable only because it is
a property of the executor that already exists.

So the next phase is spec → plan → build for the **resolver**, and its §4 clauses land in the
same phase. C4 (back-references) and C7 (instance ids derived from the instance path) must land
*with* nesting rather than after it — the RFC says so for C4 explicitly, because retrofitting
means every diagnostic path is wrong first. Appendix A.4 is already the worked test case: two
instances of one definition that must stay distinguishable, with `n_fast/n_smooth` stable
across re-resolution.

Before that phase begins, two things genuinely need owner intent:

1. **Gate 3 — does the owner accept RFC 0001?** The architecture is frozen by the goal and the
   RFC is constitutional, but its own status line still says *Proposed*. Building a resolver
   against an unaccepted constitution is the one step that should not be taken autonomously.
2. **Does the architecture migration deploy, and when?** Eight phases are committed, verified,
   and *not on the box*. `deploy.sh` refuses a dirty tree, which is the only reason they have
   not shipped; that reason is now gone. It touches sizing, exits and order routing — all three
   stop for owner acknowledgement under the goal's live-money rule, regardless of green tests.
