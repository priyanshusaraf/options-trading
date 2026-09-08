---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-account-commerce-strict-consumer-fixture-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_account_commerce_consumer_contract_and_presentation_correction",
  "goal": "Close V0-ACAPI-EG-001 with strict four-schema consumer validation and deterministic consumer-owned abort evidence, and close V0-ACAPI-PD-001 by mapping the valid internal no-entitlement UNKNOWN fact to public INACTIVE without changing service or repository authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Both findings have direct RED/GREEN/adversarial/abort/mutation/restoration/affected-suite/architecture/protected-hash evidence and one fresh Important SPEC PASS / QUALITY PASS review."},
  "risk_tags": ["important", "auth", "privacy", "api", "frontend-contract", "consumer-validation", "timeout"],
  "depends_on": ["strategy-os-v0-account-commerce-strict-consumer-fixture-replan"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/decision.json", "decision_sha256": "578867c7af8c0204a7e9899cd9d21f4ecdea042ef242201ac156d04f91861d90", "successor_capsule_sha256": "6aa5a5ede8e4c52e0c0ecfe7e1e1aad6029d69b02557f7ada04e3721c5eff25d", "open_findings": ["V0-ACAPI-EG-001", "V0-ACAPI-PD-001"], "policy": "Only route presentation and the test-local consumer contract may change; accepted service/repository authority and concurrency behavior remain frozen."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/decision.json", "sections": ["producer_consumer_boundary", "findings", "successor", "replan_verdicts"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/response-contract-matrix.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-replan/malformed-corpus.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-foundation/review/recheck-verdict.json", "sections": ["closed_findings", "open_gaps", "independent_checks", "nonclaims"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/api/account_commerce_routes.py", "paper-trader/backend/tests/test_v0_account_commerce_routes.py", "paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-correction.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-correction.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction"],
  "protected_paths": ["paper-trader/backend/app/account_commerce/service.py", "paper-trader/backend/app/account_commerce/repository.py", "paper-trader/backend/app/main.py", "paper-trader/backend/app/api/routes.py", "paper-trader/backend/app/api/principal.py", "paper-trader/backend/app/api/auth_session_routes.py", "paper-trader/backend/app/api/versioning.py", "paper-trader/backend/app/accounts/browser_auth.py", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": ["Implement every field/type/nullability/canonical-UTC/uniqueness/cross-field rule sealed in response-contract-matrix.json for access, status, profile and trial through explicit exceptions that optimized Python cannot disable.", "Run every malformed-corpus.json family against valid payloads; reject before retention and prove privacy-bearing malformed values never enter consumer projections.", "Replace the TestClient timeout claim with a consumer-owned bounded executor using an abort Event, injectable cooperative transport and injectable waiter. The real waiter uses Future.result(timeout=10); on timeout signal abort, await cooperative unwind and raise the explicit abort error before parsing or projection mutation.", "Use an injected deterministic waiter and cooperative slow transport for no-sleep abort evidence: assert the exact ten-second bound, abort observation, zero parsing, unchanged projection and clean executor shutdown; restore immediate transport and rerun the happy path.", "Add one API presentation helper that accepts internal ACTIVE, INACTIVE, EXPIRED and UNKNOWN, maps only UNKNOWN to public INACTIVE, fails closed otherwise, and applies only to access.state/status.access_state.", "Add pre-trial access/status tests proving public INACTIVE with canonical null/state/time/profile/trial relationships. Preserve the unregistered router and closed beta/coupon concurrency behavior."],
  "acceptance": ["Every success field is covered by exact type, enum, nullability and canonical UTC parsing; profile codes are approved, unique and canonical; available cross-field relations are executable.", "Every common, timestamp, schema-specific, cross-response and privacy-bearing malformed family rejects, then canonical payload restoration accepts without projection drift.", "The deterministic cooperative slow transport is aborted through the consumer-owned signal at the exact ten-second contract without network or sleep; no TestClient timeout/cancellation claim remains.", "Pre-trial access/status return public INACTIVE while protected service/repository still retain internal UNKNOWN authority.", "Existing happy path, simultaneous beta/coupon convergence, auth/CSRF/no-store/privacy and unregistered inventory stay green.", "One fresh Important review returns SPEC PASS and QUALITY PASS with V0-ACAPI-EG-001 and V0-ACAPI-PD-001 closed."],
  "test_plan": ["Capture immutable strictness and pre-trial UNKNOWN RED probes before correction.", "Run focused precision_slate/pretrial tests, full route tests and affected auth/session/tenant/service selection.", "Kill and restore parser, UNKNOWN-passthrough and late-response/no-abort mutations.", "Verify architecture and identical protected hashes after every final gate."],
  "risk_classification": {"tier": "Important", "reason": "The slice corrects bounded unpublished account-commerce response presentation and auth/privacy consumer evidence without changing tenant authority, providers, money, registration or deployment."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_account_commerce_strict_consumer_fixture_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-presentation-consumer-tests-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/api/account_commerce_routes.py", "paper-trader/backend/tests/test_v0_account_commerce_routes.py", "paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-correction.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction"], "output": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_account_commerce_strict_consumer_fixture_review", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Fresh Important auth/privacy consumer and bounded API presentation correction requires one independent review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/review-package.json", "review_paths": ["paper-trader/backend/app/api/account_commerce_routes.py", "paper-trader/backend/tests/test_v0_account_commerce_routes.py", "paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-strict-consumer-fixture-correction.md", ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction"], "exclude_paths": ["paper-trader/backend/app/account_commerce/service.py", "paper-trader/backend/app/account_commerce/repository.py", "paper-trader/backend/app/main.py", "paper-trader/backend/app/api/routes.py", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["No shared registration, external Precision Slate frontend, provider/Google/email/Razorpay network or credentials, production data, money, deployment, release-readiness or V0-complete claim."],
  "stop_conditions": ["Strict parsing requires a product schema change beyond UNKNOWN-to-INACTIVE presentation mapping.", "Cooperative abort cannot be proved without external network or sleep.", "Concurrent ownership appears on either source path."],
  "deployment_impact": {"classification": "compatible unpublished API presentation/test correction", "schema_or_migration": false, "configuration_or_dependency": false, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "review_result": {"verdict": "SPEC PASS / QUALITY PASS / final PASS", "verdict_path": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/review/verdict.json", "verdict_sha256": "487daa4c5f54e90e80f8025e86ec238e646a7fb85c6267e9d5d0586f6fdbf952", "closed_findings": ["V0-ACAPI-EG-001", "V0-ACAPI-PD-001"], "open_findings": [], "rechecks_used": 0, "rechecks_remaining": 1, "architecture_files": 474},
  "nonclaims": ["No shared registration, external frontend implementation, provider billing, payment/refund, production migration, deployment, release readiness or V0 completion."]
}
---

# Account-commerce strict consumer-fixture correction

Close only the two sealed presentation/consumer findings. Preserve the accepted
service authority, tenant boundary, retry behavior and unpublished route status.

## Accepted receipt

The fresh Important review returned SPEC PASS / QUALITY PASS / final PASS and
closed both findings without a recheck. The API remains unregistered and all
provider, frontend publication, money and deployment gates remain closed.

## Owner evidence receipt

Status: `READY_FOR_ONE_FRESH_IMPORTANT_REVIEW`; no finding closure or programme
completion is claimed before the required SPEC/QUALITY verdict.

- Immutable RED, GREEN, malformed-corpus, abort, mutation/restoration, affected,
  architecture and protected-hash evidence is indexed in
  `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/report.md`.
- The review package is
  `.agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/review-package.json`.
- Service/repository authority, shared registration, frontend, providers,
  credentials, money and deployment remain unchanged and closed.
