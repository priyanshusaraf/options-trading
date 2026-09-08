---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-monitoring-evaluation-transition-foundation",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_pure_monitoring_evaluation_transition_foundation",
  "goal": "Use the one canonical v2 evaluator to compile closed monitoring target/protection outputs into the accepted next-state, MonitoringSignalEvent and SignalAlert-or-NoAlert facts without provider, persistence, worker, API, execution or money authority.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Representative BUY, SELL, EXIT, HOLD, protection-update, ambiguity, causal-prefix, tenant/assignment and no-authority cases pass; the exact pure compiler is resource bounded, protected paths remain unchanged and one independent Critical SPEC/QUALITY review passes."
  },
  "risk_tags": ["critical", "monitoring-truth", "canonical-evaluator", "sl-tp-geometry", "causality", "tenant-isolation", "no-money-authority"],
  "depends_on": [
    "strategy-os-v0-signal-alert-attention-correction",
    "strategy-os-v0-monitoring-check-expression-semantics-correction",
    "strategy-os-v0-verified-language-catalogue",
    "strategy-os-v0-runtime-trigger-cache-detached-issued-snapshot-correction"
  ],
  "dependency_gate": {
    "signal_alert_verdict_sha256": "25e3e331cffbf731380190a141c456406e80a4ad77f54c24b12b022845e4f4dc",
    "monitoring_persistence_successor_verdict_sha256": "95a4f27ebb10961eefa36156fc92f398078abf0de3fe55da5f039b74c259b208",
    "verified_language_catalogue_verdict_sha256": "76ac68d907fc69866e94d9ab2a82c67c0ec45469ebc304ae30668b008ce09e11",
    "runtime_cache_recheck_verdict_sha256": "edde1690ad3d7b69b77db14f1b36c31a697299a36e535ebcba0dd0d2866f6dfd",
    "architecture_decision": "KEEP + HARDEN: split pure evaluation/transition compilation from provider-blocked worker and persistence integration"
  },
  "required_docs": [
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence.md", "sections": ["V0 monitoring persistence"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-correction.md", "sections": ["Signal alert truth and provenance correction"]},
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Alerts, Paper and Both orchestration", "Staged graph execution and cache contract", "Verification and deployment decision"]},
    {"path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md", "sections": ["1. Compile a resource plan with every strategy", "4. Evaluation clocks/triggers", "6. Cache identity", "9. Resource QoS priorities", "10. Per-deployment resource ceilings"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "V1 release gate"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/monitoring/evaluation.py",
    "paper-trader/backend/app/monitoring/state_contracts.py",
    "paper-trader/backend/app/monitoring/repository.py",
    "paper-trader/backend/tests/test_v0_monitoring_evaluation_transition.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-evaluation-transition-foundation.md",
    ".agent/runs/strategy-os-v0-monitoring-evaluation-transition-foundation"
  ],
  "new_paths": [
    "paper-trader/backend/app/monitoring/evaluation.py",
    "paper-trader/backend/app/monitoring/state_contracts.py",
    "paper-trader/backend/tests/test_v0_monitoring_evaluation_transition.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-evaluation-transition-foundation.md",
    ".agent/runs/strategy-os-v0-monitoring-evaluation-transition-foundation"
  ],
  "protected_paths": [
    "paper-trader/backend/app/monitoring/contracts.py",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/market_data",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Call app.ir.runtime.evaluate_v2 exactly once over the supplied accepted resolved graph and registry. Do not create a second evaluator, IR, resolver, cache or result authority.",
    "Verify the compiler-issued schedule and evaluation event, active owner-scoped assignment, graph/implementation/registry/resource/trigger bindings and current predecessor snapshot before reading evaluator outputs.",
    "Accept only closed monitoring-target-intent/1 and monitoring-protection/1 graph outputs whose authored component, contract and parameter addresses reconstruct against the accepted monitoring Type-1 catalogue.",
    "Derive deterministic FLAT/LONG/SHORT transitions and BUY/SELL/EXIT/HOLD actions. Ambiguous simultaneous targets, missing/duplicate protection, invalid units/decimals/geometry or foreign assignment facts refuse.",
    "Resolve percentage and point/distance SL/TP from the completed-event entry reference for long and short states, create one next MonitoringStateSnapshot and one MonitoringSignalEvent, then call the accepted derive_signal_alert contract.",
    "Provider evidence and dataset identity enter only as validated content addresses. No provider adapter, connection, credential, repository session, worker, API, execution, order, position, capital, PnL or money path is reachable."
  ],
  "acceptance": [
    "An actual resolved V2 fixture produces BUY LONG at entry 100 with SL 5% -> 95 and TP 15% -> 115, plus the exact canonical SignalAlert.",
    "SELL SHORT resolves SL above and TP below entry; EXIT returns FLAT; false targets produce HOLD/NoAlert; repeated target and protection-only updates remain explicit.",
    "Multiple requested targets, absent/duplicate stop or target evidence, open/forged output documents, assignment/schedule/graph/registry/resource mismatches and invalid geometry refuse with stable typed codes.",
    "Appending a later evaluated event cannot change the earlier snapshot, event, alert or addresses; deterministic replay returns byte-identical facts.",
    "A source/import guard and poisoned objects prove no provider, broker, execution, order, position, capital, PnL, credential, database session, network or deployment reachability.",
    "Below/at/above the closed graph-output bound and representative repeated evaluations prove deterministic resource behavior.",
    "Focused and affected monitoring/IR suites, isolated killed/restored guards, protected manifests, architecture validation and one independent Critical review pass."
  ],
  "test_plan": [
    "RED/GREEN actual-v2 evaluation fixtures for transition/action/protection truth and every typed refusal.",
    "Causal-prefix, deterministic replay, owner/assignment binding, output-bound and no-authority/import tests.",
    "Isolated mutations for schedule binding, ambiguous-target refusal and direction-aware protection geometry; restore and rerun.",
    "Focused monitoring/IR affected suites, resource probe, protected manifests and architecture validation before one Critical review."
  ],
  "risk_classification": {"tier": "Critical", "reason": "A false target transition, SL/TP value, causal event or tenant binding can directly mislead a trader even without execution authority."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "implementation_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PENDING",
    "focused_passed": 32,
    "affected_passed": 462,
    "affected_skipped": 17,
    "affected_excluded_stale": 2,
    "mutations_killed_restored": 7,
    "resource_probe": {"runs": 50, "deterministic_address_sets": 1, "elapsed_seconds": 87.902002, "peak_traced_bytes": 5685075},
    "protected_repo_files": 350,
    "protected_external_frontend_files": 996,
    "protected_deltas": 0,
    "architecture_files": 439,
    "provider_network": false,
    "persistence": false,
    "execution_authority": false,
    "report": ".agent/runs/strategy-os-v0-monitoring-evaluation-transition-foundation/report.md"
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_sha256": "1a6b481e3c13dfe17156cc8d975a644bfe3a224350ad248bb05c90e57d8244a4",
    "open_findings": ["V0-MET-CR-001", "V0-MET-CR-002", "V0-MET-CR-003", "V0-MET-CR-004"],
    "owner_authorized_contract_separation": "Move the sole pure assignment/state dataclasses from repository.py to new state_contracts.py and re-export; no schema/model/repository behavior change.",
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PASS",
    "registry_authority": "Exact PlatformRegistry type, current snapshot address, graph-node descriptors, registrations, implementation addresses and callable identity verify before evaluate_v2.",
    "pure_state_contracts": "MonitoringAssignmentSpec, MonitoringAssignment and MonitoringStateSnapshot moved without duplication to app.monitoring.state_contracts; repository re-exports them and migration/persistence behavior remains green.",
    "pre_evaluation_output_bound": 64,
    "new_evidence": ["point_and_verified_distance_geometry", "true_two_event_chain", "poisoned_registry", "fresh_import_closure", "duplicate_protection", "forged_authorship"],
    "rechecks_used": 1,
    "rechecks_remaining": 0
  },
  "final_review": {
    "verdict": "SPEC PASS / QUALITY PASS / final PASS",
    "recheck_verdict_sha256": "fe64a98ed42b823b46f0389a1f8f0a3bd11e028f37d61e83fc9c9fc25b5274d6",
    "closed_findings": ["V0-MET-CR-001", "V0-MET-CR-002", "V0-MET-CR-003", "V0-MET-CR-004"],
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "deployment": false
  },
  "review": {
    "required": true,
    "assignment_id": "v0_monitoring_evaluation_transition_critical_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Monitoring transition, causal truth, SL/TP geometry and tenant binding are Critical decision-support boundaries.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-monitoring-evaluation-transition-foundation/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/monitoring/evaluation.py",
      "paper-trader/backend/app/monitoring/state_contracts.py",
      "paper-trader/backend/app/monitoring/repository.py",
      "paper-trader/backend/tests/test_v0_monitoring_evaluation_transition.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-evaluation-transition-foundation.md",
      ".agent/runs/strategy-os-v0-monitoring-evaluation-transition-foundation"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/monitoring/contracts.py",
      "paper-trader/backend/app/ir",
      "paper-trader/backend/app/market_data",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/ledger",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-monitoring-evaluation-transition-foundation/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Standing V0 authority and accepted launch queue permit the pure monitoring evaluation seam only.",
    "Owner-authorized correction permits only the pure state-contract extraction and repository re-export recorded in first_review; no schema/model/query/transaction behavior changes.",
    "No provider/network/right decision, schema/migration, worker/service, API/frontend, Paper/live execution, order, position, capital, PnL, money or deployment action."
  ],
  "stop_conditions": [
    "The correction requires any further accepted contract/repository/IR/provider/schema/API/frontend path change.",
    "Evaluator output cannot be bound to accepted authored monitoring component identities without a second authority.",
    "Provider readiness, data rights or worker/service behavior would be inferred rather than refused/deferred."
  ],
  "deployment_impact": {"classification": "compatible unpublished pure compiler; monitor service remains architecture-changing and blocked", "required_evidence": "Pure deterministic behavior, resource bound, protected paths and Critical review. No runtime-service or deployment claim.", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "external_findings": [
    "tests/test_v0_monitoring_intent_contract.py retains two pre-catalogue assertions that monitoring Type-1 is unpublished and library.py has its old hash; the accepted verified-language catalogue supersedes both. This slice preserves that protected historical test and excludes only those exact nodes from the affected gate."
  ],
  "nonclaims": ["No provider acquisition, persistence transaction, delivery, attention, worker, monitor readiness, API, Alerts Inbox, Paper/live execution, order, position, capital, PnL, release deployability, deployment or V0 completion."]
}
---

# V0 monitoring evaluation transition foundation

This pure slice translates one accepted canonical V2 evaluation into the existing
monitoring state, event and alert facts. The blocked provider and service runtime
remain separate successors.
