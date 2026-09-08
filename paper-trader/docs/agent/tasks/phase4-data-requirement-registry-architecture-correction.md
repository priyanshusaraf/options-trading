---
{
  "id": "phase4-data-requirement-registry-architecture-correction",
  "phase": "phase4",
  "status": "ready",
  "goal": "Correct the Phase 4 architecture so canonical data-requirement declarations have one immutable, registry-closure-bound identity and one explicit route into resolution, planning, assessment, and admission before capability implementation resumes.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the architecture and programme allocation close the discovered registry/identity gap, preserve accepted IR v2 and Phase 4 evidence, and make exactly one bounded Terra implementation route eligible."
  },
  "risk_tags": [
    "critical",
    "architecture-correction",
    "research-integrity",
    "registry-identity",
    "admission"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "3. One accepted executable architecture",
        "7. Data requirement and provider capability contracts",
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
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
  "dependency_gate": "phase4-market-truth-persistence",
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/reports/phase4-source-coverage.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/tasks/phase4-data-requirement-registry-architecture-correction.md",
    "paper-trader/docs/agent/tasks/phase4-data-requirement-registry-correction.md",
    "paper-trader/docs/agent/tasks/phase4-data-contract-capability.md",
    "paper-trader/docs/agent/tasks/phase4-integration-gate.md",
    "paper-trader/docs/agent/tasks/phase4-review.md",
    ".agent/runs/phase4-data-requirement-registry-architecture-correction"
  ],
  "nonclaims": [
    "This is a documentation and allocation correction only; it accepts no product implementation or Phase 4 capability behavior.",
    "It grants no frontend, provider, deployment, credential, production, money, or live authority."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if the correction creates a second registry, resolver, executable identity, research lineage, admission authority, or mutable sidecar."
  ],
  "stop_conditions": [
    "The proposal cannot bind declarations to the accepted PlatformRegistry closure and deterministic resolved/plan/assessment identity.",
    "The proposal changes authored IR meaning, puts provider transport or secrets into executable identity, or silently makes legacy components Phase 4 capable.",
    "The implementation allocation overlaps active ownership, lacks exact tests and mutations, or requires an undeclared product path."
  ],
  "deployment_impact": {
    "classification": "documentation-only-architecture-correction",
    "affected_dimensions": [
      "Application-contract",
      "Admission-contract"
    ],
    "required_evidence": "A closed architecture decision, exact serial path ownership, compatibility/refusal test allocation, and explicit locally-runnable-only nonclaim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "One immutable canonical declaration vocabulary and content-address rule are located inside the accepted PlatformRegistry closure, with no mutable or parallel sidecar.",
    "Resolution, compound expansion, plan compilation, capability assessment, registry snapshot, and admission identity each have an exact deterministic binding rule.",
    "Missing, malformed, parameter-unbound, stale, or mismatched declarations fail closed for Phase 4 while legacy non-Phase-4 behavior remains compatible and non-authoritative.",
    "The correction freezes one exact Terra implementation capsule or an explicitly amended capability capsule with disjoint current ownership, targeted tests, killed mutations, and deployment nonclaims."
  ],
  "test_plan": [
    "Run the agent architecture and programme dispatcher validators after the documentation/capsule correction.",
    "Prove every changed architecture claim maps to an exact implementation path, test, refusal, mutation, and final-review scope.",
    "Run no product tests or broad suite in this architecture-only capsule."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_data_requirement_registry_architecture_correction_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/agent/tasks/phase4-data-requirement-registry-correction.md",
      "paper-trader/docs/agent/tasks/phase4-data-contract-capability.md"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-data-requirement-registry-architecture-correction/owner/report.md",
    "verdicts": [
      "ARCHITECTURE"
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

# Phase 4 data-requirement registry architecture correction

The data-capability owner correctly stopped before implementation because the accepted `PlatformRegistry` has no immutable, closed declaration channel for the full Phase 4 data-requirement contract. A mutable registry attribute, free sidecar, test-only map, or compiler inference from component names is forbidden.

This capsule freezes the smallest correct architecture and serial path allocation. It does not edit product code. Its evidence must distinguish inspected facts, architecture decisions, implementation obligations, and retained unknowns.

## Decision

Verdict: `KEEP + HARDEN` the accepted `PlatformRegistry` and `resolve_v2`; do not widen the authored v2 descriptor grammar and do not create another registry or resolver.

The exact contract is frozen in design §7. `PlatformRegistry.data_requirement_declarations` is the sole declaration channel. It is an optional constructor input keyed only by exact v2 leaf component references. Registry construction deep-copies, validates, freezes, and content-addresses each closed `data-requirement-declaration/1` value and includes the sorted declaration map in one computed registry snapshot. Phase 4 requires an explicit `NO_DATA` or non-empty `REQUIRES_DATA` classification for every lowered leaf. Absence preserves v1 and non-opted v2 compatibility but refuses a Phase 4 plan; it never implies no data.

The accepted resolver binds declarations only after compound lowering, using the final leaf parameter values while retaining authored node id, full lowered path, leaf reference, and the existing parent-to-child `target_paths` provenance. One compiler turns those facts into a canonical plan. Missing, malformed, unbound, duplicate, stale, compound-owned, v1-owned, forged, or registry-mismatched declarations refuse closed.

The frozen declaration representation is one exact object whose `requirements` member is an input-order-insensitive array of exact ten-key rows. `requirement_id` is a literal row field; the other nine fields each contain exactly one whole-field literal or parameter expression. Nested scalar expressions are forbidden. Duplicate ids refuse before canonical row sorting, bound rows contain direct typed values and no expressions, and the existing canonical JSON/content-address functions address the normalized bytes. Terra has no representation choice left.

Authored IR, registry snapshot, resolved graph, implementation closure, declaration set, plan, assessment, dataset manifest, market-truth snapshot, evaluation policy, result/cache, and admission remain distinct addressed facts. Results and admissions bind the complete chain. No provider transport, symbol, secret, entitlement inference, execution capability, current time, connection, or mutable state enters a declaration or registry snapshot.

## Allocation

A separate Terra-medium capsule, `phase4-data-requirement-registry-correction`, is required. Amending `phase4-data-contract-capability` with the registry/resolver repair would give one owner both closure repair and capability judgment, obscure the compatibility gate, and overlap `requirements.py`. The new correction exclusively owns `backend/app/ir/registry.py`, `backend/app/ir/resolve.py`, `backend/app/market_data/requirements.py`, and `backend/tests/test_phase4_data_requirement_registry.py`. The capability capsule now exclusively owns capability assessment, the existing strategy admission producer, and the two generic admission persistence seams. Its dependency changes to the registry correction.

The correction runs accepted v1/v2, compound, identity, and numeric-validity tests as read-only regressions. It owns four killed-and-restored critical mutations: declaration omission from registry snapshot; missing declaration treated as `NO_DATA` or inferred from name/port; incorrect compound parameter binding or discarded `target_paths`; declaration/registry omission from resolved or plan identity. Capability explicitly owns `backend/app/strategy/admission.py` because inspection proved it is the existing sole v2 artifact producer. That capsule adds the Phase 4 wrapper and sole constructor there, keeps the accepted v2 receipt embedded and unchanged, and uses the already allocated execution/research persistence seams only to verify and persist identical wrapper bytes. It owns later mutations for plan/registry omission, wrapper-constructor bypass, and stale or mismatched assessment acceptance. Integration reproduces both evidence sets. Final review covers `backend/app/strategy/admission.py`, the complete registry-to-admission chain, and all retained nonclaims.

## Rejected alternatives

- A mutable registry attribute, unbound sidecar, compiler argument map, or test-only fixture map is outside the registry closure and has no stable identity.
- Adding fields to accepted v1 or v2 component descriptors changes the authored language and its accepted schema instead of adding platform registration metadata.
- Inferring data needs from names, ports, domain family, kernels, execution capability, or provider support is open-world and cannot prove `NO_DATA`.
- A second registry, resolver, graph hash, or Phase 4-only resolution route would split executable truth.
- Folding closure repair into capability assessment mixes identity production with sufficiency judgment and hides the exact compatibility boundary.

## Root transition recommendation

After this architecture capsule validates, the root coordinator should atomically mark this stage accepted, add `phase4-data-requirement-registry-correction` immediately after it as the sole ready stage, change the programme dependency of `phase4-data-contract-capability` to the correction, and add the correction to `phase4-implementation.expanded_by`. `CURRENT.md` should point only to the Terra correction. Data capability and every later stage remain blocked. The transition accepts documentation and allocation only, not implementation or any provider, frontend, deployment, credential, production, money, or live-authority claim.
