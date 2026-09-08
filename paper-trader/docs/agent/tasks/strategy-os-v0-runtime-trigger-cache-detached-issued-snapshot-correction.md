---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_fresh_detached_verified_snapshot_correction",
  "goal": "Eliminate the verify-then-read interval by making every issued-fact verifier return a detached canonical snapshot of the original issued state and requiring consumers to read only that snapshot.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Issued registry stores a deep exact original state; verification checks live identity, original fingerprint and current shape, then returns a non-issued detached clone built from the original state; deterministic barriers changing the shared object after verification cannot affect event, gate, ceiling or cache consumers; focused/affected evidence and one fresh Critical review pass."
  },
  "risk_tags": ["critical", "runtime-causality", "concurrency", "immutable-snapshot", "cache-identity", "resource-policy", "tenant-isolation"],
  "depends_on": ["strategy-os-v0-runtime-trigger-cache-issued-state-seal-correction"],
  "dependency_gate": {
    "predecessor_recheck_verdict_sha256": "d700b54e5cfcfc1c4463e50100ff4daba1b33f2e8edf2b00e214b43075125e27",
    "open_finding": "V0-RTC-ISS-CR-001",
    "rechecks_remaining": 0,
    "decision": "KEEP + RETURN DETACHED ORIGINAL-STATE SNAPSHOTS"
  },
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-runtime-trigger-cache-issued-state-seal-correction/review/recheck-verdict.json", "sections": ["all output"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-runtime-trigger-cache-issued-state-seal-correction.md", "sections": ["first_review", "correction_result", "exhausted_recheck"]},
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Staged graph execution and cache contract", "Verification and deployment decision"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/ir/evaluation_schedule.py",
    "paper-trader/backend/tests/test_v0_evaluation_schedule.py",
    "paper-trader/backend/tests/test_v0_runtime_cache_identity.py",
    "paper-trader/backend/tests/test_v0_runtime_trigger_cache_foundation.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction.md",
    ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction.md",
    ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/market_data/runtime_cache_identity.py",
    "paper-trader/backend/app/ir/resource_plan.py",
    "paper-trader/backend/app/ir/incremental_runtime.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/market_data/eligibility.py",
    "paper-trader/backend/app/market_data/capability.py",
    "paper-trader/backend/app/market_truth",
    "paper-trader/backend/app/backtest",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/monitoring",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Issued registry entries retain an exact deep canonical copy of every original field in addition to weak live identity and fingerprint. No retained state aliases caller-owned mutable storage.",
    "Verification checks exact live object issuance, exact runtime shapes, unchanged original fingerprint and current self-validation, then constructs a detached non-issued fact from the stored original fields. It never returns the shared issued object.",
    "Event admission, conditional compilation, gate admission, resource preflight and cache consumers assign and read only the verifier-returned detached snapshot. A concurrent change to the shared issued object after verification cannot affect the local operation.",
    "Detached snapshots are not authority inputs to a later verifier; callers must retain/recompile the original issued fact. Snapshot addresses and fields equal the original issued state.",
    "Current exact-type guards, process-local issuance, fresh recompilation, resource ceilings, UNSUPPORTED option-depth state and cache product bytes remain unchanged."
  ],
  "acceptance": [
    "A deterministic barrier after the real schedule verifier returns changes shared declared triggers/address to tick; event admission still uses the original completed_bar snapshot and refuses tick.",
    "The same barrier changes shared owner/assignment/graph/plan/unit/freshness fields; derived, evaluation and static cache consumers use the original detached snapshot and cannot bind the changed state.",
    "A deterministic barrier after gate/conditional/ceiling verification changes the shared fact and recomputes its address; gate admission, static cache and resource preflight use the original snapshot only.",
    "Returned detached snapshots equal original canonical addresses/fields, are not in the issuance registry, and refuse if passed as authority to another verifier.",
    "Fresh process recompilation yields equal addresses and accepted new issued facts; no serialization, persistence or cross-process object authority is introduced.",
    "Prior 62 schedule, 111 cache, 5 root and exact-type cases remain; affected/resource/protected/architecture gates pass; cache product remains byte-identical.",
    "Two isolated mutations return the shared object or alias original state and are killed/restored.",
    "One fresh independent Critical SPEC/QUALITY review passes."
  ],
  "test_plan": [
    "Schedule owner adds RED deterministic synchronization hooks around verifier return and detached clone construction, then the smallest issued-state deep-copy/snapshot correction.",
    "Cache test owner adds deterministic consumer barriers without changing cache product.",
    "Root runs integrated/affected/resource/protected gates and a fresh Critical review."
  ],
  "risk_classification": {"tier": "Critical", "reason": "Reading a shared object after verification can change trigger, tenant, resource or cache meaning between check and use."},
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "v0_detached_issued_snapshot",
      "agent": "worker",
      "mode": "implementation",
      "depends_on": [],
      "write_paths": ["paper-trader/backend/app/ir/evaluation_schedule.py", "paper-trader/backend/tests/test_v0_evaluation_schedule.py", ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction/v0_detached_issued_snapshot"],
      "output": ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction/v0_detached_issued_snapshot/report.md"
    },
    {
      "id": "v0_detached_snapshot_cache_consumers",
      "agent": "worker",
      "mode": "test-only",
      "depends_on": ["v0_detached_issued_snapshot"],
      "write_paths": ["paper-trader/backend/tests/test_v0_runtime_cache_identity.py", ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction/v0_detached_snapshot_cache_consumers"],
      "output": ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction/v0_detached_snapshot_cache_consumers/report.md"
    }
  ],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "implementation_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PENDING",
    "schedule_focused": 68,
    "cache_focused": 115,
    "root_integration": 5,
    "integrated_focused": 188,
    "affected_passed": 352,
    "affected_skipped": 0,
    "affected_failures": 0,
    "resource_probe": {"runs": 50, "deterministic_address_sets": 1, "elapsed_seconds": 2.0307, "peak_traced_bytes": 804567},
    "protected_repo_files": 351,
    "protected_external_frontend_files": 996,
    "protected_deltas": 0,
    "architecture_files": 438,
    "cache_product_changed": false,
    "report": ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction/report.md"
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_sha256": "1ecd19da754da7ec1b2c0c67dd28045963245ffc392373445df407efe7caf9a8",
    "open_findings": ["V0-RTC-DET-CR-001", "V0-RTC-DET-EG-001"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PASS",
    "mutable_timezone": "refused before event issuance; retained timestamps rebuild with datetime.timezone.utc",
    "cache_barriers": ["derived", "evaluation_result", "static_schedule", "static_gate"],
    "isolated_mutations": ["mutable_timezone_alias_killed_and_restored", "shared_verifier_return_killed_and_restored"],
    "protected_deltas": 0,
    "cache_product_changed": false,
    "rechecks_remaining": 0
  },
  "final_review": {
    "verdict": "SPEC PASS / QUALITY PASS / final PASS",
    "recheck_verdict_sha256": "edde1690ad3d7b69b77db14f1b36c31a697299a36e535ebcba0dd0d2866f6dfd",
    "closed_findings": ["V0-RTC-DET-CR-001", "V0-RTC-DET-EG-001"],
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "deployment": false
  },
  "review": {
    "required": true,
    "assignment_id": "v0_runtime_trigger_cache_detached_snapshot_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Verify-through-use concurrency protects causal trigger, tenant, resource and cache meaning.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction/review-package.json",
    "review_paths": ["paper-trader/backend/app/ir/evaluation_schedule.py", "paper-trader/backend/tests/test_v0_evaluation_schedule.py", "paper-trader/backend/tests/test_v0_runtime_cache_identity.py", "paper-trader/backend/tests/test_v0_runtime_trigger_cache_foundation.py", "paper-trader/docs/agent/tasks/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction.md", ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction"],
    "exclude_paths": ["paper-trader/backend/app/market_data/runtime_cache_identity.py", "paper-trader/backend/app/ir/resource_plan.py", "paper-trader/backend/app/ir/incremental_runtime.py", "paper-trader/backend/app/ir/runtime.py", "paper-trader/backend/app/market_data/requirements.py", "paper-trader/backend/app/market_data/eligibility.py", "paper-trader/backend/app/market_data/capability.py", "paper-trader/backend/app/market_truth", "paper-trader/backend/app/backtest", "paper-trader/backend/app/providers", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": ["Standing V0 authority permits this fresh bounded correction.", "No provider/network/right decision, cache product edit, persistence/schema, monitoring/Paper activation, frontend, deployment, live/order or money action."],
  "stop_conditions": ["Detached snapshot requires protected cache product or persistence/signature/dependency changes.", "Snapshot aliases caller state or becomes reusable authority.", "Current unsupported options/depth is promoted."],
  "deployment_impact": {"classification": "compatible in-process concurrency hardening; no service activation", "required_evidence": "Deterministic barrier, restart, cache consumer, resource, protected and fresh Critical review.", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No cross-process serialized authority, cache backend, positive static options identity, provider readiness, monitoring runtime/API, Paper/live execution, frontend, release deployability, deployment or V0 completion."]
}
---

# Detached issued-snapshot correction

Verification returns an operation-local copy of the original issued state. Consumers
never read the shared issued object after the check.
