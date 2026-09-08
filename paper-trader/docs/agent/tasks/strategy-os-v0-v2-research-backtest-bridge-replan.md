---
{
  "id": "strategy-os-v0-robustness-lab",
  "lineage_id": "strategy-os-v0-v2-research-backtest-bridge-replan",
  "programme_stage": "strategy-os-v0-robustness-lab",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_v2_research_bridge_replan",
  "goal": "Resolve the V2 editor-to-research gap by selecting the smallest existing-authority bridge from an owner-scoped saved V2 version through the accepted V2 resolver/runtime into the established locked-OOS backtest trade contract, without granting live execution or inventing a second evaluator.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Two independent source audits prove the exact loader, dataset, evaluator, signal-output, fold, money and resource seams; root records KEEP/KEEP+HARDEN/REFACTOR/REPLACE/DEFER, rejects unsafe alternatives, seals exact correction paths/tests/nonclaims and one independent Critical reviewer returns SPEC PASS / QUALITY PASS on the replan."},
  "observable_outcome": "The repository has one reviewed implementation capsule capable of making saved V2 strategies research-runnable and later parameter-neighbourhood-runnable, with an exact supported output subset and no live authority.",
  "risk_tags": ["critical", "architecture", "v2-ir", "research-integrity", "locked-oos", "money", "authority-separation", "resource-bounds"],
  "required_skills": ["strategyos-repo-orientation", "architecting-strategy-os-phases", "architecture-invariant-audit", "anti-lookahead-and-market-truth", "research-validity-audit", "resource-plan-and-cost-audit", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-robustness-terminal-evidence-foundation", "strategy-os-v0-robustness-parameter-neighborhood-integration"],
  "dependency_gate": {"terminal_closure_sha256": "4716d13640b868e8f1eda8e51f427e9e4eaaf4671366306725747cb8a51b0835", "blocked_parameter_report": ".agent/runs/strategy-os-v0-robustness-parameter-neighborhood-integration/backend/report.md", "blocked_parameter_report_sha256": "dffd6c349712ad9ce0505cfe4d71f8589e54c4351da28a66a9f4a9545f5c3336", "blocked_probe": ".agent/runs/strategy-os-v0-robustness-parameter-neighborhood-integration/backend/red-v2-bridge-direct.log", "execution_head": "0051", "research_head": "0011", "policy": "Recheck exact evidence and source hashes. This replan is read-only over product code and must not infer implementation authority from an existing test-only evaluator."},
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/09-REVISED-V0-V1-V1.5-V2-V3-ROADMAP.md", "sections": ["V0-F — robustness lab"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/05-ARCHITECTURE-AND-RELEASE-PROFILE.md", "sections": ["Research compatibility"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md", "sections": ["Backtest and robustness"]},
    {"path": "paper-trader/backend/research/orchestrator/graph_experiment.py", "sections": ["build_graph_provenance", "run_published_graph_experiment"]},
    {"path": "paper-trader/backend/research/evaluation/phase5_runtime.py", "sections": ["verify_research_dataset", "research_evaluation_policy", "execute_research", "authority and parity checks"]},
    {"path": "paper-trader/backend/app/ir/runtime.py", "sections": ["evaluate_v2"]},
    {"path": "paper-trader/backend/app/ir/v2_graph_versions.py", "sections": ["V2 evidence-only boundary", "facts_from_row"]},
    {"path": "paper-trader/backend/app/editor/v2_editor_store.py", "sections": ["read_version", "published V2 facts"]},
    {"path": "paper-trader/backend/app/editor/graph_artifacts.py", "sections": ["load_owned_version_for_experiment", "legacy publish boundary"]},
    {"path": "paper-trader/backend/research/data/canonical_dataset.py", "sections": ["DatasetManifest/2 adapter", "CanonicalDataset", "canonical provenance"]},
    {"path": "paper-trader/backend/research/evaluation/walkforward.py", "sections": ["walk_forward"]},
    {"path": "paper-trader/backend/app/backtest/engine.py", "sections": ["run_trades"]},
    {"path": "paper-trader/backend/app/strategy/ir_adapter.py", "sections": ["IRGraphStrategy", "column_mapping"]}
  ],
  "questions": [
    "Can the existing Phase 5 execute_research path consume the current owner-scoped DatasetManifest/2-backed canonical research selection without a second dataset conversion or lost availability/market-truth facts?",
    "What exact ResourcePlan, policy and input-binding facts must the product route construct before V2 evaluation, and which existing authority constructs them?",
    "Can a small research Strategy adapter call the accepted resolve_v2/evaluate_v2 or execute_research path and map only explicitly named graph outputs into the existing backtest columns without duplicating evaluation semantics?",
    "Which V2 output semantic roles and types are sufficient for LONG/SHORT/EXIT/HOLD research, and must ambiguous graphs refuse instead of guessing?",
    "How can the experiment route load an immutable owner-scoped V2 version and admission/capability evidence without conflating legacy GraphVersion or granting execution authority?",
    "Which exact tests prove batch/incremental parity, prefix causality, identical walk-forward folds, cost-inclusive trades, restart identity, owner isolation and no live/paper/provider authority?"
  ],
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-replan.md",
    "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-correction.md",
    ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-replan.md",
    "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-correction.md",
    ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan"
  ],
  "protected_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts",
    "paper-trader/backend/migrations",
    "paper-trader/backend/research/domain"
  ],
  "acceptance": [
    "Each audit cites exact current source/test paths and rejects any unsupported inference. Their scopes are disjoint and their product hashes remain byte-identical.",
    "The decision reuses one accepted V2 resolver/evaluator/runtime and one existing backtest/charge/fold authority. A second IR, resolver, evaluator, hash, dataset, trial, money, signal or execution authority is rejected.",
    "The supported V2 research subset has closed graph-input/output roles, numeric validity and mode eligibility. Ambiguous/unmappable/execution-only/monitoring-only outputs refuse; no positional or display-name guess exists.",
    "The data bridge preserves owner, instrument, event/availability/knowledge time, truth snapshots, adjustment/session/resampling/missing/alignment policies and exact DatasetManifest/2 identity before evaluation.",
    "The successor owns exact loader, bridge/adapter, resource-plan/policy, route and test paths. It states whether any accepted protected source must change and why that is hardening rather than a parallel authority.",
    "The successor test plan covers real V2 saved-version loading, batch/incremental parity, prefix causality, identical OOS folds, cost-inclusive trade arithmetic, restart/tamper/tenant/resource behavior and isolated ablations.",
    "Architecture validation passes; no product code/test, migration, provider, frontend, paper/live execution or deployment byte changes in this replan; one independent Critical reviewer returns SPEC PASS / QUALITY PASS.",
    "No implementation, V2 research availability, parameter-neighbourhood availability, live/paper authority, deployment or V0 completion claim."
  ],
  "test_plan": [
    "Run both read-only audits in parallel from exact source and tests; each writes one report with observed facts, rejected hypotheses, required proof and candidate path ownership.",
    "Root integrates one architecture decision, collision map and exact successor capsule, hashes all artifacts, validates architecture and routes one read-only Critical review.",
    "No product tests are modified or implementation commands run during this replan; safe read-only source imports/tests may be cited but not counted as successor acceptance evidence."
  ],
  "risk_classification": {"tier": "Critical", "reason": "This bridge determines whether user-authored V2 semantics can enter research trades without future leakage, evaluator drift or accidental execution authority."},
  "parallel_budget": 2,
  "assignments": [
    {"id": "v2_research_runtime_dataset_bridge_audit", "agent": "explorer", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-source-audit", "depends_on": [], "write_paths": [".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/runtime-dataset-audit"], "output": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/runtime-dataset-audit/report.md"},
    {"id": "v2_saved_version_output_backtest_bridge_audit", "agent": "explorer", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-source-audit", "depends_on": [], "write_paths": [".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/version-output-audit"], "output": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/version-output-audit/report.md"}
  ],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_v2_research_backtest_bridge_replan_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "The decision opens a previously closed V2 research runtime seam near money and execution boundaries.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-replan.md", "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-correction.md", ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts"], "output": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["This replan may authorize only an exact later correction capsule. It cannot change product code/tests, migrate schema, instantiate live/paper execution, contact providers, import credentials, deploy or claim V2 research availability. Any need for a new evaluator rather than an adapter over accepted V2 runtime stops for owner review."],
  "stop_conditions": ["The two audits disagree on the authoritative dataset/evaluator path and root cannot resolve it from source/tests.", "The supported research output vocabulary would require guessing from display names/positions or treating execution/monitoring intent as backtest signal authority.", "A safe bridge requires changing V2 semantic identity, accepted money/fold semantics, shared schema or live execution authority rather than adapting existing research interfaces.", "Licence-sensitive new dependency or external service is required."],
  "deployment_impact": {"classification": "read-only architecture replan", "schema_change": false, "runtime_wiring": false, "locally_testable": false, "locally_runnable_product": false, "release_deployable": false, "production_rehearsed": false, "deployed": false, "future_gate": "strategy-os-v0-v2-research-backtest-bridge-correction"},
  "decision": "KEEP + HARDEN",
  "delivery_status": "accepted",
  "implementation": {
    "product_or_test_writes": 0,
    "source_hashes_rechecked": 42,
    "source_hash_mismatches": 0,
    "architecture_checked_files": 503,
    "architecture_failures": 0,
    "runtime_dataset_audit": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/runtime-dataset-audit/report.md", "sha256": "305d6b8e16c10840c5f25055b32b15ff961873e0ce517263301dd3f6835937f4", "verdict": "KEEP + HARDEN"},
    "saved_version_output_audit": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/version-output-audit/report.md", "sha256": "a6296baa710addd96118006d76802b736c9546083abf96bfebf6ecaf81ce896d", "verdict": "KEEP + HARDEN"},
    "decision": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/decision.json", "sha256": "1a1d21783e568f83d5f06e2e53ef47609df81252f59b2386e8be9bd3fba76357"},
    "report": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/report.md", "sha256": "d230449916c1f49e98627acc762457bbb2b3f3cfce17d9364d33c6f1d472f709"},
    "successor_capsule": {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-correction.md", "sha256": "7e6c880d1cd65c0c74e156c27d6d7ec06167ea801596672c7007ea02564caae6", "status": "blocked_pending_replan_recheck"},
    "first_review": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/review/verdict.json", "sha256": "a753dc71b2ee10014be719edd824459c899489f4128d12ca9137f103a53afd36", "verdict": "SPEC FAIL / QUALITY FAIL", "closed_findings": ["V0-V2-RBBR-CR-001", "V0-V2-RBBR-CR-002", "V0-V2-RBBR-CR-003", "V0-V2-RBBR-CR-004", "V0-V2-RBBR-CR-005", "V0-V2-RBBR-EG-001", "V0-V2-RBBR-EG-002"]},
    "corrected_review_package": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/review-package.json", "sha256": "680622bcdb07f41ce71308dcbe08cd69bed3b43e8ab4fb7ffb2c95291b13936b"},
    "focused_recheck": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/review/recheck-verdict.json", "sha256": "8dd299be588680d8effec6f05f0b23ef36cc6db371efc5b077b9915a115fe341", "verdict": "SPEC PASS / QUALITY PASS", "open_findings": []},
    "activated_successor_capsule": {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-correction.md", "sha256": "25a97b670eb3f407ea09b32edbca35e4c0e0c608725e26df2bb1b24d9809ad2c", "status": "active"},
    "integration_source_manifest": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/root/integration-source-hashes.sha256", "sha256": "701e7613163cfd2c1acf777550bb37450728a259358cb1d6487286c73a552399", "entries": 42},
    "integration_source_check": {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-replan/root/integration-source-hash-recheck-corrected.log", "sha256": "27e0753dc1d6981dd47cb43cda173f5b40a528b044cb99575495ec3926fcf07d", "status": "PASS_WITHOUT_MALFORMED_OR_SKIPPED_LINES"},
    "rechecks_used": 1,
    "rechecks_remaining": 0
  },
  "nonclaims": ["No product/test implementation, V2 backtest availability, parameter-neighbourhood availability, provider access, paper/live execution, deployment, statistical significance, profitability or V0 completion."]
}
---

# V0 V2 research/backtest bridge replan

This replan exists because the visible V2 editor currently cannot enter the legacy
backtest bridge. It must reuse the accepted V2 research runtime or stop; it may not
solve the gap with another evaluator hidden inside robustness code.

## Accepted replan receipt

The immutable first Critical verdict failed on durability, resource enforcement,
warmup ambiguity, V1 compatibility and deployment ownership. The corrected
same-lineage package received SPEC PASS / QUALITY PASS at recheck SHA-256
`8dd299be588680d8effec6f05f0b23ef36cc6db371efc5b077b9915a115fe341`.
All five findings and both evidence gaps are closed, the two policy documents
recompute to their declared addresses, and the clean 42-file source receipt passes.
The exact successor is active; no successor implementation, V2 availability,
provider, paper/live authority, deployment or V0-complete claim follows.
