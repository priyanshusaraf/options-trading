---
{
  "id": "phase3-4-ir-v2-resolution-runtime",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Resolve v2 graphs into immutable edge-preserving input bundles and exact compound parameter targets, then implement deterministic vector and independently coded prefix evaluation for the supported fixed-topology contract.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after many-input resolution, exact compound public-parameter propagation, compound closure, nested edge/parameter provenance, vector/prefix determinism, causal parity, and killed-mutation evidence pass without changing v1 behavior, and phase3-4-ir-v2-admission-persistence is review-ready."
  },
  "risk_tags": ["critical", "resolver", "runtime", "research-integrity", "causality"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["8. Edge and binding contract", "9. Fixed topology and dynamic instruments", "10. Compound components", "11. Validation", "12. Evaluation", "13. Serialization and identity"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["4. Architectural context", "5. Scope boundaries", "6. Required IR v2 contract", "9. Dependency order and chat structure", "10.3 phase3-4-ir-v2-resolution-runtime", "11. Tests and evidence", "14. Stop and owner gates", "15. Required nonclaims"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/streaming_reference.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/formats",
    "paper-trader/backend/tests/test_ir_v2_resolution_bundles.py",
    "paper-trader/backend/tests/test_ir_v2_compound_resolution.py",
    "paper-trader/backend/tests/test_ir_v2_vector_runtime.py",
    "paper-trader/backend/tests/test_ir_v2_prefix_parity.py",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-resolution-runtime.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase3-4-ir-v2-resolution-runtime"
  ],
  "nonclaims": [
    "This task supports only registered components with proved v2 evaluation contracts; it does not imply all nodes or strategies work.",
    "It does not add providers, Phase 4 validity, admission authority, persistence, frontend support, deployment, or live execution."
  ],
  "owner_gates": [
    "Stop before provider reads, broker effects, implicit time, dynamic topology, hidden fill/coercion, mutable global state, or Phase 4 semantics."
  ],
  "stop_conditions": [
    "V2 resolution collapses an accepted many-input contract or loses edge identity.",
    "Vector and prefix implementations cease to be independent.",
    "A parity mutation survives, v1 golden evidence changes, or protected/inherited work conflicts."
  ],
  "deployment_impact": {
    "classification": "runtime-additive",
    "affected_dimensions": ["Application", "CPU", "Memory", "Research runtime"],
    "required_evidence": "Determinism and bounded local microbenchmarks for representative v2 fan-in; resource results remain local estimates and do not prove capacity."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": ["owner_resolved_bundle_interfaces"],
  "assignments": [
    {
      "id": "v2_resolution_bundle_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_resolved_bundle_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_resolution_bundles.py"],
      "output": ".agent/runs/phase3-4-ir-v2-resolution-runtime/v2_resolution_bundle_cases/report.md"
    },
    {
      "id": "v2_compound_resolution_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_resolved_bundle_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_compound_resolution.py"],
      "output": ".agent/runs/phase3-4-ir-v2-resolution-runtime/v2_compound_resolution_cases/report.md"
    },
    {
      "id": "v2_vector_runtime_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_resolved_bundle_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_vector_runtime.py"],
      "output": ".agent/runs/phase3-4-ir-v2-resolution-runtime/v2_vector_runtime_cases/report.md"
    },
    {
      "id": "v2_prefix_parity_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_resolved_bundle_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_prefix_parity.py"],
      "output": ".agent/runs/phase3-4-ir-v2-resolution-runtime/v2_prefix_parity_cases/report.md"
    }
  ],
  "acceptance": [
    "Resolved input bundles retain edge_id, endpoint, binding, exact type, assembly, member order/key, and default provenance.",
    "Ordered, keyed, unordered, fan-out, defaults, and compound nesting are deterministic and reject malformed cases.",
    "Each compound public value, explicit default, or absence reaches every unique bound target unchanged; literals cannot be overridden and full nested parameter-target provenance is retained.",
    "Vector and independently coded prefix evaluation agree for supported causal fixtures and killed mutations fail.",
    "No runtime topology, provider/broker call, implicit time, or Phase 4 truth enters evaluation; v1 goldens pass."
  ],
  "test_plan": [
    "Run the four new v2 resolver/runtime clusters and current v1 resolver/runtime/streaming tests.",
    "Run focused determinism, prefix metamorphic, compound port/parameter propagation, nested provenance, and killed-mutation gates.",
    "Capture bounded local fan-in measurements without extrapolating production capacity.",
    "Run diff, protected-hash, and deployability checks."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase3_4_ir_v2_runtime_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/tests/test_ir_v2_resolution_bundles.py",
      "paper-trader/backend/tests/test_ir_v2_compound_resolution.py",
      "paper-trader/backend/tests/test_ir_v2_vector_runtime.py",
      "paper-trader/backend/tests/test_ir_v2_prefix_parity.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase3-4-ir-v2-resolution-runtime/owner_integration/report.md",
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

# IR v2 resolution and runtime goal

The owner establishes shared resolved-bundle interfaces. Four Luna test owners then work on disjoint surfaces; the parent integrates and proves the cross-path parity claim.
