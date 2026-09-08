---
{
  "id": "phase5-programme-dispatch-correction",
  "phase": "phase5",
  "status": "accepted",
  "kind": "programme_authority_correction",
  "goal": "Repair the inherited programme-history and Phase 5 dispatcher-route contradictions without accepting failed reviews, weakening fail-closed dispatch, changing product behavior, or starting P5.2.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the six-row historical universe and four successor rewires are exact, all three missing Phase 5 kinds dispatch at their declared Sol-medium routes, unknown kinds still refuse, direct mutations redden and restore exact bytes, architecture and programme contracts pass, and one independent critical review plus the root review-only gate return SPEC PASS and QUALITY PASS."
  },
  "risk_tags": ["critical", "programme-authority", "dispatcher", "false-green"],
  "required_docs": [
    {
      "path": ".agent/runs/programme-history-correction-proposal/architecture.md",
      "sections": [
        "Decision and operator outcome",
        "Constraints",
        "Exact historical universe",
        "Smallest safe correction",
        "Phase 5 route completeness",
        "Required evidence before tracked correction acceptance"
      ]
    },
    {
      "path": ".agent/runs/phase5-programme-dispatch-correction/architecture-amendment.md",
      "sections": ["Phase 5 route-normalization amendment"]
    }
  ],
  "owner_authorization": "AUTHORIZE BOUNDED PHASE-5 PROGRAMME-DISPATCH CORRECTION",
  "allowed_paths": [
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase5-programme-dispatch-correction.md",
    ".codex/scripts/programme_dispatcher.py",
    ".codex/scripts/validate_agent_architecture.py",
    ".codex/tests/test_programme_dispatcher.py",
    ".codex/tests/test_programme_orchestration.py",
    ".codex/tests/test_repository_contract.py",
    ".agent/runs/phase5-programme-dispatch-correction"
  ],
  "nonclaims": [
    "No failed, stopped, or superseded review becomes accepted.",
    "No P5.2 product, test, migration, lifecycle, consumer, or authority work begins.",
    "No broker, order, money, live, provider, frontend, credential, deployment, production, or Phase 6 authority."
  ],
  "owner_gates": [
    "Stop before any product/runtime path, generic dispatcher fallback, failed-verdict rewrite, live authority, deployment, credentials, production data, frontend, provider, broker, order, money, or Phase 6 change."
  ],
  "stop_conditions": [
    "Any historical row, verdict, stopped report, accepted package, or acceptance hash changes.",
    "Any failed historical row is marked accepted or any executable blocked row is silently skipped.",
    "Any route beyond the exact five declared Sol-medium Phase 5 kinds is changed or added.",
    "P5.2 ceases to be the first unfinished stage or an unknown kind becomes dispatchable."
  ],
  "deployment_impact": {
    "classification": "none; local programme and developer orchestration only",
    "highest_claim": "locally_runnable",
    "nonclaim": "No shipped runtime, service, dependency, configuration, schema, migration, provider, deployment, or production behavior changes."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "xhigh",
    "reviewer": "gpt-5.6-sol",
    "reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 0,
  "assignments": [],
  "historical_universe": [
    "phase4-review",
    "phase4-review-recheck",
    "phase4-review-recovery",
    "phase4-final-review-2",
    "phase4-final-review-3",
    "phase4-final-review-4"
  ],
  "rewired_successors": [
    "phase4-review-correction",
    "phase4-v2-durable-graph-integration",
    "phase4-loader-authority-recovery-correction",
    "phase4-research-receipt-authority-architecture-correction"
  ],
  "phase5_routes": {
    "correction": ["gpt-5.6-sol", "medium"],
    "implementation_sequence": ["gpt-5.6-sol", "medium"],
    "critical_runtime_lifecycle": ["gpt-5.6-sol", "medium"],
    "independent_assurance": ["gpt-5.6-sol", "medium"],
    "critical_architecture": ["gpt-5.6-sol", "medium"]
  },
  "acceptance": [
    "The six rows leave executable stages and enter historical_blocked_reviews with original bytes represented field-for-field plus explicit non-acceptance classification.",
    "Only the four declared successor dependencies change, and every removed dependency remains an explicit historical predecessor.",
    "Executable orders are contiguous, dependencies are exact predecessors, and phase5-adv-006-runtime is the first unfinished stage.",
    "The five declared Phase 5 kinds dispatch at exact Sol-medium routes; every other unknown kind refuses.",
    "The real repository dispatcher returns monitor for one active goal and dispatch for zero active goals against the corrected tracked programme.",
    "Direct history, route, omission, false-acceptance, and restored-byte mutations fail on their named defects.",
    "All failed verdict and P5.1 acceptance hashes remain exact; no product path changes."
  ],
  "test_plan": [
    "Direct real-programme first-unfinished and dispatcher route checks.",
    "Synthetic exact-route and unknown-kind refusal matrix.",
    "Complete six-row history and four-successor coverage checks.",
    "Killed/restored row reinsertion, false acceptance, history-link omission, and runtime-route removal mutations.",
    "Architecture validator, repository/programme contracts, scoped status, protected hashes, and git diff --check.",
    "Frozen review package with one independent critical SPEC/QUALITY verdict and root review-only gate."
  ],
  "review": {
    "required": true,
    "assignment_id": "phase5_programme_dispatch_correction_reviewer",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase5-programme-dispatch-correction.md",
      ".codex/scripts/programme_dispatcher.py",
      ".codex/scripts/validate_agent_architecture.py",
      ".codex/tests/test_programme_dispatcher.py",
      ".codex/tests/test_programme_orchestration.py",
      ".codex/tests/test_repository_contract.py",
      ".agent/runs/phase5-programme-dispatch-correction"
    ],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/phase5-programme-dispatch-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "acceptance_record": {
    "decision": "ACCEPTED_AFTER_FOCUSED_RECHECK",
    "package": ".agent/runs/phase5-programme-dispatch-correction/review/accepted-package.json",
    "package_sha256": "326937475e29b4604cd66da5a199fdeec8e9c799f51fcc09a59f1d74e444baeb",
    "first_verdict": ".agent/runs/phase5-programme-dispatch-correction/review/verdict.json",
    "first_verdict_sha256": "93ebb22140588541b0260f8b9378b863a2291b56d8d30446e678a9c1f8a927c9",
    "focused_recheck": ".agent/runs/phase5-programme-dispatch-correction/review/recheck-verdict.json",
    "focused_recheck_sha256": "9f571f133bfa752b7675095319d6603abd0323ae10a53a7c4c3ad70ee4ad1065",
    "root_acceptance": ".agent/runs/phase5-programme-dispatch-correction/root-acceptance/review.md",
    "root_acceptance_sha256": "1ea920c157e6a61b4729b757a2989aef0a645236f64a59b9ade73bafc75612fb",
    "spec": "PASS",
    "quality": "PASS"
  },
  "protected_evidence": {
    ".agent/runs/phase5-graph-paper-attribution-schema/review/original-package.json": "811b71ef4cd149235c0b34ffbc263236bcd05b2aa59d6983c3128b5c26fd1048",
    ".agent/runs/phase5-graph-paper-attribution-schema/review/accepted-package.json": "53f624d11914c5f4dcea8a1a9f405f1169f5fc7485fede5b298be9443f5af5af",
    ".agent/runs/phase5-graph-paper-attribution-schema/review/verdict.json": "d00e4c786684b71fb61a8ea915b2725031cdbff80b3abe7c10ef190dadde44e1",
    ".agent/runs/phase5-graph-paper-attribution-schema/review/recheck-verdict.json": "c2faea10cfc86ecb7cbb675fdd5d0fbd2a8a693e16d896f383b308257080533a",
    ".agent/runs/phase5-graph-paper-attribution-schema/root-acceptance/review.md": "f853e7c4b50107cba9a9193cdc25b10bfe2423168e849118b26eda4d52f35d9b",
    ".agent/runs/phase5-programme-dispatch-correction/authorized-proposal.md": "de2178afbbaad53f157942438a0b89a51296570f9916d47026f504d4462eee3e",
    ".agent/runs/phase5-programme-dispatch-correction/architecture-amendment.md": "3373c3a84f75e627a4e56e148bfa8e61b10cec26f082c5d7d2cc89dbe3e89a65"
  }
}
---

# Phase 5 programme-dispatch correction

This owner-authorized correction normalizes historical programme rows and the exact Phase 5 route table only. It cannot change Strategy OS product or runtime behavior and cannot start P5.2.
