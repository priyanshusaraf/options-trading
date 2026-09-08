---
{
  "id": "post-phase3-postgresql-harness",
  "phase": "post-phase3-infrastructure",
  "status": "accepted",
  "goal": "Provide one reusable, fail-closed local command that provisions disposable PostgreSQL 16, exports PT_TEST_POSTGRES_URL only to its child command, proves real PostgreSQL contracts, and always tears the instance down.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after unit contracts, a real PostgreSQL success run, a child-failure cleanup run, integrity checks, and deployability documentation pass without using live credentials or persistent databases."
  },
  "risk_tags": [
    "database",
    "developer-infrastructure",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Current verdict", "Proven foundations", "Open obligations"]
    },
    {
      "path": "paper-trader/docs/operations/postgresql-backup-restore.md",
      "sections": ["Preconditions and authority boundary", "Local PostgreSQL 16 backup"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/scripts/run_disposable_postgres.py",
    "paper-trader/backend/tests/test_disposable_postgres_harness.py",
    "paper-trader/docs/operations/local-postgresql-verification.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/tasks/post-phase3-postgresql-harness.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/post-phase3-postgresql-harness"
  ],
  "nonclaims": [
    "The harness proves local PostgreSQL-backed contracts only; it does not prove production readiness, managed PostgreSQL, backup retention, recovery objectives, deployment, or live authority.",
    "The harness does not change application schemas, migrations, runtime database selection, credentials, or provider behavior."
  ],
  "owner_gates": [
    "Do not connect to an inherited or remote PostgreSQL URL; provision a new loopback-only temporary instance for every run.",
    "Do not access live credentials, production data, the live VPS, deployment, frontend code, or authoritative live execution."
  ],
  "stop_conditions": [
    "PostgreSQL 16 server tools are unavailable locally.",
    "The harness cannot prove cleanup after both child success and child failure.",
    "Implementation would require a schema, migration, application runtime, or production configuration change."
  ],
  "architecture_decision": {
    "verdict": "KEEP + HARDEN",
    "reason": "Existing tests already consume one optional PT_TEST_POSTGRES_URL contract. Add one local lifecycle wrapper around that contract instead of adding another database profile, schema authority, or test model."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "postgresql_harness_implementation",
      "agent": "terra-worker",
      "write_paths": [
        "paper-trader/backend/scripts/run_disposable_postgres.py",
        "paper-trader/backend/tests/test_disposable_postgres_harness.py"
      ],
      "evidence_path": ".agent/runs/post-phase3-postgresql-harness/postgresql_harness_implementation"
    },
    {
      "id": "owner_integration",
      "agent": "owner",
      "write_paths": [
        "paper-trader/docs/operations/local-postgresql-verification.md",
        "paper-trader/docs/agent/DEPLOYABILITY.md",
        "paper-trader/docs/agent/tasks/post-phase3-postgresql-harness.md",
        "paper-trader/docs/agent/programme/PROGRAMME.json",
        "paper-trader/docs/agent/CURRENT.md"
      ],
      "evidence_path": ".agent/runs/post-phase3-postgresql-harness/owner_integration"
    }
  ],
  "acceptance": [
    "The command locates PostgreSQL 16 tools from PATH or supported local package-manager prefixes and fails clearly when unavailable.",
    "Each invocation creates a unique temporary cluster, binds only to loopback and its private socket directory, creates a disposable database, and supplies its URL only through the child environment.",
    "An inherited PT_TEST_POSTGRES_URL is never reused as the target.",
    "Success, child failure, interruption, and startup failure all attempt bounded shutdown and remove the temporary directory.",
    "The child exit code is preserved, and the harness does not hide skipped PostgreSQL tests.",
    "Unit contracts and a real PostgreSQL run covering the repository's execution, research, concurrency, and restore seams pass.",
    "Documentation gives one copyable command and retains precise local-only nonclaims."
  ],
  "test_plan": [
    "Run focused harness unit contracts.",
    "Run a child that verifies PT_TEST_POSTGRES_URL is PostgreSQL and queries the server version.",
    "Run representative execution, research, concurrency, and restore tests through the harness and reject skips.",
    "Run a deliberate failing child and prove the server and temporary directory are gone afterward.",
    "Run git diff --check and protected-file hashes."
  ],
  "review": {
    "required": false,
    "reason": "This is local developer tooling only and changes no product runtime, schema, migration, authority, or money behavior.",
    "assignment_id": "postgresql_harness_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/scripts/run_disposable_postgres.py",
      "paper-trader/backend/tests/test_disposable_postgres_harness.py",
      "paper-trader/docs/operations/local-postgresql-verification.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/post-phase3-postgresql-harness/owner_integration/report.md",
    "verdicts": ["INTEGRATION"],
    "max_rechecks": 0
  }
}
---

# Reusable disposable PostgreSQL developer harness

This capsule must close before Component IR v2 acceptance or any later phase implementation begins.

## Closure evidence

- Focused harness contracts: `.agent/runs/post-phase3-postgresql-harness/postgresql_harness_implementation/focused-unit-tests-psycopg-url-final.log` (`12 passed`).
- Real SQLAlchemy/Psycopg 3 connection to disposable PostgreSQL 16: `.agent/runs/post-phase3-postgresql-harness/postgresql_harness_implementation/real-sqlalchemy-psycopg-url-final.log`.
- Repository execution, research, concurrency, schema, outbox, admission, and restore contracts: `.agent/runs/post-phase3-postgresql-harness/owner_integration/repository_postgres_contracts_final.log` (exit `0`; no missing-URL skip; only the named opposite-plane parametrization skips).
- Owner integration and nonclaims: `.agent/runs/post-phase3-postgresql-harness/owner_integration/report.md`.
