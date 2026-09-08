---
{
  "id": "phase4-authority-foundation-architecture-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Freeze one canonical Phase 4 authority foundation that closes CUR-C1 through CUR-C4 and CUR-H2, maps every invalidated claim to real-path revalidation, and allocates serial bounded implementation capsules without crossing provider, frontend, deployment, production, or live-money boundaries.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the architecture distinguishes every authoritative fact, defines canonical construction and process-reload verification, allocates exact disjoint correction and integration paths for CUR-C1 through CUR-C4 and CUR-H2, and records explicit containment, owner, capsule, and deadline for each deferred High finding."
  },
  "risk_tags": [
    "critical",
    "architecture-correction",
    "research-integrity",
    "canonical-identity",
    "authority",
    "persistence",
    "migration",
    "causality"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "3. One accepted executable architecture",
        "5. Canonical instrument and market-truth model",
        "6. Data observations, alignment, and causality",
        "7. Data requirement and provider capability contracts",
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
        "10. Acceptance scenarios and refusals",
        "11. Deployment contract",
        "12. Deferred homes and nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": [
        "13. Serialization and identity",
        "14. Admission and persistence",
        "17. Phase 4 handoff",
        "18. Deployability impact",
        "20. Acceptance conditions"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "1. Scope and stopping rule",
        "2. Dependency order",
        "3. Exclusive path ownership",
        "4. Capsule outcomes and failure hypotheses",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership",
        "Phase 5 ownership",
        "Phase 6 ownership",
        "V1 release gate"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "Status and evidence rules",
        "DP-001 — Distinct facts collapsed into one representation",
        "DP-002 — Syntactic self-consistency mistaken for authority",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-004 — Immutable envelope over mutable or time-incoherent facts"
      ]
    }
  ],
  "input_evidence": [
    ".agent/runs/phase4-v2-durable-graph-integration/root_acceptance/acceptance.md",
    ".agent/runs/phase4-v2-durable-graph-integration/owner_integration/report.md",
    ".agent/runs/phase4-v2-durable-graph-integration/owner_integration/evidence-manifest.json",
    ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/report.md",
    ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/finding-register.md",
    ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/transitive-evidence-invalidation-map.md",
    ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/assumptions-never-tested.md",
    ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/audit-surface-matrix.md"
  ],
  "dependency_gate": "phase4-v2-durable-graph-integration",
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/reports/phase4-source-coverage.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase4-authority-foundation-architecture-correction.md",
    "paper-trader/docs/agent/tasks/phase4-resolved-topology-identity-correction.md",
    "paper-trader/docs/agent/tasks/phase4-canonical-market-identity-correction.md",
    "paper-trader/docs/agent/tasks/phase4-typed-market-authority-correction.md",
    "paper-trader/docs/agent/tasks/phase4-dataset-assessment-authority-correction.md",
    "paper-trader/docs/agent/tasks/phase4-authority-integration-gate.md",
    "paper-trader/docs/agent/tasks/phase5-provider-evidence-compatibility.md",
    "paper-trader/docs/agent/tasks/phase5-graph-paper-attribution-schema.md",
    "paper-trader/docs/agent/tasks/phase6-generated-strategy-version-lineage.md",
    ".agent/runs/phase4-authority-foundation-architecture-correction"
  ],
  "nonclaims": [
    "This is a documentation, interface-freeze, evidence-invalidation, and serial-allocation capsule only. It implements no product, schema, migration, provider, frontend, runtime, deployment, production, or money behavior.",
    "It may define a provider entity/product/contract identity vocabulary but may not implement a provider adapter, acquire data, infer entitlements, access credentials, or declare any feed correct.",
    "It cannot restore any stale Phase 4 claim. Only later exact implementation, real process-death lifecycle evidence, transitive revalidation, and independent final review may do that."
  ],
  "owner_gates": [
    "Stop before authoritative live IR, material paper/live sizing, routing, risk or execution changes, frontend implementation, provider adapter work, credentials, VPS, production data/use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if the architecture creates a parallel IR, registry, instrument authority, market-truth authority, dataset authority, admission path, hash, cache lineage, or generic JSON escape hatch.",
    "Stop if any Critical is deferred, if a High deferral lacks containment plus an exact owner/capsule/deadline, or if a required product path cannot be allocated exclusively and serially."
  ],
  "stop_conditions": [
    "The design cannot express exact canonical underlier identity, provider entity/product/contract identity, separate provider and normalized observations, typed truth/capability reconstruction, canonical dataset bytes and coverage, or identity-complete resolved topology without weakening an accepted invariant.",
    "A constructor token, copied digest, metadata column, generic JSON envelope, current in-memory registry, same-process object, or monkeypatched consumer is required to grant persisted authority.",
    "The proposed lifecycle does not cross create/admit, persist, process death, reload, verify, and consume/refuse in both affected persistence planes, or does not define exact negative cases and killed mutations.",
    "The correction sequence overlaps write ownership, runs implementation in parallel across dependent identities, or requires a hidden future-phase rewrite."
  ],
  "deployment_impact": {
    "classification": "documentation-only-critical-authority-architecture-correction",
    "affected_dimensions": [
      "Application-contract",
      "Identity-contract",
      "Persistence-contract",
      "Migration-contract",
      "Research-lineage",
      "Admission-contract",
      "Cache-result-contract"
    ],
    "required_evidence": "Freeze exact typed documents, canonical bytes and addresses, equality and ownership rules, reconstructors, execution/research rows, migration heads, rollback/refusal behavior, real fresh-process lifecycle, transitive revalidation matrix, serial path ownership, and explicit non-deployability."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "A fact/equality matrix distinguishes canonical instrument, exact economic underlier, provider entity/product/contract, provider observation, normalized observation, market-truth snapshot, capability profile, capability assessment, dataset manifest, dataset bytes/segments, authored graph, resolved topology, admission, result, and cache identities. No two are silently interchangeable.",
    "Each authoritative fact has one typed closed document, canonical constructor, canonical bytes/address, owner and version rule, persistent representation, process-reload reconstructor, duplicated-column equality rule, and refusal behavior. Public structural validation alone grants no authority.",
    "Dataset authority binds exact bytes or immutable segment addresses, instruments, fields, time range, gaps, corrections, provider product/contract and schema, truth/capability/policy/transform/algorithm identities, owner, and coverage. Assessment and admission load and recompute the authoritative chain rather than accept address syntax.",
    "Derivative identity binds the exact canonical underlying instrument identifier. Provider symbols and display labels remain temporal aliases. Provider observations and normalized observations are separate typed persisted facts with exact transformation/rulebook provenance and correction behavior.",
    "Resolved graph identity changes for every semantic topology change, including edges, bundles, graph inputs/outputs/defaults, compound assembly, member binding/type, and provenance, while authored, registry, implementation, and resolved facts remain distinct.",
    "The design includes adversarial substitutions for arbitrary addresses, generic/minimal rows, wrong owner/product/contract/underlier, alias collisions, malformed or column-disagreeing documents, missing fields/instruments/ranges/bytes, digest mismatch, changed rules/transforms/gaps, topology-only mutations, stale facts, cross-plane substitutions, partial writes, and process restart.",
    "Every invalidated Phase 4 contract, test, report, scenario, cache/result claim, and prior verdict is marked STALE/REQUIRES RECHECK and assigned to one exact later correction or integration gate.",
    "CUR-C1 through CUR-C4 and CUR-H2 receive serial bounded implementation capsules with exclusive paths, Sol-medium owners, only declared Luna-max mechanical children, targeted tests, required killed mutations, migration and deployability gates, and no uncontrolled rewrite.",
    "CUR-H1, CUR-H3, and CUR-H4 are either closed in the serial correction sequence or explicitly contained with rationale, named owner, exact future capsule, and a hard before-use deadline. No affected consumer may become authoritative before its gate closes."
  ],
  "test_plan": [
    "Run only capsule, programme, architecture-source-map, JSON, deployability, protected-hash, and scoped diff validation. Run no product tests, migrations, services, providers, frontend, runtime, deployment, or broad suite.",
    "Trace every design decision to an exact production path, migration, test, negative case, killed mutation, lifecycle step, evidence artifact, and final-review assertion.",
    "Validate that later capsules have disjoint serial write ownership and that the final integration gate replays the full transitive chain without monkeypatching authority, persistence, reload, or consumption."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_authority_foundation_architecture_correction_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase4-resolved-topology-identity-correction.md",
      "paper-trader/docs/agent/tasks/phase4-canonical-market-identity-correction.md",
      "paper-trader/docs/agent/tasks/phase4-typed-market-authority-correction.md",
      "paper-trader/docs/agent/tasks/phase4-dataset-assessment-authority-correction.md",
      "paper-trader/docs/agent/tasks/phase4-authority-integration-gate.md"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase4-authority-foundation-architecture-correction/owner/report.md",
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

# Phase 4 authority-foundation architecture correction

The durable Component IR v2 graph correction closes the original content-address versus executable-address contradiction only for its bounded persisted verification and refusal path. The independent checker found four separate Critical authority defects and one immediate High graph-identity defect. This capsule freezes the complete correction architecture before any further product edit.

The architecture owner must work from first principles and may not inherit a historical PASS as truth. It must answer which fact authorizes each decision, how that fact is constructed, which canonical bytes identify it, where it is persisted, how a new process reconstructs it, which exact owner/product/version it belongs to, and which consumer verifies it. Any missing answer is an open design defect.

The output is one serial implementation route, not a broad rewrite. It must preserve accepted Component IR v1/v2 compatibility and the current `V2_RUNTIME_UNAVAILABLE` boundary. It must not implement provider adapters, frontend behavior, deployment, credentials, paper/live execution, orders, or money authority.

## Frozen architecture outcome

Verdict: `KEEP + HARDEN`. Design §13 defines the canonical fact/equality matrix, bytes and address rules, owner/provider/product/contract/quality equality, execution and research persistence split, verified loaders, migration/backfill/refusal rules, process-death lifecycle, adversarial matrix, stale evidence map, and High-finding containment.

The adversarial matrix is frozen as 27 separate classified rows, `ADV-001` through `ADV-027`. Every row names exact Phase 4 primary capsule ownership and real-path evidence/refusal/identity-change requirements. The four correction capsules inherit their exact subsets in `adversarial_rows`; the integration gate inherits all 27. Validation must reject missing, duplicate, out-of-range, or unowned rows and any integration omission. Grouped evidence cannot replace an individual row observation.

Mandatory serial order:

1. `phase4-resolved-topology-identity-correction` closes CUR-H2.
2. `phase4-canonical-market-identity-correction` closes CUR-C2, CUR-C3, and CUR-H1 and owns execution `0038`.
3. `phase4-typed-market-authority-correction` closes CUR-C4 against `0038`.
4. `phase4-dataset-assessment-authority-correction` closes CUR-C1 and owns research `0009`.
5. `phase4-authority-integration-gate` rechecks the full transitive chain and patches no product.

CUR-H3 and CUR-H4 remain contained by explicit forbidden-consumer lists and hard pre-use dependencies in `phase5-graph-paper-attribution-schema` and `phase6-generated-strategy-version-lineage`. This outcome changes no programme state and makes no integration, final-review, deployment, production, live, or money claim.
