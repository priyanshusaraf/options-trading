---
{
  "id": "phase4-typed-market-authority-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Close CUR-C4 by reconstructing and verifying typed market-truth, conformance, capability-profile, and capability-assessment authority from execution 0038 facts.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The accepted Phase 4 authority-foundation architecture correction authorizes this serial CUR-C4 correction only after its dependency gate. Authority is limited to the listed typed-authority loader, test, and evidence paths; schema, provider adapters, runtime enablement, frontend, deployment, production, live, and money boundaries remain closed.",
    "stopping_condition": "Complete only after typed market-truth, conformance, CapabilityProfile, and CapabilityAssessment facts reconstruct through their sole authoritative loaders, preserve exact owner/provider/product/contract/quality identity, and refuse malformed, forged, stale, cross-owner, or dependency-mismatched state before downstream use, with direct evidence for every assigned adversarial row. Stop with the goal active at any named owner gate or unresolved acceptance failure."
  },
  "risk_tags": ["critical", "authority", "market-truth", "capability"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["5. Canonical instrument and market-truth model", "7. Data requirement and provider capability contracts", "9. Ownership, authority, and persistence", "13. Authority-foundation correction contract"]}, {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["8. Authority-correction serial route"]}],
  "dependency_gate": "phase4-canonical-market-identity-correction",
  "allowed_paths": [
    "paper-trader/backend/app/market_truth/rulebook.py",
    "paper-trader/backend/app/market_truth/authority.py",
    "paper-trader/backend/app/market_data/capability.py",
    "paper-trader/backend/app/market_data/authority.py",
    "paper-trader/backend/tests/test_phase4_typed_market_authority.py",
    ".agent/runs/phase4-typed-market-authority-correction"
  ],
  "nonclaims": ["Consumes execution 0038 without editing schema/model paths.", "No real-provider conformance, credentials, provider selection, runtime, deployment, live, or money authority."],
  "owner_gates": ["Stop if 0038 model-DDL parity is absent or if a token, copied digest/status, generic JSON, same-process object, or monkeypatch is needed for authority."],
  "stop_conditions": ["Typed facts cannot reconstruct from persisted dependencies after process death; entitlement and conformance collapse; copied columns can disagree; assessment results are accepted without recomputation."],
  "deployment_impact": {"classification": "execution-authority-loader-hardening-on-0038", "required_evidence": "No new schema/dependency/config/service; exact 0038 prerequisite; SQLite and PostgreSQL loader parity; fresh-process reconstruction and refusal."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default"},
  "parallel_budget": 0,
  "assignments": [],
  "adversarial_rows": ["ADV-001", "ADV-009", "ADV-010", "ADV-016", "ADV-018", "ADV-020", "ADV-022", "ADV-023", "ADV-024", "ADV-025", "ADV-026", "ADV-027"],
  "acceptance": [
    "market-truth-snapshot/2 reconstructs typed records and enforces knowledge/effective time, quality, evidence, gaps, and copied-column equality",
    "provider-conformance/1 remains separate from owner-contract entitlement and capability-profile/2 requires both",
    "capability-assessment/2 loads plan, registry, profile, dataset projection, truth, policy, and algorithm then recomputes exact coverage/results",
    "forged self-consistent rows, wrong owner/mode/product/contract, stale facts, changed quality, missing evidence, and column disagreements refuse",
    "fresh-process loaders return typed facts without constructor tokens and reach the real assessment consumer"
  ],
  "test_plan": ["Produce one real-path ledger entry for every adversarial_rows ID, including seam, process boundary, expected refusal/identity change, observed result, and artifact address; focused typed loader and assessment mutations; fresh-process SQLite and PostgreSQL parity; bounded query evidence; protected hashes and scoped diff."],
  "review": {"required": false, "assignment_id": "phase4_typed_market_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/market_truth/rulebook.py","paper-trader/backend/app/market_truth/authority.py","paper-trader/backend/app/market_data/capability.py","paper-trader/backend/app/market_data/authority.py","paper-trader/backend/tests/test_phase4_typed_market_authority.py"], "exclude_paths": [], "output": ".agent/runs/phase4-typed-market-authority-correction/owner/report.md", "verdicts": ["IMPLEMENTATION"]}
}
---

# Phase 4 typed market authority correction

Use the installed `0038` rows. Reconstruct the closed documents in design §13.1 and reconcile every duplicate. Never treat canonical shape or a matching outer address as proof of canonical construction. Design §13.3 row IDs in `adversarial_rows` are mandatory individual evidence cases.
