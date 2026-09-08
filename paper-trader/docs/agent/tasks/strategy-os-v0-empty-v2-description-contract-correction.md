---
{
  "id": "strategy-os-v0-empty-v2-description-contract-correction",
  "lineage_id": "strategy-os-v0-empty-v2-description-contract-correction",
  "programme_stage": "strategy-os-v0-monitoring-signals-review",
  "phase": "v0",
  "status": "accepted",
  "kind": "routine_frontend_response_contract_correction",
  "goal": "Accept the backend-authorized empty V2 graph description in the frontend draft parser without weakening any other V2 document field.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The empty-description browser refusal reproduces, one parser regression turns RED then GREEN, non-empty and malformed V2 draft behavior remains unchanged, one ablation restores the refusal, focused/full frontend tests, typecheck, build and architecture pass, and the builder browser journey reaches the real canvas."},
  "authorization_resolution": {"status": "OWNER_AUTHORIZED_AS_REQUIRED_V0_BUILDER_RECOVERY", "evidence": "The owner requested working builder interactions. The live browser journey proved that a newly created graph with the backend-authorized default empty description is rejected before the builder mounts."},
  "risk_tags": ["routine", "frontend", "response-contract", "v2-editor", "browser"],
  "required_skills": ["strategyos-repo-orientation", "executing-strategy-os-slices", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-v2-editor-private-restore-structural-correction"],
  "required_docs": [
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction.md", "sections": ["goal", "scope", "acceptance"]},
    {"path": ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction/browser-final-failure.json", "sections": ["parser_results", "contract_responses"]},
    {"path": "paper-trader/backend/app/api/ir_v2_edit_routes.py", "sections": ["V2GraphCreate"]},
    {"path": "paper-trader/backend/app/editor/v2_editor_store.py", "sections": ["create_graph"]}
  ],
  "allowed_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.test.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/.agent/runs/strategy-os-v0-empty-v2-description-contract-correction",
    "paper-trader/docs/agent/tasks/strategy-os-v0-empty-v2-description-contract-correction.md",
    ".agent/runs/strategy-os-v0-empty-v2-description-contract-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-empty-v2-description-contract-correction.md",
    ".agent/runs/strategy-os-v0-empty-v2-description-contract-correction"
  ],
  "external_review_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.test.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/.agent/runs/strategy-os-v0-empty-v2-description-contract-correction"
  ],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts"],
  "scope": [
    "Change only V2 metadata.description parsing to allow the empty string already authorized by V2GraphCreate.default and create_graph. Keep the 4,000-character bound and string requirement.",
    "Do not relax strategy_id, metadata.name, tags, ports, nodes, edges, addresses, revisions or response key closure.",
    "Add one exact parser regression and one isolated mutation that restores the old non-empty requirement."
  ],
  "acceptance": [
    "parseV2Draft accepts an exact new-graph response whose metadata.description is an empty string and returns the empty string unchanged.",
    "A missing, non-string or over-4,000-character description remains refused, and all existing V2 parser tests pass.",
    "The live synthetic browser journey reaches Search node library for a newly created empty-description graph.",
    "One isolated mutation restores the old parser call and makes the exact regression RED; exact bytes restore and the regression returns GREEN.",
    "Focused/full frontend tests, typecheck, build and architecture pass."
  ],
  "test_plan": ["Add the exact parseV2Draft empty-description test before implementation. Run shell contracts and builder tests, then full frontend tests, typecheck and build. Run one isolated mutation and resume the live browser journey."],
  "risk_classification": {"tier": "Routine", "reason": "One optional presentation string already accepted and emitted by the backend is aligned in the frontend parser; executable identity and server authority are unchanged."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_empty_v2_description_contract_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-empty-v2-description-contract-correction/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-empty-v2-description-contract-correction.md", ".agent/runs/strategy-os-v0-empty-v2-description-contract-correction"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-empty-v2-description-contract-correction/report.md", "verdicts": ["CONTRACT", "BROWSER"], "max_rechecks": 0},
  "owner_gates": ["Only the empty description contract is authorized. No other parser, backend, schema, provider, strategy, live, money or deployment change.", "Preserve concurrent builder and shell changes; do not reset, clean, stash, rebase, stage, commit or push."],
  "stop_conditions": ["The backend does not in fact authorize or emit an empty description.", "A second field must be relaxed, or the fix requires backend/schema/identity changes."],
  "deployment_impact": {"classification": "frontend-only response parser alignment", "schema_change": false, "dependency_change": false, "configuration_change": false, "runtime_wiring": false, "locally_runnable": true, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No broader parser relaxation, builder acceptance, provider readiness, deployment or V0 completion follows from this correction alone."]
}
---

# V0 empty V2 description contract correction

Align one optional frontend string with the exact response already produced by
new V2 graphs. Preserve every other V2 parser guard.
