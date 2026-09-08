---
{
  "id": "phase4-data-requirement-registry-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Add the one immutable PlatformRegistry-closure declaration and identity route for Phase 4 data requirements, bind it through the accepted v2 resolver into one deterministic plan, and preserve v1 plus non-opted v2 compatibility.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after registry closure, canonical addressing, leaf and compound binding, plan identity, compatibility, refusals, and four killed-and-restored critical mutations have direct evidence and phase4-data-contract-capability is eligible."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "registry-identity",
    "resolution",
    "compatibility"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "3. One accepted executable architecture",
        "7. Data requirement and provider capability contracts",
        "8. Dataset provenance and cache identity",
        "11. Deployment contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "4. Capsule outcomes and failure hypotheses",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    }
  ],
  "dependency_gate": "phase4-data-requirement-registry-architecture-correction",
  "allowed_paths": [
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/tests/test_phase4_data_requirement_registry.py",
    "paper-trader/docs/agent/tasks/phase4-data-requirement-registry-correction.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-data-requirement-registry-correction"
  ],
  "nonclaims": [
    "This capsule implements no capability profile or assessment, admission persistence, dataset/cache change, provider, frontend, migration, service, configuration, credential, production, money, deployment, or live authority.",
    "A complete declaration or plan does not prove dataset availability, entitlement, provider conformance, execution support, capacity, readiness, or live suitability.",
    "V1 and v2 components without complete opt-in declarations make no Phase 4 capability claim."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if work would add a descriptor field, second registry/resolver/hash, mutable sidecar, provider inference, or authored-IR identity change."
  ],
  "stop_conditions": [
    "The frozen declaration cannot remain inside PlatformRegistry construction, validation, immutability, snapshot identity, and resolver closure using only allowed paths.",
    "A required product or test edit falls outside the four exclusive paths, an inherited accepted contract must be weakened, or a protected hash changes.",
    "Missing, malformed, unbound, stale, compound-owned, or mismatched declarations can compile a Phase 4 plan, or leaf provenance is lost."
  ],
  "deployment_impact": {
    "classification": "architecture-changing-application-contract",
    "affected_dimensions": [
      "Application-contract",
      "Admission-input-contract"
    ],
    "required_evidence": "Focused immutable-closure, deterministic-address, resolver-binding, plan, compatibility, refusal, import, protected-hash, and killed-mutation evidence. No schema, dependency, configuration, service, provider, secret, or process change; highest possible claim is focused locally_runnable behavior."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "PlatformRegistry alone deep-copies, validates, freezes, and content-addresses the exact design-§7.1 declaration object and requirements-array rows and its full snapshot; caller mutation, forged identity, unknown keys, compounds, and v1 keys fail.",
    "The accepted resolve_v2 path binds leaf declarations after compound lowering and preserves authored node, full lowered path, leaf reference, resolved parameter, and target-path provenance without changing authored IR identity.",
    "One canonical plan orders and addresses exact bound facts and refuses every missing, malformed, unbound, stale, duplicate, or mismatched Phase 4 input while legacy v1 and non-opted v2 behavior remain compatible and non-authoritative.",
    "Focused regressions and four named critical mutations fail under mutation and pass after exact restoration; protected hashes and deployment nonclaims remain exact."
  ],
  "test_plan": [
    "Run backend/.venv/bin/python -m pytest -q backend/tests/test_phase4_data_requirement_registry.py.",
    "Run read-only regressions backend/tests/test_ir_v2_registry_compounds.py backend/tests/test_ir_v2_compound_resolution.py backend/tests/test_ir_v2_identity.py backend/tests/test_ir_v2_legacy_compatibility.py backend/tests/test_ir_numeric_validity.py.",
    "Prove deterministic input-array permutations, canonical row sorting, duplicate-id rejection before normalization, exact ten-key rows, whole-field-only expressions, no nested expression, post-binding direct-value validation/freeze, canonical bytes, caller mutation isolation, v1 compatibility, v2 nonclaim, leaf and compound binding, exact target-path provenance, and every closed refusal.",
    "Kill and restore: declaration omission from registry snapshot; missing declaration treated as NO_DATA or inferred from name/port; wrong/default compound parameter or removed target_paths; declaration/registry identity omitted from resolved graph or plan.",
    "Run focused import, capsule/path, protected-hash, and git diff checks only; do not run broad suites, runtime, provider, database, migration, or deployment commands."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_data_requirement_registry_correction_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/registry.py",
      "paper-trader/backend/app/ir/resolve.py",
      "paper-trader/backend/app/market_data/requirements.py",
      "paper-trader/backend/tests/test_phase4_data_requirement_registry.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-data-requirement-registry-correction/owner_integration/report.md",
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

# Phase 4 data-requirement registry correction

This is one serial Terra-medium implementation goal. It repairs the accepted registry and resolver closure before capability work resumes. It must retain full command output under its ignored evidence directory through `.codex/scripts/run_logged.py` and may not create children.
