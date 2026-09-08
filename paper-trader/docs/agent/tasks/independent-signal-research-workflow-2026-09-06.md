---
{
  "id": "independent-signal-research-workflow-2026-09-06",
  "phase": "V0",
  "status": "historical_evidence_summary",
  "kind": "non_executable_evidence_summary",
  "goal": "Preserve the bounded local signal and iterative-research evidence below, including its open integration work; this summary does not start an implementation task.",
  "risk_tags": [
    "research_evidence",
    "historical_provenance"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/STATUS.md",
      "reason": "Current integration and release claims belong to the maintained status record."
    }
  ],
  "allowed_paths": [],
  "nonclaims": [
    "No current V0 completion or deployed-journey acceptance.",
    "No new commit, push, deployment, live credential or order authority.",
    "Signal agreement is limited to the recorded strategy and rows; synthetic data demonstrates workflow mechanics only."
  ],
  "owner_gates": [
    "Deployment, live credentials, live money and destructive actions require explicit permission."
  ],
  "stop_conditions": [
    "Do not treat this historical summary as an active assignment or expand its recorded evidence scope."
  ],
  "model_route": {
    "owner": "user-selected",
    "owner_reasoning_effort": "user-selected"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Retain the named evidence and limitations without presenting historical verification as current release acceptance."
  ],
  "test_plan": [
    "This summary authorizes no new run. Verify a concrete future candidate through the current assignment and retain the open integration gaps listed below."
  ],
  "review": {
    "required": false,
    "base_sha": "UNKNOWN_HISTORICAL_BASE",
    "assignment_id": "independent_signal_research_workflow_summary",
    "review_paths": [
      "paper-trader/docs/agent/tasks/independent-signal-research-workflow-2026-09-06.md"
    ],
    "exclude_paths": [],
    "reason": "Historical evidence summary, not an executable capsule or new acceptance decision."
  }
}
---

# Independent signals and iterative research

6 September 2026. Audience: the next Strategy OS implementation/release owner. Evidence level: **bounded local journey verified; V0 and deployment remain unfinished**.

## Verified outcome

A separate standard-library Python model recalculates EMA, population deviation, z score, slope and four strict entry/exit flags. Four UI-saved versions over retained NIFTY 50 and RELIANCE history produced **7,936 comparisons with zero mismatches** (248 rows per instrument). Prefix checks passed. An independent reviewer recalculated the flags and checked timestamps, closes, parameters and source hashes.

An actual UI-queued RELIANCE worker run also matched the independent signals and batch/incremental evaluation on all requested rows. Its four development trades did not meet the minimum ten. The UI shows that failure without claiming later validation.

A distinct, explicitly synthetic 240-row control exercised the positive workflow:

- Discover saved numeric compound parameters during Backtest and choose run-only axes.
- Evaluate EMA 8/9/10; inspect every development score and the isolated/mixed neighborhood reading at 10%/20% display tolerance.
- Review selected EMA 8, explicitly save version 2, and inspect the updated compound in Build.
- Rerun version 2 on the identical explicitly selected data with EMA 7/8/9. Unchanged parameters reproduce the exact earlier score and trade count. A tie retains baseline 8.
- Explicitly save the tied EMA 7 alternative through the review form; successful publication now opens Build automatically. Version 3 was not rerun.

Both optimized runs remain archived after failed minimum out-of-sample trade and PBO gates. Synthetic results prove mechanics, not a market edge. Signal agreement is limited to the tested strategy/rows, not every position, fill, charge, component or provider.

## Integrated fixes and checks

The slice adds parameter discovery, neighborhood comparison, exact baseline/candidate-delta acceptance guards, attributable V2 result parsing and useful rejection explanations. It fixes API/worker build-identity disagreement, cold-import lease expiry, compound market-field extraction, original-primitive fanout declarations, synchronous CSV import acknowledgement and a cancellation race. The existing research bounds and execution gates remain in force.

Evidence root: `.agent/runs/strategy-research-journey-2026-09-06/`.

| Evidence | What it proves |
| --- | --- |
| `REPORT.md`, `reconciliation.json`, per-date signal CSVs | Exact real-data signal comparison and its scope |
| `ui-worker-signal-reconciliation.json` | Real UI-queued worker consumed the requested closes and matched flags |
| `control-worker-v1-reconciliation.json`, `control-worker-v2-reconciliation.json` | Actual synthetic candidate evaluations match independent flags |
| `ui-run-3-evidence.json`, `ui-run-4-evidence.json`, `iteration-comparison.json` | Candidate scores, unchanged split, accepted-only document deltas and repeatability |
| `accepted-ema8-builder.png`, `accepted-ema7-automatic-builder.png` | Visible saved parameters and final navigation, supported by persisted-document checks |
| `quality/coverage.log`, `quality/backend-restored.log` | 434 affected frontend tests and 11 selected restored-source backend checks passed |
| `quality/frontend-quality.json`, `quality/backend-quality.json` | 66 frontend/five backend affected functions meet declared complexity, Halstead and actual-coverage CRAP thresholds |
| `quality/frontend-mutations.json`, `quality/backend-mutations.json` | 26 selected semantic mutants killed; no survivors in that population, not exhaustive repository mutation coverage |
| `quality/typecheck.log`, `quality/oxlint.log`, `independent-review.md` | Current typecheck/scoped lint pass; SPEC PASS, QUALITY PASS and bounded risk boundary CLEAN |

No dead or redundant changed code was identified in independent review. No commit, push, deployment, live credential or order action was performed. Before release, the release owner must verify the packaged API/worker identity and cold-start behavior on the concrete candidate.

## Open integration work

1. Restore the exact V2 dataset mapping/cutoff across page/version remounts. The current warning is truthful; the verified rerun manually reselected identical data.
2. Forecast the existing one-year eligibility limit before queueing. The oversized synthetic control was refused and is not counted as a pass.
3. Preserve the explicit baseline-qualification prerequisite: neighboring candidates are not evaluated when the baseline fails.
4. Verify numeric result visualization for a suitable recorded run, Monte Carlo, current monitoring-to-alert activation and broad watchlist/NSE operation. Those journeys are not proved here. Provider-first publication remains with its active owner.
5. Keep reusable-group authoring polish deferred while retaining existing compounds. Complete the remaining release and deployed-journey evidence before a V0 completion claim.
