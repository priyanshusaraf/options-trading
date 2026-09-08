---
{
  "id": "phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery",
  "phase": "interphase-4-5",
  "status": "ready",
  "goal": "Recover the repeatedly failed PostgreSQL 16 semantic-authority cleanup boundary by freezing an exact fail-closed lifecycle authority, executable actual-collector branch evidence, and one fresh successor capsule without opening PostgreSQL or changing any failed evidence implementation.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "Root rejected superseding-15 before database execution after an independent actual-collector mock proved that pg_ctl status exit 1 was treated as absence, allowed directory deletion, and produced a false cleanup success. The same material observed-state cleanup defect survived superseding-14 and superseding-15, so the repository repeated-failure rule requires this fresh Sol-medium architecture recovery before any further implementation attempt.",
    "stopping_condition": "Complete only when the repeated-failure lineage, exact pg_ctl status and cleanup state machine, closed secret-redaction boundary, executable database-free actual-collector branch harness, failed-byte dispositions, serial recovery DAG, fresh successor capsule, report, manifest, scope checks, repository architecture validation, and same-byte hash validation all pass; otherwise return BLOCKED with the exact unresolved authority or ownership gate."
  },
  "risk_tags": [
    "critical",
    "architecture-recovery",
    "repeated-failure",
    "migration-evidence",
    "postgresql",
    "lifecycle-cleanup",
    "secret-containment"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-recovery.md",
      "sections": [
        "PostgreSQL 16 semantic authority recovery"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Foundation migration and numeric correction",
        "Foundation blockers"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "Status and evidence rules",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"
      ]
    }
  ],
  "dependency_gate": "postgresql16-semantic-authority-superseding-15-rejected-after-same-material-cleanup-defect-survived-two-bounded-repairs",
  "trigger_evidence": {
    "root_superseding_14_rejection": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-superseding-14-predb-rejection.json",
    "root_superseding_14_rejection_sha256": "36ea6b8b6d7549bf253c54dea446fde1bec7f38742cd9235aeeda987d2879040",
    "root_superseding_15_rejection": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-superseding-15-predb-rejection.json",
    "root_superseding_15_rejection_sha256": "a454a7aca39044246992802cd48cbe747fb9448bb8902d1155da3b425d18b53b",
    "root_superseding_15_actual_branch_audit": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-superseding-15-predb-independent-audit-rerun-2.log",
    "root_superseding_15_actual_branch_audit_sha256": "4d406f9cb6fad60f7fc0262553dc0540765b381a8bb17041105f849cc3418b2f",
    "root_superseding_15_rejection_seal": ".agent/runs/phase1-4-foundation-critical-closure/root/postgresql16-superseding-15-rejection-seal.log",
    "root_superseding_15_rejection_seal_sha256": "ce2ea904f48a02abfeb12a0fa42d77d7eb84ca3db52460cefe84dfa107245abe",
    "root_actual_branch_validator": ".agent/runs/phase1-4-foundation-critical-closure/root/validate_postgresql16_semantic_authority_predb_superseding_15.py",
    "root_actual_branch_validator_sha256": "3713da4b6e4d659dc49412afe718299c98227eaafed9d022b7d220538fcb5289",
    "blocked_owner_report": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/blocked-stopping-condition-report.json",
    "blocked_owner_report_sha256": "99cd4d8fe0893029dae1dbb943199189a52b573d16b957abf5c3be11113d7610",
    "blocked_owner_manifest": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/blocked-evidence-manifest.json",
    "blocked_owner_manifest_sha256": "682104f77cd104c4119b9db53225102b03168aa3bfa3b5fa9b3fc300105ae6a3"
  },
  "frozen_failed_inputs": {
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/collect_reference.py": "e41b6d5f4d318058a1650b0a6419a6256a9beca3a5b6f4fe41cdb101624ea9d5",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/receipt-wire-and-canonicalization-contract.json": "68c55ac8c80d42caaea4d89c41244240386533ac4be1f57700b2b71c49b9300f",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/collector-wrapper-attestation.json": "3f7ff795a56d365bbc1d0b70608edf660b35e5ea874c10e8160335e1b262c846",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/validate_static_contracts.py": "e9e962b9e0bd2416ee3937d1643d161a14d53d164d667b2d0079fbcdf48a757d",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/validate_final.py": "6abc59aaa0667fc2a3d84346edb8ac7286a6c1167ff6cea11bb45a0349ce695f",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/false-start-classification.json": "e710dbc42f03e74cfd79711c4943d047e88d257a7464e67aba8c540e152f56c9"
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  },
  "known_findings": [
    "Superseding-14 could raise during redaction before proving that a started or partially started server was stopped and absent; root rejected it before database execution.",
    "Superseding-15 moved redaction after cleanup and status-observed every start attempt, but its actual collector branch treated every nonzero pg_ctl status as absence.",
    "PostgreSQL pg_ctl status has a closed semantic boundary for this recovery: exit 0 means running, exit 3 means not running, and every other exit is an observation failure that cannot authorize cleanup success or data-directory deletion.",
    "The root database-free actual-collector harness proves exit 1 after stop and exit 1 before and after the stop decision both produce false cleanup success and delete the directory. The same harness distinguishes exit 0 as live and exit 3 as absent.",
    "The owner static validator and decisive mutation registry were self-consistent with the faulty nonzero-is-absence model, so modeled fixture coverage cannot replace executable evidence through the actual collector cleanup branch.",
    "No PostgreSQL run, semantic receipt, migration contract, native-state contract, deployability, release, production, live, order, or money claim is accepted."
  ],
  "required_decisions": {
    "failure_lineage": "Bind superseding-14 and superseding-15 as two bounded repair attempts at the same observed-state cleanup boundary. Classify every older receipt and package as ineligible and prohibit a third patch of the failed owner bytes.",
    "status_authority": "Freeze the exact pg_ctl status command, executable identity, cluster locator, timeout, stdout/stderr capture, and return-code algebra. Exit 0 is RUNNING, exit 3 is ABSENT, and every other return, signal, timeout, launch failure, malformed receipt, locator mismatch, or identity mismatch is OBSERVATION_FAILED and fails closed.",
    "cleanup_state_machine": "Define exact transitions from no start attempt, start attempted, status observed, emergency stop attempted, post-stop status observed, secrets scanned, evidence persisted or refused, and directory retained or removed. Directory deletion requires an independently recorded exact ABSENT observation after every start attempt. A failed observation must retain the directory and produce no cleanup-success claim.",
    "fallback_authority": "Prefer no fallback. If a fallback is proposed, specify an exact independent process, PID, executable, port/listener, data-directory, cluster, postmaster, and namespace identity proof; prove why it cannot confuse an unrelated server, stale PID, missing path, permission error, or command failure with absence.",
    "redaction_boundary": "Keep the complete two-secret raw and lowercase-hex scan over all persisted receipts, in-memory transcripts, emergency commands, status observations, server logs, event/state inputs, exception text, stdout, and stderr. Cleanup must finish or fail closed before any unredacted rejection can escape, while secret detection itself can never authorize deletion.",
    "actual_branch_harness": "Build a database-free executable harness that imports and drives the proposed successor collector cleanup branch rather than a copied model. It must prove 0, 3, 1, signals, timeouts, launch errors, live-after-stop, absent-after-stop, unrelated-listener, stale-PID, secret-in-each-input-family, and cleanup-order cases with exact filesystem and transcript outcomes.",
    "negative_registry": "Freeze one-to-one mutation identities for every return-code class, command/locator/identity field, state transition, stop decision, post-stop observation, deletion authorization, secret source, transcript, persistence edge, and claim field. Modeled fixtures receive no credit unless the actual-branch harness consumes the same frozen registry.",
    "byte_disposition": "Return KEEP_UNACCEPTED_FOR_ARCHITECTURE_INPUT, REPLACE_IN_SUCCESSOR, or REMOVE_IN_SUCCESSOR for every S15 collector, contract, attestation, validator, and false-start byte. Preserve useful semantic-query work without accepting faulty lifecycle authority.",
    "successor": "Emit one exact fresh Sol-medium implementation/evidence successor capsule with a fresh assignment, bounded write scope under a new ignored run path, one durable goal, zero children, initial patch plus at most one repair, no product/test/runtime change, pre-database root audit, and explicit root authorization before each PostgreSQL run.",
    "serial_dag": "Keep PostgreSQL authority evidence, contract-core recovery, native-state contract core, observers, 24-DATA/39-CAT obligations, mutation attestation, runtime migration correction, integrated evidence, numeric correction, transitive revalidation, and one critical review serial and blocked behind root acceptance."
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/failure-lineage.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/status-authority-contract.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/cleanup-state-machine.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/redaction-and-persistence-contract.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/actual-branch-negative-matrix.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/byte-disposition.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/capsule-dag.json",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery.md"
  ],
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery.md",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery",
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-recovery.md",
    ".agent/review-package.json"
  ],
  "tests": [
    "Verify trigger evidence, failed-byte, protected-file, CURRENT, PROGRAMME, active-capsule, and dispatch hashes before analysis and against final same bytes.",
    "Use only database-free ignored prototypes. Do not invoke PostgreSQL, pg_ctl, initdb, createdb, dropdb, psql, the disposable PostgreSQL harness, or the failed collector.",
    "Execute the proposed successor cleanup branch in a separate database-free harness with controlled command receipts and filesystem roots. Prove exact 0/RUNNING, 3/ABSENT, every-other/OBSERVATION_FAILED behavior and directory-retention semantics.",
    "Prove exact cleanup-before-rejection and complete two-secret raw/hex containment without printing or persisting either secret.",
    "Mutate every status, identity, locator, state-transition, stop, post-stop, deletion, secret-source, transcript, persistence, and claim binding one at a time; require the architecture validator and actual-branch harness to reject each mutation.",
    "Run capsule JSON validation, repository architecture validation, scoped diff, git diff --check, frozen/protected hash checks, report/manifest attestation, and final same-byte validation."
  ],
  "test_plan": [
    "Use architecting-strategy-os-phases to freeze the sole lifecycle authority, executing-strategy-os-slices to keep recovery and successor ownership bounded, and auditing-strategy-os-deployability to preserve every migration and release nonclaim.",
    "Retain all diagnostics and false starts. Only the final same-byte executable actual-branch evidence may support the verdict.",
    "Reject nonzero-is-absence, path-disappearance-as-absence, process-name-only checks, port-only checks, copied cleanup models, modeled-fixture-only claims, secret scanning that can prevent cleanup, or deletion after any ambiguous observation.",
    "Stop at root same-byte acceptance. Do not activate the successor, open PostgreSQL, or amend the failed S15 package."
  ],
  "acceptance": [
    "The failure lineage proves the same material cleanup defect survived S14 and S15 and bars a third local patch or reuse of any earlier receipt as acceptance evidence.",
    "The status authority makes only return 0 RUNNING and return 3 ABSENT; all other outcomes fail closed without cleanup success or directory deletion.",
    "The cleanup state machine, command identity, cluster identity, post-stop observation, redaction, persistence, and deletion authorities are exact machine contracts with no prose-only branch.",
    "A database-free harness executes the proposed successor's actual cleanup branch and rejects every frozen negative case, including exit 1 before and after stop, while proving resource and evidence outcomes.",
    "Every S15 byte has an evidence-backed disposition; one fresh successor capsule has exact paths, owner, attempt limit, root gates, tests, and nonclaims; the serial DAG remains closed.",
    "Repository architecture, scope, hashes, report/manifest attestation, and final same-byte validation pass without touching PostgreSQL, product, tests, migrations, runtime, CURRENT, PROGRAMME, or the failed S15 bytes."
  ],
  "owner_gates": [
    "Stop if any trigger, failed input, protected file, CURRENT, PROGRAMME, active capsule, or dispatch hash differs from root dispatch.",
    "Stop if the exact pg_ctl status algebra, cleanup observation boundary, cluster/process identity, redaction ordering, deletion authority, or actual-branch harness would require invented facts or observed target state as expected authority.",
    "Stop before opening PostgreSQL or invoking any database/server executable; this capsule is architecture and database-free evidence only.",
    "Stop before product, test, schema, migration, runtime, dependency, configuration, service, provider, frontend, deployment, production, live, order, or money work.",
    "Return to root for exact same-byte acceptance. Architecture completion does not activate the successor."
  ],
  "stop_conditions": [
    "Any status result other than exact 3 can authorize absence, cleanup success, or directory deletion.",
    "Any failed, signaled, timed-out, malformed, mismatched, or ambiguous status observation is normalized to absence.",
    "The proposed branch can print or persist a secret before cleanup and complete containment, or secret detection can prevent an emergency stop and absence observation.",
    "The decisive harness copies a modeled state machine instead of executing the proposed successor cleanup branch.",
    "Any third patch of S15, PostgreSQL execution, product/test/runtime edit, implicit authority choice, stale receipt acceptance, or unbounded successor route occurs.",
    "Same-byte report, manifest, machine contracts, successor capsule, scope, architecture, and hash validation do not pass."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "assignment_id": "foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect",
    "base_sha": "HEAD",
    "review_paths": [
      "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery.md",
      ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery"
    ],
    "exclude_paths": [
      ".agent/runs/phase1-4-foundation-critical-closure",
      ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery",
      "paper-trader/backend",
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
    "classification": "architecture-only; migration evidence correction required downstream",
    "highest_claim": "locally validated database-free cleanup recovery architecture",
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
    "downstream": "fresh semantic-authority evidence implementation, contract-core recovery, native-state implementation, observer, obligations, mutation attestation, runtime correction, integration evidence, numeric correction, transitive revalidation, and critical review remain blocked"
  },
  "nonclaims": [
    "No S14 or S15 byte, PostgreSQL run, receipt, semantic fact, migration behavior, native-state contract, foundation acceptance, Phase 5, Phase 6, deployability, release, production, live, order, or money claim is accepted.",
    "Database-free cleanup feasibility does not prove PostgreSQL lifecycle behavior, semantic catalog authority, reproducibility, or deployability.",
    "This capsule cannot activate its successor or authorize any PostgreSQL execution."
  ]
}
---

# PostgreSQL 16 cleanup repeated-failure recovery

This capsule resolves the lifecycle-authority defect that survived two bounded repairs. It freezes the only acceptable status and cleanup semantics, proves the proposed successor branch without opening PostgreSQL, and routes one fresh implementation owner only after root same-byte acceptance.
