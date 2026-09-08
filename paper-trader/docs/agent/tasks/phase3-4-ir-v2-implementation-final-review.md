---
{
  "id": "phase3-4-ir-v2-implementation-final-review",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "review_iteration": 2,
  "goal": "Independently accept or reject the complete IR v2 implementation in the one focused recheck after bounded correction of the immutable first final-review findings, without opening Phase 4 or any live, frontend, deployment, credential, production, or provider boundary.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner explicitly authorized this new independent final-review stage on 2026-08-17.",
    "stopping_condition": "Complete only after one fresh read-only critical reviewer verifies the corrected official package and returns separate SPEC and QUALITY verdicts in the focused recheck output. Dual PASS accepts only the reviewed IR v2 implementation; Phase 4 remains manually blocked pending a separate owner decision. Any other result exhausts the route and leaves IR v2 and Phase 4 blocked."
  },
  "risk_tags": ["critical", "read-only-product-review", "registry-closure", "compound-topology", "edge-provenance", "identity", "research-integrity", "authority"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["1. Decision", "4. One public architecture", "8. Edge and binding contract", "10. Compound components", "11. Validation", "12. Evaluation", "13. Serialization and identity", "14. Admission and persistence", "18. Deployability impact", "20. Acceptance conditions"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["3. Accepted baseline", "5. Scope boundaries", "6.2 Component and type registry", "6.4 Edges and cardinality", "6.5 Topology and compound components", "6.6 Validation and evaluation", "11. Tests and evidence", "12. Documentation and programme state", "13. Protected files and inherited work", "14. Stop and owner gates", "15. Required nonclaims", "16. Final gate", "17. Final report"]
    }
  ],
  "input_evidence": [
    ".agent/runs/phase3-4-ir-v2-implementation-review/verdict.json",
    ".agent/runs/phase3-4-ir-v2-implementation-review/recheck-verdict.json",
    ".agent/runs/phase3-4-ir-v2-implementation-final-review/verdict.json",
    ".agent/runs/phase3-4-ir-v2-implementation-recovery-correction",
    "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-implementation.md",
    ".agent/review-package.json"
  ],
  "allowed_paths": [
    ".agent/runs/phase3-4-ir-v2-implementation-final-review",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md"
  ],
  "product_paths_read_only": ["paper-trader/backend", "paper-trader/frontend"],
  "nonclaims": [
    "Dual PASS accepts only the reviewed Component IR v2 implementation; it does not open Phase 4 or prove production readiness, release deployability, frontend v2 authoring, provider capability, capacity, or live-trading safety.",
    "The reviewer performs no product-code, test, package, or evidence correction and does not overwrite any historical failed verdict."
  ],
  "owner_gates": [
    "Stop before any product, test, frontend, package, or retained-evidence edit; before deployment, provider, live authority, VPS, credential, production-data, destructive, legal, regulatory, commercial, or Phase 4 action."
  ],
  "stop_conditions": [
    "The official package, dirty fingerprint, scoped hashes, evidence hashes, protected hashes, or failed-review lineage is stale, absent, or inconsistent.",
    "Any exhausted-recheck counterexample still succeeds, any required reversible mutation survives, or direct and nested provenance compatibility is ambiguous.",
    "A fix would be required: record FAIL and stop because this focused recheck is the final permitted review iteration."
  ],
  "deployment_impact": {
    "classification": "read-only-review-of-compatible-runtime-hardening",
    "required_evidence": "Verify the recovery's no-schema/no-service classification and locally runnable evidence without inferring release deployability, deployment, or production readiness."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Package lineage, complete dirty-tree fingerprint, every scoped-file hash, every retained-evidence hash, and protected hashes verify before substantive review.",
    "The reviewer independently reproduces or inspects the named dangling body, duplicate internal tuple, direct and transitive missing component, graph cycle, component-reference cycle, and two-level provenance cases.",
    "The reviewer independently verifies that top-level and compound-body non-object edges return ordered V2_OBJECT violations without exceptions, that a validly shaped ordinary cycle returns V2_CYCLE, and that the exact malformed-edge/cycle mutation is killed.",
    "Every retained command is reproducible from its declared per-command cwd and is bound to its own timestamp, exact command, HEAD, dirty fingerprint, exit status, assumptions, and evidence class.",
    "The reviewer verifies ordinary top-level and compound-body validation share one semantic contract, registry closure is complete before evaluation, and recursive lowering retains every authored edge identity with deterministic paths and direct compatibility.",
    "Every critical reversible mutation is killed by a named regression; focused and affected compatibility evidence is attributable to the packaged tree.",
    "Separate SPEC and QUALITY verdicts are explicit. Dual PASS accepts IR v2 only; Phase 4 stays blocked pending separate owner authorization."
  ],
  "test_plan": [
    "Verify the official package, HEAD/base, complete dirty fingerprint, exact review paths, evidence hashes, protected hashes, frontend exclusion, migration heads, and historical failed-verdict hashes.",
    "Re-run only the bounded counterexamples and high-value named focused commands needed to challenge the recovery claims.",
    "Write only the focused recheck verdict JSON with separate SPEC and QUALITY results and exact evidence references; preserve the immutable first verdict and make no other file change."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase3_4_ir_v2_implementation_final_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/formats/v2.py",
      "paper-trader/backend/app/ir/registry.py",
      "paper-trader/backend/app/ir/resolve.py",
      "paper-trader/backend/tests/test_ir_v2_registry_compounds.py",
      "paper-trader/backend/tests/test_ir_v2_compound_resolution.py",
      "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
      "paper-trader/backend/tests/test_ir_v2_prefix_parity.py",
      "paper-trader/backend/tests/test_ir_v2_vector_runtime.py",
      "paper-trader/backend/tests/test_ir_v2_resolution_bundles.py",
      "paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-implementation.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-implementation-recovery-correction.md",
      "paper-trader/docs/agent/tasks/phase3-4-ir-v2-implementation-final-review.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md"
    ],
    "exclude_paths": ["paper-trader/frontend"],
    "first_output": ".agent/runs/phase3-4-ir-v2-implementation-final-review/verdict.json",
    "output": ".agent/runs/phase3-4-ir-v2-implementation-final-review/recheck-verdict.json",
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

# IR v2 independent final implementation review

This is the single focused read-only Sol-high recheck after bounded correction of the immutable first final-review findings. It has no child agents, no product edits, and no further correction or recheck route. Even dual PASS leaves Phase 4 blocked for a separate owner decision.
