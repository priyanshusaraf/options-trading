---
{
  "id": "phase3-4-ir-v2-implementation-recovery-correction",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "correction_iteration": 2,
  "goal": "Close only the independently reproduced IR v2 defects retained across the exhausted implementation recheck and the immutable first final review: ordinary compound-body graph validation, complete transitive component closure, lossless nested edge provenance, total structured rejection of malformed edges, and reproducible command attribution.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner explicitly authorized this one recovery-correction capsule and one new independent final-review stage on 2026-08-17. The active durable goal requires closure of the first final-review findings and one permitted focused dual-PASS recheck, so correction iteration 2 reopens this same capsule without creating another recovery capsule or review stage.",
    "stopping_condition": "Complete only after every retained counterexample is a failing-old and passing-corrected regression, the exact malformed-edge/cycle reversible mutation is killed, focused and affected compatibility evidence binds the final dirty tree with reproducible per-command metadata, protected paths remain unchanged, and a fresh official review package makes only the single focused recheck of phase3-4-ir-v2-implementation-final-review ready. Phase 4 remains blocked."
  },
  "risk_tags": ["critical", "registry-closure", "compound-topology", "edge-provenance", "malformed-input", "research-integrity", "runtime"],
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
    ".agent/runs/phase3-4-ir-v2-implementation-review/critical-recheck/bounded-counterexamples.log",
    ".agent/runs/phase3-4-ir-v2-implementation-review/critical-recheck/bounded_counterexamples.py",
    ".agent/runs/phase3-4-ir-v2-implementation-final-review/verdict.json"
  ],
  "allowed_paths": [
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
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/review-package.json",
    ".agent/runs/phase3-4-ir-v2-implementation-recovery-correction"
  ],
  "nonclaims": [
    "This recovery does not add a second IR, broaden Component IR v2, implement frontend authoring, open Phase 4, or authorize live IR, providers, credentials, deployment, VPS, production data, or production use.",
    "Passing local evidence proves neither release deployability nor production readiness, capacity, provider capability, or live-trading safety.",
    "The exhausted failed review and recheck remain immutable evidence and are not reclassified or overwritten."
  ],
  "owner_gates": [
    "Stop before any schema or migration change, new runtime stack, frontend edit, provider or broker change, live authority, deployment, credential, VPS, production-data, destructive, legal, regulatory, commercial, or Phase 4 action.",
    "Stop if the fix cannot remain a compatible hardening of the one accepted IR v2 validator, registry, resolver, and canonical identity contracts."
  ],
  "stop_conditions": [
    "A correction requires a protected file, migration, second IR, alternate validator/resolver/registry, caller-selected implementation seam, or relaxation of v1 behavior.",
    "Ordinary top-level and compound-body graph semantics cannot share one validation path without changing the frozen public document contract.",
    "Nested edge provenance cannot retain every authored boundary and leaf edge identity while preserving direct-edge compatibility.",
    "Any named counterexample or reversible mutation survives, a protected hash changes, inherited work conflicts, or final evidence cannot bind the exact dirty tree."
  ],
  "deployment_impact": {
    "classification": "compatible-runtime-hardening-no-schema-or-service-change",
    "affected_dimensions": ["Application", "CPU", "Memory", "Research runtime"],
    "required_evidence": "Focused compound validation, transitive closure, nested provenance, vector/prefix compatibility, mutation, protected-hash, frontend read-only, migration-head, and package-lineage evidence against the final tree. Only locally runnable behavior may be claimed."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 2,
  "completed_assignments_iteration_1": ["recovery_registry_regressions", "recovery_provenance_regressions", "recovery_mutation_evidence"],
  "owner_milestones": ["owner_malformed_edge_interface_frozen", "owner_product_code_frozen", "owner_tests_frozen"],
  "assignments": [
    {
      "id": "recovery_edge_regressions_v2",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_malformed_edge_interface_frozen"],
      "write_paths": [
        "paper-trader/backend/tests/test_ir_v2_edges_cardinality.py",
        "paper-trader/backend/tests/test_ir_v2_registry_compounds.py"
      ],
      "output": ".agent/runs/phase3-4-ir-v2-implementation-recovery-correction/recovery_edge_regressions_v2/report.md"
    },
    {
      "id": "recovery_edge_mutation_evidence_v2",
      "agent": "luna-worker",
      "mode": "write-evidence-only",
      "depends_on": ["owner_product_code_frozen", "owner_tests_frozen"],
      "write_paths": [".agent/runs/phase3-4-ir-v2-implementation-recovery-correction/recovery_edge_mutation_evidence_v2"],
      "output": ".agent/runs/phase3-4-ir-v2-implementation-recovery-correction/recovery_edge_mutation_evidence_v2/report.md"
    }
  ],
  "acceptance": [
    "A compound body is validated as the same complete ordinary v2 graph contract as a top-level graph, including closed node declarations, boundary ports, component references, endpoints, edge identity and semantic-tuple uniqueness, type and cardinality rules, bindings, and topology cycles.",
    "Registry construction rejects missing direct and transitively missing body components plus compound-reference cycles before any resolution or evaluator use.",
    "Recursive lowering preserves an ordered, deterministic provenance path containing every authored public, internal boundary, nested boundary, and leaf edge identity while retaining compatible direct provenance.edge_id behavior.",
    "Named regressions cover dangling and malformed body graphs, duplicate internal semantic tuples, direct and nested missing components, graph and component-reference cycles, two-level input/output edge paths, exact compound paths, and direct provenance compatibility.",
    "Top-level and compound-body non-object edges return ordered structured V2_OBJECT violations without exceptions, and an ordinary validly shaped graph cycle returns V2_CYCLE.",
    "A reversible mutation is killed for every critical guard and route-propagation seam; focused and affected v1/v2 compatibility tests pass without a broad confidence suite.",
    "No schema, migration, dependency, service, provider, API, frontend, live, deployment, credential, production, or Phase 4 change occurs; all protected hashes and frontend read-only checks match.",
    "Fresh attributed logs and the official review package bind each exact command to its own timestamp, actual cwd, HEAD, complete dirty fingerprint, exit status, assumptions, evidence class, retained evidence hashes, and final scoped-file hashes; every relative path reproduces from that command's declared cwd.",
    "Only phase3-4-ir-v2-implementation-final-review becomes ready. The former review stays blocked as historical evidence and Phase 4 stays blocked behind a separate owner gate."
  ],
  "test_plan": [
    "Add named top-level and compound-body non-object-edge regressions plus an ordinary graph-cycle product regression, then run the directly changed modules and the affected edge/cardinality, bundle, vector-runtime, prefix-parity, registry, and compound-resolution modules.",
    "Run an exact reversible mutation at the malformed-edge/cycle-iteration guard and retain iteration-1 mutation evidence for compound ordinary-graph validation, direct/transitive component closure, component-reference cycles, and nested edge-route preservation; require every mutation to fail the relevant test.",
    "Run final scoped diff, protected hashes, frontend read-only, migration-head, syntax/type checks applicable to changed modules, deployability-impact nonclaims, and official package verification with retained logs.",
    "Do not run broad backend or research suites merely for confidence and do not start any runtime that could touch live state."
  ],
  "review": {
    "required": true,
    "separate_stage": "phase3-4-ir-v2-implementation-final-review",
    "assignment_id": "phase3_4_ir_v2_recovery_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
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
    "output": ".agent/runs/phase3-4-ir-v2-implementation-recovery-correction/owner_correction_2/report.md",
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

# IR v2 implementation recovery correction

This is the only owner-authorized recovery after the exhausted implementation recheck. One Terra-medium owner hardens the existing validator, registry, and resolver; up to three disjoint Luna-medium children may add the declared tests and mutation evidence after the matching owner milestones. The owner integrates the final tree and stops after preparing a fresh independent final review. Phase 4 and every live or production boundary remain blocked.
