---
{
  "id": "strategy-os-v0-robustness-lab",
  "lineage_id": "strategy-os-v0-robustness-parameter-evaluation-seam-replan",
  "programme_stage": "strategy-os-v0-robustness-lab",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_parameter_evaluation_seam_replan",
  "goal": "Define the smallest safe owner-scoped seam that lets the accepted saved-V2 executor evaluate a complete bounded set of ephemeral parameter candidates against the same verified data, resource, causal and money authorities without a second evaluator or a mutable graph version.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The post-bridge seam failure is directly reproduced, the exact fact-loss and path-collision map is sealed, one closed successor interface and exact implementation ownership are recorded, protected product bytes remain unchanged, architecture passes, and one Critical reviewer returns SPEC PASS / QUALITY PASS."},
  "observable_outcome": "The existing parameter-neighbourhood implementation capsule can be resumed with explicit authority to extend the saved-V2 request/descriptor and to pass one operation-scoped candidate-evaluation capability into the existing research orchestrator. No research result or user-facing control is created by this replan.",
  "risk_tags": ["critical", "architecture", "research-integrity", "v2-ir", "locked-oos", "market-time", "resource-bounds", "tenant-isolation", "money"],
  "required_skills": ["strategyos-repo-orientation", "architecting-strategy-os-phases", "research-validity-audit", "anti-lookahead-and-market-truth", "architecture-invariant-audit", "resource-plan-and-cost-audit", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-v2-research-backtest-bridge-correction", "strategy-os-v0-robustness-parameter-neighborhood-integration"],
  "dependency_gate": {"accepted_bridge_closure": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-correction/closure-seal.json", "accepted_bridge_closure_sha256": "eda0f47275dad84dca5bb34b4f158d2815bf0643328b8388778c16646ab7043a", "accepted_bridge_recheck_sha256": "6613931a6b37e8ada71b55a79edd3ba89681417fec90bfef945cfd97f3a8cedb", "blocked_parameter_report": ".agent/runs/strategy-os-v0-robustness-parameter-neighborhood-integration/backend/report.md", "blocked_parameter_report_sha256": "cf5433c49eef3d26e2510ac7e15e800b5d1a45720da1dc7d893c7872fb0ffe31", "independent_red_sha256": "8c1f5d435e826c0f2d1d618b06a84e063db5ff697ff99fef435e0512560f9d13", "execution_head": "0051", "research_head": "0011"},
  "decision": {
    "verdict": "KEEP + HARDEN",
    "reason": "The accepted saved-V2 evaluator, dataset projection, resource admission, output adapter, walk-forward, gates and money authorities are sufficient. The missing boundary is an operation-scoped capability that retains their executable context for validated ephemeral candidates.",
    "rejected_options": [
      "Reusing the baseline signal adapter, because it intentionally rejects parameter overrides and would ignore every candidate.",
      "Rebuilding the V2 authority chain in run.py or parameter_integration.py, because that creates a second data-plan, resource, resolver or evaluator authority.",
      "Publishing candidate graph versions, because neighbourhood candidates are diagnostic ephemeral trials and must not mutate user-authored state.",
      "Adding a generic workflow or new persistence table, because the existing one-item durable operation and terminal envelope are sufficient."
    ]
  },
  "successor_contract": {
    "request_identity": "V2GraphResearchOperationRequest gains one optional closed robustness object containing parameter_neighborhood. Absence preserves the accepted request, operation descriptor and ExperimentSpec bytes. Presence is retained in the one durable experiment descriptor and changes request/operation/ExperimentSpec identity. Unknown, partial, disabled-with-work and over-bound shapes refuse before enqueue or evaluation.",
    "candidate_capability": "Inside execute_v2_graph_operation, after exact owner/version/admission/dataset/input-binding/eligibility/ResourcePlan reconstruction, create one private operation-scoped callable. It receives only a normalized complete axis point, applies the existing ordered set_parameter batch to the saved baseline through apply_semantic_commands, validates and resolves the returned immutable V2 document with REGISTRY, recompiles and verifies its data plan/eligibility/ResourcePlan against the same persisted projection and truth facts, calls only execute_research with the same causal policy and durable cancellation fence, and returns an accepted defensive V2RuntimeStrategy plus candidate address lineage. It writes or publishes no graph.",
    "orchestrator_boundary": "run_experiment receives the optional closed request, immutable baseline V2 document and candidate capability only from the saved-V2 path. It binds the request and method identities into the recipe before ExperimentSpec creation. The parameter integration enumerates the complete in-bounds grid, preflights candidate count times dataset bars, invokes each point once, and scores each returned strategy through the existing chronological walk-forward, gates, next-open fills, corrected charges and identical fold boundary contract.",
    "money_and_method": "Each candidate OOS score is the signed sum of accepted trade net_pnl converted with the existing monetary_minor authority; no float truncation or charge-free score is accepted. The existing pure analyze_parameter_neighborhood function consumes the complete population and user thresholds. No candidate may tune or replace the baseline using locked OOS evidence.",
    "durability_and_read": "The complete method payload/address or a typed bounded unavailable fact enters the existing terminal evidence transaction. Restart reconstructs the optional descriptor and candidate capability from exact saved authorities. A separate authenticated owner-private no-store endpoint semantically reconstructs AVAILABLE evidence and distinguishes not requested, disabled, running, failed, unavailable, legacy and corrupt states.",
    "resource_policy": "The existing limits remain 1..4 axes, at most 81 complete local points, at most 2,000,000 candidate-bar evaluations and at most 2,000,000 terminal-evidence bytes. Candidate graph ResourcePlan is rechecked per point. These are admission limits, not production capacity claims."
  },
  "successor_ownership": {
    "implementation_capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-parameter-neighborhood-integration.md",
    "newly_authorized_source": ["paper-trader/backend/research/orchestrator/v2_operation.py"],
    "newly_authorized_tests": ["paper-trader/backend/research_tests/test_v2_research_operation.py", "paper-trader/backend/research_tests/test_v2_graph_experiment_bridge.py", "paper-trader/backend/research_tests/test_v2_output_backtest_adapter.py", "paper-trader/backend/research_tests/test_phase5_research_execution.py", "paper-trader/backend/research_tests/test_v2_resource_policy.py", "paper-trader/backend/tests/test_research_operation_routes.py"],
    "still_protected": ["paper-trader/backend/research/evaluation", "paper-trader/backend/research/strategy/v2_runtime_strategy.py", "paper-trader/backend/app/editor", "paper-trader/backend/app/ir", "paper-trader/backend/app/backtest", "paper-trader/backend/app/engine", "paper-trader/backend/research/domain", "paper-trader/backend/scripts/research_run.py", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"]
  },
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-robustness-parameter-neighborhood-integration/backend/report.md", "sections": ["Independent post-bridge RED", "Exact current call chain and lost facts", "Minimal candidate-evaluation interface required", "Exact ownership expansion required by a successor capsule", "Why wrapping run.py alone duplicates authority"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-correction.md", "sections": ["supported_contract", "focused_recheck", "nonclaims"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-parameter-neighborhood-integration.md", "sections": ["contract", "acceptance", "owner_gates", "stop_conditions"]},
    {"path": "paper-trader/backend/research/orchestrator/v2_operation.py", "sections": ["closed descriptor parser", "execute_v2_graph_operation", "saved V2 strategy adapter boundary"]},
    {"path": "paper-trader/backend/research/orchestrator/run.py", "sections": ["run_experiment recipe", "walk-forward and locked OOS", "terminal evidence"]},
    {"path": "paper-trader/backend/research/robustness/neighborhood.py", "sections": ["expected_local_points", "analyze_parameter_neighborhood", "reconstruct_parameter_neighborhood"]}
  ],
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-parameter-evaluation-seam-replan.md",
    "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-parameter-neighborhood-integration.md",
    ".agent/runs/strategy-os-v0-robustness-parameter-evaluation-seam-replan",
    ".agent/runs/strategy-os-v0-robustness-parameter-neighborhood-integration/backend"
  ],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-robustness-parameter-evaluation-seam-replan.md", ".agent/runs/strategy-os-v0-robustness-parameter-evaluation-seam-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "acceptance": [
    "The exact current saved-V2 request, descriptor, evaluator and run boundary are mapped with direct source evidence; the independent AST probe fails all three minimum seam assertions and no product/test byte changes.",
    "The successor keeps one validator, resolver, data-plan compiler, graph eligibility authority, ResourcePlan authority, execute_research evaluator, output adapter, walk-forward, gate and money engine. The operation-scoped callable is capability narrowing, not a second evaluator.",
    "Absent optional settings preserve accepted request/descriptor/ExperimentSpec identities. Present settings are closed, durable, owner-scoped, content-bound and reconstructible after restart before candidate work.",
    "Every candidate originates from apply_semantic_commands over the immutable baseline and is revalidated against the same saved authority, verified availability projection, policy, ResourcePlan and cancellation fence. No candidate is persisted or published as a graph version.",
    "The complete grid, identical locked-OOS fold boundaries, cost-inclusive exact paise scores, existing hard-gate pass state, complete-population method and terminal semantic reconstruction each have a named rejection test and deliberate ablation in the successor.",
    "No schema, migration, dependency, provider, frontend, monitoring, paper/live execution or deployment path is added. The expanded path list is exact and the prior accepted bridge remains a regression gate.",
    "Architecture passes, replan artifacts are content-sealed, and one independent Critical reviewer returns SPEC PASS / QUALITY PASS before implementation resumes.",
    "No parameter-neighbourhood availability, production capacity, deployment, statistical significance, future performance, profitability or V0 completion claim."
  ],
  "test_plan": [
    "Review the three-failure AST RED, exact call-chain map and pre/final product hash equality; reject the replan if any allowed-only wrapper can truthfully preserve the existing authority chain.",
    "Review the closed request/descriptor identity, operation-scoped capability, complete-grid/fold/money contracts and exact ownership against the accepted bridge and pure method.",
    "Validate architecture and package fingerprint, then route one Critical reviewer. No product test or implementation command belongs to this read-only replan."
  ],
  "risk_classification": {"tier": "Critical", "reason": "A candidate seam can duplicate evaluation authority, leak future data, lose cancellation fencing, change locked OOS folds or present charge-free stability evidence."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_robustness_parameter_evaluation_seam_replan_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "The replan expands ownership into the accepted saved-V2 executor at a causal, resource and money-adjacent research boundary.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-robustness-parameter-evaluation-seam-replan/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-robustness-parameter-evaluation-seam-replan.md", "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-parameter-neighborhood-integration.md", ".agent/runs/strategy-os-v0-robustness-parameter-evaluation-seam-replan", ".agent/runs/strategy-os-v0-robustness-parameter-neighborhood-integration/backend"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"], "output": ".agent/runs/strategy-os-v0-robustness-parameter-evaluation-seam-replan/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["This replan authorizes documentation, evidence and exact future path reservation only. It does not authorize product/test implementation before Critical acceptance. The successor may change v2_operation.py only to retain the optional descriptor and expose the operation-scoped candidate capability defined here; any schema/migration, new queue/table, second evaluator, provider path, graph publication, execution authority or generic optimization surface stops."],
  "stop_conditions": ["The capability cannot keep candidate mutation, validation, resource admission, causal evaluation and cancellation under the accepted saved-V2 authority without another persistent model or evaluator.", "Absent parameter settings change accepted V2 request/descriptor/ExperimentSpec bytes or V1/stationary-bootstrap behavior.", "Identical locked-OOS folds and cost-inclusive paise scores require changing protected walk-forward, backtest, charge or gate authorities.", "A candidate or its private trades/PnL would enter editor versions, analytics, admin, support or cross-owner state."],
  "deployment_impact": {"classification": "read-only architecture and ownership replan", "schema_change": false, "configuration_change": false, "runtime_wiring": false, "locally_testable": false, "locally_runnable_product": false, "release_deployable": false, "production_rehearsed": false, "deployed": false, "implementation_gate": "strategy-os-v0-robustness-parameter-neighborhood-integration", "release_gate": "strategy-os-v0-security-operations-deployability"},
  "review_outcome": {"reviewed_package": {"path": ".agent/runs/strategy-os-v0-robustness-parameter-evaluation-seam-replan/review-package.json", "sha256": "4f4e928f2a965705041644babd0c04777b47d7f1f881abdc83710d72f93bc248", "dirty_tree_fingerprint": "5633e5b89a149e3715de256f9b745ee28e90de69b9bc40b3d70041b271c02c19"}, "verdict": {"path": ".agent/runs/strategy-os-v0-robustness-parameter-evaluation-seam-replan/review/verdict.json", "sha256": "d1cb26a8c9c71279450ab10ce8196e7ce3e3ce3bb57b472c7e2c54e625b7c4e6", "SPEC": "PASS", "QUALITY": "PASS", "final": "PASS"}, "open_findings": [], "nonblocking_evidence_gaps": ["V0-RPESR-EG-001", "V0-RPESR-EG-002"], "successor_may_resume": true},
  "nonclaims": ["No product/test implementation, parameter-neighbourhood availability, provider access, paper/live execution, schema/migration, frontend, deployment, capacity, statistical significance, profitability, future performance or V0 completion."]
}
---

# V0 parameter-evaluation seam replan

The accepted saved-V2 bridge proves one baseline graph can reach durable research and
cost-inclusive backtesting. This replan adds no behavior. It defines the one missing
capability needed to evaluate bounded ephemeral parameter candidates without copying
the V2 authority chain into the generic research orchestrator.
