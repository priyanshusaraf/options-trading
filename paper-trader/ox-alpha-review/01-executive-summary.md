# 01 — Executive Summary

**Date:** 2026-08-21 · **Reviewer:** ox-alpha · **Basis:** direct disk verification in
`.claude/worktrees/codex-execution-foundation` at HEAD `de6faae` + dirty tree. Evidence paths in
[`02-claim-verification.md`](02-claim-verification.md).

## Verdicts

| Question | Verdict |
|---|---|
| Is the Codex run summary truthful? | **Yes** — every checkable claim verified; one material omission (suite cannot collect) |
| Is Phase 1–4 work real and sound? | **Yes, at its declared boundary** — final-review-5 PASS is genuine and properly scoped as local-only |
| Is the foundation audit right to say BLOCKED? | **Yes** — A-01 (migration triggers) and A-02 (boolean OHLC) are real, verified at code level |
| Is the current deadlock a knowledge problem? | **No — it is a process problem.** The harness became self-referential; see `03` |
| Can Phase 5 open without Recovery 9 succeeding? | **Yes**, via the narrowed-contract route in `03` §4 |
| Is the architecture worth keeping? | **Yes — KEEP + HARDEN**, agreeing with the Codex assessment |
| Real money today? | **No.** Research/paper only until the named gates close. This matches the frozen preaudit's own posture field |

## The five things that matter most, ranked

1. **Commit the tree.** 374 uncommitted entries, 162 modified tracked files (+12,226/−1,523 lines),
   ~4 days of programme state existing only as working-tree bytes. The entire governance system pins
   SHA-256s of files that git does not protect yet. One bad checkout command loses it. This is the
   single highest-severity operational risk in the project right now and it costs one afternoon.
2. **Fix A-02 (boolean → price) as a normal bounded slice.** `float(True) == 1.0` crosses provider
   preparation (`dhan.py:226-230`) and the dataset encoder (`dataset_store.py:646-648`) before type
   validation. Small, dangerous, fully specified by the audit, unblocks trust in every numeric
   identity downstream. Do not gate it on the harness.
3. **Break the migration deadlock by owner decision, not by a tenth recovery.** Narrow the supported
   migration contract explicitly (fresh-install + forward-replay + seeded corpus; restore-based for
   older states), then fix A-01 as an ordinary product slice. The audit itself offers this exact
   off-ramp ("explicitly narrow the supported contract with safe operational handling").
4. **Retire the self-referential sealed-package evidence lifecycle for this class of work.** Move
   permanent regressions into `tests/` under CI. The INITIIAL_COMPLETE→ROOT_ACCEPTED sealing
   lifecycle is the machine that manufactured nine rejections. Codex's own fallback ("split the
   harness into smaller independently specified components") is correct — do it now, not after
   Recovery 9 fails.
5. **Restore suite collectability.** Two collection errors today:
   `ImportError: DeclaredNativeAdapter` (`test_foundation_research_projection_contracts.py:26`) and
   `RuntimeError: slow-shard replacement drifted for broad_tests_15`
   (`scripts/phase3_causal_gate.py:389`). Until the tree collects, no green/red claim about current
   bytes is verifiable by anyone.

## What "solidify the foundations" should mean concretely (your stated objective)

- Fix the two product defects (A-01, A-02) with permanent adversarial regressions in CI.
- Close the evidence gap by narrowing contracts rather than proving universes.
- Make the uncommitted state impossible to recur: commit-per-capsule on the codex branch.
- Add the *leading* reliability indicators now that AWS removes the droplet constraint: explicit
  pool sizing, pool saturation telemetry, request deadlines, provider rate budgets surfaced to
  users **before** activation (this is your "10 API calls/sec must be known beforehand"
  requirement — it has a natural home in the existing capability vocabulary; details in `05`).
- Keep every owner gate exactly as-is. They are the reason eight false-green harnesses never
  reached acceptance.

## What I did NOT verify

Runtime behaviour (nothing was started), the live VPS bot's health (docs forbid asserting it from
prose; nothing here claims it), full-suite pass/fail on current bytes (cannot — collection fails),
and the ~60 individual capsule documents beyond what `CURRENT.md`/`PROGRAMME.json`/the audit
summarize. Everything else in these documents carries a file path you can check.
