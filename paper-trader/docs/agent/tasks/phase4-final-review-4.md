---
{
  "id": "phase4-final-review-4",
  "phase": "phase4",
  "status": "ready",
  "goal": "Independently review the exact corrected Phase 4 tree, including real loader-enforced authority, attributable adversarial evidence, and dynamic consumer containment, and issue separate SPEC and QUALITY verdicts without repairing the tree.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized one new independent final review after bounded Phase 4 recovery and completion of the adversarial-matrix closure. This is a fresh read-only Sol-high critical review, not a recheck. It may write only its verdict. Phase 5, the later foundation audit, frontend, providers, deployment, credentials, production, live, and money authority remain blocked unless the exact programme gate later opens them.",
    "stopping_condition": "Complete only after the official package and lineage verify, the adversarial matrix proves exactly ADV-001..ADV-027 FULL with zero residual/skip/xfail/deselection/historical uplift, ADV-006 proves only the corrected Phase 4 containment contract with an explicit P5-ADV-006-RUNTIME nonclaim, the downstream runtime obligation remains exact and hard-gated, and the reviewer issues explicit SPEC and QUALITY verdicts for the exact final tree. Any package defect, missing authority enforcement, manual-helper false green, unattributable or narrowed row, successful-reclaim inference from Phase 4, weakened downstream obligation, untested real consumer, stale transitive claim, correction need, or other Critical/High blocker requires FAIL. The reviewer never repairs or re-packages the tree."
  },
  "risk_tags": [
    "critical-review",
    "authority",
    "fresh-process",
    "consumer-side-effects",
    "evidence-quality"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "9. Ownership, authority, and persistence",
        "10. Acceptance scenarios and refusals",
        "11. Deployment contract",
        "13. Authority-foundation correction contract"
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
        "DP-001 — Distinct facts collapsed into one representation",
        "DP-002 — Syntactic self-consistency mistaken for authority",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-004 — Immutable envelope over mutable or time-incoherent facts",
        "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact",
        "DP-006 — Database session timezone changed copied authority instants",
        "DP-007 — Cross-dialect JSON constraint changed authoritative field shape",
        "DP-008 — Manual prerequisite verification mistaken for consumer-enforced authority"
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
  "dependency_gate": "phase4-adversarial-matrix-closure",
  "allowed_paths": [
    ".agent/runs/phase4-final-review-4/verdict.json"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "Dual PASS accepts only the exact reviewed local Phase 4 contracts and the explicit non-executable Component IR v2 boundary. It does not implement or accept Phase 5, frontend, providers, deployment, credentials, production data/use, capacity, release, live, or money authority.",
    "The reviewer writes only the verdict and does not repair product, tests, docs, package, capsule, programme, or evidence. Historical failed verdicts remain immutable.",
    "SQLite and disposable PostgreSQL evidence do not prove production migration, feed correctness, execution behavior, service topology, capacity, or release readiness.",
    "ADV-006 FULL proves only explicit-context authority verification and fail-closed pre-claim containment. It does not prove successful v2 claim, reclaim, worker execution, result finalization, Phase 5 readiness, or P5-ADV-006-RUNTIME."
  ],
  "owner_gates": [
    "Stop before any write outside the sole verdict path and before deployment, credentials, production data/use, destructive work, frontend, provider, Phase 5, live, or money action."
  ],
  "stop_conditions": [
    "The official package, exact HEAD/base, complete dirty fingerprint, scoped/evidence hashes, historical verdict hashes, migration heads, protected hashes, frontend exclusion, programme state, or diff check is stale or inconsistent.",
    "The actual loader can reach V2_RUNTIME_UNAVAILABLE before complete persisted authority verification, or a decisive lifecycle relies on a manual pre-loader verification/helper/monkeypatch.",
    "Any claimed ADV row lacks exact command/cwd/selector/collected-node/exit/expectation/observation attribution, or any real generic-loader consumer lacks dynamic no-side-effect proof.",
    "Any ADV-001..ADV-027 row is not current-byte FULL, retains a residual, is skipped/xfailed/deselected, relies on historical uplift, omits a required persistence plane, or substitutes a helper/manual prerequisite for the named public seam.",
    "ADV-006 is treated as successful v2 claim/reclaim evidence, lacks proof that exact V2_RUNTIME_UNAVAILABLE precedes every named side effect, or omits its explicit P5-ADV-006-RUNTIME nonclaim.",
    "P5-ADV-006-RUNTIME no longer requires claim, ownership loss, public-seam reclaim after process death, exact current-authority reload, stale-claimant fencing, and current-claimant-only exactly-once finalization, or Phase 5 architecture no longer must generate one exclusive post-schema pre-reachability capsule with direct SQLite and disposable PostgreSQL 16 evidence.",
    "A correction is required. Record FAIL and stop; this review has zero rechecks and no repair authority."
  ],
  "deployment_impact": {
    "classification": "read-only-phase-wide-review-of-loader-authority-and-adversarial-assurance",
    "required_evidence": "Verify execution head 0039 and research head 0010; unchanged accepted product/migrations and v1 path; complete Phase 4 authority before terminal v2 refusal; real contextless consumer containment; exactly 27 FULL attributable adversarial rows including separate-database PostgreSQL 16 evidence; protected boundaries; frontend exclusion; deployability ledger; and production/release nonclaims. Do not infer deployability."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Official package lineage, exact HEAD/base, complete dirty fingerprint, scoped and evidence hashes, immutable failed-verdict hashes, migration heads, protected hashes, frontend exclusion, programme state, and diff check independently verify before substantive review.",
    "The reviewer reproduces final-review-3 P4FR3-SPEC-001 against the pre-correction lineage, then proves the corrected actual loader refuses missing research authority, missing persisted assessment, stale/forged transitive facts, and absent explicit context; a complete real two-plane chain alone reaches exact V2_RUNTIME_UNAVAILABLE.",
    "The reviewer proves P4FR3-QUALITY-001 closed: the decisive fresh-process integration calls the actual loader directly and contains no manual dataset/assessment prerequisite verification or authority monkeypatch.",
    "The reviewer proves P4FR3-QUALITY-002 closed: every ADV-001 through ADV-027 record is independently attributable to exact current-byte commands and collected node IDs, has an exit and semantic observation, maps to code, agrees with the implementation, is FULL with an empty residual list, and contains no skip, xfail, deselection, or historical-evidence uplift; ADV-014 and ADV-019 are specifically audited.",
    "The reviewer independently verifies ADV-006 at the real public v2 reclaim-dispatch seam with explicit current authority context: complete current authority reaches exact V2_RUNTIME_UNAVAILABLE before claim, reclaim, provider, cache, worker, claim-token, result, broker, order, or money side effects, while stale or missing authority refuses earlier. The verdict states that FULL proves containment only.",
    "The reviewer independently verifies the shared caller-owned savepoint boundary and every one of its seven adopted seams. SQLite and PostgreSQL evidence covers physical-root proof, marker cleanup, unproved external nesting refusal, no helper commit/rollback/close, clean/read/write/nested callers, failed commit plus rollback, exact retry/collision, fresh-process outcome, and at least eleven killed-and-restored mutations. Outbox writer remains the ledger owner while write_snapshot obtains direct boundary proof.",
    "The reviewer proves the preflight-to-mutation race is closed in one transaction: SQLite reservation precedes enumeration, PostgreSQL locks exact candidates, only explicit classified legacy ids are conditionally mutated with all predicates preserved, mixed v1/v2 sets cause zero mutation, concurrent inserts remain outside the closed ids, and transitions roll back. It rejects broad owner reconciliation, fresh selectors, helper-only verification, or missing lock/predicate mutation evidence.",
    "The reviewer proves one lifespan-owned synchronous research sessionmaker, at most one lazy synchronous Session per owner invocation, identical registry and aware cutoff at both loader calls, closure on every success/refusal/exception, and no hidden research state when disabled.",
    "The reviewer traces the intact P5-ADV-006-RUNTIME obligation through design, plan, deployability, Phase 5 architecture, the non-enabling graph-paper attribution schema, and programme ordering. It rejects any claim that Phase 4, schema acceptance, or a dynamic implementation placeholder proves or enables successful reclaim.",
    "The reviewer proves P4FR3-QUALITY-003 closed: the static production call-site map includes core deployments, engine runner, engine broker, backtest enqueue/retry/reclaim/pinned-worker/cache/job consumers, and dynamic tests prove refusal before each relevant provider/cache/job/worker/deployment/broker/order/money side effect.",
    "The reviewer independently attacks numeric validity, market identity/truth, capability, dataset, graph/receipt persistence, reconstruction, migration parity, owner isolation, result/cache identity, v1 compatibility, and equity/weekly-options/cross-market/refusal scenarios in proportion to their criticality, without treating historical PASS as proof.",
    "The loader remains one seam, require_phase4_current remains the sole complete Phase 4 verifier, no hidden session/authority context or new runtime exists, v1 behavior remains unchanged, and Component IR v2 remains non-executable.",
    "Separate SPEC and QUALITY verdicts are explicit. Only dual PASS permits the root to accept Phase 4 and launch the already-authorized separate user-owned Phase 1-4 foundation audit; Phase 5 remains blocked until that audit and its Critical-closure gate complete."
  ],
  "test_plan": [
    "Verify the package and immutable historical verdict lineage before relying on owner evidence.",
    "Use reviewer-owned focused counterexamples for the actual loader, missing/tampered authority, manual-helper bypass, generic-loader consumers, and evidence attribution; run only the targeted selectors required to support the verdict.",
    "Inspect the changed code and transitive consumers, exact mutation/restoration records, v1 compatibility, migrations, deployability ledger, protected paths, and package command attribution.",
    "Write only the verdict JSON with separate SPEC and QUALITY results, finding severity/evidence, residual risks, and exact downstream recommendation."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase4_final_review_4",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/db/concurrency.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/public_computation.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/ledger/service.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/research/domain/strategy_admissions.py",
      "paper-trader/backend/app/core/deployments.py",
      "paper-trader/backend/app/engine/runner.py",
      "paper-trader/backend/app/engine/broker.py",
      "paper-trader/backend/app/backtest/sweep.py",
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
      "paper-trader/backend/tests/phase4_adversarial_support.py",
      "paper-trader/backend/tests/test_phase4_adversarial_transactions.py",
      "paper-trader/backend/tests/test_phase4_adversarial_authority.py",
      "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
      "paper-trader/backend/tests/test_phase4_adversarial_resource_recovery.py",
      "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py",
      "paper-trader/backend/research_tests/test_phase4_authority_transaction_boundary.py",
      "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py",
      "paper-trader/backend/tests/ledger/test_routes.py",
      "paper-trader/backend/tests/test_outbox_contract.py",
      "paper-trader/backend/tests/test_phase4_resolved_topology_identity.py",
      "paper-trader/backend/tests/test_public_backtest_computation.py",
      "paper-trader/backend/tests/test_strategy_admission_backfill.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase4-loader-authority-recovery-correction.md",
      "paper-trader/docs/agent/tasks/phase4-adversarial-matrix-closure.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-4.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      ".agent/runs/phase4-final-review-3/verdict.json",
      ".agent/runs/phase4-loader-authority-recovery-correction",
      ".agent/runs/phase4-loader-authority-recovery-correction/root_acceptance/acceptance.md",
      ".agent/runs/phase4-adversarial-matrix-closure"
    ],
    "exclude_paths": [
      "paper-trader/frontend"
    ],
    "failed_review_output": ".agent/runs/phase4-final-review-3/verdict.json",
    "output": ".agent/runs/phase4-final-review-4/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY",
      "FINAL"
    ],
    "rechecks": 0
  }
}
---

# Phase 4 final review 4

This is a fresh independent review of the corrected final tree. It is not a
recheck and has no repair authority. It must attack the real loader boundary,
the consumers that call it, and the attribution of every claimed adversarial
result before assessing the rest of Phase 4.

Only separate SPEC and QUALITY PASS may accept Phase 4. That result opens only
the owner-authorized read-only Phase 1-4 foundation audit; Phase 5 and every
runtime, deployment, provider, frontend, live, and money boundary remain blocked.
