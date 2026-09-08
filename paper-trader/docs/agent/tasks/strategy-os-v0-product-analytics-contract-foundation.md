---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-product-analytics-contract-foundation",
  "phase": "v0",
  "status": "rejected_after_exhausted_recheck",
  "kind": "critical_pure_unpublished_product_analytics_contracts",
  "goal": "Implement immutable pure contracts for a finite server-authored product-event language and non-publishable privacy-safe aggregate dimensions without collection, persistence, retry, export, external processors, admin access or private product/money data.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Closed deterministic catalogue, authority, event and aggregate identities cover one legitimate synthetic server fact, reject private/open/foreign inputs, preserve exact restart and resource/mutation evidence and pass one Critical review; all collection, persistence, lifecycle, admin and external effects remain absent."},
  "risk_tags": ["critical", "analytics", "privacy", "tenant-isolation", "data-egress", "admin-blindness", "no-external-effect"],
  "depends_on": ["strategy-os-v0-product-analytics-policy-replan", "strategy-os-v0-platform-operations-persistence", "strategy-os-v0-structured-support-contract-foundation"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/decision.json", "policy": "Only a pure server-authored non-emitting event language may proceed; production purposes/catalogue, preferences, storage, admin and processors remain blocked."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/decision.json", "sections": ["fixed_owner_facts", "observed_inventory", "safe_pure_contract", "prohibited", "injected_configuration_without_default", "distinct_future_facts", "later_owners"]},
    {"path": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/policy-matrix.md", "sections": ["V0 product analytics policy authority matrix"]},
    {"path": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/inventory.md", "sections": ["V0 product analytics producer and destination inventory"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/product_analytics/__init__.py", "paper-trader/backend/app/product_analytics/contracts.py", "paper-trader/backend/tests/test_v0_product_analytics_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-contract-foundation.md", ".agent/runs/strategy-os-v0-product-analytics-contract-foundation"],
  "new_paths": ["paper-trader/backend/app/product_analytics/__init__.py", "paper-trader/backend/app/product_analytics/contracts.py", "paper-trader/backend/tests/test_v0_product_analytics_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-contract-foundation.md", ".agent/runs/strategy-os-v0-product-analytics-contract-foundation"],
  "protected_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/accounts", "paper-trader/backend/app/admin", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/events", "paper-trader/backend/app/engine", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/backtest", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Create frozen dataclasses/enums and canonical identities only; no database, clock lookup, HTTP, environment, network, filesystem or external dependency.",
    "Injected finite catalogue defines server-authored event type, purpose, product area, route template, build, outcome and exact enum/boolean/bounded-integer dimension domains with no production default.",
    "Collection-authority proof is explicit and non-defaulting. Event candidate binds exact catalogue/provenance, authority, opaque subject/tenant/session epoch UUIDs, immutable authoritative source-fact address and injected UTC received time.",
    "Aggregate-dimension candidate derives only from a policy-valid event and excludes subject/tenant/session/source/time. It records `publishable=false` and effects nothing.",
    "Unknown fields, dynamic keys, string answers, arbitrary property/context/payload bags, raw transport/browser/error content and every private product/research/monitoring/money/provider/payment/personal field are unrepresentable and refused by strict decoders.",
    "Existing engine analytics, generic event outbox and legacy/Precision Slate execution analytics are forbidden imports/sources.",
    "No preference/consent semantics, subject rotation lifecycle, persistence/retry/export/delete/restore, threshold, operator authority, API/frontend, external processor, analytics emission or deployment."
  ],
  "acceptance": [
    "Canonical identities change for every answer-changing catalogue, authority, source, subject/tenant/session, event, dimension and time field and refuse unknown/extra/open values.",
    "One legitimate synthetic server-authored event and non-publishable aggregate key pass so universal denial cannot pass.",
    "Cross-catalogue/authority/source/subject/tenant/session substitutions refuse; strict canonical round-trip and fresh-interpreter restart require exact injected source context.",
    "AST/signature/adversarial decode tests prove no property/context/payload/free-text/URL/body/header/DOM/replay/screenshot/error/private-domain field or forbidden import.",
    "Hostile duplicate/noncanonical/Unicode/size/depth/count/time and exact built-in-version vectors return closed validation errors.",
    "100,000 deterministic decisions under unchanged declared time/memory bounds, at least eight isolated safety mutations with restoration and one Critical SPEC/QUALITY review pass."
  ],
  "test_plan": ["RED/GREEN catalogue/authority/event/aggregate canonical codecs and positive control.", "Cross-binding and finite domain/type/count/time/size/depth/Unicode/duplicate vectors.", "Forbidden sentinel, constructor signature, AST and import guards including engine analytics and event outbox.", "Mutation kills for catalogue/authority/source/tenant/session binding, dimension-domain checks, aggregate privacy and publishable=false.", "100,000 pure event-to-aggregate decisions with no I/O."],
  "risk_classification": {"tier": "Critical", "reason": "An analytics contract can silently become a general data-egress channel or destroy the owner's promised ignorance before a collector exists."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_product_analytics_contract_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/product_analytics/__init__.py", "paper-trader/backend/app/product_analytics/contracts.py", "paper-trader/backend/tests/test_v0_product_analytics_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-contract-foundation.md", ".agent/runs/strategy-os-v0-product-analytics-contract-foundation"], "output": ".agent/runs/strategy-os-v0-product-analytics-contract-foundation/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_product_analytics_contract_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "The contract is the future egress and admin-blindness boundary.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-product-analytics-contract-foundation/review-package.json", "review_paths": ["paper-trader/backend/app/product_analytics/__init__.py", "paper-trader/backend/app/product_analytics/contracts.py", "paper-trader/backend/tests/test_v0_product_analytics_contracts.py", "paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-contract-foundation.md", ".agent/runs/strategy-os-v0-product-analytics-contract-foundation"], "exclude_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/accounts", "paper-trader/backend/app/admin", "paper-trader/backend/app/operator_auth", "paper-trader/backend/app/platform_operations", "paper-trader/backend/app/events", "paper-trader/backend/app/engine", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ir", "paper-trader/backend/app/backtest", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-product-analytics-contract-foundation/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["No production event/purpose catalogue, preference/consent, subject lifecycle, retention/export/delete/restore, small-cell threshold, operator access, persistence, API/frontend, external processor or deployment action."],
  "stop_conditions": ["A useful contract requires arbitrary properties, strings, private domain facts, browser auto-capture, stable external identifiers or any effect.", "Existing product_analytics path ownership appears concurrently."],
  "implementation_evidence": {
    "review_package_sha256": "f436a9622addc9256686c810d0b6374ce50bf89d7f03b0b48d569e2ad84cdc5e",
    "source_sha256": {"__init__.py": "ea14c628ceab97ec15810cb28425ba69bc96dfc89fb0d41ca446c262baa72090", "contracts.py": "cf3f5bbf7ec4fd095a71353ddffccde2cf169ec16cd35b0b1478d0638184205f"},
    "test_sha256": "05c8afa797dc6fe4a64b827e3772b24303b6e6e1ac137291aeb91a9c8fdc0f64",
    "report_sha256": "403f94c714639c58fc9fd2bbcf94674f463a2e382d0abfced66520ea6385c09b",
    "fingerprint_sha256": "c7918a8b7b9f437c8e91018e1abed9074d86a0e2073fd1c3beed670ba7d6bd74",
    "evidence_sha256": "e98e1b217af383593815b93906d4929b2b440c566a88f46e2b929edeae5724dc",
    "tests": 18,
    "isolated_mutations_killed_and_restored": 8,
    "resource": {"decisions": 100000, "elapsed_seconds": 5.583176, "peak_bytes": 123510},
    "architecture": {"result": "PASS", "log_sha256": "043d67980fb255283d2ce62ca9abdca5673d63fc47c2ef4a9967494e066fa0d1"},
    "protected_attribution": "Protected paths changed concurrently after orientation. This assignment did not write them, and no unchanged-protected-path claim is made.",
    "effect_flags": {"collection": false, "persistence": false, "retry": false, "export": false, "external_processor": false, "admin_access": false, "publication": false, "api": false, "frontend": false, "deployment": false}
  },
  "first_review": {"verdict": "SPEC FAIL / QUALITY FAIL / final FAIL", "verdict_sha256": "c002102c9145e5e084e74ab1bfe34d66379eeab2d280f70e2c4962f5f713b2e8", "findings": ["V0-PAC-CR-001", "V0-PAC-CR-002"], "evidence_gaps": ["V0-PAC-EG-001", "V0-PAC-EG-002", "V0-PAC-EG-003"], "rechecks_used": 0, "rechecks_remaining": 1, "correction_scope": "Centralize exact catalogue/authority/source/event validation at direct construction, aggregate derivation and decode; add attributable boundary mutations. Production identifier semantics remain a separate owner gate.", "deployment": false},
  "correction_evidence": {
    "status": "correction_complete_pending_focused_recheck",
    "corrected_package_sha256": "c0e6893113fde15df2010ab116337e8b31ef91bc3f05ab213ce4f82ebdf261fc",
    "source_sha256": {"contracts.py": "3f116893a53fb00a3f4d37b8fddae784d547995a8073cca6d688ffdf12a6eba0"},
    "test_sha256": "9fbb4949005eeafa75682575d109f587431cb30fbe1a0cce6b8596a47b9b4faf",
    "report_sha256": "8ee2b7bbca95bc50a04fbb794a3ea36d14b587c2863d9c6082abcbd9425c6122",
    "fingerprint_sha256": "d4d84d18b9361f547944d78862e72157441333ac844ce305a85a1accf2e907f0",
    "evidence_sha256": "1bc3603b49c37644eba631b2f1da406bdc75ce60b104ddabaaf0e71d985a0ab0",
    "tests": 26,
    "mutations": {"previous_restored": 8, "critical_exposed_and_restored": 2, "total": 10},
    "resource": {"decisions": 100000, "elapsed_seconds": 6.321031, "peak_bytes": 122502},
    "architecture": {"result": "PASS", "log_sha256": "043d67980fb255283d2ce62ca9abdca5673d63fc47c2ef4a9967494e066fa0d1"},
    "addressed_pending_recheck": ["V0-PAC-CR-001", "V0-PAC-CR-002", "V0-PAC-EG-001", "V0-PAC-EG-002"],
    "owner_gate_remaining": "V0-PAC-EG-003: exact production catalogue and provenance semantics require owner/privacy approval; no keyword filter added.",
    "protected_attribution": "Protected paths changed concurrently after orientation. This assignment did not write them, and no unchanged-protected-path claim is made.",
    "effect_flags": {"collection": false, "persistence": false, "retry": false, "export": false, "external_processor": false, "admin_access": false, "publication": false, "api": false, "frontend": false, "deployment": false}
  },
  "final_review": {"verdict": "SPEC FAIL / QUALITY FAIL / final FAIL", "first_verdict_sha256": "c002102c9145e5e084e74ab1bfe34d66379eeab2d280f70e2c4962f5f713b2e8", "corrected_package_sha256": "c0e6893113fde15df2010ab116337e8b31ef91bc3f05ab213ce4f82ebdf261fc", "recheck_verdict_sha256": "962f4d7944fd2e7fa1436b8bd34b460e71d2e81d94eac9f94d9a5dea7a8ca87a", "open_findings": ["V0-PAC-CR-003-R1", "V0-PAC-CR-004-R1", "V0-PAC-EG-004-R1", "V0-PAC-EG-003"], "rechecks_used": 1, "rechecks_remaining": 0, "next_action": "REPLAN_REQUIRED", "successor_replan": "strategy-os-v0-product-analytics-copy-safe-validation-replan", "collection": false, "deployment": false},
  "deployment_impact": {"classification": "compatible pure unpublished contracts", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No event collection, store, retry, preference, retention/delete/export, aggregate publication, admin access, SDK/processor, API/frontend, deployment or V0 completion."]
}
---

# Product analytics contract foundation

Pure server-authored, non-emitting analytics facts only. No collector, store,
dashboard, SDK, processor, preference or customer-visible behavior exists here.

## Implementation status

`correction_complete_pending_focused_recheck`

The owner slice implements only frozen canonical values for an injected finite
catalogue, explicit collection-authority proof, authoritative server source
context and source-fact address, opaque subject/tenant/session epoch UUIDs,
event candidates, and non-publishable aggregate dimensions. Aggregate values
exclude subject, tenant, session, source address, source context and received
time.

The synthetic identifiers prove codec and binding behavior only. Generic
identifier semantics remain a production-catalogue owner/privacy gate. This
slice does not infer safe semantics from identifier spelling and does not add
keyword filtering.

## Evidence

- RED: `.agent/runs/strategy-os-v0-product-analytics-contract-foundation/v0_product_analytics_contract_owner/red-missing-contract.log`
- Focused GREEN and eight isolated restored mutations: `.agent/runs/strategy-os-v0-product-analytics-contract-foundation/v0_product_analytics_contract_owner/mutation-and-focused.log`
- Full GREEN, restart/adversarial/AST checks, and 100,000 decisions in
  5.583176 seconds with 123,510 peak traced bytes:
  `.agent/runs/strategy-os-v0-product-analytics-contract-foundation/v0_product_analytics_contract_owner/full-contract-suite-cached-identity.log`
- Static compile, diff check, source hashes, policy-source hashes, protected
  aggregate receipt, deploy-script hash and external frontend hash:
  `.agent/runs/strategy-os-v0-product-analytics-contract-foundation/v0_product_analytics_contract_owner/closure-static-and-hashes.log`
- Review input: `.agent/runs/strategy-os-v0-product-analytics-contract-foundation/review-package.json`
- Corrected review input: `.agent/runs/strategy-os-v0-product-analytics-contract-foundation/corrected-review-package.json`
- Correction report: `.agent/runs/strategy-os-v0-product-analytics-contract-foundation/correction-report.md`

## Open gate and nonclaims

The one allowed focused Critical recheck remains required. V0-PAC-EG-003 stays
blocked on production-catalogue/provenance owner approval. There is no production catalogue,
collection, preference or consent policy, subject lifecycle, persistence, retry,
retention, export, deletion, restore, reducer, threshold, publication, admin
access, API, frontend, processor, deployment, or release-readiness claim.
