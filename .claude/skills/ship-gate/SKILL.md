---
name: ship-gate
description: Run before declaring any meaningful Strategy OS slice complete. Checks that the intended behaviour actually exists, that evidence is proportional and non-vacuous, that an independent reviewer looked, and that no owner gate was crossed.
---

# Ship gate

Answer every line with evidence or an explicit N/A and the reason. "Probably fine" fails the gate.

## Behaviour

1. **Does the intended behaviour actually exist?** Name the observable difference and how you
   observed it. Not "tests pass" — what *changed* that a user or operator could see.
2. **Are the acceptance criteria satisfied**, as written in the workstream document or the task?
3. **Behavioral evidence beyond tests**: a driven UI flow, an adapter response, a before/after
   number, a reproduced-then-fixed wrong value. Which one applies here, and where is it?

## Automated evidence

4. **Targeted tests** for the changed contract, each proven able to go red by a mutation that was
   then restored.
5. **A regression test for every bug fixed** — one that fails before the fix.
6. **Verification proportional to the blast radius.** Focused + affected-workstream regression by
   default. Full backend + research suite, `dryrun.py 700` (LEDGER OK) and `backtest_smoke.py`
   (SWEEP OK) **only** when a shared schema, runtime or safety boundary moved. Do not run the whole
   repo for a typo — that is waste, not rigour.

## Review

7. **An independent reviewer looked** — the agent matching the domain touched
   (`execution-safety-reviewer`, `security-tenancy-reviewer`, `research-leakage-reviewer`,
   `ui-verifier`, `architecture-critic`). Findings fixed or explicitly declined with a reason.
8. **Security implications** considered: does this widen what a caller can reach, read, or cause?

## State

9. **Migration head** recorded if the schema moved (`python -m app.db.migrate head`).
10. **Documentation is not stale.** `docs/CONTINUE.md` is the resume point and is rewritten every
    stop. Did an invariant, a contract or a measured number change?
11. **The diff contains nothing unexpected** — `git status --short` and `git diff --stat` read and
    understood. No stray scratch files, no unrelated refactor riding along.

## Gates

12. **Owner gates**: live IR authority · live sizing/routing/risk semantics · the live VPS or its
    credentials · destructive DB operations · licence-sensitive code adoption · regulatory or
    customer-money decisions. If one is in reach, **stop and say so** — finish everything else.
13. **Exact-head CI** is green for the commit being closed, not for an earlier one.

## Then

State plainly what is done, what is verified, what is unverified, and what you deliberately left
out. If something failed, say so with the output.
