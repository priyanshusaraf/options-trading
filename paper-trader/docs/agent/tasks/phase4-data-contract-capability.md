---
{
  "id": "phase4-data-contract-capability",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Consume the accepted registry-bound DataRequirementPlan and assess immutable research, paper, and live data capability independently, binding exact plan, registry, assessment, and market/data identity to admission without granting execution authority.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after unknown, insufficient, mismatched, unentitled, and semantically broken capability fails closed and phase4-dataset-causality is eligible."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "provider-capability",
    "tenancy",
    "admission"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "3. One accepted executable architecture",
        "7. Data requirement and provider capability contracts",
        "9. Ownership, authority, and persistence",
        "11. Deployment contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    }
  ],
  "dependency_gate": "phase4-data-requirement-registry-correction",
  "allowed_paths": [
    "paper-trader/backend/app/market_data/capability.py",
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/tests/test_phase4_data_capability.py",
    "paper-trader/backend/tests/test_phase4_capability_admission.py",
    "paper-trader/docs/agent/tasks/phase4-data-contract-capability.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-data-contract-capability"
  ],
  "nonclaims": [
    "No provider is implemented or selected, no connection opens, no adapter changes, and no execution, deployment, or live IR authority is granted.",
    "A satisfied data assessment does not prove resource fit, protection compatibility, readiness, or provider behavior outside its evidence."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if work would duplicate accepted IR, validator, resolver, hash, registry, research lineage, execution binding, owner boundary, or authority."
  ],
  "stop_conditions": [
    "Assessment recompiles requirements, reads component descriptors, rebinds parameters, reinterprets topology, or bypasses the accepted registry/resolver/plan.",
    "A name, execution capability, unknown field, missing entitlement, or stale profile satisfies a data requirement.",
    "Owner, mode, plan, profile, dataset, market truth, evaluation policy, or assessment identity is omitted.",
    "A Phase 4 admission artifact is constructed outside backend/app/strategy/admission.py, the accepted base-v2 receipt is mutated or replaced, or either generic persistence seam assembles or repairs a Phase 4 binding."
  ],
  "deployment_impact": {
    "classification": "compatible-application-and-admission-change",
    "affected_dimensions": [
      "Application",
      "Admission",
      "Configuration-contract"
    ],
    "required_evidence": "Exact plan consumption, mode separation, owner isolation, secret exclusion, stale/change-level refusal, registry/plan/assessment admission attribution, compatibility, and bounded-query evidence; no service or provider connection."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Only the accepted immutable plan is consumed; exact authored IR, registry snapshot, resolved graph, implementation closure, declarations, owner, and mode remain bound without recompilation.",
    "Research, paper, and live data capability are independent and use closed reasons plus immutable profiles.",
    "Unknown, insufficient range/resolution/freshness, mode or entitlement mismatch, level-2 stale reassessment, and level-3 semantic break fail.",
    "The sole admit_phase4_v2_strategy seam in backend/app/strategy/admission.py wraps an exact accepted V2AdmittedStrategyArtifact, preserves its authored content address and base admission address, and computes a distinct wrapper admission address over the complete Phase 4 binding.",
    "Admission records exact owner, mode, registry, resolved graph, implementation closure, declarations, plan, assessment, dataset manifest, market truth, evaluation policy, and base-receipt addresses but grants no deployment or execution authority and does not create a future-result identity cycle.",
    "Execution and research persistence accept the wrapper through the existing protocol, recompute and persist identical complete artifact bytes, and refuse partial, forged, base-mismatched, stale, cross-owner, or cross-mode wrappers without constructing admission facts."
  ],
  "test_plan": [
    "Run backend/.venv/bin/python -m pytest -q backend/tests/test_phase4_data_capability.py backend/tests/test_phase4_capability_admission.py backend/tests/test_strategy_admission.py.",
    "Test deterministic permutations and unknown, stale, insufficient, cross-owner, cross-mode, plan/registry mismatch, data/execution confusion, missing entitlement evidence, semantic break, partial wrapper, forged wrapper address, embedded base-receipt mismatch, and byte-identical execution/research persistence.",
    "Kill and restore mutations that omit plan or registry snapshot identity from assessment/admission, bypass or duplicate the sole strategy-admission wrapper constructor, or admit a stale or mismatched assessment."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_data_contract_capability_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/market_data/capability.py",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/tests/test_phase4_data_capability.py",
      "paper-trader/backend/tests/test_phase4_capability_admission.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-data-contract-capability/owner_integration/report.md",
    "verdicts": [
      "INTEGRATION"
    ],
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

# Phase 4 data contract and capability

This is one durable implementation goal. It must retain full command output under its ignored evidence directory through `.codex/scripts/run_logged.py`.
