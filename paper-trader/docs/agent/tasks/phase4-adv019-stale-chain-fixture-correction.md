---
{
  "id": "phase4-adv019-stale-chain-fixture-correction",
  "phase": "phase4",
  "status": "ready",
  "goal": "Repair the retained ADV-019 lifecycle regression so the actual Phase 4 loader evaluates a complete persisted two-plane authority chain, refuses every named stale dependency, and lets only current bytes reach the terminal runtime boundary.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded work needed to finish Phase 4. The fourth fresh matrix owner proved that the retained ADV-019 test omits the required two-plane authority context and therefore returns PHASE4_CONTEXT_REQUIRED for both stale and current databases. Authority is limited to that retained test and ignored evidence. Product, schema, migration, other tests, programme, CURRENT, package, provider, frontend, runtime, deployment, production, live, and money paths remain closed.",
    "stopping_condition": "Complete only after the retained node builds a genuine persisted execution and research authority chain through current constructors; invokes the actual load_verified_admission seam with a ReclaimAuthorityContext, a real research Session, and one aware cutoff; proves each ADV-019 topology, registry, implementation, dataset, truth, capability, policy, owner, product, and contract stale mutation refuses before terminal runtime and every named side effect; and proves only the exact current companion reaches V2_RUNTIME_UNAVAILABLE. The retained node and its smallest adjacent current loader/topology companions must pass without deselection or mocked decisive seams. Stop with the goal active if product behavior must change, a required stale class cannot be represented through current persisted facts, or another path is needed.",
    "evidence_stopping_condition": "Retain the pre-edit false-green showing stale and current both return PHASE4_CONTEXT_REQUIRED; record the exact post-edit commands, cwd, collected node IDs, exit status, observed refusal for every named stale class, current-companion V2_RUNTIME_UNAVAILABLE, absence of manual preverification and mocked decisive seams, the corrected test diff/hash, protected hashes, scoped diff check, and a concise report. Earlier matrix-owner partial rows and rejected Luna output receive no acceptance credit."
  },
  "risk_tags": ["test-evidence", "typed-authority", "stale-evidence", "fresh-process", "integration"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": ["9. Ownership, authority, and persistence", "10. Failure and refusal semantics", "13.1 Canonical fact and equality matrix", "13.2 Persistence, reconstruction, and refusal", "13.3 Adversarial verification matrix", "13.5 Stale evidence and revalidation"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": ["5. Verification cadence", "8. Authority-correction serial route"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["DP-002", "DP-003", "DP-005", "DP-008"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Current verdict", "Open obligations", "Phase 4 ownership"]
    }
  ],
  "dependency_gate": "phase4-authority-transaction-correction",
  "allowed_paths": [
    "paper-trader/backend/tests/test_phase4_resolved_topology_identity.py",
    ".agent/runs/phase4-adv019-stale-chain-fixture-correction"
  ],
  "nonclaims": [
    "This correction changes no product behavior and does not complete the adversarial matrix, accept Phase 4, build a review package, or establish deployability, production readiness, provider correctness, runtime authority, frontend readiness, money authority, or live authority.",
    "No product, schema, migration, dependency, configuration, service, provider, broker, credential, infrastructure, runtime-enablement, frontend, deployment, programme, CURRENT, or review-package path is authorized.",
    "The stopped matrix owner's ADV-001 through ADV-014 results remain partial historical diagnostics. A fresh matrix owner must restart all 27 rows from current bytes after root acceptance of this correction."
  ],
  "owner_gates": [
    "Stop if a complete two-plane fixture cannot be built through existing typed constructors and persistence seams without changing product behavior.",
    "Stop if the actual loader with complete current context does not distinguish a named stale mutation from the current companion, or if the expected refusal is architecturally ambiguous.",
    "Stop if any path outside the single retained test and ignored evidence must change."
  ],
  "stop_conditions": [
    "The test performs manual authority preverification, mocks the decisive loader/reconstruction seam, accepts PHASE4_CONTEXT_REQUIRED as ADV-019 evidence, or weakens any stale-chain assertion.",
    "Any named ADV-019 mutation is omitted, current bytes do not reach exact V2_RUNTIME_UNAVAILABLE, the focused selectors fail, protected hashes change, or the scoped diff contains product or unrelated test edits."
  ],
  "deployment_impact": {
    "classification": "test-only-current-authority-lifecycle-correction",
    "required_evidence": "No runtime, schema, migration, dependency, configuration, service, provider, frontend, or deployment change. Prove only that the retained ADV-019 regression exercises the actual complete current authority chain and distinguishes every named stale dependency from exact current bytes."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "preserve the pre-edit current-byte observation that stale and current both stop at PHASE4_CONTEXT_REQUIRED",
    "replace the incomplete execution-only fixture with a genuine persisted two-plane authority fixture built through current constructors and writers",
    "invoke the actual repository loader with a typed ReclaimAuthorityContext, real research Session, and one aware cutoff; do not manually preverify or mock the decisive seam",
    "prove topology, registry, implementation, dataset, truth, capability, policy, owner, product, and contract stale mutations refuse before terminal runtime and side effects",
    "prove only the exact unmutated current companion reaches V2_RUNTIME_UNAVAILABLE",
    "run the retained node and smallest adjacent current loader/topology companions without skip, xfail, deselection, or product changes",
    "record exact commands, cwd, collected node IDs, exits, observations, test diff/hash, protected hashes, scoped diff check, and nonclaims"
  ],
  "test_plan": [
    "Use the backend project virtualenv and .codex/scripts/run_logged.py for every credited command.",
    "Reuse current complete two-plane fixture construction and current loader call patterns from retained Phase 4 tests; do not copy a private authority implementation into the test.",
    "Keep each named stale dependency independently attributable in test output or a machine-readable evidence table, and bind it to the real loader observation.",
    "Run the exact retained node first, then the smallest adjacent current topology/loader selector needed to detect fixture drift; do not run a broad backend suite.",
    "Audit the exact single-test-file diff and frozen protected hashes before reporting."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_adv019_stale_chain_fixture_owner",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": ["paper-trader/backend/tests/test_phase4_resolved_topology_identity.py"],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-adv019-stale-chain-fixture-correction/owner/report.md",
    "verdicts": ["CORRECTED"]
  }
}
---

# Phase 4 ADV-019 stale-chain fixture correction

The retained ADV-019 lifecycle test currently stops at the Phase 4 context
precondition for both its stale and current databases. Replace that incomplete
fixture with the current complete two-plane authority lifecycle, then make the
actual loader distinguish every named stale dependency from exact current
bytes. This is a test-evidence correction only. It does not authorize a product
shim, manual preverification, a mocked decisive seam, or any Phase 4 completion
claim.
