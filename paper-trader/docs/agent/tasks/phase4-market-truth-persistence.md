---
{
  "id": "phase4-market-truth-persistence",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Persist canonical market truth and owner-scoped dataset provenance through additive execution and research migrations with exact compatibility, integrity, restart, and restore evidence.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after empty install and supported upgrades reach exact heads on SQLite compatibility and disposable PostgreSQL 16, constraints hold after restart, local restore passes, and phase4-data-contract-capability is eligible."
  },
  "risk_tags": [
    "critical",
    "migration",
    "persistence",
    "tenancy",
    "research-lineage",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
        "11. Deployment contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    }
  ],
  "dependency_gate": "phase4-market-truth-domain",
  "allowed_paths": [
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/migrations/versions/20260817_0036_phase4_market_truth.py",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/0007_phase4_dataset_provenance.py",
    "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
    "paper-trader/backend/tests/test_phase4_market_truth_postgresql.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/docs/agent/tasks/phase4-market-truth-persistence.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-market-truth-persistence"
  ],
  "nonclaims": [
    "No production migration, data backfill, provider import, deployment, credential access, or attribution rewrite occurs.",
    "Local SQLite and PostgreSQL evidence does not prove release deployability, production scale, backup, or rollback."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if work would duplicate accepted IR, validator, resolver, hash, registry, research lineage, execution binding, owner boundary, or authority."
  ],
  "stop_conditions": [
    "Either migration plane cannot install, upgrade, restart, restore, or reach exact head.",
    "Owner isolation, digest immutability, non-overlap, secret exclusion, or cross-plane digest checks can be bypassed.",
    "The change needs destructive backfill, production data, credentials, or an unowned migration path."
  ],
  "deployment_impact": {
    "classification": "migration-required",
    "affected_dimensions": [
      "Schema",
      "Migration",
      "Persistence",
      "Recovery",
      "Compatibility"
    ],
    "required_evidence": "Empty install, supported upgrade, exact heads, restart, local backup/clean restore, integrity, owner isolation, deterministic fixture import, and rollback-path evidence on SQLite compatibility and disposable PostgreSQL 16."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Execution schema owns canonical market-truth and capability metadata; research schema owns owner-scoped dataset manifests and provenance.",
    "Immutable digests, temporal non-overlap, owner filters, secret exclusion, and cross-plane digest references fail closed.",
    "SQLite compatibility and disposable PostgreSQL 16 install, upgrade, restart, local restore, and exact heads pass.",
    "No production backfill or cutover occurs."
  ],
  "test_plan": [
    "Run backend/.venv/bin/python -m pytest -q backend/tests/test_phase4_market_truth_persistence.py backend/tests/test_schema_migrations.py.",
    "Use the disposable PostgreSQL 16 harness for backend/tests/test_phase4_market_truth_postgresql.py and record exact heads.",
    "Kill mutations removing owner, immutability, non-overlap, secret exclusion, or one migration-plane head check."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_market_truth_persistence_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/migrations/versions/20260817_0036_phase4_market_truth.py",
      "paper-trader/backend/research/domain/models.py",
      "paper-trader/backend/research/domain/migrate.py",
      "paper-trader/backend/research/domain/migrations/0007_phase4_dataset_provenance.py",
      "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
      "paper-trader/backend/tests/test_phase4_market_truth_postgresql.py",
      "paper-trader/backend/tests/test_schema_migrations.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-market-truth-persistence/owner_integration/report.md",
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

# Phase 4 market-truth persistence

This is one durable implementation goal. It must retain full command output under its ignored evidence directory through `.codex/scripts/run_logged.py`.
