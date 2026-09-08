---
{
  "id": "strategy-os-v0-robustness-lab",
  "lineage_id": "strategy-os-v0-robustness-method-contracts",
  "programme_stage": "strategy-os-v0-robustness-lab",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_parallel_pure_research_method_foundation",
  "goal": "Implement the two missing bounded, deterministic V0 robustness methods as pure content-addressed research functions: stationary trade-sequence bootstrap and complete local parameter-neighbourhood analysis.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Both pure method contracts and independent tests are integrated, deterministic and bounded; isolated mutations turn named assertions RED and restore GREEN; affected research tests, source/protected hashes and one Critical SPEC PASS / QUALITY PASS exist."},
  "observable_outcome": "The backend can deterministically reconstruct a bounded trade-sequence bootstrap distribution and a complete local parameter-stability decision from explicit immutable inputs. No API, persistence, UI or product claim is enabled by this foundation alone.",
  "risk_tags": ["critical", "research-integrity", "statistics", "determinism", "resource-bounds", "selection-bias"],
  "required_skills": ["executing-strategy-os-slices", "research-validity-audit", "anti-lookahead-and-market-truth", "resource-plan-and-cost-audit", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-chart-annotation-replay"],
  "dependency_gate": {"chart_context_closure": ".agent/runs/strategy-os-v0-research-market-context-annotation-replay-implementation/closure-seal.json", "chart_context_closure_sha256": "cb24756ab6544a016d236c583efc85b0210a30003eca3a528237fc332f63500b", "chart_context_recheck_sha256": "09cef2868bad2b2bd945319e3c3273541a12f5f97e38bbf98c8e3af132ed0b5a", "execution_head": "0051", "research_head": "0011", "policy": "Recheck accepted dependency, heads, exact new paths and protected hashes before work. Any path collision or authority mismatch stops this slice."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-frontend-convergence/implementation-capsules.json", "sections": ["strategy-os-v0-robustness-lab"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/09-REVISED-V0-V1-V1.5-V2-V3-ROADMAP.md", "sections": ["V0-F — robustness lab"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md", "sections": ["Public V0 — required", "Public V0 — include with limits", "Golden path row 9"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/05-ARCHITECTURE-AND-RELEASE-PROFILE.md", "sections": ["Research compatibility"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md", "sections": ["Backtest and robustness"]},
    {"path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md", "sections": ["Resource QoS priorities", "Per-deployment resource ceilings"]},
    {"path": "paper-trader/backend/app/ir/resource_plan.py", "sections": ["ResourcePlan", "resource_calibration", "resource_tier_decision"]},
    {"path": "paper-trader/backend/research/pipeline/optimize.py", "sections": ["OptimizationResult", "complete trial population", "nested walk-forward"]},
    {"path": "paper-trader/backend/research/stats/dsr.py", "sections": ["deflated_sharpe", "expected_max_sharpe"]},
    {"path": "paper-trader/backend/research/stats/pbo.py", "sections": ["pbo", "pbo_gate"]},
    {"path": "paper-trader/backend/research/stats/neff.py", "sections": ["effective_sample_size"]}
  ],
  "source_claims": [
    {"source": "Politis and Romano, The Stationary Bootstrap, JASA 89(428), 1994, DOI 10.1080/01621459.1994.10476870", "url": "https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870", "claim": "A stationary bootstrap forms pseudo-series from randomly sized circular blocks to support inference for weakly dependent stationary observations.", "repository_hypothesis": "A deterministic circular geometric-block bootstrap can preserve some local ordering in an observed trade-PnL sequence, unlike independent reshuffling.", "limit": "Observed strategy trades are not proved stationary; calendar, regime, cross-asset, market-impact and unobserved execution dependencies are lost. Output is a conditional stress distribution, never a future-market or profitability guarantee."},
    {"source": "Bailey and Lopez de Prado, The Deflated Sharpe Ratio, 2014, SSRN 2460551", "url": "https://doi.org/10.2139/ssrn.2460551", "claim": "Selection-aware performance evidence depends on the complete trial population and non-normality, not only the reported winner.", "repository_hypothesis": "Neighbourhood output must bind the complete supplied candidate population and may not replace existing DSR/PBO/N-effective-trial authorities.", "limit": "This slice defines no universal stability, significance, Sharpe or PBO threshold; thresholds remain explicit experiment inputs."}
  ],
  "concurrent_disjoint_attribution": {"capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-auth-password-visibility-preview-correction.md", "status": "accepted_parallel_side_capsule", "closure_seal_sha256": "7885a936e286b659827cfd384ad4a7237cd78c2a5a387f4556fc7edda48a036a", "paths": {"/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx": "1d67d7cf15db802483fea70b05d78d2a43a07405d2f9bb3296000b8966dbe813", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx": "4beefc39717d9e3c376ec7a4f8fc8896b08a24261386c5bdb673c9abfe8af323", "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css": "085c2c885a38148ab990a42db5b3201df0a37d4e1bce50842ad8412e8ab833d5"}, "policy": "These exact user-directed frontend-only bytes are outside both robustness assignments and are excluded from before/after protected equality while remaining hash-attributed in the integrated package. Any other protected drift still refuses."},
  "method_contracts": {
    "stationary_trade_bootstrap": {
      "schema": "strategy-os-stationary-trade-bootstrap/1",
      "input": "Ordered signed integer net-PnL values in paise after the bound charge/slippage model, positive starting capital in paise, uint64 seed, 100..5000 iterations and exact restart_probability_ppm 1..1000000.",
      "bounds": {"minimum_trades": 20, "maximum_trades": 10000, "maximum_draw_operations": 2000000, "maximum_iterations": 5000, "maximum_starting_capital_paise": 9223372036854775807, "minimum_trade_pnl_paise": -9223372036854775808, "maximum_trade_pnl_paise": 9223372036854775807, "maximum_absolute_path_pnl_paise": 9223372036854775807, "maximum_equity_paise": 18446744073709551614},
      "algorithm": "Local SplitMix64/1 draws circular starting indexes and a geometric restart decision before each subsequent trade. Each pseudo-path has exactly the observed trade count. Baseline and every simulated terminal PnL and maximum drawdown remain exact integers; deterministic nearest-rank summaries derive from the retained bounded distributions.",
      "identity": "Input, method/PRNG version, bounds, seed, ordered trade digest, full bounded result and limitations are content addressed through the existing app.ir.hashing authority.",
      "refusals": "For normal generation, booleans-as-integers, floats, nonfinite/negative or over-bound capital, out-of-range trade magnitude, seed/probability/iterations/trade count, operation overflow, worst-case absolute path-PnL overflow, derived equity/drawdown overflow and capital paths below zero refuse through a stable typed boundary before RNG work, result publication or canonical serialization. Reconstruction first decodes and verifies the supplied canonical bytes/address, then applies the same typed numeric validation and full semantic replay; JSON digit-limit, structure, address and replay failures are also typed. Empty/partial result fallback is forbidden."
    },
    "parameter_neighbourhood": {
      "schema": "strategy-os-parameter-neighbourhood/1",
      "input": "One baseline candidate and the complete supplied candidate population, each with a unique content address, identical sorted numeric parameter keys encoded as normalized decimal strings, exact integer OOS score, pass/fail state, declared per-parameter step and inclusive bounds, maximum allowed score drop, and minimum stable-neighbour fraction in ppm.",
      "bounds": {"minimum_parameters": 1, "maximum_parameters": 4, "maximum_candidates": 625, "maximum_expected_local_neighbours": 80},
      "algorithm": "Validate and retain the complete supplied population of up to 625 unique in-bounds candidates. Enumerate the Cartesian {-step,0,+step} neighbourhood inside declared bounds, exclude the baseline, require every expected local point exactly once, and classify only those neighbours against the explicit pass and score-drop rule. Valid distant population members remain in the population digest and result identity but never enter local membership, summaries, sensitivity or the stability decision. Report exact full/local counts, ppm fraction, min/max/median rational and variance numerator/denominator, sensitivity by parameter and stable/not-stable decision.",
      "identity": "Baseline, complete population digest, steps/bounds, user thresholds, exact local membership, summaries, decision and limitations are content addressed through the existing hash authority.",
      "refusals": "Missing expected local neighbours, duplicate parameter points or addresses, extra/missing parameter keys, non-normal decimals including negative zero, booleans/floats, invalid bounds/steps, out-of-bounds candidates, oversized populations and arithmetic overflow refuse. Valid distant in-bounds candidates are retained, not refused. No best-point-only or local-population-only fallback is allowed."
    }
  },
  "allowed_paths": [
    "paper-trader/backend/research/robustness/monte_carlo.py",
    "paper-trader/backend/research/robustness/neighborhood.py",
    "paper-trader/backend/research_tests/test_v0_robustness_monte_carlo.py",
    "paper-trader/backend/research_tests/test_v0_robustness_neighborhood.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-method-contracts.md",
    ".agent/runs/strategy-os-v0-robustness-method-contracts"
  ],
  "new_paths": [
    "paper-trader/backend/research/robustness/monte_carlo.py",
    "paper-trader/backend/research/robustness/neighborhood.py",
    "paper-trader/backend/research_tests/test_v0_robustness_monte_carlo.py",
    "paper-trader/backend/research_tests/test_v0_robustness_neighborhood.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-method-contracts.md",
    ".agent/runs/strategy-os-v0-robustness-method-contracts"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/core",
    "paper-trader/backend/app/db",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/research/domain",
    "paper-trader/backend/research/orchestrator",
    "paper-trader/backend/research/pipeline",
    "paper-trader/backend/research/stats",
    "paper-trader/backend/migrations",
    "paper-trader/backend/requirements.txt",
    "paper-trader/backend/requirements.lock",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json"
  ],
  "scope": [
    "Implement only the two pure method contracts frozen above. Reuse app.ir.hashing; do not create a second hash, trial, data, strategy, result, resource-plan or execution authority.",
    "Keep ordered net-PnL inputs cost-inclusive and integer-exact. The bootstrap resamples observed trade outcomes with circular geometric blocks and states all lost dependencies. It does not synthesize prices, candles, orders, fills or provider data.",
    "Keep neighbourhood thresholds experiment-supplied and require a complete declared local grid. Preserve all supplied candidate identities and refuse missing evidence; never infer robustness from a single optimum.",
    "Enforce structural and combined-operation bounds before loops or allocation. Measure deterministic work at representative boundary workloads and prove above-bound refusal without partial output.",
    "Write no persistence, migration, route, job, UI, monitoring, alert, paper/live execution or deployment integration in this slice. Those remain the immediate successor after method acceptance."
  ],
  "acceptance": [
    "Both modules expose frozen, closed inputs/results and typed stable refusals; contain no unseeded/random-global state, clock, environment, provider, database, network, filesystem, Pandas, NumPy or execution import.",
    "Separate-process runs with the same input produce byte-identical documents and addresses; any seed, trade order/value, baseline, candidate, bound, step, threshold, method or limitation change changes identity.",
    "Bootstrap outputs exact ordered bounded distributions and summaries, preserves block adjacency under controlled vectors, reproduces baseline exactly, and states preserved/lost dependencies without a future-performance claim.",
    "Neighbourhood enumerates the complete in-bounds local Cartesian set, refuses missing/duplicate points, reports exact summaries/sensitivity and applies only the supplied stability rule. No best-only or incomplete-grid result exists.",
    "At, below and above every structural/combined resource bound are tested. Representative maximum-operation and maximum-neighbour workloads remain within declared time/memory evidence without changing semantic bounds.",
    "Mutation/ablation removes the PRNG/block restart, complete-grid guard, threshold comparison and content-address contributor in isolated copies; each turns a named assertion RED and exact source restoration returns focused/affected tests GREEN.",
    "Existing DSR/PBO/N-effective-trial, walk-forward, research-domain, provider, execution, frontend and migration protected hashes remain byte-identical. Architecture validation passes and one independent Critical reviewer returns SPEC PASS and QUALITY PASS.",
    "No API availability, persisted evidence, UI, deployability, production readiness, statistical significance, profitable strategy, future outcome, live/paper authority or V0 completion is claimed."
  ],
  "test_plan": [
    "Each worker creates its durable capsule goal, rechecks dependency/new-path/protected hashes, writes failing contract tests first, implements only its assigned pure module, and records focused/resource/restart evidence.",
    "Root integrates both disjoint modules, checks imports/static boundaries and cross-method identity vocabulary, runs isolated ablations with exact restoration, then runs the affected research stats/pipeline test cone and architecture/protected manifests.",
    "Seal one review package with source claims, assumptions, method vectors, bounds, timings, peak allocations, separate-process byte identities and explicit limitations; route one Critical reviewer only after integration."
  ],
  "risk_classification": {"tier": "Critical", "reason": "Incorrect resampling, incomplete trial populations or unstable identities can present selection noise as evidence and materially mislead strategy decisions."},
  "parallel_budget": 2,
  "assignments": [
    {"id": "v0_robustness_stationary_bootstrap_method", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "pure-method-implementation", "depends_on": [], "write_paths": ["paper-trader/backend/research/robustness/monte_carlo.py", "paper-trader/backend/research_tests/test_v0_robustness_monte_carlo.py", ".agent/runs/strategy-os-v0-robustness-method-contracts/monte-carlo"], "output": ".agent/runs/strategy-os-v0-robustness-method-contracts/monte-carlo/report.md"},
    {"id": "v0_robustness_parameter_neighbourhood_method", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "pure-method-implementation", "depends_on": [], "write_paths": ["paper-trader/backend/research/robustness/neighborhood.py", "paper-trader/backend/research_tests/test_v0_robustness_neighborhood.py", ".agent/runs/strategy-os-v0-robustness-method-contracts/neighborhood"], "output": ".agent/runs/strategy-os-v0-robustness-method-contracts/neighborhood/report.md"}
  ],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_robustness_method_contracts_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "These methods directly shape research-validity evidence, selection-bias interpretation and user risk perception.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-robustness-method-contracts/review-package.json", "review_paths": ["paper-trader/backend/research/robustness/monte_carlo.py", "paper-trader/backend/research/robustness/neighborhood.py", "paper-trader/backend/research_tests/test_v0_robustness_monte_carlo.py", "paper-trader/backend/research_tests/test_v0_robustness_neighborhood.py", "paper-trader/docs/agent/tasks/strategy-os-v0-robustness-method-contracts.md", ".agent/runs/strategy-os-v0-robustness-method-contracts"], "exclude_paths": ["paper-trader/backend/app", "paper-trader/backend/research/domain", "paper-trader/backend/research/orchestrator", "paper-trader/backend/research/pipeline", "paper-trader/backend/research/stats", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-robustness-method-contracts/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "implementation": {"status": "ACCEPTED", "stationary_bootstrap_source_sha256": "8ee73b06a5c3f93af49dac061df29a68e93a5f3cf310650091c5282ad1c5435e", "stationary_bootstrap_test_sha256": "4db7b4a054a5c9b9ed4fc21bc3df7f6a8835bb235f7e7d3b0ff51b0c601c7766", "stationary_bootstrap_seal_sha256": "6b5cccc3452c5c14c4e133f4385492f1875e242676c3bcd72fbcc0ba457d2320", "neighborhood_source_sha256": "348beb23ceef84f1fce67c9eae32fd92a39bc126784f2f39b8db961283ad5bae", "neighborhood_test_sha256": "82fdf01ad1c865ddc66805e04cb3aac4dfd3d10d2a94e1716a4325d024e957f1", "neighborhood_seal_sha256": "95fbd79d6ed49ad9be179128e9f1263fa176f5f7252d64ded6ecb3db651b9eb4", "focused_tests": 135, "affected_research_tests": 230, "semantic_reconstruction": "PASS", "method_ablations": "RED_RESTORED_GREEN", "resource_bounds": "PASS_EXACT_MONETARY_AND_DERIVED_PREFLIGHT", "complete_population_binding": "PASS_625_RETAINED_80_LOCAL", "separate_process_determinism": "PASS", "architecture": "PASS_499_0", "protected_preservation": "PASS_WITH_EXACT_AUTH_SIDE_CAPSULE_ATTRIBUTION", "persistence": false, "api": false, "frontend": false, "provider_network": false, "execution_authority": false, "review_launched_by_implementation_owners": false, "release_deployable": false, "deployment": false},
  "correction": {"status": "ACCEPTED", "immutable_verdict": ".agent/runs/strategy-os-v0-robustness-method-contracts/review/verdict.json", "immutable_verdict_sha256": "75d8b15172f004ba5b23f47d0238b04214d4bfc74f9b1790785c3621a79978b7", "closed_findings": ["V0-RMC-CR-001", "V0-RMC-CR-002"], "closed_evidence_gaps": ["V0-RMC-EG-001", "V0-RMC-EG-002"], "open_nonblocking_nonclaims": ["V0-RMC-EG-003"], "rechecks_used": 1, "rechecks_remaining": 0, "recheck_output": ".agent/runs/strategy-os-v0-robustness-method-contracts/review/recheck-verdict.json", "recheck_verdict_sha256": "8d023d580606c206a828774f063de53a55d30cd4ee6ee20f16f7826c74bacecd", "SPEC": "PASS", "QUALITY": "PASS", "scope": "Focused same-lineage closure of complete wider candidate-population binding and bounded monetary integer/derived arithmetic typed refusal only."},
  "owner_gates": ["No persistence/schema/API/job/UI/provider/monitoring/alert/paper/live/execution/deployment change; no paid data or external service; no product availability or performance/profitability claim. Any need to alter an existing pipeline/stat/hash/resource authority stops for successor integration design."],
  "stop_conditions": ["Chart dependency or 0051/0011 head changes before reservation.", "Any declared new path exists with non-identical concurrent work.", "The pure methods require a second hash/trial/data/resource authority or an existing protected-source change.", "The method cannot state exact preserved/lost dependencies or complete population semantics.", "Representative bounded work exceeds the declared local resource budget without a semantics-preserving smaller bound.", "A universal statistical/stability threshold, vendor data, production trace or investment claim would be required."],
  "deployment_impact": {"classification": "code-only dormant research method foundation", "schema_change": false, "runtime_wiring": false, "locally_testable": true, "locally_runnable_product": false, "release_deployable": false, "production_rehearsed": false, "deployed": false, "future_gate": "strategy-os-v0-robustness-lab-integration"},
  "nonclaims": ["No locked-OOS/persistence/job/API/frontend integration, no synthetic-market simulator, no provider data, no order/fill model, no execution stress beyond already net-cost trade inputs, no statistical significance or future-market guarantee, no paper/live authority, no deployability or V0 completion."]
}
---

# V0 robustness pure method contracts

This foundation closes only the missing deterministic method definitions. Product
availability remains false until the successor binds immutable ExperimentSpec,
complete trials/folds/baseline, persistence, jobs, APIs and the desktop evidence UI.
