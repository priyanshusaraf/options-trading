---
{
  "id": "phase5-capital-assurance-recovery-correction",
  "phase": "phase5",
  "status": "paused_owner_gate",
  "kind": "correction",
  "goal": "Close only P5-CAP-004 and P5-CAP-R001 with exact pre-authority integer validation, direct SQLite/PostgreSQL zero-effect regressions and non-vacuous restored mutations, without changing any runtime caller, schema or wider capital behavior.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "AUTHORIZE BOUNDED PHASE-5 CAPITAL ASSURANCE REPLAN received on 2026-08-26; execution remains blocked until phase5-capital-assurance-replan is accepted.",
    "stopping_condition": "Complete only after both original counterexamples reproduce on frozen bytes; exact bounded-int guards close them before authority, evidence addressing or locks; direct SQLite and PostgreSQL invalid-form/no-effect tests pass; unreserved v1 behavior remains unchanged; three finding-owned mutations fail and restore exact bytes; fresh focused, identical broad, inventory and deployability evidence passes; and exact final bytes are frozen for phase5-capital-assurance-final-review."
  },
  "risk_tags": [
    "critical",
    "money",
    "authority",
    "numeric",
    "recovery",
    "postgresql",
    "correction"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/phase5-capital-admission-assurance/review/recheck-verdict.json",
      "sections": [
        "finding_closure.P5-CAP-004",
        "new_findings.P5-CAP-R001",
        "evidence_gaps",
        "owner_gates"
      ]
    },
    {
      "path": ".agent/runs/phase5-capital-admission-assurance/owner-replan-proposal.md",
      "sections": [
        "Remaining exact defects",
        "Recommended fresh lineage",
        "Nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-026 — Capital safety proved against sampled identities and isolated transitions"
      ]
    }
  ],
  "dependency_gate": "phase5-capital-assurance-replan",
  "allowed_paths": [
    "paper-trader/backend/app/execution/leases.py",
    "paper-trader/backend/app/execution/capital_recovery.py",
    "paper-trader/backend/tests/test_capital_admission.py",
    "paper-trader/backend/tests/test_capital_admission_recovery.py",
    "paper-trader/backend/tests/test_capital_admission_postgresql.py",
    ".agent/runs/phase5-capital-assurance-recovery-correction",
    "paper-trader/docs/agent/tasks/phase5-capital-assurance-recovery-correction.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".codex/tests/test_programme_orchestration.py"
  ],
  "exact_write_ownership": {
    "owner": "root owner; serial; no children",
    "product": [
      "paper-trader/backend/app/execution/leases.py",
      "paper-trader/backend/app/execution/capital_recovery.py"
    ],
    "sqlite_tests": [
      "paper-trader/backend/tests/test_capital_admission.py",
      "paper-trader/backend/tests/test_capital_admission_recovery.py"
    ],
    "postgresql_tests": [
      "paper-trader/backend/tests/test_capital_admission_postgresql.py",
      "paper-trader/backend/tests/test_capital_admission_recovery.py"
    ],
    "mutations_and_evidence": [
      ".agent/runs/phase5-capital-assurance-recovery-correction"
    ],
    "root_transition_paths": [
      "paper-trader/docs/agent/tasks/phase5-capital-assurance-recovery-correction.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      ".codex/tests/test_programme_orchestration.py"
    ]
  },
  "nonclaims": [
    "No schema, migration, runtime wiring, allocator or Position behavior switch, provider/broker networking, order submission, live/customer-money authority, frontend, deployment, production state or Phase 6 work.",
    "Correction PASS prepares evidence only. It cannot accept capital assurance, Phase 5 or deployability.",
    "No prior FAIL verdict, exhausted package or prior correction report is rewritten or reclassified."
  ],
  "owner_gates": [
    "Stop before a third product file, schema/migration edit, runtime caller, external broker behavior, order path, authoritative paper/live switch, credentials, deployment, production state or Phase 6 work.",
    "Stop if either defect cannot close without changing unreserved v1 behavior or if any wider invariant fails."
  ],
  "stop_conditions": [
    "A changed path is outside exact_write_ownership or a protected hash drifts.",
    "Invalid numeric input reaches lease authority, evidence addressing, database locking or any reservation/event/head/outbox mutation.",
    "An invalid form or deliberate guard mutation remains green, PostgreSQL evidence is absent, the identical broad selection is red, or final hashes do not restore.",
    "Runtime reachability, schema identity, migration head, provider/broker network behavior or Phase 6 scope changes."
  ],
  "deployment_impact": {
    "classification": "compatible",
    "affected_dimensions": [
      "Application numeric validation",
      "Capital recovery behavior for invalid inputs",
      "Reservation-bound command validation"
    ],
    "unchanged_dimensions": [
      "Build dependencies",
      "Configuration",
      "PostgreSQL schema",
      "Migrations",
      "Services",
      "Providers",
      "Runtime wiring"
    ],
    "highest_claim": "locally_runnable paper/mock mechanics only",
    "required_evidence": "Unchanged execution/research migration heads; direct SQLite/PostgreSQL validation; identical inherited migration/restore and broad compatibility replay; protected boundaries and explicit production nonclaims.",
    "future_owner": "phase5-capital-assurance-final-review decides the exact correction; Phase 6/V1 retain production topology, rehearsal and deployment."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "findings": [
    "P5-CAP-004",
    "P5-CAP-R001"
  ],
  "acceptance": [
    "P5-CAP-004: reservation-bound prepare_command requires type(requested_qty) is int and requested_qty > 0 before lease authority or reservation lookup; 2.0 and bool refuse with zero command/reservation/event/head effect; the exact valid reserved call succeeds; unreserved v1 input behavior is unchanged.",
    "P5-CAP-R001: expected_head_revision and cumulative_filled_quantity are exact non-negative int32 and consumed_minor is exact non-negative int64, all excluding bool, before session binding, evidence addressing or locks.",
    "Float, bool, negative and above-bound forms for all three recovery fields refuse with one stable code and zero reservation/event/head/outbox effects on SQLite and PostgreSQL.",
    "One P5-CAP-004 type-guard mutation plus P5-CAP-R001 exact-type and upper-bound mutations are killed by their direct selectors and every changed byte is restored exactly.",
    "Fresh focused local and PostgreSQL 16 selectors, the identical prior broad compatibility command, current-byte inventory, unchanged migration heads and deployability audit pass from final bytes.",
    "The final correction manifest binds every command, evidence digest, current dirty fingerprint, changed path and protected hash for the fresh review."
  ],
  "test_plan": [
    "Reproduce reserved requested_qty=2.0 authorization and FILLED recovery with float-valued head/quantity/money on frozen bytes; record zero permanent drift.",
    "Add direct SQLite and PostgreSQL cases for exact valid values and every float, bool, negative and above-bound invalid form, including snapshots of reservation, event, head, command and outbox effects and a pre-bind/pre-lock sentinel.",
    "Run finding selectors, affected command/recovery files, prior 346-test local selection, identical broad compatibility selection and PostgreSQL 16 finding plus inherited migration/restore selection through run_logged.py.",
    "Run and audit three reversible mutations, inventory runtime/provider/broker callsites, query both migration heads, audit protected hashes and diff scope, then seal the correction report and final manifest."
  ],
  "review": {
    "required": true,
    "separate_stage": "phase5-capital-assurance-final-review",
    "assignment_id": "phase5_capital_assurance_recovery_correction_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/phase5-capital-assurance-final-review/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/execution/leases.py",
      "paper-trader/backend/app/execution/capital_recovery.py",
      "paper-trader/backend/tests/test_capital_admission.py",
      "paper-trader/backend/tests/test_capital_admission_recovery.py",
      "paper-trader/backend/tests/test_capital_admission_postgresql.py",
      ".agent/runs/phase5-capital-assurance-recovery-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/providers",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase5-capital-assurance-recovery-correction/report.md",
    "verdicts": [
      "CORRECTION"
    ],
    "max_rechecks": 0
  },
  "protected_files": {
    ".agent/runs/phase5-capital-admission-assurance/review/verdict.json": "89d05b05650b9775966d4ae263d833794f56f8f17690e9a390502191db9512b8",
    ".agent/runs/phase5-capital-admission-assurance/review/recheck-verdict.json": "78e81a79606b6e70c2ed4d152a5edfab54a56dde30eee03a325cc8bf7762f8a9",
    ".agent/review-package.json": "c18e21f50645efa9e34104007b432778597f6e556c843c4bbfcba4da290f7bd6",
    "paper-trader/backend/app/execution/capital_admission.py": "cdc9691cc99f2a3e22bf883ed60d11fa85bab540b073845c2890219a706c3a0b",
    "paper-trader/backend/app/execution/target_position.py": "b972ccdf8b2724c2b804f428fbc821378f6e0e3e1b650f4946d57bb054d28689",
    "paper-trader/backend/app/execution/position_lineage.py": "573cebf0838783ddf211d79bb12fc5aa40e7d13e6f1d2a4cc69b23e554ff36de",
    "paper-trader/backend/app/execution/capital_shadow.py": "f2c113a44be909eda683a0ec97bd59f9ae5090d1e8a3e9beab4a58e946567986",
    "paper-trader/backend/app/db/models.py": "8687bdcac880b326e6dfb6391d40257e0c36fc17430ee467548928798204582d",
    "paper-trader/backend/migrations/versions/20260825_0041_capital_admission.py": "a5c1fb060ed0f8021a16305a842cafebfceb019b0d424547ebd80517f33eb6a3",
    "paper-trader/backend/app/engine/runner.py": "1089b76480b2515efb52ce7ede07c09df2c0ca2cc9fa08edc8a57ef8f07d4cda",
    "paper-trader/backend/app/engine/live_broker.py": "d7ae71630442106ec2e2f4c1c04a09e939aea657ed8b60118d3f6177759f25ce",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38"
  },
  "initial_write_hashes": {
    "paper-trader/backend/app/execution/leases.py": "1e2eb76c000761fc102bcabcd56af355491d10711e72875bb3170931afcffe61",
    "paper-trader/backend/app/execution/capital_recovery.py": "91e41a3a1a2bc7e3415ec7ac43ff03c325028ad5f54379e58f24d0d20d477956",
    "paper-trader/backend/tests/test_capital_admission.py": "9470bafdbedebfc67c23a551a164d915871d04e64a888a4f19d0017fce940b7e",
    "paper-trader/backend/tests/test_capital_admission_recovery.py": "a9841b02ce39d63ff6f349f0300d4c5f0f09056f569eb04f95a622776724f185",
    "paper-trader/backend/tests/test_capital_admission_postgresql.py": "a8a81c19ac36a5671f3519091bb43b335f82d858e29774ee9c5facb247ce7515"
  },
  "blocked_record": {
    "verdict": "CORRECTION BLOCKED",
    "report": ".agent/runs/phase5-capital-assurance-recovery-correction/report.md",
    "report_sha256": "d8958fe7670a8445b2adf9578df01e3cde718e7950db17b33324a8336f7e6a19",
    "deployability": ".agent/runs/phase5-capital-assurance-recovery-correction/deployability.md",
    "deployability_sha256": "a336a4e263976416198ff0c90eec7f219872153a74e62db9645faa573c559e22",
    "finding_contracts": {
      "P5-CAP-004": "DIRECT SQLITE/POSTGRESQL/MUTATION PASS; NOT INDEPENDENTLY ACCEPTED",
      "P5-CAP-R001": "DIRECT SQLITE/POSTGRESQL/MUTATION PASS; NOT INDEPENDENTLY ACCEPTED"
    },
    "blocking_finding": {
      "id": "P5-CAP-R002",
      "severity": "HIGH",
      "verdicts": ["QUALITY"],
      "title": "An execution-control test leaks a mock-provider method into the broad process",
      "path": "paper-trader/backend/tests/test_execution_control.py",
      "evidence": [
        ".agent/runs/phase5-capital-assurance-recovery-correction/owner/broad-compatibility-final.log",
        ".agent/runs/phase5-capital-assurance-recovery-correction/owner/broad-compatibility-final-2.log",
        ".agent/runs/phase5-capital-assurance-recovery-correction/owner/broad-compatibility-final-3.log",
        ".agent/runs/phase5-capital-assurance-recovery-correction/owner/broad-failure-recheck.log",
        ".agent/runs/phase5-capital-assurance-recovery-correction/owner/isolation-exact-provider-leak.log",
        ".agent/runs/phase5-capital-assurance-recovery-correction/owner/isolation-provider-leak-cleanup-proof.log"
      ],
      "disposition": "STOP_FOR_OWNER_DIRECTION",
      "proposed_capsule": "phase5-capital-broad-compatibility-provider-leak-correction"
    },
    "fresh_package_created": false,
    "reviewer_routed": false
  }
}
---

# Phase 5 capital-assurance recovery correction

This is the sole serial correction in the owner-authorized fresh lineage. It owns
two validation seams and their direct evidence only. It cannot accept capital
assurance or change runtime authority.
