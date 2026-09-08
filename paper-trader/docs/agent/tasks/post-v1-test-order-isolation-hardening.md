---
{
  "id": "post-v1-test-order-isolation-hardening",
  "phase": "assurance-tooling",
  "status": "deferred",
  "goal": "Remove shared-state and order dependence from the repository-wide single-process backend and research suite before anyone makes a new full-suite currentness claim.",
  "owner": "assurance-tooling-maintainer",
  "deadline": "Before the next claim that `.venv/bin/python -m pytest -q tests research_tests` passes in one process.",
  "trigger_evidence": ".agent/runs/phase1-4-foundation-direct-closure/root/root-phase-gate-backend-research.log",
  "risk_tags": ["deferred", "assurance-tooling", "test-isolation"],
  "required_docs": [],
  "containment": [
    "The finite migration, numeric, Phase 1-4 subsystem, and integration selectors run from fresh local test state and pass on current frozen bytes.",
    "Dashboard and IR edit families that failed in the repository-wide order pass when rerun independently from fresh local test state.",
    "The broad failure produced false negatives and setup errors; no required direct test produced a false pass."
  ],
  "allowed_paths": [
    "paper-trader/backend/tests",
    "paper-trader/backend/research_tests",
    "paper-trader/backend/conftest.py",
    "paper-trader/backend/tests/conftest.py",
    "paper-trader/backend/research_tests/conftest.py",
    ".agent/runs/post-v1-test-order-isolation-hardening"
  ],
  "acceptance": [
    "Reproduce the order-dependent failure from a clean local environment and identify each leaked process, environment, database, application, cache, or global state boundary.",
    "Add direct fixture-isolation regressions without changing product behavior or weakening assertions.",
    "The exact repository-wide backend and research command passes twice from separate clean local test roots with identical collection and no order-sensitive result.",
    "No production, provider, frontend, deployment, live, order, or money behavior changes."
  ],
  "nonclaims": [
    "This deferred assurance-tooling work is not a Phase 1-4 product, migration, numeric, Phase 5, release, deployment, production, live, or money gate.",
    "The failed broad run is not accepted as a passing suite and remains immutable evidence."
  ],
  "owner_gates": ["Stop before product-behavior changes, assertion weakening, production data, deployment, live, order or money scope."],
  "stop_conditions": ["A false-positive required direct test is discovered; fixture isolation requires product semantic changes; a second failed correction needs replanning."],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "test_plan": ["Reproduce exact order failure; isolate each leaked state boundary; add direct fixture regressions; run the full command twice from separate clean roots; compare collection/results and git diff."],
  "review": {"required": false, "assignment_id": "post_v1_test_order_isolation_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/conftest.py", "paper-trader/backend/tests/conftest.py", "paper-trader/backend/research_tests/conftest.py", "paper-trader/backend/tests", "paper-trader/backend/research_tests"], "exclude_paths": [], "output": ".agent/runs/post-v1-test-order-isolation-hardening/report.md", "verdicts": ["ISOLATION"]}
}
---

# Post-V1 test-order isolation hardening

The repository-wide single-process suite can inherit state across unrelated files. Current direct and affected subsystem tests run from fresh state and do not depend on this deferred tooling correction. This capsule owns the next full-suite currentness claim; it cannot expand product behavior.
