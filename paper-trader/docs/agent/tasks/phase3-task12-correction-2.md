---
{
  "id": "phase3-task12-correction-2",
  "phase": "phase3-causal-strategy-admission",
  "status": "accepted",
  "goal": "Integrate Phase 3 admission across the full backend and research test surface, resolve every current broad-gate regression without weakening fail-closed authority, and regenerate exact final-tree closure evidence.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after every Phase-3-introduced or Phase-3-invalidated failure and every Phase-3 broad-order contamination is resolved; exact phase-entry failures remain unchanged and explicitly recorded; focused and affected subsystem suites, PostgreSQL, mutation, causal, and baseline-aware broad evidence pass; the review package is regenerated; and phase3-task12-review-2 is ready."
  },
  "risk_tags": ["critical", "money-path", "research-integrity", "migrations", "dirty-tree-integration"],
  "decision": "KEEP + HARDEN",
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md",
      "sections": ["Task 12: Phase 3 mutation gate, operations record, and full closure", "Final rejection-before-acceptance review"]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md",
      "sections": ["1. Outcome", "3. Governing constraints", "12. Acceptance and mutation gates", "13. Completion evidence"]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
      "sections": ["3. Position sizing hierarchy", "4. Multi-strategy position ownership", "5. Open-position version ownership", "6. Protection semantics", "7. Order semantics"]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": ["1. Risk-weighted verification", "2. Test rule", "3. Test cadence", "8. Guard against scope drift"]
    }
  ],
  "input_evidence": {
    "broad_log": ".agent/runs/phase3-task12-correction-1/owner_integration/final_backend_research.log",
    "diagnosis": ".agent/runs/phase3-task12-correction-1/owner_integration/broad_gate_diagnosis.md",
    "slice_plan": ".agent/runs/phase3-task12-correction-1/owner_integration/successor_slice_plan.md"
  },
  "allowed_paths": [
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/backend/tests",
    "paper-trader/backend/research_tests",
    "paper-trader/backend/conftest.py",
    "paper-trader/backend/scripts/phase3_causal_gate.py",
    "paper-trader/backend/scripts/causal_admission_mutations.py",
    "paper-trader/docs/operations/strategy-admission.md",
    "paper-trader/docs/reports/2026-08-13-phase3-causal-strategy-contract.md",
    "paper-trader/docs/reports/phase3-causal-gate.json",
    "paper-trader/docs/strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md",
    "paper-trader/docs/CONTINUE.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/phase3-task12-correction-2.md",
    ".agent/runs/phase3-task12-correction-2",
    ".agent/review-package.json"
  ],
  "nonclaims": [
    "Local and PostgreSQL test evidence does not establish release deployability, production rehearsal, deployment, market truth, numeric validity, provider capability, resource fit, or live authority.",
    "Phase 3 does not adopt Component IR v2 or enable authoritative live IR."
  ],
  "owner_gates": [
    "Stop before enabling authoritative live IR or materially changing live sizing, routing, risk, protection, or execution semantics.",
    "Stop before live credentials, VPS, production data, deployment, destructive infrastructure/data work, frontend implementation, or licence-sensitive adoption."
  ],
  "stop_conditions": [
    "A protected inherited-file hash changes.",
    "The required local PostgreSQL 16 environment is unavailable.",
    "A correction requires authoritative live IR, a protected file, Component IR v2, frontend work, production access, or a later-phase architecture decision."
  ],
  "deployment_impact": {
    "classification": "compatible",
    "affected_dimensions": ["PostgreSQL", "Migrations", "Health", "Services"],
    "required_evidence": "Local PostgreSQL contracts, exact execution and research migration heads, schema parity and restore tests where affected, and truthful locally-runnable-only reporting. No deployment or production-readiness claim."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 0,
  "completed_assignments": [
    {
      "id": "authority_fixture_integration",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": [],
      "write_paths": ["paper-trader/backend/tests/admitted_entry.py", "paper-trader/backend/tests/test_paper_authority.py", "paper-trader/backend/tests/test_paper_authority_engine.py", "paper-trader/backend/tests/test_paper_authority_runtime.py", "paper-trader/backend/tests/test_shadow_deployments.py", "paper-trader/backend/app/core/paper_authority.py"],
      "output": ".agent/runs/phase3-task12-correction-2/authority_fixture_integration/report.md"
    },
    {
      "id": "backtest_receipt_migration",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": [],
      "write_paths": ["paper-trader/backend/tests/test_backtest_batch_persistence.py", "paper-trader/backend/tests/test_backtest_cache.py", "paper-trader/backend/tests/test_backtest_parallel.py", "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py"],
      "output": ".agent/runs/phase3-task12-correction-2/backtest_receipt_migration/report.md"
    },
    {
      "id": "portable_research_schema",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": [],
      "write_paths": ["paper-trader/backend/tests/test_portable_concurrency_integration.py"],
      "output": ".agent/runs/phase3-task12-correction-2/portable_research_schema/report.md"
    },
    {
      "id": "exposure_test_migration",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["authority_fixture_integration"],
      "write_paths": ["paper-trader/backend/tests/test_auto_block_reentry.py", "paper-trader/backend/tests/test_daily_profit_lock.py", "paper-trader/backend/tests/test_drawdown_and_mode.py", "paper-trader/backend/tests/test_engine_intraday.py", "paper-trader/backend/tests/test_engine_loops.py", "paper-trader/backend/tests/test_excursion.py", "paper-trader/backend/tests/test_execution_control.py", "paper-trader/backend/tests/test_execution_lifecycle_recovery.py", "paper-trader/backend/tests/test_execution_routing_engine.py", "paper-trader/backend/tests/test_manual_broker.py", "paper-trader/backend/tests/test_notify_engine.py", "paper-trader/backend/tests/test_option_gtt_fill_reconcile.py", "paper-trader/backend/tests/test_overnight_multiday.py", "paper-trader/backend/tests/test_overnight_segment_filter.py", "paper-trader/backend/tests/test_phase8_engine.py", "paper-trader/backend/tests/test_poisoned_position_key.py", "paper-trader/backend/tests/test_position_sltp.py", "paper-trader/backend/tests/test_ratchet_live_parity.py", "paper-trader/backend/tests/test_runtime_sltp.py", "paper-trader/backend/tests/test_trade_log.py", "paper-trader/backend/tests/test_trailing_exchange_sync.py", "paper-trader/backend/tests/test_phantom_close.py", "paper-trader/backend/tests/test_routes_manual.py", "paper-trader/backend/tests/test_trader_controls.py"],
      "output": ".agent/runs/phase3-task12-correction-2/exposure_test_migration/report.md"
    },
    {
      "id": "residual_integration",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": ["authority_fixture_integration", "backtest_receipt_migration", "portable_research_schema", "exposure_test_migration"],
      "write_paths": ["paper-trader/backend/app", "paper-trader/backend/research", "paper-trader/backend/tests", "paper-trader/backend/research_tests"],
      "exclude_paths": ["paper-trader/backend/app/engine/kite_venue.py", "paper-trader/backend/app/engine/venue.py", "paper-trader/backend/app/providers/brokers.py", "paper-trader/backend/tests/test_broker_registry.py"],
      "output": ".agent/runs/phase3-task12-correction-2/residual_integration/report.md"
    },
    {
      "id": "phase3_d_manifest",
      "agent": "luna-worker",
      "mode": "read",
      "depends_on": ["residual_integration"],
      "write_paths": [],
      "output": ".agent/runs/phase3-task12-correction-2/phase3_d_manifest/report.md"
    },
    {
      "id": "causal_gate_contract",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": ["residual_integration", "phase3_d_manifest"],
      "write_paths": ["paper-trader/backend/scripts/phase3_causal_gate.py", "paper-trader/backend/tests/test_phase3_causal_gate.py"],
      "output": ".agent/runs/phase3-task12-correction-2/causal_gate_contract/report.md"
    },
    {
      "id": "no_live_guard_fixture",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["residual_integration"],
      "write_paths": ["paper-trader/backend/tests/test_no_live_under_pytest.py"],
      "output": ".agent/runs/phase3-task12-correction-2/no_live_guard_fixture/report.md"
    },
    {
      "id": "timeout_backtest_cluster",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": ["causal_gate_contract", "no_live_guard_fixture"],
      "write_paths": ["paper-trader/backend/tests/test_backtest_parallel.py", "paper-trader/backend/tests/test_backtest_payload.py", "paper-trader/backend/tests/test_backtest_pinned.py", "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py", "paper-trader/backend/tests/test_backtest_premium.py"],
      "output": ".agent/runs/phase3-task12-correction-2/timeout_backtest_cluster/report.md"
    },
    {
      "id": "timeout_runtime_clusters",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": ["causal_gate_contract", "no_live_guard_fixture"],
      "write_paths": ["paper-trader/backend/tests/test_durability_posture.py", "paper-trader/backend/tests/test_earnings.py", "paper-trader/backend/tests/test_engine_binding.py", "paper-trader/backend/tests/test_engine_intraday.py", "paper-trader/backend/tests/test_engine_loops.py", "paper-trader/backend/tests/test_excursion.py", "paper-trader/backend/tests/test_execution_admission_attribution.py", "paper-trader/backend/tests/test_execution_attribution.py", "paper-trader/backend/tests/test_execution_binding.py", "paper-trader/backend/tests/test_execution_book.py"],
      "output": ".agent/runs/phase3-task12-correction-2/timeout_runtime_clusters/report.md"
    },
    {
      "id": "runtime_admission_scan_performance",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": ["timeout_runtime_clusters"],
      "write_paths": ["paper-trader/backend/app/engine/runner.py", "paper-trader/backend/tests/test_engine_intraday.py", "paper-trader/backend/tests/test_execution_admission_attribution.py", "paper-trader/backend/tests/test_execution_attribution.py", "paper-trader/backend/tests/test_paper_authority_runtime.py"],
      "output": ".agent/runs/phase3-task12-correction-2/runtime_admission_scan_performance/report.md"
    },
    {
      "id": "implementation_identity_metadata_cache",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": ["runtime_admission_scan_performance"],
      "write_paths": ["paper-trader/backend/app/ir/implementation_identity.py", "paper-trader/backend/tests/test_ir_implementation_identity.py", "paper-trader/backend/tests/test_engine_intraday.py"],
      "output": ".agent/runs/phase3-task12-correction-2/implementation_identity_metadata_cache/report.md"
    }
  ],
  "assignments": [],
  "acceptance": [
    "Admission remains mandatory at every executable entry boundary; missing, stale, forged, foreign-owner, and mismatched receipts fail closed.",
    "Legacy tests that exercise downstream money behavior use real persisted admission evidence; refusal tests keep absence or corruption explicit.",
    "Backtest runs consume the admission receipt without accepting a second caller-selected execution identity.",
    "Portable research outbox and operation contracts pass on SQLite and PostgreSQL with atomicity and fencing intact.",
    "Every Phase-3 category A, B, and C broad failure and error is resolved without changing protected files or widening to live authority; category D failures are accepted only when each exact node belongs to the proven 23-node phase-entry allowlist, while any extra, changed, timed-out, or malformed result rejects closure. A baseline-D node that is now green is recorded as an improvement and does not have to remain broken.",
    "Focused, affected subsystem, mutation, PostgreSQL, migration, integrity, causal, and one exact baseline-aware broad backend-plus-research gate pass non-vacuously.",
    "The review package binds the final dirty-tree fingerprint and exact evidence hashes; Phase 3 stays rejected/open until the separate review passes."
  ],
  "test_plan": [
    "Historical task: retain the focused, affected-subsystem, PostgreSQL, mutation, causal, and baseline-aware broad evidence named by the accepted Phase 3 review.",
    "Do not replay this closed capsule merely to validate current architecture metadata."
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
      "paper-trader/backend/app",
      "paper-trader/backend/research",
      "paper-trader/backend/tests",
      "paper-trader/backend/research_tests",
      "paper-trader/docs"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase3-task12-review-2/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 3 Task 12 corrective integration 2

Owner-authorized successor to the bounded diagnosis in correction 1. Preserve
the admission architecture and correct integrations against it. Workers are not
alone in the tree: they must preserve inherited changes, stay inside declared
write paths, and never revert another worker's edits.
