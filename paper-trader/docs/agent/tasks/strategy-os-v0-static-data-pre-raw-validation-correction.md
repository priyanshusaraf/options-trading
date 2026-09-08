---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-static-data-pre-raw-validation-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_fresh_pre_raw_privacy_correction",
  "goal": "Ensure every present Kite quote row is closed and minimally valid before raw payload encoding or RawObservationSegment construction can observe it.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The exhausted-review session_cookie counterexample is RED then GREEN with zero _payload_bytes and _segment calls, valid documented rows still map identically, the prior 45-focused and affected provider cone remain green, an ordering mutation fails and restores exactly, and one fresh independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  },
  "risk_tags": ["critical", "provider-adapter", "privacy", "raw-evidence", "market-truth", "tenant-isolation"],
  "depends_on": ["strategy-os-v0-capability-evidence-closure"],
  "dependency_gate": {
    "predecessor_capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-observation-eligibility-wave.md",
    "review_task": "/root/static_data_wave_review",
    "review_package_sha256": "619a697ffd0d97a80050c7f78f3e2db61769a7126aa36d472fdf8187f1256109",
    "open_finding": "V0-SDW-CR-001",
    "rechecks_remaining": 0,
    "replan_decision": "KEEP + MOVE CLOSED ROW PREFLIGHT BEFORE RAW EVIDENCE"
  },
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-observation-eligibility-wave.md",
      "sections": ["first_review", "exhausted_recheck", "correction_scope"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave/report.md",
      "sections": ["Kite canonical observation lane", "Critical-review correction"]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
      "sections": ["9. Missing-data semantics", "13. Dataset provenance"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/market_data/kite_observations.py",
    "paper-trader/backend/tests/test_v0_kite_observations.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-pre-raw-validation-correction.md",
    ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-pre-raw-validation-correction.md",
    ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/market_data/capability.py",
    "paper-trader/backend/app/market_data/provider_evidence.py",
    "paper-trader/backend/app/market_data/authority.py",
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/app/market_data/dataset_authority.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/market_data/eligibility.py",
    "paper-trader/backend/app/market_truth",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/backend/research_tests",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Preflight every present response row immediately after the closed outer envelope and unrequested-instrument check. Absent requested rows remain typed unavailable.",
    "Before any call to _payload_bytes or _segment, require exact dict type, a subset of the documented quote-row allowlist and the required instrument_token/timestamp keys.",
    "Reuse the preflighted rows during mapping; do not create a second raw authority, copy provider payloads, change canonical identity or broaden accepted Kite shapes.",
    "Add a direct spy regression proving an undocumented session_cookie reaches neither raw encoder nor segment constructor. Preserve all prior NFO, depth, causality, absence, resource and no-network behavior."
  ],
  "acceptance": [
    "The exact session_cookie payload refuses before _payload_bytes and _segment; both spy counts remain zero.",
    "Malformed row type, undocumented key and missing required key all refuse before raw evidence; absent requested quote keys remain ProviderUnavailable rather than errors or zeros.",
    "A valid documented full quote produces the exact prior canonical batch identity and five-level depth observations.",
    "Focused Kite plus integrated static-data tests pass; an isolated mutation that moves/removes preflight ordering fails the spy regression and exact source bytes restore.",
    "No provider transport, credential, network, schema, route, runtime, frontend, deployment, live/order or money behavior changes.",
    "One fresh independent Critical SPEC and QUALITY review passes."
  ],
  "test_plan": [
    "Add the direct pre-raw spy reproduction first, make the smallest preflight ordering correction, then rerun the focused Kite mapper and prior integrated static-data cone.",
    "Run one isolated ordering mutation, exact restoration, compilation, diff, architecture and scoped protected-source checks before the fresh review package."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "Allowing unrequested or secret-bearing provider fields into raw evidence can create a durable privacy and tenant-boundary failure even when mapping later refuses."
  },
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root",
  "implementation_result": {
    "status": "IMPLEMENTATION PASS / REVIEW PENDING",
    "red": "session_cookie reached _payload_bytes and _segment before refusal",
    "green": "session_cookie refuses with zero _payload_bytes and _segment calls",
    "focused_kite": 26,
    "integrated_focused": 47,
    "affected_passed": 557,
    "affected_skipped": 2,
    "affected_external_failures": ["tests/test_phase4_market_truth_persistence.py::test_phase4_sqlite_refuses_destructive_downgrade_and_repairs_forward (known 0047-to-0046 downgrade blocker)"],
    "ordering_mutation": "killed and isolated; production bytes remained green",
    "protected_deltas": 0,
    "architecture_files": 434,
    "report": ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction/report.md"
  },
  "first_review": {
    "review_task": "/root/pre_raw_validation_review",
    "verdict_path": ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction/review/verdict.json",
    "verdict_sha256": "39eda4db0fb89de38a6a94e072a34fccec216c50bfb1760a6b01c80866150dba",
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "open_findings": ["V0-SDPV-CR-001"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "V0-SDPV-CR-001: distinguish a truly absent requested quote key from a present JSON-null row using membership before value access; present null must refuse as malformed before _payload_bytes or _segment and never become MISSING_QUOTE_KEY."
  ],
  "correction_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PENDING",
    "red": "present JSON null produced MISSING_QUOTE_KEY and did not raise",
    "green": "present JSON null refuses as malformed before raw encoding or segment construction",
    "absence_semantics": "quote_key membership distinguishes absent from present-null",
    "focused_kite": 26,
    "integrated_focused": 47,
    "mutation": "data.get null/absence conflation killed and exact production regression restored",
    "protected_deltas": 0,
    "architecture_files": 434
  },
  "final_review": {
    "review_task": "/root/pre_raw_validation_review",
    "review_package_sha256": "c365c5bc5fdb4d4d352923528d0490d35091b3dfeb629ea2ce22ada5c310c4b6",
    "verdict_path": ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction/review/recheck-verdict.json",
    "verdict_sha256": "aeb7949cbc50c31b2e87cfb6124f66a37c4e9520a67729023be04b222e835629",
    "verdict": "SPEC PASS / QUALITY PASS",
    "closed_findings": ["V0-SDPV-CR-001", "V0-SDPV-EG-001"],
    "nonblocking_evidence_gaps": ["Untracked scoped paths do not provide a baseline-to-final Git patch; exact hashes, mutation evidence and independent probes remain available."],
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "highest_claim": "bounded offline Kite quote-row preflight locally runnable",
    "provider_open": false,
    "deployment": false
  },
  "review": {
    "required": true,
    "assignment_id": "v0_static_data_pre_raw_validation_correction_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Raw provider evidence is durable provenance; privacy rejection ordering is a Critical boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/market_data/kite_observations.py",
      "paper-trader/backend/tests/test_v0_kite_observations.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-pre-raw-validation-correction.md",
      ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/providers",
      "paper-trader/backend/app/market_data/eligibility.py",
      "paper-trader/backend/app/market_data/capability.py",
      "paper-trader/backend/app/market_data/provider_evidence.py",
      "paper-trader/backend/app/market_data/authority.py",
      "paper-trader/backend/app/market_truth",
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/ledger",
      "paper-trader/backend/research_tests",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-static-data-pre-raw-validation-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Standing V0 development authority permits this bounded offline correction and fresh review.",
    "No provider credentials/network/recording, vendor/data-right entitlement, public capability, capture, route registration, monitoring/Paper activation, deployment, live/order or money action."
  ],
  "stop_conditions": [
    "The fix requires a provider transport, shared raw-schema/identity, protected capability/authority, schema/migration, API or frontend change.",
    "A documented quote shape must be narrowed or expanded beyond the accepted allowlist to satisfy the spy regression.",
    "Concurrent work changes either owned product/test path without exact attribution."
  ],
  "deployment_impact": {
    "classification": "compatible provider-adapter privacy ordering correction; no activation",
    "required_evidence": "Offline RED/GREEN, affected static-data cone, mutation/restoration and protected-source equality. Highest claim remains locally runnable.",
    "release_deployable": false,
    "production_rehearsed": false,
    "deployed": false
  },
  "nonclaims": [
    "No real Kite conformance, data rights, expiry/reconnect guarantee, prospective capture, public connection, monitoring, Paper, frontend, release deployability, deployment or V0 completion."
  ]
}
---

# Static-data pre-raw validation correction

Close quote rows before any raw evidence operation. Preserve the accepted provider,
market-truth, dataset, graph, eligibility and runtime boundaries unchanged.
