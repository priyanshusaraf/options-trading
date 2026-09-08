---
{
  "id": "phase5-capital-broad-compatibility-provider-leak-correction",
  "phase": "phase5",
  "status": "accepted",
  "kind": "correction",
  "goal": "Close only P5-CAP-R002 by restoring the process-wide mock provider after the execution-control test override, then complete the already-corrected P5-CAP-004/P5-CAP-R001 evidence package without changing engine or capital product behavior.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "AUTHORIZE PHASE-5 CAPITAL BROAD-COMPATIBILITY PROVIDER-LEAK CORRECTION received after the exact causal witness on 2026-08-26.",
    "stopping_condition": "Complete only after the direct singleton-method leak reproduces from frozen bytes; one test-only pytest-managed restoration closes it; the deliberate direct-assignment mutation fails and restores exact bytes; the causal sequence, full execution-control file and unchanged broad compatibility universe pass; predecessor focused/PostgreSQL/mutation/inventory evidence and protected hashes remain current; deployment impact is recorded as none; and one exact fresh review package is sealed for phase5-capital-assurance-final-review."
  },
  "risk_tags": ["critical-evidence", "false-green", "test-isolation", "shared-provider", "broad-compatibility", "correction"],
  "required_docs": [
    {"path": ".agent/runs/phase5-capital-assurance-recovery-correction/report.md", "sections": ["Blocking broad evidence", "Exact causal isolation", "Deployment and next gate"]},
    {"path": ".agent/runs/phase5-capital-assurance-recovery-correction/deployability.md", "sections": ["Evidence result", "Verdict and owners"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-026 — Capital safety proved against sampled identities and isolated transitions"]}
  ],
  "dependency_gate": "phase5-capital-assurance-replan",
  "historical_predecessor": "phase5-capital-assurance-recovery-correction",
  "allowed_paths": [
    "paper-trader/backend/tests/test_execution_control.py",
    ".agent/runs/phase5-capital-broad-compatibility-provider-leak-correction",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase5-capital-broad-compatibility-provider-leak-correction.md",
    "paper-trader/docs/agent/tasks/phase5-capital-assurance-final-review.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".codex/tests/test_programme_orchestration.py"
  ],
  "exact_write_ownership": {
    "owner": "root owner; serial; no children",
    "test": ["paper-trader/backend/tests/test_execution_control.py"],
    "evidence": [".agent/runs/phase5-capital-broad-compatibility-provider-leak-correction"],
    "root_transition_paths": [
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase5-capital-broad-compatibility-provider-leak-correction.md",
      "paper-trader/docs/agent/tasks/phase5-capital-assurance-final-review.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      ".codex/tests/test_programme_orchestration.py"
    ]
  },
  "nonclaims": [
    "No engine, provider, broker, capital product, schema, migration, configuration, dependency, service, runtime wiring, allocator/Position behavior, order, live/customer-money authority, frontend, deployment, production state or Phase 6 change.",
    "This test-only correction does not accept P5-CAP-004, P5-CAP-R001, capital assurance, Phase 5 or deployability. Only the fresh independent review can accept the integrated current bytes.",
    "The blocked predecessor correction, both exhausted FAIL verdicts and the exhausted package remain immutable history."
  ],
  "owner_gates": [
    "Stop before any second product/test file, shared fixture, provider implementation, engine behavior, runtime configuration, deployment or Phase 6 path.",
    "Stop if pytest-managed restoration does not close the exact causal sequence or if the complete broad universe remains red."
  ],
  "stop_conditions": [
    "A changed path is outside exact_write_ownership or a protected hash drifts.",
    "The direct-assignment mutation survives, restoration is inexact, the causal sequence is order-dependent after correction, or the broad process remains red.",
    "Any correction claim relies on the evidence-only cleanup test instead of normal pytest teardown.",
    "A runtime, schema, migration, provider/broker, order, live, production, frontend or Phase 6 byte changes."
  ],
  "deployment_impact": {
    "classification": "none",
    "affected_dimensions": ["Test-process isolation", "Phase 5 evidence integrity"],
    "unchanged_dimensions": ["Build artifacts", "Dependencies", "Configuration", "PostgreSQL", "Migrations", "Services", "Providers", "Runtime wiring", "Security", "Capacity", "Rollout"],
    "highest_claim": "locally_runnable paper/mock evidence only",
    "future_owner": "phase5-capital-assurance-final-review decides the integrated capital bytes; Phase 6/V1 retain every production and deployment obligation."
  },
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "next_reviewer": "gpt-5.6-sol", "next_reviewer_reasoning_effort": "high", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "findings": ["P5-CAP-R002"],
  "acceptance": [
    "Frozen bytes reproduce the exact two-test failure: test_disarmed_still_exits_existing_position leaves live_snapshot in the process-wide provider instance and the successor intraday test fails.",
    "The execution-control test installs the fake live_snapshot through monkeypatch.setattr and normal pytest teardown removes the instance override before the successor test.",
    "The exact two-test sequence and the complete test_execution_control.py file pass without the evidence-only cleanup test.",
    "A reversible mutation restoring the direct assignment makes the exact two-test sequence fail and restores test_execution_control.py to its final SHA-256.",
    "The unchanged 42-file broad compatibility universe passes in one process with no narrowed selection or evidence-only cleanup helper.",
    "P5-CAP-004/P5-CAP-R001 focused SQLite, disposable PostgreSQL 16 and three finding mutations remain green/current; inventory, migration heads, protected hashes, architecture and programme checks pass.",
    "A fresh package binds current product/test bytes, predecessor blocked history, every fresh evidence digest, deployment nonclaims and zero open findings for one new independent review."
  ],
  "test_plan": [
    "Retain the frozen failing two-test witness and cleanup proof, then make the one-line pytest-restoration repair in test_execution_control.py.",
    "Run the exact two-test sequence without the cleanup helper, the complete execution-control file and a deliberate direct-assignment mutation with exact restoration.",
    "Run the unchanged broad compatibility command; replay capital focused/SQLite and disposable PostgreSQL 16 selectors plus the three predecessor mutations from final bytes.",
    "Run inventory, migration-head, protected-hash, no-runtime-diff, architecture, programme and deployability audits, then seal the fresh review package."
  ],
  "review": {
    "required": true,
    "separate_stage": "phase5-capital-assurance-final-review",
    "assignment_id": "phase5_capital_provider_leak_correction_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/phase5-capital-assurance-final-review/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_execution_control.py",
      "paper-trader/backend/app/execution/leases.py",
      "paper-trader/backend/app/execution/capital_recovery.py",
      "paper-trader/backend/tests/test_capital_admission.py",
      "paper-trader/backend/tests/test_capital_admission_recovery.py",
      "paper-trader/backend/tests/test_capital_admission_postgresql.py",
      ".agent/runs/phase5-capital-broad-compatibility-provider-leak-correction",
      ".agent/runs/phase5-capital-assurance-recovery-correction"
    ],
    "exclude_paths": ["paper-trader/backend/app/engine", "paper-trader/backend/app/providers", "paper-trader/frontend"],
    "output": ".agent/runs/phase5-capital-broad-compatibility-provider-leak-correction/report.md",
    "verdicts": ["CORRECTION"],
    "max_rechecks": 0
  },
  "initial_write_hashes": {"paper-trader/backend/tests/test_execution_control.py": "bdb4cc711cd3662781eef7a479dee2f2d3fdf039c7b414d29036e478d028bf37"},
  "protected_files": {
    "paper-trader/backend/tests/test_engine_intraday.py": "64c1394430643dfd3597ae878a1fe96e818c8f9209c50812320e3e1b2929c2fe",
    "paper-trader/backend/conftest.py": "f3981b13d150804fb441cec137e36d765b1c2a7d855dd666001a256ef150fc81",
    "paper-trader/backend/app/execution/leases.py": "89878faed61af28002180f2cd40701517f05a99e379ef06d11a154f7473faad2",
    "paper-trader/backend/app/execution/capital_recovery.py": "ccc6b0c747bdb50baed41c1173a7130f19d69627cf823f03839d800383713084",
    "paper-trader/backend/tests/test_capital_admission.py": "ecf3a4ce851ce46f19f3458afe285b02f7301886c99c0038630b6c1be11cee68",
    "paper-trader/backend/tests/test_capital_admission_recovery.py": "1a1556b1f77ce6bd2cae5e69eb5d2ca3ff3f5ae647cc5ad20b98ff1518a43beb",
    "paper-trader/backend/tests/test_capital_admission_postgresql.py": "527cc86c035ac662e37f8fe467dc1e2a07e26c51bdaba045ffde50e68b1f9083",
    ".agent/runs/phase5-capital-assurance-recovery-correction/report.md": "d8958fe7670a8445b2adf9578df01e3cde718e7950db17b33324a8336f7e6a19",
    ".agent/runs/phase5-capital-assurance-recovery-correction/deployability.md": "a336a4e263976416198ff0c90eec7f219872153a74e62db9645faa573c559e22",
    ".agent/runs/phase5-capital-admission-assurance/review/verdict.json": "89d05b05650b9775966d4ae263d833794f56f8f17690e9a390502191db9512b8",
    ".agent/runs/phase5-capital-admission-assurance/review/recheck-verdict.json": "78e81a79606b6e70c2ed4d152a5edfab54a56dde30eee03a325cc8bf7762f8a9",
    ".agent/review-package.json": "c18e21f50645efa9e34104007b432778597f6e556c843c4bbfcba4da290f7bd6"
  },
  "acceptance_record": {
    "verdict": "CORRECTION PASS",
    "report": ".agent/runs/phase5-capital-broad-compatibility-provider-leak-correction/report.md",
    "report_sha256": "919de7e92b52cabc2d0eae54f8b67f15d2a32a0bca405dc43462737add15f4cc",
    "deployability": ".agent/runs/phase5-capital-broad-compatibility-provider-leak-correction/deployability.md",
    "deployability_sha256": "c24d618a5a9e46e155c35d3676bd4cf77fc2aed5c5c2eabf276ef5fac72df089",
    "final_test_sha256": "3125fc686d8a7c73b673cc7adbf9d7fbfb3a53bb1e17060c117b57ed834e60c2",
    "causal_sequence": "PASS",
    "mutation": "KILLED_AND_EXACTLY_RESTORED",
    "broad_compatibility": "PASS",
    "postgresql16": "PASS",
    "deployment_impact": "none",
    "open_findings": 0,
    "review_successor": "phase5-capital-assurance-final-review"
  }
}
---

# Phase 5 capital broad-compatibility provider-leak correction

This owner-authorized successor changes one test byte surface only. It replaces a
direct method assignment on the process-wide mock provider with pytest-managed
restoration, proves the causal sequence and complete broad gate, and prepares the
already-corrected capital bytes for the fresh independent review.
