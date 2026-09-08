---
{
  "id": "strategy-os-v0-robustness-lab",
  "lineage_id": "strategy-os-v0-v2-phase4-dynamic-binding-admission-correction",
  "programme_stage": "strategy-os-v0-robustness-lab",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_phase4_dynamic_contract_binding_admission_correction",
  "goal": "Make the existing Phase 4 V2 admission constructor, restart reconstructor and mirrored execution/research persistence canonicalizers accept and reverify the exact typed ContractInputBindings and current contract-bound registry snapshot required by analytical /2 data-plan compilation, without changing receipt/schema identity or weakening legacy/static admission behavior.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "A real current analytical /2 V2 graph plus the frozen persisted-dataset projection's ContractInputBindings mints and reconstructs one exact Phase 4 RESEARCH receipt; absent, foreign, stale, wrong-context, source-substituted, unused and missing bindings refuse; existing non-dynamic callers and receipt identities remain compatible; isolated ablations, affected tests, protected hashes and one Critical SPEC PASS / QUALITY PASS are sealed."},
  "observable_outcome": "The blocked saved-V2 research operation can receive a genuine current Phase 4 admission whose plan address binds the exact graph input sources, and restart must reproduce those bytes rather than guess or forge data context.",
  "risk_tags": ["critical", "phase4-admission", "v2-ir", "contract-input-bindings", "dataset-authority", "restart", "tenant-isolation", "research-integrity"],
  "required_skills": ["strategyos-repo-orientation", "executing-strategy-os-slices", "architecture-invariant-audit", "anti-lookahead-and-market-truth", "tenant-isolation-audit", "risk-weighted-verification", "auditing-strategy-os-deployability"],
  "depends_on": ["strategy-os-v0-v2-research-backtest-bridge-replan", "v2_canonical_runtime_authority"],
  "dependency_gate": {"replan_recheck_sha256": "8dd299be588680d8effec6f05f0b23ef36cc6db371efc5b077b9915a115fe341", "runtime_foundation_report_sha256": "8f3baf6f49ac3c8b2102e87d6bf38bca61e00b44408e594264d7a4943ed92763", "blocked_parent": "strategy-os-v0-v2-research-backtest-bridge-correction", "blocker_evidence_sha256": "c4bf36cf1bb4c1e34bdc4019ad77d126b9cd07b9ab60acf509f9c217ec3db88c", "execution_head": "0051", "research_head": "0011"},
  "supported_contract": {
    "mint": "admit_phase4_v2_strategy gains one keyword-only input_bindings parameter. One private admission helper canonicalizes and calls resolve_v2 exactly once, then reuses that exact ResolvedGraph for receipt topology, Phase 4 declaration detection and compile_data_requirement_plan(resolved, registry=registry, input_bindings=input_bindings). The separately supplied plan must equal that exact result. Current dynamic analytical /2 requires a typed ContractInputBindings; absent or wrong bindings fail closed. Non-dynamic graphs retain input_bindings=None and reject an unused supplied context through the existing compiler.",
    "restart": "reconstruct_phase4_artifact gains the same keyword-only input_bindings parameter. Its base-reconciliation helper returns both the exact base artifact and the same single ResolvedGraph used to reconstruct it; the Phase 4 plan compiler consumes that object without another resolve. The receipt's existing phase4_data_binding.plan_address and capability assessment must equal the reconstructed bound plan. A changed binding document/context therefore changes the plan and refuses the old immutable receipt.",
    "identity": "No Phase4V2AdmittedStrategyArtifact, phase4_data_binding, receipt scheme, JSON field, database column, migration or address algorithm changes. The existing plan_address already commits to parameter_binding_provenance, including each node_contract_binding and its exact input context/source addresses. Reconstruction requires caller-supplied typed bindings and proves the same plan address; it cannot recover authority from a hash alone.",
    "source": "Only the server-owned persisted dataset projection may supply production ContractInputBindings. This correction does not derive bindings from request fields, query providers, load credentials or select among plural sources.",
    "compatibility": "All current non-dynamic Phase 4 callers with no bindings remain behaviorally and identity compatible. Every direct dynamic caller must pass the exact typed bindings explicitly; no default registry or ambient/global binding lookup exists.",
    "persistence_snapshot": "One pure closed helper in app.strategy.admission recognizes exactly the legacy seven-key Phase 4 registry snapshot or the contract-bound nine-key form that adds node_contracts and contract_bindings as an atomic pair of arrays. Unknown keys, half-pairs and wrong shapes refuse. Both existing execution- and research-plane canonicalizers call that same helper, retain their independent row/persistence authorities, and still rehash the full embedded snapshot against phase4_data_binding.registry_snapshot_address. No receipt field, scheme, address or database shape changes."
  },
  "required_docs": [
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-v2-research-backtest-bridge-correction.md", "sections": ["active_blocker", "supported_contract", "owner_gates"]},
    {"path": ".agent/runs/strategy-os-v0-v2-research-backtest-bridge-correction/route-bridge/report.md", "sections": ["Confirmed blocker", "Evidence reached before the stop"]},
    {"path": "paper-trader/backend/app/strategy/admission.py", "sections": ["Phase4V2AdmittedStrategyArtifact", "admit_phase4_v2_strategy", "reconstruct_phase4_artifact"]},
    {"path": "paper-trader/backend/app/market_data/requirements.py", "sections": ["compile_data_requirement_plan", "verify_data_requirement_plan"]},
    {"path": "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py", "sections": ["ContractInputBindings", "canonical_input_bindings", "input_binding_for_node"]},
    {"path": "paper-trader/backend/research/data/canonical_dataset.py", "sections": ["project_verified_research_inputs"]}
    ,{"path": "paper-trader/backend/app/core/strategy_admissions.py", "sections": ["_canonicalize Phase 4 registry snapshot"]}
    ,{"path": "paper-trader/backend/research/domain/admissions.py", "sections": ["_canonicalize Phase 4 registry snapshot"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/tests/test_phase4_dynamic_contract_binding_admission.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction.md",
    ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_phase4_dynamic_contract_binding_admission.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction.md",
    ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/research/data/canonical_dataset.py",
    "paper-trader/backend/research/evaluation",
    "paper-trader/backend/research/orchestrator",
    "paper-trader/backend/app/backtest",
    "paper-trader/backend/app/api",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/migrations",
    "paper-trader/backend/research/domain/operations.py",
    "paper-trader/backend/migrations",
    "paper-trader/backend/requirements.txt",
    "paper-trader/backend/requirements.lock",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json"
  ],
  "acceptance": [
    "Independent RED reproduces the exact real current analytical /2 failure from both admission and reconstruction while non-dynamic controls remain green.",
    "Mint and reconstruct resolve the document once and call the sole data-plan compiler with the exact supplied PlatformRegistry and typed ContractInputBindings. No ambient, request-derived, default or hash-only binding authority is introduced.",
    "The persisted-dataset projection's bindings admit a real analytical /2 graph. The resulting plan parameter_binding_provenance retains node_contract_binding context/source facts, and the existing phase4_data_binding.plan_address plus capability assessment bind that exact plan without any receipt/schema/migration change.",
    "Absent bindings; forged ContractInputBindings wrappers; wrong owner, dataset context, evaluation context, input name, role, instrument, field, timeframe, session, alignment, provider product/contract/source address; unused and missing inputs all refuse before receipt persistence.",
    "Reconstruction with identical bindings yields exact artifact/receipt/plan identities. Every one-field binding substitution refuses the old receipt; fresh interpreter/process restart repeats the same result.",
    "The shared snapshot-shape helper accepts exactly the existing seven-key registry snapshot or the nine-key contract-bound snapshot with node_contracts and contract_bindings present together as arrays. Both execution and research writers persist/reuse the exact analytical receipt; unknown extra keys, either missing half of the pair, non-array additions, stale snapshot address and cross-plane byte drift refuse before a row is written.",
    "Existing non-dynamic Phase 4 constructor/reconstruction callers, V2 receipt persistence, lifecycle loader and Phase 4 authority tests remain green with identical receipt identities. Passing bindings to a graph that does not consume them refuses as unused.",
    "Direct instrumentation proves exactly one resolve_v2 call for public admit_v2_strategy, Phase 4 mint and Phase 4 reconstruction. The one returned ResolvedGraph supplies topology, declaration selection and bound plan; a second-call mutation makes the named call-count assertion RED while receipt bytes remain compatible after restoration.",
    "Critical isolated ablations omit input_bindings at mint/restart, substitute a binding after receipt, bypass plan-address comparison, drop registry forwarding and reintroduce a second resolve; each turns a named assertion RED and exact restoration returns the full cone GREEN.",
    "Architecture/package fingerprint pass, protected/frozen parent hashes remain byte-identical, no schema/migration/provider/frontend/paper/live/execution/deploy path changes, and one independent Critical reviewer returns SPEC PASS / QUALITY PASS.",
    "No parent bridge completion, V2 research availability, parameter-neighbourhood availability, production capacity, deployment, profitability or V0 completion claim."
  ],
  "test_plan": [
    "Owner captures exact inherited admission.py, both mirrored persistence canonicalizers and affected-caller hashes; writes real analytical RED tests first; then implements only the two keyword-bound compiler calls, one shared closed snapshot-shape helper, two persistence helper calls and necessary type/refusal handling.",
    "Run focused dynamic mint/reconstruct/persistence/restart/tamper tests, then the complete existing Phase 4 admission/authority/receipt/graph persistence and Phase 5 lifecycle consumer cone. Record optional PostgreSQL skips exactly.",
    "Run isolated mutations in disposable copies, including a second resolve call-count mutation; restore exact bytes, compile, validate architecture/protected hashes, seal one review package and route the one allowed focused Critical recheck."
  ],
  "risk_classification": {"tier": "Critical", "reason": "A wrong or ambient data binding can authorize a strategy against another owner, instrument, field or evaluation context and make research evidence unreconstructible."},
  "parallel_budget": 1,
  "assignments": [
    {"id": "v2_phase4_dynamic_binding_admission", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "phase4-admission-correction", "depends_on": [], "write_paths": ["paper-trader/backend/app/strategy/admission.py", "paper-trader/backend/app/core/strategy_admissions.py", "paper-trader/backend/research/domain/admissions.py", "paper-trader/backend/tests/test_phase4_dynamic_contract_binding_admission.py", ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/implementation"], "output": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/implementation/report.md"}
  ],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v2_phase4_dynamic_binding_admission_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "This changes the Phase 4 admission/restart and mirrored persistence authority for current analytical data bindings.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/review-package.json", "review_paths": ["paper-trader/backend/app/strategy/admission.py", "paper-trader/backend/app/core/strategy_admissions.py", "paper-trader/backend/research/domain/admissions.py", "paper-trader/backend/tests/test_phase4_dynamic_contract_binding_admission.py", "paper-trader/docs/agent/tasks/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction.md", ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction"], "exclude_paths": ["paper-trader/backend/app/market_data/requirements.py", "paper-trader/backend/app/ir", "paper-trader/backend/research/data", "paper-trader/backend/research/evaluation", "paper-trader/backend/research/orchestrator", "paper-trader/backend/research/domain/models.py", "paper-trader/backend/research/domain/migrations", "paper-trader/backend/research/domain/operations.py", "paper-trader/backend/app/core/deployments.py", "paper-trader/backend/app/core/execution_binding.py", "paper-trader/backend/app/backtest", "paper-trader/backend/app/api", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["Modify only app/strategy/admission.py, the two mirrored Phase 4 persistence canonicalizers and the one new test. In app/core/strategy_admissions.py preserve every frozen parent-route addition and change only the shared snapshot-shape validation call. Preserve all other inherited bytes. No new receipt field/scheme/address, schema/migration, persisted binding row, default/global lookup, provider call, frontend, paper/live execution or deployment. Parent route-bridge paths remain frozen. Any need to change DataRequirementPlan identity, weaken typed validation or edit another product path stops for root replan."],
  "stop_conditions": ["Exact typed bindings cannot be passed through both constructor and reconstruction without changing the immutable receipt contract or another protected authority.", "Existing non-dynamic receipts change identity/behavior or a caller cannot remain compatible with input_bindings=None.", "A safe solution requires deriving bindings from client input, an ambient registry/context, provider I/O, schema/migration or parent route edits."],
  "deployment_impact": {"classification": "compatible internal Phase 4 constructor/reconstructor signature hardening", "schema_change": false, "configuration_change": false, "runtime_wiring": false, "locally_testable": true, "locally_runnable_product": false, "release_deployable": false, "production_rehearsed": false, "deployed": false, "resume_gate": "strategy-os-v0-v2-research-backtest-bridge-correction", "release_gate": "strategy-os-v0-security-operations-deployability"},
  "discovered_persistence_gap": {"status": "AUTHORIZED_WITHIN_THIS_UNREVIEWED_CORRECTION_BEFORE_SEAL", "evidence": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/implementation/focused-mint-green.log", "cause": "Both persistence canonicalizers hard-code the seven-key registry snapshot and reject the valid current nine-key contract-bound snapshot containing node_contracts plus contract_bindings.", "collision": "app/core/strategy_admissions.py contains frozen parent route-bridge work; preserve its exact current bytes and change only snapshot-shape validation before returning the accepted hash to the parent."},
  "implementation": {"status": "correction_complete_pending_focused_recheck", "report": {"path": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/implementation/report.md", "sha256": "7fae983f19ac364fa022ab8504d01e2c3c56674bbef7e460486f0ad1eaaa7893"}, "review_inputs": {"path": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/implementation/review-inputs.json", "sha256": "4d3acfdf4c0ecaf12320f43c30e5bfeb4b4d517472e11ea0c8597c749549184f"}, "owned_hashes": {"paper-trader/backend/app/strategy/admission.py": "c95ed39046770828d0a566b99d5956b85520852f4b6ec47bb421caf5d8622dd4", "paper-trader/backend/app/core/strategy_admissions.py": "35b0d08cd5a4984f3d57633337df171ea8f9db54afa2fca45e9da67856580fda", "paper-trader/backend/research/domain/admissions.py": "2e8c7d2471d8a10a5294beb85074c81e0ad939ebb6c715923274b5fd6e2269bd", "paper-trader/backend/tests/test_phase4_dynamic_contract_binding_admission.py": "46f2d502c8ff6369b391a3f77f21260ac5d003ef29c270babc70af3a2299424c"}, "initial_red_failures": 18, "resolve_once_red_counts": {"public_admit": 2, "phase4_mint": 3, "phase4_reconstruct": 3}, "resolve_once_green_counts": {"public_admit": 1, "phase4_mint": 1, "phase4_reconstruct": 1}, "focused_passed": 22, "affected_passed": 187, "affected_skipped_optional_postgresql": 8, "ablations_killed": 6, "architecture_checked_files": 504, "architecture_failures": 0, "protected_sources_identical": true, "schema_or_migration_change": false, "review_launched": true},
  "first_review": {"path": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/review/verdict.json", "sha256": "90f56ff141f60cf1d2cab914fcec6cdf44f47a8dec900d2774a1e0a34af531a4", "verdict": "SPEC FAIL / QUALITY FAIL", "closed_findings": ["V2-P4-DBA-CR-001", "V2-P4-DBA-CR-002"]},
  "corrected_review_package": {"path": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/review-package.json", "sha256": "3c6c759ed3c5918425f3fae60d8bf1ccf07048f486befd3d3546c118bf20234f"},
  "focused_recheck": {"path": ".agent/runs/strategy-os-v0-v2-phase4-dynamic-binding-admission-correction/review/recheck-verdict.json", "sha256": "01bea918d388549758ed25fffee9c2b43a1c7a9afe99524410f36accdcb550bd", "verdict": "SPEC PASS / QUALITY PASS", "open_findings": [], "rechecks_used": 1, "rechecks_remaining": 0, "parent_bridge_may_resume_after_hash_recheck": true},
  "nonclaims": ["No parent bridge completion, V2 research/backtest availability, provider access, frontend, parameter optimization, paper/live execution, schema/migration, production capacity, deployment, profitability, statistical significance or V0 completion."]
}
---

# V0 Phase 4 dynamic input-binding admission correction

The saved-V2 research bridge exposed an earlier Phase 4 omission: current
analytical `/2` plans already require exact typed input bindings, but the mint and
restart constructors do not forward them. This correction changes only that
internal function contract. The immutable receipt schema and every downstream
authority remain unchanged.
