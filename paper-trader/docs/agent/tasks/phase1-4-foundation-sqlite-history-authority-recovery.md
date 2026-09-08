---
{
  "id": "phase1-4-foundation-sqlite-history-authority-recovery",
  "phase": "interphase-4-5",
  "status": "completed",
  "result": {
    "verdict": "RECOVERY_ARCHITECTURE_ACCEPTABLE",
    "activation": "pending root acceptance",
    "catalog_digest": "bad35ce3288953c8b26ffdc0ea1906617d305b3f4a82da1d953f52070bf54635",
    "ledger_sha256": "874cc53fc1e455428915359a1253e225467bbe5d3057cd94abd153b3f4c9e7b8",
    "source_closure_sha256": "15e4882d086d88ea6fe9afdde11d9c688cf2c7f4b36981e7c6b40d20e1832ea9",
    "support_matrix_sha256": "63aa4c648d5a20298671810012dabaee690f886c52d562cb0dcc05cd270fd8e0",
    "supported_starts": ["empty", "exact_or_enumerated_five_guard_0010", "exact_0011"],
    "unsupported_starts": ["unversioned", "0001-0009", "unknown_or_drifted"],
    "user_gate": "inactive on bounded repository evidence; activate root and user gate only on affirmative contrary stranding evidence"
  },
  "goal": "Resolve the missing immutable SQLite catalog authority for the research migration chain and produce the smallest honest supported-start matrix before projection implementation resumes.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "Root accepted the prior state-contract owner's evidence-backed stop, not its provisional matrix. This capsule authorizes one fresh Sol-medium architecture owner to recover exact SQLite source authority or propose an explicit fail-closed matrix revision in documentation and evidence only. Product, tests, migrations, CURRENT, PROGRAMME, review packages, deployment, production, live, and money paths are read-only.",
    "stopping_condition": "Complete only when every SQLite start from empty and unversioned through 0011 has an exact authority disposition; each supported start has complete transitive catalog-source closure and an executable preservation route to one immutable 0011 target; every unsupported start has pre-write refusal and operator handling; release or promise stranding has been audited; and all affected downstream contracts agree. Return BLOCKED if any supported catalog or direct transition still needs current-metadata inference, invented history, unavailable product facts, destructive repair, or an unresolved owner or user gate."
  },
  "risk_tags": [
    "critical",
    "architecture-recovery",
    "research-migration",
    "sqlite",
    "historical-schema-authority",
    "data-preservation",
    "deployability",
    "research-integrity"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": ["14. Foundation migration and market-number correction contract"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": ["9. Foundation migration and numeric correction route"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Foundation migration and numeric correction", "Foundation blockers"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-state-contract-recovery.md",
      "sections": ["Phase 1-4 foundation research-migration state-contract recovery"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "sections": ["Phase 1-4 foundation research migration projection correction"]
    }
  ],
  "dependency_gate": "sqlite-history-authority-blocker-acceptance",
  "trigger_evidence": {
    "root_blocker_acceptance": ".agent/runs/phase1-4-foundation-critical-closure/sqlite-history-authority-blocker-acceptance.json",
    "root_blocker_acceptance_sha256": "bb786b10e44a19079cd72261cc8a543c06888876bf16ab20e3400f646be96b8c",
    "state_contract_report": ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery/owner/report.md",
    "state_contract_report_sha256": "a7a357fbc0958cba6e1cf238994bc76d8fdbb5b5b238cb9930d6b6e1c4061bbb",
    "state_contract_manifest_sha256": "7e3411f08551dac9e8afbb4303f6f935e245ec13f4f52dd0fe5a8e3e70cbf81d",
    "blocked_matrix_sha256": "1e8a22ad55e37514c7a8ce38327e2e4c21a4f078332438146492338ca5acc5a4",
    "claim_invalidation_map_sha256": "e3f5f6ca1ae9d9f22e0dad1bad68653cdb2ce65d1939b77491609d07014b50f9",
    "sqlite_authority_audit_sha256": "4579ee1bec2e72a2accd5a3d424fce9cb12d56e7b4a14202778aea4d69a8634d",
    "release_stranding_audit_sha256": "1b5e225b5f7377f91344944d1747c0c645ab0a6db36b88f80aa0b47017f3b021",
    "audit_freeze_sha256": "1e751194efbbd5048807418ccfb22a69774431bbe00b03a2565e6aadfc277abf"
  },
  "architecture_questions": [
    "For empty, unversioned, every marker 0001 through 0010, and target 0011, which exact commit, accepted current-byte artifact, migration module, schema compiler, import dependency, or explicit declaration is the sole SQLite catalog authority?",
    "Do the commit-backed 0001-0005 snapshots include the full transitive import and SQLAlchemy dialect-compilation closure needed to reproduce exact tables, indexes, constraints, triggers, affinities, defaults, and marker behavior, or are any of those starts also unsupported?",
    "Can any supported 0001-0005 database transition directly to the current target while preserving arbitrary contract-valid rows, keys, owners, textual JSON and BLOB bytes, sequence state, and permitted legacy values without pretending that untracked 0006-0009 files were historical states?",
    "What exact current-byte declarations freeze the accepted 0010 catalog, and where must the sole immutable 0011 = 0010 plus guard-only target and delta live so projection builders and runtime consume one authority?",
    "Which markers must refuse before schema, row, sequence, trigger, or marker writes, what stable refusal codes apply, and what read-only operator procedure preserves the original database?",
    "Would the smallest support revision strand any released, deployed, production, supported, or externally promised SQLite database, and what exact root or user gate follows from that evidence?",
    "Which provisional design, plan, deployability, defect-pattern, projection, runtime, integration, transitive, and review claims must be accepted, replaced, or rejected before implementation may restart?"
  ],
  "required_decisions": {
    "version_ledger": "Emit a machine-readable ledger for empty, unversioned, 0001-0011. Each row records status, exact source bytes and hashes, complete transitive compiler/import closure, full durable catalog inventory, allowed user and sequence state, derivation or transition route, and independent constructibility evidence, or an explicit unsupported reason.",
    "source_closure": "For commit-backed candidates, prove every imported schema and migration dependency at the same immutable repository state. A models.py, migrate.py, and version-file trio is insufficient when a type compiler, helper, registry, dialect hook, or imported declaration can change generated SQLite DDL or semantics.",
    "current_and_target_authority": "Bind accepted current 0010 only to exact frozen current bytes and define the single product-owned 0011 catalog plus guard-only delta contract and its future implementation path. Neither a test builder nor runtime migration may become a second catalog authority.",
    "direct_transition_contracts": "Retain any 0001-0005 start only if an exact direct-to-0011 contract maps every old table, column, key, owner relation, affinity, stored byte, sequence, new table, backfill, permitted legacy state, trigger, and marker operation and proves arbitrary contract-valid U/Q preservation and restart safety.",
    "support_matrix": "Return RECOVERY_ARCHITECTURE_ACCEPTABLE only with a smallest evidence-backed matrix. Unsupported unversioned or 0006-0009 starts remain refused; 0001-0005 may remain only when source closure and direct-transition proof pass; empty, current 0010, and target 0011 receive no credit until their exact construction or no-op routes are closed.",
    "refusal_and_operator_contract": "Specify read-only preflight, stable refusal precedence and codes, zero-write digest proof, backup and isolated diagnostic handling, and prohibition on marker rewrites, auto-rebuild, or destructive repair for every unsupported or drifted start.",
    "stranding_and_deployability": "Repeat the bounded repository release and promise audit against the proposed matrix. If contrary external facts appear, stop for root and user direction. Otherwise state the local compatibility change, backup/restore and production-shaped rehearsal obligations, and why architecture probes establish no release or production readiness.",
    "downstream_route": "Amend all affected provisional documents and serial capsules so a fresh projection owner receives a complete contract. Product implementation remains paused pending root acceptance of the recovery report, manifest, ledger, support matrix, exact capsule hashes, audit freeze, and protected hashes."
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery/foundation_sqlite_history_architect/sqlite-history-authority-ledger.json",
    ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery/foundation_sqlite_history_architect/sqlite-source-closure-map.json",
    ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery/foundation_sqlite_history_architect/sqlite-support-matrix.json"
  ],
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-sqlite-history-authority-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-state-contract-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-review.md",
    ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-postgresql-history-authority-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-correction",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery",
    ".agent/review-package.json",
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md"
  ],
  "acceptance": [
    "The owner verifies the root blocker record, blocked report and manifest, matrix, claim map, authority audit, audit freeze, accepted PostgreSQL ledger, retained 0007/0008 hashes, current 0010 candidate hashes, and protected files before changing documentation.",
    "The final version ledger covers empty, unversioned, 0001-0011 with no implicit status, source, compiler/import dependency, catalog fact, data or sequence domain, transition, refusal, or evidence claim.",
    "Every supported commit-backed start has complete transitive source closure at one immutable repository state; no current worktree import or later dependency can influence its catalog construction.",
    "Every supported direct transition has an exact table/column/key/owner/affinity/default/constraint/index/trigger/sequence/marker/backfill map and preserves arbitrary contract-valid rows and exact textual JSON and BLOB bytes through interruption and restart.",
    "The current 0010 authority and sole 0011 target/delta are exact, product-owned, independently constructible, and consumed by future builders and runtime without creating another schema authority.",
    "Unversioned, 0006-0009, and every other unproved or drifted start refuse in read-only preflight before any schema, row, sequence, trigger, or marker write and leave a complete digest unchanged.",
    "No current ResearchBase.metadata subtraction, current-head rewind, later dump, cross-dialect translation, synthetic historical fact, semantic-only JSON comparison, or marker rewrite receives evidence credit.",
    "The release and promise audit binds the proposed matrix. A user gate is activated only by affirmative released, deployed, production, supported-database, customer, or external-promise evidence; the bounded repository nonfinding is not presented as external reality.",
    "Evidence-only SQLite probes independently construct every proposed supported start and exercise direct transition or no-op/refusal seams. These probes remain architecture feasibility evidence and do not modify or accept product or tests.",
    "Design, plan, deployability, defect-pattern guidance, state-contract disposition, projection, runtime, integration, transitive, and critical-review capsules use one support matrix and preserve their serial ownership and root-acceptance gates.",
    "Capsule JSON, repository architecture, scoped diff, immutable audit, protected and frozen hashes, product/test no-change audit, machine outputs, and evidence-manifest attestation pass on final bytes."
  ],
  "test_plan": [
    "Use git log, git show, git object hashes, exact current hashes, import tracing, and SQLite DDL compilation in ignored probes. Never checkout, stage, rewrite, or copy historical bytes into the dirty worktree.",
    "For each candidate supported start, construct the catalog from its declared closed source set in an isolated temporary environment and compare complete sqlite_schema, PRAGMA, trigger, index, affinity, default, marker, and sequence inventories with the ledger.",
    "For each candidate direct transition, use at least two materially different contract-valid corpora, nontrivial key and owner graphs, textual Unicode JSON, BLOB bytes, permitted legacy values, and distinct sequence states; prove exact before/after preservation, interruption, restart, and targeted refusal.",
    "For unsupported and drifted starts, mutate catalog, marker, guard inventory, sequence state, and data predicates independently; prove stable refusal precedence and complete preflight digest equality.",
    "Validate final documentation and capsule hashes, repository architecture, exact allowed scope, audit freeze, protected and retained inputs, product/test no-change, and evidence manifest."
  ],
  "owner_gates": [
    "Stop and return BLOCKED if any proposed supported catalog, compiler/import dependency, direct transition, stored-byte rule, key or owner mapping, sequence rule, target 0011 fact, or restart boundary requires unavailable or invented authority.",
    "Stop for root and user direction if evidence shows the proposed matrix could strand a released, deployed, production, supported, customer, or externally promised SQLite database state.",
    "Stop before product, test, schema, migration, package, dependency, configuration, service, provider, frontend, CURRENT, PROGRAMME, review-package, credential, deployment, production-data, destructive, runtime, live, order, or money changes.",
    "Stop if the design silently widens support, converts a refusal into destructive rebuild, weakens exact catalog or byte preservation, authorizes current-metadata inference, or lets an implementation or fixture define historical authority."
  ],
  "stop_conditions": [
    "Any ledger row, source-closure edge, supported-start predicate, direct-transition mapping, refusal code, operator action, affected claim, downstream owner, or acceptance gate remains implicit.",
    "A proposed matrix revision lacks exact release and promise evidence, conditional user-gate handling, pre-write refusal, or root acceptance requirements.",
    "The owner begins implementation, accepts retained 0007/0008, modifies product or tests, self-accepts provisional documentation, or claims deployability, production readiness, or foundation closure."
  ],
  "deployment_impact": {
    "classification": "architecture-only; downstream migration support revision and forward migration required",
    "highest_claim": "an exact and implementable SQLite historical-authority and supported-start contract",
    "unchanged": ["product", "tests", "runtime behavior", "research head", "dependencies", "configuration", "services", "providers", "frontend", "deployment", "production", "live authority", "money authority"],
    "downstream_gates": ["root acceptance of support matrix", "fresh projection correction", "fresh runtime correction", "fresh evidence integration", "numeric correction", "transitive revalidation", "critical review", "production-shaped migration rehearsal", "release deployability"]
  },
  "nonclaims": [
    "This capsule changes no product, test, schema, migration, runtime, provider, frontend, deployment, production, live, order, or money behavior.",
    "Commit-addressable source bytes do not by themselves prove complete compiler/import closure or a safe direct migration from that state.",
    "Architecture probes and a narrowed local matrix do not prove a production upgrade, release compatibility, deployment readiness, or facts outside the checkout.",
    "Accepted architecture would not accept retained 0007/0008 edits, paused projection work, runtime, integration, numeric correction, transitive evidence, foundation closure, or Phase 5."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "routing_basis": "Fresh bounded architecture recovery after an evidence-backed schema-authority owner gate; the primary owner's Ultra exception does not propagate."
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_sqlite_history_architect",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-sqlite-history-authority-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-state-contract-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
      ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery"
    ],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", ".agent/review-package.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
    "output": ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery/owner/report.md",
    "verdicts": ["RECOVERY_ARCHITECTURE_ACCEPTABLE", "BLOCKED"]
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 1-4 foundation SQLite history-authority recovery

The previous state-contract owner correctly separated immutable catalog history
from parameterized user data, then found that the repository cannot reproduce
several SQLite catalogs it had planned to support. This recovery must turn that
stop into an exact support decision. It may prove a start from immutable closed
sources or refuse it before writes. It cannot infer history from current model
metadata, resume implementation, or grant migration acceptance.
