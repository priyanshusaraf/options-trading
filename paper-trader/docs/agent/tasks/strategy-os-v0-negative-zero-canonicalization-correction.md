---
{
  "id": "strategy-os-v0-negative-zero-canonicalization-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_market_numeric_identity_correction",
  "goal": "Correct NMT-003 so market numeric ingress cannot create different canonical identities for positive and negative zero while preserving finite-value and stored-evidence compatibility.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "NMT-003 is reproduced; the one numeric ingress normalizes signed zero with explicit compatibility; raw/normalized observation and dataset/cache identities converge safely; mutations and one independent Critical SPEC/QUALITY review pass."},
  "risk_tags": ["critical", "market-data", "numeric-ingress", "canonical-identity", "cache-integrity", "research-integrity"],
  "required_docs": [
    {"path": ".agent/runs/kleppmann-numeric-and-market-truth-audit/report.md", "sections": ["Findings", "Direct evidence", "Nonclaims"]},
    {"path": ".agent/runs/kleppmann-numeric-and-market-truth-audit/owner/probe-negative-zero-identity.log", "sections": ["all output"]},
    {"path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md", "sections": ["Contract identity", "Missing-data semantics", "Dataset provenance"]}
  ],
  "dependency_gate": "Canonical research-spine foundation paths are sealed and released. No provider or schema authority follows.",
  "allowed_paths": [
    "paper-trader/backend/app/market_data/numeric.py",
    "paper-trader/backend/app/market_data/provider_evidence.py",
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/research/data/store.py",
    "paper-trader/backend/tests/test_phase4_numeric_ingress.py",
    "paper-trader/backend/tests/test_phase4_authority_integration.py",
    "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py",
    "paper-trader/backend/tests/test_phase4_authority_timestamp_normalization.py",
    "paper-trader/backend/research_tests/test_datastore.py",
    "paper-trader/backend/research_tests/test_research_run.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-negative-zero-canonicalization-correction.md",
    ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction"
  ],
  "new_paths": [".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction"],
  "protected_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/providers", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/research/domain", "paper-trader/backend/research/orchestrator", "paper-trader/backend/research/pipeline", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Normalize every accepted numeric zero to positive zero at the single raw-market ingress before canonical serialization/addressing. Preserve None/missing, nonfinite refusal and bool/type rejection.",
    "Trace provider observation, normalized observation, dataset segment/manifest and cache/result identities so semantically equal zero cannot split them.",
    "Define compatibility for any stored signed-zero bytes; do not alias two historical addresses silently or accept stale canonical bytes as current.",
    "No indicator formula, float64 port/unit contract, provider adapter, schema, dependency, frontend or deployment change."
  ],
  "acceptance": [
    "+0.0 and -0.0 normalize to one public numeric value and one new canonical identity across raw/normalized observation and dataset/cache inputs; sign-bit mutations cannot survive ingress.",
    "Nonzero subnormal/finite values remain distinct; NaN/Inf/bool/text ambiguity and negative quantities refuse under existing contracts.",
    "Existing stored evidence either verifies under its explicit historical version or refuses as stale; no two-byte identities are silently merged in persistence.",
    "Prefix/restart/cache tests and genuine sign-normalization/decoder mutations pass after exact restoration.",
    "One independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": ["RED/GREEN NMT-003 across ingress, provider/normalized observation, dataset identity and cache keys; run affected market-data/dataset authority suites.", "Kill zero-normalization and stale-byte guards; seal protected bytes and Critical package."],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "high", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "01a04eb9-3098-7063-ab34-e8c17a769b25",
  "review": {"required": true, "assignment_id": "v0_negative_zero_canonicalization_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Market data and cache identity are Critical research truth.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction/review-package.json", "review_paths": ["paper-trader/backend/app/market_data/numeric.py", "paper-trader/backend/app/market_data/provider_evidence.py", "paper-trader/backend/app/market_data/observations.py", "paper-trader/backend/research/data/store.py", "paper-trader/backend/tests/test_phase4_numeric_ingress.py", "paper-trader/backend/tests/test_phase4_authority_integration.py", "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py", "paper-trader/backend/tests/test_phase4_authority_timestamp_normalization.py", "paper-trader/backend/research_tests/test_datastore.py", "paper-trader/backend/research_tests/test_research_run.py", "paper-trader/docs/agent/tasks/strategy-os-v0-negative-zero-canonicalization-correction.md", ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction"], "exclude_paths": ["paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/providers", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["Standing V0 correction authority after sealed foundation release; no repeated token.", "No provider network, production data, schema, dependency, live, order, money or deployment action."],
  "stop_conditions": ["Correction requires silent historical-address aliasing, schema migration or provider changes.", "An active owner overlaps an allowed path."],
  "deployment_impact": {"classification": "compatible numeric-ingress identity correction; no schema/dependency/service change", "required_evidence": "stored compatibility, cache/result divergence, restart and rollback by input-contract version"},
  "implementation_result": {
    "status": "review_package_ready",
    "owned_changes": ["paper-trader/backend/app/market_data/numeric.py", "paper-trader/backend/app/market_data/observations.py", "paper-trader/backend/tests/test_phase4_numeric_ingress.py", "paper-trader/docs/agent/tasks/strategy-os-v0-negative-zero-canonicalization-correction.md"],
    "tests_passed": 240,
    "mutations_killed_and_restored": 3,
    "review_package": ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction/review-package.json",
    "reviewer_launched": false,
    "protected_charge_sha256": "63c54f0a96fe665bdcd64cadf83c9d889c6e5dfe04f8f4905e973db901553dd7",
    "deployment": false
  },
  "nonclaims": ["No unit-typed ports, provider conformance, dataset breadth, frontend acceptance, deployment, live/order/money or V0 completion."],
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction/review/verdict.json",
    "verdict_sha256": "dc4b0c768235d1f479192de333931ecfd95be59a4428d6146c7cd83cd4e14363",
    "finding_ids": ["V0-NZ-001", "V0-NZ-002"],
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Make `research/data/store.py` use the normalized value returned by `market_float` when hashing current dataset identity; preserve every nonzero finite representation.",
    "Add current +0/-0 Dataset and ExperimentSpec/cache convergence through real materialization consumers without silently rewriting or aliasing historical signed-zero artifacts.",
    "Add one end-to-end raw/provider/normalized/segment/manifest/research fixture that preserves distinct raw evidence while converging semantic zero only where identity semantics require it.",
    "Add a genuinely fresh-process durable legacy negative-zero artifact read/refusal receipt under restored current code, with exact selectors/commands and IDs.",
    "Kill a mutation that calls `market_float` but discards its return at a dataset identity consumer; restore exact bytes and reseal same lineage for one focused recheck."
  ],
  "correction_result": {
    "status": "accepted_after_focused_recheck",
    "first_review_verdict_sha256": "dc4b0c768235d1f479192de333931ecfd95be59a4428d6146c7cd83cd4e14363",
    "resolved_findings": ["V0-NZ-001", "V0-NZ-002"],
    "owned_product_changes": ["paper-trader/backend/research/data/store.py"],
    "owned_test_changes": ["paper-trader/backend/tests/test_phase4_numeric_ingress.py", "paper-trader/backend/research_tests/test_datastore.py", "paper-trader/backend/research_tests/test_research_run.py"],
    "affected_tests_collected": 123,
    "affected_tests_passed": 122,
    "affected_tests_skipped": 1,
    "mutations_killed_and_restored": 1,
    "review_package": ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction/review-package.json",
    "correction_report": ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction/correction-v0-nz/report.md",
    "recheck_remaining": 0,
    "reviewer_launched": true,
    "deployment": false
  },
  "focused_recheck": {
    "verdict": "SPEC PASS / QUALITY PASS / final PASS",
    "verdict_path": ".agent/runs/strategy-os-v0-negative-zero-canonicalization-correction/review/recheck-verdict.json",
    "verdict_sha256": "35c6b9d679214c398f29d42e117267250229f1ad03ca505b5b1ee13dfafde5a9",
    "verdict_seal_sha256": "dc84ec6befde467ab74efd63551a152f663373943b8d7939bdcbfa4bb6ebb12a",
    "corrected_package_sha256": "d79174345b5ab65ce538184d677df02c432d36eb0ff17fc827b04955aac91def",
    "recheck_package_seal_sha256": "8136be4873f26bfeb200d202e09af99bd55a862e3065bf78038c7d7b4c6f2485",
    "independent_replay_sha256": "393563550ee5d50b99e0bc90b853adc7b62422f51a5c1d969d7f7878a8596206",
    "closed_findings": ["V0-NZ-001", "V0-NZ-002"],
    "rechecks_remaining": 0
  }
}
---

# V0 negative-zero canonicalization correction

Correct NMT-003 at the one market numeric ingress without silent historical identity aliasing.
