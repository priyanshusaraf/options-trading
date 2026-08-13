# Task 11 brief: execution attribution and legacy quarantine

## Classification

**Critical.** A defect can open new exposure without causal authority, misattribute money state,
or rewrite the provenance of a late fill.

## Scope

Execute Task 11 from the accepted Phase 3 plan and design section 9.3. Require a current
owner-local admission receipt at the final pre-entry boundary. Propagate the exact immutable
`admission_address` through execution intent, position, trade, late-fill adoption, journal, and
recovery paths. Existing legacy positions may exit, protect, reconcile, and recover, but may not
grant new exposure. Add the dry-run-first exact backfill CLI with one explicit predicate per
consumer and quarantine every row whose historical proof is incomplete.

## Risk-weighted verification

- Do not build a matrix for its own sake. Every test must name a concrete money, provenance, or
  tested-vs-live divergence hypothesis.
- Prove the last pre-exposure gate independently of earlier deployment checks.
- Prove intent, paper position, late-fill position, and trade propagation at their owning seams.
- Prove null legacy positions can exit while new entry stays blocked.
- Prove backfill never uses current mutable deployment state as historical evidence.
- Run affected tests during implementation and the named Task 11 subsystem boundary before freeze.
  Keep individual commands under 60 seconds; split them when needed.

## Required mutation kills

Kill exactly these guard removals: execution binding receipt verification, live intent receipt
copy, paper position receipt copy, late-fill receipt copy from original intent, trade receipt copy,
and backfill exact-history predicate. Do not let an earlier guard mask the seam under mutation.

## Safety and git

Do not edit, stage, reset, or commit the four protected inherited files. Keep Task 11 unstaged
until independent review returns SPEC PASS and QUALITY PASS.
