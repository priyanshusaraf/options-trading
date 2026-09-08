---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-product-analytics-copy-safe-validation-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_exhausted_recheck_replan",
  "goal": "Replace the exhausted product-analytics copyable trust-marker design with a fresh value-validation architecture that revalidates all invariants at every derivation and decode boundary.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "A decision preserves both immutable failed verdicts, defines untrusted value carriers plus context-complete validation without copyable trust state, covers shallow/deep copy and constructor-only invariants, and seals one fresh successor with zero product writes."},
  "risk_tags": ["critical", "analytics", "privacy", "copy-semantics", "authority", "exhausted-recheck"],
  "depends_on": ["strategy-os-v0-product-analytics-contract-foundation"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-product-analytics-contract-foundation/review/verdict.json", "sections": ["risk_boundaries", "SPEC", "QUALITY", "evidence_gaps", "owner_gates", "recheck"]},
    {"path": ".agent/runs/strategy-os-v0-product-analytics-contract-foundation/review/recheck-verdict.json", "sections": ["fresh_recheck_evidence", "risk_boundaries", "SPEC", "QUALITY", "finding_disposition", "evidence_gaps", "recheck_accounting"]},
    {"path": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/decision.json", "sections": ["safe_pure_contract", "prohibited", "injected_configuration_without_default", "owner_privacy_security_gates"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-copy-safe-validation-replan.md", ".agent/runs/strategy-os-v0-product-analytics-copy-safe-validation-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-copy-safe-validation-replan.md", ".agent/runs/strategy-os-v0-product-analytics-copy-safe-validation-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Preserve the failed capsule and verdicts; no second same-lineage recheck or edit is acceptance evidence.", "Decide whether raw dataclasses should be explicitly untrusted value carriers and every factory/derivation/decode should reconstruct or fully revalidate all UUID/time/catalogue/authority/source/dimension/publishable invariants.", "Reject stored singleton/object-identity trust, copy/deepcopy hooks as the sole guard, keyword filtering and production catalogue choices.", "Specify shallow/deep copy, replace, object mutation, constructor and fresh-process regressions plus validation-seam mutations.", "Keep collection, persistence, API/frontend, admin, processors and deployment closed."],
  "acceptance": ["Decision explains why a copyable marker is removed rather than patched.", "Fresh successor owns exact existing product/test paths and new evidence/task paths without overwriting verdicts.", "Successor proves every accepted derivation by complete injected-context revalidation; direct values may exist but cannot be consumed as trusted without the seam.", "EG-003 remains an owner gate; zero product/test/schema/frontend/deploy writes; architecture passes."],
  "test_plan": ["Read-only failed-lineage/source inspection and architecture validation; tests belong to fresh successor."],
  "risk_classification": {"tier": "Critical", "reason": "Trust stored on mutable runtime objects is copied independently of the validated facts and can misclassify privacy-sensitive analytics values."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_product_analytics_copy_safe_validation_replan", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only exhausted-recheck routing; fresh successor receives one new Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-product-analytics-copy-safe-validation-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-copy-safe-validation-replan.md", ".agent/runs/strategy-os-v0-product-analytics-copy-safe-validation-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-product-analytics-copy-safe-validation-replan/decision.json", "verdicts": ["ARCHITECTURE", "PRIVACY"], "max_rechecks": 1},
  "owner_gates": ["Production catalogue/provenance, collection, preference, lifecycle, persistence, admin/API/frontend, processor and deployment remain closed."],
  "stop_conditions": ["A safe design still relies on copyable object identity or a second same-lineage recheck.", "A design requires production catalogue policy or effects."],
  "deployment_impact": {"classification": "none; read-only fresh-successor replan", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "FRESH REPLAN PASS", "decision": "REMOVE COPYABLE TRUST MARKER; VALIDATE COMPLETE CONTEXT AT EVERY USE", "decision_sha256": "1dd4b195b9ad15758a54ce95579430ecbe36228fb811b8fdb20327d775571055", "successor_capsule_sha256": "5236f0d928181eb2126b6c997634824e764fded65ad876d20019e804d09a0050", "successor": "strategy-os-v0-product-analytics-context-validation-correction", "product_writes": 0, "deployment": false},
  "nonclaims": ["No product correction, collection, storage, admin, API/frontend, processor, deployment or V0 completion."]
}
---

# Product analytics copy-safe validation replan

Remove stored trust from runtime values. Validation must be complete at use time.

## Replan evidence receipt

The failed marker lineage and both verdicts remain immutable. The fresh successor
removes stored derivation trust, treats dataclasses as untrusted values, and
requires complete injected-context validation at every factory, derivation and
decode boundary. V0-PAC-EG-003 remains open and blocks collection/publication.
