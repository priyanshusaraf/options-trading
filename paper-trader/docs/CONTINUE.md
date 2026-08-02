# CONTINUE

Session handoff. Exactly four things. Rewritten on every stop.

---

## 1. Current phase

**Strategy OS — Component IR. The language is finished and enforced end to end.**

RFC 0001 is **Accepted** (Gate 3 recorded 2026-08-02 against the owner's standing directive that
the architectural phase is complete — one line at the top of the RFC says so, and it is the line
to correct if that reading was too broad). §3's fourteen format clauses and §4's fifteen contract
clauses are all enforced mechanically, against a real validator and a real resolver.

`app/ir/` is now four modules — `schema.py`, `validate.py`, `resolve.py`, `kernels.py`, plus
`hashing.py` — and is **imported only by its own tests**. Nothing executes IR graphs. That is the
next phase and it is a real-money change (RFC Appendix C(d)).

Running alongside, committed and undeployed: the **enterprise architecture migration** (phases
A–H). Phase I (engine decomposition, `EngineRunner` ~2,450 lines) is not started and is
deliberately lowest priority.

**Nothing in either workstream is deployed.**

---

## 2. Last verified commit

`126c9cf` — the resolver phase (see §3 below for what was run against it). Preceded by `7a1f6e4`,
`34a4765` (§3 conformance), `cc53bba` (architecture migration), `97d6bbb` (RFC 0001).

Branch `feat/exec-completeness`, **not pushed**.

The VPS build was **not measured this session**. ROADMAP.md said `8cee4e9` and this file
previously said `4e9f125`; both are prose, and prose is how the last deployment-state error
survived a week. `curl /api/health` on the box is the only answer.

---

## 3. Last acceptance command and its output

```
$ .venv/bin/python -m pytest tests research_tests -q
PYTEST EXIT: 0          (0 FAILED, 0 ERROR — grepped, not eyeballed)
   collected 2,424 (--collect-only, summed per file)

$ .venv/bin/python scripts/dryrun.py 700
  RECONCILE cash vs expected: 187,733.06 vs 187,733.06  (diff -0.0000)
  LEDGER OK ✓
DRYRUN EXIT: 0

$ .venv/bin/python scripts/backtest_smoke.py
  net<gross where charged : OK ✓
  SWEEP OK ✓
SMOKE EXIT: 0

$ .venv/bin/python -m pytest tests/test_ir_conformance.py tests/test_ir_corpus.py \
      tests/test_ir_contract_c13.py tests/test_ir_resolution.py -q
EXIT: 0   (122 tests)
```

Guards proven able to fail, not merely observed passing:

- Suppressing **each of C1–C11, C14, C15** one at a time turns that clause's **own** test red —
  swept all of them (`scratchpad/sweep_c.py`, reproduced by re-writing the same one-line
  mutations). The sweep caught a **vacuous test of its own**: C2's no-mutation check deep-copied
  the shared fixture *after* earlier tests had already resolved it, and a resolver that eats its
  input does so on the first call and is idempotent after. It now also resolves the shared
  specification and asserts it is still intact.
- C12 proven red by planting a second `ResolvedGraph(` construction in `app/engine/`.
- C13 proven red (previous phase) by planting `if strategy.is_marketplace:` in
  `app/engine/exit_monitor.py`.
- The whole of F1–F13 was swept in the previous phase.

> Note for the next session: `python` is not on `PATH` — use `.venv/bin/python` from `backend/`.
> A backgrounded `python … | tail` returns the **pipe's** exit code; capture `$?` from pytest
> directly. Under `-q` this suite's final "N passed" line does not reach the log, so exit code
> and a `grep -cE '^FAILED|^ERROR'` are the evidence, not a summary line.

---

## 4. Next concrete action

**The component runtime — the first of the eight remaining Strategy-OS subsystems.** Spec →
plan → build, as each of them needs.

The resolver produces a `ResolvedGraph` of leaf nodes with bound parameters, composed warmup,
transitive cache identities and a domain per node. Nothing consumes it. That is this codebase's
defining defect one move away from happening again, so the next phase is the consumer: an
evaluator that walks a resolved graph and produces the series each node declares, with C10's
warmup and C11's completed-candles-only rule as its contract.

Two things are deliberately **not** next, and neither is a blocker:

1. **Adopting the resolver in the live engine** is RFC 0001 Appendix C(d). It is a production
   change to a real-money path, it needs its own parity evidence, and it stops for owner
   acknowledgement before any deploy. Build the runtime against backtest data first.
2. **Deploying the architecture migration.** Eight phases are committed, verified, and not on
   the box. `deploy.sh` refuses a dirty tree, which is the only reason they have not shipped;
   that reason is gone. It touches sizing, exits and order routing — all three stop for owner
   acknowledgement under the live-money rule, regardless of green tests. **This is the one item
   that genuinely needs the owner and has needed them for two sessions.**
