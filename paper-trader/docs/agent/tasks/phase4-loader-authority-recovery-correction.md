---
{
  "id": "phase4-loader-authority-recovery-correction",
  "phase": "phase4",
  "status": "active",
  "goal": "Make the actual Phase 4 execution admission loader enforce the complete persisted research, capability, graph, and receipt authority chain before its terminal v2-runtime refusal, and replace invocation-only evidence with attributable real-consumer evidence.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded correction work needed to finish Phase 4. The first Terra-medium owner supplied a provisionally correct loader implementation but did not satisfy the capsule evidence contract. This continuation authorizes one fresh Sol-medium repeated-failure evidence-and-regression owner and, only after the current product/test/source-map freeze, one newly declared Luna-medium evidence-only child. Final product bytes are frozen: production paths are read-only except for controlled reversible mutations with exact byte restoration. Authority is limited to focused real-consumer regressions, current-byte ADV attribution, the declared mutation matrix, transitive evidence revalidation, defect/deployability accuracy, and ignored evidence. Phase 5, frontend, provider adapters, schema, migration, service configuration, deployment, credentials, production, live, and money authority remain closed.",
    "stopping_condition": "Complete only after the actual load_verified_admission Phase 4 branch receives explicit research authority, plan, and cutoff context; calls the existing complete Phase 4 verifier itself; refuses absent or stale authority before provider, cache, job, worker, broker, deployment, evaluation, order, or money side effects; preserves the legacy v1 contract; and has direct current-byte evidence for all final-review-3 findings. Stop with the goal active if closure requires silently opening a research session, inferring authority context, changing a production caller, broker/deployment/live-money semantics, a schema or migration, a generic authority dispatcher, or a path outside this capsule.",
    "evidence_stopping_condition": "Retain the final-review-3 verdict and pre-edit missing-authority counterexample; focused product and consumer selectors; exact command/cwd/timestamp/collected-node/exit attribution for every claimed adversarial row; dynamic no-side-effect evidence for the generic loader consumers; byte-restored guard mutations; protected/scoped hashes; a transitive revalidation map; and a concise owner report. Dots-only pytest logs, manual prerequisite helpers, monkeypatched authority loaders, source-token scans without dynamic proof, and historical PASS labels do not satisfy this condition."
  },
  "risk_tags": [
    "critical",
    "authority",
    "consumer-enforcement",
    "fresh-process",
    "evidence-attribution"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "9. Ownership, authority, and persistence",
        "10. Acceptance scenarios and refusals",
        "13.1 Fact and equality matrix",
        "13.2 Persistence, reconstruction, and refusal",
        "13.3 Adversarial owner matrix",
        "13.5 Stale evidence and revalidation"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "5. Verification cadence",
        "8. Authority-correction serial route"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-002 — Syntactic self-consistency mistaken for authority",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact",
        "DP-008 — Manual prerequisite verification substituted for the consuming seam"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership"
      ]
    }
  ],
  "dependency_gate": "phase4-final-review-3",
  "allowed_paths": [
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/sweep.py",
    "paper-trader/backend/app/core/deployments.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/app/engine/broker.py",
    "paper-trader/backend/app/engine/runner.py",
    "paper-trader/backend/tests/test_backtest_admission.py",
    "paper-trader/backend/tests/test_backtest_cache.py",
    "paper-trader/backend/tests/test_backtest_job_claims.py",
    "paper-trader/backend/tests/test_backtest_parallel.py",
    "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py",
    "paper-trader/backend/tests/test_deployments.py",
    "paper-trader/backend/tests/test_shadow_deployments.py",
    "paper-trader/backend/tests/test_paper_authority_runtime.py",
    "paper-trader/backend/tests/test_phase4_authority_integration.py",
    "paper-trader/backend/tests/test_phase4_loader_authority_consumers.py",
    "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/tests/test_phase4_resolved_topology_identity.py",
    "paper-trader/backend/tests/test_public_backtest_computation.py",
    "paper-trader/backend/tests/test_strategy_admission_backfill.py",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    ".agent/runs/phase4-loader-authority-recovery-correction"
  ],
  "final_product_edits_forbidden": true,
  "mutation_only_paths": [
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/sweep.py",
    "paper-trader/backend/app/core/deployments.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/app/engine/broker.py",
    "paper-trader/backend/app/engine/runner.py"
  ],
  "nonclaims": [
    "This correction does not implement Component IR v2 execution. A completely verified Phase 4 receipt still terminates at V2_RUNTIME_UNAVAILABLE.",
    "This correction does not make a contextless deployment, runner, broker, enqueue, retry, reclaim, pinned-worker, cache, order, or money path Phase 4 capable. Such callers must fail closed before side effects until a later authorized runtime design supplies explicit authority context.",
    "This correction does not accept Phase 4, regenerate or approve the official review package, open the foundation audit, Phase 5, frontend, providers, deployment, credentials, production, live, or money authority, or claim release deployability.",
    "No hidden database session, global authority context, inferred plan/cutoff, compatibility shim, second verifier, schema, migration, dependency, service, or configuration is introduced."
  ],
  "owner_gates": [
    "Stop if a Phase 4 caller must be made operational rather than fail closed, or if any final production caller byte must change. Controlled mutations are evidence-only and must restore the exact frozen hashes before any selector or completion claim.",
    "Stop if the complete authority chain cannot be enforced by the existing sole load_verified_admission and require_phase4_current seams without opening sessions or inferring plan/time.",
    "Stop if closure requires a schema/migration, provider adapter, broker semantics, deployment semantics, runtime enablement, frontend, credentials, production, live, money, destructive, legal, or commercial action."
  ],
  "stop_conditions": [
    "The actual loader can reach V2_RUNTIME_UNAVAILABLE with missing research dataset authority, missing persisted capability assessment, a stale or forged transitive fact, or absent explicit Phase 4 verification context.",
    "A manual pre-loader helper remains necessary for the integration test to pass, or any authority/persistence/reload seam is monkeypatched in the decisive lifecycle.",
    "Any generic loader consumer reaches provider construction, cache access, job creation/claim, worker execution, deployment activation, broker evaluation, order, or money state before context or authority refusal.",
    "Legacy v1 loader return values, bytes, or supported call shape change; a required mutation survives; restored bytes differ; a claimed ADV row lacks independently attributable evidence; or protected/scoped checks fail."
  ],
  "deployment_impact": {
    "classification": "schema-free-phase4-loader-authority-enforcement",
    "required_evidence": "No schema, migration, dependency, service, configuration, provider, frontend, or runtime-enablement change. Prove current SQLite plus the existing isolated PostgreSQL-backed authority lifecycle where the real loader crosses both persistence planes; prove every contextless production consumer refuses before side effects; preserve exact v1 behavior; record V2_RUNTIME_UNAVAILABLE only after full verification. No deployment, release, production, live, or money claim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "children": "gpt-5.6-luna",
    "child_reasoning_effort": "medium",
    "child_agent_role": "luna-worker",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 1,
  "owner_milestones": [
    "owner_current_product_test_source_map_frozen",
    "owner_attributable_evidence_frozen"
  ],
  "assignments": [
    {
      "id": "phase4_loader_evidence_closure",
      "agent": "luna-worker",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "write-evidence-only",
      "depends_on": [
        "owner_current_product_test_source_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/app/backtest/repository.py",
        "paper-trader/backend/app/backtest/sweep.py",
        "paper-trader/backend/app/core/deployments.py",
        "paper-trader/backend/app/core/strategy_admissions.py",
        "paper-trader/backend/app/engine/broker.py",
        "paper-trader/backend/app/engine/runner.py",
        "paper-trader/backend/tests/test_backtest_admission.py",
        "paper-trader/backend/tests/test_backtest_cache.py",
        "paper-trader/backend/tests/test_backtest_job_claims.py",
        "paper-trader/backend/tests/test_backtest_parallel.py",
        "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py",
        "paper-trader/backend/tests/test_deployments.py",
        "paper-trader/backend/tests/test_shadow_deployments.py",
        "paper-trader/backend/tests/test_paper_authority_runtime.py",
        "paper-trader/backend/tests/test_phase4_authority_integration.py",
        "paper-trader/backend/tests/test_phase4_loader_authority_consumers.py",
        "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
        "paper-trader/backend/tests/test_phase4_resolved_topology_identity.py",
        "paper-trader/backend/tests/test_public_backtest_computation.py",
        "paper-trader/backend/tests/test_strategy_admission_backfill.py"
      ],
      "write_paths": [
        ".agent/runs/phase4-loader-authority-recovery-correction/phase4_loader_evidence_closure"
      ],
      "output": ".agent/runs/phase4-loader-authority-recovery-correction/phase4_loader_evidence_closure/report.md"
    }
  ],
  "acceptance": [
    "The Phase 4 branch of the sole actual load_verified_admission seam requires explicit research_session, plan, and aware at_time context; reconstructs the receipt; invokes require_phase4_current itself; and reaches V2_RUNTIME_UNAVAILABLE only after the complete persisted dataset, capability, market, provider, graph, receipt, owner, mode, plan, registry, and cutoff chain verifies.",
    "Missing explicit Phase 4 context has one stable fail-closed refusal distinct from ADMISSION_REQUIRED, RECEIPT_STALE, and V2_RUNTIME_UNAVAILABLE. The loader never opens a session or infers a plan/cutoff.",
    "A real two-plane lifecycle proves missing research rows, missing persisted assessment, wrong owner, stale or forged transitive facts, and mismatched plan/cutoff refuse through the actual loader. The decisive test does not pre-call the dataset or assessment loader and does not monkeypatch the authority seam.",
    "Contextless deployment, runner, broker, enqueue, retry, reclaim, pinned-worker, cache, and job consumers dynamically prove refusal before provider construction, cache lookup/write, job write/claim, worker/evaluator invocation, deployment activation, broker signal/order handling, money mutation, or live side effect. Static source mapping includes every production load_verified_admission call site and is supporting evidence only.",
    "Legacy v1 load_verified_admission callers, returned values, persistence bytes, worker serialization, and result/cache behavior remain unchanged; non-Phase4 missing-admission behavior remains unchanged.",
    "The retained ADV-001 through ADV-027 claims are re-run or explicitly narrowed against current bytes. Each row has a separate machine-readable record containing cwd, full command, timestamp, selected and collected node IDs, exit code, expectation, observed refusal or identity change, decisive addresses where applicable, and source test mapping. ADV-019 is corrected rather than inherited.",
    "DP-008 records the general pattern that manual prerequisite verification cannot substitute for enforcement by the actual authority-consuming seam, and the implementation report/deployability ledger invalidate and then revalidate all dependent Phase 4 loader, integration, H3/H4, and final-review claims.",
    "Controlled mutations kill the missing-context guard, the require_phase4_current invocation, persisted assessment/dataset verification, terminal-refusal ordering, and at least one no-side-effect consumer guard; exact product and test bytes are restored before final selectors.",
    "Focused current-tree selectors, syntax, scoped diff, protected hashes, frontend/provider/deployment/live exclusions, evidence manifest hashes, and report accuracy pass. Only phase4-final-review-4 may become ready after root audit and official package regeneration."
  ],
  "test_plan": [
    "Preserve and reproduce the final-review-3 counterexample before editing: persist only the Phase 4 graph and receipt, omit research authority rows and persisted capability assessment, call the actual loader, and show the pre-edit terminal refusal.",
    "Freeze one explicit-context loader contract. Run focused actual-loader, integration, cache/job/worker, deployment, runner, broker, v1 compatibility, and fresh-process selectors only. Do not run broad suites merely for confidence.",
    "After the fresh owner freezes current product/test/source-map bytes, dispatch only the newly declared Luna-medium evidence child. It must use .codex/scripts/run_logged.py from the exact paper-trader or backend cwd and write an attributable JSONL/manifest plus concise report; it must not edit product, tests, docs, programme, package, or verdicts.",
    "Run controlled reversible mutations, restore exact bytes, rerun the focused selector, then capture complete dirty fingerprint and scoped hashes. PostgreSQL is required only for the already-cross-plane Phase 4 lifecycle, not as a broad confidence suite."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_loader_evidence_closure_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/sweep.py",
      "paper-trader/backend/app/core/deployments.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/engine/broker.py",
      "paper-trader/backend/app/engine/runner.py",
      "paper-trader/backend/tests/test_backtest_admission.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/backend/tests/test_backtest_job_claims.py",
      "paper-trader/backend/tests/test_backtest_parallel.py",
      "paper-trader/backend/tests/test_backtest_pinned_worker_reads.py",
      "paper-trader/backend/tests/test_deployments.py",
      "paper-trader/backend/tests/test_shadow_deployments.py",
      "paper-trader/backend/tests/test_paper_authority_runtime.py",
      "paper-trader/backend/tests/test_phase4_authority_integration.py",
      "paper-trader/backend/tests/test_phase4_loader_authority_consumers.py",
      "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/tests/test_phase4_resolved_topology_identity.py",
      "paper-trader/backend/tests/test_public_backtest_computation.py",
      "paper-trader/backend/tests/test_strategy_admission_backfill.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend",
      "paper-trader/backend/app/engine/kite_venue.py",
      "paper-trader/backend/app/engine/venue.py",
      "paper-trader/backend/app/providers/brokers.py",
      "paper-trader/backend/tests/test_broker_registry.py"
    ],
    "output": ".agent/runs/phase4-loader-authority-recovery-correction/owner/report.md",
    "verdicts": [
      "CORRECTED",
      "BLOCKED"
    ]
  }
}
---

# Phase 4 loader-authority recovery correction

The third final review proved that complete Phase 4 authority was verified beside
the production loader, not by it. Keep one loader and one complete verifier. The
loader must receive explicit authority context, perform the complete check itself,
and only then return the existing non-executable v2 refusal. Existing production
callers that cannot supply that context remain fail closed before side effects.

This capsule also replaces dots-only and helper-only evidence with exact,
attributable current-byte evidence. It grants no runtime, deployment, provider,
frontend, live, or money authority.

The first implementation owner is historical input, not capsule acceptance. A
root audit accepted the frozen loader design provisionally but rejected the
completion claim because the evidence lacked separate machine-readable
ADV-001..027 records, complete dynamic generic-consumer proof, four required
mutation classes, a transitive revalidation map, and exact path-labelled hash
accounting. The fresh Sol-medium owner must close those gaps without changing
final product bytes; prior dots-only, wrong-worktree, or hash-only records are
not completion evidence.
