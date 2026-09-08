---
{
  "id": "phase3-4-ir-v2-api-contract",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Expose explicit version-discriminated backend IR contracts for accepted v1 and v2 capabilities while preserving current React/Vite v1 authoring and refusing unknown versions atomically.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after v1 API goldens, v2 canonical complete-document create/read round trips, closed metadata and content/graph identity preservation, unknown-version atomic refusal, descriptor compatibility, and a read-only frontend coupling audit pass with no frontend source edits; then make phase3-4-ir-v2-integration-gate ready."
  },
  "risk_tags": ["important", "api-contract", "compatibility", "frontend-boundary"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["2. Current accepted boundary", "14. Admission and persistence", "16. Backend API and frontend boundary", "18. Deployability impact"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["5. Scope boundaries", "7. Migration and compatibility", "9. Dependency order and chat structure", "10.5 phase3-4-ir-v2-api-contract", "11. Tests and evidence", "13. Protected files and inherited work", "14. Stop and owner gates", "15. Required nonclaims"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/api/ir_routes.py",
    "paper-trader/backend/app/api/ir_edit_routes.py",
    "paper-trader/backend/app/api/product_object_routes.py",
    "paper-trader/backend/app/editor/descriptors.py",
    "paper-trader/backend/app/editor/graph_artifacts.py",
    "paper-trader/backend/tests/test_ir_v2_api_roundtrip.py",
    "paper-trader/backend/tests/test_ir_v1_api_compatibility.py",
    "paper-trader/backend/tests/test_ir_v2_editor_descriptors.py",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-api-contract.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase3-4-ir-v2-api-contract"
  ],
  "read_only_paths": ["paper-trader/frontend"],
  "nonclaims": [
    "The React/Vite frontend cannot author v2 and v2 is not the product default.",
    "API evidence does not prove deployability, production readiness, provider capability, Phase 4 truth, or live authority."
  ],
  "owner_gates": [
    "Stop before any frontend source edit, v1 writer retirement, auto migration, provider/broker work, deployment, credentials, or live authority."
  ],
  "stop_conditions": [
    "An accepted v1 request, response, error, or editor descriptor changes incompatibly.",
    "Unknown-version refusal can persist partial state.",
    "Frontend implementation is needed, or protected/inherited work conflicts."
  ],
  "deployment_impact": {
    "classification": "api-additive",
    "affected_dimensions": ["Application", "HTTP API", "Stored artifacts", "Compatibility"],
    "required_evidence": "Focused request/response, atomicity, read-after-write, error-contract, and v1 compatibility evidence. No deployability claim."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": ["owner_api_schema_interfaces"],
  "assignments": [
    {
      "id": "v2_api_roundtrip_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_api_schema_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_api_roundtrip.py"],
      "output": ".agent/runs/phase3-4-ir-v2-api-contract/v2_api_roundtrip_cases/report.md"
    },
    {
      "id": "v1_api_compatibility_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_api_schema_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v1_api_compatibility.py"],
      "output": ".agent/runs/phase3-4-ir-v2-api-contract/v1_api_compatibility_cases/report.md"
    },
    {
      "id": "v2_editor_descriptor_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_api_schema_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_editor_descriptors.py"],
      "output": ".agent/runs/phase3-4-ir-v2-api-contract/v2_editor_descriptor_cases/report.md"
    },
    {
      "id": "react_vite_v2_coupling_audit",
      "agent": "luna-worker",
      "mode": "read",
      "depends_on": ["owner_api_schema_interfaces"],
      "write_paths": [],
      "output": ".agent/runs/phase3-4-ir-v2-api-contract/react_vite_v2_coupling_audit/report.md"
    }
  ],
  "acceptance": [
    "Every request and response carries an explicit strict format discriminator.",
    "V1 endpoints, writers, errors, and React/Vite-facing descriptors remain compatible.",
    "Accepted v2 backend writes round-trip the canonical complete document plus exact content_address and graph_address across object-key/tag reordering; unknown metadata and unknown versions fail atomically.",
    "No frontend source, provider, broker, deployment, or live path changes."
  ],
  "test_plan": [
    "Run three new API/descriptor clusters plus current focused IR edit, product-object, artifact, and API tests.",
    "Run canonical-byte golden vectors, metadata/content-vs-graph identity mutations, partial-persistence, unknown-field, and unknown-version failure cases.",
    "Capture a read-only frontend coupling inventory, then run diff, protected-hash, and deployability checks."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase3_4_ir_v2_api_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/editor",
      "paper-trader/backend/tests/test_ir_v2_api_roundtrip.py",
      "paper-trader/backend/tests/test_ir_v1_api_compatibility.py",
      "paper-trader/backend/tests/test_ir_v2_editor_descriptors.py"
    ],
    "exclude_paths": ["paper-trader/frontend"],
    "output": ".agent/runs/phase3-4-ir-v2-api-contract/owner_integration/report.md",
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

# IR v2 backend API contract goal

The frontend is read-only. Luna children own three disjoint backend test files and one evidence-only coupling audit after the Terra owner stabilizes the API schema.
