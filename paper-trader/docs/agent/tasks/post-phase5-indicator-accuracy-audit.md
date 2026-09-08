---
{
  "id": "post-phase5-indicator-accuracy-audit",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "independent_numerical_assurance",
  "goal": "Audit the complete accepted 125-component Type 2/4 analytical catalogue against authoritative independent numerical and behavioral references, quantify accuracy honestly, and define the smallest correction boundary before Phase 6.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after all 125 components have an explicit oracle classification, every numerical or stateful indicator is exercised on hostile deterministic fixtures, supported external-reference comparisons report exact tolerances and warmup policy, unverified or mismatched semantics are rejected as accuracy claims, product and product-test bytes remain unchanged, and any correction is assigned to one exact successor capsule before Phase 6."},
  "risk_tags": ["critical", "read-only", "research-integrity", "indicator-accuracy", "complete-universe"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["First-party node contract", "Verification and complete-universe gates"]}, {"path": "paper-trader/docs/reports/phase5-v1-catalogue.json", "sections": []}],
  "dependency_gate": "phase5-review",
  "allowed_paths": [".agent/runs/post-phase5-indicator-accuracy-audit", "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-audit.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md", ".codex/tests/test_programme_orchestration.py"],
  "protected_paths": ["paper-trader/backend/app/ir/first_party/analytical.py", "paper-trader/backend/tests/test_phase5_first_party_analytical_catalogue.py", "paper-trader/backend/research_tests/test_phase5_research_execution.py", ".agent/runs/phase5-research-parity-assurance/owner/independent_analytical_oracle.py"],
  "nonclaims": ["No product/test correction, semantic-version decision, new dependency, TradingView licence or access claim, provider credential/network integration, deployment, production, live, order, money, frontend or Phase 6 work."],
  "owner_gates": ["Stop before using unofficial TradingView endpoints, private/proprietary library bytes, credentials, scraped values or licence-sensitive code; stop before changing any accepted indicator semantics or product/test path."],
  "stop_conditions": ["The 125-component universe is sampled rather than complete; expected values call the product evaluator; a smooth-only fixture hides seeding or discontinuity defects; warmup/undefined differences are silently discarded; an external oracle lacks version/licence/provenance; any product/test byte changes."],
  "deployment_impact": {"classification": "read-only assurance", "highest_claim": "local diagnostic only", "required_evidence": "No operational dimension changes; Phase 6 remains blocked until every accuracy finding has exact disposition."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All 125 accepted analytical components are classified as exact field/transform, official-library comparable, primary-formula comparable, environment/session dependent, capability gated, or unverified.", "Official TA-Lib comparison runs in a disposable environment without adoption and reports overlap, warmup alignment, maximum absolute/relative error and exact mismatch locations.", "Primary-source oracles cover material non-TA-Lib indicators, with exact state/direction comparisons where numeric tolerance is inappropriate.", "Fixtures include monotonic, oscillating, flat, discontinuous/gapped, missing/invalid, multi-session and randomized seeded series plus prefix-causality checks.", "TradingView is used only through an official lawful export surface if access is available; lack of access is reported and never replaced by an unofficial API.", "Every mismatch or unverifiable claim blocks accuracy acceptance and names one smallest successor correction."],
  "test_plan": ["Freeze protected hashes and derive the complete 125-component universe from the accepted catalogue.", "Run disposable official TA-Lib 0.7.1 overlap comparisons on deterministic hostile fixtures.", "Run independent primary-formula and session/state oracles for the remaining material indicators.", "Audit declared parameters, output shapes, warmup, missing/undefined handling, prefix causality and semantic aliases.", "Seal exact results, accuracy thresholds, source/licence map, protected post-hashes and correction proposal."],
  "review": {"required": false, "assignment_id": "post_phase5_indicator_accuracy_audit_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/runs/post-phase5-indicator-accuracy-audit/review-package.json", "review_paths": ["paper-trader/backend/app/ir/first_party/analytical.py", ".agent/runs/post-phase5-indicator-accuracy-audit"], "exclude_paths": ["paper-trader/frontend"], "output": ".agent/runs/post-phase5-indicator-accuracy-audit/report.md", "verdicts": ["ACCURACY"]},
  "audit_result": {"verdict": "ACCURACY FAIL", "report": ".agent/runs/post-phase5-indicator-accuracy-audit/report.md", "catalogue_components": 125, "verified_strict": 25, "rejected": 60, "unverified": 40, "prefix_checks_passed": 2500, "product_test_changes": 0, "findings": ["P5-ACC-001", "P5-ACC-002", "P5-ACC-003", "P5-ACC-004", "P5-ACC-005", "P5-ACC-006", "P5-ACC-007"], "successor": "post-phase5-indicator-accuracy-correction-replan"}
}
---

# Post-Phase-5 indicator accuracy audit

This is a read-only numerical-assurance gate. It does not reopen accepted product
bytes or start Phase 6. Any mismatch must be rejected and routed to a separately
authorized correction capsule.
