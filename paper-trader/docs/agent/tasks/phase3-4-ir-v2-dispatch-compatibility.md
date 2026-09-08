---
{
  "id": "phase3-4-ir-v2-dispatch-compatibility",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Introduce one strict format-version dispatch seam while proving byte- and behavior-compatible v1 validation, resolution, evaluation, admission, API, and frontend-facing contracts.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after unsupported versions fail closed, the current v1 contract is frozen by direct golden evidence, one public IR path remains, focused tests pass, and phase3-4-ir-v2-schema-topology is review-ready. Do not implement v2 semantics."
  },
  "risk_tags": ["critical", "ir-contract", "compatibility", "identity"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["2. Current accepted boundary", "4. One public architecture", "14. Admission and persistence", "16. Backend API and frontend boundary"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["1. Role and objective", "2. Worktree, project root, and command roots", "3. Accepted baseline", "5. Scope boundaries", "7. Migration and compatibility", "9. Dependency order and chat structure", "10.1 phase3-4-ir-v2-dispatch-compatibility", "11. Tests and evidence", "14. Stop and owner gates", "15. Required nonclaims"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/ir/schema.py",
    "paper-trader/backend/app/ir/validate.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/streaming_reference.py",
    "paper-trader/backend/app/ir/formats",
    "paper-trader/backend/tests/test_ir_v1_dispatch_schema_golden.py",
    "paper-trader/backend/tests/test_ir_v1_dispatch_runtime_golden.py",
    "paper-trader/backend/tests/test_ir_v1_dispatch_admission_golden.py",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-dispatch-compatibility.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase3-4-ir-v2-dispatch-compatibility"
  ],
  "nonclaims": [
    "This task does not implement v2 schema, runtime, persistence, API authoring, frontend support, deployment, production readiness, or live authority.",
    "V1 remains the product-writing format."
  ],
  "owner_gates": [
    "Stop before frontend source changes, migration changes, admission-authority changes, live paths, deployment, credentials, or v1 retirement."
  ],
  "stop_conditions": [
    "A golden v1 byte, error, address, resolution, evaluation, receipt, or API contract changes.",
    "The dispatch seam requires a second registry or public IR stack.",
    "An inherited dirty path or protected hash cannot be reconciled."
  ],
  "deployment_impact": {
    "classification": "runtime-compatible-refactor",
    "affected_dimensions": ["Application", "IR API"],
    "required_evidence": "Focused v1 golden behavior and unsupported-version refusal. No deployability or production-readiness claim."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": ["owner_dispatch_scaffold"],
  "assignments": [
    {
      "id": "v1_schema_validation_golden",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_dispatch_scaffold"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v1_dispatch_schema_golden.py"],
      "output": ".agent/runs/phase3-4-ir-v2-dispatch-compatibility/v1_schema_validation_golden/report.md"
    },
    {
      "id": "v1_resolution_runtime_golden",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_dispatch_scaffold"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v1_dispatch_runtime_golden.py"],
      "output": ".agent/runs/phase3-4-ir-v2-dispatch-compatibility/v1_resolution_runtime_golden/report.md"
    },
    {
      "id": "v1_admission_identity_golden",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_dispatch_scaffold"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v1_dispatch_admission_golden.py"],
      "output": ".agent/runs/phase3-4-ir-v2-dispatch-compatibility/v1_admission_identity_golden/report.md"
    },
    {
      "id": "v1_api_frontend_contract_inventory",
      "agent": "luna-worker",
      "mode": "read",
      "depends_on": ["owner_dispatch_scaffold"],
      "write_paths": [],
      "output": ".agent/runs/phase3-4-ir-v2-dispatch-compatibility/v1_api_frontend_contract_inventory/report.md"
    }
  ],
  "acceptance": [
    "One strict public dispatch path selects v1 and rejects missing, boolean, float, string, and unknown versions.",
    "Golden v1 validation, resolution, vector/prefix evaluation, identity, admission, API, and frontend-facing contracts remain unchanged.",
    "No v2 semantics, persistence changes, frontend source changes, live authority, or deployment work exists.",
    "All child diffs are inspected and integrated by the Terra owner."
  ],
  "test_plan": [
    "Run the three new golden clusters and the current focused IR/admission/API tests.",
    "Run exact unsupported-version and no-partial-state cases.",
    "Run git diff --check, protected-hash checks, and deployability-impact audit."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase3_4_ir_v2_dispatch_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/tests/test_ir_v1_dispatch_schema_golden.py",
      "paper-trader/backend/tests/test_ir_v1_dispatch_runtime_golden.py",
      "paper-trader/backend/tests/test_ir_v1_dispatch_admission_golden.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase3-4-ir-v2-dispatch-compatibility/owner_integration/report.md",
    "verdicts": ["INTEGRATION"],
    "max_rechecks": 0
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# IR v2 dispatch and v1 compatibility goal

The shared dispatch scaffold is owner work. Luna children start only after that milestone and own only their declared mechanical evidence. Workers share a dirty tree and must not revert inherited edits.
