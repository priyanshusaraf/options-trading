---
{
  "id": "post-phase5-indicator-accuracy-unavailable-proof-correction",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_test_only_assurance_correction",
  "goal": "Repair the vacuous unavailable-component resolver proof so all 17 named refusals are exercised with real missing and plausible/capability documents before the final review recheck.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "All 34 named unavailable resolver attempts use non-None, component-specific documents in the two declared scenarios; the complete-universe package is resealed; all prior gates remain green; no product byte changes."
  },
  "risk_tags": ["critical", "research-integrity", "assurance-nonvacuity", "typed-refusal", "test-only"],
  "required_docs": [
    {"path": ".agent/runs/post-phase5-indicator-accuracy-final-review/verdict.json", "sections": ["finding_ids", "disposition", "smallest_correction"]},
    {"path": ".agent/runs/post-phase5-indicator-accuracy-final-review/report.md", "sections": ["Verdict", "F01: unavailable-row assurance is vacuous", "Smallest corrective action"]},
    {"path": "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-complete-universe-assurance.md", "sections": ["Complete universe assurance"]},
    {"path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/verification-contract.md", "sections": ["Adversarial fixtures", "Operational evidence"]}
  ],
  "dependency_gate": "Final Critical review F01 at verdict SHA-256 45831006d549f005e091e4cb9ca45cee1231146b90ae4faea91b9db04f146a00; no recheck consumed.",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_complete_universe.py",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-unavailable-proof-correction.md",
    ".agent/runs/post-phase5-indicator-accuracy-unavailable-proof-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-unavailable-proof-correction.md",
    ".agent/runs/post-phase5-indicator-accuracy-unavailable-proof-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/backend/research_tests",
    "paper-trader/backend/tests/test_indicator_accuracy_lineage_assurance.py",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-complete-universe-assurance.md",
    ".agent/runs/post-phase5-indicator-accuracy-complete-universe-assurance",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Move the unreachable document construction into `_refused_document` and leave `_sma_bound` after it with no dead code.",
    "For every REFUSE row, construct a real format-v2 graph whose node names that row's component_id/version 2. Missing-input and plausible/capability documents must be non-None and materially distinct.",
    "Assert the exact component identity, strategy identity and scenario fields before calling resolve_v2; a broad error on None, malformed generic input or the wrong component must fail the test.",
    "Keep all 17 components absent from the registry and require stable ResolutionError refusal in both scenarios without mutating dispositions.",
    "Add a genuine isolated mutation that returns None or substitutes one component and prove the natural assurance test fails, then restore exact bytes.",
    "Rerun 14/14 focused, the 169-pass affected selector with three explicit PG16 skips, architecture/protected hashes, and reseal a corrected assurance package for the same final reviewer."
  ],
  "acceptance": [
    "34/34 documents are non-None; 17 unique named component identities are observed in each scenario; missing and plausible/capability documents are distinct.",
    "34/34 calls refuse at the advertised resolver while registry/disposition facts remain byte-identical.",
    "None-return and wrong-component mutations are killed and exact source is restored.",
    "All original complete-universe focused/affected/protected/package gates pass with PostgreSQL skips retained as nonclaims.",
    "The same final Critical reviewer receives the corrected package for its single allowed focused recheck."
  ],
  "test_plan": [
    "Run the reviewer counterexample first, then repair only the helper and direct assertions.",
    "Run exact unavailable test, 14-test focused suite, affected selector once, mutation/restoration, hashes, package validation and architecture validator."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "01a04dbe-0ec2-78b0-9c3d-b69d0e58c9a2",
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_unavailable_proof_correction_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-unavailable-proof-correction/review-package.json",
    "review_paths": ["paper-trader/backend/tests/test_indicator_accuracy_complete_universe.py", ".agent/runs/post-phase5-indicator-accuracy-unavailable-proof-correction"],
    "exclude_paths": ["paper-trader/backend/app", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/backend/migrations", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/post-phase5-indicator-accuracy-unavailable-proof-correction/report.md",
    "verdicts": ["IMPLEMENTATION"],
    "max_rechecks": 0
  },
  "owner_gates": [
    "Standing V0 authority permits this exact test-only correction. No product change or user token is required.",
    "Stop before any product, prior evidence, registry, runtime, cache, provider, schema, frontend, execution or deployment byte change."
  ],
  "stop_conditions": [
    "A product behavior change is required to make a named unavailable component refuse.",
    "Any unavailable row is unexpectedly present in the registry or accepts a document.",
    "The correction cannot distinguish both scenarios or cannot kill None/wrong-component mutations."
  ],
  "deployment_impact": {"classification": "test/evidence-only correction; no runtime, schema, service, dependency or deployment change"},
  "nonclaims": ["No numerical behavior, publication, frontend, provider, PostgreSQL, deployment, live/order/money, Phase 6 or V0 completion authority."],
  "implementation_result": {
    "verdict": "IMPLEMENTATION PASS",
    "owner_task": "01a04dbe-0ec2-78b0-9c3d-b69d0e58c9a2",
    "report_sha256": "8dd7af4b861dc2f258caade361c4a3b930d294b4671a0890a73f5269ca273d99",
    "review_package_sha256": "ba1e5b2de0d761e7cf4dff64e5d5c25427a8b46b9f52208291bad4a6972413dc",
    "evidence_sha256": "8cf403a8c4d58109a4916695e6293c44748819f15e5fa95a2e9447163ca37e1f",
    "closure_seal_sha256": "245fb5630807d0138ddd34287a7b221e283c74a38dd692e3438e5701c5a7fab0",
    "focused_passed": 14,
    "affected_passed": 169,
    "affected_skipped_postgresql": 3,
    "mutations_killed": 2,
    "product_writes": 0,
    "deployment": false
  }
}
---

# Unavailable-component assurance correction

Replace the vacuous `None` resolver calls with 34 real named refusal documents and reseal only the assurance proof.
