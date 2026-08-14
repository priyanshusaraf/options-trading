---
{
  "id": "phase3-task12-correction-1",
  "phase": "phase3-causal-strategy-admission",
  "status": "ready",
  "goal": "Resolve every current Phase 3 Task 12 rejection finding, regenerate evidence from the exact final dirty tree, and prepare a truthful Sol-high recheck without widening Phase 3 scope.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after every named rejection finding has direct current evidence, the required broad gate completes successfully once, the review package is regenerated from the final tree, and phase3-task12-review-2 is ready. Keep the goal active or stop for any owner gate, unavailable required environment, or unresolved failing evidence."
  },
  "risk_tags": [
    "critical",
    "money-path",
    "research-integrity",
    "migrations",
    "dirty-tree-correction"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md",
      "sections": [
        "Task 12: Phase 3 mutation gate, operations record, and full closure",
        "Final rejection-before-acceptance review"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md",
      "sections": [
        "1. Outcome",
        "3. Governing constraints",
        "12. Acceptance and mutation gates",
        "13. Completion evidence"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
      "sections": [
        "3. Position sizing hierarchy",
        "4. Multi-strategy position ownership",
        "5. Open-position version ownership",
        "6. Protection semantics",
        "7. Order semantics"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": [
        "1. Risk-weighted verification",
        "2. Test rule",
        "3. Test cadence",
        "8. Guard against scope drift"
      ]
    }
  ],
  "rejection_evidence": {
    "verdict": ".agent/runs/phase3-task12/critical_review/verdict.json",
    "package": ".agent/review-package.json",
    "closure_report": "paper-trader/docs/reports/2026-08-13-phase3-causal-strategy-contract.md",
    "finding_ids": [
      "SPEC-P0-1",
      "SPEC-P0-2",
      "SPEC-P1-3",
      "QUALITY-P0-1",
      "QUALITY-P1-2",
      "QUALITY-P1-3"
    ]
  },
  "allowed_paths": [
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/backend/tests",
    "paper-trader/backend/research_tests",
    "paper-trader/backend/scripts/phase3_causal_gate.py",
    "paper-trader/backend/scripts/causal_admission_mutations.py",
    "paper-trader/docs/operations/strategy-admission.md",
    "paper-trader/docs/reports/2026-08-13-phase3-causal-strategy-contract.md",
    "paper-trader/docs/reports/phase3-causal-gate.json",
    "paper-trader/docs/ROADMAP.md",
    "paper-trader/docs/CONTINUE.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    ".agent/runs/phase3-task12-correction-1",
    ".agent/review-package.json"
  ],
  "nonclaims": [
    "Phase 3 does not prove market truth, numeric validity, point-in-time rulebooks, provider capability, resource fit, Strategy Preflight, dynamic derivative semantics, or production readiness.",
    "Phase 3 does not adopt or validate Component IR v2.",
    "Passing local and PostgreSQL evidence does not claim deployment or managed-production readiness."
  ],
  "owner_gates": [
    "Stop before enabling (ir_graph, live, authoritative).",
    "Stop before a material live sizing, routing, risk, protection, or execution-semantics change.",
    "Stop before live credentials, VPS, production data, deployment, destructive infrastructure/data work, frontend work, or licence-sensitive adoption."
  ],
  "stop_conditions": [
    "The starting dirty patch, untracked manifest, or protected hashes differ from the 2026-08-14 pre-orchestration recovery snapshot without an explained owner change.",
    "A protected inherited-file hash changes.",
    "A required PostgreSQL environment is unavailable; retain rejected/open status instead of substituting SQLite evidence.",
    "The broad gate remains red, incomplete, timed out, skipped, empty, or stale after bounded diagnosis.",
    "The work requires Component IR v2 or a later phase."
  ],
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "broad_failure_inventory",
      "agent": "terra-worker",
      "model": "gpt-5.6-terra",
      "reasoning_effort": "medium",
      "mode": "read",
      "depends_on": [],
      "read_paths": [
        ".agent/runs/phase3-task12",
        ".agent/review-package.json",
        "paper-trader/docs/reports/phase3-causal-gate.json",
        "paper-trader/backend/tests",
        "paper-trader/backend/research_tests"
      ],
      "write_paths": [
        ".agent/runs/phase3-task12-correction-1/broad_failure_inventory"
      ],
      "output": ".agent/runs/phase3-task12-correction-1/broad_failure_inventory/report.md"
    },
    {
      "id": "evidence_lineage_audit",
      "agent": "luna-worker",
      "model": "gpt-5.6-terra",
      "reasoning_effort": "medium",
      "mode": "read",
      "depends_on": [],
      "read_paths": [
        ".agent/runs/phase3-task12",
        ".agent/review-package.json",
        "paper-trader/backend/scripts/phase3_causal_gate.py",
        "paper-trader/backend/research/orchestrator/generate.py"
      ],
      "write_paths": [
        ".agent/runs/phase3-task12-correction-1/evidence_lineage_audit"
      ],
      "output": ".agent/runs/phase3-task12-correction-1/evidence_lineage_audit/report.md"
    }
  ],
  "acceptance": [
    "The pre-edit audit matches the recovery snapshot and all four protected hashes.",
    "Every failed and timed-out broad shard is diagnosed and corrected without weakening fail-closed admission or production checks.",
    "Execution and research migration heads come from executed owning migration-tool commands; missing, failed, empty, forged, or mismatched output fails the gate.",
    "Generated descriptor construction does not commit or roll back unrelated caller-owned pending work, proven by a transaction-boundary regression test.",
    "Every evidence command invalidated by edits is rerun from the exact final tree.",
    "Focused, mutation, PostgreSQL, integrity, and one completed broad backend-plus-research phase gate pass non-vacuously.",
    "The review package is generated only after final evidence and binds the complete current dirty-tree fingerprint and evidence hashes.",
    "The phase remains rejected/open until phase3-task12-review-2 returns both passing verdicts."
  ],
  "test_plan": [
    "Focused regression tests for each corrected finding.",
    "Affected money/authority and research subsystem suites.",
    "Direct execution and research migration-head commands through the owning tools.",
    "Causal and identity mutation gate.",
    "Exactly one final .venv/bin/python -m pytest -q tests research_tests run through run_logged.py.",
    "git diff --check, recovery comparison, protected hashes, future-file exclusion, and fresh review-package fingerprint."
  ],
  "review": {
    "required": true,
    "separate_goal": "phase3-task12-review-2",
    "assignment_id": "phase3_task12_review_2",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader"
    ],
    "exclude_paths": [
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md"
    ],
    "output": ".agent/runs/phase3-task12-review-2/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  },
  "dirty_tree_baseline": {
    "head": "db77593e3d3a278c0d1fdd7504b25b8080543f23",
    "recovery_snapshot": "/Users/priyanshusaraf/dev/options-trading-migration-backups/2026-08-14-phase3-task12-db77593-pre-goal-orchestration",
    "tracked_patch_sha256": "49a2f304fc72de9f1fe01a8f5c67770579f17ef3845243514a6e04c081beb174",
    "status_sha256": "c4af9ca4f9dd8e7d18fca6392c42839736a3352ba8fd745cf45a24ffed0c2900",
    "untracked_manifest_sha256": "82c0bfb6969f2977882d6fccc87de3d2462e6a1e5b656c0ba9ae9fbf4ab49e96",
    "future_findings_excluded": [
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md"
    ]
  }
}
---

# Phase 3 Task 12 corrective goal 1

Begin with the preserved dirty-tree audit. Use the two declared analysis assignments only if they save owner work; the Terra owner performs all product edits and integrates once. Do not rerun broad evidence until focused failures are corrected and the final tree is ready.

This goal prepares, but does not perform, the separate Sol-high phase review.
