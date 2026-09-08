---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-structured-support-contract-foundation",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_pure_unpublished_structured_support_contracts",
  "goal": "Implement immutable pure contracts for owner-scoped structured support submissions, safe operator projections, typed operator actions, in-app delivery candidates and non-identifying analytics dimensions without persistence, transport, free text, external processors or private product facts.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Closed deterministic policy and candidate identities cover one legitimate structured request/action/delivery flow, cross-owner substitutions, forbidden-content unrepresentability, canonical restart and resource/mutation evidence with one Critical review; all persistence, API, frontend, email, admin authority and deployment effects remain absent."},
  "risk_tags": ["critical", "support", "privacy", "tenant-isolation", "admin-blindness", "no-external-effect"],
  "depends_on": ["strategy-os-v0-structured-support-policy-replan", "strategy-os-v0-auth-session-transport", "strategy-os-v0-entitlement-policy-contract-foundation"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-structured-support-policy-replan/decision.json", "policy": "Only the pure unpublished closed structured language may proceed; persistence, free text, email, retention, operator access and publication remain blocked."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-structured-support-policy-replan/decision.json", "sections": ["fixed_owner_facts", "safe_structured_contract", "injected_configuration_without_default", "prohibited", "unresolved_owner_privacy_security", "data_flow", "later_owners"]},
    {"path": ".agent/runs/strategy-os-v0-structured-support-policy-replan/policy-matrix.md", "sections": ["V0 structured support policy authority matrix"]},
    {"path": ".agent/runs/strategy-os-v0-post-0045-parallel-materialization-audit/account-commerce-operations/report.md", "sections": ["Tenant and operator data-flow matrix", "Failure hypotheses", "Verification gates for successors"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/support/__init__.py", "paper-trader/backend/app/support/contracts.py", "paper-trader/backend/tests/test_v0_structured_support_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-structured-support-contract-foundation.md", ".agent/runs/strategy-os-v0-structured-support-contract-foundation"],
  "new_paths": ["paper-trader/backend/app/support/__init__.py", "paper-trader/backend/app/support/contracts.py", "paper-trader/backend/tests/test_v0_structured_support_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-structured-support-contract-foundation.md", ".agent/runs/strategy-os-v0-structured-support-contract-foundation"],
  "protected_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/accounts", "paper-trader/backend/app/admin", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/analytics", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/backtest", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Create frozen dataclasses/enums and canonical content identities only; no database, clock, HTTP, environment, network, filesystem or external dependency.",
    "Policies contain finite injected category, product-area, route-template, component, build, question, answer-domain, response-template and status-transition identifiers with no production default.",
    "Submission candidates bind exact account and tenant UUIDs, policy identity, finite context, typed answers and injected UTC time.",
    "Safe operator projections expose only approved structured fields; analytics dimensions exclude identifiers, answers, exact timestamps and route/component/build details.",
    "Operator actions use status plus approved response-template identifier only. In-app delivery is a non-sending candidate bound to the owning account/tenant/case.",
    "Unknown fields, arbitrary strings, free text, attachment/diagnostic fields and every private product/research/monitoring/money/provider/payment field are unrepresentable and refused by strict decoders.",
    "No persistence, retention/delete/export semantics, external processor, email, operator session, API/frontend, access activation, money/execution effect or deployment."
  ],
  "acceptance": [
    "Canonical identities change for every answer-changing policy, owner, tenant, context, answer, status, template and time field and refuse unknown/extra/open values.",
    "One legitimate submission, safe operator projection, allowed transition, delivery candidate and analytics dimensions pass so universal denial cannot pass.",
    "Cross-account/cross-tenant/cross-policy/action-case/delivery-owner substitutions refuse with no candidate; canonical round-trip and fresh-interpreter restart are exact.",
    "AST/signature and adversarial decode tests prove there is no free-text/title/description/note/attachment/log/URL/body/header/property-bag or forbidden domain field.",
    "100,000 deterministic evaluations, size/depth/count/identifier/time bounds and isolated omission/permissive mutations pass.",
    "Source/import guards forbid db/api/admin/operator-auth/analytics/monitoring/IR/backtest/engine/execution/ledger/provider/research/env/network/email/filesystem imports and one Critical SPEC/QUALITY review passes."
  ],
  "test_plan": ["RED/GREEN policy/submission/projection/action/delivery/analytics canonical serialization and refusal tests.", "Boundary and substitution vectors for UUIDs, identifiers, UTC time, finite domains, answer types/counts and transition authority.", "Forbidden sentinel/unknown-key/open-value tests and AST constructor/signature/import guards.", "Mutation kills for owner/tenant binding, policy proof, answer-domain enforcement, safe projection omission, transition authority and analytics identifier exclusion.", "100,000 pure decisions under declared time/memory limits; no I/O."],
  "risk_classification": {"tier": "Critical", "reason": "A support contract is a direct potential path for strategy IP, credentials, financial facts or cross-tenant disclosure even before persistence."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_structured_support_contract_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/support/__init__.py", "paper-trader/backend/app/support/contracts.py", "paper-trader/backend/tests/test_v0_structured_support_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-structured-support-contract-foundation.md", ".agent/runs/strategy-os-v0-structured-support-contract-foundation"], "output": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_structured_support_contract_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "The data-shape boundary must reject proprietary, financial, credential and cross-tenant disclosure before later persistence or admin work.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/review-package.json", "review_paths": ["paper-trader/backend/app/support/__init__.py", "paper-trader/backend/app/support/contracts.py", "paper-trader/backend/tests/test_v0_structured_support_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-structured-support-contract-foundation.md", ".agent/runs/strategy-os-v0-structured-support-contract-foundation"], "exclude_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/accounts", "paper-trader/backend/app/admin", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/analytics", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/backtest", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["No production category/answer/template catalogue, retention/export/delete/hold policy, operator step-up/admin route, email/external processor, persistence, API/frontend, analytics emission or deployment action."],
  "stop_conditions": ["A useful contract requires free text, attachments, diagnostics, keyword redaction or private product/research/money/provider fields.", "A contract would persist, deliver, emit analytics, authenticate an operator or publish a route.", "Existing support code/path ownership appears concurrently."],
  "deployment_impact": {"classification": "compatible pure unpublished contracts", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No request storage, retention/delete/export, operator access, message delivery, email, API/frontend, analytics collection, deployment or V0 completion."],
  "implementation_evidence": {
    "report": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/report.md",
    "red_log": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/v0_structured_support_contract_owner/red.log",
    "focused_log": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/v0_structured_support_contract_owner/focused-final-2.log",
    "focused_tests": 44,
    "resource_evaluations": 100000,
    "isolated_mutations_killed": 7,
    "architecture_log": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/v0_structured_support_contract_owner/architecture-validation-final.log",
    "protected_manifest_note": "The first repository before manifest was overwritten by a late process using a mismatched scope and is non-comparable; external manifests match, and exact repository protected manifests bracket package sealing.",
    "review_state": "implementation_complete_pending_critical_review",
    "deployment": false
  },
  "first_review": {"verdict": "SPEC FAIL / QUALITY FAIL / final FAIL", "verdict_sha256": "5ea56ab28fb42cca0701e84ac8de52f7cf6e55918c465a0abf7abc18d4a16044", "findings": ["V0-SSC-CR-001", "V0-SSC-CR-002", "V0-SSC-CR-003"], "evidence_gaps": ["V0-SSC-EG-001", "V0-SSC-EG-002", "V0-SSC-EG-003", "V0-SSC-EG-004"], "rechecks_used": 0, "rechecks_remaining": 1, "correction_scope": "Bind analytics to an exact projection/action fact; make action/delivery decode source-bound; close hostile recursion as ContractValidationError. Production catalogue semantic namespaces remain an owner gate.", "deployment": false},
  "correction_evidence": {
    "status": "correction_complete_pending_focused_recheck",
    "report": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/correction-report.md",
    "package": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/corrected-review-package.json",
    "red_log": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/v0_structured_support_contract_owner/correction-red.log",
    "focused_log": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/v0_structured_support_contract_owner/correction-focused-final.log",
    "focused_tests": 46,
    "resource_evaluations": 100000,
    "isolated_mutations_killed": 9,
    "architecture_log": ".agent/runs/strategy-os-v0-structured-support-contract-foundation/v0_structured_support_contract_owner/correction-architecture.log",
    "closed_findings": ["V0-SSC-CR-001", "V0-SSC-CR-002", "V0-SSC-CR-003", "V0-SSC-EG-001", "V0-SSC-EG-002", "V0-SSC-EG-003"],
    "owner_gate_remaining": "V0-SSC-EG-004: generic machine identifiers remain unpublished and require an approved production catalogue, trusted server-side provenance and forbidden semantic namespaces before persistence, publication, operator use or analytics emission.",
    "deployment": false
  },
  "final_review": {"verdict": "SPEC PASS / QUALITY PASS / final PASS", "first_verdict_sha256": "5ea56ab28fb42cca0701e84ac8de52f7cf6e55918c465a0abf7abc18d4a16044", "corrected_package_sha256": "0d3c417f61ae43cae0bc32cbc4b0ff42a1af66a3b09b3c59da044121d74d00d8", "recheck_verdict_sha256": "b0a2954b4c6af641a6c7eca97b3797bd3b1a77be90d09ea2ac6e60adc56e1d36", "closed_findings": ["V0-SSC-CR-001", "V0-SSC-CR-002", "V0-SSC-CR-003", "V0-SSC-EG-001", "V0-SSC-EG-002", "V0-SSC-EG-003"], "owner_gate_remaining": "V0-SSC-EG-004", "rechecks_used": 1, "rechecks_remaining": 0, "persistence": false, "public_api": false, "analytics_emission": false, "deployment": false}
}
---

# Structured support contract foundation

Pure closed support facts only. This slice does not create a mailbox, admin panel,
delivery path, analytics producer, external processor or persisted customer record.
