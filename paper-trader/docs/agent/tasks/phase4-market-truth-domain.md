---
{
  "id": "phase4-market-truth-domain",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Implement canonical physical instrument, selector, temporal provider mapping, immutable market-truth snapshot, rulebook, and reconstruction contracts without touching provider adapters.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after point-in-time identity and rule semantics are deterministic, current-state substitution and invented contracts fail closed, and phase4-market-truth-persistence is eligible."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "canonical-identity",
    "point-in-time-truth",
    "derivatives"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "5. Canonical instrument and market-truth model",
        "10. Acceptance scenarios and refusals",
        "11. Deployment contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    }
  ],
  "dependency_gate": "phase4-numeric-validity-contract",
  "allowed_paths": [
    "paper-trader/backend/app/market_truth/__init__.py",
    "paper-trader/backend/app/market_truth/identity.py",
    "paper-trader/backend/app/market_truth/rulebook.py",
    "paper-trader/backend/tests/test_market_truth_domain.py",
    "paper-trader/docs/agent/tasks/phase4-market-truth-domain.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-market-truth-domain"
  ],
  "nonclaims": [
    "No provider adapter, historical acquisition, persistence, dynamic subscription, held-position rewrite, frontend, deployment, or live authority is implemented.",
    "RECONSTRUCTED truth never supports an OBSERVED ground-truth claim."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if work would duplicate accepted IR, validator, resolver, hash, registry, research lineage, execution binding, owner boundary, or authority."
  ],
  "stop_conditions": [
    "Canonical identity depends on a mutable provider token or symbol.",
    "Intervals overlap, decimal identity is ambiguous, or a current dump satisfies historical truth silently.",
    "Selector movement can rewrite held physical identity."
  ],
  "deployment_impact": {
    "classification": "application-domain-additive",
    "affected_dimensions": [
      "Application",
      "Serialization"
    ],
    "required_evidence": "Canonicalization, temporal overlap, digest, compatibility, and refusal evidence; persistence belongs to phase4-market-truth-persistence."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Physical identity, economic selector, and temporal provider mapping are distinct immutable values.",
    "Observed, reconstructed, and unknown quality is closed and identity-bearing.",
    "Overlap, gaps used as facts, token reuse ambiguity, invented contracts, and current-rule substitution fail.",
    "Continuous futures separate signal and tradable contracts with explicit roll/adjustment identity."
  ],
  "test_plan": [
    "Run backend/.venv/bin/python -m pytest -q backend/tests/test_market_truth_domain.py.",
    "Test token reuse, overlap, gaps, strike evolution, expiry, decimal canonicalization, reconstruction, roll, adjustment, and held identity.",
    "Kill mutations that drop effective time, snapshot digest, contract terms, or reconstruction quality."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_market_truth_domain_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/market_truth/__init__.py",
      "paper-trader/backend/app/market_truth/identity.py",
      "paper-trader/backend/app/market_truth/rulebook.py",
      "paper-trader/backend/tests/test_market_truth_domain.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-market-truth-domain/owner_integration/report.md",
    "verdicts": [
      "INTEGRATION"
    ],
    "max_rechecks": 0
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 market-truth domain

This is one durable implementation goal. It must retain full command output under its ignored evidence directory through `.codex/scripts/run_logged.py`.
