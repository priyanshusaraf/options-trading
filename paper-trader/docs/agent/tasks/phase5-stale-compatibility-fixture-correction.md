---
{
  "id": "phase5-stale-compatibility-fixture-correction",
  "phase": "phase5",
  "status": "accepted",
  "kind": "correction",
  "goal": "Update four deterministic pre-Phase-5 compatibility fixtures to the accepted graph-attribution, current-head and execution-identity contracts without changing product behavior.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after the legacy receipt test distinguishes graph provenance from receipt authority, sweep identity supplies exact NON_GRAPH attribution, the market-truth test resolves the owning current head, and ratchet parity preserves the admitted strategy tuple; all four isolated and affected suites pass with four killed/restored mutations."},
  "risk_tags": ["compatibility", "graph-attribution", "migration-head", "execution-identity", "false-green"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-integration-evidence-recovery-replan.md", "sections": ["acceptance", "nonclaims"]}, {"path": ".agent/runs/phase5-implementation/owner/report.md", "sections": ["Unresolved broad-process cascade", "Deployment and owner gate"]}],
  "dependency_gate": "phase5-cache-version-contract-correction",
  "allowed_paths": ["paper-trader/backend/tests/test_ir_v2_legacy_compatibility.py", "paper-trader/backend/tests/test_phase4_cache_identity.py", "paper-trader/backend/tests/test_phase4_market_truth_persistence.py", "paper-trader/backend/tests/test_ratchet_live_parity.py", ".agent/runs/phase5-stale-compatibility-fixture-correction", "paper-trader/docs/agent/tasks/phase5-stale-compatibility-fixture-correction.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md"],
  "nonclaims": ["No product, schema, migration, cache, ratchet, attribution, runtime, provider, order, live, deployment, production or Phase 6 change."],
  "owner_gates": ["Stop if any failure requires product behavior or authoritative graph execution rather than a current fixture."],
  "stop_conditions": ["A fifth path is required; a fixture weakens graph attribution or current-head refusal; an isolated selector remains red; a mutation survives."],
  "deployment_impact": {"classification": "none; test-only current-contract correction", "required_evidence": "Legacy IR, Phase4 cache, market-truth migration and ratchet parity suites.", "highest_claim": "locally_runnable"},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Legacy money carriers expose admission authority and graph provenance under the accepted schema.", "Sweep identity receives an exact NON_GRAPH attribution tuple.", "Market-truth persistence uses the owning current execution head without weakening downgrade refusal.", "Ratchet seeding preserves the admitted Position strategy tuple.", "All four original nodes and affected compatibility suites pass; four mutations fail and restore."],
  "test_plan": ["Four direct nodes; affected files/suites; four fixture mutations; protected product hashes; no-runtime-diff audit."],
  "review": {"required": true, "separate_stage": "phase5-review", "assignment_id": "phase5_stale_compat_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/runs/phase5-review/review-package.json", "review_paths": ["paper-trader/backend/tests/test_ir_v2_legacy_compatibility.py", "paper-trader/backend/tests/test_phase4_cache_identity.py", "paper-trader/backend/tests/test_phase4_market_truth_persistence.py", "paper-trader/backend/tests/test_ratchet_live_parity.py"], "exclude_paths": ["paper-trader/frontend"], "output": ".agent/runs/phase5-stale-compatibility-fixture-correction/report.md", "verdicts": ["CORRECTION"], "max_rechecks": 0},
  "result": {"verdict": "CORRECTION PASS", "report": ".agent/runs/phase5-stale-compatibility-fixture-correction/report.md", "report_sha256": "ff7db6ed9cbf382a2a8e856e11acff640060700538153af14565f670331ff2b6", "deployability": ".agent/runs/phase5-stale-compatibility-fixture-correction/deployability.md", "deployability_sha256": "a5b691e6559a9f30befdc04cee402c4060de616fddac0d124d9a7fb9cc55c128", "fixtures": 4, "affected_tests_passed": 79, "mutations": 4, "execution_head": "0041", "product_drift": 0}
}
---

# Phase 5 stale compatibility fixture correction

Four tests move to already-accepted Phase 4/5 contracts; no product byte changes.
