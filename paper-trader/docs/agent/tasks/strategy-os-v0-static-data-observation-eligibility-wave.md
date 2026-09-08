---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "phase": "v0",
  "status": "rejected_replan_required",
  "kind": "critical_parallel_static_data_observation_and_eligibility_integration",
  "goal": "Map sanitized Kite-shaped market facts into canonical observations and compile exact graph/dataset capability into typed eligibility or refusal before research, monitoring or Paper can consume data.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Kite mapping and graph-data eligibility lanes are integrated without shared writes; official-shape positive/negative fixtures, causal timestamps, missing OI/depth, expired-option/history, tenant/privacy, bounded resource and no-network tests pass; the exact affected consumer cone and one independent integrated Critical SPEC/QUALITY review pass."
  },
  "risk_tags": [
    "critical",
    "provider-adapter",
    "market-truth",
    "anti-lookahead",
    "options-data-refusal",
    "tenant-isolation",
    "parallel-disjoint"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/capsule-queue.json",
      "sections": ["strategy-os-v0-kite-canonical-observations", "strategy-os-v0-graph-data-eligibility"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/strategy-os-v0-capability-evidence-closure.md",
      "sections": ["final_review"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-capability-evidence-closure/official-source-matrix.md",
      "sections": ["Official Kite facts", "Controlling V0 disposition"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-q03-cold-admission-clarification/dataset-contract.md",
      "sections": ["Scope and authority", "Executable segment interpretation", "Real consumers and evidence", "Deployment and remaining gates"]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
      "sections": ["7. Data sufficiency", "8. Live versus historical capability", "9. Missing-data semantics", "10. Cross-instrument alignment", "11. Cross-timeframe causality", "13. Dataset provenance"]
    }
  ],
  "dependency_gate": "Accepted capability-evidence closure verdict SHA-256 5f32ae3ec7de032ad4b3d3c02381b65518d4759dd62439347ac4089a39ba6cce; accepted data-only connection and canonical dataset bridge remain immutable dependencies.",
  "allowed_paths": [
    "paper-trader/backend/app/providers/kite.py",
    "paper-trader/backend/app/providers/base.py",
    "paper-trader/backend/app/market_data/kite_observations.py",
    "paper-trader/backend/tests/test_v0_kite_observations.py",
    "paper-trader/backend/app/market_data/eligibility.py",
    "paper-trader/backend/app/api/data_eligibility_routes.py",
    "paper-trader/backend/tests/test_v0_graph_data_eligibility.py",
    "paper-trader/backend/research_tests/test_v0_options_dataset_eligibility.py",
    "paper-trader/backend/research_tests/test_canonical_dataset.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-observation-eligibility-wave.md",
    ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave"
  ],
  "new_paths": [
    "paper-trader/backend/app/market_data/kite_observations.py",
    "paper-trader/backend/tests/test_v0_kite_observations.py",
    "paper-trader/backend/app/market_data/eligibility.py",
    "paper-trader/backend/app/api/data_eligibility_routes.py",
    "paper-trader/backend/tests/test_v0_graph_data_eligibility.py",
    "paper-trader/backend/research_tests/test_v0_options_dataset_eligibility.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-observation-eligibility-wave.md",
    ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave"
  ],
  "protected_paths": [
    "paper-trader/backend/app/market_data/capability.py",
    "paper-trader/backend/app/market_data/provider_evidence.py",
    "paper-trader/backend/app/market_data/authority.py",
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/app/market_data/dataset_authority.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/market_truth",
    "paper-trader/backend/app/providers/connection_store.py",
    "paper-trader/backend/app/providers/factory.py",
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/core/release_profile.py",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Lane A maps sanitized current official-shape Kite instrument, historical candle, quote and full-depth payloads into existing canonical provider/raw observation facts. It preserves provider token/symbol only at the adapter edge and never opens transport or credentials.",
    "Lane A distinguishes absent keys/fields from numeric zero, preserves five-level depth shape when present, marks OI/depth unavailable when absent, validates timestamps and refuses forming/future/incoherent facts. No expired contract is resolved from today's instrument dump.",
    "Lane B compiles the existing immutable graph/DataRequirementPlan, selected canonical manifests, provider capability profile/conformance and requested interval into one owner-safe eligibility result before writes/evaluation/cache/runtime.",
    "Lane B returns typed supported/unavailable/insufficient-range/resolution/freshness/session/alignment/depth/entitlement/history-gap refusals. Broad expired-options, historical depth/order flow and unlicensed data remain unavailable. Underlying-only counterfactual requires a distinct graph version.",
    "The two lanes share no write path. Core capability/market-truth/dataset authorities remain immutable. Public route registration, release-profile opening, provider network, capture persistence, monitoring, Paper, billing, deployment, live/order/money work are excluded."
  ],
  "acceptance": [
    "Sanitized official-shape fixtures map exact instrument/provider/mapping/source/timestamp/validity facts; missing quote key, OI or depth never becomes zero or a satisfied capability.",
    "Historical option/expired-token and historical-depth requests refuse unless exact captured canonical authority covers the interval; continuous futures never substitutes for options.",
    "Completed/available/recorded times remain distinct; available_at before completed_at, forming candles, future suffix leakage and inconsistent five-level depth refuse.",
    "Eligibility binds owner, graph/version, plan, capability/conformance/contract, dataset manifest, instruments, fields, requested interval, sessions, rulebook, missing-data and as-of identities; any answer-changing substitution changes identity or refuses.",
    "Same-owner supported cash subset passes; foreign/missing identifiers share private absence with zero writes/evaluation/provider/cache activity.",
    "Options/OI/depth strategies remain authorable but unsupported history yields actionable typed refusal. No silent underlying-only validation or provider switching.",
    "Below/at/above payload, row, instrument, depth, range and request bounds are direct; no network/socket/credential/execution import is reachable.",
    "Each lane provides focused evidence and one isolated guard mutation. Integrated affected tests and one independent Critical SPEC/QUALITY review pass."
  ],
  "test_plan": [
    "Each child begins with RED fixtures and runs only its declared focused tests while writing. Root integrates and runs the combined market-data/provider/research/tenant consumer cone.",
    "Use sanitized official response shapes only; poison network, credentials, provider fallback, execution imports and evaluation side effects.",
    "Prefix/availability tests prove no lookahead. Resource tests measure bounded payload/row/depth/instrument/request behavior.",
    "One isolated mutation per lane with exact baseline/mutated/restored evidence, followed by one integrated Critical review."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "A mapping or eligibility error can certify unavailable options/depth history, misidentify a contract, leak future data or publish a false signal."
  },
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "v0_kite_canonical_observations",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": [],
      "write_paths": [
        "paper-trader/backend/app/providers/kite.py",
        "paper-trader/backend/app/providers/base.py",
        "paper-trader/backend/app/market_data/kite_observations.py",
        "paper-trader/backend/tests/test_v0_kite_observations.py",
        ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave/v0_kite_canonical_observations"
      ],
      "output": ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave/v0_kite_canonical_observations/report.md"
    },
    {
      "id": "v0_graph_data_eligibility",
      "agent": "terra-worker",
      "mode": "write",
      "depends_on": [],
      "write_paths": [
        "paper-trader/backend/app/market_data/eligibility.py",
        "paper-trader/backend/app/api/data_eligibility_routes.py",
        "paper-trader/backend/tests/test_v0_graph_data_eligibility.py",
        "paper-trader/backend/research_tests/test_v0_options_dataset_eligibility.py",
        ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave/v0_graph_data_eligibility"
      ],
      "output": ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave/v0_graph_data_eligibility/report.md"
    }
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root",
  "review": {
    "required": true,
    "assignment_id": "v0_static_data_observation_eligibility_wave_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Integrated provider mapping, causal timestamps, options-history refusal and tenant eligibility are Critical research/signal boundaries.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/providers/kite.py",
      "paper-trader/backend/app/providers/base.py",
      "paper-trader/backend/app/market_data/kite_observations.py",
      "paper-trader/backend/tests/test_v0_kite_observations.py",
      "paper-trader/backend/app/market_data/eligibility.py",
      "paper-trader/backend/app/api/data_eligibility_routes.py",
      "paper-trader/backend/tests/test_v0_graph_data_eligibility.py",
      "paper-trader/backend/research_tests/test_v0_options_dataset_eligibility.py",
      "paper-trader/backend/research_tests/test_canonical_dataset.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-static-data-observation-eligibility-wave.md",
      ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/market_data/capability.py",
      "paper-trader/backend/app/market_data/provider_evidence.py",
      "paper-trader/backend/app/market_data/authority.py",
      "paper-trader/backend/app/market_truth",
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/ledger",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-static-data-observation-eligibility-wave/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "finding_ids": ["V0-SDW-CR-001", "V0-SDW-CR-002"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "exhausted_recheck": {
    "review_task": "/root/static_data_wave_review",
    "review_package_sha256": "619a697ffd0d97a80050c7f78f3e2db61769a7126aa36d472fdf8187f1256109",
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "open_findings": ["V0-SDW-CR-001"],
    "closed_findings": ["V0-SDW-CR-002"],
    "closed_evidence_gaps": ["NFO-FUT/NFO-OPT segment coverage", "open/nonmonotone/crossed/4-level/6-level depth coverage"],
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "smallest_correction": "Validate every present quote row's type, documented top-level field set and required keys before _payload_bytes or _segment can observe the response.",
    "successor": "strategy-os-v0-static-data-pre-raw-validation-correction"
  },
  "correction_scope": [
    "V0-SDW-CR-001: close full-quote rows to the documented field allowlist before raw evidence; add session-cookie, NFO-FUT and depth open/nonmonotone/crossed regressions.",
    "V0-SDW-CR-002: bind the complete requirement instrument type to the canonical input and selected asset; an ECONOMIC_SELECTOR option graph refuses simultaneous cash binding/dataset/capability substitution under the same graph version."
  ],
  "owner_gates": [
    "Standing V0 development authority permits these offline disjoint lanes after accepted capability evidence.",
    "No real provider credential/network/recording, vendor/data-right decision, public capability, route registration, capture service, monitoring/Paper activation, deployment, live order or money action."
  ],
  "stop_conditions": [
    "Either lane requires a protected core authority, shared schema/migration, release-profile/main registration, provider network, credential or external frontend change.",
    "A current instrument dump would be used as historical contract truth or missing OI/depth would be represented as zero.",
    "Eligibility requires evaluation, provider fallback, underlying substitution or a second graph/data authority.",
    "Parallel paths overlap or a concurrent owner changes an assignment path without exact attribution."
  ],
  "deployment_impact": {
    "classification": "compatible provider adapter and research-data contract; no activation",
    "required_evidence": "Offline deterministic tests, bounded resource measurements, no-network proof and exact protected-source equality. Highest claim remains locally runnable."
  },
  "nonclaims": [
    "No real Kite conformance, data rights, exact expiry/reconnect guarantee, historical expired-options/depth breadth, prospective capture, public connection, frontend, monitoring, Paper, deployment or V0 completion."
  ]
}
---

# Static-data observation and eligibility wave

Run two disjoint offline lanes after accepted capability evidence. Root owns
integration, protected-path checks, the heavy affected suite and final review.
