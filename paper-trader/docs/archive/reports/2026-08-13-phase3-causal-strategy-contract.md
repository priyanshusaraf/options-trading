# Phase 3 causal strategy contract — Task 12 closure report

**Report date:** 2026-08-14\
**Status:** **REJECTED / OPEN**

The Phase 3 Task 12 acceptance contract is not met. The bounded causal gate report is `failed`.
This is an evidence result, not a finding that causal admission itself is unsafe or complete.
Phase 3 must remain open.

## Evidence accepted for its narrow contract

| Check | Result | Evidence |
| --- | --- | --- |
| Focused causal gate | exit 0; 7 passed | `.agent/runs/phase3-task12/gate_closure/focused_causal_gate.log` |
| Causal and identity mutations | exit 0; 5 causal and 1 identity mutation killed; 0 survived | `.agent/runs/phase3-task12/gate_closure/causal_mutations.log` |
| PostgreSQL gate-child commands | exit 0 for both recorded commands | `paper-trader/docs/reports/phase3-causal-gate.json` |
| Scope and inherited-file audit | clean baseline diff check; protected manifest matched; future IR-v2 files excluded | `.agent/runs/phase3-task12/scope_audit/report.md` |

## Rejection reason

`paper-trader/docs/reports/phase3-causal-gate.json` records a failed bounded gate. Its broad
backend and research shards include nonzero exits and timed-out commands. The report summary is
preserved at `.agent/runs/phase3-task12/documentation_closure/report_summary.log`; full command
output remains in the gate evidence named by the JSON report. Passing focused checks, mutation
checks, and gate-child PostgreSQL commands cannot replace the required broad evidence.

The required one-shot broad command was also started with output at
`.agent/runs/phase3-task12/integration/full_backend_research.log`. It had already emitted failures
by 5% and did not complete after 6 minutes 44 seconds, so it was terminated and is failed evidence,
not a passing phase gate. No deployment was run or authorised.

## Required path to a new closure decision

1. Diagnose and resolve each reported broad failure and timeout within a future authorised slice.
2. Rerun the required broad backend and research gate once, retaining full command output under
   the capsule evidence path. It must complete successfully and non-vacuously.
3. Preserve passing focused, mutation, PostgreSQL, integrity, protected-hash, and future-file
   exclusion evidence, or rerun any evidence invalidated by the changes.
4. Build the review package only after the integrated evidence exists, then obtain the required
   critical SPEC and QUALITY verdicts.

## Authority and rollback boundary

This rejection does not grant any authority. `(ir_graph, live, authoritative)` remains outside
the Phase 3 authority boundary. Do not access live credentials or production data, deploy, change
live sizing/routing/risk/protection/execution semantics, or implement frontend work under this
report. For an existing paper-authority rollback, use its recorded controlled lifecycle and named
rollback target; do not bypass admission or replace the binding. Existing risk-reducing exits
remain available.

## Nonclaims retained

Phase 3 causal admission does not prove market truth, numeric validity, point-in-time rulebooks,
provider capability, dynamic derivative selection, resource fit, Strategy Preflight, or
production readiness. It does not adopt or validate the excluded Component IR v2 plan and
specification.
