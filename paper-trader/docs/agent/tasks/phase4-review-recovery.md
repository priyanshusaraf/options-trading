---
{
  "id": "phase4-review-recovery",
  "phase": "phase4",
  "status": "blocked",
  "stopped_by": "phase4-v2-durable-graph-integration",
  "stopped_evidence": ".agent/runs/phase4-review-recovery/owner_integration/report.md",
  "stopped_evidence_sha256": "aa87be3e60d0f5262b15867c4da134faddaf9cc360993d296408c743d3f0905c",
  "correction_iteration": 2,
  "goal": "Close only the two critical Phase 4 persistence/reconstruction defects and the corresponding real-loader evidence gap retained by the immutable focused recheck, without changing the frozen receipt schema or opening any later, frontend, provider, deployment, credential, production, money, or live boundary.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "On 2026-08-17 the owner explicitly authorized one new Phase 4 recovery-correction capsule and one new independent final-review stage, then confirmed that all bounded work needed to finish Phase 4 is authorized. The owner's standing routing decision assigns repeated-failure ownership to Sol medium and declared mechanical children to Luna max; this capsule records that explicit exception without changing the Sol-high independent-review gate.",
    "stopping_condition": "Complete only after legitimate JSON-round-tripped Phase 4 receipts reconstruct through the real loader, both execution and research write seams reject a structurally self-consistent receipt not produced by the sole Phase 4 admission authority, direct non-mocked regressions pass, every changed critical guard has killed-and-byte-restored mutation evidence, affected compatibility and the retained Phase 4 correction selector pass on the final tree, and an exact evidence manifest is ready for a fresh official review package. Do not accept Phase 4 or transition the programme; return the integrated evidence to the root coordinator."
  },
  "risk_tags": [
    "critical",
    "recovery",
    "admission-authority",
    "durable-reconstruction",
    "research-integrity",
    "cache-identity",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "3. One accepted executable architecture",
        "7. Data requirement and provider capability contracts",
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
        "10. Acceptance scenarios and refusals",
        "11. Deployment contract",
        "12. Deferred homes and nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "4.5 Data contract and capability",
        "4.6 Dataset identity and causality",
        "4.7 Integration gate",
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
        "V1 release gate"
      ]
    }
  ],
  "input_evidence": [
    ".agent/runs/phase4-review/verdict.json",
    ".agent/runs/phase4-review/recheck-verdict.json",
    ".agent/runs/phase4-review-correction/owner_integration/report.md",
    "paper-trader/docs/reports/phase4-implementation.md"
  ],
  "dependency_gate": "phase4-review-recheck",
  "allowed_paths": [
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/tests/test_phase4_capability_admission.py",
    "paper-trader/backend/tests/test_backtest_admission.py",
    "paper-trader/backend/tests/test_backtest_cache.py",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    ".agent/runs/phase4-review-recovery"
  ],
  "root_owned_paths": [
    "paper-trader/docs/agent/tasks/phase4-review-recovery.md",
    "paper-trader/docs/agent/tasks/phase4-final-review-2.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/review-package.json"
  ],
  "nonclaims": [
    "This recovery preserves the exact Phase 4 wrapper bytes and adds no second IR, admission authority, persistence table, schema, migration, dependency, configuration, service, provider connection, frontend, deployment, credential, production-data, production-use, capacity, money, or live-authority change.",
    "Durable read verification may reconstruct derivable graph/plan facts from canonical stored JSON, but only the sole constructor-authorized Phase4V2AdmittedStrategyArtifact may enter either generic persistence plane as a new Phase 4 receipt.",
    "Passing local persistence and loader evidence proves neither provider behavior, entry or exit authority, release deployability, production rehearsal, capacity, nor live-trading safety.",
    "The first failed review and failed recheck remain immutable. This recovery cannot accept Phase 4; only the new independent final review can do so."
  ],
  "owner_gates": [
    "Stop before any wrapper schema, database schema, migration, public API, dependency, service, frontend, provider or broker, execution or risk, live authority, deployment, credential, VPS, production-data/use, destructive, legal, regulatory, commercial, or Phase 5 change.",
    "Stop if closure requires embedding mutable assessment payloads in the receipt, treating generic protocol shape as admission authority, trusting a caller-supplied Phase 4 binding, or weakening owner, content-address, registry, plan, result, or cache checks."
  ],
  "stop_conditions": [
    "A correction requires a protected path, alternate constructor, second persistence representation, schema change, receipt-format change, or relaxation of v1 or non-opted-v2 behavior.",
    "A JSON-round-tripped legitimate receipt cannot be reconstructed and verified through the actual loader without relying on in-memory-only assessment state.",
    "Either execution or research write persistence accepts a lookalike Phase 4 protocol object whose canonical bytes were not authorized by the sole constructor, or either durable read path ceases to verify exact immutable bytes.",
    "A named direct regression or reversible mutation survives, a protected hash changes, frontend changes appear, inherited work conflicts, or final evidence cannot bind the exact dirty tree."
  ],
  "deployment_impact": {
    "classification": "compatible-runtime-and-research-persistence-hardening-no-schema-service-config-or-dependency-change",
    "affected_dimensions": [
      "Application",
      "Backtest worker restart/reclaim",
      "Execution admission persistence",
      "Research admission persistence",
      "Research result/cache identity",
      "Deployability ledger"
    ],
    "required_evidence": "Direct legitimate JSON roundtrip and actual-loader reconstruction; forged Phase 4 write refusal in both planes; exact retries and durable require-current compatibility; affected Phase 4 and legacy selectors; killed/restored mutations; unchanged migration heads 0036/0007; protected hashes; frontend no-diff; diff check; report accuracy; exact final-tree manifest. No deployment or readiness claim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "children": "gpt-5.6-luna",
    "child_reasoning_effort": "max",
    "child_agent_role": "default",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 3,
  "owner_milestones": [
    "owner_persistence_interfaces_frozen",
    "owner_product_code_frozen",
    "owner_test_fixtures_frozen"
  ],
  "assignments": [
    {
      "id": "phase4_recovery_persistence_regressions",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "max",
      "mode": "write",
      "depends_on": [
        "owner_persistence_interfaces_frozen"
      ],
      "write_paths": [
        "paper-trader/backend/tests/test_phase4_capability_admission.py"
      ],
      "output": ".agent/runs/phase4-review-recovery/phase4_recovery_persistence_regressions/report.md"
    },
    {
      "id": "phase4_recovery_real_loader_regressions",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "max",
      "mode": "write",
      "depends_on": [
        "owner_persistence_interfaces_frozen"
      ],
      "write_paths": [
        "paper-trader/backend/tests/test_backtest_admission.py",
        "paper-trader/backend/tests/test_backtest_cache.py"
      ],
      "output": ".agent/runs/phase4-review-recovery/phase4_recovery_real_loader_regressions/report.md"
    },
    {
      "id": "phase4_recovery_mutation_evidence",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "max",
      "mode": "write-evidence-only",
      "depends_on": [
        "owner_product_code_frozen",
        "owner_test_fixtures_frozen",
        "phase4_recovery_persistence_regressions",
        "phase4_recovery_real_loader_regressions"
      ],
      "write_paths": [
        ".agent/runs/phase4-review-recovery/phase4_recovery_mutation_evidence"
      ],
      "output": ".agent/runs/phase4-review-recovery/phase4_recovery_mutation_evidence/report.md"
    }
  ],
  "acceptance": [
    "P4-SPEC-007: the canonical persisted JSON document, not the frozen in-memory tuple representation, is supplied to resolve_v2 during reconstruction; a legitimate receipt survives serialization, database storage, process-style reload, owner-local require-current verification, graph-version verification, and actual load_verified_admission without a monkeypatched loader.",
    "P4-SPEC-006: put and store_admission reject every Phase 4 write that is not the exact constructor-authorized Phase4V2AdmittedStrategyArtifact, including a self-consistent lookalike with a substituted capability-assessment address and recomputed outer address. Exact legitimate writes and retries continue to work in both planes.",
    "Read verification remains possible for the internal reconstructed persisted artifact while no generic caller may use that read-only representation to create a new Phase 4 row. Owner, graph, receipt, embedded base, registry snapshot, plan, assessment address, and repeated binding facts remain exact and immutable.",
    "Direct tests cover legitimate and forged paths in both persistence planes and the real loader/restart seam. They do not monkeypatch load_verified_admission or substitute an in-memory artifact for the persisted JSON roundtrip being claimed.",
    "Every changed critical guard has a reversible killed-and-byte-restored mutation: remove execution write authority; remove research write authority; restore the frozen-document resolver input. The restored final selectors pass and final product hashes match their frozen baselines.",
    "The exact recovery selector, retained 139-test correction selector, necessary v1/non-opted-v2 persistence compatibility, and report-claim checks pass without a broad confidence suite.",
    "No schema or migration files change; execution/research heads remain 0036/0007; protected hashes match; frontend has no recovery diff; syntax, scoped diff, git diff --check, report, and deployability nonclaims pass.",
    "The owner returns an exact final evidence manifest with per-command cwd, command, timestamp, HEAD, complete dirty fingerprint, exit code, evidence classification, file hashes, immutable failed-verdict hashes, child reports, mutation restoration, and package-readiness boundary. Only phase4-final-review-2 may become ready after root audit."
  ],
  "test_plan": [
    "First reproduce the two immutable recheck counterexamples on the uncorrected tree and retain their exact outputs. Freeze the smallest write-authority and canonical-reconstruction interfaces before dispatching the two disjoint regression children.",
    "Run direct execution/research persistence tests, actual loader JSON roundtrip/restart tests, affected Phase 4 admission/backtest/cache selectors, and only the legacy/v1 compatibility selectors touched by these seams. Do not run a broad confidence suite.",
    "After product and test freeze, run three exact reversible mutations, require each targeted regression to fail, restore bytes exactly, and rerun the matching selector.",
    "Run final syntax/import, migration-head, protected-hash, frontend read-only, scoped diff, diff-check, evidence-hash, report-accuracy, and final-fingerprint checks through .codex/scripts/run_logged.py."
  ],
  "review": {
    "required": true,
    "separate_stage": "phase4-final-review-2",
    "assignment_id": "phase4_review_recovery_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/tests/test_phase4_capability_admission.py",
      "paper-trader/backend/tests/test_backtest_admission.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/tasks/phase4-review-recovery.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-2.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase4-review-recovery/owner_integration/report.md",
    "verdicts": [
      "INTEGRATION"
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

# Phase 4 review recovery

The owner-authorized recovery is confined to the two defects reproduced by the immutable failed recheck. One Sol-medium owner keeps all four product seams, freezes their interfaces, and then dispatches exactly two disjoint Luna-max regression children plus one later evidence-only Luna-max mutation child. It preserves the receipt schema and all downstream safety blocks. The owner prepares evidence only; a separate Sol-high critical reviewer decides Phase 4.

The capsule stopped at its declared architecture boundary. The narrow raw-JSON reconstruction and exact-type write guards are retained, but a legitimate Phase 4 v2 graph cannot be represented by legacy `GraphVersion`: its executable projection address and full document content address are intentionally distinct, and the legacy row requires one address to serve both roles. The immutable stop report is `.agent/runs/phase4-review-recovery/owner_integration/report.md` with SHA-256 `aa87be3e60d0f5262b15867c4da134faddaf9cc360993d296408c743d3f0905c`. `phase4-v2-durable-graph-integration` is the owner-authorized additive replacement; this stopped capsule makes no completion or Phase 4 acceptance claim.
