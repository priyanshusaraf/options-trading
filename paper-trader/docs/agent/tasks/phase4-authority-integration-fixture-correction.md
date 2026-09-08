---
{
  "id": "phase4-authority-integration-fixture-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Repair the one retained Phase 4 loader-tamper regression so it exercises the current typed capability-assessment envelope and reaches the real fail-closed loader contract.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded work required to finish Phase 4. The third evidence-only integration owner proved that one retained test still indexes the retired assessment projection and therefore raises KeyError before invoking the real loader. Authority is limited to that existing test and ignored evidence; product, schema, migration, other tests, programme, CURRENT, review-package, provider, frontend, runtime, deployment, production, live, and money paths remain closed.",
    "stopping_condition": "Complete only after the retained test mutates the requirement result through the exact current capability-assessment/2 fact envelope, invokes the real load_verified_admission seam, and observes RECEIPT_STALE; the focused test and its immediate Phase 4 loader companions pass with no deselection; the test diff contains only the typed-envelope path correction; protected hashes and scoped diff checks pass. Stop with the goal active if product behavior must change, any additional test is stale, or the correction weakens the tamper/refusal assertion.",
    "evidence_stopping_condition": "Retain the pre-edit KeyError counterexample, the exact post-edit focused command and result, proof that load_verified_admission was reached and returned RECEIPT_STALE, a scoped diff, the corrected test hash, protected hashes, and a concise report. The prior integration owner's deselected run is not acceptance evidence."
  },
  "risk_tags": ["test-evidence", "typed-authority", "fail-closed", "integration"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": ["9. Ownership, authority, and persistence", "13.2 Persistence, reconstruction, and refusal", "13.5 Stale evidence and revalidation"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": ["5. Verification cadence", "8. Authority-correction serial route"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["DP-003 — Mocked seam presented as lifecycle evidence", "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact"]
    }
  ],
  "dependency_gate": "phase4-research-json-shape-parity-correction",
  "allowed_paths": [
    "paper-trader/backend/tests/test_backtest_admission.py",
    ".agent/runs/phase4-authority-integration-fixture-correction"
  ],
  "nonclaims": [
    "This correction changes no product behavior and does not complete the authority integration gate, accept Phase 4, build a review package, or establish deployability, production readiness, provider correctness, runtime authority, frontend readiness, money authority, or live authority.",
    "No product, schema, migration, dependency, configuration, service, provider, broker, credential, infrastructure, runtime-enablement, frontend, deployment, programme, CURRENT, or review-package path is authorized.",
    "The third integration owner's green partial evidence remains historical until that same gate is rerun without any deselected retained selector."
  ],
  "owner_gates": [
    "Stop if the retained test cannot reach the real loader through the current typed envelope without a product change.",
    "Stop if another affected test uses a retired receipt or assessment interface, or if the expected refusal changes from RECEIPT_STALE.",
    "Stop if any path outside the single retained test and ignored evidence must change."
  ],
  "stop_conditions": [
    "The test still raises before invoking load_verified_admission, passes through a mock, accepts tampered authority, or asserts a weaker error.",
    "The focused retained selector or its immediate current-interface loader companions fail, protected hashes change, or the scoped diff contains any product or unrelated test edit."
  ],
  "deployment_impact": {
    "classification": "test-only-current-interface-correction",
    "required_evidence": "No runtime, schema, migration, dependency, configuration, service, provider, frontend, or deployment change. Prove only that the retained regression reaches the real current loader and receives the existing fail-closed RECEIPT_STALE result."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "change the stale assessment path from capability_assessment.requirement_results to capability_assessment.fact.requirement_results and make no other semantic change",
    "prove the corrected test invokes the real repository loader and refuses the self-consistently re-addressed tampered receipt as RECEIPT_STALE",
    "run the focused retained selector plus immediate Phase 4 loader companions without deselection, monkeypatched reconstruction, or product changes",
    "record exact test diff/hash, protected hashes, scoped diff check, and nonclaims"
  ],
  "test_plan": [
    "Use the project backend virtualenv and .codex/scripts/run_logged.py; preserve the owner_3 KeyError as the pre-edit counterexample.",
    "Apply only the one typed-envelope path insertion in test_backtest_admission.py.",
    "Run the named retained test, then the smallest complete Phase 4 loader selector in that file needed to prove no adjacent fixture regression.",
    "Audit the exact diff and protected hashes; do not run a broad backend suite."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_authority_integration_fixture_owner",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": ["paper-trader/backend/tests/test_backtest_admission.py"],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-authority-integration-fixture-correction/owner/report.md",
    "verdicts": ["CORRECTED"]
  }
}
---

# Phase 4 authority integration fixture correction

The third fresh integration owner reached every current authority seam but a
retained loader-tamper regression still indexes the retired assessment
projection. It raises `KeyError` before the loader can prove refusal. Correct
only that test path to the tagged `capability-assessment/2` fact envelope, prove
the real loader returns `RECEIPT_STALE`, and return to the evidence-only
integration gate. Do not change product behavior or weaken the assertion.
