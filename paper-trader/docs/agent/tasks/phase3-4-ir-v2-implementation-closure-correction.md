---
{
  "id": "phase3-4-ir-v2-implementation-closure-correction",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Close the three bounded Component IR v2 implementation defects found by the first independent review: complete compound graph lowering, immutable transitive implementation authority, and semantic duplicate-edge rejection.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after every first-review counterexample is a failing-old and passing-corrected regression, all corresponding reversible mutations are killed, fresh attributed evidence and an official review package bind the final tree, and phase3-4-ir-v2-implementation-review is ready for its single focused recheck while Phase 4 remains blocked."
  },
  "risk_tags": ["critical", "registry-identity", "compound-topology", "research-integrity", "admission-authority", "runtime"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["4. One public architecture", "8. Edge and binding contract", "10. Compound components", "11. Validation", "12. Evaluation", "13. Serialization and identity", "14. Admission and persistence", "20. Acceptance conditions"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["5. Scope boundaries", "6. Required IR v2 contract", "10.7 phase3-4-ir-v2-implementation-review", "11. Tests and evidence", "14. Stop and owner gates", "15. Required nonclaims", "16. Final gate"]
    }
  ],
  "input_evidence": [
    ".agent/runs/phase3-4-ir-v2-implementation-review/verdict.json",
    ".agent/runs/phase3-4-ir-v2-implementation-review/critical-reviewer/compound_boundary_omission_counterexample.log",
    ".agent/runs/phase3-4-ir-v2-implementation-review/critical-reviewer/compound_topology_counterexample_verified.log",
    ".agent/runs/phase3-4-ir-v2-implementation-review/critical-reviewer/compound_literal_binding_counterexample.log",
    ".agent/runs/phase3-4-ir-v2-implementation-review/critical-reviewer/v2_implementation_identity_counterexample.log",
    ".agent/runs/phase3-4-ir-v2-implementation-review/critical-reviewer/duplicate_edge_tuple_counterexample.log"
  ],
  "allowed_paths": [
    "paper-trader/backend/app/ir/formats/v2.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/implementation_identity.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/streaming_reference.py",
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/tests/test_ir_v2_registry_compounds.py",
    "paper-trader/backend/tests/test_ir_v2_compound_resolution.py",
    "paper-trader/backend/tests/test_ir_v2_admission_receipt.py",
    "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
    "paper-trader/backend/tests/test_ir_v2_vector_runtime.py",
    "paper-trader/backend/tests/test_ir_v2_prefix_parity.py",
    "paper-trader/backend/tests/test_ir_v2_resolution_bundles.py",
    "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-implementation-closure-correction.md",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-implementation-review.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/review-package.json",
    ".agent/runs/phase3-4-ir-v2-implementation-closure-correction"
  ],
  "nonclaims": [
    "This correction does not add a second IR, broaden Component IR v2, implement frontend v2 authoring, open Phase 4, or authorize live IR, deployment, providers, credentials, VPS, or production data.",
    "Passing local evidence does not prove production readiness, release deployability, capacity, cost, provider capability, or live trading safety.",
    "The first failed review remains part of the evidence lineage and is not overwritten."
  ],
  "owner_gates": [
    "Stop before any migration or persistence-schema change; the existing immutable JSON receipt and registry snapshot are the expected representation. If a schema change is proven necessary, correct this capsule before work continues.",
    "Stop before frontend implementation, provider or broker behavior, live authority, deployment, credentials, VPS, production data, destructive action, or Phase 4 semantics."
  ],
  "stop_conditions": [
    "A correction requires a protected file, migration, second IR/runtime stack, caller-selected executable implementation, or relaxation of v1 behavior.",
    "Compound lowering cannot preserve exact public/internal/nested edge and parameter provenance without changing the frozen contract.",
    "A reviewer counterexample or corresponding mutation survives, a protected hash changes, or inherited work conflicts.",
    "Fresh evidence cannot bind timestamp, cwd, exact command, HEAD, complete dirty fingerprint, exit status, assumptions, and evidence class."
  ],
  "deployment_impact": {
    "classification": "runtime-and-admission-correction-no-schema-change",
    "affected_dimensions": ["Application", "CPU", "Memory", "Research runtime", "Admission identity"],
    "required_evidence": "Focused compound, identity, admission, vector/prefix, v1 compatibility, mutation, integrity, and deployability-impact evidence against the final tree. Existing SQLite and isolated PostgreSQL evidence may be cited only if persistence shape and migrations remain unchanged."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": ["owner_v2_closure_interfaces_frozen"],
  "assignments": [
    {
      "id": "v2_registry_implementation_closure_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_closure_interfaces_frozen"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_registry_compounds.py"],
      "output": ".agent/runs/phase3-4-ir-v2-implementation-closure-correction/v2_registry_implementation_closure_cases/report.md"
    },
    {
      "id": "v2_admission_identity_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_closure_interfaces_frozen"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_admission_receipt.py"],
      "output": ".agent/runs/phase3-4-ir-v2-implementation-closure-correction/v2_admission_identity_cases/report.md"
    },
    {
      "id": "v2_compound_lowering_runtime_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_closure_interfaces_frozen"],
      "write_paths": [
        "paper-trader/backend/tests/test_ir_v2_compound_resolution.py",
        "paper-trader/backend/tests/test_ir_v2_vector_runtime.py",
        "paper-trader/backend/tests/test_ir_v2_prefix_parity.py"
      ],
      "output": ".agent/runs/phase3-4-ir-v2-implementation-closure-correction/v2_compound_lowering_runtime_cases/report.md"
    },
    {
      "id": "v2_duplicate_semantic_edge_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_closure_interfaces_frozen"],
      "write_paths": [
        "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
        "paper-trader/backend/tests/test_ir_v2_resolution_bundles.py"
      ],
      "output": ".agent/runs/phase3-4-ir-v2-implementation-closure-correction/v2_duplicate_semantic_edge_cases/report.md"
    }
  ],
  "acceptance": [
    "Every compound body is a complete ordinary v2 graph with graph inputs, graph outputs, nodes, and edges; boundary mappings are exact, literal/public-binding collisions and incomplete/dangling bodies refuse, and recursive lowering leaves only executable leaf nodes.",
    "Outer, internal, and nested compound edges and public parameter bindings are lowered without changing value or identity, with complete deterministic provenance retained through vector and independently coded prefix evaluation.",
    "PlatformRegistry is the sole immutable v2 implementation authority. It requires an exact executable leaf and transitive compound closure, rejects absent, extra, stale, forged, or conflicting registrations, and exposes no caller-selected implementation seam to either evaluator.",
    "Admission snapshots and receipts bind the exact transitive implementation identities used by evaluation. The same admitted document cannot execute different code without an admitted identity change and stale receipts fail closed.",
    "Duplicate canonical source-target-binding tuples are rejected independently of edge_id before cardinality or bundle assembly, including applicable ordered, keyed, unordered, single, and boundary cases.",
    "Every first-review counterexample has a direct regression, every corresponding reversible mutation is killed, current v1 goldens remain unchanged, frontend source remains untouched, and protected hashes match.",
    "Retained command logs carry timestamp, cwd, exact command, HEAD, complete dirty fingerprint, exit status, assumptions, and evidence class; a fresh official package hashes those logs and the final scoped tree.",
    "No migration or persistence-schema change is introduced, and phase3-4-ir-v2-implementation-review alone becomes ready for one focused recheck while Phase 4 stays blocked."
  ],
  "test_plan": [
    "Replay each first-review counterexample as a named regression and run the seven focused v2 test modules plus current v1 registry, resolver, runtime, streaming, admission, and API compatibility goldens.",
    "Run reversible mutations for compound completeness and rewiring, literal-binding collision, implementation closure and evaluator authority, admission identity pinning, and duplicate semantic tuples; require every mutation to be killed.",
    "Run final diff, protected-hash, frontend read-only, migration-head, deployability-impact, and package-lineage checks with fully attributed retained logs.",
    "Do not run broad backend/research suites merely for confidence. If persistence representation changes despite the stop gate, do not accept prior database evidence."
  ],
  "review": {
    "required": true,
    "separate_goal": "phase3-4-ir-v2-implementation-review",
    "assignment_id": "phase3_4_ir_v2_implementation_closure_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/tests/test_ir_v2_registry_compounds.py",
      "paper-trader/backend/tests/test_ir_v2_compound_resolution.py",
      "paper-trader/backend/tests/test_ir_v2_admission_receipt.py",
      "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
      "paper-trader/backend/tests/test_ir_v2_vector_runtime.py",
      "paper-trader/backend/tests/test_ir_v2_prefix_parity.py",
      "paper-trader/backend/tests/test_ir_v2_resolution_bundles.py",
      "paper-trader/docs"
    ],
    "exclude_paths": ["paper-trader/frontend"],
    "output": ".agent/runs/phase3-4-ir-v2-implementation-closure-correction/owner_integration/report.md",
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

# IR v2 implementation closure correction

This is the one bounded correction permitted after the first implementation review. The Terra owner freezes the v2 registration, compound-lowering, evaluator, duplicate-edge, and receipt interfaces before four disjoint Luna test owners begin. The owner integrates the final tree, regenerates attributed evidence and the official package, and stops before the independent focused recheck.
