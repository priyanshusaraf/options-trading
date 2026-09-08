---
{
  "id": "strategy-os-v0-local-release-output-exit-race-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_bounded_replanned_correction",
  "goal": "Close the exhausted Q14 fast-exit output-overflow race without changing the accepted local evidence contract, runtime, schema, dependencies or readiness claim ceiling.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Configured-cap-plus-one fast-exit output is always classified output_overflow with return code 125 after pump join, tracked descendants are cleaned up safely, all prior Q14 gates remain green, and one fresh Critical reviewer returns SPEC PASS and QUALITY PASS."
  },
  "risk_tags": ["critical", "deployability-evidence", "process-lifecycle", "output-bounds", "false-pass"],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-local-release-operations/review/recheck-verdict.json",
      "sections": ["verdicts", "finding_recheck", "smallest_corrective_direction", "remaining_nonclaims"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-local-release-output-exit-race-replan/decision.json",
      "sections": ["blocking_finding", "decision"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md",
      "sections": ["Deterministic offline local release-operations evidence", "Owner evidence state"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Current verdict", "Open obligations", "Strategy OS V0 release audit and accelerated plan"]
    }
  ],
  "dependency_gate": "Exhausted Q14 recheck preserved at SHA-256 5fb543b1b345b72ace441b5f98cbf8b419d1346e46738ccad3103726baaf5a9d and REPLAN PASS decision sealed.",
  "allowed_paths": [
    "paper-trader/backend/scripts/v0_local_release_evidence.py",
    "paper-trader/backend/tests/test_v0_local_release_operations.py",
    "paper-trader/backend/research_tests/test_v0_local_release_operations.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-output-exit-race-correction.md",
    ".agent/runs/strategy-os-v0-local-release-output-exit-race-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-output-exit-race-correction.md",
    ".agent/runs/strategy-os-v0-local-release-output-exit-race-correction"
  ],
  "protected_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md",
    ".agent/runs/strategy-os-v0-local-release-operations",
    "paper-trader/backend/app",
    "paper-trader/backend/migrations",
    "paper-trader/backend/requirements.txt",
    "paper-trader/backend/requirements.lock",
    "paper-trader/backend/requirements-research.txt",
    "paper-trader/backend/scripts/postgresql_backup_restore.py",
    "paper-trader/backend/scripts/verify_postgresql_restore.py",
    "paper-trader/backend/scripts/copy_sqlite_to_postgres.py",
    "paper-trader/backend/scripts/run_disposable_postgres.py",
    "paper-trader/backend/scripts/run_research_worker.py",
    "paper-trader/backend/tests/conftest.py",
    "paper-trader/backend/research_tests/conftest.py",
    "paper-trader/docker-compose.postgres.yml",
    "paper-trader/scripts",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend"
  ],
  "scope": [
    "After both output pumps join, recheck their shared overflow fact before constructing any completed outcome; overflow dominates a zero leader return code and forces termination=output_overflow plus returncode=125.",
    "Keep retained stdout/stderr truncated to the declared cap with exact recorded byte count/digest semantics; never emit a PASS receipt for truncated evidence.",
    "Define bounded cleanup for the process group created by this runner when overflow is discovered after leader exit. Prove stubborn descendants terminate and an unrelated process group is never signalled.",
    "Add repeated configured 8 MiB plus one byte immediate-exit regression, reduced-cap stress coverage, restart/verification checks and a genuine mutation that removes the post-join overflow dominance.",
    "Preserve every closed F1/F2/F3 subfinding, exact resource/query policy, locally_runnable ceiling and all nonclaims."
  ],
  "acceptance": [
    "At least 20 reduced-cap and 6 configured-cap immediate-exit runs classify output_overflow/125 with zero false completed results.",
    "Timeout, sustained-output and memory overflow still perform bounded TERM then KILL for stubborn child groups; post-exit overflow cleanup leaves no tracked descendants.",
    "A reviewer-controlled unrelated process group remains alive and receives no signal during post-exit cleanup.",
    "Focused Q14 tests, semantic forgery probes, SQLite and disposable PG16 evidence, SIGINT INCOMPLETE verification, Q06, determinism, resources and protected manifests pass.",
    "Removing only the post-join overflow recheck reproduces the original false PASS and exact source bytes are restored.",
    "One fresh independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": [
    "Reproduce the sealed 8 MiB+1 fast-exit counterexample before mutation, add deterministic reduced/configured-cap regressions, then make the smallest runner correction.",
    "Run focused tests and independent process-tree/adversarial probes before the complete prior Q14 SQLite/PG16/SIGINT/determinism/protected evidence package."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root/v0_local_release_output_exit_race",
  "required_skills": ["executing-strategy-os-slices", "auditing-strategy-os-deployability", "risk-weighted-verification"],
  "review": {
    "required": true,
    "assignment_id": "v0_local_release_output_exit_race_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "The original false PASS corrupts release evidence and the prior capsule exhausted its only recheck.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-local-release-output-exit-race-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/scripts/v0_local_release_evidence.py",
      "paper-trader/backend/tests/test_v0_local_release_operations.py",
      "paper-trader/backend/research_tests/test_v0_local_release_operations.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-output-exit-race-correction.md",
      ".agent/runs/strategy-os-v0-local-release-output-exit-race-correction"
    ],
    "exclude_paths": ["paper-trader/backend/app", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts"],
    "output": ".agent/runs/strategy-os-v0-local-release-output-exit-race-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Standing V0 development authority and the sealed REPLAN PASS permit only this bounded correction; no routine user token is required.",
    "A passing local evidence tool remains locally_runnable only and cannot authorize deployment."
  ],
  "stop_conditions": [
    "A runtime, schema, migration, dependency, service, deploy script or protected evidence-owner byte must change.",
    "Safe descendant cleanup requires a new OS/process-supervision dependency or broad process authority.",
    "The exact fast-exit race cannot be made deterministic without weakening the output cap or artifact truth."
  ],
  "deployment_impact": {
    "classification": "evidence-only local operations correction; no runtime, schema, migration, dependency, service or deployment change",
    "highest_possible_claim": "locally_runnable"
  },
  "nonclaims": [
    "No release deployability, production rehearsal, signed artifact, provider/legal approval, deployment, live/order/money authority or whole-V0 completion.",
    "No change to the current bot, VPS, PostgreSQL schema, application runtime or external infrastructure."
  ],
  "final_review": {
    "verdict": "SPEC PASS / QUALITY PASS",
    "verdict_path": ".agent/runs/strategy-os-v0-local-release-output-exit-race-correction/review/verdict.json",
    "verdict_sha256": "974d2659f2b17d4880e23d55ae473d2d84acad4a583cd1a1e241ed20f5a3c1ba",
    "review_package_sha256": "344ed0f1c98726d988a25b9c1dce3715fb5045277fdde361bc075ef5ece9fd79",
    "dirty_tree_fingerprint": "1264b3101485b90050e2a8ec737ce9dd634a7c9f9c1ee65136cb24e5462a92a4",
    "findings_open": 0,
    "highest_readiness_level": "locally_runnable",
    "deployment": false
  }
}
---

# Q14 output-exit race correction

Close only the fast-exit overflow false-PASS race under a fresh review cycle.
