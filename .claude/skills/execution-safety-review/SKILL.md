---
name: execution-safety-review
description: Required for changes to execution, deployment, authority, binding, orders, fills, positions, accounting, reconciliation, or paper/live separation in Strategy OS. Enforces the money invariants and demands independent review before closure.
---

# Execution safety review

This is the part of the system that moves real money and it is not greenfield — it evolved from a
bot that has been trading Indian markets since 2026-06-29.

## Before changing anything

Read `.claude/rules/execution-safety.md` (auto-loads in this area) and the ADR that governs what
you are touching: **0011** adoption gates · **0012** execution-state ownership and attribution ·
**0013** research approval is admission, not a lease. These questions are settled. Re-opening one
needs evidence, not preference.

## The checklist

For each, state how your change preserves it — or stop:

1. Ledger reconciles to the paisa (`scripts/dryrun.py 700` → LEDGER OK).
2. ARM gates entries only; exits fire regardless of arm state.
3. Paper/live structural separation; book resolution fails closed to `live`.
4. Canonical binding is the single decision of what runs where; source and mode are recomputed at
   the point of use against `GRANTS`.
5. Requested assignment ≠ resolved executable strategy — a refusal skips the instrument and
   substitutes nothing.
6. Exact attribution: the binding that produced a signal reaches the fill and the money record.
7. Authority withdrawal withdraws the signals that authority authored.
8. Exact content-address match when authority is granted or re-granted.
9. `(ir_graph, live, authoritative)` remains absent — **owner gate**.
10. Execution stays provenance-blind (C13): no branch under `app/engine/` on where logic came from.

## Evidence required

- Focused tests for the changed behaviour, each proven able to go red by a mutation, restored
  byte-for-byte afterwards.
- `dryrun.py 700` LEDGER OK and `backtest_smoke.py` SWEEP OK.
- The full backend + research suite when a shared schema, runtime or safety boundary moved.
- Migration head recorded if the schema changed.

## Independent review

Dispatch **`execution-safety-reviewer`** on the diff. Do not review your own execution change —
the two defects this area produced most recently (a stale signal surviving authority withdrawal,
and option fills written with a NULL strategy key) both looked correct to their author.

## Deployment

Local implementation, testing and commits continue freely. **Deployment stops for explicit owner
acknowledgement** whenever execution, routing, sizing, exits or live behaviour is affected — even
with every test green. That rule sits above this skill's criteria and cannot be discharged by them.
