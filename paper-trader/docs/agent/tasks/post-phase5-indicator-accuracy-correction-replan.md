---
{
  "id": "post-phase5-indicator-accuracy-correction-replan",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_architecture_replan",
  "goal": "Design the smallest versioned correction programme for every rejected or unverified analytical component without creating a second registry, silently changing accepted semantic version 1, or starting Phase 6.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after all 125 components have retrievable source/version authority, exact parameter/output/warmup/missing/session contracts, an explicit keep/v2-replace/refuse decision, dependency-ordered correction and assurance capsules, legacy-v1 disposition, cache/result invalidation ownership, TradingView access disposition, and a final accuracy review gate."
  },
  "risk_tags": [
    "critical",
    "architecture",
    "research-integrity",
    "semantic-versioning",
    "complete-universe"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-audit/report.md",
      "sections": [
        "Complete-universe result",
        "Blocking findings",
        "Accuracy thresholds",
        "Decision and smallest successor"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md",
      "sections": [
        "First-party node contract",
        "Verification and complete-universe gates"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-audit",
  "allowed_paths": [
    ".agent/runs/post-phase5-indicator-accuracy-correction-replan",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-correction-replan.md",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-*.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    ".codex/tests/test_programme_orchestration.py"
  ],
  "protected_paths": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "No product/test correction, component-v2 implementation, dependency adoption, TradingView access, provider, deployment, production, live, order, money, frontend or Phase 6 work."
  ],
  "owner_gates": [
    "Requires explicit owner authorization before creating its durable goal.",
    "Stop for legal/licence direction before any private TradingView library use.",
    "Stop before any in-place version-1 semantic change or product/test edit."
  ],
  "stop_conditions": [
    "Any component is omitted; v1 changes silently; source provenance is opaque; a correction wave overlaps another writer; cache/result invalidation lacks an owner; Phase 6 or deployment work starts."
  ],
  "deployment_impact": {
    "classification": "read-only architecture replan",
    "required_evidence": "Assign every later semantic/runtime/cache/deployment impact to an exact correction, assurance, Phase 6 or release capsule."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "One authoritative 125-component source and semantic matrix exists.",
    "Every rejected component receives a versioned keep/replace/refuse decision and exact correction owner.",
    "Every unverified component receives an exact oracle owner or typed unavailable disposition.",
    "No accepted v1 graph, result or cache identity is silently reinterpreted.",
    "Core math, recursive state, multi-output, session/data and remaining-oracle waves have disjoint ownership and complete-universe assurance.",
    "TradingView is either approved as a secondary export oracle or explicitly excluded; no unofficial path exists."
  ],
  "test_plan": [
    "Validate all 125 source and semantic records.",
    "Validate version/address/cache/result migration decisions.",
    "Validate correction-wave path ownership and serial dependencies.",
    "Validate exact external-source licences and access constraints.",
    "Validate protected product/test hashes remain unchanged."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_correction_replan_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/review-package.json",
    "review_paths": [
      ".agent/runs/post-phase5-indicator-accuracy-audit",
      ".agent/runs/post-phase5-indicator-accuracy-correction-replan",
      "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-*.md"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/report.md",
    "verdicts": [
      "ARCHITECTURE_REPLAN"
    ]
  },
  "owner_authorization": "AUTHORIZE POST-PHASE-5 INDICATOR ACCURACY CORRECTION REPLAN",
  "acceptance_receipt": {
    "verdict": "ARCHITECTURE_REPLAN PASS",
    "report_sha256": "bace972ec97f6602e2a765bf6e95bf5ab1eabaa51c670e2e1a0222bcf020a4ed",
    "matrix_sha256": "95050aec6ab623e9f0fb606a0f5547f90dce93fc20a9d9944c128152c1394959",
    "components": 125,
    "decisions": {
      "KEEP": 23,
      "REPLACE_V2": 85,
      "REFUSE": 17
    },
    "product_write_count": 0,
    "numerical_accuracy_claim": false,
    "next_owner_gate": "AUTHORIZE INDICATOR ACCURACY CONTRACT FOUNDATION"
  }
}

---

# Post-Phase-5 indicator accuracy correction replan

This owner-gated replan may design versioned corrections only. It cannot implement
or reinterpret any accepted indicator version.
