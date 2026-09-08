---
{
  "id": "strategy-os-v0-robustness-lab",
  "lineage_id": "strategy-os-v0-robustness-terminal-evidence-foundation",
  "programme_stage": "strategy-os-v0-robustness-lab",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_backend_research_evidence_integration",
  "goal": "Bind the accepted stationary trade bootstrap to the existing immutable experiment recipe, locked out-of-sample trade evidence, terminal evidence envelope and owner-scoped read API, and preserve semantic comparison across deterministic reruns by excluding only run-local visualization identity, without creating a second research, money, job or hash authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Explicit bounded bootstrap settings change ExperimentSpec identity; only cost-inclusive locked-OOS trades feed the accepted method; terminal evidence survives restart and is semantically replayed on read; typed unavailable/refusal states, affected tests, isolated ablations, protected hashes and one Critical SPEC PASS / QUALITY PASS exist."},
  "observable_outcome": "A completed saved backtest can carry a requested, reproducible and owner-private Monte Carlo robustness result derived only from its ordered locked-OOS net trade outcomes. A separate frontend slice may enable and render it only after this backend contract is accepted.",
  "risk_tags": ["critical", "research-integrity", "locked-oos", "money", "persistence", "tenant-isolation", "api", "resource-bounds"],
  "required_skills": ["strategyos-repo-orientation", "executing-strategy-os-slices", "research-validity-audit", "anti-lookahead-and-market-truth", "architecture-invariant-audit", "tenant-isolation-audit", "database-migration-safety", "resource-plan-and-cost-audit", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-robustness-method-contracts"],
  "dependency_gate": {"closure": ".agent/runs/strategy-os-v0-robustness-method-contracts/closure-seal.json", "closure_sha256": "8fa88fa0e61860045d4425cf862b2e30f6466a674b9709282715973eb9e4a6ea", "recheck_verdict_sha256": "8d023d580606c206a828774f063de53a55d30cd4ee6ee20f16f7826c74bacecd", "stationary_source_sha256": "8ee73b06a5c3f93af49dac061df29a68e93a5f3cf310650091c5282ad1c5435e", "execution_head": "0051", "research_head": "0011", "policy": "Verify these exact accepted bytes and current heads before work. If another owner changes an allowed or protected path, stop and attribute rather than overwrite."},
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/09-REVISED-V0-V1-V1.5-V2-V3-ROADMAP.md", "sections": ["V0-F — robustness lab"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md", "sections": ["Public V0 — required", "Public V0 — include with limits", "Golden path row 9"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md", "sections": ["Backtest and robustness"]},
    {"path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md", "sections": ["Resource QoS priorities", "Per-deployment resource ceilings"]},
    {"path": "paper-trader/backend/research/evidence.py", "sections": ["MAX_EVIDENCE_BYTES", "encode_terminal_evidence", "decode_terminal_evidence"]},
    {"path": "paper-trader/backend/research/domain/models.py", "sections": ["ExperimentSpec", "ExperimentRun", "OptimizationTrial"]},
    {"path": "paper-trader/backend/research/orchestrator/run.py", "sections": ["run_experiment", "locked OOS branches", "terminal evidence persistence"]},
    {"path": "paper-trader/backend/app/api/ir_experiment_routes.py", "sections": ["GraphExperimentRequest", "post_graph_experiment", "get_graph_experiment"]},
    {"path": "paper-trader/backend/app/api/research_visualization_routes.py", "sections": ["owner-scoped persisted evidence read pattern"]},
    {"path": "paper-trader/backend/app/engine/charges.py", "sections": ["monetary_minor", "ROUNDING_POLICY_V2"]}
  ],
  "contract": {
    "request": {"field": "robustness.stationary_bootstrap", "enabled": "required boolean when object is supplied", "iterations": "integer 100..5000", "restart_probability_ppm": "integer 1..1000000", "default": "not requested; no silent compute"},
    "identity": "The exact robustness request, method schema/version/bounds and seed are part of the immutable ExperimentSpec recipe. Any setting change changes the spec identity. The accepted method result address and complete document are stored inside the existing content-addressed terminal evidence envelope.",
    "input_truth": "For each qualified single-instrument run, use only the ordered pooled OOS BTTrade sequence produced by existing walk-forward validation or nested optimization. Convert each signed net_pnl to integer paise by applying the accepted charges.monetary_minor authority to its absolute rupee magnitude and restoring the sign. Starting capital uses the same authority. IS, qualification and whole-series trade sequences are forbidden inputs.",
    "states": ["NOT_REQUESTED", "AVAILABLE", "UNAVAILABLE"],
    "unavailable": "Fewer than twenty locked-OOS trades, multi-instrument ambiguity, accepted-method typed refusal or terminal evidence size refusal produce a closed reason code and no partial distribution. They do not silently substitute IS/full-run trades and do not erase the underlying backtest result.",
    "read": "An authenticated owner-scoped endpoint reads the stored terminal envelope, refuses corrupt or cross-owner evidence, reconstructs AVAILABLE method bytes/address through reconstruct_stationary_trade_bootstrap, and returns only the closed projection. Legacy runs report NOT_REQUESTED or a stable legacy-unavailable state.",
    "resource": "The accepted 2,000,000 draw-operation ceiling and 2,000,000-byte terminal evidence ceiling remain hard. No background thread, unbounded queue, hidden rerun or partial result is introduced."
  },
  "scope": [
    "Add one integration module that creates, serializes and reconstructs the run-level robustness projection using the accepted method and existing hash/money/evidence authorities.",
    "Thread an optional closed stationary-bootstrap request through the existing graph experiment request and run recipe. Do not change defaults for existing callers.",
    "Persist the result only inside ExperimentRun.checkpoint_json through encode_terminal_evidence. No migration or new table is authorized by this slice.",
    "Add one owner-scoped read route under the already registered research route family. Reconstruct method semantics before returning AVAILABLE evidence.",
    "Correct the existing comparison projection so nested visualization run_id, spec_id and the visualization_address derived from that contextual identity remain contextual rather than semantic, matching the existing top-level run/spec rule. All other visualization, trade, cost, fold and robustness evidence remains exact comparison input.",
    "Keep parameter-neighbourhood product binding, sensitivity/surface UI and the frontend Monte Carlo controls closed for exact successors. Do not imply that the complete Robustness Lab is available yet."
  ],
  "allowed_paths": [
    "paper-trader/backend/research/robustness/integration.py",
    "paper-trader/backend/research/orchestrator/run.py",
    "paper-trader/backend/app/api/ir_experiment_routes.py",
    "paper-trader/backend/app/api/research_visualization_routes.py",
    "paper-trader/backend/research/compare.py",
    "paper-trader/backend/research_tests/test_v0_robustness_terminal_evidence.py",
    "paper-trader/backend/research_tests/test_research_run.py",
    "paper-trader/backend/research_tests/test_graph_experiment.py",
    "paper-trader/backend/research_tests/test_compare.py",
    "paper-trader/backend/tests/test_ir_experiment_routes.py",
    "paper-trader/backend/tests/test_research_visualization_routes.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-terminal-evidence-foundation.md",
    ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation"
  ],
  "new_paths": [
    "paper-trader/backend/research/robustness/integration.py",
    "paper-trader/backend/research_tests/test_v0_robustness_terminal_evidence.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-terminal-evidence-foundation.md",
    ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation"
  ],
  "protected_paths": [
    "paper-trader/backend/research/robustness/monte_carlo.py",
    "paper-trader/backend/research/robustness/neighborhood.py",
    "paper-trader/backend/research/domain",
    "paper-trader/backend/research/evidence.py",
    "paper-trader/backend/research/pipeline",
    "paper-trader/backend/research/stats",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/engine/charges.py",
    "paper-trader/backend/app/backtest",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations",
    "paper-trader/backend/requirements.txt",
    "paper-trader/backend/requirements.lock",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json"
  ],
  "acceptance": [
    "Request validation is closed and bounded; absent settings preserve existing behavior, while any enabled setting changes ExperimentSpec identity and terminal evidence identity.",
    "Direct trace evidence proves the accepted method receives only ordered pooled OOS cost-inclusive net trades and the bound capital/seed/settings. Qualification, IS, full-series or charge-free substitutions turn named tests RED.",
    "AVAILABLE evidence stores exact method bytes/address and reconstructs byte-identically after SQLite close/reopen and a fresh process. PostgreSQL 16 runs when the disposable harness is configured; its absence is an explicit skip, not a portability claim.",
    "Insufficient trades, multi-instrument ambiguity, method refusal, evidence overflow, corrupt/tampered bytes and legacy absence produce stable typed states or 409 integrity refusal without a partial distribution or failed base backtest.",
    "The read route is authenticated and tenant-scoped. Cross-owner run ids are indistinguishable from absence, response middleware remains no-store, and no strategy, trade, credential, provider or PnL evidence enters analytics or operator projections.",
    "Two deterministic executions with semantically identical recipes/results compare equivalent when they differ only in nested visualization run_id, spec_id and the derived visualization_address. Any summary, series, trade, cost, fold, provenance or robustness change remains an exact result difference.",
    "At/below/above request, method-operation and terminal-evidence bounds are exercised. Representative maximum work is measured locally without a production capacity claim.",
    "Ablations that replace OOS with qualification/full-series trades, remove robustness settings from recipe identity, bypass semantic reconstruction, drop owner scoping, or remove run-local comparison normalization each turn a named assertion RED; exact restoration returns focused and affected suites GREEN.",
    "Execution/research heads remain 0051/0011, architecture validation passes, declared protected hashes remain byte-identical, and one independent Critical reviewer returns SPEC PASS / QUALITY PASS.",
    "No parameter-neighbourhood product availability, frontend enablement, provider access, paper/live authority, deployment, statistical-significance, future-performance, profitability or V0-completion claim."
  ],
  "test_plan": [
    "The backend owner creates its durable goal, records dependency/head/new-path/protected hashes, writes RED contract tests, implements only the declared integration and route paths, and records focused/restart/resource/tenant evidence.",
    "Run the exact existing research-run, graph-experiment, experiment-route and visualization-route affected cone plus the accepted Monte Carlo method tests. Run isolated ablations in temporary copies and restore exact source hashes.",
    "Seal one evidence-backed review package and route one Critical reviewer only after integration. The reviewer is read-only except for the declared verdict."
  ],
  "risk_classification": {"tier": "Critical", "reason": "Using in-sample, charge-free, cross-tenant or unreconstructible evidence would present false robustness and can materially mislead a strategy decision."},
  "parallel_budget": 2,
  "assignments": [
    {"id": "v0_robustness_terminal_evidence_backend", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "backend-integration-implementation", "depends_on": [], "write_paths": ["paper-trader/backend/research/robustness/integration.py", "paper-trader/backend/research/orchestrator/run.py", "paper-trader/backend/app/api/ir_experiment_routes.py", "paper-trader/backend/app/api/research_visualization_routes.py", "paper-trader/backend/research_tests/test_v0_robustness_terminal_evidence.py", "paper-trader/backend/research_tests/test_research_run.py", "paper-trader/backend/research_tests/test_graph_experiment.py", "paper-trader/backend/tests/test_ir_experiment_routes.py", "paper-trader/backend/tests/test_research_visualization_routes.py", ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/backend"], "output": ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/backend/report.md"},
    {"id": "v0_research_comparison_run_local_normalization", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "focused-comparison-correction", "depends_on": ["v0_robustness_terminal_evidence_backend"], "write_paths": ["paper-trader/backend/research/compare.py", "paper-trader/backend/research_tests/test_compare.py", ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/comparison-correction"], "output": ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/comparison-correction/report.md"}
  ],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_robustness_terminal_evidence_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "This binds locked-OOS money evidence to persisted user-visible research and an authenticated tenant boundary, including reproducible semantic comparison.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/review-package.json", "review_paths": ["paper-trader/backend/research/robustness/integration.py", "paper-trader/backend/research/orchestrator/run.py", "paper-trader/backend/research/compare.py", "paper-trader/backend/app/api/ir_experiment_routes.py", "paper-trader/backend/app/api/research_visualization_routes.py", "paper-trader/backend/research_tests/test_v0_robustness_terminal_evidence.py", "paper-trader/backend/research_tests/test_research_run.py", "paper-trader/backend/research_tests/test_graph_experiment.py", "paper-trader/backend/research_tests/test_compare.py", "paper-trader/backend/tests/test_ir_experiment_routes.py", "paper-trader/backend/tests/test_research_visualization_routes.py", "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-terminal-evidence-foundation.md", ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation"], "exclude_paths": ["paper-trader/backend/research/robustness/monte_carlo.py", "paper-trader/backend/research/robustness/neighborhood.py", "paper-trader/backend/research/domain", "paper-trader/backend/research/evidence.py", "paper-trader/backend/research/pipeline", "paper-trader/backend/research/stats", "paper-trader/backend/app/engine", "paper-trader/backend/app/backtest", "paper-trader/backend/app/providers", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "implementation": {"status": "ACCEPTED", "backend_report_sha256": "dca90e6dcebd2083495161bc3e952f759b92b65c011ec5a66ae928ff50ec3452", "backend_seal_sha256": "1a44704547ac39dc1e11464ddd90c9e395f5c7e61549b35413efa1298800f4f6", "integration_source_sha256": "c6999a0738ca331d56069c3419a17378721694ed4e4dca919c60593043127857", "orchestrator_source_sha256": "bb6636acfe46ed2699d370b55f2508a8142be65ba17061d8af0cbbb9063c7f7d", "experiment_route_sha256": "0f376489f4aec8daa55b67b377c90a3861b92f284d47a1715948834e20e2ae49", "robustness_route_sha256": "50689d4114cd006bb72e82791c64ac2f604db3b69f06e5474053e7803dead0f3", "comparison_source_sha256": "2dee2b4b1e24cf563763767bc58d3f20a964aecb3aac2a1cf6acbab60db5a442", "comparison_test_sha256": "30107d9939ea46ace83bdeb76e094416f56a1caa1d1c11002e3f108c238d1254", "robustness_route_test_sha256": "0731c84775cf10d5b9dcaca7992f6aa731e43fe1599233f76078c77c4d0ad3f3", "root_focused_passed": 40, "root_affected_passed": 144, "postgresql_optional_skipped": 1, "ablations": "TEN_RED_EXACT_RESTORE_GREEN", "architecture": "PASS_500_0", "protected_preservation": "PASS_384_0_FROM_FRESH_INTEGRATED_BASELINE_WITH_CONTROL_ATTRIBUTION", "execution_head": "0051", "research_head": "0011", "schema_change": false, "frontend": false, "provider_network": false, "execution_authority": false, "review_launched_by_implementation_owners": false, "release_deployable": false, "deployment": false},
  "correction": {"status": "ACCEPTED", "immutable_verdict": ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/review/verdict.json", "immutable_verdict_sha256": "80258da6747dc9baba646c2624230f506cde36dfa1a3bb086a6ec6dcad91bfbc", "closed_findings": ["V0-RTE-CR-001", "V0-RTE-CR-002", "V0-RTE-CR-003"], "closed_evidence_gaps": ["V0-RTE-EG-001", "V0-RTE-EG-002", "V0-RTE-EG-003", "V0-RTE-EG-004"], "recheck_checkpoint_corrections": ["CANONICAL_MAKE_REVIEW_PACKAGE_FINGERPRINT", "DIRECT_409_EXCEPTION_NO_STORE", "CLOSED_UNAVAILABLE_VISUALIZATION_STATE", "NONMAPPING_VISUALIZATION_REFUSAL"], "open_nonblocking_nonclaims": ["V0-RTE-EG-005"], "SPEC": "PASS", "QUALITY": "PASS", "reviewed_package_sha256": "af49430959e0244305fbc2b5e2b4a211c83ccbe8c86bc8d1ab19981e318ffb14", "recheck_verdict_sha256": "762749a71289d5a0d1247d17e100e84b380317c41cae43bf9657ae10d5549b94", "rechecks_used": 1, "rechecks_remaining": 0, "recheck_output": ".agent/runs/strategy-os-v0-robustness-terminal-evidence-foundation/review/recheck-verdict.json"},
  "owner_gates": ["No schema/migration, frontend, parameter-neighbourhood evaluation, provider, monitoring, alert, paper/live execution or deployment change. If the existing terminal envelope cannot safely contain the bounded artifact, or if correct OOS extraction requires changing a protected pipeline/ledger authority, stop and report the exact successor requirement."],
  "stop_conditions": ["Accepted method closure, 0051/0011 heads or an allowed path changes before reservation.", "Any correct implementation requires IS/full-series substitution, a second money/hash/job authority, mutable evidence acceptance, new database storage or an unbounded synchronous workload.", "Tenant-private trade/PnL/strategy evidence would enter analytics, operator or support projections.", "The endpoint cannot semantically reconstruct AVAILABLE evidence or make legacy/corrupt states explicit."],
  "deployment_impact": {"classification": "backend request/orchestration/read-route change using existing persistence", "schema_change": false, "configuration_change": false, "runtime_wiring": true, "locally_testable": true, "locally_runnable_product": false, "release_deployable": false, "production_rehearsed": false, "deployed": false, "future_gate": "strategy-os-v0-robustness-parameter-neighborhood-integration-and-frontend"},
  "nonclaims": ["No parameter-neighbourhood/sensitivity/surface product binding or frontend availability, no provider data, no paper/live execution, no production capacity, deployment, statistical significance, future performance, profitability or V0 completion."]
}
---

# V0 robustness terminal-evidence foundation

This slice makes the accepted stationary trade bootstrap a real saved-backtest
evidence type. It keeps the desktop control disabled until a later slice proves the
frontend contract and keeps parameter-neighbourhood analysis closed until candidate
graph variation can be bound without contaminating locked out-of-sample evidence.
