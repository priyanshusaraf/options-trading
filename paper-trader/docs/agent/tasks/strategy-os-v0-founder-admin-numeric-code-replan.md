---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-founder-admin-numeric-code-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_exhausted_admin_code_replan",
  "goal": "Replace the exhausted mutable enum/string admin dimension design with fixed exact built-in integer codes that cannot carry private strings or mutable runtime labels.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Both failed verdicts remain immutable; a fixed numeric code/family table and copy-safe validation architecture are sealed in one fresh successor with zero product writes."},
  "risk_tags": ["critical", "admin", "privacy", "runtime-mutation", "exhausted-recheck"],
  "depends_on": ["strategy-os-v0-founder-admin-safe-projection-contract-foundation"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/review/verdict.json", "sections": ["risk_boundaries", "findings", "evidence_gaps", "owner_gates"]},
    {"path": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-contract-foundation/review/recheck-verdict.json", "sections": ["risk_boundaries", "SPEC", "QUALITY", "finding_disposition", "evidence_gaps", "recheck_accounting"]},
    {"path": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan/decision.json", "sections": ["safe_pure_contract", "structural_exclusions", "owner_security_privacy_gates"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-numeric-code-replan.md", ".agent/runs/strategy-os-v0-founder-admin-numeric-code-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-numeric-code-replan.md", ".agent/runs/strategy-os-v0-founder-admin-numeric-code-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Preserve the exhausted string and enum lineage and both verdicts.", "Use exact built-in integers 1 through 10 as the only canonical dimension values, with fixed family-specific allowed subsets and no runtime label object.", "Reject bool, float, string, enum, subclass, zero, negative, out-of-range and cross-family codes at every policy/input/projection/decode boundary.", "Canonical projection emits integers only; human display labels are a later frontend copy/policy concern and never enter admin identity.", "Keep thresholds, operator auth, individual access, persistence/publication/API/frontend/deployment closed."],
  "acceptance": ["Decision explains why integer codes remove both arbitrary strings and mutable enum state.", "Fresh successor owns exact product/test paths and new task/evidence; failed review bytes remain immutable.", "All 22 string sentinels and enum internal mutation attempts refuse; exact int codes and five family subsets pass.", "No product writes in replan; architecture passes."],
  "test_plan": ["Read-only failed-lineage and current-source inspection; implementation tests belong to successor."],
  "risk_classification": {"tier": "Critical", "reason": "Mutable runtime label objects can change canonical privacy semantics after validation."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_founder_admin_numeric_code_replan", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only exhausted-lineage replan; fresh successor receives Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-founder-admin-numeric-code-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-numeric-code-replan.md", ".agent/runs/strategy-os-v0-founder-admin-numeric-code-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-founder-admin-numeric-code-replan/decision.json", "verdicts": ["ARCHITECTURE", "PRIVACY"], "max_rechecks": 1},
  "owner_gates": ["Production threshold/code selection, operator auth, individual/PII access, persistence/API/frontend/publication and deployment remain closed."],
  "stop_conditions": ["Design re-emits mutable/runtime strings or uses another same-lineage recheck.", "Any effect or production policy is required."],
  "deployment_impact": {"classification": "none; read-only fresh-successor replan", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "FRESH NUMERIC CODE REPLAN PASS", "decision": "REMOVE MUTABLE ENUM LABELS; CANONICALIZE EXACT BUILT-IN INTEGER CODES 1 THROUGH 10", "decision_sha256": "e1943b90b14e0d97bc752e2fb746297fc9712e9509b6570ac98b74416aa7dc66", "successor_capsule_sha256": "a92b2537fcbf786eff043eeb96a5635c43f203d21bdfec550ffc04d30fc1f744", "successor": "strategy-os-v0-founder-admin-numeric-projection-correction", "product_writes": 0, "deployment": false},
  "nonclaims": ["No product correction, admin access, publication, API/frontend, deployment or V0 completion."]
}
---

# Founder/admin numeric code replan

Remove mutable labels from canonical admin projection data.

## Replan evidence receipt

The exhausted string/enum lineage and both verdicts remain immutable. The fresh
successor uses exact built-in integers 1–10 only; display labels never enter
canonical projection data.
