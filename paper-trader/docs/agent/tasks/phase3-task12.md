---
{
  "id": "phase3-task12",
  "phase": "phase3-causal-strategy-admission",
  "status": "ready",
  "goal": "Audit the inherited Phase 3 dirty tree, complete the bounded causal mutation gate and truthful operations evidence, and accept or reject Phase 3 against the governing contract.",
  "risk_tags": [
    "critical",
    "execution-authority",
    "research-integrity",
    "migrations",
    "dirty-tree-integration"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md",
      "sections": [
        "Task 12: Phase 3 mutation gate, operations record, and full closure",
        "Final rejection-before-acceptance review"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md",
      "sections": [
        "1. Outcome",
        "2. Scope",
        "3. Governing constraints",
        "12. Acceptance and mutation gates",
        "13. Completion evidence"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-v1-product-steer-design.md",
      "sections": [
        "2.4 Admission is necessary, never sufficient",
        "8. V1 nonclaims and deferrals",
        "9. Phase 3 reconciliation"
      ]
    },
    {
      "path": "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md",
      "sections": [
        "2.2 The authority gate",
        "5. Owner gates"
      ]
    },
    {
      "path": "paper-trader/docs/engineering/decisions/0013-research-approval-is-admission-not-a-lease.md",
      "sections": [
        "2. The decision",
        "5.2 Admission must bind the exact graph content",
        "5.4 The withdrawal invariant is strengthened, not weakened"
      ]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/scripts/phase3_causal_gate.py",
    "paper-trader/backend/tests/test_phase3_causal_gate.py",
    "paper-trader/docs/operations/strategy-admission.md",
    "paper-trader/docs/reports/2026-08-13-phase3-causal-strategy-contract.md",
    "paper-trader/docs/reports/phase3-causal-gate.json",
    "paper-trader/docs/ROADMAP.md",
    "paper-trader/docs/CONTINUE.md",
    ".agent/runs/phase3-task12",
    ".agent/review-package.json"
  ],
  "nonclaims": [
    "Phase 3 does not prove complete market-data truth, numeric-validity semantics, point-in-time rulebooks, provider capability, dynamic derivative selection, resource capacity, or Strategy Preflight.",
    "Phase 3 does not enable authoritative live IR or change live sizing, routing, risk, protection, or execution semantics.",
    "Phase 3 does not implement, adopt, or validate the future IR-v2 plan and specification.",
    "Local and PostgreSQL test evidence does not claim deployment or managed-production readiness."
  ],
  "owner_gates": [
    "Stop before enabling (ir_graph, live, authoritative).",
    "Stop before a material live sizing, routing, risk, protection, or execution-semantics change.",
    "Stop before accessing the live VPS, live credentials, or production data.",
    "Stop before destructive data or infrastructure work, licence-sensitive adoption, or frontend implementation."
  ],
  "stop_conditions": [
    "The current dirty tree differs from the preserved recovery manifest in a way not explained by Task 12 or this architecture migration.",
    "Any protected inherited file hash changes.",
    "A required causal mutation survives, a required suite is skipped or vacuous, or a required evidence command fails.",
    "The PostgreSQL environment needed by the contract is unavailable; report Phase 3 as incomplete instead of substituting SQLite evidence.",
    "Work requires an excluded future-phase document or a path outside allowed_paths.",
    "The critical reviewer rejects the integrated slice twice."
  ],
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default",
    "reviewer": "gpt-5.6-sol",
    "reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 3,
  "assignments": [
    {
      "id": "gate_closure",
      "agent": "terra-worker",
      "model": "gpt-5.6-terra",
      "reasoning_effort": "medium",
      "mode": "write",
      "depends_on": [],
      "read_paths": [
        "paper-trader/backend/scripts/phase3_causal_gate.py",
        "paper-trader/backend/tests/test_phase3_causal_gate.py",
        "paper-trader/backend/scripts/causal_admission_mutations.py",
        "paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md#task-12-phase-3-mutation-gate-operations-record-and-full-closure"
      ],
      "write_paths": [
        "paper-trader/backend/scripts/phase3_causal_gate.py",
        "paper-trader/backend/tests/test_phase3_causal_gate.py",
        "paper-trader/docs/reports/phase3-causal-gate.json",
        ".agent/runs/phase3-task12/gate_closure"
      ],
      "output": ".agent/runs/phase3-task12/gate_closure/report.md"
    },
    {
      "id": "scope_audit",
      "agent": "luna-worker",
      "model": "gpt-5.6-terra",
      "reasoning_effort": "medium",
      "mode": "read",
      "depends_on": [],
      "read_paths": [
        "git status and complete Phase 3 diff from 932691549672f34575e7ce737df90a2295880e5f",
        "paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md#12-acceptance-and-mutation-gates",
        "/Users/priyanshusaraf/dev/options-trading-migration-backups/2026-08-14-phase3-task12-9326915/protected-files.sha256"
      ],
      "write_paths": [
        ".agent/runs/phase3-task12/scope_audit"
      ],
      "output": ".agent/runs/phase3-task12/scope_audit/report.md"
    },
    {
      "id": "documentation_closure",
      "agent": "terra-worker",
      "model": "gpt-5.6-terra",
      "reasoning_effort": "medium",
      "mode": "write",
      "depends_on": [
        "gate_closure",
        "scope_audit"
      ],
      "read_paths": [
        ".agent/runs/phase3-task12/gate_closure",
        ".agent/runs/phase3-task12/scope_audit",
        "paper-trader/docs/reports/phase3-causal-gate.json",
        "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-v1-product-steer-design.md#9-phase-3-reconciliation"
      ],
      "write_paths": [
        "paper-trader/docs/operations/strategy-admission.md",
        "paper-trader/docs/reports/2026-08-13-phase3-causal-strategy-contract.md",
        "paper-trader/docs/ROADMAP.md",
        "paper-trader/docs/CONTINUE.md",
        ".agent/runs/phase3-task12/documentation_closure"
      ],
      "output": ".agent/runs/phase3-task12/documentation_closure/report.md"
    }
  ],
  "acceptance": [
    "The inherited dirty tree is inventoried before editing and the two future IR-v2 documents remain preserved and excluded.",
    "Every mutation, authority boundary, ownership boundary, next-bar invariant, schema head, and test suite required by the Phase 3 contract has direct non-vacuous evidence.",
    "The bounded gate refuses skipped, timed-out, empty, or failed checks and rejects forbidden overclaims in its report.",
    "Focused and PostgreSQL closure evidence passes where the required environment exists; absence keeps the phase open.",
    "The full backend and research suites run exactly once at the phase gate with full output stored under .agent/runs.",
    "The four protected inherited files retain their recorded hashes and git diff --check is clean.",
    "Operations and phase reports state exact results, open gates, rollback steps, and all V1 nonclaims without asserting deployment.",
    "One critical reviewer returns separate passing SPEC and QUALITY verdicts for the integrated diff."
  ],
  "test_plan": [
    "Focused: .venv/bin/python -m pytest -q tests/test_phase3_causal_gate.py",
    "SQLite closure: run the exact focused backend and research file list from Task 12 Step 4.",
    "PostgreSQL closure: run the exact PT_TEST_POSTGRES_URL file list from Task 12 Step 5; do not invent or print credentials.",
    "Mutation gate: .venv/bin/python scripts/causal_admission_mutations.py --json",
    "Bounded phase gate: .venv/bin/python scripts/phase3_causal_gate.py --json ../docs/reports/phase3-causal-gate.json",
    "One broad gate: .venv/bin/python -m pytest -q tests research_tests",
    "Integrity: git diff --check, dirty-tree fingerprint, protected hashes, and future-file exclusion."
  ],
  "review": {
    "required": true,
    "assignment_id": "critical_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader"
    ],
    "exclude_paths": [
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md"
    ],
    "output": ".agent/runs/phase3-task12/critical_review/verdict.json",
    "inputs": [
      "this capsule",
      "the generated review package",
      "the relevant reviewing-strategy-os-critical-changes references",
      "the integrated diff",
      "only evidence logs named by the package"
    ],
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  },
  "dirty_tree_baseline": {
    "head": "932691549672f34575e7ce737df90a2295880e5f",
    "recovery_snapshot": "/Users/priyanshusaraf/dev/options-trading-migration-backups/2026-08-14-phase3-task12-9326915",
    "future_findings_excluded": [
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md"
    ]
  }
}
---

# Phase 3 Task 12 capsule

Resume from the existing dirty work. The first action is an audit, not a rewrite. The capsule limits new edits to the closure gate and evidence paths while the final reviewer evaluates the complete inherited Phase 3 diff.

Dispatch only the declared assignments and only when their dependencies permit it. The slice owner integrates compact reports, runs the broad gate once, generates the review package, and stops if any acceptance claim lacks direct evidence.
