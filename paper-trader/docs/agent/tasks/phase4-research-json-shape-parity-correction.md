---
{
  "id": "phase4-research-json-shape-parity-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Close the research-plane JSON shape contract across SQLite and PostgreSQL with explicit object/array constraints and a restart-safe forward 0010 migration, without rewriting accepted 0009 history or weakening immutable authority facts.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized bounded work needed to finish Phase 4 and permits a fresh Sol-medium owner for repeated Critical architecture failures. Authority is limited to the research JSON constraint vocabulary, the forward 0010 repair, exact migration and lifecycle tests, Phase 4 design/plan/source/deployability accuracy, defect-pattern evidence, and ignored evidence. Accepted migration 0009 is immutable. Execution schemas, provider adapters, frontend, runtime enablement, deployment, credentials, production, live, and money authority remain closed.",
    "stopping_condition": "Complete only after every authoritative research JSON column has one explicit object or array shape contract with identical SQLite and PostgreSQL semantics; a forward 0010 migration upgrades exact 0009 state, resumes safely after interruption, preserves canonical bytes/rows/keys/foreign keys/indexes/immutability triggers, refuses arbitrary drift and destructive downgrade, and reaches exact head 0010; real typed dataset-manifest persistence and reload pass on SQLite and isolated PostgreSQL 16; the original integration path clears the research manifest constraint; all targeted compatibility, syntax, scoped diff, protected hash, mutation/restoration, and deployment-ledger checks pass. Stop with the goal active if closure requires changing accepted 0009 bytes, weakening JSON shape or authority validation, dropping data, touching execution schema, or changing any path outside this capsule.",
    "evidence_stopping_condition": "Retain the PostgreSQL counterexample, a complete ResearchBase JSON-constraint use-site ledger, dialect-compiled DDL comparisons, direct malformed/wrong-shape refusal matrices, SQLite and PostgreSQL 0009-to-0010 upgrade/restart/model-DDL parity, real typed manifest write/reload evidence, exact pre/post row and canonical-byte hashes, immutable trigger/index/foreign-key verification, killed-and-byte-restored mutations, final scoped hashes, and a concise owner report. Historical migration or slice PASS labels cannot substitute for current real-row evidence."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "postgresql",
    "migration",
    "json-shape",
    "fresh-process"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
        "11. Deployment contract",
        "13.1 Fact and equality matrix",
        "13.2 Persistence, reconstruction, and refusal",
        "13.5 Stale evidence and revalidation"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "8. Authority-correction serial route"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "Status and evidence rules",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact",
        "DP-006 — Database session timezone changed copied authority instants"
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
  "dependency_gate": "phase4-authority-timestamp-normalization-correction",
  "allowed_paths": [
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/0010_research_json_shape_parity.py",
    "paper-trader/backend/research_tests/test_phase4_research_json_shape_parity.py",
    "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/reports/phase4-source-coverage.json",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    ".agent/runs/phase4-research-json-shape-parity-correction"
  ],
  "nonclaims": [
    "This correction does not accept Phase 4, complete the authority integration gate, build a review package, or establish deployability, production readiness, provider correctness, frontend readiness, runtime authority, live authority, or money authority.",
    "Accepted research migration 0009 and its historical evidence remain immutable. The repair is forward-only migration 0010; no historical migration is rewritten or reinterpreted as having passed the corrected shape contract.",
    "No execution ORM, execution migration, application authority schema, provider adapter, broker, service, dependency, configuration, credential, infrastructure, runtime-enablement, frontend, deployment, or live path is authorized.",
    "The original integration command may prove only that this JSON-shape defect is cleared. A fresh evidence-only integration owner must still rerun the complete gate from the final corrected tree."
  ],
  "owner_gates": [
    "Stop if exact object/array shape parity cannot be implemented without weakening malformed-JSON refusal on either dialect.",
    "Stop if forward repair requires editing accepted migration 0009, dropping or rewriting canonical fact bytes, losing rows/keys/foreign keys/indexes/immutability triggers, or trusting the schema marker without exact DDL validation.",
    "Stop if a partial 0010 migration cannot distinguish exact old, exact new, and arbitrary drift states for restart-safe recovery.",
    "Stop if closure crosses execution schema, provider, runtime, frontend, deployment, credential, production, live, or money boundaries."
  ],
  "stop_conditions": [
    "Any ResearchBase JSON constraint still uses an ambiguous helper whose dialect implementations enforce different shapes, or any object/array field accepts malformed JSON or the wrong top-level JSON type.",
    "A real research dataset-manifest/2 row fails on either supported database, or object-valued graph/admission/legacy-manifest fields do not receive the same strict shape contract on both dialects.",
    "Fresh 0010, exact 0009-to-0010 upgrade, interrupted restart, model-DDL parity, row/byte preservation, immutable trigger/index/foreign-key checks, arbitrary-drift refusal, or destructive-downgrade refusal lacks direct SQLite and PostgreSQL 16 evidence.",
    "The original integration path still fails at a JSON-shape constraint, a required mutation survives, restored bytes differ, protected hashes change, or scoped-path checks fail."
  ],
  "deployment_impact": {
    "classification": "additive-research-schema-json-shape-parity-repair",
    "required_evidence": "Forward research head 0010 only. Prove fresh install and exact 0009-to-0010 upgrade/restart on SQLite and isolated PostgreSQL 16; preserve every row, canonical byte string, address, key, foreign key, index, and immutability trigger; refuse arbitrary DDL drift and destructive downgrade. This is local migration evidence only and grants no deployability or production claim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "searched_surfaces": [
    "every _JsonIsValid definition and use in research/domain/models.py",
    "object-valued research_ir_v2_graph_versions.artifact_json",
    "object-valued research_strategy_admission.artifact_json",
    "object-valued research_dataset_manifests.manifest_json",
    "array-valued research_dataset_manifests_v2 segment, instrument, field, gap, and dependency JSON columns",
    "research migration exact-schema, restart, immutability, foreign-key, index, marker, and PostgreSQL validation paths",
    "real persist_verified_dataset_authority and fresh reload path"
  ],
  "acceptance": [
    "replace the ambiguous JSON helper with explicit object and array contracts; SQLite validates syntax and exact json_type without evaluating a malformed document, while PostgreSQL validates exact jsonb_typeof; every use site is classified and no ambiguous helper remains",
    "the three object-valued fields accept only canonical JSON objects and the five dataset-manifest/2 collection fields accept only canonical JSON arrays; malformed JSON, null, scalar, string, and opposite-shape substitutions refuse on both dialects",
    "new forward migration 0010 repairs only exact accepted 0009 constraints, supports exact-new idempotence and partial-restart recovery, refuses arbitrary old/new hybrid or unrelated drift, and never edits the accepted 0009 migration module",
    "fresh and 0009-to-0010 SQLite and PostgreSQL 16 lifecycles preserve exact rows, canonical bytes, addresses, composite keys, foreign keys, indexes, immutable triggers, collision refusal, and model/metadata DDL parity at exact head 0010",
    "real typed dataset segment/manifest/link persistence survives process death and reload on both dialects; exact object and array copied JSON values reconstruct; every wrong-shape or malformed substitution fails through a real database constraint or loader",
    "the preserved original integration selector clears the research dataset-manifest JSON constraint and any later failure is recorded as a separate gate rather than hidden or claimed closed",
    "reversible mutations prove object/array separation and 0009-to-0010 repair validation are causally required; every mutated product/test byte is restored exactly",
    "DP-007 records the cross-dialect JSON-shape split, full searched surface, prevention invariant, permanent real-row regression, transitive invalidation, severity, closure status, owner, and evidence without overstating Phase 4 or deployment readiness"
  ],
  "test_plan": [
    "Use the project backend virtualenv and `.codex/scripts/run_logged.py`; preserve the pre-edit PostgreSQL integration counterexample before changing product bytes.",
    "Compile every named constraint for SQLite and PostgreSQL, then execute direct real-table object/array acceptance and malformed/opposite-shape refusal matrices on both databases.",
    "Create exact 0009 fixtures from accepted historical metadata, persist representative graph, admission, legacy manifest, typed segment, typed manifest, and link rows, then run 0010 and verify byte-for-byte preservation and fresh-process reload.",
    "Interrupt 0010 at each structural boundary needed to prove restart safety; rerun from exact-old/exact-new/partial states and refuse deliberately drifted constraints or marker-only claims.",
    "Run only the focused JSON-shape, research migration, real typed-manifest, and preserved integration selector needed for causal evidence; do not run broad backend or research suites for confidence.",
    "Kill and byte-restore mutations that collapse object/array helpers or bypass migration old/new-shape validation; rerun focused SQLite and PostgreSQL selectors and compare final hashes."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_research_json_shape_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/research/domain/models.py",
      "paper-trader/backend/research/domain/migrate.py",
      "paper-trader/backend/research/domain/migrations/0010_research_json_shape_parity.py",
      "paper-trader/backend/research_tests/test_phase4_research_json_shape_parity.py",
      "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/reports/phase4-source-coverage.json",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md"
    ],
    "exclude_paths": [
      "paper-trader/backend/research/domain/migrations/0009_phase4_dataset_authority.py"
    ],
    "output": ".agent/runs/phase4-research-json-shape-parity-correction/owner/report.md",
    "verdicts": ["CORRECTED"]
  }
}
---

# Phase 4 research JSON-shape parity correction

The timestamp correction exposed the next real PostgreSQL seam. One research
constraint helper means only “valid JSON” on SQLite but means “JSON object” on
PostgreSQL. It is attached to three object-valued fields and five array-valued
typed-manifest fields. PostgreSQL therefore rejects a legitimate persisted
dataset manifest while SQLite admits shapes that the model does not intend.

Treat this as a foundation constraint-vocabulary defect, not a one-column
fixture failure. Classify every use site, enforce the same exact top-level shape
on both dialects, and repair accepted research head `0009` through forward
migration `0010`. Preserve all authoritative bytes and immutable history. The
full Phase 4 integration gate remains blocked until this capsule is accepted.
