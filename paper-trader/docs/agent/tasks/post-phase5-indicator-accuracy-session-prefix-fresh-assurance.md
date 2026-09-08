---
{
  "id": "post-phase5-indicator-accuracy-session-prefix-fresh-assurance",
  "phase": "post-phase5",
  "status": "completed",
  "kind": "independent_accuracy_assurance",
  "verdict": "ASSURANCE PASS",
  "goal": "Independently accept or reject the corrected 31-component session-data wave after the sealed F01-FRESH session-open input and identity correction.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Seal ASSURANCE PASS or REJECT for all 31 decisions, 17 candidates, 14 refusals, the eight corrected session-prefix identities, complete arrays/masks/consumers/restart/resources and historical rejection preservation. No product edit or publication."
  },
  "risk_tags": ["critical", "research-integrity", "session-prefix", "independent-assurance", "complete-universe"],
  "required_docs": [
    {"path": ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/report.md", "sections": ["Verdict", "F01-FRESH — missing first-session history remains accepted", "Required correction route and limits"]},
    {"path": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/report.md", "sections": ["Verdict", "Evidence", "Scope and remaining gate"]},
    {"path": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/identity-transition.json", "sections": ["affected_components", "decision", "records", "summary", "transitive_explanation"]},
    {"path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/verification-contract.md", "sections": ["Thresholds", "Complete-array comparators", "Adversarial fixtures", "Operational evidence"]}
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-session-prefix-correction",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_prefix_fresh_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_prefix_fresh_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-prefix-fresh-assurance.md"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_prefix_fresh_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_prefix_fresh_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance"
  ],
  "protected_paths": [
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_prefix_correction.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data_fresh_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_fresh_oracle.py",
    "paper-trader/backend/migrations",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": {
    "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py": "3592d4478cf9494c196b415c468438d3ee9d9e157b2d2104922373e9f2eb534f",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py": "6b7924a0ea1a3d5aaf768aec9c72b2023ffcd81a6677fda785413841815cc714",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/report.md": "4076e85c867bb1e65b2878f4f4cce1fca846a753dd9a660cb6e9c36878167ecf",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/evidence.json": "a710539a5313e317b70e735035df54a85bfbe99d856130f2dd8734420d56e840",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/identity-transition.json": "7c674e3be8a8b134333fd2df3cca0a15354cb10acc6f514143172238dd169725",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/closure-seal.json": "fba09d80ed688718524a4d7797adc58ab6e9a29b6b9f16ecf777a52a1217a380"
  },
  "scope": [
    "Fresh owner distinct from both correction and prior assurance owners; no history fork, agents or product edits.",
    "Independently prove all eight affected candidates require exact derived-local SESSION_OPEN_AT, refuse second-slot starts before state mutation and never expose incomplete previous-session aggregates.",
    "Independently verify all 31 decisions, complete arrays/masks/outputs/parameters/refusals, overnight/holiday/short/internal-gap/anchor cases, batch/stream/snapshot/restart/cold replay, resolver/materializer/compiler/verifier/runtime, resources and identity transition.",
    "Preserve 125 legacy and 84 earlier accepted v2 identities; verify exactly eight source/binding-source moves and the declared defining-module closure moves."
  ],
  "acceptance": [
    "The two previously failed F01 assertions and independent variants pass for all eight candidates; deleting one SESSION_OPEN_AT requirement makes assurance fail.",
    "Complete 31/17/14 closure and every numeric/mask/refusal/consumer/restart/resource assertion passes without self-derived expected values.",
    "Historical rejected reports and archived old hashes remain explicit evidence rather than being rewritten green.",
    "At least three isolated omissions/identity/first-slot mutations fail intended assertions and restore exact bytes.",
    "PASS remains unpublished wave evidence only and advances to remaining oracles, not registry/provider/frontend/deployment authority."
  ],
  "test_plan": ["Fresh independent oracles and focused correction challenges, then full session owner/assurance/consumer/restart/resource compatibility with archived-old-hash exclusions named exactly."],
  "independence": {"owner_must_differ": true, "history_fork": false, "agents": 0, "product_edits": 0},
  "concurrent_side_assignments": ["v0_data_only_connection", "v0_local_release_operations", "v0_frontend_route_attribution_correction"],
  "parallel_budget": 4,
  "assignments": [
    {"id": "v0_data_only_connection", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md", "owner_task": "/root/v0_data_only_connection", "status": "correction_active"},
    {"id": "v0_local_release_operations", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md", "owner_task": "/root/v0_local_release_operations", "status": "correction_active"},
    {"id": "v0_frontend_route_attribution_correction", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-route-attribution-correction.md", "owner_task": "/root/v0_frontend_production_convergence", "status": "active"},
    {"id": "v0_monitoring_intent_contract", "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-intent-contract.md", "owner_task": "/root/v0_nodes_signals_inventory", "status": "active"}
  ],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "01a04d1b-b1d3-76c3-9851-f796047097eb",
  "closure": {
    "report": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance/report.md",
    "evidence": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance/evidence.json",
    "closure_seal": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance/closure-seal.json",
    "focused_tests": 73,
    "complete_session_tests": 196,
    "mutations_killed": 3,
    "resource_events": 200000,
    "publication": false,
    "deployment": false
  },
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_session_prefix_fresh_assurance",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance/review-package.json",
    "review_paths": ["paper-trader/backend/tests/test_indicator_accuracy_session_prefix_fresh_assurance.py", "paper-trader/backend/research_tests/test_indicator_accuracy_session_prefix_fresh_oracle.py", "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-prefix-fresh-assurance.md", ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance"],
    "exclude_paths": ["paper-trader/backend/app", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-fresh-assurance/report.md",
    "verdicts": ["ASSURANCE"],
    "max_rechecks": 0
  },
  "owner_gates": ["Standing V0 authority and sealed correction open this fresh independent assurance. No user token is required."],
  "stop_conditions": ["Any product edit or accepted fixture rewrite is required.", "Any of the eight still accepts missing/misaligned session-open evidence.", "Expected values derive from product math or identity drift is unexplained."],
  "deployment_impact": {"classification": "evidence-only; no deployment change"},
  "nonclaims": ["No registry publication, provider/calendar certification, frontend, schema, paper/live, order, money, deployment or V0 completion."]
}
---

# Fresh session-prefix assurance

Independently challenge the corrected session-open requirement and complete 31-decision wave. Product bytes are read-only.
