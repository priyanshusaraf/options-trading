---
{
  "id": "phase5-capital-assurance-replan",
  "phase": "phase5",
  "status": "accepted",
  "kind": "critical_architecture",
  "goal": "Replace the exhausted capital-assurance correction/recheck route with one machine-native, owner-authorized serial recovery lineage that closes only P5-CAP-004 and P5-CAP-R001, preserves every prior verdict byte, and keeps all runtime, order, live, deployment and Phase 6 boundaries closed.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "AUTHORIZE BOUNDED PHASE-5 CAPITAL ASSURANCE REPLAN received on 2026-08-26.",
    "stopping_condition": "Complete only after the immutable failed lineage, exact two-defect boundary, product/test byte freeze, disjoint serial path ownership, evidence obligations, deployment classification and fresh independent-review route are machine-readable; architecture and programme validators pass from unchanged product/test bytes; and the decision is recorded as KEEP + HARDEN."
  },
  "risk_tags": [
    "critical",
    "money",
    "authority",
    "numeric",
    "recovery",
    "false-green",
    "architecture-only"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md",
      "sections": [
        "Invariants",
        "Complete failure and test matrix",
        "Deployment impact",
        "Owner gates and nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase5-capital-admission.md",
      "sections": [
        "Dependency order",
        "Slice 5: capital assurance and critical review"
      ]
    },
    {
      "path": ".agent/runs/phase5-capital-admission-assurance/owner-replan-proposal.md",
      "sections": [
        "Remaining exact defects",
        "Recommended fresh lineage",
        "Evidence invalidated by the recheck",
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
  "input_evidence": [
    ".agent/runs/phase5-capital-admission-assurance/review/verdict.json",
    ".agent/runs/phase5-capital-admission-assurance/review/recheck-verdict.json",
    ".agent/runs/phase5-capital-admission-assurance/owner-replan-proposal.md",
    ".agent/runs/phase5-capital-admission-critical-correction/report.md",
    ".agent/review-package.json"
  ],
  "dependency_gate": "phase5-capital-admission-critical-correction",
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/phase5-capital-assurance-replan.md",
    "paper-trader/docs/agent/tasks/phase5-capital-assurance-recovery-correction.md",
    "paper-trader/docs/agent/tasks/phase5-capital-assurance-final-review.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".codex/tests/test_programme_orchestration.py",
    ".agent/runs/phase5-capital-assurance-replan"
  ],
  "product_test_paths_read_only": [
    "paper-trader/backend/app/execution/leases.py",
    "paper-trader/backend/app/execution/capital_recovery.py",
    "paper-trader/backend/tests/test_capital_admission.py",
    "paper-trader/backend/tests/test_capital_admission_recovery.py",
    "paper-trader/backend/tests/test_capital_admission_postgresql.py"
  ],
  "successor_path_ownership": {
    "phase5-capital-assurance-recovery-correction": {
      "mode": "serial-write",
      "owner": "root owner; no children",
      "product_paths": [
        "paper-trader/backend/app/execution/leases.py",
        "paper-trader/backend/app/execution/capital_recovery.py"
      ],
      "test_paths": [
        "paper-trader/backend/tests/test_capital_admission.py",
        "paper-trader/backend/tests/test_capital_admission_recovery.py",
        "paper-trader/backend/tests/test_capital_admission_postgresql.py"
      ],
      "finding_mutation_namespace": ".agent/runs/phase5-capital-assurance-recovery-correction",
      "finding_ids": [
        "P5-CAP-004",
        "P5-CAP-R001"
      ]
    },
    "phase5-capital-assurance-final-review": {
      "mode": "read-only-independent-review",
      "owner": "one critical-reviewer after final bytes and package exist",
      "write_paths": [
        ".agent/runs/phase5-capital-assurance-final-review/review/verdict.json"
      ]
    }
  },
  "nonclaims": [
    "No schema, migration, runtime wiring, allocator or Position behavior switch, provider/broker networking, order submission, live/customer-money authority, frontend, deployment, production state or Phase 6 work.",
    "The failed first review and failed focused recheck remain immutable and non-executable. This lineage is a new owner-authorized assurance route, not a second focused recheck.",
    "Architecture acceptance does not accept either defect, the capital subsystem, Phase 5 or deployability."
  ],
  "owner_gates": [
    "Stop if either correction needs a third product file, schema/migration change, runtime caller, broker behavior, authoritative behavior switch, deployment, production access or Phase 6 work.",
    "Stop if the fresh review finds a wider money, migration or authority defect; do not open another correction without a new owner replan."
  ],
  "stop_conditions": [
    "Either immutable FAIL verdict or the exhausted package changes.",
    "Product or test bytes drift during this read-only architecture capsule.",
    "Correction and review write ownership overlaps or any successor is parallelized.",
    "The programme can dispatch the exhausted assurance stage or skip the fresh dual-verdict review."
  ],
  "deployment_impact": {
    "classification": "compatible validation hardening inside a migration-required capital subsystem",
    "affected_dimensions": [
      "Application numeric validation",
      "Reservation command authority",
      "Capital recovery validation",
      "Phase 5 release evidence"
    ],
    "highest_claim": "locally_runnable paper/mock mechanics only",
    "unchanged_dimensions": [
      "schema",
      "migration heads",
      "configuration",
      "dependencies",
      "services",
      "providers",
      "runtime wiring"
    ],
    "future_owner": "phase5-capital-assurance-final-review must verify the compatible correction and inherited migration evidence; Phase 6/V1 retain production-shaped install, topology, backup/restore, capacity, rollout and deployment."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high",
    "review_escalation_reason": "A fresh read-only Sol-high reviewer is required because the corrected predicates authorize reservation-bound commands and mutate money-recovery facts after the prior review lineage exhausted its budget.",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "decision": "KEEP + HARDEN",
  "acceptance": [
    "The old assurance stage is retained as immutable blocked history with both FAIL verdict digests and exhausted disposition unchanged.",
    "One serial correction owns only two product files, three direct SQLite/PostgreSQL test files and its finding-mutation namespace.",
    "The correction requires exact positive int excluding bool for reserved requested_qty before authority or mutation, while all unreserved v1 call shapes remain unchanged.",
    "Recovery requires non-negative exact int32 head revision and quantity plus non-negative exact int64 consumed money before evidence addressing, session binding or locking; every invalid form has zero reservation/event/head/outbox effect.",
    "Fresh local, PostgreSQL 16, identical broad compatibility, mutation, inventory, deployability and package evidence precede one new independent critical review with no recheck budget.",
    "Only fresh SPEC PASS and QUALITY PASS can resume phase5-implementation."
  ],
  "test_plan": [
    "Freeze and recheck the two immutable verdicts, exhausted package, owner proposal and current product/test hashes.",
    "Validate capsule schema, exact serial programme dependencies, dispatcher behavior, protected hashes and product/test no-drift.",
    "After architecture acceptance only, reproduce both counterexamples, add direct SQLite/PostgreSQL invalid-form and no-effect regressions, kill and exactly restore finding mutations, then replay the identical prior broad selection.",
    "Build a fresh current-byte package and route one read-only critical reviewer distinct from the exhausted recheck."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase5_capital_assurance_replan_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/agent/tasks/phase5-capital-assurance-replan.md",
      "paper-trader/docs/agent/tasks/phase5-capital-assurance-recovery-correction.md",
      "paper-trader/docs/agent/tasks/phase5-capital-assurance-final-review.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      ".codex/tests/test_programme_orchestration.py"
    ],
    "exclude_paths": [
      "paper-trader/backend/app",
      "paper-trader/backend/tests",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase5-capital-assurance-replan/report.md",
    "verdicts": [
      "ARCHITECTURE"
    ]
  },
  "immutable_failed_lineage": {
    "first_verdict": ".agent/runs/phase5-capital-admission-assurance/review/verdict.json",
    "first_verdict_sha256": "89d05b05650b9775966d4ae263d833794f56f8f17690e9a390502191db9512b8",
    "recheck_verdict": ".agent/runs/phase5-capital-admission-assurance/review/recheck-verdict.json",
    "recheck_verdict_sha256": "78e81a79606b6e70c2ed4d152a5edfab54a56dde30eee03a325cc8bf7762f8a9",
    "exhausted_package_sha256": "c18e21f50645efa9e34104007b432778597f6e556c843c4bbfcba4da290f7bd6",
    "owner_proposal_sha256": "6c43d1e4855454d5b52fac9973de9bb5fd6298d084f6da8898f03a19f97fe51f",
    "disposition": "IMMUTABLE_FAIL_HISTORY"
  },
  "product_test_freeze": {
    "paper-trader/backend/app/execution/leases.py": "1e2eb76c000761fc102bcabcd56af355491d10711e72875bb3170931afcffe61",
    "paper-trader/backend/app/execution/capital_recovery.py": "91e41a3a1a2bc7e3415ec7ac43ff03c325028ad5f54379e58f24d0d20d477956",
    "paper-trader/backend/tests/test_capital_admission.py": "9470bafdbedebfc67c23a551a164d915871d04e64a888a4f19d0017fce940b7e",
    "paper-trader/backend/tests/test_capital_admission_recovery.py": "a9841b02ce39d63ff6f349f0300d4c5f0f09056f569eb04f95a622776724f185",
    "paper-trader/backend/tests/test_capital_admission_postgresql.py": "a8a81c19ac36a5671f3519091bb43b335f82d858e29774ee9c5facb247ce7515"
  },
  "acceptance_record": {
    "decision": "KEEP + HARDEN",
    "verdict": "ARCHITECTURE PASS",
    "report": ".agent/runs/phase5-capital-assurance-replan/report.md",
    "report_sha256": "0e697ddd5a42228897e6c4b1feb2097da7880cc7d2dca67b7c7ee5a45ba7e42d",
    "architecture_validation": ".agent/runs/phase5-capital-assurance-replan/owner/architecture-final.log",
    "architecture_validation_sha256": "b63ef3a06b70dc16be00024d76cd986e45770b36c52683608cb81bf1d7671dd8",
    "programme_validation": ".agent/runs/phase5-capital-assurance-replan/owner/programme-final.log",
    "programme_validation_sha256": "5ecef9e5dad3a53f3c8899f5ed95bf775f041a13d8f2bcc6ea25e016db0ba048",
    "product_test_drift": 0
  }
}
---

# Phase 5 capital-assurance replan

This read-only capsule replaces the exhausted assurance route with one bounded
serial correction and one fresh independent review. The architecture decision is
`KEEP + HARDEN`. Product and test bytes remain frozen until this capsule is
accepted by the root from machine-native validation evidence.
