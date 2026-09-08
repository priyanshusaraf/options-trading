---
{
  "id": "phase4-dataset-causality",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Bind immutable dataset provenance to normalized completed observations, explicit cross-series alignment, existing research identity/cache, and causal evaluation without adding a second runtime or result cache.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after future, forming, stale, misaligned, filled, and incompletely identified results fail closed, corrected data cannot hit old results, prefix parity holds, and phase4-integration-gate is eligible."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "causality",
    "cache-identity",
    "dataset-provenance"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "3. One accepted executable architecture",
        "6. Data observations, alignment, and causality",
        "8. Dataset provenance and cache identity",
        "11. Deployment contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "2. Dependency order",
        "3. Exclusive path ownership",
        "5. Verification cadence",
        "6. Deployment evidence ownership",
        "7. Owner gates and nonclaims"
      ]
    }
  ],
  "dependency_gate": "phase4-data-contract-capability",
  "allowed_paths": [
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/app/market_data/candles.py",
    "paper-trader/backend/app/backtest/dataset_store.py",
    "paper-trader/backend/app/backtest/identity.py",
    "paper-trader/backend/app/backtest/cache.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/tests/test_phase4_dataset_manifest.py",
    "paper-trader/backend/tests/test_phase4_alignment_causality.py",
    "paper-trader/backend/tests/test_phase4_cache_identity.py",
    "paper-trader/docs/agent/tasks/phase4-dataset-causality.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-dataset-causality"
  ],
  "nonclaims": [
    "No second evaluator, cache, provider fallback, production dataset, capacity claim, frontend, deployment, or live authority is added.",
    "A local content address does not prove licensing, provider conformance, production storage, or release recovery."
  ],
  "owner_gates": [
    "Stop before frontend or provider implementation, authoritative live IR, money authority, material live execution changes, credentials, VPS, production data or use, deployment, destructive work, licence-sensitive adoption, or legal/regulatory/commercial decisions.",
    "Stop if work would duplicate accepted IR, validator, resolver, hash, registry, research lineage, execution binding, owner boundary, or authority."
  ],
  "stop_conditions": [
    "Future/forming observations or stale/skewed legs affect accepted earlier output.",
    "Fill, interpolation, derivation, or fallback is implicit or absent from provenance.",
    "A dataset, rulebook, adjustment, alignment, or component correction hits an earlier accepted cache entry."
  ],
  "deployment_impact": {
    "classification": "compatible-runtime-and-storage-consumer-change",
    "affected_dimensions": [
      "Application",
      "Research persistence consumer",
      "Cache identity",
      "Serialization"
    ],
    "required_evidence": "Prefix parity, next-bar compatibility, complete manifest identity, cache separation, correction invalidation, owner isolation, secret exclusion, bounded-query, and affected regressions; capacity and release recovery remain open."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Observations bind event, availability, completion, instrument, field, timeframe, source, truth, and validity identity.",
    "Alignment consumes only available completed observations under explicit age, skew, session, resampling, and invalid policy.",
    "Manifest and result/cache identity contain every answer-changing Phase 4 digest; incomplete legacy rows cannot satisfy Phase 4.",
    "Appending future data cannot change earlier values, validity, selector resolution, or alignment."
  ],
  "test_plan": [
    "Run backend/.venv/bin/python -m pytest -q backend/tests/test_phase4_dataset_manifest.py backend/tests/test_phase4_alignment_causality.py backend/tests/test_phase4_cache_identity.py backend/tests/test_ir_v2_prefix_parity.py backend/tests/test_backtest_cache.py.",
    "Test future append, forming bars, timezone/session, stale/skew, fill, corrections, roll/adjustment, component version, owner, and incomplete legacy identity.",
    "Kill mutations that ignore availability/completion time or omit any answer-changing cache digest."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_dataset_causality_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/market_data/observations.py",
      "paper-trader/backend/app/market_data/candles.py",
      "paper-trader/backend/app/backtest/dataset_store.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/cache.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/tests/test_phase4_dataset_manifest.py",
      "paper-trader/backend/tests/test_phase4_alignment_causality.py",
      "paper-trader/backend/tests/test_phase4_cache_identity.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-dataset-causality/owner_integration/report.md",
    "verdicts": [
      "INTEGRATION"
    ],
    "max_rechecks": 0
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 dataset identity and causality

This is one durable implementation goal. It must retain full command output under its ignored evidence directory through `.codex/scripts/run_logged.py`.
