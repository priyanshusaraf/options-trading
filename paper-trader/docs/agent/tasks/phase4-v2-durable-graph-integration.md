---
{
  "id": "phase4-v2-durable-graph-integration",
  "phase": "phase4",
  "status": "accepted",
  "correction_iteration": 3,
  "goal": "Close the Phase 4 durable-identity boundary exposed by the stopped recovery: persist immutable Component IR v2 graph facts separately from admission receipts in both persistence planes, make Phase 4 assessment evidence independently verifiable after restart, and make every current runtime consumer fail closed before provider, cache, worker, deployment, or money use until Phase 5 supplies an accepted v2 component catalogue and execution adapter.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "On 2026-08-17 the owner authorized all bounded work needed to finish Phase 4 after the earlier recovery exposed a schema and runtime boundary. Repeated-failure ownership uses Sol medium and declared mechanical children use Luna max. This authorization does not open Phase 5 implementation, frontend, providers, deployment, credentials, production, live authority, or money.",
    "stopping_condition": "Complete only after the two persistence planes store separate immutable v2 graph and Phase 4 admission facts atomically, a legitimate receipt and its complete assessment evidence survive canonical serialization and process-style reload, the real execution loader verifies the owner-local graph/receipt/registry chain and then returns the stable v2-runtime-unavailable refusal before any provider/cache/worker surface, forged or colliding facts fail closed, both migrations pass the declared fresh/upgrade/restart checks, v1 bytes and readers remain unchanged, every changed critical guard has killed-and-byte-restored mutation evidence, and an exact final-tree evidence manifest is ready for a fresh official review package. Do not accept Phase 4 or transition Phase 5; return integrated evidence to the root coordinator."
  },
  "risk_tags": [
    "critical",
    "architecture-correction",
    "schema",
    "migration",
    "ir-v2-identity",
    "admission-authority",
    "research-integrity",
    "runtime-refusal",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "2. Existing architecture verdicts",
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
        "1. Scope and stopping rule",
        "2. Dependency order",
        "3. Exclusive path ownership",
        "4.5 Data contract and capability",
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
        "Phase 5 ownership",
        "V1 release gate"
      ]
    }
  ],
  "input_evidence": [
    ".agent/runs/phase4-review/verdict.json",
    ".agent/runs/phase4-review/recheck-verdict.json",
    ".agent/runs/phase4-review-recovery/owner_integration/report.md",
    ".agent/runs/phase4-review-recovery/phase4_recovery_real_loader_regressions/report.md",
    "paper-trader/docs/reports/phase4-implementation.md"
  ],
  "dependency_gate": "phase4-final-review-2",
  "architecture_decisions": [
    "Legacy GraphVersion remains the sole v1 graph record and every existing v1 writer, reader, hash, and byte representation remains unchanged.",
    "Add one dedicated immutable owner-scoped Component IR v2 graph-version record to the execution plane and one separate equivalent evidence record to the research plane. Each stores the exact canonical v2 document plus its distinct authored content address, executable projection graph address, and registry snapshot address. Neither record grants execution authority.",
    "The sole Phase 4 admission constructor remains app.strategy.admission.admit_phase4_v2_strategy. Its canonical receipt must carry the complete immutable capability-assessment document whose content address is named by the binding; persisted reconstruction validates that document, exact requirement coverage, and every repeated binding without minting a write-authorized artifact.",
    "Execution put and research store_admission derive their plane-local v2 graph record only from the exact constructor-authorized Phase4V2AdmittedStrategyArtifact and persist graph plus receipt in one transaction/savepoint. Exact retries converge; owner/version/content/graph/registry collisions refuse.",
    "The real loader dispatches by receipt format. For Phase 4 v2 it verifies receipt, assessment, graph record, canonical document, owner, version, all addresses, and the supplied/current registry. It then raises one stable V2_RUNTIME_UNAVAILABLE refusal before constructing a Strategy, reading providers, touching cache, enqueuing work, reclaiming work, deploying, or reaching money authority.",
    "Phase 5 owns the accepted first-party v2 component catalogue, graph-output-to-Strategy mapping, v2 execution adapter, worker serialization, and enablement of research/backtest consumers. Phase 4 must not add placeholder components, infer output semantics, adapt v2 into the v1 IRGraphStrategy, or claim runnable v2 strategies."
  ],
  "allowed_paths": [
    "paper-trader/backend/app/ir/v2_graph_versions.py",
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/sweep.py",
    "paper-trader/backend/migrations/versions/20260817_0037_ir_v2_graph_versions.py",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/0008_ir_v2_graph_versions.py",
    "paper-trader/backend/tests/test_phase4_capability_admission.py",
    "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/tests/test_backtest_admission.py",
    "paper-trader/backend/tests/test_backtest_cache.py",
    "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py",
    "paper-trader/backend/tests/test_backtest_job_claims.py",
    "paper-trader/backend/tests/test_ir_v2_execution_migration.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
    "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/research_tests/test_phase4_v2_receipt_authority.py",
    "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    ".agent/runs/phase4-v2-durable-graph-integration"
  ],
  "root_owned_paths": [
    "paper-trader/docs/agent/tasks/phase4-v2-durable-graph-integration.md",
    "paper-trader/docs/agent/tasks/phase4-final-review-3.md",
    "paper-trader/docs/agent/tasks/phase4-review-recovery.md",
    "paper-trader/docs/agent/tasks/phase4-final-review-2.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-audit.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
    "paper-trader/docs/agent/tasks/phase5-architecture.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/review-package.json"
  ],
  "nonclaims": [
    "The new records are immutable graph/evidence facts, not a second IR, registry, resolver, admission authority, execution adapter, component catalogue, provider authority, research ledger, or deployment authority.",
    "A verified Phase 4 v2 receipt remains intentionally non-executable. V2_RUNTIME_UNAVAILABLE is the accepted Phase 4 runtime result until the exact Phase 5 obligations pass independent review.",
    "The migrations prove local fresh/upgrade/restart and integrity behavior only. They do not prove a production migration, cutover, backup policy, release deployability, production rehearsal, or deployment readiness.",
    "No frontend, provider/broker connection, credentials, production data/use, capacity, entry/exit policy, order routing, money authority, authoritative live IR, or Phase 5 implementation is opened.",
    "The immutable failed review, failed recheck, and stopped recovery evidence remain historical facts. Only phase4-final-review-3 can accept the corrected Phase 4 boundary."
  ],
  "owner_gates": [
    "Stop before frontend, provider/broker, credential, VPS, deployment, production data/use, destructive infrastructure/data work, money/live authority, legal/regulatory/commercial action, or Phase 5 component/runtime implementation.",
    "Stop before modifying legacy GraphVersion representation, v1 graph publication/readers, v1 IRGraphStrategy semantics, global registry contents, graph-output semantics, provider construction, cache result semantics, or worker execution semantics.",
    "Stop if the exact additive v2 tables cannot preserve owner isolation, canonical bytes, distinct content/graph addresses, immutable collision refusal, supported database dialects, and clean migration lineage without weakening an existing guard."
  ],
  "stop_conditions": [
    "Closure requires treating an admission receipt as the graph-version authority, storing a v2 document in legacy GraphVersion, inventing a Phase 4 component catalogue/output mapping, or executing v2 through IRGraphStrategy.",
    "A legitimate constructor-produced receipt cannot be independently reconstructed from persisted graph, receipt, assessment, and registry facts after process-style reload, or the stable runtime refusal occurs before those facts are verified.",
    "Either plane permits a forged lookalike, partial graph/receipt write, owner/version/address collision, mutable row, non-canonical document, or graph/assessment address substitution.",
    "A named direct regression or reversible mutation survives; a fresh/upgrade/restart migration check fails; a protected hash changes; frontend changes appear; inherited work conflicts; or final evidence cannot bind the exact dirty tree."
  ],
  "deployment_impact": {
    "classification": "additive-execution-and-research-schema-with-fail-closed-v2-runtime",
    "affected_dimensions": [
      "Application",
      "Execution PostgreSQL schema",
      "Research PostgreSQL schema",
      "SQLite development compatibility",
      "Admission persistence",
      "Backtest enqueue and worker refusal",
      "Research evidence persistence",
      "Deployability ledger"
    ],
    "required_evidence": "Execution head 0037 and research head 0008; exact fresh install and supported 0036/0007 upgrade; SQLite and disposable PostgreSQL 16 table/constraint/immutability/collision behavior; restart and canonical reload; no partial graph/receipt write; v1 schema/bytes/readers unchanged; V2_RUNTIME_UNAVAILABLE before provider/cache/worker; focused rollback-path documentation; protected hashes; frontend no-diff; diff check; exact final-tree manifest. No deployment or production claim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "children": "gpt-5.6-luna",
    "child_reasoning_effort": "max",
    "child_agent_role": "default",
    "independent_checker": "gpt-5.6-sol",
    "independent_checker_reasoning_effort": "high",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": [
    "owner_v2_persistence_interfaces_frozen",
    "owner_product_code_frozen",
    "owner_test_fixtures_frozen"
  ],
  "assignments": [
    {
      "id": "phase4_v2_graph_migration_regressions",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "max",
      "mode": "write",
      "depends_on": [
        "owner_v2_persistence_interfaces_frozen"
      ],
      "write_paths": [
        "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
        "paper-trader/backend/tests/test_ir_v2_execution_migration.py",
        "paper-trader/backend/tests/test_schema_migrations.py",
        "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
        "paper-trader/backend/research_tests/test_ir_v2_research_migration.py"
      ],
      "output": ".agent/runs/phase4-v2-durable-graph-integration/phase4_v2_graph_migration_regressions/report.md"
    },
    {
      "id": "phase4_v2_receipt_authority_regressions",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "max",
      "mode": "write",
      "depends_on": [
        "owner_v2_persistence_interfaces_frozen"
      ],
      "write_paths": [
        "paper-trader/backend/tests/test_phase4_capability_admission.py",
        "paper-trader/backend/research_tests/test_phase4_v2_receipt_authority.py"
      ],
      "output": ".agent/runs/phase4-v2-durable-graph-integration/phase4_v2_receipt_authority_regressions/report.md"
    },
    {
      "id": "phase4_v2_loader_refusal_regressions",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "max",
      "mode": "write",
      "depends_on": [
        "owner_v2_persistence_interfaces_frozen"
      ],
      "write_paths": [
        "paper-trader/backend/tests/test_backtest_admission.py",
        "paper-trader/backend/tests/test_backtest_cache.py",
        "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py",
        "paper-trader/backend/tests/test_backtest_job_claims.py"
      ],
      "output": ".agent/runs/phase4-v2-durable-graph-integration/phase4_v2_loader_refusal_regressions/report.md"
    },
    {
      "id": "phase4_v2_durable_graph_mutation_evidence",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "max",
      "mode": "write-evidence-only",
      "depends_on": [
        "owner_product_code_frozen",
        "owner_test_fixtures_frozen",
        "phase4_v2_graph_migration_regressions",
        "phase4_v2_receipt_authority_regressions",
        "phase4_v2_loader_refusal_regressions"
      ],
      "write_paths": [
        ".agent/runs/phase4-v2-durable-graph-integration/phase4_v2_durable_graph_mutation_evidence"
      ],
      "output": ".agent/runs/phase4-v2-durable-graph-integration/phase4_v2_durable_graph_mutation_evidence/report.md"
    }
  ],
  "independent_checks": [
    {
      "id": "phase4_foundation_identity_pattern_check",
      "dispatch_owner": "root",
      "agent": "default",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "high",
      "mode": "read-only-evidence",
      "depends_on": [],
      "read_paths": [
        "paper-trader/backend/app/ir",
        "paper-trader/backend/app/market_truth",
        "paper-trader/backend/app/market_data",
        "paper-trader/backend/app/strategy",
        "paper-trader/backend/app/backtest",
        "paper-trader/backend/app/core/strategy_admissions.py",
        "paper-trader/backend/app/db/models.py",
        "paper-trader/backend/migrations",
        "paper-trader/backend/research/domain",
        "paper-trader/backend/tests",
        "paper-trader/backend/research_tests",
        "paper-trader/docs/superpowers/specs/2026-08-11-multi-user-contract-design.md",
        "paper-trader/docs/superpowers/specs/2026-08-12-user-research-ownership-design.md",
        "paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md",
        "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
        "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
        "paper-trader/docs/reports/phase4-implementation.md",
        "paper-trader/docs/agent/DEFECT_PATTERNS.md",
        ".agent/runs/phase4-review",
        ".agent/runs/phase4-review-correction",
        ".agent/runs/phase4-review-recovery"
      ],
      "write_paths": [
        ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check"
      ],
      "output": ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/report.md",
      "requirements": [
        "Reconstruct the content-address versus graph-address failure from first principles without relying on the implementation owner's design or any historical PASS.",
        "Explain why earlier architecture, correction, mutation, package, and final-review evidence failed to expose the incompatible persisted-loader assumptions.",
        "Search the relevant Phase 1-4 foundation for the same distinct-fact-collapse pattern: two semantic facts represented by one identifier, row, type, cache key, ownership field, version, receipt, or authority token.",
        "Inspect real create-or-admit to persist to process-style reload to verify to consume paths wherever practical; label every mocked or unexercised seam rather than treating it as acceptance evidence.",
        "For every serious finding provide root cause, prevention invariant, permanent adversarial regression, defect-pattern-register entry, and a transitive evidence-invalidation map from changed invariant through affected contracts, phases, tests, and reviews to required revalidation.",
        "Classify each finding by severity and scope. Report Critical findings to the root coordinator immediately. Do not edit product, tests, migrations, documentation, programme state, package files, or retained evidence."
      ]
    }
  ],
  "acceptance": [
    "Execution IrV2GraphVersion and research ResearchIrV2GraphVersion are additive, owner-scoped, immutable records with exact canonical document bytes, format version 2, graph identifier/version, full content address, executable projection graph address, and registry snapshot address. They do not alter legacy GraphVersion or v1 storage/read behavior.",
    "The Phase 4 receipt includes one closed canonical capability_assessment object. Its address equals phase4_data_binding.capability_assessment_address; owner, mode, plan, registry, dataset, market truth, policy, evidence, time, requirement rows, SATISFIED state, and exact compiled-plan coverage are independently recomputed during persisted reconstruction.",
    "Execution put and research store_admission accept new Phase 4 rows only from the exact constructor-produced artifact; derive graph and assessment facts from that object; insert graph plus receipt atomically; make exact retries converge; and reject lookalikes, missing facts, owner collisions, same-version/different-content collisions, address substitution, partial-write attempts, and cross-plane byte divergence.",
    "A legitimate constructor-produced receipt survives JSON serialization, database storage, session/process-style reload, current-registry verification, plane-local v2 graph verification, and assessment reconstruction. No verification step relies on the original in-memory CapabilityAssessment token.",
    "The real load_verified_admission path dispatches Phase 4 v2 away from legacy GraphVersion and IRGraphStrategy, completes durable verification, then raises exactly V2_RUNTIME_UNAVAILABLE. Enqueue, reclaim, worker, broker/deployment consumers, and cache paths refuse before provider construction, cache read/write, job creation/claim, strategy evaluation, or money/live surfaces.",
    "The global production registry remains unchanged and cannot execute the Phase 4 fixture graphs. Tests may inject an explicit accepted test registry only to prove persistence verification; they cannot turn the loader into an executable v2 adapter.",
    "Phase 5 receives exact named obligations for the accepted component catalogue, output mapping, Strategy adapter, worker serialization, replay/cache enablement, and provider-independent execution evidence. No Phase 4 report claims executable v2 backtests, research runs, paper/live deployment, or provider correctness.",
    "Execution migration 0037 and research migration 0008 pass fresh install, supported 0036/0007 upgrade, restart/reopen, exact table/constraint/index/immutability checks, SQLite compatibility, and disposable PostgreSQL 16 checks. Destructive downgrade remains refused and the deployment ledger records the required production migration/rehearsal obligations.",
    "Direct final-tree selectors cover graph/receipt atomicity, assessment reconstruction, exact retries, collisions, tampering, owner isolation, actual loader/refusal, enqueue/worker/cache non-reachability, v1 and non-opted-v2 compatibility, both migration planes, and the retained Phase 4 correction scenarios without monkeypatching the behavior being claimed.",
    "Every changed critical guard has a reversible mutation whose exact targeted regression fails and whose byte-restored selector passes. At minimum mutate graph/receipt atomicity, execution and research exact-type gates, assessment-address verification, v2 graph-address verification, legacy-v1 dispatch separation, and the final V2_RUNTIME_UNAVAILABLE boundary.",
    "The root-dispatched independent Sol-high checker reconstructs the defect without relying on the implementation owner, completes the declared distinct-fact-collapse search, explains the prior evidence failure, and supplies a transitive invalidation map. Every Critical finding is either closed in this bounded slice with direct real-path evidence or keeps integration and final review blocked; lower-severity findings receive an explicit owner, rationale, and gate disposition.",
    "Protected hashes match, frontend has no diff, syntax and scoped diff checks pass, git diff --check passes, reports make only exercised claims, and the owner returns an exact evidence manifest with commands, cwd, timestamps, HEAD, complete dirty fingerprint, exit codes, file/evidence hashes, immutable failed-verdict and stopped-recovery hashes, migration heads, mutation restoration, and package-readiness boundary. Only phase4-final-review-3 may become ready after root audit."
  ],
  "test_plan": [
    "Retain and hash the stopped recovery evidence. Reproduce the legacy GraphVersion/v2 identity impossibility and frozen-wrapper/forged-lookalike counterexamples before editing, then freeze the additive record, receipt, and refusal interfaces before dispatching the three disjoint regression children.",
    "Use focused SQLite tests while implementing. At product/test freeze run the exact execution/research persistence, migration, admission, real-loader, enqueue/reclaim/worker/cache-refusal, and v1 compatibility selectors; then run only the affected Phase 4 selector necessary to validate the integrated claims.",
    "Run the declared reversible mutations only after product and test freeze. Require each targeted selector to fail, restore exact bytes, rerun it, and compare final product hashes with frozen baselines.",
    "Run fresh and upgrade migration checks through the disposable PostgreSQL 16 harness where declared, plus restart/reopen, model/metadata parity, protected-hash, frontend no-diff, syntax/import, scoped diff, diff-check, report accuracy, evidence hashes, and complete final fingerprint through .codex/scripts/run_logged.py."
  ],
  "review": {
    "required": true,
    "separate_stage": "phase4-final-review-3",
    "assignment_id": "phase4_v2_durable_graph_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/v2_graph_versions.py",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/sweep.py",
      "paper-trader/backend/migrations/versions/20260817_0037_ir_v2_graph_versions.py",
      "paper-trader/backend/research/domain/models.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/research/domain/migrate.py",
      "paper-trader/backend/research/domain/migrations/0008_ir_v2_graph_versions.py",
      "paper-trader/backend/tests/test_phase4_capability_admission.py",
      "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/tests/test_backtest_admission.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py",
      "paper-trader/backend/tests/test_backtest_job_claims.py",
      "paper-trader/backend/tests/test_ir_v2_execution_migration.py",
      "paper-trader/backend/tests/test_schema_migrations.py",
      "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
      "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/research_tests/test_phase4_v2_receipt_authority.py",
      "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/tasks/phase4-v2-durable-graph-integration.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-3.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-audit.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      ".agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/report.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase4-v2-durable-graph-integration/owner_integration/report.md",
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

# Phase 4 v2 durable graph integration

The stopped recovery proved that a Phase 4 v2 receipt cannot honestly traverse the legacy v1 GraphVersion and IRGraphStrategy path. This owner-authorized replacement adds separate immutable v2 graph facts, makes the persisted assessment self-verifying, and gives every current runtime consumer one explicit fail-closed result. It does not implement Phase 5's component catalogue or execution adapter. One Sol-medium owner integrates the product and documentation, three disjoint Luna-max children own regression fixtures, and one later Luna-max child owns mutation evidence. A separate Sol-high critical reviewer decides Phase 4.
