---
{
  "id": "strategy-os-v0-market-truth-recorded-at-identity-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_market_truth_identity_correction",
  "goal": "Correct NMT-001 so a MarketTruthSnapshot's recorded_at is preserved in canonical bytes, address, persistence and round-trip without rewriting historical v1 evidence under the same identity.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "NMT-001 is reproduced; a versioned snapshot contract preserves recorded_at and old v1 reconstruction; persistence/copy/restart/causality/mutations pass; one independent Critical SPEC/QUALITY review passes."},
  "risk_tags": ["critical", "market-truth", "canonical-identity", "causality", "research-integrity", "compatibility"],
  "required_docs": [
    {"path": ".agent/runs/kleppmann-numeric-and-market-truth-audit/report.md", "sections": ["Findings", "Direct evidence", "Nonclaims"]},
    {"path": ".agent/runs/kleppmann-numeric-and-market-truth-audit/owner/probe-market-truth-snapshot-identity.log", "sections": ["all output"]},
    {"path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md", "sections": ["Point-in-time market rulebook", "Contract identity", "Dataset provenance"]}
  ],
  "dependency_gate": "Canonical research-spine foundation paths are sealed and released. No schema migration or provider access is implied.",
  "allowed_paths": [
    "paper-trader/backend/app/market_truth/rulebook.py",
    "paper-trader/backend/app/market_truth/authority.py",
    "paper-trader/backend/tests/test_market_truth_domain.py",
    "paper-trader/backend/tests/test_phase4_authority_integration.py",
    "paper-trader/backend/tests/test_phase4_authority_timestamp_normalization.py",
    "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-market-truth-recorded-at-identity-correction.md",
    ".agent/runs/strategy-os-v0-market-truth-recorded-at-identity-correction"
  ],
  "new_paths": [".agent/runs/strategy-os-v0-market-truth-recorded-at-identity-correction"],
  "protected_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/providers", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Add recorded_at to the canonical snapshot fact and decoder through an explicit versioned contract. Do not change the answer of an existing v1 address or claim old bytes contained the field.",
    "Keep knowledge_cutoff and recorded_at separate. A snapshot recorded earlier than its cutoff remains distinguishable from one recorded at the cutoff.",
    "Preserve exact UTC normalization, record-learning cutoff checks, database address/canonical-json verification and all current consumers. No current-value substitution or future information.",
    "Record compatibility/migration impact honestly; no destructive rewrite, provider call, schema, dependency, frontend or deployment change."
  ],
  "acceptance": [
    "Two otherwise equal snapshots with different recorded_at have different v2 bytes/addresses and round-trip exact recorded_at; equivalent UTC offsets have one identity.",
    "Legacy v1 bytes/address remain readable under an explicit v1 decoder and never masquerade as v2; unsupported ambiguous bytes refuse.",
    "Persistence/load/reopen/copy checks recompute exact addresses; knowledge cutoff, record cutoff and created/recorded ordering refuse future leakage.",
    "Prefix/restart fixtures and genuine omit/substitute/cutoff mutations fail before exact restoration.",
    "One independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": ["RED/GREEN NMT-001, v1/v2 compatibility, UTC/cutoff/persistence/restart tests and affected market-truth/dataset authority selectors.", "Kill recorded_at omission, cutoff substitution and decoder-version guards; seal protected bytes and review package."],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "high", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "01a04eb9-389e-7c30-a861-6ab197f06ecc",
  "review": {"required": true, "assignment_id": "v0_market_truth_recorded_at_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Canonical point-in-time identity and historical reconstruction are Critical.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-market-truth-recorded-at-identity-correction/review-package.json", "review_paths": ["paper-trader/backend/app/market_truth/rulebook.py", "paper-trader/backend/app/market_truth/authority.py", "paper-trader/backend/tests/test_market_truth_domain.py", "paper-trader/backend/tests/test_phase4_authority_integration.py", "paper-trader/backend/tests/test_phase4_authority_timestamp_normalization.py", "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py", "paper-trader/docs/agent/tasks/strategy-os-v0-market-truth-recorded-at-identity-correction.md", ".agent/runs/strategy-os-v0-market-truth-recorded-at-identity-correction"], "exclude_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/providers", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-market-truth-recorded-at-identity-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["Standing V0 correction authority after sealed foundation release; no repeated token.", "No provider network, production data, schema, dependency, live, order, money or deployment action."],
  "stop_conditions": ["Correction would require rewriting historical v1 identity or a schema migration/provider fetch.", "An active owner overlaps an allowed path."],
  "deployment_impact": {"classification": "compatible versioned canonical fact change; no schema/dependency/service change", "required_evidence": "v1 reconstruction, v2 identity, persisted authority restart and exact rollback by decoder version"},
  "nonclaims": ["No provider conformance, dataset breadth, frontend acceptance, deployment, live/order/money or V0 completion."],
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-market-truth-recorded-at-identity-correction/review/verdict.json",
    "verdict_sha256": "cdc0d16c97ed4e0bb9a444a680aa53e71082416654938f31aaf5e6ac73fc6a28",
    "finding_ids": ["NMT-CR-001"],
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Freeze the actual pre-correction `market-truth-snapshot/2` envelope without recorded_at as the legacy read-only contract. Preserve its exact bytes and address; do not relabel it `/1`.",
    "Move the recorded_at-bearing current contract to a genuinely new schema version and dispatch decoding by the actual envelope version.",
    "Add a frozen real old-/2 byte/address fixture and prove direct decode plus persisted SQLite/fresh-process restart without re-encoding or re-addressing it; unsupported/ambiguous shapes still refuse.",
    "Rerun new-version recorded_at identity, UTC/cutoff, tamper and mutation evidence. Retain explicit PostgreSQL nonclaim unless the declared disposable harness runs.",
    "Reseal the same package lineage and route only the one focused recheck."
  ]
}
---

# V0 market-truth recorded-at identity correction

Correct NMT-001 without changing historical evidence under the same identity.
