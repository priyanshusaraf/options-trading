---
{
  "id": "phase1-4-foundation-critical-review",
  "phase": "interphase-4-5",
  "status": "blocked",
  "provisional_contract": "This amended capsule is unaccepted and cannot activate before every repeated-failure recovery DAG node is root-accepted and node 5 freezes a current transitive package.",
  "goal": "Independently review the frozen foundation migration and numeric corrections, their transitive currentness, and their deployability nonclaims without repairing product, tests, evidence, or programme state.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "After transitive revalidation returns EVIDENCE_CURRENT and freezes one exact package, dispatch exactly one critical-reviewer with read-only access to the declared package and repository surfaces. The reviewer has no write authority except its ignored verdict directory.",
    "stopping_condition": "Complete only when one independent reviewer verifies package hashes against current bytes, reproduces the decisive migration and numeric evidence from named logs and bounded selectors, checks DP-010 and DP-011 prevention and invalidation closure, and returns separate MIGRATION and NUMERIC PASS or FAIL plus an overall PASS only when both pass. A missing, stale, contradictory, or unsupported input is FAIL, never an invitation to patch."
  },
  "risk_tags": [
    "critical-review",
    "research-integrity",
    "numeric-ingress",
    "migration",
    "transitive-currentness",
    "deployability-nonclaim"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": ["14. Foundation migration and market-number correction contract"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence", "DP-011 — Host-language numeric subtypes cross a typed market boundary"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Current verdict", "Foundation migration and numeric correction", "Foundation blockers", "Phase 4 ownership"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
      "sections": ["Phase 1-4 foundation transitive revalidation"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-state-contract-recovery.md",
      "sections": ["Phase 1-4 foundation research migration state-contract recovery"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "sections": ["Phase 1-4 foundation research migration projection correction"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-implementation.md",
      "sections": ["Phase 1-4 foundation research migration native-state implementation"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-mutation-attestation.md",
      "sections": ["Phase 1-4 foundation research migration native mutation attestation"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
      "sections": ["Phase 1-4 foundation research migration runtime correction"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
      "sections": ["Phase 1-4 foundation research migration evidence integration"]
    }
  ],
  "dependency_gate": "phase1-4-foundation-transitive-revalidation",
  "audit_binding": {
    "report_sha256": "cec0bdc931632b9297d733fa58f6057a60b32820882af5e90b3184fd88d54d6d",
    "manifest_sha256": "4933505aa93b9a9fc03a08617b933944c28a409269602f53d9060d563f2143c5",
    "findings": ["A-01", "A-02", "A-03", "A-04", "A-05"]
  },
  "allowed_paths": [
    ".agent/runs/phase1-4-foundation-critical-review"
  ],
  "read_only_paths": [
    ".agent/review-package.json",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-migration-numeric-architecture-correction",
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
    ".agent/runs/phase1-4-foundation-research-migration-runtime-correction",
    ".agent/runs/phase1-4-foundation-research-migration-evidence-integration",
    ".agent/runs/phase1-4-foundation-numeric-ingress-correction",
    ".agent/runs/phase1-4-foundation-transitive-revalidation",
    "paper-trader/backend",
    "paper-trader/docs",
    "paper-trader/frontend"
  ],
  "review_questions": [
    "Does the package bind the exact immutable audit hashes, final current product/test hashes, owner reports, mutations, protected hashes, and scoped diff without stale substitutions?",
    "Does SQLite support only empty direct construction, exact or enumerated-five-guard 0010, and exact 0011 through the sole literal target authority, while every unversioned, 0001-0009, unknown, or drifted start refuses before writes?",
    "Do SQLite and PostgreSQL 16 use caller-derived expected state, never observed rows or inventory, for an exact 24/24-table mapping across both materially distinct corpora; preserve textual JSON and BLOB/BYTEA bytes; document timestamp and boolean adaptation; bind exact marker and sequence values; and survive commit, close, disposal, and fresh-process reopen?",
    "Does PostgreSQL 16 use the exact accepted 0010 catalog, refuse 0003 through 0009 before writes, preserve parameterized rows and non-advancing sequence state, keep DDL and marker transactional, and validate exact head?",
    "Does 0011 handle complete and enumerated defect states without repairing arbitrary drift, rewriting authority, or using current model metadata as historical authority?",
    "Does fixture taxonomy separate EXACT_HISTORICAL_CATALOG_PROJECTION, SYNTHETIC_CONTRACT_VALID_WITNESS, CURRENT_HEAD, HYBRID_FAULT_INJECTION, and RETIRED so neither current-head/hybrid fixtures nor synthetic values receive historical fact credit?",
    "Does one pre-coercion rule reject Python bool and boolean scalars in every OHLCV field and assigned raw ingress before identity or effects?",
    "Do ordinary valid finite values retain identical float, frame, binary encoding, address, causal, cache, signal, and execution behavior?",
    "Does every DATA-01..DATA-24 mutation, including research_hypothesis and research_finding and valid insert mutations for guard-protected tables, commit with guards enabled, produce an effective expected-versus-observed digest delta, fail with its exact code after required reopen, and restore exactly?",
    "Do catalog mutations cover table and column type/null/default, PK/FK/unique/check, index/predicate, sequence/serial binding, function body/identity/language, trigger table/event/function, and extra/missing objects with the same effective-delta, expected-code, durable-reopen, and restore receipts?",
    "Does the machine claim attestation bind both corpora, both dialects, all 24 tables, exact markers/sequences, every mutation, collected node, command, log, and final hash, and do independent one-obligation removal tests reject it?",
    "Are all A-01 through A-05 invalidated FND, ADV, package, Phase 5, and deployability claims current or explicitly still blocked?",
    "Does every artifact avoid foundation acceptance, release deployability, production rehearsal, deployment, runtime, live, and money claims?"
  ],
  "decisive_evidence": [
    "Exact SQLite empty direct construction, exact and all enumerated five-guard 0010 transitions, exact 0011 no-op, arbitrary-data preservation, interruption rollback, and zero-write refusal for every unsupported class.",
    "Exact SQLite and PostgreSQL 16 caller-to-native lifecycle for both materially distinct non-authoritative corpora, all 24 tables, complete catalogs, exact markers and sequences, and fresh-process reopen; pre-write PostgreSQL 0003-0009 refusal.",
    "Effective, killed, and exactly restored DATA-01..DATA-24 plus complete catalog-class mutations, bound through the independently recomputed machine claim attestation.",
    "Existing-install 0011 complete-state certification, exact five-trigger defect repair, arbitrary-drift refusal, and restart behavior.",
    "True, False, and boolean scalar rejection across every OHLCV field and real provider-to-execution-price containment path.",
    "Byte-identical valid-input dataset encoding and address corpus.",
    "DP-010 and DP-011 mutation kill and exact restoration evidence.",
    "Integrated fresh-process authority reconstruction, protected hashes, audit hashes, and package-currentness validation."
  ],
  "acceptance": [
    "Every package hash matches current bytes and all serial correction owners remained within the repeated-failure recovery DAG's disjoint declared scope.",
    "Migration evidence closes A-01, A-03, A-04, A-05 and DP-010 for the exact supported matrix without narrowing or destructive repair.",
    "Numeric evidence closes A-02 and DP-011 without changing valid finite identity or execution semantics.",
    "Transitive evidence covers every named invalidated boundary and keeps deployability, production, runtime, live, and money claims blocked.",
    "The verdict reports separate component results and cites decisive evidence for every PASS or finding for every FAIL."
  ],
  "test_plan": [
    "Recompute package, audit, protected, product, test, and evidence hashes independently.",
    "Inspect and, where bounded and safe, rerun the decisive SQLite narrow-matrix, genuine PostgreSQL, existing-install 0011, boolean lifecycle, valid-identity, and mutation selectors.",
    "Review architecture conformance, fixture provenance, marker dialect reasoning, transitive currentness, and deployability nonclaims."
  ],
  "owner_gates": [
    "Stop and return FAIL before any repair, package rewrite, product/test edit, programme transition, production access, deployment, live, or money action.",
    "Treat a stale or incomplete package, unsupported prefix, support narrowing, valid identity change, or protected/audit hash mismatch as FAIL."
  ],
  "stop_conditions": [
    "Any required package input, decisive evidence, component verdict, or audit binding is absent or contradictory.",
    "The reviewer cannot reproduce the evidence from frozen bytes or would need to repair an input.",
    "Any unresolved Critical remains inside the reviewed migration or numeric boundary."
  ],
  "verdict_contract": {
    "output": ".agent/runs/phase1-4-foundation-critical-review/verdict.json",
    "required_fields": ["audit_binding", "review_package_sha256", "reviewed_tree_hashes", "migration_verdict", "numeric_verdict", "transitive_currentness_verdict", "deployability_nonclaim_verdict", "overall_verdict", "findings", "evidence_paths"],
    "component_values": ["PASS", "FAIL"],
    "overall_values": ["PASS", "FAIL"],
    "rule": "overall PASS requires every component PASS and zero unresolved Critical finding in the reviewed boundary"
  },
  "failure_routing": [
    "Expected/observed state or baseline receipt failure returns through root to a fresh bounded recovery for foundation_research_migration_native_state_owner; DATA/CAT/receipt/claim-attestation failure returns through root to a fresh bounded recovery for foundation_research_migration_native_mutation_attestation_owner. Runner or 0011 failure returns to foundation_research_migration_runtime_owner_2; fixture or independent-attestation failure returns to foundation_research_migration_evidence_attestation_owner. No accepted owner patches a completed dependency and no retired projection owner may resume.",
    "Numeric or valid-identity failure returns to the numeric owner through root coordination.",
    "Evidence or package failure returns to the transitive revalidation owner.",
    "Architecture contradiction, support narrowing, destructive requirement, or scope expansion returns to a fresh owner-approved architecture capsule.",
    "The reviewer never patches, reroutes programme state, or converts missing evidence into PASS."
  ],
  "nonclaims": [
    "A PASS closes only the reviewed A-01 through A-05 correction boundary for the parent critical-closure coordinator.",
    "A PASS does not accept the whole foundation, start Phase 5, prove release deployability or production rehearsal, authorize deployment, enable runtime, or grant live or money authority."
  ],
  "model_route": {
    "owner": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": true,
    "assignment_id": "foundation_migration_numeric_critical_reviewer",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "frozen package base",
    "package": ".agent/review-package.json",
    "review_paths": [
      ".agent/review-package.json",
      ".agent/runs/phase1-4-foundation-audit",
      ".agent/runs/phase1-4-foundation-migration-numeric-architecture-correction",
      ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery",
      ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
      ".agent/runs/phase1-4-foundation-research-migration-runtime-correction",
      ".agent/runs/phase1-4-foundation-research-migration-evidence-integration",
      ".agent/runs/phase1-4-foundation-numeric-ingress-correction",
      ".agent/runs/phase1-4-foundation-transitive-revalidation",
      "paper-trader/backend/research/domain",
      "paper-trader/backend/app/market_data/candles.py",
      "paper-trader/backend/app/backtest",
      "paper-trader/backend/research_tests",
      "paper-trader/backend/tests",
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md"
    ],
    "exclude_paths": ["paper-trader/frontend", "paper-trader/backend/app/engine", "paper-trader/backend/app/providers"],
    "output": ".agent/runs/phase1-4-foundation-critical-review/verdict.json",
    "verdicts": ["MIGRATION", "NUMERIC", "TRANSITIVE_CURRENTNESS", "DEPLOYABILITY_NONCLAIM"],
    "max_rechecks": 1
  }
}
---

# Phase 1-4 foundation critical review

One independent reviewer assesses the frozen correction package. The reviewer
has no repair authority and cannot turn local database evidence into a release
or deployment claim.
