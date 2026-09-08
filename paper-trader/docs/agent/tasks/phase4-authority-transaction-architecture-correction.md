---
{
  "id": "phase4-authority-transaction-architecture-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Freeze one dialect-safe caller-owned transaction contract for Phase 4 authority persistence after ADV-003 proved that a top-level SQLite SAVEPOINT can commit graph and receipt rows before the caller commits, and classify the same defect pattern across every relevant Phase 1-4 persistence seam before implementation resumes.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded work needed to finish Phase 4. One fresh Sol-medium architecture owner may inspect current Phase 1-4 transaction and authority-persistence seams and edit only the declared documentation, capsule, programme, CURRENT, and ignored evidence paths. Product, tests, schemas, migrations, package, frontend, providers, deployment, credentials, production, live, and money bytes remain read-only.",
    "stopping_condition": "Complete only when the ADV-003 execution and research failures are explained at the DBAPI transaction boundary; every current begin_nested/SAVEPOINT use in the declared Phase 1-4 surface is classified as impacted, already safe, non-authoritative, or separately gated with direct evidence; one shared dialect-safe ownership rule is frozen for SQLite and PostgreSQL; the exact implementation surface and dependent evidence invalidation map are bounded; and no authority write can survive caller commit failure followed by rollback. Stop if the correction requires schema or migration work, broad transaction rewrites, provider/broker behavior, deployment, production state, or live/money authority."
  },
  "risk_tags": [
    "critical",
    "architecture-correction",
    "transaction-boundary",
    "authority-atomicity",
    "sqlite-postgresql-parity",
    "defect-pattern-search"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "9. Ownership, authority, and persistence",
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
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-008 — Manual prerequisite verification substituted for the consuming seam"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase4-adversarial-matrix-closure.md",
      "sections": [
        "Phase 4 adversarial matrix closure"
      ]
    }
  ],
  "dependency_gate": "phase4-reclaim-authority-context-correction",
  "input_evidence": [
    ".agent/runs/phase4-adversarial-matrix-closure/phase4_adversarial_matrix_closure/adv_003_decisive_residual.log",
    ".agent/runs/phase4-adversarial-matrix-closure/owner_gate/report.md",
    ".agent/runs/phase4-adversarial-matrix-closure/phase4_adversarial_matrix_closure/adv_002_authoring.log",
    ".agent/runs/phase4-reclaim-authority-context-correction/root_acceptance/acceptance.md"
  ],
  "pattern_search_paths": [
    "paper-trader/backend/app/db/concurrency.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/research/domain/strategy_admissions.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/public_computation.py",
    "paper-trader/backend/app/ledger/service.py",
    "all other current Phase 1-4 begin_nested, SAVEPOINT, commit, and rollback callers discovered by source search"
  ],
  "architecture_questions": [
    "What exact SQLAlchemy and DBAPI state proves a real caller-owned outer transaction exists before a nested SAVEPOINT on SQLite and PostgreSQL?",
    "Which helper owns beginning the real outer transaction, and how does it avoid committing or rolling back unrelated caller work?",
    "How do clean sessions, prior reads, prior writes, caller begin blocks, nested callers, flush failures, DBAPI commit failures, collisions, retries, and process restart preserve one atomic authority fact?",
    "Which current begin_nested users write authoritative multi-row facts and therefore share the defect pattern, and which uses are already safe or outside this correction?",
    "Which accepted tests, evidence, reports, and matrix rows become stale and must be rerun after product bytes change?"
  ],
  "accepted_decision": {
    "api": "app.db.concurrency.caller_owned_savepoint(session, *, scope)",
    "ownership": "The caller alone owns the outer commit or rollback. The helper enlists the existing same connection, proves or materializes the physical outer transaction, owns only one nested savepoint, and never commits, rolls back, closes, invalidates, retries, or replaces caller resources.",
    "sqlite": "Before SAVEPOINT, issue explicit BEGIN when the same sqlite driver connection is not in a transaction and verify in_transaction. A Session logical root or Session.begin is not sufficient proof.",
    "postgresql": "Before SAVEPOINT, issue a harmless statement when the driver is idle and verify INTRANS. RELEASE remains inside the caller-owned physical root.",
    "proof_lifecycle": "Bind root SessionTransaction identity, enlisted connection identity, and dialect in Session.info. Clear the marker only when the root ends; do not clear on nested end; recheck live driver state on every entry.",
    "nested_rule": "A recursive call is allowed only under the same live root proof. An already nested SQLite Session without that proof refuses before write because BEGIN cannot be inserted beneath an external top-level savepoint. An externally owned root is accepted only when the exact connection proves a physical outer transaction before the first helper savepoint.",
    "failure_rule": "Nested failure rolls back only the savepoint and propagates. A pre-COMMIT DBAPI refusal followed by caller rollback leaves zero target and unrelated rows. Ambiguous post-COMMIT or rollback failure invalidates the Session claim and requires reconstruction in a fresh Session; it is never converted into success.",
    "wrapper_rule": "OutboxRepository.writer remains a logical transaction-owner wrapper. Ledger write_snapshot must obtain direct shared-boundary proof before its nested snapshot/event write; no broad outbox rewrite is authorized."
  },
  "classified_seams": [
    {"path": "paper-trader/backend/app/core/strategy_admissions.py", "symbol": "put", "fact": "execution graph version plus receipt", "owner": "caller Session", "classification": "critical_authority_impacted"},
    {"path": "paper-trader/backend/research/domain/admissions.py", "symbol": "store_admission", "fact": "research graph version plus receipt", "owner": "caller Session", "classification": "critical_authority_impacted"},
    {"path": "paper-trader/backend/research/domain/strategy_admissions.py", "symbol": "persist_verified_dataset_authority", "fact": "typed segments, manifest, and dependency links", "owner": "caller Session", "classification": "critical_authority_impacted"},
    {"path": "paper-trader/backend/app/backtest/repository.py", "symbol": "append_claimed_result_batch", "fact": "lease heartbeat, results, and progress", "owner": "worker caller Session", "classification": "critical_fenced_result_impacted"},
    {"path": "paper-trader/backend/app/backtest/repository.py", "symbol": "complete_claim", "fact": "terminal state plus outbox event", "owner": "worker caller Session", "classification": "critical_terminal_outbox_impacted"},
    {"path": "paper-trader/backend/app/backtest/public_computation.py", "symbol": "put_immutable", "fact": "provenance-neutral public cache artifact", "owner": "publisher caller Session", "classification": "non_authoritative_persistence_impacted"},
    {"path": "paper-trader/backend/app/ledger/service.py", "symbol": "write_snapshot", "fact": "ledger snapshot plus outbox event", "owner": "outbox.writer caller unit", "classification": "critical_snapshot_outbox_impacted_transaction_hardening_only"}
  ],
  "evidence_requirements": {
    "cases": ["no prior SQL", "clean SELECT", "prior caller write", "explicit caller transaction", "externally owned root", "proved recursive nesting", "unproved external SQLite nesting refusal", "unrelated pending write", "flush failure", "DBAPI commit refusal then caller rollback", "rollback failure", "exact retry", "conflicting collision", "successful commit", "fresh-process reconstruction"],
    "dialects": ["SQLite compatibility", "disposable PostgreSQL 16"],
    "mutations": "At least eleven: physical-root establishment, marker cleanup, external-nesting refusal, no helper commit/rollback/close, and one direct adoption guard at each of seven seams.",
    "transitive": ["execution and research graph persistence", "dataset assessment authority", "backtest job claims", "public computation", "ledger routes", "portable outbox", "authority integration", "ADV-002", "ADV-003", "fresh 27-row matrix", "official review package", "final review"]
  },
  "pattern_disposition": "Exactly seven current begin_nested seams exist in backend/app and backend/research. All share the durability mechanism; six carry Critical multi-row or state/outbox facts and one is a non-authoritative cache with an impacted persistence contract. No other literal SAVEPOINT seam was found. Existing begin_reservation/locked_mutation callers are safe only when they establish the physical root before a savepoint.",
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/reports/phase4-source-coverage.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase4-authority-transaction-architecture-correction.md",
    "paper-trader/docs/agent/tasks/phase4-authority-transaction-correction.md",
    "paper-trader/docs/agent/tasks/phase4-adversarial-matrix-closure.md",
    "paper-trader/docs/agent/tasks/phase4-final-review-4.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-authority-transaction-architecture-correction"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "This capsule freezes architecture and pattern disposition only. It changes no product or test behavior and does not close ADV-003, the matrix, final review, or Phase 4.",
    "A fix limited to the two observed writers is insufficient until the same SAVEPOINT pattern is searched across the relevant foundation and every dependent claim is classified for revalidation.",
    "No local transaction evidence proves deployability, production capacity, provider correctness, runtime enablement, live authority, or release readiness."
  ],
  "owner_gates": [
    "Stop before any product, test, schema, migration, package, provider, frontend, deployment, credential, production, live, money, destructive, legal, or commercial change.",
    "Stop if a single helper cannot preserve caller ownership and unrelated pending work without hidden commits, dialect branching that changes semantics, or a second authority-persistence path.",
    "Stop if any classified Critical same-pattern seam requires product ownership outside the bounded implementation capsule; route an exact serial correction rather than defer it vaguely."
  ],
  "stop_conditions": [
    "Any current Phase 1-4 SAVEPOINT or begin_nested seam in the declared search surface remains unclassified.",
    "The contract permits release of a top-level SQLite SAVEPOINT to make authority rows durable before the caller commit, or permits a nested writer to commit/rollback unrelated caller work.",
    "SQLite and PostgreSQL semantics, collision/retry behavior, commit/flush failure, caller rollback, unrelated pending writes, and restart reconstruction lack direct implementation evidence requirements.",
    "Dependent evidence invalidation, matrix restart, protected hashes, source coverage, or programme seriality is incomplete."
  ],
  "deployment_impact": {
    "classification": "documentation-only-phase4-authority-transaction-architecture",
    "required_evidence": "Classify the correction as schema-free unless direct inspection proves otherwise; freeze SQLite and disposable PostgreSQL 16 transaction evidence; preserve migrations, configuration, services, providers, frontend, and production boundaries; route every affected persistence claim to exact current-byte revalidation."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The architect reproduces and explains why the two current authority writers can durably persist graph and receipt rows on SQLite when their top-level SAVEPOINT is released before a later caller commit failure.",
    "Every current begin_nested/SAVEPOINT use in the declared Phase 1-4 surface is listed with its fact type, transaction owner, dialect behavior, atomicity requirement, and disposition. Search results alone do not count; impacted claims name exact tests and evidence to rerun.",
    "One shared transaction-boundary contract ensures a real outer database transaction before any nested savepoint on SQLite, retains caller commit/rollback ownership, never commits unrelated pending work, and has equivalent PostgreSQL behavior.",
    "The implementation route proves clean-session, prior-read, prior-write, explicit caller transaction, nested caller, unrelated pending write, flush failure, DBAPI commit refusal, collision/retry, rollback, and fresh-process outcomes on both authority planes and both supported dialects where semantics differ.",
    "The implementation capsule has exact exclusive paths, one Terra-medium owner, at most one Luna-medium evidence-only child after freeze, reversible mutations with byte restoration, and no schema, migration, provider, frontend, deployment, production, live, or money authority.",
    "Design, plan, source coverage, deployability, defect patterns, matrix, final-review, CURRENT, and programme agree that the matrix restarts only after root acceptance of the bounded correction."
  ],
  "test_plan": [
    "Inspect current transaction and authority-persistence code only; run bounded read-only probes needed to classify DBAPI behavior, not product mutation or broad suites.",
    "Validate capsule JSON, programme order/dependencies, documentation consistency, source coverage, protected hashes, frontend exclusion, and scoped diff.",
    "Write an evidence-backed architecture report, complete seam-classification table, and exact implementation/evidence route under the ignored assignment directory."
  ],
  "architecture_evidence": {
    "verdict": "ARCHITECTURE_ACCEPTABLE",
    "report": ".agent/runs/phase4-authority-transaction-architecture-correction/owner/report.md",
    "report_sha256": "dd02e7818dd3fbfd6954f8d523c56972d980196c0a9691efa2ee74cbab661435",
    "seam_classification": ".agent/runs/phase4-authority-transaction-architecture-correction/owner/seam-classification.json",
    "seam_classification_sha256": "827189e8afdf1ea38977d5f058c3dea5820a8120ce0ee977adb62d0f1ceb7008",
    "adv_003_reproduction_sha256": "f679c41131baa684e592ab3faf66defd2d89e07bdbec612ec2c1bb921518c89a",
    "sqlite_probe_sha256": "89df20d773e5c8bc7c8b39ea38da783f3d23209f05e062fbc0bcfd5e3a40aac5",
    "postgresql_probe_sha256": "27d08d8a573094b4b1d83819f1a40db308d8da457fe43b8959df0f8a78668b42"
  },
  "review": {
    "required": false,
    "assignment_id": "phase4_authority_transaction_architect",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/reports/phase4-source-coverage.json",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase4-authority-transaction-architecture-correction.md",
      "paper-trader/docs/agent/tasks/phase4-authority-transaction-correction.md",
      "paper-trader/docs/agent/tasks/phase4-adversarial-matrix-closure.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-4.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase4-authority-transaction-architecture-correction/owner/report.md",
    "verdicts": [
      "ARCHITECTURE_ACCEPTABLE",
      "BLOCKED"
    ]
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 authority transaction architecture correction

ADV-003 exposed a dialect-sensitive authority-atomicity defect: releasing a
top-level SQLite SAVEPOINT can make graph and receipt rows durable even though
the caller has not successfully committed. This capsule freezes one safe
transaction-ownership contract, searches the pattern across the relevant
foundation, and routes exact revalidation. It does not patch product code.
