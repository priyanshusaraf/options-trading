---
{
  "id": "phase1-4-foundation-research-migration-native-state-contract-core-recovery",
  "phase": "interphase-4-5",
  "status": "active",
  "goal": "Recover an exact, implementable native-state contract-core design after the first bounded core slice exhausted its attempt budget with a strict-serialization failure and materially reduced contract surfaces.",
  "risk_tags": [
    "critical",
    "architecture-recovery",
    "research-migration",
    "native-state-contract",
    "false-green-evidence",
    "research-integrity"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "14. Foundation migration and market-number correction contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "9. Foundation migration and numeric correction route"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Foundation migration and numeric correction",
        "Foundation blockers",
        "Phase 4 ownership"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-implementation-repeated-failure-recovery.md",
      "sections": [
        "Native-state implementation repeated-failure recovery"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-contract-core.md",
      "sections": [
        "Native-state contract core"
      ]
    }
  ],
  "goal_contract": {
    "create_before_work": true,
    "durable_goal": "Produce and directly validate one exact wire, type, declaration, canonical-byte, digest, comparison, and expected-state authority contract; classify every failed core byte; and emit one fresh bounded successor capsule without changing product or test bytes.",
    "stopping_condition": "Complete only when the failure lineage, exact closed type schemas and identities, public wire roots, private canonical-value encoding boundary, domain-separated digest preimages and order, declaration authority, expected-before-locator state machine, comparison result contract, negative matrix, retained-byte disposition, and fresh successor capsule are explicit and same-byte validated. Return BLOCKED if any choice remains for the successor, authority would need invention or observed-state inference, or repository validation cannot pass.",
    "recovery_rule": "The failed core owner is retired. Its implementation remains frozen and unaccepted. This architecture owner may not patch those bytes, activate the observer, or enter obligation, mutation, runtime, integration, numeric, transitive, review, deployment, production, live, order, or money scope."
  },
  "dependency_gate": "native-state-contract-core-two-attempt-capsule-blocker-root-accepted",
  "trigger_evidence": {
    "root_blocker_acceptance": {
      "path": ".agent/runs/phase1-4-foundation-critical-closure/native-state-contract-core-blocker-acceptance.json",
      "sha256": "58a9237891ceec6d7acdfc0d426424320353650d87940f8cf201d62473580e2a"
    },
    "owner_report": {
      "path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core/foundation_native_state_contract_core_owner/report.md",
      "sha256": "b850f7dee3c17e8e7b296d32d764d6d8bb557cb3300d80c9ceec8159a9509203"
    },
    "owner_manifest": {
      "path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core/foundation_native_state_contract_core_owner/evidence-manifest.json",
      "sha256": "327cd61f7f831b21fe30734db58aac65c05c6809492ef8d1c2b9117fae960eb0"
    },
    "root_focused_rerun": {
      "path": ".agent/runs/phase1-4-foundation-critical-closure/root/native-state-contract-core-blocker-independent-rerun.log",
      "sha256": "f2914937b3f88090eb0addacfa18891cf7aec4910fb9de8a3031a5a4ad5c6594"
    },
    "root_blocker_validator": {
      "path": ".agent/runs/phase1-4-foundation-critical-closure/root/validate_native_state_contract_core_blocker.py",
      "sha256": "0c30e87dcdeaef682fd1bc81e160f92edbcd6ddfaa62c316b3b9e0037ecd1f6f"
    },
    "root_passing_audit": {
      "path": ".agent/runs/phase1-4-foundation-critical-closure/root/native-state-contract-core-blocker-root-audit-rerun.log",
      "sha256": "d086300a3c2b4873e7cff751010548743fc7c98a06b179b7d57b232754ad8c45"
    }
  },
  "upstream_architecture": {
    "report_sha256": "d5dc4e9af248848ebf38d6f95460c312feb772f57945c26d5a672b17dbe041f6",
    "manifest_sha256": "095662eb93843b1d6ccba152d1f00f9fd3c4bfeadceec6df7387527eb3083bbf",
    "code_topology_sha256": "644f3e39525146c556ed75ae89eff193b85dc28ebf7547fe706ed288599ebfd8",
    "authority_map_sha256": "9b5d6530a447bc310348ffaeeaece8cd163a1191bccb37ae6ee10d2e2109e247",
    "obligation_map_sha256": "6e0e26d30c8147108aa18ffecdb588dcfb2a0588314945899c1faf8d129c774d",
    "byte_disposition_sha256": "8a9f7fcf6ee239f171dfdec6f186951421fd86bff548f07e4369efe5c9a83682",
    "capsule_dag_sha256": "412d58a094ef7e8a7b2c780f2aa02f9d68001762d18a18e5026141273c62322d"
  },
  "frozen_unaccepted_inputs": {
    "paper-trader/backend/tests/foundation_native_state_contract.py": "6643a7e34177d586241ba01b03a0a149f711061266f2cfbb2c4491449b313ca0",
    "paper-trader/backend/tests/foundation_native_state_declarations.py": "61798987ae520a23b19909645cf999c98f0d2fa6c6edfc963ccc47b13a1877b7",
    "paper-trader/backend/tests/test_foundation_native_state_contract_core.py": "01b662c85fdc43c7cf84f3d10d70fee48151a4a4fb494866f86fd3ddec1fcf2a"
  },
  "known_findings": [
    "Attempt 1 failed during collection. Attempt 2 reached the contract and failed because ExpectedNativeState.from_caller passes a tuple root through canonical_bytes while strict_to_wire permits only dataclass roots.",
    "A tuple-only patch is insufficient: the failed bytes use placeholder DATA-01 through DATA-24 and CAT-01 through CAT-39 values instead of the exact closed obligation identities.",
    "The failed bytes materially reduce OwnerPolicyKind, FrozenCatalogDeclaration, SequenceDeclaration, ComparisonResult, and declaration coverage relative to the sealed architecture.",
    "The current core test covers a one-table example and cannot establish the declaration authority or closed type system needed by the serial observer and obligation slices.",
    "No failed core byte, observer activation, downstream evidence, deployability, foundation, Phase 5, or Phase 6 claim is accepted."
  ],
  "required_decisions": {
    "failure_lineage": "Map each activated capsule requirement and upstream machine-contract fact to the failed implementation and tests. Distinguish the collection false start, the surviving tuple-root failure, and every structural omission.",
    "wire_boundary": "Declare the exact public strict_to_wire and strict_from_wire root types, tags, field names, enum forms, tuple/list and mapping ordering, unknown and missing field refusal, versioning, and round-trip guarantees. Define a separate private canonical-value encoder if nested digest values are not public wire roots; public strictness may not be weakened to accept arbitrary containers.",
    "closed_types": "Freeze exact members and field schemas for every named core type, including all 24 DATA and 39 CAT identities, owner policies, catalog facts, sequences and bindings, expected and observed states, receipts, consumer specs, comparison results, and claim attestation.",
    "digest_contract": "Specify domain names and versions, byte framing, scalar tags, key and field ordering, table ordering, per-table preimages, aggregate preimages, empty/null distinctions, timestamp/date/boolean/binary/text encoding, and exact rejection of unsupported or ambiguous values.",
    "authority_state_machine": "Make expected construction caller-and-frozen-declaration only; finish and receipt it before locator lease issue. Observed state, database imports, mutable registries, adapters, environment state, and locator facts must be impossible inputs to expected construction.",
    "declaration_contract": "Bind exact immutable SQLite and PostgreSQL catalog declarations to the core declaration types without database access, current metadata, rewinds, observed inference, or one-table placeholders. Separate core declaration construction from observer and obligation execution.",
    "comparison_contract": "Specify exact comparison output and mismatch identities for every native-state field. Equality must bind both canonical bytes and structured facts and cannot normalize away a meaningful native distinction.",
    "negative_matrix": "Require one-at-a-time unknown field, missing field, wrong tag, wrong enum, tuple/list swap, order change, unsupported scalar, observed-source injection, locator-first, declaration omission, DATA/CAT omission, digest-domain, and comparison-fact mutations.",
    "byte_disposition": "For each of the three failed files, return KEEP_UNACCEPTED_FOR_EXACT_REUSE, REPLACE_IN_SUCCESSOR, SPLIT_IN_SUCCESSOR, or REMOVE_IN_SUCCESSOR with evidence.",
    "successor": "Emit one exact fresh Terra-medium successor capsule for foundation_native_state_contract_core_owner_2 with these same three product/test paths, one durable goal, no children, parallel budget zero, initial patch plus at most one repair, exact focused tests, and a root acceptance gate.",
    "serial_dag": "Keep the observer, 24-DATA/39-CAT obligation evidence, mutation attestation, runtime correction, integration, numeric correction, transitive revalidation, and one critical review blocked behind accepted core implementation in that order."
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/failure-lineage.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/wire-and-type-authority-contract.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/digest-and-comparison-contract.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/expected-state-machine.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/negative-test-matrix.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/byte-disposition.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/capsule-dag.json"
  ],
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-contract-core-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-contract-core.md",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-implementation-repeated-failure-recovery",
    "paper-trader/backend/tests/foundation_native_state_contract.py",
    "paper-trader/backend/tests/foundation_native_state_declarations.py",
    "paper-trader/backend/tests/test_foundation_native_state_contract_core.py",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
    "paper-trader/backend/research/domain/migrations",
    "paper-trader/backend/scripts/run_disposable_postgres.py",
    "paper-trader/backend/app",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
    ".agent/review-package.json"
  ],
  "tests": [
    "Verify trigger-evidence, upstream architecture, failed owned-byte, protected-file, CURRENT, PROGRAMME, and active-capsule hashes before analysis and again against final bytes.",
    "Use ignored evidence-only prototypes to prove the proposed strict public wire boundary and private canonical-value encoder can round-trip the complete type registry and reject every negative family without importing or opening a database.",
    "Prove exact 24-DATA and 39-CAT enum identities, every closed dataclass field, every digest domain and order, declaration construction, expected-before-locator sequencing, and comparison mismatch identities by machine-readable validation.",
    "Mutate each contract family one at a time and prove the architecture validator rejects omission, dead identity, ambiguous encoding, weakened strictness, observed-source authority, and locator-first ordering.",
    "Run capsule JSON validation, repository architecture validation, scoped diff, git diff --check, frozen/protected hash checks, report/manifest attestation, and final same-byte seal validation."
  ],
  "test_plan": [
    "Use architecting-strategy-os-phases to freeze one authority and encoding model, executing-strategy-os-slices to keep the recovery and successor bounded, and auditing-strategy-os-deployability to preserve all migration and release nonclaims.",
    "Retain every failed diagnostic and validator as a classified false start; only final same-byte evidence may support the verdict.",
    "Reject a design that weakens public strict serialization, accepts arbitrary container roots, infers expected facts from observations, leaves placeholder identities, or relies on prose-only coverage.",
    "Keep every feasibility prototype and validator under the ignored recovery evidence path and leave all failed product and test bytes unchanged."
  ],
  "acceptance": [
    "The report states the complete failure lineage and rejects a tuple-only patch as insufficient unless every structural omission is also resolved.",
    "One exact public wire and private canonical-value contract covers every closed type and meaningful native scalar without arbitrary-container acceptance.",
    "Exact field schemas and identities cover all required core types, all 24 DATA identities, and all 39 CAT identities, with no placeholder values or open registries.",
    "Digest domains, preimages, framing, ordering, state-machine authority, declaration authority, comparison outputs, and negative mutations are executable specifications rather than prose choices.",
    "Every failed byte has an evidence-backed disposition and the fresh successor capsule has exact paths, tests, attempt limits, route, and root gate.",
    "Repository architecture, scope, hashes, and same-byte manifest validation pass without any product or test edit."
  ],
  "owner_gates": [
    "Stop if any trigger, frozen input, protected byte, CURRENT, PROGRAMME, or active capsule hash differs from root dispatch.",
    "Stop if exact type identities, native scalar encoding, digest preimages, declaration authority, comparison semantics, or expected-before-locator order would require invented facts or observed-state inference.",
    "Stop before product, test, schema, migration, runtime, dependency, configuration, service, provider, frontend, deployment, production, live, order, or money work.",
    "Return to root for same-byte acceptance. Architecture completion alone does not activate the successor."
  ],
  "stop_conditions": [
    "Any wire, type, identity, field, scalar, declaration, digest, ordering, state, comparison, mutation, or ownership choice remains implicit.",
    "Any proposed expected value depends on observed rows, catalog, types, keys, owners, sequences, current metadata, current-head rewind, cross-dialect translation, or later-head dumps.",
    "Any prototype changes the three failed implementation files or enters observer, obligation, mutation, runtime, integration, numeric, transitive, review, or deployment scope.",
    "Same-byte report, manifest, contracts, successor capsule, scope, architecture, and hash validation do not pass."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "assignment_id": "foundation_native_state_contract_core_recovery_architect"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_native_state_contract_core_recovery_architect",
    "base_sha": "HEAD",
    "review_paths": [
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-contract-core-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-contract-core.md",
      ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery"
    ],
    "exclude_paths": [
      "paper-trader/backend/tests",
      "paper-trader/backend/research",
      "paper-trader/backend/app",
      "paper-trader/frontend",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
      ".agent/review-package.json"
    ],
    "verdicts": [
      "RECOVERY_ARCHITECTURE_ACCEPTABLE",
      "BLOCKED"
    ]
  },
  "deployment_impact": {
    "classification": "architecture-only; test-contract implementation required downstream",
    "highest_claim": "locally validated contract-core recovery architecture",
    "deployable": false,
    "unchanged": [
      "product runtime",
      "schema",
      "migrations",
      "configuration",
      "dependencies",
      "services",
      "providers",
      "frontend",
      "infrastructure"
    ],
    "downstream": "fresh contract-core implementation, observer, 24-DATA/39-CAT obligation evidence, mutation attestation, runtime migration correction, integrated evidence, numeric correction, transitive revalidation, and critical review remain blocked"
  },
  "nonclaims": [
    "No failed implementation byte is accepted or repaired by this capsule.",
    "No observer, database behavior, migration, runtime, fixture, integration, numeric, transitive, review, foundation, Phase 5, Phase 6, deployability, release, production, live, order, or money claim follows from architecture evidence."
  ]
}
---

# Native-state contract-core recovery

This capsule resolves the contract-shaping failure before another implementation attempt. It produces executable architecture and one fresh successor capsule, while the failed three-file implementation and every downstream slice remain frozen and unaccepted.
