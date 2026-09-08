---
{
  "id": "strategy-os-v0-signal-alert-attention-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_replanned_unpublished_contract_correction",
  "goal": "Correct the reviewed alert truth/freshness defects and replace vacuous protected evidence with a sealed complete successor baseline, without persistence, runtime, API, frontend or policy expansion.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "F1-F4 are closed by exact truth-table, freshness and protected-universe proof, all prior contract gates remain green, and one fresh Critical reviewer returns SPEC PASS and QUALITY PASS."
  },
  "risk_tags": ["critical", "monitoring-truth", "tenant-isolation", "provenance", "alert-idempotency"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-signal-alert-attention-contract/review/verdict.json", "sections": ["findings", "stopping_condition", "retained_nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-signal-alert-attention-contract/correction/f4-provenance-audit.md", "sections": ["Outcome", "Coverage audit", "Required next action"]},
    {"path": ".agent/runs/strategy-os-v0-signal-alert-attention-correction-replan/decision.json", "sections": ["blocking_findings", "decision"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-contract.md", "sections": ["Signal alert and attention contract"]},
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md", "sections": ["Conflict decisions", "Current V0 programme reconciliation"]}
  ],
  "dependency_gate": "REPLAN PASS plus sealed successor-start protected manifest; source capsule is rejected and its only recheck remains unused.",
  "allowed_paths": [
    "paper-trader/backend/app/monitoring/__init__.py",
    "paper-trader/backend/app/monitoring/contracts.py",
    "paper-trader/backend/tests/test_v0_signal_alert_attention_contract.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-correction.md",
    ".agent/runs/strategy-os-v0-signal-alert-attention-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-correction.md",
    ".agent/runs/strategy-os-v0-signal-alert-attention-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/core/deployments.py",
    "paper-trader/backend/app/ir/library.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/hashing.py",
    "paper-trader/backend/app/ir/first_party/monitoring_intent_v2.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence.md",
    "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-contract.md",
    ".agent/runs/strategy-os-v0-signal-alert-attention-contract",
    "paper-trader/frontend",
    "paper-trader/scripts/deploy.sh",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/.gitignore",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/.oxlintrc.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/README.md",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/index.html",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/tsconfig.app.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/tsconfig.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/tsconfig.node.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/vite.config.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src"
  ],
  "protected_manifest": {
    "builder": ".agent/runs/strategy-os-v0-signal-alert-attention-correction-replan/build_protected_manifest.py",
    "baseline": ".agent/runs/strategy-os-v0-signal-alert-attention-correction-replan/root/protected-successor-start-final.log",
    "status": "accepted_root_seal_before_start",
    "file_count": 385,
    "manifest_sha256": "acaa5d4c166929bb7d5de192daa6c51608c4300df50ae02db4172d4e902df532",
    "log_sha256": "1d565d18de9394e69740121d142e2621f9fa3f079b315a27ca6ac81ff5ab9568"
  },
  "scope": [
    "Permit SHORT-to-LONG BUY and LONG-to-SHORT SELL exactly as target-state transitions; retain the unsupported REVERSE operation refusal.",
    "Resolve refusal/missing/invalid/stale truth before valid HOLD, and add the crossed action-by-validity/freshness truth table.",
    "Carry the exact closed freshness fact into SignalAlert construction, serialization and content identity.",
    "Run the same deterministic alert/delivery/attention contracts and add genuine F1-F3 mutations with exact restoration.",
    "Rebuild protected proof from the root-sealed successor baseline and final manifest. Any unexplained mismatch stops the capsule; the original failed logs remain rejected evidence."
  ],
  "acceptance": [
    "Golden SHORT-to-LONG BUY and LONG-to-SHORT SELL derive one canonical alert; unsupported REVERSE remains refused.",
    "Every HOLD crossed with MISSING, INVALID, REFUSED or STALE yields the exact typed no-alert truth, while valid/fresh HOLD remains ordinary no-alert HOLD.",
    "SignalAlert contains and addresses exact freshness facts and preserves all prior strategy/instrument/time/reason/entry/SL/TP lineage.",
    "The root-sealed baseline resolves every declared protected source/config target without command errors; the final manifest matches except for independently attributed concurrent changes outside this capsule.",
    "Focused, affected, restart/serialization, 100,000-fact resource, tenant/sequence/time adversary and genuine mutation checks pass.",
    "One fresh independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": [
    "Add owner-authored F1-F3 RED fixtures before correction, then focused GREEN and isolated mutations.",
    "Run full prior alert compatibility/resource/restart suite, verify protected final manifest against root seal, then route fresh Critical review."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root/v0_signal_alert_attention_correction",
  "review": {
    "required": true,
    "assignment_id": "v0_signal_alert_attention_correction_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "The predecessor misstated transition/freshness truth and lacked protected provenance.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-signal-alert-attention-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/monitoring/__init__.py",
      "paper-trader/backend/app/monitoring/contracts.py",
      "paper-trader/backend/tests/test_v0_signal_alert_attention_contract.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-correction.md",
      ".agent/runs/strategy-os-v0-signal-alert-attention-correction"
    ],
    "exclude_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/frontend"],
    "output": ".agent/runs/strategy-os-v0-signal-alert-attention-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Start only after the root-sealed baseline exists and the capsule status becomes active.",
    "No persistence, migration, runtime, API, frontend, delivery integration, notification policy, registry, execution, money or deployment authority."
  ],
  "stop_conditions": [
    "The protected manifest misses a declared target, contains a command error or cannot attribute a final mismatch.",
    "Any protected/shared file must change or a reserved policy must be selected.",
    "F1-F3 cannot close without weakening typed invalid/no-alert or canonical identity rules."
  ],
  "deployment_impact": {"classification": "compatible unpublished contract correction; no schema, service, route, dependency or configuration change"},
  "nonclaims": [
    "No retroactive acceptance of the predecessor's failed protected logs.",
    "No persistence, runtime, API, frontend, delivery integration, admin/analytics, provider, execution, order, capital, PnL, deployment or V0 completion."
  ],
  "implementation_closure": {
    "verdict": "IMPLEMENTATION PASS PENDING FRESH CRITICAL REVIEW",
    "review_package": ".agent/runs/strategy-os-v0-signal-alert-attention-correction/review-package.json",
    "review_package_sha256": "1c26416460a056fa54e8311304e65e575f781cd4b9169ecc0fcae43bc0413da8",
    "report": ".agent/runs/strategy-os-v0-signal-alert-attention-correction/implementation-report.md",
    "report_sha256": "174a6080330052c178c499496475cf7e7e7e2a38d419489e80db50bf57d7c826",
    "review_task": "/root/v0_signal_alert_attention_correction_review",
    "protected_file_count": 385,
    "protected_manifest_sha256": "acaa5d4c166929bb7d5de192daa6c51608c4300df50ae02db4172d4e902df532",
    "persistence": false,
    "publication": false,
    "deployment": false
  },
  "final_review": {
    "verdict": "SPEC PASS / QUALITY PASS",
    "verdict_path": ".agent/runs/strategy-os-v0-signal-alert-attention-correction/review/verdict.json",
    "verdict_sha256": "25e3e331cffbf731380190a141c456406e80a4ad77f54c24b12b022845e4f4dc",
    "review_package_sha256": "1c26416460a056fa54e8311304e65e575f781cd4b9169ecc0fcae43bc0413da8",
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "findings_open": 0,
    "persistence": false,
    "publication": false,
    "deployment": false
  }
}
---

# Signal alert truth and provenance correction

Close the reviewed alert defects under a complete successor-start protected baseline.
