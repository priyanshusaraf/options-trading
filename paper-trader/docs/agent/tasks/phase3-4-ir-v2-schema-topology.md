---
{
  "id": "phase3-4-ir-v2-schema-topology",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Implement the reviewed v2 component, type, closed metadata, port, cardinality, edge, binding, compound parameter declaration, fixed-topology, validation, canonical content-address, and executable-identity contract in the single IR architecture.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after every reviewed v2 schema, compound declaration, canonical full-document/content identity, and executable-identity invariant has direct positive, negative, metamorphic, and relevant killed-mutation evidence; v1 golden behavior remains unchanged; and phase3-4-ir-v2-resolution-runtime is review-ready."
  },
  "risk_tags": ["critical", "ir-schema", "identity", "registry"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["4. One public architecture", "5. Canonical v2 document", "6. Type system", "7. Port contract", "8. Edge and binding contract", "9. Fixed topology and dynamic instruments", "11. Validation", "13. Serialization and identity", "15. Versioning"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["5. Scope boundaries", "6. Required IR v2 contract", "9. Dependency order and chat structure", "10.2 phase3-4-ir-v2-schema-topology", "11. Tests and evidence", "14. Stop and owner gates", "15. Required nonclaims"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/ir/schema.py",
    "paper-trader/backend/app/ir/validate.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/implementation_identity.py",
    "paper-trader/backend/app/ir/formats",
    "paper-trader/backend/tests/test_ir_v2_ports_types.py",
    "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
    "paper-trader/backend/tests/test_ir_v2_identity.py",
    "paper-trader/backend/tests/test_ir_v2_registry_compounds.py",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-schema-topology.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase3-4-ir-v2-schema-topology"
  ],
  "nonclaims": [
    "This task does not implement v2 evaluation, admission, persistence, API authoring, frontend support, Phase 4 market types, deployment, or live authority.",
    "A validated v2 graph is not admitted or executable."
  ],
  "owner_gates": [
    "Stop before adding provider truth, broker effects, dynamic topology, generic payloads, hidden coercion, frontend changes, migrations, or a second registry."
  ],
  "stop_conditions": [
    "Schema semantics diverge from the reviewed cardinality, edge binding, compound parameter binding, metadata, or identity tables.",
    "An executable mutation does not change graph_address or presentation mutation does.",
    "V1 golden evidence changes or a protected/inherited path conflicts."
  ],
  "deployment_impact": {
    "classification": "application-contract-additive",
    "affected_dimensions": ["Application", "Registry", "Serialization"],
    "required_evidence": "Deterministic schema, registry-construction, canonicalization, and compatibility evidence. No readiness claim."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": ["owner_v2_schema_interfaces"],
  "assignments": [
    {
      "id": "v2_ports_types_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_schema_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_ports_types.py"],
      "output": ".agent/runs/phase3-4-ir-v2-schema-topology/v2_ports_types_cases/report.md"
    },
    {
      "id": "v2_edges_cardinality_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_schema_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_edges_cardinality.py"],
      "output": ".agent/runs/phase3-4-ir-v2-schema-topology/v2_edges_cardinality_cases/report.md"
    },
    {
      "id": "v2_identity_metamorphic_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_schema_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_identity.py"],
      "output": ".agent/runs/phase3-4-ir-v2-schema-topology/v2_identity_metamorphic_cases/report.md"
    },
    {
      "id": "v2_registry_compound_declarations",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_v2_schema_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_registry_compounds.py"],
      "output": ".agent/runs/phase3-4-ir-v2-schema-topology/v2_registry_compound_declarations/report.md"
    }
  ],
  "acceptance": [
    "One PlatformRegistry owns exact types, classifications, ports, compounds, and implementation identities.",
    "All v2 metadata, port, shape, cardinality, edge binding, compound parameter declaration, topology, and validation rules are closed and deterministic.",
    "Canonical object-key/tag reordering preserves content_address and graph_address; descriptive metadata changes content_address only, presentation fields are rejected, and executable mutations change graph_address.",
    "V2 resolution/evaluation/admission remain closed until later capsules and v1 goldens pass."
  ],
  "test_plan": [
    "Run four new v2 schema/identity clusters and existing registry/identity tests.",
    "Reject unknown metadata, non-NFC strings, duplicate tags, missing/duplicate/unknown compound targets, descriptor mismatch, literal/binding conflict, and transform attempts.",
    "Kill mutations for wildcard type acceptance, binding order, compound parameter target uniqueness, metadata/content identity, and executable identity.",
    "Run v1 golden, diff, protected-hash, and deployability checks."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase3_4_ir_v2_schema_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/tests/test_ir_v2_ports_types.py",
      "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
      "paper-trader/backend/tests/test_ir_v2_identity.py",
      "paper-trader/backend/tests/test_ir_v2_registry_compounds.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase3-4-ir-v2-schema-topology/owner_integration/report.md",
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

# IR v2 schema and fixed-topology goal

The Terra owner decides and implements shared schema/registry interfaces. Luna children add only disjoint mechanical test surfaces after those interfaces stabilize.
