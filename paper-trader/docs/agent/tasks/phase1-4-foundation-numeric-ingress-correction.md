---
{
  "id": "phase1-4-foundation-numeric-ingress-correction",
  "phase": "interphase-4-5",
  "status": "blocked",
  "goal": "Correct A-02 with one source-type-before-coercion OHLCV rule that rejects booleans across preparation, storage, identity, cache, causality, and execution-price handoff while preserving every valid finite byte and address.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "After the research migration correction is root-accepted, one fresh Terra-medium owner may edit only the exact numeric product and test paths below plus this capsule and its ignored evidence. The owner must preserve inherited work and cannot dispatch children.",
    "stopping_condition": "Complete only when every assigned raw OHLCV ingress checks the source type before conversion; Python bool and boolean scalar values refuse in every field before dataset identity or effects; ordinary finite inputs retain exact encoded bytes, addresses, causality, and execution behavior; direct and transitive tests and killed/restored mutations pass from frozen bytes. Stop if the change needs schema, identity versioning, provider expansion, broader numeric semantics, sizing/routing/execution changes, or live/money authority."
  },
  "risk_tags": [
    "critical",
    "numeric-ingress",
    "pre-coercion-validation",
    "dataset-identity",
    "causality",
    "execution-containment"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": ["14.5 One pre-coercion market-number rule", "14.6 Serial currentness and deployability boundary"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": ["9. Foundation migration and numeric correction route"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["DP-011 — Host-language numeric subtypes cross a typed market boundary"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-correction.md",
      "sections": ["Phase 1-4 foundation research migration correction"]
    }
  ],
  "dependency_gate": "phase1-4-foundation-research-migration-correction",
  "audit_binding": {
    "report_sha256": "cec0bdc931632b9297d733fa58f6057a60b32820882af5e90b3184fd88d54d6d",
    "manifest_sha256": "4933505aa93b9a9fc03a08617b933944c28a409269602f53d9060d563f2143c5",
    "findings": ["A-02"]
  },
  "allowed_paths": [
    "paper-trader/backend/app/market_data/candles.py",
    "paper-trader/backend/app/backtest/dataset_store.py",
    "paper-trader/backend/app/backtest/identity.py",
    "paper-trader/backend/app/backtest/sweep.py",
    "paper-trader/backend/tests/test_candle_validation.py",
    "paper-trader/backend/tests/test_dataset_store.py",
    "paper-trader/backend/tests/test_phase4_cache_identity.py",
    "paper-trader/backend/tests/test_phase4_alignment_causality.py",
    "paper-trader/backend/tests/test_foundation_numeric_ingress.py",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-numeric-ingress-correction.md",
    ".agent/runs/phase1-4-foundation-numeric-ingress-correction"
  ],
  "read_only_paths": [
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/backtest/cache.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/research",
    "paper-trader/frontend",
    ".agent/review-package.json",
    ".agent/runs/phase1-4-foundation-audit",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json"
  ],
  "implementation_contract": [
    "Define one public raw market-number conversion in app.market_data.candles. Inspect the source value before float, NumPy, pandas, struct, JSON, hash, or cache conversion.",
    "Reject Python bool and boolean scalar source values for open, high, low, close, and volume. Do not use truthiness defaults that turn False into 0.0.",
    "After the boolean check, retain the current float conversion, finiteness, price positivity, envelope repair, and volume behavior for every other input.",
    "Route candle validation and dataframe creation, sweep provider preparation and pinned reload, dataset binary encoding, and dataset identity through the shared rule. Storage and identity validate independently and do not trust earlier callers.",
    "Do not change NumericValue, canonical IR, dataset encoding layout, identity scheme, cache-key shape, causal completed-bar rules, signals, sizing, routing, or execution semantics.",
    "Normalize refusal at existing boundaries without creating a dataset, address, cache entry, result, signal, sized request, or executable price."
  ],
  "acceptance": [
    "True, False, and boolean scalar values refuse in every OHLCV field through validate_candles, candles_to_df/frame_from, provider sweep preparation, pinned reload, encode_candles, and dataset identity.",
    "The real provider-to-preparation-to-storage/address-to-cache/computation-to-causal-evaluation-to-execution-price containment path refuses before the first authoritative identity or effect.",
    "A compatibility corpus of every ordinary finite type accepted before the correction produces identical float values, binary dataset bytes, dataset addresses, frames, and downstream results.",
    "NaN, infinity, non-positive price, envelope repair, missing-volume compatibility, duplicate, reorder, and causal next-bar behavior retain their existing results outside boolean refusal.",
    "Every direct float conversion over assigned raw OHLCV values is removed or demonstrably consumes a certified stored float; the source-map search records each disposition.",
    "Focused and transitive selectors, both killed/restored mutations, protected hashes, audit hashes, scoped diff, and git diff --check pass."
  ],
  "test_plan": [
    "Reproduce the frozen True-to-1.0 counterexample from audit evidence before correction.",
    "Parameterize True, False, and the installed boolean scalar types across all five fields and every assigned entry point.",
    "Run a direct public lifecycle from provider control through preparation, store/address, cache/computation, causal evaluation, signal and execution-price containment and assert no side effect.",
    "Capture golden encoded bytes and addresses for ints, floats, decimal values, numeric strings, and other existing accepted finite fixtures before and after correction.",
    "Run existing candle, dataset-store, cache-identity, alignment-causality, handwritten causality, and execution-containment selectors without editing read-only execution tests.",
    "Run source-map scans for float, int, NumPy, pandas, struct, and JSON coercion at assigned OHLCV boundaries; record handled and certified-only sites."
  ],
  "mutations": [
    "Remove the shared boolean source-type guard; the focused matrix and real lifecycle must fail.",
    "Replace one sweep or storage adoption with direct float coercion; the caller-adoption test must fail.",
    "Restore every changed byte before final selectors and record pre/post hashes."
  ],
  "deployment_impact": {
    "classification": "compatible application-contract correction",
    "changes": ["boolean OHLCV refusal before coercion"],
    "unchanged": ["schema", "migration", "dependencies", "configuration", "services", "providers", "frontend", "valid finite identity", "live and money semantics"],
    "highest_claim": "focused locally_runnable behavior",
    "future_gates": ["transitive current-byte revalidation", "independent critical review", "existing Phase 6 and V1 deployment gates"]
  },
  "owner_gates": [
    "Stop if any previously accepted non-boolean finite input changes bytes, address, result, or execution semantics; identity versioning needs a separate architecture and owner decision.",
    "Stop before provider adapter expansion, schema/migration work, strategy changes, sizing, routing, execution, frontend, deployment, production, live, or money changes."
  ],
  "stop_conditions": [
    "Any assigned raw OHLCV coercion remains ahead of source-type validation or any boolean case reaches identity or effects.",
    "Any valid finite input changes encoded bytes, address, causal result, signal, sizing, or execution behavior.",
    "Any mutation survives, assigned surface remains unclassified, or audit/protected hash changes."
  ],
  "nonclaims": [
    "Acceptance closes only A-02 product and focused evidence; it does not make dependent packages or reviews current.",
    "The correction does not prove provider conformance, release deployability, runtime readiness, or money safety beyond the named refusal."
  ],
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_numeric_ingress_owner",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/market_data/candles.py",
      "paper-trader/backend/app/backtest/dataset_store.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/sweep.py",
      "paper-trader/backend/tests/test_candle_validation.py",
      "paper-trader/backend/tests/test_dataset_store.py",
      "paper-trader/backend/tests/test_phase4_cache_identity.py",
      "paper-trader/backend/tests/test_phase4_alignment_causality.py",
      "paper-trader/backend/tests/test_foundation_numeric_ingress.py",
      ".agent/runs/phase1-4-foundation-numeric-ingress-correction"
    ],
    "exclude_paths": ["paper-trader/backend/research", "paper-trader/frontend", "paper-trader/backend/app/engine", "paper-trader/backend/app/providers"],
    "output": ".agent/runs/phase1-4-foundation-numeric-ingress-correction/owner/report.md",
    "verdicts": ["IMPLEMENTATION_ACCEPTABLE", "BLOCKED"]
  }
}
---

# Phase 1-4 foundation numeric ingress correction

This capsule owns one shared boolean-before-coercion OHLCV rule and its focused
evidence. It changes no valid finite identity, execution semantics, or money
authority.
