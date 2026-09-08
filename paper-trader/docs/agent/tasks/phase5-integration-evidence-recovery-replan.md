---
{
  "id": "phase5-integration-evidence-recovery-replan",
  "phase": "phase5",
  "status": "accepted",
  "kind": "critical_architecture",
  "goal": "Design one bounded serial recovery for the failed Phase 5 integration gate by deciding capital database-plane ownership, cache-schema version authority and complete process-state isolation from the frozen 169-test universe without changing product or tests.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "AUTHORIZE PHASE-5 INTEGRATION EVIDENCE RECOVERY REPLAN received on 2026-08-26.",
    "stopping_condition": "Complete only after the immutable failed integration bytes and complete 169-node/35-file universe verify; all twelve capital tables receive architecture-derived plane ownership and cross-plane implications; cache version 9 and every consumer are traced to accepted authority; process-wide state surfaces and a case-blind observation contract are frozen; serial non-overlapping correction capsules and verification tiers are machine-native; deployability impact and future owners are exact; and the decision is recorded without product/test drift."
  },
  "risk_tags": ["critical", "money", "persistence-plane", "cache-identity", "false-green", "test-process-state", "architecture-only"],
  "required_docs": [
    {"path": ".agent/runs/phase5-implementation/owner-replan-proposal.md", "sections": ["Exact failure universe", "Required architecture decisions", "Recommended serial lineage", "Boundaries"]},
    {"path": "paper-trader/docs/superpowers/plans/phase5-strategy-os.md", "sections": ["Dependency order", "Independent assurance ownership"]},
    {"path": "paper-trader/docs/superpowers/plans/phase5-capital-admission.md", "sections": ["Dependency order", "Slice 6: Phase 5 integration and final review"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "Phase 5 ownership", "V1 release gate"]}
  ],
  "input_evidence": [
    ".agent/runs/phase5-implementation/owner/report.md",
    ".agent/runs/phase5-implementation/owner/phase-tier-final.log",
    ".agent/runs/phase5-implementation/owner/failure-classification.log",
    ".agent/runs/phase5-implementation/owner/failure-inventory-final.log",
    ".agent/runs/phase5-implementation/owner/shared-state-inventory-final.log",
    ".agent/runs/phase5-capital-assurance-final-review/review/verdict.json"
  ],
  "dependency_gate": "phase5-capital-assurance-final-review",
  "historical_predecessor": "phase5-implementation",
  "allowed_paths": [
    ".agent/runs/phase5-integration-evidence-recovery-replan",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase5-integration-evidence-recovery-replan.md",
    "paper-trader/docs/agent/tasks/phase5-review.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".codex/tests/test_programme_orchestration.py"
  ],
  "product_test_paths_read_only": ["paper-trader/backend/app", "paper-trader/backend/research", "paper-trader/backend/tests", "paper-trader/backend/research_tests"],
  "decision_questions": {
    "P5-INT-001": "Which existing Plane owns each of the twelve capital tables, and which foreign-key/copy/restore consumers inherit that decision?",
    "P5-INT-002": "What accepted contract advanced backtest cache SCHEMA_VERSION to 9, and which exact tests/artifact compatibility consumers must follow it?",
    "P5-INT-003": "What complete process-wide state vector and case-blind observer can attribute every order-dependent failure without trusting sampled writer lists?"
  },
  "nonclaims": [
    "No product/test, plane mapping, cache version, shared fixture, runtime, schema, migration, dependency, configuration, service, provider/broker, order, live/customer-money, frontend, deployment, production or Phase 6 change.",
    "The accepted capital assurance remains valid at its reviewed scope; the failed integration gate and all 169 red nodes remain unaccepted history.",
    "Architecture acceptance cannot create the Phase 5 final-review package or make phase5-review ready."
  ],
  "owner_gates": [
    "Stop before any product/test repair or a plane/cache/state decision not derived from the established authority contracts.",
    "Stop if complete state observation requires runtime/live access, destructive database work, credentials, deployment or Phase 6 scope."
  ],
  "stop_conditions": [
    "The failed integration report, 169-node inventory, accepted capital verdict or a protected product/test hash drifts.",
    "A correction group overlaps another writer, a state surface is sampled or self-derived, or the correction DAG can bypass the full tests/research_tests gate.",
    "Any successor would silently enable runtime authority, weaken paper/live separation, overwrite failed history or reuse a stale package."
  ],
  "deployment_impact": {
    "classification": "architecture-changing evidence ownership; implementation impacts to be decided per successor",
    "affected_dimensions": ["Database plane ownership", "Cache/artifact compatibility", "Test-process evidence integrity", "Phase 5 release evidence"],
    "highest_claim": "locally_runnable evidence only",
    "future_owner": "Generated exact correction capsules own in-scope rows; phase5-implementation reruns the full gate; Phase 6/7/V1 retain production topology, configuration, security, capacity, rollout and deployment."
  },
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "next_reviewer": "gpt-5.6-sol", "next_reviewer_reasoning_effort": "high", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The exact 169 failed nodes, 35 files, domain counts, four deterministic reproductions and unresolved 165-node boundary are frozen and independently consumable.",
    "Every capital table has one proposed existing Plane with authority rationale; every crossing and deployment/copy/restore consumer is enumerated before implementation.",
    "Cache version 9 is traced through the code/evidence/commit lineage; the replan decides code-versus-test authority without changing a numeric literal by inspection alone.",
    "The process-state model enumerates app state, dependency overrides, provider instances, registries/caches, settings/environment, database files and other discovered mutable singletons, with pre/post serialization and case-blind diff semantics.",
    "Successor write ownership is serial, non-overlapping and proportional; each guard/restoration contract has a killed mutation and the final full phase process is mandatory.",
    "No product/test byte changes and Phase 5 review/Phase 6 remain blocked."
  ],
  "test_plan": [
    "Verify immutable hashes, programme normalization and product/test freeze.",
    "Inspect plane mapping, capital model FKs, copy/restore consumers and established plane authority; produce a complete table decision matrix.",
    "Trace SCHEMA_VERSION 9 through current code, tests, evidence and commit history; produce a complete consumer matrix.",
    "Derive and execute a read-only state-observation prototype over the exact failing file order; reject incomplete state coverage before creating successors.",
    "Validate successor capsules, protected hashes, deployability ownership, architecture and programme route; stop before correction."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase5_integration_recovery_replan_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/phase5-integration-evidence-recovery-replan/architecture-package.json",
    "review_paths": ["paper-trader/backend/app/db/planes.py", "paper-trader/backend/app/backtest/cache.py", "paper-trader/backend/conftest.py", "paper-trader/backend/tests", "paper-trader/docs/agent/DEPLOYABILITY.md", ".agent/runs/phase5-implementation"],
    "exclude_paths": ["paper-trader/frontend"],
    "output": ".agent/runs/phase5-integration-evidence-recovery-replan/report.md",
    "verdicts": ["ARCHITECTURE"]
  },
  "protected_files": {
    "paper-trader/backend/app/db/planes.py": "2f59c20b539030965c1a7a469e98c587341ecdba1e72478be57cf39093dcd990",
    "paper-trader/backend/tests/test_db_planes.py": "1fdffacbee1e7f054696b1b68b6aedf85108f5da27064367e7efd7d9b78137e3",
    "paper-trader/backend/app/backtest/cache.py": "f058baee9329fa96825a4e384cb1f75cbbc1a625df1432f5df1179075bd00f13",
    "paper-trader/backend/tests/test_backtest_cache_risk_model.py": "feb8776b6d951ab8918a1a2d273b2b19ea646c786ad475c8855a0cd5c4a2e55b",
    "paper-trader/backend/tests/test_backtest_premium.py": "5beec80d387149debf4763436064d2fdc9fc901c05cf1c0b51e856a511a1dbe7",
    "paper-trader/backend/conftest.py": "f3981b13d150804fb441cec137e36d765b1c2a7d855dd666001a256ef150fc81",
    ".agent/runs/phase5-implementation/owner/report.md": "a2f7d91d49b35c7efdabc974d7d9f6c3f7b560cd36633c7407c25c0caf9e0406",
    ".agent/runs/phase5-implementation/owner/phase-tier-final.log": "61ba69fed27f8b7f3d6a4a2ddac94b41468725fc25d327fac92e60139f58941c",
    ".agent/runs/phase5-implementation/owner/failure-inventory-final.log": "f4ae1767da589ddd7fcaf51079bb5ca2d64f99ad89987376925310237c921a59",
    ".agent/runs/phase5-implementation/owner/shared-state-inventory-final.log": "f6a90fe8d497dc420ac509ea896cd897591f7227bf5ab0824439c7bebb9a5cb9",
    ".agent/runs/phase5-capital-assurance-final-review/review/verdict.json": "14a68da48e41562f1de76994f2955aedebb92e9668cd2e5f3210a5593f050fbd"
  },
  "acceptance_record": {
    "verdict": "ARCHITECTURE PASS",
    "decision": "KEEP + HARDEN",
    "report": ".agent/runs/phase5-integration-evidence-recovery-replan/report.md",
    "report_sha256": "171fa0903476fddb7708f60e374832f2a9f77ddad55905c6cf6ea97b7cb231dd",
    "deployability": ".agent/runs/phase5-integration-evidence-recovery-replan/deployability.md",
    "deployability_sha256": "3b80b30725c99afa6251e3fba7a79b836b801a983dfee1f409c6e3864295eb8e",
    "product_test_drift": 0,
    "successors": ["phase5-capital-plane-ownership-correction", "phase5-cache-version-contract-correction", "phase5-stale-compatibility-fixture-correction", "phase5-process-state-isolation-correction", "phase5-implementation", "phase5-review"],
    "successor_authorization_required": true
  }
}
---

# Phase 5 integration evidence recovery replan

This owner-authorized capsule is read-only. It converts the failed phase gate into
architecture-derived, non-overlapping correction ownership and stops before changing
any product or test byte.
