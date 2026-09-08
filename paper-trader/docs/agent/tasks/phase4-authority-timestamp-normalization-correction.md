---
{
  "id": "phase4-authority-timestamp-normalization-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Define and apply one database-neutral UTC timestamp representation for every Phase 4 typed-authority copied SQL column so SQLite and PostgreSQL reconstruct the same canonical facts without changing their identity.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized bounded work needed to finish Phase 4 and permits a fresh Sol-medium owner for repeated Critical architecture failures. Authority is limited to the shared timestamp representation, the named Phase 4 typed-authority writers/loaders and overlap predicate, one focused regression module, defect/deployability accuracy, and ignored evidence. Frontend, provider adapters, schema, migrations, services, configuration, runtime enablement, deployment, credentials, production, live, and money authority remain closed.",
    "stopping_condition": "Complete only after one shared helper converts every canonical aware instant to a UTC-naive SQL value and separately rejects malformed loaded SQL timestamps; every named copied-timestamp writer, loader comparison, and alias overlap predicate uses that helper; canonical documents and content addresses remain byte-identical; SQLite and disposable PostgreSQL 16 configured to Asia/Kolkata pass real fresh-process reloads for every authority family and all nine dataset-dependency tables; one-hour copied-column and canonical-document substitutions refuse; the original raw-segment integration path passes; and syntax, scoped diff, protected hashes, mutation/restoration, and deployment-ledger checks pass. Stop with the goal active if closure requires a schema or migration change, a canonical identity change, a compatibility downgrade, a provider/runtime change, or any path outside this capsule.",
    "evidence_stopping_condition": "Retain the pre-edit PostgreSQL counterexample, an exact searched-surface ledger, SQLite/PostgreSQL canonical-byte and address parity, SHOW TIMEZONE evidence, real process-death/reload evidence, direct copied-column and canonical-document tamper refusals for every listed family and each dataset table, byte-restored mutation evidence for the shared conversion and loaded-value guard, final scoped hashes, and a concise owner report. Historical SQLite or capsule PASS labels cannot substitute for current PostgreSQL evidence."
  },
  "risk_tags": [
    "critical",
    "authority",
    "postgresql",
    "timestamp",
    "fresh-process"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "9. Ownership, authority, and persistence",
        "11. Deployment contract",
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
        "Status and evidence rules",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-004 — Immutable envelope over mutable or time-incoherent facts",
        "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact"
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
  "dependency_gate": "phase4-capability-assessment-receipt-correction",
  "allowed_paths": [
    "paper-trader/backend/app/market_truth/temporal.py",
    "paper-trader/backend/app/market_truth/identity.py",
    "paper-trader/backend/app/market_truth/authority.py",
    "paper-trader/backend/app/market_data/authority.py",
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/app/market_data/dataset_authority.py",
    "paper-trader/backend/tests/test_phase4_authority_timestamp_normalization.py",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    ".agent/runs/phase4-authority-timestamp-normalization-correction"
  ],
  "nonclaims": [
    "This correction does not accept Phase 4, complete the authority integration gate, build a review package, or establish deployability, production readiness, provider correctness, runtime authority, frontend readiness, money authority, or live authority.",
    "Canonical typed documents, their UTC-aware timestamp strings, and every existing content address remain unchanged. Only copied SQL timestamp representation and verification are hardened.",
    "No ORM model, DDL, migration, backfill, dependency, configuration, service, provider adapter, broker, credential, infrastructure, or runtime-enablement change is authorized.",
    "The stopped integration runs and their partial ADV/SQLite evidence remain historical only; a fresh integration owner must rerun the full gate after this correction."
  ],
  "owner_gates": [
    "Stop if one shared UTC-to-SQL representation cannot serve all listed typed-authority seams without changing canonical identity.",
    "Stop if PostgreSQL correctness requires changing DateTime columns, migration heads, DDL, or existing persisted canonical bytes.",
    "Stop if a loader would need to accept ambiguous aware SQL rows, reinterpret local wall time, or silently repair malformed persisted values.",
    "Stop if closure crosses provider, runtime, frontend, deployment, credential, production, live, or money boundaries."
  ],
  "stop_conditions": [
    "Any listed writer still sends an aware datetime directly to a timezone-naive SQL column, any listed loader strips tzinfo without first normalizing the canonical instant to UTC, or any overlap query uses a different representation.",
    "Provider contract, alias, truth snapshot, conformance, capability profile or assessment, provider or normalized observation, or any of the nine dataset-dependency table types lacks direct SQLite and non-UTC PostgreSQL evidence.",
    "A copied SQL timestamp can differ from canonical bytes by one hour without refusal, canonical JSON can change while copied columns remain unchanged without refusal, or canonical addresses differ across SQLite and PostgreSQL.",
    "The original raw-segment path still fails, a required mutation survives, restored bytes differ, protected hashes change, or scoped-path checks fail."
  ],
  "deployment_impact": {
    "classification": "schema-free-cross-database-authority-timestamp-hardening",
    "required_evidence": "No schema, migration head, dependency, configuration, service, provider, or frontend change. Prove identical canonical bytes and addresses on SQLite and isolated PostgreSQL 16 with server timezone Asia/Kolkata; prove process-death reload and tamper refusal across every named typed-authority family; record that this is local compatibility evidence only and grants no deployability or production claim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "searched_surfaces": [
    "ProviderContract effective_from/effective_to writes, reload comparisons, and raw-segment dependency reload",
    "ProviderInstrumentAlias effective_from/effective_to writes, overlap predicates, and reload comparisons",
    "MarketTruthSnapshot knowledge_cutoff/effective_from/effective_to",
    "ProviderConformance observed_from/observed_to",
    "CapabilityProfile observed_at/expires_at",
    "CapabilityAssessment assessed_at",
    "ProviderObservation event_time/available_at",
    "NormalizedMarketObservation event_time/available_at",
    "all nine dataset-dependency authority tables' recorded_at copied columns"
  ],
  "acceptance": [
    "one shared helper defines aware canonical instant to UTC-naive SQL storage, nullable handling, and fail-closed validation of loaded SQL-naive values; duplicate private conversion rules are removed from the searched surfaces",
    "all searched writers, copied-column comparisons, and temporal overlap predicates use the same representation while canonical fact serialization and addresses remain byte-identical",
    "SQLite and disposable PostgreSQL 16 under an explicitly asserted Asia/Kolkata server timezone persist, survive process death, reload, and reconstruct fixtures whose source timestamps include non-zero positive and negative UTC offsets",
    "provider contract, alias, truth snapshot, conformance, profile, assessment, provider observation, normalized observation, and each of the nine dataset-dependency table types have direct current-byte parity and refusal evidence",
    "changing any copied timestamp by one hour while canonical JSON is unchanged refuses; changing canonical JSON while copied columns are unchanged refuses; malformed aware SQL values do not pass as valid timezone-naive rows",
    "the pre-edit failing raw-segment path passes before the downstream integration seam, and reversible mutations prove the shared normalization and loaded-value guard are causally required",
    "DP-006 records the pattern, prevention invariant, searched surfaces, permanent regression, transitive invalidation, severity, closure status, owner, and evidence without overstating Phase 4 or deployment readiness"
  ],
  "test_plan": [
    "Use the project backend virtualenv and `.codex/scripts/run_logged.py`; begin with a preserved pre-edit PostgreSQL counterexample and exact SHOW TIMEZONE output.",
    "Run only the new focused timestamp contract plus the smallest existing provider/raw-segment and typed-authority selectors needed to prove compatibility; do not run a broad backend or research suite for confidence.",
    "Run a real fresh-interpreter SQLite lifecycle and an isolated PostgreSQL 16 lifecycle with separate execution/research databases where needed; compare canonical bytes and addresses exactly.",
    "Exercise one-hour copied-column and canonical-document tampering through the real loaders for every authority family and each of the nine dataset tables; retain a row-addressed evidence ledger.",
    "Kill and byte-restore mutations that remove UTC conversion, accept an aware loaded SQL value, or bypass copied-time comparison; rerun the focused selector and compare final hashes."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_authority_timestamp_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/market_truth/temporal.py",
      "paper-trader/backend/app/market_truth/identity.py",
      "paper-trader/backend/app/market_truth/authority.py",
      "paper-trader/backend/app/market_data/authority.py",
      "paper-trader/backend/app/market_data/observations.py",
      "paper-trader/backend/app/market_data/dataset_authority.py",
      "paper-trader/backend/tests/test_phase4_authority_timestamp_normalization.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-authority-timestamp-normalization-correction/owner/report.md",
    "verdicts": ["CORRECTED"]
  }
}
---

# Phase 4 authority timestamp normalization correction

The second fresh authority-integration owner stopped on a PostgreSQL 16
counterexample that SQLite masked. Canonical facts use UTC-aware instants, while
their duplicated SQL columns are timezone-naive. Some writers passed aware
values directly to PostgreSQL and some loaders removed timezone information
without first converting the canonical instant to UTC. Under a non-UTC server
timezone this changed wall-clock values and made legitimate authoritative facts
fail reconstruction.

Treat the first provider-contract failure as the earliest symptom, not the full
defect. Search and harden every listed Phase 4 copied-timestamp seam through one
shared representation policy. Preserve canonical bytes and addresses exactly.
Do not change schemas or relax authority checks. The correction is complete
only when real non-UTC PostgreSQL and SQLite lifecycles agree and deliberate
timestamp substitutions fail through the real loaders.
