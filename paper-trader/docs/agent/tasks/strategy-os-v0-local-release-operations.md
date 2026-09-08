---
{
  "id": "strategy-os-v0-local-release-operations",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "rejected_replan_required",
  "goal": "Implement a deterministic offline local release-operations evidence CLI over existing boot, migration, restore, recovery and health contracts",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Exact scoped implementation, local SQLite/PG16/restart/restore/resource/mutation evidence and one independent SPEC PASS/QUALITY PASS. No deployment or whole-V0 claim."
  },
  "risk_tags": ["critical", "deployability", "recovery", "parallel-owned"],
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/05-ARCHITECTURE-AND-RELEASE-PROFILE.md", "sections": ["Required V0 profile", "Execution hard-disable", "Schema and migration approach", "Deployment impact"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md", "sections": ["Frontend and operations", "V0 deployment topology to prove", "Deployability gates"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "V1 release gate"]},
    {"path": ".agent/runs/strategy-os-v0-local-release-operations-materialization/contract.md", "sections": ["Boundary", "Evidence CLI", "Required proof"]}
  ],
  "dependency_gate": "strategy-os-v0-release-profile-foundation",
  "programme_assignment": {
    "assignment_id": "v0_local_release_operations",
    "queue_id": "Q14",
    "parent_stage": null,
    "owner_task": "/root/v0_local_release_operations",
    "primary_programme_owner": false,
    "prerequisite": "Q01 accepted and one reviewed parallel slot released; revalidate all stable inputs and seal a stage-specific owner route before ACTUAL START. No user token."
  },
  "allowed_paths": [
    "paper-trader/backend/scripts/v0_local_release_evidence.py",
    "paper-trader/backend/tests/test_v0_local_release_operations.py",
    "paper-trader/backend/research_tests/test_v0_local_release_operations.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md",
    ".agent/runs/strategy-os-v0-local-release-operations"
  ],
  "new_paths": [
    "paper-trader/backend/scripts/v0_local_release_evidence.py",
    "paper-trader/backend/tests/test_v0_local_release_operations.py",
    "paper-trader/backend/research_tests/test_v0_local_release_operations.py"
  ],
  "protected_paths": [
    "AGENTS.md", ".agents", ".codex", ".github", "paper-trader/docker-compose.postgres.yml",
    "paper-trader/scripts", "paper-trader/backend/app", "paper-trader/backend/migrations",
    "paper-trader/backend/research/domain", "paper-trader/backend/requirements.lock",
    "paper-trader/backend/requirements.txt", "paper-trader/backend/requirements-research.txt",
    "paper-trader/backend/alembic.ini", "paper-trader/backend/scripts/postgresql_backup_restore.py",
    "paper-trader/backend/scripts/verify_postgresql_restore.py", "paper-trader/backend/scripts/copy_sqlite_to_postgres.py",
    "paper-trader/backend/scripts/run_disposable_postgres.py", "paper-trader/backend/scripts/run_research_worker.py",
    "paper-trader/backend/tests/conftest.py", "paper-trader/backend/research_tests/conftest.py",
    "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": [],
  "stable_inputs_rebind_at_dispatch": false,
  "stable_input_rebind": {
    "path": ".agent/runs/strategy-os-v0-local-release-operations-materialization/stable-input-rebind.json",
    "status": "accepted",
    "actual_start": true
  },
  "scope": [
    "Implement the full closed local-evidence contract only in the three new product/test paths. Reuse existing boot/migration/restore/worker/health tools; no copied SQL/process authority or product runtime change.",
    "Preserve every existing source, migration, lock/dependency, workflow/compose/deploy and frontend byte. Never package or expose secrets/customer data; no external provider/infrastructure action.",
    "This queued capsule cannot START until Q01 acceptance, exact stable-input rebind, current-stage carry/ownership validation and a fresh Sol-medium/no-history/zero-agent owner route."
  ],
  "acceptance": [
    "Closed deterministic safe receipt over exact local operations facts, with direct negative/restart/restore/resource proof and no false readiness label.",
    "One coordinator-routed independent critical SPEC PASS and QUALITY PASS; historical release blockers remain explicit."
  ],
  "test_plan": [
    "Focused receipt/parser/preflight RED-GREEN, then existing release-profile/health/restore/migration/Q06 affected checks on SQLite and actual disposable PG16.",
    "Fresh-process determinism, process interruption/retry, redaction/exclusion, resource bounds and genuine isolated guard mutations with exact restoration."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "required_skills": ["executing-strategy-os-slices", "auditing-strategy-os-deployability", "database-migration-safety", "risk-weighted-verification"],
  "review": {
    "required": true,
    "assignment_id": "v0_local_release_operations_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "False local release evidence can corrupt migration/restore/operator decisions; one integrated critical review is required.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-local-release-operations/review-package.json",
    "output": ".agent/runs/strategy-os-v0-local-release-operations/review.md",
    "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md", ".agent/runs/strategy-os-v0-local-release-operations"],
    "exclude_paths": [], "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1
  },
  "first_review": {
    "review_task": "01a04d04-0a30-7243-8c10-2b34cb2c829e",
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-local-release-operations/review.md",
    "verdict_sha256": "de254df6f94d89c26fc4dd26d8a8a37e891be33f7b161050aaef14ffd5d64d88",
    "finding_ids": ["F1", "F2", "F3"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Bind exact CLI and focused-test bytes and recompute exact preflight_steps argv/order/count/timeout/attempted semantics, closed resource policy, readiness claims and retained result artifacts during verify-receipt; reject the sealed forged-PASS counterexample.",
    "Stream stdout/stderr into bounded retained reviewer-safe evidence files, record byte counts/digests and recompute them during verification; do not buffer unbounded output or discard successful evidence.",
    "Terminate the whole child process group on overflow/timeout, enforce and record a supported memory ceiling, and bind the applicable query-count authority/budget.",
    "Add complete protected-path start/final manifests with explicit concurrent-drift attribution, rerun determinism/SQLite/actual PG16/SIGINT/Q06/mutations, rebuild the corrected package and route the one allowed same-reviewer recheck."
  ],
  "correction_completion": {
    "status": "LOCAL CORRECTION PASS",
    "findings_closed": ["F1", "F2", "F3"],
    "report": ".agent/runs/strategy-os-v0-local-release-operations/correction/report.md",
    "evidence": ".agent/runs/strategy-os-v0-local-release-operations/correction/evidence.json",
    "package": ".agent/runs/strategy-os-v0-local-release-operations/correction/review-package.json",
    "receipt_sha256": "41a37e748bda186bcdb18f374520d99f2b7afe1e2e146cede54987798c1a1112",
    "focused_tests": 24,
    "focused_failures": 0,
    "focused_errors": 0,
    "focused_skips": 0,
    "protected_unattributed_deltas": 0,
    "q14_protected_path_writes": 0,
    "recheck_task": "01a04d04-0a30-7243-8c10-2b34cb2c829e"
  },
  "exhausted_recheck": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-local-release-operations/review/recheck-verdict.json",
    "verdict_sha256": "5fb543b1b345b72ace441b5f98cbf8b419d1346e46738ccad3103726baaf5a9d",
    "finding": "F3-OUTPUT-EXIT-RACE",
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "successor": "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-output-exit-race-correction.md"
  },
  "deployment_impact": {
    "classification": "evidence-only local operations tooling; no deploy/runtime/schema/dependency change",
    "release_assembly_owner": "strategy-os-v0-security-operations-deployability",
    "rollback": "No deployment. Remove only the new unaccepted CLI/tests after owner decision; never downgrade or alter persisted schema/data."
  },
  "owner_gates": ["Standing all-V0/parallel authority; no routine token. Exact slot/owner/stable-input seal still required before work."],
  "stop_conditions": ["Q01 review changes a stable input; produce a new sealed successor before dispatch.", "Any shared operational/runtime/schema/dependency change is required; reproduce and route separately before mutation."],
  "nonclaims": ["No deployability, production rehearsal, signed release, CI/hosting/service topology, provider/legal approval, deployment or whole-V0 completion."]
}
---

# Deterministic offline local release-operations evidence

Exact stable inputs are rebound and ACTUAL START is open. This remains local evidence tooling and authorizes no deployment.

## Owner evidence state

The single same-reviewer recheck is exhausted at SPEC FAIL and QUALITY FAIL. Its
`F3-OUTPUT-EXIT-RACE` counterexample is preserved under the review directory. The
original capsule is frozen rejected; only the separately routed output-exit-race
successor may change the owned evidence CLI/tests. No deployability or whole-V0
authority follows from the otherwise passing local receipt.
