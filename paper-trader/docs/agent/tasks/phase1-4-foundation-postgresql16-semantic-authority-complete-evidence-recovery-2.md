---
{
  "id": "phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2",
  "phase": "interphase-4-5",
  "status": "blocked",
  "goal": "Produce one complete independently validated PostgreSQL 16 semantic-authority package from two disposable isolated runs under separately root-accepted fixture and package contracts.",
  "goal_contract": {
    "create_before_work": true,
    "durable_goal_count": 1,
    "stopping_condition": "Stop first with a complete database-free pre-invocation package whose exact bytes pass the independent consumer. Root must accept those exact bytes and separately authorize one literal command argv, environment-key set, disposable targets, ports, and timeout before execution. Complete only after two independent run receipts, lifecycle seals, cleanup proof, semantic package, report, manifest, scope, and final same-byte hashes pass; otherwise return BLOCKED."
  },
  "dependency_gate": "BLOCKED_UNTIL_ROOT_ACCEPTS_THE_EXACT_COMPLETED_SEMANTIC_PACKAGE_CONTRACT_REPORT_MANIFEST_OUTPUTS_AND_CAPSULE_HASH",
  "dispatch_contract": "Root dispatch binds this capsule SHA-256, accepted recovery, trigger-fixture, and semantic-package report/manifest/output hashes, all three predecessor acceptance artifact hashes, HEAD, CURRENT, PROGRAMME, frozen source, accepted cleanup and protected hashes.",
  "root_owned_gates": {
    "pre_invocation_acceptance": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-pre-invocation-acceptance.json",
    "postgresql_invocation_authorization": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-invocation-authorization.json",
    "final_semantic_acceptance": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-final-semantic-acceptance.json"
  },
  "root_gate_activation_inputs": [
    {"gate": "pre_invocation_acceptance", "path": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-pre-invocation-acceptance.json", "hash_authority": "exact SHA-256 supplied by root after the owner returns the complete database-free package", "access": "read-only"},
    {"gate": "postgresql_invocation_authorization", "path": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-invocation-authorization.json", "hash_authority": "exact SHA-256 supplied by root in a separate post-return dispatch", "access": "read-only"},
    {"gate": "final_semantic_acceptance", "path": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-final-semantic-acceptance.json", "hash_authority": "exact SHA-256 supplied only by root after the owner returns final same-byte outputs", "access": "read-only downstream gate"}
  ],
  "required_docs": [],
  "risk_tags": ["critical", "postgresql", "catalog-semantics", "lifecycle-evidence", "research-integrity", "false-green-evidence"],
  "allowed_paths": [
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2"
  ],
  "read_only_paths": [
    "paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent", ".agent/review-package.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-fixture-consumer-repeated-failure-recovery",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-package-contract",
    ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-pre-invocation-acceptance.json",
    ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-invocation-authorization.json",
    ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-complete-evidence-final-semantic-acceptance.json"
  ],
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/pre-invocation-package.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/pre-invocation-validation.log",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/run-one-receipt.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/run-two-receipt.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/postgresql16-independent-semantic-authority-package.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/full-run.log",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/report.md",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2/evidence-manifest.json"
  ],
  "execution_boundary": {
    "initial_attempts": 1,
    "bounded_repairs": 1,
    "repair_rule": "At most one repair may address the same material defect in the same bytes. A repeated or different material defect returns BLOCKED to root.",
    "parallel_budget": 0,
    "children": 0,
    "database_free_first_stop": true,
    "postgresql_authorization": "After independent pre-invocation validation, the owner must stop and return. Root writes the acceptance and, in a separate root-owned record, authorizes one exact literal argv, exact environment key names, exact fresh disposable cluster/database/schema/role target paths and identifiers, two ports, and one timeout. A later dispatch supplies both exact hashes read-only. Wildcards, shell expansion, inherited locators, implicit commands, and additional invocations are forbidden.",
    "mandatory_return_boundaries": [
      "Return after pre-invocation package and validation bytes are complete; do not continue in the same owner turn or write either root gate.",
      "Return after both runs and final package are sealed; root alone writes final_semantic_acceptance as a separate downstream gate."
    ]
  },
  "tests": [
    "Before PostgreSQL, verify every predecessor acceptance and byte, complete command/PQ/parser/provenance/mutation registries, two fresh target locators, accepted cleanup binding, independent consumer, scope, and pre-invocation manifest.",
    "Use two distinct disposable clusters, databases, schemas, role sets, connections, nonces and ports under the one separately authorized runner command.",
    "Execute every frozen semantic query and all sixteen immutable-trigger UPDATE/DELETE paths; a prerequisite, check, FK, unique, parse, parameter, or unrelated failure gets zero trigger credit.",
    "Authenticate observer and owner identities, prove target privilege facts and durable PRE, MUTATED, RESTORED lifecycle transitions, then seal Stage A before cleanup and Stage B after exact accepted cleanup.",
    "Require strict native PQ decoding, exact total parsing, complete isolated-schema inventory, no missing/extra/duplicate rows, and byte-identical stable projections after explicit identity-class projection.",
    "Independently consume both receipts and the real semantic package; only a separately hashed root-owned acceptance record after both runs may promote it.",
    "Run scope, git diff --check, frozen/protected hashes, manifest attestation, cleanup proof, and final same-byte validation."
  ],
  "test_plan": [
    "First materialize and independently validate the complete database-free pre-invocation package, then return without opening PostgreSQL for root same-byte acceptance and separate exact-command authorization.",
    "Only after a later dispatch binds both root-owned gate hashes, run the one exact authorized disposable command to produce two distinct complete run receipts, lifecycle/cleanup evidence, and the typed real semantic package.",
    "Independently consume and seal the final report and manifest after scope, repository architecture, frozen/protected hash, cleanup, and same-byte checks, then return for the separate root-owned final semantic acceptance gate."
  ],
  "acceptance": [
    "The root-accepted pre-invocation package and separately authorized single command match exact executed bytes and targets.",
    "Both isolated runs cover every registry element and all sixteen trigger behaviors with exact setup, refusal, equality, state, and cleanup receipts.",
    "The real package carries two independently authenticated run digests and a separately hashed root-owned acceptance record; protocol fixtures are structurally ineligible.",
    "Root accepts the completed report, manifest, outputs, logs, receipts, cleanup evidence, hashes, and capsule bytes before any downstream contract-core route resumes."
  ],
  "owner_gates": [
    "Stop on any predecessor, source, cleanup, protected, CURRENT, PROGRAMME, HEAD, dispatch, or acceptance hash mismatch.",
    "Stop after database-free validation for root same-byte acceptance and separate exact-command authorization.",
    "Stop if either disposable target is not fresh and distinct, if any semantic expectation is defined by its observation, or if cleanup cannot use exact accepted bytes.",
    "Return to root for final exact same-byte acceptance; do not activate contract-core recovery."
  ],
  "stop_conditions": [
    "Any command runs before both root gates, differs from the authorized literal command, or reaches a non-disposable target.",
    "Any product, test, migration, runtime, dependency, provider, frontend, deployment, production, live, order, or money action is proposed.",
    "Any selected-test, synthetic protocol package, prior pass count, self-asserted acceptance, first-run promotion, same-target comparison, incomplete mutation registry, or partial parser receives semantic credit.",
    "A second material repair would be needed."
  ],
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "assignment_id": "foundation_postgresql16_semantic_authority_complete_evidence_recovery_2_owner"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_postgresql16_semantic_authority_complete_evidence_recovery_2_owner",
    "base_sha": "HEAD",
    "review_paths": [".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-complete-evidence-recovery-2"],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent", ".agent/review-package.json"],
    "verdicts": ["POSTGRESQL16_SEMANTIC_AUTHORITY_EVIDENCE_ACCEPTABLE", "BLOCKED"]
  },
  "deployment_impact": {
    "classification": "evidence-only disposable PostgreSQL validation; no repository runtime or migration change", "highest_claim": "root-accepted isolated semantic evidence", "deployable": false,
    "unchanged": ["product", "tests", "migrations", "runtime", "configuration", "dependencies", "services", "providers", "frontend", "infrastructure"]
  },
  "nonclaims": [
    "No DATA/CAT native-state obligation, runtime migration behavior, foundation acceptance, deployability, release, production, live, order, or money claim follows.",
    "Accepted cleanup bytes remain cleanup-mechanics evidence only and cannot define semantic facts.",
    "This capsule cannot activate downstream work or authorize more than the separately root-approved single command."
  ]
}
---

# PostgreSQL 16 semantic-authority complete evidence recovery 2

This blocked third serial successor may prepare a database-free pre-invocation package only after root accepts both predecessors. PostgreSQL remains forbidden until root accepts that exact package and separately authorizes one exact disposable-run command.
