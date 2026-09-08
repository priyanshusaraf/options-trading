---
{
  "id": "phase3-4-ir-v2-integration-gate",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Serially integrate and verify the complete bounded IR v2 implementation, reconcile evidence and deployability obligations, and produce one exact-snapshot review package.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after all prior IR v2 implementation stages are accepted, the bounded integrated v1/v2, admission, research, migration, API, PostgreSQL, and killed-mutation gate passes, documentation and programme state agree, and a current official package makes phase3-4-ir-v2-implementation-review ready."
  },
  "risk_tags": ["critical", "serial-integration", "review-package", "migrations", "authority"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["1. Decision", "14. Admission and persistence", "18. Deployability impact", "20. Acceptance conditions"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["3. Accepted baseline", "5. Scope boundaries", "9. Dependency order and chat structure", "10.6 phase3-4-ir-v2-integration-gate", "11. Tests and evidence", "12. Documentation and programme state", "13. Protected files and inherited work", "14. Stop and owner gates", "15. Required nonclaims", "16. Final gate", "17. Final report"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Current verdict", "Open obligations", "V1 release gate"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/app/db/migrate.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/migrations/versions/20260816_0035_ir_v2_admissions.py",
    "paper-trader/backend/app/api/ir_routes.py",
    "paper-trader/backend/app/api/ir_edit_routes.py",
    "paper-trader/backend/app/api/product_object_routes.py",
    "paper-trader/backend/app/editor/descriptors.py",
    "paper-trader/backend/app/editor/graph_artifacts.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/migrations/0006_ir_v2_admissions.py",
    "paper-trader/backend/tests/test_ir_v1_dispatch_schema_golden.py",
    "paper-trader/backend/tests/test_ir_v1_dispatch_runtime_golden.py",
    "paper-trader/backend/tests/test_ir_v1_dispatch_admission_golden.py",
    "paper-trader/backend/tests/test_ir_v2_ports_types.py",
    "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
    "paper-trader/backend/tests/test_ir_v2_identity.py",
    "paper-trader/backend/tests/test_ir_v2_registry_compounds.py",
    "paper-trader/backend/tests/test_ir_v2_resolution_bundles.py",
    "paper-trader/backend/tests/test_ir_v2_compound_resolution.py",
    "paper-trader/backend/tests/test_ir_v2_vector_runtime.py",
    "paper-trader/backend/tests/test_ir_v2_prefix_parity.py",
    "paper-trader/backend/tests/test_ir_v2_admission_receipt.py",
    "paper-trader/backend/tests/test_ir_v2_execution_migration.py",
    "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
    "paper-trader/backend/tests/test_ir_v2_legacy_compatibility.py",
    "paper-trader/backend/tests/test_ir_v2_api_roundtrip.py",
    "paper-trader/backend/tests/test_ir_v1_api_compatibility.py",
    "paper-trader/backend/tests/test_ir_v2_editor_descriptors.py",
    "paper-trader/docs/operations/strategy-admission.md",
    "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-implementation.md",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-integration-gate.md",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-implementation-review.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase3-4-ir-v2-integration-gate",
    ".agent/review-package.json"
  ],
  "read_only_paths": ["paper-trader/frontend"],
  "nonclaims": [
    "Integrated local evidence does not establish release deployability, production readiness, production capacity/recovery/security/cost, frontend v2 authoring, provider capability, Phase 4 truth, or live authority.",
    "Only a later independent dual PASS can unlock Phase 4 architecture."
  ],
  "owner_gates": [
    "This goal is serial: spawn no child or reviewer before the official package exists.",
    "Stop before frontend changes, live authority, broker/provider effects, deployment, credentials, production data, or destructive work."
  ],
  "stop_conditions": [
    "A prior capsule lacks accepted evidence or binds another snapshot.",
    "The integrated gate, PostgreSQL gate, or any required killed mutation fails.",
    "A protected hash, inherited dirty path, package fingerprint, or deployability obligation cannot be reconciled."
  ],
  "deployment_impact": {
    "classification": "integrated-local-verification",
    "affected_dimensions": ["Application", "HTTP API", "Execution database", "Research database", "Migrations", "PostgreSQL", "CPU", "Memory"],
    "required_evidence": "Consolidated local impact matrix and exact evidence paths; all unproved production obligations are retained as nonclaims or exact future requirements."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "All earlier implementation stages and evidence are present, current, and internally consistent.",
    "One bounded integrated gate covers v1/v2 IR, closed metadata and canonical content bytes, compound parameter propagation/provenance, admission, research, migrations, API, PostgreSQL, and required killed mutations.",
    "Protected hashes, dirty-tree binding, documentation, CURRENT, PROGRAMME, deployability matrix, and review package agree.",
    "The package is current and phase3-4-ir-v2-implementation-review is ready; no acceptance or production claim is made."
  ],
  "test_plan": [
    "Run the exact bounded IR v1/v2, admission, migration, research, and API gate once.",
    "Run the disposable PostgreSQL gate once.",
    "Run killed mutations for dispatch, type compatibility, edge binding order, compound parameter propagation, content/graph identity separation, prefix parity, receipt immutability, and migration safety.",
    "Run architecture/programme validators, package verification, diff check, and protected-hash audit."
  ],
  "review": {
    "required": true,
    "separate_goal": "phase3-4-ir-v2-implementation-review",
    "assignment_id": "phase3_4_ir_v2_implementation_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations/versions/20260816_0035_ir_v2_admissions.py",
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/editor",
      "paper-trader/backend/research/domain",
      "paper-trader/backend/tests",
      "paper-trader/backend/research_tests",
      "paper-trader/docs"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase3-4-ir-v2-implementation-review/verdict.json",
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

# IR v2 serial integration gate

No subagent runs in this goal. One Terra owner binds all evidence to one snapshot and prepares the package for the separate critical reviewer.
