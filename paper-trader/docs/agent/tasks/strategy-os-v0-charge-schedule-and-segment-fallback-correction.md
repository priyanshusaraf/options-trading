---
{
  "id": "strategy-os-v0-charge-schedule-and-segment-fallback-correction",
  "phase": "v0",
  "status": "accepted_via_fresh_paper_entry_lifecycle_successor",
  "kind": "critical_money_research_charge_correction",
  "goal": "Correct stale charge schedules, unknown-segment fallback and unspecified paise rounding through one versioned charge identity used consistently by V0 research and simulated Paper results without changing live authority.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Current official charge sources and assumptions are frozen; unknown segments refuse; every component and aggregate uses one explicit minor-unit rounding contract; research and Paper parity, old-result identity, mutations and one independent Critical SPEC/QUALITY review pass."
  },
  "risk_tags": ["critical", "money", "research-integrity", "provider-coherence", "rounding", "paper-trading", "cache-identity"],
  "required_docs": [
    {"path": ".agent/runs/kleppmann-numeric-and-market-truth-audit/report.md", "sections": ["Findings", "Direct evidence", "Nonclaims"]},
    {"path": ".agent/runs/kleppmann-numeric-and-market-truth-audit/owner/probe-charge-boundaries.log", "sections": ["all output"]},
    {"path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md", "sections": ["Contract identity", "Live versus historical capability", "Dataset provenance", "Provider capability changes"]},
    {"path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md", "sections": ["1. Risk-weighted verification", "2. Test rule", "3. Test cadence"]},
    {"path": "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "sections": ["Decision", "Deterministic policy", "Rollout boundary"]}
  ],
  "dependency_gate": "The active canonical research-spine foundation must release protected engine/backtest charge paths. The correction must be accepted before the frontend product-acceptance recovery may present or accept net-of-charges analytics and before V0 Paper results are accepted.",
  "allowed_paths": [
    "paper-trader/backend/app/engine/charges.py",
    "paper-trader/backend/app/engine/broker.py",
    "paper-trader/backend/app/backtest/identity.py",
    "paper-trader/backend/app/backtest/engine.py",
    "paper-trader/backend/app/backtest/premium.py",
    "paper-trader/backend/research/orchestrator/run.py",
    "paper-trader/backend/tests/test_charge_schedule_correction.py",
    "paper-trader/backend/tests/test_index_futures_config.py",
    "paper-trader/backend/tests/test_equity_short_charge_legs.py",
    "paper-trader/backend/tests/test_backtest_identity.py",
    "paper-trader/backend/research_tests/test_research_run.py",
    "paper-trader/backend/research_tests/test_canonical_dataset.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-charge-schedule-and-segment-fallback-correction.md",
    ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_charge_schedule_correction.py",
    ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/engine/runner.py",
    "paper-trader/backend/app/engine/live_broker.py",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/requirements.lock",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Capture current official provider/exchange/statutory charge sources and retrieval dates before changing a rate. Public pages are evidence, not a private contract-note guarantee; unavailable or cohort-specific rates remain typed UNKNOWN/refused.",
    "Create an immutable versioned charge-schedule document/address. Preserve `zerodha_charges_v1` for historical result reconstruction; V0 corrected research/Paper uses a new explicit identity rather than silently rewriting prior results.",
    "Use exact decimal/minor-unit arithmetic and a declared rounding point/mode for each component and total. Reject binary-float or banker's-rounding ambiguity at the public calculation boundary.",
    "Remove `CHARGE_SCHEDULE.get(segment, NFO)` fallback. Unknown, unsupported or unverified segments fail closed before a result/fill is admitted.",
    "Bind segment, product class, side, turnover units, schedule address and rounding policy into research/Paper result identity and cache identity. Do not infer a historical schedule from a current page.",
    "Prove the same accepted schedule produces equal research and simulated Paper charge components for identical synthetic fills. No provider order, live routing, production contract note, credential or deployment action."
  ],
  "acceptance": [
    "NMT-004 reproduced on pre-correction bytes, including the documented understated sample cases, unknown-segment NFO fallback and rounding ambiguity.",
    "Every supported segment has exact source/version/effective/assumption evidence or a typed refusal; no conservative-looking invented rate is executable.",
    "All monetary outputs are exact integer minor units or a closed exact decimal representation with explicit conversion; component totals conserve exactly across entry/exit, partial close and replay.",
    "Unknown segment, missing rate, stale/unverified schedule, negative/nonfinite inputs, invalid side/quantity and excessive turnover refuse before cache/result/paper-ledger effects.",
    "Old v1 result identities remain reconstructible; corrected v2 schedule/address changes spec, cache and result identity. No same identity can produce two charge answers.",
    "Research/Paper parity, direction-aware short legs, futures/options/equity/intraday samples, exact official examples where available, prefix/restart and isolated rate/fallback/rounding mutations pass.",
    "One independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": [
    "Use current official sources at implementation time and record exact page/document/version/date/hash or access limitation; apply the two-source rule to high-risk rate interpretation.",
    "RED/GREEN exact minor-unit calculations, all supported segments, unknown/stale/unverified refusals, historical v1 reconstruction, v2 identity/cache divergence and research/Paper parity.",
    "Run affected backtest, paper-authority, position/trade/ledger conservation and research-spec suites without live/provider network access; kill and restore fallback, stale-rate and rounding guards.",
    "Seal protected bytes and a Critical review package."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "high", "fork_turns": "none", "service_tier": "priority", "routing_note": "User-owned Critical money/research correction after dependency release."},
  "owner_task": "01a04eb5-7146-78e2-be3a-0e0854ce0755",
  "review": {
    "required": true,
    "assignment_id": "v0_charge_schedule_segment_fallback_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Charges alter reported strategy results, future Paper cash/P&L, cache identity and provider price coherence.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/engine/charges.py",
      "paper-trader/backend/app/engine/broker.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/engine.py",
      "paper-trader/backend/app/backtest/premium.py",
      "paper-trader/backend/research/orchestrator/run.py",
      "paper-trader/backend/tests/test_charge_schedule_correction.py",
      "paper-trader/backend/tests/test_index_futures_config.py",
      "paper-trader/backend/tests/test_equity_short_charge_legs.py",
      "paper-trader/backend/tests/test_backtest_identity.py",
      "paper-trader/backend/research_tests/test_research_run.py",
      "paper-trader/backend/research_tests/test_canonical_dataset.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-charge-schedule-and-segment-fallback-correction.md",
      ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction"
    ],
    "exclude_paths": ["paper-trader/backend/app/providers", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "The canonical research-spine owner released the sealed protected paths; root records this task as the sole Critical correction owner.",
    "No private provider contract inference, real broker call, credential, production data, live execution, hardcoded production rate without evidence, deployment or money movement."
  ],
  "stop_conditions": [
    "A current exact rate or rounding rule requires private contract-note/legal interpretation that is unavailable; retain typed refusal and request owner/counsel direction.",
    "An indispensable correction needs live runner/provider/ledger/schema/dependency/frontend changes or overlaps an active owner.",
    "Historical result reconstruction would require silently changing the answer under the same identity."
  ],
  "deployment_impact": {"classification": "compatible versioned research/Paper calculation change; no schema/dependency/service topology change", "required_evidence": "Exact build/source identities, historical compatibility, cache/result divergence, safe local paper/research tests and release-owner rollback by schedule selection. No deployment claim."},
  "nonclaims": ["No provider conformance, historical statutory schedule completeness, real contract-note equality, public Paper runtime, live execution, deployment, production readiness or V0 completion follows from this correction."],
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction/review/verdict.json",
    "verdict_sha256": "6968903d07d0ae373ae669437602e9fcb5614ae8f74c742f9b451ea79eb38bd4",
    "finding_ids": ["V0-CS-001", "V0-CS-002", "V0-CS-003", "V0-CS-004"],
    "rechecks_remaining": 1
  },
  "focused_recheck": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction/review/recheck-verdict.json",
    "verdict_sha256": "443b4eb6d7012165b8d1af9a1dfda0fd2e3035a1c361907e8c49dff53bb02094",
    "corrected_package_sha256": "ad3a6f2eff984c13be0875d44540ea382c02850e2ea342bad05ee3fc48004710",
    "open_findings": ["V0-CS-001", "V0-CS-003"],
    "closed_findings": ["V0-CS-002", "V0-CS-004"],
    "rechecks_remaining": 0,
    "next_state": "REPLAN_REQUIRED",
    "successor_replan": "strategy-os-v0-paper-charge-authority-and-legacy-identity-replan"
  },
  "terminal_state": {
    "accepted": true,
    "product_and_test_paths_frozen": true,
    "same_lineage_corrections_permitted": false,
    "same_lineage_rechecks_permitted": false,
    "blocking_reasons_closed_by_successor": [
      "A supported Paper open can commit a v2 charge answer whose rounded facts match both v1 and v2 after restart, causing CHARGE_RECEIPT_AMBIGUOUS before a risk-reducing exit.",
      "The legacy compatibility helper trusts caller-supplied old address/base/legs and can associate one claimed legacy identity with different answers."
    ],
    "acceptance_route": "strategy-os-v0-paper-entry-lifecycle-identity-correction",
    "successor_verdict_sha256": "531519fa266b1e2bf568461de3d96c360c5a7ef8ea9d0d582837693bf9ab289b",
    "deployment": false
  },
  "correction_scope": [
    "Route one existing bounded simulated-Paper calculation through explicit v2 selection in `app/engine/broker.py`, preserve live-known-segment v1 behavior, and bind schedule address/rounding policy into the Paper result receipt identity available without schema change. Prove identical synthetic fills across genuinely distinct research and Paper entry points, partial close and restart. Stop/replan if durable identity requires schema work.",
    "Refuse BFO_FUT in v2 until exact independent official BSE futures rate evidence is captured and bound. Resolve intraday average-price STT with two-source exact semantics and round-trip-aware calculation, or refuse intraday v2. Regenerate the v2 address after capability/source changes.",
    "Freeze a genuine pre-correction v1 result/cache receipt from base bytes and preserve its exact legacy identity/answer or provide a content-addressed non-aliasing compatibility mapping. Prove old results remain reconstructible and distinct from v2.",
    "Catch DecimalException around conversion, quantization and arithmetic; map overflow/excess to closed typed refusals with below/at/above ceiling tests.",
    "Rerun distinct Paper/research, identity/cache, partial/restart, official-source, mutation and protected-byte gates; reseal same lineage for the one focused recheck."
  ]
}
---

# V0 charge schedule and segment fallback correction

Correct NMT-004 before any V0 surface presents net-of-charges research or simulated Paper results.
