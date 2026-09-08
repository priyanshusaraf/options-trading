---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-session-handle-integrated-runtime-recovery-replan",
  "phase": "v0",
  "status": "accepted_read_only_replan",
  "kind": "critical_read_only_runtime_evidence_recovery_replan",
  "goal": "Replan the exhausted session-handle review into one fresh runtime-integration successor that proves the accepted UUID handle through the actual OAuth initiation/callback/revocation and init_db bootstrap transaction entry points.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision freezes exact real-entry-point tests, ownership, failure mutations, supported-database evidence, reviewer and UUID/shared resume gates for V0-SRH-CR-001 and V0-SRH-CR-003."},
  "risk_tags": ["critical", "auth", "session", "oauth", "bootstrap", "identity", "tenancy", "privacy", "restart"],
  "depends_on": ["strategy-os-v0-session-record-handle-reference-correction"],
  "dependency_gate": {"first_package_sha256": "364d4ee6814a53c1f286b5cbc29a3effc2fa91bbb5094fb13765fcba88370162", "first_verdict_sha256": "b1f12b9f8cab1387db0fbb65ae011277640e191a45bf2ab6bc024b592e043090", "corrected_package_sha256": "4ede12641481930c2bd2a323bd466edba1ad37076f817a285c38629fde83799d", "recheck_verdict_sha256": "aa25218246325b436594b25c6ad070905d6261bbfea64fbb504f9b66d4d56d54", "closed": ["V0-SRH-CR-002"], "open": ["V0-SRH-CR-001", "V0-SRH-CR-003"], "policy": "The UUID source decision stays frozen. Do not accept direct ORM or manually assembled transaction evidence in place of the actual protected runtime entry points."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-session-record-handle-reference-correction/review/verdict.json", "sections": ["findings", "evidence_gaps", "verdict"]},
    {"path": ".agent/runs/strategy-os-v0-session-record-handle-reference-correction/review/recheck-verdict.json", "sections": ["findings", "closed_findings", "open_findings", "verdict"]},
    {"path": ".agent/runs/strategy-os-v0-session-record-handle-reference-correction/review-package-correction.json", "sections": ["all"]},
    {"path": "paper-trader/backend/app/api/connection_routes.py", "sections": ["_start_oauth", "_consume_callback_state", "oauth_callback", "connection revocation"]},
    {"path": "paper-trader/backend/app/db/session.py", "sections": ["init_db", "bootstrap_legacy_session caller transaction"]},
    {"path": "paper-trader/backend/app/api/principal.py", "sections": ["issue_user_session", "bootstrap_legacy_session", "resolve_principal"]},
    {"path": "paper-trader/backend/AGENTS.md", "sections": ["Backend execution rules"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery-replan.md", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery-replan.md", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Freeze the accepted principal.py UUID handle and 256-bit bearer bytes. Map the exact public/internal OAuth initiation, durable state, callback consumption, credential update, session revocation and restart entry points without editing them.",
    "Require the successor to originate a session through the real issuer, invoke the actual _start_oauth or route, inspect the exact persisted OAuthCallbackState handle/user/tenant, exercise actual callback consumption and prove revoked/expired/replaced sessions fail through the real runtime predicates without provider network.",
    "Map the actual init_db transaction, including legacy bootstrap plus broker account, deployment/outbox, catalogue, capital and universe seeds. Require an injected UUID collision at bootstrap to roll back that complete caller transaction, preserve the pre-existing session/digest/owner and succeed only after real init_db restart/retry.",
    "Define safe mock adapter/vault fixtures so OAuth semantics are exercised without broker credentials, provider network, live execution or plaintext evidence. Direct ORM insertion and manual root assembly are insufficient.",
    "Freeze exact test/evidence paths, SQLite and isolated PostgreSQL 16 matrices, privacy/tenant/restart/collision mutations, one fresh Critical review and predecessor/shared resume hashes.",
    "Preserve V0-SRH-CR-002 closure; do not rerun or rewrite accepted source merely to replace missing runtime evidence."
  ],
  "acceptance": [
    "One successor invokes actual protected OAuth and init_db entry points while writing only a dedicated integration test/evidence package; no protected runtime source changes are needed.",
    "OAuth proof covers producer-to-state-to-callback/revocation/restart with exact generated handle/user/tenant on SQLite and PostgreSQL 16 and zero provider network.",
    "init_db proof covers the complete caller transaction collision rollback, preservation and restart/retry on both databases, including all companion seeds named by the reviewer.",
    "Successor freezes mutations that make direct-insert/manual-transaction shortcuts fail, one independent Critical review, protected hashes and UUID/shared resume gates."
  ],
  "test_plan": ["Read-only runtime entry-point/caller/fixture/transaction inventory; identify exact safe hooks without changing production code; seal fresh successor and evidence matrix. Implementation belongs only to successor."],
  "risk_classification": {"tier": "Critical", "reason": "OAuth capability and init_db transactions bind session identity to credentials and durable authority; indirect fixtures can miss production-path failures."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_session_handle_integrated_runtime_recovery_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-runtime-evidence-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery-replan.md", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan"], "output": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_session_handle_integrated_runtime_recovery_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only replan after exhausted Critical review; fresh implementation receives independent Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-session-handle-integrated-runtime-recovery-replan.md", ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/decision.json", "verdicts": ["OAUTH_RUNTIME", "INIT_DB_TRANSACTION", "EVIDENCE", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No product/test/schema/migration/frontend edit, provider network/credentials, live/money, session/data rewrite, commit, deploy, UUID/shared resume or V0 claim."],
  "stop_conditions": ["Actual entry-point proof requires provider network, real credentials, destructive non-temporary state or production access.", "Protected runtime source has a new semantic defect rather than an evidence gap.", "Shared source receives concurrent ownership."],
  "deployment_impact": {"classification": "none for read-only replan; successor evidence-only unless a new source defect appears", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "decision": "KEEP + HARDEN IN ONE FRESH EVIDENCE-ONLY SUCCESSOR",
  "delivery_status": "accepted_read_only_replan",
  "output_artifacts": {
    "decision": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/decision.json", "sha256": "0b8d3fcbd7788d1c4ae3f7186cdf66cb76c75f35f6ec86d82067ee23bbb2d4bd"},
    "entrypoint_evidence": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/entrypoint-evidence.json", "sha256": "27ea66fefd50b68e7f968cfc07cde55380a41f2da13065d67cfa3ee330cddea3"},
    "successor_capsule": {"id": "strategy-os-v0-session-handle-integrated-runtime-recovery", "path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/successor-correction-capsule.md", "sha256": "6bc35eaaaea1b6710d16c707fe3c149b9784999e248bd93343cebbda8a420a81"},
    "orientation": {"path": ".agent/runs/strategy-os-v0-session-handle-integrated-runtime-recovery-replan/orientation-receipt.md", "sha256": "ddc6b5d6127a9517d253e8f22153401cbe6a5739c4b72a6672100e318c431d8a"}
  },
  "nonclaims": ["No runtime evidence correction, source change, session correction acceptance, UUID/shared resume, provider, deployment, release readiness or V0 completion."]
}
---

# Session-handle integrated runtime recovery replan

Replace indirect fixtures with direct proof through the protected OAuth and
database-bootstrap runtime entry points. Keep accepted source bytes frozen.

## Terminal replan receipt

The read-only owner selected `KEEP + HARDEN IN ONE FRESH EVIDENCE-ONLY
SUCCESSOR`. The successor begins with a real browser enrollment, invokes the
actual OAuth initiation/callback/revocation functions, and restarts on the same
temporary database. Its legacy collision fixture is another real enrollment;
the test calls `init_db` and never calls `bootstrap_legacy_session` or assembles
legacy roots itself.

The exact SQLite/PostgreSQL 16 matrix, transaction seed families, reversible
mutations, protected hashes, fresh Critical review and UUID/shared resume hashes
are frozen in the decision and successor artifacts above. V0-SRH-CR-002 remains
closed at the exhausted recheck hash. No backend, existing test, schema,
migration, frontend, CURRENT, PROGRAMME, provider, credential, live/money,
commit or deployment path changed. This receipt does not close V0-SRH-CR-001 or
V0-SRH-CR-003 and does not authorize UUID/shared assembly resume.
